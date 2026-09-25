"""QA harness registry: CHECKS, PHASES, verdicts, exit codes.

This is the single source of truth for what checks exist, what phase they run
in, and what the verdicts mean. The runner, the table renderer and the push
refusal all read from here.
"""

#: Ordered tuple of (check_id, module_name, phase, blocking).
#: A module not listed does not run. A listed module that does not yet exist
#: reports NOT_IMPLEMENTED in the table - not PASS, and not silence.
CHECKS = (
    ("lead_state", "check_lead_state", "pre_push", True),
    ("lead_pack", "check_lead_pack", "pre_push", True),
    ("lead_copy", "check_lead_copy", "pre_push", True),
    ("campaign_bison", "check_campaign_bison", "pre_push", True),
    ("campaign_heyreach", "check_campaign_heyreach", "pre_push", True),
    ("readback", "check_readback", "post_push", True),
    ("reconcile", "check_reconcile", "ongoing", True),
)

#: The three phases. pre_push refuses the push on any non-PASS. post_push
#: retries UNCONFIRMED on a fixed schedule. ongoing raises CRITICAL on FAIL.
PHASES = ("pre_push", "post_push", "ongoing")

#: Verdict -> exit code. UNCONFIRMED and VACUOUS both exit 2 because both mean
#: "this did not establish anything", but they are named apart because they
#: have different fixes: UNCONFIRMED retries, VACUOUS means the subject set or
#: the field is missing.
VERDICT_EXIT = {
    "PASS": 0,
    "FAIL": 1,
    "UNCONFIRMED": 2,
    "VACUOUS": 2,
    "ERROR": 3,
}

#: Severity ordering. The runner's exit code is the WORST of its checks.
VERDICT_SEVERITY = {
    "PASS": 0,
    "FAIL": 1,
    "UNCONFIRMED": 2,
    "VACUOUS": 2,
    "ERROR": 3,
}


def checks_for_phase(phase, blocking_only=True):
    """The checks that run in this phase.

    If blocking_only, only checks with blocking=True are returned. A check
    with blocking=False is advisory in the table and not in the refusal.
    """
    return [
        c for c in CHECKS
        if c[2] == phase and (not blocking_only or c[3])
    ]


def validate_result(result):
    """Assert the five invariants of contract §4 on a result document.

    Returns a (valid, errors) tuple. If valid is False, the runner downgrades
    the verdict to ERROR. The errors list says what broke.

    The five invariants:
    1. offenders and unverifiable hold ids, not counts or summaries.
    2. clean + |union(offenders) ∪ union(unverifiable)| == subjects.
    3. subjects == 0 is VACUOUS, never PASS, and carries a stated reason.
    4. rules, counts, offenders keys agree in both directions.
    5. rules sentences are rendered from the run's parameters (not checked
       here - the runner checks that the rule text is non-empty).
    """
    errors = []

    if not isinstance(result, dict):
        return False, ["result is not a dict"]

    # Invariant 1: offenders and unverifiable hold ids.
    for key in ("offenders", "unverifiable"):
        bucket = result.get(key) or {}
        if not isinstance(bucket, dict):
            errors.append(f"{key} is not a dict")
            continue
        for rule, ids in bucket.items():
            if not isinstance(ids, list):
                errors.append(f"{key}.{rule} is not a list")
                continue
            for id_ in ids:
                if not isinstance(id_, str) or not id_.strip():
                    errors.append(f"{key}.{rule} contains a non-string id")
                    break
                # An id must look like an identifier: contains letters, dots,
                # hyphens, colons, at-signs - something a person could paste
                # into a provider UI or grep. Pure numbers, "7 leads", "...",
                # and empty strings are not ids.
                stripped = id_.strip()
                if stripped in ("...", "…", ""):
                    errors.append(f"{key}.{rule} contains a non-id: {id_!r}")
                    break
                if stripped.isdigit():
                    errors.append(f"{key}.{rule} contains a count, not an id: {id_!r}")
                    break
                # If it looks like "N something" (a count followed by text),
                # it is a summary, not an id.
                import re as _re
                if _re.match(r"^\d+\s+\S", stripped):
                    errors.append(f"{key}.{rule} contains a summary, not an id: {id_!r}")
                    break

    # Invariant 2: the arithmetic closes.
    subjects = result.get("subjects")
    clean = result.get("clean")
    offenders = result.get("offenders") or {}
    unverifiable = result.get("unverifiable") or {}
    if subjects is not None and clean is not None:
        all_offending = set()
        for ids in offenders.values():
            if isinstance(ids, list):
                all_offending.update(ids)
        for ids in unverifiable.values():
            if isinstance(ids, list):
                all_offending.update(ids)
        expected = clean + len(all_offending)
        if expected != subjects:
            errors.append(
                f"arithmetic: clean({clean}) + offending({len(all_offending)}) "
                f"= {expected}, not subjects({subjects})")

    # Invariant 3: subjects == 0 is VACUOUS, never PASS.
    if subjects == 0:
        if result.get("verdict") == "PASS":
            errors.append("subjects == 0 cannot be PASS")
        if not result.get("vacuous_reason"):
            errors.append("subjects == 0 must carry a vacuous_reason stating "
                          "why the set was empty")

    # Invariant 4: rules, counts, offenders keys agree.
    rules = set((result.get("rules") or {}).keys())
    counts = set((result.get("counts") or {}).keys())
    off_keys = set((result.get("offenders") or {}).keys())
    if rules != counts:
        errors.append(f"rules and counts disagree: {rules} vs {counts}")
    if rules != off_keys:
        errors.append(f"rules and offenders disagree: {rules} vs {off_keys}")

    # Invariant 5: rule sentences are non-empty (the runner cannot check that
    # they are rendered from this run's parameters, but it can check that they
    # are not empty strings).
    for rule, sentence in (result.get("rules") or {}).items():
        if not isinstance(sentence, str) or not sentence.strip():
            errors.append(f"rule {rule!r} has no sentence")

    return len(errors) == 0, errors


def worst_verdict(verdicts):
    """The worst verdict in a list, by severity."""
    if not verdicts:
        return "PASS"
    return max(verdicts, key=lambda v: VERDICT_SEVERITY.get(v, 0))


def exit_code(verdict, phase):
    """The exit code for a verdict, given the phase.

    Pre-push, UNCONFIRMED and VACUOUS refuse (exit 2) because nothing has been
    written and the cost of refusing is a delay. Post-push, UNCONFIRMED is
    retried on a fixed schedule. Ongoing, UNCONFIRMED is a CRITICAL if it
    persists across two consecutive cycles.
    """
    return VERDICT_EXIT.get(verdict, 3)
