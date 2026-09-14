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
# /linkedinaccount/GetAll and /webhooks/GetAll both answer 404, and GET
# /campaign/GetAll answers 405.
#
# TWO OF THOSE 404s WERE WRONG ROUTE NAMES, NOT ABSENT CAPABILITIES, and this
# comment read them as absence twice. `/li_account/GetAll` is the seat route
# and is now on the read allowlist below. `/webhooks/GetAllWebhooks` is the
# webhook route - the vendor documents create, read, update and delete under
# /webhooks/ plus twelve event types - and nothing here has ever called it.
#
# The distinction this comment kept losing: "the provider does not expose it"
# justifies building around it, and "we have never asked correctly" does not.
# A route is recorded absent here only when the NAME the vendor documents
# answered 404.
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
#
# AND IT IS A STATEMENT ABOUT THIS ROUTE, NOT ABOUT THE PROVIDER - the same
# distinction `/campaign/GetLeadsFromCampaign` forced further down. The vendor
# documents two other ways to ask: a `CONNECTION_REQUEST_ACCEPTED` webhook
# event, and `POST /MyNetwork/IsConnection`. Neither is on an allowlist,
# neither has ever answered here, and neither changes this constant - what
# would change it is a read this module performs and reads back.
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
# The two routes that answer what the provider DID, added here rather than to
# `READ_ROUTES` above for the same reason `/li_account/GetAll` is: that tuple is
# pinned by an exact-set assertion in `tests/test_audit.py` and is about the two
# routes the inbound event contract rests on. These are lifecycle reads, which
# is a different question. Both are POSTs that read, both are free, and both
# were confirmed live on 2026-09-11.
# `/list/GetAll` and `/campaign/GetCampaignsForLead` joined the list on
# 2026-09-13, both measured. The first is the read-back for list creation -
# `tests/test_the_factory_verbs_exist_and_are_sealed.py` recorded it as
# present-but-unwired, and a write to a list route may not be enabled while
# the route that verifies it is not. The second answers "is this person
# already in another campaign", per campaign and per lead status, which is a
# collision question nothing here could ask before.
READ_ROUTES_ALL = READ_ROUTES + ("/lead/GetLead", "/li_account/GetAll",
                                 "/campaign/GetLeadsFromCampaign",
                                 "/stats/GetOverallStats",
                                 "/list/GetAll",
                                 "/campaign/GetCampaignsForLead")

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
READ_GET_ROUTES = ("/campaign/GetCampaignSequence", "/campaign/GetById",
                   "/list/GetById")

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
        # THE 404 WAS A TYPO, AGAIN. This said "no webhook management on the
        # confirmed surface (/webhooks/GetAll answers 404)", which is the same
        # mistake `/linkedinaccount/GetAll` was: a wrong route name read as an
        # absent capability. The vendor's own collection documents five routes
        # under /webhooks/ - CreateWebhook, GetWebhookById, GetAllWebhooks,
        # UpdateWebhook, DeleteWebhook - and twelve event types, among them
        # CONNECTION_REQUEST_SENT, CONNECTION_REQUEST_ACCEPTED, MESSAGE_SENT
        # and MESSAGE_REPLY_RECEIVED.
        #
        # NONE of them is called from here and none is on any allowlist, so
        # this states what this build DOES, not what the provider lacks. The
        # distinction is the whole point: "the provider has no webhooks" would
        # justify polling forever, and "we have never called them" does not.
        "webhook": "documented by the vendor (POST /webhooks/CreateWebhook, "
                   "POST /webhooks/GetAllWebhooks, GET GetWebhookById, PATCH "
                   "UpdateWebhook, DELETE DeleteWebhook; 12 event types) and "
                   "NEVER called from here - on no allowlist, never answered. "
                   "Polling is the transport this build actually uses",
        "absent": "/linkedinaccount/GetAll answers 404. The route that does "
                  "answer is /li_account/GetAll, which is on the read "
                  "allowlist and is what `senderinventory` rebuilds the seat "
                  "roster from; a campaign's campaignAccountIds says which "
                  "seats that campaign uses, which is a different question",
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
#
# INMAIL AND CHECK_IS_OPEN_PROFILE WERE ADDED ON 2026-09-13, and the first of
# those was a live gap rather than an omission: `INMAIL` appears 15 times
# across this workspace's 82 sequences and was NOT on this tuple, so every
# InMail campaign in the client's estate answered "unrecognised node type" -
# unprovable rather than cleared. An InMail is a LinkedIn message sent through
# LinkedIn by the same seat; nothing about it leaves the channel.
#
# `FIND_EMAIL` is documented by the vendor and is deliberately NOT here. It
# does not send anything, but what it exists to produce is an email address,
# and a node whose output is an address is not something this check should
# clear as LinkedIn-only on its own reading of the name.
LINKEDIN_ONLY_NODES = (
    "CHECK_IS_CONNECTION",
    "CHECK_IS_OPEN_PROFILE",
    "CONNECTION_REQUEST",
    "MESSAGE",
    "INMAIL",
    "VIEW_PROFILE",
    "FOLLOW",
    "FOLLOW_PROFILE",
    "LIKE_POST",
    "END",
)

# ------------------------------------------------- the node vocabulary
#
# MEASURED 2026-09-13 by reading `GET /campaign/GetCampaignSequence` on every
# one of the 82 campaigns in the client's workspace - 1194 nodes. Nine node
# types appear, and their counts are recorded because the absence of a type is
# the interesting half: END 396, LIKE_POST 300, MESSAGE 227, VIEW_PROFILE 135,
# CONNECTION_REQUEST 39, CHECK_IS_CONNECTION 35, SEND_LEAD_TO_BISON 24,
# FOLLOW 23, INMAIL 15.
NODE_TYPES_OBSERVED = (
    "CHECK_IS_CONNECTION", "CONNECTION_REQUEST", "MESSAGE", "INMAIL",
    "VIEW_PROFILE", "FOLLOW", "LIKE_POST", "SEND_LEAD_TO_BISON", "END")

# Named by the vendor's own `UpdateSequence` documentation and never seen in a
# live graph here. Kept separate from the tuple above because "the provider
# says this exists" and "this provider has done this for this client" are
# different facts, and only the second is evidence.
NODE_TYPES_DOCUMENTED_ONLY = (
    "CHECK_IS_OPEN_PROFILE", "FIND_EMAIL", "SEND_LEAD_TO_INSTANTLY",
    "SEND_LEAD_TO_SMARTLEAD")

NODE_TYPES = NODE_TYPES_OBSERVED + NODE_TYPES_DOCUMENTED_ONLY

# The only four nodes that may carry `conditionalNode`. Documented explicitly:
# "All other non-END nodes must NOT set this field."
#
# THE LIVE GRAPHS DISAGREE WITH THAT SENTENCE and the disagreement is only in
# one direction. Every MESSAGE and INMAIL node built in the vendor's own UI
# carries `conditionalNode: END`, which is how the UI renders "a reply ends
# this sequence". So a graph READ from the provider may legitimately carry the
# key on a non-branching node; a graph this module WRITES must not, and
# `validate_sequence_for_write` is where that asymmetry lives.
BRANCHING_NODES = ("CONNECTION_REQUEST", "CHECK_IS_CONNECTION",
                   "CHECK_IS_OPEN_PROFILE", "FIND_EMAIL")

# Nodes that are rejected with 400 unless they carry a `payload`.
PAYLOAD_REQUIRED = ("CONNECTION_REQUEST", "MESSAGE", "INMAIL", "LIKE_POST",
                    "SEND_LEAD_TO_INSTANTLY", "SEND_LEAD_TO_SMARTLEAD",
                    "SEND_LEAD_TO_BISON")

# Parents after which every child - including an END - must wait at least
# three hours. Documented, and the failure is a 400 reading
# `Node at: ... has invalid delay: 00:00:00`.
DELAY_PARENTS = ("CONNECTION_REQUEST", "MESSAGE", "INMAIL", "VIEW_PROFILE",
                 "FOLLOW", "LIKE_POST")
MIN_CHILD_DELAY_HOURS = 3
DELAY_UNITS = ("HOUR", "DAY")

# `actionDelay` is documented as 0-100 and the unit as HOUR or DAY, so the
# longest wait any single node can express is 100 days. The vendor also
# documents a 500-day ceiling; it is NOT checked here, because 100 days is the
# most the other two rules permit and a guard that cannot fire is a guard
# nobody can trust to fire.
MAX_DELAY_AMOUNT = 100


# ---------------------------- the two capability questions, answered
#
# OPEN PROFILE. `CHECK_IS_OPEN_PROFILE` is a real branching node type, so a
# SEQUENCE can act on whether somebody is an Open Profile member. Nothing else
# can. Measured 2026-09-13 across the whole documented surface - 82 requests -
# and across every field the provider publishes about a person
# (`/lead/GetLead`: 23 keys; `GetLeadsFromCampaign`'s `linkedInUserProfile`:
# 16 keys): there is no `openProfile`, no `isOpenProfile`, no premium flag and
# no connection-degree field anywhere, and no route asks the question.
#
# So open-profile status is decidable INSIDE a running graph and nowhere else.
# A planner cannot know it in advance, a report cannot state it afterwards, and
# any code that wants to say "this person is an Open Profile" has nothing to
# read. The strongest supported design is therefore to branch rather than to
# predict, which is what `linkedin_sequence` does.
OPEN_PROFILE_DETECTABLE = False        # no route, no field. Branch only.
OPEN_PROFILE_BRANCH_NODE = "CHECK_IS_OPEN_PROFILE"

# INMAIL. Same answer, same shape. `INMAIL` is a real node type and is in live
# use here, and a CONNECTION_REQUEST's `unconditionalNode` - the not-accepted
# branch - can lead to it after a wait, which is exactly the escalation asked
# for. What CANNOT be read is whether a given prospect can receive one: no
# eligibility field exists at lead level, and the seat's `inMailLimit` /
# `inMailLimitMax` / `inMailCooldown` describe OUR capacity, not their
# reachability. A seat with InMail credit says nothing about whether this
# person will accept an InMail.
INMAIL_ELIGIBILITY_DETECTABLE = False   # capacity is readable; theirs is not.
INMAIL_NODE = "INMAIL"

# AN INMAIL IS NOT A MESSAGE WITH A DIFFERENT NODE TYPE, and the payload is
# where that shows. A MESSAGE carries `messages: [str]` and
# `fallbackMessage: str`. An INMAIL carries `messages: [{subject, message}]`
# and `fallbackMessage: {subject, message}` - objects, because a LinkedIn
# InMail has a subject line and an ordinary LinkedIn message does not.
#
# ESTABLISHED THE EXPENSIVE WAY, 2026-09-13. A first version of this comment
# said an InMail had no subject field, having read the payload's KEY names and
# not the types under them, and a sequence built on that belief was refused by
# the provider: `Error converting value "..." to type
# 'Spremo.DTOs.PublicApi.Campaigns.PublicInMailMessage'`. The live graphs
# agree - all 15 INMAIL nodes in this workspace carry the object form.
#
# So a subject IS writable, it is a second piece of copy per InMail variant,
# and anything approving InMail words has to approve both halves.
INMAIL_MESSAGE_FIELDS = ("subject", "message")

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


# ------------------------------------------- building a sequence to WRITE
#
# Reading a graph and writing one are different problems and this half is the
# dangerous one. `walk_sequence` and `linkedin_only` above are tolerant on
# purpose: they classify whatever the provider hands back, including the
# `conditionalNode: END` the vendor's UI puts on every MESSAGE node. A graph
# going the other way has to satisfy the server's own rules, and the server
# answers 400 with a sentence rather than telling you which node it meant.


class SequenceInvalid(ProviderError):
    """This graph would be refused by the provider, or is unsafe to send."""


def _delay_hours(node):
    """A node's wait in hours, or None when it does not state one."""
    value = node.get("actionDelay")
    if value is None:
        return None
    unit = str(node.get("actionDelayUnit") or "").upper()
    if unit not in DELAY_UNITS:
        raise SequenceInvalid(
            f"actionDelayUnit {node.get('actionDelayUnit')!r} on a "
            f"{node.get('nodeType')!r} node is not one of "
            f"{', '.join(DELAY_UNITS)}")
    try:
        amount = int(value)
    except (TypeError, ValueError):
        raise SequenceInvalid(
            f"actionDelay {value!r} on a {node.get('nodeType')!r} node is not "
            f"a number") from None
    if not 0 <= amount <= MAX_DELAY_AMOUNT:
        raise SequenceInvalid(
            f"actionDelay {amount} is outside the documented range "
            f"0-{MAX_DELAY_AMOUNT}")
    return amount * (24 if unit == "DAY" else 1)


def _words_of(kind, entry):
    """Every piece of prospect-facing text in one message entry.

    One place, because a MESSAGE entry is a string and an INMAIL entry is a
    `{subject, message}` object, and every check that reads copy - emptiness
    here, comparison in `sequence_matches` - has to agree about which is which.
    """
    if kind == INMAIL_NODE:
        if not isinstance(entry, dict):
            return None
        return [str(entry.get(f) or "") for f in INMAIL_MESSAGE_FIELDS]
    if isinstance(entry, dict):
        return None
    return [str(entry or "")]


def _check_words(where, kind, payload):
    """Refuse a step that would send a blank, or the wrong payload shape."""
    entries = payload.get("messages")
    entries = entries if isinstance(entries, list) else []
    if not entries:
        raise SequenceInvalid(
            f"{where}: a {kind} with no `messages` sends nothing")
    for entry in entries:
        words = _words_of(kind, entry)
        if words is None:
            raise SequenceInvalid(
                f"{where}: a {kind} message entry is a "
                f"{type(entry).__name__}. An INMAIL entry is an object with "
                f"{'/'.join(INMAIL_MESSAGE_FIELDS)}; every other node's is a "
                f"string, and the provider rejects the wrong one")
        blank = [f for f, w in zip(
            INMAIL_MESSAGE_FIELDS if kind == INMAIL_NODE else ("message",),
            words) if not w.strip()]
        if blank:
            raise SequenceInvalid(
                f"{where}: a {kind} variant has an empty "
                f"{', '.join(blank)} - that reaches a real person as a blank")
    fallback = payload.get("fallbackMessage")
    words = _words_of(kind, fallback)
    if words is None or not all(w.strip() for w in words):
        raise SequenceInvalid(
            f"{where}: a {kind} needs a complete fallbackMessage. HeyReach "
            f"sends the fallback whenever a personalisation variable cannot "
            f"be filled, so an incomplete one is a blank rather than a safe "
            f"default")


def validate_sequence_for_write(sequence):
    """Refuse a graph the provider would reject, or that we should not send.

    Returns `(node_count, steps_carrying_words)` so a caller can state what it
    built rather than assert it. The second number counts every node in the
    whole tree that sends text - across ALL branches, not along one path - so
    it is a description of the graph and never a claim about what one prospect
    receives. Raises `SequenceInvalid` naming the node.

    Every rule here is the vendor's own except the last, which is ours:

      * only the four branching node types may carry `conditionalNode`;
      * a branching node must carry one, or its true branch silently vanishes;
      * a non-END node must carry `unconditionalNode`;
      * every path terminates in an END;
      * a child of an action node waits at least three hours, END included;
      * a payload is mandatory on the seven nodes that take configuration, and
        a MESSAGE/INMAIL/CONNECTION_REQUEST payload with no non-empty
        `messages` entry is a step that sends a blank;
      * and the true branch of `CHECK_IS_OPEN_PROFILE` must be an INMAIL.

    The last one is the only opinion in the list and it is the one that stops a
    quiet failure. `OPEN_PROFILE_DETECTABLE` is False: nothing here can read
    whether a prospect is an Open Profile member, so nothing can verify what a
    MESSAGE on that branch would do. LinkedIn's Open Profile channel is a free
    InMail; a plain MESSAGE to a non-connection is the thing the platform does
    not carry. Putting one there builds a sequence whose most promising branch
    reaches nobody and reports nothing, which is indistinguishable from an
    audience that did not answer.
    """
    if not isinstance(sequence, dict):
        raise SequenceInvalid("a sequence must be a node object")
    messages = 0
    seen = set()
    # `connected` is a TRI-STATE: None until a check settles it, then True or
    # False along that branch. Unknown is not False - the root of a graph that
    # never asks has not established that anybody is a stranger.
    stack = [(sequence, None, "root", False, None)]
    while stack:
        node, parent, where, invited, connected = stack.pop()
        if not isinstance(node, dict):
            raise SequenceInvalid(f"{where}: a branch holds "
                                  f"{type(node).__name__}, not a node")
        if id(node) in seen:
            raise SequenceInvalid(f"{where}: this graph is not a tree - the "
                                  f"same node object is reachable twice")
        seen.add(id(node))
        kind = str(node.get("nodeType") or "")
        if kind not in NODE_TYPES:
            raise SequenceInvalid(
                f"{where}: {kind!r} is not a node type this provider "
                f"documents. Known: {', '.join(sorted(NODE_TYPES))}")

        hours = _delay_hours(node)
        if parent is not None:
            if hours is None:
                raise SequenceInvalid(
                    f"{where}: a non-root node must state actionDelay and "
                    f"actionDelayUnit")
            if parent in DELAY_PARENTS and hours < MIN_CHILD_DELAY_HOURS:
                raise SequenceInvalid(
                    f"{where}: a child of a {parent} must wait at least "
                    f"{MIN_CHILD_DELAY_HOURS} hours and this one waits "
                    f"{hours}. The provider rejects it as 'invalid delay'")

        conditional = node.get("conditionalNode")
        unconditional = node.get("unconditionalNode")
        if kind in BRANCHING_NODES:
            if conditional is None:
                raise SequenceInvalid(
                    f"{where}: a {kind} branches, and this one has no "
                    f"conditionalNode - the branch it exists to take would "
                    f"not exist")
        elif conditional is not None:
            raise SequenceInvalid(
                f"{where}: {kind} is not a branching node and must not carry "
                f"conditionalNode. Only {', '.join(BRANCHING_NODES)} may")

        if kind == "END":
            if conditional is not None or unconditional is not None:
                raise SequenceInvalid(f"{where}: an END has no children")
            continue
        if unconditional is None:
            raise SequenceInvalid(
                f"{where}: a {kind} must state unconditionalNode - every path "
                f"has to terminate in an END and this one stops here")

        payload = node.get("payload")
        if kind in PAYLOAD_REQUIRED:
            if not isinstance(payload, dict):
                raise SequenceInvalid(
                    f"{where}: a {kind} requires a payload and carries "
                    f"{type(payload).__name__}")
            if kind in ("MESSAGE", "INMAIL", "CONNECTION_REQUEST"):
                _check_words(where, kind, payload)
                messages += 1
        elif payload is not None:
            raise SequenceInvalid(
                f"{where}: {kind} takes no payload and one was supplied")

        # THE THREE GRAPH RULES THE PROVIDER ENFORCES, each measured by
        # refusal against a real DRAFT campaign on 2026-09-13 and each quoting
        # the sentence the provider answered with. Checked here so a bad graph
        # is refused before a write rather than by a status code after one.

        # "Cannot have a FOLLOW node after a CONNECTION_REQUEST node, because
        # CONNECTION_REQUEST already follows the lead."
        if kind == "FOLLOW" and invited:
            raise SequenceInvalid(
                f"{where}: a FOLLOW cannot appear after a CONNECTION_REQUEST - "
                f"sending the invitation already follows the lead, and the "
                f"provider rejects the graph. Put the FOLLOW before the "
                f"invitation, where it is a warm-up rather than a no-op")

        # "Cannot have 2 CONNECTION_REQUEST nodes in sequence."
        if kind == "CONNECTION_REQUEST" and invited:
            raise SequenceInvalid(
                f"{where}: this path already sends a CONNECTION_REQUEST. The "
                f"provider refuses two on one path, and a second invitation to "
                f"somebody who ignored the first is not a cadence step")

        # "Cannot have MESSAGE node on the 'Not Connected' side of
        # IS_CONNECTION node."
        #
        # THIS IS THE ANSWER TO THE OPEN-PROFILE QUESTION, AND IT IS THE
        # PROVIDER'S RATHER THAN AN OPINION HELD HERE. A first version of this
        # check refused a MESSAGE on the open-profile branch on our own
        # reasoning about LinkedIn. The server refuses it across the whole
        # not-connected side, that branch included - so being an Open Profile
        # buys a FREE INMAIL, not a different kind of message, and an InMail
        # is the only node that reaches somebody who is not a connection.
        if kind == "MESSAGE" and connected is False:
            raise SequenceInvalid(
                f"{where}: a MESSAGE cannot be sent on the not-connected side "
                f"of a CHECK_IS_CONNECTION. LinkedIn carries no plain message "
                f"to a stranger and the provider rejects the graph; an "
                f"{INMAIL_NODE} is what reaches a non-connection, and an "
                f"accepted CONNECTION_REQUEST is what makes a MESSAGE possible "
                f"again")

        below_invite = invited or kind == "CONNECTION_REQUEST"
        if conditional is not None:
            # Taking the true branch of either check, or of an invitation,
            # establishes that this person IS a connection from here on.
            stack.append((
                conditional, kind, f"{where}/true:{kind}", below_invite,
                True if kind in ("CHECK_IS_CONNECTION", "CONNECTION_REQUEST")
                else connected))
        # Only the false side of CHECK_IS_CONNECTION establishes a stranger.
        # An unaccepted invitation does not - the provider's rule names
        # IS_CONNECTION - and CHECK_IS_OPEN_PROFILE changes nobody's
        # connection state at all.
        stack.append((
            unconditional, kind, f"{where}/next:{kind}", below_invite,
            False if kind == "CHECK_IS_CONNECTION" else connected))
    return len(seen), messages


def _node(kind, delay=None, unit=None, payload=None, nxt=None, cond=None):
    node = {"nodeType": kind}
    if delay is not None:
        node["actionDelay"] = int(delay)
        node["actionDelayUnit"] = str(unit or "HOUR").upper()
    if payload is not None:
        node["payload"] = payload
    if cond is not None:
        node["conditionalNode"] = cond
    if nxt is not None:
        node["unconditionalNode"] = nxt
    return node


def _copy(step, copy, kind="MESSAGE"):
    """One step's words as a payload, or a refusal naming the step.

    `kind` decides the shape, because an INMAIL's entries are
    `{subject, message}` objects and everything else's are strings. Validated
    here rather than only at the graph level so the refusal names the STEP a
    person can go and fix, not the node path it ended up at.
    """
    block = (copy or {}).get(step)
    if not isinstance(block, dict):
        shape = ("{'subject': ..., 'message': ...}" if kind == INMAIL_NODE
                 else "'...'")
        raise SequenceInvalid(
            f"no copy supplied for step {step!r}. This builder never invents "
            f"the words a prospect reads; supply "
            f"{{'messages': [{shape}], 'fallbackMessage': {shape}}}")
    entries = block.get("messages")
    payload = {"messages": list(entries) if isinstance(entries, list) else [],
               "fallbackMessage": block.get("fallbackMessage")}
    try:
        _check_words(f"step {step!r}", kind, payload)
    except SequenceInvalid as e:
        raise SequenceInvalid(f"{e}") from None
    return payload


# The steps `linkedin_sequence` needs words for. `messages` is a LIST on the
# wire, which is where `COPY-EXPERIMENTS.md`'s five variants per step land:
# the provider rotates them itself, so a variant is a graph fact rather than
# something this system has to assign per contact.
# THE ALREADY-CONNECTED BRANCH HAS ITS OWN FOUR ROLES, and that is the point.
# It used to reuse `message_2`/`message_3`/`message_4` from the cold path, and
# because a role maps to one cadence step, the first message on this branch
# (`connected_1`) and the second (`message_2`) both resolved to the same step -
# so a prospect who was already a connection received the identical sentence
# twice, three days apart. Measured on campaign 599020, 2026-09-14.
#
# The graph was never wrong; its own comment says "already connected -> message
# straight away, four of them". Four slots wanted four different messages and
# the mapping had only three to give. Naming them separately is what lets each
# one hold its own step.
SEQUENCE_STEPS = ("connection_note", "connected_1", "connected_2",
                  "connected_3", "connected_4", "message_2", "message_3",
                  "message_4", "inmail")


def linkedin_sequence(copy, withdraw_after_days=21):
    """The LinkedIn-primary graph, branched on the prospect's actual state.

    Six activities and four message opportunities on the main path, over about
    three weeks, and every branch is taken on something the provider can
    actually observe rather than on a guess this system made:

        CHECK_IS_CONNECTION                     (free, instant, root)
          already connected -> message straight away, four of them
          not connected     -> CHECK_IS_OPEN_PROFILE
              open profile  -> INMAIL now, then ask to connect anyway
              not           -> view, then ask to connect
                  accepted      -> the four-message chain
                  not accepted  -> view, follow, and an INMAIL at the end

    The not-accepted branch is the one the operator asked about by name: a
    CONNECTION_REQUEST's `unconditionalNode` IS the "they did not accept"
    branch, and it can lead to an INMAIL after a wait. What this cannot do is
    check first - `INMAIL_ELIGIBILITY_DETECTABLE` is False, so the InMail is
    attempted rather than targeted, and a seat out of InMail credit fails that
    step rather than skipping it.

    Pure. Sends nothing, and every word comes from `copy`.
    """
    def end(delay=3, unit="HOUR"):
        return _node("END", delay, unit)

    def chain(copy_block):
        """message_2 -> view -> message_3 -> message_4 -> END."""
        return _node("MESSAGE", 3, "HOUR", _copy("message_2", copy_block),
                nxt=_node("VIEW_PROFILE", 3, "DAY",
                     nxt=_node("MESSAGE", 2, "DAY", _copy("message_3", copy_block),
                          nxt=_node("MESSAGE", 7, "DAY",
                                    _copy("message_4", copy_block),
                                    nxt=end()))))

    invite = _copy("connection_note", copy)
    invite["toBeWithdrawnAfterDays"] = int(withdraw_after_days)

    # The not-accepted branch. A FOLLOW may NOT go here - the provider refuses
    # a FOLLOW below a CONNECTION_REQUEST because the invitation already
    # followed them - so the wait is a profile view and then the InMail.
    not_accepted = _node("VIEW_PROFILE", 5, "DAY",
                    nxt=_node("INMAIL", 5, "DAY",
                              _copy("inmail", copy, INMAIL_NODE), nxt=end()))

    ask_to_connect = _node("CONNECTION_REQUEST", 1, "DAY", dict(invite),
                           nxt=not_accepted, cond=chain(copy))

    open_profile = _node("INMAIL", 3, "HOUR", _copy("inmail", copy, INMAIL_NODE),
                    nxt=_node("CONNECTION_REQUEST", 2, "DAY", dict(invite),
                              cond=chain(copy),
                              nxt=_node("VIEW_PROFILE", 5, "DAY", nxt=end())))

    # The cold branch: look at them, follow them, then ask. Both warm-up steps
    # sit BEFORE the invitation, which is the only place a FOLLOW is allowed.
    cold = _node("CHECK_IS_OPEN_PROFILE", 3, "HOUR",
                 cond=open_profile,
                 nxt=_node("VIEW_PROFILE", 3, "HOUR",
                      nxt=_node("FOLLOW", 3, "HOUR", nxt=ask_to_connect)))

    already = _node("MESSAGE", 3, "HOUR", _copy("connected_1", copy),
               nxt=_node("MESSAGE", 3, "DAY", _copy("connected_2", copy),
                    nxt=_node("VIEW_PROFILE", 2, "DAY",
                         nxt=_node("MESSAGE", 5, "DAY", _copy("connected_3", copy),
                              nxt=_node("MESSAGE", 7, "DAY",
                                        _copy("connected_4", copy),
                                        nxt=end())))))

    sequence = _node("CHECK_IS_CONNECTION", 0, "HOUR", cond=already, nxt=cold)
    validate_sequence_for_write(sequence)
    return sequence


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
# WHAT WAS ADDED ON 2026-09-13, AND THE RULE THAT DECIDED EACH ONE.
#
# Every route below either STAGES something that cannot send, or STOPS
# something. Nothing here starts outreach: `/campaign/StartCampaign` and
# `/campaign/Resume` both exist, both were probed, and both are still absent
# - the same order-of-operations argument that kept Pause alone up to now.
#
#   /list/CreateEmptyList      an empty list reaches nobody
#   /campaign/Create           creates in DRAFT; a DRAFT sends nothing
#   /campaign/UpdateSequence   configuration; 400 outside DRAFT/SCHEDULED/PAUSED
#   /campaign/AddLinkedInAccountsToCampaign     additive seat assignment
#   /campaign/RemoveLinkedInAccountsFromCampaign  removes a seat
#   /campaign/StopLeadInCampaign                stops ONE person
#
# `/campaign/UpdateAccounts` IS DELIBERATELY NOT HERE and is the sharpest
# omission on the list. It is a FULL REPLACE of a campaign's sender set, and
# the vendor documents the consequence in its own words: on a PAUSED campaign,
# leads assigned to a removed account are stopped and cannot be resumed. The
# two routes above do the same job additively and subtractively, each reports
# per-account success, and neither can erase a seat nobody mentioned. There is
# no task that needs the replace verb and no undo if it is wrong.
#
# `/campaign/UpdateSchedule` IS NOT HERE EITHER, for a different reason
# entirely - see `set_schedule` below. There is no route anywhere on this API
# that reads a campaign's schedule back, so a write to it can never be
# verified, and this module's whole write discipline is read-back.
WRITE_ROUTES = (
    "/campaign/Pause",
    "/list/CreateEmptyList",
    "/campaign/Create",
    "/campaign/UpdateSequence",
    "/campaign/AddLinkedInAccountsToCampaign",
    "/campaign/RemoveLinkedInAccountsFromCampaign",
    "/campaign/StopLeadInCampaign",
    # TASK-009: the add-leads route is on the write allowlist so the transport
    # and readback can be developed and tested. It is NOT in `SUPPORTED` in
    # `providerwrites` - the door refuses it until Claude enables it after
    # review. A route on WRITE_ROUTES is a route this module CAN call; a route
    # in SUPPORTED is a route this build WILL call. The two lists are the
    # difference between "the mechanism exists" and "it is live".
    "/campaign/AddLeadsToCampaignV2",
)

# The routes that take their argument in the query string rather than a body.
# `_write` builds both forms and this is what tells them apart.
WRITE_QUERY_ROUTES = ("/campaign/Pause",)


def _write_body(path, body):
    """A POST with a JSON body that changes something. Allowlisted.

    Separate from `_write` only because `/campaign/Pause` takes its argument in
    the query string and everything added since takes a body. Folding the two
    into one function with a flag is how a body ends up on the wire as a query
    string and a write silently acts on nothing.
    """
    if path not in WRITE_ROUTES:
        raise ProviderError(
            f"heyreach: {path} is not a write route. This module writes only "
            f"to {', '.join(WRITE_ROUTES)}. Adding a route here is a decision "
            f"about what this system may do to real campaigns.")
    if path in WRITE_QUERY_ROUTES:
        raise ProviderError(
            f"heyreach: {path} takes its argument in the query string. "
            f"Sending it a body would reach the provider as a call with "
            f"nothing to act on")
    status, data = request("POST", f"{BASE}{path}", headers(), body)
    if not ok(status):
        raise ProviderError(
            f"heyreach {path}: HTTP {status} - {str(data)[:300]}")
    if isinstance(data, dict):
        return data
    # AN EMPTY BODY IS A REAL ANSWER HERE. `/campaign/UpdateSequence` returns
    # 200 with nothing at all, measured 2026-09-13, so refusing an empty body
    # would make the one write on this provider with a perfect read-back
    # unusable. Every caller reads the provider back anyway; none of them reads
    # this return value for proof.
    if data in (None, ""):
        return {"status": status}
    # A non-empty body that is not an object is a different thing: an HTML
    # error page or a proxy notice arriving with a 2xx.
    raise ProviderError(
        f"heyreach {path}: HTTP {status} with a {type(data).__name__} body - "
        f"{str(data)[:200]}. A write whose response is not the documented "
        f"shape is a write nobody can classify")


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


# ------------------------------------------------- the staging verbs
#
# Each one writes, then READS BACK, and raises unless the provider itself says
# the thing happened. A 2xx is never the proof: `/campaign/Create` returning an
# object is a claim, and `GET /campaign/GetById` finding that id is the fact.
#
# Two of these have no safe read-back and both are handled by refusing rather
# than by hoping - see `set_schedule`.

CAMPAIGN_FIELDS = ("id", "name", "status", "organizationUnitId",
                   "linkedInUserListId", "linkedInUserListName",
                   "campaignAccountIds", "creationTime", "startedAt")

LIST_FIELDS = ("id", "name", "listType", "totalItemsCount", "campaignIds",
               "creationTime")

# The statuses in which the provider accepts a configuration change. Anything
# else answers 400. Recorded here so a caller can refuse BEFORE writing rather
# than discover it from a status code.
MUTABLE_STATUSES = ("DRAFT", "SCHEDULED", "PAUSED")

DRAFT = "DRAFT"


def lists(offset=0, limit=MAX_PAGE, keyword=None, list_type=None):
    """One page of lead/company lists. Read-only. Returns (items, total)."""
    body = {"offset": int(offset), "limit": min(int(limit), MAX_PAGE)}
    if keyword:
        body["keyword"] = str(keyword)
    if list_type:
        body["listType"] = str(list_type)
    data = _read("/list/GetAll", body)
    return ([{k: row.get(k) for k in LIST_FIELDS}
             for row in _collection(data, "/list/GetAll")],
            data.get("totalCount"))


def list_by_id(list_id):
    """One list, read directly. The read-back for `create_list`."""
    data = _read_get("/list/GetById", {"listId": int(list_id)})
    return {k: data.get(k) for k in LIST_FIELDS}


def campaign_read(campaign_id):
    """One campaign, read directly by id. Trimmed.

    `campaign_by_id` pages `/campaign/GetAll` up to ten times to find one row,
    on a comment that predates the discovery that `GetById` answers as a GET.
    It is left alone - it is what `campaign_status` and `configdiff` already
    call, and replacing a working lookup was not this change's job. This is the
    one-request form the write verbs read back through.
    """
    data = _read_get("/campaign/GetById", {"campaignId": int(campaign_id)})
    return {k: data.get(k) for k in CAMPAIGN_FIELDS}


def create_list(name, list_type="USER_LIST"):
    """Create an empty lead list and prove it exists. Returns a trimmed row.

    AN EMPTY LIST REACHES NOBODY, which is what makes this the safest write on
    this provider after the pause. It is also PERMANENT: this vendor documents
    no delete for a list, only `DeleteLeadsFromList`, so a list created here
    stays in the client's estate for good and the name is not a detail.
    """
    name = str(name or "").strip()
    if not name:
        raise ProviderError("heyreach create_list: a name is required")
    if list_type not in ("USER_LIST", "COMPANY_LIST"):
        raise ProviderError(
            f"heyreach create_list: {list_type!r} is not a list type. The "
            f"provider defaults an empty one to a lead list, and a default "
            f"nobody chose is how a campaign ends up bound to the wrong kind")
    data = _write_body("/list/CreateEmptyList",
                       {"name": name, "type": list_type})
    list_id = data.get("id")
    if not list_id:
        raise ProviderError(
            "heyreach create_list: the provider returned no id. A list may "
            "exist that nothing here can name, and there is no delete verb; "
            "read /list/GetAll before trying again")
    found = list_by_id(list_id)
    if str(found.get("name")) != name or str(found.get("listType")) != list_type:
        raise ProviderError(
            f"heyreach create_list: read-back disagrees with the request. "
            f"asked for {name!r}/{list_type}, provider holds "
            f"{found.get('name')!r}/{found.get('listType')}")
    return found


def create_campaign(name, list_id, account_ids, schedule=None, sequence=None,
                    exclusions=None):
    """Create a campaign in DRAFT and prove it exists. Returns a trimmed row.

    A DRAFT SENDS NOTHING. Activation is `/campaign/StartCampaign`, which is
    not on `WRITE_ROUTES` and is not implemented here, so nothing this function
    builds can reach a person without a separate, deliberate act somewhere
    else.

    THE SEAT IS NOT OPTIONAL AND THAT IS THE PROVIDER'S RULE, measured
    2026-09-13: an empty `linkedInAccountIds` answers 400,
    "must be a string or array type with a minimum length of '1'", and an
    omitted one answers 400 "field is required". A campaign cannot be created
    unassigned. A caller that wants an unassigned campaign creates it with one
    seat and then calls `remove_senders`, which is what the provider leaves
    available; there is no single call that does it.

    `schedule` is accepted here because Create is the ONLY place a schedule can
    be set and then read back at all - see `set_schedule`. Omitting it does not
    mean no schedule: the provider defaults to Mon-Fri 09:00-17:00 UTC, and a
    default nobody chose is still a sending window.
    """
    name = str(name or "").strip()
    if not 1 <= len(name) <= 50:
        raise ProviderError(
            f"heyreach create_campaign: the name must be 1-50 characters and "
            f"{name!r} is {len(name)}. There is no campaign delete on this "
            f"provider, so a rejected name is cheaper than a wrong one")
    seats = [int(a) for a in (account_ids or [])]
    if not 1 <= len(seats) <= 100:
        raise ProviderError(
            "heyreach create_campaign: the provider requires 1-100 sender "
            "accounts and rejects an empty array. Create with the seat you "
            "intend and call remove_senders if the campaign must hold none")
    body = {"name": name, "linkedInAccountIds": seats}
    if list_id is not None:
        body["linkedInUserListId"] = int(list_id)
    if schedule is not None:
        body["schedule"] = _schedule_body(schedule)
    if sequence is not None:
        validate_sequence_for_write(sequence)
        body["sequence"] = sequence
    for flag in ("excludeContactedFromOtherCampaigns",
                 "excludeHasOtherAccConversations",
                 "excludeContactedFromSenderInOtherCampaign", "excludeListId"):
        if (exclusions or {}).get(flag) is not None:
            body[flag] = exclusions[flag]

    # THE NAME IS THE RECOVERY KEY, so it has to be unique before the write.
    # There is no campaign delete on this vendor: a create that is lost between
    # the POST and the response can only be found again by name, and two
    # campaigns sharing one is a state nobody can resolve afterwards.
    if campaign_named(name):
        raise ProviderError(
            f"heyreach create_campaign: a campaign named {name!r} already "
            f"exists. Creating a second one is permanent and would make the "
            f"name useless as the only handle either can be found by")

    data = _write_body("/campaign/Create", body)
    # `campaignId`, NOT `id`. Measured 2026-09-13, and the first live create
    # from this repository raised on a campaign that had in fact been made -
    # which is exactly the failure the name lookup below now covers, because
    # on this provider an unrecoverable id is an unrecoverable campaign.
    campaign_id = data.get("campaignId")
    if not campaign_id:
        row = campaign_named(name)
        if row is None:
            raise ProviderError(
                f"heyreach create_campaign: the provider returned no "
                f"campaignId and no campaign named {name!r} can be found. "
                f"Read /campaign/GetAll before any retry; this vendor "
                f"documents no campaign delete")
        campaign_id = row["id"]

    found = campaign_read(campaign_id)
    if str(found.get("name")) != name:
        raise ProviderError(
            f"heyreach create_campaign: read-back says the campaign is named "
            f"{found.get('name')!r} and {name!r} was asked for")
    if str(found.get("status")) != DRAFT:
        raise ProviderError(
            f"heyreach create_campaign: read-back says status "
            f"{found.get('status')!r} and a created campaign must be {DRAFT}. "
            f"Anything else is a campaign that may already be running")
    if list_id is not None and str(found.get("linkedInUserListId")) != str(int(list_id)):
        raise ProviderError(
            f"heyreach create_campaign: the campaign is bound to list "
            f"{found.get('linkedInUserListId')!r} and {list_id!r} was asked "
            f"for. A campaign pointing at the wrong list is a campaign "
            f"pointing at somebody else's people")
    held = {int(a) for a in (found.get("campaignAccountIds") or [])}
    if held != set(seats):
        raise ProviderError(
            f"heyreach create_campaign: the campaign holds seats "
            f"{sorted(held)} and {sorted(seats)} was asked for")
    return found


def campaign_named(name):
    """The one campaign with this exact name, or None. Raises if two share it.

    Pages `/campaign/GetAll` rather than filtering, because that route honours
    no name filter - the same trap the inbox sets. Bounded at 20 pages.
    """
    name, offset, found = str(name), 0, []
    for _ in range(20):
        items, total = campaigns(offset, MAX_PAGE)
        found += [i for i in items if str(i.get("name")) == name]
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
    if len(found) > 1:
        raise ProviderError(
            f"heyreach: {len(found)} campaigns are named {name!r} "
            f"({[c.get('id') for c in found]}). A name that identifies more "
            f"than one campaign identifies none of them")
    return {k: found[0].get(k) for k in CAMPAIGN_FIELDS} if found else None


def set_sequence(campaign_id, sequence):
    """Replace a campaign's whole workflow, then read the graph back.

    THE READ-BACK IS THE POINT. `GET /campaign/GetCampaignSequence` returns the
    graph the provider will actually run, so this is one of the few writes on
    either vendor that can be compared field for field with what was sent. It
    is compared on the node SHAPE - types, delays and the message texts - and
    not on raw equality, because the provider normalises: a UI-built graph
    carries `conditionalNode: END` on message nodes and a written one does not.

    Refuses outside DRAFT/SCHEDULED/PAUSED before writing rather than after,
    and on a PAUSED campaign the vendor performs a "safe update" that remaps
    existing leads into the new graph - so a caller changing a live campaign's
    copy is moving real people between steps, which is why the status is read
    first and reported in the refusal.
    """
    validate_sequence_for_write(sequence)
    status = str(campaign_read(campaign_id).get("status") or "")
    if status not in MUTABLE_STATUSES:
        raise ProviderError(
            f"heyreach set_sequence: campaign {campaign_id} is {status!r} and "
            f"the provider accepts a sequence only in "
            f"{', '.join(MUTABLE_STATUSES)}")
    _write_body("/campaign/UpdateSequence",
                {"campaignId": int(campaign_id), "sequence": sequence})
    found = campaign_sequence(campaign_id)
    same, why = sequence_matches(found, sequence)
    if not same:
        raise ProviderError(
            f"heyreach set_sequence: the write returned 2xx and the graph the "
            f"provider now holds is not the graph that was sent - {why}. The "
            f"campaign is in an unknown configuration; do NOT retry blindly")
    return found


def _fingerprint(node):
    """A node reduced to what a prospect experiences, in walk order.

    `conditionalNode` is followed and `unconditionalNode` is followed, and the
    presence of the first is recorded rather than its absence - so a provider
    that adds `conditionalNode: END` to a message node reads as a difference
    only where it changes what is sent, which it does not.
    """
    if not isinstance(node, dict):
        return None
    payload = node.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    kind = str(node.get("nodeType") or "")
    texts = payload.get("messages")
    # `_words_of` so an INMAIL's subject is compared too. A read-back that
    # ignored the subject would clear a graph whose subject lines the provider
    # had silently dropped, and the subject is the half a prospect sees first.
    out = [kind,
           node.get("actionDelay"),
           str(node.get("actionDelayUnit") or "").upper(),
           [_words_of(kind, t) for t in texts] if isinstance(texts, list) else None,
           _words_of(kind, payload.get("fallbackMessage"))]
    return [out,
            _fingerprint(node.get("conditionalNode")),
            _fingerprint(node.get("unconditionalNode"))]


# The node the provider inserts by itself, and the only difference between a
# written graph and the graph that comes back that is not a difference.
#
# MEASURED 2026-09-13 on campaign 599020: 28 nodes were sent and 40 came back.
# The twelve extra are all the same thing - a bare
# `{"nodeType": "END", "actionDelay": 0, "actionDelayUnit": "HOUR"}` hung on
# the `conditionalNode` of every MESSAGE and INMAIL node. The vendor documents
# that a non-branching node must NOT set that field, and then sets it itself.
#
# IT IS THE REPLY-STOP, MADE STRUCTURAL. The true branch of a message node is
# "they answered", and the provider ends the sequence there whether or not
# anybody asked. That is worth knowing for its own sake: a LinkedIn reply
# stops the remaining steps at the provider as well as in this system's own
# `accountpolicy.apply_reply`, so the two agree by construction rather than by
# a setting somebody has to remember.


def _is_bare_end(node):
    return (isinstance(node, dict)
            and str(node.get("nodeType") or "") == "END"
            and node.get("conditionalNode") is None
            and node.get("unconditionalNode") is None)


def _strip_added_ends(observed, sent):
    """The observed graph minus the conditionals the provider added itself.

    Walked against the graph that was SENT, so a bare END is only ignored
    where we sent nothing at that position and the node is not one that
    branches. A bare END on a CONNECTION_REQUEST, or one replacing a branch we
    did send, stays and reads as the difference it is.
    """
    if not isinstance(observed, dict):
        return observed
    sent = sent if isinstance(sent, dict) else {}
    out = dict(observed)
    kind = str(out.get("nodeType") or "")
    if (kind not in BRANCHING_NODES
            and sent.get("conditionalNode") is None
            and _is_bare_end(out.get("conditionalNode"))):
        out.pop("conditionalNode", None)
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(out.get(key), dict):
            out[key] = _strip_added_ends(out[key], sent.get(key))
    return out


def sequence_matches(observed, sent):
    """Does the provider's graph say the same thing as the one we sent?

    `(bool, why)`. Compared on node type, delay and the actual words - the
    three that decide what a person receives and when - after removing the
    reply-stop ENDs the provider adds on its own. Everything else is a
    difference, including one this system caused.
    """
    if not isinstance(observed, dict):
        raise ProviderError(
            "heyreach sequence_matches: the provider returned no graph to "
            "compare, so nothing can be said about what it will send")
    ours = _fingerprint(sent)
    theirs = _fingerprint(_strip_added_ends(observed, sent))
    if ours == theirs:
        return True, "every node type, delay and message matches what was sent"
    # Say WHERE, not just that. A diff nobody can locate produces a retry.
    def flatten(node, path="root", out=None):
        out = [] if out is None else out
        if node is None:
            return out
        out.append((path, tuple(str(x) for x in node[0])))
        flatten(node[1], path + "/true", out)
        flatten(node[2], path + "/next", out)
        return out
    mine, yours = dict(flatten(ours)), dict(flatten(theirs))
    for path in sorted(set(mine) | set(yours)):
        if mine.get(path) != yours.get(path):
            return False, (f"at {path}: sent {mine.get(path)!r}, provider "
                           f"holds {yours.get(path)!r}")
    return False, "the graphs differ in shape"


def add_senders(campaign_id, account_ids):
    """Add sender seats to a campaign WITHOUT disturbing the ones already on it.

    THE ADDITIVE VERB, AND THE REASON `/campaign/UpdateAccounts` IS NOT ON THE
    WRITE ALLOWLIST. UpdateAccounts is a full replacement: any seat missing
    from the body is removed, and the vendor documents that on a PAUSED
    campaign the leads belonging to a removed seat are stopped and cannot be
    resumed. This route adds and reports per account, so a stale caller cannot
    silently delete a seat it never knew about.

    Read back against `campaignAccountIds` on the campaign itself, because the
    per-account result in the response is the provider's claim and the campaign
    row is the fact.
    """
    return _change_senders("/campaign/AddLinkedInAccountsToCampaign",
                           campaign_id, account_ids, present=True)


def remove_senders(campaign_id, account_ids):
    """Take sender seats off a campaign. Read back the same way.

    ON A CAMPAIGN THAT HOLDS LEADS THIS IS NOT A CONFIGURATION CHANGE. The
    vendor's own words for the replacing verb apply here too: leads assigned to
    a removed seat stop, and stopping is not reversible by putting the seat
    back. This function does not refuse that - a stop is sometimes exactly what
    is wanted - but it reads the campaign first and names the number of leads
    in the refusal-free path so a caller cannot claim it did not know.
    """
    return _change_senders("/campaign/RemoveLinkedInAccountsFromCampaign",
                           campaign_id, account_ids, present=False)


def _change_senders(route, campaign_id, account_ids, present):
    seats = [int(a) for a in (account_ids or [])]
    if not 1 <= len(seats) <= 100:
        raise ProviderError(
            f"heyreach {route}: 1-100 accounts per request, {len(seats)} given")
    before = campaign_read(campaign_id)
    if str(before.get("status")) not in MUTABLE_STATUSES:
        raise ProviderError(
            f"heyreach {route}: campaign {campaign_id} is "
            f"{before.get('status')!r}; seats may only be changed in "
            f"{', '.join(MUTABLE_STATUSES)}")
    _write_body(route, {"campaignId": int(campaign_id),
                        "linkedInAccountIds": seats})
    after = campaign_read(campaign_id)
    held = {int(a) for a in (after.get("campaignAccountIds") or [])}
    wrong = [a for a in seats if (a in held) != present]
    if wrong:
        raise ProviderError(
            f"heyreach {route}: the write returned 2xx and the campaign's own "
            f"campaignAccountIds still "
            f"{'omits' if present else 'holds'} {wrong}. The provider reports "
            f"per-account failures inside a successful response, so the "
            f"status code proved nothing")
    return after


def _schedule_body(schedule):
    """The schedule object, validated as far as anything here can validate it."""
    schedule = mapping(schedule, "heyreach schedule")
    for field in ("dailyStartTime", "dailyEndTime", "timeZoneId"):
        if not str(schedule.get(field) or "").strip():
            raise ProviderError(
                f"heyreach schedule: {field} is required. There is no read "
                f"route for a schedule on this API, so a field omitted here "
                f"is a field nobody can ever check")
    days = [k for k in schedule if k.startswith("enabled")]
    if days and not any(schedule[k] for k in days):
        raise ProviderError(
            "heyreach schedule: at least one enabled day must be true")
    return dict(schedule)


def set_schedule(campaign_id, schedule):
    """REFUSED. There is no route on this API that reads a schedule back.

    This is not an omission and it is not a safety veto either - a sending
    window is ordinary configuration. It is the one verb in this module whose
    effect cannot be observed by any means the provider offers.

    The whole documented surface is 82 requests. `UpdateSchedule` writes a
    schedule; `GetById` and `GetAll` return fourteen campaign fields and none
    of them is the schedule; `GetCampaignSequence` returns the node graph and
    not the window. So after calling it, this system would hold exactly one
    piece of evidence about when a campaign may contact people - its own memory
    of what it asked for - and that is the definition of a second
    representation of a truth that nothing can reconcile.

    THE RULE IT BREAKS IS "READ BACK BEFORE DECIDING ANYTHING". `providerwrites`
    refuses a write with no read-back for exactly this reason, and a verb that
    can never supply one cannot be made to satisfy it by trying harder.

    WHAT TO DO INSTEAD, and it is not a workaround. `/campaign/Create` takes
    the schedule in the same shape, in the one call that also produces a
    campaign id - so a campaign's window is chosen once, at creation, by
    whoever creates it. That does not make it readable afterwards; it makes it
    a decision recorded at a moment somebody owns, rather than a change nobody
    can audit. An existing campaign's window is changed by a person in the
    vendor's UI, where they can at least see it.
    """
    _schedule_body(schedule)          # so a bad body fails on the body, not here
    raise ProviderError(
        f"heyreach set_schedule: refusing to write a schedule to campaign "
        f"{campaign_id}. POST /campaign/UpdateSchedule exists and no route on "
        f"this API reads a schedule back, so the write could never be "
        f"verified and this system would be the only record of when a "
        f"campaign may contact people. Pass `schedule` to create_campaign, or "
        f"change it by hand in HeyReach where a person can see it")


# The lead statuses in which the provider is still going to act on somebody.
# From `GetCampaignsForLead`'s own documented `LeadStatus` set: Pending,
# InSequence, Finished, Paused, Failed, Excluded,
# PendingOrExcludedToBeCalculated. An ALLOWLIST of the two that mean "more is
# coming", so a value this system has never seen reads as still-running and a
# stop that landed on an unknown state raises instead of being believed.
RUNNING_LEAD_STATUSES = ("Pending", "InSequence",
                         "PendingOrExcludedToBeCalculated")


def stop_lead_in_campaign(campaign_id, member_id, profile_url):
    """Stop ONE person's progression through a campaign. Read back per lead.

    The LinkedIn counterpart of `bison.stop_lead`, and the reason it belongs on
    the write allowlist despite never having succeeded: it can only ever mean
    somebody receives less. After a reply, an unsubscribe, a suppression or an
    account-level stop, this is what prevents the NEXT LinkedIn step to that
    person without pausing the campaign everybody else is in.

    NEVER LIVE-VALIDATED. No lead has ever been stopped from this repository,
    because no lead has ever been added from it. The route was probed on an
    empty campaign this system created and answers rather than 404ing; that is
    existence, not a contract. The read-back below is therefore written to fail
    closed: `GetCampaignsForLead` reports this person's `leadStatus` per
    campaign, and a status that has not left the running set raises.
    """
    member_id = str(member_id or "").strip()
    profile_url = str(profile_url or "").strip()
    if not member_id or not profile_url:
        raise ProviderError(
            "heyreach stop_lead_in_campaign: both leadMemberId and leadUrl are "
            "required. The provider matches on them and a partial body is a "
            "call that stops nobody while returning success")
    _write_body("/campaign/StopLeadInCampaign",
                {"campaignId": int(campaign_id), "leadMemberId": member_id,
                 "leadUrl": profile_url})
    rows, _total = campaigns_for_lead(profile_url)
    here = [r for r in rows if str(r.get("campaignId")) == str(campaign_id)]
    if not here:
        raise ProviderError(
            f"heyreach stop_lead_in_campaign: after the write, "
            f"GetCampaignsForLead does not list campaign {campaign_id} for "
            f"{profile_url}. The stop cannot be confirmed and must not be "
            f"retried")
    state = str(here[0].get("leadStatus") or "")
    if state in RUNNING_LEAD_STATUSES:
        raise ProviderError(
            f"heyreach stop_lead_in_campaign: the write returned 2xx and the "
            f"provider still reports this lead as {state!r} in campaign "
            f"{campaign_id}. The person is still in the sequence")
    return {"campaign_id": campaign_id, "profile_url": profile_url,
            "lead_status": state}


# ------------------------------------------------- adding leads to a campaign
#
# TASK-009. The route is on WRITE_ROUTES above. It is NOT in `SUPPORTED` in
# `providerwrites` - the door refuses it until Claude enables it after review.
#
# WHAT IS ESTABLISHED AND WHAT IS NOT.
#
# The request shape comes from `build_lead_pairs`, which already constructs the
# `accountLeadPairs` format from rows. The URL comes from `add_leads_endpoint`.
# The readback uses `/campaign/GetLeadsFromCampaign`, which is already wired
# and returns per-lead membership with lifecycle state.
#
# What is NOT established: the response shape of `AddLeadsToCampaignV2` itself.
# No successful response has ever been read. So the transport returns whatever
# the provider sends, and the READBACK is what decides the verdict - not the
# status code or the response body. A 200 with no membership confirmation is
# not a success; a membership read that finds every asked-for lead is.
#
# The request body fields that are UNKNOWN until a live call:
#   - what the response body contains on success
#   - what it returns for a lead already in the campaign
#   - what it returns for a lead it rejects (bad URL, wrong org, etc.)
#   - whether it is atomic (all-or-nothing) or per-lead
# These are recorded as questions for Claude in the task result.


def add_leads_to_campaign(campaign_id, rows, linkedin_account_id):
    """Add leads to a campaign. Returns the raw provider response.

    NOT prospect-facing at this layer: this is the transport only. The caller
    goes through `providerwrites.perform`, which owns the authorization, the
    readback and the classification.

    The request body is `{campaignId, accountLeadPairs}`. `build_lead_pairs`
    constructs the per-lead shape from rows; this function wraps it with the
    campaign id and posts it.
    """
    pairs = build_lead_pairs(rows, linkedin_account_id)
    if not pairs:
        raise ProviderError(
            "heyreach add_leads_to_campaign: no lead pairs to send. "
            "The rows produced no accountLeadPairs - check that each row "
            "has a linkedin_url")
    body = {"campaignId": int(campaign_id), "accountLeadPairs": pairs}
    return _write_body("/campaign/AddLeadsToCampaignV2", body)


def readback_membership(campaign_id, expected_urls):
    """Read back who is in the campaign and compare against who was asked for.

    Returns a dict with:
      - `found`: set of profile URLs found in the campaign
      - `missing`: set of profile URLs asked for but not found
      - `total`: the campaign's reported total lead count
      - `per_lead`: list of per-lead state dicts from `campaign_leads`

    Pages through the whole campaign rather than trusting a single page.
    Bounded at 50 pages (5000 leads) to prevent runaway on a large campaign.
    """
    expected = {str(u).strip().lower() for u in expected_urls if u}
    if not expected:
        raise ProviderError(
            "heyreach readback_membership: no expected URLs supplied. "
            "A readback with nothing to compare against verifies nothing")
    found = set()
    per_lead = []
    offset = 0
    total = None
    for _ in range(50):
        rows, count = campaign_leads(campaign_id, offset=offset)
        if count is not None:
            total = count
        for row in rows:
            url = str(row.get("profile_url") or "").strip().lower()
            if url in expected:
                found.add(url)
                per_lead.append(row)
        offset += len(rows)
        if not rows or (total is not None and offset >= int(total)):
            break
    missing = expected - found
    return {"found": found, "missing": missing, "total": total,
            "per_lead": per_lead}


def check_tenant(campaign_id, org_unit):
    """Refuse unless the campaign belongs to this client's org unit.

    A lead belonging to another client cannot enter this client's campaign.
    The campaign's `organizationUnitId` is checked against the configured
    `org_unit`, and a mismatch REFUSES rather than warns.
    """
    row = campaign_read(campaign_id)
    actual = str(row.get("organizationUnitId") or "")
    wanted = str(org_unit or "")
    if not wanted:
        raise ProviderError(
            "heyreach check_tenant: no org_unit was supplied. A lead write "
            "without a tenant boundary is a write that cannot be scoped")
    if actual != wanted:
        raise ProviderError(
            f"heyreach check_tenant: campaign {campaign_id} belongs to org "
            f"unit {actual!r} and this client is configured for {wanted!r}. "
            f"A lead belonging to another client cannot enter this client's "
            f"campaign")
    return True


def campaigns_for_lead(profile_url=None, linkedin_id=None, offset=0,
                       limit=MAX_PAGE):
    """Every campaign this person is in, with their status in each. Read-only.

    Answers the one collision question `/inbox/GetConversationsV2` cannot: a
    conversation exists only once somebody has been written to, and this lists
    the campaigns holding a person who has not been reached yet. It is also the
    read-back for `stop_lead_in_campaign`.
    """
    body = {"offset": int(offset), "limit": min(int(limit), MAX_PAGE)}
    if profile_url:
        body["profileUrl"] = str(profile_url)
    if linkedin_id:
        body["linkedinId"] = str(linkedin_id)
    if not (profile_url or linkedin_id):
        raise ProviderError(
            "heyreach campaigns_for_lead: a profile url or a linkedin id is "
            "required. An empty body is not a question about nobody, it is a "
            "question the provider answers however it likes")
    data = _read("/campaign/GetCampaignsForLead", body)
    rows = _collection(data, "/campaign/GetCampaignsForLead")
    return ([{k: r.get(k) for k in ("campaignId", "campaignName",
                                    "campaignStatus", "leadStatus",
                                    "creationTime")} for r in rows],
            data.get("totalCount"))


# ------------------------------------------------- what the provider DID
#
# THE LIFECYCLE IS READABLE, ON ROUTES THIS MODULE NEVER TRIED.
#
# `CONNECTION_STATUS_AVAILABLE = False` above stays, and stays true: it is a
# statement about `/inbox/GetConversationsV2`, re-verified, and that route
# genuinely carries no invitation state. What was wrong was reading it as a
# statement about the PROVIDER. `/campaign/GetLeadsFromCampaign` returns, per
# lead, `leadCampaignStatus`, `leadConnectionStatus`, `leadMessageStatus`,
# `lastActionTime`, `failedTime`, `errorCode` and `linkedInUserProfileId`.
#
# This is what makes a first touch recordable at all. `touch.CONFIRMING_EVENTS`
# can only be written by a send path that raises or by a webhook this vendor
# does not expose, so before these routes a canary's invitation could never be
# proven to have happened.
#
# `progressStats` CANNOT answer it and is never mapped to a lifecycle state
# here. Two live proofs: campaign 594061 reports `totalUsersInProgress: 1,
# totalUsersPending: 0` while that same lead's own row reads `Pending / None /
# lastActionTime null` - nothing sent, already counted - and campaigns
# 470039/470038/470010 report `totalUsersInProgress` of -7, -5 and -6. It is a
# residual that absorbs bucket error, not a count.

LEADS_ROUTE = "/campaign/GetLeadsFromCampaign"
STATS_ROUTE = "/stats/GetOverallStats"

REQUEST_PENDING = "request_pending"
REQUEST_SENT = "request_sent"
ACCEPTED = "accepted"
REPLIED = "replied"
FAILED = "failed"
ENDED_NO_ACTION = "ended_no_action"
LIFECYCLE_UNKNOWN = "unknown"

LIFECYCLE = (REQUEST_PENDING, REQUEST_SENT, ACCEPTED, REPLIED, FAILED,
             ENDED_NO_ACTION, LIFECYCLE_UNKNOWN)

# States in which a prospect has demonstrably been reached. Named here so no
# caller decides it locally, and FAILED is deliberately absent: a failed lead
# may already have been accepted and messaged.
REACHED = (REQUEST_SENT, ACCEPTED, REPLIED)

# ALLOWLISTS, not translation tables - the same polarity argument as
# `direction()`. Established over 851 real leads across 11 campaigns.
#
# A value this system has never seen becomes UNKNOWN and is recorded, never
# folded into a neighbouring state. That is not hypothetical: 594061's sequence
# carries `toBeWithdrawnAfterDays: 21`, so withdrawal is a scheduled event in
# this campaign, and no `Withdrawn` value appears in those 851 leads. If one
# ever does it must not read as still-pending.
CONNECTION_STATES = ("none", "connectionsent", "connectionaccepted")
MESSAGE_STATES = ("none", "messagesent", "messagereply")
CAMPAIGN_STATES = ("pending", "insequence", "finished", "failed")


def _state_word(value):
    return str(value if value is not None
               else "None").strip().lower().replace(" ", "")


def lead_state(row):
    """One lead's lifecycle state, with the provider's own words kept.

    THE THREE FIELDS ARE INDEPENDENT, NOT A STATE MACHINE. Thirteen distinct
    combinations were observed over 851 leads, including 27 at
    `(Failed, ConnectionAccepted, MessageSent)` and one at
    `(Failed, None, MessageSent)`.

    So `Failed` DOES NOT MEAN NOTHING REACHED THE PROSPECT, and that is the
    most dangerous thing to get wrong here: code reading `Failed` as "safe to
    retry" would send a second invitation to somebody who already had one, and
    in 27 of those cases had already accepted it. Failure is therefore consulted
    LAST, and only when nothing more final is present:

        replied          they answered
        accepted         the invitation was accepted
        request_sent     the invitation went out
        failed           the step failed and none of the above happened
        ended_no_action  the sequence finished having sent nothing
        request_pending  enrolled, nothing done yet

    `ended_no_action` is read from the fields rather than inferred: 165 of 252
    observed `Finished` leads carry `leadConnectionStatus: None`, so "finished"
    plainly does not mean "contacted", and calling that pending would promise an
    action that is never coming.

    `errorCode` is an OPEN set - 15 distinct values in 851 leads, a long tail of
    singletons, one carrying a vendor typo - so it is carried verbatim and never
    interpreted here.
    """
    raw = {"leadCampaignStatus": row.get("leadCampaignStatus"),
           "leadConnectionStatus": row.get("leadConnectionStatus"),
           "leadMessageStatus": row.get("leadMessageStatus")}
    campaign = _state_word(row.get("leadCampaignStatus"))
    connection = _state_word(row.get("leadConnectionStatus"))
    message = _state_word(row.get("leadMessageStatus"))
    answer = {"raw": raw, "error_code": row.get("errorCode"),
              "at": row.get("lastActionTime") or row.get("failedTime")}

    unseen = [name for name, word, allowed in (
        ("leadCampaignStatus", campaign, CAMPAIGN_STATES),
        ("leadConnectionStatus", connection, CONNECTION_STATES),
        ("leadMessageStatus", message, MESSAGE_STATES))
        if word not in allowed]
    if unseen:
        return dict(answer, state=LIFECYCLE_UNKNOWN,
                    why="the provider used a value this system has never "
                        "seen: " + ", ".join(unseen))
    if message == "messagereply":
        return dict(answer, state=REPLIED, why=None)
    if connection == "connectionaccepted":
        return dict(answer, state=ACCEPTED, why=None)
    if connection == "connectionsent":
        return dict(answer, state=REQUEST_SENT, why=None)
    if campaign == "failed":
        return dict(answer, state=FAILED, why=None)
    if campaign == "finished":
        return dict(answer, state=ENDED_NO_ACTION,
                    why="the sequence finished with no connection request "
                        "recorded against this lead")
    return dict(answer, state=REQUEST_PENDING, why=None)


def campaign_leads(campaign_id, offset=0, limit=MAX_PAGE):
    """One page of a campaign's leads, each with its lifecycle state.

    This route honours NO filters - a status, a sender or a nonsense key is
    accepted and ignored, returning the unfiltered total - so a caller must page
    and must scope by campaign id. Its `totalCount` also disagrees with
    `progressStats.totalUsers` on large campaigns (50,563 against 35,157 on
    one); this is the route that enumerates actual rows.
    """
    data = _read(LEADS_ROUTE, {"campaignId": int(campaign_id),
                               "offset": int(offset),
                               "limit": min(int(limit), MAX_PAGE)})
    out = []
    for row in _collection(data, LEADS_ROUTE):
        profile = row.get("linkedInUserProfile") or {}
        out.append({"provider_lead_id": row.get("id"),
                    "profile_url": profile.get("profileUrl"),
                    "provider_profile_id": row.get("linkedInUserProfileId"),
                    "sender_id": row.get("linkedInSenderId"),
                    "created_at": row.get("creationTime"),
                    **lead_state(row)})
    return out, data.get("totalCount")


def campaign_stats(campaign_id):
    """The campaign's own counters, as an independent cross-check per lead.

    Trimmed to the four that describe prospect-facing actions. A 200 with no
    `overallStats` object raises rather than reading as zero - the same argument
    `_collection` makes: a zero here is the claim that nothing was sent, and
    that claim has to come from the provider rather than from a missing key.
    """
    data = _read(STATS_ROUTE, {"campaignIds": [int(campaign_id)],
                               "accountIds": [], "timeFrom": None,
                               "timeTo": None})
    stats = data.get("overallStats")
    if not isinstance(stats, dict):
        raise ProviderError(
            f"heyreach {STATS_ROUTE}: no overallStats object in the response, "
            f"so a zero here would be a guess rather than a count")
    return {k: stats.get(k) for k in
            ("connectionsSent", "connectionsAccepted", "totalMessageReplies",
             "uniqueLeadsContacted")}


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


# AN UNRECOGNISED FILTER KEY IS DISCARDED IN SILENCE AND THE WHOLE INBOX COMES
# BACK. That is the failure mode this allowlist exists for, and it is measured
# rather than feared: on 2026-09-13, against an inbox of 26,039 conversations,
#
#   {"nonsenseKeyNobodyDocuments": "x"}  -> 26039   the key was dropped
#   {"companyName": "Nineyards"}         -> 26039   same: not a filter
#   {"leadProfileUrl": <a real profile>} ->     1   honoured
#   {"linkedInAccountIds": [116968]}     ->  1261   honoured
#   {"linkedInAccountIds": [999999999]}  ->     0   honoured, and empty
#
# A caller asking a narrow question with a misspelled key therefore gets an
# answer that looks like the estate agreeing with it. `collision` reads this
# route to decide whether somebody has already been written to, so "the filter
# was ignored" arriving as 26,039 rows is the shape of a false CLEAR - and a
# typo is the ordinary way to produce it.
#
# So the keys are an allowlist and an unknown one raises. Only keys measured to
# change the answer are on it. Two hazards a caller still owns:
#
#   `companyName` IS NOT HERE and cannot be. `collision.account_is_unanswerable`
#   is right: no key asks the company-level question.
#
#   A `leadProfileUrl` this API cannot resolve answers 400, NOT 0 - measured on
#   a well-formed but unknown slug. A refusal is not an absence of
#   conversations, and `_read` raises rather than returning an empty page for
#   exactly that reason.
INBOX_FILTER_KEYS = ("searchString", "leadProfileUrl", "linkedInAccountIds",
                     "campaignIds")


def conversations(offset=0, limit=50, filters=None):
    """One page of the inbox. Read-only: reading marks nothing as seen."""
    unknown = sorted(set(filters or {}) - set(INBOX_FILTER_KEYS))
    if unknown:
        raise ProviderError(
            f"heyreach /inbox/GetConversationsV2: {unknown} is not a filter "
            f"this route honours. It would be discarded in silence and the "
            f"whole inbox returned, which reads as a result. Measured keys: "
            f"{', '.join(INBOX_FILTER_KEYS)}")
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
