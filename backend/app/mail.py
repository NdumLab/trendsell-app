"""Outbound mail transports and the local sink used by recovery tests.

Action plan P03. Provider choice remains a deployment decision. The application ships a
standard authenticated SMTP transport plus development-only transports, and always asks a
`Mailer` to deliver so an unconfigured deployment cannot pretend a message was sent.

Four transports, because "not configured" and "configured wrongly" must not look alike:

``SinkMailer``          keeps messages in memory and, when given a directory, writes each
                        one as a file. This is the local mail sink P03 requires for tests
                        and for a developer exercising the flow by hand.
``UnconfiguredMailer``  the default. Accepts nothing and says so. Recovery reports itself
                        unavailable rather than silently dropping a reset a user is
                        waiting for.
``LoggingMailer``       records that a message was addressed, with no body and no address,
                        for development diagnostics before a provider exists.
``SMTPMailer``          sends through a configured submission endpoint using implicit TLS
                        or STARTTLS. Provider choice stays in deployment configuration.
"""
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
import json
import re
import smtplib
import ssl

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
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f'{len(self.sent) + 1:04d}-{message.purpose}.json'
            path.write_text(json.dumps({'to': message.to, 'subject': message.subject,
                                        'purpose': message.purpose, 'body': message.body}, indent=2))
        self.sent.append(message)
        return message

    def latest(self, purpose=None):
        for message in reversed(self.sent):
            if purpose is None or message.purpose == purpose:
                return message
        return None


class LoggingMailer(Mailer):
    """Records an attempted mail without pretending that it delivered anything.

    This is useful while observing demand for mail in development, but it is not a
    delivery transport. Callers must not mint a bearer credential or tell a person to
    check their inbox merely because this logger was selected.
    """
    configured = False

    def send(self, message: Message):
        if not deliverable(message.to):
            raise MailNotConfigured('Address is not deliverable.')
        # No address and no body: a reset link is a bearer credential.
        logger.info('mail', extra={'context': {'purpose': message.purpose, 'delivered': False}})
        return message


@dataclass(frozen=True)
class SMTPMailer(Mailer):
    """Deliver through a standard authenticated SMTP submission service."""
    host: str
    port: int
    sender: str
    username: str = ''
    password: str = ''
    starttls: bool = True
    implicit_tls: bool = False
    timeout: float = 15.0
    configured = True

    def send(self, message: Message):
        if not deliverable(message.to):
            raise MailNotConfigured('Address is not deliverable.')
        if not deliverable(self.sender):
            raise MailNotConfigured('MAIL_FROM is not a deliverable address.')

        outgoing = EmailMessage()
        outgoing['From'] = self.sender
        outgoing['To'] = message.to
        outgoing['Subject'] = message.subject
        outgoing.set_content(message.body)

        context = ssl.create_default_context()
        client_type = smtplib.SMTP_SSL if self.implicit_tls else smtplib.SMTP
        extra = {'context': context} if self.implicit_tls else {}
        with client_type(self.host, self.port, timeout=self.timeout, **extra) as client:
            if self.starttls:
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            if self.username:
                client.login(self.username, self.password)
            client.send_message(outgoing)
        return message


def build(settings):
    """The transport this configuration asks for."""
    transport = (getattr(settings, 'mail_transport', '') or '').strip().lower()
    if transport == 'sink':
        directory = getattr(settings, 'mail_sink_dir', '') or None
        return SinkMailer(Path(directory) if directory else None)
    if transport == 'log':
        return LoggingMailer()
    if transport == 'smtp':
        return SMTPMailer(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.mail_from,
            username=settings.smtp_username,
            password=settings.smtp_password,
            starttls=settings.smtp_starttls,
            implicit_tls=settings.smtp_ssl,
        )
    return UnconfiguredMailer()
