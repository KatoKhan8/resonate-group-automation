#!/usr/bin/env py -3
"""CANARY-01 criterion 7, in its PER-CAMPAIGN form: the attached pool, read
back and resolved to one owner.

TASK 0200 (pilotcaps), 2026-10-16. Nothing here attaches anything, and
nothing here dials a provider: `main()` has no live mode at all, by
construction, for the reason in THE RESOLUTION STEP below.

WHAT CRITERION 7 ACTUALLY SAYS. "One owner across the ATTACHED pool." The
instrument TASK 0190 repaired answers the ESTATE-wide form - are all 181
mailboxes one owner - and that is a different question with a different
authority. A campaign is attached to a SUBSET, the subset is what signs the
bodies, and an eleventh sender nobody approved is exactly the failure this
criterion exists to catch. So the check is per campaign or it is not the
check.

THE RESOLUTION STEP, STATED EXPLICITLY, BECAUSE THE BRIEF ASKS WHICH CALL
MAKES IT. `bison.campaign_senders(campaign_id)` returns membership **ids
only** - no address, no display name, no signature - so a read-back needs a
second step to turn an id into an address and an owner. Measured at the
transport seam (no network; see `work/probe_0200_fence.py` and the report):

    bison.campaign_senders(499)  ->  GET /api/campaigns/499/sender-emails
    bison.sender_emails()        ->  GET /api/sender-emails          (13 pages)

There is **no per-id endpoint** in the adapter: of its 62 public callables
the only sender reads are those two, and `sender_emails` takes no id
argument (`per_page=None, expect_workspace=None`). So the resolution is a
join of the membership ids onto the estate walk - and the estate walk was
already made, once, under the operator's 2026-10-15 23:00 authorisation. All
ten approved pool ids are in those recorded 181 rows.

**So the resolution step is entirely OFFLINE and costs no provider call.**
That is why this module takes `estate_rows` as an argument and never fetches
them: the recorded walk is the authority, and a function that could silently
dial is a function that will.

WHAT IS STILL NOT OFFLINE, AND IT IS THE WHOLE REMAINING BLOCKER. The
MEMBERSHIP is not. Nothing is attached - there is no canary campaign, at the
provider or in `work/campaigns.jsonl` - so there is no membership to read
back, no recorded read-back file, and `campaign_senders` is a second
endpoint outside the spent authorisation. Membership is therefore UNKNOWN
today, and `verdict_for_campaign` returns UNKNOWN for it rather than
treating an absent list as an empty pool. An empty pool is not one owner and
an unread pool is not an empty one.

THE FENCE MATCHES THE FULL PATH, NOT THE LEAF - and that is a repair, not a
preference. See `fence_0180_leaf_verdict`.
"""
import argparse
import hashlib
import json
import os
import sys
import posixpath
from collections import Counter
from urllib.parse import urlsplit, parse_qsl, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# THE LADDER HAS ONE AUTHORITY AND IT IS TASK 0190's MODULE.
#
# Importing a test module from a script is backwards and it is deliberate.
# The owner ladder - the shape of a signature block, what "unreadable" means
# as against "ownerless", and the four refusals - IS the instrument, it was
# measured and mutation-proven there, and re-implementing any part of it here
# would rebuild the defect 0190 fixed with better arithmetic. The repository's
# own rule: "a control that exercises a re-implementation of the instrument is
# not a control."
#
# The import has a second, useful consequence. `tests/__init__` installs a
# credential firewall at package import: `providers.ENV_FILE` is pointed at a
# path that cannot exist and every credential variable is popped from the
# environment. So importing this module makes a live provider call fail with a
# loud `MissingKey` rather than quietly succeed. For an offline read-back that
# is exactly the right floor.
from tests.test_every_body_is_signed_by_the_pools_owner import (  # noqa: E402
    PROVIDER_SIGNATURE_FIELD,
    OwnerlessMailbox,
    PoolEmpty,
    PoolNotOneOwner,
    SignatureFieldMissing,
    estate_row_from_provider,
    pool_owner,
)

# --- what the provider routes actually are, measured ----------------------

#: `GET /api/sender-emails` - the estate walk, the ONE endpoint the operator
#: authorised on 2026-10-15 23:00. Spent.
ROUTE_ESTATE = "/api/sender-emails"

#: `GET /api/campaigns/{id}/sender-emails` - what `bison.campaign_senders`
#: hits. MEASURED at the transport seam, never read off the adapter's source.
#: Note the leaf: it is `sender-emails`, the same leaf as the estate walk.
ROUTE_CAMPAIGN_SENDERS = "/api/campaigns/{campaign_id}/sender-emails"

#: The path `CANARY-01-ATTACH-PAYLOAD-2026-10-15.md` §4A and TASK 0180's third
#: negative control both named. The adapter generates it NOWHERE. Kept so the
#: test can prove the control was a straw path rather than assert it.
ROUTE_NOBODY_GENERATES = "/api/campaigns/{campaign_id}/senders"

# --- the approved pool ----------------------------------------------------

#: The ten `sender_email_ids` of CANARY-01's approved pool. Authority:
#: `resonate-ops/DECISION-canary-cohort-and-pool-2026-10-15.md` §2, resolved
#: from allowlist group to provider ids by TASK 0180 and recorded in
#: `docs/CANARY-01-SENDER-EMAILS-LIVE-READ-2026-10-15.md`. Ids only - the
#: addresses are on the approval sheet, outside git, and stay there.
APPROVED_POOL = (2763, 2760, 2751, 2750, 2778, 2772, 2748, 2745, 2741, 2775)

#: Approved but NOT in the pool. Named because "the ten" and "the twelve rows
#: for that local-part" are different sets and conflating them would let a
#: reserve read as an approved attach.
RESERVES_NOT_IN_POOL = (2757, 2766)

#: The px the pool must attest: the px of the live client config's
#: `sender.name`, which is what every approved body signs. Equal on all ten
#: mailboxes' `name` and `email_signature` as measured by TASK 0180.
APPROVED_OWNER_PX = "px-fc7d1255b8a3"

# --- verdicts -------------------------------------------------------------

MET = "MET"
NOT_MET = "NOT MET"
UNKNOWN = "UNKNOWN"

#: UNKNOWN dominates. If any rung could not be evaluated, the campaign is
#: UNKNOWN even when another rung positively failed - because a verdict built
#: on a partial reading is the defect this project keeps rediscovering, and
#: UNKNOWN never becomes PASS. MET requires every rung evaluated and clean.
_PRECEDENCE = {UNKNOWN: 2, NOT_MET: 1, MET: 0}


def worst(verdicts):
    """The dominant verdict of a set. Empty is UNKNOWN, never MET."""
    if not verdicts:
        return UNKNOWN
    return max(verdicts, key=lambda v: _PRECEDENCE[v])


# --- step 1: resolve ids to rows -----------------------------------------

def resolve(ids, estate_rows):
    """Join membership ids onto an estate walk.

    Returns `(resolved, unresolved, duplicated)`:

      resolved     [provider row, ...] in the order `ids` gave them
      unresolved   [id, ...] with no row in this walk - NEVER dropped and
                   never treated as absent-from-the-estate, because a short
                   walk and a departed mailbox are indistinguishable here
      duplicated   [id, ...] appearing more than once in `ids`

    No provider call. `estate_rows` is the recorded walk.
    """
    by_id = {}
    for row in estate_rows:
        by_id[row.get("id")] = row
    seen = Counter(ids)
    resolved, unresolved = [], []
    for sender_id in ids:
        row = by_id.get(sender_id)
        if row is None:
            unresolved.append(sender_id)
        else:
            resolved.append(row)
    return resolved, unresolved, sorted(i for i, n in seen.items() if n > 1)


# --- step 2: the per-campaign verdict ------------------------------------

def verdict_for_campaign(campaign_id, membership, estate_rows,
                         estate_total=None, approved_ids=APPROVED_POOL,
                         expected_px=APPROVED_OWNER_PX):
    """Criterion 7 for ONE campaign. Returns a dict, never raises.

    `membership` is the sender ids `bison.campaign_senders(campaign_id)`
    returned, or **None** when no read-back was made. None is UNKNOWN; it is
    not an empty pool.

    `estate_total` is the walk's `meta.total`. When it is given and does not
    equal `len(estate_rows)` the estate is a SAMPLE, and a sample cannot
    resolve an id's absence - so everything below is UNKNOWN. A short walk can
    only undercount, and an undercount reads as "this id is not in the
    estate", which would be a loud failure invented out of a partial read.

    Every reason found is reported, not just the first, so a human reads the
    whole state of the campaign rather than the earliest rung.
    """
    found = []
    expected = sorted(set(approved_ids))

    def note(verdict, reason):
        found.append({"verdict": verdict, "reason": reason})

    # rung 0 - is the estate itself evidence?
    if estate_total is not None and len(estate_rows) != estate_total:
        note(UNKNOWN,
             f"the estate walk is partial: {len(estate_rows)} rows against "
             f"meta.total {estate_total}. A sample cannot resolve an id's "
             f"absence, so no membership id can be judged")
    # rung 1 - was the membership read at all?
    if membership is None:
        note(UNKNOWN,
             f"no read-back of campaign {campaign_id}'s senders exists. "
             f"{ROUTE_CAMPAIGN_SENDERS.format(campaign_id=campaign_id)} is "
             f"outside the spent 2026-10-15 23:00 authorisation and no "
             f"recorded read-back file was supplied. An unread pool is not "
             f"an empty one")
        return _assemble(campaign_id, membership, expected, found, None)

    attached = list(membership)
    # rung 2 - an empty pool is not one owner
    if not attached:
        note(UNKNOWN,
             f"campaign {campaign_id} has no senders attached; an empty pool "
             f"attests no owner, and {PoolEmpty.__name__} is a refusal rather "
             f"than a pass")

    resolved, unresolved, duplicated = resolve(attached, estate_rows)
    # rung 3 - could every attached id be resolved to a mailbox?
    if unresolved:
        note(UNKNOWN,
             f"attached sender id(s) {unresolved} resolve to no row in this "
             f"estate walk, so their owner is unreadable. UNKNOWN is never a "
             f"pass and never 'not in the estate'")
    if duplicated:
        note(UNKNOWN,
             f"the read-back lists id(s) {duplicated} more than once; a "
             f"membership that cannot be read as a set is not a pool")

    # rung 4 - did the authority carry the field at all?
    ladder_rows, missing_field = [], []
    for row in resolved:
        try:
            ladder_rows.append(estate_row_from_provider(row))
        except SignatureFieldMissing as exc:
            missing_field.append(str(exc).split(";")[0])
    if missing_field:
        note(UNKNOWN,
             f"the provider rows carry no {PROVIDER_SIGNATURE_FIELD!r}: "
             f"{missing_field}. An absent authority is UNKNOWN; the "
             f"instrument has lost its basis and says so")

    # rung 5 - one owner across what IS resolved
    owner = None
    if ladder_rows:
        unreadable = [r["id"] for r in ladder_rows if r.get("unreadable")]
        if unreadable:
            note(UNKNOWN,
                 f"mailbox(es) {unreadable} carry a signature this code "
                 f"cannot read; the shape changed or the reader is wrong, "
                 f"and either way the owner is UNKNOWN")
        try:
            owner = pool_owner(ladder_rows)
        except OwnerlessMailbox as exc:
            # A block with no text at all is a MEASURED fact about the
            # mailbox, not an unreadable authority. So this is NOT MET.
            note(NOT_MET, f"{exc}")
        except PoolNotOneOwner as exc:
            note(NOT_MET, f"{exc}")
        except PoolEmpty as exc:
            note(UNKNOWN, f"{exc}")
        # rung 6 - and is it the owner the bodies are signed by?
        if owner is not None and owner != expected_px:
            note(NOT_MET,
                 f"the attached pool's single owner is {owner}, and every "
                 f"approved body signs {expected_px}")

    # rung 7 - is the attached set the approved set, exactly?
    if membership is not None:
        extra = sorted(set(attached) - set(expected))
        absent = sorted(set(expected) - set(attached))
        if extra:
            note(NOT_MET,
                 f"sender id(s) {extra} are attached and were not approved; "
                 f"an unapproved sender is a second-owner risk and is the "
                 f"failure this criterion exists to catch")
        if absent:
            note(NOT_MET,
                 f"approved sender id(s) {absent} are not attached; the "
                 f"attach did not land in full")

    return _assemble(campaign_id, membership, expected, found, owner)


def _assemble(campaign_id, membership, expected, found, owner):
    verdict = (MET if not found
               else worst([f["verdict"] for f in found]))
    return {
        "campaign_id": campaign_id,
        "verdict": verdict,
        "owner_px": owner,
        "expected_owner_px": APPROVED_OWNER_PX,
        "attached": None if membership is None else sorted(set(membership)),
        "approved": expected,
        "findings": found,
    }


def verdict_over_campaigns(scope, estate_rows, estate_total=None, **kw):
    """Criterion 7 over every campaign in scope.

    `scope` maps campaign id -> membership (or None for "not read"). An
    EMPTY scope is UNKNOWN, never MET: "no campaign failed" is a statement
    about the scope and not about the estate, and it is the exact shape of
    the defect TASK 0190 found - an instrument reporting ok while seeing
    nothing.
    """
    per = {cid: verdict_for_campaign(cid, membership, estate_rows,
                                     estate_total=estate_total, **kw)
           for cid, membership in sorted(scope.items())}
    if not per:
        overall = {
            "verdict": UNKNOWN,
            "reason": "the scope holds no campaign, so nothing was examined; "
                      "an empty scope proves nothing and is never MET",
        }
    else:
        overall = {"verdict": worst([v["verdict"] for v in per.values()]),
                   "reason": "the dominant verdict over %d campaign(s)"
                             % len(per)}
    return {"criterion": 7, "per_campaign": per, "overall": overall}


# --- the fence ------------------------------------------------------------

class OutsideAuthorisation(Exception):
    """A request this process is not authorised to make. Nothing was sent."""


def fence_0180_leaf_verdict(method, url, body, allowed_leaf="sender-emails",
                            allowed_method="GET"):
    """TASK 0180's fence predicate, kept VERBATIM as a control.

    MEASURED DEFECT, TASK 0200. 0180 enforced its one-endpoint authorisation
    by comparing the path's LAST SEGMENT. `bison.campaign_senders` hits
    `/api/campaigns/{id}/sender-emails`, whose last segment is also
    `sender-emails` - so this predicate returns ALLOWED for a second
    endpoint that the authorisation did not cover.

    It was not breached in fact: 0180's own self-check records 13 requests,
    `distinct_paths == ['/api/sender-emails']`, nothing refused during the
    read. What failed is the PROOF of narrowness. Of the three negative
    controls, the one meant to cover this - `GET /api/campaigns/499/senders`
    - names a path no adapter in this repository generates, so it refused on
    a leaf (`senders`) that could never have arrived and said nothing about
    the one neighbouring route that exists.

    Kept here rather than deleted because `path_exact_fence` below is only
    provably a repair if the thing it repairs can still be run.
    """
    parts = urlsplit(url)
    leaf = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if (str(method).upper() != allowed_method or leaf != allowed_leaf
            or bool(body)):
        return "REFUSED_BY_FENCE"
    return "ALLOWED"


def is_canonical_path(path):
    """THE RULE, in one sentence: a path is compared WHOLE and only in
    canonical form - any path that is not byte-identical to its own
    normalisation is REFUSED rather than normalised.

    WHY REFUSE RATHER THAN NORMALISE, which is the obvious cleanup and is
    wrong. `/api/campaigns/499/../../sender-emails` normalises to
    `/api/sender-emails`. A fence that canonicalised before comparing would
    ALLOW it - while the raw string is what a server receives, and it may
    route it somewhere else entirely. Normalising to decide and then sending
    the un-normalised form is two different questions answered as one, which
    is the shape this repository keeps paying for. So the non-canonical form
    is not repaired; it is refused, and refused under its own name.
    """
    if not path.startswith("/"):
        return False
    if path != posixpath.normpath(path):
        return False
    #: `%2D` is `-`. Decoding before comparing is the same mistake as
    #: normalising before comparing, so an encoded form is not canonical.
    return unquote(path) == path


def path_exact_fence(allowed_paths, allowed_method="GET"):
    """A transport that admits ONLY the given full paths, and records.

    Returns `(transport, observed)`. The transport raises
    `OutsideAuthorisation` before anything leaves the process for any method
    that is not `allowed_method`, any path that is not canonical (see
    `is_canonical_path`), any path not in `allowed_paths` **compared whole**,
    and any request carrying a body.

    A refusal records `refused_because` - one of `method`, `not-canonical`,
    `path`, `body` - because TASK 0210 measured a planted violation being
    "caught" by an accident (a missing parent directory rather than the
    wrong path), and a guard that refuses for the wrong reason reads exactly
    like a guard that refuses for the right one.

    `headers` is the only argument that could carry a credential and it is
    dropped: never recorded, never printed, never returned.

    It wraps NOTHING. There is no inner transport to fall through to, so a
    path that is allowed still reaches no network from here - this fence is
    for proving narrowness offline, not for making a read.
    """
    allowed = frozenset(allowed_paths)
    observed = []

    def transport(method, url, headers=None, body=None, timeout=None):
        parts = urlsplit(url)
        record = {"method": str(method).upper(), "path": parts.path,
                  "query": dict(parse_qsl(parts.query)),
                  "had_body": bool(body)}
        because = None
        if record["method"] != allowed_method:
            because = "method"
        elif not is_canonical_path(record["path"]):
            because = "not-canonical"
        elif record["path"] not in allowed:
            because = "path"
        elif record["had_body"]:
            because = "body"
        if because is not None:
            record["verdict"] = "REFUSED_BY_FENCE"
            record["refused_because"] = because
            observed.append(record)
            raise OutsideAuthorisation(
                f"{record['method']} {record['path']} is outside this "
                f"process's authorisation ({allowed_method}, one of "
                f"{sorted(allowed)}, canonical, no body): refused on "
                f"{because}. Nothing was sent.")
        record["verdict"] = "ALLOWED_BY_FENCE_BUT_NOT_SENT"
        observed.append(record)
        raise OutsideAuthorisation(
            f"{record['method']} {record['path']} passes the fence, and this "
            f"module still sends nothing: TASK 0200 has no live mode.")

    return transport, observed


#: The negative controls a live read-back must refuse before it is attempted,
#: CORRECTED. The third is the route that exists; 0180's was the route nobody
#: generates. The fourth and fifth are the estate walk under a wrong method
#: and the campaign read itself.
NEGATIVE_CONTROLS = (
    ("POST", ROUTE_ESTATE),
    ("GET", "/api/campaigns"),
    ("GET", ROUTE_CAMPAIGN_SENDERS.format(campaign_id=499)),
    ("GET", "/api/campaigns/499"),
    ("POST", ROUTE_CAMPAIGN_SENDERS.format(campaign_id=499)),
)


# --- loading the recorded walk -------------------------------------------

def load_recorded_estate(path):
    """The recorded 2026-10-15 walk. Returns `(rows, total)`.

    The file is outside git - it carries 181 real addresses. Only ids, px
    values and counts ever come back out of this function's callers.

    THIS FUNCTION DOES NOT AUTHENTICATE THE FILE. It parses whatever is at
    `path`. See `load_pinned_estate` for the form that refuses an estate whose
    bytes are not the bytes somebody recorded a digest for, and prefer it
    anywhere a verdict is going to be believed.
    """
    with open(path, encoding="utf-8") as handle:
        blob = json.load(handle)
    rows = blob["rows"]
    total = (blob.get("meta_returned") or {}).get("total")
    return rows, total


#: The shortest digest prefix `load_pinned_estate` will accept.
#:
#: WHY A PREFIX IS ACCEPTED AT ALL. This estate records its artifact pins
#: TRUNCATED - `FINDING-the-one-authorised-read-2026-10-15.md:60` pins the
#: recorded walk as `b677205570bba0bd...`, sixteen hex digits. A loader that
#: demanded all sixty-four could not be handed the pin the estate actually
#: wrote down, so it would be bypassed, and a check nobody can call is a check
#: nobody runs. Sixteen hex digits is 64 bits, which answers the threat this
#: guard exists for - a file quietly edited, regenerated or swapped between the
#: measurement and the verdict. It does NOT answer a chosen-prefix attack, and
#: nothing here claims it does.
MIN_PIN_HEX = 16


class EstateNotPinned(Exception):
    """The estate file is not the file its digest was recorded for.

    Raised INSTEAD OF returning rows, so that a caller cannot accidentally
    proceed with an unauthenticated estate: there is no partial result to
    mistake for one. `UNKNOWN` is the verdict a caller should record when it
    catches this - never `MET`, and never "assume unchanged".
    """


def load_pinned_estate(path, expected_sha256):
    """`load_recorded_estate`, but only if the bytes are the pinned bytes.

    THE ORDER IS THE POINT. The digest is computed over the file's bytes and
    compared BEFORE the JSON is parsed and therefore long before any membership
    id is joined onto any row. A loader that checked afterwards would already
    have produced the rows a caller could use, and this estate's own history is
    of exactly that: a value computed correctly that nothing downstream refuses
    to act on.

    Refuses, rather than returning a verdict, when:

      - `expected_sha256` is absent, not hex, or shorter than `MIN_PIN_HEX`.
        An unpinnable call is not a pinned one. A caller that has no digest
        should say so and record UNKNOWN; it must not get silent permission
        here by passing `None`.
      - the file cannot be read. Unreadable is UNKNOWN, never empty.
      - the digest does not match. Both digests are named in the message, the
        measured one in full, so the reader can tell a stale pin from a changed
        file without re-deriving anything.
    """
    pin = str(expected_sha256 or "").strip().lower()
    if not pin:
        raise EstateNotPinned(
            "no digest was supplied for %r. An estate with no pin is not "
            "evidence about the estate, and a missing pin is a refusal rather "
            "than a pass" % path)
    if len(pin) < MIN_PIN_HEX or any(c not in "0123456789abcdef" for c in pin):
        raise EstateNotPinned(
            "the digest supplied for %r is not at least %d hex digits: %r"
            % (path, MIN_PIN_HEX, expected_sha256))
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise EstateNotPinned(
            "the estate at %r cannot be read (%s), so its digest cannot be "
            "checked and its contents are UNKNOWN" % (path, exc))
    measured = hashlib.sha256(raw).hexdigest()
    if not measured.startswith(pin):
        raise EstateNotPinned(
            "the estate at %r does not match its pin. recorded %s..., "
            "measured %s. No join was attempted and no verdict exists; this "
            "is UNKNOWN, not a changed answer" % (path, pin, measured))
    return load_recorded_estate(path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CANARY-01 criterion 7, per campaign. Offline. "
                    "Attaches nothing and dials nothing.")
    parser.add_argument("--estate", required=True,
                        help="the recorded /sender-emails walk (JSON)")
    parser.add_argument("--estate-sha256", default=None, metavar="HEX",
                        help="the digest the walk was pinned under (>= %d hex "
                             "digits; truncated pins are what this estate "
                             "records). Supplying it makes the load REFUSE a "
                             "file that is not the pinned one. Omitting it "
                             "runs unpinned and says so on stderr."
                             % MIN_PIN_HEX)
    parser.add_argument("--campaign", action="append", default=[],
                        metavar="ID[:id,id,...]",
                        help="a campaign in scope. Bare ID means 'membership "
                             "not read' (UNKNOWN). ID:1,2,3 supplies a "
                             "read-back's sender ids.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    # The pin is checked HERE, before any scope is built and before any join,
    # so a refusal cannot be mistaken for a verdict. An unpinned run is still
    # allowed - the recorded walk predates this flag - but it is announced on
    # stderr rather than passing quietly, because the silent form is how a
    # swapped estate would get believed.
    if args.estate_sha256:
        try:
            rows, total = load_pinned_estate(args.estate, args.estate_sha256)
        except EstateNotPinned as exc:
            print("REFUSED: %s" % exc, file=sys.stderr)
            print("verdict: UNKNOWN (the estate was not authenticated)",
                  file=sys.stderr)
            return 2
    else:
        print("WARNING: --estate-sha256 was not supplied, so %s is being "
              "trusted unauthenticated. Any verdict below is conditional on "
              "that file being the recorded walk."
              % args.estate, file=sys.stderr)
        rows, total = load_recorded_estate(args.estate)
    scope = {}
    for spec in args.campaign:
        cid, _, ids = spec.partition(":")
        scope[int(cid)] = ([int(i) for i in ids.split(",") if i.strip()]
                           if _ else None)
    report = verdict_over_campaigns(scope, rows, estate_total=total)

    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0

    print("CANARY-01 CRITERION 7 - one owner across the ATTACHED pool")
    print(f"  estate walk     {len(rows)} rows, meta.total {total}")
    print(f"  approved pool   {sorted(APPROVED_POOL)}")
    print(f"  approved owner  {APPROVED_OWNER_PX}")
    print(f"  campaigns       {sorted(scope) or 'NONE IN SCOPE'}")
    print(f"\n  OVERALL  {report['overall']['verdict']}"
          f"  - {report['overall']['reason']}")
    for cid, verdict in report["per_campaign"].items():
        print(f"\n  campaign {cid}: {verdict['verdict']}")
        print(f"    attached {verdict['attached']}")
        print(f"    owner    {verdict['owner_px']}")
        for finding in verdict["findings"]:
            print(f"    [{finding['verdict']}] {finding['reason']}")
    return 0 if report["overall"]["verdict"] == MET else 1


if __name__ == "__main__":
    raise SystemExit(main())
