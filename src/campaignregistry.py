"""The campaign registry: what exists at both providers, and what may not be
built twice.

## Why this is not PROVIDER-CAMPAIGNS.json

`docs/state/PROVIDER-CAMPAIGNS.json` records HeyReach truth for one Resonate
campaign and the client's 83. It carries no EmailBison campaigns, no cohort or
hypothesis tagging, no duplicate detection, and no pre-creation check. It is a
snapshot of provider state; this module is a policy layer on top of it.

## What a duplicate is

Same-or-near name, same sequence hash, same lead list, or created within
minutes with the same shape. A duplicate is reported, not judged: two
campaigns with one shape may be a deliberate geo split. The detector names
the resemblance and leaves the decision to a human.

## The pre-creation check

A future campaign build calls `pre_creation_check` before creating anything.
It answers "does a campaign for this cohort or hypothesis already exist?"
The check is consumed by `src.campaigns.new_campaign` - the whole chain is
tested, not just the function in isolation.
"""
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(ROOT, "docs", "state", "CAMPAIGN-REGISTRY.json")


def load():
    """The registry as a dict. Returns an empty structure when the file is
    absent - a missing registry is not a crash, it is a reason to generate
    one."""
    if not os.path.exists(REGISTRY_PATH):
        return {"campaigns": [], "generated_at": None, "duplicates": []}
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _normalise_name(name):
    """Collapse whitespace and case for comparison. Two campaigns named
    'OMEGA 3' and 'omega   3' are the same name."""
    return re.sub(r"\s+", " ", str(name or "").strip().lower())


def _name_similarity(a, b):
    """Whether two names are the same or near-equal. Exact match after
    normalisation, or one is a prefix of the other with at most a trailing
    variant suffix (v2, -australia, etc.)."""
    na, nb = _normalise_name(a), _normalise_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return "exact"
    if na.startswith(nb) or nb.startswith(na):
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        remainder = longer[len(shorter):].strip(" -_")
        if not remainder:
            return "exact"
        if re.match(r"^(v\d|copy|dup|\d+|australia|au|us|uk|dach|\w{1,5})$",
                    remainder, re.IGNORECASE):
            return "near"
    return None


def find_duplicates(campaigns=None):
    """Pairs of campaigns that look alike. Reads the registry by default.

    Returns a list of {campaign_a, campaign_b, reason} dicts. Each reason
    names the resemblance: same name, near name, same sequence hash, same
    lead list, or created within minutes with the same shape.

    A duplicate is reported, not judged. Two campaigns with one shape may be
    a deliberate geo split.
    """
    registry = load() if campaigns is None else {"campaigns": campaigns}
    entries = registry.get("campaigns") or []
    findings = []
    seen = set()

    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            if a.get("provider") != b.get("provider"):
                continue
            reasons = []

            same_name = _name_similarity(a.get("name"), b.get("name"))
            if same_name:
                reasons.append(f"same-or-near name ({same_name})")

            seq_a = a.get("sequence_hash")
            seq_b = b.get("sequence_hash")
            if seq_a and seq_b and seq_a == seq_b:
                reasons.append("same sequence hash")

            list_a = a.get("lead_list_id")
            list_b = b.get("lead_list_id")
            if list_a and list_b and str(list_a) == str(list_b):
                reasons.append("same lead list")

            created_a = a.get("created") or ""
            created_b = b.get("created") or ""
            if created_a and created_b and _within_minutes(created_a, created_b, 5):
                shape_a = _shape_key(a)
                shape_b = _shape_key(b)
                if shape_a and shape_b and shape_a == shape_b:
                    reasons.append("created within 5 minutes with same shape")

            if reasons:
                pair_key = tuple(sorted([
                    f"{a.get('provider')}:{a.get('id')}",
                    f"{b.get('provider')}:{b.get('id')}",
                ]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    findings.append({
                        "campaign_a": _slim(a),
                        "campaign_b": _slim(b),
                        "reasons": reasons,
                    })
    return findings


def _slim(entry):
    """The fields a duplicate report carries. No PII, no bulk."""
    return {
        "provider": entry.get("provider"),
        "id": entry.get("id"),
        "name": entry.get("name"),
        "status": entry.get("status"),
        "created": entry.get("created"),
    }


def _within_minutes(a, b, minutes):
    """Whether two ISO timestamps are within `minutes` of each other."""
    try:
        from datetime import datetime, timezone
        ta = _parse_ts(a)
        tb = _parse_ts(b)
        if ta is None or tb is None:
            return False
        return abs((ta - tb).total_seconds()) <= minutes * 60
    except Exception:
        return False


def _parse_ts(value):
    """Best-effort ISO timestamp parse. Returns None on failure rather than
    guessing."""
    from datetime import datetime, timezone
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _shape_key(entry):
    """A coarse identity for 'same shape': status category and sequence
    node count. Two campaigns created minutes apart with the same status
    bucket and sequence size are the same shape."""
    status = str(entry.get("status") or "").upper()
    bucket = "ACTIVE" if status in ("IN_PROGRESS", "ACTIVE", "RUNNING",
                                     "QUEUED") else \
             "DRAFT" if status == "DRAFT" else \
             "PAUSED" if status == "PAUSED" else \
             "FINISHED" if status in ("FINISHED", "COMPLETED") else "OTHER"
    nodes = entry.get("sequence_nodes") or 0
    return f"{bucket}:{nodes}"


def pre_creation_check(cohort_key=None, hypothesis=None, name=None,
                       provider=None, registry=None):
    """Does a campaign for this cohort or hypothesis already exist?

    Called before creating a campaign. Returns {exists: bool, matches: [...],
    reasons: [...]}. An empty registry is not a pass - it is reported as
    'registry not generated' so a missing file does not silently permit
    everything.

    At least one of cohort_key, hypothesis or name must be given. A check
    with no query is not a check.
    """
    if not cohort_key and not hypothesis and not name:
        return {"exists": False, "matches": [],
                "reasons": ["no query: provide cohort_key, hypothesis or name"],
                "registry_present": False}

    reg = registry if registry is not None else load()
    entries = reg.get("campaigns") or []
    if not entries and reg.get("generated_at") is None:
        return {"exists": False, "matches": [],
                "reasons": ["registry not generated - run scripts/campaign_registry.py"],
                "registry_present": False}

    matches = []
    reasons = []

    for entry in entries:
        if provider and entry.get("provider") != provider:
            continue

        entry_cohort = entry.get("cohort_key") or ""
        entry_hypothesis = entry.get("hypothesis") or ""
        entry_name = entry.get("name") or ""

        if cohort_key and entry_cohort and cohort_key == entry_cohort:
            matches.append(_slim(entry))
            reasons.append(
                f"cohort {cohort_key} already served by "
                f"{entry.get('provider')}:{entry.get('id')} ({entry_name})")

        if hypothesis and entry_hypothesis:
            if _normalise_name(hypothesis) == _normalise_name(entry_hypothesis):
                if _slim(entry) not in matches:
                    matches.append(_slim(entry))
                reasons.append(
                    f"hypothesis '{hypothesis}' matches "
                    f"{entry.get('provider')}:{entry.get('id')} ({entry_name})")

        if name:
            sim = _name_similarity(name, entry_name)
            if sim:
                if _slim(entry) not in matches:
                    matches.append(_slim(entry))
                reasons.append(
                    f"name '{name}' is {sim} match with "
                    f"{entry.get('provider')}:{entry.get('id')} ({entry_name})")

    return {
        "exists": bool(matches),
        "matches": matches,
        "reasons": reasons,
        "registry_present": True,
    }
