#!/usr/bin/env python3
"""The five files a person reads before a campaign runs.

    out/preview.html            the whole rehearsal, for a non-developer
    out/preview.json            the same data, for anything that is not a person
    out/emailbison-preview.csv  what would be uploaded, if it were
    out/heyreach-preview.json   the same for LinkedIn
    out/report-preview.html     the client report as it would read today

The HTML is written for somebody who has never seen this codebase. That means
no status codes without a sentence beside them, no compressed timeline, and no
number whose provenance is not one click away. A preview that only a developer
can check is a preview nobody checks.

Every address is masked unless `--reveal-emails` is given, both CSVs go through
`src/export.py` so a prospect's name cannot execute in a spreadsheet, and the
word "preview" is in every filename because these files must never be mistaken
for something to upload.
"""
import argparse
import html
import os

from . import channels, export, quality, simulator, store

TITLE = "Campaign preview"

# A full card is roughly 11 KB of HTML, so 5,000 domains would render a 57 MB
# page that no browser opens and nobody reads. The cards are capped and what
# was left out is stated on the page - a preview that silently shows the first
# two hundred of five thousand reads as "this is all of it", which is worse
# than a page that is too big to open.
MAX_CARDS = 200

STYLE = """
:root { --ink:#1a1a1a; --muted:#666; --line:#e3e3e3; --bg:#fff;
        --ok:#0a7f3f; --warn:#8a6100; --bad:#a11; --held:#5a4a8a; }
* { box-sizing: border-box; }
body { font: 15px/1.55 -apple-system, "Segoe UI", Roboto, sans-serif;
       color: var(--ink); background: var(--bg); margin: 0 auto; padding: 32px;
       max-width: 1100px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 19px; margin: 36px 0 10px; padding-top: 18px;
     border-top: 2px solid var(--line); }
h3 { font-size: 16px; margin: 22px 0 6px; }
h4 { font-size: 13px; text-transform: uppercase; letter-spacing: .07em;
     color: var(--muted); margin: 16px 0 6px; }
.sub { color: var(--muted); margin: 0 0 24px; }
.headline { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
            gap: 12px; margin: 20px 0 8px; }
.stat { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
.stat .n { font-size: 26px; font-weight: 600; }
.stat .k { color: var(--muted); font-size: 12px; text-transform: uppercase;
           letter-spacing: .05em; }
.note { background: #f7f7f5; border-left: 3px solid var(--muted);
        padding: 10px 14px; margin: 16px 0; color: #333; }
.card { border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px;
        margin: 18px 0; }
.card > .who { display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; }
.who .name { font-size: 18px; font-weight: 600; }
.who .title { color: var(--muted); }
table { border-collapse: collapse; width: 100%; margin: 8px 0 4px;
        font-size: 14px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line);
         vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 12px;
     text-transform: uppercase; letter-spacing: .05em; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px;
       font-size: 12px; border: 1px solid var(--line); }
.ok { color: var(--ok); border-color: var(--ok); }
.bad { color: var(--bad); border-color: var(--bad); }
.warn { color: var(--warn); border-color: var(--warn); }
.held { color: var(--held); border-color: var(--held); }
ul { margin: 4px 0 8px; padding-left: 20px; }
li { margin: 3px 0; }
.step { border-left: 3px solid var(--line); padding: 8px 0 8px 14px;
        margin: 10px 0; }
.step.skipped { border-left-color: var(--bad); background: #fdf5f5; }
.step.duplicate { border-left-color: var(--bad); background: #fdf5f5; }
.dup { color: var(--bad); font-weight: 600; }
.step.blocked { border-left-color: var(--bad); }
.step.waiting { border-left-color: var(--warn); }
.day { font-weight: 600; }
.copy { white-space: pre-wrap; background: #fafafa; border: 1px solid var(--line);
        border-radius: 6px; padding: 10px 12px; margin: 6px 0; font-size: 14px; }
.subject { font-weight: 600; margin: 6px 0 0; }
.src { color: var(--muted); font-size: 13px; word-break: break-all; }
.wrap { overflow-x: auto; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#eee; --muted:#9a9a9a; --line:#333; --bg:#141414;
          --ok:#4ade80; --warn:#fbbf24; --bad:#f87171; --held:#a78bfa; }
  .note { background:#1e1e1e; } .copy { background:#1b1b1b; }
  .step.skipped { background:#241a1a; }
}
"""


def esc(value):
    return html.escape(str(value if value is not None else ""))


def mask(address, reveal=False):
    """An address a reviewer can recognise without the page becoming a leak."""
    if not address:
        return ""
    if reveal:
        return address
    name, _, domain = address.partition("@")
    if not domain:
        return "***"
    shown = name[:2] if len(name) > 3 else name[:1]
    return f"{shown}{'*' * max(3, len(name) - len(shown))}@{domain}"


def _duplicate_sentence(result):
    """What the duplicate counts mean, in words, on the summary table."""
    bodies = result["headline"].get("duplicate_bodies") or 0
    subjects = result["headline"].get("duplicate_subjects") or 0
    if not bodies and not subjects:
        return "none: no two email steps for one person say the same thing"
    parts = []
    if bodies:
        parts.append(f"<strong>{bodies} pair(s) send the same message "
                     "twice. This blocks approval until the step is "
                     "regenerated</strong>")
    if subjects:
        parts.append(f"{subjects} pair(s) share a subject line with different "
                     "bodies, which is reported and does not block")
    return " · ".join(parts)


def _stat(key, value):
    return (f'<div class="stat"><div class="n">{esc(value)}</div>'
            f'<div class="k">{esc(key.replace("_", " "))}</div></div>')


def _tag(text, kind=""):
    return f'<span class="tag {kind}">{esc(text)}</span>'


def _mx_absent(card):
    """Why an MX cell is empty. A blank cell reads as a broken page; the two
    reasons it can be blank are different facts and both are worth saying."""
    return ("no MX check has been run for this contact"
            if not card.get("mx_records") else "not identified")


def _channel_tags(card):
    out = []
    if card["email_eligible"]:
        out.append(_tag("email", "ok"))
    else:
        out.append(_tag(f"no email — {card['email_excluded_explained']}", "bad"))
    if card["linkedin_eligible"]:
        out.append(_tag("linkedin", "ok"))
    else:
        out.append(_tag(f"no linkedin — {card['linkedin_excluded_explained']}",
                        "bad"))
    if card["held"]:
        out.append(_tag("held for review", "held"))
    return " ".join(out)


def _evidence_list(rows):
    if not rows:
        return "<p class='src'>Nothing was retained.</p>"
    items = []
    for row in rows:
        provenance = row.get("provenance") or {}
        source = provenance.get("source_url") or "no source url"
        published = provenance.get("published_at") or "undated"
        items.append(
            f"<li>{esc(row.get('fact'))}<br>"
            f"<span class='src'>{esc(published)} · "
            f"{esc(provenance.get('source_type') or 'unknown source')} · "
            f"{esc(source)}</span></li>")
    return "<ul>" + "".join(items) + "</ul>"


def _timeline(card, reveal):
    out = []
    for row in card["timeline"]:
        status = row.get("status") or "unknown"
        css = status if status in ("skipped", "blocked", "waiting") else ""
        if row.get("duplicate"):
            css += " duplicate"
        head = (f'<div class="step {css}"><div><span class="day">DAY '
                f'{esc(row.get("day"))}</span> · '
                f'{esc((row.get("channel") or "").upper())} · '
                f'{_tag(status, "bad" if status in ("skipped", "blocked") else "")}')
        if row.get("duplicate"):
            head += (f' {_tag("DUPLICATE COPY", "bad")}'
                     f' <span class="dup">{esc(row["duplicate_of"])}</span>')
        if row.get("reason"):
            head += f' <span class="src">{esc(row["reason"])}</span>'
        head += "</div>"
        body = ""
        if row.get("subject"):
            body += f'<p class="subject">subject: {esc(row["subject"])}</p>'
        if row.get("body"):
            body += f'<div class="copy">{esc(row["body"])}</div>'
        if row.get("note"):
            body += f'<div class="copy">{esc(row["note"])}</div>'
        if row.get("lint"):
            body += ("<p class='src'>lint: "
                     + esc(", ".join(row["lint"])) + "</p>")
        if not body and status == "not_planned":
            body = "<p class='src'>not part of this contact's cadence</p>"
        out.append(head + body + "</div>")
    return "".join(out)


def _card_html(card, reveal):
    quality_block = card["personalization_quality"]
    components = "".join(
        f"<tr><td>{esc(name.replace('_', ' '))}</td>"
        f"<td>{esc(value)}</td></tr>"
        for name, value in quality_block["components"].items())
    return f"""
<div class="card">
  <div class="who">
    <span class="name">{esc(card['name'] or '(no name)')}</span>
    <span class="title">{esc(card['title'])}</span>
    <span class="src">{esc(card['company'])} · {esc(card['domain'])}</span>
  </div>
  <p>{_channel_tags(card)}</p>
  <table>
    <tr><th>persona</th><td>{esc(card['persona'])}</td>
        <th>angle</th><td>{esc(card['angle'])}</td></tr>
    <tr><th>email</th><td>{esc(mask(card['email'], reveal))}</td>
        <th>verification</th><td>{esc(card['email_verification'])}</td></tr>
    <tr><th>MX provider</th>
        <td>{esc(card['mx_provider'] or _mx_absent(card))}</td>
        <th>MX class</th>
        <td>{esc(card['mx_classification'] or _mx_absent(card))}</td></tr>
    <tr><th>linkedin</th><td class="src">{esc(card['linkedin'])}</td>
        <th>mode</th><td>{esc(card['mode'])}</td></tr>
  </table>

  <h4>Why this person</h4>
  <ul>{''.join(f'<li>{esc(line)}</li>' for line in card['why_this_person'])}</ul>

  <h4>Why this company</h4>
  <ul>{''.join(f'<li>{esc(line)}</li>' for line in card['why_this_company'])}</ul>

  <h4>Research used — company</h4>
  {_evidence_list(card['company_research']['facts'])}

  <h4>Research used — person</h4>
  {_evidence_list(card['person_research']['facts'])}
  {''.join(f"<p class='src'>{esc(line)}</p>"
           for line in card['person_research']['unavailable_because'])}

  <h4>Personalisation evidence given to the model</h4>
  {_evidence_list(card['personalization_evidence']['selected'])}
  <p class="src">{esc(len(card['personalization_evidence']['selected']))} of
     {esc(card['personalization_evidence']['considered'])} pieces considered ·
     band <strong>{esc(quality_block['band'])}</strong> ·
     {esc(quality_block['why'])}</p>
  <div class="wrap"><table>{components}</table></div>

  <h4>Final cadence, exactly as it would run</h4>
  {_timeline(card, reveal)}
</div>"""


def _company_html(company, reveal):
    status = ("accepted" if company["accepted"]
              else f"rejected: {company['rejected_reason']}")
    paused = ("<p class='note'>This company is paused: "
              + esc((company["paused"] or {}).get("reason")) + "</p>"
              if company.get("paused") else "")
    not_selected = ""
    if company["not_selected"]:
        rows = "".join(f"<li>{esc(c['name'] or c['contact_key'])} — "
                       f"{esc(c['reason'])}</li>"
                       for c in company["not_selected"])
        not_selected = f"<h4>Found but not selected</h4><ul>{rows}</ul>"
    return f"""
<h2>{esc(company['company'])} <span class="src">{esc(company['domain'])} ·
    {esc(status)} · {esc(company['contacts_selected'])} of
    {esc(company['contacts_found'])} contacts selected</span></h2>
{paused}
{not_selected}
{''.join(_card_html(card, reveal) for card in company['cards'])}"""


def _bounded(result, max_cards):
    """Companies to render, and an honest sentence about the rest."""
    companies, shown = [], 0
    for company in result["companies"]:
        if shown >= max_cards:
            break
        cards = company["cards"][:max(0, max_cards - shown)]
        shown += len(cards)
        companies.append({**company, "cards": cards})
    total = sum(len(c["cards"]) for c in result["companies"])
    omitted = total - shown
    note = ""
    if omitted:
        note = (f"<div class='note'><strong>{omitted} of {total} contact cards "
                f"are not shown on this page.</strong> The cap is "
                f"{max_cards} cards, because a page with every card at this "
                f"batch size does not open. Every number above counts the "
                f"whole batch, and <code>preview.json</code> contains all of "
                f"it.</div>")
    return companies, note


def page(result, reveal=False, max_cards=MAX_CARDS):
    headline = result["headline"]
    qa = simulator.qa_metrics(result)
    companies, omitted_note = _bounded(result, max_cards)
    stats = "".join(_stat(name, headline[name]) for name in simulator.HEADLINE)
    bands = result["personalization"]["bands"]
    return f"""<title>{TITLE}</title>
<style>{STYLE}</style>
<h1>{esc(TITLE)}</h1>
<p class="sub">{esc(result['client'] or 'no client')} ·
   {esc(result['batch'] or result['campaign_id'] or 'whole queue')} ·
   generated {esc(result['generated_at'])}</p>

<div class="note"><strong>Nothing here has been sent.</strong> This page is
built from stored data only: no email, no LinkedIn message, no connection
request, and no provider was called to produce it. Addresses are
{'shown in full' if reveal else 'masked'}.</div>

<div class="headline">{stats}</div>

<h2>What the numbers mean</h2>
<table>
<tr><th>Companies</th><td>{esc(headline['companies'])} uploaded ·
    {esc(headline['companies_accepted'])} accepted ·
    {esc(headline['companies_rejected'])} rejected</td></tr>
<tr><th>Reachable by email</th><td>{esc(headline['email_eligible'])} of
    {esc(headline['contacts'])} — the rest have no verified address or sit
    behind a filtering gateway</td></tr>
<tr><th>Reachable on LinkedIn</th><td>{esc(headline['linkedin_eligible'])} of
    {esc(headline['contacts'])}</td></tr>
<tr><th>Both</th><td>{esc(headline['multichannel'])}</td></tr>
<tr><th>Neither</th><td>{esc(headline['held'])} — held for review, not
    deleted</td></tr>
<tr><th>Blocked by a gateway</th><td>{esc(headline['mx_blocked'])} — email
    only; LinkedIn is untouched</td></tr>
<tr><th>Copy that fails lint</th><td>{esc(headline['lint_failures'])} step(s) —
    these cannot be sent as written</td></tr>
<tr><th>Duplicate emails</th><td>{_duplicate_sentence(result)}</td></tr>
<tr><th>Personalisation</th><td>high {esc(bands.get('high', 0))} ·
    medium {esc(bands.get('medium', 0))} · low {esc(bands.get('low', 0))}</td></tr>
<tr><th>Estimated cost</th><td>{esc(result['credits']['expected'])} credits
    expected, {esc(result['credits']['maximum'])} at most ·
    {esc(result['credits']['unit'])}</td></tr>
<tr><th>Approval</th><td>{esc(result['approval']['state'])} —
    {esc(result['approval']['detail'])}</td></tr>
<tr><th>Would send now</th><td>{esc(result['would_send'])}</td></tr>
</table>

<h2>Quality checks before approval</h2>
<div class="wrap"><table>
{''.join(f"<tr><th>{esc(k.replace('_', ' '))}</th><td>{esc(v)}</td></tr>"
         for k, v in qa.items())}
</table></div>

{omitted_note}
{''.join(_company_html(company, reveal) for company in companies)}
"""


def report_page(result):
    """The client-facing view: what has happened, and what has not yet."""
    report = simulator.reporting_preview(result)
    rows = []
    for key, value in report.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k}: {v}" for k, v in value.items()) or "none"
        if value is None:
            value = "not observable by this system"
        rows.append(f"<tr><th>{esc(key.replace('_', ' '))}</th>"
                    f"<td>{esc(value)}</td></tr>")
    return f"""<title>Client report preview</title>
<style>{STYLE}</style>
<h1>Client report preview</h1>
<p class="sub">{esc(result['client'] or 'no client')} ·
   generated {esc(result['generated_at'])}</p>
<div class="note">Nothing has been sent yet, so every delivery metric below is
<strong>zero</strong> rather than missing. Where a metric says "not observable
by this system", that is a different statement: it means nothing here can
measure it, and it will stay that way until somebody records it by hand.</div>
<div class="wrap"><table>{''.join(rows)}</table></div>
"""


# ------------------------------------------------------------- upload files

EMAILBISON_HEADER = ["email", "first_name", "last_name", "company", "domain",
                     "title", "persona", "angle", "step", "day", "subject",
                     "body", "record_id", "contact_key", "status"]


def emailbison_rows(result, reveal=False):
    """What would be uploaded. Every row is a step, and skipped rows say so."""
    rows = []
    for company in result["companies"]:
        for card in company["cards"]:
            first, _, last = (card.get("name") or "").partition(" ")
            for step in card["timeline"]:
                if step.get("channel") != "email":
                    continue
                if step.get("status") == "not_planned":
                    continue
                rows.append([
                    mask(card.get("email"), reveal), first, last,
                    card.get("company"), card.get("domain"), card.get("title"),
                    card.get("persona"), card.get("angle"),
                    step.get("step"), step.get("day"), step.get("subject"),
                    step.get("body"), card.get("record_id"),
                    card.get("contact_key"), step.get("status"),
                ])
    return rows


def heyreach_payload(result, reveal=False):
    """The LinkedIn side, in the shape HeyReach would receive it.

    A preview rather than a payload: the campaign id is deliberately absent,
    because a file that could be posted as-is is a file somebody eventually
    posts.
    """
    leads = []
    for company in result["companies"]:
        for card in company["cards"]:
            steps = [s for s in card["timeline"]
                     if s.get("channel") == "linkedin"
                     and s.get("status") != "not_planned"]
            if not steps:
                continue
            leads.append({
                "record_id": card["record_id"],
                "contact_key": card["contact_key"],
                "profileUrl": card.get("linkedin"),
                "firstName": (card.get("name") or "").partition(" ")[0],
                "lastName": (card.get("name") or "").partition(" ")[2],
                "companyName": card.get("company"),
                "position": card.get("title"),
                "eligible": card["linkedin_eligible"],
                "excluded_reason": card["linkedin_excluded_reason"],
                "steps": [{"step": s["step"], "day": s["day"],
                           "status": s["status"], "note": s.get("note"),
                           "lint": s.get("lint") or []}
                          for s in steps],
            })
    return {
        "preview": True,
        "campaign_id": None,
        "why_no_campaign_id": "a preview must not be postable as it stands",
        "would_send": 0,
        "leads": leads,
    }


FILES = ("preview.html", "preview.json", "emailbison-preview.csv",
         "heyreach-preview.json", "report-preview.html")


def write_all(result, out_dir=None, reveal=False, max_cards=MAX_CARDS):
    """All five, into out/. Returns the paths written."""
    out_dir = out_dir or store.out_dir()
    os.makedirs(out_dir, exist_ok=True)
    paths = {}

    path = os.path.join(out_dir, "preview.html")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page(result, reveal, max_cards))
    paths["preview.html"] = path

    paths["preview.json"] = export.write_json(
        os.path.join(out_dir, "preview.json"), result)

    paths["emailbison-preview.csv"] = export.write_csv(
        os.path.join(out_dir, "emailbison-preview.csv"), EMAILBISON_HEADER,
        emailbison_rows(result, reveal))

    paths["heyreach-preview.json"] = export.write_json(
        os.path.join(out_dir, "heyreach-preview.json"),
        heyreach_payload(result, reveal))

    path = os.path.join(out_dir, "report-preview.html")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report_page(result))
    paths["report-preview.html"] = path
    return paths


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client")
    p.add_argument("--batch")
    p.add_argument("--campaign")
    p.add_argument("--out")
    p.add_argument("--reveal-emails", action="store_true")
    p.add_argument("--max-cards", type=int, default=MAX_CARDS,
                   help="contact cards to render in the HTML; the JSON always "
                        "holds every one")
    a = p.parse_args(argv)

    from . import campaigns
    campaign = campaigns.get(a.campaign) if a.campaign else None
    if a.campaign and campaign is None:
        print(f"REFUSED: no such campaign: {a.campaign}")
        return 2
    result = simulator.simulate(client=a.client, batch=a.batch,
                                campaign=campaign)
    paths = write_all(result, a.out, a.reveal_emails, a.max_cards)
    for name in FILES:
        size = os.path.getsize(paths[name])
        print(f"  wrote {paths[name]} ({size:,} bytes)")
    print("Read-only. Nothing was sent, approved, launched or called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
