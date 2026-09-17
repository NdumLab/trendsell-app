#!/usr/bin/env python3
"""Persistent host probes and state-change alert delivery for TrendSell.

Run as a systemd one-shot. Results live outside the application database, so a dead web
worker or database is still observable. No alert destination is built in; ``--test-alert``
sends an explicitly synthetic event only after an operator configures a webhook.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text

SCHEMA = 'trendsell-monitor/1'
BAD = {'warning', 'critical'}


def integer(name, default, low, high):
    value = int(os.getenv(name, default))
    if not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}')
    return value


def number(name, default, low, high):
    value = float(os.getenv(name, default))
    if not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}')
    return value


@dataclass(frozen=True)
class Config:
    state_dir: Path
    ready_url: str
    service_unit: str
    database_url: str
    disk_path: Path
    backup_command: str
    public_host: str
    public_port: int
    smtp_host: str
    smtp_port: int
    webhook_url: str
    webhook_token: str
    heartbeat_url: str
    history_days: int
    reminder_minutes: int
    interval_minutes: int
    disk_warning_pct: float
    disk_critical_pct: float
    db_warning_pct: float
    db_critical_pct: float
    latency_warning_ms: float
    latency_critical_ms: float
    error_warning_pct: float
    error_critical_pct: float
    rate_warning_pct: float
    rate_critical_pct: float
    tls_warning_days: int
    tls_critical_days: int
    restart_warning: int
    restart_critical: int

    @classmethod
    def from_env(cls):
        raw_dir = os.getenv('TRENDSELL_MONITOR_STATE_DIR', '')
        if not raw_dir or not Path(raw_dir).is_absolute():
            raise ValueError('TRENDSELL_MONITOR_STATE_DIR must be an absolute path')
        config = cls(
            Path(raw_dir),
            os.getenv('TRENDSELL_READY_URL', 'http://127.0.0.1:8021/api/ready'),
            os.getenv('TRENDSELL_SERVICE_UNIT', 'trendsell.service'),
            os.getenv('TRENDSELL_MONITOR_DATABASE_URL', ''),
            Path(os.getenv('TRENDSELL_DISK_PATH', '/')),
            os.getenv('TRENDSELL_BACKUP_CHECK_COMMAND',
                      '/opt/trendsell/current/scripts/check_backup.sh'),
            os.getenv('TRENDSELL_PUBLIC_HOST', ''), integer('TRENDSELL_PUBLIC_PORT', 443, 1, 65535),
            os.getenv('TRENDSELL_SMTP_CHECK_HOST', ''),
            integer('TRENDSELL_SMTP_CHECK_PORT', 587, 1, 65535),
            os.getenv('TRENDSELL_ALERT_WEBHOOK_URL', '').strip(),
            os.getenv('TRENDSELL_ALERT_WEBHOOK_TOKEN', ''),
            os.getenv('TRENDSELL_HEARTBEAT_URL', '').strip(),
            integer('TRENDSELL_MONITOR_HISTORY_DAYS', 30, 1, 3650),
            integer('TRENDSELL_ALERT_REMINDER_MINUTES', 240, 5, 10080),
            integer('TRENDSELL_MONITOR_INTERVAL_MINUTES', 5, 1, 60),
            number('TRENDSELL_DISK_WARNING_PCT', 20, 1, 99),
            number('TRENDSELL_DISK_CRITICAL_PCT', 10, 1, 99),
            number('TRENDSELL_DB_WARNING_PCT', 70, 1, 99),
            number('TRENDSELL_DB_CRITICAL_PCT', 85, 1, 100),
            number('TRENDSELL_LATENCY_WARNING_MS', 1000, 1, 600000),
            number('TRENDSELL_LATENCY_CRITICAL_MS', 3000, 1, 600000),
            number('TRENDSELL_ERROR_WARNING_PCT', 2, 0, 100),
            number('TRENDSELL_ERROR_CRITICAL_PCT', 5, 0, 100),
            number('TRENDSELL_RATE_LIMIT_WARNING_PCT', 5, 0, 100),
            number('TRENDSELL_RATE_LIMIT_CRITICAL_PCT', 20, 0, 100),
            integer('TRENDSELL_TLS_WARNING_DAYS', 30, 1, 365),
            integer('TRENDSELL_TLS_CRITICAL_DAYS', 14, 0, 365),
            integer('TRENDSELL_RESTART_WARNING_COUNT', 1, 1, 1000),
            integer('TRENDSELL_RESTART_CRITICAL_COUNT', 3, 1, 1000))
        if not (config.disk_critical_pct < config.disk_warning_pct
                and config.db_warning_pct < config.db_critical_pct
                and config.latency_warning_ms < config.latency_critical_ms
                and config.error_warning_pct < config.error_critical_pct
                and config.rate_warning_pct < config.rate_critical_pct
                and config.tls_critical_days < config.tls_warning_days
                and config.restart_warning < config.restart_critical):
            raise ValueError('warning and critical monitoring thresholds are inconsistent')
        allow_http = os.getenv('TRENDSELL_MONITOR_ALLOW_HTTP') == 'yes'
        for name, url in (('alert', config.webhook_url), ('heartbeat', config.heartbeat_url)):
            if url and urlparse(url).scheme not in ({'http', 'https'} if allow_http else {'https'}):
                raise ValueError(f'{name} URL must use HTTPS')
        return config


def probe(identifier, status, detail, value=None, unit=None):
    return {'id': identifier, 'status': status, 'detail': detail,
            'value': value, 'unit': unit}


def status_high(value, warning, critical):
    return 'critical' if value >= critical else 'warning' if value >= warning else 'ok'


def status_low(value, warning, critical):
    return 'critical' if value <= critical else 'warning' if value <= warning else 'ok'


def ready(config):
    try:
        with urlopen(Request(config.ready_url, headers={'User-Agent': 'TrendSell-monitor/1'}),
                     timeout=10) as response:
            body = json.loads(response.read(65536))
            good = response.status == 200 and body.get('status') == 'ready'
            return probe('readiness', 'ok' if good else 'critical',
                         'Service and schema ready' if good else 'Service did not report ready')
    except Exception as error:
        return probe('readiness', 'critical', f'Probe failed: {type(error).__name__}')


def host_disk(config):
    try:
        usage = shutil.disk_usage(config.disk_path)
        free = usage.free / usage.total * 100 if usage.total else 0
        return probe('disk_free', status_low(free, config.disk_warning_pct,
                                            config.disk_critical_pct),
                     f'{free:.1f}% free', round(free, 2), 'percent')
    except Exception as error:
        return probe('disk_free', 'critical', f'Probe failed: {type(error).__name__}')


def service(config):
    try:
        result = subprocess.run(['systemctl', 'show', config.service_unit,
                                 '--property=ActiveState,NRestarts', '--value'],
                                text=True, capture_output=True, timeout=10, check=True)
        lines = result.stdout.splitlines()
        active, restarts = (lines[0] if lines else 'unknown'), int(lines[1] if len(lines) > 1 else 0)
        # NRestarts is cumulative. Compare it with the last persisted observation so one
        # ordinary release restart does not leave the monitor warning forever.
        previous = restarts
        try:
            state = json.loads((config.state_dir / 'state.json').read_text())
            previous = int(state.get('probes', {}).get('service', {}).get('value', restarts))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        delta = max(0, restarts - previous)
        status = ('critical' if active != 'active' else status_high(
            delta, config.restart_warning, config.restart_critical))
        return probe('service', status,
                     f'active={active}; restart_delta={delta}; restart_total={restarts}',
                     restarts, 'restart total')
    except Exception as error:
        return probe('service', 'critical', f'Probe failed: {type(error).__name__}')


def request_signals(config):
    try:
        result = subprocess.run(['journalctl', '-u', config.service_unit, '--since',
                                 f'{config.interval_minutes} minutes ago', '--output=cat', '--no-pager'],
                                text=True, capture_output=True, timeout=20, check=True)
        events = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
                if event.get('message') == 'request': events.append(event)
            except json.JSONDecodeError:
                pass
        errors = sum(int(event.get('status', 0)) >= 500 for event in events)
        limited = sum(int(event.get('status', 0)) == 429 for event in events)
        error_pct = errors / len(events) * 100 if events else 0
        limited_pct = limited / len(events) * 100 if events else 0
        durations = sorted(float(event.get('duration_ms', 0)) for event in events)
        p95 = durations[max(0, math.ceil(len(durations) * .95) - 1)] if durations else 0
        return [probe('request_errors', status_high(error_pct, config.error_warning_pct,
                                                    config.error_critical_pct),
                      f'{errors}/{len(events)} server errors', round(error_pct, 3), 'percent'),
                probe('request_latency', status_high(p95, config.latency_warning_ms,
                                                     config.latency_critical_ms),
                      f'p95 across {len(events)} requests', round(p95, 1), 'ms'),
                probe('request_rate_limited', status_high(
                          limited_pct, config.rate_warning_pct, config.rate_critical_pct),
                      f'{limited}/{len(events)} rate-limited requests',
                      round(limited_pct, 3), 'percent')]
    except Exception as error:
        return [probe('request_errors', 'critical', f'Journal failed: {type(error).__name__}'),
                probe('request_latency', 'critical', 'Journal latency unavailable'),
                probe('request_rate_limited', 'critical', 'Journal rate-limit signal unavailable')]


def postgres(config):
    if not config.database_url:
        return probe('database_connections', 'critical', 'Monitor database role is not configured')
    engine = create_engine(config.database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            used = int(connection.execute(text(
                'SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()')).scalar())
            maximum = int(connection.execute(text(
                "SELECT setting::int FROM pg_settings WHERE name='max_connections'" )).scalar())
        percent = used / maximum * 100 if maximum else 100
        return probe('database_connections', status_high(percent, config.db_warning_pct,
                                                         config.db_critical_pct),
                     f'{used}/{maximum} connections', round(percent, 2), 'percent')
    except Exception as error:
        return probe('database_connections', 'critical', f'Probe failed: {type(error).__name__}')
    finally:
        engine.dispose()


def command_probe(identifier, command, timeout=120):
    try:
        result = subprocess.run([command], capture_output=True, timeout=timeout)
        return probe(identifier, 'ok' if result.returncode == 0 else 'critical',
                     'Check passed' if result.returncode == 0 else f'Check exited {result.returncode}')
    except Exception as error:
        return probe(identifier, 'critical', f'Check failed: {type(error).__name__}')


def certificate(config):
    if not config.public_host:
        return probe('tls_expiry', 'critical', 'Public TLS host is not configured')
    try:
        with socket.create_connection((config.public_host, config.public_port), timeout=10) as raw:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=config.public_host) as secured:
                expires = secured.getpeercert()['notAfter']
        end = datetime.strptime(expires, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
        days = max(0, int((end - datetime.now(timezone.utc)).total_seconds() // 86400))
        return probe('tls_expiry', status_low(days, config.tls_warning_days,
                                             config.tls_critical_days),
                     f'{days} days remaining', days, 'days')
    except Exception as error:
        return probe('tls_expiry', 'critical', f'Probe failed: {type(error).__name__}')


def smtp(config):
    if not config.smtp_host:
        return probe('smtp', 'ok', 'SMTP disabled')
    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as client:
            client.ehlo(); client.starttls(context=ssl.create_default_context()); client.ehlo()
        return probe('smtp', 'ok', 'Protected SMTP handshake passed')
    except Exception as error:
        return probe('smtp', 'critical', f'Handshake failed: {type(error).__name__}')


def atomic_write(path, content):
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if temporary.exists(): temporary.unlink()


def append(path, value):
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    with os.fdopen(descriptor, 'a') as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def trim(path, cutoff):
    """Enforce the configured history window; malformed lines are not retained."""
    if not path.exists():
        return
    kept = []
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
            if datetime.fromisoformat(event['at']) >= cutoff:
                kept.append(json.dumps(event, sort_keys=True, separators=(',', ':')))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    atomic_write(path, ('\n'.join(kept) + '\n') if kept else '')


def send(url, payload, token=''):
    headers = {'Content-Type': 'application/json', 'User-Agent': 'TrendSell-monitor/1'}
    if token: headers['Authorization'] = f'Bearer {token}'
    with urlopen(Request(url, json.dumps(payload).encode(), headers, method='POST'), timeout=10) as response:
        if not 200 <= response.status < 300: raise RuntimeError(f'HTTP {response.status}')


def process(config, probes, moment=None, deliver=send):
    moment = moment or datetime.now(timezone.utc)
    state_path = config.state_dir / 'state.json'
    try:
        stored = json.loads(state_path.read_text())
        old = stored.get('probes', {}) if isinstance(stored, dict) else {}
        if not isinstance(old, dict): old = {}
    except (OSError, UnicodeError, json.JSONDecodeError): old = {}
    events = []
    current_by_id = {item['id']: item for item in probes}
    reminder = timedelta(minutes=config.reminder_minutes)
    for item in probes:
        prior = old.get(item['id'], {})
        if not isinstance(prior, dict):
            prior = {}
            old[item['id']] = prior
        # Older state files used the last observation as the last delivered state. Keep
        # that migration behavior, then track delivery separately so a failed recovery
        # notification is retried even though the latest observation is already healthy.
        if 'last_delivered_status' not in prior and prior.get('status'):
            prior['last_delivered_status'] = prior['status']
        delivered_status = prior.get('last_delivered_status')
        last = prior.get('last_alert_at')
        try: due = not last or moment - datetime.fromisoformat(last) >= reminder
        except (TypeError, ValueError): due = True
        pending = prior.get('pending_event')
        valid_pending = (isinstance(pending, dict)
                         and pending.get('kind') in {'alert', 'recovery'}
                         and isinstance(pending.get('probe'), dict)
                         and pending['probe'].get('id') == item['id'])
        if valid_pending:
            # A recovery that could not be delivered becomes obsolete if the probe is
            # unhealthy again. A failed alert remains material even if the transient
            # condition recovered, so deliver it before a later recovery event.
            if pending['kind'] == 'recovery' and item['status'] in BAD:
                prior.pop('pending_event', None)
            else:
                events.append(pending)
                continue
        elif pending is not None:
            prior.pop('pending_event', None)
        if item['status'] in BAD and (delivered_status != item['status'] or due):
            events.append({'kind': 'alert', 'probe': item})
        elif item['status'] == 'ok' and delivered_status in BAD:
            events.append({'kind': 'recovery', 'probe': item,
                           'previous_status': delivered_status})
    delivery_failed = False
    for event in events:
        payload = {'schema': SCHEMA, 'at': moment.isoformat(), **event}
        if not config.webhook_url:
            outcome = {'delivery': 'undeliverable'}; delivery_failed = True
            old.setdefault(event['probe']['id'], {})['pending_event'] = event
        else:
            try:
                deliver(config.webhook_url, payload, config.webhook_token)
                outcome = {'delivery': 'delivered'}
                delivered = old.setdefault(event['probe']['id'], {})
                delivered.pop('pending_event', None)
                delivered['last_alert_at'] = moment.isoformat()
                delivered['last_delivered_status'] = event['probe']['status']
                current = current_by_id[event['probe']['id']]
                if event['kind'] == 'alert' and current['status'] != event['probe']['status']:
                    if current['status'] in BAD:
                        events.append({'kind': 'alert', 'probe': current})
                    else:
                        events.append({'kind': 'recovery', 'probe': current,
                                       'previous_status': event['probe']['status']})
            except Exception as error:
                outcome = {'delivery': 'failed', 'error_type': type(error).__name__}
                delivery_failed = True
                old.setdefault(event['probe']['id'], {})['pending_event'] = event
        append(config.state_dir / 'deliveries.jsonl', {**payload, **outcome})
    latest = {}
    for item in probes:
        prior = old.get(item['id'], {})
        if not isinstance(prior, dict): prior = {}
        delivered_status = prior.get('last_delivered_status')
        if delivered_status is None and item['status'] == 'ok':
            delivered_status = 'ok'
        latest[item['id']] = {
            **item,
            'observed_at': moment.isoformat(),
            'last_alert_at': prior.get('last_alert_at'),
            'last_delivered_status': delivered_status,
            **({'pending_event': prior['pending_event']} if prior.get('pending_event') else {}),
        }
    state = {'schema': SCHEMA, 'updated_at': moment.isoformat(), 'probes': latest,
             'targets': {
                 'retention_days': config.history_days,
                 'disk_free_warning_pct': config.disk_warning_pct,
                 'disk_free_critical_pct': config.disk_critical_pct,
                 'database_warning_pct': config.db_warning_pct,
                 'database_critical_pct': config.db_critical_pct,
                 'latency_warning_ms': config.latency_warning_ms,
                 'latency_critical_ms': config.latency_critical_ms,
                 'error_warning_pct': config.error_warning_pct,
                 'error_critical_pct': config.error_critical_pct,
                 'rate_limit_warning_pct': config.rate_warning_pct,
                 'rate_limit_critical_pct': config.rate_critical_pct,
                 'tls_warning_days': config.tls_warning_days,
                 'tls_critical_days': config.tls_critical_days,
             }}
    append(config.state_dir / 'observations.jsonl',
           {'schema': SCHEMA, 'at': moment.isoformat(), 'probes': probes})
    atomic_write(state_path, json.dumps(state, indent=2, sort_keys=True) + '\n')
    metrics = ['# TYPE trendsell_monitor_probe_status gauge']
    for item in probes:
        metrics.append(f'trendsell_monitor_probe_status{{probe="{item["id"]}"}} '
                       f'{dict(ok=0, warning=1, critical=2)[item["status"]]}')
    atomic_write(config.state_dir / 'metrics.prom', '\n'.join(metrics) + '\n')
    cutoff = moment - timedelta(days=config.history_days)
    trim(config.state_dir / 'observations.jsonl', cutoff)
    trim(config.state_dir / 'deliveries.jsonl', cutoff)
    unhealthy = any(item['status'] in BAD for item in probes)
    if config.heartbeat_url and not unhealthy and not delivery_failed:
        payload = {'schema': SCHEMA, 'at': moment.isoformat(), 'kind': 'heartbeat'}
        try:
            deliver(config.heartbeat_url, payload, '')
            outcome = {'delivery': 'delivered'}
        except Exception as error:
            outcome = {'delivery': 'failed', 'error_type': type(error).__name__}
            delivery_failed = True
        append(config.state_dir / 'deliveries.jsonl', {**payload, **outcome})
    return (1 if unhealthy or delivery_failed else 0), state, events


def collect(config):
    result = [ready(config), service(config), host_disk(config), postgres(config),
              command_probe('backup', config.backup_command), certificate(config), smtp(config)]
    result.extend(request_signals(config))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe-file')
    parser.add_argument('--test-alert', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = Config.from_env()
        if args.status:
            print((config.state_dir / 'state.json').read_text()); return 0
        if args.test_alert:
            probes = [probe('alert_delivery_test', 'critical', 'Synthetic operator-requested test')]
        elif args.probe_file:
            probes = json.loads(Path(args.probe_file).read_text())
        else:
            probes = collect(config)
        if any(not isinstance(item, dict) or item.get('status') not in {'ok', *BAD}
               or not isinstance(item.get('id'), str) for item in probes):
            raise ValueError('invalid probe input')
        code, state, events = process(config, probes)
        print(json.dumps({'state': state, 'delivery_events': events}, indent=2, sort_keys=True))
        return code
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f'FAIL: {error}', file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main())
