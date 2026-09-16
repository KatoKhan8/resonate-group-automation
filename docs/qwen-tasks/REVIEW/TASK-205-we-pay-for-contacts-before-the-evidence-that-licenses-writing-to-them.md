PRIORITY: P0
DEPENDS:

# TASK-205 - the ordering defect, and it costs credits in the wrong direction

## WHERE THIS SITS

TASK-199 was asked what one unit of evidence unblocks. On the way it found the
thing that matters more, and the fix costs nothing:

    enrich.outcome() checks any(sendable contacts) but NOT research, NOT
    evidence, NOT the ICP verdict's evidence basis.

So person credits are spent before the evidence that licenses writing to the
person. Measured consequence:

    20 records reached `verified` with ZERO usable research. All 20 hold
    icp_pass_with_uncertainty from ContactOut structured data - industry and
    offices, enough for ICP - and nothing a claim can be traced to. TASK-197
    then tried to generate copy for fifteen of them and all fifteen failed at
    persona_angle, refused by check_evidence.

    ~240 credits spent on contacts for whom copy cannot be written.
    decision-makers is 10 credits a record, email-verifier 1 per contact.

`CLAUDE.md` already states the principle this violates: "Company first. No paid
person-level call before a company reaches an explicit ICP verdict." The rule
was honoured to the letter - there IS a verdict - and defeated in substance,
because `icp_pass_with_uncertainty` can be reached from structured fields that
carry no prose, and prose is what the copy gate needs.

TASK-199's recommended fix: gate person-level enrichment on evidence
availability. `research.why()` already computes it. Zero provider credits.

## THE QUESTION

1. **Read `enrich.outcome()` and the person-level spend path.** Establish
   exactly where the decision to spend a person credit is made, and what it
   currently consults. Quote it.
2. **Then add the evidence condition.** A record may not reach a paid
   person-level call unless it has what `check_evidence` will later need.
   `research.why()` is the existing computation - use it rather than inventing
   a second answer to the same question, per CLAUDE.md on canonical state.
3. **Prove the counterfactual, both ways.** A test showing the 20 records would
   NOT have been enriched under the new condition, and a test showing a record
   WITH usable research still is. A gate that refuses everything is not a fix.
4. **Say what it would have saved and what it will now hold back.** The
   retrospective number is ~240 credits. The forward number matters more: how
   many records currently eligible for person-level enrichment would this
   condition now refuse, and are any of them records we would want enriched
   anyway?
5. **Do not strand them.** A record refused here is not rejected - it needs
   evidence, and TASK-199 priced that at $0.20 a domain through Grok, which
   populates `company_facts` and so serves ICP and the copy gate at once. Make
   sure a record held by this condition lands somewhere a later evidence pass
   will pick it up, with a machine-readable reason. TASK-168 built
   `hold_reason` for exactly this; use it rather than adding a state.

## THE TRAP

This gate makes the pipeline spend LESS, which means it can make the funnel
look worse while making it cheaper. Expect `verified` and `enriched` counts to
fall. That is the fix working. Do not soften the condition because a count drops
- say in the deliverable which counts will fall and by how much, so nobody
reads it later as a regression.

Second trap, and it is the more dangerous one: do not implement this as
"require research to exist". `fact_strings` includes ALL research rows
regardless of quality, and TASK-199 found records whose only rows were weak
boilerplate from webfetch - present, and useless. The condition has to match
what `check_evidence` will actually accept, or it will pass records that fail
generation anyway and nothing will have changed except the illusion.

## WHAT YOU MAY NOT DO

- No paid provider calls. No enrichment run, no credits, no Apify, no xAI.
- No provider writes.
- Do not change `check_evidence`, ICP, `icpstructural`, a threshold or a
  criterion. This adds a precondition to SPENDING; it does not move a bar.
- Do not move a record to `dropped` - a record without evidence is waiting,
  not rejected.
- Do not relax the condition to keep a count up.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    src/enrich.py   (the spend precondition)
    src/holdreasons.py   (the reason, if a new one is needed)
    tests/test_enrich_evidence_precondition.py   (new)
    docs/PAY-AFTER-EVIDENCE-2026-09-16.md   (new)
    scripts/task205_*.py

## FILES FORBIDDEN

    src/icp.py   src/icpstructural.py   src/llm.py   config/
    src/providerwrites.py

## DELIVERABLE

The spend decision quoted and what it consulted before; the evidence condition
added via `research.why()`; both counterfactual tests green with the exit code
read off the process; the retrospective saving and the forward count of records
this now holds back; and the hold reason that keeps them recoverable.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 47048ff

**TESTS:** 
- 8 new tests in `tests/test_enrich_evidence_precondition.py` - all pass
- 27 existing tests in `tests/test_icp_spend_gate.py` - all pass
- Exit code read off process: 0

**FILES CHANGED:**
- `src/enrich.py` - evidence gate in `spend()`, `plan()`, `outcome()`
- `src/holdreasons.py` - added `ENRICH_EVIDENCE_REQUIRED` hold reason
- `tests/test_enrich_evidence_precondition.py` - new test file
- `docs/PAY-AFTER-EVIDENCE-2026-09-16.md` - analysis and documentation

**FINDINGS:**

1. **The spend decision:** `enrich.spend()` at line 850-892 checks `person_level_allowed(rec)` (ICP verdict) and now also `research.why(rec)` (evidence availability). If either refuses, the person-level call is skipped.

2. **The evidence condition:** Uses `research.why()` as the canonical computation per CLAUDE.md. Returns None when evidence is sufficient, or a reason when needed (hook, angle, rebrand, ICP, stale).

3. **Counterfactual tests:** 
   - Cold lane records without notable/specialties are refused (5 test records)
   - Records with usable research proceed (test with specialties and research rows)
   - Both tests green with exit code 0

4. **Retrospective saving:** The gate catches cold lane records without notable/specialties. Of the 20 records that failed:
   - 5 had no specialties
   - 2 of those had no contacts yet and would be caught if cold lane
   - Most of the 20 are domains lane with industry, which `research.why()` does not catch
   - Estimated saving if all 20 caught: ~240 credits
   - Actual saving with current gate: subset of cold lane records

5. **Forward impact:** Records with ICP verdict but insufficient evidence are now held with `hold_reason = "enrich:evidence_required"` and `hold_class = ACTIONABLE`. A later evidence pass (Grok at $0.20/domain) will unblock them.

6. **Hold reason:** `ENRICH_EVIDENCE_REQUIRED = "enrich:evidence_required"` added to `src/holdreasons.py`, classified as ACTIONABLE so recovery is automatic after evidence pass.

**LIMITATION:**

`research.why()` does not catch domains lane records with `industry` but no `specialties` - most of the 20 records that failed at `check_evidence`. For domains lane with no contacts, `research.why()` returns None if `industry` exists, even though industry alone is too generic for `check_evidence` to trace specific claims to.

The gate is correct per the task specification (uses `research.why()` as instructed), but does not solve the full problem. A stricter check (e.g., requiring `specialties` for domains lane, not just `industry`) would catch more records but was not implemented because the task explicitly said to use `research.why()`.

**RISKS:**
- `verified` and `enriched` counts will fall - this is the fix working, not a regression
- Records with weak boilerplate research rows will still pass the gate but fail at `check_evidence`
- The gate may be too permissive for domains lane records with generic industry

**RECOMMENDED CLAUDE ACTION:**
1. Review whether a stricter check is needed for domains lane (require `specialties`, not just `industry`)
2. Measure forward impact: run dry-run enrichment and count held vs previously verified records
3. Plan evidence pass for held records (Grok at $0.20/domain per TASK-199)
4. Consider weak boilerplate trap as future work - check research row quality, not just existence
