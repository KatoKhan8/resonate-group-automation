# Merge request — provisioning completes, and the one monitor table

Branch `infra`. Commits `fbbb8996`, `3d673bf3`, `f532b581` on top of the
earlier provisioning work and the `master` merge `a4924f7c`.

---

## 0. THE HEADLINE

**`provision.sh` ran end to end, exit 0, all nine steps, against the rebuilt
host.** It had never completed before. Six defects were found by running it;
all six are fixed, each with a test, and five mutations are verified to fail
those tests.

**The monitor table is now one table**, per the operator's four decisions,
and the campaign watchers are derived from the registry rather than listed.

---

## 1. THE SIX DEFECTS, AND WHAT THEY SHARE

Three were found on the first host (§1a-c, reported in the earlier merge
request) and three on the rebuild (§1d-f).

### 1a. `yes | ufw enable` — exit 141, firewall already up

`ufw` reads one line and exits, `yes` takes SIGPIPE, pipefail promotes 141,
`set -e` aborts. Steps 2-8 never ran. **Invisible** because on a remote host
this looks exactly like ufw dropping the session: you reconnect, the
firewall is correct, and nothing mentions the seven steps that did not
happen.

### 1b. No administrative path — the expensive one

Step 2b turned off root ssh. `adduser --disabled-password` leaves no
password, `%sudo` demands one, `/etc/sudoers.d` was empty, so `usermod -aG
sudo` bought nothing. Host unreachable administratively; the operator
rebuilt it.

**The same mistake step 1 exists to prevent**, through a door nobody
checked. The warning that was already in 2b — *verify a second ssh session
as the app user* — does not help: that session **succeeds**. Logging in was
never the part that breaks.

New step 2a writes and `visudo -c`-validates a NOPASSWD drop-in, and 2b now
**refuses** to touch `sshd_config` unless `sudo -n true` is proven to work
first. A refusal, not a note, because the note was already there.

### 1c. `systemd-timesyncd` does not exist on 26.04

chrony ships and was already synchronising. The step failed while the
condition it wanted was already true, and enabled a service in step 3 that
step 4 had not yet installed. Step 3 now asks whether the clock is
synchronised and installs only if nothing answers.

### 1d. The Docker repo line never substituted its codename

The `$(` was backslash-escaped, so bash did not expand it while building the
string; `eval` then saw it inside **single quotes**, and the literal text
`$(. /etc/os-release && echo $VERSION_CODENAME)` was written into
`docker.list`. apt refused.

**This one is worth reading twice.** The step's own note predicts a failure
that looks identical:

> IF 26.04 HAS NO DOCKER CE REPO YET, this step fails loudly rather than
> silently installing docker.io. Check the codename before cutover; the
> Docker repo has historically lagged a new LTS by weeks.

The repo was fine — `dists/resolute/Release` answers HTTP 200, checked
before the run precisely because of that note. **A correct, prominent
warning stood ready to absorb the blame for an unrelated quoting bug**, and
the next person would have waited for a repository that was already
published. The codename is resolved once into a variable now, so `--check`
prints the real repo line instead of a promise about one.

### 1e. The failure poisoned the next run

`docker.list` stayed on the host, so `apt-get update` **in step 1** failed on
the next attempt and the script aborted at the firewall over a file it had
written itself. The repo file is provisional now: if the update does not
validate it, it is removed and the run refuses. A failure that can simply be
repeated beats one that cannot.

### 1f. CRLF

`core.autocrlf=true`, no `.gitattributes`, so a checkout rewrote the working
copy and bash answered:

    bash: line 22: set: pipefail: invalid option name

Nothing in that message says line endings, and the script had run correctly
minutes earlier — the CRLF arrived with a checkout, not an edit.
`.gitattributes` now pins `*.sh`, `*.bash`, `*.service` and `*.timer` to LF
**in the working tree**, because the working tree is what gets piped to a
Linux host.

### What they share

Every one of them is a step that **takes something away, or writes
something, before the replacement is known to work** — and four of the six
produce a symptom that points somewhere else: a dropped connection, a
lagging upstream repo, a shell that does not support pipefail, a host with
no campaigns.

---

## 2. VERIFIED ON THE HOST, STEP BY STEP

    1   ufw active: 22, 443, default deny incoming
    2   app user, operator's key, groups sudo/users/docker
    2a  /etc/sudoers.d/90-resonate 0440, passwordless sudo PROVEN
    2b  sshd -T (the EFFECTIVE config, so drop-ins count):
        permitrootlogin no / passwordauthentication no
    3   UTC, NTPSynchronized yes, via chrony
    4   git curl ca-certificates sqlite3 fail2ban python3 venv pip
    4b  Python 3.14.4, above the 3.12 floor
    5   unattended-upgrades enabled, Automatic-Reboot-Time 02:00
    6   fail2ban active, sshd jail up
    7   Docker 29.8.1 installed, service DISABLED and INACTIVE,
        docker.list carrying `resolute`
    8   /etc/resonate 750 root:resonate, secrets.env 640, no secret in it

`sshd -T` rather than grepping `sshd_config`, deliberately: 26.04 ships an
`Include /etc/ssh/sshd_config.d/*.conf` at the TOP of the file, so a drop-in
would win over the lines the script edits. The drop-in directory is empty on
this image — checked — but the verification asks the resolved config anyway,
because that is the thing that is actually true.

**Nothing was started that sends. No repository cloned, no `work/` copied,
no secret written.**

---

## 3. THE ONE MONITOR TABLE

All four operator decisions, in `fbbb8996`.

**One table.** `src/supervisor.py` is it; `start_monitors.py`'s hand-written
list is deleted and it reads the supervisor. It also asks
`supervisor.heartbeat_file()` where a beat lands rather than computing
`work/heartbeat/<name>.json` itself — that was a second copy of a liveness
rule, and it was wrong for the three loops that write their beat directly.

**Derived campaign watchers.** running or paused → watched; finished inside
a 7-day grace → watched; finished past it with leads still in sequence →
watched; finished past it with none → retired. Covers 491-498 including the
four whose first sends are 09-24, keeps 495 while it holds
stopped-but-not-finished leads, retires 487 and 489, and nobody edits a list
the day a campaign launches.

**`MONITORS` is now a function.** A derived table computed at import freezes
at process start, and this estate has loops that import once and run for
days — a campaign launched at noon would go unwatched until the next
restart. `_run`'s parameter is renamed `table` for the same reason: a
parameter called `monitors` shadowed the function.

**`bison_mailbox_utilisation` is out**, per decision 3, and the question is
filed to production.

### Two refusals, both measured

**`campaigns.load()` returns an empty snapshot when the registry file is
absent.** It does not raise. Read straight, that turns *I cannot see the
registry* into *there are no campaigns*: the derived half of the table
vanishes, the supervisor comes up with five static loops, watches no
campaign at all, and reports itself healthy. It now checks the file exists
and raises `RegistryUnreadable`; `cold_start` catches it, says so, and
**exits 2**. An empty registry that IS readable is a different answer and is
allowed through.

**The leads-in-sequence source refuses rather than answering zero.** Zero
retires a watcher, so *I could not tell* must not be spelled the same way as
*it is empty*. The default source raises and a raise reads as keep watching.
An extra watcher costs provider calls; a missing one costs the thing the
watcher was for.

The retirement clock reads `completed_at` on the campaign row and **never
the watcher's own heartbeat** — a watcher that has died writes no beat, and
a rule reading the beat would retire the watcher that was supposed to
notice.

---

## 4. TESTS

    tests/test_provision_survives_its_own_firewall.py   13, 1 skipped off-host
    tests/test_supervisor.py                            +3, all green
    tests/test_the_estate_comes_back_after_a_reboot.py  +1, all green

The provisioning tests read the **plan `--check` emits**, not the source.
Three versions of them could not fail before this was settled: one read the
source and passed against the restored time-sync bug, because the source
still defines `$TIMECHECK` when the run line has been reverted; one used
`re.S` so `(.*)` swallowed the whole file as a single match; one matched the
sudoers path anywhere, which `visudo -c -f` also names.

A fourth near-miss is worth recording: the first mutation written for the
Docker quoting bug **used an unescaped `$(`**, which bash expands at
string-construction time — a different, also-broken line that the test
correctly did not flag. Reproducing the real bug needed the backslash. A
mutation that does not reproduce the defect proves nothing about the test.

---

## 5. WHAT IS STILL OPEN

- **`46474c6c` is still not on master**, three merges later.
- **`BACKUP_TARGET` and `PUBLIC_HOSTNAME` are still empty** in
  `hosts/production.env`; 2e and 2f get refusing stubs per the operator's
  instruction.
- **2b-2g proper are not built.** The units were blocked on the table
  question, which is now answered — generating them is the next task.
- **2h is specified, not built** (`docs/SERVER-PACKAGE-2H-TMUX-SESSIONS.md`);
  two of its three worktrees do not exist on the host until `deploy.sh`.
- `hosts/production.env` still carries three duplicated keys, empty first and
  filled second.
