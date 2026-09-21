# Candidate `3478c98` — re-earned gate confirmations

Prepared 21 September 2026 UTC.

The 19 September reattachment withdrew every prior PASS: nine gates had been earned against
`ddde69a`, and `backend/` had changed by 2,593 insertions and 236 deletions since. Those nine were
carried as *unverified*, not as passing. This record re-executes them against the current candidate
and records the result.

**It closes no blocker.** All 60 blocked gates stay blocked, with the same class split
(`E` 16, `H` 38, `N` 6). Nothing here is an independent review, an owner appointment, a provider
account or a production change. The nine gates below are the ones that needed neither a named human
nor a new environment — only someone to run them against the right commit. That is now done, so the
remaining queue is entirely human- and access-blocked.

## Candidate

| Item | Value |
| --- | --- |
| Candidate | `3478c9891c79d01ef3d08535d810aa92830f5ebd` |
| Branch | `impl/evidence-platform-phase0`, pushed, head of pull request #1 |
| Working tree | Clean (`git status --porcelain` empty) |
| Remote CI | Run [35554333213](https://github.com/NdumLab/trendsell-app/actions/runs/35554333213), all seven jobs success, 2026-09-21T02:29Z |
| Artifact | `trendsell-3478c9891c79.tar.gz`, SHA-256 `d2117dd6c78c5ce99d4e968d63f6594c5f25e69b7f9b3c0344afdabbe2d7ea1d` |

`3478c98` is the first commit on this branch that CI has ever run against. The three commits before
it were pushed only as far as `024929a`; the candidate itself was committed locally on 20 September
and left unpushed, so no CI evidence for it existed until this pass.

### Code identity with `e954830`

Everything between `e954830` and `3478c98` is documentation. Compared as git tree objects, the five
code paths are the same objects, not merely equivalent files:

| Path | Tree object at both `e954830` and `3478c98` |
| --- | --- |
| `backend` | `a55edbca2b09bb40411fd86839280686dbf15bc7` |
| `frontend` | `2ec81aa0ef9f5fdc9cc24b233d214158afcb5f5c` |
| `contracts` | `6dc3b32e79e01e6303512697c202b9af5ad105d4` |
| `scripts` | `a7012336898b09356567439a744d92669bf3134d` |
| `deploy` | `98b306d5622ed0695fb909d7305ab1f22f9ee327` |

This is the stated reason `F05` carries rather than being re-run. The register's rule is that prior
results do not transfer "where the changed code or environment matters"; here the code did not
change at all.

## Gate evidence

### `R01` — clean, reviewable candidate

Working tree clean; candidate pushed and identified as the head of pull request #1. The CI
clean-clone job's "Every source file the app imports is tracked" step passes, which checks that
`frontend/src/lib`, `frontend/src/shared`, `frontend/src/features`, `backend/app` and `contracts`
are all tracked and that no `.env` file is tracked. This document is the release note.

One untracked file is load-bearing for local testing and is deliberately not tracked:
`backend/.env` supplies `TEST_POSTGRES_URL`. See the note on the local baseline below.

### `R02` — reproducible artifact

The clean-clone job built `trendsell-3478c9891c79.tar.gz` twice from a fresh clone and compared the
two byte for byte with `cmp`; the checksum sidecar verified in the job. The published artifact was
then downloaded here and its SHA-256 re-verified independently of CI:
`d2117dd6c78c5ce99d4e968d63f6594c5f25e69b7f9b3c0344afdabbe2d7ea1d`. Its embedded `RELEASE.json`
pins `"commit": "3478c9891c79d01ef3d08535d810aa92830f5ebd"` with
`"source_date_epoch": 1789870801`, so the artifact identifies the exact candidate rather than a
build of unknown provenance.

### `R03` — remote CI on the exact SHA

All seven required jobs succeeded for `3478c98` in run 35554333213:

| Job | Result |
| --- | --- |
| Backend tests (SQLite) | 595 passed, 17 skipped |
| Backend tests on PostgreSQL | 612 passed, plus the separate migration/runtime role privilege exercise |
| Frontend type-check, tests and build | success |
| Browser tests | 54 passed |
| Clean clone builds | success |
| Secret scan | success |
| Dependency and license scan | success |

The 17 SQLite skips are the PostgreSQL-only cases; they run in the PostgreSQL job, which is why its
count is 612 against the same collection.

### `F02` — tenancy and role boundaries

68 tests across `test_tenant_isolation.py`, `test_auth_and_tenancy.py` and
`test_permissions_and_audit.py` pass locally against PostgreSQL, and the whole suite passes against
PostgreSQL in CI.

### `F03` — retry and concurrency convergence

8 tests in `test_concurrency.py` pass locally against PostgreSQL and in the PostgreSQL CI job. These
are the cases that reproduce the originally reported 500 against the pre-fix code.

### `F04` — immutability, lineage and replay

199 tests across `test_contract_parity.py`, `test_evidence_contract.py`,
`test_identifier_contract.py`, `test_decisions_and_records.py` and `test_assessment_visibility.py`
pass locally against PostgreSQL and in the PostgreSQL CI job.

### `F05` — migration, restart and readiness

Carried from the 20 September exercise against `e954830` on the tree-object identity recorded above,
not re-run. Evidence remains [`2026-09-20-f05-closure.md`](2026-09-20-f05-closure.md).

### `F06` — staged negative and dependency-fault exercise

Re-executed here against the downloaded exact artifact, because this gate is a runtime exercise
rather than a test run and the previous one was performed against `ddde69a`.

Setup: the unpacked artifact, a virtual environment built only from the artifact's own
`backend/requirements.lock` (confirmed to exclude pytest), a disposable PostgreSQL 16.4 container on
a dedicated port, and a local socket that completes the TCP handshake on the SMTP port and then never
sends a greeting. The service ran in `APP_ENV=production` under the deployment template's exact
command line: `uvicorn app.main:create_app --factory --workers 2 --proxy-headers --no-access-log`.
It migrated to `0006_workspace_invitations` and reported `/api/ready` ready with
`schema_matches_models: true`.

Production configuration refused two setups before accepting one, which is itself evidence the
validation works: open registration is rejected under the controlled-pilot tier, so the probe
account was seeded out of band rather than registered.

| Probe | Outcome |
| --- | --- |
| Malformed request body | 422 |
| Unauthorized workspace read | 401 |
| Oversized body, declared `content-length` | 413, refused before any body was uploaded |
| Oversized body, chunked with no declared length | 413 |
| Password reset for a real account through the deaf SMTP socket | 202 after 15.060 s |

The deaf listener logged the accepted connection, so the 15-second result is a genuine transport
timeout rather than a refused connection. The 202 response wording stayed conditional on delivery
succeeding — "If that address has a workspace and delivery succeeds" — so a delivery outage does not
become an account-existence oracle. The failure was recorded as a typed warning,
`"recovery mail undelivered"` with `"error_type": "SMTPServerDisconnected"`, carrying no address.

Log leakage scan over everything the service emitted during the exercise: the disposable address,
the disposable password, the rate-key secret and the operator metrics token each appear **0** times.
Both oversized requests logged `"route": "<unmatched>"` rather than a raw path.

The exercise was then torn down: service stopped, listener killed, container removed, ports 2526 and
8039 free. The production database container `trendsell-db` was never contacted.

### `S08` — dependencies, credentials and licenses

| Check | Result |
| --- | --- |
| `pip-audit --strict` on `backend/requirements.lock` | No known vulnerabilities (local and CI) |
| `pip-audit --strict` on `backend/requirements-dev.lock` | No known vulnerabilities (local and CI) |
| `npm audit --audit-level=high` | clean in CI |
| Credential scan, tracked files and reachable history | passed |
| Credential scan, unpacked release artifact | passed |
| Dependency license policy | passed for 181 locked packages |

## Result

| | Count |
| --- | ---: |
| Confirmed PASS for `3478c98` | **9** |
| Blocked | 60 |
| Total mandatory gates | 69 |

The nine are `R01`, `R02`, `R03`, `F02`, `F03`, `F04`, `F05`, `F06` and `S08` — the same nine gate
IDs that passed for `ddde69a`. The candidate has not gained a gate; it has re-earned the ones it was
carrying unverified. The confirmed count moves from 1 to 9 because `F05` alone had been re-executed
before this pass.

**No blocked gate moved, and none could have.** Every one of the 60 needs a named accountable owner,
a provider account or credential, an approved environment, or an exercise performed by someone other
than the change author. The engineering-side verification queue for this candidate is now empty.

## Note on the local test baseline

Locally the suite reports 612 passed with no skips, against CI's 595 passed and 17 skipped, because
`backend/.env` sets `TEST_POSTGRES_URL`. That points at `trendsell-test-db` on port 55433, database
`trendsell_test` — a container separate from production `trendsell-db` on port 55432. Each test
creates and drops its own schema inside it. The local run is therefore PostgreSQL-backed and
equivalent to the CI PostgreSQL job, and no local test run has ever touched the production database.
Anyone re-running this should confirm that port before trusting the count.

## Branch head after this record

Committing this record moves the branch head past `3478c98`, which is the same condition that left
the candidate unevidenced in the first place. It does not create a new code candidate, and the rule
that decides this is the one applied to `F05` above.

**The code candidate is the most recent commit whose code tree objects differ.** A documentation
commit leaves `backend`, `frontend`, `contracts`, `scripts` and `deploy` pointing at the same git
tree objects, so it does not produce a new artifact and does not invalidate evidence attached to the
commit before it. Verify rather than assume, for any later head:

```bash
for p in backend frontend contracts scripts deploy; do
  [ "$(git rev-parse 3478c98:$p)" = "$(git rev-parse HEAD:$p)" ] \
    && echo "$p identical" || echo "$p CHANGED — new candidate required"
done
```

Read `R01`'s "head of pull request #1" accordingly: it was literally true when this record was
written, and remains true of the code under review while every path above reports identical. As soon
as one reports `CHANGED`, the nine confirmations stop applying and must be re-earned against the new
SHA, exactly as this pass re-earned them. The one gate that then needs real re-execution rather than
a re-run of the suites is `F06`, because it is a runtime exercise against the built artifact.
