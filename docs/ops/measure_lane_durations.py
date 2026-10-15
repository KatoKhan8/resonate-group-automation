"""Re-measure the lane task duration distribution from the watcher logs.

Not a restatement of TASK 0090's figure: the logs have moved since, and the
standing rules say to re-measure a gate yourself at the moment you look.

Pairs are STRICT. A line only counts if it carries the watcher's own
"[timestamp] [lane] " prefix, because each log also contains the appended
stdout of every task, and task prose quotes the words START and DONE freely.
"""
import os
import re
import sys
from datetime import datetime

LOGS = r"C:\Users\Zvonimir\Desktop\resonate-ops\logs"
LINE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[([a-z-]+)\] "
    r"(START|DONE) +(\S+\.md)(?: -> (\S+))?\s*$")

pairs = []          # (lane, task, start, end, suffix)
unclosed = []       # (lane, task, start)

for fn in sorted(os.listdir(LOGS)):
    if not (fn.startswith("watcher-") and fn.endswith(".log")):
        continue
    open_start = {}
    with open(os.path.join(LOGS, fn), "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            m = LINE.match(raw.strip())
            if not m:
                continue
            ts, lane, kind, task, suffix = m.groups()
            when = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            if kind == "START":
                open_start[task] = when
            else:
                if task in open_start:
                    pairs.append((lane, task, open_start.pop(task), when, suffix))
    for task, when in open_start.items():
        unclosed.append((fn, task, when))

pairs.sort(key=lambda p: (p[3] - p[2]).total_seconds(), reverse=True)
mins = [(p[3] - p[2]).total_seconds() / 60.0 for p in pairs]

print("logs read            %s" % LOGS)
print("paired START/DONE    %d" % len(pairs))
if not pairs:
    sys.exit("no pairs")
srt = sorted(mins)
median = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
print("median               %.1f min" % median)
print("mean                 %.1f min" % (sum(mins) / len(mins)))
print("longest              %.1f min" % max(mins))
for thresh in (60, 77, 90, 120, 150):
    print("over %-4d min        %d of %d" % (thresh, sum(1 for x in mins if x > thresh), len(mins)))

print()
print("COMPLETED ONLY (suffix exit0) - the figure that bounds a real task:")
comp = [(p, (p[3] - p[2]).total_seconds() / 60.0) for p in pairs if p[4] == "exit0"]
if comp:
    cm = sorted(x for _, x in comp)
    cmed = cm[len(cm) // 2] if len(cm) % 2 else (cm[len(cm) // 2 - 1] + cm[len(cm) // 2]) / 2
    print("  n=%d  median %.1f  longest %.1f min" % (len(cm), cmed, max(cm)))
    print("  top 6:")
    for p, d in comp[:6]:
        print("    %-12s %-52s %5.1f min" % (p[0], p[1][:52], d))

print()
print("EVERY TASK THE CAP ACTUALLY BOUND (suffix TIMEOUT):")
tos = [(p, (p[3] - p[2]).total_seconds() / 60.0) for p in pairs if p[4] == "TIMEOUT"]
if tos:
    for p, d in tos:
        print("    %-12s %-52s %5.1f min  (%s)" % (p[0], p[1][:52], d, p[2]))
else:
    print("    none")

print()
print("BY OUTCOME:")
by = {}
for p in pairs:
    by[p[4]] = by.get(p[4], 0) + 1
for k in sorted(by, key=lambda k: -by[k]):
    print("    %-10s %d" % (k, by[k]))

print()
print("TOP 8 BY DURATION, ALL OUTCOMES:")
for p in pairs[:8]:
    print("    %-12s %-46s %5.1f min  -> %s" % (
        p[0], p[1][:46], (p[3] - p[2]).total_seconds() / 60.0, p[4]))

print()
print("UNCLOSED (START with no DONE - running now, or a lost loop): %d" % len(unclosed))
for fn, task, when in unclosed:
    print("    %-26s %-46s START %s" % (fn, task[:46], when))
