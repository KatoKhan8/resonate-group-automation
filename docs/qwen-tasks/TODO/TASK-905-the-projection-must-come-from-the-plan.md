PRIORITY: P0
SIZE: M
DEPENDS: TASK-904

# TASK-905 — the EmailBison projection must be derived from the canonical plan

**Required by the artifact: it must show an EmailBison projection, and that
projection must come from the one canonical SequencePlan.**
**GLM VERIFIES THIS TASK** — it is a provider-payload boundary.
**Serialised after TASK-904: same file. Do not start until 555 has landed.**

## The state, measured twice

    sequenceplan.derive_bison_payload     ZERO callers
    sequenceplan.derive_heyreach_payload  ZERO callers
    sequenceplan.derive_preview_data      ZERO callers

and those three are the **only** callers of `sequenceplan.approval_hash` — so
**the approval hash is never computed in production.** That is the mechanical
root cause of launch blocker 1. Confirmed statically (whole-repo call graph,
`docs/P0D-PRODUCTION-CALLER-2026-09-28.md`, `01dd7b78`) and **at runtime** with
two independent instruments (`1330815c`): generator ENTERED, SequencePlan
CREATED, canonical projection **NOT ENTERED**, approval hash **NOT ENTERED**.

Meanwhile the payload's words are built by `bisonfactory._approved_copy` from
`rec["cadence"]` — measured at **4 calls** in one dry run while
`derive_bison_payload` ran **0**. The plan's SHAPE flows; its WORDS do not.

## Scope — the SMALLEST change that makes the projection come from the plan

**Do the minimum for the slice. Do not build an abstraction.** P0-D specified
step 1 and it is deliberately small: **repoint ONE reader in
`src/bisonfactory.py`** so the payload's words derive from the plan rather than
from `rec["cadence"]`. Do not remove the other two projections' dead code, do
not refactor the plan, do not generalise.

## Acceptance — the third assertion is the one that matters
Use `scripts/runtime_approval_hash_probe.py --mode project` (`1330815c`), the
reusable check:

    derive_bison_payload         >= 1
    approval_hash                >= 1
    bisonfactory._approved_copy  == 0     <-- THE ONE THAT MATTERS

**`_approved_copy == 0` is what proves the projection derives ONLY from the
plan.** A new caller can be added while the old words-builder keeps running
beside it — payload derives from the plan, hash gets computed, every other
check passes, and the parallel implementation is still there, still able to
drift. "Only" is what that assertion measures.

Plus:
4. The projection's content matches the plan's content field for field.
5. **NEGATIVE CONTROL:** mutate the plan's copy and the projection must change
   with it. If it does not, the projection is not derived from the plan.
6. **NEGATIVE CONTROL:** bypassing the canonical projection FAILS.
7. **Approval binding:** changing approved content invalidates the approval;
   regenerated copy cannot reuse an old approval.
8. **PROVIDER WRITES = 0 throughout**, with an interceptor **fired
   deliberately** so a zero count means something.

### ACCEPTANCE COMMANDS — run these exactly and paste the real output

**These must stay in THIS section.** GLM's extractor enters at the first
`## Acceptance` heading and stops at the next `## `, so commands in a later
section are invisible to it — that cost three `NEEDS_CLAUDE` verdicts on
TASK-560/907. It only picks up lines beginning `py -3`, `python`, `grep` or
`scripts/`, so prose and the assertion table above are safely ignored.

    py -3 scripts/runtime_approval_hash_probe.py --mode project
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task560_ps_reaches_the_person
    py -3 -m unittest tests.test_task907_ps_producer_hop
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_the_research_pack_has_one_shape
    py -3 -m unittest tests.test_approve
    py -3 -m unittest tests.test_generate

**The probe is the gate**, and `bisonfactory._approved_copy == 0` is the
assertion that matters. All seven unittest modules must be green;
`tests.test_render_preview` must be **29 tests, 0 failures**.

**The P.S. and opt-out chain is already on master and must keep working.** The
projection you repoint has to carry BOTH the P.S. (`step["ps"]`, TASK-560/907)
and the opt-out line (`src/optout.OPT_OUT_LINE`, TASK-904) into the payload. If
repointing the words-builder loses either, you have replaced one silent-drop
bug with another. Prove it, pasting output:

    py -3 -c "from scripts.render_preview import _fixture_rec_email, _fixture_config_email, _build_email_plan; from src import optout; r=_fixture_rec_email(); p=_build_email_plan(_fixture_config_email(),[r]); b=[v['value'] for v in p['leads'][0]['variables'] if v['name'].startswith('body_')]; print('bodies', len(b)); print('optout', [optout.OPT_OUT_LINE in x for x in b]); print('ps_em1', 'P.S.' in b[0])"

**Every `optout` entry must be `True` and `ps_em1` must be `True`.**

## Files
`src/bisonfactory.py` and `src/sequenceplan.py` only, plus your own tests.
**Do NOT touch** `src/generate.py`, `src/claims.py`, `src/copystages.py`.

## RULES THAT OUTRANK FINISHING

- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** Fix what a gate CONSULTS, never
  what it PERMITS.
- **EVERY new check needs a NEGATIVE control and a NEAR-MISS control.** Two
  defects this week shipped with only positive controls.
- **MUTATION CHECK IS MANDATORY.** Break your fix, prove the intended test goes
  red for the intended reason, confirm no other guard fired first, restore and
  verify **byte-identical by sha256**. These files are **CRLF**: a
  `\n`-anchored regex matches zero times and your mutation silently no-ops.
- **Derive a suite verdict from a `Ran N tests` line in the output, NEVER from
  `$?`.** A killed run reported `exit=127` after writing 922 KB of real output.
  No `Ran` line = **absent** measurement, not a failure. Sweep `%TEMP%` for
  `rga-*` first: ~95k leftovers broke every run for an hour.
- **PROVIDER WRITES = 0.** `sending.live` false, freeze active, nothing sent.
- Production `work/` is READ-ONLY; verify `queue.jsonl` and `campaigns.jsonl`
  unchanged **by sha256 from a fresh process**, never by mtime.
- Write suite logs **outside** the repository — one inside the tree became part
  of `test_fixture_hygiene`'s corpus and nearly committed real prospect domains.
- Baseline `docs/state/SUITE-BASELINE-2026-09-26.txt`, compared **AS SETS**.
  Known stale on master (TASK-549).
- Commit and push to your own branch and **verify the remote with
  `git rev-parse` AFTER your last commit** — a stale verification is how a
  branch gets reported pushed while it is not. Do NOT merge. Do NOT post to
  Slack. Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your head SHA.
