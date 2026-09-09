#!/usr/bin/env python3
"""Record store CLI. The batch session touches state only through this.

Usage:
  rec.py list [--state S] [--lane L] [--fields id,company,state]
  rec.py get <id> [--field contacts]
  rec.py patch <id> --json '{"state":"enriched","contacts":[...]}'
  rec.py drop <id> --reason "..."
  rec.py stats
"""
import argparse, json, os, sys, datetime

QUEUE = os.environ.get("QUEUE", os.path.join(os.path.dirname(__file__), "..", "work", "queue.jsonl"))
QUEUE = os.path.abspath(QUEUE)


def load():
    if not os.path.exists(QUEUE):
        return []
    with open(QUEUE) as f:
        return [json.loads(l) for l in f if l.strip()]


def save(recs):
    tmp = QUEUE + ".tmp"
    with open(tmp, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, QUEUE)


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def deep_merge(base, patch):
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--state")
    pl.add_argument("--lane")
    pl.add_argument("--fields", default="id,lane,company,domain,state")

    pg = sub.add_parser("get")
    pg.add_argument("id")
    pg.add_argument("--field")

    pp = sub.add_parser("patch")
    pp.add_argument("id")
    pp.add_argument("--json", required=True)
    pp.add_argument("--note", default="")

    pd = sub.add_parser("drop")
    pd.add_argument("id")
    pd.add_argument("--reason", required=True)

    sub.add_parser("stats")

    a = p.parse_args()
    recs = load()
    idx = {r["id"]: r for r in recs}

    if a.cmd == "list":
        fields = a.fields.split(",")
        rows = [r for r in recs
                if (not a.state or r.get("state") == a.state)
                and (not a.lane or r.get("lane") == a.lane)]
        w = [max(len(f), max((len(str(r.get(f, ""))) for r in rows), default=0)) for f in fields]
        print("  ".join(f.ljust(w[i]) for i, f in enumerate(fields)))
        for r in rows:
            print("  ".join(str(r.get(f, "")).ljust(w[i]) for i, f in enumerate(fields)))
        return

    if a.cmd == "get":
        r = idx.get(a.id)
        if not r:
            sys.exit(f"no record {a.id}")
        print(json.dumps(r.get(a.field) if a.field else r, indent=2, ensure_ascii=False))
        return

    if a.cmd == "patch":
        r = idx.get(a.id)
        if not r:
            sys.exit(f"no record {a.id}")
        patch = json.loads(a.json)
        before = r.get("state")
        deep_merge(r, patch)
        r.setdefault("log", []).append({
            "step": patch.get("state", before), "at": now(),
            "note": a.note or f"patched {','.join(patch.keys())}"})
        save(recs)
        print(f"{a.id}: {before} -> {r.get('state')}")
        return

    if a.cmd == "drop":
        r = idx.get(a.id)
        if not r:
            sys.exit(f"no record {a.id}")
        r["state"] = "dropped"
        r["drop_reason"] = a.reason
        r.setdefault("log", []).append({"step": "dropped", "at": now(), "note": a.reason})
        save(recs)
        print(f"{a.id}: dropped ({a.reason})")
        return

    if a.cmd == "stats":
        from collections import Counter
        c = Counter(r.get("state") for r in recs)
        lanes = Counter(r.get("lane") for r in recs)
        print(f"records: {len(recs)}")
        for k, v in c.most_common():
            print(f"  {k:<10} {v}")
        print("lanes: " + ", ".join(f"{k}={v}" for k, v in lanes.items()))


if __name__ == "__main__":
    main()
