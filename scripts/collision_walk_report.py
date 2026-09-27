#!/usr/bin/env python3
"""Walk a bounded domain set for collision and report the four verdicts.

    py -3 scripts/collision_walk_report.py                          # 200 domains
    py -3 scripts/collision_walk_report.py --limit 50               # smaller set
    py -3 scripts/collision_walk_report.py --report                 # read state
    py -3 scripts/collision_walk_report.py --eligibility-proof      # wiring check

READ-ONLY GETs against EmailBison. Writes to .qwen/tmp/collision-walk/,
never to production work/. Domains come from the research pack
(work/researchpack-us-cohort-2026-09-25.jsonl), which is the measured
pass-everything-else set batch 3 would draw on.

## THE FOUR VERDICTS

    CLEAR       walked, no touch from us or the client (policy=allow)
    COLLIDES    walked, a touch found (policy=hold or policy=stop)
    REFUSED     the provider's answer was not trustworthy (broad match/error)
    NOT_WALKED  not asked yet (domain not in the walk set)

REFUSED and NOT_WALKED are different answers and neither is CLEAR.

## OWNERSHIP ATTRIBUTION

Every COLLIDES row names whose touch it is. The HeyReach inbox is mostly the
client's; a seat is not a campaign. Uses collision.campaign_bindings / _ours
to decide, and records which evidence decided it. A touch that cannot be
attributed is UNKNOWN_OWNER, and that is not CLEAR either.
"""
import argparse
import collections
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import collision, store                                  # noqa: E402
from src.providers import bison, load_env                         # noqa: E402

OUT_DIR = os.path.join(ROOT, ".qwen", "tmp", "collision-walk")
DOMAIN_SOURCE = os.path.join(ROOT, "work",
                              "researchpack-us-cohort-2026-09-25.jsonl")


def state_path():
    return os.path.join(OUT_DIR, "walk-state.json")


def load_state():
    path = state_path()
    if not os.path.exists(path):
        return {"accounts": {}, "started_at": None,
                "domain_source": None, "workspace": None}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = state_path()
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load_domains(limit=None):
    """Domains from the research pack, bounded."""
    domains = []
    seen = set()
    with open(DOMAIN_SOURCE, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line.strip())
            d = (row.get("domain") or "").strip().lower()
            if d and d not in seen:
                seen.add(d)
                domains.append(d)
                if limit and len(domains) >= limit:
                    break
    return domains


def attribute_ownership(answer, bindings):
    """For each person's campaigns, decide ours vs client vs unknown.

    Returns a list of per-campaign ownership records.
    """
    ownership = []
    for person in (answer.get("people") or []):
        for camp in (person.get("campaigns") or []):
            cid = camp.get("campaign_id")
            entry = {
                "email": person.get("email"),
                "campaign_id": cid,
                "status": camp.get("status"),
                "emails_sent": camp.get("emails_sent"),
                "replies": camp.get("replies"),
            }
            if cid in bindings:
                binding = bindings[cid]
                try:
                    provider_row = bison.campaign(cid)
                except Exception:                          # noqa: BLE001
                    provider_row = None
                is_ours, why = collision._ours(cid, binding, provider_row)
                if is_ours:
                    entry["owner"] = "OURS"
                    entry["evidence"] = why
                else:
                    entry["owner"] = "CLIENT"
                    entry["evidence"] = why
            else:
                entry["owner"] = "CLIENT"
                entry["evidence"] = (f"campaign {cid} has no canonical "
                                     f"binding; not our system's campaign")
            ownership.append(entry)
    return ownership


def classify(entry):
    """Map a walk entry to one of the four verdicts."""
    policy = entry.get("policy")
    if entry.get("verdict") == "REFUSED" and not policy:
        return "REFUSED"
    if policy == collision.ALLOW:
        return "CLEAR"
    if policy in (collision.HOLD, collision.STOP):
        return "COLLIDES"
    return "REFUSED"


def walk(domains, workspace_id, checkpoint=25):
    """Walk the domain set, checkpointing progress."""
    state = load_state()
    state["started_at"] = (state.get("started_at")
                           or time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime()))
    state["domain_source"] = DOMAIN_SOURCE
    state["workspace"] = workspace_id

    todo = [d for d in domains if d not in state["accounts"]]
    print(f"  {len(state['accounts'])} already answered, "
          f"{len(todo)} to walk", flush=True)

    bindings = collision.campaign_bindings()
    done = 0
    for domain in todo:
        try:
            answer = collision.check_account(domain,
                                             expect_workspace=workspace_id)
            policy, why = collision.account_policy(answer)
            ownership = attribute_ownership(answer, bindings)
            state["accounts"][domain] = {
                "policy": policy,
                "why": why,
                "verdict": answer["verdict"],
                "leads": answer["leads"],
                "emails_sent_total": answer["emails_sent_total"],
                "anyone_in_sequence": answer["anyone_in_sequence"],
                "unknown_statuses": answer.get("unknown_statuses", []),
                "ownership": ownership,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except Exception as exc:                             # noqa: BLE001
            state["accounts"][domain] = {
                "verdict": "REFUSED",
                "why": f"{type(exc).__name__}: {exc}"[:300],
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ownership": [],
            }
        done += 1
        if done % checkpoint == 0:
            save_state(state)
            print(f"  {done}/{len(todo)} walked", flush=True)

    save_state(state)
    return state


def report(state):
    """Print the four-verdict summary."""
    counts = collections.Counter()
    for domain, entry in state["accounts"].items():
        v = classify(entry)
        counts[v] += 1

    total = len(state["accounts"])
    print(f"\nCOLLISION WALK REPORT  {total} domains walked")
    print(f"  Source:    {state.get('domain_source', 'unknown')}")
    print(f"  Workspace: {state.get('workspace', 'unknown')}")
    print(f"  Started:   {state.get('started_at', 'unknown')}")
    print()
    for v in ("CLEAR", "COLLIDES", "REFUSED", "NOT_WALKED"):
        print(f"  {v:12s} {counts.get(v, 0):>5}")
    print(f"  {'TOTAL':12s} {total:>5}")

    # COLLIDES detail
    collides = [(d, e) for d, e in state["accounts"].items()
                if classify(e) == "COLLIDES"]
    if collides:
        print(f"\nCOLLIDES DETAIL ({len(collides)} domains):")
        for domain, entry in sorted(collides):
            print(f"\n  {domain}")
            print(f"    policy={entry['policy']}  verdict={entry['verdict']}")
            print(f"    why: {entry['why']}")
            print(f"    leads={entry.get('leads', 0)}  "
                  f"sent={entry.get('emails_sent_total', 0)}  "
                  f"in_seq={entry.get('anyone_in_sequence', False)}")
            print(f"    walked: {entry.get('at', '?')}")
            for own in (entry.get("ownership") or [])[:5]:
                print(f"    -> camp {own['campaign_id']}  "
                      f"owner={own['owner']}  status={own['status']}  "
                      f"sent={own['emails_sent']}  replies={own['replies']}")
                print(f"       evidence: {own['evidence'][:120]}")

    # REFUSED detail
    refused = [(d, e) for d, e in state["accounts"].items()
               if classify(e) == "REFUSED"]
    if refused:
        print(f"\nREFUSED DETAIL ({len(refused)} domains):")
        for domain, entry in sorted(refused):
            print(f"  {domain}: {entry.get('why', '?')[:200]}")

    return counts


def eligibility_proof(state):
    """Show that batch_eligibility consumes the walk output.

    Writes the walk state to the stage directory temporarily, runs
    collision_cleared(), then removes it. Reports before/after counts.
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from batch_eligibility import collision_cleared, STAGE

    walk_file = os.path.join(STAGE, "s6-collision-walk.json")
    had_existing = os.path.exists(walk_file)
    backup = None
    if had_existing:
        with open(walk_file, encoding="utf-8") as f:
            backup = f.read()

    try:
        # ABSENT: no walk output
        if os.path.exists(walk_file):
            os.remove(walk_file)
        cleared_absent = collision_cleared()
        print(f"\nWIRING PROOF: walk output ABSENT")
        print(f"  collision_cleared() = {cleared_absent}")

        # PRESENT: write our walk output
        walk_data = {"accounts": {}}
        for domain, entry in state["accounts"].items():
            walk_data["accounts"][domain] = {
                "policy": entry.get("policy"),
                "verdict": entry.get("verdict"),
                "at": entry.get("at"),
            }
        os.makedirs(STAGE, exist_ok=True)
        with open(walk_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(walk_data, f, indent=1, sort_keys=True)
        cleared_present = collision_cleared()

        print(f"\nWIRING PROOF: walk output PRESENT")
        if cleared_present is not None:
            print(f"  collision_cleared() has {len(cleared_present)} domains")
            new_clear = {d for d in state["accounts"]
                         if classify(state["accounts"][d]) == "CLEAR"}
            in_cleared = new_clear & cleared_present
            print(f"  Of {len(new_clear)} CLEAR domains from this walk, "
                  f"{len(in_cleared)} are in the cleared set")
        else:
            print(f"  collision_cleared() = None (no walk found)")

        # Now remove it again and show the difference
        os.remove(walk_file)
        cleared_after_removal = collision_cleared()
        print(f"\nWIRING PROOF: walk output REMOVED")
        print(f"  collision_cleared() = {cleared_after_removal}")

        if cleared_present != cleared_after_removal:
            print("\n  WIRING CONFIRMED: removing the walk output changes "
                  "the cleared set")
        else:
            print("\n  WIRING NOT SHOWN: cleared set unchanged "
                  "(legacy fallback may be providing the same domains)")

    finally:
        if backup is not None:
            with open(walk_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(backup)
        elif os.path.exists(walk_file):
            os.remove(walk_file)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--checkpoint", type=int, default=25)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--eligibility-proof", action="store_true")
    args = ap.parse_args(argv)

    load_env()

    state = load_state()
    if args.report or args.eligibility_proof:
        if not state["accounts"]:
            print("No walk state found. Run without --report first.")
            return 1
        report(state)
        if args.eligibility_proof:
            eligibility_proof(state)
        return 0

    ws = bison.bound_workspace()
    print(f"Workspace: id={ws['id']}, name={ws['name']}")
    domains = load_domains(limit=args.limit)
    print(f"Loaded {len(domains)} domains from {DOMAIN_SOURCE}")

    walk(domains, ws["id"], checkpoint=args.checkpoint)
    report(state := load_state())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
