#!/usr/bin/env python3
"""TASK 0150 - the machine-wide suite lock's occupancy on 2026-10-15.

READ-ONLY. Computes arithmetic over observations collected by hand from named
authorities. Nothing here reads, takes, writes or releases a lock.

Every interval carries the authority it came from. An interval whose holder
cannot be pinned is marked UNKNOWN and is never folded into a class total.

CLASSES
  LIVE_READ    a run that completed AND whose verdict was read by its own session
  LIVE_ORPHAN  a run holding the lock while the session that launched it is gone
               - the result is produced and read by nobody
  LIVE_VOID    a run that completed but whose result was declared unusable
  DEAD         the named holder was not in the process table: pure deadweight
"""
import datetime as dt


def T(hhmmss, day=15):
    h, m, s = (int(x) for x in hhmmss.split(":"))
    return dt.datetime(2026, 10, day, h, m, s)


NOW = dt.datetime(2026, 10, 16, 0, 0, 22)   # the last self-checked read

# (start, end, holder, lane, class, authority)   end=None -> still held at NOW
OCC = [
    (T("01:57:16"), T("02:45:45"), "74780", "pilotcaps", "LIVE_READ",
     "lock quote in logs/ab-0030/branch-run-launcher.out; X1 verdict wall=2908.8s"),
    (T("02:45:46"), T("03:26:28"), "?(X2)", "pilotcaps", "LIVE_READ",
     "pilotcaps-ci-2026-10-15/X2-offline-suite_verdict.txt wall=2441.6s complete"),
    (T("03:17:47"), T("03:34:15"), "76868", "glm-b", "DEAD",
     "logs/TASK-0060/baseline_console.txt waiting+takeover lines; wt-glm-b "
     "verdict 0.0s INCOMPLETE mtime 03:17:46"),
    (T("03:34:15"), T("03:34:16"), "31936", "glm-c", "DEAD",
     "branch-run-launcher.out takeover quote; baseline_console.txt mtime 03:34:16"),
    (T("03:34:16"), T("04:06:55"), "61372", "suppression", "LIVE_READ",
     "LANE-glm.md:960-999 forensics; verdict complete, 228 names, at 04:22"),
    (T("04:06:55"), T("10:48:56"), "79120", "glm-c", "DEAD",
     "lock payload read by glm/0050 (LANE-glm.md:931); dead at 04:06:55.07 by "
     "its own 0xC0000142; takeover quote in wt-glm-c/work/suite_0100_candidate.out"),
    (T("10:48:56"), T("10:52:46"), "83452", "glm-c", "LIVE_VOID",
     "wt-glm-c verdict 10:48:57->11:28:01 complete BUT overlapped glm-review's "
     "11:22:34 run; declared unusable at LANE-pilotcaps.md:3007, LANE-glm-c.md:435"),
    (T("10:52:46"), T("11:22:34"), "74556", "glm-c(wt-cand)", "DEAD",
     "wt-cand-21dae6a70 verdict 0.0s INCOMPLETE mtime 10:52:46; takeover quote "
     "in glm-review-2026-10-14/TASK-0055-halt-fix/suite-reference-1ea8105bf.log"),
    (T("11:22:34"), T("12:00:35"), "84496", "glm", "LIVE_READ",
     "suite-reference-1ea8105bf.log mtime 12:00:35, wall=2279.9s"),
    (T("12:00:35"), T("14:24:16"), "84496", "glm", "DEAD",
     "pilotcaps read ~12:20 (LANE-pilotcaps.md:2960): pid 84496 started 11:22:34 "
     "-> DEAD, self-checked Get-CimInstance"),
    (T("14:24:16"), T("15:11:06"), "83600", "glm-c", "LIVE_ORPHAN",
     "LANE-pilotcaps.md:2960 ALIVE at 14:31; NO verdict was ever written in "
     "wt-cand (mtime still 10:52:46) and LANE-glm-c.md:437's promised "
     "continuation was never appended"),
    (T("15:11:06"), T("15:57:27"), "57972", "glm", "DEAD",
     "LANE-pilotcaps.md:3921 - taken 15:11:06, ALREADY GONE at the 15:13 read"),
    (T("15:57:27"), T("16:36:42"), "?(fix leg)", "glm", "LIVE_READ",
     "wt-glm-review verdict 15:57:27->16:36:42, wall=2355.3s, complete"),
    (T("16:36:43"), T("17:14:21"), "68836", "pilotcaps", "LIVE_READ",
     "lock payload LANE-glm.md:1709; LANE-pilotcaps.md:4829-4836 narrative"),
    (T("17:15:08"), T("17:52:21"), "78348", "pilotcaps", "LIVE_READ",
     "LANE-pilotcaps.md:4834-4836 narrative; verdict-tip wall=2233.0s"),
    (T("21:39:18"), T("22:00:18"), "77584", "glm-b", "DEAD",
     "lock payload LANE-suppression.md:3369 + LANE-webapp.md:470; glm-b "
     "scripts/suite_run.log stops growing 21:51:08 = its session's DONE->NOWORK "
     "at 21:51:09"),
    (T("22:00:18"), T("22:57:53"), "83540", "suppression", "LIVE_READ",
     "wt-suppression verdict 22:00:19->22:57:53, wall=3454.5s, complete"),
    (T("22:57:57"), T("23:55:33"), "83472", "pilotcaps", "LIVE_ORPHAN",
     "the LIVE lock file, read twice during this run; ALIVE at 23:49:11 and GONE "
     "at 00:00:22, both Get-CimInstance with a self-check; the lock released "
     "itself cleanly (file ABSENT, 0 tickets). It COMPLETED - 14928 results, 294 "
     "names, failures_are_partial=False - and the session that launched it, "
     "pilotcaps/0170, was DONE at 22:58:54, so LANE-pilotcaps.md:6113's promised "
     "7a never came and nothing read the verdict"),
]

CLONE_NOTE = (
    "qwen's lane runs in a SECOND CLONE (C:\\Users\\Zvonimir\\qwc), so its suite "
    "takes qwc\\work\\suite.lock and never appears in this timeline at all - "
    "filed by qwen/0060, LANE-qwen.md:2024-2041. Its 18:18:16-18:55:39 run "
    "(qwen-d4-2026-10-15/suite_verdict-74fad6c2f.txt, wall=2243.1s) is therefore "
    "NOT in the rows above and did not serialise against them."
)

# Waits: only where a queued_at/started_at PAIR exists for the SAME run.
WAITS = [
    ("74780", "pilotcaps", T("01:57:16"), T("01:57:16"),
     "branch-run-launcher.out: 'holding since 01:57:16 (queued at 01:57:16)'"),
    ("61372", "suppression", T("02:24:06"), T("03:34:16"),
     "LANE-glm.md:966 + the waiting line in 79120's captured stdout"),
    ("76868", "glm-b", T("03:08:04"), T("03:17:47"),
     "logs/TASK-0060/baseline_console.txt waiting line"),
    ("79120", "glm-c", T("04:04:54"), T("04:06:55"),
     "lock payload read by glm/0050, LANE-glm.md:931"),
    ("83452", "glm-c", T("10:48:55"), T("10:48:56"),
     "wt-cand-21dae6a70/work/suite_0100_reference.out waiting line"),
    ("83600", "glm-c", T("14:24:15"), T("14:24:16"),
     "lock payload LANE-pilotcaps.md:3203"),
    ("57972", "glm", T("15:11:04"), T("15:11:06"),
     "lock payload LANE-pilotcaps.md:3921"),
    ("68836", "pilotcaps", T("16:15:01"), T("16:36:43"),
     "lock payload LANE-glm.md:1709-1710"),
    ("77584", "glm-b", T("21:39:17"), T("21:39:18"),
     "lock payload LANE-suppression.md:3369"),
    ("83472", "pilotcaps", T("22:56:18"), T("22:57:57"),
     "the LIVE lock file, read this run"),
]

WAITS_UNKNOWN = [
    ("31936", "glm-c", "<=26m12s",
     "took over 03:34:15; cannot have queued before 03:08:04"),
    ("74556", "glm-c(wt-cand)", "<=3m51s",
     "'queued at position 2 of 2' behind 83452 (queued 10:48:55); granted 10:52:46"),
    ("84496", "glm", "UNKNOWN", "only started_at 11:22:34 was ever quoted"),
    ("83540", "suppression", "UNKNOWN", "only started 22:00:18 was ever quoted"),
    ("?(X2)", "pilotcaps", "UNKNOWN",
     "no payload quoted; granted <=1s after X1 released"),
]

# Sessions that wanted a full reference, could not have one, and said so.
FORGONE = [
    ("webapp/0030", T("21:07:10"), T("21:48:00"),
     "glm-b's 77584 held; declined to start a leg that could not finish inside "
     "the 90m cap", "LANE-webapp.md:640"),
    ("glm-b/0110", T("21:39:18"), T("21:51:09"),
     "launched its own leg, the session ended under it, NOWORK recorded",
     "watcher-glm-b.log:249-250"),
    ("webapp/0030b", T("22:09:20"), T("22:38:00"),
     "suppression's 83540 held and was alive; declined", "LANE-webapp.md:1076"),
    ("pilotcaps/0160", T("21:40:13"), T("22:14:56"),
     "'owes a full suite reference and does not have one ... UNDONE AND NOT "
     "RE-QUEUED'", "watcher-pilotcaps.log:549"),
    ("webapp/0040", T("23:04:00"), T("23:52:00"),
     "integ-nine's 83472 held and was alive; declined, third consecutive",
     "LANE-webapp.md:1407"),
]

WORKING_MIN = 2163.4  # 92 paired watcher sessions today, measure_suite_lock.py


def mins(a, b):
    return (b - a).total_seconds() / 60.0


def main():
    print("=" * 79)
    print("1. THE LOCK'S OCCUPANCY, 2026-10-15, measured to 23:49:11")
    print("=" * 79)
    cls = {}
    print("%-9s%-9s%8s  %-13s%-16s%s" % ("from", "to", "min", "holder", "lane",
                                         "class"))
    prev_end = None
    free = 0.0
    for start, end, holder, lane, k, _auth in OCC:
        if prev_end is not None and start > prev_end:
            g = mins(prev_end, start)
            free += g
            print("%-18s%8.1f  %s" % ("", g, "--- FREE ---"))
        e = end or NOW
        d = mins(start, e)
        cls[k] = cls.get(k, 0.0) + d
        tag = "" if end else "   <== STILL HELD"
        print("%s %s %8.1f  %-13s%-16s%s%s"
              % (start.strftime("%H:%M:%S"), e.strftime("%H:%M:%S"), d,
                 holder, lane, k, tag))
        prev_end = max(prev_end, e) if prev_end else e

    span = mins(OCC[0][0], NOW)
    named = sum(cls.values())
    # The rows OVERLAP where a false DEAD let a second run take a lock a live
    # run was holding. Summing them double-counts, so HELD is the UNION and the
    # overlap is reported separately - it is itself the finding that the lock
    # failed its one job.
    iv = sorted(((s, e or NOW) for s, e, *_ in OCC))
    union = 0.0
    cur_s, cur_e = iv[0]
    overlap = 0.0
    for s, e in iv[1:]:
        if s < cur_e:
            overlap += mins(s, min(e, cur_e))
            cur_e = max(cur_e, e)
        else:
            union += mins(cur_s, cur_e)
            cur_s, cur_e = s, e
    union += mins(cur_s, cur_e)
    held = union
    # Trailing FREE: the lock released itself at 23:55:33 and was ABSENT at the
    # last read, so the span does not end with the lock held.
    trailing = mins(cur_e, NOW) if cur_e < NOW else 0.0
    print("-" * 79)
    for k in ("LIVE_READ", "LIVE_VOID", "LIVE_ORPHAN", "DEAD"):
        v = cls.get(k, 0.0)
        print("  %-12s%9.1f min  %5.2f h   %5.1f%% of held"
              % (k, v, v / 60, 100 * v / held))
    print("  %-12s%9.1f min  %5.2f h   %5.1f%% of the 01:57:16-00:00:22 span"
          % ("HELD", held, held / 60, 100 * held / span))
    free += trailing
    print("  %-12s%9.1f min  %5.2f h  (incl. %.1f after the lock freed itself "
          "at 23:55:33)" % ("FREE", free, free / 60, trailing))
    print("  %-12s%9.1f min   the class sums; HELD is their UNION"
          % ("named", named))
    print("  %-12s%9.1f min   TWO RUNS HELD/RAN AT ONCE for this long - the lock"
          % ("OVERLAP", overlap))
    print("  %-12s%9s    failing the one thing it exists to do" % ("", ""))
    print("  check: union + free = %.1f, span = %.1f" % (held + free, span))
    print()
    print("  " + CLONE_NOTE)
    print()
    print("  MACHINE TIME vs LOCK TIME: 83452's run actually ran 10:48:57-11:28:01")
    print("  (39.1 min, verdict complete, 385 names) but the lock file named it")
    print("  for only 3.8 of those minutes, because 74556 declared it dead at")
    print("  10:52:46. So 39.1 min of MACHINE capacity produced a reference that")
    print("  both glm-c and pilotcaps then declared void for contention. Lock")
    print("  minutes understate that loss by an order of magnitude.")

    print()
    print("=" * 79)
    print("2. THE WAIT, only where a queued_at/started_at PAIR exists")
    print("=" * 79)
    per = {}
    tot = 0.0
    print("%-9s%-14s%-10s%-10s%9s" % ("holder", "lane", "queued", "granted",
                                      "wait_min"))
    for holder, lane, q, s, _a in sorted(WAITS, key=lambda r: r[2]):
        w = mins(q, s)
        tot += w
        per[lane] = per.get(lane, 0.0) + w
        print("%-9s%-14s%-10s%-10s%9.2f"
              % (holder, lane, q.strftime("%H:%M:%S"), s.strftime("%H:%M:%S"), w))
    print("-" * 79)
    for lane in sorted(per):
        print("  %-14s%8.2f min" % (lane, per[lane]))
    print("  %-14s%8.2f min = %.2f h" % ("TOTAL (FLOOR)", tot, tot / 60))
    print("\n  recorded but unbounded, NOT summed:")
    for holder, lane, bound, why in WAITS_UNKNOWN:
        print("    %-9s%-17s%-10s%s" % (holder, lane, bound, why))

    print()
    print("=" * 79)
    print("3. FORGONE: sessions that wanted a full reference and could not have one")
    print("=" * 79)
    f = 0.0
    for name, a, b, why, auth in FORGONE:
        d = mins(a, b)
        f += d
        print("  %-14s%s-%s%8.1f min  %s"
              % (name, a.strftime("%H:%M"), b.strftime("%H:%M"), d, auth))
        print("                 %s" % why)
    print("  %-14s%24.1f min = %.2f h of session time that ran without the gate "
          "it needed" % ("TOTAL", f, f / 60))

    print()
    print("=" * 79)
    print("4. AGAINST THE WORKING TIME")
    print("=" * 79)
    w = WORKING_MIN
    d_ = cls.get("DEAD", 0.0)
    o_ = cls.get("LIVE_ORPHAN", 0.0)
    v_ = cls.get("LIVE_VOID", 0.0)
    print("  working time today (92 paired watcher sessions)   %8.1f min" % w)
    print("  waiting INSIDE acquire()            (FLOOR)      %8.1f min  %5.2f%%"
          % (tot, 100 * tot / w))
    print("  lock held by a DEAD holder                       %8.1f min  %5.2f%%"
          % (d_, 100 * d_ / w))
    print("  lock held by a run nobody read (ORPHAN)          %8.1f min  %5.2f%%"
          % (o_, 100 * o_ / w))
    print("  lock held by a run declared unusable (VOID)      %8.1f min  %5.2f%%"
          % (v_, 100 * v_ / w))
    waste = d_ + o_ + v_
    print("  %-49s%s" % ("", "-" * 8))
    print("  lock time that bought NOTHING                    %8.1f min  %5.2f%%"
          "   (%.1f%% of all held time)"
          % (waste, 100 * waste / w, 100 * waste / held))


if __name__ == "__main__":
    main()
