"""The v2 copy engine preview. One HTML page per lead.

docs/COPY-ENGINE-SPEC-v2.md section 8 says what it must show:
qualification status, verified facts with sources, the hypothesis visibly
marked as a hypothesis and styled differently from a fact, the capability
and why, five emails with thread and subject, four LinkedIn messages, each
message's objective from the plan, the gate's results, and any warning.

A hypothesis is NEVER displayed as a company fact. Different styling,
labelled in words.
"""
import html
import os


def _esc(text):
    return html.escape(str(text or ""))


def _gate_badge(gate):
    if not gate:
        return ""
    if gate.get("passed"):
        n = len(gate.get("warnings") or [])
        return ('<span class="gate pass">GATE PASSED'
                + (" (%d warnings)" % n if n else "") + '</span>')
    return '<span class="gate fail">GATE FAILED</span>'


def _gate_lines(gate):
    if not gate:
        return ""
    out = []
    for f in gate.get("failures") or []:
        out.append('<div class="failure">FAIL <b>%s</b> [%s]: %s</div>'
                   % (_esc(f.get("check")), _esc(f.get("step")),
                      _esc(f.get("why"))))
    for w in gate.get("warnings") or []:
        out.append('<div class="warning">warn <b>%s</b> [%s]: %s</div>'
                   % (_esc(w.get("check")), _esc(w.get("step")),
                      _esc(w.get("why"))))
    return "\n".join(out)


def _qualification_badge(qual):
    colors = {
        "QUALIFIED_RICH": "#2d6a4f",
        "QUALIFIED_THIN": "#e09f3e",
        "INSUFFICIENT": "#9e2a2b",
        "UNQUALIFIED": "#333",
    }
    color = colors.get(qual, "#666")
    return ('<span class="qualification" style="background:%s">%s</span>'
            % (color, _esc(qual)))


def _plan_objective(plan, step_key):
    """The objective for a step from the plan, or empty."""
    if not plan:
        return ""
    emails = (plan.get("emails") or {}).get(step_key) or {}
    linkedin = (plan.get("linkedin") or {}).get(step_key) or {}
    obj = emails.get("objective") or linkedin.get("objective") or ""
    return obj


def render_lead(result, lead=None):
    """One lead's section of the preview page."""
    lead = lead or {}
    company = _esc(lead.get("company", ""))
    qual = result.get("qualification", "")
    facts = result.get("facts") or []
    hypothesis = result.get("hypothesis", "")
    signal = result.get("signal_strength", "")
    cap_key = result.get("capability_key", "")
    cap_sentence = result.get("capability_sentence", "")
    why_cap = result.get("why_this_capability", "")
    copy = result.get("copy") or {}
    gate = result.get("gate")
    plan = result.get("plan") or {}
    output = result.get("output") or {}
    hold = result.get("hold")
    hold_reason = result.get("hold_reason", "")

    # Facts with sources.
    facts_html = []
    for i, f in enumerate(facts, 1):
        src = f.get("kind") or "site"
        facts_html.append(
            '<li><b>[%d]</b> <span class="source">%s</span> %s</li>'
            % (i, _esc(src), _esc(f.get("text", ""))))
    facts_list = "<ul>%s</ul>" % "\n".join(facts_html) if facts_html else "<p>No facts extracted.</p>"

    # Emails with threads.
    emails = copy.get("emails") or {}
    subjects = {
        "em1": copy.get("subject", ""),
        "em2": "(reply to em1)",
        "em3": copy.get("subject_alt", ""),
        "em4": "(reply to em3)",
        "em5": copy.get("subject_breakup", ""),
    }
    threads = {"em1": "A", "em2": "A", "em3": "B", "em4": "B", "em5": "C"}
    ps = copy.get("ps") or {}

    email_blocks = []
    for key in ("em1", "em2", "em3", "em4", "em5"):
        body = emails.get(key, "")
        subj = subjects.get(key, "")
        thread = threads.get(key, "")
        obj = _plan_objective(plan, key)
        is_new_thread = key in ("em1", "em3", "em5")
        thread_label = ('<span class="thread new">NEW THREAD %s</span>'
                        % thread if is_new_thread else
                        '<span class="thread reply">reply in %s</span>'
                        % thread)
        ps_line = ""
        if key in ps and ps[key]:
            ps_line = '<div class="ps">P.S. %s</div>' % _esc(ps[key])
        email_blocks.append(
            '<div class="email">'
            '<div class="email-head">%s %s &mdash; day %s</div>'
            '<div class="subject">Subject: %s</div>'
            '<div class="objective">Objective: %s</div>'
            '<div class="body">%s</div>'
            '%s'
            '</div>'
            % (thread_label, _esc(key),
               {"em1": "1", "em2": "4", "em3": "8", "em4": "12",
                "em5": "21"}.get(key, "?"),
               _esc(subj), _esc(obj), _esc(body).replace("\n", "<br>"),
               ps_line))
    emails_html = "\n".join(email_blocks)

    # LinkedIn messages.
    linkedin = copy.get("linkedin") or {}
    li_blocks = []
    li_days = {"connect": "1", "msg1": "3", "msg2": "8", "msg3": "14"}
    for key in ("connect", "msg1", "msg2", "msg3"):
        body = linkedin.get(key, "")
        obj = _plan_objective(plan, key)
        if body:
            li_blocks.append(
                '<div class="linkedin-msg">'
                '<div class="li-head">%s &mdash; day %s</div>'
                '<div class="objective">Objective: %s</div>'
                '<div class="body">%s</div>'
                '</div>'
                % (_esc(key), li_days.get(key, "?"), _esc(obj),
                   _esc(body).replace("\n", "<br>")))
    linkedin_html = "\n".join(li_blocks) if li_blocks else "<p>No LinkedIn (no profile or not written).</p>"

    # Hold banner.
    hold_banner = ""
    if hold:
        hold_banner = ('<div class="hold-banner">HELD: %s</div>'
                       % _esc(hold_reason))

    return '''
<div class="lead-card">
  <h2>{company}</h2>
  {hold_banner}
  <div class="meta">
    {qual_badge}
    {_gate_badge}
    <span class="signal">Signal: {signal}</span>
  </div>
  <div class="section">
    <h3>Verified facts</h3>
    {facts_list}
  </div>
  <div class="section hypothesis-section">
    <h3>Problem hypothesis <span class="hypothesis-label">(HYPOTHESIS, not a finding)</span></h3>
    <p class="hypothesis">{hypothesis}</p>
    <p class="hypothesis-basis">Business model: {biz_model}. Signal: {signal}.</p>
  </div>
  <div class="section">
    <h3>Capability chosen</h3>
    <p><b>{cap_key}</b>: {cap_sentence}</p>
    <p class="why">{why_cap}</p>
  </div>
  <div class="section">
    <h3>Email sequence</h3>
    {emails_html}
  </div>
  <div class="section">
    <h3>LinkedIn sequence</h3>
    {linkedin_html}
  </div>
  <div class="section">
    <h3>Sequence gate</h3>
    {_gate_lines}
  </div>
</div>
'''.format(
        company=company,
        hold_banner=hold_banner,
        qual_badge=_qualification_badge(qual),
        _gate_badge=_gate_badge(gate),
        signal=_esc(signal),
        facts_list=facts_list,
        hypothesis=_esc(hypothesis),
        biz_model=_esc(result.get("business_model", "")),
        cap_key=_esc(cap_key),
        cap_sentence=_esc(cap_sentence),
        why_cap=_esc(why_cap),
        emails_html=emails_html,
        linkedin_html=linkedin_html,
        _gate_lines=_gate_lines(gate),
    )


_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }
.lead-card { border: 1px solid #ddd; border-radius: 8px; padding: 1.5em;
             margin-bottom: 2em; }
.lead-card h2 { margin-top: 0; }
.meta { display: flex; gap: 1em; align-items: center; margin-bottom: 1em;
        flex-wrap: wrap; }
.qualification { color: white; padding: 2px 10px; border-radius: 4px;
                 font-size: 0.85em; font-weight: bold; }
.gate { padding: 2px 10px; border-radius: 4px; font-size: 0.85em;
        font-weight: bold; }
.gate.pass { background: #2d6a4f; color: white; }
.gate.fail { background: #9e2a2b; color: white; }
.signal { color: #666; font-size: 0.9em; }
.section { margin: 1em 0; }
.section h3 { border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
.hypothesis-section { background: #fff8e1; border: 1px dashed #e09f3e;
                      border-radius: 6px; padding: 1em; }
.hypothesis-label { color: #e09f3e; font-size: 0.85em; font-weight: bold; }
.hypothesis { font-style: italic; font-size: 1.05em; }
.hypothesis-basis { color: #666; font-size: 0.9em; }
.why { color: #555; font-size: 0.9em; }
.email { border-left: 3px solid #457b9d; padding: 0.5em 1em; margin: 0.5em 0;
         background: #f8f9fa; }
.email-head { font-weight: bold; font-size: 0.85em; color: #457b9d; }
.subject { font-weight: bold; margin: 0.3em 0; }
.objective { color: #666; font-size: 0.85em; font-style: italic; }
.body { margin: 0.5em 0; white-space: pre-wrap; }
.ps { margin-top: 0.5em; font-style: italic; color: #555;
      border-top: 1px dotted #ccc; padding-top: 0.3em; }
.thread { font-size: 0.75em; padding: 1px 6px; border-radius: 3px; }
.thread.new { background: #457b9d; color: white; }
.thread.reply { background: #ddd; color: #555; }
.linkedin-msg { border-left: 3px solid #0a66c2; padding: 0.5em 1em;
                margin: 0.5em 0; background: #f0f6ff; }
.li-head { font-weight: bold; font-size: 0.85em; color: #0a66c2; }
.failure { color: #9e2a2b; font-size: 0.9em; margin: 0.2em 0; }
.warning { color: #e09f3e; font-size: 0.9em; margin: 0.2em 0; }
.hold-banner { background: #9e2a2b; color: white; padding: 0.5em 1em;
               border-radius: 4px; margin-bottom: 1em; font-weight: bold; }
.source { color: #888; font-size: 0.85em; }
.summary { background: #f0f0f0; padding: 1em; border-radius: 6px;
           margin-bottom: 2em; }
"""


def render_page(results, leads=None, title="Copy Engine v2 Preview"):
    """Full HTML page with all leads."""
    leads = leads or [{}] * len(results)
    cards = []
    for r, lead in zip(results, leads):
        cards.append(render_lead(r, lead))

    # Summary.
    total = len(results)
    qualified = sum(1 for r in results
                    if r.get("qualification", "").startswith("QUALIFIED"))
    held = sum(1 for r in results if r.get("hold"))
    passed_gate = sum(1 for r in results
                      if r.get("gate") and r["gate"].get("passed"))
    caps = set(r.get("capability_key") for r in results
               if r.get("capability_key"))

    summary = '''
<div class="summary">
  <h2>{title}</h2>
  <p><b>{total}</b> leads: <b>{qualified}</b> qualified,
     <b>{held}</b> held, <b>{passed_gate}</b> passed the sequence gate.</p>
  <p>Distinct capabilities chosen: <b>{n_caps}</b> ({caps_list})</p>
</div>
'''.format(title=_esc(title), total=total, qualified=qualified, held=held,
           passed_gate=passed_gate, n_caps=len(caps),
           caps_list=", ".join(sorted(caps)) if caps else "none")

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{summary}
{cards}
</body>
</html>""".format(title=_esc(title), css=_CSS, summary=summary,
                  cards="\n".join(cards))


def write_page(path, results, leads=None, title="Copy Engine v2 Preview"):
    """Write the preview HTML to a file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_page(results, leads, title))
    return path
