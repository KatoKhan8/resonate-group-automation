# Server migration plan — Windows workstation to a Linux host

**FOR REVIEW. Nothing here has been executed and no host has been
provisioned.** Written on branch `infra` 2026-09-22.

## OPERATOR DECISION — Zvonimir, 2026-09-22

> *Hetzner EU accepted in principle; the governance items stay listed as
> tasks, not promises, until built. I will review both docs tomorrow; no build
> until then.*

**Accepted in principle is not accepted.** §7's restore drill still gates the
cutover, and nothing in §1 has been provisioned. The host choice is settled;
the move is not.

**The governance items in §9 stay TASKS.** Retention, erasure-on-request and
suppression minimisation are listed in §10 as unimplemented and they remain
so. Until they are built:

- **A DPA may not promise an erasure timescale.** §9's DPA checklist item 8
  already says this and it is now an instruction rather than a caution.
- **Retention is aspirational.** The table in §9 describes what we intend to
  keep and for how long. There is no deletion path in the codebase and
  `store` refuses to delete a record by design, so nothing enforces it today.
  Anybody quoting that table to a client is quoting a plan.

Do not let the distinction erode. A governance section that reads as
description rather than intent is exactly how a commitment gets made in a
sales call that the code cannot honour.

Read `DEPLOYMENT-PLAN.md` first. This does not replace it — it takes the
branch that document already blesses (*"A single VM. Also fine, and cheaper.
systemd units … More operational work, fewer moving parts"*) and makes it
concrete, then adds the two things it does not cover: a cutover that keeps the
Windows machine as fallback, and data governance.

**Where this plan and `DEPLOYMENT-PLAN.md` disagree, that document wins** on
architecture and this one wins on operations. There is one deliberate
divergence, in §2.

---

## 0. WHAT THIS DOES NOT CHANGE, AND THE ONE GATE THAT SURVIVES THE MOVE

**One replica. Exactly one.** State is JSONL under an advisory file lock,
single-writer by construction. `DEPLOYMENT-PLAN.md` §2c calls two writers on
one volume a correctness gate rather than a tuning concern, and that is as
true on Linux as on Windows. A new host does not buy horizontal scale; it buys
uptime, backups and a reverse proxy.

**`QUEUE` is `PRODUCTION_ONLY` in `src/config.py`** — production refuses to
start without it. Keep that refusal. A container or a fresh VM with `QUEUE`
unset lands the estate somewhere that is deleted on the next deploy, silently,
because an empty store is a *valid* store and nothing downstream can tell a
fresh workspace from one whose records were thrown away.

**Do not provision Postgres and do not set `DATABASE_URL`.** There is still no
SQL backend in this build. An empty instance beside the real state changes
only the bill.

---

## 1. Host

**Hetzner, EU region, a dedicated small VM.** Recommended over Railway for
this workload, and the reason is the state model rather than price:

- The estate is a **mounted filesystem under a lock**. Hetzner gives a real
  disk with a real filesystem and a snapshot API. Railway's volumes are
  attached to a service whose lifecycle the platform controls, and this app
  cannot tolerate two instances briefly overlapping during a redeploy — that
  is the single-writer gate above.
- Eight long-lived monitor loops are **not** request/response workloads.
  systemd supervises those natively; a PaaS models them as extra services and
  bills accordingly.
- **EU region is a governance requirement, not a preference.** §9.

Railway remains viable for the web app alone if the monitors stay elsewhere,
but that splits the state directory across two hosts, and the state directory
cannot be split. **Do not do that.**

    CPX21 or similar   3 vCPU / 4 GB / 80 GB NVMe, Falkenstein or Nuremberg
    Debian 12 or Ubuntu 24.04 LTS
    One non-root user `resonate`, no password login, SSH key only
    ufw: 22 (key only), 80, 443. Nothing else.

**Size check before committing**: the queue is 19.41 MB at 1,027 records, mean
19,819 bytes. At the 20k target the JSONL store alone is ~400 MB, the SQLite
store is comparable, and backups multiply it. 80 GB is ample; 20 GB is not,
once retained backups are counted.

---

## 2. Services — and the divergence from DEPLOYMENT-PLAN.md

That document lists `web`, `worker`, `scheduler`. **Today there is no worker
and no scheduler** — it says so itself, in its own table. What actually runs
is the web app plus eight independent monitor loops, from the 2026-09-22
handoff:

    bison_mailbox_utilisation      --interval 300
    reply_watch_loop               --interval 300
    notify_deliver_loop            --interval 60
    bison_watch_loop --campaign 487 --interval 180
    bison_watch_loop --campaign 489 --interval 180
    heyreach_watch_loop            --interval 300
    digest_loop                    --interval 300
    slack_agent_loop

**Model what exists, not what the roadmap wants.** One unit per loop, plus
one for the web app. Consolidating them into a "scheduler" is a code change,
not a deployment step, and doing it during a host migration mixes two
failures.

### Unit template

```ini
# /etc/systemd/system/resonate-reply-watch.service
[Unit]
Description=Resonate reply watch loop
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=resonate
WorkingDirectory=/srv/resonate/app
EnvironmentFile=/etc/resonate/env          # §3
ExecStart=/srv/resonate/venv/bin/python -m scripts.reply_watch_loop --interval 300
Restart=always
RestartSec=30
# A loop that dies every 30s forever is a fault, not a retry. Give up and
# alert rather than hammering a provider that is refusing us.
StartLimitIntervalSec=600
StartLimitBurst=10
StandardOutput=append:/var/log/resonate/reply-watch.log
StandardError=append:/var/log/resonate/reply-watch.err
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/srv/resonate/work /var/log/resonate

[Install]
WantedBy=multi-user.target
```

    Restart=always      a watcher that is not running is a watcher that
                        reports nothing, and silence reads identically to
                        "no replies yet"
    RestartSec=30       not 1. A provider 429 answered by an instant restart
                        is a self-inflicted rate-limit
    StartLimitBurst     ten failures in ten minutes stops the unit and leaves
                        it stopped, loudly

**`ProtectSystem=strict` with an explicit `ReadWritePaths`** is what stops a
unit writing outside the state directory. It is the operating-system-level
version of `store.refuse_production_write`, and it is worth having both.

**Never run anything under `timeout`.** CLAUDE.md says so and systemd gives no
reason to: `Restart` and `StartLimit` are the supervision, and a `timeout`
wrapper turns a slow provider call into a killed loop that looks like a crash.

---

## 3. Secrets

`config/.env` becomes `/etc/resonate/env`, `root:resonate`, mode **0640**,
loaded by systemd `EnvironmentFile=`. It is never in the repo, never in a
container image, never in a backup that leaves the host (§5).

31 variables are declared in `config.VARIABLES`, which is the registry and the
only source of truth for their names. **Never guess one** — CLAUDE.md records
a session that invented four and concluded the system was unauthenticated when
it was not.

Verify after cutover with the tool that reads the registry and therefore
cannot invent a name:

    py -3 scripts/credential_health.py --verify

It keeps five states apart — `NOT_CONFIGURED`, `CONFIGURED_UNVERIFIED`,
`AUTHENTICATION_VERIFIED`, `AUTHENTICATION_FAILED`, `PROVIDER_UNAVAILABLE`.
**A set variable is not an authenticated one, and a transport failure is not a
bad key.** `REOON_KEY` and `DELIVERABLE_KEY` stay `CONFIGURED_UNVERIFIED` by
design because their only endpoints cost a credit; that is expected and is not
a failed cutover.

**Never print a credential value**, in a log, a shell history or a handoff.

---

## 4. State directory

    /srv/resonate/work/          QUEUE=/srv/resonate/work/queue.jsonl

Everything else follows automatically: **30 state overrides** all default to
the queue's directory — campaigns, jobs, workspaces, audit, senders,
notifications, the MX cache, the action ledger, the spend ledger, client
approval, the Slack agent's three, and `QUEUE_DB`.

**`QUEUE_DB` is new and it matters for backups.** The SQLite store landed on
branch `infra` this session. It is not live (`QUEUE_BACKEND` defaults to
`jsonl` and promotion is gated — `docs/STORE-SQLITE-DESIGN-2026-09-22.md`
§11), but once shadow mode runs, `work/queue.db`, `queue.db-wal` and
`queue.db-shm` are real state and must be in the backup set.

**Set no override but `QUEUE`.** Setting them individually is how one file
gets left pointing somewhere else; that hazard is written into
`store.STATE_OVERRIDES`'s own comment and it has bitten twice.

---

## 5. Backup, and the restore drill that makes it real

**A backup nobody has restored is a belief, not a backup.** This section is
mostly the drill.

### Nightly

    02:30 host time, systemd timer, not cron
    1. store.lock() equivalent: stop writes for the snapshot window by
       stopping the web unit and the loops (~20s), OR snapshot the
       filesystem. Prefer the filesystem snapshot: it is atomic and needs
       no downtime.
    2. tar + zstd of /srv/resonate/work/  -> /var/backups/resonate/
    3. age-encrypt to a key held OFF the host
    4. push to Hetzner Storage Box or S3-compatible object storage, EU region
    5. retain 7 daily, 4 weekly, 6 monthly

**`/etc/resonate/env` is NOT in that archive.** Secrets are restored from the
password manager, by hand, deliberately. A backup that carries the credentials
turns one stolen archive into full provider access.

### The restore drill — quarterly, and once before cutover

Restore is the only part of a backup that has a failure mode. Do it on a
scratch VM, never on the live host:

1. Provision a throwaway VM.
2. Restore the newest archive to `/srv/resonate/work/`.
3. Supply secrets by hand from the password manager.
4. `py -3 scripts/credential_health.py --verify` — expect the five states
   above.
5. `py -3 -m src.store stats` — record count, states, lanes.
6. **Compare against `docs/state/QUEUE-MANIFEST.json`.** That manifest is the
   sanitised fingerprint — counts, stages and a hashed estate fingerprint —
   and it exists in git precisely so a restore can be checked against
   something that is not itself in the backup.
7. Start the web unit. Load one client view. Confirm it renders.
8. **Destroy the VM.** Two hosts holding the same live estate is the
   single-writer gate broken by operator error rather than by code.
9. Record the date and the record count in `docs/`. A drill that leaves no
   artifact did not happen.

**If the drill fails, the cutover does not proceed.**

---

## 6. TLS, reverse proxy, logs

**Caddy**, because it does ACME with no cron and no certbot renewal to forget.

```
app.resonategroup.co {
    reverse_proxy 127.0.0.1:8000
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }
    log { output file /var/log/resonate/access.log }
}
```

`WEB_HOST=127.0.0.1` so the app is reachable **only** through the proxy.
Binding 0.0.0.0 on a public VM publishes it without TLS and without the
headers above.

`AUTH_REDIRECT_URL` must be updated to the new origin, or the OIDC round trip
fails at cutover. It is in `config.VARIABLES`; check it explicitly in §8.

### Log rotation

    /var/log/resonate/*.log {
        daily
        rotate 14
        compress
        delaycompress
        missingok
        notifempty
        copytruncate
    }

`copytruncate` because the loops hold their file handles open and
`Restart=always` should not be triggered by logrotate.

**Logs may contain prospect names and email addresses.** They are therefore
client data under §9: 14 days, on the host, never in the off-host archive
unless encrypted with the same key discipline.

---

## 7. Cutover — Windows stays the fallback for 48 hours

The Windows workstation is not decommissioned at cutover. It is kept
**running but idle**, able to take over within minutes, for 48 hours.

### T-7 days
- [ ] Provision the host, users, firewall, Caddy, DNS **not yet pointed**
- [ ] Deploy the app and units, `systemctl enable` but **not start**
- [ ] Restore drill (§5) on a scratch VM. **Blocking.**

### T-1 day
- [ ] `git push` everything from the Windows machine and **verify the remote**
      — `git rev-parse master origin/master` must agree. Anything uncommitted
      is lost.
- [ ] Freeze all three Claude sessions and the Qwen pool.
- [ ] Record the baseline: `python -m src.store stats`, provider truth,
      `docs/state/QUEUE-MANIFEST.json`.

### T-0, in a window with NO SENDS
Check the sending windows first — 487 is Mon-Fri 07:00-15:00Z, 489 is Mon-Fri
13:00-21:00Z, and the batch campaigns have their own. **A weekend is the
obvious slot.**

- [ ] Stop every monitor on Windows. Confirm zero python processes.
- [ ] Final `rsync` of `work/` to the host. This is the authoritative copy.
- [ ] Secrets into `/etc/resonate/env` by hand, 0640.
- [ ] `credential_health.py --verify` on the host. **All five states as
      expected or stop.**
- [ ] `python -m src.store stats` on the host — **must match** the T-1 baseline
      exactly. A differing record count means the rsync raced a write.
- [ ] Start the web unit only. Load a client view over TLS.
- [ ] Point DNS. Confirm the certificate.
- [ ] Start the monitors **one at a time**, confirming each writes a heartbeat
      before starting the next. Eight at once gives eight simultaneous
      provider reconnections and no way to tell which one is failing.
- [ ] Watch for one full poll interval of the slowest loop (300s).

### T+48h
- [ ] Zero 401/403 in any watcher log — no monitor on a dead key.
- [ ] One successful nightly backup **and** a restore drill against it.
- [ ] Provider truth re-derived on the host and matching.
- [ ] Only then: stop the Windows monitors permanently and archive the
      machine. **Do not wipe it for another week.**

### Rollback, at any point before T+48h
Stop the host units, point DNS back, restart the Windows monitors, rsync
`work/` back **in the reverse direction**. The window is short precisely so
that reverse rsync is small. After T+48h the host is authoritative and
rollback means a restore from backup instead.

---

## 8. What will break at cutover, named in advance

| Thing | Why | Fix |
| --- | --- | --- |
| `AUTH_REDIRECT_URL` | OIDC redirect is origin-bound | Update before DNS, and in the IdP |
| Absolute Windows paths | `C:\Users\Zvonimir\...` appears in at least `scripts/task191_funnel.py`'s `DEFAULT_QUEUE` | grep for `C:\\Users` across `scripts/` before cutover |
| Line endings | Repo has CRLF in the working tree on Windows | `core.autocrlf=input` on the host; the tests are whitespace-sensitive in places |
| `py -3` | Windows launcher, does not exist on Linux | Units call the venv python by absolute path |
| Case sensitivity | Windows is case-insensitive; a mis-cased import works there and fails here | Full suite on the host before DNS |
| Slack channel ids | Unchanged | None — they are ids, not names |

---

## 9. DATA GOVERNANCE

The state directory holds **300 real companies and 92 real contacts** today,
and it is not ours to publish. This section is the reason the host is in the
EU and the reason `work/` is gitignored.

### Retention, per record class

| Class | Where | Retention | Why |
| --- | --- | --- | --- |
| Prospect record — contacted | `queue.jsonl` | **24 months** from last contact | Legitimate-interest record of what was sent and why |
| Prospect record — never contacted | `queue.jsonl` | **6 months** from enrichment | Sourced but never used is the weakest basis; do not keep it |
| Verification evidence | inside the record | with the record | Paid, and deleting it re-buys it |
| Action ledger | `action-ledger.jsonl` | **24 months** | Proves what was sent to whom; the audit trail |
| Spend ledger | `spend-ledger.jsonl` | **7 years** | Financial |
| Reply content | record events | **24 months** | Same basis as the record |
| Suppression / DNC | `agency-dnc.jsonl` | **PERMANENT** | See below |
| Logs | `/var/log/resonate` | **14 days** | Operational only |
| Backups | object storage | 7d/4w/6m | Inherits the strictest class it contains |

Retention is **not implemented**. There is no deletion path in the codebase
and `store` refuses to delete a record by design. Implementing this is a
task, and it is listed in §10 rather than assumed.

### Permanent suppression, and why it is the exception

**A suppression record outlives every other class and is never deleted.**

Deleting someone's do-not-contact entry is how they get contacted again. The
suppression list is the one place where "we no longer hold your data" and "we
will not contact you" are in direct conflict, and the resolution is standard:
retain the **minimum** needed to honour the objection — a hashed identifier
and a date — and nothing else. Not the name, not the company, not the reason
in free text.

`CONTACT_STOPS` in `store.py` is enforced by `refuse_history_loss`, which
raises if a write would lift a stop nobody lifted. **That guard is the
technical expression of this policy** and it is why it has no opt-out in
`src/`.

### Per-client data ownership

- **The client owns their prospect data.** We are a processor for it.
- Tenancy is enforced in code: `list_records` has **no default client** —
  omitting it is a `TypeError`, an unknown slug raises, and `client=ALL` must
  be passed explicitly. That is the boundary, and it outranks convenience
  everywhere in CLAUDE.md's ordering.
- **Export on request**: `scripts/` has the client export cycle (TASK-244).
  Deletion on request does **not** exist yet — §10.
- **Our own derived data** — ICP verdicts, priority scores, angle
  classifications — is ours, but it is *about* their prospects and travels
  with the client on termination.
- **Shared LinkedIn seats are a governance edge**, not just an operational
  one: on a seat we share with the client, their actions are not in our
  ledger and ours are not in theirs. `seatledger` reports client usage as
  `UNKNOWN` rather than guessing, and that honesty is the correct posture for
  an audit too.

### What a client DPA must cover

1. **Roles**: client is controller, we are processor. Named.
2. **Subject matter and duration**: cold outreach on their behalf; duration of
   the engagement plus the retention above.
3. **Categories**: business contact data — name, work email, title, employer,
   public LinkedIn profile. **No special categories, ever.**
4. **Sub-processors, named, with a change-notice period**: ContactOut, Apify,
   Blitz, AI Ark, Reoon, Deliverable, EmailBison, HeyReach, Slack, and the LLM
   provider. **The LLM provider is the one clients ask about** — state
   explicitly whether prospect data is used for training. If the answer is not
   documented, do not sign until it is.
5. **Location**: EU processing and storage. Name any sub-processor that is
   not, with its transfer mechanism.
6. **Security**: SSH-key access, secrets off-repo, encrypted backups, one
   named operator, the tenancy boundary above.
7. **Breach notification**: to the client without undue delay, with a stated
   maximum.
8. **Subject rights**: how access, rectification, erasure and objection are
   handled, and in what time. **Erasure is not implemented — do not promise a
   timescale the code cannot meet.**
9. **Deletion or return on termination**, with the suppression-list carve-out
   spelled out: we retain a minimal hashed suppression entry permanently, and
   we say so rather than discovering it during an audit.
10. **Audit rights**, proportionate.

---

## 10. What this plan does NOT authorise, and the gaps it exposes

- **It does not authorise the move.** Operator decision, and §7's drill gates
  it.
- **It does not implement retention.** No deletion path exists. **Task.**
- **It does not implement erasure-on-request.** **Task.**
- **It does not implement suppression-record minimisation.** Today a
  suppression carries more than a hash and a date. **Task.**
- **It does not consolidate the loops** into a scheduler. Deliberate: a code
  change during a host migration mixes two failures.
- **It does not change the single-writer gate.** One replica, still.
- **It does not resolve the LLM sub-processor training question** in §9.4.
  That is a contract question and it blocks a DPA, not a deploy.

Suggested task order once approved: retention → erasure → suppression
minimisation → loop consolidation. The first three are governance debt the
DPA will surface; the fourth is convenience.
