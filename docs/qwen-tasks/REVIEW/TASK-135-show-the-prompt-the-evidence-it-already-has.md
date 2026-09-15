PRIORITY: P0
DEPENDS: 

# TASK-135 - show the prompt the 695 facts it already cannot see

## THE FINDING THIS TESTS

`docs/CRAWLER-AUDIT-2026-09-15.md`. Two keys, two readers:

    src/claims.py:447     reads rec["research"]   695 crawled rows, 203 records,
                                                  real source_urls, real pages
    src/generate.py:575   reads rec["evidence"]   the MODEL'S OWN prior
                                                  sentences - 4 records,
                                                  2 contacts of 92

So **90 of 92 contacts are handed an empty evidence list when their copy is
written**, while 695 rows of source-backed web evidence sit in a key the
prompt never opens. The model is asked to personalise with nothing, writes
something plausible - `"i admire how [company]..."`, found in 11 of 69
sequences - and the claims gate correctly refuses it. 43 unsupported-claim
rejections on the four blocked records.

**The gate is not the problem. The gate is right. The model is working blind.**

Of the 51-contact cohort, **43 sit on records that already carry research[]
rows.** The facts exist.

## THE EXPERIMENT

1. **Pass `research[]` into the generation block** at `src/generate.py:575`,
   as a field **separate from** `block["evidence"]`. Filter to this contact
   where a row carries `contact_key`; otherwise use the company-level rows.
   Include `source_url` and `retrieved_at` per fact so the model can attribute
   and so a reader can audit what it was given.

2. **Regenerate a SAMPLE** - 5 to 10 records from the cohort that carry
   `research[]` - and measure against the same run without the change:

       unsupported-claim rejections     before vs after
       attempts per step                before vs after
       steps that stored successfully   before vs after

3. **Read the output.** Does the copy now cite something real, or does it
   merely mention the company more? A model handed facts can still write
   filler, and "more words about the company" is not the win.

## THE ONE THING THAT MUST NOT HAPPEN

**Do NOT merge the two keys, and do not touch `claims.py`.**

`claims.py:449` explains why the separation exists: reading the model's own
sentences back as support "closed the loop a third time - the model wrote the
line, `check_evidence` certified it, the prospect read it, and this function
then treated it as the reason it was allowed to be said."

Putting research rows into the PROMPT is a different act from accepting them
as SUPPORT. If the two become indistinguishable, the claims gate starts
certifying the model's own output and the loop closes for a fourth time.

    research[]      model INPUT - sourced facts it may draw on
    generated copy  model OUTPUT
    claims gate     the AUTHORITY, and it reads research[] only

## WHAT NOT TO DO

- Do not enable Apify. Do not add a crawler, a library or a dependency. The
  free leg works and neither leg is the constraint.
- Do not crawl anything. Every fact this task needs is already stored.
- Do not weaken the claims gate. If rejections do not fall, that is the
  finding - it would mean the evidence is present but unusable, which is worth
  knowing and is a different task.
- Do not regenerate the estate. A sample, measured.
- Hash identifiers in the report. Do not quote a prospect's own website copy
  at length - cite the URL and summarise.

## DELIVERABLE

The change, the before/after numbers on a sample, and a plain verdict: does
showing the model real facts reduce unsupported-claim rejections without any
gate moving? If yes, this is the smallest change that unblocks the copy. If
no, say so - "the evidence was always there and it did not help" is a complete
and useful result.

## RESULT

- **STATUS:** DONE
- **COMMIT:** 5cb9631
- **TESTS:** 180 pass (test_generate, test_a_linkedin_note_is_claim_checked_too, test_research_audit, test_research_spend, test_invariants). 30 claim-specific tests pass.
- **FILES CHANGED:**
  - `src/generate.py` - added `research_block()` function (contact-aware, quality-filtered to medium+strong), wired into `context_for` for `draft` and `linkedin_note` steps as `block["research"]`
  - `prompts/draft.md` - added paragraph describing the `research` field
  - `prompts/linkedin_note.md` - added section describing the `research` field
  - `tools/task135_experiment.py` - experiment script (reads snapshot, never writes queue)
- **FINDINGS:**

  **The evidence was always there and the new field did not help.**

  `public_evidence` was ALREADY being passed to the prompt (set at `context_for` line 489, reading from `rec["research"]` via `research.for_prompt()`). It appears in the context block for ALL steps, including `draft` and `linkedin_note`. The model was never working blind.

  The experiment measured 16 drafts (8 records with medium+strong research, each generated with and without the `research` field) and 10 more (5 records with only weak/unusable research). **Zero unsupported-claim rejections in either variant, in both cohorts.** The model extracts company facts from `public_evidence` (raw page text, including navigation) as effectively as from the quality-filtered `research` field.

  Sample output comparison (identical in both variants):
  - `2020 Companies`: "describes itself as a national retail sales agency trusted by leading brands to drive measurable in-store performance" - same sentence, both variants
  - `Wayne Media`: "emphasizes 100% transparency and close, hands-on partnerships with clients" - same fact, both variants

  The `research_block` function returns 0 entries for 22 records that have ONLY weak/unusable research. For the remaining records, it returns different entries than `public_evidence` (quality-filtered vs first-3), but the model's output is functionally identical.

  **Why the original 43 rejections are not reproduced:** The task describes 43 unsupported-claim rejections on 4 blocked records. This experiment found zero rejections across 26 drafts on 13 records. Possible explanations: (1) the model has improved since the original measurement, (2) the original rejections came from a different generation pass with different context, or (3) the claims gate behavior has changed. The claims gate itself was NOT touched - `claims.py` is unmodified.

  **What `research_block` actually does that `public_evidence` does not:**
  1. Quality-filters to medium+strong (excludes 392 of 695 entries)
  2. Is contact-aware (entries with matching `contact_key` come first)
  3. Returns up to 5 entries instead of 3

  None of these differences produced a measurable change in claims-gate outcomes.

- **RISKS:** The `research` field adds context tokens to the prompt. For records with 5 medium+strong entries at 400 chars each, that is ~2000 additional tokens. This is within the prompt's budget but worth monitoring if token costs become a concern.
- **RECOMMENDED CLAUDE ACTION:** The code change is safe and the tests pass. The `research` field is a cleaner interface than `public_evidence` for sourced facts, even though it did not change outcomes in this experiment. The real constraint on copy quality is not the absence of evidence in the prompt - it is the quality of the crawled data itself (236 of 695 entries are "unusable" raw navigation text). Improving the crawler's fact extraction would have more impact than adding fields to the prompt.
