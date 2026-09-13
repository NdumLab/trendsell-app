import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    environment: str = 'development'
    database_url: str = 'sqlite:///./trendsell.db'
    origins: tuple[str, ...] = ('http://localhost:3000', 'http://127.0.0.1:3000')
    allow_registration: bool = True
    research_daily_limit: int = 20
    # Authentication limits, per hour (action plan P04). The address limits are generous
    # because a shared network is one address; the account limit is what actually bounds
    # guessing against one person, including from many addresses.
    login_ip_hourly_limit: int = 30
    login_account_hourly_limit: int = 10
    register_ip_hourly_limit: int = 10
    #: Writes per workspace per minute, so one busy workspace cannot crowd out another.
    workspace_write_minute_limit: int = 60
    #: Shared secret for the operational metrics surface (review finding R07). Counters
    #: are fleet-wide, so they are not a workspace's to read: owning a workspace is not
    #: operating the service. Unset means the surface is off, which is the default.
    metrics_token: str = ''
    #: Outbound mail transport (action plan P03): '' (none), 'sink', 'log' or 'smtp'.
    #: Sink/log are development diagnostics; SMTP is the production transport.
    mail_transport: str = ''
    #: Where a 'sink' transport writes each message, for a developer exercising the flow.
    mail_sink_dir: str = ''
    #: How long readiness may reuse its physical-schema verdict (review finding R09).
    #: Inspecting tables and columns on every probe would make a liveness-frequency
    #: endpoint do real work; a changed revision refreshes the verdict regardless of
    #: this interval, so it only bounds how long an *unrecorded* schema change hides.
    schema_recheck_seconds: float = 30.0
    #: HMAC key for network/email rate buckets. Production requires an independent random
    #: value so their small input spaces cannot be enumerated from a database copy.
    rate_key_secret: str = 'development-only-rate-key-secret'
    #: Audit events are useful for investigation but still carry pseudonymous user and
    #: workspace identifiers. Production therefore requires an explicit bounded policy.
    audit_retention_days: int = 365
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    mail_from: str = ''
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    #: Browser origin used in one-time action links. When unset, the first explicit CORS
    #: origin is used; production operators should set this when the UI has several
    #: allowed origins so messages always lead to the canonical host.
    public_app_url: str = ''
    #: Invitation delivery has its own abuse limits: one owner cannot turn the service
    #: into a bulk sender, and one recipient cannot be flooded by several workspaces.
    invitation_workspace_hourly_limit: int = 20
    invitation_email_daily_limit: int = 3

    @classmethod
    def from_env(cls):
        env = os.getenv('APP_ENV', 'development')
        url = os.getenv('DATABASE_URL', 'sqlite:///./trendsell.db' if env != 'production' else '')
        origins = tuple(x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000' if env != 'production' else '').split(',') if x.strip())
        if env not in {'development', 'test', 'production'}:
            raise ValueError('APP_ENV must be development, test, or production')
        if not url:
            raise ValueError('DATABASE_URL is required')
        if '*' in origins or not origins:
            raise ValueError('CORS_ORIGINS must be an explicit origin allowlist')
        if env == 'production' and (not url.startswith('postgresql+psycopg://') or any(not x.startswith('https://') for x in origins)):
            raise ValueError('Production requires postgresql+psycopg DATABASE_URL and HTTPS CORS_ORIGINS')
        limit = int(os.getenv('RESEARCH_DAILY_LIMIT', '20'))
        if limit < 1 or limit > 1000:
            raise ValueError('RESEARCH_DAILY_LIMIT must be between 1 and 1000')

        def hourly(name, default):
            value = int(os.getenv(name, str(default)))
            if value < 1 or value > 100000:
                raise ValueError(f'{name} must be between 1 and 100000')
            return value

        recheck = float(os.getenv('SCHEMA_RECHECK_SECONDS', '30'))
        if recheck < 0 or recheck > 3600:
            raise ValueError('SCHEMA_RECHECK_SECONDS must be between 0 and 3600')

        transport = os.getenv('MAIL_TRANSPORT', '').strip().lower()
        if transport not in {'', 'sink', 'log', 'smtp'}:
            raise ValueError("MAIL_TRANSPORT must be '', 'sink', 'log' or 'smtp'")
        if env == 'production' and transport in {'sink', 'log'}:
            raise ValueError(
                'MAIL_TRANSPORT sink and log are development diagnostics, not delivery.')

        def enabled(name, default):
            value = os.getenv(name, default).strip().lower()
            if value not in {'true', 'false'}:
                raise ValueError(f'{name} must be true or false')
            return value == 'true'

        smtp_host = os.getenv('SMTP_HOST', '').strip()
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME', '')
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        mail_from = os.getenv('MAIL_FROM', '').strip()
        smtp_starttls = enabled('SMTP_STARTTLS', 'true')
        smtp_ssl = enabled('SMTP_SSL', 'false')
        if smtp_port < 1 or smtp_port > 65535:
            raise ValueError('SMTP_PORT must be between 1 and 65535')
        if smtp_starttls and smtp_ssl:
            raise ValueError('SMTP_STARTTLS and SMTP_SSL cannot both be true')
        if bool(smtp_username) != bool(smtp_password):
            raise ValueError('SMTP_USERNAME and SMTP_PASSWORD must either both be set or both be empty')
        if transport == 'smtp':
            if not smtp_host or not mail_from:
                raise ValueError('SMTP_HOST and MAIL_FROM are required when MAIL_TRANSPORT=smtp')
            if env == 'production' and not (smtp_starttls or smtp_ssl):
                raise ValueError('Production SMTP requires SMTP_STARTTLS=true or SMTP_SSL=true')

        rate_key_secret = os.getenv(
            'RATE_KEY_SECRET',
            'development-only-rate-key-secret' if env != 'production' else '')
        if env == 'production' and len(rate_key_secret) < 32:
            raise ValueError('RATE_KEY_SECRET must be an independent random value of at least 32 characters in production')

        audit_retention_days = int(os.getenv('AUDIT_RETENTION_DAYS', '365'))
        if audit_retention_days < 30 or audit_retention_days > 3650:
            raise ValueError('AUDIT_RETENTION_DAYS must be between 30 and 3650')

        public_app_url = os.getenv('PUBLIC_APP_URL', '').strip().rstrip('/')
        if public_app_url and (not public_app_url.startswith(('http://', 'https://'))
                               or (env == 'production' and not public_app_url.startswith('https://'))):
            raise ValueError('PUBLIC_APP_URL must be an HTTPS origin in production')

        return cls(
            environment=env, database_url=url, origins=origins,
            allow_registration=os.getenv(
                'ALLOW_REGISTRATION', 'false' if env == 'production' else 'true') == 'true',
            research_daily_limit=limit,
            login_ip_hourly_limit=hourly('LOGIN_IP_HOURLY_LIMIT', 30),
            login_account_hourly_limit=hourly('LOGIN_ACCOUNT_HOURLY_LIMIT', 10),
            register_ip_hourly_limit=hourly('REGISTER_IP_HOURLY_LIMIT', 10),
            workspace_write_minute_limit=hourly('WORKSPACE_WRITE_MINUTE_LIMIT', 60),
            metrics_token=os.getenv('METRICS_TOKEN', ''), mail_transport=transport,
            mail_sink_dir=os.getenv('MAIL_SINK_DIR', ''), schema_recheck_seconds=recheck,
            rate_key_secret=rate_key_secret, audit_retention_days=audit_retention_days,
            smtp_host=smtp_host, smtp_port=smtp_port, smtp_username=smtp_username,
            smtp_password=smtp_password, mail_from=mail_from, smtp_starttls=smtp_starttls,
            smtp_ssl=smtp_ssl, public_app_url=public_app_url,
            invitation_workspace_hourly_limit=hourly('INVITATION_WORKSPACE_HOURLY_LIMIT', 20),
            invitation_email_daily_limit=hourly('INVITATION_EMAIL_DAILY_LIMIT', 3))
