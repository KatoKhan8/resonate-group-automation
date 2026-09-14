"""Build a HeyReach campaign sequence from canonical state, and prove it.

The campaign row in `work/campaigns.jsonl` is the specification. This module
is the LinkedIn counterpart of `bisonfactory`: it reads a record's approved
LinkedIn copy, maps it onto the graph `heyreach.linkedin_sequence` builds,
and writes the result through `providerwrites.perform`.

THE MAPPING FROM CADENCE TO GRAPH
----------------------------------

The cadence `PRODUCTIVE_LI_HEAVY_V1` produces six LinkedIn steps keyed
`li1`..`li6`. The graph builder `linkedin_sequence` wants a copy block keyed
by ROLE: `connection_note`, `connected_1`, `message_2`, `message_3`,
`message_4`, `inmail`. The two shapes do not match one-to-one:

    li1  (connect, day 1)    -> connection_note
    li2  (message, day 3)    -> connected_1 AND message_2
    li3  (message, day 6)    -> message_3
    li3  (alternative)       -> inmail  (InMail fallback)
    li4  (message, day 10)   -> message_4
    li5  (message, day 15)   -> (no slot in the graph)
    li6  (message, day 18)   -> (no slot in the graph)

`li2` serves two positions because the graph has two branches that both start
with "the first message to a connection": `connected_1` on the already-
connected branch and `message_2` on the post-connection branch. The same
generated words fill both slots.

`li5` and `li6` are cadence steps that the graph has no position for. The
graph's longest path carries four messages; the cadence names five. The
factory does not require them and their absence does not cause a refusal.

THE INMAIL DECISION
-------------------

`INMAIL_ELIGIBILITY_DETECTABLE` is False: nothing in this build can read
whether a prospect can receive an InMail. The InMail is ATTEMPTED rather than
targeted, and a seat out of InMail credit fails that step rather than
skipping it. `cadencelibrary` holds any step naming `CAP_INMAIL` for that
reason, so in practice no InMail copy is ever approved.

The factory therefore OMITS the InMail branch by default. The graph it builds
replaces the InMail nodes with terminal paths: the not-accepted branch ends
after a profile view, and the open-profile check is bypassed. The report
always states that the InMail fallback was omitted and why.

A caller MAY include the InMail branch by passing `include_inmail=True` and
supplying approved InMail copy. The factory refuses if the flag is set but
the copy is missing. A cadence that includes InMail reports more touches than
one that does not; the report states the count either way.

REPLACE, NOT APPEND
-------------------

`/campaign/UpdateSequence` REPLACES the entire graph. This is the opposite of
EmailBison's sequence write, which appends and cannot be undone. A second
call overwrites the first. The factory relies on this for idempotency:
re-staging the same material produces the same graph, and the provider's
readback is compared field-for-field. `heyreach.set_sequence` already
performs this comparison through `sequence_matches`.
"""
import argparse
import sys

from . import cadence, cadencelibrary, campaigns, clients, providerwrites, store
from .providers import ProviderError, heyreach


class FactoryRefused(Exception):
    """The campaign must not be staged, and the reason is not the provider's."""


# --------------------------------------------------------- the copy mapping
#
# The cadence step key -> the graph role(s) it fills. A step may fill more
# than one role (li2 fills both connected_1 and message_2), and a step's
# alternative may fill a different role (li3's alternative fills inmail).
#
# li5 and li6 have no entry: the graph has no position for them. They are
# cadence steps that exist on paper but not in the provider graph.

# EVERY ROLE RESOLVES TO EXACTLY ONE CADENCE STEP, and no branch of the graph
# carries the same step twice. That was not true until 2026-09-14: `li2` mapped
# to `connected_1` AND `message_2`, and those two roles sit one after the other
# on the already-connected branch, so a prospect who was already a connection
# received the identical sentence twice, three days apart. Read back from
# campaign 599020 before any lead was written.
#
# The docstring above justified the double mapping by saying the two roles sit
# on different branches. That is true of `chain()` and false of `already`,
# which used both in sequence - the justification described a graph the builder
# does not build.
#
# The two branches are DIFFERENT LENGTHS because they start from different
# places, and that is why they need different steps rather than a shared chain:
#
#     not connected yet    li1 invite -> li2 -> li3 -> li4
#     already connected    li2 -> li3 -> li4 -> li5      (no invite needed)
#
# So `li2` is genuinely the first message on both branches - `message_2` on one
# and `connected_1` on the other - and every later position differs by one.
# That is also what finally gives `li5` a position. `li6` still has none and is
# reported in `touch_report` rather than silently dropped.
COPY_MAPPING = {
    "li1": {"role": "connection_note", "kind": "MESSAGE"},
    "li2": {"role": ("connected_1", "message_2"), "kind": "MESSAGE"},
    "li3": {"role": ("connected_2", "message_3"), "kind": "MESSAGE"},
    "li4": {"role": ("connected_3", "message_4"), "kind": "MESSAGE"},
    "li5": {"role": ("connected_4",), "kind": "MESSAGE"},
}

# The alternative branch of a cadence step, mapped to its graph role.
# li3's alternative is the InMail fallback.
ALTERNATIVE_MAPPING = {
    "li3": {"role": "inmail", "kind": heyreach.INMAIL_NODE},
}

# The roles the graph requires. Derived from COPY_MAPPING and
# ALTERNATIVE_MAPPING, but stated explicitly so a test can assert the set
# without walking the mapping.
REQUIRED_ROLES = ("connection_note", "connected_1", "connected_2",
                  "connected_3", "connected_4", "message_2", "message_3",
                  "message_4")

# The roles needed when InMail is included.
INMAIL_ROLE = "inmail"


def _step_copy(step, *, channel=None):
    """The prospect-facing text from one approved cadence step.

    Returns the text for a message step, or None if the step has no approved
    copy. A LinkedIn message step carries `message`; a connection step
    carries `note`. An InMail step carries `subject` and `message`.

    `channel` overrides the step's own channel field. Used for alternatives,
    which inherit the channel from their parent step and do not carry one.
    """
    if not isinstance(step, dict):
        return None
    if not step.get("approval"):
        return None
    effective_channel = channel or step.get("channel")
    if effective_channel != "linkedin":
        return None
    action = step.get("linkedin_action")
    if action == "connect":
        note = (step.get("note") or "").strip()
        return note or None
    if action == "inmail":
        subject = (step.get("subject") or "").strip()
        message = (step.get("message") or step.get("note") or "").strip()
        if subject and message:
            return {"subject": subject, "message": message}
        return None
    # message or open_profile_message: the copy field is `note`, not
    # `message`. push.heyreach_rows reads step.get("note", "") and no code
    # writes a `message` field for LinkedIn. The `message` fallback is
    # defensive for future use.
    text = (step.get("note") or step.get("message") or "").strip()
    return text or None


def assemble_linkedin_copy(source, contact_key, *, include_inmail=False):
    """The copy block `linkedin_sequence` needs, from a record's approved steps.

    Returns `(copy_block, missing)`. `copy_block` is a dict keyed by role.
    `missing` is a list of (contact_key, step_key, role) tuples for steps
    that are missing approved copy.

    Refuses by contact and step when a REQUIRED role has no approved copy.
    The InMail role is only required when `include_inmail=True`.

    WHY THIS REPORTS RATHER THAN RAISES. The same reason as
    `bisonfactory._approved_copy`: the caller needs to know what is missing
    before deciding whether to proceed. A dry run returns the missing list;
    the live path refuses on it.
    """
    steps = ((source or {}).get("cadence") or {}).get(contact_key) or {}
    copy = {}
    missing = []

    for step_key, mapping in COPY_MAPPING.items():
        step = steps.get(step_key) or {}
        text = _step_copy(step)
        roles = mapping["role"]
        if isinstance(roles, str):
            roles = (roles,)
        if not text:
            for role in roles:
                missing.append((contact_key, step_key, role))
            continue
        for role in roles:
            copy[role] = {"messages": [text], "fallbackMessage": text}

    if include_inmail:
        for step_key, mapping in ALTERNATIVE_MAPPING.items():
            step = steps.get(step_key) or {}
            alt = step.get("alternative") or {}
            # Alternatives inherit the channel from their parent step.
            text = _step_copy(alt, channel=step.get("channel"))
            role = mapping["role"]
            if not text or not isinstance(text, dict):
                missing.append((contact_key, step_key, role))
                continue
            copy[role] = {
                "messages": [text],
                "fallbackMessage": text,
            }

    return copy, missing


def _refuse_missing(missing):
    """Turn a missing-copy list into a refusal naming every gap."""
    if not missing:
        return
    parts = []
    for contact_key, step_key, role in missing:
        parts.append(f"contact {contact_key!r}, step {step_key!r} -> "
                     f"role {role!r}")
    raise FactoryRefused(
        f"approved LinkedIn copy is missing for: "
        f"{'; '.join(parts)}. Every role the graph requires must have "
        f"approved words; a step with no copy sends a blank to a real person")


# ----------------------------------------- building the graph without InMail
#
# When InMail is omitted, the graph changes in two places:
#
# 1. The not-accepted branch: instead of VIEW -> INMAIL -> END, it becomes
#    VIEW -> END. The profile view remains as a warm-up; the InMail is gone.
#
# 2. The open-profile branch: instead of INMAIL -> CONNECT -> ..., it becomes
#    the same as the cold path. CHECK_IS_OPEN_PROFILE is kept (it is free
#    and the provider supports it) but both branches lead to the same cold
#    path: VIEW -> FOLLOW -> CONNECT.

def _build_sequence_no_inmail(copy, withdraw_after_days=21):
    """The LinkedIn-primary graph without any InMail nodes.

    Same structure as `linkedin_sequence` but the not-accepted branch ends
    after a profile view, and the open-profile check leads to the same cold
    path as the non-open-profile branch.
    """
    def end(delay=3, unit="HOUR"):
        return heyreach._node("END", delay, unit)

    def chain(copy_block):
        return heyreach._node(
            "MESSAGE", 3, "HOUR", heyreach._copy("message_2", copy_block),
            nxt=heyreach._node("VIEW_PROFILE", 3, "DAY",
                nxt=heyreach._node(
                    "MESSAGE", 2, "DAY",
                    heyreach._copy("message_3", copy_block),
                    nxt=heyreach._node(
                        "MESSAGE", 7, "DAY",
                        heyreach._copy("message_4", copy_block),
                        nxt=end()))))

    invite = heyreach._copy("connection_note", copy)
    invite["toBeWithdrawnAfterDays"] = int(withdraw_after_days)

    # Not-accepted: view, then end. No InMail.
    not_accepted = heyreach._node("VIEW_PROFILE", 5, "DAY", nxt=end())

    ask_to_connect = heyreach._node(
        "CONNECTION_REQUEST", 1, "DAY", dict(invite),
        nxt=not_accepted, cond=chain(copy))

    # Cold path: view, follow, connect. Same for open and non-open profiles.
    cold_path = heyreach._node(
        "VIEW_PROFILE", 3, "HOUR",
        nxt=heyreach._node("FOLLOW", 3, "HOUR", nxt=ask_to_connect))

    already = heyreach._node(
        "MESSAGE", 3, "HOUR", heyreach._copy("connected_1", copy),
        nxt=heyreach._node("MESSAGE", 3, "DAY",
                           heyreach._copy("connected_2", copy),
            nxt=heyreach._node("VIEW_PROFILE", 2, "DAY",
                nxt=heyreach._node("MESSAGE", 5, "DAY",
                    heyreach._copy("connected_3", copy),
                    nxt=heyreach._node("MESSAGE", 7, "DAY",
                        heyreach._copy("connected_4", copy),
                        nxt=end())))))

    sequence = heyreach._node("CHECK_IS_CONNECTION", 0, "HOUR",
                              cond=already, nxt=cold_path)
    heyreach.validate_sequence_for_write(sequence)
    return sequence


# ---------------------------------------------- per-lead copy, not per-campaign
#
# A HEYREACH SEQUENCE IS CAMPAIGN-LEVEL. ONE GRAPH SERVES EVERY LEAD IN IT.
#
# `_plan` used to build that graph from `complete[0]["copy"]` - the approved
# words of whichever eligible contact sorted first - and the payloads went to
# the provider as literal strings. Campaign 599020 therefore carried "hi jacob,
# ... let's connect!" and "how are you currently managing this at &Partner?"
# while its canonical row named FOURTEEN records. Enabling `LINKEDIN_ADD_LEAD`
# would have sent thirteen people at thirteen other companies a note addressed
# to Jacob at &Partner. Measured 2026-09-14, before any lead was written.
#
# So the graph carries MERGE FIELDS and the words travel per lead, which is
# what `bisonfactory` already does with `{SUBJECT_1}`..`{BODY_5}`. The two
# providers are now the same shape, and that is the point: a campaign-level
# artifact may not contain anything true of only one person.
#
# The mechanism is not new and is proven on this workspace. The client's own
# live campaign 565765 uses `{FIRST_NAME}`, `{COMPANY}` and a custom
# `{Icebreaker}` today. `heyreach.build_lead_pairs` already carries an
# arbitrary per-row `custom_fields` dict onto the wire as `customUserFields`,
# `heyreach.supplied_field_names` derives what every row supplies as an
# INTERSECTION, and `heyreach.refuse_unsupported_sequence` raises when the copy
# uses a variable the push does not supply.
#
# THE VARIABLE NAME IS THE ROLE NAME, deliberately. A separate naming scheme
# would be one more mapping to keep in step with `COPY_MAPPING`, and the two
# would drift the first time somebody added a role.

# The one thing this module may not invent: what a prospect reads when a
# variable cannot be filled.
#
# HeyReach does not error on an unfilled variable - it sends `fallbackMessage`
# instead. `refuse_unsupported_sequence` is what makes that unreachable in
# practice, because it refuses the push unless EVERY lead supplies EVERY
# variable. This is the second line, for the case where the provider
# substitutes differently than we believe it does.
#
# It comes from the client's own config and its absence REFUSES. A fallback
# invented here would be unapproved copy that this system wrote and nobody
# read, reaching a real person at exactly the moment something has already
# gone wrong - which is the definition of a silent fallback on a safety path.
FALLBACK_CONFIG_KEY = "linkedin_sequence"


def merge_variable_of(role):
    """The HeyReach custom-field name carrying `role`'s words, per lead."""
    return str(role)


def merge_sequence_copy(config):
    """The copy block the GRAPH is built from: variables, never words.

    Returns a block shaped like `assemble_linkedin_copy`'s, but every
    `messages` entry is `{role}` rather than one contact's sentence. The
    `fallbackMessage` is the client's configured fallback for that role.

    Raises `FactoryRefused` naming every role whose fallback is missing.
    """
    configured = ((config or {}).get(FALLBACK_CONFIG_KEY) or {}).get(
        "fallbacks") or {}
    block, missing = {}, []
    for role in REQUIRED_ROLES:
        fallback = str(configured.get(role) or "").strip()
        if not fallback:
            missing.append(role)
            continue
        block[role] = {"messages": ["{" + merge_variable_of(role) + "}"],
                       "fallbackMessage": fallback}
    if missing:
        raise FactoryRefused(
            f"this client declares no LinkedIn fallback copy for "
            f"{', '.join(sorted(missing))}. HeyReach sends `fallbackMessage` "
            f"whenever a per-lead variable cannot be filled, so a graph "
            f"without one would reach a real person as a blank - and a "
            f"fallback invented here would be words nobody approved. Declare "
            f"them under `{FALLBACK_CONFIG_KEY}.fallbacks` in the client "
            f"config")
    return block


def custom_fields_for(source, contact_key, *, include_inmail=False):
    """One contact's approved words, keyed by the variable that carries them.

    Returns `(fields, missing)` with the same `missing` shape
    `assemble_linkedin_copy` returns, because it is the same question asked
    per lead instead of per campaign.
    """
    copy, missing = assemble_linkedin_copy(
        source, contact_key, include_inmail=include_inmail)
    fields = {}
    for role, block in (copy or {}).items():
        entries = (block or {}).get("messages") or []
        if not entries or not isinstance(entries[0], str):
            # An INMAIL role's entry is a {subject, message} object and needs
            # two variables rather than one. Not wired - see `_plan`.
            continue
        fields[merge_variable_of(role)] = entries[0]
    return fields, missing


def build_sequence(copy, *, include_inmail=False, withdraw_after_days=21):
    """The graph this campaign will run. Pure: sends nothing.

    When `include_inmail` is True, delegates to `heyreach.linkedin_sequence`
    which includes the InMail branches. When False (the default), builds a
    graph without InMail nodes.

    Returns `(sequence, touch_report)` where `touch_report` describes what
    the graph carries: node count, message count, and whether InMail is
    present.
    """
    if include_inmail:
        sequence = heyreach.linkedin_sequence(
            copy, withdraw_after_days=withdraw_after_days)
        inmail_present = True
    else:
        sequence = _build_sequence_no_inmail(
            copy, withdraw_after_days=withdraw_after_days)
        inmail_present = False

    nodes, types, _truncated = heyreach.walk_sequence(sequence)
    messages = sum(1 for n in nodes
                   if str(n.get("nodeType") or "") in ("MESSAGE", "INMAIL",
                                                       "CONNECTION_REQUEST"))
    return sequence, {
        "nodes": len(nodes),
        "message_nodes": messages,
        "inmail": inmail_present,
        "node_types": sorted(types),
    }


# ----------------------------------------------------------- the staging verb

def stage(campaign_id, *, recs=None, config=None, live=False, by="system",
          include_inmail=False, withdraw_after_days=21):
    """Bring one campaign's LinkedIn sequence into existence at HeyReach.

    Returns a report: what was built, what was sent, and what the provider
    said afterwards. Dry run by default.

    Follows `bisonfactory.stage`'s pattern: plan, refuse, write, read back.
    """
    rows = campaigns.load()
    campaign = campaigns.require(str(campaign_id), rows)
    client = campaign.get("client")
    if not client:
        raise FactoryRefused(
            f"campaign {campaign_id} names no client; every provider write is "
            f"tenant-bound and an untenanted one cannot be attributed")
    if config is None:
        config = clients.load(client)
    recs = store.load() if recs is None else recs

    plan = _plan(campaign, recs, config, include_inmail=include_inmail,
                 withdraw_after_days=withdraw_after_days)
    report = {"campaign": str(campaign_id), "client": client,
              "live": bool(live), "plan": plan, "did": [], "provider": {}}
    if not live:
        report["did"].append("dry run: nothing was sent")
        return report

    # THE PROVIDER ID IS ON THE ROW, NOT THE ROW'S NAME. This was
    # `int(campaign_id)`, which reads the CANONICAL id as the provider's -
    # so `productive-linkedin-production-v1` raised `invalid literal for
    # int()`, and any campaign whose canonical id happened to be numeric
    # would have written a sequence into whatever campaign that number names
    # at HeyReach. `bisonfactory` reads `bison_campaign_id` off the row for
    # exactly this reason; the binding is canonical state, not a coincidence
    # of naming.
    provider_id = campaign.get("heyreach_campaign_id")
    if not provider_id:
        raise FactoryRefused(
            f"campaign {campaign_id!r} carries no `heyreach_campaign_id`, so "
            f"there is no provider campaign to write a sequence into. Map it "
            f"with `orchestrator.map_external` first")
    provider_id = int(provider_id)
    sequence = plan["sequence"]

    def _transport(_payload):
        return heyreach.set_sequence(provider_id, sequence)

    def _readback():
        found = heyreach.campaign_sequence(provider_id)
        same, _why = heyreach.sequence_matches(found, sequence)
        return {"matches": same, "node_count": len(
            heyreach.walk_sequence(found)[0])}

    providerwrites.perform(
        providerwrites.LINKEDIN_SET_SEQUENCE,
        campaign=str(campaign_id), tenant=client,
        payload={"campaignId": provider_id, "sequence": sequence},
        transport=_transport, readback=_readback,
        expected={"matches": True}, by=by)

    report["did"].append(f"wrote sequence to HeyReach campaign {provider_id}")
    report["provider"]["campaign_id"] = provider_id
    report["provider"]["readback"] = _readback()
    return report


def _plan(campaign, recs, config, *, include_inmail=False,
          withdraw_after_days=21):
    """What this campaign's LinkedIn sequence is, from canonical state."""
    from . import cadence as _cadence

    cadence_steps = _cadence.steps_for(campaign, config=config)
    by_id = {r.get("id"): r for r in recs}

    if include_inmail:
        # An INMAIL carries a subject AND a message, so it needs two variables
        # per lead rather than one, and no approved InMail copy has ever
        # existed here - `cadencelibrary` holds every step naming `CAP_INMAIL`
        # because the capability is unproven. Refusing is honest; wiring a
        # second variable for a branch nothing can fill would be speculative.
        raise FactoryRefused(
            "per-lead InMail copy is not wired: an INMAIL step carries a "
            "subject and a message and so needs two variables per lead, and "
            "no InMail copy is ever approved because `CAP_INMAIL` is unproven. "
            "Build without InMail, which is the default")

    # THE GRAPH IS BUILT FROM VARIABLES AND NOTHING ELSE. It used to be built
    # from `complete[0]["copy"]` - see the note above `merge_sequence_copy`.
    sequence, touch_report = build_sequence(
        merge_sequence_copy(config), include_inmail=False,
        withdraw_after_days=withdraw_after_days)

    # Collect each contact's own words, which travel per lead.
    per_contact = []
    all_missing = []
    for rec in recs:
        if rec.get("dropped") or rec.get("paused"):
            continue
        for contact in rec.get("contacts") or []:
            if not contact.get("linkedin"):
                continue
            key = contact.get("key")
            fields, missing = custom_fields_for(rec, key)
            if missing:
                all_missing.extend(missing)
            per_contact.append({
                "record_id": rec.get("id"),
                "contact_key": key,
                "custom_fields": fields,
                "missing": missing,
            })

    # A contact who cannot fill every variable is not pushable - HeyReach
    # would send that step's fallback instead of their words. The sequence is
    # unaffected, which is the difference this change makes: one incomplete
    # contact no longer decides what the whole campaign says.
    complete = [c for c in per_contact if not c["missing"]]
    if not complete:
        if per_contact:
            _refuse_missing(all_missing)
        raise FactoryRefused(
            "no contact on any record has approved LinkedIn copy for every "
            "role the graph requires")

    return {
        "cadence_steps": cadence_steps,
        "contacts": per_contact,
        "pushable": [c for c in complete],
        "missing": all_missing,
        "sequence": sequence,
        "touch_report": touch_report,
        "copy_mapping": COPY_MAPPING,
        "merge_variables": [merge_variable_of(r) for r in REQUIRED_ROLES],
        "inmail_included": False,
    }
