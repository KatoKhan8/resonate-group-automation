#!/usr/bin/env python3
"""Where a company is, and what time it is there.

Timezone is a campaign field rather than a display detail. An email that lands
at 04:00 local is worse than one that never arrives: it is visibly automated,
and it is the kind of mistake a prospect remembers. So the timezone is stored
as an IANA name - Europe/London, not UTC+0 - because an offset is only true
for half the year, and the half it is wrong for is the half nobody checks.

Three fields travel together and none of them is optional:

    timezone             the IANA name, or None
    timezone_source      what the answer was derived from
    timezone_confidence  high / medium / low / unknown

Where the answer is ambiguous - a country spanning several zones, a city we
cannot place - the timezone is None and scheduling is **held**. A guessed
timezone is worse than a missing one, because a missing one stops the send and
a guessed one sends at the wrong time confidently.

  python -m src.geo --country "United Kingdom"
  python -m src.geo --window Europe/Zagreb --date 2026-07-15
"""
import argparse
import datetime
import json

# ------------------------------------------------------------- confidence

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
UNKNOWN = "unknown"
CONFIDENCE = (HIGH, MEDIUM, LOW, UNKNOWN)

# What the timezone was derived from, most trustworthy first.
FROM_CITY = "city"
FROM_COUNTRY_SINGLE = "country_single_zone"
FROM_COUNTRY_DEFAULT = "country_dominant_zone"
FROM_REGION = "region_default"
FROM_TLD = "tld"
SOURCES = (FROM_CITY, FROM_COUNTRY_SINGLE, FROM_COUNTRY_DEFAULT, FROM_REGION,
           FROM_TLD)


# ------------------------------------------------------------- the regions
#
# GTM regions, not geography. "DACH" and "Nordics" exist because campaigns are
# planned that way; the country stays stored separately so a region can be
# redrawn without losing what was actually known.

UK = "UK"
DACH = "DACH"
NORDICS = "Nordics"
BENELUX = "Benelux"
CEE = "CEE"
SOUTHERN_EUROPE = "Southern Europe"
US_EAST = "US East"
US_CENTRAL = "US Central"
US_WEST = "US West"
CANADA = "Canada"
ANZ = "Australia / New Zealand"
OTHER = "Other"

REGIONS = (UK, DACH, NORDICS, BENELUX, CEE, SOUTHERN_EUROPE, US_EAST,
           US_CENTRAL, US_WEST, CANADA, ANZ, OTHER)

# country (lower case) -> (ISO2, region, timezone or None, source)
#
# A timezone of None means the country spans zones we cannot choose between
# from the country alone. The United States is the obvious case and it is
# handled by state/city below rather than by picking one.
COUNTRIES = {
    "united kingdom": ("GB", UK, "Europe/London", FROM_COUNTRY_SINGLE),
    "great britain": ("GB", UK, "Europe/London", FROM_COUNTRY_SINGLE),
    "england": ("GB", UK, "Europe/London", FROM_COUNTRY_SINGLE),
    "scotland": ("GB", UK, "Europe/London", FROM_COUNTRY_SINGLE),
    "wales": ("GB", UK, "Europe/London", FROM_COUNTRY_SINGLE),
    "northern ireland": ("GB", UK, "Europe/London", FROM_COUNTRY_SINGLE),
    "ireland": ("IE", UK, "Europe/Dublin", FROM_COUNTRY_SINGLE),

    "germany": ("DE", DACH, "Europe/Berlin", FROM_COUNTRY_SINGLE),
    "austria": ("AT", DACH, "Europe/Vienna", FROM_COUNTRY_SINGLE),
    "switzerland": ("CH", DACH, "Europe/Zurich", FROM_COUNTRY_SINGLE),

    "sweden": ("SE", NORDICS, "Europe/Stockholm", FROM_COUNTRY_SINGLE),
    "norway": ("NO", NORDICS, "Europe/Oslo", FROM_COUNTRY_SINGLE),
    "denmark": ("DK", NORDICS, "Europe/Copenhagen", FROM_COUNTRY_SINGLE),
    "finland": ("FI", NORDICS, "Europe/Helsinki", FROM_COUNTRY_SINGLE),
    "iceland": ("IS", NORDICS, "Atlantic/Reykjavik", FROM_COUNTRY_SINGLE),

    "netherlands": ("NL", BENELUX, "Europe/Amsterdam", FROM_COUNTRY_SINGLE),
    "belgium": ("BE", BENELUX, "Europe/Brussels", FROM_COUNTRY_SINGLE),
    "luxembourg": ("LU", BENELUX, "Europe/Luxembourg", FROM_COUNTRY_SINGLE),

    "poland": ("PL", CEE, "Europe/Warsaw", FROM_COUNTRY_SINGLE),
    "czech republic": ("CZ", CEE, "Europe/Prague", FROM_COUNTRY_SINGLE),
    "czechia": ("CZ", CEE, "Europe/Prague", FROM_COUNTRY_SINGLE),
    "slovakia": ("SK", CEE, "Europe/Bratislava", FROM_COUNTRY_SINGLE),
    "hungary": ("HU", CEE, "Europe/Budapest", FROM_COUNTRY_SINGLE),
    "romania": ("RO", CEE, "Europe/Bucharest", FROM_COUNTRY_SINGLE),
    "bulgaria": ("BG", CEE, "Europe/Sofia", FROM_COUNTRY_SINGLE),
    "croatia": ("HR", CEE, "Europe/Zagreb", FROM_COUNTRY_SINGLE),
    "slovenia": ("SI", CEE, "Europe/Ljubljana", FROM_COUNTRY_SINGLE),
    "serbia": ("RS", CEE, "Europe/Belgrade", FROM_COUNTRY_SINGLE),
    "bosnia and herzegovina": ("BA", CEE, "Europe/Sarajevo",
                               FROM_COUNTRY_SINGLE),
    "estonia": ("EE", CEE, "Europe/Tallinn", FROM_COUNTRY_SINGLE),
    "latvia": ("LV", CEE, "Europe/Riga", FROM_COUNTRY_SINGLE),
    "lithuania": ("LT", CEE, "Europe/Vilnius", FROM_COUNTRY_SINGLE),

    "spain": ("ES", SOUTHERN_EUROPE, "Europe/Madrid", FROM_COUNTRY_DEFAULT),
    "portugal": ("PT", SOUTHERN_EUROPE, "Europe/Lisbon", FROM_COUNTRY_DEFAULT),
    "italy": ("IT", SOUTHERN_EUROPE, "Europe/Rome", FROM_COUNTRY_SINGLE),
    "greece": ("GR", SOUTHERN_EUROPE, "Europe/Athens", FROM_COUNTRY_SINGLE),
    "malta": ("MT", SOUTHERN_EUROPE, "Europe/Malta", FROM_COUNTRY_SINGLE),
    "cyprus": ("CY", SOUTHERN_EUROPE, "Asia/Nicosia", FROM_COUNTRY_SINGLE),
    "france": ("FR", SOUTHERN_EUROPE, "Europe/Paris", FROM_COUNTRY_DEFAULT),

    # Spans six zones. Never resolved from the country alone.
    "united states": ("US", None, None, None),
    "usa": ("US", None, None, None),
    "united states of america": ("US", None, None, None),
    # Spans six zones as well, and the population is concentrated in the east
    # - which is a reason to look at the city, not a reason to assume.
    "canada": ("CA", CANADA, None, None),

    "australia": ("AU", ANZ, None, None),      # spans three
    "new zealand": ("NZ", ANZ, "Pacific/Auckland", FROM_COUNTRY_SINGLE),
}

ISO_TO_COUNTRY = {}
for _name, (_iso, _region, _tz, _source) in COUNTRIES.items():
    ISO_TO_COUNTRY.setdefault(_iso, _name)


# US states and Canadian provinces to region and zone. A US company without a
# state or a recognised city stays unresolved rather than becoming Eastern.
US_STATES = {
    # East
    "new york": (US_EAST, "America/New_York"),
    "ny": (US_EAST, "America/New_York"),
    "massachusetts": (US_EAST, "America/New_York"),
    "ma": (US_EAST, "America/New_York"),
    "pennsylvania": (US_EAST, "America/New_York"),
    "pa": (US_EAST, "America/New_York"),
    "florida": (US_EAST, "America/New_York"),
    "fl": (US_EAST, "America/New_York"),
    "georgia": (US_EAST, "America/New_York"),
    "ga": (US_EAST, "America/New_York"),
    "north carolina": (US_EAST, "America/New_York"),
    "nc": (US_EAST, "America/New_York"),
    "virginia": (US_EAST, "America/New_York"),
    "va": (US_EAST, "America/New_York"),
    "new jersey": (US_EAST, "America/New_York"),
    "nj": (US_EAST, "America/New_York"),
    "connecticut": (US_EAST, "America/New_York"),
    "maryland": (US_EAST, "America/New_York"),
    "district of columbia": (US_EAST, "America/New_York"),
    "dc": (US_EAST, "America/New_York"),
    "ohio": (US_EAST, "America/New_York"),
    "michigan": (US_EAST, "America/New_York"),
    # Central
    "illinois": (US_CENTRAL, "America/Chicago"),
    "il": (US_CENTRAL, "America/Chicago"),
    "texas": (US_CENTRAL, "America/Chicago"),
    "tx": (US_CENTRAL, "America/Chicago"),
    "minnesota": (US_CENTRAL, "America/Chicago"),
    "mn": (US_CENTRAL, "America/Chicago"),
    "missouri": (US_CENTRAL, "America/Chicago"),
    "wisconsin": (US_CENTRAL, "America/Chicago"),
    "tennessee": (US_CENTRAL, "America/Chicago"),
    "louisiana": (US_CENTRAL, "America/Chicago"),
    "oklahoma": (US_CENTRAL, "America/Chicago"),
    "iowa": (US_CENTRAL, "America/Chicago"),
    "kansas": (US_CENTRAL, "America/Chicago"),
    "nebraska": (US_CENTRAL, "America/Chicago"),
    # West
    "california": (US_WEST, "America/Los_Angeles"),
    "ca": (US_WEST, "America/Los_Angeles"),
    "washington": (US_WEST, "America/Los_Angeles"),
    "wa": (US_WEST, "America/Los_Angeles"),
    "oregon": (US_WEST, "America/Los_Angeles"),
    "or": (US_WEST, "America/Los_Angeles"),
    "nevada": (US_WEST, "America/Los_Angeles"),
    "colorado": (US_WEST, "America/Denver"),
    "co": (US_WEST, "America/Denver"),
    "arizona": (US_WEST, "America/Phoenix"),
    "az": (US_WEST, "America/Phoenix"),
    "utah": (US_WEST, "America/Denver"),
    "new mexico": (US_WEST, "America/Denver"),
}

# Cities distinctive enough to place without a country. Deliberately short:
# every entry is a claim, and "Springfield" is a claim nobody can defend.
CITIES = {
    "london": ("GB", UK, "Europe/London"),
    "manchester": ("GB", UK, "Europe/London"),
    "bristol": ("GB", UK, "Europe/London"),
    "edinburgh": ("GB", UK, "Europe/London"),
    "glasgow": ("GB", UK, "Europe/London"),
    "leeds": ("GB", UK, "Europe/London"),
    "dublin": ("IE", UK, "Europe/Dublin"),
    "berlin": ("DE", DACH, "Europe/Berlin"),
    "munich": ("DE", DACH, "Europe/Berlin"),
    "hamburg": ("DE", DACH, "Europe/Berlin"),
    "cologne": ("DE", DACH, "Europe/Berlin"),
    "frankfurt": ("DE", DACH, "Europe/Berlin"),
    "vienna": ("AT", DACH, "Europe/Vienna"),
    "zurich": ("CH", DACH, "Europe/Zurich"),
    "geneva": ("CH", DACH, "Europe/Zurich"),
    "stockholm": ("SE", NORDICS, "Europe/Stockholm"),
    "gothenburg": ("SE", NORDICS, "Europe/Stockholm"),
    "malmo": ("SE", NORDICS, "Europe/Stockholm"),
    "oslo": ("NO", NORDICS, "Europe/Oslo"),
    "copenhagen": ("DK", NORDICS, "Europe/Copenhagen"),
    "helsinki": ("FI", NORDICS, "Europe/Helsinki"),
    "amsterdam": ("NL", BENELUX, "Europe/Amsterdam"),
    "rotterdam": ("NL", BENELUX, "Europe/Amsterdam"),
    "utrecht": ("NL", BENELUX, "Europe/Amsterdam"),
    "brussels": ("BE", BENELUX, "Europe/Brussels"),
    "antwerp": ("BE", BENELUX, "Europe/Brussels"),
    "warsaw": ("PL", CEE, "Europe/Warsaw"),
    "krakow": ("PL", CEE, "Europe/Warsaw"),
    "prague": ("CZ", CEE, "Europe/Prague"),
    "budapest": ("HU", CEE, "Europe/Budapest"),
    "bucharest": ("RO", CEE, "Europe/Bucharest"),
    "zagreb": ("HR", CEE, "Europe/Zagreb"),
    "ljubljana": ("SI", CEE, "Europe/Ljubljana"),
    "belgrade": ("RS", CEE, "Europe/Belgrade"),
    "tallinn": ("EE", CEE, "Europe/Tallinn"),
    "madrid": ("ES", SOUTHERN_EUROPE, "Europe/Madrid"),
    "barcelona": ("ES", SOUTHERN_EUROPE, "Europe/Madrid"),
    "lisbon": ("PT", SOUTHERN_EUROPE, "Europe/Lisbon"),
    "porto": ("PT", SOUTHERN_EUROPE, "Europe/Lisbon"),
    "milan": ("IT", SOUTHERN_EUROPE, "Europe/Rome"),
    "rome": ("IT", SOUTHERN_EUROPE, "Europe/Rome"),
    "athens": ("GR", SOUTHERN_EUROPE, "Europe/Athens"),
    "paris": ("FR", SOUTHERN_EUROPE, "Europe/Paris"),
    "new york": ("US", US_EAST, "America/New_York"),
    "brooklyn": ("US", US_EAST, "America/New_York"),
    "boston": ("US", US_EAST, "America/New_York"),
    "philadelphia": ("US", US_EAST, "America/New_York"),
    "atlanta": ("US", US_EAST, "America/New_York"),
    "miami": ("US", US_EAST, "America/New_York"),
    "chicago": ("US", US_CENTRAL, "America/Chicago"),
    "austin": ("US", US_CENTRAL, "America/Chicago"),
    "dallas": ("US", US_CENTRAL, "America/Chicago"),
    "houston": ("US", US_CENTRAL, "America/Chicago"),
    "minneapolis": ("US", US_CENTRAL, "America/Chicago"),
    "san francisco": ("US", US_WEST, "America/Los_Angeles"),
    "los angeles": ("US", US_WEST, "America/Los_Angeles"),
    "seattle": ("US", US_WEST, "America/Los_Angeles"),
    "portland": ("US", US_WEST, "America/Los_Angeles"),
    "san diego": ("US", US_WEST, "America/Los_Angeles"),
    "denver": ("US", US_WEST, "America/Denver"),
    "phoenix": ("US", US_WEST, "America/Phoenix"),
    "toronto": ("CA", CANADA, "America/Toronto"),
    "ottawa": ("CA", CANADA, "America/Toronto"),
    "montreal": ("CA", CANADA, "America/Toronto"),
    "vancouver": ("CA", CANADA, "America/Vancouver"),
    "calgary": ("CA", CANADA, "America/Edmonton"),
    "sydney": ("AU", ANZ, "Australia/Sydney"),
    "melbourne": ("AU", ANZ, "Australia/Melbourne"),
    "brisbane": ("AU", ANZ, "Australia/Brisbane"),
    "perth": ("AU", ANZ, "Australia/Perth"),
    "adelaide": ("AU", ANZ, "Australia/Adelaide"),
    "auckland": ("NZ", ANZ, "Pacific/Auckland"),
    "wellington": ("NZ", ANZ, "Pacific/Auckland"),
}


def _clean(value):
    return " ".join(str(value or "").strip().lower().replace(",", " ").split())


def region_settings(config):
    """Region mapping is configurable: a client may redraw or rename one.

    Only known region names are accepted, and only known countries may be
    moved, so a typo produces a dropped override rather than a silent region
    nobody can filter on.
    """
    block = ((config or {}).get("segmentation") or {}).get("regions") or {}
    overrides = {}
    for country, region in block.items():
        country = _clean(country)
        region = str(region).strip()
        if country in COUNTRIES and region in REGIONS:
            overrides[country] = region
    return overrides


# --------------------------------------------------------------- resolving

def _blank(reason):
    return {"country": None, "country_code": None, "region": OTHER,
            "region_confidence": UNKNOWN, "city": None, "timezone": None,
            "timezone_source": None, "timezone_confidence": UNKNOWN,
            "why": reason}


def _iso_code(value):
    """If value is a two-letter ISO country code, return it uppercased."""
    raw = str(value or "").strip()
    if len(raw) == 2 and raw.isalpha():
        return raw.upper()
    return None


def _try_city_from_segments(text):
    """Try each comma-separated segment of text as a city name.

    Whole-token matching via _contains_phrase on each segment, so "Newcastle"
    never matches "New York". Returns the first city key found, or None.
    """
    for segment in text.split(","):
        cleaned = _clean(segment)
        if not cleaned:
            continue
        for name in CITIES:
            if _contains_phrase(cleaned, name):
                return name
    return None


def resolve(country=None, city=None, state=None, config=None, places=None):
    """Country, region and timezone from whatever location evidence exists.

    Order matters: a city is a stronger claim than a country, and a US state
    is the only thing that makes a US company schedulable.
    """
    overrides = region_settings(config)
    country_text = _clean(country)
    city_text = _clean(city)
    state_text = _clean(state)

    # A two-letter ISO code as the country argument maps through ISO_TO_COUNTRY.
    # The confidence is MEDIUM rather than HIGH: an ISO code places the country
    # but is weaker evidence than a city or a country name.
    iso_source = False
    iso_hint = _iso_code(country)
    if iso_hint and iso_hint in ISO_TO_COUNTRY and country_text not in COUNTRIES:
        country_text = ISO_TO_COUNTRY[iso_hint]
        iso_source = True

    # Free text - "Stockholm, Sweden" - as a last resort, matched on whole
    # tokens so "Newcastle" never matches "New York". Each comma-separated
    # segment is also tried as a city, because office strings put the city
    # at varying positions. A city is searched for even when the country is
    # already known: an ISO code places the country but the city is the
    # stronger evidence and may upgrade the confidence.
    if places and not city_text:
        text = _clean(places)
        for name in CITIES:
            if _contains_phrase(text, name):
                city_text = name
                break
        if not city_text:
            city_text = _try_city_from_segments(places)
        if not country_text:
            for name in COUNTRIES:
                if _contains_phrase(text, name):
                    country_text = name
                    break

    if city_text in CITIES:
        iso, region, zone = CITIES[city_text]
        country_name = ISO_TO_COUNTRY.get(iso)
        return {
            "country": country_name,
            "country_code": iso,
            "region": overrides.get(country_name or "", region),
            "region_confidence": HIGH,
            "city": city_text,
            "timezone": zone,
            "timezone_source": FROM_CITY,
            "timezone_confidence": HIGH,
            "why": f"the city {city_text} places this unambiguously",
        }

    if country_text in COUNTRIES:
        iso, region, zone, source = COUNTRIES[country_text]
        region = overrides.get(country_text, region)
        if iso in ("US", "CA", "AU") and state_text:
            table = US_STATES if iso == "US" else {}
            if state_text in table:
                region, zone = table[state_text]
                return {
                    "country": country_text, "country_code": iso,
                    "region": overrides.get(country_text, region),
                    "region_confidence": HIGH,
                    "city": None, "timezone": zone,
                    "timezone_source": FROM_CITY,
                    "timezone_confidence": MEDIUM,
                    "why": f"the state {state_text} narrows the zone",
                }
        if zone is None:
            return {
                "country": country_text, "country_code": iso,
                "region": region or OTHER,
                "region_confidence": HIGH if region else UNKNOWN,
                "city": None,
                "timezone": None, "timezone_source": None,
                "timezone_confidence": UNKNOWN,
                "why": (f"{country_text.title()} spans several time zones and "
                        "a state or city is needed to narrow it; "
                        "scheduling is held rather than guessed"),
            }
        # An ISO code places the country but is weaker than a name or city.
        confidence = (HIGH if source == FROM_COUNTRY_SINGLE else MEDIUM)
        if iso_source and confidence == HIGH:
            confidence = MEDIUM
        return {
            "country": country_text, "country_code": iso,
            "region": region, "region_confidence": HIGH,
            "city": None, "timezone": zone,
            "timezone_source": source,
            "timezone_confidence": confidence,
            "why": (f"{country_text.title()} uses one zone"
                    if source == FROM_COUNTRY_SINGLE else
                    f"{country_text.title()} has a dominant zone"),
        }

    return _blank("no usable location evidence")


def _contains_phrase(text, phrase):
    """Whole-token containment, so Newcastle never matches New York."""
    words = text.split()
    parts = phrase.split()
    for i in range(len(words) - len(parts) + 1):
        if words[i:i + len(parts)] == parts:
            return True
    return False


# ------------------------------------------ TLD inference (TASK-190, free geo)
#
# A country-code TLD is a structural fact about the domain registration, not
# a guess. A .dk domain is registered under Denmark's namespace; that is a
# legal fact, not an inference about where the company operates. It is weaker
# than an office address (a company can register a .dk domain from anywhere)
# but it is unambiguous: no .dk domain is registered outside Denmark.
#
# Two rules, both enforced by the task that motivated this:
#
# 1. Inference may only move UNKNOWN to PASS, never UNKNOWN to FAIL. A wrong
#    inference that fails a geography criterion turns a good company into
#    icp_fail, and FAIL on any criterion is terminal for qualification. So
#    this function returns a country or None; it never says "not in any
#    market". The caller decides whether the inferred country passes.
#
# 2. Every inferred fact carries its provenance. The returned dict names the
#    method (FROM_TLD), the input (the domain), and the confidence (HIGH for
#    an unambiguous ccTLD). The claims gate can tell this apart from a
#    provider-verified fact, and copy may not be written from it - "the
#    domain ends in .dk" is not a citation a prospect would recognise.
#
# Excluded deliberately:
#   .ai  Anguilla in ISO, but universally used by AI companies worldwide
#   .io  British Indian Ocean Territory, same pattern as .ai
#   .co  Colombia, but used globally as a .com alternative
#   .edu  US-focused but not exclusively, and not a company TLD
#   .africa  continent-level, not a country

TLD_TO_ISO = {
    # Western Europe
    "uk": "GB", "ie": "IE", "nl": "NL", "de": "DE", "fr": "FR",
    "be": "BE", "lu": "LU",
    # Nordics
    "se": "SE", "no": "NO", "dk": "DK", "fi": "FI", "is": "IS",
    # Southern Europe
    "es": "ES", "it": "IT", "pt": "PT", "gr": "GR", "mt": "MT",
    "cy": "CY",
    # CEE
    "pl": "PL", "cz": "CZ", "sk": "SK", "hu": "HU", "ro": "RO",
    "bg": "BG", "hr": "HR", "si": "SI", "rs": "RS", "lt": "LT",
    "lv": "LV", "ee": "EE",
    # DACH (CH already above)
    "at": "AT", "ch": "CH",
    # Americas
    "ca": "CA", "us": "US",
    # ANZ
    "au": "AU", "nz": "NZ",
    # Asia
    "jp": "JP", "kr": "KR", "in": "IN",
    # Other
    "ua": "UA", "za": "ZA", "ru": "RU",
}


def from_domain_tld(domain):
    """Country from a ccTLD, or None. HIGH confidence, with provenance.

    Returns a dict shaped like the other geo results plus provenance fields,
    or None when the TLD is generic (.com, .io, .ai) or unrecognised. Never
    returns a FAIL or an excluded country: inference may only move UNKNOWN to
    PASS, and the caller checks the returned country against the include list.
    """
    if not domain or "." not in domain:
        return None
    tld = domain.rsplit(".", 1)[-1].strip().lower()
    iso = TLD_TO_ISO.get(tld)
    if not iso:
        return None
    country_name = ISO_TO_COUNTRY.get(iso)
    if not country_name:
        return None
    entry = COUNTRIES.get(country_name)
    region = entry[1] if entry else OTHER
    return {
        "country": country_name,
        "country_code": iso,
        "region": region,
        "region_confidence": HIGH,
        "city": None,
        "timezone": entry[2] if entry else None,
        "timezone_source": FROM_TLD,
        "timezone_confidence": MEDIUM,
        "why": (f"the domain {domain} is registered under the {tld} "
                f"country-code TLD, which places it in "
                f"{country_name.title()}"),
        # Provenance: the claims gate reads these to tell inferred facts
        # apart from provider-verified ones.
        "inferred": True,
        "inference_method": FROM_TLD,
        "inference_input": domain,
    }


def _trailing_iso(office):
    """The two-letter ISO code at the end of an office string, or None."""
    parts = str(office or "").split(",")
    if not parts:
        return None
    tail = parts[-1].strip()
    code = _iso_code(tail)
    if code and code in ISO_TO_COUNTRY:
        return code
    return None


def from_record(rec, config=None):
    """The location a record actually carries, in the order it is trusted."""
    facts = (rec or {}).get("company_facts") or {}
    offices = facts.get("offices") or []
    places = " ".join(str(o) for o in offices)

    # An explicit country on the record takes precedence. Otherwise, the
    # trailing ISO code of the first office with one is the country evidence.
    country = facts.get("country")
    if not country or _clean(country) not in COUNTRIES:
        for office in offices:
            code = _trailing_iso(office)
            if code:
                country = code
                break

    return resolve(country=country, city=facts.get("city"),
                   state=facts.get("state") or facts.get("region"),
                   config=config,
                   places=" ".join(filter(None, [places, facts.get("hq"),
                                                 facts.get("location")])))


# ------------------------------------------------------------- scheduling

DEFAULT_WINDOWS = {
    "email": {"start": "09:00", "end": "11:30"},
    "linkedin": {"start": "09:30", "end": "16:00"},
    "days": [1, 2, 3, 4, 5],          # Monday is 1, matching ISO weekday
}


def windows(config):
    """The client's sending windows, in the prospect's local time."""
    block = ((config or {}).get("scheduling") or {}).get("windows") or {}
    merged = {"email": dict(DEFAULT_WINDOWS["email"]),
              "linkedin": dict(DEFAULT_WINDOWS["linkedin"]),
              "days": list(DEFAULT_WINDOWS["days"])}
    for channel in ("email", "linkedin"):
        given = block.get(channel) or {}
        for edge in ("start", "end"):
            value = given.get(edge)
            if isinstance(value, str) and _valid_time(value):
                merged[channel][edge] = value
    days = block.get("days")
    if isinstance(days, list) and days:
        kept = [int(d) for d in days
                if str(d).isdigit() and 1 <= int(d) <= 7]
        if kept:
            merged["days"] = sorted(set(kept))
    return merged


def _valid_time(text):
    try:
        hour, _, minute = str(text).partition(":")
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    except (TypeError, ValueError):
        return False


def _parse_time(text):
    hour, _, minute = str(text).partition(":")
    return datetime.time(int(hour), int(minute))


class TimezoneUnavailable(RuntimeError):
    """The platform has no IANA database, so local time cannot be computed."""


def zone(name):
    """The tzinfo for an IANA name, or a refusal that says why.

    `zoneinfo` needs a system tz database, which Windows does not ship. Where
    it is missing this raises rather than falling back to a fixed offset: a
    fixed offset is right for half the year, and the wrong half is the half
    nobody checks.
    """
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as e:                       # pragma: no cover
        raise TimezoneUnavailable("zoneinfo is not available") from e
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as e:
        raise TimezoneUnavailable(
            f"no timezone database entry for {name}: install tzdata") from e


def available():
    """Can this machine compute local times at all?"""
    try:
        zone("Europe/London")
        return True
    except Exception:
        return False


def send_window(timezone, on, config=None, channel="email"):
    """The UTC instants that bracket one local sending window on one date.

    `on` is a date in the prospect's local calendar. The conversion happens
    through the IANA zone, so the answer moves with daylight saving instead of
    drifting by an hour twice a year.
    """
    if not timezone:
        return {"ok": False, "reason": "no timezone: scheduling is held",
                "timezone": None, "channel": channel}
    spec = windows(config)[channel]
    try:
        tz = zone(timezone)
    except TimezoneUnavailable as e:
        return {"ok": False, "reason": str(e), "timezone": timezone,
                "channel": channel}

    start_local = datetime.datetime.combine(on, _parse_time(spec["start"]),
                                            tzinfo=tz)
    end_local = datetime.datetime.combine(on, _parse_time(spec["end"]),
                                          tzinfo=tz)
    return {
        "ok": True,
        "channel": channel,
        "timezone": timezone,
        "date": on.isoformat(),
        "local_start": start_local.isoformat(),
        "local_end": end_local.isoformat(),
        "utc_start": start_local.astimezone(datetime.timezone.utc).isoformat(),
        "utc_end": end_local.astimezone(datetime.timezone.utc).isoformat(),
        # Reported rather than assumed: an offset is a fact about one date.
        "utc_offset_hours": start_local.utcoffset().total_seconds() / 3600,
        "is_dst": bool(start_local.dst()),
        "sending_day": on.isoweekday() in windows(config)["days"],
    }


def schedulable(resolution, config=None):
    """May this company be scheduled at all, and if not, why not."""
    if not resolution.get("timezone"):
        return False, (resolution.get("why")
                       or "no timezone: scheduling is held")
    if resolution.get("timezone_confidence") == LOW:
        return False, "timezone confidence is too low to schedule against"
    if not available():
        return False, ("this machine has no IANA timezone database, so local "
                       "times cannot be computed")
    return True, "local sending windows can be computed"


# ----------------------------------------- cohort window proposal (TASK-227)
#
# A campaign sends to a cohort, not to a timezone. When the campaign's
# schedule is set to 09:00-17:00 Europe/Zagreb but the recipients are in
# US Eastern, 09:00 Zagreb is 03:00 Eastern - an email that lands at 3 AM
# is visibly automated and the kind of mistake a prospect remembers.
#
# This function is PURE READ-ONLY. It does not write to any campaign, does
# not call any provider, does not spend any credit. It reads each recipient's
# location evidence, classifies it, and either proposes a coherent window or
# returns NO PROPOSAL with a reason so the caller falls back to the existing
# production default. The rule that outranks the feature: a guessed timezone
# is worse than a missing one.

RESOLVED = "resolved"
AMBIGUOUS = "ambiguous"
# UNKNOWN already defined above as a confidence level; reused as a status.


def _classify_recipient(rec, config=None):
    """Classify one recipient's location evidence.

    Returns a dict with:
      status:        RESOLVED / AMBIGUOUS / UNKNOWN
      timezone:      the IANA name or None
      confidence:    the geo confidence label
      region:        the GTM region or Other
      country:       the country name or None
      why:           human-readable explanation
    """
    resolution = from_record(rec, config=config)
    tz = resolution.get("timezone")
    conf = resolution.get("timezone_confidence", UNKNOWN)
    country = resolution.get("country")
    region = resolution.get("region", OTHER)

    if tz and conf in (HIGH, MEDIUM):
        return {
            "status": RESOLVED,
            "timezone": tz,
            "confidence": conf,
            "region": region,
            "country": country,
            "why": resolution.get("why", ""),
        }
    if tz and conf == LOW:
        return {
            "status": AMBIGUOUS,
            "timezone": None,
            "confidence": LOW,
            "region": region,
            "country": country,
            "why": (resolution.get("why")
                    or "timezone confidence too low to propose"),
        }
    if country or region != OTHER:
        return {
            "status": AMBIGUOUS,
            "timezone": None,
            "confidence": conf,
            "region": region,
            "country": country,
            "why": (resolution.get("why")
                    or "location known but timezone not determined"),
        }
    return {
        "status": UNKNOWN,
        "timezone": None,
        "confidence": UNKNOWN,
        "region": OTHER,
        "country": None,
        "why": resolution.get("why") or "no usable location evidence",
    }


def propose_cohort_window(recipients, config=None, min_resolved=3,
                          channel="email"):
    """Propose a send window for a cohort from recipient locations.

    Pure read-only: no writes, no provider calls, no credit spend.

    Each recipient is classified:
      RESOLVED  - has a timezone with HIGH or MEDIUM confidence
      AMBIGUOUS - has some location info but no confident timezone
      UNKNOWN   - no usable location evidence

    A proposal is returned only when at least *min_resolved* recipients
    share a single timezone. Otherwise NO PROPOSAL is returned with a
    reason so the caller falls back to the production default.

    Returns a dict:
      ok:             bool
      timezone:       IANA name or None
      region:         GTM region or None
      window:         {start, end} in local time or None
      reason:         why no proposal (when not ok)
      classifications: list of per-recipient classification dicts
      summary:        {resolved, ambiguous, unknown, total}
    """
    if not recipients:
        return {
            "ok": False,
            "timezone": None,
            "region": None,
            "window": None,
            "reason": "no recipients provided",
            "classifications": [],
            "summary": {"resolved": 0, "ambiguous": 0, "unknown": 0,
                        "total": 0},
        }

    classifications = []
    for rec in recipients:
        classifications.append(_classify_recipient(rec, config=config))

    resolved = [c for c in classifications if c["status"] == RESOLVED]
    ambiguous = [c for c in classifications if c["status"] == AMBIGUOUS]
    unknown = [c for c in classifications if c["status"] == UNKNOWN]

    summary = {
        "resolved": len(resolved),
        "ambiguous": len(ambiguous),
        "unknown": len(unknown),
        "total": len(classifications),
    }

    if not resolved:
        return {
            "ok": False,
            "timezone": None,
            "region": None,
            "window": None,
            "reason": "no recipients resolved to a timezone",
            "classifications": classifications,
            "summary": summary,
        }

    if len(resolved) < min_resolved:
        return {
            "ok": False,
            "timezone": None,
            "region": None,
            "window": None,
            "reason": (f"only {len(resolved)} of {len(classifications)} "
                       f"recipients resolved; need at least {min_resolved}"),
            "classifications": classifications,
            "summary": summary,
        }

    timezones = set(c["timezone"] for c in resolved)
    if len(timezones) > 1:
        return {
            "ok": False,
            "timezone": None,
            "region": None,
            "window": None,
            "reason": ("recipients span multiple timezones: "
                       + ", ".join(sorted(timezones))),
            "classifications": classifications,
            "summary": summary,
        }

    tz = resolved[0]["timezone"]
    region = resolved[0]["region"]
    spec = windows(config)[channel]
    return {
        "ok": True,
        "timezone": tz,
        "region": region,
        "window": {"start": spec["start"], "end": spec["end"]},
        "reason": None,
        "classifications": classifications,
        "summary": summary,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--country")
    p.add_argument("--city")
    p.add_argument("--state")
    p.add_argument("--window", help="an IANA timezone to show a window for")
    p.add_argument("--date", default="2026-07-15")
    p.add_argument("--channel", default="email", choices=("email", "linkedin"))
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.window:
        on = datetime.date.fromisoformat(a.date)
        result = send_window(a.window, on, channel=a.channel)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 2

    result = resolve(a.country, a.city, a.state)
    print(json.dumps(result, indent=2) if a.json else
          "\n".join(f"  {k:<22} {v}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
