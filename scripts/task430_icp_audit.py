#!/usr/bin/env python3
"""TASK-430 - ICP verdicts for the contacts in EmailBison 491-500.

READ-ONLY with respect to production. This script never calls a provider, never
calls a model, and never writes the production store. It is pointed at a COPY of
`work/` through `QUEUE` (or `--work-dir`), and the caller verifies the
production files are byte-identical before and after.

    py -3 scripts/task430_icp_audit.py --work-dir <copy> --out <json>

WHAT IT MEASURES

  1. The population: the campaigns whose `bison_campaign_id` is 491..500, the
     records they name, and the SENDABLE contacts on those records. "Sendable"
     is copied from the real staging path rather than invented:
     `bisonfactory.stage` skips a record that is missing/dropped/paused and a
     contact without `email` or without `sendable`.
  2. The account, de-duplicated by domain. Classifying one company nine times
     costs nine times as much for one answer.
  3. The ICP verdict, from `qualify.company`, which is DETERMINISTIC PYTHON -
     `segments.classify`, `icp.score`, `routing.plan`, `strategy.for_company`,
     `dmplan.for_company`. No provider, no model, no tokens, no spend.
  4. Whether the company would pass the gate the real staging path applies:
     `sequencegate.BLOCKING_QUALIFICATIONS` blocks every `qualify.state_of`
     answer but `qualified` and `dm_enrichment_approved`.

ISSUE-049 / TASK-464

`src/ingest.py` maps the client CSV's `company_employee_count` into
`company_facts["headcount"]` as a BARE STRING, while `headcount.block_of`
assumes a dict block, so `qualify.company` raises `AttributeError` on a record
the ingest itself wrote. This script does NOT fix that - `src/ingest.py` is
reserved for TASK-464. It works around it VISIBLY: every company is classified
inside a try/except that records an `error` verdict with the exception text, and
an errored company is COUNTED AND REPORTED, never skipped. A skipped company
would appear as one fewer company evaluated and would understate exactly the
number the operator asked for.
"""
import argparse
import copy
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, dmplan, providers, sequencegate, store  # noqa: E402
from src import qualify as _qualify  # noqa: E402

# ------------------------------------------------------------------------
# PROVIDER WRITES = 0, PROVIDER READS = 0, DEMONSTRATED RATHER THAN ASSERTED.
#
# The wire is replaced with a transport that RAISES. This is the same
# `providers.set_transport` seam `tests/base.py` uses for its cassette, except
# that a cassette answers and this refuses, so a call that should not happen
# fails the run loudly instead of passing quietly. Installed at import, before
# any measurement, because a guard installed afterwards proves nothing about
# what ran before it.
PROVIDER_ATTEMPTS = []


class ProviderCallAttempted(RuntimeError):
    """Something tried to reach a provider during a read-only audit."""


def _booby_trap(method, url, headers, body, timeout):
    PROVIDER_ATTEMPTS.append({"method": method, "url": str(url)[:200]})
    raise ProviderCallAttempted(
        "TASK-430 is read-only: a provider call was attempted (%s %s). "
        "Provider reads and writes must both be 0." % (method, str(url)[:200]))


providers.set_transport(_booby_trap)

CAMPAIGN_IDS = tuple(str(n) for n in range(491, 501))

#: EVENTS THAT PROVE A REAL PERSON RECEIVED SOMETHING.
#:
#: Read deliberately narrow. `touch.CONFIRMING_EVENTS` - `push_marked`,
#: `email_delivered`, `linkedin_connected` - is the canonical confirmed-touch
#: vocabulary, and it is ALSO checked, but on this population it is empty: the
#: provider's send events were never ingested into the queue. So the fallback is
#: the events that cannot happen without a delivery. A reply, an out-of-office
#: and a classified reply each require that a message arrived.
#:
#: `contact_suppressed` is NOT here. A suppression can be pre-emptive, so it is
#: counted and reported separately rather than read as proof of a send.
REACHED_EVENTS = ("reply_received", "reply_classified",
                  "positive_reply_detected", "out_of_office_recorded",
                  "referral_mentioned")

#: The states the real gate lets through. Everything else is blocked, and
#: `sequencegate._is_blocking` is asked rather than this list being trusted.
PASSING = (dmplan.QUALIFIED, dmplan.DM_APPROVED)

#: Verdict buckets the operator named. `unknown`/`review` are counted APART
#: from `rejected` because they are different answers.
QUALIFIED = "QUALIFIED"
NOT_QUALIFIED = "NOT_QUALIFIED"
HOLD_UNKNOWN = "HOLD_UNKNOWN"
ERROR = "ERROR"


def _load_provider_sent(path):
    """Per-lead send counts from a STORED provider readback, or None.

    `work/491-gate-scan.json` is a readback of EmailBison campaign 491's lead
    list taken on 2026-09-25, one row per lead with `id` (the EmailBison lead
    id) and `sent` (how many of that lead's scheduled rows the provider records
    as sent). It is the ONLY stored per-lead send evidence this repository holds
    for 491-500, and it covers 491 alone.

    Nothing here asks a provider anything. Provider reads for this task are 0.
    """
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    return {int(r["id"]): int(r.get("sent") or 0)
            for r in rows if r.get("id") is not None}


def _reached_events(rec):
    """Contact keys on this record that an event proves were reached.

    Two vocabularies, both asked. `touch.CONFIRMING_EVENTS` is canonical and is
    checked first; `REACHED_EVENTS` is the fallback for a population whose
    provider send events were never written into the queue.
    """
    from src import touch

    confirmed, implied = set(), set()
    for entry in (rec.get("events") or []):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type") or entry.get("kind")
        key = entry.get("contact")
        if kind in touch.CONFIRMING_EVENTS:
            confirmed.add(key)
        elif kind in REACHED_EVENTS:
            implied.add(key)
    return confirmed, implied


def _suppressed_contacts(rec):
    return {c.get("key") for c in (rec.get("contacts") or [])
            if c.get("suppressed") or c.get("unsubscribed") or c.get("stopped")}


def _sendable_contacts(rec):
    """The contacts the real staging path would build a lead for.

    Mirrors `bisonfactory.stage`: a record that is missing, dropped or paused
    contributes nothing, and a contact needs both an address and `sendable`.
    """
    if rec.get("drop_reason") or rec.get("paused"):
        return []
    return [c for c in (rec.get("contacts") or [])
            if c.get("email") and c.get("sendable")]


def _bucket(state, verdict):
    """The operator's four buckets, from `qualify.state_of`'s vocabulary."""
    if state == dmplan.REJECTED:
        return NOT_QUALIFIED
    if state in PASSING:
        return QUALIFIED
    # `review_required` (icp `review` or `unknown`) and `classified` both mean
    # nobody has reached a positive answer. Missing evidence is never positive
    # evidence, so they are held, not qualified - and held is not rejected.
    return HOLD_UNKNOWN


def _rejection_reasons(verdict):
    """Why this company did not qualify, as the scorer itself put it."""
    out = []
    for item in (verdict.get("classification_reasons") or []):
        if isinstance(item, dict):
            out.append(str(item.get("kind") or item.get("why") or item))
        else:
            out.append(str(item))
    for item in (verdict.get("negative_signals") or []):
        if isinstance(item, dict):
            out.append(str(item.get("kind") or item.get("why") or item))
        else:
            out.append(str(item))
    return out


def _missing_evidence(verdict):
    out = []
    for item in (verdict.get("missing_evidence") or []):
        if isinstance(item, dict):
            out.append(str(item.get("kind") or item.get("field") or item))
        else:
            out.append(str(item))
    return out


def run(work_dir=None, client="productive", provider_sent_path=None):
    if work_dir:
        store.use_directory(work_dir)
    provider_sent = _load_provider_sent(provider_sent_path)
    queue_path = store.queue_path()
    campaigns_path = store.campaigns_path()
    recs = store.read_jsonl(queue_path)
    camps = store.read_jsonl(campaigns_path)
    by_id = {r.get("id"): r for r in recs}

    try:
        config = clients.load(client)
    except Exception as exc:          # a missing client config is reportable
        config = {}
        config_error = f"{type(exc).__name__}: {exc}"
    else:
        config_error = None

    mine = [c for c in camps if str(c.get("bison_campaign_id")) in CAMPAIGN_IDS]
    mine.sort(key=lambda c: int(str(c.get("bison_campaign_id"))))

    # ---------------------------------------------------------- population
    per_campaign = []
    record_to_campaigns = defaultdict(set)
    population = {}                  # record id -> record
    for camp in mine:
        bid = str(camp.get("bison_campaign_id"))
        rids = list(camp.get("record_ids") or [])
        missing, dropped, paused, sendable_here = [], [], [], 0
        recs_here, domains_here = [], set()
        for rid in rids:
            rec = by_id.get(rid)
            if rec is None:
                missing.append(rid)
                continue
            if rec.get("drop_reason"):
                dropped.append(rid)
            if rec.get("paused"):
                paused.append(rid)
            contacts = _sendable_contacts(rec)
            if not contacts:
                continue
            sendable_here += len(contacts)
            recs_here.append(rid)
            domains_here.add((rec.get("domain") or "").strip().lower()
                             or "record:%s" % rid)
            record_to_campaigns[rid].add(bid)
            population[rid] = rec
        per_campaign.append({
            "bison_campaign_id": bid,
            "campaign_id": camp.get("campaign_id"),
            "status": camp.get("status"),
            "record_ids": len(rids),
            "records_missing_from_queue": len(missing),
            "records_dropped": len(dropped),
            "records_paused": len(paused),
            "records_with_sendable_contacts": len(recs_here),
            "sendable_contacts": sendable_here,
            "distinct_companies": len(domains_here),
        })

    # ------------------------------------------------ de-duplicate by domain
    by_domain = defaultdict(list)     # domain key -> [record ids]
    for rid, rec in population.items():
        key = (rec.get("domain") or "").strip().lower() or "record:%s" % rid
        by_domain[key].append(rid)

    # ----------------------------------------------------------- classify
    companies = {}
    for key in sorted(by_domain):
        rids = sorted(by_domain[key])
        # One record per domain is the account. Where a domain somehow carries
        # more than one record, the first by id is classified and the rest are
        # named, so the number is reproducible rather than order-dependent.
        rec = population[rids[0]]
        contacts = sum(len(_sendable_contacts(population[r])) for r in rids)
        campaign_ids = sorted({c for r in rids
                               for c in record_to_campaigns[r]},
                              key=int)
        # ------------------------------------------- was anybody here reached?
        #
        # Three independent answers, kept apart on purpose. A provider readback
        # is evidence; a reply is evidence; a suppression is not, and a campaign
        # having sent SOMETHING is not evidence about THIS contact.
        prov_sent, prov_covered, reached, suppressed = 0, 0, 0, 0
        for r in rids:
            srec = population[r]
            confirmed_keys, implied_keys = _reached_events(srec)
            supp_keys = _suppressed_contacts(srec)
            for ct in _sendable_contacts(srec):
                lid = ct.get("bison_lead_id")
                if provider_sent is not None and lid is not None \
                        and int(lid) in provider_sent:
                    prov_covered += 1
                    if provider_sent[int(lid)] > 0:
                        prov_sent += 1
                if ct.get("key") in confirmed_keys or ct.get("key") in implied_keys:
                    reached += 1
                if ct.get("key") in supp_keys:
                    suppressed += 1

        entry = {
            "domain": key,
            "record_ids": rids,
            "sendable_contacts": contacts,
            "campaign_ids": campaign_ids,
            "prior_state": _qualify.state_of(rec),
            # Contacts the STORED provider readback records at least one send
            # for, and how many of this company's contacts that readback covers
            # at all. `covered` is what stops a zero being read as "not sent".
            "provider_sent_contacts": prov_sent,
            "provider_readback_covers": prov_covered,
            # Contacts an event proves were reached: a reply, a classified
            # reply, an out-of-office, a referral. A floor, never a total.
            "reached_by_event_contacts": reached,
            # Recorded separately. A suppression is not proof of a send.
            "suppressed_contacts": suppressed,
        }
        # A DEEP COPY, so nothing this loop does can reach the store even if
        # the caller forgot to point QUEUE at a copy. `store_result=True` is
        # what writes the verdict onto the record; it writes onto the copy.
        work = copy.deepcopy(rec)
        try:
            result = _qualify.company(work, config, store_result=True)
        except Exception as exc:
            # ISSUE-049 is the expected shape of this. It is RECORDED, not
            # skipped: a skipped company would understate the answer.
            entry.update({
                "bucket": ERROR,
                "state": None,
                "icp_status": None,
                "icp_tier": None,
                "icp_score": None,
                "icp_confidence": None,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "headcount_type": type(
                    (rec.get("company_facts") or {}).get("headcount")).__name__,
                "reasons": [],
                "missing_evidence": [],
                "evidence_count": len(rec.get("research") or []),
                "facts_present": sorted(rec.get("company_facts") or {}),
            })
        else:
            verdict = result["verdict"]
            state = _qualify.state_of(work)
            entry.update({
                "bucket": _bucket(state, verdict),
                "state": state,
                "icp_status": verdict.get("icp_status"),
                "icp_tier": verdict.get("icp_tier"),
                "icp_score": verdict.get("icp_score"),
                "icp_confidence": verdict.get("icp_confidence"),
                "error": None,
                "headcount_type": type(
                    (rec.get("company_facts") or {}).get("headcount")).__name__,
                "reasons": _rejection_reasons(verdict),
                "missing_evidence": _missing_evidence(verdict),
                "evidence_count": len(rec.get("research") or []),
                "facts_present": sorted(rec.get("company_facts") or {}),
            })
        # The gate as the staging path applies it, asked rather than assumed.
        entry["blocked_by_sequencegate"] = bool(
            sequencegate._is_blocking(entry["state"])) if entry["state"] \
            else True
        entry["provenance"] = {
            "classifier": "src/qualify.py:company -> src/icp.py:score",
            "model": None,
            "deterministic": True,
            "inputs_fingerprint": (work.get("qualification") or {}).get(
                "inputs_fingerprint"),
            "facts_present": entry["facts_present"],
            "evidence_count": entry["evidence_count"],
            "client_config": client if not config_error else None,
            "at": (work.get("qualification") or {}).get("at"),
        }
        companies[key] = entry

    # ------------------------------------------------------------- totals
    buckets = Counter(e["bucket"] for e in companies.values())
    contact_buckets = Counter()
    for e in companies.values():
        contact_buckets[e["bucket"]] += e["sendable_contacts"]

    blocked = [e for e in companies.values() if e["blocked_by_sequencegate"]]
    blocked_contacts = sum(e["sendable_contacts"] for e in blocked)

    reasons = Counter()
    for e in companies.values():
        if e["bucket"] in (NOT_QUALIFIED, HOLD_UNKNOWN):
            for r in e["reasons"] or e["missing_evidence"] or ["no_reason_recorded"]:
                reasons[r] += 1
    missing_ev = Counter()
    for e in companies.values():
        for m in e["missing_evidence"]:
            missing_ev[m] += 1

    per_campaign_verdicts = {}
    for row in per_campaign:
        bid = row["bison_campaign_id"]
        b, cb = Counter(), Counter()
        blocked_c, blocked_ct, cov, snt = 0, 0, 0, 0
        for e in companies.values():
            if bid in e["campaign_ids"]:
                b[e["bucket"]] += 1
                # A company's contacts are counted per campaign from the
                # records that campaign actually names.
                here = sum(
                    len(_sendable_contacts(population[r])) for r in e["record_ids"]
                    if bid in record_to_campaigns[r])
                cb[e["bucket"]] += here
                if e["blocked_by_sequencegate"]:
                    blocked_c += 1
                    blocked_ct += here
                cov += e["provider_readback_covers"] if e["campaign_ids"] == [bid] else 0
                snt += e["provider_sent_contacts"] if e["campaign_ids"] == [bid] else 0
        per_campaign_verdicts[bid] = {
            "companies": dict(b), "contacts": dict(cb),
            "blocked_companies": blocked_c, "blocked_contacts": blocked_ct,
            "contacts_covered_by_provider_readback": cov,
            "contacts_provider_sent": snt,
        }

    return {
        "task": "TASK-430",
        "provider_call_attempts": list(PROVIDER_ATTEMPTS),
        "provider_transport": "booby-trapped: providers.set_transport raises",
        "queue_path": queue_path,
        "campaigns_path": campaigns_path,
        "client": client,
        "client_config_error": config_error,
        "campaign_ids_requested": list(CAMPAIGN_IDS),
        "campaigns_found": [r["bison_campaign_id"] for r in per_campaign],
        "per_campaign": per_campaign,
        "per_campaign_verdicts": per_campaign_verdicts,
        "totals": {
            "records_named_by_campaigns_with_duplicates":
                sum(r["record_ids"] for r in per_campaign),
            "distinct_records_named": len(
                {rid for c in mine for rid in (c.get("record_ids") or [])}),
            "records_in_population": len(population),
            "sendable_contacts": sum(r["sendable_contacts"]
                                     for r in per_campaign),
            "sendable_contacts_distinct_records": sum(
                len(_sendable_contacts(r)) for r in population.values()),
            "distinct_companies": len(companies),
        },
        "verdicts": {
            "companies": dict(buckets),
            "contacts": dict(contact_buckets),
        },
        "gate": {
            "blocked_companies": len(blocked),
            "blocked_contacts": blocked_contacts,
            "passing_companies": len(companies) - len(blocked),
            "passing_contacts": sum(e["sendable_contacts"]
                                    for e in companies.values()
                                    if not e["blocked_by_sequencegate"]),
        },
        # THE NUMBER THAT SIZES A REAL EXPOSURE rather than a gate argument:
        # of the companies and contacts that would NOT pass, how many were
        # already reached. Three independently-sourced answers, never summed.
        "exposure": {
            "provider_readback_source": provider_sent_path,
            "provider_readback_leads": (len(provider_sent)
                                        if provider_sent is not None else None),
            "blocked_contacts_covered_by_readback": sum(
                e["provider_readback_covers"] for e in blocked),
            "blocked_contacts_provider_sent": sum(
                e["provider_sent_contacts"] for e in blocked),
            "blocked_companies_provider_sent": sum(
                1 for e in blocked if e["provider_sent_contacts"]),
            "blocked_contacts_reached_by_event": sum(
                e["reached_by_event_contacts"] for e in blocked),
            "blocked_companies_reached_by_event": sum(
                1 for e in blocked if e["reached_by_event_contacts"]),
            "blocked_contacts_suppressed": sum(
                e["suppressed_contacts"] for e in blocked),
            "all_contacts_covered_by_readback": sum(
                e["provider_readback_covers"] for e in companies.values()),
            "all_contacts_provider_sent": sum(
                e["provider_sent_contacts"] for e in companies.values()),
            "all_contacts_reached_by_event": sum(
                e["reached_by_event_contacts"] for e in companies.values()),
            "all_contacts_suppressed": sum(
                e["suppressed_contacts"] for e in companies.values()),
        },
        "primary_reasons": reasons.most_common(25),
        "missing_evidence": missing_ev.most_common(25),
        "headcount_types": dict(Counter(
            e["headcount_type"] for e in companies.values())),
        "errors": [{"domain": e["domain"], "error": e["error"]}
                   for e in companies.values() if e["bucket"] == ERROR],
        "companies": companies,
    }


def record_verdicts(work_dir, client="productive"):
    """Write the verdicts through `store.py` and prove re-running is idempotent.

    Runs against a COPY. TASK-430 acceptance 2 asks for the verdicts to be
    recorded through `store.py` and for a re-run not to duplicate or silently
    change one; this exercises exactly that path - `store.transaction` ->
    `qualify.run(store_result=True)` -> `store.save` - and then runs it again to
    show the second pass REUSES every verdict instead of recomputing it, which
    is `qualify.needs_work`'s stored-fingerprint contract.

    It is deliberately NOT pointed at production. The brief for this run requires
    `work/queue.jsonl` to be byte-identical before and after, and that and a
    write-back to production cannot both be true; the conservative reading wins
    and the operator decides whether to apply them.
    """
    store.use_directory(work_dir)
    try:
        config = clients.load(client)
    except Exception:
        config = {}

    camps = store.read_jsonl(store.campaigns_path())
    mine = [c for c in camps if str(c.get("bison_campaign_id")) in CAMPAIGN_IDS]
    wanted = {rid for c in mine for rid in (c.get("record_ids") or [])}

    passes = []
    for _ in range(2):
        with store.transaction() as recs:
            subset = [r for r in recs if r.get("id") in wanted]
            before = {r.get("id"): json.dumps(
                (r.get("qualification") or {}).get("verdict"), sort_keys=True,
                default=str) for r in subset}
            result = _qualify.run(subset, client=None, config=config,
                                  store_result=True)
            after = {r.get("id"): json.dumps(
                (r.get("qualification") or {}).get("verdict"), sort_keys=True,
                default=str) for r in subset}
        changed = [rid for rid in before if before[rid] != after[rid]]
        passes.append({
            "records": len(subset),
            "processed": result["processed"],
            "reused": result["reused"],
            "verdicts_changed_this_pass": len(changed),
            "qualification_blocks_present": sum(
                1 for r in subset if r.get("qualification")),
        })
    return {"work_dir": work_dir, "passes": passes}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", help="a COPY of work/, never production")
    p.add_argument("--client", default="productive")
    p.add_argument("--provider-sent",
                   help="a STORED provider readback of per-lead send counts, "
                        "e.g. work/491-gate-scan.json. Never a live read.")
    p.add_argument("--out", help="write the full JSON here")
    p.add_argument("--record-verdicts", metavar="DIR",
                   help="exercise the store.py write path on this COPY and "
                        "report whether a second pass is idempotent")
    a = p.parse_args(argv)

    if a.record_verdicts:
        print(json.dumps(record_verdicts(a.record_verdicts, a.client),
                         indent=2, sort_keys=True, default=str))
        return 0

    result = run(a.work_dir, a.client, a.provider_sent)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True, default=str)
    slim = {k: v for k, v in result.items() if k != "companies"}
    print(json.dumps(slim, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
