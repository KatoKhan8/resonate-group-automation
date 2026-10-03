# TASK-976 RESULT — the three entry gates, the em1 contract, and the exemplars

Branch `task-copy-exemplars`, commit `2d79524e`, pushed and verified against
`origin/task-copy-exemplars`. Master untouched (`e967271d` local and remote).

**WRITTEN AFTER THE CODE.** Every command below was executed before it was
written down. No full suite was run: the main session holds the machine lock.

## The four measurements of TASK-976, re-run

| TASK-976 says | re-run 2026-10-03 | verdict |
|---|---|---|
| none of the three holds exists | `grep -rnE "research_required\|proof_required\|offer_unapproved" src/ tests/ scripts/ config/` → one hit, a COMMENT in `productive-offers.yaml:67` | CONFIRMED (and the comment already predicted the spelling) |
| em3's rule is live, `claims.check` at 5 sites | 11 `claims.check` mentions in `generate.py`, including all five lines named (1002, 1107, 1408, 1489, 1669) plus 1771, 2389, 2419 | CONFIRMED, and LARGER than claimed |
| `eligibility` contains "offer" zero times | `grep -c offer src/eligibility.py` → 0 | CONFIRMED |
| the research count is known at generation | `_evidence_fingerprint` and `research_block` both read `rec["research"]` | CONFIRMED |

All three acceptance commands FAILED before the change, each for the predicted
reason — missing constants, `OFFER-A-ECONOMIC-BUYER` and `OFFER-B-OPERATIONS`
silent on `client_approved`, and `licensed_proof_rows` not existing — and all
three pass now.

## The operator's em1 exemplars, measured

17 `.eml` files parsed. **16 carry a three-line bare-name signature worth
EXACTLY 7 tokens in all 16.** Excluding it:

    114 116 117 118 119 120 120 120 121 122 122 123 125 127 132 133
    min 114  max 133  mean 121.8  median 120.5  modal 120
    inside 90..140: 16 of 16

The 17th is a reply inside an existing thread at 69 words with no such block.

**Correction to the brief: the median is 120.5, not 120.** n is even; 120 is
the modal value and `median_low`. The band and the target are the operator's
real copy either way.

`lint.countable_words` returned the RAW token count for all 17 before the fix —
measured by running it over them — so every body was credited with 7 words no
prospect reads.

## A21 was worse than one collision

There is **no `WORD_CONTRACT` symbol anywhere on this branch**. em1's length was
stated in five places and no two agreed:

    src/copystages.py:311       "EMAIL 1: 60 TO 90 WORDS"        the prompt
    src/copystages.py:658       "<full body, 60-90 words>"       the JSON schema
    src/skills/cold_email_writing.py:36,69,77-81  "60-90"        the skill card
    src/sequencegate.py:356     FAIL >130, warn outside 45..95   a gate
    src/lint.py                 MIN_WORDS 40 .. MAX_WORDS 180    the gate

`lint.WORD_CONTRACT` is now the authority and all four others render from it.
`test_the_prompt_follows_the_contract_when_it_moves` renders the prompt against
a different contract and asserts the numbers move, so "derived" is proven
rather than asserted.

**The old gate refused the operator's own best copy.** `sequencegate` FAILED em1
above 130, so the 133-word and 132-word exemplars were refused outright and
nine more were warned for being outside "target 60 to 90".

## Two bugs the change exposed

1. **`lint.check` decided "is this a thread reply" by comparing RANGES** —
   `(low, high) != (MIN_WORDS, MAX_WORDS)` — which became TRUE for em1 the
   moment em1 had a band, so an over-long em1 would have been reported
   `reply_too_long`. `lint.is_reply_step` is membership now.
2. **`word_range` would have let the tenant-neutral contract overrule the
   offer record.** An offer declaring `thread_reply_rungs: [3]` still had its
   em2 judged against 15..60. Caught by
   `test_an_offer_with_a_different_shape_is_not_forced_into_offer_a`, not by
   reasoning.

## THE RESEARCH GATE: DECIDED, 2026-10-03 - DO NOT "FIX" THIS BACK

**OPERATOR'S RULING, Zvonimir, 2026-10-03. ACCEPTED AS SHIPPED.** The
lighter form stands: `research_required` holds em1 when the record has
**no research row AND no fact**. An em1 with at least one verifiable fact
may be generated without a research row.

His reason, in his own words: *"Doslovno pravilo bi drzalo cijelu bazu."*
The literal rule would hold the entire database.

**IF YOU ARE READING THIS BECAUSE THE CODE LOOKS LOOSER THAN TASK-976's
WORDS, IT IS, AND THAT IS THE DECISION RATHER THAN A DRIFT.** TASK-976
says "em1 with zero research rows". The gate asks a wider question on
purpose. Tightening `generate.entry_gates` back to the literal count
needs a new operator ruling, not a cleanup: it would hold the majority of
the estate and every generation fixture in this repository. The
measurement that made the case is below and it is why the ruling exists.

## THE MEASUREMENT BEHIND THAT RULING

The order is "em1 with **zero research rows**: HELD `research_required`".
Applied literally, that holds **every generation fixture in this repository** —
all of them carry zero `research` rows — and, per CLAUDE.md's own figure (695
rows on 203 of ~1,582 records), most of the live estate. Eleven tests went red,
and four of the five fixtures carry 2 to 8 facts that `facts_block` returns
happily, so the literal trigger held records that were never short of evidence.

**The gate as shipped asks "nothing to write from": no research row AND no
fact `facts_block` will return.** `research` is one store of company evidence;
`facts_block` is the authority on what the writer may see. A record with
neither has nothing to open with; a record with either does not need this hold.

The eleven red tests were the measurement, not an inconvenience: they were
the first evidence of how wide the literal rule reaches. The operator ruled
on them the same day.

## The tenancy edge TASK-976 named

`claims.licensed_proof_rows(client)` returns `None` — **not 0** — for any client
but Productive, because `offers.py` is single-tenant (TASK-564 finding 3) and
cannot answer. `proof_rotation_satisfied` has three answers, and
`generate.entry_gates` tests `is False` rather than `not`: `not None` is True,
so `not` would have held em3 for every client but Productive on a question
nobody asked. UNKNOWN is still never a pass on the SEND path, where
`eligibility` fails closed on `client_approved` and `claims.check` refuses an
unlicensed customer-outcome sentence whatever the tenant.

Productive's count is **11** (11 `CLIENT_APPROVED` evidence rows, each with a
stored page under `docs/evidence/case-studies/`), so `proof_required` does not
hold Productive today.

## `client_approved`, settled before the hold was built

| offer | before | after |
|---|---|---|
| `OFFER-GIVE-001` | false | false (unchanged — the control) |
| `OFFER-A-ECONOMIC-BUYER` | absent | **true**, Zvonimir, 2026-10-03, `e471a035` |
| `OFFER-B-OPERATIONS` | absent | **true**, Zvonimir, 2026-10-03, `e471a035` |
| the other six | absent, `approval_status: pending` | unchanged |

Verified with `offers.load()`, the project's own parser, not PyYAML.
`offers._validate` now REFUSES to load an `approval_status: approved` offer
that is silent on `client_approved`, so a tenth offer cannot repeat the
omission.

## What is NOT done, and why

- **`sequencegate.role_ladder` still has no production caller.** It was not
  wired. Wiring it is a change to what generation refuses, it belongs to
  TASK-964's own follow-up, and it needs a full-suite reference this lane
  cannot take.
- **No full suite.** The machine lock is held by the main session. The
  verification is a per-module failing-NAME-SET diff against a detached
  worktree at the base commit `e471a035`, over the **158 modules** that
  import a changed module or read a changed fixture: **157 of 158 came back
  SAME SET**, and the one that did not
  (`test_run::test_a_half_drafted_record_is_refused_by_name_without_the_flag`)
  was a REAL ordering defect this diff caught - `_entry_gate_hold` ran before
  `_refuse_partial_regeneration`, so a caller that would have destroyed half
  a generated set was told the record was held instead of being refused by
  name. The caller contract goes first now and that existing test owns the
  order. Re-measured after the fix: 15 of 15 SAME SET.
  A change under `src/` ALWAYS needs a fresh reference by the operator's own
  rule, so **this branch is NOT merge-gated yet** and must get one before it
  lands.
- ~~`lint.REPLY_MIN_WORDS`/`REPLY_MAX_WORDS` are still in force~~ **DONE,
  2026-10-03.** The operator ruled explicitly: both constants are DELETED,
  for the same reason as TASK-943 - one authority for one number. See the
  section below.
- **`docs/qwen-tasks/REVIEW/TASK-964-...md` names a real prospect company**
  in its "STILL OPEN" section. Pre-existing at `e471a035`, flagged not fixed.

## PII

Two independent scans over the STAGED DIFF before the commit, both with
positive controls, both reporting hashes and never plaintext. **They found two
real leaks:**

1. a recipient company name in a comment I wrote in `src/lint.py`, and another
   in `src/copystages.py` — typed into a change that is about not doing that;
2. a mobile number, twice, inside the one exemplar that is a reply rather than
   a cold opener.

Both fixed: the comments are rewritten without the names, and that exemplar's
body is described rather than printed. **The exemplar file had already passed
two clean scans of its own before the staged-diff scan caught it** — a file
that passes two scans is not a clean file. The committed test
(`tests/test_the_em1_contract_has_one_authority.py`) holds 41 SHA-256 hashes
and no names, scans the files, the rendered prompt and **itself**, and
`test_the_scan_can_fail` proves the scanner is watching.

## Acceptance

All executed. 67 tests in `tests/test_the_em1_contract_has_one_authority.py`,
all green, and nine mutations were applied and reverted one at a time:

| mutation | tests that went red |
|---|---|
| em1 band back to (60, 75, 90) | 6 |
| `countable_words` loses the bare-name signature | 2 |
| `is_reply` derived from the range again | 3 |
| `sequencegate` hardcodes its thresholds again | 4 |
| the offer hold is not called from `decide` | 1 |
| the entry gates are not called from `generate_record` | 1 |
| the exemplars are not substituted into the prompt | 3 |
| the `client_approved` backfill is removed | 6 |
| `licensed_proof_rows` ignores the stored page | 1 |

The last one failed NOTHING on the first pass — the count stayed at 11 and no
test observed it — and `test_the_stored_PAGE_half_is_required` exists because
of that.

## THE REPLY BAND LOSES ITS SECOND AUTHORITY, 2026-10-03

**OPERATOR'S RULING, Zvonimir, 2026-10-03.** `lint.REPLY_MIN_WORDS` and
`lint.REPLY_MAX_WORDS` are **DELETED**. The band is 15 to 60 exactly as his
2026-10-01 ruling set it; what went is the second COPY of those numbers.
`WORD_CONTRACT["em2"]` and `["em4"]` hold the band now and `reply_band()`
is how a caller without a step key asks for it.

### Every reader, named, as the condition required

`grep -rn "REPLY_MIN_WORDS\|REPLY_MAX_WORDS" src/ tests/ scripts/` before
the deletion - **four live source readers and four test readers**, not a
constant with none:

| site | what it did | now |
|---|---|---|
| `lint.py:321,323` | `WORD_CONTRACT`'s em2/em4 entries | state `(15, None, 60)` themselves |
| `lint.py:385` | `word_range`'s reply branch | `reply_band()` |
| `lint.py:387` | the guard that stops the contract overruling the offer | `reply_band()` |
| `lint.py:553,555` | `EXPLAIN`'s two reply retry sentences | `reply_band()` |
| `lint.py:862` | a comment | names `WORD_CONTRACT` |
| `test_a_thread_reply...py:206` | the offer-shape test | `lint.reply_band()` |
| `test_a_thread_reply...py:231` | the fallback test | `lint.WORD_CONTRACT["em4"]` |
| `test_a_thread_reply...py:313,314` | the prompt test | `lint.reply_band()` |

### It had ALREADY drifted, which is the argument for the deletion

`EXPLAIN` interpolated the constants into the writer's retry sentence while
`word_range` had been taught to read the dict. Two authorities, one number,
and the writer could be told one band and judged against another - the exact
shape that intersected to a single legal length for em2 (CLAUDE.md,
operator, 2026-10-02).

**And a worse instance of the same defect was found and fixed in the same
commit.** `EXPLAIN`'s `body_too_short` said *"the body is under 40 words"* -
`MIN_WORDS` - for every step alike. em1's floor became **90** on 2026-10-03,
so the retry instruction fed straight back to the writer was an instruction
to write a body the gate then refuses. That is the measured cause of the
bigfish `em4` round (under-length 7 then 10 times in consecutive rounds,
having been told the wrong number every time), now true of em1.
`explain(codes, text, step_key=...)` renders the four length sentences with
THAT step's band; the eight call sites that cannot name a step keep the
global numbers, unchanged.

### `reply_band()` takes no argument, and the existing test caught why

The first version accepted `reply_steps` and looked those steps up in the
contract first. `test_an_offer_with_a_different_shape_is_not_forced_into_
offer_as` went red: an offer declaring `thread_reply_rungs: [3]` made
`reply_band(("em3",))` return em3's **opener** band of 40..180, because em3
has a contract entry and it is not a reply band. The steps an offer newly
declares replies are precisely the ones with no reply band of their own, so
asking them is asking the wrong thing. An intersection across rungs (max
floor, min ceiling) was considered and rejected: it invents a number nobody
ruled on, in the one place this change exists to stop that.

### The mutation the operator asked for

**Written before the deletion.** `TheReplyBandHasOneAuthorityToo` failed
five ways with the constants present - the two `hasattr` assertions, the two
derivation assertions (`word_range` returned the constants, so moving the
contract moved nothing) and the retry-instruction assertion (`explain` had
no way to know which step it was explaining). Then deleted, then green.

Then restored, with `__pycache__` wiped before every run:

| mutation | result |
|---|---|
| **M1** - the constants restored and NOTHING else | **exactly one** test reds: `test_the_two_reply_constants_are_gone`, `AssertionError: REPLY_MIN_WORDS is back`. No other guard fires first, and `test_a_thread_reply_has_its_own_word_range`, `test_lint` and `test_structural_repetition` stay green |
| **M2** - the full revert: restored AND read again | **four** tests red, each with its own reason: the namespace one, both derivation ones (`(15, 60) != (7, 21)`), and the retry instruction (`'7' not found in '...at least 15 words'`) |
| restore | byte-identical, baseline green again in all four modules |

M1 is the one that answers the operator's condition: a bare resurrection of
the two constants, reading nothing, still reds a test - and reds ONLY that
test, so the failure cannot be mistaken for collateral.

### What this does NOT do

### ONE THING FOR THE OPERATOR, because the two statements disagree

CLAUDE.md's TASK-943 line reads: *"THE WRITER CONTRACT IS THE ONLY
AUTHORITY FOR A BODY'S WORD COUNT ... **The 15-to-60 thread-reply range is
abolished.**"* Tonight's instruction was narrower - delete the two
CONSTANTS, for the same reason as 943, one authority - and said nothing
about retiring the band. **This commit follows tonight's instruction: the
band stays at 15 to 60 and only the second copy of the numbers went.**
`test_the_band_itself_is_unchanged` pins that, so if the intent was in fact
to abolish the RANGE as well, that test is the one line to change and it
will say so loudly rather than drifting.

A second, smaller mismatch of the same kind, recorded rather than acted on:
943's line puts the single authority in **the writer contract**. This
commit puts the numbers in `lint.WORD_CONTRACT` and has
`copystages.WRITER_SYSTEM` RENDER from it - so the writer contract still
states them and cannot disagree with the gate, which is the effect 943
asks for, reached from the other direction. `lint` was chosen because it is
the module every gate already imports and `copystages` imports nothing;
the reverse would have created an import cycle.

The 15-to-60 band is **not** abolished, and `reply_too_short` /
`reply_too_long` are **not** retired. `test_the_band_itself_is_unchanged`
is the control: `word_range("em2")` and `word_range("em4")` are still
exactly `(15, 60)`. Only the second copy of the numbers went.

## MERGE BLOCKER ON THIS BRANCH, NOT CAUSED BY THIS TASK - and it is a
## REAL defect, not a stale test

The name-set diff against master `7e8eee41` came back **SAME SET for every
module but one**. `tests.test_only_the_selected_offer_is_validated` has
**two** names on this branch that master does not have:

    test_productive_no_longer_refuses_at_offer_pm_001
    test_the_validated_selection_is_the_set_the_strategy_plans_around

**ATTRIBUTED BY MEASUREMENT, NOT BY ARGUMENT.** Both fail at `e471a035`,
this branch's base, before any of today's work - run in a detached
worktree at that SHA. They arrive with `4099a130`, the give-first offer
commit (TASK-964's), because `OFFER-GIVE-001` is the first offer in the
library that is `approval_status: approved`, persona `champion`, and
**composes nothing**.

### The second one is a live inconsistency and its own docstring predicted it

Measured 2026-10-03:

    generate_campaign._select_offers('productive', 'champion')
        -> ['OFFER-B-OPERATIONS']
    campaignstrategy._offers_for_segment('productive', 'champion')
        -> ['OFFER-B-OPERATIONS', 'OFFER-GIVE-001']

`_select_offers` has a third narrowing step - a COMPOSED offer is the
shippable unit, so a bare offer beside one is a building block -
and `_offers_for_segment` filters on segment and persona only. Until
`OFFER-GIVE-001` existed, every persona had exactly one composed offer and
the two agreed **by accident**. That test's own docstring says what this
means: *"If the two ever disagree, the gate is validating one set while the
campaign is built from another."* It now does, and the offer the strategy
would carry and the gate never validated is precisely the one with
`client_approved: false`.

### Not fixed here, deliberately

Resolving it is a design decision in another task's modules: either
`_offers_for_segment` learns the composed-offer rule, or `_select_offers`
stops narrowing. **Editing the test to make it pass would be weakening a
check that is correctly reporting a disagreement** - the one thing CLAUDE.md
forbids outright - so it is reported instead.

**Nothing can be SENT with it in the meantime**, and that is this task's own
backstop rather than luck: `eligibility._offer_unapproved` holds any step
naming `OFFER-GIVE-001`, because its `client_approved` is `false`. The
exposure is that the strategy can carry it into GENERATED copy without the
offer gate having validated it - which is what the copy review is for, and
is the operator's own split working as intended.

### One more row from the same diff

`tests.test_invariants` reports **4 failing names on master and 3 on this
branch** - a strict subset, so one name that fails on master passes here.
Recorded rather than claimed as a fix: a name that disappears is verified
positively or not at all (CLAUDE.md), and this branch was not aiming at it.

## Master merged

`origin/master` `7e8eee41` (TASK-973, the production write barrier) merged
into this branch before anything touching `store` was run, as instructed.
No conflict. Master touched `src/generate.py` and four test modules this
branch also changes; the merge is clean and TASK-942's token-budget work
states no word band, so it adds no new authority for a number this task
owns - checked by grep rather than assumed.

