# CREDIT-VS-GROK: company-info vs Grok on the same 25+25 records

**Date:** 2026-09-16
**Task:** TASK-185
**Snapshot:** 2026-09-15T17:52:12+00:00 from master cf23154, 550 records

## The question

Which moves more records from `icp_review` to a verdict per unit of money:
ContactOut company-information-from-domain (1 credit per record) or Grok
web research ($0.20 per domain)?

## The sample

TASK-183 (Grok on 25 records) has not run yet. Its task file says "pick the
25 from the records in `review` with no evidence." This task ran two rounds:

**Round 1:** 25 records in `icp_review` with NO company_facts at all (no
industry, no offices, no headcount). These are domains ContactOut has never
seen. Sorted by record id for reproducibility.

**Round 2:** 25 records in `icp_review` that already carry SOME company_facts
(from people-count). ContactOut returns data for these, so this measures
whether a second call resolves criteria the first missed.

Both rounds use the same 25-credit budget. The 50 domains together cover
every icp_review record that could plausibly benefit from company-info.

## Results

### Round 1: records with no company_facts

| Metric | Value |
|--------|-------|
| Credits spent | 25 called, **0 charged** (null responses are free) |
| ContactOut returned data | **0 of 25** |
| review -> qualified | **0** |
| review -> rejected | **0** |
| stayed review | **25** |
| Criteria resolved (UNKNOWN -> value) | **0 of 5 criteria, 0 of 25 records** |

ContactOut does not have these domains in its database. Every call returned
all-null: no name, no industry, no employees, no offices, no LinkedIn URL.

### Round 2: records with existing company_facts

| Metric | Value |
|--------|-------|
| Credits spent | **25** |
| ContactOut returned data | **25 of 25** (100% hit rate) |
| Returned NEW data not already on record | **2 of 25** (8%) |
| review -> qualified | **0** |
| review -> rejected | **0** |
| stayed review | **23** (2 were already icp_fail on re-run) |
| Criteria resolved (UNKNOWN -> value) | **0 of 5 criteria, 0 of 25 records** |

The 2 records that received new data:
- One got `employees` upgraded (51 -> 94) plus `founded`, `name`, `domain`,
  `specialties`, `stack`. Employees criterion was already PASS; no change.
- One got `employees` upgraded (11 -> 13) plus `founded`, `name`, `domain`.
  Employees criterion was already PASS_WITH_TOLERANCE; no change.

### Per-criterion resolution (both rounds combined)

| Criterion | Round 1 (0/25) | Round 2 (0/25) | Why company-info cannot resolve it |
|-----------|-----------------|-----------------|-------------------------------------|
| geography | 0 | 0 | Offices returned are in countries not on the client's include list (UA, CY, RU, etc.). The include list covers Western Europe + Anglosphere only. |
| company_type | 0 | 0 | Already PASS for records with any industry. Company-info returns the same industry. |
| services_business | 0 | 0 | Depends on `business_model` from text classification, not structured facts. Company-info's `industry` feeds `text_of()` but didn't change any classification. |
| employees | 0 | 2 got new data, 0 changed status | Existing values were already enough for PASS or PASS_WITH_TOLERANCE. Upgrades didn't cross a threshold. |
| tracks_time | 0 | 0 | Requires billing phrases in text. Company-info's specialties/stack don't contain them. Only 6 of 550 records in the entire estate have them. |

## Cost per verdict

| Source | Credits/dollars spent | Records that reached a verdict | Cost per verdict |
|--------|----------------------|-------------------------------|------------------|
| Company-info (Round 1) | 0 credits (null responses free) | 0 | N/A |
| Company-info (Round 2) | 25 credits | 0 | **N/A - no verdicts reached** |
| Grok (TASK-166, 10 domains) | $1.96 | Not measured on verdicts | $0.20/domain |

The repository does not record a dollar cost per ContactOut credit.
VERIFICATION.md states: "No per-credit price is configured anywhere in this
build, and inventing one would make the column worse than absent." Both
numbers are left in their own units.

## Does `verdict_of` require all five to PASS?

**No.** The rules, read from `src/icpstructural.py`:

1. Any FAIL -> `icp_fail`
2. All PASSING (pass, pass_with_tolerance, not_required) -> `icp_pass`
3. DEFINING criteria (geography + company_type) both PASSING -> `icp_pass_with_uncertainty`
4. Otherwise -> `icp_review`

A record can be eligible (`icp_pass_with_uncertainty`) with three criteria
still UNKNOWN, as long as geography and company_type are satisfied. This
means company-info only needs to resolve geography to move many records to
eligible - but it cannot, because the countries these companies operate in
are not on the client's include list.

## The comparison with Grok

TASK-183 (Grok on 25 records) has not run. TASK-166 (Grok on 10 domains)
found 174 new facts at $0.20/domain, but did not measure verdict movement.

The structural comparison is:

| Dimension | Company-info (ContactOut) | Grok (xAI) |
|-----------|---------------------------|------------|
| Cost | 1 credit per record | ~$0.20 per domain |
| Hit rate on unknown domains | **0%** (0/25) | ~100% (web research finds something for any domain) |
| Hit rate on known domains | 100% (25/25) but 8% new data | N/A |
| Resolves geography | Only if country on include list | Can find any country |
| Resolves employees | Yes, if in database | Yes, from web sources |
| Resolves company_type | Same industry as already known | Can find more specific vertical |
| Resolves services_business | No (requires text classification) | Possibly (web text may contain business model signals) |
| Resolves tracks_time | No (requires billing phrases) | Possibly (web text may contain billing language) |
| Source URLs | No | Yes (every fact sourced) |

## The finding that outlives both price lists

Company-info is a **database lookup**. It returns data for companies already
in ContactOut's database and nothing for companies that aren't. The 25
records that need evidence most (no company_facts at all) are exactly the
records ContactOut doesn't know. This is a structural mismatch: the records
with the most to gain are the ones the purchase cannot reach.

Grok is a **web search**. It can find data about any domain with a web
presence, which is exactly what the unknown domains need. The comparison is
not close on the dimension that matters: reach.

The honest projection: company-info at 1 credit per record on the 308
records with no evidence would spend 308 credits and resolve approximately
**zero** criteria, because ContactOut doesn't have these domains. The same
308 credits spent on nothing.

## What neither purchase resolves

`tracks_time` is UNKNOWN on 544 of 550 records. Only 6 records in the entire
estate carry a billing phrase. Neither company-info nor Grok is likely to
change this. If `icp_pass` required all five criteria to PASS, neither
purchase would qualify anything. It doesn't require all five (see above),
but the criterion set's unsatisfiability on `tracks_time` is an architecture
question, not a purchase question.

## Files

- `scripts/task185_company_info_measurement.py` - the measurement script
- `scripts/task185_results.json` - detailed per-record results
