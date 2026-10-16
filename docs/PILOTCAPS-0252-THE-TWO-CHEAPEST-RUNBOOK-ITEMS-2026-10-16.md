# The two cheapest items on the CANARY-01 runbook, re-measured 2026-10-16

TASK 0252, pilotcaps lane. The brief moved runbook items **P7** (the write-bypass
guard red in both directions) and **P10** (the brake's proof that cannot run)
off the `glm-c` lane after its weekly model quota was spent and the operator
stopped that lane.

**Both items were already repaired before this task started, by this same lane,
and both repairs hold on re-measurement.** This file exists because the
repairs' evidence lived only in terminal output and in an ops-folder lane file
that is not in git, and because the brief's own instruction — *reproduce first,
your measurement is twelve hours old* — turned out to be the operative one: on
P7 the premise no longer reproduces at all.

Every number below is measured, with the tree and the SHA it was measured on.
All four trees were CRLF on disk (`requirements.txt` CR=15, 812 B), so no
name-set here is compared across the line-ending boundary.

## P7 — the write-bypass guard

Repaired at `5b6ffc927`. Re-measured at `402b10d68`:

    py -3 -B -W ignore::ResourceWarning -m unittest \
        tests.test_no_new_write_bypasses_the_door -v
    Ran 10 tests in 18.291s
    OK

The two names the brief quotes as red —
`test_no_bypassing_call_site_is_new` and
`test_the_baseline_has_not_fallen_behind_the_code` — are green. The relocation
of `heyreach.add_leads_to_list` from `batch_linkedin_push.py::main` into
`stage_rows_to_list` is recorded in the baseline.

**The baseline is still current twelve hours and several merges later**, which
is the one thing nobody could have measured before now:

    scripts/known_write_bypasses.json
      before regen  sha256 ee7e30bb…c472b4f   2146 B
      after  regen  sha256 ee7e30bb…c472b4f   2146 B
      git diff      EMPTY

So the diff the brief asked to be stated entry-by-entry is **empty: zero
entries changed**. A regeneration that changes nothing cannot be a silenced
guard, and the one relocation it was expected to carry is already in.

### The guard still fires, proven by plant, at `402b10d68`

Regeneration makes a red test green, which is the shape of a silenced check, so
the plant is the evidence rather than the regeneration:

| world | analyzer | failing name-set |
|---|---|---|
| A — no plant | write paths 58, BYPASS 26 | *(empty)* |
| B — one new ungated write | write paths 59, **BYPASS 27** | `test_no_bypassing_call_site_is_new` |

Exactly **one new name**, none gone, and the failure message prints the planted
key in full:

    scripts/pc0252_planted_ungated_write.py::pc0252_planted_ungated_write::heyreach.create_campaign

Reverted: plant absent, baseline sha256 unchanged against the value read before
the plant, `git status` byte-identical to before (clean), name-set back to
world A's.

**The plant was an untracked file, deliberately.** 1245 of this tree's 1312
tracked `.py` files are CRLF on disk against an LF blob and read clean only
through git's stat cache; touching one makes it read ` M` permanently, and no
form of `git checkout` repairs it. `call_sites` in
`scripts/write_path_denominator.py` is an `os.walk` over `src` and `scripts`
with no `git ls-files` anywhere in it, so an untracked file exercises exactly
the same analyzer path, and its revert is an unlink.

## P10 — the brake's proof under integration

The same nine brake modules, run in three trees, name-sets read from unittest's
own `result.errors` / `result.failures` rather than parsed from `-v` output:

| tree | SHA | ran | red |
|---|---|---|---|
| the integrated tree | `5b8dfd108` | 61 | **5 ERROR, 0 FAIL** |
| the fixture repair | `c2883f479` | 61 | **none** |

The five reproduce exactly as recorded, all carrying one refusal —
`heyreach.create_list … requires a GateToken from providerwrites.grant(…). It
was called with NoneType.` — and among them is
`test_no_file_and_the_transport_is_reached`, the brake tests' own control.

The repair is a **fixture repair**: `git diff 5b8dfd108 c2883f479` is two test
files, +94/-9, and **no file under `src/`**. The fixtures mint a token the way
production callers do; `providerwrites` is not weakened, no test exemption is
added, `require_released` is untouched.

### The door was not relaxed

Measured outside the tests on `c2883f479`:

    perform(LINKEDIN_CREATE_LIST, …)  with no gate=
      -> WriteRefused: … requires a GateToken … called with NoneType
    the same call WITH grant(…)
      -> WriteRefused: no read-back supplied

So a token moves a call past the grant rung **only**; every later rung still
applies.

### The control, both directions, and its teeth

Unmutated, each test run alone so green is seen rather than inferred:

    test_no_file_and_the_transport_is_reached                     OK
    test_the_file_present_refuses_and_the_transport_is_unreached  OK

Two mutations of `src/haltfile.py`, each written as bytes with the module's
bytecode dropped in the same breath (see below), each reverted to a
sha256-identical file:

| mutation | byte delta | control killed | brake-pulled test killed |
|---|---|---|---|
| the brake refuses always | +49 B | **YES** | yes |
| the brake never refuses | +17 B | **no** | yes |

That pair is what makes the control a control rather than a test that reddens
for any edit to the file: the two mutations produce different kill-sets (17 and
18 names), and only the "refuses always" one reaches the control — which is
precisely the case the control's own docstring names, *a brake that refuses
everything proves nothing*.

## The revert discipline applied, and which rule it is

`qwen/0176`'s rule, landed in `LANE-qwen.md` as a proposal for
`_STANDING-RULES.md` and as `docs/qwen-tasks/stale_pyc_scan.py` on its own
branch — **it is not in `_STANDING-RULES.md`, measured, so it is applied here
by choice rather than by citation**:

> Delete the module's bytecode in the same breath as every write to its source
> — the plant AND the revert — because Python validates a `.pyc` on the
> source's whole-second mtime and byte size only.

Applied unconditionally on every write in both directions, and in addition:
every interpreter ran with `-B`; no revert used `git checkout --` (0176's S10
measured it as the most exposed revert path, and in a CRLF tree it flips line
endings besides); the byte delta of each mutation is stated above so the proof
is auditable afterwards. Both mutations here changed the file's length, which
is 0176's sufficiency condition (b) on its own — the rule was still applied.

## Criterion 9, per tree

| tree | SHA | criterion 9 |
|---|---|---|
| `origin/master` | `b1f290c84` | **UNKNOWN — no instrument.** Neither `src/haltfile.py` nor `scripts/exit_nine.py` exists there (`git cat-file -e` fails on both). |
| the pilotcaps lane tree | `402b10d68` | **UNKNOWN — no instrument**, same two files absent. |
| the integrated tree | `5b8dfd108` | **NOT MET** — `exit_nine.py --only 9`: 46 tests across eight brake modules, 5 failing. |
| the fixture repair | `c2883f479` | **MET** — 46 tests, 0 failing, shipped constant exercised and pinned by identity. |

### The fifth distinct reason, named

Criterion 9 has now failed for five distinct reasons. The first four were
properties of the code or of its fixtures: a planted violation the criterion
should have caught went undetected; the brake was absent from the tree that
would send; two lanes' greens could not both hold in one tree; and the brake
tests' own control could not execute there.

**The fifth is not about the brake at all. It is MET in exactly one tree, and
that tree cannot be merged, because the merge gate has no reference to be
measured against.** Re-measured here rather than inherited: `origin/master` is
`b1f290c84` by `git ls-remote`, and every full-suite reference tree in the
estate — `2bf7b8a57`, `cd8e00bc6`, `e9ae9e6b1` — is a strict **ancestor** of it,
with none at it or after it. The standing merge rule forbids gating a branch
against an older reference, because the previous merge's changes would then be
charged to this one.

So the brake, its tests, its control and its shipped-constant pin are all
sound, and the criterion is **satisfied and unlandable**. That is a different
problem from the four before it and it has a different fix: a full-suite
reference measured on `b1f290c84`.
