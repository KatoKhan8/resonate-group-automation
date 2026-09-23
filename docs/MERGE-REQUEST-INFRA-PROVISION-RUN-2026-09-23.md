# Merge request — increment 1: provisioning, run for the first time

Branch `infra`, commit `3e5427ae`, on top of the `master` merge `a4924f7c`.
Two files: `scripts/server/provision.sh` and one new test module.

---

## 0. THE ONE THING TO READ FIRST

**The host has no administrative path and needs the Hetzner console.**

Provisioning ran. Steps 1, 2 and 2b applied; step 3 aborted; steps 4-8 never
ran. Step 2b turned off root ssh — correctly, that is its job — and the app
user it handed the estate to **cannot sudo**. Both doors are shut.

Nothing is deployed, nothing is started, no data moved, no secret written.
The host is a firewalled empty Ubuntu box. **The blast radius is a host with
nothing on it**, which is the only reason this is a merge request and not an
incident.

Recovery is in §4 and is two minutes of operator time.

---

## 1. WHAT WAS ASKED, AND WHAT RUNNING IT FOUND

The instruction was: `--check`, show the plan, then execute. All three
happened. `--check` was verified to be a true dry run first — nothing on the
host changed, confirmed field by field — and then the script was executed.

It aborted three times. **Each abort came after the step had already changed
the host**, which is the property that makes all three worth a test rather
than three one-line fixes.

### 1a. `yes | ufw enable` — exit 141, firewall already up

`ufw enable` reads one line and exits. `yes` is then killed by SIGPIPE and
the pipeline reports 141. The script runs under `set -euo pipefail`, so
pipefail promotes the dead `yes` to the pipeline's status and `set -e` aborts
on it — one line after the firewall came up.

**Why it is invisible.** Enabling a firewall on a remote host looks exactly
like a dropped connection: output stops mid-run. The natural reading is "ufw
disrupted my ssh session"; the natural next move is to reconnect and find the
firewall correctly configured. Reconnecting proves the firewall works. It
proves nothing about the seven steps that never ran, and nothing anywhere
mentions them.

Fixed to `ufw --force enable` — ufw's own non-interactive flag, no pipeline.

### 1b. `systemctl enable --now systemd-timesyncd` — unit does not exist

Ubuntu 26.04 does not ship `systemd-timesyncd` on this image. The package is
in the archive; it is not installed. **chrony is what ships, and it was
already synchronising** — the step failed while the condition it wanted was
already satisfied. It was also enabling a service in step 3 that step 4 had
not yet had the chance to install.

Step 3 now asks whether the clock is synchronised and installs chrony only if
nothing answers. On this host it installs nothing.

### 1c. The expensive one — the host lost every administrative path

Step 2b completed. Then:

    app user logs in            YES
    app user can sudo           NO   - no password, and it was never given one
    root can ssh                NO   - step 2b, working as designed

`adduser --disabled-password` leaves the account with no password.
`%sudo ALL=(ALL:ALL) ALL` demands one. `/etc/sudoers.d` was empty. So
`usermod -aG sudo` bought **nothing**: group membership without a password
and without a NOPASSWD drop-in is decoration.

**This is the same mistake step 1 exists to prevent.** The script's header
explains at length why port 22 is allowed *before* `ufw enable`, because the
other order locks you out of a remote host. Nobody applied that reasoning to
the second door.

And the warning that was already there did not help:

> VERIFY A SECOND SSH SESSION AS `<user>` BEFORE CLOSING THE ONE YOU ARE IN

A second session as the app user **succeeds**. Logging in was never the part
that breaks. The note describes the wrong failure, so following it exactly
would have produced the same lockout with more confidence.

---

## 2. THE FIX

New **step 2a**, between the user and the hardening:

- writes `/etc/sudoers.d/90-<user>` granting NOPASSWD, mode 0440
- validates it with `visudo -c` — a sudoers file with a syntax error is
  itself a lockout, because sudo then refuses to run at all rather than
  ignoring the bad file

**Step 2b now refuses.** It will not touch `sshd_config` unless
`sudo -n true` is demonstrated to work, as the app user, non-interactively,
in the shell that is about to lose root. A refusal and not a note, because
the note was already there and the lockout happened anyway.

**NOPASSWD rather than a password**, deliberately: the host is key-only by
the next line of the same step, so a sudo password would be a second secret
to store, rotate and lose, protecting a shell that the ssh key already
grants. It is also what cloud-init already does for the default user on this
image.

---

## 3. THE TESTS, AND THE ONE THAT COULD NOT FAIL

`tests/test_provision_survives_its_own_firewall.py`, 10 tests.

They read **the plan the script emits under `--check`**, not its source text.
That distinction earned itself during this increment: the first version of
the time-sync test read the source, and the source still defines `$TIMECHECK`
even when the line that *runs* it has been changed back to the broken
`systemctl enable`. **It passed against the restored bug.** A second version
using `re.S` made `(.*)` swallow the entire file as one match and passed
against everything.

Five mutations are verified to fail the suite, each for its own reason:

    A  yes | ufw enable restored              2 failures
    B  systemd-timesyncd enable restored      1 failure, 1 error
    C  the sudoers drop-in not written        1 failure
    D  the 2b refusal gate removed            1 failure
    E  the visudo validation removed          1 failure

C is in the list because it passed the first time it was tried: the test was
matching the path `/etc/sudoers.d/90-` anywhere in the plan, and
`visudo -c -f /etc/sudoers.d/90-<user>` names the same file while being a
*check* of a drop-in rather than the writing of one. It now matches the
write.

---

## 4. WHAT THE OPERATOR HAS TO DO

Two options. The script is idempotent either way, and **re-running the
corrected script completes steps 3-8 and fixes sudo on the way through.**

**(a) Restore access, then re-run — about two minutes.**
Hetzner Cloud console → the server → *Reset root password*, then the web
console, then:

    echo 'resonate ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/90-resonate
    chmod 0440 /etc/sudoers.d/90-resonate
    visudo -c -f /etc/sudoers.d/90-resonate

Root ssh stays off, which is where it should be. Then say so here and the
corrected script finishes the job.

**(b) Rebuild the image and run the corrected script once, clean.**
The host holds nothing — no repo, no secrets, no data — so this costs only
the rebuild. It buys a production box whose entire provenance is one run of
one reviewed script, rather than one that was half-provisioned by a version
with three known aborts in it.

**(b) is the recommendation** if the cutover is not tonight. (a) is right if
it is.

---

## 5. WHAT IS STILL OPEN, AND NOT THIS BRANCH'S

- **`46474c6c` is still not on master.** The night handoff's §0 said to adopt
  it before the reboot drill, and the merge of master into infra at
  `a4924f7c` confirms production has not. Without it `cold_start --verify`
  looks for heartbeats where no monitor writes them, polls ten minutes and
  reports a recovery time that means nothing.
- **`BACKUP_TARGET` and `PUBLIC_HOSTNAME` are empty** in
  `hosts/production.env`. They block 2e (off-host backup — and the 6b
  encryption decision is still unanswered too) and 2f (Caddy needs a real DNS
  name for TLS-ALPN-01 on 443, since port 80 is closed by step 1).
- `hosts/production.env` carries **`HOST_IPV4`, `HOST_IPV6` and `HOST_PLAN`
  twice**, empty first and filled second. `source` takes the last, so
  everything here read the right values — but a parser that takes the first,
  or that treats an empty value as set, reads no address at all. Worth
  deduplicating by hand; nothing in the repository reads this file, so
  nothing can do it for you.

---

## 6. STANDING RULES

Branch only; nothing on master. No `config/.env`, no `work/`, no
`src/providers/*`. No live writes — nothing on the host was started, no
service enabled that sends, no data transferred. No timeout wrappers. Host
values came only from the gitignored `hosts/production.env`.

**One exception to report rather than bury: a host IPv4 was printed to the
session transcript.** A redaction filter written for exactly this purpose had
a defect and passed one value through before it was caught and rebuilt. The
value is the host's public address, not a credential, and no secret was
exposed — but the rule was "never print them" and it was broken once. It is
in this session's transcript under `~/.claude/projects/`. Flagged so the
decision about it is the operator's.
