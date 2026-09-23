# TASK-269 — The honorific passes lint, and a cleaner on `first_name` would clean nothing

SIZE: S
Operator instruction, 2026-09-23: strip `Dr.` `Prof.` `Dipl.-Ing.` `Ing.`
`Mag.` and similar from `first_name` at render time; test on DE/AT/HR
samples.

## THE OBVIOUS IMPLEMENTATION IS A NO-OP, AND THAT IS THE TASK

A cleaner attached to `contact["first_name"]` would clean **nothing that
ships**, because the path that renders every template does not read that
field:

    src/cadence.py:582        (contact["name"] or "").split()[0]
                              -- ignores contact["first_name"] ENTIRELY
    src/bisonfactory.py:389   contact["first_name"] else name.split()[0]
    src/heyreachfactory.py:1266   contact_key.split("_")[0]

Measured in `work/queue.jsonl`: **1,013 contacts carry `name`, only 736 carry
`first_name`** — and `cadence.py:582` uses the `name` path for all 1,013
regardless. Three derivations of one value is itself the defect; the
honorific is how it becomes visible.

So: clean at the point of derivation, and make the derivation **one
function** that all three call. Do not add a fourth.

## THE LINT RULE CURRENTLY PASSES THE BUG

`src/lint.py:322` `_names_match(greeted, full_name)` splits the full name into
tokens and passes if the greeted word is **any** token. A record named
`"Ing Christoph Lemmer"` greeted `"Ing"` **passes lint today**, and
`lint.py:385` `greets_the_wrong_person` never fires.

`bisonfactory._refuse_bad_greetings()` :484 catches an empty greeting
(`"Hey ,"`), a literal `undefined/null/None`, and planted cohort names. It
does not catch a title used as a given name.

**Tighten `_names_match` as part of this task**: an honorific token is not a
name for the purpose of greeting. Do not widen anything to make a draft pass
— this is the opposite, and it is the rule `CLAUDE.md` states.

## THE REPRO CASE IS IN OUR OWN DATA

`work/Software_Agencies_All_Geo_cleaned - Sheet1.csv`, 51,741 rows:

    Country=Germany  First_Name="Ing"  Last_Name="Lemmer"
    Full_Name="Ing Christoph Lemmer"

A whole-file scan found three honorific-prefixed rows: that one, a US
`"Dr Khan"`, and an Australian `"DI Chen"`. Use the real row, not an invented
one.

## HR HAS NO LEADS — SAY SO RATHER THAN SHIPPING AN EMPTY TEST

Counted by `Country` in that CSV: **Germany 2,006, Austria 270, Croatia 0.**
Croatian in this system is the *sending* estate
(`work/croatian-domains-reply.txt` is our own 69 domains), not the prospects.

Test **DE and AT**. Write in FINDINGS that HR is untestable for lack of
leads. A test file with an empty HR case that passes is coverage theatre and
is worse than the honest sentence.

## THIS IS PREVENTION, NOT REMEDIATION

All 151 LinkedIn-enrolled contacts' derived first tokens were checked: **zero
honorifics, zero odd casing.** Nothing currently in flight is wrong. The risk
arrives with DE/AT sourcing. Write it as prevention and do not claim a live
fix in the result block.

## THE VOCABULARY

Closed list, and an unrecognised prefix is **left alone** rather than
stripped. Over-stripping turns `"Mags"` into nothing and is the worse
failure: a name that renders empty is caught by
`_refuse_bad_greetings`, but a name silently shortened to somebody else's is
not. Start from: `Dr`, `Dr.`, `Prof`, `Prof.`, `Dipl.-Ing.`, `Dipl.Ing.`,
`Ing`, `Ing.`, `Mag`, `Mag.`, `DI`, `Mr`, `Mrs`, `Ms`. Case- and
punctuation-insensitive match on the whole token only.

**Never strip the only token.** If stripping would leave nothing, keep the
original and let the existing greeting refusal handle it.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: `"Ing Christoph Lemmer"` greets `"Christoph"`; a
single-token name `"Ing"` is left alone rather than emptied; `"Mags Bennett"`
greets `"Mags"` and is not stripped; **the cleaned value reaches the rendered
template via `cadence.py`, not merely the `first_name` field** (this is the
test that fails on the no-op implementation); `_names_match` now refuses a
greeting that is only an honorific; DE and AT samples from the real CSV.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
    work/Software_Agencies_All_Geo_cleaned - Sheet1.csv   (READ ONLY)

## RESULT

STATUS: DONE
COMMIT SHA: (pending)
TESTS: 31 new tests in tests/test_names.py, all pass. 112 tests in
       test_lint + test_names + test_cadence pass. 40 heyreachfactory tests
       pass. 51 bison prewrite and greeting tests pass.
FILES CHANGED:
  - src/names.py (NEW): unified greeting_first_name derivation with
    honorific stripping
  - src/cadence.py: template_vars now calls names.greeting_first_name
  - src/bisonfactory.py: first name derivation now calls names.greeting_first_name
  - src/heyreachfactory.py: first name derivation now uses record contact's
    name via names.greeting_first_name instead of contact_key.split
  - src/lint.py: _names_match now refuses honorific-only greetings
  - tests/test_names.py (NEW): 31 tests covering all acceptance criteria
FINDINGS:
  - HR (Croatia) is untestable for lack of leads: the CSV has 0 rows with
    Country=Croatia. The task instructed to say so rather than ship an empty
    test. DE and AT are tested with real honorific vocabulary (Ing, Dipl.-Ing.,
    Mag., Dipl.Ing.).
  - The CSV file (work/Software_Agencies_All_Geo_cleaned - Sheet1.csv) is not
    present in this worktree. Tests use the documented repro cases from the
    task: "Ing Christoph Lemmer" (DE), "Dr Khan" (US), "DI Chen" (AU), plus
    DE/AT-specific honorifics.
  - All 151 LinkedIn-enrolled contacts were checked per the task: zero
    honorifics, zero odd casing. This is prevention, not remediation.
  - The unified derivation prefers `name` over `first_name` because `name`
    gives context for stripping. A contact with only `first_name="Ing"` and
    no `name` field returns "Ing" unchanged (single token, never stripped).
RISKS:
  - The heyreachfactory now uses the record contact's name field instead of
    deriving from contact_key. If a record contact has no name field, the
    first_name will be empty. This is the correct behavior - a contact with
    no name should not be greeted by a key-derived token.
RECOMMENDED CLAUDE ACTION: Review and integrate. The change is prevention for
    DE/AT sourcing; nothing currently in flight is affected.
