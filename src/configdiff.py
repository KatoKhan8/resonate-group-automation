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

3. `UNVERIFIABLE` is a FAILURE for any required field, not a warning. HeyReach
   exposes no route for a campaign's lead identities and no campaign limit
   field, so those are structurally unverifiable there - and a campaign whose
   lead set cannot be read is a campaign that cannot be proven to hold one
   person. The honest consequence is that HeyReach staging is capped at one
   lead until those routes are allowlisted, where `totalUsers == 1` plus a
   verified list id IS the lead set. `REQUIRED` per channel says so explicitly.

4. Nothing here writes, to state or to a provider. It reads canonical state and
   read-only provider routes. A differ that could edit either side to make them
   agree would be worse than no differ.
"""
import json
import sys

from . import campaigns as campaigns_state
from . import approval, cadence, clients, store
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
    "list_id", "lead_count", "actions", "note", "delays", "linkedin_only",
    "bison_handoff",
)

REQUIRED_BISON = (
    "campaign_id", "campaign_name", "status", "workspace", "sender_ids",
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
    """A comparable set of provider ids, as strings."""
    out = set()
    for value in values or ():
        if isinstance(value, dict):
            value = value.get("id")
        if value in (None, ""):
            continue
        out.add(str(value).strip())
    return frozenset(out)


# ------------------------------------------------------- APPROVED, HeyReach

def approved_heyreach(campaign, recs=None, config=None):
    """What canonical state says this LinkedIn campaign should be.

    `campaign` is a canonical campaign row - the binding of a
    provider campaign to records, senders and limits. The copy comes from the
    per-contact cadence step, so a template change moves the approved note and
    the diff fails until somebody re-approves, which is the point.
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

    leads, notes, actions = set(), [], []
    for rec in rows:
        for contact in rec.get("contacts") or ():
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

    if not notes:
        raise DiffRefused(
            "no APPROVED and renderable LinkedIn step on any of this "
            "campaign's records; an unapproved step is not an approved config")
    if len(set(notes)) > 1:
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
        "actions": ("CONNECTION_REQUEST", "END"),
        "note": notes[0],
        "delays": tuple(delays),
        "linkedin_only": True,
        "bison_handoff": False,
        "daily_limit": (campaign.get("daily_volume") or {}).get("linkedin"),
    }


LINKEDIN_STEP = {"key": "day3", "day": 3, "channel": "linkedin",
                 "template": "linkedin_intro"}


# ------------------------------------------------------- PROVIDER, HeyReach

def provider_heyreach(campaign_id):
    """What HeyReach actually holds. Read-only routes only.

    Two fields come back `UNVERIFIABLE` because no allowlisted route exposes
    them: the lead IDENTITIES (only a count is published, in `progressStats`)
    and any per-campaign daily limit (no such field exists on the campaign
    object). They are reported as unverifiable rather than guessed, and
    `REQUIRED_HEYREACH` deliberately omits `lead_set` and `daily_limit` so a
    ONE-lead campaign can still pass on `lead_count` - see the module docstring.
    """
    row = heyreach.campaign_by_id(campaign_id)
    if not row:
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
        "lead_set": UNVERIFIABLE,
        "lead_count": int(stats.get("totalUsers") or 0) if stats else UNVERIFIABLE,
        "actions": tuple(order),
        "note": _norm_text(notes[0]) if notes else "",
        "delays": delays,
        "linkedin_only": bool(only),
        "bison_handoff": any("EmailBison" in h or "onward" in h for h in hazards),
        "daily_limit": UNVERIFIABLE,
        "_hazards": hazards,
    }


# ------------------------------------------------------- APPROVED, EmailBison

def approved_bison(campaign, recs=None, config=None):
    """What canonical state says this email campaign should be."""
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

    leads, subjects, bodies, delays, actions = set(), [], [], [], []
    for rec in rows:
        for contact in rec.get("contacts") or ():
            address = (contact.get("email") or "").strip().lower()
            if not address:
                continue
            leads.add(address)
            for spec in cadence.STEPS:
                if spec.get("channel") != "email":
                    continue
                step = cadence.expand_step(rec, contact, spec, config)
                if not step:
                    continue
                actions.append(spec["key"])
                subjects.append(_norm_text(step.get("subject")))
                bodies.append(_norm_text(step.get("body")))
                delays.append(int(spec.get("day") or 0))
    if not leads:
        raise DiffRefused("no emailable contact on any approved record")

    volume = (campaign.get("daily_volume") or {}).get("email")
    return {
        "campaign_id": str(cid),
        "campaign_name": campaign.get("name"),
        "status": campaign.get("provider_status_expected") or "paused",
        "workspace": str(campaign.get("workspace") or ""),
        "sender_ids": _ids((campaign.get("senders") or {}).get("email")),
        "lead_set": frozenset(leads),
        "lead_count": len(leads),
        "actions": tuple(actions),
        "subjects": tuple(subjects),
        "bodies": tuple(bodies),
        "delays": tuple(delays),
        "max_emails_per_day": volume,
        "max_new_leads_per_day": volume,
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
    steps.sort(key=lambda s: int(s.get("order") or 0))
    live = [s for s in steps if s.get("active")]

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
        "subjects": tuple(_norm_text(s.get("email_subject")) for s in live),
        "bodies": tuple(_norm_text(s.get("email_body")) for s in live),
        "delays": tuple(int(s.get("wait_in_days") or 0) for s in live),
        "max_emails_per_day": row.get("max_emails_per_day"),
        "max_new_leads_per_day": row.get("max_new_leads_per_day"),
        "_per_domain_cap": row.get("daily_max_sends_per_receiving_domain"),
        "_bounced": row.get("bounced"),
        "_emails_sent": row.get("emails_sent"),
    }


# ---------------------------------------------------------------- the diff

def diff(approved, provider, required=()):
    """Per-field verdicts over the UNION of both sides' keys, and PASS/FAIL.

    The union rather than `approved`'s keys, because the dangerous field is the
    one nobody approved: a second sender, an extra sequence node, a lead that
    should not be there. Those are `UNEXPECTED` and they fail.

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


def compare_heyreach(campaign, recs=None, config=None):
    """`(diff, approved, provider)` for one LinkedIn campaign."""
    approved = approved_heyreach(campaign, recs, config)
    provider = provider_heyreach(approved["campaign_id"])
    return diff(approved, provider, REQUIRED_HEYREACH), approved, provider


def compare_bison(campaign, recs=None, config=None, expect_workspace=None):
    """`(diff, approved, provider)` for one email campaign."""
    approved = approved_bison(campaign, recs, config)
    provider = provider_bison(approved["campaign_id"],
                              expect_workspace=expect_workspace)
    return diff(approved, provider, REQUIRED_BISON), approved, provider


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
        if a.channel == "linkedin":
            result, approved, provider = compare_heyreach(campaign)
        else:
            result, approved, provider = compare_bison(
                campaign, expect_workspace=a.workspace)
    except DiffRefused as e:
        print(f"REFUSED: {e}")
        return 2
    print(json.dumps(result, indent=1, default=_show) if a.json
          else report(result, approved, provider))
    return 0 if result["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
