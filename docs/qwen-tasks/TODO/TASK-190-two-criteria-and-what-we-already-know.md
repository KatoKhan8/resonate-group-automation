PRIORITY: P0
DEPENDS:

# TASK-190 - only two criteria matter, so check what we already have first

## WHERE THIS SITS

TASK-187 corrected a premise everybody was working from, including Claude's.
`icp_pass` is not the gate. Reading `verdict_of`:

    any FAIL                              -> icp_fail
    all five PASS                         -> icp_pass
    geography AND company_type both PASS  -> icp_pass_with_uncertainty
    otherwise                             -> icp_review

**Both `icp_pass` and `icp_pass_with_uncertainty` map to
`icp_status = "qualified"`,** and `qualify.state_of` is what gates person-credit
spend. 113 records have already reached qualified this way. Every one of them
has `tracks_time = unknown`. The design intends that.

So the qualification bar is two criteria: **geography and company_type.**
Nothing else blocks. And TASK-187 measured that all 66 review records are
blocked on one or both of those two - resolving `tracks_time` would change the
qualified count by exactly zero.

Two purchases are being measured against each other for this - company-info at
a credit a record (TASK-185) and Grok at twenty cents a domain (TASK-183).
Before either is scaled, there is a cheaper question nobody has asked.

## THE QUESTION

**How many of the 66 can be resolved from data the system already has?**

1. **Geography.** What exactly does the criterion accept - an ISO country from
   `company_facts.offices`, `segment.country`, something else? Then find every
   other place the system already knows where a company is: the MX cache, a TLD
   (`.dk`, `.hr`, `.co.uk` are not ambiguous), an address on a page already
   crawled, a phone country code, existing waterfall call results, a
   `geo.py` inference. For each source say how many of the 66 it resolves and
   how reliable it is.
2. **Company type.** Same treatment. What does the criterion accept, and what
   does the system already hold that answers it - `segment` classification,
   industry from an earlier provider call, the vertical keywords
   `icpstructural` looks for in research text that may already be present
   under a different key?
3. **Then count the free yield.** If every free source were used, how many of
   the 66 reach `qualified`, how many still need a purchase, and which
   criterion each remaining record is short of.
4. **Do not stop at the 66.** The 250 unprocessed records have no data at all,
   but they do have domains, and a TLD is free. How many of the 250 could have
   geography resolved for nothing? That number changes what the purchase for
   the 250 has to buy.
5. **Implement only what is provably correct.** If a `.dk` domain reliably
   means Denmark for the geography criterion, wire that as an evidence source
   with provenance, the same as any other fact - source, method, timestamp. If
   a source is only 80% reliable, do NOT wire it; report it and say so.

## THE TRAP

Inferring a fact and evidencing one are different, and this task sits exactly
on that line. A TLD-derived country is an inference. It may be good enough for
ICP geography and it is certainly not good enough for copy - the claims gate
needs a source it can license, and "the domain ends in .dk" is not a citation.

So: if you wire an inferred fact, mark it as inferred, with its method, and
make sure the claims gate can tell the difference. If that distinction does not
exist in the evidence model, that is the finding and you should stop and report
it rather than inventing one.

Second trap: do not let an inference produce a FAIL. A wrong inference that
fails a criterion turns a good company into `icp_fail`, and a FAIL on any
criterion is terminal for qualification. Inference may only move UNKNOWN to
PASS, never UNKNOWN to FAIL. Say in the code why.

## WHAT YOU MAY NOT DO

- No paid provider calls. No credits, no Apify, no xAI. That is the entire
  point of this task.
- No provider writes.
- Do not change `icpstructural.py`, a criterion, a threshold or a weighting.
  Add evidence; do not move the bar.
- Do not move a record to `dropped` or produce a FAIL from an inference.
- A full free run may still be writing to `work/`. Check for a live writer
  before you write and say what you found.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    src/geo.py or the evidence module that should own an inferred fact - read
      first and justify the file you choose
    tests/test_inferred_evidence.py   (new)
    docs/FREE-GEOGRAPHY-AND-TYPE-2026-09-16.md   (new)
    scripts/task190_*.py

## FILES FORBIDDEN

    src/icp.py   src/icpstructural.py   config/

## DELIVERABLE

What each of the two criteria accepts, every free source that can answer them
with its per-source yield against the 66 and reliability, the free yield total,
the count for the 250 from TLD alone, whatever you wired marked as inferred
with provenance, and the records still short with the criterion named.
