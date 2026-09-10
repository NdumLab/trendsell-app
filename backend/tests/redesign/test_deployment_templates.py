"""Production templates must preserve the privacy properties claimed by the runbook."""
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
NGINX = REPOSITORY / 'deploy/nginx-trendsell.conf.template'
BACKUP_SERVICE = REPOSITORY / 'deploy/trendsell-backup.service.template'
BACKUP_TIMER = REPOSITORY / 'deploy/trendsell-backup.timer.template'


def test_uvicorn_does_not_emit_a_second_raw_access_log():
    service = (REPOSITORY / 'deploy/trendsell.service.template').read_text()
    command = next(line for line in service.splitlines() if line.startswith('ExecStart='))
    assert '--no-access-log' in command


def test_nginx_access_log_omits_addresses_request_targets_and_client_headers():
    nginx = NGINX.read_text()
    format_lines = [line.strip() for line in nginx.splitlines()
                    if line.lstrip().startswith(('log_format trendsell_safe',
                                                 "'request_time="))]
    safe_format = ' '.join(format_lines)
    for unsafe in ('$remote_addr', '$request ', '$request_uri', '$uri',
                   '$args', '$http_user_agent', '$http_referer'):
        assert unsafe not in safe_format
    safe_access = 'access_log /var/log/nginx/${TRENDSELL_DOMAIN}.access.log trendsell_safe;'
    assert nginx.count(safe_access) == 2, 'both the HTTP redirect and HTTPS server need the safe format'


def test_nginx_csp_has_no_third_party_browser_origin():
    nginx = NGINX.read_text()
    assert 'fonts.googleapis.com' not in nginx
    assert 'fonts.gstatic.com' not in nginx
    assert "connect-src 'self'" in nginx


def test_nginx_body_limit_matches_the_application_limit():
    from app.limits import MAX_BODY_BYTES
    nginx = NGINX.read_text()
    assert f'client_max_body_size {MAX_BODY_BYTES // 1024}k;' in nginx


def test_backup_schedule_is_a_hardened_explicit_opt_in():
    service = BACKUP_SERVICE.read_text()
    timer = BACKUP_TIMER.read_text()
    assert 'Type=oneshot' in service
    assert 'User=trendsell' in service
    assert 'UMask=0077' in service
    assert 'ProtectSystem=strict' in service
    assert 'ReadWritePaths=/var/backups/trendsell' in service
    assert 'OnCalendar=' in timer and 'Persistent=true' in timer
    assert 'WantedBy=timers.target' in timer
