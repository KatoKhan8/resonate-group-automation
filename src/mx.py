#!/usr/bin/env python3
"""Which email-security gateway sits in front of an address, and what that means.

## What this is for

Some gateways are not worth writing to. A message that lands in a Proofpoint or
Mimecast quarantine is not a message that failed to persuade - it is a message
nobody saw, and it still costs the sending domain reputation. So the operator
gets to name gateways they would rather not send through, and this module makes
that decision once per email domain, cheaply, before anything paid happens.

It is **channel suppression, not a drop**. A blocked gateway stops the email
track and nothing else: the contact stays in the campaign, LinkedIn stays
eligible, and the email steps stay in the timeline marked skipped with the
provider named, so a year later it is clear why nothing was sent.

## Two rules that are easy to get wrong

**The lookup uses the address's own domain.** A contact at company.com whose
address is john@mail-company.test is protected by whatever guards
mail-company.test. Substituting the company domain would classify the wrong
thing entirely, and both directions of that mistake are bad.

**Matching is on label boundaries, never substrings.** `pphosted.com` matches
`mx1.pphosted.com`, and does not match `notpphosted.com.evil.test`. A substring
check here would block a competitor who happened to put "mimecast" in a
hostname, and would miss nothing in return.

## When DNS will not answer

Five outcomes, and they are deliberately not four:

    known_allowed     resolved, recognised, not on the blocked list
    known_blocked     resolved, recognised, on the blocked list
    unknown_provider  resolved, not recognised - policy decides
    dns_failure       we could not ask. The channel is HELD, not allowed
    no_mx             the domain accepts no mail at all

A temporary resolver failure must never read as "no gateway found". That is the
one failure mode that would quietly send into exactly the thing this module
exists to avoid, so it holds instead.

  python -m src.mx check example.com
  python -m src.mx run --dry-run
"""
import argparse
import json
import os
import random
import socket
import struct
import sys
import time

from . import clients, events, store

# ------------------------------------------------------------- the gateways
#
# Suffixes that identify a gateway from an MX hostname with no ambiguity. Every
# one of these is a domain the vendor operates for exactly this purpose, so a
# match is evidence rather than a hint.
#
# Vendors deliberately NOT listed, because their cloud MX cannot be identified
# from the hostname alone: Fortinet FortiMail (self-hosted, customer hostnames)
# and Sophos Email when fronted by a customer domain. Guessing at those would
# block real prospects for no reason.

GATEWAYS = {
    "barracuda": {
        "name": "Barracuda",
        "suffixes": ("barracudanetworks.com", "ess.barracudanetworks.com",
                     "barracuda.com", "cudasvc.com"),
    },
    "proofpoint": {
        "name": "Proofpoint",
        "suffixes": ("pphosted.com", "ppe-hosted.com", "pphosted.co.uk",
                     "proofpoint.com"),
    },
    "mimecast": {
        "name": "Mimecast",
        "suffixes": ("mimecast.com", "mimecast.co.za", "mimecast-offshore.com",
                     "mimecast.net"),
    },
    "cisco": {
        "name": "Cisco Secure Email (IronPort)",
        "suffixes": ("iphmx.com", "ironport.com"),
    },
    "forcepoint": {
        "name": "Forcepoint",
        "suffixes": ("mailcontrol.com",),
    },
    "trendmicro": {
        "name": "Trend Micro",
        "suffixes": ("trendmicro.com", "tmes.trendmicro.com",
                     "hes.trendmicro.com", "trendmicro.eu"),
    },
    "spamtitan": {
        "name": "SpamTitan",
        "suffixes": ("spamtitan.com", "titanhq.com"),
    },
    "hornetsecurity": {
        "name": "Hornetsecurity",
        "suffixes": ("hornetsecurity.com", "antispameurope.com"),
    },
    "symantec": {
        "name": "Symantec / Broadcom MessageLabs",
        "suffixes": ("messagelabs.com", "messagelabs.co.jp"),
    },
    "sophos": {
        "name": "Sophos Email",
        "suffixes": ("sophos.com", "mx.sophos.com"),
    },
    # MailChannels is an outbound relay far more often than an inbound
    # gateway, and where it does sit on MX it is usually a shared host's
    # default rather than a deliberate security posture. Recognised, and
    # categorised below as ordinary rather than protected for that reason.
    "mailchannels": {
        "name": "MailChannels",
        "suffixes": ("mailchannels.net", "mailchannels.com"),
    },
}

# Recognised, and emphatically not gateways to avoid. Named so that "we know
# what this is" and "we would rather not send through it" stay separate
# questions - blocking every Microsoft-hosted domain would delete most of the
# addressable market.
MAILBOX_HOSTS = {
    "google": {
        "name": "Google Workspace",
        "suffixes": ("google.com", "googlemail.com", "aspmx.l.google.com"),
    },
    "microsoft": {
        "name": "Microsoft 365",
        "suffixes": ("outlook.com", "mail.protection.outlook.com",
                     "olc.protection.outlook.com", "office365.us"),
    },
    "zoho": {"name": "Zoho Mail", "suffixes": ("zoho.com", "zoho.eu")},
    "fastmail": {"name": "Fastmail", "suffixes": ("messagingengine.com",)},
}

ALL_KNOWN = {**GATEWAYS, **MAILBOX_HOSTS}

# ------------------------------------------------------- policy categories
#
# "Which vendor is this?" and "how hard does it filter cold mail?" are two
# different questions, and collapsing them is how Microsoft 365 ends up
# blocked for being Microsoft. The category answers the second one, and the
# client policy is expressed over categories rather than over vendor names, so
# adding a vendor does not silently change anybody's policy.
#
#   normal           an ordinary mailbox host or relay; cold mail behaves
#                    roughly as it would anywhere
#   protected        a filtering layer that quarantines some cold mail
#   high_protection  a gateway that reliably quarantines it, where sending
#                    costs sender reputation and buys nothing
#   unknown          no MX evidence identifies the operator

NORMAL = "normal"
PROTECTED = "protected"
HIGH_PROTECTION = "high_protection"
UNKNOWN_CATEGORY = "unknown"

CATEGORIES = (NORMAL, PROTECTED, HIGH_PROTECTION, UNKNOWN_CATEGORY)

# Assigned from observed behaviour towards cold outbound, not from vendor
# marketing. The three in high_protection are the three the default policy
# blocks; everything else is a judgement worth arguing with in config rather
# than in code.
CATEGORY_OF = {
    "proofpoint": HIGH_PROTECTION,
    "mimecast": HIGH_PROTECTION,
    "barracuda": HIGH_PROTECTION,
    "cisco": PROTECTED,
    "forcepoint": PROTECTED,
    "trendmicro": PROTECTED,
    "spamtitan": PROTECTED,
    "hornetsecurity": PROTECTED,
    "symantec": PROTECTED,
    "sophos": PROTECTED,
    "mailchannels": NORMAL,
    "google": NORMAL,
    "microsoft": NORMAL,
    "zoho": NORMAL,
    "fastmail": NORMAL,
}


def category_of(provider_key):
    """The policy category for a recognised provider, or unknown."""
    return CATEGORY_OF.get(provider_key or "", UNKNOWN_CATEGORY)


def providers_in(category):
    return tuple(sorted(k for k, v in CATEGORY_OF.items() if v == category))

# ------------------------------------------------------------------ statuses

KNOWN_ALLOWED = "known_allowed"
KNOWN_BLOCKED = "known_blocked"
UNKNOWN_PROVIDER = "unknown_provider"
DNS_FAILURE = "dns_failure"
NO_MX = "no_mx"
NOT_CHECKED = "not_checked"

STATUSES = (KNOWN_ALLOWED, KNOWN_BLOCKED, UNKNOWN_PROVIDER, DNS_FAILURE,
            NO_MX, NOT_CHECKED)

BLOCK_REASON = "mx_security_provider_blocked"

# The stable, greppable reason stored on a contact whose email channel a
# gateway closed: "mx_protection:proofpoint". One prefix, one vendor key, no
# prose - prose belongs in `reason`, which is for humans and may be reworded.
PROTECTION_REASON = "mx_protection"

# Blocking is expressed over categories; the vendor list below is derived so
# the two can never drift apart. A client may still name individual vendors.
DEFAULT_CATEGORY_POLICY = {
    NORMAL: "allow",
    PROTECTED: "allow",
    HIGH_PROTECTION: "block",
    UNKNOWN_CATEGORY: "allow",
}

DEFAULTS = {
    "enabled": True,
    "blocked_providers": providers_in(HIGH_PROTECTION),
    "category_policy": DEFAULT_CATEGORY_POLICY,
    "unknown_provider_policy": "allow",
    "cache_days": 7,
    "timeout_seconds": 3.0,
}


class MXError(RuntimeError):
    pass


# -------------------------------------------------------------------- policy

def settings(config):
    """The client's MX policy, with safe defaults for anything unset."""
    block = ((config or {}).get("email_security") or {}).get("mx_filter") or {}
    merged = dict(DEFAULTS)
    merged["enabled"] = block.get("enabled", DEFAULTS["enabled"]) is not False
    blocked = block.get("blocked_providers", DEFAULTS["blocked_providers"])
    if isinstance(blocked, str):
        blocked = [blocked]
    # An unrecognised name in the config is dropped rather than silently
    # treated as "block everything" or "block nothing in particular".
    merged["blocked_providers"] = tuple(
        str(p).strip().lower() for p in (blocked or [])
        if str(p).strip().lower() in GATEWAYS)
    merged["unknown"] = [str(p).strip().lower() for p in (blocked or [])
                         if str(p).strip().lower() not in GATEWAYS]
    # Category policy: an unrecognised category name is dropped rather than
    # guessed at, and an unrecognised verdict falls back to the default for
    # that category rather than to "block everything".
    given = block.get("category_policy") or {}
    categories = dict(DEFAULT_CATEGORY_POLICY)
    if isinstance(given, dict):
        for name, verdict in given.items():
            name = str(name).strip().lower()
            verdict = str(verdict).strip().lower()
            if name in CATEGORIES and verdict in ("allow", "block"):
                categories[name] = verdict
    merged["category_policy"] = categories

    policy = str(block.get("unknown_provider_policy",
                           DEFAULTS["unknown_provider_policy"])).strip().lower()
    merged["unknown_provider_policy"] = policy if policy in ("allow", "block") \
        else DEFAULTS["unknown_provider_policy"]
    try:
        merged["cache_days"] = max(0, int(block.get("cache_days",
                                                    DEFAULTS["cache_days"])))
    except (TypeError, ValueError):
        merged["cache_days"] = DEFAULTS["cache_days"]
    try:
        merged["timeout_seconds"] = float(block.get("timeout_seconds",
                                                    DEFAULTS["timeout_seconds"]))
    except (TypeError, ValueError):
        merged["timeout_seconds"] = DEFAULTS["timeout_seconds"]
    return merged


# ------------------------------------------------------------------ identity

def email_domain(email):
    """The address's OWN domain, lower-cased. Never the company's.

    john@mail-company.test is protected by mail-company.test, whatever the
    company's website happens to be.
    """
    if not isinstance(email, str) or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1].strip().lower().rstrip(".")
    return domain or None


def normalise_host(host):
    """An MX hostname as a comparable string: lower-cased, no trailing dot."""
    if not isinstance(host, str):
        return None
    host = host.strip().lower().rstrip(".")
    return host or None


def _matches(host, suffix):
    """Label-boundary suffix match. Never a substring test."""
    return host == suffix or host.endswith("." + suffix)


def classify(hosts):
    """(provider_key, provider_name) for the first recognised MX, or (None, None).

    Gateways are checked before mailbox hosts: a domain fronted by Mimecast and
    delivering to Microsoft is a Mimecast domain for our purposes.
    """
    cleaned = [normalise_host(h) for h in (hosts or [])]
    cleaned = [h for h in cleaned if h]
    for table in (GATEWAYS, MAILBOX_HOSTS):
        for key, entry in table.items():
            for suffix in entry["suffixes"]:
                if any(_matches(host, suffix) for host in cleaned):
                    return key, entry["name"]
    return None, None


# ----------------------------------------------------------------- resolver
#
# A minimal MX query, because this project has no third-party dependencies and
# the standard library cannot ask for an MX record. Only the answer section is
# parsed, and only MX records in it: nothing here is a general DNS client.

DNS_PORT = 53
TYPE_MX = 15
CLASS_IN = 1
DEFAULT_SERVERS = ("1.1.1.1", "8.8.8.8")


def _encode_name(name):
    out = b""
    for label in name.split("."):
        if not label:
            continue
        encoded = label.encode("idna") if any(ord(c) > 127 for c in label) \
            else label.encode("ascii")
        if len(encoded) > 63:
            raise MXError(f"label too long in {name!r}")
        out += bytes([len(encoded)]) + encoded
    return out + b"\x00"


def _read_name(data, offset):
    """Read a possibly compressed name. Returns (name, next_offset)."""
    labels, jumped, next_offset, hops = [], False, offset, 0
    while True:
        if offset >= len(data):
            raise MXError("truncated response")
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise MXError("truncated pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                next_offset = offset + 2
            offset, jumped = pointer, True
            hops += 1
            if hops > 20:
                raise MXError("compression loop")
            continue
        offset += 1
        if length == 0:
            if not jumped:
                next_offset = offset
            break
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
    return ".".join(labels), next_offset


def _query(domain, server, timeout):
    """One UDP MX query. Returns the raw response bytes."""
    request_id = random.randint(0, 0xFFFF)
    header = struct.pack("!HHHHHH", request_id, 0x0100, 1, 0, 0, 0)
    question = _encode_name(domain) + struct.pack("!HH", TYPE_MX, CLASS_IN)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(header + question, (server, DNS_PORT))
        data, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    if len(data) < 12 or struct.unpack("!H", data[:2])[0] != request_id:
        raise MXError("mismatched response")
    return data


def _parse(data):
    """The MX hostnames in an answer, best preference first."""
    _, flags, questions, answers, _, _ = struct.unpack("!HHHHHH", data[:12])
    rcode = flags & 0x000F
    if rcode == 3:
        return []                       # NXDOMAIN: the name does not exist
    if rcode != 0:
        raise MXError(f"dns rcode {rcode}")
    offset = 12
    for _ in range(questions):
        _, offset = _read_name(data, offset)
        offset += 4
    found = []
    for _ in range(answers):
        _, offset = _read_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, _, _, length = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        end = offset + length
        if rtype == TYPE_MX and length >= 3:
            preference = struct.unpack("!H", data[offset:offset + 2])[0]
            host, _ = _read_name(data, offset + 2)
            if host:
                found.append((preference, normalise_host(host)))
        offset = end
    return [host for _, host in sorted(found) if host]


def resolve(domain, timeout=None, servers=DEFAULT_SERVERS):
    """MX hostnames for a domain. Raises MXError when it cannot be answered.

    A failure here is a failure, never an empty list: "no answer" and "no MX"
    are different facts and only one of them is safe to act on.
    """
    timeout = DEFAULTS["timeout_seconds"] if timeout is None else timeout
    last = None
    for server in servers:
        try:
            return _parse(_query(domain, server, timeout))
        except (socket.timeout, OSError, MXError, struct.error) as e:
            last = e
    raise MXError(f"could not resolve MX for {domain}: {last}")


# -------------------------------------------------------------------- cache

def cache_path():
    return os.path.abspath(os.environ.get("MX_CACHE")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "mx-cache.json"))


def load_cache():
    path = cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    path = cache_path()
    store.refuse_production_write(path)
    with store.lock(for_path=path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    return cache


def _fresh(entry, cache_days, now=None):
    if not entry or not entry.get("checked_at"):
        return False
    if cache_days <= 0:
        return False
    try:
        checked = time.mktime(time.strptime(entry["checked_at"][:19],
                                            "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return False
    now = now if now is not None else time.time()
    return (now - checked) < cache_days * 86400


# ----------------------------------------------------------- the decision

def decide(records_or_hosts, policy, status=None, domain=None):
    """Turn MX hostnames plus a policy into the one normalised decision.

    Pure: no DNS, no cache, no clock. This is what push re-runs to check that
    an upstream decision has not been tampered with.
    """
    hosts = [normalise_host(h) for h in (records_or_hosts or [])]
    hosts = [h for h in hosts if h]
    key, name = classify(hosts)

    if status == DNS_FAILURE:
        return _decision(domain, hosts, None, None, DNS_FAILURE, False,
                         "DNS did not answer: the email channel is held rather "
                         "than assumed safe")
    if status == NO_MX or (status is None and not hosts):
        if status is None and not hosts:
            status = NO_MX
        return _decision(domain, hosts, None, None, NO_MX, False,
                         "the domain publishes no MX record, so it accepts no "
                         "mail")

    if key is None:
        allowed = policy.get("unknown_provider_policy", "allow") == "allow"
        return _decision(domain, hosts, None, None, UNKNOWN_PROVIDER, allowed,
                         "no recognised gateway; policy is to "
                         + ("allow" if allowed else "block"))

    categories = policy.get("category_policy") or DEFAULT_CATEGORY_POLICY
    category = category_of(key)
    if key in GATEWAYS and key in (policy.get("blocked_providers") or ()):
        return _decision(domain, hosts, key, name, KNOWN_BLOCKED, False,
                         f"{name} is on this client's blocked gateway list")
    if key in GATEWAYS and categories.get(category) == "block":
        return _decision(domain, hosts, key, name, KNOWN_BLOCKED, False,
                         f"{name} is classified {category}, which this client "
                         "does not send cold email through")
    return _decision(domain, hosts, key, name, KNOWN_ALLOWED, True,
                     f"{name} is recognised and not blocked")


def _decision(domain, hosts, key, name, status, allowed, reason,
              checked_at=None):
    """The one shape an MX decision ever takes.

    Two vocabularies live here on purpose. `security_provider`,
    `email_cadence_allowed` and `checked_at` are what this codebase already
    reads; `mx_provider`, `email_eligible` and `mx_checked_at` are the names
    the interface contract uses. Both are written from the same locals in this
    one constructor, so they cannot drift - which is the only reason having
    two of them is acceptable at all.
    """
    classification = category_of(key) if key else UNKNOWN_CATEGORY
    excluded = None
    if not allowed:
        excluded = (f"{PROTECTION_REASON}:{key}" if key and key in GATEWAYS
                    else f"mx_{status}")
    return {
        "email_domain": domain,
        "mx_records": hosts,
        "security_provider": key,
        "security_provider_name": name,
        "security_detected": bool(key and key in GATEWAYS),
        "status": status,
        "email_cadence_allowed": bool(allowed),
        "reason": reason,
        "checked_at": checked_at,
        # The contract names. Same locals, one constructor, no drift.
        "mx_provider": key,
        "mx_classification": classification,
        "mx_checked_at": checked_at,
        "email_eligible": bool(allowed),
        "email_excluded_reason": excluded,
    }


def _stamp(decision, at):
    """Set the check time in both vocabularies, so neither can be stale."""
    decision["checked_at"] = at
    decision["mx_checked_at"] = at
    return decision


def for_domain(domain, config=None, cache=None, resolver=None, now=None,
               save=True):
    """The decision for one email domain, using the cache where it is fresh.

    Domain-level on purpose: fifty contacts at one company resolve once.
    """
    policy = settings(config)
    domain = normalise_host(domain)
    if not domain:
        return _decision(None, [], None, None, NO_MX, False,
                         "no email domain to check")
    if not policy["enabled"]:
        decision = _decision(domain, [], None, None, NOT_CHECKED, True,
                             "MX filtering is disabled for this client")
        return _stamp(decision, store.now())

    own_cache = cache is None
    cache = load_cache() if own_cache else cache
    entry = cache.get(domain)
    if _fresh(entry, policy["cache_days"], now):
        cached = decide(entry.get("mx_records"), policy,
                        status=entry.get("status"), domain=domain)
        _stamp(cached, entry.get("checked_at"))
        cached["cached"] = True
        return cached

    resolver = resolver or resolve
    try:
        hosts = resolver(domain)
        status = None if hosts else NO_MX
    except Exception:
        hosts, status = [], DNS_FAILURE

    decision = decide(hosts, policy, status=status, domain=domain)
    _stamp(decision, store.now())
    decision["cached"] = False
    # A DNS failure is not cached: it is a transient condition and caching it
    # would hold the channel for a week over one bad second.
    if decision["status"] != DNS_FAILURE:
        cache[domain] = {"mx_records": hosts, "status": decision["status"],
                         "checked_at": decision["checked_at"]}
        if own_cache and save:
            save_cache(cache)
    return decision


# ------------------------------------------------------- applying to records

def stored_decision(contact):
    return (contact or {}).get("mx") or {}


def fresh_decision(contact, config=None):
    """The decision re-derived from the stored MX hostnames, right now.

    The stored verdict AND the stored status are both ignored: only the
    hostnames are treated as evidence, because they are the only part a
    tampered record cannot make agree with itself.
    """
    stored = stored_decision(contact)
    if not stored:
        return None
    policy = settings(config)
    if not policy["enabled"]:
        return None
    hosts = stored.get("mx_records") or []
    # A stored DNS failure is the one status worth carrying: it means there
    # were never any hostnames to re-derive from.
    status = DNS_FAILURE if (stored.get("status") == DNS_FAILURE
                             and not hosts) else None
    return decide(hosts, policy, status=status,
                  domain=stored.get("email_domain"))


def allows_email(contact, config=None):
    """Does MX policy permit the email channel for this contact?

    Re-derived from the stored MX hostnames rather than trusting the stored
    verdict, so flipping `email_cadence_allowed` by hand changes nothing.
    """
    stored = stored_decision(contact)
    if not stored:
        return True, "no MX check has been run for this contact"
    fresh = fresh_decision(contact, config)
    if fresh is None:
        return True, "MX filtering is disabled for this client"
    return fresh["email_cadence_allowed"], fresh["reason"]


def block_reason(contact, config=None):
    """The stable reason code for a blocked contact, or None."""
    allowed, _ = allows_email(contact, config)
    if allowed:
        return None
    fresh = fresh_decision(contact, config) or stored_decision(contact)
    provider = fresh.get("security_provider")
    if provider:
        return f"{BLOCK_REASON}:{provider}"
    return f"mx_{fresh.get('status') or NOT_CHECKED}"


def apply_to_record(rec, config=None, cache=None, resolver=None, save=False):
    """Check every selected contact's email domain and store the decision."""
    from . import personalization
    results = {}
    cache = load_cache() if cache is None else cache
    for contact in personalization.selected_contacts(rec, config):
        domain = email_domain(contact.get("email"))
        if not domain:
            continue
        events.record(rec, events.MX_LOOKUP_STARTED,
                      contact_key=contact.get("key"), email_domain=domain)
        decision = for_domain(domain, config, cache=cache, resolver=resolver,
                              save=False)
        contact["mx"] = decision
        results[contact.get("key")] = decision
        if decision["status"] == DNS_FAILURE:
            events.record(rec, events.MX_LOOKUP_FAILED,
                          contact_key=contact.get("key"), email_domain=domain,
                          reason=decision["reason"])
        else:
            events.record(rec, events.MX_LOOKUP_COMPLETED,
                          contact_key=contact.get("key"), email_domain=domain,
                          provider=decision.get("security_provider"),
                          status=decision["status"])
        if decision["security_detected"]:
            events.record(rec, events.MX_SECURITY_PROVIDER_DETECTED,
                          contact_key=contact.get("key"), email_domain=domain,
                          provider=decision["security_provider"])
        if not decision["email_cadence_allowed"]:
            events.record(rec, events.EMAIL_CHANNEL_BLOCKED_MX,
                          contact_key=contact.get("key"), email_domain=domain,
                          provider=decision.get("security_provider"),
                          reason=decision["reason"])
    if save:
        save_cache(cache)
    return results


def summarise(recs, config=None):
    """Counts for the campaign summary. Reads stored decisions only."""
    from . import personalization
    counts = {"checked": 0, "blocked": 0, "allowed": 0, "unknown": 0,
              "dns_failure": 0, "no_mx": 0, "linkedin_only": 0,
              "by_provider": {}}
    for rec in recs or []:
        for contact in personalization.selected_contacts(rec, config):
            decision = stored_decision(contact)
            if not decision:
                continue
            counts["checked"] += 1
            status = decision.get("status")
            if status == KNOWN_BLOCKED:
                counts["blocked"] += 1
                key = decision.get("security_provider") or "other"
                counts["by_provider"][key] = counts["by_provider"].get(key, 0) + 1
                if contact.get("linkedin"):
                    counts["linkedin_only"] += 1
            elif status == KNOWN_ALLOWED:
                counts["allowed"] += 1
            elif status == UNKNOWN_PROVIDER:
                counts["unknown"] += 1
            elif status == DNS_FAILURE:
                counts["dns_failure"] += 1
            elif status == NO_MX:
                counts["no_mx"] += 1
    return counts


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.mx")
    sub = p.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("domain")
    check.add_argument("--client")
    run = sub.add_parser("run")
    run.add_argument("--client")
    run.add_argument("--live", action="store_true",
                     help="actually resolve. DNS is free but not silent")
    a = p.parse_args(argv)

    config = {}
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception as e:
            print(f"REFUSED: {e}")
            return 2

    if a.cmd == "check":
        decision = for_domain(a.domain, config)
        for field in ("email_domain", "status", "security_provider_name",
                      "email_cadence_allowed", "reason"):
            print(f"  {field:<24} {decision.get(field)}")
        print(f"  {'mx_records':<24} {', '.join(decision['mx_records']) or 'none'}")
        return 0 if decision["email_cadence_allowed"] else 1

    recs = store.load()
    if not a.live:
        domains = sorted({email_domain(c.get("email"))
                          for rec in recs for c in rec.get("contacts") or []
                          if email_domain(c.get("email"))})
        print(f"DRY RUN: {len(domains)} distinct email domain(s) would be "
              f"resolved once each")
        for domain in domains[:20]:
            print(f"  {domain}")
        return 0

    cache = load_cache()
    for rec in recs:
        try:
            record_config = config or clients.load(rec.get("client"))
        except Exception:
            record_config = {}
        apply_to_record(rec, record_config, cache=cache)
    save_cache(cache)
    store.save(recs)
    counts = summarise(recs, config)
    for name, value in sorted(counts.items()):
        print(f"  {name:<16} {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
