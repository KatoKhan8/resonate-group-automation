# Productive pilot plan

Prepared, not authorised. Nothing here has been executed and nothing here
sends.

This supersedes the audience and sequencing in `RELEASE-CANDIDATE.md` §9
for one reason, discovered on 2026-09-02 by reading HeyReach: **Productive
is not a greenfield.** `PRODUCTION-TRANSITION.md` §2 has the numbers. The
plan those documents describe was written for a workspace with no existing
outbound, and that assumption is false.

---

## 1. The blocker that comes before audience size

Roughly 160,000 prospects are mid-sequence in 42 live HeyReach campaigns
for this agency, across 39 LinkedIn sender accounts. Canonical state in
this build has never been told about any of them.

So the ordinary hygiene check - the one `ENGAGEMENT-HYGIENE.md` exists to
run before anybody spends a credit - **would pass on somebody HeyReach is
already talking to.** The prospect experiences one company approaching
them twice, from two senders, about two different things, and the first
they hear of it is the second message.

**No Productive contact may be selected until this is answered.** It is
`PRODUCT-GAPS.md` §15 and it is a P1. Three ways to close it, in
increasing order of effort and decreasing order of risk:

| option | what it costs | what it leaves open |
| --- | --- | --- |
| **Exclude by list** — export the audiences of the 42 live campaigns and load them as suppression | a read per campaign, and it goes stale the moment a campaign adds anybody | drift between the export and the next send |
| **Ask at pre-send** — query HeyReach for the contact before building a payload | a read per contact, and latency in the send path | HeyReach has no confirmed per-person lookup; `/lead/GetLead` is allowlisted but unproven for this |
| **Separate the populations** — agree a segment Resonate owns exclusively and HeyReach never touches | a decision, and discipline on both sides | nothing technical; it is the only option that is correct by construction |

**The third is the recommendation.** It is the only one that does not
depend on two systems staying in sync, and it is a conversation rather
than a build.

### What the EmailBison half of this now measures at

Answered exhaustively on 2026-09-02, read-only, against the live
instance: **0 of 50 pilot domains and 0 of 114 pilot addresses exist in
EmailBison's lead base.** Not a sample - all 27,035 leads were traversed
and the count matches the provider's own reported total, so this is a
verdict rather than a floor.

Getting there established the provider contract, which was worth more
than the answer:

- `per_page`, `limit` and `page_size` are ignored; the page is always 15.
- `?email`, `?q` and `?filter[email]` are ignored - `total` stays 27,035.
- `?search` is **not a filter**. Searching one pilot domain returned
  17,311 of 27,035 rows, none of them at that domain. It must never be
  used to decide whether a person is already known.
- `?page` beyond 1000 is refused with HTTP 422, so offset paging can
  reach 15,000 of 27,035 leads and silently miss 44% of them.
- Cursor pagination is the provider's own prescribed traversal and the
  only complete one.

**This does not close the P1 above.** EmailBison's lead base is not the
42 live HeyReach campaigns, and the pilot is email-only precisely because
LinkedIn is where the collision risk lives. A person can sit in a
HeyReach sequence and be absent from EmailBison, which is exactly the
case the blocker describes. What is now true is narrower and worth
stating: the *email* channel's own history has been checked completely
rather than assumed, and it is clean.

---

## 2. The pilot, once that is answered

Deliberately smaller than the system can do. The first live run validates
the path, not the funnel.

| | | why |
| --- | --- | --- |
| Audience | 10–15 companies, 20–30 contacts | small enough that a mistake is recoverable by hand |
| Selection | ICP `accept` only, and **only from the population Resonate owns exclusively** | `review` and `unknown` are real answers and spend nothing |
| Channel | **email only** | LinkedIn is where the collision risk lives, and where 39 senders are already working. Email capacity is idle: 15 campaigns, none sending |
| Senders | **one** human sender identity, one inbox | multi-sender is built and reported; it is not what a first run should prove |
| Cadence | **one arm.** No experiment | a reply that cannot be attributed to an arm is worse than no arm |
| Copy | **one variant per step**, written by a person | no model ships with this repository, and five variants over thirty contacts separates nothing |
| Volume cap | the workspace daily cap, set **before** approval | a cap set afterwards is a cap that was not in force |
| Approval | a named human, after `campaignqa` passes | an edit invalidates it; that is the point of the fingerprint |
| Pre-send | eligibility re-derived at payload time from primary state | not from what approval saw |
| Replies | **handled by a person.** Nothing polls | the single most important sentence here |
| Stop | freeze the campaign; any reviewer may | `killswitch` evaluates every layer and reports all of them |

**Success is not a reply rate.** It is: everyone who received something
was eligible when it was built; every confirmed touch matches a real
provider event; every reply reached canonical state before anybody was
told; and the report's numerators and denominators are events rather than
plans.

---

## 3. Controlled live write validation — prepared, not executed

No write was made during this work and none is authorised. Each of these
is the smallest reversible action that would prove one contract, derived
from what the provider actually exposes rather than from a plausible name.

### Slack — one message to a throwaway channel

| | |
| --- | --- |
| Mutation | one `chat.postMessage` to a channel created for this and nothing else |
| Preconditions | `SLACK_BOT_TOKEN`, `SLACK_OPS_CHANNEL` pointing at the throwaway channel, `SLACK_LIVE` set |
| Expected | 200 with a `ts`, and the message visible |
| Read-back | the outbox row records `posted`, and the `ts` is stored |
| Cleanup | delete the message; delete the channel |
| Cost | none |
| Risk | **low, and only if the channel is wrong.** A real client channel here wakes a client |
| Stop | any 4xx other than a channel error; any message appearing anywhere else |

### EmailBison — one lead into one draft campaign

| | |
| --- | --- |
| Mutation | `POST /campaigns/{id}/leads` with a single lead the agency owns |
| Target | a campaign created for this, left in `draft`. **Never one of the 7 paused or 2 completed campaigns** |
| Expected | 2xx, and the lead readable back |
| Read-back | `GET /campaigns/{id}` and confirm the lead and our identifier survived |
| Cleanup | delete the lead, then the campaign |
| Cost | none beyond the seat |
| Risk | **material.** A lead added to a campaign that is later unpaused is a real email to a real person |
| Stop | the campaign is not `draft` at the moment of the call; the identifier does not round-trip |

### HeyReach — no write is proposed

`heyreach.py` posts only to `/campaign/GetAll`,
`/inbox/GetConversationsV2` and `/lead/GetLead`, and refuses anything
else. Adding leads is not implemented. **A write test would mean writing
the write path first**, and that is a code change and a review rather than
a validation.

### ContactOut, AI Ark, Reoon, Deliverable

Not writes - **spends**. Each needs a decision about credits, not about
safety:

| | one deliberate call | cost |
| --- | --- | --- |
| Deliverable | verify one address the agency owns, then set `DELIVERABLE_RESULT_SHAPE=confirmed` **only if the normaliser matches** | 1 verification credit |
| Reoon | `python -m src.check --live-reoon` | 1 credit |
| ContactOut | `company-information-from-domain` on a domain the agency owns | 1 credit |
| ContactOut | `decision-makers`, `--no-reveal` | ~5 credits |
| AI Ark | one enrichment | AI Ark credits |

**Deliverable is the one that matters.** Its response shape has never been
read, `verify()` refuses to spend until it has been, and until then the
verification waterfall's final step is written against an assumption.
`LIVE-VALIDATION-PLAN.md` §2.1 is the procedure.
