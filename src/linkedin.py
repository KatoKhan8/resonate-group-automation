#!/usr/bin/env python3
"""One canonical form for a LinkedIn profile URL.

## Why this is load-bearing

HeyReach's inbox does not carry our identifiers. Confirmed live on 2026-08-26:
`customFields` is an empty list on every conversation, and `/lead/GetLead` -
the only working lead lookup - exposes no custom fields at all, just a
`customEmailAddress` string. What it *does* return, exactly as asked for, is
`profileUrl`.

So the LinkedIn URL is the correlation key between a reply and one of our
records. That makes its canonical form a safety property rather than tidiness:
two spellings of one profile must collapse to one key, or a real reply goes
unmatched and the company keeps being sequenced after it answered. And two
different people must never collapse together, or a reply pauses the wrong
company and a stranger's message is attributed to someone else.

## What is normalised, and what deliberately is not

Normalised, because LinkedIn treats them as the same page:

    scheme, host case, www./locale subdomains, /in/ path case, trailing
    slash, query string, fragment, percent-encoding

NOT normalised, because they identify different things:

    the vanity segment's own characters. `/in/jan-novak` and `/in/jan-novak-2`
    are two people. Nothing here strips digits, suffixes or hyphens, and
    nothing here compares names.

There is no fuzzy matching anywhere in this module, and there never should be.
A near-miss is an unmatched event, which is safe; a wrong match pauses somebody
else's campaign.
"""
import re
import urllib.parse

# LinkedIn serves the same profile from a locale or www subdomain.
HOSTS = ("linkedin.com",)
PROFILE_PREFIXES = ("/in/", "/pub/")

# Tracking and locale noise that never changes which profile is meant.
STRIP_PARAMS = ()          # every query parameter is dropped; kept for clarity


class NotAProfile(ValueError):
    """This is not a LinkedIn member profile URL. Never guessed at."""


def _host_ok(host):
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
    # A locale subdomain: de.linkedin.com, uk.linkedin.com.
    parts = host.split(".")
    if len(parts) > 2 and parts[0] not in ("www",):
        host = ".".join(parts[-2:])
    return host in HOSTS, host


def canonical(url):
    """The one form of a profile URL, or None if it is not a profile.

    Returns None rather than raising, because an unrecognised URL is a
    perfectly ordinary thing to meet in provider data and the caller's job is
    to leave that contact unmatched, not to crash.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    raw = url.strip()

    # A bare vanity name, which is how some exports store it.
    if "/" not in raw and " " not in raw and "." not in raw:
        vanity = _clean_vanity(raw)
        return f"https://www.linkedin.com/in/{vanity}" if vanity else None

    if "//" not in raw:
        raw = "https://" + raw.lstrip("/")

    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return None

    ok, host = _host_ok(parsed.netloc.split("@")[-1].split(":")[0])
    if not ok:
        return None

    path = urllib.parse.unquote(parsed.path or "")
    lowered = path.lower()
    for prefix in PROFILE_PREFIXES:
        if lowered.startswith(prefix):
            vanity = path[len(prefix):]
            break
    else:
        return None

    # Everything after the vanity segment is a sub-page: /detail/contact-info.
    #
    # EXCEPT under /pub/, where it is part of who this is. A legacy public URL
    # is `/pub/jan-novak/1a/2b3/4c5`, and that trailing triplet is exactly what
    # distinguishes two members who share a vanity segment. Dropping it mapped
    # both of them - and anybody at `/in/jan-novak`, who may be a third person
    # - onto one identity, which is the wrong match this module opens by
    # refusing to make: "A near-miss is an unmatched event, which is safe; a
    # wrong match pauses somebody else's campaign."
    #
    # So a /pub/ URL that carries those segments keeps them and stays its own
    # identity. A bare /pub/vanity has nothing to disambiguate and keeps its
    # existing reading as the /in/ form of the same vanity.
    rest = [segment for segment in vanity.split("/")[1:] if segment.strip("/")]
    vanity = _clean_vanity(vanity.split("/")[0])
    if not vanity:
        return None
    if lowered.startswith("/pub/") and rest:
        tail = [_clean_vanity(segment) for segment in rest]
        if not all(tail):
            return None
        return "https://www.linkedin.com/pub/" + "/".join([vanity] + tail)
    return f"https://www.linkedin.com/in/{vanity}"


def _clean_vanity(vanity):
    """The vanity segment, lower-cased and stripped of nothing else.

    Case is folded because LinkedIn resolves /in/Jan-Novak and /in/jan-novak to
    the same member. Characters are otherwise left alone: `-2` at the end of a
    vanity is part of somebody's identity, not noise.
    """
    vanity = (vanity or "").strip().strip("/")
    vanity = urllib.parse.unquote(vanity).strip()
    if not vanity:
        return None
    # Query or fragment glued on by a sloppy export.
    vanity = re.split(r"[?#]", vanity)[0].strip("/")
    return vanity.lower() or None


def same_profile(left, right):
    """Do these two URLs mean the same member? Never a fuzzy answer."""
    a, b = canonical(left), canonical(right)
    return bool(a) and a == b


PROFILE_ROOTS = tuple("https://www.linkedin.com" + prefix
                      for prefix in PROFILE_PREFIXES)


def key(url):
    """The short form used as a lookup key: everything that identifies them.

    The vanity segment for an `/in/` profile. For a legacy `/pub/` one it is
    the vanity PLUS the segments that tell two members sharing that vanity
    apart, because those are now kept - a `rsplit` on the last slash would
    have returned the final segment on its own and put two people one
    character apart.
    """
    full = canonical(url)
    if not full:
        return None
    for root in PROFILE_ROOTS:
        if full.startswith(root):
            return full[len(root):]
    return None


def index(records):
    """{canonical url: (record, contact)} for every contact with a profile.

    A URL that two contacts share is dropped from the index rather than
    resolved: it means the data is wrong, and picking one of them would attach
    somebody's reply to the wrong person.
    """
    found, ambiguous = {}, set()
    for record in records or []:
        for contact in record.get("contacts") or []:
            url = canonical(contact.get("linkedin"))
            if not url:
                continue
            if url in found and found[url][1].get("key") != contact.get("key"):
                ambiguous.add(url)
                continue
            found[url] = (record, contact)
    for url in ambiguous:
        found.pop(url, None)
    return found
