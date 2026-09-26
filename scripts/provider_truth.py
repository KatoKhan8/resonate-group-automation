#!/usr/bin/env python3
"""Ask the providers what exists, and write the answer down where it survives.

## Why this exists

On 2026-09-15 the operator could not see the expected campaigns in the
HeyReach dashboard and asked whether they had ever been created. Nothing in
this repository could answer that, because every local artefact - a passing
dry run, a generated sequence, an adapter test, a "write passed" line in a
handoff - describes an INTENTION. None of them is evidence that a campaign
exists.

So this script asks the provider and writes the answer to
`docs/state/PROVIDER-CAMPAIGNS.json`, which is committed. A fresh session on
another machine reads that file and knows what is real.

READ-ONLY. It performs no writes, and it must stay that way: the whole point
is a report you can trust to be free of side effects.

## What counts as truth

A campaign is real when the provider returns it by id. Everything else -
including our own `work/campaigns.jsonl` - is an internal claim, and the
INTERNAL vs PROVIDER comparison in the output is there precisely so a claim
that has drifted from reality shows up as a defect rather than as agreement.

## Secrets

Credentials are read from the environment by the provider modules. Only the
NAMES of the variables appear here, never a value, and nothing this script
writes carries a key, a token or an unhashed prospect identifier.
"""

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import bison, heyreach, load_env, request  # noqa: E402
from src.providers import ProviderError  # noqa: E402

OUT = os.path.join(ROOT, "docs", "state", "PROVIDER-CAMPAIGNS.json")

# A campaign this system created. Everything older belongs to the client's
# pre-Resonate history and is reported but never claimed.
RESONATE_PREFIXES = ("RESONATE",)


def owned_by_resonate(name, provider_id, claimed_ids):
    """Ours, or not - and the name prefix is a FALLBACK, never the source.

    Operator decision, 2026-09-26 evening. `work/campaigns.jsonl` - what our
    own factory recorded creating - is the source of truth; the RESONATE name
    prefix only covers a campaign our factory made but never registered, or
    (measured, 2026-09-26) a campaign the client's own naming used the prefix
    for by coincidence. It cuts both ways: EmailBison 503/504/505 carry no
    RESONATE prefix at all and are ours anyway (`campaigns.jsonl` already had
    them, from the 09-25 factory run) - a prefix-only test called them
    client-or-other and was wrong. `claimed_ids` is the set of provider ids
    (as ints) `internal_claims()` already found in `campaigns.jsonl` for this
    provider.
    """
    try:
        if int(provider_id) in claimed_ids:
            return True
    except (TypeError, ValueError):
        pass
    return (name or "").upper().startswith(RESONATE_PREFIXES)


def short_hash(value):
    """Stable, non-reversible. Used so a tracked file can say "the same sender
    as last time" without carrying a real person's name."""
    import hashlib
    v = " ".join(str(value or "").split()).lower()
    if not v:
        return None
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]


def all_campaigns(base, hdr):
    out, off, total = [], 0, None
    while True:
        st, data = request("POST", base + "/campaign/GetAll", hdr,
                           {"offset": off, "limit": 100})
        if st != 200:
            raise RuntimeError("GetAll failed: %s %s" % (st, str(data)[:200]))
        items = data.get("items") or []
        out.extend(items)
        total = data.get("totalCount")
        off += len(items)
        if not items or off >= (total or 0):
            break
    return out, total


def sequence_shape(campaign_id):
    """Node count and message count, via the tree walker. A flat `steps` list
    does not exist on this provider - the sequence is a branching graph and
    reading it as a list silently reports zero."""
    try:
        seq = heyreach.campaign_sequence(campaign_id)
    except Exception as exc:
        return {"readable": False, "error": str(exc)[:200]}
    if not seq:
        return {"readable": False, "error": "empty sequence"}
    # walk_sequence returns (nodes, types, truncated) - NOT a list of paths.
    # Reading it as paths unpacks the tuple and silently reports "3", which is
    # the length of the tuple rather than anything about the campaign.
    nodes, types, truncated = heyreach.walk_sequence(seq)
    kinds, copies, variants = {}, 0, {}
    for n in nodes:
        k = n.get("nodeType") or "?"
        kinds[k] = kinds.get(k, 0) + 1
        # The copy lives in `payload.messages` and NOWHERE else. `message`,
        # `note`, `text` and `body` do not exist on this provider's graph, and
        # reading them returns a confident zero that looks like "no copy" -
        # which is how a campaign full of text reports as empty. The repo
        # documents this at heyreach.connection_notes; it caught me once here.
        payload = n.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        msgs = payload.get("messages")
        msgs = msgs if isinstance(msgs, list) else []
        if msgs:
            copies += 1
            # Per-node arm count: this is the "variants/messages per node"
            # the operator asked for.
            variants[k] = variants.get(k, [])
            variants[k].append(len(msgs))
    return {
        "readable": True,
        # True means a branch could not be followed, so the graph is not
        # fully proven and no clearance may be claimed from it.
        "truncated": truncated,
        "unique_nodes": len(nodes),
        "node_types": kinds,
        "distinct_types": sorted(types),
        "nodes_carrying_copy": copies,
        "messages_per_node_by_type": variants,
        "sequence_hash": heyreach_sequence_hash(seq),
    }


def heyreach_sequence_hash(seq):
    """Identity of the exact graph, so a later readback can prove it did not
    move without diffing the whole tree."""
    import hashlib
    blob = json.dumps(seq, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def internal_claims():
    """What THIS repository believes. Deliberately separate from provider
    truth so the two can disagree visibly."""
    path = os.path.join(ROOT, "work", "campaigns.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows.append({
                "client": r.get("client"),
                "status": r.get("status"),
                # Normalised: this field has been seen as both int and str,
                # which is itself a defect worth surfacing.
                "heyreach_campaign_id": (str(r["heyreach_campaign_id"])
                                         if r.get("heyreach_campaign_id") else None),
                "bison_campaign_id": (str(r["bison_campaign_id"])
                                      if r.get("bison_campaign_id") else None),
            })
    return rows


def classify(c):
    """CREATED_AND_VERIFIED / CREATED_BUT_INCOMPLETE / DRAFT / LIVE / MISSING."""
    status = (c.get("status") or "").upper()
    leads = (c.get("progressStats") or {}).get("totalUsers", 0)
    seq = c.get("sequence") or {}
    if status in ("IN_PROGRESS",):
        return "LIVE"
    if not seq.get("readable") or seq.get("unique_nodes", 0) == 0:
        return "CREATED_BUT_INCOMPLETE"
    if status == "DRAFT" and leads == 0:
        # A sequence that reads back but has nobody in it. Real, and not able
        # to send. This is the honest label for 599020.
        return "DRAFT"
    if status == "DRAFT":
        return "CREATED_AND_VERIFIED"
    return status or "UNKNOWN"


def read_emailbison_campaigns(claimed_bison_ids=frozenset()):
    """Every EmailBison campaign, with lead counts from meta.total.

    READ-ONLY. No POST, PATCH, PUT or DELETE. The whole point of provider
    truth is a report free of side effects.

    Returns a dict with ``campaigns`` (a list of per-campaign dicts),
    ``total`` (meta.total from the listing), ``campaign_ids`` (the sorted
    named set), and ``error`` (None when the read succeeded, a reason string
    when it did not). A campaign whose lead count cannot be read carries
    ``lead_count: "UNKNOWN"`` with a ``lead_count_reason`` - it is NOT
    reported as zero, because zero is a number and an unreadable count is
    not one.

    EVERY CAMPAIGN THE CREDENTIAL CAN SEE, TAGGED BY OWNERSHIP - never
    filtered down to a believed id range and never decided by name prefix
    alone. Found 2026-09-26: this function already covers the whole
    workspace (`bison.list_all_campaigns()` is fully paginated with no id
    filter), but the first ownership tag used only the RESONATE name prefix
    and got it wrong in both directions - 487/489 (RESONATE-prefixed,
    ACTIVE) were missed by every human reading a snapshot that already had
    them, and 503/504/505 (no prefix, but already recorded in
    `work/campaigns.jsonl` from the 09-25 factory run) would have read as
    the client's. `owned_by_resonate` fixes the order: `claimed_bison_ids`
    (from `internal_claims()`) decides first, the name prefix is the
    fallback for a real campaign our factory made but never registered.
    """
    try:
        campaigns, total = bison.list_all_campaigns()
    except Exception as exc:
        return {
            "campaigns": [],
            "total": None,
            "campaign_ids": [],
            "error": "listing failed: %s" % str(exc)[:200],
        }

    detailed = []
    for c in campaigns:
        cid = c.get("id")
        name = c.get("name")
        entry = {
            "bison_campaign_id": cid,
            "name": name,
            "status": c.get("status"),
            "owner": ("resonate"
                      if owned_by_resonate(name, cid, claimed_bison_ids)
                      else "client_or_other"),
        }
        try:
            entry["lead_count"] = bison.campaign_lead_count(cid)
        except Exception as exc:
            entry["lead_count"] = "UNKNOWN"
            entry["lead_count_reason"] = str(exc)[:200]
        detailed.append(entry)

    ids = sorted({str(c["bison_campaign_id"]) for c in detailed
                  if c.get("bison_campaign_id") is not None})
    return {
        "campaigns": detailed,
        "total": total,
        "campaign_ids": ids,
        "error": None,
    }


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()
    st, _ = request("GET", base + "/auth/CheckApiKey", hdr)
    if st != 200:
        print("HeyReach credential rejected: HTTP %s (env var HEYREACH_KEY)" % st)
        return 2

    claims = internal_claims()
    claimed_hr_ids = {int(r["heyreach_campaign_id"]) for r in claims
                      if r.get("heyreach_campaign_id")}
    claimed_bison_ids = {int(r["bison_campaign_id"]) for r in claims
                         if r.get("bison_campaign_id")}

    campaigns, total = all_campaigns(base, hdr)
    ours = [c for c in campaigns
            if owned_by_resonate(c.get("name"), c.get("id"), claimed_hr_ids)]

    detailed = []
    for c in ours:
        cid = c.get("id")
        c = dict(c)
        c["sequence"] = sequence_shape(cid)
        list_id = c.get("linkedInUserListId")
        if list_id:
            lst, ldata = request("GET", base + "/list/GetById?listId=%s" % list_id, hdr)
            c["list_detail"] = ({"id": ldata.get("id"), "name": ldata.get("name"),
                                 "count": ldata.get("totalItemsCount"),
                                 "type": ldata.get("listType")}
                                if lst == 200 else {"error": lst})
        c["classification"] = classify(c)
        detailed.append(c)

    # Sender accounts, so "sender missing" can be ruled in or out by name.
    st, adata = request("POST", base + "/li_account/GetAll", hdr, {"offset": 0, "limit": 100})
    accounts = {a["id"]: a for a in (adata.get("items") or [])} if st == 200 else {}

    mapping = []
    for c in detailed:
        senders = []
        for aid in (c.get("campaignAccountIds") or []):
            a = accounts.get(aid)
            # The sender is a REAL PERSON - a client seat holder. The id and
            # whether it resolves and is active is everything an operator needs
            # to rule "sender missing" in or out; the name adds nothing and is
            # PII in a tracked file. Writing it here tripped
            # test_no_real_person_or_client_named on the first commit of this
            # script, which is the guard doing its job on its own author.
            senders.append({"id": aid,
                            "name_hash": short_hash("%s %s" % (a.get("firstName") or "",
                                                               a.get("lastName") or "")) if a else None,
                            "active": a.get("isActive") if a else None,
                            "resolves": bool(a)})
        mapping.append({
            "internal_campaign_id": "productive-linkedin-production-v1"
                                    if c.get("id") == 599020 else None,
            "heyreach_campaign_id": c.get("id"),
            "name": c.get("name"),
            "status": c.get("status"),
            "classification": c["classification"],
            "created": c.get("creationTime"),
            "started_at": c.get("startedAt"),
            "lead_list_id": c.get("linkedInUserListId"),
            "lead_list_name": c.get("linkedInUserListName"),
            "lead_count": (c.get("progressStats") or {}).get("totalUsers"),
            "list_detail": c.get("list_detail"),
            "senders": senders,
            "organization_unit_id": c.get("organizationUnitId"),
            "sequence": c["sequence"],
            "last_provider_readback": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

    # claims / claimed_hr_ids / claimed_bison_ids already computed above, for
    # ownership. Reused here (as strings, since these two compare against
    # string-keyed provider id sets) for the orphan-claim consistency check.
    claimed_hr_ids_str = {str(i) for i in claimed_hr_ids}
    provider_ids = {str(c.get("id")) for c in campaigns}
    # A claim the provider does not confirm is a production consistency defect.
    orphan_hr_claims = sorted(claimed_hr_ids_str - provider_ids)

    # --- EmailBison half: read-only, every campaign, lead counts from meta.total
    bison_result = read_emailbison_campaigns(claimed_bison_ids)
    claimed_bison_ids_str = {str(i) for i in claimed_bison_ids}
    bison_provider_ids = set(bison_result["campaign_ids"])
    orphan_bison_claims = sorted(claimed_bison_ids_str - bison_provider_ids)

    # Campaigns the provider sees that we do not claim - the reverse drift.
    bison_unclaimed = sorted(bison_provider_ids - claimed_bison_ids_str)

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ("HeyReach public API + EmailBison public API, both "
                   "read-only. Credential env vars: HEYREACH_KEY, BISON_KEY."),
        "heyreach": {
            "campaigns_total_in_account": total,
            "campaigns_created_by_resonate": len(ours),
            "resonate_campaigns": mapping,
            "status_totals": _counts(campaigns),
            "linkedin_accounts_available": len(accounts),
        },
        "emailbison": {
            "campaigns_total": bison_result["total"],
            "campaigns": bison_result["campaigns"],
            "campaign_ids": bison_result["campaign_ids"],
            "status_totals": _bison_status_counts(bison_result["campaigns"]),
            "owner_totals": _bison_owner_counts(bison_result["campaigns"]),
            "error": bison_result["error"],
            "sending_now": [
                {"bison_campaign_id": c["bison_campaign_id"],
                 "name": c.get("name"),
                 "owner": c.get("owner"),
                 "lead_count": c["lead_count"]}
                for c in bison_result["campaigns"]
                if (c.get("status") or "").lower() in ("active", "sending",
                                                        "in_sequence")
            ],
        },
        "internal_vs_provider": {
            "internal_records": len(claims),
            "heyreach": {
                "internal_ids": sorted(claimed_hr_ids_str),
                "claims_provider_does_not_confirm": orphan_hr_claims,
            },
            "emailbison": {
                "internal_ids": sorted(claimed_bison_ids_str),
                "provider_ids": bison_result["campaign_ids"],
                "claims_provider_does_not_confirm": orphan_bison_claims,
                "at_provider_not_claimed": bison_unclaimed,
            },
            "consistent": not orphan_hr_claims and not orphan_bison_claims,
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print("HeyReach campaigns in account: %s" % total)
    print("Created by Resonate OS:        %s" % len(ours))
    for m in mapping:
        print("  %s  %-44s %-22s leads=%s nodes=%s" % (
            m["heyreach_campaign_id"], m["name"][:44], m["classification"],
            m["lead_count"], m["sequence"].get("unique_nodes")))
    print("internal HeyReach claims the provider does not confirm: %s" % (
        orphan_hr_claims or "none"))
    print()
    print("EmailBison campaigns:  %s" % (
        bison_result["total"] if bison_result["total"] is not None else "READ ERROR"))
    if bison_result["error"]:
        print("  ERROR: %s" % bison_result["error"])
    for c in bison_result["campaigns"]:
        lc = c["lead_count"]
        reason = c.get("lead_count_reason", "")
        lc_str = str(lc) if lc != "UNKNOWN" else "UNKNOWN (%s)" % reason
        print("  %s  %-44s %-16s leads=%s" % (
            c["bison_campaign_id"], (c.get("name") or "")[:44],
            c.get("status") or "?", lc_str))
    print("EmailBison campaign ids (named set): %s" % bison_result["campaign_ids"])
    print("internal EmailBison claims the provider does not confirm: %s" % (
        orphan_bison_claims or "none"))
    print("at provider not claimed internally: %s" % (
        bison_unclaimed or "none"))
    sending = doc["emailbison"]["sending_now"]
    if sending:
        print("SENDING NOW (from provider status):")
        for s in sending:
            print("  %s  leads=%s" % (s["bison_campaign_id"], s["lead_count"]))
    else:
        print("SENDING NOW: none (no campaign has an active/sending status)")
    print("written: docs/state/PROVIDER-CAMPAIGNS.json")
    return 0


def _counts(campaigns):
    out = {}
    for c in campaigns:
        k = c.get("status") or "?"
        out[k] = out.get(k, 0) + 1
    return out


def _bison_status_counts(campaigns):
    """Status histogram for the EmailBison half. Same shape as _counts but
    over the trimmed bison campaign dicts."""
    out = {}
    for c in campaigns:
        k = c.get("status") or "?"
        out[k] = out.get(k, 0) + 1
    return out


def _bison_owner_counts(campaigns):
    """Ownership histogram for the EmailBison half - resonate vs
    client_or_other, over every campaign the credential can see. Answers
    "how much of this workspace is ours" without anyone having to read 40
    rows by hand."""
    out = {}
    for c in campaigns:
        k = c.get("owner") or "?"
        out[k] = out.get(k, 0) + 1
    return out


if __name__ == "__main__":
    sys.exit(main())
