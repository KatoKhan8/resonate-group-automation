#!/usr/bin/env python3
"""What a run expected to spend, what the providers say it spent, and the gap.

## Why this exists

On 2026-09-09 I reported "zero credits spent" from ContactOut's `count` field
alone. That was not sufficient evidence: ContactOut meters at least three
buckets independently - `count` for email, `search_count`, `phone_count` - and
one counter is not a total. The correction stands as this module's premise.

Then on 2026-09-10 a run's internal ledger expected 26 credits, 22 of them
ContactOut, and all three ContactOut counters were unchanged before and after.
Both numbers were real. Neither was the answer on its own, and nothing in the
system was able to say so.

## The five things a cost claim can be

    RECONCILED         expected spend, observed spend, and they agree
    FREE_CONFIRMED     expected nothing, observed nothing
    UNPRICED           the calls were ledgered, the price table says zero,
                       and the provider's counter says otherwise
    COST_UNRECONCILED  expected and observed disagree with no such excuse
    ESTIMATED_ONLY     no authoritative counter exists for this provider

`COST_UNRECONCILED` is the point of the module. It is not an error state and
it is not a failure of the run - it is the honest name for "these two numbers
do not match and we do not know why", which is the answer more often than
anybody would like. Reporting it as either number would be a lie by rounding.

## What this will never do

Invent a price. Convert between units it was not told the exchange rate for.
Report an estimate as a measurement. A provider that exposes no counter gets
ESTIMATED_ONLY and keeps it, however confident the internal table is.

Nothing here calls a provider. `snapshot()` is passed the readings.
"""
import argparse
import json

RECONCILED = "RECONCILED"
FREE_CONFIRMED = "FREE_CONFIRMED"
COST_UNRECONCILED = "COST_UNRECONCILED"
ESTIMATED_ONLY = "ESTIMATED_ONLY"
# The ledger saw the calls; the price table says they are free and the
# provider's counter disagrees. Distinct from COST_UNRECONCILED, and the
# distinction is not pedantic: one sends somebody hunting for a call that
# bypassed the ledger, the other tells them the price table is wrong. The
# first version of this module reported Apify as the former and was wrong -
# `COSTS["apify-research"]` is 0 because Apify bills compute units rather
# than credits, so ten correctly-ledgered calls expect nothing and cost
# $0.66.
UNPRICED = "UNPRICED"

# Which providers expose a counter this system can read, and in what unit.
#
# The unit matters and is deliberately not normalised. ContactOut meters in
# credits across three independent buckets; Apify bills compute in US dollars.
# Adding them would produce a number with no meaning, so they are reconciled
# separately and reported separately.
AUTHORITATIVE = {
    "contactout": ("count", "search_count", "phone_count"),
    "apify": ("usd",),
}

# Providers with no readable counter. Named rather than inferred, so that a
# provider nobody has thought about lands here loudly instead of silently
# passing as reconciled.
NO_COUNTER = ("deliverable", "reoon", "aiark", "blitz", "heyreach",
              "emailbison", "bison", "slack", "unknown")


def expected_by_provider(records, since=None):
    """What the waterfall ledger believes was spent, per provider.

    Reads `expected_cost`, which `waterfall.record_step` writes at the moment
    of the call. `actual_cost` is a field the ledger has always had and that
    nothing has ever populated, because no provider here reports a per-call
    price - which is exactly why reconciliation has to happen at the level of
    a run rather than a call.
    """
    out = {}
    for rec in records or []:
        for row in (rec.get("waterfall") or []):
            if not isinstance(row, dict):
                continue
            if since and str(row.get("at") or "") < since:
                continue
            provider = row.get("provider") or "unknown"
            bucket = out.setdefault(provider, {"calls": 0, "expected": 0,
                                               "by_call": {}})
            bucket["calls"] += 1
            bucket["expected"] += int(row.get("expected_cost") or 0)
            call = bucket["by_call"].setdefault(
                row.get("call") or "unknown", {"calls": 0, "expected": 0})
            call["calls"] += 1
            call["expected"] += int(row.get("expected_cost") or 0)
    return out


def observed(before, after):
    """The delta each authoritative counter moved. Never negative-by-guess.

    A counter that went DOWN is reported as it read. Quotas reset, plans
    change, and a negative delta is a fact about the provider rather than
    something to clamp to zero - clamping is how "the counter reset" becomes
    "we spent nothing".
    """
    out = {}
    for provider, buckets in AUTHORITATIVE.items():
        b, a = (before or {}).get(provider) or {}, (after or {}).get(provider) or {}
        if not isinstance(b, dict) or not isinstance(a, dict):
            b = {"usd": b} if not isinstance(b, dict) else b
            a = {"usd": a} if not isinstance(a, dict) else a
        deltas = {}
        for name in buckets:
            start, end = b.get(name), a.get(name)
            if start is None or end is None:
                deltas[name] = None          # not read is not zero
            else:
                deltas[name] = round(end - start, 6)
        out[provider] = deltas
    return out


def _verdict(provider, expected, deltas, calls=0):
    """One provider's reconciliation, with the sentence behind it."""
    if provider not in AUTHORITATIVE:
        return ESTIMATED_ONLY, (
            f"{provider} exposes no counter this system can read, so "
            f"{expected} is an estimate from the internal price table and "
            f"cannot be confirmed or refuted")

    readings = [v for v in (deltas or {}).values() if v is not None]
    if not readings:
        return ESTIMATED_ONLY, (
            f"{provider} has counters but none were read on both sides of the "
            f"run, so there is no delta to compare {expected} against")

    moved = sum(abs(v) for v in readings)
    if expected == 0 and moved == 0:
        return FREE_CONFIRMED, (
            f"nothing was expected and no counter moved: "
            f"{_fmt(deltas)}")
    if expected > 0 and moved > 0:
        return RECONCILED, (
            f"{expected} expected and the counters moved: {_fmt(deltas)}. "
            f"The units are not converted, so this is agreement in direction "
            f"and magnitude rather than an audited equality")
    if expected > 0 and moved == 0:
        return COST_UNRECONCILED, (
            f"{expected} credit(s) expected and NO counter moved "
            f"({_fmt(deltas)}). Either these operations do not meter against "
            f"the buckets this system can read, or the counters lag. It must "
            f"not be reported as {expected} spent, and it must not be "
            f"reported as free")
    if calls:
        return UNPRICED, (
            f"{calls} ledgered call(s) expected nothing and the counters "
            f"moved: {_fmt(deltas)}. The calls were recorded; the internal "
            f"price table says they are free and the provider disagrees. "
            f"This is a wrong price, not a bypass")
    return COST_UNRECONCILED, (
        f"nothing was expected, NO call was ledgered, and the counters moved: "
        f"{_fmt(deltas)}. Something spent money without going through the "
        f"ledger at all")


def _fmt(deltas):
    return ", ".join(f"{k} {'unread' if v is None else v:+}"
                     if v is not None else f"{k} unread"
                     for k, v in sorted((deltas or {}).items()))


def reconcile(before, after, records, since=None):
    """The whole run: expected, observed, and a verdict per provider."""
    expected = expected_by_provider(records, since=since)
    deltas = observed(before, after)
    providers = sorted(set(expected) | set(deltas) | set(NO_COUNTER)
                       & set(expected))
    rows = []
    for provider in providers:
        want = (expected.get(provider) or {}).get("expected", 0)
        calls = (expected.get(provider) or {}).get("calls", 0)
        if not calls and provider not in deltas:
            continue
        status, why = _verdict(provider, want, deltas.get(provider), calls)
        rows.append({"provider": provider, "calls": calls,
                     "expected": want, "observed": deltas.get(provider),
                     "status": status, "why": why,
                     "by_call": (expected.get(provider) or {}).get("by_call", {})})
    return {
        "providers": rows,
        "unreconciled": [r["provider"] for r in rows
                         if r["status"] == COST_UNRECONCILED],
        "unpriced": [r["provider"] for r in rows if r["status"] == UNPRICED],
        "estimated_only": [r["provider"] for r in rows
                           if r["status"] == ESTIMATED_ONLY],
        # Deliberately NOT a total. Credits and dollars do not add up, and a
        # single headline number is what made "zero credits spent" sayable.
        "total": None,
        "total_why": "credits and dollars are different units and are not "
                     "summed; read the per-provider rows",
    }


# Worst first. An operator reads the top of the report, so the top has to be
# the thing that needs a decision - not whichever provider sorts first
# alphabetically, which put a FREE_CONFIRMED line above an unreconciled one.
SEVERITY = (COST_UNRECONCILED, UNPRICED, ESTIMATED_ONLY, RECONCILED,
            FREE_CONFIRMED)


def report(result):
    """The human-readable form. One line per provider, worst first."""
    lines = []
    rows = sorted(result.get("providers") or [],
                  key=lambda r: (SEVERITY.index(r["status"])
                                 if r["status"] in SEVERITY else len(SEVERITY),
                                 r["provider"]))
    for row in rows:
        lines.append(f"{row['status']:<18} {row['provider']:<14} "
                     f"expected={row['expected']:<6} calls={row['calls']}")
        lines.append(f"{'':<18} {row['why']}")
    if result.get("unreconciled"):
        lines.append("")
        lines.append(f"UNRECONCILED: {', '.join(result['unreconciled'])} - "
                     f"these must not be reported as spent or as free")
    if result.get("unpriced"):
        lines.append(f"UNPRICED: {', '.join(result['unpriced'])} - real money "
                     f"the internal price table records as zero, so no cap "
                     f"can bound it")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.costs")
    p.add_argument("--before", required=True, help="snapshot JSON before the run")
    p.add_argument("--after", required=True, help="snapshot JSON after the run")
    p.add_argument("--since", help="only ledger rows at or after this stamp")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from . import store
    before = json.load(open(a.before, encoding="utf-8"))
    after = json.load(open(a.after, encoding="utf-8"))
    # The snapshot files store apify as a bare number under its own key.
    for snap in (before, after):
        if "apify_usd_month_to_date" in snap:
            snap["apify"] = {"usd": snap["apify_usd_month_to_date"]}
    result = reconcile(before, after, store.load(), since=a.since)
    print(json.dumps(result, indent=1) if a.json else report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
