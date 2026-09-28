#!/usr/bin/env python3
"""TEN-ACCOUNT PREP — the selection funnel, both exclusions, and the dry-run gate probe.

PREPARATION ONLY. This script performs ZERO provider writes and ZERO provider
reads. It never writes to `work/`. It answers one question:

    how many accounts, TODAY, satisfy the SAME frozen criteria the one-account
    run was held to — and if the answer is fewer than ten, exactly which gate
    stopped each one.

It invents no criterion and relaxes none. Every gate below is an existing
production authority, called by its own name:

    research.for_prompt          is there usable research at all (the "125")
    qualify.state_of             the ICP verdict, folding in a human rejection
    qualification.persona_plan   how many decision makers the tier LICENSES
    channels.email_verdict       may we write to this person today
    personas.classify            is this person a persona for this client
    campaignstrategy             which approved offer this persona selects
    sequencegate.check           the sequence-level gate, per lead

WHY A COPY OF THE STORE. `work/queue.jsonl` is read-only for this task, and a
worktree has no `work/` of its own, so every state override is pointed at a
snapshot. `--queue` is required rather than defaulted, so this script can never
silently open production.

    py -3 scripts/ten_account_prep.py --queue <snapshot>/queue.jsonl
    py -3 scripts/ten_account_prep.py --queue <snap>/queue.jsonl --gate-probe
    py -3 scripts/ten_account_prep.py --queue <snap>/queue.jsonl --json out.json
"""
import argparse
import collections
import copy
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# --------------------------------------------------------------- the ladder

#: Every gate, in the order a selection applies them. The name is the authority
#: that answers it, so a count below can never be traced to a criterion this
#: script made up.
LADDER = (
    ("total_records", "store.load"),
    ("usable_research", "research.for_prompt"),
    ("icp_qualified", "qualify.state_of == qualified"),
    ("licensed_2_plus_dms", "qualification.persona_plan.max_contacts_to_enrich >= 2"),
    ("has_2_stored_contacts", "len(rec['contacts']) >= 2"),
    ("has_2_emailable", "channels.email_verdict"),
    ("has_2_distinct_personas", "personas.classify"),
    ("not_excluded_task430", "the operator's human_review reject"),
    ("not_old_three_step_copy", "rec['cadence'] step keys != {em1,em2,em3}"),
)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _point_state_at(queue_path):
    """Every state override beside the snapshot, so nothing can reach `work/`.

    `store.STATE_OVERRIDES` is the canonical set — read rather than retyped, so
    a module added to the system cannot keep pointing at the real directory
    while everything else moves.
    """
    from src import store

    here = os.path.dirname(os.path.abspath(queue_path))
    os.environ["QUEUE"] = os.path.abspath(queue_path)
    defaults = {
        "CAMPAIGNS": "campaigns.jsonl",
        "WORKSPACES": "workspaces.jsonl",
        "SENDERS": "senders.jsonl",
        "AUDIT": "audit.jsonl",
        "ACTION_LEDGER": "action-ledger.jsonl",
        "AGENCY_DNC": "agency-dnc.jsonl",
    }
    for name in store.STATE_OVERRIDES:
        os.environ[name] = os.path.join(here, defaults.get(name, name.lower()))
    return os.environ["QUEUE"]


# ------------------------------------------------------------ the exclusions

def three_step_contacts(rec):
    """Contact keys on this record whose stored cadence is the OLD three steps.

    ISSUE-054's population. `{em1, em2, em3}` exactly — the shape that carries
    one thread and one repeated subject, and which `no_repetition/subjects` was
    the only gate refusing.
    """
    out = []
    for key, steps in (rec.get("cadence") or {}).items():
        if isinstance(steps, dict) and set(steps) == {"em1", "em2", "em3"}:
            out.append(key)
    return out


def task430_rejection(rec):
    """The operator's TASK-430 rejection on this record, or None.

    Read through `dmplan.human_review`, which is the authority, so a review
    whose fingerprint no longer matches the verdict's inputs correctly reports
    as absent rather than as a rejection that is no longer anchored.
    """
    from src import dmplan, qualify

    review = dmplan.human_review(rec) or {}
    if review.get("decision") != qualify.REJECT:
        return None
    return review


def exclusion_report(rows):
    """Both operator exclusions, PROVED against the store rather than assumed."""
    from src import qualify, research, sequencegate

    # ---- exclusion 1: the TASK-430 companies
    rejected = [r for r in rows if task430_rejection(r)]
    by_state = collections.Counter(qualify.state_of(r) for r in rejected)

    # The durability question: `human_review` is fingerprint-bound, so a fact
    # refresh can discard it. Measured on in-memory copies; nothing is written.
    survives, reverts = [], []
    for rec in rejected:
        probe = copy.deepcopy(rec)
        probe["qualification"]["inputs_fingerprint"] = "AFTER_A_FACT_REFRESH"
        (survives if qualify.state_of(probe) == "rejected" else reverts).append(
            rec.get("domain"))

    # ---- exclusion 2: the old three-step copy
    three = [(r, k) for r in rows for k in three_step_contacts(r)]
    three_states = collections.Counter(qualify.state_of(r) for r, _ in three)

    # ---- the second, independent gate: what `sequencegate` does with each word
    seq = {"emails": {"em1": "We noticed your studio runs retained engagements "
                             "and wanted to ask about resource planning."},
           "subjects": {"em1": "resource planning"}}
    facts = [{"text": "The studio runs retained monthly engagements for clients.",
              "source_url": "https://example.invalid/about"}]
    gate = {}
    for word in ("qualified", "dm_enrichment_approved", "rejected",
                 "review_required", "not_processed", "classified"):
        res = sequencegate.check(seq, facts, "resource_planning", word)
        fired = [f for f in (res.get("failures") or [])
                 if f.get("check") == "qualified"]
        gate[word] = {"passed": bool(res.get("passed")),
                      "qualified_check_fired": bool(fired),
                      "why": (fired[0]["why"] if fired else None)}

    return {
        "task430": {
            "records_carrying_the_operator_reject": len(rejected),
            "state_of": dict(by_state),
            "all_resolve_to_rejected": set(by_state) == {"rejected"},
            "in_the_usable_research_pool": sum(
                1 for r in rejected if research.for_prompt(r)),
            "durability": {
                "survives_a_fact_refresh": len(survives),
                "reverts_to_review_required": len(reverts),
                "reverting_domains": sorted(d for d in reverts if d),
            },
        },
        "issue054_old_three_step": {
            "contact_cadences": len(three),
            "records": len({r["id"] for r, _ in three}),
            "state_of": dict(three_states),
            "any_qualified": three_states.get("qualified", 0),
        },
        "sequencegate_by_qualification": gate,
    }


# --------------------------------------------------------------- the funnel

def funnel(rows, config):
    """The ladder, counted, with the reason each account stopped."""
    from src import channels, personas, qualify, research

    counts = collections.OrderedDict((name, 0) for name, _ in LADDER)
    counts["total_records"] = len(rows)
    detail = []

    for rec in rows:
        if not research.for_prompt(rec):
            continue
        counts["usable_research"] += 1

        state = qualify.state_of(rec)
        if state != "qualified":
            continue
        counts["icp_qualified"] += 1

        plan = (rec.get("qualification") or {}).get("persona_plan") or {}
        licensed = plan.get("max_contacts_to_enrich") or 0
        verdict = (rec.get("qualification") or {}).get("verdict") or {}

        contacts = rec.get("contacts") or []
        emailable = []
        reasons = collections.Counter()
        for contact in contacts:
            ok, why = channels.email_verdict(rec, contact, config)
            if ok:
                emailable.append(contact)
            else:
                reasons[why] += 1
        classified = sorted({personas.classify(c, config)[0]
                             for c in emailable
                             if personas.classify(c, config)[0]})

        row = {
            "id": rec.get("id"),
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "record_state": rec.get("state"),
            "icp_tier": verdict.get("icp_tier"),
            "icp_confidence": verdict.get("icp_confidence"),
            "icp_score": verdict.get("icp_score"),
            "evidence_count": len(rec.get("research") or []),
            "licensed_decision_makers": licensed,
            "stored_contacts": len(contacts),
            "emailable_contacts": len(emailable),
            "email_refusals": dict(reasons),
            "personas": classified,
            "old_three_step_contacts": len(three_step_contacts(rec)),
            "task430_rejected": bool(task430_rejection(rec)),
        }
        row["stopped_at"] = _stopped_at(row)
        detail.append(row)

        if licensed >= 2:
            counts["licensed_2_plus_dms"] += 1
        if len(contacts) >= 2:
            counts["has_2_stored_contacts"] += 1
        if len(emailable) >= 2:
            counts["has_2_emailable"] += 1
        if len(emailable) >= 2 and len(classified) >= 2:
            counts["has_2_distinct_personas"] += 1
        if not row["task430_rejected"]:
            counts["not_excluded_task430"] += 1
        if not row["old_three_step_contacts"]:
            counts["not_old_three_step_copy"] += 1

    return counts, detail


def _stopped_at(row):
    """The FIRST gate this account fails. One reason, not a list."""
    if row["task430_rejected"]:
        return "excluded: the operator's TASK-430 rejection"
    if row["old_three_step_contacts"]:
        return "excluded: carries OLD 3-STEP copy (ISSUE-054)"
    if row["licensed_decision_makers"] < 2:
        return (f"tier {row['icp_tier']} licenses only "
                f"{row['licensed_decision_makers']} decision maker")
    if row["stored_contacts"] < 2:
        return f"only {row['stored_contacts']} stored contact(s)"
    if row["emailable_contacts"] < 2:
        return f"only {row['emailable_contacts']} email-contactable contact(s)"
    if len(row["personas"]) < 2:
        return f"only one persona among the contactable: {row['personas']}"
    return None


# ------------------------------------------------- the offer each persona picks

def offer_map():
    """Which APPROVED offer each productive persona selects.

    Through `campaignstrategy._offers_for_segment`, the only live importer of
    `offers.load()` — not `offers.for_campaign`, which has no production caller.
    """
    from src import campaignstrategy, offers

    # `load()` returns {offer_id: offer}, and `_offers_for_segment` returns the
    # same shape narrowed to what that persona selects — so both are walked by
    # key rather than as a list.
    loaded = offers.load()
    out = {"loaded": len(loaded),
           "approved": sorted(oid for oid, o in loaded.items()
                              if o.get("approval_status") == offers.APPROVED),
           "pending": sorted(oid for oid, o in loaded.items()
                             if o.get("approval_status") != offers.APPROVED),
           "by_persona": {}}
    for persona in ("champion", "economic_buyer"):
        picked = campaignstrategy._offers_for_segment("all", persona)
        out["by_persona"][persona] = [
            {"id": oid, "capability": o.get("capability"),
             "cta": o.get("cta")}
            for oid, o in sorted(picked.items())]
    return out


# ------------------------------------------------------- the dry-run gate probe

def gate_probe():
    """WHICH gates a dry run actually reaches — read off the module, by line.

    The operator's definition is "execute the real decision and safety path
    without provider writes". This reports which halves of that path a
    `stage(live=False)` executes and which it cannot, because a gate that does
    not run looks exactly like a gate that passed.
    """
    import inspect

    from src import bisonfactory

    src, start = inspect.getsourcelines(bisonfactory.stage)
    early = None
    for offset, line in enumerate(src):
        if line.strip() == "if not live:":
            early = start + offset
            break
    marks = {}
    for offset, line in enumerate(src):
        text = line.strip()
        for name in ("_refuse_copylint(", "_refuse_sequence_gate(",
                     "_ensure_leads(", "bison.bound_workspace()"):
            if text.startswith(name) or text.startswith("workspace = " + name):
                marks.setdefault(name.rstrip("("), start + offset)

    inside, _ = inspect.getsourcelines(bisonfactory._ensure_leads)
    live_only = [n for n in ("_refuse_colliding_leads", "killswitch.workspace_state",
                             "_refuse_bad_greetings", "_refuse_unsupported",
                             "_refuse_unvariabled_leads", "_refuse_blank_render")
                 if any(n in l for l in inside)]

    return {
        "stage_first_line": start,
        "dry_run_early_return_at": early,
        "gate_lines": marks,
        "runs_on_a_dry_run": sorted(n for n, ln in marks.items()
                                    if early and ln < early),
        "live_only_because_below_the_return": sorted(
            n for n, ln in marks.items() if early and ln > early),
        "gates_inside_ensure_leads_and_therefore_live_only": live_only,
    }


# ----------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(prog="ten_account_prep")
    p.add_argument("--queue", required=True,
                   help="path to a COPY of queue.jsonl. Required on purpose: "
                        "this script must never silently open production.")
    p.add_argument("--client", default="productive")
    p.add_argument("--gate-probe", action="store_true")
    p.add_argument("--json", dest="out")
    a = p.parse_args(argv)

    queue = _point_state_at(a.queue)
    from src import clients, providers, store

    #: A provider write or read from this script is a defect, not a risk to be
    #: managed. The transport is replaced by one that raises, so an accidental
    #: call fails loudly instead of reaching a provider.
    def _no_provider(*args, **kw):
        raise AssertionError("ten_account_prep performed a provider call; "
                             "this script is preparation and must not")

    providers.set_transport(_no_provider)

    config = clients.load(a.client)
    rows = [r for r in store.load() if r.get("client") == a.client]

    counts, detail = funnel(rows, config)
    result = {
        "task": "ten-account prep",
        "queue": queue,
        "queue_sha256": _sha256(queue),
        "queue_records": len(rows),
        "client": a.client,
        "ladder": [{"gate": n, "authority": auth, "count": counts[n]}
                   for n, auth in LADDER],
        "exclusions": exclusion_report(rows),
        "offers": offer_map(),
        "accounts": sorted(detail, key=lambda r: (
            -r["emailable_contacts"], -r["licensed_decision_makers"],
            str(r["id"]))),
        "provider_reads": 0,
        "provider_writes": 0,
    }
    if a.gate_probe:
        result["dry_run_gate_probe"] = gate_probe()

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, sort_keys=True)

    print(f"queue            {queue}")
    print(f"sha256           {result['queue_sha256']}")
    print(f"records          {result['queue_records']}")
    print()
    print("THE LADDER — every count named by the authority that answered it")
    for row in result["ladder"]:
        print(f"  {row['count']:>6}  {row['gate']:<26} {row['authority']}")
    print()
    ex = result["exclusions"]
    print("EXCLUSION 1 — the operator's TASK-430 rejections")
    t = ex["task430"]
    print(f"  records carrying it            {t['records_carrying_the_operator_reject']}")
    print(f"  qualify.state_of              {t['state_of']}")
    print(f"  all resolve to rejected       {t['all_resolve_to_rejected']}")
    print(f"  any in the research pool      {t['in_the_usable_research_pool']}")
    print(f"  survive a fact refresh        {t['durability']['survives_a_fact_refresh']}")
    print(f"  REVERT on a fact refresh      {t['durability']['reverts_to_review_required']}")
    print()
    print("EXCLUSION 2 — the OLD 3-STEP copy (ISSUE-054)")
    i = ex["issue054_old_three_step"]
    print(f"  contact cadences              {i['contact_cadences']}")
    print(f"  records                       {i['records']}")
    print(f"  qualify.state_of              {i['state_of']}")
    print(f"  any QUALIFIED                 {i['any_qualified']}")
    print()
    print("THE SECOND, INDEPENDENT GATE — sequencegate.check by qualification")
    for word, got in ex["sequencegate_by_qualification"].items():
        verdict = "PASSES" if got["passed"] else "REFUSED"
        print(f"  {word:<24} {verdict:<8} {got['why'] or ''}")
    print()
    print("OFFERS")
    print(f"  loaded {result['offers']['loaded']}  "
          f"approved {result['offers']['approved']}")
    for persona, picked in result["offers"]["by_persona"].items():
        names = ", ".join(f"{o['id']} ({o['capability']})" for o in picked)
        print(f"  {persona:<16} -> {names or 'NOTHING'}")
    if a.gate_probe:
        print()
        print("DRY-RUN GATE PROBE — what a stage(live=False) actually executes")
        g = result["dry_run_gate_probe"]
        print(f"  dry-run early return at line  {g['dry_run_early_return_at']}")
        print(f"  RUNS on a dry run             {g['runs_on_a_dry_run']}")
        print(f"  live-only (below the return)  {g['live_only_because_below_the_return']}")
        print(f"  live-only (in _ensure_leads)  "
              f"{g['gates_inside_ensure_leads_and_therefore_live_only']}")
    print()
    print(f"PROVIDER READS {result['provider_reads']}   "
          f"PROVIDER WRITES {result['provider_writes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
