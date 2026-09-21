# TASK-246 — the learning tags, and the nightly rate report

Operator instruction, 2026-09-21: every enrolled lead carries a learning tag
schema, and a nightly report gives the rates by tag.

    persona · angle · subject variant · sender · timezone cohort ·
    source · signal

## WHY THIS EXISTS

Two emails have been sent in this project's history. Every future argument
about what works - which angle, which subject, which persona - will be
settled by whatever was recorded at enrollment, and a tag that was not
written at enrollment cannot be reconstructed afterwards. Batch 1 enrolls
tonight. **The schema must be able to tag leads that are already enrolled**,
from the enrollment artifacts, or the first real cohort is permanently
unmeasurable.

## THE SCHEMA

Seven fields, on the lead, at enrollment. Each is a CLOSED vocabulary except
signal, and an unknown value is refused rather than coerced - a tag that
silently accepts anything measures nothing.

    persona           the role pattern the copy was written for
    angle             the argument the opener makes
    subject_variant   the subject line's identity, not its text
    sender            the mailbox, which is also the human
    timezone_cohort   the recipient-local window group
    source            where the lead came from: the supplier file, nightly
                      sourcing, the READY reservoir, and `reengagement`.
                      OPERATOR, 2026-09-21: "Tag source = reengagement on
                      every lead so the learning report separates it from
                      cold." Cold and re-engagement share one daily capacity
                      and will share campaigns; if this field cannot separate
                      them, neither can any rate in the report.
    signal            the evidence that made it ICP-IN. Free text, recorded,
                      never parsed for decisions

Tags are written where the lead lives in OUR state, not at the provider.
Provider custom variables are for merge fields; a learning tag that only
exists at EmailBison is a tag we cannot join against replies.

## THE NIGHTLY RATE REPORT

Per tag value, per campaign, and overall:

    enrolled · provider-confirmed sent · replied · positive · bounced ·
    unsubscribed

**Rates need denominators and denominators need honesty.** A reply rate over
enrolled is not a reply rate - enrolled is not sent, and tonight's batch will
sit enrolled for days. Every rate names which denominator it used. A cell
with fewer than 30 sends prints the count and REFUSES the percentage; two
replies out of three sends is not a 67% reply rate and a report that prints
it will be believed.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test name both directions.

Required tests: an unknown vocabulary value is refused; a lead enrolled
before this task existed can be back-tagged from its enrollment artifact;
the under-30 cell refuses its percentage; a rate names its denominator.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
