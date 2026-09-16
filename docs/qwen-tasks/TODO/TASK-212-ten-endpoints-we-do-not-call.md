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
