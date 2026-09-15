PRIORITY: P0
DEPENDS:

# TASK-160 - 250 of 550 records have no ICP verdict at all

`scripts/funnel.py` measures it: `qualification.verdict.icp_status` is absent
on 250 records. Not rejected, not review - absent. They have never been
qualified, and that is the estate's real bottleneck, not intake.

## FIND THE CAUSE, DO NOT GUESS IT

Exactly one of these, with evidence:

    scheduler              nothing ever selected them
    missing research       `research.why()` blocks qualification
    provider dependency    a paid call they never got
    qualification gate     `qualify` refuses them for a stated reason
    state-transition bug   they moved past the stage without being scored
    worker capacity        the batch simply never ran that far
    deliberate backpressure

Read `src/qualify.py` and `src/run.py` for the selection predicate, then check
the 250 against it: do they MATCH the predicate and get skipped, or fail to
match at all? Those are different defects.

Group the 250 by `state`, `lane` and whether they have `company_facts` and
`research`. The shape of that table usually names the cause on its own.

## DELIVERABLE

`docs/ICP-BOTTLENECK-2026-09-15.md`: the cause with the evidence, the count
per contributing reason, and the smallest change that would move them. If it
is a defect, name the file and function.

## RULES

Read-only on `work/`. No provider writes. No model calls. Do not run `qualify`
against the real queue - that is Claude's. Quote the snapshot stamp.
