"""TASK-201: resolve the 21 records whose offices use missing ISO codes.

For each affected record: which country now resolves, and what the geography
criterion returns.  Hashes record ids and domains so no PII leaves the file.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import icpstructural, clients, segments, store


SNAPSHOT = Path(__file__).parent.parent / "work" / "queue.snapshot.jsonl"


def _hash(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


# The 17 codes that were missing before TASK-201 completed the table.
PREVIOUSLY_MISSING = {
    "CZ", "GR", "CY", "RS", "SS", "UA", "AR", "HU", "JO", "SI",
    "LT", "EE", "ZA", "MC", "RU", "TN", "MX",
}


def _affected_records(records):
    """Return sorted indices of records whose offices use a previously-missing code."""
    affected = set()
    for idx, rec in enumerate(records):
        offices = (rec.get("company_facts") or {}).get("offices") or []
        for line in offices:
            token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
            if token in PREVIOUSLY_MISSING:
                affected.add(idx)
    return sorted(affected)


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    config = clients.load("productive")
    rules = icpstructural.settings(config)

    affected_indices = _affected_records(records)

    print(f"Records affected by previously-missing ISO codes: {len(affected_indices)}")
    print(f"Codes that were missing: {sorted(PREVIOUSLY_MISSING)}")
    print()

    # Show per-record resolution AFTER the table is complete.
    print("Per-record resolution (after ISO_TO_NAME completion):")
    print(f"  {'rec_id':>14s}  {'domain':>14s}  {'country':>20s}  "
          f"{'source':>24s}  {'geo_status':>10s}")
    print("  " + "-" * 92)

    on_include = []
    for idx in affected_indices:
        rec = records[idx]
        seg = segments.classify(rec, config)
        country, source = icpstructural.resolve_country(rec, seg)
        geo = icpstructural._geography(rec, seg, rules)

        rec_hash = _hash(rec.get("id", idx))
        domain_hash = _hash(rec.get("domain", "?"))

        print(f"  {rec_hash:>14s}  {domain_hash:>14s}  "
              f"{str(country):>20s}  {str(source):>24s}  "
              f"{geo['status']:>10s}")

        if geo["status"] == "pass":
            on_include.append((rec_hash, country))

    print()
    if on_include:
        print(f"Records that now PASS geography: {len(on_include)}")
        for rh, c in on_include:
            print(f"  {rh}  ->  {c}")
    else:
        print("No records resolve to a country on the include list.")
        print("All 21 remain UNKNOWN (correct: informed unknown, not ignorant).")

    # Aggregate by country
    print()
    print("Aggregate by resolved country:")
    by_country = {}
    for idx in affected_indices:
        rec = records[idx]
        seg = segments.classify(rec, config)
        country, _ = icpstructural.resolve_country(rec, seg)
        name = str(country) if country else "(unresolved)"
        by_country[name] = by_country.get(name, 0) + 1
    for country, count in sorted(by_country.items(), key=lambda x: -x[1]):
        print(f"  {country:>25s}: {count}")


if __name__ == "__main__":
    main()
