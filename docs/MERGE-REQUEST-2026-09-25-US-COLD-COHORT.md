# The US cold cohort — provider-confirmed, 2026-09-25 morning

LANE J. Reads only, no provider writes, no credits spent (`productive` spent
today: **0** of `per_day: 5000`, unchanged by this lane). Own branch, no merge,
no push.

---

## THE NUMBER

**12,407 US contacts on 10,418 domains** survive the four exclusions, measured
against the live EmailBison estate at **2026-09-25 08:48:40Z–08:52:53Z**.

**Pushable today: 179.** The binding constraint is **packs**, not verification.
Without the pack requirement it is **2,525** and verification binds.

And the number the brief's own starting point produces:

**From `work/qualified-supply.jsonl`'s 16,247 US domains: 15,354 domains
survive the exclusions and ZERO contacts are pushable, today or on any day,
because not one of those 16,247 domains has a contact anywhere in this
system.** That is measured, not inferred: 0 of 16,247 appear in
`work/queue.jsonl`, which holds every contact this system has ever discovered
(1,582 domains, 1,065 contacts).

The two populations are different and the brief treats them as one. **They
overlap on 1,484 domains out of 16,247.** Section 1 separates them before
anything else, because every number below depends on which one is meant.

---

## 1. THE BRIEF NAMES TWO POPULATIONS AND THEY ARE NOT THE SAME LIST

The brief says the **09-07 list** goes out as cold, and then gives the starting
point as **`work/qualified-supply.jsonl`, US slice 16,247**. Measured:

| | the 09-07 list | `qualified-supply.jsonl` |
|---|---|---|
| file | `work/Productive/productive_ICP_safe_to_send (1).csv` | `work/qualified-supply.jsonl` |
| dated | 2026-09-07 (file mtime 09-07 20:44) | `_sourced_at` **2026-09-22**, all 32,951 rows |
| unit | **contacts** — 33,887 rows | **domains** — 32,951 rows |
| addresses | 33,445 unique, all `Work Email Status: Verified` | **none. There is no email field.** |
| domains | 24,710 | 32,951 |
| US | 17,312 addresses / 13,064 domains (see §2) | 16,247 domains (`country`) |

**Overlap: 1,484 domains** of the 16,247 US supply domains carry an address on
the 09-07 list; 14,763 do not. The 09-07 list is the only population in this
repository that carries contacts at all, so it is the only one from which a
cohort of *people* can be built today. `qualified-supply.jsonl` is a list of
companies nobody has found anybody at.

A second denominator trap inside the supply itself: `country == "United
States"` gives 16,247, but `_slice` ending `|United States` gives 15,906. They
disagree on 405 rows (373 one way, 32 the other). The 16,247 in the brief is
the `country` reading and this report keeps it, saying so.

---

## 2. THE FUNNEL — the 09-07 list, every stage with its denominator

| # | stage | count | denominator |
|---|---|---|---|
| 0 | the file as supplied | 33,887 rows | — |
| 0a | unique addresses in it | **33,445** | 33,887 rows (442 duplicate addresses) |
| 1 | US-classified from `Location` | 17,568 rows → **17,312 unique addresses** on 13,064 domains | 33,887 rows |
| 1x | *not* US | 11,307 rows | 33,887 rows |
| 1? | **UNDECIDED** — see below | 5,012 rows | 33,887 rows |
| 2 | present in the EmailBison estate | **9,765 (56.4%)** | 17,312 US addresses |
| 3a | **replied to the client, any class** | **968** | 17,312 |
| 3b | **unsubscribed** | **NOT READABLE — see §4** | 17,312 |
| 3c | **bounced at the provider** | **394** | 17,312 |
| 3d | **in a live sequence anywhere (email)** | **3,832** | 17,312 |
| 3 | union of 3a–3d (a person can be in several) | **4,905** | 17,312 |
| 4 | our own DNC list (`config/suppress.*`, NOT the provider) | **0 further** | 12,407 |
| 5 | **SURVIVORS** | **12,407 addresses / 10,418 domains** | 17,312 |
| 6a | survivors with a research-pack fact right now | **179** on 128 domains | 12,407 |
| 6b | survivors this day's verification budget can clear | **2,525** | 12,407 |
| 6 | **PUSHABLE TODAY** | **179** | 12,407 |

`Location` is supplier free text, not a country field. The UNDECIDED 5,012 are
single-segment labels the classifier would have to guess at — the largest are
`United Kingdom` (476), `Canada` (221), `Germany` (136) on the not-US side and
US metro labels with no country suffix on the other. **So the true US slice is
between 17,312 and roughly 20,000 addresses, and 17,312 is the floor.** It is
reported as a floor rather than resolved, because resolving it by guessing is
how "1,508 exportable that was 114" happens.

### What the survivors are made of — the stage the headline must not skip

| | count |
|---|---|
| never seen in the EmailBison estate at all | **7,547** |
| in the estate, demonstrably contacted, carrying **no** exclusion class | **4,860** |
| of those survivors, sitting at a domain where somebody **else** is excluded | 2,037 (flagged on the row, **not** removed) |

The 4,860 exist only because of the operator's decision. They are people the
client's estate has written to — `sequence_finished` or `stopped` — and the
collision rule's "touched by the client" clause would have removed every one.
The brief says that clause does not hold this list, so they stay, and they are
**39% of the cohort**. If that decision is ever revisited the number falls from
12,407 to 7,547.

The 2,037 are the account-level question. They are kept, per the same
instruction, and flagged on every row as
`domain_level_flag.estate_holds_an_excluded_person_at_this_domain`. Applying an
account rule instead would take the cohort to **10,370**.

### The same funnel for `qualified-supply.jsonl`, since the brief anchors on it

| # | stage | count | denominator |
|---|---|---|---|
| 0 | domains sourced 09-22 | 32,951 | — |
| 1 | `country == United States` | **16,247** | 32,951 |
| 1a | all `_icp_status: qualified` | 16,247 | 16,247 ✔ |
| 1b | all `_prior_touch: never_touched` | 16,247 | 16,247 ✔ (our store's opinion, not the provider's) |
| 1c | MX `known_allowed` 14,665 / `unknown_provider` 1,582 | 16,247 | 16,247 ✔ |
| 2 | domains where the estate holds **any** lead | **1,553** | 16,247 |
| 3a | domains holding a **replied** lead | **269** | 16,247 |
| 3b | domains holding an **unsubscribed** lead | **NOT READABLE** | 16,247 |
| 3c | domains holding a **bounced** lead | **100** | 16,247 |
| 3d | domains holding an **in_sequence** lead | **671** | 16,247 |
| 3 | union | **893** | 16,247 |
| 4 | **surviving domains** | **15,354** (13,802 MX `known_allowed`) | 16,247 |
| 5 | **contacts known at those domains** | **0** | 15,354 |
| 6 | **pushable today** | **0** | — |

Stage 5 is the whole point. 15,354 is a supply number and it has never been
asked stage 5's question. `_prior_touch: never_touched` is our store's record
and is the exact field the 09-24 incident proved cannot be trusted — the
provider read above finds 1,553 of these "never touched" domains already in the
client's estate and 893 of them holding somebody who is excluded.

---

## 3. WHAT ESTABLISHED EACH EXCLUSION, AND THE READ THAT DID IT

**The read.** `GET /api/leads`, workspace asserted as PRODUCTIVE (id 10) via
`bison.require_workspace(10)` before the first page, **cursor-paginated**,
2026-09-25 **08:48:40Z → 08:52:53Z**, **28,118 leads** in 1,875 pages.
Reconciled: `/leads` `meta.total` answers **28,118**. The walk is provably
complete.

| class | field that establishes it | US hits |
|---|---|---|
| replied to the client | `lead_campaign_data[].status == "replied"` | 968 |
| bounced | `lead.status == "bounced"` OR `lead_campaign_data[].status == "bounced"` | 394 |
| in a live sequence | `lead_campaign_data[].status == "in_sequence"` | 3,832 |
| unsubscribed | — nothing on this provider carries it — | unreadable |

Estate-wide, for scale: 3,259 leads replied, 1,272 bounced, 9,533 in_sequence,
0 unsubscribed; 14,970 of 28,118 carry no exclusion class at all.

### The reply field is not the obvious one, and the obvious one is wrong

`overall_stats.replies` and the per-campaign `replies` counter **read 0 for
people who demonstrably replied.** Measured live on three real leads:

    sandie@mediafast.com        overall_stats.replies 0, campaign 327 replies 0
                                campaign 327 STATUS: replied
                                provider's Inbox holds her "Automatic reply:
                                it starts at allocation, not invoicing"
    aundrea@redroverpromo.com   same shape, "Automatic reply: utilization at
                                Red Rover Promotions"
    camille.cunningham@...      lead.status bounced, campaign 327 status bounced

The operator's rule names OOO **first** among the classes that exclude. A
cohort built on the reply COUNTERS would have kept both of these women and
every other auto-responder in the file. The membership STATUS catches them.
This is why the count here (968 US) is larger than any counter-based read.

### The campaign-level counters disagree with the message feed, so neither was used

Campaign 327 reports `replied: 531`; `/replies?campaign_id=327&folder=inbox`
holds 153 rows; `emails_sent: 47,302` against 48 rows in its `Sent` folder.
The message feed is not a complete per-campaign archive and the counters are
not per-person. The per-lead membership status is the only surface that is
both complete and person-level, and it is what the cohort file cites.

### An offset walk of this estate silently reads half of it

`GET /leads?page=N` answers 200 at page 1000 and **422 at page 1001**, while
`meta.last_page` reports **1875**. At 15 rows a page (the estate ignores
`per_page`) an offset walk sees **15,000 of 28,118** and the 13,118 it cannot
reach are the OLDEST leads — which is exactly where the client's 2026-04
campaigns put the people this cohort must exclude. The first walk this lane ran
hit that wall. The cohort was rebuilt with cursor pagination and the count
reconciled against `meta.total`. **Any other lane walking `/leads` by `page`
has half an estate and no error to show for it.**

---

## 4. THE TWO CLASSES I COULD NOT CONFIRM, AND WHICH KIND OF "NO" EACH IS

### 4a. `unsubscribed` — the binding is absent, the answer is not zero

Zero of 28,118 leads carry `status: unsubscribed`; all 36 campaigns report
`unsubscribed: 0`. That is **not** a measurement that nobody unsubscribed.

- Eleven candidate routes — `/unsubscribes`, `/unsubscribed`, `/blocklist`,
  `/blacklist`, `/suppressions`, `/suppression-list`, `/do-not-contact`,
  `/leads/unsubscribed`, `/settings/blocklist`, `/workspaces/blocklist`,
  `/block-list` — **all 404** (probed 2026-09-25 08:54Z).
- `GET /leads?status=unsubscribed` answers **200 with all 28,118 rows**: the
  parameter is accepted and discarded, the `workspace_id` trap this API sets
  everywhere. A caller reading that count as "28,118 unsubscribed" or reading a
  filtered subset as authoritative would be equally wrong.
- Yet `attach_leads`' own refusal sentence names unsubscribed as a thing this
  provider enforces: *"either in other sequences, have previously bounced, or
  unsubscribed"*. **So the provider holds the fact and exposes no route to it.**

The consequence is concrete: an unsubscribed address in the 12,407 will not be
caught by this lane, and will surface as an all-or-nothing `attach_leads`
refusal at push time naming nobody. §7 says what to do about it.

### 4b. LinkedIn — not joinable to this cohort at all

HeyReach holds **120 campaigns** (47 IN_PROGRESS) and **949,683 lead-slots** —
of which **949,528 are the client's own** and 155 are ours across 38
RESONATE-named campaigns. 186,821 in progress, 698,841 pending. The inbox holds
**27,219 conversations**.

It cannot be subtracted from this cohort, and the reason is structural, not a
sampling limit. Sampled 2,000 conversations, 2026-09-25 08:56Z:

| field on `correspondentProfile` | populated |
|---|---|
| `emailAddress` | **0 / 2,000** |
| `enrichedEmailAddress` | **0 / 2,000** |
| `customEmailAddress` | **0 / 2,000** |
| `companyUrl` | 1,571 / 2,000 — **every one a `linkedin.com/company/…` page**, so it yields exactly one web domain: `linkedin.com` |
| `companyName` | 1,963 / 2,000 — free text |
| `profileUrl` | 2,000 / 2,000 |

`campaign_leads` rows carry `profile_url`, `provider_profile_id`, `sender_id`
and three status fields — **no email, no web domain**. So there is no key on
which a LinkedIn reply or a live LinkedIn sequence can be joined to an
email-domain cohort. The only candidate is `companyName` free text, and this
repository has already measured a label search returning a different company.

This is ISSUE-041's shape seen from the other end. ISSUE-041 says zero of our
contacts carry `heyreach_lead_id`; re-measured today, **1 of 1,065** does — the
operator's test identity, bound by hand after the incident. Both halves of the
binding are missing, so **"no LinkedIn activity recorded" for this cohort means
the binding is structurally absent, not that nothing happened.** Per the
brief's trap 2, that is stated and not counted as evidence.

One thing the LinkedIn side *is* covered on: EmailBison campaign 352, "HeyReach
Connection Campaign", holds 21,530 leads **with email addresses**, and those
leads were in the estate walk. So HeyReach-sourced people who were also loaded
into EmailBison are excluded normally; the 949k who were not, are not reachable
by any read available here.

Also on trap 1: 95 of the 2,000 sampled conversations have the correspondent as
the last sender — consistent with the brief's 12-of-400. For this lane that
distinction does not matter (a reply to the client excludes too), but it could
not be applied either way, for the reason above.

---

## 5. THE ESTATE IS TWICE WHAT THE BRIEF SAYS, AND THE MISSING HALF IS THE HALF THAT MATTERS

The brief: *"17 EmailBison campaigns (ids 451–502; 15 ours, 501 ours, 502 is a
human's draft)"*. Measured by walking `GET /campaigns?page=N&per_page=100`,
2026-09-25 08:43:34Z: **36 campaigns, ids 200–502.**

| | campaigns | leads | emails sent | replied | bounced | unsubscribed |
|---|---|---|---|---|---|---|
| ids 200–424 — **the client's own** | **19** | 55,547 | **246,514** | **2,276** | **2,147** | 0 |
| ids 451–502 — ours | 17 | 891 | 694 | 21 | 3 | 0 |

The 17 in the brief are only the RESONATE-prefixed ones. **Every exclusion this
lane is asked for lives overwhelmingly in the 19 the brief does not mention** —
"replied to the client" is, definitionally, campaigns 200–424. A lane that
enumerated 451–502 and stopped would have found 21 replies instead of 2,276 and
reported a cohort ~4,800 people too large.

Campaigns were ordered by provider id numerically throughout, never by
`created_at`. (For the record: on `GET /campaigns` `created_at` is **populated**
on all 36, including the ones that send — the null-`created_at` hazard in the
register did not reproduce on this route today. Ordering by id anyway.)

**Campaign 502 is being loaded by a human right now.** Observed live:
57 leads at 08:42Z → 66 at 08:43Z → **76 at 08:58Z**, status `draft`,
`PRODUCTIVE - SOFTWARE DEVELOPMENT - CONNECTED - JELENA - SEPTEMBER 25`,
created 08:21:47Z today. Whoever pushes must not assume 502 is inert, and its
76 leads will start reading `in_sequence` the moment it leaves draft — a lead on
a DRAFT campaign already reads `in_sequence`, per `_attach_refusal`.

---

## 6. PUSHABLE TODAY, AND WHICH CONSTRAINT BINDS

### Verification — not binding

`productive` declares `per_day: 5000`, **0 spent today**, `total: 50000` with
**4,444 committed** (45,556 left). Measured from `work/spend-ledger.jsonl`:
1,065 `reoon-verify` rows at 1 credit and 1,068 `deliverable-verify` rows at 1
credit — two verifiers per address, **1.98–2.00 credits per address**. So
**2,525 addresses today**, which matches the brief's ~2,500.

Confirmed and NOT acted on: `per_run: 2000` is declared and **not enforced** —
`spendledger.check()` tests `per_day`, `total` and `per_provider_per_day` and
never reads `per_run`. No ceiling was raised. Nothing was spent.

### Packs — **binding, at 179**

The brief's "zero of the 32,951 carry a research pack" was true this morning
and is no longer. `work/researchpack-us-CALIBRATION.jsonl`, last written
**08:52:29Z**: 900 domains attempted, **609 carry ≥1 fact** (67.7% yield, all
`site_page` from `local_http` — free, `usd: 0.0`).

Of the **12,407 survivors, 179 have a pack fact** (128 domains).
Of the 15,354 surviving supply domains, 486 do.

**The free crawl is pointed at the wrong population for this cohort.** It is
crawling the 09-22 US supply; the cohort with contacts is the 09-07 list, and
they share 1,484 domains. So:

- survivors whose domain the current crawl will *ever* reach: **1,688** (1,071 domains)
- survivors the current crawl **can never pack**: **10,719**

Even run to completion on all 16,247, the current crawl caps this cohort at
~1,688 pushable addresses. To reach 12,407 it has to be pointed at the
**10,418 survivor domains**, 9,347 of which it has no reason to visit.

**The crawl appears to have stopped.** 900 domains in 8.1 minutes (110.7/min,
67.7% yield), last row 08:52:29Z, no new rows by 08:58:23Z. At the observed
rate the remaining 15,347 supply domains are ~2.3 hours **if it resumes**. Lane
C/D own it; flagged, not touched.

### The answer

| | cohort | binding |
|---|---|---|
| with the pack requirement | **179 today** | **packs** |
| without the pack requirement | **2,525 today** | verification |
| the full cohort, unconstrained | **12,407** | 24,566 credits ≈ 5 days at the daily ceiling, inside the 45,556 total headroom |
| from `qualified-supply.jsonl` | **0, today or ever** | **contact discovery, which nobody's lane owns** |

That last row is the one to argue with. Cost of discovery measured from the
ledger: 4,444 credits produced 1,065 contacts across 1,582 domains — **2.81
credits per domain processed, 4.17 per contact produced.** At 2.81/domain the
16,247 US supply domains cost **45,654 credits**. The remaining total headroom
is **45,556**. The supply is, to within 0.2%, exactly one credit budget wide,
and discovery competes with verification for the same 5,000/day.

---

## 7. THE COHORT FILES

**`work/US-COLD-COHORT-2026-09-25.jsonl`** — 12,407 rows, one per surviving
address. Per-lead provenance on every row: source list and its 09-07 date, the
`PRODUCTIVE-2026-09-07` approval snapshot, the supplier's own email status, the
US classification basis, and a `provider_read` block naming provider,
workspace, route, read timestamp, estate size, `bison_lead_id`, `lead_status`
and **every campaign membership with its status**. The `exclusions` block
records the three classes that were confirmed false and spells out, in the row
itself, that `unsubscribed` is NOT_READABLE and LinkedIn is NOT_JOINABLE, with
the probe evidence. `domain_level_flag` carries the 2,037.

**`work/US-COLD-SUPPLY-DOMAINS-2026-09-25.jsonl`** — 15,354 rows, the surviving
US supply domains, each carrying `contacts_known: 0` and a `blocking` field
saying so.

Both are in **this lane's worktree**:
`C:\Users\Zvonimir\Desktop\resonate-group-automation\.claude\worktrees\agent-a512859f89c845afa\work\`.
`work/` is gitignored, so they are not in the commit; the foreground session
should read them from that absolute path or copy them across.

**Freshness re-checked after the fact.** 30 survivors sampled from the 4,860
that exist in the estate were re-read live at **08:57:35Z**, after the cohort
was written: **0 had drifted into an exclusion class.** This is the 09-24
failure's own check — 73 of a re-engagement cohort had already replied and the
store did not know — run against this cohort rather than assumed away. It does
not make the file permanent: the estate changes, and 502 gained 10 leads during
this session.

---

## 8. WHAT I COULD NOT VERIFY

1. **`unsubscribed`.** No route exists (§4a). The class is unmeasured, not
   zero. Nothing in the 12,407 is certified un-unsubscribed.
2. **Any LinkedIn exclusion.** No join key exists (§4b). 949,528 client
   lead-slots and 27,219 conversations are outside this cohort's reach.
3. **The UNDECIDED 5,012** rows of the 09-07 list (§2). 17,312 is a floor;
   the US slice may be ~20,000 and the cohort correspondingly larger.
4. **Inbound mail that is not attributable to a campaign.** The provider's
   Inbox folder holds **109,355** messages; only **1,050** are attributable to
   any of the 36 campaigns. The remaining ~108,000 are the client's own
   mailbox traffic. Walking it is free but runs at ~3 pages/min against this
   route's 15-row pages — **~38 hours** — so it was started, measured, and
   abandoned rather than left to produce a partial answer that looked whole.
   Per-lead membership status covers everyone who is a lead; somebody who wrote
   to the client without ever being a lead is not covered.
5. **Whether the supplier's "Verified" still holds.** All 33,887 rows say
   `Verified`, dated 2026-09-07 — **18 days stale**. None was re-verified here;
   that costs credits another lane needs, so it is declared rather than spent.
6. **The 2,037 domain-level flags** are a policy question, not a measurement.
   Kept per the brief; removing them gives 10,370.

---

## 9. THE ONE THING THAT SHOULD CHANGE BEFORE ANYBODY PUSHES

`attach_leads` is **all-or-nothing**: one unsubscribed or in_sequence address
in a batch attaches **nobody**, and the 422 names nobody. With `unsubscribed`
unreadable (§4a), that failure is not preventable by pre-filtering — it can
only be made cheap. Push in small batches and let `_attach_refusal`'s
per-lead diagnosis (capped at 50) name the holder, rather than sending 179 and
learning that one of them is suppressed.

---

*Lane J. EmailBison reads: 1 campaign listing, 75 campaign fetches, 1,875 lead
pages, ~20 probe calls, 30 re-checks. HeyReach reads: 3 campaign pages, 41
conversation pages, 1 campaign-leads page. Zero writes. Zero credits.*
