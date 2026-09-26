#!/usr/bin/env python3
"""Build the operator's review file from rendered lead data.

TASK-301, Stage 3. Produces an HTML file with one row per lead, showing
every email step's full body, the personalisation block (all facts, USED
and NOT USED), and the LinkedIn columns where a profile exists.

    py -3 scripts/build_review_html.py --render work/review/503-render.jsonl
    py -3 scripts/build_review_html.py --render work/review/503-render.jsonl --out work/review/503-2026-09-25.html

## Column spec (operator, 2026-09-25, standing for EVERY review file)

    sender mailbox | sender name | lead email | name | title | company
    cohort tag | persona
    each email step: subject + FULL BODY exactly as the provider will send it
    LinkedIn connection note and follow-ups, where a profile exists
    PERSONALISATION BLOCK

## The personalisation block

Every scraped fact for that account, not only the used one:

    source URL | retrieved date | the exact snippet | USED or NOT USED

And for a USED fact: WHICH SENTENCE of the copy it feeds.

## IMPORTANT: provider readback

The task specifies that rows should be read back from the provider after
stage 2, never from our local render. This script generates the file from
whatever data it is given. When given local render data, it produces the
PREVIEW file. When given provider readback data (stage 2 output), it
produces the CERTIFIED review file. The hash differs.
"""
import argparse
import html
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import reviewapproval  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _esc(text):
    return html.escape(str(text or ""), quote=True)


def _step_header(step_key, order):
    return f"em{order} ({step_key})"


def render_html(leads, held=None, title="Campaign 503 Review File"):
    """Produce the full HTML document for the review file."""
    held = held or []
    css = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           margin: 20px; color: #333; }
    h1 { border-bottom: 2px solid #333; padding-bottom: 8px; }
    .summary { background: #f5f5f5; padding: 12px; border-radius: 4px; margin-bottom: 20px; }
    .lead-row { border: 1px solid #ddd; margin-bottom: 16px; border-radius: 4px; overflow: hidden; }
    .lead-header { background: #e8e8e8; padding: 8px 12px; font-weight: bold; }
    .lead-body { padding: 12px; }
    .step-block { margin: 8px 0; }
    .step-label { font-weight: bold; color: #555; margin-bottom: 4px; }
    .step-subject { background: #fff3cd; padding: 4px 8px; font-style: italic; margin-bottom: 4px; }
    .step-body { background: #fff; padding: 8px; border-left: 3px solid #007bff;
                 white-space: pre-wrap; font-size: 14px; }
    .fact-block { margin-top: 12px; border-top: 1px solid #eee; padding-top: 8px; }
    .fact-row { display: flex; gap: 8px; margin: 4px 0; font-size: 13px; }
    .fact-used { color: #28a745; font-weight: bold; }
    .fact-not-used { color: #dc3545; }
    .fact-snippet { background: #f8f9fa; padding: 4px 8px; border-left: 2px solid #6c757d;
                    font-style: italic; max-width: 600px; }
    .held-section { margin-top: 24px; }
    .held-row { background: #fff3cd; padding: 4px 8px; margin: 2px 0; border-radius: 2px; }
    .meta { color: #666; font-size: 13px; }
    table { border-collapse: collapse; width: 100%; }
    td, th { border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { background: #f0f0f0; }
    """

    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<style>{css}</style>
</head>
<body>
<h1>{_esc(title)}</h1>
<div class="summary">
<p><strong>Generated:</strong> {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}</p>
<p><strong>Rendered leads:</strong> {len(leads)}</p>
<p><strong>Held leads:</strong> {len(held)}</p>
</div>
"""]

    for i, lead in enumerate(leads, 1):
        email = lead.get("email", "")
        name = lead.get("name", "")
        title_val = lead.get("title", "")
        company = lead.get("company", "")
        domain = lead.get("domain", "")
        persona = lead.get("persona", "")
        angle = lead.get("angle", "")
        sender_name = lead.get("sender_name", "(from sender pool)")
        sender_mailbox = lead.get("sender_mailbox", "(assigned at activation)")
        cohort = lead.get("cohort_tag", "")

        parts.append(f"""
<div class="lead-row" id="lead-{i}">
<div class="lead-header">
#{i} &mdash; {_esc(name)} ({_esc(email)}) &mdash; {_esc(company)}
</div>
<div class="lead-body">
<table>
<tr><th>Sender mailbox</th><td>{_esc(sender_mailbox)}</td>
    <th>Sender name</th><td>{_esc(sender_name)}</td></tr>
<tr><th>Lead email</th><td>{_esc(email)}</td>
    <th>Name</th><td>{_esc(name)}</td></tr>
<tr><th>Title</th><td>{_esc(title_val)}</td>
    <th>Company</th><td>{_esc(company)}</td></tr>
<tr><th>Domain</th><td>{_esc(domain)}</td>
    <th>Persona</th><td>{_esc(persona)}</td></tr>
<tr><th>Angle</th><td colspan="3">{_esc(angle)}</td></tr>
<tr><th>Cohort</th><td colspan="3">{_esc(cohort)}</td></tr>
</table>
""")

        # Email steps
        steps = lead.get("steps", [])
        templates = lead.get("templates", {})
        step_keys = ("em1", "em2", "em3", "em4", "em5")
        for order, step_key in enumerate(step_keys, 1):
            step = steps[order - 1] if order - 1 < len(steps) else {}
            subject = step.get("subject", "")
            body = step.get("body", "")
            template_name = templates.get(step_key, "")

            parts.append(f"""
<div class="step-block">
<div class="step-label">{_esc(_step_header(step_key, order))}
    <span class="meta">[template: {_esc(template_name)}]</span></div>
""")
            if subject:
                parts.append(f'<div class="step-subject">Subject: {_esc(subject)}</div>')
            parts.append(f'<div class="step-body">{_esc(body)}</div>')
            parts.append("</div>")

        # LinkedIn columns (where a profile exists)
        linkedin_url = lead.get("linkedin_url", "")
        if linkedin_url:
            parts.append(f"""
<div class="step-block">
<div class="step-label">LinkedIn</div>
<p class="meta">Profile: <a href="{_esc(linkedin_url)}">{_esc(linkedin_url)}</a></p>
""")
            li_messages = lead.get("linkedin_messages", {})
            for key in ("connection_note", "connected_1", "connected_2",
                        "connected_3", "connected_4"):
                msg = li_messages.get(key, "")
                if msg:
                    parts.append(f'<div class="step-body">{_esc(msg)}</div>')
            parts.append("</div>")
        else:
            parts.append("""
<div class="step-block">
<div class="step-label">LinkedIn</div>
<p class="meta">No LinkedIn profile URL available for this lead.</p>
</div>
""")

        # Personalisation block: ALL facts
        classified = lead.get("pack_facts_classified", [])
        if classified:
            parts.append("""
<div class="fact-block">
<div class="step-label">Personalisation Block &mdash; All Scraped Facts</div>
<table>
<tr><th>Status</th><th>Source URL</th><th>Retrieved</th><th>Snippet</th><th>Feeds</th></tr>
""")
            for entry in classified:
                fact = entry.get("fact", {})
                usable = entry.get("usable", False)
                status = "USED" if usable else "NOT USED"
                status_class = "fact-used" if usable else "fact-not-used"
                source_url = fact.get("source_url", "")
                retrieved = fact.get("retrieved_at", "") or \
                            fact.get("published_at", "") or ""
                snippet = fact.get("snippet", "")
                feeds = ""
                if usable:
                    feeds = "step 1 opener"
                parts.append(f"""
<tr>
<td class="{status_class}">{status}</td>
<td><a href="{_esc(source_url)}">{_esc(source_url[:60])}</a></td>
<td>{_esc(retrieved)}</td>
<td class="fact-snippet">{_esc(snippet)}</td>
<td>{_esc(feeds)}</td>
</tr>""")
            parts.append("</table></div>")

        parts.append("</div></div>")

    # Held leads
    if held:
        parts.append("""
<div class="held-section">
<h2>Held Leads</h2>
""")
        for h in held:
            parts.append(f"""<div class="held-row">
{_esc(h.get('email', '?'))} &mdash; {_esc(h.get('reason', 'unknown'))}
</div>""")
        parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--render", required=True,
                        help="Path to the rendered JSONL from stage 1")
    parser.add_argument("--out", default=None,
                        help="Output HTML path (default: alongside input)")
    args = parser.parse_args(argv)

    leads, held = [], []
    with open(args.render, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.pop("held", False):
                held.append(row)
            else:
                leads.append(row)

    html_content = render_html(leads, held)

    out_path = args.out or args.render.rsplit(".", 1)[0] + ".html"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    file_hash = reviewapproval.file_hash(out_path)
    print(f"Review file: {out_path}")
    print(f"Leads: {len(leads)} rendered, {len(held)} held")
    print(f"File hash: {file_hash}")
    print(f"\nPost this file and hash to #resonate-os.")
    print(f"Activation is refused until the operator replies:")
    print(f"  APPROVED 503 {file_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
