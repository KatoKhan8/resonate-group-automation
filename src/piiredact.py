#!/usr/bin/env python3
"""Stable pseudonym redaction for tracked reports and pre-commit scanning.

Two entry points, one contract:

    redact(text)  returns text with every forbidden token replaced by a
                  stable pseudonym.  Two mentions of the same token get the
                  same pseudonym, so a report saying "<client-a3f2b1> overlaps
                  with <client-a3f2b1>" stays linkable without naming anybody.

    scan(text)    returns a list of (token, category, position) tuples for
                  everything that *would* be redacted.  The pre-commit check
                  uses this to report what would leak before the file is
                  written, rather than discovering it in a test run after.

The forbidden sets are imported from tests/test_fixture_hygiene.py - the same
lists the guard asserts against.  A token the guard would flag, this module
replaces.  A token the guard does not flag, this module does not touch.  The
two stay in lockstep because they read from one source.

Record IDs are domain slugs: dots become hyphens, lowered.  Every
forbidden domain produces a corresponding slug, and that slug is redacted
alongside the domain itself.  A report that names a record becomes a report
with a pseudonym tag - the count survives, the identifier does not.
"""
import hashlib
import re

from tests.test_fixture_hygiene import (
    FORBIDDEN_DOMAINS,
    FORBIDDEN_FIGURES,
    FORBIDDEN_NAMES,
)


def _pseudonym(prefix, token):
    """Deterministic short hash so the same token always maps to the same tag.

    Six hex characters from sha256 give 16M slots - enough that a collision
    within one document would be surprising, and the prefix keeps the two
    namespaces (client, record) visually distinct even if a collision occurred.
    """
    digest = hashlib.sha256(token.lower().encode("utf-8")).hexdigest()[:6]
    return f"<{prefix}-{digest}>"


def _domain_slug(domain):
    """The record id form of a domain: dots become hyphens, lowered.

    'Examplecorp.Com' becomes 'examplecorp com' with the dot replaced.  This
    is how store.new_record keys its rows, so every forbidden domain has
    exactly one slug that identifies it.
    """
    return domain.lower().replace(".", "-")


def _build_token_map():
    """One pass: every forbidden token mapped to its replacement.

    Order matters for scan/replace: longer tokens first, so a full domain is
    caught before a bare name token would match a substring of it.  Within the
    same length the order is arbitrary.
    """
    mapping = {}
    for domain in FORBIDDEN_DOMAINS:
        tag = _pseudonym("client", domain)
        mapping[domain.lower()] = tag
        slug = _domain_slug(domain)
        mapping[slug] = _pseudonym("record", slug)
    for name in FORBIDDEN_NAMES:
        mapping[name.lower()] = _pseudonym("client", name)
    for figure in FORBIDDEN_FIGURES:
        mapping[figure] = _pseudonym("figure", figure)
    return mapping


_TOKEN_MAP = _build_token_map()

_LONGEST_FIRST = sorted(_TOKEN_MAP.keys(), key=len, reverse=True)

_RECORD_ID_RE = re.compile(
    r"\b([a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"-[a-z]{2,})\b"
)

_SAFE_RECORD_IDS = frozenset({
    "dry-run", "pre-commit", "e-mail", "co-workers", "follow-up",
    "sign-up", "log-in", "opt-in", "opt-out", "self-test", "run-off",
    "walk-through", "smoke-test", "pre-check", "post-fix", "re-run",
    "sub-par", "non-zero", "non-empty", "non-null", "non-interactive",
    "built-in", "built-out", "drop-in", "long-running", "short-lived",
    "high-priority", "low-priority", "real-time", "part-time",
    "full-time", "open-source", "cross-reference", "meta-data",
    "on-hold", "in-flight", "at-risk", "up-stream", "down-stream",
    "a-b-test",
})


def _classify(token):
    """What category a token belongs to, or None if it is clean."""
    low = token.lower()
    if low in _TOKEN_MAP:
        if low in {d.lower() for d in FORBIDDEN_DOMAINS}:
            return "domain"
        if low in {_domain_slug(d) for d in FORBIDDEN_DOMAINS}:
            return "record_id"
        if low in {n.lower() for n in FORBIDDEN_NAMES}:
            return "name"
        if low in FORBIDDEN_FIGURES:
            return "figure"
    return None


def scan(text):
    """Every leak in the text, without modifying it.

    Returns a list of (token, category, start, end) tuples.  The pre-commit
    check calls this; the redact() path does not, because redact needs to
    handle overlapping tokens in a single pass rather than report them.
    """
    hits = []
    low = text.lower()
    for token in _LONGEST_FIRST:
        start = 0
        while True:
            idx = low.find(token, start)
            if idx < 0:
                break
            cat = _classify(token)
            if cat:
                hits.append((token, cat, idx, idx + len(token)))
            start = idx + 1
    for m in _RECORD_ID_RE.finditer(text):
        slug = m.group(1)
        if slug in _SAFE_RECORD_IDS:
            continue
        if slug in _TOKEN_MAP:
            continue
        hits.append((slug, "record_id_shaped", m.start(), m.end()))
    return hits


def redact(text):
    """Return text with every forbidden token replaced by a stable pseudonym.

    The replacement is case insensitive for names and domains: both casing
    variants become the same <client-abcdef>.  Figures are matched literally,
    because a comma separated number is a specific string, not a word.

    A slug that is not in the forbidden set but matches the structural pattern
    (alphanumeric hyphen, ending in a 2+ letter suffix) is also replaced, so
    a record id that was not anticipated by the forbidden list is still caught.
    """
    result = text
    low = result.lower()
    for token in _LONGEST_FIRST:
        replacement = _TOKEN_MAP[token]
        new_result = []
        start = 0
        tlow = token.lower()
        rlow = low if result is result else result.lower()
        while True:
            idx = rlow.find(tlow, start)
            if idx < 0:
                new_result.append(result[start:])
                break
            new_result.append(result[start:idx])
            new_result.append(replacement)
            start = idx + len(token)
        result = "".join(new_result)
        low = result.lower()
    def _replace_structural(m):
        slug = m.group(1)
        if slug in _SAFE_RECORD_IDS:
            return m.group(0)
        if slug.lower() in _TOKEN_MAP:
            return m.group(0)
        return m.group(0).replace(slug, _pseudonym("record", slug))
    result = _RECORD_ID_RE.sub(_replace_structural, result)
    return result
