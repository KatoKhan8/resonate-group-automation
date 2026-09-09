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
    vanity = vanity.split("/")[0]
    vanity = _clean_vanity(vanity)
    if not vanity:
        return None
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


def key(url):
    """The short form used as a lookup key: the vanity segment alone."""
    full = canonical(url)
    return full.rsplit("/", 1)[-1] if full else None


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
