PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-913 — the writer contract must produce five emails and five LinkedIn steps

**Operator, Zvonimir, 2026-09-29, after TASK-912 produced a clean failure.**
Two generation-contract defects, both located. **Fix the contract. Do not
weaken the requirement, do not allow fewer steps, do not insert copy
downstream, do not generate filler, do not patch drafts.**

**OUT OF SCOPE — do not touch:** qualification, Second Brain (TASK-911 is
closed), Offer Engine, evidence licensing, `copylint` acceptance rules, Slack,
TASK-564/565. **No other account.**

## What TASK-912 measured

Everything before the writer passed: `QUALIFIED_THIN`, persona
`economic_buyer`, canonical slug `productive`, Second Brain 26 relevant with
`profitability` and `budgeting` present, strategy + hypothesis built, Offer A
selected. Then, three attempts:

    attempt 1   em1 407   em2 0   em3 365   em4 0   em5 0
    attempt 2   em1 405   em2 0   em3 0     em4 0   em5 0
    attempt 3   em1 361   em2 0   em3 0     em4 0   em5 0
    linkedin    connect 147-157  msg1 154-168  msg2 160-206  msg3 115-140

`copylint` correctly refused `empty_step`. `missing_opt_out` was collateral —
`optout.append_opt_out("")` returns `""`, so an empty body trips it too.

## ROOT CAUSE — BOTH DEFECTS ARE IN ONE PLACE

`src/copystages.py`, the `WRITER_SYSTEM` OUTPUT block:

    "emails":{"em1":"<full body, 60-90 words>","em2":"","em3":"","em4":"","em5":""},
    "ps":{"em1":"","em3":""},
    "linkedin":{"connect":"","msg1":"","msg2":"","msg3":""},
    ...
    A step the plan dropped is written as an empty string, not invented.

1. **The template DEMONSTRATES emptiness.** Only `em1` carries a content
   placeholder; `em2`-`em5` are shown as `""`. The model reproduces the shape
   it is shown.
2. **The closing line still LICENSES emptiness.** TASK-910 removed the prose
   instruction ("set it null... four good messages beats five") but this line
   survived and says the same thing. **The contract still permits what
   `copylint` refuses.**
3. **LinkedIn has only four keys** — `connect`, `msg1`, `msg2`, `msg3` — while
   the canonical cadence declares five li steps. **`li5` is structurally
   unreachable**, regardless of model behaviour.

Measured canonical cadence for this client (`cadence.steps_for`):

    li1 d1 · em1 d1 · li2 d3 · em2 d4 · li3 d6 · em3 d8 · li4 d10 · em4 d12 · li5 d15 · em5 d21

**And the key tuple is duplicated three times** in
`src/generate_campaign.py` — lines ~765, ~806, ~817 all hardcode
`("connect", "msg1", "msg2", "msg3")`. **That is three authorities for one
mapping.**

## PART A — the email contract

In `copystages.WRITER_SYSTEM`:

- Give **every** one of `em1`-`em5` a real content placeholder, so the template
  never shows an acceptable empty body.
- **Delete the "written as an empty string" licence.** It contradicts the
  TASK-910 contract already in the same prompt, which says all five are
  required and that insufficient evidence means a **generation failure**, not a
  short sequence.
- Make the **sequence ROLES** explicit, as functions and never as claims:

      em1  initial evidence-led relevance / value hypothesis
      em2  follow-up from a different relevant Productive capability or angle
      em3  deepen the same business case via another licensed angle/evidence
      em4  concise objection/friction reducer, or an alternative framing
      em5  close-the-loop, permission-based final message

  **These are functions, not facts.** Every prospect-side factual statement
  still needs licensed prospect evidence. CLIENT_SUPPLIED Productive knowledge
  guides the value proposition and **never** licenses a claim about the
  account.

In `src/skills/cold_email_writing.py`'s `output_schema`, `em2`-`em5` are
declared `"str"`, and `""` satisfies `"str"`. **Require non-empty** for
`em1`-`em5` and for the five LinkedIn steps, using the declaration style
already in that file (`"str (60-90 words)"` shows the convention).

**If a schema-validation mechanism already exists, use it** — `src/llm.py`
carries `SCHEMAS`, `_qwen_json_schema` and `_schema_type_for`, and its module
docstring says output is "validated against a schema before it touches the
store" with a retry on schema failure. **Use the existing mechanism. Do not
build another generation or validation framework.** If the campaign writer
genuinely cannot use it, say so in the result block with the reason.

## PART B — the LinkedIn contract

The writer must be asked for **five** LinkedIn steps.

- **Prefer canonical names `li1`-`li5`.** `heyreachfactory` already maps
  `li1`..`li5` to the provider graph roles (`connection_note`, `connected_1`,
  `connected_2`, `connected_3`, `connected_4`), so canonical names make the
  writer-to-cadence mapping an identity.
- If a compatibility boundary genuinely requires the legacy
  `connect`/`msg1`-`msg3` names internally, keep them **but prove the mapping
  is explicit, deterministic, complete and yields all five canonical steps**,
  and say where the boundary is.
- **There must be exactly ONE authority for the key list.** Replace the three
  hardcoded tuples in `generate_campaign.py` with a single named constant and
  read it at all three sites.

**Do not add `li5` downstream. Do not duplicate `msg3`. Do not fabricate a
fifth message.** The writer produces it or generation fails.

## PART C — focused tests

Prove, each as its own assertion:

1. the writer schema requires `em1`-`em5`
2. a missing `em2` FAILS
3. a missing `em4` FAILS
4. a missing `em5` FAILS
5. the writer schema requires all five LinkedIn steps
6. a missing `li5` FAILS
7. the canonical cadence and the writer schema contain the **same** five email
   and five LinkedIn steps — compare as SETS against `cadence.steps_for`
8. the parser cannot silently turn missing writer output into an acceptable
   empty step
9. no downstream component manufactures a missing step
10. a complete 5+5 writer output reaches `SequencePlan`
11. `li5` survives into `SequencePlan`
12. `li5` survives the canonical provider projection
13. `em1`/`em3` P.S. behaviour unchanged
14. opt-out behaviour unchanged
15. signature behaviour unchanged
16. unsupported prospect claims remain blocked
17. CLIENT_SUPPLIED knowledge still cannot independently license a prospect
    claim

## THE PRE-EXISTING RETRY DEFECT — do NOT fix, do NOT hide

`tests.test_generate` currently carries a **known pre-existing** baseline:

    56 collected · 53 passed · 2 failed · 1 error

    ERROR test_a_draft_that_breaks_a_rule_is_regenerated_not_patched
          KeyError: 'rowan-blake'
    FAIL  test_the_model_is_told_what_failed_rather_than_the_draft_being_edited
          AssertionError: 2 != 1
    FAIL  test_the_retry_names_the_banned_phrase_rather_than_the_code
          AssertionError: 2 != 1

Red at `143f132f` and every commit since. **Do not fix or redesign it here.**

**BUT: if your contract fix changes those tests in any way — count, name, or
error type — STOP and report the interaction before broadening scope. Do not
hide a changed baseline.** Report the signature before and after.

## Acceptance

1. Writer contract supports 5 emails + 5 LinkedIn steps.
2. All 17 focused tests pass.
3. No previously-green relevant suite regresses.
4. `test_generate` baseline is **not worse** and its signature is unchanged.
5. **MUTATION:** restore one empty-string placeholder in the OUTPUT template;
   the corresponding focused test must go red for that reason. Restore and
   verify byte-identical by sha256. Files are **CRLF** — an `\n`-anchored
   regex matches zero times and the mutation becomes a silent no-op.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_task910_writer_contract
    py -3 -m unittest tests.test_task911_second_brain_canonical_status
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_approve
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate

    py -3 -c "import sys; from src import copystages; s=copystages.WRITER_SYSTEM; bad=[k for k in ('em2','em3','em4','em5') if ('\"%s\":\"\"' % k) in s.replace(' ','')]; sys.exit('template still shows empty: %r' % bad) if bad else print('OK: no empty email placeholders')"

    py -3 -c "import sys; from src import copystages; s=copystages.WRITER_SYSTEM; sys.exit('the empty-string licence is still present') if 'written as an empty string' in s else print('OK: licence removed')"

**Read exit codes OFF THE PROCESS, never through a pipe.**

## Files
`src/copystages.py`, `src/skills/cold_email_writing.py`,
`src/generate_campaign.py`, plus your own tests. **Do NOT touch**
`src/copylint.py`, `src/lint.py`, `src/secondbrain.py`, `src/offers.py`,
`src/packfacts.py`, `src/render.py`, `src/bisonfactory.py`,
`src/sequenceplan.py`, `src/trailingcontent.py`, `src/optout.py`.

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`**; verify HEAD equals
  `origin/master` before working.
- **NEVER WIDEN A GATE.** `copylint` and `STEPS_EXPECTED = 5` are correct and
  stay. The contract was wrong, not the gate.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **Do not report a PREDICTED result.** Run it and measure it.
- **PROVIDER WRITES = 0.** `sending.live` false, freeze active. Nothing sent,
  enrolled or attached. **Do not run generation against production `work/`** —
  copy it if you need estate data.
- **Write suite logs OUTSIDE the repository.** A suite with no `Ran N tests`
  line is an **absent measurement, not a failure**.
- Commit every file you touch — an uncommitted line once blocked three
  dispatches.
- Commit and push to your own branch and **verify the remote with
  `git rev-parse`**. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**The operator is waiting to read the actual five emails and five LinkedIn
messages for Rachele Crumpler at 2020 Companies. This contract is the only
thing standing between them and that copy.**

---

# REWORK 1 — 2026-09-29, Claude (merge authority). NOT MERGED.

**Branch `qwen-worker-3-r21` head `3d1ae79e`. THE WRITER FIX IS CORRECT AND
VALIDATED. Do not change it.** The remaining defect is a consumer migration,
and **the file restriction in the original brief is what made it incomplete —
that was my error, and this rework corrects the allowed file list.**

## MEASURED AND ACCEPTED — do not touch

Real Rachele run, isolated copy, model invoked:

    qualification      QUALIFIED_THIN
    persona            economic_buyer
    offer              OFFER-A-ECONOMIC-BUYER {profitability, budgeting}
    sequences keys     em1..em5, li1..li5, ps_em1, ps_em3   (12, ALL non-empty)
    copylint           PASS   hold_kind None   held None

**Do NOT change** the writer contract, qualification, Second Brain, Offer
Engine, evidence licensing, `copylint`, or the generated copy. The copy is
good; it simply cannot reach the plan.

## THE DEFECT — stale consumers, measured

    writer     5 emails + 5 LinkedIn, all non-empty, gates PASS
    SequencePlan   EMPTY
    HeyReach projection   0 leads

Because these still read the legacy four keys:

    src/sequenceplan.py:192        for key in ("connect","msg1","msg2","msg3")
    src/generate.py:2093           _PLAN_LINKEDIN_ORDER = ("connect","msg1","msg2","msg3")
    src/generate.py:2200-2202      sequences.get(_PLAN_LINKEDIN_ORDER[n])
                                   guarded by `if n >= len(_PLAN_LINKEDIN_ORDER): break`

Proven: `sequenceplan.derive_heyreach_payload(plan)` returns **0 leads** while
the plan carries all five `li*` keys non-empty. The stored log reads *"the
writer produced no copy for any generated step (em1..em5, li2..li5)"*.

**There is also a four-element CAP.** Even with correct names, `n >= 4` breaks,
so only four steps would ever map. **Remove the cap.**

## FIX — one authority, no duplicated tuple

`src/generate_campaign.py` already defines the authority TASK-913 introduced:

    LINKEDIN_WRITER_KEYS = ("li1", "li2", "li3", "li4", "li5")

**Make that the single authority for every production consumer.** If importing
it into `sequenceplan.py` or `generate.py` would create an import cycle, move
the constant to a module both already import and have `generate_campaign` read
it from there — **but there must be exactly ONE tuple in the codebase.** Do not
add a second.

**Delete the stale production authorities** at `sequenceplan.py:192` and
`generate.py:2093`, and remove the four-element cap at `generate.py:2200-2202`.

### LEGACY STORED RECORDS — measured: no compatibility layer is needed
**Do not build one.** Measured across production `work/`: **467 li steps
declared estate-wide, ZERO carrying copy, ZERO of 1,099 records with any
LinkedIn copy.** There is no stored `connect`/`msg1`-`msg3` copy anywhere to be
compatible with. If you find evidence to the contrary, **stop and report it**
rather than adding a shim.

### copyprompts — SETTLED, leave it alone
`src/copyprompts.py:391-394` sits inside the module constant `COHORT_SYSTEM`
(begins line 248). **Measured: `COHORT_SYSTEM` has ZERO references anywhere
outside `copyprompts.py` — not in `src/`, not in `scripts/`, not in `tests/`.**
The canonical path calls only `icp_user`, `extract_user`, `source_url_for` and
`ps_variant_for`. **It is dead-path debt. Do NOT touch it and do NOT broaden
this task into a legacy cleanup.**

## Acceptance — 18 points

1. canonical writer emits `li1`-`li5`
2. all five non-empty
3. SequencePlan consumes `li1`-`li5`
4. SequencePlan contains exactly five LinkedIn steps
5. `li5` exists in SequencePlan
6. **no four-element production cap remains** — assert it, do not eyeball it
7. provider projection receives all five LinkedIn steps
8-12. projected `li1`..`li5` each **equal** the canonical plan's value
   (`assertEqual` on the strings, not "contains")
13. no downstream component manufactures missing copy
14. all five email steps survive unchanged
15. `em1`/`em3` P.S. behaviour correct
16. opt-out correct
17. signature correct
18. approval material can be constructed from the complete canonical plan

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_task910_writer_contract
    py -3 -m unittest tests.test_task911_second_brain_canonical_status
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_approve
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate

    py -3 -c "import sys; from src import generate; sys.exit('legacy order still present') if getattr(generate,'_PLAN_LINKEDIN_ORDER',None)==('connect','msg1','msg2','msg3') else print('OK: legacy order gone')"

    py -3 -c "import sys,re; s=open('src/sequenceplan.py',encoding='utf-8').read(); sys.exit('legacy tuple still in sequenceplan') if re.search(r'\"connect\"\s*,\s*\"msg1\"', s) else print('OK: sequenceplan migrated')"

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING test_generate — keep visible, do NOT fix

    56 collected · 53 passed · 2 failed · 1 error
    ERROR test_a_draft_that_breaks_a_rule_is_regenerated_not_patched  KeyError: 'rowan-blake'
    FAIL  test_the_model_is_told_what_failed_rather_than_the_draft_being_edited  AssertionError: 2 != 1
    FAIL  test_the_retry_names_the_banned_phrase_rather_than_the_code            AssertionError: 2 != 1

Red at `143f132f` and every commit since. **Do not fix it here. If the
signature changes at all — count, name or error type — STOP and report why.**

## Files
`src/sequenceplan.py`, `src/generate.py`, `src/generate_campaign.py`, plus your
own tests. **Do NOT touch** `src/copystages.py` (the writer contract is
correct), `src/skills/cold_email_writing.py`, `src/copyprompts.py`,
`src/copylint.py`, `src/lint.py`, `src/secondbrain.py`, `src/offers.py`,
`src/packfacts.py`, `src/render.py`, `src/bisonfactory.py`, `src/optout.py`,
`src/trailingcontent.py`.

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`.** **First command:**
  `git merge --no-edit origin/qwen-worker-3-r21` — the writer fix lives there.
  Confirm your TASK-913 commits are present, then migrate the consumers on top.
- **NEVER WIDEN A GATE.** `copylint` and `STEPS_EXPECTED = 5` stay.
- **Do not manufacture a missing step downstream.** If the writer did not
  produce it, it does not exist.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **MUTATION:** restore the four-element cap; acceptance 6 and 7 must go red for
  that reason. Restore and verify byte-identical by sha256. Files are **CRLF**.
- **PROVIDER WRITES = 0.** `sending.live` false. Nothing sent, enrolled or
  attached. **Production `work/` is READ-ONLY — copy it if you need estate
  data.**
- Suite logs OUTSIDE the repository. A suite with no `Ran N tests` line is an
  absent measurement, not a failure.
- **Commit every file you touch.**
- Push to your own branch and verify the remote with `git rev-parse`. Do NOT
  merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**The copy for Rachele Crumpler at 2020 Companies already exists and already
passes every gate. This migration is the only thing between the operator and
reading it.**
