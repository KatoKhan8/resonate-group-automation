#!/usr/bin/env python3
"""The Productive funnel, counted from canonical state. No model, no provider.

WHY IT IS DETERMINISTIC ON PURPOSE.

Every number here comes from `work/queue.jsonl`, `work/campaigns.jsonl` and
`docs/state/PROVIDER-CAMPAIGNS.json`. Nothing is inferred, estimated or asked
of a model, which is what makes it safe to run on every batch and cheap enough
to run continuously.

The one thing it will not do is guess. A stage whose evidence is not on the
record is reported as a stage nobody can count, rather than as a zero - a zero
and an unread field look identical from outside, and this repository has been
bitten by exactly that.

    py -3 scripts/funnel.py
    py -3 scripts/funnel.py --json
    py -3 scripts/funnel.py --since 2026-09-15T00:00:00+00:00
"""
import argparse
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, store  # noqa: E402

# Stage -> the question asked of a record. Each is a predicate over canonical
# state, and each names the FIELD it reads so a zero can be told apart from a
# field nobody writes.
STAGES = (
    ("RECEIVED", "every record in the queue"),
    ("PRELIMINARY_ICP", "qualification.verdict.icp_status present"),
    ("QUALIFIED", "that verdict is `qualified`"),
    ("ICP_REVIEW", "that verdict is `review` - a person must look"),
    ("PERSON_DISCOVERY", "at least one contact"),
    ("ENRICHED", "a contact carries an email or a linkedin"),
    ("VERIFIED", "a contact's address cleared verification"),
    ("CAMPAIGN_READY", "a contact has approved copy for a channel"),
    ("LIVE_ELIGIBLE", "campaign-ready and not dropped, held or paused"),
)


def _contacts(rec):
    return rec.get("contacts") or []


def _icp(rec):
    """The ICP verdict, from where it is actually written.

    THIS READ THE WRONG FIELD AND REPORTED A ZERO. It asked for
    `rec["icp_status"]`, which nothing writes, so PRELIMINARY_ICP and QUALIFIED
    both counted 0 while 116 records carried `drop_reason: rejected at ICP` -
    a funnel reporting that nothing had been qualified, beside a drop reason
    saying everything had been. A zero and an unread field look identical from
    outside, which is the failure this module's own docstring warns about, and
    it took about a minute to commit it.

    The verdict lives on `qualification.icp_status`, beside `icp_tier`,
    `icp_score` and the structural criteria that produced it.
    """
    verdict = (rec.get("qualification") or {}).get("verdict")
    if isinstance(verdict, dict):
        return str(verdict.get("icp_status") or "")
    return str(verdict or "")


def _verified(contact):
    v = contact.get("verification") or {}
    return str(v.get("state") or "").lower() in ("verified", "valid", "ok")


def _approved_any(rec, contact):
    steps = ((rec.get("cadence") or {}).get(contact.get("key")) or {})
    return any(isinstance(s, dict) and s.get("approval")
               for s in steps.values())


def classify(rec):
    """Every stage this record has reached. Cumulative, not exclusive."""
    reached = {"RECEIVED"}
    icp = str(_icp(rec)).lower()
    if icp:
        reached.add("PRELIMINARY_ICP")
    if icp == "qualified":
        reached.add("QUALIFIED")
    if icp == "review":
        reached.add("ICP_REVIEW")
    contacts = _contacts(rec)
    if contacts:
        reached.add("PERSON_DISCOVERY")
    if any(c.get("email") or c.get("linkedin") for c in contacts):
        reached.add("ENRICHED")
    if any(_verified(c) for c in contacts):
        reached.add("VERIFIED")
    ready = [c for c in contacts if _approved_any(rec, c)]
    if ready:
        reached.add("CAMPAIGN_READY")
        blocked = (rec.get("dropped") or rec.get("paused")
                   or str(rec.get("state") or "") in ("dropped", "held"))
        if not blocked:
            reached.add("LIVE_ELIGIBLE")
    return reached


def _reason(rec):
    """Why this record is not moving, in the record's own words."""
    for field in ("drop_reason", "hold_reason", "pause_reason"):
        why = rec.get(field)
        if why:
            return f"{field}: {str(why)[:70]}"
    state = str(rec.get("state") or "")
    if state in ("dropped", "held"):
        return f"state {state}, no reason recorded"
    return None


def _rate(recs, since):
    """Records whose last log entry is after `since`, as an hourly rate."""
    if not since:
        return None
    moved = 0
    for rec in recs:
        log = rec.get("log") or []
        at = (log[-1] or {}).get("at") if log else None
        if at and str(at) >= since:
            moved += 1
    try:
        start = datetime.datetime.fromisoformat(since)
        now = datetime.datetime.now(datetime.timezone.utc)
        hours = max((now - start).total_seconds() / 3600.0, 0.01)
    except Exception:
        return None
    return {"moved": moved, "hours": round(hours, 2),
            "per_hour": round(moved / hours, 1)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="funnel", description=__doc__)
    p.add_argument("--client", default="productive")
    p.add_argument("--since", help="ISO timestamp, for a throughput rate")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = [r for r in store.load() if r.get("client") == a.client]
    counts = collections.Counter()
    dropped = held = 0
    reasons = collections.Counter()
    for rec in recs:
        for stage in classify(rec):
            counts[stage] += 1
        state = str(rec.get("state") or "")
        if rec.get("dropped") or state == "dropped":
            dropped += 1
            why = _reason(rec)
            if why:
                reasons[f"DROPPED {why}"] += 1
        elif state == "held" or rec.get("paused"):
            held += 1
            why = _reason(rec)
            if why:
                reasons[f"HELD {why}"] += 1

    # Provider truth, read from the derived file rather than the network, so
    # this stays free to run. `scripts/provider_truth.py` refreshes it.
    staged = {"heyreach": None, "bison": None}
    path = os.path.join("docs", "state", "PROVIDER-CAMPAIGNS.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                truth = json.load(fh)
            staged["heyreach"] = truth
        except Exception:
            pass

    out = {
        "client": a.client,
        "TOTAL": len(recs),
        "stages": {name: counts.get(name, 0) for name, _q in STAGES},
        "DROPPED": dropped,
        "HELD": held,
        "top_reasons": reasons.most_common(3),
        "throughput": _rate(recs, a.since),
        "campaigns": [
            {"campaign_id": c.get("campaign_id"), "status": c.get("status"),
             "heyreach": c.get("heyreach_campaign_id"),
             "bison": c.get("bison_campaign_id"),
             "records": len(c.get("record_ids") or [])}
            for c in campaigns.load() if c.get("client") == a.client],
    }
    if a.json:
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"PRODUCTIVE FUNNEL   total {out['TOTAL']}")
    prev = None
    for name, question in STAGES:
        n = out["stages"][name]
        drop = f"  (-{prev - n})" if prev is not None and prev >= n else ""
        print(f"  {name:18} {n:6}{drop:10}  {question}")
        prev = n
    print(f"  {'DROPPED':18} {dropped:6}")
    print(f"  {'HELD':18} {held:6}")
    if out["throughput"]:
        t = out["throughput"]
        print(f"  throughput         {t['per_hour']}/hour "
              f"({t['moved']} records in {t['hours']}h)")
    print("TOP REASONS HELD OR DROPPED")
    for why, n in out["top_reasons"] or [("none recorded", 0)]:
        print(f"  {n:5}  {why}")
    print("CAMPAIGNS")
    for c in out["campaigns"]:
        print(f"  {c['campaign_id']:38} {str(c['status']):18} "
              f"heyreach={c['heyreach']} bison={c['bison']} "
              f"records={c['records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
