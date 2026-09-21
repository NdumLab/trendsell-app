"""Backup wrappers publish only verified dumps and preserve restore connection options."""
import base64
import hashlib
import os
import stat
import subprocess
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
BACKUP = REPOSITORY / 'scripts/backup_postgres.sh'
CHECK = REPOSITORY / 'scripts/check_backup.sh'
RESTORE = REPOSITORY / 'scripts/restore_postgres.sh'


def executable(path, body):
    path.write_text('#!/usr/bin/env bash\nset -eu\n' + body)
    path.chmod(0o755)


def backup_tools(tmp_path):
    tools = tmp_path / 'bin'
    tools.mkdir()
    executable(tools / 'pg_dump', r'''
target=''
for argument in "$@"; do
  case "$argument" in --file=*) target="${argument#--file=}" ;; esac
done
[ -n "$target" ]
printf 'partial dump' > "$target"
[ "${FAIL_DUMP:-0}" != 1 ]
''')
    executable(tools / 'pg_restore', r'''
[ "$1" = '--list' ]
[ -s "$2" ]
''')
    return tools


def backup_environment(tmp_path, tools):
    environment = os.environ.copy()
    environment.update({
        'PATH': f'{tools}:{environment["PATH"]}',
        'DATABASE_URL': 'postgresql+psycopg://user:password@db.example/trendsell',
        'TRENDSELL_BACKUP_DIR': str(tmp_path / 'backups'),
        'TRENDSELL_BACKUP_KEEP': '14',
    })
    return environment


def test_backup_atomically_publishes_a_verified_private_dump(tmp_path):
    tools = backup_tools(tmp_path)
    result = subprocess.run([BACKUP], env=backup_environment(tmp_path, tools),
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    backups = list((tmp_path / 'backups').glob('trendsell-*.dump'))
    assert len(backups) == 1
    assert backups[0].read_text() == 'partial dump'
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    checksum = backups[0].with_suffix('.dump.sha256')
    assert checksum.exists()
    assert checksum.read_text().split()[1] == backups[0].name
    assert str(tmp_path) not in checksum.read_text()
    assert stat.S_IMODE(checksum.stat().st_mode) == 0o600
    assert list((tmp_path / 'backups').glob('*.partial')) == []


def test_failed_dump_leaves_no_partial_file_presented_as_a_backup(tmp_path):
    tools = backup_tools(tmp_path)
    environment = backup_environment(tmp_path, tools)
    environment['FAIL_DUMP'] = '1'
    result = subprocess.run([BACKUP], env=environment, text=True, capture_output=True)
    assert result.returncode != 0
    assert list((tmp_path / 'backups').iterdir()) == []


def test_backup_retention_must_be_a_bounded_whole_number(tmp_path):
    tools = backup_tools(tmp_path)
    for invalid in ('fourteen', '0', '3651', '-1'):
        environment = backup_environment(tmp_path, tools)
        environment['TRENDSELL_BACKUP_KEEP'] = invalid
        result = subprocess.run([BACKUP], env=environment, text=True, capture_output=True)
        assert result.returncode == 2, invalid


def test_configured_offsite_copy_uploads_dump_and_checksum(tmp_path):
    tools = backup_tools(tmp_path)
    calls = tmp_path / 'aws.log'
    executable(tools / 'aws', r'''
printf '%s\n' "$*" >> "$AWS_LOG"
''')
    environment = backup_environment(tmp_path, tools)
    environment.update({
        'AWS_LOG': str(calls),
        'TRENDSELL_BACKUP_S3_URI': 's3://private-backups/trendsell',
        'TRENDSELL_BACKUP_S3_SSE': 'AES256',
    })
    result = subprocess.run([BACKUP], env=environment, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    uploads = calls.read_text().splitlines()
    assert len(uploads) == 2
    assert all('s3://private-backups/trendsell/' in call for call in uploads)
    assert any('.dump --only-show-errors --sse AES256 --checksum-algorithm SHA256' in call
               for call in uploads)
    assert any('.dump.sha256 --only-show-errors --sse AES256 --checksum-algorithm SHA256'
               in call for call in uploads)


def test_offsite_destination_requires_a_bucket_prefix(tmp_path):
    tools = backup_tools(tmp_path)
    environment = backup_environment(tmp_path, tools)
    environment['TRENDSELL_BACKUP_S3_URI'] = 's3://private-backups'
    result = subprocess.run([BACKUP], env=environment, text=True, capture_output=True)
    assert result.returncode == 2
    assert 'bucket and private prefix' in result.stderr


def test_an_offsite_failure_fails_the_backup_job_but_keeps_local_recovery(tmp_path):
    tools = backup_tools(tmp_path)
    executable(tools / 'aws', 'exit 9\n')
    environment = backup_environment(tmp_path, tools)
    environment['TRENDSELL_BACKUP_S3_URI'] = 's3://private-backups/trendsell'
    result = subprocess.run([BACKUP], env=environment, text=True, capture_output=True)
    assert result.returncode == 9
    assert len(list((tmp_path / 'backups').glob('trendsell-*.dump'))) == 1


def test_offsite_failure_does_not_prevent_local_retention(tmp_path):
    tools = backup_tools(tmp_path)
    executable(tools / 'aws', 'exit 9\n')
    environment = backup_environment(tmp_path, tools)
    environment['TRENDSELL_BACKUP_S3_URI'] = 's3://private-backups/trendsell'
    backup_dir = Path(environment['TRENDSELL_BACKUP_DIR'])
    backup_dir.mkdir()
    old = backup_dir / 'trendsell-20000101T000000Z-old.dump'
    old.write_text('expired dump')
    old.with_suffix('.dump.sha256').write_text('expired checksum')
    old_time = 946684800
    os.utime(old, (old_time, old_time))
    os.utime(old.with_suffix('.dump.sha256'), (old_time, old_time))

    result = subprocess.run([BACKUP], env=environment, text=True, capture_output=True)
    assert result.returncode == 9
    assert not old.exists() and not old.with_suffix('.dump.sha256').exists()
    assert len(list(backup_dir.glob('trendsell-*.dump'))) == 1


def check_environment(tmp_path, *, remote_dump_checksum=None):
    tools = tmp_path / 'check-bin'
    tools.mkdir()
    executable(tools / 'pg_restore', r'''
[[ "$1" == "--list" && -s "$2" ]]
''')
    backup_dir = tmp_path / 'check-backups'
    backup_dir.mkdir()
    dump = backup_dir / 'trendsell-20260914T120000Z-check.dump'
    dump.write_bytes(b'checked dump')
    checksum = hashlib.sha256(dump.read_bytes()).hexdigest()
    sidecar = dump.with_suffix('.dump.sha256')
    sidecar.write_text(f'{checksum}  {dump.name}\n')
    dump_checksum = base64.b64encode(hashlib.sha256(dump.read_bytes()).digest()).decode()
    sidecar_checksum = base64.b64encode(
        hashlib.sha256(sidecar.read_bytes()).digest()).decode()
    executable(tools / 'aws', r'''
printf '%s\n' "$*" >> "$AWS_LOG"
case "$*" in
  *".dump.sha256"*)
    printf '{"ContentLength":%s,"ServerSideEncryption":"AES256","ChecksumSHA256":"%s"}\n' \
      "$SIDECAR_SIZE" "$REMOTE_SIDECAR_CHECKSUM"
    ;;
  *".dump"*)
    printf '{"ContentLength":%s,"ServerSideEncryption":"AES256","ChecksumSHA256":"%s"}\n' \
      "$DUMP_SIZE" "$REMOTE_DUMP_CHECKSUM"
    ;;
  *) exit 3 ;;
esac
''')
    environment = os.environ.copy()
    environment.update({
        'PATH': f'{tools}:{environment["PATH"]}',
        'TRENDSELL_BACKUP_DIR': str(backup_dir),
        'TRENDSELL_BACKUP_MAX_AGE_HOURS': '30',
        'TRENDSELL_BACKUP_S3_URI': 's3://private-backups/trendsell',
        'TRENDSELL_BACKUP_S3_SSE': 'AES256',
        'AWS_LOG': str(tmp_path / 'check-aws.log'),
        'DUMP_SIZE': str(dump.stat().st_size),
        'SIDECAR_SIZE': str(sidecar.stat().st_size),
        'REMOTE_DUMP_CHECKSUM': remote_dump_checksum or dump_checksum,
        'REMOTE_SIDECAR_CHECKSUM': sidecar_checksum,
    })
    return environment


def test_backup_check_proves_local_and_s3_checksums_sizes_and_encryption(tmp_path):
    environment = check_environment(tmp_path)
    result = subprocess.run([CHECK], env=environment, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'PASS newest local and encrypted offsite TrendSell backup agree' in result.stdout
    calls = Path(environment['AWS_LOG']).read_text().splitlines()
    assert len(calls) == 2
    assert all('--checksum-mode ENABLED' in call for call in calls)


def test_backup_check_rejects_an_equal_size_remote_object_with_wrong_checksum(tmp_path):
    environment = check_environment(tmp_path, remote_dump_checksum='not-the-local-checksum')
    result = subprocess.run([CHECK], env=environment, text=True, capture_output=True)
    assert result.returncode == 1
    assert 'SHA-256 does not match the local backup' in result.stderr


def test_restore_preserves_connection_query_options(tmp_path):
    tools = tmp_path / 'bin'
    tools.mkdir()
    log = tmp_path / 'commands.log'
    executable(tools / 'psql', r'''
printf 'psql:%s\n' "$*" >> "$COMMAND_LOG"
''')
    executable(tools / 'pg_restore', r'''
printf 'restore:%s\n' "$*" >> "$COMMAND_LOG"
''')
    dump = tmp_path / 'source.dump'
    dump.write_text('dump')
    checksum = subprocess.run(['sha256sum', dump.name], cwd=tmp_path, text=True,
                              capture_output=True, check=True).stdout
    dump.with_suffix('.dump.sha256').write_text(checksum)
    environment = os.environ.copy()
    environment.update({
        'PATH': f'{tools}:{environment["PATH"]}',
        'COMMAND_LOG': str(log),
        'TRENDSELL_ADMIN_URL':
            'postgresql+psycopg://user:password@db.example/postgres?sslmode=require',
    })
    result = subprocess.run([RESTORE, dump, 'restored_copy'], env=environment,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert ('restore:--dbname=postgresql://user:password@db.example/'
            'restored_copy?sslmode=require') in commands


def test_restore_refuses_a_tampered_dump_before_creating_a_database(tmp_path):
    tools = tmp_path / 'bin'
    tools.mkdir()
    log = tmp_path / 'commands.log'
    executable(tools / 'psql', 'printf "called\\n" >> "$COMMAND_LOG"\n')
    executable(tools / 'pg_restore', 'printf "called\\n" >> "$COMMAND_LOG"\n')
    dump = tmp_path / 'source.dump'
    dump.write_text('original')
    checksum = subprocess.run(['sha256sum', dump.name], cwd=tmp_path, text=True,
                              capture_output=True, check=True).stdout
    dump.with_suffix('.dump.sha256').write_text(checksum)
    dump.write_text('tampered')
    environment = os.environ.copy()
    environment.update({
        'PATH': f'{tools}:{environment["PATH"]}', 'COMMAND_LOG': str(log),
        'TRENDSELL_ADMIN_URL': 'postgresql://user:password@db.example/postgres',
    })
    result = subprocess.run([RESTORE, dump, 'restored_copy'], env=environment,
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert 'SHA-256 verification failed' in result.stderr
    assert not log.exists()
