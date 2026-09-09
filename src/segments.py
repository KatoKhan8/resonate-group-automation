#!/usr/bin/env python3
"""What kind of company this is, decided from evidence and never from a guess.

Classification here is deterministic keyword matching over the company facts
and retained evidence. That is a deliberate choice over asking a model: the
same company must land in the same segment every time, a reviewer has to be
able to see *why*, and a segment that shifts between runs makes every campaign
comparison meaningless.

The rule that matters more than the taxonomy: **UNKNOWN is a real answer**. A
company we cannot place is not "Other Agency" - it is unclassified, it says so,
and it goes to review rather than into a campaign. Forcing a subvertical from
thin evidence is how a software agency ends up receiving copy about creative
retainers.

  python -m src.segments --domain acme.test --describe
"""
import argparse
import json
import re

from . import geo

UNKNOWN = "UNKNOWN"

# ------------------------------------------------------------- verticals
#
# The Productive-facing taxonomy. Every vertical here is a business that sells
# people's time against client projects, except the last two, which exist so
# that "not our market" is a stateable answer rather than an absence.

DIGITAL_MARKETING = "Digital Marketing Agency"
PERFORMANCE_MARKETING = "Performance Marketing Agency"
CREATIVE = "Creative / Branding Agency"
SEO = "SEO Agency"
PR = "PR / Communications Agency"
SOFTWARE_DEV = "Software Development Agency"
PRODUCT_DEV = "Product Development Agency"
DESIGN_UX = "Design / UX Agency"
CONSULTING = "Consulting"
PROFESSIONAL_SERVICES = "Professional Services"
ARCHITECTURE_ENGINEERING = "Architecture / Engineering"
OTHER_AGENCY = "Other Agency"
OTHER_PROFESSIONAL = "Other Professional Services"
NON_ICP = "Non ICP / Other"

VERTICALS = (DIGITAL_MARKETING, PERFORMANCE_MARKETING, CREATIVE, SEO, PR,
             SOFTWARE_DEV, PRODUCT_DEV, DESIGN_UX, CONSULTING,
             PROFESSIONAL_SERVICES, ARCHITECTURE_ENGINEERING, OTHER_AGENCY,
             OTHER_PROFESSIONAL, NON_ICP)

# Verticals that sell project delivery, which is what Productive is for.
# What kind of business a vertical is, which is the only thing `icp` needs to
# know about one in order to score it.
AGENCY_KIND = "agency"
SERVICE_KIND = "service"
NON_ICP_KIND = "non_icp"
VERTICAL_KINDS = (AGENCY_KIND, SERVICE_KIND, NON_ICP_KIND)

AGENCY_VERTICALS = (DIGITAL_MARKETING, PERFORMANCE_MARKETING, CREATIVE, SEO,
                    PR, SOFTWARE_DEV, PRODUCT_DEV, DESIGN_UX, OTHER_AGENCY)
SERVICE_VERTICALS = AGENCY_VERTICALS + (CONSULTING, PROFESSIONAL_SERVICES,
                                        ARCHITECTURE_ENGINEERING,
                                        OTHER_PROFESSIONAL)

# Ordered: the first vertical whose evidence is strongest wins, and ties are
# broken by this order so the answer is stable across runs.
VERTICAL_SIGNALS = (
    (SEO, ("seo", "search engine optimisation", "search engine optimization",
           "organic search", "link building", "technical seo")),
    (PERFORMANCE_MARKETING, ("performance marketing", "paid media", "ppc",
                             "paid search", "paid social", "google ads",
                             "media buying", "demand generation")),
    (PR, ("public relations", "communications agency", "press office",
          "media relations", "corporate communications")),
    (DESIGN_UX, ("ux", "user experience", "ui design", "product design",
                 "design studio", "interaction design", "usability")),
    (SOFTWARE_DEV, ("software development", "software house", "web development",
                    "custom software", "app development", "mobile development",
                    "development agency", "engineering services", "devops")),
    (PRODUCT_DEV, ("product development", "product studio", "product agency",
                   "mvp development", "digital product")),
    (CREATIVE, ("branding", "brand strategy", "creative agency", "advertising",
                "creative studio", "campaign creative", "art direction")),
    (DIGITAL_MARKETING, ("digital marketing", "marketing agency",
                         "content marketing", "social media marketing",
                         "email marketing", "inbound marketing", "growth agency")),
    (ARCHITECTURE_ENGINEERING, ("architecture", "architects", "civil engineering",
                                "structural engineering", "surveying",
                                "engineering consultancy")),
    (CONSULTING, ("consultancy", "consulting", "advisory", "management consulting",
                  "strategy consulting", "business transformation")),
    (PROFESSIONAL_SERVICES, ("professional services", "accountancy",
                             "accounting firm", "law firm", "legal services",
                             "recruitment agency", "staffing")),
)

# Anything that is emphatically not a project-delivery business. Checked
# first, because a SaaS company that also says "consulting" is still SaaS.
NON_ICP_SIGNALS = (
    ("saas", ("saas", "software as a service", "our platform", "subscription "
              "software", "free trial", "per seat", "pricing plans",
              "product-led")),
    ("ecommerce", ("ecommerce store", "online store", "online retailer",
                   "shop now", "free shipping", "add to cart", "our products",
                   "d2c brand", "dtc brand")),
    ("manufacturing", ("manufacturer", "manufacturing", "factory", "production "
                       "facility", "wholesale")),
    ("holding", ("holding company", "investment holding", "family office",
                 "venture capital", "private equity", "investment firm")),
    ("marketplace", ("marketplace", "book a driver", "listings platform")),
    ("education", ("university", "school", "college", "bootcamp")),
    ("nonprofit", ("charity", "nonprofit", "non-profit", "ngo")),
)

# ---------------------------------------------------------- business model

AGENCY = "agency"
CONSULTANCY = "consultancy"
PRODUCT = "product"
ECOMMERCE = "ecommerce"
HYBRID = "hybrid"
NOT_A_BUSINESS = "other"
BUSINESS_MODELS = (AGENCY, CONSULTANCY, PRODUCT, ECOMMERCE, HYBRID,
                   NOT_A_BUSINESS, UNKNOWN)

# ------------------------------------------------------------ size bands
#
# Bands rather than a number because the number is usually a provider's
# estimate, and campaigns are planned in bands anyway. The keys double as
# segment-key fragments, so they are stable strings rather than tuples.

# Eight bands rather than six. `50_199` and `500_PLUS` each spanned a real
# change in who owns resourcing - a 60-person agency and a 190-person agency
# are routed to different people - and a band that contains both cannot express
# that. The split is why `band_order` exists rather than an inequality on the
# raw headcount: everything downstream compares bands, so widening or narrowing
# one is a config change rather than a code change.
DEFAULT_BANDS = (
    ("1_9", 1, 9),
    ("10_19", 10, 19),
    ("20_49", 20, 49),
    ("50_99", 50, 99),
    ("100_199", 100, 199),
    ("200_499", 200, 499),
    ("500_999", 500, 999),
    ("1000_PLUS", 1000, None),
)
BANDS = DEFAULT_BANDS
BAND_NAMES = tuple(name for name, _, _ in BANDS) + (UNKNOWN,)


def bands(config=None):
    """The band table for this client, validated.

    A client may redraw the boundaries - a client selling to enterprises only
    has no use for four bands under fifty - but the bands must stay ordered,
    contiguous and open-ended at the top, because `band_order` is what every
    merge and routing decision compares. A malformed table raises rather than
    being silently repaired: a band table that is quietly wrong misroutes every
    company in the batch and looks like nothing happened.
    """
    block = ((config or {}).get("segmentation") or {}).get("employee_bands")
    if not block:
        return DEFAULT_BANDS
    table = []
    for row in block:
        try:
            name, low, high = row["name"], int(row["min"]), row.get("max")
            high = None if high in (None, "", "+") else int(high)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"employee_bands: malformed band {row!r}: {e}")
        table.append((str(name), low, high))
    if not table:
        return DEFAULT_BANDS
    table.sort(key=lambda r: r[1])
    for i, (name, low, high) in enumerate(table):
        if low < 1:
            raise ValueError(f"employee_bands: {name} starts below 1")
        if high is not None and high < low:
            raise ValueError(f"employee_bands: {name} ends before it starts")
        if i and table[i - 1][2] is None:
            raise ValueError("employee_bands: only the last band may be open")
        if i and table[i - 1][2] + 1 != low:
            raise ValueError(f"employee_bands: gap or overlap before {name}")
    if table[-1][2] is not None:
        raise ValueError("employee_bands: the last band must be open-ended")
    return tuple(table)

# ------------------------------------------------------------- maturity

STARTUP = "startup"
GROWING = "growing"
ESTABLISHED = "established"
MATURE = "mature"
MATURITIES = (STARTUP, GROWING, ESTABLISHED, MATURE, UNKNOWN)

# --------------------------------------------------------- delivery model

PROJECT = "project"
RETAINER = "retainer"
MIXED = "mixed"
STAFF_AUG = "staff_augmentation"
DELIVERY_MODELS = (PROJECT, RETAINER, MIXED, STAFF_AUG, UNKNOWN)

DELIVERY_SIGNALS = (
    (RETAINER, ("retainer", "monthly retainer", "ongoing support",
                "managed service")),
    (STAFF_AUG, ("staff augmentation", "dedicated team", "team extension",
                 "outstaffing", "hire developers")),
    (PROJECT, ("fixed price", "project based", "per project", "scope of work",
               "statement of work", "sprint")),
)


def settings(config):
    """Client-tunable pieces of the taxonomy.

    A client may *add* a vertical of its own; it may not rename one of these,
    because a renamed vertical silently orphans every existing campaign
    segment that used the old name. Adding renames nothing, and without it
    this taxonomy is Productive's market and no one else's - fourteen
    categories of agency and professional services, with `extra_keywords`
    letting a client add words to somebody else's vertical and never declare
    their own. A client selling to dental practices or manufacturers had no
    expressible vertical at all, so every company they uploaded scored
    UNKNOWN and the whole ICP model sat idle.

    A declared vertical says what kind of business it is, because that is what
    `icp` needs in order to score it:

        segmentation:
          verticals:
            Dental Clinic:
              keywords: [dentist, dental practice, orthodontist]
              kind: service        # agency | service | non_icp

    `agency` and `service` correspond to the two existing groupings and carry
    their weights; `non_icp` declares a business this client does not sell to,
    which is how a client says "manufacturers are not my market" without
    editing this file.
    """
    block = ((config or {}).get("segmentation") or {})
    merged = {
        # How many distinct keyword hits before a vertical is claimed rather
        # than left UNKNOWN. Two by default: one word is a coincidence.
        "min_signals": 2,
        # A single very strong phrase is enough on its own.
        "strong_phrase_is_enough": True,
        "extra_keywords": {},
    }
    try:
        merged["min_signals"] = max(1, int(block.get("min_signals",
                                                     merged["min_signals"])))
    except (TypeError, ValueError):
        pass
    if block.get("strong_phrase_is_enough") is False:
        merged["strong_phrase_is_enough"] = False
    extra = block.get("extra_keywords")
    if isinstance(extra, dict):
        merged["extra_keywords"] = {
            name: [str(w).lower() for w in words]
            for name, words in extra.items()
            if name in VERTICALS and isinstance(words, list)}

    declared = {}
    for name, spec in (block.get("verticals") or {}).items():
        name = str(name).strip()
        if not name or name in VERTICALS:
            continue                       # never redefines a built-in
        if isinstance(spec, dict):
            words = spec.get("keywords") or []
            kind = str(spec.get("kind") or SERVICE_KIND).strip().lower()
        else:
            words, kind = spec, SERVICE_KIND
        words = [str(w).lower().strip() for w in (words or [])
                 if str(w).strip()]
        if not words or kind not in VERTICAL_KINDS:
            continue                       # an unusable declaration is ignored
        declared[name] = {"keywords": words, "kind": kind}
    merged["verticals"] = declared
    return merged


def vertical_signals(config=None):
    """The taxonomy this client actually classifies against.

    The built-ins first, in their existing order, so a client's own vertical
    never silently outranks one of them on a tie.
    """
    declared = settings(config)["verticals"]
    return list(VERTICAL_SIGNALS) + [(name, spec["keywords"])
                                     for name, spec in declared.items()]


def kind_of(vertical, config=None):
    """`agency`, `service`, `non_icp`, or None for a vertical we cannot place.

    Asked instead of testing membership of `AGENCY_VERTICALS` directly, so a
    client-declared vertical is scored rather than falling through as
    unrecognised.
    """
    if vertical in AGENCY_VERTICALS:
        return AGENCY_KIND
    if vertical in SERVICE_VERTICALS:
        return SERVICE_KIND
    declared = settings(config)["verticals"].get(vertical)
    return declared["kind"] if declared else None


# --------------------------------------------------------------- the text

def text_of(rec):
    """Everything we may classify from, as one lower-case string.

    Only trimmed facts and retained evidence - never a raw provider payload,
    and never the email copy, which would let a message we wrote classify the
    company we wrote it about.
    """
    facts = (rec or {}).get("company_facts") or {}
    parts = [str(rec.get("company") or ""), str(rec.get("hook") or ""),
             str(facts.get("industry") or ""), str(facts.get("description") or ""),
             str(facts.get("tagline") or "")]
    parts.extend(str(s) for s in (facts.get("specialties") or []))
    parts.extend(str(s) for s in (facts.get("services") or []))
    for item in (rec.get("research") or []):
        parts.append(str(item.get("fact") or ""))
    return " ".join(parts).lower()


def _hits(text, words):
    """Whole-phrase matches, so "seo" never matches "seoul"."""
    found = []
    for word in words:
        if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text):
            found.append(word)
    return found


# ---------------------------------------------------------- the decisions

def employee_band(employees, config=None):
    if not isinstance(employees, int) or employees <= 0:
        return UNKNOWN
    for name, low, high in bands(config):
        if employees >= low and (high is None or employees <= high):
            return name
    return UNKNOWN


def band_order(name, config=None):
    """For sorting and for merging a small segment upward.

    An unknown band sorts last rather than raising: `UNKNOWN` is a real answer
    here, and a company we cannot size must not sort as though it were tiny.
    """
    names = [n for n, _, _ in bands(config)]
    return names.index(name) if name in names else len(names)


def maturity(rec):
    facts = (rec or {}).get("company_facts") or {}
    founded = facts.get("founded")
    employees = facts.get("employees")
    if isinstance(founded, int) and founded > 1900:
        age = 2026 - founded
        if age <= 3:
            return STARTUP
        if age <= 8:
            return GROWING
        if age <= 20:
            return ESTABLISHED
        return MATURE
    # Size is a weaker proxy and is only used where the age is missing.
    if isinstance(employees, int):
        if employees >= 200:
            return MATURE
        if employees >= 50:
            return ESTABLISHED
    return UNKNOWN


def delivery_model(text, config=None):
    scores = {}
    for name, words in DELIVERY_SIGNALS:
        found = _hits(text, words)
        if found:
            scores[name] = len(found)
    if not scores:
        return UNKNOWN, []
    if len(scores) > 1 and sorted(scores.values())[-1] == sorted(scores.values())[-2]:
        return MIXED, sorted(scores)
    best = max(scores, key=lambda k: (scores[k], -list(scores).index(k)))
    return best, [best]


def business_model(text, vertical):
    """What the company sells. Derived from the vertical where it is clear."""
    product = _hits(text, dict(NON_ICP_SIGNALS)["saas"])
    shop = _hits(text, dict(NON_ICP_SIGNALS)["ecommerce"])
    if vertical in AGENCY_VERTICALS:
        return HYBRID if product else AGENCY
    if vertical in (CONSULTING,):
        return CONSULTANCY
    if vertical in (PROFESSIONAL_SERVICES, ARCHITECTURE_ENGINEERING,
                    OTHER_PROFESSIONAL):
        return CONSULTANCY
    if shop:
        return ECOMMERCE
    if product:
        return PRODUCT
    return UNKNOWN


def classify_vertical(rec, config=None):
    """The vertical, the evidence for it, and an honest UNKNOWN.

    Non-ICP signals are checked first: a SaaS company that also mentions
    "consulting" is a SaaS company, and reading it the other way round is how
    a product business ends up in an agency campaign.
    """
    policy = settings(config)
    text = text_of(rec)
    if not text.strip():
        return {"vertical": UNKNOWN, "subvertical": UNKNOWN, "matched": [],
                "why": "no company text to classify from",
                "non_icp_signals": []}

    non_icp = []
    for name, words in NON_ICP_SIGNALS:
        found = _hits(text, words)
        if found:
            non_icp.append({"kind": name, "matched": found})

    scored = []
    for vertical, words in vertical_signals(config):
        words = list(words) + policy["extra_keywords"].get(vertical, [])
        found = _hits(text, words)
        if found:
            scored.append((vertical, found))

    # A strong non-ICP signal with no service evidence at all is decisive.
    if non_icp and not scored:
        return {"vertical": NON_ICP, "subvertical": UNKNOWN,
                "matched": [w for s in non_icp for w in s["matched"]],
                "why": f"{non_icp[0]['kind']} signals and no service evidence",
                "non_icp_signals": non_icp}

    if not scored:
        return {"vertical": UNKNOWN, "subvertical": UNKNOWN, "matched": [],
                "why": "nothing in the company text matches a known vertical",
                "non_icp_signals": non_icp}

    # Ties break on declaration order, over the same list that was searched -
    # built-ins first, so a client's own vertical never silently outranks one
    # of them on equal evidence.
    order = [v for v, _ in vertical_signals(config)]
    scored.sort(key=lambda pair: (-len(pair[1]), order.index(pair[0])))
    best, matched = scored[0]

    enough = (len(matched) >= policy["min_signals"]
              or (policy["strong_phrase_is_enough"]
                  and any(" " in word for word in matched)))
    if not enough:
        # One weak keyword is a coincidence. Say so rather than commit.
        return {"vertical": UNKNOWN, "subvertical": UNKNOWN,
                "matched": matched,
                "why": (f"only {len(matched)} weak signal(s) for {best}: not "
                        "enough to classify"),
                "non_icp_signals": non_icp}

    # The subvertical is the runner-up only when it is genuinely supported.
    subvertical = UNKNOWN
    if len(scored) > 1 and len(scored[1][1]) >= policy["min_signals"]:
        subvertical = scored[1][0]

    return {
        "vertical": best,
        "subvertical": subvertical,
        "matched": matched,
        "why": f"{len(matched)} signal(s) for {best}: {', '.join(matched[:4])}",
        "non_icp_signals": non_icp,
    }


def classify(rec, config=None):
    """Every segmentation dimension for one company."""
    facts = (rec or {}).get("company_facts") or {}
    text = text_of(rec)
    vertical = classify_vertical(rec, config)
    location = geo.from_record(rec, config)
    model, delivery_matched = delivery_model(text, config)
    offices = facts.get("offices") or []

    return {
        "vertical": vertical["vertical"],
        "subvertical": vertical["subvertical"],
        "vertical_why": vertical["why"],
        "vertical_matched": vertical["matched"],
        "non_icp_signals": vertical["non_icp_signals"],
        "industry": facts.get("industry") or UNKNOWN,
        "business_model": business_model(text, vertical["vertical"]),
        "employees": facts.get("employees"),
        "employee_band": employee_band(facts.get("employees"), config),
        "company_maturity": maturity(rec),
        "delivery_model": model,
        "delivery_matched": delivery_matched,
        "office_count": len(offices) or None,
        "distributed": len(offices) > 1 if offices else None,
        "country": location["country"],
        "country_code": location["country_code"],
        "region": location["region"],
        "region_confidence": location["region_confidence"],
        "city": location["city"],
        "timezone": location["timezone"],
        "timezone_source": location["timezone_source"],
        "timezone_confidence": location["timezone_confidence"],
        "location_why": location["why"],
    }


def is_service_business(segment):
    return segment.get("vertical") in SERVICE_VERTICALS


def distribution(segments, field):
    """How a batch is spread across one dimension, for the preview."""
    counts = {}
    for segment in segments:
        value = segment.get(field) or UNKNOWN
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain")
    p.add_argument("--describe", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.describe or not a.domain:
        described = {
            "verticals": list(VERTICALS),
            "agency_verticals": list(AGENCY_VERTICALS),
            "business_models": list(BUSINESS_MODELS),
            "employee_bands": list(BAND_NAMES),
            "maturities": list(MATURITIES),
            "delivery_models": list(DELIVERY_MODELS),
            "regions": list(geo.REGIONS),
        }
        print(json.dumps(described, indent=2))
        return 0

    from . import store
    rec = store.get(a.domain) or next(
        (r for r in store.load() if r.get("domain") == a.domain), None)
    if rec is None:
        print(f"REFUSED: no record for {a.domain}")
        return 2
    result = classify(rec)
    print(json.dumps(result, indent=2) if a.json else
          "\n".join(f"  {k:<22} {v}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
