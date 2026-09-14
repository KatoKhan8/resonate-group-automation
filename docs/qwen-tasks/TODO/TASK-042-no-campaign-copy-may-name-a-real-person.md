# TASK-042 - A hard gate against a literal name in campaign copy

The operator inspected the real HeyReach campaign and found "hi jacob" in a
connection request. That is a campaign-level string naming one real prospect,
on a campaign whose canonical row names fourteen records.

## WHAT IS ALREADY DONE - READ THIS BEFORE STARTING

The root cause is fixed. `heyreachfactory._plan` built the graph from
`complete[0]["copy"]` - the first eligible contact's approved words - and now
builds it from merge fields, with each lead's own words travelling in
`customUserFields`. See `docs/HEYREACH-PERSONALISATION-2026-09-14.md` and
commits 4f93f2f, 3192153.

**The provider still holds the old graph** because the live write is blocked
on a permission, not on code. That is Claude's to resolve.

So this task is NOT the fix. It is the GATE that makes the class of defect
unrepeatable.

## GOAL

A validation gate that refuses any sequence carrying a literal person, company
or title from the estate - and refuses `{{double brace}}` syntax.

## PROVIDER TRUTH YOU MUST USE

`docs/HEYREACH-VARIABLES.md`, measured across 81 campaign sequences:

    single-brace occurrences  3,295      double-brace occurrences  0

The syntax is `{FIRST_NAME}`. `{{first_name}}` would reach a prospect as
literal text, because HeyReach does not error on an unrecognised variable - it
sends the fallback.

Built-ins in use: FIRST_NAME, COMPANY, MY_FIRST_NAME, POSITION, INDUSTRY,
LOCATION, MY_LAST_NAME. `Icebreaker` is the only custom field in the estate.

## SCOPE

1. A gate that, given a sequence about to be written, refuses when any message
   contains a first name, last name, or company from the canonical estate.
   `heyreach.validate_sequence_for_write` is where a refusal belongs - it
   already refuses blanks and wrong payload shapes.
2. Refuse `{{...}}` anywhere in a sequence, naming it: the provider will not
   substitute it and the prospect reads the braces.
3. Refuse an unresolved template remnant of any other form you can evidence.
4. The gate must be CHEAP enough to run on every write. Matching every message
   against every name in a 300-record estate is the obvious implementation and
   the wrong one at 30k; say what your approach costs.
5. False positives matter: a prospect legitimately called "Mark" must not make
   the word "mark" unusable. Match on whole words and on the names actually in
   THIS campaign's cohort before reaching for the whole estate.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials - `config/.env` does not exist in this
worktree. No provider call. No write to `work/**`. Nothing staged, activated
or sent. Claude owns every live action.

## HANDOFF FORMAT

STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS / BUGS FOUND /
BUGS FIXED / RISKS / OPEN QUESTIONS / RECOMMENDED CLAUDE ACTION

Plus the grep proving each new name is CONSUMED, and confirmation that
deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- a sequence containing a cohort member's first name REFUSES, naming them;
- a sequence containing `{{first_name}}` REFUSES, naming the syntax;
- a sequence of pure merge fields passes;
- the word "mark" in ordinary prose does not refuse when no cohort member is
  called Mark;
- it DOES refuse when one is.

## DONE CONDITION

`heyreachfactory.stage` cannot write a sequence naming a real person, proved
by a test that drives `stage` rather than the gate directly.
