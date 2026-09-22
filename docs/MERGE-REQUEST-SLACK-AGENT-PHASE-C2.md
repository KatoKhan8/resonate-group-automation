# Merge request — Phase C, increments 3 to 6

**For the production session.** Branch `slack-agent` at `57c882a6`, pushed.
Not merged, not pushed to master.

Increments 1 and 2 are already on master as `cd143eda`. The branch carries
five commits master does not have:

    5ad2f7f7  the six client-channel fixes (client view, the offer)
    f3ecba4c  increment 3 — the offer's missing process, and counting
    c4120b45  increment 4 — per-user roles, and the week as an answer
    1af0b5b9  increment 5 — the material the client prompt was built from
    57c882a6  increment 6 — one domain, which is how the question is asked

`docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C1.md` covers what is already merged.
This covers the five above.

---

## 0. READ THIS FIRST: THE LIVE LOOP IS NOT RUNNING THE MERGED CODE

`scripts/slack_agent_loop.py` has been up since **13:18:29** today, PID
116292. Increments 1 and 2 landed on master at **14:25:10** and their files
were written at 14:23:16:

    slackconversation.py   14:23:16   loop started 13:18:29
    slackagenttools.py     14:23:16
    slacklanguage.py       14:23:16
    slack_agent_loop.py    14:23:16

Python imports at start and this loop does not reload. **So nothing merged
after 13:18 is in the running process**: no `sending_domains`, no
`slacklanguage`, no relay trigger, no seat handling. The merge is real and
the behaviour is not, and the only difference a reader would notice is the
agent answering a domain question the old way.

It needs a restart. That is yours — this session does not touch the running
estate. Everything below has the same dependency.

## 1. WHAT THIS TOUCHES THAT IS YOURS

    nothing

No `config/.env`, no `work/`, no `src/providers/*`, no `*_watch_loop.py`.
`src/providers/slack.py` is unchanged since increment 1, where
`thread_parent` is still filed for your review.

New files, all agent-owned:

    src/slackroles.py                                   NEW
    scripts/slack_followup_loop.py                      NEW   ← must be started
    tests/test_counting_is_a_different_question_from_lookup.py
    tests/test_the_offer_has_a_process_behind_it.py
    tests/test_a_role_records_and_never_refuses.py
    tests/test_the_week_is_an_answer_not_a_promise.py

Modified: `src/slackagenttools.py`, `src/slackconversation.py`,
`src/slackfollowup.py`, `src/slackrequests.py`,
`tests/test_slack_agent_cannot_act.py`,
`tests/test_what_a_client_is_shown.py`.

---

## 2. THE OFFER HAD NO PROCESS BEHIND IT

`src/slackfollowup.py` exists because the first live client answer ended
"would you like a short update once the first batch-1 mails go out" and
nothing anywhere could have produced that update.

It then shipped at `5ad2f7f7` with `register()` wired into the conversation
and **`due()` read by no process at all.** A client says yes, a row is
written, and the same silence follows. The fault was one level down and
harder to see, because a journal full of registered watches looks like a
working feature.

`scripts/slack_followup_loop.py` is the process, and it beats on its own
interval because the agent loop cannot do this work: it blocks in
`socketmode.envelopes` waiting for a mention, and on a quiet afternoon that
is a read that returns nothing for an hour. A watch that fires only when
somebody happens to speak is not a watch.

Three properties, each tested:

- **The offer is withdrawn while nothing is beating.**
  `slackfollowup.deliverer_is_running()` reads the deliverer's heartbeat
  and `offer_is_available` returns `None` when it is cold. Committed and
  not started is, from the client's side, identical to never built — so the
  agent says nothing rather than something optimistic. This is the property
  that stops "build the mechanism" degrading back into "write the
  sentence", and it means **if you merge this and do not start the loop,
  the feature is simply off** rather than lying.
- **Post first, close second.** Closing first loses the message when the
  post fails and leaves a client waiting on a watch that says it fired. The
  other order can at worst repeat, in the one place a repeat is visible.
- **The channel binding is re-resolved at fire time.** A channel rebound
  between registering and firing is cancelled unposted and logged loudly,
  because posting a day-old batch's campaign ids into a channel that now
  belongs to somebody else is a cross-client leak arriving late.

### To start it

    py -3 -u scripts/slack_followup_loop.py --interval 60

Dry run first if you want to see it decide without posting:

    py -3 scripts/slack_followup_loop.py --once --dry-run

It writes `work/heartbeat/slack-followup.json`, so `monitors` shows it like
every other watcher, and `work/slack-followups-delivered.jsonl` for what it
said and to whom.

---

## 3. COUNTING, WHICH IS 175 QUESTIONS AND WAS NOT ANSWERABLE

The catalogue's own finding: *the gap is counting, not looking up.
`lead_lookup` answers "is this person in a campaign"; nobody asks that.*

### `lead_counts`

Enrolled per campaign from the provider's membership, sent, replied,
bounced, and the last seven days — with **emails and people counted apart**
because they are not the same number. A three-step sequence sends three
emails to one person, so "na koliko leadova smo poslali ovaj tjedan" and
"how many emails went out" diverge by the length of the cadence and the gap
grows daily. People are counted by distinct provider lead id; a person in
two campaigns is one person in the workspace total and appears under both,
so the per-campaign figures do not sum to it and the note says so.

- **Enrolled is the provider's membership in every scope.** The local
  store's enrolled state is internal, under its own name, labelled as
  staging rather than membership — it is the number that reached a client
  once already.
- **An unreadable campaign makes every total a floor**, never a zero, with
  the count of failures beside it.

### `lead_in_campaign`

"Is this person in a campaign" answered from the provider rather than from
our staging record. A contact carrying a `bison_lead_id` was STAGED, and
staged is not enrolled: the push can have been refused, the lead stopped,
the campaign rebuilt.

`find_lead_by_email` searches the whole provider estate, which spans every
workspace we run there. So **only the numeric id leaves that search**, it is
asked about this workspace's campaign ids and no others, and *"the provider
has no lead with that address in any of this workspace's campaigns"* is the
same sentence for a lead that does not exist and a lead that belongs to
another client. Telling those apart is the disclosure. Tested.

Capped at twelve campaigns because `membership` costs one read each and
there is no route that asks the other direction.

`lead_lookup` now stamps its own answer `our store, not the provider`.

---

## 4. PER-USER ROLES, WHICH REFUSE NOTHING

`src/slackroles.py`. Every person in a client channel was the same person to
this agent, so a ticket reached you saying only "a client asked for this".

**The rule that matters is the one a permission system usually gets
backwards.** The highest-severity message in the entire corpus is a client,
in their own channel, writing:

> can you please stop sending messages to people who have replied????

An agent that answered that with "you are not authorised" — or that quietly
held it until somebody senior repeated it — would be worse than the agent
that existed before roles did. So:

- **Every request that REDUCES reach is taken from anybody, always**, with
  no authority check of any kind: `stop_account`, `remove_lead`,
  `pause_campaign`. The ticket says why there is no gate, so you do not read
  the absent authority line as an oversight and start adding one.
- **A request that widens or alters sending** — `add_lead`, `change_copy`,
  `change_window` — is still raised, unchanged, and arrives flagged when the
  requester is not the recorded owner.
- **None of it is ever said back into the client's channel.** The client
  hears exactly what they heard before: it is with the Resonate team, no
  timescale. Telling somebody in front of their colleagues that they may not
  ask is not the agent's to do.

Roles come from workspace policy, beside the users list that already exists:

    "slack.workspace_users": ["U0AAA", "U0BBB"]
    "slack.roles": {"U0AAA": "owner", "U0BBB": "observer"}

Unlisted is `member`, which is what everybody will be until somebody fills
this in. A role that is not one of `owner` / `member` / `observer` is
dropped rather than kept: a typo that became authority is the one bug this
file must not have. `SLACK_WORKSPACE_ROLES=U0AAA:owner,...` works too.

**Nothing is configured yet, and that is a decision for you** — until then
every ticket says "no role is recorded for this requester" and names the
policy key.

---

## 5. THE WEEK AS AN ANSWER

`weekly_plan`. The expectations doc calls the weekly update a habit with a
shape, asked every Monday and Tuesday; the agent could answer each piece
separately and none of it as the question people ask.

**The forward half is three days long and says so.** The provider answers
`today`, `tomorrow` and `day_after_tomorrow` and nothing beyond, so that is
the horizon, named in the readback. Anything past it would be our inference
wearing the provider's clothes.

**Three states that never merge.** The provider's own empty answer — its 400
carrying "No emails scheduled for this period" — reads `none scheduled`; a
failed read reads `unreadable`; a real zero stays `0`. Reading the first as
a failure alarms every weekend and reading it as zero reports a healthy
campaign as silent, which is the class of mistake the whole problem register
is made of.

The last seven days travel with it, because "nothing goes out tomorrow"
means one thing after a week of sending and another after a week of silence.

A client gets their own campaigns, plainly named, in their own zone. The
open change requests and campaigns awaiting decision are internal: an open
ticket names the operator and the gate, which is our machinery.

---

## 5a. THE MATERIAL CARRIED THE WORDS THE ANSWER WAS CHECKED FOR

Added at `1af0b5b9`. Found by auditing the client-filtered knowledge pack
against the term list the finished answer is checked against — a check that
had never been run, and which takes four lines.

`Scope._identity_for_scope` states the property the whole module rests on:
**the material may not contain a word the answer is checked for.** Three
things were breaking it.

**1. Client-safe policies carried our operating procedure.**
`CLIENT_SAFE_POLICY_IDS` says a policy's SUBJECT is the client's business.
It says nothing about the words the rule is written in, and the rules are
written for you. So `client-approval-cycle` was putting this into every
client prompt:

> one EmailBison campaign per attested human, 8 max … credits spent. Then
> wait 15 minutes. If I do not veto…

Both providers, the attestation control and what we spend. The rule text is
now checked the same way the answer is, and withheld when it fails — title
and `why` survive, because THAT a policy governs their outreach is theirs
and the procedure is not. Our own `docs/` paths are withheld with it.

The cost of this was never only the leak, which the outbound guard catches.
It is that an honest answer quoting the policy is **discarded**, and the
reader gets a hedge from a system that was working perfectly — the failure
`slackagenttools.run` documents at length, arriving by a different door.

**2. A client named after a provider could not be named.** One workspace
here is `contactout`, which is also on the commercial term list, so every
answer naming that client by name was being thrown away in that client's
own channel. A word list cannot tell the vendor from the customer, and
refusing to say a customer's name is unmistakably the worse error. The
exemption is the scope's own slug and nobody else's — `productive` still
may not say it, and `contactout` still may not say `heyreach`.

**3. The experiment vocabulary was stripped from campaign NAMES and not
from prose.** `plain_campaign_label` cannot reach the model writing "the
US-hours control campaign" itself, out of the thread above it or out of its
own sense of what it is describing — and that is what actually went out.
`INTERNAL_EXPERIMENT_TERMS` blocks the phrases with no innocent reading. It
is deliberately narrower than the label list: `test`, `arm`, `batch`,
`variant` and `pilot` stay off it, because a false positive discards a
whole correct answer and `UNBOUND_EXTRA_TERMS` already records what
happened the last time this list reached for an ordinary word.

All three client packs now audit clean. There is a test that asserts it
against the **live** pack rather than a fixture, which is the only version
of it that can catch a policy somebody edits next month.

## 5b. ONE DOMAIN, WHICH IS HOW THE QUESTION IS ASKED

Added at `57c882a6`. `domain_detail` — the catalogue's third tool.

> Note the shape: almost never "list the domains". Usually ONE domain, one
> sender, one campaign — which `sending_domains` answers at the wrong
> granularity.

The proof is the message immediately after the 194KB CSV went into the
client channel: *sending-domain-a.example.test, kakva je ovo domena?* Sixty-nine
domains answer a question nobody asked while leaving the one they did ask
open.

It gives whose mailboxes are on the domain, how many, the daily ceiling,
which campaigns it carries, and what it sent this week — people and emails
apart, as `lead_counts` does. Health and bounce stay internal, on the line
`sending_domains` already draws.

- **Not yours and nobody's are one answer.** Same rule as
  `lead_in_campaign`: distinguishing them confirms the other client's
  estate exists.
- **A pasted address leaves as a domain.** People paste
  `tina@sending-domain-a.example.test` when they mean the domain. The local part is
  dropped before anything is looked up, so the answer cannot echo a mailbox
  back — which `sending_domains` refuses on purpose in every scope. A test
  asserts no `@` survives anywhere in the answer.
- **A value with no dot in it is refused**, not looked up as a domain.

### And the test file found something about the tests

It passed alone and failed in a full run. `from . import senderidentity`
reads the ATTRIBUTE on the `src` package and only falls back to
`sys.modules` when there is none — so patching `sys.modules` works exactly
until something earlier in the run imports the real module. Both are
patched now, and the comment says why, because the next person mocking a
`src` sibling will hit it.

## 6. TESTS

    tests/test_counting_is_a_different_question_from_lookup.py   25  NEW
    tests/test_the_offer_has_a_process_behind_it.py              15  NEW
    tests/test_a_role_records_and_never_refuses.py               18  NEW
    tests/test_the_week_is_an_answer_not_a_promise.py            14  NEW
    tests/test_the_question_is_one_domain_not_the_list.py        15  NEW
    tests/test_what_a_client_is_shown.py                         50  (+17)
    tests/test_slack_agent_cannot_act.py                         10

**503 slack tests, green**, run together and each file alone.

`tests/test_invariants.py` still has its one pre-existing failure — two
modules importing `ProviderError` by name — which is not from this branch
and is the same one increment 1 reported.

### The cannot-act guarantee got wider

`AGENT_SOURCES` listed five of the eight files that run when a Slack message
arrives: `slackclientview`, `slackfollowup` and `slacklanguage` arrived with
Phase C and were never added. They are on it now, with the deliverer. A
guarantee that covers most of the files is one somebody adds the next file
to without noticing.

Two provider verbs were added to `PROVIDER_READ_VERBS`, deliberately, both
GETs: `find_lead_by_email` (`GET /leads?search=`) and `sending_schedule`
(`GET /campaigns/{id}/sending-schedule`). `slack.post` is now allowed in two
files rather than one — the agent loop and the deliverer, whose entire job
is one message into one thread.

---

## 7. STILL YOURS

Carried forward from increment 2 and unchanged:

- Reconcile `hr-` / `li-` properly. The seat count works on the bare-id join.
- Decide seat ownership, or accept counts-without-names indefinitely.
- Decide the eight unbound shared client channels: bind, leave, or authorise.
- `src/providers/slack.py` `thread_parent` — still for review.
- The plaintext GoDaddy password in Slack history.

New:

- **Restart `slack_agent_loop.py`.** It is running pre-merge code.
- **Start `slack_followup_loop.py`**, or accept that the follow-up offer
  stays switched off. It switches itself off correctly, which is the point,
  but a client who would have been told is not being told.
- **Fill in `slack.roles`** for Productive, or accept "no role recorded" on
  every widening ticket.
- `meetings_booked` is still the most-asked number nothing can produce, and
  the promise scan — 53 commitments in ten days — still has no consumer.
