"""Contact identity: the per-contact id the cadence is keyed by.

BUILD-SPEC section 3 keys `cadence` by contact id. Phase 1's `slug()` keeps only
a-z0-9, which is right for a record id built from a company name but wrong for a
person: `Ćuk Šimić` collapses to `uk-imi`, and a name with no Latin characters
at all collapses to nothing.

So contact ids are built here instead, and record ids are left exactly as phase 1
made them. Nothing in this module touches `ingest.slug`.

Three rules:

  1. transliterate first, so Ćuk Šimić becomes cuk-simic rather than uk-imi
  2. if a name yields nothing usable, fall back to a deterministic id derived
     from the strongest identity the contact has: LinkedIn, then email, then name
  3. if two contacts on one record would collide, both keep a stable
     discriminator derived from their own identity, never a positional counter,
     so the id is the same on every re-run

An id already stored on the contact wins, so an id never changes under a record
that is already in flight.
"""
import hashlib
import re
import unicodedata

# Letters that do not decompose under NFKD and would otherwise be dropped.
SPECIAL = {"đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "ø": "o", "Ø": "O",
           "ł": "l", "Ł": "L", "ß": "ss", "æ": "ae", "Æ": "ae",
           "œ": "oe", "Œ": "oe", "þ": "th", "Þ": "th"}


def transliterate(text):
    """Latin-ish text to ASCII, keeping the letters rather than dropping them."""
    if not text:
        return ""
    text = "".join(SPECIAL.get(ch, ch) for ch in str(text))
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def slug(text):
    """ASCII slug of a transliterated string. Empty if nothing survives."""
    ascii_text = transliterate(text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:48]


def identity_of(contact):
    """The strongest stable thing this contact has, for hashing."""
    contact = contact or {}
    for field in ("linkedin", "email", "name"):
        value = (contact.get(field) or "").strip().lower()
        if value:
            return f"{field}:{value}"
    return ""


def digest(contact, length=6):
    identity = identity_of(contact)
    if not identity:
        return "0" * length
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:length]


def base_key(contact):
    """The readable part of the id, before any collision handling."""
    contact = contact or {}
    from_name = slug(contact.get("name"))
    if from_name:
        return from_name
    email = (contact.get("email") or "").strip().lower()
    if "@" in email:
        from_email = slug(email.split("@")[0])
        if from_email:
            return from_email
    return f"contact-{digest(contact)}"


def contact_key(contact, existing=()):
    """The contact id. Deterministic, stable, and unique within a record.

    `existing` is a mapping of already-assigned key to identity, or any iterable
    of keys. A key already stored on the contact is kept.
    """
    contact = contact or {}
    if contact.get("key"):
        return contact["key"]

    key = base_key(contact)
    taken = existing if isinstance(existing, dict) else {k: None for k in existing}
    if key not in taken:
        return key
    if taken.get(key) == identity_of(contact):
        return key                      # the same person, already assigned
    return f"{key}-{digest(contact)}"   # a real collision, both stay stable


def assign_keys(contacts):
    """Give every contact on a record its id. Returns the contacts."""
    taken = {}
    for contact in contacts or []:
        key = contact_key(contact, taken)
        contact["key"] = key
        taken[key] = identity_of(contact)
    return contacts
