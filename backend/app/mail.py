"""Outbound mail, and the local sink that makes recovery testable without a provider.

Action plan P03. The provider decision is not mine to make and is still open, so this
deliberately ships *no* provider. What it does ship is the seam: the application always
asks a `Mailer` to deliver, and which mailer it gets is configuration.

Three transports, because "not configured" and "configured wrongly" must not look alike:

``SinkMailer``          keeps messages in memory and, when given a directory, writes each
                        one as a file. This is the local mail sink P03 requires for tests
                        and for a developer exercising the flow by hand.
``UnconfiguredMailer``  the default. Accepts nothing and says so. Recovery reports itself
                        unavailable rather than silently dropping a reset a user is
                        waiting for.
``LoggingMailer``       records that a message was addressed, with no body and no address,
                        for a deployment that wants evidence of volume before a provider
                        exists.

No transport here opens a socket. Adding a real provider means adding one class and one
settings branch; nothing that calls `send()` changes.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json
import re

from .observability import logger


class MailNotConfigured(RuntimeError):
    """Raised when delivery is required but no transport can deliver."""


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str
    #: What the message is for, so a sink can be asserted on without parsing prose.
    purpose: str = 'general'


#: A deliberately conservative shape. This is an addressability check for our own
#: outbound path, not an opinion about what the RFCs permit.
ADDRESS = re.compile(r'^[^@\s]+@[^@\s.]+\.[^@\s]+$')


def deliverable(address):
    return bool(address) and bool(ADDRESS.match(address)) and len(address) <= 320


class Mailer:
    """The seam. `configured` is what callers check before promising delivery."""
    configured = False

    def send(self, message: Message):
        raise NotImplementedError


class UnconfiguredMailer(Mailer):
    """The default: refuses, loudly, rather than pretending to have sent something."""
    configured = False

    def send(self, message: Message):
        raise MailNotConfigured(
            'No mail transport is configured, so this message cannot be delivered. '
            'Set MAIL_TRANSPORT (see docs/RUNBOOK.md).')


@dataclass
class SinkMailer(Mailer):
    """A local mail sink: every message is kept, and optionally written to a directory.

    Purpose-built for P03's acceptance check — "tests use a local mail sink; recovery is
    exercised end to end" — so a test can read the token out of the message the user would
    have received, rather than reaching into the database and testing nothing about the
    delivery path.
    """
    directory: Path | None = None
    sent: list[Message] = field(default_factory=list)
    configured = True

    def send(self, message: Message):
        if not deliverable(message.to):
            raise MailNotConfigured(f'{message.to!r} is not an address this transport can send to.')
        self.sent.append(message)
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f'{len(self.sent):04d}-{message.purpose}.json'
            path.write_text(json.dumps({'to': message.to, 'subject': message.subject,
                                        'purpose': message.purpose, 'body': message.body}, indent=2))
        return message

    def latest(self, purpose=None):
        for message in reversed(self.sent):
            if purpose is None or message.purpose == purpose:
                return message
        return None


class LoggingMailer(Mailer):
    """Counts messages without keeping their content, addresses or tokens."""
    configured = True

    def send(self, message: Message):
        if not deliverable(message.to):
            raise MailNotConfigured('Address is not deliverable.')
        # No address and no body: a reset link is a bearer credential.
        logger.info('mail', extra={'context': {'purpose': message.purpose, 'delivered': False}})
        return message


def build(settings):
    """The transport this configuration asks for."""
    transport = (getattr(settings, 'mail_transport', '') or '').strip().lower()
    if transport == 'sink':
        directory = getattr(settings, 'mail_sink_dir', '') or None
        return SinkMailer(Path(directory) if directory else None)
    if transport == 'log':
        return LoggingMailer()
    return UnconfiguredMailer()
