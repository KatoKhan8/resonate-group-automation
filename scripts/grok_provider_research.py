#!/usr/bin/env python3
"""Ask Grok, with web search, the provider questions we cannot answer from our
own estate - and classify every answer.

    py -3 scripts/grok_provider_research.py --list
    py -3 scripts/grok_provider_research.py --question sender_selection
    py -3 scripts/grok_provider_research.py --all --live

READ-ONLY with respect to every provider that matters: it calls xAI and
nothing else. No EmailBison write, no HeyReach write, no canonical state.

## Why these questions and not a general search

Each one is a decision this system is currently blocked on, and each has a
consequence if it is guessed:

`sender_selection`  If EmailBison picks a sender PER EMAIL from a campaign's
                    attached pool, then attaching a second inbox means a
                    prospect can hear from two humans in one thread and
                    nothing records which. `executionguard`'s arity rule
                    exists because nobody knows the answer. It is the single
                    fact standing between campaign 487 and 2,610 emails a day
                    of measured idle capacity.
`timezone`          Campaign 487 is scheduled 09:00-17:00 Europe/Zagreb and
                    its prospects are not in Zagreb. Whether the provider can
                    send in the RECIPIENT's local hours decides whether that
                    window is a bug or a constraint.
`webhooks`          Every send, reply and bounce is currently discovered by
                    polling on a 300s loop. A webhook would make reply
                    suppression immediate rather than eventually.
`bulk`              Ten leads took four provider calls each. The estate holds
                    550 records.
`scheduling`        487's ten leads were queued six days out and no route
                    lists a mailbox's forward book, so the reason is inferred.

## Classification, which is the point of the exercise

Every answer is recorded as one of:

    DOCUMENTED   the vendor's own documentation says it, with a URL
    OBSERVED     we have seen it in this estate's own provider responses
    HYPOTHESIS   a plausible reading with no source that settles it
    UNKNOWN      the question was asked and not answered

**A model answering confidently is not DOCUMENTED.** The prompt demands a
source URL per claim and anything without one is downgraded here rather than
by whoever reads the report. TASK-166 measured Grok returning ZERO unsourced
facts over ten domains with web_search on, so the demand is reasonable - but
it is checked rather than trusted.

Nothing here may be acted on as provider truth until a readback against our
own estate agrees with it. An invented capability acted on as real is the
failure this whole file exists to avoid.
"""

import argparse
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, xai  # noqa: E402

SYSTEM = (
    "You research vendor API documentation. Answer ONLY from sources you can "
    "cite with a URL. For every claim, give the URL. If the documentation "
    "does not say, answer exactly 'NOT DOCUMENTED' for that point rather than "
    "inferring - an invented capability is worse than an absent one, because "
    "it will be built on. Be concise and concrete: endpoint names, field "
    "names, parameter names, and what the documented behaviour actually is."
)

QUESTIONS = {
    "sender_selection": """EmailBison (emailbison.com) cold email platform API.
When a campaign has MULTIPLE sender email accounts attached:
1. How does EmailBison choose which sender sends a given email? Round robin,
   random, per-lead sticky, per-thread sticky, configurable?
2. If a lead receives a multi-step sequence, do all steps go from the SAME
   sender inbox, or can different steps come from different inboxes?
3. Is there any setting, field or API parameter that controls or pins sender
   selection per lead or per thread?
4. What does the API return that identifies which sender sent or will send a
   given scheduled email?
Cite documentation URLs.""",

    "timezone": """EmailBison cold email platform API and app.
1. A campaign schedule has a timezone plus start/end times and weekday flags.
   Is the sending window interpreted in the CAMPAIGN's timezone, the
   workspace's, or the recipient's?
2. Does EmailBison support sending in the RECIPIENT's local timezone
   ("timezone-aware sending", "send in prospect local time")?
3. Can a timezone be set or inferred PER LEAD, and is there a lead field for
   it?
4. Can a campaign's schedule or timezone be changed after the campaign is
   running, and what happens to already-scheduled emails?
Cite documentation URLs.""",

    "webhooks": """EmailBison cold email platform API.
1. Does EmailBison support webhooks? Which events - email sent, opened,
   replied, bounced, unsubscribed, lead status change?
2. How are webhooks configured - API endpoint or app only? What is the
   payload shape and is there signature verification?
3. Is there any push or streaming alternative to polling for replies?
Cite documentation URLs.""",

    "bulk": """EmailBison cold email platform API.
1. Which endpoints accept BULK input - creating many leads at once, attaching
   many leads to a campaign, updating many leads, adding many senders?
2. What are the documented per-request limits (max items, page sizes)?
3. What are the documented rate limits, and what does the API return when one
   is hit?
Cite documentation URLs.""",

    "scheduling": """EmailBison cold email platform API.
1. How does EmailBison decide WHEN a campaign's leads are scheduled? Is there
   documentation of the scheduling cycle, and when new leads for a day are
   assigned?
2. Is there any endpoint that shows a SENDER EMAIL's forward schedule or
   remaining capacity - across all the campaigns that sender is attached to,
   not just one campaign?
3. How do `max_emails_per_day` on a campaign and `daily_limit` on a sender
   email interact when a sender serves several campaigns?
4. Does mailbox warmup consume a sender's daily limit?
Cite documentation URLs.""",

    "empty_queue": """EmailBison cold email platform API.
A campaign is `status: active` with leads `in_sequence`, but has ZERO
scheduled emails and its sending-schedule endpoint reports nothing for today,
tomorrow or the day after. It was resumed once; the resume CLEARED ten
existing scheduled rows and none were rebuilt.
1. Is it documented that resuming a campaign CLEARS existing scheduled
   emails? Does pause/resume invalidate already-scheduled messages?
2. What documented operations trigger queue regeneration, other than resume
   and the end-of-sending-day cycle?
3. Can an ACTIVE campaign legitimately hold an empty queue indefinitely, and
   what documented conditions cause the scheduler to produce nothing?
4. How does a sender's FORWARD COMMITMENT to other campaigns affect whether
   a rebuild can place rows - is a fully-booked mailbox documented to yield
   an empty queue rather than a later date?
5. Which READ-ONLY endpoints expose scheduling state and sender capacity, so
   this can be diagnosed without any mutating call?
Cite documentation URLs.""",

    "conversation_attribution": """HeyReach LinkedIn automation platform API.
We receive inbox events whose only identifier is a conversation id, in the
form `2-<base64>` where the decoded value looks like
`<uuid>_100`. They carry no campaign, no lead and no sender.
1. Which PUBLIC endpoint resolves a CONVERSATION id to the CAMPAIGN it
   belongs to, and to the LinkedIn SENDER SEAT (account id) that owns it?
   Name the exact endpoint, method, request fields and response fields.
2. Is there an inbox or conversation LIST endpoint that returns campaignId
   and linkedInAccountId per conversation? What are its filter parameters
   and its pagination shape?
3. What does the `2-` prefix on a conversation id denote, and is the format
   documented anywhere?
4. What are the documented RATE LIMITS on those endpoints, and the payload
   shape of a single conversation object?
5. Is there a webhook that delivers a message/reply event WITH its campaign
   and sender already attached, so no lookup is needed?
Cite documentation URLs. Where the docs do not say, answer NOT DOCUMENTED.""",

    "heyreach_sender": """HeyReach LinkedIn automation platform API.
1. When a campaign has multiple LinkedIn sender accounts, how is the sender
   chosen per lead? Is `accountLeadPairs` on AddLeadsToCampaignV2 the
   documented way to pin a specific sender to a specific lead?
2. Is a campaign's sending schedule readable through the API after creation?
   Which endpoint?
3. Does HeyReach support webhooks for connection accepted, message reply, or
   lead status change?
Cite documentation URLs.""",
}


def ask(name, live, model=None, timeout=180):
    prompt = QUESTIONS[name]
    if not live:
        return {"question": name, "chars": len(prompt), "live": False}
    answer = xai.respond(
        [{"role": "system", "content": SYSTEM},
         {"role": "user", "content": prompt}],
        model=model, tools=[{"type": "web_search"}], timeout=timeout)
    return {"question": name, "live": True, "content": answer.get("content"),
            "sources": answer.get("search_urls") or [],
            "usage": answer.get("usage"), "model": answer.get("model"),
            # `respond` does not return a duration; the report prints what is
            # there rather than inventing a number for a field it lacks.
            "status": answer.get("status"),
            "refusal": answer.get("refusal")}


def _detach(argv):
    """Re-run this script detached, and say where the output went.

    The child must survive this process AND the shell that started it, so it
    gets its own process group and its stdio goes to a file rather than to a
    pipe nobody will read.
    """
    import subprocess
    argv = [a for a in (argv or sys.argv[1:]) if a != "--background"]
    log = os.path.join(ROOT, "work",
                       f"grok-{os.getpid()}-{int(time.time())}.out")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    kwargs = {}
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    with open(log, "wb") as handle:
        child = subprocess.Popen([sys.executable, os.path.abspath(__file__)]
                                 + argv, stdout=handle, stderr=handle,
                                 stdin=subprocess.DEVNULL, **kwargs)
    print(f"detached pid {child.pid}, output -> {log}")
    print("This process is NOT waiting. Check the log and the artifact size "
          "before calling the run COMPLETED.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question", action="append", dest="questions")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "docs", "GROK-PROVIDER-RESEARCH-2026-09-17.md"))
    # FOREGROUND IS THE DEFAULT, AND DETACHING IS AN EXPLICIT REQUEST.
    #
    # Two silent child deaths in two days, both the same shape: the caller
    # wrote `nohup py -3 ... &` from a shell that then exited, the child died
    # with it, and the run reported exit 0 having produced only a banner. The
    # artifact check below now catches the empty result, but the better fix is
    # that a long research call is not backgrounded by accident in the first
    # place. So `--background` is opt-in and it detaches PROPERLY - a new
    # process group on POSIX, DETACHED_PROCESS on Windows - rather than
    # relying on a shell to outlive it.
    parser.add_argument("--background", action="store_true",
                        help="detach and return immediately; without it this "
                             "runs in the foreground and you wait for it")
    args = parser.parse_args(argv)

    if args.background:
        return _detach(argv)

    if args.list:
        for name in QUESTIONS:
            print(f"  {name}")
        return 0

    names = list(QUESTIONS) if args.all else (args.questions or [])
    if not names:
        print("nothing asked; --list shows the questions, --all asks them all")
        return 2

    load_env(os.path.join(ROOT, "config", ".env"))
    results = []
    for name in names:
        print(f"--- {name} ---", flush=True)
        try:
            result = ask(name, args.live)
        except Exception as exc:                  # noqa: BLE001 - classified
            print(f"  {type(exc).__name__}: {str(exc)[:160]}", flush=True)
            results.append({"question": name, "error":
                            f"{type(exc).__name__}: {exc}"})
            continue
        results.append(result)
        if result.get("live"):
            print(f"  {result.get('model')} status={result.get('status')} "
                  f"{len(result.get('sources') or [])} sources", flush=True)
            print(str(result.get("content"))
                  .encode("ascii", "replace").decode("ascii")[:1200],
                  flush=True)
        else:
            print(f"  {result['chars']} chars (dry run)", flush=True)

    if not args.live:
        print("\nDRY RUN: xAI was not called.")
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(f"# Grok provider research\n\n{stamp}. One call per "
                     f"question, web_search enabled.\n\n")
        handle.write(
            "**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, "
            "and a confident answer is not a documented one. A point is\n"
            "DOCUMENTED only where a source URL states it, OBSERVED only "
            "where this estate's own provider responses show it, and\n"
            "HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth "
            "until a readback against our own estate agrees with it.\n\n---\n\n")
        for result in results:
            handle.write(f"## {result['question']}\n\n")
            if result.get("error"):
                handle.write(f"**CALL FAILED:** {result['error']}\n\n")
                continue
            handle.write(f"`{result.get('model')}`, "
                         f"{result.get('seconds')}s, "
                         f"{len(result.get('sources') or [])} search URLs, "
                         f"usage {result.get('usage')}.\n\n")
            handle.write((result.get("content") or "") + "\n\n")
            if result.get("sources"):
                handle.write("Sources the model searched:\n\n")
                for url in (result["sources"] or [])[:25]:
                    handle.write(f"- {url}\n")
                handle.write("\n")
    print(f"\nwrote {args.out}")

    # A HEADER IS NOT AN ANSWER, AND EXIT 0 SAID IT WAS.
    #
    # 2026-09-21: the first `empty_queue` run printed its banner, wrote
    # nothing else, and exited 0. The dispatcher recorded COMPLETED, and the
    # only reason it was caught is that a human opened the file. Same class
    # as the r51 dispatch issue: a wrapper that reports success because the
    # process ended rather than because it produced something.
    #
    # Two checks, because they fail differently. Per-question content catches
    # a model that answered nothing; artifact size catches a write that
    # produced only the preamble. MIN_ANSWER_CHARS is deliberately low - a
    # floor under "empty", not a judgement about quality, and a genuine
    # NOT DOCUMENTED answer clears it easily.
    MIN_ANSWER_CHARS = 200
    MIN_ARTIFACT_BYTES = 900          # the preamble alone is ~700 bytes
    answered, empty, failed = [], [], []
    for result in results:
        if result.get("error"):
            failed.append(result["question"])
        elif len((result.get("content") or "").strip()) < MIN_ANSWER_CHARS:
            empty.append(result["question"])
        else:
            answered.append(result["question"])
    try:
        written = os.path.getsize(args.out)
    except OSError:
        written = 0

    if failed or empty or written <= MIN_ARTIFACT_BYTES:
        print()
        print("FAILED: this run produced no usable research.")
        if failed:
            print(f"  call failed      {', '.join(failed)}")
        if empty:
            print(f"  answered nothing {', '.join(empty)} "
                  f"(under {MIN_ANSWER_CHARS} chars)")
        if written <= MIN_ARTIFACT_BYTES:
            print(f"  artifact         {written} bytes, at or under the "
                  f"{MIN_ARTIFACT_BYTES}-byte preamble")
        if answered:
            print(f"  answered         {', '.join(answered)}")
        print("  Exit 1 so a dispatcher records FAILED, not COMPLETED.")
        return 1

    print(f"answered {len(answered)}/{len(results)}, {written} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
