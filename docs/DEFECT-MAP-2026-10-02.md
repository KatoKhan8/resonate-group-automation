# Defect map — everything found since 2026-09-30

State at the time of writing: `master = eeead37d`, `origin/master = 10a38310` (one merge ahead,
deliberately not pushed). The only thing merged so far is `task-named-baseline`: the named 231
baseline, the honest `INCOMPLETE` verdict status, and a 3600s watchdog.

Categories: **live** = a real defect in running code · **fixture** = the code was right and the test
was stale · **neizmjereno** = a claim nobody had measured · **okolina** = tooling or environment,
not the product.

"Canary put" means it stands between us and one provider-confirmed send.

---

## A. Live defects

| # | što | kako izmjereno | canary put | popravak živi | TASK |
|---|---|---|---|---|---|
| A1 | Internal campaigns were not protected at all: 8 verbs (bison+heyreach pause / create_campaign / set_sequence / stop_lead) reached transport for operator-internal AND unknown campaigns. `CONDITIONAL` declared empty at `providerwrites.py:799`, populated in 8 places, those verbs on none of them | transport + readback that raise if touched; 27-cell effect table; `require_conditional_permission` called directly returned True for all four internal ids and a nonexistent one | **DA** | branch `task-guard-regressions-rebased` `b83f11fc` | — |
| A2 | The blank-content halt would have been REFUSED live. `bison_watch_loop.py` put the PROVIDER id in `perform`'s CANONICAL `campaign=` slot and passed `provider_campaign_id` nowhere (0 occurrences in the file). No canonical row is named "497"; 497 is the `bison_campaign_id` of `productive-email-batch1-jakov`. Second time this control alarmed and stopped nothing (first: 2026-09-23T20:18:58Z, missing write scope) | effect: with the id → `transport_calls=[pause,campaign]`, `outcome=accepted`; without → `[]`, `outcome=refused`. Byte mutation, md5 verified | **DA** | branch `task-guard-regressions-rebased` `b83f11fc` | — |
| A3 | `bison.resume` on **487** reaches transport. CLAUDE.md's "the 2026-09-21 grant was SPENT, never resume again" is documentation, not code. `_SEALED_CAMPAIGNS` has **0 occurrences on master** | `grep -c` on master and on `b83f11fc` = 0; the seal exists only on `task-936`, where `require_not_sealed` is verb-agnostic and runs first in `_perform` | **DA** | branch `task-936-487-on-the-gate` `7b732696` | TASK-936 |
| A4 | Tenancy guard failed open: a client with no `providers:` block built campaign 501 and attached two leads inside the estate the credential is bound to. `clients.STARTER` declares no estate, so that was every client `clients.create` writes | reproduced before the fix | ne | branch `task-tenancy-guards-fail-open` `f03ae373` | — |
| A5 | Classifier deaf to a refusal with no keyword. Bare `remove` → `unknown 0.0` while `remove me`/`DNC`/`Stop`/`unsubscribe` → `unsubscribe 0.95`. `"No needs, thanks."` → `automated 0.85` — a human refusal labelled an autoresponder. Cause: `^stop$` anchored to the whole normalised message, and `normalise` collapses newlines, so the anchor only matches a reply with nothing after the word | committed classifier, `RULE_HASH` matched the artifact; 899 replies; 46 removal verdicts gained, 0 lost | ne | branch `task-939-keywordless-refusal` `274083c9` | TASK-939 |
| A6 | Reply 1603100: the entire human content is the word `remove`; master read it as `referral 0.8` on evidence `please contact` taken **from its own confidentiality footer**, a class that does not suppress. The person was on no list | per-reply verdicts before/after; DNC membership checked directly | ne | A5's branch **and** manually added to `work/agency-dnc.jsonl` 2026-10-02 | TASK-939 |
| A7 | Reply 1538458: the entire content is `Stop`; master read it as `positive 0.75` on evidence `that would be useful` — **a sentence we wrote**, quoted back in the thread. A person asking to be left alone was reported as a buying signal | same | ne | fixed independently by both classifier branches | TASK-939 |
| A8 | An `unknown` verdict notifies nobody. In `replies.apply` only `is_positive` calls `_announce`; unknown is written to an event, pauses the cadence, and no human is told. `notify.UNMATCHED_REPLY` fires only from `inbound.py` on ATTRIBUTION failure, never on CLASSIFICATION failure. **274 replies sit there after both classifier fixes land**; 13 are clear removal signals | execution path read; corpus counts across four rule versions | ne | **OTVORENO** | TASK-941 |
| A9 | The suite verdict parser was blind exactly when it mattered: on a watchdog kill it wrote a four-line verdict with no `failures=` line at all, and `_find_failures()` returned 0 on a log containing 6. On an older log with 200+ failures `grep -cE '^(FAIL\|ERROR): '` returned 0 | `run_suite.py --timeout 20` run for real; the honest parse of the same log | **DA** (every merge rests on it) | **master `eeead37d`** | — |
| A10 | `_read_spend` in `glm_verify_branch.py` filters `client == "_model"`, a pseudo-tenant retired by TASK-346 because it hid model spend from every client ceiling. It therefore matches nothing and always prints `Spend: 0 rows`. The real row existed the whole time | the ledger row read directly: `client "unattributed", provider "glm", 11266 microusd` | ne | **OTVORENO** (Qwen did not do it) | TASK-940 |
| A11 | `glm_verify_branch.py` sends GLM a **diffstat** where its own prompt asks whether a new helper has a caller — which its docstring names as the tool's purpose. Every `NEEDS_CLAUDE` from that cause is vacuous and costs a full paid call | the tool run for real; GLM's own words; the three questions then answered by hand | ne | **OTVORENO** | TASK-940 |
| A12 | The same tool pointed at the OLD text baseline (128 entries) after the baseline moved to JSON (231), so it would report every new master failure as "new on the branch" | found by Qwen, pinned with a test; uncommitted | ne | **OTVORENO**, work exists uncommitted in `wt-qwen-940` | TASK-940 |
| A13 | `synthetic: true` is read by nothing in `src/`. **0 of 15 pool queries exclude on it**; `must_not_contact()` returns no reason, `discovery.delta()` returns it as NEW, `candidatelist.append()` accepts it into a permanent list | each query run twice over twins identical but for the flag; agreement proves the flag changed nothing. Test deliberately red (12 tests, 15 failures) | **DA** (sandbox safety) | **OTVORENO** — mine; honest home is `operatorexclusion`, which is an operator decision | — |
| A14 | `prior_contact` is two-state on master (`generate.py:672` reduces to `bool`), and the campaign copy path had **zero** references to it: `copystages.py`, `copyprompts.py`, `generate_campaign.py`, `copylint.py` all 0, while `copystages.py:388` asserted "FIRST TOUCH SHAPE" unconditionally | `grep -c`; prompt text read | **DA** | branches `task-recontact-cold-lead` `f931a2cd` + `task-937-prior-contact-copylint` `f71221da` | TASK-937 |
| A15 | `em5` vs rung 5 (`one operational view`) is marginal, not solved. Two independent generation runs both converged only on the **third** attempt, each with up to 10 internal lint retries — order of 20–30 discarded drafts for five emails. In one run `step_objectives` rejections on the converging attempt were 0, in the other 3 | two full generation runs against a store copy | **DA** | branch `task-step-objectives-convergence` `c916d3fd` (the fix works; the fragility remains) | — |
| A16 | 773 of 1,584 records carry **zero contacts**. Only 811 records hold the 1,381 contacts | store snapshot, with controls (a field present on every record returned 1,584; a bogus field 0) | **DA** (sourcing) | **OTVORENO** — sourcing, not code | — |
| A17 | 1,297 of 1,584 records have no usable vertical: 866 have no `qualification.segment.vertical` path and 431 hold the literal string `UNKNOWN`. A vertical lives at **three** paths that can disagree (`segment` 718, `messaging` 247, `segment_parts` 9) | same snapshot; distribution asserted to sum to 1,584 | **DA** | **OTVORENO** | — |
| A18 | One of 1,584 records carries `state: "do_not_contact"`, which is not in `store.STATES` | dummy run | ne | **OTVORENO** | — |
| A19 | `executionguard` has **five preconditions before gate 1** plus seven gates, and **no record has ever reached gates 1–7**. The first dummy stopped at precondition `copy` with `passed=()` | dummy run v1 | **DA — this is the current first blocker** | **OTVORENO** — Phase 0 in flight | — |
| A20 | `max_tokens` is sent nowhere: `grep -c max_tokens src/generate.py` is **0 on master and 0 on `task-step-objectives-convergence`**. A truncated completion raises `JSONDecodeError`, a broad `except Exception` at `generate.py:2356`/`:2486` swallows it, and the record ends `hold_kind="error"` after ONE attempt — spending the whole ten-retry budget that exists for it | golden-path run on master; grep on both sides; the live bigfish run failed on `JSONDecodeError … column 2724` and continued only because the branch fixes the accounting | **DA** | retry accounting on `c916d3fd`; **the cause is OPEN everywhere** | TASK-942 |

---

## B. Stale fixtures — the code was right

| # | što | kako izmjereno | canary put | popravak živi | TASK |
|---|---|---|---|---|---|
| B1 | All 66 of the guard branch's "regressions" were fixtures that never recorded their destination: they bound it only through `mock.patch.object(campaigns, "require", …)`, and the guard deliberately does not read `require` — a mock is a claim the caller makes about itself, the ledger is the only positive record | 497/599020/327/999999 classified against a real ledger copy; 5 mutation probes with byte-exact restore; a property test that goes red when the guard is restored | **DA** | branch `task-guard-regressions-rebased` `b83f11fc`, rebased onto master, 0 conflicts, 231/231 | — |
| B2 | 4 real regressions on the cold branch: the branch adds a FOURTH provider read to gate 4 (`collision.recontact_check`, `executionguard.py:703`) and the test module's `allow_collision()` binds only two — its docstring still says "the two places a gate would reach one are mocked" | reproduced on a clean checkout; 5 mutations; with the fix applied to master the module cannot even import, so the fix is inseparable from the change | **DA** | branch `task-cold-regressions` `4222ee88` | — |
| B3 | One stale fixture note held 17 tests red in `test_heyreachfactory_ensure_leads`: the refusal rose inside `_plan` (`heyreachfactory.py:929`) after gate 1 and before gates 2–6, so every test that had to pass gate 1 died one line before its own subject | 17 red → 29/29 green on a clean detached checkout | ne | branch `task-reply-stop-15min` `8fe07357` | — |
| B4 | Three false greens inside that same module, found by fixing it: a DNC test asserting only `assertIn("pat", text)` which passed while gate 2 was never reached; twelve classes whose `setUp` never called `super().setUp()` so the leaked-patch net was unregistered; and a `transport.assert_not_called()` that could never fire because the closure it guarded only runs inside a mocked `providerwrites.perform` | each reproduced | ne | same branch | — |
| B5 | `tests/test_fixture_hygiene.py` is RED on master — 5 of 17 — and was red before any of this work. Its failures name real identities in `src/operatorexclusion.py`, `scripts/record_self_send_exclusions.py` and two test files | run on a pristine master worktree | ne | **OTVORENO** — a red suite test is tolerated; a refused commit would not be, which is the argument for TASK-938 | TASK-938 |

---

## C. Okolina — tooling, not the product

| # | što | kako izmjereno | popravak živi | TASK |
|---|---|---|---|---|
| C1 | `.gitattributes` has rules for `*.sh`, `*.bash`, `*.service`, `*.timer` but **none for `*.py`**, while `core.autocrlf=true`. So every checkout smudges Python to CRLF while a file a tool wrote stays LF — and six tests assert literally `assertIn(b"\r\n", …)`. This manufactured **12 phantom regressions** | both blobs pure LF (CRLF=0), production tree CRLF=1544; converting to LF turned exactly those 12 red with the exact message, back to CRLF green | **OTVORENO** | — |
| C2 | `config/.env` is gitignored, so a worktree does not have it. `load_env("config/.env")` relative to a worktree loads nothing silently: `LLM_API_KEY` stays empty, `OpenAICompatibleModel.configured()` returns False, and `from_env()` falls through by design to the Qwen CLI, which dies with "No auth type is selected" | three generation attempts failed that way; the same `configured()` from the production root returned True | documented; load the production `.env` by absolute path | — |
| C3 | Qwen CLI 0.23.3 does **not** read `security.auth.selectedType` from `~/.qwen/settings.json` — auth had been configured there since 2026-09-13, three weeks before the failure. It needs `--auth-type openai` explicitly, and `--prompt` rather than a `--` positional | three test invocations; the working one returned `QWEN-OK`, exit 0, 6.1s | documented in the launcher | — |
| C4 | `QwenCliModel` in `src/llm.py` carries both of C3's defects. **Deliberately NOT fixed** by operator decision: fixing it would turn a loud failure into a silent model substitution on the copy path | same | by decision, stays broken and loud | — |
| C5 | PowerShell `Start-Job` does not survive the tool invocation. Three Qwen tasks reported as running had died with their session, producing no output file, no commit, no report | output files absent, worktrees untouched | fixed: `run-qwen.sh` driven as a harness-tracked background command, smoke-tested | — |
| C6 | The session scratchpad is shared between agents: one agent's `namediff.py` was overwritten by another mid-measurement | the file started referring to a module it had never used | documented; read tooling from git, not the shared scratchpad | — |
| C7 | A sibling agent killed the merge sequence's suite with a broad PowerShell filter (`tests.offline` + a 40-minute window), hitting a PID from the main checkout. Cost: one wasted ~26-minute run; the merge track relaunched by itself at 10:56 | the agent reported it; the damaged verdict carries `exit 4294967295`, `wall 1561.9s`, `failures_are_partial=True` | process rule now in every brief: match your own PID or worktree path | — |
| C8 | `approval.AUTONOMOUS_WINDOWS` holds a window expiring `2026-10-01`, and `bisonfactory._certified_copy` reads the real clock with no `on=`. From 2026-10-02 `test_autonomous_production_is_not_a_self_stamp…certifies_at_staging` fails on CLEAN master and is not in the 231 baseline, so it appears as a phantom regression on every branch | failed identically on clean master in the same minutes, under both the local and the UTC day boundary; forcing the clock to 2026-10-01 restores it | **OTVORENO** — operator decision: thread `on=` through, do not extend the window | — |

---

## D. REFUTED — claims from earlier reports that measurement later overturned

**This section is the point of the document.** Every line here was once reported as fact.

| # | the claim | what measurement said | who claimed it |
|---|---|---|---|
| D1 | "The master suite does not fit in 2700s / times out" | **REFUTED.** It COMPLETES in **2717.8s**. The 2700s run was killed **18 seconds from the end**. Every "the base suite times out" conclusion came from a watchdog set below the suite's own duration | earlier session |
| D2 | "The baseline is 227 named failures" | **REFUTED.** No named list for 227 existed anywhere — it was a count read off a truncated log. The real baseline is **231** (full run) / 221 (module-isolated). Reconstructing the old era gives 206 names, and full-vs-reconstructed is SAME 206 / GONE 0 / NEW 25, all 25 being tests the killed run never reached. **Nothing was fixed and nothing regressed** between `d98c83ce` and `10a38310` | earlier session |
| D3 | "The cold branch carries 16 regressions" | **REFUTED.** Only **4** reproduce on the commit. The other 12 were an artefact of the worktree the branch was authored in (C1) | this session's own name-diff track |
| D4 | "The L3/L4 branch has 6 regressions, confirmed by two independent methods" | **REFUTED in the worse direction: 26.** The decision not to merge stands either way, but 6 was an underestimate by more than four times | earlier session |
| D5 | "Two linters disagree on em5, so a draft could ship that `check()` rejects" | **REFUTED as a general property.** Swept em5 from 41 words down to 10: 41 passes both, 39 and below fail **both** with the same code. No length disagrees. The gate cannot be slipped on this step kind | dummy run v1 |
| D6 | "487/489/493 are untouchable" | **REFUTED.** `bison.resume` and `bison.assign_sender` PASS ownership for all three and reach transport. What held them was the killswitch, `sending.live=false` and stale approvals — three conditions outside the write gate (A3) | standing assumption |
| D7 | "The 15-minute reply stop is proven for the LinkedIn push path" | **REFUTED.** `scripts/batch_linkedin_push.py` has **0** references to `heyreachfactory`, `providerwrites`, `eligibility` and `executionguard`, against 11 to `store` and 12 to `heyreach` — so the grep works. The tests prove a stop on a module that script never calls. Only the `HALT` constant holds it | earlier session, re-verified this session |
| D8 | "GLM recorded no spend — the money is invisible" | **REFUTED.** The ledger row existed the whole time (`11266 microusd`). The script's **reader** was broken (A10). Opposite of what was first written, and corrected in TASK-940 | my own claim, this session |
| D9 | "315 records have no LinkedIn URL" | **REFUTED.** All **1,381** contacts carry a `linkedin` value and all 1,381 canonicalise — zero absent, null, empty or non-canonical. The control confirms `canonical('')` returns None, so the zero is a verdict. The 315 could not be reproduced under any reading; the real gap is A16 | working assumption |
| D10 | "654 records have no vertical" | **REFUTED in the worse direction: 1,297** (A17) | working assumption |
| D11 | "bigfish gets 2 accepted research rows, both medium, relevance 0.70" | **REFUTED.** The script that produced the claim (`scratch/measure_bigfish_chain.py`) measures outcome, refusal, stats and per-page character counts and **never computes relevance or quality at all**. bigfish appears in **no** crawl cache. `quality` is derived via `recheck()` so an asserted 0.70 has no effect, and the real scorer gave comparable synthetic facts 0.097–0.197 — all UNUSABLE. Its `robots.txt` also returns 403 to our UA, which the honest-UA rule treats as a refusal | earlier session |
| D12 | "Qwen's TASK-940 diff weakened a test" | **REFUTED — it strengthened it.** `assertGreater(…, 100, "~128")` became `assertGreater(…, 200, "~231")`. I had read removed lines without the added ones | my own claim, this session |
| D13 | "Qwen is already working on its first task" | **REFUTED.** The job had died with its PowerShell session: no output file, no commit, no report (C5) | my own claim, this session |
| D14 | "Slack cannot be posted from this build" | **REFUTED.** Posted to `#resonate-os` today, readback byte-identical | earlier session |
| D15 | "`activeCampaigns: 8` means 8 campaigns on the seat" | **REFUTED.** It is the count of IN_PROGRESS campaigns; **28** hang on that seat — 1 ours, 8 internal, 19 unknown | earlier session |
| D16 | "All 1,584 records have no vertical" | **REFUTED by the next measurement.** I had guessed the path. It lives at `qualification.segment.vertical` | my own claim, this session |
| D17 | "The guard agent wrote `*pii*` files into production `work/`" | **REFUTED.** All three are dated 2026-09-22, ten days old, and contain no emails or fingerprints | my own suspicion, this session |
| D18 | "A mutation residue remains in `osattribution.py` after restore" | **REFUTED.** My grep pattern matched two legitimate `return OURS` lines inside `attribution()` | my own check, this session |

### D-bis. Three of my own specifications were wrong, and the agents were right to refuse them

| # | my instruction | why it was wrong |
|---|---|---|
| E1 | "Cherry-pick these three commits" for the guard rebase | The range `d98c83ce..c54276f4` holds **four**. Dropping the fourth would have dropped `d89ca718` — **the guard itself** — leaving 66 repaired fixtures with nothing to repair against: a green, meaningless branch |
| E2 | "Remove the operator's line from `config/internal-campaigns.txt` and the same write must reach transport again" | Vacuous as written. 274/327/328/352 are in no canonical row, so removing the line moves them from `resonate_internal` to `unknown`, which refuses identically. The agent rebuilt the control on a campaign present in both sources, where the line is the only variable |
| E3 | "Prove each repaired test fails if the branch change is reverted" | Inapplicable twice. Those tests are pre-existing tenancy and idempotency tests whose fixtures went stale; they are not tests of the change, so reverting it leaves them green — and **if they had gone red, that would mean the fixture was bound to the guard, which would be the bug** |

---

## E. Where the fix lives, at a glance

| branch | SHA | carries |
|---|---|---|
| **master** | `eeead37d` | A9, the named 231 baseline, 3600s watchdog |
| task-guard-regressions-rebased | `b83f11fc` | A1, A2, B1 — rebased onto master, 0 conflicts, 231/231 |
| task-936-487-on-the-gate | `7b732696` | A3 |
| task-939-keywordless-refusal | `274083c9` | A5, A6, A7 |
| task-cold-regressions | `4222ee88` | B2 |
| task-937-prior-contact-copylint | `f71221da` | A14 (sits on the cold branch) |
| task-938-pii-gate | `6839dfe5` | B5's control; hooks deliberately NOT installed |
| task-eligibility-reply-only | `21a1d956` | the 40 declared OS campaigns; 274/327/328/352 not OS |
| task-step-objectives-convergence | `c916d3fd` | A15 |
| task-tenancy-guards-fail-open | `f03ae373` | A4 |
| task-pause-exception | `0d7e6e71` | deferred by operator decision — new feature |
| task-crawler-identity-integrated | `3ffe535f` | the honest-UA crawler; D11 lives here |
| **OTVORENO** | — | A8, A10, A11, A12, A13, A16, A17, A18, A19, B5, C1, C8 |

## F. The one thing that is not a defect and is worth saying

The copy converges. bigfish's five emails were produced twice independently, both on the third
attempt, and `lint.check` and `lint.check_step` both return zero failures over all five steps with a
positive control that fires. The word floor is exactly 40 and two of the five steps sit at 41 — one
word above it — so a regeneration can drop below. That is a fragility, not a defect.
