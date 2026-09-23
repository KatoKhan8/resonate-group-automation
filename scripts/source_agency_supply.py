#!/usr/bin/env python3
"""Source agency-shaped supply from ContactOut, sliced, counted before bought.

    py scripts/source_agency_supply.py --plan     # slices and free counts only
    py scripts/source_agency_supply.py --run      # walk, buy pages, write rows
    py scripts/source_agency_supply.py --report   # what the last run did

Operator decision, 2026-09-22. This replaces the AI Ark company-search route,
which cannot slice: `companyIndustry` and `companyLocation` are accepted and
INERT there - identical `totalElements` (72,657,969) and byte-identical row
hashes across every filter combination. ContactOut honours industry, size and
location, measured the same day by varying each one at a time.

THE SHAPE, and every part of it is a rule rather than a preference:

  COUNT BEFORE YOU BUY.  `people-count` is free and `company-search` bills one
  credit per company RETURNED - a page of 25 costs 25. Every slice is counted
  first and an empty slice is skipped without spending anything. This is the
  progressive shape the routing policy already requires; here it is free to
  obey, so there is no excuse not to.

  THE BUCKET IS NOT THE HEADCOUNT.  `size` is LinkedIn's self-reported band
  and `employees` is a different estimate - a row in the `51_200` bucket came
  back reading `employees: 392`. `11_50` straddles the client's 20 floor, so
  the floor is applied to `employees` on every row and never inferred from
  the bucket.

  DEDUPE AGAINST EVERYTHING WE ALREADY HOLD.  The estate, the candidate list
  and the client suppression roster, plus the rows collected earlier in this
  run. A domain we already have is not new supply, and buying it again is
  paying twice for the same fact.

  ONE WALKER, RESUMABLE.  A lock, and per-slice page cursors on disk. Two
  walkers on one cursor is how the reply walk put 32,025 rows in a
  16,650-row file.

  CREDITS ARE REPORTED, NEVER GATED.  Per the 2026-09-21 amendment. The run
  stops on the DOMAIN target or on slice exhaustion - never on spend - and
  says what each slice cost.

Output is `work/agency-sourcing.jsonl`, which S3 reads next. Nothing here
writes to the store, enrolls anybody, or touches a provider that sends.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import candidatelist, ingest, singlewalker, store       # noqa: E402
from src.providers import contactout, load_env                   # noqa: E402

OUT = os.path.join(ROOT, "work", "agency-sourcing.jsonl")
STATE = os.path.join(ROOT, "work", "agency-sourcing.state.json")
LOCK = os.path.join(ROOT, "work", "agency-sourcing.lock")

#: The five agency shapes the operator named. Every label was confirmed live
#: on 2026-09-22 to resolve to a real population - a mistyped industry returns
#: zero, which is indistinguishable from an empty market and would have this
#: script report a whole segment as exhausted when it was never asked for.
INDUSTRIES = (
    "Advertising Services",
    "Design Services",
    "Marketing Services",
    "Public Relations and Communications Services",
    "Software Development",
)

#: 20-50 / 51-200 / 201-500 / 501-1000, in ContactOut's bucket codes. There is
#: no `20_50`: the provider's band is `11_50`, so it STRADDLES the 20 floor and
#: the floor is enforced on `employees` per row instead.
#:
#: **THE BANDS THAT CANNOT WASTE A CREDIT COME FIRST.** Operator decision,
#: 2026-09-22. Every company in `51_200` and above already clears the client's
#: 20 floor, so every credit spent there buys a domain that survives the
#: filter. `11_50` is the only band where we pay for companies the floor then
#: discards, and the first 6,474 credits - spent almost entirely inside it -
#: returned about 20% yield and falling.
PRIMARY_BUCKETS = ("51_200", "201_500", "501_1000")

#: Walked LAST, and only if the target has not already been met. Whether it is
#: worth buying at all is tomorrow's decision, and the per-bucket yield report
#: is what that decision is made on.
DEFERRED_BUCKETS = ("11_50",)

BUCKETS = PRIMARY_BUCKETS + DEFERRED_BUCKETS

#: The client's own include list, minus `Nordics` - which is a region in the
#: ICP config, not a country ContactOut can filter on. Its four members are
#: named individually and are already here.
GEOS = (
    "United Kingdom", "Ireland", "Netherlands", "Germany", "France",
    "Sweden", "Norway", "Denmark", "Finland", "Belgium", "Austria",
    "Switzerland", "Spain", "Italy", "Portugal", "Poland", "Australia",
    "New Zealand", "United States", "Canada",
)

MIN_EMPLOYEES = 20
PAGE_SIZE = 25

#: **THERE IS NO DOMAIN TARGET AND NO SPEND CAP.** Operator decision,
#: 2026-09-22: the account behind `CONTACTOUT_TOKEN` is the operator's own and
#: its search credits are available in full for sourcing. The earlier
#: 50,000-domain stop is removed. Every slice runs to exhaustion, in the
#: recorded bucket order, until the slices are done or the balance is empty.
#:
#: THE ONLY THING THAT STOPS THIS RUN IS THE PROVIDER SAYING NO. Slice
#: exhaustion ends a slice; an exhausted balance ends the run. Neither is a
#: question to bring back to the operator mid-run, and a rate limit is neither
#: of them.
#: 402 is payment required. 403 is AMBIGUOUS - it can be an exhausted balance
#: or a revoked key - and both need a human, so both end the run rather than
#: spinning. The stop message quotes the status so the morning summary says
#: which it was instead of guessing.
BALANCE_EXHAUSTED_STATUSES = ("402", "403")

#: Seconds between pages. The first run walked 65 pages of one slice and then
#: took a 429 on every page after it, including the first page of the next
#: seven slices - the limit is per-key and per-minute, not per-slice, so
#: marching on to the next slice inherits the same exhausted budget.
PAGE_PAUSE = 1.5

#: Backoff for a rate limit, in seconds. **A 429 RETRIES THE SAME PAGE.** The
#: standing order is explicit that a provider rate limit is a reason to back
#: off and continue, never a reason to halt - and abandoning the slice is a
#: quiet way of halting it. The first version of this script treated any
#: exception as end-of-slice, so one burst of 429s marched through eight
#: slices collecting nothing and marking them finished.
RATE_LIMIT_BACKOFF = (20, 45, 90, 180, 300)
#: A slice the provider says is enormous is still walked, but the provider
#: stops paging somewhere; this bounds a runaway rather than the spend.
#:
#: 2026-09-23, MEASURED: "somewhere" is page 400, exactly. Probed directly
#: against Software Development|51_200|United States -
#:
#:     page 399  OK, 11 companies        page 401  HTTP 500
#:     page 400  OK, 11 companies        page 402  HTTP 500
#:                                       page 450  HTTP 500
#:
#: so this constant coincidentally equals ContactOut's own ceiling and
#: RAISING IT BUYS NOTHING. The five slices left at page 401 by the
#: 2026-09-22 run are not resumable by paging, and three of them have
#: 273k-326k people behind them on the free count.
#:
#: THE CONSEQUENCE IS THE STRATEGY, NOT THE CAP. One company-search query
#: can surface at most ~400 pages of companies however large the population
#: is. Reaching the rest means SUBDIVIDING the slice - narrower industry,
#: tighter size band, region instead of country - so each sub-query lands
#: inside 400 pages. A bigger number here cannot do it.
MAX_PAGES_PER_SLICE = 400

#: A slice whose free people-count is at least this and which returned NO
#: companies is reported SUSPECT rather than finished.
SUSPECT_COUNT_FLOOR = 1000


def slice_key(industry, bucket, geo):
    return f"{industry}|{bucket}|{geo}"


def slices():
    """Bucket-major, primary bands first.

    The ORDER is the decision: iterating bucket-major means every slice of
    `51_200`, `201_500` and `501_1000` across every industry and geo is walked
    before a single credit goes into `11_50`, where the 20 floor discards part
    of what we pay for. Industry-major would interleave them and spend on the
    straddling band from the first minute.
    """
    for bucket in BUCKETS:
        for industry in INDUSTRIES:
            for geo in GEOS:
                yield industry, bucket, geo


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    return {"slices": {}, "new_domains": 0, "credits": 0,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def save_state(state):
    tmp = f"{STATE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=1)
    os.replace(tmp, STATE)


def already_held():
    """Every domain that is not new supply.

    THREE SOURCES, AND MISSING ONE IS A DOUBLE-BUY. The estate's own records,
    the candidate list from earlier sourcing, and the client's suppression
    roster - a suppressed domain is not merely uninteresting, it is one we
    have been told not to contact, and sourcing it again would walk it back
    into the funnel from the top.
    """
    held = set()
    try:
        for rec in store.load():
            domain = str(rec.get("domain") or "").strip().lower()
            if domain:
                held.add(domain)
    except Exception as exc:                      # noqa: BLE001
        print(f"  WARNING: store unreadable ({exc}); dedupe is weaker",
              flush=True)
    held |= candidatelist.domains_already_known()
    try:
        held |= {str(d).strip().lower() for d in ingest.load_suppress()}
    except Exception as exc:                      # noqa: BLE001
        print(f"  WARNING: suppression unreadable ({exc}); REFUSING to run - "
              "a run that cannot read suppression can source a domain the "
              "client told us to leave alone", flush=True)
        raise
    return {d for d in held if d}


def collected_domains():
    """Domains this run has already written, so a resume does not duplicate."""
    out = set()
    if not os.path.exists(OUT):
        return out
    with open(OUT, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.add(json.loads(line)["domain"])
            except (ValueError, KeyError):
                continue
    return out


def count_slice(industry, bucket, geo):
    """Free probe. `location`, never `current_work_location`.

    BUILD-SPEC section 9 trap 7: the latter returned 86 where the former
    returned 230,222 for the same query, and the adapter refuses it outright.
    """
    result = contactout.people_count(location=geo, industry=[industry],
                                     company_size=[bucket])
    return int(result.get("profiles") or 0)


class BalanceExhausted(RuntimeError):
    """The provider refused for want of credit. The one thing that ends a run."""


def is_rate_limit(exc):
    return "429" in str(exc)


def is_balance_exhausted(exc):
    """A refusal for credit, told apart from every other 4xx.

    Kept separate from `is_rate_limit` deliberately: a 429 means "not this
    minute" and a 402 means "not ever, until somebody tops up". Treating the
    second as the first would spin on backoff for hours against a provider
    that has already given its final answer.
    """
    text = str(exc)
    return any(code in text for code in BALANCE_EXHAUSTED_STATUSES)


def fetch_page(industry, bucket, geo, page_number, key):
    """One page, backing off and RETRYING on a rate limit.

    Returns the page, or None when the slice cannot be advanced now. The
    distinction that matters: a 429 is not a fact about this slice, it is a
    fact about the last minute, so it retries the same page rather than
    concluding anything about the data behind it.
    """
    for attempt, wait in enumerate((0,) + RATE_LIMIT_BACKOFF):
        if wait:
            print(f"    {key} page {page_number}: rate limited, "
                  f"waiting {wait}s", flush=True)
            time.sleep(wait)
        try:
            return contactout.company_search(
                industry=industry, size=bucket, location=geo,
                page=page_number)
        except Exception as exc:                  # noqa: BLE001
            if is_balance_exhausted(exc):
                raise BalanceExhausted(
                    f"{key} page {page_number}: {exc}") from exc
            if not is_rate_limit(exc):
                print(f"    {key} page {page_number}: {exc}", flush=True)
                return None
            if attempt == len(RATE_LIMIT_BACKOFF):
                print(f"    {key} page {page_number}: still rate limited "
                      "after every backoff; leaving the cursor here",
                      flush=True)
                return None
    return None


def plan():
    load_env()
    total = 0
    rows = []
    for industry, bucket, geo in slices():
        n = count_slice(industry, bucket, geo)
        total += n
        rows.append((n, industry, bucket, geo))
        print(f"  {n:>9,}  {industry} | {bucket} | {geo}", flush=True)
    empty = sum(1 for n, *_ in rows if n == 0)
    print(f"\n  {len(rows)} slices, {empty} empty and skipped, "
          f"{total:,} people behind the non-empty ones")
    return rows


def run(max_pages=MAX_PAGES_PER_SLICE):
    load_env()
    state = load_state()
    held = already_held()
    seen = collected_domains()
    print(f"  {len(held):,} domains already held; {len(seen):,} already "
          f"collected by this run", flush=True)

    handle = open(OUT, "a", encoding="utf-8", newline="\n")
    stopped_for = "slices exhausted"
    broke = []
    try:
        for industry, bucket, geo in slices():
            key = slice_key(industry, bucket, geo)
            record = state["slices"].setdefault(
                key, {"count": None, "page": 1, "done": False,
                      "credits": 0, "new": 0})
            if record["done"]:
                continue
            if record["count"] is None:
                record["count"] = count_slice(industry, bucket, geo)
                save_state(state)
            if record["count"] == 0:
                record["done"] = True
                save_state(state)
                continue

            while record["page"] <= max_pages:
                page = fetch_page(industry, bucket, geo, record["page"], key)
                if page is None:
                    broke.append(key)
                    # A non-rate-limit failure, or a rate limit that outlasted
                    # every backoff. The cursor stays put, so a resume picks
                    # this page up rather than skipping past it.
                    break
                companies = page["companies"]
                record["credits"] += len(companies)
                state["credits"] += len(companies)
                if not companies:
                    # EMPTY IS AMBIGUOUS: end-of-results, or a transient
                    # failure, or a filter the provider is not honouring for
                    # this slice. Marking it done conflates all three, and on
                    # 2026-09-22 that silently dropped every Canada slice -
                    # nine of them closed as FINISHED on page one with
                    # thousands of people behind them, because company-search
                    # returns almost nothing for location=Canada and what it
                    # does return is Spanish and Indian companies.
                    record["done"] = True
                    if (record["count"] or 0) >= SUSPECT_COUNT_FLOOR \
                            and record["new"] == 0:
                        record["suspect"] = (
                            f"closed empty on page {record['page']} while the "
                            f"free count said {record['count']:,} - the filter "
                            "may not be honoured for this slice")
                        state.setdefault("suspect", []).append(key)
                    break
                for row in companies:
                    domain = row["domain"]
                    if domain in held or domain in seen:
                        continue
                    employees = row.get("employees")
                    if not isinstance(employees, int) or employees < MIN_EMPLOYEES:
                        # The 20 floor, on `employees` and never on the band.
                        continue
                    seen.add(domain)
                    row["_slice"] = key
                    row["_sourced_at"] = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    handle.write(json.dumps(row) + "\n")
                    record["new"] += 1
                    state["new_domains"] += 1
                handle.flush()
                total = page["total"]
                if not isinstance(total, int) or total <= 0:
                    # `or 0` here closed the slice after ONE page whenever the
                    # provider omitted a total - a full page of results
                    # discarded as "finished". A missing total is UNKNOWN, not
                    # zero. Keep paging; the empty-page branch above is what
                    # legitimately ends a slice.
                    record["page"] += 1
                    save_state(state)
                    time.sleep(PAGE_PAUSE)
                    continue
                if record["page"] * PAGE_SIZE >= total:
                    record["done"] = True
                    break
                record["page"] += 1
                save_state(state)
                time.sleep(PAGE_PAUSE)
            save_state(state)
            if record["new"]:
                print(f"    {key}: +{record['new']} new, "
                      f"{record['credits']} credits, total "
                      f"{state['new_domains']:,}", flush=True)
    except BalanceExhausted as exc:
        # The provider's final answer, not a transient one. Everything bought
        # so far is on disk and every cursor is saved, so a top-up resumes
        # exactly here.
        stopped_for = f"BALANCE EXHAUSTED - {exc}"
    finally:
        handle.close()
        save_state(state)
    if broke and stopped_for == "slices exhausted":
        # "slices exhausted" was the INITIAL value, overwritten only on a
        # credit refusal - so a night of 5xx or ambiguous 403s would end the
        # run printing a clean finish while most of the slice space was never
        # walked. A slice that BROKE was not exhausted, and the difference is
        # the operator reading success where there was none.
        names = sorted(set(broke))
        stopped_for = (f"slices exhausted EXCEPT {len(names)} that BROKE and "
                       f"were not walked to the end: {names[:5]}")
    suspect = state.get("suspect") or []
    if suspect:
        print(f"\n  SUSPECT - closed empty while the free count said there "
              f"was supply ({len(set(suspect))}): {sorted(set(suspect))[:6]}")
    print(f"\n  stopped: {stopped_for}")
    report(state)
    return 0


def by_bucket(state):
    """Yield and cost per size band. **The number tomorrow's decision needs.**

    `credits per qualified domain` is the whole question about `11_50`: every
    other band clears the 20 floor by construction, so its credits and its
    domains are the same event. In `11_50` we pay for companies the floor then
    discards, and this is where that shows up as a price.
    """
    rows = {}
    for key, slice_state in state["slices"].items():
        bucket = key.split("|")[1]
        agg = rows.setdefault(bucket, {"credits": 0, "new": 0, "slices": 0,
                                       "done": 0})
        agg["credits"] += slice_state.get("credits") or 0
        agg["new"] += slice_state.get("new") or 0
        agg["slices"] += 1
        agg["done"] += 1 if slice_state.get("done") else 0
    return rows


def print_by_bucket(state):
    rows = by_bucket(state)
    if not rows:
        return
    print("\n  PER BUCKET - yield, and what a qualified domain costs:")
    print(f"    {'bucket':<10} {'credits':>9} {'new':>8} {'yield':>7} "
          f"{'cr/domain':>10}  slices")
    order = [b for b in BUCKETS if b in rows] + \
            [b for b in rows if b not in BUCKETS]
    for bucket in order:
        agg = rows[bucket]
        pct = (agg["new"] / agg["credits"] * 100) if agg["credits"] else 0
        per = (agg["credits"] / agg["new"]) if agg["new"] else 0
        note = "  <- straddles the 20 floor" if bucket in DEFERRED_BUCKETS \
            else ""
        print(f"    {bucket:<10} {agg['credits']:>9,} {agg['new']:>8,} "
              f"{pct:>6.1f}% {per:>10.1f}  "
              f"{agg['done']}/{agg['slices']}{note}")


def report(state=None):
    state = state or load_state()
    done = sum(1 for s in state["slices"].values() if s["done"])
    empty = sum(1 for s in state["slices"].values() if s.get("count") == 0)
    print(f"\n  new domains  {state['new_domains']:,}")
    print(f"  credits      {state['credits']:,}  (reported, never gated)")
    print(f"  slices       {done} done of {len(state['slices'])} touched, "
          f"{empty} empty")
    print_by_bucket(state)
    top = sorted(state["slices"].items(), key=lambda kv: -kv[1]["new"])[:12]
    print("\n  best slices:")
    for key, s in top:
        if s["new"]:
            print(f"    {s['new']:>6} new  {s['credits']:>6} cr  {key}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument(
        "--max-pages", type=int, default=MAX_PAGES_PER_SLICE,
        help=("pages per slice before the walk gives up on it. The DEFAULT "
              "stays %(default)s: five slices ended the 2026-09-22 run sitting "
              "at page 401 against this cap, and a resume at the default walks "
              "ZERO pages for them and reports a clean finish - the exact "
              "false-completion shape 4854964b fixed elsewhere in this file. "
              "Raising it is a SPEND decision and belongs on the command line, "
              "not in a constant somebody edits and forgets. NOTE, measured "
              "2026-09-23: ContactOut itself 500s past page 400, so raising "
              "this above %(default)s buys nothing - see the constant."))
    args = parser.parse_args(argv)
    if args.report:
        return report()
    if args.plan:
        plan()
        return 0
    if not args.run:
        parser.error("one of --plan, --run or --report")
    if args.max_pages != MAX_PAGES_PER_SLICE:
        print(f"  MAX PAGES PER SLICE RAISED: {MAX_PAGES_PER_SLICE} -> "
              f"{args.max_pages}. This buys pages, and pages cost credits.")
    with singlewalker.held(LOCK):
        return run(max_pages=args.max_pages)


if __name__ == "__main__":
    raise SystemExit(main())
