"""Did THIS lane spend anything? A whole-file hash cannot answer that.

LANE O, 2026-09-25.

## THE FALSE ALARM THAT MADE THIS FILE

The brief says the free crawl is $0.00 and the ledger must stay untouched,
verified by hash before and after, as lane K did. Lane K's run had the
estate to itself for thirteen minutes. This one does not: lanes M, N and P
are live, and 90 seconds into the crawl the sha256 of
`work/spend-ledger.jsonl` had already moved - **10 rows, all `reoon` and
`deliverable` email verification, none of them Apify and none of them
this lane's.** A whole-file hash in a shared estate reports every other
lane's work as this lane's, and an alarm that fires on somebody else's
correct behaviour is an alarm nobody reads twice.

## WHAT IS ACTUALLY BEING ASSERTED

The free path cannot bill. `webfetch` opens a socket, `apify.check_url`
resolves a name, and neither goes anywhere near `spendledger.record` -
`researchpack/pack.py` is the only caller and `run_actor` is the only
function in it that calls, and nothing in this lane calls `run_actor`. So
the claim is narrower and checkable: **no APIFY row appeared while this
lane ran, and the rows that did appear are accounted for by provider.**

That is what `--baseline` records and `--check` verifies. Rows are compared
as a MULTISET of `(provider, call, expected_cost)` with the count, because
two identical verification calls a second apart are two real rows and a set
would hide the second.

## AND IT PRINTS THE WHOLE-FILE HASH TOO

Not as the verdict, as evidence: the file did change, this says by how much
and whose it was, and refusing to print the number would look like hiding
it.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os

#: The providers this lane could conceivably have spent on. Nothing here
#: calls them; a row from one of these while the lane ran is the finding.
OURS = ("apify",)


def read(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def fingerprint(rows):
    counts = collections.Counter(
        (str(r.get("provider")), str(r.get("call")),
         int(r.get("expected_cost") or 0)) for r in rows)
    return {"rows": len(rows),
            "by_provider": dict(collections.Counter(
                str(r.get("provider")) for r in rows)),
            "cents": sum(int(r.get("expected_cost") or 0) for r in rows),
            "last_at": max((str(r.get("at") or "") for r in rows),
                           default=""),
            "last_apify_at": max((str(r.get("at") or "") for r in rows
                                  if r.get("provider") == "apify"),
                                 default=""),
            "multiset": ["%s|%s|%d" % k + "|%d" % v
                         for k, v in sorted(counts.items())]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--state", required=True,
                    help="where the baseline is written and read")
    ap.add_argument("--check", action="store_true",
                    help="compare against the baseline instead of writing it")
    args = ap.parse_args(argv)

    rows = read(args.ledger)
    now = fingerprint(rows)
    now["sha256"] = digest(args.ledger)
    now["at"] = datetime.datetime.now(
        datetime.timezone.utc).replace(microsecond=0).isoformat()

    if not args.check:
        with open(args.state, "w", encoding="utf-8") as handle:
            json.dump(now, handle, indent=1)
        print("baseline: %d row(s), %d cent(s), sha256 %s"
              % (now["rows"], now["cents"], now["sha256"]))
        print("  by provider: %s" % now["by_provider"])
        print("  last apify row: %s" % (now["last_apify_at"] or "none ever"))
        print("written to %s" % args.state)
        return 0

    with open(args.state, encoding="utf-8") as handle:
        before = json.load(handle)

    added = collections.Counter()
    for key in set(before["by_provider"]) | set(now["by_provider"]):
        delta = now["by_provider"].get(key, 0) - before["by_provider"].get(key, 0)
        if delta:
            added[key] = delta

    print("ledger %s" % args.ledger)
    print("  sha256 before %s" % before["sha256"])
    print("  sha256 after  %s" % now["sha256"])
    print("  rows %d -> %d   cents %d -> %d"
          % (before["rows"], now["rows"], before["cents"], now["cents"]))
    print("  rows added, by provider: %s" % (dict(added) or "none"))
    print("  last apify row before: %s" % (before["last_apify_at"] or "none"))
    print("  last apify row after:  %s" % (now["last_apify_at"] or "none"))

    ours = {k: v for k, v in added.items() if k in OURS and v > 0}
    if ours:
        print("")
        print("FAILED: %s row(s) appeared on a provider this lane could have "
              "spent on. This lane calls no actor, so this is either another "
              "lane's spend or a bug worth stopping for." % ours)
        return 1
    if before["last_apify_at"] != now["last_apify_at"]:
        print("")
        print("FAILED: the last apify row moved from %s to %s"
              % (before["last_apify_at"], now["last_apify_at"]))
        return 1
    print("")
    print("PASSED: no apify row appeared. The %d row(s) that did are %s - "
          "other lanes' address verification, not this lane's crawl, which "
          "reaches no billable call at all."
          % (sum(added.values()), dict(added) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
