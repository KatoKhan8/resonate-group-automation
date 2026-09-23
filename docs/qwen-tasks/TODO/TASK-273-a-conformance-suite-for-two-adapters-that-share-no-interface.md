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
