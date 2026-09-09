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

from . import clients, events, store
from .providers import ProviderError, apify

# Why public evidence is genuinely required. A scrape with any other reason is
# refused rather than run.
NEED_HOOK_EVIDENCE = "public_evidence_required_for_hook"
NEED_ANGLE_EVIDENCE = "public_evidence_required_for_angle"
NEED_REBRAND_EVIDENCE = "public_evidence_required_for_rebrand"
NEED_ICP_EVIDENCE = "public_evidence_required_for_icp_dimensions"


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

REASONS = (NEED_HOOK_EVIDENCE, NEED_ANGLE_EVIDENCE, NEED_REBRAND_EVIDENCE)


def structured_evidence(rec):
    """What the structured providers already gave us."""
    facts = rec.get("company_facts") or {}
    return {k: v for k, v in facts.items()
            if k in ("name", "employees", "revenue", "founded", "industry",
                     "offices", "specialties", "notable", "stack")
            and v not in (None, "", [], {})}


def existing_evidence(rec):
    return list(rec.get("research") or [])


def why(rec):
    """The reason public evidence is needed, or None when it is not.

    Structured data wins. This only fires when a step downstream has nothing to
    work with, which is the only honest reason to go and read someone's website.
    """
    if existing_evidence(rec):
        return None                               # already have it
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
    status = ((rec.get("qualification") or {}).get("verdict") or {}).get(
        "icp_status")
    if status in ("review", "unknown") and icp_prose_missing(rec):
        return NEED_ICP_EVIDENCE
    return None


def plan(rec, config=None):
    """What a run would do for this record, or why it will not happen."""
    config = config or {}
    conf = apify.settings(config)
    reason = why(rec)
    if not reason:
        return {"record": rec["id"], "planned": False,
                "why_not": "structured evidence is sufficient"}
    if not conf["enabled"]:
        return {"record": rec["id"], "planned": False, "reason": reason,
                "why_not": "apify is not enabled for this client"}
    planned = apify.plan(rec["domain"], reason, config)
    return {"record": rec["id"], "planned": True, "reason": reason, **planned}


def run(rec, config=None, live=False, spend=None, scrape_budget=None):
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
    proposal = plan(rec, config)
    if not proposal.get("planned"):
        events.record(rec, events.PROVIDER_CALL_SKIPPED, provider="apify",
                      operation="research", reason=proposal.get("why_not"))
        return []

    events.record(rec, events.SCRAPE_PLANNED, provider="apify",
                  operation=proposal["actor"], reason=proposal["reason"])
    if not live:
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
        if finished["status"] != "SUCCEEDED" or not finished.get("dataset_id"):
            events.record(rec, events.SCRAPE_FAILED, provider="apify",
                          operation=proposal["actor"],
                          reason=f"run {finished['status']}")
            store.log(rec, "research", f"apify run {finished['status']}")
            return []
        items = apify.dataset_items(finished["dataset_id"], conf["max_items_per_run"])
    except ProviderError as e:
        events.record(rec, events.SCRAPE_FAILED, provider="apify",
                      operation=proposal["actor"], reason=str(e)[:100])
        store.log(rec, "research", f"apify failed: {e}")
        return []

    evidence = apify.evidence_from_items(items, rec["domain"], proposal["actor"],
                                         sources_by_url, conf)
    for entry in evidence:
        entry["record_id"] = rec["id"]
        entry["retrieved_at"] = entry.get("retrieved_at") or store.now()
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
    """
    out = []
    for entry in existing_evidence(rec)[:limit]:
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
