#!/usr/bin/env python3
"""canary/0002: point the 13 record-reading rows at the real work/ queue.

    py -3 -B scripts/preflight_join_and_run.py --cohort <cohort.json>
    py -3 -B scripts/preflight_join_and_run.py --cohort <cohort.json> --no-addresses
    py -3 -B scripts/preflight_join_and_run.py --cohort <cohort.json> --channel linkedin

WHY THIS FILE EXISTS. audit/0001 measured the 13 rows of the canary
preflight that read a queue record as 13 OPERATOR / 0 lane-closable,
because their inputs live only in the main checkout's gitignored work/ -
"the code is lane-buildable, the sight is not". canary/0002 built the
code (13 ask functions, 3 control arms each, on synthetic records). The
rows read `contact["record"]`, and the cohort JSON format has always
carried record as OPTIONAL ("when present, is this contact's queue
record" - scripts/canary_preflight.py). Nothing ever bound it. This
script is the collapsed operator step: JOIN, then RUN.

  1. JOIN. Every cohort contact is matched against this tree's real
     queue - `store.load()`, THE authority, read through store.py - using
     the instrument's OWN matcher, `preflight._matched_record_entry`
     (lint.find_contact by key, then the normalised email; a name is
     never identity). Exactly one matching record binds; the join then
     re-decides nothing.

       0 matches  NOT FOUND  - left unbound. The 13 rows read UNKNOWN
                  for that contact through evaluate()'s own needs_record
                  floor. A record is never invented.
       2+ matches AMBIGUOUS  - left unbound, both record ids named.
                  Identity is proved, never guessed.

  2. WRITE. The joined cohort goes to `preflight-joined-cohort.json`
     BESIDE the queue, under work/ - gitignored, so real addresses and
     real records never enter git. The path is derived from
     `store.queue_path()` and cannot land anywhere else.

  3. RUN. `scripts/preflight_one_command.py`'s own main(), in process,
     on the joined cohort - the fixed three-section shape, the roll-up
     vocabulary, the provenance line and the instrument's exit codes,
     all unchanged. This script prints the join report ABOVE it.

READ-ONLY against every authority: the queue, the eight files and the
register are only read. The one write is the joined cohort under work/.
NO provider call, NO network, NO send, NO activation, no guard, gate,
cap, assertion or client config touched.

FAIL CLOSED. Any fault in the join - unreadable cohort, a contact that
is not a dict, an empty queue - prints JOIN FAULT (never a traceback:
an uncaught exception would exit 1, which is the instrument's
EXIT_EXCLUDED, and a wrapper crash must never read as a finding about a
person) and returns preflight.EXIT_UNKNOWN (2).

RUN IT FROM THE MAIN CHECKOUT, with the canary/0002 branch checked out.
`store.queue_path()` resolves per-tree, so a worktree joins against its
OWN work/, not production's; the script says loudly which tree it read
when it is not the main checkout.

THE OUTPUT IS VERDICTS, NOT CLEARANCE. Clearance is the operator's
judgement over the whole table.
"""
import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
for path in (ROOT, SCRIPT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from src import preflight, store                               # noqa: E402
import preflight_one_command as poc                            # noqa: E402

JOINED_NAME = "preflight-joined-cohort.json"


def _main_checkout_root():
    """The main checkout's root, or None - never a guess. Derived through
    the one path identical from every tree and the main checkout, the
    absolute git common dir (the suite lock's own doctrine); a relative
    answer is refused rather than resolved against this process's cwd."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    common = (proc.stdout or "").strip()
    if not common or not os.path.isabs(common):
        return None
    return os.path.normcase(os.path.abspath(os.path.dirname(common)))


def _label(contact, addresses):
    key = contact.get("key") or "?"
    if addresses and contact.get("email"):
        return "%s <%s>" % (key, contact["email"])
    return key


def join(contacts, records, addresses=True, out=print):
    """Bind each contact to its record through the instrument's own
    matcher. Returns (joined_contacts, stats). Pure reads; the only side
    effect is printing the join report."""
    joined, not_found, ambiguous, rebound = [], [], [], 0
    for pos, contact in enumerate(contacts):
        if not isinstance(contact, dict):
            raise ValueError("cohort position %d is %s, not a contact dict"
                             % (pos, type(contact).__name__))
        matches = [rec for rec in records
                   if preflight._matched_record_entry(rec, contact)[0]
                   is not None]
        if len(matches) == 1:
            if contact.get("record"):
                rebound += 1
            bound = dict(contact, record=matches[0])
            joined.append(bound)
        elif not matches:
            not_found.append(_label(contact, addresses))
            joined.append(dict(contact))
        else:
            ambiguous.append("%s (matched %d records: %s)" % (
                _label(contact, addresses), len(matches),
                ", ".join(str(r.get("id") or "?") for r in matches)))
            joined.append(dict(contact))

    out("JOIN - cohort contacts bound to THIS tree's queue records")
    out("  contacts in cohort   %d/%d" % (len(contacts), len(contacts)))
    out("  JOINED               %d/%d%s"
        % (len(contacts) - len(not_found) - len(ambiguous), len(contacts),
           "  (%d rebound over a stale copy - the queue is the authority)"
           % rebound if rebound else ""))
    out("  NOT FOUND            %d/%d  left unbound; the 13 record rows "
        "read UNKNOWN for each, through evaluate()'s own floor"
        % (len(not_found), len(contacts)))
    for label in not_found:
        out("      %s" % label)
    out("  AMBIGUOUS            %d/%d  left unbound; identity is proved, "
        "never guessed" % (len(ambiguous), len(contacts)))
    for label in ambiguous:
        out("      %s" % label)
    return joined, {"joined": len(contacts) - len(not_found) - len(ambiguous),
                    "not_found": not_found, "ambiguous": ambiguous,
                    "rebound": rebound}


def main(argv=None, out=print):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cohort", required=True,
                    help="JSON list of contacts. Never in git.")
    ap.add_argument("--channel", default="email",
                    choices=("email", "linkedin"))
    ap.add_argument("--no-addresses", action="store_true",
                    help="withhold addresses from stdout")
    ap.add_argument("--sha", default=None,
                    help="passed through to preflight_one_command")
    args = ap.parse_args(argv)
    addresses = not args.no_addresses

    try:
        queue_path = store.queue_path()
        tree = preflight.tree_root()
        out("=" * 72)
        out("CANARY/0002 JOIN+RUN - the 13 record rows against the real "
            "queue")
        out("=" * 72)
        out("tree        : %s" % tree)
        main_root = _main_checkout_root()
        if main_root is None:
            out("main checkout: UNKNOWN (git common dir could not be "
                "derived) - named, not guessed")
        elif main_root != os.path.normcase(os.path.abspath(tree)):
            out("main checkout: %s" % main_root)
            out("WARNING      : THIS TREE IS NOT THE MAIN CHECKOUT. "
                "store.queue_path() is per-tree, so this run joins against "
                "THIS tree's own work/ - a lane or scratch queue is not "
                "the production estate.")
        out("queue       : %s" % queue_path)
        records = store.load()
        if not records:
            out("JOIN FAULT: the queue at %s holds no records. An empty "
                "queue is a state to name, not a cohort to assess: are you "
                "in the main checkout? Nothing was joined; UNKNOWN, exit %d"
                % (queue_path, preflight.EXIT_UNKNOWN))
            return preflight.EXIT_UNKNOWN
        out("queue holds  %d record(s), read through src/store.py"
            % len(records))
        contacts = poc.load_cohort(args.cohort)
        joined, _stats = join(contacts, records, addresses=addresses, out=out)

        joined_path = os.path.join(os.path.dirname(queue_path), JOINED_NAME)
        with open(joined_path, "w", encoding="utf-8", newline="\n") as h:
            json.dump(joined, h, indent=1, sort_keys=True)
        out("  joined cohort written to %s (under work/, gitignored - real "
            "addresses and records never enter git)" % joined_path)
        out("verdicts are src/preflight.py's; this join binds records and "
            "re-decides nothing. UNKNOWN never renders as CLEARED.")
        out("")
    except SystemExit:
        raise
    except Exception as exc:                                    # noqa: BLE001
        print("JOIN FAULT: the join could not be completed: %s: %s"
              % (type(exc).__name__, poc._one_line(exc, 300)))
        print("nothing was assessed by this run; UNKNOWN, exit %d"
              % preflight.EXIT_UNKNOWN)
        return preflight.EXIT_UNKNOWN

    forward = ["--cohort", joined_path, "--channel", args.channel]
    if args.no_addresses:
        forward.append("--no-addresses")
    if args.sha:
        forward += ["--sha", args.sha]
    return poc.main(forward)


if __name__ == "__main__":
    raise SystemExit(main())
