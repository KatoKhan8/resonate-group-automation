#!/usr/bin/env python3
"""Which loops beat on a TIMER, and which only when traffic arrives.

    py -3 scripts/heartbeat_inventory.py [--json out.json]

READ-ONLY AND SOURCE-ONLY. It parses `scripts/*.py` with `ast` and reports,
per loop, every `watchsink.beat` / local `heartbeat(...)` call site and
whether that site sits on the unconditional path of the loop body or behind
a condition that only holds when something arrived.

IT DOES NOT READ `work/`. Live heartbeat freshness is a different question
and production state is out of scope here, so this answers the STRUCTURAL
one: can this loop's heartbeat distinguish "alive and idle" from "dead"?
If every write is traffic-gated, the answer is no, whatever the files say.

## THE CONTRACT THE PRIMITIVE ALREADY CLAIMS

`src/watchsink.py:beat` documents itself as "Called on EVERY poll including
the ones that emit nothing, which is the whole point: the event log going
quiet and the watcher dying look identical from the outside and this is
what separates them."

So the primitive is not the defect. A loop that beats only per envelope is
violating a contract its own helper states, and this names which ones do.

## WHAT "UNCONDITIONAL" MEANS HERE, PRECISELY

A beat is TIMER-DRIVEN when it is reached on every iteration of the loop
that also sleeps - i.e. it is a direct statement of the `while` body, or of
a `try` directly in that body, with no `if` between it and the loop. It is
TRAFFIC-GATED when an `if`/`for` over incoming items stands between them.
A `for ... in envelopes(...)` counts as traffic-gated: no envelope, no
iteration, no beat.

This is a static reading and it is reported as such. It cannot see a
`continue` that skips a beat at runtime, so a loop reported TIMER here can
still be wrong in a way only a live clock would show - which is what the
detector in the same patch is for.
"""
import argparse
import ast
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Call names that write a heartbeat.
BEAT_NAMES = ("beat", "heartbeat")

#: Node types that make a child traffic-gated rather than timer-driven.
GATES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
         ast.With)


def loops():
    here = os.path.join(ROOT, "scripts")
    for name in sorted(os.listdir(here)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(here, name)
        text = io.open(path, encoding="utf-8", errors="replace").read()
        if not any("%s(" % b in text for b in BEAT_NAMES):
            continue
        if "watchsink" not in text and "heartbeat" not in text:
            continue
        yield name, path, text


def beat_sites(tree):
    """Every heartbeat call, with the chain of enclosing blocks."""
    out = []

    def walk(node, chain):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Call):
                target = child.func
                name = getattr(target, "attr", None) or getattr(
                    target, "id", None)
                if name in BEAT_NAMES:
                    out.append((child.lineno, list(chain)))
            nxt = chain + [type(child).__name__] if isinstance(
                child, GATES) else chain
            walk(child, nxt)

    walk(tree, [])
    return out


def classify(path, text):
    tree = ast.parse(text)
    sites = beat_sites(tree)
    rows = []
    for lineno, chain in sites:
        gated = [c for c in chain if c in ("If", "For", "AsyncFor")]
        rows.append({
            "line": lineno,
            "enclosing_blocks": chain,
            "timer_driven": not gated,
            "gated_by": gated,
            "source": text.splitlines()[lineno - 1].strip()[:88],
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    report = []
    for name, path, text in loops():
        rows = classify(path, text)
        timer = [r for r in rows if r["timer_driven"]]
        report.append({
            "loop": name,
            "beat_sites": len(rows),
            "timer_driven_sites": len(timer),
            "verdict": ("CAN distinguish idle from dead"
                        if timer else
                        "CANNOT distinguish idle from dead"),
            "sites": rows,
        })

    width = max(len(r["loop"]) for r in report)
    print("HEARTBEAT INVENTORY - source-only, no work/ read")
    print("%-*s  %5s  %5s  %s" % (width, "loop", "beats", "timer", "verdict"))
    for row in report:
        print("%-*s  %5d  %5d  %s"
              % (width, row["loop"], row["beat_sites"],
                 row["timer_driven_sites"], row["verdict"]))
    print()
    bad = [r for r in report if not r["timer_driven_sites"]]
    print("LOOPS WHOSE HEARTBEAT IS ENTIRELY TRAFFIC-GATED: %d of %d"
          % (len(bad), len(report)))
    for row in bad:
        print("  %s" % row["loop"])
        for site in row["sites"]:
            print("    line %-5d gated by %-22s %s"
                  % (site["line"], ",".join(site["gated_by"]),
                     site["source"]))
    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1)
        print("\nwrote %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
