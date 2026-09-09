#!/usr/bin/env python3
"""Restore verification evidence from a record's own event log.

WHY THIS EXISTS. On 2026-09-08 a batch verification run reached its budget
ceiling and emitted a `verification_result` carrying `state: unknown`,
`reason: "no verification evidence"` and **`contact: null`**. That contact-less
verdict was written onto contacts that did have evidence, and
`verification.apply` stored it: two addresses at `brightpath.test` that had
been answered by ContactOut and Reoon came back reading `state: unknown`,
`cost: 0`, `providers: []`, `evidence: []`.

That is missing evidence overwriting *negative* evidence, which is worse than
the usual direction. `accept_all_uncleared` means "a catch-all that nothing
cleared - do not send". `unknown` means "ask again". So the loss did not just
forget an answer, it converted a refusal into an instruction to re-buy, and
the ledger shows the re-buy had already happened once (13:27, then 15:17).

`store.refuse_evidence_loss` would refuse that write today. It landed two and
a half hours after this happened, so this is damage that predates its guard.

WHAT THIS MODULE MAY AND MAY NOT DO. The event log is append-only and survived,
and it carries the structured rows - provider, status, timestamp, contact key -
that a verification evidence entry is built from. So the answers are
recoverable without asking any provider anything.

The rules this module holds itself to, because a reconstruction that is not
obviously a reconstruction is worse than a gap:

  - Only `provider_call_completed` events with `operation == "verify"` are
    read, and only their `provider`, `status` and `at`. Prose is never parsed;
    the `reason` text on a `verification_result` is not evidence of anything.
  - No provider field is invented. `deliverable`, `safe_to_send`, `catch_all`,
    `score` and the rest stay `None` because the event log does not record
    them. The recomputed reason is therefore sometimes less specific than the
    one originally logged, and that is the honest outcome.
  - The state is **recomputed** by `verification.decide` from the restored
    evidence. The state recorded on the old event is used only to check the
    answer afterwards, never copied.
  - Evidence is appended through `verification.apply`, which merges rather
    than replaces and re-decides when the caller's list is short.
  - `verification.evidence_for` binds evidence to the address it was bought
    for, so a row cannot migrate to a different person or a different mailbox.
  - Every restored row is marked `reconstructed: True` and carries the id of
    the event it came from.

This is not a general repair tool and takes no arguments naming what to fix:
it finds contacts whose stored evidence is missing rows their own event log
proves were bought, and restores exactly those.
"""
import argparse
import json

from . import events, store, verification


class NothingToRepair(RuntimeError):
    """No contact has evidence its own event log can restore."""


def completed_verify_calls(rec, key):
    """The durable rows for one contact: provider, status, moment.

    `operation == "verify"` because a record's event log also carries
    discovery and research calls, and only a verification answer belongs in
    verification evidence.
    """
    out = []
    for entry in rec.get("events") or []:
        if entry.get("type") != events.PROVIDER_CALL_COMPLETED:
            continue
        if entry.get("operation") != "verify":
            continue
        if entry.get("contact") != key or not key:
            continue
        if not entry.get("provider") or not entry.get("status"):
            continue
        out.append(entry)
    return out


def _restored_row(contact, event):
    """One evidence entry, built only from fields the event actually carries."""
    row = verification.result(event["provider"], event["status"],
                              email=contact.get("email"), at=event["at"])
    row["reconstructed"] = True
    row["reconstructed_from"] = {
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "why": ("restored from this record's own event log after a "
                "contact-less verification result overwrote the stored "
                "evidence; no provider was called"),
    }
    return row


def missing_rows(rec, contact):
    """Rows the event log proves were bought and the contact no longer holds.

    Keyed the way `verification._row_key` keys them - provider, address,
    moment - so a row already stored is never restored twice.
    """
    key = contact.get("key")
    calls = completed_verify_calls(rec, key)
    if not calls:
        return []
    held = {verification._row_key(row)
            for row in verification.evidence_of(contact)}
    out = []
    for event in calls:
        row = _restored_row(contact, event)
        if verification._row_key(row) in held:
            continue
        out.append(row)
    return out


def repair_contact(rec, contact, policy=None):
    """Restore one contact's evidence and recompute its verdict.

    Returns the decision, or None when there was nothing to restore.
    """
    rows = missing_rows(rec, contact)
    if not rows:
        return None
    events.record(rec, events.EVIDENCE_RECONSTRUCTED,
                  contact_key=contact.get("key"), channel="email",
                  restored=len(rows),
                  providers=sorted({row["provider"] for row in rows}),
                  reason=("evidence restored from this record's event log; "
                          "no provider was called"))
    # `apply` merges rather than replaces, and re-decides from the merged
    # history rather than from the rows handed to it. Passing the decision
    # computed from the restored rows alone would be wrong if anything is
    # already stored, which is exactly the case `apply` re-decides for.
    decision = verification.decide(
        verification.evidence_for(contact, rows), policy)
    return verification.apply(contact, decision, rows, rec=rec, policy=policy)


def repair_record(rec, policy=None):
    """Every contact on one record, selected and excluded alike.

    Excluded people are repaired too: an exclusion moves somebody out of the
    selection, it does not un-buy what was spent on them, and leaving their
    evidence missing is what makes a later re-selection re-buy it.
    """
    done = []
    for group in ("contacts", "excluded"):
        for contact in rec.get(group) or []:
            decision = repair_contact(rec, contact, policy)
            if decision is None:
                continue
            done.append({
                "record": rec.get("id"),
                "domain": rec.get("domain"),
                "group": group,
                "contact": contact.get("key"),
                "name": contact.get("name"),
                "state": decision.get("state"),
                "sendable": decision.get("sendable"),
                "reason": decision.get("reason"),
                "restored": len(verification.evidence_of(contact)),
            })
    return done


def scan(recs, policy=None):
    """What would be repaired, without changing anything."""
    found = []
    for rec in recs:
        for group in ("contacts", "excluded"):
            for contact in rec.get(group) or []:
                rows = missing_rows(rec, contact)
                if not rows:
                    continue
                found.append({
                    "record": rec.get("id"),
                    "domain": rec.get("domain"),
                    "group": group,
                    "contact": contact.get("key"),
                    "name": contact.get("name"),
                    "rows": len(rows),
                    "providers": sorted({row["provider"] for row in rows}),
                    "would_be": verification.decide(
                        verification.evidence_for(contact, rows),
                        policy).get("state"),
                })
    return found


def run(live=False, policy=None):
    """Scan, and when `live`, write. Dry by default like everything else here."""
    if not live:
        return {"live": False, "found": scan(store.load(), policy)}
    repaired = []
    with store.transaction() as recs:
        for rec in recs:
            repaired += repair_record(rec, policy)
    return {"live": True, "repaired": repaired}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true",
                   help="write the restored evidence; dry run otherwise")
    a = p.parse_args(argv)
    print(json.dumps(run(live=a.live), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
