# Slack agent — handoff, 2026-09-22 night

Supersedes `SLACK-AGENT-HANDOFF-2026-09-22-EVENING.md` and everything
before it. Written to the test CLAUDE.md sets: a fresh session on another
machine, with a clone and the secrets supplied separately, should be able
to read this and say what happened and what to do next.

**Merged to master:** Phases A and B, and Phase C increments 1 and 2
(`cd143eda`). Master head when this was written: `be6e14b2`.

**On the branch, not merged:** `slack-agent`, pushed and verified against
the remote. The last CODE commit is `ecb93a9f`; everything after it is this
handoff and its merge request, so a sha quoted here cannot be the branch
head by the time you read it. **Eleven commits master does not have:**

    5ad2f7f7  the six client-channel fixes (client view, the offer)
    f3ecba4c  the offer's missing process, and counting
    c4120b45  per-user roles, and the week as an answer
    1af0b5b9  the material the client prompt was built from
    57c882a6  one domain, which is how the question is asked
    5025feb6  meetings booked - the number the contract runs on
    0e376be1  the promise scan - 53 promises, now checked
    1f840c4f  campaign_copy - nobody ever asked for the shape
    ecb93a9f  a client sees a winner, and nothing else
    816e42b7  the merge request for all of it
    (+ this handoff)

Two merge requests, both current:

    docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C2.md   increments 3 to 6
    docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C3.md   the operator's decisions

---

## THE FIRST THING, AND IT IS NOT A MERGE

**The running agent loop has never executed any merged Phase C code.**

`scripts/slack_agent_loop.py`, PID 116292, started **13:18:29**. Increments
1 and 2 landed on master at **14:25:10** and wrote their files at 14:23:16.
Python imports at start and this loop does not reload, so `sending_domains`,
`slacklanguage`, the relay trigger and the seat handling are all merged and
none of them is running. The only visible symptom is the agent answering a
domain question the old way, which is indistinguishable from a bug.

A restart is the whole fix and it is the operator's to make. Everything
below has the same dependency.

**How to check this for any loop here**, because there are about fifteen of
them and none reloads:

    Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
      Where-Object { $_.CommandLine -like '*<loop>*' } |
      Select ProcessId, CreationDate
    ls -l --time-style=+%m-%d_%H:%M:%S src/<module>.py

Any mtime later than the start time means the process is stale. Never write
"X is live" on the strength of a merge; write "merged, needs a restart" and
name the loop.

---

## WHAT THE TEN COMMITS ADDED

**The offer has a process.** `slackfollowup` shipped with `register()`
wired in and `due()` read by nothing — a client said yes, a row was
written, and the silence the module exists to prevent followed one level
down. `scripts/slack_followup_loop.py` fires it, and the agent reads that
loop's heartbeat before making the offer: not started means not offered, so
an unstarted deliverer switches the feature off rather than turning it into
a lie.

**Counting.** `lead_counts` and `lead_in_campaign` close the catalogue's
largest gap — 175 questions asking *how many* against an agent that could
only answer *who*. Emails and people counted apart, enrolled from provider
membership in every scope, an unreadable campaign making every total a
floor, and a lead in another client's campaign reading exactly like a lead
that does not exist.

**Roles that refuse nothing.** `src/slackroles.py` records who asked, for
the operator's eyes. Every request that reduces reach — stop, remove, pause
— is taken from anybody, always, because the corpus's highest-severity
message is a client writing *"can you please stop sending messages to
people who have replied????"*. Widening requests are raised unchanged and
arrive flagged.

**The week.** `weekly_plan`, with a three-day forward horizon it names,
because that is how far the provider answers. `none scheduled`, `0` and
`unreadable` stay three separate states.

**One domain.** `domain_detail` answers the question the catalogue says is
actually asked, which is the message that followed the 194KB CSV. A domain
that is not this workspace's reads exactly like one that is nobody's.

**The material.** An audit of the client-filtered pack against the term
list the answer is checked against found three faults nobody had looked
for: policy rule text carrying our operating procedure into every client
prompt, a client named after a provider whose own name was a forbidden word
in their own channel, and the experiment vocabulary blocked in campaign
names but not in prose. All three fixed, asserted against the live pack.

**Meetings booked.** A hand-fed ledger to the operator's design.
`counts()` returns `{source: n}` and nothing in the module hands back a
bare number, so a second source can only ever be a second key. A question
never writes a row; the check is on the person, not the room; attribution
is refused rather than guessed.

**The promise scan.** The operator's delivery definition, verbatim. Four
states, and `undated` is never called late. "danas ili sutra" is judged on
sutra. The evidence is named rather than collapsed, because the promise it
was written about was kept with the wrong artefact.

**Campaign copy, and the visibility axis.** `campaign_copy` walks approvals
rather than steps, so revoked and edited copy drop out by themselves.
Variants carry `client_status` — testing / winner / retired — as a second
axis that never touches allocation. Clients see a winner as ordinary
cadence copy; internal sees all three.

---

## STATE OF THE TESTS

**591 slack tests, green**, together and file by file. **218
variant-engine tests, green and untouched.**

Two known failures, neither from this branch:

- `tests/test_invariants.py` — two test modules import `ProviderError` by
  name. Present since before Phase C and reported in every merge request
  since increment 1.
- `tests/test_the_cadence_the_client_chose_is_the_one_that_runs.py` and
  `tests/test_the_cadence_reacts_to_what_the_prospect_did.py` —
  `productive_li_heavy_v1` is expected to carry 6 LinkedIn steps and has 5,
  total 10 rather than 11. **Verified pre-existing**: they fail identically
  against the pristine `src/variants.py` from before this branch touched
  it. It may be this worktree's own `work/clients/productive` rather than
  production's, so check on master before editing any cadence on the
  strength of it.

---

## OPEN FOR THE OPERATOR

Ordered by what costs most to leave undone.

1. **Restart `slack_agent_loop.py`.** It is running pre-merge code.
2. **Start `scripts/slack_history.py --loop` as a monitor.** The operator's
   decision of 2026-09-22; this session did not run it. The promise scan is
   correct and empty until something pulls history. Read
   `MERGE-REQUEST-...-C3.md` §2e first: the raw history contains the
   plaintext GoDaddy password, payroll and personal phone numbers, so a
   scheduled pull puts a copy of that on disk on a schedule.
3. **Start `scripts/slack_followup_loop.py --interval 60`**, or accept that
   the follow-up offer stays correctly switched off. It withdraws itself,
   which is the point, but a client who would have been told is not being
   told.
4. **The plaintext GoDaddy password in Slack history.** A standing exposure
   that predates all of this and is made worse by item 2.
5. **Fill in `slack.roles`** for Productive, or accept "no role recorded"
   on every widening ticket.
6. **Seat ownership** — which HeyReach seats are Resonate's. Until decided,
   client channels give counts without names.
7. **`hr-` / `li-` reconciliation.** The seat count works on the bare-id
   join; 32 of 33 resolve.
8. **The eight unbound shared client channels:** bind, leave, or authorise
   reading.
9. **`src/providers/slack.py` `thread_parent`** — one added READ, still for
   review since increment 1.
10. **The digest line** for meeting counts (C3 §1e), if you want it there.
11. **Promote a winner** when there is one (C3 §3c). Until somebody does,
    every variant reads as `testing` and no client sees one — which is
    exactly the pre-merge behaviour.
12. **A correction verb for the meetings ledger**, if you want one.

---

## THE TWO FACTS THAT STILL CONTRADICT THE EARLIER HANDOFFS

Unchanged and unresolved since the morning: batch 1 shows `emails_sent 0`
on all eight campaigns, and holds **393 leads, not 151** — two independent
provider witnesses agree. `lead_counts` and `batch_state` now report that
from provider membership rather than from the store, which is how it should
have been read in the first place. Nothing has been done about the
underlying discrepancy.

---

## NEXT THREE

1. **`report_link`** — the catalogue's fifth and last listed tool.
   `src/clientreport.py` exists and nothing calls it from here. Reporting
   is 11 questions, all client. Pointing at a report is smaller and more
   honest than composing one.
2. **A second meetings source.** The ledger is shaped for it — a new tag,
   never a bigger number under the old one — and Calendly or the CRM would
   halve the hand-feeding.
3. **Watch the promise scan's false opens.** Delivery is judged in the
   promise's own thread, exactly as specified, so a promise answered by a
   separate channel message reads as `open`. If that shape shows up in the
   briefing, the fix is a decision about the window, not a patch.

---

## THE RULES THIS SESSION WORKED UNDER

Recorded so the next one does not have to be told again. Stated by the
operator, not written in CLAUDE.md:

- This session never merges to master and never pushes to it. Delivery is a
  merge-request doc in `docs/` plus one line in `#resonate-os`
  (`C0C3C6MDN9L`).
- It never edits `config/.env`, `work/`, `src/providers/*` or
  `scripts/*_watch_loop.py`. Verified for every commit above.
- `src/variants.py` was the one file touched outside slack-agent code.
  Branch overlap was checked first — nothing ahead of master touches it —
  and the change is additive, with the variant engine's own 218 tests
  passing untouched.
- A merge request per increment; a handoff before context runs out.
