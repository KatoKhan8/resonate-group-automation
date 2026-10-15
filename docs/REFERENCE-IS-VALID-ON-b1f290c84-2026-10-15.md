# The 2bf7b8a57 reference is valid on b1f290c84 — proven, not assumed

**TASK-0030, suppression lane, 2026-10-15.** Measured, not argued.

## The question

Master moved from `2bf7b8a57` to `b1f290c84`. Every merge is gated against a
reference measured on the master it is merging into, so a diff taken against
`b1f290c84` using the `2bf7b8a57` reference would charge that master delta to
whichever branch was being measured. The delta is not obviously inert:

    git diff --name-only 2bf7b8a57 b1f290c84
    docs/qwen-tasks/TODO/TASK-1012-the-copylint-verdict-drives-the-refusal-and-nothing-proves-it.md
    docs/qwen-tasks/TODO/TASK-1013-never-attach-a-lead-whose-copy-is-not-already-on-it.md
    docs/qwen-tasks/TODO/TASK-1014-the-entry-point-that-every-entry-point-missed.md
    docs/qwen-tasks/TODO/TASK-1015-the-narrow-audit-slicer-that-never-existed.md
    4 files changed, 894 insertions(+)

plus `b1f290c84` itself, which is an empty probe commit touching no file.

`.md` is in `test_fixture_hygiene`'s `TEXT_SUFFIXES`, so these four files are
READ BY A TEST. They are not inert and the question is real.

## Why a fresh 46-minute reference run was NOT spent

Nothing under `src/` and nothing under `tests/` changed, which is the bound
CLAUDE.md puts on the targeted-run alternative. Within that bound the rule
requires a MEASUREMENT that no test can observe the delta, naming the tests
that could — not an argument from the kind of file.

The machine lock was also held by a live holder at the time
(`wt-pilotcaps-2026-10-14`, pid 74780, started 01:57:16, confirmed alive via
`suitelock._alive`), so a reference run would have queued behind a full suite
and then denied the lock to the next lane for another ~46 minutes.

## The task framing understated the observer set: it is TWO modules, not one

A targeted run of `test_fixture_hygiene` ALONE would have been insufficient.
`test_secrets.TestNoRealCredentialInTheRepository.tracked_files` also
enumerates the whole tracked corpus via `git ls-files` and also includes
`.md` in its suffix filter.

Enumerated mechanically rather than by reading around:

| class of reader | modules | can it see a new `docs/*.md`? |
|---|---|---|
| whole tracked corpus via `git ls-files`, `.md` in suffix filter | `test_fixture_hygiene`, `test_secrets` | **YES — the observers** |
| `os.walk(ROOT)` repo-wide | `test_nothing_writes_to_a_provider` | no — yields `name.endswith(".py")` only |
| tree walk scoped to `src/` or `tests/` | 15 modules: `test_audit`, `test_invariants`, `test_campaign_audit`, `test_compliance_gate`, `test_deployment_config`, `test_research_audit`, `test_transport_audit`, `test_variant_wiring`, `test_verification`, `test_web_invariants`, `test_nothing_talks_back_to_a_prospect`, `test_a_permanent_operator_exclusion_survives_a_fact_refresh`, `test_a_credential_is_checked_by_its_real_name`, `test_personalization_api_is_whole`, `test_http_timeout_aborts_at_socket_layer` | no — out of scope and/or `.py` only |
| walk of a temporary directory | `test_persistent_volume`, `test_the_readback_cache_cannot_lie_about_its_age` | no |
| names `docs/qwen-tasks/...` but against a THROWAWAY git repo | `test_claim_task`, `test_claim_task_readiness_is_not_inferred`, `test_the_scan_reads_code_not_task_files` | no |
| opens ONE named real `docs/` file, none of the four | `test_the_replay_harness_can_fail` (`SLACK-AGENT-QUESTION-CATALOGUE.md`), `test_the_secrets_checklist_never_prints_a_value` (`SECRETS-MOVE.md`) | no |

`test_the_estate_comes_back_after_a_reboot` was a candidate carried over from
the previous task in this lane; it mentions a `.md` path in a docstring only
and reads no `.md` bytes. It was included in the run anyway, because including
it costs seconds.

## The measurement: one tree, two checkouts

A fresh detached worktree, `wt-ref-b1f290c84`, created at `b1f290c84`. The
nine modules above were run in it, then the SAME tree was checked out at
`2bf7b8a57` and the same nine were run again. Same filesystem, same
interpreter, same absent `config/.env` (confirmed absent in the frozen
`ref-2bf7b8a57` tree too, so the conditions match the reference run's) — only
the four files differ. That design removes every confound a two-tree
comparison would leave open.

`resonate-ops/ref-2bf7b8a57` was NOT used for this and was NOT checked out
from under: CLAUDE.md records a 44-minute run lost that way.

Names were extracted with `run_suite._parse_failures`, never grepped.

    at b1f290c84 (four files PRESENT) : 9 failing names, 151 tests collected
    at 2bf7b8a57 (four files ABSENT)  : 9 failing names, 151 tests collected
    set difference, both directions   : EMPTY

The same nine modules sliced out of the full-suite reference log
(`ref-2bf7b8a57/scripts/suite_run.log`, 228 names) give the SAME nine:

    FAIL: test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
    FAIL: test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_linkedin_url_with_real_vanity_name
    FAIL: test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain
    FAIL: test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named
    FAIL: test_fixture_hygiene.TestTheExemptionStaysNarrow.test_the_identifiers_appear_nowhere_ELSE_in_the_repository
    FAIL: test_nothing_writes_to_a_provider.NoUndeclaredProviderWrite.test_every_http_write_in_the_repository_is_declared
    FAIL: test_secrets.TestNoRealCredentialInTheRepository.test_no_tracked_file_contains_a_credential_shaped_assignment
    FAIL: test_secrets.TestTheEnvFileIsIgnored.test_every_state_override_is_in_the_example
    FAIL: test_the_secrets_checklist_never_prints_a_value.TheCommittedDocMatchesItsGenerator.test_the_committed_checklist_is_what_the_generator_produces

Control that the log reader works rather than returning an empty set for
everything: `test_e2e` in the same reference log yields its 11 known names.

Positive check that the runs collected tests rather than matching nothing — a
zero-test discover would also produce zero failures and look like agreement:

    test_fixture_hygiene                             17 tests
    test_secrets                                     20 tests
    test_nothing_writes_to_a_provider                 7 tests
    test_claim_task                                  31 tests
    test_claim_task_readiness_is_not_inferred        15 tests
    test_the_scan_reads_code_not_task_files           9 tests
    test_the_replay_harness_can_fail                 11 tests
    test_the_secrets_checklist_never_prints_a_value  11 tests
    test_the_estate_comes_back_after_a_reboot        30 tests
    ---------------------------------------------- 151 tests, each side

## Verdict

**The 228-name reference measured on `2bf7b8a57` is VALID as the reference for
`b1f290c84`.** Reusable at
`resonate-ops/logs/reference-228-master-2bf7b8a5.log`, identical in content to
`resonate-ops/ref-2bf7b8a57/scripts/suite_run.log`.

Cost: 151 tests twice, about 80 seconds of wall clock and no machine lock,
against ~46 minutes of lock for a fresh full run plus the queue behind it.

Raw logs: `resonate-ops/logs/ab-0030/at-b1f290c84.log` and
`.../at-2bf7b8a57.log`.

## A trap found while doing this, and it is the suite lock's own trap

`suitelock.path()` resolves the machine-wide lock through
`git rev-parse --path-format=absolute --git-common-dir` and FALLS BACK to this
tree's own `work/` when git cannot answer. In this environment git cannot
answer: the shell exports `GIT_CONFIG_COUNT=1` and `GIT_CONFIG_KEY_0` with no
matching `GIT_CONFIG_VALUE_0`, so every git invocation dies with
`fatal: unable to parse command-line config` and exit 128.

Unguarded, the first read here returned
`wt-suppression-2026-10-14\work\suite.lock`, reported `None` for the holder
and would have launched a second full suite in parallel with the live one —
exactly the per-worktree lock CLAUDE.md says the module exists to prevent,
reached through a different door. With `GIT_CONFIG_COUNT` cleared the same
call returns the main checkout's `work/suite.lock` and the live pilotcaps
holder.

**Anything launching `run_suite.py` from a lane shell must clear
`GIT_CONFIG_COUNT` first, or it silently serialises nothing.** Whether that
fallback should REFUSE rather than fall back is an operator-facing question;
filed, not acted on, because the FOCUS RULE puts it outside this task.

## One more hazard, for whoever measures next

`test_fixture_hygiene.tracked_files()` reads `git ls-files --others
--exclude-standard` as well as the tracked list, so it scans files that are
UNTRACKED BUT NOT IGNORED, live from disk. Writing a report, a scratch script
or a note into the tree while a suite is running therefore changes what that
suite measures. The run for this task was stopped and relaunched for exactly
this reason once the tree was final.
