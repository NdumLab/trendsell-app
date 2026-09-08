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

        return cls(env, url, origins,
                   os.getenv('ALLOW_REGISTRATION', 'false' if env == 'production' else 'true') == 'true', limit,
                   hourly('LOGIN_IP_HOURLY_LIMIT', 30),
                   hourly('LOGIN_ACCOUNT_HOURLY_LIMIT', 10),
                   hourly('REGISTER_IP_HOURLY_LIMIT', 10),
                   hourly('WORKSPACE_WRITE_MINUTE_LIMIT', 60),
                   os.getenv('METRICS_TOKEN', ''))
