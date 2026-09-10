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
    #: Outbound mail transport (action plan P03): '' (none), 'sink' or 'log'. No provider
    #: is shipped -- that decision is still open -- so recovery reports itself unavailable
    #: rather than silently dropping a reset a user is waiting for.
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
        if transport not in {'', 'sink', 'log'}:
            raise ValueError("MAIL_TRANSPORT must be '', 'sink' or 'log'")
        if env == 'production' and transport:
            raise ValueError(
                'No production mail transport ships with this release. '
                'MAIL_TRANSPORT must be empty in production; sink and log are '
                'development diagnostics, not delivery.')

        rate_key_secret = os.getenv(
            'RATE_KEY_SECRET',
            'development-only-rate-key-secret' if env != 'production' else '')
        if env == 'production' and len(rate_key_secret) < 32:
            raise ValueError('RATE_KEY_SECRET must be an independent random value of at least 32 characters in production')

        return cls(env, url, origins,
                   os.getenv('ALLOW_REGISTRATION', 'false' if env == 'production' else 'true') == 'true', limit,
                   hourly('LOGIN_IP_HOURLY_LIMIT', 30),
                   hourly('LOGIN_ACCOUNT_HOURLY_LIMIT', 10),
                   hourly('REGISTER_IP_HOURLY_LIMIT', 10),
                   hourly('WORKSPACE_WRITE_MINUTE_LIMIT', 60),
                   os.getenv('METRICS_TOKEN', ''),
                   transport,
                   os.getenv('MAIL_SINK_DIR', ''),
                   recheck,
                   rate_key_secret)
