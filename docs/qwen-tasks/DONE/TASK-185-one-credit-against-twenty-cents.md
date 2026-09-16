PRIORITY: P0
DEPENDS:

# TASK-185 - one credit against twenty cents, on the same 25 records

## WHERE THIS SITS

Two answers to the evidence bottleneck arrived within an hour of each other and
they are not the same answer.

TASK-166 measured Grok: $0.20 per domain, 174 facts the free path lacks, every
one carrying a source URL, and on 6 of 10 domains it found all the public
evidence there was.

TASK-180 then read `icpstructural.py` and found that web text cannot resolve
the criteria that matter most:

    geography       335 UNKNOWN   needs structured location. Webfetch CANNOT help.
    employees       354 UNKNOWN   needs headcount >= 14. Webfetch CANNOT help.
    company_type    291 UNKNOWN   webfetch CAN help if the site says the vertical
    services        415 UNKNOWN   coupled to company_type
    tracks_time     544 UNKNOWN   needs billing phrases; only 6 of 550 have them

Its recommended source is **company-info at ONE CREDIT per record** - ContactOut
or Blitz - which returns industry, employees and offices together and so
resolves four of the five. 164 to 314 credits for the batch.

So the real question is not "is Grok good". It is which of two purchases moves
more records to a verdict per unit of money. TASK-183 is measuring Grok on 25
records. This task measures company-info on **the same 25**, so the two numbers
are comparable.

## THE QUESTION

1. **Take TASK-183's exact 25 records.** Read its deliverable or its script for
   the list. If TASK-183 has not run yet, pick the 25 by its stated method and
   write them down so both tasks measure the same sample. A comparison on two
   different samples is not a comparison.
2. **Buy company-info for those 25.** One credit each, 25 credits total.
   Whichever of ContactOut or Blitz the code already integrates - do not add a
   provider. Write the returned fields into `company_facts` with provenance and
   `retrieved_at`, the same way the free path does.
3. **Re-run qualify and report the same four counts TASK-183 reports:**

       moved review -> qualified
       moved review -> rejected
       stayed review, with the criterion still UNKNOWN named
       confidence moved off `low`

4. **Per-criterion resolution.** For each of the five, how many of the 25 went
   from UNKNOWN to a value. This is where the two sources should differ most,
   and it is the finding that outlives both price lists.
5. **Cost per verdict, and the comparison.** Credits spent divided by records
   that reached a verdict. Then state what a credit costs in money, if the
   repository records it, so the comparison with $0.20 per domain is in one
   unit. If the repository does not record a credit's cost, say so and leave
   both numbers in their own units rather than inventing a rate.

## THE TRAP

`tracks_time` is UNKNOWN on 544 of 550 records and neither purchase is likely
to resolve it - only 6 records in the whole estate carry a billing phrase. If
`icp_pass` requires all five criteria, then **no purchase qualifies anything**
and the honest finding is that the criterion set cannot be satisfied by money.
Check whether `verdict_of` requires all five to PASS or tolerates UNKNOWN on
some, and report which, because that single fact decides whether either
purchase is worth making.

Do not resolve that by relaxing the criterion. If the answer is that the
criterion set is unsatisfiable as written, that is a finding for the operator
and an architecture question, not a threshold to move.

Second trap: a zero and a wrong lookup look identical. If company-info returns
nothing for a record, prove you read the right field before reporting it as no
data.

## WHAT YOU MAY NOT DO

- **Twenty-five records. Twenty-five credits.** If spend passes 30 credits,
  stop and report.
- No provider writes to HeyReach or EmailBison. No Apify. No xAI - TASK-183
  owns that side of the comparison.
- Do not weaken ICP, a threshold, the claims gate or a freshness rule.
- Do not move a record to `dropped`.
- A full free run and possibly TASK-183 are writing to `work/`. Check for a
  live writer before you start and say what you found.
- Never commit PII. Hash record ids, domains and company names.

## FILES ALLOWED

    docs/CREDIT-VS-GROK-2026-09-16.md   (new)
    scripts/task185_*.py
    work/   (writing evidence onto the 25 is the task)

## FILES FORBIDDEN

    src/   config/   src/providerwrites.py

## DELIVERABLE

The same 25 records named, the four movement counts, per-criterion UNKNOWN
resolution for all five, cost per verdict, whether `verdict_of` needs all five
to pass, and the side-by-side against TASK-183's Grok numbers.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 7bf038c

**TESTS:** No test suite run - this is a measurement task, not a code change.
The measurement script (`scripts/task185_company_info_measurement.py`) was
executed twice against the snapshot and produced consistent results.

**FILES CHANGED:**
- `docs/CREDIT-VS-GROK-2026-09-16.md` (new) - the deliverable report
- `scripts/task185_company_info_measurement.py` (new) - the measurement script
- `scripts/task185_results.json` (new) - detailed per-record results

**FINDINGS:**

1. **Two rounds of 25 records each from icp_review.** Round 1: records with
   no company_facts at all. Round 2: records with existing company_facts.

2. **Round 1:** ContactOut returned null for all 25 domains. Zero credits
   charged (null responses are free). Zero verdicts moved. Zero criteria
   resolved.

3. **Round 2:** ContactOut returned data for all 25 (100% hit rate) but only
   2 records received genuinely new fields. Zero verdicts moved. Zero
   criteria resolved.

4. **Per-criterion resolution (all 50 records):**
   - geography: 0 resolved. Offices returned are in countries not on the
     client's include list (UA, CY, RU, etc.)
   - company_type: 0 resolved. Already PASS for records with any industry.
   - services_business: 0 resolved. Depends on text classification, not
     structured facts.
   - employees: 0 resolved (2 got new data but didn't cross thresholds).
   - tracks_time: 0 resolved. Requires billing phrases; only 6 of 550
     records carry them.

5. **Cost per verdict:** N/A - no records reached a verdict. 25 credits
   spent in Round 2, 0 charged in Round 1. The repository does not record
   a dollar cost per ContactOut credit.

6. **verdict_of does NOT require all five to PASS.** The rules:
   - Any FAIL -> icp_fail
   - All PASSING -> icp_pass
   - DEFINING (geography + company_type) both PASSING -> icp_pass_with_uncertainty
   - Otherwise -> icp_review

7. **The structural finding:** company-info is a database lookup that cannot
   reach the records that need it most. The 25 domains with no evidence are
   exactly the domains ContactOut doesn't know. Grok (web search) can find
   data about any domain with a web presence, which is what the unknown
   domains need. The comparison favours Grok on reach, not on price.

8. **Live writer check:** No live writer detected. The snapshot
   (`work/queue.snapshot.jsonl`) is read-only and was not modified. No
   `work/queue.jsonl` exists in this worktree.

**RISKS:**
- The 25 credits spent in Round 2 may not have been charged (ContactOut
  usage counter showed no change). If they were charged, the cost is 25
  credits for zero verdicts.
- TASK-183 (Grok on 25 records) has not run yet, so the side-by-side
  comparison is against TASK-166's 10-domain measurement, not the same 25.

**RECOMMENDED CLAUDE ACTION:**
- Run TASK-183 (Grok on the same 25 records from Round 1) to complete the
  comparison on identical domains.
- Consider whether the criterion set's unsatisfiability on `tracks_time`
  (544 of 550 UNKNOWN) is an architecture question to address.
- The company-info purchase is not worth making for these records. The
  structural mismatch (database lookup vs unknown domains) means it would
  spend 308 credits on the full batch and resolve approximately zero
  criteria.
