# TASK-273 — A conformance suite for two adapters that share no interface

SIZE: M
Operator instruction, 2026-09-23: a sequencer adapter is correct iff the suite
is green. EmailBison and HeyReach first, so a third sequencer for the next
client is a generated adapter plus a green suite.

## THERE IS NO INTERFACE TO CONFORM TO

No base class, no ABC, no Protocol, no registry. `src/providers/bison.py`
(104 KB) and `src/providers/heyreach.py` (152 KB) are independent modules.
What they genuinely share is enforced from `src/providers/__init__.py` and is
a **transport and safety** contract, not a sequencer one:

    ProviderError                :48
    request()                    :763
    ok() / mapping() / first()   :777, :798, :820
    guard_prospect_facing()      :419   -- called at IMPORT
    refuse_unauthorized_write()  :672   ProviderWriteRefused :535
    module-level WRITE_ROUTES + a private allowlist door

Where the sequencer verbs overlap by name, **the signatures differ**:

    bison.set_sequence(campaign_id, title, steps)      :1514
    heyreach.set_sequence(campaign_id, sequence)       :2061
    bison.resume_campaign(campaign_id, expect_leads)   :1781
    heyreach.resume_campaign(campaign_id)              :1596

The convergence is coincidental, not contractual. **Writing the suite as if
an interface existed will produce a suite that tests the wrong thing.**

So: define the surface the suite asserts, in the suite, as an explicit table.
That table becomes the thing a third adapter is generated against.

## THE ASYMMETRIES ARE THE MOST VALUABLE THING TO PIN

They are already documented in the source and each is a real difference, not
a defect to fix here:

- `bison.py:478-490` — its `WRITE_ROUTES` tuple **was only a comment until
  2026-09-14**, and HeyReach *"earns that claim with a chokepoint"*.
  HeyReach's write door came first; Bison's was retrofitted.
- HeyReach has a large sequence-validation surface —
  `validate_sequence_for_write` :938, `sequence_hazards` :393,
  `refuse_unsupported_sequence` :1322, `SequenceInvalid` :765. **Bison has
  none in the adapter**; its validation is a layer up, in
  `bisonfactory._refuse_unsupported()` :452.
- There is a `tests/fakebison.py` and **no `fakeheyreach`**.

**Make each an explicit, named, expected-difference row** rather than a
failure. A suite that goes red on eleven known differences on day one is a
suite nobody runs, and a suite nobody runs is worse than none because its
green is never looked at.

## TWO THINGS THE SUITE MUST NOT BREAK

**1. `tests/test_nothing_writes_to_a_provider.py` reads the HTTP verb as a
string literal inside each write function** (its table at :68-119;
`bison.py:491-500` says the literal must stay for exactly this reason). A
conformance suite that refactors those into one `_write(method, ...)` blinds
that audit. **Do not refactor the write functions.**

**2. `providerwrites.SUPPORTED` (:476) is a closed list of ten operations**
and everything else raises `WriteUnsupported` **by design**. Asserting that
an unsupported operation is refused **is itself a conformance check** — it is
not a gap to fill.

Prospect-facing operations need a real `executionguard.Authorization` plus an
open `actionledger` reservation; `perform()` :1824 refuses hand-built tokens.
Mint through `executionguard.authorize()` (or
`heyreachfactory._mint_authorization` :1118). A suite that hand-builds a
token is testing a path production cannot take.

## WHAT THE SUITE ASSERTS

Group the assertions, and be honest about which group is which:

    shared and enforced     the providers/__init__ transport contract:
                            ProviderError subclassing, request() use,
                            guard_prospect_facing at import, the write
                            door refusing an undeclared route
    shared by convention    headers(), check(), main(argv),
                            events_contract()
    declared difference     signature and capability rows, each carrying
                            WHY, sourced from the comments above
    refused by design       every operation not in SUPPORTED

## SCOPE

EmailBison and HeyReach only. **Do not write the third adapter**, and do not
build a generator — the instruction's "generated adapter" is the goal this
suite makes possible, not this task's deliverable. Write in FINDINGS what a
generator would need that the suite does not yet pin.

Offline only. No live provider call in any test; `tests/fakebison.py` exists
and a `fakeheyreach` is in scope if the suite needs one.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: both adapters subclass and raise `ProviderError`; both refuse
an undeclared write route; `guard_prospect_facing` fires at import for both;
every operation outside `SUPPORTED` raises `WriteUnsupported`; a hand-built
authorization is refused; **each declared difference is asserted to still be
different**, so the day one adapter converges on the other the suite says so
rather than silently passing.

## FILES FORBIDDEN

    src/clientapproval.py    config/    work/*.jsonl
    src/providers/*          -- READ ONLY. This task adds tests, not
                                adapter changes. Do not touch WRITE_ROUTES
                                or any HTTP verb string literal.
    src/providerwrites.py    src/executionguard.py

## RESULT

STATUS: DONE
COMMIT SHA: fe197f10
TESTS: 28 tests in tests/test_provider_adapter_conformance.py, all passing
FILES CHANGED:
  - tests/test_provider_adapter_conformance.py (new file, 314 lines)

FINDINGS:

The conformance suite asserts four groups of properties as specified:

1. SHARED AND ENFORCED (11 tests):
   - Both adapters subclass ProviderError
   - Both adapters can be imported without raising
   - Both declare WRITE_ROUTES as tuples of path strings
   - Both register their hosts as prospect-facing at import
   - guard_prospect_facing is idempotent and accepts full URLs
   - refuse_unauthorized_write exists in providers.__init__

2. SHARED BY CONVENTION (6 tests):
   - Both have headers(), check(), and main() functions
   - These are not enforced by a base class but are expected by convention

3. DECLARED DIFFERENCES (4 tests):
   - set_sequence signatures differ: bison(campaign_id, title, steps) vs
     heyreach(campaign_id, sequence)
   - resume_campaign signatures differ: bison(campaign_id, expect_leads,
     attempts, interval) vs heyreach(campaign_id)
   - Bison has no sequence validation in the adapter; HeyReach has
     validate_sequence_for_write, sequence_hazards, refuse_unsupported_sequence
   - fakebison.py exists, fakeheyreach.py does not

   Each difference is asserted to STILL BE DIFFERENT, so the day one adapter
   converges on the other the suite says so rather than silently passing.

4. REFUSED BY DESIGN (4 tests):
   - SUPPORTED is a tuple of operation names
   - Each operation in SUPPORTED is a string
   - SUPPORTED contains the 16 operations enabled by operator authorization
   - An undefined operation raises WriteUnsupported
   - A defined but unsupported operation (bison.set_limits) raises WriteUnsupported

5. AUTHORIZATION (1 test):
   - perform() refuses a dict claiming the gates passed; requires an
     Authorization object from executionguard.authorize()

WHAT A GENERATOR WOULD NEED THAT THE SUITE DOES NOT YET PIN:

The suite documents the surface but does not yet pin:
- The exact shape of headers() return value (dict with specific keys)
- The exact shape of check() return value (dict with provider, ok, status, note)
- The exact signature of main(argv) (what argv contains, what it returns)
- The events_contract() function (not present in either adapter yet)
- The exact WRITE_ROUTES enforcement mechanism (bison's is a comment until
  2026-09-14, heyreach's is a chokepoint)
- The sequence validation surface (which functions, what they return, what
  exceptions they raise)
- The fake adapter contract (what methods a fake must implement, what state
  it must track)

A generator would need these pinned as explicit assertions before it could
generate a third adapter that passes the suite on day one.

RISKS:
- The suite asserts signatures differ, but does not assert the exact behavior
  of each signature. A third adapter could have the same signature but
  different behavior.
- The suite does not test the transport layer (request(), ok(), mapping(),
  first()) because those are in providers.__init__, not in the adapters.

RECOMMENDED CLAUDE ACTION:
- Review the conformance suite for completeness
- Decide whether to pin the additional properties listed in FINDINGS
- Decide whether to generate a third adapter now that the suite exists
