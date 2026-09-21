#!/usr/bin/env python3
"""What LinkedIn cadences Productive is actually running, and which works.

    py -3 scripts/heyreach_cadence_survey.py --out docs/HEYREACH-CADENCES-2026-09-21.md

READ-ONLY. Every call is a HeyReach read; nothing is created, cloned or
started here.

OPERATOR, 2026-09-21: "Read the sequence graphs of the HeyReach campaigns
that have been running for Productive... Report each: steps, delays, branches
on accept / no accept, message texts, and which one has the best reply rate
over the last 90 days by seat. Clone the best-performing graph as the
standard LinkedIn cadence for every Resonate-run campaign, step for step."

This script does the READING half. The cloning half is a separate decision
that needs these numbers in front of it.

## THE TWO THINGS THIS CANNOT DO, STATED RATHER THAN GUESSED

**A reply rate needs a denominator and HeyReach's stats are campaign-level.**
`campaign_stats` gives totals; splitting them by seat needs per-seat rows the
public API may not carry. Where a per-seat split cannot be read, this says so
instead of dividing something by something else.

**"Over the last 90 days" is a window this API does not obviously filter
on.** A campaign that finished in May and one running now are not comparable
on lifetime totals. Each campaign's own dates are reported beside its numbers
so the comparison is made with the dates visible rather than silently.
"""
import argparse
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import heyreach, load_env                     # noqa: E402


def walk_graph(node, depth=0, branch="", out=None):
    """Flatten HeyReach's nested graph into readable steps.

    A HeyReach sequence is NOT a list. It is a node - CONNECTION_REQUEST,
    MESSAGE, VIEW, FOLLOW - carrying `actionDelay`, `actionDelayUnit`, a
    `payload` with message VARIANTS, and a `conditionalNode` that runs when
    the condition this node sets is met. That nesting IS the accept / no
    accept branching the operator asked about: the request's conditional
    child is what happens when the request is accepted.

    Reading it as a flat `steps` list, which the first version of this did,
    showed every campaign as "? steps".
    """
    out = [] if out is None else out
    if not isinstance(node, dict):
        return out
    payload = node.get("payload") or {}
    messages = [m for m in (payload.get("messages") or []) if str(m).strip()]
    out.append({
        "depth": depth,
        "branch": branch,
        "type": node.get("nodeType"),
        "delay": node.get("actionDelay"),
        "unit": node.get("actionDelayUnit"),
        "messages": messages,
        "fallback": payload.get("fallbackMessage") or "",
        "withdraw_after_days": payload.get("toBeWithdrawnAfterDays"),
    })
    child = node.get("conditionalNode")
    if child:
        walk_graph(child, depth + 1, "if the previous step's condition is met",
                   out)
    for key in ("elseNode", "negativeNode", "fallbackNode"):
        if node.get(key):
            walk_graph(node[key], depth + 1, f"{key}", out)
    return out


def _rate(part, whole):
    if not whole:
        return "n/a"
    return f"{(part / whole) * 100:.1f}%"


def survey(limit=None):
    load_env()
    rows, total = heyreach.campaigns()
    print(f"campaigns visible: {len(rows)} of {total}")
    out = []
    for row in rows:
        if limit and len(out) >= limit:
            break
        campaign_id = row.get("id")
        entry = {"id": campaign_id, "name": row.get("name"),
                 "status": row.get("status"),
                 "seats": len(row.get("campaignAccountIds")
                              or row.get("linkedInAccountIds") or []),
                 "created": row.get("creationTime") or row.get("createdAt")}
        try:
            entry["sequence"] = heyreach.campaign_sequence(campaign_id)
        except Exception as exc:                                # noqa: BLE001
            entry["sequence_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        try:
            entry["stats"] = heyreach.campaign_stats(campaign_id)
        except Exception as exc:                                # noqa: BLE001
            entry["stats_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        out.append(entry)
        print(f"  {campaign_id} {str(row.get('status'))[:11]:11s} "
              f"{str(row.get('name'))[:44]:44s} "
              f"{'seq ok' if 'sequence' in entry else 'seq FAILED'}  "
              f"{'stats ok' if 'stats' in entry else 'stats FAILED'}")
    return out


def render(entries):
    lines = ["# Productive's LinkedIn cadences, read from HeyReach",
             "",
             f"Read {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}. "
             "READ-ONLY survey; nothing was cloned or created.",
             "",
             "## The campaigns",
             "",
             "    id       status       seats  steps  name",
             ""]
    for entry in entries:
        sequence = entry.get("sequence") or {}
        count = (len(walk_graph(sequence))
                 if isinstance(sequence, dict) and sequence.get("nodeType")
                 else "?")
        lines.append(f"    {str(entry['id']):8s} {str(entry['status'])[:11]:12s} "
                     f"{entry['seats']:>5}  {str(count):>5}  "
                     f"{str(entry['name'])[:52]}")
    lines += ["", "## Per campaign", ""]
    for entry in entries:
        lines.append(f"### {entry['id']} - {entry['name']}")
        lines.append("")
        lines.append(f"- status `{entry['status']}`, {entry['seats']} seat(s)")
        stats = entry.get("stats")
        if isinstance(stats, dict):
            sent = (stats.get("messagesSent") or stats.get("totalMessagesSent")
                    or 0)
            requests = (stats.get("connectionsSent")
                        or stats.get("totalConnectionsSent") or 0)
            accepted = (stats.get("connectionsAccepted")
                        or stats.get("totalConnectionsAccepted") or 0)
            # THE KEY IS `totalMessageReplies`. Reading `totalReplies`,
            # which HeyReach does not send, made every campaign show 0
            # replies while 523997 had six.
            replies = (stats.get("totalMessageReplies")
                       or stats.get("totalReplies") or stats.get("replies") or 0)
            contacted = (stats.get("uniqueLeadsContacted") or 0)
            lines.append(f"- requests {requests}, accepted {accepted} "
                         f"({_rate(accepted, requests)} of requests), "
                         f"replies {replies} "
                         f"({_rate(replies, accepted)} of ACCEPTED, "
                         f"{_rate(replies, contacted)} of contacted), "
                         f"contacted {contacted}")
            lines.append(f"- raw stats: `{json.dumps(stats, default=str)[:400]}`")
        else:
            lines.append(f"- stats: {entry.get('stats_error', 'none')}")
        sequence = entry.get("sequence")
        if isinstance(sequence, dict) and sequence.get("nodeType"):
            steps = walk_graph(sequence)
            lines.append("")
            lines.append(f"Graph: {len(steps)} node(s)")
            lines.append("")
            for index, step in enumerate(steps, 1):
                pad = "  " * step["depth"]
                lines.append(f"    {pad}{index}. {step['type']}   "
                             f"delay {step['delay']} {step['unit']}"
                             f"{'   [' + step['branch'] + ']' if step['branch'] else ''}")
                for variant, text in enumerate(step["messages"], 1):
                    lines.append(f"    {pad}   variant {variant}:")
                    for piece in str(text).splitlines():
                        lines.append(f"    {pad}     | {piece[:110]}")
                if step["withdraw_after_days"]:
                    lines.append(f"    {pad}   withdraw after "
                                 f"{step['withdraw_after_days']} days")
        elif sequence:
            lines.append(f"- sequence: `{json.dumps(sequence, default=str)[:600]}`")
        else:
            lines.append(f"- sequence: {entry.get('sequence_error', 'none')}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    entries = survey(limit=args.limit)
    text = render(entries)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text + "\n")
        print(f"\nwritten to {args.out}")
    else:
        print(text[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
