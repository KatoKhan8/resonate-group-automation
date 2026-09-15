#!/usr/bin/env python3
"""Generate the campaign registry from both providers.

Reads every campaign at HeyReach and EmailBison, writes a unified registry to
`docs/state/CAMPAIGN-REGISTRY.json`, and runs duplicate detection over the
result.

READ-ONLY. No POST/PATCH/PUT/DELETE at either provider. No sends, no campaign
creation, no lead additions. The whole point is a report that is free of side
effects.

## What the registry carries

For every campaign at both providers:
  - provider (heyreach or emailbison)
  - id
  - name
  - status
  - created
  - lead count
  - sequence hash (where readable)
  - whether Resonate created it
  - cohort/hypothesis (where known, from internal campaign records)
  - sequence node count (for shape comparison)

## Secrets

Credentials are read from the environment by the provider modules. Only the
NAMES of the variables appear here, never a value.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, bison, load_env, request  # noqa: E402
from src import campaignregistry  # noqa: E402

OUT = os.path.join(ROOT, "docs", "state", "CAMPAIGN-REGISTRY.json")

RESONATE_PREFIXES = ("RESONATE",)


def short_hash(value):
    import hashlib
    v = " ".join(str(value or "").split()).lower()
    if not v:
        return None
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]


def heyreach_sequence_hash(seq):
    blob = json.dumps(seq, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def collect_heyreach():
    """Every HeyReach campaign, read-only. Returns (entries, status_totals)."""
    base, hdr = heyreach.BASE, heyreach.headers()
    st, _ = request("GET", base + "/auth/CheckApiKey", hdr)
    if st != 200:
        print(f"HeyReach credential rejected: HTTP {st} (env var HEYREACH_KEY)")
        return [], {}

    campaigns, off, total = [], 0, None
    while True:
        st, data = request("POST", base + "/campaign/GetAll", hdr,
                           {"offset": off, "limit": 100})
        if st != 200:
            raise RuntimeError(f"GetAll failed: {st} {str(data)[:200]}")
        items = data.get("items") or []
        campaigns.extend(items)
        total = data.get("totalCount")
        off += len(items)
        if not items or off >= (total or 0):
            break

    status_totals = {}
    entries = []
    for c in campaigns:
        cid = c.get("id")
        name = c.get("name") or ""
        status = c.get("status") or "UNKNOWN"
        status_totals[status] = status_totals.get(status, 0) + 1

        seq_hash = None
        seq_nodes = 0
        try:
            seq = heyreach.campaign_sequence(cid)
            if seq:
                seq_hash = heyreach_sequence_hash(seq)
                nodes, types, truncated = heyreach.walk_sequence(seq)
                seq_nodes = len(nodes)
        except Exception:
            pass

        is_resonate = name.upper().startswith(RESONATE_PREFIXES)
        entries.append({
            "provider": "heyreach",
            "id": str(cid),
            "name": name,
            "status": status,
            "created": c.get("creationTime"),
            "lead_count": (c.get("progressStats") or {}).get("totalUsers", 0),
            "sequence_hash": seq_hash,
            "sequence_nodes": seq_nodes,
            "lead_list_id": str(c.get("linkedInUserListId") or ""),
            "is_resonate": is_resonate,
            "cohort_key": None,
            "hypothesis": None,
        })
    return entries, status_totals


def collect_emailbison():
    """Every EmailBison campaign, read-only. Returns (entries, status_totals).

    EmailBison paginates at 15 rows per page whatever per_page is set to.
    The walk is capped to avoid runaway pagination.
    """
    try:
        bison.base()
        bison.headers()
    except Exception as e:
        print(f"EmailBison credential unavailable: {e}")
        return [], {}

    entries = []
    status_totals = {}
    page = 1
    cap = 40

    while page <= cap:
        try:
            status, data = request(
                "GET",
                f"{bison.base()}/campaigns?page={page}&per_page=100",
                bison.headers())
        except Exception as e:
            print(f"EmailBison campaigns page {page} failed: {e}")
            break

        if status != 200:
            print(f"EmailBison campaigns page {page}: HTTP {status}")
            break

        rows = []
        if isinstance(data, dict):
            rows = data.get("data") or []
        if not isinstance(rows, list) or not rows:
            break

        for r in rows:
            if not isinstance(r, dict):
                continue
            cid = r.get("id")
            name = r.get("name") or ""
            cstatus = r.get("status") or "unknown"
            status_totals[cstatus] = status_totals.get(cstatus, 0) + 1

            seq_hash = None
            seq_nodes = 0
            try:
                steps = bison.sequence_steps(cid)
                if steps:
                    blob = json.dumps(steps, sort_keys=True,
                                      separators=(",", ":"), default=str)
                    seq_hash = hashlib.sha256(
                        blob.encode("utf-8")).hexdigest()[:16]
                    seq_nodes = len(steps)
            except Exception:
                pass

            is_resonate = name.upper().startswith(RESONATE_PREFIXES)
            entries.append({
                "provider": "emailbison",
                "id": str(cid),
                "name": name,
                "status": cstatus,
                "created": r.get("created_at") or r.get("createdAt"),
                "lead_count": r.get("leads_count") or r.get("leadsCount") or 0,
                "sequence_hash": seq_hash,
                "sequence_nodes": seq_nodes,
                "lead_list_id": None,
                "is_resonate": is_resonate,
                "cohort_key": None,
                "hypothesis": None,
            })

        meta = data.get("meta") if isinstance(data, dict) else {}
        try:
            last = int(meta.get("last_page") or 0)
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1

    return entries, status_totals


def enrich_from_internal(entries):
    """Match internal campaign records to registry entries by provider id,
    and copy cohort_key and hypothesis where the internal record carries
    them."""
    path = os.path.join(ROOT, "work", "campaigns.jsonl")
    if not os.path.exists(path):
        return entries
    internal = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            hr = r.get("heyreach_campaign_id")
            br = r.get("bison_campaign_id")
            if hr:
                internal[f"heyreach:{hr}"] = r
            if br:
                internal[f"emailbison:{br}"] = r

    for entry in entries:
        key = f"{entry['provider']}:{entry['id']}"
        rec = internal.get(key)
        if rec:
            entry["cohort_key"] = rec.get("cohort_key")
            entry["hypothesis"] = rec.get("hypothesis")
    return entries


def main():
    load_env()

    hr_entries, hr_status = collect_heyreach()
    print(f"HeyReach: {len(hr_entries)} campaigns")

    eb_entries, eb_status = collect_emailbison()
    print(f"EmailBison: {len(eb_entries)} campaigns")

    all_entries = hr_entries + eb_entries
    all_entries = enrich_from_internal(all_entries)

    duplicates = campaignregistry.find_duplicates(all_entries)
    print(f"Duplicate pairs found: {len(duplicates)}")
    for d in duplicates:
        a, b = d["campaign_a"], d["campaign_b"]
        print(f"  {a['provider']}:{a['id']} ({a['name'][:40]}) <-> "
              f"{b['provider']}:{b['id']} ({b['name'][:40]})")
        for reason in d["reasons"]:
            print(f"    - {reason}")

    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ("Read-only collection from HeyReach and EmailBison APIs. "
                   "Credential env vars: HEYREACH_KEY, BISON_KEY."),
        "totals": {
            "heyreach": len(hr_entries),
            "emailbison": len(eb_entries),
            "total": len(all_entries),
            "resonate_created": sum(1 for e in all_entries if e.get("is_resonate")),
        },
        "heyreach_status_totals": hr_status,
        "emailbison_status_totals": eb_status,
        "campaigns": all_entries,
        "duplicates": duplicates,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2, default=str)
        fh.write("\n")

    print(f"\nWritten: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
