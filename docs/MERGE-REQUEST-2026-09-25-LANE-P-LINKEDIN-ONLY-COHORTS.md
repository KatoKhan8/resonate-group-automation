# LANE P - LinkedIn-only cohorts, provider-checked

**2026-09-25, reads only.** No provider write was made by this lane. Every
HeyReach write verb was replaced by a refusal before the first call and every
EmailBison call went through a GET-only wrapper; both wrappers counted
themselves (680 requests for the whole pool, listed in section 8). The
foreground session performs the enrollment.

The plan the foreground executes is `work/laneP/ENROLLMENT-PLAN-PREFLIGHT.json`
(gitignored, because it holds real people). This document holds the
measurements, the arithmetic and the refusals. Everything here can be re-run:
`scripts/laneP/`.

---

## 0. The headline: 825 is off by two orders of magnitude, and seats are not why

| the number | what it is | where it comes from |
|---|---|---|
| **825** | 25/seat x 33 seats | the target as stated |
| **779** | sum of `min(25, seat's own configured connection limit)` | provider, measured today - 7 seats cannot take 25 |
| **330** | 10/seat x 33 seats, the rate a SHARED seat licenses | operator rule 2026-09-22 + provider: zero seats are exclusively ours |
| **74** | people in the store who are provably in no email campaign, in no LinkedIn campaign, and whose profile is provably theirs | 207 candidates through four provider gates |
| **5** | of those 74 who may actually be enrolled today, **ignoring cohort shape entirely** | the client's own account rules, applied per account against provider truth |
| **2** | today's first cohort, homogeneous on all five axes, on one seat | the plan |

**The binding constraint is not seats and not the cohort rule. It is that the
74 survivors sit at twelve accounts, six of which have somebody mid-sequence
or already answered.** Loosening the five-axis rule to nothing moves the
number from 2 to 5. Raising the rate from 10 to 25 moves it not at all.

---

## 1. The estate, re-measured rather than inherited

**36 EmailBison campaigns, ids 200-502, in THREE requests.** Cursor
pagination (`?pagination_type=cursor&per_page=100`) walks the whole listing
in three pages; the ids are in `work/laneP/bison_campaigns.json`.

**The campaign listing's own `total_leads` UNDERCOUNTS membership:**

| campaign | listing `total_leads` | membership `meta.total` |
|---|---|---|
| 352 | 21,530 | 21,530 |
| 328 | 10,285 | 10,915 |
| 327 | 9,676 | 10,008 |
| 274 | 9,734 | 10,049 |

Three of four disagree, always downward. Any sizing that subtracts a listing
count from a pool is short by about a thousand people.

**A full enumeration was priced and refused.** The listing sums to 56,452
lead-slots and the membership route serves fifteen rows a page whatever
`per_page` says - 3,764 pages. Not a proportionate business-hours read, so
the question was inverted per person (section 2) rather than answered by a
crawl that would have outrun the deadline.

---

## 2. "In no email campaign", answered per person, from provider truth

`GET /leads?search=<address>` is workspace-wide and each lead row carries
`lead_campaign_data`: the provider's own array of every campaign that lead is
in. Four things were established before any cohort rested on it:

1. **It reaches the client's estate.** A lead taken from each of 352, 328,
   327 and 274 was found by address, exactly once, every time.
2. **It is complete for a lead in several campaigns.** A lead whose campaign
   page showed `[274, 327, 352]` reported the same three through search.
3. **A name finds the person**, which is what makes the alias gate possible.
4. **An empty result is NOT how absence looks.** A deliberately impossible
   address returned **two rows**, `meta.total: 2`. The route is token-ish, so
   absence is argued from an exact-address filter over the rows, never from a
   short page. `bison.find_lead_by_email`'s docstring claims a nonsense term
   "returns nothing"; that is measured to be false today, and nothing in this
   lane depends on it.

### The four gates, in cost order

| gate | question | route | reject / exclude |
|---|---|---|---|
| E1 | in an email campaign under the address we hold? | `/leads?search=<address>`, exact match, `lead_campaign_data` | non-empty -> REJECT |
| E2 | in one under an address we do NOT hold? | `/leads?search=<full name>`, matched on normalised first+last AND company tokens | alias in a campaign -> REJECT |
| H1 | already in ANY LinkedIn campaign, ours or the client's? | `/campaign/GetCampaignsForLead` | any campaign -> REJECT; a 404 is UNVERIFIABLE, never absence |
| M1 | does this profile belong to that person at that company? | `/lead/GetLead` -> `firstName`/`lastName`/`companyName` | surname or company disagrees -> REFUSED; provider will not say -> UNVERIFIABLE |

**`unverifiable` is not a pass anywhere.** The verdict starts at
`unverifiable` and only evidence moves it.

### What 207 candidates did against those gates

| verdict | n | what it means |
|---|---|---|
| `linkedin_only` | **74** | passed all four |
| `excluded:M1_refused` | 46 | the profile is **not** that person at that company |
| `excluded:H1_unverifiable` | 30 | HeyReach answered 404 for the profile - a refusal, not an absence |
| `rejected:in_email_campaign` | 23 | in an EmailBison campaign the store knew nothing about |
| `excluded:M1_unverifiable` | 17 | the provider would not name the company on one side |
| `rejected:already_on_linkedin` | 17 | already in a LinkedIn campaign, ours or the client's |

**Two of these are the whole reason the lane exists.** 23 candidates carried
no `bison_lead_id` in our store and were nonetheless in client email
campaigns - one in three of them at once (274, 327 and 352). 17 were already
in LinkedIn campaigns the store had no record of; the first three candidates
ever probed included one sitting in **thirteen**. Exactly one contact in the
store carries `heyreach_lead_id` and it is the operator's test identity, so
the store is structurally incapable of either answer and was never asked.

**63 of 207 - three in ten - failed match validation.** That is the
wrong-person class, caught before a write rather than after one.

---

## 3. The seats, read rather than assumed

`/li_account/GetAll`: **41 seats, 34 active, 33 active with valid auth.**
Per-seat `accountLimits.connectioRequestLimit` across those 33, today:

| configured daily connection limit | seats |
|---|---|
| 40 | 20 |
| 25 | 6 |
| 23 / 22 / 19 / 18 / 17 / 15 / 15 | 7 |

**Seven of the 33 cannot take 25 a day**, so `min(25, limit)` sums to **779**
and 825 is 46 slots larger than the estate's own configuration. A seat's
limit also moves: the 2026-09-17 capacity audit recorded seat 139699 at 0 and
it reads 25 today. Read it, never remember it.

**Every one of the 33 seats is SHARED.** `/campaign/GetAll` returns **120
campaigns**; 33 are attributable to us and **47 are IN_PROGRESS**. Each of
the 33 seats carries between **8 and 14 of the client's** IN_PROGRESS
campaigns alongside our one. **Zero seats are exclusively ours**, so
`src/seatledger.py`'s permanent refusal applies to every seat: our ledger is
a lower bound and the client's usage is unobservable rather than unwalked.

The standing operator rule of 2026-09-22 settles the rate for that case:
*"25 requests/seat/day is licensed by the seat's OWN ledger, not by the
absence of evidence. Where the client's usage on a shared seat is UNKNOWN,
the rate is 10 - unknown is not room."* Every seat is in that case today, so
this plan is built at **10 per seat per day**. The operator can raise it to
25 by ruling on the shared-seat question; nobody here may assume it.

Seat **174810** is held back: it is inside our 33 live campaigns while the
2026-09-17 capacity audit excludes it as unattested. An attestation conflict
is not a seat to open a new cohort on. It is named rather than quietly used.

---

## 4. The pool, and the two things that empty it

Store-side funnel (production `work/queue.jsonl`, read-only):

| step | contacts |
|---|---|
| records | 1,582 |
| contacts under a record that is not dropped / held / DNC | 1,011 |
| with a canonical LinkedIn profile | 1,011 |
| minus already carrying `bison_lead_id` | -646 |
| minus already in a LinkedIn campaign per the store | -149 |
| minus stopped / paused / do-not-contact | -9 |
| **survivors the store cannot rule out** | **207** |
| after the four provider gates | **74** |

### 4a. The 74 sit at twelve accounts

| account verdict (`collision.account_policy`) | accounts | people behind them |
|---|---|---|
| `hold` - a campaign there ended early and nobody can say who stopped it | 3 | **44** |
| `allow` - no prior contact, or finished history with no reply | 3 | 19 |
| `stop` - somebody is mid-sequence (4) or the account has already replied (2) | 6 | 11 |

With the client's own `fatigue.account.max_active_contacts: 2` -
configured, not a default, and reasoned on the lines above it in
`config/clients/productive.yaml` - the three ALLOW accounts yield **5
people** (2 + 2 + 1; the third has only one survivor). That is the ceiling
for today **with no cohort rule at all** (`scripts/laneP/ceiling.py`,
`work/laneP/CEILING.json`).

All three `hold` accounts hold for the same reason, and it is **ISSUE-035**:
our own deliberate stop reads to the collision gate as "a campaign at this
account ended early (stopped), and the status does not say whether we
stopped it, they unsubscribed, or the provider stopped it on a reply".
**44 of the 74 survivors - three in five - are behind that one open issue.**
It is the largest single block in the funnel and it is our bug, not the
client's estate.

### 4b. Five-axis homogeneity, and what it costs

34 of the 207 carry all five axes. The axes that fail are persona (99 of 207
name one after `personas.classify` is re-run against live titles), vertical
(82 `UNKNOWN`) and region (80 `Other`).

**The fifth axis is honest rather than convenient.** `work/signals.jsonl` is
**zero bytes** - there is no first-party signal on anybody in this store - so
every candidate's signal state is `COLD`. The cohorts are homogeneous on that
axis by measurement, not by selection, and the tag says `COLD` rather than
implying a signal nobody has.

**And homogeneity alone produced an account blast.** The first two cells this
lane built held **eight people at one domain and six at another**: the
fully-tagged residue of this store is a handful of large companies with many
contacts each. Five-axis cohorting does not protect an account - the account
cap does, and it is now applied inside the plan builder.

---

## 5. The cohorts and their seat plan

Homogeneous on all five axes, one campaign per seat so the lead-to-seat
binding stays sticky (a multi-seat campaign hands rotation to the provider),
the campaign name carries every tag, and every lead has been through the four
provider gates, the account cap, the account gate, the suppression roster and
the provider's own lead-shape validator.

| cohort | geo | industry group | band | persona | signal | seat | leads | campaign name |
|---|---|---|---|---|---|---|---|---|
| **P-1** | UK | Performance Marketing Agency | 1000_PLUS | economic_buyer | COLD | 116968 | **2** | `RP-UK-PERF-1000_PLUS-BUY-CLD-S116968-D1` |
| P-2 | UK | Creative / Branding Agency | 200_499 | economic_buyer | COLD | 116973 | 0 (account `hold`) | `RP-UK-CREA-200_499-BUY-CLD-S116973-D1` |
| P-3 | UK | Performance Marketing Agency | 10_19 | champion | COLD | 116988 | 0 (account `stop`) | `RP-UK-PERF-10_19-CHM-CLD-S116988-D1` |
| P-4 | DACH | Performance Marketing Agency | 100_199 | champion | COLD | 116989 | 0 (account `stop`) | `RP-DACH-PERF-100_199-CHM-CLD-S116989-D1` |
| P-5 | US East | Performance Marketing Agency | 200_499 | economic_buyer | COLD | 119588 | 0 (account `hold`) | `RP-USEAST-PERF-200_499-BUY-CLD-S119588-D1` |

**P-1 is the only cohort with leads, and it is two people on one seat.**
Against a seat whose own configured limit is 40 and a licensed rate of 10.

The names are 35-41 characters. `cohort_name` **raises** rather than trimming
at the provider's 50-character ceiling: the first build spelled the verticals
out, two names came back cut at exactly 50 - losing the `-D1` day suffix -
and on a provider with no campaign delete, a colliding name is unrecoverable.

### Schedule: seven days, 07:00-23:00

```
dailyStartTime 07:00   dailyEndTime 23:00   timeZoneId <cohort timezone>
enabledMonday .. enabledSunday all true
```

**It can only be set at creation.** `heyreach.set_schedule` is refused by
this repository because no route on the API reads a schedule back, and
`/campaign/Create` takes the same object. A campaign created without it
inherits the provider's Mon-Fri 09:00-17:00 UTC default - a window nobody
chose. Two consequences:

* the existing 33 campaigns' windows **cannot be verified from the provider
  at all**, by this lane or any other. TASK-297's
  `schedule_07_to_23_seat_local_seven_days` check cannot be satisfied by a
  provider read; it can only be satisfied at the next create.
* **"seat-local" is not resolvable from provider truth** - a seat row carries
  no timezone field. The plan names the **cohort's** timezone
  (prospect-local), `Europe/London` for P-1. If the operator means the seat's
  own local time, that value has to come from the roster attestation.

### How the foreground executes P-1, and where it must stop

| step | verb | permission | state today |
|---|---|---|---|
| 1 | `heyreach.create_list(name)` | `LINKEDIN_CREATE_LIST` | SUPPORTED, unconditional - an empty list is inert |
| 2 | `liststaging.assert_list_safe(list_id)` then `heyreach.add_leads_to_list` | `LINKEDIN_ADD_LEAD_TO_LIST` | SUPPORTED, conditional on the list being unbound - read at the moment of the write |
| 3 | `heyreach.create_campaign(name, list_id, [116968], schedule=..., sequence=...)` | `LINKEDIN_CREATE_CAMPAIGN` | SUPPORTED. One-way: binding the list ends its staging safety property |
| 4 | `heyreach.activate_campaign(id, expect_leads=2)` | `LINKEDIN_ACTIVATE` | **REFUSED.** `_is_the_authorized_linkedin_canary` admits HeyReach campaign **604869 and nothing else** |

**So P-1 can be staged to DRAFT today and cannot be made to send.** Making it
send needs an operator grant that names the new campaign id and the exposure
(2 people, one seat), in the same shape as the 2026-09-16 grant for 604869.
Nobody should discover that at step 4.

The adjacent shortcut is closed too, and correctly: adding the two leads to
the seat's existing IN_PROGRESS campaign would both break cohort homogeneity
and be refused by `LINKEDIN_ADD_LEAD`, whose condition demands a provider
read proving the destination cannot send - and only DRAFT proves that.

### Expected readback, per campaign

* `campaign_read(id).status` == `DRAFT` immediately after create, holding
  exactly `[seat_id]` and the list id asked for;
* `list_leads(list_id)` count == the staged count. HeyReach answers 200 with
  `addedLeadsCount: 0` for a lead missing firstName or lastName - a 200 is
  not a staged lead;
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
| "in no email campaign" from our store | never asked the store; E1/E2 are provider reads. 23 candidates the store called clean were in client campaigns |
| a partial campaign enumeration | the full 200-502 range walked with cursor pagination, on disk |
| an empty LinkedIn field read as no LinkedIn activity | H1 asks the provider per profile; 17 were already enrolled and one was in thirteen campaigns |
| a seat's capacity assumed | `/li_account/GetAll` read per seat; 25 is contradicted for 7 of 33, and the shared-seat rule caps the rate at 10 |
| `unverifiable` counted as a pass | it excludes: 30 H1 404s and 17 M1 no-company cases were dropped, not admitted |
| a cohort built in a worktree with an empty `work/` | this worktree's `work/` is empty; every store read is against the PRODUCTION checkout by absolute path, and `scripts/laneP/boot.py` takes that path from `RESONATE_PROD_ROOT` |
| a person-level check standing in for the account question | `collision.check_account` per account; it removed 69 of 74 |
| a redaction guard that agrees with itself | the first one flagged `.gitignore` and `AGENTS.md` - it tested four-letter name tokens. The second tests full names, whole addresses, dotted domains, multi-word company names and hyphenated slugs, and REPORTS the 521 single-word company names it cannot test rather than counting them clean |

## 7. What the operator has to decide

1. **The rate.** 10/seat is what a shared seat licenses. 25 needs a ruling
   that the client's usage on a shared seat may be ignored - and even then
   the estate's configuration only supports 779, not 825.
2. **ISSUE-035.** 44 of the 74 survivors are held because our own stop looks
   like an account that ended early. Three accounts, one bug, three in five
   of everything this lane found - the cheapest people in the estate.
3. **Supply.** 74 survivors at 12 accounts is not a sourcing pipeline. The
   2026-09-18 finding stands: expansion is a sourcing problem.
4. **Activation.** `LINKEDIN_ACTIVATE` admits campaign 604869 and nothing
   else. P-1 stages to DRAFT without a decision; it sends only with a grant
   naming the new campaign id and the exposure.
5. **"Seat-local".** Unanswerable from the provider; name the source.

## 8. Request volume

| read | requests |
|---|---|
| EmailBison campaign enumeration | 3 |
| EmailBison search-contract and coverage probes | 16 |
| HeyReach seats | 1 |
| HeyReach campaigns (120, paged at 10 - the route times out at 100) | 12 |
| the four gates over all 207 candidates | 680 (359 EmailBison, 321 HeyReach) |
| `collision.check_account` over 12 accounts, twice (plan + ceiling) | ~40 |

Roughly 750 reads, against the 5,079 a lane ran this morning. Two provider
quirks worth carrying forward: `/campaign/GetAll` **times out at `limit=100`**
and answers in about four seconds at `limit=10`; and EmailBison's
`/leads?search=` is an index that lags creation, so a lead enrolled minutes
ago is exactly the lead it cannot see.

## 9. What this lane did NOT do

* No provider write of any kind - no list, no campaign, no lead.
* No claim about the 33 live campaigns' sending windows: unreadable by
  construction.
* No claim that the agency do-not-contact index cleared anybody:
  `work/agency-dnc.jsonl` **does not exist**, so `agencydnc.load()` returned
  an empty index and that gate watched nothing. It is reported as vacuous
  rather than as a pass.
