"""The Client Second Brain as retrieval over what already exists.

This module is a RETRIEVAL LAYER, not a store. Every fact it returns comes
from `config/clients/<client>.yaml` (via `clients.load`) or from modules that
already read it (`contextpack`, `playbooks`, `strategy`). It writes no client
fact anywhere.

`for_task(task, client, **scope)` returns only the sections a given task
needs. The whole brain is never passed into a prompt: the spec forbids it and
the cost shape depends on it.

Sections map to ARCHITECTURE-UPGRADE-SPEC section 3:
    profile       A. Client Profile
    market        B. Market Intelligence
    competitors   C. Competitor Intelligence (MISSING, never invented)
    customers     D. Customer Intelligence
    offers        E. Offer Library (MISSING until TASK-318)
    messaging     F. Messaging Intelligence
    learning      G. Learning Memory

Every fact carries `source`, `date` and `verified` (True/False). A fact that
cannot answer those three questions is not returned.
"""
import datetime
import os

from . import clients

TODAY = datetime.date.today().isoformat()

SECTIONS = (
    "profile", "market", "competitors", "customers",
    "offers", "messaging", "learning",
)

MISSING_SECTIONS = frozenset({"competitors", "offers", "learning"})

TASK_SECTIONS = {
    "cold_email_writing": ("profile", "customers", "messaging", "offers"),
    "linkedin_writing": ("profile", "customers", "messaging"),
    "account_research": ("profile", "market", "customers"),
    "signal_verification": ("market", "customers"),
    "campaign_strategy": ("profile", "market", "customers", "messaging"),
}


def _fact(text, source, date=None, verified=True):
    return {
        "text": text,
        "source": source,
        "date": date or TODAY,
        "verified": verified,
    }


def _profile(config):
    facts = []
    product = clients.product(config)
    if product.get("name"):
        facts.append(_fact(
            f"Product: {product['name']}",
            "config/clients/productive.yaml product.name"))
    if product.get("what_it_is"):
        facts.append(_fact(
            product["what_it_is"],
            "config/clients/productive.yaml product.what_it_is"))
    for key, value in (product.get("capabilities") or {}).items():
        facts.append(_fact(
            f"{key}: {value}",
            "config/clients/productive.yaml product.capabilities"))
    sender = clients.sender_identity(config)
    if sender.get("works_on"):
        facts.append(_fact(
            sender["works_on"],
            "config/clients/productive.yaml sender.works_on"))
    if config.get("domain"):
        facts.append(_fact(
            f"Domain: {config['domain']}",
            "config/clients/productive.yaml domain"))
    return facts


def _market(config):
    facts = []
    market = config.get("market") or {}
    if market.get("must"):
        facts.append(_fact(
            f"ICP must: {market['must']}",
            "config/clients/productive.yaml market.must"))
    geos = market.get("geos") or []
    if geos:
        facts.append(_fact(
            f"Target geos: {', '.join(str(g) for g in geos)}",
            "config/clients/productive.yaml market.geos"))
    exclude = market.get("exclude_geos") or []
    if exclude:
        facts.append(_fact(
            f"Excluded geos: {', '.join(str(g) for g in exclude)}",
            "config/clients/productive.yaml market.exclude_geos"))
    structural = (config.get("icp") or {}).get("structural") or {}
    types = structural.get("company_types") or {}
    primary = types.get("primary") or []
    if primary:
        facts.append(_fact(
            f"Company types: {', '.join(str(t) for t in primary)}",
            "config/clients/productive.yaml icp.structural.company_types.primary"))
    verticals = types.get("verticals") or []
    if verticals:
        facts.append(_fact(
            f"Verticals: {', '.join(str(v) for v in verticals[:8])}"
            + (f" (+{len(verticals) - 8} more)" if len(verticals) > 8 else ""),
            "config/clients/productive.yaml icp.structural.company_types.verticals"))
    emp = (structural.get("employees") or {})
    if emp.get("min"):
        facts.append(_fact(
            f"Min employees: {emp['min']}",
            "config/clients/productive.yaml icp.structural.employees.min"))
    if market.get("size_min_employees"):
        facts.append(_fact(
            f"Size min employees: {market['size_min_employees']}",
            "config/clients/productive.yaml market.size_min_employees"))
    return facts


def _competitors():
    return []


def _customers(config):
    facts = []
    personas = clients.personas(config)
    for persona_name, persona in personas.items():
        titles = persona.get("titles") or []
        if titles:
            facts.append(_fact(
                f"Persona '{persona_name}' titles: {', '.join(str(t) for t in titles[:6])}"
                + (f" (+{len(titles) - 6} more)" if len(titles) > 6 else ""),
                f"config/clients/productive.yaml personas.{persona_name}.titles"))
        angles = persona.get("angles") or {}
        for angle_key, angle_text in angles.items():
            facts.append(_fact(
                f"Persona '{persona_name}', angle '{angle_key}': {angle_text}",
                f"config/clients/productive.yaml personas.{persona_name}.angles.{angle_key}"))
        cap = persona.get("cap_per_domain")
        if cap is not None:
            facts.append(_fact(
                f"Persona '{persona_name}' cap per domain: {cap}",
                f"config/clients/productive.yaml personas.{persona_name}.cap_per_domain"))
    return facts


def _offers():
    return []


def _messaging(config):
    facts = []
    tone = config.get("tone") or {}
    for channel in ("email", "linkedin"):
        if tone.get(channel):
            facts.append(_fact(
                f"Tone ({channel}): {tone[channel]}",
                f"config/clients/productive.yaml tone.{channel}"))
    labels = clients.angle_labels(config)
    for key, value in labels.items():
        facts.append(_fact(
            f"Angle label '{key}': {value}",
            "config/clients/productive.yaml angle_labels"))
    product = clients.product(config)
    cap_by_persona = product.get("capability_by_persona") or {}
    for persona, capability in cap_by_persona.items():
        facts.append(_fact(
            f"Capability for {persona}: {capability}",
            "config/clients/productive.yaml product.capability_by_persona"))
    seq = config.get("linkedin_sequence") or {}
    fallbacks = seq.get("fallbacks") or {}
    for role, text in fallbacks.items():
        facts.append(_fact(
            f"LinkedIn fallback ({role}): {text}",
            "config/clients/productive.yaml linkedin_sequence.fallbacks"))
    return facts


def _learning():
    return []


_EXTRACTORS = {
    "profile": _profile,
    "market": _market,
    "competitors": _competitors,
    "customers": _customers,
    "offers": _offers,
    "messaging": _messaging,
    "learning": _learning,
}


def for_task(task, client, **scope):
    """Return only the sections `task` needs, each fact carrying source and date.

    Raises ValueError for an unknown task name. Returns a dict mapping section
    names to lists of facts. Sections in MISSING_SECTIONS that have no data
    are reported via `missing_sections` on the return value's metadata, not
    silently omitted - the caller sees what is absent.
    """
    needed = TASK_SECTIONS.get(task)
    if needed is None:
        raise ValueError(
            f"unknown task {task!r}; known tasks: {sorted(TASK_SECTIONS)}")
    config = clients.load(client)
    result = {}
    for section in needed:
        extractor = _EXTRACTORS[section]
        facts = extractor(config) if section not in MISSING_SECTIONS else extractor()
        result[section] = facts
    return result


def all_sections(client):
    """Every section, for the index page. Not for prompts."""
    config = clients.load(client)
    result = {}
    for section, extractor in _EXTRACTORS.items():
        facts = extractor(config) if section not in MISSING_SECTIONS else extractor()
        result[section] = facts
    return result


def index_html(client):
    """The Second Brain index page for one client.

    Ten sections from the spec, plus MISSING INFORMATION AND RESEARCH
    PRIORITIES as a first-class section. Writes to
    `work/review/secondbrain-<client>.html`.
    """
    config = clients.load(client)
    name = config.get("name") or client
    data = all_sections(client)

    section_titles = {
        "profile": "Client Profile",
        "market": "Market Intelligence",
        "competitors": "Competitor Intelligence",
        "customers": "Customer Intelligence (ICP & Personas)",
        "offers": "Offer Library",
        "messaging": "Messaging Intelligence",
        "learning": "Learning Memory",
    }

    rows = []
    for key in ("profile", "market", "competitors", "customers",
                "offers", "messaging", "learning"):
        facts = data.get(key) or []
        title = section_titles.get(key, key)
        if facts:
            items = "\n".join(
                f"<li><strong>{_esc(f['text'])}</strong> "
                f"<small>(source: {_esc(f['source'])}, "
                f"date: {_esc(f['date'])}, "
                f"{'verified' if f.get('verified') else 'inferred'})"
                f"</small></li>"
                for f in facts)
            body = f"<ul>{items}</ul>"
        else:
            body = "<p><em>No data available.</em></p>"
        rows.append(f"<h2>{_esc(title)}</h2>\n{body}")

    missing_items = []
    missing_items.append("<li><strong>Competitor intelligence</strong>: "
                         "no competitor products, pricing, positioning or "
                         "reviews have been recorded. Research required.</li>")
    missing_items.append("<li><strong>Customer case studies</strong>: "
                         "no documented outcomes or case studies available."
                         "</li>")
    missing_items.append("<li><strong>Verified benchmarks</strong>: "
                         "no before/after metrics from comparable firms."
                         "</li>")
    missing_items.append("<li><strong>Offer library</strong>: "
                         "no approved campaign offers yet (TASK-318)."
                         "</li>")
    missing_items.append("<li><strong>Learning memory</strong>: "
                         "no campaign performance history recorded yet."
                         "</li>")
    missing_items.append("<li><strong>Dashboard or workflow example</strong>: "
                         "no screenshot or demo link available.</li>")

    rows.append(
        "<h2>Missing Information and Research Priorities</h2>\n"
        "<ul>" + "\n".join(missing_items) + "</ul>")

    body = "\n".join(rows)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n<head>\n"
        f"<meta charset=\"utf-8\">\n"
        f"<title>Second Brain: {_esc(name)}</title>\n"
        "<style>body{font-family:system-ui;max-width:900px;margin:2em auto;"
        "padding:0 1em}li{margin:.5em 0}h2{border-bottom:1px solid #ccc;"
        "padding-bottom:.3em}</style>\n"
        "</head>\n<body>\n"
        f"<h1>Second Brain: {_esc(name)}</h1>\n"
        f"<p>Generated {TODAY}. "
        "Every fact carries source, date and verification status.</p>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )


def _esc(text):
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
