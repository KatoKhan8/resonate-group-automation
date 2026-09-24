# 2g — the cutover runbook

Branch `infra`, 2026-09-24. Written against 2b–2f as built. **The operator
chooses the evening.** Nothing in here runs itself.

Read `docs/THE-QUIET-WINDOW-IS-THREE-TIMEZONES-2026-09-23.md` first; §1
below is its conclusion, not a restatement of its reasoning.

---

## 1. THE WINDOW, AND WHY IT MOVES TWICE

Campaigns 491–498 carry **cohort timezones, not UTC windows** — five
America/New_York, two Europe/London, one Europe/Zagreb. The union of their
sending hours therefore moves twice a year, in two different weeks:

    now, all DST on        07:00Z-21:00Z     quiet 21:00Z -> 07:00Z
    after EU falls back    08:00Z-21:00Z     quiet 21:00Z -> 08:00Z
    after US falls back    08:00Z-22:00Z     quiet 22:00Z -> 08:00Z

**Cut over inside the quiet band, and prefer the first two hours of it**, so
there is room to roll back before the next window opens.

**02:00Z is inside the band in all three configurations, so the scheduled
reboot time does not move.** What moves is the margin against nightly
sourcing, which is pinned at 02:00 Europe/Zagreb — 00:00Z in CEST, 01:00Z in
CET. **The gap halves from two hours to one on the last Sunday in October.**
Named here because it is a running production job, not a setting.

---

## 2. BEFORE THE EVENING

    [ ] The tag exists and is pushed.        git tag -l; git push --tags
    [ ] The suite baseline is current.       docs/state/SUITE-BASELINE-*-MERGED.json
    [ ] BACKUP_TARGET filled, or 2e's ship step is knowingly skipped.
    [ ] PUBLIC_HOSTNAME filled, and DNS already resolves to the host.
        DNS propagation is not a cutover-night activity: TLS-ALPN issuance
        needs the name pointing at the host BEFORE Caddy starts.
    [ ] secrets.env filled.                  docs/SECRETS-MOVE.md
        py -3 scripts/server/secrets_checklist.py --verify-names
        py -3 scripts/credential_health.py --verify
    [ ] Item 3's shadow deploy has been done, and readiness reported.

**A set variable is not an authenticated one.** The two commands above answer
different questions and both are needed.

---

## 3. THE EVENING, IN ORDER

Every step names how you know it worked. A step whose success you cannot
observe is a step you are assuming.

### 3a. Confirm the window is actually quiet

    py -3 -m scripts.supervise --status

Not the clock alone — **read the provider**. CLAUDE.md: recompute provider
truth before acting on any number. A campaign mid-send is a reason to stop.

### 3b. Stop the monitors on the old machine

    py -3 scripts/start_monitors.py --status     # what is running
    # stop them, and CONFIRM they are stopped, not merely asked to stop

**Nothing may be watching from two places.** Two supervisors on one estate is
the failure `singlewalker` exists to prevent, and it is worse across machines
because neither lock sees the other.

### 3c. Back up `work/`, and drill it

    py -3 scripts/server/backup.py --drill --into /var/backups/resonate

**`--drill`, not `--backup`.** A backup that has not been restored is a file
with a date in its name, and this is the last moment it is cheap to find out.

### 3d. Copy `work/` to the host

Once, with sends stopped. `deploy.sh` deliberately does not do this: state
does not travel with code.

### 3e. Deploy the tag

    bash scripts/server/deploy.sh --check --tag <TAG>     # first, always
    bash scripts/server/deploy.sh --tag <TAG> --no-start

`--no-start` even now: install, look, then start. The rollback is
`deploy.sh --rollback`.

### 3f. Verify before starting anything

    py -3 scripts/cold_start.py --verify
    cat build/systemd/MONITOR-TABLE.txt

**Read the monitor table against what you expect.** This is the check that
would have caught 496, 497 and 498 being unwatched. Today it should list 20
monitors — the 15 production hand-wrote, plus 493 and the four `draft`
campaigns. If it lists fewer, stop.

### 3g. Start

    sudo systemctl enable --now resonate-supervisor
    systemctl status resonate-supervisor
    py -3 scripts/cold_start.py --verify

**`is-active` is not an estate that is up.** It answers about the supervisor
process; `cold_start --verify` answers about the monitors' heartbeats, which
is the question you actually have.

### 3h. The webhook

    # NOT /healthz - only /webhook* is proxied, by design, so /healthz
    # returns 403 from outside and is reachable on loopback only. Corrected
    # 2026-09-24 after the shadow deploy returned 403 here.
    ssh <user>@<host> 'curl -sS http://127.0.0.1:8787/healthz'
    # then, from outside: a SIGNED test POST, and an oversized one

Both. The oversized one is the point: it must return a readable 413 naming
the limit, **not** a broken pipe. See 2f.

### 3i. The sessions

    sudo loginctl enable-linger resonate
    systemctl --user enable --now tmux-production tmux-agent tmux-infra

Verification is a **deliberate reboot, checked before logging in** — logging
in is what hides a missing `enable-linger`. 2h §6.

---

## 4. ROLLBACK

    bash scripts/server/deploy.sh --rollback

Exercised in `tests/test_the_deploy_can_be_rolled_back.py`, not merely
written. It returns the checkout to the previously deployed tag and restarts
the unit.

**What rollback does NOT undo:** `work/` copied to the host in 3d. If state
moved and you roll the code back, the state is still there — which is
usually right, and is the reason 3c's drill exists.

**Decide the abort condition before you start**, not at 23:40: if the estate
is not verified up by the time the quiet band has two hours left, roll back
and keep the old machine running. A cutover that overruns into a sending
window is the one failure with a client-visible cost.

---

## 5. THE MORNING AFTER

    [ ] cold_start --verify, again, cold
    [ ] every monitor has beaten since the restart
    [ ] the first sends of the day happened in their own windows
    [ ] the 02:00 reboot fired and the sessions came back with nobody logged in
    [ ] one line in #resonate-os

---

## 6. WHAT THIS RUNBOOK DOES AND DOES NOT CLAIM

**Updated 2026-09-24, after the shadow deploy.** 2b–2f have now been run
against the host, and running them found four defects that review and a green
suite had both missed — see `docs/SHADOW-DEPLOY-READINESS-2026-09-24.md` §1.
One of them, a Caddy directive that validated cleanly and meant something
else, is the kind this document cannot protect you from.

So the steps above are tested rather than imagined, with three exceptions
that are **not** yet evidence:

- **3d, copying `work/`.** Only `work/campaigns.jsonl` has been copied. The
  queue has never moved.
- **3g, starting the estate.** No monitor has ever run on this host.
- **3i, the tmux sessions.** Two of the three worktrees do not exist there
  yet and `Linger=no`.

Those three are the cutover's real content. Expect one of them to be wrong in
a way that names the wrong thing — that has now happened five times in this
package, and the two most expensive were a guard whose evidence was correct
and whose conclusion was not, and a config the validator approved.
