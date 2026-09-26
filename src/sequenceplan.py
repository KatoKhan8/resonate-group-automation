"""The single truth for a generated campaign sequence.

Preview, the XLSX workbook, the approval hash, the EmailBison payload and the
HeyReach payload are projections of this plan. Each derives from it; none
re-implements it. If a projection needs a field the plan does not carry, the
field belongs in the plan.

TASK-369.
"""
import hashlib
import json

ENTRYPOINT_VERSION = "1"


def new(client_name, account, contacts, *, strategy=None, second_brain_facts=None,
        offers=None, cadence=None):
    """Build an empty SequencePlan skeleton.

    The caller fills per-contact sequences as generation proceeds. The
    top-level fields (client, account, strategy, facts, offers) are set once;
    the per-contact entries are the variable part.
    """
    return {
        "version": ENTRYPOINT_VERSION,
        "client": client_name,
        "account": {
            "company": account.get("company", ""),
            "domain": account.get("domain", ""),
        },
        "strategy": strategy or {},
        "second_brain_facts": second_brain_facts or [],
        "offers": offers or {},
        "cadence": cadence or {},
        "contacts": contacts if isinstance(contacts, list) else [],
    }


def approval_hash(plan):
    """A stable digest of everything the operator approved.

    Used by the execution guard to detect drift between what was approved and
    what the provider payload carries. Two plans with the same approval hash
    produce the same prospect-facing copy.
    """
    material = {
        "client": plan.get("client"),
        "account": plan.get("account"),
        "strategy_id": (plan.get("strategy") or {}).get("strategy_id"),
        "contacts": [],
    }
    for contact in plan.get("contacts") or []:
        material["contacts"].append({
            "email": contact.get("email"),
            "sequences": contact.get("sequences") or {},
            "subjects": contact.get("subjects") or {},
        })
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def derive_preview_data(plan):
    """Extract the fields the preview page needs from the plan.

    Returns a dict shaped for `preview.gather`-like consumption. Every value
    is read from the plan; nothing is recomputed.
    """
    rows = []
    for contact in plan.get("contacts") or []:
        rows.append({
            "contact_key": contact.get("contact_key"),
            "email": contact.get("email"),
            "first_name": contact.get("first_name", ""),
            "company": plan.get("account", {}).get("company", ""),
            "qualification": contact.get("qualification"),
            "hypothesis": (contact.get("hypothesis") or {}).get("hypothesis"),
            "capability": (contact.get("match") or {}).get("capability_key"),
            "sequences": contact.get("sequences") or {},
            "subjects": contact.get("subjects") or {},
            "gate": contact.get("sequence_gate") or {},
        })
    return {
        "client": plan.get("client"),
        "account": plan.get("account"),
        "strategy": plan.get("strategy"),
        "rows": rows,
        "approval_hash": approval_hash(plan),
    }


def derive_bison_payload(plan):
    """Extract the EmailBison custom-variable payload from the plan.

    Each lead gets per-step subject and body merge fields. The sequence
    template is set at the campaign level.
    """
    leads = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        steps = []
        sequences = contact.get("sequences") or {}
        subjects = contact.get("subjects") or {}
        for key in ("em1", "em2", "em3", "em4", "em5"):
            body = sequences.get(key)
            if not body:
                continue
            subject_key = {"em1": "A", "em3": "B", "em5": "C"}.get(key, "")
            steps.append({
                "step_key": key,
                "subject": subjects.get(subject_key, ""),
                "body": body,
            })
        if steps:
            leads.append({
                "contact_key": contact.get("contact_key"),
                "email": contact.get("email"),
                "first_name": contact.get("first_name", ""),
                "steps": steps,
            })
    return {"leads": leads, "approval_hash": approval_hash(plan)}


def derive_heyreach_payload(plan):
    """Extract the HeyReach LinkedIn graph payload from the plan.

    Maps the cadence step keys (em1..em5, connect, msg1..msg3) to the graph
    roles HeyReach expects: connection_note, connected_1..4, message_2..4.
    """
    leads = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        sequences = contact.get("sequences") or {}
        li = {}
        for key in ("connect", "msg1", "msg2", "msg3"):
            text = sequences.get(key)
            if text:
                li[key] = text
        if li:
            leads.append({
                "contact_key": contact.get("contact_key"),
                "linkedin": li,
            })
    return {"leads": leads, "approval_hash": approval_hash(plan)}
