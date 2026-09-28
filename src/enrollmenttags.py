#!/usr/bin/env python3
"""Learning tags on every enrolled lead, and the nightly rate report.

## What this is

Seven fields recorded on each lead at enrollment time. Six are closed
vocabularies that refuse unknown values; one (signal) is free text that is
recorded but never parsed for decisions.

    persona           the role pattern the copy was written for
    angle             the argument the opener makes
    subject_variant   the subject line's identity, not its text
    sender            the mailbox, which is also the human
    timezone_cohort   the recipient-local window group
    source            where the lead came from
    signal            the evidence that made it ICP-IN

## Why this exists

Two emails have been sent in this project's history. Every future argument
about what works is settled by whatever was recorded at enrollment, and a
tag that was not written at enrollment cannot be reconstructed afterwards.

## What this is not

Tags are written where the lead lives in OUR state, not at the provider.
Provider custom variables are for merge fields; a learning tag that only
exists at EmailBison is a tag we cannot join against replies.

## The nightly report

Per tag value, per campaign, and overall: enrolled, sent, replied, positive,
bounced, unsubscribed. Every rate names its denominator. A cell with fewer
than 30 sends prints the count and refuses the percentage.
"""
import datetime

# ------------------------------------------------------------------ sources
#
# Where a lead came from. Closed: a source not in this set is refused,
# because a tag that silently accepts anything measures nothing.

SUPPLIER_FILE = "supplier_file"
NIGHTLY_SOURCING = "nightly_sourcing"
READY_RESERVOIR = "ready_reservoir"
REENGAGEMENT = "reengagement"

SOURCE_VALUES = (SUPPLIER_FILE, NIGHTLY_SOURCING, READY_RESERVOIR,
                 REENGAGEMENT)

# --------------------------------------------------------- timezone cohorts
#
# Recipient-local window groups. These determine when a lead is enrolled
# for sending, and the cohort is recorded so the report can separate
# "enrolled at 9am their time" from "enrolled at 3am their time".

AMERICAS = "americas"
EMEA = "emea"
APAC = "apac"

TIMEZONE_COHORT_VALUES = (AMERICAS, EMEA, APAC)

# --------------------------------------------------------- the seven fields
#
# Six are closed; signal is free text. The closed fields are validated
# either against a fixed set (source, timezone_cohort) or against a
# caller-supplied vocabulary (persona, angle, subject_variant, sender)
# because those depend on the client config and campaign.

CLOSED_FIXED = {
    "source": SOURCE_VALUES,
    "timezone_cohort": TIMEZONE_COHORT_VALUES,
}

CLOSED_DYNAMIC = ("persona", "angle", "subject_variant", "sender")

ALL_FIELDS = ("persona", "angle", "subject_variant", "sender",
              "timezone_cohort", "source", "signal")

# The tag key on the record.
TAG_KEY = "learning_tags"


# ----------------------------------------------------------- validation

class UnknownTagValue(ValueError):
    """A learning tag value is not in its closed vocabulary.

    Raised rather than coerced: a tag that silently accepts anything
    measures nothing. The caller supplies the value; the vocabulary
    decides whether it is valid.
    """


def validate(tags, vocabularies=None):
    """Return a list of problems. Empty list means every tag is valid.

    `vocabularies` is a dict of {field: allowed_values} for the dynamic
    fields (persona, angle, subject_variant, sender). The fixed fields
    (source, timezone_cohort) are always checked against their built-in
    sets. Signal is free text and is never validated.
    """
    vocabularies = vocabularies or {}
    problems = []

    for field in ALL_FIELDS:
        value = tags.get(field)
        if value is None:
            continue

        if field == "signal":
            if not isinstance(value, str) or not value.strip():
                problems.append(f"signal must be a non-empty string, "
                                f"got {value!r}")
            continue

        if field in CLOSED_FIXED:
            allowed = CLOSED_FIXED[field]
            if value not in allowed:
                problems.append(
                    f"{field}: unknown value {value!r}, "
                    f"expected one of {allowed}")
            continue

        if field in CLOSED_DYNAMIC:
            allowed = vocabularies.get(field)
            if allowed is None:
                problems.append(
                    f"{field}: no vocabulary supplied for validation")
                continue
            if value not in allowed:
                problems.append(
                    f"{field}: unknown value {value!r}, "
                    f"not in the supplied vocabulary")
            continue

    return problems


def refuse_unknown(tags, vocabularies=None):
    """Validate and raise on the first problem.

    Returns the tags dict unchanged if valid. Raises UnknownTagValue with
    every problem named if not.
    """
    problems = validate(tags, vocabularies)
    if problems:
        raise UnknownTagValue("; ".join(problems))
    return dict(tags)


# --------------------------------------------------------- apply / backfill

def apply(record, tags, vocabularies=None):
    """Write learning tags onto a record. Refuses unknown values.

    The tags are stored under `learning_tags` on the record. An existing
    tag set is replaced; partial updates are the caller's responsibility
    (merge before calling).

    Returns the record.
    """
    refuse_unknown(tags, vocabularies)
    record[TAG_KEY] = dict(tags)
    return record


def backfill(record, artifact, vocabularies=None):
    """Tag a lead that was enrolled before this task existed.

    `artifact` is the enrollment context: the campaign, the copy, the
    sender assignment - whatever carries the evidence for what the tags
    should be. The caller extracts the tag values from it; this function
    validates and writes them.

    The difference from `apply` is intent: `apply` is for new enrollments,
    `backfill` is for leads already in the queue. Both validate, both
    refuse unknown values, and both write the same structure. The
    distinction is in the caller, not in this function.

    Returns the record.
    """
    tags = {}
    for field in ALL_FIELDS:
        value = artifact.get(field)
        if value is not None:
            tags[field] = value
    return apply(record, tags, vocabularies)


def tags_on(record):
    """The learning tags on a record, or an empty dict if none."""
    return dict(record.get(TAG_KEY) or {})


# --------------------------------------------------------- nightly report
#
# Per tag value, per campaign, and overall. Every rate names its
# denominator. A cell with fewer than 30 sends refuses its percentage.

MINIMUM_SENDS_FOR_RATE = 30

# The outcome columns.
ENROLLED = "enrolled"
SENT = "sent"
REPLIED = "replied"
POSITIVE = "positive"
BOUNCED = "bounced"
UNSUBSCRIBED = "unsubscribed"

OUTCOME_FIELDS = (ENROLLED, SENT, REPLIED, POSITIVE, BOUNCED, UNSUBSCRIBED)

# Rates that need a denominator. Each names which denominator it uses.
RATE_DEFINITIONS = {
    "reply_rate": {"numerator": REPLIED, "denominator": SENT,
                   "label": "replies / sent"},
    "positive_rate": {"numerator": POSITIVE, "denominator": SENT,
                      "label": "positive replies / sent"},
    "bounce_rate": {"numerator": BOUNCED, "denominator": SENT,
                    "label": "bounces / sent"},
    "unsubscribe_rate": {"numerator": UNSUBSCRIBED, "denominator": SENT,
                         "label": "unsubscribes / sent"},
}


class _Cell:
    """One cell of the report: counts and rates for one tag value."""

    def __init__(self, tag_field, tag_value, campaign_id=None):
        self.tag_field = tag_field
        self.tag_value = tag_value
        self.campaign_id = campaign_id
        self.counts = {field: 0 for field in OUTCOME_FIELDS}

    def add(self, outcome_field, n=1):
        self.counts[outcome_field] = self.counts.get(outcome_field, 0) + n

    def to_dict(self):
        sent = self.counts[SENT]
        result = {
            "tag_field": self.tag_field,
            "tag_value": self.tag_value,
            "campaign_id": self.campaign_id,
            "counts": dict(self.counts),
        }
        rates = {}
        for rate_name, defn in RATE_DEFINITIONS.items():
            num = self.counts[defn["numerator"]]
            den = self.counts[defn["denominator"]]
            if den < MINIMUM_SENDS_FOR_RATE:
                rates[rate_name] = {
                    "value": None,
                    "refused": True,
                    "reason": f"{den} sends, below the {MINIMUM_SENDS_FOR_RATE} "
                              f"minimum",
                    "numerator": num,
                    "denominator": den,
                    "label": defn["label"],
                }
            else:
                rates[rate_name] = {
                    "value": num / den if den else 0.0,
                    "refused": False,
                    "numerator": num,
                    "denominator": den,
                    "label": defn["label"],
                }
        result["rates"] = rates
        return result


def _lead_outcomes(record):
    """What happened to this lead, from its record state and events."""
    outcomes = {field: 0 for field in OUTCOME_FIELDS}
    outcomes[ENROLLED] = 1

    state = record.get("state", "")
    events = record.get("events") or []

    if state in ("pushed", "approved"):
        outcomes[SENT] = 1
    for event in events:
        etype = event.get("type", "")
        if etype == "confirmed_touch":
            outcomes[SENT] = 1
        elif etype == "reply":
            outcomes[REPLIED] = 1
            if event.get("sentiment") == "positive":
                outcomes[POSITIVE] = 1
        elif etype == "bounce":
            outcomes[BOUNCED] = 1
        elif etype == "unsubscribe":
            outcomes[UNSUBSCRIBED] = 1

    contacts = record.get("contacts") or []
    for contact in contacts:
        if contact.get("unsubscribed"):
            outcomes[UNSUBSCRIBED] = 1
        if contact.get("bounced"):
            outcomes[BOUNCED] = 1

    return outcomes


def nightly_report(records, campaigns=None, tag_fields=None):
    """The nightly rate report.

    Per tag value, per campaign, and overall. Every rate names its
    denominator. A cell with fewer than 30 sends refuses its percentage.

    `records` is the queue (or a filtered subset). `campaigns` is the
    campaign file rows, used to map record ids to campaign ids. If None,
    every lead is reported under campaign_id=None.

    `tag_fields` limits which tag dimensions are reported. Default: all
    seven.

    Returns a dict with `cells` (one per tag-value x campaign combination),
    `overall` (one per campaign plus one grand total), and `generated_at`.
    """
    tag_fields = tag_fields or list(ALL_FIELDS)
    campaigns = campaigns or []

    rec_to_campaign = {}
    for camp in campaigns:
        for rid in (camp.get("record_ids") or []):
            rec_to_campaign[rid] = camp.get("campaign_id")

    cells = {}

    def get_cell(field, value, camp_id):
        key = (field, value, camp_id)
        if key not in cells:
            cells[key] = _Cell(field, value, camp_id)
        return cells[key]

    for record in records:
        tags = tags_on(record)
        if not tags:
            continue
        camp_id = rec_to_campaign.get(record.get("id"))
        outcomes = _lead_outcomes(record)

        for field in tag_fields:
            value = tags.get(field)
            if value is None:
                continue

            if camp_id is not None:
                cell = get_cell(field, value, camp_id)
                for outcome_field, count in outcomes.items():
                    if count:
                        cell.add(outcome_field, count)

            overall_cell = get_cell(field, value, None)
            for outcome_field, count in outcomes.items():
                if count:
                    overall_cell.add(outcome_field, count)

    result_cells = [cell.to_dict() for cell in cells.values()
                    if cell.campaign_id is not None]
    overall_cells = [cell.to_dict() for cell in cells.values()
                     if cell.campaign_id is None]

    return {
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "minimum_sends_for_rate": MINIMUM_SENDS_FOR_RATE,
        "cells": result_cells,
        "overall": overall_cells,
        "rate_definitions": {
            name: {"label": defn["label"],
                   "denominator": defn["denominator"]}
            for name, defn in RATE_DEFINITIONS.items()
        },
    }


# --------------------------------------------------------- campaign wiring
#
# The consumption point: a campaign's records must carry learning tags
# before it can be staged. This is what makes the schema real rather than
# a module that exists.

def campaign_tag_report(campaign, recs):
    """Tag coverage for a campaign's records.

    Returns a dict with `total` (records in the campaign), `tagged` (records
    carrying learning_tags), `untagged` (record ids without tags), and
    `coverage` (fraction tagged). A campaign with zero tagged records has
    coverage 0.0; a campaign with every record tagged has 1.0.

    This is the function the staging path calls to decide whether a campaign
    is measurable. A campaign that ships without tags is a campaign whose
    results cannot be attributed to any persona, angle, subject, sender,
    timezone, source or signal - and that is the campaign this task exists
    to prevent.
    """
    record_ids = campaign.get("record_ids") or []
    by_id = {r["id"]: r for r in recs}
    tagged = 0
    untagged = []
    for rid in record_ids:
        rec = by_id.get(rid)
        if rec is None:
            continue
        if tags_on(rec):
            tagged += 1
        else:
            untagged.append(rid)
    total = len(record_ids)
    return {
        "campaign_id": campaign.get("campaign_id"),
        "total": total,
        "tagged": tagged,
        "untagged": untagged,
        "coverage": tagged / total if total else 0.0,
    }


# --------------------------------------------------------- CLI
#
# python -m src.enrollmenttags report [--campaign ID] [--json]
#
# The nightly rate report. Reads the queue and campaigns, produces the
# report. Without --campaign, reports across every campaign.

def main(argv=None):
    import argparse
    import json as _json

    from src import campaigns as _campaigns
    from src import store as _store

    p = argparse.ArgumentParser(
        prog="python -m src.enrollmenttags",
        description=__doc__)
    sub = p.add_subparsers(dest="command")

    report_p = sub.add_parser("report", help="the nightly rate report")
    report_p.add_argument("--campaign", help="limit to one campaign")
    report_p.add_argument("--json", action="store_true",
                          help="output as JSON")

    check_p = sub.add_parser("check",
                             help="tag coverage for a campaign")
    check_p.add_argument("--campaign", required=True,
                         help="campaign id to check")
    check_p.add_argument("--json", action="store_true")

    a = p.parse_args(argv)

    if a.command == "report":
        recs = _store.load()
        camp_rows = _campaigns.load()
        if a.campaign:
            camp = _campaigns.get(a.campaign, camp_rows)
            if camp is None:
                print(f"REFUSED: no such campaign: {a.campaign}")
                return 2
            camp_rows = [camp]
        report = nightly_report(recs, campaigns=camp_rows)
        if a.json:
            print(_json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_report(report)
        return 0

    if a.command == "check":
        recs = _store.load()
        camp_rows = _campaigns.load()
        camp = _campaigns.get(a.campaign, camp_rows)
        if camp is None:
            print(f"REFUSED: no such campaign: {a.campaign}")
            return 2
        result = campaign_tag_report(camp, recs)
        if a.json:
            print(_json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"campaign {result['campaign_id']}: "
                  f"{result['tagged']}/{result['total']} tagged "
                  f"({result['coverage']:.0%})")
            if result["untagged"]:
                print(f"  untagged: {', '.join(result['untagged'][:10])}")
        return 0

    p.print_help()
    return 0


def _print_report(report):
    """Human-readable nightly report."""
    print(f"Generated: {report['generated_at']}")
    print(f"Minimum sends for rate: {report['minimum_sends_for_rate']}")
    print()

    if not report["overall"]:
        print("No tagged records found.")
        return

    print("=== OVERALL ===")
    for cell in report["overall"]:
        _print_cell(cell)

    if report["cells"]:
        print()
        print("=== PER CAMPAIGN ===")
        for cell in report["cells"]:
            _print_cell(cell)


def _print_cell(cell):
    """One cell of the report, printed."""
    label = f"[{cell['tag_field']}={cell['tag_value']}]"
    if cell["campaign_id"]:
        label += f" (campaign {cell['campaign_id']})"
    print(label)
    counts = cell["counts"]
    print(f"  enrolled={counts['enrolled']}  sent={counts['sent']}  "
          f"replied={counts['replied']}  positive={counts['positive']}  "
          f"bounced={counts['bounced']}  unsubscribed={counts['unsubscribed']}")
    for rate_name, rate in cell["rates"].items():
        if rate["refused"]:
            print(f"  {rate_name}: REFUSED ({rate['reason']})")
        else:
            print(f"  {rate_name}: {rate['value']:.1%} "
                  f"({rate['label']}: {rate['numerator']}/{rate['denominator']})")
    print()


if __name__ == "__main__":
    import sys
    sys.exit(main())
