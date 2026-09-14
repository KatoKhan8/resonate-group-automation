#!/usr/bin/env python3
"""Grouping companies into campaigns, without ending up with 400 of them.

A segment key is a promise that everything inside it can receive the same
message. Cut too finely and you get four hundred segments of three companies,
each needing its own copy, none worth writing. Cut too coarsely and a
twelve-person SEO shop in Zagreb gets a message written for a 300-person
consultancy in Frankfurt.

So segments are built at full specificity and then **merged upward** until each
one is worth writing for. The ladder is explicit and ordered - the least
important dimension is given up first - and every company records which rung it
ended on and why, so "why are these two in the same campaign?" has an answer
that is not "the algorithm decided".

  python -m src.campaignseg --describe
"""
import argparse
import json
import re

from . import geo, icp, segments

# Short codes keep a key readable. They are stable identifiers: renaming one
# orphans every campaign that used it, so they are treated as vocabulary.
VERTICAL_CODES = {
    segments.DIGITAL_MARKETING: "DIGITAL",
    segments.PERFORMANCE_MARKETING: "PERFORMANCE",
    segments.CREATIVE: "CREATIVE",
    segments.SEO: "SEO",
    segments.PR: "PR",
    segments.SOFTWARE_DEV: "SOFTWARE",
    segments.PRODUCT_DEV: "PRODUCT",
    segments.DESIGN_UX: "DESIGN",
    segments.CONSULTING: "CONSULTING",
    segments.PROFESSIONAL_SERVICES: "PROFSERV",
    segments.ARCHITECTURE_ENGINEERING: "AEC",
    segments.OTHER_AGENCY: "AGENCY",
    segments.OTHER_PROFESSIONAL: "PROFOTHER",
    segments.NON_ICP: "NONICP",
    segments.UNKNOWN: "UNKNOWN",
}

REGION_CODES = {
    geo.UK: "UK",
    geo.DACH: "DACH",
    geo.NORDICS: "NORDICS",
    geo.BENELUX: "BENELUX",
    geo.CEE: "CEE",
    geo.SOUTHERN_EUROPE: "SEUROPE",
    geo.US_EAST: "USEAST",
    geo.US_CENTRAL: "USCENTRAL",
    geo.US_WEST: "USWEST",
    geo.CANADA: "CANADA",
    geo.ANZ: "ANZ",
    geo.OTHER: "OTHER",
}

# Where several verticals share one message, they share one merged code.
VERTICAL_FAMILIES = {
    "MARKETING": (segments.DIGITAL_MARKETING, segments.PERFORMANCE_MARKETING,
                  segments.SEO, segments.PR),
    "CREATIVE": (segments.CREATIVE, segments.DESIGN_UX),
    "TECH": (segments.SOFTWARE_DEV, segments.PRODUCT_DEV),
    "ADVISORY": (segments.CONSULTING, segments.PROFESSIONAL_SERVICES,
                 segments.ARCHITECTURE_ENGINEERING, segments.OTHER_PROFESSIONAL),
}
FAMILY_OF = {vertical: family
             for family, verticals in VERTICAL_FAMILIES.items()
             for vertical in verticals}

# Adjacent bands that can share a message when either is too small alone.
BAND_FAMILIES = {
    "SMALL": ("1_9", "10_19", "20_49"),
    "MID": ("50_99", "100_199"),
    "LARGE": ("200_499", "500_999", "1000_PLUS"),
}
BAND_FAMILY_OF = {band: family
                  for family, bands in BAND_FAMILIES.items()
                  for band in bands}

# Regions that can share a message when either is too small alone.
REGION_FAMILIES = {
    "EUROPE": (geo.UK, geo.DACH, geo.NORDICS, geo.BENELUX, geo.CEE,
               geo.SOUTHERN_EUROPE),
    "NORTHAM": (geo.US_EAST, geo.US_CENTRAL, geo.US_WEST, geo.CANADA),
    "APAC": (geo.ANZ,),
    "OTHER": (geo.OTHER,),
}
REGION_FAMILY_OF = {region: family
                    for family, regions in REGION_FAMILIES.items()
                    for region in regions}

# The ladder. Each rung gives up one dimension, least important first: the
# persona is the last thing surrendered because it decides who the message is
# addressed to, and a message to the wrong role is not a coarser message, it is
# the wrong message.
LADDER = ("full", "band_family", "vertical_family", "region_family",
          "persona_only")

DEFAULT_POLICY = {
    "min_segment_size": 50,
    "max_segment_size": 500,
    # Derived from the client, never the name of one.
    #
    # This said "PRODUCTIVE", and the override that would have changed it -
    # `campaign_segments.client_prefix` - is set by no client file, is absent
    # from `clients.STARTER`, and is not in `workspaces.POLICY_KEYS`, so it
    # could not be set from the product at all. Every other workspace
    # therefore had a different agency's client name stamped on its own
    # segment keys, and those keys are read back onto the Segments screen, the
    # campaign brief a person approves from, the explorer and the reports.
    # A second client would have seen it on day one and had no way to change
    # it.
    "client_prefix": None,
}


def settings(config):
    block = ((config or {}).get("campaign_segments") or {})
    merged = dict(DEFAULT_POLICY)
    for name in ("min_segment_size", "max_segment_size"):
        try:
            if block.get(name) is not None:
                merged[name] = max(1, int(block[name]))
        except (TypeError, ValueError):
            pass
    prefix = block.get("client_prefix")
    if isinstance(prefix, str) and prefix.strip():
        merged["client_prefix"] = _code(prefix)
    else:
        # The client's own name, which `clients.load` guarantees is set - it
        # defaults to the slug. An unnamed config gets a neutral word rather
        # than somebody else's brand.
        merged["client_prefix"] = _code((config or {}).get("name") or "CLIENT")
    if merged["max_segment_size"] < merged["min_segment_size"]:
        merged["max_segment_size"] = merged["min_segment_size"]
    return merged


def _code(text):
    """Uppercase, ASCII, and safe in a key.

    The underscore survives because it carries meaning: `50_99` is a band
    boundary, and `50199` is a number nobody can read back. The hyphen is the
    key's own separator, so it is the one character that cannot appear inside
    a part.
    """
    text = re.sub(r"[^A-Za-z0-9_]+", "", str(text or "")).upper()
    return text.strip("_") or "UNKNOWN"


def key_parts(segment, persona, rung="full", config=None, _policy=None):
    """The four parts of a key at one rung of the ladder."""
    policy = _policy if _policy is not None else settings(config)
    vertical = segment.get("vertical") or segments.UNKNOWN
    region = segment.get("region") or geo.OTHER
    band = segment.get("employee_band") or segments.UNKNOWN

    vertical_code = VERTICAL_CODES.get(vertical, "UNKNOWN")
    region_code = REGION_CODES.get(region, "OTHER")
    band_code = _code(band)

    if rung in ("band_family", "vertical_family", "region_family",
                "persona_only"):
        band_code = BAND_FAMILY_OF.get(band, "UNKNOWN")
    if rung in ("vertical_family", "region_family", "persona_only"):
        vertical_code = FAMILY_OF.get(vertical, vertical_code)
    if rung in ("region_family", "persona_only"):
        region_code = REGION_FAMILY_OF.get(region, "OTHER")
    if rung == "persona_only":
        vertical_code = "ALL"
        region_code = "ALL"
        band_code = "ALL"

    return {
        "prefix": policy["client_prefix"],
        "region": region_code,
        "vertical": vertical_code,
        "band": band_code,
        "persona": _code(persona),
        "rung": rung,
    }


def key_for(segment, persona, rung="full", config=None, _policy=None):
    parts = key_parts(segment, persona, rung, config, _policy=_policy)
    return "-".join([parts["prefix"], parts["region"], parts["vertical"],
                     parts["band"], parts["persona"]])


def _reason(parts, segment, persona):
    if parts["rung"] == "full":
        return (f"{segment.get('vertical')} in {segment.get('region')} at "
                f"{segment.get('employee_band')} people, approached through "
                f"{persona}")
    if parts["rung"] == "band_family":
        return (f"too few companies at exactly {segment.get('employee_band')}, "
                f"so sizes were merged into {parts['band']}")
    if parts["rung"] == "vertical_family":
        return (f"too few in {segment.get('vertical')} alone, so related "
                f"verticals were merged into {parts['vertical']}")
    if parts["rung"] == "region_family":
        return (f"too few in {segment.get('region')} alone, so neighbouring "
                f"regions were merged into {parts['region']}")
    return (f"too few companies to segment by anything but the persona, so "
            f"everyone approached through {persona} shares one campaign")


def assign(companies, config=None):
    """Give every company a segment key, merging upward until each is viable.

    `companies` is a list of {record, segment, persona_plan, verdict}. Only
    qualified companies are segmented: a rejected company has no campaign to
    belong to, and putting it in one would make the counts lie.
    """
    policy = settings(config)
    eligible = [entry for entry in companies
                if entry["verdict"].get("icp_status") == icp.QUALIFIED
                and (entry["persona_plan"].get("persona_priority") or [])]
    eligible_ids = {entry["record"]["id"] for entry in eligible}
    skipped = [entry for entry in companies
               if entry["record"]["id"] not in eligible_ids]

    # Each company is placed at the finest rung that ends up viable. The loop
    # walks the ladder once per rung and only re-places companies that are
    # still in a segment too small to be worth writing for.
    placement = {}
    for entry in eligible:
        placement[entry["record"]["id"]] = "full"

    for rung, next_rung in zip(LADDER, LADDER[1:]):
        counts = {}
        for entry in eligible:
            if placement[entry["record"]["id"]] != rung:
                continue
            persona = entry["persona_plan"]["persona_priority"][0]
            counts.setdefault(key_for(entry["segment"], persona, rung, config,
                                      _policy=policy),
                              []).append(entry)
        for key, members in counts.items():
            if len(members) < policy["min_segment_size"]:
                for entry in members:
                    placement[entry["record"]["id"]] = next_rung

    assigned = []
    for entry in eligible:
        rung = placement[entry["record"]["id"]]
        persona = entry["persona_plan"]["persona_priority"][0]
        parts = key_parts(entry["segment"], persona, rung, config,
                          _policy=policy)
        assigned.append({
            **entry,
            "segment_key": key_for(entry["segment"], persona, rung, config,
                                   _policy=policy),
            "segment_parts": parts,
            "segment_rung": rung,
            "segment_reason": _reason(parts, entry["segment"], persona),
        })

    for entry in skipped:
        assigned.append({
            **entry,
            "segment_key": None,
            "segment_parts": None,
            "segment_rung": None,
            "segment_reason": (
                f"not segmented: status is "
                f"{entry['verdict'].get('icp_status')}"),
        })
    return assigned


def summarise(assigned, config=None):
    """Segment sizes, and which ones are still outside the healthy range."""
    policy = settings(config)
    sizes = {}
    for entry in assigned:
        key = entry.get("segment_key")
        if not key:
            continue
        bucket = sizes.setdefault(key, {"companies": 0, "rung": entry["segment_rung"],
                                        "reason": entry["segment_reason"]})
        bucket["companies"] += 1

    too_small = {k: v for k, v in sizes.items()
                 if v["companies"] < policy["min_segment_size"]}
    splittable = {k: v for k, v in sizes.items()
                  if v["companies"] > policy["max_segment_size"]}
    return {
        "segments": len(sizes),
        "segmented_companies": sum(v["companies"] for v in sizes.values()),
        "unsegmented_companies": sum(1 for e in assigned
                                     if not e.get("segment_key")),
        "sizes": dict(sorted(sizes.items(),
                             key=lambda kv: (-kv[1]["companies"], kv[0]))),
        "below_minimum": too_small,
        "eligible_for_splitting": splittable,
        "min_segment_size": policy["min_segment_size"],
        "max_segment_size": policy["max_segment_size"],
        # Named rather than hidden: a merge that could not reach the minimum
        # is a real state, and pretending otherwise loses the information.
        "note": ("segments below the minimum are those that reached the "
                 "bottom of the ladder and are still small: there is nothing "
                 "left to merge into" if too_small else
                 "every segment is at or above the minimum size"),
    }


def why_together(first, second, config=None):
    """Why two companies share a campaign, or why they do not."""
    if first.get("segment_key") != second.get("segment_key"):
        return {
            "same_segment": False,
            "why": (f"{first.get('segment_key')} and "
                    f"{second.get('segment_key')} are different segments"),
        }
    return {
        "same_segment": True,
        "segment_key": first.get("segment_key"),
        "rung": first.get("segment_rung"),
        "why": first.get("segment_reason"),
        "shared": {
            "region": first["segment_parts"]["region"],
            "vertical": first["segment_parts"]["vertical"],
            "band": first["segment_parts"]["band"],
            "persona": first["segment_parts"]["persona"],
        },
    }


def describe(config=None):
    policy = settings(config)
    return {
        "ladder": list(LADDER),
        "vertical_codes": VERTICAL_CODES,
        "region_codes": REGION_CODES,
        "vertical_families": {k: list(v) for k, v in VERTICAL_FAMILIES.items()},
        "band_families": {k: list(v) for k, v in BAND_FAMILIES.items()},
        "region_families": {k: list(v) for k, v in REGION_FAMILIES.items()},
        "policy": policy,
        "example": "PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--describe", action="store_true")
    p.add_argument("--client")
    a = p.parse_args(argv)

    from . import clients
    config = {}
    try:
        config = clients.load(a.client)
    except Exception:
        config = {}
    print(json.dumps(describe(config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
