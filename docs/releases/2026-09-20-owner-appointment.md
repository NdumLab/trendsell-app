# Accountable owner appointment — PARTIALLY RECORDED

Prepared 20 September 2026 UTC; first rows recorded the same day.

**Only the rows marked Accepted are in force.** A row marked Proposed names a person who has not
yet confirmed to this record that they accept the role. Henry Ndum proposing a colleague is Henry's
decision to ask them; it is not their acceptance, and it does not satisfy any gate that requires a
named accountable owner. Silence does not appoint anyone, and being named by someone else is
silence.

## Why this page is the first thing

Of the 60 blocked release gates, **38 cannot move until these rows are filled in.** Almost every
one reads "a named owner approves…". They are not waiting on code, budget or infrastructure. They
are waiting on a person who will accept a decision and be recorded as having accepted it.

One person may hold several roles. **The same person may hold all four.** The only genuine
separation requirement is the independent reviewer, who must not be the author of the change under
review.

## The rows

| Role | Full name | Contact | Status | Date (UTC) |
| --- | --- | --- | --- | --- |
| Product | Henry Ndum | admin@yerikasystems.com | **Accepted** | 2026-09-20 |
| Engineering / Platform | Henry Ndum | admin@yerikasystems.com | **Accepted** | 2026-09-20 |
| Security / Privacy | *withheld pending acceptance* | — | Proposed by Henry Ndum | 2026-09-20 |
| Operations / Support | *withheld pending acceptance* | — | Proposed by Henry Ndum | 2026-09-20 |
| Independent reviewer (not the change author) | *withheld pending acceptance* | — | Proposed by Henry Ndum | 2026-09-20 |

Henry Ndum holds Product and Engineering / Platform by elimination: the two roles he did not
assign to someone else. If he intended a different split, this table is wrong and should be
corrected before any gate cites it.

Three people have been proposed: two for Security / Privacy and Operations / Support, and one for
the independent reviewer. Their names are **deliberately not published here yet**, for two
reasons: none has confirmed acceptance to this record, and this repository is public, so recording
a private individual's name and role is a publication that cannot be retracted later. The names
are held in `/etc/trendsell/owner-appointments.md`, outside the tracked tree, and will be entered
here once each person confirms they accept the role and are content to be named publicly.

The independent reviewer row now has a proposed holder, named by Henry Ndum on 20 September 2026
and recorded outside this repository. The row is **Proposed, not Accepted**, so `R04`, `R05`,
`O05` and the exclusion verifications remain blocked exactly as before. Nothing about this
appointment is in force until that person confirms acceptance to this record.

The independence requirement is satisfiable by this candidate: the proposed reviewer is not
Henry Ndum, and `git log` shows no commit in this repository authored by them, so they are not the
author of the change under review. That is a fact about the candidate, not an acceptance.

## What each role is accepting

**Product** — what the pilot is and what it promises. Cohort and invitation scope (`A01`), the
participant agreement and comprehension protocol (`T02`), decision methodology, corridor, formulas
and stated blind spots (`T05`), the claim inventory across UI, API, export and any external wording
(`T01`, `T07`), supported browsers and devices (`F07`), the accessibility target (`F08`), load and
success targets (`I05`), the import-review exclusion (`T04`), dated Nigeria domain claims or their
removal (`T08`), and the commercial-exclusion confirmations (`C01`–`C05`).

**Engineering / Platform** — how it is built, deployed and recovered. Staging topology and funding
(`I04`), the deployment reconciliation direction recorded on the 16 September decision sheet,
database role split and privilege evidence (`I02`), installed-host install, restart and reboot
(`I03`), the supported-component patch owner and cadence (`S04`), environment values and a redacted
installed-environment review (`I01`), and the installed-topology review that the 19 September
divergence finding already supplies evidence for (`R06`).

**Security / Privacy** — who may reach what, and what is kept. Secret storage, rotation and
emergency revocation (`S01`), traffic thresholds (`S06`), log access and numeric retention (`S07`),
production and support access, MFA and offboarding (`S10`), the incident and data-request procedure
(`S11`), the deployed data map (`P01`), vendor terms for Resend and S3 (`P06`), lawful-request
handling (`P07`), the published privacy notice (`P02`), the retention schedule (`P03`), provider
rights for research, display, derived metrics and retention (`P04`), and participant terms,
prohibited use and the appeal route (`P05`).

**Operations / Support** — what happens when it breaks, and who answers. SLOs, stop and rollback
thresholds and the support window (`O01`), monitor access and retention (`O02`), alert destination,
recipients and credential handling (`O03`), the end-to-end alert drill (`O04`), the named support
contact, hours, response target and escalation (`O06`), budgets and quotas before any vendor cost
alert is tested (`O07`), mail provider and sender or the operator-recovery fallback (`A02`/`A03`),
backup destination proof and failure alerting (`D02`), and RPO/RTO with representative scale
(`D01`/`D03`).

**Independent reviewer** — the person who checks work they did not produce. The exact candidate
diff with dated findings (`R04`, via pull request #1), risk dispositions (`R05`), verification that
excluded capabilities really are inaccessible and unpromised (`T01`, `T04`, `T07`, `D06`, `C01`,
`C03`, `C04`), and the drills that `O05` requires be run by an operator other than the author.
A qualified security reviewer for `S09` is a separate appointment and is expected to cost money;
it is deliberately not bundled into this row.

## Commit attribution — resolved

The repository git identity is now `Henry Ndum <admin@yerikasystems.com>`. Commits from
20 September 2026 onward are attributable to a person. Commits before that remain authored
`root <root@srv1753392.hstgr.cloud>` and are not retrospectively attributable; history was not
rewritten, because rewriting published history to manufacture attribution would be worse than
recording the gap.

A contact telephone number was supplied for Henry Ndum and is **deliberately not recorded here**.
This repository is public, and a personal telephone number in published release documentation is
not retractable. Operational contact details belong in the `/etc/trendsell` configuration or an
access-controlled operations record, not in the tracked tree.

## How this becomes real

Fill in the rows, record the UTC date each person accepted, and commit it. Gate evidence then cites
this file by commit. Until then every `H` gate remains blocked, correctly.
