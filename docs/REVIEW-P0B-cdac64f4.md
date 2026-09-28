# Independent review: P0-B copy engine, head `e4e2a35d`

**Head under review:** `e4e2a35da6445cac890b8a521b4ea7aab7ef0280`
on `origin/task-p0b-copy-engine-pareto`
**Reviewed against:** `origin/master` = `35001d6c87679f6e9e5f4662ba097b1a053ae9bf`
(master moved twice during this review: `8399b728` → `f50a61f5` →
`3208de98` → `35001d6c`)
**Reviewer:** independent review agent, own worktree, branch `review-p0b-cdac64f4`
**Date:** 2026-09-28
**Provider writes:** 0. No Slack post. No merge, no push to the branch under review.

### Re-pointed from `cdac64f4`, and why every code finding carried over

This review began against `cdac64f4` and was re-pointed at `e4e2a35d` when the
branch was pushed again. **`git diff cdac64f4 e4e2a35d` touches no `src/` file
at all** — only `docs/P0B-COPY-ENGINE-PARETO-2026-09-28.md` (+51) and
`tests/test_the_research_pack_has_one_shape.py` (+96). Verified by blob hash:

| file | `cdac64f4` | `e4e2a35d` |
|---|---|---|
| `src/generate.py` | `142f956f` | `142f956f` |
| `src/generate_campaign.py` | `c8b39652` | `c8b39652` |
| `src/copystages.py` | `a68ba679` | `a68ba679` |
| `src/sequencegate.py` | `81d6dfaa` | `81d6dfaa` |
| `src/quality.py` | `516caead` | `516caead` |

So every measurement in sections 1-5, 7, 8 and F3 was taken against source
that is byte-identical to `e4e2a35d`, and every finding stands unchanged. Two
new findings come from the re-point and are in sections **T1** and **T2**.

---

## Verdict

**DO NOT MERGE** `e4e2a35d` as it stands.

Four blocking defects, all small fixes:

- **B4 — the branch's headline enforcement change does not fire in
  production.** The tenant guard compares the offers **filename slug**
  (`'productive'`) against the client config's **display name**
  (`'Productive'`), and `src/generate.py` always passes the config object. So
  the sequence-gate verdict is still *"stored on the result for nobody"* on
  the only path production uses. It is live in exactly one test — the one the
  author had to fix — which is why it read as tenancy scoping working.
- **B3 — the safety one. The new figure gate is wired into the EMAIL branch
  only, so a fabricated benchmark in a LinkedIn message reaches a real
  prospect unchecked** — on the very surface this branch widened from four
  messages to five.
- **B1.** `_WORDED_QUANTITY` **never consults the support set.** It refuses
  unconditionally, so it is a check that cannot pass, and it refuses ordinary
  English (`"half an hour"`, `"double-check"`, `"I wrote twice"`). Its refusal
  sentence asserts *"no stored fact supports"* — a claim the code never tests.
- **B2.** The date exemption `\d{1,2}/\d{1,2}` **exempts fabricated ratios.**
  `"a 60/90 budget burn split"` — the certified run's own figures, the ones
  this gate was written to catch — passes. So do `70/30` and `90/10`.

**The suite does NOT block, and I settled it myself.** 13,652 tests, 123
distinct failing names against the 128-name baseline, **6 in / 11 out** —
reproducing the author's arithmetic exactly. All six "in" are accounted for:
four inherited (proved by running a clean `42a5c5e0` tree and, for one, by
measuring the offending strings rather than trusting the file list), one the
branch's own and **fixed in `e4e2a35d`**, one the documented intermittent
loopback test that passes alone. **No new failure is attributable to the
branch.** Detail in 6a/6b.

Everything else the author claimed, I could verify. `sequencegate.py` is
untouched byte for byte, the repetition gate's rule and threshold are untouched
byte for byte, `li5` genuinely blocks, a failed draft genuinely cannot be
stored, and the `step_objectives` result is not in dispute. The branch fixes
real, operator-found defects and every blocker below is a small fix.

Four further findings are non-blocking but should be recorded before merge:
the P.S. is stored ungated and rendered nowhere (F3), three of the branch's
own claims are pinned by no test (M3/M7/M8 mutations survived — M7 is B4 seen
from the other side), `no_repetition/subjects` can no longer fire on the
Productive path (1d), and merging this branch is what makes master's approved
LinkedIn cap change live, which nothing tests (T2).

---

## 0. The merge base — the trap, and what it actually is

**CLAIM:** the branch was based on `d0e95d20` because that is where the 18
refusals were measured.
**AUTHORITY:** `git merge-base --all cdac64f4 origin/master`.
**MEASURED AT:** 2026-09-28, this worktree.
**STATE: VERIFIED, with a correction that matters.**

There are **two** merge bases. The history is criss-cross:

    d0e95d20e0b88adcf80bec88fd5898a1f8ca01a7
    2d54e274f1dbf646907073047ede73b5999ab273

A plain `git merge-base cdac64f4 origin/master` returns `d0e95d20`, and
`git log d0e95d20..cdac64f4` then lists **23 of master's own commits** as
though the branch had authored them. That is the misattribution the brief
warned about, and it reproduces exactly.

The honest sets are the two-dot ones:

| Question | Command | Result |
|---|---|---|
| What does the branch add? | `git log origin/master..e4e2a35d` | 7 commits + 1 merge |
| What does master have that it lacks? | `git log e4e2a35d..origin/master` | 13 commits |

Branch-only commits: `60f75236`, `279dded9`, `2bf960cb`, `de04b0ff`,
`cdac64f4`, `4d7ca8be`, `e4e2a35d`, plus merge `42a5c5e0` (which merges
`origin/task-425-one-account-dry-run`, content already on master via
`439aa169`).

**The real P0-B content surface is `git diff 42a5c5e0 e4e2a35d`** — 15 files,
2,194 insertions, 66 deletions (3 of them `src/`).
Reviewing `git diff origin/master e4e2a35d`
instead shows ~1,860 spurious deletions that are master's own doc and state
churn, not the branch's work.

**No silent revert.** Master's 10 commits touch only `CLAUDE.md`,
`WEB-READINESS.md`, `config/model-prices.yaml`, `docs/**`, `docs/state/**` and
`scripts/task425_one_account_dry_run.py`. The branch touches
`src/copystages.py`, `src/generate.py`, `src/generate_campaign.py`,
`tests/**` and one new doc. **The two sets do not intersect**, so merging
reverts nothing of master's.

---

## 1. Is any gate weakened, widened, or made inert?

### 1a. `sequencegate.py` — the author's central claim

**CLAIM:** `sequencegate.py` was NOT modified; only its inputs were corrected.
**AUTHORITY:** git blob hashes.
**STATE: VERIFIED, byte for byte.**

    42a5c5e0:src/sequencegate.py   81d6dfaa0c18bfd87709194c09cd10ce2e13fec8
    cdac64f4:src/sequencegate.py   81d6dfaa0c18bfd87709194c09cd10ce2e13fec8
    origin/master:src/sequencegate.py  81d6dfaa0c18bfd87709194c09cd10ce2e13fec8

One blob at all three points. The claim holds.

### 1b. Every other gate module

`git diff --name-only 42a5c5e0 cdac64f4` returns exactly three `src/` files:
`copystages.py`, `generate.py`, `generate_campaign.py`.

Unchanged, therefore: `copylint.py`, `packfacts.py`, `killswitch.py`,
`claims.py`, `lint.py`, `quality.py` (blob `516caead` at all three points),
`cadencelibrary.py`, `sequenceplan.py`, `bisonfactory.py`,
`heyreachfactory.py`, `render.py`, `approve.py`.
`copylint._traces` is intact at `src/copylint.py:257`.

### 1c. The one change in enforcement — and it is a tightening

The branch adds, inside the retry loop
(`generate_campaign.py`, around line 1181):

```python
if offer is not None and client_name and (
        str(client_name) == _offer_library_tenant()):
    failures = failures + [
        "sequencegate %s/%s: %s" % (...)
        for f in (result["sequence_gate"].get("failures") or ())]
```

Before this, `sequencegate`'s verdict was computed and stored on the result
and **read by nobody in the loop**; enforcement happened later at
`bisonfactory._refuse_sequence_gate`, which is unchanged and still refuses the
whole push. So a refusal now *costs a writer attempt* where before it arrived
after the copy was already stored. **This can only refuse more copy than
before, never less.** Not a weakening.

**But see B4: on the path production uses, this condition is never true, so
the change refuses nothing at all.** The direction is right; the wiring is
not.

### 1d. The one place enforcement genuinely goes down — report this to the operator

**CLAIM (mine, not the author's):** `no_repetition/subjects` can no longer
fire on the Productive path.
**AUTHORITY:** `src/sequencegate.py:420-436`, plus the branch's new
`threads=_threads_for(_subj)` argument.
**STATE: VERIFIED.**

The branch starts passing `threads=` to `sequencegate.check`. With
Productive's one-thread cadence, `per_thread` collapses to a single subject,
`len(subs) < 2`, and the check emits a **warning** — *"this cadence opens 1
thread(s), so there are 1 thread subject(s) to compare and duplicate thread
subjects could NOT be checked"* — instead of a verdict. The branch
**deliberately excludes warnings** from the retry failures.

This is defensible and honestly built: the `threads` handling is pre-existing
code in master (`sequencegate.py` is unmodified), it is the operator's own
ISSUE-054 ruling, one subject genuinely cannot duplicate itself, and the
"could NOT be checked" wording was written precisely so this would not go
silent. But the operator should know the consequence plainly: a check the
author measured refusing **256 of 1,323 stored contacts** now cannot fire on
that surface, and its "not checked" signal is filtered out of the loop that
would act on it. That is a real reduction in refusals, correctly reported
rather than hidden.

---

## 2. The new `_invented_quantities` figure gate

Attacked in both directions. It does what the author says on the inputs the
author names — and it has three holes the author did not name, two of them
blocking.

Support set for every case below: the record's own research carries
`2 week delivery cycles` and `launched ... in 2016`, so `2` and `2016` are
stored and `60`, `73`, `41` are not.

### What works (negative and positive controls both hold)

| Input | Expected | Measured |
|---|---|---|
| `Decisions at 60% budget burn versus 90% differ.` | REFUSED | REFUSED |
| `It has three times the impact on final margin.` | REFUSED | REFUSED |
| `We improved margin by 15% last quarter.` | REFUSED | REFUSED |
| `That would double your delivery throughput.` | REFUSED | REFUSED |
| `Your 2 week delivery cycles are unusual.` (stored) | PASSED | PASSED |
| `Since 2016 the healthcare practice has run.` (stored) | PASSED | PASSED |
| `On 2024-10-17 we spoke about the key.` | PASSED | PASSED |
| `On 17 October Jesse asked about the list.` | PASSED | PASSED |
| `A 5 minute call would settle it.` (1 char) | PASSED | PASSED |

Every row of the author's own "CAN IT STILL FAIL, AND ON WHAT INPUT?" table
(`docs/P0B-COPY-ENGINE-PARETO-2026-09-28.md` §7) reproduces exactly as they
report it. **All four of my findings sit in rows that table does not have:**

| The table tests | It does not test |
|---|---|
| a fabricated numeric figure | a fabricated figure written `60/90` (**B2**) |
| a worded quantity with no support | a worded quantity the pack **does** support (**B1**) |
| copy in an email step | copy in a **LinkedIn** step (**B3**) |
| a day-and-month date | a **year** (**F1**) |

That is not a criticism of the author's honesty — the table is accurate. It is
the reason an independent pass was worth running: the falsification set was
built from the failure that was found, and the holes are one axis out from it.

### B3 — BLOCKING, and the one that reaches a prospect. The gate covers email steps only

**CLAIM:** *"This runs in the GENERATOR's own refusal path (`_step_refusals`),
on copy being written now... a draft that asserts an unsupported figure is
regenerated... this closes the copy path and only the copy path."*
**AUTHORITY:** `_step_refusals`, `src/generate.py`.
**STATE: REFUTED. It closes the EMAIL copy path and only that.**

`_step_refusals` branches on channel. The LinkedIn branch runs
`lint.check_linkedin` and nothing else:

```python
if step.get("channel") == "linkedin":
    failures = lint.check_linkedin(trial, key, step)
    content = [f for f in failures if f not in lint.LINKEDIN_HELD_CODES]
    text = step.get("note") or ""
else:
    ...
    unsupported = claims.check(text, trial, contact)
    invented = _invented_quantities(text, trial, contact, pack_support)
    repeats = _quality_of(...)
```

No `claims.check`, no `_invented_quantities`, no `_quality_of` on a LinkedIn
note. Measured through the live path, `li4` carrying the writer's `msg3`:

    stored note : Rowan, we cut delivery overhead by 73% across 41 studios
                  and tripled margin last year.
    refusal     : None                      <- stored as a send candidate

    the identical text handed to the gate directly:
      the figure 73 appears in no stored fact...
      the figure 41 appears in no stored fact...

**And nothing else catches it.**

- `copylint.untraceable` on that note → `[]`; `check_batch` reports
  `untraceable_company_claim: 0`. That is the `COMPANY_CLAIM` blind spot which
  is the stated reason `_invented_quantities` exists at all.
- `sequencegate`'s `claims_supported` iterates **emails only**
  (`src/sequencegate.py:297`, `for step, body in sorted(emails.items())`), so
  LinkedIn bodies are never put through it. `sequencegate` reads LinkedIn text
  only for `hypothesis_not_asserted` and `channels_complement`.

**Why this is the most serious of the three.** Unlike the P.S. (F3), LinkedIn
notes genuinely reach a person: `heyreachfactory.COPY_MAPPING` maps
`li1..li5` onto `connection_note` and `connected_1..4`, and
`heyreachfactory.py:251` sources the words from the record's own cadence —
which is exactly where `_candidate_steps` stores them. So this is a live
prospect-facing path, not a latent one.

The asymmetry between the two branches is pre-existing. What this branch does
is add the figure gate to one side of it while **widening the unguarded side
from four LinkedIn messages to five**. The task's own framing — "the gate that
should have fired" — applies to `li1..li5` as much as to `em1..em5`.

### B1 — BLOCKING. `_WORDED_QUANTITY` is a check that cannot pass

**CLAIM:** the worded-quantity branch refuses a quantity "no stored fact
supports".
**AUTHORITY:** `src/generate.py`, the second loop of `_invented_quantities`.
**STATE: REFUTED.**

```python
for worded in _WORDED_QUANTITY.findall(str(text or "")):
    out.append("%r states a quantity no stored fact supports; a figure "
               "spelled as words is still a figure" % worded)
```

There is **no membership test against `stored`**. The numeric loop directly
above it has one (`cleaned not in stored`); this one does not. So the branch
refuses on match alone, regardless of support, and the sentence it emits
states something the code never checked.

Measured with a record whose research literally reads
*"Brightmoor Studio **doubled** its delivery throughput and halved cycle
time, **twice** audited"*:

| Input | Support contains the word? | Measured |
|---|---|---|
| `That would double throughput.` | yes — "doubled" | **REFUSED** |
| `It was audited twice.` | yes — "twice" | **REFUSED** |
| `Half of the work is done.` | — | **REFUSED** |

And on ordinary English, through the live
`_candidate_steps -> _step_refusals` path:

| Input | Measured |
|---|---|
| `Let me double-check that before I say more.` | **REFUSED** |
| `I wrote twice last year and got no reply.` | **REFUSED** |
| `Half an hour would be enough to settle it.` | **REFUSED** |
| `Half the team had changed by then.` | **REFUSED** |

`"half an hour"`, `"double-check"` and `"I wrote twice"` are exactly the
register a re-engagement sequence writes in. Each one now costs a writer
attempt, and after `MAX_WRITER_ATTEMPTS = 3` the contact is held with
`hold_kind="copy_refused"`. This branch exists to make the copy engine
converge; this gate pushes it the other way, and does so while asserting a
falsehood in the operator-visible reason.

**Why it shipped:** the author's own file preamble sets the standard —
*"every tightening below is paired with a POSITIVE control (it fires on bad
copy) and a NEGATIVE control (it does not fire on good copy)"*. For
`_WORDED_QUANTITY` there is **only a positive control**
(`test_a_quantity_spelled_as_words_is_still_a_quantity`). Every negative
control in the class (`test_it_does_not_refuse_a_figure_the_pack_supports`,
`test_a_figure_licensed_by_the_PLANS_facts_is_not_refused`,
`test_the_pack_does_not_license_a_figure_it_never_mentions`) exercises the
**numeric** branch only. The missing negative control is the whole reason
this got through.

### B2 — BLOCKING. The date exemption exempts fabricated ratios

**CLAIM:** the exemption is *"narrow on purpose"*; it exempts a number only
beside a month name or in an ISO/slashed date, and *"`we recovered 17% in
October` is NOT exempt — the percent sign is not part of a date — so the
benchmark catch is untouched"*.
**AUTHORITY:** `_DATE_FIGURE`'s fourth alternative,
`(?:\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b)`.
**STATE: REFUTED.**

A slash between two small integers is treated as a date, so any fabricated
ratio written that way is exempted whole. Measured through the live
`_step_refusals` path:

| Input | Measured |
|---|---|
| `Decisions at 60% burn versus 90% differ sharply.` | REFUSED |
| `Decisions at a 60/90 burn split differ sharply.` | **PASSED** |
| `We normally see a 70/30 split in margin recovery.` | **PASSED** |
| `Early intervention gives a 90/10 recovery rate.` | **PASSED** |

The first and second rows carry the **same two fabricated figures from the
certified run's own `em4`** — the input this gate was written for. One
character of punctuation is the whole difference between a refusal and a send
candidate.

### F1 — non-blocking but wrong. A calendar year is refused

**CLAIM:** *"Referring to WHEN something happened is not the defect this check
exists to catch... A day number beside a month name is neither, and refusing
it would refuse every legitimate reference to a real prior conversation."*
**STATE: the intent is right; the implementation misses years.**

`_DATE_FIGURE`'s month branches are `\d{1,2}` only, and a bare year matches no
branch at all:

| Input | Expected by the gate's own rationale | Measured |
|---|---|---|
| `We last spoke in October 2024 about this.` | PASSED | **REFUSED** (`the figure 2024...`) |
| `The practice has been running since 2019.` | PASSED | **REFUSED** |
| `Nothing has been decided since Q1 2025.` | PASSED | **REFUSED** |

Also live through `_step_refusals`. This is the same class as the two false
refusals the author found and fixed; a third one survives. The author's own
fixture escapes it only because `2016` happens to be a stored fact.

### Completeness gaps in `_WORDED_QUANTITY` (record, do not block)

Not caught: `halve`/`halved`, `eleven times` and above, `a hundred times`,
`orders of magnitude`. A miss in a tightening is not a regression, so these
are noted rather than blocking — but they show the word list is a heuristic,
which is another reason it must consult the support set (B1) rather than
refuse on sight.

---

## 3. The repetition gate

**CLAIM:** the rule and the threshold are untouched; only the sibling set
changed, from `subject + body` to bodies only.
**AUTHORITY:** blob hash of `src/quality.py`; live runs of `_quality_of`.
**STATE: VERIFIED.**

`src/quality.py` is blob `516caead1e2575717f090bff9609b0654b2ffe21` at
`42a5c5e0`, `cdac64f4` and `origin/master`. `_REPETITION_OVERLAP = 0.50` and
`_REPETITION_MIN_SHARED = 3` are therefore untouched by construction.

It still collides. Measured through `_candidate_steps -> _step_refusals`, one
thread, all five steps sharing the opener's subject:

| Case | Measured |
|---|---|
| five distinct bodies | no repetition refusal |
| `em3` byte-identical to `em1` | **COLLIDES** (all five steps refused) |
| `em3` a genuine paraphrase of `em1` | **COLLIDES** (all five steps refused) |

The author's reported 44.4% / 50.0% / 43.8% progression is consistent with
what I measure, and the gate is not hollowed out.

**But the change is pinned by no test.** See M3 in section 7: reverting the
sibling set to `subject + body` fails **nothing**, across 42 related test
modules. `test_a_shared_subject_alone_does_not_collide_two_distinct_steps`
does exercise `_quality_of`, but its chosen bodies sit far enough apart that
re-adding the subject does not tip them. The one fixture pair that *would*
have detected it — `test_generate.py`'s HARBOURLINE `em1`/`em3` — was
rewritten in this same branch to argue different things, which removed the
only witness. The fix fails safe (a revert makes the gate stricter, not
looser), so this is a coverage gap, not a defect.

---

## 4. "Missing content BLOCKS"

**CLAIM:** `li5` rendering nothing is now a refusal, not a silent 4-of-5, and
a missing P.S. blocks.
**STATE: VERIFIED for `li5`. PARTLY VERIFIED and UNPINNED for the P.S.**

Measured against `PRODUCTIVE_LI_HEAVY_V1` with a sendable contact on a profile:

| Case | `_content_shortfall` | `_campaign_validator` |
|---|---|---|
| `msg4 = ""` | names `li5` — *"LinkedIn step li5 came back empty (empty)"* | REFUSES |
| `em3 = ""` | names `em3` — *"email step em3 came back empty (empty)"* | REFUSES |
| `msg4 = "   "` | not named (truthiness, not `.strip()`) | REFUSES (via `lint.check_linkedin`) |
| `em3 = "   "` | not named | REFUSES |

**A step rendering to nothing cannot pass as 4-of-5.** With `msg4 = ""`,
`_candidate_steps` builds exactly `['li1','li2','li3','li4']` and the
validator refuses the contact. Confirmed.

Two things to record:

- **Whitespace-only content is not named by the shortfall check** because both
  it and `_candidate_steps` test truthiness rather than `.strip()`. The
  contact still blocks, via lint, so this is a reporting nit rather than a
  hole — but the operator reading the hold will not see `li5` named.
- **A missing P.S. is not checked by `_content_shortfall` or
  `_campaign_validator` at all.** Measured: with no `ps_em1`/`ps_em3`
  anywhere, both return nothing. The only block is
  `generate_campaign.missing_required` (lines 1011-1017, folded in at 1190),
  and **mutation M8 shows that block is pinned by no test** — removing
  `failures = failures + missing_required` fails nothing across 42 modules.
  Compounding it, `tests/base.py`'s `writer_answer` now supplies a **default
  P.S. to every fixture**, so no existing test can reach the refusal either.
  A grep of `tests/` for the refusal text finds nothing.

---

## 5. The sequence-gate read inside the retry loop

**CLAIM:** this cannot cause a draft that failed a gate to be stored as a send
candidate. Operator decision 2 is absolute.
**AUTHORITY:** `src/generate_campaign.py:940-1210`, read in full.
**STATE: VERIFIED.**

- `result["sequences"]` and `result["subjects"]` are **wholly reassigned at the
  top of every attempt** (lines 958-969), so no content from a failed attempt
  can survive into a later one.
- The sequence-gate read only ever **appends** to `failures`, so it can only
  prevent the `if not failures: break`. It cannot cause a store.
- Every exit that is not a clean break empties the copy:
  writer hold → `sequences = {}`, `subjects = {}` (953-954);
  attempts exhausted → `sequences = {}`, `subjects = {}`, `hold_kind =
  "copy_refused"` (1206-1207); pipeline defect → same (1261-1262).
- `llm.ModelError` propagates rather than being written onto the record.

The invariant holds: a draft that failed a gate is never stored.

**Unpinned, though.** Mutation M7 — replacing the tenant condition with
`if False:` so the sequence-gate verdict is never read in the loop — **fails
nothing** across 42 modules. The branch's headline enforcement change has no
test.

---

## 6. Suite: baseline as a SET, not a count

**CLAIM (author):** 1,532 tests across 66 modules, 10 failures, all in
baseline; the full 12,737-test suite **UNKNOWN, still running**.
**BASELINE:** `docs/state/SUITE-BASELINE-2026-09-26.txt` — 128 distinct
fully-qualified failing names, master `0af11fcb`.

**STATE: see 6b for the set diff.** Run by this review, full
`python -m unittest discover -s tests -v`, compared as sets. `^FAIL:` was
never grepped mid-run — only `suite_verdict.txt` on completion.

The run was started against `cdac64f4` before the re-point. It remains valid
for `e4e2a35d` because the two heads are byte-identical in `src/` (see the
header table); the only test file that differs is
`tests/test_the_research_pack_has_one_shape.py`, which I ran separately from a
clean `e4e2a35d` tree: **19 tests, OK** — so the author's fix for it works.
The branch's own new file also passes there: **40 tests, OK**.

### 6a. The "four are not mine" claim — verified independently, by my own revert

**CLAIM:** of the 6 failures absent from the baseline, 4 are not the branch's;
proved by swapping the three source files for their merge-commit versions.
**MY METHOD, deliberately stronger than a three-file swap:** a clean
`git archive 42a5c5e0` tree — the branch's merge commit, i.e. every branch
file *without* any of the five P0-B commits — and run the suspects there.
**STATE: VERIFIED for the suspects I could identify ahead of the full set.**

Ran 183 tests at `42a5c5e0` across the modules touching the files the author
named (`productive-offers.yaml`, `docs/qwen-tasks/`, `cadencelibrary.py`)
plus the modules my own mutation runs had shown red. **11 failures**, and they
are the same 11 my wide mutation baseline saw against the branch — identical
with and without P0-B. Cross-referenced against the 128-name baseline:

| at `42a5c5e0`, no P0-B changes | in baseline? |
|---|---|
| `test_all_linkedin_steps_affected` | yes |
| `test_full_linkedin_shape` | yes |
| `test_all_unusable_means_empty_public_evidence` | yes |
| `test_hook_step_also_filters_unusable` | yes |
| `test_unusable_rows_are_excluded_from_public_evidence` | yes |
| `test_fresh_rows_come_first_after_refresh` | yes |
| `test_strong_before_medium` | yes |
| `test_no_test_fixture_carries_a_real_looking_slack_token` | yes |
| `test_successful_regeneration_replaces_all_notes` | yes |
| **`test_approval_status_is_not_defaulted_to_approved`** | **NO** |
| **`test_the_campaign_file_is_gitignored`** | **NO** |

The last two are **absent from the baseline and fail with no P0-B code
present**. They are inherited, not the branch's — confirmed by my own revert,
not by the author's. `test_approval_status_is_not_defaulted_to_approved` reads
`productive-offers.yaml`, which is one of the files the author named and which
the branch never touches.

This independently corroborates the author's claim and master's own
`TASK-549` ("the suite baseline is stale on master, found twice
independently", filed as `35001d6c`). **The baseline is stale**, so a strict
"any name not in the baseline BLOCKS" reading would block this branch for
failures master already had. I apply the rule as it is meant: a new failure
blocks only if it is *caused by the branch*, and causation is settled by
revert-and-rerun, not by set membership alone.

---

### 6b. The full suite, run by this review, compared as SETS

**STATE: SETTLED. The suite does NOT block. No new failure is attributable to
the branch.**

    Ran 13652 tests in 2053.068s
    FAILED (failures=97, errors=26, skipped=15, expected failures=18)
    -> 123 distinct fully-qualified failing names

13,652 tests — the author's reported count, reproduced. Against the 128-name
baseline, parsed and diffed as sets (never as counts):

| | |
|---|---|
| baseline distinct failing names | 128 |
| this run distinct failing names | 123 |
| **in** (failing here, not in baseline) | **6** |
| **out** (in baseline, not failing here) | **11** |
| same name, FAIL↔ERROR kind flipped | 0 |

**My arithmetic reproduces the author's exactly: 6 in, 11 out.** And the trap
is real — 123 against 128 reads as a five-name improvement while six new names
hide inside it. The count is not the measure.

**All six accounted for, and none is the branch's fault:**

| # | name | disposition | how I established it |
|---|---|---|---|
| 1 | `test_an_offer_cannot_be_invented…test_approval_status_is_not_defaulted_to_approved` | INHERITED | fails at a clean `42a5c5e0` tree, no P0-B code present |
| 2 | `test_fixture_hygiene…test_every_email_address_is_on_a_reserved_domain` | INHERITED | see below — the offending strings are unchanged by the branch |
| 3 | `test_fixture_hygiene…test_no_real_client_prospect_or_roster_domain` | INHERITED | 37 hits, all `productive.io` in `config/clients/*.yaml`, `docs/**` and `docs/evidence/case-studies/*.json` — no branch file among them |
| 4 | `test_the_cadence_reacts_to_what_the_prospect_did…test_the_meeting_reaches_the_send_gate_too` | INHERITED | fails at a clean `42a5c5e0` tree |
| 5 | `test_the_research_pack_has_one_shape…test_the_literal_acceptance_call_produces_copy` | **the branch's own — FIXED in `e4e2a35d`** | ran the module from a clean `e4e2a35d` tree: 19 tests, OK |
| 6 | `test_upload_is_never_truncated…test_nothing_is_imported_by_the_refusal` | ENVIRONMENTAL, intermittent | HTTP 413 then a secondary read failure on loopback; passes alone at `e4e2a35d` (7 tests, OK) |

**#2 deserves the detail, because the author's attribution was incomplete and
I nearly scored it against the branch.** The failure names nine offending
files, and **five of them are test files this branch modifies**
(`test_changing_an_approved_fact_changes_the_output.py`,
`test_task400_rework2.py`, `test_the_entrypoint_actually_loads_its_skills.py`,
`test_the_entrypoint_is_the_only_generation_path.py`,
`test_the_entrypoint_refuses_at_a_client_ceiling.py`), each for the
non-reserved domain `testcorp.com`. The author's summary says the inherited
failures "name files the branch never touches", which is not true of this one.
So I measured the strings rather than the filenames — occurrences of
`testcorp.com` at `42a5c5e0` versus `e4e2a35d`:

    5 -> 5   tests/test_changing_an_approved_fact_changes_the_output.py
    9 -> 9   tests/test_task400_rework2.py
    4 -> 4   tests/test_the_entrypoint_actually_loads_its_skills.py
    5 -> 5   tests/test_the_entrypoint_is_the_only_generation_path.py
    4 -> 4   tests/test_the_entrypoint_refuses_at_a_client_ceiling.py

Identical. **The branch edits those files but adds none of the offending
strings** (its own new fixtures correctly use the reserved `testcorp.test`).
Inherited — but established by content, not by the file-level claim, and the
file-level claim as written would not have survived checking.

**#6, not dismissed.** CLAUDE.md requires an intermittent be diagnosed alone,
as a class, and in an isolated full run. Alone: passes. Its traceback is a
loopback `HTTPError: 413` followed by a failed `e.read()` inside
`http.client`/`tempfile` — the documented overlap CLAUDE.md names ("both bind
loopback and build demo estates… one HTTP test fails intermittently"). Neither
the test nor the web upload path is touched by this branch.

**The 11 "out" are not claimed as fixed**, by the author or by me: five in
`test_a_resume_leaves_a_ledger_row` (which the baseline itself flags as
PRE-EXISTING RED and warns not to read either way), four in `test_e2e`,
`test_secrets…test_every_classified_variable_is_in_the_example`, and
`test_set_regeneration…test_model_calls_are_counted`. Their not reproducing
here is environment, not repair.

**And the baseline itself is the problem.** Four of the six "in" fail on code
that predates this branch, which is `TASK-549` on master
(`35001d6c`, "found twice independently"). A literal "any name absent from the
baseline BLOCKS" would block this branch for master's own failures. The rule's
purpose is to catch failures *the branch caused*; causation is settled by
revert-and-rerun, and by that test **the branch caused none**.

---

## 7. Mutation testing — my own harness

Thirteen mutations, run on an **isolated copy** of the tree (so the full suite
running in the worktree could not be perturbed), with the two assertions this
repository learned to demand:

1. the mutated bytes really reached disk (`sha256` before ≠ after) — a
   mutation that never applied is indistinguishable from a killed one;
2. the source was restored **byte-identical** afterwards.

Baseline green before every mutation. Target: the branch's own new test file
plus `test_generate`, `test_only_the_last_subject_may_claim_finality`,
`test_task400_rework2/3`; the three survivors were then re-run against **42**
related modules.

| # | Mutation | Verdict |
|---|---|---|
| M1 | `_PLAN_LINKEDIN_ORDER` back to four writer keys | KILLED (2) |
| M4 | `_invented_quantities` returns nothing | KILLED (8) |
| M5 | the P.S. is not carried onto the step | KILLED (1) |
| M6 | `_plan_subject_of` back to the hardcoded three-thread map | KILLED (3) |
| M9 | the worded-quantity branch removed | KILLED (5) |
| M10 | the LinkedIn shortfall branch silenced (the old silent `break`) | KILLED (3) |
| M11 | `_content_shortfall`'s verdict not read by the validator | KILLED (1) |
| **M3** | **repetition gate back to `subject + body` siblings** | **SURVIVED** |
| **M7** | **sequencegate verdict no longer read in the retry loop** | **SURVIVED** |
| **M8** | **`missing_required` no longer reaches `failures`** | **SURVIVED** |

**Source integrity after every mutation, verified by hash:**

    src/generate.py           5c0436b9d2fd459d7df72e2b9e6916ff7cbcdd888423306f8d5c2793b2558eec
    src/generate_campaign.py  b1e4e31e151c07cda55b368dff62e57d2e0e2e6f1409153f898c95ed1872ef88
    src/copystages.py         a8b66d8698c562a5c40166f998be1bb64de4c0bae60c71140b711696063b2150

These match the worktree's own files exactly, and `git status --porcelain`
reports no modification to any tracked file. Nothing was left mutated.

The author reported one mutation that initially SURVIVED and was then pinned.
I find **three** that survive now — M3, M7, M8 — each covering a claim the
branch makes in its own commit messages.

---

## 8. Scope drift and silent revert

Every changed line answers to P0-B. Three `src/` files, one new doc, ten test
files. No reformatting, no drive-by renames.

- `copylint._traces` — intact, `src/copylint.py:257`, file unmodified.
- `packfacts` claim-licensing — file unmodified.
- killswitch gates — file unmodified.
- `bisonfactory._refuse_sequence_gate` — file unmodified; still refuses the
  whole push before any provider write.

**Test changes reviewed for weakening; none found.** The one that looked most
like a relaxation is the opposite:
`test_only_the_last_subject_may_claim_finality` moved its falsifier from
`subject_alt` to the opener's `subject`. Under the one-thread ruling
`subject_alt` reaches no step, so the old falsifier was **vacuous** — it would
have passed for a `copylint` that had stopped reading subjects entirely. The
new form drives the subject that actually ships. That is a strengthening.

`tests/base.py`'s fixture changes (a fifth LinkedIn message, a default P.S.,
a rewritten `msg3`) are required by the new contract. The side effect worth
recording is the one already noted in section 4: supplying a default P.S. to
every caller removes any incidental coverage of the missing-P.S. refusal.

---

## F3 — the P.S. is stored ungated, and rendered nowhere

Non-blocking today only because nothing sends it. Both halves are defects.

**F3a — nothing consumes `step["ps"]`.**
`git grep` for `"ps"` across `src/` returns: `copylint.py:192` (a **lead**-level
`ps`), `sequencegate.py:255` and `:438` (a **sequence**-level `ps`),
`generate_campaign.py:1012/1060/1075` (the harvest and the two gate inputs),
and the branch's new `generate.py:2327`. **`bisonfactory.py` contains zero
`ps` references**; `render.py` reads `subject` and `body` only;
`bisonfactory`'s copy resolver refuses on `subject`/`body` alone.

So the operator's defect 1 — *"Missing P.S. on email 1 and email 3. The
artifact has no P.S. field anywhere, for any message"* — is **not** fixed on
any path that reaches a prospect. The P.S. now exists on the stored cadence
step and on no message. The branch's test asserts only
`pairs["em1"].get("ps") == "P.S. one."` — key existence, nothing more. That is
the "existence is not function" class `CLAUDE.md` names as this repository's
recurring defect, and the author's own test file states the right standard one
class earlier: *"The consumer link. A shortfall nothing reads is not a
refusal."*

**F3b — when a consumer is added, the P.S. bypasses every content gate.**
`_step_refusals` computes

```python
text = f"{step.get('subject') or ''} {step.get('body') or ''}"
```

`step["ps"]` is not in it, so `claims.check`, `_invented_quantities` and
`_quality_of` never see the P.S. `lint.check` reads only `body` and `subject`
too. Measured with an otherwise-clean five-step sequence, changing nothing but
where the fabricated benchmark sits:

| Case | Measured |
|---|---|
| baseline, no P.S. | clean — stored as send candidate |
| `We cut delivery overhead by 73% across 41 studios last year.` in the **body** | **REFUSED** — *the figure 73... the figure 41...* |
| the identical sentence in the **P.S.** | **clean — stored as send candidate**, and `step["ps"]` carries it |

The lead-level gates do not cover it either. `copylint.check_batch` reports
`untraceable_company_claim: 0` on that P.S. — the `COMPANY_CLAIM` blind spot
this branch exists to work around — and `sequencegate` touches the P.S. only
to compare the two P.S. lines to each other (`sequencegate.py:437`). So the
one newly-plumbed prospect-facing surface is the one surface the new figure
gate never inspects.

---

## B4 — BLOCKING. The new sequence-gate enforcement is INERT on the production path

**CLAIM (the branch's headline, commit `2bf960cb` "Scope the gate read to the
real tenant"):** the sequence gate's verdict is now read inside the retry
loop, so *"a REFUSAL now costs an attempt and reaches the writer, instead of
being stored on the result for nobody."*
**AUTHORITY:** `src/generate_campaign.py:458-468` and `:1181-1182`;
`src/generate.py:~3010`.
**STATE: REFUTED on the path production uses.**

The guard compares a **display name** against a **filename slug**:

    _offer_library_tenant()  ->  'productive'
        # os.path.basename(offers._offers_path()).split("-offers")[0]
        # i.e. derived from config/clients/productive-offers.yaml

And `client_name` is resolved two different ways depending on how the caller
passes the client (`generate_campaign.py:458-468`):

```python
if isinstance(client, str):     # PATH A
    ...
    client_name = client                        # 'productive'
else:                           # PATH B
    config = client
    client_name = config.get("name", "")        # 'Productive'
```

Measured:

| path | `client_name` | `== _offer_library_tenant()` |
|---|---|---|
| A — `generate("productive", ...)` | `'productive'` | **True** |
| B — `generate(clients.load("productive"), ...)` | `'Productive'` | **False** |

`clients.load("productive")["name"]` is `'Productive'` — a human-readable
label. There is no `"client"` key on the config at all (`config.get("client")`
→ `None`).

**Production always takes PATH B.** `src/generate.py`'s
`_generate_via_campaign` — "TASK-400. The real entrypoint" — loads the config
itself (raising if it cannot) and then calls:

```python
plan = generate_campaign.generate(
    client_config or client_name,   # client_config is always set here
    ...
)
```

`client_config` is a dict, so `client_config or client_name` is **always the
dict**. Measured: `isinstance(chosen, str)` → `False`.

**Consequence.** On the only path production generates copy through, the
condition at `generate_campaign.py:1181` is never true, so

```python
failures = failures + ["sequencegate %s/%s: %s" % ...]
```

never executes. `sequencegate`'s verdict is computed, stored on
`result["sequence_gate"]`, and — in the author's own words about the state
before this change — *"read by nobody in the loop"*. The branch's headline
enforcement change is **inert in production**.

It is live in exactly one place: a caller passing the literal lowercase string
`"productive"`. That is
`test_the_research_pack_has_one_shape.test_the_literal_acceptance_call_produces_copy`
— the single test the author had to fix in `e4e2a35d`. The author observed
this correctly (*"this is the one test in this file that passes the client as
the literal name"*) and drew the wrong conclusion from it: that the other
tests demonstrate tenancy scoping working, rather than that the gate fires
nowhere else, production included.

**Why this blocks even though it is not a safety hole.**
`bisonfactory._refuse_sequence_gate` still refuses the whole push before any
provider write, so no bad copy ships because of this — the author's "where the
enforcement already was" paragraph is accurate and load-bearing. What is lost
is the entire claimed benefit: closing *"the gap between the refusal and the
only loop that can fix it"*. On the real path that gap is still open, and the
task reports it closed. A reported result that rests on an inert branch is the
defect class this repository names most often, and it is a one-line fix
(compare a normalised client identifier, or resolve the tenant from the same
authority on both sides).

**It also puts the scoping exactly upside down.** Combined with **T1** below:

- in the retry loop, where a tenant guard makes the gate **inert** — the guard
  is present;
- at `bisonfactory._refuse_sequence_gate`, where the absence of a tenant guard
  means **one client's approved ladder refuses every client's push** — there is
  no guard at all.

---

## T1 — the tenancy scoping: the branch's guard is REAL and NECESSARY, and its *description* is wrong

The coordinator's challenge was the right one: *"it only fails where the tenant
matches" is also what a wrongly-scoped gate looks like.* I checked, and the
answer has three parts.

**The author's fix to `test_the_research_pack_has_one_shape` is correct.**
`e4e2a35d` supplies ladder-compliant fixture copy
(`_OFFER_B_LADDER_SEQUENCES`) instead of `CampaignModel`'s default. The test
failed because the branch's in-loop gate read started working; the response was
to make the draft comply, **not** to widen the gate or exempt the tenant. That
is the right direction and the opposite of "widen a rule to make a draft pass".

**The tenant guard is load-bearing, not defensive theatre.** I expected to find
`offer is None` for other clients, which would have made the guard redundant.
It is not. Every offer in `config/clients/productive-offers.yaml` declares
`segment: all`, and `_applies_to` treats `all` as matching any segment key:

    _select_offers('productive',  'champion') -> ['OFFER-B-OPERATIONS']
    _select_offers('acme',        'champion') -> ['OFFER-B-OPERATIONS']
    _select_offers('otherclient', 'champion') -> ['OFFER-B-OPERATIONS']
    _select_offers('',            'champion') -> ['OFFER-B-OPERATIONS']

So `offer is not None` really is true for every client, exactly as the author
says, and **without** the `client_name == _offer_library_tenant()` condition
the retry loop would spend every client's regeneration budget enforcing
Productive's operator-approved spine. The guard is necessary. Confirmed.

**But the claim about what the siblings get is wrong.** The author writes:

> The other tests here go through `_client_config()`, whose client is not
> `productive`, so the ladder is reported as UNCHECKED for them rather than
> borrowed - which is the tenancy scoping working.

It is **not** reported UNCHECKED. `sequencegate.check(...)` is still called with
`offer=` Productive's offer for those clients — the call site is unconditional;
only the *reading* of the verdict is scoped. UNCHECKED requires `offer=None`,
which `_select_offers` never returns against a populated library. So the spine
**is** borrowed and the verdict **is** computed against it; it is simply not
enforced in the loop. The scoping works at the point the author changed, and
the description of the other branch of it is inaccurate.

**And the same hazard is unguarded at the point that actually blocks the push.**
This is pre-existing on master, not introduced by P0-B, and out of scope for
this branch — but it belongs on the record because it is the same defect the
branch guards against one layer up:

    bisonfactory._refuse_sequence_gate  (src/bisonfactory.py:822)
        offer_id, offer = _offer_for(lead.get("persona"), client)
        result = sequencegate.check(..., offer=offer, ...)
        if not result.get("passed"): refused.append(...)
        ... raise FactoryRefused(...)

Measured:

    bisonfactory._offer_for('champion', 'productive')  -> OFFER-B-OPERATIONS
    bisonfactory._offer_for('champion', 'acme')        -> OFFER-B-OPERATIONS
    bisonfactory._offer_for('champion', None)          -> OFFER-B-OPERATIONS

There is no tenant condition anywhere in `_refuse_sequence_gate` (grep for
`tenant`/`productive` in `bisonfactory.py` returns only unrelated hits). So at
staging time, **one client's approved offer ladder is enforced as a hard push
refusal against every client's copy.** `bisonfactory.py` is unmodified by this
branch; this is a master finding and should be filed as one.

---

## T2 — the merge interaction master's new `lint.py` fix creates, which neither side's tests can see

**This is the finding the re-point produced, and it is the one I would want an
operator to read.**

The `lint.is_connection_note` defect is resolved on master by `f50a61f5`, so I
am not reporting it as open. But **the fix is inert on master alone, and it
becomes live only when this branch merges.**

Master's new classifier keys entirely off the step's `requires` field:

```python
CONNECTED_STATES = frozenset({CONNECTION_ACCEPTED, CONNECTED})

def is_connection_note(step):
    return (step or {}).get("requires") not in CONNECTED_STATES
```

**Master never puts that field on a generated step.** `git show
35001d6c:src/generate.py | grep -c requires` returns **1**, and that one
occurrence is an error message about contacts. The `requires` propagation onto
LinkedIn steps is **this branch's** change (`src/generate.py`, the
`_candidate_steps` LinkedIn loop).

Measured, with the branch's `_candidate_steps` output classified by each
version of `lint.is_connection_note`:

| step | `requires` the branch sets | branch `lint.py` | master `lint.py` (`f50a61f5`) |
|---|---|---|---|
| `li1` | `None` | NOTE (300) | NOTE (300) |
| `li2` | `'connected'` | NOTE (300) | **MESSAGE (1900)** |
| `li3` | `'connected'` | NOTE (300) | **MESSAGE (1900)** |
| `li4` | `'connected'` | NOTE (300) | **MESSAGE (1900)** |
| `li5` | `'connected'` | NOTE (300) | **MESSAGE (1900)** |
| `li2` as **master's** generate builds it (`{}`) | absent | — | NOTE (300) |

So:

- **branch alone:** no cap change. The author's "behaviour-neutral today,
  deliberately so" claim is VERIFIED — against the master it was written on.
- **master alone:** no cap change on the generation path either. `f50a61f5` is
  a correct fix to a classifier that nothing on the generation path currently
  feeds, so it is **an inert guard today**.
- **merged:** `li2`..`li5` move from the 300-character cap to the 1900-character
  cap. The change materialises **only on the merge**, and it is tested by
  nothing: master's new test file exercises `is_connection_note` with explicit
  `requires` values, and the branch's tests run against the old `lint.py`.

**This is not a blocker.** It is the operator-approved outcome — decision "A",
2026-09-28 — and it is exactly what "a LinkedIn message is not a connection
request" means. Merging P0-B is what *completes* master's fix. Two points for
the record:

1. Master's commit title *"neither cap moved"* is true of the constants and of
   master in isolation, but post-merge **the cap that applies to `li2`..`li5`
   moves from 300 to 1900**. Anyone reading that title as "nothing about
   LinkedIn length changed when P0-B landed" will be wrong.
2. The cap move should get one post-merge assertion, because right now no test
   covers the combination. The cheap one: build a `li2` step through
   `_candidate_steps` and assert a 1,500-character note passes
   `lint.check_linkedin` while the same text on `li1` fails.

**No textual merge conflict.** `f50a61f5` touches `src/lint.py` and a new test
file; `3208de98` and `35001d6c` touch only `docs/qwen-tasks/TODO/`. The branch
touches none of those paths. The merge bases against the new master are still
the same criss-cross pair (`d0e95d20`, `2d54e274`), so the section 0 caution
still applies.

---

## Observation — the new prompt quotes the gates' numeric thresholds to the writer

Not a defect. Recorded because it changes what the gates select for, and that
is an operator-level judgement rather than a code one.

`LADDER_BRIEF_HEADER` (new in this branch, `src/generate_campaign.py:123`)
tells the model, in the prompt itself:

> `repetition_across_rungs` refuses the whole sequence when two steps share
> three or more distinctive words AND half their vocabulary.

> A follow-up that restates an earlier email's argument is refused by
> `followup_adds_value` at 45% argument overlap.

The gates are unchanged, and this is the branch's most effective convergence
lever — a writer that knows the rule can satisfy it deliberately instead of
re-rolling blind dice, which is precisely the diagnosis the branch makes and
which I think is correct.

The cost is that naming an exact lexical boundary to a generative model
invites threshold-hugging: copy tuned to land at 49% overlap rather than copy
that genuinely argues different things. The measured gate would report clean
either way. The prompt does carry the right qualitative instruction
immediately afterwards — *"If two steps would make the same argument, change
one of them rather than rewording it"* — which is the mitigation, and the
reason I am recording this rather than objecting to it. If refusal rates fall
sharply after this merges, this is the first thing to check, and the check is
the overlap **distribution**, not the pass rate.

---

## Latent note — `_plan_subject_of` clamps silently past three threads

Not a finding today; recorded so it is not discovered later.

`_plan_subject_of` derives correctly from the real cadence — measured
`ladder_name_for(PRODUCTIVE_LI_HEAVY_V1, "email") == "email_five"`,
pattern `[False, True, True, True, True]`, giving
`{em1..em5: "A"}`, one thread, which is the operator's ruling.

But the writer contract emits only three subjects, and the mapping ends in
`_PLAN_SUBJECT_ORDER[min(thread_index, len(_PLAN_SUBJECT_ORDER) - 1)]`. So a
client declaring four or more thread starters gets:

    thread_reply_pattern = [False]*5  ->  {em1:A, em2:B, em3:C, em4:C, em5:C}

Three distinct thread *starters* sharing one subject is a threading defect,
and the clamp makes it silent rather than a refusal. **Unreachable today**:
`cadencelibrary.THREAD_REPLY_PATTERNS` holds exactly two patterns,
`email_five` and `email_eight`, and both declare exactly one starter. The
author's claim that a client opening a genuine second or third thread is
served without a code change is true; a fourth is not, and would degrade
quietly.

---

## Disclosed item 1 — `lint.is_connection_note`: CONFIRMED, and now RESOLVED ON MASTER

**Not an open finding.** The operator approved the fix and it landed on master
as `f50a61f5`, outside this branch. Recorded here because the diagnosis was
the author's, it was right, and the merge interaction it creates is **T2**
above — which is the part that still needs attention.

**STATE: VERIFIED. The author's diagnosis was right, and its decision to
report rather than fix it was right — the fix needed an operator, and got
one.** Measured below against the branch's own (pre-`f50a61f5`) `lint.py`.

- `src/lint.py:460-464` — `CONNECTION_ACCEPTED = "connection_accepted"`;
  `is_connection_note(step)` returns `(step or {}).get("requires") != CONNECTION_ACCEPTED`.
- `src/cadencelibrary.py:44-45` declares **both** `CONNECTED = "connected"`
  and `CONNECTION_ACCEPTED = "connection_accepted"`.
- `PRODUCTIVE_LI_HEAVY_V1` gives `li2`..`li5` `requires: CONNECTED`.

Measured on the real cadence:

    li1   requires=None         is_connection_note=True
    li2   requires='connected'  is_connection_note=True
    li3   requires='connected'  is_connection_note=True
    li4   requires='connected'  is_connection_note=True
    li5   requires='connected'  is_connection_note=True

    a step with NO requires (the pre-branch shape):  True

So every LinkedIn **message** is linted as a connection **request** and capped
at `NOTE_MAX_CHARS` (300) instead of `MESSAGE_MAX_CHARS` (1900). Confirmed.

**The branch's `requires` propagation is verified behaviour-neutral against
the `lint.py` it was written on**: a step with no `requires` also yields
`True`, so propagating the cadence's value changed zero verdicts at the time.
Leaving the fix to the operator was correct — it raises a cap for every
client, and "never widen a gate" outranks convergence.

**That neutrality expires on merge.** Against master's `f50a61f5` classifier
the same propagated field flips `li2`..`li5` to the 1900 cap. See **T2** — the
branch is now the half that makes master's approved fix live, which is the
intended outcome and the thing no test currently covers.

---

## Disclosed item 2 — `derive_heyreach_payload` and `msg4`: CONFIRMED in code, REFUTED as a live send gap

**STATE: the code is exactly as described. The production consequence is not.**

`src/sequenceplan.py:190` iterates four keys:

```python
for key in ("connect", "msg1", "msg2", "msg3"):
```

So `msg4` is generated, gated, stored — and absent from that projection.
Confirmed.

**But that function has no production caller.** `git grep
derive_heyreach_payload` returns its definition, `scripts/task425_one_account_dry_run.py:858`
(the dry-run artifact script) and two references in
`tests/test_the_entrypoint_is_the_only_generation_path.py`. Nothing on the
send path calls it.

The live HeyReach path is `src/heyreachfactory.py`, which is **unmodified** by
this branch and whose `COPY_MAPPING` (line 113) already reads

```python
"li5": {"role": ("connected_4",), "kind": "MESSAGE"},
```

and which sources per-lead copy from the record's own cadence
(`heyreachfactory.py:251`, `steps = ((source or {}).get("cadence") or {}).get(contact_key)`)
— where this branch now stores `li5`.

So: `msg4` is **not** silently dropped before the provider on the live path.
The gap is confined to a dry-run projection — which is very likely part of why
the certified artifact under-reported the fifth message in the first place.
The author's disclosure is honest but overstates the blast radius; it is worth
fixing for consistency, and it is not a send defect.

---

## Production state: untouched

No provider writes. No Slack post. No write to production `work/`.
Hashed from a fresh process before any work and again after all of it:

    work/queue.jsonl      dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
    work/campaigns.jsonl  00b6f103bbdb469f25a7977665e4e08339f30f2b827d9e2a3c82be560d4c5931

Identical. Mutation testing ran on a copy under the scratchpad, never in the
worktree and never against production state. `sending.live` was not touched;
the freeze stands.

---

## What I attacked and did not break

Falsification attempts that **failed** — the branch held:

- `sequencegate.py` modified in any way — blob-identical at three points.
- `quality.py` rule or threshold moved — blob-identical at three points.
- the repetition gate made incapable of firing — it collides on identical
  bodies and on a genuine paraphrase.
- a failed draft surviving into storage — every failure path empties
  `sequences` and `subjects`; attempt state is fully reassigned each loop.
- a figure the pack supports being refused (numeric branch) — passes,
  including via `_pack_support` on the campaign path.
- a date being refused — ISO, `17 October` and `October 17` all pass.
- a one-character figure being refused — passes.
- a step rendering to nothing passing as 4-of-5 — only four candidates are
  built and the validator refuses.
- master's work being reverted by the merge — the changed-file sets do not
  intersect.
- a weakened test slipped in among the test changes — the one rewritten
  falsifier was strengthened, not relaxed.

---

## What has to happen before this merges

1. **B4** — make the tenant comparison compare like with like. Resolve the
   client identifier from one authority on both sides (a slug on the config,
   or normalise `config["name"]`), and prove it with a test that drives
   `generate_campaign.generate(clients.load("productive"), ...)` — the PATH B
   production actually uses — and asserts a `sequencegate` failure costs a
   writer attempt. The current test only covers PATH A. Mutation M7 surviving
   (section 7) is the same hole seen from the other side: nothing fails when
   the verdict read is removed, because in every test but one it was never
   reached.
2. **B3** — run the content gates on LinkedIn notes too, or state explicitly
   why five prospect-facing messages are exempt from the figure check that
   the same commit added for emails. Prove it with a LinkedIn note carrying
   an unsupported figure being refused, and a note carrying a pack-supported
   one passing. `sequencegate.claims_supported` iterating `emails` only is the
   same gap one layer up and is worth naming to the operator even though
   `sequencegate.py` is out of scope for this branch.
3. **B1** — give `_WORDED_QUANTITY` the membership test the numeric branch
   has, so a worded quantity the pack supports is not refused and the refusal
   sentence stops asserting something unchecked. Add the **negative control**
   the class is missing: a pack containing "doubled"/"twice" must not refuse
   "double"/"twice", and `"half an hour"` must not refuse.
4. **B2** — stop `\d{1,2}/\d{1,2}` exempting ratios. Require a date context,
   or drop the slashed-date branch and let ISO and month-name forms carry the
   exemption. Prove `60/90`, `70/30` and `90/10` refuse while a real date
   still passes.
5. **F1** — extend the date exemption to years (`October 2024`, a bare
   four-digit year), which the gate's own stated rationale already requires.
6. **M3 / M7 / M8** — pin the three unpinned claims: a test that fails if the
   repetition sibling set goes back to `subject + body`; a test that fails if
   the sequence-gate verdict stops being read in the retry loop; a test that
   fails if `missing_required` stops reaching `failures` (which is also the
   missing-P.S. block).
7. **F3** — decide the P.S. Either render it, in which case it must go into
   `_step_refusals`'s `text` so `claims.check` and `_invented_quantities` see
   it; or state plainly that operator defect 1 is not yet fixed on the wire.
   Do not leave it stored, ungated and unsent while the task reports it fixed.

**Items 1-4 are blocking.** Items 5-7 are the conditions I would want met
before this is called done, and none of them is large.

I did not fix anything. `sequencegate.py`, `lint.py`, `quality.py`,
`copylint.py` and `packfacts.py` were not touched by this review.
