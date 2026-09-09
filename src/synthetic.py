#!/usr/bin/env python3
"""A 5,000-domain dataset that is deliberately messy, and deterministic.

`src/benchmark.py` already measures speed, and for that a uniform record is
the right thing: it isolates our overhead. This module is the opposite. Every
record here is broken in a specific, named way, because the failures that
matter at 5,000 domains are not slowness — they are the eighty records where a
name contains a formula, an address belongs to two companies, or a provider
returned nothing at all.

Nothing here is random. Shape is chosen by `index % len(SHAPES)`, so shape N
lives at known indices and a failing test names the defect rather than a seed.

  python -m src.synthetic --size 5000 --describe
  python -m src.synthetic --size 5000 --write     # through src/store.py
"""
import argparse
import json

from . import cadence, evidence, mx, store, verification

TODAY = "2026-08-26"

# Hostnames chosen so the MX decision is real rather than stubbed: Google and
# Microsoft must stay allowed, the gateways must block.
GOOGLE = ["aspmx.l.google.com", "alt1.aspmx.l.google.com"]
MICROSOFT = ["example-com.mail.protection.outlook.com"]
PROOFPOINT = ["mx1-us1.ppe-hosted.com"]
MIMECAST = ["eu-smtp-inbound-1.mimecast.com"]
BARRACUDA = ["cudamail.example.com.ess.barracudanetworks.com"]
NO_MX_AT_ALL = []


def _verified(email, provider="deliverable"):
    """Two independent confirmations, because that is what verified means.

    One provider used to be enough here. Under `required_confirmations: 2` a
    single answer is half of a verdict, and a synthetic dataset whose
    "verified" contacts would be held in production is not modelling
    production - it is modelling the policy we stopped using.
    """
    return {"state": verification.VERIFIED,
            "evidence": [
                verification.result("contactout", verification.S_VALID, email,
                                    deliverable=True, safe_to_send=True,
                                    at=TODAY),
                verification.result(provider, verification.S_VALID, email,
                                    deliverable=True, safe_to_send=True,
                                    at=TODAY),
            ]}


def _catch_all(email):
    return {"state": verification.ACCEPT_ALL_UNCLEARED,
            "evidence": [verification.result("deliverable",
                                             verification.S_ACCEPT_ALL, email,
                                             catch_all=True, at=TODAY)]}


def _invalid(email):
    return {"state": verification.INVALID,
            "evidence": [verification.result("deliverable",
                                             verification.S_INVALID, email,
                                             deliverable=False, at=TODAY)]}


def _unknown(email):
    return {"state": verification.UNKNOWN,
            "evidence": [verification.result("reoon", verification.S_UNKNOWN,
                                             email, at=TODAY)]}


def _contradiction(email):
    """Two providers that disagree. The resolver must hold, not pick a side."""
    return {"state": verification.HELD,
            "evidence": [
                verification.result("deliverable", verification.S_VALID, email,
                                    deliverable=True, safe_to_send=True,
                                    at=TODAY),
                verification.result("reoon", verification.S_INVALID, email,
                                    deliverable=False, at=TODAY)]}


# --------------------------------------------------------------- the shapes
#
# Each entry is (name, what it exercises). The builder below reads the name.

SHAPES = (
    ("clean_multichannel",   "the ordinary case: verified email and a profile"),
    ("email_only",           "no LinkedIn profile was ever found"),
    ("linkedin_only",        "no address exists, so email must never be planned"),
    ("no_contacts",          "enrichment returned nobody"),
    ("catch_all",            "accept-all domain, nothing cleared it"),
    ("invalid_address",      "a provider said definitively no"),
    ("unknown_verification", "no usable evidence either way"),
    ("contradiction",        "two providers disagree"),
    ("gateway_proofpoint",   "an email security gateway in front of the domain"),
    ("gateway_mimecast",     "a second gateway vendor"),
    ("gateway_barracuda",    "a third, matched by suffix not substring"),
    ("microsoft_mailbox",    "M365 must NOT be blocked for being Microsoft"),
    ("no_mx",                "the domain accepts no mail at all"),
    ("dns_failure",          "DNS did not answer; held, not assumed safe"),
    ("duplicate_email",      "the same mailbox as an earlier company"),
    ("duplicate_linkedin",   "the same profile as an earlier company"),
    ("unsubscribed",         "asked us to stop"),
    ("already_replied",      "a reply arrived, so the company is paused"),
    ("role_address",         "info@, which is a mailbox but not a person"),
    ("personal_email",       "a gmail address for a work conversation"),
    ("unicode_name",         "non-ASCII throughout"),
    ("very_long_fields",     "a name and title far past any sane column width"),
    ("formula_name",         "a name that a spreadsheet would execute"),
    ("markup_name",          "a name that a careless template would render"),
    ("no_research",          "nothing was found to personalise with"),
    ("stale_research",       "evidence too old to lead with"),
    ("dropped",              "disqualified at ingest and never enriched"),
    ("missing_name",         "an address with nobody attached to it"),
)

SHAPE_NAMES = tuple(name for name, _ in SHAPES)

# Names a spreadsheet or a shell would take literally. These are the reason
# src/export.py exists, and they belong in the dataset rather than only in a
# unit test, so the whole pipeline meets them.
HOSTILE_NAMES = (
    "=cmd|' /C calc'!A0",
    "+1234567890",
    "-2+3+cmd|' /C calc'!A0",
    "@SUM(1+9)*cmd|' /C calc'!A0",
    '=HYPERLINK("http://evil.test","click")',
    "\tTabbed Name",
    "Carriage\rReturn",
    "\x00null byte",
)

MARKUP_NAMES = (
    "<script>alert('x')</script>",
    "Ann <b>Bold</b> Smith",
    '"><img src=x onerror=alert(1)>',
    "Jos&eacute; Entity",
)

UNICODE_NAMES = ("Zoë Müller", "Åsa Ödegård", "李 明", "Ægir Þórsson",
                 "Ola Nordmann–Hansen", "أحمد الفارسي")


def _hosts_for(shape, index):
    if shape == "gateway_proofpoint":
        return PROOFPOINT, None
    if shape == "gateway_mimecast":
        return MIMECAST, None
    if shape == "gateway_barracuda":
        return BARRACUDA, None
    if shape == "microsoft_mailbox":
        return MICROSOFT, None
    if shape == "no_mx":
        return NO_MX_AT_ALL, mx.NO_MX
    if shape == "dns_failure":
        return [], mx.DNS_FAILURE
    return GOOGLE, None


def _name_for(shape, index):
    if shape == "formula_name":
        return HOSTILE_NAMES[index % len(HOSTILE_NAMES)]
    if shape == "markup_name":
        return MARKUP_NAMES[index % len(MARKUP_NAMES)]
    if shape == "unicode_name":
        return UNICODE_NAMES[index % len(UNICODE_NAMES)]
    if shape == "very_long_fields":
        return "Bartholomew " + ("Fitzgerald-Wintersbottom " * 12).strip()
    if shape == "missing_name":
        return ""
    return f"Person {index % 97}"


def _title_for(shape, index):
    if shape == "very_long_fields":
        return ("Interim Global Head of Operational Excellence and Delivery "
                "Transformation for EMEA and APAC, reporting to the COO " * 3)
    if shape == "unicode_name":
        return "Directrice des opérations"
    return ("Operations Manager", "Chief Operating Officer", "Founder",
            "Head of Delivery")[index % 4]


def _email_for(shape, rid, index):
    if shape in ("linkedin_only", "no_contacts"):
        return None
    if shape == "duplicate_email":
        return "shared.person@dupe-source.test"
    if shape == "role_address":
        return f"info@{rid}.test"
    if shape == "personal_email":
        return f"person{index % 97}@gmail.com"
    return f"person{index % 97}@{rid}.test"


def _verification_for(shape, email):
    if not email:
        return {"state": verification.UNKNOWN, "evidence": []}
    if shape == "catch_all":
        return _catch_all(email)
    if shape == "invalid_address":
        return _invalid(email)
    if shape == "unknown_verification":
        return _unknown(email)
    if shape == "contradiction":
        return _contradiction(email)
    return _verified(email)


def record(index, config=None, today=TODAY):
    """One synthetic company, broken in exactly one named way."""
    shape = SHAPE_NAMES[index % len(SHAPE_NAMES)]
    rid = f"syn{index:05d}"
    rec = store.new_record(rid, ("cold", "revive", "domains")[index % 3],
                           "demo", f"Synthetic Co {index}", f"{rid}.test")
    rec["shape"] = shape                      # for assertions, not for logic
    rec["hook"] = "runs delivery across several teams"
    rec["company_facts"] = {"industry": "Professional services",
                            "employees": 5 + (index % 900),
                            "specialties": ["delivery"]}

    if shape == "dropped":
        rec["state"] = "dropped"
        rec["drop_reason"] = "no_website"
        return rec

    rec["state"] = "drafted"
    hosts, status = _hosts_for(shape, index)
    decision = mx.decide(hosts, mx.settings(config or {}), status=status,
                         domain=f"{rid}.test")

    contacts = []
    if shape != "no_contacts":
        for n in range(2):
            email = _email_for(shape, rid, index + n)
            linkedin = None
            if shape != "email_only":
                slug = ("shared-person" if shape == "duplicate_linkedin"
                        else f"{rid}-c{n}")
                linkedin = f"https://www.linkedin.com/in/{slug}"
            contact = {
                "key": f"{rid}-c{n}",
                "name": _name_for(shape, index + n),
                "title": _title_for(shape, index + n),
                "persona": "champion" if n == 0 else "economic_buyer",
                "angle": ("ops", "founder", "finance")[index % 3],
                "email": email,
                "linkedin": linkedin,
                "verification": _verification_for(shape, email),
                # Filled in below, once the evidence it refers to exists. A
                # decision that names evidence the record does not carry is a
                # shape production can never produce.
                "personalization": {"quality": "none",
                                    "selected_evidence_ids": []},
            }
            if email:
                contact["mx"] = decision
            if shape == "unsubscribed":
                contact["unsubscribed"] = {"at": today, "source": "reply"}
            contacts.append(contact)
    rec["contacts"] = contacts

    if shape == "already_replied":
        rec["paused"] = {"since": today, "reason": "reply_received",
                         "contact_key": contacts[0]["key"] if contacts else None}

    if shape == "no_research":
        rec["research"] = []
    else:
        published = "2019-04-02" if shape == "stale_research" else "2026-08-20"
        rec["research"] = [evidence.make(
            f"Synthetic Co {index} is hiring a delivery manager to improve "
            "utilisation across the team.",
            f"https://{rid}.test/careers", "careers_page", "apify", rid,
            published_at=published, persona="operations",
            angle_words=["utilisation", "capacity"], today=today)]

    # The personalisation decision, made against the evidence that actually
    # exists on this record rather than asserted independently of it.
    for contact in contacts:
        chosen = [item["evidence_id"] for item in (rec.get("research") or [])
                  if item.get("quality") in evidence.USABLE]
        contact["personalization"] = {
            "quality": (rec["research"][0].get("quality") if chosen else "none"),
            "selected_evidence_ids": chosen,
            "persona": contact.get("persona"),
            "angle": contact.get("angle"),
        }

    for contact in contacts[:1]:
        rec.setdefault("cadence", {})[contact["key"]] = {
            key: {"channel": "email", "generated": True,
                  "subject": f"quick question about Synthetic Co {index}",
                  "body": ("Hi there,\n\nNoticed you are hiring a delivery "
                           "manager to improve utilisation across the team. "
                           "Most operations leads we speak to lose the better "
                           "part of a day every month reconciling time before "
                           "they can answer a question anyone actually asked."
                           "\n\nIs that roughly how it works with you today?\n")}
            for key in cadence.GENERATED_KEYS}
    return rec


def dataset(size=5000, config=None, today=TODAY):
    """`size` records, every shape present as long as size >= len(SHAPES)."""
    return [record(i, config, today) for i in range(size)]


def indices_of(shape, size=5000):
    """Where a given defect lives, so a test can name it rather than search."""
    if shape not in SHAPE_NAMES:
        raise KeyError(shape)
    start = SHAPE_NAMES.index(shape)
    return list(range(start, size, len(SHAPE_NAMES)))


def describe(size=5000):
    """What the dataset contains, counted rather than asserted."""
    per_shape = {}
    for offset, (name, why) in enumerate(SHAPES):
        per_shape[name] = {"count": len(range(offset, size, len(SHAPES))),
                           "exercises": why}
    return {"size": size, "shapes": len(SHAPES), "per_shape": per_shape}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=int, default=5000)
    p.add_argument("--describe", action="store_true")
    p.add_argument("--write", action="store_true",
                   help="replace the queue with the synthetic dataset")
    a = p.parse_args(argv)

    if a.describe:
        print(json.dumps(describe(a.size), indent=2))
        return 0
    recs = dataset(a.size)
    if a.write:
        store.save(recs)
        print(f"wrote {len(recs)} synthetic records to {store.queue_path()}")
    else:
        print(f"built {len(recs)} synthetic records "
              f"({len(SHAPES)} shapes); pass --write to store them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
