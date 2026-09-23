"""Name derivation and honorific stripping for greetings.

TASK-269. Three call sites derived a greeting first name three different ways:

    cadence.py:582        (contact["name"] or "").split()[0]
    bisonfactory.py:389   contact["first_name"] else name.split()[0]
    heyreachfactory.py:1266   contact_key.split("_")[0]

The honorific defect: a contact named "Ing Christoph Lemmer" greets "Ing"
because the first token of the name is an honorific, not a given name. The
lint rule `_names_match` passed it because "Ing" was a token of the full name.

This module is the ONE derivation. Every call site that renders a greeting
first name goes through `greeting_first_name`. The function:

1. Derives the raw first token from the contact (first_name, name, or key)
2. Strips a closed-list honorific prefix
3. Never strips the only token (a single-token "Ing" is left alone)

An unrecognised prefix is left alone. Over-stripping turns "Mags" into nothing
and is the worse failure: a name that renders empty is caught by
`_refuse_bad_greetings`, but a name silently shortened to somebody else's is not.
"""

# Closed list. Case- and punctuation-insensitive match on the whole token only.
# An unrecognised prefix is left alone rather than stripped.
# Trailing punctuation is stripped by _normalise_token, so entries here are
# without trailing periods.
HONORIFICS = frozenset({
    "dr",
    "prof",
    "dipl.-ing", "dipl.ing",
    "ing",
    "mag",
    "di",
    "mr",
    "mrs",
    "ms",
})


def _normalise_token(token):
    """Lowercase and strip trailing punctuation for honorific comparison."""
    return token.lower().rstrip(".,")


def strip_honorific(name):
    """Strip a leading honorific from a name string.

    Returns the name with the first token removed if it is a recognised
    honorific AND there are remaining tokens. If stripping would leave nothing,
    the original is returned unchanged.

    An unrecognised prefix is left alone. "Mags Bennett" returns "Mags Bennett".
    """
    if not name or not name.strip():
        return name
    parts = name.split()
    if len(parts) <= 1:
        return name
    first = parts[0]
    if _normalise_token(first) in HONORIFICS:
        return " ".join(parts[1:])
    return name


def greeting_first_name(contact):
    """Derive the greeting first name from a contact dict.

    The unified derivation for every call site that renders a greeting.
    Preference order:
    1. contact["name"] if present (full name gives context for stripping)
    2. contact["first_name"] if present (single token, no stripping possible)

    When `name` is available, strips a leading honorific and returns the next
    token. When only `first_name` is available (a single token), returns it
    unchanged - stripping would empty it. A single-token name is never emptied.

    Returns the cleaned first name string, or empty string if no name found.
    """
    if not contact:
        return ""

    name = (contact.get("name") or "").strip()
    if name:
        cleaned = strip_honorific(name)
        return cleaned.split()[0] if cleaned else ""

    first_name = (contact.get("first_name") or "").strip()
    if first_name:
        return first_name

    return ""
