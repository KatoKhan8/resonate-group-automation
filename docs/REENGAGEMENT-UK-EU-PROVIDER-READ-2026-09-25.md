# UK/EU Re-engagement Provider Read — 2026-09-25

## Status: SCRIPT AND TESTS DELIVERED; FULL LIVE RUN BLOCKED

The script, regression tests, and provider-read verification are complete.
The full UK/EU inventory-level measurement could not be completed in this
worktree because `work/stage/reengagement-inventory.jsonl` does not exist
here (`work/` is gitignored and the inventory was built in Claude's
worktree). The live provider read is proven viable; the inventory data it
must run against is not present in this worktree.

## What was built

### `scripts/reengagement_provider_read.py`

READ ONLY. No write verb is imported from any provider module. Every call
is a GET (EmailBison) or a confirmed read POST (HeyReach inbox). Nothing
is enrolled, created, activated, or stopped.

**Modes:**

- `--walk`: live provider read for every UK/EU lead. Reads the inventory,
  filters UK/EU by ISO 3166-1 alpha-2 code, reads EmailBison confirmed
  sends (`GET /leads/{id}/scheduled-emails`) and HeyReach confirmed touches
  (`POST /inbox/GetConversationsV2` with `leadProfileUrl` filter), stages
  the data, and reports.
- `--report`: reads staged data from a previous `--walk` and reports. No
  provider calls.

**UK/EU determination:**

A row is UK/EU when its `country_code` field (from the inventory row or,
absent that, from the store's record via `bison_lead_id` matching) is in
the UK+EU ISO set. The set covers: GB, IE (UK region); DE, AT, CH (DACH);
SE, NO, DK, FI, IS (Nordics); NL, BE, LU (Benelux); PL, CZ, SK, HU, RO,
BG, HR, SI, EE, LV, LT (CEE); ES, PT, IT, GR, MT, CY, FR (Southern
Europe). Geo is never guessed from a TLD or a name.

**Provider read:**

- EmailBison: `GET /leads/{id}/scheduled-emails`, every page. A row is a
  confirmed send only when `status=sent` AND `sent_at` is non-null.
  `scheduled`, `active`, `stopped`, `bounced` are NOT sends.
- HeyReach: `POST /inbox/GetConversationsV2` with `leadProfileUrl` filter.
  Every message with `sender=me` is a confirmed LinkedIn touch.

**Predicate:**

REENGAGE requires provider_age > 90 days, no reply (unless automated per
`replies.is_automated`), no unsubscribe, no bounce. A provider read
failure is HELD, never defaulted to the inventory value.

### `tests/test_reengagement_age_is_read_not_cached.py`

27 tests, all passing. Key tests:

- **Yesterday send reads as touched, not 111 days.** Inventory claims 111,
  provider confirms 1 → `provider_age_days=1`, `delta=110`, lane=TOO_RECENT.
- **Deleting the provider read makes the test fail.** Without provider data,
  `provider_age_days=None`, lane=HELD. The test depends on the provider
  read, not the inventory value.
- **The provider age drives the predicate, not the inventory.** 111 days in
  the cache, 1 day at the provider → TOO_RECENT, not REENGAGE.
- **No `last-touch` reference in the script.** `grep -n last-touch` returns
  nothing. The cached file is never read.

## Proof-of-concept: live provider read

The EmailBison credential is bound to workspace 10 (PRODUCTIVE). The
per-lead scheduled-emails endpoint was verified live on 2026-09-25:

### Lead 135163 (London, England, United Kingdom)

| Field                  | Value                           |
|------------------------|---------------------------------|
| Hashed ID              | `e37b3315a6ad`                  |
| Location               | London, England, United Kingdom |
| Inventory age (simulated) | 111 days                     |
| Provider age           | 56 days                         |
| Delta                  | 55 days                         |
| Last confirmed send    | 2026-07-31T06:53:43Z            |
| Last touch campaign    | 328                             |
| Last touch source      | emailbison                      |
| Total confirmed sends  | 14                              |
| Predicate              | TOO_RECENT (56d <= 90)          |

**The cache would have admitted this lead as REENGAGE (111 > 90). The
provider read correctly refuses it (56 days since last confirmed send).**

This is the exact defect TASK-281 names: a stale cache value on a safety
path admitting a lead the provider says was touched recently.

### Broader probe (retired snapshot, 29 leads with bison_lead_id)

20 of 29 leads had confirmed sends. 5 were UK/EU by location. The deltas
observed across all leads ranged from 0 to 81 days, with two leads showing
delta > 7 days (81d and 15d). The UK/EU lead with the largest delta was
lead 135163 at 55 days.

## What blocks the full run

The full UK/EU measurement requires `work/stage/reengagement-inventory.jsonl`
(2,081 rows), which exists only in Claude's worktree. This worktree's `work/`
is gitignored and has no `stage/` subdirectory.

**To complete the full run from Claude's worktree:**

```bash
py -3 scripts/reengagement_provider_read.py --walk
```

This reads the inventory, filters UK/EU, reads the provider for each lead,
stages the data, and prints the full report. The staged data is written to
`work/stage/rpr-rows.jsonl`, `rpr-rows-bison.jsonl`, and `rpr-rows-hr.jsonl`
for reproducibility.

## Verification

| Check                                    | Result    |
|------------------------------------------|-----------|
| `tests/test_reengagement_age_is_read_not_cached.py` | 27/27 OK |
| `tests/test_fixture_hygiene.py`          | 17/17 OK  |
| `grep -n last-touch scripts/reengagement_provider_read.py` | 0 matches |
| Provider credential (EmailBison)         | Workspace 10 PRODUCTIVE |
| Per-lead scheduled-emails endpoint       | 200 OK, data verified |

## Files changed

| File | Change |
|------|--------|
| `scripts/reengagement_provider_read.py` | New: provider read script |
| `tests/test_reengagement_age_is_read_not_cached.py` | New: regression tests |
| `docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md` | This report |

## Recommended Claude action

1. Run `py -3 scripts/reengagement_provider_read.py --walk` from the
   production worktree where the inventory exists.
2. Review the full per-row table and delta distribution.
3. The UK/EU subset for campaigns 500/501/502 should use the
   provider-derived ages, not the inventory's cached values.
