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

**COMMIT SHA:** e099e91

**TESTS:** Two verification scripts run against live API (read-only):
- `scripts/task141_verify_attribution.py` — end-to-end chain: reply → scheduled_email → step → variant check
- `scripts/task141_variant_index.py` — cross-check: event `sequence_step_variant` vs computed index

Both scripts ran successfully. Key findings verified live:
- Reply 1609200 → scheduled_email 22310733 → step 4036 (variant=True, variant_from_step=4035)
- Event `sequence_step_variant` values (2, 3, 5) match computed variant indices, NOT step ids

**FILES CHANGED:**
- `docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` (new) — the three-way boundary document
- `scripts/task141_verify_attribution.py` (new) — chain verification script
- `scripts/task141_variant_index.py` (new) — variant index cross-check script

**FINDINGS:**

1. **Step-level attribution is RECONSTRUCTABLE.** Reply → `scheduled_email_id` → `GET /scheduled-emails/{id}` → `sequence_step_id`. Two hops on integer keys. No timestamp matching, no inference. Verified live on reply 1609200 → step 4035.

2. **Variant-level attribution is RECONSTRUCTABLE.** The `sequence_step_id` on the scheduled email IS the variant step id when a variant was sent. Verified live: reply 1609200 → step 4036, which is `variant: true, variant_from_step: 4035`. The step id is the variant identifier; there is no separate variant id field.

3. **CORRECTION to prior documentation.** `BISON-API-CAPABILITY-MAP-2026-09-14.md` section D stated `sequence_step_variant` in events is the step id of the variant. **That is wrong.** Live verification shows it is a sequential index (1=A, 2=B, 3=C) within a parent step, not a step id. Step ids are in the 4000s; variant index values observed are 2, 3, 5. Cross-referenced three events: computed index matches event value exactly. The index is not a persistent identifier; the step id is.

4. **Events carry the richest step-level data but have 10-day retention.** `GET /events` payload includes `sequence_step_id`, `sequence_step_order`, and `sequence_step_variant` directly. This avoids the scheduled-email lookup but is limited to recent data.

5. **The strongest defensible analysis:** Per-step and per-variant reply counts and rates are reconstructable facts. Causal attribution ("step N caused this reply") is a hypothesis. Variant comparison as experiment requires controlled design the provider does not supply (one campaign per arm, subject marker, custom variable, or known assignment mechanism).

6. **Consequence for TASK-059:** It can prove the threading link (reply R is threaded to the email sent at step N on date D). It cannot prove causal attribution (step N produced reply R). The first is a fact; the second is a hypothesis. TASK-059 should state the threading link and label it as such.

**RISKS:**
- The variant index correction changes the interpretation of event data. Any code or analysis that treated `sequence_step_variant` as a step id is wrong and must be fixed.
- The 10-day event retention means historical analysis must use the scheduled-email path, not events.
- Untracked replies (`scheduled_email_id: null`) cannot be attributed to any step or variant. They are not negative outcomes; they are unknown.

**RECOMMENDED CLAUDE ACTION:**
1. Review `docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` for accuracy and completeness.
2. Update TASK-059 in light of this boundary: it can prove threading, not causation.
3. Fix any code that treats `sequence_step_variant` as a step id (the earlier docs were wrong).
4. Consider the four designs for making variant experiments readable (one campaign per arm, subject marker, custom variable, known assignment mechanism).
