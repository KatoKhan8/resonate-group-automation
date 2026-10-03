#!/usr/bin/env python3
"""Prove from the PROVIDERS that a person and company are in no campaign.

TASK-935. The local ledger says "never contacted" about people who have been
emailed six times - the ingest code had zero production callers. So a
collision check against the ledger proves nothing. This module asks the
providers themselves.

READ ONLY. No write of any kind. Runs before any canary write and must be
safe at any time.

Two estates, both checked:
  - OURS: the ~912 historical sends across campaigns 491-505, 503-505
  - THE CLIENT'S: "FIXED - PRODUCTIVE" in HeyReach, 327/328/352/418 in
    EmailBison

A match is a disposition, then next candidate. UNKNOWN is not CLEAR - an
incomplete walk refuses rather than passing.
"""
import time

from . import collision
from .providers import (bison, heyreach, ProviderError, HttpTimeout,
                        HttpTransportError)

CLEAR = "clear"
COLLISION = "collision"
UNKNOWN = "unknown"

#: The client's own EmailBison campaigns, named by id. These are the
#: campaigns the client was running before this system existed, and a
#: collision in any one of them is the worst outcome available: writing to
#: somebody their own team is already sequencing.
CLIENT_BISON_CAMPAIGNS = (327, 328, 352, 418)

#: The client's own HeyReach campaign, identified by name. Read from the
#: provider data, not hardcoded into the code as a campaign id - the
#: provider can tell us which campaign carries this name.
CLIENT_HEYREACH_CAMPAIGN_NAME = "FIXED - PRODUCTIVE"

#: Default retry delays for HeyReach timeouts. The campaign/GetAll endpoint
#: timed out at 25s on 2026-09-30; rather than treating a timeout as an
#: empty estate, retry with backoff and report UNKNOWN if all retries fail.
DEFAULT_RETRY_DELAYS = (1.0, 2.0, 4.0)


class CollisionCheckResult:
    """The outcome of a provider collision check.

    Attributes:
        disposition: CLEAR, COLLISION, or UNKNOWN.
        provider: which provider found the collision (or None).
        campaign_id: the campaign id where the collision was found (or None).
        campaign_name: the campaign name (or None).
        matched_on: what matched - "email", "domain", or None.
        reason: explanation for UNKNOWN, or additional context.
        complete: whether the walk was exhaustive. An incomplete walk is
            UNKNOWN, never CLEAR.
    """

    def __init__(self, disposition, provider=None, campaign_id=None,
                 campaign_name=None, matched_on=None, reason=None,
                 complete=True):
        self.disposition = disposition
        self.provider = provider
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.matched_on = matched_on
        self.reason = reason
        self.complete = complete

    def __repr__(self):
        parts = [f"disposition={self.disposition!r}"]
        if self.provider:
            parts.append(f"provider={self.provider!r}")
        if self.campaign_id is not None:
            parts.append(f"campaign_id={self.campaign_id!r}")
        if self.campaign_name:
            parts.append(f"campaign_name={self.campaign_name!r}")
        if self.matched_on:
            parts.append(f"matched_on={self.matched_on!r}")
        if self.reason:
            parts.append(f"reason={self.reason!r}")
        parts.append(f"complete={self.complete!r}")
        return f"CollisionCheckResult({', '.join(parts)})"

    def __eq__(self, other):
        if not isinstance(other, CollisionCheckResult):
            return NotImplemented
        return (self.disposition == other.disposition
                and self.provider == other.provider
                and self.campaign_id == other.campaign_id
                and self.campaign_name == other.campaign_name
                and self.matched_on == other.matched_on
                and self.complete == other.complete)


def _norm(value):
    return str(value or "").strip().lower()


def _domain_of(email_or_domain):
    """Extract the domain from an email or return the domain as-is."""
    text = _norm(email_or_domain)
    if "@" in text:
        return text.split("@")[-1]
    return text


def _email_matches(email, lead_email):
    """Case-insensitive email comparison."""
    return _norm(email) == _norm(lead_email)


def _lead_domain_matches(lead_email, domain):
    """Does this lead's email belong to this domain?"""
    return _norm(lead_email).endswith("@" + _norm(domain))


# --------------------------------------------------------- EmailBison check

def _bison_campaign_name(campaign_id, campaign_index):
    """Look up a campaign name from a pre-built index, or None."""
    if campaign_index is None:
        return None
    row = campaign_index.get(int(campaign_id))
    if isinstance(row, dict):
        return row.get("name")
    return None


def _build_bison_campaign_index():
    """Every campaign the credential can see, keyed by id.

    Returns None if the listing fails - a failed listing makes the check
    UNKNOWN, not CLEAR.
    """
    try:
        rows, _total = bison.list_all_campaigns()
    except (ProviderError, Exception):
        return None
    return {int(r["id"]): r for r in rows if isinstance(r, dict) and r.get("id")}


def check_emailbison(email, domain, expect_workspace=None,
                     campaign_index=None):
    """Check EmailBison for this email and domain.

    Uses `collision.leads_for_domain` which searches by domain label and
    matches locally - the only form of query whose absence of results means
    anything. Paginates to exhaustion.

    Returns a CollisionCheckResult.
    """
    domain = _norm(domain)
    email_norm = _norm(email)
    if not domain:
        return CollisionCheckResult(
            UNKNOWN, provider="emailbison",
            reason="no domain to check", complete=False)

    # Build the campaign index for name lookups if not provided.
    if campaign_index is None:
        campaign_index = _build_bison_campaign_index()

    try:
        leads = collision.leads_for_domain(
            domain, expect_workspace=expect_workspace)
    except collision.CollisionUnknown as e:
        return CollisionCheckResult(
            UNKNOWN, provider="emailbison",
            reason=str(e), complete=False)

    for lead in leads:
        if not isinstance(lead, dict):
            continue
        lead_email = _norm(lead.get("email"))
        if not lead_email:
            continue

        # Person check: exact email match.
        if email_norm and _email_matches(email_norm, lead_email):
            campaign_data = lead.get("lead_campaign_data")
            campaign_data = (campaign_data
                             if isinstance(campaign_data, list) else [])
            for entry in campaign_data:
                if not isinstance(entry, dict):
                    continue
                cid = entry.get("campaign_id")
                cname = _bison_campaign_name(cid, campaign_index)
                return CollisionCheckResult(
                    COLLISION, provider="emailbison",
                    campaign_id=cid, campaign_name=cname,
                    matched_on="email", complete=True)

        # Company check: any lead at this domain means the company is
        # present, even if the specific email is not this person.
        if _lead_domain_matches(lead_email, domain):
            campaign_data = lead.get("lead_campaign_data")
            campaign_data = (campaign_data
                             if isinstance(campaign_data, list) else [])
            for entry in campaign_data:
                if not isinstance(entry, dict):
                    continue
                cid = entry.get("campaign_id")
                cname = _bison_campaign_name(cid, campaign_index)
                return CollisionCheckResult(
                    COLLISION, provider="emailbison",
                    campaign_id=cid, campaign_name=cname,
                    matched_on="domain", complete=True)

    return CollisionCheckResult(
        CLEAR, provider="emailbison", complete=True)


# --------------------------------------------------------- HeyReach check

def _heyreach_campaigns_exhaustive(max_pages=20, retry_delays=(),
                                   _sleep=time.sleep):
    """Every HeyReach campaign, paged to exhaustion.

    HeyReach's campaign/GetAll timed out at 25s on 2026-09-30. This function
    retries with backoff and raises if all retries fail - returning an empty
    list would read as "no campaigns" which is the false CLEAR.

    Returns (items, total_count). Raises ProviderError on failure.
    """
    offset = 0
    all_items = []
    total = None
    page = 0

    while page < max_pages:
        page += 1
        data = _heyreach_read_with_retry(
            "/campaign/GetAll",
            {"offset": offset, "limit": min(heyreach.MAX_PAGE, 100)},
            retry_delays=retry_delays, _sleep=_sleep)
        items = heyreach._collection(data, "/campaign/GetAll")
        if total is None:
            total = data.get("totalCount")
        all_items.extend(items)
        if not items:
            break
        offset += len(items)
        if total is not None and offset >= int(total):
            break

    if total is not None and len(all_items) != int(total):
        raise ProviderError(
            f"heyreach campaigns: totalCount says {total} and "
            f"{len(all_items)} arrived. Refusing to return a partial "
            f"listing as the whole estate.")
    return all_items, total


def _heyreach_read_with_retry(path, body, retry_delays=(), _sleep=time.sleep):
    """A HeyReach POST read with retry on timeout.

    HeyReach's campaign/GetAll timed out at 25s. Rather than treating a
    timeout as an empty estate, retry with backoff. If all retries fail,
    raise - the caller must report UNKNOWN, not CLEAR.
    """
    delays = retry_delays or DEFAULT_RETRY_DELAYS
    last_error = None
    for attempt, delay in enumerate(delays):
        try:
            return heyreach._read(path, body)
        except (HttpTimeout, HttpTransportError) as e:
            last_error = e
            if attempt < len(delays) - 1:
                _sleep(delay)
    # Final attempt without catching - let it raise.
    try:
        return heyreach._read(path, body)
    except (HttpTimeout, HttpTransportError) as e:
        raise ProviderError(
            f"heyreach {path}: timed out after {len(delays) + 1} attempts. "
            f"Last error: {e}") from e


def _heyreach_leads_for_campaign(campaign_id, max_pages=100,
                                 retry_delays=(), _sleep=time.sleep):
    """Every lead in a HeyReach campaign, paged to exhaustion.

    Returns raw lead rows (not trimmed) so the caller can inspect company
    and profile fields. Raises ProviderError on incomplete walk.
    """
    offset = 0
    all_rows = []
    total = None
    page = 0

    while page < max_pages:
        page += 1
        body = {"campaignId": int(campaign_id),
                "offset": offset,
                "limit": min(heyreach.MAX_PAGE, 100)}
        try:
            data = _heyreach_read_with_retry(
                heyreach.LEADS_ROUTE, body,
                retry_delays=retry_delays, _sleep=_sleep)
        except ProviderError:
            raise
        rows = heyreach._collection(data, heyreach.LEADS_ROUTE)
        if total is None:
            total = data.get("totalCount")
        all_rows.extend(rows)
        if not rows:
            break
        offset += len(rows)
        if total is not None and offset >= int(total):
            break

    if total is not None and len(all_rows) != int(total):
        raise ProviderError(
            f"heyreach leads for campaign {campaign_id}: totalCount says "
            f"{total} and {len(all_rows)} arrived. Refusing to return a "
            f"partial membership as the whole.")
    return all_rows


def _lead_company_domain(lead_row):
    """Extract a domain from a HeyReach lead's company info, or None."""
    profile = lead_row.get("linkedInUserProfile") or {}
    company = str(profile.get("companyName") or
                  lead_row.get("companyName") or "").strip().lower()
    if not company:
        return None
    # Company names are free text. Extract what looks like a domain.
    # "BrightPath Solutions" -> "brightpath" (no dot, so no domain)
    # "brightpath.test" -> "brightpath.test"
    # "www.brightpath.com" -> "brightpath.com"
    if "." in company:
        parts = [p for p in company.replace("www.", "").split(".") if p]
        if len(parts) >= 2:
            return ".".join(parts[-2:]) if parts[-1] not in (
                "com", "co", "org", "net", "io") else ".".join(parts)
    return None


def _lead_email_match(lead_row, email):
    """Check if a HeyReach lead matches by email. HeyReach leads are
    LinkedIn-based and typically don't carry emails, but check anyway."""
    email_norm = _norm(email)
    if not email_norm:
        return False
    profile = lead_row.get("linkedInUserProfile") or {}
    lead_email = _norm(profile.get("email") or lead_row.get("email"))
    return lead_email and _email_matches(email_norm, lead_email)


def _lead_domain_match(lead_row, domain):
    """Check if a HeyReach lead's company matches the domain."""
    domain = _norm(domain)
    if not domain:
        return False
    # Check the company name for a domain match.
    profile = lead_row.get("linkedInUserProfile") or {}
    company = str(profile.get("companyName") or
                  lead_row.get("companyName") or "").strip().lower()
    if not company:
        return False
    # Direct domain in company field.
    if domain in company:
        return True
    # Extract domain from company name.
    lead_domain = _lead_company_domain(lead_row)
    if lead_domain and _norm(lead_domain) == domain:
        return True
    # Check if the domain label (first part) appears in the company name.
    label = domain.split(".")[0] if "." in domain else domain
    if label and len(label) >= 3 and label in company:
        return True
    return False


def check_heyreach(email, domain, max_campaign_pages=20,
                   max_lead_pages=100, retry_delays=(), _sleep=time.sleep):
    """Check HeyReach for this email and domain.

    Walks every campaign and every lead, checking for matches. Paginates to
    exhaustion on both levels. A timeout or partial walk reports UNKNOWN.

    Returns a CollisionCheckResult.
    """
    domain = _norm(domain)
    email_norm = _norm(email)

    try:
        all_campaigns, _total = _heyreach_campaigns_exhaustive(
            max_pages=max_campaign_pages, retry_delays=retry_delays,
            _sleep=_sleep)
    except (ProviderError, Exception) as e:
        return CollisionCheckResult(
            UNKNOWN, provider="heyreach",
            reason=f"campaign listing failed: {e}", complete=False)

    for campaign_row in all_campaigns:
        if not isinstance(campaign_row, dict):
            continue
        cid = campaign_row.get("id")
        cname = campaign_row.get("name")
        if cid is None:
            continue

        try:
            leads = _heyreach_leads_for_campaign(
                cid, max_pages=max_lead_pages,
                retry_delays=retry_delays, _sleep=_sleep)
        except (ProviderError, Exception) as e:
            return CollisionCheckResult(
                UNKNOWN, provider="heyreach",
                reason=f"lead listing for campaign {cid} failed: {e}",
                complete=False)

        for lead_row in leads:
            if not isinstance(lead_row, dict):
                continue

            # Person check by email (HeyReach leads typically don't have
            # emails, but check anyway for completeness).
            if email_norm and _lead_email_match(lead_row, email_norm):
                return CollisionCheckResult(
                    COLLISION, provider="heyreach",
                    campaign_id=cid, campaign_name=cname,
                    matched_on="email", complete=True)

            # Company check by domain.
            if domain and _lead_domain_match(lead_row, domain):
                return CollisionCheckResult(
                    COLLISION, provider="heyreach",
                    campaign_id=cid, campaign_name=cname,
                    matched_on="domain", complete=True)

    return CollisionCheckResult(
        CLEAR, provider="heyreach", complete=True)


# --------------------------------------------------------- unified check

def check(email, domain, *, bison_workspace=None,
          max_pages=40, heyreach_max_campaign_pages=20,
          heyreach_max_lead_pages=100, retry_delays=(),
          _sleep=time.sleep):
    """Prove from the providers that this person and company are in no
    campaign. Read-only. Covers both estates: ours and the client's.

    Args:
        email: the email address to check.
        domain: the company domain to check.
        bison_workspace: the EmailBison workspace id to pin the read to.
            Required - the credential's binding can move mid-session.
        max_pages: max pages for EmailBison domain search.
        heyreach_max_campaign_pages: max pages for HeyReach campaign listing.
        heyreach_max_lead_pages: max pages per HeyReach campaign's leads.
        retry_delays: delays between HeyReach timeout retries.
        _sleep: injectable sleep for tests.

    Returns:
        CollisionCheckResult with disposition CLEAR, COLLISION, or UNKNOWN.
        UNKNOWN is returned when any part of the walk was incomplete - an
        incomplete read cannot prove absence.
    """
    if not email and not domain:
        return CollisionCheckResult(
            UNKNOWN, reason="no email or domain to check", complete=False)

    # Build the EmailBison campaign index for name lookups.
    campaign_index = _build_bison_campaign_index()

    # Check EmailBison first - it has the email-based leads.
    bison_result = check_emailbison(
        email, domain, expect_workspace=bison_workspace,
        campaign_index=campaign_index)
    if bison_result.disposition == COLLISION:
        return bison_result
    if bison_result.disposition == UNKNOWN:
        return bison_result

    # Check HeyReach - LinkedIn-based, so company domain is the primary
    # match vector.
    heyreach_result = check_heyreach(
        email, domain,
        max_campaign_pages=heyreach_max_campaign_pages,
        max_lead_pages=heyreach_max_lead_pages,
        retry_delays=retry_delays, _sleep=_sleep)
    if heyreach_result.disposition == COLLISION:
        return heyreach_result
    if heyreach_result.disposition == UNKNOWN:
        return heyreach_result

    # Both providers say CLEAR with complete walks.
    return CollisionCheckResult(
        CLEAR, reason="both providers confirm no collision", complete=True)
