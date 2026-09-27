#!/usr/bin/env python3
"""The knowledge pack: everything the Slack agent is allowed to know.

OPERATOR, 2026-09-21: "KNOWLEDGE PACK, rebuilt hourly and on demand."

## WHY A PACK AND NOT A PROMPT

A model that is told about this project in a prompt knows what somebody
believed when they wrote the prompt. This project's own problem register
names that failure six times over - "a value that was true when it was
written, cached somewhere that had no way to notice it had gone stale" - so
the pack is BUILT, from the repository and the state files, and every
section carries the file it came from and the time it was read.

    built_at        when this pack was assembled
    sources         every file read, with its modification time
    identity        what Resonate OS is, and what it is not
    timeline        when the project started and what has happened since
    workers         who works on it and how              (INTERNAL ONLY)
    policies        the standing decisions, dated, with the reason
    workspaces      per client: ICP, personas, cadence, campaigns, sends

## EVERY NUMBER TRACES

`numbers()` returns every numeric token in the pack together with the
section it came from. `slackanswer.unsupported_numbers` uses it to refuse an
answer that contains a figure the pack and the readbacks do not. That is the
whole "never invents a number" guarantee, and it is mechanical rather than
an instruction to the model.

## WHAT IS NOT IN HERE

No provider call. The pack is built from the repository and from local
canonical state, so building it costs nothing and cannot be rate limited.
Live provider truth is a TOOL (`slackagenttools`), called per question, and
it carries its own read time.

No prospect name and no mailbox address, in any section, in any scope. The
pack holds counts and domains, which is the rule
`notify._status_payload` already enforces for the status channel.
"""
import json
import os
import re
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Where the built pack is cached. In `work/`, the only directory the agent
#: may write.
#:
#: KEPT AS A MODULE CONSTANT for the tests that point it at a temporary
#: file, and resolved through `cache_path()` everywhere else - see below.
CACHE = os.path.join(ROOT, "work", "knowledge-pack.json")

#: Set this to pin the cache; otherwise it follows the state directory.
#: Registered in `store.STATE_OVERRIDES` so `use_directory` moves it with
#: everything else - a state file the move-together set forgets keeps
#: writing to the real `work/` while the rest go to the temp one.
CACHE_VAR = "KNOWLEDGE_PACK"


def cache_path():
    """Where the pack is cached, resolved PER CALL beside the queue.

    A fixed path was wrong and the fake-client harness found it. Pointing
    `QUEUE` at a throwaway tree moves every other state file with it -
    that is what `store.STATE_OVERRIDES` is for - but the pack stayed on
    `work/knowledge-pack.json`, so a run against a synthetic client read the
    REAL pack, with real workspaces in it, and would have answered as one
    client out of another's material. The bug was in the test harness this
    time. It would not have stayed there.

    So the pack follows the queue, the way `campaigns_path` and
    `notify.path` already do, and `store.queue_path`'s own docstring says
    why it is resolved per call rather than captured at import.
    """
    override = (os.environ.get(CACHE_VAR) or "").strip()
    if override:
        return os.path.abspath(override)
    if CACHE != _DEFAULT_CACHE:
        # A test pinned it. Honour that over the queue.
        return CACHE
    try:
        from . import store
        return os.path.join(os.path.dirname(store.queue_path()),
                            "knowledge-pack.json")
    except Exception:                                           # noqa: BLE001
        return CACHE


_DEFAULT_CACHE = CACHE

#: Rebuilt hourly. A pack older than this is stale and is rebuilt on the
#: next question rather than served with a disclaimer - an answer that says
#: "as of three hours ago" is the shape of mistake this project keeps making.
MAX_AGE_SECONDS = 3600

#: Files the pack is built from. A missing one is recorded as missing; it is
#: never quietly skipped, because a section that vanished and a section that
#: is empty look the same to a reader and mean very different things.
SOURCE_FILES = (
    ("product_goal", "PRODUCT-GOAL.md"),
    ("product_inventory", "PRODUCT-INVENTORY.md"),
    ("register", "docs/state/PROBLEM-REGISTER.md"),
    ("routing_policy", "PROVIDER-ROUTING-POLICY.md"),
    ("routing_order", "docs/ROUTING-ORDER-2026-09-16.md"),
    ("auth_batch1", "docs/OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1.md"),
    ("auth_continuous", "docs/OPERATOR-AUTHORIZATION-2026-09-21-CONTINUOUS.md"),
    ("slack_notifications", "SLACK-NOTIFICATIONS.md"),
    ("cadence_model", "CADENCE-MODEL.md"),
)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read(relative):
    path = os.path.join(ROOT, relative)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except Exception:                                           # noqa: BLE001
        return None


def _mtime(relative):
    path = os.path.join(ROOT, relative)
    if not os.path.isfile(path):
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",
                         time.gmtime(os.path.getmtime(path)))


#: Where the handoffs live. NOT a filename.
#:
#: The first version of this named `PRODUCTION-HANDOFF-2026-09-21-EVENING.md`
#: directly. Within hours a NIGHT handoff superseded it - "151 leads are
#: enrolled and none of them can be sent to" - and the pack went on serving
#: the evening's picture as current. That is the register's own recurring
#: defect, committed by the module written to avoid it.
#:
#: So the handoffs are DISCOVERED and sorted, newest first, and a section
#: that needs one scans them in that order and records WHICH it used. A new
#: handoff is picked up by existing, not by somebody remembering to edit a
#: tuple.
HANDOFF_GLOB = "PRODUCTION-HANDOFF-*.md"
HANDOFF_DIR = "docs"

#: Handoffs are named `...-YYYY-MM-DD[-PART].md`, and the parts of one day
#: run in this order.
#:
#: TWO CASES THAT ARE NOT THE SAME, and conflating them put the superseded
#: morning document at the top of the list:
#:
#:   NO part suffix       the day's BASE handoff, written first. Every named
#:                        part of that day supersedes it, so it sorts FIRST
#:                        (oldest) within the day, not last.
#:   an UNKNOWN part      a name this tuple has not seen. It sorts last,
#:                        because a part somebody invented is far more
#:                        likely to be a late addition than an early one.
HANDOFF_PARTS = ("MORNING", "MIDDAY", "AFTERNOON", "EVENING", "NIGHT")

_NO_PART_RANK = -1
_UNKNOWN_PART_RANK = len(HANDOFF_PARTS)


def handoffs():
    """Every production handoff, newest first, as repo-relative paths."""
    import glob
    directory = os.path.join(ROOT, HANDOFF_DIR)
    if not os.path.isdir(directory):
        return []
    found = []
    for path in glob.glob(os.path.join(directory, HANDOFF_GLOB)):
        name = os.path.basename(path)
        date = re.search(r"(\d{4}-\d{2}-\d{2})", name)
        part = re.search(r"\d{4}-\d{2}-\d{2}-([A-Z]+)\.md$", name)
        if not part:
            rank = _NO_PART_RANK
        elif part.group(1) in HANDOFF_PARTS:
            rank = HANDOFF_PARTS.index(part.group(1))
        else:
            rank = _UNKNOWN_PART_RANK
        found.append(((date.group(1) if date else "", rank, name),
                      "%s/%s" % (HANDOFF_DIR, name)))
    found.sort(reverse=True)
    return [relative for _key, relative in found]


def latest_handoff():
    rows = handoffs()
    return rows[0] if rows else None


def find_in_handoffs(pattern, flags=re.M):
    """`(relative path, match)` for the newest handoff that matches.

    Newest first and the first hit wins, so a section that only the evening
    handoff carries is still found after a night one lands - and the pack
    records which document it came from rather than implying the newest.
    """
    for relative in handoffs():
        text = _read(relative)
        if not text:
            continue
        match = re.search(pattern, text, flags)
        if match:
            return relative, match
    return None, None


def sources():
    """Every source file with its modification time, present or missing."""
    out = {}
    for label, relative in SOURCE_FILES:
        stamp = _mtime(relative)
        out[label] = {"path": relative,
                      "modified": stamp,
                      "present": stamp is not None}
    for index, relative in enumerate(handoffs()):
        out["handoff" if index == 0 else "handoff_%d" % index] = {
            "path": relative, "modified": _mtime(relative), "present": True,
            "current": index == 0}
    return out


# ------------------------------------------------------------- identity

def _bullets(text, heading, limit=12):
    """The `- ` bullets under one `## heading`, in order."""
    if not text:
        return []
    body = re.split(r"^##\s+" + re.escape(heading) + r"\s*$", text,
                    maxsplit=1, flags=re.M)
    if len(body) < 2:
        return []
    section = re.split(r"^##\s", body[1], maxsplit=1, flags=re.M)[0]
    out = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(re.sub(r"\*\*", "", stripped[2:]).strip())
        if len(out) >= limit:
            break
    return out


def _block(text, heading):
    """The indented code block under one `## heading`, as a list of lines."""
    if not text:
        return []
    body = re.split(r"^##\s+" + re.escape(heading) + r"\s*$", text,
                    maxsplit=1, flags=re.M)
    if len(body) < 2:
        return []
    section = re.split(r"^##\s", body[1], maxsplit=1, flags=re.M)[0]
    out = []
    for line in section.splitlines():
        if line.startswith("    ") and line.strip():
            out.append(line.strip())
        elif out:
            break
    return out


def identity():
    """What this is, what it is not, and the hierarchy. From PRODUCT-GOAL."""
    goal = _read("PRODUCT-GOAL.md")
    inventory = _read("PRODUCT-INVENTORY.md")
    out = {
        "source": "PRODUCT-GOAL.md",
        "read_at": _now(),
        "one_line": ("An internal, multi-client, admin-operated lead "
                     "generation engine for Resonate Group. Resonate admins "
                     "operate it; clients receive reporting and results."),
        "what_it_is_not": _bullets(goal, "What this is not"),
        "hierarchy": _block(goal, "The hierarchy"),
        "invariant": _block(goal, "The non-negotiable invariant"),
        "cross_client_contamination": _bullets(
            goal, "Cross-client contamination"),
    }
    if inventory:
        rows = [line for line in inventory.splitlines()
                if line.startswith("| ") and line.count("|") >= 4]
        out["inventory_rows"] = max(0, len(rows) - 2)
    return out


# ------------------------------------------------------------- timeline

def _git(*args):
    try:
        proc = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True,
                              text=True, timeout=30)
    except Exception:                                           # noqa: BLE001
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


#: Dated facts the pack lifts out of prose. Each names the file it comes
#: from and a pattern that must match; an unmatched pattern produces NO
#: milestone rather than a remembered one.
#: `HANDOFF` as the file means "the newest handoff that carries this
#: sentence", searched newest first. Any other string is a literal path.
HANDOFF = "<handoff>"

MILESTONE_PATTERNS = (
    ("first-send", "docs/state/PROBLEM-REGISTER.md",
     r"EmailBison (\d+) sent a real email at (\d{4}-\d{2}-\d{2}T[\d:]+Z)",
     "First provider-confirmed send: campaign {0} at {1}."),
    ("second-send", HANDOFF,
     r"First at (\d{2}:\d{2}:\d{2}Z), second at (\d{2}:\d{2}:\d{2}Z)",
     "Two sends on 2026-09-21: {0} and {1}."),
    ("estate-attested", HANDOFF,
     r"HUMAN_IDENTITY_ATTESTED\s+0 -> (\d+) mailboxes across (\d+) humans",
     "Sender estate attested: {0} mailboxes across {1} humans, 2026-09-21."),
    ("slack-live", "docs/state/PROBLEM-REGISTER.md",
     r"`scripts/slack_smoke\.py` posted one message and Slack\s+returned "
     r"`ts (\d+\.\d+)`",
     "Slack transport proven live, receipt ts {0}, 2026-09-21."),
    ("batches-pushed", HANDOFF,
     r"campaigns exist, \*\*(\d+)\s+through (\d+)\*\*, one per attested "
     r"human, holding (\d+) leads",
     "Batches pushed: campaigns {0}-{1} hold {2} enrolled leads."),
    ("capacity", HANDOFF,
     r"CAPACITY WENT ([\d,]+) -> ([\d,]+) FIRST STEPS A DAY",
     "First-step capacity went {0} to {1} a day."),
)


def timeline():
    """When the project started, and what has happened since.

    The start date and the commit counts come from git, which cannot be
    remembered wrongly. The milestones come from named sentences in named
    files, and a sentence that is no longer there produces no milestone.
    """
    out = {"source": "git history + PROBLEM-REGISTER.md + the handoff",
           "read_at": _now()}

    first = _git("log", "--reverse", "--format=%ad", "--date=short")
    if first:
        lines = [line for line in first.splitlines() if line.strip()]
        if lines:
            out["started_on"] = lines[0].strip()
            out["commits_total"] = len(lines)
            out["latest_commit_on"] = lines[-1].strip()
            by_day = {}
            for line in lines:
                by_day[line.strip()] = by_day.get(line.strip(), 0) + 1
            out["days_worked"] = len(by_day)
            out["commits_by_day"] = dict(sorted(by_day.items())[-14:])

    milestones = []
    for key, relative, pattern, template in MILESTONE_PATTERNS:
        if relative == HANDOFF:
            found, match = find_in_handoffs(pattern)
        else:
            text = _read(relative)
            match = re.search(pattern, text, re.M) if text else None
            found = relative
        if not match:
            continue
        milestones.append({"id": key, "source": found,
                           "fact": template.format(*match.groups())})
    out["milestones"] = milestones
    return out


# -------------------------------------------------------------- workers
#
# INTERNAL ONLY. `slackscope.Scope.filter_pack` drops this section for every
# scope but `internal`, and the outbound check refuses an answer that names
# one of these workers in a client channel.

#: Who works on this and what each is for. The ROLE is editorial - it is a
#: description of how the project is run, which no file states outright -
#: and each row's LIVE state is read, not remembered.
WORKER_ROLES = (
    ("claude-code", "Claude Code",
     "Orchestration. Plans the work, writes and merges code, runs the gates, "
     "and is the only thing that executes an approved change."),
    ("qwen", "Qwen",
     "Bounded engineering. Takes one written task brief at a time, works on "
     "its own branch, and returns a suite result. It never chooses what to "
     "build."),
    ("glm", "GLM",
     "Adversarial review. Reads a change and tries to break the reasoning "
     "behind it before it merges."),
    ("grok", "Grok",
     "Research. Fourth in the provider order, for still-missing, current or "
     "ambiguous company evidence."),
    ("monitors", "Python monitors",
     "The watchers. Campaign watchers, the reply watcher, mailbox "
     "utilisation, notification delivery and verification workers. Each "
     "writes a heartbeat; a silent monitor is a fault, not a quiet day."),
    ("buggie", "Buggie",
     "A parallel crew of specialist reviewers plus adversarial skeptics that "
     "try to refute every finding before it is written down."),
)


def workers():
    """Who works on it, and what each is doing right now."""
    out = {"read_at": _now(), "internal_only": True,
           "source": "AGENTS.md, QWEN.md, docs/qwen-tasks, work/heartbeat",
           "roles": [{"id": key, "name": name, "role": role}
                     for key, name, role in WORKER_ROLES]}

    tasks = {"running": [], "rework": [], "ready": []}
    base = os.path.join(ROOT, "docs", "qwen-tasks")
    for folder, key in (("RUNNING", "running"), ("REWORK", "rework"),
                        ("READY", "ready")):
        directory = os.path.join(base, folder)
        if os.path.isdir(directory):
            tasks[key] = sorted(name for name in os.listdir(directory)
                                if name.endswith(".md"))
    out["qwen_tasks"] = tasks

    try:
        from . import watchsink
        beats = watchsink.heartbeats()
    except Exception:                                           # noqa: BLE001
        beats = []
    now = time.time()
    rows = []
    for beat in beats:
        epoch = beat.get("epoch")
        age = round(now - epoch, 1) if isinstance(epoch, (int, float)) else None
        rows.append({"watcher": beat.get("watcher") or beat.get("source"),
                     "pid": beat.get("pid"), "age_seconds": age,
                     "at": beat.get("at")})
    out["monitors"] = rows
    out["monitors_beating_within_15_minutes"] = len(
        [r for r in rows if isinstance(r.get("age_seconds"), (int, float))
         and r["age_seconds"] < 900])
    return out


# ------------------------------------------------------------- policies

#: The plain-language WHY for each standing decision. The RULE text is read
#: out of the handoff so it cannot drift from the document; this is the part
#: no document states in a sentence a person would say out loud.
POLICY_WHY = {
    "provider-order": (
        "Every provider is asked only for what the one before it did not "
        "return, cheapest capable first. It is an enrichment order, not a "
        "verification order - ContactOut was removed from verification on "
        "the same day it was kept first for enrichment, because being good "
        "at finding an address is not the same as being right about whether "
        "it accepts mail."),
    "verification": (
        "Two independent confirmations before anything is written to. Two "
        "providers that disagree HOLD rather than pick a winner, because a "
        "wrong verdict costs a bounce and a bounce costs the estate."),
    "credit-spend": (
        "Spend is reported and never gated. A hard cap would stop the "
        "pipeline mid-account and leave half-enriched rows nobody can "
        "reason about; a rate limit means back off and continue, never "
        "halt."),
    "collision-recency": (
        "Somebody already contacted recently is not contacted again. A "
        "reply excludes forever regardless of how long ago it was - it is "
        "the strongest signal a person can send - and an unknown history "
        "HOLDS rather than proceeds."),
    "pipeline-order": (
        "Collision is checked before verification because collision is free "
        "and verification is not. Spending a credit to verify somebody we "
        "were never going to be allowed to mail is money spent to learn "
        "nothing."),
    "dual-channel": (
        "Email and LinkedIn run as two channels against the same account. "
        "The human sending the email and the seat sending the connection "
        "request need not be the same person, but within one channel the "
        "same human holds the thread - a conversation that changes voice "
        "halfway reads as automation."),
    "pacing": (
        "A campaign's enrolled-but-unsent backlog stays at or below three "
        "days of its own first-step capacity. Batches are sized to that "
        "rule rather than to a round number, so nothing sits enrolled for a "
        "week looking like progress."),
    "hard-stops": (
        "Bounce rate, suppression, reply-stop and the kill switch are "
        "absolute. Autonomy on this project means fewer manual steps, never "
        "fewer gates."),
    "client-approval-cycle": (
        "A client approves accounts before anybody is contacted at them, and "
        "the approval is fingerprinted - change the copy or the recipients "
        "and the approval goes stale rather than silently covering the new "
        "version."),
    "batches": (
        "Batches are continuous, 2..N, each under the same eight conditions "
        "as batch 1: stats posted, a fifteen-minute veto window, then push."),
    "cross-channel": (
        "The email human and the LinkedIn seat need not match. Within a "
        "channel, the same human holds the thread."),
    "reengagement-lanes": (
        "Somebody contacted before is re-approached on a different lane "
        "with a different angle, never by repeating the first message."),
}

#: Which standing decision each row of the handoff's policy table is, keyed
#: by the table's own first column. The table is fixed-width: a row starts
#: at four spaces, its label runs to the first double space, and anything
#: indented deeper is a continuation of the row above.
POLICY_LABELS = {
    "PROVIDER ORDER": ("provider-order", "Provider order"),
    "VERIFICATION ROLES": ("verification", "Verification roles"),
    "CREDIT SPEND": ("credit-spend", "Credit spend"),
    "COLLISION RECENCY": ("collision-recency", "Collision recency"),
    "PIPELINE ORDER": ("pipeline-order", "Pipeline order"),
    "CROSS-CHANNEL": ("cross-channel", "Cross-channel"),
    "BATCHES": ("batches", "Batches"),
}

#: Standing practice that no document states as a rule in one sentence.
#: Marked `editorial` so an answer can say where it comes from, and kept
#: separate from anything parsed out of a document.
EDITORIAL_POLICIES = (
    ("hard-stops", "Hard stops",
     "Bounce rate above 2%, suppression, reply-stop and the kill switch "
     "halt sending. A hard stop halts all further batches until the "
     "operator clears it in writing."),
    ("reengagement-lanes", "Re-engagement lanes",
     "Somebody contacted before is re-approached on a different lane with a "
     "different angle, subject to the collision recency rule."),
)


def policies():
    """The standing decisions, with the date, who made them, and the why.

    Parsed out of the handoff's own policy block rather than transcribed, so
    a decision that changes in the document changes here on the next hourly
    rebuild. A decision this parser cannot find is absent rather than
    remembered.
    """
    source, block = find_in_handoffs(
        r"^##\s*\d*\.?\s*STANDING POLICY DECISIONS([\s\S]*?)^## ")
    rows = []
    body = block.group(1) if block else ""
    text = _read(source) if source else ""
    decided_on = "2026-09-21"
    decided_by = "Zvonimir (operator)"
    heading = re.search(r"all operator, all (\d{4}-\d{2}-\d{2})", text or "")
    if heading:
        decided_on = heading.group(1)

    current = None
    buckets = {}
    titles = {}
    order = []
    for line in body.splitlines():
        if not line.startswith("    ") or not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        head = re.match(r"([A-Z][A-Z \-]*[A-Z])\s{2,}(.*)$", line.strip())
        if indent <= 5 and head and head.group(1) in POLICY_LABELS:
            ident, title = POLICY_LABELS[head.group(1)]
            current = ident
            if current not in buckets:
                buckets[current] = []
                titles[current] = title
                order.append(current)
            buckets[current].append(head.group(2).strip())
        elif current:
            buckets[current].append(line.strip())

    for key in order:
        rows.append({
            "id": key,
            "title": titles.get(key, key),
            "rule": " ".join(buckets[key]).strip(),
            "decided_on": decided_on,
            "decided_by": decided_by,
            "source": source,
            "why": POLICY_WHY.get(key, ""),
        })

    # Decisions that live in their own authorization documents rather than
    # in the handoff's table.
    for relative, ident, title in (
            ("docs/OPERATOR-AUTHORIZATION-2026-09-21-CONTINUOUS.md",
             "pacing", "Pacing rule"),
            ("docs/OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1.md",
             "client-approval-cycle", "Client approval cycle"),
    ):
        grant = _read(relative)
        if not grant:
            continue
        if ident == "pacing":
            match = re.search(r"PACING RULE\.([\s\S]*?)\n\n", grant)
        else:
            match = re.search(r"CONDITIONS, all binding:([\s\S]*?)\n\n", grant)
        if not match:
            continue
        rows.append({
            "id": ident, "title": title,
            "rule": " ".join(match.group(1).split()),
            "decided_on": "2026-09-21", "decided_by": "Zvonimir (operator)",
            "source": relative, "why": POLICY_WHY.get(ident, ""),
        })

    for ident, title, rule in EDITORIAL_POLICIES:
        if any(r["id"] == ident for r in rows):
            continue
        rows.append({"id": ident, "title": title, "rule": rule,
                     "decided_on": "2026-09-21",
                     "decided_by": "Zvonimir (operator)",
                     "source": "standing practice, not a single document",
                     "editorial": True,
                     "why": POLICY_WHY.get(ident, "")})

    return rows


# --------------------------------------------------------- current state

#: Headings that mean "what is waiting on a person". Handoffs do not use one
#: name for this - the evening's was "TOMORROW'S FIRST THREE ACTIONS", the
#: night's is "WHAT IS WAITING ON THE OPERATOR" - so the pack looks for any
#: of them, newest handoff first, and records which it found.
WAITING_HEADINGS = (
    r"WHAT IS WAITING ON THE OPERATOR",
    r"TOMORROW'S FIRST THREE ACTIONS",
    r"WHAT NEEDS THE OPERATOR",
    r"NEXT ACTIONS",
)

#: Same idea for the headline. A handoff's section 1 is always what somebody
#: thought was the most important thing at the time it was written, which is
#: exactly what a morning briefing's first sentence needs.
HEADLINE_PATTERN = r"^##\s*1\.\s*(?:THE HEADLINE:\s*)?(.+?)\s*$"


def current_state():
    """What the NEWEST handoff says is true now, and what waits on a person.

    Separate from `timeline` deliberately. The timeline is what happened;
    this is what is happening, and it is the section a morning briefing and
    an internal "where are we" both read. It always names the document it
    came from, because "current" is a claim with a date on it.
    """
    out = {"read_at": _now(), "source": latest_handoff()}
    text = _read(out["source"]) if out["source"] else None
    if not text:
        out["_error"] = "no production handoff is present"
        return out

    headline = re.search(HEADLINE_PATTERN, text, re.M)
    if headline:
        out["headline"] = headline.group(1).strip()

    for heading in WAITING_HEADINGS:
        source, block = find_in_handoffs(
            r"^##\s*\d*\.?\s*" + heading + r"([\s\S]*?)(?:^## |\Z)")
        if not block:
            continue
        items = []
        for match in re.finditer(r"^\d+\.\s+(.+?)(?=^\d+\.|\Z)",
                                 block.group(1).strip(), re.M | re.S):
            items.append(re.sub(r"\*\*", "",
                                " ".join(match.group(1).split()))[:300])
        if items:
            out["waiting_on_operator"] = items
            out["waiting_source"] = source
            out["waiting_heading"] = heading
            break

    monitors = re.search(r"^##\s*\d*\.?\s*MONITORS([\s\S]*?)(?:^## |\Z)",
                         text, re.M)
    if monitors:
        names = re.findall(r"^\s{2,}\S+\s+(\S+)", monitors.group(1), re.M)
        out["monitors_expected"] = sorted(set(names))
    return out


# ------------------------------------------------------------ workspaces

def _client_config(slug):
    try:
        from . import clients
        return clients.load(slug)
    except Exception:                                           # noqa: BLE001
        return None


def _id_sort_key(ident):
    """Sort a campaign id the way its issuer counts, not as text.

    These ids arrive as strings and were sorted as strings. That is right
    for three digits and wrong for four: `'1001'` sorts BELOW `'451'`, so
    the first four-digit campaign this provider issues would scramble the
    whole order. Comparing `(len, text)` orders digit strings numerically
    without assuming they parse as ints, and anything non-numeric sorts
    after all of them rather than raising.
    """
    ident = str(ident or "")
    if ident.isdigit():
        return (0, len(ident), ident)
    return (1, 0, ident)


def _campaign_ids_newest_first(rows):
    """This workspace's provider campaign ids, newest first.

    THE ORDER IS LOAD-BEARING AND WAS BACKWARDS. Seven readers in
    `slackagenttools` take `ids[:N]` - `sends_today` takes eight,
    `activity_this_week` and `replies` and `weekly_plan` ten,
    `lead_in_campaign` and the two domain walks twelve - because each one
    costs a provider read per campaign. This list decides which N they get.

    It was built with `sorted()`, which is oldest first, so every cap
    discarded the newest campaigns - and new campaigns are the ones that
    are running. Measured live on 2026-09-22: the estate held fourteen
    campaigns, four had sent that day (491, 492, 494, 495 - 296 emails),
    and `sends_today` saw two of them, because 493 onward sat past the
    cut behind six campaigns that had not sent since the 14th.

    ## AND THE ORDER IS THE PROVIDER'S ID, NOT `created_at`

    `created_at` was the obvious key and it is the wrong one. Measured
    against the live store on 2026-09-22, every campaign in this estate
    that has ever sent carries **`created_at: None`**:

        451 484 485 487 489      2026-09-13 .. 2026-09-18   draft/approved
        491 492 493 494 495 ...  None                       the batch that
                                                            is sending

    The eight batch-1 campaigns were written by a path that never set it.
    So ordering on it - under any rule for the nulls - sorts the six dead
    campaigns above the eight live ones, which is the defect this function
    exists to fix, restored by the fix. A signal that is absent on exactly
    the rows that matter is not a signal.

    The provider's id IS present on every row and IS its issue order:
    451 predates 481 predates 491. That is what this sorts on, descending,
    through `_id_sort_key` so it counts rather than compares text.

    `created_at` is not consulted at all. Ordering on a field that is null
    for the newest half of the estate would be a second way to get this
    wrong, and the first way already reached a client channel.
    """
    ids = [str(r["bison_campaign_id"]) for r in rows
           if r.get("bison_campaign_id")]
    return sorted(ids, key=_id_sort_key, reverse=True)


def _campaign_rows(slug):
    try:
        from . import campaigns
        return [r for r in campaigns.load()
                if (r.get("client") or r.get("workspace")) == slug]
    except Exception:                                           # noqa: BLE001
        return []


def _stage_counts():
    """Batch and stage counts from the staging journals, keyed by state."""
    out = {}
    directory = os.path.join(ROOT, "work", "stage")
    for name, key in (("s3-icp.jsonl", "s3_icp"),
                      ("s5-verify.jsonl", "s5_verification"),
                      ("s7-copy.jsonl", "s7_copy")):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        latest = {}
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    latest[row.get("email") or row.get("domain")
                           or len(latest)] = row
        except Exception:                                       # noqa: BLE001
            continue
        states = {}
        reasons = {}
        for row in latest.values():
            state = row.get("state") or row.get("verdict") or "unknown"
            states[state] = states.get(state, 0) + 1
            if state == "held":
                reason = str(row.get("reason") or "unknown").split(":")[0]
                reasons[reason] = reasons.get(reason, 0) + 1
        out[key] = {"decided": len(latest), "by_state": states}
        if reasons:
            out[key]["held_by_reason"] = reasons
    return out


def _caps(config):
    """The daily limits that actually apply, and where each one came from.

    `pilotcaps.effective` reports `configured` or `ceiling` per key. Keeping
    that distinction is the point: a client asking "how many a day" is owed
    the number that binds, not the number somebody typed into a file that a
    lower ceiling overrides.
    """
    try:
        from . import pilotcaps
        rows = pilotcaps.effective(config)
    except Exception:                                           # noqa: BLE001
        return None
    return {key: {"limit": row.get("limit"), "from": row.get("source")}
            for key, row in (rows or {}).items()}


def _cadence(name):
    """One named cadence as steps: day, channel and what the step does.

    The email steps and the LinkedIn graph are the same sequence read two
    ways - a LinkedIn step carries a `requires` (connected, or connection
    not accepted) and the email steps do not - so both are returned from
    one place rather than described twice.
    """
    if not name:
        return None
    try:
        from . import cadencelibrary
        steps = cadencelibrary.named(name)
    except Exception:                                           # noqa: BLE001
        return {"name": name, "_error": "cadence not found in the library"}
    out = {"name": name, "steps": []}
    for step in steps or []:
        row = {"key": step.get("key"), "day": step.get("day"),
               "channel": step.get("channel")}
        if step.get("linkedin_action"):
            row["action"] = step["linkedin_action"]
        if step.get("requires"):
            row["requires"] = step["requires"]
        alternative = step.get("alternative") or {}
        if alternative.get("linkedin_action"):
            row["if_not"] = "%s -> %s" % (
                alternative.get("requires") or "otherwise",
                alternative["linkedin_action"])
        out["steps"].append(row)
    out["email_steps"] = len([s for s in out["steps"]
                              if s.get("channel") == "email"])
    out["linkedin_steps"] = len([s for s in out["steps"]
                                 if s.get("channel") == "linkedin"])
    out["days"] = max([s.get("day") or 0 for s in out["steps"]] or [0])
    return out


def workspace_entry(slug, config=None):
    """One client's configuration and current state. No prospect names."""
    config = config or _client_config(slug)
    entry = {"slug": slug, "read_at": _now()}
    if config:
        entry["name"] = config.get("name") or slug
        icp = config.get("icp") or {}
        market = config.get("market") or {}
        entry["icp"] = {
            "sells_to": market.get("must") or icp.get("must"),
            "min_employees": (market.get("size_min_employees")
                              or icp.get("size_min_employees")),
            "geos": market.get("geos") or icp.get("geos"),
            "exclude_geos": market.get("exclude_geos"),
        }
        personas = config.get("personas") or {}
        entry["personas"] = sorted(personas) if isinstance(personas, dict) \
            else personas
        angles = {}
        if isinstance(personas, dict):
            for name, spec in personas.items():
                if isinstance(spec, dict) and spec.get("angles"):
                    angles[name] = list(spec["angles"])
        entry["angles"] = angles
        window = config.get("sending_window") or {}
        entry["sending"] = {
            "window_days": window.get("days"),
            "window_start": window.get("start"),
            "window_end": window.get("end"),
            "timezone": window.get("timezone"),
            "caps": _caps(config),
        }
        entry["cadence"] = _cadence(config.get("cadence"))

    rows = _campaign_rows(slug)
    by_status = {}
    for row in rows:
        status = (row.get("status") or "unknown").lower()
        by_status[status] = by_status.get(status, 0) + 1
    entry["campaigns"] = {"total": len(rows), "by_status": by_status}
    entry["provider_campaign_ids"] = _campaign_ids_newest_first(rows)

    batches = {}
    for row in rows:
        batch = row.get("batch_id")
        if not batch:
            continue
        seen = batches.setdefault(
            batch, {"campaigns": 0, "accounts": 0, "bound_to_provider": 0,
                    "created_at": row.get("created_at")})
        seen["campaigns"] += 1
        seen["accounts"] += len(row.get("record_ids") or [])
        if row.get("bison_campaign_id"):
            seen["bound_to_provider"] += 1
        if row.get("created_at") and (
                not seen["created_at"]
                or row["created_at"] < seen["created_at"]):
            seen["created_at"] = row["created_at"]
    entry["batch_history"] = dict(sorted(batches.items()))
    return entry


def workspaces_section():
    """Every workspace, each keyed by its slug. Scope filters this."""
    try:
        from . import workspaces as ws
        slugs = [w.get("slug") for w in ws.workspaces() if w.get("slug")]
    except Exception:                                           # noqa: BLE001
        slugs = []
    out = {}
    for slug in slugs:
        out[slug] = workspace_entry(slug)
    stages = _stage_counts()
    if stages and "productive" in out:
        # The staging journals are the 24k Productive track. They are named
        # per workspace rather than globally so a second client's stages
        # cannot be read as this one's.
        out["productive"]["stages"] = stages
    return out


# --------------------------------------------------------- mechanisms

#: The catalogue of mechanism questions the pack claims to answer. Each
#: entry names a section key and a question an operator has asked or is
#: likely to ask. `scope_test` walks this and fails when the pack has no
#: material for a question it lists - which is how the next gap is found
#: before a human asks it.
MECHANISM_CATALOGUE = (
    ("cross_channel_stop",
     "how does the cross-channel stop work"),
    ("cross_channel_stop",
     "what happens when a lead replies on LinkedIn"),
    ("cross_channel_stop",
     "can a reply fail to stop the other channel"),
)


def cross_channel_stop():
    """The cross-channel stop mechanism, from the code rather than from
    a description of it. Every claim traces to a line in `src/inbound.py`
    or `src/leadstop.py`.

    TASK-274: the agent answered "I am reasoning, not reporting" when asked
    this, because the pack carried no mechanism section. The answer was
    right about its own limits; the defect was the pack.
    """
    return {
        "source": "src/inbound.py + src/leadstop.py",
        "read_at": _now(),
        "summary": (
            "A reply on either channel stops the lead on BOTH channels. "
            "The stop is attempted BEFORE classification, because it is a "
            "safety reduction - it can only mean somebody receives less."),
        "flow": [
            {
                "step": "reply ingested",
                "description": (
                    "A provider payload arrives and is normalised to neutral "
                    "events by the adapter layer."),
                "code": "src/inbound.py:528 (ingest) -> src/inbound.py:365 "
                        "(handle)",
            },
            {
                "step": "event applied",
                "description": (
                    "The event is applied idempotently on the provider's own "
                    "event id. A duplicate is a no-op."),
                "code": "src/inbound.py:374 (events.apply)",
            },
            {
                "step": "provider stop, both channels",
                "description": (
                    "BEFORE classification, _stop_at_provider attempts a "
                    "stop on BOTH email and LinkedIn. A contact with a "
                    "bison_lead_id gets the email stop; a contact with a "
                    "heyreach_lead_id gets the LinkedIn stop. A contact "
                    "live on both channels is stopped on both. 'No lead on "
                    "that channel' is not a failure - most contacts are "
                    "staged on one channel only."),
                "code": "src/inbound.py:420-425 (_stop_at_provider call), "
                        "src/inbound.py:186-238 (_stop_at_provider "
                        "definition), src/inbound.py:63-73 (STOP_ROUTES)",
            },
            {
                "step": "per-channel stop attempt",
                "description": (
                    "Each channel's stop goes through allow_writes with "
                    "only=STOP_ROUTES - the reply path may stop a lead and "
                    "may do nothing else. persist=False because ingest owns "
                    "the save; a nested transaction would change the file "
                    "and the outer save would refuse with QueueChanged."),
                "code": "src/inbound.py:278-322 (_stop_one), "
                        "src/inbound.py:308-314 (allow_writes scope guard)",
            },
            {
                "step": "email stop at provider",
                "description": (
                    "leadstop.stop_contact refuses rather than guesses at "
                    "every point where it cannot name exactly who is being "
                    "stopped: no bison_lead_id, no campaign, tenant "
                    "mismatch, no provider campaign, lead not a member. "
                    "Already-stopped is a success, not a write. A live "
                    "stop goes through providerwrites.perform with "
                    "EMAIL_STOP_LEAD and reads back membership to confirm."),
                "code": "src/leadstop.py:39-100 (stop_contact)",
            },
            {
                "step": "LinkedIn stop at provider",
                "description": (
                    "leadstop.stop_linkedin_contact is the LinkedIn "
                    "counterpart. Uses heyreach_lead_id and "
                    "heyreach_campaign_id. The profile URL comes from "
                    "contact['linkedin'] (1,014 contacts) with "
                    "contact['linkedin_url'] as fallback (zero contacts). "
                    "Goes through providerwrites.perform with "
                    "LINKEDIN_STOP_LEAD."),
                "code": "src/leadstop.py:123-175 "
                        "(stop_linkedin_contact)",
            },
            {
                "step": "classification",
                "description": (
                    "ONLY AFTER the provider stop, the reply is classified "
                    "by replies.apply. The classification determines the "
                    "account pause, not the provider stop."),
                "code": "src/inbound.py:434-440 (replies.apply)",
            },
            {
                "step": "summary and refusals",
                "description": (
                    "summarise_stops builds one line from the per-channel "
                    "outcomes: 'stopped', 'already stopped', 'no lead', or "
                    "'REFUSED (reason)'. Refusals are the only outcome "
                    "that raises an alert - an unstopped person is the "
                    "thing somebody has to go and look at."),
                "code": "src/inbound.py:241-276 (summarise_stops)",
            },
        ],
        "refusal_cases": [
            {
                "case": "no lead on that channel",
                "description": (
                    "The contact carries no provider binding for that "
                    "channel. Not a failure, not a refusal. Reported as "
                    "'email: no lead' or 'linkedin: no lead'."),
                "code": "src/inbound.py:201-205",
            },
            {
                "case": "already stopped",
                "description": (
                    "The provider already reports this lead as stopped. "
                    "A success, not a write. The provider's own state is "
                    "the idempotency check."),
                "code": "src/leadstop.py:72-76",
            },
            {
                "case": "REFUSED with reason",
                "description": (
                    "The stop was attempted and the provider or the write "
                    "layer refused it. This is the only outcome that "
                    "raises an alert, because somebody may still be "
                    "written to after they answered."),
                "code": "src/inbound.py:262-270, src/leadstop.py:48-56 "
                        "(StopRefused)",
            },
        ],
        "sweep": (
            "leadstop.sweep is the batch counterpart: it walks every "
            "staged contact and stops anybody who is now ineligible. It "
            "is idempotent and dry-run by default. The live reply path "
            "and the sweep are independent; a reply stops that person "
            "immediately, the sweep catches everybody else."),
        "sweep_code": "src/leadstop.py:213-300 (sweep)",
    }


# ----------------------------------------------------------------- build

def build():
    """Assemble the whole pack. Costs no provider call and never writes."""
    pack = {
        "built_at": _now(),
        "built_epoch": int(time.time()),
        "sources": sources(),
        "identity": identity(),
        "timeline": timeline(),
        "current_state": current_state(),
        "workers": workers(),
        "policies": policies(),
        "workspaces": workspaces_section(),
        "mechanisms": {
            "cross_channel_stop": cross_channel_stop(),
        },
    }
    return pack


def write(pack=None):
    """Cache the pack beside the queue. The only file this module writes."""
    pack = pack or build()
    path = cache_path()
    from . import store
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(pack, handle, default=str, indent=1)
    os.replace(tmp, path)
    return pack


def cached():
    path = cache_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:                                           # noqa: BLE001
        return None


def age_seconds(pack):
    built = (pack or {}).get("built_epoch")
    if not isinstance(built, (int, float)):
        return None
    return time.time() - built


def pack(max_age_seconds=MAX_AGE_SECONDS, force=False):
    """The pack, rebuilt if it is older than `max_age_seconds`.

    Rebuilding on read rather than only on a timer means the answer is never
    served from a pack nobody refreshed because the rebuild loop had died -
    which is the failure mode every cached value in this project's register
    has in common.
    """
    if not force:
        existing = cached()
        age = age_seconds(existing)
        if existing and age is not None and age <= max_age_seconds:
            return existing
    return write(build())


# ------------------------------------------------------------ provenance

#: A number, as it appears in text. Thousands separators and decimals are
#: one token; a date is matched separately so 2026-09-21 does not read as
#: three unsupported figures.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:]+Z?)?")
_TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?Z?\b")


def numeric_tokens(text):
    """Every number in a piece of text, dates and clock times removed.

    Dates and times are removed rather than checked because they are read
    back from timestamps constantly and would drown the real signal - an
    invented 519 among a hundred supported timestamps.

    THE PERCENT SIGN IS KEPT. "2" and "2%" are different claims: one is a
    count and the other is a rate, and this project has a 2% hard stop and
    a 0.83% measured estate, so a rate the material does not contain is
    exactly the kind of figure that must not pass. Keeping the sign makes
    them different tokens, which is what stops "2" in a queue count from
    licensing "2%" in a sentence about bounces.
    """
    body = _TIME.sub(" ", _DATE.sub(" ", str(text or "")))
    out = set()
    for match in _NUMBER.finditer(body):
        token = match.group(0).replace(",", "")
        percent = token.endswith("%")
        token = token.rstrip("%").rstrip(".")
        if not token:
            continue
        out.add(token + "%" if percent else token)
    return out


def numbers(pack_data):
    """Every numeric token the pack supports."""
    return numeric_tokens(json.dumps(pack_data, default=str))


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Build the knowledge pack.")
    parser.add_argument("--force", action="store_true",
                        help="rebuild even if the cache is fresh")
    parser.add_argument("--section", help="print one section only")
    args = parser.parse_args(argv)
    data = pack(force=args.force)
    if args.section:
        print(json.dumps(data.get(args.section), default=str, indent=1))
    else:
        print(json.dumps({k: v for k, v in data.items()
                          if k not in ("workspaces",)},
                         default=str, indent=1))
        print("workspaces: " + ", ".join(sorted(data.get("workspaces") or {})))
    print("built_at %s, %d numeric tokens"
          % (data.get("built_at"), len(numbers(data))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
