# MERGE REQUEST — CheapVerifier provider and the new S5 order

**Lane Q.** Branch `worktree-agent-a9fe2f7a7ad9343aa`, rebased on master
`76f29779`. Own branch, not merged, not pushed by this lane.

**HEAD sha is recorded at the foot of this document**, after the final commit.

---

## 0. THE HEADLINE, BEFORE ANYTHING ELSE

**The 12,407-address run did not happen, and it must not happen today.**

Productive's declared `per_day` ceiling is **5,000 credits**. The ledger shows
**14,365 credits already committed today**. The ceiling was crossed by 9,365
before this lane started, so `spendledger.check` refuses *one* credit, let
alone 12,407.

```
  spent today     14365  (2026-09-25)
  binding ceiling per_day
  remaining       -9365

  CEILING CHECK: REFUSED
    productive has committed 14365 credit(s) today (2026-09-25) and this
    call expects 12407, which crosses the per_day ceiling of 5000

  AND NOT EVEN ONE CREDIT IS ALLOWED:
    ... and this call expects 1, which crosses the per_day ceiling of 5000

  RESULT: HALTED CLEANLY AT THE PREFLIGHT. SPEND = 0.
```

Nothing was uploaded, no address reached the provider, and no credit was
spent. **No ceiling was raised.**

### The brief's ceiling figure was wrong, and the difference is the whole decision

The task stated `per_day: 15000`, which would have left ~635 credits of
headroom. The config says **5,000**:

```yaml
budget:
  per_day: 5000
  per_run: 2000
  total: 50000
```

`config/clients/productive.yaml:672`, confirmed on rebased master and
confirmed through `spendledger.caps(clients.load("productive"))` rather than
by reading the YAML. Under the stated 15,000 this would have been a small
partial run; under the real 5,000 it is no run at all.

---

## 1. WHAT WAS BUILT

`src/providers/cheapverifier.py` — a production provider module.

| area | what it does |
|---|---|
| stored lookup | `stored()` — free; **404 → `None`**, never an exception, never a verdict |
| single verify | `verify_single()` — paid; handles the 202/poll path |
| bulk | `upload()` / `wait_for()` / `details()` / `settle_and_ledger()` |
| credit rule | `credits_for()` — the single place cost is decided |
| ledger | `reserve()` before, `ledger()` after; `headroom()` for preflight |
| readiness | `check()` — a **free** authenticated probe |
| refusal | `NotConfigured` raised before the wire when unconfigured |

Trimmed dicts only; no raw payload leaves the module.

### The 404 that is an answer

`GET /verify/{address with nothing stored}` answers **404**:

```json
{"error":"Not found","message":"No validation result found for ..."}
```

Measured live, and recorded as a cassette. On a cold cohort this is the
answer for nearly every address. `stored()` returns `None`. Treating it as an
error would make the rung that exists to stop us paying twice into the thing
that breaks the run on the first address.

---

## 2. THE CONTRACT WAS RE-VERIFIED, NOT ASSUMED

`work/cheapverifier-openapi.json` was re-fetched live while this module was
written and compared byte-for-byte with the saved copy:

```
live  bytes 24919  sha256 365e27d9eb29411e6317700f
saved bytes 24919  sha256 365e27d9eb29411e6317700f
IDENTICAL
```

(The brief's "24,879" is the character count; 24,919 is the byte count. Same
document.)

### Two places the live API disagrees with its own spec

Both measured, both cassetted, and both load-bearing:

**1. A wrong key is `403`, not the documented `401`.**

```
no key sent    401  {"error":"API key required"}
wrong key      403  {"error":"Invalid API key"}
```

The spec documents 401 for "Missing or invalid API key". An adapter reading
only 401 as a credential fault would report a bad key as a server error, and
`credential_health` would misclassify it. `auth_failure()` reads both.

**2. The documented error envelope is never sent.**

The spec's `Error` schema promises `{"success": false, "message", "error"}`.
Across **nine recorded error responses on five endpoints, `success` appears
zero times**, and at least four different shapes do:

```
{"error":"Not found","message":"No validation result found for ..."}
{"error":"Task not found"}                        <- no message at all
{"status":"error","message":"Task not found"}     <- different again
{"error":"Validation failed","details":[{...}]}   <- 422, reason in details
{"status":"error","message":"...","code":"EMAIL_REQUIRED"}
```

`message_of()` reads every shape and branches on none of them being
`success`. A test asserts that no recorded body carries `success`, so if the
provider ever starts sending it, we are told.

This also found a real bug during the build: `message_of` originally returned
the top-level `"Validation failed"` for a 422 and never reached the useful
sentence in `details`. Fixed in the code, not in the test.

---

## 3. RATE LIMIT — MEASURED ON THE FREE PATH, NOT ESTABLISHED ON THE PAID ONE

The spec documents **no** rate limit: no 429 on any of the seven endpoints, no
`RateLimit-*` or `Retry-After` header anywhere in the document.

### How it was measured

Against `GET /verify/{email}` — the **free** stored lookup, answering 404 for
addresses that cannot exist (`@example.invalid`), so the entire ramp cost
nothing. Five arms of 40 requests at rising concurrency, halting on the first
429/503:

| arm | requests | throughput | codes | p50 | throttle headers |
|---|---|---|---|---|---|
| K=1 | 40 | 9.4 req/s | 404 ×40 | 0.44 s | none |
| K=4 | 40 | 14.8 req/s | 404 ×40 | 0.44 s | none |
| K=8 | 40 | 18.0 req/s | 404 ×40 | 0.44 s | none |
| K=16 | 40 | 32.1 req/s | 404 ×40 | 0.34 s | none |
| K=32 | 40 | 40.5 req/s | 404 ×40 | 0.52 s | none |

**200 requests, zero 429s, zero throttle headers, p50 flat across a 32×
change in concurrency.**

### What that establishes, and what it does not

It establishes that the **stored-lookup path** does not throttle below
~40 req/s.

It establishes **nothing about the paid endpoints**. `/file/upload` and
`/email-validation` run real SMTP conversations on a different fleet — the
spec says so itself ("when the fleet is slower than the request can wait").
Measuring those costs credits, and the day's ceiling refuses them.

So **`RATE_LIMIT_PAID = None`, and None means UNKNOWN and says so.** An
unknown limit is not permission to pick a number. This repository already
paid 351 minutes for a concurrency sized against a provider the runner was
not calling; `recommended_workers("paid")` returns `None` rather than
repeating that. `recommended_workers("free")` returns 16 — one step below the
measured-clean edge, because a clean arm at K is evidence for K and not 2K.

---

## 4. `/task/details` — VERIFIED AT RUNTIME BECAUSE IT COULD NOT BE VERIFIED LIVE

The operator states, and the spec's text agrees, that omitting `page` returns
every row ("10 rows per page; omit `page` to return every row").

**This could not be confirmed live.** Confirming it needs a completed file,
which needs a paid upload, which the ceiling refuses. What *was* confirmed
live is that the endpoint exists and 404s correctly for an unknown file, and
that the schema does carry `page` / `total` / `totalPages`.

So it is not trusted — it is **checked at runtime**. `details()`:

1. makes the unpaged read;
2. compares the rows returned against the `total` **the same response
   reports** (and against the caller's independently-known count);
3. if they disagree, pages through explicitly;
4. raises `IncompleteRead` rather than returning a half-read.

This is the `/leads` failure exactly — an offset that died at page 1,000 while
`meta.last_page` promised more, and the half-read looked like a complete one.
A verification read that silently returns half a file marks the rest
unverified and re-buys it. Three tests cover it, including one that fails if
the length check is deleted.

---

## 5. CASSETTE PROVENANCE

Ten cassettes in `tests/cassettes/cheapverifier/`, every one produced by
`work/cv/record_cassettes.py`, which **makes the call and saves what came
back**. Each carries a `_provenance` block with the timestamp, the method and
path, and `"real": true`. The test helper refuses any cassette not marked
real, so a hand-written one cannot quietly join them.

| cassette | status | what it pins |
|---|---|---|
| `stored_miss_404` | 404 | nothing stored — the central case |
| `stored_invalid_syntax_422` | 422 | the `details` envelope |
| `auth_missing_key_401` | 401 | no key |
| `auth_wrong_key_403` | 403 | **wrong** key — the spec deviation |
| `task_status_missing_404` | 404 | `{status,message}` envelope |
| `task_details_missing_404` | 404 | `{error}` only, no message |
| `uploads_results_missing_404` | 404 | `{error,message}` envelope |
| `uploads_results_bad_status_422` | 422 | allowed-value list |
| `single_missing_param_400` | 400 | a free 400 on a paid path |
| `openapi_200` | 200 | the contract itself |

Addresses used are `@example.invalid` — a reserved TLD that cannot resolve —
so nothing real is recorded.

**What is deliberately ABSENT:** a 200 from `/email-validation`, a 200 from
`/file/upload`, and `/task/details` for a real completed file. Recording those
costs credits the ceiling refuses. They are **not** faked. Around thirty tests
were green against invented Apify actor ids this week because the cassettes
matched the invention; the paid paths are exercised instead by **constructed**
responses that are labelled as constructed and that test our own guard logic,
making no claim about what the provider sends.

---

## 6. THE NEW S5 ORDER, WIRED

Wired as **roles through `policy_for`**, not as new branching. The existing
`decide()` already produces the operator's order once the roles are set,
which is why this is a config change plus a provider module rather than a
rewrite of the waterfall.

```yaml
verification:
  primary: cheapverifier
  secondary: deliverable
  catch_all: reoon
  accepted_pairs: [cheapverifier+deliverable, cheapverifier+reoon]
```

| rule | where it is enforced |
|---|---|
| 0. stored lookup first, free | `verification.call` calls `cheapverifier.stored()` before any paid rung |
| 1. CheapVerifier first paid | `primary` |
| 2. `invalid` is dropped | `decide()`→INVALID, `verify()` breaks, `needs()` returns False — **pinned by test** |
| 3. Deliverable on valid/catch_all/unknown | `needs(secondary)` — **pinned by test for all three** |
| 4. Reoon third only | `needs(catch_all)` on disagreement / unknown / shortfall |

`accepted_pairs` is a new policy key with a real consumer (`pair_accepted()`),
and both pairs are accepted. **It annotates; it does not gate.** `decide()`
is unchanged, because turning the pair into a refusal would hold leads
today's policy clears, and what was asked for was widening what is *accepted*.
A pair is compared as a **set**, so which provider answered first — a fact
about scheduling, not about evidence — cannot fail a policy the run satisfies.

`clients.parse` carries inline scalar lists but not lists of lists, so a pair
is `a+b` and `pair_accepted` splits it. The same limit keeps the HeyReach
graph in its own file.

### THE MIGRATION CONSEQUENCE — read this before merging

**Every address verified under the old order becomes `held` under the new
one.** `(deliverable, reoon)` was the required pair from 09-21 until today;
the new primary has never answered for any of those addresses, so `decide()`
returns "valid but the primary is missing" and `trust_secondary_when_primary_
unknown` is correctly `False`.

Measured in the S5 journal, deduplicated by address with the latest row
winning — 14,478 distinct addresses, of which **9,107 stand at `verified`**:

| pair that cleared the lead | leads | accepted by the new policy? |
|---|---|---|
| `(deliverable, reoon)` | 8,504 | no |
| `(contactout, reoon)` | 603 | no |
| **total** | **9,107** | **none of them** |

**All 9,107 revert to held**, because not one of them includes the new
primary. They would be re-bought through CheapVerifier — a second full
verification bill for addresses already paid for once.

This is the correct consequence of moving the primary, not a defect — but it
is the single biggest operational effect of the change, it is a second full
verification bill for work already paid for, and it should be an explicit
operator decision rather than something discovered in production. It is
pinned by `test_the_pair_the_client_used_yesterday_no_longer_clears`.

---

## 7. CREDIT ACCOUNTING, RECONCILED AGAINST LEDGER ROWS

### The rule, in one place

`credits_for(outcome)` — keyed on the **outcome**, which is what the provider
bills on:

| outcome | credits |
|---|---|
| `valid` | 1 |
| `invalid` | 1 |
| `catch_all` | 0 |
| `unknown` | 0 |
| unrecognised | 1 (conservative: under-reporting a bill is how a ledger stops being able to refuse) |

**A reservation is never ledgered as spend.** `creditsReserved` is held, not
spent; the file settles to the rows that reached a verdict. `trim_upload()`
deliberately has no `credits` key, only `credits_reserved`, so nothing
downstream can mistake one for the other.

**`billingStatus: "pending"` is chargeable.** A `creditsUsed: 0` alongside
`pending` means "not settled yet", never "free". Pinned by test.

### Check before spend

`reserve()` calls `spendledger.check` **before a request is built**. The two
defects named in the brief — `run_actor` ledgering every Apify call without
checking, and S5's `per_run` crossed at K=8 — are both caps consulted after
the answer arrived, which can only report an overshoot.

### The ledger reconciliation

All figures from `work/spend-ledger.jsonl`, 17,937 rows, 0 unparseable.

| day | ledger credits | breakdown |
|---|---|---|
| 2026-09-24 | 2,404 | deliverable 989, reoon 968, **apify 447** |
| 2026-09-25 | 14,365 | deliverable 7,194, reoon 7,171 |

**Yesterday's 1.98 is reconciled:**

```
verification-only credits (2,404 − 447 apify)  = 1,957
addresses given a live primary call (deliverable rows) = 989
1,957 / 989 = 1.9788  ->  1.98
```

Two things this exposes:

1. **447 of yesterday's 2,404 credits are Apify, not verification.** Anyone
   computing cost-per-address from the day's total gets 2.43 and is wrong by
   23%.
2. **The S5 journal recorded 1,388 decisions on 09-24 but the ledger shows
   only 989 live primary calls.** The gap is resumed addresses that re-used
   stored evidence. The brief warned the runner's counters and the ledger
   disagreed by 18; on this measurement they disagree by rather more, and the
   ledger is the one that settled it — which is the point.

---

## 8. COST PER VERIFIED ADDRESS vs 1.98

**It was not measured, because the run was refused. Reporting a measured
number here would be inventing one.** What follows is a projection with its
assumptions stated.

### The structural arithmetic

Per address reaching the primary, under the new order:

| CheapVerifier says | cv | deliverable | reoon | total |
|---|---|---|---|---|
| `invalid` | 1 | — dropped | — | **1** |
| `valid` | 1 | 1 | only if escalated | **2 (+1)** |
| `catch_all` | 0 | 1 | 1 | **2** |
| `unknown` | 0 | 1 | 1 | **2** |

> **The free outcomes do not save money.** A `catch_all` or `unknown` from
> CheapVerifier costs 0 credits — but it is not a *confirmation*, so the
> address still needs **both** Deliverable and Reoon to reach two, and still
> costs 2. The only real saving in the new order is dropping `invalid` early.

cost/address ≈ **2 − (invalid rate) + (valid rate × escalation rate)**

The system's own forecaster agrees, which is a useful independent check —
`verification.plan()` under the new policy returns:

```
  cheapverifier  1  unconditional  "no stored verdict for this address"
  deliverable    1  unconditional  "a second independent confirmation is required"
  reoon          1  CONDITIONAL    "only if a catch-all is still unresolved"

  exposure: {'expected': 2, 'maximum': 3}
```

and after a CheapVerifier `invalid` it returns an **empty plan, exposure 0** —
rule 2 visible in the forecaster as well as in the runner.

### Sensitivity, against the 1.979 baseline

| CheapVerifier invalid rate | esc 0% | esc 10% | esc 25% |
|---|---|---|---|
| 2% | 1.98 | 2.06 | 2.18 |
| 5% | 1.95 | 2.03 | 2.14 |
| 10% | 1.90 | 1.97 | 2.08 |
| 15% | 1.85 | 1.92 | 2.02 |
| 25% | 1.75 | 1.81 | 1.90 |
| 40% | 1.60 | 1.65 | 1.72 |

**The new order breaks even with 1.98 only when CheapVerifier's invalid rate
exceeds roughly `2% + valid_rate × escalation_rate`.** Below that it costs
*more* per address, because it adds a third provider to a two-provider
waterfall and the free outcomes do not reduce the pair requirement.

For scale: today's S5 run found an invalid rate of **0.26%** (19 of 7,182) —
on a different provider, but on comparable supply. If CheapVerifier's invalid
rate on this cold US cohort is similarly low, **the new order is more
expensive per address than the one it replaces**, and its case has to rest on
accuracy rather than on cost.

**What is owed:** the real number, from a bounded measured run once there is
headroom. A 500-address arm settles it for ~1,000 credits and gives the
invalid rate and the escalation rate directly.

### Cost per address actually CLEARED

Worth separating, since "verified" can mean either:

| day | verification credits | cleared | credits per cleared address |
|---|---|---|---|
| 2026-09-24 | 1,957 | 647 | 3.02 |
| 2026-09-25 | 14,365 | 2,774 | 5.18 |

The 1.98 figure is per address *given a primary call*, not per address
cleared. Both are reported so the comparison is like-for-like.

---

## 8b. THE BUG THAT WOULD HAVE BROKEN THE RUN, CAUGHT BEFORE IT SHIPPED

Worth its own section because everything else looked green when it was still
broken.

`verification.verify()` calls `waterfall.record_step()` for every rung, and
`record_step` enforces `waterfall.require()`, which refuses any provider the
`EMAIL_VERIFICATION` stage does not declare. CheapVerifier was not declared:

```
record_step(cheapverifier) -> REFUSED:
    WaterfallViolation: cheapverifier is not part of the
    email_verification waterfall
```

**The module imported, the policy resolved, the client config parsed, the
live credential check passed, and 36 unit tests were green — and the first
paid CheapVerifier call in any run that passes a record would have raised.**
This is "existence is not function" exactly: the provider existed, and the
consumer that had to accept it did not know about it.

Found by asking the consumer rather than by reading the module.

### The fix, and why it is positioned where it is

`CHEAPVERIFIER` is registered in `waterfall.STAGES[EMAIL_VERIFICATION]` and
in `COST_UNITS` — without the latter the step would ledger `cost_unit:
"unknown"`, which is how a bill stops being attributable.

It is declared **second in the tuple, after ContactOut, not first.** Position
in that tuple does not decide runtime order — `policy_for` does, through
primary/secondary/catch_all — so declaring it second keeps the standing
**"every stage starts with ContactOut"** invariant
(`PROVIDER-ROUTING-POLICY.md`, a PRODUCT priority, asserted by
`test_waterfall_order` and `test_waterfall`) true of this **global** table,
while Productive's own config scopes the actual order to that one workspace.
Putting it first turned three invariant tests red, and the right answer was
to respect the invariant rather than to edit it.

It carries `"is_fallback": False` — the marker the table already provides for
a primary-path step that is not ContactOut — because it is the first provider
asked for the workspace that names it primary, so there is nothing before it
to justify leaving. `may_fall_back()` already states that primary-path steps
need no reason, and `verification.LEDGER_REASONS["cheapverifier"]` is `None`
to match.

**No guard was weakened to achieve this.** Verified after the change:

```
  cheapverifier  ACCEPTED    deliverable  ACCEPTED
  reoon          ACCEPTED    contactout   ACCEPTED
  a fallback with no reason  -> REFUSED (correct)
  cheapverifier is a primary rung, not a fallback : True
  contactout still primary for other workspaces   : True
```

Five tests pin it, including one that fails if the `COST_UNITS` entry is
removed and one that fails if the reasonless-fallback guard is loosened.

---

## 9. A DEFECT FOUND ON THE WAY, AND IT IS THE SAME FAMILY

**`stage_s5_verify.py` consults no durable ceiling and writes no ledger row.**

`verification.verify()` gates *both* the `spendledger.check` and the
`spendledger.record` on `rec is not None`. `stage_s5_verify.py` passes
`config` — precisely so the ceiling can be consulted — but does **not** pass
`rec`. Demonstrated by effect, not by reading:

```
stage_s5_verify-shaped call (rec=None, config passed):
   spendledger.check  calls: 0
   spendledger.record calls: 0
```

And the complementary hole: `spendledger.caps(None)` returns every ceiling as
`None`, which means unlimited, so a caller that passes `rec` but omits
`config` gets a check that always passes:

```
check(client, config=None, cost=20000) -> ALLOWED   <- ceiling is INERT
```

This is a third instance of the family the brief names: a cap that records
and never checks, or checks against nothing. It is **not fixed here** —
`scripts/` S5 changes are outside this lane's authorisation and the fix
belongs with whoever owns that runner — but it is the most likely explanation
for how 14,365 credits were committed against a 5,000 ceiling today, and it
should be treated as P1.

Suggested shape: move the ceiling check out from under `if rec is not None`,
and make `check()` refuse rather than allow when `config` is `None` and a
client is named.

---

## 10. CREDENTIAL REGISTRATION

`CHEAPVERIFIER_API_KEY` added to `config.VARIABLES` (group `providers`,
class `LIVE`) and mapped in `scripts/credential_health.py`. Proven by effect:

```
CHEAPVERIFIER_API_KEY in registry: True
state (verify=True): ('AUTHENTICATION_VERIFIED',
   {'length': 67, 'latency_ms': 310, 'status': 404,
    'note': 'key accepted; stored lookup answered 404 (nothing stored) ...'})
```

**This is the only verifier in the estate whose key can be genuinely proven,
and it costs nothing.** Deliverable and Reoon have no free account endpoint,
so their `check()` can only report SKIPPED — the key cannot be tested without
spending a verification credit. CheapVerifier's stored lookup is a real
authenticated read that costs zero, so `check()` returns a true
`AUTHENTICATION_VERIFIED` rather than "configured, unverified".

No credential value is ever printed, by this module or by the health check.

---

## 11. TESTS

`tests/test_cheapverifier_reads_a_404_as_nothing_stored.py` — **41 tests**,
covering: the 404-is-None rule, the 403/401 split, the absence of `success`,
every real error envelope, the credit rule, reservation-is-not-spend,
pending-is-chargeable, the complete-read guard and its half-read refusal, the
invalid-drop, the pair policy, the unconfigured refusal, the credential
registration, and the rate-limit honesty.

### Regression baseline, by name and not by count

| | failures |
|---|---|
| master `76f29779`, verification-related modules (286 tests) | **1** |
| this branch, same modules + the new file (325 tests) | **1** |

The one failure is the same on both — `test_decide_blocks_a_bounced_address`
— and is **pre-existing on master**, not introduced here.

Six tests did go red on this branch and all six were stale assertions about
the *old* order. None was weakened:

- `test_productive_verification_roles` — updated to the new roles. Its other
  six guards (two confirmations, disagreement holds, silent primary not
  trusted, only Reoon clears a catch-all, defaults untouched) **all passed
  unchanged**, which is the evidence that the change moved roles and nothing
  else.
- `test_approval_uses_the_clients_verification_policy` — the file is about
  the gate asking the *client's* policy rather than the default. Unchanged in
  purpose; the demonstrating pair moved, and a new test pins the migration
  consequence.
- `test_double_verification::TestTheEmailBisonGate` — the fixture estate
  carries `(contactout, deliverable)` evidence, the roles it was built
  against. The verification roles are now **pinned** there exactly as the
  cadence already was, and for the documented reason: a client editing their
  own YAML must not turn this suite red.

Full-suite verdict: **recorded at the foot of this document.**

---

## 12. REDACTION

`work/` is gitignored and all raw probe output stayed there. Every tracked
file this lane wrote or changed — **20 files, this document included** — was
scanned against **every** real value: all 12,407 cohort addresses, their
domains and company names, and every credential in `config/.env`.

**Zero addresses, zero domains, zero credential values** in any of them.

**The filter was proven to fire first**, which is the step that was skipped
the day an IPv4 got through:

```
planted address     -> detected: True
planted domain      -> detected: True
planted credential  -> detected: True
planted THE CheapVerifier key (real case) -> detected: True

files scanned 16, leaks 0
RESULT: CLEAN
```

The first run of that self-test **failed on its own probe**: secrets were
compared case-sensitively against lower-cased text, so a mixed-case
credential could never have matched and the CLEAN would have meant nothing.
Fixed before the result was believed.

Two incidental notes:

- A repository-wide pass found **real client domains from earlier cohorts
  already committed in `docs/`** (`docs/BISON-COHORT-LIVE-2026-09-15.md`,
  `docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md`, and others). Not this lane's
  files and not fixed here, but they are real leaks and somebody owns them.
- Company names in this cohort include ordinary English words and phrases
  ("Create", "Twelve", "Merge", "Wait", "One Source"), so name matching is
  done on word boundaries and only within this lane's files. The three
  phrase matches that remain are all **pre-existing prose on master** —
  `verification.py`'s "two answers from one source share whatever made the
  first one wrong", and the ICP vertical descriptors "Digital Marketing
  Agency" and "Design Studio" in `productive.yaml` — none of them in a line
  this lane wrote, and none of them a leak. A filter that reports thirty
  false leaks is one that gets ignored.

---

## 13. FILES

| file | change |
|---|---|
| `src/providers/cheapverifier.py` | **new** — the module |
| `tests/test_cheapverifier_reads_a_404_as_nothing_stored.py` | **new** — 41 tests |
| `tests/cassettes/cheapverifier/*.json` | **new** — 10 recorded responses |
| `src/verification.py` | roles, `accepted_pairs`, `pair_accepted`, stored-first call path, local-refusal exemption |
| `config/clients/productive.yaml` | the new order and both accepted pairs |
| `src/waterfall.py` | **CheapVerifier registered in the EMAIL_VERIFICATION stage and COST_UNITS — see §8b** |
| `src/config.py` | `CHEAPVERIFIER_API_KEY` registered |
| `scripts/credential_health.py` | mapped to the adapter |
| `tests/test_productive_verification_roles.py` | updated to the new order |
| `tests/test_approval_uses_the_clients_verification_policy.py` | updated pair; migration test added |
| `tests/test_double_verification.py` | verification roles pinned for the fixture estate |

No other provider module was touched. `config/.env` was read, never written,
and no value was printed.

---

## 14. WHAT THE OPERATOR HAS TO DECIDE

1. **The run is blocked by the day's ceiling.** It runs tomorrow, or under a
   ceiling the operator changes deliberately. This lane did not change one.
2. **9,107 already-verified leads revert to held** under the new primary. Is
   re-buying them intended?
3. **The cost case is not yet established.** On the arithmetic the new order
   is likely *at or above* 1.98 per address unless CheapVerifier's invalid
   rate is high. A 500-address arm (~1,000 credits) settles it.
4. **`stage_s5_verify.py` checks no ceiling and writes no ledger row.** P1,
   outside this lane's authorisation.

---

## 15. VERDICT AND HEAD

<!-- FINAL-STATUS -->
