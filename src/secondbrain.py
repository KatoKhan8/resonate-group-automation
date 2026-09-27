"""The Client Second Brain as retrieval over what already exists.

This module is a RETRIEVAL LAYER, not a store. Every fact it returns comes
from `config/clients/<client>.yaml` (via `clients.load`) or from modules that
already read it (`contextpack`, `playbooks`, `strategy`). It writes no client
fact anywhere.

`for_task(task, client)` returns only the sections a given task needs. The
whole brain is never passed into a prompt: the spec forbids it and the cost
shape depends on it.

Sections map to ARCHITECTURE-UPGRADE-SPEC section 3:
    profile       A. Client Profile
    market        B. Market Intelligence
    competitors   C. Competitor Intelligence (MISSING, never invented)
    customers     D. Customer Intelligence
    offers        E. Offer Library (MISSING until TASK-318)
    messaging     F. Messaging Intelligence
    learning      G. Learning Memory

Every fact carries `source`, `date` and `verified` (True/False). A fact that
cannot answer those three questions is not returned. `verified` is False
unless a verification step has run - nothing in this module verifies, so
facts from here are unverified by default.
"""
import datetime
from types import MappingProxyType

from . import clients

TODAY = datetime.date.today().isoformat()

SECTIONS = (
    "profile", "market", "competitors", "customers",
    "offers", "messaging", "learning",
)

MISSING_SECTIONS = frozenset({"competitors", "offers", "learning"})

_TASK_SECTIONS_MAP = {
    "cold_email_writing": ("profile", "customers", "messaging", "offers"),
    "linkedin_writing": ("profile", "customers", "messaging"),
    "account_research": ("profile", "market", "customers"),
    "signal_verification": ("market", "customers"),
    "campaign_strategy": ("profile", "market", "customers", "messaging"),
}

TASK_SECTIONS = MappingProxyType(_TASK_SECTIONS_MAP)


def _source(client, key):
    """Derive the provenance string from the client actually read."""
    return f"config/clients/{client}.yaml {key}"


def _fact(text, client, key, date=None, verified=False):
    return {
        "text": text,
        "source": _source(client, key),
        "date": date or TODAY,
        "verified": verified,
    }


def _profile(config, client):
    facts = []
    product = clients.product(config)
    if product.get("name"):
        facts.append(_fact(
            f"Product: {product['name']}", client, "product.name"))
    if product.get("what_it_is"):
        facts.append(_fact(
            product["what_it_is"], client, "product.what_it_is"))
    for key, value in (product.get("capabilities") or {}).items():
        facts.append(_fact(
            f"{key}: {value}", client, "product.capabilities"))
    sender = clients.sender_identity(config)
    if sender.get("works_on"):
        facts.append(_fact(
            sender["works_on"], client, "sender.works_on"))
    if config.get("domain"):
        facts.append(_fact(
            f"Domain: {config['domain']}", client, "domain"))
    return facts


def _market(config, client):
    facts = []
    market = config.get("market") or {}
    if market.get("must"):
        facts.append(_fact(
            f"ICP must: {market['must']}", client, "market.must"))
    geos = market.get("geos") or []
    if geos:
        facts.append(_fact(
            f"Target geos: {', '.join(str(g) for g in geos)}",
            client, "market.geos"))
    exclude = market.get("exclude_geos") or []
    if exclude:
        facts.append(_fact(
            f"Excluded geos: {', '.join(str(g) for g in exclude)}",
            client, "market.exclude_geos"))
    structural = (config.get("icp") or {}).get("structural") or {}
    types = structural.get("company_types") or {}
    primary = types.get("primary") or []
    if primary:
        facts.append(_fact(
            f"Company types: {', '.join(str(t) for t in primary)}",
            client, "icp.structural.company_types.primary"))
    verticals = types.get("verticals") or []
    if verticals:
        facts.append(_fact(
            f"Verticals: {', '.join(str(v) for v in verticals[:8])}"
            + (f" (+{len(verticals) - 8} more)" if len(verticals) > 8 else ""),
            client, "icp.structural.company_types.verticals"))
    emp = (structural.get("employees") or {})
    if emp.get("min"):
        facts.append(_fact(
            f"Min employees: {emp['min']}", client,
            "icp.structural.employees.min"))
    if market.get("size_min_employees"):
        facts.append(_fact(
            f"Size min employees: {market['size_min_employees']}",
            client, "market.size_min_employees"))
    return facts


def _competitors(config, client):
    return []


def _customers(config, client):
    facts = []
    personas = clients.personas(config)
    for persona_name, persona in personas.items():
        titles = persona.get("titles") or []
        if titles:
            facts.append(_fact(
                f"Persona '{persona_name}' titles: "
                f"{', '.join(str(t) for t in titles[:6])}"
                + (f" (+{len(titles) - 6} more)" if len(titles) > 6 else ""),
                client, f"personas.{persona_name}.titles"))
        angles = persona.get("angles") or {}
        for angle_key, angle_text in angles.items():
            facts.append(_fact(
                f"Persona '{persona_name}', angle '{angle_key}': {angle_text}",
                client,
                f"personas.{persona_name}.angles.{angle_key}"))
        cap = persona.get("cap_per_domain")
        if cap is not None:
            facts.append(_fact(
                f"Persona '{persona_name}' cap per domain: {cap}",
                client, f"personas.{persona_name}.cap_per_domain"))
    return facts


def _offers(config, client):
    return []


def _messaging(config, client):
    facts = []
    tone = config.get("tone") or {}
    for channel in ("email", "linkedin"):
        if tone.get(channel):
            facts.append(_fact(
                f"Tone ({channel}): {tone[channel]}",
                client, f"tone.{channel}"))
    labels = clients.angle_labels(config)
    for key, value in labels.items():
        facts.append(_fact(
            f"Angle label '{key}': {value}", client, "angle_labels"))
    raw_product = (config or {}).get("product") or {}
    cap_by_persona = raw_product.get("capability_by_persona") or {}
    for persona, capability in cap_by_persona.items():
        caps = capability if isinstance(capability, list) else [capability]
        for cap in caps:
            facts.append(_fact(
                f"Capability for {persona}: {cap}",
                client, "product.capability_by_persona"))
    seq = config.get("linkedin_sequence") or {}
    fallbacks = seq.get("fallbacks") or {}
    for role, text in fallbacks.items():
        facts.append(_fact(
            f"LinkedIn fallback ({role}): {text}",
            client, "linkedin_sequence.fallbacks"))
    return facts


def _learning(config, client):
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


def for_task(task, client):
    """Return only the sections `task` needs, each fact carrying source and date.

    Raises ValueError for an unknown task name. Returns a dict mapping section
    names to lists of facts. Every fact's `source` reflects the client config
    file actually read. Facts are unverified (`verified=False`) unless a
    verification step has run - this module performs no verification.
    """
    needed = TASK_SECTIONS.get(task)
    if needed is None:
        raise ValueError(
            f"unknown task {task!r}; known tasks: {sorted(TASK_SECTIONS)}")
    config = clients.load(client)
    result = {}
    for section in needed:
        extractor = _EXTRACTORS[section]
        result[section] = extractor(config, client)
    return result


def all_sections(client, *, reason):
    """Every section, for the index page.

    Requires an explicit `reason` keyword argument to make casual use visible.
    The whole brain is not for prompts - this gate ensures every caller
    declares why it needs the undifferentiated dump.
    """
    if not reason or not str(reason).strip():
        raise ValueError("all_sections requires a non-empty reason= argument")
    config = clients.load(client)
    result = {}
    for section, extractor in _EXTRACTORS.items():
        result[section] = extractor(config, client)
    return result


def index_html(client):
    """The Second Brain index page for one client.

    Returns the HTML as a string. The caller is responsible for writing it
    to disk.
    """
    config = clients.load(client)
    name = config.get("name") or client
    data = all_sections(client, reason="index page generation")

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
                f"{'verified' if f.get('verified') else 'unverified'})"
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


# --------------------------------------------------------- account scope
#
# TASK-326: retrieval is account-scoped. Company research is done once per
# account and reused across its buying committee. Person relevance is a
# lighter layer on top - it shapes interpretation, never the evidence.

_ROLE_ANGLES = {
    "ceo": (
        "business impact",
        "growth, margin, visibility and strategic outcome"),
    "founder": (
        "business impact",
        "growth, margin, visibility and strategic outcome"),
    "coo": (
        "operational control",
        "delivery, resourcing, utilisation and operational control"),
    "head_of_delivery": (
        "project delivery",
        "projects, capacity, budgets and workflow"),
    "project_manager": (
        "project delivery",
        "projects, capacity, budgets and workflow"),
}

_DEFAULT_ANGLE = (
    "general business",
    "general business outcomes")

_account_cache = {}


def _load_account_evidence(domain, client=None):
    """Load company-level evidence for a domain.

    Reads the client config's ICP structure to produce facts about what kind
    of company this domain is being evaluated against. Each fact carries
    source and date per TASK-322's contract.

    The `client` parameter is accepted for interface compatibility but the
    evidence is keyed on `domain` - the prospect's company, not the client.
    """
    config = clients.load(client) if client else {}
    facts = []
    icp = (config.get("icp") or {}).get("structural") or {}
    market = config.get("market") or {}

    company_types = (icp.get("company_types") or {}).get("primary") or []
    if company_types:
        facts.append({
            "text": f"ICP company types: {', '.join(str(t) for t in company_types)}",
            "source": f"config/clients/{client}.yaml icp.structural.company_types.primary",
            "date": TODAY,
            "verified": False,
        })

    verticals = (icp.get("company_types") or {}).get("verticals") or []
    if verticals:
        shown = verticals[:8]
        more = f" (+{len(verticals) - 8} more)" if len(verticals) > 8 else ""
        facts.append({
            "text": f"ICP verticals: {', '.join(str(v) for v in shown)}{more}",
            "source": f"config/clients/{client}.yaml icp.structural.company_types.verticals",
            "date": TODAY,
            "verified": False,
        })

    emp = icp.get("employees") or {}
    if emp.get("min") or emp.get("max"):
        parts = []
        if emp.get("min"):
            parts.append(f"min {emp['min']}")
        if emp.get("max"):
            parts.append(f"max {emp['max']}")
        facts.append({
            "text": f"ICP employee range: {', '.join(parts)}",
            "source": f"config/clients/{client}.yaml icp.structural.employees",
            "date": TODAY,
            "verified": False,
        })

    if market.get("size_min_employees"):
        facts.append({
            "text": f"Min company size: {market['size_min_employees']} employees",
            "source": f"config/clients/{client}.yaml market.size_min_employees",
            "date": TODAY,
            "verified": False,
        })

    geos = market.get("geos") or []
    if geos:
        facts.append({
            "text": f"Target geos: {', '.join(str(g) for g in geos[:8])}"
                   + (f" (+{len(geos) - 8} more)" if len(geos) > 8 else ""),
            "source": f"config/clients/{client}.yaml market.geos",
            "date": TODAY,
            "verified": False,
        })

    return {
        "domain": domain,
        "account_ref": f"account:{domain}",
        "facts": facts,
    }


def _get_account_evidence(client, domain):
    """Return cached account evidence, loading on first call per domain."""
    if domain not in _account_cache:
        _account_cache[domain] = _load_account_evidence(domain, client=client)
    return _account_cache[domain]


def for_account(client, domain):
    """Company-level evidence for a prospect domain.

    Returns the company-level evidence once, each fact carrying `source` and
    `date` per TASK-322's contract. The result is cached so that multiple
    `for_contact` calls for the same domain share one load.

    Retrieval is READ-ONLY: no file is written under config/ or work/.
    """
    evidence = _get_account_evidence(client, domain)
    return {
        "domain": domain,
        "client": client,
        "account_ref": evidence["account_ref"],
        "facts": list(evidence["facts"]),
    }


def for_contact(client, domain, contact_key, role):
    """Person-level layer for one contact at the account.

    Returns ONLY the person layer and a reference to the account evidence -
    not a copy of it. The account evidence is resolved once and shared across
    all contacts at the same domain.

    Role shapes interpretation (the `angle`), never the evidence itself.
    """
    evidence = _get_account_evidence(client, domain)
    angle_key, angle_description = _ROLE_ANGLES.get(
        role, _DEFAULT_ANGLE)
    return {
        "contact_key": contact_key,
        "role": role,
        "angle": angle_key,
        "angle_description": angle_description,
        "account_ref": evidence["account_ref"],
        "facts": [],
    }
