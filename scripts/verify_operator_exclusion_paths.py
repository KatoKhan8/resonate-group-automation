#!/usr/bin/env python3
"""PROVE the permanent operator exclusion at every path, on REAL records.

A passing unit test is not proof. This runs the ten production paths capable
of moving an account toward outreach against records read from a real queue,
names the function that refuses at each one, and shows it refusing. It then
runs the critical negative control: one of the 25 companies the CLASSIFIER
called `review`, before and after a fact refresh that genuinely moves
`qualification.inputs_fingerprint`.

READ-ONLY AGAINST THE STORE. It loads records from `$QUEUE` and mutates them
in memory only; nothing is saved, no provider is called, no credit is spent,
and the exclusion register is never written. Point `$QUEUE` at a copy.

  QUEUE=<copy of work/queue.jsonl> \
    py -3 scripts/verify_operator_exclusion_paths.py \
      --verdicts work/TASK-430-icp-verdicts-2026-09-27.json
"""
import argparse
import copy
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (campaigns, channels, clients, dmplan, eligibility, enrich,
                 operatorexclusion as oe, qualify, refresh, revival, run as
                 runner, sequencegate, sequenceplan, store)  # noqa: E402

RESULTS = []


def check(path_no, path_name, function, condition, detail):
    RESULTS.append({"path": path_no, "name": path_name, "function": function,
                    "refused": bool(condition), "detail": str(detail)[:300]})
    flag = "REFUSED" if condition else "*** DID NOT REFUSE ***"
    print(f"  {path_no:>2}. {path_name:<34} {function}")
    print(f"      {flag}: {str(detail)[:200]}")


def load(queue_path, wanted_ids):
    out = {}
    with open(queue_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("id") in wanted_ids:
                out[rec["id"]] = rec
    return out


def a_contact(rec):
    """Any contact on the record, or a synthetic one with an address.

    A company that did not qualify consumes zero person credits by policy, so
    several of the 32 carry no contact at all. The channel verdicts are about
    a person, so one is supplied - and the exclusion must refuse it, which is
    the whole point: the account is excluded, not one known mailbox.
    """
    for contact in rec.get("contacts") or []:
        if contact.get("email"):
            return contact, False
    return ({"key": "probe-contact", "name": "Probe Person",
             "first_name": "Probe", "email": f"probe@{rec.get('domain')}",
             "linkedin": "https://www.linkedin.com/in/probe-person/",
             "sendable": True, "selected": True}, True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verdicts", required=True)
    p.add_argument("--json")
    a = p.parse_args(argv)

    queue_path = store.queue_path()
    print(f"QUEUE                 {queue_path}")
    print(f"register              {oe.path()}")
    register_before = hashlib.sha256(
        open(oe.path(), "rb").read()).hexdigest()
    print(f"register sha256       {register_before}")
    report = oe.audit()
    print(f"register active       {report['active']}   "
          f"fingerprint {report['active_set_fingerprint']}")

    audit = json.load(open(a.verdicts, encoding="utf-8"))["companies"]
    the32 = {d: r for d, r in audit.items() if r.get("icp_status") != "qualified"}
    review_only = {d: r for d, r in the32.items()
                   if r.get("icp_status") == "review"}
    ids = {}
    for domain, row in the32.items():
        for rid in row.get("record_ids") or []:
            ids[rid] = domain
    recs = load(queue_path, set(ids))
    print(f"the 32                {len(the32)}  "
          f"(review {len(review_only)}, rejected {len(the32) - len(review_only)})")
    print(f"records loaded        {len(recs)}")

    # Every one of the 32 must be seen by the register. If the register and
    # the audit disagree about even one account, nothing below is meaningful.
    index = oe.resolve()
    unseen = [rid for rid, rec in recs.items() if not oe.blocks(rec, index)]
    print(f"records the register  {len(recs) - len(unseen)} of {len(recs)} blocked"
          + (f"  UNSEEN: {unseen}" if unseen else ""))
    if unseen:
        print("REFUSING TO CONTINUE: the register does not cover every account")
        return 2

    # THE SUBJECT. One of the 25 the classifier called `review` - the case the
    # operator singled out, because for these the classifier must go on saying
    # `review` and the prohibition must hold anyway.
    subject_domain = sorted(review_only)[0]
    subject_id = (review_only[subject_domain].get("record_ids") or [None])[0]
    rec = copy.deepcopy(recs[subject_id])
    config = {}
    try:
        config = clients.load(rec.get("client"))
    except Exception:
        config = {}

    print()
    print("=" * 72)
    print(f"SUBJECT  record_id={subject_id}  classifier verdict="
          f"{((rec.get('qualification') or {}).get('verdict') or {}).get('icp_status')!r}")
    print("=" * 72)
    contact, synthetic = a_contact(rec)
    print(f"  contact: {'synthetic (the record carries none)' if synthetic else 'on the record'}")

    # A CONTROL ACCOUNT. Identical shape, a domain the register has never
    # heard of. Every check below is also run against it, because a gate that
    # refuses everything proves nothing about this exclusion.
    control = copy.deepcopy(rec)
    control["id"] = "control-not-excluded"
    control["domain"] = "control-account-not-excluded.test"
    control_contact = dict(contact)
    control_contact["email"] = "probe@control-account-not-excluded.test"

    print()
    print("THE TEN PATHS, each with the real function that refuses:")
    print()

    # 1 -------------------------------------------------- qualification
    state = qualify.state_of(rec)
    check(1, "qualification / enrolment", "qualify.state_of",
          state == dmplan.OPERATOR_EXCLUDED, f"returned {state!r}")

    # 2 ----------------------------------------------- person enrichment
    verdict = (rec.get("qualification") or {}).get("verdict") or {}
    allowed, why = dmplan.may_enrich({}, [], rec, verdict, config)
    check(2, "person enrichment", "dmplan.may_enrich",
          not allowed, why)
    p_allowed, p_state = enrich.person_level_allowed(rec)
    check(2, "person enrichment (spend path)", "enrich.person_level_allowed",
          not p_allowed, f"allowed={p_allowed} state={p_state!r}")

    # 3 ------------------------------------------------- email eligibility
    ok, reason = channels.email_verdict(rec, contact, config)
    check(3, "email eligibility", "channels.email_verdict",
          (not ok) and reason == channels.OPERATOR_EXCLUDED,
          f"({ok}, {reason!r})")

    # 4 ---------------------------------------------- linkedin eligibility
    ok, reason = channels.linkedin_verdict(rec, contact, config)
    check(4, "LinkedIn eligibility", "channels.linkedin_verdict",
          (not ok) and reason == channels.OPERATOR_EXCLUDED,
          f"({ok}, {reason!r})")

    # 5 ------------------------------------------------- campaign planning
    reasons = eligibility.must_not_contact(rec, contact, config=config)
    check(5, "campaign planning / send gate", "eligibility.must_not_contact",
          reasons[0] == eligibility.BLOCKED_OPERATOR_EXCLUDED,
          f"first reason {reasons[0]!r}")
    fake_campaign = {"campaign_id": "probe", "client": rec.get("client"),
                     "record_ids": [rec.get("id")]}
    ok, detail = campaigns.check_no_operator_excluded_accounts(
        fake_campaign, [rec], config)
    check(5, "campaign launch blocker",
          "campaigns.check_no_operator_excluded_accounts", not ok, detail)
    decided = eligibility.decide(
        rec, contact, "em1", channel="email", config=config,
        step={"channel": "email", "day": 1, "subject": "s", "body": "b"})
    check(5, "the send-step decision", "eligibility.decide",
          decided.get("verdict") == eligibility.BLOCKED
          and decided.get("reason") == eligibility.BLOCKED_OPERATOR_EXCLUDED,
          f"{decided.get('verdict')} / {decided.get('reason')}")

    # 6 ------------------------------- SequencePlan / provider projection
    try:
        sequenceplan.new(rec.get("client"), {"company": rec.get("company"),
                                             "domain": rec.get("domain")}, [])
        check(6, "SequencePlan (build)", "sequenceplan.new", False,
              "returned a plan")
    except sequenceplan.PlanRefused as refusal:
        check(6, "SequencePlan (build)", "sequenceplan.new", True, refusal)
    stale_plan = {"client": rec.get("client"),
                  "account": {"company": rec.get("company"),
                              "domain": rec.get("domain")},
                  "contacts": []}
    for name, fn in (("derive_bison_payload", sequenceplan.derive_bison_payload),
                     ("derive_heyreach_payload",
                      sequenceplan.derive_heyreach_payload)):
        try:
            fn(stale_plan)
            check(6, f"provider projection ({name})", f"sequenceplan.{name}",
                  False, "produced a payload")
        except sequenceplan.PlanRefused as refusal:
            check(6, f"provider projection ({name})", f"sequenceplan.{name}",
                  True, refusal)
    gate = sequencegate.check(
        {"emails": {"em1": "a body with enough words in it to be a message"},
         "subjects": {"A": "a subject"}, "hypothesis": "a hypothesis"},
        qualification=qualify.state_of(rec))
    # `fail("qualified", ...)` is the check name `sequencegate` uses for a
    # blocking qualification. Matched exactly rather than by "any failure":
    # this gate has a dozen other checks and a sequence that failed lint
    # would otherwise read as the exclusion working.
    blocking = [f for f in gate["failures"] if f["check"] == "qualified"]
    check(6, "staging sequence gate", "sequencegate.check",
          bool(blocking) and not gate["passed"],
          blocking[0]["why"] if blocking else
          f"passed={gate['passed']} failures="
          f"{[f['check'] for f in gate['failures']]}")

    # 7 ------------------------------------------------- retry / reprocess
    assessed = revival.assess(rec, config=config)
    check(7, "retry / reprocess (revival)", "revival.assess",
          assessed["verdict"] == revival.NEVER
          and assessed["why"] == revival.OPERATOR_EXCLUDED,
          f"{assessed['verdict']}: {assessed['why']}")

    # 8 ----------------------------------------------------- fact refresh
    why = refresh.excluded(rec)
    check(8, "fact refresh", "refresh.excluded",
          why == refresh.OPERATOR_EXCLUDED, f"returned {why!r}")

    # 9 ----------------------------------------------------- requalification
    # The full path, not a simulated fingerprint move: `qualify.company`
    # rescores from the evidence and restamps `inputs_fingerprint`, which is
    # exactly what made the old prohibition evaporate.
    requalified = copy.deepcopy(rec)
    requalified.setdefault("company_facts", {})["probe_requalification"] = True
    qualify.company(requalified, config, store_result=True)
    check(9, "requalification", "qualify.state_of (after qualify.company)",
          qualify.state_of(requalified) == dmplan.OPERATOR_EXCLUDED,
          f"state {qualify.state_of(requalified)!r}; classifier verdict is "
          f"still "
          f"{((requalified.get('qualification') or {}).get('verdict') or {}).get('icp_status')!r}")
    # And the one function in the qualification path that moves a record
    # TOWARDS outreach must not release it.
    dropped = copy.deepcopy(rec)
    dropped["state"] = "dropped"
    dropped["drop_reason"] = enrich.ICP_REJECTED
    released = qualify._release_stale_icp_drop(dropped)
    check(9, "requalification (drop release)",
          "qualify._release_stale_icp_drop",
          released is None and dropped["state"] == "dropped",
          f"released={released!r} state={dropped['state']!r}")

    # 10 ----------------------------------------------------- regeneration
    marked = copy.deepcopy(rec)
    marked.setdefault("stages", {})
    outcome = runner.stage_generate([marked], model=None, spend=True, notes=[])
    stage = (marked.get("stages") or {}).get("generate") or {}
    check(10, "regeneration", "run.stage_generate",
          outcome["records"] == 0 and stage.get("status") == "refused",
          f"records={outcome['records']} stage={stage.get('status')!r} "
          f"note={stage.get('note')}")

    print()
    print("=" * 72)
    print("THE CRITICAL NEGATIVE CONTROL")
    print("=" * 72)
    fresh = copy.deepcopy(recs[subject_id])
    q = fresh.get("qualification") or {}
    fp_before = q.get("inputs_fingerprint")
    review_before = (q.get("human_review") or {}).get("inputs_fingerprint")
    verdict_before = (q.get("verdict") or {}).get("icp_status")
    print(f"  STEP 1  before the refresh")
    print(f"          classifier verdict      {verdict_before!r}")
    print(f"          inputs_fingerprint      {fp_before!r}")
    print(f"          human_review fp         {review_before!r}  "
          f"(matches: {fp_before == review_before})")
    print(f"          qualify.review_of       "
          f"{'a live review' if qualify.review_of(fresh) else 'None'}")
    print(f"          qualify.state_of        {qualify.state_of(fresh)!r}")
    print(f"          permanent exclusion     "
          f"{'BLOCK' if oe.blocks(fresh) else 'NO BLOCK'}")

    print(f"  STEP 2  change the company facts so the fingerprint MOVES")
    facts = fresh.setdefault("company_facts", {})
    facts["employees"] = int(facts.get("employees") or 0) + 777
    facts["probe_fact_added_by_the_negative_control"] = True
    recomputed = qualify._inputs_fingerprint(fresh)
    print(f"          new inputs_fingerprint  {recomputed!r}  "
          f"(moved: {recomputed != fp_before})")
    assert recomputed != fp_before, (
        "the fingerprint did not move, so this control proves nothing")

    print(f"  STEP 3  run the real fact-refresh / requalification path")
    # `qualify.company(store_result=True)` is what a requalification does: it
    # rescores, rewrites `qualification` and restamps `inputs_fingerprint`.
    qualify.company(fresh, config, store_result=True)
    q2 = fresh.get("qualification") or {}
    print(f"          classifier verdict now  "
          f"{(q2.get('verdict') or {}).get('icp_status')!r}   "
          f"(was {verdict_before!r})")
    print(f"          inputs_fingerprint now  {q2.get('inputs_fingerprint')!r}")
    print(f"          human_review fp         "
          f"{(q2.get('human_review') or {}).get('inputs_fingerprint')!r}")
    print(f"          qualify.review_of       "
          f"{'a live review' if qualify.review_of(fresh) else 'None - STALE, as designed'}")
    print(f"          qualify.stale_review_of "
          f"{'present' if qualify.stale_review_of(fresh) else 'None'}")
    print(f"          dmplan.human_review     "
          f"{'a review' if dmplan.human_review(fresh) else 'None - STALE, as designed'}")
    print(f"          qualify.state_of        {qualify.state_of(fresh)!r}")
    print(f"          permanent exclusion     "
          f"{'BLOCK' if oe.blocks(fresh) else '*** NO BLOCK ***'}")
    after = {
        "state_of": qualify.state_of(fresh),
        "email": channels.email_verdict(fresh, contact, config),
        "linkedin": channels.linkedin_verdict(fresh, contact, config),
        "must_not_contact": eligibility.must_not_contact(
            fresh, contact, config=config)[0],
        "may_enrich": dmplan.may_enrich({}, [], fresh,
                                        q2.get("verdict") or {}, config)[0],
        "refresh": refresh.excluded(fresh),
        "revival": revival.assess(fresh, config=config)["verdict"],
    }
    print()
    print("  AFTER THE REFRESH, every path re-asked:")
    for name, value in after.items():
        print(f"          {name:<20} {value!r}")
    held = (after["state_of"] == dmplan.OPERATOR_EXCLUDED
            and after["email"][1] == channels.OPERATOR_EXCLUDED
            and after["linkedin"][1] == channels.OPERATOR_EXCLUDED
            and after["must_not_contact"] == eligibility.BLOCKED_OPERATOR_EXCLUDED
            and after["may_enrich"] is False
            and after["refresh"] == refresh.OPERATOR_EXCLUDED
            and after["revival"] == revival.NEVER)
    print(f"  STEP 3 RESULT: the permanent exclusion "
          f"{'HELD at every path' if held else '*** FELL OFF ***'}")

    print()
    print("  THE INVERSE: did anything silently REMOVE the exclusion?")
    register_after = hashlib.sha256(open(oe.path(), "rb").read()).hexdigest()
    print(f"          register sha256 before  {register_before}")
    print(f"          register sha256 after   {register_after}")
    print(f"          byte-identical          {register_before == register_after}")
    still = oe.exclusion_of(fresh)
    print(f"          exclusion still active  {bool(still)}")
    print(f"          by / at unchanged       "
          f"{still.get('by')!r} / {still.get('at')!r}")

    print()
    print("=" * 72)
    print("INSPECTABILITY, on this real record after the refresh")
    print("=" * 72)
    print(json.dumps(oe.explain(fresh), indent=2, ensure_ascii=False)[:4000])

    print()
    print("  THE CONTROL ACCOUNT - the same checks against a domain the")
    print("  register has never heard of, so a gate that refuses everything")
    print("  cannot be mistaken for this exclusion working:")
    ctl = {
        "blocks": oe.blocks(control),
        "state_of": qualify.state_of(control),
        "email_reason": channels.email_verdict(control, control_contact, config)[1],
        "linkedin_reason": channels.linkedin_verdict(control, control_contact,
                                                     config)[1],
        "must_not_contact": eligibility.must_not_contact(
            control, control_contact, config=config)[0],
        "refresh": refresh.excluded(control),
        "revival_why": revival.assess(control, config=config)["why"],
    }
    for name, value in ctl.items():
        print(f"          {name:<20} {value!r}")
    control_clean = (
        ctl["blocks"] is False
        and ctl["state_of"] != dmplan.OPERATOR_EXCLUDED
        and ctl["email_reason"] != channels.OPERATOR_EXCLUDED
        and ctl["linkedin_reason"] != channels.OPERATOR_EXCLUDED
        and ctl["must_not_contact"] != eligibility.BLOCKED_OPERATOR_EXCLUDED
        and ctl["refresh"] != refresh.OPERATOR_EXCLUDED
        and ctl["revival_why"] != revival.OPERATOR_EXCLUDED)
    print(f"  CONTROL RESULT: no path attributes its refusal to the "
          f"exclusion: {control_clean}")

    print()
    print("=" * 72)
    print("ALL 32, NOT ONE. The same negative control on every account:")
    print("  refresh the facts, requalify, and re-ask four independent gates.")
    print("=" * 72)
    sweep = {"held": 0, "fell_off": [], "verdict_before": {},
             "verdict_after": {}, "state_without_the_register": {}}
    for rid in sorted(recs):
        one = copy.deepcopy(recs[rid])
        before = ((one.get("qualification") or {}).get("verdict")
                  or {}).get("icp_status")
        sweep["verdict_before"][before] = \
            sweep["verdict_before"].get(before, 0) + 1
        one.setdefault("company_facts", {})["sweep_probe"] = rid
        qualify.company(one, config, store_result=True)
        after_status = ((one.get("qualification") or {}).get("verdict")
                        or {}).get("icp_status")
        sweep["verdict_after"][after_status] = \
            sweep["verdict_after"].get(after_status, 0) + 1
        one_contact, _ = a_contact(one)
        holds = (qualify.state_of(one) == dmplan.OPERATOR_EXCLUDED
                 and channels.email_verdict(one, one_contact, config)[1]
                 == channels.OPERATOR_EXCLUDED
                 and eligibility.must_not_contact(one, one_contact,
                                                  config=config)[0]
                 == eligibility.BLOCKED_OPERATOR_EXCLUDED
                 and refresh.excluded(one) == refresh.OPERATOR_EXCLUDED)
        if holds:
            sweep["held"] += 1
        else:
            sweep["fell_off"].append(rid)
        # WHAT WOULD HAPPEN WITHOUT THE REGISTER: the measured defect, on
        # every one of the 32. `state_of` reads the register, so the only
        # honest way to ask is to ask the pre-exclusion resolver's inputs.
        q = one.get("qualification") or {}
        review = q.get("human_review")
        review_live = (review or {}).get("inputs_fingerprint") == \
            q.get("inputs_fingerprint")
        legacy = (dmplan.REJECTED if after_status == "rejected"
                  else dmplan.REJECTED if (review_live and
                                           (review or {}).get("decision")
                                           == qualify.REJECT)
                  else dmplan.REVIEW_REQUIRED if after_status in
                  ("review", "unknown") else dmplan.QUALIFIED)
        sweep["state_without_the_register"][legacy] = \
            sweep["state_without_the_register"].get(legacy, 0) + 1
    print(f"  accounts swept                          {len(recs)}")
    print(f"  classifier verdicts BEFORE the refresh  {sweep['verdict_before']}")
    print(f"  classifier verdicts AFTER  the refresh  {sweep['verdict_after']}")
    print(f"  WITHOUT the register, state would be    "
          f"{sweep['state_without_the_register']}   <- the defect")
    print(f"  WITH the register, exclusion held on    "
          f"{sweep['held']} of {len(recs)} at all four gates")
    if sweep["fell_off"]:
        print(f"  *** FELL OFF: {sweep['fell_off']}")
    all32 = sweep["held"] == len(recs)

    print()
    print("=" * 72)
    refused = [r for r in RESULTS if r["refused"]]
    print(f"PATH CHECKS: {len(refused)} of {len(RESULTS)} refused")
    for row in RESULTS:
        if not row["refused"]:
            print(f"  *** PATH {row['path']} DID NOT REFUSE: {row['function']}"
                  f" -> {row['detail']}")
    ok = (len(refused) == len(RESULTS) and held and control_clean and all32
          and register_before == register_after and bool(still))
    print(f"VERDICT: {'ALL PATHS REFUSE, CONTROL CLEAN' if ok else 'FAILED'}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"paths": RESULTS, "held_after_refresh": held,
                       "control_clean": control_clean, "sweep": sweep,
                       "register_sha256_before": register_before,
                       "register_sha256_after": register_after,
                       "subject_record_id": subject_id,
                       "subject_classifier_verdict_before": verdict_before,
                       "subject_classifier_verdict_after":
                           (q2.get("verdict") or {}).get("icp_status"),
                       "explain": oe.explain(fresh)}, fh, indent=2)
        print(f"wrote {a.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
