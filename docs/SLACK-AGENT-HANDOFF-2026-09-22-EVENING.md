# Slack agent — handoff, 2026-09-22 evening

Supersedes `SLACK-AGENT-HANDOFF-2026-09-22-PM.md`, whose "one commit
unmerged" is now eight.

**Merged to master:** Phases A and B, and Phase C increments 1 and 2
(`cd143eda`). Master head is `be6e14b2`.

**On the branch, not merged:** `slack-agent` @ `1f840c4f`, pushed.

    5ad2f7f7  the six client-channel fixes (client view, the offer)
    f3ecba4c  the offer's missing process, and counting
    c4120b45  per-user roles, and the week as an answer
    1af0b5b9  the material the client prompt was built from
    57c882a6  one domain, which is how the question is asked
    5025feb6  meetings booked - the number the contract runs on
    0e376be1  the promise scan - 53 promises, now checked
    1f840c4f  campaign_copy - nobody ever asked for the shape

Merge requests: `docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C2.md` (the first
five) and `docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C3.md` (the last three,
built to the operator's decisions of 2026-09-22). Neither touches
nothing of the production session's: no `config/.env`, no `work/`, no
`src/providers/*`, no `*_watch_loop.py`.

---

## THE THING TO ACT ON FIRST

**The running agent loop is not executing the merged code.** PID 116292
started at 13:18:29; increments 1 and 2 landed on master at 14:25:10 and
wrote their files at 14:23:16. Python imports at start and this loop does
not reload, so `sending_domains`, `slacklanguage`, the relay trigger and
the seat handling are all merged and none of them is running. A restart is
the whole fix and it is the operator's to do.

## WHAT THE EIGHT COMMITS ADDED

**The offer now has a process.** `slackfollowup` shipped with `register()`
wired in and `due()` read by nothing — a client could say yes, a row was
written, and the silence the module exists to prevent followed one level
down. `scripts/slack_followup_loop.py` fires it, and the agent checks that
loop's heartbeat before it makes the offer at all: not started means not
offered, so an unstarted deliverer switches the feature off instead of
turning it into a lie.

**Counting.** `lead_counts` and `lead_in_campaign` close the catalogue's
largest gap — 175 questions asking *how many* against an agent that could
only answer *who*. Emails and people are counted apart, enrolled is the
provider's membership in every scope, an unreadable campaign makes every
total a floor, and a lead in another client's campaign reads exactly like a
lead that does not exist.

**Roles that refuse nothing.** `src/slackroles.py` records who asked, for
the operator. Every request that reduces reach — stop, remove, pause — is
taken from anybody, always: the corpus's highest-severity message is a
client writing "can you please stop sending messages to people who have
replied????" and an agent that made that wait would be worse than one with
no roles at all. Widening requests are raised unchanged and arrive flagged.

**The week.** `weekly_plan` answers Monday's question with a three-day
forward horizon it names, because that is how far the provider answers.
`none scheduled`, `0` and `unreadable` stay three separate states.

**One domain.** `domain_detail` answers the question the catalogue says
is actually asked — one domain, not a list of sixty-nine — which is the
message that followed the 194KB CSV in the client channel. A domain that
is not this workspace's reads exactly like a domain that is nobody's, and
a pasted address leaves as a domain with the local part dropped.

**The material.** An audit of the client-filtered pack against the term
list the answer is checked against found three faults: policy rule text
carrying our operating procedure into every client prompt, a client named
after a provider whose own name was a forbidden word in their own channel,
and the experiment vocabulary blocked in campaign names but not in prose.
All three fixed; all three client packs now audit clean, asserted against
the live pack.

**Meetings booked.** A hand-fed ledger, the operator's design: an internal
person types `meeting booked <domain> <date>` and one row is recorded.
Sources never merge because `counts()` returns `{source: n}` and nothing in
the module hands back a bare number. A question never writes a row, the
check is on the person rather than the room, and attribution is refused
rather than guessed.

**The promise scan.** The operator's delivery definition, implemented
verbatim. Four states, and `undated` is never called late. "danas ili
sutra" is judged on sutra. The evidence is named rather than collapsed,
because the promise this was written about was kept with the wrong
artefact. Internal-only, structurally.

**Campaign copy.** What a step actually says, filtered by walking
approvals rather than steps - so a revoked or edited step drops out by
itself and "not history" needs no code that knows what history is. A
variant under test is withheld from a client and counted, never silently
omitted.

## STATE OF THE TESTS

**577 slack tests, green**, together and file by file.
`tests/test_invariants.py` has its one pre-existing failure — two modules
importing `ProviderError` by name — which predates this branch and is the
same one increment 1 reported.

## OPEN FOR THE OPERATOR

Carried forward, unchanged:

- Seat ownership: which HeyReach seats are Resonate's. Until decided,
  client channels give counts without names.
- `hr-` / `li-` reconciliation. The seat count works on the bare-id join.
- The plaintext GoDaddy password in Slack history.
- The eight unbound shared client channels: bind, leave, or authorise.
- `src/providers/slack.py` `thread_parent`, still for review.
- `slack_history.py --loop`, handed over and not running.

New:

- **Restart `slack_agent_loop.py`.** It is running pre-merge code.
- **Start `slack_followup_loop.py --interval 60`**, or accept that the
  follow-up offer stays off. It switches itself off correctly, which is the
  point, but a client who would have been told is not being told.
- **Fill in `slack.roles`** for Productive, or accept "no role recorded" on
  every widening ticket.

## THE TWO FACTS THAT STILL CONTRADICT THE EARLIER HANDOFFS

Unchanged and unresolved: batch 1 shows `emails_sent 0` on all eight
campaigns, and holds **393 leads, not 151** — two independent provider
witnesses agree. `lead_counts` will now report that from provider
membership rather than from the store, which is how it should have been
read in the first place.

## NEXT THREE

All three of the previous next-three are built. What is left:

1. **`report_link`** — the catalogue's fifth tool and the last one on its
   list. `src/clientreport.py` exists and nothing calls it from here;
   reporting is 11 questions, all client. Pointing at a report is a
   smaller and more honest thing than composing one.
2. **A second meetings source.** The ledger is shaped for it - a new tag,
   never a bigger number under the old one - and Calendly or the CRM would
   halve the hand-feeding.
3. **Refresh the Slack history on a schedule.** The promise scan is
   correct and empty until something pulls history; `slack_history.py
   --loop` is written, handed over, and not running.
