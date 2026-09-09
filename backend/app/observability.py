"""Request identity, structured logs and operational counters (action plan P07).

An injected failure has to be findable. Every request gets an id — the client's
``X-Request-ID`` when it looks sane, otherwise a generated one — which is returned on the
response, written on every log line for that request, and stored on the audit event the
request produced. That is the thread from "a user reported an error at 14:02" to the exact
row that was written.

Logs are JSON, one object per line, and carry no credentials, no request bodies and no
record payloads: a path, a status, a duration, the request id and — when the request was
authenticated — the workspace and user ids.
"""
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

REQUEST_ID: ContextVar[str] = ContextVar('request_id', default='-')
WORKSPACE_ID: ContextVar[str] = ContextVar('workspace_id', default='-')
USER_ID: ContextVar[str] = ContextVar('user_id', default='-')

SAFE_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{8,64}$')


def request_id():
    return REQUEST_ID.get()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'time': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname.lower(),
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', REQUEST_ID.get()),
        }
        for key, value in getattr(record, 'context', {}).items():
            payload[key] = value
        if record.exc_info:
            payload['error'] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(payload, default=str)


def configure_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger('trendsell')
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False
    return root


logger = configure_logging()


#: Every label a worker will retain. A metric label set is a fixed vocabulary; anything
#: past this bound is folded into `OVERFLOW_LABEL` rather than growing without limit.
MAX_LABELS = 200
OVERFLOW_LABEL = '<other>'
#: Requests that matched no route. One label for all of them, whatever was asked for.
UNMATCHED_LABEL = '<unmatched>'


def route_label(path, route=None):
    """The label for one request: the *matched route template*, never the raw path.

    Review finding R07: labels were built by collapsing path segments that looked like
    long hex ids, so every other client-controlled segment — including any unknown path,
    which needs no authentication — became a dictionary key retained for the worker's
    lifetime. Twenty unknown paths produced twenty permanent labels.

    A matched route already has a bounded template (`/api/v1/products/{product_id}`), and
    the router hands it to the middleware, so the template is the label. Everything else
    is one shared label. `path` is accepted so a caller reads naturally and so the two
    arguments stay together, but it is deliberately never used to build a label: a
    request rejected before routing — a CSRF failure, an unknown path — has no template,
    and its path is whatever the caller typed (review finding F05).
    """
    return getattr(route, 'path', None) or UNMATCHED_LABEL


class Counters:
    """In-process operational counters. Deliberately small and proportionate to the pilot.

    They are per worker, so a value is a floor rather than a fleet total; the metrics
    response says so rather than implying otherwise.
    """

    def __init__(self):
        self.started_at = time.time()
        self.requests = {}
        self.errors = {}
        self.status = {}
        self.duration_ms = {}
        self.rate_limited = 0
        self.jobs = {}

    def _bounded(self, label):
        """`label`, or the overflow label once this worker has seen enough of them.

        Bounding the *set* is what keeps an unauthenticated caller from growing a worker's
        memory one unknown path at a time (review finding R07).
        """
        if label in self.requests or len(self.requests) < MAX_LABELS:
            return label
        return OVERFLOW_LABEL

    def record(self, method, path, status, duration_ms, route=None):
        label = self._bounded(f'{method} {route_label(path, route)}')
        self.requests[label] = self.requests.get(label, 0) + 1
        self.status[str(status)] = self.status.get(str(status), 0) + 1
        bucket = self.duration_ms.setdefault(label, {'count': 0, 'total': 0.0, 'max': 0.0})
        bucket['count'] += 1
        bucket['total'] += duration_ms
        bucket['max'] = max(bucket['max'], duration_ms)
        if status >= 500:
            self.errors[label] = self.errors.get(label, 0) + 1
        if status == 429:
            self.rate_limited += 1

    def record_job(self, status):
        self.jobs[status] = self.jobs.get(status, 0) + 1

    def snapshot(self):
        return {
            'note': 'Counters are per worker process and reset on restart, so a value is a '
                    'floor rather than a fleet total.',
            'uptime_seconds': round(time.time() - self.started_at, 1),
            'requests': dict(sorted(self.requests.items())),
            'responses_by_status': dict(sorted(self.status.items())),
            'server_errors': dict(sorted(self.errors.items())),
            'rate_limited': self.rate_limited,
            'jobs': dict(sorted(self.jobs.items())),
            'latency_ms': {label: {'count': b['count'], 'mean': round(b['total'] / b['count'], 1),
                                   'max': round(b['max'], 1)}
                           for label, b in sorted(self.duration_ms.items())},
        }


def new_request_id(supplied):
    """Use the caller's id when it is a sane token, otherwise mint one."""
    if supplied and SAFE_REQUEST_ID.match(supplied):
        return supplied
    return uuid.uuid4().hex
