# Merge request — the account rule and the collision gate

**Lane G · 2026-09-25 morning · for GLM adversarial review before merge**

Branch `worktree-agent-a93040ed4ffcf10b6`, HEAD `83609320`
(parent `46846329`, forked from master `24acafff`).
Not merged, not pushed.

---

## 0. READ THIS FIRST — three things that block today's plan

Everything else in this document is secondary to these. Each is measured, and
each one changes what the foreground session should do this afternoon.

### 0.1 The EmailBison staging path does not run this gate, and cannot be made to by me

`src/bisonfactory.py:1455-1463` says so in its own words: *"`_ensure_leads`
calls `bison.create_lead` and `bison.attach_leads` directly, bypassing
`executionguard.authorize()` and every gate it runs."*

| path | runs the account rule? |
|---|---|
| `executionguard.authorize` — the per-action send gate, both channels | **yes**, wired here |
| `heyreachfactory.ensure_leads` → `_mint_authorization` → `authorize` (`:1174`) | **yes**, via the above |
| `bisonfactory.stage` → `_ensure_leads` | **NO — bypasses `authorize` entirely** |

**The 63 stopped leads go into fresh campaigns through `bisonfactory.stage`.**
That is the un-gated path. `bisonfactory.py` is held by lane B (staging guard)
and lane D (copylint wiring, ~line 86) this morning, so I did not touch it —
the collision is flagged rather than taken.

**The wiring is not a two-line copy of what I did, and I want to be precise
rather than hand the next lane a snippet that will not compile.**
`_refuse_colliding_leads(wanted, workspace_id, already_on)`
(`src/bisonfactory.py:1336`) works over *lead* dicts carrying `email` and
`contact_key` — it never sees a record, and `account_rule.evaluate` needs one.
So either:

- the caller `_ensure_leads` (`:1417`, which does have the records) evaluates
  the rule per contact before calling it and passes the refusals down, or
- `_refuse_colliding_leads` gains a `records` argument keyed so each lead can
  find its own.

The first is smaller. Either way the refusal should join the existing
`refused` list so a staged cohort fails with one message naming every reason,
which is the behaviour ISSUE-021 tuned.

Until that lands, **this gate does not protect the EmailBison cohort build.**

### 0.2 Productive's live config refuses the second persona before this rule is reached

`config/clients/productive.yaml:637` sets `fatigue.account.max_active_contacts:
2`, configured rather than defaulted. `fatigue.account_check` WARNs when the
count *would equal* the limit and BLOCKs above it; `executionguard` demands
`fatigue` be exactly `"ok"`, and `eligibility._account_fatigue` holds on BLOCK.

Measured against the loaded Productive config:

| colleagues already touched at the account | `fatigue.check` | effect |
|---|---|---|
| 0 | `ok` | sends |
| 1 | `warn` | **refused at the `fatigue` gate** |
| 2 | `block` | **refused at `eligibility`** |

So a **second** persona — which the operator's rule permits after five days of
silence — is refused today whatever this rule says, and a third is refused
twice over. **The US second-persona batch this afternoon is exactly this case.**

Raising a send cap is an operator decision and `productive.yaml` is lane B's
file, so I changed nothing. The number is named here so it can be changed
deliberately: `max_active_contacts: 2` → `3` is what the operator's own rule
implies, since the rule defines a first, a second and a third persona.

Pinned by `TheLiveConfigRefusesBeforeThisRuleIsReached` in
`tests/test_the_account_rule_refuses_the_send_itself.py`, which asserts the cap
is still 2 and will fail the day somebody changes it — deliberately, so the
change is noticed.

### 0.3 The ISSUE-035 exception is correct and INERT on today's data

The exception requires two arms: our own reason **and** an operator-recorded
move. Measured:

- `work/action-ledger.jsonl` contains **zero** `stop_lead` rows (106
  `bison.activate`, 18 `heyreach.activate`, 12 `heyreach.add_lead`, nothing
  else). Its last write is 2026-09-18 07:35, six days before the stops.
- All **8** `contact_stopped` events in `work/queue.jsonl` carry `outcome` and
  nothing else. Neither `our_stop` nor `operator_recorded` appears on any of
  them, and neither name appears anywhere in `src/` or `scripts/`.

**Nothing in the system writes either field.** So the exception can never fire
on the 63 as they stand, and merging this does not by itself unblock them. It
makes them *unblockable with an attestation* — somebody must record the move.

This is the "shipped inert past green tests" failure this codebase has
produced before, and I am naming it rather than letting a green suite imply the
63 are free. **If the intent is to re-push the 63 today, recording the
operator's move is a prerequisite, not a follow-up.**

---

## 1. What the gate enforces

`src/account_rule.py` is new. `evaluate(rec, contact_key)` returns
`{"verdict": ALLOW|REFUSE, "why": <sentence>, "rule": <name>}`, in this
precedence order:

| # | rule name | behaviour |
|---|---|---|
| 1 | `same_contact_twice` | any confirmed touch to this contact, any channel → REFUSE |
| 2 | `account_unsubscribed` | an unsubscribe anywhere at the account → REFUSE |
| 2 | `account_answered` | a **human** reply anywhere at the account → REFUSE. Automated (out-of-office, assistant redirect, bare acknowledgement, per `replies.is_automated`) is not human. An **unclassified** reply is treated as human |
| 3 | `account_stopped` | a stop anywhere at the account → REFUSE, **unless** our own reason AND an operator-recorded move (ISSUE-035) |
| 4 | `linkedin_reply_state_unreadable` | a confirmed LinkedIn touch at an account where no contact carries `heyreach_lead_id` → REFUSE (ISSUE-041) |
| 5 | `stagger_gap` | 2nd persona needs 5 days of silence; 3rd needs 12 |
| 5 | `persona_cap` | a 4th persona → REFUSE; the rule defines no fourth |

Precedence is load-bearing in two places, both tested: an excused ISSUE-035
stop does **not** license writing to the same person again (rule 1 outranks
rule 3), and it does **not** override a human reply (rule 2 outranks rule 3).

### Where it sits

It is **ANDed** with `collision.account_policy`, never substituted for it.
`collision` answers what the *client's own estate* has done, read from the
provider; this answers what *we* may do next. A `collision` STOP still refuses
whatever this allows. The only widening anywhere in this change is the ISSUE-035
exception, and that sits behind both arms.

### Why it runs at the top of gate 4

Placed after `fatigue` — where it belongs by subject — it was **unreachable**
for every case it exists to decide, for the reason in §0.2. A rule nothing
reaches is `src/stoppedcause.py`, which has classified stop causes correctly
since 2026-09-18 and has no caller on any send path to this day. So it runs
first, and fatigue still runs below it, so nothing it allows escapes fatigue.

**This is a gate-ordering change and it changes which refusal an operator is
shown first.** It is the change in this diff I would most like attacked.

---

## 2. The TASK-275 tests

### They were not where the handoff said they were

Handoff §7 item 2 says *"TASK-275's are written and red."* They were not on
master, and `docs/qwen-tasks/TODO/TASK-275-account-rule-red-tests.md` was still
in `TODO`. The work exists on branch **`qwen-worker-2-r9`**, commit
**`e37f9359`**, which also moved the task file to `RUNNING`. Nothing was ever
in `REVIEW`. I brought the test file into this branch with
`git checkout qwen-worker-2-r9 -- tests/...`; no merge, no push.

**All 19 now pass.** (The commit message on `e37f9359` says 17; it is 19.)

### The one change I made to their file, and it was not an assertion

TASK-275's `_add_confirmed_touch` recorded **`push_prepared`** and called it *"a
confirmed send in the event log."* It is not one, and `src/touch.py` says so by
name:

> `push_prepared` — a payload was built. A payload is not a send. … in this
> build every payload is constructed and none is sent, so treating it as
> evidence would make *every* planned touch look like it had happened. It is
> the single most dangerous near-miss in the vocabulary and it is excluded by
> name.

`push_prepared` also occurs **zero times** in the 28,262 events of
`work/queue.jsonl`, so it was not a shape the real store carries either.

I changed the fixture helper to emit `push_marked` — one of the three
confirming events the rest of the system trusts — and **changed no assertion**.
Run against the rule as written, the original fixture left 7 tests failing and
3 more (`day 5`, `day 10`, `day 12`) **passing vacuously**: with nothing in the
log every account reads as untouched and every verdict is a first-persona
ALLOW.

**This is the single item I most want GLM to check.** The instruction was to
report a disagreement rather than edit, and editing a fixture is not editing an
assertion — but it is still an edit to somebody else's red test, and the
argument above is the whole justification.

### Where I think TASK-275 is wrong and did NOT change it

`TestThirdPersonaStaggers`'s docstring says *"the 7-day gap is measured from the
SECOND persona's first touch"*, and its own assertions contradict that. The
day-11 case has the second persona touched 11 days ago and asserts REFUSE;
11 ≥ 7, so under the docstring it should ALLOW.

The reading that satisfies **every** assertion in the file is *cumulative gap
since the most recent confirmed touch at the account*: 5 days before a second
persona, 5 + 7 = **12** before a third. That is what `REQUIRED_GAP_DAYS`
implements and it fits "a third after 7 more days" as naturally as the other
reading. The assertions stand unedited; the docstring is wrong.

**This is an operator question, not a code question:** does "a third after 7
more days" mean 12 days of silence, or 7 days after the second persona was
contacted? I took the reading the tests encode. If it is the other one, the
change is one number in `REQUIRED_GAP_DAYS`.

---

## 3. Every test goes RED when its fix is removed — verified, 13/13

Mutation harness, one arm removed at a time, both modules re-run, the file
asserted changed on disk before anything ran (a no-op patch reporting OK is its
own failure mode). `src/` verified restored afterwards.

| mutation | tests that went RED |
|---|---|
| same contact twice: never refuse | 3 |
| human reply at the account: ignore it | 8 |
| unsubscribe: read as an ordinary reply | 1 |
| unclassified reply: treat as automated | 1 |
| stop at the account: never hold | 7 |
| ISSUE-035 arm 1: call every stop ours | 1 |
| ISSUE-035 arm 2: call every stop operator-recorded | 2 |
| LinkedIn reply state: claim always readable | 1 |
| second persona gap 5 → 4 | 2 |
| third persona gap 12 → 7 | 2 |
| persona cap → allow a fourth | 1 |
| count planned payloads as sends | 1 |
| unhook the gate from `executionguard` | 17 |

**The twelfth started as a hole.** Flipping
`account.touches(confirmed_only=True)` to `False` left all 51 tests green —
the most dangerous mutation available, since it would make every account with
drafted copy read as worked and the rule would refuse the estate while
reporting that it was staggering it. `APayloadIsNotASend` (4 tests) now pins
it, including the direction that matters most: a 400-day-old `push_prepared`
must not age an account whose confirmed touch is one day old.

Harness: `scratchpad/mutate.py` (gitignored; reproduce with
`py -3 scratchpad/mutate.py`).

---

## 4. Measured against the real store — `work/queue.jsonl`, 1,582 records

Two passes, because only reporting one would be a lie by omission.
1,581 accounts and 1,064 contacts evaluated; the operator's test identity
(`crosschannel-stop-test-2026-09-23` / `zvonimir-beslic`) excluded.

### Pass 1 — the local event log alone, which is what the gate sees today

**27 contacts refused, at 19 accounts.**

| rule | n |
|---|---|
| `account_answered` | 19 |
| `account_stopped` | 7 |
| `same_contact_twice` | 1 |
| *(ALLOW `first_persona`)* | *1,037* |

Accounts refused: amarketforce.com, brunetgarcia.com, casselteam.com,
ciwebgroup.com, deltadiversified.net, donovanadv.com, hotsoupgroup.com,
ifstudiony.com, naperville.net, odonnellco.com, olv.global, ptimesports.com,
storybrand.com, studionorth.com, terrisandy.com, thresholdagency.com,
truedigital.co.uk, tsroofingsystems.com, wearebond.com.

Note `deltadiversified.net` and `truedigital.co.uk`: one person replied and the
rule correctly stops **three** and **four** colleagues respectively. That is
the rule doing the job it exists for.

### Pass 2 — with the provider's confirmed sends replayed

`work/stage/pc-lead-sends.jsonl`, status `sent` with a `sent_at`, joined on
`bison_lead_id`: **2,319 send rows** replayed onto the records.

**182 contacts refused, at 150 accounts.**

| rule | n |
|---|---|
| `same_contact_twice` | 150 |
| `stagger_gap` | 14 |
| `account_answered` | 12 |
| `account_stopped` | 5 |
| `persona_cap` | 1 |

**The gap between the passes is the finding: 27 → 182 contacts, 19 → 150
accounts. 131 accounts are only refused once provider truth is visible.** The
local event log holds **one** `push_marked` event in the entire store; the
provider holds 2,319 confirmed sends across 1,313 leads. The local log does not
record sends.

### The 14 the operator should look at before this afternoon

These are second personas whose account was touched **inside the five-day
window**, and they are precisely the batch this gate governs:

| account | contact | gap |
|---|---|---|
| hyphametrics.com | joanna-drews | 1.6 d |
| bluleadz.com | eric-baum | 2.5 d |
| dksmo.com | joel-dickstein | 2.5 d |
| intmar.com | david-rouff | 2.5 d |
| sobepromos.com | sobe-conciergeserviceintl | 2.5 d |
| liveanimations.org | egor-pavlenko | 2.6 d |
| mortaragency.com | mark-williams | 2.6 d |
| smartliteusa.com | paul-lauro | 2.6 d |
| smithkroeger.com | kelli-zieg | 2.6 d |
| smithkroeger.com | terry-kroeger | 2.6 d |
| whalar.com | jo-cronk | 2.6 d |
| swishad.com | bill-davidson | 2.7 d |
| icleanse.com | greg-reilly | 2.8 d |
| leadmemedia.com | jeff-grady | 2.8 d |

Plus one `persona_cap`: **danitesign.com / jennifer-bender**, a fourth persona
at an account where three are already contacted.

Script: `scratchpad/measure.py` (gitignored, read-only).

---

## 5. Timing, and whether `last_touch` is still on this path

**Handoff §7 item 1 verified independently and it holds.** Lead 133283 reads
`2026-06-05T01:17:12Z` in `work/stage/last-touch.json` while its last confirmed
send is `2026-09-22T19:40:34Z` from campaign **491** — our own. The cache is
**109 days** stale on that lead.

**`last_touch` is NOT read on the send path.** `work/stage/last-touch.json` is
opened only by `scripts/reengagement_inventory.py`; nothing in `src/` opens it.
`src/fatigue.py` and `src/eligibility.py` derive their gaps from confirmed
events. `src/account.py:324` *writes* `last_touch_at` into the derived account
graph; the consumers of that are reporting.

**One read on a selection path is worth fixing and is not mine:**
`src/nightlysourcing.py:486` does `rec.get("last_touch_at") or
rec.get("updated_at")` — and **nothing in `src/` or `scripts/` ever writes
`last_touch_at` onto a queue record**, so that read always falls through to
`updated_at`. It is ISSUE-041's shape on the sourcing path.

`src/account_rule.py` reads neither. `TheCacheIsNotConsulted` pins it three
ways, including a source-level assertion that the field name never appears —
stated as source precisely because the behavioural tests would also pass if the
field were read and merely happened to agree.

### What I could NOT deliver on the "read from the provider at decision time" bar

**There is no decision-time provider read in this codebase that returns a
last-send TIMESTAMP.** `collision.check_account` → `collision.touches_of`
returns `emails_sent`, `replies`, `opens` and per-campaign status — **counts,
no `sent_at`**. The only timestamped source is the staged snapshot
`work/stage/pc-lead-sends.jsonl` (written 2026-09-24 20:27), which is a cache
by any honest definition.

So: **the stagger's gap is computed from the local event log, which is nearly
empty of sends.** That is why pass 1 finds 0 `stagger_gap` refusals and pass 2
finds 14. Closing it needs a per-lead sends read added to `src/providers/bison.py`
— a file I am forbidden to touch — and is the largest outstanding piece of this
work.

**What does hold today:** "the same contact is never contacted twice" is already
enforced against decision-time provider truth by the *existing*
`collision.check_address`, which returns `TOUCHED` when `emails_sent > 0` and
which `executionguard` requires to be `CLEAR`. My rule's arm 1 is a local
backstop to that, not the primary. **For LinkedIn there is no such backstop**,
which is §6.

---

## 6. ISSUE-041, and the one number in the brief that was off

The brief says *zero* contacts carry `heyreach_lead_id`. Measured: **exactly
one of 1,065 does** — and it is the operator's own test identity, record
`crosschannel-stop-test-2026-09-23`, contact `zvonimir-beslic`,
`/in/zbeslic`, state `do_not_contact`.

So the substance is not merely right, it is stronger than stated: **among real
prospects it is zero.** LinkedIn reply state is structurally absent, not
empty, and `heyreach_campaign_id` tells the same story (also 1, the same
record).

The rule therefore refuses rather than allows when an account carries a
confirmed LinkedIn touch and no contact there carries the id — `no reply
recorded` there is a fact about our plumbing, not about the prospect. The arm
is deliberately narrow: an account with **no** LinkedIn touch is not refused
for this, or the whole email estate would be.

---

## 6b. The referral conflict — found while reviewing, not yet decided

The operator's rule says *any reply at the account stops all others*. The
codebase already holds a documented exception to that, and I did **not** build
it in, because building it would widen who gets contacted and that is the
operator's call rather than mine.

`src/accountpolicy.py:126` — `reply.activate_referred_contact`, default
**CONTINUE**:

> *"A referral is an explicit escalation: the referrer said 'talk to B', so B
> is activated. Only that one person, and only because the referrer named
> them."*

**My rule refuses B.** A referred contact sits at an account that has, by
definition, just answered — so `account_answered` or `account_stopped` fires
and the gate blocks the one person the referral policy exists to let through.

How live is this today, measured:

- **Zero** `referred_contact_activated` events exist in the store, so nothing
  is actually being blocked right now.
- **8** `referral_mentioned` events exist. Seven are `candidate` or `unknown`
  with `needs_a_person: True` — a human decides, and no automatic activation
  is at stake.
- **One is an exact match**: `olv.global`, `anita-rozentale`'s reply names
  `referred_contact: liga-rolava`, `needs_a_person: False`. My gate refuses
  `liga-rolava` under `account_stopped`. That is the case that will bite.

**Decision needed:** does "any reply stops all others" outrank
`reply.activate_referred_contact`, or is a named, exact-match referral the one
reply that does not stop the person it names? The rule as written takes the
first reading — the conservative one — and refuses. If the second is wanted it
is a narrow arm: allow a contact that is the `referred_contact` of an
`exact_match` `referral_mentioned` event, and nothing else.

---

## 7. What I could not verify, and what I got wrong

- **Three of the five "READ FIRST" documents do not exist.**
  `docs/DECISIONS-2026-09-25-OPTION-A-AND-THE-FREE-CRAWL.md` is absent;
  **ISSUE-041 through ISSUE-045 are absent** — `docs/state/PROBLEM-REGISTER.md`
  tops out at ISSUE-037. `ACCOUNT-OUTREACH.md` is at the repo root, not under
  `docs/`. Everything I say about ISSUE-041 comes from my own measurement of
  the store, not from a register entry, and ISSUE-042..045 I know nothing
  about — **if any of them bears on this gate, I have not accounted for it.**
- **I could not reproduce "145 of 2,081 rows staler than the live lead."** On
  the snapshots in `work/stage` as of now I measure **26 of 1,313** overlapping
  leads with a cache older than the live last send, worst by 109 days (the
  handoff says 111). The 109-day lead-133283 finding reproduces exactly; the
  aggregate does not, and I do not know which denominator produced 2,081. I
  report my number rather than repeating one I could not reproduce.
- **The 5/12-day reading of the third-persona rule is my interpretation**
  (§2). It satisfies every TASK-275 assertion, but the task's own docstring
  says something different. An operator should settle it.
- **The `is_automated` boundary is inherited, not verified by me.** I trust
  `replies.is_automated` and its `AUTOMATED_CATEGORIES`
  (`out_of_office`, `automated`, `assistant_redirect`). If that classification
  is wrong for a given reply, this rule lets a second persona through. Note
  `tmgroup.com / robert-ross` in the live store is classified `automated` — the
  rule would allow a colleague there.
- **`reply_received` without a classification is treated as a human reply.** I
  believe fail-closed is right; it will refuse accounts whose classifier simply
  has not run yet.
- **The gate-ordering change (§1) is the riskiest line in the diff.** It moves
  the account rule above `eligibility`, `suppression`, `copy`, `claims` and
  `fatigue`. No gate was removed and nothing it allows escapes those gates, but
  refusal *attribution* changes and some existing test may reasonably depend on
  which gate spoke first. The suite result is in §8.
- **I did not measure the LinkedIn/HeyReach side against the provider at all.**
  No provider writes were made and no HeyReach read was attempted.

---

## 8. Suite

One full pass, `py -3 scripts/run_suite.py --offline`, diffed **by name** in
both directions against `docs/state/SUITE-BASELINE-2026-09-23-MERGED.json`
(170 named entries, runner `py -3 -m tests.offline`, taken at `0d6ed72c`).

<!-- SUITE RESULT -->

---

## 9. Files

| file | change |
|---|---|
| `src/account_rule.py` | **new** — the rule |
| `src/executionguard.py` | +1 import, +1 gate at the top of gate 4, comment at the old `account_collision` site |
| `tests/test_the_account_rule_staggers_rather_than_blocks.py` | **from `qwen-worker-2-r9`**; one fixture helper changed, no assertion changed |
| `tests/test_the_account_rule_refuses_the_send_itself.py` | **new** — 36 effect tests |

**Lane collisions:** none taken. I avoided `src/bisonfactory.py` (lanes B and
D) and `config/clients/productive.yaml` (lane B) entirely — §0.1 and §0.2 are
the two places where that avoidance leaves work undone, and both are named so
the owning lane can finish them. `src/executionguard.py` is, as far as I can
see, claimed by nobody this morning.

No provider writes. No edits to `config/.env`, `src/providers/*`,
`scripts/*_watch_loop.py` or `work/`.
