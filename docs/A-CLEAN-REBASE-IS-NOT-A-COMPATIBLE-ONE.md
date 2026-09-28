# A clean rebase is not a compatible one

**`task400-rework3` rebased onto master, 2026-09-28. `git rebase` reported ZERO
textual conflicts across all 18 commits, and the tree it produced imported,
compiled, and carried TWO PARALLEL REPRESENTATIONS OF ONE TRUTH.**

Resolution commit: `638f1ed5`. Branch: `task400-rework3-rebased`.

This is written down because **a reviewer cannot re-derive any of it from the
merge diff.** After the resolution, `git diff master HEAD` shows `sequenceplan.py`
absent and both factories carrying four or five lines each — it looks like a
rebase that had nothing to resolve. The thing worth knowing is what was there
before the resolution, and it leaves no trace in the final diff.

## WHY GIT HAD NOTHING TO SAY

The branch was cut at `5c356b7d`, which is not an ancestor of master. Between
that point and master, `TASK-364` rewrote `src/sequenceplan.py` into one
canonical plan that both factories project from. The branch had meanwhile made
its own small edits in the same area.

`git merge` compares TEXT in LINE REGIONS. The branch's edits landed in regions
master had not touched line-for-line, so there was nothing for git to flag. **A
conflict is evidence of textual overlap, and its absence is evidence of nothing
else.** Semantic compatibility is not a question git is able to ask.

The clean rebase was therefore the DANGEROUS outcome, not the reassuring one: a
conflict would have forced a human decision at exactly the place one was needed.

## WHAT THE TREE ACTUALLY CARRIED

### 1. A second, backwards-derived canonical plan in BOTH factories

Master's `bisonfactory._plan` builds the plan FORWARD and projects from it:

    sequence_plan    = sequenceplan.for_campaign(campaign, config, ...)
    provider_sequence = sequenceplan.derive_bison_sequence(...)

The rebased tree kept those AND added, in the same function:

    canonical_contacts = _leads_to_canonical_contacts(leads)   # <-- from leads
    canonical_plan     = sequenceplan.new(..., cadence_steps=cadence_steps)
    derived_payload    = sequenceplan.derive_bison_payload(canonical_plan)

`leads` is the ALREADY-BUILT provider payload. So this second plan was derived
BACKWARDS out of the thing it is supposed to be the source of, and then a payload
was projected back out of it. `heyreachfactory._plan` had the identical shape via
`_contacts_to_canonical(per_contact)`, plus `_company_of_li`,
`_ROLE_TO_SEQUENCE_KEY`, and a duplicated `# ensure_leads` section banner.

**This is verbatim the defect `TASK-364` rework 2 was rejected for**, and master's
own module docstring names it:

> The second attempt at this task built the derivation backwards: it built each
> provider's sequence first and then generated a "canonical plan" FROM the
> result. Plan and payload could not disagree - one was made out of the other -
> so a consistency test between them passed by construction and proved nothing,
> and a mutation of the plan could not change either payload. That is worse than
> dead code, because the system looks verified exactly where it is not.

**Had this merged, `TASK-364`'s canonical plan would have been silently
un-canonicalised, and every test would have stayed green.** Plan and payload
cannot disagree when one is made from the other; a plan mutation changes neither
payload; the consistency test passes by construction. The acceptance check would
have kept passing while the property it exists to prove was gone. Two parallel
representations of one truth is precisely what the "One truth" invariant
(`OPERATING-MODE.md`, §5) exists to prevent, and nothing in CI can see it.

**Resolved:** both factories reverted to master byte-for-byte, except the one
thing that is `TASK-400`'s own and not `TASK-364`'s — the four-line
`refuse_dry_run_records` guard at each attach boundary
(`bisonfactory._ensure_leads`, `heyreachfactory.ensure_leads`), asserted
behaviourally by `tests/test_task400_rework2.py`
`TestBothProvidersRefuseAStampedRecord`, which booby-traps the provider
`request` seam so a refusal arriving after the network fails the test rather
than passing quietly, and which carries a negative control proving the refusal
is conditional.

### 2. A `cadence_steps` parameter that silently discarded the caller's cadence

The branch re-added a parameter to `sequenceplan.new()` as a deliberate,
documented one-line recovery: rework 2 called `new(..., cadence_steps=...)`, and
that signature existed only on the then-unmerged `TASK-364` branch, so every
staging call was raising `TypeError`. On its own base that recovery was correct
and the branch said so in a comment.

After the rebase it was **redundant and actively harmful.**

Redundant: `TASK-364` is merged, and master's real entry point
`sequenceplan.for_campaign(campaign, config, *, cadence_steps=None, ...)` already
takes it. No caller of `new()` passes it any more — the only one left,
`generate_campaign.py:181`, passes `cadence=`.

Harmful, and this is the part that would not have been noticed:

    if cadence_steps is not None:
        cadence = {"name": ..., "steps": list(cadence_steps)}

It does not ADD steps to the cadence. It **REPLACES the caller's whole `cadence`
dict with a two-key one**, discarding every other field the caller passed. A
caller handing `new()` a richer cadence would have had it quietly truncated, with
no error and no test covering the loss.

**Resolved:** `src/sequenceplan.py` reverted to master, byte-identical — zero
diff. Verified afterwards that nothing in `src/`, `tests/` or `scripts/` still
calls `sequenceplan.new(..., cadence_steps=...)`.

### 3. A deleted comment that the diff could not account for

The branch's `_plan` diff deleted master's nine-line **"THE CAMPAIGN'S OWN WINDOW
WINS"** block — the one recording that EmailBison schedules ONE window per
campaign, so the window is a property of the cohort rather than the client, and
that mixing timezones into one campaign guarantees somebody is mailed at 03:00
local. Nothing in the branch's change needed it gone; it was collateral of
editing the adjacent return dict.

**Resolved:** restored with the rest of the file. Recorded here because deleting
a comment that explains a real scheduling hazard is a silent loss — it does not
fail a test, and the next person to touch campaign grouping is the one who pays
for it.

## THE GENERAL LESSON

**A rebase that reports no conflicts has told you about TEXT, not about DESIGN.**
When a branch is cut before a structural change landed on master, the correct
question is not "did it apply?" but **"does the branch still mean what it meant,
against the architecture that is now underneath it?"**

The failure mode is specific and worth naming: the branch's code was *right on its
own base*. It became wrong the moment master's design changed beneath it, and the
rebase preserved it faithfully — which is exactly what a rebase is for. Fidelity
to the branch is the wrong objective when the branch's premise has been replaced.

What made it findable:

1. **Diff the rebased head against master and read every hunk in a file the
   other side rewrote** — not just the files git flagged, which was none of them.
2. **Ask what already holds this truth.** Two fields named `sequence_plan` and
   `canonical_sequence_plan` in one return dict is the tell; so is two functions
   projecting the same payload.
3. **Check the direction of derivation.** If X is built from Y and Y is built
   from X, any test comparing them passes by construction.
4. **Read the target module's own docstring.** Master's `sequenceplan` had
   already written down the defect, in the words of the review that rejected it.
   The rebased tree reintroduced precisely what that paragraph forbids.

For the next rebase onto this area: `src/sequenceplan.py` owns plan
CONSTRUCTION, and the factories own NONE of it. A factory that builds a plan, or
converts leads or contacts back into plan shape, is reintroducing this defect
whatever it is called.

## WHAT WAS VERIFIED AFTER THE RESOLUTION

Not "it still compiles":

    acceptance   tests.test_generate                          51/51
    branch       test_task400_rework2 + rework3               56/56
    protected    7 proofs incl. test_one_plan_decides_both_providers  86/86
    suite        0 new failing names vs master, 5 fixed, by NAME
    mutations    6 of 6 reproduced, each failing its intended
                 test for its intended reason

`test_one_plan_decides_both_providers` is the load-bearing one here: it is the
proof that ONE plan decides both providers, and it is exactly the test a second
backwards-derived plan would have left passing while making false.

Provider writes 0. No campaign touched.
