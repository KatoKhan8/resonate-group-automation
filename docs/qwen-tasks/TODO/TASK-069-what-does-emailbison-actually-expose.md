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


---

## THE FOUR QUESTIONS, AND THE ONLY FOUR ANSWERS ALLOWED

Supersedes the addendum above where they differ. Every one of A, B, C and D
gets EXACTLY ONE of these verdicts, and a verdict with no real provider
response behind it is not a verdict:

    1  DIRECTLY SUPPORTED BY PROVIDER
    2  RECONSTRUCTABLE FROM PROVIDER DATA
    3  NOT AVAILABLE
    4  UNKNOWN / NOT YET PROVEN

**Do not assume any of them.** Inspect real responses from the real estate,
and say how many rows and which campaigns you checked. `UNKNOWN / NOT YET
PROVEN` is a legitimate and useful answer; a confident guess is not.

    A  Do historical per-lead / per-step SENDS with timestamps exist?
       Not for a scheduled campaign - for one that finished months ago.

    B  Does a REPLY carry a direct message or step relationship?
       A field that names the sequence step, or the message it answers.

    C  Can exact sequence position be RECONSTRUCTED when B is absent?

    D  Does EmailBison expose a persistent VARIANT identifier that survives
       both the send and the readback?

## THREE KINDS OF STATEMENT, AND THEY MAY NEVER BE MIXED

For anything not answered by verdict 1, label every claim as exactly one of:

    PROVIDER FACT              the API returned this field with this value
    RESONATE RECONSTRUCTION    we derived it from provider data, and here is
                               the derivation and what it assumes
    ATTRIBUTION HYPOTHESIS     we believe this reply relates to that touch,
                               and it is a belief

**"The last email before the reply" is an ATTRIBUTION HYPOTHESIS and never
proof that the email caused the reply.** A prospect may answer email one
three weeks later, after emails two and three have gone out. A reply may be
triggered by a LinkedIn touch the email estate cannot see. Crediting the most
recent touch is the single easiest way to manufacture a finding that is not
there, and this repository has already paid for one version of that mistake.

Where you use last-touch attribution because nothing better exists, SAY SO in
the same sentence as the number, every time.

## IF D IS NOT AVAILABLE - DESIGN THE LEDGER, DO NOT BUILD IT

If EmailBison cannot carry a variant identifier through a send and back, then
five variants per position is unmeasurable at the provider and the experiment
has to be owned by us. DESIGN a Resonate-owned experiment ledger:

    lead
    campaign
    channel
    sequence position
    variant_id
    exact rendered copy
    sent_at
    reply_at
    classified outcome
    attribution confidence

Write the design into the result: what it stores, where it lives, what writes
it, what reads it, and how it survives a provider that forgets. Say what it
CANNOT know - if the provider cannot tell us which step a reply answers, the
ledger cannot either, and `attribution confidence` is where that honesty
lives.

**Design only.** Do not implement it in this task, and do not add a new
persistence file. `CLAUDE.md`: new state has to earn its place, and Claude
decides whether a second ledger is the right answer or whether the existing
event log already holds this.

## OUTPUT

`docs/BISON-PROVIDER-TRUTH-<date>.md`, with A/B/C/D each carrying its verdict,
its evidence, and its row counts. The ledger design as an appendix if D is
not verdict 1.

Still no performance findings. That is TASK-070, and what you conclude here
decides what TASK-070 is allowed to claim.
