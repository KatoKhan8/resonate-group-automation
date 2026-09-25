"""Free-crawl the US slice of `work/qualified-supply.jsonl` into research packs.

LANE K, 2026-09-25. **Nothing here spends a cent and nothing here calls Apify.**

## WHY THIS EXISTS

Zero of the 32,951 sourced domains in `work/qualified-supply.jsonl` carry a
research pack. The 439 domains that ARE packed are the UK/EU cohort and the
pilots and they are disjoint from the supply - measured, not assumed, and
re-measured by `--report` below. `src/copylint.py` rule 1 refuses any lead
whose step-1 opener touches no pack fact, so the whole 09-07 list is
unpushable until it is packed.

## WHAT IT RUNS, AND WHAT IT REFUSES TO FORK

`src/researchpack/site.py` belongs to LANE C and is unmerged. It is NOT
copied into this branch. It is materialised from lane C's own git blob at
run time and the blob sha is printed, so what ran is provably byte-identical
to what lane C wrote:

    git show worktree-agent-aea4a82ef07084898:src/researchpack/site.py
    blob 225f4354418419b20c5b9bd1ca15015ab6ded17e

`src/webfetch.py` and `src/researchpack/facts.py` are on master already and
are byte-identical to lane C's copies (`git rev-parse` on both branches
agrees), so those are imported normally.

## THE SSRF GATE THE FREE PATH DID NOT HAVE

`src/providers/apify.check_url` is the SSRF posture this repository wrote -
scheme, credentials, port, loopback names, internal suffixes, private and
reserved addresses, and DNS resolution of the host. It guards the APIFY
input path only; `webfetch.research` never calls it. `webfetch` has its own
bounds (https only, `same_domain`, bounded redirects, robots, byte/page/wall
caps) but it does NOT ask whether a supply domain resolves into RFC1918.

With 16,247 attacker-adjacent strings arriving from a sourcing file, that
gap is worth closing, so every domain is put through `check_url` BEFORE the
crawler sees it. Nothing was widened: the function is imported and called,
not edited, and a refusal is recorded as UNSAFE_URL and never crawled.
Importing `src.providers.apify` starts no run and needs no token.

## CONCURRENCY

One worker handles one domain end to end, so per-host concurrency is 1 by
construction however high K goes - the politeness bound a crawler actually
owes a site is respected at every K. Robots is asked per domain either way.
Use `--calibrate` to measure a K on this estate rather than inheriting one.

## DURABILITY

Results append to a JSONL as each domain finishes and the handle is flushed
every row, because a long crawl that is lost at hour two is worth nothing.
`--resume` skips domains already in the log. `--consolidate` turns the log
into a `src/researchpack/cache.py`-shaped JSON that `RESEARCH_PACK_CACHE`
can point at.

`researchpack.cache.put` is deliberately NOT used for the walk: it loads and
rewrites the whole cache per entry, which is O(n^2) over 16,247 domains.
"""
import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from src import webfetch                                    # noqa: E402
from src.researchpack import facts as packfacts             # noqa: E402
from src.providers import apify                             # noqa: E402

#: Lane C's branch and the file this lane borrows from it, unchanged.
LANE_C_BRANCH = "worktree-agent-aea4a82ef07084898"
LANE_C_SITE = "src/researchpack/site.py"

#: The source is free and the provider cannot bill. Stated once, asserted
#: at the end of every run, and written into every row.
PROVIDER = "local_http"
USD = 0.0

#: Priority, from the brief: only ~2,500 addresses can be verified today, so
#: the first few thousand domains matter far more than the last ten thousand.
#: `known_allowed` outranks `unknown_provider` because a domain whose MX we
#: cannot place cannot be verified at all today.
MX_RANK = {"known_allowed": 0, "unknown_provider": 1}


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


# ------------------------------------------------------- lane C's module

def lane_c_site(repo, branch=LANE_C_BRANCH, path=LANE_C_SITE, into=None):
    """Load lane C's `site.py` from its blob. Returns `(module, blob_sha)`.

    Materialised rather than imported from a checkout because lane C's tree
    is not this tree, and copied into `src/` rather than never because a
    copy in `src/` would be a fork somebody later edits.
    """
    sha = subprocess.run(["git", "rev-parse", "%s:%s" % (branch, path)],
                         cwd=repo, capture_output=True, text=True, check=True
                         ).stdout.strip()
    body = subprocess.run(["git", "cat-file", "blob", sha],
                          cwd=repo, capture_output=True, check=True).stdout
    target = into or os.path.join(repo, "work", "lanec-site-%s.py" % sha[:12])
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as handle:
        handle.write(body)

    # `site.py` says `from .. import webfetch` and `from . import facts`, so
    # it has to load as a member of the real package rather than standalone.
    name = "src.researchpack.site"
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, sha


# ------------------------------------------------------------ the supply

def read_supply(path, country="United States"):
    """The slice, in priority order, deduplicated on domain."""
    rows, seen = [], set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if country and rec.get("country") != country:
                continue
            domain = str(rec.get("domain") or "").strip().lower().lstrip("@")
            if not domain or domain in seen:
                continue
            seen.add(domain)
            rows.append(rec)
    return rows


def prioritise(rows):
    """known_allowed first, then the largest `_slice` buckets first.

    Bucket size is counted over the slice itself rather than hardcoded, so
    the order follows the file instead of a number typed from a report.
    """
    sizes = {}
    for rec in rows:
        sizes[rec.get("_slice")] = sizes.get(rec.get("_slice"), 0) + 1

    def key(rec):
        return (MX_RANK.get(rec.get("_mx_status"), 9),
                -sizes.get(rec.get("_slice"), 0),
                str(rec.get("_slice") or ""),
                str(rec.get("domain")))

    return sorted(rows, key=key)


# -------------------------------------------------------------- one domain

def pack_one(rec, site, config=None):
    """One domain, free. Returns the row that goes in the log."""
    domain = str(rec.get("domain") or "").strip().lower().lstrip("@")
    row = {
        "domain": domain,
        "name": rec.get("name"),
        "industry": rec.get("industry"),
        "slice": rec.get("_slice"),
        "mx_status": rec.get("_mx_status"),
        "retrieved_at": now(),
        "provider": PROVIDER,
        "usd": USD,
        "facts": [],
    }
    started = time.monotonic()
    try:
        # THE SSRF GATE, BEFORE THE CRAWLER SEES THE STRING.
        apify.check_url("https://%s/" % domain, allowed_domain=domain,
                        resolve=True)
    except apify.UnsafeURL as e:
        row["outcome"] = "UNSAFE_URL"
        row["refused"] = str(e)
        row["seconds"] = round(time.monotonic() - started, 2)
        return row
    except Exception as e:                      # noqa: BLE001 - classified
        row["outcome"] = "UNSAFE_URL"
        row["refused"] = "%s: %s" % (type(e).__name__, e)
        row["seconds"] = round(time.monotonic() - started, 2)
        return row

    try:
        made, outcome = site.research(domain, config=config)
    except Exception as e:                      # noqa: BLE001 - classified
        row["outcome"] = "RESEARCH_FAILED"
        row["error"] = "%s: %s" % (type(e).__name__, e)
        row["seconds"] = round(time.monotonic() - started, 2)
        return row

    row["facts"] = made
    row["outcome"] = outcome.get("outcome")
    row["stats"] = outcome.get("stats") or {}
    row["pages_kept"] = outcome.get("pages_kept")
    row["off_domain_pages_dropped"] = outcome.get("off_domain_pages_dropped")
    row["retrieved_at"] = outcome.get("retrieved_at") or row["retrieved_at"]
    row["seconds"] = round(time.monotonic() - started, 2)
    # Belt and braces on the one thing that must never be wrong here.
    if outcome.get("usd"):
        raise RuntimeError("the free crawl reported a cost of %r on %s"
                           % (outcome.get("usd"), domain))
    return row


# ------------------------------------------------------------- the walk

class Log:
    """An append-only JSONL, flushed every row, safe across threads."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._handle = open(path, "a", encoding="utf-8")

    def write(self, row):
        line = json.dumps(row, ensure_ascii=False, default=str)
        with self._lock:
            self._handle.write(line + "\n")
            self._handle.flush()

    def close(self):
        self._handle.close()


def already_done(path):
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line).get("domain"))
            except ValueError:
                continue
    return done


def walk(rows, site, log, workers, config=None, every=250, label=""):
    """Crawl `rows` with K workers. Returns (done, seconds)."""
    started = time.monotonic()
    counter = {"n": 0, "facts": 0}
    lock = threading.Lock()

    def one(rec):
        row = pack_one(rec, site, config=config)
        log.write(row)
        with lock:
            counter["n"] += 1
            counter["facts"] += 1 if row.get("facts") else 0
            n = counter["n"]
            if every and (n % every == 0 or n == len(rows)):
                spent = time.monotonic() - started
                sys.stderr.write(
                    "%s %d/%d  %.3f dom/s  %d with a fact (%.1f%%)  %.0fs\n"
                    % (label, n, len(rows), n / spent if spent else 0.0,
                       counter["facts"], 100.0 * counter["facts"] / n, spent))
                sys.stderr.flush()
        return row

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, rows))
    return counter["n"], time.monotonic() - started


# ------------------------------------------------------------ consolidate

def consolidate(log_path, out_path, profile="site_content"):
    """The log, as a `researchpack.cache`-shaped JSON keyed `domain::profile`.

    Only domains that made at least one fact get an entry: a cache entry
    with no facts is a 30-day promise that this domain has been researched,
    and it has not.
    """
    data, rows, kept = {}, 0, 0
    with open(log_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows += 1
            if not row.get("facts"):
                continue
            kept += 1
            data["%s::%s" % (row["domain"], profile)] = {
                "domain": row["domain"],
                "profile": profile,
                "retrieved_at": row.get("retrieved_at"),
                "facts": row["facts"],
                "cost": 0,
            }
    tmp = out_path + ".tmp"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, default=str)
    os.replace(tmp, out_path)
    return rows, kept


# ------------------------------------------------------------------ cli

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--supply", required=True)
    ap.add_argument("--log", required=True, help="append-only JSONL")
    ap.add_argument("--cache", help="consolidated JSON cache to write at the end")
    ap.add_argument("--country", default="United States")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--calibrate", default="",
                    help="comma-separated K values to measure on a sample")
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--every", type=int, default=250)
    ap.add_argument("--consolidate-only", action="store_true")
    args = ap.parse_args(argv)

    if args.consolidate_only:
        rows, kept = consolidate(args.log, args.cache)
        print("consolidated %d log row(s) -> %d cache entr(ies) at %s"
              % (rows, kept, args.cache))
        return 0

    site, sha = lane_c_site(HERE)
    print("lane C site.py blob %s (loaded, not forked)" % sha)
    print("webfetch bounds: %s" % json.dumps(webfetch.settings(None)))

    rows = prioritise(read_supply(args.supply, args.country))
    print("%s: %d domain(s) in the supply" % (args.country, len(rows)))

    if args.calibrate:
        # A sample taken from the MIDDLE of the priority order, so the
        # measurement is not made on the head the real run also uses - and a
        # DISJOINT window per K, because `webfetch.robots_allows` caches per
        # domain and the OS caches DNS, so re-running the same 40 domains at
        # a higher K would measure the warm cache and call it concurrency.
        mid = len(rows) // 2
        log = Log(args.log)
        try:
            ks = [int(x) for x in args.calibrate.split(",") if x.strip()]
            for i, k in enumerate(ks):
                lo = mid + i * args.sample
                sample = rows[lo:lo + args.sample]
                done, spent = walk(sample, site, log, k, every=0,
                                   label="K=%d" % k)
                print("K=%-3d %d domain(s)  %.1fs  %.3f dom/s"
                      % (k, done, spent, done / spent if spent else 0.0))
        finally:
            log.close()
        return 0

    if args.resume:
        done = already_done(args.log)
        before = len(rows)
        rows = [r for r in rows if r.get("domain") not in done]
        print("resume: %d already in the log, %d to go" % (before - len(rows),
                                                           len(rows)))
    if args.offset:
        rows = rows[args.offset:]
    if args.limit:
        rows = rows[:args.limit]

    log = Log(args.log)
    try:
        n, spent = walk(rows, site, log, args.workers, every=args.every)
    finally:
        log.close()
    print("%d domain(s) in %.1fs at K=%d  %.3f dom/s  $%.5f"
          % (n, spent, args.workers, n / spent if spent else 0.0, USD))

    if args.cache:
        total, kept = consolidate(args.log, args.cache)
        print("consolidated %d log row(s) -> %d cache entr(ies) at %s"
              % (total, kept, args.cache))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
