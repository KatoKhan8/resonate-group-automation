# Batch 1 cannot go tonight, and the condition it fails is number 1

Measured 2026-09-21T15:0xZ. S6 collision run over every domain carrying a
verified contact - 440 domains, read from EmailBison with the workspace
binding asserted, zero errors:

    touched       427
    in_sequence     5     somebody is mid-sequence at that account RIGHT NOW
    clear           8

**The 660 verified contacts yield EIGHT leads that clear collision**, not the
360 the pacing rule allows. The exact condition failed is CONDITION 1 of
`OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1.md`: "collision and suppression
cleared fail-closed". It is not a near miss and it cannot be fixed by sizing
the batch differently.

## The file is not new inventory

`productive_ICP_safe_to_send (1).csv` is dated 2026-09-07 and its name is the
supplier's claim, not ours. The estate has sent 198,000 emails from these
eight humans. **97% of the file's domains have already been contacted.**

S1 caught the 306 domains that were in our own store. Collision catches the
far larger set that were worked THROUGH THE PROVIDER and never entered it -
which is the difference between "not in our queue" and "not contacted", and
only the provider knows the second one.

Five domains have somebody mid-sequence today. Enrolling a second person at
one of those accounts is exactly what the account gate exists to prevent, and
it would have happened tonight on the strength of a filename.

## The ordering lesson, for the register

S2 (account history) sat BEFORE S5 (verification) in the original pipeline for
a reason. It was deferred because collision costs one provider call per domain
while S3 was a cheap bulk filter at 30 domains a call - the right call for
cost, the wrong one for sequencing. The consequence is that 660 addresses were
verified before anybody asked whether they could be written to.

The verification is not wasted: those contacts stay verified and re-enter the
reservoir the moment an account clears. But the cheap gate that disqualifies
97% of a population belongs before the expensive one that qualifies 92% of it.

**Run collision before verification on the next input.** The rule generalises:
order the pipeline by how much each stage REMOVES per unit cost, not by how
cheap the stage is.

## What this does not say

It does not say the 427 touched domains are dead. `touched` records that the
estate has contacted the account, and the account policy decides when it may
be approached again - that is a separate question with its own recency and
fatigue rules, and it is not answered here.

It does not say the file was a bad input. 4,870 domains cleared ICP and MX
from it. It says the file is not NEW, and that "safe to send" in a filename is
not a verdict this system may accept.
