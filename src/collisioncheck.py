#!/usr/bin/env python3
"""Collision check against provider truth, not the local ledger.

TASK-935. The local ledger says "never contacted" about people who have been
emailed six times, because the code that ingests sent events had zero
production callers. This module answers from the providers themselves.

Takes an email address and a company domain. Returns:

    CLEAR      neither the person nor the company appears in any campaign
    COLLISION  where it appears - provider, campaign id, campaign name
    UNKNOWN    a provider could not be fully read; UNKNOWN is not CLEAR

Both estates are covered: ours and the client's. The client's EmailBison
campaigns (327, 328, 352, 418) and HeyReach campaign ("FIXED - PRODUCTIVE")
are discovered from the provider, not hardcoded.

Rules:
    - READ ONLY. No write of any kind.
    - Paginate to exhaustion. An incomplete walk is UNKNOWN.
    - Timeouts are retried with backoff. A timeout that exhausts retries
      is UNKNOWN, never CLEAR.
"""
import time

from .providers import bison, heyreach
from .providers import (ProviderError, HttpTimeout, HttpTransportError,
                        request, ok)

CLEAR = "CLEAR"
COLLISION = "COLLISION"
UNKNOWN = "UNKNOWN"

# Retry budget for a single provider call that timed out. HeyReach's
# campaign/GetAll timed out at 25s on 2026-09-30; three attempts over
# ~15 seconds is enough to survive a transient stall without blocking
# the whole check for a minute.
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0


def _retry(fn, what):
    """Call fn() with retry+backoff on timeout. Returns the result or raises.

    Timeouts are retried because HeyReach's campaign/GetAll timed out at 25s
    on 2026-09-30 and the task requires reporting UNKNOWN rather than treating
    a timeout as an empty estate. Transport errors (connection refused, DNS
    failure) are also retried - the request demonstrably did not arrive.

    A ProviderError that is not a timeout is NOT retried - it is a real
    answer from the provider.
    """
    last_exc = None
    for attempt in range(max(1, RETRY_ATTEMPTS)):
        if attempt:
            time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
        try:
            return fn()
        except (HttpTimeout, HttpTransportError) as e:
            last_exc = e
    raise ProviderError(
        f"collisioncheck {what}: {RETRY_ATTEMPTS} attempts failed, last: "
        f"{type(last_exc).__name__}: {last_exc}") from last_exc


# --------------------------------------------------------- EmailBison
#
# find_lead_by_email searches across ALL leads in the workspace. The lead's
# lead_campaign_data lists every campaign the lead belongs to, with status.
# One or two calls answer the question for the whole estate - ours and the
# client's, because both are in the same workspace.

def _bison_campaign_name(campaign_id):
    """The provider's own name for this campaign. One read."""
    try:
        row = bison.campaign(campaign_id)
        return (row or {}).get("name")
    except Exception:
        return None


def check_email_bison(email):
    """Check EmailBison for this email address. Returns a verdict dict.

    {
        "provider": "emailbison",
        "verdict": CLEAR | COLLISION | UNKNOWN,
        "collisions": [{"campaign_id": ..., "campaign_name": ..., "status": ...}],
        "complete": True | False,
        "why": "..."   # only when UNKNOWN
    }
    """
    email = str(email or "").strip().lower()
    if not email or "@" not in email:
        return {"provider": "emailbison", "verdict": UNKNOWN,
                "collisions": [], "complete": False,
                "why": f"{email!r} is not a valid email address"}

    try:
        lead = _retry(lambda: bison.find_lead_by_email(email),
                      "emailbison find_lead_by_email")
    except ProviderError as e:
        return {"provider": "emailbison", "verdict": UNKNOWN,
                "collisions": [], "complete": False,
                "why": f"emailbison could not be asked: {e}"}

    if lead is None:
        return {"provider": "emailbison", "verdict": CLEAR,
                "collisions": [], "complete": True}

    campaign_data = lead.get("lead_campaign_data") or []
    if not isinstance(campaign_data, list):
        return {"provider": "emailbison", "verdict": UNKNOWN,
                "collisions": [], "complete": False,
                "why": "lead found but lead_campaign_data is not a list"}

    collisions = []
    for entry in campaign_data:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("campaign_id")
        if cid is None:
            continue
        name = _bison_campaign_name(cid)
        collisions.append({
            "campaign_id": cid,
            "campaign_name": name,
            "status": entry.get("status"),
            "emails_sent": entry.get("emails_sent"),
        })

    if collisions:
        return {"provider": "emailbison", "verdict": COLLISION,
                "collisions": collisions, "complete": True}
    return {"provider": "emailbison", "verdict": CLEAR,
            "collisions": [], "complete": True}


# --------------------------------------------------------- HeyReach
#
# HeyReach has no email search. The company domain is matched against each
# lead's companyName in every campaign. This requires walking all campaigns
# and all their leads - expensive, but the task requires pagination to
# exhaustion.

def _domain_label(domain):
    """The first label of a domain, for matching against company names.

    'example.com' -> 'example', 'sub.example.co.uk' -> 'sub'.
    Same approach as collision.search_term.
    """
    domain = str(domain or "").strip().lower()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[-1]
    parts = [p for p in domain.replace(".", " ").split() if p]
    return parts[0] if parts else domain


def _company_matches(company_name, domain_label):
    """Does this company name match the domain label? Case-insensitive."""
    if not company_name or not domain_label:
        return False
    return domain_label in str(company_name).lower()


def check_heyreach_company(domain, max_campaign_pages=50):
    """Check HeyReach for this company domain. Returns a verdict dict.

    Walks ALL campaigns and ALL their leads. A timeout or partial walk
    returns UNKNOWN, never CLEAR.

    {
        "provider": "heyreach",
        "verdict": CLEAR | COLLISION | UNKNOWN,
        "collisions": [{"campaign_id": ..., "campaign_name": ...,
                        "lead_profile_url": ..., "company_name": ...}],
        "complete": True | False,
        "campaigns_walked": N,
        "leads_walked": N,
        "why": "..."   # only when UNKNOWN
    }
    """
    label = _domain_label(domain)
    if not label:
        return {"provider": "heyreach", "verdict": UNKNOWN,
                "collisions": [], "complete": False,
                "campaigns_walked": 0, "leads_walked": 0,
                "why": f"{domain!r} produced no domain label to match"}

    # Step 1: enumerate all campaigns.
    try:
        all_campaigns = _retry(
            lambda: _all_heyreach_campaigns(max_campaign_pages),
            "heyreach campaigns")
    except ProviderError as e:
        return {"provider": "heyreach", "verdict": UNKNOWN,
                "collisions": [], "complete": False,
                "campaigns_walked": 0, "leads_walked": 0,
                "why": f"heyreach campaigns could not be listed: {e}"}

    campaigns_walked = len(all_campaigns)
    collisions = []
    leads_walked = 0

    # Step 2: for each campaign, walk all leads and check company name.
    for camp in all_campaigns:
        cid = camp.get("id")
        cname = camp.get("name")
        if cid is None:
            continue
        try:
            leads = _retry(
                lambda c=cid: _all_campaign_leads(c),
                f"heyreach campaign_leads({cid})")
        except ProviderError:
            return {"provider": "heyreach", "verdict": UNKNOWN,
                    "collisions": collisions, "complete": False,
                    "campaigns_walked": campaigns_walked,
                    "leads_walked": leads_walked,
                    "why": (f"heyreach campaign {cid} ({cname}) could not be "
                            f"fully read")}
        leads_walked += len(leads)
        for lead in leads:
            if _company_matches(lead.get("company_name"), label):
                collisions.append({
                    "campaign_id": cid,
                    "campaign_name": cname,
                    "lead_profile_url": lead.get("profile_url"),
                    "company_name": lead.get("company_name"),
                })

    if collisions:
        return {"provider": "heyreach", "verdict": COLLISION,
                "collisions": collisions, "complete": True,
                "campaigns_walked": campaigns_walked,
                "leads_walked": leads_walked}
    return {"provider": "heyreach", "verdict": CLEAR,
            "collisions": [], "complete": True,
            "campaigns_walked": campaigns_walked,
            "leads_walked": leads_walked}


def _all_heyreach_campaigns(max_pages=50):
    """Every HeyReach campaign, fully paginated. Raises on incomplete walk."""
    items, offset, total = [], 0, None
    for _ in range(max(1, max_pages)):
        page, page_total = heyreach.campaigns(offset, heyreach.MAX_PAGE)
        if not isinstance(page, list):
            raise ProviderError(
                "heyreach campaigns: response is not a list")
        items.extend(p for p in page if isinstance(p, dict))
        if page_total is not None:
            total = int(page_total)
        offset += len(page)
        if not page or (total is not None and offset >= total):
            break
    if total is not None and len(items) < total:
        raise ProviderError(
            f"heyreach campaigns: walked {len(items)} of {total} - "
            f"incomplete inventory")
    return items


def _all_campaign_leads(campaign_id, max_pages=500):
    """Every lead in one HeyReach campaign, fully paginated."""
    leads, offset, total = [], 0, None
    for _ in range(max(1, max_pages)):
        page, page_total = heyreach.campaign_leads(
            campaign_id, offset, heyreach.MAX_PAGE)
        if not isinstance(page, list):
            raise ProviderError(
                f"heyreach campaign_leads({campaign_id}): not a list")
        leads.extend(p for p in page if isinstance(p, dict))
        if page_total is not None:
            total = int(page_total)
        offset += len(page)
        if not page or (total is not None and offset >= total):
            break
    if total is not None and len(leads) < total:
        raise ProviderError(
            f"heyreach campaign_leads({campaign_id}): walked {len(leads)} "
            f"of {total} - incomplete inventory")
    return leads


# --------------------------------------------------------- combined

def check(email=None, company_domain=None):
    """Check both providers. Returns a combined verdict dict.

    {
        "verdict": CLEAR | COLLISION | UNKNOWN,
        "emailbison": {...},
        "heyreach": {...},
        "collisions": [...]   # all collisions from both providers
    }

    UNKNOWN from either provider makes the whole verdict UNKNOWN.
    COLLISION from either provider makes the whole verdict COLLISION.
    Only when both are CLEAR is the verdict CLEAR.
    """
    results = {}
    all_collisions = []

    if email:
        results["emailbison"] = check_email_bison(email)
        all_collisions.extend(
            {"provider": "emailbison", **c}
            for c in results["emailbison"].get("collisions", []))

    if company_domain:
        results["heyreach"] = check_heyreach_company(company_domain)
        all_collisions.extend(
            {"provider": "heyreach", **c}
            for c in results["heyreach"].get("collisions", []))

    # Combine verdicts: UNKNOWN > COLLISION > CLEAR.
    verdicts = [r.get("verdict") for r in results.values()]
    if UNKNOWN in verdicts:
        combined = UNKNOWN
    elif COLLISION in verdicts:
        combined = COLLISION
    else:
        combined = CLEAR

    return {
        "verdict": combined,
        "emailbison": results.get("emailbison"),
        "heyreach": results.get("heyreach"),
        "collisions": all_collisions,
    }
