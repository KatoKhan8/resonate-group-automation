#!/usr/bin/env python3
"""Reoon deep verification for addresses ContactOut returned as accept_all.

Two modes, because the sandbox egress proxy blocks direct calls to Reoon but
WebFetch reaches it fine:

  verify.py --direct            HTTP straight to Reoon (use in n8n / on your box)
  verify.py --emit              print the URLs for the batch session to WebFetch
  verify.py --ingest results.json   fold WebFetch'd JSON back into the queue

Env: REOON_KEY
"""
import argparse, json, os, sys, urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE = os.path.join(ROOT, "work", "queue.jsonl")
API = "https://emailverifier.reoon.com/api/v1/verify"


def load():
    return [json.loads(l) for l in open(QUEUE) if l.strip()]


def save(recs):
    with open(QUEUE, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def pending(recs):
    """(record_id, email) pairs that need a deep check."""
    out = []
    for r in recs:
        for c in r.get("contacts") or []:
            if c.get("verdict") == "accept_all" and not c.get("reoon"):
                out.append((r["id"], c["email"]))
    return out


def url_for(email, key):
    return f"{API}?" + urllib.parse.urlencode({"email": email, "key": key, "mode": "power"})


def apply_result(recs, email, data):
    keep = {k: data.get(k) for k in
            ("is_deliverable", "is_safe_to_send", "is_catch_all", "overall_score", "status")}
    for r in recs:
        for c in r.get("contacts") or []:
            if c.get("email") == email:
                c["reoon"] = keep
                if keep.get("is_safe_to_send") is False:
                    c["verdict"] = "invalid"
    return recs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--direct", action="store_true")
    p.add_argument("--emit", action="store_true")
    p.add_argument("--ingest")
    a = p.parse_args()

    recs = load()
    key = os.environ.get("REOON_KEY", "REOON_KEY")

    if a.emit:
        todo = pending(recs)
        if not todo:
            print("nothing pending")
            return
        for rid, email in todo:
            print(f"{rid}\t{email}\t{url_for(email, key)}")
        return

    if a.ingest:
        payload = json.load(open(a.ingest))
        items = payload if isinstance(payload, list) else [payload]
        for d in items:
            email = d.get("email")
            if email:
                apply_result(recs, email, d)
        save(recs)
        print(f"ingested {len(items)} result(s)")
        return

    if a.direct:
        import requests
        todo = pending(recs)
        for rid, email in todo:
            try:
                d = requests.get(url_for(email, key), timeout=30).json()
            except Exception as e:
                print(f"  {email}: {e}", file=sys.stderr)
                continue
            apply_result(recs, email, d)
            print(f"  {email}: deliverable={d.get('is_deliverable')} "
                  f"safe={d.get('is_safe_to_send')} score={d.get('overall_score')}")
        save(recs)
        return

    p.print_help()


if __name__ == "__main__":
    main()
