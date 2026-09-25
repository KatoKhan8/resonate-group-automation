"""Lane R: can the packs actually ground a connection note for THIS cohort?

Rule: the connection note must be under 280 characters and may not assert a
specific the pack does not support. Lane O proved copylint rule 1 is mostly
fake - a stranger's pack passes it up to 91.8% of the time, while the ANCHOR
matches the wrong company zero times. So `anchor_grounded` is the field that
decides whether there is anything worth quoting; `anchor_grounded == 0` means
the site had nothing and the rule-1 pass is a category word.

This asks one question and reports the denominator for it: of the 681
accounts behind cohort 491-498, how many are covered by lane O's union cache
at all, and how many of those have a grounded anchor?

No provider call. Pure file read against two gitignored artifacts.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
LANEO = os.path.join(boot.PROD, ".claude", "worktrees",
                     "agent-ae370675963454a79", "work")
UNION = os.path.join(LANEO, "laneO-union-cache-2026-09-25.json")
SHIP = os.path.join(LANEO, "laneO-shippable-2026-09-25.jsonl")


def norm(d):
    # The union cache keys rows `<domain>::<profile>`, not by bare domain.
    # Splitting on `::` is the difference between 0% coverage and the real
    # figure - a join that silently matches nothing reads exactly like an
    # absent pack.
    d = str(d or "").strip().lower().split("::")[0]
    for p in ("http://", "https://", "www."):
        if d.startswith(p):
            d = d[len(p):]
    return d.split("/")[0].strip(".")


def main():
    rows = json.load(open(os.path.join(OUT, "cohort-491-498.json"),
                          encoding="utf-8"))["rows"]
    mine = {norm(r["domain"]) for r in rows if r["domain"]}
    print("distinct accounts behind cohort 491-498 :", len(mine))

    if not os.path.exists(SHIP):
        print("lane O shippable file absent at", SHIP)
        return
    ship = {}
    for line in open(SHIP, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ship[norm(d.get("domain"))] = d
    print("lane O shippable domains                :", len(ship))

    union = set()
    if os.path.exists(UNION):
        try:
            u = json.load(open(UNION, encoding="utf-8"))
            union = {norm(k) for k in (u.keys() if isinstance(u, dict)
                                       else [])}
        except (ValueError, MemoryError) as exc:
            print("union cache unreadable:", type(exc).__name__)
    print("lane O union-cache domains              :", len(union))
    print()

    in_ship = mine & set(ship)
    in_union = mine & union
    print("--- coverage, denominator = %d accounts ---" % len(mine))
    print("  covered by the union cache            : %d  (%.1f%%)"
          % (len(in_union), 100.0 * len(in_union) / len(mine)))
    print("  covered by the shippable set          : %d  (%.1f%%)"
          % (len(in_ship), 100.0 * len(in_ship) / len(mine)))
    print()

    if in_ship:
        g = Counter()
        for d in in_ship:
            try:
                val = int(ship[d].get("anchor_grounded") or 0)
            except (TypeError, ValueError):
                val = 0
            g["anchor_grounded == 0 (nothing to quote)" if val == 0
              else "anchor_grounded >= 7 (quotable)" if val >= 7
              else "anchor_grounded 1-6 (thin)"] += 1
        print("  of those %d, the anchor:" % len(in_ship))
        for k, c in g.most_common():
            print("     %-44s %d" % (k, c))
        one_word = sum(1 for d in in_ship
                       if str(ship[d].get("rests_on_one_word")) == "True")
        print("     rests_on_one_word == True                 %d" % one_word)
    print()
    print("A connection note may only be written for an account with a")
    print("grounded anchor. Every other account gets the neutral opener,")
    print("which asserts nothing about them - NOT a category word dressed")
    print("up as a specific.")

    with open(os.path.join(OUT, "pack-coverage.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"accounts": len(mine), "in_shippable": len(in_ship),
                   "in_union": len(in_union)}, fh, indent=1)


if __name__ == "__main__":
    main()
