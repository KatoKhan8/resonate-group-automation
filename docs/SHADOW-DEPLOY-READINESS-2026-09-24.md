# Shadow deploy — done, and what it found

Branch `infra`, 2026-09-24. Lane 3. The host is deployed at
`infra-shadow-2026.09.24e`, **the supervisor is installed and NOT started**,
and the webhook receiver is answering signed requests over TLS.

Cutover is tentatively **Monday 2026-09-28, after 23:00 Europe/Zagreb**.

---

## 0. READINESS, IN ONE TABLE

    app installed at a tag              YES   infra-shadow-2026.09.24e
    secrets in place                    PARTLY 5 of 6 names; see §3
    monitors NOT started                YES   disabled + inactive, after a reboot
    cold_start --verify readable        YES   20 monitors by name, 0 witnesses
    webhook answering a signed test     YES   200 over TLS, and after a reboot
    certificate                         YES   Let's Encrypt, expires 2026-12-23
    survives a reboot                   YES   verified by rebooting, §5

**Blocking the cutover: one operator action** (§3, the age key). Everything
else is either done or is a cutover-night step.

---

## 1. THE SHADOW DEPLOY FOUND FOUR DEFECTS, AND THAT WAS THE POINT

`provision.sh` was written, reviewed, and then found to have six defects the
moment it was run. The same held here. **None of these four was visible to
review or to a green test suite.**

### 1a. `--check` could not survive a first deploy

In check mode the clone is printed rather than executed, so the `cd` that
followed found nothing and the dry run died — **at the exact moment a dry run
is most worth having, before the first deploy of all.** Every existing test
started from a fixture that already had a checkout, so nothing covered it.

### 1b. A fresh clone looked like a dirty working tree

`git clone --no-checkout` leaves an empty working tree with a fully populated
index, so `git status --porcelain` reports **every file as deleted**. The
dirty-tree guard then refused the first real deploy, naming 1,800 files
nobody had touched, in a directory one second old.

The guard was right, its evidence was right, and its conclusion was wrong:
`git status` answers a question about index-versus-tree and I had read it as
a question about whether a person had edited something.

### 1c. `alpn tls-alpn-01` is valid, and does something else entirely

**The worst of the four.** The Caddyfile said `tls { alpn tls-alpn-01 }`.
`alpn` *is* a real `tls` subdirective — it sets the server's ALPN protocol
list — and has **nothing to do with ACME challenge selection**. So:

- `caddy validate` answered **"Valid configuration"**
- the test asserting `"tls-alpn-01" in output` **passed**
- Caddy tried **HTTP-01** against the port 80 that provisioning deliberately
  leaves closed, and failed with *"Timeout during connect (likely firewall
  problem)"* — precisely the failure the generator's own comment claimed to
  prevent

Valid syntax meaning something else is worse than a syntax error, because the
validator agrees with you and the test matches the string you meant rather
than the behaviour you needed. The directive that actually selects the
challenge is `issuer acme { disable_http_challenge }`.

**Be accurate about the certificate**: it *was* obtained — via `tls-alpn-01`,
after **two failed `http-01` attempts**, because Caddy falls back on its own.
The fix did not obtain the certificate. It removes two wasted validation
failures from a Let's Encrypt limit of five per hostname per hour, which at
cutover is the difference between a retry and a week's wait.

### 1d. The deploy dirtied the tree and blocked the next deploy

`generate_units.py` writes `build/systemd/` inside the checkout; `build/` was
neither tracked nor ignored, so the next deploy's dirty-tree guard refused.
**A deploy that blocks the one after it.** `build/` is now ignored.

### And one gap, not a defect: the receiver had no unit

It was started by hand to prove it answered — and **proving it answers is not
the same as it being there tomorrow.** With no unit, the first unattended
02:00 reboot would have left Caddy proxying to a closed port and every
webhook answered with a 502 nobody was watching for.
`resonate-webhook.service` now exists, separate from the supervisor on
purpose, and `--no-start` starts the receiver while leaving the estate down.

---

## 2. WHAT IS ON THE HOST

    deployed tag        infra-shadow-2026.09.24e   (detached, clean tree)
    suite-check         DELETED (48M staging copy from 09-23)
    work/campaigns.jsonl  26 rows — THE REGISTRY ONLY
    work/queue.jsonl    DELIBERATELY NOT COPIED
    units               resonate-supervisor  disabled + inactive
                        resonate-webhook     enabled + active
                        caddy                active, cert valid
    deploy key          GitHub read-only, id 164308397, revocable

**Only the campaign registry was copied**, because `cold_start --verify` and
the unit generator cannot say anything true without it. The queue — 300 real
companies, 92 real contacts — was not, and moving it is a cutover step with
sends stopped.

**The derived table on the host produced 20 monitors**, by name, matching
`test_the_derived_table_is_the_incident_gates_15` exactly: production's 15,
plus 493, plus the four `draft` campaigns.

---

## 3. WHAT STILL NEEDS YOU

### 3a. The age key pair — BLOCKING, and the only blocker

Run this **on your laptop**. It writes the private key to a file and prints
only the public half, so the private key never enters a transcript:

    winget install FiloSottile.age          # or: scoop install age
    mkdir %USERPROFILE%\.age
    age-keygen -o %USERPROFILE%\.age\resonate-backup.key

It prints `Public key: age1...`. That public half is the **recipient**:

    BACKUP_AGE_RECIPIENT=age1...            # into /etc/resonate/secrets.env

**Back the private key up somewhere that is not the host and not this
machine only** — a password manager entry or a printed copy. It is the only
thing that can ever open a backup, and losing it makes every archive
permanently unreadable.

**The consequence is deliberate and worth stating**: with the private key on
your laptop only, **the host can encrypt and cannot decrypt, so it cannot
verify its own backups.** The drill on the host proves the tar round-trips;
proving the *shipped, encrypted* archive can be opened requires:

    py -3 scripts/server/backup.py --verify-encrypted <file>.age \
        --identity %USERPROFILE%\.age\resonate-backup.key --state-dir work

Run that once after the first real backup, on your laptop. A backup nobody
has ever decrypted is not a backup.

### 3b. The Storage Box password — where and when

**It does not go in `secrets.env`, and it is not typed on the host more than
once.** You asked where; the honest answer is *ideally nowhere on the host*:

- **Preferred** — paste the host's ssh public key into the Storage Box via
  Hetzner's web UI. The password is never typed on the host at all.
- **Otherwise** — on the host, once:

      ssh-copy-id -s -p 23 <user>@<user>.your-storagebox.de

  `-s` because a Storage Box has no shell. Type it **at the interactive
  prompt only** — never as a command argument, which puts it in shell history
  and in `ps`, and never into a file. After that, authentication is by key
  and the password is never needed again.

### 3c. The GitHub deploy key

I added one so the host could clone: **read-only**, titled
`resonate-production-host (read-only, added 2026-09-24)`, id `164308397`.
The private half was generated on the host and never left it. Revoke it in
Settings → Deploy keys if you would rather do this differently.

---

## 4. NOT DONE, AND DELIBERATELY

- **2h tmux sessions.** Two of the three worktrees do not exist on the host,
  so the units are not installed and `Linger=no`. This is a cutover step, and
  its verification is a reboot checked **before logging in**.
- **The estate has never been started.** No monitor has run, nothing has
  sent, `work/queue.jsonl` is not there.
- **The runbook's `curl /healthz` check is wrong** and is corrected: only
  `/webhook*` is proxied, by design, so `/healthz` returns 403 from outside
  and is reachable on loopback only.

---

## 5. THE REBOOT TEST

Rebooted deliberately, during the shadow phase, with nothing running that
sends. Checked **without logging in interactively**:

    supervisor   disabled + inactive     (correct: the estate stays down)
    webhook      enabled + active        (survived)
    caddy        active, certificate intact
    signed POST over TLS -> 200
    oversized POST over TLS -> 413, refusal readable

---

## 6. THE BROKENPIPE FINDING, SETTLED ON THE PLATFORM THAT HAS IT

The four `AnOversizedUploadIsRefused` tests fail on Linux and pass on Windows
because the server closes before the client finishes sending, and the client
gets EPIPE instead of the refusal. 2f was written against that and its tests
said, honestly, that Windows could not prove it.

**On the host, measured:**

    oversized POST -> 413, and the sender READ the refusal
    drained 196,616 of 196,616 announced bytes, recorded none
    records written: 1 (the signed request), 0 (the oversized one)

Draining is not accepting: the body is read only so the answer is reachable,
and thrown away unparsed. It holds through Caddy, over TLS, after a reboot.

---

## 7. A CORRECTION

Two commit messages in this session state test counts that are wrong. The
2g/2h commit says 117 and the webhook-unit commit says 91; the true figures
are **91 and 101** respectively. Corrected here rather than by rewriting
pushed commits. The current suite total is **101 tests, 100 passing, 1
skipped** — the skip is the age round-trip, which needs `age` installed and
runs on the host rather than this laptop.
