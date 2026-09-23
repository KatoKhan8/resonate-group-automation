"""S3: ICP qualification over a staging journal, never the live store.

WHY A STAGING JOURNAL. `store.save` rewrites the whole queue file, and a
record averages ~31 KB. Pushing 24,404 domains through the live store to find
out which ones qualify would rewrite hundreds of megabytes per pass for
records that mostly will not survive S3. So this walks a JSONL journal in
gitignored `work/stage/` and a record reaches the store only when it is READY.

RESUMABLE BECAUSE IT WILL BE INTERRUPTED. Every batch appends its verdicts and
the journal is the checkpoint: a re-run reads what is already decided and asks
the provider only about the rest. A crash at domain 12,000 costs the current
batch of 30, not the 12,000.

THE VERDICT IS THREE-VALUED AND `flagged` IS NOT `out`. The client's own ICP
sets `flag_dont_drop: true`, and this respects it: a domain the provider
cannot size, or that sits outside the named geos without being in an excluded
one, is FLAGGED with its reason and stays available for a human or a later
signal. Only an explicit disqualifier is OUT. Nothing is dropped silently -
every domain leaves this stage carrying a verdict and a reason.

COST. `/domain/enrich` takes up to 30 domains per call and bills ONE SEARCH
CREDIT PER COMPANY FOUND - not per call, and not free. Search credits are a
separate pool from email credits: 117,419 remaining at the 2026-09-21
baseline, so a full 24,404-domain pass is about 21% of it.

    py -3 scripts/stage_s3_icp.py --limit 600
    py -3 scripts/stage_s3_icp.py --until-in 500     # stop once 500 are IN
"""

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, mx                                    # noqa: E402
from src.providers import contactout, load_env                 # noqa: E402

STAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "work", "stage")
JOURNAL = os.path.join(STAGE, "s3-icp.jsonl")
SURVIVORS = os.path.join(STAGE, "s1-survivors.json")

BATCH = 30            # the endpoint's documented maximum
CALLS_PER_MIN = 60    # ContactOut's published limit for this route


def decided():
    """{domain: verdict} already in the journal. The checkpoint."""
    out = {}
    if not os.path.exists(JOURNAL):
        return out
    with open(JOURNAL, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue                      # a torn last line is not fatal
            if row.get("domain"):
                out[row["domain"]] = row
    return out


def _shape(raw):
    """The few fields S3 judges on, off one company object.

    Deliberately not `company_info`'s full shape: this stage decides size and
    geo and nothing else, and the keys are the live ones confirmed on the
    2026-08-26 response - `employees` is the head count, `size` is a bucket
    code and is NOT a fallback for it.
    """
    if not isinstance(raw, dict):
        return {}
    return {
        "domain": raw.get("domain") or raw.get("website"),
        "name": raw.get("name") or raw.get("company_name"),
        "employees": raw.get("employees", raw.get("employee_count")),
        "industry": raw.get("industry"),
        "offices": raw.get("locations") or raw.get("offices") or [],
        # THE COUNTRY IS ITS OWN FIELD, AND MATCHING THE ADDRESS BLOB IS WRONG.
        # The first pass matched geo names against `locations` + `industry`,
        # and a location reads "Marienstr. 37, Stuttgart, 70178, DE" - the
        # country appears as a two-letter code or not at all, so "Germany"
        # never matched. 70 of the first 300 were FLAGGED "geo not confirmed"
        # while holding a perfectly good `country: "Germany"`. Confirmed live
        # 2026-09-21.
        "country": raw.get("country"),
    }


#: OPERATOR AMENDMENT, 2026-09-22. (The operator is named in the
#: authorization document below, which is where attribution belongs; the
#: hygiene guard forbids real names in tracked files and this comment was
#: one of two places leaking one.)
#: `docs/OPERATOR-AUTHORIZATION-2026-09-22-BOUNCE-DENOMINATOR-AND-HEADCOUNT.md`
#: section D: "Remove the headcount criterion from the S3 ICP verdict for the
#: 2026-09-07 Productive file (24,404 domains). Geo and industry rules
#: unchanged; unknown country stays FLAGGED."
#:
#: IT IS BOUND TO THE SNAPSHOT BY NAME AND REFUSES ANY OTHER, because the
#: authorisation's own scope line is that `config/clients/productive.yaml` is
#: NOT edited and the 20+ floor still applies to every sourced account and
#: every future export. A flag that could be passed to another file would be
#: exactly the config edit the operator declined to make.
HEADCOUNT_AMENDMENT = "PRODUCTIVE-2026-09-07"

#: OPERATOR DECISION, the operator, 2026-09-23. Second amendment, same
#: snapshot. A domain the CLIENT supplied on their own list is IN even when
#: its country is outside the configured allow list, "because the client
#: supplied these domains on their own list" - the client naming a company is
#: itself the market signal the allow list exists to approximate.
#:
#: IT DOES NOT TOUCH THE BLOCK LIST. `exclude_geos` still returns OUT, because
#: a block is a refusal and not a default, and the operator said so in as many
#: words: "The block list (IN, PK, AE and the rest) stays OUT."
#:
#: IT IS NOT A WIDER ALLOW LIST, and the difference is the whole point. SOURCED
#: supply from Canada, Poland or Czechia stays FLAGGED pending Productive's
#: answer; only client-supplied rows get this. A judge that could not tell the
#: two apart would have quietly turned a question for the client into a policy.
CLIENT_SUPPLIED_AMENDMENT = "PRODUCTIVE-2026-09-07"


def judge(info, icp, headcount=True, client_supplied=False):
    """(verdict, reason). `flagged` whenever the evidence cannot decide.

    `headcount=False` applies the 2026-09-22 amendment: size is not judged at
    all. It is NOT the same as widening the band - a company whose headcount
    is unknown stops being FLAGGED for that reason, which is most of what the
    amendment recovers.
    """
    if not info or not info.get("domain"):
        return "flagged", "provider returned no company for this domain"

    if headcount:
        emp = info.get("employees")
        try:
            emp = int(emp) if emp not in (None, "") else None
        except (TypeError, ValueError):
            emp = None

        lo = icp.get("size_min_employees") or 0
        hi = icp.get("size_max_employees") or 1000
        if emp is None:
            size = ("flagged", "headcount unknown")
        elif emp < lo:
            size = ("out", f"headcount {emp} below {lo}")
        elif emp > hi:
            size = ("out", f"headcount {emp} above {hi}")
        else:
            size = ("in", f"headcount {emp}")
    else:
        size = ("in", "headcount not judged (2026-09-22 amendment)")

    country = (info.get("country") or "").strip().lower()
    for bad in (icp.get("exclude_geos") or []):
        if bad.strip().lower() == country:
            return "out", f"excluded geo: {bad}"

    # "Nordics" is a grouping rather than a country. Left unexpanded it
    # silently failed every Swedish, Danish, Norwegian and Finnish company.
    NORDICS = {"sweden", "norway", "denmark", "finland", "iceland"}
    geos = set()
    for g in (icp.get("geos") or []):
        g = g.strip().lower()
        geos |= NORDICS if g == "nordics" else {g}
    geo_hit = (country in geos) if geos else True
    if not country:
        geo_hit = False          # unknown country is flagged, never assumed in

    if size[0] == "out":
        return size
    if size[0] == "flagged":
        return "flagged", size[1]
    if not geo_hit:
        # A country we could not read at all is NOT the same as a country
        # outside the list, and the 2026-09-23 amendment covers only the
        # second. `country` is empty for the first, and it stays flagged so it
        # reaches the resolution chain instead of being waved through.
        if client_supplied and country:
            return "in", (f"{size[1]}, geo {country} outside the allow list "
                          f"but client-supplied (2026-09-23 amendment)")
        # flag_dont_drop: absence of a named geo is not a disqualifier.
        return "flagged", f"{size[1]}, geo not confirmed"
    return "in", f"{size[1]}, geo matched"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after this many NEW domains")
    parser.add_argument("--until-in", type=int, default=None,
                        help="stop once this many verdicts are `in`")
    args = parser.parse_args(argv)

    load_env()
    os.makedirs(STAGE, exist_ok=True)
    client_config = clients.load("productive")
    icp = (client_config.get("market") or {})
    # One cache for the whole run: fifty contacts at one company resolve once,
    # and the entry is good for seven days under the client's policy.
    mx_cache = mx.load_cache()
    mx_counts = {}

    survivors = json.load(open(SURVIVORS, encoding="utf-8"))
    already = decided()
    todo = [d for d in survivors if d not in already]
    in_count = sum(1 for r in already.values() if r.get("verdict") == "in")

    print(f"S3 ICP  survivors {len(survivors)}  already decided {len(already)}"
          f"  (in {in_count})  todo {len(todo)}")
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("nothing to do")
        return 0

    spacing = 60.0 / CALLS_PER_MIN
    counts = {"in": 0, "out": 0, "flagged": 0}
    found = 0
    started = time.time()

    with open(JOURNAL, "a", encoding="utf-8") as journal:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            t0 = time.time()
            try:
                # ONE CALL FOR THIRTY DOMAINS, NOT THIRTY CALLS.
                #
                # `contactout.company_info` takes a single domain and is the
                # wrong primitive here: at 24,404 domains and 60 calls/min it
                # is 6.8 hours. Probed live 2026-09-21 - the endpoint answers
                # `{"companies": {"<domain>": {...}}}` with EVERY domain of
                # the request present, so the batch is one request and the
                # walk is 814 calls, about fourteen minutes.
                raw = contactout.call("company-information-from-domain",
                                      {"domains": chunk})
                companies = raw.get("companies") or {}
                infos = {d: _shape(companies.get(d) or {}) for d in chunk}
            except Exception as e:                              # noqa: BLE001
                print(f"  batch {i//BATCH}: {type(e).__name__}: "
                      f"{str(e)[:120]} - left undecided, resumable")
                continue
            for d in chunk:
                info = infos.get(d) or {}
                if info.get("domain"):
                    found += 1
                verdict, reason = judge(info, icp)
                counts[verdict] += 1

                # S4b: MX, HERE AND NOT ONLY IN THE SEND PATH.
                #
                # It runs BEFORE any paid call, so a domain that accepts no
                # mail never costs a person-search or a verification credit.
                # `cadence.py:1125` still gates on `mx.allows_email` at
                # promotion and that backstop is deliberately kept - this is
                # the cheap early copy of the same question, not a
                # replacement for it.
                #
                # THE ADDRESS DOMAIN, NOT THE COMPANY DOMAIN. These domains
                # were derived in S1 from each contact's `Work Email`, so `d`
                # IS the address domain already; the company's website domain
                # can differ and is not what accepts the mail.
                mx_out = mx_skip = None
                if verdict != "out":
                    try:
                        decision = mx.for_domain(d, config=client_config,
                                                 cache=mx_cache)
                        mx_out = decision.get("status")
                        mx_counts[mx_out] = mx_counts.get(mx_out, 0) + 1
                        # known_blocked and no_mx take the EMAIL channel away
                        # from every contact at this domain and skip their S5
                        # verification. LinkedIn eligibility is untouched.
                        mx_skip = mx_out in (mx.KNOWN_BLOCKED, mx.NO_MX)
                    except Exception as e:                      # noqa: BLE001
                        mx_out = "lookup_error"
                        mx_counts[mx_out] = mx_counts.get(mx_out, 0) + 1
                        mx_skip = False       # never a skip on a failed ask

                journal.write(json.dumps({
                    "domain": d, "verdict": verdict, "reason": reason,
                    "employees": info.get("employees"),
                    "industry": info.get("industry"),
                    "country": info.get("country"),
                    "mx": mx_out,
                    "email_channel": (None if mx_out is None
                                      else (not mx_skip)),
                    "at": datetime.datetime.now(
                        datetime.timezone.utc).isoformat(),
                }) + "\n")
            journal.flush()
            in_count += counts["in"]
            done = i + len(chunk)
            if done % 300 < BATCH or done >= len(todo):
                print(f"  {done}/{len(todo)}  in {counts['in']} "
                      f"out {counts['out']} flagged {counts['flagged']}  "
                      f"search credits ~{found}")
            if args.until_in and in_count >= args.until_in:
                print(f"  reached {in_count} IN, stopping")
                break
            nap = spacing - (time.time() - t0)
            if nap > 0:
                time.sleep(nap)

    mx.save_cache(mx_cache)

    print(f"\nS3 DONE in {time.time()-started:.0f}s")
    print(f"  in {counts['in']}  out {counts['out']} "
          f"flagged {counts['flagged']}")
    print(f"  companies found (search credits spent) ~{found}")

    # S4b is reported as FIVE outcomes, never collapsed to pass/fail. A
    # `dns_failure` is "we could not ask" and is HELD; folding it in with
    # `no_mx` - "this domain accepts no mail" - is the one mistake that
    # would send into exactly what the module exists to avoid.
    print("\nS4b MX (address domain, 7-day cache, no credits):")
    for key in (mx.KNOWN_ALLOWED, mx.KNOWN_BLOCKED, mx.UNKNOWN_PROVIDER,
                mx.DNS_FAILURE, mx.NO_MX, "lookup_error"):
        print(f"  {key:<18} {mx_counts.get(key, 0)}")
    blocked = mx_counts.get(mx.KNOWN_BLOCKED, 0) + mx_counts.get(mx.NO_MX, 0)
    print(f"  -> EMAIL skipped for {blocked} domain(s), and their S5 "
          f"verification with it. LinkedIn eligibility unchanged.")
    print(f"  -> {mx_counts.get(mx.DNS_FAILURE, 0)} HELD on dns_failure: we "
          f"could not ask, so the channel is not allowed.")
    print(f"  -> not asked for {counts['out']} domain(s) already OUT at S3.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
