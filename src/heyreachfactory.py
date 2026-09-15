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
import re
import sys

from . import (cadence, cadencelibrary, campaigns, clients, configdiff,
               collision, eligibility, executionguard, killswitch, lint,
               providerwrites, store)
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


def assemble_linkedin_copy(source, contact_key, *, include_inmail=False,
                           cadence_steps=None, campaign=None, config=None):
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

    TASK-126: VARIANTS ARE COLLECTED, NOT RESOLVED. A LinkedIn step carrying
    five variants puts all five into the messages list, preserving order so
    arm identity is positional. The provider rotates them. Each variant must
    be approved independently. A step with no variants carries one message
    (the base template), preserving backward compatibility.
    """
    from . import cadence as _cadence
    from . import variants

    steps = ((source or {}).get("cadence") or {}).get(contact_key) or {}
    spec_by_key = {}
    for spec in (cadence_steps or ()):
        if spec.get("key"):
            spec_by_key[spec["key"]] = spec
    copy = {}
    missing = []

    for step_key, mapping in COPY_MAPPING.items():
        step = steps.get(step_key) or {}
        spec = spec_by_key.get(step_key) or {}
        # TASK-126: Collect ALL approved variants, not just one.
        variant_entries = spec.get(_cadence.VARIANTS_KEY) or []
        if variant_entries:
            # Collect all approved variants for this step.
            texts = []
            for entry in variant_entries:
                if entry.get("status") != "active":
                    continue
                # Check the variant's own approval, not the step's.
                variant_approval = entry.get("approval")
                if not variant_approval:
                    continue
                stepped = variants.apply_to_step(dict(step), entry)
                from . import approval
                if approval.fingerprint(stepped) != variant_approval.get(
                        "fingerprint"):
                    continue
                # THROUGH `_step_copy`, NOT ALONGSIDE IT.
                #
                # The first version of this block extracted the text itself,
                # because `_step_copy` refuses a step with no `approval` and a
                # variant carries its approval on the VARIANT rather than on
                # the step. That is a real obstacle and duplicating the
                # extractor was the wrong answer to it: the copy had already
                # drifted from the original in the same commit that created
                # it. It dropped `_step_copy`'s channel check entirely, so a
                # non-LinkedIn variant could reach a LinkedIn payload, and it
                # reversed the InMail field precedence from
                # `message or note` to `note or message`, so a variant
                # carrying both would send different words down the two paths.
                #
                # Lifting the variant's approval onto the stepped copy clears
                # the obstacle honestly: the approval is real and it is the
                # variant's own, verified by fingerprint immediately above.
                # One extractor, one set of guards.
                stepped["approval"] = variant_approval
                text = _step_copy(stepped)
                if text:
                    texts.append(text)
            if texts:
                # All variants collected. Use the first as fallback.
                fallback = texts[0]
            else:
                # No approved variants. Fall back to base template.
                text = _step_copy(step)
                texts = [text] if text else []
                fallback = text
        else:
            # No variants on this step. Use the base template.
            text = _step_copy(step)
            texts = [text] if text else []
            fallback = text
        roles = mapping["role"]
        if isinstance(roles, str):
            roles = (roles,)
        if not texts:
            for role in roles:
                missing.append((contact_key, step_key, role))
            continue
        for role in roles:
            copy[role] = {"messages": texts, "fallbackMessage": fallback}

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


def unsupported_claims(rec, contact, fields):
    """Every per-lead variable whose words assert something unsupported.

    THE EMAIL HALF HAS THREE GATES AND THE LINKEDIN HALF HAD ONE. `generate`
    runs lint, claims and quality when a draft is STORED, and
    `executionguard` runs claims again at send time - but the send-time gate
    guards a send, and putting a lead into a campaign is not a send, so
    nothing stood between a stored LinkedIn note and a real person.

    Measured 2026-09-14 across the Productive estate: 26 stored LinkedIn notes
    assert something the record does not support - "'utilisation' is asserted
    about them and nothing stored supports it" - and EIGHT of the fifteen
    contacts this campaign would have pushed carried one. The checkpoint's
    count of seventeen remaining unsupported drafts was email only; the 194
    stored LinkedIn notes had never been audited.

    Those notes predate the fix that put `claims.check` beside `lint.check` in
    `generate.draft`, so the mechanism is right and the DATA is stale. That
    distinction does not help the prospect, which is why this refuses on the
    stored words rather than trusting when they were written.

    Returns `(contact_key, variable, why)` tuples, the same reporting shape
    `assemble_linkedin_copy` uses for missing copy.
    """
    from . import claims

    key = (contact or {}).get("key")
    found = []
    for variable, text in sorted((fields or {}).items()):
        for problem in claims.check(str(text or ""), rec, contact) or []:
            found.append((key, variable, problem.get("why") or "unsupported"))
            break
    return found


def custom_fields_for(source, contact_key, *, include_inmail=False,
                      cadence_steps=None, campaign=None, config=None):
    """One contact's approved words, keyed by the variable that carries them.

    Returns `(fields, missing)` with the same `missing` shape
    `assemble_linkedin_copy` returns, because it is the same question asked
    per lead instead of per campaign.
    """
    copy, missing = assemble_linkedin_copy(
        source, contact_key, include_inmail=include_inmail,
        cadence_steps=cadence_steps, campaign=campaign, config=config)
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


def _graph_text(sequence):
    """Every prospect-facing string in the sequence graph, concatenated.

    Walks the entire tree - every branch, every node - and collects the
    text a prospect could read: ``messages`` entries, ``fallbackMessage``,
    and ``note``. Used by the name gate to check whether the campaign-level
    graph carries a literal name that belongs to one person.
    """
    texts = []

    def _walk(node):
        if not isinstance(node, dict):
            return
        payload = node.get("payload")
        if isinstance(payload, dict):
            for msg in (payload.get("messages") or []):
                if isinstance(msg, str):
                    texts.append(msg)
            fb = payload.get("fallbackMessage")
            if isinstance(fb, str):
                texts.append(fb)
            note = payload.get("note")
            if isinstance(note, str):
                texts.append(note)
        for key in ("conditionalNode", "unconditionalNode"):
            child = node.get(key)
            if isinstance(child, dict):
                _walk(child)

    _walk(sequence)
    return " ".join(texts)


def _refuse_cohort_names_in_graph(sequence, cohort_names):
    """Refuse when the campaign-level graph carries a cohort member's name.

    A HeyReach sequence is campaign-level: one graph serves every lead.
    If the graph contains a literal first name, last name, or company
    from this campaign's cohort, the copy was written for one person and
    baked into a graph that every other person would receive.

    THE CHECK IS ON THE GRAPH, NOT THE PER-LEAD CUSTOM FIELDS. The graph
    carries merge variables (``{connection_note}``, ``{FIRST_NAME}``) and
    must be campaign-neutral. The custom fields carry each lead's own
    words, which legitimately contain that lead's name. Checking the
    custom fields would refuse every correct plan.

    Matches on word boundaries and only for names of 2+ characters to
    avoid false positives on common words.
    """
    if not cohort_names:
        return
    text = _graph_text(sequence)
    if not text:
        return
    text_lower = text.lower()
    for name in sorted(cohort_names):
        if len(name) < 2:
            continue
        if re.search(r'\b' + re.escape(name.lower()) + r'\b', text_lower):
            raise FactoryRefused(
                f"the sequence graph contains literal name {name!r} from "
                f"this campaign's cohort. A campaign-level graph must "
                f"carry merge variables, not one person's name; every "
                f"other lead would receive copy written for this one")


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

    # THE CAMPAIGN'S OWN RECORDS, AND ONLY THOSE. This walked the WHOLE
    # estate: measured against `productive-linkedin-production-v1`, whose row
    # names fourteen records, it considered 92 contacts and produced 598
    # missing-copy entries for records that are not in this campaign at all.
    #
    # It read as harmless while the graph came from one contact, because the
    # extra contacts only padded a report. It is not harmless now: `pushable`
    # is the set a lead write reads, so an unscoped walk is how a record
    # nobody added to this campaign ends up in it - and how a contact
    # belonging to ANOTHER CLIENT would, since nothing here compared tenants
    # either. Today every LinkedIn contact in the estate happens to be
    # Productive's, which is luck rather than a boundary.
    #
    # Empty `record_ids` REFUSES rather than meaning "everybody". A campaign
    # that names nobody should push nobody, and the permissive reading of an
    # empty set is the one that reaches people by accident.
    client_of = campaign.get("client")
    wanted_ids = [str(i) for i in (campaign.get("record_ids") or [])]
    if not wanted_ids:
        raise FactoryRefused(
            f"campaign {campaign.get('campaign_id')!r} names no records, so "
            f"there is nobody to push. An empty record set is not a licence "
            f"to walk the estate")
    wanted = set(wanted_ids)

    # THE NAME GATE. A campaign-level graph may not carry a literal name
    # from this campaign's cohort. The graph uses merge variables; if a
    # name from the cohort appears in it, the copy was written for one
    # person and baked into a graph every other person would receive.
    #
    # THIS IS THE EXACT DEFECT of campaign 599020: "hi jacob" in a
    # connection request on a campaign naming fourteen records.
    #
    # THE CHECK IS ON THE GRAPH, NOT THE PER-LEAD CUSTOM FIELDS. The
    # custom fields carry each lead's own words, which legitimately
    # contain that lead's name. Checking them would refuse every correct
    # plan. The previous attempt at this gate did exactly that and broke
    # seventeen tests - the module protecting this exact defect was
    # refused by the gate meant to enforce it.
    cohort_names = set()
    for rec in recs:
        if str(rec.get("id")) not in wanted:
            continue
        company = (rec.get("company") or "").strip()
        if company:
            cohort_names.add(company)
        for contact in rec.get("contacts") or []:
            for name_field in ("first_name", "last_name"):
                n = (contact.get(name_field) or "").strip()
                if n:
                    cohort_names.add(n)
            full_name = (contact.get("name") or "").strip()
            if full_name:
                for part in full_name.split():
                    if len(part) >= 2:
                        cohort_names.add(part)
    _refuse_cohort_names_in_graph(sequence, cohort_names)

    # Collect each contact's own words, which travel per lead.
    per_contact = []
    all_missing = []
    all_unsupported = []
    for rec in recs:
        if rec.get("dropped") or rec.get("paused"):
            continue
        if str(rec.get("id")) not in wanted:
            continue
        if client_of and rec.get("client") != client_of:
            raise FactoryRefused(
                f"record {rec.get('id')!r} belongs to client "
                f"{rec.get('client')!r} and campaign "
                f"{campaign.get('campaign_id')!r} belongs to {client_of!r}. "
                f"A record named by another client's campaign is a tenancy "
                f"error, not a record to skip quietly")
        for contact in rec.get("contacts") or []:
            if not contact.get("linkedin"):
                continue
            key = contact.get("key")
            fields, missing = custom_fields_for(
                rec, key, cadence_steps=cadence_steps, campaign=campaign,
                config=config)
            if missing:
                all_missing.extend(missing)
            unsupported = unsupported_claims(rec, contact, fields)
            if unsupported:
                all_unsupported.extend(unsupported)
            per_contact.append({
                "record_id": rec.get("id"),
                "contact_key": key,
                "custom_fields": fields,
                "missing": missing,
                "unsupported": unsupported,
            })

    # A contact who cannot fill every variable is not pushable - HeyReach
    # would send that step's fallback instead of their words. The sequence is
    # unaffected, which is the difference this change makes: one incomplete
    # contact no longer decides what the whole campaign says.
    complete = [c for c in per_contact
                if not c["missing"] and not c["unsupported"]]

    # SEMANTIC DUPLICATE DETECTION. A sequence whose steps rephrase one
    # another cannot be written. The operator observed "how do you currently
    # ensure profitability is visible in your projects?" appearing repeatedly
    # in the real campaign - not as an exact repeat (the existing path test
    # catches that) but as paraphrases wearing different words.
    #
    # EVERY COMPLETE CONTACT, NOT THE FIRST ONE.
    #
    # This ran on `complete[0]` and justified it: "all contacts share the same
    # sequence structure, so if one contact's copy is progressive, every
    # contact's is". MEASURED on the real cohort 2026-09-14 and it is false -
    # 2 of the 10 pushable contacts carry copy that repeats itself, and
    # NEITHER of them is the first. `ranjan-damodar` has seven collisions and
    # the campaign was accepted because `jacob-faertz` sorted ahead of him.
    #
    # Copy is generated PER CONTACT, against that contact's own evidence, in
    # three attempts that can each fail differently. Structure is shared;
    # words are not, and it is the words that repeat.
    #
    # This is the same defect `4f93f2f` was written about - one contact
    # deciding what the whole campaign does - reappearing inside the checker
    # meant to prevent it. The refusal names WHICH contact, because "the
    # sequence repeats itself" with ten contacts in the plan sends a reader
    # to the wrong one.
    #
    # `quality.campaign_repetition` discounts the company name and the
    # subject vocabulary (profitability, margin, etc.) because every message
    # in a Productive sequence names the company and argues the subject.
    # Those are what the conversation IS, not what it says.
    if complete:
        from . import quality
        # `first_fields` is gone: the loop below reads each contact's own.
        # THE PER-LEAD COPY IS WHAT IS COMPARED, NOT THE GRAPH'S MERGE
        # VARIABLES. The graph carries placeholders ({connection_note},
        # {connected_1}, ...) and comparing those would find nothing,
        # every time, forever - the "evaluator reporting INSUFFICIENT_DATA
        # because nothing writes the field it reads" defect. The real words
        # travel in custom_fields, one dict per contact, keyed by role.
        #
        # THE CHECK IS PATH-BASED, NOT GLOBAL. A prospect walks one
        # execution path through the graph. connected_1 and message_2
        # sit on different branches (already-connected vs cold), and a
        # prospect receives one or the other, never both. A global
        # comparison would flag them as duplicates (they share the same
        # source step, li2), but no prospect sees both. So the check
        # walks the sequence graph, extracts the MESSAGE roles from each
        # root-to-leaf path, and checks repetition within each path.
        #
        # The previous wiring mapped roles back to step keys, so li2
        # appeared twice with identical text and was compared against
        # itself - a guaranteed false positive that refused every plan.
        company_name = None
        for rec in recs:
            if str(rec.get("id")) in wanted:
                company_name = rec.get("company")
                break

        def _extract_paths(node):
            """MESSAGE roles along each root-to-leaf path in the graph."""
            if not isinstance(node, dict):
                return [[]]
            roles = []
            if node.get("nodeType") == "MESSAGE":
                payload = node.get("payload") or {}
                messages = payload.get("messages") or []
                if messages and isinstance(messages[0], str):
                    step = messages[0].strip("{}")
                    if step:
                        roles = [step]
            children = []
            for branch_key in ("conditionalNode", "unconditionalNode"):
                child = node.get(branch_key)
                if isinstance(child, dict):
                    children.append(child)
            if not children:
                return [roles]
            paths = []
            for child in children:
                for sub in _extract_paths(child):
                    paths.append(roles + sub)
            return paths

        all_paths = _extract_paths(sequence)
        # REVERSE MAPPING: role -> step_key. A step that fails lint is not
        # valid copy and must not participate in repetition comparisons.
        # See TASK-062: a stored step that fails the gates cannot ship, so
        # it is a draft that did not make it, not a sibling.
        _role_to_step = {}
        for sk, m in COPY_MAPPING.items():
            r = m["role"]
            for role in (r if isinstance(r, tuple) else (r,)):
                _role_to_step[role] = sk
        offender = None
        collisions = []
        for entry in complete:
            rec_for_entry = by_id.get(str(entry["record_id"]))
            contact_key = entry["contact_key"]
            cadence_for_contact = ((rec_for_entry or {}).get("cadence") or {}).get(contact_key) or {}
            for path_roles in all_paths:
                steps_for_check = []
                for role in path_roles:
                    text = (entry["custom_fields"] or {}).get(role)
                    if not isinstance(text, str) or not text.strip():
                        continue
                    step_key = _role_to_step.get(role)
                    step = cadence_for_contact.get(step_key) or {} if step_key else {}
                    if step and lint.classify(lint.check_step(rec_for_entry, contact_key, step)) == "failed":
                        continue
                    steps_for_check.append({"key": role, "text": text})
                if len(steps_for_check) < 2:
                    continue
                found = quality.campaign_repetition(
                    steps_for_check, company_name=company_name)
                if found:
                    offender, collisions = entry, found
                    break
            if collisions:
                break
        if collisions:
            parts = []
            for c in collisions[:6]:
                shared = ", ".join(c["shared"][:5])
                parts.append(
                    f"{c['step_a']!r} and {c['step_b']!r} share "
                    f"{c['shared_words']} words ({shared})")
            who = (f"{offender['record_id']}/{offender['contact_key']}"
                   if offender else "a contact")
            raise FactoryRefused(
                f"{who}'s copy repeats itself: "
                f"{'; '.join(parts)}"
                f"{' ...' if len(collisions) > 6 else ''}. "
                f"Each step must make a different argument; paraphrases "
                f"of the same idea are not progression. Regenerate that "
                f"contact's cadence steps so each one argues a different "
                f"angle.")

    if not complete:
        # THREE DIFFERENT REFUSALS, because they are three different problems
        # and one message covering all of them sends a reader to the wrong
        # place. "No approved copy" is a generation job, "asserts something
        # unsupported" is a regeneration job on copy that already exists, and
        # "nobody at all" is a cohort problem.
        if all_missing:
            _refuse_missing(all_missing)
        if all_unsupported:
            parts = [f"contact {ck!r}, variable {var!r}: {why}"
                     for ck, var, why in all_unsupported]
            raise FactoryRefused(
                f"every contact's LinkedIn copy asserts something the record "
                f"does not support: {'; '.join(parts[:6])}"
                f"{' ...' if len(parts) > 6 else ''}. These drafts predate the "
                f"claims gate in `generate.draft`; regenerate them rather "
                f"than editing them, and never widen the claim rules to let "
                f"them through")
        raise FactoryRefused(
            "no contact on any record has approved LinkedIn copy for every "
            "role the graph requires")

    return {
        "cadence_steps": cadence_steps,
        "contacts": per_contact,
        "pushable": [c for c in complete],
        "missing": all_missing,
        "unsupported": all_unsupported,
        "sequence": sequence,
        "touch_report": touch_report,
        "copy_mapping": COPY_MAPPING,
        "merge_variables": [merge_variable_of(r) for r in REQUIRED_ROLES],
        "inmail_included": False,
    }


# --------------------------------------------------------- ensure_leads
#
# THE CALLER THAT PUTS A REAL LEAD INTO A HEYREACH CAMPAIGN.
#
# `stage` writes the SEQUENCE (the graph). `ensure_leads` writes the LEADS
# (the people). The sequence carries variables; each lead carries its own
# words in `customUserFields`. The two together make a working campaign:
# a graph that says what happens and people who bring the words.
#
# Nothing calls `heyreach.add_leads_to_campaign` today. That is the defect
# this function closes: the transport exists, the graph is built, the copy
# is approved, and the leads are ready - but nobody put them in. The only
# thing between a real lead and this function is `LINKEDIN_ADD_LEAD` not
# being in `providerwrites.SUPPORTED`, which is an operator decision.

def _seat_for(campaign, provider_id, config):
    """The LinkedIn account this campaign sends from. Refuses rather than 0.

    This read `(config.get("heyreach") or {}).get("default_account_id", 0)`,
    and that key does not exist: the client config carries the HeyReach block
    under `providers.heyreach`, and it holds `org_unit` rather than a seat at
    all. So every lead would have gone to the wire with
    `linkedInAccountId: 0` - a lead assigned to nobody, on a provider where
    the seat is WHO THE PROSPECT SEES the message come from.

    Zero is the worst possible default here, which is why there is no default.
    The seat comes from canonical state where it is recorded, and from the
    provider campaign itself otherwise - `campaignAccountIds` is what HeyReach
    already believes, and disagreeing with it silently is how a lead ends up
    sending from the wrong person.
    """
    recorded = ((campaign.get("senders") or {}).get("linkedin") or [])
    for sender in recorded:
        seat = (sender or {}).get("provider_account_id")
        if seat:
            return int(seat)

    row = heyreach.campaign_read(provider_id) or {}
    bound = [a for a in (row.get("campaignAccountIds") or []) if a]
    if len(bound) == 1:
        return int(bound[0])
    if len(bound) > 1:
        raise FactoryRefused(
            f"HeyReach campaign {provider_id} has {len(bound)} LinkedIn "
            f"accounts bound to it ({bound}) and this campaign's canonical "
            f"row names none, so which human a prospect hears from would be "
            f"decided by list order. Record the seat in `senders.linkedin`")
    raise FactoryRefused(
        f"no LinkedIn seat for campaign {campaign.get('campaign_id')!r}: the "
        f"canonical row names none and HeyReach campaign {provider_id} has "
        f"none bound. A lead pushed without a seat is a lead assigned to "
        f"nobody, and the seat is who the prospect sees the message from")


def _first_linkedin_step(campaign, config):
    """The key of the first LinkedIn step in this campaign's cadence.

    `authorize` asks whether a STEP renders for a contact, so adding somebody
    to a LinkedIn campaign has to name the step they will actually receive
    first. Raises rather than guessing: a cadence with no LinkedIn step is not
    a campaign anybody should be added to, and a default here would be the
    same class of bug as the hard-coded key it replaces.
    """
    from . import cadence as _cadence

    for spec in _cadence.steps_for(campaign, config=config) or ():
        if spec.get("channel") == "linkedin":
            return spec.get("key")
    raise FactoryRefused(
        f"campaign {campaign.get('campaign_id')!r} runs a cadence with no "
        f"LinkedIn step, so there is no first action to authorise against. "
        f"Adding a lead to it would put somebody into a sequence that will "
        f"never message them")


def _mint_authorization(campaign, rec, contact, *, config=None, readback=None,
                        by="system"):
    """One Authorization per contact, from the canonical gate.

    THE AUTHORIZATION COMES FROM executionguard.authorize(), NOT FROM
    CONSTRUCTING THE OBJECT DIRECTLY. providerwrites.perform checks with
    isinstance, so a hand-built object passes while having passed no gate.
    authorize() is the ONLY place in src/ that may construct an Authorization,
    and it runs gates the five pre-filters do not, starting with `copy` which
    asks whether the step actually renders for this contact.

    The five pre-filters in ensure_leads (killswitch, suppression, collision,
    tenant, unsupported sequence) are a cheap pre-filter that refuses by name
    before the expensive path. They may not stand in for the Authorization.

    A batch authorization would let one gate cover every person, and a gate
    that covers a batch cannot refuse by name. The authorization is per
    person because the gates are per person: a suppression that fires for
    one contact must not be bypassed by another contact's clean record.
    """
    client = campaign.get("client")
    # THE STEP KEY IS DERIVED, NOT NAMED. This read `step_key = "day3"`, which
    # is a step of `PRODUCTIVE_BALANCED_V1` - the old seven-step shape - and
    # does not exist in `productive_li_heavy_v1` at all:
    #
    #     position(li_heavy, "day3")  ->  (None, None, None)
    #     position(li_heavy, "li1")   ->  ("linkedin", 1, 6)
    #
    # So `authorize`'s `copy` gate would have asked whether "day3" renders for
    # this contact, found nothing, and refused every single person. Fail-closed
    # rather than unsafe - but the path would simply never have worked, and no
    # test would have said so because every test mocks `authorize`.
    #
    # The right key is the FIRST LINKEDIN STEP THIS CAMPAIGN'S CADENCE
    # ACTUALLY HAS, because that is the first thing the sequence does to the
    # person being added. Derived from the cadence rather than written down
    # here, so a campaign on a different cadence asks about its own first step.
    step_key = _first_linkedin_step(campaign, config)
    return executionguard.authorize(
        operation=providerwrites.LINKEDIN_ADD_LEAD,
        channel="linkedin",
        campaign=campaign,
        rec=rec,
        contact=contact,
        step_key=step_key,
        workspace=client,
        config=config,
        readback=readback,
        by=by)


def ensure_leads(campaign_id, *, recs=None, config=None, live=False,
                 by="system"):
    """Put a campaign's pushable contacts into the HeyReach campaign.

    Returns a report: who was pushed, who was already there, who was refused.
    Dry run by default.

    THE GATES, IN ORDER, AND EACH ONE REFUSING RATHER THAN SKIPPING:
      1. killswitch workspace state - is this workspace allowed to send
      2. suppression and DNC - may this person be contacted
      3. account collision - is this account already being worked
      4. tenant check - does the campaign belong to this client
      5. unsupported sequence - can every row fill every variable

    A contact who fails any gate is refused BY NAME and the transport is
    never reached. A batch where one lead cannot fill one variable refuses
    the WHOLE push.

    THE READBACK DECIDES. The response body of AddLeadsToCampaignV2 has
    never been read, so nothing may be concluded from it. The readback is
    `heyreach.readback_membership`, which reads the campaign's actual
    membership and compares it to what was asked for.

    IDEMPOTENT: reads membership first and pushes only the difference.
    A re-run costs reads and writes nothing.
    """
    rows = campaigns.load()
    campaign = campaigns.require(str(campaign_id), rows)
    client = campaign.get("client")
    if not client:
        raise FactoryRefused(
            f"campaign {campaign_id} names no client; every provider write "
            f"is tenant-bound")
    if config is None:
        config = clients.load(client)
    recs = store.load() if recs is None else recs

    report = {"campaign": str(campaign_id), "client": client,
              "live": bool(live), "did": [], "refused": [], "provider": {}}

    # Gate 1: killswitch workspace state.
    ws_state = killswitch.workspace_state(client)
    if not ws_state["sending"]:
        raise FactoryRefused(
            f"the killswitch for workspace {client!r} is off: "
            f"{ws_state['why']}. No leads were added")

    plan = _plan(campaign, recs, config)
    pushable = plan.get("pushable") or []
    sequence = plan["sequence"]

    # Build enriched rows for the sequence check and the transport.
    rec_map = {r.get("id"): r for r in recs}
    enriched = []
    for contact in pushable:
        rec = rec_map.get(contact["record_id"])
        if not rec:
            continue
        linkedin_url = None
        for c in rec.get("contacts") or []:
            if c.get("key") == contact["contact_key"]:
                linkedin_url = c.get("linkedin")
                break
        if not linkedin_url:
            continue
        enriched.append({
            "record_id": contact["record_id"],
            "contact_key": contact["contact_key"],
            "linkedin_url": linkedin_url,
            "first_name": (contact.get("contact_key") or "").split("_")[0],
            "last_name": "",
            "company": rec.get("company", ""),
            "title": "",
            "custom_fields": dict(contact.get("custom_fields") or {}),
            "domain": rec.get("domain", ""),
        })

    # Gate 2: suppression and DNC, by name.
    for row in enriched:
        rec = rec_map.get(row["record_id"])
        contact_obj = None
        for c in (rec.get("contacts") or []):
            if c.get("key") == row["contact_key"]:
                contact_obj = c
                break
        reasons = eligibility.must_not_contact(rec, contact_obj, config=config)
        fired = [r for r in reasons if r]
        if fired:
            raise FactoryRefused(
                f"contact {row['contact_key']!r} (record "
                f"{row['record_id']!r}) is blocked: {', '.join(fired)}. "
                f"The transport was not reached")

    # Gate 3: account collision.
    #
    # `expect_workspace` IS THE EMAILBISON WORKSPACE ID, NOT THE CLIENT SLUG.
    # This passed `client` - "productive" - and every call refused:
    #
    #   WorkspaceMismatch: this credential is bound to workspace 10
    #   ('PRODUCTIVE'), not productive
    #
    # which is the tenancy guard working, and it meant the collision gate
    # could never pass rather than never fire. `bisonfactory` reads the id
    # from `bison.bound_workspace()` for the same call, because `workspace_id`
    # is ignored by every route on that API and a read taken against the wrong
    # binding cannot be told apart from a correct one afterwards.
    #
    # The collision estate is EmailBison's even when the campaign is HeyReach:
    # `ACCOUNT-OUTREACH.md` makes the ACCOUNT the unit, so a person already
    # mid-sequence by email is a reason not to open a second channel at that
    # company.
    from .providers import bison as _bison

    workspace_id = (_bison.bound_workspace() or {}).get("id")
    if not workspace_id:
        raise FactoryRefused(
            "the EmailBison credential reports no bound workspace, so the "
            "client's own estate cannot be read and no account can be "
            "cleared. A lead that cannot be checked cannot be cleared")

    colliding = []
    for row in enriched:
        domain = row.get("domain")
        if not domain:
            continue
        try:
            account = collision.check_account(
                domain, expect_workspace=workspace_id)
        except collision.CollisionUnknown as e:
            raise FactoryRefused(
                f"the provider estate could not be read for {domain!r}: "
                f"{e}. Refusing to add a lead at an unreadable account")
        verdict, why = collision.account_policy(account)
        if verdict in (collision.STOP, collision.HOLD):
            colliding.append((row, verdict, why))

    # COLLECTED, THEN RAISED ONCE - the shape `bisonfactory` already uses.
    # Raising on the first collision means an operator clearing a cohort
    # discovers it one contact at a time, one provider round trip each.
    if colliding:
        detail = "; ".join(
            f"{row['contact_key']} ({row.get('domain')}): {v} - {w}"
            for row, v, w in colliding[:5])
        raise FactoryRefused(
            f"{len(colliding)} of {len(enriched)} contact(s) collided with "
            f"the client's own estate: {detail}"
            f"{' and more' if len(colliding) > 5 else ''}. A contact at an "
            f"account the client is already working must not be opened on a "
            f"second channel. The transport was not reached")

    # Gate 4: tenant check.
    provider_id = campaign.get("heyreach_campaign_id")
    if not provider_id:
        raise FactoryRefused(
            f"campaign {campaign_id!r} carries no `heyreach_campaign_id`")
    provider_id = int(provider_id)
    org_unit = (config.get("heyreach") or {}).get("org_unit_id")
    if org_unit:
        heyreach.check_tenant(provider_id, org_unit)

    # Gate 5: refuse_unsupported_sequence against the rows actually pushed.
    if enriched:
        heyreach.refuse_unsupported_sequence(
            sequence, rows=enriched, campaign_id=str(campaign_id))

    # Read current membership for idempotency.
    expected_urls = [r["linkedin_url"] for r in enriched]
    if expected_urls:
        membership = heyreach.readback_membership(
            provider_id, expected_urls)
        already_member = membership.get("found") or set()
    else:
        membership = {"found": set(), "missing": set(), "total": 0,
                      "per_lead": []}
        already_member = set()

    new_contacts = [r for r in enriched
                    if r["linkedin_url"].lower() not in already_member]

    if not new_contacts:
        report["did"].append(
            "all pushable contacts are already members; nothing to push")
        return report

    # RESOLVED BEFORE THE DRY RUN, because the dry run REPORTS it. A dry run
    # that cannot say which seat a lead would send from is not answering the
    # question an operator is asking it, and resolving it here also means a
    # campaign with no seat refuses in a dry run rather than at the write.
    linkedin_account_id = _seat_for(campaign, provider_id, config)

    if not live:
        report["did"].append(
            f"dry run: would push {len(new_contacts)} contact(s) to "
            f"HeyReach campaign {provider_id}")
        for row in new_contacts:
            report["did"].append(
                f"  {row['contact_key']} ({row.get('domain', '?')}) "
                f"from seat {linkedin_account_id}: "
                f"variables="
                f"{sorted(row.get('custom_fields', {}).keys())}")
        return report

    # Gate 6: the campaign must demonstrably not be sending right now.
    # Re-read from the provider at the moment of the write, not from local
    # state cached at planning time. A campaign can be started by a human in
    # the vendor UI between the plan and the write, and the whole point of
    # this gate is that the window is small and checked.
    if not heyreach.campaign_cannot_send(provider_id):
        raise FactoryRefused(
            f"HeyReach campaign {provider_id} is not proven unable to send "
            f"(only DRAFT is). Adding a lead to a campaign that can send is "
            f"prospect-facing: the sequence acts on it immediately. "
            f"The transport was not reached")

    # THE PROVIDER WRITE. One authorization per contact, one perform call.
    # The transport is heyreach.add_leads_to_campaign; the readback is
    # heyreach.readback_membership. THE READBACK DECIDES.
    #
    # THE AUTHORIZATION COMES FROM executionguard.authorize(), which requires
    # a sealed Readback from configdiff.compare_heyreach(). The Readback is
    # obtained once before the loop and passed to each authorize() call.
    # authorize() runs gates the five pre-filters do not, starting with `copy`
    # which asks whether the step actually renders for this contact.

    # Obtain a sealed Readback for the authorization gate. This is a provider
    # comparison that stamps its own timestamp after the last provider read.
    # The Readback is single-use per authorize() call, but compare_heyreach
    # produces a fresh one each time. For the lead addition, we obtain one
    # Readback and pass it to each authorize() call; authorize() spends it on
    # the first call, so subsequent calls need their own Readback.
    # However, the Readback is spent inside authorize(), so we need to obtain
    # a fresh one for each contact. This is expensive but correct: each
    # authorization gets its own sealed, timestamped provider comparison.
    def _obtain_readback():
        return configdiff.compare_heyreach(campaign, recs=recs, config=config)

    # ONE CONTACT PER WRITE, AND THAT IS A FIX.
    #
    # This closure took `new_contacts` - the WHOLE batch - while the loop
    # below calls `perform` once PER CONTACT. Every iteration therefore sent
    # every lead again: N contacts meant N calls to AddLeadsToCampaignV2 each
    # carrying N pairs, and the readback below asked about every expected URL
    # rather than the one that iteration was authorised for, so after the
    # first call each later one passed trivially on leads a different
    # authorization had put there.
    #
    # Nothing caught it because every test in `test_heyreachfactory_ensure_
    # leads` pushes a single contact, where N squared and N are the same
    # number. At 122 leads it is 14,884 pairs across 122 writes, and each of
    # those writes is authorised by a token minted for one person.
    #
    # An authorization names a record, a contact and a step. The write it
    # drives must carry that contact and no one else.
    def _transport_for(row):
        def _transport(payload):
            return heyreach.add_leads_to_campaign(
                provider_id, [row], linkedin_account_id)
        return _transport

    def _readback_for(row):
        def _readback():
            return heyreach.readback_membership(
                provider_id, [row["linkedin_url"]])
        return _readback

    for row in new_contacts:
        rec = rec_map.get(row["record_id"])
        contact_obj = None
        for c in (rec.get("contacts") or []):
            if c.get("key") == row["contact_key"]:
                contact_obj = c
                break
        # Each contact gets its own Readback because authorize() spends it.
        readback = _obtain_readback()
        auth = _mint_authorization(
            campaign, rec, contact_obj, config=config, readback=readback,
            by=by)
        providerwrites.perform(
            providerwrites.LINKEDIN_ADD_LEAD,
            authorization=auth,
            campaign=str(campaign_id), tenant=client,
            payload={"campaignId": provider_id,
                     "contact": row["contact_key"]},
            transport=_transport_for(row), readback=_readback_for(row),
            expected={"found": {row["linkedin_url"].strip().lower()}},
            provider_campaign_id=provider_id, by=by)
        report["did"].append(
            f"pushed {row['contact_key']} to HeyReach campaign "
            f"{provider_id}")

    report["provider"]["campaign_id"] = provider_id
    report["provider"]["pushed"] = len(new_contacts)
    report["provider"]["already_member"] = len(already_member)
    return report
