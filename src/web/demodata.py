#!/usr/bin/env python3
"""Enough fictional data to click through the whole product, offline.

## What this is

Demo mode is not a mock of the application. It is the real application, given
records that were built rather than bought. Every verdict on every screen in
demo mode came out of `icp.score`, `verification.decide`, `mx.classify`,
`channels.evaluate`, `cadence.build`, `qa.report` and `push.payloads` - the
same functions a live batch would go through. What is fictional is the input.

That distinction is the whole point. A demo that fakes its outputs proves
nothing about the engine; this one exercises it.

## What it contains

Three campaigns, chosen so the segment explorer has something to explore and
so the dashboard's channel breakdown is not all one colour:

    PRODUCTIVE - UK DIGITAL AGENCIES
    PRODUCTIVE - DACH SOFTWARE AGENCIES
    PRODUCTIVE - US CREATIVE AGENCIES

plus the seven verification scenarios from `demo_outreach`, which is where the
double-verification screens get their disagreement, their escalation and their
one-confirmation hold.

Everything is on `.test` domains and nobody in it is real.
`tests/test_fixture_hygiene.py` keeps it that way.

## Determinism

Built from an index, never from a clock or a random seed, so company 41 is the
same company on every machine and a screenshot taken tonight matches one taken
tomorrow. The one exception is `store.now()` timestamps, which are what they
are.
"""
import datetime
import os

from .. import (cadence, channels, clients, demo_outreach, evidence, icp,
                mx, personalization, qualify, segments, store, verification,
                workspaces as ws)

TODAY = "2026-08-27"
CLIENT = "productive"

# (campaign id, name, country, city, vertical words, industry, band, tz hosts)
CAMPAIGNS = (
    ("uk-digital", "Productive - UK Digital Agencies", "United Kingdom",
     "London", ["digital marketing", "content marketing", "paid media"],
     "Marketing and Advertising", (28, 190),
     ["aspmx.l.google.com"]),
    ("dach-software", "Productive - DACH Software Agencies", "Germany",
     "Berlin", ["software development", "custom software", "web development"],
     "Software Development", (35, 240),
     ["dach.mail.protection.outlook.com"]),
    ("us-creative", "Productive - US Creative Agencies", "United States",
     "New York", ["branding", "brand strategy", "creative studio"],
     "Design", (22, 140),
     ["mx.zoho.com"]),
)

# ------------------------------------------------------- the workspaces
#
# Three tenants, populated differently on purpose. A demo with one workspace
# cannot show that a workspace is a boundary: you need a second one holding
# data you must not be able to reach, and a third at a different stage of the
# funnel so the screens are not all the same screen.

CONTACTOUT_CAMPAIGNS = (
    ("apac-recruiting", "ContactOut - APAC Recruiting Agencies", "Australia",
     "Sydney", ["recruitment", "talent acquisition", "executive search"],
     "Staffing and Recruiting", (40, 300),
     ["apac.mail.protection.outlook.com"]),
    ("sg-consulting", "ContactOut - Singapore Consulting", "Singapore",
     "Singapore", ["management consulting", "operations consulting"],
     "Management Consulting", (18, 120),
     ["aspmx.l.google.com"]),
)

# A batch that has been uploaded, qualified, segmented and routed, and has no
# campaign yet. Without one of these every demo segment is already spoken for
# and the campaign builder has nothing to build - which is the one screen where
# an operator is supposed to be able to see the step between "qualified" and
# "there is a campaign". `install` drops its campaign row and keeps its
# records, so it sits exactly where the pipeline says it should.
PRODUCTIVE_UNBUILT = (
    ("nl-ecommerce", "Productive - Benelux Ecommerce Agencies",
     "Netherlands", "Amsterdam",
     ["digital marketing", "paid media", "conversion optimisation"],
     "Marketing and Advertising", (30, 160),
     ["nl.mail.protection.outlook.com"]),
)

DEMO_CLIENT_CAMPAIGNS = (
    ("ie-services", "Demo Client - Ireland Managed Services", "Ireland",
     "Dublin", ["managed services", "it services", "support desk"],
     "IT Services", (12, 90), ["mx.zoho.com"]),
)

# slug, display name, client config, campaign table, name/domain offset,
# which campaign gets approved (index, or None), which gets a planted reply,
# and which batches keep their records but lose their campaign row so the
# campaign builder has something to build.
WORKSPACES = (
    {"slug": "productive", "name": "Productive", "client": "productive",
     "campaigns": CAMPAIGNS + PRODUCTIVE_UNBUILT, "seed": 0, "approve": 0,
     "reply": 1, "unbuilt": ("nl-ecommerce",)},
    {"slug": "contactout", "name": "ContactOut", "client": "contactout",
     "campaigns": CONTACTOUT_CAMPAIGNS, "seed": 100, "approve": None,
     "reply": None},
    {"slug": "demo-client", "name": "Demo Client", "client": "demo-client",
     "campaigns": DEMO_CLIENT_CAMPAIGNS, "seed": 200, "approve": None,
     "reply": None},
)

# One person per role, so every view can be seen as the role that owns it.
# `ops@contactout.test` is deliberately in two workspaces with *different*
# roles: operator in one, reviewer in the other. A permission model that
# resolves a role once per session rather than once per workspace gets this
# person wrong, and that is exactly the bug worth being able to see.
USERS = (
    {"email": "root@resonate.test", "name": "Sam Okafor",
     "super_admin": True, "memberships": ()},
    {"email": "admin@productive.test", "name": "Rae Lindqvist",
     "memberships": (("productive", ws.WORKSPACE_ADMIN),)},
    {"email": "ops@productive.test", "name": "Tomas Weber",
     "memberships": (("productive", ws.OPERATOR),)},
    {"email": "review@productive.test", "name": "Ines Ferreira",
     "memberships": (("productive", ws.REVIEWER),)},
    {"email": "client@productive.test", "name": "Nora Halvorsen",
     "memberships": (("productive", ws.VIEWER),)},
    {"email": "admin@contactout.test", "name": "Peter Nagy",
     "memberships": (("contactout", ws.WORKSPACE_ADMIN),)},
    {"email": "ops@contactout.test", "name": "Mara Kovac",
     "memberships": (("contactout", ws.OPERATOR),
                     ("productive", ws.REVIEWER))},
    {"email": "ops@demo-client.test", "name": "Liam Duarte",
     "memberships": (("demo-client", ws.OPERATOR),)},
    {"email": "client@demo-client.test", "name": "Ruth Bakker",
     "memberships": (("demo-client", ws.VIEWER),)},
)


# ------------------------------------------------ the fictional client files
#
# Written into a disposable directory, never into `config/clients/`. Demo mode
# must not be able to reach a real client's ICP rules, personas or provider
# mapping, and the way to guarantee that is for it to read from somewhere else
# entirely rather than to promise it will be careful.

CONFIG_TEXT = {
    "productive": """\
# Fictional. Demo mode only. Not the real Productive client file.
name: Productive
domain: productive.test
booking_link: https://productive.test/book
sender:
  mode: client_rep
market:
  must: services business that tracks time
  size_min_employees: 20
  geos: [United Kingdom, Ireland, Netherlands, Germany, France, Nordics,
         Australia, United States]
  exclude_geos: [Antarctica]
  flag_dont_drop: true
personas:
  champion:
    titles: [Operations Manager, Operations Director, Project Manager,
             Finance Manager, Head of Finance, Head of Operations]
    cap_per_domain: 2
    angles:
      finance: margin per project, month end reconciliation
      delivery: live budget burn, scope creep, resourcing visibility
      ops:     utilisation, capacity planning, one system not five
  economic_buyer:
    titles: [CFO, COO, CEO, Owner, Founder, Managing Director]
    cap_per_domain: 1
    start_offset_days: 5
    angles:
      founder: profitability visible on Monday not two weeks late
cadence: productive_default
sender_policy:
  # This client has told us their senders may be described to a prospect
  # as colleagues. ContactOut and Demo Client deliberately have not, so
  # the same evidence produces a handoff here and a standalone message
  # there. What differs is the permission, not the facts.
  colleague_language: true
tone:
  email: polished, professional, no em dashes, no buzzwords, no fluff openers
  linkedin: casual, lowercase, human
""",
    "contactout": """\
# Fictional. Demo mode only. Nothing here describes a real customer.
name: ContactOut
domain: contactout.test
booking_link: https://contactout.test/book
sender:
  mode: client_rep
market:
  must: a recruiting or consulting firm that bills for people time
  size_min_employees: 15
  geos: [Australia, Singapore, New Zealand, United Kingdom]
  exclude_geos: [Antarctica]
  flag_dont_drop: true
personas:
  champion:
    titles: [Head of Talent, Talent Acquisition Manager, Recruitment Manager,
             Operations Manager, Head of Delivery]
    cap_per_domain: 2
    angles:
      sourcing: hours lost to sourcing before the first conversation
      ops:      one system for search, outreach and placement
  economic_buyer:
    titles: [CEO, Managing Director, Founder, COO, Partner]
    cap_per_domain: 1
    start_offset_days: 4
    angles:
      founder: cost per placement visible this month not next quarter
cadence: productive_default
tone:
  email: direct, plain, no buzzwords
  linkedin: casual, lowercase, human
""",
    "demo-client": """\
# Fictional. Demo mode only.
name: Demo Client
domain: demo-client.test
booking_link: https://demo-client.test/book
sender:
  mode: client_rep
market:
  must: a managed services business that tracks engineer time
  size_min_employees: 10
  geos: [Ireland, United Kingdom]
  exclude_geos: [Antarctica]
  flag_dont_drop: true
personas:
  champion:
    titles: [Service Delivery Manager, Operations Manager, Head of Operations,
             Finance Manager]
    cap_per_domain: 2
    angles:
      ops: engineer utilisation against contracted hours
  economic_buyer:
    titles: [Managing Director, Founder, CEO]
    cap_per_domain: 1
    start_offset_days: 5
    angles:
      founder: which contracts actually make money
cadence: productive_default
tone:
  email: plain, short, no buzzwords
  linkedin: casual, lowercase, human
""",
}


def install_configs(directory=None):
    """Write the fictional client files into a disposable config directory.

    Refuses to write into the repository's real `config/clients/`. Demo mode
    must not be able to add, overwrite or shadow a real client file, and a
    check is cheaper than the incident.
    """
    directory = directory or clients.clients_dir()
    if os.path.abspath(directory) == os.path.abspath(clients.CLIENTS):
        raise RuntimeError(
            "refusing to write demo client configs into the real "
            "config/clients directory; set CLIENTS_DIR to a disposable path")
    os.makedirs(directory, exist_ok=True)
    written = []
    for slug, text in CONFIG_TEXT.items():
        path = os.path.join(directory, f"{slug}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(path)
    return written


def seed_people():
    """Users, workspaces and memberships. Roles come from here, never a form."""
    for spec in WORKSPACES:
        ws.ensure(spec["slug"], spec["name"], client=spec["client"],
                  created_by="demo")
    for person in USERS:
        ws.add_user(person["email"], person["name"],
                    super_admin=bool(person.get("super_admin")))
        for slug, role in person["memberships"]:
            ws.assign(person["email"], slug, role, actor="demo")
    return ws.users()


STEMS = ("Northwind", "Brightside", "Copperline", "Harbourline", "Vantage",
         "Meridian", "Kestrel", "Redwood", "Skyline", "Lantern", "Foxglove",
         "Marlow", "Ashgrove", "Bellweather", "Cranfield", "Dunmore",
         "Eastgate", "Fairhaven", "Glenmoor", "Holloway")
SUFFIXES = ("Studio", "Group", "Partners", "Collective", "Works", "Agency",
            "Digital", "Labs")

FIRST = ("Mara", "Tomas", "Ana", "Peter", "Ines", "Sven", "Ruth", "Liam",
         "Clara", "Jonas", "Elena", "Marcus")
LAST = ("Lindqvist", "Weber", "Ferreira", "Nagy", "Kovac", "Halvorsen",
        "Ellery", "Doyle", "Bergman", "Fischer", "Rossi", "Whitfield")
TITLES = ("Head of Operations", "Operations Director", "Finance Manager",
          "Operations Manager", "Head of Delivery")

# Which contact index gets which verification outcome. Spread deliberately so
# every state in the double-verification UI has something behind it.
VERIFICATION_CYCLE = (
    {"contactout": "valid", "deliverable": "valid"},          # double confirmed
    {"contactout": "valid", "deliverable": "valid"},
    {"contactout": "valid"},                                   # one of two: held
    {"contactout": "valid", "deliverable": "invalid"},         # disagreement
    {"contactout": "valid", "deliverable": "unknown",
     "reoon": "valid"},                                        # escalated
    {"contactout": "valid", "deliverable": "valid"},
    {"contactout": "invalid"},                                 # blocked
)

# One company per campaign sits behind a gateway, so the MX screen has a real
# block to show and the "no verifier credit spent" saving is visible.
PROOFPOINT = ["mx1.pphosted.com"]
MIMECAST = ["eu-smtp-inbound-1.mimecast.com"]
BARRACUDA = ["cudamail.example.com.ess.barracudanetworks.com"]
GATEWAYS = {2: PROOFPOINT, 9: MIMECAST, 15: BARRACUDA}

PER_CAMPAIGN = 8

# A batch where every company scores the same teaches an operator nothing: the
# ICP screen exists to show the *spread*, and the review queue exists because
# some companies land in the middle. Every third company is thinned out and
# every seventh is plainly not a prospect, which is roughly the shape a real
# scraped list arrives in.
STRONG = ("We run delivery teams across a portfolio of retainer and project "
          "clients. Resource planning, utilisation and project margin are how "
          "the studio is run, across several disciplines and two offices.")
THIN = "A marketing agency."
# Deliberately unplaceable. Not a rejection - a *gap*: there is nothing here
# to score, which is what puts a company in front of a human rather than
# through the machine. Without one of these in the main demo workspace the ICP
# review queue is empty, and an empty queue demonstrates nothing about the one
# decision PLAYBOOK section 1 reserves for a person.
SPARSE = "An independent studio."
NOT_ICP = ("We sell a SaaS platform on monthly and annual subscriptions, with "
           "self-serve pricing plans and a free trial.")


def _persona_for(config, index):
    """(persona, angle, title) for one contact, from the client's own config.

    Read rather than invented. Every persona and angle in the demo estate is
    one this client actually declares, so a breakdown by persona on the
    reporting screen is grouping by the same vocabulary the engine routes on.

    Varied across the batch on purpose. The brief asks to compare "COO vs CFO"
    and "Founder vs Operations", and a demo where every contact is a champion
    approached on the ops angle can demonstrate neither - every persona
    breakdown is one row, and one row is not a comparison.
    """
    # `personas` and `angles_for` return maps; sorted keys keep the demo
    # deterministic, which is what makes company 41 the same company on every
    # machine and a screenshot taken tonight match one taken tomorrow.
    names = sorted(clients.personas(config)) or ["champion"]
    persona = names[index % len(names)]
    angles = sorted(clients.angles_for(config, persona)) or ["ops"]
    angle = angles[(index // len(names)) % len(angles)]
    titles = clients.titles_for(config, persona) or list(TITLES)
    return persona, angle, titles[index % len(titles)]


def _profile(index):
    """(description, specialties, employees, industry) for one slot.

    `None` for specialties, employees or industry means the demo record simply
    does not carry that fact - not that it carries an empty one. That
    distinction is the whole point of the sparse profile: `icp.score` has to
    reach `unknown` because there was nothing to score, and a record with an
    empty list where a fact should be would be scored as evidence of absence.
    """
    if index % 7 == 6:
        return NOT_ICP, ["saas", "software platform"], None, "Computer Software"
    if index % 11 == 5:
        return SPARSE, [], None, None
    if index % 3 == 2:
        return THIN, None, None, None
    return STRONG, None, None, None


def _days_ago(n):
    day = datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=n)
    return day.isoformat()


def _hosts(index, default):
    """MX hostnames for one company. Real shapes, so `mx.classify` does the work."""
    return list(GATEWAYS.get(index, default))


def _resolver_for(table):
    def resolve(domain):
        hosts = table.get(mx.normalise_host(domain))
        if hosts is None:
            raise mx.MXError(f"no demo MX entry for {domain}")
        return list(hosts)
    return resolve


def build(config=None, client=CLIENT, campaigns_spec=CAMPAIGNS, seed=0):
    """Every demo record and campaign for ONE workspace, in memory.

    `seed` offsets the name tables and the domain numbering, so two workspaces
    built from the same generator do not end up describing the same companies
    at the same domains. Two tenants holding a record for `northwind000.test`
    would be realistic but unreadable, and it would make a cross-tenant leak
    look like a coincidence instead of a bug. Nothing here is written.
    """
    config = config or clients.load(client)
    policy = personalization.settings(config)
    recs, campaigns, mx_table = [], [], {}
    index = 0

    for (batch, name, country, city, words, industry, band,
         hosts) in campaigns_spec:
        record_ids = []
        for slot in range(PER_CAMPAIGN):
            stem = STEMS[(index + seed) % len(STEMS)]
            suffix = SUFFIXES[(index + seed // 3) % len(SUFFIXES)]
            company = f"{stem} {suffix}"
            rid = f"{batch}-{index:03d}"
            domain = f"{stem.lower()}{seed + index:03d}.test"
            employees = band[0] + (index * 17) % max(1, band[1] - band[0])

            rec = store.new_record(rid, "domains", client, company, domain)
            rec["state"] = "drafted"
            rec["batch"] = batch
            rec["demo"] = True
            rec["hook"] = (f"{company} is hiring a resource manager to own "
                           "scheduling across the studio")
            (description, override, employees_override,
             industry_override) = _profile(index)
            sparse = override == []
            rec["company_facts"] = {
                "name": company,
                "industry": None if sparse else (industry_override or industry),
                "specialties": [] if sparse else list(override or words),
                "description": description,
                "employees": None if sparse else (employees_override
                                                  or employees),
                "country": country, "city": city,
                "state": "New York" if country == "United States" else None,
                "offices": [city], "founded": 2009 + (index % 12),
                "email_domain": domain,
            }
            mx_table[domain] = _hosts(index, hosts)

            first = FIRST[(index + seed) % len(FIRST)]
            last = LAST[(index * 3 + seed) % len(LAST)]
            key = f"{rid}-{first.lower()}-{last.lower()}"
            email = f"{first.lower()}.{last.lower()}@{domain}"
            persona, angle, title = _persona_for(config, index)
            contact = {
                "key": key, "name": f"{first} {last}",
                "title": title,
                "email": email, "email_source": "provider",
                "persona": persona, "angle": angle,
                "primary": True, "selected": True,
                # Every fourth contact has no usable profile, so the
                # email-only mode is represented.
                "linkedin": (None if index % 4 == 3 else
                             f"https://www.linkedin.com/in/{first.lower()}-"
                             f"{last.lower()}-{seed + index:03d}"),
            }
            answers = VERIFICATION_CYCLE[index % len(VERIFICATION_CYCLE)]
            _verify(contact, answers, email, config)
            rec["contacts"] = [contact]

            rec["research"] = [evidence.make(
                f"{company} opened a second office and moved four delivery "
                "leads across", f"https://{domain}/news/expansion",
                "company_announcement", "apify", rid,
                published_at=_days_ago(9 + index % 30), subject=evidence.COMPANY,
                persona="operations",
                angle_words=["utilisation", "capacity", "margin"],
                today=TODAY, policy=policy["freshness"],
                min_relevance=policy["min_relevance_score"],
                retrieved_at=_days_ago(1), confidence=0.92)]
            rec["research_state"] = {"company_done": True,
                                     "company_at": _days_ago(1)}
            _drafts(rec, company, first)
            recs.append(rec)
            record_ids.append(rid)
            index += 1

        campaigns.append({
            "campaign_id": batch, "client": client, "name": name,
            "status": "awaiting_approval", "created_at": store.now(),
            "created_by": "U0DEMOADMIN1", "record_ids": record_ids,
            "daily_volume": {"email": 40, "linkedin": 20},
            "senders": {"email": [{"id": "bison-a", "daily_limit": 50}],
                        "linkedin": [{"id": "hr-a", "daily_limit": 25}]},
            "bison_campaign_id": None, "heyreach_campaign_id": None,
            "approval": None, "fingerprint": None,
            "launch": {"state": "not_launched", "at": None},
            "pause": None, "log": [], "events": [], "demo": True,
        })

    # The real engine, in the order production runs it.
    resolver = _resolver_for(mx_table)
    cache = {}
    for rec in recs:
        personalization.apply(rec, config)
        for contact in rec["contacts"]:
            domain = mx.email_domain(contact.get("email"))
            if domain:
                contact["mx"] = mx.for_domain(domain, config, cache=cache,
                                              resolver=resolver, save=False)
        channels.apply_to_record(rec, config)
    return campaigns, recs, config


def _verify(contact, answers, email, config):
    """Build the verification block from provider answers, never by hand."""
    policy = verification.policy_for(config)
    evidence_rows = []
    for provider in ("contactout", "deliverable", "reoon"):
        status = answers.get(provider)
        if status is None:
            continue
        fields = {"reason": f"demo fixture: {provider} said {status}",
                  "at": _days_ago(1)}
        if provider == "reoon":
            fields["safe_to_send"] = status == verification.S_VALID
            fields["catch_all"] = False
            fields["score"] = 92 if status == verification.S_VALID else 48
        evidence_rows.append(
            verification.result(provider, status, email, **fields))
    verification.apply(contact, verification.decide(evidence_rows, policy),
                       evidence_rows)
    return contact


BODY = (
    "Hi {first}, noticed {company} opened a second office and moved four "
    "delivery leads across.\n\n"
    "Most operations leads we speak to at that point are running scheduling in "
    "one place, budgets in another and month end in a third, and the "
    "reconciliation is what eats the week.\n\n"
    "Productive puts the three in one system, so project margin is visible on "
    "the Monday rather than two weeks after the month closes.\n\n"
    "Is resourcing across teams something {company} is trying to solve this "
    "quarter?")

LATER = (
    "Hi {first}, the hiring signal is usually the tell: a resource manager "
    "appears when scheduling has outgrown the spreadsheet.\n\n"
    "The teams we work with had the same three systems and the same month end, "
    "and what changed was not the reporting - it was knowing on the Monday "
    "which projects were going to miss.\n\n"
    "Worth fifteen minutes to see whether {company} is in the same shape?")


def _drafts(rec, company, first):
    """The two generated emails, as phase 5 would leave them."""
    for contact in rec["contacts"]:
        stored = rec.setdefault("cadence", {}).setdefault(contact["key"], {})
        for step_key, template in (("day1", BODY), ("day15", LATER)):
            stored[step_key] = {
                "channel": "email", "generated": True,
                "subject": (f"resourcing across teams at {company}"
                            if step_key == "day1"
                            else f"one more thought on {company}"),
                "body": template.format(first=first, company=company),
                "angle": contact.get("angle"),
            }


def qualify_all(recs, config, client=CLIENT):
    """ICP, segmentation, routing and the DM plan, through the real engine."""
    return qualify.run(recs, client=client, config=config, store_result=True)


def install(config=None):
    """Write the whole demo estate into whatever store this process points at.

    Three workspaces, their users and their memberships, then their records
    and campaigns. Only ever called with `QUEUE`, `CAMPAIGNS`, `WORKSPACES`
    and `CLIENTS_DIR` pointing somewhere disposable - the web CLI sets them to
    a temp directory in demo mode, and the tests set them per test.

    It refuses to run against a queue that already holds non-demo records,
    because overwriting somebody's real batch to show a demo would be the
    worst possible trade.
    """
    existing = [r for r in store.load() if not r.get("demo")]
    if existing:
        raise RuntimeError(
            f"refusing to install demo data over {len(existing)} real "
            "record(s); point QUEUE somewhere disposable first")

    install_configs()
    seed_people()

    from .. import campaigns as campaign_store
    all_recs, all_campaigns, configs = [], [], {}
    for spec in WORKSPACES:
        cfg = clients.load(spec["client"])
        campaigns_, recs, cfg = build(cfg, spec["client"], spec["campaigns"],
                                      spec["seed"])
        # `qualify.run` mutates the record objects rather than writing, so
        # qualifying one list and saving another would persist the records and
        # drop every verdict - which is what "no ICP results in demo mode"
        # looked like the first time.
        qualify_all(recs, cfg, spec["client"])
        all_recs.extend(recs)
        # An "unbuilt" batch keeps every record and loses only its campaign.
        # Building the records through the same generator and then dropping
        # the campaign is deliberate: the records are then indistinguishable
        # from any other qualified batch, which is what makes the builder
        # screen exercise the real path rather than a special case.
        unbuilt = set(spec.get("unbuilt") or ())
        all_campaigns.extend(c for c in campaigns_
                             if c["campaign_id"] not in unbuilt)
        configs[spec["slug"]] = cfg

    # The sender roster before the records are saved, because planting a
    # scenario needs an assignment and an assignment needs a roster.
    from . import demosenders
    demosenders.install()
    scenarios = {}
    for spec in WORKSPACES:
        scenarios[spec["slug"]] = demosenders.plant(
            [r for r in all_recs if r.get("client") == spec["client"]],
            workspace=spec["slug"], config=configs[spec["slug"]])

    store.save(all_recs)
    campaign_store.save(all_campaigns)

    # Approvals and replies come after everything is stored, because both read
    # the saved state back rather than the list in hand.
    for spec in WORKSPACES:
        cfg = configs[spec["slug"]]
        if spec["approve"] is not None:
            batch = spec["campaigns"][spec["approve"]][0]
            approve_campaign(batch, cfg)
        if spec["reply"] is not None:
            _plant_reply(cfg, spec["campaigns"][spec["reply"]][0])

    # Last, because the Slack estate maps channels onto workspaces that must
    # already exist and plans notifications against them. Nothing is posted:
    # `notify.plan` records a routing decision and stops, and SLACK_LIVE is
    # not set in demo mode.
    # One account rich enough to show the new model: three decision makers,
    # four humans, a referral, and a planned touch that must not be claimed.
    from . import demoaccount
    demoaccount.install()

    # Manual signals, so account intelligence has something to read. Every
    # one is fictional and every one carries quotable evidence.
    from . import demosignals
    demosignals.install()

    # GTM decisions, including one superseded and one setting left
    # deliberately unexplained.
    from . import demogtm
    demogtm.install()

    # An earlier discovery run and a client ruling, so this week's delta
    # has something to subtract against.
    from . import demodiscovery
    demodiscovery.install()

    from . import demoslack
    demoslack.install()

    return all_campaigns, store.load(), configs[WORKSPACES[0]["slug"]]


def approve_campaign(campaign_id, config):
    """Take one campaign through the real approval path.

    One per estate, not all of them. A demo where nothing is approved shows an
    empty provider payload on every screen and teaches the reader nothing about
    what the sender would receive; a demo where *everything* is approved leaves
    the Approval Center with nothing to do. The other two workspaces stay
    unapproved on purpose, which is also what a reviewer's queue looks like.

    This is `approve.approve_record` and `orchestrator.decide` - the same calls
    the review screen and the Slack button make - on records that exist only in
    this demo store. Steps first, campaign last: the campaign fingerprint
    covers each step's approved flag, so signing before they settle leaves a
    signature describing a campaign that no longer exists.
    """
    from .. import approve, campaigns as campaign_store, orchestrator
    campaign = next((c for c in campaign_store.load()
                     if c.get("campaign_id") == campaign_id), None)
    if campaign is None:
        return None

    # Whoever this workspace's config says may approve. Read rather than
    # hardcoded: these client files have no Slack block at all, and inventing
    # an approver would mean the demo exercised a permission check that does
    # not describe the client. Where there is nobody, the per-step approvals
    # still happen and the campaign stays awaiting_approval - which is the
    # honest state, and the Approval Center shows it as such.
    approvers = ((config.get("slack") or {}).get("allowed_approvers") or [])
    approver = approvers[0] if approvers else None
    recs = [r for r in store.load()
            if r["id"] in (campaign.get("record_ids") or [])]
    for rec in recs:
        approve.approve_record(rec, by=approver or "demo-operator",
                               config=config)
    others = {x["id"] for x in recs}
    store.save([r for r in store.load() if r["id"] not in others] + recs)

    fresh = [r for r in store.load()
             if r["id"] in (campaign.get("record_ids") or [])]
    orchestrator.request_approval(campaign, fresh, config)
    if approver:
        orchestrator.decide(campaign, approver, "approve",
                            fingerprint=campaign.get("fingerprint"),
                            interaction_id="demo-approval", config=config,
                            recs=fresh)
    with campaign_store.transaction() as rows:
        for i, row in enumerate(rows):
            if row.get("campaign_id") == campaign.get("campaign_id"):
                rows[i] = campaign
    return campaign


def _plant_reply(config, batch):
    """One positive reply, so the pause path has something to show.

    Applied through `replaysim.simulate`, the production rehearsal: it writes a
    neutral event and the real pause follows from it. No provider is contacted
    and no provider state is read.
    """
    from .. import replaysim
    recs = store.load()
    target = next((r for r in recs
                   if r.get("batch") == batch and r.get("contacts")),
                  None)
    if target is None:
        return None
    contact_key = target["contacts"][0]["key"]
    replaysim.simulate(target, contact_key, scenario="positive_email",
                       recs=recs, config=config)
    store.save(recs)
    return target["id"]
