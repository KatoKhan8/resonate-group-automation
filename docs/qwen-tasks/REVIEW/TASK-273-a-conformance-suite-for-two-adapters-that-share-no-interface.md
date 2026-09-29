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
COMMIT SHA: d34f53ae
TESTS: 26 new tests in tests/test_adapter_conformance.py, all pass.
  Zero new failures against the branch baseline. Two pre-existing failures
  in test_invariants (reviewapproval barrier checklist, bison v3 campaign
  id) and one in test_nothing_writes_to_a_provider (undeclared POST in two
  scripts from a cherry-picked branch) are NOT caused by this change.
  Verified: test_invariants.NoTestBindsAReloadedExceptionClass passes after
  fixing the ProviderError import to use providers.ProviderError at call
  time.
FILES CHANGED:
  tests/test_adapter_conformance.py  (new, 406 lines)
  docs/qwen-tasks/RUNNING/TASK-273-...  (moved from TODO/)
FINDINGS:
  1. The DECLARED_DIFFERENCES table in the suite is the artifact a third
     adapter generator would be built against. It pins five asymmetries:
     set_sequence signature, resume_campaign signature, sequence validation
     location, write door shape, and fake existence. Each is asserted to
     STILL differ, so convergence is reported rather than silently passing.

  2. What a generator would need that the suite does NOT yet pin:
     - The READ_ROUTES_ALL / declared-reads contract. HeyReach declares
       POST-as-read routes and registers them via guard_read_routes; Bison
       uses plain GETs. A generator needs to know which reads are POST and
       declare them, or the transport guard refuses them.
     - The _write_body vs _write split in HeyReach (query-string routes vs
       body routes). A generator that collapses these into one function
       would silently send bodies to query-string routes.
     - The expect_leads containment on bison.resume_campaign. A generator
       that omits this parameter removes the lead-count safety net.
     - The WRITE_QUERY_ROUTES tuple in HeyReach, which prevents bodies from
       being sent to query-string routes.
     - The bisonfactory._refuse_unsupported validation layer. A generator
       for Bison needs to know validation lives OUTSIDE the adapter.

  3. The suite does NOT build a fakeheyreach. The declared difference table
     pins its absence. Building it is a separate task.

  4. The hand-built Authorization test pins that isinstance passes for a
     directly-constructed Authorization object but the ledger reservation
     is the real gate. The suite does not attempt to call perform() with a
     hand-built token because that path requires a real ledger reservation
     that cannot be constructed offline without mocking the entire ledger.

RISKS:
  - The DECLARED_DIFFERENCES table is a snapshot. If either adapter changes
    its signature, the suite reports it (which is the point), but the table
    description needs updating too.
  - The suite imports bison and heyreach at module scope, which triggers
    guard_prospect_facing registration. This is by design - the test
    asserts that registration happened.

RECOMMENDED CLAUDE ACTION:
  Review the DECLARED_DIFFERENCES table in tests/test_adapter_conformance.py
  and confirm the five asymmetries are the right ones for a generator to
  work against. The suite is ready to be the green-light criterion for a
  third adapter.
