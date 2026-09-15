PRIORITY: P1
DEPENDS:

# TASK-141 - provider fact, reconstruction, hypothesis: draw the three lines in the data model

## WHY THIS IS NOT AN ANALYSIS TASK

The operator's standing rule is that every outcome must be labelled as one of
three things and never silently promoted between them:

    PROVIDER FACT             the provider told us this
    RESONATE RECONSTRUCTION   we joined provider rows together to infer it
    ATTRIBUTION HYPOTHESIS    we believe this caused that

"The last email before the reply" is a RECONSTRUCTION. Calling it the email
that produced the reply is a HYPOTHESIS. Neither is a fact, and the difference
decides whether a variant can be declared a winner.

TASK-059 is in REVIEW and asks which email produced which reply. This task asks
the prior question: **what can EmailBison actually prove, and where exactly does
proof end?** Answer it and TASK-059's answer becomes checkable instead of
plausible.

## WHAT TO ESTABLISH

You hold real EmailBison credentials and the rule is READS ONLY - no write, no
send, no campaign mutation, no resume, no pause. Reads are the whole task.

Work down the hierarchy and record, for each level, the FIELDS THE PROVIDER
RETURNS - not the fields you expected:

    campaign -> sequence -> step -> lead -> variant -> send -> reply -> outcome

For each level answer three questions:

1. Does the provider expose it at all, at which route, and what does the
   response actually contain? Paste the trimmed field names.
2. Can a reply be joined to a SPECIFIC STEP by provider data alone, or only by
   reconstructing from timestamps? Say which, and show the field that decides.
3. Can a reply be joined to a SPECIFIC VARIANT? If the provider does not carry
   variant identity on a send, then variant-level attribution is not available
   at any confidence and the honest answer is to say so in the data model
   rather than approximate it.

## THE DOCUMENTATION HIERARCHY

`docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` and
`docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` already record what has been
probed. **Start there and do not re-probe what is already evidenced.** Add to
them; do not restate them. Where the recorded evidence and a live read
disagree, the live read wins and the disagreement is itself a finding.

## THE OUTPUT

`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md`, structured as:

    what the provider states                     (FACT)
    what we can join, and by which key           (RECONSTRUCTION)
    what we would be guessing                    (HYPOTHESIS)
    and for each: the route, the field, an example trimmed row

Then the consequence, stated plainly: given those boundaries, what is the
STRONGEST DEFENSIBLE analysis of reply outcomes? Not the best-sounding one.
If step-level attribution is reconstructable and variant-level is not, say
that, and say what a variant experiment would have to change to become
readable - a separate campaign per arm, a subject marker, something the
provider does carry.

## WHAT YOU MAY NOT DO

- No writes at any provider, for any reason.
- Do not quote an open rate. `open_tracking` is False estate-wide and any
  number derived from it is noise.
- Do not count an UNKNOWN reply as negative.
- Do not write to `work/`.

## FILES ALLOWED

    docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md   (new)
    scripts/task141_*.py
    the task file itself

## FILES FORBIDDEN

    src/       work/

## DELIVERABLE

The three-way boundary with a route and a field behind every line, and the
strongest defensible analysis that boundary permits.
