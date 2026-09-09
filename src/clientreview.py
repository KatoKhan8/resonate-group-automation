#!/usr/bin/env python3
"""The client's ruling on a list of candidates, and getting it back safely.

## Why a CSV

Because the client already has one open. This is the one place in the
product where the counterparty is not an operator, has no login, and will
edit the file in Excel on a Tuesday. Everything below follows from that.

## The file that goes out

Two kinds of column, kept apart:

    canonical   what we found, and the id that ties a row to a candidate
    editable    the three fields the client is being asked to fill

The canonical ones are *echoed back* on return and compared. If a
`domain` or an `icp_tier` comes back changed, that is not an edit to
accept - it is a file that has been through something, and applying its
decisions would attach the client's ruling to the wrong company. The
return path refuses the row and says which field moved.

## The id is the identity

`resonate_candidate_id` is a hash of workspace, batch and domain. A row
whose id is unknown, missing or duplicated is refused rather than matched
on company name, because name matching here would mean a client's "do not
contact" landing on a different company that happened to be spelled
similarly.

## Statuses are a closed set

Free text in a decision column is a decision nobody can act on
consistently. Thirteen statuses, each with a defined consequence, and an
unrecognised one is refused with the list rather than quietly treated as
unknown.

## What a status does

The consequences are deliberately narrow. `DO_NOT_CONTACT` suppresses.
`EXISTING_CLIENT` and the other relationship statuses exclude the company
from cold outreach and say why. `BAD_FIT` is *learning input and nothing
more* - it does not change the ICP, because one client's opinion about one
company is not a change to what the client sells to, and §71 of the brief
is explicit that only an authorised human may move canonical ICP.

Nothing here enriches, contacts, or spends. Applying decisions writes
suppression and review state; the enrichment that costs money is behind
the approval gate that follows.
"""
import csv
import hashlib
import io
import json
import os

from . import export, ingest, store

# ------------------------------------------------------------------ statuses
#
# A closed set, because free text in a decision column is a decision
# nobody can act on consistently. Each carries what it *does*, and several
# deliberately do nothing but inform.

APPROVED = "approved"
EXISTING_CLIENT = "existing_client"
EXISTING_OPPORTUNITY = "existing_opportunity"
ACTIVE_PROSPECT = "active_prospect"
FORMER_CLIENT = "former_client"
PARTNER = "partner"
COMPETITOR = "competitor"
DO_NOT_CONTACT = "do_not_contact"
NOT_RELEVANT = "not_relevant"
BAD_FIT = "bad_fit"
DUPLICATE = "duplicate"
UNKNOWN = "unknown"
REVIEW_LATER = "review_later"

STATUSES = (APPROVED, EXISTING_CLIENT, EXISTING_OPPORTUNITY, ACTIVE_PROSPECT,
            FORMER_CLIENT, PARTNER, COMPETITOR, DO_NOT_CONTACT, NOT_RELEVANT,
            BAD_FIT, DUPLICATE, UNKNOWN, REVIEW_LATER)

# What each one means for outreach. Three outcomes and nothing else:
# proceed, do not, or a person decides.
PROCEED = "proceed"
EXCLUDE = "exclude"
SUPPRESS = "suppress"
DEFER = "defer"
REVIEW = "review"

EFFECT = {
    APPROVED: PROCEED,
    # A removal request from the client is the strongest thing on this
    # list and the only one that writes to suppression.
    DO_NOT_CONTACT: SUPPRESS,
    # Relationships. None of these is a suppression - the company may be
    # worked later, by a person, through a different motion - but none of
    # them may receive a cold sequence.
    EXISTING_CLIENT: EXCLUDE,
    EXISTING_OPPORTUNITY: EXCLUDE,
    ACTIVE_PROSPECT: EXCLUDE,
    PARTNER: EXCLUDE,
    COMPETITOR: EXCLUDE,
    FORMER_CLIENT: REVIEW,
    # Judgements about fit. They inform and they do not act: see
    # `learning_signal` below.
    NOT_RELEVANT: EXCLUDE,
    BAD_FIT: EXCLUDE,
    DUPLICATE: EXCLUDE,
    REVIEW_LATER: DEFER,
    UNKNOWN: REVIEW,
}

STATUS_LABEL = {
    APPROVED: "Approved - go ahead",
    EXISTING_CLIENT: "Already a customer",
    EXISTING_OPPORTUNITY: "Live opportunity",
    ACTIVE_PROSPECT: "Already in conversation",
    FORMER_CLIENT: "Former customer",
    PARTNER: "Partner",
    COMPETITOR: "Competitor",
    DO_NOT_CONTACT: "Do not contact",
    NOT_RELEVANT: "Not relevant",
    BAD_FIT: "Not a fit",
    DUPLICATE: "Duplicate of another row",
    UNKNOWN: "Not sure",
    REVIEW_LATER: "Come back to this",
}

# The statuses that say something about *fit* rather than about a
# relationship. Only these are worth learning from, and even then only as
# an observation - the ICP does not move without a person moving it.
FIT_JUDGEMENTS = (BAD_FIT, NOT_RELEVANT, APPROVED)


class ReviewRefused(ValueError):
    """The returned file was not applied, and the message says why."""


# ------------------------------------------------------------------ the file

ID_COLUMN = "resonate_candidate_id"

# Echoed out and compared on the way back in. A change here is tampering
# or a mangled file, not an edit.
CANONICAL_COLUMNS = ("domain", "company_name", "country", "industry",
                     "employee_band", "icp_score", "icp_tier",
                     "why_matched", "discovery_source", "signal_summary")

# The only three the client is asked to touch.
EDITABLE_COLUMNS = ("client_status", "client_notes", "client_approved")

COLUMNS = (ID_COLUMN,) + CANONICAL_COLUMNS + EDITABLE_COLUMNS


def candidate_id(workspace, batch, domain):
    """Stable, and derived rather than stored.

    Workspace is in the hash, so an id from one client's file cannot
    match a row in another's - a returned file is checked against the
    workspace it is being applied to, and a foreign id simply will not be
    found.
    """
    blob = f"{workspace}|{batch}|{ingest.norm_domain(domain)}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _facts(entry):
    facts = entry.get("facts") or {}
    verdict = entry.get("verdict_facts") or {}
    return {
        "country": facts.get("country"),
        "industry": facts.get("industry"),
        "employee_band": facts.get("employee_band"),
        "icp_score": verdict.get("icp_score"),
        "icp_tier": verdict.get("icp_tier"),
    }


def rows_for(workspace, batch, candidates):
    """The rows of the outgoing file, before they are rendered."""
    rows = []
    for entry in candidates:
        facts = _facts(entry)
        rows.append({
            ID_COLUMN: candidate_id(workspace, batch, entry["domain"]),
            "domain": entry["domain"],
            "company_name": entry.get("company") or "",
            "country": facts["country"] or "",
            "industry": facts["industry"] or "",
            "employee_band": facts["employee_band"] or "",
            "icp_score": facts["icp_score"] if facts["icp_score"] is not None
            else "",
            "icp_tier": facts["icp_tier"] or "",
            "why_matched": entry.get("evidence") or "",
            "discovery_source": entry.get("source") or "",
            "signal_summary": entry.get("signal_summary") or "",
            "client_status": "",
            "client_notes": "",
            "client_approved": "",
        })
    return rows


def to_csv(workspace, batch, candidates):
    """The file to send. Every cell guarded against formula execution.

    The guard matters more here than anywhere else in the product: this is
    the one file that leaves the building and is opened, by somebody who
    is not us, in a spreadsheet.
    """
    rows = rows_for(workspace, batch, candidates)
    return export.to_csv(list(COLUMNS),
                         [[row[column] for column in COLUMNS]
                          for row in rows])


def fingerprint(workspace, batch, candidates):
    """What went out, so what comes back can be compared against it.

    Held by the caller alongside the batch. Without it a returned file can
    only be trusted to the extent that its ids are recognised, and the
    canonical columns could be edited freely.
    """
    rows = rows_for(workspace, batch, candidates)
    return {row[ID_COLUMN]: {column: str(row[column])
                             for column in CANONICAL_COLUMNS}
            for row in rows}


# ---------------------------------------------------------------- coming back

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 200_000


def parse(data, workspace, batch, sent, strict_canonical=True):
    """Read a returned file. Writes nothing; returns what would happen.

    `sent` is the `fingerprint()` of what went out. Every row is checked
    against it:

      * the id must be present, known, and appear once
      * every canonical column must come back unchanged
      * the status must be one of the closed set

    A row that fails any of those is refused *individually* and the rest
    of the file still previews, because one mangled row should not cost
    the client the other four hundred decisions they made.
    """
    if not data:
        raise ReviewRefused("the file was empty")
    if len(data) > MAX_BYTES:
        raise ReviewRefused(
            f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")

    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ReviewRefused("no header row")
    headers = [(h or "").strip().lower() for h in reader.fieldnames]
    if ID_COLUMN not in headers:
        raise ReviewRefused(
            f"no {ID_COLUMN} column: this is not a review file, or the "
            "column was removed")
    if "client_status" not in headers:
        raise ReviewRefused("no client_status column")

    applied, refused, seen = [], [], set()
    blank = 0
    for number, raw in enumerate(reader, start=2):
        if len(applied) + len(refused) >= MAX_ROWS:
            raise ReviewRefused(f"more than {MAX_ROWS} rows")
        row = {(k or "").strip().lower(): (v or "").strip()
               for k, v in raw.items() if k}
        entry_id = row.get(ID_COLUMN, "")

        if not entry_id:
            refused.append({"row": number, "id": None,
                            "why": "no candidate id on this row"})
            continue
        if entry_id in seen:
            refused.append({"row": number, "id": entry_id,
                            "why": "this candidate id appears more than once"})
            continue
        if entry_id not in sent:
            # Also the answer for a file from another workspace or an
            # older batch: the id simply is not one we sent.
            refused.append({"row": number, "id": entry_id,
                            "why": "not a candidate from this review file"})
            continue
        seen.add(entry_id)

        if strict_canonical:
            moved = [column for column, value in sent[entry_id].items()
                     if row.get(column, "") != value]
            if moved:
                refused.append({
                    "row": number, "id": entry_id,
                    "why": "these columns were changed and must not be: "
                           + ", ".join(sorted(moved))})
                continue

        status = (row.get("client_status") or "").strip().lower()
        status = status.replace(" ", "_").replace("-", "_")
        if not status:
            blank += 1
            continue
        if status not in STATUSES:
            refused.append({
                "row": number, "id": entry_id,
                "why": f"{status!r} is not a status. One of: "
                       + ", ".join(STATUSES)})
            continue

        applied.append({
            "row": number,
            "id": entry_id,
            "domain": sent[entry_id]["domain"],
            "status": status,
            "label": STATUS_LABEL[status],
            "effect": EFFECT[status],
            # Client text, carried and never interpreted. It is stripped of
            # control characters on the way in and guarded again on the way
            # out, because it will be exported into another spreadsheet.
            "notes": export.strip_controls(
                row.get("client_notes", ""))[:600],
        })

    by_effect = {}
    for row in applied:
        by_effect[row["effect"]] = by_effect.get(row["effect"], 0) + 1

    missing = [entry_id for entry_id in sent if entry_id not in seen]
    return {
        "workspace": workspace,
        "batch": batch,
        "applied": applied,
        "refused": refused,
        "counts": {
            "rows": len(applied) + len(refused) + blank,
            "decided": len(applied),
            "refused": len(refused),
            "left_blank": blank,
            "never_returned": len(missing),
            **{effect: by_effect.get(effect, 0)
               for effect in (PROCEED, EXCLUDE, SUPPRESS, DEFER, REVIEW)},
        },
        # A row the client did not return is not a rejection. It is a row
        # they did not get to, and treating silence as a decision is how a
        # company gets excluded because somebody closed the file early.
        "never_returned": missing,
        "committed": False,
    }


def learning_signal(parsed):
    """What this review says about fit, as an observation and nothing else.

    Separated from `apply` on purpose. A client calling one company a bad
    fit is evidence about that company; it is not a change to what the
    client sells to. Only an authorised person moves the ICP - see
    GTM-STRATEGY.md - and this returns something to look at, never
    something that acts.
    """
    rows = [row for row in parsed["applied"]
            if row["status"] in FIT_JUDGEMENTS]
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    total = len(rows)
    return {
        "judged": total,
        "by_status": counts,
        "approved": counts.get(APPROVED, 0),
        "rejected_on_fit": counts.get(BAD_FIT, 0) + counts.get(NOT_RELEVANT, 0),
        "domains": {row["domain"]: row["status"] for row in rows},
        "why": (f"{counts.get(APPROVED, 0)} of {total} judged candidates were "
                "approved" if total else "no fit judgements in this file"),
        # Said here so a reader of the return value cannot mistake it.
        "note": ("An observation about these companies, not a change to the "
                 "ICP. Moving the ICP is an explicit decision a person "
                 "makes."),
    }


# ------------------------------------------------------------------ storage

def path():
    return os.path.abspath(
        os.environ.get("CLIENT_REVIEW")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "clientreview.jsonl"))


def load(workspace=None, file_path=None):
    rows = []
    for entry in store.read_jsonl(file_path or path()):
        if workspace and entry.get("workspace") != workspace:
            continue
        rows.append(entry)
    return rows


def record(entries, file_path=None):
    entries = list(entries)
    for entry in entries:
        if not entry.get("workspace"):
            raise ReviewRefused("a decision must name its workspace")
    file_path = file_path or path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entries


def decided(workspace, file_path=None):
    """domain -> the status the client last gave it.

    Last wins, because a client who sends a corrected file means the
    correction. The earlier row stays in the log.
    """
    out = {}
    for entry in load(workspace, file_path):
        if entry.get("domain"):
            out[entry["domain"]] = entry.get("status")
    return out
