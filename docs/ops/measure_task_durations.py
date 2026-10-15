"""TASK 0090 step 2 - how long do lane tasks actually take?

The 90 -> 150 raise needs a measured floor, not an argument. The only authority
for how long a task ran is the lane's own watcher log, which writes

    [YYYY-MM-DD HH:MM:SS] [lane] START <brief>
    [YYYY-MM-DD HH:MM:SS] [lane] DONE  <brief> -> <suffix>

around every task. A DONE with no START (the log predates the task, or the
watcher died) is reported as UNPAIRED and never guessed at. A START with no
DONE is either IN FLIGHT or a task whose watcher died mid-run; the two are
distinguished by whether the lane has a live watcher now, which this script
does not read - so both are reported as OPEN and excluded from the statistics.

    py -3 measure_task_durations.py
"""

import io
import os
import re
import sys

LOGS = r"C:\Users\Zvonimir\Desktop\resonate-ops\logs"

LINE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(?P<lane>[^\]]+)\] "
    r"(?P<verb>START|DONE) \s*(?P<name>\S+)"
)


def to_seconds(ts):
    # no timezone anywhere in these logs; all one machine, one clock
    d, t = ts.split(" ")
    y, mo, da = (int(x) for x in d.split("-"))
    h, mi, s = (int(x) for x in t.split(":"))
    return (((da * 24 + h) * 60 + mi) * 60) + s, (y, mo)


def main():
    if not os.path.isdir(LOGS):
        print("FATAL: no log directory at %s" % LOGS)
        return 2

    rows = []
    opens = []
    unpaired = []
    for fn in sorted(os.listdir(LOGS)):
        if not fn.startswith("watcher-") or not fn.endswith(".log"):
            continue
        path = os.path.join(LOGS, fn)
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        pending = {}
        for line in text.splitlines():
            m = LINE.match(line)
            if not m:
                continue
            lane = m.group("lane")
            name = m.group("name")
            secs, _ym = to_seconds(m.group("ts"))
            if m.group("verb") == "START":
                if name in pending:
                    opens.append((lane, name, "re-STARTed without a DONE"))
                pending[name] = (secs, m.group("ts"))
            else:
                if name not in pending:
                    unpaired.append((lane, name, m.group("ts")))
                    continue
                start_secs, start_ts = pending.pop(name)
                rows.append((lane, name, start_ts, m.group("ts"),
                             secs - start_secs))
        for name, (_s, ts) in pending.items():
            opens.append((lane if rows or opens else fn, name, "STARTed %s, no DONE" % ts))

    if not rows:
        print("no paired START/DONE in any log - nothing measurable")
        return 1

    rows.sort(key=lambda r: -r[4])
    print("PAIRED TASKS: %d, across %d lane log(s)" % (
        len(rows), len(set(r[0] for r in rows))))
    print("")
    print("%-12s %7s  %-19s  %s" % ("lane", "minutes", "started", "brief"))
    for lane, name, start_ts, _end_ts, secs in rows[:18]:
        print("%-12s %7.1f  %-19s  %s" % (lane, secs / 60.0, start_ts, name[:52]))
    if len(rows) > 18:
        print("... %d shorter tasks omitted" % (len(rows) - 18))
    print("")

    mins = sorted(r[4] / 60.0 for r in rows)
    longest = rows[0]
    print("longest : %.1f min  %s / %s" % (longest[4] / 60.0, longest[0], longest[1]))
    print("median  : %.1f min" % mins[len(mins) // 2])
    print("mean    : %.1f min" % (sum(mins) / len(mins)))
    for cut in (60, 77, 90, 120, 150):
        over = [m for m in mins if m > cut]
        print("over %3d min : %d of %d (%.0f%%)" % (
            cut, len(over), len(mins), 100.0 * len(over) / len(mins)))
    print("")

    if opens:
        print("OPEN (started, no DONE in the log) - excluded from the figures:")
        for lane, name, why in opens:
            print("  %-12s %-52s %s" % (lane, name[:52], why))
        print("")
    if unpaired:
        print("UNPAIRED DONE (no START in this log) - excluded, never guessed:")
        for lane, name, ts in unpaired:
            print("  %-12s %-52s DONE at %s" % (lane, name[:52], ts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
