#!/usr/bin/env python3
"""Render the cadence as the operator sees it in the review.

TASK-343. The old preview in `work/v2_pages.py` hardcoded the LinkedIn days
(1, 3, 8, 14) instead of reading them from the graph. Days 8 and 14 were
invented - 8 is em3's day and 14 is nothing's. The real LinkedIn days are
1, 3, 6, 10, 15. This script reads them from `src/cadencelibrary.py` and
renders what the graph actually says.

USAGE:
    py -3 scripts/preview_cadence.py
    py -3 scripts/preview_cadence.py --sequence productive_li_heavy_v1
    py -3 scripts/preview_cadence.py --format text
    py -3 scripts/preview_cadence.py --format html --out work/review/preview.html

READS ONLY. No provider, no credential, no send.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import cadencelibrary  # noqa: E402


# The branch labels for LinkedIn steps. A step with `requires: connected`
# walks the connected branch; a step with an alternative requiring
# `connection_not_accepted` walks the not-connected branch for that
# alternative. Steps with neither walk both.
CONNECTED = cadencelibrary.CONNECTED
CONNECTION_NOT_ACCEPTED = cadencelibrary.CONNECTION_NOT_ACCEPTED
OPEN_PROFILE = cadencelibrary.OPEN_PROFILE


def _branch_label(step):
    """Which branch this step sits on, as a human-readable label.

    A step with `requires: connected` is on the connected branch. A step
    with an alternative requiring `connection_not_accepted` has a
    not-connected alternative. A step with neither walks both branches.
    """
    requires = step.get("requires")
    alt = step.get("alternative", {})
    alt_requires = alt.get("requires") if alt else None

    if requires == CONNECTED:
        return "connected"
    if requires == CONNECTION_NOT_ACCEPTED:
        return "not-connected"
    if alt_requires == CONNECTION_NOT_ACCEPTED:
        return "connected + not-connected (inmail fallback)"
    if requires == OPEN_PROFILE:
        return "open-profile"
    return "both"


def _action_label(step):
    """What the LinkedIn step does, as a human-readable label."""
    action = step.get("linkedin_action", "")
    labels = {
        "connect": "connection request",
        "message": "message",
        "inmail": "InMail",
        "open_profile_message": "Open Profile message",
    }
    return labels.get(action, action)


def render_steps(sequence):
    """Render every step in the sequence as a list of dicts.

    Each dict has: key, day, channel, action (LinkedIn only), branch
    (LinkedIn only), and any alternative the step carries.

    This is the load-bearing function. It reads `day` from the step dict
    in the graph, not from any local table.
    """
    rows = []
    for step in sequence:
        row = {
            "key": step["key"],
            "day": step["day"],
            "channel": step["channel"],
        }
        if step["channel"] == "linkedin":
            row["action"] = _action_label(step)
            row["branch"] = _branch_label(step)
            alt = step.get("alternative")
            if alt:
                row["alternative"] = {
                    "action": _action_label(alt),
                    "requires": alt.get("requires", ""),
                    "branch": _branch_label(alt),
                }
        rows.append(row)
    return rows


def format_text(rows, name="productive_li_heavy_v1"):
    """Render the steps as a plain-text table."""
    lines = []
    lines.append("Cadence: %s" % name)
    lines.append("=" * 72)
    lines.append("%-6s  %4s  %-10s  %-24s  %s" % (
        "key", "day", "channel", "action", "branch"))
    lines.append("-" * 72)
    for row in rows:
        action = row.get("action", "")
        branch = row.get("branch", "")
        lines.append("%-6s  %4d  %-10s  %-24s  %s" % (
            row["key"], row["day"], row["channel"], action, branch))
        alt = row.get("alternative")
        if alt:
            lines.append("       %4s             %-24s  %s (alt: %s)" % (
                "", "", alt["action"], alt["requires"]))
    lines.append("-" * 72)

    # Summary: LinkedIn steps with their real days.
    li_steps = [r for r in rows if r["channel"] == "linkedin"]
    lines.append("")
    lines.append("LinkedIn steps: %d" % len(li_steps))
    for s in li_steps:
        lines.append("  %s  day %d  %s  [%s]" % (
            s["key"], s["day"], s["action"], s["branch"]))
    return "\n".join(lines)


def format_html(rows, name="productive_li_heavy_v1"):
    """Render the steps as an HTML table."""
    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("<title>Cadence Preview: %s</title>" % name)
    parts.append("<style>")
    parts.append("body { font-family: monospace; margin: 2em; }")
    parts.append("table { border-collapse: collapse; }")
    parts.append("th, td { border: 1px solid #ccc; padding: 4px 8px; "
                 "text-align: left; }")
    parts.append("th { background: #f0f0f0; }")
    parts.append(".linkedin { background: #e8f0fe; }")
    parts.append(".email { background: #fff8e1; }")
    parts.append("</style></head><body>")
    parts.append("<h1>Cadence: %s</h1>" % name)
    parts.append("<table>")
    parts.append("<tr><th>Key</th><th>Day</th><th>Channel</th>"
                 "<th>Action</th><th>Branch</th></tr>")
    for row in rows:
        css = row["channel"]
        action = row.get("action", "")
        branch = row.get("branch", "")
        parts.append("<tr class='%s'><td>%s</td><td>%d</td><td>%s</td>"
                     "<td>%s</td><td>%s</td></tr>" % (
                         css, row["key"], row["day"], row["channel"],
                         action, branch))
        alt = row.get("alternative")
        if alt:
            parts.append(
                "<tr class='%s'><td></td><td></td><td></td>"
                "<td>%s</td><td>%s (alt: %s)</td></tr>" % (
                    css, alt["action"], branch, alt["requires"]))
    parts.append("</table>")

    li_steps = [r for r in rows if r["channel"] == "linkedin"]
    parts.append("<h2>LinkedIn steps (%d)</h2>" % len(li_steps))
    parts.append("<ul>")
    for s in li_steps:
        parts.append("<li><b>%s</b> day %d &mdash; %s [%s]</li>" % (
            s["key"], s["day"], s["action"], s["branch"]))
    parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def format_json(rows, name="productive_li_heavy_v1"):
    """Render the steps as JSON."""
    return json.dumps({"cadence": name, "steps": rows}, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sequence", default="productive_li_heavy_v1",
                        help="the cadence name from cadencelibrary.SEQUENCES")
    parser.add_argument("--format", choices=("text", "html", "json"),
                        default="text")
    parser.add_argument("--out", help="write to this file instead of stdout")
    args = parser.parse_args(argv)

    sequence = cadencelibrary.named(args.sequence)
    if sequence is None:
        print("ERROR: unknown sequence %r" % args.sequence, file=sys.stderr)
        print("Available: %s" % ", ".join(sorted(cadencelibrary.SEQUENCES)),
              file=sys.stderr)
        return 1

    rows = render_steps(sequence)

    formatters = {
        "text": format_text,
        "html": format_html,
        "json": format_json,
    }
    output = formatters[args.format](rows, name=args.sequence)

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print("Wrote %s" % args.out)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
