# Installed deployment layout does not match the release tooling

Prepared 19 September 2026 UTC against candidate `d15ff395c8c437c2a6f5c3277577bdc9065c4052`.
This is a finding record, not an approval or a production change. Production was inspected
read-only; nothing was deployed, migrated, restarted or rolled back to produce it.

## What was inspected

The repository working host is also the production host. `/opt/trendsell` was read directly
rather than inferred from documentation.

## Installed state

| Fact | Observed value |
| --- | --- |
| Application root | `/opt/trendsell/backend`, with sibling `contracts/`, `deploy/`, `docs/`, `scripts/` |
| Service unit | `WorkingDirectory=/opt/trendsell/backend` |
| Interpreter | `ExecStart=/opt/trendsell/venv-ae3742d/bin/uvicorn`, `127.0.0.1:8021` |
| Deployed commit | `RELEASE.json` → `d15ff395c8c437c2a6f5c3277577bdc9065c4052` |
| Previous commit | `RELEASE.json.pre-d15ff395-20260919T005744Z` → `90d6312b6fa0d3a48361788194af760e4ff2cd78` |
| Version stamp | `.trendsell-version` → `d15ff395 ci-35409486282 2026-09-19T00:57:44Z` |
| Rollback artifact | `backend.pre-d15ff395-20260919T005744Z` and one `.pre-` sibling per deployed directory |
| Service state | `active`, started 2026-09-19 01:02:09 UTC, `/api/ready` → 200 |

## Divergences

1. **Activation target.** `scripts/deploy_release.sh` activates `/opt/trendsell/current` and
   `/opt/trendsell/previous` symlinks over `/opt/trendsell/releases/<commit>`. None of these
   paths exist. The unit loads `/opt/trendsell/backend` directly, so switching those links
   changes nothing the service reads.
2. **Interpreter.** The script defaults migrations to `/opt/trendsell/venv/bin/python`. The
   service runs from `/opt/trendsell/venv-ae3742d`. Both directories exist, so migrations
   would have run against a different installed dependency set than the application serves.
3. **Unversioned deploy mechanism.** No script in this repository writes the `.pre-<commit>-<ts>`,
   `.staging-<commit>-<ts>`, `.trendsell-version` or flat-directory convention the host uses.
   The procedure that produced the running installation is not under version control and
   cannot be reviewed, tested or re-executed from the repository.
4. **Contradictory version sources.** `/opt/trendsell/.git` is a checkout of branch
   `redesign/evidence-platform` at `03744d3` with a dirty working tree, while `RELEASE.json`
   records `d15ff395` from `impl/evidence-platform-phase0`. Two on-host sources disagree about
   what is installed; `RELEASE.json` matches the deployed files and the CI run.

## Consequence

Before this finding, an operator following `docs/RUNBOOK.md` step 6 on this host would satisfy
every approval, backup and commit latch, **migrate the production database**, stage a release
into an unused directory tree, switch links nothing reads, restart onto unchanged application
code, observe a passing readiness probe and be told the deployment succeeded. The documented
readiness-failure path would then "roll back" by switching the same unread links.

The forward path and the rollback path were both inoperative, and neither failed loudly.

## Change made under this finding

`scripts/deploy_release.sh` now refuses to run when the installed unit does not load what the
script activates, or when the service and its migrations resolve to different interpreter
directories. Both checks read the running unit rather than a documented assumption, and both
run before staging, migration or restart. Verified against this host: the layout check refuses,
the interpreter check refuses independently, and a matching layout proceeds.

This makes the mismatch loud. It does not make the host deployable by this script.

## Gate impact

`R06`, `I03` and the rollback element of the recovery gates cannot pass on the current
installation, and prior runbook-based rollback confidence is withdrawn. `docs/RUNBOOK.md`
steps 6 and 7 are not executable as written on this host and are corrected in the same commit.

## Open decision

Reconcile in one of two directions. This requires a named Engineering/Platform owner:

* **Move the host to the tooling.** Restructure `/opt/trendsell` to `releases/<commit>` with
  `current`/`previous` symlinks and repoint the unit. `release_manager.py` already implements
  and tests atomic activation and rollback. Cost: one production restructure and restart,
  rehearsed in staging first. Recommended — it is the only option that yields an atomic,
  already-tested activation and a real rollback target.
* **Move the tooling to the host.** Implement flat activation with `.pre-<commit>` restore in
  `release_manager.py`. Cost: writing and proving a new production-mutating path that cannot
  be atomic, because a directory swap is several operations.

Neither may be applied to production before the staging gate (`I04`) has a named owner and host.
