#!/usr/bin/env python3
"""The synthetic fixture for the 60-day sandbox simulation. ENTIRELY INVENTED.

    py -3 scripts/sandbox_fixture.py --seed 1 --out docs/sandbox/fixture-seed-1.json

WHAT THIS IS. 300 person-level prospect records across 100 companies, EXACTLY
three decision makers each, partitioned into six HOMOGENEOUS cohorts of exactly
50. Nothing here was fetched, enriched or verified: there is no network call in
this file and no provider is imported. Every byte is computed from `--seed`.

EXACTLY THREE PER COMPANY, ASSERTED AS EQUALITY. The operator's correction of
2026-10-12 made this an equality rather than a 2-3 range, which is also the
only thing the arithmetic ever allowed:

    x companies with 2 + y companies with 3
    x + y = 100  and  2x + 3y = 300   =>   y = 100, x = 0

So the range and the equality were always the same requirement. The test
asserts `== 3`, not `2 <= n <= 3`, so a company that lost a contact fails
instead of degrading quietly into the old tolerance.

WHY THERE ARE TWO GEOGRAPHIES AND NOT FOUR. A cohort carries ONE geo, ONE
industry, ONE headcount band, ONE signal and ONE persona, and no cohort may
hold fewer than 50 records. The three decision makers inside a company have
DISTINCT personas, so one company's three records necessarily land in three
DIFFERENT cohorts. Therefore a geography's records cannot occupy fewer than
three cohorts, i.e. no geography can carry fewer than 150 records, i.e.

    300 / 150 = 2

is the hard ceiling on the number of geographies at this n. Asking for the UK,
Western Europe, Australia and the US *and* a 50-record floor *and* one geo per
cohort is over-determined; four geographies needs n >= 600. The partition below
takes the two largest ICP regions and says so, rather than shipping cohorts of
25 that would pass no homogeneity test worth writing. This is a finding, not a
shortcut - see docs/sandbox/FIXTURE.md.

THE SAFETY PROPERTIES, each asserted by tests/test_sandbox_fixture.py:

  * every email ends `.invalid`, AND NOTHING ELSE. `example.com` was permitted
    by the first brief and is NOT permitted any more (operator, 2026-10-12);
    the generator cannot emit one and the test's positive control is an
    `example.com` address, proving the check would catch it. `.invalid` is
    reserved by RFC 6761 and can never resolve, so no message built from this
    fixture can reach a person even if a sandbox leaks into a sender.
  * every company domain is `<slug>.invalid`, which is what makes "no real
    domain appears" a property rather than a hope. Coined names cannot be
    proven absent from the world without a network lookup, and a network
    lookup is forbidden here; the reserved TLD is the part that *is* provable.
  * every record carries a LinkedIn URL that is already its own
    `linkedin.canonical()` form. A missing URL is a data-loss defect in this
    system, so the generator cannot emit one and the test refuses the fixture
    if it does. `canonical()` only accepts `linkedin.com` hosts, so the
    fakeness lives in the vanity segment, which is suffixed `-sandbox`.
  * research facts cite `https://<slug>.invalid/...`, which is same-site with
    the record's own domain, so `packfacts.identity_of` returns ADMITTED and
    the copy path has licensed facts to work from - that are also incapable of
    being fetched.

The record skeleton comes from `store.new_record()` and the contact, fact and
company_facts key names were read off the live `work/queue.jsonl`. No field
name in the queue projection was invented.
"""
import argparse
import datetime
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pure modules only, and every one of them is here to supply a SHAPE rather
# than to fetch anything: `store.new_record` for the record skeleton,
# `evidence.make` for a scored evidence item, `verification.result` for a
# provider verdict, `cadence.STEPS` for the step list and `clients.load` for
# the client's real persona titles. No provider module is imported and there
# is no socket in this file - `tests/test_sandbox_fixture.py` asserts that
# from the AST.
from src import cadence, clients, evidence, store, verification   # noqa: E402

SCHEMA = "resonate-sandbox-fixture/1"
CLIENT = "productive"
LANE = "cold"

# THE 60-DAY SIMULATION HORIZON (operator correction, 2026-10-12; it was
# 30 months). A FIXED anchor, never `date.today()`: a fixture whose bytes move
# at midnight is not reproducible, and "same seed gives byte-identical output"
# is the operator's acceptance test.
#
# 60 days is shorter than any re-engagement cycle, so nothing in the partition
# below has to carry a second or third touch of the same person. It does not
# relax the 50-record cohort floor, which is what actually shapes the
# partition.
WINDOW_START = datetime.date(2026, 10, 12)
WINDOW_DAYS = 60

# Research is published BEFORE the simulation starts - a fact dated inside the
# horizon would be a fact the run had not yet been able to read.
RESEARCH_LOOKBACK_DAYS = 365

# ------------------------------------------------------------- the partition
#
# A block is a set of companies homogeneous in geo, industry, headcount band
# and signal. Crossing a block with its three personas gives the cohorts, and
# because every company in a block carries the same three personas the cohort
# sizes come out exactly equal - 50 companies x 1 record per persona.

BLOCKS = (
    {
        "block": "A",
        "geo": "United Kingdom",
        "country_code": "GB",
        "industry": "Marketing & Advertising",
        "headcount_band": "20-49",
        "employees_min": 20,
        "employees_max": 49,
        "signal": "public_timesheet_rollout",
        "companies": 50,
        "cities": ("Ashbury Vale", "Pentlow Reach", "Marrowgate",
                   "Deepwick Cross", "Harlingstoke"),
        "personas": (
            ("Operations Manager", "champion", "operations"),
            ("Finance Manager", "champion", "finance"),
            ("CFO", "economic_buyer", "finance"),
        ),
    },
    {
        "block": "B",
        "geo": "United States",
        "country_code": "US",
        "industry": "Software Development",
        "headcount_band": "50-99",
        "employees_min": 50,
        "employees_max": 99,
        "signal": "headcount_growth_over_20pct",
        "companies": 50,
        "cities": ("Calder Springs", "Northam Flats", "Verity Bend",
                   "Sabal Heights", "Linden Forge"),
        "personas": (
            ("Operations Director", "champion", "operations"),
            ("Project Manager", "champion", "delivery"),
            ("COO", "economic_buyer", "operations"),
        ),
    },
)

# The client's own words for each angle, copied from config/clients/productive.yaml
# so the copy path meets a key it already knows. Not a new claim.
ANGLE_WORDING = {
    "operations": "utilisation, capacity planning, one system not five",
    "finance": "margin per project, month end reconciliation, multi entity billing",
    "delivery": "live budget burn, scope creep, resourcing visibility",
}

# ----------------------------------------------------------------- the names
#
# Coined, and coined on purpose in a shape no register of real people or
# companies uses: a syllable stem that is not a word, plus a compound ending
# that is not a surname anybody has. "Fixbury" and "Mockworth" are not
# cautious spellings of real names; they are not names.

GIVEN = ("Arvelle", "Brunnic", "Corvane", "Darnith", "Elspire", "Fendril",
         "Galwyn", "Hesperra", "Ilvane", "Jorrith", "Kesmira", "Lorvane",
         "Marnelle", "Nevric", "Orvane", "Pelwyn", "Quorith", "Ravelle",
         "Solvane", "Tamric", "Ulwyn", "Velmira", "Wynnoth", "Yarvelle",
         "Zelric", "Brynneth", "Dovric", "Esvane", "Thalwyn", "Mirroth")

SURNAME = ("Mockworth", "Fixbury", "Sandmoor", "Synthwell", "Testavere",
           "Dummerly", "Fauxley", "Simworth", "Stubfield", "Mimbry",
           "Pseudane", "Notionby", "Placeholt", "Sampleton", "Fablewick",
           "Invenby", "Contrivell", "Figmenthorpe", "Coinwright", "Devisely")

STEM = ("Mornvale", "Threxmoor", "Quilbrook", "Vexmoor", "Harrowdene",
        "Pellasto", "Grindale", "Obrevant", "Sallowfen", "Trennick",
        "Umbervale", "Kesslow", "Drayvant", "Fennhollow", "Wrenmoor",
        "Yolbright", "Zantheral", "Brackvane", "Clovemoor", "Dunfallow",
        "Erriswade", "Fosswick", "Gallowmere", "Hesterby", "Islemoor",
        "Jarrowfen", "Kindlevast", "Lowmarch", "Myrthwaite", "Norvane",
        "Ostlerby", "Prendwick", "Quarrowmoor", "Ruthvane", "Starrowgate",
        "Tolbrand", "Underhaven", "Varnwell", "Westholme", "Xandermoor")

SUFFIX = ("Studio", "Collective", "Digital", "Labs", "Works", "Partners",
          "Agency", "Group", "Interactive", "Systems")

STREET = ("Tallowmere Row", "Quinder Walk", "Belgrave Fold", "Nettlecombe Way",
          "Harrowsend Lane", "Pindle Court", "Veltham Rise", "Oakenshaw Mews",
          "Crannock Street", "Stillwater Parade")

# THE FACT TEXT HAS TO EARN ITS QUALITY SCORE, NOT BE ASSIGNED ONE.
#
# `evidence.make` scores every fact through `evidence.relevance` and
# `evidence.quality`, and `quality` returns UNUSABLE below a relevance of
# 0.35 and WEAK below MIN_RELEVANCE (0.65). The first draft of this file
# wrote pleasant firmographic sentences and measured 0.339 - UNUSABLE on all
# 400 of them. The copy path would then have had a research pack that
# licensed nothing and fallen back to persona pain, and the sandbox would
# have been exercising the FALLBACK while reporting that research worked.
#
# The score is not nudged by lowering `min_relevance`. The text below
# contains, honestly, the things the scorer looks for: the cohort's own angle
# words (+0.35), an operational term (+0.25), a company-change term (+0.35)
# and a specific figure (+0.10). A sentence that genuinely says "utilisation
# and capacity planning" is a sentence a copywriter can use; one that scores
# well without saying anything is the thing `boilerplate()` exists to refuse.
COMPANY_FACT = (
    "{company} is a {industry_lower} firm of {employees} people in {city}, "
    "{geo}, billing clients against tracked time, and has launched a "
    "timesheet rollout across its delivery and project teams."
)

ANGLE_FACTS = {
    "operations": (
        "{company} has rolled out timesheets to all {employees} of its people "
        "and now reviews utilisation and capacity planning weekly, having "
        "launched one system in place of the five tools it used before."
    ),
    "finance": (
        "{company} runs multi entity billing across {entities} legal entities, "
        "closed its month end reconciliation {days} days faster this quarter, "
        "and has appointed a finance lead to report project margin per "
        "engagement."
    ),
    "delivery": (
        "{company} tracks live budget burn across {projects} active client "
        "engagements, reviews scope creep weekly, and has launched a "
        "resourcing visibility report for its delivery leads."
    ),
}

# The angle words the scorer is given, from the client's own `angles` block.
# Passed to `evidence.make` so an angle hit is a real match against the words
# this client actually sells on, not against a list invented here.
ANGLE_TERMS = {angle: wording.replace(",", " ").split()
               for angle, wording in (
                   ("operations", "utilisation, capacity planning, one system "
                                  "not five"),
                   ("finance", "margin per project, month end reconciliation, "
                               "multi entity billing"),
                   ("delivery", "live budget burn, scope creep, resourcing "
                                "visibility"))}

# What the company-level fact is scored against: the cohort signal, in the
# words the fact itself uses.
COMPANY_ANGLE_TERMS = ("timesheet", "tracked time", "rollout", "delivery",
                       "project")

# A FIXED timestamp for every synthetic provider verdict. `verification.result`
# defaults `at` to `store.now()`, which is the wall clock - leaving it to the
# default made two runs of one seed differ by the second they were run in, and
# "same seed, identical bytes" is the operator's acceptance test. This is the
# one place the clock could have leaked in.
VERDICT_AT = "2026-10-12T00:00:00+00:00"

INVARIANTS = (
    "exactly 300 person-level records",
    "exactly 100 companies, exactly 3 distinct decision makers each (equality)",
    "the 3 decision makers in a company are distinct people with distinct personas",
    "6 cohorts of exactly 50; no cohort under 50",
    "every cohort homogeneous in geo, industry, headcount_band, signal and persona",
    "every record carries a LinkedIn URL equal to its own linkedin.canonical() form",
    "every email ends in .invalid - example.com is NOT permitted - and is "
    "already dedupe.normalise_email()-canonical",
    "every company domain ends in .invalid, so no real domain can appear",
    "every research source_url is same-site with the record domain, so "
    "packfacts.identity_of returns ADMITTED",
    "no synthetic domain appears in production work/queue.jsonl, "
    "work/campaigns.jsonl or config/suppress.local.txt",
    "no synthetic contact is on work/agency-dnc.jsonl - tested by FINGERPRINT "
    "through agencydnc.keys_for, because that file stores only sha256 and a "
    "domain scan of it could never match",
    "no real client domain from config/suppress.local.txt or "
    "config/clients/productive.yaml appears anywhere in the fixture",
    "byte-identical output for a given --seed; different output for a "
    "different --seed",
    "every queue_records row satisfies store.validate() with no problems",
    "every contact key is a name slug, the live queue's own key shape",
    "every research item is an evidence.make() object, and scores USABLE",
    "every contact's stored `sendable` equals verification.is_sendable() "
    "recomputed from its evidence under the client's own policy",
    "cadence steps live under cadence.CADENCE_KEY as a list",
    "no provider, no network, no credit: nothing in this fixture was fetched",
    "the fields only a provider can answer are present and NULL, never "
    "invented: mx, reoon, verdict, bison_lead_id",
)

# WHAT THIS FIXTURE STILL CANNOT POPULATE, AND WHY IT IS LEFT NULL.
#
# The email path IS runnable at zero credits, and the reason is specific:
# `verification.is_sendable` recomputes from an evidence list and never trusts
# a stored flag, so supplying two synthetic provider verdicts models the
# POLICY rather than bypassing it. The policy genuinely runs - two
# independent confirmations are genuinely required, and the two controls in
# the test module prove the requirement bites.
#
# These four are different. They are not policy, they are facts about the
# world or about a push that has not happened:
#
#   mx              a DNS lookup. No resolver, and `.invalid` has no MX.
#   reoon, verdict  the LEGACY verifier fields. `verification.legacy_evidence`
#                   reads them and would count a stored `verdict: "valid"` as
#                   a THIRD confirmation nobody obtained - so filling these
#                   would quietly inflate the confirmation count past the
#                   policy that is meant to be under test.
#   bison_lead_id   issued by Bison when a lead is pushed. Nothing was pushed.
#
# Left NULL rather than omitted, so the key is present in the shape the flow
# expects, and left NULL rather than filled, because an invented value here
# is indistinguishable downstream from a real one.
NULL_WITHOUT_A_PROVIDER = ("mx", "reoon", "verdict", "bison_lead_id")


def _slug(text):
    return "".join(ch.lower() if ch.isalnum() else "-"
                   for ch in text).strip("-").replace("--", "-")


WINDOW_END = WINDOW_START + datetime.timedelta(days=WINDOW_DAYS - 1)


def _cohorts():
    """The partition, declared before a single record exists."""
    out = []
    for block in BLOCKS:
        for persona, family, angle in block["personas"]:
            out.append({
                "key": "%s-%s" % (_slug(block["geo"]), _slug(persona)),
                "block": block["block"],
                "geo": block["geo"],
                "industry": block["industry"],
                "headcount_band": block["headcount_band"],
                "signal": block["signal"],
                "persona": persona,
                "persona_family": family,
                "angle": angle,
                "size": block["companies"],
            })
    return out


def _people(rng, wanted):
    """`wanted` distinct coined people, sampled without replacement."""
    pool = ["%s %s" % (given, surname)
            for given in GIVEN for surname in SURNAME]
    if wanted > len(pool):
        raise ValueError("name pool too small: %d wanted, %d available"
                         % (wanted, len(pool)))
    rng.shuffle(pool)
    return pool[:wanted]


def _company_names(rng, wanted):
    """`wanted` distinct coined companies whose slugs are also distinct."""
    pool = ["%s %s" % (stem, suffix) for stem in STEM for suffix in SUFFIX]
    rng.shuffle(pool)
    out, slugs = [], set()
    for name in pool:
        slug = _slug(name)
        if slug in slugs:
            continue
        slugs.add(slug)
        out.append(name)
        if len(out) == wanted:
            return out
    raise ValueError("company pool too small: %d wanted, %d distinct"
                     % (wanted, len(out)))


def _personas_from_config(config):
    """The client's own persona titles, by family.

    READ, not hardcoded (operator, 2026-10-12). `personas.classify` decides
    whether a contact is a persona by matching its title against exactly this
    list, so a title this fixture invented would be set aside as "not a
    persona for this client" the moment it reached the real flow - and the
    cohort would be empty in practice while looking full in the JSON.
    `build()` asserts every persona it uses is in here, so the fixture tracks
    the client file instead of drifting from it.
    """
    out = {}
    for family in ("champion", "economic_buyer"):
        titles = (config.get("personas") or {}).get(family, {}).get("titles")
        out[family] = {str(title).strip() for title in (titles or [])}
        if not out[family]:
            raise ValueError("config/clients/%s.yaml declares no %s titles"
                             % (CLIENT, family))
    return out


def _evidence_for(rng, company, domain, record_id, block, city, employees,
                  contacts):
    """The record's `research` list, built with `evidence.make`.

    A LIST of scored evidence items, not a dict and not hand-built: the
    constructor returns eighteen scored fields and `quality._selected` reads
    them, so a hand-made dict raises `AttributeError: 'str' object has no
    attribute 'get'` in there.

    Source URLs are FAKE and on the company's own `.invalid` site, which is
    what `packfacts.identity_of` admits as same-site - so the copy path gets a
    licensed fact whose citation can never be fetched by anybody.

    One company-level fact, plus one fact per contact bound to that contact's
    own angle. The per-contact binding is what lets each of the three decision
    makers at a company be written to about a different thing without three
    different companies having to exist.
    """
    published = {}
    for slot in range(1 + len(contacts)):
        published[slot] = (WINDOW_START - datetime.timedelta(
            days=rng.randrange(1, RESEARCH_LOOKBACK_DAYS + 1))).isoformat()

    items = [evidence.make(
        fact=COMPANY_FACT.format(company=company,
                                 industry_lower=block["industry"].lower(),
                                 city=city, geo=block["geo"],
                                 employees=employees),
        source_url="https://%s/about" % domain,
        # NOT `apify`, NOT `local_http`, NOT `webfetch` - the three real
        # values in the live queue. Claiming one would be claiming a fetch.
        source_type="synthetic_fixture",
        provider="sandbox",
        record_id=record_id,
        published_at=published[0],
        retrieved_at=WINDOW_START.isoformat(),
        subject=evidence.COMPANY,
        angle_words=list(COMPANY_ANGLE_TERMS),
        # A FIXED `today`, like VERDICT_AT: freshness is measured from it, so
        # the real clock here would move `age_days` and the relevance score
        # every day and break byte-identity.
        today=WINDOW_START.isoformat(),
        confidence="synthetic: invented for the sandbox, true of nothing",
    )]

    for slot, contact in enumerate(contacts, start=1):
        angle = contact["angle"]
        items.append(evidence.make(
            fact=ANGLE_FACTS[angle].format(
                company=company, employees=employees,
                entities=rng.randrange(2, 7),
                days=rng.randrange(2, 9),
                projects=rng.randrange(8, 40)),
            source_url="https://%s/insights/%s-note" % (domain, angle),
            source_type="synthetic_fixture",
            provider="sandbox",
            record_id=record_id,
            contact_key=contact["key"],
            published_at=published[slot],
            retrieved_at=WINDOW_START.isoformat(),
            subject=evidence.COMPANY,
            persona=contact["title"],
            angle_words=ANGLE_TERMS[angle],
            today=WINDOW_START.isoformat(),
            confidence="synthetic: invented for the sandbox, true of nothing",
        ))
    return items


def build(seed):
    """The whole fixture as a plain dict. Pure: seed in, data out."""
    rng = random.Random(seed)
    cohorts = _cohorts()
    total_companies = sum(block["companies"] for block in BLOCKS)
    total_records = sum(len(block["personas"]) * block["companies"]
                        for block in BLOCKS)

    # The client's real config, for the persona titles and the verification
    # policy. Both are READ rather than restated, so this fixture fails loudly
    # if the client file moves underneath it instead of quietly generating
    # records the real flow would set aside.
    config = clients.load(CLIENT)
    declared = _personas_from_config(config)
    policy = verification.policy_for(config)
    for block in BLOCKS:
        for persona, family, _angle in block["personas"]:
            if persona not in declared[family]:
                raise ValueError(
                    "persona %r is not a %s title in config/clients/%s.yaml - "
                    "the real flow would set every one of these contacts "
                    "aside as 'not a persona for this client'"
                    % (persona, family, CLIENT))

    names = _company_names(rng, total_companies)
    people = _people(rng, total_records)

    companies, records, queue_records = [], [], []
    person = 0
    company_index = 0
    for block in BLOCKS:
        for _ in range(block["companies"]):
            name = names[company_index]
            slug = _slug(name)
            domain = "%s.invalid" % slug
            city = block["cities"][company_index % len(block["cities"])]
            employees = rng.randrange(block["employees_min"],
                                      block["employees_max"] + 1)
            company_id = "sbx-co-%03d" % (company_index + 1)
            address = "%d %s, %s, %s" % (rng.randrange(1, 240),
                                         STREET[company_index % len(STREET)],
                                         city, block["geo"])
            companies.append({
                # `id`, matching the queue record this company IS. One
                # company is one record in this system, so the two share an
                # id rather than being joined on an invented `company_id`.
                "id": company_id,
                "name": name,
                "domain": domain,
                "block": block["block"],
                "geo": block["geo"],
                "country_code": block["country_code"],
                "city": city,
                "address": address,
                "industry": block["industry"],
                "headcount_band": block["headcount_band"],
                "employees": employees,
                "signal": block["signal"],
                "linkedin": "https://www.linkedin.com/company/%s-sandbox" % slug,
            })

            # The queue projection. Skeleton from the real module so no field
            # name here is invented.
            rec = store.new_record(
                id=company_id, lane=LANE, client=CLIENT, company=name,
                domain=domain,
                context="synthetic sandbox fixture, seed %s" % seed,
                signal=block["signal"])
            rec["company_facts"] = {
                "industry": block["industry"],
                "employees": employees,
                "employee_range": "%s employees" % block["headcount_band"],
                "offices": [address],
                "linkedin": "https://www.linkedin.com/company/%s-sandbox" % slug,
                "headcount_signal": employees,
                "research_outcome": "SYNTHETIC_FIXTURE",
                "icp_flags": [],
            }
            contacts = []
            for slot, (persona, family, angle) in enumerate(block["personas"]):
                full = people[person]
                person += 1
                first, last = full.split(" ", 1)
                cohort_key = "%s-%s" % (_slug(block["geo"]), _slug(persona))
                email = "%s.%s@%s" % (first.lower(), last.lower(), domain)
                vanity = "%s-%s-%s-sandbox" % (first.lower(), last.lower(),
                                               _slug(persona))
                linkedin = "https://www.linkedin.com/in/%s" % vanity
                entered = WINDOW_START + datetime.timedelta(
                    days=rng.randrange(WINDOW_DAYS))
                # THE REAL KEY SHAPE IS A NAME SLUG, NOT A SLOT NUMBER.
                # Measured on the live `work/queue.jsonl`: contact keys there
                # are `kelly-smith`, `jacob-faertz`. This file first used
                # `c1`/`c2`/`c3`, which `store.validate` accepts - the only
                # rule it enforces is one key per contact - so nothing would
                # have failed, and every downstream join keyed on a person
                # would have been keyed on a position instead. All 300 people
                # are distinct, so the slug is unique inside its record.
                contact_key = _slug(full)
                records.append({
                    # `id` AND `key`, the real names. An earlier draft of this
                    # manifest called them `record_id` and `contact_key`,
                    # which are not field names this system uses: `id` is the
                    # record id and `key` is the contact key, and a reader
                    # joining this manifest to `queue_records` on the invented
                    # spellings would have joined on nothing.
                    "id": company_id,
                    "key": contact_key,
                    "company": name,
                    "domain": domain,
                    "cohort": cohort_key,
                    "block": block["block"],
                    "geo": block["geo"],
                    "industry": block["industry"],
                    "headcount_band": block["headcount_band"],
                    "employees": employees,
                    "signal": block["signal"],
                    "persona": persona,
                    "persona_family": family,
                    "name": full,
                    "first_name": first,
                    "last_name": last,
                    "title": persona,
                    "email": email,
                    "linkedin": linkedin,
                    "angle": angle,
                    "angle_wording": ANGLE_WORDING[angle],
                    "entered_at": entered.isoformat(),
                })
                # TWO SYNTHETIC PROVIDER VERDICTS, AS EVIDENCE.
                #
                # `verification.is_sendable` RECOMPUTES from this list every
                # time and never reads a stored `sendable` flag, so writing
                # `sendable: true` on the contact would do precisely nothing -
                # which is the whole design of that module and the reason the
                # email path can be exercised here at zero credits.
                #
                # Productive's resolved policy, read above from the client
                # config rather than restated: primary `deliverable`,
                # secondary `reoon`, `required_confirmations` 2,
                # `trust_secondary_when_primary_unknown` false. Two
                # independent `valid` verdicts is exactly what that policy
                # requires - no more, and the tests prove no less: one
                # confirmation alone returns False, and evidence recording a
                # DIFFERENT address returns False, because evidence is
                # address-bound by construction.
                #
                # Every entry says `synthetic sandbox fixture` in its reason
                # and carries the fixed VERDICT_AT. Nothing was verified; what
                # is modelled is the policy, and the policy is genuinely run.
                verdicts = [
                    verification.result(
                        policy["primary"], verification.S_VALID, email,
                        reason="synthetic sandbox fixture", charged=False,
                        at=VERDICT_AT),
                    verification.result(
                        policy["secondary"], verification.S_VALID, email,
                        reason="synthetic sandbox fixture", charged=False,
                        at=VERDICT_AT),
                ]
                contact = {
                    "key": contact_key,
                    "name": full,
                    "email": email,
                    "linkedin": linkedin,
                    "persona": family,
                    "title": persona,
                    "primary": slot == 0,
                    "angle": angle,
                    "email_source": "sandbox_fixture",
                    "verification": {"evidence": verdicts},
                    # NOT a stored opinion: computed from the evidence above
                    # through the real authority, so the stored field and the
                    # recomputation cannot disagree. A test asserts they
                    # still agree for all 300.
                    "sendable": None,
                    # A DNS lookup and two legacy verifier fields. Left None
                    # rather than filled: `mx` needs a resolver, and a stored
                    # `verdict`/`reoon` is read by
                    # `verification.legacy_evidence` and would be counted as
                    # a THIRD confirmation this fixture never obtained.
                    "mx": None,
                    "reoon": None,
                    "verdict": None,
                    # Issued by Bison on push. There has been no push.
                    "bison_lead_id": None,
                }
                contact["sendable"] = verification.is_sendable(contact, policy)
                contacts.append(contact)

            rec["contacts"] = contacts

            # Evidence AFTER the contacts, because each per-contact fact is
            # bound to its contact's key, persona and angle.
            rec["research"] = _evidence_for(rng, name, domain, company_id,
                                            block, city, employees, contacts)
            company_fact = rec["research"][0]
            for slot, contact in enumerate(contacts, start=1):
                # WITHOUT THIS LINK PERSONALISATION QUALITY CANNOT BE
                # COMPUTED. The evidence exists on the record and the contact
                # is the thing being written to; `selected_evidence_ids` is
                # what joins them.
                contact["personalization"] = {
                    "selected_evidence_ids": [
                        rec["research"][slot]["evidence_id"],
                        company_fact["evidence_id"],
                    ],
                }

            # `cadence.CADENCE_KEY` IS `cadence_steps`, AND IT IS A LIST.
            # `rec["cadence"] = {...}` - which `new_record` creates and leaves
            # empty - is a different key: a campaign carrying its sequence
            # under the wrong one gets "not part of the configured cadence for
            # this contact" on every step, with nothing else failing.
            rec[cadence.CADENCE_KEY] = [dict(step) for step in cadence.STEPS]

            # The remaining keys of the live record shape. PRESENT and EMPTY,
            # not populated: `events` and `waterfall` are the provider-call
            # audit trail, `stages` is what each pipeline stage writes when it
            # runs, and `qualification` is the qualify stage's computed
            # output. Inventing any of them would be fabricating a run.
            rec["batch"] = {"id": "sandbox-fixture-seed-%s" % seed}
            rec["stages"] = {}
            rec["events"] = []
            rec["waterfall"] = []
            rec["qualification"] = None

            queue_records.append(rec)
            company_index += 1

    return {
        "schema": SCHEMA,
        "seed": seed,
        "client": CLIENT,
        "lane": LANE,
        "synthetic": True,
        "generated_by": "scripts/sandbox_fixture.py",
        "provider_calls": 0,
        "data_credits_spent": 0,
        "window": {
            "start": WINDOW_START.isoformat(),
            "end": WINDOW_END.isoformat(),
            "days": WINDOW_DAYS,
        },
        "partition_note": (
            "Two blocks, three personas each, six cohorts of exactly 50. One "
            "geo per cohort and a 50-record floor caps the number of "
            "geographies at 300/150 = 2; see docs/sandbox/FIXTURE.md."
        ),
        "invariants": list(INVARIANTS),
        "null_without_a_provider": list(NULL_WITHOUT_A_PROVIDER),
        "cohorts": cohorts,
        "counts": {
            "records": len(records),
            "companies": len(companies),
            "cohorts": len(cohorts),
            "per_cohort": {cohort["key"]: cohort["size"] for cohort in cohorts},
        },
        "companies": companies,
        "records": records,
        "queue_records": queue_records,
    }


def dumps(fixture):
    """The one serialisation. `sort_keys` and a fixed separator are what make
    two runs of one seed byte-identical rather than merely equal as objects."""
    return json.dumps(fixture, indent=2, sort_keys=True,
                      ensure_ascii=True) + "\n"


def write(fixture, out):
    directory = os.path.dirname(os.path.abspath(out))
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Binary, so the platform cannot insert \r and break byte-identity
    # between a run here and a run anywhere else.
    with open(out, "wb") as handle:
        handle.write(dumps(fixture).encode("utf-8"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, required=True,
                        help="the only input; same seed, same bytes")
    parser.add_argument("--out", required=True, help="path to write")
    args = parser.parse_args(argv)
    fixture = build(args.seed)
    path = write(fixture, args.out)
    print("seed %d -> %s (%d records, %d companies, %d cohorts, %d bytes)"
          % (args.seed, path, fixture["counts"]["records"],
             fixture["counts"]["companies"], fixture["counts"]["cohorts"],
             os.path.getsize(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
