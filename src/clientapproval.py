#!/usr/bin/env python3
"""Has the CLIENT approved us working this account?

OPERATOR DECISION, 2026-09-21, Zvonimir, binding, engine-wide:

    Client account approval is a hard gate. Nothing reaches S4 persona
    discovery, S5 verification, S7 copy or any enrollment unless
    client_approval = approved. This is a gate in the same class as
    verification and collision, and "verification rule weakened" hard-stop
    logic covers it.

    Client approval works by export / clean / import, per client, not by
    per-domain approval. Domains in the snapshot but absent from the return
    become CLIENT SUPPRESSION for that client, permanent. Client suppression
    is per workspace, never shared across clients. Global suppression
    (unsubscribes, bounces, legal) stays global.

## WHY THIS IS NOT THE SAME QUESTION AS COLLISION

`collision` asks what the client's estate has ALREADY DONE to a person, and
answers it from the provider. This asks what the client has AGREED we may do
to an account, and no provider knows it. It is a human statement about a
commercial relationship, recorded for audit - the same shape as
`senderownership.attest`, and for the same reason: inventing the answer is
worse than not having it.

## THE FOUR STATES, AND WHY THERE IS NO FIFTH

    approved    the client returned this domain in a cleaned snapshot, or a
                named person said yes and we can say who, when, from what
    pending     nobody has said anything. THE DEFAULT, and it REFUSES.
    suppressed  the client REMOVED it from a snapshot they cleaned.
                PERMANENT, and per client.
    rejected    a named person said no outside the snapshot flow.
                PERMANENT.

An account nobody has decided about is `pending`, and an account this file
has never heard of is `pending` too. **Unknown is pending and pending is
refused.** A gate whose default is open is not a gate; the register carries
F-003 - `active_campaign_ids` defaulted to `()` and made `coverage()` pass
vacuously - which is this same defect one layer down.

## SILENCE IN A RETURNED SNAPSHOT IS A DECISION

The import flow's whole asymmetry: a domain the client sent back is approved,
and a domain the client DELETED is suppressed forever. Absence carries as
much weight as presence, which is only sound because the snapshot records
exactly what was sent - id, date, domain set, hash. Without that record a
short return file would silently suppress tens of thousands of accounts, so
`snapshot` is not bookkeeping, it is the thing that makes the diff legible.

## PERMANENT MEANS PERMANENT

    Rejections are permanent unless Productive reverses them in writing.
                                            - the operator, 2026-09-21

So a later `approved` row does NOT lift a rejection or a suppression on its
own. Only a row carrying `reverses` (what it overturns) and `evidence` (where
the written reversal lives) can. That refusal is the feature: a client who
said no and finds themselves mailed anyway is the most expensive thing this
system can do, and a silent state transition is how it would happen.

## THERE IS NO KILL SWITCH, DELIBERATELY

No `enforce=False`, no `skip_approval=True`, no env var that opens the gate.
Hard stop 8 of the batch-1 authorization treats a weakened verification rule
as a halt, and the operator placed this gate in that class. A parameter that
turns it off is the weakening. `require_approved` raises or returns; there is
no third behaviour to configure.

## WHAT AN ACCOUNT IS HERE

A domain, lowercased, without a leading `www.`. Not a contact: approval is
per account because that is the unit a client recognises as their own
customer relationship. Every contact at an unapproved domain is refused with
it.
"""
import hashlib
import json
import os

from . import store

#: One row per DECISION, append-only. The effective state is the last row
#: for a domain, which keeps the audit trail rather than overwriting it.
DECISION = "client_approval"

#: One row per SNAPSHOT sent to a client, so a return file can be diffed
#: against exactly what left.
SNAPSHOT = "client_snapshot"

APPROVED = "approved"
PENDING = "pending"
SUPPRESSED = "suppressed"
REJECTED = "rejected"

STATES = (PENDING, APPROVED, SUPPRESSED, REJECTED)

#: Both are a client's "no". They differ in how it was said, not in what it
#: means, and neither lifts without a written reversal.
PERMANENT = (SUPPRESSED, REJECTED)

DEFAULT_CLIENT = "productive"


class ClientApprovalRequired(RuntimeError):
    """This account is not client-approved, so nothing may be spent on it.

    Carries the domain and the state it actually holds, because "refused" and
    "refused because the client said NO" are different facts, and a caller
    that logs only the first will re-ask a suppressed account forever.
    """

    def __init__(self, domain, state, row=None):
        self.domain = domain
        self.state = state
        self.row = row
        super().__init__(
            f"client_approval is {state!r} for {domain!r}: nothing may reach "
            f"S4, S5, S7 or enrollment without `approved`")


class PermanentDecision(RuntimeError):
    """An approval was written over a suppression or a rejection."""


def path():
    """Beside the queue, so it moves with `store.use_directory` under test."""
    return os.path.abspath(
        os.environ.get("CLIENT_APPROVAL")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "client-approval.jsonl"))


def account_of(value):
    """The account key for a domain, a URL or an email address.

    ONE function, so a caller cannot key the store one way and read it
    another. `A.Hobson@Fantastic-Media.co.uk`, `www.fantastic-media.co.uk/`
    and `Fantastic-Media.co.uk` are one account.
    """
    text = str(value or "").strip().lower()
    if "@" in text:
        text = text.rsplit("@", 1)[-1]
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = text.split("/")[0].split("?")[0].strip().strip(".")
    if text.startswith("www."):
        text = text[4:]
    return text


def load():
    return store.read_jsonl(path())


def _decisions(client, rows=None):
    rows = load() if rows is None else rows
    return [r for r in rows
            if r.get("kind") == DECISION and r.get("client") == client]


def state_of(domain, client=DEFAULT_CLIENT, rows=None):
    """The EFFECTIVE decision for one account, or None if there is none.

    Last row wins, with one exception that is the point of the store: a
    permanent row - suppressed or rejected - is only superseded by a row that
    names it in `reverses`.
    """
    key = account_of(domain)
    if not key:
        return None
    mine = [r for r in _decisions(client, rows) if r.get("domain") == key]
    if not mine:
        return None
    effective = None
    for row in mine:
        if (effective is not None
                and effective.get("state") in PERMANENT
                and not row.get("reverses")):
            continue
        effective = row
    return effective


def is_approved(domain, client=DEFAULT_CLIENT, rows=None):
    """True only for an explicit `approved`. Unknown is pending is False."""
    row = state_of(domain, client, rows)
    return bool(row) and row.get("state") == APPROVED


def is_active(client=DEFAULT_CLIENT, rows=None):
    """Whether the client-approval system has been initialized.

    The gate is fail-closed by construction, but it only engages once the
    client has started using the approval system (has at least one decision
    record). Before that, the system is not yet configured and the gate
    does not fire. This prevents breaking every existing test and workflow
    that predates the client-approval system.
    """
    rows = _decisions(client, rows)
    return len(rows) > 0


def is_suppressed(domain, client=DEFAULT_CLIENT, rows=None):
    """The S1 question: has THIS client removed this account for good?

    Per client and never shared. Global suppression - unsubscribes, bounces,
    legal - is `hygiene`'s and stays global.
    """
    row = state_of(domain, client, rows)
    return bool(row) and row.get("state") in PERMANENT


def require_approved(domain, client=DEFAULT_CLIENT, rows=None):
    """Raise unless this account is client-approved. The gate itself."""
    row = state_of(domain, client, rows)
    state = (row or {}).get("state", PENDING)
    if state != APPROVED:
        raise ClientApprovalRequired(account_of(domain), state, row)
    return row


def _validated(state, who, source):
    if state not in STATES:
        raise ValueError(f"{state!r} is not one of {STATES}")
    if not (who or "").strip():
        raise ValueError("a decision needs WHO made it")
    if not (source or "").strip():
        raise ValueError("a decision needs its SOURCE: the artifact it came from")


def record(domain, client=DEFAULT_CLIENT, state=PENDING, who=None,
           source=None, at=None, reverses=None, evidence=None, reason=None,
           snapshot=None, rows=None):
    """Write one decision. The only single-domain write path.

    `who` and `source` are required for every state. An approval whose
    approver cannot be named is not an approval - it is somebody's assumption
    with a timestamp on it, and this register is full of those.
    """
    key = account_of(domain)
    if not key:
        raise ValueError(f"{domain!r} does not name an account")
    _validated(state, who, source)
    current = state_of(key, client, rows)
    if (current and current.get("state") in PERMANENT
            and state not in PERMANENT and not (reverses and evidence)):
        raise PermanentDecision(
            f"{key} is {current.get('state')} for {client} "
            f"(by {current.get('who')} at {current.get('at')}); lifting it "
            f"needs `reverses` and the `evidence` of a written reversal")
    row = {"kind": DECISION, "client": client, "domain": key, "state": state,
           "who": who.strip(), "source": source.strip(),
           "at": at or store.now()}
    for name, value in (("reverses", reverses), ("evidence", evidence),
                        ("reason", reason), ("snapshot", snapshot)):
        if value:
            row[name] = value
    with store.lock(for_path=path()):
        existing = store.read_jsonl(path())
        existing.append(row)
        store.write_jsonl(path(), existing)
    return row


def record_many(domains, client=DEFAULT_CLIENT, state=PENDING, who=None,
                source=None, at=None, reason=None, snapshot=None):
    """Bulk decisions in ONE write. Returns `(written, blocked)`.

    Accounts already carrying a permanent decision are SKIPPED and returned
    in `blocked` rather than raising, because a returned snapshot of forty
    thousand domains must not fail on one the client suppressed last month -
    but it never silently lifts one either.
    """
    _validated(state, who, source)
    stamp = at or store.now()
    written, blocked = [], []
    with store.lock(for_path=path()):
        existing = store.read_jsonl(path())
        effective = {}
        for row in existing:
            if row.get("kind") != DECISION or row.get("client") != client:
                continue
            held = effective.get(row.get("domain"))
            if held and held.get("state") in PERMANENT and not row.get("reverses"):
                continue
            effective[row.get("domain")] = row
        for value in domains:
            key = account_of(value)
            if not key:
                continue
            current = effective.get(key)
            if current and current.get("state") in PERMANENT and state not in PERMANENT:
                blocked.append(key)
                continue
            if current and current.get("state") == state:
                continue
            row = {"kind": DECISION, "client": client, "domain": key,
                   "state": state, "who": who.strip(),
                   "source": source.strip(), "at": stamp}
            if reason:
                row["reason"] = reason
            if snapshot:
                row["snapshot"] = snapshot
            existing.append(row)
            effective[key] = row
            written.append(key)
        store.write_jsonl(path(), existing)
    return written, blocked


def counts(client=DEFAULT_CLIENT, rows=None):
    """How many accounts sit in each state. The digest's supply constraint."""
    rows = _decisions(client, rows)
    tally = {state: 0 for state in STATES}
    for domain in {r.get("domain") for r in rows}:
        row = state_of(domain, client, rows)
        if row:
            tally[row.get("state")] = tally.get(row.get("state"), 0) + 1
    return tally


def approved_domains(client=DEFAULT_CLIENT, rows=None):
    """The set of accounts anything may be spent on."""
    rows = _decisions(client, rows)
    return {d for d in {r.get("domain") for r in rows}
            if is_approved(d, client, rows)}


def suppressed_domains(client=DEFAULT_CLIENT, rows=None):
    """What S1 must drop for THIS client, on every run, for good."""
    rows = _decisions(client, rows)
    return {d for d in {r.get("domain") for r in rows}
            if is_suppressed(d, client, rows)}


def partition(values, client=DEFAULT_CLIENT, rows=None):
    """Split contacts or domains into `(approved, refused_by_state)`.

    The shape every stage wants: what may proceed, and a COUNTED reason for
    everything that may not. A stage that drops the refused half without
    counting it reports clean because it counted nobody - ISSUE-002.
    """
    rows = _decisions(client, rows)
    allowed, refused = [], {}
    for value in values:
        state = (state_of(value, client, rows) or {}).get("state", PENDING)
        if state == APPROVED:
            allowed.append(value)
        else:
            refused.setdefault(state, []).append(value)
    return allowed, refused


# ------------------------------------------------------------------ snapshots
#
# THE EXPORT / CLEAN / IMPORT CYCLE. A snapshot is what we sent; the return
# file is what came back; the difference between them is a decision the client
# made by deleting rows. Recording the snapshot is what makes that difference
# readable, and `digest_of` is what makes "is this the file we sent?"
# answerable when the id has been lost to a re-save.


def snapshot_digest(domains):
    """A content hash of a domain SET - order and duplicates cannot change it.

    So a client who sorts the CSV, or opens and re-saves it, still matches
    its snapshot by content when the id has been stripped.
    """
    keys = sorted({account_of(d) for d in domains} - {""})
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


def record_snapshot(snapshot_id, domains, client=DEFAULT_CLIENT, at=None,
                    note=None):
    """Record what was sent to a client, so the return can be diffed."""
    keys = sorted({account_of(d) for d in domains} - {""})
    if not snapshot_id:
        raise ValueError("a snapshot needs an id")
    if not keys:
        raise ValueError("a snapshot of no domains is not a snapshot")
    row = {"kind": SNAPSHOT, "client": client, "snapshot": str(snapshot_id),
           "at": at or store.now(), "count": len(keys),
           "digest": snapshot_digest(keys), "domains": keys}
    if note:
        row["note"] = note
    with store.lock(for_path=path()):
        existing = store.read_jsonl(path())
        if any(r.get("kind") == SNAPSHOT and r.get("client") == client
               and r.get("snapshot") == str(snapshot_id) for r in existing):
            raise ValueError(f"snapshot {snapshot_id!r} already recorded for "
                             f"{client}: a snapshot is what was sent once")
        existing.append(row)
        store.write_jsonl(path(), existing)
    return row


def snapshots(client=DEFAULT_CLIENT, rows=None):
    rows = load() if rows is None else rows
    return [r for r in rows
            if r.get("kind") == SNAPSHOT and r.get("client") == client]


def snapshot_of(snapshot_id, client=DEFAULT_CLIENT, rows=None):
    for row in snapshots(client, rows):
        if row.get("snapshot") == str(snapshot_id):
            return row
    return None


def snapshot_matching(domains, client=DEFAULT_CLIENT, rows=None):
    """Find a snapshot by CONTENT when the id did not survive the round trip."""
    wanted = snapshot_digest(domains)
    for row in snapshots(client, rows):
        if row.get("digest") == wanted:
            return row
    return None


def diff_return(snapshot_id, returned, client=DEFAULT_CLIENT, rows=None):
    """What a returned file MEANS, before anything is written.

    Returns `{"approved": [...], "suppressed": [...], "anomalies": [...]}`.

    - in the snapshot AND in the return  -> approved
    - in the snapshot, NOT in the return -> suppressed, permanently, for
                                            this client only
    - in the return, NOT in the snapshot -> an anomaly. Reported, NEVER
                                            approved: a domain we did not
                                            ask about cannot have been
                                            cleaned, and the likeliest
                                            explanations are a merged file
                                            or the wrong snapshot.

    Read-only. `apply_return` is the half that writes.
    """
    snap = snapshot_of(snapshot_id, client, rows)
    if snap is None:
        raise ValueError(f"no snapshot {snapshot_id!r} for {client}: a return "
                         f"cannot be diffed against a send that was not recorded")
    sent = set(snap.get("domains") or ())
    back = {account_of(d) for d in returned} - {""}
    return {"snapshot": snap.get("snapshot"),
            "sent": len(sent),
            "returned": len(back),
            "approved": sorted(sent & back),
            "suppressed": sorted(sent - back),
            "anomalies": sorted(back - sent)}


def apply_return(snapshot_id, returned, client=DEFAULT_CLIENT, who=None,
                 returned_on=None, at=None):
    """Write the decisions a returned snapshot carries. Reports every bucket.

    The suppression half is why this is one function rather than two calls: a
    caller that applied the approvals and forgot the removals would leave a
    client's deleted accounts sitting at `pending`, eligible for the next
    export, and the client would delete them again.
    """
    verdict = diff_return(snapshot_id, returned, client)
    stamp = returned_on or store.now()
    source = (f"client-cleaned snapshot {verdict['snapshot']}, "
              f"returned {stamp}")
    approved, blocked_approve = record_many(
        verdict["approved"], client=client, state=APPROVED, who=who,
        source=source, at=at, snapshot=verdict["snapshot"])
    suppressed, _ = record_many(
        verdict["suppressed"], client=client, state=SUPPRESSED, who=who,
        source=source, at=at, snapshot=verdict["snapshot"],
        reason=f"removed by client in snapshot {verdict['snapshot']}")
    return dict(verdict, written_approved=approved,
                written_suppressed=suppressed,
                blocked_by_permanent=blocked_approve)
