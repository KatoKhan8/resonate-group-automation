# Merge request — the write ledger, the resume verb, and one log per watcher

Branch `infra`, 2026-09-24 night. Production merges and measures the
email → LinkedIn direction live.

**`src/providers/heyreach.py` IS UNCHANGED.** The one-function grant was not
used, and §1 is why.

---

## 0. THE HEADLINE

Three items were asked for. **The first was already built**; the second and
third were real and are done.

    1  heyreach.stop_lead behind route-scoped allow_writes   ALREADY BUILT
    2  pause/resume through perform, always a ledger row      DONE
    3  one log file per bison watcher                         DONE

---

## 1. ITEM 1 WAS ALREADY BUILT, AND THE GRANT IS UNUSED

`providerwrites.LINKEDIN_STOP_LEAD` **is** the string `"heyreach.stop_lead"`.
It is a *verb in the write layer*, not a Python function name, and it already
exists, is in `SUPPORTED`, and has been since 2026-09-23. The whole chain is
wired:

    inbound._stop_one
      └─ providers.allow_writes(only=STOP_ROUTES)     route-scoped
           └─ leadstop.stop_linkedin_contact
                └─ providerwrites.perform("heyreach.stop_lead", …)
                     └─ heyreach.stop_lead_in_campaign   the transport

`STOP_ROUTES` is `("stop-future-emails", "stopleadincampaign")` — the reply
path can stop on either channel and nothing else.

**Adding a Python function called `stop_lead` would have made
`heyreach.stop_lead` mean two different things** — a verb and a function —
and put a second name on `stop_lead_in_campaign`. That is the drift this
repository has paid for twice this week already, in two monitor tables and
two heartbeat mechanisms. So the grant went unused and `src/providers/` is
untouched.

### What WAS missing, and is now fixed

**`tests/test_the_reply_path_may_stop_and_nothing_else.py` had two guards
that could not fail for the right reason.** They read
`inspect.getsource(inbound._stop_at_provider)` and grepped it for
`"allow_writes"` and `"STOP_ROUTES"`. The scope later moved into
`_stop_one`, where the per-channel work happens — so **both have been failing
ever since, carried in the suite baseline as accepted failures, while the
behaviour they were written to protect was correct the whole time.**

That is worse than a false alarm. A guard that fails for a reason nobody
believes gets filed under "known", and then it cannot raise its voice on the
day the scope really does go missing.

They now drive the reply path and ask the running guard what it permits:

    the LinkedIn stop is permitted where the work happens
    the email stop is permitted where the work happens
    and NOTHING else is — enrol, pause, resume, create all refused
    the scope does not outlive the reply

**Mutations, both killed:** widening the grant (`only=STOP_ROUTES` removed)
and breaking the `allow_writes` call. This also removes a baseline failure.

---

## 2. EVERY WRITE LEAVES A ROW — A REFUSED ONE MOST OF ALL

### 2a. What was true before

`providers._log_refusal` wrote the **refusals** and nothing wrote the
successes. `work/provider-write-refusals.jsonl` grew only when the system
said no, and a write that worked left no trace anywhere. **An audit that
records one half of a decision cannot answer "what did this process do",
which is the only question anybody asks it.**

`perform` now writes one row per call — refused, failed, unverified,
verified — to `work/provider-writes.jsonl`.

It is a **wrapper** rather than a line per exit, deliberately: `_perform`
refuses in eight places and returns from two, and a ledger written at each of
them loses a row the next time somebody adds a ninth refusal.

### 2b. Resume never reached a provider at all

`orchestrator.resume` cleared the local pause, wrote a local event, and
**never told the provider**. A resumed campaign read RUNNING locally while
EmailBison still had it paused — and because `perform` was never called,
there was no ledger row anywhere to notice the divergence. The LinkedIn side
was worse: it did nothing and said nothing, which is indistinguishable from
a resume that worked.

It now goes through `perform` per channel, in the same shape `pause` uses,
and **does not raise**: a resume that cannot reach the provider is still a
local resume, and losing the local state change would trade a visible
divergence for an invisible one.

### 2c. Both resume verbs are DECLARED AND SEALED

    bison.resume        declared, NOT in SUPPORTED
    heyreach.resume     declared, NOT in SUPPORTED, and no route exists

**Enabling a resume is an operator authorization, not the write layer's to
grant.** Resuming is the verb that puts a paused sequence back in front of
people — a sending action. CLAUDE.md records one such grant already spent:
*"487 WAS RESUMED AND RECOVERED … That grant is now SPENT: do not resume 487
again under any outcome."*

`heyreach.resume` is sealed for a second and stronger reason:
`/campaign/Resume` answers 400 and is deliberately absent from
`heyreach.WRITE_ROUTES` — *"Pause is what lifts it. Resume comes after, or
not at all."* Enabling it needs a route first, which is a separate decision.

**Declaring them sealed is not a half-measure.** A sealed verb refuses *by
name* and leaves a row, which is strictly better than the silence it
replaces. `test_a_resume_leaves_a_row_for_each_channel` is the operator's
test and it passes on refusals.

### 2d. Two defects I introduced and found before pushing

**The bare `except Exception: pass` hid a bug in its own function.** Copied
from `_log_refusal`, it swallowed a `NameError` — `_store` used without being
imported — so **every call raised and not one row was written**. Nothing
failed, because nothing asserted a row *existed*. The only reason it
surfaced is that the test asserts presence rather than absence of a crash.

**And it would have defeated the production barrier.** `store
.refuse_production_write` is what stops a test writing real client state, and
a blanket swallow would have made the busiest writer in the repository the
one that quietly bypassed it. Now only `OSError` is swallowed — a full disk
must not turn a refusal into a crash — and the barrier is called outside the
try.

The barrier is **honoured by not writing the row, not by raising**:
re-raising would turn every `WriteRefused` in an un-isolated test into a
`ProductionStateUnderTest`, which is the ledger deciding the outcome of the
write it was only supposed to record. **A ledger must never change the
verdict it is recording.**

### 2e. The repo's own guard caught the rest

`test_invariants` has a pair of tests that keep a checklist honest: any
module resolving a path from `queue_path()` and appending must be on
`SELF_WRITERS` *and* must call the barrier. It failed within the hour and
named `providerwrites`. Both halves are now satisfied, and
`PROVIDER_WRITES_LEDGER` is in `store.STATE_OVERRIDES` so the ledger moves
with the rest of the state.

---

## 3. FOURTEEN WATCHERS WERE APPENDING TO ONE FILE

`start_monitors.spawn` named the log after the **script** —
`w-{basename(argv[0])}.out` — and every campaign watcher runs the same
`scripts/bison_watch_loop.py`. So 451, 481, 484, 485, 487, 489 and 491–498
all opened `w-bison_watch_loop.py.out` in append mode: **fourteen processes
interleaving into one handle, with nothing in a line saying which campaign
wrote it.**

The cost is paid exactly when the file is needed. **497 is where the blank
emails were found, by a person reading logs.** Separating one campaign's
lines out of a shared file while thirteen others write into it is the
difference between a log and a pile.

It is now `w-{monitor name}.out`, sanitised so a name can never escape
`work/`.

**A mutation found a gap in my own tests here.** They called `log_path`
directly, so reverting the fix *inside* `spawn` left every one of them green
— and the call sites still read `spawn(argv, name)`, so the source check
passed too. There is now a test that drives `spawn` with the process
creation stubbed and reads the path off the handle it actually opened. That
mutation now fails.

---

## 4. VERIFICATION

    tests/test_a_resume_leaves_a_ledger_row.py         15   NEW
    tests/test_each_watcher_has_its_own_log.py          6   NEW
    tests/test_the_reply_path_may_stop_and_nothing_else 17   rewritten
    tests/test_invariants.py                           85
    tests/test_the_write_layer_is_sealed.py
    tests/test_no_write_happens_without_every_gate.py
                                                      ----
                                                      228 run, 227 pass

The one failure is `test_invariants.TestNothingCanSend
.test_emailbison_posts_only_to_routes_it_declares`, which needs a real
`work/` and **is in the committed baseline**. Two baseline failures are
REMOVED by this change (the two stale source-text guards in §1).

**Mutations: seven run, six killed.** The seventh — a no-op control — did not
apply and is reported as not applied rather than as a survivor.

---

## 5. FOR PRODUCTION, BEFORE YOU MEASURE

- **`bison.resume` is sealed.** Measuring a live resume needs it added to
  `SUPPORTED`, which is your authorization and not mine. Until then a resume
  changes local state, refuses at the provider, and leaves two ledger rows
  saying so.
- **The email → LinkedIn direction is the one to measure**, and it is
  unchanged by this merge — it was already wired. What changed is that you
  can now *see* it: every attempt leaves a row naming the verb, the campaign
  and the outcome.
- **`work/provider-writes.jsonl` is new** and will grow on every write. It is
  gitignored with the rest of `work/`.
