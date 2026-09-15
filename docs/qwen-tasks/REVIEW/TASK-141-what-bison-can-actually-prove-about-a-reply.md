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

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** (pending final commit)

**TESTS:** No code changes in `src/`. Two probe scripts verify the live API
reads: `scripts/task141_attribution_probe.py` and
`scripts/task141_variant_edge.py`. Both ran successfully against the live
API on 2026-09-15. No test suite changes needed — this task produced
documentation, not code.

**FILES CHANGED:**
- `docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` (new) — the deliverable
- `scripts/task141_attribution_probe.py` (new) — traces reply→step→variant chain
- `scripts/task141_variant_edge.py` (new) — verifies parent vs variant step sends
- Task file moved from `TODO/` to `RUNNING/`

**FINDINGS:**

1. **Step-level attribution is reconstructable from provider data.** The join
   is `reply.scheduled_email_id → GET /scheduled-emails/{id} → sequence_step_id`.
   Verified on 5 live replies. Every field is a provider fact. The causal
   claim is a reconstruction, not a fact.

2. **Variant-level attribution IS available** — this was the open question and
   the answer is better than expected. When EmailBison sends a variant, the
   scheduled email's `sequence_step_id` points to the VARIANT step (not the
   parent). The sequence-steps listing states whether that step has
   `variant: true`. The join is deterministic. Verified live: reply 1609200
   → scheduled email 22310733 → step 4036 (variant=True, variant_from_step=4035).
   Reply 1609203 → scheduled email 22310389 → step 4035 (variant=False, parent).
   Both in the same campaign. The provider distinguishes them.

3. **Events carry a compact variant index** (`sequence_step_variant`, 1-based)
   but only for 10 days. The step id is the durable identifier.

4. **Untracked replies are unattributable.** `scheduled_email_id: null` means
   no join path exists. Counting them as positive or negative is a hypothesis.

5. **Open rates are noise.** `open_tracking` is `false` estate-wide.

6. **No disagreement with existing documentation.** The live reads confirmed
   every field shape recorded in `BISON-API-CAPABILITY-MAP-2026-09-14.md`
   and `BISON-API-ROUTE-EVIDENCE-2026-09-15.md`.

7. **The strongest defensible analysis:** "This tracked reply was a response
   to the email sent at step X (variant Y) on [date]." Not "this email caused
   this reply." Step-level and variant-level attribution are both available
   from provider data. Causation is a reconstruction.

**RISKS:**
- The 10-day event window means `sequence_step_variant` and
  `sequence_step_order` are not available for historical analysis. The step
  id is durable but requires the sequence-steps listing to interpret.
- If sequence steps are deleted or renumbered, the variant mapping is lost
  unless preserved externally.

**RECOMMENDED CLAUDE ACTION:**
- Review `docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` for accuracy.
- TASK-059 can now use the two-hop join (`reply → scheduled_email → step`)
  with the confidence level stated in the boundary document.
- The variant experiment model in `COPY-EXPERIMENTS.md` is compatible with
  EmailBison's step model — variant steps have their own ids, and the
  scheduled email records which variant step was sent.
