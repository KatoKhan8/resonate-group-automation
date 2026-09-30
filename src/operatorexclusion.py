#!/usr/bin/env python3
"""THE PERMANENT OPERATOR EXCLUSION: an account the operator refuses to sell to.

Operator decision "B", Zvonimir, 2026-09-28.

## The defect this exists to fix, measured rather than assumed

32 companies across campaigns 491-500 (`TASK-430`) were recorded as not
qualified so that they "can never be enrolled again". The guarantee did not
hold. The ruling was written as a HUMAN REVIEW, and both readers of a human
review - `qualify.review_of` and `dmplan.human_review` - discard a review
whose `inputs_fingerprint` no longer matches the qualification's.

Measured on a byte-identical copy of `work/queue.jsonl`, 2026-09-28: all 32
carry `qualification.human_review` with `decision: reject` by
`Zvonimir (operator) 2026-09-28`, and all 32 resolve `rejected` through
`qualify.state_of` today. Move the stored `inputs_fingerprint` - which is
exactly what `qualify.company()` does on a fact refresh - and **7 stay
`rejected` (the classifier itself says so) while 25 revert to
`review_required`.** The prohibition falls off silently.

Staleness is the RIGHT rule for a review that PERMITS: an accept given on
Monday must not authorise spending on Tuesday's different company. It is
exactly backwards for a review that FORBIDS. So the fix is not to weaken the
staleness rule; it is to stop expressing a permanent prohibition as a review
of evidence at all.

## Three semantics, and they stay distinct in the data

    classifier verdict    what the classifier concluded from the evidence
                          -> qualification.verdict.icp_status, UNTOUCHED
    human review          what a human concluded from THAT VERSION of the
                          evidence -> qualification.human_review, UNTOUCHED,
                          and still allowed to go stale
    permanent exclusion   explicit operator policy: this account must not be
                          enrolled regardless of future fact refreshes
                          -> THIS MODULE, and nothing else

For the 25 companies the classifier called `review`, **the classifier still
says `review`**. Nothing here writes a verdict, and nothing here writes to a
record at all.

## REUSE WAS EVALUATED FIRST AND NONE OF THE THREE CANDIDATES FITS

**`agencydnc` - the agency-wide do-not-contact.** The closest fit, and it
fails on four counts. (1) It is keyed on STRONG PERSON IDENTITY only -
`keys_for` builds keys from an email and a LinkedIn URL and deliberately
refuses to look at anything else, so it cannot express "this company". Most
of the 32 have one contact or none, because a company that did not qualify
consumes zero person credits by policy - and a person-level key cannot reach
a decision maker discovered next month. (2) Its privacy model is that it
stores NOTHING but a hash, a closed reason category and a timestamp: "No
name. No company. No workspace... a free-text note is where somebody
eventually writes 'replied to Productive'". WHO decided and WHY is precisely
what this state has to carry, so extending it would break the property it
exists to have. (3) Its notice is `suppressed by agency safety policy` - it
IS suppression, and a prospect who unsubscribed and a company the operator
refuses to sell to are different facts with different reversibility. (4) It
is append-only with no lift path at all, so it cannot record an operator
reversal either.

**`ingest.load_suppress()` - the domain suppression list.** Read on the send
path, at company level, which is the right shape. But it returns a `set` of
bare domain strings: no `by`, no `at`, no reason, no origin, and no room for
any, at twenty-odd call sites. And its content is the CLIENT'S OWN CUSTOMER
ROSTER - `config/suppress.local.txt`, described in `ingest` as "the roster of
who is paying us". A customer who churns comes off that list; an operator
policy does not. Merging the two would destroy the origin distinction the
operator called load-bearing and would put operator policy in a file the
client's account team edits.

**`accountstate.DO_NOT_CONTACT` / `record["do_not_contact"]`.** A REPORTING
vocabulary - `accountstate`'s own docstring says it is for "the Monday Slack
post, the PDF and later the portal" - and no send gate reads it.
`record["do_not_contact"]` is a bare boolean on a queue record with no who,
no when and no why, and `accountpolicy.ACCOUNT_DNC` means "Somebody asked us
to stop contacting the company", which is a fact about the company's wishes,
not about ours. Worse: it lives ON THE RECORD, and a queue record is exactly
what a migration, a batch reprocess or a re-ingest rewrites.

So this is a new canonical state. It is deliberately thin - one file, one
lookup, one vocabulary - and every reader calls it rather than re-deriving
anything.

## WHY THE REGISTER IS IN GIT, AND WHY THE ACCOUNT IS HASHED

Two rules in this repository pull in opposite directions here.

    OPERATING-MODE: "Business logic never depends on gitignored work/...
    a gate whose only evidence lived in a gitignored directory fails open
    on a clean clone."

    CLAUDE.md: "work/ stays gitignored. It is 300 real companies and 92
    real contacts and it is not ours to publish."

A safety state whose only copy is in `work/` is one `git clone` away from
silently permitting everything it was written to forbid. A file naming 32
real prospect domains is not ours to commit. The resolution is the one
`agencydnc` already made for the same conflict: **commit a one-way hash of
the account, in cleartext alongside the decision metadata, which is not
identifying.** The register reaches every clone; the roster does not.

This is not encryption and it is not claimed to be. Somebody holding this
file AND a candidate domain list can test each one, exactly as the pipeline
does. What it buys is that the file itself is not a directory of a client's
prospects. Identical trade, identical limits, stated in `agencydnc.fingerprint`.

## REVERSIBLE ONLY BY AN OPERATOR

The register is an append-only log of two operations, `exclude` and `lift`,
each carrying who, when, why and under what authority. `resolve()` replays
them in file order, so the last operation on an account wins and the whole
history stays readable.

Three separate things make "no automated path may clear it" true rather than
asserted:

  1. **The exclusion is not on the record.** `exclusion_of(rec)` hashes the
     record's domain and looks it up. Nothing on a queue record is trusted,
     so a fact refresh, a requalification, a fingerprint change, a batch
     reprocess, a queue migration and a re-ingest cannot reach it - they
     rewrite records, and the answer does not live there. This is the same
     discipline `channels` documents: "A tampered `email_eligible` on a
     contact changes nothing about what this returns."
  2. **`lift()` demands the account key it is about**, as `confirm`. A loop
     over a batch cannot pass that by accident.
  3. **Nothing in `src/` calls `lift()`.** Asserted by a test that walks
     every module, and by a second test that hashes the register file before
     and after a requalification, a fact refresh, a full batch run and a
     regeneration and requires it byte-identical.

A `lift` whose `authority` is not `operator` is refused at write time and
ignored at read time. Both, because a row that reached the file some other
way must not take effect either.

## INSPECTABILITY IS A REQUIRED PROPERTY

`explain(rec)` answers five questions for any blocked account - WHY, WHO,
WHEN, WHAT REASON, and WHICH ORIGIN - across all four origins a block can
have. That last field is the load-bearing one: four origins with four
different reversibility rules must not collapse into one "blocked".

    classifier      the classifier concluded it from the evidence; a better
                    verdict may legitimately change it
    human_review    a human concluded it from one version of the evidence;
                    it goes stale when the evidence moves, by design
    compliance      somebody asked us to stop, or a legal instruction; we do
                    not lift it, they do
    operator_policy this module; lifted only by an operator, explicitly,
                    with who / when / why recorded

  python -m src.operatorexclusion --list
  python -m src.operatorexclusion --why acme.test
"""
import argparse
import hashlib
import json
import os

from . import store

# --------------------------------------------------------------- vocabulary

#: The four origins a block can have. Each has its own reversibility rule, and
#: keeping them apart is the point - see the module docstring.
CLASSIFIER = "classifier"
HUMAN_REVIEW = "human_review"
COMPLIANCE = "compliance"
OPERATOR_POLICY = "operator_policy"
ORIGINS = (CLASSIFIER, HUMAN_REVIEW, COMPLIANCE, OPERATOR_POLICY)

ORIGIN_REVERSIBILITY = {
    CLASSIFIER: "re-derived from evidence; a better verdict may change it",
    HUMAN_REVIEW: "bound to one version of the evidence; goes stale when the "
                  "evidence moves",
    COMPLIANCE: "not ours to lift; the person or the instruction decides",
    OPERATOR_POLICY: "lifted only by an explicit operator action recorded "
                     "with who, when and why",
}

#: The two operations the register records. Append-only; nothing is rewritten.
EXCLUDE = "exclude"
LIFT = "lift"
OPERATIONS = (EXCLUDE, LIFT)

#: Who may write either operation. A `lift` by anything else is refused at
#: write time AND ignored at read time.
OPERATOR = "operator"

#: The one stable reason code every reader reports. It is vocabulary: renaming
#: it breaks reporting, so it is spelled once here and imported.
REASON_CODE = "operator_excluded"

#: What any surface is told, in one sentence.
NOTICE = ("permanently excluded by operator policy: this account must not be "
          "enrolled regardless of future fact refreshes")


class ExclusionRefused(RuntimeError):
    """A write to the register that the register will not accept."""


def path():
    """The register. IN GIT, resolved per call so tests can redirect it.

    Not beside the queue, which is where `agencydnc` puts its own file and
    where every other piece of runtime state lives. The difference is
    deliberate and is the whole reason the account is hashed: a safety state
    that does not survive a clean clone fails open on one.
    """
    return os.path.abspath(
        os.environ.get("OPERATOR_EXCLUSIONS")
        or os.path.join(store.ROOT, "config", "operator-exclusions.jsonl"))


# ------------------------------------------------------------------ the key

def account_key(domain):
    """The stored key for one account: a one-way hash of its domain.

    Normalised through `ingest.norm_domain` so `https://Acme.test/x`,
    `acme.test.` and `acme.test` are one account. Deferred import for the same
    reason `ingest.norm_domain` defers `dedupe`: this module is imported by
    the gates, and the gates are imported by everything.

    Unsalted, exactly as `agencydnc.fingerprint` is unsalted and for the same
    reason: a per-install salt would stop the CLI and the web process agreeing,
    and the threat this addresses is a reader of the file enumerating a
    client's prospects, not an attacker who already holds a domain list.
    """
    from . import ingest

    normalised = ingest.norm_domain(domain)
    if not normalised:
        return ""
    return hashlib.sha256(f"domain:{normalised}".encode("utf-8")).hexdigest()


def address_key(email):
    """The stored key for one ADDRESS: a one-way hash, same trade as above.

    WHY AN ADDRESS AND NOT ONLY AN ACCOUNT. The operator's own address is at a
    public mailbox provider that prospects also use, so excluding its DOMAIN
    would refuse every prospect with a Gmail mailbox. The prohibition is about
    one person and has to be keyed on one person.

    `agencydnc` is the other place a person-level prohibition can live and was
    the first choice, but its file is `work/agency-dnc.jsonl`, which is
    gitignored: an exclusion recorded there does not survive a clean clone, and
    "never contact the operator" is exactly the kind of state that must. This
    register is tracked for that reason, so it is where a permanent one goes.
    Prefixed `address:` rather than `domain:` so the two key spaces cannot
    collide.
    """
    from . import dedupe

    normalised = dedupe.normalise_email(email)
    if not normalised:
        return ""
    return hashlib.sha256(f"address:{normalised}".encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- the read

def rows(file_path=None):
    """Every operation in the register, in file order. Missing file is empty.

    A corrupt line is SKIPPED AND COUNTED, never silently dropped: `audit()`
    reports the count, because a register that quietly lost half its rows is
    indistinguishable from an empty one and one of the two is safe.
    """
    file_path = file_path or path()
    out, bad = [], 0
    if not os.path.exists(file_path):
        return out, bad
    with open(file_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if not isinstance(row, dict) or row.get("op") not in OPERATIONS:
                bad += 1
                continue
            if not row.get("account"):
                bad += 1
                continue
            out.append(row)
    return out, bad


#: A one-entry cache, keyed on the file's identity rather than on nothing.
#:
#: WHY A CACHE AT ALL. Every gate calls `blocks()`, and `eligibility.decide`
#: runs per contact per step: a 5,000-record batch re-parsed this file six
#: figures of times. `agencydnc` is read from disk on every call and says so
#: ("a cached suppression is a suppression that arrived after the cache"),
#: which is the right instinct and the reason the key below is what it is.
#:
#: WHY IT IS SAFE HERE. The key is (path, mtime_ns, size), and the register is
#: APPEND-ONLY - `_append` is the only writer and it only ever grows the file
#: - so every write changes the size. Both parts must match for a hit. The
#: honest limit: a file replaced wholesale, in the same nanosecond, at exactly
#: the same size would not be noticed. That is not a thing the append-only
#: writer can do, and an operator editing the file by hand changes its size or
#: its mtime or both.
#:
#: A MISSING FILE IS NEVER CACHED. An empty register means every account is
#: permitted, so a cached "the file was not there" is the one wrong answer
#: worth re-checking the filesystem for on every call.
_CACHE = {}


def _cache_key(file_path):
    try:
        info = os.stat(file_path)
    except OSError:
        return None
    return (file_path, info.st_mtime_ns, info.st_size)


def forget():
    """Drop the cache. For a test, and for an operator who just edited it."""
    _CACHE.clear()


def resolve(file_path=None):
    """The register as {account_key: active exclusion}, history replayed.

    The last operation on an account wins. A `lift` removes the account from
    the result; a later `exclude` puts it back. Each returned row carries
    `history`, so "this was excluded, lifted, and excluded again" is readable
    rather than a single mysterious current value.

    A `lift` whose `authority` is not `operator` IS IGNORED HERE, not merely
    refused at write time. A row that reached this file by some other route -
    an editor, a script, a bad merge - must not take effect either.
    """
    file_path = file_path or path()
    cache_key = _cache_key(file_path)
    if cache_key is not None and _CACHE.get("key") == cache_key:
        return _CACHE["value"]
    ordered, _bad = rows(file_path)
    active, history = {}, {}
    for row in ordered:
        account = row.get("account")
        history.setdefault(account, []).append(row)
        if row.get("op") == EXCLUDE:
            active[account] = dict(row)
        elif row.get("op") == LIFT:
            if row.get("authority") != OPERATOR:
                continue                 # not an operator: it lifts nothing
            active.pop(account, None)
    for account, row in active.items():
        row["history"] = history.get(account) or []
    if cache_key is not None:
        _CACHE["key"], _CACHE["value"] = cache_key, active
    return active


def exclusion_of(rec, index=None):
    """The active operator exclusion for this record's account, or None.

    THE ONE FUNCTION EVERY GATE CALLS. It reads the record's domain and
    nothing else off the record - no stored flag, no cached verdict - so
    nothing that rewrites a record can change the answer.
    """
    key = account_key((rec or {}).get("domain"))
    if not key:
        return None
    index = resolve() if index is None else index
    return index.get(key)


def blocks(rec, index=None):
    """Is this account permanently excluded? A bool, for a caller that wants one."""
    return exclusion_of(rec, index) is not None


def exclusion_of_address(email, index=None):
    """The active operator exclusion for one ADDRESS, or None."""
    key = address_key(email)
    if not key:
        return None
    index = resolve() if index is None else index
    return index.get(key)


def blocks_address(email, index=None):
    """Is this exact address permanently excluded?"""
    return exclusion_of_address(email, index) is not None


def refusal(rec, index=None):
    """The sentence a surface shows, or None. Carries who and when.

    Deliberately NOT the reason text alone: an operator reading "excluded"
    with no author and no date has to go and find both, and the whole point
    of this state is that it answers for itself.
    """
    hit = exclusion_of(rec, index)
    if not hit:
        return None
    return (f"{NOTICE} (by {hit.get('by')} on {hit.get('at')}: "
            f"{hit.get('reason')})")


# ---------------------------------------------------------------- the write

def _require_text(name, value, limit=500):
    text = str(value or "").strip()
    if not text:
        raise ExclusionRefused(
            f"{name} is required: an exclusion with no {name} cannot answer "
            "for itself later, which is the whole reason this state exists")
    return text[:limit]


def exclude(domain, *, by, reason, authority, at=None, origin=OPERATOR_POLICY,
            task=None, file_path=None):
    """Record a permanent operator exclusion. Appends; rewrites nothing.

    Every one of `by`, `reason` and `authority` is mandatory. An exclusion
    that cannot say who decided it and why is a block with no origin, which is
    the exact failure mode this module was built to end.
    """
    return _record(account_key(domain), f"account domain: {domain!r}",
                   by=by, reason=reason, authority=authority, at=at,
                   origin=origin, task=task, file_path=file_path)


def exclude_address(email, *, by, reason, authority, at=None,
                    origin=OPERATOR_POLICY, task=None, file_path=None):
    """Record a permanent operator exclusion for ONE ADDRESS.

    Same row, same append-only file, same mandatory who/why/authority. See
    `address_key` for why a person-level prohibition lives here rather than in
    `agencydnc`.
    """
    return _record(address_key(email), f"address: {email!r}",
                   by=by, reason=reason, authority=authority, at=at,
                   origin=origin, task=task, file_path=file_path)


def _record(key, what, *, by, reason, authority, at, origin, task, file_path):
    if not key:
        raise ExclusionRefused(f"not a usable {what}")
    if origin not in ORIGINS:
        raise ExclusionRefused(
            f"unknown origin {origin!r}; expected one of {', '.join(ORIGINS)}")
    row = {
        "op": EXCLUDE,
        "account": key,
        "origin": origin,
        "by": _require_text("by", by, 200),
        "reason": _require_text("reason", reason),
        "authority": _require_text("authority", authority, 200),
        "at": str(at or store.now()),
    }
    if task:
        row["task"] = str(task)[:64]
    return _append(row, file_path)


def lift(domain, *, by, reason, confirm, at=None, file_path=None):
    """Lift an exclusion. OPERATOR ONLY, and it takes saying so twice.

    `confirm` must be the account key being lifted. A batch loop cannot
    supply that by accident, which is the point: the guarantee wanted here is
    that no requalification, fact refresh, fingerprint change, batch
    reprocess or migration can clear an exclusion, and the strongest form of
    that guarantee is a call none of them can make.

    The `authority` written is always `operator`, because `resolve()` ignores
    a lift by anything else. There is no parameter for it on purpose: a caller
    that could choose its own authority could choose one that works.
    """
    key = account_key(domain)
    if not key:
        raise ExclusionRefused(f"not a usable account domain: {domain!r}")
    if confirm != key:
        raise ExclusionRefused(
            "a lift must name the account key it is lifting. Expected "
            f"confirm={key!r}. This is the guard that stops an automated "
            "path clearing a permanent operator exclusion in passing")
    row = {
        "op": LIFT,
        "account": key,
        "authority": OPERATOR,
        "by": _require_text("by", by, 200),
        "reason": _require_text("reason", reason),
        "at": str(at or store.now()),
    }
    return _append(row, file_path)


#: The tracked register, by absolute path, resolved once at import. Used only
#: by the write barrier below, which needs to know what "the real one" is
#: independently of whatever `OPERATOR_EXCLUSIONS` currently points at.
TRACKED_REGISTER = os.path.abspath(
    os.path.join(store.ROOT, "config", "operator-exclusions.jsonl"))


class ProductionRegisterUnderTest(RuntimeError):
    """A test tried to append to the tracked register."""


def _append(row, file_path=None):
    """The only write. Append-only, and barriered.

    `store.refuse_production_write` does not cover this file: it guards
    `work/`, and this register deliberately lives in `config/` so it reaches
    every clone. So the barrier is here, for the same reason that one exists -
    a test that reaches a writer outside the barrier writes the operator's
    real state, which is how fixture rows once landed in the real
    `replywatch.json`. A register with test rows in it excludes accounts
    nobody excluded.
    """
    file_path = file_path or path()
    target = os.path.abspath(file_path)
    if store.under_test() and target == TRACKED_REGISTER:
        raise ProductionRegisterUnderTest(
            "a test tried to append to the tracked operator-exclusion "
            f"register at {target}. Point OPERATOR_EXCLUSIONS somewhere "
            "disposable first, or pass file_path=")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# -------------------------------------------------------- inspectability

def explain(rec, index=None):
    """WHY is this account blocked, WHO blocked it, WHEN, WHY, and BY WHAT ORIGIN.

    All four origins, each reported separately with its own reversibility
    rule, because collapsing them into one "blocked" is the failure this is
    written against. Returns every origin that currently blocks, strongest
    reversibility guarantee first.

    Read-only. Calls no provider, writes nothing, and never changes a verdict.
    """
    from . import qualify

    rec = rec or {}
    found = []

    hit = exclusion_of(rec, index)
    if hit:
        found.append({
            "origin": OPERATOR_POLICY,
            "blocked": True,
            "who": hit.get("by"),
            "when": hit.get("at"),
            "reason": hit.get("reason"),
            "authority": hit.get("authority"),
            "task": hit.get("task"),
            "reversibility": ORIGIN_REVERSIBILITY[OPERATOR_POLICY],
            "why": NOTICE,
            "history": [
                {"op": h.get("op"), "by": h.get("by"), "at": h.get("at"),
                 "reason": h.get("reason")}
                for h in (hit.get("history") or [])],
        })

    # COMPLIANCE. Two independent mechanisms, kept apart from each other and
    # from the above: the agency list is a request made to Resonate, the
    # domain list is the client's own roster.
    from . import agencydnc, ingest

    domain = ingest.norm_domain(rec.get("domain"))
    if domain and domain in ingest.load_suppress():
        found.append({
            "origin": COMPLIANCE, "blocked": True, "who": None, "when": None,
            "reason": "the domain is on the suppression list",
            "authority": None, "task": None,
            "reversibility": ORIGIN_REVERSIBILITY[COMPLIANCE],
            "why": "suppressed at domain level", "history": []})
    for contact in rec.get("contacts") or []:
        notice = agencydnc.lookup(contact)
        if notice:
            found.append({
                "origin": COMPLIANCE, "blocked": True,
                "who": None, "when": None, "reason": notice,
                "authority": None, "task": None,
                "reversibility": ORIGIN_REVERSIBILITY[COMPLIANCE],
                "why": notice, "history": [],
                "contact": contact.get("key")})
            break

    # HUMAN REVIEW. Reported with its staleness, not folded into a yes/no:
    # "nobody reviewed this" and "somebody reviewed a version of this that no
    # longer exists" are different pieces of work, and `qualify` already
    # keeps them apart.
    live = qualify.review_of(rec)
    stale = qualify.stale_review_of(rec)
    review = live or stale
    if review and review.get("decision") == qualify.REJECT:
        found.append({
            "origin": HUMAN_REVIEW,
            "blocked": bool(live),
            "who": review.get("by"),
            "when": review.get("at"),
            "reason": review.get("note") or "a human reviewed this and rejected it",
            "authority": None, "task": None,
            "reversibility": ORIGIN_REVERSIBILITY[HUMAN_REVIEW],
            "why": ("a human rejected this version of the evidence" if live else
                    "a human rejected an EARLIER version of the evidence; this "
                    "review is stale and authorises nothing"),
            "stale": not bool(live),
            "reviewed_status": review.get("reviewed_status"),
            "history": []})

    # CLASSIFIER. The verdict as the classifier left it, never rewritten.
    verdict = ((rec.get("qualification") or {}).get("verdict") or {})
    status = verdict.get("icp_status")
    if status and status != "qualified":
        found.append({
            "origin": CLASSIFIER,
            "blocked": status == "rejected",
            "who": "src/qualify.py:company -> src/icp.py:score",
            "when": (rec.get("qualification") or {}).get("at"),
            "reason": "; ".join(verdict.get("classification_reasons") or [])[:500]
                      or f"the classifier concluded {status}",
            "authority": None, "task": None,
            "reversibility": ORIGIN_REVERSIBILITY[CLASSIFIER],
            "why": f"classifier verdict: {status}",
            "icp_status": status,
            "icp_tier": verdict.get("icp_tier"),
            "icp_confidence": verdict.get("icp_confidence"),
            "history": []})

    order = {OPERATOR_POLICY: 0, COMPLIANCE: 1, HUMAN_REVIEW: 2, CLASSIFIER: 3}
    found.sort(key=lambda row: order.get(row["origin"], 9))
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "account_key": account_key(rec.get("domain")),
        "permanently_excluded": bool(hit),
        "origins": found,
        # The one-line answer, and it names the origin rather than hiding it.
        "summary": (refusal(rec, index) if hit else
                    "; ".join(f"{r['origin']}: {r['why']}"
                              for r in found if r["blocked"])
                    or "nothing blocks this account"),
    }


def audit(file_path=None):
    """What the register holds, without naming anybody.

    `unreadable_rows` is reported rather than swallowed: a register that lost
    rows to corruption looks exactly like an empty one from the outside, and
    one of those two is safe.
    """
    ordered, bad = rows(file_path)
    active = resolve(file_path)
    blob = json.dumps(sorted(active), separators=(",", ":"))
    return {
        "path": file_path or path(),
        "operations": len(ordered),
        "excludes": sum(1 for r in ordered if r.get("op") == EXCLUDE),
        "lifts": sum(1 for r in ordered if r.get("op") == LIFT),
        "active": len(active),
        "unreadable_rows": bad,
        # A fingerprint of the ACTIVE SET, so an operator can confirm the
        # register still holds the same accounts without the file naming one.
        "active_set_fingerprint":
            hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16],
        "origins": sorted({r.get("origin") for r in active.values() if r.get("origin")}),
        "by": sorted({r.get("by") for r in active.values() if r.get("by")}),
        "tasks": sorted({r.get("task") for r in active.values() if r.get("task")}),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true",
                   help="what the register holds, naming no account")
    p.add_argument("--why", metavar="DOMAIN",
                   help="why one account is blocked, and by which origin")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.why:
        index = resolve()
        key = account_key(a.why)
        hit = index.get(key)
        out = {"domain": a.why, "account_key": key,
               "permanently_excluded": bool(hit), "exclusion": hit}
        print(json.dumps(out, indent=2))
        return 0 if hit else 1

    report = audit()
    if a.json:
        print(json.dumps(report, indent=2))
        return 0
    for name in ("path", "operations", "excludes", "lifts", "active",
                 "unreadable_rows", "active_set_fingerprint"):
        print(f"  {name:<24} {report[name]}")
    print(f"  {'origins':<24} {', '.join(report['origins']) or '-'}")
    print(f"  {'by':<24} {', '.join(report['by']) or '-'}")
    print(f"  {'tasks':<24} {', '.join(report['tasks']) or '-'}")
    print("  No account is named by this report. --why <domain> answers for one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
