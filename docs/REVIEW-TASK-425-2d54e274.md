# Second independent review — `task-425-one-account-dry-run` @ `2d54e274`

**Branch head reviewed: `2d54e274f1dbf646907073047ede73b5999ab273`**
(`origin/task-425-one-account-dry-run`). Reviewed 2026-09-28, read-only, in a
private worktree on branch `review-task-425-2d54e274`. Nothing was merged,
nothing was pushed to the task branch.

**VERDICT: MERGE** `2d54e274f1dbf646907073047ede73b5999ab273`, as a true
`git merge` and never as a squash-replace, with three follow-ups filed (below).

The four acceptance criteria were not re-litigated. The question answered here
is only: **is this branch safe to merge to master as it stands?**

---

## 0. A correction to the review brief, load-bearing

**CLAIM** `origin/master` is not `4b1fb0c6`, and `4b1fb0c6` is not the fork point.
**AUTHORITY** `git rev-parse`, `git merge-base`, in this worktree.
**MEASURED AT** 2026-09-28 13:05 and re-fetched 14:05.
**STATE** VERIFIED.

    origin/master        dcc21701 at 13:05, 1d9b8f6c at 14:05  (it is moving)
    merge-base           a49c84c8f704301df44bf234dede52279c6796df
    branch vs master     23 commits ahead, 13 BEHIND

`4b1fb0c6` is an ancestor of master, not the fork point. Every diff below is
therefore taken against the **merge base `a49c84c8`**, which is the only base
that shows what the branch actually changed. Diffing against `4b1fb0c6`
attributes 13 of master's own commits to the branch as deletions.

---

## 1. Scope drift and junk — NONE FOUND

**CLAIM** All 16 changed files answer to TASK-425 or to a bug its verification exposed.
**AUTHORITY** `git diff --stat a49c84c8 2d54e274`, and reading each hunk.
**STATE** VERIFIED.

    docs/TASK-425-*                        3 files   criterion 4 artifact, findings, operator summary
    docs/state/PROBLEM-REGISTER.md         +201      ISSUE-050..055, the canonical register
    scripts/task425_*.py                   4 files   the harness, the artifact writer, the mutation proof
    src/sequencegate.py                    +410      criterion 3: the ladder as a gate
    src/bisonfactory.py                    +133/-11  wires the offer and the thread map into the gate
    src/generate_campaign.py               +104      plumbs the offer to the writer and the gate
    src/campaignstrategy.py                +45       carries step_objectives; json.loads -> llm.parse
    src/copystages.py                      +106      writer prompt, tightened
    src/offers.py                          +19       messaging_rules() accessor
    tests/ (2 files)                       +1022     24 tests, with controls and a booby trap

Two changes are not criterion-3 wiring and both earn their place as bugs the
verification exposed:

- `campaignstrategy._call_model`: a bare `json.loads` crashed the entire run on
  the first fenced model answer, outside the per-contact `try`. Replaced with
  the canonical `llm.parse`. **This is not a loosening** — `llm.parse` still
  refuses prose and non-object answers; only a fence stops being a crash.
- `copystages.py` is **prompt text only** and every edit TIGHTENS: LinkedIn cap
  600 -> 280 chars (600 was a number no gate enforces; the gate that actually
  applies caps at 300), a 45-word floor, and the previously-untold curly-quote,
  claims and repetition rules. The single removal is the style note "shorter
  than email 1 where they can be", which is replaced and explicitly demoted.

**No cherry-pick is recommended. There is no junk file to leave behind.**

---

## 2. Silent revert of master — NONE. The change sets are DISJOINT.

**CLAIM** The branch reverts nothing on master.
**AUTHORITY** `comm -12` over both changed-file sets since `a49c84c8`; blob hashes.
**STATE** VERIFIED.

The intersection of {files master changed since the fork} and {files the branch
changed since the fork} is **empty**. The three named regression targets are
byte-identical between `2d54e274` and `origin/master`:

    src/copylint.py    1f56625858a6f9c4f3d5cae051966731853594af   IDENTICAL
    src/packfacts.py   853cfca53fb845339b7c3d6ec8df529f6e94d662   IDENTICAL
    src/killswitch.py  1ef05aeb7acbb08a06f35e65f39fcf60baf0a7b0   IDENTICAL

`CLIENT_SUPPLIED` and `packfacts.pack_for` are present and unmodified;
`copylint._traces` is present with its TASK-330 comment intact.

**The one thing to get right at merge time.** The branch is 13 commits behind,
and those commits include `9726b2d3` "DISABLE the automatic weekly client post,
fail-closed" plus its test. The branch's copies of those files are byte-identical
to the **fork point**, i.e. the branch never touched them:

    src/weeklyreportwatch.py      fork 3a3f5a56 == branch 3a3f5a56, master b0b9b8ff
    scripts/weekly_report_loop.py fork bb6c984a == branch bb6c984a, master e3737bb3

A true `git merge` therefore keeps master's fail-closed version. A squash,
a `reset --hard` to the branch, or any "replace master with the branch"
operation **would delete the killswitch disable and its test**. Merge, do not
replace, and re-assert those two blob hashes after merging.

---

## 3. Gates — one real loosening, disclosed; the new checks can fail

### 3.1 The new `step_objectives` / `ai_*` checks are not inert

**CLAIM** Every new refusal branch can fail, and the branch's tests catch it when it cannot.
**AUTHORITY** My own mutation harness, independent of `scripts/task425_verdict_mutations.py`, asserting the file changed on disk before each run.
**STATE** VERIFIED (5 of 5 disable-mutations killed).

    M1 order check            -> if False   KILLED (failures=1)
    M2 coverage check         -> if False   KILLED (failures=2)
    M3 ai_one_per_message     -> if False   KILLED (failures=2)
    M4 ai_is_supporting       -> if False   KILLED (failures=2)
    M5 subject repetition     -> if False   KILLED (failures=2)

The branch supplies its own negative controls — the in-order ladder must PASS,
and `test_the_booby_trap_actually_fires` proves the zero-write claim — so the
refusals are not the artefact of a gate that refuses everything.

### 3.2 `no_repetition/subjects` IS weakened on the production path — and says so

**CLAIM** With the thread map `bisonfactory` now supplies, this check cannot fail for any cadence in this repository.
**AUTHORITY** Direct measurement against `sequencegate.check`.
**STATE** VERIFIED.

    master behaviour (no thread map): FAIL "two of the 5 thread subjects are the same"
    branch, one-thread map          : no failure; WARN "this cadence opens 1 thread(s)
                                      ... duplicate thread subjects could NOT be checked"
    branch, two threads, dupes      : FAIL "two of the 2 thread subjects are the same"

So the check is **structurally unreachable on every configured cadence** (all
declare one thread starter) but **is not structurally incapable of firing** —
it fires at two or more threads. This is the second attempt: the first version
dropped follow-up subjects and was silently inert, an adversarial review caught
it, and the replacement's disclosure is the fix. The warning is real, not
cosmetic: `report_lines` emits warnings, and `_refuse_sequence_gate` puts
`report_lines` into the `FactoryRefused` message the operator reads.

The underlying justification is sound — `EMAILBISON-COPY-REQUIREMENTS.md`
requires same-thread follow-ups, so em2 legitimately repeats em1's subject and
the old check was refusing correct copy. **Accepted, with the loss named.**

### 3.3 Holes I found in the NEW checks (limits, not regressions)

Master enforced `step_objectives` not at all, so none of these is a weakening of
anything that exists today. They are recorded so nobody reads a pass as more
than it is.

- **A partial shuffle passes.** The order test refuses only 100%-against-0%.
  Measured against the real `OFFER-A-ECONOMIC-BUYER`: with rung 1's argument at
  em3 and rung 3's at em1, **each keeping one word of its own rung, the gate
  raised no `step_objectives` failure at all.** Remove the retained word and it
  refuses both steps by name. My mutation M6 (widening back to `best != rung`)
  SURVIVED the branch's tests, so the necessity of the narrowing is justified
  only by real generated copy measured on 2026-09-28 and is **UNPROVEN by any
  test in the branch**.
- **Offer B rung 2 is not order-testable.** Its objective is the single word
  "time", which also appears in rung 4's text, so it has no distinctive
  vocabulary and the check warns and skips. Order is enforced on 3 of 5 rungs
  for Offer B (2 untestable, 4 conditional) and 4 of 5 for Offer A.
- **Offer A rung 1 hangs on one stem** (`visi`).
- **`ai_is_supporting` is inert on every LinkedIn step.** Measured: "Report
  Intelligence" in `em1` is refused; the same name in `msg1` raises nothing,
  because `connect`/`msg1..3` carry no rung and the loop `continue`s first. The
  gate warns "carries no ladder rung"; but `copystages.py` now tells the writer
  that naming a capability "anywhere else is refused by
  `sequencegate.ai_is_supporting`", which for LinkedIn is not true.
  `ai_one_per_message` does apply to LinkedIn. On the staging path LinkedIn copy
  is not handed to the gate at all.
- The coverage half is a one-shared-stem presence test. Disclosed in-code.

### 3.4 Two latent defects the wiring introduces

- **Argument-order bug.** `bisonfactory._offer_for` calls
  `_gc._select_offers(client, persona)`; the parameter is `segment_key`. It is
  harmless **only** because every offer in the library is `segment: all`. The
  first offer that declares a real segment will make the staging gate silently
  select nothing and report the ladder as unchecked.
- **Cross-tenant coupling.** `_refuse_sequence_gate` now reads the
  single-tenant Productive offer library for **every** client and refuses
  staging against Productive's ladder. `generate_campaign` explicitly declines
  this exact fault ("a worse fault than the one it fixes"); the staging path
  takes it. Latent today — only `productive` and `demo` exist — and the branch
  itself records it as `ISSUE-053 CONFIRMED, NOT FIXED`.

### 3.5 A config that now misstates its own enforcement

`config/clients/productive-offers.yaml` is **untouched by the branch** and still
reads:

    enforced_by: sequencegate checks step_objectives
    # ENFORCEMENT IS NOT YET BUILT. ... sequencegate does not read
    # step_objectives today. ... nothing refuses a message that ignores it.
    enforcement_status: DATA_ONLY_NOT_YET_ENFORCED

That is now false, and it is the exact inverse of the defect the branch set out
to fix — a rule the file the operator edits describes wrongly. One-line follow-up.

---

## 4. Suite — 0 new failures attributable to the branch

**CLAIM** The branch adds no new failing test name.
**AUTHORITY** Full `python -m unittest discover -s tests -v` at `2d54e274` from Git Bash, compared to `docs/state/SUITE-BASELINE-2026-09-26.txt` AS SETS, plus a negative control at `origin/master`.
**MEASURED AT** 2026-09-28, 13:52–14:38.
**STATE** VERIFIED.

    Ran 13604 tests in 2773.7s
    FAILED (failures=96, errors=25, skipped=15, expected failures=18)
    121 distinct failing names   vs   128 in the baseline
    NEW vs baseline: 4        CLEARED vs baseline: 11

**A METHODOLOGY FAULT IN MY OWN FIRST RUN, AND WHAT I DID ABOUT IT.** My first
full run was started before the mutation harness, and the harness rewrote
`src/sequencegate.py` on disk WHILE that suite was running. Any test module
imported after a mutation would have read mutated source. That run was
**discarded**, the restoration was verified (`git status` clean, blob identical
to `2d54e274`), and the suite was re-run with nothing else touching the tree.
Only the clean run is reported above. The contaminated run was also ~4x slower
from contention, which is how it surfaced.

The 4 names absent from the baseline were each run at `origin/master`
(`1d9b8f6c`), **without the branch**, and all four fail there too:

    test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
    test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain
    test_an_offer_cannot_be_invented.TestApprovalRefusal.test_approval_status_is_not_defaulted_to_approved
    test_the_cadence_reacts_to_what_the_prospect_did.ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too

None names a file the branch touches. The hygiene failures name
`docs/qwen-tasks/DONE/TASK-330-*.md` and five pre-existing test fixtures; the
offer failure names `productive-offers.yaml`, which the branch does not modify.
They are drift between the 2026-09-26 baseline and today's master, which
CLAUDE.md predicts. **The baseline is stale and should be regenerated on master
as a separate task** — it is now 7 names and two days adrift.

---

## 5. Production state and providers — ZERO WRITES

**CLAIM** Nothing in the branch wrote production state or reached a provider.
**AUTHORITY** mtime on the canonical files, before and after every command I ran.
**STATE** VERIFIED.

    work/queue.jsonl      mtime 2026-09-28 12:38:18   (my first command ran 13:05)
    work/campaigns.jsonl  mtime 2026-09-26 21:05:08
    checked again at      2026-09-28 14:17 — unchanged

Supporting evidence: `tests/base.QueueTest` redirects `QUEUE` and `OUT` to a
`mkdtemp`; the harness sets `os.environ["OUT"]` to a temp dir and pins
`sending.live: off`; `generate.run(live=True)` means "generate", not "send"
(`src/generate.py:2645`); `bisonfactory.stage`/`heyreachfactory.stage` are
called `live=False`; and the refusal in `_refuse_sequence_gate` is raised
**before** any provider write.

The tracked 7,092-line artifact was scanned: the only hostnames in it are
`brightmoor.test` (fixture) and `api.emailbison.com` (the tripwire URL); the only
addresses are `ada@`/`grace@`/`hedy@brightmoor.test`; no secret-shaped string
matched. No real prospect data is committed.

---

## 6. Follow-ups to file (none of them blocks this merge)

1. `config/clients/productive-offers.yaml`: `enforcement_status` and the comment
   under `enforced_by` are now false. One-line fix.
2. `bisonfactory._offer_for` passes `client` where `_select_offers` takes
   `segment_key`.
3. `copystages.py` overstates `ai_is_supporting`, which does not reach LinkedIn
   steps — and the order test's narrowed threshold has no test proving the
   narrowing was necessary (my M6 survived). A test for the partial-shuffle case
   would close both.
4. Regenerate `docs/state/SUITE-BASELINE-2026-09-26.txt` on master.

---

## What I attacked and did not find

- A second `no_repetition`-class loosening: attacked all five new refusal
  branches with disable-mutations; all five were killed by the branch's tests.
- A silent revert: change sets are disjoint and the three named fixes are
  byte-identical to master.
- A provider or production write: refuted by mtime, twice.
- PII or credentials in the tracked artifact: refuted by scan.
- Scope drift: the two non-criterion-3 changes are a crash fix and a
  tightening-only prompt edit.

The strongest thing I found is §3.3 — the order test passes a genuine rung
swap when each step keeps one word of its own rung — and it is a limit of a
check that did not exist on master, not a regression. It does not block.
