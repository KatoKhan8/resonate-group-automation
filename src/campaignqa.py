#!/usr/bin/env python3
"""What a reviewer needs to know before approving an account-based campaign.

## Why this is separate from `src/qa.py`

`qa.py` checks the *drafts*: lint, length, placeholders, banned phrases, one
message at a time. That is still right and unchanged.

This checks the *plan*: the cadence graph, the senders in it, the decision
makers it targets, the claims it may make, and the pacing it implies. None of
that is visible from any single message, and all of it is what goes wrong
when four correct sequences share an account.

## Structure, safety, pacing, claims

Four groups, and the reason for the split is what a reviewer does about each:

  STRUCTURE   the cadence cannot run - fix the graph
  SAFETY      it could run and should not - fix the team, the roles, the
              provider capability
  PACING      it would reach people too often - fix the limits or the plan
  CLAIMS      a message could reference something unsupported - fix the
              policy or accept that the reference is unavailable

## Blocking is a policy decision, not a severity

A finding is `block` when proceeding would do something this system exists to
prevent: a fabricated reference, a sender nobody authorised, a provider action
nothing has validated. Everything else warns, because a reviewer who is
blocked on things that are merely untidy learns to override blocks.
"""
from . import account, cadencegraph, fatigue, lint, variants
from . import outreachclaims as oc
from . import senderteam

STRUCTURE = "structure"
SAFETY = "safety"
PACING = "pacing"
CLAIMS = "claims"
GROUPS = (STRUCTURE, SAFETY, PACING, CLAIMS)

GROUP_LABEL = {
    STRUCTURE: "Cadence structure",
    SAFETY: "Outreach safety",
    PACING: "Contact and account pacing",
    CLAIMS: "What messages may claim",
}

BLOCK = "block"
WARN = "warn"
OK = "ok"


def _finding(group, level, why, where=None, fix=None):
    return {"group": group, "level": level, "why": why, "where": where,
            "fix": fix}


def review(repo, campaign, graph=None, recs=None, config=None, rows=None):
    """Every plan-level problem with this campaign, grouped and explained.

    Reads rather than mutates. A reviewer sees the same list the approval
    gate uses, which is the point: a check that only runs at approval is a
    check somebody discovers at approval.
    """
    from . import senderidentity as si

    config = config if config is not None else repo.config()
    rows = si.load() if rows is None else rows
    recs = recs if recs is not None else [
        r for r in repo.records()
        if r["id"] in (campaign.get("record_ids") or [])]

    team = senderteam.team_for(repo.workspace, campaign.get("campaign_id"),
                               rows=rows)
    graph = graph or campaign.get("cadence_graph")

    findings = []
    findings += _structure(graph, team, config)
    findings += _variants(graph, config, recs)
    findings += _safety(graph, team, repo.workspace, rows)
    findings += _pacing(recs, config)
    findings += _claims(recs, graph, repo.workspace, config, rows)

    blocking = [f for f in findings if f["level"] == BLOCK]
    return {
        "campaign_id": campaign.get("campaign_id"),
        "findings": findings,
        "by_group": {group: [f for f in findings if f["group"] == group]
                     for group in GROUPS},
        "blocking": blocking,
        "state": BLOCK if blocking else (WARN if findings else OK),
        "team": senderteam.describe(team, repo.workspace, rows),
        "graph": cadencegraph.describe(graph) if graph else None,
        "records": len(recs),
    }


def _structure(graph, team, config):
    if not graph:
        return [_finding(STRUCTURE, WARN,
                         "This campaign has no cadence graph; it runs the "
                         "legacy linear cadence.",
                         fix="Build one on the cadence screen.")]
    # No team passed, and unvalidated nodes filtered out: `_safety` reports
    # both, with a `fix` this cannot give. A reviewer reading the same
    # violation twice under two headings learns to skim, which is the
    # opposite of what a QA list is for.
    out = []
    for finding in cadencegraph.validate(graph, None, config):
        if "outreach team" in finding["why"]:
            continue
        if "capability nothing here has validated" in finding["why"]:
            continue
        out.append(_finding(
            STRUCTURE,
            BLOCK if finding["level"] == "block" else WARN,
            finding["why"], finding.get("node")))
    return out


def _variants(graph, config, recs=None):
    """Every active variant, checked on its own.

    The failure this exists to prevent: a campaign passing review because
    variant A is clean while variant D says something nothing supports.
    Four of five safe is not safe - a fifth of the audience receives the
    fifth one.

    Structure first (`variants.validate`), then the copy itself through the
    same lint the single-copy path has always used. Claim safety is not
    here: a claim resolves against a *contact*, so it is checked when the
    message is prepared, and `_claims` below reports the shape of it.
    """
    out = []
    if not graph:
        return out
    # One representative record and contact, purely so lint has the shape it
    # expects. Nothing about this contact is asserted; the recipient codes
    # are filtered out below precisely because they would be.
    sample = next((r for r in (recs or []) if r.get("contacts")), None)
    if sample is None:
        return out
    sample_key = (sample["contacts"][0] or {}).get("key")

    for node in sorted((graph.get("nodes") or {}).values(),
                       key=lambda n: str(n.get("key"))):
        for finding in variants.validate(node):
            out.append(_finding(
                STRUCTURE,
                BLOCK if finding["level"] == "block" else WARN,
                f"{node.get('label') or node['key']}: {finding['why']}",
                node["key"],
                "Open the step and edit its variants."))

        entries = variants.experiment_of(node)
        if not entries:
            if variants.is_message_node(node):
                out.append(_finding(
                    STRUCTURE, WARN,
                    f"{node.get('label') or node['key']} has no copy "
                    f"experiment; it will send one version to everybody.",
                    node["key"],
                    f"Add {variants.MINIMUM_VARIANTS} variants on the "
                    f"cadence screen."))
            continue

        for entry in entries:
            for reason in _lint_variant(node, entry, sample, sample_key):
                out.append(_finding(
                    SAFETY, BLOCK,
                    f"{node.get('label') or node['key']}, variant "
                    f"{entry['variant_id']} ({entry.get('style')}): {reason}",
                    node["key"],
                    "Rewrite this variant. Do not widen the rule."))
    return out


# Failures that are about the *record or the recipient*, not about the copy.
#
# A variant is copy. Whether a particular mailbox cleared verification, or
# whether a contact has an angle selected, is asked again per contact at
# send time - reporting either here would put a red mark on a well-written
# variant because somebody in the audience is missing a field.
_NOT_ABOUT_THE_COPY = frozenset({
    "recipient_not_on_record", "recipient_missing", "recipient_not_sendable",
    "no_linkedin_profile", "profile_missing",
    "domains_contact_no_angle",
})


def _lint_variant(node, entry, rec, contact_key):
    """What the shared lint says about this one variant's copy.

    Run through `lint.check_step`, which is the single door every step goes
    through - a second implementation here is a second place that can
    disagree about what a well-formed message is. The recipient codes are
    dropped because they are not facts about the variant.
    """
    channel = cadencegraph.NODE[node["type"]]["channel"]
    step = {"channel": channel, **variants.content_of(entry)}
    try:
        failures = lint.check_step(rec, contact_key, step)
    except Exception as e:                                  # noqa: BLE001
        return [f"lint could not read it: {type(e).__name__}"]
    return sorted(set(failures or ()) - _NOT_ABOUT_THE_COPY)


def _safety(graph, team, workspace, rows):
    out = []
    if not graph:
        return out

    # A provider action nothing has validated must not be planned as though
    # it were supported. Reported once, here, because this is the copy that
    # tells a reviewer what to do about it.
    for node in graph["nodes"].values():
        if node["type"] in cadencegraph.UNVALIDATED:
            out.append(_finding(
                SAFETY, BLOCK,
                f"{cadencegraph.NODE[node['type']]['label']} uses a provider "
                f"capability nothing in this build has validated.",
                node["key"],
                "Remove the step, or validate the capability first - see "
                "LIVE-VALIDATION-PLAN.md."))

    # Every human in the graph must be on the authorised team. One finding
    # per offending human rather than per node: eight identical rows about
    # one person is a list nobody reads.
    seen = set()
    for offender in senderteam.validate_against(graph, team, workspace, rows):
        if offender["sender_id"] in seen:
            continue
        seen.add(offender["sender_id"])
        out.append(_finding(SAFETY, BLOCK, offender["why"],
                            offender["node"],
                            "Add them to the outreach team, or use somebody "
                            "who is on it."))

    # A step that contacts somebody must say who it is for.
    for node in cadencegraph.steps_of(graph):
        if not node.get("contact_role"):
            out.append(_finding(
                SAFETY, BLOCK,
                f"{node.get('label')} does not say which decision maker it "
                f"is for.", node["key"],
                "Set the step's target role."))

    # A cadence that never checks for a reply keeps sending after somebody
    # answers. The engine pauses on reply regardless, but a plan that does
    # not contemplate it is a plan nobody has thought through.
    conditions = {n.get("condition") for n in graph["nodes"].values()}
    if not conditions & {"replied", "no_reply", "positive_reply"}:
        out.append(_finding(
            SAFETY, WARN,
            "No step in this cadence branches on whether the contact "
            "replied.",
            fix="Add a reply check, so the sequence stops on its own rather "
                "than relying on the engine's pause."))
    return out


def _pacing(recs, config):
    """Contact and account pacing, checked against real records."""
    out = []
    limits = fatigue.limits(config)
    worst_contact, worst_account = None, None
    for rec in recs:
        company = fatigue.account_check(rec, config=config)
        if company["state"] == fatigue.BLOCK:
            worst_account = worst_account or (rec, company)
        for contact in account.contacts_of(rec):
            verdict = fatigue.contact_check(rec, contact.get("key"),
                                            config=config)
            if verdict["state"] == fatigue.BLOCK:
                worst_contact = worst_contact or (rec, contact, verdict)

    if worst_contact:
        rec, contact, verdict = worst_contact
        out.append(_finding(
            PACING, BLOCK,
            f"{contact.get('name') or contact.get('key')} at "
            f"{rec.get('company')} is already past a pacing limit: "
            + "; ".join(f["why"] for f in verdict["findings"]),
            fix="Raise the limit deliberately, or space the sequence."))
    if worst_account:
        rec, company = worst_account
        out.append(_finding(
            PACING, BLOCK,
            f"{rec.get('company')} is past an account pacing limit: "
            + "; ".join(f["why"] for f in company["findings"]),
            fix="Reduce the decision makers worked at once, or raise the "
                "limit deliberately."))

    unconfigured = [entry for entry in limits.values()
                    if not entry["configured"]]
    if len(unconfigured) == len(limits):
        out.append(_finding(
            PACING, WARN,
            "No pacing limit has been configured for this workspace; the "
            "defaults are in force.",
            fix="Set them on the settings screen so they are a decision "
                "rather than a default."))
    return out


# How many companies the claim scan reads. Capped because the check is
# per contact per claim type and a campaign can hold tens of thousands;
# stated on the finding, because a cap nobody is told about turns a
# sample into a false all-clear.
CLAIM_SCAN_CAP = 200


def _claims(recs, graph, workspace, config, rows):
    """Whether the cadence's cross-channel handoffs could be supported.

    A handoff node says "carry the reference across". Whether any reference
    is *available* depends on the account, so this reports the shape of the
    problem rather than pretending to resolve it per contact - and it names
    the one case that is always wrong.
    """
    out = []
    if not graph:
        return out

    handoffs = [n for n in graph["nodes"].values()
                if n["type"] in ("handoff", "dm_handoff")]
    if handoffs:
        enabled = [claim for claim in oc.TYPES
                   if oc.allowed_by_policy(claim, config)[0]]
        if not enabled:
            out.append(_finding(
                CLAIMS, WARN,
                "This cadence has a handoff step, but every account-aware "
                "reference is switched off, so the handoff will carry no "
                "context.",
                handoffs[0]["key"],
                "Enable a reference type, or replace the handoff with a "
                "standalone step."))

    # The one thing that is always wrong: a message referencing a touch that
    # has not been confirmed. Reported per record so a reviewer sees scale.
    #
    # The scan is capped, and the cap is *stated* below. A safety check
    # that inspects two hundred of thirty thousand and reports like it
    # read the campaign is the worst kind of green: the reviewer cannot
    # tell "nothing is wrong" from "nothing was looked at".
    unsupported = 0
    inspected = min(len(recs), CLAIM_SCAN_CAP)
    for rec in recs[:CLAIM_SCAN_CAP]:
        for contact in account.contacts_of(rec):
            senders = (contact.get("sender_assignment") or {})
            sender_id = ((senders.get("email") or {}).get("sender_id")
                         or (senders.get("linkedin") or {}).get("sender_id"))
            for claim in oc.available(rec, contact.get("key"), workspace,
                                      sender_id, config, rows):
                if claim["allowed"] and not claim["evidence"]:
                    unsupported += 1
    if unsupported:
        out.append(_finding(
            CLAIMS, BLOCK,
            f"{unsupported} claim(s) resolved as allowed with no evidence "
            f"attached. This should be impossible; treat it as a bug.",
            fix="Do not approve. Report it."))
    elif len(recs) > inspected:
        # Said even when nothing was found, because that is precisely when
        # the reader would otherwise assume the whole campaign was read.
        out.append(_finding(
            CLAIMS, WARN,
            f"Claim evidence was checked on {inspected} of {len(recs)} "
            f"companies, not all of them.",
            fix="Nothing was found in what was checked. Treat the rest as "
                "unchecked rather than clean."))
    return out
