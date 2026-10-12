#!/usr/bin/env python3
"""Walk every reply EmailBison holds, for the learning analysis.

    py -3 scripts/learning_walk_replies.py            # walk/resume
    py -3 scripts/learning_walk_replies.py --report

READ-ONLY GETs. Writes one progress file. No message bodies are stored - only
the facts the analysis needs, because a reply body is a real person's words and
this file is not the place for them.

## WHY REPLIES FIRST

The learning question is reply rate and POSITIVE rate by subject, step,
persona, sender, hour, weekday, industry and headcount. Replies are the
numerator and they are cheap: `/api/replies` is cursor-paginated and the whole
history is a few hundred pages. The denominator - every send, with its subject,
step, sender and hour - is a walk of ~186,000 scheduled-email rows across
327/328/352, which is an overnight job.

So this half runs now and is useful on its own: a reply count per campaign and
per lead, and `interested` per reply, which is the only positive signal the
provider carries.

## `interested` IS THE PROVIDER'S FLAG, NOT OUR CLASSIFICATION

It is recorded as-is and never inferred from the body. A reply with
`automated_reply` true is kept and marked, because an out-of-office is a reply
the send produced and excluding it silently would flatter every rate computed
from this file.
"""
import argparse
import collections
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import replies, store                                  # noqa: E402
from src.providers import bison, load_env                       # noqa: E402

# `store` owns the layout, here as everywhere else. This script spelled the
# path itself, so no test could isolate the store it writes and the ingestion
# path had nowhere to find it - see `store.reply_store_path`.
OUT = store.reply_store_path()
STATE = os.path.join(ROOT, "work", "learning-replies.state.json")
LOCK = os.path.join(ROOT, "work", "learning-replies.lock")


class AlreadyWalking(RuntimeError):
    """A second walker refused. It is not an error condition to recover from."""


def acquire_lock():
    """Refuse to start when another walker holds the lock.

    Two walkers share one cursor and one append-mode OUT, so the second does
    not walk twice as fast - it re-walks the same pages and writes every row a
    second time. That happened on 2026-09-22 and the evidence is still on
    disk: `work/learning-replies.jsonl.dupbak.2026-09-22` holds 34,125 lines
    carrying 17,700 distinct replies, 1.93x. (This docstring said "32,025
    rows in a 16,650-row file" - measured 2026-10-12 against the backup
    itself, those were the wrong two numbers, and a figure nobody can
    reconcile against the file is worse than none.) The duplication is
    invisible in `state["rows"]`, which counts only what that process
    fetched. The file is the thing analysis reads, so the file is the thing
    that has to be right.

    THIS LOCK IS NO LONGER THE ONLY GUARD, and it never could have been: it
    cannot see the ingestion path, and it cannot see a walk that restarts
    because `STATE` was lost. `_append` is idempotent on `reply_id` for both
    of those. This stays because refusing a second walker is still cheaper
    than deduplicating one.

    O_EXCL is the whole mechanism: the create succeeds for exactly one process.
    A lock whose pid is gone is stale - a killed walker never unlinks - so that
    case reclaims it rather than blocking the estate on a dead process.
    """
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                with open(LOCK, encoding="utf-8") as handle:
                    pid = int((handle.read() or "0").strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and _alive(pid):
                raise AlreadyWalking(
                    f"another walker holds {LOCK} (pid {pid}). One walker only: "
                    "a second re-walks the same pages into the same file.")
            os.unlink(LOCK)
            continue
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        return


def _alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def release_lock():
    try:
        os.unlink(LOCK)
    except OSError:
        pass


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    return {"cursor": None, "pages": 0, "rows": 0, "complete": False}


def save_state(state):
    tmp = f"{STATE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=1)
    os.replace(tmp, STATE)


def trim(row):
    """Only what the analysis needs. No bodies, no names, no addresses.

    THE VERDICT IS PART OF WHAT THE ANALYSIS NEEDS. These rows carried no
    classification at all, so `interested` - the PROVIDER's flag - was the
    only signal in the file and the question the walk exists to answer
    ("reply rate and POSITIVE rate") could not be asked of our own
    classifier over any span of time. `replies.verdict_fields` adds the
    classification, the confidence and `classifier`, which is the rule
    digest `replyverdict` compares a stored verdict against.

    It still stores no body: the excerpt, the evidence and the reason that
    `replies.classify` also returns quote a real person and are dropped.
    """
    lead = row.get("lead") or {}
    email = str(lead.get("email") or "")
    trimmed = {
        "reply_id": row.get("id"),
        "campaign_id": row.get("campaign_id"),
        "lead_id": row.get("lead_id"),
        "domain": email.split("@")[-1].lower() if "@" in email else "",
        "received_at": row.get("date_received") or row.get("created_at"),
        "interested": bool(row.get("interested")),
        "automated": bool(row.get("automated_reply")),
    }
    # The BODY only and no subject, exactly as the ingestion path classifies
    # it, so a row written by the walk and a row written by the watcher are
    # the same measurement.
    trimmed.update(replies.verdict_fields(
        row.get("text_body") or row.get("body") or ""))
    return {name: trimmed.get(name) for name in replies.STORED_FIELDS}


def walk(cap_pages=None):
    load_env()
    acquire_lock()
    try:
        return _walk(cap_pages)
    finally:
        release_lock()


def _walk(cap_pages=None):
    state = load_state()
    if state.get("complete"):
        print(f"  already complete: {state['rows']} replies in "
              f"{state['pages']} pages")
        return 0
    # FETCHED AND STORED ARE TWO NUMBERS. `state["rows"]` counts what this
    # process fetched, which is what it has always meant and what the
    # `acquire_lock` docstring warns is not the file. `landed` is what
    # `_append` actually wrote, so a walk that re-reads ground the store
    # already holds says so instead of looking like fresh work.
    landed = 0
    try:
        while True:
            if cap_pages and state["pages"] >= cap_pages:
                print(f"  stopped at --pages ({state['rows']} fetched, "
                      f"{landed} new). Resumable")
                save_state(state)
                return 0
            rows, cursor = bison.fetch_replies(cursor=state["cursor"])
            landed += _append(json.dumps(trim(row)) + "\n" for row in rows)
            state["rows"] += len(rows)
            state["pages"] += 1
            state["cursor"] = cursor
            if state["pages"] % 10 == 0:
                save_state(state)
                print(f"    {state['rows']} fetched, {landed} new, "
                      f"{state['pages']} pages", flush=True)
            if not rows or not cursor:
                state["complete"] = True
                save_state(state)
                print(f"\n  COMPLETE: {state['rows']} replies fetched in "
                      f"{state['pages']} pages, {landed} new to the store")
                return 0
    finally:
        save_state(state)


def _append(lines):
    """One page of rows, deduplicated on `reply_id`. Returns how many landed.

    THE STORE HAS TWO WRITERS AND BOTH OF THEM HAVE TO DEDUPLICATE. This
    walk reads history; `replies.remember` writes the head of the feed every
    few minutes. Two things are therefore shared rather than assumed:

    THE LOCK. `AlreadyWalking` above only serialises this script against a
    second copy of itself, and an append-mode handle held open across a
    whole walk does not serialise against another process's append at all -
    on Windows append mode seeks to the end per write, so two writers can
    interleave bytes inside one line. `store.lock(for_path=OUT)` is the lock
    `replies.remember` takes, so one append at a time, across processes.

    THE KEY. The lock alone only stops a torn line; it does not stop the
    same reply being stored twice. `work/learning-replies.state.json` is
    `complete: false` and the ONLY thing standing between this walk and a
    second pass over the whole feed is that one small file: lose it, corrupt
    it, or run with it cleared, and the walk restarts at the head and
    descends through all of history - re-appending every historical row AND
    every head row the watcher has already stored. That is not a
    hypothetical shape, it is the measured one:
    `work/learning-replies.jsonl.dupbak.2026-09-22` holds 34,125 lines for
    17,700 distinct replies, 1.93x. The current store is 179,715 lines and
    179,715 distinct ids, 1.00x, which is what a latent duplicate mode looks
    like before it is triggered. So the id check is here, under the lock,
    against the same index `replies.remember` reads.

    A row too malformed to name a reply is KEPT. Dropping it would lose a
    reply because we could not read our own line, and the failure being
    guarded against is duplication, not unreadability.

    Appending per PAGE rather than per ten also means the rows are durable
    before the cursor that would skip them is saved. The old version flushed
    every ten pages, so a crash lost up to ten pages of rows that
    `state["cursor"]` had already walked past.
    """
    candidates = [line for line in lines if line.strip()]
    if not candidates:
        return 0
    store.refuse_production_write(OUT)
    with store.lock(for_path=OUT):
        seen = replies.stored_reply_index(OUT)
        pending, fresh = set(), []
        for line in candidates:
            try:
                key = json.loads(line).get("reply_id")
            except ValueError:
                key = None
            if key is not None:
                key = str(key)
                if key in seen or key in pending:
                    continue
                pending.add(key)
            fresh.append(line)
        if not fresh:
            return 0
        with open(OUT, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(fresh))
            handle.flush()
            os.fsync(handle.fileno())
    return len(fresh)


def report():
    if not os.path.exists(OUT):
        print("no replies walked yet")
        return 1
    per_campaign = collections.Counter()
    interested = collections.Counter()
    # OUR OWN VERDICT, counted separately from the provider's `interested`
    # flag, and with "no verdict stored" as its own line rather than folded
    # into a class. A row written before the verdict existed is UNKNOWN and
    # unconfirmable, not neutral and not a measurement.
    verdicts = collections.Counter()
    unverdicted = 0
    automated = 0
    total = 0
    seen = set()
    with open(OUT, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["reply_id"] in seen:
                continue
            seen.add(row["reply_id"])
            total += 1
            per_campaign[row["campaign_id"]] += 1
            if row["interested"]:
                interested[row["campaign_id"]] += 1
            if row["automated"]:
                automated += 1
            verdict = replies.stored_verdict(row)
            if verdict["stored"]:
                verdicts[verdict["classification"]] += 1
            else:
                unverdicted += 1
    print(f"\n  {total} distinct replies, {automated} automated")
    print(f"  {sum(interested.values())} marked interested by the provider")
    print(f"  {unverdicted} carry NO stored verdict (unclassifiable: these "
          f"rows predate the verdict and are not counted below)")
    for name, n in verdicts.most_common():
        print(f"    {name:>24} {n:>8}")
    print("")
    print(f"  {'campaign':>10} {'replies':>8} {'interested':>11}")
    for cid, n in per_campaign.most_common(20):
        print(f"  {str(cid):>10} {n:>8} {interested.get(cid, 0):>11}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--pages", type=int, default=None)
    args = ap.parse_args(argv)
    if args.report:
        return report()
    return walk(cap_pages=args.pages)


if __name__ == "__main__":
    raise SystemExit(main())
