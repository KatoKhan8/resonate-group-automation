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

## The mechanism is the rebase, and it is 2 of 2

Confirmed on a second branch the same night. `task-936-487-on-the-gate` carried
`measured_at_commit=0555dfa6`, which WAS an ancestor until it was rebased onto
master `e967271d` for its own gate run — and was not one afterwards. Nothing
warned, nothing changed in the file, and the filename still named the branch
while the date still looked current.

**So this is not one branch's untidiness: every rebase in the merge queue
silently invalidates every attestation the branch carries.** Two of the two
rebased branches tonight show it, and the queue holds five more older-base
branches that will each need a rebase. 936's copy was DELETED rather than
hand-edited (`3948c968`), per the rule below, and its replacement is the gate
run of the rebased tree plus the reference log.

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
python -c "import glob,json,subprocess; KEYS=('commit','measured_at_commit','sha','head_commit'); files=sorted(glob.glob('docs/state/SUITE-*.json')); assert files, 'no committed suite attestations found at all - this command would prove nothing'; pairs=[(p,k,d[k]) for p in files for d in [json.load(open(p,encoding='utf-8'))] for k in KEYS if d.get(k)]; assert pairs, 'every attestation claims a commit under none of the known keys %s - add the new spelling here, do not delete the check'%(KEYS,); bad=[(p,k,str(v)[:8]) for p,k,v in pairs if subprocess.run(['git','merge-base','--is-ancestor',str(v),'HEAD']).returncode!=0]; assert not bad, 'a committed suite attestation names a commit that is not an ancestor of HEAD: '+repr(bad); print('OK', len(pairs), 'attestation(s) across', len(files), 'files all name a commit on this branch')"
```

### NEGATIVE CONTROL

**It fails today** on the guard branch, naming the file and `31bc1801`.

**The first version of this command would have passed on the very next branch
in the queue, and that is why it now reads four keys.** Applied to
`task-936-487-on-the-gate` after its rebase, it reported `stale attestations:
none` — because that branch's `docs/state/SUITE-TASK-936-2026-10-02.json`
spells the field **`measured_at_commit`**, not `commit`, and the command only
looked for one spelling. Read under both, the same branch says:

    SUITE-TASK-936-2026-10-02.json   measured_at_commit=0555dfa6   NOT AN ANCESTOR

A command that checks one of two spellings in use is a vacuous pass wearing an
assertion, which is the defect this whole task is about. It now also fails
loudly when NO attestation claims a commit under any known key, rather than
passing on an empty list — so a third spelling introduced later makes it red
and names itself instead of going quiet. A single file with no commit key among
others that have one is still skipped on purpose: an attestation that claims
nothing misleads nobody.

The other two controls stand: the file count is printed, and a non-empty glob
is asserted rather than assumed.

## Files

`docs/state/SUITE-task-guard-regressions-2026-10-02.json`, and wherever the
structural check lands.

## Not in scope

The branch's guards themselves. They were measured clean on their own commit.
