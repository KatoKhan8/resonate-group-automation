

## TASK 0060 — 2026-10-15 14:40 — closed late: every proof re-derived, and the neighborhood run twice (glm-a)

0060 ran 10:04–11:08, committed its six tests, and wrote nothing here; the
watcher dispatches forward, so the only surviving account was its 2,416-byte
stdout log. TASK 0063 ordered this close. **Nothing below is pasted from
0060's artifacts**: every proof, run and diff was re-executed in this session
today (2026-10-15, 14:20–14:36) and names the SHA it was measured on. Where
the surviving log could not carry a fact, the full 0060 session transcript
(`~/.claude/projects/C--Users-Zvonimir-Desktop-wt-glm-review-2026-10-14/
0270e11e-393d-45ba-9d16-9c2d7567d863.jsonl`) was read for it — that is a
record, not a measurement, and is labelled as one.

The worktree was found detached at `1ea8105bf` (0055's leftover) and
returned to the branch before any measurement. **This is 0064's step-4 end
state, already accomplished — 0064 need not checkout again.**

### 1. The commit and its six controls — SHA `93162471d`

`TASK 0060: six smallest honest tests for the next uncovered controls`,
parent `9718023a6` (0040), on top of `6caa9ea58` =
origin/task-glm-review-2026-10-14. `git show --stat`: six new test files,
**426 insertions(+), zero src files touched**. The controls, by name:

1. **a refused pause** — `src/web/api.py:3177`, an already-paused campaign
   raises `ActionRefused` before any transport is touched.
2. **the pause executor propagates a refused write** —
   `src/orchestrator.py:607-613`, `_perform_pause` lets `WriteRefused`
   escape rather than swallowing it into a stopped-result.
3. **a positive reply holds the account and suppresses nobody** —
   `src/accountpolicy.py:96`, the `("reply.on_positive", HOLD, ACCOUNT, …)`
   policy row.
4. **a refused stop does not lose the reply** — `src/inbound.py:321`,
   `_stop_one`'s except-clause returns a classified result instead of
   raising past the reply.
5. **an absent lead's copy is named, not passed** — `src/configdiff.py:1136-1139`,
   the `MISSING at provider` failure entry.
6. **copy-lint refusal before any provider write** — `src/bisonfactory.py:699`,
   `_refuse_copylint`'s gate.

All seven test methods re-run GREEN today at 14:20 on `93162471d`:
`Ran 7 tests in 2.159s … OK`, exit 0 (`.codex/0063/six-green.txt`). The
seven, by name:

- `test_a_pause_of_an_unresolvable_campaign_refuses.APauseOfAnUnresolvableCampaignRefuses.test_the_refusal_propagates_before_any_transport`
- `test_a_plan_whose_copy_fails_lint_is_refused.APlanWhoseCopyFailsLintIsRefused.test_the_stage_is_refused_naming_the_lead_and_the_rule`
- `test_a_positive_reply_holds_the_account_and_suppresses_nobody.APositiveReplyHoldsTheAccountAndSuppressesNobody.test_nobody_is_suppressed`
- `…APositiveReplyHoldsTheAccountAndSuppressesNobody.test_the_account_is_held_for_a_person`
- `test_a_refused_pause_pauses_nothing.ARefusedPausePausesNothing.test_the_refusal_reaches_the_caller_and_nothing_is_recorded`
- `test_a_refused_stop_does_not_lose_the_reply.ARefusedStopDoesNotLoseTheReply.test_the_refusal_is_classified_and_the_reply_is_applied`
- `test_an_absent_leads_copy_is_named_not_passed.AnAbsentLeadsCopyIsNamedNotPassed.test_an_approved_lead_absent_at_the_provider_is_named`

### 2. The mutation proofs, re-run today — SEVEN proofs across six controls

0060's brief said six. The honest count is seven, because control 3 has two
failure directions — its own docstring requires that a positive reply both
HOLDS the account and suppresses nobody, and one mutation cannot go red for
both. "If it can go red two ways, split it."

Protocol for every proof: mutate the guard → run its test RED for the
intended reason → `git checkout -- <file>` (byte-exact from HEAD) → run
GREEN. Every edit and every revert on `93162471d`; outputs in
`.codex/0063/mut*-{red,green}.txt`, 14:23–14:26.

1. `api.py:3177` guard → `if False and …`. RED:
   `AssertionError: ActionRefused not raised`. Revert → green.
2. `orchestrator.py:607` `perform` wrapped in try/except returning a
   stopped-result. RED: `AssertionError: WriteRefused not raised`. Revert →
   green.
3a. `accountpolicy.py:96` HOLD → STOP. RED, both methods: the suppression
   dict `{'unsubscribed': True, 'since': …, 'reason': 'positive', …}` is not
   None — a positive reply suppressed the whole account.
3b. `accountpolicy.py:96` ACCOUNT → CONTACT. RED, only
   `test_the_account_is_held_for_a_person`:
   `AssertionError: None is not true : a positive reply did not hold the
   account` — while `test_nobody_is_suppressed` stayed green. The split
   holds: one mutation, one reason.
4. `inbound.py:321` except-clause → bare `raise`. RED (ERROR):
   `src.leadstop.StopRefused: record 'rec-1' is in no campaign, so there is
   no provider campaign to stop them in` escaping the handler — the reply
   lost. Revert → green.
5. `configdiff.py:1136` MISSING append → silent skip. RED:
   `lead_copy:686b5e4cf4f9: MISSING at provider` vanished from the failure
   list while the nameless `lead_count`/`lead_set` mismatches remained.
   Revert → green.
6. `bisonfactory.py:699` `if not found["refused"]:` → `if True:`. RED:
   `AssertionError: FactoryRefused not raised`. Revert → green.

Every revert verified by `git diff --stat` per file; the final `git diff` is
empty — the tree is byte-identical to `93162471d`.

### 3. The line-ending churn — 0060 record, plus today's measurement

From the 0060 transcript (a record; the surviving log names the fact but
not the files): the Edit tool CRLF-normalised four src files mid-run, each
a symmetric whole-file rewrite with content identical to HEAD —
`src/orchestrator.py` 1890/1890, `src/inbound.py` 1184/1184,
`src/configdiff.py` 2478/2478, `src/accountpolicy.py` 1494/1494. Each was
restored byte-exact with `git checkout -- <file>`; 0060's own summary:
"CRLF churn, all content identical to HEAD. checkout restored byte-exact."

Today's re-derivation (measured, `93162471d`, 14:23–14:26): **zero churn**
— every post-edit `git diff --stat` showed exactly the intended lines
(1/1, 9/5, 1/1, 0/2, 2/4, 1/1) and no whole-file rewrite, and the final
diff is empty. No churn persists anywhere in the tree.

### 4. The pre-existing failures — measured on both SHAs

`tests.test_compare_bison` run today on `93162471d` at 14:34 —
`Ran 7 tests in 0.066s, FAILED (failures=2)` — and inside both neighborhood
runs (§6) on `9718023a6` and `93162471d`. The same two names fail at every
SHA:

- `CompareBisonPass.test_verdict_pass_when_everything_matches` — expected
  PASS, got FAIL: all six `body_N` entries score `approved "<p>Hi X, …
  body</p>\n\nIf this isn't relevant, re…" vs provider '<p>Hi X, … body</p>'`.
- `CompareBisonFailLeadCopy.test_alice_passes_when_only_bob_differs` —
  alice's hash found in the failure text through exactly those footer-only
  mismatches, in addition to Bob's intended `subject_2: WRONG SUBJECT`.

Mechanism, verified in code today, not inferred: the approved side composes
every expected body through `trailingcontent.compose`
(`src/configdiff.py:588-632` — "THE TRAILING CONTENT IS PART OF WHAT THE
LEAD CARRIES"), and `compose` appends the opt-out **unconditionally**
(`src/trailingcontent.py:134`, `optout.append_opt_out(result)` — it runs
even with no signature, P.S. or CTA). The fixture claims to build "Leads
with custom variables matching the approved copy"
(`tests/test_compare_bison.py:251`) but feeds the provider mirror the RAW
step bodies. Expected = body + opt-out; mirror = body; every body_N
mismatches. This is the two-implementations-of-one-fact drift that
`configdiff.py`'s own docstring records for 2026-09-29, one field along. It
predates 0060 — commit `93162471d` touches no src file, and both names
fail identically at parent `9718023a6`.

**A third pre-existing failure was measured today, unreported until now:**
`test_the_stop_can_be_performed.ThePauseIsPerformable.test_and_nothing_else_came_with_it`
(`tests/test_the_stop_can_be_performed.py:205`):
`AssertionError: True is not false : heyreach.stop_lead` — the test asserts
nothing adjacent validates after a live-validated verb, and
`providerwrites.is_supported("heyreach.stop_lead")` returns True. Identical
at `9718023a6` and `93162471d`. 0060's log recorded only two pre-existing
failures because it ran only `test_compare_bison`. Recorded here as
measured; diagnosis and fix are outside 0063's scope (no work invented).

### 5. The 0040-era baseline gap — carried finding, restated

No lane entry exists for 0040 and no full-suite log survives at
`9718023a6`, so a both-directions full-suite failing-name diff for 0040's
own change **cannot be established from surviving artifacts**. What today
adds: 0040's five test modules ran green in both neighborhood batches (§6)
at both SHAs. What closing the gap fully needs: full-suite references at
`6caa9ea58` (pre-0040) and `9718023a6` (post), each ~40 minutes under the
lock. The lock is stale — every recorded holder pid is dead (self-checked
sweep, `.codex/sweep-0063.ps1`, SELFCHECK row present) — and per standing
orders it was NOT released; the next full-suite acquire self-heals it.

### 6. The neighborhood batch — run twice, in the foreground of this task

The one thing 0060 could not do (a suite was running then). Today the
machine was quiet — the self-checked sweep found no run_suite / unittest /
tests.offline process, with its own query visible as the SELFCHECK row —
and a module batch is not a full suite, so the lock was neither needed nor
taken. Both runs env-clean (`env -u GIT_CONFIG_* …`), unpiped (stdout
redirected to file), `-v`, foreground.

Module list — the 18 from 0060's own planning note, recovered from its
transcript (derivation stated there: 0060's six + their 0040 twins + every
sibling module exercising the six source files):

0060's six — `test_a_refused_pause_pauses_nothing`,
`test_a_pause_of_an_unresolvable_campaign_refuses`,
`test_a_positive_reply_holds_the_account_and_suppresses_nobody`,
`test_a_refused_stop_does_not_lose_the_reply`,
`test_an_absent_leads_copy_is_named_not_passed`,
`test_a_plan_whose_copy_fails_lint_is_refused`; the twelve pre-existing —
`test_a_refused_resume_resumes_nothing` (0040 twin),
`test_a_reply_reaches_the_provider_not_just_the_record` (inbound twin),
`test_account_policy` (apply_reply siblings),
`test_account_saturation`, `test_compare_bison`,
`test_a_lead_without_its_copy_is_never_attached` (0040),
`test_no_blank_variable_ever_travels_to_the_provider` (0040),
`test_no_transport_for_a_verb_outside_supported` (0040),
`test_one_yes_is_not_enough_to_send` (0040),
`test_the_stop_can_be_performed` (orchestrator pause/stop),
`test_a_pause_says_what_it_paused` (orchestrator pause),
`test_bison_prewrite_check` (bisonfactory prewrite).

**Run A — WITH the six files, SHA `93162471d`, 14:35:**
`Ran 118 tests in 7.297s, FAILED (failures=3)`. Failing name-set:
`test_compare_bison.CompareBisonFailLeadCopy.test_alice_passes_when_only_bob_differs`,
`test_compare_bison.CompareBisonPass.test_verdict_pass_when_everything_matches`,
`test_the_stop_can_be_performed.ThePauseIsPerformable.test_and_nothing_else_came_with_it`.

**Run B — WITHOUT them, SHA `9718023a6` (parent; the six files do not
exist there), 14:36:** the same twelve pre-existing modules.
`Ran 111 tests in 4.915s, FAILED (failures=3)`. Failing name-set: the
identical three.

**Both directions: A−B = EMPTY — the six files introduced no failure. B−A =
EMPTY — they masked or fixed nothing.** 118 − 111 = 7 = exactly the seven
new methods, all passing in Run A.

### Bookkeeping and state

Branch `task-glm-review-2026-10-14` at `93162471d`, up to date with origin;
tree clean apart from untracked `.codex/` (this task's artifacts:
`.codex/0063/*.txt` run outputs, `lane-entry-0060.md` this entry's source,
`.codex/sweep-0063.ps1`). `origin/master` still
`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`; no push, no merge, master
untouched. Queue: 0060 already sits in DONE (the watcher moved it); RUNNING
holds only 0063, which stays where the dispatcher holds it (0030/0050
Windows holder precedent, not forced). Nothing 0063 started is still
running.

**Boundary:** 0063 is complete. The halt fix (0065) and the suitelock
proposal are ordered separately and were not started here.
