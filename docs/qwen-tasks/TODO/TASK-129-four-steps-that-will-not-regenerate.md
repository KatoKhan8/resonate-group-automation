PRIORITY: P1
DEPENDS: 

# TASK-129 - four steps the regeneration will not replace, cause unknown

## WHAT IS ESTABLISHED, AND WHAT IS NOT

The economic_buyer cohort is 51 verified-sendable contacts; 47 pass
channel-correct lint. The 4 that fail all fail on `em_dash`, in these steps:

    state=held      li1  approved=True   ladder_fingerprint=False  len=113
    state=drafted   li2  approved=False  ladder_fingerprint=False  len=132
    state=drafted   li1  approved=True   ladder_fingerprint=False  len=117
    state=approved  li1  approved=True   ladder_fingerprint=False  len=130

**TASK-128 fixed the REPORTING and did not fix these.** Before it, the estate
dry run reported 0 stale steps for them; after it, the whole-estate run
reports 187 stale steps and 87 approvals. But running the flag live per
record still prints `nothing to generate`, and the four steps are byte-for-byte
unchanged - no fingerprint, same em dash.

## TWO HYPOTHESES ALREADY ELIMINATED - DO NOT RE-TEST THEM

1. **Approval.** Claude assumed this first because 3 of 4 are approved.
   TASK-128 proved the cause was gate ORDERING instead. Approval may still be
   involved but it is not the whole answer and assuming it wasted a cycle.
2. **Gate ordering.** Fixed in TASK-128 and verified: the check now runs
   before lint/claims/quality. The reporting moved; these four did not.

## THE OBSERVATION THAT SHOULD DRIVE THIS

    CLI:  py -3 -m src.generate --regen-stale-ladder --client productive
          -> steps to re-plan: 187

    direct: generate.plan(rec, client='productive', regen_stale_ladder=True)
          -> ZERO ops carrying ladder_stale, across every record

**The CLI and a direct `plan()` call disagree.** `run()` passes something
`plan()` does not get by default - a campaign, a config, a sequence - and that
difference is very likely where these four are decided. This is the same shape
as TASK-083's approval count, which read 0 because it reconstructed a key the
wrong way.

Start there: diff what `run()` passes into `plan()` against what a bare call
passes, and find which argument changes the verdict.

## WHAT NOT TO DO

- **Do not revoke an approval**, not even to test. If approval turns out to be
  part of the cause, that is a FINDING to report, not a thing to work around.
- **Do not weaken or special-case the `em_dash` rule.** It is correct and
  provably satisfiable: 497 regenerated steps, zero violations, and both
  prompts already forbid the character.
- **Do not hand-edit `work/queue.jsonl`.** It is a production ledger and
  `src/store.py` is the only sanctioned way in. Editing the four steps by hand
  would "fix" the cohort while leaving the mechanism broken, which is worse
  than four blocked leads.
- Do not guess. Two hypotheses have already been wrong here; find the line.

## DELIVERABLE

The exact reason these four do not regenerate, named at a line of code, with
the argument or branch that decides it. Then say whether the fix is safe - if
it turns out the system is deliberately protecting approved copy, the right
outcome may be that these four stay blocked and the cohort is 47.
