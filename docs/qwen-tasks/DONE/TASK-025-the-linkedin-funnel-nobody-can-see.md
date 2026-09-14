# TASK-025 - The LinkedIn funnel, and what is missing to see it

Operator backlog: QWEN-13's analysis half, and items 6 and 7 of the analysis
list - connection request, acceptance, reply.

## GOAL

State exactly which stages of the LinkedIn funnel this system can measure
today, which it cannot, and the cheapest read that would close each gap.

## WHY IT MATTERS - measured 2026-09-14

`/campaign/GetAll` returns `progressStats`, and it is EXECUTION only:
totalUsers, pending, inProgress, finished, failed, excluded, manuallyStopped.
Across 83 campaigns that is 949,536 users.

**Connection acceptance is not in it.** The operator's own hierarchy puts
acceptance below reply and warns against optimising it - but "do not
over-weight it" and "cannot see it at all" are different situations, and
right now it is the second.

Conversations give replies: 697 of 6,000 threads sampled carry an inbound
message, 11.6%.

## WHERE THE DATA IS

Claude holds the provider credentials; this worktree has none, by design and
structurally - `config/.env` does not exist here. So the provider reads are
already done and the results are on disk OUTSIDE any repository:

    C:\Users\Zvonimir\Desktop\resonate-analysis\

    replies_email.jsonl      sanitised inbound email replies
    replies_linkedin.jsonl   sanitised inbound LinkedIn messages
    bison_campaigns.json     22 EmailBison campaigns with outcome counters
    hr_campaigns.json        83 HeyReach campaigns with progressStats

The reply bodies are SANITISED: emails, URLs, phone numbers and every personal
and company name this system knows are replaced with placeholders. They are
still real client correspondence. **Read them, never copy them.** No body, no
fragment of a body, and no name may enter this repository - not into a
fixture, not into a docstring, not into a commit message. Invent every example
you need. `tests/test_fixture_hygiene` is failing today because that rule was
broken before.

Do NOT attempt a provider call. There are no credentials here, and a task that
tries to get some has misunderstood its job.


## SCOPE

1. Enumerate the funnel: targeted -> request sent -> accepted -> messaged ->
   replied -> positive -> meeting. For EACH stage say SUPPORTED (naming the
   route and field), UNSUPPORTED (naming what was looked for and where), or
   UNDETERMINED (naming the single cheapest live read that would settle it
   and what each possible answer would mean).
2. Do the same for action-type performance: does anything let us compare a
   CONNECTION_REQUEST, a MESSAGE, a VIEW_PROFILE, a FOLLOW and an INMAIL for
   effect? Say so honestly if the answer is no.
3. Quantify the cost of each missing read. A per-lead read across 949,536
   users is not a measurement, it is a bill - say how big.
4. Write a test asserting that a step naming an unproven capability is HELD
   by the planner and not silently dropped. Assert on what the planner
   returns. This overlaps TASK-021 by design; coordinate through Claude
   rather than editing `src/linkedinstate.py` here.

## FILES ALLOWED

`scripts/`, `docs/`, `docs/qwen-tasks/`, `tests/`.

## FILES FORBIDDEN

`src/**`, `work/**`.

## TESTS REQUIRED

Behavioural, on invented fixtures. Zero network.


## RESULT

STATUS: done

COMMIT SHA: 7200499

TESTS:
  9 tests in tests/test_task025_funnel_unproven_held.py - all pass.
  Three classes:
    EveryLinkedInStepGetsAVerdict (2 tests) - walks the full li_heavy
      cadence and asserts every LinkedIn step produces an explicit
      verdict; no step is silently dropped.
    UnprovenCapabilitiesAreHeld (4 tests) - asserts that li1's open
      profile alternative and li3's InMail fallback both return
      WAIT/HELD_CAPABILITY_UNPROVEN when their capability is unproven;
      proven capabilities (connect, message) are NOT held; held steps
      name their node.
    CapabilityTableIsTheGatekeeper (3 tests) - asserts the shipped
      CAPABILITIES table has connect/message as True and open_profile/
      inmail as False; unknown capabilities return False.
  Audit script: scripts/linkedin_funnel_audit.py reads the extracted
    provider data and the codebase, classifies each funnel stage, and
    writes scripts/task025_funnel_audit.json.

FILES CHANGED:
  scripts/linkedin_funnel_audit.py     (new) funnel audit script
  scripts/task025_funnel_audit.json    (new) machine-readable output
  tests/test_task025_funnel_unproven_held.py (new) 9 behavioural tests
  docs/qwen-tasks/RUNNING/TASK-025-the-linkedin-funnel-nobody-can-see.md
    -> docs/qwen-tasks/DONE/TASK-025-the-linkedin-funnel-nobody-can-see.md

FINDINGS:

  FUNNEL STAGE VERDICTS:

  1. TARGETED: SUPPORTED
     Route: POST /campaign/GetAll, field: progressStats.totalUsers
     83 campaigns, 949,536 total users. progressStats also carries
     pending, inProgress, finished, failed, manuallyStopped, excluded.
     Consumer: src/providers/heyreach.py READ_ROUTES.

  2. REQUEST SENT: SUPPORTED
     Route: Local event log (events.PUSH_MARKED, channel=linkedin).
     Field: entry.type == 'push_marked' AND action_of(step) == 'connect'.
     Consumer: src/linkedinstate.evidence() reads request_at.
     Provider route POST /campaign/GetLeadsFromCampaign is on
     READ_ROUTES_ALL; lead_state() maps connectionsent to REQUEST_SENT.
     BUT leadobserve.observe() has NO CALLER in src/ - the provider
     read is defined but not invoked. The local event log is the
     operative record.

  3. ACCEPTED: UNDETERMINED
     Route checked: POST /campaign/GetLeadsFromCampaign (on
     READ_ROUTES_ALL); field: leadConnectionStatus == 'ConnectionAccepted'.
     lead_state() maps 'connectionaccepted' to ACCEPTED.
     BUT leadobserve.observe() has NO CALLER in src/.
     CONNECTION_STATUS_AVAILABLE = False for the inbox route
     (/inbox/GetConversationsV2), confirmed over 100 conversations.
     The vendor documents POST /MyNetwork/IsConnection and a
     CONNECTION_REQUEST_ACCEPTED webhook event; neither is on any
     allowlist and neither has ever been called.
     Cheapest read: run `python -m src.leadobserve --campaign <id>`
     for one of the 12 IN_PROGRESS campaigns. If output contains
     state='accepted' rows, the gap is wiring, not capability.

  4. MESSAGED: SUPPORTED
     Route: Local event log (events.PUSH_MARKED, channel=linkedin).
     Field: action_of(step) == 'message'.
     Provider: leadMessageStatus == 'MessageSent'.
     Consumer: src/linkedinstate.evidence(), plan_step() gates on
     MESSAGEABLE states. CAP_MESSAGE is proven (True).

  5. REPLIED: SUPPORTED
     Route: POST /inbox/GetConversationsV2 (READ_ROUTES).
     Field: messages[].sender == 'CORRESPONDENT' (allowlist).
     695 LinkedIn reply records in replies_linkedin.jsonl.
     Consumer: src/linkedinstate.evidence() records replied_at;
     src/eligibility._replied uses the same predicate.

  6. POSITIVE: SUPPORTED
     Route: src/replies.py apply() -> classify() -> classify_rules().
     Field: verdict category == 'positive'.
     30 of 695 LinkedIn replies classified positive.
     Consumer: src/inbound.py calls replies.apply() and
     replies.is_positive(). POSITIVE is in ALERTING.

  7. MEETING: UNSUPPORTED
     Looked for: event type, calendar integration, or classifier
     output distinguishing meeting from positive.
     Looked in: src/events.py (no MEETING type), src/replies.py
     (explicitly declines to split: "a meeting is determined by an
     action, not by words alone"), src/ (no calendar module).
     Cheapest read: scan 30 positive reply bodies for calendar-link
     patterns. But even a positive result needs a confirmation
     mechanism no provider here offers.

  ACTION-TYPE PERFORMANCE: UNSUPPORTED
  Looked for: per-action-type comparison (CONNECTION_REQUEST vs MESSAGE
  vs VIEW_PROFILE vs FOLLOW vs INMAIL for effect).
  Looked in: progressStats (no per-action counters), lead_state()
  (only leadConnectionStatus and leadMessageStatus - two dimensions,
  not five), LINKEDIN_ONLY_NODES (lists types but does not measure
  effect). VIEW_PROFILE, FOLLOW and INMAIL have no lead-level status
  field. A cross-action comparison cannot be answered from any data
  here.

  COST OF MISSING READS:
  Total users: 949,536 across 83 campaigns.
  Acceptance gap: 9,496 API calls at 100/page (free, but leadobserve
    needs wiring into the poller).
  Meeting gap: no API call possible; design decision needed.
  Action-type gap: ~9,579 API calls (free), but the data does not
    answer the question even after reading.

  CALLER VERIFICATION (QWEN.md rule):
  grep -rn "leadobserve.observe" src/ -> 2 hits, both docstrings.
    No actual caller.
  grep -rn "replies.apply" src/ -> 1 hit: src/inbound.py:163.
    Consumed.
  grep -rn "replies.is_positive" src/ -> 1 hit: src/inbound.py:175.
    Consumed.

RISKS:
  - The acceptance verdict (UNDETERMINED) rests on the observation
    that leadobserve.observe() has no caller. If Claude has wired it
    in a branch not yet on qwen-worker-2, the verdict should be
    upgraded to SUPPORTED. The cheapest check is one CLI invocation.
  - The audit script reads source text with regex, not AST. A renamed
    function would not be caught. The test file asserts on behaviour,
    not source text.

RECOMMENDED CLAUDE ACTION:
  1. Run `python -m src.leadobserve --campaign 565765` to settle the
     acceptance question. If it returns state='accepted' rows, wire
     leadobserve.observe() into the poller and the funnel gains its
     third SUPPORTED stage.
  2. The meeting gap is a design decision, not an engineering one.
     CADENCE-EXPERIMENTS.md may absorb it as a reply-classifier
     extension if the 30 positive bodies carry calendar links.
  3. The action-type comparison gap is not closable by provider reads
     alone. It requires a controlled experiment (CADENCE-EXPERIMENTS.md
     territory) or a new data model.
