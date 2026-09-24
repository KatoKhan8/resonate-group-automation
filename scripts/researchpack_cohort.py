#!/usr/bin/env python3
"""Research packs for a COHORT that is about to be written to.

    py -3 scripts/researchpack_cohort.py                         # plan only
    py -3 scripts/researchpack_cohort.py --live --work <dir>

## WHY A COHORT AND NOT AN ESTATE

`docs/RESEARCH-PACK-PILOT-2026-09-24.md` ends on the arithmetic that decides
this: all four sources on all 19,612 accounts is $781.94 a month against
$199. With the website crawl moved to our own free crawler the LinkedIn half
is $215 on the whole estate - still over - and the operator's third option
was the one that actually fits: research the accounts that reach a campaign,
because a pack bought for an account nobody writes to is spend with no
addressee. This script buys for exactly one cohort.

## THE COHORT IS THE ONE `batch1_build` WOULD BUILD, NOT ONE OF MY OWN

`selection()` below is `scripts/batch1_build.select` restricted to the
requested cohorts: the same `s7-copy.jsonl` rendered rows, the same
`s3-icp.jsonl` country, the same `clientapproval.is_approved` gate, the same
`campaigns x 45` cap. It is a SECOND READER of that selection and not a
second definition of it - if the two ever disagree the packs are for
accounts the push will not carry, so `--plan` prints the counts to be
checked against `batch1_build --plan` before any money moves.

## EVERY PAID CALL IS CHECKED AND THEN RECORDED

`researchpack.pack.check_budget` asks `spendledger.check` before each Apify
run and `spendledger.record` writes the row. This script's own job is to
print what is already committed BEFORE it starts, and to HALT on
`BudgetExceeded` rather than catch it and carry on - a ceiling that a walk
steps over is not a ceiling. It never raises one: `--budget-usd` can only
stop the walk sooner.

## WHAT IT MEASURES, AND WHY OBSERVED IS NOT PLANNED

The same reason `scripts/researchpack_pilot.py` gives. `spendledger` holds
the EXPECTED cost in whole cents rounded up, which is right for a control
and wrong for a cost report: every LinkedIn run costs a fraction of a cent.
The dollars here are `usageTotalUsd` read back off each Apify RUN RECORD,
plus the account's own monthly-usage total before and after.

`site_content` has no run record because it has no run. It is reported with
`$0.00000` and the requests and seconds `webfetch` counts, which are the two
costs a local read actually has.

## IT WRITES TO `work/`, UNDER ITS OWN NAMES

The per-account rows name real prospects, so the file is gitignored and the
summary printed to stdout is the safe half. Both the pack cache and the
output file are named for this run and are not files any other process
reads - a shared cache warmed by one lane is a call another lane thinks it
made.
"""
import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The cohort windows, copied from `scripts/batch1_build.COHORTS` - the same
#: country lists and the same campaign counts. Imported would be better and
#: is not possible: that module reads `work/` paths off its own location at
#: import time, and this script has to be pointed at a different `work/`.
COHORTS = {
    "us": {"countries": {"United States"}, "campaigns": 5},
    "uk": {"countries": {"United Kingdom", "Ireland"}, "campaigns": 2},
    "eu": {"countries": {"Germany", "Sweden", "France", "Finland",
                         "Netherlands", "Denmark", "Norway", "Belgium",
                         "Austria", "Switzerland", "Poland", "Spain",
                         "Italy", "Croatia", "Portugal", "Czechia"},
           "campaigns": 1},
}
PER_CAMPAIGN = 45

#: `economic_buyer` is this estate's word for the exec. `champion` is its own.
PERSONAS = {"champion": "champion", "exec": "economic_buyer"}

SOURCES = ("open_roles", "company_posts", "person_posts:champion",
           "person_posts:exec", "site_content")

KIND_OF = {"open_roles": "open_role", "company_posts": "company_post",
           "person_posts:champion": "person_post",
           "person_posts:exec": "person_post",
           "site_content": "site_page"}

#: Which of the five are billed by Apify. `site_content` is ours.
PAID = ("open_roles", "company_posts", "person_posts:champion",
        "person_posts:exec")


def point_at(work_dir):
    """Every path this run touches, named before anything is imported.

    A worktree has its own empty `work/`, and a probe that resolves against
    it reads nothing and reports it as an empty estate. The queue, the spend
    ledger and the client-approval file are therefore pinned to the
    directory the operator named, and the pack CACHE deliberately is not -
    it gets a name of this run's own.
    """
    work_dir = os.path.abspath(work_dir)
    os.environ["QUEUE"] = os.path.join(work_dir, "queue.jsonl")
    os.environ["CAMPAIGNS"] = os.path.join(work_dir, "campaigns.jsonl")
    os.environ["SPEND_LEDGER"] = os.path.join(work_dir, "spend-ledger.jsonl")
    os.environ["CLIENT_APPROVAL"] = os.path.join(work_dir,
                                                 "client-approval.jsonl")
    return work_dir


def _jsonl(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def cohort_of(country, wanted):
    for name in wanted:
        if country in COHORTS[name]["countries"]:
            return name
    return None


def source_people(work_dir):
    """The supplier CSV, keyed by work email. `Url` is a LinkedIn profile.

    THE SAME FILE `batch1_build` READS, and the reason this script does not
    read the queue for its subjects. Batch 1's leads are built from this CSV
    plus `s7-copy.jsonl`; the queue holds 1,582 records and 53 of the 92
    accounts in tomorrow's UK/EU cohort have no row in it at all. Taking the
    queue as the subject list would have silently researched 39 accounts and
    reported that as the cohort.
    """
    import csv
    path = os.path.join(work_dir, "Productive",
                        "productive_ICP_safe_to_send (1).csv")
    people = {}
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("Work Email") or "").strip().lower()
            if email and email not in people:
                people[email] = row
    return people


def selection(work_dir, wanted, client, cap=True):
    """The accounts `batch1_build` would put in these cohorts tomorrow.

    Returns `(by_cohort, held, subjects)`. `by_cohort` maps a cohort name to
    the DOMAINS it carries, in the same order `batch1_build` walks emails so
    the cap falls on the same rows; `subjects` maps a domain to the company
    name and the contacts a pack can be aimed with.
    """
    from src import clientapproval as ca
    stage = os.path.join(work_dir, "stage")
    icp = {}
    for row in _jsonl(os.path.join(stage, "s3-icp.jsonl")):
        icp[str(row.get("domain", "")).lower()] = row
    rendered = {}
    for row in _jsonl(os.path.join(stage, "s7-copy.jsonl")):
        if row.get("state") == "rendered":
            rendered[str(row.get("email", "")).lower()] = (
                row.get("variables") or {})
    people = source_people(work_dir)

    by_cohort, held = collections.OrderedDict(), collections.Counter()
    picked = collections.defaultdict(list)
    for email in sorted(rendered):
        domain = email.split("@")[-1].lower()
        country = (icp.get(domain) or {}).get("country") or "unknown"
        cohort = cohort_of(country, wanted)
        if cohort is None:
            held["not in %s: %s" % ("/".join(wanted), country)] += 1
            continue
        if not ca.is_approved(domain, client):
            held["client approval not approved"] += 1
            continue
        picked[cohort].append((email, domain))

    subjects = {}
    for cohort in wanted:
        entries = picked.get(cohort, [])
        ceiling = (COHORTS[cohort]["campaigns"] * PER_CAMPAIGN if cap
                   else len(entries))
        kept = []
        for email, domain in entries[:ceiling]:
            person = people.get(email) or {}
            subject = subjects.get(domain)
            if subject is None:
                subject = subjects[domain] = {
                    "domain": domain,
                    # The COMPANY NAME is what `open_roles` is aimed with,
                    # and the domain is not one. A record that falls back to
                    # its domain here would search LinkedIn jobs for
                    # "acme.test", which is not a company name and is
                    # exactly the shape that returns somebody else.
                    "company": (person.get("Company") or "").strip() or None,
                    "cohort": cohort,
                    "contacts": [],
                }
                kept.append(domain)
            subject["contacts"].append({
                "email": email,
                "persona": rendered[email].get("persona"),
                "linkedin": (person.get("Url") or "").strip() or None,
                "primary": len(subject["contacts"]) == 0,
                "name": " ".join(x for x in
                                 [(person.get("First Name") or "").strip(),
                                  (person.get("Last Name") or "").strip()]
                                 if x),
            })
        by_cohort[cohort] = kept
        if len(entries) > ceiling:
            held["over the %s cohort cap of %d" % (cohort, ceiling)] += (
                len(entries) - ceiling)
    return by_cohort, held, subjects


def contact_url(subject, persona):
    """That persona's LinkedIn profile, through `linkedin.canonical`.

    Seven of the estate's stored values are a bare vanity name and the rest
    carry locale hosts and tracking parameters, so the raw field is refused
    by `apify.check_url` for having no scheme - correctly. The fix is to
    canonicalise the input, never to teach the guard to accept a schemeless
    string.
    """
    from src import linkedin
    wanted = PERSONAS[persona]
    rows = [c for c in (subject.get("contacts") or [])
            if c.get("linkedin") and (c.get("persona") or "") == wanted]
    rows.sort(key=lambda c: (not c.get("primary"), str(c.get("name") or "")))
    for row in rows:
        url = linkedin.canonical(row["linkedin"])
        if url:
            return url
    return None


def monthly_usage_usd():
    """What Apify says this billing cycle has cost: the invoice's own number."""
    from src.providers import apify, key, query, request
    status, data = request("GET", query(apify.BASE + "/users/me/usage/monthly",
                                        {"token": key(apify.KEY_VAR)}))
    body = (data or {}).get("data") or {}
    return float(body.get("totalUsageCreditsUsdAfterVolumeDiscount") or 0.0)


def measuring_runner(observed):
    """The production lifecycle, plus the run id the cost report needs.

    `pack._live_runner` returns rows and nothing else, which is right for
    production. The billed figure lives on the RUN, and reconstructing it
    from item counts would be the planned number wearing a different hat.
    """
    from src.providers import apify
    from src.researchpack import pack

    def runner(actor, payload, limit):
        started = pack._start(actor, payload)
        finished = apify.wait_for(started["id"]) or {}
        dataset = finished.get("dataset_id") or started.get("dataset_id")
        rows = apify.dataset_items(dataset, limit) if dataset else []
        observed.append({"actor": actor, "run_id": started["id"],
                         "status": finished.get("status"), "rows": len(rows)})
        return rows
    return runner


def billed(run_ids):
    """What each run actually cost, read back from Apify's own run record."""
    from src.providers import apify, key, query, request
    out = {}
    token = key(apify.KEY_VAR)
    for run_id in run_ids:
        status, data = request("GET", query(
            apify.BASE + "/actor-runs/" + run_id, {"token": token}))
        row = (data or {}).get("data") or {}
        out[run_id] = {"usd": float(row.get("usageTotalUsd") or 0.0),
                       "status": row.get("status"),
                       "events": row.get("chargedEventCounts") or {}}
    return out


def coverage(packs):
    """Per source: addressable, covered, and what covered MEANS.

    "Addressable" = the pack could aim the source at all. "Covered" = it
    came away with at least one usable fact of that source's kind. A run
    that succeeded and returned nothing is not coverage, and neither is a
    site that answered and said too little.
    """
    n = len(packs) or 1
    out = collections.OrderedDict()
    for source in SOURCES:
        kind = KIND_OF[source]
        subject = source.split(":")[1] if ":" in source else None
        addressable = covered = 0
        for built in packs:
            if source in built.get("unaddressable", {}):
                continue
            addressable += 1
            hits = [f for f in built["facts"]
                    if f["kind"] == kind
                    and (subject is None or f.get("subject") == subject)]
            covered += 1 if hits else 0
        out[source] = {"addressable": addressable, "covered": covered,
                       "of_all": covered / float(n),
                       "of_addressable": (covered / float(addressable)
                                          if addressable else None),
                       "billed_by": "apify" if source in PAID else "local_http"}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=os.path.join(ROOT, "work"),
                        help="the work/ directory holding the real queue, "
                             "stage files and spend ledger")
    parser.add_argument("--cohort", default="uk,eu",
                        help="comma separated: uk, eu, us")
    parser.add_argument("--client", default="productive")
    parser.add_argument("--accounts", type=int, default=0,
                        help="0 means the whole cohort")
    parser.add_argument("--budget-usd", type=float, default=2.00,
                        help="the walk STOPS on this. It cannot raise a "
                             "declared ceiling and does not try to")
    parser.add_argument("--no-cap", action="store_true",
                        help="ignore the `campaigns x 45` cohort cap and take "
                             "every approved rendered lead in these cohorts. "
                             "For a FREE pass - see --sources - where the cap "
                             "is about how many a campaign can carry rather "
                             "than about what may be read")
    parser.add_argument("--sources", default=None,
                        help="comma separated subset of %s. `site_content` "
                             "alone is the free pass: it starts no Apify run, "
                             "writes no ledger row and cannot reach a ceiling"
                             % ",".join(
                                 ("open_roles", "company_posts",
                                  "person_posts", "site_content")))
    parser.add_argument("--resolve-slug", action="store_true",
                        help="after the jobs run fails to yield a slug, ask "
                             "harvestapi/linkedin-company for it")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--env", default=None,
                        help="the config/.env holding APIFY_TOKEN. A worktree "
                             "has none of its own and the credential is never "
                             "copied into one - `providers.load_env` only ever "
                             "setdefaults, and a real env var still wins. The "
                             "VALUE is never printed by anything here")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    work_dir = point_at(args.work)
    wanted = [c.strip() for c in args.cohort.split(",") if c.strip()]
    for name in wanted:
        if name not in COHORTS:
            parser.error("unknown cohort %r" % name)

    from src import clients, spendledger, store                  # noqa: E402
    from src import researchpack                                 # noqa: E402
    from src.providers import load_env                           # noqa: E402
    from src.researchpack import actors                          # noqa: E402
    from src.researchpack import cache as rpcache                # noqa: E402

    # THIS RUN'S OWN CACHE, and never the shared one. A cache warmed by one
    # lane is a call another lane believes it made, and the pilot's cache is
    # quarantined as PRE-FIX-DO-NOT-SERVE for exactly that reason.
    os.environ.setdefault(rpcache.CACHE_VAR, os.path.join(
        work_dir, "researchpack-cohort-%s-cache.json" % "-".join(wanted)))

    config = clients.load(args.client)
    caps = spendledger.caps(config)
    today = spendledger.today()
    committed = spendledger.spent(args.client, day=today)

    sources = tuple(x.strip() for x in args.sources.split(",")
                    if x.strip()) if args.sources else None
    by_cohort, held, subjects = selection(work_dir, wanted, args.client,
                                          cap=not args.no_cap)
    domains = [d for cohort in wanted for d in by_cohort.get(cohort, [])]
    if args.accounts:
        domains = domains[:args.accounts]
    # AN ACCOUNT WITH NO COMPANY NAME CANNOT REACH THE JOBS ACTOR, and the
    # jobs actor is the only source of the LinkedIn slug. It is reported
    # rather than dropped silently: it is a gap in the supplier list, not a
    # property of the account.
    nameless = [d for d in domains if not subjects[d]["company"]]
    chosen = [subjects[d] for d in domains]

    print("research packs for tomorrow's cohort")
    print("  work            %s" % work_dir)
    print("  queue           %s" % store.queue_path())
    print("  spend ledger    %s" % spendledger.path())
    print("  pack cache      %s" % rpcache.path())
    print("  cohorts         %s" % ", ".join(wanted))
    for cohort in wanted:
        print("    %-4s %3d account(s), cap %d"
              % (cohort, len(by_cohort.get(cohort, [])),
                 COHORTS[cohort]["campaigns"] * PER_CAMPAIGN))
    for reason, count in held.most_common():
        print("    held  %-44s %d" % (reason[:44], count))
    print("  accounts        %d selected; %d carry a company name, %d do not"
          % (len(domains), len(chosen) - len(nameless), len(nameless)))
    with_champion = sum(1 for s_ in chosen if contact_url(s_, "champion"))
    with_exec = sum(1 for s_ in chosen if contact_url(s_, "exec"))
    print("  addressable     champion profile %d, exec profile %d"
          % (with_champion, with_exec))

    print("\nthe ceilings, READ BEFORE ANYTHING IS BOUGHT")
    for scope in spendledger.SCOPES:
        limit = caps.get(scope)
        print("  %-24s %s" % (scope, "UNLIMITED - none declared"
                              if limit is None else limit))
    print("  committed today          %d credit(s) on %s" % (committed, today))
    headroom = (None if caps.get("per_day") is None
                else caps["per_day"] - committed)
    print("  headroom under per_day   %s"
          % ("unbounded" if headroom is None else headroom))

    per_account_cents = actors.cost_of(["open_roles", "company_posts",
                                        "person_posts", "person_posts"]
                                       + (["company_slug"]
                                          if args.resolve_slug else []))
    per_account_usd = (sum(actors.usd_per_account(n) for n in
                           ("open_roles", "company_posts"))
                       + 2 * actors.usd_per_account("person_posts")
                       + (actors.usd_per_account("company_slug")
                          if args.resolve_slug else 0.0))
    print("\nwhat a cold account plans to cost, at every source's own limit")
    for name, spec in actors.ACTORS.items():
        print("  %-14s %-38s $%.5f  %2d credit(s)"
              % (name, spec["actor"], actors.usd_per_account(name),
                 actors.planned_cost(name)))
    for name, spec in actors.FREE_SOURCES.items():
        print("  %-14s %-38s $%.5f   0 credit(s)  (ours)"
              % (name, spec["provider"], spec["usd_per_account"]))
    print("  %-14s %-38s $%.5f  %2d credit(s)"
          % ("PER ACCOUNT", "worst case, nothing cached",
             per_account_usd, per_account_cents))
    print("  %-14s %-38s $%.5f  %2d credit(s)"
          % ("x %d" % len(chosen), "if every source is addressable",
             per_account_usd * len(chosen), per_account_cents * len(chosen)))
    if headroom is not None and per_account_cents * len(chosen) > headroom:
        print("  NOTE: the worst case exceeds today's headroom. The walk will "
              "halt on the ceiling rather than raise it.")

    if not args.live:
        print("\nnot live: nothing was started, nothing was read and nothing "
              "was charged.")
        return 0

    load_env(args.env) if args.env else load_env()
    before = monthly_usage_usd()
    print("\napify monthly usage before: $%.4f" % before)

    observed, packs, halted = [], [], None
    started = time.time()
    for i, subject in enumerate(chosen, 1):
        if observed:
            charged = sum(c["usd"] for c in
                          billed([r["run_id"] for r in observed]).values())
            if charged >= args.budget_usd:
                halted = ("budget", "observed $%.4f reached --budget-usd "
                          "$%.2f at account %d" % (charged, args.budget_usd, i))
                print("STOPPING: %s" % halted[1])
                break
        mark = len(observed)
        domain = str(subject["domain"])
        try:
            built = researchpack.build(
                domain, live=True, client=args.client, config=config,
                company=subject.get("company"),
                champion=contact_url(subject, "champion"),
                exec_profile=contact_url(subject, "exec"),
                resolve_slug=args.resolve_slug, sources=sources,
                runner=measuring_runner(observed))
        except spendledger.BudgetExceeded as refusal:
            # HALTED, NOT WIDENED. The ceiling is the operator's number and
            # raising it is the operator's call; a walk that steps over one
            # has turned a control into a suggestion.
            halted = ("ceiling", str(refusal))
            print("HALTED on a declared ceiling at account %d (%s): %s"
                  % (i, domain, refusal))
            break
        built["runs"] = [r["run_id"] for r in observed[mark:]]
        built["company"] = subject.get("company")
        built["cohort"] = subject.get("cohort")
        packs.append(built)
        print("  %3d/%d %-32s facts=%-3d bought=%-24s free=%-12s "
              "unaddressable=%s"
              % (i, len(chosen), domain[:32], built["fact_count"],
                 ",".join(built["bought"]) or "-",
                 ",".join(built["free"]) or "-",
                 ",".join(sorted(built["unaddressable"])) or "-"))

    # Events settle a moment after a run ends. A charge read too early reads
    # as the actor start alone, which is how a per-event actor looks free.
    if observed:
        time.sleep(10)
    charges = billed([r["run_id"] for r in observed])
    for row in observed:
        charges[row["run_id"]]["actor"] = row["actor"]
        charges[row["run_id"]]["rows"] = row["rows"]
    after = monthly_usage_usd()

    per_actor = collections.Counter()
    runs_per_actor = collections.Counter()
    for entry in charges.values():
        per_actor[entry.get("actor", "?")] += entry["usd"]
        runs_per_actor[entry.get("actor", "?")] += 1
    total_usd = sum(entry["usd"] for entry in charges.values())

    site_stats = [b.get("site") or {} for b in packs if b.get("site")]
    summary = {
        "at": store.now(),
        "client": args.client,
        "cohorts": wanted,
        "accounts_selected": len(domains),
        "accounts_built": len(packs),
        "halted": halted,
        "coverage": coverage(packs),
        "observed_usd_total": round(total_usd, 6),
        "observed_usd_per_account": round(total_usd / float(len(packs) or 1), 6),
        "per_actor_usd": {a: round(v, 6) for a, v in per_actor.items()},
        "runs_per_actor": dict(runs_per_actor),
        "monthly_usage_before": before,
        "monthly_usage_after": after,
        "monthly_usage_delta": round(after - before, 6),
        "site_requests": sum(int((s.get("stats") or {}).get("requests") or 0)
                             for s in site_stats),
        "site_seconds": round(sum(float((s.get("stats") or {}).get("seconds")
                                        or 0.0) for s in site_stats), 1),
        "site_outcomes": dict(collections.Counter(
            s.get("outcome") for s in site_stats)),
        "slug_source": dict(collections.Counter(
            b.get("slug_source") or "none" for b in packs)),
        "ledger_credits_this_run": sum(b["cost"] for b in packs),
        "ledger_committed_before": committed,
        "ledger_committed_after": spendledger.spent(args.client, day=today),
        "caps": caps,
        "seconds": round(time.time() - started, 1),
    }

    out = args.out or os.path.join(
        work_dir, "researchpack-cohort-%s-%s.json"
        % ("-".join(wanted), time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "packs": packs, "charges": charges},
                  handle, indent=1, default=str, ensure_ascii=False)

    print("\ncoverage per source, over %d account(s)" % len(packs))
    for source, row in summary["coverage"].items():
        print("  %-24s %-10s %2d addressable, %2d covered  %5.1f%% of all"
              % (source, row["billed_by"], row["addressable"], row["covered"],
                 100.0 * row["of_all"]))
    print("\nwhere the company LinkedIn slug came from")
    for where, count in sorted(summary["slug_source"].items(),
                               key=lambda kv: -kv[1]):
        print("  %-24s %3d" % (where, count))
    # "%d requests" and not the plural in brackets:
    # `tests/test_nothing_writes_to_a_provider.DYNAMIC` strips docstrings and
    # comments before matching but not ordinary strings, so the literal
    # `request(s` inside a print reads as a call whose verb is decided at
    # runtime and the whole file is reported as an undeclared HTTP write.
    # The guard is right to be blunt about a verb it cannot read; the cheap
    # side of that trade is here, not in the guard.
    print("\nour own crawler: %d requests, %.1fs, %s"
          % (summary["site_requests"], summary["site_seconds"],
             summary["site_outcomes"]))
    print("\nobserved apify spend, from the run records")
    for actor, usd in sorted(per_actor.items()):
        print("  %-44s %3d run(s)  $%.5f"
              % (actor, runs_per_actor[actor], usd))
    print("  %-44s %3d run(s)  $%.5f"
          % ("TOTAL", len(charges), summary["observed_usd_total"]))
    print("  %-44s           $%.5f"
          % ("per account", summary["observed_usd_per_account"]))
    print("  %-44s           $%.5f"
          % ("apify monthly-usage delta", summary["monthly_usage_delta"]))
    print("\nthe ledger")
    print("  credits committed by this run   %d" % summary["ledger_credits_this_run"])
    print("  %s committed today: %d -> %d (per_day %s)"
          % (args.client, committed, summary["ledger_committed_after"],
             caps.get("per_day")))
    if halted:
        print("\nHALTED (%s): %s" % halted)
    print("\nwrote %s  (work/ is gitignored and these rows name real "
          "prospects)" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
