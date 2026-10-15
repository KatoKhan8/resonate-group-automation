#!/usr/bin/env python3
"""TASK 0150 - how much lane time is lost waiting for the machine-wide suite lock?

READ-ONLY. Takes no lock, writes nothing outside its own stdout. Walks three
authorities and never mixes them:

  A  resonate-ops/logs/watcher-*.log   START/DONE per lane -> WORKING time
  B  every surviving run_suite artifact -> each suite run's [start,end] window
  C  lock payloads quoted in lane files / captured stdout -> recorded WAITS

A wait is only counted when a `queued_at`/`started_at` PAIR exists for the same
run. There is no wait log on this machine, so every total here is a FLOOR and is
labelled as one.
"""
import os, re, sys, json, datetime as dt

DESKTOP = r"C:\Users\Zvonimir\Desktop"
OPS = os.path.join(DESKTOP, "resonate-ops")
LOGS = os.path.join(OPS, "logs")
TODAY = "2026-10-15"

# ---------------------------------------------------------------- authority A
EV = re.compile(r"^\[(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d)\] \[([a-z-]+)\] "
                r"(START|DONE|NOWORK|TIMEOUT)\s*(.*)$")

def watcher_events():
    out = []
    for fn in sorted(os.listdir(LOGS)):
        if not (fn.startswith("watcher-") and fn.endswith(".log")):
            continue
        lane = fn[len("watcher-"):-len(".log")]
        with open(os.path.join(LOGS, fn), encoding="utf-8-sig",
                  errors="replace") as fh:
            for line in fh:
                m = EV.match(line.rstrip("\n"))
                if m:
                    out.append(dict(lane=lane, date=m.group(1),
                                    t=m.group(2), kind=m.group(4),
                                    rest=m.group(5).strip()))
    return out


def pair_sessions(events):
    """START..DONE per lane, in order. An unpaired START is reported, never guessed."""
    open_, done, dangling = {}, [], []
    for e in events:
        if e["kind"] == "START":
            if e["lane"] in open_:
                dangling.append(open_[e["lane"]])
            open_[e["lane"]] = e
        elif e["kind"] in ("DONE", "TIMEOUT"):
            s = open_.pop(e["lane"], None)
            if s is None:
                continue
            done.append((s, e))
    return done, list(open_.values()) + dangling


def secs(d, t):
    return dt.datetime.strptime(d + " " + t, "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- authority B
def suite_artifacts():
    """Every surviving run_suite verdict, with its [start,end] window.

    `suite_verdict.txt` carries wall_seconds; its mtime is when the run ENDED.
    start = end - wall_seconds. Only the LAST run per tree survives, because
    run_suite.py overwrites both files - so this enumeration is a FLOOR on the
    number of runs, not a census.
    """
    cands = []
    roots = [DESKTOP, os.path.join(DESKTOP, "resonate-trees")]
    for root in roots:
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for n in names:
            p = os.path.join(root, n, "scripts", "suite_verdict.txt")
            if os.path.isfile(p):
                cands.append(p)
    # verdict copies the lanes filed under resonate-ops
    for dirpath, _dirs, files in os.walk(OPS):
        for f in files:
            if "verdict" in f.lower() and f.endswith(".txt"):
                cands.append(os.path.join(dirpath, f))
    rows = []
    for p in cands:
        try:
            body = open(p, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            rows.append(dict(path=p, error=str(exc)))
            continue
        g = dict(re.findall(r"^(\w+)=(.*)$", body, re.M))
        end = dt.datetime.fromtimestamp(os.path.getmtime(p))
        try:
            wall = float(g.get("wall_seconds", "nan"))
        except ValueError:
            wall = float("nan")
        rows.append(dict(path=p, end=end, wall=wall,
                         start=(end - dt.timedelta(seconds=wall))
                         if wall == wall else None,
                         status=g.get("status"),
                         timed_out=g.get("timed_out"),
                         reached=g.get("results_reached")))
    return rows


def main():
    print("=" * 78)
    print("A. WATCHER SESSIONS - the WORKING time the waiting is measured against")
    print("=" * 78)
    ev = watcher_events()
    pairs, unpaired = pair_sessions(ev)
    today = [(s, e) for s, e in pairs if s["date"] == TODAY]
    per_lane = {}
    for s, e in today:
        d = (secs(e["date"], e["t"]) - secs(s["date"], s["t"])).total_seconds()
        per_lane.setdefault(s["lane"], []).append((s["rest"], d, e["rest"]))
    total = 0.0
    print(f"{'lane':<13}{'tasks':>6}{'working_min':>13}{'median_min':>12}")
    for lane in sorted(per_lane):
        ds = sorted(x[1] for x in per_lane[lane])
        tot = sum(ds) / 60.0
        total += tot
        med = ds[len(ds) // 2] / 60.0
        print(f"{lane:<13}{len(ds):>6}{tot:>13.1f}{med:>12.1f}")
    print(f"{'TOTAL':<13}{sum(len(v) for v in per_lane.values()):>6}"
          f"{total:>13.1f}")
    print(f"\nunpaired STARTs (still running or lost): {len(unpaired)}")
    for u in unpaired:
        print(f"  {u['lane']:<12} {u['date']} {u['t']}  {u['rest']}")

    print()
    print("=" * 78)
    print("B. SURVIVING run_suite ARTIFACTS - one window per run that survived")
    print("=" * 78)
    rows = [r for r in suite_artifacts() if not r.get("error")]
    rows.sort(key=lambda r: r["end"])
    for r in rows:
        if r["end"].strftime("%Y-%m-%d") != TODAY:
            continue
        s = r["start"].strftime("%H:%M:%S") if r["start"] else "   ?    "
        print(f"  {s} -> {r['end']:%H:%M:%S}  {r['wall']:>8.1f}s  "
              f"{str(r['status']):<11} reached={str(r['reached']):<6} "
              f"{os.path.relpath(r['path'], DESKTOP)}")
    print(f"\n  rows today: {sum(1 for r in rows if r['end'].strftime('%Y-%m-%d')==TODAY)}"
          f"   rows all dates: {len(rows)}")
    print("\n  NOTE: run_suite.py OVERWRITES scripts/suite_run.log and")
    print("  scripts/suite_verdict.txt, so at most ONE run per worktree survives.")
    print("  This is a FLOOR on the number of runs, never a census.")


if __name__ == "__main__":
    main()
