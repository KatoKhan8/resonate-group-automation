# TASK-249 — the agent answers about an account, and never names a person

OPERATOR DECISION, 2026-09-21, Zvonimir, recorded verbatim:

> 1. Account lookup, any channel: "is <domain> in a campaign" returns client
>    approval state, collision state, campaign ids, step, last touch, reply /
>    bounce / unsubscribe flags. Domains only.
> 2. Lead lookup, DM only, never in a channel: "status of <email>" or a
>    LinkedIn URL returns the same fields for that person, without echoing the
>    name or address back in the answer. Refuse in channels with a one-line
>    reason.
> 3. Add: "why is <domain> held", "what did we send to <domain>", "when does
>    <campaign id> send next", "how many replies today", "credits spent
>    today". All read-only, all logged to work/slack-agent.jsonl with who
>    asked.
> 4. Every answer keeps the "Read at <timestamp>" line and, when it counts
>    monitors, states how many it could not see.

## THE LOOP IS BUILT. YOU EXTEND IT.

`scripts/slack_agent_loop.py` and `src/socketmode.py` are on master and the
agent is connected and answering. **Rebase first.** Read the loop's docstring
before you touch it: the property that makes it safe is that there is NO code
path from a Slack message to a write, and every query you add must keep it.

`route()` is a closed keyword table returning `(query, argument)`; `gather()`
runs exactly one read; `plain_answer()` assembles the facts; the model only
rephrases what it is handed. Add to those three. Do not give the model the
choice of what to read, and do not add a query that writes.

## THE PRIVACY RULE IS THE HARD PART, AND IT IS TESTABLE

**Lead lookup is DM-only.** A channel is a room with an audience; a lead's
status is about one identifiable person. In a channel the answer is one line
saying it is DM-only, and it must not leak the answer while refusing - "I
cannot look up jane@example.test here" has already said who was asked about.

**The answer never echoes the identifier.** Asked "status of <email>", the
reply says "that lead is enrolled in campaign 491, step 1, last touched
2026-09-14" with no address and no name. `notify._EMAIL_SHAPE` and
`notify.STATUS_FORBIDDEN_FIELDS` already encode this rule - reuse them rather
than writing a second, weaker one. The loop's `scrub()` is the last line of
defence and must stay.

Required tests: a lead lookup in a channel refuses AND does not echo the
identifier; a lead lookup in a DM answers AND contains no address and no
name; an account answer carries the domain and never a contact; the log row
records who asked and what was asked.

## WHAT EACH QUERY READS

    is <domain> in a campaign   clientapproval.state_of, the local
                                last-touch index, campaign membership from
                                canonical state, then a provider readback for
                                the campaign's own status
    why is <domain> held        the S5 journal's state and reason, S7's hold
                                reason, the ICP verdict, the MX decision.
                                A held lead's reason is usually already
                                written down - read it, do not re-derive it
    what did we send to <domain>  the record's events and the provider's
                                scheduled rows. SENT means a provider-
                                confirmed send, never `scheduled`
    when does <campaign> send next  bison.sending_schedule for today,
                                tomorrow and the day after.
                                `SendingScheduleEmpty` is the provider saying
                                NOTHING IS PLANNED - it is not zero and it is
                                not an error, and an answer that reports it
                                as either is wrong. 487 has read empty for
                                three days and that is the finding
    how many replies today      the notify store and the reply watcher
    credits spent today         reported, never gated

## WHAT MUST NOT BE RE-DERIVED

`scheduled_emails(352)` REFUSES - 96,045 rows over 6,403 pages - so an
account lookup must not walk a queue to answer. The local last-touch index
`work/stage/last-touch.json` is the answer and it is already built.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test name both directions. No live Slack, provider or LLM
call in any test.

## FILES FORBIDDEN

    src/clientapproval.py   src/providerwrites.py   config/.env
    work/*.jsonl            src/providers/*

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** c01b4bf3
- **TESTS:** 22 new tests in tests/test_slack_agent_task249.py, all green.
  279 existing Slack agent tests unchanged, all green. Import-graph test
  (test_slack_agent_cannot_act) passes: no write path introduced.
- **FILES CHANGED:**
  - src/slackagenttools.py: 7 new tool functions + REGISTRY entries + _is_dm helper
  - src/slackconversation.py: 7 keyword routes in KEYWORD_PLAN
  - tests/test_slack_agent_task249.py: new test file, 22 tests
- **FINDINGS:**
  - The Scope class does not carry channel_type, but scope.source starts with
    "dm:" for DMs and "channel:" for channels. The _is_dm() helper uses this.
  - notify.STATUS_FORBIDDEN_FIELDS has "contact_name", "first_name" etc. but
    not bare "name". The lead_status_dm tool strips "name" explicitly.
  - The keyword routes use multi-word phrases like "in a campaign", "status of",
    "why is" to avoid false positives with existing routes.
  - campaign_sending_schedule treats SendingScheduleEmpty as "none scheduled"
    (a result), not as zero or an error.
  - credits_today is INTERNAL only - spend is Resonate's, not a client's.
- **RISKS:**
  - The domain_hold_reason tool reads S5/S7 journals by domain substring match.
    If a journal key is an email address, the domain match works; if it is a
    hash or opaque ID, it will not find the row.
  - The domain_send_history tool reads events from the record's own event log.
    If events are stored elsewhere (e.g., in the provider's queue), the answer
    will undercount. The note in the output directs to weekly_plan for the
    full provider view.
- **RECOMMENDED CLAUDE ACTION:** Review and integrate. The privacy rule is
  structural: lead_status_dm refuses in channels before any data is read, and
  the answer scrubbing reuses notify._EMAIL_SHAPE and STATUS_FORBIDDEN_FIELDS.
