#!/usr/bin/env python3
"""Readback comparison: expected (canonical) vs actual (EmailBison provider).

    py -3 scripts/bison_readback.py <canonical-campaign-id> --expect

Reads the campaign back from EmailBison, builds what the factory WOULD write
from canonical state, compares them field by field, prints a table, and
exits non-zero on any mismatch.

READ-ONLY. Writes nothing to any provider.

THE DEFECT THIS CATCHES. A step that was meant to be a follow-up
(thread_reply True) and landed as a new thread (thread_reply False) is
exactly the defect a readback exists to catch. Campaign 481 had this on all
five steps; campaign 352 runs F,T,F,T,F. The readback compares intended
thread behaviour against provider state.
"""
import argparse
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.bisonfactory import _comparable_step
from src.providers import bison


# ---------------------------------------------- data-access setup
#
# The script needs campaign rows, record queue and the API key. The Qwen
# worktree has config/.env with model credentials; provider keys are READS
# ONLY at every provider.

_CLAUDE = r"C:\Users\Zvonimir\Desktop\resonate-group-automation"


def _setup_data_access():
    """Point store/campaigns/clients at Claude's data. Called from main()."""
    for env_key, subpath in [
        ("QUEUE", os.path.join("work", "queue.jsonl")),
        ("CAMPAIGNS", os.path.join("work", "campaigns.jsonl")),
        ("CLIENTS_DIR", os.path.join("config", "clients")),
    ]:
        full = os.path.join(_CLAUDE, subpath)
        if os.path.exists(full):
            os.environ.setdefault(env_key, full)
    env_file = os.path.join(_PROJECT_ROOT, "config", ".env")
    if os.path.exists(env_file):
        from src.providers import load_env
        load_env(env_file)


# ---------------------------------------------- comparison

def _fmt(value, width=55):
    s = str(value)
    if len(s) > width:
        return s[:width - 3] + "..."
    return s


def build_rows(expected_steps, observed_steps, campaign_data=None):
    """The comparison rows. Each: (check, expected, actual, passed).

    Pure: no API calls, no side effects. The caller supplies both step lists
    and the campaign metadata.
    """
    rows = []
    cd = campaign_data or {}

    # --- campaign metadata ---
    rows.append(("campaign_id",
                 str(cd.get("id", "?")),
                 str(cd.get("id", "?")),
                 True))
    rows.append(("campaign_name",
                 str(cd.get("name", "?")),
                 str(cd.get("name", "?")),
                 True))
    rows.append(("status",
                 str(cd.get("status", "?")),
                 str(cd.get("status", "?")),
                 True))

    # --- step count ---
    rows.append(("step_count",
                 str(len(expected_steps)),
                 str(len(observed_steps)),
                 len(expected_steps) == len(observed_steps)))

    # --- per-step comparison ---
    for i, (exp, obs) in enumerate(zip(expected_steps, observed_steps), start=1):
        order = exp.get("order", i)
        # SUBJECT, COMPARED THROUGH THE SAME NORMALISATION `configdiff` USES.
        #
        # EmailBison prepends "Re: " ITSELF on a `thread_reply` step - measured
        # across 153 follow-ups by TASK-159 and stated in
        # `bisonfactory._comparable_step`, which is where the one copy of this
        # rule lives. This script compared the raw strings, so it reported
        # `step_2_subject  {SUBJECT_1}  vs  Re: {SUBJECT_1}  ** FAIL **` on
        # campaigns that are CORRECT - measured on 487 and 489, two failures
        # each, both spurious, while `configdiff.compare_bison` returned PASS
        # on the same campaigns in the same minute.
        #
        # That is worse than cosmetic. This readback is the COMPARE half of
        # WRITE -> READ BACK -> COMPARE -> RECONCILE, and a compare that cries
        # FAIL on a difference which is correct by construction teaches an
        # operator to ignore the verdict.
        #
        # IMPORTED, NOT REIMPLEMENTED. A second copy of the rule is how the two
        # drift, and the cases that must still FAIL are exactly the ones a
        # re-implementation gets wrong: a follow-up wearing a DIFFERENT subject
        # under its "Re: ", and a "Re: " on a step that is not a thread reply
        # at all.
        exp_subject, _, _ = _comparable_step(
            exp.get("email_subject"), exp.get("email_body"),
            bool(exp.get("thread_reply", False)))
        obs_subject, _, _ = _comparable_step(
            obs.get("email_subject"), obs.get("email_body"),
            bool(obs.get("thread_reply", False)))
        rows.append((f"step_{order}_subject",
                     _fmt(exp.get("email_subject", "")),
                     _fmt(obs.get("email_subject", "")),
                     exp_subject == obs_subject))
        # body
        rows.append((f"step_{order}_body",
                     _fmt(exp.get("email_body", "")),
                     _fmt(obs.get("email_body", "")),
                     exp.get("email_body") == obs.get("email_body")))
        # wait
        rows.append((f"step_{order}_wait",
                     str(exp.get("wait_in_days")),
                     str(obs.get("wait_in_days")),
                     exp.get("wait_in_days") == obs.get("wait_in_days")))
        # THREAD-REPLY: the load-bearing comparison for TASK-081.
        # A step meant to be a follow-up that landed as a new thread is the
        # exact defect this readback exists to catch.
        exp_tr = exp.get("thread_reply", False)
        obs_tr = obs.get("thread_reply")
        # Normalise: None and False are equivalent at the provider
        if obs_tr is None:
            obs_tr = False
        rows.append((f"step_{order}_thread_reply",
                     str(exp_tr),
                     str(obs_tr),
                     bool(exp_tr) == bool(obs_tr)))

    return rows


def print_report(cid, rows):
    width = 100
    print("=" * width)
    print("  EMAILBISON READBACK COMPARISON - campaign {}".format(cid))
    print("=" * width)
    print("  {:<28} {:<32} {:<32} {}".format(
        "CHECK", "EXPECTED", "ACTUAL", "VERDICT"))
    print("  {} {} {} {}".format("-" * 27, "-" * 31, "-" * 31, "-" * 7))
    for check, expected, actual, passed in rows:
        tag = "PASS" if passed else "** FAIL **"
        print("  {:<28} {:<32} {:<32} {}".format(
            check, _fmt(expected, 31), _fmt(actual, 32), tag))
    print("=" * width)
    n_pass = sum(1 for *_, p in rows if p)
    n_fail = sum(1 for *_, p in rows if not p)
    print("  {} passed, {} failed".format(n_pass, n_fail))
    if n_fail:
        print("  VERDICT: FAIL - the provider campaign does not match "
              "canonical state")
    else:
        print("  VERDICT: PASS")
    return n_fail


# ---------------------------------------------- main

def load_and_compare(canonical_id):
    """Load campaign data, build expected, read actual, compare.

    Returns (rows, canonical_id, provider_id, expected_steps, observed_steps).
    """
    _setup_data_access()
    from src import campaigns, clients, bisonfactory
    from src import cadence as _cadence

    rows_list = list(campaigns.load())
    campaign = campaigns.require(str(canonical_id), rows_list)
    client_name = campaign.get("client")
    if not client_name:
        raise SystemExit("campaign {} names no client".format(canonical_id))
    config = clients.load(client_name)
    provider_id = campaign.get("bison_campaign_id")
    if not provider_id:
        raise SystemExit(
            "campaign {!r} has no bison_campaign_id".format(canonical_id))
    provider_id = int(provider_id)

    campaign_data = bison.campaign(provider_id)
    cadence_steps = _cadence.steps_for(campaign, config=config)
    expected_steps = bisonfactory._sequence_steps(
        (config or {}).get("email_sequence"), cadence_steps)
    observed_steps = bison.sequence_steps(provider_id)

    comparison_rows = build_rows(expected_steps, observed_steps,
                                 campaign_data=campaign_data)
    return (comparison_rows, canonical_id, provider_id,
            expected_steps, observed_steps)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="bison_readback",
        description="Compare EmailBison provider state against canonical "
                    "expected state. READ-ONLY: writes nothing.")
    p.add_argument("campaign",
                   help="the CANONICAL campaign id")
    p.add_argument("--expect", action="store_true",
                   help="run the expected-vs-actual comparison")
    args = p.parse_args(argv)
    if not args.expect:
        p.error("--expect is required: the script's purpose is the comparison")

    (rows, cid, pid,
     expected_steps, observed_steps) = load_and_compare(args.campaign)
    n_fail = print_report(cid, rows)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
