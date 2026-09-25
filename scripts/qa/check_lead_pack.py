#!/usr/bin/env python3
"""QA check: every lead in a batch carries a research pack with identity.

    py -3 scripts/qa/check_lead_pack.py \\
        --phase pre_push --batch batch-2-2026-09-25 \\
        --workspaces <path-to-work-copy>

READ ONLY. Reads queue records and rendered copy. Reaches no provider.

## THE FOUR RULES AND THE IDENTITY REPORT

    pack_present                at least one admitted fact for this lead's
                                account
    fact_has_source_date_snippet
                                each admitted fact carries all THREE
    opener_uses_a_pack_fact     the first line of step 1 references a fact
    no_claim_outside_the_pack   no company claim traces to nothing

    identity                    per lead: admitted / refused / unverifiable
                                counts, reported separately and never summed

`unverifiable` is NOT a pass. A fact that does not say whose it is has not
been shown to be this account's.

## IDENTITY IS IMPORTED, NOT REIMPLEMENTED

`src.packfacts.identity_of` is the one test. The send path asks it; this
check asks it; two copies would disagree. Import it.

## THE RESULT SHAPE

Conforms to scripts/qa/ contract (TASK-292). Four rules in `rules`,
`counts`, `offenders`; `unverifiable` holds the identity-unverifiable leads;
arithmetic closes: clean + |offenders union unverifiable| == subjects.
"""
import argparse
import collections
import datetime
import json
import os
import sys

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from src import copylint, packfacts                          # noqa: E402
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE    # noqa: E402


def load_records(queue_path):
    """Load queue records, indexed by email and by id."""
    by_email, by_id = {}, {}
    with open(queue_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_id[str(rec.get("id"))] = rec
            for contact in rec.get("contacts") or []:
                addr = str(contact.get("email") or "").strip().lower()
                if addr:
                    by_email[addr] = rec
    return by_email, by_id


def load_rendered(path):
    """Load rendered rows from a JSONL file."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _file_evidence(path):
    """mtime and row count for one file."""
    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(path)).isoformat()
    count = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return {"path": path, "mtime": mtime, "rows": count}


def _missing_elements(fact):
    """Which of source, date, snippet are absent from an admitted fact."""
    missing = []
    if not str(fact.get("source_url") or "").strip():
        missing.append("source")
    if not str(fact.get("published_at") or "").strip():
        missing.append("date")
    if not str(fact.get("snippet") or "").strip():
        missing.append("snippet")
    return missing


def _rendered_to_lead(row):
    """Convert a rendered row to copylint's lead shape."""
    variables = row.get("variables") or {}
    steps = []
    for key in ("body_1", "body_2", "body_3", "body_4", "body_5"):
        body = variables.get(key)
        if body is None:
            continue
        subj_key = "subject_2" if key in ("body_4", "body_5") else "subject_1"
        steps.append({
            "body": body or "",
            "subject": variables.get(subj_key) or "",
        })
    return {"id": str(row.get("id") or row.get("email") or "?"),
            "steps": steps}


def _opener_uses_pack(lead, pack):
    """Does the first line of step 1 reference any pack fact?

    Uses `copylint.first_line` and `copylint.pack_text` - the same modules
    the send path asks.
    """
    steps = lead.get("steps") or []
    if not steps:
        return False
    opener = copylint.first_line(
        steps[0].get("body") if isinstance(steps[0], dict)
        else steps[0])
    supported = copylint.pack_text(pack)
    if not supported:
        return False
    tokens = [t for t in copylint._WORD.findall(opener.lower())
              if len(t) > 4]
    return any(t in supported for t in tokens)


def run(workspaces, rendered_rel="work/stage/s7-copy.jsonl",
        queue_rel="work/queue.jsonl", batch=None, campaigns=None,
        phase="pre_push"):
    """Run the lead-pack check. Returns the result dict."""
    rendered_path = os.path.join(workspaces, rendered_rel)
    queue_path_full = os.path.join(workspaces, queue_rel)

    for needed, label in ((rendered_path, "rendered copy"),
                          (queue_path_full, "queue")):
        if not os.path.isfile(needed):
            return {
                "check": "lead_pack", "phase": phase,
                "verdict": "ERROR",
                "batch": batch, "campaigns": campaigns or [],
                "subjects": 0, "clean": 0, "refused": True,
                "vacuum_reason": "%s not found at %s" % (label, needed),
                "rules": {}, "counts": {}, "offenders": {},
                "unverifiable": {},
                "identity_totals": {
                    "admitted": 0, "refused": 0, "unverifiable": 0},
                "per_lead_identity": [],
                "source_date_snippet": {"missing_source": 0,
                                        "missing_date": 0,
                                        "missing_snippet": 0},
                "three_sets": {"admitted": [], "only_unverifiable_or_refused": [],
                               "no_record": []},
                "join": {"key": "email", "matched": 0, "unmatched": 0},
                "evidence": {"files_read": []},
                "measured_at": datetime.datetime.now(
                    datetime.timezone.utc).isoformat(),
                "workspaces": workspaces,
            }

    files_read = [_file_evidence(rendered_path), _file_evidence(queue_path_full)]

    by_email, _ = load_records(queue_path_full)
    rendered = load_rendered(rendered_path)

    rules = {
        "pack_present":
            "the lead has no admitted pack fact (identity-verified)",
        "fact_has_source_date_snippet":
            "an admitted fact is missing source, date or snippet",
        "opener_uses_a_pack_fact":
            "step 1 first line does not reference any pack fact",
        "no_claim_outside_the_pack":
            "a company claim contains a specific no pack fact supports",
    }

    counts = {name: 0 for name in rules}
    offenders = {name: [] for name in rules}
    unverifiable_leads = {name: [] for name in rules}
    identity_totals = {ADMITTED: 0, REFUSED: 0, UNVERIFIABLE: 0}
    per_lead_identity = []
    missing_source = 0
    missing_date = 0
    missing_snippet = 0

    admitted_set = []
    only_unverified_set = []
    no_record_set = []

    matched = 0
    unmatched = 0

    for row in rendered:
        email = str(row.get("email") or "").strip().lower()
        lead_id = str(row.get("id") or email or "?")
        rec = by_email.get(email)

        if rec is None:
            unmatched += 1
            no_record_set.append(lead_id)
            continue

        matched += 1
        pack, unused = packfacts.pack_for(rec)
        lead = _rendered_to_lead(row)

        a_count = len(pack.get("facts") or [])
        r_count = len(unused.get(REFUSED) or [])
        u_count = len(unused.get(UNVERIFIABLE) or [])
        identity_totals[ADMITTED] += a_count
        identity_totals[REFUSED] += r_count
        identity_totals[UNVERIFIABLE] += u_count
        per_lead_identity.append({"lead": lead_id,
                                  "domain": rec.get("domain"),
                                  "admitted": a_count,
                                  "refused": r_count,
                                  "unverifiable": u_count})

        if a_count > 0:
            admitted_set.append(lead_id)
        else:
            only_unverified_set.append(lead_id)

        dirty = set()

        if a_count == 0:
            offenders["pack_present"].append(lead_id)
            dirty.add(lead_id)

        for fact in pack.get("facts") or []:
            missing = _missing_elements(fact)
            if missing:
                if "source" in missing:
                    missing_source += 1
                if "date" in missing:
                    missing_date += 1
                if "snippet" in missing:
                    missing_snippet += 1
                offenders["fact_has_source_date_snippet"].append(lead_id)
                dirty.add(lead_id)
                break

        if not _opener_uses_pack(lead, pack):
            offenders["opener_uses_a_pack_fact"].append(lead_id)
            dirty.add(lead_id)

        steps = lead.get("steps") or []
        bodies = [s.get("body") or "" if isinstance(s, dict) else str(s)
                  for s in steps]
        whole = "\n".join(bodies)
        bad = copylint.untraceable(whole, pack)
        if bad:
            offenders["no_claim_outside_the_pack"].append(lead_id)
            dirty.add(lead_id)

    subjects = matched
    all_offending = set()
    for name in rules:
        all_offending.update(offenders[name])
    clean = subjects - len(all_offending)

    if subjects == 0:
        reason = ("no rendered row matched a queue record "
                  "(%d rendered, %d matched)" % (len(rendered), matched))
        verdict = "VACUOUS"
    elif all_offending:
        verdict = "FAIL"
    else:
        verdict = "PASS"

    return {
        "check": "lead_pack",
        "phase": phase,
        "verdict": verdict,
        "batch": batch,
        "campaigns": campaigns or [],
        "subjects": subjects,
        "clean": clean,
        "refused": verdict == "FAIL",
        "rules": rules,
        "counts": counts,
        "offenders": {k: sorted(v) for k, v in offenders.items()},
        "unverifiable": {k: sorted(v) for k, v in unverifiable_leads.items()},
        "identity_totals": identity_totals,
        "per_lead_identity": per_lead_identity,
        "source_date_snippet": {
            "missing_source": missing_source,
            "missing_date": missing_date,
            "missing_snippet": missing_snippet,
        },
        "three_sets": {
            "admitted": sorted(admitted_set),
            "only_unverifiable_or_refused": sorted(only_unverified_set),
            "no_record": sorted(no_record_set),
        },
        "join": {
            "key": "email",
            "matched": matched,
            "unmatched": unmatched,
        },
        "evidence": {"files_read": files_read},
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "workspaces": workspaces,
        "vacuum_reason": ("no rendered row matched a queue record"
                          if subjects == 0 else None),
    }


def text_report(result):
    """Human-readable report lines."""
    out = ["LEAD PACK CHECK",
           "  verdict: %s" % result["verdict"],
           "  batch: %s" % result.get("batch"),
           "  subjects: %d   clean: %d" % (result["subjects"],
                                            result["clean"]),
           ""]

    j = result["join"]
    out.append("  join key: %s   matched: %d   unmatched: %d"
               % (j["key"], j["matched"], j["unmatched"]))
    out.append("")

    out.append("  THREE SETS (must add to rendered row count):")
    ts = result["three_sets"]
    out.append("    admitted:                    %d"
               % len(ts["admitted"]))
    out.append("    only unverifiable/refused:    %d"
               % len(ts["only_unverifiable_or_refused"]))
    out.append("    no record:                    %d"
               % len(ts["no_record"]))
    out.append("")

    out.append("  RULES:")
    for name, why in result["rules"].items():
        count = result["counts"].get(name, 0)
        out.append("    %-34s %d" % (name, count))
        out.append("      %s" % why)
        ids = result["offenders"].get(name) or []
        if ids:
            show = ids[:8]
            out.append("      offenders: %s%s"
                       % (", ".join(show),
                          " ..." if len(ids) > 8 else ""))
    out.append("")

    it = result["identity_totals"]
    out.append("  IDENTITY TOTALS (facts, not leads):")
    out.append("    admitted:     %d" % it["admitted"])
    out.append("    refused:      %d" % it["refused"])
    out.append("    unverifiable: %d  (NOT a pass)" % it["unverifiable"])
    out.append("")

    sds = result["source_date_snippet"]
    out.append("  SOURCE / DATE / SNIPPET missing counts:")
    out.append("    missing_source: %d" % sds["missing_source"])
    out.append("    missing_date:   %d" % sds["missing_date"])
    out.append("    missing_snippet: %d" % sds["missing_snippet"])
    out.append("")

    if result.get("vacuum_reason"):
        out.append("  VACUUM: %s" % result["vacuum_reason"])
        out.append("")

    for fr in result.get("evidence", {}).get("files_read", []):
        out.append("  file: %s  rows=%d  mtime=%s"
                   % (fr["path"], fr["rows"], fr["mtime"]))

    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python scripts/qa/check_lead_pack.py")
    p.add_argument("--phase", default="pre_push")
    p.add_argument("--batch", default=None)
    p.add_argument("--campaign", action="append", default=None)
    p.add_argument("--workspaces", required=True,
                   help="path to a copy of production work/")
    p.add_argument("--json", dest="json_out", default=None)
    args = p.parse_args(argv)

    result = run(workspaces=args.workspaces, batch=args.batch,
                 campaigns=args.campaign, phase=args.phase)

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)),
                    exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
    else:
        print(text_report(result))

    return {"PASS": 0, "FAIL": 1, "VACUOUS": 2, "UNCONFIRMED": 2,
            "ERROR": 3}.get(result["verdict"], 3)


if __name__ == "__main__":
    raise SystemExit(main())
