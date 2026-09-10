#!/usr/bin/env python3
"""Push lint-clean output into EmailBison (email) and HeyReach (LinkedIn),
and mark the records pushed.

SENDING IS REFUSED HERE. This is the original prototype and it predates every
guard the product has. `--live` posted straight to
`campaign/AddLeadsToCampaignV2` and to EmailBison with no eligibility check,
no approval fingerprint, no killswitch, no pilot cap, no account fatigue, no
sequence check and no suppression - and then rewrote `work/queue.jsonl`
directly rather than through `src/store.py`, so the tenancy checks and the
evidence guard never saw the write either.

Nothing imports this file. It survived because it lives under `prototype/`,
which is where the product's own "nothing can send" claim stopped looking:
`src/push.py` raises `LiveSendNotEnabled`, `LIVE-READINESS.md` says "there is
no code path to either provider", and this was one, needing only an API key
in the environment and a flag.

THE TRANSPORT IS GONE, not merely refused. `refuse_live()` was the only thing
between an API key in the environment and real connection requests, and it was
three hand-placed calls in front of two live `requests.post` bodies - fully
formed, correct, and one deleted line from sending. A refusal a person can
delete is not the same as a capability that does not exist, and this file
cannot be brought under the execution guard because it imports nothing from
`src/`: no eligibility, no approval fingerprint, no killswitch, no pilot cap,
no ledger, no readback.

The dry run still works and still shows what would go where, which is the only
thing this file was still useful for. To actually send, build the guarded path
through `src/executionguard.py` and `src/providerwrites.py`. Do not restore the
POSTs below, and do not lift the refusals.

Dry run by default. `--live` is refused.

  push.py                                     show what would go where
  push.py --live --campaign 42                EmailBison
  push.py --to heyreach --live --campaign 7   HeyReach
  push.py --to both --live --campaign 42 --heyreach-campaign 7 --sender-account 3

Env: BISON_BASE (default https://send.resonategroup.co/api), BISON_KEY,
     HEYREACH_KEY
"""
import argparse, csv, json, os, sys


class LiveSendRefused(SystemExit):
    """`--live` in the prototype. Never a warning, never a flag to flip."""


def refuse_live():
    """Called on every path that would reach a provider or mark a record.

    Placed at each such path rather than once in `main` because
    `push_heyreach` is also called directly by the `--to both` branch, and a
    single check at the entry point is one refactor away from being bypassed.
    """
    raise LiveSendRefused(
        "prototype/bin/push.py cannot send. This script predates every guard "
        "the product has - no eligibility, approval, killswitch, pilot cap, "
        "fatigue, sequence or suppression check - and it wrote the queue "
        "without going through src/store.py. The guarded send path is "
        "src/push.py, which raises LiveSendNotEnabled by design. Nothing "
        "here may be the thing that sends first.")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE = os.path.join(ROOT, "work", "queue.jsonl")
CSVP = os.path.join(ROOT, "out", "emailbison.csv")
HRP = os.path.join(ROOT, "out", "heyreach.csv")
BASE = os.environ.get("BISON_BASE", "https://send.resonategroup.co/api")
HR_BASE = "https://api.heyreach.io/api/public"


def rows(path=None):
    path = path or CSVP
    if not os.path.exists(path):
        sys.exit("run build.py first")
    return list(csv.DictReader(open(path)))


def push_heyreach(campaign_id, sender_account, live):
    rs = rows(HRP)
    print(f"\nHeyReach: {len(rs)} profile(s)")
    for r in rs:
        print(f"  {r['linkedin_url']:<52} {r['first_name']} {r['last_name']} ({r['company'][:20]})")
    if not live:
        return set()
    refuse_live()


def mark_pushed(ids):
    """Refused too, and not only because sending is.

    This replaced the whole queue file with its own serialisation, so it
    bypassed the tenancy validation, the identity invariants and the evidence
    guard in `src/store.py`. That is the same mechanism that destroyed the
    Productive estate once already.
    """
    refuse_live()
    recs = [json.loads(l) for l in open(QUEUE) if l.strip()]
    for rec in recs:
        if rec["id"] in ids:
            rec["state"] = "pushed"
    with open(QUEUE, "w") as f:
        for rec in recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"marked {len(ids)} record(s) pushed")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true")
    p.add_argument("--to", default="emailbison", choices=["emailbison", "heyreach", "both"])
    p.add_argument("--campaign", help="EmailBison campaign id")
    p.add_argument("--heyreach-campaign")
    p.add_argument("--sender-account", help="HeyReach linkedInAccountId")
    a = p.parse_args()

    if a.to == "heyreach":
        ids = push_heyreach(a.heyreach_campaign or a.campaign, a.sender_account, a.live)
        if ids:
            mark_pushed(ids)
        elif not a.live:
            print("\ndry run. add --live --campaign <id> --sender-account <id> to push")
        return

    rs = rows()
    print(f"EmailBison: {len(rs)} lint-clean draft(s) ready")
    for r in rs:
        print(f"  {r['email']:<38} {r['company'][:24]:<26} {r['subject'][:44]}")

    if not a.live:
        if a.to == "both":
            push_heyreach(a.heyreach_campaign, a.sender_account, False)
        print("\ndry run. add --live --campaign <id> to push")
        return
    if not a.campaign:
        sys.exit("--live needs --campaign")

    refuse_live()


if __name__ == "__main__":
    main()
