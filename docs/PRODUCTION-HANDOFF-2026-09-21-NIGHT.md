# Production handoff — 2026-09-21 night

Written for a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-21-EVENING.md`**, whose headline — two real
emails sent — still stands and is no longer the most important thing.

---

## 1. THE HEADLINE: 151 LEADS ARE ENROLLED AND NONE OF THEM CAN BE SENT TO

Batches 1 and 2 pushed tonight. Eight EmailBison campaigns exist, **491
through 498**, one per attested human, holding 151 leads between them:

    491 kresimir 34 · 492 bernarda 30 · 493 ivan 20 · 494 fran 12
    495 tomislav 26 · 496 bojan  9 · 497 jakov  7 · 498 luka 13

Every one is **paused**, with 0 scheduled rows and 0 sends.

**THE ONE BLOCKER, AND IT IS AN OPERATOR DECISION BY CONSTRUCTION.**
`providerwrites.CONDITIONAL["bison.activate"]` resolves the campaigns it will
activate from their canonical rows and names **487 and 489 only**. Its
docstring says widening it is "a new operator decision. Adding an entry to
the tuple above is not a refactor." It has NOT been widened. Until it is,
those 151 leads sit enrolled and silent.

Everything else about them is done: verified twice, MX open, collision
cleared against the client's live estate, copy rendered and approved with the
grant as approver, senders bound, caps set, windows per cohort.

## 2. CAPACITY WENT 120 -> 2,310 FIRST STEPS A DAY

TASK-241 merged (`90bd119b` + `490f6f58`), so the arity rule moved from the
campaign to the action and each campaign now names **all** of its human's
attested mailboxes. 154 bound of 159.

**Five were held out by the 2% bounce hard stop, checked before the write:**
3760 (2.29%), 3743 (2.08%), 3761 (3.53%), 3947 (2.68%), 3437 (2.14%).

**3437 is the mailbox 489 is sending from.** Its 2.14% is LIFETIME over 8,947
sends; the grant's hard stop is 7 days, which `sender_emails()` cannot
answer. 489 itself has bounced 0 of 2. Not halted, not ignored — it needs a
7-day read nobody has taken.

## 3. THE BASELINE EVERYONE WAS DIFFING AGAINST WAS STALE

This cost a merge and is worth not repeating.

    r53  12:14Z  master        10,671 / 50 / 33   <- quoted in every brief
    r58  19:10Z  master        10,769 / 76 / 44   <- measured tonight
    r57  18:45Z  master + 241  10,755 / 74 / 36

TASK-241 was refused a merge on "+3 failures" that were nothing to do with
it. The verification-roles change landed at midday, ~27 enrichment and e2e
tests assert the OLD roles, and they had been failing for hours. Proven by
checking out `b9823c6f` and running one: it fails there identically.
**TASK-250** is the fixture work; the rule in it is update the fixtures,
never the policy.

## 4. THE GATES DID THEIR JOB FOUR TIMES AND EACH ONE WAS A REAL FINDING

- **The write guard** refused all eight campaign creates because the entry
  point had not declared write authority. Readback confirmed zero campaigns
  created. `scripts/batch1_push.py` now opens `providers.allow_writes(reason)`.
- **The live collision check** refused 101 contacts at accounts tonight's
  local recency walk had cleared: 75 where a campaign ended early, 26 where
  somebody has already replied. **Recency is not the whole rule.**
- **`store.refuse_evidence_loss`** blocked a repair that would have deleted a
  third provider's paid verification result.
- **`cadence.CompanyNameUnusable`** held four accounts whose only company
  name is their own hostname ("Collier.Simon", "M3.agency").

## 5. TWO DEFECTS FOUND IN GATES THEMSELVES, BOTH FIXED

**The approval gate was reading the DEFAULT verification policy, not the
client's.** `approve.why_not` asked `lint.sendable(contact)` with no policy,
so it answered under ContactOut-primary while Productive had moved to
Deliverable that morning. Measured: 168 contacts approved under a policy
their client no longer uses, 189 refused that the client's policy clears.
Fixed in `approve.py` and `lint.py`; `lint.policy_for_record` caches per
client.

**`CLIENT_APPROVAL` was missing from `store.STATE_OVERRIDES`**, so a test
fixture could have written the real client-approval store. Found by TASK-245's
worker, whose own addition to that tuple made the invariant test report mine.

## 6. WHAT EXISTS NOW THAT DID NOT THIS MORNING

    src/clientapproval.py        four states, default closed, no kill switch,
                                 snapshot export/clean/import, per-client
                                 suppression. 27 tests.
    scripts/client_snapshot.py   export / import / adopt / counts
    scripts/batch_eligibility.py READY re-derived from journals, fail-closed
    scripts/stage_s7_copy.py     S7: renders 489's approved words per lead
    scripts/batch1_build.py      S8: journals -> records, approvals, campaigns
    scripts/batch_preflight.py   runs the factory's refusals before the push
    scripts/batch1_push.py       the push, with the veto as an argument
    scripts/repoint_to_all_mailboxes.py   wave 2
    scripts/reengagement_inventory.py     read-only estate walk, resumable
    scripts/heyreach_cadence_survey.py    the LinkedIn cadence survey
    scripts/digest_loop.py       because NOTHING was firing the daily digest
    src/socketmode.py            stdlib websocket for the Slack agent
    src/nightlysourcing.py       TASK-245, stops at candidates

**Productive's list is adopted as snapshot `PRODUCTIVE-2026-09-07`: 24,710
domains approved.** Client approval is now a hard gate everything passes
through.

## 7. SUPPLY

    S5 verification   3,943 of 8,387 walked, 2,913 verified. STILL RUNNING
                      (pid 90260). It is re-asking the leads whose pair the
                      client's policy no longer accepts.
    S7 copy           850 of 871 rendered. The 338 held for "no angle" were
                      held for a MISSING MAP, not a missing angle - Project
                      Manager now resolves to `delivery`, CFO to a `finance`
                      angle built from the client's own words.
    Re-engagement     973 REENGAGE, 37 REVIVE, 379 UNKNOWN, 17 ACTIVE, 9
                      NEVER, from 1,415 leads across 16 campaigns.
                      **352, 327 and 328 are NOT in that count** - membership
                      refuses a 96,045-row campaign rather than returning a
                      page of it. They are unread, not absent.

## 8. WHAT IS WAITING ON THE OPERATOR

1. **Activate 491-498.** One line. 151 leads are enrolled behind it.
2. **The re-engagement copy** in `docs/REENGAGEMENT-COPY-FOR-APPROVAL-2026-09-21.md`.
   No REENGAGE lead enrols until it is approved.
3. **The 37 REVIVE leads** — permission to start posting them to
   `#replies-productive` at 20/day.
4. **Mailbox 3437's 7-day bounce rate.**
5. **Whether the ~90,000 leads in 352/327/328 are worth a per-lead walk.**

## 9. MONITORS

    86848   bison_mailbox_utilisation --interval 300
    19236   reply_watch_loop --interval 300
    95760   notify_deliver_loop --interval 60
    89640   bison_watch_loop --campaign 487 --interval 180
    105276  bison_watch_loop --campaign 489 --interval 180
    92332   heyreach_watch_loop --interval 300
    90260   stage_s5_verify --workers 3
    104992  slack_agent_loop        (owned by a DIFFERENT session now)
    111964  digest_loop --interval 300      NEW
    33521   reengagement_inventory --walk   read-only, resumable
    census  bison_forward_book_census --reset, on campaign 352

Restart bare. **Never under `timeout`.**

## 10. THE SLACK AGENT IS NOT THIS SESSION'S

A dedicated session owns `scripts/slack_agent_loop.py` and
`src/socketmode.py` in the `slack-agent` worktree. This session stopped
touching them at the operator's instruction and removed
`tests/test_slack_agent_readback.py` from master, which tested a polling loop
that no longer exists. Review its merge-request docs when they appear.

`#resonate-os` (C0C3C6MDN9L) is live as a third notify destination, and the
07:00 digest now routes there rather than to ops.

## 11. WHAT MUST NOT BE RE-DERIVED

- **A campaign's pause is not a lead's stop.** Reading `stopped` as a lead
  decision put 1,351 of 1,415 leads in NEVER. This estate is mostly archived
  April campaigns; the stop only counts against the lead while its campaign
  is still running.
- **`totalMessageReplies`**, not `totalReplies`, is HeyReach's reply key.
- **A HeyReach sequence is a nested graph**, not a `steps` list. The
  `conditionalNode` chain IS the accept / no-accept branching.
- **Evidence with no address does not count.** `verification.evidence_for`
  drops it, and that is why 1,068 approval attempts refused on the first run.
- **The planted-name guard cannot tell a person from a syllable.** 'Mark'
  inside 'Marketing' cost 46 leads until the pre-flight learned to drop the
  smaller side of the conflict.
