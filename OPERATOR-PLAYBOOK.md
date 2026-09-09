# Operator Playbook

How a campaign actually gets run, start to finish, in the order it happens.

`PLAYBOOK.md` is the rules — the things that outrank convenience. This is the
sequence. Where the two disagree, `PLAYBOOK.md` wins.

**Steps 14 onward are disabled in this build.** Everything up to and including
approval works today and costs nothing beyond enrichment credits. Sending does
not exist yet: `push.run(live=True)` raises. Each step below says which side of
that line it is on.

---

## The line

| Steps | State |
| --- | --- |
| 1–13 | **Work today.** Offline except where a step says it spends credits |
| 14 | **Disabled.** Gated by `GO-LIVE-CHECKLIST.md` |
| 15–18 | **Built, never run live.** The machinery exists; nothing feeds it |

---

## 1. Create the workspace

**Works today.** Super admin, `/admin`.

A workspace is the tenancy boundary. One client, one workspace, one set of
members. Everything after this is scoped to it, and nothing you do inside it
can reach another one.

Then open `/onboarding`. That screen is this playbook's first half, checked
against stored state, and it tells you which step is next.

## 2. Configure the ICP

**Works today.** `/settings`, and the client's YAML in `config/clients/`.

Market rule, size band, geographies, personas, angles. Workspace-level
overrides live in `workspaces.jsonl` and are edited on the settings page;
structural things live in the client config.

This is the step that decides what qualification will do, and qualification is
what stops person-level credits being spent on companies that were never a
fit. Getting it approximately right here is worth more than any optimisation
later.

## 3. Configure senders

**Works today.** `/senders`.

Three separate things, and keeping them separate is the point:

- **human identities** — real people who will appear as the sender
- **email accounts** — inboxes, many per person
- **LinkedIn accounts** — profiles, usually far fewer

Then pair them. A pairing says "Anna sends the email, Petar sends the
LinkedIn" for the same prospect, which is the shape most agencies actually
run.

Set capacity where you know it. Where you do not, leave it unknown — the
system reports "no known limit" rather than assuming one, and a guessed limit
is how a sending account gets burned.

## 4. Upload domains

**Works today.** `/upload`. Free.

A CSV of domains. 5,000 is a normal batch. The upload normalises, deduplicates
and reports invalid rows before anything is committed; you see the preview and
confirm.

## 5. Qualify

**Works today. Free.** `/icp`.

Company-first. Every company gets an explicit ICP verdict — qualified,
rejected, review or unknown — from stored evidence, with the criteria shown.

**No paid person-level call happens before this.** Rejected, review and
unknown all mean zero person credits.

## 6. Enrich

**Spends credits.** `/jobs`.

ContactOut first. A paid fallback needs an accepted reason; one without a
reason is refused. Every paid call goes through `enrich.spend()`, which writes
the waterfall ledger — a provider call that skips it is invisible to the spend
audit.

Cap before you fan out. The cap is on the job.

## 7. Verify

**Spends credits.** `/jobs`.

Two independent providers on every address. Where they disagree, the contact
is **held** for a person rather than sent to on a guess. Where a second
opinion is needed, Reoon escalates.

Held is not a failure. It is the system declining to guess, and the held count
on a dashboard is a feature.

## 8. Screen MX and email security

**Works today. Free, and it runs before verification.** `/companies`.

Barracuda, Proofpoint, Mimecast, Cisco/IronPort, Trend Micro, Sophos are
classified and filtered per policy. Google and Microsoft are never blocked —
they are mailbox hosts, not gateways.

A blocked gateway moves a contact to LinkedIn-only. It never drops them, and
it never costs a verifier credit.

## 9. Segment

**Works today. Free.** `/segments`.

Vertical, subvertical, industry, size band, country, region, timezone, ICP
tier, persona. Drill into any of them.

## 10. Build the campaign

**Works today.** `/campaigns/new`.

Audience, personas, geography, channels, sender strategy, cadence,
personalisation, research. Each stage validates and explains what is blocking
it.

## 11. Inspect the outreach

**Works today, and this is the step most worth your time.** `/outreach`.

The full cadence per contact, chronologically: which day, which channel, which
human, which inbox, what the copy says, and what evidence it rests on.

Read the cross-channel handoffs. "My colleague Anna emailed you earlier this
week" is only allowed where Anna's email is a **confirmed** touch. A planned
step, an approved step and a built payload are all refused, and the screen
tells you which.

Never label planned work as sent. The product will not; do not do it in your
own head either while reading this screen.

## 12. QA

**Works today. Free.** Automatic on build; visible on the campaign.

Lint every draft, both channels, through one door. A BLOCK verdict is never
averaged away by a good score.

**Never widen a lint rule to make a draft pass. Regenerate the draft.**

## 13. Approve

**Works today.** `/approvals`.

A reviewer sees the audience, the sender strategy, the QA verdicts, the held
counts and the credit exposure, and approves, rejects or holds.

The approval binds to a **fingerprint** of the launch-sensitive state. Change
the campaign and the approval goes stale, visibly — an approval is permission
for *this* content, not for the campaign as a name.

## 14. Launch — **DISABLED**

`push.run(live=True)` raises `LiveSendNotEnabled`. Nothing in the app can turn
that off.

Enabling it is `GO-LIVE-CHECKLIST.md`: every gate signed by two people, then
one campaign at the smallest useful volume, watched for a working day.

## 15. Ingest replies — **built, nothing feeds it**

`src/inbound.py` handles a reply end to end. What does not exist is a process
that fetches them — there is no poller running, so today a reply arrives only
when somebody hands it over.

The order inside it is the safety property: apply the event, **pause the
company**, classify, then notify. Nothing in classification or notification
can reach back and undo the pause.

## 16. Pause responders — **automatic, and not optional**

Any reply pauses **both channels for the whole company**, not just the person
who answered. Nobody on that list is contacted again after somebody answers.

## 17. Notify — **routed and recorded, never posted**

Positive replies go to that workspace's own Slack channel. Everything
operational goes to the global operations channel. Neutral and negative
replies go to neither — they live in the Web App.

There is no fallback between the two levels and no fallback between
workspaces. A workspace with no channel gets `unconfigured` and posts nowhere.

`SLACK_LIVE` is unset, so nothing is posted. `/notifications` shows what would
have gone where.

## 18. Report

**Works today.** `/reporting`, `/reporting/client`.

Analytics with every denominator stated, then a client report as a PDF —
executive, detailed, or internal operations. The template is a permission: a
client-facing role cannot render the internal one, and cannot reach its
sections by naming them.

Every figure comes from the same functions the screens read, so a report
cannot disagree with a dashboard. Meetings say "not tracked", because nothing
here observes a calendar.

---

## Things that go wrong, and what they mean

| What you see | What it means |
| --- | --- |
| A large held count | Verification disagreed or MX ruled the domain out. Not a delivery failure, and not something to override |
| "no known limit" on a sender | Nobody configured a capacity. Set it; do not let the system guess |
| An approval marked stale | The campaign changed after approval. Re-approve deliberately — the old one was for different content |
| A contact reachable on LinkedIn only | Email was ruled out. LinkedIn capacity, not list size, now limits this segment |
| An unmatched reply | Somebody answered and the system cannot say who. A person decides; nothing is auto-attributed |
| A workspace with no Slack channel | Its positive replies are recorded and go nowhere. They are never redirected to another client's room |
| "Not tracked" on meetings | Correct. Nothing observes a calendar, and no reply's wording will be read as a booking |

---

## Where to look

| Question | Screen |
| --- | --- |
| What does this workspace still need? | `/onboarding` |
| What is running, and what is only configured? | `/admin/health` |
| Who is stopped, and why? | `/suppression` |
| Where would this alert have gone? | `/notifications` |
| What did we tell this client last month? | `/reporting/client` |
| Who did what, when? | `/audit` |
