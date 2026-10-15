## 2026-10-15 — TASK 0065 — the halt fixed in the foreground: 0055's commit found, verified, not duplicated

Brief: `queue/glm/0065-fix-the-halt-in-the-foreground.md` (GLM-A). `_STANDING-RULES.md`
read first, as ordered. `DECISION-2026-10-15-three.md` §2 read: the operator ordered the
fix and named its shape (a safety write fails OPEN). No push, no merge, no lock release,
no other gate, no `CLIENT_CHANNEL_GAG`, no suitelock proposal, no provider/network call,
no other lane's worktree.

### The premise, corrected by measurement

The brief asserts "your 0055 did not apply it" and "there was no fix". There IS a fix:
`b77cd4b20` ("TASK 0055: the blank-email halt fails OPEN - bison.pause needs no
GateToken", 11:22:08, parent `1ea8105bf`), tip of `task-glm-halt-failopen-2026-10-15`,
local = origin. `git show --stat`: **1 file, `src/providerwrites.py`, +36/−12**;
`git rev-list 1ea8105bf..b77cd4b20` = exactly that one commit. What 0055 did NOT do was
record or certify it: no lane entry, no post-fix run, and its session died waiting on the
background suite (the standing-rules loss pattern). Everything below verifies the commit
the brief believed absent, rung by rung, on the trees.

### The shape, read out of the diff

The GateToken demand block in `_perform`'s NON-FACING branch is wrapped in
`if operation != EMAIL_PAUSE:` (`src/providerwrites.py:2600` at the tip). `EMAIL_PAUSE`
is `"bison.pause"` (`:152`), non-facing (`:428`). **No grant is minted anywhere** — the
sink simply does not demand one for the halt's verb; the wrong-token and raising-gate
cases fall out of the same skip. `grep` over the whole of `_perform` after the guarded
block: the only reads of `gate` are inside the block itself, so `gate=None` is never
dereferenced downstream. The ledger row (`by=`/`step=`), the readback,
`require_conditional_permission`, `require_resonate_os_campaign` and the REPEATABLE
handling all still run — measured below, not assumed. `heyreach.pause` and both
stop-leads stay demanded: only `bison.pause` is exempted.

### The ladder, both legs printed in the transcript

Red at the parent `1ea8105bf` (detached, this worktree):

- `py -3 -m unittest tests.test_a_safety_pause_fails_open -v` → **FAIL**,
  `AssertionError: None != 497`, refusal text = the demand itself ("bison.pause is a
  non-facing provider write and requires a GateToken ... It was called with NoneType"),
  BLANK-CONTENT-HALT-REFUSED emitted, `Ran 1 test` — red for the stated reason, not an
  import or environment problem (bind, watcher-module load and spy all succeeded).
- 0020 reproduction `...TheWatcherHaltsAndTheGuardRefuses.test_the_halt_actually_pauses_
  and_carries_a_write_scope` → **FAIL**, `AssertionError: None != 497` at
  `tests/test_a_blank_email_can_never_be_sent_again.py:354` — the exact failure TASK
  0020 recorded.

Green at the tip `b77cd4b20`: both tests **OK** (1 test each, ~0.04s). The test's
`presented.get("gate") is None` assertion held at the tip — the pause was performed with
NO token presented, so the fix is the sink-side skip the docstring demands, not a mint.
**Mutation proof**: the two trees differ by exactly `b77cd4b20` (one file), so fix
absent → red with the intended reason, fix present → green, both outputs printed.

### Blast radius — every other caller of what changed

All `perform(EMAIL_PAUSE, ...)` / `bison.pause` sites at the tip, each measured:

1. `scripts/bison_watch_loop.py:422` (the halt, no `gate=`): refused → performed. THE
   TARGET; pinned green by both tests above.
2. `scripts/nudge_487_scheduler.py:105` (no `gate=`, `by="operator"`, dry-run default,
   `--live` explicit): refused → performed. Behaviour changed for this second caller —
   in the safe direction: a pause of our own campaign 487, non-facing, and the
   ownership door is intact (next item).
3. `src/orchestrator.py:575` → `_perform_pause`: mints its own `grant(...)` — email leg
   unchanged (valid token before, demand skipped now); linkedin leg still demanded
   (`LINKEDIN_PAUSE ≠ EMAIL_PAUSE`).
4. `src/bisonfactory.py:2777`: calls `bison.pause_campaign` directly, NOT through the
   sink — untouched by both the demand and this fix (pre-existing direct call; widening
   to it is out of scope).

Safety direction pinned by whole modules at the tip:
`tests.test_an_internal_campaign_is_never_touched` — **59 tests OK** (274/327/328/352
refused before the network, ours reach the transport, unknown refused). In
`tests.test_the_stop_can_be_performed` + `tests.test_an_emergency_stop_is_not_refused_
by_its_own_history`: 8 failing/erroring names IDENTICAL at parent and tip (pre-existing
on this lineage, not the fix), plus exactly one flipped:
`StopButtonIsNotRefusedByItsOwnHistory.test_pause_after_resume_reaches_the_provider`
ERROR at the parent → OK at the tip — a pause the GateToken demand had silently broken,
now restored. **No changed outcome is a prospect-facing write**: `EMAIL_PAUSE` is
non-facing; a pause sends nothing to anyone.

### Commit

Nothing new to commit: verification found no defect in `b77cd4b20`, so the ordered
"smallest change" is that commit itself, already on the branch and on origin (local =
origin verified). The commit's own red/green claims are now independently reproduced
above. `git show --stat b77cd4b20`: `src/providerwrites.py | 48 +++++... 1 file changed,
36 insertions(+), 12 deletions(-)`.

pilotcaps certification of the fix (`DECISION-2026-10-15-three.md` §2 names them the
certifier) is still OUTSTANDING — nothing in `LANE-pilotcaps.md` certifies `b77cd4b20`;
their halt mentions are the 10-14 enforcement audit of the defect. This entry is the glm
lane's verification leg, not the certification.

### SUITE

(Running at entry time — this section is appended below, inside this same run, per the
brief's hard rule. Reference leg launched detached at `1ea8105bf`, branch leg at
`b77cd4b20`, both full runs with the machine-wide lock, outputs redirected unpiped,
nothing piped through a filter.)
