# CREDENTIAL EXPOSURE INVENTORY — 2026-09-28

**Operator decision 12, Zvonimir, 2026-09-28.** Every credential that appeared
in Slack, a `work/` artifact or a shared chat, listed **by variable NAME and
never by value**, each marked **ROTATED (with evidence)** or **ROTATION
REQUIRED**.

**NO CUTOVER AND NO LIVE SEND WHILE ANY LINE BELOW SAYS ROTATION REQUIRED.**

The operator rotates. Claude then verifies **by authentication** —
`py -3 scripts/credential_health.py --verify`, which reads the registry and so
cannot invent a name, and which keeps `NOT_CONFIGURED` /
`CONFIGURED_UNVERIFIED` / `AUTHENTICATION_VERIFIED` / `AUTHENTICATION_FAILED` /
`PROVIDER_UNAVAILABLE` apart. **A set variable is not an authenticated one.**

---

## 1. WHAT WAS SEARCHED, AND WHAT THAT PROVES

Names came from `config.VARIABLES`; none is guessed. Every credential-shaped
name (`*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`) that is SET in this
environment with a value of 12 characters or more was searched for, as a
literal string, across every text file under `work/`, `docs/`, `scripts/`,
`src/`, `config/` and `tests/` — `config/.env` excepted, which is the store
rather than a leak.

**THE LIMIT OF THIS SEARCH, STATED BECAUSE IT CHANGES WHAT A CLEAN LINE
MEANS.** It searched for the value each variable holds **today**. A credential
that was exposed and has since been changed would NOT match, and one that was
exposed and never changed WOULD. So:

    a NAME listed below          its CURRENT value was found in the clear
    a name NOT listed below      its CURRENT value was not found. That is
                                 NOT proof it was never exposed - a
                                 superseded value is invisible to this
                                 search, and that state is UNKNOWN

Per invariant 0, **UNKNOWN is not PASS.** Where the operator wants certainty
for a name not listed here, the answer is a rotation, not a re-run of this
scan.

## 2. EXPOSED — ROTATION REQUIRED

All six were found **in the clear** in the stored history of
**`#resonate-leadership`** (Slack channel `C0AF9URBYSK`).

    AIARK_KEY              ROTATION REQUIRED
    APIFY_TOKEN            ROTATION REQUIRED
    BISON_KEY              ROTATION REQUIRED
    DELIVERABLE_KEY        ROTATION REQUIRED
    HEYREACH_KEY           ROTATION REQUIRED
    REOON_KEY              ROTATION REQUIRED

**The channel is PRIVATE and NOT externally shared** — confirmed by
`conversations.info`: `is_private: true`, `is_shared: false`,
`is_ext_shared: false`. **So this is not a client-facing disclosure**, and it
is a materially smaller incident than the two that reached prospects. It is
still exposure: Slack retains and indexes the message, every member of that
channel can read it, and any app or admin with history scope can export it.

Three messages carry them, all posted by the same human account, none by a
bot:

    2026-07-30T20:04Z   REOON_KEY, AIARK_KEY, HEYREACH_KEY
    2026-08-25T18:29Z   REOON_KEY, AIARK_KEY, HEYREACH_KEY,
                        APIFY_TOKEN, DELIVERABLE_KEY
    2026-09-09T15:19Z   BISON_KEY

## 3. ALSO EXPOSED, AND NOT IN THE LIST ABOVE

**`CONTACTOUT_TOKEN` — ROTATION REQUIRED.** It does not appear in section 2
because the STORED history shows `[REDACTED:SECRET]` where it stood. That
redaction happened on OUR side when the history was ingested. **The message in
Slack itself still carries the real token.** The redaction marker is positive
evidence that a ContactOut token was posted there, which is enough to require
a rotation; the value was deliberately not retrieved to establish it.

**A Deliverable account login — ROTATION REQUIRED, operator's own credential.**
The same 2026-08-25 message carries a `deliverable.co` username (a
`resonategroup.co` address) and a password, the password likewise already
`[REDACTED:SECRET]` in our stored copy. That is an account password rather
than an API variable, so it has no entry in `config.VARIABLES` and no
`credential_health` state — **it will not be caught by any automated check and
has to be rotated by hand.**

**At least one SUPERSEDED EmailBison key.** The two older messages carry a
Bison key that is NOT the current `BISON_KEY`, so the key changed at some
point between 2026-08-25 and 2026-09-09. Whether that change was a deliberate
rotation or an unrelated reissue is **UNKNOWN**, and an old key that was never
revoked at the provider is still a live key. **Confirm at EmailBison that
every key other than the current one is revoked** — rotating the current one
does not do that.

## 4. NO EVIDENCE OF EXPOSURE

`SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `AUTH_CLIENT_SECRET`,
`SESSION_SECRET`, `BLITZ_API_KEY`, `LLM_API_KEY`, `OPENROUTER_API_KEY`,
`GROQ_API_KEY`, `ANTHROPIC_API_KEY`.

Read this as section 1 says to read it: **their current values were not found
in the clear anywhere scanned.** It is not a statement about their history.

## 5. A SECOND DEFECT THIS SURFACED — THE INGEST REDACTOR IS INCOMPLETE

The stored history redacted a **ContactOut token** and a **password** and
missed **five other live provider keys in the same message**. A redactor that
catches two shapes and passes five is worse than none, because its output
looks redacted.

This is the same defect class already recorded once on this project: the
filter must be **self-tested against every value it is supposed to catch, and
before the first write, not after.** Whatever redacts Slack history on ingest
should be driven from `config.VARIABLES` — the registry that cannot invent or
forget a name — rather than from a list of patterns somebody maintained by
hand. Recorded here as work, not fixed in this change.

## 6. WHAT HAPPENS NEXT, IN ORDER

1. **Operator rotates** the seven names in sections 2 and 3, plus the
   Deliverable account password by hand.
2. **Operator confirms at EmailBison** that superseded keys are revoked.
3. **Operator says done.**
4. **Claude verifies by authentication** with
   `py -3 scripts/credential_health.py --verify` and reports per name, with
   `AUTHENTICATION_VERIFIED` as the only value that closes a line.
5. Only then does "no cutover and no live send" lift on this ground.

**Deleting the three Slack messages is not a substitute for rotation** and is
not proposed here: a credential that has sat in a channel for two months must
be assumed read. Deletion is tidying, and it is the operator's call, separately
from this.
