#!/usr/bin/env python3
"""Review sheet, push file and summary. BUILD-SPEC section 2.

Read only: render never writes to the queue and never changes a record's state.
The amber "held" marking here is a render-time classification, phase 4 owns the
actual state transition.

  python -m src.render        -> out/review.html, out/emailbison.csv, out/summary.json
"""
import argparse
import html
import json
import os
from collections import Counter

from . import export, lint, store

ROOT = store.ROOT


def out_dir():
    """One definition of where output goes, shared with personas.py."""
    return store.out_dir()


def clean_steps(results):
    """The only source of rows for a push file. Nothing else may feed it."""
    return [r for r in results if r["status"] == "clean"]


def name_parts(contact):
    parts = ((contact or {}).get("name") or "").split()
    return (parts[0] if parts else "", " ".join(parts[1:]))


HEADER = ["email", "first_name", "last_name", "company", "domain", "title",
          "subject", "body", "lane", "day", "record_id"]


def emailbison_rows(results):
    """Every row is re-checked here, before a single byte is written."""
    rows = []
    for r in clean_steps(results):
        # Belt and braces: a row is built only if it still lints clean.
        if r["failures"]:
            raise AssertionError(
                f"{lint.step_id(r)} reached the push file with failures")
        rec, contact, step = r["record"], r["contact"], r["step"]
        first, last = name_parts(contact)
        rows.append([contact.get("email", ""), first, last, rec.get("company", ""),
                     rec.get("domain", ""), contact.get("title", ""),
                     step.get("subject", ""), step.get("body", ""),
                     rec.get("lane", ""), r["day"], rec["id"]])
    return rows


def write_emailbison(results, path):
    """Every push file goes through export.write_csv, which is the only
    writer that knows a prospect's name can be a formula."""
    rows = emailbison_rows(results)      # raises before the file is touched
    export.write_csv(path, HEADER, rows)


def esc(s):
    return html.escape(str(s or ""))


ORDER = {"failed": 0, "held": 1, "clean": 2}
LABEL = {"failed": "failed lint", "held": "held, address not cleared", "clean": "clean"}

STYLE = """
:root{--bg:#0E1116;--card:#161B22;--line:#232A33;--fg:#E9EEF3;--mut:#93A1AF;
--acc:#4DD0B1;--bad:#FF7B72;--warn:#E3B341}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:40px}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:28px;margin:0 0 6px}
.sum{color:var(--mut);margin-bottom:32px}
.sum b{color:var(--fg)}
article{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--line);border-radius:12px;padding:22px;margin-bottom:20px}
article.failed{border-left-color:var(--bad)}
article.held{border-left-color:var(--warn)}
article.clean{border-left-color:var(--acc)}
.top{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
h2{font-size:19px;margin:0}
.lane,.day{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);border:1px solid var(--line);padding:2px 8px;border-radius:20px}
.tag{font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:20px;border:1px solid}
.tag.failed{color:var(--bad)} .tag.held{color:var(--warn)} .tag.clean{color:var(--acc)}
.meta{color:var(--mut);font-size:13px;margin-top:6px}
code{color:var(--fg)}
.why{color:var(--mut);font-size:14px;border-left:2px solid var(--line);padding-left:12px;margin:16px 0}
.subject{font-weight:600;margin:16px 0 8px}
pre{white-space:pre-wrap;font:inherit;background:#0E1116;border:1px solid var(--line);border-radius:8px;padding:16px;margin:0}
footer{margin-top:14px;font-size:13px}
footer.failed{color:var(--bad)} footer.held{color:var(--warn)} footer.clean{color:var(--acc)}
ul{color:var(--mut)}
"""


def card(r):
    rec, contact, step = r["record"], r["contact"], r["step"]
    status = r["status"]
    detail = "; ".join(r["failures"]) or "passes every rule"
    diag = rec.get("diagnosis") or {}
    if rec.get("lane") == "revive":
        why = f"<b>{esc(diag.get('died_on'))}</b> {esc(diag.get('died_because'))}"
    else:
        why = esc(rec.get("hook") or "")
    return (
        f'<article class="{status}">\n'
        f'  <header>\n'
        f'    <div class=top><h2>{esc(rec.get("company"))}</h2>\n'
        f'      <span class=lane>{esc(rec.get("lane"))}</span>\n'
        f'      <span class=day>{esc(r["day"])}</span>\n'
        f'      <span class="tag {status}">{esc(LABEL[status])}</span></div>\n'
        f'    <div class=meta>{esc((contact or {}).get("name"))} &middot; '
        f'{esc((contact or {}).get("title"))} &middot; '
        f'<code>{esc((contact or {}).get("email"))}</code> &middot; '
        f'{esc((contact or {}).get("verdict"))}</div>\n'
        f'  </header>\n'
        f'  <p class=why>{why}</p>\n'
        f'  <div class=subject>{esc(step.get("subject"))}</div>\n'
        f'  <pre>{esc(step.get("body"))}</pre>\n'
        f'  <footer class="{status}">{esc(detail)}</footer>\n'
        f'</article>\n')


def review_html(recs, results):
    cards = "".join(card(r) for r in
                    sorted(results, key=lambda r: (ORDER[r["status"]], r["id"])))
    counts = Counter(r["status"] for r in results)
    dropped = [r for r in recs if r.get("state") == "dropped"]
    droplist = "".join(f'<li><b>{esc(r.get("company"))}</b> {esc(r.get("drop_reason"))}</li>'
                       for r in dropped)
    drops = f"<h1>Dropped</h1><ul>{droplist}</ul>" if dropped else ""
    return (
        "<!doctype html><meta charset=utf-8>\n<title>Batch review</title>\n"
        f"<style>{STYLE}</style>\n"
        "<div class=wrap>\n<h1>Batch review</h1>\n"
        f'<div class=sum><b>{len(results)}</b> generated email(s): '
        f'<b>{counts.get("failed", 0)}</b> failed lint, '
        f'<b>{counts.get("held", 0)}</b> held, '
        f'<b>{counts.get("clean", 0)}</b> clean &middot; '
        f'<b>{len(dropped)}</b> dropped record(s) &middot; '
        f'generated {esc(store.now())}</div>\n'
        f"{cards}{drops}\n</div>\n")


def summary(recs, results):
    counts = Counter(r["status"] for r in results)
    return {
        "generated": store.now(),
        "records": len(recs),
        "states": dict(Counter(r.get("state") for r in recs)),
        "lanes": dict(Counter(r.get("lane") for r in recs)),
        "emails": len(results),
        "clean": counts.get("clean", 0),
        "held": counts.get("held", 0),
        "failed": counts.get("failed", 0),
        "failure_modes": dict(Counter((r.get("diagnosis") or {}).get("failure_mode")
                                      for r in recs if r.get("diagnosis"))),
        "lint_failed": {lint.step_id(r): r["failures"] for r in results if r["failures"]},
        "dropped": {r["id"]: r.get("drop_reason") for r in recs
                    if r.get("state") == "dropped"},
    }


def build():
    recs = store.load()
    results = lint.check_all(recs)
    # Build everything, including the guarded push rows, before writing anything,
    # so a tripped guard cannot leave a half-written push file behind.
    html_page = review_html(recs, results)
    s = summary(recs, results)
    rows = emailbison_rows(results)

    out = out_dir()
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "review.html"), "w", encoding="utf-8") as f:
        f.write(html_page)
    export.write_csv(os.path.join(out, "emailbison.csv"), HEADER, rows)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    return s


def main(argv=None):
    argparse.ArgumentParser(prog="python -m src.render").parse_args(argv)
    s = build()
    print(f"{s['emails']} generated email(s): {s['failed']} failed, "
          f"{s['held']} held, {s['clean']} clean")
    for step, fails in s["lint_failed"].items():
        print(f"  {step}: {'; '.join(fails)}")
    print(f"wrote {out_dir()}/review.html, emailbison.csv, summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
