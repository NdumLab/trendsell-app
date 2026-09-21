# Owner acceptance requests — templates

Prepared 21 September 2026 UTC.

[`2026-09-20-owner-appointment.md`](2026-09-20-owner-appointment.md) has three rows at **Proposed**:
Security / Privacy, Operations / Support, and the independent reviewer. Proposed means Henry Ndum
intends to ask someone. It is not their acceptance, and 38 `H` gates plus the reviewer gates stay
blocked until each person confirms.

This page holds the messages that ask them. **No names appear here**, for the same reason the
appointment page carries none: this repository is public, and naming a private individual in a role
they have not confirmed is a publication that cannot be retracted. The name-filled copies are in
`/etc/trendsell/owner-acceptance-requests.md`, mode 0600.

## What acceptance has to produce

A gate that requires a named accountable owner needs a name, a UTC date and a reference. So each
message asks for a reply in a fixed form, which can be pasted into the record verbatim:

> I, **[full name]**, accept the **[role]** role for the TrendSell controlled pilot as described in
> your message of **[date]**. I **[do / do not]** consent to my name and this role being recorded in
> the public TrendSell repository. Date (UTC): **[YYYY-MM-DD]**.

Two separate consents, deliberately. Accepting the role and agreeing to be named publicly are
different decisions, and someone may reasonably do the first and not the second.

- **Accepts and consents to publication** — the name and date go into the appointment table, and
  gate evidence cites that file by commit.
- **Accepts, declines publication** — the acceptance is recorded in `/etc/trendsell` instead, and the
  public row reads *Accepted, holder recorded out of tree*. This still satisfies the gates that need
  an accountable person, because what they require is a person who has accepted and is recorded, not
  a person who is published. It is weaker for the **independent reviewer**, where attributability is
  much of the point — see that message.
- **Declines** — the row returns to *Not appointed* and the name is removed from the 0600 file.
- **No reply** — the row stays *Proposed*. Silence is not acceptance and never becomes acceptance.

## Before any of this can be sent

**No contact address exists for any of the three.** That is the actual first blocker: the messages
below cannot be delivered until Henry supplies a way to reach each person. Any channel is fine —
email, WhatsApp, in person — provided the reply is preserved verbatim with its date, because the
reply is the gate evidence. An acceptance relayed from memory is not a record.

Do not shorten these messages to "can you be the security guy". Each person is being asked to be
accountable for a decision about a live system, and the message has to say what that means, what it
costs them, and that no is a complete answer.

---

## Message 1 — Security / Privacy

**Subject:** Asking you to take the Security & Privacy role on TrendSell — you can say no

[NAME],

I've written your name down as the proposed Security & Privacy owner for TrendSell. I want to be
straight about what that is: it was my decision to ask you, not your agreement to anything. Nothing
is in force, nothing is relying on you today, and if you say no the project is exactly where it was.

TrendSell is a tool for deciding whether a product is worth importing from China to Nigeria, based on
dated evidence rather than guesses. It is running at trendsell.yerikasystems.com, but registration is
closed, no outside data source is connected, and the planned pilot is at most five named people.

The role is: **who may reach what, and what is kept.** You would be the person who approves, and is
recorded as approving — secret storage, rotation and emergency revocation; traffic limits; who can
read the logs and for how long they are kept; production and support access, MFA and what happens
when someone leaves; the incident and data-request procedure; the map of what personal data the
deployed system holds; the terms of the mail and backup providers; how a lawful request for data is
handled; the published privacy notice; the retention schedule; what the evidence providers allow us
to do with their data; and the participant terms and appeal route.

Most of these already exist as written drafts. The work is reading a proposal and saying yes, no, or
change this — not writing them from scratch.

**What this is not:** it is not a security audit. There is a separate requirement for a qualified
security reviewer to test the system properly, which is a paid appointment I would arrange
separately. You are not being asked to do that, and accepting this role does not sign you up for it.

**The public part.** The repository is public. If you accept and agree to be named, your name and
this role go into a file anyone can read, permanently — it can be copied and forked, so it cannot be
taken back later. You can accept the role and decline to be named; the acceptance is then kept in a
restricted file on the server and the public page says the holder is recorded privately. Please
treat that as a real option rather than a fallback.

If this is more than you want, say no. It is genuinely useful to know now rather than in a month.

To accept, reply with:

> I, [full name], accept the Security / Privacy role for the TrendSell controlled pilot as described
> in your message of [date]. I [do / do not] consent to my name and this role being recorded in the
> public TrendSell repository. Date (UTC): [YYYY-MM-DD].

Henry

---

## Message 2 — Operations / Support

**Subject:** Asking you to take the Operations & Support role on TrendSell — you can say no

[NAME],

I've put your name down as the proposed Operations & Support owner for TrendSell. That was me
deciding to ask you; it is not your agreement, and nothing is in force until you say so. No is a
complete answer.

TrendSell is a tool for deciding whether a product is worth importing from China to Nigeria. It is
live at trendsell.yerikasystems.com with registration closed, and the planned pilot is at most five
named people.

The role is: **what happens when it breaks, and who answers.** You would approve, and be recorded as
approving — the service targets and the thresholds at which we stop or roll back; the support window
and what counts as a timely response; who can see the monitoring and how long it is kept; where
alerts go, who receives them and how their credentials are handled; the named support contact and
escalation route; budgets and quotas before anything can run up a bill; the mail provider and sender
address, or the manual fallback if we do not use one; proof that backups are landing and that a
failure actually raises an alarm; and how much data loss and downtime is tolerable.

**Be aware this one has an ongoing commitment, not just approvals.** Being the named support contact
means being reachable in an agreed window and being the person an alert wakes up. The current
proposal is a maximum of 30 hours of data loss and 4 hours to restore service, with intake paused if
either cannot be met. Those are proposals, not decisions — if they are not commitments you want to
carry, say so and we change the targets or the role goes to someone else. Agreeing to numbers you
cannot actually meet is worse for me than you declining.

**The public part.** The repository is public. If you accept and agree to be named, your name and
role are published permanently and cannot be retracted, because the repository can be copied and
forked. You can accept the role and decline to be named — the acceptance is then recorded in a
restricted file on the server, and the public page says so. That is a real option.

To accept, reply with:

> I, [full name], accept the Operations / Support role for the TrendSell controlled pilot as
> described in your message of [date]. I [do / do not] consent to my name and this role being
> recorded in the public TrendSell repository. Date (UTC): [YYYY-MM-DD].

Henry

---

## Message 3 — Independent reviewer

**Subject:** Asking you to independently review TrendSell before it takes real users

[NAME],

I am asking whether you would act as the independent reviewer for TrendSell before it is allowed to
take real users. As with the others: I wrote your name down, that is not your agreement, and nothing
is in force until you say so.

This role exists precisely because the person who wrote the code should not be the person who
certifies it. I checked the repository history and there is no commit authored by you, which is what
makes you eligible. That is a fact about you, not a commitment from you.

**What you would be reviewing.** One pull request: 53 commits, 305 files, about 33,900 added lines,
of which roughly 12,600 are backend code. I am not asking you to read every line. I am asking for
dated, written findings on specific questions — whether one customer's data can leak into another's,
whether authorization is actually enforced, how credentials and passwords are handled, whether the
database migrations are safe, whether account recovery can be abused, whether concurrent use corrupts
anything, whether saved decisions remain reproducible, and whether what the product claims on screen
matches what it actually does. You would also be checking that the features we say are switched off
really are unreachable, and that the operational drills get run by someone other than the author.

**I am not asking you to approve it.** A review that records problems, or that declines to sign off,
is the review working. If part of it is outside what you can judge, writing that down is a valid and
useful finding. The one outcome that would be worth nothing to me is a yes that does not mean
anything — I would rather hear that it is not ready.

**Honest about the cost.** This is the largest of the three asks. A real review of a change this size
is days of work, not hours, and I am not able to pay for it. If that is not realistic, please say so.
A narrower review with its limits stated plainly is worth considerably more to me than a broad one
that quietly skipped things.

**The public part.** The repository is public, so your name and this role would be published
permanently and cannot be withdrawn afterwards. You can accept and decline to be named, and the
acceptance would be kept in a restricted file instead — but I should be honest that for this role in
particular, being named is much of the value. The point of an independent review is that someone
identifiable put their name to it. If you would rather not be named, I would want to talk about what
the review can honestly claim before we start, rather than discover the problem at the end.

To accept, reply with:

> I, [full name], accept the independent reviewer role for the TrendSell controlled pilot as
> described in your message of [date]. I [do / do not] consent to my name and this role being
> recorded in the public TrendSell repository. Date (UTC): [YYYY-MM-DD].

Henry

---

## Handling the replies

1. Keep the reply verbatim, with its date and the channel it arrived on. That text is the evidence.
2. Record acceptance in the appointment table, or in `/etc/trendsell/owner-appointments.md` where
   publication was declined, and commit the change so gates can cite it by commit.
3. Do not mark a row Accepted on a verbal yes that has not been written down. The whole point of the
   register is that an approval is attributable and dated.
4. A person who accepts has not thereby approved anything else. Each gate still needs its own dated
   decision from them — accepting the Security / Privacy role is not approval of the retention
   schedule.
