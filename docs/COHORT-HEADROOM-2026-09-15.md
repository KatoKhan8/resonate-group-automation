# The deployable inventory is 97, and the number that shrank it was not ICP

Measured 2026-09-15 against the live queue (`work/queue.jsonl`, 550 records),
by `scripts/build_control_cohort.py --limit 0`, which is a dry run and wrote
nothing. Every rejection below is a real read against the client's own
EmailBison estate, cached per domain.

    contacts with a LinkedIn profile, on a live record      277
    minus prior EmailBison outreach                         -29     248
    minus ACCOUNT COLLISION                                -151      97

**97 contacts are deployable right now.** That is the number the batch
progression - 3 -> 10 -> 25 -> 50 -> larger - has to fit inside, and it does:
a ~50-lead cohort is reachable without touching a single account the client is
already working.

## The 61% nobody had counted

151 of 248 eligible contacts were rejected at the ACCOUNT level, not the
person level. The account is the unit of outreach - `ACCOUNT-OUTREACH.md` - so
a person at a company already mid-sequence by email is not a fresh prospect
however cold they personally are.

The verdicts, in the order they appear:

    stop   somebody at this account is mid-sequence right now
    stop   N person(s) at this account have already replied or been marked
           interested; the account is in a conversation
    hold   a campaign at this account ended early (stopped) and the status
           does not say whether we stopped it, they unsubscribed, or the
           provider stopped it on a reply

The third is the interesting one. A STOPPED EmailBison campaign is ambiguous
by construction: the provider's status does not distinguish "we paused this"
from "they asked us to go away". `collision.account_policy` reads that
ambiguity as HOLD rather than resolving it, which is the correct reading and
also the expensive one - it is a large share of the 151.

**That is a data question, not an engineering one.** If those stopped
campaigns could be told apart, some of the held accounts would become
deployable. Nothing here should resolve them by guessing; the ambiguity is
real and the gate is right to refuse it.

## Why this was found by shipping rather than by planning

The first canary of three was assembled from the top of the eligible list, the
copy was installed, the campaign's record set was written - and
`ensure_leads` then refused the whole push, because two of the three were at
one account carrying a stopped campaign. The gate did its job at the moment
the gate runs, which is after everything else has already been done.

So the collision check moved into SELECTION. `build_control_cohort.py` now
clears each candidate's account before choosing it and says why each rejected
one was rejected, and an account whose estate cannot be read is a refusal
rather than a skip - an unreadable account has not been cleared.

## What this means for scale

    3      canary, shipped                    fits
    10     fits
    25     fits
    50     fits, with 47 to spare
    >50    needs either new inventory from the 20,944-domain estate or the
           stopped-campaign ambiguity resolved

The 20,944-domain estate is the answer to the last row and is not urgent: 97
deployable contacts is more than the next four batches need.

## The cost of knowing this

151 domain reads against EmailBison, cached per domain, one dry run. Cheap,
and it is the difference between a batch plan that fits and one that refuses
at the gate after the work is done.
