#!/usr/bin/env python3
"""HeyReach. BUILD-SPEC section 5.5.

Base https://api.heyreach.io/api/public, header X-API-KEY.
GET /auth/CheckApiKey is the health check.

Phase 3 is auth, health and the request builder only. There is deliberately no
send function here: AddLeadsToCampaignV2 is phase 7, behind the explicit --live
rule. The builder produces the accountLeadPairs shape documented in section 5.5.

  python -m src.providers.heyreach --check
"""
import argparse
import json
import re
import urllib.parse

from . import ProviderError, failed, key, mapping, ok, request, result

BASE = "https://api.heyreach.io/api/public"


def headers():
    return {"X-API-KEY": key("HEYREACH_KEY")}


def build_lead_pairs(rows, linkedin_account_id):
    """Rows with a LinkedIn URL into accountLeadPairs. Pure: sends nothing.

    Our own identifiers travel in `customUserFields` beside the note. They were
    not there before, and `src/adapters.py` has always read `record_id` and
    `contact_key` off an inbound conversation - so that branch could never fire
    and every LinkedIn reply fell through to URL matching whether or not the
    provider could have told us exactly who it was.

    This does **not** make them a correlation key. Confirmed live on
    2026-08-26, HeyReach returns `customFields: []` on every conversation and
    `/lead/GetLead` exposes none at all, so the canonical profile URL remains
    the thing replies are matched on and `src/linkedin.py` remains load-bearing.
    What sending them buys is real but smaller: a person looking at a lead in
    HeyReach's own UI can see which record it came from, and if the provider
    ever does echo them back, the better key is already there.

    `note` stays first. The push CLI prints `customUserFields[0]` and a test
    asserts the note is what travels there.
    """
    return [{
        # Per row, not per push. A LinkedIn sender is assigned per contact and
        # sticks to them, so a single account id for the whole batch would
        # send every prospect from whichever profile the caller happened to
        # name - which is exactly the "who is writing to me" confusion the
        # sticky assignment exists to prevent. The argument stays as the
        # fallback for a row with no assignment and for callers that predate
        # the sender model.
        "linkedInAccountId": _account_id_for(r, linkedin_account_id),
        "lead": {
            "profileUrl": r["linkedin_url"],
            "firstName": r.get("first_name", ""),
            "lastName": r.get("last_name", ""),
            "companyName": r.get("company", ""),
            "position": r.get("title", ""),
            "customUserFields": [
                {"name": "note", "value": r.get("note", "")},
            ] + [{"name": name, "value": str(r[name])}
                 for name in ("record_id", "contact_key", "client",
                              # Which human owns this LinkedIn relationship.
                              # HeyReach returns customFields: [] on every
                              # conversation - confirmed live 2026-08-26 - so
                              # nothing reads these back and the canonical
                              # profile URL remains the correlation key.
                              # They are sent so a person in HeyReach's own UI
                              # can see who owns the lead.
                              "sender_id", "sender_account_id")
                 if r.get(name)] + [
                # Whatever this campaign's own copy asks for. HeyReach
                # sequences may reference any custom field name - campaign
                # 565765 uses `{Icebreaker}` - and a name we do not send is
                # not an error there: HeyReach substitutes the fallback and
                # the prospect gets copy this system did not write. So the
                # names are not enumerated here. They come from the row,
                # `refuse_unsupported_sequence` checks the live sequence
                # against what this actually produces, and the mapping from
                # our fields to a campaign's variable names is a client
                # decision rather than something this module may invent.
                {"name": str(name), "value": str(value)}
                for name, value in sorted((r.get("custom_fields") or {}).items())
                if value not in (None, "")],
        },
    } for r in rows]


def _account_id_for(row, fallback):
    """The HeyReach account this row goes out from.

    HeyReach's own id is an integer. Our `provider_account_id` holds whatever
    the roster recorded, which may be a string, so it is coerced here and the
    fallback is used when it is not a number at all - guessing an account id
    would send a prospect from a profile nobody chose.
    """
    candidate = row.get("provider_account_id")
    if candidate not in (None, ""):
        try:
            return int(candidate)
        except (TypeError, ValueError):
            pass
    return int(fallback or 0)


def add_leads_endpoint():
    """The URL phase 7 will POST to. Named here so it is reviewable."""
    return f"{BASE}/campaign/AddLeadsToCampaignV2"


# --------------------------------------------------------- inbound events
#
# Confirmed live on 2026-08-26, read-only:
#
#   POST /campaign/GetAll        {offset, limit} -> {items, totalCount}
#   POST /inbox/GetConversationsV2 {filters, offset, limit}
#                                                -> {items, totalCount}
#
# Confirmed absent, so not guessed at: /linkedinaccount/GetAll and
# /webhooks/GetAll both answer 404, and GET /campaign/GetAll answers 405. The
# sender accounts come from a campaign's own `campaignAccountIds` instead,
# which is what mapping validation actually needs.
#
# These are POST endpoints that read. That is why this module is allowed a POST
# at all, and why READ_ROUTES below is an explicit allowlist: the send route,
# AddLeadsToCampaignV2, is deliberately not in it, and a test enforces that.
#
# Same trap as EmailBison: a conversation carries our own outgoing messages
# too. `lastMessageSender` says who spoke last, and only a message from the
# correspondent is a reply.

EVENTS_CONTRACT_CONFIRMED = True          # for reading. Sending is not.

# Connection acceptance: NOT identifiable from this endpoint, confirmed over
# 100 conversations. The only field whose name suggests it,
# `correspondentProfile.connections`, is an integer follower/connection count,
# not a status. No acceptedAt, no connectionStatus, no invitation state, and a
# conversation exists whether or not a request was accepted.
#
# So connection_accepted is not inferred here. The neutral event still exists
# and a webhook that declares one is mapped; what is refused is guessing it
# from an inbox row. Inferring acceptance wrongly would unlock the day-8
# LinkedIn follow-up for someone who never accepted, which reads to them as a
# stranger messaging out of nowhere.
CONNECTION_STATUS_AVAILABLE = False

READ_ROUTES = ("/campaign/GetAll", "/inbox/GetConversationsV2")

# Every route this module may POST to. All four read; none mutates.
#
# `/li_account/GetAll` is added here rather than to `READ_ROUTES` above because
# that tuple is pinned by an exact-set assertion in `tests/test_audit.py`, and
# that assertion is about the two routes the event contract rests on. This one
# is a sender-inventory read, which is a different question.
#
# It is the route that answers which LinkedIn seats exist. A comment in this
# module used to say sender accounts were unavailable because
# `/linkedinaccount/GetAll` answers 404 - true, and it was the wrong route
# name rather than an absent capability.
READ_ROUTES_ALL = READ_ROUTES + ("/lead/GetLead", "/li_account/GetAll")

# Read-only GETs. Separate from the POST allowlist above because these take
# their argument in the query string, not a body.
#
# `GET /campaign/GetCampaignSequence?campaignId=` answers 200 with the whole
# node graph - every step, delay, message variant and fallback. That matters
# more than it looks: `AddLeadsToCampaignV2` adds a lead to a campaign whose
# sequence is configured in HeyReach, so until this route was found there was
# no way for this system to know what a lead it pushed would actually be sent.
# A comment here previously said `POST /campaign/GetById` answers 405, which
# is true and incomplete - it is a GET.
READ_GET_ROUTES = ("/campaign/GetCampaignSequence", "/campaign/GetById")

# Confirmed live: limit=200 answers 400, limit=100 answers 200. Asking for
# more than this does not return more, it returns nothing - and a lookup that
# always errors degrades every mapping check to "provider unreachable", which
# looks like an outage rather than the bug it is.
MAX_PAGE = 100


class EventContractNotConfirmed(ProviderError):
    """Raised when a route outside READ_ROUTES is asked for."""


def events_contract():
    return {
        "provider": "heyreach",
        "confirmed": EVENTS_CONTRACT_CONFIRMED,
        "base": BASE,
        "polling": "confirmed live: POST /inbox/GetConversationsV2, paged by "
                   "offset",
        "webhook": "no webhook management on the confirmed surface "
                   "(/webhooks/GetAll answers 404). Polling is the transport",
        "absent": "/linkedinaccount/GetAll answers 404; sender accounts come "
                  "from a campaign's own campaignAccountIds",
        "mapping": "src/adapters.from_heyreach, written against a real page",
        "hazard": "a conversation carries our own messages. lastMessageSender "
                  "must be the correspondent for it to be a reply",
    }

# Direction, confirmed live over 600 conversations on 2026-08-26. The field
# takes exactly two values and nothing else was ever seen:
#
#   ME            we sent it
#   CORRESPONDENT they sent it
#
# This is an ALLOWLIST, and the polarity is the safety property. An earlier
# version asked "is this NOT one of ours?", which meant any value HeyReach
# might add later - SYSTEM, TEAMMATE, AUTOMATION - would have been read as a
# prospect reply and would have paused the company. Only CORRESPONDENT is
# inbound; ME is ours; anything else is unknown and dropped.

THEIRS = "theirs"
OURS = "ours"
UNKNOWN = "unknown"

CORRESPONDENT = "correspondent"
ME = "me"


def direction(value):
    """Who sent this? theirs | ours | unknown. Never guessed."""
    sender = str(value or "").strip().lower()
    if sender == CORRESPONDENT:
        return THEIRS
    if sender == ME:
        return OURS
    return UNKNOWN


def is_from_correspondent(conversation):
    """Did the other person send the LAST message in this thread?

    Kept because it is a useful question, but it is not how replies are found:
    8 threads in 100 carry a prospect reply that we then answered, so the last
    message is ours and the reply would be missed. inbound_messages() is what
    the adapter uses.
    """
    return direction(mapping(conversation, "heyreach conversation")
                     .get("lastMessageSender")) == THEIRS


def inbound_messages(conversation):
    """Every message in this thread that the prospect sent.

    A conversation is a thread, not an event. Scanning it is what catches a
    reply we have since answered - and `messages` was complete on every one of
    100 sampled conversations, so there is nothing to page through.
    """
    conversation = mapping(conversation, "heyreach conversation")
    out = []
    for message in conversation.get("messages") or []:
        if not isinstance(message, dict):
            continue
        if direction(message.get("sender")) == THEIRS:
            out.append(message)
    if out or conversation.get("messages"):
        return out
    # No message list at all: fall back to the thread summary, and only when
    # it is positively theirs.
    if direction(conversation.get("lastMessageSender")) == THEIRS:
        return [{"body": conversation.get("lastMessageText"),
                 "createdAt": conversation.get("lastMessageAt"),
                 "sender": conversation.get("lastMessageSender")}]
    return []


def unknown_directions(conversation):
    """Messages whose sender this code does not recognise. Counted, dropped."""
    return [m for m in mapping(conversation, "heyreach conversation")
                          .get("messages") or []
            if isinstance(m, dict) and direction(m.get("sender")) == UNKNOWN]


def _read_get(path, params):
    """A GET that reads. Refuses any route not on the GET allowlist."""
    if path not in READ_GET_ROUTES:
        raise ProviderError(
            f"heyreach: {path} is not a read-only GET route. This module gets "
            f"only {', '.join(READ_GET_ROUTES)}.")
    query = urllib.parse.urlencode(params or {})
    status, data = request("GET", f"{BASE}{path}?{query}", headers(), None)
    if not ok(status):
        raise ProviderError(f"heyreach {path}: {status}")
    if not isinstance(data, dict):
        raise ProviderError(f"heyreach {path}: unexpected response shape")
    return data


def campaign_sequence(campaign_id):
    """The node graph a campaign will actually run. Read-only.

    Returned whole rather than trimmed, because the caller's question is "what
    would this send", and a summary is exactly what cannot answer it.
    """
    return _read_get("/campaign/GetCampaignSequence",
                     {"campaignId": campaign_id})


# What a sequence does that a caller pushing one lead has to know about.
#
# `AddLeadsToCampaignV2` looks like a LinkedIn action. A sequence ending in
# SEND_LEAD_TO_BISON hands the person to an EmailBison campaign afterwards, so
# the blast radius of one LinkedIn lead includes email that this system did not
# write and did not choose. Naming that is the whole point of this function.
BISON_HANDOFF = "sends the lead onward to an EmailBison campaign"
UNKNOWN_VARIABLE = "the copy uses a personalisation variable we do not supply"
EMPTY_CONNECTION_NOTE = "the connection request carries no note at all"
# Only the negative appears in a hazard list; the positive is the absence of
# this one. `linkedin_only()` is where a caller asks the question directly.
NOT_LINKEDIN_ONLY = "the sequence is NOT provably LinkedIn-only"


def sequence_hazards(sequence, supplied_fields=()):
    """What a caller must be told before pushing a lead into this sequence.

    Not a verdict. Each hazard is a fact about the configured sequence that a
    person has to weigh, and the reason they are gathered here rather than
    inferred at the call site is that every one of them is invisible from the
    campaign list.
    """
    blob = json.dumps(sequence or {})
    supplied = {str(f).lower() for f in supplied_fields}
    found = []

    if "SEND_LEAD_TO_BISON" in blob:
        targets = sorted(set(re.findall(r'"bisonCampaignId"\s*:\s*(\d+)', blob)))
        found.append((BISON_HANDOFF, targets))

    used = sorted(set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", blob)))
    # Built-ins HeyReach fills itself. Anything else has to come from the
    # custom fields the push supplies, and a name that does not match is not
    # an error - HeyReach quietly sends the fallback instead.
    builtin = {"FIRST_NAME", "LAST_NAME", "COMPANY", "POSITION", "INDUSTRY",
               "LOCATION", "MY_FIRST_NAME", "MY_LAST_NAME", "MY_COMPANY"}
    unmet = [v for v in used
             if v not in builtin and v.lower() not in supplied]
    if unmet:
        found.append((UNKNOWN_VARIABLE, unmet))

    if '"CONNECTION_REQUEST"' in blob:
        for match in re.finditer(r'"nodeType"\s*:\s*"CONNECTION_REQUEST".{0,400}', blob):
            chunk = match.group(0)
            if '"messages":[]' in chunk.replace(" ", "") or '"messages":[""]' in chunk.replace(" ", ""):
                found.append((EMPTY_CONNECTION_NOTE, []))
                break
    return found


DEFAULT_NOTES = (
    # HeyReach pre-fills a new connection request with its own placeholder.
    # These are not our copy and must never reach a prospect. Written
    # lowercase because `note_is_placeholder` lowercases before comparing -
    # a mixed-case entry here can never match anything and is a dead rule.
    "hey, would love to connect!",
    "hi, would love to connect!",
    "would love to connect!",
    "hi {{firstname}}, would love to connect!",
)


def connection_notes(sequence):
    """Every connection-request note the sequence will actually send.

    THE GAP THIS CLOSES. `sequence_hazards` flags a connection request with NO
    note, and `linkedin_only` proves the channel. Neither reads the words. A
    canary campaign was built by hand on 2026-09-09 with the operator's own
    note pasted in - and the provider held HeyReach's placeholder,
    "Hey, would love to connect!". Every check passed: the sequence was
    provably LinkedIn-only, the note was not empty, and no hazard fired,
    because "a note exists" and "the note is the approved note" are different
    questions and only the first was being asked.

    Returns the notes in graph order so a caller can compare them against what
    was approved. Reads `payload.messages`, which is where the real graph keeps
    them - not `message`, `note`, `text` or `body`, none of which exist.
    """
    notes = []
    nodes, _types, _truncated = walk_sequence(sequence)
    for node in nodes:
        if str(node.get("nodeType") or "").upper() != "CONNECTION_REQUEST":
            continue
        payload = node.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        messages = payload.get("messages")
        for message in (messages if isinstance(messages, list) else []):
            notes.append(str(message or ""))
    return notes


def note_is_placeholder(note):
    """Is this the vendor's default rather than copy somebody wrote?"""
    return " ".join(str(note or "").split()).strip().lower() in DEFAULT_NOTES


def note_matches(sequence, approved):
    """Does the configured note match the approved words? `(bool, why)`.

    Whitespace-normalised, because a UI textarea introduces trailing newlines
    that are not an edit. Nothing else is normalised: case and punctuation are
    the copy.

    Fails closed on every ambiguity - no connection request, more than one
    note, an empty note, the vendor placeholder, or any difference at all -
    because this is the last check between a rendered draft and a real person.
    """
    approved_text = " ".join(str(approved or "").split())
    if not approved_text:
        return False, "no approved note was supplied to compare against"
    notes = connection_notes(sequence)
    if not notes:
        return False, ("the sequence has no connection-request note to read, "
                       "so nothing can be compared")
    if len(notes) > 1:
        return False, (f"the sequence carries {len(notes)} connection notes; "
                       f"which one a prospect receives is not determinable "
                       f"here")
    found = " ".join(notes[0].split())
    if not found:
        return False, "the connection request carries an empty note"
    if note_is_placeholder(found):
        return False, (f"the note is the vendor's placeholder, not our copy: "
                       f"{found!r}")
    if found != approved_text:
        return False, (f"the configured note is not the approved note. "
                       f"provider={found!r} approved={approved_text!r}")
    return True, "the configured note is exactly the approved note"


# ------------------------------------------------- is it LinkedIn-only?
#
# `sequence_hazards` DETECTS the Bison handoff. It cannot answer "is this
# campaign LinkedIn-only", and the difference is the whole canary question.
# Three reasons the detector is not the predicate:
#
#   1. It searches for one literal string. The absence of SEND_LEAD_TO_BISON
#      is not the absence of email egress - it is the absence of one named
#      node type, and any other egress node would be invisible to it.
#   2. It never walks the graph, so it cannot say whether the graph it was
#      handed is the whole graph.
#   3. Its verdict is discarded by its only caller anyway.
#
# So this is an ALLOWLIST over the node types actually reached, and it fails
# closed on anything it does not recognise. A denylist here would be a
# promise about HeyReach's whole node vocabulary, which nothing in this
# repository knows - four types are named anywhere in it.

# Node types that do nothing but act on LinkedIn. Anything absent from this
# tuple makes a campaign unprovable rather than unsafe, which is the honest
# distinction: we are not saying it sends email, we are saying we cannot say
# it does not.
# Confirmed against two real sequence graphs on 2026-09-09, the first ever read
# from this repository: campaign 567683 uses CHECK_IS_CONNECTION / MESSAGE / END
# and is cleared; campaign 565765 uses CONNECTION_REQUEST, FOLLOW, VIEW_PROFILE
# and SEND_LEAD_TO_BISON and is refused on the last of those. `FOLLOW` is the
# provider's spelling - `FOLLOW_PROFILE` was inferred and is kept because it
# costs nothing to accept both, but `FOLLOW` is the one that has been seen.
LINKEDIN_ONLY_NODES = (
    "CHECK_IS_CONNECTION",
    "CONNECTION_REQUEST",
    "MESSAGE",
    "VIEW_PROFILE",
    "FOLLOW",
    "FOLLOW_PROFILE",
    "LIKE_POST",
    "END",
)

# The branch keys a node hands on through. Read from the shape
# `tests/test_a_campaigns_own_copy_gates_the_push.py` builds, which is the
# only description of the graph this repository has.
BRANCH_KEYS = ("conditionalNode", "unconditionalNode", "nextNode", "children")


def walk_sequence(sequence):
    """Every node reachable from the root, and every node type seen.

    Returns `(nodes, types, truncated)`. `truncated` is True when a branch key
    is present but holds something that is not a node - a reference, an id, a
    lazily-loaded stub - because a graph we cannot finish walking is a graph we
    cannot clear.
    """
    root = sequence if isinstance(sequence, dict) else None
    if root is None:
        return [], set(), True
    nodes, types, truncated = [], set(), False
    seen = set()
    queue = [root]
    while queue:
        node = queue.pop(0)
        if id(node) in seen:
            continue
        seen.add(id(node))
        nodes.append(node)
        kind = node.get("nodeType")
        if kind is None:
            # A dict in a branch position with no nodeType is not a node we
            # can classify. Unreadable, so unprovable.
            truncated = True
        else:
            types.add(str(kind))
        for key in BRANCH_KEYS:
            if key not in node:
                continue
            child = node[key]
            if child is None:
                continue
            if isinstance(child, dict):
                queue.append(child)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        queue.append(item)
                    elif item is not None:
                        truncated = True
            else:
                # A scalar where a node belongs: an id or a reference we
                # cannot follow.
                truncated = True
    return nodes, types, truncated


def linkedin_only(sequence):
    """Is this campaign provably LinkedIn-only? `(bool, reason)`.

    Fails closed on every ambiguity: an empty graph, a node with no type, a
    branch we cannot follow, or any node type not on the allowlist. "We cannot
    prove it" and "it sends email" are different facts and both are answered
    False here, but the reason distinguishes them - and the reason is what a
    person reads before authorising a canary.
    """
    nodes, types, truncated = walk_sequence(sequence)
    if not nodes:
        return False, ("no sequence graph to read: an unfetched or empty "
                       "sequence proves nothing")
    if not types:
        # Checked before truncation so an empty or typeless graph gets the
        # precise reason rather than the generic one. A graph that is BOTH
        # truncated and typed still falls through to the truncation reason,
        # which is the more serious of the two.
        return False, "no node in the graph states a nodeType"
    if truncated:
        return False, ("the graph could not be walked to the end - a branch "
                       "holds something that is not a node, so there may be "
                       "steps this check never saw")
    unknown = sorted(t for t in types if t not in LINKEDIN_ONLY_NODES)
    if unknown:
        egress = [t for t in unknown if "BISON" in t.upper()
                  or "EMAIL" in t.upper()]
        if egress:
            return False, (f"the sequence hands the lead off: {', '.join(egress)}"
                           f". A LinkedIn push into this campaign releases "
                           f"email this system did not write")
        return False, (f"unrecognised node type(s): {', '.join(unknown)}. Not "
                       f"proof of email, but this check will not clear a node "
                       f"it cannot classify")
    return True, (f"every node is LinkedIn-only: "
                  f"{', '.join(sorted(types))}")


class SequenceRefused(ProviderError):
    """This campaign's configured copy needs something we do not send."""


def supplied_field_names(rows=None, linkedin_account_id=0):
    """Exactly which custom field names reach the wire, asked of the builder.

    Derived rather than listed. A hand-maintained copy of this drifts the
    moment somebody edits `build_lead_pairs`, and it drifts silently in the
    safe-looking direction: a name still on the list but no longer sent makes
    a hazard disappear, which is the one failure this guard exists to stop.

    With no rows, a probe carrying every optional field answers "what can this
    push supply at all", which is the right question for the operator command:
    `build_lead_pairs` omits falsy fields, so an empty probe would report the
    smallest possible answer as though it were the contract.

    With rows, the answer is the **intersection** of what each row actually
    produces, and that difference is load-bearing. Merging each row over the
    probe was tried and is wrong: a row with no `note` would still have
    reported `note` as supplied, because the probe filled it, while the payload
    built from that row carries no `note` at all. A variable has to be present
    for every lead in the push - one lead missing it is one prospect receiving
    the fallback - so a field only counts when every row has it.
    """
    probe = {"linkedin_url": "https://www.linkedin.com/in/probe",
             "note": "probe", "record_id": "probe", "contact_key": "probe",
             "client": "probe", "sender_id": "probe",
             "sender_account_id": "probe",
             "custom_fields": {}}
    if not rows:
        pair = build_lead_pairs([probe], linkedin_account_id)[0]
        return [f["name"] for f in pair["lead"]["customUserFields"]]

    common, order = None, []
    for row in rows:
        pair = build_lead_pairs([row], linkedin_account_id)[0]
        # An empty value is not a supplied field. `note` is emitted
        # unconditionally by the builder, so without this a row with no note
        # reported one - and a campaign whose copy used it would have rendered
        # a blank where the words were meant to go. That is the same failure as
        # an empty Icebreaker, which the caller already refuses, and the two
        # have to agree or the gate contradicts itself.
        names = [f["name"] for f in pair["lead"]["customUserFields"]
                 if str(f.get("value") or "").strip()]
        order = order or names
        common = set(names) if common is None else (common & set(names))
    return [n for n in order if n in (common or set())]


def refuse_unsupported_sequence(sequence, rows=None, campaign_id=None):
    """Raise unless this campaign's copy can actually be rendered from what
    we send. Returns the hazards that are *not* refusals, for the caller to
    report.

    This is the consumer `sequence_hazards` never had. The check was correct
    and inert: nothing in `src/` called it, so a lead pushed into HeyReach
    campaign 565765 - the one campaign in the workspace whose copy uses
    `{Icebreaker}` - would have had HeyReach quietly substitute its fallback.
    The prospect receives copy this system did not write while the system
    records a send, and nothing anywhere reports a problem.

    Only `UNKNOWN_VARIABLE` refuses. The other two hazards are real and are
    returned rather than raised, because neither can be decided here: a Bison
    handoff is a deliberate configuration in sixteen of this workspace's
    campaigns, and an empty connection note is a campaign whose invite carries
    no text - both are things a person weighs, and turning them into a refusal
    would block sixteen working campaigns to no purpose.
    """
    supplied = supplied_field_names(rows)
    hazards = sequence_hazards(sequence, supplied_fields=supplied)
    # The LinkedIn-only verdict travels with the hazards rather than being
    # recomputed by whoever needs it. `sequence_hazards` detects the Bison
    # handoff; only this says whether the campaign is provably LinkedIn-only,
    # and a canary may not be called LinkedIn-only without it.
    proven, why = linkedin_only(sequence)
    if not proven:
        # Only the negative is a hazard. A hazard list is a list of problems,
        # and appending a confirmation to it would make "no hazards" impossible
        # and quietly break every caller that reads an empty list as clean.
        hazards = list(hazards) + [(NOT_LINKEDIN_ONLY, [why])]
    unmet = [detail for what, detail in hazards if what == UNKNOWN_VARIABLE]
    if unmet:
        missing = ", ".join(sorted({v for group in unmet for v in group}))
        where = f" {campaign_id}" if campaign_id else ""
        raise SequenceRefused(
            f"heyreach campaign{where}: the configured copy uses "
            f"{missing}, which this push does not supply. HeyReach does not "
            f"error on an unknown variable - it sends the fallback message "
            f"instead, so the prospect would receive copy this system did not "
            f"write. Supply it in the row's `custom_fields`, or push to a "
            f"campaign whose copy uses only what we send: "
            f"{', '.join(supplied)}")
    return hazards


# ------------------------------------------------------------------- writes

# The ONE route this module may write to, and it is the one that STOPS things.
#
# ESTABLISHED BY PROBE, not by documentation. HeyReach's own campaign-API post
# documents Create/UpdateSettings/UpdateSequence/UpdateAccounts/UpdateSchedule
# and does not mention pausing at all; third-party write-ups name a path but
# cite each other. So on 2026-09-10 each candidate was sent an EMPTY body -
# no campaignId, nothing to act on - and the status separated them:
#
#   /campaign/Pause           400   exists, refused a malformed request
#   /campaign/Resume          400   exists
#   /campaign/StartCampaign   400   exists
#   /campaign/PauseCampaign   404   does not exist
#   /campaign/ResumeCampaign  404   does not exist
#
# WHY PAUSE AND NOTHING ELSE, when Resume and StartCampaign demonstrably exist.
# Because a system that can start an outreach campaign and cannot stop one is
# strictly worse than a system that can do neither: it acquires the ability to
# create exposure without acquiring the ability to end it, and the killswitch
# becomes a control this build claims and does not have. `executionguard`'s
# `stoppability` gate encodes exactly that and caps an unstoppable channel at
# one contact. Pause is what lifts it. Resume comes after, or not at all.
#
# Pausing is also the safest possible first write to this vendor: it is not
# prospect-facing, it is idempotent, and its worst case is that an outreach
# campaign stops.
WRITE_ROUTES = ("/campaign/Pause",)


def _write(path, params):
    """A POST that changes something. Refuses any route not on the allowlist.

    Deliberately a separate function from `_read` rather than a flag on it.
    One allowlist with a boolean would mean a single wrong argument turns a
    read into a write, and `_read` is called from a dozen places.
    """
    if path not in WRITE_ROUTES:
        raise ProviderError(
            f"heyreach: {path} is not a write route. This module writes only "
            f"to {', '.join(WRITE_ROUTES)}. Adding a route here is a decision "
            f"about what this system may do to real campaigns.")
    qs = urllib.parse.urlencode(params or {})
    status, data = request("POST", f"{BASE}{path}?{qs}", headers(), {})
    if not ok(status):
        # THE STATUS AND THE BODY, both. `f"heyreach {path}: {status}"` was
        # what this said, and when the first real write failed it was
        # impossible to tell a 403 (this account's plan does not include the
        # campaign API, which is in beta) from a 400 (the argument is in the
        # wrong place) without calling again. A write path whose failures
        # cannot be diagnosed without repeating the write is a write path that
        # invites repeating the write.
        raise ProviderError(
            f"heyreach {path}: HTTP {status} - {str(data)[:200]}")
    return data if isinstance(data, dict) else {"status": status}


def pause_campaign(campaign_id):
    """Stop a running campaign. Returns the raw provider response.

    NOT prospect-facing: nothing is sent, and leads already in progress keep
    their state. This is the transport only - `providerwrites.perform` owns
    the reservation, the read-back and the classification.
    """
    return _write("/campaign/Pause", {"campaignId": int(campaign_id)})


def campaign_status(campaign_id):
    """The campaign's status as the provider currently reports it.

    The read-back for `pause_campaign`, kept beside it so the pair is obvious.
    """
    return (campaign_by_id(campaign_id) or {}).get("status")


def _read(path, body):
    """A POST that reads. Refuses any route not on the allowlist."""
    if path not in READ_ROUTES_ALL:
        raise ProviderError(
            f"heyreach: {path} is not a read-only route. This module posts only "
            f"to {', '.join(READ_ROUTES_ALL)}; adding leads is not implemented.")
    status, data = request("POST", f"{BASE}{path}", headers(), body)
    if not ok(status):
        raise ProviderError(f"heyreach {path}: {status}")
    if not isinstance(data, dict):
        raise ProviderError(f"heyreach {path}: unexpected response shape")
    return data


def _collection(data, path, key="items"):
    """The list under `key`, or a stated failure. Never a silent empty page.

    `_read` already refuses a body that is not an object; this is where it
    used to stop being strict. A 200 whose collection key is missing,
    renamed or re-nested was flattened to `[]`, and on the inbox route that
    reads as "nobody replied" - the quietest possible way for positive-reply
    protection to stop working, since the poll succeeds and reports zero
    events with no error at all. Same argument as `providers.mapping`: a
    body of the wrong *shape* is a contract violation, not a result.

    An empty list is a genuine "none" and passes through untouched.
    """
    items = data.get(key)
    if not isinstance(items, list):
        raise ProviderError(
            f"heyreach {path}: no `{key}` array in the response (got "
            f"{type(items).__name__}); refusing to read that as none")
    return items


def campaigns(offset=0, limit=50):
    """One page of campaigns. Read-only. Returns (items, total)."""
    data = _read("/campaign/GetAll", {"offset": int(offset),
                                      "limit": min(int(limit), MAX_PAGE)})
    return _collection(data, "/campaign/GetAll"), data.get("totalCount")


def campaign_by_id(campaign_id, page_size=MAX_PAGE, max_pages=10):
    """One campaign, found by paging the list.

    There is no confirmed GetById route (POST /campaign/GetById answers 405),
    so this walks pages until it finds the id or runs out. Bounded, so an
    account with thousands of campaigns cannot turn one lookup into a crawl.
    """
    offset = 0
    for _ in range(max(1, max_pages)):
        items, total = campaigns(offset, page_size)
        for item in items:
            if str(item.get("id")) == str(campaign_id):
                return item
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
    return None


def li_accounts(offset=0, limit=MAX_PAGE):
    """One page of LinkedIn seats. Read-only. Returns (items, total).

    Untrimmed on purpose, like `campaign_sequence`: the caller's question is
    "which seats exist and can they send", and the fields that answer it -
    `authIsValid`, `isActive`, `activeCampaigns` and the `accountLimits`
    object - have never been read from this repository, so a trim written now
    would be a guess about key names rather than a filter over known ones.
    `senderinventory` classifies; this only fetches.
    """
    data = _read("/li_account/GetAll", {"offset": int(offset),
                                        "limit": min(int(limit), MAX_PAGE)})
    return _collection(data, "/li_account/GetAll"), data.get("totalCount")


def all_li_accounts(page_size=MAX_PAGE, max_pages=10):
    """Every seat, paged. Bounded, and it refuses a short read.

    The same guard `bison.sender_emails` needed and for the same reason: a
    sender inventory is what capacity is planned against, so returning one page
    of it would read as a small estate rather than a partial answer.
    """
    items, total, offset = [], None, 0
    for _ in range(max(1, max_pages)):
        page, count = li_accounts(offset, page_size)
        if total is None:
            total = count
        items += page
        offset += len(page)
        if not page or (total is not None and offset >= int(total)):
            break
    if total is not None and len(items) != int(total):
        raise ProviderError(
            f"heyreach li_accounts: totalCount says {total} seats and "
            f"{len(items)} arrived. Refusing to return a partial sender "
            f"inventory.")
    return items, total


def conversations(offset=0, limit=50, filters=None):
    """One page of the inbox. Read-only: reading marks nothing as seen."""
    data = _read("/inbox/GetConversationsV2",
                 {"filters": filters or {}, "offset": int(offset),
                  "limit": int(limit)})
    return (_collection(data, "/inbox/GetConversationsV2"),
            data.get("totalCount"))


def check():
    """The documented health check. Costs nothing, changes nothing."""
    try:
        status, data = request("GET", f"{BASE}/auth/CheckApiKey", headers())
        return result("HeyReach", status, str(data) if data is not None else "OK")
    except ProviderError as e:
        return failed("HeyReach", e)


def _report_sequence(campaign_id):
    """What a push into this campaign would and would not be able to render.

    An operator command rather than a screen because the question is asked
    once per campaign, before a canary, and the answer decides whether that
    campaign is usable at all. `--check` says the key works; this says the
    copy works, which is a different question and the one that reaches a
    prospect.
    """
    try:
        sequence = campaign_sequence(campaign_id)
    except ProviderError as e:
        print(f"FAIL {campaign_id}: {e}")
        return 1
    supplied = supplied_field_names()
    print(f"campaign {campaign_id}")
    print(f"  we supply: {', '.join(supplied)}")
    hazards = sequence_hazards(sequence, supplied_fields=supplied)
    if not hazards:
        print("  ok: the configured copy needs nothing we do not send")
        return 0
    blocking = 0
    for what, detail in hazards:
        mark = "REFUSES" if what == UNKNOWN_VARIABLE else "note   "
        blocking += what == UNKNOWN_VARIABLE
        print(f"  {mark} {what}" + (f": {', '.join(map(str, detail))}"
                                    if detail else ""))
    if blocking:
        print("  a push would be refused: HeyReach sends its fallback for a "
              "variable it cannot fill, so the prospect would receive copy "
              "this system did not write")
    return 1 if blocking else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.heyreach")
    p.add_argument("--check", action="store_true")
    p.add_argument("--sequence", metavar="CAMPAIGN_ID",
                   help="read this campaign's configured copy and report "
                        "whether a push could actually render it. Read-only, "
                        "no credit, no write.")
    args = p.parse_args(argv)
    if args.sequence:
        return _report_sequence(args.sequence)
    r = check()
    print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['provider']:<12} {r['status']}  {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

# ------------------------------------------------------- person-level facts
#
# `/lead/GetLead` is confirmed live: POST {profileUrl} -> a profile with
# headline, position, companyName, about, summary and experiences. It is a
# read, it costs nothing, and it comes through our own licensed HeyReach
# account rather than by scraping LinkedIn.
#
# That matters for what this project will and will not do. Public LinkedIn
# posts cannot be collected without an authenticated session or a third party
# holding one, which means bypassing an access control - so posts are simply
# not a source here. What a licensed provider already returns about a person is
# a different thing entirely, and it is enough to say something specific about
# somebody's actual remit.

PROFILE_ROUTE = "/lead/GetLead"

PROFILE_FIELDS = ("headline", "position", "companyName", "about", "summary",
                  "location", "industry", "profileUrl", "linkedin_id",
                  "firstName", "lastName")


def lead_profile(profile_url):
    """One person's public profile as HeyReach holds it. Read-only.

    Returns a trimmed dict, never the raw payload: `experiences`, `education`
    and `emailEnrichments` are deliberately dropped, because a cold email has
    no business reciting somebody's CV back at them.
    """
    data = _read(PROFILE_ROUTE, {"profileUrl": profile_url})
    trimmed = {k: data.get(k) for k in PROFILE_FIELDS
               if data.get(k) not in (None, "", [], {})}
    # A current role, if the profile states one plainly.
    if data.get("position") and data.get("companyName"):
        trimmed["current_role"] = f"{data['position']} at {data['companyName']}"
    return trimmed
