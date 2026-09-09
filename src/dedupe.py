#!/usr/bin/env python3
"""Recognising the same person twice, and refusing to guess when unsure.

## Why this is not a nice-to-have

The same person arrives through several doors. ContactOut returns them for
company.com, AI Ark returns them again for the rebrand domain, an old batch has
them under a personal address, and two clients in the same vertical both want
to talk to them. Sending twice reads as carelessness; sending from two clients
in one week reads as a leak.

## Strong identity, and nothing else

An identity is asserted only from something that cannot be coincidence:

    normalized email        one address is one mailbox
    canonical LinkedIn URL  one profile is one member
    provider lead id        the provider's own key, namespaced by provider
    record_id + contact_key our own key, which is where it all started

Names and companies are never identity. Two people called Jan Novak at two
Novak Consultings are two people, and "Jan Novak" at "Novak Consulting" and
"Novak Consulting GmbH" might be one - which is exactly why a human decides.
Name similarity produces `possible_duplicate` and a review queue entry. It never
merges anything, and there is no code path here that can.

## Nothing is deleted

A duplicate keeps its record and gains `duplicate_of`, `duplicate_scope` and
`duplicate_reason`. Deleting it would destroy the evidence that the decision
was ever made, and the second copy is often the one with the better data.

## Scopes, because "duplicate" depends on who is asking

    batch       the same person twice in one upload: always a duplicate
    campaign    the same person twice in one campaign: always a duplicate
    client      the same person in two of one client's campaigns: configurable
    cross_client two clients targeting the same person: configurable, and
                OFF by default, because two Resonate clients may legitimately
                sell to the same company

Cross-client is off by default on purpose: turning it on means one client's
targeting silently suppresses another's, which is a commercial decision and
not a technical one.
"""
import re

from . import linkedin, store

BATCH = "batch"
CAMPAIGN = "campaign"
CLIENT = "client"
CROSS_CLIENT = "cross_client"
SCOPES = (BATCH, CAMPAIGN, CLIENT, CROSS_CLIENT)

# What kind of identifier proved it.
BY_EMAIL = "email"
BY_LINKEDIN = "linkedin"
BY_PROVIDER_ID = "provider_id"
BY_RECORD = "record_contact"
POSSIBLE = "possible_name_match"

STRONG = (BY_EMAIL, BY_LINKEDIN, BY_PROVIDER_ID, BY_RECORD)

DEFAULTS = {
    "within_batch": True,
    "within_campaign": True,
    "within_client": True,
    "cross_client": False,
    "flag_possible_name_matches": True,
}


def settings(config):
    block = ((config or {}).get("dedupe") or {})
    merged = dict(DEFAULTS)
    for key in merged:
        if key in block:
            merged[key] = block[key] is True
    return merged


# ------------------------------------------------------------------ identity

def normalise_email(email):
    """One mailbox, one string. Case and surrounding space only.

    Deliberately NOT stripping plus-addressing or dots: john+a@x.test and
    john@x.test are the same Gmail mailbox but not the same mailbox everywhere,
    and a wrong merge here suppresses a real person.
    """
    if not isinstance(email, str) or "@" not in email:
        return None
    local, _, domain = email.strip().lower().partition("@")
    domain = domain.rstrip(".")
    return f"{local}@{domain}" if local and domain else None


def provider_ids(contact):
    """Provider-issued ids, namespaced so two providers cannot collide."""
    out = []
    for name in ("contactout_id", "aiark_id", "bison_lead_id",
                 "heyreach_lead_id", "provider_id"):
        value = (contact or {}).get(name)
        if value not in (None, "", 0):
            out.append(f"{name}:{value}")
    for provider, value in ((contact or {}).get("provider_ids") or {}).items():
        if value not in (None, "", 0):
            out.append(f"{provider}:{value}")
    return sorted(set(out))


def keys_for(rec, contact):
    """Every strong identifier this contact carries, best first."""
    keys = []
    email = normalise_email(contact.get("email"))
    if email:
        keys.append((BY_EMAIL, f"email:{email}"))
    profile = linkedin.canonical(contact.get("linkedin"))
    if profile:
        keys.append((BY_LINKEDIN, f"linkedin:{profile}"))
    for pid in provider_ids(contact):
        keys.append((BY_PROVIDER_ID, f"provider:{pid}"))
    if rec.get("id") and contact.get("key"):
        keys.append((BY_RECORD, f"record:{rec['id']}:{contact['key']}"))
    return keys


def identity_of(rec, contact):
    """The single best identity key, or None when the contact has no strong id.

    A contact with no email, no profile and no provider id cannot be
    deduplicated, and saying so is better than inventing a key from a name.
    """
    keys = keys_for(rec, contact)
    strong = [key for kind, key in keys if kind in (BY_EMAIL, BY_LINKEDIN,
                                                    BY_PROVIDER_ID)]
    return strong[0] if strong else None


def _name_key(rec, contact):
    """A weak key, used ONLY to raise a possible duplicate for review."""
    name = re.sub(r"[^a-z ]", "", (contact.get("name") or "").lower()).strip()
    company = re.sub(r"[^a-z ]", "", (rec.get("company") or "").lower()).strip()
    # Company suffixes vary between records for the same firm.
    for suffix in (" gmbh", " ltd", " limited", " bv", " ab", " as", " oy",
                   " sro", " doo", " inc", " llc", " sa", " ag", " plc"):
        if company.endswith(suffix):
            company = company[: -len(suffix)].strip()
    return f"{name}|{company}" if name and company else None


# ---------------------------------------------------------------- detection

def find(records, scope=BATCH, config=None, campaign_ids=None):
    """Every duplicate in a set of records. Marks nothing; just reports.

    Returns a list of findings, each naming the two contacts, the identifier
    that matched, and whether it is strong enough to act on.
    """
    policy = settings(config)
    seen, findings = {}, []
    weak = {}

    for rec in records or []:
        for contact in rec.get("contacts") or []:
            here = (rec.get("id"), contact.get("key"))
            for kind, key in keys_for(rec, contact):
                if kind == BY_RECORD:
                    continue                # its own key never collides
                first = seen.get(key)
                if first is None:
                    seen[key] = (here, rec, contact)
                    continue
                (there, first_rec, first_contact) = first
                if there == here:
                    continue
                if scope == CROSS_CLIENT and first_rec.get("client") == rec.get("client"):
                    continue
                if scope != CROSS_CLIENT and first_rec.get("client") != rec.get("client"):
                    continue                # a different client is another scope
                findings.append({
                    "scope": scope, "kind": kind, "key": key, "strong": True,
                    "record_id": rec.get("id"), "contact_key": contact.get("key"),
                    "duplicate_of": {"record_id": there[0], "contact_key": there[1]},
                    "reason": f"same {kind}: {key.split(':', 1)[-1]}",
                })
                break                       # one finding per contact is enough

            if policy["flag_possible_name_matches"]:
                name_key = _name_key(rec, contact)
                if not name_key:
                    continue
                previous = weak.get(name_key)
                if previous and previous != here and not any(
                        f["record_id"] == rec.get("id")
                        and f["contact_key"] == contact.get("key")
                        for f in findings):
                    findings.append({
                        "scope": scope, "kind": POSSIBLE, "key": name_key,
                        "strong": False,
                        "record_id": rec.get("id"),
                        "contact_key": contact.get("key"),
                        "duplicate_of": {"record_id": previous[0],
                                         "contact_key": previous[1]},
                        "reason": ("same name at a similar company: a human "
                                   "decides, nothing is merged"),
                    })
                weak.setdefault(name_key, here)
    return findings


def mark(records, findings):
    """Write the audit fields. Never deletes, never merges.

    A possible name match is recorded as `possible_duplicate` and does not set
    `duplicate_of`, because that field means "this is the same person" and a
    name is not evidence of that.
    """
    by_id = {rec.get("id"): rec for rec in records or []}
    marked = 0
    for finding in findings:
        rec = by_id.get(finding["record_id"])
        if rec is None:
            continue
        for contact in rec.get("contacts") or []:
            if contact.get("key") != finding["contact_key"]:
                continue
            if finding["strong"]:
                contact["duplicate_of"] = finding["duplicate_of"]
                contact["duplicate_scope"] = finding["scope"]
                contact["duplicate_reason"] = finding["reason"]
            else:
                contact["possible_duplicate"] = {
                    "of": finding["duplicate_of"], "reason": finding["reason"]}
            marked += 1
            store.log(rec, "dedupe", finding["reason"],
                      contact=contact.get("key"))
    return marked


def is_duplicate(contact):
    """Strong duplicates only. A possible name match never blocks anything."""
    return bool((contact or {}).get("duplicate_of"))


def duplicate_reason(contact):
    return (contact or {}).get("duplicate_reason")


# --------------------------------------------------------- company collision

# Prefixes that are the same site, not a different company.
HOST_PREFIXES = ("www.", "mail.", "smtp.", "mx.", "email.", "go.", "info.")


def normalise_domain(domain):
    domain = (domain or "").strip().lower().rstrip(".")
    for prefix in HOST_PREFIXES:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain or None


def same_company(left, right):
    """Only when the registrable domain is identical after obvious prefixes.

    company.com and company.co.uk are NOT merged: they are frequently separate
    legal entities with separate buyers, and merging them would silently drop
    half a campaign. A caller who knows better records the link explicitly.
    """
    a, b = normalise_domain(left), normalise_domain(right)
    return bool(a) and a == b


def company_collisions(records):
    """Domains that look related but are not automatically merged."""
    by_domain, findings = {}, []
    for rec in records or []:
        key = normalise_domain(rec.get("domain"))
        if not key:
            continue
        if key in by_domain and by_domain[key] != rec.get("id"):
            findings.append({
                "kind": "same_domain", "record_id": rec.get("id"),
                "other": by_domain[key], "domain": key,
                "reason": "two records share one domain after normalisation",
            })
        else:
            by_domain.setdefault(key, rec.get("id"))

    # A mail domain that differs from the website is a rebrand signal, not a
    # merge instruction.
    for rec in records or []:
        mail = normalise_domain((rec.get("company_facts") or {}).get("email_domain"))
        site = normalise_domain(rec.get("domain"))
        if mail and site and mail != site:
            findings.append({
                "kind": "mail_domain_differs", "record_id": rec.get("id"),
                "domain": site, "other": mail,
                "reason": ("the mail domain differs from the website domain: "
                           "possible rebrand, flagged for review"),
            })
    return findings
