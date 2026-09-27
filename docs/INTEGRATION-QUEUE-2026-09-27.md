# INTEGRATION QUEUE — 2026-09-27

**What this is.** One pass over the unintegrated worker results, with a verdict
per result measured **against the branch head SHA**, not against master. A
verdict that does not name the branch head SHA it reviewed is void in this
project; every row below names one.

**Authority for the queue size.** `py -3 scripts/claim_task.py --status`,
run 2026-09-27 19:30 Europe/Zagreb:

    claims held:                                    0
    ready (unclaimed, deps met):                    0
    awaiting integration (a result on a branch):  140
    recoverable (branch stage, no live claim):      9
    stale branches hiding available tasks:        109

**140 results across 73 distinct branches.** That second number is the one that
matters and it is in no handoff: eleven branches carry ten or more task results
each (`qwen-worker-r9` carries eleven), so 140 results is not 140 integration
units. `scripts/task_registry.py` reports 133 QUEUED and is MASTER-ONLY; those
largely overlap the 140. A branch's task-file stage is an artifact, not task
state.

**Master moved under this pass.** The brief named `1f4d464c`. By the time the
first suite run finished, master was `1646367c`, four commits later, one of them
`cf76f099` "SAFETY: sending.live = off for productive". Every merge below is onto
`1646367c` and every verdict was re-checked against it before merging.

**Provider calls: zero.** No write, no read. Nothing launched, activated,
enrolled, attached or sent.

## RESULT

| | |
| --- | --- |
| Queue size at start | **140** results across 73 branches |
| **Resolved with a verdict** | **78** |
| — MERGE | 13 |
| — MERGE-PARTIAL | 2 |
| — REWORK | 13 |
| — CLOSE | 9 |
| — HELD for the orchestrator (TASK-364/400/426) | 3 |
| — BLOCKED-ON-CRITICAL-PATH (reserved files) | 38 |
| **Not reached this pass** | **62** |

Fifteen results were integrated onto master (13 whole, 2 partial), two were
CLOSEd with their result blocks carried over, and one merge was made and then
reverted when the suite named the regression it caused.

## SUITE DELTA

Both runs are `py -3 scripts/run_suite.py`, i.e.
`python -m unittest discover -s tests -v`, the baseline file's own command, on
this machine.

| run | commit | wall | distinct failing NAMES |
| --- | --- | --- | --- |
| before | master `1f4d464c` | 1843s | **197** |
| after the merges | `c4938c1c` | 1671s | **200** |
| **after the four fixes (confirming run)** | **`1e29ce0f`** | **1796s** | **196** |

**FINAL SET DIFF, before → confirming run: ZERO NEW FAILURES, ONE FIXED.**

    NEW FAILURES (0):
    FIXED (1):
      - FAIL test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example

That one is TASK-337 doing its job: `test_every_classified_variable_is_in_the_example`
was a baseline failure because `ANTHROPIC_API_KEY`, `GROQ_API_KEY` and
`OPENROUTER_API_KEY` were classified in `config.VARIABLES` and missing from
`config/.env.example`. Documenting them turned a red guard green.

**197 → 196 names. The integrated unit is clean by set diff, which is the only
comparison that counts here.**

**Set diff, before → after (names, never counts):**

    NEW FAILURES (4)
      + FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named
      + FAIL test_preproduction.TestTheWholeRunIsAccountedFor.test_the_queue_is_the_only_record_state_written
      + FAIL test_slack_agent_cannot_act.NoStateWriterIsCalled.test_the_agent_writes_only_inside_work
      + FAIL test_stop_buttons.ARemovalRequestFromNobodyWeKnow.test_an_unattributable_positive_still_only_holds
    FIXED (1)
      - FAIL test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example

**All four were diagnosed to a named cause inside a merged artifact and cleared
individually. None was cleared by weakening or deleting a test.**

| new failure | cause | what was done |
| --- | --- | --- |
| `test_no_real_person_or_client_named` | TASK-164's own result block quotes the real LinkedIn vanity name it was reporting as a leak | redacted in `2aa368dc`; the finding is kept, the name is not |
| `test_the_queue_is_the_only_record_state_written` | TASK-332's `enrich.py` passed `unit=unit_for(provider)`, and `unit_for` falls back to `DEFAULT_UNIT`, so every unpriced row grew `unit`, `usd_estimate`, `rate`, `rate_source` — which `spendledger.record`'s own "NOT DEFAULTED, DELIBERATELY" comment forbids | that one argument reverted in `89bc50cc`; the `report()` tripwire and `xai:ticks` kept |
| `test_the_agent_writes_only_inside_work` | TASK-332's new test wrote `addCleanup(store.use_directory, self.tmp)` in four places, discarding the restore callable `use_directory` returns, so the store stayed pointed at a deleted temp dir for every later module | corrected to the form `src/store.py:181` documents, in `1e29ce0f`; the two modules now pass together |
| `test_an_unattributable_positive_still_only_holds` | TASK-351's new branch also fires for outcomes already planning `account=HOLD`, so `_hold_account`'s idempotency guard suppresses section 2 and the audit label changes from `account_held` to `account_held_unattributed` | **the whole merge reverted** in `3fd8c9aa`; TASK-351 becomes REWORK |

Each fix was verified by re-running the named module: `test_fixture_hygiene`
down to its two pre-existing failures, `test_preproduction` down to its
pre-existing six, `test_ledger_does_not_sum_across_units` +
`test_slack_agent_cannot_act` green together (25 tests), `test_stop_buttons` +
`test_hold_reasons` + `test_replies` green but for the pre-existing
`test_every_verdict_carries_its_evidence` (127 tests).

The work was pushed to its own branch `worktree-agent-a0c5bed4fa47fe482`
first and only promoted to master after the confirming run came back with zero
new names. That is the standing rule: durability is a reason to push to a
branch, never a reason to put unconfirmed work on master.

## THE QUEUE COUNTER CANNOT GO DOWN, SO IT IS NOT A BACKLOG

Measured after everything below was merged and pushed to `origin/master`
(`a3d508c1`), `py -3 scripts/claim_task.py --status` still reports:

    awaiting integration (a result exists on a branch): 140
        TASK-164 DONE on qwen-worker-r29
        TASK-244 DONE on qwen-worker-3-task-244
        TASK-247 DONE on qwen-worker-6-task-247
        TASK-268 DONE on qwen-worker-3-r58
        ... all sixteen integrated results still listed

**Integrating a result does not decrement that number and cannot.** The check is
"a branch exists whose task file is at a result stage". Merging the branch to
master leaves the branch exactly where it was, so the count only ever falls when
somebody DELETES a branch. 140 will read 140 after the next pass too, and after
the one after that.

So "138 results awaiting integration" is a count of branches carrying results,
not a measure of unintegrated work, and it must not be used as a burn-down. It is
still the right tool for ENUMERATING the queue — that is what this pass used it
for — but the only honest progress measure is per-result verdicts, which is what
the table at the end of this file is.

One real signal did move: `ready (unclaimed, deps met)` went from **0 to 1**
(`TASK-352`). Integration unblocked a dependency, which is the effect worth
reporting.

---

## THE FIVE THINGS THIS PASS FOUND THAT NOTHING ELSE SAYS

### 1. `qwen-worker-6-r62` would have reverted provider truth by a day

TASK-336 regenerated the five derived `docs/state/*.json` files on 2026-09-26
and its branch is honest about it. Master has since been regenerated:
`docs/state/PROVIDER-CAMPAIGNS.json` on master carries
`generated_at 2026-09-27T10:17:30Z`, the branch's carries
`2026-09-26T10:11:11Z`; `docs/state/TASK-REGISTRY.json` the same
(`2026-09-27T10:10:26Z` against the branch's snapshot). **Merging the branch
would have moved provider truth backwards by a day.** Only the hand-authored
part — `PROBLEM-REGISTER.md` ISSUE-046 and ISSUE-047 — was taken, and ISSUE-047
was corrected on the way in (below).

A derived file is never merged from a branch; it is regenerated on master by its
own generator. Three are still stale there: `LEDGER.json` (2026-09-20),
`QUEUE-MANIFEST.json` (2026-09-20), `SENDER-CAPACITY.json` (2026-09-21), plus
`READY-RESERVOIR.json` (2026-09-18, whose generator `build_ready_reservoir.py`
crashes with `KeyError: 'productive-linkedin-cohort-v2'` per TASK-336's own
finding). `PROVIDER-CAMPAIGNS.json` cannot be refreshed from here at all:
regenerating it is a provider read and this pass made none.

**ISSUE-047 was filed against master as CONFIRMED / Not FIXED and it is FIXED.**
`cb7e5861` changed `_fact(text, source, date=None, verified=True)` into
`_fact(text, client, key, date=None, verified=False)`, which builds `source`
from `_source(client, key)`; `grep -c "config/clients/productive.yaml"
src/secondbrain.py` is 0. The register entry now says FIXED **and not
PRODUCTION_VERIFIED**, because that same commit message records that the new
bridge has no caller.

### 2. TASK-344's consumer audit is FALSIFIED, and merging it would have put the falsehood on master as a test

TASK-344 rebuilt `scripts/consumer_audit.py`. Its acceptance criterion 1 is that
four modules "still come out DISCONNECTED", one of them `src/sequencegate.py`,
and its result block reports "`src/sequencegate.py` — 0 importers in src/ or
scripts/".

That is false on master:

    src/bisonfactory.py:35-36     from . import (campaigns, clients, copylint, packfacts, providerwrites,
                                                 sequencegate, store)
    src/bisonfactory.py:668       result = sequencegate.check(sequence)
    src/generate_campaign.py:21   from . import (... secondbrain, sequencegate, sequenceplan, skills)
    src/generate_campaign.py:104  batch_gate = sequencegate.check(
    src/generate_campaign.py:374  result["sequence_gate"] = sequencegate.check(

The branch also ships `tests/test_every_producer_has_a_production_consumer.py`,
which would commit that answer as an assertion. A consumer audit that misses a
real importer is the tool that licenses deleting a live safety gate, and its
"10 DISCONNECTED out of 235" count cannot be trusted until the importer bug is
found. REWORK.

This finding also rescues TASK-330: `copylint.untraceable` is reached from
production through `sequencegate.check`, which the audit said nothing calls.

### 3. Five parallel implementations of a review surface master already owns

Master has `src/preview.py`, `src/previewpage.py`, `src/clientreview.py`,
`src/reviewapproval.py` and `scripts/render_preview.py`. The queue holds four
more renderers, each built independently:

| TASK | branch | head SHA | what it adds |
| --- | --- | --- | --- |
| TASK-301 | `qwen-worker-7-r59` | `24df89c75622` | `scripts/build_review_html.py`, `scripts/render_review_503.py`, `src/packfact.py` |
| TASK-303 | `qwen-worker-8-r59` | `53cd306b66d5` | `scripts/task303_render_review.py` |
| TASK-304 | `origin/qwen-worker-4-task304-review-file` | `1a82ed63b6e4` | `src/reviewfile.py`, `scripts/build_review_file.py` |
| TASK-342 | `qwen-worker-r72` | `b32d979028e2` | `scripts/export_review_342.py` |

`src/packfact.py` is one letter from the existing `src/packfacts.py`. This is
OPERATING-MODE §5 exactly: a projection, never a second implementation. All four
are REWORK, and which surface is canonical is one operator decision rather than
four workers' independent ones. None was merged.

### 4. The standing suite baseline no longer describes master — by name, not by count

`docs/state/SUITE-BASELINE-2026-09-26.txt` is a list of **128 named failures**.
Measured at master `1f4d464c` with the baseline's own command:

    197 distinct failing names
     75 names in the run that are NOT in the baseline
      6 baseline names that now pass

Master has drifted **+75 / −6 names in one day.** This is not a proposal to
adopt 197 as a new baseline — TASK-372 proposed exactly that with 228 and was
rightly refused, and the number is not the point. It is why this pass gated its
merges on a set diff against a before-run measured on the same machine at the
same commit, which is the only comparison that answers "did I break something".
The named before-set is `scratchpad/before-1f4d464c.txt` and the logs are
`scratchpad/suite-before-1f4d464c.log` and `scratchpad/suite_after.out` in the
integrating worktree. **Somebody owns regenerating the standing baseline as a
list at a named master SHA; until then it under-reports master's debt by 75
names and cannot gate a merge on its own.**

### 5. Two branches were already integrated, a third mostly was, and one adds nothing at all

- **TASK-164** (`qwen-worker-r29 @ a6e7eb2db989`): both allowlist corrections
  are already on master, at `tests/test_the_heyreach_write_contract.py:248` and
  `tests/test_nothing_writes_to_a_provider.py:133-139`. `/list/AddLeadsToListV2`
  is in master's `heyreach.WRITE_ROUTES` with its own rationale, so the test's
  closed set was stale and has already been corrected.
- **TASK-244** (`qwen-worker-3-task-244 @ 3c1e51d5aa2a`): five of its files are
  byte-identical to master's and `config/clients/productive.yaml` already carries
  the `client_approval_export` block that `src/clients.py:488` reads. The branch
  would add 16 lines and remove 369 of master's.
- **TASK-225** (`qwen-worker-7-r28 @ b80d3631532b`): `git diff master..branch --
  src/ratelimit.py tests/test_ratelimit.py` is **0 insertions, 86 deletions**.
  The branch adds nothing that master lacks.
- **`origin/qwen-worker-10-r9`** is the same shape at scale: of 127 changed
  non-task files, **109 are byte-identical to master**. Its
  `git diff master...branch --stat` reads `+22388 −184`, which is mostly master's
  own work measured from a stale merge base.

**The method.** `git diff master...<branch>` is measured from the MERGE BASE, so
it cannot distinguish "the branch adds this" from "master added this and the
branch has it too" — which is how `task173_scan.py` once reported twelve
stranded tasks of which six were integrated. For every branch this pass compared
the blob hash of every touched file at three points (merge base, master, branch
head) and classified it: master unmoved (a clean apply), identical on branch and
master (already integrated), or moved on both (a real 3-way). It then ran
`git diff master..<branch>` restricted to the branch's own files: **zero
insertions in that direction means the branch cannot add, only remove.** Both
scans are reproducible from `scratchpad/overlap.py` and
`scratchpad/adds_nothing.py`.

## WHAT WAS MERGED

Onto master `1646367c`, in this order:

    2e833db1  TASK-337  config/.env.example
    504aec5a  TASK-300  findings only
    4841ba1d  TASK-347  findings only
    09e44f68  TASK-393  findings only
    91cce953  TASK-291  docs only
    ee42fc19  TASK-351  src/accountpolicy.py            REVERTED by 3fd8c9aa
    2d789753  TASK-332  src/spendledger.py              SPEND LEDGER (conflict resolved to keep BOTH glm and xai units)
    7d3d3ea0  TASK-268  src/linkedin_match.py           SAFETY, wired
    02591b0c  TASK-247  src/reengagement.py             junk dropped
    5f4c2d54  TASK-348  src/ingest.py, src/packfacts.py
    9d9569b3  TASK-297  scripts/qa/                     reads only
    e3e2e0a8  TASK-299  scripts/qa/                     reads only
    b4a75724  TASK-330  src/copylint.py                 PROVENANCE, launch blocker 5
    290ba7c6  TASK-378  src/copylint.py                 COPY SAFETY
    1d5bc42f  TASK-338  src/copylint.py                 SAFETY, demotion expiry
    667cea6b  TASK-336  docs/state/PROBLEM-REGISTER.md  PARTIAL, JSONs refused
    c4938c1c  TASK-341  REWORK recorded, artifact refused
    0905fbb6  TASK-164 + TASK-244  CLOSE, result blocks only
    2aa368dc  redaction  (fixture-hygiene regression)
    89bc50cc  TASK-332 partial revert (preproduction regression)
    3fd8c9aa  TASK-351 revert (stop-buttons regression)
    1e29ce0f  store-isolation fix (slack-agent regression)

Three merges touch `src/copylint.py`, which is on the copy-refusal path. They
went in one at a time with the targeted modules run green after each:

| after | modules | result |
| --- | --- | --- |
| TASK-332 | the seven ledger/ceiling modules + the two model-spend modules | 170 tests OK |
| TASK-268 | `test_linkedin_profile_match`, `test_hold_reasons`, `test_nothing_writes_to_a_provider` | 62 OK |
| TASK-247 | `test_the_three_lanes_have_no_overlap` | 36 OK |
| TASK-348 | `test_the_ingest_keeps_headcount_and_products`, `test_ingest` | 27 OK |
| TASK-297/299 | the four new QA modules | 42 OK |
| TASK-330 | `test_a_reused_number_does_not_launder_a_new_claim`, `test_copylint`, `test_the_sequence_gate_catches_what_copylint_cannot`, `test_a_case_study_claim_must_appear_on_the_page` | 79 OK |
| TASK-378 | those four + `test_a_step_may_not_claim_to_be_the_last_one` | 101 OK |
| TASK-338 | that set + `test_a_time_boxed_demotion_expires_on_its_own` | 92 OK |

TASK-338's expiry was proved by call rather than only by test:
`copylint.warning_rules()` returns `['step1_without_pack_fact']` on 2026-09-27
and 2026-09-28 and `[]` on 2026-09-29. The demotion reverts to REFUSING with no
human action.

## THREE THINGS A READER MUST NOT READ AS SAFE

1. **TASK-378 widens what must be grounded.** `SPECIFIC_RES` changes from
   `\b\d[\d,.]{1,}\b` to `\b\d[\d,.]*\b`, so a single digit inside a company
   claim is now a specific that needs a pack sentence. With TASK-330's sentence
   binding this refuses strictly more copy than master did. It was merged because
   the direction is fail-closed on a path that has already reached real prospects
   twice, but it is a behaviour change on the refusal path: read the first batch
   it refuses, do not override it.

2. **TASK-348 puts client-CSV columns into the admitted pack.** `_ingest_facts`
   appends headcount, size, 12-month growth, products, headline and industry to
   the admitted facts **without passing `packfacts.identity_of()`**, tagged
   `verification: "client-provided"` with the batch file as source. Nothing is
   fabricated and the source is honest, but "client-provided" is a fifth word
   beside VERIFIED / CLIENT_APPROVED / INFERRED / UNKNOWN, and these facts are
   what `copylint.untraceable` will now accept as grounding for a prospect-facing
   claim.

3. **TASK-247's classifier has no caller, and that is correct.**
   `src/reengagement.py` is imported by nothing. The task text forbids
   enrolment — "your output is a lane assignment per lead and a queue, not a
   write" — so this is licensed disconnection, not the DISCONNECTED defect. Do
   not let a later consumer audit delete it, and do not let anyone wire it
   without the operator's re-engagement copy approval.

## WHAT WAS NOT DONE, AND WHY

- **No provider was called.** Writes 0, reads 0. So
  `docs/state/PROVIDER-CAMPAIGNS.json` was not regenerated, and the live
  read-only runs TASK-350 and TASK-297 both still owe were not performed.
- **No branch touching `src/bisonfactory.py`, `src/heyreachfactory.py`,
  `src/generate.py`, `tests/test_generate.py` or `src/sequenceplan.py` was
  merged or cherry-picked.** Twelve branches carrying 38 results are in that
  class. `src/sequencegate.py` was added to the reserved set on the evidence of
  master `1646367c` ("Verify 42114d2f (sequencegate enforcement): PASS,
  merge-ready, HELD") — which is the second reason TASK-339 is REWORK.
- **TASK-364, TASK-400 and TASK-426 were not touched.**
- **A `git push -q origin HEAD:refs/heads/<branch>` was refused by the Claude
  Code auto-mode permission classifier**, not by git and not by GitHub. The bare
  form `git push origin worktree-agent-a0c5bed4fa47fe482` succeeded immediately
  and the remote created the branch. Recorded because this project has once
  misread a classifier refusal as a remote rejection.

## THE HIGHEST-VALUE THING LEFT: TASK-358

`TASK-358` (CheapVerifier into the email-verification waterfall) is the item to
do next, and it is not one of the 140 — `claim_task.py` does not list the clean
branch it lives on. It unblocks TASK-347 and TASK-393, both of which name it as
their first blocker.

It exists twice:

| branch | head SHA | shape |
| --- | --- | --- |
| `qwen-worker-5-r69` | `efa5edd6` | four files: `src/providers/cheapverifier.py` +1141, `src/waterfall.py` +9, `src/enrich.py` +2, one test. **Zero deletions.** Touches no reserved file. |
| `qwen-worker-3-r9` | `b27c8452` | the same module plus eleven provider cassettes and `src/waterfall.py` +26 — but also modifies `src/bisonfactory.py` and `scripts/claim_task.py`. |

Next integrator: diff the two `src/waterfall.py` patches, take
`qwen-worker-5-r69` or cherry-pick the cassettes onto it, and leave
`qwen-worker-3-r9` alone. `CHEAPVERIFIER_API_KEY` is already present and
`config/clients/productive.yaml` already declares its budget.

## EVERY RESULT, ONE ROW EACH

Verdicts are against the named branch head SHA. **NOT REACHED means exactly
that**: the branch was confirmed to exist, its head SHA and changed-file count
are recorded, no reserved file is touched, and nobody has yet read its diff
closely enough to hold an opinion. It is not a pass and it is not a fail.

| TASK | BRANCH | HEAD SHA | VERDICT | REASON / WHAT I DID |
| --- | --- | --- | --- | --- |
| TASK-247 | `qwen-worker-6-task-247` | `c2e3738da7c2` | **MERGE** | Lane classifier plus REVIVE queue. No production importer BY DESIGN - the task text forbids enrolment. Junk (.qwen-TASK.err/.out) dropped. |
| TASK-268 | `qwen-worker-3-r58` | `41d5c2a48fe8` | **MERGE** | Safety, and WIRED: scripts/batch_linkedin_push.py main() calls verify_leads() at line 424. A missing profileUrl, a raising fetch and an empty profile all HOLD. |
| TASK-291 | `qwen-worker-7-r60` | `1168cee29e8b` | **MERGE** | Report only, docs/SPEND-SECOND-PASS-2026-09-25.md. No code, no suite risk. |
| TASK-297 | `qwen-worker-8-r60` | `0bc320b851ea` | **MERGE** | Six per-campaign HeyReach QA rules, READS ONLY, argparse-gated. Includes the rendered-not-template connection-note check. |
| TASK-299 | `qwen-worker-9-r60` | `6109d7266a9d` | **MERGE** | Reconcile QA. Its finding - a rule keyed on a field nobody carries is vacuous - is the point. READS ONLY. |
| TASK-300 | `qwen-worker-11-r60` | `3b632b057028` | **MERGE** | Findings only. Re-verified on master: shifted_allocation() has exactly one non-test caller, src/web/demovariants.py:218, which never persists. The learning loop is open. |
| TASK-330 | `qwen-worker-4-r61` | `82b828c2b779` | **MERGE** | Launch blocker 5. _traces no longer reduces to token-in-document; a specific must appear in a pack SENTENCE sharing two content words with the draft sentence. |
| TASK-337 | `qwen-worker-8-r62` | `9290497fe77c` | **MERGE** | Three LIVE credential names from src/config.py VARIABLES were absent from config/.env.example. Verified against the registry, never guessed. No values. |
| TASK-338 | `qwen-worker-10-r62` | `74d9f0312e48` | **MERGE** | A safety demotion now expires mechanically: active 09-27 and 09-28, empty 09-29, proved by call. Dead @property block dropped. |
| TASK-347 | `qwen-worker-4-r68` | `9f5a720ac682` | **MERGE** | Findings only, BLOCKED. Blockers 1/2/5 re-verified on master. Blockers 3 and 4 rest on an empty work/ in the worker's own worktree and are artifacts, not system state. |
| TASK-348 | `qwen-worker-5-r68` | `9eac47ecaa37` | **MERGE** | Ingest carries headcount/size/growth/products/headline/industry into company_facts; packfacts surfaces them with the batch file as source and client-provided as verification. |
| TASK-378 | `qwen-worker-12-r80` | `52ed8fcba6e4` | **MERGE** | Three rules and one field reader were pointed at email bodies only. Now the whole rendered surface. SPECIFIC_RES widened to single digits - a deliberate fail-closed widening, recorded. |
| TASK-393 | `origin/qwen-worker-2-r93` | `c2dd5ad0ec68` | **MERGE** | Findings only. Confirmed CheapVerifier was added only on qwen-worker-3-r9 (b27c8452) and qwen-worker-5-r69 (efa5edd6) via git log --diff-filter=A --all. |
| TASK-332 | `qwen-worker-7-r61` | `cb283e896773` | **MERGE-PARTIAL** | PARTIAL. KEPT: report() refusing to sum cents/credits/microusd/ticks as one integer, LEDGER_UNITS xai:ticks (10e9 ticks = $1, src/providers/xai.py:80), and researchpack/pack.py passing unit='cents' explicitly. REFUSED: the enrich.py `unit=unit_for(provider)` argument - unit_for falls back to DEFAULT_UNIT, so it stamps 'credits' plus a derived usd_estimate on every unpriced provider row, which record()'s own 'NOT DEFAULTED, DELIBERATELY' comment forbids and which test_preproduction caught as 'the spend ledger grew a record field'. Its test also leaked the store directory in four places (addCleanup(f, arg) instead of addCleanup(f(arg))), breaking test_slack_agent_cannot_act; corrected to the form src/store.py:181 documents. |
| TASK-336 | `qwen-worker-6-r62` | `e1f55f176bc6` | **MERGE-PARTIAL** | PARTIAL. ISSUE-046/047 taken into PROBLEM-REGISTER.md with ISSUE-047 corrected to FIXED (cb7e5861). The five derived docs/state JSONs REFUSED - master's PROVIDER-CAMPAIGNS.json is 2026-09-27T10:17:30Z and the branch's is 2026-09-26T10:11:11Z, so merging would have reverted provider truth by a day. |
| TASK-248 | `qwen-worker-7-task-248` | `f37cc9b77a80` | **REWORK** | STALE. The branch adds 806 lines and would revert 1005 lines of master's Slack-agent work (scripts/slack_agent_loop.py, src/slackagentreadback.py both moved on master). Rebase onto master and re-verify; a merge here is a partial revert, not an integration. |
| TASK-301 | `qwen-worker-7-r59` | `24df89c75622` | **REWORK** | ONE-TRUTH violation (OPERATING-MODE §5). Adds scripts/build_review_html.py, scripts/render_review_503.py and src/packfact.py - the last one letter from the existing src/packfacts.py - beside master's src/preview.py, src/previewpage.py, src/clientreview.py and src/reviewapproval.py. |
| TASK-303 | `qwen-worker-8-r59` | `53cd306b66d5` | **REWORK** | ONE-TRUTH violation. Adds scripts/task303_render_review.py, a task-numbered production script, as a third review renderer. |
| TASK-304 | `origin/qwen-worker-4-task304-review-file` | `1a82ed63b6e4` | **REWORK** | ONE-TRUTH violation. Adds src/reviewfile.py and scripts/build_review_file.py as a fourth review renderer. |
| TASK-307 | `qwen-worker-9-r59` | `2ee0940d37f2` | **REWORK** | DISCONNECTED. contactout.linkedin_from_email has zero callers in src/ or scripts/; the call is registered in enrich.COSTS and CALL_STAGE but nothing dispatches it. |
| TASK-312 | `qwen-worker-4-r59` | `073e81e040a2` | **REWORK** | REWORK. Adds src/copyengine.py, 759 lines, with zero importers on its own branch, beside master's existing src/copystages.py and src/copyprompts.py. A second copy engine on the one path three concurrent subagents hold: One-Truth (OPERATING-MODE §5) and DISCONNECTED at once. |
| TASK-339 | `qwen-worker-2-r63` | `ae54f5182b82` | **REWORK** | _role_profile is literally _concept_profile, so the advertised two-threshold test is one threshold computed twice and the score reduces to (x+x)/2. The min() denominator scores any subset-of-concepts pair at 1.0, which over-refuses. The retained 'lexical overlap only' warning becomes false. Also collides with the sequencegate enforcement on the critical path (master 1646367c). |
| TASK-341 | `qwen-worker-5-r63` | `0554b7da0492` | **REWORK** | Finding TRUE (senderidentity has no signature field, launch blocker 3 stands) but the artifact is three @unittest.skip tests, one asserting on its own fixture. Finding kept, tests refused. |
| TASK-342 | `qwen-worker-r72` | `b32d979028e2` | **REWORK** | ONE-TRUTH violation. Adds scripts/export_review_342.py as a fifth review renderer. |
| TASK-344 | `qwen-worker-3-r68` | `ffa0d4792178` | **REWORK** | FALSIFIED. Its acceptance rests on src/sequencegate.py being DISCONNECTED; sequencegate is imported at src/bisonfactory.py:36 and src/generate_campaign.py:21 and check() is called at bisonfactory.py:668 and generate_campaign.py:104/374. Merging would put a test on master asserting a live safety gate has no consumer. |
| TASK-349 | `qwen-worker-6-r68` | `c92175e7a15f` | **REWORK** | Right direction, unsafe implementation: _write_back_to_ledger wraps the ledger write in bare `except Exception: return None`, and None means not-applicable, no-event-id, replay AND write-failed. A silent failure on a provenance path, against CLAUDE.md's no-silent-fallbacks rule. |
| TASK-350 | `qwen-worker-7-r68` | `efe70035f21e` | **REWORK** | DISCONNECTED against its own spec. The task says 'add the check to the existing loop'; reconcile_campaigns() is reachable only from a --reconcile CLI flag, and the result block itself says 'Integrate into the watcher's periodic loop if desired'. The watcher still does not reconcile. |
| TASK-351 | `qwen-worker-8-r68` | `337b6b2a3c2e` | **REWORK** | MERGED THEN REVERTED (ee42fc19 reverted by 3fd8c9aa). The finding is real - seven outcomes with no attributable contact planned account=CONTINUE and wrote nothing. But the new else-branch also fires for outcomes whose plan is already HOLD, and section 2's _hold_account then returns False because the record is already paused, so tests/test_stop_buttons.py::test_an_unattributable_positive_still_only_holds went red: 'account_held' not found in ['account_held_unattributed']. The fix is one condition - fire only when plan['account'] == CONTINUE. |
| TASK-164 | `qwen-worker-r29` | `a6e7eb2db989` | **CLOSE** | ALREADY INTEGRATED. Both allowlist corrections are on master (test_the_heyreach_write_contract.py:248, test_nothing_writes_to_a_provider.py:133-139). Result block cherry-picked. |
| TASK-221 | `qwen-worker-2-r50` | `e3d60bdee844` | **CLOSE** | SUPERSEDED. Its load-bearing change, STANDING_EMAIL_DEFECT = frozenset(), is already at tests/test_no_activation_without_an_exact_match.py:113 on master. The branch's copy of that file is 477 lines behind master's; merging it is the TASK-232 shape (deleting gate coverage to gain a fixture). If THREADED_EMAIL_SEQUENCE is still wanted it belongs on master's current file. |
| TASK-225 | `qwen-worker-7-r28` | `b80d3631532b` | **CLOSE** | ADDS NOTHING. `git diff master..branch -- src/ratelimit.py tests/test_ratelimit.py` is 0 insertions and 86 deletions: master's rate limiter is 86 lines ahead of the branch's. Merging could only remove work. |
| TASK-230 | `task-230-prefetch-headcount` | `f0ada227185f` | **CLOSE** | SUPERSEDED. master's src/gather.py, src/enrich.py and tests/test_prefetch_headcount.py are ahead: the branch would add 96 lines and remove 222 of master's. |
| TASK-240 | `qwen-worker-r55` | `8f4406e1bb2a` | **CLOSE** | ALREADY INTEGRATED. master carries tests/test_task240_arity_rule_moves_to_action.py and a further-evolved src/executionguard.py; the branch would add 6 lines and remove 13 of master's guard. |
| TASK-244 | `qwen-worker-3-task-244` | `3c1e51d5aa2a` | **CLOSE** | ALREADY INTEGRATED. Five of its files are byte-identical to master and productive.yaml already carries the client_approval_export block that src/clients.py:488 reads. Result block cherry-picked. |
| TASK-250 | `qwen-worker-9-r61` | `3efcc9683f2a` | **CLOSE** | SUPERSEDED by TASK-262 on qwen-worker-10-r59, which is the same three-file fixture change (tests/base.py, test_e2e.py, test_enrich.py) done as 'attempt 2: private fixtures, shared ones untouched'. git diff between the two branches shows no difference in those files. Take TASK-262, not this. |
| TASK-286 | `qwen-worker-3-r60` | `a67999eb71f4` | **CLOSE** | SUPERSEDED. Adds a 2026-09-25 suite baseline; master carries docs/state/SUITE-BASELINE-2026-09-26.txt, which is the standing baseline named by OPERATING-MODE §19. |
| TASK-359 | `qwen-worker-r70` | `7150fd809358` | **CLOSE** | DEFERRED BY COVERING INSTRUCTION, and the branch does the forbidden thing. OPERATING-MODE defers TASK-359 until the internal ledger is proven and states that no scheduled task is registered; the branch adds scripts/register_usage_job.ps1, a scheduled-task registrar. Not merged. |
| TASK-364 | `qwen-worker-7-r9` | `8db9271503ac` | **HELD (orchestrator)** | Critical path. The orchestrator merges this. |
| TASK-400 | `qwen-worker-r9` | `b7df77153a76` | **HELD (orchestrator)** | Critical path. The orchestrator merges this. |
| TASK-426 | `qwen-worker-r9` | `b7df77153a76` | **HELD (orchestrator)** | Critical path. The orchestrator merges this. |
| TASK-216 | `origin/qwen-worker-10-r9` | `d3b76e3e172b` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/generate.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 127 changed non-task files and 109 of them are already byte-identical to master. |
| TASK-219 | `qwen-worker-r51` | `dff854cf8fce` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 5 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-243 | `qwen-worker-2-task-243` | `d0f49d12d199` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 13 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-246 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-267 | `qwen-worker-3-r9` | `402a0d305c5a` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 24 changed non-task files and 4 of them are already byte-identical to master. |
| TASK-269 | `qwen-worker-4-r58` | `fe92b486beb9` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 6 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-273 | `qwen-worker-11-r9` | `6ed3049176fd` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 7 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-281 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-283 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-292 | `origin/qwen-worker-10-r9` | `d3b76e3e172b` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/generate.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 127 changed non-task files and 109 of them are already byte-identical to master. |
| TASK-293 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-295 | `origin/qwen-worker-10-r9` | `d3b76e3e172b` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/generate.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 127 changed non-task files and 109 of them are already byte-identical to master. |
| TASK-296 | `qwen-worker-11-task314` | `ddc0bc816fed` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 14 changed non-task files and 1 of them are already byte-identical to master. |
| TASK-310 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-314 | `qwen-worker-11-task314` | `ddc0bc816fed` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 14 changed non-task files and 1 of them are already byte-identical to master. |
| TASK-318 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-328 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-355 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-358 | `qwen-worker-3-r9` | `402a0d305c5a` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 24 changed non-task files and 4 of them are already byte-identical to master. |
| TASK-367 | `origin/qwen-worker-5-r9` | `d0432a8945ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 34 changed non-task files and 25 of them are already byte-identical to master. |
| TASK-372 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-383 | `origin/qwen-worker-5-r9` | `d0432a8945ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 34 changed non-task files and 25 of them are already byte-identical to master. |
| TASK-385 | `qwen-worker-11-r9` | `6ed3049176fd` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 7 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-386 | `qwen-worker-8-r9` | `afa48d18ab6d` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 30 changed non-task files and 26 of them are already byte-identical to master. |
| TASK-388 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-390 | `origin/qwen-worker-10-r9` | `d3b76e3e172b` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/generate.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, `tests/test_generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 127 changed non-task files and 109 of them are already byte-identical to master. |
| TASK-391 | `qwen-worker-11-r9` | `6ed3049176fd` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 7 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-395 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-396 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-397 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-398 | `qwen-worker-11-task314` | `ddc0bc816fed` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 14 changed non-task files and 1 of them are already byte-identical to master. |
| TASK-403 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-410 | `qwen-worker-3-r9` | `402a0d305c5a` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 24 changed non-task files and 4 of them are already byte-identical to master. |
| TASK-411 | `qwen-worker-2-r9` | `f03c74fc01a4` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 39 changed non-task files and 15 of them are already byte-identical to master. |
| TASK-412 | `qwen-worker-3-r9` | `402a0d305c5a` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 24 changed non-task files and 4 of them are already byte-identical to master. |
| TASK-413 | `qwen-worker-11-task314` | `ddc0bc816fed` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 14 changed non-task files and 1 of them are already byte-identical to master. |
| TASK-421 | `qwen-worker-11-r9` | `6ed3049176fd` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/generate.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 7 changed non-task files and 0 of them are already byte-identical to master. |
| TASK-425 | `qwen-worker-7-r9` | `8db9271503ac` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`, reserved by three concurrent subagents. Not merged, not cherry-picked: the branch carries 59 changed non-task files and 19 of them are already byte-identical to master. |
| TASK-192 | `qwen-worker-5-r59` | `2b3584534d6c` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 5 changed non-task files, no reserved file touched. |
| TASK-213 | `qwen-worker-4-r45` | `71f42b1e4eba` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 2 changed non-task files, no reserved file touched. |
| TASK-226 | `qwen-worker-8-r28` | `36a4ce61b454` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 10 changed non-task files, no reserved file touched. |
| TASK-231 | `qwen-worker-8-r28` | `36a4ce61b454` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 10 changed non-task files, no reserved file touched. |
| TASK-245 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-249 | `qwen-worker-8-r61` | `8e6ee5edcb1c` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-262 | `qwen-worker-10-r59` | `1c8377bd4dcc` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-264 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-266 | `qwen-worker-r58` | `cf1515fb4073` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 2 changed non-task files, no reserved file touched. |
| TASK-270 | `qwen-worker-5-r58` | `26eb2cd0cfbb` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-271 | `qwen-worker-6-r58` | `c921c1348112` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-272 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-274 | `qwen-worker-5-r58` | `26eb2cd0cfbb` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-279 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-280 | `qwen-worker-4-r9-task280` | `cdffd0a2d3ba` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 10 changed non-task files, no reserved file touched. |
| TASK-284 | `qwen-worker-12-r59` | `a520841c33e0` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 7 changed non-task files, no reserved file touched. |
| TASK-285 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-287 | `qwen-worker-4-r60` | `8d98cb78410b` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-288 | `qwen-worker-6-r59` | `357c1ffffdd0` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 1 changed non-task files, no reserved file touched. |
| TASK-289 | `qwen-worker-6-r60` | `9154d87f2a30` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 1 changed non-task files, no reserved file touched. |
| TASK-290 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-294 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-298 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-302 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-305 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-308 | `qwen-worker-4-r9-task280` | `cdffd0a2d3ba` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 10 changed non-task files, no reserved file touched. |
| TASK-311 | `qwen-worker-6-r9` | `a28311c68ab7` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 28 changed non-task files, no reserved file touched. |
| TASK-313 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-315 | `qwen-worker-4-r9-task280` | `cdffd0a2d3ba` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 10 changed non-task files, no reserved file touched. |
| TASK-319 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-325 | `qwen-worker-r60` | `2594a3088814` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 1 changed non-task files, no reserved file touched. |
| TASK-326 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-327 | `qwen-worker-2-r60` | `94819507ab30` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 2 changed non-task files, no reserved file touched. |
| TASK-335 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-340 | `qwen-worker-4-r67` | `85b82ddc7ec4` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 5 changed non-task files, no reserved file touched. |
| TASK-345 | `qwen-worker-r68` | `f95066072e12` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
| TASK-353 | `qwen-worker-9-r68` | `8ff73995d5b7` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 6 changed non-task files, no reserved file touched. |
| TASK-357 | `qwen-worker-r69` | `a66b6c5bc8a8` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 2 changed non-task files, no reserved file touched. |
| TASK-360 | `qwen-worker-2-r70` | `29f90f7bee91` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 6 changed non-task files, no reserved file touched. |
| TASK-387 | `qwen-worker-6-r9` | `a28311c68ab7` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 28 changed non-task files, no reserved file touched. |
| TASK-389 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-392 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-399 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-402 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-404 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-405 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-406 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-407 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-408 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-409 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-414 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-415 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-416 | `qwen-worker-9-r9` | `f1b9c357c17f` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 24 changed non-task files, no reserved file touched. |
| TASK-417 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-418 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-419 | `qwen-worker-6-r9` | `a28311c68ab7` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 28 changed non-task files, no reserved file touched. |
| TASK-420 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-422 | `qwen-worker-4-r9` | `1646367c5987` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-423 | `qwen-worker-6-r9` | `a28311c68ab7` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 28 changed non-task files, no reserved file touched. |
| TASK-424 | `qwen-worker-12-r9` | `c5a756d27a73` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 17 changed non-task files, no reserved file touched. |
| TASK-427 | `qwen-worker-r9` | `b7df77153a76` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 0 changed non-task files, no reserved file touched. |
| TASK-428 | `qwen-worker-6-r9` | `a28311c68ab7` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 28 changed non-task files, no reserved file touched. |
---

# SECOND PASS — 2026-09-27 night into 2026-09-28

**Appended, not a rewrite.** Everything above is the first pass and stands as
written, except where a row below says it was corrected. This pass started from
the first pass's 62 NOT REACHED rows and did not redo a resolved row.

## THE QUEUE, MEASURED, AND WHICH NUMBER CAME FROM WHERE

| number | value | authority |
| --- | --- | --- |
| Queue at start | **122** results | `py -3 scripts/claim_task.py --status`, run by me at master `e2ecaad7`, 2026-09-27 ~23:00 Europe/Zagreb |
| Distinct branches carrying them | **41** | `git rev-parse` on each branch name the status listing printed |
| Results the first pass left NOT REACHED | **62** (+1 new, `TASK-429`) = **63** | the table above, parsed; `TASK-429` appears in the status listing and in no first-pass row |
| Integrated this pass | **20** results, in 5 pushes | my own commits, `git rev-parse master origin/master` agreeing after each |
| Sent to REWORK | **15** | per-row, below |
| CLOSED | **4** | per-row, below |
| BLOCKED-ON-CRITICAL-PATH | **23** | reserved-file branches, plus `TASK-427` |
| In flight, nothing to integrate | **1** (`TASK-422`) | its task file moved TODO→RUNNING at 2026-09-27 23:25:59 |
| Remaining unresolved after this pass | **0 of the 63** | every one of the 63 carries a verdict below |

**The queue counter DID go down, and the first pass's rule about it is wrong in
one specific way.** The first pass concluded "integrating a result does not
decrement that number and cannot — the count only ever falls when somebody
DELETES a branch." Measured: it fell from **140 to 122** with no branch deleted.
The 18 are exactly the 19 results the first pass merged or closed (`TASK-164`,
`244`, `247`, `268`, `291`, `297`, `299`, `300`, `330`, `332`, `336`, `337`,
`338`, `341`, `347`, `348`, `378`, `393`, `425`) minus the one new arrival
(`TASK-429`). The mechanism is not branch deletion: `claim_task.py` compares the
stage of the task file **on master** against the stage on the branch, and when
master's copy advances the branch row is reclassified from "awaiting integration"
into "stale branches hiding available tasks" (114 of those now, up from 109). So
carrying a result block over to master — which the first pass did for exactly
these — moves the row out of the bucket.

**It is still not a burn-down, for a different and worse reason.** See finding 1
below: the branch the counter names is frequently not the branch the artifact is
on.

## THE FOUR THINGS THIS PASS FOUND THAT NOTHING ELSE SAYS

### 1. `claim_task.py --status` MISATTRIBUTES RESULTS TO BRANCHES, and ten rows proved it

`claim_task.py --status` reported ten results on `origin/qwen-worker-4-r9`:
`TASK-245`, `264`, `279`, `285`, `298`, `326`, `408`, `414`, `422`, `427`. At
that branch's head `2cb8755afc8a` **not one of them is there.** All ten task
files exist on that SHA only as `docs/qwen-tasks/TODO/TASK-NNN-*.md`, and all ten
are byte-identical to master's — `git diff --name-status 13a64166 2cb8755a --`
over those ten paths is empty. A TODO-stage file carries no RESULT block.

The branch's actual work at that SHA is `TASK-352` and `TASK-438`, neither of
which is one of the ten.

The cause is force-pushing. `refs/heads/qwen-worker-4-r9` locally pointed at
`980f3fdb`, which is **not an ancestor of** `origin/qwen-worker-4-r9`; that line
is `TASK-279`'s, published as `origin/qwen-worker-4-r9-task279`. One branch name,
two divergent lines, and the status tool folds both into one row. Stage hygiene
makes it worse: `980f3fdb` adds `REVIEW/TASK-279-*.md` **and**
`RUNNING/TASK-279-*.md` without deleting the `TODO/` copy, so three stage copies
of one task coexist.

Where the ten actually live, found with
`git log --diff-filter=A --all -- <claimed path>`:

| TASK | the artifact is really on |
| --- | --- |
| 245 | **master**, and master is 4 commits AHEAD of the branch version |
| 264 | nowhere — no RESULT block on any ref; two rival implementations in flight |
| 279 | `origin/qwen-worker-4-r9-task279 @ 980f3fdb` |
| 285 | `origin/qwen-worker-3-r9-task285 @ c8a62f41` |
| 298 | `origin/qwen-worker-r9 @ ac4190cd` |
| 326 | `origin/qwen-worker-r9 @ ac4190cd` |
| 408 | nowhere at all — never claimed, never started |
| 414 | `origin/qwen-worker-11-r9 @ f7e95b58` |
| 422 | nowhere — claimed RUNNING at 23:25:59 tonight |
| 427 | `origin/qwen-worker-r9 @ ac4190cd` |

**So a verdict that names the branch the status tool named, without locating the
artifact, is naming the wrong SHA.** Every merge in this pass was made from a SHA
found by `--diff-filter=A`, not from the listing.

### 2. LOCAL WORKER BRANCH HEADS ARE BEING RESET TO MASTER WHILE YOU READ THEM

Measured twice, minutes apart, in the same shared clone:

    refs/heads/qwen-worker-11-r9   6ed3049176fd  ->  13a641669454 (= master)
    refs/heads/qwen-worker-r9      ...           ->  13a641669454 (= master)
    refs/heads/qwen-worker-4-r9    ...           ->  13a641669454 (= master)
    refs/heads/qwen-worker-5-r9    ...           ->  3a2388c879e7 (ancestor of master)
    refs/heads/qwen-worker-10-r9   d3b76e3e172b  ->  3a2388c879e7 (ancestor of master)

The live pool resets a worker's local branch to master when it claims a task. A
first reading of this queue against **local** heads therefore reported six
branches as `ANCESTOR-OF-MASTER` with zero changed files — i.e. "already
integrated, nothing to do" — which was false for every one of them. The pushed
`refs/remotes/origin/<branch>` still held the work.

**The durable head is the remote-tracking ref. A verdict measured against a local
worker branch head is void within minutes.** This is the same class as the
first-pass lesson that a branch's task-file stage is an artifact and not task
state: a ref under local control is not evidence.

`origin/` heads move too, just more slowly and only forward:
`qwen-worker-3-r9` `402a0d30`→`7fee1321`, `qwen-worker-12-r9` `c5a756d2`→`d274ec55`,
`qwen-worker-r9` `b7df7715`→`11cd35ed`→`7e79c6b4`→`d291fc15`, all within this
pass. **Every SHA in the rows below is the SHA reviewed, and it is pinned.**

### 3. THE STANDING SUITE BASELINE IS 4 NAMES SHORT, NOT 75 — and TASK-426 is why

The first pass measured 197 distinct failing names at master `1f4d464c` and
concluded the baseline "under-reports master's debt by 75 names and cannot gate a
merge on its own". Measured independently by me with the baseline file's own
command (`python -m unittest discover -s tests -v`, one process, via
`scripts/run_suite.py`) at master `e2ecaad7`, 2144s:

    125 distinct failing names   (100 failures + 25 errors)
      4 names failing that the baseline does not list
      7 baseline names that now pass

Not +75/−6. The gap closed because `6e72f9f0` merged `TASK-426` and
`bisonfactory.stage()` started working again; the ~70 names the first pass saw
were that one breakage fanning out. The four unlisted names are:

    test_an_offer_cannot_be_invented.TestApprovalRefusal.test_approval_status_is_not_defaulted_to_approved
    test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
    test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain
    test_the_cadence_reacts_to_what_the_prospect_did.ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too

and the seven that now pass include all five of
`test_a_resume_leaves_a_ledger_row`, which the baseline file's own note flags as
"PRE-EXISTING RED ... a guard that has been red long enough to become baseline is
not a guard". They are green again.

This was settled in parallel and independently by `322526ba` ("Settle the suite:
128 names, not 197, and the baseline is 4 short not 75") while this pass was
running, and it names the same four. Two harnesses measuring 125 and 128 differ
by three order-dependent names, which is the difference between harnesses and not
drift. **No new baseline was adopted and the baseline file was not edited.**

### 4. TWO STANDING AUTHORITIES CITED BY OPERATING-MODE DID NOT EXIST ON MASTER

- `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`. OPERATING-MODE's ARCHITECTURAL
  INVARIANTS names it as the authority for the LinkedIn cadence. It was on no ref
  reachable from master. **Now merged** (`TASK-325`), after checking it against
  the code rather than against the claim: `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`
  returns li1 d1, em1 d1, li2 d3, em2 d4, li3 d6, em3 d8 … — ten steps, five
  LinkedIn on 1/3/6/10/15 and five email on 1/4/8/12/21, exactly what the
  document says and what OPERATING-MODE declares canonical.
- `config/model_policy.yaml` and `src/modelrouter.py`. OPERATING-MODE's MODEL
  POLICY section ends "no model slug outside `config/model_policy.yaml`". Neither
  file exists on master. The commit that looks like it delivered them,
  `91a7e1b456b8` — subject **"Model routing implemented to the operator's scope:
  router, observability, GLM stages, escalation, tournament"** — contains seven
  files and all seven are task briefs plus `docs/BACKLOG.md`. **Zero code.** A
  commit subject in the past tense is not an implementation, and this is how a
  standing invariant comes to cite a file nobody wrote. `TASK-360`'s branch is the
  only place both files exist; it is REWORK below for a different reason.

## WHAT WAS INTEGRATED, AND THE SUITE GATE IT PASSED

Five pushes, each verified with `git rev-parse HEAD origin/master` agreeing:

    23ade722  TASK-325, TASK-289, TASK-345
    be597e80  TASK-284, TASK-287 (partial), TASK-270, TASK-274, TASK-327
    390c83ae  TASK-271                          SAFETY, send path
    90cd4175  TASK-279, TASK-285 (partial), TASK-315, TASK-414, TASK-290 (partial), TASK-416 (partial)
    <final>   TASK-353, TASK-192 (partial), TASK-213 (partial), TASK-280 (partial), TASK-298 (partial)

**Everything was CHERRY-PICKED BY PATH. Nothing was merged.** Every branch in
this pass is between 26,000 and 230,000 lines behind master; `git merge` on any of
them is a partial revert, not an integration. Each file was classified at three
points — merge base, master head, branch head — by blob hash, and only files in
these classes were taken: `new-file-on-branch(clean-add)` (master does not have
it) and `master-unmoved(clean-apply)` (master's blob equals the merge base's, so
the branch's version cannot discard master's work). **No file classed
`both-moved(REAL-3WAY)` was taken anywhere in this pass.**

Gate: the before-set was pinned at master `e2ecaad7` with the baseline file's own
command — 125 named failures, 2144s — and after every unit the affected modules
were run and diffed **by name**, scoped to those modules. Zero new names was the
condition for each commit. The confirming full run is at the end of this section.

## THE THREE MOST IMPORTANT ROWS

### TASK-271 — a compliance gate that refuses every email cadence today

`qwen-worker-6-r58 @ c921c1348112`. Merged, and it is a behaviour change on the
send path that must not be read as routine. Inside gate 4 of
`executionguard.authorize`, an email step that is not staging is REFUSED unless
the body carries an unsubscribe link or merge field, or the campaign/client config
NAMES a provider-level setting. Nothing satisfies either today, so **it refuses
every current email cadence** — intentional, fail-closed, and the operator's own
instruction of 2026-09-23 as recorded in the task text. `COMPLIANCE.md` records
why it cannot be a `List-Unsubscribe` check instead: the string appears nowhere in
the repository and EmailBison's sequence-step payload has no field for it.

It was safe to land tonight because `sending.live` is off for productive and the
freeze is in force. **The operator still owes one decision** — add an unsubscribe
affordance to every email body, or name a provider-level setting.

Falsified rather than believed. Mutation: `if channel == "email" and not staging:`
→ `if False and …`. Four tests went red, and they failed **for the intended
reason** — `caught.exception.gate` read `sender`, not `compliance`, so the
compliance gate genuinely runs before the sender gate rather than being shadowed
by it. Source restored and verified byte-identical.

The mutation also caught a test that could not fail:
`test_the_refusal_carries_the_passed_gate_trace` stayed GREEN with the gate
disabled, because it asserted only that the trace holds tenancy/approval/
campaign_approval/readback — and the `sender` refusal that takes over carries the
same four. One line added, `assertEqual(caught.exception.gate, "compliance")`,
which is the distinction the test's own docstring says it exists to draw. 27/27
green. Nothing weakened.

A tension handed on, not resolved: the gate is skipped for `staging=True`,
justified by `killswitch.py:277-293`. That justification predates `dc302934`,
which records the operator's definition that a dry run "NEVER means skip the
safety path because `live=false`". Whoever owns the dry-run safety path should
decide whether a staging preview should see this gate as a WARNING rather than
skip it.

### TASK-226 — MERGED, THEN REVERTED: the offset index silences `JournalCorrupt`

`qwen-worker-8-r28 @ 36a4ce61b454`. Its result block says "**All 11 existing
journal tests pass UNCHANGED**" and "No guard was added; the test was not
inverted". **Falsified by running them.** With `src/queuejournal.py` cherry-picked,
four previously-green guards in
`tests/test_a_checkpoint_costs_what_it_changed.JournalTest` go red:

    test_a_torn_middle_line_raises           JournalCorrupt not raised
    test_an_entry_without_a_record_raises    JournalCorrupt not raised
    test_a_record_without_an_id_raises       JournalCorrupt not raised
    test_a_torn_final_line_is_discarded_not_raised

`replay()` now seeks by byte offset from the new index instead of scanning the
journal, so it never reads the corrupt lines and corruption becomes invisible.
The test's own docstring states the consequence: *"Not a crash. Replaying around
it invents a state nobody wrote."* That is a silent fallback on the record-state
integrity path, which CLAUDE.md forbids outright.

`QUEUE_JOURNAL` is default OFF, so master is not exposed today — which is exactly
why this would have been a good defect to ship: it lands quietly and waits for
the flag. The cherry-pick was reverted in the worktree, `src/queuejournal.py`
confirmed byte-identical to master's, and the 23 tests green again. **REWORK.**
The index is a good idea and the benchmark numbers look real; it must rebuild and
VALIDATE on read, not seek past what it did not index.

### TASK-427 — the highest-value unintegrated item, and it is the orchestrator's

`origin/qwen-worker-r9 @ ac4190cd7c11`. Operator decision 5 of 2026-09-27
(OPERATING-MODE, "Scope and offers"): `_check_offers` checks ONLY the offer
selected for that prospect. **Master is still unfixed** — `_check_offers(client_name)`
at `src/generate_campaign.py:114` on master `13a64166`, re-checked at `2f97b9a6`
and unchanged, still iterating the library and raising on the first non-approved
offer. With 8 offers of which 2 are approved, that refuses every live run for
productive at `OFFER-PM-001`: correctly fail-closed and pointed at the wrong
question. **It blocks the critical path.**

The fix exists: `_select_offers` at `:174`, `_check_offers(client_name, segment,
persona)` at `:199`, call site `:118`, implementation `8fced7fc` (+53/−8, one
file), tests `bec395aa`. It is genuinely self-contained — the persona/segment
derivation moves above the gate — so it does not need the rest of TASK-400.

**NOT MERGED, deliberately.** `src/generate_campaign.py` is TASK-400's territory
and `origin/qwen-worker-r9` is the branch the orchestrator merges. Two things the
next hand must know: `bec395aa` also modifies `tests/test_changing_an_approved_fact_changes_the_output.py`,
`tests/test_task400_rework2.py`, `tests/test_the_entrypoint_actually_loads_its_skills.py`
and `tests/test_the_entrypoint_refuses_at_a_client_ceiling.py`, none of them named
in its FILES CHANGED; and its acceptance 7 (a failing-name SET diff against the
baseline) was not performed — "14 new tests, all passing" is not that.

## FOUR MORE FINDINGS WORTH THE ROW THEY SIT IN

- **`TASK-284`: the weekly candidate export's prior-touch column has always been
  empty.** `nightlysourcing._to_candidate` writes the record with the key
  `prior_touch_status` (`src/nightlysourcing.py:507`, reading `company["_prior_touch"]`
  set at `:450`) and `candidateexport.FIELD_MAP` looked up `_prior_touch`
  (`src/candidateexport.py:42`), which no record carries. Producer, canonical
  record and consumer now agree. One line. Merged.
- **`TASK-287`: `docs/state/PROBLEM-REGISTER.md` has two genuine ID collisions.**
  `ISSUE-011` at line 799 is "the LinkedIn ownership allowlist went stale" and at
  line 1507 is "The forward book's COVERING property decays silently";
  `ISSUE-012` at 756 is the 400-page search slice and at 1543 is the collision
  gate refusing a batch as NOT WALKED. Two more are deliberate re-use the lint
  cannot yet express (`ISSUE-006` + its "(original)" at 1038, `ISSUE-016` RECURRED
  at 376 above its original at 1216). The lint is merged and reports all four; the
  **test is refused** because renumbering an id that commits and handoffs already
  cite is the register owner's decision, not an integrator's.
- **`TASK-416`: a fact scored `strong` 200 days ago still reaches the draft
  prompt.** `generate.research_block` (`src/generate.py:215-248`) filters on the
  `quality` frozen at storage time and never calls `evidence.recheck`, `reaged` or
  `select`, which `research.for_prompt` does — so stale evidence sits beside a
  correctly re-aged `public_evidence` block. `evidence.py:477`'s own docstring
  describes this exact failure. `src/generate.py` is reserved by TASK-400, so the
  three-line fix is recorded, not made. The measuring tool is merged.
- **Two independent workers wrote the same forbidden import.**
  `tests/test_the_nightly_sourcing_pipeline.py:28` and
  `tests/test_a_reply_stops_the_other_channel.py:44` both did
  `from src.providers import ProviderError`, which master's own invariant
  `test_invariants.NoTestBindsAReloadedExceptionClass` forbids by name because a
  reload replaces the class and a bound name stops matching it. Both corrected on
  the way in to the form that invariant's failure message prescribes. A guard
  whose message only appears after the commit is a guard reaching nobody in time.

## THINGS A READER MUST NOT READ AS SAFE

1. **`TASK-315` does not close launch blocker 4.** 36 green tests pin the
   cross-channel stop in both directions and pin the readback trap, and every
   provider response in them is mocked. OPERATING-MODE's blocker 4 requires a
   readback against real provider state — "never inferred from logs or mocks" —
   and that needs separate operator authorisation. What landed is the test that
   will be true when the live validation happens.
2. **`TASK-284`'s DNS test carries its own copy of the thing it checks.**
   `tests/test_a_dns_failure_never_reads_as_allowed.py` RESTATES the S5 gate
   predicate as a module constant `MX_OK` rather than importing it from
   `scripts/stage_s5_verify.py`, and says so in a comment. It is real evidence
   about `src/mx.py`'s five outcomes and about the vocabulary mismatch between the
   module, the walk and the gate. It is NOT evidence that the deployed S5 tuple
   still refuses `dns_failure`, because it never reads the deployed tuple.
3. **`TASK-279`'s live run never happened.** Its result block is candid: the
   actor-id, HTTP-status and USD-per-account fields are unfilled. The script is on
   master as a tool; the measurement it exists to make has not been made.
4. **The four pre-existing export failures are worktree artifacts, not master
   defects.** `test_task245_…` ×3 and
   `test_review_may_not_reach_the_export.test_the_real_pool_on_disk_is_refused_today`
   read the real `work/candidates.jsonl`, which is gitignored and empty in a fresh
   worktree. The last one says so itself: "Not a fixture: the actual file".

## WHAT WAS NOT DONE, AND WHY

- **No provider was called. Writes 0, reads 0.** Nothing launched, activated,
  enrolled, attached, resumed or sent. Campaigns 487, 489 and 493 untouched.
  `sending.live` still off for productive. `docs/state/PROVIDER-CAMPAIGNS.json`
  not regenerated, because regenerating it is a provider read.
- **No reserved file was touched**: `src/bisonfactory.py`,
  `src/heyreachfactory.py`, `src/sequenceplan.py`, `src/generate.py`,
  `tests/test_generate.py`, `src/packfacts.py`, `src/ingest.py`,
  `src/copylint.py`. Twenty-two of the 63 sit on branches that modify one of
  them and are BLOCKED-ON-CRITICAL-PATH below. `TASK-427` is a
  twenty-third, on `src/generate_campaign.py` — not on the reserved list, but
  TASK-400's territory and on the orchestrator's branch.
- **`TASK-364`, `TASK-400`, `TASK-425` and `TASK-426` were not touched.**
- **No derived file was merged from a branch.** `docs/state/TASK-REGISTRY.json`
  on `qwen-worker-9-r9` was refused on the first pass's own rule.
- **The suite baseline file was not edited.** See finding 3.

## EVERY ONE OF THE 63, ONE ROW EACH

Verdicts are against the named head SHA, pinned at the moment of review. Where
the branch differs from the one `claim_task.py` named, the row says so.

| TASK | BRANCH REVIEWED | HEAD SHA | VERDICT | REASON / WHAT I DID | SUITE DELTA |
| --- | --- | --- | --- | --- | --- |
| TASK-271 | `qwen-worker-6-r58` | `c921c1348112` | **MERGE** | SAFETY. Compliance gate in `executionguard.authorize` gate 4; refuses every email step with no unsubscribe affordance. `+109/-0` on executionguard, so it cannot revert master. Mutation-falsified: disabling it turned four tests red and `gate` read `sender`, proving compliance fires first. Strengthened one test that stayed green under mutation. | 40 executionguard modules, 0 new names |
| TASK-284 | `qwen-worker-12-r59` | `a520841c33e0` | **MERGE** | Production correctness, traced producer→record→consumer: the export read `_prior_touch`, the record carries `prior_touch_status`, so the column was always empty. Plus MX-walk report, its script and four new test modules. | 20 modules, 0 new names |
| TASK-325 | `qwen-worker-r60` | `2594a3088814` | **MERGE** | The LinkedIn cadence document OPERATING-MODE cites as its authority existed on no ref reachable from master. Verified TRUE against `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1` before taking it. | 7 scanner modules, 0 new names |
| TASK-345 | `qwen-worker-r68` | `f95066072e12` | **MERGE** | `scripts/glm_verify_branch.py` + two sample reports. `dc302934` now requires a GLM verdict against every branch head reaching REVIEW; this is the tool that does it. Read-only apart from its report. Compiles clean. | 7 scanner modules, 0 new names |
| TASK-289 | `qwen-worker-6-r60` | `9154d87f2a30` | **MERGE** | Report only, `docs/APIFY-COST-SECOND-PASS-2026-09-25.md`. No code. | 0 new names |
| TASK-270 | `qwen-worker-5-r58` | `26eb2cd0cfbb` | **MERGE** | `src/slackknowledge.py` mechanism section, and it is CONSUMED, not merely present: the pack builder calls `cross_channel_stop()` at `slackknowledge.py:1111`, beside `workspaces_section()` at `:1109`. | 20 modules, 0 new names |
| TASK-274 | `qwen-worker-5-r58` | `26eb2cd0cfbb` | **MERGE** | Same artifact. Its finding was that the Slack agent answered "I am reasoning, not reporting" because the pack had no mechanism section; the section now exists and every claim in it names a line in `src/inbound.py` or `src/leadstop.py`. | as above |
| TASK-327 | `qwen-worker-2-r60` | `94819507ab30` | **MERGE** | `docs/state/ACCOUNT-MODEL-INVARIANTS.md` + `tests/test_the_account_relationships_survive.py`, both clean adds, 22 tests green. | 0 new names |
| TASK-279 | `origin/qwen-worker-4-r9-task279` | `980f3fdb` | **MERGE** | `scripts/pack_fetch.py` + its test, both absent from master. NOT the branch `claim_task.py` named — neither file exists on `origin/qwen-worker-4-r9`. Live run still owed and recorded as owed. | 11 modules, 0 new names |
| TASK-315 | `qwen-worker-4-r9-task280` | `cdffd0a2d3ba` | **MERGE** | 36 tests pinning the cross-channel stop both ways through `inbound.handle`, and pinning the readback trap. Does NOT close launch blocker 4 — all mocked. Fixed its forbidden `ProviderError` import. | 11 modules, 0 new names |
| TASK-414 | `origin/qwen-worker-11-r9` | `f7e95b58` | **MERGE** | `tests/test_spend_report_groups_by_real_client_id.py`. Imports only `src.spendledger` and `src.store`, so it stands alone. Its own conclusion is that the wiring is already right after TASK-346, so this is a pinning test, nothing behavioural. Branch head has since moved to `39561261`. | 11 modules, 0 new names |
| TASK-353 | `qwen-worker-9-r68` | `8ff73995d5b7` | **MERGE** | SUPERSEDED banners on five historical docs (`+19/-0` total, purely additive, the convention CLAUDE.md itself uses) plus `docs/DOC-TRUTH-SWEEP-2026-09-26.md`. Nothing historical was rewritten or deleted. | 7 scanner modules, 0 new names |
| TASK-287 | `qwen-worker-4-r60` | `8d98cb78410b` | **MERGE-PARTIAL** | TAKEN: `scripts/register_lint.py`, `docs/REGISTER-HYGIENE-2026-09-25.md`. REFUSED: its test, which goes RED on master. The finding is REAL — four duplicated register ids, two of them genuine collisions between different problems (ISSUE-011 at 799 vs 1507, ISSUE-012 at 756 vs 1543). Renumbering a cited id is the register owner's call. | 20 modules, 0 new names |
| TASK-285 | `origin/qwen-worker-3-r9-task285` | `c8a62f41` | **MERGE-PARTIAL** | Three paths taken: collision-walk script, its test, its report. THE BRANCH WAS REFUSED: its diff against master deletes `docs/INTEGRATION-QUEUE-2026-09-27.md`, `src/linkedin_match.py`, `src/reengagement.py`, all of `scripts/qa/` and sixteen tests including `test_sending_live_off_blocks_only_our_new_writes.py` — the killswitch proof committed tonight. | 11 modules, 0 new names |
| TASK-290 | `qwen-worker-9-r9` | `f1b9c357c17f` | **MERGE-PARTIAL** | `docs/COPYLINT-SECOND-PASS-2026-09-25.md` taken. Its test file HELD: its fixture approves one step while the campaign's sequence comes from `cadence.steps_for(None, config)`, so `bisonfactory`'s `missing_copy` stand-aside at `:649-652` may swallow all four assertions into a missing-steps refusal that names no rule; and test 4 stubs `copylint.check_batch` rather than letting a real rule bite. | 0 new names |
| TASK-416 | `qwen-worker-9-r9` | `f1b9c357c17f` | **MERGE-PARTIAL** | `scripts/measure_research_freshness.py` taken. Its finding is CONFIRMED on master and is the valuable half — stale evidence reaching the draft prompt, `src/generate.py:215-248`. The three-line fix is NOT made: `src/generate.py` is reserved. Acceptance (20+ records measured) still unmet. | 0 new names |
| TASK-192 | `qwen-worker-5-r59` | `2b3584534d6c` | **MERGE-PARTIAL** | `docs/BOUGHT-EVIDENCE-2026-09-16.md` taken. REFUSED: `.qwen-257.err` and `.qwen-257.out`, worker scratch at the repo root (the `.err` is a Qwen headless yolo warning); an 844-line growth of `scripts/task183_results.json`, an unreviewed data blob; and a one-line `SNAPSHOT` path change to a gitignored `work/` filename that cannot be verified from git. | 7 scanner modules, 0 new names |
| TASK-213 | `qwen-worker-4-r45` | `71f42b1e4eba` | **MERGE-PARTIAL** | `docs/FAIL-CLOSED-GROUPS-2026-09-16.md` taken. REFUSED `scripts/task213_locate_fail_closed.py`: a task-numbered one-shot production script — the same One-Truth/scope-drift pattern the first pass reworked TASK-303 for — whose comment reads "Live state is in Claude's worktree", baking the stale-`work/` trap into the tool. | 7 scanner modules, 0 new names |
| TASK-280 | `qwen-worker-4-r9-task280` | `cdffd0a2d3ba` | **MERGE-PARTIAL** | Three clean adds taken: `docs/REVERSE-RECONCILIATION-2026-09-25.md`, `scripts/reverse_reconcile.py`, `tests/test_reverse_reconciliation_is_exhaustive.py`. `src/spendledger.py` REFUSED — see TASK-308. | see final run |
| TASK-298 | `origin/qwen-worker-r9` | `ac4190cd` | **MERGE-PARTIAL** | Four paths taken: `scripts/qa/check_readback.py`, its two tests, `docs/QA-READBACK-2026-09-25.md`. `scripts/qa/__init__.py` REFUSED: the result block itself records that it "had been emptied to just a docstring" on this branch, and master's copy is the registry the first pass populated with TASK-297/299. Taking it would have emptied the registry. | see final run |
| TASK-245 | `origin/qwen-worker-4-r9` | `2cb8755afc8a` | **CLOSE** | ALREADY INTEGRATED and the branch is behind. `src/nightlysourcing.py` was added twice — `28e0b7d1` on the branch at 20:10 and `608d1a76` on master at 22:00 the same evening — and master then corrected it four more times, including `ac44f859` "The candidate export is stopped: ICP REVIEW was passing as IN". Blob-compared: `candidatelist.py` identical, the other three differ with master ahead. Its own result block also reports modifying `src/providers/aiark.py`, which its FILES FORBIDDEN list names. | none |
| TASK-231 | `qwen-worker-8-r28` | `36a4ce61b454` | **CLOSE** | ALREADY INTEGRATED at `b513879d` "Integrate TASK-231: the timeout aborts the socket, and it is still a ProviderError", confirmed an ancestor of master. Merging the branch would delete 571 lines of master's provider-guard work on `src/providers/__init__.py`, including two GLM security rounds (`23d7a71e`, `0081027a` — "a bytes verb walked past the guard", "GLM found a bypass in the guard I wrote hours earlier"). | none |
| TASK-408 | `origin/qwen-worker-4-r9` | `2cb8755afc8a` | **CLOSE** | NEVER STARTED. `git log --all --name-status` over its task path returns only three adds of the **TODO** file (`26e68e6b`, `4a4473ae`, `a681ecfa`, one refill commit re-pushed); `git log --all --diff-filter=A -- "docs/glm-reviews/TASK-408*"` is empty. No claim, no branch, no artifact. An unstarted TODO was being reported as a result awaiting integration. | none |
| TASK-402 | `qwen-worker-9-r9` | `f1b9c357c17f` | **CLOSE** | Verification record, no artifact to integrate, and it HOLDS: every cited line reproduces against master (`render_prompt` call sites in `generate.py`, `copyprompts.py:79/184`, `copystages.py:191/273`), and both sharp claims check out — `stage_a|stage_b|stage_e|stage_f` has zero matches in `src/generate.py`, and `generate_campaign` has zero hits in `src`/`scripts` although the file exists. It made a real falsification attempt rather than rubber-stamping. Its closing instruction cannot be executed: TASK-391 is still TODO on master with its result unintegrated. | none |
| TASK-226 | `qwen-worker-8-r28` | `36a4ce61b454` | **REWORK** | MERGED THEN REVERTED. The offset index makes `replay()` seek past corrupt lines, so `JournalCorrupt` stops being raised: four previously-green guards in `test_a_checkpoint_costs_what_it_changed.JournalTest` go red (torn middle line, entry without a record, record without an id, torn final line). The result block claims "all 11 existing journal tests pass UNCHANGED" — false. `QUEUE_JOURNAL` is default OFF so master is not exposed, which is what would have made this a quiet one to ship. The index must rebuild and VALIDATE on read. | reverted; guards green again (23 tests OK) |
| TASK-308 | `qwen-worker-4-r9-task280` | `cdffd0a2d3ba` | **REWORK** | MASTER'S OWN MERGE BLOCKER STILL APPLIES: `docs/MERGE-BLOCKER-ANTHROPIC-SPEND-IS-UNCAPPED-2026-09-25.md` says "Do not merge TASK-308 or TASK-309 until this is fixed" and prescribes the order. Master already has the fix (`LEDGER_UNITS` with `anthropic: microusd`, `spendledger.py:152`). The branch's `src/spendledger.py` would delete master's whole per-provider-ceilings lane — `reserve`/`holding`, `PROVIDERS_KEY`, the reservation docs — 165+ lines of it. Rebase and call `record(..., unit="microusd")` instead of `_append_row`. | not merged |
| TASK-266 | `qwen-worker-r58` | `cf1515fb4073` | **REWORK** | DISCONNECTED. `src/learningrules.py` is a new 263-line module and `git grep -n learningrules cf1515fb4073 -- src scripts` returns NOTHING — zero importers on its own branch, let alone on master. Existence is not function. | not merged |
| TASK-305 | `qwen-worker-9-r9` | `f1b9c357c17f` | **REWORK** | DISCONNECTED, and a third path to a live one. `src/providers/groq.py` and `openrouter.py` are absent from master (CLAUDE.md is right) and are good code — they reserve/settle/release through the ledger correctly. But `complete()` has ZERO production callers: `git grep` finds only the modules' own docstring, CLI string and mutual fallback. Compare `glm.py`, the module the task said to copy, called from `scripts/glm_review.py:555` and `scripts/glm_audit_safety.py:147`. Master ALREADY runs Groq through `src/llm.py:OpenAICompatibleModel`, whose `_detect_provider()` returns `"groq"` at `llm.py:274`, already ledgered. Also `scripts/credential_health.py` cannot be split off: `state_of()` does `__import__("src.providers." + name)` inside an except whose tuple excludes `ModuleNotFoundError`, so the `+2` lines alone would report a good `GROQ_API_KEY` as AUTHENTICATION_FAILED. | not merged |
| TASK-392 | `qwen-worker-9-r9` | `f1b9c357c17f` | **REWORK** | Finding CONFIRMED (no mailbox carries a signature; `senderinventory.provider_state()` returns eleven keys and none is it, while `scripts/propose_sender_attestation.py:139` reads `email_signature` and `:152` says the provider publishes it). The artifact is refused: all four assertions are `assertNotIn`, green BECAUSE the defect exists and red the day it is fixed, and the docstrings admit it. Worse, `test_cadence_render_has_no_signature_variable` asserts `cadence.render(...)` has no `"signature"` key, which passes in any codebase including one where signatures fully work — a test that cannot fail. Invert the assertions and delete that one. | not merged |
| TASK-313 | `qwen-worker-9-r9` | `f1b9c357c17f` | **REWORK** | The 700-line audit is absent from master and is a strong artifact — BUG-1 reproduces unusually well (`git grep -n generate_campaign origin/master -- src scripts` is zero while `src/generate_campaign.py` exists). Two claims are FALSE and one is an operator-facing headline: its Executive Summary item 2 says `LINKEDIN_STOP_LEAD` is not in `SUPPORTED`, and it is, at `src/providerwrites.py:541`, already there at the audit's own stated baseline — and the task's own result block finding 2 says the opposite, so the document contradicts its result block; and section 12's "No freshness policy for research" is refuted by `evidence.recheck/reaged/select` at `src/evidence.py:477/519/546`, which TASK-416 on the same branch documents in detail. Correct both, then merge. | not merged |
| TASK-404 | `qwen-worker-9-r9` | `f1b9c357c17f` | **REWORK** | It did the right things — checked READ-ONLY first, correctly classified `POST /li_account/GetAll` as a read on the allowlist, and caught a real arithmetic defect in its target rather than waving it through (TASK-397's "13 seats totalling 694" reproduces as 12 totalling 229). But raw scratch reasoning is left in an operator-facing review ("Wait — the task says 13. Let me recount from the table"), and its recommendation 1 cherry-picks `docs/TASK-397-SEAT-CAP-FINDINGS.md`, which is on no ref. Strip the scratch; the recommendation is not actionable. | not merged |
| TASK-399 | `qwen-worker-9-r9` | `f1b9c357c17f` | **REWORK** | Report-only and honest, but its value is EDITS to master's files and must be hand-applied, never file-picked. Of the twelve, spot-checked four: correction 1 (CLAUDE.md's stale handoff pointer) was FIXED by `645fb482` tonight, independently, while this pass ran; correction 2 (CLAUDE.md's `generated_at 2026-09-26T18:29:43Z`) is still live; correction 6 (OPERATING-MODE:37 "Five skills verified ready on branch, not yet integrated", false — they are in `src/skills/`) is still live; correction 4 is moot, master's SHA line is now later than the one it proposed. | not merged |
| TASK-326 | `origin/qwen-worker-r9` | `ac4190cd` | **REWORK** | Artifact real — `_load_account_evidence`/`for_account`/`for_contact` at `src/secondbrain.py:247/267/281`, none of those names on master, plus a clean-add test. But its STATUS reads "DONE (acceptance tests 1-5 pass, full suite running)" with acceptance 6 PENDING: a DONE stamped before its own acceptance returned. `src/secondbrain.py` is not reserved, so this is a real two-file port once the suite answer exists. | not merged |
| TASK-264 | `origin/qwen-worker-4-r9` | `2cb8755afc8a` | **REWORK** | NO RESULT EXISTS. On `ac4190cd` the task file moved TODO→RUNNING as a pure rename, so there is nothing to grade. Two independent implementations are in flight — `tests/base.py` + `scripts/measure_isolation.py` on `qwen-worker-r9`, and `tests/base.py` + `test_no_test_leaves_the_environment_changed.py` on `qwen-worker-11-r59 @ e04c1fda` — the duplicate-implementation pattern the first pass flagged. Pick one. A GLM verification of it already exists, which is odd given there is nothing yet to verify. | not merged |
| TASK-262 | `qwen-worker-10-r59` | `1c8377bd4dcc` | **REWORK** | The first pass named this one to take over TASK-250, and it is not takeable as it stands. `tests/test_e2e.py` narrows `E2EModel.complete(self, prompt, temperature=0, client=None, config=None)` back to `complete(self, prompt)`, reverting master's TASK-373 "thread client and config through every model.complete call site". And its `tests/base.py` hunk changes `fixture_config`, which the whole suite uses, so it cannot be validated by module-targeted runs — it needs a rebase plus one full-suite set diff. The value is real (these tests are red because the productive client file now names deliverable as primary verifier and they are about the waterfall, not the client file). | not merged |
| TASK-249 | `qwen-worker-8-r61` | `8e6ee5edcb1c` | **REWORK** | `src/slackagenttools.py` is a clean apply (`+436/-0`, master unmoved) but `src/slackconversation.py` is a real 3-way: the branch adds `+19/-0` while master moved `+8/-5` via `77221f9f` (TASK-373). The 436 lines have their consumer in the file that needs the 3-way, so a file-level take of either half is wrong. Rebase and re-apply the 19 lines. | not merged |
| TASK-340 | `qwen-worker-4-r67` | `85b82ddc7ec4` | **REWORK** | Its value is in `src/llm.py` (`+35/-2`) and `src/providers/glm.py` (`+12/-1`), and master has moved `+83/-29` and `+59/-15` on those same files via `77221f9f` (TASK-373, threading client and config) and `2fdb5568` (TASK-346, refusing a model call at a ceiling). A file-level take reverts both. Rebase. | not merged |
| TASK-360 | `qwen-worker-2-r70` | `29f90f7bee91` | **REWORK** | The model router OPERATING-MODE names, and neither `config/model_policy.yaml` nor `src/modelrouter.py` exists on master (see finding 4). It IS wired on its branch — `src/llm.py:559`, `src/providers/glm.py:68`, `src/providers/xai.py:30` all import it. That is also why it cannot be file-picked: the wiring lives in the same `llm.py`/`glm.py` master moved `+83/-29` and `+59/-15` on. Taking only the clean adds would leave `modelrouter` with zero importers, i.e. DISCONNECTED, which is not an honest partial. Rebase onto master and re-apply ~24 lines of wiring. | not merged |
| TASK-288 | `qwen-worker-6-r59` | `357c1ffffdd0` | **REWORK** | Its only artifact does `from src.account_rule import evaluate` at line 44, and `src/account_rule.py` is on neither master nor TASK-288's own branch — it was added by `46846329` on some other ref. `unittest` reports `ModuleNotFoundError`; the test cannot be imported, let alone run. Must land with, or after, whatever carries that module. | refused; would have been a load error |
| TASK-427 | `origin/qwen-worker-r9` | `ac4190cd` | **BLOCKED-ON-CRITICAL-PATH** | THE HIGHEST-VALUE UNINTEGRATED ITEM. Operator decision 5 is unimplemented on master: `_check_offers(client_name)` at `src/generate_campaign.py:114` still iterates the library, which refuses every live productive run at `OFFER-PM-001`. Fix is `8fced7fc` + `bec395aa` on this branch and is self-contained. Not merged because `src/generate_campaign.py` is TASK-400's territory and this is the orchestrator's branch. Two caveats for whoever takes it: `bec395aa` also edits four test files it does not name, one of them TASK-400's own; and its acceptance 7 set diff was never run. | not merged |
| TASK-422 | `origin/qwen-worker-4-r9` | `2cb8755afc8a` | **IN FLIGHT** | Claimed TODO→RUNNING at 2026-09-27 23:25:59, ninety seconds before this pass looked. No result block. It needs a real read-only provider read, which has not happened and which this pass did not make. Nothing to integrate. | none |
| TASK-272 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/ingest.py`, reserved by the CLIENT_SUPPLIED provenance work. 18 changed non-task files. | none |
| TASK-335 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-405 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-409 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-415 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-417 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-424 | `qwen-worker-12-r9` | `d274ec55bbd8` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. TASK-424 is the lease-based registry OPERATING-MODE names as the scheduler instance of "state is explicit"; worth unblocking early. | none |
| TASK-311 | `qwen-worker-6-r9` | `56dd4fcd021c` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/ingest.py`, reserved. 32 changed non-task files. | none |
| TASK-387 | `qwen-worker-6-r9` | `56dd4fcd021c` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-419 | `qwen-worker-6-r9` | `56dd4fcd021c` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-423 | `qwen-worker-6-r9` | `56dd4fcd021c` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-428 | `qwen-worker-6-r9` | `56dd4fcd021c` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, same reserved file. | none |
| TASK-357 | `qwen-worker-r69` | `a66b6c5bc8a8` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/ingest.py`, reserved. | none |
| TASK-294 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Branch modifies `src/bisonfactory.py`, `src/generate.py`, `src/heyreachfactory.py`, `src/sequenceplan.py` — four reserved files — and is the branch the orchestrator merges for TASK-364/400/426. Head moved four times during this pass (`b7df7715`→`11cd35ed`→`7e79c6b4`→`d291fc15`). | none |
| TASK-302 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-319 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-389 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-406 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-407 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-418 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-420 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | Same branch, four reserved files. | none |
| TASK-429 | `origin/qwen-worker-r9` | `d291fc1580a9` | **BLOCKED-ON-CRITICAL-PATH** | New since the first pass — it is in the status listing and in no first-pass row. Same branch, four reserved files. | none |

## WHAT THE NEXT PASS SHOULD DO FIRST

1. **`TASK-427`**, by the orchestrator, onto `src/generate_campaign.py`. It is the
   one item in this queue that unblocks the critical path, and master is still
   unfixed at `:114`.
2. **`TASK-360` rebased.** `config/model_policy.yaml` is named by a standing
   invariant and exists nowhere on master. One rebase, ~24 lines of wiring.
3. **`TASK-262` rebased**, then one full-suite set diff. It is the only item here
   that plausibly clears a block of baseline failures, and it cannot be judged
   from targeted runs.
4. **Renumber the two genuine `PROBLEM-REGISTER.md` collisions** (ISSUE-011,
   ISSUE-012) and give the two deliberate re-uses a form the lint accepts, then
   land `tests/test_the_register_has_no_duplicate_ids.py`.
5. **Fix `claim_task.py`'s branch attribution**, or stop printing a branch name
   next to a result. Ten rows in this queue named a branch that does not hold the
   artifact, and a verdict against the wrong SHA is void here by standing rule.
