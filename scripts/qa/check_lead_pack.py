#!/usr/bin/env python3
"""The per-lead research pack check.  Lane F, TASK-294.

    py -3 scripts/qa/check_lead_pack.py \
        --phase pre_push \
        --workspaces <path to a copy of production work/> \
        --json work/qa/<run>/lead_pack.json

READ ONLY.  No provider write, no Apify call, no mutation of any kind.

## THE FOUR RULES

    pack_present                at least one admitted fact for this lead's
                                account
    fact_has_source_date_snippet
                                each admitted fact carries source, date AND
                                snippet.  A fact with a snippet and no source
                                is a sentence somebody wrote; a fact with a
                                source and no date is a claim about a company
                                as it was at an unknown time.
    opener_uses_a_pack_fact     the first line of step 1 references a fact
                                in the pack.  `copylint.first_line` and
                                `copylint.pack_text` do the work.
    no_claim_outside_the_pack   no company claim in any step traces to
                                nothing.  `copylint.untraceable` +
                                `copylint.specifics_in`.

## THE REPORT THAT IS NOT A RULE

    identity    per lead: admitted / refused / unverifiable counts, reported
                separately and NEVER summed into "covered".  Unverifiable is
                NOT a pass.

## THE THREE SETS

Every lead lands in exactly one of:

    admitted        carries at least one admitted pack fact
    uncovered       carries ONLY unverifiable or refused facts (or zero facts)
    no_record       matches no queue record at all

These three MUST add to the subject count.  A join that silently drops the
leads with no record is the defect lane D measured at 31%.

## THE NEGATIVE CONTROL

    --audit-pack-cache <path>   runs `identity_of` over a research-pack cache
                                and reports the 50-of-71 shape.  A check that
                                cannot fire is indistinguishable from one that
                                has nothing to fire on.
"""
import argparse
import collections
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src import copylint, packfacts
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE

RULES = {
    "pack_present":
        "at least one admitted fact for this lead's account",
    "fact_has_source_date_snippet":
        "each admitted fact carries source, date and snippet",
    "opener_uses_a_pack_fact":
        "the first line of step 1 references a pack fact",
    "no_claim_outside_the_pack":
        "no company claim in any step traces to nothing",
}

BODY_KEYS = ("body_1", "body_2", "body_3", "body_4", "body_5")


def _load_records(queue_path):
    """Queue records keyed by email and by id."""
    by_email, by_id = {}, {}
    with open(queue_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_id[rec.get("id")] = rec
            for contact in rec.get("contacts") or []:
                addr = str(contact.get("email") or "").strip().lower()
                if addr:
                    by_email[addr] = rec
    return by_email, by_id


def _steps_of(variables):
    """Rendered steps as (key, body) pairs in order."""
    out = []
    for key in BODY_KEYS:
        body = variables.get(key)
        if body is not None:
            out.append((key, body or ""))
    return out


def _file_evidence(path):
    """Mtime and row count for the evidence block."""
    if not os.path.isfile(path):
        return {"path": path, "missing": True}
    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(path), tz=datetime.timezone.utc
    ).isoformat()
    rows = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows += 1
    return {"path": path, "rows": rows, "mtime": mtime}


def _fact_well_formed(fact):
    """Which of source, date, snippet does this fact carry?"""
    missing = []
    if not str(fact.get("source_url") or "").strip():
        missing.append("source")
    if not str(fact.get("published_at") or "").strip():
        missing.append("date")
    if not str(fact.get("snippet") or "").strip():
        missing.append("snippet")
    return missing


def run(workspaces, phase="pre_push", batch=None, campaigns=None,
        json_path=None):
    """The check.  Returns the result dict.

    `workspaces` is the path to a copy of production's `work/` tree.
    """
    rendered_path = os.path.join(workspaces, "stage", "s7-copy.jsonl")
    queue_file = os.path.join(workspaces, "queue.jsonl")

    for path, label in [(rendered_path, "s7-copy.jsonl"),
                        (queue_file, "queue.jsonl")]:
        if not os.path.isfile(path):
            return _error("missing %s in %s" % (label, workspaces))

    by_email, _ = _load_records(queue_file)

    per_lead = []
    identity_totals = {ADMITTED: 0, REFUSED: 0, UNVERIFIABLE: 0}
    three_sets = {"admitted": [], "uncovered": [], "no_record": []}
    offenders = {name: [] for name in RULES}
    unverifiable_offenders = {name: [] for name in RULES}
    missing_element_counts = {"source": 0, "date": 0, "snippet": 0}
    subjects = 0

    with open(rendered_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            subjects += 1
            lead_id = str(row.get("id") or row.get("contact")
                          or row.get("email") or "?")
            email = str(row.get("email") or "").strip().lower()
            rec = by_email.get(email)

            if rec is None:
                three_sets["no_record"].append(lead_id)
                per_lead.append({
                    "lead_id": lead_id,
                    "set": "no_record",
                    "admitted": 0, "refused": 0, "unverifiable": 0,
                })
                continue

            pack, unused = packfacts.pack_for(rec)
            n_admitted = len(pack["facts"])
            n_refused = len(unused[REFUSED])
            n_unverifiable = len(unused[UNVERIFIABLE])

            identity_totals[ADMITTED] += n_admitted
            identity_totals[REFUSED] += n_refused
            identity_totals[UNVERIFIABLE] += n_unverifiable

            if n_admitted > 0:
                three_sets["admitted"].append(lead_id)
            else:
                three_sets["uncovered"].append(lead_id)

            lead_entry = {
                "lead_id": lead_id,
                "record_id": rec.get("id"),
                "domain": rec.get("domain"),
                "set": "admitted" if n_admitted > 0 else "uncovered",
                "admitted": n_admitted,
                "refused": n_refused,
                "unverifiable": n_unverifiable,
                "rule_offences": [],
            }

            # --- rule 1: pack_present ---
            if n_admitted == 0:
                offenders["pack_present"].append(lead_id)
                lead_entry["rule_offences"].append("pack_present")

            # --- rule 2: fact_has_source_date_snippet ---
            malformed_facts = []
            for fact in pack["facts"]:
                missing = _fact_well_formed(fact)
                if missing:
                    malformed_facts.append(missing)
                    for elem in missing:
                        missing_element_counts[elem] += 1
            if malformed_facts:
                offenders["fact_has_source_date_snippet"].append(lead_id)
                lead_entry["rule_offences"].append(
                    "fact_has_source_date_snippet")

            # --- rule 3: opener_uses_a_pack_fact ---
            steps = _steps_of(row.get("variables") or {})
            opener = copylint.first_line(steps[0][1] if steps else "")
            supported = copylint.pack_text(pack)
            opener_tokens = [t for t in copylint._WORD.findall(opener.lower())
                             if len(t) > 4]
            if not supported or not any(t in supported for t in opener_tokens):
                offenders["opener_uses_a_pack_fact"].append(lead_id)
                lead_entry["rule_offences"].append("opener_uses_a_pack_fact")

            # --- rule 4: no_claim_outside_the_pack ---
            bodies_text = "\n".join(body for _, body in steps)
            untraceable = copylint.untraceable(bodies_text, pack)
            if untraceable:
                offenders["no_claim_outside_the_pack"].append(lead_id)
                lead_entry["rule_offences"].append(
                    "no_claim_outside_the_pack")

            per_lead.append(lead_entry)

    if subjects == 0:
        return _vacuous(workspaces, rendered_path, queue_file)

    # --- build the result document ---
    all_offending_ids = set()
    for ids in offenders.values():
        all_offending_ids.update(ids)
    clean_ids = set()
    for entry in per_lead:
        if entry["lead_id"] not in all_offending_ids:
            if entry.get("set") != "no_record":
                clean_ids.add(entry["lead_id"])
    no_record_ids = set(three_sets["no_record"])
    clean_count = len(clean_ids)

    counts = {name: len(offenders[name]) for name in RULES}
    arithmetic_ok = (clean_count + len(all_offending_ids | no_record_ids)
                     == subjects)

    result = {
        "check": "lead_pack",
        "phase": phase,
        "verdict": _verdict(offenders, subjects),
        "batch": batch,
        "campaigns": campaigns or [],
        "subjects": subjects,
        "clean": clean_count,
        "refused": any(counts[n] > 0 for n in RULES),
        "rules": dict(RULES),
        "counts": counts,
        "offenders": {k: sorted(v) for k, v in offenders.items()},
        "unverifiable": {k: sorted(v) for k, v in
                         unverifiable_offenders.items()},
        "three_sets": {
            "admitted": sorted(three_sets["admitted"]),
            "uncovered": sorted(three_sets["uncovered"]),
            "no_record": sorted(three_sets["no_record"]),
        },
        "three_set_counts": {
            "admitted": len(three_sets["admitted"]),
            "uncovered": len(three_sets["uncovered"]),
            "no_record": len(three_sets["no_record"]),
        },
        "identity_totals": dict(identity_totals),
        "missing_elements": dict(missing_element_counts),
        "arithmetic_ok": arithmetic_ok,
        "evidence": {
            "files_read": [
                _file_evidence(rendered_path),
                _file_evidence(queue_file),
            ],
            "provider_reads_skipped": False,
        },
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "workspaces": workspaces,
    }

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, indent=2, sort_keys=False)
            fh.write("\n")

    return result


def _verdict(offenders, subjects):
    if subjects == 0:
        return VERDICT_VACUOUS
    if any(len(v) > 0 for v in offenders.values()):
        return VERDICT_FAIL
    return VERDICT_PASS


def _error(reason):
    return {
        "check": "lead_pack",
        "verdict": VERDICT_ERROR,
        "error": reason,
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "rules": dict(RULES),
        "counts": {name: 0 for name in RULES},
        "offenders": {name: [] for name in RULES},
        "unverifiable": {name: [] for name in RULES},
        "three_sets": {"admitted": [], "uncovered": [], "no_record": []},
        "three_set_counts": {"admitted": 0, "uncovered": 0, "no_record": 0},
        "identity_totals": {ADMITTED: 0, REFUSED: 0, UNVERIFIABLE: 0},
        "missing_elements": {"source": 0, "date": 0, "snippet": 0},
        "arithmetic_ok": True,
        "evidence": {"files_read": [], "provider_reads_skipped": False},
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
    }


def _vacuous(workspaces, rendered_path, queue_file):
    reason = "no rendered rows found in %s" % rendered_path
    if not os.path.isfile(rendered_path):
        reason = "rendered copy missing: %s" % rendered_path
    elif not os.path.isfile(queue_file):
        reason = "queue missing: %s" % queue_file
    result = _error(reason)
    result["verdict"] = VERDICT_VACUOUS
    return result


VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_VACUOUS = "VACUOUS"
VERDICT_ERROR = "ERROR"


def audit_pack_cache(path):
    """The negative control: run identity_of over a research-pack cache.

    Against the quarantined pre-fix pilot cache this finds the 50 job rows
    of 71 that were a different company.  A check that cannot fire is
    indistinguishable from one that has nothing to fire on.
    """
    if not os.path.isfile(path):
        return "PACK-CACHE IDENTITY AUDIT\n  %s\n  FILE NOT FOUND" % path

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    per_source = collections.defaultdict(
        lambda: {ADMITTED: 0, REFUSED: 0, UNVERIFIABLE: 0})
    all_wrong = []
    total_rows = 0

    for entry in (data or {}).values():
        if not isinstance(entry, dict):
            continue
        domain = packfacts.normalise_domain(entry.get("domain"))
        source = entry.get("profile") or "?"
        rows = [r for r in entry.get("rows") or [] if isinstance(r, dict)]
        if not rows:
            continue
        total_rows += len(rows)
        for row in rows:
            verdict = packfacts.identity_of(row, domain)
            per_source[source][verdict] += 1
        verdicts = [packfacts.identity_of(row, domain) for row in rows]
        if all(v != ADMITTED for v in verdicts):
            all_wrong.append((domain, source, len(rows)))

    out = ["PACK-CACHE IDENTITY AUDIT", "  %s" % path, "",
           "  total rows: %d" % total_rows, "",
           "  %-24s %8s %8s %8s" % ("source", "admitted", "refused",
                                     "unverifiable")]
    for source in sorted(per_source):
        c = per_source[source]
        out.append("  %-24s %8d %8d %8d"
                   % (source, c[ADMITTED], c[REFUSED], c[UNVERIFIABLE]))
    out.append("")
    out.append("  accounts where NO row was this company: %d" % len(all_wrong))
    for domain, source, count in sorted(all_wrong)[:12]:
        out.append("    %-28s %-14s %d rows" % (domain, source, count))
    return "\n".join(out)


def report_lines(result):
    """Human-readable summary of a result."""
    out = []
    out.append("LEAD PACK CHECK  verdict=%s" % result.get("verdict"))
    out.append("  subjects=%d  clean=%d  refused=%s"
               % (result["subjects"], result["clean"], result["refused"]))
    out.append("")

    ts = result.get("three_set_counts", {})
    out.append("  THREE SETS (must add to %d):" % result["subjects"])
    out.append("    admitted:   %d" % ts.get("admitted", 0))
    out.append("    uncovered:  %d" % ts.get("uncovered", 0))
    out.append("    no_record:  %d" % ts.get("no_record", 0))
    total = ts.get("admitted", 0) + ts.get("uncovered", 0) + ts.get(
        "no_record", 0)
    out.append("    sum:        %d  %s"
               % (total, "OK" if total == result["subjects"] else "MISMATCH"))
    out.append("")

    idt = result.get("identity_totals", {})
    out.append("  IDENTITY TOTALS")
    out.append("    admitted:      %d" % idt.get(ADMITTED, 0))
    out.append("    refused:       %d" % idt.get(REFUSED, 0))
    out.append("    unverifiable:  %d  (NOT a pass)" % idt.get(UNVERIFIABLE, 0))
    out.append("")

    me = result.get("missing_elements", {})
    out.append("  SOURCE/DATE/SNIPPET missing counts")
    for elem in ("source", "date", "snippet"):
        out.append("    %-10s %d" % (elem, me.get(elem, 0)))
    out.append("")

    out.append("  RULES")
    for name, why in RULES.items():
        count = result["counts"].get(name, 0)
        out.append("    %-34s %4d  %s" % (name, count, why))
        ids = result.get("offenders", {}).get(name, [])
        if ids:
            show = ids[:6]
            out.append("      offenders: %s%s"
                       % (", ".join(show), " ..." if len(ids) > 6 else ""))
    out.append("")
    out.append("  arithmetic closed: %s" % result.get("arithmetic_ok"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python scripts/qa/check_lead_pack.py")
    ap.add_argument("--phase", default="pre_push",
                    choices=("pre_push", "post_push", "ongoing"))
    ap.add_argument("--batch")
    ap.add_argument("--campaign", action="append", dest="campaigns")
    ap.add_argument("--workspaces", required=False,
                    help="path to a copy of production work/")
    ap.add_argument("--json", dest="json_path",
                    help="where to write the result JSON")
    ap.add_argument("--audit-pack-cache", dest="pack_cache",
                    help="run the negative control over a pack cache")
    args = ap.parse_args(argv)

    if args.pack_cache:
        print(audit_pack_cache(args.pack_cache))
        if not args.workspaces:
            return 0

    if not args.workspaces:
        ap.error("--workspaces is required (or --audit-pack-cache alone)")

    result = run(workspaces=args.workspaces, phase=args.phase,
                 batch=args.batch, campaigns=args.campaigns,
                 json_path=args.json_path)

    for line in report_lines(result):
        print(line)

    if result["verdict"] == VERDICT_PASS:
        return 0
    if result["verdict"] in (VERDICT_VACUOUS, VERDICT_ERROR):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
