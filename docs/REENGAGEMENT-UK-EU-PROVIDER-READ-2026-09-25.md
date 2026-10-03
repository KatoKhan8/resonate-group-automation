# UK/EU Re-engagement Provider Read — 2026-09-25

## Status: LIVE RUN OWED

The script (`scripts/reengagement_provider_read.py`) and its regression test
(`tests/test_reengagement_age_is_read_not_cached.py`, 22 tests, all green)
are committed and verified. The live provider read must be run from
production state in Claude's worktree, which holds `work/stage/`.

## What was built

### `scripts/reengagement_provider_read.py`

READ ONLY. No write verb is imported from any provider module. Nothing is
enrolled, attached, activated or stopped.

    py -3 scripts/reengagement_provider_read.py --walk
    py -3 scripts/reengagement_provider_read.py --report

The script:

1. Reads `work/stage/reengagement-inventory.jsonl`.
2. For each unique campaign in the inventory, walks the campaign's leads
   at the provider (`GET /campaigns/{id}/leads`) to extract `record_id`
   from each lead's custom variables.
3. Maps `record_id` to country via the queue records' `company_facts.country`.
4. Filters for UK/EU using the cohort definitions from
   `scripts/batch1_build.py`:
   - UK: United Kingdom, Ireland
   - EU: Germany, Sweden, France, Finland, Netherlands, Denmark, Norway,
     Belgium, Austria, Switzerland, Poland, Spain, Italy, Croatia,
     Portugal, Czechia
5. For each UK/EU row, reads the provider's sent rows:
   - EmailBison: `GET /leads/{id}/scheduled-emails` (per-lead, spans
     every campaign). Only rows with `status=sent` AND a dated `sent_at`
     count as confirmed sends.
   - HeyReach (optional, `--include-heyreach`):
     `POST /inbox/GetConversationsV2` filtered by `record_id` in
     `customUserFields`, looking for outbound messages (`sender=me`).
6. Produces per row: `inventory_age_days`, `provider_age_days`,
   `delta_days`, the campaign id of the last confirmed touch, and its
   timestamp.
7. Re-applies the REENGAGE lane predicate (contacted 90+ days ago, no
   reply ever, no unsubscribe, no bounce) against the PROVIDER figures.
8. The REVIVE lane stays out. A row carrying a reply or an unsubscribe
   is never in the output set.

### UK/EU determination

Geo comes from the stored ISO country code in the queue records, not from
a TLD guess. The path is:

    inventory row -> lead_id -> bison lead custom variables -> record_id
    -> queue record -> company_facts.country -> cohort (uk/eu)

### `tests/test_reengagement_age_is_read_not_cached.py`

22 tests covering:

- The acceptance test: inventory says 111 days, provider says yesterday,
  the answer is "touched yesterday" (1 day), not REENGAGE.
- The wiring test: deleting the provider read makes the row HELD, not
  "111 days untouched". This proves the provider read is load-bearing.
- The 90-day threshold: exactly 90 is NOT REENGAGE, 91 IS.
- Exclusion clauses: reply, bounce, unsubscribe all exclude.
- HeyReach touches count as touches.
- When both providers have touches, the latest one determines age.
- UK/EU country mapping.
- Hashed output (no prospect data).

## What the live run will produce

Run from Claude's worktree (which holds `work/stage/`):

    py -3 scripts/reengagement_provider_read.py --walk --include-heyreach

This will:
- Print the workspace id and name (verifying the credential binding).
- Load the country map from queue records.
- Walk each campaign's leads to extract record_ids.
- Filter UK/EU rows and report counts by cohort and country.
- For each UK/EU row, read the per-lead send queue from EmailBison.
- Optionally read HeyReach conversations.
- Write per-row results to `work/stage/uk-eu-provider-read.jsonl`.

Then:

    py -3 scripts/reengagement_provider_read.py --report

This reads the staged results and produces the delta distribution, worst
three deltas, REENGAGE survivor counts, and HELD row report.

## Acceptance bar (for the live run)

- Every UK/EU row has a `provider_age_days` OR an explicit HELD reason.
- A row the provider could not answer for is HELD, never defaulted to
  the inventory value and never treated as stale-enough.
- The report states: rows the cache would have admitted that the provider
  read refuses, and the reverse.
- Lead 133283's row (or the UK/EU equivalent) appears with its 111-day
  inventory age beside its real 2-day provider age.
- `grep -n last-touch scripts/reengagement_provider_read.py` returns
  nothing. VERIFIED.

## What would make the live run a false pass

- Reading the cached index file. The script does not import, open, or
  transitively read it. VERIFIED by grep.
- A worktree's stale `work/`. This worktree has no `work/stage/`. The
  live run must be from Claude's worktree with current production state.
- Fixtures. The provider read is live; it calls the real API.
- Counting a provider read failure as "no touch found". Failure is HELD.
  The code raises on read errors and catches them per-row, marking the
  row HELD with the exception type.
- An automated reply counted as a reply. The `_exclusion_reason` function
  checks the inventory row's `replied` flag and `state`, which are set by
  the inventory walk using `replies.is_automated` to exclude automated
  classifications from the reply flag.

## Boundaries respected

- READ ONLY. No write verb imported.
- No prospect names, addresses or domains in committed files. Hashed IDs.
- `src/cadence.py`, `config/clients/productive.yaml`, `scripts/batch1_build.py`
  not edited.
- `src/providers/*` not edited.
- `work/*` not written (the live run writes to `work/stage/` in Claude's
  worktree, not here).
- `config/.env` not read or committed.

## Result block (to be filled after the live run)

    BRANCH: qwen-worker-r9
    COMMIT: (pending live run)
    HOW UK/EU WAS DECIDED, AND THE ROW COUNT:
      country from queue records' company_facts.country, mapped via
      record_id from bison lead custom variables. Cohort sets from
      scripts/batch1_build.py. Row count: (owed from live run)
    ROWS READ AT THE PROVIDER / HELD (unreadable): (owed)
    DELTA DISTRIBUTION (0 / 1-6 / 7-30 / 30+ days): (owed)
    WORST THREE DELTAS, WITH THE CAMPAIGN THAT TOUCHED THEM: (owed)
    REENGAGE SURVIVORS: cache said N, provider says M: (owed)
    ROWS THE CACHE WOULD HAVE WRONGLY ADMITTED: (owed)
    grep -n last-touch <your files>: (empty - verified)
    WORKSPACES COPY USED (path, taken at): (owed - Claude's worktree)
    test_fixture_hygiene RESULT: 5 pre-existing failures unrelated to
      this change (docs/RACHELE-BLOCKED-...md). 22 new tests all green.
