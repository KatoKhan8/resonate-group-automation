#!/usr/bin/env python3
"""Ingest a batch into work/queue.jsonl.

Accepts:
  a .jsonl already in record shape
  a .csv with columns: company,domain,lane,client,context|signal
  a directory of .md/.txt/.eml files (filename = company, contents = context)

Applies: domain normalisation, slug ids, dedupe by domain, suppression list.

Usage:
  prep.py batches/2026-08-16.csv --client contactout --lane revive
  prep.py batches/dumps/ --client contactout --lane revive --append
"""
import argparse, csv, json, os, re, sys, glob, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE = os.path.join(ROOT, "work", "queue.jsonl")
SUPPRESS = os.path.join(ROOT, "config", "suppress.txt")

SENDERS = {
    "contactout": {"name": "Operator Operator", "title": "Senior Manager",
                   "company": "ContactOut", "email": "operator@contactout.test"},
    "resonate": {"name": "Operator Operator", "title": "",
                 "company": "Resonate Group", "email": "operator@resonate.test"},
}


def norm_domain(d):
    if not d:
        return ""
    d = d.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0].split("?")[0]


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:40] or "record"


def load_suppress():
    if not os.path.exists(SUPPRESS):
        return set()
    out = set()
    for line in open(SUPPRESS):
        line = line.split("#")[0].strip()
        if line:
            out.add(norm_domain(line))
    return out


def from_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            yield {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}


def from_dir(path):
    for fp in sorted(glob.glob(os.path.join(path, "*"))):
        if os.path.isdir(fp) or not fp.lower().endswith((".md", ".txt", ".eml")):
            continue
        name = os.path.splitext(os.path.basename(fp))[0]
        text = open(fp, encoding="utf-8", errors="replace").read()
        m = re.search(r"(?:^|\s)((?:[a-z0-9-]+\.)+[a-z]{2,})(?:\s|/|$)", text, re.I)
        yield {"company": name.replace("-", " ").title(),
               "domain": m.group(1) if m else "",
               "context": text}


def from_jsonl(path):
    for line in open(path, encoding="utf-8"):
        if line.strip():
            yield json.loads(line)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--client", default="contactout")
    p.add_argument("--lane", default="revive", choices=["revive", "cold"])
    p.add_argument("--append", action="store_true")
    a = p.parse_args()

    if os.path.isdir(a.source):
        rows = list(from_dir(a.source))
    elif a.source.endswith(".jsonl"):
        rows = list(from_jsonl(a.source))
    elif a.source.endswith(".csv"):
        rows = list(from_csv(a.source))
    else:
        sys.exit("source must be .csv, .jsonl or a directory")

    existing = []
    if a.append and os.path.exists(QUEUE):
        existing = [json.loads(l) for l in open(QUEUE) if l.strip()]
    seen_domains = {r.get("domain") for r in existing}
    seen_ids = {r.get("id") for r in existing}
    suppress = load_suppress()

    added, skipped = [], []
    for row in rows:
        domain = norm_domain(row.get("domain"))
        company = row.get("company") or domain
        if not domain:
            skipped.append((company, "no domain"))
            continue
        if domain in suppress:
            skipped.append((company, "suppressed (live account)"))
            continue
        if domain in seen_domains:
            skipped.append((company, "duplicate domain"))
            continue
        rid = slug(row.get("id") or company)
        while rid in seen_ids:
            rid += "-2"
        lane = row.get("lane") or a.lane
        rec = {
            "id": rid, "lane": lane, "client": row.get("client") or a.client,
            "company": company, "domain": domain,
            "context": row.get("context", ""), "signal": row.get("signal", ""),
            "sender": SENDERS.get(row.get("client") or a.client, SENDERS["contactout"]),
            "state": "queued", "drop_reason": None,
            "contacts": [], "diagnosis": None, "hook": None, "sizing": None, "draft": None,
            "log": [{"step": "queued",
                     "at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
                     "note": f"ingested from {os.path.basename(a.source)}"}],
        }
        added.append(rec)
        seen_domains.add(domain)
        seen_ids.add(rid)

    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    with open(QUEUE, "w") as f:
        for r in existing + added:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"queued {len(added)} record(s) -> {QUEUE}")
    for c, why in skipped:
        print(f"  skipped {c}: {why}")


if __name__ == "__main__":
    main()
