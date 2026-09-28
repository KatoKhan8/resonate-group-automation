# CREDENTIAL EXPOSURE INVENTORY — 2026-09-28

**Operator decision 12, Zvonimir, 2026-09-28.** Every credential that appeared
in Slack, a `work/` artifact or a shared chat, listed **by variable NAME and
never by value**, each marked **ROTATED (with evidence)** or **ROTATION
REQUIRED**.

**NO CUTOVER AND NO LIVE SEND WHILE ANY LINE BELOW SAYS ROTATION REQUIRED.**

The operator rotates and says "rotated X". Claude then verifies **by
authentication only** — never by the variable being set, never by a value
comparison, never by the operator's say-so:
`py -3 scripts/credential_health.py --verify`, which reads the registry and so
cannot invent a name, and which keeps `NOT_CONFIGURED` /
`CONFIGURED_UNVERIFIED` / `AUTHENTICATION_VERIFIED` / `AUTHENTICATION_FAILED` /
`PROVIDER_UNAVAILABLE` apart. **`AUTHENTICATION_VERIFIED` is the only value
that closes a line.** A set variable is not an authenticated one, and a
transport failure is not a bad key.

---

## 1. TWO INDEPENDENT SOURCES, AND ONE OF THEM IS INVISIBLE TO ANY SCAN

    A.  the stored history of #resonate-leadership   found by scanning
    B.  a shared chat link, now being deleted        OPERATOR'S EVIDENCE ONLY

**Source B cannot be scanned from here and its entries rest entirely on the
operator's report.** They are recorded as ROTATION REQUIRED on that basis,
which is the correct authority for them: the operator saw the link, and no
tool here can.

## 2. CORRECTION TO THIS DOCUMENT'S FIRST VERSION — THE SCAN WAS NARROWER THAN IT SAID

The first version searched every credential-shaped name in
`config.VARIABLES` and reported the rest as "no evidence of exposure". **That
enumeration was incomplete, and the gap is structural rather than accidental.**

`config.VARIABLES` is the APPLICATION's registry. Live credentials exist
outside it, by design — `scripts/server/secrets_checklist.py` says so in its
own words: *"These are NOT in `config.VARIABLES` and should not be: that
registry is the application's, and nothing in `src/` reads any of these."*

So the first scan never searched for these, and two of them were exposed all
along:

    XAI_API_KEY        read by src/providers/xai.py       EXPOSED in Slack
    ZAI_API_KEY        read by src/providers/glm.py       EXPOSED in Slack
    SLACK_APP_TOKEN    read by src/socketmode.py          not found by scan

**`XAI_API_KEY` and `ZAI_API_KEY` sit in the clear in the same
`#resonate-leadership` history as the other six.** They were missed because of
where the scan looked, not because of where they were.

**The lesson is the one already recorded in section 8: a filter must be
self-tested against every value it is supposed to catch.** This one was
self-tested against every value *in a registry that was not the whole set*,
which is the same defect one level up. Any future exposure scan enumerates
`config.VARIABLES` **plus** `secrets_checklist.INFRA_VARIABLES` **plus** the
off-registry names above.

## 3. EXPOSED IN SLACK — ROTATION REQUIRED

All eight found **in the clear** in the stored history of
**`#resonate-leadership`** (channel `C0AF9URBYSK`).

    AIARK_KEY              ROTATION REQUIRED
    APIFY_TOKEN            ROTATION REQUIRED
    BISON_KEY              ROTATION REQUIRED
    DELIVERABLE_KEY        ROTATION REQUIRED
    HEYREACH_KEY           ROTATION REQUIRED
    REOON_KEY              ROTATION REQUIRED
    XAI_API_KEY            ROTATION REQUIRED   (found in the correction above)
    ZAI_API_KEY            ROTATION REQUIRED   (found in the correction above)

**The channel is PRIVATE and NOT externally shared** — confirmed by
`conversations.info`: `is_private: true`, `is_shared: false`,
`is_ext_shared: false`. **So this is not a client-facing disclosure.** It is
still exposure: Slack retains and indexes the message, every member can read
it, and any app or admin with history scope can export it.

Three messages, all from the same human account, none from a bot:

    2026-07-30T20:04Z   REOON_KEY, AIARK_KEY, HEYREACH_KEY
    2026-08-25T18:29Z   REOON_KEY, AIARK_KEY, HEYREACH_KEY,
                        APIFY_TOKEN, DELIVERABLE_KEY
    2026-09-09T15:19Z   BISON_KEY

`CONTACTOUT_TOKEN` — **ROTATION REQUIRED** on different evidence: our stored
copy shows a redaction marker where it stood, which is positive evidence that
a token was posted there. The value was deliberately not retrieved to
establish that.

A **`deliverable.co` account login** — username and password, the password
likewise already redacted in our stored copy. **ROTATION REQUIRED, by hand.**
It is an account password, not an API variable, so it has no entry in any
registry and **no automated check will ever catch it.**

**At least one SUPERSEDED EmailBison key** is in the two older messages — it is
not the current `BISON_KEY`, so the key changed between 2026-08-25 and
2026-09-09. Whether that was a deliberate rotation or an unrelated reissue is
**UNKNOWN**, and an old key never revoked at the provider is still a live key.
**Confirm at EmailBison that every key but the current one is revoked** —
rotating the current one does not do that.

## 4. EXPOSED IN A SHARED CHAT LINK — ROTATION REQUIRED

Operator's report, 2026-09-28. The link is being deleted. **Deletion is not
rotation**: a link that was live must be assumed fetched.

    SLACK_BOT_TOKEN        ROTATION REQUIRED
    SLACK_APP_TOKEN        ROTATION REQUIRED
    OPENROUTER_API_KEY     ROTATION REQUIRED  ← and LLM_API_KEY, see below
    LLM_API_KEY            ROTATION REQUIRED  ← same value, second spelling
    XAI_API_KEY            ROTATION REQUIRED  (also section 3)
    ZAI_API_KEY            ROTATION REQUIRED  (also section 3)
    BLITZ_API_KEY          ROTATION REQUIRED
    the backup age PRIVATE key      ROTATION REQUIRED — section 6
    the Storage Box password        ROTATION REQUIRED — section 7

**⚠ `OPENROUTER_API_KEY` AND `LLM_API_KEY` CURRENTLY HOLD THE SAME VALUE.**
Measured, not assumed. `LLM_API_KEY` is the legacy spelling for OpenRouter and
is **still read** as a fallback by `providers.model_key('openrouter')`.
**Rotating one name and not the other leaves the compromised key live under
the other spelling** — and generation would keep working, so nothing would
look wrong. Update BOTH, or set the new key on `OPENROUTER_API_KEY` and unset
`LLM_API_KEY` entirely.

## 5. THE TWO THAT MATTER MOST, AND WHY THEY ARE DIFFERENT IN KIND

The provider keys buy an attacker someone else's API quota. **The age private
key and the Storage Box password together buy the estate itself.**

    the Storage Box password   → fetch the archives
    the age PRIVATE key        → decrypt them

Each alone is limited. **Together they are read access to everything
`scripts/server/backup.py` has ever shipped, which is `work/` — in CLAUDE.md's
own words, "300 real companies and 92 real contacts and it is not ours to
publish".** If both were in that link, treat them as one incident, not two
lines on a list.

### ~~UNKNOWN~~ → MEASURED, 2026-09-28: THE ARCHIVES EXIST

**This section said the archive question was UNKNOWN from this laptop, and
correctly refused to read the laptop's unset `BACKUP_*` variables as an
authority on the host. The canonical authority has now been read.** The infra
session listed the Storage Box destination itself over SFTP, from the host.

    2 x prodwork   89.7 MB and 93.2 MB   the FULL production work/ tree,
                                         438+ files, ~517 MB uncompressed,
                                         shipped 2026-09-25 and 2026-09-27
    6 x state      13.5 KB each          the registry, 09-25 to 09-27

**This is the second outcome — the expensive one. Section 6's rotation DOES
NOT PROTECT THESE.**

**Provenance, recorded because it is not inferable and it changes the
timeline.** The infra session set `BACKUP_AGE_RECIPIENT` on the host on
2026-09-25 from a recipient the operator supplied directly in-session, ran the
first encrypted backup, and scheduled a nightly at 20:30Z which then ran five
times. **So these archives exist because of infra work done AFTER this
document's original evidence, not before it.** All eight are encrypted to the
SAME recipient: `/etc/resonate/secrets.env` has not been modified since
2026-09-25T16:41:15Z, measured from the file's mtime, so the recipient cannot
have changed under them.

**THE SEVERITY IS CONDITIONAL AND THE CONDITION IS NOT KNOWN.** If the exposed
age PRIVATE key is the private half of that recipient, then all eight archives
are readable by anyone holding it **plus** the Storage Box password — and both
are in section 4. **Whether the two key pairs are the same is UNKNOWN and only
the operator can confirm it.** Neither session has asked, and neither should
infer it. Until it is confirmed, this is UNKNOWN, and UNKNOWN is not safe.

**What the archives are NOT:** they are not the only home of production state.
Measured 2026-09-28 from `store.load()`: the live `work/` tree is present and
readable with 1,582 records. **So deleting these archives would cost restore
points, not live data.**

**Two actions were taken, both by the infra session, both recorded here:**
1. **The nightly cron is PAUSED** — commented with a dated marker, script and
   gate untouched, one edit to resume. It was still armed and would have
   shipped another ~90 MB of client data at 20:30Z to a destination whose
   password is in section 4. Trivially reversible, and the safe default while
   this is open.
2. **No archive was deleted or moved.** Section 6 says that is a separate
   decision this document does not assume, **and it needs the operator's
   explicit APPROVED.** It remains unasked while the operator has the
   credential incident parked.

**The host holds no plaintext for 09-25 and 09-27** — the nightly deleted its
plain copies after shipping, gated on an operator-confirmed decrypt.
Production's own originals are unaffected, per the live-store measurement
above.

## 6. ROTATING THE BACKUP age KEY — EXACT STEPS

Grounded in `scripts/server/backup.py` as it is written, not a generic
procedure. The design: the **PUBLIC** key (`age1...`) lives on the host in
`BACKUP_AGE_RECIPIENT`; the **PRIVATE** key is generated on the operator's
laptop and never reaches the host. `ship()` refuses a recipient that does not
start with `age1`, so a private key cannot be put in that field by accident.
The host can encrypt and **cannot decrypt** — deliberately.

**1. Generate the new key pair ON THE LAPTOP. It never leaves.**

    age-keygen -o ~/.config/age/resonate-2026-09-28.key

That file contains the new PRIVATE key and prints the new PUBLIC recipient
(`age1...`). Back it up the way you back up a password, not into this repo:
`.env`, `secrets.env` and anything under `work/` are all wrong homes for it.

**2. KEEP THE OLD PRIVATE KEY. OFFLINE. DO NOT DELETE IT.**
Every archive already shipped is encrypted to the OLD public key and **can
only ever be opened with the OLD private key.** Deleting it destroys every
existing backup as surely as deleting the archives. Move it to offline media,
label it with the date range it covers, and keep it.

**3. Put ONLY the new PUBLIC key on the host**, in
`/etc/resonate/secrets.env`:

    BACKUP_AGE_RECIPIENT=age1<the new public half>

Nothing else changes. `BACKUP_TARGET`, `BACKUP_ENCRYPTION=age` and
`BACKUP_SSH_PORT` stay as they are.

**4. Take the next backup normally.** It encrypts to the new recipient. No
re-encryption of old archives happens, and none is attempted — `ship()`
encrypts the archive it is given and nothing else.

**5. PROVE the new key opens the new archive, on the laptop**, because the
host structurally cannot:

    py -3 scripts/server/backup.py --verify-encrypted <archive>.age \
        --identity ~/.config/age/resonate-2026-09-28.key

It decrypts, restores, and compares against the live tree **by name and by
hash**. `ENCRYPTED VERIFY PASSED` is the evidence. **Until that has run once
against the new key, the rotation is IMPLEMENTED and not LIVE_VALIDATED** —
an untested new recipient means the next restore is the first test, at the
worst possible moment.

**⚠ WHAT THIS PROCEDURE DOES NOT DO, AND IT IS THE GAP THAT MATTERS.**
Rotation protects **future** archives only. Archives already on the Storage
Box stay encrypted to the OLD public key, and whoever saw the old private key
can still open every one of them. **If section 5 finds archives there, rotation
is not enough** — each must be either deleted, or downloaded, decrypted with
the old identity, re-encrypted to the new recipient and re-uploaded, with the
old copies then removed. That is a separate decision and this document does not
assume it.

## 7. ROTATING THE STORAGE BOX PASSWORD — EXACT STEPS

**The reassuring part first, because it changes the urgency: rotating this
password does not break backups.** `secrets_checklist.py` records why in its
own words — the password *"is typed once, into an interactive prompt, to
install the host's ssh public key on the Storage Box — and never again.
Authentication afterwards is by key."* `ship()` uses
`scp -o BatchMode=yes`, which cannot even prompt for a password. **So the
running backup path never uses it.**

**1. Change it in the Hetzner Robot / Storage Box panel.** It is not in
`secrets.env`, not in git, and not in any file this repo reads — deliberately,
and `NEVER_IN_SECRETS` names it. **So there is no `secrets.env` edit for this
one**, and adding it there would undo the design.

**2. Confirm the host's SSH key still authenticates** — this is the whole
verification, and it is an authentication check rather than an inspection:

    ssh -p 23 -o BatchMode=yes <user>@<host> ls

`BatchMode=yes` means it cannot fall back to a password prompt, so a success
proves key authentication specifically. A "Permission denied" here means the
host's public key is no longer installed and must be re-installed with the
NEW password, once.

**3. Review who else could still reach the box.** A password rotation does not
revoke SSH keys. List the installed keys and remove any that are not this
host's.

**4. Then decide about existing archives**, per section 6's warning. The
password change closes the fetch route; it does nothing about copies already
fetched.

## 8. A SECOND DEFECT THIS SURFACED — THE INGEST REDACTOR IS INCOMPLETE

The stored history redacted a **ContactOut token** and a **password** and
missed **seven other live keys in the same channel**. A redactor that catches
two shapes and passes seven is worse than none, because its output looks
redacted.

It must be **self-tested against every value it is supposed to catch, before
the first write rather than after**, and driven from the union of registries
in section 2 rather than a hand-maintained pattern list. Recorded as work, not
fixed in this change.

## 9. NO EVIDENCE OF EXPOSURE

`SLACK_SIGNING_SECRET`, `AUTH_CLIENT_SECRET`, `SESSION_SECRET`,
`GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `WEBHOOK_SIGNING_SECRET`.

Read that as section 2 now requires: **their current values were not found in
the clear anywhere scanned, and the scan's reach is what section 2 says it
is.** It is not a statement about their history, and a name absent from the
exposed lists is UNKNOWN rather than clean. Where certainty is wanted, the
answer is a rotation, not a re-run of the scan.

## 10. THE ORDER, AND WHO DOES WHAT

1. **On the host: establish whether any archive was ever shipped** (section 5).
   That answer decides how much section 6 actually has to cover.
2. **Operator rotates** every name in sections 3 and 4, plus the
   `deliverable.co` password by hand — remembering that
   `OPENROUTER_API_KEY` and `LLM_API_KEY` are one credential under two names.
3. **Operator confirms at EmailBison** that superseded keys are revoked.
4. **Operator rotates the age key and the Storage Box password** per sections
   6 and 7, keeping the old age private key offline.
5. **Operator says "rotated X"**, per name.
6. **Claude verifies X by authentication only** and reports per name.
   `AUTHENTICATION_VERIFIED` closes the line; anything else does not.
7. Only when no line says ROTATION REQUIRED does this stop blocking cutover
   and live send.

**Deleting the Slack messages and the shared link is not a substitute for
rotation, and neither is proposed here as one.** A credential that sat in a
channel for two months, or behind a link that was shared, must be assumed
read. Deletion is tidying, and it is the operator's call, separately.
