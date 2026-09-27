#!/usr/bin/env python3
"""QA check: per-lead research pack — identity, not presence.

TASK-294. Lane F, the standing QA suite. Pre-push. Subject: lead.

THE QUESTION THIS ANSWERS

Does every lead in this batch carry at least one research fact that is
provably about THAT company, with a source, a date and a snippet — and does
the copy's first line actually use one?

FOUR RULES

    pack_present            at least one admitted fact for this lead's account
    fact_has_source_date_snippet
                            each admitted fact carries all THREE
    opener_uses_a_pack_fact the first line of step 1 references a fact in
                            the pack
    no_claim_outside_the_pack
                            no company claim in any step traces to nothing

ONE REPORT (not a rule, the reason the task exists)

    identity                per lead: admitted / refused / unverifiable
                            counts, reported separately and never summed
                            into "covered"

THE NEGATIVE CONTROL

`--audit-pack-cache` runs the identity test over a research-pack cache and
finds the 50-of-71 wrong-company rows. A check that cannot fire is
indistinguishable from one that has nothing to fire on.

READ ONLY. No provider write, no Apify call.

Usage:
    py -3 scripts/qa/check_lead_pack.py \\
        --phase pre_push \\
        --workspaces <path to work/ copy> \\
        --json work/qa/<run>/lead_pack.json
"""
import argparse
import collections
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR

from src import copylint, packfacts
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE

# ------------------------------------------------------------- exit codes

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

# --------------------------------------------------------- rule names

RULE_PACK_PRESENT = "pack_present"
RULE_FACT_WELL_FORMED = "fact_has_source_date_snippet"
RULE_OPENER_USES_PACK = "opener_uses_a_pack_fact"
RULE_NO_UNTRACEABLE = "no_claim_outside_the_pack"

RULES = (
    RULE_PACK_PRESENT,
    RULE_FACT_WELL_FORMED,
    RULE_OPENER_USES_PACK,
    RULE_NO_UNTRACEABLE,
)


# --------------------------------------------------------- helpers

def load_records(queue_path):
    """Load queue records keyed by email and by id."""
    by_email, by_id = {}, {}
    with open(queue_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_id[rec.get("id")] = rec
            for contact in rec.get("contacts") or []:
                address = str(contact.get("email") or "").strip().lower()
                if address:
                    by_email[address] = rec
    return by_email, by_id


def load_rendered(rendered_path):
    """Load rendered rows."""
    rows = []
    with open(rendered_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def steps_of_rendered(row):
    """The rendered steps as (key, subject, body) tuples."""
    variables = row.get("variables") or {}
    body_keys = ("body_1", "body_2", "body_3", "body_4", "body_5")
    out = []
    for i, key in enumerate(body_keys, start=1):
        body = variables.get(key)
        if body is None:
            continue
        subject = (variables.get("subject_2") if i >= 4
                   else variables.get("subject_1"))
        out.append((key, subject or "", body or ""))
    return out


def fact_well_formed(fact):
    """Does this fact carry source, date and snippet?

    Returns a list of MISSING element names. Empty means well-formed.
    """
    missing = []
    snippet = str(fact.get("snippet") or "").strip()
    source = str(fact.get("source_url") or "").strip()
    date = str(fact.get("published_at") or "").strip()
    if not snippet:
        missing.append("snippet")
    if not source:
        missing.append("source")
    if not date:
        missing.append("date")
    return missing


def opener_uses_pack(body, pack):
    """Does the first line of the body reference a pack fact?

    Uses `copylint.first_line` and `copylint.pack_text` — the same seam the
    send path asks.
    """
    opener = copylint.first_line(body)
    supported = copylint.pack_text(pack)
    if not supported:
        return False
    tokens = [t for t in copylint._WORD.findall(opener.lower())
              if len(t) > 4]
    return bool(tokens) and any(t in supported for t in tokens)


# --------------------------------------------------------- the check

def run(phase, workspaces, rendered_rel="work/stage/s7-copy.jsonl",
        queue_rel="work/queue.jsonl"):
    """Run the lead-pack check. Returns a result dict."""
    rendered_path = os.path.join(workspaces, rendered_rel)
    queue_path = os.path.join(workspaces, queue_rel)

    if not os.path.isfile(rendered_path):
        return {"verdict": ERROR,
                "reason": "rendered file not found: %s" % rendered_path,
                "subjects": 0}
    if not os.path.isfile(queue_path):
        return {"verdict": ERROR,
                "reason": "queue file not found: %s" % queue_path,
                "subjects": 0}

    by_email, by_id = load_records(queue_path)
    rendered = load_rendered(rendered_path)

    # --- join rendered rows to queue records
    matched = []
    no_record = []
    for row in rendered:
        address = str(row.get("email") or "").strip().lower()
        rec = by_email.get(address)
        if rec is None:
            no_record.append({
                "email_hash": _hash_email(address),
                "row_id": row.get("id") or row.get("contact") or "?",
            })
        else:
            matched.append((row, rec))

    subjects = len(rendered)
    if subjects == 0:
        return {"verdict": ERROR,
                "reason": "no rendered rows in %s" % rendered_path,
                "subjects": 0}

    # --- per-lead evaluation
    per_lead = []
    offenders = {name: [] for name in RULES}
    identity_totals = {ADMITTED: 0, REFUSED: 0, UNVERIFIABLE: 0}
    missing_elements = collections.Counter()

    # Three sets for the 128 report
    admitted_leads = []
    only_unverifiable_or_refused = []
    no_record_leads = []

    for row, rec in matched:
        lead_id = str(rec.get("id") or "?")
        domain = rec.get("domain") or ""
        steps = steps_of_rendered(row)
        pack, unused = packfacts.pack_for(rec)

        # Identity counts
        n_admitted = len(pack["facts"])
        n_refused = len(unused[REFUSED])
        n_unverifiable = len(unused[UNVERIFIABLE])
        identity_totals[ADMITTED] += n_admitted
        identity_totals[REFUSED] += n_refused
        identity_totals[UNVERIFIABLE] += n_unverifiable

        lead_entry = {
            "lead_id": lead_id,
            "domain": domain,
            "admitted": n_admitted,
            "refused": n_refused,
            "unverifiable": n_unverifiable,
            "rules_fired": [],
        }

        # Classify into three sets
        if n_admitted > 0:
            admitted_leads.append(lead_id)
        elif n_refused > 0 or n_unverifiable > 0:
            only_unverifiable_or_refused.append(lead_id)

        # Rule 1: pack_present
        if n_admitted == 0:
            offenders[RULE_PACK_PRESENT].append(lead_id)
            lead_entry["rules_fired"].append(RULE_PACK_PRESENT)

        # Rule 2: fact_has_source_date_snippet
        for fact in pack["facts"]:
            missing = fact_well_formed(fact)
            for elem in missing:
                missing_elements[elem] += 1
            if missing:
                if lead_id not in offenders[RULE_FACT_WELL_FORMED]:
                    offenders[RULE_FACT_WELL_FORMED].append(lead_id)
                lead_entry["rules_fired"].append(RULE_FACT_WELL_FORMED)
                break

        # Rule 3: opener_uses_a_pack_fact
        if steps:
            first_body = steps[0][2]
            if not opener_uses_pack(first_body, pack):
                offenders[RULE_OPENER_USES_PACK].append(lead_id)
                lead_entry["rules_fired"].append(RULE_OPENER_USES_PACK)
        else:
            offenders[RULE_OPENER_USES_PACK].append(lead_id)
            lead_entry["rules_fired"].append(RULE_OPENER_USES_PACK)

        # Rule 4: no_claim_outside_the_pack
        bodies = [s[2] for s in steps]
        subjects_text = " ".join(str(s[1] or "") for s in steps)
        full_text = "\n".join(bodies + [subjects_text])
        untraceable = copylint.untraceable(full_text, pack)
        if untraceable:
            offenders[RULE_NO_UNTRACEABLE].append(lead_id)
            lead_entry["rules_fired"].append(RULE_NO_UNTRACEABLE)

        per_lead.append(lead_entry)

    # No-record leads
    for entry in no_record:
        no_record_leads.append(entry["row_id"])

    # Verdict
    any_offenders = any(offenders[r] for r in RULES)
    if any_offenders:
        verdict = FAIL
    elif not matched:
        verdict = VACUOUS
    else:
        verdict = PASS

    return {
        "verdict": verdict,
        "phase": phase,
        "subjects": subjects,
        "matched": len(matched),
        "no_record_count": len(no_record),
        "three_sets": {
            "admitted": admitted_leads,
            "only_unverifiable_or_refused": only_unverifiable_or_refused,
            "no_record": no_record_leads,
        },
        "identity_totals": dict(identity_totals),
        "per_rule": {
            name: {
                "subjects": subjects,
                "clean": subjects - len(offenders[name]),
                "offenders": offenders[name],
            }
            for name in RULES
        },
        "missing_elements": dict(missing_elements),
        "per_lead": per_lead,
        "evidence": {
            "files_read": [
                {"path": rendered_path, "rows": len(rendered)},
                {"path": queue_path,
                 "rows": len(by_id)},
            ],
        },
    }


def audit_pack_cache(path):
    """The negative control: identity test over a research-pack cache.

    Re-measures the 50-of-71 wrong-company defect from the quarantined
    pre-fix pilot cache. Delegates to `scripts.packfact_check.audit_pack_cache`
    — the same module lane D built — because two copies of an identity test
    is how the two come to disagree about who a fact belongs to.
    """
    from scripts import packfact_check
    return packfact_check.audit_pack_cache(path)


def _hash_email(address):
    """A one-way hash of an email address. No PII in committed output."""
    import hashlib
    return hashlib.sha256(address.encode("utf-8")).hexdigest()[:16]


def report(result):
    """Human-readable report."""
    out = ["LEAD-PACK CHECK", ""]
    out.append("  verdict:  %s" % result.get("verdict", ERROR))
    out.append("  subjects: %d" % result.get("subjects", 0))
    out.append("  matched:  %d" % result.get("matched", 0))
    out.append("  no_record: %d" % result.get("no_record_count", 0))
    out.append("")

    # Three sets
    three = result.get("three_sets", {})
    out.append("  THREE SETS (must add to subjects)")
    out.append("    admitted:                    %d"
               % len(three.get("admitted", [])))
    out.append("    only_unverifiable_or_refused: %d"
               % len(three.get("only_unverifiable_or_refused", [])))
    out.append("    no_record:                   %d"
               % len(three.get("no_record", [])))
    out.append("")

    # Identity totals
    identity = result.get("identity_totals", {})
    out.append("  IDENTITY TOTALS")
    out.append("    admitted:     %d" % identity.get(ADMITTED, 0))
    out.append("    refused:      %d" % identity.get(REFUSED, 0))
    out.append("    unverifiable: %d" % identity.get(UNVERIFIABLE, 0))
    out.append("")

    # Per-rule
    out.append("  PER-RULE TABLE")
    out.append("    %-35s %6s %6s %6s"
               % ("rule", "clean", "offend", "subjects"))
    for name in RULES:
        rule_data = result.get("per_rule", {}).get(name, {})
        out.append("    %-35s %6d %6d %6d"
                   % (name,
                      rule_data.get("clean", 0),
                      len(rule_data.get("offenders", [])),
                      rule_data.get("subjects", 0)))
    out.append("")

    # Missing elements
    missing = result.get("missing_elements", {})
    if missing:
        out.append("  MISSING ELEMENTS (source/date/snippet)")
        for elem, count in sorted(missing.items()):
            out.append("    %-12s %d" % (elem, count))
        out.append("")

    # Offenders (first 20)
    for name in RULES:
        rule_data = result.get("per_rule", {}).get(name, {})
        off = rule_data.get("offenders", [])
        if off:
            out.append("  %s offenders (%d)" % (name, len(off)))
            for lid in off[:20]:
                out.append("    %s" % lid)
            out.append("")

    return "\n".join(out)


# --------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python scripts/qa/check_lead_pack.py")
    p.add_argument("--phase", required=True,
                   choices=("pre_push", "post_push", "ongoing"))
    p.add_argument("--workspaces", required=True,
                   help="path to a copy of production work/")
    p.add_argument("--rendered", default="work/stage/s7-copy.jsonl",
                   help="relative path to rendered copy inside workspaces")
    p.add_argument("--queue", default="work/queue.jsonl",
                   help="relative path to queue inside workspaces")
    p.add_argument("--audit-pack-cache", dest="pack_cache",
                   help="run the negative control over a pack cache")
    p.add_argument("--json", dest="json_path",
                   help="where to write the result JSON")
    args = p.parse_args(argv)

    if args.pack_cache:
        print(audit_pack_cache(args.pack_cache))
        if not os.path.isdir(args.workspaces):
            return 0

    result = run(phase=args.phase, workspaces=args.workspaces,
                 rendered_rel=args.rendered, queue_rel=args.queue)

    if result.get("subjects", 0) == 0:
        print("ERROR: %s" % result.get("reason", "no subjects"))
        return EXIT_UNCONFIRMED

    if args.json_path:
        os.makedirs(os.path.dirname(args.json_path) or ".", exist_ok=True)
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)

    print(report(result))

    if result["verdict"] == PASS:
        return EXIT_PASS
    elif result["verdict"] == FAIL:
        return EXIT_FAIL
    elif result["verdict"] == VACUOUS:
        return EXIT_UNCONFIRMED
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
