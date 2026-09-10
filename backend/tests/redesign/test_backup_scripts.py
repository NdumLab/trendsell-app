"""Backup wrappers publish only verified dumps and preserve restore connection options."""
import os
import stat
import subprocess
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
BACKUP = REPOSITORY / 'scripts/backup_postgres.sh'
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
