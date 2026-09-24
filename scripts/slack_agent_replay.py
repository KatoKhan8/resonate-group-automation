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
CHECKS = ("numbers", "scope", "terms", "promise", "language", "length",
          "subject")

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


#: SUBJECT. What the question is ABOUT, and what an answer about that
#: same thing has to say. Each row is (name, asked, answered): if `asked`
#: matches the question, `answered` must match the reply.
#:
#: ## THE CHECK THE FIRST AUDIT DID NOT HAVE
#:
#: `numbers` reads the turn's own `guard`, which fires when a figure is
#: ABSENT from the material. It cannot fire on a figure that is present,
#: correct, and answers a different question than the one asked. The first
#: row of the 2026-09-23 replay is exactly that: **`what is running` was
#: answered with MONITOR HEALTH**, and it scored clean on all six checks,
#: because every number in it was real.
#:
#: So this asserts the answer NAMES THE THING THE QUESTION ASKED ABOUT.
#: Both languages, because the corpus is mostly Croatian.
#:
#: **`n/a` WHERE NO SUBJECT IS FOUND, NEVER `pass`.** "what's the status on
#: that?" names nothing extractable, and scoring it `pass` would report a
#: check that had not run as a check that had succeeded - which is the
#: `terms` column of the last audit, 32 of 32 `n/a` read as 32 passes.
SUBJECTS = (
    ("campaign",
     r"kampanj|campaign|pu[sš]tene|aktivne|\brunning\b|\blive\b|"
     r"[sš]to se vrti|what'?s? (?:on|going out)",
     r"kampanj|campaign|\b\d{3}\b"),
    ("sender",
     r"\bsender|\bdomen|\bdomain|mailbox|\binbox|[sš]alje",
     r"\bsender|\bdomen|\bdomain|mailbox|\binbox"),
    ("lead",
     r"\blead|kontakt|\bcontact|prospect",
     r"\blead|kontakt|\bcontact|prospect"),
    ("meeting",
     r"\bmeeting|\bpoziv|\bcall\b|sastan",
     r"\bmeeting|\bpoziv|\bcall|sastan"),
    ("reply",
     r"\brepl(?:y|ies|ied)|odgovor",
     r"\brepl|odgovor"),
    ("approval",
     r"approv|odobr|awaiting|[cč]eka",
     r"approv|odobr|awaiting|[cč]eka"),
    ("report",
     r"\breport|izvje[sš]taj|izvu[cć]i",
     r"\breport|izvje[sš]taj|\bpdf"),
)

#: A campaign id typed in the question. If somebody asks about 487, an
#: answer about 489 is wrong however right its numbers are.
CAMPAIGN_ID = re.compile(r"\b(\d{3})\b")


def subjects_of(text):
    """Which subjects this question is about, and what the answer must say."""
    low = str(text or "").lower()
    out = [(name, answered) for name, asked, answered in SUBJECTS
           if re.search(asked, low, re.I)]
    for ident in sorted(set(CAMPAIGN_ID.findall(low))):
        out.append(("id:" + ident, r"\b" + ident + r"\b"))
    return out


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


#: A catalogue phrasing: a blockquote line, wrapped in emphasis.
QUOTE = re.compile(r"^\s*>\s?(.*)$")

#: Longest first, so `**` is tried before `*` and a bold phrasing is not
#: read as an italic one with a stray asterisk at each end.
EMPHASIS = ("***", "**", "*", "_")


def _unwrap(text):
    """Strip one matched pair of emphasis markers, or return None.

    None means the block is not closed yet - the catalogue wraps a phrasing
    that ran onto a second line in ONE pair spanning both lines, so an
    unclosed opener is the signal to keep reading rather than a malformed
    entry.
    """
    text = text.strip()
    for mark in EMPHASIS:
        if text.startswith(mark):
            if text.endswith(mark) and len(text) > 2 * len(mark):
                return text[len(mark):-len(mark)].strip()
            return None
    return text


def catalogue_questions(root=None):
    """The question catalogue's own examples, as a second corpus.

    `docs/SLACK-AGENT-QUESTION-CATALOGUE.md` was mined from 6,091 messages.
    Its examples are real phrasings that may not appear in the agent's own
    log, because most of them were asked before the agent existed.

    ## THIS PARSED THE WRONG SHAPE AND SCORED ZERO QUESTIONS

    Until 2026-09-24 the pattern here was `- "quoted line"`. The catalogue
    has never used that shape: every phrasing in it is a markdown blockquote
    in emphasis -

        > *jesu puštene kampanje sada?*
        > **can you please stop sending messages to people who have
        > replied????**

    - so `--catalogue` contributed NOTHING to every run that passed it, and
    the run said `replaying 32 question(s)` either way. **A corpus flag that
    silently adds nothing looks exactly like a corpus with nothing in it.**
    That is why this raises when it parses none: see `main`.

    Consecutive quote lines are SEPARATE phrasings, not one block - the
    catalogue lists them back to back with no blank line between - so a
    line is its own question unless its emphasis is left open, which is the
    only thing that makes it run on.
    """
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "docs", "SLACK-AGENT-QUESTION-CATALOGUE.md")
    if not os.path.exists(path):
        return []
    out, pending = [], []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            hit = QUOTE.match(line)
            if not hit:
                pending = []            # a gap closes an unterminated block
                continue
            pending.append(hit.group(1).strip())
            text = _unwrap(" ".join(pending))
            if text is None:
                continue                # emphasis still open: read on
            pending = []
            if len(text) > 8:
                out.append({"text": text, "channel": None, "user": None,
                            "at": None, "source": "catalogue"})
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

    # SUBJECT. The right number answering the wrong question. See SUBJECTS.
    wanted = subjects_of(question["text"])
    if not reply or not wanted:
        marks["subject"] = NA
    else:
        missed = [name for name, answered in wanted
                  if not re.search(answered, reply, re.I)]
        marks["subject"] = FAIL if missed else PASS
        if missed:
            # NAME WHAT WAS MISSED. "subject failed" sends the next reader
            # back to the transcript; "subject: campaign" does not.
            result["subject_missed"] = missed

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
    parser.add_argument("--lift-gag", action="store_true",
                        help="answer client questions in this process, to "
                             "measure the scope the target is stated in")
    parser.add_argument("--no-model", action="store_true")
    parser.add_argument("--out", default=None,
                        help="write the scored rows as JSON here")
    parser.add_argument("--log", default=None)
    args = parser.parse_args(argv)

    load_env()
    model = llm.NoModel() if args.no_model else None

    # --lift-gag. THE TARGET IS STATED IN CLIENT SCOPE AND CLIENT SCOPE
    # ANSWERS IN 0.0 SECONDS.
    #
    # `CLIENT_CHANNEL_GAG` returns before anything is planned, so a replay
    # of real traffic measures the gag rather than the latency - the
    # 2026-09-23 run scored 11 of 32 at `how: gagged`, every one a client.
    # And the gag is not to be lifted in production until the latency is
    # fixed, so the number that would justify lifting it cannot be taken
    # while it is set. That is a circle, and this is the way out of it.
    #
    # IT IS SAFE HERE FOR ONE REASON AND IT IS STRUCTURAL: THIS SCRIPT
    # POSTS NOTHING. `conversation.respond` returns a dict; the only thing
    # in this repository that writes to Slack is the loop, and the loop is
    # not imported here. Lifting the gag in THIS process cannot reach a
    # client channel, because no code path from here to Slack exists.
    #
    # It is also only this process. Nothing is written to config, the
    # constant is rebound in memory, and the running loop is untouched -
    # a merge is not a deploy and neither is this.
    if args.lift_gag:
        conversation.CLIENT_CHANNEL_GAG = ""
        print("--lift-gag: client channels will be ANSWERED in this "
              "process. Nothing is posted - this script has no write path "
              "to Slack - and the running loop is unaffected.")
        sys.stdout.flush()

    corpus = questions(args.log or log_path(), since=args.since)
    if args.catalogue:
        extra = catalogue_questions()
        if not extra:
            # THE CONTROL. `--catalogue` parsed the wrong bullet shape for
            # its whole life and added zero questions to every run, and the
            # only visible difference was a count nobody had a second
            # number to compare against. A corpus flag that finds nothing
            # is a broken parser far more often than an empty catalogue, so
            # it stops here instead of quietly replaying the log twice.
            print("--catalogue parsed NO questions from "
                  "docs/SLACK-AGENT-QUESTION-CATALOGUE.md. The parser and "
                  "the document disagree about the shape of a phrasing; "
                  "fix `catalogue_questions`, do not ignore this.",
                  file=sys.stderr)
            return 2
        corpus += extra
    if args.limit:
        corpus = corpus[:args.limit]

    print("replaying %d question(s)%s"
          % (len(corpus), " with no model" if args.no_model else ""))
    sys.stdout.flush()
    rows = []
    for index, question in enumerate(corpus, 1):
        row = replay_one(question, model=model)
        rows.append(row)
        flag = ",".join(row.get("failed") or []) or "-"
        print("%3d/%d %-7s %-9s %5.1fs %-18s %s"
              % (index, len(corpus), question["source"],
                 row.get("scope") or "?", row["seconds"], flag,
                 str(question["text"])[:58].replace("\n", " ")))
        # FLUSH PER QUESTION. Redirected to a file, Python block-buffers
        # stdout, so a run taking half an hour shows NOTHING until it
        # exits - and a stalled run is then indistinguishable from a slow
        # one. Measured the hard way on the first real pass: twenty
        # minutes with an empty log and no way to tell which.
        sys.stdout.flush()

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
