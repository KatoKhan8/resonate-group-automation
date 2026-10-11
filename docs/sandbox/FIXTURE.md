# The synthetic sandbox fixture

Entirely invented data for the 60-day sandbox simulation. Nothing in here was
fetched, enriched or verified. **Zero data credits were spent**, no provider
was called and no socket was opened.

    py -3 scripts/sandbox_fixture.py --seed 1 --out docs/sandbox/fixture-seed-1.json
    py -3 scripts/sandbox_fixture.py --seed 2 --out docs/sandbox/fixture-seed-2.json
    py -3 -m unittest tests.test_sandbox_fixture -v

| artefact | path |
| --- | --- |
| generator | `scripts/sandbox_fixture.py` |
| seed 1 | `docs/sandbox/fixture-seed-1.json` |
| seed 2 | `docs/sandbox/fixture-seed-2.json` |
| tests | `tests/test_sandbox_fixture.py` |

---

## The cohort partition, designed before any record existed

A cohort carries **one** geo, **one** industry, **one** headcount band,
**one** signal and **one** persona, and **no cohort may hold fewer than 50
records**. Those rules do not merely describe the output; they determine it,
so the partition was fixed first and the data generated into it.

### Two blocks

A *block* is a set of companies homogeneous in geo, industry, headcount band
and signal. Crossing a block with its three personas gives the cohorts.
Because every company in a block carries the same three personas, the cohort
sizes come out exactly equal: 50 companies, one record per persona.

| block | geo | industry | headcount band | signal | companies |
| --- | --- | --- | --- | --- | --- |
| A | United Kingdom | Marketing & Advertising | 20-49 | `public_timesheet_rollout` | 50 |
| B | United States | Software Development | 50-99 | `headcount_growth_over_20pct` | 50 |

### Six cohorts of exactly 50

| cohort key | block | geo | industry | band | signal | persona | family | records |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `united-kingdom-operations-manager` | A | United Kingdom | Marketing & Advertising | 20-49 | `public_timesheet_rollout` | Operations Manager | champion | **50** |
| `united-kingdom-finance-manager` | A | United Kingdom | Marketing & Advertising | 20-49 | `public_timesheet_rollout` | Finance Manager | champion | **50** |
| `united-kingdom-cfo` | A | United Kingdom | Marketing & Advertising | 20-49 | `public_timesheet_rollout` | CFO | economic_buyer | **50** |
| `united-states-operations-director` | B | United States | Software Development | 50-99 | `headcount_growth_over_20pct` | Operations Director | champion | **50** |
| `united-states-project-manager` | B | United States | Software Development | 50-99 | `headcount_growth_over_20pct` | Project Manager | champion | **50** |
| `united-states-coo` | B | United States | Software Development | 50-99 | `headcount_growth_over_20pct` | COO | economic_buyer | **50** |
| | | | | | | | **total** | **300** |

---

## Why two geographies and not four

The brief named the UK, Western Europe, Australia and the US. At n = 300 that
is **not satisfiable** alongside the other two rules, and the arithmetic is
short:

1. A cohort carries one persona.
2. The three decision makers inside a company have **distinct** personas, so
   one company's three records necessarily land in three **different**
   cohorts.
3. Therefore a geography's records occupy **at least three** cohorts.
4. With a floor of 50 per cohort, a geography carries **at least 150**
   records.
5. `300 / 150 = 2`.

**Two is the hard ceiling on the number of geographies at this n.** Four
geographies needs n ≥ 600. The partition takes the two largest ICP regions and
says so here, rather than shipping twelve cohorts of 25 that would fail the
homogeneity floor the brief asked for. Raising n to 600 — or lowering the
cohort floor — is the operator's call; both are one constant in
`scripts/sandbox_fixture.py`.

## Why exactly three decision makers per company

The first brief said "2 to 3"; the operator's correction of 2026-10-12 made it
an equality. These were always the same requirement:

    x companies with 2 + y companies with 3
    x + y = 100   and   2x + 3y = 300    =>    y = 100, x = 0

The test asserts `== 3`, not `2 <= n <= 3`, so a company that loses a contact
fails instead of degrading quietly into the old tolerance.

---

## Distribution

**Records 300 · companies 100 · contacts per company exactly 3 · cohorts 6**

| geo | records | companies |
| --- | --- | --- |
| United Kingdom | 150 | 50 |
| United States | 150 | 50 |

| persona | family | records |
| --- | --- | --- |
| Operations Manager | champion | 50 |
| Operations Director | champion | 50 |
| Project Manager | champion | 50 |
| Finance Manager | champion | 50 |
| CFO | economic_buyer | 50 |
| COO | economic_buyer | 50 |

| persona family | records |
| --- | --- |
| champion | 200 |
| economic_buyer | 100 |

| headcount band | employees | records | companies |
| --- | --- | --- | --- |
| 20-49 | 20-49, uniform per company | 150 | 50 |
| 50-99 | 50-99, uniform per company | 150 | 50 |

| industry | records |
| --- | --- |
| Marketing & Advertising | 150 |
| Software Development | 150 |

All four **champion** personas the brief named are present. Of the five
economic-buyer personas named (CFO, COO, CEO, Owner, Founder) only **two** fit
— one persona per cohort at a 50-record floor allows six personas in total,
and four of those six are spent on the champions. CEO, Owner and Founder need
additional cohorts, i.e. a larger n.

Every persona title is **read from
`config/clients/productive.yaml`** at generation time and the generator raises
if one is not in the client's own list — `personas.classify` matches titles
against exactly that list, so an invented title would be set aside as "not a
persona for this client" and the cohort would be empty in practice while
looking full in the JSON.

### ICP fit

Services businesses that track time, marketing and software agencies, 20+
employees, UK and US. `market.size_min_employees` for this client is 20 and
both bands clear it. Every company's research states that it bills clients
against tracked time, which is the client's `must` criterion.

---

## The simulation window

60 days, anchored at a **fixed** date — never `date.today()`, because a
fixture whose bytes move at midnight is not reproducible.

| | |
| --- | --- |
| start | 2026-10-12 |
| end | 2026-12-10 |
| days | 60 |
| research published | 1-365 days **before** the window starts |

Research is dated before the start because a fact dated inside the horizon is
a fact the run had not yet been able to read.

---

## Record shape — the real one

The fixture is fed to the **existing production flow**, so no field name in it
was invented. `fixture["queue_records"]` is the pipeline input: 100 rows, one
per company, each with 3 contacts.

* **Record**: skeleton from `store.new_record()`, plus `batch`, `stages`,
  `events`, `waterfall`, `qualification`, `research` and `cadence_steps` — 24
  keys (the 23 of a live row, plus `cadence_steps`).
* **Contacts**: the 15 live contact keys plus `personalization` — 16.
  `key` is a **name slug** (`elspire-invenby`), which is the live queue's own
  shape.
* **`research`**: a **list** of `evidence.make()` objects, 18 scored fields
  each, 4 per company (one company-level, one per contact bound to that
  contact's key, persona and angle). 400 items, **all USABLE** and all
  **ADMITTED** by `packfacts.identity_of`. The strong/medium split is a
  function of the seeded publication dates — seed 1 is 105 `strong` / 295
  `medium`, seed 2 is 92 / 308 — and the test asserts *USABLE*, not a split.
* **`cadence_steps`**: `cadence.STEPS`, the real 7-step sequence, under
  `cadence.CADENCE_KEY`.
* **`contact["personalization"]["selected_evidence_ids"]`**: the contact's own
  fact plus the company fact.

### Present and empty, not invented

`stages`, `events`, `waterfall` and `qualification` are the pipeline's own
output — `events` and `waterfall` are specifically the **provider-call audit
trail**. They are present and empty. Filling them would be fabricating a run.

### Null because only a provider could know

| field | why |
| --- | --- |
| `mx` | a DNS lookup. There is no resolver here, and `.invalid` has no MX. |
| `reoon`, `verdict` | the **legacy** verifier fields. `verification.legacy_evidence` reads them, so a stored `verdict: "valid"` would be counted as a **third** confirmation nobody obtained — inflating the very policy under test. |
| `bison_lead_id` | issued by Bison on push. Nothing was pushed. |

Left `null` rather than omitted, so the key is present in the shape the flow
expects — and `null` rather than filled, because an invented value here is
indistinguishable downstream from a real one.

---

## Safety properties

| property | how it is guaranteed |
| --- | --- |
| no real domain | every company domain is `<slug>.invalid`. `.invalid` is reserved by RFC 6761 and can never be delegated. |
| no deliverable email | every address ends `.invalid`. **`example.com` is not permitted** (operator, 2026-10-12). |
| every record has a LinkedIn URL | the generator cannot emit one without it, and each URL **already equals** its own `linkedin.canonical()` form. |
| fake, unfetchable sources | every `source_url` is on the company's own `.invalid` site — same-site, so `packfacts.identity_of` returns ADMITTED, and unfetchable by anybody. |
| zero spend | the generator imports no provider and no network module; asserted from the AST. |

### The email path at zero credits

`verification.is_sendable` **recomputes** from an evidence list and never reads
a stored flag, so writing `sendable: true` does nothing. Each contact instead
carries two synthetic provider verdicts built with `verification.result(...)`,
each marked `reason="synthetic sandbox fixture"` and `charged=False`.

Productive's resolved policy — read from the client config, not restated — is
primary `deliverable`, secondary `reoon`, `required_confirmations` 2,
`trust_secondary_when_primary_unknown` false. Two independent `valid` verdicts
is exactly what it requires, giving `sendable: true`,
`confirmation_count: 2`, `confirmed_by: ["deliverable", "reoon"]`.

**The policy is modelled, not bypassed**, and two tests prove the requirement
bites: one confirmation alone returns `False`, and evidence recording a
different address returns `False` because evidence is address-bound.

### Names

Company and person names are coined — invented stems plus compound endings
(`Mockworth`, `Fixbury`, `Sandmoor`) that are not names anybody has — and
street names are invented so no full address is real. Name-level
non-existence cannot be *proven* without a network lookup, and a network
lookup is forbidden here; the reserved TLD is the part that **is** provable,
and the both-direction domain assertions below are what carry the guarantee.

---

## Invariants asserted by `tests/test_sandbox_fixture.py`

Every assertion is paired with a **positive control** that poisons a copy of
the fixture and proves the same checker reports the problem. The checkers are
module-level functions so the control runs the *same* code the assertion runs.

1. exactly 300 records, exactly 100 companies, unique ids and domains
2. every company has **exactly** 3 decision makers
3. the three are distinct **people** with distinct **personas**
4. every persona is one `config/clients/productive.yaml` declares
5. every record has a LinkedIn URL equal to its own `canonical()` form
6. every email ends `.invalid` and is `normalise_email`-canonical
7. six cohorts of exactly 50, none under the floor
8. every cohort homogeneous in geo, industry, band, signal and persona
9. the live record and contact shape; a **positional** contact key is caught
   even though `store.validate` accepts it
10. `cadence_steps` is a non-empty list under the right key
11. research items are `evidence.make()` objects that score USABLE and license
    through `packfacts.pack_for`
12. `selected_evidence_ids` resolves to evidence on the record
13. stored `sendable` equals the recomputation; 2 confirmations required
14. determinism: same seed byte-identical, **across processes**; different seed
    different people and domains; no wall clock in the bytes
15. the committed seed files match the generator
16. **both-direction domain safety**, each direction with its own control:
    * **(a)** no synthetic domain in production `work/queue.jsonl`,
      `work/campaigns.jsonl` or `config/suppress.local.txt`; and no synthetic
      **contact** on `work/agency-dnc.jsonl`, tested by fingerprint — see the
      finding below
    * **(b)** no real client domain — the 12 on the roster plus the client's
      own — anywhere in the fixture
17. production `work/` md5 **and mtime and size** unchanged across every test
18. the generator imports no provider and no network module

### Confidentiality: no customer name is written into a tracked file

`config/suppress.local.txt` is gitignored on purpose — *"who is paying us is
confidential, and a tracked file reaches every clone, every fork and every
backup of this repository"*. The direction-(b) controls therefore **read their
needle from that roster at runtime** and never spell one out. The single
exception is `productive.io`, the client's own domain, which is already
tracked in `config/clients/productive.yaml`. An earlier draft of the test
hardcoded a customer domain as a control needle; that would have published a
customer name, and it was removed.

### Finding: a domain scan of `work/agency-dnc.jsonl` cannot fail

The brief asked for "no synthetic domain appears in the real `work/queue.jsonl`,
`work/agency-dnc.jsonl` or `config/suppress.local.txt`". Two of those three
hold plaintext. **`work/agency-dnc.jsonl` does not.** It stores only

    sha256("email:<address>")      sha256("linkedin:<url>")

which is its deliberate privacy model — *"the file cannot be read to enumerate
anybody"*. All 15 rows are `{at, fingerprint, reason}` and there is not one
host, address or domain in the file.

So a scan of it for synthetic domains **can never match, whatever the data**:
it is a check incapable of failing. This surfaced because the control for it
failed on first run (`no host-like token in the DNC file`) instead of the
assertion passing quietly — which is the entire reason each assertion here
carries one.

It is replaced by the question that file can actually answer, and by a pinned
property:

* `test_no_synthetic_contact_is_on_the_agency_dnc` — hashes all 300 contacts
  through `agencydnc.keys_for` (the same function the live import uses) and
  intersects against the loaded index, asserting the index is non-empty first.
* `test_control_the_dnc_check_fires_on_a_fingerprinted_contact` — the control
  cannot plant a plaintext needle, since the hash is one-way, so it
  **fingerprints a synthetic contact into a copy** of the file in the temp
  directory and proves the matcher then finds it. The real file is never
  opened for writing.
* `test_the_agency_dnc_holds_no_plaintext_at_all` — pins the reason, and fails
  if the DNC ever starts storing plaintext, at which point it must go into
  `PLAINTEXT_STATE`.

The DNC file is still md5'd, mtimed and size-checked before and after every
test, like the other two.

### Why the production paths are resolved through `.git`

This module normally runs from a **linked worktree**, and a worktree has **no
`work/` at all** and no `config/suppress.local.txt` (gitignored). Measured
2026-10-12: all four were absent here. Every production assertion would have
been **vacuous** — the domain scan would have searched an empty string and
passed, and the before/after would have compared `None` to `None`.
`_production_root()` (from `tests/test_sandbox_phase1.py` at `963a7d64`)
resolves the **main checkout**, and `setUp` asserts each file is present
before using it.

Direction (a)'s control plants a domain **read out of the real queue at
runtime**, which proves both that the scanner finds what is there and that the
file it scanned had content in it.

### Isolation

`store.use_directory()` into a throwaway temp directory, with `queue_path()`
**and** `campaigns_path()` asserted to have both moved and the `CAMPAIGNS`
override asserted gone — a stale `CAMPAIGNS` would otherwise survive the
redirect and keep pointing at the real file.
