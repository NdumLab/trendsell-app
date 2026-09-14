# Incident, breach and data-request runbook

Status: **DRAFT — owner approval, contacts and tabletop evidence are release-blocking**

Applies to the free, invitation-only TrendSell controlled pilot. This document supplies a
procedure; it does not supply legal advice, appoint an owner, establish a notification
deadline or authorize a release. The production-readiness gates S11 and P07 remain blocked
until the required people fill the fields below, approve this version and complete the
recorded exercises.

## Required ownership before pilot admission

Blank values are **BLOCKED**, not implied assignments.

| Role | Named person | Secure contact | Backup/delegate | Approved at (UTC) |
| --- | --- | --- | --- | --- |
| Incident commander | **PENDING** | **PENDING** | **PENDING** | **PENDING** |
| Platform responder | **PENDING** | **PENDING** | **PENDING** | **PENDING** |
| Security/Privacy decision-maker | **PENDING** | **PENDING** | **PENDING** | **PENDING** |
| Product/support communicator | **PENDING** | **PENDING** | **PENDING** | **PENDING** |
| Qualified legal/regulatory adviser, when required | **PENDING** | **PENDING** | **PENDING** | **PENDING** |

The approved access register must separately identify who may read production logs,
query the database, administer the host, access backup objects, rotate credentials and
contact processors. An application workspace role grants none of those powers.

## When to declare an incident

Open an incident immediately for any suspected:

- cross-workspace read/write or authorization bypass;
- credential, recovery token, session or private-data exposure;
- silent corruption, deletion, lost write, failed restore or decision replay mismatch;
- use or disclosure of a source without approved rights;
- materially false product, evidence, import-readiness or availability claim;
- repeated readiness failure, unexpected service restart, database exhaustion, low disk,
  stale/failed backup, certificate risk or enabled-provider outage;
- mail sent to the wrong recipient, unbounded mail/provider use or unexpected public
  registration; or
- request from a pilot participant alleging security, privacy, deletion, export or
  decision-integrity harm.

An alert is not required to declare an incident. Until O03/O04 pass, a report or manual
check may be the first signal and the gap itself must be recorded in the incident timeline.

## First response

1. Create a restricted incident record with a unique identifier, detection time, reporter,
   affected environment and the facts known. Do not paste credentials, cookies, tokens,
   message bodies, raw customer payloads or full database rows into it.
2. Page the named incident commander and Security/Privacy decision-maker. If either contact
   is blank or unreachable, admission remains stopped and the release cannot claim an
   operable incident process.
3. Freeze deployment and cohort admission. For a suspected cross-tenant, credential,
   corruption/loss, unlawful-use or materially false-claim event, stop affected writes and
   access as soon as containment can be performed without destroying evidence.
4. Record the running release manifest, service/configuration fingerprints, schema revision,
   UTC time and relevant request IDs. Preserve the candidate and previous artifacts plus
   their verified checksums.
5. Set an initial severity based on plausible impact, not on the small number of reports.
   Unknown scope stays high until evidence narrows it.

## Preserve evidence safely

- Export only the minimum relevant journal window and request IDs into a root-owned,
  access-controlled incident directory. Preserve original timestamps and calculate a
  SHA-256 digest for each exported file.
- Capture service state/restart counts, listener/firewall state, readiness/schema status,
  PostgreSQL connection/capacity state and backup-check status. Prefer read-only commands.
- Do not run the application's normal workspace export as an infrastructure evidence dump:
  it creates an audit event and contains customer records. When customer content is
  necessary, the Security/Privacy decision-maker must authorize and record its scope and
  access.
- Do not modify or delete the suspected live database. If data integrity is in question,
  take the approved fresh backup and restore into a separate database under the recovery
  procedure. Keep the original isolated for investigation.
- Keep evidence out of chat, public issues and ordinary support email. Record everyone who
  receives a copy and the approved deletion date for that copy.

## Containment playbooks

### Cross-workspace access or authorization bypass

1. Stop admission and affected writes; if the boundary cannot be isolated confidently,
   stop the service through the approved operator path.
2. Preserve request IDs, audit events and the smallest relevant log window for both the
   requesting and affected workspace.
3. Do not ask a participant to reproduce a disclosure against another participant's data.
   Reproduce only in a disposable database.
4. Treat confirmed cross-workspace disclosure as non-waivable. Correct it in a new candidate,
   run the full tenant/route inventory on SQLite and PostgreSQL, obtain independent review,
   and complete notification assessment before resuming access.

### Credential, token or session exposure

1. Identify the credential class without copying its value into the incident record:
   database, SMTP, AWS backup, metrics, rate-key, user password, recovery/invitation token,
   or session.
2. Disable or revoke the exposed credential at its authority. Do not rely only on editing a
   local environment file.
3. Rotate one class at a time through the approved secret store and validate the least
   privileged path. Database, SMTP and AWS changes require their provider-side revocation;
   changing `RATE_KEY_SECRET` intentionally starts new rate buckets and needs abuse
   monitoring; user credential exposure requires session/recovery revocation.
4. Search only approved bounded logs/artifacts for the credential's fingerprint or a safe
   disposable marker. Never print the credential to prove its absence.
5. Treat any reachable-history or release-artifact credential as a release blocker even
   after rotation; remove it from distribution and complete the independent exposure review.

### Data corruption, loss or deletion failure

1. Stop writes and take a fresh verified backup unless doing so would overwrite or expire
   evidence; the backup scripts publish a new file and do not overwrite an old one.
2. Restore the selected recovery point into a new database. Verify checksum, physical
   schema, workspace/record counts and every saved-assessment replay before considering it.
3. Reapply every approved post-recovery change, especially deletion requests, from the
   independent deletion register required by D04. **That register is not implemented yet;
   no restored database may become live until D04 passes.**
4. Reconcile the restored copy with a pre-incident baseline and have Product confirm any
   intentionally lost/paused writes against the approved RPO.

### Provider, SMTP, certificate or backup failure

1. Keep the affected capability visibly unavailable. A failed provider is never a zero
   observation, falling demand or successful delivery.
2. Disable the provider path if failure is unsafe or unbounded. Do not switch to an
   unapproved provider, source or region during the incident.
3. For backup failure, stop cohort expansion when the approved RPO would be exceeded. For
   certificate risk, retain HTTPS and stop access rather than serve the application over
   plaintext.
4. Record the provider's incident/reference ID, what data it may hold and the contract
   contact used. Security/Privacy decides whether processor escalation or notification is
   required.

### False or unsupported product claim

1. Preserve the exact UI/export/support statement and the evidence state that produced it.
2. Disable or remove the affected claim/capability; do not relabel missing evidence as an
   estimate or approve a result to make the screen appear complete.
3. Identify every participant who received the statement and provide a correction approved
   by Product and Security/Privacy before the workflow resumes.

## Breach and notification decision

The Security/Privacy decision-maker owns the assessment and records, at minimum:

| Question | Required record |
| --- | --- |
| What happened and when? | Evidence-backed UTC timeline and detection source |
| Whose data may be affected? | Named data categories, participant/workspace scope and locations; use counts where identities are unnecessary |
| Was confidentiality, integrity or availability affected? | Reasoned finding for each, including uncertainty |
| Which processors or jurisdictions are involved? | Approved vendor/data map references and qualified advice where needed |
| Is notification required, to whom and by when? | Named decision-maker, legal/policy basis, decision time and approved message |
| If notification is not made, why? | Dated rationale and approving person |
| What containment and recovery occurred? | Actions, owners, timestamps and verification evidence |

No notification deadline is invented in this repository. The qualified owner must supply
the applicable duties for the approved pilot participants, data and jurisdictions. An
unknown duty is a reason to escalate and keep the affected release blocked, not a reason
to assume no notification is required.

## Recovery and return to service

Return requires all of the following:

1. The incident commander records containment and the Security/Privacy owner approves the
   breach/notification disposition.
2. Any code or configuration correction has a new immutable candidate, artifact, checksum,
   full CI evidence and independent review. An old artifact's approval does not transfer.
3. Schema/readiness, tenant denial, saved-decision replay, export reconciliation and the
   affected failure case pass in isolated staging.
4. Backup freshness/integrity passes and any restored copy passes the approved RPO/RTO and
   D04 deletion replay before service configuration can point at it.
5. The named operator executes the release smoke and observation window. Pilot users are
   admitted only after the recorded recovery decision permits it.

## Data access, export and deletion requests

1. Receive requests only through the approved secure contact. Record a request ID, receipt
   time, request type, workspace, verification method, assigned owner and target response
   date; do not place a password, token or unnecessary record content in the log.
2. Verify the requester's authority through an approved channel before disclosing or
   deleting data. A signed-in owner may export the workspace through the product, but that
   does not authorize disclosure to a different address or support contact.
3. Identify every applicable store from the approved data inventory: live PostgreSQL,
   audit, journal/nginx, mail/provider, backup copies and incident evidence. “No data” is a
   finding only after each applicable store was checked.
4. For access/export, generate the minimum authorized export, record its schema/counts and
   deliver it through the approved secure channel. Record delivery without retaining an
   uncontrolled extra copy.
5. For correction, record the requested correction and Product/domain disposition. Saved
   assessments remain immutable; corrections create new evidence/assessment versions and
   do not rewrite history silently.
6. For live workspace deletion, follow the owner-authenticated product flow and record the
   request in the independent D04 register before deletion. Backups expire under the
   approved schedule rather than being rewritten. If D04 is not operational, deletion
   replay after restore is not assured and the pilot remains blocked.
7. Close the request only after the owner and Security/Privacy reviewer record the outcome,
   response time, stores checked, exceptions/basis and any follow-up date.

### Data-request log template

| Request ID | Received UTC | Type | Verified requester/workspace | Stores in scope | Owner | Target date | Outcome/delivery | Closed UTC | Privacy review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **No requests recorded — template only** |  |  |  |  | **PENDING** |  |  |  | **PENDING** |

The operational request log must be access-controlled and stored outside public source
control. This empty template demonstrates fields only; it is not evidence that no external
request has ever been received.

## Tabletop and review record

Complete at least these scenarios with someone other than the runbook author:

1. cross-workspace read reported with one request ID;
2. exposed SMTP or backup credential requiring provider-side revocation;
3. restore to a point before a participant's workspace-deletion request;
4. stale backup plus unreachable alert owner; and
5. a support claim presenting unavailable evidence as a favorable market result.

| Field | Required value |
| --- | --- |
| Runbook version/commit | **PENDING** |
| Participants and roles | **PENDING** |
| Scenario/date (UTC) | **PENDING** |
| Detection and page time | **PENDING** |
| Containment decision/time | **PENDING** |
| Evidence preserved and access list | **PENDING** |
| Breach/notification decision-maker and result | **PENDING** |
| Recovery checks and time | **PENDING** |
| Gaps, owners and due dates | **PENDING** |
| Security/Privacy approval | **PENDING** |
| Operations approval | **PENDING** |
