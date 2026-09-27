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
    "prior_touch_status": "prior-touch status",
}


#: The ONLY ICP verdict a client export may carry. Operator ruling
#: 2026-09-22: QUALIFIED only, REVIEW to further enrichment.
EXPORTABLE_ICP = "qualified"

#: The field only the sourced chain writes. `qualify_sourced_supply.py`
#: stamps it; nothing that produced the legacy pool ever did.
#:
#: PROVENANCE RATHER THAN A FLAG, so the retirement clears ITSELF. A boolean
#: somebody has to remember to flip is a boolean that stays flipped, and the
#: last thing this export needs is a second piece of state that drifts from
#: the thing it describes.
SOURCED_PROVENANCE = "_sourced_at"


class RetiredCandidatePool(Exception):
    """The pool on disk is the retired one and may not be exported.

    RAISED RATHER THAN RETURNING AN EMPTY LIST, and that is the decision
    worth keeping. An empty CSV is indistinguishable from "no new candidates
    this week" - it looks like a quiet week rather than a stopped export, and
    this repository has shipped that confusion before: an evaluator reported
    INSUFFICIENT_DATA for ever because nothing wrote the field it read.
    """


def exportable_candidates():
    """Candidates ready for this week's export: NEW **and** QUALIFIED.

    THE VERDICT GATE IS HERE AS WELL AS AT THE WRITER, and that is the whole
    point of this function's second condition.

    `4afb54d5` implemented the operator's ruling in `nightlysourcing`, which
    is where records ENTER the candidate list - so no REVIEW record has been
    added since. It cannot reach the 1,394 REVIEW records that were already
    in `candidates.jsonl` when it landed, and this function had no verdict
    condition at all, so every one of them was still exportable.

    MEASURED 2026-09-24, by calling it:

        exportable_candidates()          1508 rows
        of which icp_status == review    1394
        rows at icp_score 0.0            1410
        median headcount                 16,745

    Productive sells to 20+ person marketing and creative agencies. That
    export is the ISSUE-019 incident a second time, from the other end: the
    ruling was enforced where records are written and absent where they are
    read, and the register recorded it as implemented and standing.

    A gate at the writer protects the future. A gate at the reader protects
    the file as it is. The export needs the second one, because the defective
    rows are already on disk and no amount of correct writing removes them.
    """
    rows = [r for r in candidatelist.load()
            if r.get("state") == "new"
            and str(r.get("icp_status") or "").strip().lower() == EXPORTABLE_ICP]

    # OPERATOR DECISION 2026-09-24, ISSUE-031: the 1,508-row pool is RETIRED
    # from every export path. It is not a tuning problem - 58 of its 114
    # QUALIFIED rows scored 0.0 while passing structurally, and its median
    # QUALIFIED headcount is 16,996 for a client who sells to 20+ person
    # agencies. The sourced chain is the only source until it is rebuilt.
    legacy = [r for r in rows if not r.get(SOURCED_PROVENANCE)]
    if legacy:
        raise RetiredCandidatePool(
            "%d of %d exportable rows carry no `%s`, so they come from the "
            "retired pool rather than the sourced chain. The weekly export "
            "is STOPPED by operator decision 2026-09-24 (ISSUE-031, and "
            "ISSUE-023 underneath it). Rebuild `candidates.jsonl` from "
            "`qualify_sourced_supply.py` - this refusal clears itself when "
            "the rows carry that field."
            % (len(legacy), len(rows), SOURCED_PROVENANCE))
    return rows


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
