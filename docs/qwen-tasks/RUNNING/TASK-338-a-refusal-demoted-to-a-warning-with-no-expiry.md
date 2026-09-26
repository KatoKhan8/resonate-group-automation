PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-338 - a refusal demoted to a warning, with no expiry

**SEVERITY: MEDIUM.** Buggie finding M5, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

`src/copylint.py`:

    WARNING_RULES = frozenset({"step1_without_pack_fact"})

The comment says the demotion was granted under an operator directive
**"explicitly time-boxed to 2026-09-28"**. There is no date check anywhere in
`copylint.py` and no automatic reversion. After 2026-09-28 the rule keeps warning
instead of refusing, silently, until a human remembers to edit the frozenset.

Today is 2026-09-26. The window has **two days left**, so this is not yet firing -
which is exactly why it is worth fixing now rather than discovering later.

`step1_without_pack_fact` means the opening email carries no researched fact about
the company. That is the difference between a personalised opener and a generic
one, and it is a REFUSE rule in its normal state.

## What to do

Make the expiry mechanical, not remembered.

    src/copylint.py    MODIFY. The demotion carries its own expiry date and
                       stops applying after it.
    tests/test_a_time_boxed_demotion_expires_on_its_own.py   NEW

Design constraint: **the expiry must be data, not a hardcoded `if` on today's
date buried in a function.** A demotion is `(rule, until_date, why, who_granted)`
so the next one is recorded the same way and is equally visible.

**Do not extend the window.** Whether to renew the demotion past 2026-09-28 is
the operator's decision, not yours. If the rule would start refusing copy the
moment you ship this, that is the correct behaviour and the operator's to
override - say so clearly in the result block, with a count of how many of the
fifty's 31 written leads would newly refuse.

## Acceptance - RUN each, paste real output

1. Before the expiry date, the rule warns:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import copylint;\
    print('warning rules today:', sorted(copylint.warning_rules(today='2026-09-27')))"

2. **After the expiry date, the rule REFUSES.** This is the whole point, so prove
   it rather than asserting the table:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import copylint;\
    r=copylint.warning_rules(today='2026-09-29');\
    assert 'step1_without_pack_fact' not in r, 'demotion survived its own deadline';\
    print('expired correctly; warning rules after 09-28:', sorted(r))"

   Name the real function if your implementation differs, but the assertion must
   be on BEHAVIOUR at a date, not on the presence of a date string.

3. A batch that would refuse after expiry is seen to refuse - a real lint call,
   not a table lookup.

4. Report the count of the fifty's written leads that would newly refuse.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- **Do not extend or renew the demotion.** Operator's call.
- Do not widen any other rule, and do not move another REFUSE to a warning.
- Do not modify the fifty's posted files.
- Nothing sent, nothing activated.
