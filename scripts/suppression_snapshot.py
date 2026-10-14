"""Assemble the provider's per-lead suppression snapshot from STORED STATE, and
measure `suppression.reconcile` / `reconcile_all` against it.

WHY THIS EXISTS. `docs/SUPPRESSION-MEASUREMENT-2026-10-14.md` section 6a says
EmailBison keeps a second suppression list, that the LIST ITSELF cannot be read
(`/blocklist/emails` and `/blocklist/domains` are 404, and `src/providers/bison.py`
declares no such route), and that what IS readable is the EFFECT, per lead. It
then says the reconciliation "is tested, never measured, because no snapshot has
been taken". This builds that snapshot from what is already on disk, so §6a can
be measured by name.

NO PROVIDER CALL IS MADE AND NO PROVIDER STATE IS WRITTEN. Every byte read here
is a file some earlier provider read left behind. That is the whole point: the
measurement is owed and a provider call is not this script's to make.

TWO OUTPUTS, BECAUSE ONE OF THEM HOLDS REAL ADDRESSES.

  * The FULL snapshot carries plaintext email addresses, so it is written into
    `work/`, which is gitignored for exactly this reason. It is 300 real
    companies' people and it is not ours to publish.
  * The SANITISED snapshot carries `agencydnc.fingerprint` digests, counts and
    provenance - enough to know what was measured and to re-run it, and
    deliberately not enough to rebuild the prospect list. That one may go in
    git, beside `QUEUE-MANIFEST.json`, which exists on the same reasoning.

A MISSING SOURCE IS REPORTED, NEVER SKIPPED. `store.read_jsonl` answers a
missing file with an empty list, which would make "the file is gone" read as
"nobody is suppressed there" - invariant 0, and the exact shape this repository
keeps rediscovering. Every source is stat'd before it is read and a source that
is absent makes the run FAIL rather than shrink.

THE JOIN IS `bison_lead_id`. The stored provider rows carry a lead id and no
address; the queue's contacts carry both. 805 of 1,381 production contacts
carry a `bison_lead_id`, so the join is the ceiling on what this snapshot can
cover and the report says so rather than reporting the covered part alone.
"""

import argparse
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import agencydnc, dedupe, store, suppression          # noqa: E402

# ------------------------------------------------------------------ sources
#
# Each entry names a file that an earlier PROVIDER READ wrote, and how to get
# `(lead_id, status)` pairs out of it. Declared as data rather than inlined so
# that a source which is absent is NAMED in the report - a reader that silently
# skipped one would report a smaller snapshot as a clean one.
#
# `required` is True for every source that was present when this was written.
# A new deployment with fewer files should fail loudly and have the entry
# removed deliberately, not degrade quietly.


def _pc_leads(row):
    """`stage/pc-leads.jsonl`: one row per lead, with campaign memberships."""
    lead = row.get("lead_id")
    for member in row.get("memberships") or []:
        yield lead, member.get("status"), member.get("campaign_id")


def _queue_rows(row):
    """`stage/pc-sends.jsonl`, `stage/pc-lead-sends.jsonl`: one scheduled row."""
    yield row.get("lead_id"), row.get("status"), row.get("campaign_id")


def _reengagement(row):
    """`stage/reengagement-inventory.jsonl`: one row per lead per campaign."""
    yield row.get("lead_id"), row.get("state"), row.get("campaign_id")


SOURCES = (
    {"path": ("stage", "pc-leads.jsonl"), "reader": _pc_leads,
     "witness": "campaign membership", "required": True},
    {"path": ("stage", "pc-sends.jsonl"), "reader": _queue_rows,
     "witness": "queue row", "required": True},
    {"path": ("stage", "pc-lead-sends.jsonl"), "reader": _queue_rows,
     "witness": "queue row", "required": True},
    {"path": ("stage", "reengagement-inventory.jsonl"), "reader": _reengagement,
     "witness": "campaign membership", "required": True},
)

#: Read directly for its address - the one stored file that carries an email
#: beside a provider status, so it needs no join. Two rows today; included
#: because a source that is small is not a source that is absent.
OBSERVATIONS = ("lead-observations.jsonl",)


class MissingSource(RuntimeError):
    """A declared source is not on disk. The run refuses rather than shrinks."""


def _stat(path):
    info = os.stat(path)
    return {"bytes": info.st_size,
            "mtime": datetime.datetime.fromtimestamp(
                info.st_mtime, datetime.timezone.utc).isoformat()}


def _rows(path):
    """Every JSON line, with unreadable lines COUNTED rather than dropped."""
    good, damaged = [], 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                good.append(json.loads(line))
            except ValueError:
                damaged += 1
    return good, damaged


# -------------------------------------------------------------------- join

def lead_id_to_email(records):
    """`bison_lead_id` -> the set of normalised addresses that claim it.

    A set, not a string: two contacts claiming one provider lead id is a real
    possibility and silently keeping the last one would be a wrong merge, which
    at this layer means suppressing or clearing the wrong person.
    """
    out = collections.defaultdict(set)
    contacts = 0
    with_id = 0
    with_email = 0
    for rec in records:
        for contact in rec.get("contacts") or []:
            contacts += 1
            lead = contact.get("bison_lead_id")
            email = dedupe.normalise_email(contact.get("email"))
            if lead not in (None, "", 0):
                with_id += 1
            if email:
                with_email += 1
            if lead not in (None, "", 0) and email:
                out[str(lead)].add(email)
    census = {"contacts": contacts, "with_bison_lead_id": with_id,
              "with_email": with_email,
              "joinable": sum(len(v) for v in out.values()),
              "distinct_lead_ids": len(out)}
    return out, census


# ---------------------------------------------------------------- assembly

def assemble(work):
    """Build the snapshot. Returns `(snapshot, provenance)`."""
    provenance = {"work": work, "sources": [], "absent": []}

    #: lead id -> {status -> [(source, campaign_id), ...]}
    by_lead = collections.defaultdict(lambda: collections.defaultdict(list))
    #: email -> {status -> [(source, campaign_id), ...]}, for sources that
    #: carry an address and so need no join.
    direct = collections.defaultdict(lambda: collections.defaultdict(list))

    for source in SOURCES:
        # Forward slashes in the recorded name, backslashes only in the path
        # actually opened: the sanitised artifact is committed, and a provenance
        # entry reading `stage\pc-leads.jsonl` would be a Windows path in git.
        rel = "/".join(source["path"])
        path = os.path.join(work, *source["path"])
        if not os.path.exists(path):
            provenance["absent"].append(rel)
            if source["required"]:
                raise MissingSource(
                    "declared source is not on disk: %s - a snapshot built "
                    "without it would be smaller and would not say so" % path)
            continue
        rows, damaged = _rows(path)
        pairs = 0
        for row in rows:
            for lead, status, campaign in source["reader"](row):
                if lead in (None, "", 0):
                    continue
                text = str(status or "").strip().lower()
                if not text:
                    continue
                by_lead[str(lead)][text].append((rel, campaign))
                pairs += 1
        entry = {"path": rel, "rows": len(rows), "damaged_lines": damaged,
                 "status_pairs": pairs, "witness": source["witness"]}
        entry.update(_stat(path))
        provenance["sources"].append(entry)

    for name in OBSERVATIONS:
        path = os.path.join(work, name)
        if not os.path.exists(path):
            provenance["absent"].append(name)
            continue
        rows, damaged = _rows(path)
        pairs = 0
        for row in rows:
            email = dedupe.normalise_email(row.get("email"))
            status = str(row.get("raw_status") or row.get("state")
                         or "").strip().lower()
            if not (email and status):
                continue
            direct[email][status].append((name, row.get("campaign_id")))
            pairs += 1
        entry = {"path": name, "rows": len(rows), "damaged_lines": damaged,
                 "status_pairs": pairs, "witness": "lead observation (keyed "
                 "on email, no join needed)"}
        entry.update(_stat(path))
        provenance["sources"].append(entry)

    queue = os.path.join(work, "queue.jsonl")
    if not os.path.exists(queue):
        raise MissingSource("no queue at %s - the join key lives there" % queue)
    records = store.read_jsonl(queue)
    joined, census = lead_id_to_email(records)
    entry = {"path": "queue.jsonl", "rows": len(records),
             "damaged_lines": 0, "witness": "the join key (bison_lead_id)"}
    entry.update(_stat(queue))
    provenance["sources"].append(entry)
    provenance["join"] = census

    #: email -> {status: [{"source":..., "campaign_id":...}, ...]}
    snapshot = collections.defaultdict(lambda: collections.defaultdict(list))
    matched_leads = set()
    for lead, statuses in by_lead.items():
        emails = joined.get(lead)
        if not emails:
            continue
        matched_leads.add(lead)
        for email in emails:
            for status, where in statuses.items():
                for src, campaign in where:
                    snapshot[email][status].append(
                        {"source": src, "campaign_id": campaign,
                         "bison_lead_id": lead})
    for email, statuses in direct.items():
        for status, where in statuses.items():
            for src, campaign in where:
                snapshot[email][status].append(
                    {"source": src, "campaign_id": campaign,
                     "bison_lead_id": None})

    provenance["coverage"] = {
        "provider_lead_ids_in_stored_state": len(by_lead),
        "provider_lead_ids_joined_to_an_email": len(matched_leads),
        "provider_lead_ids_we_cannot_name": len(by_lead) - len(matched_leads),
        "emails_in_snapshot": len(snapshot),
    }

    vocabulary = collections.Counter()
    for statuses in snapshot.values():
        for status, where in statuses.items():
            vocabulary[status] += len(where)
    provenance["vocabulary"] = dict(vocabulary.most_common())
    provenance["vocabulary_classified"] = {
        "provider_stopped": sorted(
            s for s in vocabulary if s in suppression.PROVIDER_STOPPED),
        "provider_active": sorted(
            s for s in vocabulary if s in suppression.PROVIDER_ACTIVE),
        "in_neither_set": sorted(
            s for s in vocabulary
            if s not in suppression.PROVIDER_STOPPED
            and s not in suppression.PROVIDER_ACTIVE),
    }
    return {k: dict(v) for k, v in snapshot.items()}, provenance


# ------------------------------------------------------------- measurement
#
# `reconcile` takes ONE status string per person, and a person can carry
# several - 749 of them carry between one and five. There is no single
# precedence that is conservative in both directions:
#
#   * For somebody WE have stopped, a NON-stopped provider status is the
#     dangerous reading (`SUPPRESSED_HERE_ONLY` - the provider is still
#     sending). A "prefer a stop" precedence would hide it.
#   * For somebody we have NOT stopped, a STOPPED provider status is the
#     finding (`BLOCKED_THERE_ONLY`). A "prefer an active status" precedence
#     would hide that one instead.
#
# So the reduction is not chosen in advance: `reconcile` is asked once per
# distinct status the person carries and the MOST SEVERE answer is kept. Then
# `reconcile_all` - §6a's estate-level entry point - is handed exactly the
# status that produced that answer, and must reproduce it. That second run is
# a control on `reconcile_all`'s own key handling, not an independent
# measurement, and it is reported as such.

SEVERITY = {suppression.SUPPRESSED_HERE_ONLY: 3,
            suppression.BLOCKED_THERE_ONLY: 2,
            suppression.UNKNOWN_THERE: 1,
            suppression.AGREE: 0}


def measure(records, snapshot, config=None, now=None):
    """Fan `reconcile` out over every status a person carries. Worst wins."""
    findings = collections.Counter()
    per_person = []
    worst_status = {}
    fanned = 0
    for rec in records:
        for contact in rec.get("contacts") or []:
            email = dedupe.normalise_email(contact.get("email"))
            statuses = sorted((snapshot.get(email) or {}) if email else {})
            candidates = statuses or [None]
            best = None
            for status in candidates:
                fanned += 1
                finding, detail = suppression.reconcile(
                    rec, contact, provider_status=status, config=config,
                    now=now)
                rank = SEVERITY[finding]
                if best is None or rank > best[0]:
                    best = (rank, finding, status, detail)
            _, finding, status, detail = best
            findings[finding] += 1
            if email and status is not None:
                worst_status[email] = status
            per_person.append({
                "rec_id": rec.get("id"), "contact_key": contact.get("key"),
                "email_fingerprint": (agencydnc.fingerprint("email", email)
                                      if email else None),
                "finding": finding,
                "statuses_seen": statuses,
                "status_used": status,
                "ours": detail.get("ours"),
                "our_reasons": detail.get("our_reasons")})
    return {"findings": dict(findings), "people": per_person,
            "reconcile_calls": fanned, "worst_status_by_email": worst_status}


def control(records, worst_status, config=None, now=None):
    """`reconcile_all` over the same estate, handed the same statuses."""
    grouped = suppression.reconcile_all(records, worst_status, config=config,
                                        now=now)
    return {kind: len(rows) for kind, rows in grouped.items()}


# ------------------------------------------------------------------- output

def sanitise(snapshot, provenance, result, control_counts):
    """The git-safe artifact: digests, counts and provenance. No addresses."""
    return {
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "what": "EmailBison per-lead suppression effect, assembled from STORED "
                "state. NOT the provider's blacklist, which is unreadable - "
                "see docs/SUPPRESSION-MEASUREMENT-2026-10-14.md section 6a.",
        "provider_call_made": False,
        "unknown_is_not_a_pass": suppression.UNKNOWN_IS_NOT_A_PASS,
        "provenance": provenance,
        "snapshot": {
            "entries": len(snapshot),
            "by_email_fingerprint": {
                agencydnc.fingerprint("email", email): sorted(statuses)
                for email, statuses in sorted(snapshot.items())},
        },
        "measurement": {
            "reconcile_calls": result["reconcile_calls"],
            "findings": result["findings"],
            "reconcile_all_control": control_counts,
            "control_agrees": control_counts == _padded(result["findings"]),
        },
    }


def _padded(findings):
    return {kind: findings.get(kind, 0) for kind in suppression.RECONCILIATION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work", default=None,
        help="the work directory to read. Defaults to the MAIN checkout's, "
             "because a worktree's own work/ is gitignored and empty.")
    parser.add_argument(
        "--suppress-local", default=None,
        help="path to config/suppress.local.txt. REQUIRED from a worktree: the "
             "file is gitignored, `suppression.reconcile` has no parameter for "
             "it, and reading a shorter roster would understate our own side.")
    parser.add_argument("--full-out", default=None,
                        help="full snapshot WITH addresses. Must be under work/.")
    parser.add_argument("--sanitised-out", default=None,
                        help="git-safe snapshot, fingerprints only.")
    args = parser.parse_args(argv)

    work = args.work or store.main_checkout_work() or store.PRODUCTION_WORK
    work = os.path.abspath(work)

    # OUR OWN SIDE IS READ FROM DISK AND THERE IS NO PARAMETER FOR IT.
    # `reconcile` calls `decide`, which calls `eligibility.must_not_contact`,
    # which calls `ingest.load_suppress()`. `ingest.SUPPRESS_LOCAL` is anchored
    # to the repository ROOT, and a worktree has no `config/suppress.local.txt`
    # because it is gitignored. So from a worktree the roster is SHORTER than
    # production's unless it is pointed at the real one - and a shorter roster
    # understates how many people we have stopped, which is the half of the
    # reconciliation that produces `SUPPRESSED_HERE_ONLY`.
    from src import ingest
    roster = {"suppress": ingest.SUPPRESS, "suppress_local": ingest.SUPPRESS_LOCAL}
    if args.suppress_local:
        ingest.SUPPRESS_LOCAL = os.path.abspath(args.suppress_local)
        roster["suppress_local"] = ingest.SUPPRESS_LOCAL
    roster["suppress_exists"] = os.path.exists(ingest.SUPPRESS)
    roster["suppress_local_exists"] = os.path.exists(ingest.SUPPRESS_LOCAL)
    roster["domains_loaded"] = len(ingest.load_suppress())

    # The agency DNC ledger and the queue follow `store.queue_path()`, so one
    # redirect moves both at once.
    os.environ["QUEUE"] = os.path.join(work, "queue.jsonl")

    snapshot, provenance = assemble(work)
    provenance["our_side"] = roster
    provenance["agency_dnc"] = agencydnc.path()

    records = store.read_jsonl(os.path.join(work, "queue.jsonl"))
    suppression.reset_consultations()
    result = measure(records, snapshot)
    consulted = len(suppression.consultations())
    control_counts = control(records, result["worst_status_by_email"])

    report = sanitise(snapshot, provenance, result, control_counts)
    report["measurement"]["consultations_recorded"] = consulted

    if args.full_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.full_out)),
                    exist_ok=True)
        with open(args.full_out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"provenance": provenance, "snapshot": snapshot,
                       "people": result["people"]}, handle, indent=1,
                      sort_keys=True)
    if args.sanitised_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.sanitised_out)),
                    exist_ok=True)
        with open(args.sanitised_out, "w", encoding="utf-8",
                  newline="\n") as handle:
            json.dump(report, handle, indent=1, sort_keys=True)

    json.dump(report["measurement"], sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    json.dump({"coverage": provenance["coverage"],
               "join": provenance["join"],
               "vocabulary": provenance["vocabulary"],
               "vocabulary_classified": provenance["vocabulary_classified"],
               "our_side": roster}, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
