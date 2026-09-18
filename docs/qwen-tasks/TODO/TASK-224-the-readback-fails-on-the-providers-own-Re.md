# TASK-224 - the readback FAILS on the provider's own "Re:"

## The observation, measured 2026-09-18

    py -3 scripts/bison_readback.py productive-email-control-v3 --expect

    step_2_subject   {SUBJECT_1}   Re: {SUBJECT_1}   ** FAIL **
    step_3_subject   {SUBJECT_1}   Re: {SUBJECT_1}   ** FAIL **
    VERDICT: FAIL - the provider campaign does not match canonical state

Campaign 487 is CORRECT. `src/bisonfactory.py:1017` says EmailBison prepends
"Re: " itself on a `thread_reply` step, and `src/configdiff.py:853` already
normalises exactly that before comparing. `bison_readback.py` does not.

## Why this matters more than a cosmetic diff

`bison_readback` is the COMPARE half of the production write contract
(WRITE -> READ BACK -> COMPARE -> RECONCILE). A compare that cries FAIL on a
difference that is correct by construction has two outcomes and both are bad:
an operator learns to ignore the verdict, or a valid activation is blocked.
A gate nobody believes is not a gate.

## The objective

Make `scripts/bison_readback.py` agree with `src/configdiff.py` about what a
threaded follow-up's subject is, WITHOUT weakening the check.

Falsifiable requirements:

1. `productive-email-control-v3` reads **16 passed, 0 failed, VERDICT: PASS**.
2. A step with `thread_reply: true` whose provider subject is
   `Re: {SUBJECT_1}` PASSES when canonical says `{SUBJECT_1}`.
3. A step with `thread_reply: true` whose provider subject is
   `Re: {SUBJECT_2}` - a DIFFERENT subject wearing a Re: - still **FAILS**.
   This is the case the normalisation must not swallow, and it is the exact
   defect `scripts/activate_control_campaign_v3.py:15` describes.
4. A step with `thread_reply: FALSE` carrying `Re: {SUBJECT_1}` still FAILS -
   stripping is licensed by the threading flag, not by the text.
5. Do not copy configdiff's logic. IMPORT it, or extract the one helper both
   call. Two implementations of the same normalisation is how they drift.

## Tests required

Unit tests over the comparison function with synthetic step pairs covering
all four cases above, including the two that MUST still fail. Break-proof it:
delete the `thread_reply` condition and confirm case 4 starts passing, then
restore.

## Boundaries

READ-ONLY against the provider. No provider write. No campaign mutation. Do
not touch `src/configdiff.py`'s behaviour - if the shared helper lands there,
its existing callers must be proven unchanged.
