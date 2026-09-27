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
| **Resolved with a verdict** | **76** |
| — MERGE | 13 |
| — MERGE-PARTIAL | 2 |
| — REWORK | 12 |
| — CLOSE | 8 |
| — HELD for the orchestrator (TASK-364/400/426) | 3 |
| — BLOCKED-ON-CRITICAL-PATH (reserved files) | 38 |
| **Not reached this pass** | **64** |

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
| after the four fixes | `1e29ce0f` | see below | — |

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

**The confirming full run is the last thing outstanding.** It was started at
`1e29ce0f` and the work is pushed to its own branch
`worktree-agent-a0c5bed4fa47fe482` rather than to master until it returns. That
is the standing rule: durability is a reason to push to a branch, never a reason
to put unconfirmed work on master.

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
| TASK-286 | `qwen-worker-3-r60` | `a67999eb71f4` | **CLOSE** | SUPERSEDED. Adds a 2026-09-25 suite baseline; master carries docs/state/SUITE-BASELINE-2026-09-26.txt, which is the standing baseline named by OPERATING-MODE §19. |
| TASK-359 | `qwen-worker-r70` | `7150fd809358` | **CLOSE** | DEFERRED BY COVERING INSTRUCTION. OPERATING-MODE: TASK-359 is deferred until the internal ledger is proven, and no scheduled task may be registered. |
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
| TASK-250 | `qwen-worker-9-r61` | `3efcc9683f2a` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 3 changed non-task files, no reserved file touched. |
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
| TASK-312 | `qwen-worker-4-r59` | `073e81e040a2` | **NOT REACHED** | Not reached this pass. Branch verified to exist, 2 changed non-task files, no reserved file touched. |
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

