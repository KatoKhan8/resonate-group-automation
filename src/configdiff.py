#!/usr/bin/env python3
"""Does the provider hold what was approved? Answered field by field.

THE DEFECT THIS EXISTS TO CATCH, AND IT IS NOT HYPOTHETICAL. On 2026-09-09 a
dedicated one-lead LinkedIn canary campaign was built by hand in the vendor UI
with the approved note pasted in. Provider read-back showed the graph held
HeyReach's own pre-filled placeholder, `Hey, would love to connect!`. Every
check the system had passed it: the sequence was provably LinkedIn-only, no
hazard fired, the note was not empty, the lead was the right person, the sender
was the right seat, the workspace was right. Nothing compared the sentence a
human would read against the sentence that was approved, because nothing
compared anything.

So this module answers one question - "is the provider configured exactly as
approved" - and answers it about every field at once rather than about whichever
field somebody remembered to look at.

FOUR RULES, AND THEY ARE THE WHOLE DESIGN.

1. `APPROVED_CONFIG` is built from canonical state ONLY. If it were ever built
   from the provider, the comparison would be the provider agreeing with
   itself, which is how a placeholder passes.

2. The diff walks the UNION of both sides' keys. A sender, lead or sequence
   node that exists at the provider and in nobody's approval is `UNEXPECTED`
   and fails. A checklist of fields somebody thought of cannot catch the field
   they did not.

3. `UNVERIFIABLE` is a FAILURE for any required field, not a warning. On
   HeyReach that now applies to the campaign limit alone: no read route exposes
   a per-campaign daily limit, so `daily_limit` is structurally unverifiable and
   is omitted from `REQUIRED_HEYREACH`.

   THE LEAD SET IS NO LONGER AMONG THEM, and the correction matters because the
   old claim was load-bearing. This rule used to read "HeyReach exposes no route
   for a campaign's lead identities", and every staging argument rested on it:
   `lead_set` came back `UNVERIFIABLE` and a campaign was proven by
   `lead_count` plus a verified list id. `/campaign/GetLeadsFromCampaign`
   returns a profile URL and a `linkedInUserProfileId` per lead - the
   identities were readable the whole time this module said they were not. The
   diff now asserts WHO the provider holds rather than how many.

4. Nothing here writes, to state or to a provider. It reads canonical state and
   read-only provider routes. A differ that could edit either side to make them
   agree would be worse than no differ.
"""
import collections
import json
import sys

from . import campaigns as campaigns_state
from . import approval, cadence, clients, collision, store
from .providers import bison, heyreach, ok, request

# ------------------------------------------------------------------ verdicts

MATCH = "match"
MISMATCH = "mismatch"            # both sides have it and they differ
UNEXPECTED = "unexpected"        # the provider has it and no approval does
MISSING = "missing"              # approved and the provider does not have it
UNVERIFIABLE = "unverifiable"    # no read route exposes it at all

FAILING = (MISMATCH, UNEXPECTED, MISSING, UNVERIFIABLE)

PASS = "PASS"
FAIL = "FAIL"

# Fields that must be VERIFIED and MATCH for a channel to pass. A field absent
# from this tuple is still diffed and still reported; it just does not fail the
# verdict on its own. Keeping the two ideas separate means a new field can be
# observed for a while before it is made blocking.
REQUIRED_HEYREACH = (
    "campaign_id", "campaign_name", "status", "org_unit", "sender_ids",
    # `lead_set` IS REQUIRED NOW. It used to be omitted because this module
    # believed the identities were unreadable, so a campaign could pass on a
    # count alone - "the provider holds one lead" rather than "the provider
    # holds this person". `/campaign/GetLeadsFromCampaign` answers the stronger
    # question, so the diff asks it.
    "list_id", "lead_set", "lead_count", "actions", "note", "delays",
    "linkedin_only", "bison_handoff",
)

REQUIRED_BISON = (
    "campaign_id", "campaign_name", "status", "workspace", "sender_ids",
    # WHO, NOT HOW MANY - the same correction `REQUIRED_HEYREACH` already
    # carries above. `lead_count` alone says "the provider holds one lead",
    # and the wrong person passes that as easily as the right one. `lead_set`
    # was computed on both sides and compared by nothing, so the email lane
    # verified an approved head-count against a provider head-count and
    # called it a match.
    "lead_set",
    "lead_count", "actions", "subjects", "bodies", "delays",
    "max_emails_per_day", "max_new_leads_per_day",
)


class DiffRefused(RuntimeError):
    """The comparison could not be made. Never a PASS.

    Raised rather than returning FAIL when the inputs themselves are unusable -
    no campaign id, no approval, an unreadable graph. FAIL means "they differ";
    this means "the question was not asked", and collapsing the two is how a
    campaign nobody checked reads as a campaign that passed.
    """


# ------------------------------------------------------- normalising helpers

def _norm_text(value):
    """Whitespace-normalised. Case and punctuation are the copy and survive."""
    return " ".join(str(value or "").split())


def _ids(values):
    """A comparable set of provider ids, as strings.

    IT READ THE WRONG KEY OFF A SENDER ROW, and the failure was silent in the
    direction that matters. A canonical campaign stores its senders as
    `{"provider_account_id": 174892}` - `senderidentity` writes that key for
    both providers and `heyreachfactory._seat_for` reads it - and this asked
    for `id`, got None, and skipped the entry. So the APPROVED sender set of
    every HeyReach and EmailBison campaign was the empty set.

    Against a provider that reports a seat that is MISMATCH, which is how it
    was found: campaign 599020's diff failed on `sender_ids` alone, approved
    `frozenset()` against provider `{'174892'}`, on a campaign whose seat was
    correct and had been correct for days.

    Against a provider reporting NO seats it is worse and would not have been
    found: empty would have matched empty and the field would have passed
    while asserting nothing. A campaign with no sender assigned would have
    read as a campaign whose senders were exactly as approved.

    `id` is kept because `approved_bison` passes rows the provider returns,
    which do use it. A row carrying neither key is still skipped - but it is
    now much harder for a whole side to be empty by accident.
    """
    out = set()
    for value in values or ():
        if isinstance(value, dict):
            value = (value.get("provider_account_id")
                     if value.get("provider_account_id") not in (None, "")
                     else value.get("id"))
        if value in (None, ""):
            continue
        out.add(str(value).strip())
    return frozenset(out)


# ------------------------------------------------------- APPROVED, HeyReach

def _approved_for_campaign(rec, contact, config):
    """Whether this contact has approved copy for every role the graph needs.

    ASKED OF THE FACTORY THAT OWNS THE QUESTION, not answered again here.
    `heyreachfactory.custom_fields_for` is what `_plan` uses to decide who is
    pushable, and it reads the campaign's own `COPY_MAPPING` roles - li1 to
    li5 - through `assemble_linkedin_copy`, which returns a role's words only
    when that step carries an `approval`.

    Keeping a second opinion about it here is how the two drift, and a drift
    on this particular question means the diff blesses a lead set the factory
    would refuse, or refuses one it would push. The import is local because
    `heyreachfactory` imports this module at the top of the file.
    """
    from . import heyreachfactory

    _fields, missing = heyreachfactory.custom_fields_for(
        rec, contact.get("key"), config=config)
    return not missing


def approved_heyreach(campaign, recs=None, config=None):
    """What canonical state says this LinkedIn campaign should be.

    `campaign` is a canonical campaign row - the binding of a
    provider campaign to records, senders and limits.

    TWO SHAPES OF CAMPAIGN, AND THE ROW SAYS WHICH. A campaign that declares
    no `provider_note` is the single-step canary this function was written
    for: its copy comes from the per-contact cadence step, so a template
    change moves the approved note and the diff fails until somebody
    re-approves, which is the point. A campaign that DOES declare one carries
    merge variables at the provider and its words travel per lead - see the
    long note below for what that gives up and what it does not.
    """
    from . import collision
    if not campaign:
        raise DiffRefused("no canonical campaign row to compare against")
    cid = campaign.get("heyreach_campaign_id")
    if cid in (None, ""):
        raise DiffRefused(
            "the canonical campaign names no heyreach_campaign_id, so there is "
            "nothing to compare it to")
    recs = recs if recs is not None else store.load()
    config = config or clients.load(campaign.get("client"))
    wanted = set(campaign.get("record_ids") or ())
    rows = [r for r in recs if r.get("id") in wanted]

    # WHICH SHAPE OF CAMPAIGN IS THIS, AND THE ROW HAS TO SAY.
    #
    # This function could only ever describe ONE shape: a single-step canary
    # whose graph is CONNECTION_REQUEST then END and which carries one literal
    # note, rendered from one contact's `day3` step. That was campaign 594061
    # and it was right for it.
    #
    # Campaign 599020 is not that. Its graph has 24 nodes and six node types,
    # and - the fact checkpoint E calls the most important one in the system -
    # it carries MERGE VARIABLES rather than words. Read back from the
    # provider, its connection-request payload is the literal string
    # `{connection_note}`; each lead brings its own approved words in
    # `customUserFields`. So every field this function derived from a rendered
    # note described a campaign that does not exist, and the diff could not
    # pass for a reason that had nothing to do with safety.
    #
    # The row declares its shape, and a row that does not is refused rather
    # than guessed. That is the rule this module already set for itself over
    # `provider_delays` - "a cadence day is a position in a schedule, an
    # actionDelay is a wait after the lead enters this campaign" - and the
    # same argument applies here with more force, because guessing the note
    # means guessing what a real person reads.
    #
    # WHAT DECLARING THE NOTE DOES NOT GIVE UP. The protection being replaced
    # was that a template edit moves the fingerprint and drops the contact out
    # of the approved set until somebody re-approves. In a merge-variable
    # campaign that protection does not weaken, it MOVES to where the words
    # now are: `heyreachfactory._plan` refuses any contact without approved
    # copy for every role the graph requires, and `providerwrites.
    # _require_approved_words` re-checks the fingerprint at the write and then
    # checks the approved text literally appears in the payload. The words are
    # still fingerprint-bound. They are just no longer in the graph.
    declared_note = campaign.get("provider_note")
    declared_actions = campaign.get("provider_actions")
    if declared_note is not None and not declared_actions:
        raise DiffRefused(
            "this campaign declares `provider_note`, so it is a "
            "merge-variable campaign whose graph this function cannot derive "
            "from a cadence step - and it declares no `provider_actions`. A "
            "campaign that states what its graph SAYS must also state what "
            "its graph DOES, or the diff checks the words and not the shape")

    leads, notes, actions = set(), [], []
    for rec in rows:
        for contact in rec.get("contacts") or ():
            if declared_note is not None:
                # The lead set is who this campaign may legitimately contain.
                # The copy question was answered above and per-lead; what is
                # left here is identity, and `_approved_for_campaign` asks the
                # factory that owns the campaign's own copy roles rather than
                # this module keeping a second opinion about them.
                if not _approved_for_campaign(rec, contact, config):
                    continue
                slug = collision.profile_slug(contact.get("linkedin"))
                if not slug:
                    raise DiffRefused(
                        f"{contact.get('name')!r} has no readable LinkedIn "
                        f"profile, so the approved lead set cannot be stated")
                leads.add(slug)
                continue
            step = cadence.expand_step(rec, contact, LINKEDIN_STEP, config)
            if not step:
                continue
            # ONLY APPROVED STEPS ARE IN THE APPROVED CONFIG.
            #
            # Without this, every contact on a named record counted as
            # approved. The first record this ran against carried two selected
            # champions and one approval, so the approved lead set silently
            # became two people and the approved note became ambiguous - the
            # diff would then have refused for the wrong reason, or worse,
            # passed a campaign containing somebody nobody blessed.
            #
            # `approval.is_approved` is fingerprint-bound, so an edit to the
            # template or the angle moves the fingerprint and drops the contact
            # out of the approved set until a human approves the new words.
            if not approval.is_approved(rec, contact["key"],
                                        LINKEDIN_STEP["key"], step):
                continue
            slug = collision.profile_slug(contact.get("linkedin"))
            if not slug:
                raise DiffRefused(
                    f"{contact.get('name')!r} has no readable LinkedIn profile, "
                    f"so the approved lead set cannot be stated")
            leads.add(slug)
            notes.append(_norm_text(step.get("note")))
            actions.append("CONNECTION_REQUEST")

    if declared_note is not None:
        if not leads:
            raise DiffRefused(
                "no contact on this campaign's records has approved copy for "
                "every role its graph requires, so the approved lead set is "
                "empty and there is nobody this campaign may legitimately "
                "hold. An unapproved contact is not an approved config")
        notes = [_norm_text(declared_note)]
        actions = list(declared_actions)
    elif not notes:
        raise DiffRefused(
            "no APPROVED and renderable LinkedIn step on any of this "
            "campaign's records; an unapproved step is not an approved config")
    elif len(set(notes)) > 1:
        raise DiffRefused(
            f"{len(set(notes))} different approved notes across this campaign's "
            f"records; one campaign carries one note at the provider, so the "
            f"comparison is not well defined")

    # THE PROVIDER DELAY IS DECLARED, NOT DERIVED FROM THE CADENCE DAY.
    #
    # This got it wrong first. `cadence.STEPS` says day 3, so the approved
    # delay was built as `("DAY", 3)` - and the real graph read back
    # `("HOUR", 0)`, producing a mismatch on a campaign that was correct.
    #
    # They are different quantities. The cadence day is where a step sits in a
    # multi-channel schedule across weeks. A HeyReach `actionDelay` is how long
    # the node waits after the lead ENTERS THIS CAMPAIGN, and for a dedicated
    # one-step canary the intended answer is "immediately". Deriving one from
    # the other silently asserts they mean the same thing.
    #
    # So the canonical campaign row declares it, and a row that does not is
    # refused rather than guessed - the same fail-closed rule as everywhere
    # else here.
    declared = campaign.get("provider_delays")
    if not declared:
        raise DiffRefused(
            "the canonical campaign declares no `provider_delays`, and the "
            "provider-side delay is not derivable from the cadence day: a "
            "cadence day is a position in a schedule, an actionDelay is a wait "
            "after the lead enters this campaign")
    delays = tuple((str(unit), int(value)) for unit, value in declared)

    # ONE LEAD, AND THE REASON HAS CHANGED. This refusal used to say a two-lead
    # campaign could not be PROVEN, because the lead identities were unreadable
    # - and that is no longer true: `_provider_leads` enumerates them, `lead_set`
    # is required, and a two-lead campaign would now diff on exactly who is in
    # it. Keeping the refusal on a false reason is the habit this module was
    # written to break.
    #
    # It stays because of what cannot be STOPPED rather than what cannot be
    # proven. `executionguard`'s stoppability gate caps an unstoppable channel at
    # one contact while `providerwrites.is_supported("heyreach.pause")` is False,
    # and a staged campaign larger than that ceiling is a campaign whose leads
    # could not all be recalled. When a pause is established and read back, that
    # gate lifts by itself and this bound should be raised deliberately with it -
    # not silently, and not here first.
    #
    # THE CONDITION IT SET FOR ITSELF HAS BEEN MET, and this is the deliberate
    # raise it asked for. `heyreach.pause` entered `SUPPORTED` on 2026-09-12
    # against campaign 594061: POST /campaign/Pause returned 200, the campaign
    # read back PAUSED, connectionsSent stayed 0, and provider, canonical
    # state, ledger and touches reconciled four ways. A stop demonstrably
    # exists, so a staged campaign is no longer a campaign whose leads could
    # not be recalled.
    #
    # It reads the SAME PREDICATE `executionguard` reads rather than a number
    # copied to sit beside it. A hardcoded 1 here and a lifted gate there is
    # precisely the drift this module was written against - two representations
    # of one truth, and nothing to keep them honest. If the pause is ever
    # withdrawn from `SUPPORTED`, both tighten together and neither has to
    # remember to.
    from . import providerwrites

    if not providerwrites.is_supported("heyreach.pause"):
        if len(leads) != 1:
            raise DiffRefused(
                f"this campaign has {len(leads)} approved LinkedIn leads. "
                f"While no pause route is established the stoppability "
                f"ceiling is one contact per unstoppable channel, so a "
                f"campaign staged beyond it holds people this system could "
                f"not recall")
    elif not leads:
        raise DiffRefused(
            "this campaign has no approved LinkedIn leads, so there is "
            "nobody it may legitimately hold and nothing to compare the "
            "provider's lead set against")

    senders = _ids((campaign.get("senders") or {}).get("linkedin"))
    return {
        "campaign_id": str(cid),
        "campaign_name": campaign.get("name"),
        "status": campaign.get("provider_status_expected") or "PAUSED",
        "org_unit": str(campaign.get("org_unit") or ""),
        "sender_ids": senders,
        "list_id": str(campaign.get("heyreach_list_id") or ""),
        "lead_set": frozenset(leads),
        "lead_count": len(leads),
        # THE GRAPH THE ROW DECLARES, OR THE CANARY'S IF IT DECLARES NONE.
        #
        # This was the literal tuple `("CONNECTION_REQUEST", "END")` and the
        # `actions` list built in the loop above was assembled and thrown
        # away - a value computed correctly that nothing read, which is the
        # defect this repository keeps finding. It did not matter while every
        # campaign was that one shape. Campaign 599020 has six node types, so
        # the hardcoded pair described a graph that does not exist and the
        # diff would have failed on `actions` even once the note was right.
        "actions": tuple(actions) if declared_note is not None
        else ("CONNECTION_REQUEST", "END"),
        "note": notes[0],
        "delays": tuple(delays),
        "linkedin_only": True,
        "bison_handoff": False,
        "daily_limit": (campaign.get("daily_volume") or {}).get("linkedin"),
    }


# How many pages of leads this module will enumerate before it stops claiming
# to know the whole set. A campaign this system approved holds a handful of
# people; one holding thousands is not a campaign it staged, and half a lead set
# is more dangerous than none because it would diff PASS against a subset.
MAX_LEAD_PAGES = 5


def _provider_leads(campaign_id):
    """The lead identities the provider actually holds, and how many.

    THE PREMISE THIS REPLACES WAS FALSE, and it was load-bearing. Rule 3 of the
    module docstring said "HeyReach exposes no route for a campaign's lead
    identities", so `lead_set` came back `UNVERIFIABLE` and the whole staging
    argument rested on `lead_count` plus a verified list id.
    `/campaign/GetLeadsFromCampaign` returns a profile URL and a
    `linkedInUserProfileId` per lead. The identities are readable, and were the
    entire time this module said otherwise.

    `lead_count` now comes from that route's `totalCount` rather than from
    `progressStats.totalUsers`, because `progressStats` is a residual that
    absorbs bucket error - three live campaigns report `totalUsersInProgress`
    as -7, -5 and -6, and on the canary it counts a lead that has done nothing.

    Slugs, to compare against what the approved side states: `approved_heyreach`
    builds its set from `collision.profile_slug`, so the provider side has to
    speak the same identifier. A lead whose profile URL yields no slug leaves
    the set unverifiable rather than silently shrinking it - a subset that
    diffed PASS would be the worst possible answer here.
    """
    from .providers import heyreach

    rows, total = [], None
    for page in range(MAX_LEAD_PAGES):
        found, total = heyreach.campaign_leads(campaign_id,
                                              offset=page * heyreach.MAX_PAGE)
        rows.extend(found)
        if total is None or len(rows) >= int(total or 0) or not found:
            break
    count = int(total) if total is not None else len(rows)
    if count > len(rows):
        return {"lead_set": UNVERIFIABLE, "lead_count": count}
    slugs = set()
    for row in rows:
        slug = collision.profile_slug(row.get("profile_url"))
        if not slug:
            return {"lead_set": UNVERIFIABLE, "lead_count": count}
        slugs.add(slug)
    return {"lead_set": frozenset(slugs), "lead_count": count}


LINKEDIN_STEP = {"key": "day3", "day": 3, "channel": "linkedin",
                 "template": "linkedin_intro"}


# ------------------------------------------------------- PROVIDER, HeyReach

def provider_heyreach(campaign_id):
    """What HeyReach actually holds. Read-only routes only.

    ONE field comes back `UNVERIFIABLE` because no allowlisted route exposes it:
    a per-campaign daily limit, which is not on the campaign object at all. It is
    reported as unverifiable rather than guessed, and `REQUIRED_HEYREACH` omits
    it so a campaign is not failed for a field the vendor does not publish.

    It used to be two. The lead IDENTITIES were the other, on the stated premise
    that only a count was published - and `/campaign/GetLeadsFromCampaign`
    returns a profile URL and a `linkedInUserProfileId` per lead. `_provider_leads`
    reads them, and `lead_count` comes from that route's `totalCount` rather than
    from `progressStats`, which is a residual that goes negative on live
    campaigns.
    """
    # ONE REQUEST, NOT UP TO TEN PAGES OF THE WHOLE ACCOUNT.
    #
    # This called `campaign_by_id`, which finds a campaign by paging
    # `/campaign/GetAll` - up to ten pages, against an account holding 83
    # campaigns - because its docstring says "there is no confirmed GetById
    # route (POST /campaign/GetById answers 405)".
    #
    # That sentence is stale in the way that matters: GetById answers as a
    # GET, `heyreach.campaign_read` has used it that way since it was written,
    # and `campaign_read`'s own docstring calls itself "the one-request form
    # the write verbs read back through". Both were true at once and this
    # function took the slow one.
    #
    # It stopped being merely slow during the first canary. `ensure_leads`
    # obtains a FRESH readback per contact - deliberately, because
    # `authorize` spends it - so three contacts meant three full account
    # pagings, and `/campaign/GetAll` began timing out. Two consecutive write
    # attempts died on a READ, before the transport, having written nothing.
    #
    # Same fields either way: `campaign_read` projects the same
    # `CAMPAIGN_FIELDS`, and `organizationUnitId`, `linkedInUserListId` and
    # `campaignAccountIds` - the three this function reads beyond the
    # obvious - all come back. Verified against 599020 before the switch.
    row = heyreach.campaign_read(campaign_id)
    if not row or row.get("id") is None:
        raise DiffRefused(
            f"heyreach has no campaign {campaign_id}; a missing campaign is "
            f"not an empty one")
    graph = heyreach.campaign_sequence(campaign_id)
    nodes, types, truncated = heyreach.walk_sequence(graph)
    if truncated:
        raise DiffRefused(
            "the sequence graph could not be walked to the end, so the actions "
            "it would run cannot be stated")
    only, _why = heyreach.linkedin_only(graph)
    hazards = [h[0] for h in heyreach.sequence_hazards(
        graph, supplied_fields=heyreach.supplied_field_names())]
    notes = heyreach.connection_notes(graph)
    if len(notes) > 1:
        raise DiffRefused(
            f"the provider sequence carries {len(notes)} connection notes; "
            f"which one a prospect receives is not determinable from the graph")
    stats = row.get("progressStats") or {}

    order, seen = [], set()
    for node in nodes:
        kind = str(node.get("nodeType") or "")
        if kind and kind not in seen:
            seen.add(kind)
            order.append(kind)
    delays = tuple((str(n.get("actionDelayUnit") or ""), int(n.get("actionDelay") or 0))
                   for n in nodes
                   if str(n.get("nodeType") or "").upper() == "CONNECTION_REQUEST")

    return {
        "campaign_id": str(row.get("id")),
        "campaign_name": row.get("name"),
        "status": str(row.get("status") or ""),
        "org_unit": str(row.get("organizationUnitId") or ""),
        "sender_ids": _ids(row.get("campaignAccountIds")),
        "list_id": str(row.get("linkedInUserListId") or ""),
        **_provider_leads(row.get("id")),
        "actions": tuple(order),
        "note": _norm_text(notes[0]) if notes else "",
        "delays": delays,
        "linkedin_only": bool(only),
        "bison_handoff": any("EmailBison" in h or "onward" in h for h in hazards),
        "daily_limit": UNVERIFIABLE,
        "_hazards": hazards,
    }


# ------------------------------------------------------- APPROVED, EmailBison

def _expected_lead_variables(contact_copy, sequence, first_name=""):
    """The custom variables one lead should carry at the provider.

    The sequence is a template of merge fields - `{SUBJECT_1}`, `{BODY_1}` -
    so the resolved copy travels per lead in custom variables. This function
    builds the expected variable mapping for one contact, matching the naming
    `bisonfactory._variables_for` uses at write time.

    For a multi-step sequence: `subject_1`, `body_1`, `subject_2`, etc.
    For a single-step sequence: `subject` and `body`.
    """
    values = {}
    if len(contact_copy) <= 1:
        values["subject"] = (contact_copy[0].get("subject") or "") if contact_copy else ""
        values["body"] = (contact_copy[0].get("body") or "") if contact_copy else ""
    else:
        for position, node in enumerate(contact_copy, start=1):
            values[f"subject_{position}"] = node.get("subject") or ""
            values[f"body_{position}"] = node.get("body") or ""
    return {k: v for k, v in values.items() if v}


def approved_bison(campaign, recs=None, config=None):
    """What canonical state says this email campaign should be.

    TWO KINDS OF COMPARISON, AND THE OLD CODE CONFUSED THEM.

    The SEQUENCE comparison asks: "does the provider's sequence template hold
    the placeholders the config declares?" The sequence at the provider carries
    `{SUBJECT_1}`, `<p>{BODY_1}</p>`, etc. - merge variables, not resolved
    copy. So the approved side must state the EXPECTED PLACEHOLDERS, not the
    per-contact resolved text. TASK-159 established that EmailBison has no
    merge variables of its own; the sequence carries our placeholders and the
    per-lead words travel as CUSTOM VARIABLES on the lead.

    The LEAD COPY comparison asks: "does each lead's custom variables hold the
    resolved copy that was approved for that contact?" This is per-contact and
    per-variable, and it is where the approval fingerprint is actually enforced
    at the provider. A lead whose custom variable differs from its approved
    copy is a lead that would send the wrong words.

    The old code compared resolved per-contact subjects/bodies against the
    provider's sequence placeholders - two different quantities that can never
    agree. It compared cadence DAY positions against provider `wait_in_days` -
    a schedule position against a graph property. Both mismatches were by
    design, not by drift.
    """
    from . import bisonfactory

    if not campaign:
        raise DiffRefused("no canonical campaign row to compare against")
    cid = campaign.get("bison_campaign_id")
    if cid in (None, ""):
        raise DiffRefused(
            "the canonical campaign names no bison_campaign_id, so there is "
            "nothing to compare it to")
    recs = recs if recs is not None else store.load()
    config = config or clients.load(campaign.get("client"))
    wanted = set(campaign.get("record_ids") or ())
    rows = [r for r in recs if r.get("id") in wanted]

    # THE SEQUENCE: what the provider's template should hold.
    #
    # Built from the config's `email_sequence.steps` via the same function
    # `bisonfactory._sequence_steps` uses to write the sequence. The subjects
    # and bodies are the PLACEHOLDERS (`{SUBJECT_1}`, `<p>{BODY_1}</p>`), not
    # the resolved per-contact copy. The delays are the declared
    # `wait_in_days`, not the cadence day positions.
    cadence_steps = cadence.steps_for(campaign, config=config)
    sequence = bisonfactory._sequence_steps(
        (config or {}).get("email_sequence"), cadence_steps)

    seq_subjects, seq_bodies, seq_delays, seq_actions = [], [], [], []
    for node in sequence:
        tr = bool(node.get("thread_reply"))
        subj, body, _ = bisonfactory._comparable_step(
            node.get("email_subject"), node.get("email_body"), tr)
        seq_subjects.append(_norm_text(subj))
        seq_bodies.append(_norm_text(body))
        seq_delays.append(int(node.get("wait_in_days") or 0))
        seq_actions.append(f"step{int(node.get('order') or 0)}")

    # THE LEAD SET AND PER-LEAD COPY.
    leads = set()
    lead_copy = {}
    by_id = {r.get("id"): r for r in rows}
    for rec in rows:
        for contact in rec.get("contacts") or ():
            address = (contact.get("email") or "").strip().lower()
            if not address:
                continue
            approved_here = False
            contact_copy = []
            for spec in cadence_steps:
                if spec.get("channel") != "email":
                    continue
                step = cadence.expand_step(rec, contact, spec, config)
                if not step:
                    continue
                if not approval.is_approved(rec, contact["key"], spec["key"],
                                            step):
                    continue
                approved_here = True
                contact_copy.append({"step_key": spec["key"],
                                     "subject": step.get("subject"),
                                     "body": step.get("body")})
            if approved_here:
                leads.add(address)
                lead_copy[address] = _expected_lead_variables(
                    contact_copy, sequence)
    if not leads:
        raise DiffRefused(
            "no contact on any listed record has an approved email step, so "
            "there is no approved lead set to compare the provider against")

    volume = (campaign.get("daily_volume") or {}).get("email")
    # THE DERIVED NAME, NOT THE ROW'S HUMAN NAME.
    #
    # TASK-170 hit the identical problem for HeyReach and fixed it by calling
    # `bisonfactory.provider_campaign_name`. The provider holds the derived
    # name with the `[client/campaign_id]` suffix; the row holds the human
    # name. Comparing the human name against the derived name is the same
    # class of defect as comparing resolved copy against placeholders.
    from . import bisonfactory as _bf

    # WORKSPACE FROM CONFIG, NOT FROM THE ROW.
    #
    # The row's `workspace` field is empty for campaign 485 because
    # `bisonfactory.stage` reads the workspace from the config and does not
    # write it back. The comparator derives it the same way the factory does.
    workspace = str(((config.get("providers") or {}).get("emailbison")
                     or {}).get("workspace") or "")
    return {
        "campaign_id": str(cid),
        "campaign_name": _bf.provider_campaign_name(campaign),
        "status": campaign.get("provider_status_expected") or "paused",
        "workspace": workspace,
        "sender_ids": _ids((campaign.get("senders") or {}).get("email")),
        "lead_set": frozenset(leads),
        "lead_count": len(leads),
        "actions": tuple(seq_actions),
        "subjects": tuple(seq_subjects),
        "bodies": tuple(seq_bodies),
        "delays": tuple(seq_delays),
        "max_emails_per_day": volume,
        "max_new_leads_per_day": volume,
        "_lead_copy": lead_copy,
    }


# ------------------------------------------------------- PROVIDER, EmailBison

def provider_bison(campaign_id, expect_workspace=None, max_pages=200):
    """What EmailBison actually holds. Read-only GETs only.

    Unlike HeyReach this provider publishes everything the diff needs:
    `/campaigns/{id}` carries status and all three daily limits,
    `/sequence-steps` carries subject, body and `wait_in_days` per step, and
    `/sender-emails` and `/leads` are both paginated and complete. So no field
    here is structurally unverifiable, and `REQUIRED_BISON` is correspondingly
    strict.

    `expect_workspace` is passed to `bison.require_workspace` before any read,
    for the reason `collision.leads_for_domain` documents at length: this
    credential's binding is chosen in the vendor UI and has moved mid-session.
    """
    if expect_workspace is not None:
        bison.require_workspace(expect_workspace)

    def get(path):
        status, data = request("GET", f"{bison.base()}{path}", bison.headers())
        if not ok(status):
            raise DiffRefused(f"emailbison {path} -> {status}")
        if not isinstance(data, dict):
            raise DiffRefused(f"emailbison {path}: unexpected shape")
        return data

    row = get(f"/campaigns/{campaign_id}")
    row = row.get("data") if isinstance(row.get("data"), dict) else row

    def page(path, key):
        out, page_no = [], 1
        while page_no <= max_pages:
            data = get(f"{path}?page={page_no}")
            chunk = data.get("data")
            if not isinstance(chunk, list):
                raise DiffRefused(
                    f"emailbison {path}: no `data` array; refusing to read "
                    f"that as an empty {key}")
            out.extend(chunk)
            meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
            total = meta.get("total")
            if total is not None and len(out) >= int(total):
                return out, int(total)
            if not chunk:
                return out, total
            page_no += 1
        raise DiffRefused(f"emailbison {path}: more than {max_pages} pages")

    senders, _ = page(f"/campaigns/{campaign_id}/sender-emails", "sender set")
    leads, lead_total = page(f"/campaigns/{campaign_id}/leads", "lead set")
    steps = get(f"/campaigns/{campaign_id}/sequence-steps").get("data") or []
    steps = [s for s in steps if isinstance(s, dict)]

    # EMAILBISON HAS A NATIVE VARIANT MODEL AND THIS DID NOT KNOW ABOUT IT.
    #
    # Measured on live Productive campaign 352 on 2026-09-12: 44 sequence-step
    # rows, of which FIVE are the sequence - `variant: false`, `order` 1 to 5 -
    # and thirty-nine are A/B variants of those five, carrying `variant: true`,
    # `variant_from_step` pointing at a base step's id, and `order: null`.
    #
    # `int(s.get("order") or 0)` turns every one of those nulls into 0, so the
    # sort put all thirty-nine variants ahead of the sequence and `actions`
    # came out as thirty-nine indistinguishable `step0`s followed by step1 to
    # step5. That is not a mismatch with the approved side, it is a fiction
    # about the provider - and it is the real reason `compare_bison` can never
    # reach PASS, deeper than the `day1` versus `step1` naming.
    #
    # So the base sequence is what gets compared, because it is what canonical
    # state has a model for. The variants are counted per base step and
    # reported under a `_` key, which `diff` does not score: this system has no
    # canonical representation of a provider-side variant yet, and scoring a
    # field with nothing to compare it to would be inventing a verdict.
    # COPY-EXPERIMENTS.md describes five variants per step as a Resonate
    # concept; the provider implements its own, and reconciling the two is a
    # product decision rather than something to guess here. PRODUCT-GAPS.md
    # carries it.
    base = [s for s in steps if not s.get("variant")]
    variants = [s for s in steps if s.get("variant")]
    base.sort(key=lambda s: int(s.get("order") or 0))
    live = [s for s in base if s.get("active")]
    variants_by_step = collections.Counter(
        str(s.get("variant_from_step")) for s in variants if s.get("active"))

    # PER-LEAD CUSTOM VARIABLES.
    #
    # The campaign leads endpoint does NOT return custom variables - confirmed
    # against the provider. Each lead must be read individually via
    # `GET /leads/{id}`. For a campaign with ten leads this is ten extra GETs;
    # for a campaign with thousands it would be expensive, but the comparator
    # runs against staged campaigns that hold a handful of people.
    #
    # The variables are keyed by email address so `compare_bison` can match
    # them against the approved side's per-lead resolved copy.
    lead_variables = {}
    for lead_row in leads:
        if not isinstance(lead_row, dict):
            continue
        lead_id = lead_row.get("id")
        email = str(lead_row.get("email") or "").strip().lower()
        if not lead_id or not email:
            continue
        try:
            full = get(f"/leads/{lead_id}")
            full = full.get("data") if isinstance(full.get("data"), dict) else full
            vars_map = {v.get("name"): v.get("value")
                        for v in (full.get("custom_variables") or [])
                        if isinstance(v, dict) and v.get("name")}
            lead_variables[email] = vars_map
        except DiffRefused:
            # A lead that cannot be read leaves its variables unverifiable
            # rather than silently shrinking the comparison.
            lead_variables[email] = UNVERIFIABLE

    # The sequence subjects/bodies need the same `_comparable_step`
    # normalisation the approved side applies: strip "Re: " from thread_reply
    # steps so the two sides compare the same quantity.
    from . import bisonfactory as _bf

    prov_subjects, prov_bodies = [], []
    for s in live:
        tr = bool(s.get("thread_reply"))
        subj, body, _ = _bf._comparable_step(
            s.get("email_subject"), s.get("email_body"), tr)
        prov_subjects.append(_norm_text(subj))
        prov_bodies.append(_norm_text(body))

    return {
        "campaign_id": str(row.get("id")),
        "campaign_name": row.get("name"),
        "status": str(row.get("status") or ""),
        "workspace": str((bison.bound_workspace() or {}).get("id") or ""),
        "sender_ids": _ids([s.get("id") for s in senders if isinstance(s, dict)]),
        "lead_set": frozenset(
            str(l.get("email") or "").strip().lower()
            for l in leads if isinstance(l, dict) and l.get("email")),
        "lead_count": int(lead_total if lead_total is not None else len(leads)),
        "actions": tuple(f"step{int(s.get('order') or 0)}" for s in live),
        "subjects": tuple(prov_subjects),
        "bodies": tuple(prov_bodies),
        "delays": tuple(int(s.get("wait_in_days") or 0) for s in live),
        "max_emails_per_day": row.get("max_emails_per_day"),
        "max_new_leads_per_day": row.get("max_new_leads_per_day"),
        "_per_domain_cap": row.get("daily_max_sends_per_receiving_domain"),
        "_bounced": row.get("bounced"),
        "_emails_sent": row.get("emails_sent"),
        "_variants_per_step": {str(s.get("id")): variants_by_step.get(
            str(s.get("id")), 0) for s in live},
        "_variant_rows": len(variants),
        "_lead_variables": lead_variables,
    }


# ---------------------------------------------------------------- the diff

# Fields a STAGING comparison compares directionally rather than by equality.
#
# WHY EQUALITY CANNOT BE THE RULE FOR A LEAD SET THAT IS ABOUT TO CHANGE.
#
# `executionguard.authorize` will not mint an authorization unless this diff
# says PASS, and `heyreachfactory.ensure_leads` asks for that authorization in
# order to ADD A LEAD. Comparing the lead set by equality therefore demanded
# that the provider ALREADY HOLD the people we were asking permission to put
# there. The gate could not admit a first lead into any campaign, ever, and
# the reason nobody had noticed is that no lead had ever been added.
#
# The safety property that actually matters is not "the provider holds exactly
# who we approved". It is "the provider holds NOBODY WE DID NOT APPROVE", and
# that one survives the write: a campaign whose leads are a subset of the
# approved set contains no stranger, whether it is empty, half-filled or
# complete. A lead nobody approved still fails, because it is not in the
# approved set and containment refuses it.
#
# Equality stays the rule for every other field and for these two whenever the
# caller does not ask, so this cannot loosen a comparison by accident.
SUBSET_FIELDS = ("lead_set", "lead_count")


def _within(want, got):
    """`got` is contained by `want`, for the two shapes a lead set takes."""
    if isinstance(want, (frozenset, set)) and isinstance(got, (frozenset, set)):
        return got <= want
    if isinstance(want, bool) or isinstance(got, bool):
        return want == got
    if isinstance(want, int) and isinstance(got, int):
        return got <= want
    return want == got


def diff(approved, provider, required=(), subset_fields=()):
    """Per-field verdicts over the UNION of both sides' keys, and PASS/FAIL.

    The union rather than `approved`'s keys, because the dangerous field is the
    one nobody approved: a second sender, an extra sequence node, a lead that
    should not be there. Those are `UNEXPECTED` and they fail.

    `subset_fields` are compared as containment rather than equality - read
    `SUBSET_FIELDS` for the one operation that needs it and why equality made
    the gate unsatisfiable for it. Nothing is compared that way unless the
    caller names it.

    Keys starting `_` are context for a human reading the report - hazards,
    counters - and are never part of the verdict.
    """
    if not isinstance(approved, dict) or not isinstance(provider, dict):
        raise DiffRefused("both sides must be normalised configuration dicts")
    fields, failures = {}, []
    for key in sorted(set(approved) | set(provider)):
        if key.startswith("_"):
            continue
        want, got = approved.get(key, MISSING), provider.get(key, MISSING)
        if got is UNVERIFIABLE or got == UNVERIFIABLE:
            verdict = UNVERIFIABLE
        elif key not in approved:
            verdict = UNEXPECTED
        elif key not in provider:
            verdict = MISSING
        elif want == got:
            verdict = MATCH
        elif key in subset_fields and _within(want, got):
            verdict = MATCH
        else:
            verdict = MISMATCH
        fields[key] = {"verdict": verdict, "approved": _show(want),
                       "provider": _show(got)}
        if verdict in FAILING and key in required:
            failures.append(f"{key}: {verdict}")
        elif verdict == UNEXPECTED:
            # Unexpected always fails, required or not. Nobody approved it.
            failures.append(f"{key}: {verdict}")
    return {"verdict": FAIL if failures else PASS, "failures": failures,
            "fields": fields,
            "checked": len([k for k in fields]),
            "required": list(required)}


def _show(value):
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    return value


class Readback:
    """A provider comparison, bound to what it compared and usable once.

    THE HOLE THIS CLOSES. `executionguard` used to take `readback` as a plain
    dict and inspect three things: the verdict, the failures and a
    `verified_at` the CALLER stamped. Nothing tied it to a campaign, a channel
    or a provider id, and nothing marked it used. So a diff computed for
    campaign A satisfied the gate for campaign B, and one dict authorised any
    number of actions - which is precisely the defect `Authorization` exists to
    prevent, reproduced one level up. A dict claiming a provider was verified is
    not proof that it was.

    So the timestamp is stamped HERE, immediately after the last provider read,
    rather than by whoever happens to call this; the identity of what was
    compared travels with the verdict; and `spend()` makes it single-use.
    """

    __slots__ = ("diff", "approved", "provider", "campaign_id", "channel",
                 "provider_campaign_id", "verified_at", "_spent")

    def __init__(self, **fields):
        for name in self.__slots__:
            if name != "_spent":
                setattr(self, name, fields.get(name))
        self._spent = False

    @property
    def verdict(self):
        return (self.diff or {}).get("verdict")

    @property
    def failures(self):
        return (self.diff or {}).get("failures") or []

    def spend(self):
        if self._spent:
            raise DiffRefused(
                f"this read-back for {self.campaign_id} has already authorised "
                f"an action; re-read the provider rather than reusing one")
        self._spent = True
        return self

    def __repr__(self):
        return f"<Readback {self.campaign_id} {self.channel} {self.verdict}>"


def compare_heyreach(campaign, recs=None, config=None, staging=False):
    """`(diff, approved, provider)` for one LinkedIn campaign.

    `staging=True` says this comparison is about to authorise a write that ADDS
    people to the campaign, so the lead set is compared as containment rather
    than equality. `SUBSET_FIELDS` carries the reasoning; the short version is
    that equality asked the provider to already hold the people we were asking
    permission to add.
    """
    approved = approved_heyreach(campaign, recs, config)
    provider = provider_heyreach(approved["campaign_id"])
    found = diff(approved, provider, REQUIRED_HEYREACH,
                 subset_fields=SUBSET_FIELDS if staging else ())
    # Stamped here, after the last provider read, so freshness means what it says.
    return Readback(diff=found, approved=approved, provider=provider,
                    campaign_id=campaign.get("campaign_id"), channel="linkedin",
                    provider_campaign_id=approved["campaign_id"],
                    verified_at=store.now())


def compare_bison(campaign, recs=None, config=None, expect_workspace=None):
    """`(diff, approved, provider)` for one email campaign.

    TWO COMPARISONS, ONE READBACK.

    The SEQUENCE diff asks whether the provider's template holds the expected
    placeholders, declared waits, and step names. This is the `diff()` call.

    The LEAD COPY diff asks whether each lead's custom variables at the
    provider hold the resolved copy that was approved for that contact. This
    is a per-contact comparison that runs after the sequence diff and adds its
    own failures to the result. A lead whose custom variable differs from its
    approved copy FAILS loudly, naming the contact by hashed email.
    """
    approved = approved_bison(campaign, recs, config)
    provider = provider_bison(approved["campaign_id"],
                              expect_workspace=expect_workspace)
    found = diff(approved, provider, REQUIRED_BISON)

    # PER-LEAD COPY COMPARISON.
    #
    # The approved side's `_lead_copy` maps email -> expected custom variables.
    # The provider side's `_lead_variables` maps email -> actual custom
    # variables. For each approved lead, check that the provider's variables
    # match. A mismatch names the contact by hashed email.
    #
    # This is where the approval fingerprint is actually enforced at the
    # provider. The sequence comparison proves the template is right; this
    # proves the words each prospect receives are right.
    approved_copy = approved.get("_lead_copy") or {}
    provider_vars = provider.get("_lead_variables") or {}
    copy_failures = []
    for email, expected in sorted(approved_copy.items()):
        actual = provider_vars.get(email)
        if actual is UNVERIFIABLE:
            copy_failures.append(
                f"lead_copy:{_hash_email(email)}: UNVERIFIABLE")
            continue
        if actual is None:
            copy_failures.append(
                f"lead_copy:{_hash_email(email)}: MISSING at provider")
            continue
        # Compare variable by variable.
        all_keys = sorted(set(expected) | set(actual))
        for key in all_keys:
            want = expected.get(key, "")
            got = actual.get(key, "")
            if want != got:
                copy_failures.append(
                    f"lead_copy:{_hash_email(email)}.{key}: "
                    f"approved {_show(want)[:60]!r} vs "
                    f"provider {_show(got)[:60]!r}")
    if copy_failures:
        found["failures"].extend(copy_failures)
        found["verdict"] = FAIL
        # Add a synthetic field to the diff for reporting.
        found["fields"]["lead_copy"] = {
            "verdict": MISMATCH,
            "approved": f"{len(approved_copy)} lead(s)",
            "provider": f"{len(provider_vars)} lead(s)",
            "detail": copy_failures,
        }

    return Readback(diff=found, approved=approved, provider=provider,
                    campaign_id=campaign.get("campaign_id"), channel="email",
                    provider_campaign_id=approved["campaign_id"],
                    verified_at=store.now())


def _hash_email(email):
    """A hashed email for reporting, so the diff does not log PII."""
    import hashlib
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]


def report(result, approved=None, provider=None):
    lines = [f"{result['verdict']}  ({result['checked']} fields checked)"]
    for key, row in result["fields"].items():
        mark = "ok  " if row["verdict"] == MATCH else "FAIL"
        lines.append(f"  {mark} {key:20} {row['verdict']}")
        if row["verdict"] != MATCH:
            lines.append(f"       approved: {json.dumps(row['approved'])[:150]}")
            lines.append(f"       provider: {json.dumps(row['provider'])[:150]}")
    if result["failures"]:
        lines.append("  failing: " + "; ".join(result["failures"]))
    return "\n".join(lines)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="python -m src.configdiff",
                                description=__doc__)
    p.add_argument("--campaign", required=True,
                   help="canonical campaign_id, as `campaigns.get` addresses it")
    p.add_argument("--channel", choices=("linkedin", "email"), required=True)
    p.add_argument("--workspace", type=int,
                   help="required for email: the EmailBison workspace to pin")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    campaign = campaigns_state.get(a.campaign)
    if not campaign:
        print(f"no canonical campaign {a.campaign!r}")
        return 2
    try:
        # A SEALED `Readback`, NOT A THREE-TUPLE. This unpacked one until now and
        # raised `TypeError: cannot unpack non-iterable Readback object` every
        # time it ran - on the command an operator uses to verify a provider
        # configuration before a canary. `executionguard.main` was fixed for
        # exactly this and carries the note; this CLI was missed because nothing
        # covered it, so `test_configdiff_cli` now does.
        readback = (compare_heyreach(campaign) if a.channel == "linkedin"
                    else compare_bison(campaign,
                                       expect_workspace=a.workspace))
    except DiffRefused as e:
        print(f"REFUSED: {e}")
        return 2
    result = readback.diff
    print(json.dumps(result, indent=1, default=_show) if a.json
          else report(result, readback.approved, readback.provider))
    return 0 if result["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
