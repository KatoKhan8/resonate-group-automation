PRIORITY: P1
DEPENDS:

# TASK-212 - ten ContactOut endpoints we do not call, and one we call nowhere

## WHERE THIS SITS

`PROVIDER-ROUTING-POLICY.md` says ContactOut is the primary provider whenever
CAPABLE, and warns in as many words: "Do not assume our current adapter
represents all ContactOut capabilities."

TASK-206 measured that. ContactOut documents **15 endpoints**; the adapter
implements **5** - people-count, people-search, decision-makers,
email-verifier, company-information-from-domain. Ten are not implemented. And
of the five, `people_search` has **no production caller** at all: defined in
the adapter, referenced in `validate.py`, called by neither `enrich` nor
`generate`, and absent from the waterfall. An adapter method with no caller
proves nothing, which is a defect this repository has a name for.

TASK-206 also mapped capability to requirement and found exactly two genuine
gaps:

    prose evidence      NO CONTACTOUT CAPABILITY   <- blocks check_evidence,
                                                      which blocks all copy
    job-change signal   NO CONTACTOUT CAPABILITY

Everything else - geography, company_type, employees, person discovery,
contact email - ContactOut can already answer.

Those two gaps are what licenses Grok under the policy. So this task decides
whether either is really a gap, or whether one of the ten unimplemented
endpoints closes it - because a gap that ContactOut can fill must be filled by
ContactOut.

## THE QUESTION

1. **List the ten, with what each returns and what it costs.** From the
   documentation and the integration, not from guesswork. Mark each "available
   to our plan/key" or "documented but unavailable to us" - TASK-206 was asked
   to keep those as separate columns and the distinction decides everything
   downstream.
2. **Does any of the ten close the prose-evidence gap?** `check_evidence` in
   `src/llm.py` needs a claim traceable to a research row - prose about the
   company, with a source. Read what the gate actually accepts (TASK-199
   specified it) and say, endpoint by endpoint, whether its return could
   satisfy it. A structured firmographic field cannot; a company description or
   a news-shaped field might.
3. **Does any close the job-change gap?** ContactOut is a people-data provider
   and job changes are its native territory, so this one is worth checking
   carefully.
4. **`people_search`: wire it or delete it.** Decide which, and argue it. If
   the waterfall has a stage it belongs in - `people_discovery` already starts
   at `people-count` then `decision-makers` - say where and what it would add
   over `decision-makers`. If it adds nothing, an orphan method is debt and
   should go.
5. **Recommend, do not implement.** For each endpoint worth adding: which
   waterfall stage, which position, primary or fallback, and what reason would
   license it. Wiring is a separate task; a recommendation that names the stage
   and the reason is what makes that task small.

## THE TRAP

Do not call an endpoint to see what it returns. Every ContactOut call costs
credits, and this repository's rule is that a paid call needs a reason before
it is made. This task reads documentation and code. If a question can only be
settled by a live call, say so and say what the call would cost - Claude
decides whether to spend it.

Second trap: "ContactOut first" is a product decision, not a cost argument, so
do not recommend against a ContactOut endpoint because Grok looks cheaper. The
order is settled. What is open is whether the capability exists.

## WHAT YOU MAY NOT DO

- No ContactOut calls. No paid provider calls of any kind.
- No provider writes.
- Do not change the adapter, the waterfall or a stage definition - this task
  recommends. TASK-207 and TASK-208 own that file and a third writer will
  collide.
- Do not delete `people_search` in this task even if you recommend deleting it.
- Never commit a key or PII.

## FILES ALLOWED

    docs/CONTACTOUT-UNUSED-2026-09-16.md   (new)
    scripts/task212_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The ten endpoints with returns, costs and an available-to-us verdict each;
whether any closes the prose-evidence gap and whether any closes the
job-change gap, decided against what those gates accept; the wire-or-delete
recommendation for `people_search` with its argument; and per recommended
endpoint the stage, position and licensing reason.

## RESULT

STATUS: DONE
COMMIT SHA: f183ca3f
TESTS: No src/ changes. Analysis derived from API documentation cross-referenced
       against adapter, waterfall, enrich pipeline, and evidence gate code.
FILES CHANGED:
  docs/CONTACTOUT-UNUSED-2026-09-16.md          (new - the deliverable)

FINDINGS:

1. THE TEN ENDPOINTS (all assumed available to our plan/key, none live-proven):
   - LinkedIn Profile Enrich (GET /v1/linkedin/enrich) — full profile + contact, 1 search/email/phone credit
   - People Enrich (POST /v1/people/enrich) — enriched profile, 1 search + email/phone credits
   - Contact Info Single (GET /v1/people/linkedin) — emails + phone, 1 email/phone credit
   - Company Search (POST /v1/company/search) — firmographics, 1 search per result
   - Email-to-LinkedIn (GET /v1/people/person) — LinkedIn URL from email, 1 email credit
   - Personal Email Checker — boolean, cost unconfirmed
   - Work Email Checker — boolean, cost unconfirmed
   - Phone Checker — boolean, cost unconfirmed
   - Batch Email Verify — per-email verifier credits
   - Bulk Contact Info v1/v2 — per-profile email/phone credits

2. PROSE-EVIDENCE GAP: None of the ten close it. Key finding: the existing
   `company-information-from-domain` response already includes a `description`
   field that the adapter's `company_info()` trim drops. Adding it to the trim
   is a one-line change at zero additional credits and partially addresses the
   gap. The rest is genuinely unbridgeable by ContactOut (layers 3-4 own it).

3. JOB-CHANGE GAP: None close it. `linkedin/enrich` and `people/enrich` return
   work history with dates, but detecting a change requires snapshot diffing
   the pipeline does not support. ContactOut has no "changed since" query.

4. people_search: DELETE. Orphan method — implemented, tested, called by
   nothing in production. Same data as `decision-makers` at the same cost.
   The pipeline does not need its filtering capability.

5. RECOMMENDED ADDITIONS:
   - `linkedin/enrich` in `email_discovery` stage, after Blitz email fallback,
     as a second ContactOut path addressed by LinkedIn URL. Needs live-proof
     on 5-10 records first (~5-10 email credits).
   - Add `description` to `company_info()` trim (one-line adapter change,
     zero credits, partially closes prose-evidence gap).

6. NOT RECOMMENDED: The remaining eight endpoints. Company Search returns the
   same data as the existing endpoint. Contact Info Single is a subset of
   LinkedIn Enrich. Email-to-LinkedIn solves a problem the pipeline does not
   have (email→URL, when the flow is URL→email). Checkers return booleans
   where the pipeline needs actual addresses. Batch/bulk endpoints solve a
   different usage pattern than the pipeline's one-domain-at-a-time flow.

RISKS:
- All ten endpoints are "assumed available" based on API docs not gating by
  plan tier. None are live-proven. A single call per endpoint would confirm.
- The `description` field finding is the highest-value item: zero credits,
  one line, and it puts company prose into the fact pool check_evidence reads.
- `linkedin/enrich` recommendation is conditional on live-proof that it
  returns contact info where `decision-makers` did not.

RECOMMENDED CLAUDE ACTION:
1. Read docs/CONTACTOUT-UNUSED-2026-09-16.md
2. Add `description` to `company_info()` trim (one line, zero credits)
3. Decide on `people_search` deletion
4. If `linkedin/enrich` is wanted, live-proof on 5-10 records first
5. Wire `linkedin/enrich` via TASK-207/208 (they own waterfall.py)
