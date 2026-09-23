# Merge request — Phase D4: account status, and the witness that was blind

## THE DECISION THIS IS BUILT ON — READ THIS FIRST

**OPERATOR, 2026-09-23**, verbatim:

> Provider-confirmed sends, bounces, replies and HeyReach requests/accepts
> are written back into the local event ledger by the watchers on every
> readback (idempotent per provider row id), so account status and
> accounts-first reporting are computed locally from the ledger, with the
> provider as a periodic second witness, never as a per-account call.
> **Production owns the write-back; the agent reads the ledger.**

**Production owns the write-back. This branch does not contain it, and
cannot: `src/providers/*` and the watch loops are not this session's.**

What this branch does is make the agent side correct on both sides of that
change:

- It reads the **ledger** and nothing else per account. An earlier version
  of this increment walked the campaign queues per account — it answered
  correctly and it is exactly the shape ruled out above, so it is **gone**,
  and a test asserts the function no longer exists so it cannot be quietly
  reintroduced.
- It asks **one** question per workspace per ten minutes — *is the ledger
  recording sends yet?* — and caches it. Fifty accounts cost one provider
  read, asserted by test.
- Until the write-back lands, it **withholds `untouched`** rather than
  asserting it. See §1: the ledger currently holds 1 confirming event
  against 494 provider-confirmed sends.

**So the agent goes quiet on most accounts until production ships the
write-back, and loud the moment it does.** That is deliberate and it is the
same pattern as the follow-up offer, which stays switched off until its
deliverer beats. A tool that answers confidently from a ledger nobody is
writing is the failure this whole document is about.

**What production needs to do for this to light up:** write the four event
kinds back on every readback, idempotent per provider row id, using the
event types `touch.CONFIRMING_EVENTS` already names — `push_marked`,
`email_delivered`, `linkedin_connected` — plus `reply_received` /
`reply_classified`, which already exist and already work. Nothing here needs
a new event type or a schema change.

---

**For the production session.** Branch `slack-agent` at `18b7c068`, pushed
and verified against the remote. Not merged, not pushed to master.

The operator's additive item 2: *"'what is happening with `<domain>`'
returns the account status (untouched / sequenced / engaged / replied /
meeting / won / lost / do_not_contact), the personas in play with their
step, last touch, replies by class, and next planned touch; client-scoped in
client channels. Build it on the account status object as production lands
it; until then derive from provider truth and the ledgers and label the
source."*

**Stacked on D3** (`b428fea9`), which is stacked on **D2** (`edb9146f`,
now merged — thank you). Take D3 and this together or in order.

## 0. WHAT THIS TOUCHES THAT IS YOURS

    nothing

    src/slackagenttools.py    account_status, _ledger_carries_sends, _account_state
    tests/test_what_is_happening_with_this_account.py   NEW, 47 tests

---

## 1. THE FINDING, AND IT IS THE REASON TO READ THIS ONE

**`account.graph()` cannot see this estate's sends.** Counted on the live
store this afternoon, against 494 provider-confirmed sends the day before:

    push_marked           1
    email_delivered       0
    linkedin_connected    0
    reply_received       11

`account.py` builds every touch from `touch.CONFIRMING_EVENTS`, which is
exactly those three. Its own docstring calls it *"the canonical answer to
every account-level question, and every screen, claim resolver and fatigue
check reads it rather than walking the event log again"* — and on this
estate it answers `untouched` for accounts we emailed.

The first draft of this tool did exactly what the docstring told it to, and
over 400 live records returned:

    399 untouched · 1 sequenced

on a workspace that emailed 494 people the previous day. **Telling a client
nothing has happened on an account we wrote to yesterday is the worst
version of the confidently-empty failure**: it is confident, it is
client-facing, and nothing errors.

**This is not a defect in this increment; it is a defect this increment
found**, and it is bigger than this tool. Anything reading `account.graph()`
for "has this account been contacted" is currently wrong on this estate -
every screen, claim resolver and fatigue check the docstring names. The
operator has since decided the fix, and it is at the top of this document:
the watchers write the sends back, and the agent reads the ledger.

---

## 2. SO THE PROVIDER IS A PERIODIC WITNESS ON THE LEDGER ITSELF

`_ledger_carries_sends(slug)` asks one question for a whole workspace and
caches the answer for ten minutes: **does the ledger hold anything like the
number of sends the provider is reporting?**

It is deliberately **not an equality**. The ledger counts touches on this
workspace's records and the provider counts sends on its campaigns; they are
close relatives, not the same number. What is being detected is the ledger
being *empty* against a provider that is plainly sending — **1 against 494**,
not 480 against 494.

**`None` is not `False`.** A witness that could not be asked has not
reported a problem, and treating an unreachable provider as a broken ledger
would degrade every answer on a transient outage.

### 2a. What the verdict licenses, and what it does not

The witness **only ever licenses the absence of evidence**:

- Ledger has a touch → answered, whatever the witness says. Evidence present
  beats evidence missing.
- Ledger empty, witness `True` or `None` → `untouched`.
- **Ledger empty, witness `False` → no status at all**, with an error
  naming the write-back. In a client channel `untouched` there would be a
  guess dressed as an answer, about an account we may well have emailed
  yesterday.

### 2b. What that means live, today, and it is not comfortable

Run over the live estate this afternoon, before the write-back exists:

    60 accounts sampled   ->   60 unanswerable
    12 accounts in the whole workspace carry a touch or reply in the ledger
       -> those 12 answer: 1 sequenced, 8 replied, 3 do_not_contact

**The tool is nearly silent until production ships the write-back.** That is
the honest consequence of the decision, not a defect in it: the alternative
is the per-account queue walk that was removed, and the alternative to
*that* is telling a client `untouched` about an account we wrote to.

---

## 3. THE VOCABULARY IS NOT ALIASED ONTO `account.py`'s

`src/account.py` carries ACTIVE / ENGAGED / PAUSED / SUPPRESSED / STOPPED /
NOT_STARTED. That answers *may we write to this contact*. The operator's
eight are a commercial progression for a whole account. **They share two
words and mean different things by both**, and aliasing them is how a screen
comes to say `engaged` about an account nobody may contact.

Precedence, strongest first, each one a judgement rather than a lookup:

    do_not_contact  >  meeting  >  replied  >  engaged  >  sequenced  >  untouched

**`do_not_contact` outranks `meeting` deliberately.** It answers "what may we
do next", not "how far did this get". An account that met us and then asked
to be left alone is an account we may not write to, and ranking the meeting
above that is how a good outcome becomes a reason to ignore a stop.

`engaged` means something **short of a reply** — a LinkedIn touch that
landed with nobody writing back. Without that it collapses into `replied`
and one of the two words stops meaning anything.

### 3a. `won` and `lost` have no source and are never returned

Nothing in this tree records a deal. The meetings ledger is hand-fed and
stops at the meeting. The answer carries `states_without_a_source` and says
so in its note, because **from the outside a state that never appears looks
like a thing that never happens.**

---

## 4. THREE SHAPE BUGS, ALL FOUND BY READING

Same family as everything else this session has reported, and worth listing
because the pattern is now four days old:

- **`slackmeetings.by_domain()` returns a LIST**, one row per meeting, not a
  count keyed by domain. Read as a mapping it raises, the raise is caught,
  and `meeting` becomes a state the function can never return — silently, on
  the happy path.
- **`graph()["contacts"]` is a LIST**; `by_contact` is the mapping.
  `.values()` on it raises and every account comes back unreadable.
- **A `touches_attempted` field I wrote could never differ from
  `touches_confirmed`**, because every event `account.touches()` yields is a
  confirming one. A field that cannot vary is a claim nobody can check. It
  is gone, replaced by an explicit limit: **a held step and a step not yet
  due look identical here.**
- **`account.replies()` returns one row per EVENT, not per reply** — it
  answers "what is on this record". `reply_received` and `reply_classified`
  are both on it for the same reply, so a naive per-class count doubles
  every classified reply and invents an unclassified one. Live:

      olv.global   {'unclassified': 1, 'out_of_office': 1}

  for a single out-of-office — **two replies, one apparently unlooked-at,
  both halves false, and it would have reached a client channel.** Fixed by
  counting the receipt only when nothing classified it; re-run live, all
  twelve accounts now show one reply with its real class. **Any other caller
  counting `len(account.replies(rec))` as a reply count has this bug**, and
  that is worth a grep on your side.

A fixture that mocked `graph()` would have hidden the first two. The tests
use **records in the store's shape** and run the real `graph()`.

---

## 5. THE TESTS

**47, and the ones that matter are the live-shaped ones.** Each of the six
reachable states is produced from a record rather than asserted about a
constant; the precedence is tested including `do_not_contact` over
`meeting`; the provider leg is tested for all four combinations of
local/provider evidence; and the client-scope property is tested
**word for word** — another client's domain and a domain nobody has must
return the identical note, because the difference between them is the leak.

**319 slack tests green.** `test_the_account_is_the_unit_of_outreach` has 3
failures; all 3 are in the 71/35 infra baseline and predate this. I did not
touch that baseline.

---

## 6. STILL YOURS

New, and the first is the only one that matters:

- **Ship the write-back.** Everything above is switched off until it exists:
  the four event kinds, idempotent per provider row id, on every watcher
  readback. No new event types and no schema change — `push_marked`,
  `email_delivered`, `linkedin_connected`, `reply_received` /
  `reply_classified` all already exist and already work. **Accounts-first
  reporting (additive item 3) is waiting on the same thing**, and it is
  waiting for a stronger reason: a report wants these counts across a whole
  workspace, and with a blind ledger every account in it is unanswerable.
- **`next_planned_touch` is refused rather than guessed.** It lives in the
  provider's queue and `weekly_plan` already answers it honestly with a
  three-day horizon, because that is as far as the provider answers. Wiring
  it into this answer means repeating that horizon caveat in a second place;
  say if you want it there.
- **When production's account-status object lands**, `_account_state` is the
  one function to replace, and `source.not_production_account_status_object`
  is the flag that should stop being true.

Carried forward: `docs/SLACK-AGENT-HANDOFF-2026-09-23-MORNING.md` §7, less
the items now done. **`scripts/slack_followup_loop.py` has still never been
started**, so D3's feature is switched off by construction.
