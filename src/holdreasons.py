"""Hold-reason taxonomy for record-level holds.

TASK-168: every hold carries a machine-readable reason. The taxonomy has
five classes that decide what happens next:

    ACTIONABLE     something we can do now moves it
    WAITING        a dependency outside us, time will move it
    RETRYABLE      transient, retrying is correct
    HUMAN_REVIEW   a person must decide
    PERMANENT      it is never moving

A hold without a class is a record that leaves the pipeline silently.
"""
import datetime

ACTIONABLE = "ACTIONABLE"
WAITING = "WAITING"
RETRYABLE = "RETRYABLE"
HUMAN_REVIEW = "HUMAN_REVIEW"
PERMANENT = "PERMANENT"

CLASSES = (ACTIONABLE, WAITING, RETRYABLE, HUMAN_REVIEW, PERMANENT)

# Enrichment holds: contacts exist but verification is unresolved.
ENRICH_UNRESOLVED_VERDICT = "enrich:unresolved_verdict"
ENRICH_ACCEPT_ALL_UNCLEARED = "enrich:accept_all_uncleared"
ENRICH_NO_CONTACTS = "enrich:no_contacts_found"
ENRICH_VERIFIERS_DISAGREE = "enrich:verifiers_disagree"

# Generation holds: model failed to produce valid output.
GENERATION_EVIDENCE_TRACE = "generation:evidence_not_traceable"
GENERATION_EVIDENCE_EMPTY = "generation:evidence_empty"
GENERATION_JSON_PARSE = "generation:json_parse_failure"
GENERATION_LINT_FAILURE = "generation:lint_failure"

# Un-drop holds: reinstated after drop, pending re-enrichment.
UNDROP_PENDING_REENRICHMENT = "undrop:pending_reenrichment"


def classify(reason_code):
    """Map a reason code to its taxonomy class.

    Returns the class string. Unknown codes map to HUMAN_REVIEW, which is
    the safe default: a person looks rather than an automated action taking
    a wrong turn.
    """
    if reason_code in (ENRICH_UNRESOLVED_VERDICT,
                       ENRICH_ACCEPT_ALL_UNCLEARED):
        return WAITING
    if reason_code == ENRICH_NO_CONTACTS:
        return PERMANENT
    if reason_code == ENRICH_VERIFIERS_DISAGREE:
        return HUMAN_REVIEW
    if reason_code in (GENERATION_EVIDENCE_TRACE,
                       GENERATION_EVIDENCE_EMPTY,
                       GENERATION_JSON_PARSE):
        return RETRYABLE
    if reason_code == GENERATION_LINT_FAILURE:
        return HUMAN_REVIEW
    if reason_code == UNDROP_PENDING_REENRICHMENT:
        return ACTIONABLE
    return HUMAN_REVIEW


def can_return_to_queue(rec):
    """Predicate: is it provably safe to move this held record back?

    Safe means ALL three:
      1. The condition that caused the hold is measurably gone.
      2. The record still passes every gate it passed before.
      3. Returning it costs nothing (no provider call, no credit).

    Returns (bool, str). The string explains which condition failed when
    the answer is False.
    """
    reason = rec.get("hold_reason") or ""
    code = reason.split(":")[0] + ":" + reason.split(":")[1] \
        if reason.count(":") >= 1 else reason
    cls = classify(code) if ":" in reason else classify(reason)

    if cls == PERMANENT:
        return False, "permanent: condition will not change"

    if cls == WAITING:
        contacts = rec.get("contacts") or []
        unresolved = [c for c in contacts
                      if c.get("verdict") in (None, "unknown", "accept_all")]
        if unresolved:
            return False, ("waiting: %d contact(s) still unresolved"
                           % len(unresolved))
        return True, "all contacts resolved"

    if cls == ACTIONABLE:
        contacts = rec.get("contacts") or []
        if not contacts:
            return False, "actionable: no contacts to re-enrich"
        unresolved = [c for c in contacts
                      if c.get("verdict") in (None, "unknown", "accept_all")]
        if unresolved:
            return False, ("actionable: %d contact(s) still need enrichment"
                           % len(unresolved))
        return True, "contacts present and resolved"

    if cls == RETRYABLE:
        return False, "retryable: requires model re-run, not free"

    if cls == HUMAN_REVIEW:
        return False, "human_review: person must decide"

    return False, "unknown hold reason: cannot assess safety"


def set_hold_reason(rec, reason_code, detail=None):
    """Write hold_reason and hold_class onto a record at the moment of hold.

    Also records hold_at (timestamp) so the reason can be aged.
    """
    rec["hold_reason"] = reason_code
    rec["hold_class"] = classify(reason_code)
    rec["hold_at"] = (datetime.datetime.now(datetime.timezone.utc)
                      .replace(microsecond=0).isoformat())
    if detail:
        rec["hold_detail"] = detail
