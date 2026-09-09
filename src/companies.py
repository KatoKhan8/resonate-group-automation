#!/usr/bin/env python3
"""A deterministic 5,000-company universe that looks like a real upload.

`src/synthetic.py` builds records that are broken in named ways, to test the
contact-level gates. This builds the other half: companies that are *plausible*
rather than defective, in the mix an actual domain list arrives in - good
agencies, borderline ones, software shops, consultancies, and the SaaS and
ecommerce companies that always get scraped in alongside them.

Nothing is random. The archetype is chosen by `index % len(ARCHETYPES)` and
every varying field is derived from the index, so company 4,312 is the same
company on every machine and a failing test names an archetype instead of a
seed.

  python -m src.companies --size 5000 --describe
  python -m src.companies --size 5000 --write
"""
import argparse
import json

from . import evidence, store

TODAY = "2026-08-26"

# Countries in the mix, with the state where one is needed to be schedulable.
PLACES = (
    ("United Kingdom", None, "London"),
    ("United Kingdom", None, "Manchester"),
    ("Ireland", None, "Dublin"),
    ("Germany", None, "Berlin"),
    ("Germany", None, "Munich"),
    ("Austria", None, "Vienna"),
    ("Switzerland", None, "Zurich"),
    ("Sweden", None, "Stockholm"),
    ("Norway", None, "Oslo"),
    ("Denmark", None, "Copenhagen"),
    ("Netherlands", None, "Amsterdam"),
    ("Belgium", None, "Brussels"),
    ("Poland", None, "Warsaw"),
    ("Croatia", None, "Zagreb"),
    ("Czech Republic", None, "Prague"),
    ("Spain", None, "Madrid"),
    ("Italy", None, "Milan"),
    ("France", None, "Paris"),
    ("United States", "New York", "New York"),
    ("United States", "California", "San Francisco"),
    ("United States", "Illinois", "Chicago"),
    ("United States", "Texas", "Austin"),
    # A US company with no state and no recognised city: unschedulable, on
    # purpose, because a real list is full of them.
    ("United States", None, None),
    ("Canada", None, "Toronto"),
    ("Australia", None, "Sydney"),
    ("Australia", None, None),           # spans zones, nothing narrows it
    ("New Zealand", None, "Auckland"),
)

# (name, industry, specialties, description, employees, evidence)
#
# The descriptions are what a company says about itself, because that is what
# the classifier reads. The operational language in the good ones is the
# difference between a company that scores and one that does not - and that is
# the point: the model should reward companies that talk about delivery.
ARCHETYPES = (
    ("strong_digital_agency", {
        "industry": "Marketing and Advertising",
        "specialties": ["digital marketing", "content marketing",
                        "social media marketing"],
        "description": ("We run delivery teams across multiple clients on both "
                        "retainer and project work. Resource planning, "
                        "utilisation and project margin are how we run the "
                        "studio."),
        "employees": 90,
        "offices": 2,
        "evidence": ("is hiring a delivery manager to improve utilisation "
                     "across the team", "careers_page", 6),
    }),
    ("strong_software_agency", {
        "industry": "Software Development",
        "specialties": ["software development", "custom software",
                        "web development"],
        "description": ("Fixed price and sprint based delivery for concurrent "
                        "projects. Our delivery teams handle capacity planning "
                        "and resourcing across several practice areas."),
        "employees": 140,
        "offices": 2,
        "evidence": ("opened a second engineering office and is moving four "
                     "delivery leads there", "company_announcement", 12),
    }),
    ("mid_creative_agency", {
        "industry": "Design",
        "specialties": ["branding", "brand strategy", "creative studio"],
        "description": ("A creative studio running project based work for "
                        "brands, with producers and account managers across "
                        "disciplines."),
        "employees": 55,
        "offices": 1,
        "evidence": ("is hiring a studio producer to manage concurrent "
                     "projects", "careers_page", 20),
    }),
    ("small_seo_agency", {
        "industry": "Marketing",
        "specialties": ["seo", "technical seo", "link building"],
        "description": ("Organic search and technical seo on monthly retainer "
                        "for a client portfolio."),
        "employees": 22,
        "offices": 1,
        "evidence": ("published a note on billable time across its retainer "
                     "clients", "company_blog", 40),
    }),
    ("large_consultancy", {
        "industry": "Management Consulting",
        "specialties": ["management consulting", "advisory",
                        "business transformation"],
        "description": ("Practice areas delivering concurrent projects, with "
                        "utilisation and profitability reported per "
                        "engagement."),
        "employees": 320,
        "offices": 4,
        "evidence": ("reported growth across its practice areas",
                     "press_release", 30),
    }),
    ("borderline_agency", {
        "industry": "Marketing",
        "specialties": ["digital marketing"],
        "description": "A marketing agency.",
        "employees": 35,
        "offices": 1,
        "evidence": None,
    }),
    ("performance_agency", {
        "industry": "Advertising",
        "specialties": ["performance marketing", "paid media", "ppc"],
        "description": ("Paid media and performance marketing with budget "
                        "control and margin reporting per client."),
        "employees": 48,
        "offices": 1,
        "evidence": ("is hiring a paid media lead", "careers_page", 15),
    }),
    ("design_ux_studio", {
        "industry": "Design",
        "specialties": ["ux", "product design", "user experience"],
        "description": ("Product design and user experience work delivered "
                        "per project with a small delivery team."),
        "employees": 18,
        "offices": 1,
        "evidence": None,
    }),
    ("architecture_practice", {
        "industry": "Architecture",
        "specialties": ["architecture", "structural engineering"],
        "description": ("An architecture practice running project based work "
                        "with budget tracking across concurrent projects."),
        "employees": 65,
        "offices": 2,
        "evidence": ("won a mixed use development", "news_article", 25),
    }),
    ("pr_agency", {
        "industry": "Public Relations",
        "specialties": ["public relations", "media relations"],
        "description": ("Corporate communications on retainer, with timesheets "
                        "and billable time across a client portfolio."),
        "employees": 30,
        "offices": 1,
        "evidence": None,
    }),
    ("staff_aug_shop", {
        "industry": "Software Development",
        "specialties": ["software development", "team extension"],
        "description": ("Dedicated team and staff augmentation for product "
                        "companies. We hire developers and place them."),
        "employees": 210,
        "offices": 3,
        "evidence": None,
    }),
    ("tiny_studio", {
        "industry": "Design",
        "specialties": ["branding", "creative studio"],
        "description": "A small branding studio.",
        "employees": 4,
        "offices": 1,
        "evidence": None,
    }),
    ("saas_product", {
        "industry": "Software",
        "specialties": [],
        "description": ("Our platform is software as a service. Pricing plans, "
                        "a free trial, and a product-led motion."),
        "employees": 120,
        "offices": 1,
        "evidence": None,
    }),
    ("ecommerce_retailer", {
        "industry": "Retail",
        "specialties": [],
        "description": ("Our online store sells direct to consumer. Free "
                        "shipping, add to cart, and our products ship "
                        "worldwide."),
        "employees": 60,
        "offices": 1,
        "evidence": None,
    }),
    ("holding_company", {
        "industry": "Financial Services",
        "specialties": [],
        "description": "An investment holding company and family office.",
        "employees": 8,
        "offices": 1,
        "evidence": None,
    }),
    ("manufacturer", {
        "industry": "Manufacturing",
        "specialties": [],
        "description": "A manufacturer with a production facility and wholesale.",
        "employees": 400,
        "offices": 2,
        "evidence": None,
    }),
    ("enterprise_services", {
        "industry": "Professional Services",
        "specialties": ["professional services", "accountancy"],
        "description": ("Accountancy and advisory across offices, with "
                        "chargeable time and utilisation reported monthly."),
        "employees": 900,
        "offices": 6,
        "evidence": ("announced a merger", "press_release", 50),
    }),
    ("unknown_thin", {
        "industry": None,
        "specialties": [],
        "description": "",
        "employees": None,
        "offices": 0,
        "evidence": None,
    }),
    ("unknown_named_only", {
        "industry": "Services",
        "specialties": [],
        "description": "We help businesses grow.",
        "employees": None,
        "offices": 0,
        "evidence": None,
    }),
    ("hybrid_agency_product", {
        "industry": "Software Development",
        "specialties": ["software development", "product development"],
        "description": ("We build custom software for clients and also sell "
                        "our platform as a service with pricing plans."),
        "employees": 75,
        "offices": 1,
        "evidence": ("is hiring a delivery lead", "careers_page", 10),
    }),
    # Facts that cannot all be true: four offices for three people, a provider
    # headcount an order of magnitude off the stated one, and a founding year
    # in the future. Every one of these is something a real provider record
    # does, and each trips a different detector in `icp.contradictions`.
    ("contradictory_evidence", {
        "industry": "Marketing and Advertising",
        "specialties": ["digital marketing", "content marketing"],
        "description": ("We run delivery teams across multiple clients on "
                        "retainer and project work, with resource planning "
                        "and utilisation tracked across the studio."),
        # `_vary` moves the headcount by up to six either way, so the office
        # count has to sit above the top of that range for the contradiction to
        # be reliable rather than occasional. Twelve offices for a handful of
        # people is exactly the shape of a bad provider record.
        "employees": 3,
        "offices": 12,
        "evidence": ("lists a dozen offices", "news", 30),
        "headcount_signal": 400,
        "founded": 3041,
    }),
)

ARCHETYPE_NAMES = tuple(name for name, _ in ARCHETYPES)

# Suffixes, so 5,000 companies do not all share four names.
SUFFIXES = ("Studio", "Group", "Partners", "Collective", "Works", "Labs",
            "Agency", "Co", "Digital", "Consulting")


def _vary(value, index, spread):
    """Deterministic variation around a base, so bands are not all identical."""
    if value is None:
        return None
    offset = (index * 37) % (spread * 2 + 1) - spread
    return max(1, value + offset)


def record(index, config=None, client="benchmark", batch=None, today=TODAY):
    """One plausible company. The archetype decides what kind."""
    name, spec = ARCHETYPES[index % len(ARCHETYPES)]
    rid = f"co{index:05d}"
    country, state, city = PLACES[index % len(PLACES)]
    suffix = SUFFIXES[(index // len(ARCHETYPES)) % len(SUFFIXES)]
    company_name = f"{_stem(name, index)} {suffix}"

    rec = store.new_record(rid, "domains", client, company_name, f"{rid}.test")
    rec["state"] = "enriched"
    rec["archetype"] = name              # for assertions, never for logic
    if batch:
        rec["batch"] = batch

    employees = _vary(spec["employees"], index, 6)
    rec["company_facts"] = {
        "name": company_name,
        "industry": spec["industry"],
        "specialties": list(spec["specialties"]),
        "description": spec["description"],
        "employees": employees,
        "country": country,
        "state": state,
        "city": city,
        "offices": [city or country] * max(0, spec["offices"])
        if spec["offices"] else [],
        "founded": spec.get("founded")
        or (2026 - (8 + index % 20) if employees else None),
    }
    # A second source's headcount, where the archetype declares one. This is
    # the field ContactOut's free people-count writes, so a disagreement here
    # is the ordinary case of two providers not matching rather than a
    # contrived one.
    if spec.get("headcount_signal") is not None:
        rec["company_facts"]["headcount_signal"] = spec["headcount_signal"]

    rec["research"] = []
    if spec["evidence"]:
        fact, source_type, age = spec["evidence"]
        rec["research"].append(evidence.make(
            f"{company_name} {fact}.",
            f"https://{rid}.test/news", source_type, "apify", rid,
            published_at=_days_before(today, age),
            persona="operations",
            angle_words=["utilisation", "capacity", "margin"],
            today=today))
    return rec


def _stem(archetype, index):
    """A readable company name stem, derived from the archetype and index."""
    stems = {
        "strong_digital_agency": ("Northwind", "Brightside", "Copperline"),
        "strong_software_agency": ("Bitforge", "Ironwood", "Halyard"),
        "mid_creative_agency": ("Marlow", "Fieldhouse", "Tinderbox"),
        "small_seo_agency": ("Rankly", "Signalpost", "Beacon"),
        "large_consultancy": ("Ashgrove", "Delaney", "Whitmore"),
        "borderline_agency": ("Vantage", "Crestline", "Parkway"),
        "performance_agency": ("Uplift", "Trajectory", "Bidwell"),
        "design_ux_studio": ("Formwork", "Pica", "Kerning"),
        "architecture_practice": ("Stonebridge", "Kestrel", "Lattice"),
        "pr_agency": ("Cadence", "Loudspeaker", "Wren"),
        "staff_aug_shop": ("Talentway", "Benchmark", "Sourcefield"),
        "tiny_studio": ("Inkwell", "Tuppence", "Nib"),
        "saas_product": ("Trackly", "Flowbase", "Metricly"),
        "ecommerce_retailer": ("Shopfront", "Cartwheel", "Parcelly"),
        "holding_company": ("Meridian Capital", "Oakvale", "Sterling House"),
        "manufacturer": ("Forgeworks", "Castmill", "Pressline"),
        "enterprise_services": ("Halloway", "Pennington", "Bexley"),
        "unknown_thin": ("Mystery", "Blank", "Quiet"),
        "unknown_named_only": ("Generic", "Nondescript", "Vague"),
        "contradictory_evidence": ("Janus", "Paradox", "Crosswire"),
        "hybrid_agency_product": ("Duality", "Twofold", "Janus"),
    }
    options = stems.get(archetype, ("Company",))
    return options[index % len(options)]


def _days_before(today, days):
    import datetime
    return (datetime.date.fromisoformat(today)
            - datetime.timedelta(days=days)).isoformat()


def dataset(size=5000, config=None, client="benchmark", batch=None,
            today=TODAY):
    return [record(i, config, client, batch, today) for i in range(size)]


def indices_of(archetype, size=5000):
    if archetype not in ARCHETYPE_NAMES:
        raise KeyError(archetype)
    start = ARCHETYPE_NAMES.index(archetype)
    return list(range(start, size, len(ARCHETYPES)))


def describe(size=5000):
    per = {}
    for offset, (name, spec) in enumerate(ARCHETYPES):
        per[name] = {
            "count": len(range(offset, size, len(ARCHETYPES))),
            "employees": spec["employees"],
            "industry": spec["industry"],
        }
    return {"size": size, "archetypes": len(ARCHETYPES), "per_archetype": per,
            "countries": len({p[0] for p in PLACES})}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=int, default=5000)
    p.add_argument("--client", default="benchmark")
    p.add_argument("--batch")
    p.add_argument("--describe", action="store_true")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)

    if a.describe:
        print(json.dumps(describe(a.size), indent=2))
        return 0
    recs = dataset(a.size, client=a.client, batch=a.batch)
    if a.write:
        store.save(recs)
        print(f"wrote {len(recs)} synthetic companies through src/store.py")
    else:
        print(f"built {len(recs)} synthetic companies "
              f"({len(ARCHETYPES)} archetypes); pass --write to store them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
