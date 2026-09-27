# TASK-247 — NEVER, REENGAGE, REVIVE: three lanes, by rule, no overlap

OPERATOR DECISION, 2026-09-21, Zvonimir, recorded verbatim:

> RE-ENGAGEMENT SUPPLY, authorized: every lead currently in EmailBison (all
> campaigns in the workspace) and HeyReach (all lists and campaigns) is
> client-approved for re-engagement.
>
> Three lanes, by rule, no overlap:
> NEVER      unsubscribe, negative reply, bounce, unknown stop reason.
> REENGAGE   no reply ever, sequence finished, last touch > 90 days.
>            Email: a distinct re-engagement cadence, new thread, copy that
>            acknowledges prior contact, never the first-touch template.
>            LinkedIn: if already connected, message-only cadence with no new
>            connection request; if not connected, standard cadence.
> REVIVE     any reply (positive or neutral) then silence. Not enrolled
>            anywhere. Posted to #replies-productive with the thread and a
>            drafted next message for a human. Cap 20 per day so it stays
>            readable.
> Leads still in an active sequence anywhere are untouched.
>
> Pacing, hard stops, veto window and per-mailbox caps apply to
> re-engagement exactly as to cold. Re-engagement and cold share the same
> daily capacity; cold from approved new accounts takes priority when both
> are available.

## WHAT YOU DO NOT DO

**You do not read the providers.** Claude owns provider reads and is running
the inventory now; it lands in the local last-touch index and a bucket file.
You build the CLASSIFIER and the REVIVE queue over that data, offline, with
fixtures. A task that cannot be tested without a provider is a task that
cannot be tested.

**You do not enroll anything.** REENGAGE enrollment is blocked on operator
approval of the re-engagement copy, which Claude is drafting. Your output is
a lane assignment per lead and a queue, not a write.

## THE CLASSIFIER

One function, one lead, one lane, and it must be TOTAL: every lead lands in
exactly one of NEVER, REENGAGE, REVIVE, ACTIVE or UNKNOWN. No lead falls
through. No lead lands in two.

    NEVER       unsubscribe · negative reply · bounce · unknown stop reason
    ACTIVE      still in an active sequence anywhere - untouched, and this
                is checked BEFORE the other lanes, because a lead being
                mailed right now must not be re-enrolled by a rule about
                its age
    REVIVE      any reply, positive or neutral, then silence
    REENGAGE    no reply ever AND sequence finished AND last touch > 90 days
    UNKNOWN     everything else. It HOLDS. It is not a fourth lane to be
                drained later by a looser rule.

**The precedence is the whole design and it is not negotiable.** NEVER beats
everything. ACTIVE beats REVIVE and REENGAGE. A lead that unsubscribed and
later replied is NEVER. `has_reply` excludes REGARDLESS of recency - that is
the standing collision rule and this does not amend it.

**UNKNOWN STAYS HOLD.** The register's REFUTED rows are mostly the shape of
"a category nobody could explain, drained anyway". Report its size loudly.

## THE REVIVE QUEUE

Posted to `#replies-productive` (C0BFUF4JRK9), each with the thread and a
drafted next message from `prompts/reply_handling.md`, three variants, for a
human to send. **No auto-reply, ever.** Cap 20 per day, and the cap is a
queue not a filter: number 21 is tomorrow's, not nobody's. Ordering is
oldest-reply-first, and a lead already posted is never posted twice.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test name both directions.

Required tests: totality over a fixture estate (every lead gets exactly one
lane); precedence, one test per pair that can collide; a lead in an active
sequence is untouched by every rule; the 20/day cap queues rather than drops;
the same lead is never posted twice; UNKNOWN holds and is counted.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 1b6f873c
- **TESTS:** 36/36 pass in `tests.test_the_three_lanes_have_no_overlap`.
  `test_invariants` has 3 pre-existing failures on master (CLIENT_APPROVAL
  override, bison route binding, ProviderError import) - none introduced by
  this change, verified by stashing and re-running.
- **FILES CHANGED:**
  - `src/reengagement.py` (new) — classifier + revive queue
  - `tests/test_the_three_lanes_have_no_overlap.py` (new) — 36 tests
- **FINDINGS:**
  - The classifier is TOTAL: every lead gets exactly one of NEVER, REENGAGE,
    REVIVE, ACTIVE, UNKNOWN. No lead falls through.
  - Precedence is enforced by check order: NEVER first, then ACTIVE, then
    REVIVE, then REENGAGE, then UNKNOWN as the catch-all.
  - `has_reply` excludes regardless of recency — a lead that replied two
    years ago is REVIVE, not REENGAGE. Re-engagement copy that pretends a
    reply did not happen would be a lie.
  - `we_stopped_it` is NOT a NEVER reason — it is our own action, not a
    prospect signal. Without other signals, it falls to UNKNOWN.
  - The 90-day boundary is strict: exactly 90 days is UNKNOWN, 91 is REENGAGE.
  - UNKNOWN holds and is counted loudly via `lane_counts()`.
  - The ReviveQueue caps at 20/day, orders oldest-reply-first, and never
    posts the same lead twice. Overflow is queued for tomorrow, not dropped.
  - `prompts/reply_handling.md` does not exist yet — the revive queue's
    `draft` field is a placeholder for the three variants Claude is drafting.
- **RISKS:**
  - The module is not yet consumed by any caller in `src/`. It is a library
    awaiting integration with Claude's last-touch index and provider reads.
    `grep -rn "reengagement" src/` returns only the definition.
  - The Slack channel destination (C0BFUF4JRK9) is not wired — the queue
    produces batches but does not post. Posting is a separate integration
    task.
- **RECOMMENDED CLAUDE ACTION:**
  1. Wire the classifier to the last-touch index when the provider reads land.
  2. Integrate ReviveQueue with `notify.py` for Slack posting to #replies-productive.
  3. Draft `prompts/reply_handling.md` for the three reply variants.
