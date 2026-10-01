# HANDOFF — 2026-10-01 LIVE SESSION

Written at the START of the session that owns it, not at the end, because the
previous tab reached 100% context and wrote no handoff. It is updated before
every ~80% context mark. No PII. Person-level detail lives outside the repo.

**Repo:** `master d98c83ce4625cbbaef7d55894333bd2b3412839e` == `origin/master`,
verified by `git fetch origin && git rev-parse HEAD origin/master` at 13:36.

**Freeze ON. `sending.live=false`. Zero prospect-facing writes until TWO
SEPARATE operator GOs: an email GO and a LinkedIn GO. An email GO is not a
LinkedIn GO.** Credits limit 200, 90 spent.

---

## 0. WHAT THE PREVIOUS TAB LEFT, MEASURED NOT ASSUMED

**CLAIM** Two agents were possibly still running from the stopped tab.
**AUTHORITY** `Get-Process` (process table), `work/` mtimes, `git worktree list`,
`git for-each-ref` across all refs.
**MEASURED AT** 2026-10-01 13:34-13:38.
**STATE**

- **No python process is running at all.** The only `claude` process started
  today is this tab (13:33:34). Nothing is generating, crawling or sending.
- **No `work/queue.jsonl.lock`.** `work/queue.jsonl` mtime 12:45 — no store
  write since. Safe to write to the store.
- **LinkedIn readiness agent: FINISHED, result recovered.**
  `docs/LINKEDIN-CANARY-READINESS-2026-10-01.md` (13:33). Person-level log is
  outside the repo at the canary-log directory on the Desktop.
- **Crawler-UA and bigfish research agent: DID NOT FINISH; its work is lost.**
  Measured: `src/webfetch.py` `USER_AGENT` is unchanged from master, there is no
  branch or commit for it, and `work/crawl-cache.json` holds **thirstcraft.com
  only — zero rows for bigfish.co.uk**. Re-launched in this session.
- The "inspecting research blocks in productive.yaml" agent left no process, no
  branch and no file. Nothing to recover.

---

## 1. EMAIL TRACK — BLOCKED BEFORE GENERATION, TWO CAUSES

**E1 = the first provider-confirmed email send.** Not reached.

Candidate: **bigfish.co.uk** (Operations Director, champion persona, verified,
never contacted). Reserve: **thirstcraft.com**.

**First blocker — the angle, and it is a code defect, not a data problem.**
`src/personas.py:127 default_angle(config, persona, family=None)` returns an
angle only when the routing `family` matches one of the persona's angles, or
when the persona has **exactly one** angle. The `champion` persona has four, and
the call site passes no family, so it returns `None`; `lint` then raises
`domains_contact_no_angle` at every step and nothing can be generated. That is
exactly what the scoped run produced today: `domains_contact_no_angle` on all
steps, contact angle `None`, research rows 0.

**Second blocker — research returned nothing.** 0 research rows for
bigfish.co.uk. The previous tab's explanation was a 403 caused by the
User-Agent while robots.txt allows the path. **That explanation is UNVERIFIED**
and is being measured one variable at a time this session, because a WAF or bot
manager and a UA block are not the same finding, and only one of them is fixed
by changing a string.

### The operator's decision that unblocks it (2b, approved)

L1/L2 stay exactly as they are when permitted evidence exists. With **zero**
permitted evidence rows the angle is chosen **deterministically from config** —
the persona's primary angle per the client's own config, else the first in the
canonical order — labelled **L3/L4**, and the copy carries **not one claim about
the prospect**. A lack of personalization is NOT a reason to HELD. Claims,
traceability, CTA, lint and sequencegate are untouched. Traceability stays
all-or-nothing by authority (bd133ca7), no union. Writer contract: a mixed
sentence (offer plus capability behaviour) is always split into two.

---

## 2. LINKEDIN TRACK — THE SEAT IS NOW DECLARED, THE BINDING IS NOT BUILT

**L1 = the first provider-confirmed LinkedIn action, precisely classified as a
connection request or a message.** Not reached.

**Operator decision, 2026-10-01:** Ivan Mamic's LinkedIn profile on HeyReach is
the sender for L1. **No other HeyReach account is in scope.**

What the readiness measurement found (live provider read, same day):

- 41 seats, 33 active with valid auth; **exactly one on the `productive.io`
  domain** — the Ivan Mamic seat, 40/day connection requests, 40/day messages,
  no cooldown, 8 active campaigns, **none of them ours**.
- The campaign literally named `RESONATE - PRODUCTIVE LINKEDIN CANARY - CONTROL`
  (604869) **is attached to a different seat** on a `gmail.com` domain attested
  to a different human. The pre-built canary would have sent as somebody else.
- `senderownership.one_attested_human` **refuses 35 of 35 seats**. Two measured
  causes: the Productive-domain seat has no `linkedin_account` roster row at all,
  and the 33 LinkedIn `ownership_attestation` rows are keyed `hr-<id>` while the
  account rows are keyed `li-<id>` — **intersection 0 of 35**. The attestations
  exist and never join. The email side does join.
- `seatledger.daily` on that seat returns **REFUSED / client_usage_unknown**,
  and it is permanent, not stale: exclusivity requires
  `campaigns_total == campaigns_created_by_resonate` and the account is 121 total
  against 40 ours. No walk of our own ledger can ever prove room on a shared seat.
- LinkedIn writes were measured bypassing `eligibility.decide`
  (`heyreachfactory`, `providerwrites`). The cross-channel stop HOLDS at
  `decide` in both directions; the September incident happened on a path that
  does not call it. **A gate that answers correctly when asked is not a send
  path that asks it.**

Standing LinkedIn constraints, unchanged: a different person AND a different
company from the email canary; the 9 accepted connections the operator answers
by hand are untouchable; Megan Ward and her company are DNC on both channels;
negative HeyReach replies, including the "no thank you" incident, block email
too, proven by test; `vertical: UNKNOWN` disqualifies; the `mike-hurt` override
is refused; the Bruno ownership message is NOT sent.

---

## 3. TWO NEW PERMANENT RULES — Zvonimir, 2026-10-01

Both are written in full in `docs/OPERATING-MODE.md` and summarised in
`CLAUDE.md`. They are standing rules, not session notes.

1. **Every workspace holds two kinds of campaign** — Resonate OS campaigns (our
   code made them and recorded them in the ledger) and internal Resonate
   campaigns the team runs by hand. **274, 327, 328 and 352 are internal**, and
   they are neither the client's nor Resonate OS. Internal campaigns are never
   written to, by any verb, from code or from an agent. The provider-write guard
   **defaults to REFUSE** for any campaign not positively recorded as Resonate OS
   in the ledger. Three ownership states: `resonate_os`, `resonate_internal`
   (operator-declared list in config, because the provider has no owner field),
   `unknown` — and **UNKNOWN means do-not-touch and members NOT CLEAN**. They are
   a read-only learning asset, and their negative replies, DNCs, unsubscribes and
   bounces go into the **local** suppression and touch ledger, never to a provider.
2. **"Never contacted" is no longer the line — COLD LEAD is.** Blocked if in an
   active campaign on any channel, or a paused one with non-terminal rows; if the
   last prospect-facing touch on any channel is within 30 days by provider truth;
   permanently on negative reply, DNC, unsubscribe, bounce, operator exclusion or
   suppression; on a live conversation or positive reply, which goes to a human;
   and on **any UNKNOWN**. Otherwise a previously targeted lead whose last touch
   is older than 30 days is COLD and eligible, subject to every other gate.
   Status is authoritative, not the replies counter. Cold-lead copy must not
   pretend to be a first contact, nor mention prior campaigns.

For the canary, bigfish stays primary precisely because it was never contacted.

---

## 4. LANES IN FLIGHT THIS SESSION

| Lane | Branch | What it must return |
|---|---|---|
| EMAIL critical path | `task-l34-deterministic-angle` | deterministic L3/L4 angle from config, four tests with controls, false-positive measurement |
| EMAIL research | `task-honest-crawler-ua` | the TRUE cause of the 403 one variable at a time, honest identifying UA, robots.txt enforced on every path, research-row counts for both domains |
| LINKEDIN | `task-linkedin-seat-binding` | Ivan Mamic account measured read-only, the `hr-` to `li-` key join fixed with controls, the exact roster row needed, a candidate proposal or a reasoned refusal |
| RAMP, internal campaigns | `task-internal-campaign-guard` | three-state classifier, default-REFUSE guard, every write verb refused for 274/327/328/352, entry-point bypass table |
| RAMP, learning | `task-internal-campaign-learnings` | reply rates per campaign and step, what got replies, the negative and DNC list in a scratchpad for local ledger merge |
| RAMP, eligibility | `task-recontact-cold-lead` | the cold-lead rule with its eight tests, and the re-measured COLD-eligible pool count |

No lane may write to `work/` — only this session writes the store. No lane may
merge; this session merges after GLM PASS on the final SHA.

---

## 5. WHAT IS STILL UNKNOWN, AND STAYS UNKNOWN UNTIL MEASURED

- Whether the bigfish 403 is a UA block or a bot manager. UNVERIFIED.
- Whether the Ivan Mamic seat can ever pass `seatledger` while it is shared
  (121 campaigns against 40 ours). The operator must either accept an unknown
  denominator in writing or supply an exclusive seat.
- Which of the two contradictory `li1` builders is the canonical one. Until that
  is settled the LinkedIn checkpoint cannot state the action being approved.
- The 15-minute automated reply-stop test the push halt waits on has still never
  run.
