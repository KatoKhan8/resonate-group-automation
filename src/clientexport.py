#!/usr/bin/env python3
"""Build the client-approval export: a CSV of candidate domains for the client.

THE EXPORT / CLEAN / IMPORT CYCLE, the export half.

    1. Select domains that passed S3 ICP, S4b MX and local collision.
    2. Remove everything this client has suppressed or already approved.
    3. Write a CSV with exactly: domain, company, headcount, industry,
       country, website.  NO contacts, NO emails, NO person names.
    4. Record the snapshot so the return file can be diffed.

The columns are the client's own vocabulary for deciding about a domain.
Headcount is the provider's estimate, industry is what the provider stated,
country is where the company is.  Website is the domain itself - the client
knows their own customers by domain, and a URL column would invite the
LinkedIn-profile mistake `client_snapshot.NOT_AN_ACCOUNT` guards against.

TARGET SIZE.  40,000-50,000 domains when supply allows.  A 4,000-row snapshot
is a supply finding, not a failure to pad.  The export reports its count
honestly and never relaxes a filter to reach a target.

PII.  A person's name in a client export handed to a third party is a new
leak.  The columns above carry no person-level data by construction: every
field is a fact about the company, not about anybody who works there.
"""
import csv
import io
import os

from . import clientapproval as ca
from . import export as csv_guard
from . import icp, mx, segments, store

#: The exact columns the client sees.  Order matters: it is what the CSV
#: header reads, and the client's cleaned return must be parseable by
#: `client_snapshot.domains_from` against these same names.
EXPORT_COLUMNS = ("domain", "company", "headcount", "industry", "country",
                  "website")

#: MX statuses that say "we can email this domain".  `known_blocked` and
#: `dns_failure` are not candidates: one is a gateway we must not hit, the
#: other is a channel we cannot confirm.
MX_PASS = (mx.KNOWN_ALLOWED, mx.UNKNOWN_PROVIDER)

#: The supply target.  An export below this count reports honestly; nothing
#: relaxes a filter to reach it.
TARGET_MIN = 40_000
TARGET_MAX = 50_000


def _icp_qualified(rec):
    """S3: the company passed ICP scoring."""
    verdict = (rec.get("qualification") or {}).get("verdict") or {}
    return verdict.get("icp_status") == icp.QUALIFIED


def _mx_passes(domain, config, cache):
    """S4b: the domain's mail is not blocked by a recognised gateway."""
    try:
        decision = mx.for_domain(domain, config, cache=cache, save=False)
    except Exception:
        return False
    return (decision or {}).get("status") in MX_PASS


def _locally_clear(domain, history):
    """No prior engagement in our own estate at this domain.

    This is the local half of collision: have WE already worked this company?
    The provider half - has the CLIENT's estate worked it? - is a live check
    that belongs in the sourcing pipeline, not in a CSV export.
    """
    if not history:
        return True
    entries = history.get("by_domain", {}).get(domain, [])
    for entry in entries:
        if any(c.get("confirmed_touches") for c in entry.get("contacts", [])):
            return False
        if entry.get("account_state") == "suppress":
            return False
    return True


def _row_for(rec, segment):
    """One export row from a record and its segment.  Company-level only."""
    facts = (rec or {}).get("company_facts") or {}
    employees = facts.get("employees")
    return {
        "domain": rec.get("domain", ""),
        "company": rec.get("company", ""),
        "headcount": employees if employees is not None else "",
        "industry": facts.get("industry") or "",
        "country": segment.get("country") or "",
        "website": rec.get("domain", ""),
    }


def build_candidate_list(recs, config, client, history=None, mx_cache=None):
    """Select the domains eligible for this client's next export.

    Returns `(rows, supply_note)` where `rows` is a list of export dicts and
    `supply_note` describes the count honestly.

    A domain is eligible when:
      - the record belongs to this client
      - S3 ICP is qualified
      - S4b MX is known_allowed or unknown_provider
      - local collision is clear (no prior engagement in our estate)
      - the domain is not suppressed by this client
      - the domain is not already approved by this client
    """
    if mx_cache is None:
        mx_cache = {}
    suppressed = ca.suppressed_domains(client)
    approved = ca.approved_domains(client)

    rows = []
    seen = set()
    skipped_icp = 0
    skipped_mx = 0
    skipped_collision = 0
    skipped_suppressed = 0
    skipped_approved = 0

    for rec in recs:
        if rec.get("client") != client:
            continue
        domain = (rec.get("domain") or "").strip().lower()
        if not domain or domain in seen:
            continue

        if not _icp_qualified(rec):
            skipped_icp += 1
            continue

        if ca.account_of(domain) in suppressed:
            skipped_suppressed += 1
            continue
        if ca.account_of(domain) in approved:
            skipped_approved += 1
            continue

        if not _mx_passes(domain, config, mx_cache):
            skipped_mx += 1
            continue

        if not _locally_clear(domain, history):
            skipped_collision += 1
            continue

        seen.add(domain)
        segment = segments.classify(rec, config)
        rows.append(_row_for(rec, segment))

    total_skipped = (skipped_icp + skipped_mx + skipped_collision
                     + skipped_suppressed + skipped_approved)
    note = (f"{len(rows)} candidate(s) from {len(recs)} record(s); "
            f"skipped {total_skipped} "
            f"(icp={skipped_icp}, mx={skipped_mx}, "
            f"collision={skipped_collision}, "
            f"suppressed={skipped_suppressed}, "
            f"already_approved={skipped_approved})")
    if len(rows) < TARGET_MIN:
        note += (f"; supply below target of {TARGET_MIN:,}-"
                 f"{TARGET_MAX:,}, reported as-is")
    return rows, note


def to_csv(rows):
    """Render the export rows as a CSV string, formula-guarded."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(csv_guard.safe_row(list(EXPORT_COLUMNS)))
    for row in rows:
        writer.writerow(csv_guard.safe_row(
            [row.get(col, "") for col in EXPORT_COLUMNS]))
    return buf.getvalue()


def write_csv(rows, path):
    """Write the export to disk, formula-guarded."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_csv(rows))
    return path


def build_export(recs, config, client, snapshot_id, history=None,
                 mx_cache=None, at=None, note=None):
    """The whole export: build, write, record the snapshot.

    Returns `{"rows": [...], "csv": "<path>", "snapshot": {...},
              "supply_note": "..."}`.

    The snapshot is recorded through `clientapproval.record_snapshot`, which
    refuses a re-used id.  The CSV is written through `export.write_csv`,
    which formula-guards every cell.
    """
    rows, supply_note = build_candidate_list(
        recs, config, client, history=history, mx_cache=mx_cache)
    domains = [r["domain"] for r in rows]
    snap = ca.record_snapshot(snapshot_id, domains, client=client, at=at,
                              note=note)
    return {"rows": rows, "snapshot": snap, "supply_note": supply_note,
            "count": len(rows)}
