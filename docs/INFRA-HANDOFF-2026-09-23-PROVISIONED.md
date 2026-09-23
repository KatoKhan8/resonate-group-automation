# Infra handoff — 2026-09-23, host provisioned

Supersedes `docs/INFRA-HANDOFF-2026-09-23-LATE.md`, which superseded the
night handoff. Branch `infra`, worktree `../resonate-infra`. Written for a
session with no conversation context.

---

## 0. THE TWO THINGS TO READ FIRST

**1. The host is provisioned and empty.** `provision.sh` ran end to end,
exit 0, all nine steps — the first time it has ever completed. Verified step
by step on the host. **Nothing is deployed, nothing is started, no secret is
written, no `work/` copied.** The next thing it needs is `deploy.sh`, which
does not exist yet (2c).

**2. `46474c6c` is STILL not on master**, three merges later. The night
handoff made it §0 and it has not moved. Without it `cold_start --verify`
looks for each monitor's heartbeat at `watchsink.heartbeat_path(name)`,
where **none of the eight beat**, polls ten minutes, and reports a recovery
time that means nothing. It is production's to adopt.

---

## 1. STATE

    infra      aef8e1b8   pushed, origin/infra agrees
    master     deea87b1   production's, 20:39, merged in at a4924f7c

Six commits of this session's work on top of the merge. No uncommitted work.
Nothing running locally or on the host.

**Access to the host changed.** Root ssh is disabled by design. Connect as
the app user; it has passwordless sudo:

    ssh <SSH_USER>@<host>            # values from hosts/production.env only
    ssh <user>@<host> 'sudo -n bash -s' < scripts/server/provision.sh

`tr -d '\r'` the script before piping it — see §4f.

---

## 2. WHAT THE HOST HAS

Verified field by field after the run, not assumed:

    1   ufw active: 22, 443, default deny incoming
    2   app user, operator's key, groups sudo/users/docker
    2a  /etc/sudoers.d/90-<user> 0440, passwordless sudo PROVEN
    2b  sshd -T: permitrootlogin no, passwordauthentication no
    3   UTC, NTPSynchronized yes, via chrony
    4   git curl ca-certificates sqlite3 fail2ban python3 venv pip
    4b  Python 3.14.4
    5   unattended-upgrades enabled, Automatic-Reboot-Time 02:00
    6   fail2ban active, sshd jail up
    7   Docker 29.8.1 installed, service DISABLED and INACTIVE
    8   /etc/resonate 750 root:<user>, secrets.env 640, empty

`sshd -T` rather than grepping the config file, because 26.04 puts
`Include /etc/ssh/sshd_config.d/*.conf` at the TOP of `sshd_config` and a
drop-in would win over the lines the script edits. The drop-in directory is
empty on this image — checked — but the verification asks the resolved
config anyway, because that is what is actually true.

There is also a **staging copy of the repository at `~/suite-check`** on the
host, put there to run the suite. It has no `.git`, no `work/`, no `hosts/`.
It is not a deployment and `deploy.sh` should not build on it — delete it
when 2c lands.

---

## 3. THE SUITE ON THE HOST, BY NAME

See §5 for the full comparison. The headline:

**The baseline reproduces exactly.** 73 of the baseline's 74 entries fail on
the host, and the one that does not is precisely the one the night handoff
predicted would be gone:

    test_providers.TestNoSendPathExists
        .test_every_contactout_post_goes_to_a_read_only_route

fixed by `ca08363d`. Expect 73, not 74 — confirmed on a different machine,
a different OS and a different Python.

**Only 17 failures are host-only, and 0 are local-only.** The suite was run
on BOTH machines at the same commit and diffed by name. Thirteen of the 17
need a `.git` the staging copy does not have; **four are a real Linux
difference that 2f has to know about** — see §5. The rise from 74 to 132 is
the master merge, not the host: the baseline was measured at `dc395fa1`,
before this session merged 44 commits. **It is stale, and a count against it
means nothing until re-measured.**

---

## 4. THE SIX DEFECTS, AND WHY THEY MATTER BEYOND THEMSELVES

All six were found by running the script. All six are fixed, each with a
test, five mutations verified to fail those tests.
`docs/MERGE-REQUEST-INFRA-PROVISION-COMPLETE-2026-09-23.md` is the long
version.

    4a  yes | ufw enable            exit 141, firewall already up
    4b  no sudo password            no admin path, root ssh already off
    4c  systemd-timesyncd           unit does not exist on 26.04
    4d  docker repo codename        never substituted; written literally
    4e  the failure persisted       poisoned step 1 of the next run
    4f  CRLF                        set: pipefail: invalid option name

**What they share, and the thing to carry forward: four of the six produce a
symptom that points somewhere else.**

- 4a looks like ufw dropping your ssh session. Reconnect and the firewall is
  correct — which proves the firewall works and nothing about the seven
  steps that never ran.
- 4b's warning was already written and was about the wrong failure: it says
  verify a second ssh session as the app user, and that session **succeeds**.
- 4d is the sharpest. The step's own note predicts "if 26.04 has no Docker CE
  repo yet, this step fails loudly... the repo has historically lagged a new
  LTS by weeks." **The repo was fine** — `dists/resolute/Release` answers 200.
  A correct, prominent warning stood ready to take the blame for a quoting
  bug in the line below it, and the next person would have waited for a
  repository that was already published.
- 4f says `set: pipefail: invalid option name`, which names neither line
  endings nor git, and the script had run correctly minutes earlier — the
  CRLF arrived with a checkout, not an edit.

`.gitattributes` now pins `*.sh`, `*.bash`, `*.service`, `*.timer` to LF **in
the working tree**, because the working tree is what gets piped to a Linux
host. Note that a Python `write_text` on Windows re-introduces CRLF by
default: use `newline="\n"` or write bytes.

---

## 5. THE SUITE, MEASURED ON BOTH MACHINES

The host run alone could not answer "is anything host-specific?", so the
same suite was run locally at the same commit and the two failing sets were
diffed BY NAME.

    baseline (dc395fa1, PRE-merge)   74 distinct
    local,  merged tree             132 distinct
    host,   merged tree             149 distinct

    baseline entries still failing LOCALLY    73 / 74
    baseline entries still failing ON HOST    73 / 74
    the one that is gone, on both:
        test_providers.TestNoSendPathExists
            .test_every_contactout_post_goes_to_a_read_only_route

**The baseline's content reproduces exactly, on both machines, and the only
entry that disappeared is the one the night handoff predicted** (`ca08363d`
fixed it). Expect 73, not 74 — now confirmed on a different OS and a
different Python build.

    HOST-ONLY   17     fail on the host, pass locally
    LOCAL-ONLY   0

So the merge, not the host, accounts for the rise from 74 to 132. **The
baseline was measured before this session merged 44 commits of master
(`a4924f7c`), so it does not describe this tree, and a count against it
means nothing until it is re-measured.**

### The 17 host-only failures

**Eleven need a `.git` directory** and the staging copy has none — every
`*_is_gitignored`, `TestNoRealDataAnywhereInGit`,
`TestTheSuppressionRosterIsNotInGit`, `test_git_ignores_config_env`,
`test_the_start_date_comes_from_the_first_commit`. `git ls-files -z` exits
128. An artifact of how the tree was staged, not a defect, and a reason not
to re-measure the baseline from `~/suite-check`.

**Two more are the same family**: `test_the_pack_reports_its_own_numbers`
and `test_every_phone_number_is_a_reserved_fiction` both read the tree the
same way.

**Four are a genuine platform difference, and they matter for 2f.**
`test_upload_is_never_truncated.AnOversizedUploadIsRefused`, all four, fail
on Linux with:

    BrokenPipeError: [Errno 32] Broken pipe
    urllib.error.URLError: <urlopen error [Errno 32] Broken pipe>

The server refuses the oversized body and closes the connection before the
client has finished sending it. On Windows the client still reads the
refusal; **on Linux it gets EPIPE and never sees the message at all.** The
test asserts the refusal *says what the limit is*, and on the host there is
no response to read.

This is not a test artifact to wave away. **The webhook receiver in 2f will
run on this Linux host**, and a receiver that drops the connection on an
oversized or malformed body — rather than returning a readable refusal —
gives the sender a transport error instead of an answer. Whoever builds 2f
should read this cluster first: the refusal has to be sent *after* the body
is drained, or the peer never gets it.

### Two jobs, and conflating them is how a merge regression gets filed as a host problem

1. Re-measure the baseline at the merged commit, on one machine, full
   discovery and per-module standalone, diffed by name.
2. Triage separately what the merge turned red. That is production's code,
   not this branch's.

**One oddity worth not chasing:** the host run reported
`Ran 11999 tests in 684029s` — 7.9 days, for a run of about twenty minutes.
The host's timezone was set to UTC during provisioning, in the same window.
A clock artifact in the runner's elapsed measure, not a hung test.

**And one measurement trap that cost a wrong answer here:** the host's
failing names were passed through the host-value redactor and the local
ones were not, so every test whose NAME contains the app username appeared
in both "host-only" and "local-only". It looked like a real divergence. Both
sides have to be normalised the same way before a set difference means
anything.

## 6. WHAT IS BUILT, AND WHAT IS NOT

    2a  provisioning script        DONE and RUN, nine steps, exit 0
    2b  systemd units              NOT BUILT - unblocked now, see §7
    2c  deploy.sh with rollback    NOT BUILT
    2d  secrets move checklist     NOT BUILT
    2e  backup to off-host target  BLOCKED: BACKUP_TARGET empty, and the
                                   6b encryption decision is still open
    2f  Caddy + webhook receiver   BLOCKED: PUBLIC_HOSTNAME empty
    2g  cutover runbook            window DERIVED (§8), runbook not written
    2h  three tmux sessions        SPECIFIED, not built - needs 2c first
                                   docs/SERVER-PACKAGE-2H-TMUX-SESSIONS.md

Operator's instruction for 2e and 2f: build them with the two values as
**named, unfilled inputs that refuse** rather than guessing a hostname or
shipping an unencrypted archive off-host.

---

## 7. THE MONITOR TABLE IS ONE TABLE NOW

Operator's four decisions are implemented in `fbbb8996`. This is what
unblocks 2b, because units generated from the wrong table would have watched
487 and 489 — finished — and none of the four campaigns that are sending.

- `src/supervisor.py` is the single source; `start_monitors.py` reads it and
  its hand-written list is gone. It also asks `supervisor.heartbeat_file()`
  where a beat lands instead of computing the path itself.
- Campaign watchers are **derived**: running or paused → watched; finished
  inside a 7-day grace → watched; finished past it with leads in sequence →
  watched; otherwise retired.
- **`MONITORS` is a function, not a constant.** A derived table computed at
  import freezes at process start, and this estate has loops that import once
  and run for days.
- `bison_mailbox_utilisation` is out, per decision 3, and filed to
  production.

**Two refusals that are load-bearing.** `campaigns.load()` answers an ABSENT
registry file with an empty snapshot rather than an error — read straight,
that turns "I cannot see the registry" into "there are no campaigns", and
the supervisor comes up watching five static loops and reports itself
healthy. It now raises `RegistryUnreadable` and `cold_start` exits 2. And
the leads-in-sequence source **refuses rather than answering zero**, because
zero retires a watcher.

---

## 8. THE QUIET WINDOW, RE-DERIVED

`docs/THE-QUIET-WINDOW-IS-THREE-TIMEZONES-2026-09-23.md`.

491-498 have **cohort timezones**, not UTC windows — five America/New_York,
two Europe/London, one Europe/Zagreb — so the union moves twice a year, in
two different weeks:

    now, all DST on        07:00Z-21:00Z    quiet 21:00Z -> 07:00Z
    after EU falls back    08:00Z-21:00Z    quiet 21:00Z -> 08:00Z
    after US falls back    08:00Z-22:00Z    quiet 22:00Z -> 08:00Z

02:00Z is inside the band in all three, **so the reboot time does not move**.
What moves is the margin against nightly sourcing: it is pinned at 02:00
Europe/Zagreb, which is 00:00Z in CEST and 01:00Z in CET, so the gap halves
from two hours to one on the last Sunday in October. Named, not fixed — it
is a running production job.

---

## 9. NEXT STEPS, IN ORDER

1. **2b systemd units**, generated from `supervisor.monitors()`. Unblocked.
2. **2c `deploy.sh`** with rollback, deploying a tag. Then delete
   `~/suite-check` from the host.
3. **2d secrets checklist**, then **2g** using §8's window.
4. **2e and 2f** as refusing stubs until the operator fills the two values.
5. **Re-measure the suite baseline** at the merged commit, by name, per §5.
   This is a prerequisite for item 3's readiness claim, not a nice-to-have.
6. **Item 3, shadow deploy**: app installed, secrets in place, monitors NOT
   started, `cold_start --verify` readable, webhook answering a signed test.
   Then 2h's verification — reboot and check the three sessions BEFORE
   logging in, because logging in is what would hide a missing
   `enable-linger`.
7. Report readiness. **The operator chooses the cutover evening.**
8. Then E (status JSON), D8, D10, D9, item 2's three `os.environ` call sites,
   git history dry run.

---

## 10. STANDING RULES

Branch only, never master. Never `config/.env`, `work/` or `src/providers/*`
— the one written exception, the three `os.environ` call sites, is **still
not exercised**. No live writes. No timeout wrappers. Suites to a file with
name diffs. One merge request per increment, one line in `#resonate-os`.
Handoff before 150k tokens.

**A rule was broken earlier in this session and is recorded rather than
buried.** A host IPv4 reached the transcript: a redaction filter written for
exactly that purpose had a defect and passed one value through on the first
probe that used it. It was caught, confirmed against the file, and rebuilt
in Python with a self-test asserting every value round-trips and that no raw
value survives a line containing all of them. Every host command since has
gone through it. The value is a public address, not a credential; the
transcript is under `~/.claude/projects/`. The operator has been told.
