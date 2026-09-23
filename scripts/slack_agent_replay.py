#!/usr/bin/env python3
"""Replay every real question ever asked of the agent, and score the answers.

    py -3 scripts/slack_agent_replay.py --since 2026-09-21
    py -3 scripts/slack_agent_replay.py --since 2026-09-21 --catalogue
    py -3 scripts/slack_agent_replay.py --limit 5 --no-model   # quick pass

OPERATOR, 2026-09-23: "find and fix the ways the agent is worse than it
should be, measured against REAL TRAFFIC, not imagined."

## WHY REPLAY AND NOT MORE TESTS

Every test in this repository asserts something somebody already thought of.
`work/slack-agent.jsonl` holds what people actually typed - including the
phrasings nobody would invent, the Croatian, the one-word follow-ups and the
questions asked in the wrong channel. A suite cannot tell you the agent
answers "what is running" with MONITOR HEALTH when the asker meant
campaigns; the log can.

## IT REPLAYS IN THE ORIGINAL SCOPE, WHICH IS THE WHOLE POINT

Each row carries its channel and user, so the replay resolves the same scope
the live turn did. Replaying a client question as internal would score an
answer the client never saw, and scope is half of what is being scored.

## IT POSTS NOTHING

`--ask` answers locally. Provider READS are live and deliberately so - "are
the numbers right" cannot be answered against a fixture. Nothing here
writes, and `slackagenttools` has no write path to reach.

## THE SIX SCORES ARE THE OPERATOR'S

    numbers    every figure in the answer appears in the material
    scope      the answer stayed inside what that channel may see
    terms      no forbidden term reached a client channel
    promise    no offer the system has no mechanism to keep
    language   the answer is in the language of the question
    length     two to six sentences unless the question needed more

Each is `pass`, `fail` or `n/a`, and `n/a` is used rather than `pass` where
a check does not apply - an internal channel has no forbidden terms, so
scoring it `pass` would inflate every internal answer.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import slackconversation as conversation                # noqa: E402
from src import slackscope, slacklanguage as language            # noqa: E402
from src import llm                                              # noqa: E402
from src.providers import load_env                               # noqa: E402

PASS, FAIL, NA = "pass", "fail", "n/a"
CHECKS = ("numbers", "scope", "terms", "promise", "language", "length")

#: An offer the agent may make. Anything else that reads like a promise is
#: scored against, because `slackfollowup` is the only mechanism there is.
KNOWN_OFFER = "when the first"

#: Phrases that promise future action. Deliberately broad: a false positive
#: here costs a line in a report, a false negative ships a promise nobody
#: can keep - which is the failure the one-offer rule exists to prevent.
PROMISE = re.compile(
    r"\b(i'?ll |i will |we'?ll |we will |let me know once|"
    r"i'?ll let you know|coming (?:up|back) to you|"
    r"i'?ll (?:check|look|find out|get back|update|send|post|follow up))",
    re.I)


def log_path(root=None):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "work", "slack-agent.jsonl")


def questions(path, since=None):
    """Every real question, oldest first, with the scope it was asked in."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("kind") != "question" or not row.get("text"):
                continue
            if since and str(row.get("at") or "") < since:
                continue
            out.append({"text": row["text"], "channel": row.get("channel"),
                        "user": row.get("user"), "at": row.get("at"),
                        "source": "live"})
    return out


def catalogue_questions(root=None):
    """The question catalogue's own examples, as a second corpus.

    `docs/SLACK-AGENT-QUESTION-CATALOGUE.md` was mined from 6,091 messages.
    Its examples are real phrasings that may not appear in the agent's own
    log, because most of them were asked before the agent existed.
    """
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "docs", "SLACK-AGENT-QUESTION-CATALOGUE.md")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            hit = re.match(r'^\s*[-*]\s+"(.+?)"\s*$', line)
            if hit and len(hit.group(1)) > 8:
                out.append({"text": hit.group(1), "channel": None,
                            "user": None, "at": None, "source": "catalogue"})
    return out


def score(question, result):
    """The six checks, for one answered question."""
    reply = str(result.get("reply") or "")
    scope_kind = result.get("scope")
    marks = {}

    # NUMBERS. The turn already ran this and recorded the outcome: `guard`
    # is set when the answer was REPLACED for carrying an unsupported
    # figure, so this reads the system's own verdict rather than inventing
    # a second opinion that could disagree with it.
    guard = str(result.get("guard") or "")
    marks["numbers"] = FAIL if "number" in guard.lower() else PASS

    # SCOPE. Same reasoning: a scope violation replaces the answer.
    marks["scope"] = FAIL if ("scope" in guard.lower()
                              or "workspace" in guard.lower()) else PASS

    # TERMS. Re-checked rather than trusted, because this is the one the
    # operator asked about and a backstop that was not called leaves no
    # trace in `guard`.
    if scope_kind == slackscope.CLIENT and reply:
        try:
            slackscope.Scope(slackscope.CLIENT,
                             workspace=result.get("workspace"),
                             source="replay").check_outbound(reply)
            marks["terms"] = PASS
        except Exception:                                       # noqa: BLE001
            marks["terms"] = FAIL
    else:
        marks["terms"] = NA

    # PROMISE. An offer with no mechanism behind it.
    if not reply:
        marks["promise"] = NA
    elif PROMISE.search(reply) and KNOWN_OFFER not in reply.lower():
        marks["promise"] = FAIL
    else:
        marks["promise"] = PASS

    # LANGUAGE.
    if not reply:
        marks["language"] = NA
    else:
        want = language.detect(question["text"])
        got = language.detect(reply)
        marks["language"] = PASS if want == got else FAIL

    # LENGTH. Sentences, not characters: the prompt asks for two to six.
    if not reply:
        marks["length"] = NA
    else:
        sentences = len([s for s in re.split(r"[.!?]\s", reply) if s.strip()])
        marks["length"] = PASS if 1 <= sentences <= 8 else FAIL

    return marks


def replay_one(question, model=None):
    started = time.time()
    try:
        result = conversation.respond(
            question["text"], channel=question.get("channel"),
            user=question.get("user"), model=model)
    except Exception as exc:                                    # noqa: BLE001
        return {"question": question, "error": "%s: %s"
                % (type(exc).__name__, str(exc)[:200]),
                "seconds": round(time.time() - started, 2),
                "marks": {c: FAIL for c in CHECKS}}
    out = {"question": question, "reply": result.get("reply"),
           "scope": result.get("scope"), "workspace": result.get("workspace"),
           "how": result.get("how"), "planned": result.get("planned"),
           "guard": result.get("guard"),
           "tools": [t.get("name") for t in result.get("tools") or []],
           "seconds": round(time.time() - started, 2)}
    out["marks"] = score(question, out)
    out["failed"] = [c for c in CHECKS if out["marks"].get(c) == FAIL]
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--catalogue", action="store_true")
    parser.add_argument("--no-model", action="store_true")
    parser.add_argument("--out", default=None,
                        help="write the scored rows as JSON here")
    parser.add_argument("--log", default=None)
    args = parser.parse_args(argv)

    load_env()
    model = llm.NoModel() if args.no_model else None

    corpus = questions(args.log or log_path(), since=args.since)
    if args.catalogue:
        corpus += catalogue_questions()
    if args.limit:
        corpus = corpus[:args.limit]

    print("replaying %d question(s)%s"
          % (len(corpus), " with no model" if args.no_model else ""))
    rows = []
    for index, question in enumerate(corpus, 1):
        row = replay_one(question, model=model)
        rows.append(row)
        flag = ",".join(row.get("failed") or []) or "-"
        print("%3d/%d %-7s %-9s %5.1fs %-18s %s"
              % (index, len(corpus), question["source"],
                 row.get("scope") or "?", row["seconds"], flag,
                 str(question["text"])[:58].replace("\n", " ")))

    tally = {c: {PASS: 0, FAIL: 0, NA: 0} for c in CHECKS}
    for row in rows:
        for check, mark in (row.get("marks") or {}).items():
            tally[check][mark] = tally[check].get(mark, 0) + 1
    print("\n%-10s %6s %6s %6s" % ("check", "pass", "fail", "n/a"))
    for check in CHECKS:
        print("%-10s %6d %6d %6d" % (check, tally[check][PASS],
                                     tally[check][FAIL], tally[check][NA]))
    clean = len([r for r in rows if not r.get("failed")])
    print("\nclean answers: %d of %d" % (clean, len(rows)))
    times = sorted(r["seconds"] for r in rows)
    if times:
        print("latency p50 %.1fs  p95 %.1fs  max %.1fs"
              % (times[len(times) // 2], times[int(len(times) * .95) - 1],
                 times[-1]))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=1, default=str)
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
