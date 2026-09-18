import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    environment: str = 'development'
    #: This release intentionally supports one real-user scope. Keeping the tier in
    #: configuration makes an open or paid launch a deliberate software change instead
    #: of an accidental toggle of the registration flag.
    release_tier: str = 'development'
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
    #: Append-only deletion intent lives outside PostgreSQL so an older restore cannot
    #: resurrect a workspace deleted after that recovery point. Production requires an
    #: explicit restricted directory; tests opt in with a disposable path.
    deletion_register_dir: str = ''
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
    #: Amazon Creators API is an explicit server-side opt-in. Credentials are never sent
    #: to the browser or written to source-health/job records.
    amazon_creators_enabled: bool = False
    amazon_creators_credential_id: str = ''
    amazon_creators_credential_secret: str = ''
    amazon_creators_credential_version: str = '3.1'
    amazon_creators_partner_tag: str = ''
    amazon_creators_marketplace: str = 'www.amazon.com'
    amazon_creators_usage_rights: str = ''
    amazon_creators_timeout_seconds: float = 12.0
    #: The live pilot uses commercial research feeds only after an operator records the
    #: applicable accepted terms, plan, and intended-use basis. Published terms may
    #: establish permission; this field is evidence of that basis, not a made-up demand
    #: for separate written approval. A key without it is intentionally misconfigured.
    dataforseo_enabled: bool = False
    dataforseo_login: str = ''
    dataforseo_password: str = ''
    dataforseo_usage_rights: str = ''
    dataforseo_catalog_location_code: int = 2840
    dataforseo_trends_location_code: int = 2566
    dataforseo_retention_days: int = 30
    dataforseo_timeout_seconds: float = 15.0
    brightdata_jumia_enabled: bool = False
    brightdata_api_token: str = ''
    brightdata_jumia_dataset_id: str = ''
    brightdata_jumia_usage_rights: str = ''
    brightdata_jumia_retention_days: int = 30
    brightdata_timeout_seconds: float = 65.0
    open_exchange_rates_enabled: bool = False
    open_exchange_rates_app_id: str = ''
    open_exchange_rates_usage_rights: str = ''
    open_exchange_rates_retention_days: int = 365
    open_exchange_rates_timeout_seconds: float = 12.0
    #: Actionable import review stays unavailable in production until Product names the
    #: qualified category/jurisdiction scope. Development/test defaults keep the workflow
    #: exercisable; production from_env defaults it off and requires an approval reference.
    import_review_enabled: bool = True
    import_review_policy_ref: str = ''

    @classmethod
    def from_env(cls):
        env = os.getenv('APP_ENV', 'development')
        release_tier = os.getenv(
            'RELEASE_TIER', 'controlled_pilot' if env == 'production' else 'development'
        ).strip().lower()
        if release_tier not in {'development', 'controlled_pilot'}:
            raise ValueError(
                'RELEASE_TIER must be development or controlled_pilot; '
                'this release does not support public or paid launch tiers')
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
        registration_value = os.getenv(
            'ALLOW_REGISTRATION', 'false' if env == 'production' else 'true'
        ).strip().lower()
        if registration_value not in {'true', 'false'}:
            raise ValueError('ALLOW_REGISTRATION must be true or false')
        allow_registration = registration_value == 'true'
        if env == 'production' and release_tier != 'controlled_pilot':
            raise ValueError('Production only supports RELEASE_TIER=controlled_pilot in this release')
        if release_tier == 'controlled_pilot' and allow_registration:
            raise ValueError(
                'The controlled pilot is invitation-only; ALLOW_REGISTRATION must be false')
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

        deletion_register_dir = os.getenv('DELETION_REGISTER_DIR', '').strip()
        if env == 'production' and (not os.path.isabs(deletion_register_dir)
                                    or os.path.normpath(deletion_register_dir) == os.path.sep):
            raise ValueError(
                'DELETION_REGISTER_DIR must be a dedicated absolute path in production')

        public_app_url = os.getenv('PUBLIC_APP_URL', '').strip().rstrip('/')
        if public_app_url and (not public_app_url.startswith(('http://', 'https://'))
                               or (env == 'production' and not public_app_url.startswith('https://'))):
            raise ValueError('PUBLIC_APP_URL must be an HTTPS origin in production')

        amazon_enabled = enabled('AMAZON_CREATORS_ENABLED', 'false')
        amazon_version = os.getenv('AMAZON_CREATORS_CREDENTIAL_VERSION', '3.1').strip()
        if amazon_version not in {'3.1', '3.2', '3.3'}:
            raise ValueError('AMAZON_CREATORS_CREDENTIAL_VERSION must be 3.1, 3.2, or 3.3')
        amazon_marketplace = os.getenv('AMAZON_CREATORS_MARKETPLACE', 'www.amazon.com').strip().lower()
        # The product-input contract and evidence market currently support Amazon US
        # only. Do not accept a valid-looking foreign locale and then label its evidence
        # as US; add the locale mapping and identifier contract before widening this.
        if amazon_marketplace != 'www.amazon.com':
            raise ValueError('AMAZON_CREATORS_MARKETPLACE must be www.amazon.com for this pilot')
        amazon_timeout = float(os.getenv('AMAZON_CREATORS_TIMEOUT_SECONDS', '12'))
        if amazon_timeout < 1 or amazon_timeout > 60:
            raise ValueError('AMAZON_CREATORS_TIMEOUT_SECONDS must be between 1 and 60')

        def bounded_int(name, default, minimum, maximum):
            value = int(os.getenv(name, str(default)))
            if value < minimum or value > maximum:
                raise ValueError(f'{name} must be between {minimum} and {maximum}')
            return value

        def timeout(name, default):
            value = float(os.getenv(name, str(default)))
            if value < 1 or value > 120:
                raise ValueError(f'{name} must be between 1 and 120')
            return value

        dataforseo_retention = bounded_int('DATAFORSEO_RETENTION_DAYS', 30, 1, 3650)
        brightdata_retention = bounded_int('BRIGHTDATA_JUMIA_RETENTION_DAYS', 30, 1, 3650)
        oxr_retention = bounded_int('OPEN_EXCHANGE_RATES_RETENTION_DAYS', 365, 1, 3650)

        import_review_enabled = enabled(
            'IMPORT_REVIEW_ENABLED', 'false' if env == 'production' else 'true')
        import_review_policy_ref = os.getenv('IMPORT_REVIEW_POLICY_REF', '').strip()
        if env == 'production' and import_review_enabled and not import_review_policy_ref:
            raise ValueError(
                'IMPORT_REVIEW_POLICY_REF is required when import review is enabled in production')

        return cls(
            environment=env, release_tier=release_tier, database_url=url, origins=origins,
            allow_registration=allow_registration,
            research_daily_limit=limit,
            login_ip_hourly_limit=hourly('LOGIN_IP_HOURLY_LIMIT', 30),
            login_account_hourly_limit=hourly('LOGIN_ACCOUNT_HOURLY_LIMIT', 10),
            register_ip_hourly_limit=hourly('REGISTER_IP_HOURLY_LIMIT', 10),
            workspace_write_minute_limit=hourly('WORKSPACE_WRITE_MINUTE_LIMIT', 60),
            metrics_token=os.getenv('METRICS_TOKEN', ''), mail_transport=transport,
            mail_sink_dir=os.getenv('MAIL_SINK_DIR', ''), schema_recheck_seconds=recheck,
            rate_key_secret=rate_key_secret, audit_retention_days=audit_retention_days,
            deletion_register_dir=deletion_register_dir,
            smtp_host=smtp_host, smtp_port=smtp_port, smtp_username=smtp_username,
            smtp_password=smtp_password, mail_from=mail_from, smtp_starttls=smtp_starttls,
            smtp_ssl=smtp_ssl, public_app_url=public_app_url,
            invitation_workspace_hourly_limit=hourly('INVITATION_WORKSPACE_HOURLY_LIMIT', 20),
            invitation_email_daily_limit=hourly('INVITATION_EMAIL_DAILY_LIMIT', 3),
            amazon_creators_enabled=amazon_enabled,
            amazon_creators_credential_id=os.getenv('AMAZON_CREATORS_CREDENTIAL_ID', ''),
            amazon_creators_credential_secret=os.getenv('AMAZON_CREATORS_CREDENTIAL_SECRET', ''),
            amazon_creators_credential_version=amazon_version,
            amazon_creators_partner_tag=os.getenv('AMAZON_CREATORS_PARTNER_TAG', '').strip(),
            amazon_creators_marketplace=amazon_marketplace,
            amazon_creators_usage_rights=os.getenv('AMAZON_CREATORS_USAGE_RIGHTS', '').strip(),
            amazon_creators_timeout_seconds=amazon_timeout,
            dataforseo_enabled=enabled('DATAFORSEO_ENABLED', 'false'),
            dataforseo_login=os.getenv('DATAFORSEO_LOGIN', '').strip(),
            dataforseo_password=os.getenv('DATAFORSEO_PASSWORD', ''),
            dataforseo_usage_rights=os.getenv('DATAFORSEO_USAGE_RIGHTS', '').strip(),
            dataforseo_catalog_location_code=bounded_int(
                'DATAFORSEO_CATALOG_LOCATION_CODE', 2840, 1, 9999999),
            dataforseo_trends_location_code=bounded_int(
                'DATAFORSEO_TRENDS_LOCATION_CODE', 2566, 1, 9999999),
            dataforseo_retention_days=dataforseo_retention,
            dataforseo_timeout_seconds=timeout('DATAFORSEO_TIMEOUT_SECONDS', 15),
            brightdata_jumia_enabled=enabled('BRIGHTDATA_JUMIA_ENABLED', 'false'),
            brightdata_api_token=os.getenv('BRIGHTDATA_API_TOKEN', ''),
            brightdata_jumia_dataset_id=os.getenv('BRIGHTDATA_JUMIA_DATASET_ID', '').strip(),
            brightdata_jumia_usage_rights=os.getenv('BRIGHTDATA_JUMIA_USAGE_RIGHTS', '').strip(),
            brightdata_jumia_retention_days=brightdata_retention,
            brightdata_timeout_seconds=timeout('BRIGHTDATA_TIMEOUT_SECONDS', 65),
            open_exchange_rates_enabled=enabled('OPEN_EXCHANGE_RATES_ENABLED', 'false'),
            open_exchange_rates_app_id=os.getenv('OPEN_EXCHANGE_RATES_APP_ID', ''),
            open_exchange_rates_usage_rights=os.getenv(
                'OPEN_EXCHANGE_RATES_USAGE_RIGHTS', '').strip(),
            open_exchange_rates_retention_days=oxr_retention,
            open_exchange_rates_timeout_seconds=timeout('OPEN_EXCHANGE_RATES_TIMEOUT_SECONDS', 12),
            import_review_enabled=import_review_enabled,
            import_review_policy_ref=import_review_policy_ref)
