PRIORITY: P0
DEPENDS: 

# TASK-128 - the propagation flag does not reach an approved step

## THE CONCRETE CASE, MEASURED 2026-09-15

The economic_buyer cohort is 51 verified-sendable contacts. 47 pass
channel-correct lint. **The 4 that fail all fail on `em_dash`**, and every one
of those steps looks like this:

    state=held      li1  approved=True   ladder_fingerprint=False
    state=drafted   li2  approved=False  ladder_fingerprint=False
    state=drafted   li1  approved=True   ladder_fingerprint=False
    state=approved  li1  approved=True   ladder_fingerprint=False

Three of four are APPROVED. All four carry NO fingerprint, so they are stale
by definition. And:

    py -3 -m src.generate --regen-stale-ladder --live --client productive --id <each>
      steps to re-plan:              0
      approvals that would be revoked: 0
      GENERATED: 1 record(s)

**The flag built to make a ladder change reach the copy reports nothing to do
on steps that are provably stale.**

## WHY THIS MATTERS MORE THAN FOUR LEADS

Both prompts have forbidden em and en dashes for some time, and **zero of the
497 regenerated steps contain one**. The rule works. These four survive
because approval pinned words written before the rule, and `plan` will not
re-plan an approved step - so the copy is simultaneously APPROVED and FAILING
A CURRENT GATE.

That is the same shape TASK-098, TASK-110 and the approval audit each found by
a different route, and this is its sharpest instance: approval does not just
freeze mediocre copy, it freezes copy the linter would now refuse.

## WHAT TO ESTABLISH

1. **Where does `plan` skip the step?** Trace `regen_stale_ladder=True` for
   one of these records and find the branch that returns before the
   fingerprint comparison. Is approval checked first, or state
   (`held`/`approved`), or both?
2. **Is the skip deliberate?** There is a real argument for it - regenerating
   an approved step silently discards a human decision. If the skip is
   intentional, the flag's impact report is WRONG rather than the flag: it
   says "approvals that would be revoked: 0" while the reason is that it
   refuses to touch them at all. An operator reading 0 concludes there is
   nothing to decide.
3. **What SHOULD the flag do with an approved stale step?** It cannot silently
   revoke. It also cannot silently skip, which is what it does now. The
   honest behaviour is probably to COUNT them, REPORT them, and revoke only
   under an explicit further flag - so the operator sees the real number.
4. **The fourth record is not approved and still did not regenerate.** That is
   a separate path and needs its own answer.

## WHAT NOT TO DO

- **Do not revoke any approval.** Not one, not for a test. Approval semantics
  are on the list nothing may own, and the whole defect here is a mechanism
  being quiet about them.
- Do not weaken the `em_dash` rule. It is correct and the regenerated estate
  proves it is satisfiable - 497 steps, zero violations.
- Do not edit `work/queue.jsonl` directly. It is a production ledger and
  `src/store.py` is the only sanctioned way in.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## DELIVERABLE

The exact line where the skip happens, a verdict on whether it is deliberate,
and a corrected impact report that distinguishes "no stale steps" from "stale
steps I will not touch". Those are different answers to the operator's only
question and they currently print identically.
