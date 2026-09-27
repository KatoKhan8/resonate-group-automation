# BRIEF — TASK-425: the one-account dry run, and then STOP

**NOT A POOL TASK. CLAUDE ONLY, critical path, item 5 of 5.** It lives here and
not in `docs/qwen-tasks/TODO/` because a header naming an owner is not an access
control — three workers proved that tonight.

**Dispatch only after `TASK-400` and `TASK-427` are merged.** `TASK-427` is a hard
gate, measured by running it: `_check_offers` is step 1 of `generate()` and does
not gate on `live`, so a dry run refuses at `OFFER-PM-001` until it lands.

## THE ACCEPTANCE CRITERIA ARE FROZEN

Operator, Zvonimir, 2026-09-27, recorded in `docs/OPERATING-MODE.md`. **Narrowing
them to make the run pass is not a decision, it is the failure this task exists to
prevent.** If one of them genuinely cannot be met, STOP and say so with the
evidence — a partial artifact honestly labelled is worth far more than a complete
one that quietly redefined a criterion.

**1. THE CAUSAL MATRIX.** Same account, everything else constant.

    A  original
    B  one fact or signal changed      -> angle AND copy must change
    C  persona economic buyer -> operations
                                      -> Offer A -> B AND capabilities must change
    D  key evidence removed           -> the claim disappears, or the lead HOLDs

Each run states its **EXPECTED** change and its **OBSERVED** diff. **An unexpected
change, or NO change, is a BLOCK.** The point is causation, not output: a matrix
where everything changes a little proves nothing, and neither does one where the
diff is asserted rather than shown.

**2. THE SIGNATURE CHAIN**, end to end: mailbox owner → `sender_signature` →
the rendered final message in the provider projection. **An empty signature is a
BLOCK.** Launch blocker 3 says no mailbox has a stored signature and 155 email
steps render empty, so expect this to fail and report it as a BLOCK rather than
working around it.

**3. OFFER SEQUENCING AS STEP OBJECTIVES, enforced by `sequencegate`, WITH A
NEGATIVE TEST.**

    A: margin visibility -> quote vs burn -> resource decisions that move margin
       -> Report Intelligence as mechanism ONLY if it strengthens the angle
       -> reframe and close
    B: project visibility -> time -> resourcing
       -> AI Time Tracking as mechanism ONLY if it strengthens the angle
       -> one operational view

The MECHANISM for this now exists: a zero-write dry run executes `sequencegate`
(merged tonight, `tests/test_a_dry_run_runs_the_sequence_gate.py`). **What is
missing is CONTENT** — those ladders as cadence steps and copy. That is your work.
The negative test is not optional: a sequence that violates the ladder must be
REFUSED, and you must show it.

**4. AN AUDIT ARTIFACT PER MESSAGE.** Primary problem · selected offer and why ·
core capabilities · AI capability used yes/no, which, and why relevant · source and
provenance · the exact claim licensed and where it appeared in copy. Plus: facts
with sources, strategy, full email and LinkedIn copy, copylint, sequencegate, the
SequencePlan, BOTH the EmailBison and HeyReach projections, suppression, spend, and
**provider writes = 0**.

## FIVE TRAPS FOUND TONIGHT THAT WILL BITE THIS TASK

1. **`report["sequencegate"]` is ABSENT for a zero-lead campaign, in both modes.**
   So `report.get("sequencegate", {}).get("passed")` is `None` — and **`None` is
   not `True`**. Your audit artifact reads that key. If you write it so that
   absence renders as a pass, criterion 3 becomes decorative and the artifact
   lies. Assert the key is PRESENT before reading it.
2. **`CLIENT_SUPPLIED` facts license no prospect-facing claim** (operator decision
   B, merged). The six client-CSV keys — headline, industry, headcount,
   employee_range, headcount_growth_12m, products — inform strategy and offer
   selection and may NOT support a claim in copy. So for criterion 4, "the exact
   claim licensed" must trace to admitted research, never to the CSV. Expect the
   copy path to refuse drafts that lean on those, and treat that as correct.
3. **The copy path refuses strictly more than it used to.** `TASK-330` binds a
   claim to the pack SENTENCE (two shared content words), `TASK-378` widened
   `SPECIFIC_RES` to single digits and made three rules see the full rendered
   surface. `untraceable_company_claim` fires on 44.7% of stored leads. A refused
   draft is the system working — regenerate, never widen a rule.
4. **A stored cadence spec missing `template` CRASHES** with `KeyError: 'template'`
   at `src/cadence.py:959` instead of refusing. If your campaign hits it, that is
   `TASK-449`-class pre-existing breakage above your seam, not your bug — report
   it.
5. **`claim_task.py --status` misattributes results to branches, and local worker
   branch heads get reset to master.** Only `refs/remotes/origin/*` is durable.
   Irrelevant to the run itself, relevant if you go looking for prior work.

## THE ACCOUNT

One safe Productive account, a **fixture built from real structure**, two to three
decision makers. **NO PII IS COMMITTED** — do not copy a real person's name, email
or phone into a committed file. Match the SHAPE of a real record, not its contents.
The company may be a real public domain; the people may not be real people.
`tests/test_fixture_hygiene.py` and `tests/test_campaign_audit.py` enforce this and
have caught a leak this week.

## BOUNDARIES — THE ONES THAT END THE TASK IF CROSSED

- **PROVIDER WRITES = 0.** Prove it, do not assert it: install a transport via
  `providers.set_transport` that raises on any call, over the REAL provider module,
  and fire the trap once on purpose so the claim cannot rest on an inert trap. See
  `tests/test_a_dry_run_runs_the_sequence_gate.py` for the pattern.
- **No send, activate, resume, enrol, attach or pause.** The freeze is in force.
  **Do not touch campaigns 487, 489 or 493.** `sending.live` is off for productive
  and stays off — a killswitch refusal on the EmailBison path is EXPECTED.
- **Do not loosen a gate or a test, or approve an offer or any copy.** Approval is
  the operator's.
- **WHEN THE RUN IS DONE, STOP.** Do not start a second account, do not start ten,
  do not "scale up to check it generalises". The operator's instruction is explicit
  and the artifact goes to them for review first.

## WHAT TO REPORT

The complete artifact, plus: which criteria PASSED, which are BLOCKED and why, and
for the causal matrix, each run's expected-versus-observed. Name the branch and
head SHA. Then STOP — the orchestrator posts it to `#resonate-os`.

**If a criterion is BLOCKED, say so plainly and keep going with the others.** A
run reporting three passes and one honest BLOCK is the successful outcome of this
task. A run reporting four passes because one criterion was reinterpreted is the
failure it was designed to catch.
