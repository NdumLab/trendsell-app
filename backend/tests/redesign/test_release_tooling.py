"""Release tooling must be deterministic, clean-tree-only and safely redacting."""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
BUILD_RELEASE = REPOSITORY / 'scripts/build_release_artifact.sh'
SCAN_SECRETS = REPOSITORY / 'scripts/scan_secrets.sh'


def run(command, *, cwd, environment=None):
    return subprocess.run(command, cwd=cwd, env=environment, text=True,
                          capture_output=True)


def git(repository, *arguments):
    result = run(['git', *arguments], cwd=repository)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + body)
    path.chmod(0o755)


def write(path, body='fixture\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def initialize_repository(path):
    path.mkdir()
    git(path, 'init', '-q')
    git(path, 'config', 'user.name', 'Release test')
    git(path, 'config', 'user.email', 'release-test@example.invalid')


def commit_all(path, message):
    git(path, 'add', '--all')
    git(path, 'commit', '-q', '-m', message)


def release_fixture(tmp_path):
    repository = tmp_path / 'repository'
    initialize_repository(repository)

    files = {
        '.gitignore': 'frontend/dist/\nrelease/\n',
        'backend/app/main.py': 'APP = True\n',
        'backend/migrations/versions/0001.py': 'revision = "0001"\n',
        'backend/alembic.ini': '[alembic]\n',
        'backend/requirements.lock': 'example==1.0\n',
        'backend/server.py': 'from app.main import APP\n',
        'contracts/case.json': '{}\n',
        'deploy/service.template': '[Service]\n',
        'docs/PRIVACY_AND_PERMISSIONS.md': '# Privacy\n',
        'docs/DEPENDENCY_LICENSES.md': '# Dependency licenses\n',
        'docs/PRODUCTION_READINESS.md': '# Readiness\n',
        'docs/RUNBOOK.md': '# Runbook\n',
        'frontend/package.json': '{"scripts":{"build":"fixture"}}\n',
        'frontend/package-lock.json': '{}\n',
        'scripts/backup_postgres.sh': '#!/usr/bin/env bash\n',
        'scripts/check_backup.sh': '#!/usr/bin/env bash\n',
        'scripts/check_dependency_licenses.py': '#!/usr/bin/env python3\n',
        'scripts/check_postgres_privileges.py': '#!/usr/bin/env python3\n',
        'scripts/check_recovery_state.sh': '#!/usr/bin/env bash\n',
        'scripts/configure_postgres_roles.sh': '#!/usr/bin/env bash\n',
        'scripts/configure_postgres_roles.sql': '-- fixture\n',
        'scripts/deploy_release.sh': '#!/usr/bin/env bash\n',
        'scripts/monitor_trendsell.py': '#!/usr/bin/env python3\n',
        'scripts/release_manager.py': '#!/usr/bin/env python3\n',
        'scripts/replay_deletions.py': '#!/usr/bin/env python3\n',
        'scripts/rollback_postgres_roles.sh': '#!/usr/bin/env bash\n',
        'scripts/rollback_postgres_roles.sql': '-- fixture\n',
        'scripts/restore_postgres.sh': '#!/usr/bin/env bash\n',
        'scripts/scan_secrets.sh': '#!/usr/bin/env bash\n',
        'scripts/sync_deletion_register.sh': '#!/usr/bin/env bash\n',
        'scripts/verify_deletion_register.py': '#!/usr/bin/env python3\n',
        'scripts/verify_restore.py': 'print("verify")\n',
    }
    for relative, body in files.items():
        write(repository / relative, body)
    (repository / 'scripts/check_backup.sh').chmod(0o755)
    shutil.copy2(BUILD_RELEASE, repository / 'scripts/build_release_artifact.sh')
    commit_all(repository, 'fixture release')

    tools = tmp_path / 'bin'
    executable(tools / 'npm', '''
[[ "$1" == "--prefix" && "$2" == "frontend" && "$3" == "run" && "$4" == "build" ]]
mkdir -p frontend/dist/assets
printf '<!doctype html>fixture\n' > frontend/dist/index.html
printf 'fixture javascript\n' > frontend/dist/assets/app.js
''')
    environment = os.environ.copy()
    environment['PATH'] = f'{tools}:{environment["PATH"]}'
    return repository, environment


def test_release_archive_is_clean_tree_only_versioned_and_reproducible(tmp_path):
    repository, environment = release_fixture(tmp_path)
    first_dir = tmp_path / 'first'
    second_dir = tmp_path / 'second'

    first = run(['bash', '-c', 'umask 0002; exec "$0" "$1"',
                 repository / 'scripts/build_release_artifact.sh', first_dir],
                cwd=repository, environment=environment)
    second = run(['bash', '-c', 'umask 0077; exec "$0" "$1"',
                  repository / 'scripts/build_release_artifact.sh', second_dir],
                 cwd=repository, environment=environment)
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr

    commit = git(repository, 'rev-parse', 'HEAD')
    archive_name = f'trendsell-{commit[:12]}.tar.gz'
    first_archive = first_dir / archive_name
    second_archive = second_dir / archive_name
    assert first_archive.read_bytes() == second_archive.read_bytes()
    expected_hash = hashlib.sha256(first_archive.read_bytes()).hexdigest()
    assert (first_dir / f'{archive_name}.sha256').read_text() == (
        f'{expected_hash}  {archive_name}\n')

    with tarfile.open(first_archive, 'r:gz') as archive:
        names = archive.getnames()
        prefix = f'trendsell-{commit[:12]}'
        manifest = json.load(archive.extractfile(f'{prefix}/RELEASE.json'))
        assert archive.getmember(f'{prefix}/backend/app/main.py').mode == 0o644
        assert archive.getmember(f'{prefix}/backend/app').mode == 0o755
        assert archive.getmember(f'{prefix}/scripts/build_release_artifact.sh').mode == 0o755
        assert archive.getmember(f'{prefix}/scripts/check_backup.sh').mode == 0o755
    assert manifest['commit'] == commit
    assert manifest['schema'] == 'trendsell-release/1'
    assert f'{prefix}/frontend/dist/index.html' in names
    assert f'{prefix}/backend/app/main.py' in names
    assert not any('/frontend/src/' in name for name in names)

    with (repository / 'backend/app/main.py').open('a') as source:
        source.write('DIRTY = True\n')
    refused = run([repository / 'scripts/build_release_artifact.sh', tmp_path / 'dirty'],
                  cwd=repository, environment=environment)
    assert refused.returncode == 2
    assert 'dirty checkout' in refused.stderr
    assert not (tmp_path / 'dirty').exists()


def secret_scan_fixture(tmp_path):
    repository = tmp_path / 'secret-repository'
    initialize_repository(repository)
    (repository / 'scripts').mkdir()
    shutil.copy2(SCAN_SECRETS, repository / 'scripts/scan_secrets.sh')
    write(repository / 'README.md', '# Safe fixture\n')
    commit_all(repository, 'safe start')
    return repository


def test_secret_scan_finds_tracked_and_historical_values_without_printing_them(tmp_path):
    repository = secret_scan_fixture(tmp_path)
    scanner = repository / 'scripts/scan_secrets.sh'
    clean = run([scanner, '--tracked', '--history'], cwd=repository)
    assert clean.returncode == 0, clean.stderr

    token = 's' + 'k-' + ('A' * 24)
    write(repository / 'leaked.txt', f'credential={token}\n')
    git(repository, 'add', 'leaked.txt')
    tracked = run([scanner, '--tracked'], cwd=repository)
    assert tracked.returncode == 1
    assert 'leaked.txt' in tracked.stderr
    assert token not in tracked.stdout + tracked.stderr

    commit_all(repository, 'add historical fixture')
    (repository / 'leaked.txt').unlink()
    commit_all(repository, 'remove historical fixture')
    current = run([scanner, '--tracked'], cwd=repository)
    historical = run([scanner, '--history'], cwd=repository)
    assert current.returncode == 0, current.stderr
    assert historical.returncode == 1
    assert 'leaked.txt' in historical.stderr
    assert token not in historical.stdout + historical.stderr


def test_secret_scan_checks_unpacked_release_content_and_redacts_value(tmp_path):
    repository = secret_scan_fixture(tmp_path)
    release = tmp_path / 'unpacked-release'
    token = 'g' + 'hp_' + ('B' * 24)
    write(release / 'configuration.txt', f'credential={token}\n')
    result = run([repository / 'scripts/scan_secrets.sh', '--directory', release],
                 cwd=repository)
    assert result.returncode == 1
    assert 'configuration.txt' in result.stderr
    assert token not in result.stdout + result.stderr
