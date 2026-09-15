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
