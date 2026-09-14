# TASK-069 - WORKER: establish what EmailBison actually exposes, before analysing it

## WHY THIS IS A SEPARATE TASK

The HeyReach analysis (TASK-058) produced real numbers and then had to be
partly reinterpreted, because the definition of "a reply" was never pinned
down first - it reported ~20% of conversations replying where a direct probe
found ~6%. That ambiguity cost more than establishing the shape would have.

So for EmailBison: **establish provider truth first, analyse second.** This
task produces NO findings about performance. It produces a map.

## DO NOT ASSUME A FIELD EXISTS

`src/providers/bison.py` is the existing implementation and its docstrings
already record several probes and several wrong guesses - read them. Note in
particular the long comment about `workspace_id` being accepted and silently
discarded, which is the shape of trap this task exists to avoid.

## WHAT TO ESTABLISH, WITH A REAL RESPONSE BEHIND EACH ANSWER

For each, say: does it exist, what is the exact field name, what shape is the
value, is it populated in practice, and on how many rows you checked.

    CAMPAIGN      id, name, status, created_at, run dates
                  emails_sent, opened, replied, bounced, unsubscribed,
                  interested, total_leads, total_leads_contacted
                  open_tracking  <- CRITICAL. Campaign 451 has it FALSE, so
                                    its zero opens are an absent measurement
                                    rather than an absent open. Establish how
                                    many campaigns track opens at all; any
                                    open-rate analysis that ignores this is
                                    fiction.

    SEQUENCE      steps, order, wait_in_days, active, subject, body,
                  variables/merge fields

    LEAD          id, email, custom variables, status, per-lead stats

    SEND HISTORY  is there a per-lead per-step record of what was actually
                  SENT, with a timestamp? `scheduled_emails` carries
                  `sent_at`, `status`, `opens`, `replies` - establish whether
                  it is available for historical campaigns or only scheduled
                  ones. **This is the single most important question in the
                  task**: step-level learning is impossible without it.

    REPLIES       `fetch_replies`, `classify_reply_row` and
                  `events_contract` already exist. What does a reply row
                  carry? Can it be joined to a CAMPAIGN, a LEAD and a STEP?
                  If it cannot be joined to a step, say so plainly - that is
                  a finding that shapes everything downstream.

## THE JOIN IS THE DELIVERABLE

The question the operator wants answerable is:

    campaign -> lead -> exact email step -> exact copy -> send timestamp
             -> reply -> outcome

Establish whether that join is possible with what the provider exposes, and
where it breaks. If the step cannot be determined for a reply, say what CAN
be determined - campaign and lead may still be enough for cadence-shape
learning even when per-step attribution is not.

**Do not fabricate attribution to complete the chain.** Preserve the
uncertainty and name it.

## OUTPUT

`docs/BISON-PROVIDER-TRUTH-<date>.md`: the map, with field names, shapes,
population rates and the count of rows behind each claim. No performance
findings - those are TASK-070's, and they will be built on this.

## WHAT YOU MAY NOT DO

- **READS ONLY.** No campaign creation, no sequence write, no lead write, no
  resume, no pause. You hold real keys.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not commit prospect PII - no real emails, names or company domains.
- Do not print a credential value.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.


---

## ADDENDUM - THE STEP-LEVEL JOIN IS THE WHOLE POINT

Added after dispatch. If you have already started, read this before writing
the result block.

The operator's requirement is step-level learning:

    campaign -> lead -> email step -> delay -> subject/body/variant
             -> send timestamp -> reply -> classified outcome

So the questions that matter most in this map are the ones that decide
whether that chain can be built at all:

1. **Is there a per-lead, per-step record of what was SENT, with a
   timestamp, for HISTORICAL campaigns?** `scheduled_emails` carries
   `sent_at`, `status`, `opens` and `replies`, and it is known to work for a
   scheduled campaign. Establish whether it returns rows for a campaign that
   finished months ago, or only for pending sends. If the latter, the send
   history for historical campaigns may not exist and that changes what
   TASK-070 can ask.

2. **Can a REPLY be joined to a STEP?** Not to a campaign - to a step. If a
   reply row carries a `sequence_step_id`, say so and give the field name.
   If it does not, say that plainly and say what the nearest available join
   is. "Reply attributable to campaign and lead but not step" is a complete
   and useful answer.

3. **Can a lead's position in the sequence at reply time be RECONSTRUCTED**
   from sends plus timestamps, if the direct join is absent? That is the
   fallback and it is worth establishing, but say clearly that it is a
   reconstruction rather than a provider fact.

4. **Does a step carry a VARIANT identifier?** Five variants per position is
   the target design; establish whether the provider can distinguish them at
   all, because an experiment nobody can read back is not an experiment.

Answer each with a real response behind it and a row count. A NO here is
worth more than an optimistic maybe: it tells TASK-070 what it may claim.
