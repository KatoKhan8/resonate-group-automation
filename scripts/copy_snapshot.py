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
from src.providers import bison, query, request  # noqa: E402

# WHERE THE CREDENTIAL COMES FROM WHEN THIS RUNS OUT OF A WORKTREE.
#
# `providers.ENV_FILE` is `<repo root>/config/.env`, and a worktree has its
# own root with no `.env` in it - so this script, run from a lane's worktree,
# reads nothing and every call is unauthenticated. `RESONATE_ENV_FILE` names
# the real file explicitly. It is READ, never written; nothing here edits a
# credential file and `load_env` cannot: it only calls `setdefault`.
providers.load_env(os.environ.get("RESONATE_ENV_FILE") or None)


def _walk(url, what, cap=200):
    """Every row behind a paginated provider route, or a refusal.

    Deliberately NOT `bison._paged`: that one caps at 40 pages and a campaign
    queue of 45 pages is exactly the read this needs. The refusal it has is
    kept - a short read reported as a whole one is the failure - only the
    ceiling moves, and it is stated per call.
    """
    rows, total, page = [], None, 1
    while True:
        status, data = request("GET", query(url, {"page": page}), bison.headers())
        if not (status and 200 <= status < 300):
            raise RuntimeError("%s: page %d -> %s" % (what, page, status))
        chunk = (data or {}).get("data")
        if not isinstance(chunk, list):
            raise RuntimeError("%s: page %d is not a list" % (what, page))
        rows += chunk
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        if page >= cap:
            raise RuntimeError(
                "%s: %d pages and this read stops at %d; refusing to return "
                "%d of %s as though it were all of them"
                % (what, last, cap, len(rows), total))
        page += 1
    if isinstance(total, int) and len(rows) != total:
        raise RuntimeError(
            "%s: meta.total says %d and %d arrived. Refusing to report a "
            "partial read as a complete one" % (what, total, len(rows)))
    return rows


def snapshot(provider_campaign_id):
    """The whole campaign as the provider holds it, right now."""
    cid = str(provider_campaign_id)
    base = bison.base()
    status, data = request("GET", "%s/campaigns/%s" % (base, cid), bison.headers())
    campaign = ((data or {}).get("data") or {}) if 200 <= (status or 0) < 300 else {}
    return {
        "provider_campaign_id": cid,
        "campaign": campaign,
        "senders": bison.campaign_senders(cid),
        # THE POOL WITH ITS NAMES ON IT. `campaign_senders` returns ids and
        # nothing else, and "who owns this mailbox" is the question the
        # signature gate exists to answer - a review file that can only print
        # `4280` cannot show an operator that the copy is signed by somebody
        # who does not own the inbox it is leaving from.
        "sender_pool": _walk(
            "%s/campaigns/%s/sender-emails" % (base, cid), "senders:%s" % cid),
        "sequence": bison.sequence_steps(cid),
        "leads": _walk(bison.leads_endpoint(cid), "leads:%s" % cid),
        "queue": _walk("%s/campaigns/%s/scheduled-emails" % (base, cid),
                       "queue:%s" % cid),
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
