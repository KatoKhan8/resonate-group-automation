# TASK-238 · An event we can PROVE is not ours

PRIORITY: P0
DEPENDS:
OWNER: qwen
CHANNEL: linkedin / notifications

## THE PROBLEM

`src/inbound.py` raises `notify.UNMATCHED_REPLY` at severity
`action_required` for every HeyReach event it cannot attribute. On
2026-09-21 that was 21 events in one day, roughly 3.4/hour, and **not one of
them was ours**.

They cannot be ours, and it is provable rather than likely: our only live
LinkedIn campaign is 605732 and it has `sent = 0` on every read that day - no
messages, no connection requests. A reply event cannot originate from a
campaign that has never sent anything. We own 4 of 86 HeyReach campaigns and
the API key is workspace-wide, so the reply watcher is being shown the
CLIENT'S inbox traffic and correctly failing to attribute it.

The ops channel `#resonate-notifications` went live 2026-09-21. At this rate
it receives ~80 false `action_required` alerts a day, and **the reply
watchers are deliberately NOT restarted until this task is merged**, so that
the first thing that channel ever shows is not 80 false positives.

## WHAT THIS IS NOT

It is not a volume problem and the fix is not a digest. That option was
considered and rejected by the operator: batching would keep paging about
somebody else's inbox, just more quietly. An event on a seat we do not
operate is a FALSE POSITIVE, and the fix is attribution.

## WHAT WE OWN - the whole set, from `docs/state/PROVIDER-CAMPAIGNS.json`

    campaigns   605732 (IN_PROGRESS)   605487 (DRAFT)
                604869 (DRAFT)         599020 (FINISHED)
    seat        174892   - the only LinkedIn sender on all four

## THE RULE, AND IT IS FAIL-CLOSED

**Drop an event ONLY when it is POSITIVELY attributed to a campaign or seat
that is not in the set above.**

Everything else keeps today's behaviour - the event stays `unmatched`, the
notification is raised, a person reviews it:

    lookup raised                    -> KEEP. Not proof of anything.
    lookup returned empty            -> KEEP. Absence is not attribution.
    lookup returned no campaign/seat -> KEEP. A field that is not there
                                        cannot say whose it is.
    attributed to one of OUR four    -> KEEP, and this is the alert that
                                        matters - it is a real unmatched
                                        reply on a campaign we run.
    attributed to a campaign or seat
      that is NOT ours               -> DROP. The only drop.

An absence of evidence is never a drop. If the lookup cannot answer, the
system must behave exactly as it does today. **A quiet channel bought by
silently discarding a real reply is far worse than 80 false positives.**

## THE LOOKUP - what research already established, do not re-derive it

`docs/GROK-CONVERSATION-ATTRIBUTION-2026-09-21.md`, 208 sources:

- **There is NO documented endpoint that resolves a conversation id to its
  campaign and seat.** NOT DOCUMENTED. Do not go looking for one.
- **`POST https://api.heyreach.io/api/public/inbox/GetConversationsV2`
  exists** - "a paginated collection of LinkedIn conversations", header
  `X-API-KEY`, body `{offset, limit, filters}` with `limit` 1-100. The
  filters include **`campaignIds`** and **`linkedInAccountIds`**, plus
  `leadLinkedInId`, `leadProfileUrl`, `searchString`, `tags`, `seen`.
- **Whether each returned conversation CARRIES `campaignId` and
  `linkedInAccountId` is NOT DOCUMENTED.** The only published item sketch is
  unofficial and shows `id`, `lastMessageText`, `lastMessageSender`,
  `correspondentProfile` - no campaign, no account.

**SO YOUR FIRST STEP IS A MEASUREMENT, NOT A DESIGN.** Make ONE read-only
call to `GetConversationsV2` and print the exact keys of one conversation
object. Everything after depends on the answer:

- **If an item carries a campaign id and/or a sender account id** - build
  positive attribution on that field. This is the intended shape.
- **If it does not** - STOP AND SAY SO in your result block. Do NOT fall back
  to "it was absent from a filtered query, therefore it is not ours." That is
  an exclusion argument, and this repository has already learned what it is
  worth: `REFUSED IS NOT ROOM` in `docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`
  - a walk can only undercount, so absence from one is provable only from a
  complete, fresh, covering walk. A paginated inbox query over an account with
  86 campaigns is not that, and treating it as one would silently discard real
  replies the moment a page is missed. If the field is absent, the correct
  outcome of this task is a measurement and a written NO, not a fix.

## FILES ALLOWED

    src/inbound.py            the unmatched branch, around line 124-156
    src/providers/heyreach.py a READ for GetConversationsV2, next to
                              `_read_get` / the existing read helpers
    tests/test_task238_*.py   new
    scripts/task238_probe.py  new, the read-only measurement

## FILES FORBIDDEN

    src/notify.py       the routing table. `UNMATCHED_REPLY` stays
                        (GLOBAL, ACTION_REQUIRED). This task changes whether
                        an event REACHES notify, never where notify sends it.
    config/             and anything under it

## INVARIANTS - each of these is load-bearing

1. **THE HOLD SURVIVES, ALWAYS.** `accountpolicy.hold_for_unattributed_reply`
   runs over `events.correspondents` BEFORE any attribution question is asked,
   and a dropped notification must not skip it. Read the comment above it:
   an unattributable reply still stops the cadence to that person, because
   being known twice must not make somebody less safe. If an event turns out
   to be the client's, `correspondents` finds no records of ours and the hold
   is a no-op by itself - let it be a no-op, do not skip it.
2. **NO PROVIDER WRITES.** `GetConversationsV2` is a POST that READS. Declare
   it as a read so `providers.refuse_unauthorized_write` does not refuse it -
   see `is_declared_read` and how the other read-shaped POSTs are registered.
   Do not add it to `WRITE_ROUTES` and do not touch `SUPPORTED`.
3. **THE LOOKUP MUST NOT BREAK INGEST.** Wrap it the way
   `_from_the_site_itself` wraps its crawl: an attribution lookup that raises,
   times out or is rate-limited must leave the event exactly as it found it.
4. **ONE LOOKUP PER EVENT AT MOST**, and cache per conversation id for the
   pass. The watcher polls every 300s; do not turn one poll into 21 calls
   twice over.
5. **NO PII.** Conversation ids, profile urls and correspondent names are not
   to be logged or committed. Hash any identifier that reaches a test fixture.

## ACCEPTANCE

A test file that proves, with the transport stubbed and never live:

1. An event attributed to a campaign NOT in our four is dropped - no
   notification raised.
2. An event attributed to a seat that is not 174892 is dropped.
3. An event attributed to 605732 raises the notification.
4. An event attributed to 605487, 604869 and 599020 each raise it.
5. **The lookup raising an exception raises the notification.**
6. **The lookup returning an empty result raises the notification.**
7. **The lookup returning an item with NO campaign/seat field raises the
   notification.**
8. **The hold is applied in every one of the seven cases above**, including
   the dropped ones.
9. The lookup is called at most once for two events sharing a conversation id.

Tests 5, 6 and 7 are the point of this task. A fix that passes 1-4 and fails
5-7 is worse than no fix, because it discards real replies quietly.

## DELIVERABLE

The measured key set of a real conversation object, pasted verbatim; which
branch of the fork you took and why; the diff; the test run; and an explicit
statement of what an operator will now NOT be told about.
