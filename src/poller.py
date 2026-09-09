#!/usr/bin/env python3
"""Polling both providers for inbound events, resumably.

Neither provider offers a webhook we can verify. EmailBison's self-hosted
instance has no webhook management endpoint at all, and the product documents
no signature on the webhooks it can send; HeyReach's webhook management is not
on the surface either. An unsigned webhook is an open door - anyone who learns
the URL can pause every company you have - so polling is the transport, and a
webhook, if one is ever pointed at us, is treated as a hint to poll rather than
as evidence. That decision lives here.

## The checkpoint

A poll that rescans from the beginning every run is not a poll, it is a
liability: it re-reads every reply ever received, and on a bad day it re-pauses
companies that were unpaused by hand. So a checkpoint is stored durably in
work/checkpoints.json and a run reads forward of it.

What the checkpoint holds is a *reply timestamp*, for both providers, and never
the provider's own cursor or offset. A resume point handed back by a feed is
only valid if the feed does not move under it, and neither of these holds still:
EmailBison's cursor bounds the page to older rows and walks backwards into
history, and HeyReach's inbox has no documented ordering, so a stored offset
steps over whatever arrived since. Both cost the same thing when they go wrong -
a reply nobody ever answers - so both pollers start at the head each run and
stop against the mark instead. Re-reading is free: every event is idempotent on
the provider's own id.

## Bounded, always

`max_pages` caps a single run. A provider that hands back a cursor forever -
because it is broken, or because we are pointed at the wrong account - stops
after that many pages rather than spinning until someone notices the bill.

  python -m src.poller emailbison --dry-run
  python -m src.poller heyreach --max-pages 2
"""
import argparse
import json
import os
import re
import sys
import time

from . import adapters, events, inbound, store
from .providers import ProviderError, bison, heyreach

MAX_PAGES = 5
PAGE_SIZE = 50

# What is worth trying again, and what is not. A transport that failed may
# succeed in a moment; a payload we cannot read will never become readable.
#
# Resolved at call time rather than captured here: the audit suite reloads
# src.providers, which mints a fresh ProviderError, and a tuple captured at
# import would then be comparing against a class nobody raises any more.
def retryable():
    from .providers import ProviderError as Current
    return (Current,)


MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1, 4)          # bounded and finite; never a loop


class PollError(RuntimeError):
    pass


# ------------------------------------------------------------- checkpoints

def checkpoint_path():
    return os.path.abspath(os.environ.get("CHECKPOINTS")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "checkpoints.json"))


def load_checkpoints():
    path = checkpoint_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        # A corrupt checkpoint must not stop the world. Starting from the top
        # is safe: every event is idempotent.
        return {}


def checkpoint_key(provider, scope=None):
    """Which slot in checkpoints.json a run reads and writes.

    The mark is a reply timestamp out of one provider feed, and an EmailBison
    feed answers for exactly one workspace without ever saying which. Keying
    the mark by provider alone therefore lets a mark earned in one estate
    suppress replies in another: poll while the credential is bound to
    Bluewave, store its newest timestamp, and every Productive reply older
    than it is filtered out as "already seen" on the next poll and is never
    ingested. Nobody ever answers those.

    So the workspace is part of the key. An unscoped key stays legal and
    unchanged - that is HeyReach, which has one estate - and a scoped one
    simply starts from the head the first time, which is free because
    ingestion is idempotent on the provider's own id.
    """
    return provider if not scope else f"{provider}:{scope}"


def save_checkpoint(provider, cursor, extra=None, scope=None):
    """Atomic, under the same lock discipline as everything else in work/."""
    path = checkpoint_path()
    store.refuse_production_write(path)
    with store.lock(for_path=path):
        data = load_checkpoints()
        entry = data.setdefault(checkpoint_key(provider, scope), {})
        entry["cursor"] = cursor
        entry["at"] = store.now()
        if extra:
            entry.update(extra)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    return cursor


def cursor_for(provider, scope=None):
    return (load_checkpoints().get(checkpoint_key(provider, scope))
            or {}).get("cursor")


# ------------------------------------------------------------------ retry

def with_retry(fn, attempts=MAX_ATTEMPTS, backoff=BACKOFF_SECONDS,
               sleep=time.sleep):
    """Try a transport call a bounded number of times, then give up loudly.

    Only transport errors are retried. A malformed payload, a bad signature or
    a refused approval is not a transient condition and retrying it is how a
    retry storm starts.
    """
    last = None
    for attempt in range(max(1, attempts)):
        try:
            return fn()
        except retryable() as e:
            last = e
            if attempt < attempts - 1:
                sleep(backoff[min(attempt, len(backoff) - 1)])
    raise PollError(f"gave up after {attempts} attempt(s): {last}")


# ------------------------------------------------------------- the pollers

STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]")


def high_water(value):
    """A stored checkpoint that is a reply timestamp, or None.

    Builds before this one stored EmailBison's opaque base64 cursor in the
    same slot. It is not a timestamp, and ordering a timestamp against it
    would compare base64 to ISO-8601 and answer confidently nonsense. An
    unrecognised value therefore means no mark, which re-reads the head -
    safe, because ingestion is idempotent on the provider's own id.
    """
    text = str(value or "").strip()
    return text if STAMP.match(text) else None


def stamp_of(row):
    return str((row or {}).get("created_at") or "").strip()


def poll_emailbison(max_pages=MAX_PAGES, page_size=PAGE_SIZE, cursor=None,
                    fetch=None, sleep=time.sleep):
    """Rows of `/api/replies` newer than the high-water mark, newest first.

    The checkpoint is a high-water mark, not a provider cursor, because
    this feed is descending: `meta.next_cursor` decodes to
    `{"created_at": ..., "_pointsToNextItems": true}` and bounds the page
    to *older* rows. Storing it and resuming from it walks backwards into
    history and never returns to the head, so every reply that arrives
    after a checkpoint is written would be invisible. The poll would still
    report pages and events while missing the only row that mattered.

    So each run starts at the head and pages down until it meets something
    already seen. The cursor is still used, but only within a run.

    Never advance past a gap: if the page budget runs out before the run
    reaches the mark, the mark is returned unchanged and the backlog is
    re-read next time. Re-reading costs a request; skipping is a reply
    nobody ever answers.
    """
    fetch = fetch or bison.fetch_replies
    seen_through = high_water(
        cursor if cursor is not None else cursor_for("emailbison"))

    pages, seen_cursors = [], set()
    newest, page_cursor, caught_up = None, None, False
    for _ in range(max(1, max_pages)):
        current = page_cursor
        rows, next_cursor = with_retry(
            lambda: fetch(cursor=current, per_page=page_size), sleep=sleep)
        if not rows:
            caught_up = True
            break

        for row in rows:
            stamp = stamp_of(row)
            if stamp and (newest is None or stamp > newest):
                newest = stamp

        if seen_through:
            # A row with no timestamp is unreadable, not old. Keeping it is
            # the fail-closed reading: the alternative drops replies whose
            # shape we did not anticipate.
            fresh = [r for r in rows
                     if not stamp_of(r) or stamp_of(r) > seen_through]
            pages.append({"data": fresh})
            if len(fresh) < len(rows):
                caught_up = True        # reached what we already had
                break
        else:
            pages.append({"data": rows})

        if not next_cursor or next_cursor in seen_cursors:
            caught_up = True
            break                       # a cursor that repeats is a loop
        seen_cursors.add(next_cursor)
        page_cursor = next_cursor

    if seen_through and not caught_up:
        return pages, seen_through      # a gap remains; do not jump it
    return pages, (newest or seen_through)


def conversation_stamp(row):
    """The newest message timestamp in one thread, or "" if it states none.

    A HeyReach conversation is a thread, not an event: each message carries
    `createdAt` and the thread summary carries `lastMessageAt`. The newest
    of them is what "have I already read this thread" is asked about, and a
    thread that receives a new message gets a newer one.
    """
    row = row if isinstance(row, dict) else {}
    stamps = [str(row.get("lastMessageAt") or "").strip()]
    for message in row.get("messages") or []:
        if isinstance(message, dict):
            stamps.append(str(message.get("createdAt") or "").strip())
    stamps = [s for s in stamps if STAMP.match(s)]
    return max(stamps) if stamps else ""


def _descending(items):
    """Is this page newest-first, as the live inbox was when last read?

    The early stop above is only sound on a descending feed. Asserting it
    per page costs one comparison and means the guard cannot outlive the
    fact it rests on. A thread with no readable timestamp is skipped
    rather than treated as an inversion: unreadable is not evidence
    either way.
    """
    stamps = [s for s in (conversation_stamp(r) for r in items) if s]
    return all(a >= b for a, b in zip(stamps, stamps[1:]))


def _reached(total, offset):
    """Has `offset` reached a stated totalCount? An unreadable count is no."""
    try:
        return total is not None and offset >= int(total)
    except (TypeError, ValueError):
        return False                    # never claim the inbox was drained


def poll_heyreach(max_pages=MAX_PAGES, page_size=PAGE_SIZE, cursor=None,
                  fetch=None, sleep=time.sleep):
    """Pages of the inbox, filtered against a high-water mark.

    **The checkpoint is not an offset.** It used to be: the run stored
    `offset + len(items)` and the next run resumed from it. An offset is
    only a valid resume point if the collection never reorders, and
    `POST /inbox/GetConversationsV2` documents no ordering at all - not in
    HeyReach's surface as this repository has confirmed it, and not
    anywhere here. Both plausible orderings break a stored offset:

      - newest-first, the ordinary case: every new conversation shifts the
        rest down, so resuming at the stored offset steps straight over
        exactly the rows that arrived since. The replies skipped are
        permanently skipped, and the poll reports a clean run.
      - by last-message time: a thread moves when it receives a message,
        so rows cross page boundaries and are missed at the seam.

    Same defect class as EmailBison's stored cursor, fixed live on
    2026-09-02 (`PRODUCT-GAPS.md` 15a). So the offset is now scratch state
    inside a single run, and the durable checkpoint is a message timestamp.

    **What is known, and what is assumed.** Known: the endpoint takes
    `offset`/`limit` and answers `{items, totalCount}`; a conversation
    carries `lastMessageAt` and messages carry `createdAt`; ingestion is
    idempotent on `provider_event_id`, which is thread plus message stamp.
    Assumed: nothing about order. So this does *not* stop paging when it
    meets a page that looks old - under an unknown order that would skip
    whatever sits further down - it pages from 0 every run within the page
    budget and lets dedupe absorb the repeats.

    The mark is what makes that cheap rather than merely safe, and it is
    only advanced when the run actually **drained** the inbox: a short
    page, an empty page, or `offset` reaching `totalCount`. Only then is
    "every message at or before the newest one I saw has been ingested"
    true without assuming an order, and only then may a later run filter a
    thread out for being at or below the mark. If the page budget runs out
    first, the mark is returned unchanged - never advanced across a gap.

    Consequence, stated rather than hidden: an inbox longer than
    `max_pages * page_size` is never drained, so the mark never advances
    and only the first pages are ever read. That is a coverage limit; it is
    not a skip, and it is what an undocumented order permits.
    """
    fetch = fetch or heyreach.conversations
    seen_through = high_water(
        cursor if cursor is not None else cursor_for("heyreach"))

    pages, offset, newest, drained = [], 0, None, False
    for _ in range(max(1, max_pages)):
        current = offset
        items, total = with_retry(
            lambda: fetch(offset=current, limit=page_size), sleep=sleep)
        items = items or []

        for row in items:
            stamp = conversation_stamp(row)
            if stamp and (newest is None or stamp > newest):
                newest = stamp

        if seen_through:
            # A thread with no readable timestamp is unreadable, not old:
            # keeping it is the fail-closed reading, and ingestion drops
            # the duplicate if we have seen it before.
            fresh = [r for r in items
                     if not conversation_stamp(r)
                     or conversation_stamp(r) > seen_through]
            pages.append({"items": fresh})
            if len(fresh) < len(items) and _descending(items):
                # Everything below this row is older still - but only if
                # this page really is descending, which is checked here
                # rather than assumed.
                #
                # The ordering was undocumented, so this walk used to have
                # to read every page it could afford: 250 conversations of
                # 25,473, about one per cent, with the mark never
                # advancing. Confirmed live on 2026-09-07 against the real
                # inbox - `lastMessageAt` monotonically non-increasing
                # across 200 conversations, four pages and fifteen hours
                # of traffic, no inversion - which licenses stopping at
                # the mark the way `poll_emailbison` does.
                #
                # `_descending` keeps that licence tied to evidence rather
                # than to a date. A provider that reorders its inbox stops
                # satisfying it, and the walk goes back to reading every
                # page it can afford: less coverage per run, and never a
                # silently skipped reply.
                drained = True
                break
        else:
            pages.append({"items": items})

        offset = current + len(items)
        if not items or len(items) < page_size:
            drained = True              # a short page is the end of it
            break
        if _reached(total, offset):
            drained = True
            break

    if not drained:
        return pages, seen_through      # a gap remains; do not jump it
    return pages, (newest or seen_through)


POLLERS = {"emailbison": poll_emailbison, "heyreach": poll_heyreach}

# Which providers can say what they are reading, and how to ask. Only
# EmailBison needs this: its credential is bound to one of thirteen
# workspaces, the binding is changed in the vendor's UI rather than here, and
# it has moved four times in three days with nothing in this repository
# changing. HeyReach's key answers for one organisation unit and has no such
# selector, so it is deliberately absent rather than stubbed.
IDENTIFY = {"emailbison": bison.bound_workspace}


class WrongWorkspace(PollError):
    """The credential is bound to an estate the caller did not expect."""


def identity_of(provider, identify=None):
    """(scope, workspace) for a provider that can say, (None, None) otherwise.

    `identify` is the injection point, the same way `fetch` is: a test proves
    the keying and the refusal without a credential, and production passes
    nothing and gets the live read.
    """
    resolver = identify or IDENTIFY.get(provider)
    if resolver is None:
        return None, None
    who = resolver()
    if not isinstance(who, dict) or "id" not in who:
        raise PollError(f"{provider}: identity read returned no workspace id")
    return f"ws{who['id']}", who


def run(provider, max_pages=MAX_PAGES, page_size=PAGE_SIZE, live=False,
        recs=None, config=None, post=None, fetch=None, sleep=time.sleep,
        advance=True, identify=None, expect=None):
    """Poll one provider and apply everything it returns.

    Dry by default: `live=False` fetches nothing and reports what it would do,
    so the command is safe to run anywhere. Reading is not sending, but a
    default that reaches a provider is still a default that surprises someone.
    """
    poller = POLLERS.get(provider)
    if poller is None:
        raise PollError(f"no poller for {provider!r}")

    if not live:
        # Dry: nothing is read, so there is nothing to scope and no identity
        # call to make. Reporting the unscoped mark would be a guess about
        # which estate a live run would land in, so the cursor is stated as
        # unknown rather than as a value that might belong to another client.
        return {"provider": provider, "live": False, "cursor": None,
                "workspace": None, "pages": 0, "events": 0, "outcomes": [],
                "why": "dry run: nothing was fetched and nothing was applied"}

    # Before the first read and before any mark is touched. A refusal here
    # leaves the checkpoint exactly as it found it, which is the whole point:
    # the damage this guards against is a mark advanced over another estate's
    # timestamps, and that happens on the write, not on the read.
    scope, workspace = identity_of(provider, identify)
    if expect is not None:
        if workspace is None:
            # A pin nobody can check is not a pin. Reading it as "fine" would
            # be the same defect one level up: the caller has stated which
            # estate it believes it is polling, and this provider cannot
            # answer, so the honest outcome is a refusal rather than silence.
            raise WrongWorkspace(
                f"{provider}: workspace {expect} was pinned, but this "
                f"provider cannot say which workspace it is reading; "
                f"refusing to poll rather than assume it is the right one")
        if str(workspace.get("id")) != str(expect):
            raise WrongWorkspace(
                f"{provider}: expected workspace {expect}, but this key is "
                f"bound to {workspace.get('id')} "
                f"({workspace.get('name') or 'unnamed'}); refusing to poll")

    start = cursor_for(provider, scope)
    # Passed down rather than left to the poller to look up. Both pollers
    # fall back to reading the checkpoint themselves when handed None, and
    # that read is unscoped - so a scoped run would have written to `ws29`
    # and gone on reading the shared slot. `""` is "no mark", which is not
    # the same value as None here and is what keeps the fallback unreached.
    pages, cursor = poller(max_pages=max_pages, page_size=page_size,
                           cursor=start if start is not None else "",
                           fetch=fetch, sleep=sleep)
    outcomes = []
    for page in pages:
        # `workspace` is what `identity_of` just proved this credential is bound
        # to. It travels onto every event so a reply can name the estate it came
        # from a day later - see `events.apply`.
        outcomes.extend(inbound.ingest(page, provider, recs=recs, config=config,
                                       post=post,
                                       provider_workspace=workspace))
    if advance and cursor is not None and cursor != start:
        save_checkpoint(provider, cursor, {"pages": len(pages)}, scope=scope)
    return {"provider": provider, "live": True, "cursor": cursor,
            "workspace": workspace,
            "pages": len(pages), "events": len(outcomes), "outcomes": outcomes,
            "applied": sum(1 for o in outcomes
                           if (o.get("applied") or {}).get("status") == "applied"),
            "duplicates": sum(1 for o in outcomes
                              if (o.get("applied") or {}).get("status") == "duplicate"),
            "unmatched": sum(1 for o in outcomes
                             if (o.get("applied") or {}).get("status") == "unmatched")}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.poller")
    p.add_argument("provider", choices=sorted(POLLERS))
    p.add_argument("--live", action="store_true",
                   help="actually fetch. Reading costs nothing and sends nothing")
    p.add_argument("--max-pages", type=int, default=MAX_PAGES)
    p.add_argument("--page-size", type=int, default=PAGE_SIZE)
    p.add_argument("--reset-cursor", action="store_true",
                   help="start from the beginning. Every event is idempotent, "
                        "so this re-reads rather than re-applies")
    p.add_argument("--expect-workspace",
                   help="the provider estate this poll must be reading. "
                        "Defaults to the deployment's own pin; --expect-workspace "
                        "any waives it and says so")
    a = p.parse_args(argv)

    if a.reset_cursor:
        save_checkpoint(a.provider, None, {"reset_at": store.now()})
        print(f"cursor for {a.provider} cleared")

    # THE PIN APPLIES HERE TOO. `run` has always taken `expect` and refused a
    # mismatch, but this CLI never passed one, so `python -m src.poller
    # emailbison --live` ignored `BISON_WORKSPACE_ID` entirely - while
    # `replywatch`, the only other caller, did pin it. So the documented
    # guarantee that the poller "refuses to poll when it does not match
    # BISON_WORKSPACE_ID" was true of the watcher and false of the command a
    # person actually types.
    #
    # It matters more than a missing flag: this path writes replies into
    # `work/queue.jsonl`, and a reply read from the wrong estate pauses a
    # client's account, opens a review and fires a positive-reply alert. Reading
    # is not sending, but it is still writing.
    expect = a.expect_workspace
    if expect is None:
        from . import providers as provider_env
        from . import replywatch
        # `expected_workspace` is a pure env reader on purpose - loading the
        # file inside it would set the pin process-wide for every later caller -
        # so the file is loaded here, at the edge, by the command that wants it.
        provider_env.load_env()
        expect = replywatch.expected_workspace(a.provider)
    elif str(expect).strip().lower() == "any":
        expect = None
        print("  WARNING: polling without a workspace pin. A reply read from "
              "another estate will be applied to this client's records.")

    result = run(a.provider, max_pages=a.max_pages, page_size=a.page_size,
                 live=a.live, expect=expect)
    print(f"  workspace pin {expect if expect is not None else 'NONE (waived)'}")
    print(f"{a.provider}: {'live' if result['live'] else 'DRY RUN'}")
    print(f"  cursor    {result.get('cursor')}")
    print(f"  pages     {result['pages']}")
    print(f"  events    {result['events']}")
    if result["live"]:
        print(f"  applied   {result.get('applied')}")
        print(f"  duplicate {result.get('duplicates')}")
        print(f"  unmatched {result.get('unmatched')}")
    else:
        print(f"  {result['why']}")
    print("\nPolling reads. Nothing was sent to anyone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
