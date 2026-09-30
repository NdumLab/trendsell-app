# Target technical gap audit

Observed 30 September 2026 UTC on the TrendSell production host. This is a
read-only evidence record: no configuration, service, database, firewall,
backup, bucket, user, or release state was changed.

The installed release records commit `d15ff395c8c437c2a6f5c3277577bdc9065c4052`.
The application runtime paths at that commit (`backend/app`, migrations,
runtime dependency lock, frontend, contracts and deploy templates) are the
same git tree objects as candidate
`3478c9891c79d01ef3d08535d810aa92830f5ebd`. The candidate additionally
contains the deployment-layout guard, its tests and release documentation.

## Result

This audit closes several evidence unknowns but does not turn a release gate
into PASS. It confirms that the public network boundary, service sandbox and
current backup are healthy. It also demonstrates, rather than assumes, the
remaining database-role, database-TLS, installed-monitor, bucket-control and
deployment-layout gaps.

## Public and service boundary

* UFW is active with default deny for inbound and routed traffic. Public TCP
  rules are limited to rate-limited SSH management plus HTTP/HTTPS. The only
  wildcard listeners are SSH and nginx on ports 22, 80 and 443.
* TrendSell's API listens only on `127.0.0.1:8021`; its PostgreSQL container is
  published only on `127.0.0.1:55432`. The test and release-gate databases are
  also loopback-only.
* nginx is the public application path and proxies TrendSell to
  `127.0.0.1:8021`. The public HTML response carries HSTS, CSP,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and
  `Permissions-Policy`.
* `/api/health` and `/api/ready` both returned HTTP 200. Readiness reported
  revision `0006_workspace_invitations` and a physical schema matching the
  models.

This supplies the listener/firewall half of `S02`. It does not close that gate
because the database privilege state below is not least privilege.

## Installed service and configuration

The installed application service runs as the dedicated `trendsell` user and
group with `UMask=0077`, no capability bounding set, `NoNewPrivileges=yes`,
`PrivateTmp=yes`, `ProtectHome=yes`, `ProtectSystem=strict`, an explicit write
path for the deletion register, and restricted address families. The current
`systemd-analyze security` exposure score is **1.5 OK**.

The non-secret release settings are coherent with the selected tier:

| Setting | Installed value |
| --- | --- |
| Environment | production |
| Release tier | controlled pilot |
| Public registration | disabled |
| Allowed browser origin | `https://trendsell.yerikasystems.com` |
| Mail transport | SMTP |
| DataForSEO collector | disabled |
| Bright Data Jumia collector | disabled |
| Open Exchange Rates collector | disabled |

Secret-bearing environment files were inspected only for ownership, mode and
variable names; their values were not printed or copied into this record.

The installed unit remains rooted at `/opt/trendsell/backend`, while the
repository template is rooted at `/opt/trendsell/current/backend`. The
installed nginx frontend root is likewise outside the repository's immutable
`current` release layout. The service is hardened and has restarted cleanly,
but the installed file hashes differ from the release templates and no
current/previous activation or rollback path exists. No controlled host reboot
was performed by this audit.

## PostgreSQL identity, privileges and transport

Read-only catalog queries against the production connection reported:

| Fact | Observed value |
| --- | --- |
| PostgreSQL | 16.4 |
| Runtime login | `trendsell_app` |
| Superuser / create-role / create-database / replication / bypass-RLS flags | all false |
| PostgreSQL TLS for the application connection | **false** |
| Database CREATE privilege | **true** |
| Database TEMP privilege | **true** |
| `public` schema CREATE privilege | **true** |
| Application schema objects owned by runtime login | **9 of 9** |
| Separate installed migration URL/role | **not configured** |

The login is not a cluster superuser, which is useful, but it is still the
schema owner and can create database, temporary and schema objects. Production
therefore does not use the tested split migration/runtime role model. The
loopback-only container connection is not encrypted with PostgreSQL TLS, and
at-rest encryption and capacity/maintenance ownership remain undocumented.
`I02` and the privilege half of `S02` remain BLOCKED.

## Backup and object storage

The backup, backup-age and deletion-register timers are enabled and active.
The current exact installed backup check passed:

> PASS newest local and encrypted offsite TrendSell backup agree; age=7h

That check verifies local SHA-256, `pg_restore --list`, offsite object size,
server-side AES-256 metadata and SHA-256 agreement for both the dump and its
sidecar.

The installed backup credential was denied permission to read bucket
versioning, default encryption, Public Access Block, policy status and
lifecycle configuration. This does not show those controls are absent; it
shows the release evidence cannot currently prove them with the installed
principal. The principal is shared with another backup workload rather than
being TrendSell-only. There is still no delivered backup-failure alert to a
named TrendSell operator. `D02` therefore remains BLOCKED despite the current
healthy backup.

## Monitoring and alert delivery

No `trendsell-monitor.service` or `trendsell-monitor.timer` is installed. The
backup-age timer and deletion-register synchronization are active, but they do
not replace the repository monitor's readiness, service restart, database,
disk, latency/error, rate-limit, TLS, SMTP and provider probes. No alert or
heartbeat destination was invoked.

This confirms the current residual state of `O02`, `O03` and `O04`: the
monitoring implementation exists in the candidate, but the target installation
and named-recipient drill do not.

## Gate impact and exact next actions

| Gate | Evidence advanced here | Remaining requirement |
| --- | --- | --- |
| R06 | Current listeners, service identity, redacted settings, installed paths and configuration divergence are inventoried | Reconcile the immutable release layout and database roles; named owner reviews the resulting topology record |
| S02 | API and PostgreSQL are loopback-only; UFW default-denies inbound traffic except SSH/HTTP/HTTPS | Apply and verify split database roles in approved staging/target; decide and document transport-encryption treatment |
| I02 | Exact PostgreSQL version, login flags, ownership, creation privileges and TLS state are recorded | Separate migration/runtime roles, TLS/at-rest/capacity facts and maintenance ownership |
| I03 | Dedicated service identity and strong systemd sandbox are verified | Install from the intended immutable paths, diff exact templates, and perform authorized restart/reboot recovery evidence |
| D02 | Current local/offsite integrity and all three recovery-related timers are verified | TrendSell-only IAM scope, bucket TLS/Public Access Block/lifecycle evidence and delivered failure alert |
| O02–O04 | Absence of the target monitor installation is verified | Approve owner/destination/retention, install the monitor and perform an end-to-end synthetic alert drill |

These are target facts, not approvals. The overall release decision remains
NO-GO until the checklist's named-owner and independent-review conditions are
also satisfied.
