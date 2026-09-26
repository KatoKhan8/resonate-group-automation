"""The v2 copy engine: stages A to H, per lead.

docs/COPY-ENGINE-SPEC-v2.md is the spec. Claude owns the prompts
(`copystages.py`, `copyprompts.py`) and the gate (`sequencegate.py`); this
module owns the implementation, the preview and the tests.

THE COST SHAPE. Stages A to E run on Groq (gpt-oss-120b, reasoning effort
low). Only stage F, the writer, runs on Sonnet. That is deliberate: the
expensive model writes what a prospect reads and nothing else.

WHAT THIS IS NOT. It is not `work/ten_pages.py`. That is the v1 pipeline:
direct synchronous calls, no ledger, standing paragraphs from templates. The
v2 engine writes every email whole from a per-lead plan, carries the plan
from E into F so the writer argues to objectives rather than inventing them,
and rewrites only the step the gate names on failure.
"""
import json
import re
import time
import urllib.error
import urllib.request

from . import copyprompts, copystages, sequencegate

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"
UA = "resonate-os/2.0 (+https://resonategroup.co)"

#: Sonnet truncates at small caps. 4000 is generous enough to fit the full
#: writer output with room for reasoning. Measured: at 700 it cut off 4/10,
#: at 2600 it cut off 5/10.
SONNET_MAX_TOKENS = 4000

#: Groq spends max_tokens on reasoning before output. A small cap returns an
#: empty string, not an error. 4000 leaves room.
GROQ_MAX_TOKENS = 4000

#: The four qualification outcomes.
QUALIFIED_RICH = "QUALIFIED_RICH"
QUALIFIED_THIN = "QUALIFIED_THIN"
INSUFFICIENT = "INSUFFICIENT"
UNQUALIFIED = "UNQUALIFIED"

#: Qualifications that block sending.
BLOCKING = (INSUFFICIENT, UNQUALIFIED)

#: Email step keys in order.
EMAIL_KEYS = ("em1", "em2", "em3", "em4", "em5")

#: LinkedIn step keys in order.
LINKEDIN_KEYS = ("connect", "msg1", "msg2", "msg3")

#: Thread assignment per the spec's three-thread cadence.
THREAD_OF = {"em1": "A", "em2": "A", "em3": "B", "em4": "B", "em5": "C"}

#: Day offsets for emails.
EMAIL_DAYS = {"em1": 1, "em2": 4, "em3": 8, "em4": 12, "em5": 21}

#: Day offsets for LinkedIn.
LINKEDIN_DAYS = {"connect": 1, "msg1": 3, "msg2": 8, "msg3": 14}


# --------------------------------------------------------------------------
# HTTP plumbing
# --------------------------------------------------------------------------

def _post(url, payload, headers, timeout=120, attempts=4):
    """One POST, with backoff on 429 only.

    429 is the one failure where the SAME input is worth retrying: the
    provider is asking us to wait, not telling us the request was wrong.
    Every other 4xx is retried never: an identical request buys an identical
    refusal at full price.
    """
    body = json.dumps(payload).encode()
    for i in range(attempts):
        req = urllib.request.Request(url, data=body, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == attempts - 1:
                raise
            wait = float(e.headers.get("retry-after") or (2 ** i))
            time.sleep(min(wait, 30))


def _groq(system, user, max_tokens=GROQ_MAX_TOKENS, api_key=None):
    """One Groq call. Returns the raw text content."""
    from . import providers
    key = api_key
    if key is None:
        key, _ = providers.model_key("groq")
    data = _post(GROQ_URL, {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning_effort": "low",
    }, {"Authorization": "Bearer %s" % key,
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Accept": "application/json"})
    usage = data.get("usage") or {}
    return (data["choices"][0]["message"]["content"],
            {"in": usage.get("prompt_tokens", 0),
             "out": usage.get("completion_tokens", 0)})


def _sonnet(system, user, max_tokens=SONNET_MAX_TOKENS, api_key=None):
    """One Sonnet call. Returns the raw text content."""
    from . import providers
    key = api_key
    if key is None:
        key, _ = providers.model_key("anthropic")
    data = _post(ANTHROPIC_URL, {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }, {"x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "User-Agent": UA})
    usage = data.get("usage") or {}
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return (text,
            {"in": usage.get("input_tokens", 0),
             "out": usage.get("output_tokens", 0)})


def _as_json(text):
    """Parse model output as JSON, handling fences and literal newlines.

    Models wrap JSON in prose or fences often enough to handle it.
    `strict=False` because the model emits literal newlines in strings,
    which is invalid JSON but trivially readable and not worth a retry.

    A JSONDecodeError is treated as truncation FIRST: Sonnet at max_tokens
    700 cut off mid-JSON on 4 of 10. The caller decides whether to retry
    or hold.
    """
    t = str(text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("no JSON object in model output: %r" % t[:200])
    try:
        return json.loads(t[i:j + 1], strict=False)
    except json.JSONDecodeError as e:
        raise ValueError("JSON truncated or malformed (likely truncation): "
                         "%s: %r" % (e, t[:200])) from e


# --------------------------------------------------------------------------
# THE STAGE RUNNER
# --------------------------------------------------------------------------

def _clean_nav(text, limit=2500):
    """Strip navigation chrome from scraped text."""
    nav = re.compile(
        r"^(?:\s*(?:login|about|home|menu|contact|services|work|"
        r"recent work|blog|pricing|team|careers|portfolio|our work|"
        r"skip to main content)\b[\s|,·\-]*)+", re.I)
    t = nav.sub("", str(text or "")).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:limit]


def _role_family(title):
    """Map a job title to a role family for stage D.

    Returns one of: executive, operations, delivery, finance.
    Defaults to executive for unknown titles: a founder-level person is the
    commonest case and the safest default.
    """
    t = str(title or "").lower()
    if any(w in t for w in ("finance", "cfo", "financial", "accounting")):
        return "finance"
    if any(w in t for w in ("project", "delivery", "production",
                            "studio manager", "design director")):
        return "delivery"
    if any(w in t for w in ("operations", "coo", "ops", "resource",
                            "resourcing", "traffic", "head of production")):
        return "operations"
    return "executive"


def _assets_available(config):
    """What the strategy stage may promise. From the client config.

    The spec is explicit: until the client supplies case studies, benchmarks,
    calculators and demo links, days 8 and 12 use a concrete product workflow
    described in plain words. Nothing is invented.
    """
    product = (config or {}).get("product") or {}
    caps = product.get("capabilities") or {}
    available = []
    if caps:
        available.append("six Productive capabilities: %s"
                         % ", ".join(caps.keys()))
    what = product.get("what_it_is")
    if what:
        available.append("product description: %s" % what)
    return "; ".join(available) if available else "no assets available"


def run_lead(lead, sources, config, groq_fn=None, sonnet_fn=None):
    """Run stages A to H for one lead. Returns a result dict.

    `lead` is a dict with: name, title, email, company, domain, first, last,
    sender_name, sender_email, linkedin (url or None).
    `sources` is a list of {label, url, text} already cleaned of chrome.
    `config` is the client config (from `clients.load`).
    `groq_fn` and `sonnet_fn` are optional callables for testing. Each takes
    (system, user) and returns a string.

    Returns a dict with:
        qualification: one of the four outcomes
        facts: list of extracted facts
        hypothesis: the problem hypothesis (stage C output)
        capability: the matched capability (stage D output)
        plan: the sequence strategy (stage E output)
        written: the copy (stage F output), or None if held
        gate: the gate result (stage G output)
        output: the EmailBison/HeyReach shapes (stage H output)
        held: reason the lead was held, or None
        error: error message, or None
        tokens: {groq_in, groq_out, sonnet_in, sonnet_out}
    """
    groq = groq_fn or (lambda s, u: _groq(s, u))
    sonnet = sonnet_fn or (lambda s, u: _sonnet(s, u))
    tokens = {"groq_in": 0, "groq_out": 0, "sonnet_in": 0, "sonnet_out": 0}
    result = {"lead": lead, "qualification": None, "facts": [],
              "hypothesis": None, "capability": None, "plan": None,
              "written": None, "gate": None, "output": None,
              "held": None, "error": None, "tokens": tokens,
              "stages": {}}

    company = lead.get("company", "")
    domain = lead.get("domain", "")
    title = lead.get("title", "")
    role_fam = _role_family(title)

    def _groq_tracked(system, user, **kw):
        if groq_fn:
            text = groq(system, user)
            return text, {"in": 0, "out": 0}
        text, usage = _groq(system, user, **kw)
        tokens["groq_in"] += usage.get("in", 0)
        tokens["groq_out"] += usage.get("out", 0)
        return text, usage

    def _sonnet_tracked(system, user, **kw):
        if sonnet_fn:
            text = sonnet(system, user)
            return text, {"in": 0, "out": 0}
        text, usage = _sonnet(system, user, **kw)
        tokens["sonnet_in"] += usage.get("in", 0)
        tokens["sonnet_out"] += usage.get("out", 0)
        return text, usage

    # Prepare source blocks for the prompts
    source_blocks = [{"label": s.get("label") or "site",
                      "url": s.get("url"),
                      "text": _clean_nav(s.get("text"))}
                     for s in (sources or [])]

    # ---- STAGE A: Lead qualification (Groq) ----
    try:
        text, _ = _groq_tracked(
            copyprompts.ICP_SYSTEM,
            copyprompts.icp_user(company, domain, source_blocks))
        icp = _as_json(text)
        result["stages"]["A_icp"] = icp
    except Exception as e:
        result["error"] = "stage A (ICP): %s: %s" % (type(e).__name__,
                                                       str(e)[:200])
        return result

    is_agency = icp.get("is_agency", False)
    confidence = icp.get("confidence", 0)
    if not is_agency:
        what = icp.get("what_they_actually_are") or "unclear"
        result["qualification"] = UNQUALIFIED
        result["held"] = "not an agency: %s" % what
        return result

    # ---- STAGE B: Research extraction (Groq) ----
    try:
        text, _ = _groq_tracked(
            copyprompts.EXTRACT_SYSTEM,
            copyprompts.extract_user(company, domain, source_blocks))
        extraction = _as_json(text)
        result["stages"]["B_extract"] = extraction
    except Exception as e:
        result["error"] = "stage B (extract): %s: %s" % (type(e).__name__,
                                                          str(e)[:200])
        return result

    facts = extraction.get("facts") or []
    for f in facts:
        f["source_url"] = copyprompts.source_url_for(f, source_blocks)
    result["facts"] = facts
    angle = extraction.get("angle")
    angle_reason = extraction.get("angle_reason") or ""

    if not extraction.get("usable") or len(facts) < copyprompts.MIN_FACTS:
        result["held"] = "no usable fact: %d fact(s), usable=%s" % (
            len(facts), extraction.get("usable"))
        result["qualification"] = INSUFFICIENT
        return result

    # ---- STAGE C: Problem hypothesis (Groq) ----
    try:
        text, _ = _groq_tracked(
            copystages.HYPOTHESIS_SYSTEM,
            copystages.hypothesis_user(
                company, domain, title, facts))
        hyp = _as_json(text)
        result["stages"]["C_hypothesis"] = hyp
        result["hypothesis"] = hyp
    except Exception as e:
        result["error"] = "stage C (hypothesis): %s: %s" % (
            type(e).__name__, str(e)[:200])
        return result

    qualification = hyp.get("qualification", QUALIFIED_THIN)
    result["qualification"] = qualification
    if qualification in BLOCKING:
        result["held"] = "qualification %s: %s" % (
            qualification, hyp.get("hypothesis", "")[:120])
        return result

    # ---- STAGE D: Value proposition matching (Groq) ----
    product = (config or {}).get("product") or {}
    capabilities = product.get("capabilities") or {}
    hypothesis_text = hyp.get("hypothesis", "")

    try:
        text, _ = _groq_tracked(
            copystages.MATCH_SYSTEM,
            copystages.match_user(
                hypothesis_text, role_fam, title, capabilities))
        match = _as_json(text)
        result["stages"]["D_match"] = match
        result["capability"] = match
    except Exception as e:
        result["error"] = "stage D (match): %s: %s" % (
            type(e).__name__, str(e)[:200])
        return result

    cap_key = match.get("capability_key", "")
    cap_sentence = capabilities.get(cap_key, "")
    what_changes = match.get("what_changes", "")

    # ---- STAGE E: Sequence strategy (Groq) ----
    assets = _assets_available(config)
    try:
        text, _ = _groq_tracked(
            copystages.STRATEGY_SYSTEM,
            copystages.strategy_user(
                company, hypothesis_text, cap_sentence, what_changes,
                title, facts, assets))
        plan = _as_json(text)
        result["stages"]["E_strategy"] = plan
        result["plan"] = plan
    except Exception as e:
        result["error"] = "stage E (strategy): %s: %s" % (
            type(e).__name__, str(e)[:200])
        return result

    # ---- STAGE F: Copy generation (Sonnet) ----
    ps_variant = copyprompts.ps_variant_for(lead.get("email", ""))
    if ps_variant == "ps_none":
        ps_variant = "ps_fact"
    result["ps_variant"] = ps_variant

    has_linkedin = bool(lead.get("linkedin"))
    lead_for_writer = {
        "name": ("%s %s" % (lead.get("first", ""),
                            lead.get("last", ""))).strip(),
        "title": title,
        "sender_name": lead.get("sender_name", ""),
        "linkedin": lead.get("linkedin"),
    }

    plan_json = json.dumps(plan, indent=2)
    try:
        text, _ = _sonnet_tracked(
            copystages.WRITER_SYSTEM,
            copystages.writer_user(
                lead_for_writer, company, facts, plan_json,
                cap_sentence, ps_variant, has_linkedin))
        written = _as_json(text)
        result["stages"]["F_written"] = written
    except Exception as e:
        result["error"] = "stage F (writer): %s: %s" % (
            type(e).__name__, str(e)[:200])
        return result

    if written.get("hold"):
        result["held"] = "writer held: %s" % written.get("hold_reason")
        return result

    result["written"] = written

    # ---- STAGE G: Quality validation (code) ----
    sequence = {
        "emails": {k: written.get("emails", {}).get(k, "")
                   for k in EMAIL_KEYS},
        "linkedin": {k: written.get("linkedin", {}).get(k, "")
                     for k in LINKEDIN_KEYS},
        "subjects": {
            "A": written.get("subject", ""),
            "B": written.get("subject_alt", ""),
            "C": written.get("subject_breakup", ""),
        },
        "ps": written.get("ps") or {},
        "hypothesis": hypothesis_text,
        "company": company,
    }
    gate = sequencegate.check(
        sequence,
        facts=facts,
        capability=cap_sentence,
        qualification=qualification)
    result["gate"] = gate
    result["stages"]["G_gate"] = gate

    # ---- STAGE H: Output shapes ----
    output = _build_output(lead, written, config)
    result["output"] = output
    result["stages"]["H_output"] = output

    return result


def run_batch(leads_with_sources, config, groq_fn=None, sonnet_fn=None):
    """Run the engine for a batch of leads. Returns a list of results.

    `leads_with_sources` is a list of (lead, sources) tuples.
    Also runs the batch-level capability check through the gate.
    """
    results = []
    for lead, sources in leads_with_sources:
        r = run_lead(lead, sources, config, groq_fn=groq_fn,
                     sonnet_fn=sonnet_fn)
        results.append(r)

    # Batch-level gate: check capability diversity across the batch.
    caps = [r.get("capability", {}).get("capability_key")
            for r in results if r.get("capability")]
    if len(caps) >= 5:
        batch_gate = sequencegate.check(
            {}, batch_capabilities=caps)
        for r in results:
            if r.get("gate") is None:
                r["gate"] = {"passed": True, "failures": [], "warnings": []}
            if batch_gate.get("failures"):
                r["gate"]["failures"].extend(batch_gate["failures"])
            if batch_gate.get("warnings"):
                r["gate"].setdefault("warnings", []).extend(
                    batch_gate["warnings"])
    return results


# --------------------------------------------------------------------------
# STAGE H: Output shapes
# --------------------------------------------------------------------------

def _build_output(lead, written, config):
    """Build the EmailBison custom variables and HeyReach steps.

    EmailBison: subject_1, body_1..5, template ids.
    HeyReach: the four LinkedIn steps.
    Preview: everything the operator reviews.
    """
    emails = written.get("emails") or {}
    linkedin = written.get("linkedin") or {}
    ps = written.get("ps") or {}
    subjects = {
        "A": written.get("subject", ""),
        "B": written.get("subject_alt", ""),
        "C": written.get("subject_breakup", ""),
    }

    # EmailBison custom variables
    email_steps = []
    for key in EMAIL_KEYS:
        body = emails.get(key, "")
        thread = THREAD_OF[key]
        subj = subjects.get(thread, "")
        is_reply = key in ("em2", "em4")
        email_steps.append({
            "key": key,
            "day": EMAIL_DAYS[key],
            "thread": thread,
            "subject": ("Re: %s" % subj) if is_reply else subj,
            "thread_reply": is_reply,
            "body": body,
            "ps": ps.get(key, ""),
        })

    emailbison = {
        "subject_1": subjects.get("A", ""),
        "subjects": subjects,
        "steps": email_steps,
    }

    # HeyReach LinkedIn steps
    li_steps = []
    for key in LINKEDIN_KEYS:
        text = linkedin.get(key, "")
        if not text:
            continue
        li_steps.append({
            "key": key,
            "day": LINKEDIN_DAYS[key],
            "body": text,
        })

    heyreach = {"steps": li_steps}

    return {
        "emailbison": emailbison,
        "heyreach": heyreach,
    }


# --------------------------------------------------------------------------
# Preview rendering
# --------------------------------------------------------------------------

def preview_html(results, sender_signatures=None):
    """Render the full preview as HTML. One page per lead.

    Shows: qualification status, verified facts with sources, the hypothesis
    visibly marked as a hypothesis, the capability and why, five emails with
    thread and subject, four LinkedIn messages, each message's objective from
    the plan, the gate's results, and any warning.
    """
    import html as html_mod
    sender_signatures = sender_signatures or {}
    esc = html_mod.escape

    pages = []
    for rec in results:
        lead = rec.get("lead") or {}
        pages.append(_preview_page(rec, esc, sender_signatures))
    return pages


def _preview_page(rec, esc, sender_sigs):
    """One lead's preview page as HTML."""
    lead = rec.get("lead") or {}
    company = lead.get("company", "")
    qualification = rec.get("qualification") or "UNKNOWN"
    facts = rec.get("facts") or []
    hyp = rec.get("hypothesis") or {}
    cap = rec.get("capability") or {}
    plan = rec.get("plan") or {}
    written = rec.get("written")
    gate = rec.get("gate")
    held = rec.get("held")
    error = rec.get("error")

    qual_class = {
        "QUALIFIED_RICH": "rich",
        "QUALIFIED_THIN": "thin",
        "INSUFFICIENT": "insuf",
        "UNQUALIFIED": "unq",
    }.get(qualification, "unk")

    parts = [_PREVIEW_CSS]
    parts.append("<div class='lead'>")
    parts.append("<h2>%s &mdash; %s</h2>" % (
        esc(lead.get("name", "")), esc(company)))
    parts.append("<p class='meta'>%s &middot; %s &middot; "
                 "<span class='qual %s'>%s</span></p>" % (
                     esc(lead.get("email", "")),
                     esc(lead.get("title", "") or "role unknown"),
                     qual_class, esc(qualification)))

    if held:
        parts.append("<div class='held'><b>HELD</b> &mdash; %s</div>"
                     % esc(held))
    if error:
        parts.append("<div class='error'><b>ERROR</b> &mdash; %s</div>"
                     % esc(error))

    # Facts
    parts.append("<div class='facts'><h3>Verified facts</h3>")
    for i, f in enumerate(facts, 1):
        parts.append("<div class='fact'><b>%d.</b> %s"
                     "<div class='src'>[%s] %s</div></div>" % (
                         i, esc(f.get("text", "")),
                         esc(f.get("kind", "")),
                         esc((f.get("quote") or "")[:200])))
    parts.append("</div>")

    # Hypothesis - VISIBLY MARKED
    if hyp:
        parts.append("<div class='hypothesis'>"
                     "<h3>Problem hypothesis "
                     "<span class='label'>(HYPOTHESIS, not a finding)"
                     "</span></h3>"
                     "<p>%s</p>"
                     "<p class='basis'>Basis: %s</p>"
                     "<p class='basis'>Signal: %s (%s)</p>"
                     "</div>" % (
                         esc(hyp.get("hypothesis", "")),
                         esc(hyp.get("hypothesis_basis", "")),
                         esc(str(hyp.get("signal") or "none")),
                         esc(hyp.get("signal_strength", ""))))

    # Capability
    if cap:
        parts.append("<div class='capability'>"
                     "<h3>Matched capability</h3>"
                     "<p><b>%s</b>: %s</p>"
                     "<p class='basis'>Why: %s</p>"
                     "</div>" % (
                         esc(cap.get("capability_key", "")),
                         esc(cap.get("what_changes", "")),
                         esc(cap.get("why_this_one", ""))))

    # Plan objectives
    if plan:
        parts.append("<div class='plan'><h3>Sequence plan</h3>")
        emails_plan = (plan.get("emails") or {})
        for key in EMAIL_KEYS:
            step = emails_plan.get(key) or {}
            if step:
                parts.append("<div class='plan-step'><b>%s</b>: %s"
                             "<div class='angle'>angle: %s</div>"
                             "<div class='cta'>CTA: %s</div></div>" % (
                                 key, esc(step.get("objective", "")),
                                 esc(step.get("angle", "")),
                                 esc(step.get("cta", ""))))
        parts.append("</div>")

    # Emails
    if written:
        output = rec.get("output") or {}
        eb = output.get("emailbison") or {}
        for step in eb.get("steps") or []:
            parts.append("<div class='email'>"
                         "<div class='email-head'>"
                         "<b>Day %d</b> &middot; Thread %s%s &middot; "
                         "<b>%s</b></div>"
                         "<div class='email-body'>%s</div>" % (
                             step["day"],
                             esc(step["thread"]),
                             " (reply)" if step["thread_reply"] else " (opens)",
                             esc(step["subject"]),
                             esc(step["body"])))
            if step.get("ps"):
                parts.append("<div class='ps'>P.S. %s</div>"
                             % esc(step["ps"]))
            parts.append("</div>")

        # LinkedIn
        hr = output.get("heyreach") or {}
        parts.append("<h3>LinkedIn</h3>")
        for step in hr.get("steps") or []:
            li_plan = (plan.get("linkedin") or {}).get(step["key"]) or {}
            parts.append("<div class='linkedin'>"
                         "<div class='li-head'><b>Day %d</b> %s</div>"
                         "<div class='li-obj'>objective: %s</div>"
                         "<div class='li-body'>%s</div></div>" % (
                             step["day"], esc(step["key"]),
                             esc(li_plan.get("objective", "")),
                             esc(step["body"])))

    # Gate results
    if gate:
        parts.append("<div class='gate'><h3>Sequence gate</h3>")
        lines = sequencegate.report_lines(gate)
        for line in lines:
            cls = "fail" if "FAIL" in line else ("warn" if "warn" in line
                                                  else "")
            parts.append("<div class='gate-line %s'>%s</div>" % (
                cls, esc(line)))
        parts.append("</div>")

    parts.append("</div>")
    return "\n".join(parts)


_PREVIEW_CSS = """<style>
:root{--ink:#16191d;--dim:#5a6472;--line:#dfe3e8;--bg:#f4f5f7}
*{box-sizing:border-box}
body{font:14px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;
background:var(--bg);color:var(--ink);padding:20px}
.lead{background:#fff;border:1px solid var(--line);border-radius:8px;
padding:20px;margin:0 0 24px}
h2{margin:0 0 4px;font-size:18px} h3{font-size:13px;text-transform:uppercase;
letter-spacing:.06em;color:var(--dim);margin:18px 0 8px}
.meta{color:var(--dim);font-size:13px;margin:0 0 12px}
.qual{font-weight:700;padding:2px 8px;border-radius:3px;font-size:11px}
.qual.rich{background:#e8f5ee;color:#1d6b45}
.qual.thin{background:#fff8e1;color:#8a6d00}
.qual.insuf{background:#fdecea;color:#9b2c22}
.qual.unq{background:#fdecea;color:#9b2c22}
.held{background:#fdecea;border:1px solid #f5c2bd;border-radius:6px;
padding:12px 14px;margin:0 0 14px;color:#9b2c22}
.error{background:#fff3e0;border:1px solid #ffe0b2;border-radius:6px;
padding:12px 14px;margin:0 0 14px;color:#e65100}
.facts{margin:0 0 14px}
.fact{border-left:3px solid #2f855a;padding:6px 10px;margin:0 0 6px;
background:#fbfcfd}
.src{color:#4a5563;font-size:12px;margin-top:3px}
.hypothesis{background:#f0f4ff;border:1px solid #c3d4ef;border-radius:6px;
padding:14px;margin:0 0 14px}
.hypothesis .label{font-size:11px;color:#c53030;font-weight:700;
background:#fdecea;padding:2px 6px;border-radius:3px;margin-left:6px}
.basis{color:var(--dim);font-size:12.5px;margin:4px 0 0}
.capability{background:#f0fff4;border:1px solid #c6f6d5;border-radius:6px;
padding:14px;margin:0 0 14px}
.plan{margin:0 0 14px}
.plan-step{border-left:2px solid var(--line);padding:4px 10px;margin:0 0 6px}
.angle,.cta{color:var(--dim);font-size:12px}
.email{border:1px solid var(--line);border-radius:6px;margin:0 0 12px;
overflow:hidden}
.email-head{padding:8px 12px;background:#fafbfc;border-bottom:1px solid #eceff2;
font-size:12px;color:var(--dim)}
.email-body{padding:10px 14px;white-space:pre-wrap}
.ps{margin-top:10px;padding-top:8px;border-top:1px dashed #d0d7de;
color:#4a5563;font-style:italic;padding-left:14px;padding-bottom:10px}
.linkedin{border:1px solid var(--line);border-radius:6px;margin:0 0 10px;
overflow:hidden}
.li-head{padding:6px 12px;background:#fafbfc;border-bottom:1px solid #eceff2;
font-size:12px;color:var(--dim)}
.li-obj{padding:4px 12px 0;font-size:11.5px;color:#2f855a;font-style:italic}
.li-body{padding:8px 14px;white-space:pre-wrap}
.gate{margin:14px 0 0;padding:12px 14px;background:#fafbfc;
border:1px solid var(--line);border-radius:6px}
.gate-line{font-size:12.5px;font-family:monospace}
.gate-line.fail{color:#9b2c22;font-weight:700}
.gate-line.warn{color:#8a6d00}
</style>"""


def distinct_capabilities(results):
    """Count distinct capabilities stage D chose across a batch.

    If this count is 1, stage D is defaulting and the gate says so.
    """
    caps = set()
    for r in results:
        cap = (r.get("capability") or {}).get("capability_key")
        if cap:
            caps.add(str(cap).strip().lower())
    return len(caps)
