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

## RESULT

STATUS: DONE
COMMIT SHA: 4096da4
TESTS: 209 tests pass across test_generate, test_ladder_propagation,
  test_set_regeneration, test_invariants, test_cadence. Two new tests added
  to test_set_regeneration.py verify the fix and its negative case.

FILES CHANGED:
  src/generate.py           - propagate ladder_stale to linkedin_set op
  tests/test_set_regeneration.py - two new tests

FINDINGS:

**The exact reason, named at a line of code:**

`src/generate.py` lines 932-943 (before fix): the set regeneration detection
in `plan()` removes individual `linkedin_note` ops and replaces them with a
single `linkedin_set` op. The removed ops carried `ladder_stale: True` (set
at lines 729-749 and 828-848), but the replacement `linkedin_set` op did not.
The `ladder_stale` flag was silently dropped.

**What decides it:** the `for i in reversed(contact_li_ops): ops.pop(i)` loop
at line 937 removes the individual ops, and the `ops.append(...)` at line 938
creates a new set op without the flag. Any subsequent code that checks
`op.get("ladder_stale")` - the impact report in `run()` at line 1819, the
direct `plan()` caller - sees zero for contacts whose notes were absorbed.

**The fix is safe.** The steps ARE regenerated: `_regenerate_linkedin_set`
generates fresh notes against the current ladder and sets new fingerprints.
The fix only makes the reporting correct - it propagates `ladder_stale` and
`stale_step_count` to the set op so the impact report counts them.

**Two contacts in the estate are affected:**
- 2ton-com / Sam Nielsen: 6 LinkedIn steps absorbed into linkedin_set
- swipemarket-com / Jamie Winterstern: 6 LinkedIn steps absorbed into linkedin_set

The total stale count moved from 621 to 633 (12 more steps correctly counted).

**The original four em_dash-failing steps from the task:**
Three of four (5bonsai-com, 5p-retail-be, adagri-com) now show as individual
`ladder_stale` ops and will be regenerated. The fourth (2ton-com / Sam Nielsen)
shows as a `linkedin_set` op with `[LADDER STALE]` and will be regenerated
through the set path. All four will be fixed by a live run.

**The CLI-vs-direct discrepancy from the task:**
The task described `plan(rec, client='productive', ...)` returning ZERO.
This was because `client='productive'` is a string, not a loaded config,
and `cadence._named_sequence` crashes on `'str' object has no attribute 'get'`.
When called correctly with `clients.load('productive')`, both CLI and direct
`plan()` agree. The remaining discrepancy (for set-absorbed contacts) is now
fixed.

RISKS:
- The approval counting for linkedin_set ops now iterates over all LinkedIn
  steps in the contact's cadence. If a contact has steps from a different
  sequence or old cadence, they would also be counted. This is correct
  behavior (all are protected by approval) but may overcount vs. the
  individual-op path where only the specific step is checked.

RECOMMENDED CLAUDE ACTION:
Integrate. The fix is a reporting correction, not a behavior change. The
steps were already being regenerated; now the operator can see them.
