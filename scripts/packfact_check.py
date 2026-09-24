#!/usr/bin/env python3
"""Check every RENDERED step against the pack facts of the lead's own account.

    py -3 scripts/packfact_check.py --rendered work/stage/s7-copy.jsonl

READ ONLY. It opens the rendered copy and the queue, writes nothing, and
reaches no provider.

## THE QUESTION IT ASKS

A rendered step must not assert a fact the research pack does not carry. The
lint that enforces that on a batch is `src/copylint.py`; this is the same
question asked of copy that has ALREADY been rendered and is waiting to be
pushed, so the answer exists before the push rather than during it.

## IDENTITY, NOT PRESENCE

The measured precedent, 2026-09-24: 50 of 71 job rows in the research pilot
belonged to a DIFFERENT company, because `companyName` is a text filter and
not an identity match. Re-measured here from the quarantined pre-fix cache:
on FIVE of the eight accounts that returned job rows, every one of the ten was
somebody else's. A pack assembled from those rows would have put a
stranger's open roles into a client's personalised email, and every
presence-only check would have called that pack "covered".

So a fact is admitted to a lead's pack only when `src.packfacts.identity_of`
can show it is THIS account's fact. That test is not duplicated here: the
send path asks the same module, and two copies of an identity test is how the
two come to disagree about who a fact belongs to.

A row that answers neither the website question nor the source-host one is
not admitted and not refused: it is counted
separately as unverifiable, because "this fact's owner cannot be established"
and "this fact belongs to somebody else" are different problems with
different fixes, and a check that folded them together would report the
second as the first. All three numbers are printed - a check that silently
kept the refused ones would report exactly the coverage the pilot reported
before anybody measured it.

`--audit-pack-cache` runs the same identity test over a research-pack cache
and is the negative control: against the quarantined pre-fix pilot cache it
finds the 50 job rows of 71 that were a different company, which is how a
check that cannot fire is told apart from one that has nothing to fire on.

## WHAT IT CANNOT DO

It inherits `copylint.untraceable`'s reach: it extracts SPECIFICS - figures,
dates, quoted phrases, capitalised multi-word names - from sentences that
make a claim about the company, and requires each to appear in a pack fact.
A sentence that is wrong while carrying no specific ("you must be struggling
with scale") passes this and is a judgement call for a person. Said out loud
because a check believed to cover more than it does is worse than none.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import copylint, packfacts  # noqa: E402
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE  # noqa: E402

#: The rendered variables that carry a step's BODY, in step order. `subject_1`
#: and `subject_2` are checked too, under the step whose body they head.
BODY_KEYS = ("body_1", "body_2", "body_3", "body_4", "body_5")


identity_of = packfacts.identity_of
normalise_domain = packfacts.normalise_domain
pack_for = packfacts.pack_for


def load_records(queue_path):
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


def steps_of(variables):
    """The rendered steps, as `(key, subject, body)`, in order."""
    out = []
    for i, key in enumerate(BODY_KEYS, start=1):
        body = variables.get(key)
        if body is None:
            continue
        subject = (variables.get("subject_2") if i >= 4
                   else variables.get("subject_1"))
        out.append((key, subject or "", body or ""))
    return out


def check(rendered_path, queue_path):
    by_email, _ = load_records(queue_path)
    result = {
        "rendered_rows": 0, "matched_to_a_record": 0, "no_record": 0,
        "rendered_steps": 0, "empty_steps": 0,
        "leads_with_a_pack": 0, "leads_without_a_pack": 0,
        "facts_admitted": 0, "facts_refused_on_identity": 0,
        "facts_identity_unverifiable": 0,
        "steps_with_an_unsupported_specific": 0,
        "leads_with_an_unsupported_specific": 0,
        "leads_whose_opener_no_fact_supports": 0,
        "unsupported_by_step": collections.Counter(),
        "top_unsupported_specifics": collections.Counter(),
    }
    offenders = []
    with open(rendered_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            result["rendered_rows"] += 1
            address = str(row.get("email") or "").strip().lower()
            rec = by_email.get(address)
            if rec is None:
                result["no_record"] += 1
                continue
            result["matched_to_a_record"] += 1
            pack, unused = pack_for(rec)
            result["facts_admitted"] += len(pack["facts"])
            result["facts_refused_on_identity"] += len(unused[REFUSED])
            result["facts_identity_unverifiable"] += len(unused[UNVERIFIABLE])
            if pack["facts"]:
                result["leads_with_a_pack"] += 1
            else:
                result["leads_without_a_pack"] += 1

            steps = steps_of(row.get("variables") or {})
            supported = copylint.pack_text(pack)
            dirty = []
            for key, subject, body in steps:
                result["rendered_steps"] += 1
                if not str(body).strip():
                    result["empty_steps"] += 1
                bad = copylint.untraceable("%s\n%s" % (subject, body), pack)
                if bad:
                    result["steps_with_an_unsupported_specific"] += 1
                    result["unsupported_by_step"][key] += 1
                    result["top_unsupported_specifics"].update(bad)
                    dirty.append((key, bad))
            if dirty:
                result["leads_with_an_unsupported_specific"] += 1
                offenders.append({"record": rec.get("id"),
                                  "domain": rec.get("domain"),
                                  "steps": [{"step": k, "unsupported": v}
                                            for k, v in dirty]})
            opener = copylint.first_line(steps[0][2] if steps else "")
            tokens = [t for t in copylint._WORD.findall(opener.lower())
                      if len(t) > 4]
            if not supported or not any(t in supported for t in tokens):
                result["leads_whose_opener_no_fact_supports"] += 1
    return result, offenders


def report(result, offenders, show=8):
    out = ["PACK-FACT CHECK", ""]
    order = ("rendered_rows", "matched_to_a_record", "no_record",
             "rendered_steps", "empty_steps",
             "leads_with_a_pack", "leads_without_a_pack",
             "facts_admitted", "facts_refused_on_identity",
             "facts_identity_unverifiable",
             "leads_whose_opener_no_fact_supports",
             "leads_with_an_unsupported_specific",
             "steps_with_an_unsupported_specific")
    for key in order:
        out.append("  %-38s %7d" % (key, result[key]))
    out.append("")
    out.append("  unsupported specifics by step")
    for key in BODY_KEYS:
        count = result["unsupported_by_step"].get(key, 0)
        if count:
            out.append("    %-10s %7d" % (key, count))
    out.append("")
    out.append("  most common unsupported specific")
    for value, count in result["top_unsupported_specifics"].most_common(show):
        out.append("    %5d  %s" % (count, value))
    out.append("")
    for row in offenders[:show]:
        out.append("  %s (%s)" % (row["record"], row["domain"]))
        for step in row["steps"]:
            out.append("    %-10s %s" % (step["step"],
                                         ", ".join(step["unsupported"][:4])))
    return "\n".join(out)


def audit_pack_cache(path):
    """The identity test, run over a research-pack cache's own rows.

    THE NEGATIVE CONTROL. Today's estate research is a site crawl and every
    row of it is on the account's own domain, so the identity test admits all
    of it and never fires - which is indistinguishable from a test that
    cannot fire. This runs the same test over the pack cache, where the
    defect actually happened, and reports what it refuses.
    """
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    per_source = collections.defaultdict(collections.Counter)
    all_wrong = []
    for entry in (data or {}).values():
        if not isinstance(entry, dict):
            continue
        domain = normalise_domain(entry.get("domain"))
        source = entry.get("profile") or "?"
        rows = [r for r in entry.get("rows") or [] if isinstance(r, dict)]
        if not rows:
            continue
        verdicts = [identity_of(row, domain) for row in rows]
        for verdict in verdicts:
            per_source[source][verdict] += 1
        if verdicts and all(v != ADMITTED for v in verdicts):
            all_wrong.append((domain, source, len(rows)))
    out = ["PACK-CACHE IDENTITY AUDIT", "  %s" % path, "",
           "  %-24s %8s %8s %8s" % ("source", "this", "other", "unknown")]
    for source in sorted(per_source):
        counts = per_source[source]
        out.append("  %-24s %8d %8d %8d"
                   % (source, counts[ADMITTED], counts[REFUSED],
                      counts[UNVERIFIABLE]))
    out.append("")
    out.append("  accounts where NO row was this company: %d" % len(all_wrong))
    for domain, source, count in sorted(all_wrong)[:12]:
        out.append("    %-28s %-14s %d rows" % (domain, source, count))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python scripts/packfact_check.py")
    p.add_argument("--rendered",
                   help="the rendered copy, one JSON object per line")
    p.add_argument("--audit-pack-cache", dest="pack_cache",
                   help="run the identity test over a research-pack cache")
    p.add_argument("--queue", default=os.environ.get("QUEUE"),
                   help="the queue holding each lead's research")
    p.add_argument("--json", dest="as_json", action="store_true")
    args = p.parse_args(argv)
    if args.pack_cache:
        print(audit_pack_cache(args.pack_cache))
        if not args.rendered:
            return 0
    if not args.rendered:
        p.error("--rendered, or --audit-pack-cache")
    if not args.queue:
        p.error("--queue, or QUEUE in the environment")
    result, offenders = check(args.rendered, args.queue)
    if args.as_json:
        payload = dict(result)
        payload["unsupported_by_step"] = dict(result["unsupported_by_step"])
        payload["top_unsupported_specifics"] = dict(
            result["top_unsupported_specifics"].most_common(40))
        payload["offenders"] = offenders[:200]
        print(json.dumps(payload, indent=1, default=str))
    else:
        print(report(result, offenders))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
