# LANE P - LinkedIn-only cohorts, provider-checked

**2026-09-25, reads only.** No provider write was made by this lane. Every
HeyReach write verb was replaced by a refusal before the first call and every
EmailBison call went through a GET-only wrapper; both wrappers counted
themselves. The foreground session performs the enrollment.

The plan the foreground executes is `work/laneP/ENROLLMENT-PLAN.json`
(gitignored, because it holds real people). This document holds the
measurements, the arithmetic and the refusals.

---

## 0. The headline

The constraint is **supply, not seats**. After the provider - not our store -
ruled on every candidate, the store yields **fewer than twenty** people who
are provably in no email campaign, provably in no LinkedIn campaign, and
whose LinkedIn profile provably belongs to the person and company we think.
The 825 figure is not reachable today from this store by any arithmetic,
and the three numbers below say why in three different ways.

| the number | what it is | source |
|---|---|---|
| 825 | 25/seat x 33 seats | the target as stated |
| 779 | sum of `min(25, seat's configured connection limit)` | provider, measured today |
| 330 | 10/seat x 33 seats, the rate a SHARED seat licenses | operator rule 2026-09-22 + provider, measured today |
| 14 | people who passed all four gates in the cells verified so far | provider, measured today |

---

## 1. The estate, re-measured rather than inherited

**36 EmailBison campaigns, ids 200-502, in THREE requests.** Cursor
pagination (`?pagination_type=cursor&per_page=100`) walks the whole campaign
listing in three pages. The full id list is in `work/laneP/bison_campaigns.json`.

**The campaign listing's own `total_leads` UNDERCOUNTS membership.** Measured
against the membership route's `meta.total` on the four largest client
campaigns:

| campaign | listing `total_leads` | membership `meta.total` |
|---|---|---|
| 352 | 21,530 | 21,530 |
| 328 | 10,285 | 10,915 |
| 327 | 9,676 | 10,008 |
| 274 | 9,734 | 10,049 |

Three of four disagree, always downward. **Any sizing that subtracts a
listing count from a pool is short by about a thousand people.**

**A full enumeration was priced and refused.** The listing sums to 56,452
lead-slots and the membership route serves fifteen rows a page whatever
`per_page` says - 3,764 pages. That is not a proportionate business-hours
read, so the question was inverted (section 2) rather than answered by a
crawl that would have run past the deadline.

---

## 2. "In no email campaign", answered per person, from provider truth

`GET /leads?search=<address>` is workspace-wide and each lead row carries
`lead_campaign_data`: the provider's own array of every campaign that lead is
in. Four things were established before any cohort rested on it:

1. **It reaches the client's estate, not just ours.** A lead taken from each
   of 352, 328, 327 and 274 was found by address, exactly once, every time.
2. **It is complete for a lead in several campaigns.** A lead whose campaign
   page showed `[274, 327, 352]` reported the same three through the search
   route.
3. **A name finds the person.** Searching a full name returned that same
   lead - which is what makes the alias check (E2) possible at all.
4. **An empty result is NOT how absence looks.** A deliberately impossible
   address returned **two rows** with `meta.total: 2`. The route is
   token-ish, so absence is argued from an exact-address filter over the
   rows, never from a short page. The provider module's docstring claims a
   nonsense term "returns nothing"; that is now measured to be false, and
   nothing in this lane depends on it.

### The four gates, in cost order

| gate | question | route | reject / exclude |
|---|---|---|---|
| E1 | in an email campaign under the address we hold? | `/leads?search=<address>`, exact match, `lead_campaign_data` | non-empty -> REJECT |
| E2 | in one under an address we do NOT hold? | `/leads?search=<full name>`, matched on normalised first+last AND company tokens | alias in a campaign -> REJECT |
| H1 | already in ANY LinkedIn campaign, ours or the client's? | `/campaign/GetCampaignsForLead` | any campaign -> REJECT |
| M1 | does this profile belong to that person at that company? | `/lead/GetLead` -> `firstName`/`lastName`/`companyName` | surname or company disagrees -> REFUSED; provider will not say -> UNVERIFIABLE |

**`unverifiable` is not a pass anywhere.** The verdict starts at
`unverifiable` and only evidence moves it. H1 that raises, M1 with no
company on either side, E2 that matched a name while neither side names a
company - all three exclude the candidate.

**H1 is the gate the store could not have answered.** Among the first three
candidates probed, one was in **thirteen** LinkedIn campaigns - IN_PROGRESS
and PAUSED, lead statuses `InSequence`, `Finished`, `Excluded` - while our
store recorded no LinkedIn campaign for them at all. Exactly one contact in
the store carries `heyreach_lead_id` and it is the operator's test identity,
so the store is structurally incapable of this answer and was never asked.

---

## 3. The seats, read rather than assumed

`/li_account/GetAll`: **41 seats, 34 active, 33 active with valid auth.**
Per-seat `accountLimits.connectioRequestLimit`, today, across those 33:

| configured daily connection limit | seats |
|---|---|
| 40 | 20 |
| 25 | 6 |
| 23 / 22 / 19 / 18 / 17 / 15 / 15 | 7 |

**Seven of the 33 seats cannot take 25 a day.** `min(25, limit)` over the 33
sums to **779**, so even granting the 25 rate, 825 is 46 slots larger than
the estate's own configuration. (A seat's limit also moves: the 2026-09-17
capacity audit recorded seat 139699 at 0; today it reads 25. Read it, never
remember it.)

**Every one of the 33 seats is SHARED.** `/campaign/GetAll` returns **120
campaigns**, 33 of which the store can attribute to us; **47 are
IN_PROGRESS** and each of the 33 seats carries between **8 and 14 of the
client's** IN_PROGRESS campaigns alongside our one. **Zero seats are
exclusively ours** - so `src/seatledger.py`'s permanent refusal applies to
every seat: our ledger is a lower bound and the client's usage is
unobservable, not merely unwalked.

The standing operator rule of 2026-09-22 settles what that means for the
rate: *"25 requests/seat/day is licensed by the seat's OWN ledger, not by the
absence of evidence. Where the client's usage on a shared seat is UNKNOWN,
the rate is 10 - unknown is not room."* Every seat is in that case today, so
**this plan is built at 10 per seat per day (330/day ceiling)** and the
operator can raise it to 25 by ruling on the shared-seat question, not by
anyone here assuming it.

One seat is held back: **174810** is inside our 33 live campaigns while the
2026-09-17 capacity audit excludes it as unattested. An attestation conflict
is not a seat to open a new cohort on. It is named rather than quietly used.

---

## 4. The pool, and where it goes

Store-side funnel (production `work/queue.jsonl`, read-only):

| step | contacts |
|---|---|
| records | 1,582 |
| contacts under a record that is not dropped/held/DNC | 1,011 |
| with a canonical LinkedIn profile | 1,011 |
| minus already carrying `bison_lead_id` | -646 |
| minus already in a LinkedIn campaign per the store | -149 |
| minus stopped / paused / do-not-contact | -9 |
| **survivors the store cannot rule out** | **207** |

Of those 207, **34 carry all five cohort axes**. The axes that fail are
persona (108 unnamed, before re-classification; 99 of 207 name one after
`personas.classify` is re-run against live titles), vertical (82 UNKNOWN) and
region (80 `Other`). The largest fully-tagged cell holds **nine** people.

**The fifth axis is honest rather than convenient.** `work/signals.jsonl` is
**zero bytes** - there is no first-party signal on anybody in this store - so
every candidate's signal state is `COLD`. The cohorts are homogeneous on that
axis by measurement, not by selection, and the tag says `COLD` rather than
implying a signal nobody has.

### What the provider did to the first three cells

20 candidates verified, 73 requests:

| verdict | n |
|---|---|
| `linkedin_only` (passed all four gates) | 14 |
| `excluded:M1_refused` - the profile is not that person at that company | 3 |
| `excluded:H1_unverifiable` - HeyReach would not answer | 2 |
| `rejected:in_email_campaign` | 1 |

**Three in twenty failed match validation.** That is the wrong-person class,
caught before a write rather than after one, and it is the reason M1 is not
optional.

---

## 5. The first cohort and its seat plan

Both cohorts below are homogeneous on all five axes, one campaign per seat so
the lead-to-seat binding stays sticky (multi-seat campaigns hand rotation to
the provider), and the campaign name carries every tag:

| cohort | geo | industry group | band | persona | signal | seat | leads | campaign name |
|---|---|---|---|---|---|---|---|---|
| P-1 | UK | Performance Marketing Agency | 1000_PLUS | economic_buyer | COLD | 116968 | 8 | `RP-UK-PERFORMANCE-1000_PLUS-BUYER-COLD-S116968-D1` |
| P-2 | UK | Creative / Branding Agency | 200_499 | economic_buyer | COLD | 116973 | 6 | `RP-UK-CREATIVE-200_499-BUYER-COLD-S116973-D1` |

Both names are under the provider's 50-character ceiling and unique in the
tenant. The lead rows, in `heyreach.build_lead_pairs` shape with `first_name`
and `last_name` present (the provider drops a lead missing either with a 200
and no error), are in `work/laneP/ENROLLMENT-PLAN.json`.

### Schedule: seven days, 07:00-23:00

```
dailyStartTime 07:00   dailyEndTime 23:00   timeZoneId <cohort timezone>
enabledMonday..enabledSunday all true
```

**It can only be set at creation.** `heyreach.set_schedule` is refused by
this repository because no route on the API reads a schedule back, and
`/campaign/Create` takes the same object. A campaign created without it
inherits the provider's Mon-Fri 09:00-17:00 UTC default - a window nobody
chose. Two consequences worth stating plainly:

* the existing 33 campaigns' windows **cannot be verified from the provider
  at all**, by this lane or any other;
* "seat-local" is **not resolvable from provider truth** - a seat row carries
  no timezone field. The plan therefore names the **cohort's** timezone
  (prospect-local), which for P-1 and P-2 is `Europe/London`. If the operator
  means the seat's own local time, that value has to come from the roster
  attestation, not from HeyReach.

### Expected readback, per campaign

* `campaign_read(id).status` == `DRAFT` immediately after create, and the
  campaign holds exactly `[seat_id]`;
* `list_leads(list_id)` count == the staged count - a 200 is not a staged lead;
* `campaigns_for_lead(profile_url)` == 1 campaign, this one, `leadStatus`
  `Pending`;
* the store write-back must carry `campaign_id_linkedin`, `linkedin_list_id`
  **and `heyreach_lead_id`**. ISSUE-041: the cross-channel stop is gated on
  that last field and no contact carries it, so an enrollment that omits it
  builds the next silent-stop failure while looking successful.

---

## 6. What would have made this a false pass

| the trap | what was done |
|---|---|
| "in no email campaign" from our store | never asked the store; E1/E2 are provider reads, and 646 store-flagged contacts were excluded BEFORE the provider even saw them, so the store can only shrink the pool, never admit to it |
| a partial campaign enumeration | the full 200-502 range was walked with cursor pagination in three requests and is on disk |
| an empty LinkedIn field read as no LinkedIn activity | H1 asks the provider per profile; the first three probes found one person in 13 campaigns the store knew nothing about |
| a seat's capacity assumed | `/li_account/GetAll` read per seat; the 25 rate is contradicted for 7 of 33 seats and the shared-seat rule caps the plan at 10 |
| `unverifiable` counted as a pass | it excludes, in all three gates that can produce it; 2 of the first 20 were dropped for exactly this |
| a cohort built in a worktree with an empty `work/` | this worktree's `work/` was empty; every store read is against the PRODUCTION checkout's `work/queue.jsonl`, by absolute path |

## 7. Request volume

| read | requests |
|---|---|
| EmailBison campaign enumeration | 3 |
| EmailBison search-contract and coverage probes | 16 |
| HeyReach seats | 1 |
| HeyReach campaigns (120, paged at 10 - the route times out at 100) | 12 |
| the gauntlet, first three cells (20 candidates) | 73 |
| the gauntlet, remainder of the 207-candidate pool | see `work/laneP/verified_all.json` |

Two provider quirks worth carrying forward: `/campaign/GetAll` **times out at
`limit=100`** and answers in about four seconds at `limit=10`; and
EmailBison's `/leads?search=` is an index that lags creation, so a lead
enrolled minutes ago is exactly the lead it cannot see.

## 8. What this lane did NOT do

* No provider write of any kind, including no list and no campaign.
* No claim about the 33 live campaigns' sending windows - unreadable by
  construction.
* No cohort larger than its evidence: the remaining 173 of the 207 survivors
  are being verified against the same four gates, and anything that passes
  extends the plan without changing its shape.
