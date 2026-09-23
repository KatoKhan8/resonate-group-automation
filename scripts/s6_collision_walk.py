#!/usr/bin/env python3
"""Walk the client's live estate for every account batch 3 might draw on.

    py -3 scripts/s6_collision_walk.py                 # walk/resume
    py -3 scripts/s6_collision_walk.py --report        # read the state

READ-ONLY GETs against EmailBison. Writes one progress file and prints
counts. No PII beyond the account domain, which is a company rather than a
person.

## WHY THIS EXISTS

`batch_eligibility`'s collision gate reads `work/stage/batch1-candidates.json`
- the set batch 1's walk cleared - and refuses everything outside it. On
2026-09-22 that refused 5,488 verified contacts, and the refusal reason is
NOT_WALKED rather than COLLIDES. Fail-closed is right, and it is also the
whole of batch 3's supply sitting behind a walk nobody has run.

**A cleared set from an earlier batch is a cached value on a safety path.**
That is the shape of six rows in the problem register, so this re-walks rather
than re-reading, and the output carries the day it was walked.

## RESUMABLE, because the walk is thousands of provider searches

Progress is checkpointed to `work/stage/s6-collision-walk.json` after every
`--checkpoint` accounts: the verdict per domain and the point reached.
Re-running resumes and re-asks nothing it has already answered.

**A domain this refuses to answer is NOT cleared.** `collision.check_account`
refuses when the provider's response looks like a broad match rather than a
filtered one, and that refusal is carried as REFUSED, never folded into clear.
"""
import argparse
import collections
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import collision, store                                 # noqa: E402
from src.providers import bison, load_env                        # noqa: E402

#: The credential's OWN binding, asked rather than named. `expect_workspace`
#: is checked against what the token is actually bound to, and a literal here
#: would be one more hand-maintained name standing in for a registry -
#: the `CONTACTOUT_KEY` defect. `bound_workspace()` is the thing that knows.
def workspace():
    return bison.bound_workspace().get("id")


def state_path():
    return os.path.join(os.path.dirname(store.queue_path()),
                        "stage", "s6-collision-walk.json")


def load_state():
    path = state_path()
    if not os.path.exists(path):
        return {"accounts": {}, "started_at": None}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state):
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=1, sort_keys=True)
    os.replace(tmp, path)


def targets():
    """The accounts worth walking, from the measured pass-everything-else set."""
    path = os.path.join(ROOT, "work", "_s", "supply.json")
    with open(path, encoding="utf-8") as handle:
        return list(json.load(handle)["new_domains"])


def report(state):
    verdicts = collections.Counter(
        f'{entry.get("policy") or "REFUSED"} / {entry.get("verdict") or "-"}'
        for entry in state["accounts"].values())
    print(f"\nS6 COLLISION WALK  {len(state['accounts'])} accounts answered")
    for name, count in verdicts.most_common():
        print(f"    {str(name):10s} {count}")
    allowed = [d for d, e in state["accounts"].items()
               if e.get("policy") == collision.ALLOW]
    print(f"\n  CLEAR accounts: {len(allowed)}")
    return allowed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--checkpoint", type=int, default=25)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    load_env()
    ws = workspace()
    state = load_state()
    if args.report:
        report(state)
        return 0

    state["started_at"] = state.get("started_at") or time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    todo = [d for d in targets() if d not in state["accounts"]]
    if args.limit:
        todo = todo[:args.limit]
    print(f"  {len(state['accounts'])} already answered, {len(todo)} to walk",
          flush=True)

    done = 0
    for domain in todo:
        try:
            answer = collision.check_account(domain, expect_workspace=ws)
            policy, why = collision.account_policy(answer)
            state["accounts"][domain] = {
                # BOTH, because they answer different questions. `verdict`
                # says what the estate HOLDS; `policy` says what may be DONE.
                # Only ALLOW is supply; HOLD and STOP are not.
                "policy": policy,
                "why": why,
                "verdict": answer["verdict"],
                "leads": answer["leads"],
                "emails_sent_total": answer["emails_sent_total"],
                "anyone_in_sequence": answer["anyone_in_sequence"],
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except Exception as exc:                       # noqa: BLE001
            # A domain we could not ask about is REFUSED, never clear. The
            # distinction between "no history" and "we could not look" is the
            # one this whole module exists to keep.
            state["accounts"][domain] = {
                "verdict": "REFUSED",
                "why": f"{type(exc).__name__}: {exc}"[:200],
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        done += 1
        if done % args.checkpoint == 0:
            save_state(state)
            print(f"  {done}/{len(todo)} walked", flush=True)

    save_state(state)
    report(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
