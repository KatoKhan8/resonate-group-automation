# Infra handoff — 2026-09-23, late

Supersedes `docs/INFRA-HANDOFF-2026-09-23-NIGHT.md` on the host and on
provisioning. Everything that document says about F6, backup encryption and
item 2's call sites is unchanged and still the reference.

Branch `infra`, worktree `../resonate-infra`. Written for a session with no
conversation context.

---

## 0. THE ONE THING TO READ FIRST

**The operator is rebuilding the host. Do not provision until they say it is
back.**

Provisioning ran tonight for the first time and aborted three times. The
third abort left the host with no administrative path — root ssh off, app
user unable to sudo. The operator chose **rebuild the image** over a console
fix, because the host held nothing and a production box should have one run
of one reviewed script as its whole provenance.

All three defects are **fixed and tested** on `infra` at `3e5427ae`. When the
rebuilt host is announced, the sequence is:

    bash scripts/server/provision.sh --check     # via ssh stdin, writes nothing
    bash scripts/server/provision.sh             # same way, as root

and it should complete all nine steps. It has never yet completed.

---

## 1. STATE

    infra      a6b11dc7   pushed, origin/infra agrees
    master     deea87b1   production's, 20:39

`master` was merged into `infra` at `a4924f7c` — clean, no conflicts, 44
commits. Two commits of this session's own work sit on top.

**`46474c6c` IS STILL NOT ON MASTER.** The night handoff's §0 said to adopt
it before the reboot drill. The merge confirms production has not. Without
it `cold_start --verify` looks for each monitor's heartbeat at
`watchsink.heartbeat_path(name)`, where **none of the eight monitors beat**,
polls ten minutes and reports a recovery time that means nothing. This is
still the most load-bearing open item and it is production's, not this
branch's.

No uncommitted work. Nothing running: no suite, no benchmark, no background
task, no connection held open to the host.

---

## 2. WHAT THIS SESSION DID

### 2a. Merged master, then ran provisioning for the first time

`--check` was verified to be a true dry run before anything else — every
file and unit it claims not to touch was checked on the host afterwards and
none had changed. Then the script was executed as root over ssh stdin, so
nothing was written to the host's filesystem to run it.

Three aborts, each **after** its step had already changed the host. Full
account in `docs/MERGE-REQUEST-INFRA-PROVISION-RUN-2026-09-23.md`; the short
version:

    1a  `yes | ufw enable`             exit 141 under pipefail, firewall up,
                                       steps 2-8 never ran
    1b  `systemctl enable --now
        systemd-timesyncd`             unit does not exist on 26.04; chrony
                                       ships and was already synchronising
    1c  step 2b completed              root ssh off AND app user cannot sudo:
                                       --disabled-password, %sudo wants a
                                       password, /etc/sudoers.d empty

1c is the same mistake step 1's header exists to warn about — give yourself
the new way in before removing the old one — through a door nobody checked.
The existing note said to verify a second ssh session as the app user, and
that session **succeeds**. Logging in was never the part that breaks.

Fixed: new step 2a writes and `visudo -c`-validates a NOPASSWD drop-in, and
2b now REFUSES to touch `sshd_config` unless `sudo -n true` is demonstrated
as the app user first.

### 2b. Ten tests that read the plan, not the source

`tests/test_provision_survives_its_own_firewall.py`. They parse what
`--check` emits, because two earlier versions of them could not fail:

- the first time-sync test read the source, which still defines `$TIMECHECK`
  when the line that runs it has been reverted to the broken `systemctl
  enable` — **it passed against the restored bug**
- a version using `re.S` made `(.*)` swallow the whole file as one match and
  passed against everything
- the sudoers test matched the path `/etc/sudoers.d/90-` anywhere, which
  `visudo -c -f` also names — so a mutation removing the *write* passed

Five mutations are now verified to fail, each for its own reason. If you
touch this file, re-run the mutations; the failure mode here is specifically
a test that looks right and asserts nothing.

---

## 3. HOST FACTS, MEASURED (pre-rebuild — re-confirm after)

Read from the host before it was provisioned. The rebuild should reproduce
all of these; the Python version is the one worth re-checking.

    Ubuntu 26.04.1 LTS, codename resolute, kernel 7.0.0-30-generic
    2 vCPU, 3809 MB RAM, 75 G disk (71 G free)
    python3 3.14.4          well above the 3.12 floor the script enforces
    chrony present and synchronising; systemd-timesyncd NOT installed
    Docker CE publishes a `resolute` repo — step 7 will not abort

That last one was checked because `provision.sh`'s own note warns the Docker
repo historically lags a new LTS by weeks, and under `set -e` a 404 there
would abort the run after steps 1-6 had applied. It returns HTTP 200.

**Host values come only from `hosts/production.env`, gitignored, and are
never printed.** Nothing in the repository reads that file; it is an operator
reference and the address to ssh to.

---

## 4. WHAT IS BLOCKED AND ON WHOM

### 4a. On the operator

- **The rebuild.** Items 1 and 3 wait on it. Nothing else does.
- **`BACKUP_TARGET` and `PUBLIC_HOSTNAME` are EMPTY** in
  `hosts/production.env`. The operator's instruction for this is: write 2e
  and 2f with both as **named, unfilled inputs that refuse** rather than
  guess a hostname or ship an unencrypted archive off-host. Do not invent
  either value.
- **6b, backup encryption**, from TASK-265 and still open: stdlib has none,
  `cryptography` and `pyage` are both third-party against a zero-dependency
  rule, and an unencrypted archive shipped off-host is worse than no off-host
  copy. `work/` carries the action ledger, spend ledger and client approval.
- **F6's five decisions** in §15 of `docs/LOCAL-BUSINESS-SOURCING-DESIGN.md`.
  Operator said they would answer; still open.

### 4b. A trap in `hosts/production.env`

It carries **`HOST_IPV4`, `HOST_IPV6` and `HOST_PLAN` twice** — empty first
from the example, filled second where the operator appended them. `source`
takes the last, so this session read the right values. A parser that takes
the first, or that treats an empty string as set, reads **no address at
all**. Worth deduplicating by hand. Nothing in the repo reads the file, so
nothing can do it automatically, and nothing will fail loudly if it is wrong.

---

## 5. THE QUIET WINDOW IS DERIVED FROM THE WRONG CAMPAIGNS

`provision.sh` step 5 pins the unattended-upgrades reboot to 02:00Z and
derives it, in a comment, from **487 (07:00-15:00Z) and 489 (13:00-21:00Z)**.

The operator's instruction for 2g is that the cutover quiet window comes from
**491-498, not 487/489**. Those are the campaigns that are actually live —
`CLAUDE.md` has 491-498 ACTIVE, and master's own commits tonight are about
491 going blind at 647 queue rows and 495 being archived by nobody we can
name. 487 and 489 are history.

**Step 5's comment and 2g must be re-derived together**, or the runbook and
the reboot timer will disagree about when the estate is quiet. This was NOT
done tonight.

---

## 6. NEXT STEPS, IN ORDER

1. **Wait for the rebuild**, then `--check`, read it, then run it. Verify a
   second ssh session as the app user before closing the first — and this
   time the script itself refuses to harden sshd unless sudo is proven, so
   the check is no longer only a note.
2. **Run the suite on the host** and diff by NAME against
   `docs/state/SUITE-BASELINE-2026-09-23.json`. **Expect 73, not 74**: the
   baseline was measured at `d8232de1` and `ca08363d` fixed
   `test_providers.TestNoSendPathExists.test_every_contactout_post_goes_to_a_read_only_route`.
   A count is not the check; the set difference by name is.
3. **2b systemd units**, 2c `deploy.sh` with rollback, 2d secrets move
   checklist, 2g cutover runbook with the window re-derived per §5. Then 2e
   and 2f as refusing stubs per §4a.
4. **Item 3**, shadow deploy: app installed, secrets in place, monitors NOT
   started, `cold_start --verify` readable, webhook answering a signed test.
   Report readiness; **the operator chooses the cutover evening.**
5. Then E (status JSON), D8 (rate-limit table), D10 (cost ledger), D9
   (cassette tests), item 2 (env mutation at the three call sites named in
   the night handoff §3c), git history dry run.

---

## 7. STANDING RULES

Branch only, never master. Never `config/.env`, `work/` or `src/providers/*`
— the one written exception is the three `os.environ` call sites in the night
handoff §3c, and it is **still not exercised**. No live writes. No timeout
wrappers. Suites detached to a file with name diffs. One merge request per
increment, one line in `#resonate-os` each. Handoff before 150k tokens.

**One rule was broken tonight and is recorded rather than buried.** A host
IPv4 was printed to the session transcript: a redaction filter written for
exactly that purpose had a defect and passed one value through on the first
probe that used it. It was caught, confirmed against the file, and the filter
was rebuilt in Python with a self-test asserting every value round-trips and
that no raw value survives a line containing all of them. The value is a
public address, not a credential. The transcript is under
`~/.claude/projects/`. The operator has been told.
