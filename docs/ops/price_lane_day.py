#!/usr/bin/env python3
r"""TASK 0130 - price the measured lane-day. Pure arithmetic over sessions.json.

No network call, no model call. Every price carries its source below.
"""
import json, io, re, collections, sys

SESSIONS = sys.argv[1] if len(sys.argv) > 1 else "sessions.json"

# ---------------------------------------------------------------- prices
# Anthropic first-party API rates. Source: the bundled `claude-api` skill's
# Current Models table (cached 2026-06-24) for base input/output, and
# shared/prompt-caching.md for the cache multipliers:
#   cache read  = 0.1x base input
#   cache write = 1.25x base input (5m TTL), 2x base input (1h TTL)
ANTHROPIC = {
    "claude-opus-5":   {"in": 5.00, "out": 25.00},
    "claude-sonnet-5": {"in": 2.00, "out": 10.00},
}
for v in ANTHROPIC.values():
    v["read"] = v["in"] * 0.1
    v["w5m"] = v["in"] * 1.25
    v["w1h"] = v["in"] * 2.0

# glm-5.3 at z.ai. Source: this repository's own config/model-prices.yaml,
# `source: https://z.ai/pricing`, `as_of: 2026-09-26`. NINETEEN DAYS OLD and
# NOT re-verified here, because re-verifying needs a network call this task is
# forbidden to make.
GLM_IN, GLM_OUT = 0.40, 1.60
# z.ai's cache-read price is NOT in that file and is UNKNOWN. Bounded, never
# guessed: free, the Anthropic-style 0.1x discount, or no discount at all.
GLM_READ_BOUNDS = [("free (0.0x)", 0.0), ("0.1x input", GLM_IN * 0.1),
                   ("1.0x input", GLM_IN)]

LANE_MODEL = {"glm": "glm-5.3", "glm-b": "glm-5.3", "glm-c": "glm-5.3",
              "pilotcaps": "claude-opus-5", "suppression": "claude-opus-5",
              "qwen": "claude-opus-5", "webapp": "claude-opus-5"}


def load():
    g = json.load(io.open(SESSIONS, encoding="utf-8"))
    out = []
    for lane, ss in g.items():
        for s in ss:
            ep = s["entrypoints"] or {}
            if not ep or max(ep, key=ep.get) != "sdk-cli":
                continue          # an operator's own `cli` session, not a task
            t = collections.Counter()
            for model, c in s["by_model"].items():
                for k, v in c.items():
                    t[k] += v
            m = re.search(r"TASK\s+(\d{3,4})", s["prompt"] or "")
            out.append(dict(lane=lane, task=m.group(1) if m else None,
                            first=s["first"], calls=s["calls"], tok=t))
    return out


def anth_cost(tok, model):
    p = ANTHROPIC[model]
    return (tok["input_tokens"] * p["in"]
            + tok["output_tokens"] * p["out"]
            + tok["cache_1h"] * p["w1h"]
            + tok["cache_5m"] * p["w5m"]
            + tok["cache_read_input_tokens"] * p["read"]) / 1e6


def glm_cost(tok, read_rate):
    return (tok["input_tokens"] * GLM_IN
            + tok["output_tokens"] * GLM_OUT
            + tok["cache_read_input_tokens"] * read_rate) / 1e6


def main():
    rows = load()
    print("=" * 78)
    print("MEASURED LANE-DAY  2026-10-14T23:30Z .. 2026-10-15T21:19Z")
    print("source: Claude Code session transcripts, deduped by requestId")
    print("=" * 78)

    byl = collections.defaultdict(lambda: collections.Counter())
    nses = collections.Counter()
    for r in rows:
        nses[r["lane"]] += 1
        for k, v in r["tok"].items():
            byl[r["lane"]][k] += v
        byl[r["lane"]]["calls"] += r["calls"]

    print("")
    print("%-12s %-14s %5s %6s %11s %11s %11s %11s" %
          ("lane", "model", "tasks", "calls", "in", "out", "cache_wr",
           "cache_rd"))
    for lane in LANE_MODEL:
        t = byl[lane]
        print("%-12s %-14s %5d %6d %11d %11d %11d %11d" %
              (lane, LANE_MODEL[lane], nses[lane], t["calls"],
               t["input_tokens"], t["output_tokens"],
               t["cache_creation_input_tokens"], t["cache_read_input_tokens"]))

    opus = [l for l in LANE_MODEL if LANE_MODEL[l] == "claude-opus-5"]
    glm = [l for l in LANE_MODEL if LANE_MODEL[l] == "glm-5.3"]
    O = collections.Counter()
    G = collections.Counter()
    for l in opus:
        O.update(byl[l])
    for l in glm:
        G.update(byl[l])

    # ---------------------------------------------------- A. today's bill
    print("")
    print("-" * 78)
    print("A. TODAY'S BILL - the estate as it actually ran (3 lanes glm, 4 Opus)")
    print("-" * 78)
    oc = anth_cost(O, "claude-opus-5")
    no, ng = sum(nses[l] for l in opus), sum(nses[l] for l in glm)
    print("  4 Opus-5 lanes   %2d tasks   $%8.2f   ($%6.2f / task)"
          % (no, oc, oc / no))
    print("    in $%.2f  out $%.2f  cache-write(1h) $%.2f  cache-read $%.2f"
          % (O["input_tokens"] * 5 / 1e6, O["output_tokens"] * 25 / 1e6,
             O["cache_1h"] * 10 / 1e6, O["cache_read_input_tokens"] * .5 / 1e6))
    print("  3 glm-5.3 lanes  %2d tasks   cache-read price UNKNOWN -> bounded:"
          % ng)
    glo = ghi = None
    for name, rate in GLM_READ_BOUNDS:
        c = glm_cost(G, rate)
        glo = c if glo is None else min(glo, c)
        ghi = c if ghi is None else max(ghi, c)
        print("      reads at %-12s  $%8.2f   ($%6.2f / task)"
              % (name, c, c / ng))
    print("  ---")
    print("  TOTAL 7 lanes, %d tasks:  $%.2f .. $%.2f   ($%.2f .. $%.2f / task)"
          % (len(rows), oc + glo, oc + ghi,
             (oc + glo) / len(rows), (oc + ghi) / len(rows)))

    # ------------------------------- B. all seven lanes at Anthropic prices
    print("")
    print("-" * 78)
    print("B. THE SAME VOLUME, ALL SEVEN LANES ON ANTHROPIC")
    print("-" * 78)
    # z.ai reports ZERO cache-creation tokens against 385M cache reads, which
    # is impossible - a read implies a write. The most likely reading is that
    # z.ai folds cache writes into `input_tokens`. That split is UNKNOWN, so
    # the glm volume is priced at both ends and calibrated in between.
    share = O["cache_1h"] / float(O["cache_1h"] + O["input_tokens"])
    mids = {}
    for label, model in (("Opus 5", "claude-opus-5"),
                         ("Sonnet 5", "claude-sonnet-5")):
        p = ANTHROPIC[model]
        base = anth_cost(O, model)
        gfix = (G["output_tokens"] * p["out"]
                + G["cache_read_input_tokens"] * p["read"]) / 1e6
        lo = base + gfix + G["input_tokens"] * p["in"] / 1e6
        hi = base + gfix + G["input_tokens"] * p["w1h"] / 1e6
        mid = base + gfix + G["input_tokens"] * (
            share * p["w1h"] + (1 - share) * p["in"]) / 1e6
        mids[label] = mid
        print("  all 7 lanes on %-9s  $%8.2f .. $%8.2f" % (label, lo, hi))
        print("      calibrated (%.2f%% of glm non-read input priced as a 1h"
              " cache write, the\n      share measured in the four Opus lanes)"
              ":  $%.2f  = $%.2f / task"
              % (share * 100, mid, mid / len(rows)))

    # ------------------------------------------------- C. scale to a month
    print("")
    print("-" * 78)
    print("C. PER MONTH AT TODAY'S RATE (%d tasks/day measured)" % len(rows))
    print("-" * 78)
    for days, dn in ((22, "22 working days"), (30, "30 calendar days")):
        print("  %-24s x %-17s $%8.0f .. $%8.0f"
              % ("today's mixed estate", dn, (oc + glo) * days,
                 (oc + ghi) * days))
    for label in ("Opus 5", "Sonnet 5"):
        for days, dn in ((22, "22 working days"), (30, "30 calendar days")):
            print("  %-24s x %-17s $%8.0f"
                  % ("all 7 on " + label, dn, mids[label] * days))

    # ------------------------------------------------ D. the spread per task
    print("")
    print("-" * 78)
    print("D. PER-TASK SPREAD (one session = one dispatched task, 1:1 verified)")
    print("-" * 78)
    costs = []
    for r in rows:
        m = LANE_MODEL[r["lane"]]
        c = (anth_cost(r["tok"], m) if m in ANTHROPIC
             else glm_cost(r["tok"], GLM_READ_BOUNDS[1][1]))
        costs.append((c, r["lane"], r["task"]))
    costs.sort()
    n = len(costs)
    print("  cheapest : $%6.2f  %s/%s" % costs[0])
    print("  median   : $%6.2f  %s/%s" % costs[n // 2])
    print("  dearest  : $%6.2f  %s/%s" % costs[-1])
    for m in ("claude-opus-5", "glm-5.3"):
        sub = sorted(c for c, l, t in costs if LANE_MODEL[l] == m)
        print("  %-14s n=%2d  median $%6.2f  max $%7.2f  mean $%6.2f  "
              "(glm reads at 0.1x)"
              % (m, len(sub), sub[len(sub) // 2], sub[-1],
                 sum(sub) / len(sub)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
