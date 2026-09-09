#!/usr/bin/env python3
"""The demo outreach page: one campaign, rendered for a person to judge.

This is the prototype of the Campaign Review screen. It is written for
somebody who has not read the code and is deciding whether they would send
this, so it is organised around the questions they actually ask - would I
target this company, is this the right person, would I send this email - and
not around the modules that answered them.

Three rules it is built to:

**Every number is clickable through to its reason.** A summary card that says
"1 blocked by MX" is a claim; the contact card underneath names the gateway,
the policy category and the exact reason code. A page that only shows totals
teaches people to trust totals.

**Nothing is silently omitted.** Steps that will not run are rendered in place,
struck through, with the reason beside them. A timeline that quietly drops its
blocked steps shows a campaign that is not the campaign.

**Untrusted text is escaped once, at the boundary.** Company names, evidence
facts and prospect names are attacker-controlled: they arrive from providers
and scrapes. `esc()` wraps every interpolation, and a test renders a card whose
name is a script tag and asserts it comes out inert.

Addresses are masked unless `--reveal-emails` is passed. They are fictional
here; the habit is the point.
"""
import html
import json
import os

MAX_EVIDENCE = 8


def esc(value):
    return html.escape(str(value if value is not None else ""))


def mask(address, reveal=False):
    """Recognisable to a reviewer without the page becoming a leak."""
    if not address:
        return ""
    if reveal:
        return str(address)
    name, _, domain = str(address).partition("@")
    if not domain:
        return "***"
    shown = name[:2] if len(name) > 3 else name[:1]
    return f"{shown}{'*' * max(3, len(name) - len(shown))}@{domain}"


# Status vocabulary, mapped to the five visual states section 11 asks for.
STATUS_KIND = {
    "eligible": "pass", "pushed": "pass", "pass": "pass",
    "unapproved": "review", "waiting": "review", "review": "review",
    "blocked": "blocked", "skipped": "blocked", "not_planned": "blocked",
    "block": "blocked",
    "paused": "paused",
    "failed": "failed", "held": "failed",
}

STATUS_WORDS = {
    "eligible": "will send",
    "pushed": "already sent",
    "unapproved": "needs approval",
    "waiting": "waiting on a connection",
    "blocked": "blocked",
    "skipped": "skipped",
    "paused": "paused",
    "not_planned": "not planned",
}


def _kind(status):
    return STATUS_KIND.get(str(status or "").lower(), "review")


def _tag(text, kind=""):
    return f'<span class="tag {kind}">{esc(text)}</span>'


def _stat(label, value, kind=""):
    return (f'<div class="stat {kind}"><div class="n">{esc(value)}</div>'
            f'<div class="k">{esc(label)}</div></div>')


def _row(label, value, kind=None):
    body = value if kind == "raw" else esc(value)
    return f"<tr><th>{esc(label)}</th><td>{body}</td></tr>"


def _country(value):
    """Countries are stored lower-cased for matching; display them properly."""
    return str(value or "").title() or None


def _unavailable(why):
    """An absence, said out loud. A blank cell reads as a broken page."""
    return f'<span class="absent">unavailable — {esc(why)}</span>'


def _section(title, body, open_=False):
    return (f'<details class="sec"{" open" if open_ else ""}>'
            f"<summary>{esc(title)}</summary><div class=\"secbody\">{body}"
            f"</div></details>")


# ------------------------------------------------------------------ blocks

def _why_company(card):
    icp, seg, facts = card["icp"], card["segment"], card["company_facts"]
    rows = [
        _row("Company", card["company"]),
        _row("Domain", card["domain"]),
        _row("Country", _country(seg.get("country"))
             or _unavailable("no country on the record"),
             None if seg.get("country") else "raw"),
        _row("Region", seg.get("region")),
        _row("Timezone", seg.get("timezone") or _unavailable(
            "the country spans several zones and nothing narrows it"), "raw"
            if not seg.get("timezone") else None),
        _row("Vertical", seg.get("vertical")),
        _row("Industry", facts.get("industry")),
        _row("Employees", f"{facts.get('employees')} ({seg.get('employee_band')})"),
        _row("ICP verdict", f'{_tag(icp["status"], _kind("pass" if icp["status"] == "qualified" else "review"))}'
             f' {_tag("tier " + str(icp["tier"]))} '
             f'{_tag("score " + str(icp["score"]))} '
             f'{_tag(str(icp["confidence"]) + " confidence")}', "raw"),
        _row("Scoring version", icp.get("scoring_version")),
    ]
    reasons = "".join(f"<li>{esc(r)}</li>" for r in icp["reasons"][:6])
    positives = "".join(
        f'<li><strong>{esc(s["dimension"])}</strong> +{esc(s["weight"])} — {esc(s["why"])}</li>'
        for s in icp["positive"][:6])
    negatives = "".join(
        f'<li><strong>{esc(s["dimension"])}</strong> {esc(s["weight"])} — {esc(s["why"])}</li>'
        for s in icp["negative"][:6])
    missing = "".join(f"<li>{esc(m)}</li>" for m in icp["missing"][:6])
    contradictions = "".join(
        f'<li>{esc(c.get("kind"))} — {esc(c.get("why"))}</li>'
        for c in icp["contradictions"])

    out = f'<table class="kv">{"".join(rows)}</table>'
    out += f"<h4>Why it qualified</h4><ul>{reasons}</ul>"
    if positives:
        out += f"<h4>Positive signals</h4><ul>{positives}</ul>"
    if negatives:
        out += f'<h4>Negative signals</h4><ul class="neg">{negatives}</ul>'
    if missing:
        out += (f"<h4>What we do not know</h4>"
                f'<p class="note">Missing evidence never counts as a positive '
                f"signal. It costs confidence.</p><ul>{missing}</ul>")
    if contradictions:
        out += (f"<h4>Contradictory evidence</h4>"
                f'<ul class="neg">{contradictions}</ul>')
    return out


def _why_person(card):
    why = card["why_person"]
    rows = [
        _row("Name", card["name"]),
        _row("Title", card["title"]),
        _row("Persona", why.get("persona")),
        _row("Angle", why.get("angle")),
        _row("Titles this persona matches",
             ", ".join(why.get("matched_titles") or []) or _unavailable(
                 "no title list configured for this persona"),
             "raw" if not why.get("matched_titles") else None),
    ]
    out = f'<table class="kv">{"".join(rows)}</table>'
    out += f'<p>{esc(why.get("why"))}</p>'
    if not why.get("person_research_available"):
        out += (f'<p class="note"><strong>No person-level research.</strong> '
                f'{esc(why.get("person_research_note"))}</p>')
    return out


def _contact_block(card, reveal):
    email, li = card["email"], card["linkedin"]
    mxd = email.get("mx") or {}

    verification = email.get("verification") or {}
    evidence_rows = "".join(
        f"<tr><td>{esc(e.get('provider'))}</td><td>{esc(e.get('status'))}</td>"
        f"<td>{esc(e.get('safe_to_send'))}</td><td>{esc(e.get('reason'))}</td>"
        f"<td>{esc(e.get('at'))}</td></tr>"
        for e in verification.get("evidence") or [])

    count = verification.get("confirmation_count", 0)
    required = verification.get("required_confirmations", 1)
    enough = count >= required
    email_rows = [
        _row("Address", mask(email.get("address"), reveal)
             if email.get("address") else _unavailable("no address was found"),
             "raw" if not email.get("address") else None),
        _row("Confirmations",
             f'{_tag(f"{count} / {required}", _kind("pass" if enough else "review"))}'
             + (_tag("DISAGREEMENT", "blocked")
                if verification.get("disagreement") else ""),
             "raw"),
        _row("Final verification",
             _tag("PASS" if enough and email.get("sendable") else
                  "BLOCKED" if verification.get("state") == "invalid" else "HELD",
                  _kind("pass" if enough and email.get("sendable")
                        else "blocked" if verification.get("state") == "invalid"
                        else "review")), "raw"),
        _row("Why", verification.get("reason")
             or _unavailable("no verification has been run"),
             None if verification.get("reason") else "raw"),
        _row("Verification state", verification.get("state")),
        _row("Sendable", _tag("yes" if email.get("sendable") else "no",
                              _kind("pass" if email.get("sendable") else "blocked")),
             "raw"),
        _row("MX provider", mxd.get("security_provider")
             or mxd.get("mailbox_provider")
             or _unavailable("no MX evidence identifies the operator"),
             "raw" if not (mxd.get("security_provider")
                           or mxd.get("mailbox_provider")) else None),
        _row("MX classification", mxd.get("category")
             or _unavailable("not classified"),
             "raw" if not mxd.get("category") else None),
        _row("MX hostnames", ", ".join(mxd.get("hosts") or []) or _unavailable(
            "no lookup recorded"),
            "raw" if not mxd.get("hosts") else None),
        _row("Email eligible",
             _tag("YES" if email["eligible"] else "NO",
                  _kind("pass" if email["eligible"] else "blocked")), "raw"),
        _row("Reason", email.get("reason") or "eligible"),
        _row("In plain words", email.get("reason_text")
             or "this address may be written to"),
    ]

    li_rows = [
        _row("Profile URL", f'<code>{esc(li.get("url"))}</code>' if li.get("url")
             else _unavailable("no profile was found for this person"), "raw"),
        _row("LinkedIn eligible",
             _tag("YES" if li["eligible"] else "NO",
                  _kind("pass" if li["eligible"] else "blocked")), "raw"),
        _row("Reason", li.get("reason") or "eligible"),
        _row("In plain words", li.get("reason_text")
             or "this profile may be approached"),
    ]

    out = f"<h4>Email</h4><table class=\"kv\">{''.join(email_rows)}</table>"

    # One row per verifier, including the ones that were never asked. An
    # absent provider is a fact worth showing: "not required" and "could not
    # answer" lead to different next actions, and a table that silently omits
    # the providers it skipped reads as though they all agreed.
    results = verification.get("results") or {}
    order = ("contactout", "deliverable", "reoon")
    verifier_rows = ""
    for provider in order:
        answer = results.get(provider)
        if answer:
            status = str(answer.get("verdict") or "unknown")
            kind = _kind("pass" if status == "valid"
                         else "blocked" if status in ("invalid", "disposable")
                         else "review")
            cell = _tag(status.upper(), kind)
            when = esc(answer.get("checked_at") or "")
            extra = answer.get("reason") or ""
            if answer.get("is_safe_to_send") is not None:
                extra = (f"safe_to_send={answer['is_safe_to_send']} · "
                         f"catch_all={answer.get('is_catch_all')} · {extra}")
        elif enough:
            cell = _tag("NOT REQUIRED", "")
            when, extra = "", "the pair was already complete"
        else:
            cell = _tag("NOT RUN", "review")
            when, extra = "", "this provider was never asked"
        verifier_rows += (f"<tr><td>{esc(provider)}</td><td>{cell}</td>"
                          f"<td>{when}</td><td>{esc(extra)}</td></tr>")
    out += ("<h5>Verifiers</h5><table class=\"grid\">"
            "<tr><th>provider</th><th>verdict</th><th>checked at</th>"
            f"<th>detail</th></tr>{verifier_rows}</table>")
    if verification.get("disagreement"):
        out += ('<p class="note"><strong>The verifiers disagree.</strong> '
                "Two independent providers reached different conclusions "
                "about this address, so nothing is sent on the optimistic "
                "one. The email channel closes and LinkedIn is untouched.</p>")
    elif not enough and email.get("address"):
        out += (f'<p class="note"><strong>Double verification incomplete.</strong> '
                f"{esc(count)} of {esc(required)} independent confirmations. "
                "The address is held rather than blocked: one more verifier "
                "call would settle it.</p>")
    if evidence_rows:
        out += ("<h5>Verification evidence</h5><table class=\"grid\">"
                "<tr><th>provider</th><th>status</th><th>safe to send</th>"
                f"<th>reason</th><th>at</th></tr>{evidence_rows}</table>")
    out += f"<h4>LinkedIn</h4><table class=\"kv\">{''.join(li_rows)}</table>"
    return out


def _evidence_block(card):
    def rows(items):
        if not items:
            return None
        out = ""
        for item in items[:MAX_EVIDENCE]:
            url = item.get("source_url")
            link = (f'<a href="{esc(url)}" rel="nofollow noopener">{esc(url)}</a>'
                    if url else _unavailable("no source URL"))
            out += (
                f'<div class="ev"><div class="fact">{esc(item.get("fact"))}</div>'
                f'<div class="prov">'
                f'{_tag(item.get("provider") or "unknown provider")}'
                f'{_tag(item.get("source_type") or "unknown source")}'
                f'{_tag((item.get("quality") or "unrated") + " quality")}'
                f'{_tag((item.get("freshness") or "undated") + " freshness")}'
                f"</div>"
                f'<div class="meta">published {esc(item.get("published_at") or "unknown")}'
                f' · retrieved {esc(item.get("retrieved_at") or "unknown")}'
                f' · relevance {esc(item.get("relevance"))}'
                f' · id <code>{esc(item.get("evidence_id"))}</code></div>'
                f'<div class="meta">{link}</div></div>')
        return out

    ev = card["evidence"]
    out = "<h4>Company evidence</h4>"
    out += rows(ev["company"]) or f"<p>{_unavailable('no company evidence was retained')}</p>"
    out += "<h4>Person evidence</h4>"
    out += (rows(ev["person"])
            or f'<p class="note">{esc(ev["person_note"])}</p>')
    seg = card["segment"]
    out += ("<h4>Campaign / segment context</h4>"
            f'<table class="kv">'
            f'{_row("Vertical", seg.get("vertical"))}'
            f'{_row("Employee band", seg.get("employee_band"))}'
            f'{_row("Region", seg.get("region"))}'
            f'{_row("Timezone", seg.get("timezone"))}'
            f'{_row("Business model", seg.get("business_model"))}'
            f'{_row("Delivery model", seg.get("delivery_model"))}'
            "</table>")
    return out


def _personalization_block(card):
    p = card["personalization"]
    comps = p.get("components") or {}
    bars = "".join(
        f'<div class="bar"><span>{esc(name.replace("_", " "))}</span>'
        f'<div class="track"><i style="width:{max(0, min(100, float(value) * 100)):.0f}%"></i></div>'
        f"<b>{esc(round(float(value), 2))}</b></div>"
        for name, value in comps.items() if isinstance(value, (int, float)))
    rows = [
        _row("Personalisation band",
             _tag(str(p.get("band")), _kind(
                 "pass" if p.get("band") == "high"
                 else "review" if p.get("band") == "medium" else "blocked")),
             "raw"),
        _row("Meets the campaign minimum",
             _tag("yes" if p.get("meets_minimum") else "no",
                  _kind("pass" if p.get("meets_minimum") else "blocked")), "raw"),
        _row("Evidence pieces considered", p.get("evidence_count")),
        _row("Selected angle", p.get("angle")),
        _row("Why this angle", p.get("angle_why")),
    ]
    out = f'<table class="kv">{"".join(rows)}</table>'
    out += f'<p>{esc(p.get("why"))}</p>'
    if bars:
        out += f'<div class="bars">{bars}</div>'
    for warning in p.get("warnings") or []:
        out += f'<p class="note">{esc(warning)}</p>'
    return out


def _step_html(step):
    kind = _kind(step.get("status"))
    word = STATUS_WORDS.get(step.get("status"), step.get("status"))
    header = (
        f'<div class="stephead">'
        f'<span class="day">DAY {esc(step.get("day"))}</span>'
        f'{_tag(step.get("provider"), "prov")}'
        f'{_tag(word, kind)}'
        f'<span class="stepkey">{esc(step.get("step"))}</span>'
        f"</div>")

    reasons = ""
    if not step.get("lint_ok"):
        reasons += (f'<div class="why blocked">Lint: '
                    f'{esc(", ".join(step.get("lint") or []))}</div>')
    if step.get("eligibility_reasons"):
        reasons += (f'<div class="why">Eligibility: '
                    f'{esc(", ".join(step["eligibility_reasons"]))}</div>')
    if step.get("blocked_by"):
        blocked = step["blocked_by"]
        blocked = ", ".join(blocked) if isinstance(blocked, list) else str(blocked)
        reasons += f'<div class="why blocked">Blocked by: {esc(blocked)}</div>'
    if step.get("requires"):
        reasons += (f'<div class="why">Requires: {esc(step["requires"])} — '
                    "no connection-accepted state is assumed, so this step "
                    "waits rather than firing</div>")

    body = ""
    if step.get("channel") == "email":
        if step.get("subject"):
            body += f'<div class="subj">Subject: {esc(step["subject"])}</div>'
        body += f'<pre class="copy">{esc(step.get("text"))}</pre>'
        body += (f'<div class="meta">{esc(step.get("words"))} words · '
                 f'angle {esc(step.get("angle"))} · '
                 f'{"generated" if step.get("generated") else "template " + esc(step.get("template") or "")}'
                 "</div>")
    else:
        if step.get("text"):
            body += f'<pre class="copy">{esc(step.get("text"))}</pre>'
            body += (f'<div class="meta">{esc(step.get("characters"))} characters · '
                     f'template {esc(step.get("template") or "none")}</div>')
        else:
            body += (f'<p>{_unavailable("this activity carries no text: it is a "
                                        "connection request or it has not been expanded")}</p>')

    return f'<div class="step {kind}">{header}{body}{reasons}</div>'


def _coherence_block(card):
    report = card["coherence"]
    verdict = report["verdict"]
    out = (f'<p>Cross-channel verdict: '
           f'{_tag(verdict.upper(), _kind(verdict))} over '
           f'{esc(report["steps_checked"])} steps.</p>')
    if not report["findings"]:
        out += ('<p class="note">The email and LinkedIn steps for this person '
                "read as one conversation: nothing repeats, nothing "
                "contradicts, and no step references the other channel.</p>")
        return out
    out += "<ul>"
    for finding in report["findings"]:
        out += (f'<li>{_tag(finding["severity"], _kind(finding["severity"]))} '
                f'<strong>{esc(finding["kind"])}</strong> — '
                f'{esc(finding["message"])}')
        if finding.get("detail"):
            out += f'<div class="meta">{esc(finding["detail"])}</div>'
        out += "</li>"
    out += "</ul>"
    return out


def _qa_block(card):
    out = _coherence_block(card)
    dupes = card.get("duplicates") or []
    out += "<h4>Duplicate email steps</h4>"
    if not dupes:
        out += ('<p class="note">No two email steps for this person say the '
                "same thing.</p>")
    else:
        out += "<ul>" + "".join(
            f'<li>{esc(d.get("steps"))} — {esc(d.get("why"))}</li>'
            for d in dupes) + "</ul>"
    out += "<h4>Lint, step by step</h4><table class=\"grid\">"
    out += "<tr><th>step</th><th>channel</th><th>result</th><th>detail</th></tr>"
    for step in card["timeline"]:
        ok = step["lint_ok"]
        out += (f'<tr><td>{esc(step["step"])}</td>'
                f'<td>{esc(step["channel"])}</td>'
                f'<td>{_tag("pass" if ok else "fail", _kind("pass" if ok else "blocked"))}</td>'
                f'<td>{esc(", ".join(step.get("lint") or []) or "—")}</td></tr>')
    out += "</table>"
    return out


def _payload_block(card, payloads, reveal):
    """The rows of the real payload that belong to this contact."""
    bison_body = payloads["emailbison"]["body"]
    bison_leads = (bison_body.get("leads") if isinstance(bison_body, dict)
                   else bison_body) or []
    mine = [lead for lead in bison_leads
            if str(lead.get("record_id") or "") == card["record_id"]
            or str(lead.get("email") or "").endswith("@" + str(card["domain"]))]

    pairs = payloads["heyreach"]["body"]["accountLeadPairs"]
    my_pairs = []
    for pair in pairs:
        fields = {f["name"]: f["value"]
                  for f in pair["lead"].get("customUserFields") or []}
        if (fields.get("record_id") == card["record_id"]
                or pair["lead"].get("profileUrl") == card["linkedin"].get("url")):
            my_pairs.append(pair)

    def redact(obj):
        text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
        if not reveal and card["email"].get("address"):
            text = text.replace(card["email"]["address"],
                                mask(card["email"]["address"]))
        return text

    bison = (f"<p>{esc(payloads['emailbison']['method'])} "
             f"<code>{esc(payloads['emailbison']['endpoint'])}</code></p>")
    if mine:
        bison += f'<pre class="json">{esc(redact(mine))}</pre>'
    else:
        bison += (f'<p class="note"><strong>This contact is not in the '
                  f"EmailBison payload.</strong> "
                  f'{esc(card["email"].get("reason_text") or "no email step is eligible")}</p>')

    heyreach = (f"<p>{esc(payloads['heyreach']['method'])} "
                f"<code>{esc(payloads['heyreach']['endpoint'])}</code></p>")
    if my_pairs:
        heyreach += f'<pre class="json">{esc(redact(my_pairs))}</pre>'
        heyreach += ('<p class="note">Identity travels in '
                     "<code>customUserFields</code>: <code>record_id</code> and "
                     "<code>contact_key</code> are ours, and the canonical "
                     "profile URL is what a reply is actually matched on. "
                     "There is no name or company matching anywhere in that "
                     "path.</p>")
    else:
        heyreach += (f'<p class="note"><strong>This contact is not in the '
                     f"HeyReach payload.</strong> "
                     f'{esc(card["linkedin"].get("reason_text") or "no LinkedIn step is eligible")}</p>')
    return bison, heyreach


def _events_block(card):
    if card["paused"]:
        out = (f'<p>{_tag("PAUSED", "paused")} '
               f'{esc(card.get("pause_reason") or "this company has replied")}</p>'
               '<p class="note">The pause is company-wide and covers both '
               "channels. Nothing is deleted: every step keeps its place in "
               "the timeline and its reason.</p>")
    else:
        out = f'<p>{_tag("active", "pass")} no reply has been recorded.</p>'
    rows = "".join(
        f'<tr><td>{esc(e.get("at"))}</td><td>{esc(e.get("type"))}</td>'
        f'<td>{esc(e.get("channel") or "")}</td>'
        f'<td>{esc(e.get("step") or e.get("operation") or "")}</td></tr>'
        for e in (card.get("events") or [])[-14:])
    if rows:
        out += ('<table class="grid"><tr><th>at</th><th>event</th>'
                f"<th>channel</th><th>step</th></tr>{rows}</table>")
    return out


def _card_html(card, payloads, reveal):
    mode_kind = {"multichannel": "pass", "email_only": "review",
                 "linkedin_only": "review", "none": "failed"}
    bison, heyreach = _payload_block(card, payloads, reveal)

    head = (
        f'<div class="cardhead">'
        f'<div><div class="scenario">{esc(card["scenario_title"])}</div>'
        f'<h3>{esc(card["name"])} <span class="muted">— {esc(card["title"])}'
        f"</span></h3>"
        f'<div class="muted">{esc(card["company"])} · '
        f'<code>{esc(card["domain"])}</code></div></div>'
        f'<div class="modes">'
        f'{_tag(str(card["mode"]).replace("_", " ").upper(), mode_kind.get(card["mode"], "review"))}'
        f'{_tag("email " + ("on" if card["email"]["eligible"] else "off"), _kind("pass" if card["email"]["eligible"] else "blocked"))}'
        f'{_tag("linkedin " + ("on" if card["linkedin"]["eligible"] else "off"), _kind("pass" if card["linkedin"]["eligible"] else "blocked"))}'
        f'{_tag("PAUSED", "paused") if card["paused"] else ""}'
        f"</div></div>"
        f'<p class="ask">{esc(card["scenario_ask"])}</p>')

    steps = "".join(_step_html(s) for s in card["timeline"])

    body = (
        _section("1 · Why this company", _why_company(card))
        + _section("2 · Why this person", _why_person(card))
        + _section("3 · Contact and verification", _contact_block(card, reveal))
        + _section("4 · Research and evidence", _evidence_block(card))
        + _section("5 · Personalisation strategy", _personalization_block(card))
        + _section("6 · Full outreach, every step in order",
                   f'<div class="steps">{steps}</div>', open_=True)
        + _section("7 · QA, lint and cross-channel coherence", _qa_block(card))
        + _section("8 · EmailBison payload", bison)
        + _section("9 · HeyReach payload", heyreach)
        + _section("10 · Events and pause state", _events_block(card))
    )
    return f'<article class="card" id="{esc(card["contact_key"])}">{head}{body}</article>'


def _reply_block(result):
    reply = result["reply"]

    def table(rows, title):
        out = f"<h4>{esc(title)}</h4><table class=\"grid\">"
        out += "<tr><th>step</th><th>day</th><th>channel</th><th>status</th></tr>"
        for row in rows:
            out += (f'<tr><td>{esc(row["step"])}</td><td>{esc(row["day"])}</td>'
                    f'<td>{esc(row["channel"])}</td>'
                    f'<td>{_tag(STATUS_WORDS.get(row["status"], row["status"]), _kind(row["status"]))}</td></tr>')
        return out + "</table>"

    return (
        f'<p>A positive reply on day {esc(reply["reply_day"])} from '
        f'<code>{esc(reply["contact_key"])}</code>. The reply is a local event '
        "applied through the production pause path. No provider was "
        "contacted.</p>"
        f'<div class="two">{table(reply["before"], "Before the reply")}'
        f'{table(reply["after"], "After the reply")}</div>'
        '<p class="note"><strong>Both channels stop together.</strong> The '
        "pause is company-wide, not per contact and not per channel, and the "
        "steps that had already gone out keep their status. Nothing is "
        "deleted.</p>")


def _overview(result, reveal):
    t = result["totals"]
    cards = [
        _stat("companies", t["companies"]),
        _stat("contacts", t["contacts"]),
        _stat("multichannel", t["multichannel"], "pass"),
        _stat("email only", t["email_only"]),
        _stat("linkedin only", t["linkedin_only"]),
        _stat("held", t["held"], "failed" if t["held"] else ""),
        _stat("blocked by MX", t["mx_blocked"], "blocked" if t["mx_blocked"] else ""),
        _stat("paused", t["paused"], "paused" if t["paused"] else ""),
        _stat("cadence steps", t["steps"]),
        _stat("lint failures", t["lint_failures"],
              "blocked" if t["lint_failures"] else "pass"),
        _stat("coherence pass", t["coherence_pass"], "pass"),
        _stat("coherence blocked", t["coherence_failed"],
              "blocked" if t["coherence_failed"] else ""),
    ]
    qa = result["qa"]
    push = result["push"]
    approval = result.get("approval") or {}
    meta = (
        f'<table class="kv">'
        f'{_row("Campaign", result["campaign"]["name"])}'
        f'{_row("Client", result["campaign"]["client"])}'
        f'{_row("Campaign status", result["campaign"].get("status"))}'
        f'{_row("Approval", _tag(str(approval.get("status")), _kind("pass" if approval.get("status") == "approved" else "review")), "raw")}'
        f'{_row("Approval fingerprint", approval.get("fingerprint"))}'
        f'{_row("QA verdict", _tag(str(qa.get("verdict")), _kind(str(qa.get("verdict")).lower())), "raw")}'
        f'{_row("EmailBison rows", push["payloads"]["emailbison"]["count"])}'
        f'{_row("HeyReach lead pairs", push["payloads"]["heyreach"]["count"])}'
        f'{_row("Would send now", _tag(str(result["would_send"]), "pass"), "raw")}'
        f'{_row("Generated", result["generated_at"])}'
        "</table>")
    return f'<div class="stats">{"".join(cards)}</div>{meta}'


def _segment_table(result):
    rows = "".join(
        f'<tr><td>{esc(s["company"])}</td><td>{esc(s["vertical"])}</td>'
        f'<td>{esc(s["employee_band"])}</td><td>{esc(_country(s["country"]))}</td>'
        f'<td>{esc(s["region"])}</td>'
        f'<td>{esc(s["timezone"]) or _unavailable("spans zones")}</td>'
        f'<td>{_tag("yes" if s["schedulable"] else "no", _kind("pass" if s["schedulable"] else "blocked"))}</td>'
        "</tr>" for s in result["segments"])
    return ('<table class="grid"><tr><th>company</th><th>vertical</th>'
            "<th>band</th><th>country</th><th>region</th><th>timezone</th>"
            f"<th>schedulable</th></tr>{rows}</table>")


def _schedule_table(result):
    sched = result.get("schedule") or {}
    span = sched.get("first_step_utc_span")
    rows = ""
    for row in (sched.get("rows") or []):
        first = next((s for s in row["steps"] if s.get("utc_at")), None)
        rows += (f'<tr><td>{esc(row["domain"])}</td>'
                 f'<td>{esc(row["timezone"])}</td>'
                 f'<td>{esc((first or {}).get("local_at"))}</td>'
                 f'<td>{esc((first or {}).get("utc_at"))}</td></tr>')
    for row in (sched.get("held_rows") or []):
        rows += (f'<tr><td>{esc(row["domain"])}</td><td>{_unavailable(row["why"])}</td>'
                 f"<td>—</td><td>—</td></tr>")
    out = ""
    if span and span["hours"]:
        out += (f'<p>Day 1 of this campaign spans <strong>{esc(span["hours"])} '
                f"hours</strong> of UTC, because every send is placed in the "
                f"prospect's own working morning.</p>")
    elif span:
        out += ("<p>Every prospect here is in one UTC offset — this client "
                "sells to the UK and Ireland — so day 1 fires at a single "
                "instant. The times below are still computed through each "
                "company's own IANA zone rather than assumed, which is what "
                "makes them move correctly across a daylight-saving "
                "change.</p>")
    return out + ('<table class="grid"><tr><th>domain</th><th>timezone</th>'
                  "<th>day 1 local</th><th>day 1 UTC</th></tr>"
                  f"{rows}</table>")


CSS = """
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:#16202b;background:#eef1f5}
.wrap{max-width:1120px;margin:0 auto;padding:28px 20px 80px}
header.top{background:#0f1b2b;color:#fff;padding:30px 20px}
header.top .wrap{padding:0 0 4px}
header.top h1{margin:0 0 6px;font-size:25px;letter-spacing:-.2px}
header.top p{margin:0;color:#9fb3c8;font-size:14px;max-width:70ch}
.banner{background:#fff4d6;border:1px solid #e2c268;border-radius:8px;padding:12px 14px;margin:22px 0;font-size:14px}
.banner strong{color:#7a5a00}
h2{font-size:18px;margin:34px 0 12px;letter-spacing:-.2px}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(126px,1fr));gap:10px;margin:14px 0}
.stat{background:#fff;border:1px solid #d9e0e8;border-radius:8px;padding:12px}
.stat .n{font-size:23px;font-weight:650}
.stat .k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#5d7086;margin-top:3px}
.stat.pass{border-color:#7fc09a;background:#f2fbf6}
.stat.blocked{border-color:#e0a0a0;background:#fdf4f4}
.stat.paused{border-color:#c8b4e8;background:#f8f5fd}
.stat.failed{border-color:#d98080;background:#fdf1f1}
table.kv{width:100%;border-collapse:collapse;margin:8px 0 14px}
table.kv th{text-align:left;width:210px;padding:6px 10px 6px 0;color:#5d7086;font-weight:500;
vertical-align:top;font-size:13px}
table.kv td{padding:6px 0;vertical-align:top}
table.grid{width:100%;border-collapse:collapse;margin:8px 0 16px;font-size:13px}
table.grid th{text-align:left;background:#e6ebf1;padding:7px 9px;font-weight:600;font-size:12px}
table.grid td{padding:7px 9px;border-top:1px solid #e2e8ef;vertical-align:top}
.tag{display:inline-block;padding:2px 8px;border-radius:11px;font-size:11.5px;font-weight:600;
background:#e6ebf1;color:#3c4b5c;margin:0 4px 3px 0;white-space:nowrap}
.tag.pass{background:#d8f0e2;color:#1b6640}.tag.blocked{background:#f8dcdc;color:#8d2020}
.tag.review{background:#fdeccd;color:#7a5300}.tag.paused{background:#e7ddf8;color:#4b2d85}
.tag.failed{background:#f8dcdc;color:#8d2020}.tag.prov{background:#dde6f5;color:#25457e}
.card{background:#fff;border:1px solid #d9e0e8;border-radius:10px;padding:20px;margin:16px 0}
.cardhead{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-start}
.cardhead h3{margin:3px 0;font-size:19px}
.scenario{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#25457e;font-weight:700}
.muted{color:#5d7086;font-weight:400;font-size:14px}
.ask{background:#f2f5f9;border-left:3px solid #25457e;padding:9px 12px;margin:12px 0 4px;font-size:14px}
details.sec{border-top:1px solid #e2e8ef;margin-top:10px}
details.sec>summary{cursor:pointer;padding:10px 0;font-weight:600;font-size:14.5px;list-style:none}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary:before{content:"▸";display:inline-block;width:16px;color:#7a8ea3}
details.sec[open]>summary:before{content:"▾"}
.secbody{padding:2px 0 16px 16px}
h4{margin:16px 0 6px;font-size:14px;color:#25457e}
h5{margin:12px 0 4px;font-size:12.5px;color:#5d7086;text-transform:uppercase;letter-spacing:.04em}
.note{background:#f2f5f9;border-radius:6px;padding:9px 11px;font-size:13.5px;color:#3c4b5c;margin:8px 0}
.absent{color:#8a97a6;font-style:italic}
ul{margin:6px 0;padding-left:20px}li{margin:3px 0}
ul.neg li strong{color:#8d2020}
.steps{margin-top:6px}
.step{border:1px solid #dde3ea;border-left:4px solid #b9c4d0;border-radius:8px;padding:12px 14px;margin:9px 0;background:#fbfcfd}
.step.pass{border-left-color:#3d9c6d;background:#f7fdfa}
.step.blocked{border-left-color:#c05a5a;background:#fdf7f7}
.step.review{border-left-color:#d59b2a;background:#fffcf5}
.step.paused{border-left-color:#7d5bbe;background:#faf8fe}
.step.failed{border-left-color:#c05a5a;background:#fdf7f7}
.stephead{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:7px}
.day{font-weight:700;font-size:12px;letter-spacing:.06em;color:#25457e}
.stepkey{color:#8a97a6;font-size:11.5px;margin-left:auto}
.subj{font-weight:600;margin:6px 0 4px;font-size:14px}
pre.copy{white-space:pre-wrap;word-wrap:break-word;background:#fff;border:1px solid #e2e8ef;
border-radius:6px;padding:11px 13px;margin:6px 0;font:14px/1.6 inherit}
pre.json{white-space:pre-wrap;word-wrap:break-word;background:#0f1b2b;color:#cfe0f2;border-radius:8px;
padding:13px;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-x:auto}
.step.blocked pre.copy,.step.paused pre.copy{opacity:.62}
.meta{font-size:12px;color:#5d7086;margin-top:5px}
.why{font-size:13px;margin-top:6px;color:#5d7086}
.why.blocked{color:#8d2020;font-weight:500}
.ev{border:1px solid #e2e8ef;border-radius:7px;padding:10px 12px;margin:7px 0;background:#fbfcfd}
.ev .fact{font-size:14px;margin-bottom:5px}
.bars{margin:10px 0}
.bar{display:flex;align-items:center;gap:9px;font-size:12.5px;margin:4px 0}
.bar span{width:150px;color:#5d7086}
.bar .track{flex:1;height:7px;background:#e6ebf1;border-radius:4px;overflow:hidden}
.bar .track i{display:block;height:100%;background:#3d78c4}
.bar b{width:38px;text-align:right;font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
code{background:#eef1f5;padding:1px 5px;border-radius:4px;font:12.5px ui-monospace,Menlo,Consolas,monospace}
a{color:#25457e}
footer{margin-top:40px;padding-top:18px;border-top:1px solid #d9e0e8;color:#5d7086;font-size:13px}
@media(max-width:760px){.two{grid-template-columns:1fr}table.kv th{width:auto;display:block;padding-bottom:0}
table.kv td{display:block;padding-top:2px}}
"""


def page(result, reveal=False):
    """The whole page, as one self-contained string."""
    payloads = result["push"]["payloads"]
    cards = "".join(_card_html(card, payloads, reveal)
                    for card in result["cards"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demo outreach — campaign review</title>
<style>{CSS}</style></head><body>
<header class="top"><div class="wrap">
<h1>Demo outreach — campaign review</h1>
<p>Five fictional companies taken through the real engine. Every verdict,
timeline, lint result and provider payload below was produced by the
production code path. Nothing was sent.</p>
</div></header>
<div class="wrap">

<div class="banner"><strong>Nothing on this page was sent.</strong>
Live sending is disabled in this build: <code>push.run(live=True)</code>
raises <code>LiveSendNotEnabled</code>. The payloads below are the exact
request bodies the sender would post, built and displayed, never submitted.
Every company, person, address and profile is fictional and every domain
is <code>.test</code>.</div>

<h2>Campaign overview</h2>
{_overview(result, reveal)}

<h2>Segments</h2>
{_segment_table(result)}

<h2>When each first step would fire</h2>
{_schedule_table(result)}

<h2>Reply and pause</h2>
{_reply_block(result)}

<h2>Contacts</h2>
<p>Each card is one scenario. Expand a section to see the evidence behind
any claim on it.</p>
{cards}

<footer>
Generated {esc(result["generated_at"])} by
<code>python -m src.demo_outreach</code>.
Would send now: <strong>{esc(result["would_send"])}</strong>.
No provider, model or network was contacted.
</footer>
</div></body></html>"""


def write(result, path, reveal=False):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page(result, reveal))
    return path
