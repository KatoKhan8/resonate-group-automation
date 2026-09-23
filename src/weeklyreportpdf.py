"""The Monday PDF, from the weekly report's own data dict.

OPERATOR, 2026-09-23: "PDF via `clientreport` from the report's data dict
under the new vocabulary."

## WHY THIS IS THREE SECTIONS AND NOT TWENTY-FIVE

`clientreport.build` lays out what it is given and renders a key it cannot
find as "not tracked". Its renderers read **33** keys.
`slackagenttools.weekly_report` produces `accounts`, `replies` and `emails`.

Handing the whole monthly template a dict that feeds three of its
twenty-five sections produces a document that is mostly "Not tracked" boxes -
and a client reading twenty-two of those does not conclude "this is a weekly,
those are monthly questions". They conclude we measured and found nothing.
`SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` §5 measured the overlap at
**one key of thirty-three** before the vocabulary change and refused to ship
the adapter that would have papered over it.

So the weekly document is **short on purpose**: the sections the weekly
report can actually feed, and an appendix that says what a weekly cannot
answer. Absence by omission, not absence dressed as a measurement.

## IT DOES NOT COUNT ANYTHING

Every number here came from `weekly_report`, which read the ledger and the
provider. This module chooses sections and hands over bytes. A second
opinion about any figure would be a fourth place counting a reply, and this
repository already found three.
"""
from . import clientreport

#: The sections a weekly report's data dict can honestly fill.
#:
#: `accounts` is the point of the document - the operator's eight states,
#: the vocabulary decision of 2026-09-23. `replies` reads the reply block.
#: `appendix` is not optional: it is the section that says what this
#: document cannot answer, and dropping it to make the PDF tidier would
#: remove the only page that bounds the rest.
WEEKLY_SECTIONS = ("accounts", "replies", "appendix")

#: `clientreport` has no `weekly` template and this does not add one. MONTHLY
#: is the template whose section table offers `accounts`; the section list
#: above narrows it, which is exactly what `resolve_sections` is for.
TEMPLATE = "monthly"


def sections_available(report):
    """Which of `WEEKLY_SECTIONS` this particular report can actually fill.

    A weekly whose reply ledger could not be read should not print a Reply
    Analysis page saying "not tracked" - the Slack post already carries
    `replies_error` and saying it twice in two registers is how a transient
    read failure starts looking like a finding about the client.
    """
    out = ["accounts"]
    if report.get("replies") is not None:
        out.append("replies")
    out.append("appendix")
    return [s for s in WEEKLY_SECTIONS if s in out]


def build(report, workspace_name, meta=None):
    """The weekly PDF as bytes, from `weekly_report`'s return value.

    `report` is that dict unchanged - not a translation of it. That is the
    operator's decision: one vocabulary, so the thing the Slack post is
    written from and the thing the PDF is laid out from are the same object.
    """
    if not isinstance(report, dict) or "accounts" not in report:
        raise ValueError(
            "the weekly PDF needs weekly_report's dict, with `accounts`")

    full = dict(meta or {})
    full.setdefault("template", TEMPLATE)
    full.setdefault("workspace_slug", report.get("workspace") or "-")
    full.setdefault("workspace_name", workspace_name)
    full.setdefault("title", "Weekly Report")
    full.setdefault("template_label", "Weekly Report")
    full.setdefault("period", "The week to %s"
                    % str(report.get("read_at") or "")[:10])

    return clientreport.build(report, full, sections_available(report))
