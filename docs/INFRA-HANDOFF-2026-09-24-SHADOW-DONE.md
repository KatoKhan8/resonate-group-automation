# Infra handoff — 2026-09-24, shadow deploy done, cutover Monday

Supersedes `docs/INFRA-HANDOFF-2026-09-24-SERVER-PACKAGE-BUILT.md` and
`docs/SHADOW-DEPLOY-READINESS-2026-09-24.md` (both still accurate; this one
is shorter and is the one to act from). Branch `infra`, worktree
`../resonate-infra`. Written for a session with no conversation context.

**Lane 3.** Cutover, then nothing until the estate has run one clean day.
Handoff thresholds are **600k** (write one, keep working) and **850k**
(write a fresh one, stop for `/clear`). Never mid-push or mid-incident.

---

## 0. THE TWO THINGS TO READ FIRST

**1. The estate has never run on this host.** The package is deployed and
the supervisor is installed and **stopped**. No monitor has ever started,
`work/queue.jsonl` is not there, nothing has sent. The webhook receiver and
Caddy *are* running, and neither can send anything.

**2. Three operator steps are open and two of them block the cutover** — §3.
The age key pair blocks the backup; the Storage Box password blocks the
off-host copy. Claude Code's login does not block, it only means the tmux
sessions open without it.

**3. `infra` IS EIGHT COMMITS BEHIND `master` AND THAT IS THE FIRST JOB.**
The lane-3 assist was merged into master at `236eeef7`, and master has moved
on since: the research pack, the copy lint, a slack-agent merge, and two
changes that bear directly on this handoff (§1a). **Merge master into infra
before the cutover**, so the tag deployed on Monday carries what production
is actually running. That merge has not been done and should not be done at
23:00 on the night.

---

## 1a. WHAT CHANGED AFTER THIS HANDOFF WAS FIRST WRITTEN

**`bison.resume` IS NO LONGER SEALED.** Production added `EMAIL_RESUME` to
`SUPPORTED` on 2026-09-24 (`e9adfc1e`), as the operator authorization the
verb's own entry asked for. 491 and 481 were resumed the same day through
`bison.resume_campaign` directly — verified, and not wrong, but bypassing
`perform`, which is why the ledger's last row before that was 09-18. So a
resume at cutover now **reaches the provider and leaves a row** instead of
refusing. `heyreach.resume` is still sealed and still has no route.

**A FIXTURE I WROTE CARRIED A REAL VENDOR DOMAIN** — the Storage Box
provider's, in the backup tests, with `6ff9cc94`. Master's hygiene guard went
red the moment it merged; production fixed it to a reserved `.example` domain
(`d08cd3e7`) and the same fix is now on infra. The domain is deliberately not
reproduced here: the guard scans `docs/` too, and writing it in prose to
explain the mistake would repeat it.

The account number was invented, so no credential left — but the lesson is
the checking, not the value. **My pre-push leak check compared against the
exact values in `hosts/production.env`**, and the vendor domain is a
substring of `BACKUP_TARGET` rather than equal to it, so the check passed
while the hygiene guard would have failed. Two different questions: "did a
secret leak" and "is every fixture on a reserved domain". Answering the
first does not answer the second, and the second is the one with a guard.

---

## 1. HOST STATE

    deployed tag     infra-shadow-2026.09.24e     (detached, tree clean)
    commit           9a000e4
    OS / Python      Ubuntu 26.04.1 LTS / 3.14.4
    age              1.2.1 installed
    Claude Code      NOT installed
    ssh keys         github_deploy.pub only

    work/campaigns.jsonl   26 rows — THE REGISTRY ONLY
    work/webhooks/         4 rows from the shadow tests
    work/queue.jsonl       ABSENT, deliberately. Moves at cutover, step 4.

**Local:** `infra` pushed, `origin/infra` agrees, tree clean. 101 tests, 100
passing, 1 skipped (the age round-trip, which needs `age` and runs on the
host rather than the laptop).

### What is installed and what is stopped

    resonate-supervisor.service   installed   DISABLED + INACTIVE   <- the estate
    resonate-webhook.service      installed   enabled + active      <- records only
    caddy                         installed   enabled + active      <- TLS, cert valid
    loginctl linger               NOT enabled                       <- 2h, at cutover
    ~/.config/systemd/user/       empty                             <- 2h, at cutover

The supervisor being **disabled** as well as inactive is deliberate: a
reboot before cutover must not start the estate. Verified by rebooting on
2026-09-24 and checking **without logging in**.

`suite-check` (48M staging copy from 09-23) is deleted.

**GitHub deploy key**, added 2026-09-24 so the host could clone: read-only,
**id `164308397`**. Its title names the host and is therefore not reproduced
here; the id identifies it without a host value. Private half generated on
the host, never left it. Revoke in Settings → Deploy keys if you want this
done differently.

---

## 2. CUTOVER — MONDAY 2026-09-28, FROM 23:00 EUROPE/ZAGREB

**23:00 Zagreb is 21:00Z**, and that is exactly when the quiet band opens.
Zagreb is CEST on this date; EU falls back 2026-10-25, US 2026-11-01, so all
three timezone cohorts are still on DST and the band is `21:00Z → 07:00Z`.

    21:00Z   23:00 Zagreb   the quiet band opens, cutover starts
    00:00Z   02:00 Zagreb   NIGHTLY SOURCING RUNS — be finished before this
    02:00Z   04:00 Zagreb   scheduled unattended reboot
    07:00Z   09:00 Zagreb   sending resumes

**The real deadline is 00:00Z, not 07:00Z.** Nightly sourcing is a running
production job and it should meet a settled estate, not a half-migrated one.
That gives three hours for ninety minutes of work.

**Decide the abort at 23:30Z, before you start, not at 23:40 on the night.**
If the estate is not verified up by 23:30Z: roll back, leave the old machine
running, and let sourcing run against it as normal. A cutover that overruns
into sourcing is worse than one that did not happen.

### The checklist

    T        step                                           how you know
    -------  ---------------------------------------------  ----------------------
    21:00Z   1. Confirm the window is actually quiet        provider read, not the
             py -3 -m scripts.supervise --status            clock. Mid-send = stop.

    21:10Z   2. Stop the monitors on the OLD machine        --status shows none.
             py -3 scripts/start_monitors.py --status       Confirm stopped, do not
                                                            assume asked = stopped.

    21:20Z   3. Back up work/ AND DRILL IT                  "DRILL PASSED ... every
             py -3 scripts/server/backup.py --drill \       file came back, byte
                 --into /var/backups/resonate               for byte."

    21:35Z   4. Copy work/ to the host, once, sends stopped ls work/ on the host
             (deploy.sh deliberately does not do this:      shows queue.jsonl
             state does not travel with code)

    21:50Z   5. Deploy the tag, still not starting          "SUPERVISOR is
             bash scripts/server/deploy.sh --check --tag X  installed and NOT
             bash scripts/server/deploy.sh --tag X \        started"
                 --no-start

    22:00Z   6. VERIFY BEFORE STARTING ANYTHING             the table lists the
             py -3 scripts/cold_start.py --verify \         monitors you expect.
                 --deadline 30                              READ IT, do not
             cat build/systemd/MONITOR-TABLE.txt            count to a number
                                                            written last week.

    22:15Z   7. Start the estate                            is-active, THEN
             sudo systemctl enable --now resonate-supervisor cold_start --verify
             py -3 scripts/cold_start.py --verify           showing two witnesses.

    22:35Z   8. The webhook, both cases                     signed -> 200,
             (signed POST, and an OVERSIZED one)            oversized -> readable
                                                            413. NOT a broken pipe.

    22:50Z   9. The tmux sessions                           three sessions exist
             sudo loginctl enable-linger <app user>
             systemctl --user enable --now \
                 tmux-production tmux-agent tmux-infra

    23:10Z   10. Deliberate reboot, verify BEFORE logging in  all three sessions
             sudo reboot                                      back, supervisor up,
                                                              webhook up

    23:30Z   ABORT DECISION POINT

    00:00Z   nightly sourcing runs against a settled estate
    02:00Z   the scheduled reboot happens on its own — watch it

**Step 6 is the one that earns its place.** Reading the monitor table against
what you expect is the check that would have caught 496, 497 and 498 going
unwatched.

It listed **20** on 2026-09-24 — production's 15, plus 493, plus the four
`draft` campaigns. **Do not treat 20 as the answer on Monday.** The table is
derived from the registry, 491 and 481 were resumed on the 24th, and the
whole point of deriving it is that the number moves without anyone editing a
list. Read the names against what you believe is live; a count that matches
for the wrong reasons is exactly what a derived table is meant to stop you
relying on. Fewer names than campaigns you know are sending is the signal to
stop.

**Step 7: `is-active` is not an estate that is up.** It answers about the
supervisor process. `cold_start --verify` answers about heartbeats, which is
the question you actually have.

### Rollback

    bash scripts/server/deploy.sh --rollback

Exercised against a throwaway repository, not merely written. It returns the
checkout to the previously deployed tag and restarts the unit.

**It does not undo step 4.** If `work/` moved and you roll the code back, the
state is still on the host — usually right, and the reason step 3 drills the
backup first.

---

## 3. THE THREE OPERATOR STEPS STILL OPEN

No values appear below. Every command reads what it needs from a file that
already holds it.

### 3a. The age key pair — ON YOUR LAPTOP. Blocks the backup.

The private half must never reach the host. `age-keygen -o` writes it to a
file and prints only the public half, so nothing secret reaches a terminal.

    winget install FiloSottile.age
    mkdir "%USERPROFILE%\.age"
    age-keygen -o "%USERPROFILE%\.age\resonate-backup.key"

It prints `Public key: age1...`. That is the **recipient**. Put it on the
host — it is not a secret:

    ssh <app user>@<host> 'sudo -n tee -a /etc/resonate/secrets.env' <<< \
        'BACKUP_AGE_RECIPIENT=age1...'

**Back the private key up somewhere that is neither the host nor only this
laptop** — a password manager entry, or printed. It is the only thing that
can ever open a backup; losing it makes every archive permanently unreadable.

**The consequence is deliberate: the host can encrypt and cannot decrypt, so
it cannot verify its own backups.** The drill on the host proves the tar
round-trips. Proving the *shipped, encrypted* archive opens requires the
identity, so run this once on the laptop after the first real backup:

    py -3 scripts/server/backup.py --verify-encrypted <file>.age \
        --identity "%USERPROFILE%\.age\resonate-backup.key" --state-dir work

A backup nobody has ever decrypted is not a backup.

### 3b. The Storage Box password — ON THE HOST, ONCE. Blocks the off-host copy.

**It never goes in `secrets.env`.** It is typed once, at an interactive
prompt, to install a key — and never again.

The host has no general-purpose ssh key yet (only the GitHub deploy key), so
make one. Naming it `id_ed25519` means `scp` finds it without any config:

    ssh-keygen -t ed25519 -N "" -C "resonate-backup" -f ~/.ssh/id_ed25519

Then, on the host, deriving the destination from the file that already holds
it so you never type or echo it:

    set -a; . /etc/resonate/secrets.env; set +a
    ssh-copy-id -s -p "${BACKUP_SSH_PORT:-23}" "${BACKUP_TARGET%%:*}"

`-s` because a Storage Box has no shell. **Type the password at the prompt
only** — never as a command argument, which puts it in shell history and in
`ps`, and never into a file.

**Hetzner's web UI can install the public key instead**, which avoids typing
the password on the host at all. Prefer that if it is available to you.

Verify without sending anything:

    set -a; . /etc/resonate/secrets.env; set +a
    ssh -p "${BACKUP_SSH_PORT:-23}" -o BatchMode=yes "${BACKUP_TARGET%%:*}" \
        'echo key-auth-works'

### 3c. Claude Code login — ON THE HOST. Does not block the cutover.

Not installed there yet. Install it as the **app user**, not root, then
authenticate interactively **once**; the credential lives in that user's
home and every tmux session picks it up.

    # as the app user, install per the current official instructions
    claude            # then complete the interactive login

**It is not a service credential.** It does not go in `secrets.env`, not in
a unit file, and not in git — `secrets.env` is for what the application needs
to run, and putting a personal login in the deploy path conflates the two.

Without it the three sessions still come up; they just have no Claude in
them. So do it whenever, including after the cutover.

---

## 4. WHAT THE SHADOW DEPLOY FOUND

Four defects, none visible to review or to a green suite. Full detail in
`docs/SHADOW-DEPLOY-READINESS-2026-09-24.md` §1; the short version, because
the pattern is the useful part:

- **`--check` could not survive a first deploy** — it died at the moment a
  dry run is most worth having. Every test started from a fixture that
  already had a checkout.
- **A fresh clone looked like a dirty tree.** `git clone --no-checkout`
  leaves an empty tree with a full index, so `git status` reported 1,800
  files deleted and the guard refused the first real deploy. The guard was
  right, its evidence was right, its conclusion was wrong.
- **The deploy dirtied its own tree and blocked the next one.**
- **`tls { alpn tls-alpn-01 }` is valid and means something else.** `alpn`
  sets the server's ALPN list, not the ACME challenge. `caddy validate` said
  "Valid configuration", the test asserting the string passed, and Caddy
  tried HTTP-01 against the closed port 80. The correct directive is
  `issuer acme { disable_http_challenge }`.

**Be accurate about the certificate:** it was obtained anyway, via
`tls-alpn-01` after two failed `http-01` attempts, because Caddy falls back
on its own. The fix removes two wasted validations from a Let's Encrypt
limit of five per hostname per hour. It did not obtain the certificate.

And one gap: **the receiver had no unit**, so it would not have survived a
reboot — Caddy proxying to a closed port, 502s nobody was watching for.

**The BrokenPipe finding is settled on the platform that has it.** Oversized
POST over TLS returns 413 and the sender reads the refusal; 196,616 of
196,616 announced bytes drained, nothing recorded.

---

## 5. FROZEN UNTIL OCTOBER

Operator directive, effective 2026-09-24 until 2026-10-01. Lane 3 is the
cutover and then **nothing until the estate has run one clean day on the
server**. These are not forgotten, they are parked:

    D8    the rate-limit table
    D9    cassette tests
    D10   the cost ledger
    E     status JSON
    F6
    git history dry run, and scripts/history_pii_scan.py
    gateway evaluations
    item 2's three os.environ call sites  — still never exercised

**DONE AND MERGED, not frozen** (lane-3 assist, 2026-09-24, `236eeef7`): the
provider-write ledger, the declared resume verbs, and one log file per bison
watcher. Two consequences for the cutover rather than for October:
`work/provider-writes.jsonl` is new and grows on every write, and the
watchers' logs are now `w-<monitor name>.out` instead of one shared
`w-bison_watch_loop.py.out` — so tail the campaign you care about.

Two more that are production's rather than this branch's, and are open
questions rather than tasks:

- **Five order-dependent suite failures**, all in
  `test_ownership_readback_staleness.AStaleReadbackRefuses`: they fail in a
  full run and pass standalone. `test_no_test_leaves_the_environment_changed`
  is green, so the carrier is not an environment variable and that guard does
  not cover the class.
- **The registry's status vocabulary** (`approved`/`draft`/
  `awaiting_approval`) matches neither `LIVE_STATUSES` nor
  `FINISHED_STATUSES`, so every campaign takes the `unknown status` safety
  branch and the interesting half of the derivation rule is never exercised
  by real data.

---

## 6. STANDING RULES

Branch only, never master. Never `config/.env`, `work/` or `src/providers/*`.
No live writes. No timeout wrappers — `cold_start --verify` has its own
`--deadline`, which is the tool's parameter and not a wrapper. Suites to a
file with name diffs. One merge request per increment, one line in
`#resonate-os`.

**Host values come only from the gitignored `hosts/production.env`, and are
never printed.** The redactor is `redact.py` in the session scratchpad with
`hssh.sh` beside it; **self-test it before the first host command, not after**
— the 2026-09-23 breach was a correct filter with the check in the wrong
place. It currently carries 13 rules and passes.

One trap worth keeping: `hosts/production.env` has **three duplicate
assignments** — `HOST_IPV4`, `HOST_IPV6`, `HOST_PLAN` — with the empty one
first and the real one last. Shell sourcing takes the last, so everything
works; **a first-wins parser reads the host address as empty**, which looks
exactly like "No route to host".
