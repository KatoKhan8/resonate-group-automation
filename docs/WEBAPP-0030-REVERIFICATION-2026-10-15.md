# TASK 0030 re-verified: the mutation gate re-proven, and the bounded gate widened from four modules to thirteen

Written 2026-10-15 22:30 local, in `Desktop\resonate-trees\wt-webapp-2026-10-15`,
branch `task-webapp-2026-10-15`. Everything below was measured at
**`149ae6307ddb92aa97557f997150a15f47015886`** against its parent
**`49a6fc75383fe0ca30d4e5660c66dff732fadc92`**. The tree never left its branch.

## Why this document exists

`queue/webapp/0030-build-the-first-page.md` was dispatched a second time. The
page it asks for was already built and committed — `88372a774` and `149ae6307`
— and the `0030` lane entry predicted this re-dispatch in writing. So this run
did not rebuild anything. It did the one thing a second look is actually worth:
**re-measured the gate instead of inheriting it.**

That distinction is the standing rule (`NAME THE SHA OF EVERY MEASUREMENT`:
re-measure a gate yourself, at the moment you look) and it earned its keep
twice here. One previously recorded result was red **for the wrong reason**, and
the module set the previous run bounded its gate to was chosen by reasoning
rather than by measurement — and when measured, it was missing nine modules
that are coupled to any change in the repository by construction.

Nothing under `src/` or `tests/` changed in this run. This file is the only
addition.

## 1. The page still does what it claims, re-measured

    py -3 -m unittest tests.test_the_provider_write_log_says_which_kind_of_nothing
    27 tests, OK, 18.9s, run alone

Baseline re-run three further times during the mutation work, green at 27/27
every time (19.7s, 20.5s, 20.6s).

Disk bytes equal the committed blobs — checked by raw hash rather than by
`git status`, because a long-lived tree in this estate was found holding
mutated source while git called it clean:

    src/web/api.py                            931730ee28a8…  == HEAD blob
    src/web/app.py                            b6660dc916c0…  == HEAD blob
    src/web/pages.py                          952d249833c9…  == HEAD blob
    tests/test_the_provider_write_log_…py     47ee8f6b2448…  == HEAD blob

## 2. Mutation re-proof: ten mutants, all red, every revert byte-exact

Driver contract, and the first two clauses are the lessons the previous run
paid for: it **refuses to mutate a file whose disk bytes do not already hash to
its HEAD blob** (the revert is `git checkout --`, which is a checkout and not an
undo — the first `0030` run destroyed 236 uncommitted lines that way), it edits
**bytes** rather than rewriting the file through an editor (this tree is LF and
a whole-file rewrite flips every line ending, which would turn later hash
comparisons into statements about newlines), and it proves each revert by
comparing the restored hash to the pristine one.

Grouped by the brief's four requirements, so each one is answered:

**Requirement: it renders an explicit UNKNOWN when its source is missing**

| mutant | guard broken | result |
|---|---|---|
| M1 | `_read_provider_log` returns `LOG_EMPTY` for a missing file — the `store.read_jsonl` shape | **RED 2** — `test_an_absent_ledger_is_not_a_zero` (`'No ledger file' not found`); `test_the_three_states_render_three_different_pages` (`2 != 3 : two of the three nothings rendered identically`) |

**Requirement: a provider-derived value shows its age, and shows stale rather than silently showing old**

| mutant | guard broken | result |
|---|---|---|
| M2 | `_log_age` returns `0` instead of `None` for an unparseable stamp | **RED 2** — `test_a_row_with_no_readable_stamp_renders_UNKNOWN` (`'0 seconds ago' unexpectedly found`); `test_an_undateable_row_is_age_None_and_not_age_zero` (`0 is not None`) |

**Requirement: the route is reachable only with the permission chosen, and that choice is asserted**

| mutant | guard broken | result |
|---|---|---|
| M3a | the **route table** gate widened to `operations.view` | **RED 2** — `test_the_route_is_gated_on_provider_settings_view`; `test_the_nav_offers_it_on_exactly_the_permission_the_route_checks` |
| M3b | the **handler's own** `repo.require` widened | **RED 1** — `test_the_service_layer_refuses_a_reviewer_ON_ITS_OWN` (`NotPermitted not raised`) |
| M3c | both gates widened at once | **RED 4** — the three above plus `test_a_reviewer_is_refused_although_they_may_see_operations` (`403 != 200`) |

**M3b is the one that matters.** It SURVIVED in the first `0030` run — the route
table refused a reviewer first, so every HTTP-level assertion still passed while
the service layer had quietly stopped refusing. Two gates, one of them watched.
The test added in `149ae6307` calls the service function directly, where the
route is not in the way, and **M3b is now RED 1**. That claim was made at the
commit that fixed it; it reproduces independently here.

**Requirement: nothing the page does writes anything**

| mutant | guard broken | result |
|---|---|---|
| M4 | an audit row, written with five positionals | **RED 18, AND FOR THE WRONG REASON — see below** |
| M4b | an audit row, **well-formed** | **RED 2** — `test_it_writes_no_audit_row_either` (`26 != 27`); `test_a_request_for_this_page_changes_no_file_in_the_store` (`audit.jsonl` 5,879 B → 6,755 B, hash moved) |
| M4c | one stray file dropped into the store | **RED 1** — `test_a_request_for_this_page_changes_no_file_in_the_store` (`mutation-M4c.txt` appeared in the snapshot) |

Beyond the brief's four, because they are the page's own reason to exist:

| mutant | guard broken | result |
|---|---|---|
| M5 | an unknown outcome defaulted into a bucket | **RED 1** — `test_an_unrecognised_outcome_is_not_filed_into_a_bucket` |
| M6 | the tenant filter removed | **RED 1** — `test_another_tenants_rows_are_not_shown_and_not_counted` (`'heyreach.pause' unexpectedly found`) |

Every revert byte-exact, verified by hash, every time:
`src/web/api.py` back to `931730ee28a8…`, `src/web/app.py` back to
`b6660dc916c0…`. No test was edited to make any mutation red.

### M4 was red for the wrong reason, and that is a finding about the method

`Repo.audit` is `audit(self, action, resource_type=None, resource_id=None, **kw)`
— three positionals. M4 passed four, so the page raised `TypeError` and returned
**500**, and eighteen tests went red on the crash. Two of those eighteen were
the write-detection tests, so the table would have read `RED 18` and the
requirement would have looked over-proven.

It was not proven at all. The tests fired because the page was broken, not
because it wrote anything — the exact failure mode CLAUDE.md names: *confirm
that the intended test failed, that it failed for the intended reason, and that
a different guard did not fire first.* Two of the eighteen reasons said
`TypeError: Repo.audit() takes from 2 to 4 positional arguments but 5 were
given`, which is what gave it away.

M4b is the mutation that was intended, and it is red on the two assertions that
actually watch for a write. M4c exists because M4b alone would not have proven
the broader claim: a stray file is caught by the store snapshot and is **not**
caught by the audit-row test, so both tests are load-bearing and neither is
redundant.

**The previous entry's M4 row said `RED 2` with the `audit.jsonl` hash moving.
That is the correct result and it is what M4b now measures — but the mutation
recorded beside it was not the one that produced it.** Same verdict, different
evidence; the verdict stands, the evidence is now the right evidence.

## 3. The bounded gate was widened, and the widening was derived rather than chosen

The first `0030` run bounded its gate to four modules, chosen by reading what
walks `pages.NAV`: `test_demo_smoke`, `test_tenancy_penetration`,
`test_slack_route`, `test_web_invariants`. That reasoning is sound as far as it
goes. It is not the whole coupling, and the gap was found by asking the question
the other way round: **which test modules are coupled to any change in this
repository by construction?**

Answer, measured by scanning all of `tests/` for a walk mechanism rooted at a
repository path rather than a temp directory — nineteen modules use `os.walk`,
`rglob` or `glob.glob`, and **ten of them walk a repository root**:

    test_a_credential_is_checked_by_its_real_name     os.walk        NOT measured before
    test_campaign_audit                               os.walk        NOT measured before
    test_deployment_config                            os.walk        NOT measured before
    test_invariants                                   os.walk,glob   NOT measured before
    test_nothing_talks_back_to_a_prospect             os.walk        NOT measured before
    test_nothing_writes_to_a_provider                 os.walk        NOT measured before
    test_research_audit                               os.walk        NOT measured before
    test_transport_audit                              os.walk        NOT measured before
    test_variant_wiring                               os.walk        NOT measured before
    test_web_invariants                               glob.glob      in the original four

`test_nothing_writes_to_a_provider` is the sharpest of the nine. Its
`test_every_http_write_in_the_repository_is_declared` walks the whole tree and
requires every HTTP write anywhere in it to appear in an allowlist that already
names `("src/web/oidc.py", "POST")`. A change that adds 380 lines to the web
tier is exactly the kind of change it exists to notice, and it was outside the
gate.

### The result: zero new names, zero gone, in both directions

Both legs ran the same ten modules with `-v`. Both trees **LF**, and that was
established before anything was compared, because `qwen/0060` measured thirteen
names that flip between a CRLF and an LF checkout at the same SHA:

    reference worktree  requirements.txt  CR=0  797 B  LF   detached at 49a6fc753, under $TEMP
    this tree           requirements.txt  CR=0  797 B  LF
    git diff b1f290c84 49a6fc753 -- src tests          EMPTY — the reference's
                                                       src/ and tests/ are
                                                       byte-identical to origin/master

    reference  49a6fc753   273 collected   9 failing   110.9s   exit 1
    branch     149ae6307   273 collected   9 failing    89.4s   exit 1

    FAILING   : NEW at branch 0   GONE at branch 0   sets identical
    COLLECTED : NEW at branch 0   GONE at branch 0   sets identical

Diffed as **sets, both directions**, never by count — three finished suites in
this repository once reported exactly 231 failing names and one of them was a
different 231.

**And the reasons were compared too, not only the names**, because a name can
fail for a different cause on each side and still diff clean. All nine
assertion messages are identical on both sides, character for character:
9 same, 0 differing.

### The nine failures are pre-existing, and not one of them names this change

They fail identically at `49a6fc753`, whose `src/` and `tests/` are
`origin/master`. Each names a file this change did not touch:

    NoSourceFileComposesAResponse.test_no_function_answers_a_prospect
        ['slackfollowup.py:reply_message_for'] != []
    NoUndeclaredProviderWrite.test_every_http_write_in_the_repository_is_declared
        [('scripts/runtime_approval_hash_probe.py', …'POST')] != []
    TestNoSecretsOrRealPeople.test_no_test_fixture_carries_a_real_looking_slack_token
        a fixture token matching xox[baprs]- in test_the_secrets_checklist_never_prints_a_value.py
    TestNothingCanSend.test_emailbison_posts_only_to_routes_it_declares
        v3 carries no bison_campaign_id, so nothing can be checked against it
    TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones
        ['src\\providers\\__init__.py:376'] != []
    TestTheBarrierCoversEveryWriter.test_nothing_was_written_by_that
        the same fixture token, in the same file
    TestTheBarrierCoversEveryWriter.test_the_checklist_has_not_fallen_behind_the_code
        ['reviewapproval'] != []
    TheVocabularyContainsNoSend.test_and_no_send_verb_is_supported
    TheVocabularyContainsNoSend.test_the_declared_operations_are_lifecycle_and_staging_only
        the declared heyreach/bison operation vocabulary

Filed, not escalated, and **not investigated** — the FOCUS RULE says anything
off the critical path becomes a task rather than a work stream. They are
recorded here only to establish that the branch introduced none of them.

### The collector refuses rather than reporting a clean diff

It exits 2 if it finds a `_FailedTest` or fewer than twenty names. The previous
run's first collector produced exactly one name — `_FailedTest.tests`, because
the tree root was not on `sys.path` — and diffed **NEW 0, GONE 0**, which reads
exactly like a pass. A comparison that collected nothing reports clean. Here the
collected total of 273 equals `unittest`'s own `Ran 273 tests` on both legs, and
that agreement is the check that the reader works. Two controls alongside it:
the failing set and the collected set are confirmed to differ (9 vs 273, so the
instrument can tell two sets apart), and a known-absent name is confirmed absent.

### `test_invariants` dirties a tracked file, and in an LF tree it is a line-endings rewrite

Running the ten left `docs/requests/2026-01-01-aaaa.md` modified. Measured:

    after the leg   CR=23   456 B   hash e28dec00b63e…
    after restore   CR=0    433 B   hash 4ec179fc2137…  == HEAD blob

So in an LF tree the modification is `test_invariants` rewriting the file with
CRLF. Restored with `git checkout --` and proven by hash, not by `git status`.
**The durability alarm this trips is not a durability problem** — it is a test
writing to a tracked fixture — and anybody running a suite in this tree should
expect it and restore it the same way.

## 4. Permission, re-checked against the clause the brief cites

`provider_settings.view`, and the choice is asserted off `GRANTS` rather than
restated. Re-measured in the new code, which is the part worth checking:

- **No role literal anywhere in the 840-line delta.** Grepped the diff for
  `super_admin`, `admin`, `operator`, `reviewer`, `viewer`, `client_viewer` as
  string literals: nothing.
- The permission is referenced symbolically at both gates —
  `ws.PROVIDER_SETTINGS_VIEW` in the handler, `workspaces.PROVIDER_SETTINGS_VIEW`
  in the route table.
- The `SECTIONS` entry carries the plain string `"provider_settings.view"`, and
  **that is the convention rather than a departure from it**: all 50 non-`None`
  permission values in `NAV` are plain `str`. The duplication is guarded —
  `test_the_nav_offers_it_on_exactly_the_permission_the_route_checks` ties the
  nav string to the route's constant, and M3a turns it red.

**What `api.py:3223` actually is**, since the brief cites it as the reason for
the no-hardcoded-role sentence and a line number alone ages badly: it is
`orchestrator.resume(campaign, by=by, role=roles.ADMIN, recs=recs, …)` — a
resume that hands the orchestrator `roles.ADMIN` as a constant, whoever the
actor is. The role travelling with the action is not the role of the person
performing it.

## 5. SUITE: NOT OBTAINED — the arithmetic, and the recipe to close it

The brief asks for the offline suite diffed by name in both directions against
a reference on the parent. **The full pair was not obtained, for the second
consecutive run, and it was not obtainable inside this window.** Measured
rather than estimated:

    22:00:18   task-suppression-2026-10-14 took work/suite.lock, pid 83540,
               `scripts/run_suite.py --timeout 5400`, confirmed ALIVE by
               Get-CimInstance with a self-check, 462 CPU-seconds at 22:12
    22:09:20   this lane's watcher logged START; its 90-minute timeout kills
               at 23:39:20
    35-45 min  one full leg (CLAUDE.md: 2,100-2,720s)
    ~80 min    a reference leg plus a branch leg

A pair cannot begin before suppression releases (22:35 at the earliest) and
cannot finish before the kill. **The lock was read before and after every
measurement in this run, was held by suppression throughout, and was never
taken, never queued against and never released.** No full suite was started —
and none was started that could not finish, which is the whole of today's
standing-rules lesson about runs that end mid-flight.

**No shortcut is available** and it is worth saying why precisely. The change is
under `src/` and `tests/`, so the operator's 2026-10-02 bounded-alternative rule
gives it no exception: a new reference, with none. And **no existing reference
can be reused**, measured rather than assumed:

- every reference measured today was taken in a **CRLF** lane tree, and this is
  the only LF lane — `qwen/0060` measured thirteen names that flip between the
  two regimes at the same SHA, so those references are void here;
- `qwen/0080`'s `suite_verdict-74fad6c2f.txt` is the one LF-tree full verdict
  on disk (its tree was a `$TEMP` checkout), and **`74fad6c2f` is not even a
  valid object in this worktree** — `git cat-file -t` returns
  `Not a valid object name` — so its SHA cannot be related to this branch at
  all, let alone its `src/` tree compared.

**What it needs, so a task file can execute it without re-deriving any of
this.** The reference worktree recipe below was used and verified in this run,
on the ten-module legs, and comes out LF:

    git worktree add --detach <$TEMP path> 49a6fc753     with GIT_CONFIG_SYSTEM
                                                         pointed at an EMPTY file,
                                                         which is what makes it LF
    verify   requirements.txt CR=0, 797 B, matching the lane tree
    verify   git diff b1f290c84 49a6fc753 -- src tests   EMPTY

    leg 1  reference  49a6fc753   py -3 scripts/run_suite.py -v   in that tree
    leg 2  branch     149ae6307   py -3 scripts/run_suite.py -v   in the lane tree

Both with `-v`, because without it a killed run leaves nothing analysable. Both
unpiped, stdout redirected to a file, because a pipe reports the filter's exit
code and destroys the lock announcements. Env-clean (`GIT_CONFIG_*` unset), or
the lock becomes per-worktree and serialises nothing. Then diff the failing
name-sets **as sets, both directions**, and require NEW = 0; parse with
`run_suite._parse_failures` rather than by grepping, and do not point it at the
summary file, which parses to zero names and looks exactly like a clean
reference.

**It needs a dedicated window of at least two hours with the lock free, which
is more than a 90-minute watcher slot allows alongside any other work. UNDONE
AND NOT RE-QUEUED: a file has to be written for it to happen.**

## 6. What is proven without the full suite, stated exactly

- the page's own module is green at 27/27, run alone, four times;
- all four of the brief's required behaviours are mutation-proven red for the
  stated reason and green again after a byte-exact revert — ten mutants, and the
  one that previously survived is now caught;
- thirteen distinct test modules have been diffed by name between the parent and
  the branch across the two runs — the four `NAV` walkers in the first, and the
  ten repository-root walkers here, overlapping in `test_web_invariants` — with
  **zero new failing names, zero gone, and identical failure reasons**;
- what remains unmeasured is every module in neither set: the full suite is
  roughly 14,850 tests and these thirteen modules collect 273 plus the first
  run's 153. **That is a small fraction and this section is not a merge
  verdict.** The gate for a merge is the full pair in §5, and it is not met.
