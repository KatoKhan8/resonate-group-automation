# Infra handoff — 2026-09-24, the server package is built and unrun

Supersedes `docs/INFRA-HANDOFF-2026-09-23-PROVISIONED.md`. Branch `infra`,
worktree `../resonate-infra`. Written for a session with no conversation
context.

---

## 0. THE TWO THINGS TO READ FIRST

**1. SUPERSEDED THE SAME DAY — THE SHADOW DEPLOY IS DONE.** This section
said "2b–2h has never run against the host". That was true when it was
written this morning and is false now. Read
**`docs/SHADOW-DEPLOY-READINESS-2026-09-24.md`** instead of this file for
anything about the host: the package is deployed at
`infra-shadow-2026.09.24e`, the supervisor is installed and NOT started, the
receiver answers over TLS, and a deliberate reboot was survived.

Running it found **four defects** review and a green suite had both missed —
including a Caddy directive that `caddy validate` approved and that meant
something else entirely. The prediction in this paragraph's original text
was correct; it just stopped being the future.

**The rest of this document below §1 is still accurate** as the record of the
merge, the baseline and the design decisions. §5's test count of 91 is now
101.

**2. `46474c6c` is STILL not on master**, four handoffs later. Without it
`cold_start --verify` looks for each monitor's heartbeat at
`watchsink.heartbeat_path(name)`, where none of the eight beat, and reports a
recovery time that means nothing. **It is production's to adopt.** This
session found the same defect a second time, in this branch's own derived
half — see §3.

---

## 1. STATE

    infra      29996819   pushed, origin/infra agrees
    master     5c9fb515   merged in at f23d461a

Ten commits this session on top of `c3a19132`. No uncommitted work. Nothing
running locally or on the host.

    f23d461a  merge master: both hand-written monitor tables deleted
    64d6a425  merge request for that merge
    0d6ed72c  scripts/suite_baseline.py
    61f02fd2  the baseline, re-measured at the merged commit
    ed905c3f  2b  systemd unit, generated from the table
    0e297ff4  2c  deploy.sh with rollback
    4f44631d  2d  secrets checklist, derived
    b3a14a4f  2e  backup with a restore drill, refusing stubs
    0df19557  2f  webhook receiver + Caddyfile, refusing stubs
    29996819  2g  cutover runbook, and 2h tmux units

---

## 2. THE MERGE, AND THE OPERATOR'S PREMISE THAT DID NOT HOLD

Production hand-edited **both** monitor tables to 15 entries for the incident
gate. Both hand-written lists are **deleted**, and the 15 now come from the
derived table — pinned by
`tests/test_the_derived_table_is_the_incident_gates_15.py`.

**The operator asked for a test that the derived set EQUALS those 15. It does
not. It is a bounded superset of 20**, and the five extras are the argument
for deriving rather than a defect in it:

- **`+493`** — approved, same batch as 491–498, **absent from the list a
  person typed while fixing an incident caused by campaigns being absent from
  the list a person typed.** Nobody decided to leave it out.
- **`+451, +481, +484, +485`** — the registry calls them `draft`. Watched
  anyway, because **the registry cannot be trusted to say what is sending**:
  497's own row says `status=approved, launch.state=not_launched` while it was
  sending the blank emails this gate exists for. A rule that retired a watcher
  on `launch.state` would retire 497's.

There is a way to make the set equal 15 exactly and it is the wrong fix;
`test_a_draft_is_still_watched_because_497_sent_while_not_launched` fails if
anyone makes it.

**Two questions for the operator are open** in
`docs/MERGE-REQUEST-INFRA-MASTER-MERGE-THE-15-ARE-DERIVED-2026-09-23.md` §5.
Neither blocks. The second matters more than it looks: the registry's status
vocabulary (`approved`/`draft`/`awaiting_approval`) matches **neither**
`LIVE_STATUSES` nor `FINISHED_STATUSES`, so every campaign takes the
`unknown status` safety branch. **The grace window and the leads-in-sequence
refusal — the interesting half of the rule — are not exercised by real data
at all.**

---

## 3. THE DEFECT THE MERGE FOUND IN THIS BRANCH'S OWN CODE

`scripts/heyreach_watch_loop.py` hardcodes `PROVIDER_ID = 605732` and takes no
`--campaign`, so **which campaign it watches is not a fact about the
registry** — and the derived half was deriving it from the registry. The
registry holds **five** heyreach rows; the derived half kept the lowest-named
(594061, the paused canary), and its heartbeat resolved to
`heyreach-594061.json` — **a file nothing writes**. `cold_start --verify`
would have reported the LinkedIn monitor down forever.

That is `46474c6c`'s defect arriving a second time, through the derived half.

**It was green the whole time.** `MonitorTableTest.ROWS` invents a registry
with exactly one heyreach row and it is 605732, so the fixture agreed with the
loop. A fixture that invents the convenient input is not a witness. Fixed by
declaring `supervisor.HEYREACH_CAMPAIGN`, pinned to the loop's own constant by
a test that reads it with `ast` rather than importing it.

---

## 4. THE BASELINE, RE-MEASURED

`docs/state/SUITE-BASELINE-2026-09-23-MERGED.json`, at `0d6ed72c`, full
discovery **and** 550 modules standalone at the same commit, diffed by name.

    tests run          12205
    distinct failing     170  (full)     165 (standalone)
    vs pre-merge:  73 of 74 still failing, 1 gone, 97 new

**The baseline reproduces and the one that vanished is the predicted one** —
`TestNoSendPathExists...read_only_route`, which `ca08363d` fixed. The rise to
170 is the master merge.

**NEW, and a count-only baseline would have hidden it: five entries fail in
the full run and pass standalone**, all in
`test_ownership_readback_staleness.AStaleReadbackRefuses`. The pre-merge
baseline recorded **zero** and credited
`test_no_test_leaves_the_environment_changed` with keeping it so. **That guard
is still green**, so this leak is not an environment variable and the guard
does not cover the class. `OWNERSHIP_MAX_AGE_HOURS` is not mutated anywhere
else, and the tests pass an explicit path — so the carrier is a module-level
cache, the clock, or the working directory. **Not triaged here**: per the
previous handoff §5, re-measuring and triaging merge-red are two jobs and the
second is production's code.

`scripts/suite_baseline.py` regenerates and diffs. It is validated against
history: run over the committed 09-22 and 09-23 baselines it reproduces that
session's independently computed diff exactly, 14 gone and 6 new, names
included. **Use `--redact-map` for a host comparison** — both sides must be
normalised the same way or every test whose name contains the app username
appears in both directions.

---

## 5. WHAT 2b–2h ARE, AND THE DECISIONS INSIDE THEM

    2b  scripts/server/generate_units.py       13 tests   5/5 mutations
    2c  scripts/server/deploy.sh               13 tests   5/5
    2d  scripts/server/secrets_checklist.py    11 tests   2/3 (1 benign)
    2e  scripts/server/backup.py               14 tests   5/5
    2f  webhook_receiver.py + Caddyfile        23 tests   3/4 (1 not applied)
    2h  generate_tmux_units.py                 10 tests
    2g  docs/SERVER-PACKAGE-2G-CUTOVER-RUNBOOK.md

**91 tests across the seven suites, all green.** *(The 2g/2h commit message
says 117. That is wrong — the correct figure is 91, and it is corrected here
rather than by rewriting a pushed commit.)*

Four decisions worth not re-litigating:

- **2b is ONE unit, not one per monitor.** Units written at deploy time
  freeze a table that is derived precisely so it does not freeze — a campaign
  going live at noon would have no unit until somebody regenerated. The
  supervisor already owns locking, backoff and heartbeats; a per-monitor unit
  adds a second restart policy beside it.
  `test_no_per_monitor_units_are_written` pins it.
- **2c is a single checkout, not `releases/` + a symlink.** `work/` lives
  *inside* the tree; a releases layout orphans the queue, registry and
  heartbeats on every deploy.
- **2f: draining is not accepting.** `src/web/app.py` refuses on the announced
  `Content-Length` before reading a byte (a short read looks like a smaller
  file — 267,107 rows once vanished). A peer cannot read your answer if you
  close while it is still writing. Both rules hold: the receiver reads the
  oversized body and **throws it away unparsed**, purely so the refusal is
  readable, with a bounded drain.
- **2d and 2g are derived/checked, not hand-written**, for the same reason as
  the monitor table.

**Refusing stubs, as instructed:** `BACKUP_TARGET`, `BACKUP_ENCRYPTION`
(2e) and `PUBLIC_HOSTNAME` (2f) all refuse by name and say what they
prevented. A `BACKUP_TARGET` *without* encryption still refuses — a
destination is not permission to send 300 real companies in the clear.

---

## 6. THREE THINGS THIS SESSION GOT WRONG, KEPT RATHER THAN BURIED

**1. A mutation that never applied reported a passing test twice.** A shell
heredoc was collapsing the `\n` escape, so the patch silently no-op'd and the
suite's "OK" meant nothing — indistinguishable from a real pass. Every
mutation since builds its escapes with `chr(92)` and asserts the pattern
matched. **If you mutation-test here, assert the file changed.**

**2. A guard aimed next to the thing it guards.** Replacing 2e's drill
comparison with `len(before) == len(after)` left every drill test green,
because a healthy restore has equal counts either way — and the test written
to prevent exactly that asserted on `inventory()`, which the drill's
comparison never goes through. The comparison is now its own function, tested
directly.

**3. Source-text assertions failed on prose, three times.** A test grepping
for `CONTACTOUT_KEY`, one grepping for `queue`/`providers`, and two grepping
for `Restart=always`/`RemainAfterExit` all failed on the module's **own
comments** explaining what it does *not* do. This is CLAUDE.md's warning
verbatim. They now assert on checklist items, the import graph, and stripped
directives respectively.

Also: the first baseline run was **discarded and re-run**, because it had been
started before `scripts/suite_baseline.py` was written — the hygiene tests
that walk the repository would have seen a file appear mid-run.

---

## 7. NEXT, IN ORDER

1. **Item 3, the shadow deploy.** App installed at a tag, secrets in place,
   **monitors NOT started**, `cold_start --verify` readable, webhook answering
   a signed test *and* an oversized one. Then delete `~/suite-check` (2c does
   it). Then 2h's reboot check — **before logging in**, because logging in is
   what hides a missing `enable-linger`.
   Host values come **only** from the local gitignored `hosts/production.env`,
   never printed. Use the rebuilt Python redactor and self-test it *before*
   the first command.
2. **Report readiness**, and what still needs the operator's `BACKUP_TARGET`
   and `PUBLIC_HOSTNAME`. **The operator chooses the cutover evening.**
3. **Then** E (status JSON), D8 (rate-limit table), D10 (cost ledger), D9
   (cassette tests), the env-mutation item 2 at its three `os.environ` call
   sites — **still not exercised** — and the git history dry run.
4. Open for production, not this branch: the five order-dependent failures
   (§4), and the registry status vocabulary (§2).

---

## 8. STANDING RULES

Branch only, never master. Never `config/.env`, `work/` or `src/providers/*` —
the one written exception, the three `os.environ` call sites, is still not
exercised. No live writes. No timeout wrappers. Suites to a file with name
diffs. One merge request per increment, one line in `#resonate-os`.

**HANDOFF THRESHOLDS, operator directive 2026-09-24, superseding 150k:**
**600k** — write a handoff and KEEP WORKING. **850k** — write a fresh
handoff and STOP for `/clear`. Never hand off mid-push or mid-incident;
finish the unit of work first.

**LANE DIRECTIVE, operator, effective 2026-09-24 until 2026-10-01.** This
session is **LANE 3, infra**: the shadow deploy, then cutover Monday
2026-09-28 after 23:00 Europe/Zagreb, then **nothing else until the estate
has run one clean day on the server**. FROZEN, and to be picked up in
October rather than now: D8, D9, D10, E, F6, the git history dry run, the
history PII scan, gateway evaluations, and the env-mutation item 2 at its
three `os.environ` call sites.

A fresh session in this lane should read
`docs/SHADOW-DEPLOY-READINESS-2026-09-24.md` before anything: the shadow
deploy is DONE, and §3 is the one thing still waiting on the operator.

The 2026-09-23 redaction breach stands recorded in the previous handoff §10.
Every host command since has gone through the rebuilt filter. **Self-test it
against every value before the first command, not after** — the original
defect was a correct filter with the check in the wrong place.
