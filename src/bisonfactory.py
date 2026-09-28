#!/usr/bin/env python3
"""Build a real EmailBison campaign from canonical state, and prove it.

The campaign row in `work/campaigns.jsonl` is the specification. There is no
second one: `campaigns.material()` already assembles every field an approval
decision covers, `campaigns.fingerprint()` already digests it, and
`providerwrites.staged_already()` already remembers what reached the provider.
This module orchestrates those; it invents no new state.

WHAT MAKES IT IDEMPOTENT. `bison_campaign_id` on the campaign row is the
anchor. It is written the instant the provider answers, inside the same
transaction that reads it. A crash between the POST and the persist leaves a
real campaign that no local state names, and this paragraph used to say that
case "is reported as ambiguous rather than retried" - it was not. Nothing
looked, and the next run built a second campaign: measured on 2026-09-13, two
campaigns with byte-identical names. The name is now DERIVED from the campaign
row (`provider_campaign_name`) and looked up before anything is created, so an
orphan is recovered and bound; two orphans are the ambiguity that paragraph
claimed, and they are refused.

THE OTHER THING THAT MAKES IT IDEMPOTENT IS THE ORDER. The campaign is
stopped BEFORE its leads are attached, because a lead in a campaign that has
not been stopped reads `in_sequence` and a lead that is `in_sequence`
anywhere cannot be attached anywhere else. See `stage`.

WHAT IT WILL NOT DO. It never resumes a campaign. Activation is what makes a
staged sequence start emailing real people, `bison.activate` is not in
`providerwrites.SUPPORTED`, and a factory that could start sending would make
every gate above it advisory. The campaign it leaves behind is populated,
sequenced and stopped.
"""
import argparse
import sys

from . import (campaigns, clients, copylint, packfacts, providerwrites,
               sequencegate, sequenceplan, store)
from .providers import ProviderError, bison
# THE CONSTANT, NOT THE TRANSPORT. Tests swap `bison` for a fake provider,
# and this number is not something a provider answers - it is how many pairs
# of copy variables this engine declares. Reading it off the swapped module
# made a fake without the attribute crash a check that has nothing to do
# with the wire.
from .providers.bison import MAX_SEQUENCE_STEPS


class FactoryRefused(Exception):
    """The campaign must not be staged, and the reason is not the provider's.

    IT CARRIES THE REPORT THE REFUSAL WAS TAKEN FROM, when there is one.

    A gate's verdict is structured - `copylint` reports `offenders` keyed by
    rule, `sequencegate` reports a result per lead - and the message is a
    rendering of it. Until a dry run ran the gates, that structure was reachable
    only on the RETURN value, so "the dry run reports the verdict" and "the dry
    run refuses" were incompatible ways to ask the same question, and two proofs
    depended on the first: `tests/test_a_client_csv_fact_cannot_license_a_claim`
    asserts WHICH rule fired and which did not, which no string can answer
    without being a source-text assertion.

    So the refusal carries it. `raise FactoryRefused(text)` is unchanged for
    every site that has nothing to attach, and `.report` is None there rather
    than absent, because a caller reading it must not have to ask whether the
    attribute exists.
    """

    def __init__(self, *args, report=None):
        super().__init__(*args)
        self.report = report


class FactoryAmbiguous(Exception):
    """The provider may have acted. Read provider truth; do NOT retry."""


def stage(campaign_id, *, recs=None, config=None, live=False, by="system"):
    """Bring one campaign into existence at EmailBison, or confirm it is there.

    Returns a report: what was already true, what was done, and what the
    provider said afterwards. Dry run by default - `live=True` is explicit,
    because everything below this line writes to a real estate.

    WHAT A DRY RUN IS. "Execute the real decision and safety path without
    provider writes" (operator, 2026-09-27, `docs/OPERATING-MODE.md`). It is
    NOT "skip the safety path because `live` is false". Every gate above the
    tenancy check therefore runs in both modes and refuses in both modes, with
    the same message for the same reason; `live` decides only whether anything
    is WRITTEN, which is why it is read for the first time below those gates.
    A refusal carries the report it was taken from - see `FactoryRefused`.
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

    plan = _plan(campaign, recs, config)
    report = {"campaign": str(campaign_id), "client": client, "live": bool(live),
              "workspace": None, "plan": plan, "did": [], "provider": {}}
    # THE BATCH COPY LINT, BEFORE THE FIRST PROVIDER CALL OF ANY KIND.
    #
    # It is here and not inside `_ensure_leads` for the reason ISSUE-037 is
    # open: the blank-render gate refuses AFTER the attach and its refusal
    # does not roll back, so a campaign can be left holding leads a gate has
    # already condemned. This one runs before the workspace is even read, so
    # nothing it refuses can have reached the estate.
    #
    # AND IT RUNS ON A DRY RUN, AS THE SAME CALL WITH THE SAME VERDICT.
    #
    # The dry-run return sat ABOVE this line, so `live=False` skipped the
    # refusal. The lint itself did run there - a second call to
    # `_copylint_report`, whose verdict went on the report and stopped nothing -
    # so a dry run could report `refused: true` and still be read as a pass by
    # anything that looked only at whether it raised. A dry run means "execute
    # the real decision and safety path without provider writes" (operator,
    # 2026-09-27); it never means withhold the decision because `live` is false.
    _refuse_copylint(plan, recs, report)

    # SEQUENCE-LEVEL GATE, AFTER COPYLINT BUT BEFORE ANY PROVIDER CALL.
    #
    # `copylint` asks whether each message is acceptable. `sequencegate` asks
    # whether the WHOLE sequence is acceptable: no repetition across steps,
    # no hypothesis stated as a finding, no question asked twice across
    # channels. A campaign can be built entirely from acceptable messages
    # and still be bad, and nothing above this line could say so.
    #
    # The refusal names the STEP that caused each failure, so the operator
    # knows which message to regenerate. Regenerating everything hides which
    # message was wrong and burns the budget hiding it.
    #
    # AND IT RUNS ON A DRY RUN, WHICH IT DID NOT UNTIL NOW. The dry-run return
    # sat ABOVE this line, so a zero-write run never ran the sequence gate at
    # all and `report` carried no `sequencegate` key to say so - a check that
    # did not run looking exactly like a check that passed, which is the
    # failure mode this repository keeps paying for. It also made `TASK-425`
    # acceptance criterion 3 unsatisfiable, because that asks for sequencing
    # "enforced by `sequencegate`, with a negative test" from a run performing
    # zero provider writes, and the gate only ran when writes were allowed.
    #
    # NOTHING WAS RELAXED TO MOVE IT AND NO PROVIDER IS CONSULTED BY IT. The
    # gate is the same call with the same five inputs; `sequencegate` imports
    # only `re` and `copylint`, and every input it is handed comes off the
    # plan, which is built identically in both modes - so a dry run refuses a
    # bad sequence for the same reason, and with the same message, as a live
    # one, and the transport is still never reached. Proof:
    # `tests/test_a_dry_run_runs_the_sequence_gate.py`, which drives
    # `stage(live=False)` with `providers.set_transport` booby-trapped to raise
    # on any call.
    _refuse_sequence_gate(plan, recs, report)

    if not live:
        report["did"].append("dry run: nothing was sent")
        # BOTH GATES HAVE NOW PASSED, so a dry run returns only what a live run
        # would have gone on to write. `_refuse_copylint` declines to lint a
        # plan it can see is incomplete (see its docstring), and that is the one
        # case where it sets no verdict - so the dry run fills it in, because
        # "what is missing" is the question a dry run exists to answer and the
        # lint's `empty_step` view is part of the answer. It is the same call
        # the refusal above would have made.
        if "copylint" not in report:
            report["copylint"] = _copylint_report(plan, recs)
        return report

    # TENANCY, AGAINST THE PROVIDER, BEFORE ANYTHING IS WRITTEN.
    #
    # `workspace_id` is accepted and discarded by every list route on this
    # API, and the answer for a workspace that does not exist is identical to
    # the answer for the one that does - so a caller can believe it scoped a
    # read and be holding another client's estate. `GET /users` is the only
    # route that states which workspace the credential is actually bound to.
    workspace = bison.bound_workspace()
    report["workspace"] = workspace
    expected = ((config.get("providers") or {}).get("emailbison") or {}).get(
        "workspace")
    if expected is not None and str(workspace.get("id")) != str(expected):
        raise FactoryRefused(
            f"this credential is bound to EmailBison workspace "
            f"{workspace.get('id')} ({workspace.get('name')!r}) and {client!r} "
            f"is configured for workspace {expected}. Refusing to build one "
            f"client's campaign inside another client's estate")

    provider_id, provider_name = _find_or_create(campaign, report, by=by)
    report["provider"]["campaign_id"] = provider_id
    report["provider"]["name"] = provider_name

    _ensure_limits(provider_id, campaign, provider_name, report)
    _ensure_schedule(provider_id, plan, report)
    _ensure_senders(provider_id, campaign, report)
    _ensure_sequence(provider_id, campaign, plan, report, by=by)
    # STOPPED BEFORE IT HOLDS ANYBODY, for the reason `_ensure_limits` is
    # applied before the leads and for one more that is not about this
    # campaign at all. A lead attached to a campaign that has not been stopped
    # reads `in_sequence` AT ONCE - draft is enough - and a lead that is
    # `in_sequence` anywhere cannot be attached to any other campaign; the
    # provider refuses the whole batch with one unattributed 422. So the old
    # order left every lead of this campaign unattachable elsewhere for the
    # length of a staging run, and two campaigns staged at the same time
    # raced: measured 2026-09-13, the second one failed outright.
    _ensure_stopped(provider_id, report, by=by)
    _ensure_leads(provider_id, campaign, plan, report, by=by)

    report["provider"]["readback"] = _readback(provider_id)
    return report


def provider_campaign_name(campaign):
    """The name this campaign row has at EmailBison. Derived, never chosen.

    THE ONLY HANDLE ON A CAMPAIGN NOBODY WROTE DOWN. `bison_campaign_id` is
    the anchor and it is written the instant the provider answers - but if the
    process dies in between, the provider holds a campaign that no local state
    names and the next run builds another. Measured 2026-09-13: two campaigns,
    byte-identical names, one of them orphaned.

    So the name carries the canonical identity, and `_find_or_create` looks it
    up before it creates anything. `client` is in it because `campaign_id` is
    unique per client and this workspace holds more than one tenant's work,
    and the operator's own name stays at the front because this string is what
    a person sees in EmailBison's UI.

    WHAT IS DELIBERATELY NOT IN IT: `campaigns.fingerprint`. That digest moves
    whenever a draft, a sender, a volume or a client setting changes, which is
    exactly right for "is this still what was approved" and exactly wrong for
    "which provider campaign is this". A name carrying it would stop matching
    the moment copy was regenerated, and the next re-stage would build a
    second campaign for the same row - the defect this function exists to
    close, reintroduced. Identity is stable; material is not; they are
    different questions and the fingerprint answers the other one.
    """
    human = str(campaign.get("name") or "").strip() or "resonate"
    return f"{human} [{campaign.get('client')}/{campaign.get('campaign_id')}]"


# WHAT `wait_in_days` MEANS, MEASURED RATHER THAN ASSUMED.
#
# It is the wait AFTER the step that carries it, before the next one - not a
# wait before it. Read off the client's own live campaign 352 on 2026-09-13:
# 381 consecutive scheduled-email pairs whose two steps declare DIFFERENT
# waits, which are the only pairs that can tell the two readings apart.
#
#     earlier wait 3, later wait 1  ->  delta 3 in 59 of 87 pairs
#     earlier wait 3, later wait 4  ->  delta 3 in 115 of 168
#     earlier wait 4, later wait 3  ->  delta 4 in 77 of 126
#
# The mode is the EARLIER step's wait in all three groups. The one-to-two day
# spread around it is the sending window and the weekend, which is why the
# mode is the evidence and an exact match is not: pairs whose two steps
# declare the SAME wait cannot discriminate at all and are excluded.
#
# So a five-step cadence declares four meaningful waits and one that has no
# successor to be a wait before. The declaration and the check against the
# cadence now live in `sequenceplan._email_steps`, which is where the plan is
# built; `_sequence_steps` below projects what it built.


def _sequence_steps(configured, cadence_steps):
    """The provider sequence this campaign writes: a PROJECTION of the plan.

    THIS FUNCTION BUILDS NOTHING ANY MORE, and that is the change TASK-364
    makes. It used to assemble the provider steps itself out of the client's
    `email_sequence` block and the cadence - which meant EmailBison's payload,
    HeyReach's graph, the preview and the XLSX were four assemblies of the same
    two inputs, free to disagree the day one of them was edited.

    Now the plan is built FIRST from strategy and copy - one canonical
    SequencePlan, `sequenceplan.for_campaign` - and this asks it for the
    EmailBison projection. Every property this function used to be responsible
    for lives in that module: the two declared shapes, the keys checked against
    the cadence, the delays verified rather than derived, and the invariant
    that only the opener owns a subject. `sequenceplan` raises `PlanRefused`,
    which is the same refusal with a different name, so it is re-raised here as
    `FactoryRefused` - a caller of this module gets one refusal type, and the
    message is unchanged.

    `MAX_SEQUENCE_STEPS` is passed rather than read inside the plan because it
    is a fact about EMAILBISON - how many pairs of copy variables that
    workspace declares - and not about the campaign. A cadence longer than the
    provider can carry is a projection problem, and the plan is the same plan
    whichever provider asks it for a payload.

    The signature is unchanged because `configdiff` and the preview renderer
    both go through here, and both are now reading the plan through it.
    """
    plan = sequenceplan.for_campaign(
        None, {"email_sequence": configured or {}},
        cadence_steps=cadence_steps)
    return _derive_bison_sequence(plan)


def _derive_bison_sequence(plan):
    """The plan's EmailBison projection, with a plan refusal named as ours."""
    try:
        return sequenceplan.derive_bison_sequence(
            plan, max_steps=MAX_SEQUENCE_STEPS)
    except sequenceplan.PlanRefused as refusal:
        raise FactoryRefused(str(refusal)) from refusal


def _require_declared_cadence(campaign):
    """A campaign must declare its OWN cadence, or it is not staged.

    WHAT THIS REPLACED, AND WHY THE OLD PROTECTION WAS AN ACCIDENT. Until
    2026-09-25 a campaign carrying no `cadence_steps` was caught - when it was
    caught at all - by `_sequence_steps`, because the client's
    `email_sequence.steps` keys happened to DIFFER from whatever
    `cadence.steps_for` fell back to. That is protection by coincidence
    between two unrelated files. The moment the operator aligned Productive's
    email days to the client's own `productive_li_heavy_v1` ladder - so that
    email and LinkedIn run the same clock for the same prospect, which is
    correct and was asked for - the two agreed, the refusal stopped firing,
    and nothing was left.

    Measured at that moment: 16 of 28 campaign rows carry no `cadence_steps`,
    and three of those are real EMAIL campaigns. One is LIVE and ACTIVE at the
    provider with its sequence already written. `bison.set_sequence` APPENDS -
    no replace, no per-step delete - so staging it would have left it holding
    its existing sequence plus five more steps and sending duplicates to a
    live cohort. One staging call away.

    SO THE REFUSAL IS ABOUT THE CAMPAIGN, NOT ABOUT TWO FILES DISAGREEING.
    "This campaign never declared its own cadence" is the thing actually worth
    refusing, it is true independently of what any other file says, and it
    cannot be dissolved by making two unrelated declarations agree.

    CAMPAIGN-LEVEL AND CLIENT-AGNOSTIC, deliberately. A client-scoped check
    does not reach this case: `cadence.steps_for` falls back through
    `_named_sequence` and `_library_sequence`, which ARE client declarations,
    so "the client declared something" is satisfied while the campaign
    declared nothing. The dangerous campaign passes a client-scoped check.

    NOTHING IS WRITTEN TO MAKE A ROW PASS. Filling `cadence_steps` in for the
    sixteen would hand them a cadence nobody chose, which is the same defect
    one level down. They are refused until somebody decides what they run.
    """
    # Deferred like every other `cadence` use in this module: the two import
    # each other, so a module-level import is a cycle at load time.
    from . import cadence as _cadence

    if (campaign or {}).get(_cadence.CADENCE_KEY):
        return
    raise FactoryRefused(
        f"campaign {campaign.get('campaign_id')!r} declares no "
        f"`{_cadence.CADENCE_KEY}` of its own, so the sequence it would send "
        f"comes from whatever the client's config falls back to rather than "
        f"from anything this campaign chose. Refusing: the provider's "
        f"`set_sequence` APPENDS, so a campaign staged against a guessed "
        f"cadence cannot be corrected afterwards. Declare the steps on the "
        f"campaign row")


def _plan(campaign, recs, config):
    """What this campaign is, from canonical state. No provider call."""
    # BEFORE ANY CADENCE IS RESOLVED, because resolving it is the thing that
    # silently substitutes one. A dry run refuses here too: a dry run that
    # reports a plan and a live run that refuses is the mismatch this exists
    # to stop.
    _require_declared_cadence(campaign)
    # Deferred for the reason `cadence` below is: `qualify` reaches `dmplan`,
    # which reaches `enrich`, and this module is imported by `configdiff`.
    from . import qualify as _qualify
    material = campaigns.material(campaign, recs=recs, config=config)
    # WHICH contacts comes from the approval material, because that is what
    # was blessed. Their NAMES come from the record: `_contact_material`
    # deliberately carries only what launching cares about - who, where, may
    # we send - and a name is none of those. Reading names out of it silently
    # produced empty ones, which the provider then rejected.
    by_id = {r.get("id"): r for r in recs}
    # THE PLAN IS BUILT BEFORE THE LEADS, AND THE LEADS ARE BUILT FROM IT.
    #
    # Two reasons, and the second one is TASK-364's. The sequence decides how
    # many approved steps each lead has to carry - a lead is words plus an
    # address, and which words depends on how many the sequence will ask for.
    # And the plan is the SOURCE rather than a summary: it is built from
    # strategy (this campaign's declared cadence) and copy (the client's
    # templates), and every payload below is a projection of it.
    #
    # THE DIRECTION IS THE WHOLE POINT. An earlier attempt built the provider
    # sequence here and then generated a "canonical plan" from the leads it
    # produced, which makes plan and payload incapable of disagreeing and a
    # consistency test between them worthless. Nothing below this line builds
    # a sequence.
    from . import cadence as _cadence
    cadence_steps = _cadence.steps_for(campaign, config=config)
    sequence_plan = sequenceplan.for_campaign(campaign, config,
                                              cadence_steps=cadence_steps)
    sequence = _derive_bison_sequence(sequence_plan)
    leads = []
    for record in material.get("records") or []:
        if record.get("missing") or record.get("dropped") or record.get("paused"):
            continue
        source = by_id.get(record.get("id")) or {}
        # THIS COMPANY'S OWN ICP VERDICT, FROM THE CANONICAL RESOLVER, carried
        # on the plan because `_refuse_sequence_gate` has to hand it to
        # `sequencegate.check` and the gate refuses an absent one by design.
        #
        # `qualify.state_of` rather than a reach into
        # `qualification.verdict.icp_status`: `enrich` already calls it the
        # canonical resolver, it folds in a human's explicit
        # rejection, and - the part that matters here - it has a WORD for a
        # record nobody ever qualified (`not_processed`) instead of a None
        # that a caller could read as "fine". A record this system never
        # qualified is not a qualified record.
        #
        # Measured on the production queue, 2026-09-27: of the records that
        # carry both generated copy and research - the only ones that can get
        # past `_refuse_copylint` and reach the sequence gate at all - 53 are
        # `qualified` and 2 are `rejected`, and NONE lacks a verdict. So this
        # refuses nothing that is legitimately stageable today, and it refuses
        # the two that a campaign should never have held.
        qualification = _qualify.state_of(source)
        names = {c.get("key"): c for c in (source.get("contacts") or [])}
        for contact in record.get("contacts") or []:
            if not contact.get("email") or not contact.get("sendable"):
                continue
            person = names.get(contact.get("key")) or {}
            # `name` is what this estate actually stores - the split fields
            # are empty on every Productive contact - so the first token is
            # taken from it, which is the convention `push.build_rows` has
            # used since it was written. Following it rather than inventing a
            # second one: two places splitting names differently is how the
            # same person gets greeted two ways.
            #
            # Deriving a given name from a full name is not reliable for
            # every name in the world. It is reading what is on the record
            # rather than inventing anything, which is the line that matters,
            # and a contact with no name at all is still refused below.
            first = (person.get("first_name") or "").strip()
            if not first:
                first = ((person.get("name") or "").split() or [""])[0].strip()
            if not first:
                raise FactoryRefused(
                    f"contact {contact.get('key')!r} on record "
                    f"{record.get('id')!r} has no name at all, and EmailBison "
                    f"requires a first name. Refusing to invent one that will "
                    f"greet a real person")
            # THE WORDS, CARRIED WITH THE PERSON.
            #
            # The sequence written to the provider is a template of merge
            # fields - `{SUBJECT}` and `{BODY}` - so the copy itself travels
            # per lead in custom variables. Without this the template renders
            # against nothing: the campaign would be staged, the readback
            # would look right, and the email would go out empty.
            #
            # Only an APPROVED step's words are carried. An unapproved draft
            # is not copy anybody has blessed, and the approval fingerprint
            # is what `executionguard` checks a payload against, so shipping
            # words that carry no approval would put the gate and the wire
            # out of step.
            copy, missing = _approved_copy(source, contact.get("key"),
                                           sequence, record.get("id"),
                                           cadence_steps=cadence_steps,
                                           campaign=campaign,
                                           config=config)
            leads.append({"record_id": record.get("id"),
                          "contact_key": contact.get("key"),
                          "email": contact.get("email"),
                          "first_name": first,
                          "qualification": qualification,
                          # THE CAPABILITY THIS LEAD'S OWN COPY NAMES, from
                          # the client's file by way of the contact's persona.
                          # `product_words` is the one place that path is
                          # spelled out and it is what resolves `{capability}`
                          # in the rung-3 template, so the sequence gate is
                          # asked about the same sentence the prospect reads.
                          # A persona the client has no capability for
                          # resolves to None, which the gate's check 4 skips
                          # rather than guessing at.
                          "capability": _cadence.product_words(
                              person, config).get("capability"),
                          # THE PERSONA, CARRIED FOR THE SAME REASON AS THE
                          # CAPABILITY DIRECTLY ABOVE. `_refuse_sequence_gate`
                          # has to ask which offer this contact is being sold
                          # before it can check the sequence against that
                          # offer's step objectives, and selection is a
                          # property of the persona. It is read off the record
                          # rather than defaulted: a contact with no persona
                          # selects no offer and the gate reports the ladder as
                          # unchecked, which is true, where a default would
                          # check the sequence against a spine nobody chose.
                          "persona": person.get("persona"),
                          "copy": copy,
                          "missing_copy": missing,
                          "unsupported_copy": _unsupported_copy(
                              source, person, copy),
                          "step_key": copy[0]["step_key"] if copy else None,
                          "subject": copy[0]["subject"] if copy else "",
                          "body": copy[0]["body"] if copy else "",
                          "last_name": (
                              (person.get("last_name") or "").strip()
                              or " ".join(
                                  (person.get("name") or "").split()[1:]))})
    return {"fingerprint": campaigns.fingerprint(campaign, recs=recs,
                                                 config=config),
            "name": provider_campaign_name(campaign),
            "leads": leads,
            # THE CAMPAIGN'S OWN WINDOW WINS. EmailBison schedules ONE window
            # per campaign, so the window is a property of the cohort rather
            # than of the client: a Toronto prospect in a campaign on the
            # client's Europe/Zagreb hours would be written to at 03:00 local.
            #
            # Which is why geography belongs in campaign grouping wherever
            # provider scheduling is campaign-level - mixing timezones into
            # one campaign guarantees somebody is mailed in the middle of
            # their night. The client setting stays as the default for a
            # cohort that does not state one.
            "window": (campaign.get("sending_window")
                       or (config or {}).get("sending_window") or {}),
            # THE CANONICAL PLAN, AND ITS EMAILBISON PROJECTION. The key
            # `sequence` is RETIRED rather than renamed: while a key of that
            # name exists on this dict, a write path can read a sequence that
            # nothing derived from the plan, which is the defect TASK-364 is
            # about. `provider_sequence` is what the write paths read and it
            # comes from one place only, `_derive_bison_sequence` above.
            "sequence_plan": sequence_plan,
            "provider_sequence": sequence,
            "sequence_config": (config or {}).get("email_sequence") or {},
            "bison_campaign_id": campaign.get("bison_campaign_id")}


def _copylint_batch(plan, recs):
    """The plan's leads and their packs, in the shape `copylint` reads.

    The ONLY translation here is of shape. Which rules exist, what they
    check and what a refusal says are the lint's business, so a rule added to
    `copylint.RULES` next week is enforced on this path without a line
    changing here - that is what the wiring means, and enumerating rules is
    how a wiring silently stops enforcing the new ones.

    A step's SUBJECT is deliberately not folded into its body. `copylint`
    takes the first line of step 1 as the opener, and a cohort shares its
    subject template, so a subject prepended here would make every lead in a
    campaign a duplicate-first-line offender and the rule would be measuring
    the sequence rather than the copy.
    """
    by_id = {record.get("id"): record for record in recs or []}
    leads, packs = [], {}
    for lead in plan.get("leads") or []:
        lead_id = "%s/%s" % (lead.get("record_id"), lead.get("contact_key"))
        leads.append({"id": lead_id,
                      "steps": [{"body": step.get("body")}
                                for step in lead.get("copy") or []]})
        # IDENTITY, NOT PRESENCE. `packfacts` admits a fact only when it can
        # be shown to be this account's; 50 of 71 job rows in the research
        # pilot were a different company, and a pack that kept them would
        # have made a stranger's open roles "supporting evidence".
        pack, _ = packfacts.pack_for(by_id.get(lead.get("record_id")))
        packs[lead_id] = pack
    return leads, packs


def _copylint_report(plan, recs):
    """Run the batch lint over what this stage is about to write.

    `steps_expected` is THIS PLAN'S sequence length, not the lint's module
    constant. The constant is the operator's target cadence; the plan's
    sequence is how many steps this push will actually send, and checking a
    four-step push against a five-step target would refuse every lead for a
    reason that is about the cadence rollout rather than about the copy.
    """
    leads, packs = _copylint_batch(plan, recs)
    expected = len(plan.get("provider_sequence") or ()) or copylint.STEPS_EXPECTED
    found = copylint.check_batch(leads, packs, steps_expected=expected)
    found["steps_expected"] = expected
    found["leads_with_a_pack"] = sum(1 for p in packs.values() if p["facts"])
    return found


def _refuse_copylint(plan, recs, report):
    """Refuse the whole stage if the batch copy lint refuses it.

    IT STOPS THE STAGE rather than skipping the offenders, for the reason
    `_refuse_unsupported` gives directly below: a campaign meant for fifty
    that quietly stages forty-one is a campaign whose reach nobody stated.

    The refusal text is the LINT'S OWN report, not a sentence written here,
    so it names the leads and the rules the lint named - including a rule
    that did not exist when this function was written.

    AN INCOMPLETE BATCH IS NOT ASKED. If any lead carries no approved copy
    for a step of this sequence, the push is refused either way - and it is
    refused BETTER one gate down, because `_ensure_leads` knows WHICH steps
    are missing and says so ("rec-2/rec-2-c1 missing em3 ... generate and
    approve the missing steps"). The lint can only report `empty_step`
    against the lead, because the batch it is handed is a list of bodies
    with no step keys in it.

    Measured 2026-09-25, an hour after this wiring merged: `empty_step`
    fired first on every incomplete plan, so the refusal an operator reads
    for the commonest real failure lost the step name, and the refusal in
    `_ensure_leads` that carries it became unreachable on the live path - a
    correct guard nothing can call, which is the defect `CLAUDE.md` names by
    name. It also masked the tenancy refusal, which `_approved_copy` is
    positioned where it is specifically to avoid.

    THIS IS NOT A RULE BEING WIDENED. No push that was refused becomes
    accepted: the batch cannot be staged at all, nothing reaches a provider,
    and the next run - once the missing steps exist - is linted in full with
    every rule and still before the first provider call. What changes is
    only which of two refusals an operator is handed for one condition, and
    the informative one wins.
    """
    short = [lead for lead in plan.get("leads") or []
             if lead.get("missing_copy")]
    if short:
        return None
    found = _copylint_report(plan, recs)
    report["copylint"] = found
    if not found["refused"]:
        return found
    raise FactoryRefused(
        "the batch copy lint refuses this push, and it runs before any "
        "provider write so nothing has reached the estate:\n%s\nREGENERATE "
        "the affected copy; CLAUDE.md forbids widening a lint rule to let a "
        "draft through." % "\n".join(copylint.report_lines(found)),
        # THE STRUCTURED VERDICT TRAVELS WITH THE REFUSAL. The message is a
        # rendering of `found`; which rule fired against which lead - and which
        # rules did NOT - is only answerable from the report itself, and asking
        # it of the message would be a source-text assertion in a test's
        # clothing.
        report=report)


def _gate_facts(rec):
    """The admitted facts for one record, in the shape `sequencegate` reads.

    Same source as `_copylint_batch`'s pack and for the same reason: a fact is
    admitted only when `packfacts` can show it is THIS account's, and a gate
    handed a stranger's open roles would be supporting a claim with somebody
    else's evidence.

    The ONLY translation here is of key name. `packfacts` calls a fact's words
    a `snippet` and `sequencegate` reads `quote` or `text`, so the words are
    carried across under `text` - which both of the gate's fact readers
    (`claims_supported` and `reason_for_outreach`) understand.
    """
    pack, _ = packfacts.pack_for(rec)
    return [{"text": fact.get("snippet")} for fact in pack.get("facts") or []
            if str(fact.get("snippet") or "").strip()]


def _offer_for(persona, client):
    """The offer this persona is being sold, as `(offer_id, offer)`.

    `(None, None)` when no single offer is selected. TASK-425 criterion 3.

    SELECTION IS NOT REIMPLEMENTED HERE. `generate_campaign._select_offers` is
    the one place that answers "which offer has this run selected for this
    prospect". It encodes the operator's TASK-427 decision - that the
    constituents of a composed offer are provenance rather than shippable
    records - and a second copy of that rule in the staging path is how the gate
    comes to check the spine of one offer while the copy was written for
    another. Imported inside the function because `generate_campaign` pulls in
    `llm` and `skills`, and this module is imported by `configdiff`.

    A PERSONA WITH NO SINGLE OFFER RETURNS None, AND THE GATE REPORTS THAT AS
    UNCHECKED RATHER THAN PASSED. It is not refused here: `_check_offers` is the
    gate that refuses an unselected or unapproved offer and it lives on the
    generation path, where the licence decision belongs. A second licence check
    at staging time would let a library edit stop a campaign whose copy a person
    has already approved, and this function is not a licence check.
    """
    from . import generate_campaign as _gc

    if not persona:
        return None, None
    selected = _gc._select_offers(client, persona)
    if len(selected) != 1:
        return None, None
    offer_id = next(iter(selected))
    return offer_id, selected[offer_id]


def _refuse_sequence_gate(plan, recs, report):
    """Refuse the whole stage if the sequence-level gate refuses it.

    Runs AFTER copylint (which checks individual messages) and BEFORE any
    provider call. `sequencegate.check` asks about the WHOLE sequence:
    repetition across steps, hypothesis stated as a finding, question asked
    twice across channels, a claim with no fact behind it.

    The refusal names the LEAD and the STEP that caused each failure, so the
    operator knows which message to regenerate. A failure is a REFUSAL, not a
    warning: a campaign built from acceptable messages can still be bad, and
    this gate is what says so.

    PER LEAD, NOT ONCE FOR THE CAMPAIGN. This asked the gate about the first
    lead only, on the grounds that "the sequence is campaign-level, so all
    leads share it". They do not: the sequence written to the provider is a
    template of merge fields and every lead carries its OWN words, its own
    account's facts and its own company's ICP verdict. Checking lead one and
    staging fifty is how a rejected company or an unsupported claim reaches a
    provider behind a gate that reported PASSED.

    WHAT IT HANDS THE GATE, and where each one comes from. `sequencegate.check`
    takes seven inputs and this call site passed one, which is why every stage
    refused on `qualified` from 2026-09-26 15:27 (`6fa49014`) onward:

      sequence            the lead's approved copy, keyed by cadence step
      qualification       `qualify.state_of` for this lead's company, carried
                          on the plan. Absence is never manufactured into a
                          qualification: a record nobody qualified resolves to
                          `not_processed`, which the gate refuses
      facts               the account's own admitted research, via `packfacts`
      capability          the capability sentence this lead's copy names, from
                          the client's file by way of the contact's persona
      offer               the offer this contact's persona selects, via
                          `generate_campaign._select_offers`. It carries the
                          `step_objectives` ladder the operator approved and
                          the AI capabilities licensed for that offer, which is
                          what makes `TASK-425` criterion 3 enforceable on a
                          zero-write run rather than documented
      messaging_rules     the offer library's own block, so "at most one AI
                          capability per prospect-facing message" is read from
                          the file the operator edits
      batch_capabilities  NOT SUPPLIED, and deliberately - see below

    THE OFFER'S SPINE IS WHY THIS FUNCTION NOW READS THE OFFER LIBRARY AT ALL.
    `messaging_rules` recorded `enforced_by: sequencegate checks step_objectives`
    next to `enforcement_status: DATA_ONLY_NOT_YET_ENFORCED` - a rule written
    down and read by nothing, which is the defect `CLAUDE.md` names as this
    repository's recurring one. A lead whose persona selects no single offer is
    reported by the gate as UNCHECKED rather than passed, so the difference
    between "the ladder holds" and "nobody looked" survives onto the report.

    WHY `batch_capabilities` IS LEFT FOR THE GATE TO REPORT AS UNCHECKED. That
    check asks whether the copy engine's stage D chose a capability per lead or
    defaulted to one: it fails when five or more leads share a single distinct
    value. There is no stage D on this path. The capability here is a
    deterministic function of the contact's persona and the client's config, so
    a cohort of one persona legitimately shares one capability - and the client
    runs two personas. Measured on the production campaign file, 2026-09-27:
    five staged campaigns (9, 10, 10, 10 and 5 leads) are single-persona, so
    handing this list over would refuse every one of them for a defect they do
    not have. The gate already has the honest answer for a caller that cannot
    answer the question - `batch_capabilities is None` warns that stage D's
    choosing was NOT checked - and that warning is true here.
    """
    leads = plan.get("leads") or []
    if not leads:
        return
    by_id = {record.get("id"): record for record in recs or []}
    # THE LIBRARY'S MESSAGING RULES, READ ONCE. `offers.messaging_rules()` parses
    # the offer file, and it is the same answer for every lead in the campaign.
    # It is NOT wrapped in a try: a malformed offer library is a configuration
    # error and this path must refuse rather than fall back to a rule nobody
    # wrote - `_select_offers` below would raise on the same file anyway.
    from . import offers as _offers
    rules = _offers.messaging_rules()
    client = report.get("client")
    # WHICH THREAD EACH STEP BELONGS TO, from the plan rather than from a second
    # opinion about the cadence.
    #
    # `sequencegate`'s `no_repetition` check reads `subjects` and its own message
    # is "two of the THREE THREAD SUBJECTS are the same" - it was written for the
    # writer's `{A, B, C}`, one entry per thread. This call site handed it one
    # entry per STEP, and a correctly threaded sequence has fewer threads than
    # steps: `EMAILBISON-COPY-REQUIREMENTS.md` requires that "a sequence is one
    # conversation, same-thread follow-ups use the provider's thread_reply rather
    # than a new subject every step", so em2 legitimately carries em1's subject.
    # Five steps carrying three distinct thread subjects therefore read to the
    # check as three duplicates and REFUSED the push. Measured 2026-09-28 on
    # TASK-425's first staged campaign, on copy that had passed every other gate.
    #
    # THIS IS A SHAPE ERROR AT THE CALL SITE, NOT A RULE TO WIDEN, and it is the
    # same class as the defect TASK-426 fixed here: a check handed the wrong
    # inputs cannot answer the question it was written for.
    #
    # THE FIRST VERSION OF THIS FIX WAS A LOOSENING AND IS RECORDED AS ONE. It
    # dropped every follow-up's subject before the gate saw it, which left ONE
    # subject for every cadence configured in this repository - all of them
    # declare exactly one thread starter - so `no_repetition/subjects` became
    # structurally incapable of firing here, and 256 of 1,323 stored contacts
    # flipped from refused to accepted with that as their only failure. An
    # adversarial review refuted the claim that the check "keeps its whole
    # power"; reproduced independently, and it was right.
    #
    # So the THREAD MAP goes to the gate instead, and the gate compares one
    # subject per thread AND WARNS WHEN IT HAD FEWER THAN TWO TO COMPARE. The
    # difference between "the subjects are fine" and "there was only one subject
    # to look at" now survives onto the report, which is the part the first
    # version lost.
    #
    # `thread_reply` comes off `plan["provider_sequence"]`, which is
    # `sequenceplan.derive_bison_sequence`'s projection and the same flag the
    # provider is actually told. Not the client config's
    # `email_sequence.thread_reply_pattern`, and not `generate._PLAN_SUBJECT_OF`:
    # those three disagree about how many threads this cadence has (1, 1 and 3),
    # which is `ISSUE-054`. The projection is the one the wire sees.
    projected = [step for step in plan.get("provider_sequence") or ()
                 if isinstance(step, dict)]
    thread_of, current = {}, None
    for step in projected:
        key = step.get("step_key")
        if not step.get("thread_reply") or current is None:
            current = key
        thread_of[key] = current
    checked, refused = [], []
    for lead in leads:
        copy_entries = lead.get("copy") or []
        if not copy_entries:
            # An incomplete lead is refused either way, and refused BETTER by
            # `_ensure_leads`, which names the missing steps. Same reason
            # `_refuse_copylint` stands aside for it.
            continue
        emails, subjects = {}, {}
        for entry in copy_entries:
            key = entry.get("step_key") or f"step_{entry.get('order', 0)}"
            body = entry.get("body") or ""
            subject = entry.get("subject") or ""
            if body:
                emails[key] = body
            # EVERY subject is handed over, exactly as master handed them. The
            # THREAD MAP is what tells the gate which of them belong to one
            # conversation; dropping them here is what made the check inert.
            if subject:
                subjects[key] = subject
        offer_id, offer = _offer_for(lead.get("persona"), client)
        result = sequencegate.check(
            {"emails": emails, "subjects": subjects},
            facts=_gate_facts(by_id.get(lead.get("record_id"))),
            capability=lead.get("capability"),
            qualification=lead.get("qualification"),
            offer=offer,
            messaging_rules=rules,
            threads=thread_of)
        lead_id = "%s/%s" % (lead.get("record_id"), lead.get("contact_key"))
        # WHICH OFFER'S SPINE THIS VERDICT IS AGAINST, ON THE REPORT. Without
        # it "step_objectives passed" is unreadable: a verdict against no offer
        # carries the same `passed: True` as a verdict against the right one,
        # and TASK-425's audit artifact has to say which offer licensed each
        # message. `None` is recorded as None rather than omitted.
        checked.append({"lead": lead_id, "offer": offer_id, **result})
        if not result.get("passed"):
            refused.append((lead_id, result))
    report["sequencegate"] = {"passed": not refused, "leads": checked}
    if not refused:
        return
    detail = []
    for lead_id, result in refused:
        detail.append(lead_id)
        detail.extend("  " + line
                      for line in sequencegate.report_lines(result))
    raise FactoryRefused(
        "the sequence-level gate refuses %d of %d lead(s) in this push, and it "
        "runs before any provider write so nothing has reached the estate:\n%s"
        "\nREGENERATE the affected steps; the failure names which lead and "
        "which step is wrong." % (len(refused), len(leads), "\n".join(detail)),
        # Same reason as `_refuse_copylint`: `report["sequencegate"]` carries the
        # per-lead result and the per-check verdicts, and a caller that has to
        # parse them back out of the message is reading prose.
        report=report)


def _refuse_unsupported(plan):
    """Refuse the whole stage if any lead's approved copy asserts something
    the record does not support.

    A separate function from `_ensure_leads` so it can be exercised without a
    provider, an estate or a campaign row - the refusal is the part that has
    to be right, and a guard only reachable through four other guards is a
    guard nobody tests.

    IT STOPS THE WHOLE STAGE rather than skipping the lead. `bisonfactory`
    already takes that position for missing copy and for the same reason: a
    campaign meant for nine that quietly stages eight is a campaign whose
    reach nobody stated, and `resume_campaign`'s `expect_leads` count is
    built on the caller knowing that number.
    """
    wanted = plan.get("leads") or []
    untrue = [(lead["record_id"], lead["contact_key"], lead["unsupported_copy"])
              for lead in wanted if lead.get("unsupported_copy")]
    if not untrue:
        return
    detail = "; ".join(f"{rid}/{key} {steps[0][0]}: {steps[0][1]}"
                       for rid, key, steps in untrue[:4])
    raise FactoryRefused(
        f"{len(untrue)} of {len(wanted)} contact(s) carry approved copy that "
        f"asserts something the record does not support: {detail}"
        f"{' and more' if len(untrue) > 4 else ''}. An approval proves a human "
        f"blessed these words, not that they are true of this person, and "
        f"after staging the provider sends on its own - there is no later "
        f"gate. REGENERATE the affected steps; do not edit them and do not "
        f"widen the claim rules to let them through")


def _refuse_bad_greetings(plan):
    """TASK-082. Refuse if any lead's body text has a broken greeting.

    THE DEFECT THIS PREVENTS. EmailBison does NOT have a {first_name} merge
    variable. The greeting is part of the generated body text that travels
    as {BODY_N}. If the generator produces "Hey ," or "Hi undefined," that
    goes straight to the provider and out the door. There is no provider-side
    substitution to save it.

    THREE CLASSES OF DEFECT:
    1. Empty greeting: "Hey ," "Hi ," "Hello ," - name is missing
    2. Literal placeholder: "Hi undefined," "Hi null," "Hi None,"
    3. Planted cohort name: one contact's body contains another contact's
       first name (the hi-jacob defect class for email)

    CALLED BY _ensure_leads, which is called by stage(). Deleting the call
    makes the test fail - that is the wiring proof.
    """
    import re as _re

    wanted = plan.get("leads") or []
    if not wanted:
        return

    # Collect cohort first names for planted-name detection.
    cohort_names = set()
    for lead in wanted:
        first = (lead.get("first_name") or "").strip()
        if first and len(first) > 1:
            cohort_names.add(first)

    problems = []
    for lead in wanted:
        contact_key = lead.get("contact_key", "?")
        record_id = lead.get("record_id", "?")
        own_first = (lead.get("first_name") or "").strip()
        copy = lead.get("copy") or []

        for entry in copy:
            body = entry.get("body") or ""
            step_key = entry.get("step_key", "?")
            if not body:
                continue
            first_line = body.split("\n")[0] if body else ""

            # Check 1: empty greeting.
            if _re.match(r'^(Hey|Hi|Hello)\s*,', first_line):
                problems.append(
                    f"{record_id}/{contact_key} step {step_key}: "
                    f"empty greeting - {first_line[:50]!r}")

            # Check 2: literal placeholder.
            for bad in ("undefined", "null", "None"):
                if bad in first_line:
                    problems.append(
                        f"{record_id}/{contact_key} step {step_key}: "
                        f"greeting contains literal {bad!r} - "
                        f"{first_line[:50]!r}")

            # Check 3: planted cohort name, IN A SALUTATION POSITION.
            #
            # ISSUE-015. This used to flag any occurrence of another cohort
            # member's first name anywhere in the body, and that is not the
            # defect it names. Measured 2026-09-22 across the five campaigns
            # carrying batch 3: 275 flags, every one a false positive.
            #
            #   269 of them on the single name 'Will', which is a first name
            #     AND an ordinary English auxiliary verb - so one cohort
            #     member named Will made every body containing the word
            #     "will" a defect
            #   the rest were company names carrying a person's name:
            #     russellherder.com, terrisandy.com, bigstarbranding.com,
            #     wearerichlifestyle.com, sobepromos.com
            #
            # The hi-jacob defect is a MIS-PERSONALISED GREETING - a letter to
            # Michael that opens by addressing Jacob. Checks 1 and 2 above
            # already read only the greeting line, for exactly that reason.
            # So this looks where a greeting puts a name and nowhere else:
            # after a salutation word, or opening a line as a bare vocative,
            # which is the form the approved Productive copy actually uses
            # ("Janie, I work with ...").
            #
            # NARROWED TO THE DEFECT, NOT WIDENED PAST IT. A planted name in a
            # salutation still fails, on any step and anywhere in the body -
            # the suite asserts that on a second-step follow-up. What no
            # longer fails is the word "will" inside a sentence.
            for name in cohort_names:
                if name == own_first:
                    continue
                planted = (r'^\s*(?:(?:Hi|Hey|Hello|Dear)\s+)?'
                           + _re.escape(name) + r'\s*[,.!:]')
                if _re.search(planted, body,
                              _re.IGNORECASE | _re.MULTILINE):
                    problems.append(
                        f"{record_id}/{contact_key} step {step_key}: "
                        f"body greets cohort name {name!r} "
                        f"(hi-jacob defect class)")

    if problems:
        detail = "; ".join(problems[:4])
        raise FactoryRefused(
            f"{len(problems)} greeting/copy defect(s) detected: {detail}"
            f"{' and more' if len(problems) > 4 else ''}. "
            f"EmailBison has no provider-side variable for first name - "
            f"the greeting is baked into the body text and travels as "
            f"{{BODY_N}}. A broken greeting reaches the prospect as-is. "
            f"REGENERATE the affected steps")


def _unsupported_copy(rec, contact, copy):
    """Every approved step whose words assert something the record cannot
    support. Returns `(step_key, why)` pairs.

    AN APPROVAL IS NOT A FACT-CHECK. `_approved_copy` proves a human blessed
    these exact words - the fingerprint is per step key and the gate checks
    the payload against it - and that is a different question from whether
    the words are true of this person. This module checked the first and
    never the second, so the only thing standing between a stored draft and
    a real person was whoever clicked approve.

    It matters because `_ensure_leads` writes the words into per-lead
    variables and the campaign then sends on its own. `executionguard` runs
    `claims.check` before a SEND, but it never sees these: staging is not a
    send, and after staging the provider does the sending. So for email there
    is no later gate at all - this is the last one.

    Measured 2026-09-14: the 9 live leads on campaign 481 are CLEAN, checked
    against the words actually held at the provider rather than the local
    store. They are clean because they were regenerated after `claims.check`
    was added to `generate.draft`, not because anything here checked. 17
    stored email steps elsewhere in the estate still assert something
    unsupported, and the only reason they cannot be staged is a collision
    gate that is answering a different question.
    """
    from . import claims

    found = []
    for entry in copy or []:
        text = f"{entry.get('subject') or ''} {entry.get('body') or ''}"
        for problem in claims.check(text, rec, contact) or []:
            found.append((entry.get("step_key"),
                          problem.get("why") or "unsupported"))
            break
    return found


# TASK-560: the P.S. is required on these steps. A step in this set whose
# `ps` field is absent or empty BLOCKS - it must never vanish silently.
# This is the SINGLE authority for which steps require a P.S.; both the
# staging check (_approved_copy) and any future consumer read from here.
STEPS_REQUIRING_PS = frozenset({"em1", "em3"})


def _approved_copy(source, contact_key, sequence, record_id, *,
                   cadence_steps=None, campaign=None, config=None):
    """The APPROVED words this contact carries, one entry per sequence step.

    Returns `(copy, missing)`. It REPORTS rather than refuses, and
    `_ensure_leads` is what refuses: this runs inside `_plan`, which is what
    a dry run returns and which happens before the workspace check, so
    raising here would mask a tenancy refusal with a copy complaint and would
    leave an operator no way to ask "what is missing" without being stopped
    at the first answer.

    WHY ANYTHING REFUSES AT ALL. The sequence written to the provider is a
    template of merge fields, so every step's words travel with the lead. A
    step whose variable is absent renders as nothing: the campaign is staged,
    the sequence reads back correctly, the sender is bound, the membership is
    right, and on day eight a real person receives an email with no subject
    and no body. `_variables_for` already said this about the single-step
    case; it was said and not enforced, and the code staged the lead with
    `""` for both. Five steps make it five times as likely and no more
    visible.

    MATCHED BY STEP KEY, NOT BY POSITION. `_sequence_steps` keys each provider
    step to the cadence step it came from, and the record's approvals are
    stored under those same keys - `approval.fingerprint` is per step key and
    `push_id` is `record:contact:step:channel`. Matching by position instead
    would put a day-twelve approval into the day-one slot the first time a
    contact was approved out of order, and the approval fingerprint on the
    wire would still be the one the gate checked.

    An EMPTY sequence reports nothing missing: a campaign the client has
    configured no sequence for stages leads with attribution and no words,
    which is what `_ensure_sequence` already reports and permits.

    VARIANTS ARE RESOLVED HERE, not downstream. A step carrying five variants
    assigns one per contact deterministically (see `cadence.variant_for`),
    and the variant's words - not the base template's - are what the provider
    receives. Each variant is approved independently: five variants means
    five approvals, not one stretched over five. A variant whose words have
    not been approved is treated the same as a step with no approval at all:
    it is reported missing and the stage refuses on it.
    """
    if not sequence:
        return [], []
    steps = ((source or {}).get("cadence") or {}).get(contact_key) or {}
    # Index cadence step specs by key so variant lookup is O(1).
    spec_by_key = {}
    for spec in (cadence_steps or ()):
        if spec.get("key"):
            spec_by_key[spec["key"]] = spec
    copy, missing = [], []
    for node in sequence:
        key = node.get("step_key")
        if key is None:
            # The single-step shape carries no cadence key, so the earliest
            # approved email step is the opener, exactly as before.
            found = _earliest_approved_email(steps)
        else:
            step = steps.get(key) or {}
            spec = spec_by_key.get(key) or {}
            found = _resolve_step_copy(step, spec, key, contact_key,
                                       campaign, config)
        if not found or not found.get("subject") or not found.get("body"):
            missing.append(str(key) if key is not None
                           else f"step {node['order']}")
            continue
        # TASK-560: A required P.S. that is missing BLOCKS. Whether a P.S.
        # is required is a property of WHICH STEP this is
        # (STEPS_REQUIRING_PS), not of whether the field survived
        # serialisation. An em1/em3 with no `ps` key at all is refused -
        # absence is not permission, and a boundary that drops empty fields
        # must not convert the blocking case into the silently-passing one.
        if key in STEPS_REQUIRING_PS:
            ps_val = (found.get("ps") or "").strip()
            if not ps_val:
                missing.append(f"{key} (missing P.S.)")
                continue
        copy.append(found)
    return copy, missing


def _certified_copy(step, key, extra=None):
    """The staged words for one step, or None unless an approval certifies
    THESE EXACT WORDS.

    THE ONLY PLACE EMAIL COPY BECOMES STAGEABLE. Every branch below - variant,
    no-variant, single-step opener - returns through here, because "a human
    approved this step" and "a human approved the words this step is about to
    ship" are two different questions and only the second one is safe to ask
    at staging time.

    The entry is built FIRST and the fingerprint is then computed over the
    entry's own `subject` and `body`, so the material that is hashed is the
    same string the provider receives in `{SUBJECT_N}` / `{BODY_N}`. A check
    that hashed the step instead could agree while the words in the payload
    came from somewhere else, which is exactly the defect this closes:
    `approve.approve_step` stamped a fingerprint taken over the
    campaign-expanded step onto a slot that still held older generated copy,
    and the no-variant branch staged the slot's words after checking only that
    an approval EXISTED. Measured 2026-09-16 on campaign 485: ten leads, zero
    reported missing, thirty steps of words no operator had approved.

    `channel` and `note` come from the step because `approval.fingerprint`
    covers them too, and an approval taken over a step carrying a note does
    not certify the same step with the note removed.

    FAILS CLOSED, always by returning None, which `_approved_copy` reports as
    missing copy and `_ensure_leads` refuses the whole stage on:
      - no approval on the step at all
      - an approval with no fingerprint recorded on it
      - a fingerprint that does not cover the words being staged
    """
    from . import approval

    stamp = (step or {}).get("approval") or {}
    recorded = stamp.get("fingerprint")
    if not recorded:
        # No approval, or an approval that records nothing about the words it
        # was given for. Neither certifies anything.
        return None
    if not approval.is_accountable_approver(stamp.get("by")):
        # An approval this system recorded for itself is not an approval. The
        # fingerprint proves the words have not moved; it cannot prove a person
        # ever read them, and on a `generated: true` step the words never move,
        # so a self-stamp would stay current forever.
        return None
    entry = {"step_key": key, "subject": (step or {}).get("subject"),
             "body": (step or {}).get("body")}
    # Include ps in the entry if the step has the field, even if empty. This
    # allows downstream checks to detect "step expected P.S. but got none".
    # The fingerprint only includes non-empty ps for backward compatibility.
    if "ps" in (step or {}):
        entry["ps"] = (step or {}).get("ps")
    material = dict(step or {})
    material["subject"] = entry["subject"]
    material["body"] = entry["body"]
    # Fingerprint only includes non-empty ps for backward compatibility with
    # existing approvals that were computed without ps.
    ps_for_fingerprint = (step or {}).get("ps")
    if ps_for_fingerprint:
        material["ps"] = ps_for_fingerprint
    if approval.fingerprint(material) != recorded:
        return None
    if extra:
        # `extra` IS METADATA AND MAY NEVER BE COPY.
        #
        # The merge happens AFTER the fingerprint proof, so a caller passing
        # `subject` or `body` here would overwrite certified words with
        # uncertified ones and every layer downstream would still report
        # success. Today the single caller passes variant_id/style/version, so
        # the hatch is unused - but "unused" is a fact about this week's
        # callers, and the next caller is exactly how a hatch like this gets
        # walked through. Found by an independent model reading the function
        # cold, which is the whole reason for asking one.
        forbidden = sorted(set(extra) & {"subject", "body", "note", "message", "ps"})
        if forbidden:
            raise FactoryRefused(
                f"_certified_copy was handed prospect-facing field(s) "
                f"{forbidden} as metadata for step {key!r}. `extra` is merged "
                f"after the approval is verified, so copy arriving that way "
                f"would reach a prospect uncertified. Put the words in the "
                f"step before it is fingerprinted")
        entry.update(extra)
    return entry


def _resolve_step_copy(stored_step, spec, key, contact_key, campaign, config):
    """The approved words for one step, resolving variants when present.

    When the step spec carries variants, the assigned variant's words are
    used and the variant_id is recorded on the result. The variant is
    resolved deterministically so the same contact always gets the same arm.

    Every variant must be approved independently. The approval fingerprint
    covers the variant's words because `variants.apply_to_step` puts them
    into the step before `approval.fingerprint` hashes it. A variant whose
    words do not match any stored approval is not copy anybody has blessed.

    NEITHER BRANCH RETURNS WORDS AN APPROVAL DOES NOT COVER. The variant
    branch always compared; the no-variant branch asked only whether an
    approval existed, so a stored slot whose copy had moved on from the
    fingerprint stamped on it staged clean. Both go through
    `_certified_copy` now, which is the one place that comparison happens.
    """
    from . import cadence as _cadence
    from . import variants

    entry = None
    if spec.get(_cadence.VARIANTS_KEY):
        recorded = (stored_step or {}).get("variant_id")
        entry = _cadence.variant_for(spec, campaign, contact_key,
                                     recorded=recorded, config=config)
    if entry is not None:
        # The variant's words, applied to the stored step so the approval
        # fingerprint covers them.
        stepped = variants.apply_to_step(dict(stored_step or {}), entry)
        return _certified_copy(
            stepped, key,
            extra={"variant_id": entry.get("variant_id"),
                   "variant_style": entry.get("style"),
                   "variant_version": entry.get("version")})
    # No variant: the stored step's own words - and only if the approval on
    # the step is an approval OF those words.
    if stored_step.get("channel") == "email":
        return _certified_copy(stored_step, key)
    return None


def _earliest_approved_email(steps):
    """The first APPROVED email step by key, or None.

    Used only for the single-step sequence shape, where the one step that
    goes out is the opener and a later step's words in its place would be a
    message arriving out of order.

    Which is why an approval that does not certify the opener's stored words
    returns None rather than walking on to the next step: falling through
    would answer "this contact has no approved opener" with a day-eight
    message, and a refusal is the only honest answer to it.
    """
    for step_key in sorted(steps or {}):
        step = (steps or {})[step_key] or {}
        if step.get("channel") != "email" or not step.get("approval"):
            continue
        return _certified_copy(step, step_key)
    return None


def _find_or_create(campaign, report, by="system"):
    """The provider campaign for this row, reused if it exists.

    Reuse comes first and is checked against the PROVIDER, not against the
    row: a `bison_campaign_id` naming a campaign that has since been deleted
    is a stale binding, and building on it would attach leads to nothing.
    """
    bound = campaign.get("bison_campaign_id")
    if bound:
        try:
            live_row = bison.campaign(bound)
        except ProviderError as e:
            raise FactoryRefused(
                f"campaign {campaign.get('campaign_id')} is bound to EmailBison "
                f"campaign {bound}, which the provider will not return "
                f"({e}). Refusing to create a second one behind a binding "
                f"that may still be valid; reconcile by hand") from None
        status = str(live_row.get("status") or "").lower()
        if status == bison.PENDING_DELETION:
            # DELETE IS ASYNCHRONOUS HERE AND THE ROW SURVIVES IT FOR A FEW
            # SECONDS. Measured 2026-09-13: `DELETE /campaigns/{id}` answers
            # 200 "queued for deletion", the GET keeps answering 200 with this
            # status, and two seconds later the same GET is a 404. Staging
            # into that window writes a cap, a schedule, a sequence and a set
            # of leads into a campaign that is about to stop existing, and
            # every readback in between looks correct.
            raise FactoryRefused(
                f"campaign {campaign.get('campaign_id')} is bound to "
                f"EmailBison campaign {bound}, which is {status!r}. It is on "
                f"its way out and anything staged into it goes with it. Clear "
                f"the binding once the provider has finished deleting it")
        report["did"].append(f"reused EmailBison campaign {bound}")
        report["provider"]["status_before"] = live_row.get("status")
        return bound, str(live_row.get("name") or report["plan"]["name"])

    # BEFORE CREATING: IS ONE ALREADY THERE UNDER THIS ROW'S NAME?
    #
    # This is the crash-between-POST-and-persist case, and until now the
    # module's own docstring claimed it was "reported as ambiguous rather than
    # retried" while the code went straight to a second POST. `bison_campaign_
    # id` is written inside the transaction that reads it, so the window is
    # small - and a window that is only small is one that eventually opens.
    #
    # The lookup is exact and the name is derived, so this finds the campaign
    # this row would have built and nothing else. Two of them is not a case to
    # choose between: both are real campaigns that can hold real people.
    planned = report["plan"]["name"]
    orphans = bison.find_campaigns_by_name(planned)
    orphans = [o for o in orphans
               if str(o.get("status") or "").lower() != bison.PENDING_DELETION]
    if len(orphans) > 1:
        raise FactoryAmbiguous(
            f"EmailBison holds {len(orphans)} campaigns named {planned!r} "
            f"({sorted(o.get('id') for o in orphans)}) and this row is bound "
            f"to none of them. Both can hold real people. Bind the right one "
            f"by hand and delete the other; do NOT re-run this")
    if orphans:
        found = orphans[0]
        _bind(campaign, found["id"], "found by name and bound: it was created "
                                     "and never recorded")
        report["did"].append(
            f"recovered EmailBison campaign {found['id']} by name: it existed "
            f"already and this row was bound to nothing")
        report["provider"]["recovered"] = True
        report["provider"]["status_before"] = found.get("status")
        return found["id"], str(found.get("name") or planned)

    payload = {"name": planned}
    # `perform` reports the response as trimmed JSON TEXT, which is right for
    # an audit line and useless for reading an id back out of. The transport
    # holds the real row, so it is captured here rather than reparsed.
    created = {}

    def _create(p):
        created.update(bison.create_campaign(p["name"]))
        return created

    providerwrites.perform(
        providerwrites.EMAIL_CREATE_CAMPAIGN,
        campaign=str(campaign.get("campaign_id")), tenant=campaign.get("client"),
        payload=payload, transport=_create,
        readback=lambda: {"exists": bool(created.get("id"))},
        expected={"exists": True}, by=by)
    provider_id = created.get("id")
    if not provider_id:
        raise FactoryAmbiguous(
            "EmailBison accepted the campaign but returned no id. A campaign "
            "may now exist that nothing here can name. Find it by name and "
            "bind it by hand; do NOT re-run this")

    # PERSIST IMMEDIATELY, IN ITS OWN TRANSACTION.
    # Everything after this point can be retried. This cannot: an unpersisted
    # id is a campaign nobody can find, and the next run would build another -
    # which is now recoverable by name above rather than merely narrow.
    _bind(campaign, provider_id, "created and bound")
    report["did"].append(f"created EmailBison campaign {provider_id}")
    return provider_id, planned


def _bind(campaign, provider_id, why):
    """Write the provider's campaign id onto the row, in its own transaction."""
    with campaigns.transaction() as rows:
        row = campaigns.get(str(campaign.get("campaign_id")), rows)
        if row is not None:
            row["bison_campaign_id"] = provider_id
            campaigns.log(row, "provider",
                          f"EmailBison campaign {provider_id} {why}")
    return provider_id


def _ensure_limits(provider_id, campaign, provider_name, report):
    """Cap the campaign before it holds anybody.

    The provider's default is 1000 emails a day and `POST /campaigns` accepts
    a cap and stores 1000 anyway, so a campaign is uncapped until something
    explicitly caps it. This runs before leads are attached: the order is the
    point, since a cap applied afterwards is a cap that was briefly absent.

    A campaign whose daily volume nobody configured is REFUSED rather than
    left on the default. "Nobody said" and "a thousand a day" must not be the
    same state.

    `provider_name` IS THE PROVIDER'S OWN NAME, not the planned one. The cap
    route requires `name` in the same body, so writing a cap rewrites the
    name - and re-staging is routine. Passing the planned name here meant
    reconciling a campaign somebody had renamed in EmailBison's UI silently
    renamed it back, which is an edit nobody asked this function to make.
    """
    volume = (campaign.get("daily_volume") or {}).get("email")
    if not volume:
        raise FactoryRefused(
            f"campaign {campaign.get('campaign_id')!r} sets no email daily "
            f"volume. EmailBison defaults to 1000 a day and discards a cap "
            f"passed at create time, so staging this would leave a campaign "
            f"nobody rate-limited")
    state = bison.set_limits(provider_id, provider_name, int(volume))
    report["provider"]["limits"] = state
    report["did"].append(f"capped at {state['max_emails_per_day']}/day")


def _ensure_schedule(provider_id, plan, report):
    """Write the sending window, and refuse a campaign that has none.

    Same argument as the daily cap: a campaign staged without a window takes
    whatever the provider does, and "nobody chose" must not be indistinguish-
    able from "somebody chose that". `GET .../schedule` answers 200 with
    `success: false` when no schedule exists, so absence here is read from the
    body rather than the status.

    "ALREADY CORRECT" MEANS ALL OF IT. This compared the days and the timezone
    and not the hours, so narrowing a window from 09:00-17:00 to 09:00-12:00
    on the same days was reported as "already correct; unchanged" and the
    campaign kept sending until five. The hours are the part of a sending
    window a client actually asks to change.
    """
    window = plan.get("window") or {}
    missing = [k for k in ("days", "start", "end", "timezone")
               if not window.get(k)]
    if missing:
        raise FactoryRefused(
            f"the client config sets no sending window ({', '.join(missing)} "
            f"absent), so this campaign would send on whatever schedule the "
            f"provider defaults to. Set `sending_window` for this client")
    if bison.schedule_matches(bison.schedule(provider_id), window["days"],
                              window["start"], window["end"],
                              window["timezone"]):
        report["did"].append("schedule already correct; unchanged")
        return
    bison.set_schedule(provider_id, window["days"], window["start"],
                       window["end"], window["timezone"])
    report["did"].append(
        f"scheduled {len(window['days'])} day(s) {window['start']}-"
        f"{window['end']} {window['timezone']}")


def _ensure_senders(provider_id, campaign, report):
    """Bind the inboxes this campaign sends from.

    The provider answers 200 with `success: false` when it attaches nothing,
    so `bison.attach_senders` reads the membership back and raises unless
    every sender asked for is actually bound. A campaign with no configured
    senders is left alone rather than guessed at - picking an inbox would be
    choosing which human a prospect hears from.
    """
    wanted = []
    for sender in (campaign.get("senders") or {}).get("email") or []:
        ident = sender.get("provider_account_id") if isinstance(sender, dict) \
            else sender
        if ident:
            wanted.append(int(ident))
    if not wanted:
        report["did"].append(
            "no senders staged: the campaign names none, and choosing an "
            "inbox would be choosing who a prospect hears from")
        return
    bound = bison.campaign_senders(provider_id)
    if set(wanted) <= set(bound):
        report["did"].append(f"{len(wanted)} sender(s) already bound")
        return
    state = bison.attach_senders(provider_id, wanted)
    report["provider"]["senders"] = state["senders"]
    report["did"].append(f"bound {len(state['senders'])} sender inbox(es)")


def _comparable_step(subject, body, thread_reply):
    """One sequence step, in a shape the provider and we can be compared in.

    THE PROVIDER REWRITES THE SUBJECT ON A THREAD REPLY, and it is documented
    behaviour rather than drift. TASK-159 measured it across 153 same-thread
    follow-ups in the estate: EmailBison prepends "Re: " itself, and
    `EMAILBISON-COPY-REQUIREMENTS.md` says not to write it ourselves.

    So a verbatim comparison of what we asked for against what is held is
    guaranteed to disagree on every `thread_reply` step, forever. Measured
    2026-09-16 on campaign 484: five steps written once, the only difference
    being "Re: " on steps 2 and 4, and the read-back called it DRIFTED and
    raised `WriteUnverified`. Nothing had drifted. The campaign was correct.

    A false DRIFTED is expensive in a specific way: `set_sequence` APPENDS,
    so the operator is told not to retry, and the campaign is abandoned as
    unverifiable when it was right all along.

    Normalising ONLY this one leading token, ONLY on a step that declares
    itself a thread reply. Body and `thread_reply` are still compared exactly,
    and a subject that differs by anything else still fails.
    """
    text = str(subject or "")
    if thread_reply and text[:4].lower() == "re: ":
        text = text[4:]
    return (text, body, thread_reply)


def _ensure_sequence(provider_id, campaign, plan, report, by="system"):
    """Write the sequence into an EMPTY campaign, or refuse.

    THE WRITE APPENDS AND NOTHING CAN UNDO IT. Measured 2026-09-13: two writes
    leave two steps, three writes leave four, renumbered 1, 3, 2, 4. There is
    no replace verb and no per-step route - the sequence path is GET, HEAD,
    POST only. A campaign whose sequence is written twice therefore sends
    twice, the second email carrying the older copy, and the only remedy is
    deleting the campaign.

    `providerwrites.staged_already` guarded the IDENTICAL payload, which is
    the case that never needed guarding: a client editing `email_sequence`, or
    a campaign whose derived title changed, produces a DIFFERENT payload, and
    that went straight to a second POST. So the provider is asked what it
    holds, and a campaign already holding a different sequence stops here.

    AND THE READ-BACK IS A READ NOW. It used to be `{"steps": len(steps)}`
    compared against `{"steps": len(steps)}` - the request compared to itself,
    which agreed unconditionally. `bison.sequence_steps` answers the real
    question, so a write that did not take is visible.
    """
    # THE TITLE COMES OFF THE PLAN, like the steps. It is one of the two
    # fields this write sends, and reading it out of the raw client config
    # while the steps came from the plan is how a payload ends up half
    # projected: the plan already carries the declared title, so there is no
    # reason for this function to read `email_sequence` a second time.
    title = ((plan.get("sequence_plan") or {}).get("email") or {}).get("title")
    # `step_key` is this module's own bookkeeping - it is how a lead's
    # approved words are matched to the step that will send them - and the
    # provider has no field for it. Stripped here rather than never carried,
    # because the readback compares what was asked for against what is held.
    steps = [{k: v for k, v in node.items() if k != "step_key"}
             for node in plan.get("provider_sequence") or []]
    if not steps:
        report["did"].append(
            "no sequence staged: the client config names no `email_sequence`")
        return
    held = bison.sequence_steps(provider_id)
    if held:
        wanted = [_comparable_step(s["email_subject"], s["email_body"],
                                   s.get("thread_reply")) for s in steps]
        got = [_comparable_step(s.get("email_subject"), s.get("email_body"),
                                s.get("thread_reply")) for s in held]
        if got == wanted:
            report["did"].append(
                f"sequence already staged ({len(held)} step(s)); unchanged")
            return
        raise FactoryRefused(
            f"EmailBison campaign {provider_id} already holds {len(held)} "
            f"sequence step(s) and they are not the {len(steps)} this "
            f"campaign specifies. The sequence route APPENDS - there is no "
            f"replace and no delete - so writing would leave the campaign "
            f"sending both, the old copy second. Held: "
            f"{[s.get('email_subject') for s in held]}. Wanted: "
            f"{[s['email_subject'] for s in steps]}. Rebuild the campaign, or "
            f"fix it by hand in EmailBison")
    # THE PROVIDER CAMPAIGN IS PART OF WHAT THIS WRITE IS.
    #
    # `providerwrites.perform` refuses a repeat of the same MATERIAL for the
    # same campaign row, and the material used to be the title and the steps
    # alone. So a row whose provider campaign was deleted and rebuilt could
    # never be given its sequence again: the new campaign holds nothing, the
    # row remembers the same words, and the write is refused. Naming the
    # provider campaign makes staging into 501 a different write from staging
    # into 500, which is what it is. The transport reads `title` and
    # `sequence_steps` and ignores this.
    payload = {"title": title or plan["name"],
               "bison_campaign_id": provider_id,
               "sequence_steps": steps}
    providerwrites.perform(
        providerwrites.EMAIL_SET_SEQUENCE,
        campaign=str(campaign.get("campaign_id")), tenant=campaign.get("client"),
        payload=payload,
        transport=lambda p: bison.set_sequence(provider_id, p["title"],
                                               p["sequence_steps"]),
        readback=lambda: {"steps": [
            _comparable_step(s.get("email_subject"), s.get("email_body"),
                             s.get("thread_reply"))
            for s in bison.sequence_steps(provider_id)]},
        expected={"steps": [_comparable_step(s["email_subject"],
                                             s["email_body"],
                                             s.get("thread_reply"))
                            for s in steps]}, by=by)
    report["did"].append(f"staged a {len(steps)}-step sequence")


def _known_lead_ids(campaign, wanted):
    """Provider lead ids this system already recorded, by contact key."""
    recs = store.load()
    by_id = {r.get("id"): r for r in recs}
    known = {}
    for lead in wanted:
        rec = by_id.get(lead["record_id"]) or {}
        for contact in rec.get("contacts") or []:
            if contact.get("key") == lead["contact_key"] and contact.get(
                    "bison_lead_id"):
                known[lead["contact_key"]] = contact["bison_lead_id"]
    return known


def _remember_lead(lead, lead_id):
    """Write the provider's id onto the contact, immediately.

    Immediately, and in its own transaction, for the same reason the campaign
    id is: an id the provider issued and this system did not record is a lead
    that will be created again, and the second attempt is the one that fails.
    """
    with store.transaction() as rows:
        for rec in rows:
            if rec.get("id") != lead["record_id"]:
                continue
            for contact in rec.get("contacts") or []:
                if contact.get("key") == lead["contact_key"]:
                    contact["bison_lead_id"] = lead_id


def _remember_leads(pairs):
    """Write many provider ids in one transaction instead of one per lead.

    At 30k records each transaction reads and writes the full queue. N leads
    in N transactions moves O(N * queue_size) bytes; one transaction moves it
    once. `_remember_lead` is kept for the single-lead path; this is what
    `_ensure_leads` calls after the create loop.
    """
    if not pairs:
        return
    with store.transaction() as rows:
        by_id = {rec.get("id"): rec for rec in rows}
        for lead, lead_id in pairs:
            rec = by_id.get(lead["record_id"])
            if rec is None:
                continue
            for contact in rec.get("contacts") or []:
                if contact.get("key") == lead["contact_key"]:
                    contact["bison_lead_id"] = lead_id


def _append_ps(body, ps):
    """Append the P.S. to the body if present.

    The P.S. is a separate field on the step, rendered after the body with a
    blank line separator. An empty or missing P.S. returns the body unchanged.
    """
    ps = (ps or "").strip()
    if not ps:
        return body or ""
    body = (body or "").rstrip()
    return f"{body}\n\n{ps}" if body else ps


def _variables_for(lead, campaign, sequence=None):
    """Everything this lead carries at the provider.

    Two kinds, and both are load-bearing.

    ATTRIBUTION. `adapters.from_emailbison` reads `record_id` and
    `contact_key` back off an inbound reply. Without them a reply arrives
    attached to an address and to nothing else, and reply-stop cannot find
    the person it is supposed to stop.

    THE COPY. The sequence is a template of merge fields - `{SUBJECT}` and
    `{BODY}` - so the approved words travel per lead and render into it. A
    lead staged without them produces an email with an empty subject and an
    empty body, and nothing in the staging readback would have shown it: the
    campaign, the schedule, the sender and the membership would all look
    exactly right. `_ensure_leads` refuses that case rather than trusting
    this paragraph to be read.

    ONE VARIABLE PER STEP, NUMBERED BY POSITION. A custom variable holds one
    value per lead, so five steps of generated copy cannot share `subject`:
    the template `{SUBJECT_3}` resolves to the variable `subject_3`, which is
    the third step's approved words. The unnumbered `subject` and `body` are
    still written for a single-step sequence, because campaign 451 is staged
    against `{SUBJECT}` and is production evidence with a scheduled send on
    it. A campaign built from the multi-step shape never reads them.

    ONE SHAPE PER CAMPAIGN, NEVER BOTH. A single-step campaign carries
    `subject` and `body` and no numbered pair; a multi-step one carries the
    numbered pairs and neither unnumbered name. Writing both would leave
    every lead holding a variable its own template never reads, and a reader
    comparing two leads could not tell which shape the campaign was built in.

    THREADED SEQUENCES: SUBJECT_1 ONLY. When the sequence has threaded
    follow-ups (any step declares ``thread_reply: true``), only ``subject_1``
    carries the opener's subject. Follow-up subject variables are written as
    empty strings: the template references ``{SUBJECT_1}`` for every step,
    and the provider prepends ``Re:`` itself. A non-empty ``subject_2`` on a
    threaded lead is a stale value from a previous non-threaded era, and
    ``_stale_clearances`` wipes it during reconciliation.
    """
    values = {"record_id": lead["record_id"],
              "contact_key": lead["contact_key"],
              "client": campaign.get("client") or ""}
    copy = lead.get("copy") or []
    if len(copy) <= 1:
        values["subject"] = lead.get("subject") or ""
        # For single-step, read body and ps from the copy node if present
        node = copy[0] if copy else {}
        body = node.get("body") or lead.get("body") or ""
        ps = node.get("ps") or lead.get("ps") or ""
        values["body"] = _append_ps(body, ps)
    else:
        threaded_keys = set()
        for node in (sequence or ()):
            if node.get("thread_reply") and node.get("step_key"):
                threaded_keys.add(node["step_key"])
        for position, node in enumerate(copy, start=1):
            step_key = node.get("step_key")
            if position > 1 and step_key in threaded_keys:
                values[f"subject_{position}"] = ""
            else:
                values[f"subject_{position}"] = node.get("subject") or ""
            body = node.get("body") or ""
            ps = node.get("ps") or ""
            values[f"body_{position}"] = _append_ps(body, ps)
    return bison._variables(values)


def _stale_clearances(sequence):
    """Empty-valued entries for numbered copy slots the sequence does not use.

    TWO KINDS OF STALE, ONE MECHANISM.

    1. Out-of-range positions: a lead that previously carried a longer
       sequence holds ``subject_N`` and ``body_N`` variables beyond the
       current length. ``_variables_for`` names only the positions the
       sequence reads, so the reconciliation in ``_ensure_leads`` never
       compares - and never clears - the higher ones. Measured on campaign
       485 on 2026-09-16: ten leads held ``subject_4``, ``subject_5``,
       ``body_4`` and ``body_5`` from a five-step era while the campaign had
       shrunk to three steps.

    2. In-range follow-up subjects on a threaded sequence: when the threaded
       shape is in effect (any step declares ``thread_reply: true``), only
       ``subject_1`` carries prospect-facing content. Follow-up subjects at
       positions 2..N are not referenced by the template (all steps reference
       ``{SUBJECT_1}``), but a lead from a previous non-threaded era may still
       hold a non-empty ``subject_2`` or ``subject_3``. Without clearing them,
       a config change from non-threaded to threaded would leave stale
       subjects on the lead that the template no longer reads - but that a
       future template change could resurrect.

    Returns explicit empties for:
    - Every ``subject_{2..N}`` when the sequence is threaded (in-range
      follow-up subjects the threaded shape does not use).
    - Every ``subject_{N+1..MAX}`` and ``body_{N+1..MAX}`` (out-of-range
      positions beyond the sequence length).

    ``_ensure_leads`` merges them into the wanted set; the provider PATCH
    stores the empty value and the template never reads a variable its
    sequence does not declare.

    Single-step campaigns use unnumbered ``subject`` and ``body`` and have
    no numbered positions to clear, so the answer is empty.
    """
    n_steps = len(sequence)
    if n_steps < 2:
        return []
    entries = []
    has_threading = any(s.get("thread_reply") for s in sequence)
    for pos in range(2, MAX_SEQUENCE_STEPS + 1):
        if pos <= n_steps:
            if has_threading:
                entries.append({"name": f"subject_{pos}", "value": ""})
        else:
            entries.append({"name": f"subject_{pos}", "value": ""})
            entries.append({"name": f"body_{pos}", "value": ""})
    return entries


def _already_on_campaign(provider_id):
    """Addresses this campaign ALREADY holds, lowercased.

    Read from the campaign's own queue, which carries `lead.email` per row and
    is one paginated read. A lead enrolled but with no queue row yet is not in
    this set and is therefore still collision-checked - the safe direction, and
    the reason this returns a set of what is KNOWN present rather than a claim
    about what is absent.

    An unreadable queue returns the empty set, so every lead is checked. That
    is the same direction: it can only add checks, never skip one.
    """
    if not provider_id:
        return set()
    try:
        rows = bison.scheduled_emails(provider_id)
    except Exception:                                           # noqa: BLE001
        return set()
    return {str(((row.get("lead") or {}).get("email") or "")).strip().lower()
            for row in rows} - {""}


def _refuse_colliding_leads(wanted, workspace_id, already_on=()):
    """Refuse leads whose account the client's estate says STOP or HOLD.

    ## RE-STAGING AN EXISTING MEMBER IS NOT A NEW TOUCH

    ISSUE-021. `stage` re-submits every lead on the campaign, not only the new
    ones, so once a campaign has emailed somebody that lead collides with ITS
    OWN sent state - and this refuses the WHOLE stage rather than one lead, so
    two already-contacted people blocked 34 good ones on 2026-09-22.

    The account gate exists to stop us ADDING somebody to an account that is
    already in play. A lead that is already on this campaign is not being
    added; it is being re-described. Whether it should have been added was
    decided when it was, and re-deciding it now on a state OUR OWN send
    created is the circular reading that blocked batch 3.

    `already_on` is what the campaign already holds. It never widens the check
    to a lead that is not there: an unreadable queue yields an empty set and
    everything is checked, which is the safe direction.

    Uses `collision.check_account` and `collision.account_policy` - the same
    gates `executionguard` runs at send time. Fetched per domain and cached
    for the duration of this call: a campaign's leads typically span a small
    number of domains, and each `check_account` costs one paginated search.

    WHICH STATES BLOCK AND WHICH MAY PASS, per `account_policy`:
      - `in_sequence`   -> STOP  -> block. A second channel now is the
                        collision this module exists to prevent.
      - `stopped`       -> HOLD  -> block. The status does not say who ended
                        it; it is the state a reply or unsubscribe leaves.
      - `bounced`       -> HOLD  -> block. The data is suspect; a person
                        should look before we spend more.
      - `sequence_finished` -> ALLOW -> may pass. A campaign that ran its
                        course with no reply is history, not a live conflict.
                        It is still REPORTED in the account check, so "cold
                        outreach" is never claimed about a worked account.

    An UNREADABLE estate is refused. "We could not check" and "there is
    nothing there" are the two answers this module exists to keep apart.
    """
    from . import collision

    on_campaign = {str(a).strip().lower() for a in (already_on or ())}

    by_domain = {}
    for lead in wanted:
        address = str(lead["email"]).strip().lower()
        if address in on_campaign:
            # Already a member: being re-described, not added. See ISSUE-021.
            continue
        domain = address.rsplit("@", 1)[-1]
        if domain:
            by_domain.setdefault(domain, []).append(lead)

    refused = []
    for domain, leads in by_domain.items():
        try:
            account = collision.check_account(
                domain, expect_workspace=workspace_id)
        except collision.CollisionUnknown as e:
            raise FactoryRefused(
                f"the provider estate could not be read for {domain}: {e}. "
                f"Refusing to stage leads at an unreadable account: a lead "
                f"that cannot be checked cannot be cleared") from None
        verdict, why = collision.account_policy(account)
        if verdict in (collision.STOP, collision.HOLD):
            for lead in leads:
                refused.append((lead, verdict, why))

    if refused:
        detail = "; ".join(
            f"{lead['contact_key']} ({lead['email']}): {v} - {w}"
            for lead, v, w in refused[:5])
        raise FactoryRefused(
            f"{len(refused)} contact(s) collided with the client's own estate: "
            f"{detail}"
            f"{' and more' if len(refused) > 5 else ''}. "
            f"A contact the client is already emailing or whose data is "
            f"suspect must not be staged into a Resonate campaign")


def _ensure_leads(provider_id, campaign, plan, report, by="system"):
    """Create the leads this campaign needs, then attach exactly those.

    Attachment is checked against provider membership on both sides, so a
    re-run costs reads and writes nothing. `bison.attach_leads` raises unless
    the readback contains what was asked for, which is what stops a partial
    attach being reported as a full one.

    A LEAD WITHOUT THE WORDS ITS SEQUENCE WILL ASK FOR STOPS THE WHOLE RUN.
    This is the last point at which nothing has reached a person: the
    sequence is written, the campaign is stopped, and no lead exists yet. A
    step whose copy variable is absent sends an email with an empty subject
    and an empty body, and `_readback` would report that campaign correct -
    the sequence, the schedule, the sender and the membership are all exactly
    right. The whole run stops rather than the one lead being skipped,
    because a campaign that quietly stages four of five people is a cohort
    nobody can reason about afterwards. `_plan` lists them without raising,
    so a dry run answers "which contacts, and which steps" in one pass.
    """
    wanted = plan.get("leads") or []
    if not wanted:
        report["did"].append("no leads staged: the plan carries none")
        return

    # TASK-400: refuse dry-run stamped records BEFORE any provider call.
    from . import generate_campaign, store as _store
    generate_campaign.refuse_dry_run_records(_store.load())

    _refuse_unsupported(plan)
    _refuse_bad_greetings(plan)
    short = [(lead["record_id"], lead["contact_key"], lead["missing_copy"])
             for lead in wanted if lead.get("missing_copy")]
    if short:
        detail = "; ".join(f"{rid}/{key} missing {', '.join(steps)}"
                           for rid, key, steps in short[:5])
        raise FactoryRefused(
            f"{len(short)} of {len(wanted)} contact(s) carry no approved copy "
            f"for every step of this campaign's "
            f"{len(plan.get('provider_sequence') or [])}"
            f"-step sequence: {detail}"
            f"{' and more' if len(short) > 5 else ''}. Each missing step sends "
            f"a real person an email with an empty subject and an empty body, "
            f"and every readback would agree the campaign was correct. "
            f"Generate and approve the missing steps, then stage again")
    # THE ESTATE IS CHECKED BEFORE ANY LEAD IS CREATED OR ATTACHED.
    # `_ensure_leads` calls `bison.create_lead` and `bison.attach_leads`
    # directly, bypassing `executionguard.authorize()` and every gate it
    # runs. The killswitch check below closes the tenant-level half of that
    # gap; this closes the person-level half. A contact already mid-sequence,
    # stopped, bounced or replied in the client's own estate must not be
    # staged into a Resonate campaign. Measured 2026-09-13: nineteen contacts
    # were staged into EmailBison campaign 481, nine of them already in the
    # client's own campaigns, and nothing objected.
    #
    # THE CHECK IS ACCOUNT-LEVEL, USING `collision.check_account` AND
    # `collision.account_policy`. The account is the unit of outreach per
    # `ACCOUNT-OUTREACH.md`, and `account_policy` already draws the line
    # between what blocks and what is history. This does not invent a new
    # verdict; it applies the existing one at the staging boundary.
    #
    # CACHED PER DOMAIN. A campaign's leads typically span a small number of
    # domains, and each `check_account` costs one paginated provider search.
    # The cache lives for the duration of this call only.
    workspace_id = (report.get("workspace") or {}).get("id")
    if workspace_id:
        _refuse_colliding_leads(wanted, workspace_id,
                                already_on=_already_on_campaign(provider_id))
    # The variables must exist on the workspace before a lead may carry one:
    # the provider refuses an undeclared name outright. Idempotent, and it
    # creates nothing that can reach a person.
    bison.ensure_custom_variables()
    # THE KILLSWITCH IS CONSULTED BEFORE ANY LEAD IS CREATED OR ATTACHED.
    # `_ensure_leads` does not go through `providerwrites.perform` - it calls
    # `bison.create_lead` and `bison.attach_leads` directly - so the write
    # door's killswitch gate does not cover it. The workspace layer is the
    # meaningful control at staging time: `sending.live` is the tenant switch
    # that says whether this workspace's outreach is active. A workspace that
    # has never been switched on, or that has been switched off, must not have
    # leads created for it. The GLOBAL layer is excluded because it refuses
    # sending (which staging is not); the CAMPAIGN layer is excluded because
    # the canonical campaign is not RUNNING during staging and that is the
    # correct state for a campaign being built.
    from . import killswitch

    ws_state = killswitch.workspace_state(campaign.get("client"))
    if not ws_state["sending"]:
        raise FactoryRefused(
            f"the killswitch for workspace {campaign.get('client')!r} is off: "
            f"{ws_state['why']}. No leads were created or attached")
    before = bison.campaign_lead_count(provider_id)
    known = _known_lead_ids(campaign, wanted)
    ids, created, reconciled, refreshed = [], 0, 0, 0
    adopted = 0
    #: provider lead id -> the lead we staged, for the pre-attach check.
    _wanted_by_id = {}
    remember_pairs = []
    for lead in wanted:
        existing = known.get(lead["contact_key"])
        if existing:
            # THE COPY MAY HAVE CHANGED SINCE THIS LEAD WAS MADE. A
            # regenerated draft, a fresh approval, a corrected angle - all
            # change the words without changing who they go to, and a lead
            # created before that still holds the old ones. Reconciled rather
            # than assumed: the provider is asked what it has, and told only
            # what differs.
            #
            # STALE NUMBERED VARIABLES BEYOND THE SEQUENCE LENGTH ARE
            # CLEARED HERE. `_variables_for` names only the positions the
            # sequence reads; `_stale_clearances` adds explicit empties for
            # every numbered slot above that, so a lead that previously
            # carried a longer sequence has its out-of-range copy wiped.
            # Without this, subject_4/body_4/subject_5/body_5 from a five-
            # step era survive silently on a three-step campaign, and the
            # stale comparison never names them because they are not in the
            # wanted set.
            projected = plan.get("provider_sequence") or []
            wanted_vars = _variables_for(lead, campaign, sequence=projected)
            clearances = _stale_clearances(projected)
            all_wanted = wanted_vars + clearances
            held = bison.variables_of(bison.lead(existing))
            stale = [v for v in all_wanted
                     if held.get(v["name"]) != v["value"]]
            if stale:
                bison.update_lead(existing, {"custom_variables": stale})
                refreshed += 1
                report["did"].append(
                    f"refreshed {len(stale)} variable(s) on lead {existing}: "
                    f"{sorted(v['name'] for v in stale)}")
            ids.append(existing)
            _wanted_by_id[existing] = lead
            continue
        try:
            row = bison.create_lead({
                "email": lead["email"],
                "first_name": lead["first_name"],
                "last_name": lead["last_name"],
                # WHO THIS IS, IN THE PROVIDER'S OWN RECORD.
                # `adapters.from_emailbison` reads these back off an inbound
                # reply. Without them a reply arrives attached to an address
                # and to nothing else, and reply-stop cannot find the person
                # it is supposed to stop.
                "custom_variables": _variables_for(
                    lead, campaign,
                    sequence=plan.get("provider_sequence") or [])})
            created += 1
        except ProviderError as e:
            # ALREADY THERE, AND WE NEVER WROTE IT DOWN.
            # Creating it again is what the provider just refused, and
            # guessing an id would attach a stranger to this campaign. So the
            # address is looked up exactly, or this stops.
            #
            # THE LOOKUP WAITS, because the commonest way to get here is a
            # race this process just lost: two campaigns for the same client
            # staged at once, both needing the same person, one of them
            # creating the lead a fraction of a second earlier. The provider's
            # lead search is an index and the index is about a second behind,
            # so asking once meant the loser reported AMBIGUOUS and stopped -
            # measured 2026-09-13. Six tries over five seconds, and if it is
            # still not there this stops exactly as before: a lead that exists
            # and cannot be named must not be guessed at.
            if "already been taken" not in str(e):
                raise
            row = bison.find_lead_by_email(lead["email"], attempts=6,
                                           interval=1.0)
            if not row:
                raise FactoryAmbiguous(
                    f"EmailBison says {lead['email']} already exists but will "
                    f"not return it - its lead search lags behind creation. "
                    f"Wait and re-run; do NOT create a duplicate") from None
            # THE ADOPTED LEAD IS NOT OURS YET, AND THIS IS WHERE 73 BLANK
            # EMAILS CAME FROM.
            #
            # "already been taken" does NOT only mean we lost a race with
            # ourselves. It also means the address is already in the CLIENT'S
            # OWN ESTATE - and then this lookup returns THEIR lead, months
            # old, carrying THEIR custom variables (`headline`, `location`)
            # and none of ours. Until 2026-09-23 this branch took that id and
            # attached it, and the variables were never written: our sequence
            # is a template of merge fields, so `{BODY_1}` resolved against
            # nothing and the provider sent `<p></p>`.
            #
            # Measured: 90 of the 91 foreign leads in campaigns 491-498 are
            # recorded in our own store as `bison_lead_id` on our own
            # contacts, and 85 of them are `sequence_finished` members of the
            # client's campaign 352.
            # `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.
            #
            # So the copy is written HERE, before the lead can be attached,
            # and the `_verified` check below refuses if it did not land.
            bison.update_lead(row["id"], {"custom_variables": _variables_for(
                lead, campaign, sequence=plan.get("provider_sequence") or [])})
            adopted += 1
            reconciled += 1
        remember_pairs.append((lead, row["id"]))
        ids.append(row["id"])
        _wanted_by_id[row["id"]] = lead
    _remember_leads(remember_pairs)
    _refuse_unvariabled_leads(ids, _wanted_by_id, campaign, plan, report)
    # FRESH READ, NOT ASSUMED FROM `_ensure_stopped` FOUR CALLS AGO.
    # The invariant that makes lead attachment safe is "the campaign is
    # stopped at the provider". `_ensure_stopped` established that earlier,
    # but the campaign's provider status is read from the provider, not
    # assumed from local state, so it is re-confirmed here immediately
    # before the attach. A campaign that became active between the two
    # reads - resumed by hand in the provider UI, or by another process -
    # is caught here rather than discovered from a readback that agrees
    # with a send already in flight.
    #
    # SKIPPED WHEN `_ensure_stopped` DELIBERATELY LEFT THE CAMPAIGN RUNNING.
    # Re-staging a live campaign reconciles material but does not stop the
    # send - that is a deliberate design choice, not a race. The fresh read
    # is there to catch a STATUS CHANGE between the two calls, not a status
    # that was already active when `_ensure_stopped` saw it. The
    # `left_running` flag in the report records that `_ensure_stopped`
    # chose not to stop it, so the fresh read would be asking the wrong
    # question.
    if not report.get("provider", {}).get("left_running"):
        pre_attach_status = str(bison.campaign(provider_id).get("status") or
                                "").lower()
        if pre_attach_status in bison.STARTED_STATES or pre_attach_status in bison.STARTING_STATES:
            raise FactoryRefused(
                f"EmailBison campaign {provider_id} is {pre_attach_status} "
                f"and leads were about to be attached to a running campaign. "
                f"Refusing: a lead attached to an active campaign is acted "
                f"on immediately")
    outcome = bison.attach_leads(provider_id, ids)
    report["provider"]["attached"] = outcome
    # Counted, not just narrated. Which PATH found each lead matters: the
    # remembered id is authoritative, while reconciliation leans on a provider
    # search that lags behind creation. A run that quietly stopped using the
    # first and started relying on the second would still avoid duplicates -
    # and would be one indexing delay away from not avoiding them.
    report["provider"]["leads"] = {"created": created, "reused": len(known),
                                   "reconciled": reconciled,
                                   "refreshed": refreshed,
                                   # Adopted from an address that already
                                   # existed - usually the CLIENT's own
                                   # estate. Counted separately because it is
                                   # the path that crossed a lane.
                                   "adopted": adopted}
    report["did"].append(
        f"created {created} lead(s), reused {len(known)}, reconciled "
        f"{reconciled}; attached {len(outcome['attached'])}, "
        f"{len(outcome['already'])} already present, "
        f"{outcome['count']} in campaign now")
    # The SIZE before and after, not a list of members: the campaign lead
    # route serves fifteen rows however many the campaign holds, so a list
    # here was a page pretending to be a membership.
    report["provider"]["leads_before"] = before
    _refuse_blank_render(provider_id, report)


def _refuse_unvariabled_leads(ids, wanted_by_id, campaign, plan, report):
    """NEVER ATTACH A LEAD WHOSE COPY IS NOT ALREADY ON IT.

    OPERATOR DECISION 2026-09-23, the structural half of the incident fix.
    Set the variables first, READ THE LEAD BACK, and only then attach.

    WHY AN INVARIANT OVER ALL IDS AND NOT A FIX TO ONE BRANCH. The adoption
    branch is the one that did this, and fixing it there is necessary and not
    sufficient: `ids` is assembled from three paths - remembered, created,
    adopted - and the property that matters is about what goes on the wire,
    not about which branch put it there. A fourth path added later inherits
    this check instead of having to remember the lesson.

    IT READS THE PROVIDER. The write we are guarding against is one where our
    PATCH was accepted and did not take, and our own copy of what we sent
    cannot see that. The read is per lead touched this run, not per lead in
    the campaign: leads already carrying their copy from an earlier stage are
    not re-read, so a 300-lead re-stage does not pay 300 GETs to re-prove a
    property nothing changed.

    A REFUSAL HERE LEAVES LEADS CREATED AND UNATTACHED, which is the safe
    direction and is stated so nobody 'fixes' it: an unattached lead sends
    nothing to anybody, while an attached one is in a campaign's queue within
    the minute.
    """
    from . import emptyrender
    sequence = plan.get("provider_sequence") or []
    unverified = []
    for lead_id in ids:
        lead = wanted_by_id.get(lead_id)
        if lead is None:
            # Not staged by this run: it was already on the campaign and
            # nothing here changed it. Naming it rather than passing it
            # silently, because "we did not look" is not "it is fine".
            unverified.append((lead_id, "not staged by this run"))
            continue
        wanted = {v["name"]: v["value"]
                  for v in _variables_for(lead, campaign, sequence=sequence)}
        held = bison.variables_of(bison.lead(lead_id))
        for name, value in sorted(wanted.items()):
            if held.get(name) != value:
                unverified.append((lead_id, f"{name} did not take"))
                break
        else:
            # And the copy itself must be sendable, by the SAME predicate the
            # queue is judged by - not by a truthiness check, which is what
            # let `'None'` through.
            body = held.get("body_1") or held.get("body") or ""
            fault = emptyrender.classify_body(body)
            if fault:
                unverified.append((lead_id, f"body_1 is {fault}"))

    report.setdefault("provider", {})["leads_variable_verified"] = (
        len(ids) - len(unverified))
    if unverified:
        detail = "; ".join(f"lead {i}: {w}" for i, w in unverified[:5])
        raise FactoryRefused(
            f"{len(unverified)} of {len(ids)} lead(s) would be attached "
            f"without their copy on them: {detail}"
            f"{' and more' if len(unverified) > 5 else ''}. A lead attached "
            f"without `subject_1`/`body_1` renders the sequence template "
            f"against nothing and the provider SENDS the empty result - it "
            f"did so 76 times on 2026-09-22/23. Nothing was attached")


def _refuse_blank_render(provider_id, report):
    """Control (a): read back what the provider WILL SEND, and refuse a blank.

    OPERATOR DECISION 2026-09-23, the incident gate. Refuse any push where a
    step for any lead would send an empty, `"None"` or placeholder subject or
    body - verified by reading the provider's own rendered queue rather than
    by checking what we intended to send.
    `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.

    WHY THE RENDERED ROW AND NOT OUR OWN MATERIAL. Every other guard in this
    file inspects `wanted` - the leads we are staging - and each one of them
    passed while 76 blank emails went out, because 73 of those went to leads
    this factory never created and had no reason to look at. And the three
    that WERE ours carry correct copy to this day: they were patched up to 54
    minutes after the empty row had already been queued and sent, because the
    render is a snapshot and patching a lead does not rebuild it. There is
    exactly one object that answers "what will this person receive", and it
    is the queue row.

    IT REPORTS HOW MANY ROWS IT CHECKED, AND ZERO IS NOT A PASS.

    A campaign is paused while it is staged, and the provider may not have
    built the queue yet - so this can legitimately find nothing to look at.
    That is a different fact from "every row is fine", and conflating the two
    is how a guard becomes ceremony: it would report clean on every push, for
    ever, and nobody would know. So `blank_render_checked` carries the row
    count and `blank_render_verified` is False when it is zero. The live
    window is covered by the watcher check, which is control (b) and is not
    optional precisely because this one can come up empty.
    """
    from . import emptyrender
    try:
        rows = bison.scheduled_emails(
            provider_id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP) or []
    except Exception as exc:                                  # noqa: BLE001
        # A queue that cannot be read is not a queue that is fine. Refusing
        # costs a re-run; assuming costs an empty email.
        raise FactoryRefused(
            f"the rendered queue for EmailBison campaign {provider_id} could "
            f"not be read ({type(exc).__name__}: {str(exc)[:160]}), so what "
            f"it would send cannot be verified. Refusing the push: an "
            f"unreadable queue is the state the blank-email incident was "
            f"invisible in") from None

    found = emptyrender.scan(rows)
    provider = report.setdefault("provider", {})
    provider["blank_render_checked"] = len(rows)
    provider["blank_render_verified"] = bool(rows)
    offending = found["pending"] + found["already"]
    if not offending:
        report.setdefault("did", []).append(
            f"read back {len(rows)} rendered queue row(s): none empty"
            if rows else
            "rendered queue is EMPTY - nothing was verified, and the watcher "
            "check is what covers this campaign once the provider builds it")
        return

    reasons = sorted({f"{f}/{r}" for e in offending for f, r in e["faults"]})
    steps = sorted({str(e["step"]) for e in offending if e.get("step")})
    raise FactoryRefused(
        f"{len(offending)} of {len(rows)} rendered queue row(s) on EmailBison "
        f"campaign {provider_id} would send nothing a person can read - "
        f"steps {','.join(steps) or '?'}, {', '.join(reasons)} "
        f"({len(found['pending'])} still sendable). This is read from the "
        f"PROVIDER's own rendered queue, not from our material, and it is the "
        f"check that 76 blank emails got past on 2026-09-22/23. Fix the "
        f"lead variables and re-stage; do not activate this campaign")


def _ensure_stopped(provider_id, report, by="system"):
    """Stop the campaign BEFORE it holds anybody. Do not stop a running one.

    A campaign this factory builds must not be able to send, so it is paused -
    that part is unchanged, and the factory still never STARTS anything. What
    changed is when: the pause now happens before the leads are attached, and
    `stage` says why.

    What it must not do is pause a campaign that is ALREADY LIVE. Re-staging
    is routine: it reconciles copy, limits and membership, and it is run again
    whenever a draft changes. Pausing unconditionally meant a routine re-stage
    silently stopped a running campaign - measured on 2026-09-13, when the
    duplicate-refusal check re-staged the authorised canary and suspended the
    send it had just committed. Nothing raised, because pausing looks like the
    safe direction.

    Stopping a live campaign is a decision somebody takes on purpose, through
    `orchestrator.pause`, which records who and why. It is not a side effect
    of reconciling a draft.

    AND "NOT DRAFT OR PAUSED" IS NOT THE SAME AS "RUNNING". That test reported
    a campaign the provider had marked `failed` as LEFT RUNNING - an operator
    reading that line would believe a dead campaign was sending. The statuses
    this instance actually uses are enumerated in `bison`, so they are
    classified here rather than divided into one name and everything else.
    """
    status = str(bison.campaign(provider_id).get("status") or "").lower()
    if status in bison.STARTED_STATES or status in bison.STARTING_STATES:
        report["did"].append(
            f"campaign is {status} and was LEFT RUNNING: re-staging "
            f"reconciles material, it does not stop a live campaign. Use "
            f"orchestrator.pause to stop it")
        report["provider"]["left_running"] = True
        return
    if status in bison.FAILED_STATES:
        # It is not sending and it is not a campaign this factory built into
        # shape either. Pausing it below is honest - it cannot send afterwards
        # and it could not before - but the reason it is here has to survive
        # into the report, because `failed` means the provider refused to
        # start it and a staged-looking readback would hide that.
        report["provider"]["provider_failed"] = True
        report["did"].append(
            f"campaign reads {status}: the provider tried to start it and "
            f"gave up. It is NOT sending")
    state = bison.pause_campaign(provider_id)
    report["did"].append(f"campaign left {state['status']}")


def _readback(provider_id):
    """What the provider says is true, after everything above."""
    row = bison.campaign(provider_id)
    return {"id": row.get("id"), "name": row.get("name"),
            "status": row.get("status"),
            "leads": bison.campaign_lead_count(provider_id)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaign", help="a canonical campaign id")
    parser.add_argument("--live", action="store_true",
                        help="actually write to EmailBison")
    args = parser.parse_args(argv)
    try:
        report = stage(args.campaign, live=args.live)
    except (FactoryRefused, FactoryAmbiguous, ProviderError) as e:
        print(f"{type(e).__name__}: {e}")
        return 1
    for line in report["did"]:
        print(" ", line)
    print(" provider:", report["provider"].get("readback"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
