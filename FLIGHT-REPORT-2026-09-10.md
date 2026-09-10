# Flight report — 2026-09-10

Written for an operator who was away and needs to know what changed, what it
cost, what is now true that was not, and what still needs a person.

---

## The headline

**The 50-domain Productive cohort went from zero campaign-ready to four
qualified companies and two contacts with full 2/2 verification — with no ICP
rule loosened, no threshold lowered, and no safety invariant weakened.**

Three defects were in the way, and all three were things that looked like
working systems.

| | BEFORE | AFTER |
|---|---|---|
| research executed | 1 | 22 |
| vertical known | 16 | 21 |
| confidence HIGH / MEDIUM / LOW | 0 / 0 / 50 | 1 / 4 / 45 |
| **QUALIFIED** | **0** | **4** |
| review / unknown / rejected | 7 / 24 / 19 | 8 / 18 / 20 |
| records with contacts | 0 | 2 |
| people found | 0 | 4 |
| **2/2 verified, sendable** | **0** | **2** |
| persona assigned / cadence built | 0 / 0 | 0 / 0 |

The last row is the honest edge of it: the `personas` and `generate` stages
have not been run, so nothing is campaign-ready in the full sense yet. What
exists is a verified person at a qualified company, which is the input those
stages need and which did not exist this morning.

---

## What was actually broken

### 1. Two producers of one evidence shape

`icp.confidence_components` scores `source_quality` from `item["quality"]` and
`recency` from `item["freshness_score"]`. `apify.evidence_from_items`
hand-built a nine-key dict and wrote neither — so every piece of research
scored 0.0, with the reason "0 usable piece(s) of evidence", about pages that
had been retrieved perfectly well. `claims` licenses a sentence by
`evidence_id`, also absent, so nothing written from a scraped page could ever
be cited.

Fixed at the producer. There are now 11 STRONG and 4 MEDIUM pieces of evidence
where before every single one was `quality: None`.

### 2. The need was computed after the only chance to act on it

`research.why` returns NEED_ICP_EVIDENCE only when `icp_status` is review or
unknown. That status is written by the **qualify** stage. `research.run` is
called from **enrich**. `STAGES` is `("enrich", "qualify", ...)`.

So at the moment research was offered, the verdict it depends on did not
exist. Measured: 30 records for which the need is stated once a verdict
exists, and **zero scrape events on any of them, ever**.

Enrichment now asks the free question first — `qualify.company` spends nothing
— and threads the computed verdict through. Computed, not stored: a first
attempt persisted it, which held the record and stopped verification running
at all. Eight tests went red and said so.

### 3. Boilerplate was classifying companies

`segments.text_of` appended every research fact to the text the vertical
classifier reads. For the one company this build had ever researched, that was
2,488 words of Hungarian privacy and cookie policy — long, in the company's own
language, diluting every ratio the module computes.

`evidence.boilerplate` is a new canonical test, calibrated on the corpus rather
than chosen: real company copy runs 0.5–1.5 consent terms per 100 words, the
two policy documents ran 10.3 and 13.2. Over all 86 stored items it refuses
exactly three — two policy documents and a password wall.

Two earlier versions of that filter were wrong in the direction that matters,
and both are pinned as tests: one rejected a 39-word agency description for a
single cookie line, the other rejected "Acme opened a Vienna delivery office"
for being six words.

---

## What it cost, and what cannot be said about it

`src/costs.py` is new. It reconciles what a run's ledger expected against what
the providers' own counters say, and classifies each provider:

```
COST_UNRECONCILED  contactout   expected=22  calls=4
                   22 credits expected and NO counter moved. It must not be
                   reported as 22 spent, and it must not be reported as free.
UNPRICED           apify        expected=0   calls=10   usd +0.664858
                   Ledgered calls at a zero price that cost real money.
                   A wrong price, not a bypass.
ESTIMATED_ONLY     deliverable, reoon — no counter this system can read
```

**Apify, measured**: $4.03 → $6.47 across the day, ≈ $2.44 for 22 research
runs (~$0.10 each, at ~70s median).

**ContactOut — CORRECTED LATER THE SAME DAY.** Read twenty minutes after
pass 3, all three counters were unchanged against 22 expected credits, and
this section originally said "unchanged all day". Read again eight hours
later, the same window showed `count` 566→570, `search_count` 77→102,
`phone_count` 462→465, and the verdict moved from COST_UNRECONCILED to
**RECONCILED**.

**The counters lag.** The module had said "either these operations do not
meter against the buckets this system can read, OR the counters lag", and
refused to choose. The second disjunct was the true one, and the refusal is
what made the later correction cheap instead of embarrassing.

`costs.py` now carries `PENDING_SETTLEMENT` for exactly this: a disagreement
read minutes after a run is evidence of impatience, not of a mismatch. The
window is stated as bounds rather than as a number pretending to be exact -
not settled at 20 minutes, settled by 8 hours, nothing observed in between.

---

## Safety work

**A channel nobody can stop is capped at one person.** The killswitch refuses
to START an action and cannot END one, because neither provider exposed a pause
route. At one contact that gap is survivable; at fifty the killswitch is
decorative, and a daily volume cap never notices because fifty people reached
one a day never exceeds a daily ceiling. The new `stoppability` gate is
cumulative and unlocks itself the day a pause is proven.

**The pause route exists, is implemented, and is deliberately not declared.**
Probing with an empty body — no campaign identified, nothing to act on —
established `/campaign/Pause`, `/campaign/Resume` and `/campaign/StartCampaign`
all answer 400 where a made-up name answers 404. Pause is built, allowlisted
and tested. `SUPPORTED` is still empty, because `executionguard` LIFTS a
promotion ceiling on `is_supported`, and a ceiling must not move on the
strength of a route that has never once succeeded. One live attempt returned a
non-2xx; the write layer classified it UNVERIFIED and refused to retry; the
campaign stayed PAUSED throughout; further live attempts were refused by this
environment.

Resume and StartCampaign are deliberately NOT implemented. A system that can
start an outreach campaign before it can stop one has acquired the ability to
create exposure without the ability to end it.

**The prototype could still reach both providers.** `prototype/bin/push.py`
held two fully formed `requests.post` bodies behind three hand-placed
`refuse_live()` calls, importing nothing from `src/` — so no eligibility,
approval, killswitch, pilot cap, ledger or readback was in its path. It needed
an API key and a flag. The transport is deleted, not refused. A new repo-wide
scan asserts no undeclared HTTP write anywhere, and reports a verb decided at
runtime as unreadable, because that is the shape a future bypass would have.

**The LinkedIn collision check was unscoped.** The email half of that check
answered CLEAR against another client's empty estate on 2026-09-09 and was
hardened. The LinkedIn half — the channel campaigns actually run on, against an
inbox of 25,595 conversations across 33 seats — kept the original signature
with no workspace at all. HeyReach's inbox route accepts no organisation
parameter, so scoping now comes from the answer: a conversation is evidence
about this client only if it sits on a seat in this client's canonical roster.
Empty roster raises rather than answering CLEAR.

**An interrupted run discarded everything it had paid for.** `store.save` ran
once, after every per-record stage. A run killed at ten minutes changed zero
records and had spent $0.386 of Apify compute producing that nothing. Now
checkpointed every five records.

**Identity matching refused ambiguity for one identifier and not the other.**
`events.match_contact` gathered LinkedIn candidates and refused when there were
two, under a comment about attributing somebody's reply to the wrong person —
while the email branch three lines above returned on its first hit.

---

## The canary

Campaign 594061 passes **14 of 15 gates** against fresh provider truth,
including the now-scoped collision check:

```
PASS tenancy approval campaign_approval readback eligibility suppression
PASS copy claims fatigue collision sender pilot_cap stoppability ledger
STOP killswitch — global: live sending is refused in code (3 of 6 layers)
```

It did not execute, for two independent reasons:

1. The killswitch's global layer is **derived from `push.py` raising**, not read
   from a flag. There is no designed transition for it, and the standing
   instruction is not to neuter it.
2. This environment's permission layer refused every live provider write I
   attempted. That is a guardrail outside the repository, and I did not try to
   work around it.

**Execution remains one manual action**: unpause 594061 in the HeyReach UI.
Blast radius is one connection request from seat 116968 to the single staged
lead, carrying copy verified against the approved fingerprint today.
`HUMAN-ACTIONS-REQUIRED` §5e has the detail; §5f has the ladder gate.

---

## Validation

    full suite      6,980 tests, 1 failure - mine, fixed, re-run green
    offline harness 6,981 tests, 1 error - the documented intermittent
    mutations       32 run across 9 guards, each caught by its intended test
    HEAD            0c7695b

The offline error is `test_production_auth` failing to bind loopback, which
CLAUDE.md records as the known consequence of running `discover` and
`tests.offline` back to back without a gap. I ran them back to back. Diagnosed
rather than dismissed: it passes alone, as a class, and as a whole module.

One pre-existing integrity warning the suite raises and a human has to
decide: `report-drafts.jsonl` holds 4,944 rows created by
`tests/test_report_editor.py` with no store isolation, every one authored by
a reserved-TLD fixture address. Nothing read from that file is evidence about
a client. Clearing it is a destructive write to client state and is not mine
to make.

### The mutations, by guard

    sender gate            4   human-id lookup, unscoped roster, health, active
    stoppability           4   tenant, channel, never-applies, self-exclusion
    evidence contract      8   quality, freshness, entity, stale, empty,
                               malformed, boilerplate, foreign company
    verdict ordering       4   not consulted, not threaded, persisted, zero cap
    checkpoint             3   removed, interval widened, never saves
    crash window           3   sent reservable, unresolved unblocking,
                               unresolved not counted as exposure
    linkedin tenancy       3   foreign counted, workspace optional, empty roster
    cost reconciliation    4   unread-as-zero, unmoved-as-reconciled,
                               negative clamped, unpriced collapsed
    contactout-first       1   ordering fix reverted

---

## What still needs a person

1. **Press unpause on 594061**, or tell me the environment may perform live
   provider writes. Both are yours.
2. **Decide the ladder gate** (§5f): establish a pause route, or agree and
   write down an out-of-band stop, before LinkedIn goes past one contact.
3. **ContactOut's metering.** 22 expected credits moved no counter. Either
   `decision-makers` and `email-verifier` bill against a bucket `/stats` does
   not expose, or the counters lag. A support question, not a code question.
4. **Two ICP dimensions cannot be scored from company websites** —
   `utilization_need` and `time_tracking_need`. No agency advertises the
   operational problem a vendor wants to sell it. Job postings would answer
   both; nothing in this build reads them. That is a product decision.

---

## What is now autonomous that was not

- Research fires for the companies that need it, and its evidence reaches the
  classifier in the canonical shape every consumer already expected.
- Boilerplate cannot become decision evidence, at ingest or at classification.
- A run reports its own per-stage wall time, and survives being killed.
- A cost claim names its evidence class and refuses to resolve a disagreement
  it cannot resolve.
- The guard reports which gates passed before it stopped.

## What is deliberately still not

- No prospect-facing provider write. `providerwrites.SUPPORTED` is empty and
  four `raise` statements stand behind it.
- No campaign activation. The route exists and is not implemented.
- No automatic reply. A reply is a human's.
