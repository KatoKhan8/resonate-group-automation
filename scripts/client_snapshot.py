#!/usr/bin/env python3
"""Export / clean / import: the client-approval cycle, per client.

    py -3 scripts/client_snapshot.py export --client productive \
        --domains work/stage/candidates.json --id PRODUCTIVE-2026-10-05
    py -3 scripts/client_snapshot.py import --client productive \
        --id PRODUCTIVE-2026-09-07 --file <returned.csv> --who "<name>"
    py -3 scripts/client_snapshot.py adopt  --client productive \
        --id PRODUCTIVE-2026-09-07 --file <list.csv> --who "<name>" \
        --source "..." --note "..."
    py -3 scripts/client_snapshot.py counts --client productive

OPERATOR DECISION, 2026-09-21: "Client approval works by export / clean /
import, per client, not by per-domain approval. This is an engine feature,
not a Productive branch: the logic lives once in `src/`."

So this script is a thin mouth on `src/clientapproval`. Every rule - what a
return means, what silence means, that a no is permanent - is in the module
and tested there. Nothing here decides anything.

## THE THREE VERBS

`export` records what we are about to send. `import` diffs a returned file
against it: present is approved, ABSENT IS SUPPRESSED FOREVER, and a domain
that was never sent is an anomaly that is reported and never approved.

`adopt` is the third case and it exists because of a real one. Productive's
`productive_ICP_safe_to_send (1).csv` came to us already cleaned, from before
this cycle existed. There is no prior export to diff against, so a diff would
read every domain as an anomaly and approve nothing. `adopt` records the file
AS a snapshot and approves what it holds - and suppresses NOTHING, because
absence from a list that was never sent is not a client decision.

**`adopt` is the dangerous verb and it is deliberately separate.** It takes
the client's word for a file we did not send. It requires `--who` and
`--source` naming the human and the artifact, and it should be rare enough
that every use is a recorded operator decision.

## WHAT A CSV IS HERE

Any CSV with a domain-bearing column - `domain`, `website`, `url`, or an
email column we take the domain from. No contacts, no emails and no names are
ever written to the approval store: the store holds domains, and a domain is
not PII.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clientapproval as ca                            # noqa: E402

#: Columns that can carry an account, best first.
#:
#: `url` SITS BELOW THE EMAIL COLUMNS, and that ordering is a measurement
#: rather than a preference. In `productive_ICP_safe_to_send (1).csv` the
#: `Url` column is the person's LinkedIn profile, so reading it as a website
#: keys all 33,887 rows to `linkedin.com`, which `NOT_AN_ACCOUNT` then drops -
#: an adopt of a 35,000-row file that approves nothing. A work email's domain
#: is unambiguously the company; a bare `url` is not.
DOMAIN_COLUMNS = ("domain", "website", "company domain", "company website",
                  "web site", "site", "work email", "email", "url")

NOT_AN_ACCOUNT = {"linkedin.com", "lnkd.in", "facebook.com", "twitter.com",
                  "x.com", "instagram.com", "youtube.com", "google.com"}


def _column_of(fieldnames):
    lowered = {(name or "").strip().lower(): name for name in fieldnames or ()}
    for wanted in DOMAIN_COLUMNS:
        if wanted in lowered:
            return lowered[wanted]
    return None


def domains_from(path):
    """Every account in a file, de-duplicated, order preserved. CSV or JSON."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        values = data if isinstance(data, list) else list(data)
    else:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            column = _column_of(reader.fieldnames)
            if column is None:
                raise SystemExit(
                    f"REFUSED: {path} has no domain-bearing column. Looked "
                    f"for {', '.join(DOMAIN_COLUMNS)}; found "
                    f"{', '.join(reader.fieldnames or ['nothing'])}")
            values = [row.get(column) for row in reader]
    seen, out = set(), []
    for value in values:
        key = ca.account_of(value)
        if not key or key in NOT_AN_ACCOUNT or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _report(title, pairs):
    print(f"\n{title}")
    width = max((len(name) for name, _ in pairs), default=0)
    for name, value in pairs:
        print(f"  {name.ljust(width)}   {value}")


def do_export(args):
    domains = domains_from(args.domains)
    row = ca.record_snapshot(args.id, domains, client=args.client,
                             note=args.note)
    _report(f"SNAPSHOT {row['snapshot']} recorded for {args.client}",
            [("domains", row["count"]), ("digest", row["digest"][:16]),
             ("at", row["at"])])
    print("\nNothing is approved by an export. The client cleans it and the "
          "return decides.")
    return 0


def do_import(args):
    returned = domains_from(args.file)
    report = ca.apply_return(args.id, returned, client=args.client,
                             who=args.who, returned_on=args.returned_on)
    _report(f"IMPORT {report['snapshot']} for {args.client}",
            [("sent", report["sent"]), ("returned", report["returned"]),
             ("approved", len(report["approved"])),
             ("suppressed", len(report["suppressed"])),
             ("anomalies", len(report["anomalies"]))])
    if report["anomalies"]:
        print("\nANOMALIES - in the return, never sent, NOT approved:")
        for domain in report["anomalies"][:20]:
            print(f"  {domain}")
        if len(report["anomalies"]) > 20:
            print(f"  ... and {len(report['anomalies']) - 20} more")
    if report["blocked_by_permanent"]:
        print(f"\n{len(report['blocked_by_permanent'])} returned domains were "
              f"already suppressed or rejected and were NOT re-approved.")
    _report("client_approval now", sorted(ca.counts(args.client).items()))
    return 0


def do_adopt(args):
    domains = domains_from(args.file)
    snap = ca.snapshot_of(args.id, args.client)
    if snap is None:
        snap = ca.record_snapshot(args.id, domains, client=args.client,
                                  note=args.note or "adopted: supplied by the "
                                  "client already cleaned, no prior export")
    written, blocked = ca.record_many(domains, client=args.client,
                                      state=ca.APPROVED, who=args.who,
                                      source=args.source, snapshot=args.id)
    _report(f"ADOPTED {args.id} for {args.client}",
            [("domains in file", len(domains)),
             ("approved", len(written)),
             ("already permanent, untouched", len(blocked)),
             ("suppressed", 0)])
    print("\nNothing was suppressed: absence from a list we never sent is not "
          "a client decision.")
    _report("client_approval now", sorted(ca.counts(args.client).items()))
    return 0


def do_counts(args):
    _report(f"client_approval for {args.client}",
            sorted(ca.counts(args.client).items()))
    snaps = ca.snapshots(args.client)
    if snaps:
        print("\nsnapshots")
        for row in snaps:
            print(f"  {row['snapshot']}   {row['count']} domains   "
                  f"{row['at']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--client", default=ca.DEFAULT_CLIENT)
    sub = parser.add_subparsers(dest="verb", required=True)

    export = sub.add_parser("export", help="record what is being sent")
    export.add_argument("--domains", required=True)
    export.add_argument("--id", required=True)
    export.add_argument("--note")
    export.set_defaults(func=do_export)

    imp = sub.add_parser("import", help="apply a cleaned return")
    imp.add_argument("--id", required=True)
    imp.add_argument("--file", required=True)
    imp.add_argument("--who", required=True)
    imp.add_argument("--returned-on", dest="returned_on")
    imp.set_defaults(func=do_import)

    adopt = sub.add_parser("adopt", help="a pre-cleaned list, no prior export")
    adopt.add_argument("--id", required=True)
    adopt.add_argument("--file", required=True)
    adopt.add_argument("--who", required=True)
    adopt.add_argument("--source", required=True)
    adopt.add_argument("--note")
    adopt.set_defaults(func=do_adopt)

    counts = sub.add_parser("counts", help="what stands right now")
    counts.set_defaults(func=do_counts)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
