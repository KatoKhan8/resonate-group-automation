"""MX over the amended 2026-09-07 journal. DNS only - no credits, no provider.

S5 gates on `row["mx"] in MX_OK`, and the offline re-judge carried `mx` forward
as null because it never asked. This asks, for every row the amended judge did
not put OUT, and writes the answer back.

RESUMABLE AND INCREMENTAL. It writes its own journal as it goes and re-reads it
on start, because 24k DNS lookups is long enough that it will be interrupted.

    py -3 -u scripts/stage_mx_amended.py
    py -3 scripts/stage_mx_amended.py --report
"""

import argparse
import collections
import io
import json
import os
import sys
import threading
import time
import concurrent.futures as cf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, mx                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
AMENDED = os.path.join(STAGE, "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")
JOURNAL = os.path.join(STAGE, "mx-amended-PRODUCTIVE-2026-09-07.jsonl")

WORKERS = 16      # DNS, not a metered API. The limit is the resolver's.


def rows(path):
    out = []
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    done = {r["domain"]: r for r in rows(JOURNAL)}

    if args.report:
        c = collections.Counter(r.get("mx") for r in done.values())
        ch = collections.Counter(r.get("email_channel") for r in done.values())
        print(f"mx journal: {len(done):,} domains")
        for k, n in c.most_common():
            print(f"  {str(k):<20}{n:>8,}")
        print(f"\nemail channel open: {ch.get(True, 0):,}   "
              f"closed: {ch.get(False, 0):,}")
        return 0

    config = clients.load("productive")
    cache = mx.load_cache()
    cache_lock = threading.Lock()
    write_lock = threading.Lock()

    src = rows(AMENDED)
    todo = [r for r in src
            if r.get("verdict") != "out" and r["domain"] not in done]
    print(f"amended journal {len(src):,} rows; "
          f"already resolved {len(done):,}; todo {len(todo):,}")
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("nothing to do")
        return 0

    counts = collections.Counter()
    started = time.time()
    fh = io.open(JOURNAL, "a", encoding="utf-8")

    def one(r):
        d = r["domain"]
        try:
            with cache_lock:
                local = cache
            decision = mx.for_domain(d, config=config, cache=local)
            status = decision.get("status")
            # known_blocked and no_mx take the EMAIL channel from every
            # contact at this domain. LinkedIn eligibility is untouched -
            # that distinction is the whole point of dual-channel.
            skip = status in (mx.KNOWN_BLOCKED, mx.NO_MX)
        except Exception as e:                                  # noqa: BLE001
            status, skip = "lookup_error", False   # never a skip on a failed ask
        out = dict(r, mx=status, email_channel=(not skip),
                   mx_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with write_lock:
            counts[status] += 1
            fh.write(json.dumps(out) + "\n")
            n = sum(counts.values())
            if n % 500 == 0:
                fh.flush()
                rate = n / max(time.time() - started, 1e-9)
                left = (len(todo) - n) / max(rate, 1e-9) / 60.0
                print(f"  {n:,}/{len(todo):,}  {rate:.0f}/s  "
                      f"~{left:.0f} min left  {dict(counts)}", flush=True)
        return out

    try:
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(one, todo))
    finally:
        fh.flush()
        fh.close()
        with cache_lock:
            mx.save_cache(cache)

    print(f"\ndone in {(time.time()-started)/60:.1f} min")
    for k, n in counts.most_common():
        print(f"  {str(k):<20}{n:>8,}")
    opened = sum(n for k, n in counts.items()
                 if k not in (mx.KNOWN_BLOCKED, mx.NO_MX))
    print(f"\nemail channel open on {opened:,} of {len(todo):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
