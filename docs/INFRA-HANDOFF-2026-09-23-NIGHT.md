# Infra handoff — 2026-09-23, night

Written for a session with no conversation context. Branch `infra`, worktree
`../resonate-infra`.

---

## 0. THE ONE THING TO READ FIRST

**`46474c6c` is NOT on master, and tonight's reboot drill needs it.**

Production merged infra at `bbc5df69` ("TASK-251..265, cold start, supervisor,
test isolation"), taking everything up to and including `ca08363d`. Five
commits landed after that merge and the first of them is the one that matters
tonight:

    46474c6c  supervise --status on two witnesses, and the heartbeat map

Without it, `cold_start --verify` looks for each monitor's heartbeat at
`watchsink.heartbeat_path(monitor_name)`. **Not one of the eight monitors
beats there.** The check finds zero heartbeats for all eight, polls for ten
minutes, times out, and reports a recovery time that means nothing.

**Adopt `46474c6c` or later before the drill.** Everything else in this
document can wait until tomorrow.

---

## 1. BRANCH AND REMOTE STATE

    infra          1c700126   pushed, origin/infra agrees
    master         16454a45   "Enable heyreach.stop_lead, and find it could
                              never have worked"  (production's, 20:26)

    master..infra  5 commits  listed in section 2b
    infra..master  43 commits production's work today, not merged here

No uncommitted work in this worktree. Nothing is running: no suite, no
benchmark, no background task.

---

## 2. WHAT MERGED TODAY

### 2a. On master already, via `bbc5df69`

    TASK-264  test isolation. Order-dependence is ZERO: full discovery and
              per-module standalone measured at the same commit and diffed by
              name, 74 = 74. Baseline 82 -> 74 as a set diff.
              tests/envisolation.py restores the environment between modules;
              tests/test_no_test_leaves_the_environment_changed.py is the
              guard that fails NAMING the module and the variable. Fifteen
              modules were cleaned - twelve, then three more the guard found
              once the first twelve stopped masking them.

    TASK-265  nightly backup and restore drill, recovered from qwen-worker-6
              and then attacked: five defects, each of the shape "reports
              success while not doing the work". Drill artifact at
              docs/RESTORE-DRILL-AT-SCALE-2026-09-23.md - 20,000 records back
              up in 2.0s and restore+verify in 9.4s.

    D1        cold start. scripts/cold_start.py, scripts/install_autostart.py,
              docs/COLD-START-RUNBOOK-2026-09-23.md, 27 tests.

    keepawake wired into supervisor._run. It had landed on master with NO
              CALLER because supervisor.py lives on infra; hardening 6 names
              exactly that. `powercfg /requests` names a process only once the
              supervisor is running - and requires elevation to read at all.

    ContactOut allowlist, ca08363d. One definition in tests/base.py read by
              both guards. test_providers' copy had been RED since 09-22, on
              master too: c56800ae added /company/search to test_invariants'
              copy and there were two.

### 2b. On infra only — the five commits master does not have

    1c700126  --check must not write (provision.sh)
    e71281ff  docs/SERVER-SIZING-2026-09-23.md, measured
    d8186c13  scripts/server/provision.sh for Ubuntu 26.04
    46474c6c  supervise --status two witnesses + heartbeat map   <- TONIGHT
    d9a2737c  docs/LOCAL-BUSINESS-SOURCING-DESIGN.md (F6, review only)

---

## 3. WHAT PRODUCTION OWES

### 3a. Adopt `46474c6c` or later — before the drill

See section 0. Two statuses arrive with it that are new and deliberate:

    STARTING        process up, no beat yet, started under one interval ago.
                    Normal for the first minutes after a restart, and without
                    it every monitor reads DOWN during the window being
                    measured.
    UP_ONE_WITNESS  the monitor writes NO heartbeat, so only the pid can be
                    checked. It can never read UP.

### 3b. Two heartbeat findings, named and NOT fixed

Both change running production loops, so they are production's call.

1. **Three loops bypass `watchsink`** and write `work/heartbeat/<name>.json`
   themselves: `notify_deliver_loop`, `digest_loop`, `slack_agent_loop`.
   Two mechanisms for one job; `watchsink` exists so the format is one thing.

2. **`bison_mailbox_utilisation` writes no heartbeat at all.** For that
   monitor, "gone quiet" and "died" are indistinguishable — which is the
   sentence `src/supervisor.py`'s own docstring opens with. It reports
   `UP_ONE_WITNESS` and can never be fully confirmed.

The map is declared in `supervisor.MONITORS` and pinned by
`test_the_real_table_resolves_to_the_files_the_loops_write`, so if a loop
moves its beat, a test fails instead of the estate silently reading down.

### 3c. Item 2 — production code mutates `os.environ`

This was assigned to the production session and is **not done**. The files
are:

    src/providers/__init__.py   load_env()  -> os.environ.setdefault per key
    src/providers/deliverable.py:94          -> os.environ[var] = str(value)
    src/web/demoslack.py:227                 -> setdefault(OPS_CHANNEL_VAR)

(The assignment named `replies.py`; the three call sites measured today are
the ones above. If `replies.py` is a separate instance, it was not found by
the whole-environment scan.)

Four of the fifteen leaking test modules trace to these. The infra-side
workaround is module-level save/restore in `test_a_refusal_is_not_a_purchase`,
`test_demo_mode`, `test_persistent_volume`, `test_xai_adapter` — **those four
hooks are what can be deleted once item 2 lands**, and nothing else.

**The harness itself must NOT be removed.** Eleven of the fifteen leaks were
test-side and unrelated to `os.environ` mutation in `src/`: `CampaignTest`
restoring in `tearDown` where unittest skips it, a module importing
`setUpModule` without `tearDownModule`, two dropping the `use_directory`
restore. Removing `tests/envisolation.py` reopens that class immediately.

Item 1 of that assignment — `store.use_directory` returning a restore
callable — **is already done**, on infra at `cdd63566`, now on master. If the
production session implements it too, two versions of one contract change
meet at a merge.

---

## 4. THE HOST, AND WHY PROVISIONING DID NOT RUN

**Provisioning was authorized and did not run.** `hosts/production.env` **is
not on disk** — only `hosts/production.env.example`, which is committed.
Without it there is no address, and guessing or scanning for one is not a
thing to do.

**Every host value lives in `hosts/production.env`, gitignored, and no value
appears in this document or in any committed file.** The shape of that file
is `hosts/production.env.example`.

Facts given by the operator and recorded in `scripts/server/provision.sh`'s
header as the target it was written against: Hetzner Cloud, hel1, 4 GB plan,
~75 GB disk, Ubuntu 26.04.1 LTS, kernel 7.0, IPv4 and IPv6.

### The sizing answer, measured

`docs/SERVER-SIZING-2026-09-23.md`. **37,458 bytes of Python heap per
record**, flat from 550 to 20,000 records (tracemalloc, three sizes).

    550 records     ~900 MB total on the host, everything running
    <=5,000         comfortable in any arrangement
    5,000-15,000    fine at 2-3 concurrent loaders, not at 11
    >=20,000        wrong host: one loader alone is 749 MB

Ends sooner if the F6 sourcing container runs (headless browser + dockerd,
1-1.5 GB) or if two full loads overlap. **Cut over on 4 GB**; flag at 10,000
records; Hetzner resizes in place with a reboot, which is now a four-minute
event.

---

## 5. SERVER PACKAGE STATUS

    2a  provisioning script          DONE, NEVER RUN     scripts/server/provision.sh
    2b  systemd units                NOT STARTED
    2c  deploy.sh                    NOT STARTED
    2d  secrets move + checklist     NOT STARTED
    2e  backup to off-host target    PARTIAL - the scripts exist from TASK-265
                                     (backup_state.py, restore_drill.py) and the
                                     drill has run locally; the OFF-HOST TARGET
                                     and ENCRYPTION are both unanswered, see 6b
    2f  HTTPS webhook endpoint       NOT STARTED
    2g  cutover runbook              NOT STARTED

`provision.sh` notes that are decisions, not details:

- **Firewall is step 1**, and 22 is allowed **before** `ufw enable` — the
  other order locks you out of a remote host.
- **Port 80 is closed**, so ACME must use **TLS-ALPN-01** on 443. Caddy tries
  HTTP-01 first unless told otherwise. This bites 2f.
- **Python is checked, not pinned.** The brief said 3.12; the script refuses
  below 3.12 and says the real confirmation is the suite on the host.
- **Reboot pinned to 02:00Z**, derived: sends are 07:00-21:00Z across 487 and
  489, sourcing is 00:00Z, so the quiet band is 21:00Z-07:00Z.
- **Docker installed and DISABLED.** F6 is unapproved and dockerd costs
  ~100 MB on a 4 GB host.

---

## 6. WHAT IS WAITING ON THE OPERATOR

### 6a. F6, the five decisions in §15 of `docs/LOCAL-BUSINESS-SOURCING-DESIGN.md`

Operator said they will answer tomorrow.

1. Scraper, SERP vendors, or neither? The scraper breaks Google's ToS; the
   vendors move that onto a contract; the licensed Places API **cannot hold
   this estate** (only `place_id` is cacheable indefinitely).
2. Which countries may receive email? Default is none. UK PECR's corporate
   exemption does **not** cover sole traders and partnerships; Germany's UWG
   effectively requires prior consent even B2B, and DE is in the geo list.
3. Domainless businesses: drop them, or change the record schema? Collision
   and suppression both key on domain, and ~a third of this ICP has no
   website. **An Art 21 objection from a domainless business cannot be
   recorded where the next sourcing run will read it.**
4. Phone now or later? The design says later — CTPS/TPS screening does not
   exist here.
5. Review text: derive only, never quote?

### 6b. Backup, from TASK-265 and still open

- **Encryption.** stdlib has none. `cryptography` or `pyage`, both
  third-party against a zero-dependency rule.
- **Off-host target.** None configured. The worker correctly refused to
  invent one.

They are **one decision**: an unencrypted archive shipped off-host is worse
than no off-host copy. `work/` carries the action ledger, spend ledger and
client approval.

---

## 7. EXACT NEXT STEPS, IN ORDER

1. **Production adopts `46474c6c` or later**, then runs the drill per
   `docs/COLD-START-RUNBOOK-2026-09-23.md`, verifying with
   `py -3 -m scripts.cold_start --verify` and **not** `supervise --status`
   on a pre-`46474c6c` checkout.
2. **Operator creates `hosts/production.env`** from the example. Provisioning
   is blocked until it exists.
3. **`bash scripts/server/provision.sh --check` on the host**, read the plan,
   then run it. Verify a second ssh session as the app user **before** closing
   the first — step 2b turns off root login and passwords.
4. **Run the suite on the host** and diff by name against
   `docs/state/SUITE-BASELINE-2026-09-23.json`. See the note in section 8.
5. **2b systemd units**, then 2c deploy.sh, 2d secrets, 2f webhook, 2g
   cutover runbook. 2e needs the 6b decision first.
6. Then the rest of the standing queue: status JSON (3), provider rate-limit
   table (4), daily cost ledger (5), cassette contract tests (6), git history
   rewrite dry run (7).

---

## 8. TWO THINGS THAT WILL LOOK WRONG AND ARE NOT

**The baseline JSON is one commit stale, by exactly one test.**
`docs/state/SUITE-BASELINE-2026-09-23.json` was measured at `d8232de1` and
lists 74 distinct failures including
`test_providers.TestNoSendPathExists.test_every_contactout_post_goes_to_a_read_only_route`.
`ca08363d` fixed that one. **Expect 73, not 74**, on any measurement at
`ca08363d` or later. Production already noticed this in `bbc5df69`'s message
and was right.

**`--status` reporting `UP_ONE_WITNESS` is not a degradation.** It means the
monitor writes no heartbeat and therefore cannot prove it is working. Before
`46474c6c` the same monitor read `UP` from a pid alone, which is the claim a
reused pid forges across a reboot.

---

## 9. STANDING RULES THIS SESSION WORKED UNDER

Branch only, never master. Never `config/.env`, `work/` or
`src/providers/*` — the one exception was authorized in writing for the three
`os.environ` call sites in section 3c and **was not exercised**. No live
writes. No timeout wrappers. Suites detached to a file with name diffs. One
merge request per increment, one line in `#resonate-os` each.
