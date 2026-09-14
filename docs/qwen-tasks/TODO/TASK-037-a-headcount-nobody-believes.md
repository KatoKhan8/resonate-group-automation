# TASK-037 - Headcount data quality, and what contradicts what

Operator backlog: QWEN-18.

## GOAL

A measured account of how trustworthy the headcount figures are, and a
reconciliation rule for the cases where two sources disagree.

## WHY IT MATTERS

Headcount decides ICP. `config/clients/productive.yaml` sets `min: 20` with a
`tolerance: 0.30`, so the effective floor is 14, and the config already
records one contradiction rule: a stored headcount under the floor at a
company reporting $3M+ revenue is "a broken estimate, not a four-person
agency" - one record reports FOUR PEOPLE against $172.7M.

That rule handles revenue. Nothing handles the others.

## CURRENT FACTS, measured 2026-09-14 across 300 Productive records

    employees  pass                 88
    employees  pass_with_tolerance  18
    employees  fail                 89
    employees  unknown             105

So 105 records - a third of the estate - have no usable headcount at all, and
89 are failing on a number that may or may not deserve belief.

`company_facts.headcount` carries `value`, `range`, `source`, `confidence`,
`contradictions` and `observations`, so the structure for this already exists.
Establish whether it is POPULATED and whether anything reads it.

## SCOPE

1. Distribution first: by source, by confidence, and how often `range` and
   `value` disagree. Numbers before rules.
2. How often do two sources contradict each other, and by how much? A 20-vs-25
   disagreement is noise; 4-vs-400 is a broken record.
3. Propose a reconciliation rule ONLY where the data supports one. Where it
   does not, `unknown` is the correct answer and must stay - the config is
   explicit that UNKNOWN IS NOT FAIL, and this task must not quietly convert
   unknowns into numbers to raise the qualified count.
4. How many of the 105 unknowns could be resolved from evidence already
   stored, with no new provider call? That number is the deliverable.

## PRODUCTION BOUNDARY

ZERO network. ZERO credentials - `config/.env` does not exist in this
worktree and a task that tries to obtain one has misunderstood its job. No
provider call. No write to `work/**`. Nothing is staged, activated or sent.

## HANDOFF FORMAT

Return ONLY this, concisely:

    STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS /
    BUGS FOUND / BUGS FIXED / RISKS / OPEN QUESTIONS /
    RECOMMENDED CLAUDE ACTION

Plus, required of every task since 2026-09-14: the output of
`grep -rn "<each new name you added>" src/` proving it is CONSUMED, and
confirmation that deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- a contradiction is detected and recorded rather than silently resolved;
- an unknown stays unknown when nothing supports a value;
- the tolerance still applies exactly as configured;
- a reconciliation that would raise a record above the floor is tested with
  the record that motivated it.

## DONE CONDITION

A report with the distributions, the contradiction counts, and a rule proposal
per case - plus the count of unknowns resolvable from stored evidence.
