#!/usr/bin/env python3
"""Public-web research, and the reasons it is allowed to happen.

Evidence order, and nothing skips a step: ContactOut structured data first, AI
Ark structured fallback where ContactOut is genuinely insufficient, and only
then Apify on the company's own public pages.

A scrape needs a stated need. "More context would be useful" is not one. The
only reasons this module accepts are the ones a downstream step actually
blocked on.

  python -m src.research --plan
  python -m src.research --plan --id meridian
"""
import argparse
import datetime
import json
import logging
import os

from . import clients, events, evidence as ev, store
from .providers import ProviderError, apify

log = logging.getLogger(__name__)

# Why public evidence is genuinely required. A scrape with any other reason is
# refused rather than run.
NEED_HOOK_EVIDENCE = "public_evidence_required_for_hook"
NEED_ANGLE_EVIDENCE = "public_evidence_required_for_angle"
NEED_REBRAND_EVIDENCE = "public_evidence_required_for_rebrand"
NEED_ICP_EVIDENCE = "public_evidence_required_for_icp_dimensions"
NEED_REFRESH = "public_evidence_stale_refresh_required"

# ------------------------------------------ company-level crawl cache (pass-scoped)
#
# One crawl per company per pass, reused across every contact on that company.
# TASK-162 fixed the analogous waste in what gets sent into prompts - 66.7% of
# the company context on a 3-contact record was a duplicate of itself, at
# roughly 2.5 contacts per domain. The crawl itself gets the same treatment.
#
# Pass-scoped in-memory layer: cleared at the start of each `enrich.run()`
# pass. Evidence must not age out mid-pass or persist across passes pretending
# to be current. The persisted layer underneath answers only when entries are
# still fresh by the per-field TTL, which is what makes carrying them across
# passes legitimate.
_crawl_cache = {}
_persisted_cache = None  # loaded lazily, None means "not yet loaded"
_dirty = False           # has anything been added since the last flush?


def crawl_cache_path():
    """Path obtained from `store`, never spelled here."""
    return os.path.abspath(
        os.environ.get("CRAWL_CACHE")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "crawl-cache.json"))


def load_crawl_cache():
    """Load the persisted crawl cache from disk.

    A corrupt or unparseable file is a cache MISS and a warning, never an
    exception and never a silently empty dict that looks like a cold start.
    """
    global _persisted_cache
    path = crawl_cache_path()
    if not os.path.exists(path):
        _persisted_cache = {}
        return _persisted_cache
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("crawl cache: file is not a dict, treating as miss")
            _persisted_cache = {}
            return _persisted_cache
        _persisted_cache = data
        return _persisted_cache
    except (OSError, ValueError, json.JSONDecodeError) as e:
        log.warning("crawl cache: corrupt file (%s), treating as miss", e)
        _persisted_cache = {}
        return _persisted_cache


def save_crawl_cache(cache):
    """Persist the crawl cache to disk. Atomic write following mx pattern."""
    path = crawl_cache_path()
    store.refuse_production_write(path)
    with store.lock(for_path=path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    return cache


def _fresh_entries(entries, today=None):
    """Filter entries by per-field freshness. Returns only fresh ones."""
    today = today or datetime.datetime.now(datetime.timezone.utc)
    fresh = []
    for entry in entries:
        age = age_of(entry, today)
        if age is None:
            continue
        if age <= ttl_for(entry.get("field")):
            fresh.append(entry)
    return fresh


def crawl_cache_get(domain, today=None):
    """Cached crawl result for this domain, or None.

    Checks the in-memory layer first. On miss, checks the persisted layer
    filtered by per-field freshness. Does NOT populate the in-memory layer
    from the persisted one - the persisted layer answers directly so that
    stale entries never enter the pass-scoped layer.
    """
    mem = _crawl_cache.get(domain)
    if mem is not None:
        return mem
    persisted = _persisted_cache if _persisted_cache is not None else load_crawl_cache()
    entries = persisted.get(domain)
    if not entries:
        return None
    fresh = _fresh_entries(entries, today)
    if not fresh:
        return None
    return fresh


def crawl_cache_set(domain, evidence):
    """Store a crawl result for reuse across contacts on this company.

    Writes to both the in-memory pass-scoped layer and the persisted layer.
    """
    global _dirty
    _crawl_cache[domain] = evidence
    persisted = (_persisted_cache if _persisted_cache is not None
                 else load_crawl_cache())
    persisted[domain] = evidence
    _dirty = True
    # DELIBERATELY NOT SAVED HERE. An earlier version called
    # `save_crawl_cache` on every set, which rewrites the WHOLE cache file
    # once per domain - so a pass over N domains performs N full-file writes
    # of a file that grows to N entries. That is the same O(N^2) shape as the
    # queue's whole-file checkpoint, reintroduced in a new file, and at 5,000
    # domains it is the dominant cost of the run rather than a saving.
    #
    # `mx` already solves this and is the pattern the brief named: `enrich.run`
    # loads the cache once at the start and saves it once at the end. This
    # follows it. `flush_crawl_cache` is the save.


def crawl_cache_clear():
    """Clear the pass-scoped in-memory crawl cache.

    Does NOT destroy the persisted layer. The persisted layer answers only
    when entries are still fresh by the per-field TTL.
    """
    _crawl_cache.clear()


def flush_crawl_cache():
    """Persist the cache if anything was added. Once per pass, not per domain.

    Returns the number of domains held, or None if there was nothing to do.

    A FAILURE HERE IS A WARNING AND NOT A CRASH, with one exception that is
    deliberately allowed through: `ProductionStateUnderTest`. Swallowing that
    one would turn the barrier that stops a test writing into the real `work/`
    directory into a log line nobody reads, which is the opposite of what a
    barrier is for. Everything else - a full disk, a permission error - costs
    a re-crawl next pass and must not lose the run.
    """
    global _dirty
    if not _dirty or _persisted_cache is None:
        return None
    try:
        save_crawl_cache(_persisted_cache)
    except store.ProductionStateUnderTest:
        raise
    except Exception as exc:                        # noqa: BLE001 - classified
        log.warning("crawl cache: failed to persist (%s), continuing", exc)
        return None
    _dirty = False
    return len(_persisted_cache)


def _reset_persisted_cache():
    """Reset the persisted cache global. Tests only."""
    global _persisted_cache, _dirty
    _persisted_cache = None
    _dirty = False

# -------------------------------------------------------------- evidence TTL

# A hiring post from last week is not the same kind of fact as "this company
# builds software for agencies". One expires in days, the other in months.
# A single global TTL is wrong for every fact at once, so the shelf life comes
# from the evidence row's own `field` - the same field `for_prompt` already
# reads and passes to the prompt.

SHORT_LIVED_FIELDS = frozenset((
    "team", "careers", "hiring", "jobs", "news", "announcements", "launches",
))

LONG_LIVED_DAYS = 30
SHORT_LIVED_DAYS = 3


def ttl_for(field):
    """How many days this kind of evidence is worth before a refresh."""
    if (field or "") in SHORT_LIVED_FIELDS:
        return SHORT_LIVED_DAYS
    return LONG_LIVED_DAYS


def age_of(entry, today=None):
    """Days since this evidence was retrieved, computed from `retrieved_at`.

    `age_days` is NULL on every row in the estate - nothing ever wrote it.
    `retrieved_at` is always present. Reading the NULL column would make this
    function return None for every row and the TTL would refuse to fire, which
    is exactly the defect an evaluator once hit for the same reason: it read
    INSUFFICIENT_DATA forever because nothing wrote the field it read.
    """
    retrieved = entry.get("retrieved_at")
    if not retrieved:
        return None
    today = today or datetime.datetime.now(datetime.timezone.utc)
    if isinstance(today, str):
        today = datetime.datetime.fromisoformat(today)
    if isinstance(today, datetime.datetime):
        today_date = today.date()
    else:
        today_date = today
    try:
        retrieved_dt = datetime.datetime.fromisoformat(retrieved)
    except (ValueError, TypeError):
        return None
    return (today_date - retrieved_dt.date()).days


def stale_evidence(rec, today=None):
    """Evidence rows that have outlived their field's TTL.

    Returns the rows, not just a bool, so `why()` can say WHICH row aged out.
    A record with no `research` has no stale rows; a record whose evidence is
    all long-lived and three days old has no stale rows; a record carrying a
    `team` row from six days ago has one.
    """
    stale = []
    for entry in rec.get("research") or []:
        age = age_of(entry, today)
        if age is None:
            continue
        if age > ttl_for(entry.get("field")):
            stale.append(entry)
    return stale


class RunBudget:
    """A hard stop on how many scrapes one batch may start.

    `apify.settings` has computed `max_runs_per_batch` since it was written and
    nothing in `src/` ever read it, so the only ceilings that actually applied
    were per-run - pages, items, characters. There was no bound at all on how
    many runs a batch could start, and an Apify run bills in compute units that
    `enrich.Budget` cannot see, because `COSTS["apify-research"]` is zero. So
    the credit cap could report a batch well inside budget while it started a
    scrape for every record in the queue.

    This is that ceiling, made real. It counts starts rather than costs,
    because compute units are not a number this system is told.
    """

    def __init__(self, cap=None):
        self.cap = cap
        self.started = []
        self.refused = []

    def allow(self, record_id):
        if self.cap is not None and len(self.started) >= self.cap:
            self.refused.append(record_id)
            return False
        self.started.append(record_id)
        return True


def icp_prose_missing(rec):
    """None of the phrases the ICP model reads appear in what we hold.

    Six of the twelve ICP dimensions - resource planning, profitability,
    utilisation, time tracking, operational complexity, delivery complexity -
    match phrases against `segments.text_of`. ContactOut returns firmographics
    rather than prose, so for a company enriched from structured sources alone
    those six never score, `_confidence` lands in its LOW band, and LOW forces
    `review` however high the number is.
    """
    from . import icp, segments

    text = segments.text_of(rec)
    return not any(segments._hits(text, words)
                   for words in icp.NEED_SIGNALS.values())

REASONS = (NEED_HOOK_EVIDENCE, NEED_ANGLE_EVIDENCE, NEED_REBRAND_EVIDENCE,
           NEED_REFRESH)


def structured_evidence(rec):
    """What the structured providers already gave us."""
    facts = rec.get("company_facts") or {}
    return {k: v for k, v in facts.items()
            if k in ("name", "employees", "revenue", "founded", "industry",
                     "offices", "specialties", "notable", "stack")
            and v not in (None, "", [], {})}


def existing_evidence(rec):
    return list(rec.get("research") or [])


def why(rec, verdict=None, today=None):
    """The reason public evidence is needed, or None when it is not.

    `verdict` lets a caller supply a freshly computed ICP verdict that has NOT
    been written to the record. The ICP branch below is gated on `icp_status`,
    which the qualify stage writes AFTER the stage research runs in - so on a
    first pass the status is None and the need can never be stated. Computing
    a verdict is free; persisting one mid-enrichment is not neutral, because
    it can hold the record and stop verification. So the caller computes,
    passes it here, and lets the qualify stage own what gets stored.

    `today` pins the clock for test determinism. Production callers leave it
    None and get the wall clock.

    Structured data wins. This only fires when a step downstream has nothing to
    work with, which is the only honest reason to go and read someone's website.
    Evidence has a shelf life that depends on what it is: a team page from six
    days ago is stale, a services page from six days ago is not.
    """
    stale = stale_evidence(rec, today)
    if stale:
        return NEED_REFRESH
    if existing_evidence(rec):
        return None                               # already have it, and fresh
    facts = structured_evidence(rec)

    if rec.get("lane") == "cold" and not rec.get("hook"):
        if not facts.get("notable") and not facts.get("specialties"):
            return NEED_HOOK_EVIDENCE
    if rec.get("lane") == "domains":
        needs_angle = any(not c.get("angle") for c in rec.get("contacts") or [])
        if needs_angle and not facts.get("specialties") and not facts.get("industry"):
            return NEED_ANGLE_EVIDENCE
    mail_domain = (rec.get("company_facts") or {}).get("email_domain")
    if mail_domain and mail_domain != rec.get("domain") and not facts.get("name"):
        return NEED_REBRAND_EVIDENCE

    # The ICP dimensions that read prose, and only for a company whose verdict
    # is still open. A rejected company is a decision, not a gap, and scraping
    # it would be spending compute to re-ask a question already answered; a
    # qualified one needs nothing further. "Structured data wins" above still
    # holds for the hook and the angle - this asks a different question, about
    # evidence the structured sources do not carry at all.
    status = (verdict or
              (rec.get("qualification") or {}).get("verdict") or {}).get(
        "icp_status")
    if status in ("review", "unknown") and icp_prose_missing(rec):
        return NEED_ICP_EVIDENCE
    return None


def plan(rec, config=None, verdict=None, today=None):
    """What a run would do for this record, or why it will not happen."""
    config = config or {}
    conf = apify.settings(config)
    reason = why(rec, verdict=verdict, today=today)
    if not reason:
        return {"record": rec["id"], "planned": False,
                "why_not": "structured evidence is sufficient"}
    if not conf["enabled"]:
        return {"record": rec["id"], "planned": False, "reason": reason,
                "why_not": "apify is not enabled for this client"}
    planned = apify.plan(rec["domain"], reason, config)
    return {"record": rec["id"], "planned": True, "reason": reason, **planned}


def _from_the_site_itself(rec, config):
    """Read the company's own website. Returns retained evidence, or None.

    None means "this did not settle it" - either the site defeated a plain
    HTTP read in a way `webfetch` names, or it yielded nothing usable - and
    the caller falls through to the paid crawl. Anything else is evidence
    gathered for free, through the same boilerplate filter and the same
    events as the paid leg, so a consumer cannot tell which leg paid for a
    fact and does not need to.

    Company-level cache: one crawl per domain per pass, reused across every
    contact on that company. The cache is pass-scoped and cleared at the
    start of each `enrich.run()` pass so evidence does not age out.
    """
    from . import evidence as ev
    from . import webfetch

    domain = rec.get("domain")
    if not domain:
        return None

    cached = crawl_cache_get(domain)
    if cached is not None:
        usable = [dict(e, record_id=rec["id"]) for e in cached]
        rec.setdefault("research", []).extend(usable)
        events.record(rec, events.SCRAPE_COMPLETED, provider="webfetch",
                      operation="company_website", reason="cached",
                      items=len(usable))
        for entry in usable:
            events.record(rec, events.EVIDENCE_ADDED, provider="webfetch",
                          operation=entry.get("field"),
                          reason=entry.get("source_url"))
        store.log(rec, "research",
                  f"site read: {len(usable)} page(s) from company-level cache")
        return usable

    try:
        got = webfetch.research(domain, config)
    except Exception as e:                       # a free leg may never break a run
        events.record(rec, events.SCRAPE_FAILED, provider="webfetch",
                      operation="company_website",
                      reason=f"{type(e).__name__}: {e}"[:120])
        return None

    outcome, pages = got.get("outcome"), got.get("pages") or []
    if not pages:
        events.record(rec, events.SCRAPE_FAILED, provider="webfetch",
                      operation="company_website", reason=str(outcome))
        store.log(rec, "research",
                  f"site read: {outcome}, falling back to a paid crawl"
                  if got.get("fallback_worthy")
                  else f"site read: {outcome}, nothing usable")
        return None

    # `_page` already returns the evidence shape - `source_url`, `field`,
    # `fact`, `provider: local_http`, `content_hash`, `http_status`, `chars` -
    # and 26 records already carry `local_http` rows from an ad-hoc run, so
    # the consumers are known to read it. Only the two fields the paid leg
    # stamps afterwards are added, rather than re-mapping and losing the hash.
    usable = []
    for page in pages:
        entry = dict(page, record_id=rec["id"],
                     retrieved_at=(page.get("retrieved_at")
                                   or got.get("retrieved_at") or store.now()))
        why = ev.boilerplate(entry.get("fact"))
        if why:
            events.record(rec, events.EVIDENCE_REFUSED, provider="webfetch",
                          operation=entry.get("field"),
                          reason=f"{entry.get('source_url')}: {why}")
            continue
        usable.append(entry)

    if not usable:
        events.record(rec, events.SCRAPE_FAILED, provider="webfetch",
                      operation="company_website",
                      reason=f"{outcome}: every page was boilerplate")
        return None

    # Cache at company level for reuse across contacts on this company.
    # Stored without record_id so each consumer gets its own copy with its
    # own record_id; provenance (source_url, content_hash) and retrieved_at
    # are preserved from the original crawl.
    crawl_cache_set(domain, [dict(e, record_id=None) for e in usable])

    rec.setdefault("research", []).extend(usable)
    events.record(rec, events.SCRAPE_COMPLETED, provider="webfetch",
                  operation="company_website", reason=str(outcome),
                  items=len(usable))
    for entry in usable:
        events.record(rec, events.EVIDENCE_ADDED, provider="webfetch",
                      operation=entry.get("field"),
                      reason=entry.get("source_url"))
    
    # Record the waterfall step so the ledger sees the free leg. Without this,
    # every cost measurement that read the ledger said "webfetch: 0 rows" and
    # concluded the free crawl was not being used - when in fact it was not
    # even being attempted (option a), and even if it had been, it would have
    # written no ledger row (option c).
    from . import waterfall
    waterfall.record_step(rec, "company_information", "webfetch",
                          "webfetch-crawl",
                          reason="public_evidence_required",
                          result=f"{len(usable)} page(s) retained",
                          expected_cost=0,
                          enforce=False)
    
    store.log(rec, "research",
              f"site read: {len(usable)} page(s) retained for free")
    return usable


def run(rec, config=None, live=False, spend=None, scrape_budget=None,
        verdict=None, today=None):
    """Gather public evidence. Returns what was retained, never the raw dataset.

    `live` is a second gate on top of the client's own `enabled`: a plan is
    always free, a run is never accidental.

    `spend` is `enrich`'s ledger closure and is required for a live run. An
    actor run is real money - billed in Apify compute units rather than in
    credits, which is why its `COSTS` entry is zero, and a zero-cost call
    still has to be *recorded*. This function used to take a `budget` it
    never read: the caller passed one, the run looked bounded, and nothing
    consulted it. The spend audit therefore reported clean about a provider
    it was not watching.

    Refusing without one is deliberate. A live run whose only reachable
    caller forgot to thread the ledger through would otherwise go back to
    being invisible, and silence is the failure this guards against.
    """
    config = config or {}
    proposal = plan(rec, config, verdict=verdict, today=today)

    # THE FREE LEG WAS GATED BEHIND THE PAID PLAN, SO IT NEVER RAN.
    #
    # This function used to return here when `planned` was false, and the
    # free webfetch leg sits BELOW that return. But `plan()` sets
    # `planned: False` for two completely different situations:
    #
    #   no `reason`            research is not needed at all
    #   apify not enabled      research IS needed and the PAID crawl is off
    #
    # The second one is the normal case - `apify.settings({})["enabled"]` is
    # False unless a client asks, and `test_apify_is_disabled_unless_a_client_
    # asks` pins that. So for any client without Apify, a record that needed
    # research returned an empty list before reaching the free crawl, and the
    # comment below ("THE FREE LEG OF THE WATERFALL, WHICH NOTHING WAS
    # CALLING") stayed true after the leg was wired in, because it was wired
    # in underneath the gate.
    #
    # Measured 2026-09-16 across all 550 records: 1056 contactout waterfall
    # rows, 298 apify, 221 blitz, and ZERO webfetch. 394 records have
    # research and every one of them BOUGHT it. A free-legs run over 330
    # records changed no state at all, because with Apify refused by
    # `--cap 0` nothing substituted for it.
    #
    # So the need signal is `reason`, and the free leg is gated on that.
    # `planned` continues to gate the PAID leg, further down, exactly as
    # before.
    reason = proposal.get("reason")
    if not reason:
        events.record(rec, events.PROVIDER_CALL_SKIPPED, provider="apify",
                      operation="research", reason=proposal.get("why_not"))
        return []

    # THE FREE LEG OF THE WATERFALL, NOW IN THE EXECUTION PATH.
    #
    # `src/webfetch.py` is complete: bounded pages, bytes, redirects and
    # wall-clock, robots respected, same-domain only, and it follows the
    # site's OWN links rather than guessing `/about` and `/team` the way the
    # Apify proposal does - two of five guessed paths 404'd on the first live
    # run and the navigation text was kept as though the page were real. It
    # classifies what it could not read (`JS_RENDERING_REQUIRED`, `BLOCKED`,
    # `TIMEOUT`) instead of pretending, and `FALLBACK_WORTHY` names exactly
    # the outcomes worth paying for.
    #
    # It had ZERO callers because it sat BELOW `if not live: return []`, and
    # `live` was `live and apify.settings(config)["enabled"]`, which is False
    # unless a client asks. Measured on the Productive cohort: 103 of 300
    # records carry no research evidence at all, 88 of the 158 under the
    # headcount floor have no research text, and only 25 of the 111 size-
    # failures ever had a team or about page crawled. Crawl coverage is the
    # constraint, and this is the free half of it.
    #
    # Moved BEFORE the `live` gate because a socket costs nothing and must not
    # consume a run this client is rationing. A site this reads successfully
    # never reaches the paid leg at all. The `live` gate now stops only the
    # PAID leg, further down.
    free = _from_the_site_itself(rec, config)
    if free is not None:
        return free

    if proposal.get("planned"):
        events.record(rec, events.SCRAPE_PLANNED, provider="apify",
                      operation=proposal["actor"], reason=reason)
    if not live:
        return []

    # THE PAID LEG STARTS HERE, and it needs the plan the free leg did not.
    # Everything below was previously unreachable without `planned` because
    # the function returned at the top; now the free crawl runs first and this
    # is where the Apify gate actually belongs.
    if not proposal.get("planned"):
        events.record(rec, events.PROVIDER_CALL_SKIPPED, provider="apify",
                      operation="research", reason=proposal.get("why_not"))
        return []

    if scrape_budget is not None and not scrape_budget.allow(rec["id"]):
        events.record(rec, events.PROVIDER_CALL_SKIPPED, provider="apify",
                      operation="research",
                      reason="max_runs_per_batch reached")
        return []

    if spend is None:
        events.record(rec, events.SCRAPE_FAILED, provider="apify",
                      operation=proposal["actor"],
                      reason="no spend ledger was supplied")
        store.log(rec, "research",
                  "apify: refused, a live run needs the spend ledger")
        return []
    # Through the same door as every other paid call: this writes the
    # PLANNED event and appends the waterfall step the spend audit reads.
    #
    # It does not bound the run. `COSTS["apify-research"]` is zero because
    # this is billed in compute units rather than credits, and a zero-cost
    # charge is affordable at any cap - so what this buys is visibility,
    # not a limit. What limits it is upstream and per record: a stated
    # need from `why`, the client's own `enabled`, `live`, and
    # `max_items_per_run`. PRODUCT-GAPS.md records that the credit cap
    # does not reach compute units.
    # Two reason vocabularies, and the ledger owns one of them.
    # `why` says which downstream step blocked - hook, angle or rebrand -
    # and that is the sentence a person reads. `waterfall.require` accepts
    # only its own words, and for this stage the word is
    # `PUBLIC_EVIDENCE_REQUIRED`; passing `why`'s word raised
    # `WaterfallViolation` and took the run down with it. The specific
    # need is not lost: `SCRAPE_PLANNED` above records it, which is the
    # event that answers "why did we read this company's website".
    from .enrich import PUBLIC_EVIDENCE_REQUIRED
    if not spend("apify-research", proposal["reason"], provider="apify",
                 reason_code=PUBLIC_EVIDENCE_REQUIRED):
        return []

    conf = apify.settings(config)
    sources_by_url = {u["url"]: u["source"] for u in proposal["urls"]}
    try:
        started = apify.start_run(proposal["actor"], proposal["urls"], conf)
        # Recorded here, after the run exists, and carrying its id.
        #
        # It used to be recorded *before* the call and without the id, which
        # made it a statement of intent rather than of fact - and the id
        # then lived in a local variable and nowhere else. `wait_for` polls
        # for as long as `POLL_ATTEMPTS` allows, so a process that died in
        # there left an actor running and billing compute units with its id
        # held nowhere, an empty `rec["research"]`, and therefore the same
        # stated need next run, which started a second one. `COSTS` prices
        # this at zero because it is billed in compute units rather than
        # credits, so `--cap` could not have bounded the duplication.
        #
        # One event, not two: `events.record` dedupes on the derived id, so
        # a second SCRAPE_STARTED for the same record collapses into the
        # first and the id would have been dropped on the floor again.
        #
        # It used to live in this local variable and nowhere else, and
        # `wait_for` polls for as long as `POLL_ATTEMPTS` allows - so a
        # process that died in there left an actor running and billing
        # compute units with its id held nowhere. Nobody could reclaim it
        # or cancel it, `rec["research"]` was still empty so `why` returned
        # the same reason next run, and the next run started a *second*
        # actor. `COSTS["apify-research"]` is zero because this is billed
        # in compute units rather than credits, so `--cap` cannot bound
        # the duplication either.
        events.record(rec, events.SCRAPE_STARTED, provider="apify",
                      operation=proposal["actor"], reason=proposal["reason"],
                      run_id=started.get("id"))
        finished = apify.wait_for(started["id"])
        # A PARTIAL CRAWL IS EVIDENCE. This required SUCCEEDED, so a run the
        # actor killed at its own deadline was discarded WITH ITS DATASET ID
        # IN HAND - three of five pages already fetched, already billed, and
        # thrown away. Measured: 35 of 248 runs ended other than SUCCEEDED,
        # and the record was left with nothing, so the next batch started a
        # second actor for the same domain. 23.4% of all runs were duplicates.
        #
        # So the dataset decides, not the status. A run with a dataset is read
        # whatever its verdict, and what came back is recorded as partial so
        # nobody mistakes three pages for five.
        if not finished.get("dataset_id"):
            events.record(rec, events.SCRAPE_FAILED, provider="apify",
                          operation=proposal["actor"],
                          reason=f"run {finished['status']}")
            store.log(rec, "research", f"apify run {finished['status']}")
            return []
        items = apify.dataset_items(finished["dataset_id"], conf["max_items_per_run"])
        if finished["status"] != "SUCCEEDED":
            events.record(rec, events.SCRAPE_PARTIAL, provider="apify",
                          operation=proposal["actor"],
                          reason=f"run {finished['status']}",
                          items=len(items))
            store.log(rec, "research",
                      f"apify run {finished['status']}: kept {len(items)} "
                      f"page(s) it had already written")
    except ProviderError as e:
        events.record(rec, events.SCRAPE_FAILED, provider="apify",
                      operation=proposal["actor"], reason=str(e)[:100])
        store.log(rec, "research", f"apify failed: {e}")
        return []

    # The client's OWN configured vocabulary, which is what `relevance` is
    # documented to score against - "not from a model's opinion". At this
    # point in the pipeline there is no contact and therefore no single
    # angle, so every configured angle counts: research is company-level and
    # a page about resourcing is relevant to this client whichever persona
    # eventually reads it.
    angle_words = sorted({w for label in (config.get("angle_labels") or {}).values()
                          for w in str(label).split() if len(w) > 3})
    evidence = apify.evidence_from_items(items, rec["domain"], proposal["actor"],
                                         sources_by_url, conf,
                                         record_id=rec["id"],
                                         angle_words=angle_words)
    for entry in evidence:
        entry["retrieved_at"] = entry.get("retrieved_at") or store.now()

    # BOILERPLATE NEVER BECOMES DECISION EVIDENCE. `evidence.quality` already
    # answers UNUSABLE for it; dropping it here as well means it is not stored
    # either, so it cannot reach `segments.text_of` - which appends every
    # research fact to the text the vertical classifier reads, and did append
    # 2,488 words of a Hungarian agency's privacy and cookie policies.
    #
    # Dropped rather than stored-and-ignored because a consumer that forgets
    # to filter is the defect this whole change is about, and because keeping
    # it would mean paying to store what nothing may read. The event below
    # records that it was retrieved and refused, which is the audit trail.
    usable, refused = [], []
    for entry in evidence:
        why = ev.boilerplate(entry.get("fact"))
        (refused if why else usable).append((entry, why))
    for entry, why in refused:
        events.record(rec, events.EVIDENCE_REFUSED, provider="apify",
                      operation=entry.get("field") or "company_website",
                      reason=f"{entry.get('source_url')}: {why}")
        store.log(rec, "research", f"refused {entry.get('source_url')}: {why}")
    evidence = [entry for entry, _ in usable]
    rec.setdefault("research", []).extend(evidence)
    events.record(rec, events.SCRAPE_COMPLETED, provider="apify",
                  operation=proposal["actor"], reason=proposal["reason"],
                  items=len(evidence))
    for entry in evidence:
        events.record(rec, events.EVIDENCE_ADDED, provider="apify",
                      operation=entry["field"], reason=entry["source_url"])
    store.log(rec, "research",
              f"apify: {len(evidence)} page(s) retained for {proposal['reason']}")
    return evidence


def for_prompt(rec, limit=3, chars=800):
    """The evidence a prompt may see: attributed, trimmed, and small.

    A model is given a fact and where it came from, never a page. The fence in
    src/llm.py then marks the whole thing as data rather than instruction.

    TASK-146: used to return the first `limit` rows in stored order - no
    quality filter, no ranking. After TASK-138's refresh, new rows were
    appended AFTER stale ones, so `[:limit]` still returned the rows the
    crawl was paid to replace. Two consumers already did this correctly
    (`evidence.select` for the dossier, `generate.research_block` for the
    draft prompt); this function was the third and the one that mattered
    because it is what `context_for` calls for every step.
    """
    chosen = ev.select(rec.get("research") or [], limit=limit)
    out = []
    for entry in chosen:
        out.append({
            "field": entry.get("field"),
            "source_url": entry.get("source_url"),
            "retrieved_at": entry.get("retrieved_at"),
            "fact": (entry.get("fact") or "")[:chars],
        })
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.research")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--id")
    a = p.parse_args(argv)

    for rec in store.load():
        if a.id and rec["id"] != a.id:
            continue
        try:
            config = clients.load(rec.get("client"))
        except clients.ConfigError:
            config = {}
        proposal = plan(rec, config)
        if not proposal.get("planned"):
            print(f"{rec['id']:<20} no scrape: {proposal.get('why_not')}")
            continue
        print(f"{rec['id']:<20} scrape planned: {proposal['reason']}")
        for entry in proposal["urls"]:
            print(f"    {entry['source']:<16} {entry['url']}")
        print(f"    bounded by {proposal['cost']['bounded_by']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
