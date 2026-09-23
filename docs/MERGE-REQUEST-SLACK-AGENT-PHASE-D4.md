# Merge request — Phase D4: account status, and the witness that was blind

**For the production session.** Branch `slack-agent` at `0e8133a8`, pushed
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

    src/slackagenttools.py    account_status, _provider_touches, _account_state
    tests/test_what_is_happening_with_this_account.py   NEW, 39 tests

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
for "has this account been contacted" is currently wrong on this estate —
every screen, claim resolver and fatigue check the docstring names. **Whether
the sends should be written back into the event log is production's call**,
and it is the thing worth taking from this document.

---

## 2. SO THE PROVIDER IS THE SECOND WITNESS

Which is what *"derive from provider truth"* means.
`_provider_touches(slug, emails)` matches the account's contact addresses
against the campaign queues — through `readback.queue`, so it carries D2's
page cap — and counts rows the provider says were **sent**. `sent_at` is the
witness, never membership: enrolled is not sent.

Re-run live after the change:

    28row.com   untouched  ->  sequenced
                provider sends: 1
                "the provider confirms 1 send(s) to this account and the
                 local event log carries none"

**The disagreement is reported, not smoothed over.** Quietly preferring the
provider would hide a writer that has stopped writing.

### 2a. Unreadable is never zero, in both places

- `_provider_touches` returns **`None`** when queues refused and nothing was
  found — not `[]`. A campaign nobody could read is not a campaign that sent
  nothing.
- An account with no local touch **and** an unreadable provider returns **no
  status at all**, with an error. `untouched` there would be a guess dressed
  as an answer, in a client channel.

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

A fixture that mocked `graph()` would have hidden the first two. The tests
use **records in the store's shape** and run the real `graph()`.

---

## 5. THE TESTS

**39, and the ones that matter are the live-shaped ones.** Each of the six
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

New, and the first is the important one:

- **Decide whether provider sends should be written back to the event log.**
  Until they are, `account.graph()` is blind on this estate and this tool is
  carrying a provider call per account to work around it. That cost is
  acceptable for one-domain questions and **will not scale to a report**,
  which matters for the operator's additive item 3 (accounts-first
  reporting) — that wants these counts across a whole workspace.
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
