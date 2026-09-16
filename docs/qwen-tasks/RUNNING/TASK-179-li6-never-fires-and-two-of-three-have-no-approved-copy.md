PRIORITY: P0
DEPENDS:

# TASK-179 - a step that never fires, and a canary of one

## WHERE THIS SITS

TASK-176 resolved the LinkedIn canary payload and found that LinkedIn's blocker
is not the one email had. Email's blocker was a variable that would not
resolve. LinkedIn's blocker is APPROVAL:

    contact 1   all 8 roles approved on the operator-control arm
    contact 2   7 of 8 fallbacks; its generated li1 FAILS lint (em dash) and
                FAILS claims (a flat operational assertion about the prospect)
    contact 3   8 of 8 fallbacks; zero approved copy

15 of 24 variable slots are CONTROL fallbacks. So rung 3 of the ladder is, in
practice, a canary of ONE - and the two gates did their job on contact 2 by
refusing copy that asserts something about a person we cannot evidence.

It also found a defect that has nothing to do with the canary:

    the cadence names six steps, li1 through li6
    the HeyReach graph has positions for five, li1 through li5
    li6 exists on paper and NEVER FIRES at the provider

## THE QUESTION

Two separate things. Do both, and keep them separate in the deliverable.

### li6

1. Read `COPY_MAPPING` and the cadence definition. Confirm or refute that li6
   has no graph position, from the code and from campaign 599020's actual
   nodes. TASK-176 says the corrected campaign carries 17 nodes with merge
   variables; count the copy-bearing positions yourself.
2. Decide which of two things is true and say which: the graph is missing a
   position it should have, or the cadence names a step that should not exist.
   Do not guess - the cadence's own definition and the campaign's audited
   readback hash are both evidence.
3. Fix the one that is wrong, with a test that fails if the cadence and the
   graph ever disagree on step count again. That test is the real deliverable
   here: a step that silently never fires is a whole message nobody sends and
   no gate complains about.

### The approval gap

4. **What is the approval path?** `approval.by` on a cadence step is what
   contact 1 has and the other two lack. Read the module. Who can set it, what
   values does it take, and what does `operator-control-arm` mean as distinct
   from `claude`? Report the mechanism; do not set one.
5. **What would a CONTROL-fallback-only canary look like?** TASK-176's
   recommendation was to replace the generated copy for contacts 2 and 3 with
   CONTROL fallbacks. Establish whether that is a data change in the queue, an
   approval change, or both - and whether CONTROL fallback text, once in the
   per-lead fields, passes lint and claims for those two contacts. Render it
   and run the gates. If it passes, say so; if it fails, say on which rule.

## THE TRAP

`approval.by` is the field that decides whether copy reaches a person, and this
task reads it. **Do not set it, do not default it, do not add a fallback that
makes an unapproved step behave like an approved one.** The repository's own
record is that copy passing every automated gate still failed a human read, and
approval is the human. Bulk-approving to raise a count is named in the
checkpoint as the most damaging action available here.

Second trap: contact 2's generated li1 contains a company name in the copy
itself. If you quote failing copy in the deliverable, hash the company and the
name first.

## WHAT YOU MAY NOT DO

- **No provider writes.** Do not add a lead, set a sequence, edit a node, start
  or activate anything. Campaign 599020's readback hash must still verify after
  this task.
- Do not set, clear or default `approval.by` for any step or contact.
- Do not weaken lint or the claims gate, and do not exempt a contact from
  either.
- Never commit a prospect name, a company name, a domain or a profile URL.

## FILES ALLOWED

    src/cadence*.py or wherever COPY_MAPPING and the step list live - read
      first, and say why the file you changed is the right one
    tests/test_cadence_graph_agreement.py   (new)
    docs/LI6-AND-APPROVAL-2026-09-16.md   (new)
    scripts/task179_*.py

## FILES FORBIDDEN

    src/providerwrites.py   src/approval.py (read only)   work/   config/

## DELIVERABLE

The li6 verdict with the evidence, the fix, and the test that pins cadence and
graph together; then the approval mechanism explained, and the rendered
CONTROL-fallback copy for contacts 2 and 3 with its lint and claims verdicts.
