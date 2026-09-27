"""LinkedIn profile match validation before enrollment.

TASK-268: a connection request to the wrong profile does not bounce - it
silently reaches a stranger. The URL we supply is accepted by HeyReach on
trust; nothing between the record and the wire verified that the profile at
that URL IS the person in the record.

The comparison is structural, not fuzzy. `src/linkedin.py` declares no-fuzzy-
matching as policy and this module respects it: a near-miss is a hold, not a
guess. Three fields must agree:

    surname         unique within the account AND matching the provider
    company         normalised token overlap
    location        normalised country, when both sides carry it

A match that cannot be made - no profile fetched, no surname to compare, a
surname that is not unique within the account - is a HOLD, not a pass. Fail
closed: the ambiguous record is never sent.
"""
import re


PASS = "pass"
HOLD = "hold"

# The hold reason code. Matches the namespace in src/holdreasons.py.
PROFILE_UNVERIFIED = "identity:profile_unverified"


class MatchResult:
    """The outcome of comparing one contact against a provider profile.

    `decision` is PASS or HOLD. `reasons` lists what disagreed or could not be
    checked. A PASS has an empty reasons list; a HOLD has at least one.
    """

    def __init__(self, decision, reasons=None, profile=None):
        self.decision = decision
        self.reasons = list(reasons or [])
        self.profile = profile

    def __repr__(self):
        return f"MatchResult({self.decision!r}, reasons={self.reasons!r})"

    def __eq__(self, other):
        if not isinstance(other, MatchResult):
            return NotImplemented
        return (self.decision == other.decision
                and self.reasons == other.reasons)


def _normalise_name(value):
    """Lower-case, strip diacritics approximated by ASCII folding, collapse
    whitespace. Good enough for surname comparison without a real normaliser.
    """
    if not value:
        return ""
    value = str(value).strip().lower()
    # Strip common diacritics by keeping only ASCII letters and spaces.
    value = re.sub(r"[^a-z\s\-]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _parse_surname(full_name):
    """The last token of a space-separated name. Empty string if nothing.

    A single-token name has no surname to compare - it is either a first name
    only or a mononym, and neither can be checked against a provider's
    lastName.
    """
    name = _normalise_name(full_name)
    if not name:
        return ""
    parts = name.split()
    if len(parts) < 2:
        return ""
    return parts[-1]


def _normalise_company(value):
    """Tokenise a company name into a set of lower-case alphabetic tokens.

    Punctuation, legal suffixes and common noise words are dropped. The
    comparison is set intersection: "Acme Corp" and "acme incorporated" share
    the token "acme" and that is enough to agree.
    """
    if not value:
        return set()
    value = _normalise_name(value)
    # Drop common legal suffixes that do not identify the company.
    noise = {"corp", "corporation", "inc", "incorporated", "llc", "ltd",
             "limited", "co", "company", "gmbh", "ag", "sa", "srl", "bv",
             "nv", "oy", "ab", "the"}
    tokens = set(value.split())
    return tokens - noise


def _normalise_location(value):
    """Extract the country from a location string, normalised.

    A location is typically "City, Country" or "City, State, Country". The
    last comma-separated token is taken as the country. A single-token
    location is returned as-is (it might be a country code).

    Returns empty string if the location is empty or unparseable.
    """
    if not value:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    # Take the last comma-separated segment as the country.
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        return ""
    country = parts[-1].lower()
    # Strip diacritics approximated by ASCII folding.
    country = re.sub(r"[^a-z\s]", "", country)
    return re.sub(r"\s+", " ", country).strip()


def _surname_count_in_account(record, contact_key):
    """Count how many contacts at this record share this contact's surname.

    A surname that appears more than once at the same account cannot
    distinguish between the people who carry it. The comparison needs to know
    whether a match is meaningful or merely coincidental.

    Returns the count including this contact. A contact with no parseable
    surname returns 0, which the caller treats as "cannot check".
    """
    contacts = record.get("contacts") or []
    this_contact = None
    for c in contacts:
        if c.get("key") == contact_key:
            this_contact = c
            break
    if not this_contact:
        return 0
    this_surname = _parse_surname(this_contact.get("name") or "")
    if not this_surname:
        return 0
    count = 0
    for c in contacts:
        if _parse_surname(c.get("name") or "") == this_surname:
            count += 1
    return count


def verify(contact_name, contact_key, company, record, profile,
           location=None):
    """Compare a contact against a provider-resolved profile.

    Arguments:
        contact_name: the contact's full name from our record
        contact_key: the contact's key (for surname uniqueness lookup)
        company: the company name from our record
        record: the full record (for surname uniqueness across contacts)
        profile: the provider-resolved profile dict (from heyreach.lead_profile)
        location: optional location from our record (if we have one)

    Returns a MatchResult. PASS means all available checks agreed. HOLD means
    at least one check failed or could not be made.

    The checks, in order:
        1. Profile must be present and non-empty.
        2. Surname must be parseable from our name.
        3. Surname must be unique within the account.
        4. Surname must match the provider's lastName.
        5. Company tokens must overlap.
        6. Location country must match, if both sides carry it.
    """
    if not profile:
        return MatchResult(HOLD, ["no profile to compare against"])

    reasons = []

    # --- Surname ---
    our_surname = _parse_surname(contact_name)
    provider_surname = _normalise_name(profile.get("lastName") or "")

    if not our_surname:
        reasons.append("no surname in our record to compare")
    elif not provider_surname:
        reasons.append("no surname in provider profile to compare")
    else:
        # Surname uniqueness within the account.
        count = _surname_count_in_account(record, contact_key)
        if count > 1:
            reasons.append(
                f"surname {our_surname!r} appears {count} times at this "
                f"account; cannot distinguish")
        if our_surname != provider_surname:
            reasons.append(
                f"surname mismatch: ours={our_surname!r}, "
                f"provider={provider_surname!r}")

    # --- Company ---
    our_company_tokens = _normalise_company(company)
    provider_company_tokens = _normalise_company(profile.get("companyName") or "")

    if not our_company_tokens:
        reasons.append("no company in our record to compare")
    elif not provider_company_tokens:
        reasons.append("no company in provider profile to compare")
    elif not (our_company_tokens & provider_company_tokens):
        reasons.append(
            f"company mismatch: ours={sorted(our_company_tokens)}, "
            f"provider={sorted(provider_company_tokens)}")

    # --- Location ---
    our_location = _normalise_location(location)
    provider_location = _normalise_location(profile.get("location") or "")

    if our_location and provider_location:
        if our_location != provider_location:
            reasons.append(
                f"location mismatch: ours={our_location!r}, "
                f"provider={provider_location!r}")
    # If either side lacks location, we cannot compare but do not hold on
    # that alone - the surname and company checks carry the load.

    if reasons:
        return MatchResult(HOLD, reasons, profile)
    return MatchResult(PASS, [], profile)
