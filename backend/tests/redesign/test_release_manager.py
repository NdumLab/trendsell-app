"""Exact artifact staging and reversible application switch (I07/D05)."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile

REPOSITORY = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('release_manager',
    REPOSITORY / 'scripts/release_manager.py')
manager = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = manager
SPEC.loader.exec_module(manager)

COMMIT = 'a' * 40


def artifact(tmp_path, commit=COMMIT, unsafe=None):
    archive = tmp_path / 'candidate.tar.gz'
    root = f'trendsell-{commit[:12]}'
    files = {
        'RELEASE.json': json.dumps({'schema': 'trendsell-release/1', 'commit': commit}),
        'backend/app/__init__.py': '', 'backend/migrations/env.py': '',
        'frontend/dist/index.html': '<html/>', 'deploy/unit': '', 'scripts/tool': '',
    }
    with tarfile.open(archive, 'w:gz') as bundle:
        for name, content in files.items():
            data = content.encode(); info = tarfile.TarInfo(f'{root}/{name}'); info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
        if unsafe:
            data = b'x'; info = tarfile.TarInfo(unsafe); info.size = 1
            bundle.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    Path(f'{archive}.sha256').write_text(f'{digest}  {archive.name}\n')
    return archive


def test_verified_artifact_stages_and_switches_back(tmp_path):
    archive = artifact(tmp_path)
    staged, digest = manager.stage(archive, COMMIT, tmp_path / 'releases')
    assert staged.name == COMMIT and len(digest) == 64
    assert manager.stage(archive, COMMIT, tmp_path / 'releases') == (staged, digest)
    prior = tmp_path / 'releases' / ('b' * 40); prior.mkdir()
    (prior / 'RELEASE.json').write_text('{}')
    current, previous = tmp_path / 'current', tmp_path / 'previous'
    current.symlink_to(prior)
    assert manager.activate(staged, current, previous) == prior
    assert current.resolve() == staged and previous.resolve() == prior
    assert manager.rollback(current, previous) == prior
    assert current.resolve() == prior and previous.resolve() == staged


def test_repeated_activation_preserves_the_rollback_target(tmp_path):
    staged, _ = manager.stage(artifact(tmp_path), COMMIT, tmp_path / 'releases')
    prior = tmp_path / 'releases' / ('b' * 40); prior.mkdir()
    (prior / 'RELEASE.json').write_text('{}')
    current, previous = tmp_path / 'current', tmp_path / 'previous'
    current.symlink_to(prior)
    manager.activate(staged, current, previous)
    manager.activate(staged, current, previous)
    assert current.resolve() == staged
    assert previous.resolve() == prior


def test_manifest_commit_must_match_approval(tmp_path):
    archive = artifact(tmp_path, commit='b' * 40)
    try: manager.stage(archive, COMMIT, tmp_path / 'releases')
    except ValueError as error: assert 'manifest commit' in str(error)
    else: raise AssertionError('mismatched artifact was staged')


def test_existing_release_must_match_exact_artifact(tmp_path):
    archive = artifact(tmp_path)
    staged, _ = manager.stage(archive, COMMIT, tmp_path / 'releases')
    (staged / manager.ARTIFACT_DIGEST).write_text('0' * 64 + '\n')
    try: manager.stage(archive, COMMIT, tmp_path / 'releases')
    except ValueError as error: assert 'different artifact' in str(error)
    else: raise AssertionError('mutated staged release was accepted')


def test_existing_release_content_cannot_drift_from_exact_artifact(tmp_path):
    archive = artifact(tmp_path)
    staged, _ = manager.stage(archive, COMMIT, tmp_path / 'releases')
    (staged / 'frontend/dist/index.html').write_text('<html>changed</html>')
    try: manager.stage(archive, COMMIT, tmp_path / 'releases')
    except ValueError as error: assert 'content differs' in str(error)
    else: raise AssertionError('locally changed staged release was accepted')


def test_archive_paths_cannot_escape_release_directory(tmp_path):
    archive = artifact(tmp_path, unsafe='../outside')
    try: manager.stage(archive, COMMIT, tmp_path / 'releases')
    except ValueError as error: assert 'unsafe archive path' in str(error)
    else: raise AssertionError('unsafe artifact was staged')


def test_archive_cannot_supply_the_internal_digest_marker(tmp_path):
    archive = artifact(tmp_path, unsafe=f'trendsell-{COMMIT[:12]}/{manager.ARTIFACT_DIGEST}')
    try: manager.stage(archive, COMMIT, tmp_path / 'releases')
    except ValueError as error: assert 'reserves' in str(error)
    else: raise AssertionError('artifact supplied the internal digest marker')
