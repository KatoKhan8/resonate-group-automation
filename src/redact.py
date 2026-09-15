"""Redact sensitive tokens from report text.

Provides redact() - every report generator can call this before writing text
to a tracked file.  Forbidden tokens (FORBIDDEN_NAMES, FORBIDDEN_DOMAINS,
FORBIDDEN_FIGURES from the hygiene guard) and every known record id are
replaced with stable pseudonyms so two mentions of one company stay linkable
within a document.

The pre-commit check (scripts/check_leaks.py) uses the same token sources
to report what would leak before the file is written rather than after.

Wired through outcomes.render() so the production run report cannot carry a
real record id into a tracked file.  grep for 'from src.redact' to prove
the wiring is consumed.
"""
import hashlib
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _hash_token(token, length=8):
    return hashlib.sha1(token.encode("utf-8")).hexdigest()[:length]


RECORD_PSEUDO = "<record-{}>"
FORBIDDEN_PSEUDO = "<redacted-{}>"


def _load_record_ids():
    """Record ids from the read-only snapshot.  Empty set when the snapshot
    does not exist - tests run without one, and a missing snapshot must not
    break a report renderer."""
    path = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = rec.get("id")
            if rid and isinstance(rid, str):
                ids.add(rid)
    return ids


def _forbidden_tokens():
    """Every literal token the hygiene guard forbids.

    Imported from the test module so there is one source of truth.  If the
    import ever fails (renamed module, circular dependency) the tuple falls
    back to empty and the caller still works - just without forbidden-token
    redaction.
    """
    try:
        from tests.test_fixture_hygiene import (
            FORBIDDEN_DOMAINS, FORBIDDEN_FIGURES, FORBIDDEN_NAMES,
        )
        return (tuple(FORBIDDEN_DOMAINS)
                + tuple(FORBIDDEN_NAMES)
                + tuple(FORBIDDEN_FIGURES))
    except Exception:
        return ()


def redact(text, record_ids=()):
    """Return *text* with every forbidden token and every *record_ids* entry
    replaced by a stable pseudonym.

    Stability: the same token always maps to the same pseudonym within one
    call, so "acme-corp" at line 3 and line 50 both become the same
    <record-HASH>.  Different tokens get different hashes.

    Longer tokens are replaced first so a short forbidden name inside a
    longer record id ("arbona" inside "arbona-com") does not win the race
    and corrupt the longer replacement.
    """
    if not text:
        return text

    mapping = {}

    for token in _forbidden_tokens():
        if token and token not in mapping:
            mapping[token] = FORBIDDEN_PSEUDO.format(_hash_token(token))

    for rid in record_ids:
        if rid and rid not in mapping:
            mapping[rid] = RECORD_PSEUDO.format(_hash_token(rid))

    if not mapping:
        return text

    pattern = re.compile(
        "|".join(re.escape(t)
                 for t in sorted(mapping, key=len, reverse=True)),
        re.IGNORECASE,
    )
    return pattern.sub(lambda m: mapping[m.group(0).lower()], text)


def redact_rendered(text):
    """redact() with every known record id from the snapshot.

    The one-liner a report renderer passes its output through when it does
    not know which record ids the data contained.
    """
    return redact(text, _load_record_ids())
