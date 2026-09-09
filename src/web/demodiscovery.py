#!/usr/bin/env python3
"""Demo discovery: fictional candidates, real delta discipline.

What this has to demonstrate is not that discovery finds companies but
that it **subtracts honestly**:

    a genuinely new company
    a company already in the workspace
    a company already in a campaign
    a company an earlier run proposed
    a company the client has already ruled on
    a company on the suppression list

Six proposals, and only some of them survive. A demo where everything is
new would teach that the delta is decorative; it is the whole module.

Every candidate carries evidence a person could argue with, because
`discovery.candidate` refuses one that does not - the same rule the real
path enforces.

Nothing here is a real company and no provider was called.
"""
from .. import clientreview, discovery, ingest, store

RUN = "2026-08-24-weekly"

# Proposed by the (fictional) source this week. The domains that collide
# with the demo estate are deliberate: they are what makes the delta
# visible.
PROPOSED = (
    # --- genuinely new
    ("nordlicht-studio.test", "Nordlicht Studio",
     "digital agency in Hamburg, 55 staff listed on their team page",
     {"country": "Germany", "employee_band": "51-200"}),
    ("meridian-collective.test", "Meridian Collective",
     "brand and product studio, Rotterdam, 40 staff on the about page",
     {"country": "Netherlands", "employee_band": "11-50"}),
    ("halden-works.test", "Halden Works",
     "software consultancy, Oslo, 70 people listed on LinkedIn",
     {"country": "Norway", "employee_band": "51-200"}),
    # --- the client already told us about this one
    ("kestrel-digital.test", "Kestrel Digital",
     "performance marketing agency, Manchester, 45 staff",
     {"country": "United Kingdom", "employee_band": "11-50"}),
    # --- an earlier run proposed this
    ("brightside-group.test", "Brightside Group",
     "creative agency, Leeds, 60 staff listed",
     {"country": "United Kingdom", "employee_band": "51-200"}),
    # --- one the source listed twice, which is not two companies
    ("nordlicht-studio.test", "Nordlicht Studio GmbH",
     "agency in Hamburg, appears again under its registered name",
     {"country": "Germany"}),
)

# What an earlier run already proposed, so `SEEN_BEFORE` has something to
# fire on.
PREVIOUSLY = ("brightside-group.test",)

# What the client ruled on in a returned review file.
ALREADY_DECIDED = (
    ("kestrel-digital.test", clientreview.EXISTING_CLIENT,
     "We have worked with them since 2024"),
)


def build(workspace="productive", run=RUN):
    """This week's proposals. Fictional, evidenced, and not all new."""
    return [
        discovery.candidate(
            workspace, domain, source=discovery.PROVIDER,
            source_ref="demo-fixture", evidence=evidence, company=company,
            run=run, found_by="discovery@resonate.test", facts=facts)
        for domain, company, evidence, facts in PROPOSED]


def install(workspace="productive"):
    """Write the demo discovery history, this week's run, and the rulings.

    The earlier run is recorded first so this week's delta has something
    to find, and this week's proposals are recorded rather than returned:
    the API reads the store, and a demo fixture that the production path
    imported would be a demo fixture running in production.
    """
    earlier = [
        discovery.candidate(
            workspace, domain, source=discovery.PROVIDER,
            source_ref="demo-fixture", run="2026-08-17-weekly",
            evidence="proposed by an earlier weekly run",
            found_by="discovery@resonate.test")
        for domain in PREVIOUSLY]
    if earlier:
        discovery.record(earlier)

    discovery.record(build(workspace))

    clientreview.record([
        {"workspace": workspace, "domain": ingest.norm_domain(domain),
         "status": status, "notes": note, "at": store.now(),
         "run": "2026-08-17-weekly"}
        for domain, status, note in ALREADY_DECIDED])
    return discovery.load(workspace)
