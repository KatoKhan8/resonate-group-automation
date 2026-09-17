# What EmailBison documents, and the three answers that change what we build

2026-09-17. Grok with web_search, three questions, 88-105 sources each, every
claim carrying a URL. Raw output in
`docs/GROK-PROVIDER-RESEARCH-2026-09-17.md`. Cost: ~$1.40 per question.

Classification per the operator's contract: **DOCUMENTED** where the vendor's
own docs or OpenAPI spec say it, **OBSERVED** where this estate's provider
responses show it, **HYPOTHESIS** where a reading is plausible with no source,
**UNKNOWN** where it was asked and not answered.

**Primary source discovered:** EmailBison publishes a full OpenAPI spec at
`https://dedi.emailbison.com/api/reference.openapi`, plus
`https://docs.emailbison.com/llms.txt`. Nothing in this repository has ever
read either. Several answers below come straight out of them.

---

## 1. The sender IS sticky per lead — DOCUMENTED, and it agrees with our measurement

> "Once a lead has been sent an email in a campaign, the same Sender Email
> will send the remaining steps for that lead, as well as emails sent to the
> lead from a followup campaign."
> — https://docs.emailbison.com/campaigns/overview

**DOCUMENTED.** And it matches, exactly, what
`scripts/bison_sender_stickiness.py` measured hours earlier without knowing
the documentation existed: 243 leads seen at more than one sequence step
across campaigns holding 59 and 222 senders, zero rotations. Vendor
documentation and our own provider readback agree.

**The gap is named precisely and it is the one that matters for attribution:**

> "First send across multiple attached inboxes: **NOT DOCUMENTED.** Docs never
> say round-robin, random, weighted, ESP-matched, or any other picker. OpenAPI
> has no rotation/sticky/selection field."

So: **which human a prospect first hears from is chosen by the provider and is
not controllable or knowable in advance.** The only documented request field
naming a sender is `sender_email_id` on
`POST /api/campaigns/sequence-steps/{id}/test-email` — a TEST send, not
campaign traffic. `attach-sender-emails` takes only `sender_email_ids` with no
selection mode, and `attach-leads` takes `lead_ids` and an undocumented-to-us
`allow_parallel_sending` — no sender field.

This is exactly what `docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md` concluded
from the code: per-lead sender on EmailBison is OBSERVABLE, not CONTROLLABLE.
It is now documented rather than inferred.

**What it licenses:** a campaign may hold several inboxes belonging to ONE
attested human with no attribution risk at all, because stickiness makes every
step come from whichever of that human's inboxes was picked, and they are all
that human. **What it forbids:** attaching two humans' inboxes and hoping —
the first-send picker is undocumented, so the human a given prospect gets is
ours to observe after the fact and never to choose.

---

## 2. Recipient-local sending does not exist — DOCUMENTED absence

> "**NOT DOCUMENTED** in the API or product docs as a send mode. There is no
> schedule flag, campaign setting, or lead field for it. The documented send
> clock is the campaign `schedule.timezone`."

And the trap, caught and labelled by the researcher rather than passed on:

> "A marketing FAQ claims 'timezone-based scheduling, automatically sending
> emails based on each prospect's local time.' That is not described in the
> API/docs (no mechanism). **Do not build on it.**"

Also DOCUMENTED:

- A lead has `first_name`, `last_name`, `email`, `title`, `company`, `notes`,
  `custom_variables`. **No timezone field, and `custom_variables` are not
  documented as driving send time.**
- `scheduled_date_local` is defined against **the campaign's** timezone.
- `GET /api/campaigns/schedule/available-timezones` gives the allowed IANA
  ids. There are schedule TEMPLATES —
  `GET /api/campaigns/schedule/templates` and
  `POST /api/campaigns/{id}/create-schedule-from-template`.
- A schedule, including its timezone, CAN be updated on a running campaign via
  `PUT /api/campaigns/{campaign_id}/schedule`, with no documented restriction
  by status. **What happens to already-scheduled rows is NOT DOCUMENTED.**

**So the timezone architecture is ours to build and there is no provider
shortcut.** Seven of campaign 487's ten prospects are American and four are
scheduled to arrive between 03:12 and 05:46 their time
(`docs/SEVEN-OF-TEN-ARE-IN-AMERICA-2026-09-17.md`). The only mechanism this
provider offers is **one timezone per campaign** — which means timezone
buckets become campaign boundaries, and a cohort is already the unit of a
campaign. Schedule templates make that cheap.

---

## 3. Why 487 was queued at 15:02Z — DOCUMENTED, and it kills my hypothesis

> "it schedules on campaign resume and **at the end of each sending day**;
> pause then resume can force a scheduler run before end of day."
> — https://docs.emailbison.com/campaigns/overview.md

Campaign 487's ten rows appeared at **2026-09-17T15:02:48Z, two minutes after
its 09:00–17:00 Europe/Zagreb window closed.** The documentation says the
scheduler runs at the end of each sending day. Observation and documentation
agree to the minute.

**My standing hypothesis — that this provider assigns a day's leads at or near
the window OPENING, and 487 missed it by activating at 10:07 local — is
wrong.** It predicted 07:00–07:30Z on 2026-09-18 and the event fired sixteen
hours earlier at the other edge of the day. It is discarded, not adjusted. See
`docs/487-IS-QUEUED-AND-THE-HYPOTHESIS-IS-WRONG-2026-09-17.md`, written before
this documentation was found; the two now agree.

**It also names a lever, and the lever is not free.** "Pause then resume can
force a scheduler run before end of day" is the documented way to make 487
reschedule sooner than 2026-09-23. But a probe already paused this campaign
once and could not restart it (commit 105b86ed), the campaign now holds ten
rows of rendered copy, and what a reschedule does to existing rows is not
documented. **Not tonight, and not without deciding that six days is worse
than the risk.**

---

## 4. Webhooks exist and we poll every 300 seconds — DOCUMENTED

Every event the reply watcher polls for is a documented webhook:

    Email Sent            Email Opened          Contact Replied
    Email Bounced         Contact Unsubscribed  Contact Interested
    Untracked Reply Received                    Tag Attached / Removed

- Configurable by API: `POST /api/webhooks`. Test events via
  `POST /api/webhook-events/test-event`.
- Deliveries retry **5 times over 24 hours**, 15-second attempt timeout.
- **`/api/events` replays the last 10 days**, so a missed webhook is
  recoverable rather than lost — which is what makes this safe to depend on.
- Lead status change as a general event: NOT DOCUMENTED.

**Relevance to Resonate:** reply suppression is a safety invariant — an
inbound reply must stop future cadence for that lead on BOTH channels — and it
currently runs on a 300-second poll. A webhook makes it immediate, and
`/api/events` makes a missed one recoverable. This is the clearest throughput
and safety improvement in the whole research set.

**Not built tonight.** A webhook needs a reachable endpoint, signature
handling, and a replay reconciler against `/api/events`, and none of that is a
provider mutation to make at 21:00. Recorded as the next integration.

---

## What was NOT asked yet

`bulk`, `scheduling` and `heyreach_sender` are written and unrun —
`scripts/grok_provider_research.py --list`. The first run died on the
adapter's 60-second clamp (raised to 300 in `0e01aa83`), and the three that
matter most were run first.

## The standing rule

Nothing above is acted on as provider truth until a readback against our own
estate agrees with it. Two already have: sender stickiness, measured over 243
leads before the documentation was found, and the end-of-day scheduler,
observed at 15:02:48Z. Both agree. That is the standard the rest must meet.
