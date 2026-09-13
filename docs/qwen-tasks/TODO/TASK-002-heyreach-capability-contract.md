# TASK-002 - What HeyReach can actually be asked, on paper

## GOAL

A precise, evidence-backed statement of which HeyReach routes in
`src/providers/heyreach.py` could answer two questions - "is this profile an
Open Profile" and "can this seat send an InMail" - and which cannot, derived
from the adapter and its fixtures WITHOUT making a live call.

## WHY IT MATTERS

`src/cadencelibrary.py` declares `CAP_OPEN_PROFILE` and `CAP_INMAIL`, and
`productive_li_heavy_v1` HOLDS any step that needs them because neither is
established. A held step is correct and it is also a cadence running ten
touches while reporting eleven. Before anybody spends a live call measuring
this, the paper answer should exist: which route, which field, what the
absence of that field would mean.

## CURRENT CONTEXT

- `src/providers/heyreach.py` is ~2300 lines. `WRITE_ROUTES` is seven routes
  and is asserted by seal tests; reads wired are listed in
  `docs/CLAUDE-HANDOFF.md`.
- Resume, StartCampaign and every `AddLeadsToCampaign` spelling are
  deliberately absent and asserted absent.
- Campaign 599020 exists at the provider in DRAFT with no sequence.

## SCOPE

Read-only analysis plus tests.

1. Enumerate every response field any wired read route is known to return,
   from the fixtures in `tests/` and from the adapter's own parsing.
2. For each of the two capabilities, answer one of:
   - SUPPORTED, naming route + field + the fixture that shows it;
   - UNSUPPORTED, naming what was looked for and where;
   - UNDETERMINED FROM FIXTURES, naming the single cheapest live read that
     would settle it and what each possible answer would mean.
3. Write a test asserting the capability constants are consumed by the state
   machine - that a step naming an unproven capability is HELD and not
   silently dropped. Assert on behaviour (what the planner returns), never by
   grepping source text. CLAUDE.md is explicit about this and it has bitten
   this repo before.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`, a new markdown report under `docs/`.

## FILES FORBIDDEN

`src/providers/heyreach.py` and every other `src/**` file. This task changes
no adapter. `work/**`.

## PRODUCTION CONSTRAINTS

Zero network. Zero credentials. Do not call HeyReach. Do not touch campaign
599020 or 594061, and do not touch the other 48 campaigns in that workspace -
they are the client's own live work.

## TESTS REQUIRED

At least one behavioural test for the hold path described above. It must fail
if the hold is removed - prove that by removing it temporarily, confirming
the intended test failed for the intended reason, and restoring.

## EXPECTED OUTPUT

`docs/HEYREACH-CAPABILITY-CONTRACT.md` with one classification per
capability, plus the test.

## DONE CONDITION

Claude can read that document and know exactly which one live call to spend
next, or that no live call is needed because the fixtures already answer it.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
