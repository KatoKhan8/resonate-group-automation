# TASK-977 — five failures GLM charged to a branch, and the one real defect under them

Opened 2026-10-03 from GLM's second multi-part FAIL of
`task-word-contract-enforced`. The verdict named five red tests in the branch's
changed modules and it was RIGHT that they are red. **It was wrong that they
are the branch's.** All five are master's, all five are already in
`reference-228-master-7e8eee41.log`, and two of the three underlying causes are
STALE TESTS rather than lost guards.

This file exists because three of those five would otherwise be "fixed" by
reverting decisions the operator took on 2026-09-30 after measuring them.

## The measurement that reassigns all five

Per module, branch at `6cffa188` (which contains master `7e8eee41`):

    test_campaign_ready_funnel                    ran=27  fails=0
    test_generate                                 ran=56  fails=3
    test_ladder_propagation                       ran=25  fails=0
    test_task910_writer_contract                  ran=16  fails=2
    test_task913_writer_contract_five_plus_five   ran=40  fails=0
    test_the_keyless_doors_get_the_contract       ran=15  fails=0
    test_word_contract_enforced                   ran=53  fails=0
                                                  ran=232 fails=5

The same two modules on a neutral worktree detached at master `7e8eee41`, with
nothing from the branch present, give the **same five names and the same
counts**. And all five parse out of the reference log (228 names via
`run_suite._parse_failures`; positive control `test_e2e` = 11).

**A changed-file list is not an attribution.** The branch edits
`test_task910_writer_contract.py` and `test_generate.py` only to lengthen
fixture bodies to meet the word contract. CLAUDE.md already records the mirror
of this trap for references measured against an older master.

## Defect A — two tests pin a punctuation chain that was deliberately replaced

`tests/test_task910_writer_contract.py`

    TestNormaliserOnCanonicalPath.test_em_dash_still_fails_after_normalisation
    TestPunctuationRegression.test_em_dash_normalised_but_still_caught

Both assert em dash -> `" - "` -> `copylint.DASH_RE` fires -> `copy_refused`.
`_PUNCTUATION_MAP["—"]` has been `", "` since `20d9fb12` (2026-09-30), *"The
punctuation normaliser manufactured the exact dash the copy lint bans"*: the
old `" - "` output was itself the banned pattern, so the normaliser generated
the refusal it existed to prevent. The tests predate that by two days
(`a353f920`, 2026-09-28) and were never moved.

**THE BAN IS NOT LOST.** Measured:

    lint.check on a RAW em dash          ['em_dash', ...]
    normalise_punctuation('clauses—x')   'clauses, x'
    DASH_RE on the raw text              True
    DASH_RE on 'clauses, x'              False
    em dash surviving normalisation      False

An em dash is still in `SUBSTITUTED_PUNCTUATION`, `lint.check` still refuses it
in un-normalised copy, and no em dash can reach a prospect. What changed is
that after normalisation there is no dash left for `DASH_RE` to catch, which is
the point of the change.

**What to do:** move the two tests to the current contract — em dash
normalises to `", "`, is NOT refused after normalisation, and IS refused before
it. Keep a test that a raw em dash is refused, because that is the guard.
**Do NOT revert the map.** That position was measured and refuted: "a dash used
as punctuation" was the single most recurrent writer refusal, surviving twenty
attempts across two models.

## Defect B — the rejection ledger accumulates and never forgets

`src/generate_campaign.py`, the `MAX_WRITER_ATTEMPTS` loop. **This is the one
real defect of the five.**

First, the part that is NOT a defect: `MAX_WRITER_ATTEMPTS = 10`, raised
3 -> 6 -> 10 in `b946b59c` (2026-09-30) with its reasoning recorded inline. So
10 writer calls = 1 draft + **9 retries** is the designed budget, and
`assertEqual(len(model.retry_prompts), 1)` in two `test_generate` tests pins a
cap three versions old. Measured: `writer_prompts: 10`, `retry_prompts: 9`.

The defect is what those nine retries are TOLD. The reason list handed to retry
9 is byte-identical to the one handed to retry 1:

    - step 1 opens with a line no pack fact supports
    - a buzzword or banned phrase -> em1 ('i wanted to reach out')
    - em2 ('i wanted to reach out')
    - em3 ('i wanted to reach out')
    - em4 ('i wanted to reach out')
    - day1: you referred to an attachment. Nothing is attached
    - the body is under 40 words
    - you used "i wanted to reach out", which is banned outright...
    - you left an unfilled placeholder in square, curly or angle brackets
    - day15: you referred to an attachment. Nothing is attached

Nine of those ten come from attempt 0's deliberately-bad draft. Logging every
writer answer shows call 0 returns the bad body and calls 1-9 return the clean
one, so **drafts 1 to 9 contain none of the nine stale complaints.** The model
is told nine times to remove a phrase it removed on the first retry, while the
single complaint that does apply is buried in the list.

`b946b59c` fixed uninformative retries by making the feedback COMPLETE — every
distinct reason, located, with a rising temperature. The unintended consequence
is that it is no longer CURRENT. "Refused for ALL of the following" is correct
as a requirement and wrong as a diagnosis.

**What to do:** prune the ledger to what the CURRENT draft actually offends
before composing the retry, while keeping the "satisfy every one at once"
requirement for constraints that are still live. The acceptance has to
distinguish the two, so a fix cannot pass by simply dropping the accumulation:

- a draft that fixes A and reintroduces B is still told about both;
- a draft that fixes A and keeps it fixed is NOT told about A again;
- the cost per refused contact falls below 10 writer calls when the earlier
  reasons are genuinely resolved.

**The spend.** 10 model calls per refused contact, and in this fixture nothing
is stored at the end of them. Attribute per CLAUDE.md's spend rule when
measuring.

## Defect C — the `harbourline` fixture has no pack fact for its opener

`tests/test_generate.py:250`,
`TestTheAcceptanceTest.test_a_draft_that_breaks_a_rule_is_regenerated_not_patched`,
`KeyError: 'rowan-blake'`. **Not a fixture typo and not in `test_task910`** —
it is defect B's downstream symptom. Every attempt is refused, so nothing is
written:

    record state   : verified
    cadence stored : []

and `rec()["cadence"]["rowan-blake"]` raises. The blocking gate is
`step 1 opens with a line no pack fact supports`: the fixture carries no pack
fact licensing its opener, so the opener can never be licensed and the set can
never pass however many attempts it gets.

A branch named `lane-l-staging-fixtures-packfacts` already exists and may own
this. **Check it before building a second fixture.**

## Acceptance

Each command must fail before its fix and pass after, and the controls matter
more than usual here because two of the three fixes are test moves and a test
move can always be made to pass by asserting less.

```
python -c "import sys; sys.path.insert(0,'.'); from src import lint, copylint; EM='—'; raw='clauses'+EM+'like this'; n=lint.normalise_punctuation(raw); assert EM not in n, n; assert n=='clauses, like this', n; assert not copylint.DASH_RE.search(n), 'the normaliser is manufacturing the banned dash again'; assert copylint.DASH_RE.search(raw), 'the control failed: DASH_RE no longer sees a raw em dash at all'; print('OK em dash normalises to a comma and the normaliser does not manufacture the ban')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import lint; body=' '.join(['word']*50)+' clauses—like this'; rec={'id':'r','domain':'example.test','contacts':[{'key':'k','email':'a@example.test','cadence':{'em2':{'channel':'email','generated':True,'subject':'a subject that is fine','body':body}}}]}; step=rec['contacts'][0]['cadence']['em2']; fails=lint.check(rec,'k',step,step_key='em2'); assert 'em_dash' in fails, 'THE BAN IS GONE: a raw em dash was not refused: '+str(fails); clean=dict(step, body=lint.normalise_punctuation(body)); assert 'em_dash' not in lint.check(rec,'k',clean,step_key='em2'), 'a normalised body is still refused for a dash it no longer has'; print('OK raw em dash refused, normalised body not')"
```

```
python -m unittest tests.test_task910_writer_contract -v
```

```
python -m unittest tests.test_generate -v
```

### NEGATIVE CONTROL

**COMMANDS 1 AND 2 PASS TODAY, EXECUTED 2026-10-03, AND THAT IS THE POINT.**
They are not the fail-to-pass pair — they are the GUARDS that pin the behaviour
defect A's fix must not disturb, and they are written down so a fix that makes
commands 3 and 4 green by weakening the em-dash rule gets caught. Only commands
3 and 4 currently fail.

Command 1's third assertion is the one that matters: it fails if anybody
restores `" - "` as the em-dash replacement, which is the refuted position.
Its fourth is the control that `DASH_RE` still works at all — without it, a
`DASH_RE` that matched nothing would pass the first three assertions while
watching nothing.

Command 2 is the guard half, and it is the command that would catch a "fix"
that deleted the em dash from `SUBSTITUTED_PUNCTUATION` to make the tests
green. Its second assertion stops the opposite over-correction.

Commands 3 and 4 are the five names themselves. They must go from the measured
`2/16` and `2+1/56` to `0`. **Re-measure the reference afterwards**: these five
are IN the 228-name baseline, so fixing them REMOVES five names, and the next
branch measured against the old reference would be charged with five
disappearances it did not cause. A name that disappears is verified positively
by finding it running and passing — CLAUDE.md's rule, and it applies to this
task's own result.

## Files

`tests/test_task910_writer_contract.py` (defect A),
`src/generate_campaign.py` + `tests/test_generate.py` (defect B),
the `harbourline` pack-fact fixture (defect C, check
`lane-l-staging-fixtures-packfacts` first).

## Not in scope

`_PUNCTUATION_MAP["—"]`, which stays `", "`. `MAX_WRITER_ATTEMPTS`, which stays
10 — the budget is not the defect, the staleness of what it is spent on is.
The word contract itself (TASK-968) and its numbers (TASK-964).
