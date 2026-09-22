#!/usr/bin/env python3
"""Change requests raised in Slack: recognised, confirmed, ticketed, decided.

OPERATOR, 2026-09-21: "Recognize... confirm the exact intent in thread...
create a ticket in docs/requests/<date>-<id>.md... post it to #resonate-os
as ACTION REQUIRED with an approve / reject prompt for the operator."

## A TICKET IS A RECORD OF A REQUEST, NOT AN INSTRUCTION

Writing one changes nothing about any campaign, lead, provider or policy.
There is no path from this module to a write - it imports the store readers,
the scope and the standard library, and `tests/test_slack_agent_cannot_act.py`
walks the import graph. An approved ticket is picked up by Claude Code, which
executes it through the gates that already exist.

So the thing to get right here is not safety - that is structural - it is
**fidelity**. A ticket built from a guess is worse than no ticket, because it
looks like a record. Everything below exists to make the ticket say exactly
what the person asked for.

## THE TWO-TURN CONTRACT

    turn 1   recognise the kind, extract the target, and RESTATE it
             precisely. Nothing is written.
    turn 2   the requester confirms in the same thread. Only then is the
             ticket written and posted.

The restatement is the point. "Remove lead X" becomes "suppress
X@company.test across this workspace and stop them on both channels in
campaign 491 - confirm and I will raise it for Zvonimir to approve", and a
requester who meant something else says so before anything is recorded.

A request this module cannot pin down does NOT become a vague ticket. It
becomes a question.

## ONLY ONE SLACK USER MAY APPROVE

`SLACK_OPERATOR_USER`. Not "an admin", not "somebody in the internal
channel", not the requester however senior they are in the client's
organisation. An approval from anybody else is recorded as an attempt and
refused, because the whole value of the gate is that it has exactly one key.
"""
import json
import os
import re
import secrets
import time

from . import slackroles as roles
from . import slackscope

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Where tickets live. Tracked in git: a change somebody asked for and a
#: decision somebody made are exactly the durable state CLAUDE.md says
#: belongs in the repository rather than in scrollback.
#:
#: Resolved PER CALL through `requests_dir()`, because a fixture must not be
#: able to write a real ticket. The fake-client harness raised one into
#: `docs/requests/` on its first run and it had to be deleted by hand - a
#: test that leaves an artefact in the repository is a test that will one
#: day leave one nobody notices.
REQUESTS_DIR = os.path.join(ROOT, "docs", "requests")
REQUESTS_DIR_VAR = "SLACK_REQUESTS_DIR"


def requests_dir():
    override = (os.environ.get(REQUESTS_DIR_VAR) or "").strip()
    return os.path.abspath(override) if override else REQUESTS_DIR

#: The worklist the main session drains. Beside the queue like every other
#: piece of runtime state, and derived: the ticket file is the record, this
#: is the worklist pointing at it.
#:
#: NOT "request-queue.jsonl". `tests/test_invariants` refuses any literal
#: containing "queue.jsonl" outside `store`, and it is right to: the queue
#: is one named thing in this repository and a second file whose name reads
#: like it is how somebody ends up pointing the wrong override at the wrong
#: file. This is a journal of requests, so it is named one.
JOURNAL_NAME = "slack-requests.jsonl"
JOURNAL_VAR = "SLACK_REQUESTS"

AWAITING = "awaiting_operator"
APPROVED = "approved"
REJECTED = "rejected"
EXECUTED = "executed"
FAILED = "failed"
WITHDRAWN = "withdrawn"

STATUSES = (AWAITING, APPROVED, REJECTED, EXECUTED, FAILED, WITHDRAWN)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today():
    return time.strftime("%Y-%m-%d", time.gmtime())


def queue_path():
    """Where the request journal lives. Beside the queue, override-able."""
    override = (os.environ.get(JOURNAL_VAR) or "").strip()
    if override:
        return os.path.abspath(override)
    try:
        from . import store
        return os.path.join(os.path.dirname(store.queue_path()), JOURNAL_NAME)
    except Exception:                                           # noqa: BLE001
        return os.path.join(ROOT, "work", JOURNAL_NAME)


# ------------------------------------------------------------ recognition
#
# Each kind carries the patterns that recognise it and the fields it needs
# before a ticket may be written. A kind whose required fields are not all
# present becomes a QUESTION, never a ticket.

EMAIL = r"[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}"
DOMAIN = r"[a-z0-9][a-z0-9.-]*\.[a-z]{2,}"

KINDS = {
    "remove_lead": {
        "label": "Remove a lead from outreach",
        "client_effect": ("they are added to your suppression list and stopped on both email and LinkedIn, so nothing further reaches them."),
        "needs": ("lead",),
        "executes": ("Add the contact to this workspace's suppression list, "
                     "then stop the lead at the provider on BOTH channels - "
                     "email and LinkedIn - through the existing stop verbs "
                     "with their fail-closed readbacks. The queue record is "
                     "dropped with a reason, never deleted."),
        "patterns": (
            r"\bremove\b[^.]*?\blead\b",
            r"\bremove\b\s+(?:" + EMAIL + r")",
            r"\btake\b[^.]*\boff\b[^.]*\b(?:campaign|sequence|list)\b",
            r"\bunsubscribe\b[^.]*\b(?:lead|contact|person)\b",
        ),
    },
    "stop_account": {
        "label": "Stop contacting an account",
        "client_effect": ("the whole company is marked do-not-contact for you: everyone at it is stopped on both channels and it is excluded from future sourcing."),
        "needs": ("account",),
        "executes": ("Mark the account do-not-contact for this workspace, "
                     "suppress every contact at it, and stop each of them at "
                     "the provider on both channels. Future sourcing "
                     "excludes the domain."),
        "patterns": (
            r"\bstop\b[^.]*\bcontact",
            r"\b(?:do not|don'?t)\s+contact\b",
            r"\bdnc\b",
            r"\bblacklist\b|\bblocklist\b",
        ),
    },
    "change_copy": {
        "label": "Change approved copy",
        "client_effect": ("nothing changes yet. The wording is recorded for review, because live copy has already been approved and new words need approving again before they go out."),
        "needs": ("cadence_or_campaign", "step", "new_text"),
        "executes": ("NOTHING is applied. The proposed wording is recorded "
                     "for review. Changing approved live copy is "
                     "operator-gated and re-approval is required, because an "
                     "approval is fingerprinted against the words it "
                     "covered - new words make the old approval stale."),
        "patterns": (
            r"\bchange\b[^.]*\b(?:copy|message|wording|text|subject|note)\b",
            r"\b(?:connection|invite|intro)\s+(?:message|note)\b",
            r"\brewrite\b[^.]*\bstep\b",
            r"\bstep\s*\d+[^.]*\b(?:copy|message|text|wording)\b",
        ),
    },
    "pause_campaign": {
        "label": "Pause a campaign",
        "client_effect": ("the campaign stops sending. Everyone already in it stays in it, and it can be resumed."),
        "needs": ("campaign",),
        "executes": ("Pause the campaign at the provider through the guarded "
                     "pause verb, with a readback confirming the provider "
                     "agrees it is paused. Enrolled leads stay enrolled."),
        "patterns": (
            r"\bpause\b[^.]*\bcampaign\b",
            r"\bpause\b\s+\d{3,6}\b",
            r"\b(?:halt|hold|freeze)\b[^.]*\bcampaign\b",
        ),
    },
    "add_lead": {
        "label": "Add a lead",
        "client_effect": ("they enter the pipeline at the start and have to clear every check - fit, deliverability, two verifications and a look at whether we or you have contacted them recently - before any message is drafted for them."),
        "needs": ("lead",),
        "executes": ("Nothing is enrolled directly. The contact enters the "
                     "pipeline at qualification and must clear every gate - "
                     "ICP, MX, two verifications, collision, suppression and "
                     "copy - before it can reach a campaign."),
        "patterns": (
            r"\badd\b[^.]*\b(?:lead|contact|person|prospect)\b",
            r"\benrol{1,2}\b[^.]*\b(?:lead|contact|person)\b",
        ),
    },
    "change_window": {
        "label": "Change a sending window",
        "client_effect": ("new sends follow the new hours. Anything already scheduled keeps the slot it was given."),
        "needs": ("window",),
        "executes": ("Update the workspace's sending window, then re-read it "
                     "from the provider for every affected campaign. A "
                     "window change does not move mail that is already "
                     "scheduled: the send date is a property of the mailbox."),
        "patterns": (
            r"\b(?:change|move|shift|adjust)\b[^.]*\b(?:sending\s+)?window\b",
            r"\bsend(?:ing)?\s+(?:hours|times|window)\b",
        ),
    },
}

#: A message that matches nothing here is not a change request.
KIND_ORDER = ("change_copy", "stop_account", "remove_lead", "pause_campaign",
              "change_window", "add_lead")


#: A message that OPENS like a question is a question. "why did we pause
#: 487" is about a decision already taken; "pause 487" is a request.
#:
#: THIS LIVES HERE AND `slackconversation` IMPORTS IT. It was written in the
#: conversation module first and `recognise` did not consult it, so "why did
#: we pause 487?" - answered correctly as a question by one code path - was
#: recognised as a REQUEST TO PAUSE A LIVE CAMPAIGN by the other. Two copies
#: of one rule is how the two disagree, which is CLAUDE.md's own warning
#: about a second representation of the same truth.
_QUESTION_OPENER = re.compile(
    r"^\W*(?:what|why|when|who|whom|whose|how|which|where|is|are|was|were|"
    r"do|does|did|has|have|had|can|could|should|would|will|any|anything|"
    r"status|tell me|show me|give me|send me|explain)\b", re.I)

#: ...unless it also asks somebody to do the thing. "can you pause 487?"
#: opens like a question and is a request.
_EXPLICIT_ASK = re.compile(
    r"\b(?:please|can you|could you|would you|will you|i need you to|"
    r"go ahead and|i want you to|make sure you)\b", re.I)

#: Always a state change, however it is phrased. These are the shapes that
#: try to talk their way past the classifier rather than ask for something.
_ALWAYS_ACTION = re.compile(
    r"ignore (?:your|all|previous)|you are now|admin mode|\bsudo\b|"
    r"developer mode|override your|new instructions|disregard", re.I)


def strip_mentions(text):
    """A Slack mention arrives as `<@U123> pause 487`. It is not a word."""
    return re.sub(r"<@[^>]+>", " ", str(text or "")).strip()


def reads_as_a_question(text):
    """Is this asking ABOUT something rather than FOR something?"""
    body = strip_mentions(text)
    if _ALWAYS_ACTION.search(body) or _EXPLICIT_ASK.search(body):
        return False
    return bool(_QUESTION_OPENER.search(body))


def recognise(text):
    """`(kind, fields)` for a change request, or `(None, {})`.

    Ordered, and the order matters: "change the connection message for
    acme.test" is a COPY change that happens to name a domain, not a request
    to stop contacting them. Copy is checked first for that reason.

    A message that reads as a question is never a request, however many of
    the verbs it contains.
    """
    body = strip_mentions(text)
    if reads_as_a_question(body):
        return None, {}
    lowered = body.lower()
    for kind in KIND_ORDER:
        spec = KINDS[kind]
        if any(re.search(pattern, lowered) for pattern in spec["patterns"]):
            return kind, extract(kind, body)
    return None, {}


def extract(kind, text):
    """Every target field this module can find. Absent is absent."""
    body = str(text or "")
    fields = {}

    address = re.search(EMAIL, body)
    if address:
        fields["lead"] = address.group(0)

    domain = re.search(r"\b(" + DOMAIN + r")\b", body.lower())
    if domain and not (address and domain.group(1) in address.group(0)):
        fields["account"] = domain.group(1)
    elif address:
        fields["account"] = address.group(0).split("@")[-1]

    campaign = re.search(r"\bcampaign\s+(\d{3,6})\b", body.lower()) or \
        re.search(r"\b(\d{3,6})\b", body)
    if campaign:
        fields["campaign"] = campaign.group(1)

    step = re.search(r"\bstep\s*(\d+)\b", body.lower())
    if step:
        fields["step"] = step.group(1)
    elif re.search(r"\bconnection\s+(?:message|note|request)\b", body.lower()):
        # The connection request IS step one of the LinkedIn graph, and
        # naming it by its own name is how a person refers to it.
        fields["step"] = "linkedin connection request"

    cadence = re.search(r"\bcadence\s+([a-z0-9_]+)\b", body.lower())
    if cadence:
        fields["cadence_or_campaign"] = cadence.group(1)
    elif fields.get("campaign"):
        fields["cadence_or_campaign"] = "campaign %s" % fields["campaign"]

    window = re.search(r"(\d{1,2}:\d{2})\s*(?:-|to|until|–)\s*(\d{1,2}:\d{2})",
                       body)
    if window:
        fields["window"] = "%s-%s" % (window.group(1), window.group(2))

    quoted = re.search(r"[\"“”']{1}(.{6,400}?)[\"“”']{1}", body, re.S)
    if quoted:
        fields["new_text"] = quoted.group(1).strip()
    else:
        after = re.search(r"\bto\s*:?\s*(.{10,400})$", body, re.S)
        if after and kind == "change_copy":
            fields["new_text"] = after.group(1).strip()

    return fields


def missing(kind, fields):
    """Which required fields this request has not pinned down."""
    return [name for name in KINDS[kind]["needs"] if not fields.get(name)]


#: Which target a kind must OWN before it may be ticketed from a client
#: channel, and the tool that answers "is this yours".
#:
#: Without this a client could raise "remove lead mole@another-client.test"
#: in their own channel: the ticket would be scoped to THEIR workspace and
#: name somebody else's person, and executing it would reach into another
#: client's estate through a gate that had checked the wrong thing. The
#: reading filter does not cover it, because the target arrives in the
#: MESSAGE rather than out of the store.
#:
#: `stop_account`, `add_lead` and `change_window` are deliberately not here.
#: A client may pre-emptively name a domain they never want contacted, may
#: give us somebody new, and may change their own window - none of those is
#: a claim about an existing record.
OWNERSHIP = {
    "remove_lead": "lead",
    "pause_campaign": "campaign",
    "change_copy": "cadence_or_campaign",
}


class NotYours(PermissionError):
    """The target is not in this workspace. Says nothing about whose it is."""


def check_ownership(kind, fields, scope):
    """Raise `NotYours` if a client is targeting something not theirs.

    THE MESSAGE IS THE SAME whether the target belongs to another client or
    to nobody at all. "I cannot find that in your workspace" is true in both
    cases, and an answer that distinguished them would confirm the other
    client's record exists - which is the disclosure, not the removal.
    """
    if not scope.is_client:
        return
    field = OWNERSHIP.get(kind)
    if not field or not fields.get(field):
        return
    target = str(fields[field])
    if _owns(scope.workspace, kind, target):
        return
    raise NotYours(
        "I cannot find %s in your workspace, so I have not raised anything. "
        "If it should be there, the Resonate team can check it for you."
        % target)


def _owns(slug, kind, target):
    from . import slackagenttools as tools
    if kind == "remove_lead":
        return bool(tools._find_contacts(slug, target.lower(), limit=1))
    rows = tools._campaign_rows(slug)
    if kind == "pause_campaign":
        wanted = str(target).strip()
        return any(wanted in (str(r.get("bison_campaign_id")),
                              str(r.get("heyreach_campaign_id")),
                              str(r.get("campaign_id")))
                   for r in rows)
    # change_copy: a cadence name this workspace runs, or one of its
    # campaigns named directly.
    lowered = str(target).lower()
    if any(lowered in (str(r.get("campaign_id")).lower(),
                       ("campaign %s" % r.get("bison_campaign_id")).lower())
           for r in rows):
        return True
    try:
        from . import clients
        config = clients.load(slug) or {}
    except Exception:                                           # noqa: BLE001
        return False
    return str(config.get("cadence") or "").lower() == lowered


#: What to ask for, per field, in a person's words.
ASK_FOR = {
    "lead": "which person - their email address",
    "account": "which account - the domain",
    "campaign": "which campaign - its id",
    "cadence_or_campaign": "which cadence or campaign",
    "step": "which step",
    "new_text": "the exact new wording, in quotes",
    "window": "the new window, as HH:MM-HH:MM",
}


def question_for(kind, fields):
    """The clarifying question, when a request is not yet pinned down."""
    wants = [ASK_FOR[name] for name in missing(kind, fields)]
    if not wants:
        return None
    known = ", ".join("%s %s" % (k, v) for k, v in sorted(fields.items())
                      if k in ASK_FOR)
    lead = "I can raise that as a change request for approval. "
    if known:
        lead += "I have %s. " % known
    return lead + "I still need %s." % _join(wants)


def restate(kind, fields, workspace, client_facing=False):
    """The exact intent, in one paragraph, for the requester to confirm.

    `client_facing` changes two things and neither is cosmetic. It does not
    name the operator - who decides inside Resonate is not a client's
    business - and it does not describe the provider mechanics of what
    executing it would do. A client is owed a plain statement of the effect
    on THEIR outreach; "the existing stop verbs with their fail-closed
    readbacks" is a sentence about our machinery.
    """
    spec = KINDS[kind]
    parts = ["**%s** for %s." % (spec["label"], workspace)]
    for name in ("lead", "account", "campaign", "cadence_or_campaign",
                 "step", "window"):
        if fields.get(name):
            parts.append("%s: %s." % (name.replace("_", " ").title(),
                                      fields[name]))
    if fields.get("new_text"):
        parts.append("Proposed wording: “%s”" % fields["new_text"])
    if client_facing:
        parts.append("If it goes ahead: %s" % spec["client_effect"])
        parts.append("Nothing happens until the Resonate team has reviewed "
                     "it. Confirm and I will pass it on.")
    else:
        parts.append("If approved, this is what happens: %s"
                     % spec["executes"])
        parts.append("Nothing is done until Zvonimir approves it. "
                     "Confirm and I will raise it.")
    return " ".join(parts)


def _join(items):
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


#: A confirmation. Deliberately narrow: "yes", "confirmed", "go ahead",
#: "raise it". A message that is not clearly a yes is NOT a yes - it is the
#: requester saying something else, and the pending request stays pending.
CONFIRM = re.compile(
    r"^\W*(?:yes|yep|yup|confirm(?:ed|s)?|correct|that'?s right|go ahead|"
    r"raise it|please do|do it|approved by me|ok|okay)\b", re.I)

#: And a clear no, so a pending request can be dropped rather than hang.
DECLINE = re.compile(
    r"^\W*(?:no|nope|cancel|forget it|never ?mind|drop it|withdraw)\b", re.I)


def is_confirmation(text):
    return bool(CONFIRM.match(re.sub(r"<@[^>]+>", " ", str(text or "")).strip()))


def is_decline(text):
    return bool(DECLINE.match(re.sub(r"<@[^>]+>", " ", str(text or "")).strip()))


# ------------------------------------------------------------- the ticket

def new_id():
    """`<date>-<four hex>`. Short enough to type in `approve <id>`."""
    return "%s-%s" % (_today(), secrets.token_hex(2))


def build(kind, fields, requester, channel, scope, thread_ts=None,
          original=""):
    authority, note = _authority(kind, requester, scope)
    return {
        "id": new_id(),
        "kind": kind,
        # WHO THIS CAME FROM, kept as its own field rather than inferred
        # from `requester_scope` at read time. An operator triaging a queue
        # needs "a client asked for this" to be the first thing they see,
        # and a derived value is one refactor away from not being there.
        "origin": "client" if scope.is_client else "internal",
        "label": KINDS[kind]["label"],
        "raised_at": _now(),
        "requester": requester,
        "requester_scope": scope.kind,
        # WHO THEY ARE INSIDE THE CLIENT, for the operator's eyes only.
        # It never decides whether the ticket is raised - see
        # `slackroles`, whose first rule is that a request reducing reach
        # is taken from anybody, always.
        "requester_authority": authority,
        "authority_note": note,
        "channel": channel,
        "workspace": scope.workspace or "internal",
        "thread_ts": thread_ts,
        "fields": dict(fields),
        "executes": KINDS[kind]["executes"],
        "original_message": str(original or "")[:1000],
        "status": AWAITING,
        "decided_by": None,
        "decided_at": None,
        "decision_note": None,
        "outcome": None,
    }


def _authority(kind, requester, scope):
    try:
        return roles.authority_note(kind, requester, scope)
    except Exception:                                           # noqa: BLE001
        # A role register that cannot be read must not stop a ticket being
        # written. Unknown authority is exactly what the default says.
        return "not recorded", None


def path_for(ticket):
    return os.path.join(requests_dir(), "%s.md" % ticket["id"])


def render(ticket):
    """The ticket file. Markdown, because a person reads it."""
    fields = ticket.get("fields") or {}
    lines = [
        "# %s — %s" % (ticket["id"], ticket["label"]),
        "",
        "    requester   %s (%s scope)" % (ticket["requester"],
                                           ticket["requester_scope"]),
    ]
    if ticket.get("requester_authority"):
        # ABSENT MEANS "RAISED BEFORE ROLES EXISTED", which is not the same
        # claim as "not recorded" - that one is a statement about an empty
        # register, and putting it on a ticket from last week would be the
        # agent asserting something it never checked.
        lines.append("    authority   %s" % ticket["requester_authority"])
    lines += [
        "    channel     %s" % ticket["channel"],
        "    workspace   %s" % ticket["workspace"],
        "    raised_at   %s" % ticket["raised_at"],
        "    kind        %s" % ticket["kind"],
        "    status      %s" % ticket["status"],
        "",
        "## The exact change",
        "",
    ]
    for name in ("lead", "account", "campaign", "cadence_or_campaign",
                 "step", "window"):
        if fields.get(name):
            lines.append("- **%s**: %s" % (name.replace("_", " "),
                                           fields[name]))
    if fields.get("new_text"):
        lines += ["", "Proposed new text, as given by the requester and "
                      "NOT applied:", "", "> %s" % fields["new_text"]]
    lines += ["", "## What executing it would do", "",
              ticket["executes"], "",
              "## As it was asked", "",
              "> %s" % ticket.get("original_message", ""), "",
              "## Decision", ""]
    if ticket.get("decided_by"):
        lines.append("%s by %s at %s." % (ticket["status"].upper(),
                                          ticket["decided_by"],
                                          ticket["decided_at"]))
        if ticket.get("decision_note"):
            lines += ["", "> %s" % ticket["decision_note"]]
    else:
        lines.append("Awaiting the operator. `approve %s` or `reject %s` "
                     "in the internal channel, from the operator's own "
                     "Slack id and nobody else's."
                     % (ticket["id"], ticket["id"]))
    if ticket.get("outcome"):
        lines += ["", "## Outcome", "", ticket["outcome"]]
    lines.append("")
    return "\n".join(lines)


def write(ticket):
    """The ticket file and its queue row. The only files this writes."""
    from . import store
    path = path_for(ticket)
    store.refuse_production_write(path)
    os.makedirs(requests_dir(), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(render(ticket))
    os.replace(tmp, path)
    _append_queue(ticket)
    return path


def _append_queue(ticket):
    from . import store
    path = queue_path()
    # BEFORE `makedirs`, not after. The refusal has to land before any
    # filesystem mutation, which is what `refuse_production_write`'s own
    # docstring says and why it is called here rather than at the open.
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(ticket, at=_now()), default=str) + "\n")


def load():
    """Every ticket, newest state last. Rebuilt from the queue journal.

    The journal is APPEND-ONLY and the latest row per id wins, which is the
    same shape every other state file here uses. The markdown file is the
    human record; this is the machine one, and they are written together.
    """
    path = queue_path()
    if not os.path.isfile(path):
        return []
    latest = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id"):
                latest[row["id"]] = row
    return sorted(latest.values(), key=lambda r: str(r.get("raised_at")))


def get(ticket_id):
    for row in load():
        if row.get("id") == ticket_id:
            return row
    return None


def pending():
    return [r for r in load() if r.get("status") == AWAITING]


def approved_unexecuted():
    """What the main session has to do. The handoff, in one call."""
    return [r for r in load() if r.get("status") == APPROVED]


# ------------------------------------------------------------- decisions

#: A ticket id has a KNOWN SHAPE, and matching it is what stopped
#: `approve 2026-09-21-7008` from being read as ticket `2026` with the note
#: "09-21-7008". The first version used `(\S+?)` and let a hyphen end the
#: id, which is every id this module generates.
TICKET_ID = r"\d{4}-\d{2}-\d{2}-[0-9a-fA-F]{4}"

#: The note is separated by a SPACED dash, an em dash or a colon. An
#: unspaced hyphen is part of the id.
DECISION = re.compile(
    r"^\W*(approve|reject)\s+`?(" + TICKET_ID + r")`?"
    r"(?:\s*(?:[-–—:]|\bbecause\b)\s*(.*))?$",
    re.I | re.S)


def parse_decision(text):
    """`(verb, ticket id, note)` or None. Not a fuzzy match.

    A message that says `approve` and does not carry a well-formed ticket
    id is NOT a decision. It returns None and is answered as an ordinary
    message, because guessing which request somebody meant is the one
    mistake an approval gate may not make.
    """
    body = re.sub(r"<@[^>]+>", " ", str(text or "")).strip()
    match = DECISION.match(body)
    if not match:
        return None
    return (match.group(1).lower(), match.group(2).strip(),
            (match.group(3) or "").strip() or None)


class NotTheOperator(PermissionError):
    """Somebody who is not the operator tried to decide a request."""


def operator_id():
    return (os.environ.get(slackscope.OPERATOR_USER_VAR) or "").strip() or None


def decide(ticket_id, verb, user, note=None):
    """Approve or reject. Refuses anybody but the operator.

    A refusal is RECORDED against the ticket as an attempt rather than
    silently dropped: somebody trying to approve their own request is
    exactly the thing the person reading this file later needs to see.
    """
    ticket = get(ticket_id)
    if ticket is None:
        raise KeyError("no request %r" % ticket_id)
    expected = operator_id()
    if not expected:
        raise NotTheOperator(
            "no operator is configured (%s is unset), so nothing can be "
            "approved. That is the safe failure."
            % slackscope.OPERATOR_USER_VAR)
    if user != expected:
        attempt = dict(ticket, decision_attempt_by=user,
                       decision_attempt_at=_now())
        _append_queue(attempt)
        raise NotTheOperator(
            "%s is not the operator. Only the operator's own Slack id may "
            "approve a change request." % user)
    if ticket["status"] != AWAITING:
        raise ValueError("request %s is already %s"
                         % (ticket_id, ticket["status"]))
    ticket = dict(ticket,
                  status=APPROVED if verb == "approve" else REJECTED,
                  decided_by=user, decided_at=_now(), decision_note=note)
    write(ticket)
    return ticket


def record_outcome(ticket_id, outcome, status=EXECUTED):
    """What Claude Code did, written back onto the ticket."""
    ticket = get(ticket_id)
    if ticket is None:
        raise KeyError("no request %r" % ticket_id)
    if status not in STATUSES:
        raise ValueError("unknown status %r" % status)
    ticket = dict(ticket, status=status, outcome=str(outcome)[:2000],
                  executed_at=_now())
    write(ticket)
    return ticket


# ------------------------------------------------------------- the posts

def action_required(ticket):
    """The ACTION REQUIRED message for the internal channel."""
    fields = ticket.get("fields") or {}
    detail = "; ".join("%s %s" % (k.replace("_", " "), v)
                       for k, v in sorted(fields.items())
                       if k != "new_text")
    client = ticket.get("origin") == "client"
    lines = ["*ACTION REQUIRED* — change request `%s`%s"
             % (ticket["id"], "  ·  *client-originated*" if client else ""),
             ""]
    if client:
        # THE FIRST THING THE OPERATOR SEES. A request from outside
        # Resonate is decided on different grounds from one raised
        # internally, and burying that in a scope field further down would
        # make the two look alike in the one place they must not.
        lines.append(":inbox_tray: Raised by an EXTERNAL person in the "
                     "client's own channel. They have been told it is with "
                     "the Resonate team, and given no timescale.")
        lines.append("")
    lines.append("*%s* for *%s*, raised by <@%s> in <#%s>."
                 % (ticket["label"], ticket["workspace"],
                    ticket["requester"], ticket["channel"]))
    if detail:
        lines.append(detail)
    note = ticket.get("authority_note")
    if note:
        # ON THE TICKET AND IN HERE, NEVER IN THE CLIENT'S CHANNEL. What
        # the client hears is unchanged: it is with the Resonate team, no
        # timescale. Telling somebody in front of their colleagues that
        # they may not ask is not the agent's to do.
        lines += ["", ":bust_in_silhouette: %s" % note]
    if fields.get("new_text"):
        lines += ["", "Proposed wording (NOT applied):",
                  "> %s" % fields["new_text"][:600]]
    lines += ["", "If approved: %s" % ticket["executes"],
              "",
              "Reply `approve %s` or `reject %s`. Only the operator's id "
              "counts." % (ticket["id"], ticket["id"]),
              "Ticket: `docs/requests/%s.md`" % ticket["id"]]
    return "\n".join(lines)


def decision_note_for(ticket):
    """What gets posted back into the original thread."""
    client = ticket.get("origin") == "client"
    if ticket["status"] == APPROVED:
        text = ("The Resonate team have approved this. It is queued to be "
                "carried out and I will post here when it is done."
                if client else
                "Approved. It is queued for Claude Code to execute through "
                "the usual gates, and I will report back here when it is "
                "done.")
    elif ticket["status"] == REJECTED:
        text = ("The Resonate team have not approved this, so nothing has "
                "changed. They will follow up with you directly."
                if client else
                "This was not approved, so nothing has changed.")
    elif ticket["status"] == EXECUTED:
        text = "Done. %s" % (ticket.get("outcome") or "")
    elif ticket["status"] == FAILED:
        text = ("This could not be completed. %s"
                % (ticket.get("outcome") or ""))
    else:
        text = "Status is now %s." % ticket["status"]
    if ticket.get("decision_note"):
        text += " Note from the operator: “%s”" % \
            ticket["decision_note"]
    if ticket.get("origin") == "client":
        return "About your request (%s) — %s" % (
            ticket.get("label", "change request").lower(), text)
    return "Change request `%s` — %s" % (ticket["id"], text)
