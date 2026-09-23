"""Re-judge the 2026-09-07 Productive snapshot under the headcount amendment.

ZERO PROVIDER CALLS AND ZERO CREDITS. `work/stage/s3-icp.jsonl` already
carries `employees`, `country` and `industry` for all 24,404 domains, which
is every field `judge` reads. Re-running S3 against ContactOut to change a
local judgement would spend the estate's credits to learn nothing new.

IT WRITES A SEPARATE JOURNAL AND NEVER TOUCHES THE BASELINE. Two reasons.
S3's journal is its checkpoint - appending amended verdicts to it would make
the next real S3 run skip every domain as already decided. And the
authorisation asks for the diff "on the SET of domains, not on the counts",
which needs both sets to still exist afterwards.

    py -3 scripts/stage_s3_rejudge_amended.py
"""

import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util                                          # noqa: E402
from src import clients                                        # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "stage_s3_icp", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "stage_s3_icp.py"))
s3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s3)

BASELINE = s3.JOURNAL
AMENDED = os.path.join(s3.STAGE, "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")


def rows(path):
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    icp = (clients.load("productive").get("market") or {})
    base = rows(BASELINE)
    print(f"baseline journal: {len(base)} rows, "
          f"{len({r['domain'] for r in base})} distinct domains")

    before = collections.Counter(r["verdict"] for r in base)
    after = collections.Counter()
    moves = collections.Counter()
    amended_rows = []

    for r in base:
        # The journal row IS the company object for the fields judge reads.
        info = {"domain": r.get("domain"), "employees": r.get("employees"),
                "country": r.get("country"), "industry": r.get("industry")}
        # A domain the provider could not resolve has no company to judge, and
        # the amendment does not conjure one. `judge` returns flagged for it on
        # its own, but only if `domain` is falsy - here it never is, so the
        # journal's own reason is authoritative and is carried forward.
        if r.get("reason") == "provider returned no company for this domain":
            verdict, reason = "flagged", r["reason"]
        else:
            verdict, reason = s3.judge(info, icp, headcount=False)
        after[verdict] += 1
        if verdict != r["verdict"]:
            moves[f"{r['verdict']} -> {verdict}"] += 1
        amended_rows.append(dict(r, verdict=verdict, reason=reason,
                                 amendment=s3.HEADCOUNT_AMENDMENT))

    with io.open(AMENDED, "w", encoding="utf-8") as fh:
        for r in amended_rows:
            fh.write(json.dumps(r) + "\n")

    print(f"\nwrote {AMENDED}")
    print(f"\n{'verdict':<10}{'baseline':>10}{'amended':>10}{'delta':>10}")
    for v in ("in", "out", "flagged"):
        print(f"{v:<10}{before[v]:>10,}{after[v]:>10,}{after[v]-before[v]:>+10,}")
    print(f"{'total':<10}{sum(before.values()):>10,}{sum(after.values()):>10,}")

    print("\nmovements:")
    for k, n in moves.most_common():
        print(f"  {k:<22}{n:>8,}")

    base_in = {r["domain"] for r in base if r["verdict"] == "in"}
    amd_in = {r["domain"] for r in amended_rows if r["verdict"] == "in"}
    print(f"\nSET diff on IN (the baseline rule - counts can agree and members differ):")
    print(f"  baseline IN        {len(base_in):>8,}")
    print(f"  amended IN         {len(amd_in):>8,}")
    print(f"  kept               {len(base_in & amd_in):>8,}")
    print(f"  recovered by amendment {len(amd_in - base_in):>8,}")
    print(f"  LOST (must be zero){len(base_in - amd_in):>8,}")
    if base_in - amd_in:
        print("  !! removing a criterion removed an IN - that is a bug:")
        for d in sorted(base_in - amd_in)[:10]:
            print("    ", d)
    pct = 100.0 * after["in"] / max(sum(after.values()), 1)
    print(f"\nIN rate under the amendment: {pct:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
