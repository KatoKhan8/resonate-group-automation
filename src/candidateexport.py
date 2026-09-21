#!/usr/bin/env python3
"""The weekly candidate export. TASK-245.

Monday 07:00 Europe/Zagreb. Columns, exactly these, in this order:

    domain, company, headcount, industry, country, website,
    why it matched, prior-touch status

The export is the input to TASK-244's approval intake. Written so that
task's sheet writer and Slack poster can both consume it without reshaping.

DST: the schedule is stated in Zagreb time and moves with it. The UTC hour
is derived from geo.zone, never hardcoded.

  python -m src.candidateexport --dry-run
  python -m src.candidateexport --live
"""
import argparse
import csv
import datetime
import io
import json
import os

from . import candidatelist, export as export_mod, geo, store

TIMEZONE = "Europe/Zagreb"
EXPORT_COLUMNS = [
    "domain", "company", "headcount", "industry", "country", "website",
    "why it matched", "prior-touch status",
]

# Map from candidate field names to export column names.
FIELD_MAP = {
    "domain": "domain",
    "company": "company",
    "headcount": "headcount",
    "industry": "industry",
    "country": "country",
    "website": "website",
    "why_matched": "why it matched",
    "_prior_touch": "prior-touch status",
}


def exportable_candidates():
    """Candidates in 'new' state, ready for this week's export."""
    return [r for r in candidatelist.load() if r.get("state") == "new"]


def to_export_rows(candidates):
    """Candidate dicts -> export rows in the exact column order."""
    rows = []
    for c in candidates:
        row = []
        for col in EXPORT_COLUMNS:
            src_key = None
            for cand_key, export_col in FIELD_MAP.items():
                if export_col == col:
                    src_key = cand_key
                    break
            value = c.get(src_key, "") if src_key else ""
            if value is None:
                value = ""
            row.append(value)
        rows.append(row)
    return rows


def build_csv(candidates=None):
    """The export as a CSV string. Uses export.safe_cell for formula guard."""
    candidates = candidates if candidates is not None \
        else exportable_candidates()
    rows = to_export_rows(candidates)
    return export_mod.to_csv(EXPORT_COLUMNS, rows)


def write_export(path, candidates=None):
    """Write the CSV to disk. Returns the path."""
    candidates = candidates if candidates is not None \
        else exportable_candidates()
    rows = to_export_rows(candidates)
    return export_mod.write_csv(path, EXPORT_COLUMNS, rows)


def run(live=False, output_dir=None):
    """The weekly export.

    live=False: dry run, returns the CSV and the domains that would be marked.
    live=True: writes the CSV and marks exported candidates.
    """
    candidates = exportable_candidates()
    csv_text = build_csv(candidates)
    domains = [str(c.get("domain") or "") for c in candidates]

    report = {
        "candidates": len(candidates),
        "domains": domains,
        "csv_length": len(csv_text),
        "live": live,
        "at": store.now(),
    }

    if live and candidates:
        output_dir = output_dir or os.path.join(store.ROOT, "work", "exports")
        os.makedirs(output_dir, exist_ok=True)
        today = datetime.date.today().isoformat()
        path = os.path.join(output_dir, f"candidates-{today}.csv")
        write_export(path, candidates)
        report["path"] = path
        marked = candidatelist.mark_exported(domains)
        report["marked_exported"] = marked

    return report, csv_text


def to_json_payload(candidates=None):
    """The export as a JSON array of dicts, for TASK-244's sheet writer."""
    candidates = candidates if candidates is not None \
        else exportable_candidates()
    rows = []
    for c in candidates:
        row = {}
        for col in EXPORT_COLUMNS:
            src_key = None
            for cand_key, export_col in FIELD_MAP.items():
                if export_col == col:
                    src_key = cand_key
                    break
            value = c.get(src_key, "") if src_key else ""
            row[col] = value if value is not None else ""
        rows.append(row)
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true",
                   help="write the CSV and mark candidates exported")
    p.add_argument("--json", action="store_true",
                   help="output as JSON instead of CSV")
    p.add_argument("--output-dir")
    a = p.parse_args(argv)

    report, csv_text = run(live=a.live, output_dir=a.output_dir)
    if a.json:
        payload = to_json_payload()
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(csv_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
