# Merge request — Phase D3: the second post, and it is about a person

**For the production session.** Branch `slack-agent` at `55aced87`, pushed
and verified against the remote. Not merged, not pushed to master.

Phase D **item 2**: *"proactive client updates, opt-in per thread: post once
when that batch's first provider-confirmed send lands and once on first
human reply, then stop. Never unsolicited in a client channel."*

This sits on top of **D2** (`edb9146f`, `docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D2.md`),
which is also unmerged. Take them in order or take them together.

## 0. WHAT THIS TOUCHES THAT IS YOURS

    nothing

No `config/.env`, no `work/`, no `src/providers/*`, no `*_watch_loop.py`.
`scripts/slack_followup_loop.py` is the agent's own deliverer, written by
this session's lineage in C3, and is not a `*_watch_loop.py`.

    src/slackfollowup.py            stages, the reply half, the messages
    src/slackagentreadback.py       newest_reply_id()
    src/slackconversation.py        the marker at registration; OFFER_NOTICE
    scripts/slack_followup_loop.py  THE CALLER
    tests/test_the_second_post_is_a_person_not_a_counter.py   NEW, 26 tests
    tests/test_slack_agent_cannot_act.py                      two verbs argued for

---

## 1. THE HALF THAT WAS MISSING, AND WHY IT IS THE WHOLE POINT

The send half shipped in C3. `f5ae0270` on this branch added the module
side of the reply half and **said in its own commit message that nothing
called it** — which is exactly this module's history:

> `src/slackfollowup.py` was written because the agent offered an update
> nothing could deliver. It then shipped with `register()` wired into the
> conversation and `due()` READ BY NOTHING — so a client says yes, a row is
> written, and the same silence follows.

**This commit is the caller.** `tick()` now reads
`due_replies(read_human_replies)`, `deliver()` has a reply branch, and the
send branch advances the watch instead of closing it.

    awaiting_send  -> awaiting_reply   the send happened, announced once
                   -> expired          nothing sent in 24h; says so once
    awaiting_reply -> fired            a person replied, announced once
                   -> expired          nobody did in 7 days; says so once
    either         -> cancelled        withdrawn, or the channel was rebound

`due_replies` is read in its **own** `try`, separate from `due`'s. The two
halves read different feeds, and one being down is not the other being
down; collapsing them would let a reply-feed outage stop a send from ever
being announced.

---

## 2. A PERSON, NOT A COUNTER

The provider's `replied` counter includes autoresponders. That is precisely
what **D2's reply-classification work** (`4af4f982`) established: on a day
of 316 sends the only "positive" was an executive assistant replying on
someone else's behalf.

So the reply half does not read a counter. It reads the reply feed, where
**each row carries its own `campaign_id`** — verified live this morning
against the estate, 15 rows, campaign 492 among them. The local event log
cannot do this job: `reply_classified` events carry `contact` and
`classification` and **no campaign**, and exactly one record in the whole
live queue names a campaign. The join is the provider's, not ours.

**Two witnesses, and they must agree.** A reply counts as human only when
`replies.is_automated` says it is not automated **and** the provider's own
`automated_reply` flag does not contradict it. Disagreement fails closed,
because the errors are not symmetrical: a missed human reply costs one
tick, and a false one tells a client an autoresponder was their first real
answer — in a thread they opted into, in the direction that sounds like
good news. A classifier that raises is not a licence either.

### 2a. The marker, not a count

The watch stores the **highest provider reply id** it had seen when the
client said yes. A count would have to be recomputed from the whole reply
history every tick to be compared; a marker lets the walk stop at the first
already-seen row, so in steady state it reads one page.

**Read at the yes, not at the offer.** Between the two the client reads,
thinks and types, and a reply arriving in that gap is theirs.

**Unreadable is None and stays None**, at both ends. No marker at
registration means `advance_to_reply` closes the watch at the first post
rather than advancing it — the reply half was never promised to that
client, so it is not owed to them. An unreadable feed at fire time leaves
the watch open for the next tick rather than announcing a silence nobody
measured.

---

## 3. THE PROMISE MOVED LAST

`OFFER_NOTICE` now says two messages **and says "then I'll stop"** — a
client agreeing to updates is not agreeing to be narrated at. It was
changed **after** the mechanism existed, in the same commit. That ordering
is the whole lesson of this module and it is worth stating: the sentence
may never move ahead of the thing that keeps it.

`offer_is_available` still returns `None` while the deliverer is cold, so
none of this is offered at all until `scripts/slack_followup_loop.py` is
running. **It has still never been started** — there is no
`work/heartbeat/slack-followup.json`. That is correct behaviour and it is
also why this feature is worth nothing until item 5 of §7 happens.

---

## 4. TWO GUARDS FIRED, AND BOTH WERE RIGHT

`tests/test_slack_agent_cannot_act.py` caught **`fetch_replies`** and
**`classify_reply_row`** the moment the agent first touched them, with the
message *"If one of these is genuinely a GET, add it to
PROVIDER_READ_VERBS deliberately."*

That is the same service this guard did for ContactOut's `company-search`
POST yesterday (D1 §6), and it is worth noticing it working twice in two
days. Both are argued for in the allow-list rather than added as noise:

- `fetch_replies` is **verified a GET** — `request("GET", query(...))`,
  and its own docstring says "Read-only: this endpoint creates nothing".
- `classify_reply_row` **makes no request at all**; it is a pure function
  over a row the caller already holds. It is named because the guard reads
  attribute access rather than requests, which is the right way round.

---

## 5. THE TESTS

`tests/test_the_second_post_is_a_person_not_a_counter.py` — **26 tests, and
every one drives the real deliverer**, loaded by path, through
`loop.tick()` or `loop.read_human_replies`. None of them hands
`followup.due_replies` a reader of its own and calls that a passing
feature: **a caller that does not exist is the failure mode, and a test
that supplies the caller itself cannot see it.**

    1. two posts, never three - the third tick posts nothing
    2. out-of-office, ticket acknowledgement and YESTERDAY'S ACTUAL EA
       REPLY are each rejected through the REAL classifier - see 5a
    3. either witness alone disqualifies; a raising classifier disqualifies
    4. the marker - an older reply, the marker row itself, another
       campaign's reply, and a human reply buried under an older row
    5. unreadable is not zero, at registration and at fire time
    6. seven quiet days are reported out loud, not dropped
    7. a rebound channel is cancelled unposted AT THE SECOND STAGE TOO -
       it fires days later, which is when a rebinding is likeliest

**Attacked twice.** With the caller removed and nothing else changed, **7 of
the 26 fail plus 1 error**. With `_is_human` leaning on the provider's
`automated_reply` flag alone, **7 fail** — including all three EA tests and
the out-of-office and ticket ones.

### 5a. The EA reply, and a fixture that had been trimmed until it passed

The operator's instruction was *"automated and assistant_redirect never fire
it — add a test with yesterday's EA auto-reply as the negative case."* The
gate was already correct; the **fixture was not**.

The first EA fixture here was synthetic — `"I manage Peter's inbox."` —
written that short because the realistic sentence I tried first classified
`negative` and fired the trigger. **A fixture trimmed until it passes is not
evidence**, and this is the fourth time in three days that a test in this
repository proved something other than what it claimed.

It now imports `EA_REDIRECT` from
`tests/test_an_assistant_is_not_a_buying_signal.py`, where `4af4f982`
sanitised the real thing — **one canonical fixture for one real reply**,
not a second copy to keep in step. The emoji and exclamation marks are load
bearing: they are what made the old classifier read it as warmth.

Three tests where there was one, and the second and third are the ones that
matter under refactoring:

- `test_yesterdays_ea_auto_reply_does_not_fire_it` — the named case.
- `test_it_is_the_new_classifier_that_stops_it` — names the mechanism, so a
  refactor onto the provider flag alone cannot pass this class by accident.
- `test_the_provider_did_not_flag_it` — **the hard case.** That row carries
  `automated_reply` **false**, and it is stopped anyway. The provider's flag
  was true on 21 of that day's 26 replies, but a flag is not the rule.

**319 slack tests green.** `test_replies` (76), `test_invariants` (83),
`test_the_offer_has_a_process_behind_it` (15),
`test_what_a_client_is_shown` (50) and the neighbouring suites are
unchanged. I did **not** re-run the full-repo discovery: its 71/35 baseline
is infra's and I was told to leave it alone.

---

## 6. ONE FINDING, AND IT IS NOT OURS TO FIX

Writing the fixtures surfaced a real classifier behaviour:

> "I manage Peter's inbox and I look after his diary — **I will pass this
> along to him**" classifies **`negative`**.

"I will pass this along" matches the decline sense of *"I'll pass"*. A
forwarding assistant is read as a refusal.

**It errs in the safe direction for sending** — it stops contact rather than
continuing it — so nothing about the cadence is unsafe. What it costs is the
contact candidate that `assistant_redirect` exists to keep, and
`reply.on_referral` never gets the chance to apply.

**But it is NOT safe for this feature**, and that is the part worth your
attention: a `negative` classification is not automated, so a forwarding
assistant **does** fire the second post. A client who opted in would be told
their first human reply had arrived when what arrived was an assistant
forwarding the mail on.

It is asserted as current behaviour in
`test_the_forwarding_assistant_is_the_boundary_and_it_does_fire`, not hidden
in a comment, so the day somebody fixes `src/replies.py` that test fails
loudly and tells them a client-facing trigger moved with it.
`src/replies.py` is not this session's to edit and the reply-classification
policy is the production session's, so it is reported rather than patched.

A second, smaller one, recorded because it looks like a bug and is not: an
EA who writes *"he is not taking new meetings"* classifies `negative`
rather than `assistant_redirect`, because NEGATIVE outranks
ASSISTANT_REDIRECT in the rule table **by design** — a classification may
never soften a stop. The fixture was wrong, not the code.

---

## 7. STILL YOURS

New:

- **Start `scripts/slack_followup_loop.py --interval 60`.** Nothing about
  this feature is offered to any client until it beats, by construction.
- **`REPLY_TTL_SECONDS = 7 days` is a guess** and is labelled as one in the
  source. Nobody here has measured how long a first human reply takes; when
  somebody does, that is the line to change.
- **A judgement to confirm:** a person who replies *"not interested"* is a
  first human reply and will fire the second post. The message does not
  characterise the reply — it says a person wrote one and that the thread is
  closed from our side — but if you would rather the second post fired only
  on a non-negative reply, that is a one-line change to `_is_human`'s
  caller and it is yours, not mine.

Carried forward and still open: everything in
`docs/SLACK-AGENT-HANDOFF-2026-09-23-MORNING.md` §7, starting with the fact
that **`slack_agent_loop.py` is still not running** and has no liveness
monitor.
