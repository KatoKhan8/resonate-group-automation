# Lane C - the operator's three rulings on reply classification

**Branch** `task-rulings-classify`, off master `2bf7b8a5`.
Worktree `scratchpad/wt-rul` (the path contains none of the nine forbidden
substrings, so `test_invariants`' send guard is live over every file).

All three rulings are implemented. Nothing is deferred for lack of a
decision; four questions for the operator are at the foot of this file,
and one of them is a discrepancy inside ruling 3 that I resolved
conservatively rather than guessed at silently.

---

## What lane 3's doc said, and what changed because of it

Read first, as instructed: `docs/PHASE2-UNMATCHED-CLASSIFICATION-2026-10-03.md`
and `docs/qwen-tasks/TODO/TASK-1011-...md` at `0db3d489`. Two things in it
changed the shape of this work.

**The brief's premise is TASK-1004's world, not master's.** The brief says
"today `question` maps to `NEEDS_A_PERSON` wholesale". On master `2bf7b8a5`
there is no `NEEDS_A_PERSON` at all: `question`, `objection` and
`assistant_redirect` all map to `UNKNOWN`, the one outcome `OUTCOME_POLICY`
has no entry for. `NEEDS_A_PERSON` exists only on
`task-1004-positive-replies-reach-a-human` (`88eb98fe`), which is at REVIEW
and **not merged** - confirmed with `git merge-base --is-ancestor`.

I was told to branch off master, so I introduced the outcome here, **using
TASK-1004's exact spelling, exact policy key, exact REVIEW/ACCOUNT effect
and exact signal mapping**, so the two are one thing and the merge is a
textual conflict rather than a semantic one. I deliberately did **not**
duplicate TASK-1004's other work: its `notify.REPLY_NEEDS_A_PERSON` route,
its `reply.on_referral` STOP to HOLD change, its `interested` and
`meeting_intent` remapping and its `channels` changes are all untouched.

**Consequence, stated plainly: on this branch a `needs_a_person` reply
reaches a person through the review queue (`rec["review"]["open"]` plus
`REVIEW_REQUIRED`), which is exactly how `unknown` reached one. It does not
yet raise a Slack notification. That half is TASK-1004's, and merging it
completes all three rulings.** No hole is opened: the positive path is
untouched, and nothing that reached a person before stops reaching one.

**`wrong person` / TASK-1011 was read and deliberately not touched.**
`REFERRAL` stays last in `RULES`; `NOT_RELEVANT_PATTERNS` is unchanged;
`referral.CUES` is unchanged. Ruling 3 is implemented without re-ranking
anything, and a control test proves the referral cue list did not widen.

---

## Ruling 1 - "a question about the offer" splits

**Narrow (price, how it works, a demo) counts toward the primary metric.
Broad still reaches a person. Nothing changes class.**

| file | change |
|---|---|
| `src/replies.py` | `QUESTION_NARROW`/`QUESTION_BROAD`; `NARROW_PRICE_PATTERNS`, `NARROW_HOW_IT_WORKS_PATTERNS`, `NARROW_DEMO_PATTERNS` (closed-form, three limbs, nothing else); `QUESTION_FIT_PATTERNS` as a one-way guard; `question_scope()`; `counts_as_positive()` |
| `src/replies.py` | `classify()` attaches `question_scope` **only** to a `question` verdict; `apply()` writes `counts_as_positive` and `question_scope` onto the `REPLY_CLASSIFIED` event |
| `src/accountpolicy.py` | `question` to `NEEDS_A_PERSON` (both limbs - the limb is a metric fact, not an outcome) |
| `src/report.py` | `_counts_as_positive()`, exposed as `counts_as_positive` in `daily()` and `client_summary()`, **beside** `positive_replies`, which is unchanged |

Three things this deliberately does **not** do, because over-claiming the
metric is the expensive error at 38.5% precision:

- a narrow question is **not** reclassified `positive`. No
  `POSITIVE_REPLY_DETECTED`, no alert, no `reply.on_positive`, no client
  trigger. `is_positive` and `counts_as_positive` are now two questions.
- `signals.ENGAGEMENT_SIGNAL[NEEDS_A_PERSON]` is `ENGAGED_REPLY`, not
  `ENGAGED_POSITIVE` and not `ENGAGED_MEETING`.
- `tagsync.OUTCOME_TAGS[NEEDS_A_PERSON]` carries no `resonate_positive`.

**The fit guard is the conservative half.** "How does this work?" is
narrow; "how does this work **with our stack**?" matches the same pattern
and is a question about fit, which lane 3's Q1 put under the broad
reading. The guard can only move a reply narrow to broad, never the
reverse. Scenario S15 ("how would this work with the tooling we already
run") is **broad** under this implementation, on both counts.

`counts_as_positive` fails closed: a `question` verdict carrying no scope -
one stored before today, a hand-built dict, a model answer - is broad.

## Ruling 2 - a past-failure objection is `objection`, not `negative`

| file | change |
|---|---|
| `src/replies.py` | `PAST_FAILURE_PATTERNS` and its own `(OBJECTION, PAST_FAILURE_PATTERNS, 0.75)` row in `RULES`, below every stop |
| `src/accountpolicy.py` | `objection` to `NEEDS_A_PERSON`, which **gives the class a policy**: `reply.on_needs_a_person` |

**The named consequence is discharged, and it is not cosmetic.** Before,
`resolve("unknown")` returned `key: None` and the why-string "no policy
covers 'unknown'". After, `objection` resolves to a named policy a
workspace can see and configure, with a title that says what it is. The
*effect* is unchanged on purpose (REVIEW at ACCOUNT scope, byte-for-byte
what `unknown` resolved to) - the ruling asked for a class and a route,
not a new permission.

Two deliberate choices in the patterns:

- **A conjunction, not a phrase.** Each pattern needs the attempt AND how
  it went, in the same clause. "We tried something like this before", with
  nothing about the outcome, is **not** swept in - there is a test for
  that. A pattern loose enough to take it would also take "we tried your
  competitor before and loved it".
- **Its own top-level tuple, not an addition to `OBJECTION_PATTERNS`.**
  This is load-bearing and I found it by inspection: `replies.py` binds
  `OBJECTION_PATTERNS` **twice** (line ~733 production, line ~926
  taxonomy). `RULES` captured the first at import; `_rule_material()`
  walks `globals()` and therefore sees only the second. **A group added to
  the production tuple would change what the classifier does without
  moving `RULE_HASH`** - precisely the failure that identity exists to
  catch. A new `*_PATTERNS` name is seen by both. Reported as a finding
  below; not fixed here.

## Ruling 3 - an EA redirect holds the cadence and raises a referral

| file | change |
|---|---|
| `src/accountpolicy.py` | `assistant_redirect` to `NEEDS_A_PERSON` (still **not** `REFERRAL`) |
| `src/referral.py` | `ASSISTANT_CUES`, `ASSISTANT_NAME`, and an opt-in `assistant=` argument on `evidence()` and `read()` - default off |
| `src/replies.py` | `_points_at_somebody(assistant=)`; `apply()` raises `REFERRAL_MENTIONED` for an `assistant_redirect` that names somebody |

**The hold.** It was already the behaviour - `unknown` resolves to REVIEW
at ACCOUNT scope, so the contact was held - but it was held as an accident
of there being no policy, which is not a rule. Lane 3's Q3 said "the
answer today is: nothing. The next step goes out on schedule"; **measured,
that is not so** - `effects("unknown")["replier"]` is `HOLD` and
`apply_reply` writes `contact["paused"]`. What was missing was the rule,
the name and the policy. Those are now there and pinned.

**The referral.** An assistant naming their principal uses none of the
hand-off cues, so `mentions_referral` read it as naming nobody. Measured
over seven realistic EA redirects: **2 of 7 raised a referral, 5 named a
person the system never recorded.** `ASSISTANT_CUES` is a **separate** list
read only for a reply already classified `assistant_redirect`; adding those
phrases to `referral.CUES` would have turned "I look after Mark Reynolds
diary" into a referral for every class of reply, and there is a control
test asserting `referral.evidence` and `mentions_referral` are unchanged on
exactly those strings.

It is a **note, never an action**: same event, same resolver, same
`needs_a_person` flag as every other class.
`reply.activate_referred_contact` stays reachable from the `REFERRAL`
outcome alone, `effects(needs_a_person)["activate_referred"]` is False, and
a test asserts no `REFERRED_CONTACT_ACTIVATED` is written. It fails closed:
no name, no referral - an empty mention is a queue item nobody can act on.
A removal request still never raises one.

---

## The tests, and the proof each change is load-bearing

`tests/test_reply_rulings.py` - **34 tests, all green**. Written before the
source and run red first (17 red / 16 green on untouched master).

Every change was then **mutated one at a time**, `__pycache__` wiped on
both sides, restored with `git checkout HEAD -- <file>` and **verified by
effect** (the module re-run to OK, not the file re-read):

| mutation | test that went red |
|---|---|
| `question` to `UNKNOWN` | `test_both_limbs_reach_a_person` |
| `counts_as_positive` returns True always | `test_only_two_things_count_toward_the_metric` + 4 others |
| fit guard removed | `test_a_narrow_phrasing_tied_to_their_own_stack_stays_broad` |
| past-failure `RULES` row removed | `test_a_past_failure_classifies_as_an_objection` |
| `objection` to `UNKNOWN` | `test_an_objection_now_carries_a_policy_of_its_own` |
| past-failure row made `NEGATIVE` | `test_a_past_failure_is_not_negative` |
| `assistant_redirect` to `UNKNOWN` | `test_the_ea_redirect_has_a_named_outcome_with_a_policy` |
| EA name extraction switched off | `test_the_ea_redirect_raises_a_referral_to_the_person_named` |
| `ASSISTANT_CUES` folded into the shared `CUES` | `test_the_referral_cue_list_was_not_widened` |

The first mutation run showed the fit guard was caught by **nothing**. I
added a test for it rather than leaving an untested guard, and re-ran the
mutation to confirm it now fails.

**Controls that pass both before and after**, so a blanket change cannot
satisfy the file: `test_only_two_things_count_toward_the_metric` enumerates
every member of `replies.CATEGORIES`; a refusal wearing an objection still
reads `NEGATIVE`; the objections that already worked still work; a past
attempt with no stated failure is still not an objection; the question rule
was not widened; the referral cue list was not widened; a non-EA reply
raises nothing; an EA who names nobody raises nothing; a removal request
never raises a referral; an EA redirect is never positive; and
`needs_a_person` is no more permissive than the `unknown` it replaced.

### Two tests on master asserted the rulings' opposite and were updated

Both kept their guard at full strength; only the third option changed.

- `test_taxonomy_safety.NewCategoriesMapToUnknown.test_objection_maps_to_unknown`
  became `test_objection_is_neither_a_refusal_nor_a_buying_signal`. Still
  asserts not-NEGATIVE **and** not-POSITIVE, and now also that the effect
  equals `unknown`'s.
- `test_an_assistant_is_not_a_buying_signal` ...
  `test_an_assistant_redirect_goes_to_review_not_to_referral`. Still
  asserts never-REFERRAL, and now also `activate_referred` False and
  REVIEW/ACCOUNT directly.
- `test_reply_transitions.EveryOutcomeHasAStatedEffect.EXPECTED` gained the
  `needs_a_person` row (the table asserts it covers `ap.OUTCOMES`).

### Validated against real replies, not only invented ones

`resonate-ops/copy-review/POSITIVE-SAMPLE-2026-10-03.md` - the operator's
own 32 flagged replies, with the text as the people wrote it. Classified on
master and on this branch and diffed row by row. The texts stayed outside
the repo; only aggregates are reproduced here.

- **Not one of the 32 changed classification.** Five rows changed OUTCOME,
  and only the five `question` rows: `unknown` to `needs_a_person`, same
  effect.
- **No row moved out of a stop class.**
- The metric moves **18 to 19**. The single row added is **row 8**, the
  operator's own question-limb keep, whose stated reason is "a price
  question is a question about the offer". The narrow limb takes 1 of the
  5 question rows; 4 stay broad.
- Zero `objection` and zero `assistant_redirect` rows in this sample, so
  rulings 2 and 3 move nothing on it - consistent with lane 3's "3 in
  899". This sample is the positive bucket, not the whole corpus.

### Modules run, compared BY NAME against untouched master

Baseline measured on `scratchpad/wt-taxbase`, clean, detached at
`2bf7b8a5`. **No full suite was run** - 40 individual modules, the same 40
on both sides.

**Result: 17 failing names on master, 17 on this branch. NEW: none. GONE:
none.**

The five I was asked to report:

| module | master | this branch |
|---|---|---|
| `tests.test_replies` | 83 ran, 1 fail - `TestTheClassifier.test_every_verdict_carries_its_evidence` | identical |
| `tests.test_taxonomy_safety` | 30 ran, 1 fail - `GenuineInterestStillClassifies.test_genuine_curiosity_reaches_interested` | identical |
| `tests.test_reply_transitions` | 43 ran, OK | 43 ran, OK |
| `tests.test_referral` | 46 ran, **1 fail** - `TheWholeChain.test_a_plain_hand_off_holds_the_referrer` | identical |
| `tests.test_signals` | 95 ran, OK | 95 ran, OK |

plus `tests.test_reply_rulings` 34 OK (new), and
`tests.test_an_assistant_is_not_a_buying_signal` 26 OK,
`tests.test_tagsync` 28 OK, `tests.test_account_policy` 31 OK,
`tests.test_reporting` 43 OK, `tests.test_reporting_honesty` 19 OK,
`tests.test_inbox` 28 OK, `tests.test_notify_pipeline` 50 OK,
`tests.test_events` 41 OK, `tests.test_eligibility` 59 OK,
`tests.test_a_stored_verdict_names_the_rules_that_made_it` 16 OK.

**A THIRD PRE-EXISTING RED IN MY NAMED LIST, AND IT IS NOT MINE.**
`test_referral.TheWholeChain.test_a_plain_hand_off_holds_the_referrer`
fails on untouched master, standalone, in a worktree whose only change was
an empty `REPORT.md`. It asserts the referrer is **paused** after a plain
hand-off; master's `reply.on_referral` is `STOP`, so the contact is stopped
and not paused. That is TASK-1004's `reply.on_referral` STOP to HOLD
change, which master's test file already expects and master's source does
not yet do. My brief named two reds; there are three. The other fourteen
failing names are in modules outside those five.

---

## Findings worth somebody's attention, not fixed here

1. **`replies.OBJECTION_PATTERNS` is bound twice**, and `RULE_HASH` only
   sees the second. A change to the production objection patterns is
   invisible to the verdict identity - the exact failure mode `RULE_HASH`
   was built after. Worked around here; one of the two should be renamed.
2. Lane 3's Q3 premise - "the next step goes out on schedule" for an EA
   redirect - is not what master does. The contact is held. Only the
   notification and the referral were missing.

## Questions for the operator

**Q-A - ruling 3's comparison does not match the code, and I took the
explicit half.** You wrote "an EA redirect HOLDS the cadence for that
person AND raises a referral to the person named, **exactly as
`wrong_person` is treated**". Measured on master, `wrong_person` does
neither: `reply.on_wrong_person` is CONTINUE at CONTACT scope, so the
replier is **STOPPED**, the account carries on, and the outcome raises no
referral. I implemented your explicit words - hold, plus a referral raised
- and left `wrong_person` untouched. Did you mean (a) the behaviour you
described, which is what I built, (b) literally map an EA redirect to the
`wrong_person` outcome, which would STOP the contact instead of holding
them, or (c) `wrong_person` as TASK-1011 would leave it once implemented?

**Q-B - who is "the person named" in an EA redirect?** I read it as the
principal the assistant names ("I am the EA to Jane Hopkins" raises Jane
Hopkins), because that is the only person the reply names. Your 2026-09-22
decision described the EA themselves as "a new contact candidate at that
account", which is the other reading, and the two differ: the principal is
usually already a contact, the assistant usually is not. Which should the
referral point at?

**Q-C - your narrow set and your earlier narrow wording are not the same
set.** This ruling's narrow limb is "price, how it works, a demo". Your
2026-10-03 review file described the narrow reading as "what the offer *is*
or what it *costs*". "How it works" and "a demo" are in this ruling and
were not in that wording; "what it is" was in that wording and is not in
this ruling. On your own 32 flagged replies that choice decides four rows:
row 8 (price) counts, rows 14, 16, 23 and 26 do not. I implemented this
ruling as written. Confirm, or name the fourth limb.

**Q-D - should the primary metric replace the old number or sit beside
it?** I added `counts_as_positive` **beside** `positive_replies` in
`report.daily()` and `report.client_summary()` rather than redefining the
existing field, because `positive_replies` is read in six places and is
also what fires the alert. If the client-facing number should now *be*
`counts_as_positive`, that is a one-line change in each report and a
decision about a number you report outward, so I did not make it.

---

## Constraints honoured

No full suite: `scripts/run_suite.py`, `tests.offline` and `unittest
discover` were never run, and the machine-wide lock was never touched. No
provider write, no Slack post, no write to production `work/`. No `git
stash`. No `git push`. `__pycache__` wiped after every source mutation,
and every restore verified by effect. No pattern list widened to make a
case pass - the two new lists are new, explicit and narrow, and both are
guarded by a control proving the existing lists are unchanged. No reply
text from the operator's review file was copied into this repository.
