#!/usr/bin/env python3
"""Lint every draft, then emit the review sheet and the push-ready files.

  build.py            -> out/review.html, out/emailbison.csv, out/heyreach.csv, out/summary.json
  build.py --lint     -> lint only, non-zero exit if anything fails
"""
import argparse, csv, html, json, os, re, datetime
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE = os.path.join(ROOT, "work", "queue.jsonl")
OUT = os.path.join(ROOT, "out")

BANNED_PHRASES = [
    "i hope this email finds you well", "i wanted to reach out", "circling back",
    "just following up", "touching base", "quick question for you",
    "let me know if you'd like to hop on", "synergy", "game-changer",
    "revolutionary", "cutting-edge", "as per my last email",
]


def lint(rec):
    """Returns list of failures. These are the rules the batch session must satisfy."""
    f = []
    d = rec.get("draft") or {}
    body = d.get("body", "")
    subj = d.get("subject", "")

    if not d.get("to"):
        f.append("no recipient")
    if not subj:
        f.append("no subject")
    if len(subj) > 60:
        f.append(f"subject {len(subj)} chars, over 60")
    if subj[:1].isupper() and subj.isupper():
        f.append("subject is shouting")

    if "—" in body or "—" in subj or "–" in body:
        f.append("em/en dash present")
    # No attachments ever. Catch real attachment talk, not the idiom
    # "with no pitch attached".
    if re.search(r"\battachment\b"
                 r"|attached (is|are|you'?ll|please|here|below)"
                 r"|(see|find|i'?ve|i have|we'?ve) attached"
                 r"|attached (file|screenshot|deck|pdf|doc|csv|list|sheet|rate card)"
                 r"|(file|screenshot|deck|pdf|doc|csv|sheet|rate card|image)s? attached",
                 body, re.I):
        f.append("mentions an attachment")
    if re.search(r"[\[{<](?!http)[^\]}>\n]{2,40}[\]}>]", body):
        f.append("unfilled placeholder in body")

    words = len(body.split())
    if words > 180:
        f.append(f"{words} words, over 180")
    if words < 40:
        f.append(f"{words} words, too thin")

    for para in body.split("\n\n"):
        for line in para.split("\n"):
            if line.strip() and len(line) < 75 and line is not para.split("\n")[-1]:
                f.append("hard-wrapped paragraph")
                break

    low = body.lower()
    for ph in BANNED_PHRASES:
        if ph in low:
            f.append(f"filler phrase: {ph}")

    if rec.get("lane") == "revive" and not (rec.get("diagnosis") or {}).get("died_because"):
        f.append("revive record with no diagnosis")
    if rec.get("lane") == "cold" and not rec.get("hook"):
        f.append("cold record with no hook")

    prim = [c for c in rec.get("contacts") or [] if c.get("email") == d.get("to")]
    if not prim:
        f.append("recipient not in verified contact list")
    else:
        c = prim[0]
        if c.get("verdict") == "invalid":
            f.append("recipient verified invalid")
        if c.get("verdict") == "unknown":
            f.append("recipient unverified")
        if c.get("verdict") == "accept_all" and not (c.get("reoon") or {}).get("is_safe_to_send"):
            f.append("catch-all recipient without a passing Reoon check")
    return f


def load():
    return [json.loads(l) for l in open(QUEUE) if l.strip()]


def esc(s):
    return html.escape(s or "")


def review_html(recs, results):
    rows = []
    for r in recs:
        if not r.get("draft"):
            continue
        d = r["draft"]
        fails = results[r["id"]]
        badge = ("<span class=ok>clean</span>" if not fails else
                 "<span class=bad>" + esc("; ".join(fails)) + "</span>")
        prim = next((c for c in r["contacts"] if c["email"] == d["to"]), {})
        diag = r.get("diagnosis") or {}
        why = (f"<b>{esc(diag.get('died_on',''))}</b> {esc(diag.get('died_because',''))}"
               if r["lane"] == "revive" else esc(r.get("hook", "")))
        rows.append(f"""
<article>
  <header>
    <div><h2>{esc(r['company'])}</h2><span class=lane>{esc(r['lane'])}</span></div>
    <div class=meta>{esc(prim.get('name',''))} &middot; {esc(prim.get('title',''))} &middot;
      <code>{esc(d['to'])}</code> &middot; {esc(prim.get('verdict',''))}</div>
  </header>
  <p class=why>{why}</p>
  <div class=subject>{esc(d['subject'])}</div>
  <pre>{esc(d['body'])}</pre>
  <footer>{badge}</footer>
</article>""")

    drafted = sum(1 for r in recs if r.get("draft"))
    dropped = [r for r in recs if r.get("state") == "dropped"]
    droplist = "".join(
        f"<li><b>{esc(r['company'])}</b> {esc(r.get('drop_reason',''))}</li>" for r in dropped)
    clean = sum(1 for v in results.values() if not v)
    stamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    return f"""<!doctype html><meta charset=utf-8>
<title>Batch review</title>
<style>
:root{{--bg:#0E1116;--card:#161B22;--line:#232A33;--fg:#E9EEF3;--mut:#93A1AF;--acc:#4DD0B1;--bad:#FF7B72}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:40px}}
.wrap{{max-width:860px;margin:0 auto}}
h1{{font-size:28px;margin:0 0 6px}}
.sum{{color:var(--mut);margin-bottom:32px}}
.sum b{{color:var(--acc)}}
article{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px;margin-bottom:20px}}
article header div:first-child{{display:flex;align-items:center;gap:10px}}
h2{{font-size:19px;margin:0}}
.lane{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--acc);border:1px solid var(--line);padding:2px 8px;border-radius:20px}}
.meta{{color:var(--mut);font-size:13px;margin-top:6px}}
code{{color:var(--fg)}}
.why{{color:var(--mut);font-size:14px;border-left:2px solid var(--acc);padding-left:12px;margin:16px 0}}
.subject{{font-weight:600;margin:16px 0 8px}}
pre{{white-space:pre-wrap;font:inherit;background:#0E1116;border:1px solid var(--line);border-radius:8px;padding:16px;margin:0}}
footer{{margin-top:14px;font-size:13px}}
.ok{{color:var(--acc)}} .bad{{color:var(--bad)}}
ul{{color:var(--mut)}}
</style>
<div class=wrap>
<h1>Batch review</h1>
<div class=sum><b>{drafted}</b> drafts, <b>{clean}</b> clean on lint,
<b>{len(dropped)}</b> dropped &middot; generated {stamp}</div>
{''.join(rows)}
{'<h1>Dropped</h1><ul>' + droplist + '</ul>' if dropped else ''}
</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lint", action="store_true")
    a = ap.parse_args()

    recs = load()
    results = {r["id"]: lint(r) for r in recs if r.get("draft")}

    for rid, fails in results.items():
        print(f"{rid:<20} {'OK' if not fails else '; '.join(fails)}")
    if a.lint:
        raise SystemExit(1 if any(results.values()) else 0)

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "review.html"), "w").write(review_html(recs, results))

    with open(os.path.join(OUT, "emailbison.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["email", "first_name", "last_name", "company", "domain",
                    "title", "subject", "body", "lane", "record_id"])
        for r in recs:
            d = r.get("draft")
            if not d or results[r["id"]]:
                continue
            c = next((x for x in r["contacts"] if x["email"] == d["to"]), {})
            parts = (c.get("name") or "").split()
            w.writerow([d["to"], parts[0] if parts else "", " ".join(parts[1:]),
                        r["company"], r["domain"], c.get("title", ""),
                        d["subject"], d["body"], r["lane"], r["id"]])

    with open(os.path.join(OUT, "heyreach.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["linkedin_url", "first_name", "last_name", "company", "title", "note", "record_id"])
        for r in recs:
            for c in r.get("contacts") or []:
                if c.get("linkedin"):
                    parts = (c.get("name") or "").split()
                    w.writerow([c["linkedin"], parts[0] if parts else "", " ".join(parts[1:]),
                                r["company"], c.get("title", ""),
                                (r.get("hook") or (r.get("diagnosis") or {}).get("died_because", ""))[:280],
                                r["id"]])

    summary = {
        "generated": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "records": len(recs),
        "states": dict(Counter(r["state"] for r in recs)),
        "lanes": dict(Counter(r["lane"] for r in recs)),
        "failure_modes": dict(Counter((r.get("diagnosis") or {}).get("failure_mode")
                                      for r in recs if r.get("diagnosis"))),
        "lint_clean": sum(1 for v in results.values() if not v),
        "lint_failed": {k: v for k, v in results.items() if v},
        "dropped": {r["id"]: r.get("drop_reason") for r in recs if r["state"] == "dropped"},
    }
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=2)
    print(f"\nwrote {OUT}/review.html, emailbison.csv, heyreach.csv, summary.json")


if __name__ == "__main__":
    main()
