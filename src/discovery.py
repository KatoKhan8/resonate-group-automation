#!/usr/bin/env python3
"""What is genuinely new, and nothing else.

## The only question worth asking

A discovery run that returns companies the client already knows is worse
than one that returns nothing. Nothing costs nothing; a list padded with
the client's own customers costs their trust, and it costs it the first
time they read it.

So the operation here is a **difference**, not a search:

    what a source proposes
      minus everything already known
      minus everything already decided
      = candidates

`known()` builds the second and third terms once, from canonical state,
and `delta()` subtracts. There is no path that returns a candidate without
going through the subtraction.

## What "already known" means

Seven things, and leaving any of them out produces a specific
embarrassment:

    the seed import        "we sent you your own list back"
    later imports          the same, a month later
    prior discovery        "you showed me this last week"
    client review          "I told you they were a client"
    suppression            a live customer, cold-sequenced
    campaign history       already being worked
    the CRM                LIVE CRM CONNECTOR REQUIRED

Six are canonical state this system already holds. The CRM is not
connected, and `known()` says so rather than quietly returning a smaller
universe - a delta computed against an absent CRM is not a smaller delta,
it is a wrong one, and it surfaces the client's open opportunities as
fresh leads.

Agency-wide DNC is **not** in this list and cannot be: it is a
person-level index of hashed mailboxes and profile URLs, and a candidate
is a domain with nobody attached to it yet. It is enforced at `hygiene`,
once contacts exist. `known()` names that too, because "we did not check
this here" and "there was nothing to check" are different sentences and
only one of them is true.

## Identity is the domain, exactly

`ingest.norm_domain` and nothing else. No fuzzy company-name matching:
"Acme Ltd" and "ACME Limited" may be the same company or two competitors,
and the cost of being wrong is asymmetric - a missed duplicate is a
wasted row, a wrong merge sends nothing to somebody who should have heard
from us, or sends to somebody who asked not to.

## Provenance is mandatory

A candidate carries the source that proposed it and the evidence that
source gave. `candidate()` refuses one without both. Nothing here invents
a company: `SOURCES` names the shapes a provider could take and no
provider is connected, so in this build every candidate comes from a
fixture or a manual entry and says so.

    LIVE DISCOVERY PROVIDER REQUIRED

## It spends nothing

Discovery proposes. Enrichment costs money and happens after a human
approves, which is the first of the two gates. Nothing in this module
calls a provider, and there is a test asserting the whole flow from
proposal to approval touches no paid path.
"""
import json
import os

from . import ingest, store

# ------------------------------------------------------------------ sources
#
# Named for what they are, so a candidate can always answer "who said so".
# None of these is connected. The shapes exist because a delta needs to
# record provenance from the first row, not from the day a provider is
# wired up.

MANUAL = "manual"              # somebody typed it in, and is named
IMPORT = "import"              # arrived in a client file
PROVIDER = "provider"          # a discovery source - none is connected
SOURCES = (MANUAL, IMPORT, PROVIDER)

SOURCE_LABEL = {
    MANUAL: "Entered by a person",
    IMPORT: "From a client file",
    PROVIDER: "Discovery source",
}

# ------------------------------------------------- why a candidate is not new
#
# Ordered most-final first. A domain can be several of these at once and
# the operator needs the one that settles it: "they asked us to stop"
# outranks "we imported them in March".

SUPPRESSED = "suppressed"
CLIENT_DECIDED = "client_decided"
IN_CAMPAIGN = "in_campaign"
KNOWN_RECORD = "known_record"
SEEN_BEFORE = "seen_before"
NEW = "new"

VERDICTS = (SUPPRESSED, CLIENT_DECIDED, IN_CAMPAIGN,
            KNOWN_RECORD, SEEN_BEFORE, NEW)

# Agency-wide DNC is deliberately not one of these. It is a
# *person-level* index - hashed mailboxes and profile URLs - and a
# candidate is a domain with nobody attached yet, so there is nothing
# to look up. It is enforced at `hygiene`, once contacts exist. A
# verdict that could never fire would be a claim to check something
# this cannot see.

VERDICT_LABEL = {
    SUPPRESSED: "On the suppression list",
    CLIENT_DECIDED: "The client already ruled on this one",
    IN_CAMPAIGN: "Already in a campaign",
    KNOWN_RECORD: "Already in this workspace",
    SEEN_BEFORE: "Proposed by an earlier run",
    NEW: "New",
}


class DiscoveryRefused(ValueError):
    """The candidate was not accepted, and the message says why."""


MINIMUM_EVIDENCE = 12


def candidate(workspace, domain, *, source=PROVIDER, source_ref=None,
              evidence=None, company=None, run=None, found_by=None,
              at=None, facts=None):
    """One proposed company. Provenance is not optional.

    `evidence` is why this source thinks the company matches - "an agency
    in Berlin with 60 staff listed on their site", not "matched". A
    candidate nobody can question is a candidate nobody can reject, which
    is how a bad list gets approved.
    """
    normalised = ingest.norm_domain(domain)
    # `norm_domain` normalises and does not judge: "not a domain" comes
    # back unchanged. The shape check is separate and shared with the
    # import path.
    if not normalised or not ingest.is_hostname(normalised):
        raise DiscoveryRefused(f"not a usable domain: {domain!r}")
    if source not in SOURCES:
        raise DiscoveryRefused(f"unknown source: {source!r}")
    evidence = (evidence or "").strip()
    if len(evidence) < MINIMUM_EVIDENCE:
        raise DiscoveryRefused(
            "say why this company was proposed - something specific enough "
            "to argue with, like 'digital agency, Berlin, 60 staff listed'")
    return {
        "workspace": workspace,
        "domain": normalised,
        "company": (company or "").strip() or None,
        "source": source,
        "source_ref": (source_ref or "").strip() or None,
        "evidence": evidence[:600],
        "run": run,
        "found_by": found_by,
        "at": at or store.now(),
        # Whatever the source could say about the company, trimmed. Never
        # promoted to a verdict here: `qualify` decides ICP, and a
        # discovery source has no standing to.
        "facts": dict(facts or {}),
    }


# ------------------------------------------------------------ the known universe

def known(repo, seen=None, suppressed=None):
    """Everything a proposal has to be checked against, built once.

    Returned as sets of normalised domains plus a note about what could
    not be consulted. The note is load-bearing: a delta computed without
    the CRM is not a smaller delta, it is a wrong one, and the screen has
    to be able to say so.
    """
    # Read once and index by record id, so the campaign pass is a lookup
    # rather than a scan. Walking every record per campaign is the shape
    # that made the campaign list take ten seconds at 30,000 records.
    records, in_campaign = set(), set()
    domain_of = {}
    for rec in repo.records():
        domain = ingest.norm_domain(rec.get("domain"))
        if not domain:
            continue
        records.add(domain)
        domain_of[rec.get("id")] = domain
    for campaign in repo.campaigns():
        for record_id in campaign.get("record_ids") or []:
            domain = domain_of.get(record_id)
            if domain:
                in_campaign.add(domain)

    # Taken from the caller when it has one, so a weekly run reads the
    # file once rather than once per workspace.
    raw = ingest.load_suppress() if suppressed is None else suppressed
    suppressed = {ingest.norm_domain(d) for d in raw}
    suppressed.discard(None)
    suppressed.discard("")

    previous = {ingest.norm_domain(d) for d in (seen or ())}
    previous.discard(None)

    return {
        "workspace": repo.workspace,
        "records": records,
        "in_campaign": in_campaign,
        "suppressed": suppressed,
        "previous": previous,
        # Named rather than omitted. See the module docstring.
        "unavailable": [
            {"source": "agency_dnc",
             "why": "the agency-wide do-not-contact list is person-level - "
                    "hashed mailboxes and profile URLs - and a candidate "
                    "is a domain with nobody attached yet. It is "
                    "enforced at hygiene, once contacts exist",
             "marker": None},
            {"source": "crm",
             "why": "no CRM connector exists in this build, so open "
                    "opportunities and existing customers recorded only in "
                    "the client's CRM cannot be excluded here",
             "marker": "LIVE CRM CONNECTOR REQUIRED"},
        ],
        "counts": {"records": len(records), "in_campaign": len(in_campaign),
                   "suppressed": len(suppressed),
                   "previous": len(previous)},
    }


def classify(entry, universe, decided=None):
    """Is this candidate new, and if not, what settles it?

    `decided` maps domain -> a client review status, so a company the
    client has already ruled on is never proposed again. It is passed in
    rather than loaded because the review store is the caller's to read,
    and this module must not reach past the repo it was handed.
    """
    domain = entry["domain"]
    if domain in universe["suppressed"]:
        return SUPPRESSED, "on the suppression list"
    if domain in (decided or {}):
        status = (decided or {})[domain]
        return CLIENT_DECIDED, f"the client marked this {status}"
    if domain in universe["in_campaign"]:
        return IN_CAMPAIGN, "already in a campaign"
    if domain in universe["records"]:
        return KNOWN_RECORD, "already in this workspace"
    if domain in universe["previous"]:
        return SEEN_BEFORE, "an earlier discovery run proposed this"
    return NEW, "not known here"


def delta(proposed, universe, decided=None):
    """The difference. Candidates in, candidates and reasons out.

    Two proposals of the same domain inside one run collapse to one: a
    source that lists a company twice has not found it twice, and two rows
    for one company is the shape that makes a review list look bigger than
    it is.
    """
    fresh, excluded, seen = [], [], {}
    for entry in proposed:
        domain = entry["domain"]
        if domain in seen:
            # Keep the first, and record that a second source agreed.
            other = seen[domain]
            if entry["source_ref"] and entry["source_ref"] not in (
                    other.get("also_from") or []):
                other.setdefault("also_from", []).append(entry["source_ref"])
            excluded.append({**entry, "verdict": SEEN_BEFORE,
                             "why": "already proposed in this run"})
            continue
        verdict, why = classify(entry, universe, decided)
        row = {**entry, "verdict": verdict, "why": why}
        if verdict == NEW:
            seen[domain] = row
            fresh.append(row)
        else:
            excluded.append(row)

    by_verdict = {}
    for row in excluded:
        by_verdict[row["verdict"]] = by_verdict.get(row["verdict"], 0) + 1

    return {
        "workspace": universe["workspace"],
        "proposed": len(proposed),
        "new": fresh,
        "excluded": excluded,
        "counts": {
            "proposed": len(proposed),
            "new": len(fresh),
            "already_known": len(excluded),
            **{verdict: by_verdict.get(verdict, 0) for verdict in VERDICTS
               if verdict != NEW},
        },
        "checked_against": universe["counts"],
        "unavailable": universe["unavailable"],
        # Nothing has been enriched, contacted or spent. The first gate is
        # what turns any of this into cost.
        "spent": 0,
    }


# ------------------------------------------------------------------ storage
#
# Runs are append-only. A run is a fact about what was proposed on a day,
# and rewriting one would erase the answer to "did you already show me
# this" - which is the entire question this module exists to answer.

def path():
    return os.path.abspath(
        os.environ.get("DISCOVERY")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "discovery.jsonl"))


def load(workspace=None, file_path=None):
    """Every recorded candidate, oldest first, scoped when asked.

    The workspace filter is the tenancy boundary. One client's discovery
    is not another's to read, and a delta that leaked across workspaces
    would tell a client which companies another client is pursuing.
    """
    rows = []
    for entry in store.read_jsonl(file_path or path()):
        if workspace and entry.get("workspace") != workspace:
            continue
        rows.append(entry)
    return rows


def record(entries, file_path=None):
    """Append candidates. Returns them."""
    entries = list(entries)
    for entry in entries:
        if not entry.get("workspace"):
            raise DiscoveryRefused("a candidate must name its workspace")
        if not entry.get("domain"):
            raise DiscoveryRefused("a candidate must name a domain")
    file_path = file_path or path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entries


def domains_seen(workspace, file_path=None):
    """Every domain any previous run proposed in this workspace."""
    return {row["domain"] for row in load(workspace, file_path)
            if row.get("domain")}


def runs(workspace, file_path=None):
    """What has been proposed, grouped by run, newest first."""
    grouped = {}
    for row in load(workspace, file_path):
        key = row.get("run") or "unnamed"
        found = grouped.setdefault(key, {
            "run": key, "candidates": 0, "at": row.get("at"),
            "sources": set(), "domains": []})
        found["candidates"] += 1
        found["sources"].add(row.get("source"))
        found["domains"].append(row.get("domain"))
        if (row.get("at") or "") > (found["at"] or ""):
            found["at"] = row.get("at")
    out = [{**row, "sources": sorted(s for s in row["sources"] if s)}
           for row in grouped.values()]
    # Timestamp first, then the run label. Two runs recorded in the same
    # second - a seeded fixture, an import, a replay - are otherwise
    # ordered arbitrarily, and "the newest run" is the whole basis for
    # deciding which proposals are this week's.
    return sorted(out, key=lambda r: (r["at"] or "", r["run"]), reverse=True)
