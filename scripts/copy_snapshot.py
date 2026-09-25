#!/usr/bin/env python3
"""Read one EmailBison campaign back from the provider, whole, to a file.

READS ONLY. Nothing here mutates anything: every call is a GET, and the
transport guard in `src.providers` refuses a write from this process anyway
because no entry point opted in.

WHY A SNAPSHOT FILE AT ALL. The review file and the retroactive audit both
need the same four reads, and a campaign of 333 leads is 23 pages of
membership and 45 pages of queue. Reading it once and working from the file
means the audit can be re-run - and its bugs fixed - without hammering a
client's provider, and it means the evidence behind a refusal is on disk
rather than in a process that has exited.

    py scripts/copy_snapshot.py 503 504 505 --out work/review/raw

The file is provider truth and it carries real recipients, so it is written
under `work/`, which is gitignored. It must never be copied into `docs/`.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import providers  # noqa: E402
from src.providers import bison, request  # noqa: E402

# WHERE THE CREDENTIAL COMES FROM WHEN THIS RUNS OUT OF A WORKTREE.
#
# `providers.ENV_FILE` is `<repo root>/config/.env`, and a worktree has its
# own root with no `.env` in it - so this script, run from a lane's worktree,
# reads nothing and every call is unauthenticated. `RESONATE_ENV_FILE` names
# the real file explicitly. It is READ, never written; nothing here edits a
# credential file and `load_env` cannot: it only calls `setdefault`.
providers.load_env(os.environ.get("RESONATE_ENV_FILE") or None)


#: HOW MANY PAGES THIS READER WILL WALK. The queue on campaign 491 is 45
#: pages at fifteen a page and `bison.PAGE_CAP` is 40, so the default
#: refuses on the largest campaign in the estate - correctly, and this
#: caller genuinely needs every row. The REFUSAL is the property and it is
#: unchanged: past this, the provider module still raises rather than
#: returning a prefix. Only the ceiling moves, and it moves here, at the
#: call site, where somebody can see which campaign made it necessary.
PAGE_CAP = 200


def snapshot(provider_campaign_id):
    """The whole campaign as the provider holds it, right now.

    Five reads, all through `src.providers.bison`, so the pagination
    refusals are the provider module's and there is not a second walk in
    this repository to drift away from them.
    """
    cid = str(provider_campaign_id)
    status, data = request("GET", "%s/campaigns/%s" % (bison.base(), cid),
                           bison.headers())
    campaign = ((data or {}).get("data") or {}) if 200 <= (status or 0) < 300 else {}
    return {
        "provider_campaign_id": cid,
        "campaign": campaign,
        "senders": bison.campaign_senders(cid),
        # THE POOL WITH ITS NAMES ON IT. `campaign_senders` returns ids and
        # nothing else, and "who owns this mailbox" is the question the
        # signature gate exists to answer - a review file that can only
        # print `4280` cannot show an operator that the copy is signed by
        # somebody who does not own the inbox it is leaving from.
        "sender_pool": bison.campaign_sender_emails(cid),
        "sequence": bison.sequence_steps(cid),
        "leads": bison.campaign_leads(cid, cap=PAGE_CAP),
        "queue": bison.scheduled_emails(cid, cap=PAGE_CAP),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("campaigns", nargs="+")
    ap.add_argument("--out", default=os.path.join("work", "review", "raw"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for cid in a.campaigns:
        snap = snapshot(cid)
        path = os.path.join(a.out, "bison-%s.json" % cid)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(snap, f, ensure_ascii=False)
        print("%s  leads=%d queue=%d senders=%d steps=%d  -> %s"
              % (cid, len(snap["leads"]), len(snap["queue"]),
                 len(snap["senders"]), len(snap["sequence"]), path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
