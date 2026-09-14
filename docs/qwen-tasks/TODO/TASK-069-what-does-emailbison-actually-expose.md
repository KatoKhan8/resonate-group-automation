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
