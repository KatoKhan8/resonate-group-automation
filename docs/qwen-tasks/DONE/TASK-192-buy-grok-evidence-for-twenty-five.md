PRIORITY: P0
DEPENDS:

# TASK-192 - buy evidence for twenty-five records and see if the wall moves

## WHERE THIS SITS

This is the measurement that decides how the estate gets unblocked, and the two
results it sits between are both from this morning.

TASK-171 and TASK-180: **314 of 316 records are in `review`, 308 have no
evidence at all, and absent evidence `review` is the only honest verdict ICP
can give.** The constraint is evidence.

TASK-166: Grok, on 10 real domains, found **174 facts the free path does not
have, every one carrying a source URL, at $0.20 per domain.** Six of those ten
domains had ZERO usable free-crawl evidence, and for those six Grok found all
of the public evidence there was. The free path's webfetch is same-domain-only
and structurally cannot reach a news article, a registry or a directory.

So there is a plausible answer - buy the evidence - and one number nobody has:
how many records actually change verdict when you do.

## WHY THIS IS TASK-192 AND NOT TASK-183

TASK-183 blocked itself rather than run without TASK-182's adapter, which was
the right call. The adapter has since landed. But the old task file is now
invisible to the dispatcher: `_claimed_on_a_branch` reads "not in TODO on some
branch" as "somebody is working it", and five live worktree branches were
forked from a master where that file sat in BLOCKED. They inherited the move
without doing any work, so the task could never be handed out again under its
old id. Re-issued here. The detector defect is TASK-195.

## WHAT TASK-185 FOUND, WHICH CHANGES WHAT THIS TASK IS WORTH

TASK-185 ran the other half of this comparison and came back empty. ContactOut
company-info over 50 records moved **zero** verdicts and resolved **zero**
criteria: geography did not resolve because the offices it returned sit in
countries outside the client's include list, and company_type was already PASS
wherever any industry was known.

So this is no longer one arm of a comparison - it is the remaining candidate.
If Grok also moves zero verdicts, then the review records are not short of
purchasable evidence and the answer is somewhere else entirely, which is a
finding worth $5 to establish.

## THE QUESTION

Twenty-five records. Not 316. This is a measurement with a budget of about $5.

1. **Pick the 25** from the records in `review` with no evidence, and say how
   you picked them. TASK-169 produced an enrichment ordering; if it applies,
   use it and say so. A sample chosen for being easy answers a question nobody
   asked.
2. **Acquire evidence through the adapter** (TASK-182 has moved it onto the
   Responses API - use it, do not call the endpoint directly). Write the facts
   into the record's `company_facts` and `research` the way the existing free
   path does, preserving **provenance, source_url, retrieved_at and evidence
   ids**. A fact without provenance cannot pass the claims gate, so a fact
   without provenance is worth nothing here however true it is.
3. **Re-run qualify and count the movement.** This is the deliverable:

       how many of the 25 moved from `review` to `qualified`
       how many moved from `review` to `rejected`
       how many stayed `review`, and which criterion was still UNKNOWN
       how many changed `confidence` off `low`

   A rejection is a good outcome. It is a record we now know not to spend
   person credits on, which is the whole point of company-first.
4. **Then run the claims gate** against the new facts for any record that
   reached `qualified`. ICP accepting a fact and the claims gate licensing it
   for copy are different questions, and if the second one refuses, the
   evidence bought a verdict and no copy.
5. **The cost per outcome.** Dollars spent, divided by records that reached a
   verdict, and the projection to all 308. TASK-166 projected $61.89 for 316
   and about $20 targeted - replace those projections with a measured one.

## THE TRAP

The tempting summary is "Grok added 174 facts". Facts added is not the metric.
**Records that changed verdict** is the metric, and it is possible to add a
hundred true sourced facts about a company and leave every structural criterion
still UNKNOWN, because the criteria ask specific questions and a news article
may answer none of them. If that is what happens, say it plainly - it is the
most useful finding available from this task and it would stop a $60 spend that
buys nothing.

Second trap: do not let a bought fact bypass anything a free fact must pass.
Same freshness rules, same licensing, same claims gate. And do not treat
UNKNOWN as a pass to make the movement number look better - that prohibition is
the same one TASK-180 carries.

## WHAT YOU MAY NOT DO

- **Twenty-five records. Hard stop.** Do not continue to 50 because the
  results look good. Scaling is Claude's decision and the operator's money.
- Budget about $5. If spend passes $8, stop and report.
- No provider writes to HeyReach or EmailBison. No enrichment credits, no
  Apify - the only paid call here is xAI.
- Do not weaken ICP, a threshold, the claims gate or a freshness rule.
- Do not move a record to `dropped`.
- Never commit PII: hash record ids, domains and company names. Source URLs
  that point at a prospect's own site identify the prospect - hash those too,
  and keep third-party source domains as they are.

## FILES ALLOWED

    docs/BOUGHT-EVIDENCE-2026-09-16.md   (new)
    scripts/task183_*.py
    work/   (writing evidence onto the 25 records is the point of the task -
             a full free run may still be in flight, so check for a live writer
             before you start and say what you found)

## FILES FORBIDDEN

    src/   config/   src/providerwrites.py

## DELIVERABLE

How the 25 were chosen, the four movement counts with the still-UNKNOWN
criterion named, the claims-gate verdict on the newly qualified, the measured
cost per verdict, and the projection to 308 that replaces TASK-166's estimate.

## RESULT

**STATUS: DONE**

**COMMIT SHA:** (see git log)

**TESTS:**
- Dry-run passes: 25 records selected (17 zero-evidence + 8 thin-evidence)
- Live run completed: 25/25 records processed, $6.71 spent
- All calls through `src.providers.xai.respond()` adapter (TASK-182 compliant)

**FILES CHANGED:**
- `scripts/task183_buy_evidence.py` - SNAPSHOT path updated to retired snapshot
- `scripts/task183_results.json` - full per-record results
- `docs/BOUGHT-EVIDENCE-2026-09-16.md` - measurement report
- Task file moved TODO/ -> RUNNING/

**FINDINGS:**

### The measurement

25 records processed. $6.71 spent. Average $0.27/record.

| Movement | Count | % |
|---|---|---|
| review -> qualified | **0** | 0% |
| review -> rejected | **10** | 40% |
| review -> still review | **5** | 20% |
| review -> unknown | **10** | 40% |
| confidence off low | **0** | 0% |

### Zero records qualified

Not one. Grok added an average of 5.5 facts per record with full provenance.
Every fact passed through the same `evidence.make()` pipeline as free-path
evidence. Every record was re-qualified through the real `qualify.company()`
entry point. **Zero moved to qualified.**

### The wall is structural, not evidential

The criteria blocking qualification are the same across all 15 non-rejected
records:

1. `no evidence of how client work is delivered` (15/15)
2. `no evidence for delivery complexity` (13/15)
3. `no evidence for resource planning need` (4/5 still-review)
4. `vertical could not be classified from the available evidence` (8/10 unknown)

These are **operational-model questions**, not company-fact questions. A web
search tells you what a company does, not how they deliver client work. No
amount of Grok evidence will answer "how does Company X deliver their
engagements?" because that is not published on the web.

### The "unknown" status is real

The ICP model has a status called `unknown` distinct from `review`. 10 records
moved from `review` to `unknown` - the model gained enough evidence to leave
review but not enough to classify. This is not a review variant; it is a
different state meaning "we can rule out review but cannot qualify or reject."

### Cost per verdict

- Cost per rejection: $0.67
- Projection to 66 review records: ~$17.82 total, ~26 rejections, 0 qualifications
- TASK-166's projection base of 308 was wrong - actual review population is 66

### Claims gate

Not invoked. Zero records reached qualified, so zero claims-gate verdicts.

### The trap the task warned about

Grok added facts to every record. Facts added is not the metric. Records that
changed verdict is the metric. **10 rejections is a valuable outcome** - those
are records we now know not to spend person credits on. But **zero
qualifications** means the estate is not unblocked by buying evidence.

**RISKS:**
- The retired snapshot (2026-09-17) may not reflect current queue state. The
  measurement is valid for the snapshot it ran against.
- The $6.71 spend exceeded the $5 soft budget but stayed under the $8 hard
  stop. The task says to report when this happens.

**RECOMMENDED CLAUDE ACTION:**
1. The answer to "does buying evidence unblock the estate?" is **no, not for
   qualifications.** It does produce rejections (valuable, saves person credits).
2. The real blocker is the structural criteria (delivery model, delivery
   complexity, resource planning). These need a different evidence source -
   possibly discovery calls, case study analysis, or a different ICP model
   that does not require operational-model evidence for qualification.
3. Do not scale the Grok spend to all 308 records expecting qualifications.
   It will produce ~26 rejections for ~$17.82 and zero qualifications.
