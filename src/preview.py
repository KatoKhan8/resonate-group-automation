#!/usr/bin/env python3
"""The campaign preview: everything an operator needs to say yes or no.

## What this is for

Approving a campaign from a summary line is approving a number. The preview
exists so the person clicking approve can see the actual sentences that will
reach actual people, next to the evidence each one rests on, and answer in a
few seconds:

    why this company, why this person, why this angle, why now,
    what proves it, when did it happen, what exactly gets sent,
    what is written by a model and what is a template,
    is the address verified, is anything held, what does it cost,
    and is this still the campaign that was approved?

## It reads and nothing else

Opening this file cannot approve, launch, push, mutate or call a provider.
`build()` takes records that are already loaded and returns a string. There is
no network client imported here, no store write, and the generated page has no
form, no fetch and no link that changes anything - the only interactivity is
client-side filtering over rows already present.

That is not politeness. A preview that can act is a preview nobody can safely
open on a phone.

  python -m src.preview <campaign-id>
  python -m src.preview --demo
"""
import argparse
import html
import json
import os
import sys

from . import (approval, cadence, campaigns, claims, clients, evidence, lint,
               mx, personalization, store)

TITLE = "Campaign preview"


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _mask(address, reveal=False):
    """An address, shown only as far as the preview policy allows."""
    if not address:
        return ""
    if reveal:
        return address
    name, _, domain = str(address).partition("@")
    keep = name[:2] if len(name) > 2 else name[:1]
    return f"{keep}***@{domain}" if domain else f"{keep}***"


# ------------------------------------------------------------ the gathering

def gather(campaign, recs, config=None):
    """Everything the page shows, computed once. Calls no provider."""
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}

    ids = set(campaign.get("record_ids") or [])
    mine = [r for r in recs if r.get("id") in ids]
    fingerprint = campaigns.fingerprint(campaign, recs, config)
    approved_at = (campaign.get("approval") or {}).get("fingerprint")

    companies, totals = [], {
        "domains": 0, "contacts_found": 0, "contacts_selected": 0,
        "sendable": 0, "held": 0, "dropped": 0, "suppressed": 0,
        "email_steps": 0, "linkedin_steps": 0, "lint_failures": 0,
        "unapproved": 0, "strong": 0, "medium": 0, "weak": 0, "none": 0,
        "company_signal": 0, "person_signal": 0,
        "apify_used": 0, "apify_skipped": 0, "aiark_used": 0,
        "generated": 0, "template": 0, "evidence_total": 0, "signal_ages": [],
        "mx_blocked": 0, "mx_linkedin_only": 0, "mx_unknown": 0,
        "mx_dns_failure": 0, "mx_no_mx": 0, "mx_by_provider": {},
    }

    # One pause scan for the whole page, not one per company.
    paused_set = cadence.paused_domains(recs)
    for rec in sorted(mine, key=lambda r: r.get("id") or ""):
        totals["domains"] += 1
        found = rec.get("contacts") or []
        selected = personalization.selected_contacts(rec, config)
        selected_keys = {c.get("key") for c in selected}
        totals["contacts_found"] += len(found) + len(rec.get("excluded") or [])
        totals["contacts_selected"] += len(selected)
        if rec.get("state") == "held":
            totals["held"] += 1
        if rec.get("state") == "dropped":
            totals["dropped"] += 1
        if (rec.get("drop_reason") or "").startswith("suppress"):
            totals["suppressed"] += 1

        providers_used = _provider_trail(rec)
        totals["apify_used"] += 1 if providers_used["apify"]["used"] else 0
        totals["apify_skipped"] += 0 if providers_used["apify"]["used"] else 1
        totals["aiark_used"] += 1 if providers_used["aiark"]["used"] else 0

        timeline = cadence.build(rec, config, recs=recs,
                                 paused_set=paused_set,
                                 campaign=campaign)
        people = []
        for contact in found:
            if contact.get("key") not in selected_keys:
                continue
            person = _person_card(rec, contact, timeline, config, totals)
            people.append(person)

        companies.append({
            "record": rec,
            "id": rec.get("id"),
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "lane": rec.get("lane"),
            "state": rec.get("state"),
            "paused": bool(rec.get("paused")),
            "facts": rec.get("company_facts") or {},
            "evidence": evidence.rank(personalization.stored(rec,
                                                             evidence.COMPANY)),
            "providers": providers_used,
            "people": people,
            "excluded": rec.get("excluded") or [],
        })

    mx_counts = mx.summarise(mine, config)
    totals["mx_blocked"] = mx_counts["blocked"]
    totals["mx_linkedin_only"] = mx_counts["linkedin_only"]
    totals["mx_unknown"] = mx_counts["unknown"]
    totals["mx_dns_failure"] = mx_counts["dns_failure"]
    totals["mx_no_mx"] = mx_counts["no_mx"]
    totals["mx_by_provider"] = mx_counts["by_provider"]

    coverage = 0
    if totals["contacts_selected"]:
        strong_ish = totals["strong"] + totals["medium"]
        coverage = round(100.0 * strong_ish / totals["contacts_selected"], 1)
    totals["coverage_percent"] = coverage
    ages = [a for a in totals.pop("signal_ages") if isinstance(a, int)]
    totals["average_signal_age_days"] = round(sum(ages) / len(ages), 1) if ages else None

    return {
        "campaign": campaign,
        "config": config,
        "companies": companies,
        "totals": totals,
        "estimate": campaigns.cost_estimate(campaign, recs, config),
        "fingerprint": fingerprint,
        "approved_fingerprint": approved_at,
        "stale": bool(approved_at) and approved_at != fingerprint,
        "validation": campaigns.validate(campaign.get("campaign_id"), recs,
                                         config, campaign=campaign),
    }


def _provider_trail(rec):
    """Which providers ran for this company, and why the others did not."""
    seen = {}
    for entry in rec.get("events") or []:
        provider = entry.get("provider")
        if not provider:
            continue
        seen.setdefault(provider, []).append(entry)

    def summarise(name, absent_reason):
        entries = seen.get(name) or []
        used = any(e.get("type") in ("provider_call_completed",
                                     "scrape_completed", "contact_found",
                                     "provider_call_started")
                   for e in entries)
        why = next((e.get("reason") for e in entries
                    if e.get("reason") and not used), None)
        return {"used": used,
                "why": why or ("used" if used else absent_reason),
                "calls": len(entries)}

    return {
        "contactout": summarise("contactout", "not needed: stored data sufficed"),
        "aiark": summarise("aiark", "not needed: ContactOut answered"),
        "apify": summarise("apify", "not needed: structured evidence sufficed"),
        "deliverable": summarise("deliverable", "not needed"),
        "reoon": summarise("reoon", "not needed"),
    }


def _person_card(rec, contact, timeline, config, totals):
    steps = (timeline.get("contacts") or {}).get(contact.get("key")) or {}
    decision = contact.get("personalization") or personalization.decide(
        rec, contact, config)
    quality = decision.get("quality") or "none"
    totals[quality if quality in ("strong", "medium", "weak") else "none"] += 1
    if decision.get("selected_evidence_ids"):
        totals["evidence_total"] += len(decision["selected_evidence_ids"])
    chosen = [e for e in (rec.get("research") or [])
              if e.get("evidence_id") in set(decision.get("selected_evidence_ids") or [])]
    if any(e.get("subject") == evidence.PERSON for e in chosen):
        totals["person_signal"] += 1
    elif chosen:
        totals["company_signal"] += 1
    for entry in chosen:
        if isinstance(entry.get("age_days"), int):
            totals["signal_ages"].append(entry["age_days"])

    sendable = lint.sendable(contact)
    if sendable:
        totals["sendable"] += 1

    rows = []
    for key in sorted(steps, key=lambda k: (steps[k].get("day", 0), k)):
        step = steps[key]
        failures = (lint.check(rec, contact.get("key"), step)
                    if step.get("channel") == "email" else [])
        approved = approval.is_approved(rec, contact.get("key"), key, step)
        unsupported = claims.verify(step, rec, contact, chosen)
        if step.get("channel") == "email":
            totals["email_steps"] += 1
        else:
            totals["linkedin_steps"] += 1
        if failures:
            totals["lint_failures"] += 1
        if not approved:
            totals["unapproved"] += 1
        if step.get("generated"):
            totals["generated"] += 1
        else:
            totals["template"] += 1
        rows.append({
            "key": key, "day": step.get("day"), "channel": step.get("channel"),
            "subject": step.get("subject"), "body": step.get("body"),
            "note": step.get("note"), "status": step.get("status"),
            "blocked_by": step.get("blocked_by") or [],
            "generated": bool(step.get("generated")),
            "template": step.get("template"),
            "lint": failures, "approved": approved,
            "unsupported": unsupported,
        })

    mx_decision = mx.stored_decision(contact)
    mx_allowed, mx_why = mx.allows_email(contact, config)
    return {
        "mx": mx_decision, "mx_allowed": mx_allowed, "mx_why": mx_why,
        "contact": contact, "key": contact.get("key"),
        "name": contact.get("name"), "title": contact.get("title"),
        "persona": contact.get("persona"), "angle": contact.get("angle"),
        "linkedin": contact.get("linkedin"), "email": contact.get("email"),
        "sendable": sendable,
        "verification": contact.get("verification") or {},
        "personalization": decision, "evidence": chosen, "steps": rows,
    }


# ------------------------------------------------------------------- render

STYLE = """
:root{--bg:#fbfbfa;--fg:#1a1a19;--mut:#6b6b66;--line:#e3e3df;--card:#fff;
--ok:#1f7a4d;--warn:#8a6100;--bad:#a32020;--acc:#2b4c7e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:22px;margin:0 0 2px} h2{font-size:17px;margin:28px 0 10px}
h3{font-size:15px;margin:0 0 4px}
.mut{color:var(--mut)} .small{font-size:13px} .tiny{font-size:12px}
.banner{padding:12px 14px;border-radius:8px;margin:14px 0;font-weight:600}
.banner.stale{background:#fff3cd;border:1px solid #e0c86b;color:#6b4e00}
.banner.ok{background:#e8f5ee;border:1px solid #b6ddc6;color:#1f5b3d}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));
gap:10px;margin:14px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:10px 12px}
.stat b{display:block;font-size:19px} .stat span{font-size:12px;color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px;margin:14px 0}
.person{border-left:3px solid var(--acc);padding-left:14px;margin:16px 0}
.step{border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0;
background:#fdfdfc}
.step pre{white-space:pre-wrap;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;
margin:6px 0 0;background:#f7f7f5;padding:10px;border-radius:6px;overflow-x:auto}
.tag{display:inline-block;font-size:11px;padding:2px 7px;border-radius:20px;
border:1px solid var(--line);margin:0 4px 4px 0;background:#f4f4f2}
.tag.ok{background:#e8f5ee;border-color:#b6ddc6;color:var(--ok)}
.tag.bad{background:#fdecec;border-color:#f0c2c2;color:var(--bad)}
.tag.warn{background:#fff6e0;border-color:#e8d49a;color:var(--warn)}
.why{background:#f4f7fb;border:1px solid #d6e2f2;border-radius:8px;padding:10px;
margin:8px 0;font-size:13px}
.why b{color:var(--acc)}
table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;
vertical-align:top}
a{color:var(--acc)}
.filters{position:sticky;top:0;background:var(--bg);padding:10px 0;
border-bottom:1px solid var(--line);z-index:5;margin-bottom:8px}
.filters button{font:13px inherit;padding:5px 11px;margin:0 5px 5px 0;
border:1px solid var(--line);background:#fff;border-radius:20px;cursor:pointer}
.filters button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.hide{display:none !important}
"""

SCRIPT = """
(function(){
  var active=null;
  function apply(){
    document.querySelectorAll('[data-flags]').forEach(function(el){
      el.classList.toggle('hide', !!active && el.dataset.flags.indexOf(active)<0);
    });
    document.querySelectorAll('.company').forEach(function(c){
      var any=c.querySelector('.person:not(.hide)');
      c.classList.toggle('hide', !!active && !any);
    });
  }
  document.querySelectorAll('.filters button').forEach(function(b){
    b.addEventListener('click',function(){
      active = (active===b.dataset.filter) ? null : b.dataset.filter;
      document.querySelectorAll('.filters button').forEach(function(x){
        x.classList.toggle('on', x.dataset.filter===active);});
      apply();
    });
  });
})();
"""

FILTERS = (("failed", "Lint failed"), ("held", "Held / unsendable"),
           ("pending", "Pending approval"), ("strong", "Strong signal"),
           ("weak", "Weak / no signal"), ("champion", "Champions"),
           ("buyer", "Economic buyers"), ("email", "Has email step"),
           ("linkedin", "Has LinkedIn step"),
           ("mxblocked", "MX blocked"))


def _flags(person):
    flags = []
    if any(s["lint"] for s in person["steps"]):
        flags.append("failed")
    if not person["sendable"]:
        flags.append("held")
    if any(not s["approved"] for s in person["steps"]):
        flags.append("pending")
    quality = (person["personalization"].get("quality") or "none")
    flags.append("strong" if quality == "strong" else
                 "weak" if quality in ("weak", "none") else "medium")
    persona = (person.get("persona") or "").lower()
    flags.append("buyer" if "buyer" in persona else "champion")
    if any(s["channel"] == "email" for s in person["steps"]):
        flags.append("email")
    if any(s["channel"] == "linkedin" for s in person["steps"]):
        flags.append("linkedin")
    if person.get("mx") and not person.get("mx_allowed"):
        flags.append("mxblocked")
    return " ".join(flags)


def build(campaign, recs, config=None, reveal_emails=False):
    """The whole page as a string. Reads; changes nothing."""
    data = gather(campaign, recs, config)
    t, c = data["totals"], data["campaign"]
    out = [f"<!doctype html><html><head><meta charset='utf-8'>",
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>{esc(TITLE)}: {esc(c.get('name'))}</title>",
           f"<style>{STYLE}</style></head><body><div class='wrap'>"]

    out.append(f"<h1>{esc(c.get('name') or c.get('campaign_id'))}</h1>")
    out.append(f"<div class='mut small'>{esc(c.get('client'))} &middot; "
               f"{esc(c.get('campaign_id'))} &middot; status "
               f"<b>{esc(c.get('status'))}</b></div>")

    if data["stale"]:
        out.append("<div class='banner stale'>CAMPAIGN CHANGED SINCE APPROVAL "
                   "&mdash; RE-APPROVAL REQUIRED<div class='small' "
                   "style='font-weight:400'>approved against "
                   f"{esc(data['approved_fingerprint'])}, now "
                   f"{esc(data['fingerprint'])}</div></div>")
    elif data["approved_fingerprint"]:
        out.append("<div class='banner ok'>Approved, and unchanged since "
                   f"<span class='small'>({esc(data['fingerprint'])})</span></div>")
    else:
        out.append("<div class='banner stale'>Not yet approved "
                   f"<span class='small'>(fingerprint {esc(data['fingerprint'])})"
                   "</span></div>")

    out.append("<div class='grid'>")
    for label, value in (("Domains", t["domains"]),
                         ("Contacts found", t["contacts_found"]),
                         ("Selected", t["contacts_selected"]),
                         ("Sendable", t["sendable"]),
                         ("Held", t["held"]), ("Dropped", t["dropped"]),
                         ("Suppressed", t["suppressed"]),
                         ("Email steps", t["email_steps"]),
                         ("LinkedIn steps", t["linkedin_steps"]),
                         ("Lint failures", t["lint_failures"]),
                         ("Pending approval", t["unapproved"]),
                         ("Coverage %", t["coverage_percent"])):
        out.append(f"<div class='stat'><b>{esc(value)}</b><span>{esc(label)}</span></div>")
    out.append("</div>")

    out.append("<h2>Personalisation</h2><div class='grid'>")
    for label, value in (("Strong", t["strong"]), ("Medium", t["medium"]),
                         ("Weak", t["weak"]), ("No signal", t["none"]),
                         ("Company signal", t["company_signal"]),
                         ("Person signal", t["person_signal"]),
                         ("Evidence used", t["evidence_total"]),
                         ("Avg age (days)",
                          t["average_signal_age_days"]
                          if t["average_signal_age_days"] is not None else "n/a"),
                         ("Generated", t["generated"]),
                         ("Template", t["template"]),
                         ("Apify used", t["apify_used"]),
                         ("Apify skipped", t["apify_skipped"])):
        out.append(f"<div class='stat'><b>{esc(value)}</b><span>{esc(label)}</span></div>")
    out.append("</div>")

    out.append("<h2>Email security (MX)</h2><div class='grid'>")
    for label, value in (("MX blocked", t["mx_blocked"]),
                         ("LinkedIn-only", t["mx_linkedin_only"]),
                         ("Unknown gateway", t["mx_unknown"]),
                         ("DNS failure", t["mx_dns_failure"]),
                         ("No MX", t["mx_no_mx"])):
        out.append(f"<div class='stat'><b>{esc(value)}</b><span>{esc(label)}</span></div>")
    out.append("</div>")
    if t["mx_by_provider"]:
        out.append("<table><tr><th>Gateway</th><th>Contacts blocked</th></tr>")
        for name, count in sorted(t["mx_by_provider"].items()):
            label = (mx.ALL_KNOWN.get(name) or {}).get("name", name)
            out.append(f"<tr><td>{esc(label)}</td><td>{esc(count)}</td></tr>")
        out.append("</table>")

    out.append("<h2>Expected cost</h2><table><tr><th>Item</th><th>Value</th></tr>")
    for key, value in sorted(data["estimate"].items()):
        out.append(f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>")
    out.append("</table><p class='tiny mut'>Enrichment and verification are "
               "spent before approval; a figure this system cannot know is "
               "shown as unknown rather than guessed.</p>")

    out.append("<h2>Launch checklist</h2><table>")
    for row in data["validation"]["checks"]:
        mark = ("<span class='tag ok'>ok</span>" if row["ok"]
                else "<span class='tag bad'>blocked</span>")
        out.append(f"<tr><td>{mark}</td><td>{esc(row['check'])}</td>"
                   f"<td class='mut'>{esc(row['detail'])}</td></tr>")
    out.append("</table>")

    out.append("<div class='filters'>")
    for key, label in FILTERS:
        out.append(f"<button data-filter='{esc(key)}'>{esc(label)}</button>")
    out.append("</div>")

    for company in data["companies"]:
        out.extend(_company_html(company, reveal_emails))

    out.append(f"<p class='tiny mut'>Read-only preview. Nothing on this page "
               f"approves, launches, sends or calls a provider.</p>")
    out.append(f"</div><script>{SCRIPT}</script></body></html>")
    return "\n".join(out)


def _company_html(company, reveal):
    out = ["<div class='card company'>"]
    out.append(f"<h2 style='margin-top:0'>{esc(company['company'])} "
               f"<span class='mut small'>{esc(company['domain'])}</span></h2>")
    tags = [f"<span class='tag'>{esc(company['lane'])}</span>",
            f"<span class='tag'>{esc(company['state'])}</span>"]
    if company["paused"]:
        tags.append("<span class='tag bad'>company paused</span>")
    out.append("".join(tags))

    facts = company["facts"]
    if facts:
        out.append("<table>")
        for key in ("industry", "employees", "revenue", "founded", "offices",
                    "specialties", "stack", "email_domain"):
            if facts.get(key) not in (None, "", [], {}):
                out.append(f"<tr><td class='mut'>{esc(key)}</td>"
                           f"<td>{esc(facts[key])}</td></tr>")
        out.append("</table>")

    out.append("<h3 class='small mut' style='margin-top:12px'>Provider waterfall</h3>"
               "<table>")
    for name, info in company["providers"].items():
        mark = ("<span class='tag ok'>used</span>" if info["used"]
                else "<span class='tag'>skipped</span>")
        out.append(f"<tr><td>{esc(name)}</td><td>{mark}</td>"
                   f"<td class='mut tiny'>{esc(info['why'])}</td></tr>")
    out.append("</table>")

    if company["evidence"]:
        out.append("<h3 class='small mut' style='margin-top:12px'>Company evidence</h3>")
        for entry in company["evidence"][:6]:
            out.append(_evidence_html(entry))

    for person in company["people"]:
        out.extend(_person_html(person, reveal))
    out.append("</div>")
    return out


def _evidence_html(entry):
    bucket = entry.get("freshness_bucket") or "unknown"
    css = {"high": "ok", "medium": "", "low": "warn",
           "background": "warn", "unknown": "warn"}.get(bucket, "")
    link = (f" &middot; <a href='{esc(entry.get('source_url'))}' "
            f"rel='noreferrer noopener' target='_blank'>View source</a>"
            if entry.get("source_url") else "")
    return ("<div class='why'>"
            f"<div>{esc(entry.get('fact'))}</div>"
            f"<div class='tiny mut' style='margin-top:5px'>"
            f"<span class='tag {css}'>{esc(bucket)}</span>"
            f"<span class='tag'>{esc(entry.get('quality'))}</span>"
            f"<span class='tag'>relevance {esc(entry.get('relevance_score'))}</span>"
            f"{esc(entry.get('source_type'))} &middot; "
            f"{esc(entry.get('published_at') or 'date unknown')}{link}"
            f"</div></div>")


def _person_html(person, reveal):
    decision = person["personalization"]
    quality = decision.get("quality") or "none"
    css = {"strong": "ok", "medium": "", "weak": "warn",
           "none": "warn"}.get(quality, "")
    out = [f"<div class='person' data-flags='{esc(_flags(person))}'>"]
    out.append(f"<h3>{esc(person['name'])} "
               f"<span class='mut small'>{esc(person['title'])}</span></h3>")
    out.append(f"<span class='tag'>{esc(person['persona'])}</span>"
               f"<span class='tag'>angle: {esc(person['angle'])}</span>"
               f"<span class='tag {css}'>personalisation: {esc(quality)}</span>"
               + ("<span class='tag ok'>sendable</span>" if person["sendable"]
                  else "<span class='tag bad'>not sendable</span>"))
    out.append(f"<div class='tiny mut'>{esc(_mask(person['email'], reveal))}"
               + (f" &middot; <a href='{esc(person['linkedin'])}' target='_blank' "
                  f"rel='noreferrer noopener'>LinkedIn</a>"
                  if person.get("linkedin") else "") + "</div>")

    verification = person["verification"] or {}
    if verification:
        out.append("<table><tr><th>Verification</th><th></th></tr>")
        out.append(f"<tr><td class='mut'>state</td><td>{esc(verification.get('state'))}</td></tr>")
        for entry in (verification.get("evidence") or [])[:4]:
            out.append(f"<tr><td class='mut'>{esc(entry.get('provider'))}</td>"
                       f"<td>{esc(entry.get('status'))}</td></tr>")
        out.append("</table>")

    decision_mx = person.get("mx") or {}
    if decision_mx:
        allowed = person.get("mx_allowed")
        css = "ok" if allowed else "bad"
        out.append("<div class='why'><b>Email security</b><table>")
        for label, value in (
                ("Email domain", decision_mx.get("email_domain")),
                ("MX provider", decision_mx.get("security_provider_name")
                 or "not recognised"),
                ("MX records", ", ".join(decision_mx.get("mx_records") or [])
                 or "none"),
                ("MX status", decision_mx.get("status")),
                ("Checked", decision_mx.get("checked_at") or "not checked")):
            out.append(f"<tr><td class='mut' style='width:110px'>{esc(label)}</td>"
                       f"<td>{esc(value)}</td></tr>")
        out.append(f"<tr><td class='mut'>EMAIL</td><td>"
                   f"<span class='tag {css}'>"
                   f"{'ALLOWED' if allowed else 'BLOCKED'}</span></td></tr>")
        out.append(f"<tr><td class='mut'>LINKEDIN</td><td>"
                   + ("<span class='tag ok'>ELIGIBLE</span>"
                      if person.get("linkedin")
                      else "<span class='tag'>no profile</span>")
                   + "</td></tr>")
        out.append(f"<tr><td class='mut'>Reason</td>"
                   f"<td>{esc(person.get('mx_why'))}</td></tr>")
        out.append("</table></div>")

    out.append("<div class='why'><b>Why this message?</b><table>")
    for label, value in (("Persona", decision.get("persona")),
                         ("Angle", decision.get("angle")),
                         ("Signal", decision.get("primary_signal") or "none"),
                         ("Source", decision.get("source") or "n/a"),
                         ("Published", decision.get("published_at") or "unknown"),
                         ("Freshness", decision.get("freshness")),
                         ("Reason", decision.get("reason"))):
        out.append(f"<tr><td class='mut' style='width:110px'>{esc(label)}</td>"
                   f"<td>{esc(value)}</td></tr>")
    out.append("</table></div>")

    for entry in person["evidence"]:
        out.append(_evidence_html(entry))

    for step in person["steps"]:
        out.append(_step_html(step))
    out.append("</div>")
    return out


def _step_html(step):
    tags = [f"<span class='tag'>day {esc(step['day'])}</span>",
            f"<span class='tag'>{esc(step['channel'])}</span>",
            f"<span class='tag'>{'LLM' if step['generated'] else 'template'}</span>",
            (f"<span class='tag ok'>lint pass</span>" if not step["lint"]
             else f"<span class='tag bad'>lint: {esc(', '.join(step['lint']))}</span>"),
            (f"<span class='tag ok'>approved</span>" if step["approved"]
             else "<span class='tag warn'>pending approval</span>"),
            f"<span class='tag'>{esc(step['status'])}</span>"]
    if step["unsupported"]:
        tags.append("<span class='tag bad'>unsupported claim</span>")
    body = step.get("body") or step.get("note") or ""
    subject = f"<div class='small'><b>{esc(step['subject'])}</b></div>" \
        if step.get("subject") else ""
    return ("<div class='step'>" + "".join(tags) + subject +
            f"<pre>{esc(body)}</pre></div>")


# --------------------------------------------------------------------- CLI

def write(campaign, recs, config=None, path=None, reveal_emails=False):
    path = path or os.path.join(store.out_dir(), "campaign-preview.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build(campaign, recs, config, reveal_emails))
    return path


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.preview")
    p.add_argument("campaign_id", nargs="?")
    p.add_argument("--out")
    p.add_argument("--reveal-emails", action="store_true",
                   help="show addresses in full. Off by default")
    p.add_argument("--demo", action="store_true",
                   help="build the fictional demo campaign instead")
    p.add_argument("--client",
                   help="preview a whole batch rather than one campaign; "
                        "writes the five pre-production files")
    p.add_argument("--batch", help="narrow the client preview to one batch")
    p.add_argument("--max-cards", type=int,
                   help="contact cards to render; the JSON always holds all")
    a = p.parse_args(argv)

    # A client (with or without a batch) means the pre-production preview:
    # five files rather than one page, because a batch is inspected before a
    # campaign exists to hang it on.
    if a.client or a.batch:
        from . import previewpage, simulator
        result = simulator.simulate(client=a.client, batch=a.batch)
        paths = previewpage.write_all(
            result, a.out, a.reveal_emails,
            a.max_cards or previewpage.MAX_CARDS)
        for name in previewpage.FILES:
            print(f"  wrote {paths[name]}")
        headline = result["headline"]
        print(f"  {headline['companies']} companies · "
              f"{headline['contacts']} contacts · "
              f"{headline['email_eligible']} emailable · "
              f"{headline['linkedin_eligible']} on LinkedIn · "
              f"{headline['held']} held")
        print(f"  would send: {result['would_send']}")
        print("Read-only. Nothing was sent, approved, launched or called.")
        return 0

    if a.demo:
        from . import demo
        campaign, recs, config = demo.build()
        path = write(campaign, recs, config,
                     a.out or os.path.join(store.out_dir(),
                                           "demo-campaign-preview.html"),
                     a.reveal_emails)
        print(f"wrote {path}")
        print("Fictional data only. Nothing was called and nothing can be sent.")
        return 0

    if not a.campaign_id:
        p.error("a campaign id is required unless --demo is given")
    try:
        campaign = campaigns.require(a.campaign_id)
    except campaigns.NotFound as e:
        print(f"REFUSED: {e}")
        return 2
    path = write(campaign, store.load(), None, a.out, a.reveal_emails)
    print(f"wrote {path}")
    print("Read-only. Nothing was approved, launched, pushed or called.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
