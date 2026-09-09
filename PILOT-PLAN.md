# The first live pilot

The purpose of the first live run is not results. It is to find out which of
this system's assumptions are wrong while the cost of being wrong is twenty
people rather than five thousand.

Everything in this system has been tested against a cassette. A cassette is a
recording of what a provider did once, which is a good model of a provider and
a poor model of reality. The pilot is where that gap gets measured.

## Scale, and why it is this small

**One client. One lane. Twenty contacts. Email only.**

Not fifty, and not both channels. Twenty is enough to see whether sends land,
replies come back, and the reply-to-pause loop closes, and small enough that a
mistake is an apology rather than an incident. LinkedIn is excluded from the
first run for a specific reason: adding a lead to a HeyReach campaign is a
mutation, and the lead-identity round-trip has been reasoned about but never
observed. That gets its own pilot afterwards.

## Before anything is enabled

- [ ] Sender domains are warmed. This system cannot check that, and cannot fix
      a burnt domain afterwards.
- [ ] A real EmailBison campaign exists and is mapped to the campaign record.
- [ ] The twenty contacts are verified, MX-allowed, deduplicated and selected.
- [ ] `python -m src.plan --campaign <id>` shows exactly twenty email steps due
      and no warnings.
- [ ] `python -m src.qa <id>` returns PASS, with no rule widened.
- [ ] Campaign approval is current, taken through the normal path, and the
      fingerprint matches.
- [ ] The suppression list has been reviewed by a human who knows the client.
- [ ] Somebody is available to watch it. An unattended first live send is not a
      pilot, it is a hope.

## The run

**Day 0.** Enable the sender. Send the day-1 email to five contacts only, not
twenty. Watch for two hours.

Look for: did the payloads reach EmailBison; do the sent records carry a
`push_id` and a push event; does the reply poller return a cursor; do any
bounces arrive; does anything appear in the observability counters that was not
expected.

**Day 0, later.** If those five are clean, send the remaining fifteen.

**Days 1–3.** Poll replies twice a day. Every reply must:

1. Classify to something in the allowlist,
2. Pause its company,
3. Block every further step for that contact,
4. Notify Slack once, not twice.

A reply that arrives and does not pause the company is a stop-the-pilot event.

**Day 5.** The second email step goes out to whoever has not replied. This is
the first test of the cadence over real elapsed time rather than a `day=`
argument.

**Days 5–21.** Let the cadence run. Re-read the plan weekly and compare the
backlog it predicted against what actually went out.

## What is being measured

Not reply rate. Twenty contacts cannot tell you a reply rate, and reporting
suppresses one below thirty touches for that reason.

What the pilot answers:

| Question | How it is answered |
|---|---|
| Do sends actually leave? | The provider's own sent count matches ours |
| Is our push idempotent in practice? | Repeat a push deliberately; nothing is sent twice |
| Do replies come back at all? | The poller's cursor advances and events land |
| Does a reply stop the sequence? | The company pauses; further steps block |
| Do bounces classify correctly? | A bounce is a bounce, not a reply |
| Does Slack control work under real signatures? | An approve and a reject, from Slack |
| Is anything about our timing wrong? | Compare the plan's schedule to reality |

## Abort criteria

Freeze the campaign — `orchestrator.freeze(campaign, why, by=...)` — and stop,
without discussion, if any of these happen:

- An email reaches an address that was not verified and MX-allowed.
- The same person receives the same step twice.
- A reply arrives and the company does not pause.
- A bounce is classified as a reply, or the reverse.
- Anything is sent to a suppressed or unsubscribed address.
- A draft goes out that did not pass lint, or that was edited after approval.
- The provider returns errors on more than one send in twenty.
- Anyone replies asking how we got their details and we cannot answer from
  `python -m src.audit --record <id> --contact <key>`.

The freeze is deliberately cheap: it blocks every step, changes no status and
leaves the approval intact, so hitting it costs nothing but time. Hit it early.

## After the pilot

Do not scale to 5,000 next. The order is:

1. Twenty contacts, email only. (this document)
2. Twenty contacts, LinkedIn only — the mutation and identity round-trip.
3. Fifty contacts, both channels, one client. Watch channel separation.
4. Two hundred, two clients. This is where cross-client dedup first matters.
5. A full batch.

At each step, the same rule: the thing being tested is whether an assumption
was wrong, and the way to find out is to look at what happened rather than at
whether the numbers were good.

## What to write down

After the pilot, update PRODUCTION-READINESS.md — specifically the "built but
unproven" table. Every row that the pilot actually exercised moves, and every
new unknown the pilot revealed gets added. That table is only useful if it is
honest about the date it was last true.
