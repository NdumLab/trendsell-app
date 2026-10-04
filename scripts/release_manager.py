#!/usr/bin/env python3
"""Verify, stage and atomically switch exact TrendSell release artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile

COMMIT = re.compile(r'^[0-9a-f]{40}$')
ARTIFACT_DIGEST = '.artifact-sha256'


def checksum(archive):
    sidecar = Path(f'{archive}.sha256')
    if not sidecar.is_file():
        raise ValueError(f'checksum sidecar is missing: {sidecar}')
    fields = sidecar.read_text(encoding='ascii').strip().split()
    if len(fields) != 2 or fields[1].lstrip('*') != archive.name:
        raise ValueError('checksum sidecar must name the supplied archive exactly')
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if fields[0] != actual:
        raise ValueError('release archive failed SHA-256 verification')
    return actual


def file_digest(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def archive_files(archive):
    """Validate archive members and return their one-root-relative content/modes."""
    with tarfile.open(archive, 'r:gz') as bundle:
        listed = bundle.getmembers()
        roots = set()
        files = {}
        for member in listed:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts:
                raise ValueError(f'unsafe archive path: {member.name}')
            roots.add(path.parts[0])
            if not (member.isfile() or member.isdir()):
                raise ValueError(f'links and special files are not permitted: {member.name}')
        if len(roots) != 1:
            raise ValueError('release archive must contain one top-level directory')
        root = roots.pop()
        for member in listed:
            if not member.isfile():
                continue
            relative = PurePosixPath(member.name).relative_to(root).as_posix()
            if relative == ARTIFACT_DIGEST:
                raise ValueError(f'release archive reserves {ARTIFACT_DIGEST}')
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError(f'release archive file is unreadable: {member.name}')
            with stream:
                files[relative] = (file_digest(stream), member.mode & 0o777)
        return root, files


def staged_files(destination):
    """Hash a staged tree so an idempotent retry cannot bless local drift."""
    files = {}
    for path in destination.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f'existing release contains a link or special file: {path.name}')
        if not path.is_file():
            continue
        relative = path.relative_to(destination).as_posix()
        if relative == ARTIFACT_DIGEST:
            continue
        with path.open('rb') as stream:
            files[relative] = (file_digest(stream), path.stat().st_mode & 0o777)
    return files


def stage(archive, expected_commit, release_root):
    archive = Path(archive).resolve()
    release_root = Path(release_root).resolve()
    if not COMMIT.fullmatch(expected_commit):
        raise ValueError('expected commit must be a full lowercase Git SHA')
    digest = checksum(archive)
    archive_root, expected_files = archive_files(archive)
    release_root.mkdir(mode=0o755, parents=True, exist_ok=True)
    destination = release_root / expected_commit
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError('existing release path is not a real directory')
        manifest = json.loads((destination / 'RELEASE.json').read_text())
        if manifest.get('commit') != expected_commit:
            raise ValueError('existing release directory has a different manifest')
        staged_digest = (destination / ARTIFACT_DIGEST).read_text(encoding='ascii').strip()
        if staged_digest != digest:
            raise ValueError('existing release directory came from a different artifact')
        if staged_files(destination) != expected_files:
            raise ValueError('existing release directory content differs from the artifact')
        return destination, digest
    temporary = Path(tempfile.mkdtemp(prefix='.stage-', dir=release_root))
    try:
        with tarfile.open(archive, 'r:gz') as bundle:
            bundle.extractall(temporary, filter='data')
        unpacked = temporary / archive_root
        manifest = json.loads((unpacked / 'RELEASE.json').read_text())
        if manifest.get('schema') != 'trendsell-release/1':
            raise ValueError('release manifest schema is unsupported')
        if manifest.get('commit') != expected_commit:
            raise ValueError('release manifest commit does not match the approved commit')
        for required in ('backend/app', 'backend/migrations', 'frontend/dist', 'deploy', 'scripts'):
            if not (unpacked / required).is_dir():
                raise ValueError(f'release artifact is missing {required}')
        (unpacked / ARTIFACT_DIGEST).write_text(f'{digest}\n', encoding='ascii')
        os.replace(unpacked, destination)
        directory = os.open(release_root, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        return destination, digest
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def link_target(link):
    return Path(os.path.realpath(link)) if link.is_symlink() or link.exists() else None


def replace_link(link, target):
    link.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = link.with_name(f'.{link.name}.{os.getpid()}.tmp')
    try:
        temporary.symlink_to(target)
        os.replace(temporary, link)
        directory = os.open(link.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        try: temporary.unlink()
        except FileNotFoundError: pass


def activate(release, current, previous):
    release = Path(release).resolve(strict=True)
    if not (release / 'RELEASE.json').is_file():
        raise ValueError('release directory has no manifest')
    current, previous = Path(current), Path(previous)
    old = link_target(current)
    # Re-running activation for an already-current artifact must not overwrite the last
    # known-good rollback target with the candidate itself.
    if old == release:
        return old
    if old:
        replace_link(previous, old)
    replace_link(current, release)
    return old


def rollback(current, previous):
    current, previous = Path(current), Path(previous)
    old, target = link_target(current), link_target(previous)
    if target is None:
        raise ValueError('no previous release target is recorded')
    replace_link(current, target)
    if old:
        replace_link(previous, old)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    staged = sub.add_parser('stage')
    staged.add_argument('--archive', required=True)
    staged.add_argument('--expected-commit', required=True)
    staged.add_argument('--release-root', required=True)
    for name in ('activate', 'rollback'):
        command = sub.add_parser(name)
        command.add_argument('--current', required=True)
        command.add_argument('--previous', required=True)
        if name == 'activate': command.add_argument('--release', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'stage':
            path, digest = stage(args.archive, args.expected_commit, args.release_root)
            print(json.dumps({'release': str(path), 'sha256': digest}))
        elif args.action == 'activate':
            old = activate(args.release, args.current, args.previous)
            print(json.dumps({'current': str(Path(args.release).resolve()),
                              'previous': str(old) if old else None}))
        else:
            target = rollback(args.current, args.previous)
            print(json.dumps({'current': str(target)}))
        return 0
    except (OSError, ValueError, tarfile.TarError, json.JSONDecodeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
