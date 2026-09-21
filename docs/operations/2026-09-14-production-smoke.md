# Production smoke evidence — 14 September 2026

Target: `https://trendsell.yerikasystems.com`, schema `0006_workspace_invitations`.
Credentials were loaded from root-only `/etc/trendsell/smoke-identities.env`; no password or
bearer token was written to this artifact, source control, command output or application logs.
A fresh checksummed offsite backup completed immediately before the exercise.

The following checks passed against the dedicated disposable smoke workspace:

* owner, reviewer and viewer authenticated and resolved to the expected role in one workspace;
* the owner created and confirmed one disposable investigation while the viewer could read it
  but received 403 when attempting to write;
* the owner requested a disposable compliance review and a different reviewer rejected it;
* the owner exported the workspace while reviewer export and viewer audit access received 403;
* an invitation sent through production SMTP to Resend's official `delivered@resend.dev` test
  recipient was accepted, changed to viewer, revoked, and immediately lost its session;
* a second invitation reactivated the same suspended identity;
* a production recovery request created a reset credential, reset invalidated the active session,
  and the replacement password authenticated; and
* all three disposable domain records and the temporary member were removed. The protected
  owner/reviewer/viewer identities remained active, with zero domain records and zero sessions.

Limitation: the installed Resend key is deliberately send-only. It returned 401 for the sent-email
list API, so automation could not retrieve the actual message body. SMTP acceptance was exercised,
but the one-way invitation and recovery hashes were replaced with fresh in-memory test-token hashes
before redemption. This proves application issuance, SMTP acceptance, redemption and revocation,
but not a human opening the delivered message. Bounce/failure alert delivery also remains open.
