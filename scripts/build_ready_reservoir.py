#!/usr/bin/env python3
"""Build and persist the durable READY reservoir.

STRICTLY READ-ONLY at every provider. No provider write, no activation,
no campaign mutation, no credit spend. It proposes, it does not send.

## What it writes

    work/ready_reservoir.json          real data, gitignored, names real people
    docs/state/READY-RESERVOIR.json    sanitised manifest: counts, stages,
                                       hashed fingerprint, deliberately not
                                       enough to rebuild the prospect list

## Why two files

`work/` is gitignored because it names 300 real companies and 92 real contacts.
`docs/state/` is in git and must carry no PII - counts, stages and a hashed
fingerprint, enough to know whether the estate changed, deliberately not
enough to rebuild the prospect list. `scripts/durable_state.py` is the pattern.

## The DERIVED rule

The reservoir is DERIVED, never latched. Every run re-computes the READY set
by running the screen. A contact that was READY an hour ago and has since
replied, been suppressed, had its approval invalidated by a copy edit, or had
its account collide must NOT still be READY.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import clients, store                                    # noqa: E402
from src.providers import load_env                                # noqa: E402
from src import reservoir                                         # noqa: E402

CLIENT = "productive"
WORK_DIR = os.path.join(ROOT, "work")
STATE_DIR = os.path.join(ROOT, "docs", "state")


def h(*parts):
    """The repo's identifier hash. Never print the input."""
    return hashlib.sha256(":".join(str(p) for p in parts)
                          .encode("utf-8")).hexdigest()[:12]


def sanitised_manifest(report, recs):
    """Counts, stages and a hashed fingerprint. No PII.

    Enough to know whether the estate changed, deliberately not enough to
    rebuild the prospect list.
    """
    estate_digest = hashlib.sha256()
    for rec in recs:
        estate_digest.update(h(rec.get("domain") or rec.get("id") or "")
                             .encode())

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "derived_from": "scripts/next_ready_cohort.py via src/reservoir.py",
        "proposes_does_not_send": True,
        "channels": {},
        "estate_fingerprint": estate_digest.hexdigest()[:16],
        "record_count": len(recs),
    }
    for channel, data in report.items():
        summary = reservoir.depth_and_blockers({channel: data})[channel]
        manifest["channels"][channel] = {
            "depth": data["depth"],
            "population": data["population"],
            "buckets": data["buckets"],
            "blockers_ranked": summary["blockers_ranked"],
            "ready_hashes": [r["contact"] for r in data["ready"]],
        }
    return manifest


def main(argv=None):
    load_env(os.path.join(ROOT, "config", ".env"))
    recs = store.load()
    config = clients.load(CLIENT)
    campaigns_by_id = {c["campaign_id"]: c
                       for c in store.read_jsonl(store.campaigns_path())}

    report = reservoir.ready_set(recs, config, campaigns_by_id)

    # Persist real data to work/ (gitignored).
    os.makedirs(WORK_DIR, exist_ok=True)
    reservoir_path = os.path.join(WORK_DIR, "ready_reservoir.json")
    with open(reservoir_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)

    # Persist sanitised manifest to docs/state/.
    os.makedirs(STATE_DIR, exist_ok=True)
    manifest = sanitised_manifest(report, recs)
    manifest_path = os.path.join(STATE_DIR, "READY-RESERVOIR.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    # Print summary.
    for channel in ("linkedin", "email"):
        data = report[channel]
        print(f"=== {channel.upper()}  population={data['population']}  "
              f"READY={data['depth']}")
        summary = reservoir.depth_and_blockers({channel: data})[channel]
        for gate, count in summary["blockers_ranked"]:
            print(f"    {gate:<20} {count}")

    print(f"\nwrote {reservoir_path}")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
