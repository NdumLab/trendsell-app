"""Durable workspace-deletion intent and post-restore replay.

The primary database cannot remember that a workspace was deleted after an older backup
is restored: the deletion happened *after* that recovery point.  This module keeps a
small append-only register outside PostgreSQL.  An entry is durably written and
checksummed before the database transaction removes live rows.  Startup and the restore
tool replay every valid entry, so a crash or an older database restore cannot resurrect a
workspace whose owner already requested deletion.

Entries contain only pseudonymous database identifiers and the one-way rate-limit
fragments needed to remove restored buckets.  They contain no email address, record
payload, password, token, or session credential.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from sqlalchemy.orm import Session as OrmSession

from .db import (Audit, Invitation, RateBucket, Record, RecoveryToken, Session, User,
                 Workspace)


SCHEMA = 'trendsell-deletion/1'
ENTRY_NAME = re.compile(r'^[0-9a-f]{32}\.json$')
HEX_DIGEST = re.compile(r'^[0-9a-f]{64}$')


class DeletionRegisterError(RuntimeError):
    """The register is unavailable or contains an unverifiable entry."""


@dataclass(frozen=True)
class ReplayResult:
    entries: int
    workspaces_deleted: int


class DeletionRegister:
    """A directory of immutable JSON entries with adjacent SHA-256 sidecars."""

    def __init__(self, directory: str | Path | None):
        self.directory = Path(directory) if directory else None

    @property
    def enabled(self) -> bool:
        return self.directory is not None

    def _directory(self, *, prepare: bool = True) -> Path:
        if self.directory is None:
            raise DeletionRegisterError(
                'Workspace deletion is unavailable because no deletion register is configured.')
        try:
            if self.directory.is_symlink():
                raise DeletionRegisterError('The deletion register must not be a symbolic link.')
            if prepare:
                self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                # Do not broaden an operator-created directory. Tighten only the mode
                # bits; ownership remains an installation concern.
                self.directory.chmod(0o700)
            elif not self.directory.is_dir():
                raise DeletionRegisterError('The deletion register does not exist.')
        except OSError as error:
            action = 'writable' if prepare else 'readable'
            raise DeletionRegisterError(
                f'The deletion register is not {action}.') from error
        return self.directory

    @staticmethod
    def _payload(workspace_id: str, member_ids: list[str], rate_fragments: list[str],
                 requested_at: str, request_id: str) -> dict:
        return {
            'schema': SCHEMA,
            'event_id': uuid.uuid4().hex,
            'workspace_id': workspace_id,
            'requested_at': requested_at,
            'request_id': request_id,
            'member_ids': sorted(set(member_ids)),
            'rate_fragments': sorted(set(rate_fragments)),
        }

    def record(self, *, workspace_id: str, member_ids: list[str],
               rate_fragments: list[str], requested_at: str, request_id: str) -> dict:
        """Fsync one deletion intent before the caller changes PostgreSQL.

        The JSON and checksum are first written as private temporary files in the same
        directory, then linked to never-before-used names.  ``event_id`` is random and
        ``O_EXCL``/``link`` semantics prevent an existing entry from being replaced.
        """
        directory = self._directory()
        payload = self._payload(workspace_id, member_ids, rate_fragments,
                                requested_at, request_id)
        encoded = (json.dumps(payload, sort_keys=True, separators=(',', ':')) + '\n').encode()
        digest = hashlib.sha256(encoded).hexdigest()
        name = f'{payload["event_id"]}.json'
        target = directory / name
        checksum_target = directory / f'{name}.sha256'
        temporary: list[Path] = []
        try:
            for suffix, content in (
                    ('.json.tmp', encoded),
                    ('.sha256.tmp', f'{digest}  {name}\n'.encode())):
                descriptor, raw_path = tempfile.mkstemp(prefix='.deletion-', suffix=suffix,
                                                        dir=directory)
                path = Path(raw_path)
                temporary.append(path)
                try:
                    os.fchmod(descriptor, 0o600)
                    with os.fdopen(descriptor, 'wb') as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                except Exception:
                    # ``fdopen`` owns and closes the descriptor once constructed.
                    # A failure before construction is not expected after mkstemp, and
                    # retrying close here could mask the original error with EBADF.
                    raise
            os.link(temporary[0], target)
            os.link(temporary[1], checksum_target)
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            # A lone JSON file is still an intent that an operator can repair using the
            # bytes already fsynced; replay refuses it until its sidecar is present.
            raise DeletionRegisterError('The deletion request could not be durably recorded.') from error
        finally:
            for path in temporary:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        return payload

    @staticmethod
    def _validate(payload: object, name: str) -> dict:
        if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
            raise DeletionRegisterError(f'{name} has an unsupported deletion-register schema.')
        required_strings = ('event_id', 'workspace_id', 'requested_at', 'request_id')
        if any(not isinstance(payload.get(field), str) or not payload[field]
               for field in required_strings):
            raise DeletionRegisterError(f'{name} is missing a required deletion identifier.')
        if name != f'{payload["event_id"]}.json':
            raise DeletionRegisterError(f'{name} does not match its event identifier.')
        for field in ('member_ids', 'rate_fragments'):
            values = payload.get(field)
            if (not isinstance(values, list)
                    or any(not isinstance(value, str) or not value for value in values)):
                raise DeletionRegisterError(f'{name} has an invalid {field} list.')
        if any(not HEX_DIGEST.fullmatch(value) for value in payload['rate_fragments']):
            raise DeletionRegisterError(f'{name} has a malformed rate-limit fragment.')
        return payload

    def entries(self, *, prepare: bool = True) -> list[dict]:
        """Read and verify every entry; one bad or partial entry stops all replay."""
        # The application may create its pre-provisioned writable directory on startup.
        # Verification/sync/replay tools pass prepare=False so their read-only systemd
        # sandboxes never attempt mkdir/chmod and a missing register fails closed.
        directory = self._directory(prepare=prepare)
        entries = []
        paths = sorted(directory.iterdir())
        entry_paths = []
        sidecar_names = set()
        for path in paths:
            if path.name.startswith('.'):
                continue
            if path.is_symlink() or not path.is_file():
                raise DeletionRegisterError(
                    f'Unexpected file in deletion register: {path.name}')
            if ENTRY_NAME.fullmatch(path.name):
                entry_paths.append(path)
            elif path.name.endswith('.json.sha256'):
                sidecar_names.add(path.name)
            else:
                raise DeletionRegisterError(
                    f'Unexpected file in deletion register: {path.name}')
        expected_sidecars = {f'{path.name}.sha256' for path in entry_paths}
        orphaned = sorted(sidecar_names - expected_sidecars)
        if orphaned:
            raise DeletionRegisterError(
                f'Deletion-register checksum has no entry: {orphaned[0]}')
        for path in entry_paths:
            sidecar = path.with_name(f'{path.name}.sha256')
            try:
                encoded = path.read_bytes()
                checksum_line = sidecar.read_text(encoding='ascii').strip()
            except (OSError, UnicodeError) as error:
                raise DeletionRegisterError(
                    f'Deletion-register entry {path.name} is incomplete or unreadable.') from error
            expected = f'{hashlib.sha256(encoded).hexdigest()}  {path.name}'
            if checksum_line != expected:
                raise DeletionRegisterError(
                    f'Deletion-register entry {path.name} failed SHA-256 verification.')
            try:
                payload = json.loads(encoded)
            except (json.JSONDecodeError, UnicodeError) as error:
                raise DeletionRegisterError(
                    f'Deletion-register entry {path.name} is not valid JSON.') from error
            entries.append(self._validate(payload, path.name))
        return entries


def delete_workspace_rows(db: OrmSession, entry: dict) -> bool:
    """Apply one verified intent in the caller's transaction; safe to repeat."""
    workspace_id = entry['workspace_id']
    exists = db.get(Workspace, workspace_id) is not None
    member_ids = set(entry['member_ids'])
    member_ids.update(row.id for row in db.query(User.id).filter_by(
        workspace_id=workspace_id).all())
    db.query(Record).filter_by(workspace_id=workspace_id).delete(synchronize_session=False)
    db.query(Audit).filter_by(workspace_id=workspace_id).delete(synchronize_session=False)
    db.query(Invitation).filter_by(workspace_id=workspace_id).delete(synchronize_session=False)
    if member_ids:
        db.query(Session).filter(Session.user_id.in_(member_ids)).delete(synchronize_session=False)
        db.query(RecoveryToken).filter(
            RecoveryToken.user_id.in_(member_ids)).delete(synchronize_session=False)
    fragments = set(entry['rate_fragments']) | {workspace_id, *member_ids}
    for fragment in fragments:
        # Register validation makes rate fragments hexadecimal; ids are generated UUIDs.
        # Escaping still keeps this safe if an adopted installation used '_' in an id.
        escaped = fragment.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        db.query(RateBucket).filter(
            RateBucket.key.like(f'%{escaped}%', escape='\\')).delete(synchronize_session=False)
    db.query(User).filter_by(workspace_id=workspace_id).delete(synchronize_session=False)
    workspace = db.get(Workspace, workspace_id)
    if workspace is not None:
        db.delete(workspace)
    return exists


def replay(db: OrmSession, entries: list[dict]) -> ReplayResult:
    deleted = sum(delete_workspace_rows(db, entry) for entry in entries)
    return ReplayResult(entries=len(entries), workspaces_deleted=deleted)
