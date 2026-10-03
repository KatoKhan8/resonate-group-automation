# TASK-974 — the guard branch ships a suite attestation for a commit that is not on the branch

Found by GLM part 4 of 5 on `task-guard-regressions-rebased` @ `eff4e890`,
2026-10-03, and **confirmed to be worse than GLM said**.

## Measured

`docs/state/SUITE-task-guard-regressions-2026-10-02.json`, committed on the
branch, carries:

    commit     31bc1801bbf1a40584eef8a1cb507a7a2984fc1e
    modules    81
    total      232   (162 fail + 70 error)

The branch tip is `eff4e890`. GLM called `31bc1801` "the pre-rebase commit",
which would already be a defect. It is more than that:

    git merge-base --is-ancestor 31bc1801 HEAD  ->  False

**`31bc1801` is not an ancestor of the branch at all.** The rebase abandoned
it, so the file attests a tree that exists nowhere in this branch's history,
under a filename that names the branch and a date that looks current.

## Why this is a defect rather than untidiness

This repository has been fooled by exactly this artefact before — it is in the
standing rules as *a committed stale suite verdict*, one of the three ways a
green test proves nothing. The cost is not hypothetical: it is what sent two
of GLM's five parts off the rails tonight. Part 4 read the file as the branch's
after-state and called a regression; part 5 could not tell baseline from
regression and returned NEEDS_CLAUDE, which under the operator's standing rule
does not pass. **A branch that carries a misleading attestation fails its own
gate for a reason that has nothing to do with its code.**

The branch's real state was measured separately and is clean: a full suite on
`eff4e890` itself gave 231 names against the 231 of
`reference-231-master-0c9adf0a.log` — 0 new, 0 gone, 2,099.5s, 14,759 results.
And the three failures GLM named from the stale file are all IN that reference,
verified by name:

    test_nothing_writes_to_a_provider.test_every_http_write_in_the_repository_is_declared
    test_invariants.test_no_module_issues_an_http_post_outside_the_named_ones
    test_a_person_can_enter_a_heyreach_campaign.TheSealStillHolds.test_supported_is_exactly_this

So the 232 outcomes are the documented baseline, not the branch's doing.

## What to do

Either regenerate the file from a run of the commit it ships with, or delete it
and let the reference log be the evidence. **Do not hand-edit the `commit`
field** — a file whose body belongs to one tree and whose header names another
is the same defect with better camouflage.

Then make it structural, because a rule nobody can forget is worth more than
this task: a committed `docs/state/SUITE-*.json` whose `commit` is not an
ancestor of `HEAD` should red a test.

## Acceptance

```
python -c "import glob,json,subprocess,sys; bad=[]; [bad.append((p,d.get('commit'))) for p in glob.glob('docs/state/SUITE-*.json') for d in [json.load(open(p,encoding='utf-8'))] if d.get('commit') and subprocess.run(['git','merge-base','--is-ancestor',d['commit'],'HEAD']).returncode!=0]; assert not bad, 'a committed suite attestation names a commit that is not an ancestor of HEAD: '+repr(bad); print('OK every committed suite attestation names a commit on this branch,', len(glob.glob('docs/state/SUITE-*.json')), 'files checked')"
```

### NEGATIVE CONTROL

**It fails today** on the branch, naming the file and `31bc1801`. It cannot
pass by finding nothing: the printed count is the control, and it is a real
number on both master and the branch (the glob is non-empty, which was checked
before this was written). A file with no `commit` key is skipped rather than
failed, deliberately — the defect being prevented is a WRONG attestation, and
an attestation that claims nothing misleads nobody.

## Files

`docs/state/SUITE-task-guard-regressions-2026-10-02.json`, and wherever the
structural check lands.

## Not in scope

The branch's guards themselves. They were measured clean on their own commit.
