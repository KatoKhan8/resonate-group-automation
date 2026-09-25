"""The batch pipeline runner: plan a file into batches, run one end to end.

    py -3 scripts/batch_pipeline.py plan    --source PATH --file SLUG [--size N]
    py -3 scripts/batch_pipeline.py run     --file SLUG --batch N [--live]
    py -3 scripts/batch_pipeline.py progress --file SLUG
    py -3 scripts/batch_pipeline.py budget  [--client SLUG]

DRY RUN IS THE DEFAULT FOR EVERY STAGE THAT SPENDS. `--live` is explicit and
it still does not reach a provider WRITE: `push` is prepared and handed to the
foreground session, which owns every enrolment and activation. Nothing in this
file mutates EmailBison or HeyReach.

## WHY THE STAGES ARE A TABLE AND NOT A CHAIN OF CALLS

`src/batchpipeline.py` holds the manifest, the denominators and the budget;
this holds the wiring to the stage implementations that already exist, because
none of them should be rewritten. Each entry says how a stage is run, what it
COSTS, and - the part that matters - HOW ITS OUTPUT IS COUNTED. A stage is
never counted from its own exit code: `stage_s3_icp.py`, `stage_mx_amended.py`,
`stage_s7_copy.py` and `batch_eligibility.py` all return 0 whether they decided
eighteen thousand domains or none, so an orchestrator that trusted the exit
code would report a clean pass over an empty input. That is this estate's
signature failure and the readback is the defence: every stage is counted by
re-reading what it wrote.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import batchpipeline as bp                             # noqa: E402
from src import clients, mx, store                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = "productive"

# The measured unit costs. Each one is a MEASUREMENT with a date, not an
# estimate, and where a number is not measured it says so rather than
# carrying a plausible default.
#
#   verification   5.17 credits per SENDABLE address / 2.00 per address ASKED
#                  (lane N, 2026-09-25: 7,182 asked -> 2,774 sendable). The
#                  planner reserves against ASKED, because that is what the
#                  ledger is charged for; 5.17 is the yield-adjusted figure
#                  and reserving against it would under-reserve by 2.6x.
#   discovery      2.81 credits per domain, and it is NOT BOUGHT for this
#                  file: every one of its 12,407 rows already carries an
#                  address, so discovery would be pure waste.
COST_PER_ADDRESS_ASKED = 2
COST_PER_SENDABLE_MEASURED = 5.17
COST_PER_DOMAIN_DISCOVERY = 2.81


def plan(args):
    """Cut a source file into homogeneous batches and write every manifest.

    Manifests for every batch are written UP FRONT, all of them `pending`, so
    `n of m` in the progress block is a fact about the file rather than a
    number that grows as work happens. A denominator that only becomes known
    once the work is done is the one thing a progress report may not have.
    """
    config = clients.load(args.client)
    rows = bp.read_source(args.source)
    summary = bp.source_summary(args.source, rows)
    print(f"source        {summary['path_basename']}")
    print(f"  contacts    {summary['rows_total']}")
    print(f"  domains     {summary['company_domains_total']} (company)")
    print(f"  addresses   {summary['addresses_total']}")
    print(f"  rows with an address  {summary['rows_with_address']}")

    batches = bp.plan_slices(rows, config, size=args.size)
    print(f"\n{len(batches)} batch(es) at <= {args.size} contacts, "
          f"homogeneous on {', '.join(bp.SLICE_DIMENSIONS)}\n")

    members_dir = os.path.join(bp.manifest_dir(args.file), "members")
    os.makedirs(members_dir, exist_ok=True)

    for spec in batches:
        members = [rows[i] for i in spec["indexes"]]
        key = bp.assert_homogeneous(members, config)     # refuses a mixed one
        denominators = bp.measure(members)

        # Membership is client data and lives beside the manifest under
        # `work/`, which is gitignored. The manifest names the file and never
        # its contents - see `new_manifest`.
        member_path = os.path.join(members_dir, f"{spec['batch']}.jsonl")
        store.refuse_production_write(member_path)
        with open(member_path, "w", encoding="utf-8", newline="\n") as fh:
            for row in members:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        manifest = bp.new_manifest(
            args.file, spec["batch"], spec["of"], key, denominators,
            args.client,
            {**summary, "members_file": os.path.basename(member_path),
             "members_are_under": "work/, gitignored, never in a tracked file"})
        manifest["budget"]["headroom_at_plan"] = bp.headroom(
            args.client, config)
        bp.save(manifest)
        print(f"  {spec['batch']:>3}/{spec['of']}  "
              f"{denominators['contacts_in_batch']:>5} contacts  "
              f"{denominators['company_domains_in_batch']:>5} domains  "
              f"{bp.slice_label(key)}")

    print(f"\nmanifests in {bp.manifest_dir(args.file)}")
    return 0


# ------------------------------------------------------------ the stages

def members_of(file_slug, n):
    path = os.path.join(bp.manifest_dir(file_slug), "members", f"{n}.jsonl")
    return bp.read_source(path)


def stage_qualification(manifest, members, config, live):
    """Every row here already carries a provider-confirmed ICP verdict.

    This file is the OUTPUT of qualification, not its input: the 12,407 rows
    are what survived the 09-07 approval snapshot and four exclusions applied
    on 2026-09-25. So the stage does not re-judge - it RE-READS the verdict
    already on the row and counts the rows that carry one, which is a
    different and cheaper claim than "we qualified them".

    A row with no provenance is not silently passed. It is not counted.
    """
    carried = [r for r in members
               if (r.get("provenance") or {}).get("approval_snapshot")]
    stamps = {(r.get("provenance") or {}).get("approval_snapshot")
              for r in carried}
    return {
        "attempted": len(members),
        "produced": len(carried),
        "counted_from": (f"provenance.approval_snapshot present on "
                         f"{len(carried)} of {len(members)} member rows; "
                         f"{len(stamps)} distinct snapshot stamp(s)"),
        "credits": 0,
        "note": "re-read, not re-judged. This file is qualification's output.",
    }


def stage_mx(manifest, members, config, live):
    """One gateway decision per EMAIL domain. DNS only, no credits.

    The denominator is email domains and not contacts, and `mx.email_domain`
    is what produces it: a gateway guards the domain of the ADDRESS, so a
    contact at one company whose mail is hosted elsewhere is answered by the
    host's decision and not their employer's.

    Counted from the MX cache after the pass, never from the pass's own
    return: that is the readback.
    """
    domains = sorted({mx.email_domain(r.get("email") or "") or ""
                      for r in members} - {""})
    cache = mx.load_cache()
    if live:
        # Threaded because it is ~1,000 DNS round trips and they are all
        # waiting on the network, not on us. `for_domain` is handed the SAME
        # cache dict by every worker, which is how a domain already resolved
        # by one worker is free for the next; CPython dict writes under the
        # GIL are atomic and the values are independent per key.
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(
                lambda d: mx.for_domain(d, config=config, cache=cache),
                domains))
        mx.save_cache(cache)
        cache = mx.load_cache()                       # re-read, not reused
    decided = [d for d in domains if d in cache]

    # THE VERDICT BREAKDOWN, NOT JUST THE COUNT. `produced` is domains that
    # reached ANY of the five outcomes, because that is what the stage does.
    # How many of them may carry email is a different question with a
    # different answer, and collapsing the two is how `dns_failure` - which
    # means we could not ask - gets read as `no_mx`, which means nobody
    # accepts mail there.
    verdicts = {}
    allowed = 0
    for domain in decided:
        decision = mx.for_domain(domain, config=config, cache=cache)
        status = decision.get("status") or "unrecorded"
        verdicts[status] = verdicts.get(status, 0) + 1
        allowed += bool(decision.get("email_cadence_allowed"))
    shape = ", ".join(f"{k} {v}" for k, v in sorted(verdicts.items()))
    return {
        "attempted": len(domains),
        "produced": len(decided),
        "counted_from": (f"{len(decided)} of {len(domains)} email domains "
                         f"present in the MX cache at {mx.cache_path()} "
                         f"after the pass; {shape or 'nothing decided'}"),
        "credits": 0,
        "note": ("DNS only, no credits. " +
                 ("live pass. " if live else
                  "DRY RUN: counted from the cache as it already stands. ") +
                 f"{allowed} of {len(decided)} decided domains permit the "
                 f"email channel (known_allowed or unknown_provider); "
                 f"dns_failure is HELD, not passed and not refused."),
    }


def stage_discovery(manifest, members, config, live):
    """NOT BOUGHT for this file, and the reason is a measurement.

    Discovery costs 2.81 credits per domain. Every row in this file already
    carries an email address - checked here rather than assumed, because
    "these are contacts, not domains" is exactly the kind of premise that is
    true of a file until the day it is not. The stage is SKIPPED, with the
    count of rows that would have needed it, and skipping is recorded as its
    own word so nobody later reads it as work that happened.
    """
    missing = [r for r in members if not (r.get("email") or "").strip()]
    would_cost = len({r.get("domain") for r in missing}) * COST_PER_DOMAIN_DISCOVERY
    return {
        "attempted": 0,
        "produced": 0,
        "status": bp.SKIPPED,
        "counted_from": (f"{len(missing)} of {len(members)} member rows carry "
                         f"no email address"),
        "credits": 0,
        "note": (f"skipped: every row already carries an address, so buying "
                 f"discovery would be waste. Had they not, this batch would "
                 f"have cost ~{would_cost:.0f} credits at 2.81/domain."),
    }


def stage_verification(manifest, members, config, live):
    """Blocked until CheapVerifier is live. Not fallen back, not skipped.

    Operator decision, 2026-09-25: stored lookup (free), then CheapVerifier,
    `invalid` dropped with no further spend, Deliverable on the rest, Reoon
    only as a third opinion. Lane Q owns the adapter and it is not finished.

    The old order - ContactOut primary, Deliverable secondary, Reoon on
    catch-all - is still wired and still works, and running it would produce a
    green stage and a real number. It is NOT run, because the operator said
    not to spend the raised ceiling on it. A stage that quietly bought the
    declined order would look identical in every report to one that bought the
    chosen one, and the money would be gone either way.
    """
    seam = bp.verification_seam()
    addresses = {(r.get("email") or "").strip().lower()
                 for r in members} - {""}
    affordable, why = (0, "not sized: the verifier is not live")
    try:
        affordable, why = bp.size_against_ledger(
            len(addresses), COST_PER_ADDRESS_ASKED, CLIENT, config)
        sizing_error = None
    except bp.LedgerNotCredible as exc:
        sizing_error = str(exc)

    if not seam["live"]:
        return {
            "attempted": 0, "produced": 0, "status": bp.BLOCKED,
            "blocked_on": "cheapverifier",
            "counted_from": None, "credits": 0,
            "note": (f"{seam['reason']}. {len(addresses)} address(es) in this "
                     f"batch are waiting. Budget sizing says "
                     f"{affordable} affordable ({why})."
                     + (f" LEDGER REFUSAL: {sizing_error}"
                        if sizing_error else "")),
        }
    if sizing_error:
        return {"attempted": 0, "produced": 0, "status": bp.BLOCKED,
                "blocked_on": "spend-ledger", "counted_from": None,
                "credits": 0, "note": sizing_error}
    if affordable <= 0:
        return {"attempted": 0, "produced": 0, "status": bp.HALTED,
                "counted_from": None, "credits": 0,
                "note": f"no room: {why}. The ceiling is not raised."}
    raise SystemExit(
        "REFUSED: the verifier reports live but this runner has not been "
        "wired to it. The seam is deliberate - lane Q owns "
        f"{bp.CHEAPVERIFIER_MODULE} and the call belongs in "
        "scripts/stage_s5_verify.py, which already reserves before it asks "
        "and holds itself to the declared per_run. Wire it there, not here.")


def stage_packs(manifest, members, config, live):
    """Free crawl first; Apify only where the crawl found nothing.

    THE CACHE KEY IS NOT THE DOMAIN. `researchpack.cache.key_for` builds
    `<domain>::<profile>`, and the union cache built today is keyed that way -
    6,667 entries, every one of them profile `site_content`. A lookup on the
    bare domain matches NOTHING: measured against this file it returns 0
    covered domains where 6,186 are in fact covered, and a packs stage that
    believed it would re-crawl every one of them. So the cache is indexed by
    its entries' own `domain` field, which is the only reading that survives a
    key format change.

    Counted from the index after the pass, per DOMAIN, because a pack is a
    property of a company and not of a person.
    """
    index = load_union_index(args_union_cache())
    domains = sorted({bp._normalise(r.get("domain")) for r in members} - {""})
    covered = [d for d in domains if index.get(d)]
    facts = sum(index.get(d, 0) for d in domains)
    return {
        "attempted": len(domains),
        "produced": len(covered),
        "counted_from": (f"{len(covered)} of {len(domains)} company domains "
                         f"carry a cached pack with at least one fact "
                         f"({facts} facts in total), indexed by each entry's "
                         f"own `domain` field rather than by the cache key"),
        "credits": 0,
        "apify_runs": 0,
        "apify_usd": 0.0,
        "note": ("cache readback only. The free crawl and the Apify actors "
                 "are not run here: crawling is free but slow and Apify "
                 "costs dollars, so both are run by their own stage once the "
                 "batch is past verification and the survivors are known - "
                 "packing a row that verification will drop is waste."),
    }


def _union_cache_path():
    return os.environ.get("UNION_PACK_CACHE") or ""


def args_union_cache():
    return _union_cache_path()


def load_union_index(path):
    """domain -> fact count, from a union cache keyed `<domain>::<profile>`."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    index = {}
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        domain = bp._normalise(entry.get("domain") or key.split("::", 1)[0])
        index[domain] = index.get(domain, 0) + len(entry.get("facts") or [])
    return index


def stage_render(manifest, members, config, live):
    """Not run before verification. A draft for an unverified address is waste.

    CLAUDE.md: no email is generated for an unverified address. The
    denominator is `contacts_verified`, which is zero until verification runs,
    and `record_stage` refuses a percentage against an unknown denominator -
    so this cannot be reported as 0% of anything until there is something to
    be a percentage of.
    """
    return {"attempted": 0, "produced": 0, "status": bp.BLOCKED,
            "blocked_on": "verification", "counted_from": None, "credits": 0,
            "note": "no copy is generated for an unverified address"}


def stage_lint(manifest, members, config, live):
    return {"attempted": 0, "produced": 0, "status": bp.BLOCKED,
            "blocked_on": "render", "counted_from": None, "credits": 0,
            "note": "nothing rendered to lint. The empty-render gate is a "
                    "FULL SWEEP of the rendered rows, never a sample - it "
                    "caught 31% of a batch with no subject and no body today."}


def stage_cohort(manifest, members, config, live):
    return {"attempted": 0, "produced": 0, "status": bp.BLOCKED,
            "blocked_on": "lint", "counted_from": None, "credits": 0,
            "note": "the slice is already homogeneous on geo, industry group "
                    "and persona, so it maps to one cohort campaign; the row "
                    "is written once lint has said who is in it."}


def stage_push(manifest, members, config, live):
    """Prepared, never performed. The foreground session owns provider writes.

    `src/providerwrites.report()` reports the write layer SEALED, and
    `scripts/batch1_push.py` additionally refuses `--live` without either a
    `--veto-closed` time already past or the operator's verbatim
    `--veto-waived` words. Five samples and a 15-minute veto come before any
    push, every batch, every time.
    """
    return {"attempted": 0, "produced": 0, "status": bp.BLOCKED,
            "blocked_on": "foreground-session",
            "counted_from": None, "credits": 0,
            "note": "prepared only. This runner performs no provider write; "
                    "push, enrolment and activation belong to the foreground "
                    "session, after five samples and a 15-minute veto."}


STAGE_RUNNERS = {
    bp.QUALIFY: stage_qualification,
    bp.MX: stage_mx,
    bp.DISCOVERY: stage_discovery,
    bp.VERIFY: stage_verification,
    bp.PACKS: stage_packs,
    bp.RENDER: stage_render,
    bp.LINT: stage_lint,
    bp.COHORT: stage_cohort,
    bp.PUSH: stage_push,
}


def run(args):
    config = clients.load(args.client)
    manifest = bp.load(args.file, args.batch)
    members = members_of(args.file, args.batch)

    if len(members) != manifest["denominators"]["contacts_in_batch"]:
        raise SystemExit(
            f"REFUSED: the members file holds {len(members)} rows and the "
            f"manifest says {manifest['denominators']['contacts_in_batch']}. "
            f"One of them is stale and a count taken now would be wrong.")
    # The homogeneity claim is re-proved against the rows, not trusted from
    # the manifest that asserted it.
    bp.assert_homogeneous(members, config)

    print(f"batch {manifest['batch']} of {manifest['of']}  "
          f"{manifest['slice']['label']}")
    print(f"  {'live' if args.live else 'DRY RUN'}\n")

    for stage in bp.STAGES:
        started = store.now()
        result = STAGE_RUNNERS[stage](manifest, members, config, args.live)
        status = result.pop("status", bp.DONE)
        attempted, produced = result.get("attempted", 0), result.get("produced", 0)
        if status == bp.DONE and attempted and not produced:
            status = bp.EMPTY
        entry = bp.record_stage(manifest, stage, status,
                                started_at=started, ended_at=store.now(),
                                **result)
        pct = entry["percent_of_denominator"]
        shown = f"{pct:>5.1f}%" if pct is not None else "    -"
        print(f"  {stage:<14} {status:<8} {entry['produced']:>6} / "
              f"{entry['denominator_value']:>6} {shown}  "
              f"of {entry['denominator']}")
        if entry["note"]:
            print(f"                 {entry['note']}")
    bp.save(manifest)
    print(f"\nmanifest {bp.manifest_path(args.file, args.batch)}")
    return 0


def progress(args):
    config = clients.load(args.client)
    block = bp.progress(args.file, config=config, client=args.client)
    if args.json:
        print(json.dumps(block, indent=1))
        return 0
    print(render_progress(block))
    return 0


def render_progress(block):
    """The two-hourly progress block, in words, from the manifests."""
    if not block.get("stages"):
        return block.get("note", "no manifests")
    out = [f"FILE {block['file']}   as of {block['as_of']}",
           f"  batch {block['batch']['latest_started']} of "
           f"{block['batch']['of']}"
           f"   ({block['batch']['batches_started']} started, "
           f"{block['batch']['batches_complete']} complete, "
           f"{block['batch']['manifests_written']} planned)",
           f"  source: {block['source']['rows_total']} "
           f"{block['source']['rows_are']}",
           f"          {block['source']['company_domains_total']} company "
           f"domains", "", "  STAGE          THROUGH / DENOMINATOR"]
    for stage, s in block["stages"].items():
        pct = s["percent_of_denominator"]
        shown = f"{pct:>5.1f}%" if pct is not None else "    -"
        flags = []
        if s["batches_empty"]:
            flags.append(f"{s['batches_empty']} EMPTY")
        if s["batches_blocked"]:
            flags.append(f"{s['batches_blocked']} blocked")
        if s["batches_halted"]:
            flags.append(f"{s['batches_halted']} halted")
        out.append(f"  {stage:<14} {s['produced']:>6} / "
                   f"{s['denominator_total_across_batches']:>6} {shown}  "
                   f"{s['denominator']}"
                   + (f"   [{', '.join(flags)}]" if flags else ""))
    leads = block["leads"]
    out += ["", "  LEADS",
            f"    verified        {leads['verified']}",
            f"    packed domains  {leads['packed_domains']}",
            f"    rendered        {leads['rendered']}",
            f"    pushed          {_pc(leads['pushed_provider_confirmed'])}",
            f"    sent            {_pc(leads['sent_provider_confirmed'])}",
            f"    ({leads['note']})", "",
            f"  APIFY   {block['apify']['runs_this_batch']} run(s) this batch,"
            f" ${block['apify']['usd_this_batch']}"
            f"   |  cumulative {block['apify']['runs_cumulative']} run(s), "
            f"${block['apify']['usd_cumulative']}",
            f"  CREDITS {block['credits']['this_batch']} this batch"
            f"   |  cumulative {block['credits']['cumulative_across_manifests']}"
            " across these manifests"]
    room = block["credits"].get("headroom")
    if room:
        out.append(f"          ledger: {room['spent_total']} committed "
                   f"lifetime, {room['spent_today']} today; "
                   f"{room['binding']} binds with {room['available']} left")
    eta = block["eta"]
    out += ["", "  ETA (throughput, from measured stage rates)"]
    if not eta["measurable"]:
        out.append(f"    NOT MEASURABLE - {eta['why']}")
        for stage, on in (eta.get("blocked_stages") or {}).items():
            out.append(f"      {stage} blocked on {', '.join(on)}")
    else:
        out += [f"    binding stage   {eta['binding_stage']} at "
                f"{eta['binding_rate_rows_per_hour']} rows/hour MEASURED",
                f"    rows remaining  {eta['rows_remaining']}",
                f"    finishes        {eta['finishes_at_utc']} "
                f"({eta['hours_remaining']}h)",
                f"    {eta['caveat']}"]

    fund = block["funding_eta"]
    out += ["", "  ETA (funding, from the ledger and the declared ceilings)"]
    if not fund["measurable"]:
        out.append(f"    {fund['why']}")
    else:
        covers = fund["lifetime_ceiling_covers_it"]
        out += [f"    addresses left  {fund['addresses_outstanding']} "
                f"({fund['addresses_are']})",
                f"    credits needed  {fund['credits_needed']} at "
                f"{fund['credits_per_address_asked']}/address asked",
                f"    left today      {fund['credits_left_today']}",
                f"    left lifetime   {fund['credits_left_lifetime']}",
                f"    days of budget  {fund['days_of_budget_needed']}",
                f"    lifetime covers it: "
                f"{'YES' if covers else 'NO' if covers is False else '-'}"
                f"  (margin {fund['lifetime_margin']})"]
    return "\n".join(out)


def _pc(value):
    return "not read back from the provider" if value is None else str(value)


def budget(args):
    config = clients.load(args.client)
    room = bp.headroom(args.client, config)
    print(json.dumps(room, indent=1))
    try:
        bp.require_credible_ledger(args.client, config)
        print("\nledger: credible (carries history for this client)")
    except bp.LedgerNotCredible as exc:
        print(f"\nLEDGER NOT CREDIBLE\n{exc}")
        return 1
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 scripts/batch_pipeline.py")
    p.add_argument("--client", default=CLIENT)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("plan")
    a.add_argument("--source", required=True)
    a.add_argument("--file", required=True, help="the file slug")
    a.add_argument("--size", type=int, default=1000)
    a.set_defaults(fn=plan)

    b = sub.add_parser("run")
    b.add_argument("--file", required=True)
    b.add_argument("--batch", type=int, required=True)
    b.add_argument("--live", action="store_true")
    b.set_defaults(fn=run)

    c = sub.add_parser("progress")
    c.add_argument("--file", required=True)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=progress)

    d = sub.add_parser("budget")
    d.set_defaults(fn=budget)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
