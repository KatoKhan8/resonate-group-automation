#!/usr/bin/env python3
"""What went out, to whom, from which sender, and did anything refuse.

WHY THIS MODULE EXISTS. It is the question the operator will have at 09:00 on
the morning CANARY-01 sends, and today answering it needs a shell and three
files. TASK 0030 shipped the provider write log, which answers "what did this
process ask a provider to do" - a VERB-level record. This answers the other
half, which is per PROSPECT, and the two are not the same question: the
provider ledger has no address, no sender, no step and no channel in it.

TWO AUTHORITIES, CROSSED, NEVER COLLAPSED - the same shape as `src.lanes`,
and for the same reason, which is that each one reads healthy in a state the
other calls broken:

    the record event log      per prospect, per step: which channel, which
    (via `src.touch`)         sender, what state, on what evidence. This is
                              the canonical touch history and it is READ
                              rather than reimplemented - a second
                              representation of "did this reach them" is how
                              the two come to disagree.

    the provider write log    whether a write was REFUSED, and why. A refusal
    (`src.providerwrites`)    is an event whose answer was no, and it is
                              recorded against a campaign and a verb, never
                              against a person - so it can say "something
                              refused on this campaign" and never "this
                              prospect was refused".

THE COUNTER THAT MATTERS IS `unaccounted`, and it is built so that it CAN be
non-zero. attempted minus (sent + refused), where `attempted` is defined by a
named set of states that mean "we acted" - NOT as sent plus refused plus a
remainder, which would make it zero by construction and the page would be
reporting its own arithmetic back to itself. A state this module has not been
told about counts as attempted AND lands in unaccounted, so a new touch state
added upstream surfaces as an alarm instead of being dropped.

WHAT THIS PAGE CANNOT SEE, and it is stated on the page itself rather than
only here. The event log is the WRITER's own record. A message that left the
provider and bounced at the recipient, or landed in spam, or was never
actually transmitted despite an accepted API call, is not in it unless a
webhook wrote it back. So a clean screen here is not a clean send, and the
one sentence on the page says exactly that.

It writes no file, opens no socket, reaches no provider and reads no
credential. Addresses are real prospects, so nothing here copies one anywhere
and the tests use synthetic ones.
"""
import datetime

from src import providerwrites, touch

# -------------------------------------------------------------- outcomes
#
# Three, because the brief asks for three, and the third is not a bucket for
# the awkward ones - it is the alarm.

SENT = "sent"
REFUSED = "refused"
UNKNOWN = "unknown"

OUTCOME_TEXT = {
    SENT: ("SENT",
           "the touch history confirms this step reached the prospect, on a "
           "confirming event rather than on a payload having been built. "
           "That is the writer's own record and is NOT evidence the message "
           "was delivered, opened or wanted"),
    REFUSED: ("REFUSED",
              "a guard, a hold or a failure stopped this step. The reason is "
              "shown beside it; a refusal is an event whose answer was no "
              "and never an absence of an event"),
    UNKNOWN: ("UNKNOWN",
              "this step was acted on and its state is one this page cannot "
              "classify as either. It is counted in `unaccounted`, which is "
              "the one number on this page that must never be quietly "
              "non-zero - and UNKNOWN is not 'probably fine'"),
}

#: Which touch states mean WE ACTED. `attempted` is this set, and it is
#: defined independently of SENT and REFUSED on purpose: `unaccounted` as
#: "whatever is left over" would be zero by construction and could never
#: raise the alarm it exists to raise.
#:
#: The three excluded states are the ones that mean "not yet": planned,
#: approved and payload_ready. `touch`'s own docstring makes the same
#: distinction and calls `push_prepared` the important omission - a payload
#: having been built is not an attempt.
NOT_YET = frozenset({touch.PLANNED, touch.APPROVED, touch.PAYLOAD_READY})

#: The states that mean it reached them. Taken from `touch.CONFIRMED_STATES`
#: rather than re-listed, so this page cannot drift from the canonical
#: definition of a confirmed touch.
SENT_STATES = frozenset(touch.CONFIRMED_STATES)

#: The states that mean something said no, with what each one means. BLOCKED,
#: HELD, PAUSED, FAILED and SKIPPED are five different refusals and the page
#: shows which - flattening them to one word is how "held pending review" and
#: "the transport raised" become the same row.
REFUSED_STATES = {
    touch.BLOCKED: "a gate refused this step",
    touch.HELD: "held, and a person has to release it",
    touch.PAUSED: "the campaign or the contact is paused",
    touch.FAILED: "the step was attempted and failed",
    touch.SKIPPED: "skipped",
}


def classify(state):
    """One step's outcome, and why. Fails closed on a state it is shown once.

    A state `touch` knows and this module does not is the case that matters:
    it is counted as attempted and returned UNKNOWN, never filed into
    whichever of the two buckets happens to be checked first.
    """
    if state in NOT_YET:
        return None, "not attempted yet"
    if state in SENT_STATES:
        return SENT, touch.WORDS.get(state, state)
    if state in REFUSED_STATES:
        return REFUSED, REFUSED_STATES[state]
    if state in touch.STATES:
        return UNKNOWN, (
            "%r is a touch state this page has not been told how to "
            "classify. It is counted as attempted and as UNACCOUNTED rather "
            "than being read as either sent or refused" % state)
    return UNKNOWN, (
        "%r is not a state `src.touch` defines at all, so neither this page "
        "nor the touch history can say what happened" % state)


# ------------------------------------------------------- the refusal ledger

def campaign_refusals(path=None, tenant=None):
    """Provider-write refusals, by campaign. The second authority.

    VERB-LEVEL AND NOT PER PERSON, and the page says so. This ledger records
    that `bison.resume_campaign` was refused on campaign 487; it cannot say
    which prospect that cost. So it is shown as a campaign-scoped banner and
    is never joined onto a prospect row, because a plausible join here would
    be this page inventing an attribution.
    """
    path = path or providerwrites.ledger_path()
    state, rows, damaged = _read_ledger(path)
    by_campaign = {}
    for row in rows:
        if tenant is not None and str(row.get("tenant") or "") != str(tenant):
            continue
        if str(row.get("outcome") or "") != "refused":
            continue
        key = str(row.get("campaign") or "")
        by_campaign.setdefault(key, []).append({
            "at": row.get("at"),
            "operation": row.get("operation"),
            "detail": row.get("detail"),
        })
    return {"state": state, "by_campaign": by_campaign, "damaged": damaged,
            "total": sum(len(v) for v in by_campaign.values())}


LEDGER_ABSENT = "absent"
LEDGER_UNREADABLE = "unreadable"
LEDGER_EMPTY = "empty"
LEDGER_PRESENT = "present"


def _read_ledger(path):
    """The ledger's rows, or the exact kind of nothing it is instead.

    Four kinds, kept apart. An unreadable ledger is the one that must not
    read as "nothing was refused": absence of a record is a refusal to
    answer, never a pass.
    """
    import json
    import os

    if not os.path.exists(path):
        return LEDGER_ABSENT, [], 0
    if not os.path.isfile(path):
        return LEDGER_UNREADABLE, [], 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return LEDGER_UNREADABLE, [], 0
    rows = []
    damaged = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            # A truncated final line is normal for an append-only file being
            # written to. Counted and shown, never skipped silently.
            damaged += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            damaged += 1
    if not rows and not damaged:
        return LEDGER_EMPTY, [], 0
    return LEDGER_PRESENT, rows, damaged


# ------------------------------------------------------------------ the rows

def _age(stamp, now):
    """Seconds since `stamp`, or None. Never 0 standing in for unmeasured."""
    if not stamp:
        return None
    text = str(stamp).strip().replace("Z", "+00:00")
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is not None:
        when = when.replace(tzinfo=None)
    delta = int((now - when).total_seconds())
    return delta if delta >= 0 else None


def _timelines_for(rec, config):
    """This record's per-contact cadence timeline, or why there is none.

    WHY THIS IS NOT OPTIONAL, and it is the most important measurement in
    this module. `BLOCKED`, `HELD` and `PAUSED` are produced by
    `touch._planned_state` from the TIMELINE's `status` field. An
    event-derived step gets `status: "historical"`, which maps to PLANNED.

    So a history built without a timeline can show confirmed sends and
    **not one refusal**. The page would read `3 sent, 0 refused` and look
    perfect while every refusal was invisible - which is precisely the
    instrument-sees-nothing defect this page is built to avoid. A record
    whose timeline cannot be built therefore makes the REFUSED count
    UNKNOWN rather than contributing a zero to it.

    Built once per record, not once per contact: `touch.history`'s own
    docstring names the per-contact rebuild as the quadratic mistake.
    """
    from src import cadence

    try:
        built = cadence.build(rec, config)
    except Exception as error:                  # noqa: BLE001 - see below
        # NOT a silent fallback. The exception type and message are carried
        # out of here and onto the page, and the consequence is that
        # `refused` becomes UNKNOWN. Classifying explicitly and failing
        # closed is the rule; swallowing this would make the page claim a
        # refusal count it cannot measure.
        return None, "%s: %s" % (type(error).__name__, error)
    return (built.get("contacts") or {}), None


def rows_for(records, now=None, config=None, timelines=None):
    """One row per prospect-step that was acted on, newest first.

    `records` is supplied rather than loaded, so this function reaches no
    store and a test hands it a list. The caller scopes it to one tenant.

    Returns the rows, the number of contacts in the cohort, and the records
    whose timeline could not be built - the third of which is what stops a
    refusal-blind read being presented as a complete one.
    """
    now = now or datetime.datetime.now()
    out = []
    cohort = set()
    blind = []
    for rec in records:
        if timelines is not None:
            per_contact, why = timelines.get(rec.get("id")) or {}, None
        else:
            per_contact, why = _timelines_for(rec, config)
        if per_contact is None:
            blind.append({"record_id": rec.get("id"), "why": why})
            per_contact = {}
        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            key = contact.get("key")
            cohort.add((rec.get("id"), key))
            timeline = per_contact.get(key) or {}
            for step in touch.timeline_rows(rec, key, timeline, config):
                outcome, why = classify(step.get("state"))
                if outcome is None:
                    continue
                out.append({
                    "at": step.get("at"),
                    "age_seconds": _age(step.get("at"), now),
                    # The address as the record holds it. Rendered, never
                    # copied anywhere: these are real prospects.
                    "address": (contact.get("email")
                                or contact.get("linkedin")),
                    "address_kind": ("email" if contact.get("email")
                                     else "linkedin" if
                                     contact.get("linkedin") else None),
                    "channel": step.get("channel"),
                    "campaign": rec.get("campaign") or rec.get("campaign_id"),
                    # glm-c's TASK 0230 is adding `step` to the ledger. The
                    # touch history already carries a step key, so this
                    # column is populated from there - and when it is absent
                    # it renders UNKNOWN rather than the column vanishing.
                    "step": step.get("step"),
                    "sender_id": step.get("sender_id"),
                    "outcome": outcome,
                    "outcome_label": OUTCOME_TEXT[outcome][0],
                    "why": why,
                    "state": step.get("state"),
                    "state_words": step.get("state_words"),
                    # What established the state. A row claiming SENT with
                    # no confirming event is the thing worth seeing.
                    "evidence_event": step.get("evidence_event"),
                    "blocked_by": step.get("blocked_by"),
                    "record_id": rec.get("id"),
                    "contact_key": key,
                })
    out.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return out, len(cohort), blind


def counters(rows, cohort_size=None, approved_cohort=None,
             refusals_visible=True):
    """Four numbers, each with its denominator, and one of them an alarm.

    `approved_cohort` is the size of the cohort the operator APPROVED. Its
    authority is the approval sheet, which lives outside this repository and
    names real prospects - so when it is not supplied the denominator is
    UNKNOWN and says so. It is never defaulted to the number of rows found,
    which would make the figure agree with itself whatever happened.
    """
    sent = [r for r in rows if r["outcome"] == SENT]
    refused = [r for r in rows if r["outcome"] == REFUSED]
    unaccounted = [r for r in rows if r["outcome"] == UNKNOWN]
    by_reason = {}
    for row in refused:
        by_reason[row["why"]] = by_reason.get(row["why"], 0) + 1
    if not refusals_visible:
        # AN UNDERCOUNT PRESENTED AS A COUNT IS THE DEFECT. At least one
        # record's timeline could not be built, so refusals for it are
        # structurally invisible and `len(refused)` is a floor rather than a
        # figure. UNKNOWN, and `unaccounted` with it because it is derived
        # from this - never 0, which would read as "nothing refused".
        return {
            "attempted": len(rows),
            "approved_cohort": approved_cohort,
            "cohort_touched": cohort_size,
            "sent": len(sent),
            "refused": None,
            "refused_at_least": len(refused),
            "refused_by_reason": {},
            "unaccounted": None,
            "unaccounted_rows": unaccounted,
            "has_unaccounted": True,
            "refusals_visible": False,
        }
    return {
        "attempted": len(rows),
        # None, not 0: nobody has told this page how big the approved cohort
        # is, and 0 would read as "nothing was approved".
        "approved_cohort": approved_cohort,
        "cohort_touched": cohort_size,
        "sent": len(sent),
        "refused": len(refused),
        "refused_by_reason": dict(sorted(by_reason.items(),
                                         key=lambda kv: -kv[1])),
        "unaccounted": len(unaccounted),
        # THE ONE THE PAGE MUST SHOUT ABOUT. Non-zero means rows were acted
        # on and this page cannot say what happened to them, which is the
        # same defect as a hand-kept denominator.
        "unaccounted_rows": unaccounted,
        "has_unaccounted": bool(unaccounted),
        "refused_at_least": len(refused),
        "refusals_visible": True,
    }


# -------------------------------------------------------------- the controls
#
# THREE, RUN ON EVERY RENDER, each printing PASS or FAIL. The third is the
# load-bearing one: the first two are satisfied by a reader that classifies
# nothing, which is this lane's own B7 defect - an instrument reporting clean
# because it watched nothing.

#: A ledger path that must never exist, for the unreadable-ledger control.
#: Asserted absent by the control itself, so it cannot quietly go vacuous.
ABSENT_LEDGER = "a-provider-write-ledger-that-must-not-exist.jsonl"

#: A touch state that is deliberately not in `touch.STATES`. This is what a
#: row the page cannot classify looks like, and it is how control 3 proves
#: `unaccounted` can actually become non-zero.
PLANTED_UNCLASSIFIABLE = "a_state_no_module_defines"


def controls(now=None):
    """The three controls, each with a PASS or a FAIL and a reason.

    A FAIL is not a footnote: `report` turns every figure UNKNOWN, because a
    reader that cannot be shown to work has no standing to report a count.
    """
    import os
    import tempfile

    now = now or datetime.datetime.now()
    results = []

    # 1. An unreadable ledger makes the refusal figure UNKNOWN, not zero.
    path = os.path.join(tempfile.gettempdir(), ABSENT_LEDGER)
    exists = os.path.exists(path)
    found = campaign_refusals(path=path)
    ok = (not exists) and found["state"] == LEDGER_ABSENT
    results.append({
        "name": "an_unreadable_ledger_is_unknown_not_zero",
        "what": "a ledger that cannot be read makes the refusal count "
                "UNKNOWN rather than 0",
        "ok": ok,
        "detail": ("the fixture path exists, so this control measures "
                   "nothing" if exists else
                   "an absent ledger reported state=%s with no rows"
                   % found["state"] if ok else
                   "an absent ledger reported state=%s" % found["state"])})

    # 2. A planted refusal appears as REFUSED, with its reason.
    outcome, why = classify(touch.BLOCKED)
    ok = outcome == REFUSED and bool(why)
    results.append({
        "name": "a_planted_refusal_is_refused_with_its_reason",
        "what": "a step in a refusing state classifies as REFUSED and "
                "carries a reason",
        "ok": ok,
        "detail": ("a %r step classified %s - %s" % (touch.BLOCKED, outcome,
                                                     why) if ok else
                   "a %r step classified %r" % (touch.BLOCKED, outcome))})

    # 3. A planted row that classifies as NEITHER lands in `unaccounted` and
    #    raises the warning. Without this the two above are satisfied by a
    #    reader that classifies everything as refused, or as nothing.
    outcome, why = classify(PLANTED_UNCLASSIFIABLE)
    tally = counters([{"outcome": outcome, "why": why}])
    ok = (outcome == UNKNOWN and tally["unaccounted"] == 1
          and tally["has_unaccounted"] and tally["attempted"] == 1
          and tally["sent"] == 0 and tally["refused"] == 0)
    results.append({
        "name": "an_unclassifiable_row_lands_in_unaccounted",
        "what": "a row that is neither sent nor refused is counted as "
                "attempted AND as unaccounted, and raises the warning",
        "ok": ok,
        "detail": ("attempted=1 sent=0 refused=0 unaccounted=1, warning "
                   "raised" if ok else
                   "attempted=%s sent=%s refused=%s unaccounted=%s"
                   % (tally["attempted"], tally["sent"], tally["refused"],
                      tally["unaccounted"]))})
    return results


# ---------------------------------------------------------------- the report

def report(records, now=None, config=None, ledger_path=None, tenant=None,
           approved_cohort=None, timelines=None):
    """The rows, the four counters, and the controls that watched the read."""
    now = now or datetime.datetime.now()
    checks = controls(now=now)
    failed = [check["name"] for check in checks if not check["ok"]]

    rows, cohort_size, blind = rows_for(records, now=now, config=config,
                                        timelines=timelines)
    tally = counters(rows, cohort_size=cohort_size,
                     approved_cohort=approved_cohort,
                     refusals_visible=not blind)
    refusals = campaign_refusals(path=ledger_path, tenant=tenant)

    poison = None
    if failed:
        poison = ("this page's own control(s) %s FAILED, so its reader "
                  "cannot be shown to work and NO figure on it may be "
                  "believed. Every count is UNKNOWN and every row's outcome "
                  "is UNKNOWN until that is fixed." % ", ".join(failed))
        # EVERY COUNT BECOMES UNKNOWN - None, never 0, because a zero here
        # reads as "nothing went out" which is the most dangerous possible
        # answer on this particular page.
        for key in ("attempted", "sent", "refused", "unaccounted"):
            tally[key] = None
        tally["refused_by_reason"] = {}
        # Nothing is accounted for when the reader is not trusted, so the
        # alarm stays raised rather than going quiet because the count that
        # raised it has just been set to UNKNOWN.
        tally["has_unaccounted"] = True
        # The row's recorded STATE is kept verbatim. What is untrusted when a
        # control fails is this page's reader, not the event log, and
        # discarding what the log said would destroy information rather than
        # flag it.
        for row in rows:
            row["outcome"] = UNKNOWN
            row["outcome_label"] = OUTCOME_TEXT[UNKNOWN][0]
            row["why"] = poison

    return {
        "rendered_at": now.replace(microsecond=0).isoformat(" "),
        "controls": checks,
        "controls_ok": not failed,
        "controls_failed": failed,
        "poison": poison,
        "rows": rows,
        "counters": tally,
        "refusals": refusals,
        # The records whose cadence timeline could not be built. While this
        # is non-empty the refusal count is UNKNOWN, because refusals for
        # those records cannot appear at all - see `_timelines_for`.
        "blind": blind,
        "outcome_glossary": [{"label": label, "why": why}
                             for label, why in OUTCOME_TEXT.values()],
        # THE SENTENCE THAT MUST BE ON THE PAGE. Not a footnote and not in
        # this docstring only: the event log is the writer's own record.
        "cannot_see": (
            "This page reads the WRITER's own record. A message that left "
            "the provider and then bounced at the recipient, landed in "
            "spam, or was never transmitted despite an accepted API call is "
            "NOT here unless a webhook wrote it back. A clean screen is "
            "therefore not a clean send, and open tracking reads 0 across "
            "all 181 mailboxes in this estate so no metric may be built on "
            "it."),
        "authorities": [
            {"figure": "every prospect row",
             "source": "the record event log, read through `src.touch`",
             "why": "the canonical touch history. A state is established by "
                    "a confirming event, never by a payload having been "
                    "built"},
            {"figure": "refused, by campaign",
             "source": "`provider-writes.jsonl`, via `src.providerwrites`",
             "why": "VERB-level and not per person. It can say a write was "
                    "refused on a campaign; it cannot say which prospect "
                    "that cost, so it is never joined onto a row above"},
            {"figure": "the approved cohort size",
             "source": "the approval sheet, OUTSIDE this repository",
             "why": "it names real prospects and is not in git. When it is "
                    "not supplied the denominator is UNKNOWN - never the "
                    "number of rows found, which would agree with itself "
                    "whatever happened"},
        ],
    }


def describe(data):
    """The page as text, for a terminal. Same reader, same refusals."""
    out = ["CANARY-01 send log - read at %s" % data["rendered_at"], ""]
    for check in data["controls"]:
        out.append("  %-4s %-44s %s" % ("PASS" if check["ok"] else "FAIL",
                                        check["name"], check["detail"]))
    out.append("")
    if data["poison"]:
        out.append("  " + data["poison"])
        out.append("")
    tally = data["counters"]

    def figure(value):
        """UNKNOWN, never 0. A zero on this page reads as 'nothing went
        out', which is the most dangerous wrong answer it could give."""
        return "UNKNOWN" if value is None else str(value)

    out.append("  attempted    %s of %s approved"
               % (figure(tally["attempted"]),
                  figure(tally["approved_cohort"])))
    out.append("  sent         %s of %s attempted"
               % (figure(tally["sent"]), figure(tally["attempted"])))
    out.append("  refused      %s of %s attempted"
               % (figure(tally["refused"]), figure(tally["attempted"])))
    out.append("  unaccounted  %s%s"
               % (figure(tally["unaccounted"]),
                  "   <-- ROWS THIS PAGE CANNOT CLASSIFY"
                  if tally["has_unaccounted"] else ""))
    out.append("")
    for row in data["rows"][:40]:
        out.append("  %-20s %-34s %-9s %-5s %-14s %s"
                   % (row["at"] or "UNKNOWN", row["address"] or "UNKNOWN",
                      row["channel"] or "UNKNOWN", row["step"] or "UNKNOWN",
                      row["sender_id"] or "UNKNOWN", row["outcome_label"]))
    out.append("")
    out.append("  " + data["cannot_see"])
    return "\n".join(out)
