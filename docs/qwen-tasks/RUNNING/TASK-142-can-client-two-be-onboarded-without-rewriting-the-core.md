PRIORITY: P2
DEPENDS:

# TASK-142 - the portability test, answered with a list rather than an opinion

## THE QUESTION, EXACTLY

Can a second client be onboarded through CONFIGURATION, DATA and PRODUCT
KNOWLEDGE, or does it require editing Resonate OS core logic?

That is the test that decides when development attention can move to Client #2
while Productive keeps running. It is not answered by "mostly yes".

## THE METHOD

Do not read the code looking for things that feel Productive-specific. Walk the
PRODUCTION LOOP and, at each stage, ask what a second client would need and
where that value comes from today:

    domain inventory -> account processing -> research -> signals
      -> ICP qualification -> contact discovery -> relationship state
      -> cohorting -> copy and variables -> gates -> provider campaign
      -> senders -> leads -> readback -> outcomes -> learning

For every stage produce one row:

    stage
    what is client-specific about it
    where that value lives today   (config key / data file / hardcoded in src)
    what Client #2 would have to do
    verdict: CONFIG | DATA | CODE CHANGE

Three already-known entries, recorded and deliberately NOT refactored, so do
not spend the task rediscovering them:

    the client config carries the fallback copy inline
    scripts/build_intake_batch.py hardcodes the Productive source CSV path
    several task scripts default to --client productive

Those do not block production. Confirm they are still true in one line each and
move on to what is not yet known.

## WHAT MAKES THIS USEFUL RATHER THAN A SURVEY

Every CODE CHANGE row must name the FILE AND THE FUNCTION, and must say
whether it is:

    BLOCKING     Client #2 cannot be onboarded without it
    FRICTION     Client #2 works but somebody edits code to do it
    COSMETIC     neither; it just looks client-specific

A list of forty cosmetic observations is worth less than three blocking ones
with file and function. Rank them and put the blockers first.

## THE TENANCY BOUNDARY IS DIFFERENT FROM THE CONFIG BOUNDARY

Some things are not "Productive-specific values" but "assumptions that there is
one client". Those are more serious and harder to see. Look specifically for:

    a lookup that would return another client's row
    a default that means "everybody" when a client is not named
    a provider credential bound to one workspace and read as if global
    a state key that does not carry a client

`heyreachfactory._plan` already refuses an empty `record_ids` rather than
walking the estate, and refuses a record belonging to another client, so that
shape of guard exists and is worth pattern-matching against elsewhere.

## WHAT YOU MAY NOT DO

- **Do NOT refactor anything.** This task produces the list. A multi-tenant
  refactor now would put unreviewed structural change on the path of the first
  live campaign, which is the trade the priority order forbids.
- No provider calls. No writes to `work/`.

## FILES ALLOWED

    docs/CLIENT-TWO-PORTABILITY-2026-09-15.md   (new)
    the task file itself

## FILES FORBIDDEN

    src/       scripts/       config/       work/

## DELIVERABLE

The stage-by-stage table, the ranked BLOCKING / FRICTION / COSMETIC list with
file and function on every code row, the tenancy-assumption findings, and a
one-line verdict on the portability question that a reader can check against
the rows above it.
