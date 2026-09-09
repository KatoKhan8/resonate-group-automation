#!/usr/bin/env python3
"""Demo signals: fictional observations, real evidence discipline.

What this has to demonstrate is not that signals exist but that they are
*read honestly*:

    a high-priority account that is nonetheless suppressed
    a fresh signal and a stale one on the same account
    a manual signal, visibly distinguished from a derived one
    an account with nothing happening, which stays low

Every entry carries evidence a person could quote back - "7 open
project-management roles", never "scaling rapidly". That is the same rule
the real constructor enforces, and a demo that broke it would be teaching
the wrong habit.

Nothing here is a real company or a real observation.
"""
import datetime

from .. import signals as S

# Demo records these attach to. `demo-acme` is the account-outreach
# fixture; the rest are from the Productive batch.
ACME = "demo-acme"


def _days_ago(days, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return (now - datetime.timedelta(days=days)).isoformat()


def build(workspace="productive", now=None):
    """The demo signal set. Manual source throughout - nothing observed it."""
    entry = []

    def add(record_id, kind, evidence, days, confidence=S.MEDIUM,
            contact_key=None):
        entry.append(S.signal(
            workspace, kind, record_id=record_id, contact_key=contact_key,
            evidence=evidence, source=S.MANUAL,
            observed_at=_days_ago(days, now), confidence=confidence,
            created_by="demo@resonate.test"))

    # --- Acme: the account the outreach demo is built around. Already has
    #     first-party signals (a positive reply, a referral); these push it
    #     into high priority so the tier is demonstrable.
    add(ACME, S.NEW_EXECUTIVE,
        "Michael Green announced as CFO on the company blog, 12 August",
        14, S.HIGH)
    add(ACME, S.HIRING_SURGE,
        "7 open project-management and delivery roles listed on the careers "
        "page", 6, S.HIGH)
    # ...and one that has aged out, so the screen can show the difference.
    add(ACME, S.WEBSITE_CHANGE,
        "services page rewritten around fixed-price delivery", 240, S.LOW)

    # --- Skyline Studio: high signal, and suppressed. The pair that matters
    #     most: a score of 80 and no permission to write.
    add("dach-software-008", S.FUNDING,
        "Series A of EUR 6m reported in the trade press, 2 August", 27,
        S.HIGH)
    add("dach-software-008", S.HEADCOUNT_GROWTH,
        "headcount on the team page rose from 140 to 171 over two quarters",
        20, S.MEDIUM)

    # --- Foxglove: one fresh account-level signal, nothing else.
    add("dach-software-002", S.HIRING_SURGE,
        "4 open operations roles listed", 3, S.MEDIUM)

    # --- Brightside: a stale signal only, so it reads as quiet.
    add("dach-software-004", S.COMPANY_NEWS,
        "named in a regional agency roundup", 300, S.LOW)

    return entry


def install(workspace="productive", now=None):
    """Write the demo signals. Called by `demodata.install`."""
    return S.install(build(workspace, now))
