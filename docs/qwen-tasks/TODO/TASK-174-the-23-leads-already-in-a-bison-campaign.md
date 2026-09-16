PRIORITY: P0
DEPENDS:

# TASK-174 - campaign 481 already holds 23 people, and we did not decide that today

## WHERE THIS SITS

EmailBison provider truth, measured:

    481   paused, 23 leads, 5 steps, 0 sent     ours
    451   completed, 1 sent, 0 bounced          ours

TASK-167 resolved the CONTROL sequence against the real queue and produced a
payload for 17 contacts, all of which render and pass lint and claims.

Seventeen and twenty-three are different numbers, and nobody has said how they
relate. Campaign 481 is paused with five steps and a population that predates
the CONTROL sequence. So before anything is written to EmailBison, there is a
question with three possible answers and no default:

    reuse 481   -> we are writing a new sequence over a campaign holding 23
                   people who were added under a different plan
    new campaign -> 481 stays as it is, and someone must eventually say what
                   happens to the 23
    neither      -> the 23 are the cohort, and the 17 are a subset or a
                   contradiction of them

## THE QUESTION

Read-only against the provider. Answer all four.

1. **Who are the 23?** Hashed. When was each added, under what sequence, and
   what is each lead's current step and status in the campaign. A lead paused
   at step 3 is not the same as one that never started.
2. **Do the 23 and the 17 overlap?** Match against the queue by whatever
   identifier is stable - hashed email, record id, domain. Report the three
   counts: in both, only in 481, only in the payload.
3. **Do the 23 pass the gates we apply today?** Run each through prior-contact,
   collision, fatigue, caps, approval and the historical-contact check. A lead
   added weeks ago under an older gate set is not grandfathered - report per
   lead which gate would refuse it now.
4. **What are 481's five steps?** Read them. Compare to the CONTROL sequence
   `persona_pain -> comparable_proof -> breakup`. Are they the same copy, older
   copy, or copy nobody has audited? Quote the step count, the delays, and the
   `thread_reply` flag per step.

Then state, with the evidence behind it, which of the three answers above the
data supports. You are not deciding it - Claude and the operator are - but an
answer with no recommendation is half a task.

## THE TRAP

`bison.set_sequence` is in `SUPPORTED` and `bison.add_lead` is NOT. So writing
a sequence onto 481 is authorized and adding a lead to it is not. That asymmetry
makes one specific mistake easy and expensive: writing the CONTROL sequence over
a campaign that already holds 23 people is a change to what 23 real people would
receive, performed by a route whose permission comment justifies itself on the
grounds that "a sequence written onto a campaign holding nobody reaches nobody".

481 holds somebody. Say so loudly in the deliverable, because it is the single
fact that decides whether the authorized route is safe here.

## WHAT YOU MAY NOT DO

- **No provider writes.** Do not set a sequence, add a lead, resume, activate,
  or stop a lead. Reads only.
- Do not resolve the 23 by removing them.
- Never commit an email address, a name, a domain or reply text. Hash every
  identifier and say what you hashed.
- Read the provider, not `PROVIDER-CAMPAIGNS.json`, for anything about 481's
  current state - and say which of your numbers came from which.

## FILES ALLOWED

    docs/BISON-481-POPULATION-2026-09-16.md   (new, PII hashed)
    scripts/task174_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The 23 characterised with dates, steps and statuses; the three overlap counts
against the 17; the per-lead verdict from today's gates; 481's five steps
compared to CONTROL; and a recommendation among reuse, new campaign, or
neither, with the evidence that supports it.
