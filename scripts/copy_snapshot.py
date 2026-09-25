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

from src import providers, reviewfile  # noqa: E402

# WHERE THE CREDENTIAL COMES FROM WHEN THIS RUNS OUT OF A WORKTREE.
#
# `providers.ENV_FILE` is `<repo root>/config/.env`, and a worktree has its
# own root with no `.env` in it - so this script, run from a lane's worktree,
# reads nothing and every call is unauthenticated. `RESONATE_ENV_FILE` names
# the real file explicitly. It is READ, never written; nothing here edits a
# credential file and `load_env` cannot: it only calls `setdefault`.
providers.load_env(os.environ.get("RESONATE_ENV_FILE") or None)


#: THE FIVE READS LIVE IN `src.reviewfile.snapshot`, not here. Three
#: callers need them - `bisonfactory.stage` on every push, this script for
#: the audit, and `py -m src.reviewfile` on demand - and three copies of
#: five route names is three places to disagree about what a review file is
#: made of. The pagination refusals would be the first thing to drift.
snapshot = reviewfile.snapshot


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
