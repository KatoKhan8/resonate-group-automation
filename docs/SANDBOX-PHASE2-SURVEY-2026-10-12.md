# Phase-2 sandbox survey: the real flow, and where the sandbox may touch it

Measured 2026-10-12 on `task-sandbox-phase2-horizon`, base master
`2bf7b8a5`, phase 1 merged in at `963a7d64`.

**The constraint this document exists to honour:** the sandbox observes and
tests the EXISTING flow. It does not reorder it, refactor it or fix it. A
simplified reimplementation that passes would be worse than no test, because
it would prove the harness and nothing else.

An earlier draft of this work did exactly that - `scripts/sandbox_horizon.py`
carried its own `step_due`, its own cadence model and its own reply
generator. It was deleted rather than kept, because every measurement it
produced would have been a measurement of itself.

---

## 0. Verified, not assumed

| claim | how it was checked | result |
|---|---|---|
| sandbox phase 1 is unintegrated | `git merge-base --is-ancestor 963a7d64 origin/master` | **NOT on origin/master** - confirmed unintegrated |
| phase 2 never ran | no `work/sandbox/`, no metrics artefact anywhere | **confirmed never run** |
| the tree was clean enough to work in | `git status --porcelain` | one untracked task file; worked on a branch |

## 1. Two drivers already exist, and this is the central finding

The question the brief asks - *can the flow already be driven through its
existing interface with fake providers and an injected clock?* - is largely
**yes**, and the sandbox should compose what is here rather than add an engine.

### `src/simulator.py` - the prospect-to-send half

Its own docstring states the property that makes it the right seam:

> It computes nothing new about eligibility. Every verdict here comes from the
> module that owns it: `channels` for reachability, `mx` for gateways, `lint`
> for copy, `quality` for personalisation, `eligibility` for the send
> decision, `waterfall` for spend. A simulator that made its own judgements
> would be a second opinion nobody asked for, and the preview would stop
> matching the run.
>
> Nothing here calls a provider, a model, or DNS.

Entry point: `simulate(recs=None, client=None, batch=None, campaign=None, config=None)`.

### `src/replaysim.py` - the reply half

> it feeds a real inbound event through the real inbound path, and then reads
> the record afterwards to check each link in the chain actually moved.

It asserts six links in order: event received, identity resolved, company
paused, cadence suppressed, slack planned (and **not** posted), reporting
recorded. Entry points `simulate(rec, contact_key, scenario=...)` and
`run_all(...)`; `_event_for(..., at=None, ...)` takes an injectable instant.

## 2. The order of business steps, as the code actually runs it

Taken from `simulator.simulate` -> `company_card` -> `contact_card` and the
modules each delegates to.

1. **record scope** - `_records_for(recs, client, batch, campaign)`
2. **company acceptance** - `qualification.verdict` on the record (ICP)
3. **pause state** - paused companies collected before any contact is read
4. **per contact:**
   1. `quality.assess(rec, contact, config)` - personalisation band, which
      reads `_selected()` -> the record's `research` evidence list re-aged
      through `evidence.recheck`
   2. `channels.email_verdict(rec, contact, config, suppressed)` - in this
      fixed order: operator-excluded, unsubscribed, suppressed, no address,
      bounced, MX, then verification
   3. `channels.linkedin_verdict(...)`
   4. `mx.allows_email(contact, config)`
   5. `lint.sendable(contact, lint.policy_for_record(rec))` ->
      `verification.is_sendable`
   6. `duplicates` across the batch
   7. `timeline_for(...)` - the cadence steps, per contact
5. **spend** - `waterfall` reports; `_credit_estimate` totals
6. **approval state** - `_approval_state(campaign, recs, config)`

The reply path then runs through `replaysim`, and the six links above are its
order.

## 3. Exact injection and replacement points

Three, and only three. Everything else is left alone.

| # | what | where | why it is behaviour-neutral |
|---|---|---|---|
| 1 | **the wire** | `providers.set_transport(...)` | the seam already exists for tests. Phase 1 measured the trap: the writer model and the provider calls share ONE transport, so a blanket sentinel kills copy generation too - that is what broke phase 0's first attempt. So the seal is BY HOST. |
| 2 | **the state directory** | `store.use_directory(tmp)` | the seam already exists. Phase 1 also found that `campaigns_path()` needs the `CAMPAIGNS` env override DELETED, because a stale override survives `use_directory` and points campaign state back at production. Asserted separately. |
| 3 | **the clock** | `src/sandboxclock.install()` patches `store.now` | see below |

Plus provider **readbacks** replaced by raisers (`sandboxharness.seal_readbacks`),
because a readback that silently returns a default would report a write as
confirmed with nothing confirming it.

### Why the clock needed a new module, and what it deliberately does not do

There is **no central clock seam** in this repository. Measured: `src/` holds
**102 real-clock reads across 44 files** - 34 `time.time()`, 28
`datetime.now()`, 24 `time.monotonic()`, 12 `date.today()`, 4 `utcnow()`.

They fall into three classes and only one needed anything new:

1. **Business time behind an injectable parameter.** The repository's own
   idiom is `now = now or datetime.datetime.now(timezone.utc)` -
   `senderheadroom.py:189` and `:337` are the pattern, and
   `fatigue.contact_check(rec, key, at=...)` and `fatigue.account_check(at=...)`
   are the ones the holds run through. A caller passing `at=`/`now=` never
   reads the wall clock. **This is the good design that was already here**, and
   it is why the simulated clock reaches the real hold policy.
2. **Business time with no parameter.** `store.now()` (`src/store.py:233`) is
   the canonical one - one function, every stored timestamp. Patching that
   single attribute moves every `at` the run writes.
3. **Real elapsed time, which MUST NOT be faked.** `store.py:268` and `:296`
   use `time.monotonic()` for the queue-lock deadline and `:290` uses
   `time.time()` against a file mtime for lock staleness. Those ask "how long
   have I actually been waiting", and a simulated answer would either spin
   forever or declare a live lock stale. `suitelock.py` is the same. Faking
   these would be a bug, not a feature, and `sandboxclock.REAL_ELAPSED_EXEMPT`
   names them so the omission is visibly deliberate.

`sandboxclock.install()` touches class 2 only, by module attribute rather than
by rewriting `datetime`, precisely so class 3 keeps ticking in real time.
`unpatched_business_clock_reads()` enumerates what is left so the run can
report any unreachable class-1/2 read **as a defect with a file and a line**
rather than quietly producing a wrong answer.

**Default behaviour is unchanged:** `sandboxclock` and `sandboxharness` are
inert until something calls them. Nothing in the production flow imports
either.

## 4. What the fixture must carry, measured by driving the flow

Each of these was forced by a real failure, not guessed.

- `rec["research"]` is a **list** of evidence items, each built by
  `evidence.make(...)` (18 scored fields incl. `evidence_id`). Hand-built
  dicts raised `AttributeError: 'str' object has no attribute 'get'` in
  `quality._selected`.
- `contact["personalization"]["selected_evidence_ids"]` links the contact to
  that evidence, or personalisation quality cannot be computed.
- The cadence key is `rec["cadence_steps"]` (`cadence.CADENCE_KEY`), a list.
  Supplying `rec["cadence"] = {"key": ...}` instead made **every** step report
  *"this step is not part of the configured cadence for this contact"*.
- Record ids are `id` and `key`, not `record_id` and `contact_key`;
  the contact's profile field is `linkedin`, not `linkedin_url`.

### The verification finding, and why it is not a workaround

A `.invalid` address cannot be verified by a provider, and the first run came
back `email_eligible: False, verification_not_sendable`. The naive fix - set
`sendable: true` - **does nothing**, by design:

> `is_sendable` is always **recomputed from the evidence**, never read from
> the stored state. It used to return `stored in SENDABLE_STATES` whenever a
> verification block existed, which made `verification.state` a second source
> of truth: anything that could write that string could make an address
> sendable without a provider ever having said so.

So the sandbox supplies what the providers *would have said*, as evidence:

    contact["verification"] = {"evidence": [
        verification.result("deliverable", verification.S_VALID, email, ...),
        verification.result("reoon",       verification.S_VALID, email, ...)]}

Productive's real policy is primary `deliverable`, secondary `reoon`,
`required_confirmations: 2`, `trust_secondary_when_primary_unknown: false`.
With both, `resolve()` returns `sendable: true, confirmation_count: 2,
confirmed_by: ["deliverable","reoon"]`.

This is fixture data in the same sense as a synthetic name or a synthetic
fact, and the policy is genuinely exercised rather than bypassed - proved by
two controls that both fire:

| control | result |
|---|---|
| one confirmation only | `is_sendable` **False** - `required_confirmations: 2` is real |
| evidence recording a DIFFERENT address | `is_sendable` **False** - evidence is address-bound by construction |

## 5. Pass criterion 1, met

One synthetic contact through the existing flow, one simulated day:

    WIRE SEALED - positive control fired (NETWORK TOUCHED on a deliberate call)
    store -> ...\Temp\sandbox-one-2aevl7r3\queue.jsonl
    clock injected: store.now() = 2026-10-20T06:00:00+00:00
    simulator.simulate() RAN THE EXISTING FLOW
      accepted: True
      email_eligible: False -> verification_not_sendable  (before the fix above)
      linkedin_eligible: True, mode: linkedin_only
      personalization_quality.band: high
    wire calls attempted: 1  (refused)
    production work/ UNCHANGED - asserted

## 6. Open findings about testability, reported rather than worked around

1. **No central clock seam.** 102 real-clock reads, 44 files. The holds and
   the headroom take `at=`/`now=`, which is what makes this phase possible at
   all; anything on the simulated path that does not is a defect and the run
   reports it with a file and a line.
2. **`store.now()` is the only canonical timestamp seam** and it is a bare
   module function. Patching a module attribute is the least invasive option
   available, but a `clock` parameter threaded through `store` would be the
   behaviour-neutral fix. Not done here: it would change the production flow.
3. **`.invalid` addresses cannot reach the email path without synthetic
   verification evidence.** Handled as fixture data above; recorded because it
   means a future sandbox author who omits the evidence will silently measure
   a LinkedIn-only estate and may not notice.
