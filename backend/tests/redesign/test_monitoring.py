"""Persistent monitoring state and delivery behavior (readiness O02-O04)."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('monitor_trendsell',
    REPOSITORY / 'scripts/monitor_trendsell.py')
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def config(tmp_path, webhook='https://alerts.example.test/trendsell'):
    return monitor.Config(tmp_path, 'http://127.0.0.1/ready', 'trendsell.service', '',
        tmp_path, '/bin/true', '', 443, '', 587, webhook, 'test-token', '', 30, 240, 5,
        20, 10, 70, 85, 1000, 3000, 2, 5, 5, 20, 30, 14, 1, 3)


def test_alert_transition_is_delivered_once_and_persisted(tmp_path):
    sent = []
    deliver = lambda url, payload, token: sent.append((url, payload, token))
    moment = datetime(2026, 9, 16, tzinfo=timezone.utc)
    bad = [monitor.probe('readiness', 'critical', 'synthetic failure')]
    code, state, events = monitor.process(config(tmp_path), bad, moment, deliver)
    assert code == 1 and [event['kind'] for event in events] == ['alert']
    assert sent[0][0] == 'https://alerts.example.test/trendsell' and sent[0][2] == 'test-token'
    assert state['probes']['readiness']['status'] == 'critical'
    assert 'delivered' in (tmp_path / 'deliveries.jsonl').read_text()
    assert 'probe="readiness"} 2' in (tmp_path / 'metrics.prom').read_text()
    code, _, events = monitor.process(config(tmp_path), bad,
                                      moment + timedelta(minutes=5), deliver)
    assert code == 1 and events == [] and len(sent) == 1


def test_recovery_is_delivered(tmp_path):
    sent = []
    deliver = lambda url, payload, token: sent.append(payload)
    moment = datetime(2026, 9, 16, tzinfo=timezone.utc)
    monitor.process(config(tmp_path), [monitor.probe('backup', 'critical', 'old')], moment, deliver)
    code, state, events = monitor.process(config(tmp_path), [monitor.probe('backup', 'ok', 'fresh')],
                                          moment + timedelta(minutes=5), deliver)
    assert code == 0 and [event['kind'] for event in events] == ['recovery']
    assert state['probes']['backup']['status'] == 'ok' and sent[-1]['kind'] == 'recovery'


def test_failed_recovery_delivery_is_retried(tmp_path):
    moment = datetime(2026, 9, 16, tzinfo=timezone.utc)
    bad = [monitor.probe('backup', 'critical', 'old')]
    good = [monitor.probe('backup', 'ok', 'fresh')]
    monitor.process(config(tmp_path), bad, moment, lambda *_: None)

    def fail(*_):
        raise OSError('synthetic delivery failure')

    code, state, events = monitor.process(
        config(tmp_path), good, moment + timedelta(minutes=5), fail)
    assert code == 1 and [event['kind'] for event in events] == ['recovery']
    assert state['probes']['backup']['last_delivered_status'] == 'critical'

    sent = []
    code, state, events = monitor.process(
        config(tmp_path), good, moment + timedelta(minutes=10),
        lambda _url, payload, _token: sent.append(payload))
    assert code == 0 and [event['kind'] for event in events] == ['recovery']
    assert sent[-1]['kind'] == 'recovery'
    assert state['probes']['backup']['last_delivered_status'] == 'ok'


def test_failed_transient_alert_is_retried_after_the_probe_recovers(tmp_path):
    moment = datetime(2026, 9, 16, tzinfo=timezone.utc)
    good = [monitor.probe('service', 'ok', 'steady')]
    warning = [monitor.probe('service', 'warning', 'one restart')]
    monitor.process(config(tmp_path), good, moment, lambda *_: None)

    def fail(*_):
        raise OSError('synthetic delivery failure')

    code, state, _ = monitor.process(
        config(tmp_path), warning, moment + timedelta(minutes=5), fail)
    assert code == 1
    assert state['probes']['service']['pending_event']['probe']['status'] == 'warning'

    sent = []
    code, state, events = monitor.process(
        config(tmp_path), good, moment + timedelta(minutes=10),
        lambda _url, payload, _token: sent.append(payload))
    assert code == 0 and [event['kind'] for event in events] == ['alert', 'recovery']
    assert sent[-2]['probe']['status'] == 'warning'
    assert sent[-1]['kind'] == 'recovery'
    assert state['probes']['service']['status'] == 'ok'
    assert state['probes']['service']['last_delivered_status'] == 'ok'


def test_heartbeat_attempt_is_persisted(tmp_path):
    monitored = replace(config(tmp_path),
                        heartbeat_url='https://heartbeat.example.test/trendsell')
    code, _, _ = monitor.process(
        monitored, [monitor.probe('readiness', 'ok', 'ready')],
        datetime(2026, 9, 16, tzinfo=timezone.utc), lambda *_: None)
    assert code == 0
    delivery = json.loads((tmp_path / 'deliveries.jsonl').read_text())
    assert delivery['kind'] == 'heartbeat' and delivery['delivery'] == 'delivered'


def test_missing_delivery_is_visible_and_fails(tmp_path):
    code, _, _ = monitor.process(config(tmp_path, webhook=''),
        [monitor.probe('disk_free', 'warning', 'synthetic low disk')],
        datetime(2026, 9, 16, tzinfo=timezone.utc))
    assert code == 1 and 'undeliverable' in (tmp_path / 'deliveries.jsonl').read_text()


def test_threshold_directions_are_explicit():
    assert monitor.status_low(9, 20, 10) == 'critical'
    assert monitor.status_low(15, 20, 10) == 'warning'
    assert monitor.status_high(86, 70, 85) == 'critical'
    assert monitor.status_high(75, 70, 85) == 'warning'
    assert monitor.status_high(20, 70, 85) == 'ok'


def test_service_restart_threshold_uses_delta_not_lifetime_total(tmp_path, monkeypatch):
    state = {'probes': {'service': {'value': 40}}}
    (tmp_path / 'state.json').write_text(json.dumps(state))
    monkeypatch.setattr(monitor.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout='active\n41\n'))
    observed = monitor.service(config(tmp_path))
    assert observed['status'] == 'warning'
    assert observed['value'] == 41
    assert 'restart_delta=1' in observed['detail']


def test_journal_signals_include_fleet_rate_limits(tmp_path, monkeypatch):
    lines = '\n'.join([
        json.dumps({'message': 'request', 'status': 200, 'duration_ms': 10}),
        json.dumps({'message': 'request', 'status': 429, 'duration_ms': 20}),
        json.dumps({'message': 'request', 'status': 500, 'duration_ms': 30}),
        json.dumps({'message': 'startup'}),
    ])
    monkeypatch.setattr(monitor.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout=lines))
    signals = {item['id']: item for item in monitor.request_signals(config(tmp_path))}
    assert signals['request_errors']['detail'] == '1/3 server errors'
    assert signals['request_rate_limited']['detail'] == '1/3 rate-limited requests'
    assert signals['request_latency']['value'] == 30
