"""Carry the already-crawled rows that ARE in the repointed cohort across.

LANE K, 2026-09-25, after the repoint. The first walk read 6,219 domains of
`work/qualified-supply.jsonl` before it was stopped. Lane J's cohort and
that supply overlap, so some of those 6,219 are domains the new target also
needs. Re-fetching them would be free but not instant, and the rows are
minutes old from the same crawler on the same day.

So they are carried across BY DOMAIN, unchanged, with `carried_from` naming
the log they came from - a row whose provenance is silently rewritten is
worse than a re-crawl. Only rows for domains in the cohort move; nothing is
invented and no row is edited.
"""
import argparse
import json
import os


def domains_of(path, field="domain"):
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            value = str(row.get(field) or "").strip().lower().lstrip("@")
            if value:
                out.add(value)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-log", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--into", required=True)
    args = ap.parse_args(argv)

    wanted = domains_of(args.cohort)
    already = domains_of(args.into) if args.into else set()
    moved = 0
    with open(args.from_log, encoding="utf-8") as src, \
            open(args.into, "a", encoding="utf-8") as dst:
        seen = set()
        for line in src:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            domain = str(row.get("domain") or "").lower()
            if domain not in wanted or domain in already or domain in seen:
                continue
            seen.add(domain)
            row["carried_from"] = args.from_log.replace("\\", "/").split("/")[-1]
            dst.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            moved += 1
    print("cohort domains %d; carried %d row(s) from %s into %s"
          % (len(wanted), moved, args.from_log, args.into))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
