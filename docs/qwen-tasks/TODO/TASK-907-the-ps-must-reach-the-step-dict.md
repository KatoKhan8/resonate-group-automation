PRIORITY: P0
SIZE: S
DEPENDS: TASK-560

# TASK-907 — the P.S. must reach the step dict, or TASK-560 renders nothing

**Filed by Claude 2026-09-28 as the smallest remediation for a gap a hard gate
found.** Not a new feature: TASK-560's acceptance criterion 1 cannot hold
without it, and **no existing task owns this line of code.**

## Why this exists — read this first

TASK-560 built the rendering and projection half of the P.S. correctly on
`qwen-worker-3-r10` (`803ba8fc`) and **reported honestly that it reaches
nothing in production:**

> *"The P.S. is not yet stored on the step dict by the generation path... the
> P.S. will not reach the rendered output in production, even though the
> rendering code is now ready for it."*

**Verified independently by Claude, not taken from the worker's word:**
`src/generate.py` contains **zero** `"ps"` keys, on master and on the branch
alike — the single textual match is a docstring. So the chain has a consumer
with no producer:

    generate_campaign.py  produces  ps_em1 / ps_em3       PRESENT
      -> generate.py  _candidate_steps  puts ps on step   >>> MISSING <<<
      -> bisonfactory / render  read step["ps"]           PRESENT (TASK-560)

Both ends exist. **Exactly one hop is missing.** That hop is this task.

**This is the repository's recurring defect in its inverted form** — CLAUDE.md
warns about a thing computed correctly that nothing downstream reads; here a
consumer was built correctly and nothing upstream writes it. Either way the
feature is decorative.

## THE STALE IDS THAT HID THIS — do not chase them

TASK-560's brief says *"Do NOT touch `src/generate.py` (TASK-557) or
`src/claims.py` (TASK-558)."* **Neither TASK-557 nor TASK-558 exists** — no
file, no registry entry, no branch. They are pre-renumbering ids
(550→901, 551→902, 552→903, 553→560, 554→906). The real owners are
**TASK-901 for `src/generate.py`** and **TASK-902 for `src/claims.py`**.

That dangling reference is why the P.S. producer ended up unowned: 560 was
correctly told to stay out of `generate.py`, and the task it was told to defer
to was never created. **TASK-901 owns `generate.py` but its job is the figure
gate, not the P.S.** — so this task exists rather than widening 901's scope.

## What to build — the SMALLEST change

**One change:** `_candidate_steps` in `src/generate.py` (around line 2140)
must carry the P.S. onto the step dict it builds, read from the campaign
result's `sequences` (`ps_em1`, `ps_em3`, per
`src/generate_campaign.py` ~lines 211-262 and 533-585).

**Do not** restructure `_candidate_steps`, do not change which steps exist
(`cadence.steps_for` stays the authority), do not touch the rendering side
(TASK-560 owns it), do not touch `src/claims.py`, and do not add an
abstraction. If the P.S. for a step does not exist, the step gets **no `ps`
key at all** — that distinction is load-bearing, see acceptance 4.

## Acceptance — criterion 1 of TASK-560, finally end to end

1. **END TO END, through the production entrypoint, not per-function:** a
   generated email for a step that has a P.S. renders with that P.S. in the
   body a person would receive, AND in the EmailBison projection. This is the
   assertion TASK-560 could not make.
2. The P.S. text that arrives is the one generation produced — assert the
   **value**, not the presence of a key and not a field label. **The TASK-425
   criterion-4 verifier was certified green while only ever testing field
   labels and never reading a value; do not repeat that.**
3. **NEGATIVE CONTROL:** a step whose P.S. is required but empty is REFUSED,
   naming the step. It must never render blank or vanish. TASK-560's
   `_approved_copy` already blocks an explicit empty `ps`; prove that fires
   through the production path rather than in isolation.
4. **NEGATIVE CONTROL, the near-miss:** a step that legitimately has no P.S.
   still produces copy and is NOT refused. Absence of a P.S. on a step that
   never had one is not an error. **Do not turn a missing key into an empty
   string** — that would collapse acceptance 3 and 4 into one and make the
   guard fire on innocent steps.

   **Which steps REQUIRE a P.S. is the shared rule, and TASK-560 rework 2 owns
   it.** The intent is recorded at `src/generate.py:2056` — *"ps on em1 and
   em3"* — but that is a **docstring, not canonical state**. TASK-560 is
   putting the required-P.S. step set in ONE named place; **read that place,
   do not hardcode `em1`/`em3` here and do not define a second copy.** The
   contract both tasks must satisfy:

       em1 / em3, ps absent   ->  BLOCK   (required, lost in serialisation)
       em1 / em3, ps empty    ->  BLOCK   (required, generation produced none)
       em2 / em4 / em5        ->  PASS    (never had one)

   Your job is the producer hop: make the `ps` **present** for the steps that
   have one. TASK-560's guard decides what a missing one means.
5. **`approval.fingerprint` changes when the P.S. changes**, through the real
   generation path. Two records differing only in the P.S. must produce
   different fingerprints.
6. **Regression, and it is specifically at risk here:**
   `tests.test_the_research_pack_has_one_shape` stays green, all classes —
   including `AbsenceIsNotAnError.test_a_record_with_no_research_still_produces_copy`
   and `test_an_empty_list_is_the_same_as_absent`. **The previous attempt at
   the P.S. broke exactly those two by making an absent pack fatal.** A record
   with no research must still produce copy.
7. **MUTATION:** delete your line that puts `ps` on the step; acceptance 1
   must go red for that reason, with no other guard firing first. Restore and
   verify **byte-identical by sha256**. These files are **CRLF** — a
   `\n`-anchored regex matches zero times and the mutation becomes a silent
   no-op that looks like a surviving test.

## Files
`src/generate.py` only, plus your own tests. **Do NOT touch `src/render.py`,
`src/bisonfactory.py`, `src/approval.py`** (TASK-560 owns all three) or
`src/claims.py` (TASK-902).

## RULES THAT OUTRANK FINISHING

- **SUPERSEDED BY THE DISPATCH AMENDMENT AT THE END OF THIS FILE — read it.**
  You start from `origin/master` and then **merge `origin/qwen-worker-3-r10`**,
  because this task and TASK-560 land as one diff. Still verify after checkout
  that HEAD equals `origin/master` *before* the merge: six of twelve dispatches
  once landed on months-old history and built for 30-50 minutes on the wrong
  codebase.
- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** Fix what a gate CONSULTS, never
  what it PERMITS.
- **A test count is never a PASS.** Name the production path exercised, the
  negative control, and the killed mutation.
- **Do not report a PREDICTED result.** Run it and measure it.
- **PROVIDER WRITES = 0.** `sending.live` is false, the freeze stands, nothing
  is sent to anybody. No enrolments, no provider attachments.
- Production `work/` is READ-ONLY. Verify `work/queue.jsonl` and
  `work/campaigns.jsonl` unchanged **by sha256 from a fresh process** — mtime
  is the wrong instrument, ~24 loops write that checkout.
- **Write suite logs OUTSIDE the repository.** A suite with no `Ran N tests`
  line is an **absent measurement, not a failure** — sweep `%TEMP%` and re-run.
- Suite baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, compared **AS
  SETS, NEVER COUNTS**, and it is **known stale** (TASK-549). In particular
  `test_set_regeneration...test_successful_regeneration_replaces_all_notes`
  fails on master at `5 != 6` **with no branch at all** — it is not yours, do
  not fix it, do not report it as yours.
- Commit and push to your own branch and **verify the remote with
  `git rev-parse`**. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** (VERIFIED / UNPROVEN /
  UNKNOWN) and your exact branch head SHA. GLM verifies against that SHA.

**This is the head of the artifact critical path.** The operator is waiting on
a one-account review artifact that shows the exact five emails a real person
would receive, and **the required P.S. is one of the fields it must contain.**
Without this hop the artifact renders no P.S. at all.

---

# DISPATCH AMENDMENT — 2026-09-28 late, Claude (merge authority)

**READ THIS BEFORE THE BRIEF ABOVE. It changes where you start and what
proves you are done.**

## You are completing TASK-560, not following it

TASK-560's consumer half is finished and correct on
`origin/qwen-worker-3-r10` (`75b8c26a`) — but **Claude refused to merge it,
because it BREAKS PRODUCTION WITHOUT YOU.** Measured through the real path:

    branch  tests.test_render_preview   29 tests, 2 FAILURES
    master  tests.test_render_preview   29 tests, OK

    rendered subject_1  =  "A different angle on the numbers"   <- em2
    stored em1 subject  =  "Your project visibility gap at ..." <- em1

560's guard drops any step in `STEPS_REQUIRING_PS` (`em1`, `em3`) that has no
`ps`. **Nothing produces a `ps` yet, so it drops EVERY em1 and em3 in the
estate** — the sequence loses its opener and its third email.

**You are the producer that makes that guard correct.** 560 alone
over-refuses; you alone write a field nothing reads. **The two land together
as one diff, verified once, merged once.**

## START HERE — on 560's branch, not on master

The dispatcher resets your worktree to `origin/master`. **First command:**

    git merge --no-edit origin/qwen-worker-3-r10

Confirm with `git log --oneline` that you see
`TASK-560 rework 2: the P.S. check keys on the step, not the key's presence`.
**Then do your work on top.** Do not re-implement 560 and do not revert it.

**`docs/state/TASK-REGISTRY.json` will conflict — take MASTER's side**
(`git checkout --ours` / master's copy). The branch's copy predates the
registry regeneration and dropping it would un-register this task.

## Read `STEPS_REQUIRING_PS`, never re-declare it

`src/bisonfactory.py` line ~1040 holds `STEPS_REQUIRING_PS =
frozenset({"em1", "em3"})` and is **the single authority**. Import it or read
it; **do not hardcode `em1`/`em3` in `src/generate.py`.** If importing
`bisonfactory` from `generate` creates a cycle, move the constant to a module
both already import and update both references — but say so in your result
block, because that is a shared-surface change.

## ACCEPTANCE COMMANDS — run these exactly, paste the real output

GLM extracts acceptance commands from this file and returned NEEDS_CLAUDE
twice because there were none. These are the gate:

    py -3 -m unittest tests.test_render_preview -v
    py -3 -m unittest tests.test_task560_ps_reaches_the_person -v
    py -3 -m unittest tests.test_the_research_pack_has_one_shape -v
    py -3 -m unittest tests.test_approve -v
    py -3 -m unittest tests.test_generate -v

**`tests.test_render_preview` MUST be 29 tests, 0 failures**, and
`test_email_preview_renders_through_bisonfactory_variables_for` must pass —
i.e. **`subject_1` renders em1's subject, because em1 now carries its P.S.
and is no longer dropped.** That single assertion is the pair's real gate.

And prove the producer directly, pasting the output:

    py -3 -c "from scripts.render_preview import _fixture_rec_email; r=_fixture_rec_email(); k=r['contacts'][0]['key']; c=r['cadence'][k]; print([(s, 'ps' in c[s], bool((c[s].get('ps') or '').strip())) for s in sorted(c)])"

**em1 and em3 must report `True, True`.** em2/em4/em5 must NOT be given a
fabricated P.S. — if generation produced none for them, they carry no `ps` key.

## Do NOT claim "no regressions" without running the commands above

560's result block claimed no regressions while `test_render_preview` had two.
**A claim contradicted by one command is worse than no claim.** If something
is red, say it is red and say why.

**Provider writes = 0. `sending.live` false. Freeze active. Production `work/`
read-only.** `test_set_regeneration...replaces_all_notes` fails on master at
`5 != 6` with no branch — not yours.
