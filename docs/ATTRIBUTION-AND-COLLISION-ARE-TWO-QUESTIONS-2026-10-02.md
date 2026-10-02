# Attribution and collision were one question, and they are now two

**Branch** `task-one-os-authority` · **base** `4222ee88` · **2026-10-02**

**RESOLVED. Nothing is being asked here any more.** This document opened as an
escalation - five tests contradicted a first reading of decision 2 and were left
red rather than patched. The operator refined the decision, the refinement
resolved the conflict in the tests' favour, and all five now pass. It is kept
because the wrong turn is the useful part of the record.

## The decision, as refined

> "Atribucija: ne-OS povijest ne blokira i ne broji se kao naš touch. Kolizija:
> ako je osoba trenutno mid-sequence u bilo kojoj aktivnoj kampanji, OS ili ne,
> verdikt je HOLD do kraja te sekvence, ne STOP i ne DNC. To je doslovno 'all
> finished' iz account_policy."

Two questions that had been run together:

| | question | consults ownership | lives in |
|---|---|---|---|
| **ATTRIBUTION** | WHOSE campaign sent it | **yes** - this is what the authority is for | `osattribution.attribution`, `os_campaign_ids`, `our_heyreach_campaign_ids` |
| **COLLISION** | is somebody mid-sequence to this person RIGHT NOW | **no, never** | `collision.account_policy` |

Non-OS history does not block and does not count as our touch - that is
attribution, and the fail-closed rule stays there: an unreadable authority is
UNKNOWN, never "not ours", because unreadable-becoming-cold would hand a full new
sequence to everybody we have already written to.

A live sequence belonging to anybody is a HOLD until it finishes - that is
collision, and ownership is not an input to it.

## The wrong turn, recorded

The first implementation gated the mid-sequence STOP on the OS authority, so a
sequence on one of the operator's internal campaigns (274, 327, 328, 352) did not
block at all. Five tests went red. Three of them asserted the old rule
deliberately, two of those citing a real staging incident, so they were left
failing and written up rather than edited.

**That was the right process and the wrong conclusion, and the tests were right.**
What a mid-sequence check protects against is TWO SENDERS REACHING ONE PERSON IN
THE SAME WEEK - a deliverability and client-relationship problem that does not
care whose campaign the other one is. Attribution was the right question for a
different purpose and got borrowed for this one. Had those tests been "fixed" to
match the implementation, the protection would have been deleted and the suite
would have been green.

It is also not a new rule. The ALLOW arm already read *"emailed before, ALL
FINISHED, nobody replied"*. A campaign still running is not finished, so a live
membership simply fails that condition. HOLD was always what the account meant;
the STOP was the overstatement, because STOP says the account is answered and a
running sequence has answered nothing.

## What changed in the code

- `account_policy`: mid-sequence returns **HOLD**, and the ownership condition is
  gone. Its `os_campaigns` / `ledger_readable` parameters are removed - with
  ownership out of the branch they were dead.
- **The answered STOP moved ABOVE the mid-sequence arm, and had to.** Both arms
  used to return STOP, so their order changed only the sentence. With
  mid-sequence a HOLD, asking it first would DOWNGRADE an answered account -
  somebody who replied while a colleague is still mid-sequence would come back
  HOLD. A reply is terminal; a running sequence is a not-yet.
- `mid_sequence_campaigns` stays and now **reports instead of gating**: it names
  what is running and counts what it could not name, so an operator has somewhere
  to look. It cannot change the verdict, which is HOLD for any live membership
  including one whose `campaign_id` is missing - so a reader bug cannot turn a
  collision into an ALLOW.
- `nextaction`: `WAIT_IN_SEQUENCE` was keyed on `STOP and anyone_in_sequence`.
  STOP now means exactly "answered", so that test could never match again and
  every mid-sequence account would have fallen through to the generic
  `WAIT_ESTATE_HOLD`, losing the reason code that says why. STOP is asked first,
  then `anyone_in_sequence` carries the not-yet.

**HOLD blocks exactly as hard as STOP did.** `executionguard` requires `ALLOW`,
both factories test `in (STOP, HOLD)`, `nextaction` tests `!= ALLOW`. Nothing is
let through that was blocked before; what changed is the reason an operator reads
and the fact that the account is revisited when the sequence ends.

**This now AGREES with `classify`.** Step 2 of the operator's LEAD KLASIFIKACIJA
of 2026-10-01 holds a lead for anybody's live campaign, ownership-blind by design.
For one commit `account_policy` asked whose campaign it was while `classify`
refused to - two gates answering by opposite principles. They now answer alike,
and the inconsistency flagged in the first version of this document is closed
rather than merely noted.

## The five tests: renamed, re-verdicted, all passing

None was deleted and no assertion was weakened; each asserts the collision rather
than ownership, and each gained a twin on an OS campaign so the pair cannot pass
while owner still decides.

| was | is | verdict |
|---|---|---|
| `test_in_sequence_is_refused_by_name` | `test_a_live_sequence_is_a_collision_whoever_is_running_it` | refuses (unchanged) |
| `test_the_nine_real_cases_as_a_fixture` | unchanged | refuses (unchanged) |
| `test_a_colleague_mid_sequence_still_stops_the_account` | `test_a_colleague_mid_sequence_holds_the_account_whoever_is_sending` | STOP → HOLD |
| `test_mid_sequence_still_outranks_everything` | `test_mid_sequence_outranks_an_ambiguous_ending` | STOP → HOLD |
| `test_somebody_mid_sequence_stops_it` | `test_somebody_mid_sequence_holds_it` | STOP → HOLD |

One more surfaced during the rework: `test_a_stop_outranks_a_bounce` asserted STOP
for in-sequence-plus-bounce. Both arms are HOLD now, so a verdict-only assertion
there **could not fail**. It is `test_a_live_sequence_outranks_a_bounce_in_the_reason`
and asserts the precedence where it is still visible - the reason an operator
reads.

## PII removed, and what is still out there

`tests/test_staging_refuses_colliding_contacts.py` carried **four real EmailBison
lead ids** - one in the docstring the operator named, three more in the module
header and sibling docstrings. All eight occurrences were prose; no assertion ever
read one. They are now `LEAD-A` … `LEAD-D`, with a header note recording that the
measurement was real and that real identifiers were removed rather than silently
dropped. Campaign ids (327, 352, 481, 487) stay: those are the operator's own
campaigns, not people.

**STILL PRESENT ELSEWHERE, NOT FIXED HERE - flagging rather than touching
historical measurement docs:**

- `docs/BISON-COHORT-LIVE-2026-09-15.md:106` pairs a lead id with a **real
  person's full name**. This is the worst of the set and the one worth deciding
  about first.
- `docs/HISTORICAL-ESTATE-2026-09-15.md:50`, `docs/qwen-tasks/DONE/TASK-015-*.md:16`
  carry the same lead ids.

## Proof

Both mutations required, both on effect, `__pycache__` wiped before each:

- **HOLD → STOP** (the old rule): 14 tests red, including every
  `OwnershipDoesNotDecideACollision` case and both renamed HOLD assertions.
  **The byte count was IDENTICAL** - `HOLD` and `STOP` are the same length - so
  this one was verified by grep and by effect, never by file size.
- **the arm deleted** (so a live sequence ALLOWs): 19 of 100 red.

An earlier mutation attempt did not apply at all because the file is CRLF and the
pattern used `\n`; the `assert` on the match count caught it and no conclusion was
drawn from the run that followed.

`TheCollisionArmAsksNoAuthorityAtAll` proves the separation structurally rather
than behaviourally: both halves of the authority are replaced with a function that
raises, and the verdict is unaffected. Its control replaces the same names for
`osattribution.authority` and asserts that one DOES raise - otherwise the test
would pass while proving only that the patch missed.

## Per-module name-set diff

A full `tests.offline` run was **not** used: one full suite is running and the
machine is serialised. 61 modules, each in its own process - every module naming
`account_policy`, `os_campaign_ids`, `our_heyreach_campaign_ids`,
`mid_sequence_campaigns`, `campaign_key`, `osattribution` or `anyone_in_sequence`,
plus every module driving a caller of `account_policy`. 18 of the 61 carry
failures in the master 221-name baseline of 2026-10-02, which is how the
pre-existing ones were identified rather than assumed.

| tree | commit | tests reached | failing names |
|---|---|---|---|
| this branch | `bb1f38bb` | 1490 | **73** |
| base | `4222ee88` | 1432 | **73** |
| master | `87a77eba` | 1356 | **73** |

**Against base `4222ee88`: 0 newly failing, 0 no longer failing.**
**Against master `87a77eba`: 0 newly failing, 0 no longer failing.**

The three failing-name SETS are identical, not merely equal in size - compared as
sets of names, because `73 == 73` would also hold for a different 73 and that has
happened on this repository before. The refinement takes the branch to exact
parity: the five regressions the ownership version introduced are gone, and
nothing else moved in either direction.

The ownership version, for the record, measured **+5 / −0** against both
references - the five tests written up above.

Two modules confirmed **already red at `00b49197`** and not caused by this branch:
`test_heyreachfactory_ensure_leads` (4F/13E) and
`test_the_second_activation_at_an_account_is_refused` (3F).

A full-suite name-set diff is still owed and will be run once the operator says
the machine is free.

---

## The authoritative full-suite run

Taken on `3c8f4f84` (this branch merged with master `6f3aeda2`), under the
machine-wide suite lock, after waiting for two tracks ahead of it.

    status=FAIL  exit_code=1  wall_seconds=2347.3  timed_out=False
    results_reached=14773   failures=231   failures_are_partial=False
    result_line=FAILED - 165 failure(s), 70 error(s) of 14818

`timed_out=False` and `failures_are_partial=False` are the two fields that make
the number usable: a truncated run's names are a prefix, not a set, and must
never be diffed against a complete one.

**Compared by NAME SET against the committed FULL baseline** -
`docs/state/SUITE-BASELINE-2026-10-02-FULL.json`, 231 names at `87a77eba`, same
method (one process, `tests.offline -v`), status COMPLETE:

    newly failing    : 0
    no longer failing: 0

The two 231-name sets are IDENTICAL. `231 == 231` was not treated as the
answer - a different 231 compares equal on count, which is the error this
repository has made three times in one day.

Three controls, all passing:

  - parsed name count == the count the runner itself declared (231), so the
    parser is not silently dropping or inventing lines;
  - reference set size == the total the baseline declares (231);
  - the comparison's own positive control: the reference diffed against itself
    is 0 gone / 0 new, and with exactly one name swapped it is 1 gone / 1 new.
    Without this, a comparison that always returned "no differences" would look
    like a clean result.

**The phantom is ABSENT from both sets.** `...certifies_at_staging` /
`self_stamp` appears in neither my run nor the reference, so the pinned clock
holds on this branch too. It is not a finding.

### What this run does and does not establish

It establishes that this branch adds no failure to the tree it was measured
against, and - because `6f3aeda2`'s delta is already merged into it - that
`6f3aeda2` added none either, since the set is unchanged from `87a77eba`.

It does NOT establish a comparison against master as it stands now. Master
advanced to `e9ae9e6b` (*Merge task-939-keywordless-refusal*) during this run,
adding 113 lines to `src/replies.py` and 95 to `tests/test_replies.py`. Both
sets here contain
`test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence`, and
that delta plausibly changes its outcome - so current master's failing set may
not be these 231. Nobody should assume it is without measuring it.

### Why no master reference run exists for `6f3aeda2`

The run that was expected to serve as the shared reference held the lock from
15:19 as PID 117216 in the `scratchpad/measure` worktree. It produced NO
`suite_verdict.txt` anywhere in that tree - searched tree-wide, not just
`work/`, which matters because the runner writes the verdict beside
`scripts/`, not into `work/`. Its wrapper logs were truncated to 0 bytes.

`measure` is the merge sequence's gate worktree and it TRACKS master: verified
at `6f3aeda2` at 15:40 and found at `e9ae9e6b` by 16:05, with `src/replies.py`
rewritten under it. A reference bound to a worktree another track can check out
is not a reference; it has to be a frozen checkout at a named SHA. The 15:40
verification was correct and was stale within twenty-five minutes, which is the
point - the defect is structural, not a misreading.

Also observed in first production use: the lock's waiting message prints
`branch='HEAD'` for a detached worktree, so it names nothing a reader can act
on. Three separate parties investigated who held the lock as a result.
