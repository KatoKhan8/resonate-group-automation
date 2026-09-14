#!/usr/bin/env python3
"""The one authority on whether an address may be written to.

Nothing else in this repository decides sendability. Providers report evidence;
this module weighs it against the client's policy and returns a single verdict.
`lint.sendable` delegates here, and `enrich` asks here rather than deciding.

The waterfall, and it stops the moment the policy has enough:

  stored evidence        free, and it is checked first
  ContactOut verifier    the primary, 1 verifier credit on a definitive result
  Deliverable            only when the primary is ambiguous
  Reoon power mode       only when a catch-all is still unresolved

Conservative by construction. Every unresolved, ambiguous, failed, timed out or
contradictory case ends `held`, never `sendable`. Discovery is not verification:
an address found by AI Ark, scraped from a website, inferred from a pattern or
typed into a CRM starts with no evidence at all, and no origin is a substitute
for a verdict.
"""
import argparse

from . import events, spendledger, store

# ---------------------------------------------------------------- states

VERIFIED = "verified"                    # a provider cleared it, policy agrees
INVALID = "invalid"                      # definitively bad, never send
ACCEPT_ALL_UNCLEARED = "accept_all_uncleared"   # catch-all, nothing cleared it
UNKNOWN = "unknown"                      # no usable evidence
HELD = "held"                            # ambiguous, contradictory or failed

STATES = (VERIFIED, INVALID, ACCEPT_ALL_UNCLEARED, UNKNOWN, HELD)
SENDABLE_STATES = (VERIFIED,)

# Normalised statuses a provider result can carry.
S_VALID = "valid"
S_INVALID = "invalid"
S_ACCEPT_ALL = "accept_all"
S_DISPOSABLE = "disposable"
S_UNKNOWN = "unknown"
S_ERROR = "error"
S_TIMEOUT = "timeout"

PROVIDER_STATUSES = (S_VALID, S_INVALID, S_ACCEPT_ALL, S_DISPOSABLE, S_UNKNOWN,
                     S_ERROR, S_TIMEOUT)

# What each verification call costs, for the planner and the cap.
COSTS = {"contactout": 1, "deliverable": 1, "reoon": 1}

DEFAULT_POLICY = {
    # The order the waterfall runs in. ContactOut first: it is the primary and
    # the credits are ours.
    "primary": "contactout",
    "secondary": "deliverable",
    "catch_all": "reoon",
    # ------------------------------------------------------------------
    # How many INDEPENDENT providers must say an address is good before it may
    # be written to. Two, by default, and this is the invariant the rest of the
    # module is built around.
    #
    # One verifier is a single point of failure with a commercial interest in
    # saying yes. ContactOut returning `valid` is evidence, not proof: it has
    # been observed returning `accept_all` for an address it separately marked
    # verified in its own data (BUILD-SPEC section 9, trap 2). A second
    # provider that has never seen our first provider's answer is the cheapest
    # protection against a whole class of quiet, expensive mistakes - and the
    # expensive part is not the credit, it is the sending reputation.
    #
    # Set to 1 to restore the old single-verifier behaviour. That is a
    # deliberate, configured, tested choice; it is not the default and it is
    # not what happens by accident.
    "required_confirmations": 2,
    # Which providers are allowed to clear a catch-all. BUILD-SPEC section 5.3:
    # only Reoon's is_safe_to_send clears one, so Deliverable alone does not.
    "accept_all_clears_on": ["reoon"],
    # What to do when two providers disagree. hold is the only safe default.
    "disagreement": "hold",
    # A primary `unknown` is not rescued by a secondary `valid` unless this is
    # turned on deliberately.
    "trust_secondary_when_primary_unknown": False,
    # Three calls: primary, secondary, escalation. The cap has to allow the
    # escalation or a disagreement could never be resolved.
    "max_verification_cost_per_contact": 3,
}

# The statuses that count as one provider confirming an address. Deliberately
# only `valid`: a catch-all is not a confirmation, it is the absence of one,
# and `unknown` is the absence of an answer.
CONFIRMING_STATUSES = (S_VALID,)


class VerificationError(RuntimeError):
    """The waterfall could not run. The contact is held, never cleared."""


# ---------------------------------------------------------------- policy

def policy_for(config=None):
    """The client's verification policy, over the conservative defaults."""
    policy = dict(DEFAULT_POLICY)
    supplied = (config or {}).get("verification") or {}
    for key, value in supplied.items():
        if key in policy and value is not None:
            policy[key] = value
    if isinstance(policy["accept_all_clears_on"], str):
        policy["accept_all_clears_on"] = [policy["accept_all_clears_on"]]
    return policy


# -------------------------------------------------------------- evidence

def result(provider, status, email=None, **fields):
    """One provider's answer, normalised. No raw payload ever gets in here."""
    if status not in PROVIDER_STATUSES:
        status = S_UNKNOWN
    entry = {
        "provider": provider,
        "status": status,
        "email": email,
        "deliverable": fields.get("deliverable"),
        "safe_to_send": fields.get("safe_to_send"),
        "catch_all": fields.get("catch_all"),
        "disposable": fields.get("disposable"),
        "role_account": fields.get("role_account"),
        "score": fields.get("score"),
        "reason": fields.get("reason"),
        # Whether this call actually cost anything. `None` means nobody said,
        # and nobody saying is treated as charged - see `call`, which only
        # marks a refusal raised BEFORE the network as free. Defaulting the
        # other way would let a silent provider quietly stop being billed.
        "charged": fields.get("charged"),
        "at": fields.get("at") or store.now(),
    }
    return entry


def evidence_of(contact):
    """Every normalised result stored on this contact, oldest first."""
    return list((contact.get("verification") or {}).get("evidence") or [])


def evidence_from(contact, provider):
    for entry in evidence_of(contact):
        if entry.get("provider") == provider:
            return entry
    return None


def legacy_evidence(contact):
    """Evidence implied by the pre-existing verdict and reoon fields.

    Records written before this module existed carry `verdict` and `reoon`
    directly. They are read as evidence rather than migrated, so nothing has to
    be rewritten and nothing silently changes meaning.
    """
    out = []
    verdict = contact.get("verdict")
    if verdict:
        status = verdict if verdict in PROVIDER_STATUSES else S_UNKNOWN
        out.append(result("contactout", status, contact.get("email"),
                          catch_all=(verdict == S_ACCEPT_ALL),
                          disposable=(verdict == S_DISPOSABLE),
                          reason="from the record's stored verdict"))
    reoon = contact.get("reoon") or {}
    if reoon:
        safe = reoon.get("is_safe_to_send")
        status = S_VALID if safe is True else (
            S_ACCEPT_ALL if reoon.get("is_catch_all") else S_UNKNOWN)
        out.append(result("reoon", status, contact.get("email"),
                          safe_to_send=safe, catch_all=reoon.get("is_catch_all"),
                          deliverable=reoon.get("is_deliverable"),
                          score=reoon.get("overall_score"),
                          reason="from the record's stored Reoon result"))
    # A legacy verdict has no time on it. `result` stamps `store.now()` when
    # it is not told one, which is right for a call that just happened and
    # wrong here: it would report a verification from two years ago as
    # today's, with a timestamp confident enough to be believed. Undated is
    # the honest answer and `age_of` reports it as unknown.
    return [dict(entry, at=None) for entry in out]


def normalise_address(value):
    """The one spelling an address is compared by.

    Case and surrounding whitespace only. No mail system treats either as
    significant, and refusing them would burn credits re-verifying an
    address that has already been checked. Nothing else is folded: the local
    part is the mailbox owner's business, and deciding that `a.b@` and `ab@`
    are the same address is exactly the fuzzy matching this system refuses
    everywhere else it matters.
    """
    return str(value or "").strip().lower()


def evidence_for(contact, evidence=None):
    """Evidence that is actually about this contact's current address.

    The invariant is that two independent vendors approved *the exact
    normalised mailbox about to be written to*, and evidence stored on a
    contact outlives the address it was obtained for. A corrected typo, a
    re-enrichment that finds a better mailbox, or an operator replacing one
    that bounced would otherwise inherit the previous address's
    confirmations and present as verified for an address nobody has checked.

    Evidence recording no address cannot be shown to be about this one, so
    it does not count. That is the fail-closed reading; it costs a
    re-verification, which is the cheap half of the trade.
    """
    here = normalise_address(contact.get("email"))
    if not here:
        return []                      # no mailbox is not a verified mailbox
    entries = evidence_of(contact) if evidence is None else evidence
    return [e for e in entries
            if normalise_address(e.get("email")) == here]


def age_of(contact, now=None):
    """How old the evidence behind this address is. Never a guess.

    There is no freshness *rule* in this build - nobody has chosen how
    long a verification is good for, and choosing costs re-verification
    credits, so it is a decision rather than a parser. `MANUAL-REVIEW.md`
    9b is where that decision is asked for.

    What was missing was any way to answer it. This reports the ages so a
    person can look at the oldest one and say whether they would send to
    it today.

    `dated` is the count of results that carry a real timestamp. A legacy
    verdict carries none, and is reported as undated rather than as new.
    """
    stamps = []
    undated = 0
    for entry in all_evidence(contact):
        moment = _moment(entry.get("at"))
        if moment is None:
            undated += 1
        else:
            stamps.append(moment)

    current = _moment(now) or _moment(store.now())
    oldest = min(stamps) if stamps else None
    newest = max(stamps) if stamps else None
    return {
        "dated": len(stamps),
        "undated": undated,
        "oldest_at": oldest.isoformat() if oldest else None,
        "newest_at": newest.isoformat() if newest else None,
        "oldest_days": ((current - oldest).days
                        if oldest and current else None),
        "newest_days": ((current - newest).days
                        if newest and current else None),
    }


def _moment(value):
    """An aware datetime, or None. A naive one is unreadable, not UTC."""
    import datetime

    try:
        parsed = datetime.datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def all_evidence(contact):
    """Stored normalised evidence, or the legacy fields read as evidence.

    Stored evidence still takes precedence over the legacy fields, and the
    fall-through happens only when there is none at all. Falling back
    because the stored evidence was written for a *different* address would
    reintroduce the drift this binding exists to stop, on exactly the
    records old enough to carry both.
    """
    stored = evidence_of(contact)
    if stored:
        return evidence_for(contact, stored)
    # Built from the contact's own address, so bound by construction; the
    # filter is applied anyway so one rule governs both paths.
    return evidence_for(contact, legacy_evidence(contact))


# -------------------------------------------------------------- decision

def _verdict(state, sendable, reason, evidence, policy):
    """One decision, with the confirmation rule applied last and to everything.

    The rule is one sentence: **a decision may only be sendable if enough
    independent providers confirmed it.** Applying it here rather than at each
    branch is what makes it an invariant instead of a convention - a new
    branch in `decide` inherits it without its author having to remember.

    Downgrading is one-way. This can turn a sendable decision into a held one;
    it can never turn a held one into a sendable one, so no future policy knob
    plumbed through here can accidentally open the gate.
    """
    count, required = _shortfall(evidence, policy)
    providers = sorted(confirmations(evidence))
    decision = {
        "state": state,
        "sendable": bool(sendable),
        "reason": reason,
        "confirmation_count": count,
        "required_confirmations": required,
        "confirmed_by": providers,
        "disagreement": False,
    }
    if decision["sendable"] and count < required:
        missing = required - count
        decision.update({
            "state": HELD,
            "sendable": False,
            "reason": (f"{reason}, but only {count} of {required} required "
                       f"independent confirmations "
                       f"({', '.join(providers) or 'none'}): "
                       f"{missing} more needed"),
            "insufficient_confirmations": True,
        })
    return decision


def confirmations(evidence):
    """Which distinct providers positively confirmed this address.

    A set of provider names, so it counts *providers* and not calls. Asking
    ContactOut twice is one confirmation: two answers from one source share
    whatever made the first one wrong, which is the entire reason a second
    opinion is worth buying.
    """
    by_provider = {}
    for entry in evidence or []:
        by_provider[entry["provider"]] = entry           # last answer wins
    return {provider for provider, entry in by_provider.items()
            if entry["status"] in CONFIRMING_STATUSES}


def _shortfall(evidence, policy):
    """(count, required). The pair every hold-for-more-evidence reason quotes."""
    required = int(policy.get("required_confirmations") or 1)
    return len(confirmations(evidence)), required


def decide(evidence, policy=None):
    """The whole policy, in one pure function. No I/O, no provider, no record.

    Every return goes through `_verdict` so that no path can produce a
    decision without a confirmation count on it, and so that the
    required-confirmations rule cannot be forgotten on one branch. That
    matters more than it looks: the branch somebody forgets is always the one
    that says `sendable: True`.
    """
    policy = policy or DEFAULT_POLICY
    count, required = _shortfall(evidence, policy)

    def verdict(state, sendable, reason):
        return _verdict(state, sendable, reason, evidence, policy)

    if not evidence:
        return verdict(UNKNOWN, False, "no verification evidence")

    by_provider = {}
    for entry in evidence:
        by_provider[entry["provider"]] = entry           # last wins
    statuses = {p: e["status"] for p, e in by_provider.items()}

    # 1. A provider that failed or timed out is evidence of nothing.
    failed = [p for p, s in statuses.items() if s in (S_ERROR, S_TIMEOUT)]
    usable = {p: s for p, s in statuses.items() if s not in (S_ERROR, S_TIMEOUT)}
    if not usable:
        return verdict(HELD, False,
                       f"every verifier failed: {', '.join(sorted(failed))}")

    # 2. A contradiction is reported as one, before anything else, so it can be
    #    seen and counted. It is never sendable either way, but "they disagree"
    #    and "it is dead" are different facts about an address.
    positives = {p for p, s in usable.items() if s == S_VALID}
    negatives = {p for p, s in usable.items()
                 if s in (S_INVALID, S_DISPOSABLE)}
    negatives |= {p for p, e in by_provider.items()
                  if e.get("disposable") is True and p in usable}
    # An explicit refusal, whatever word the status carries.
    #
    # Reoon answers `is_safe_to_send: false` and `is_deliverable: false`,
    # and `call` records both on the evidence - but maps the *status* to
    # `unknown`, because only `true` becomes `valid`. So the refusal was
    # recorded and never read: it was not in `negatives`, so it could not
    # be a disagreement, and step 4 below returns VERIFIED on a valid
    # primary before the catch-all branch that would have refused it ever
    # runs. A catch-all the trusted clearer explicitly declined came back
    # `verified, sendable, disagreement: False` on the strength of two
    # other vendors. "CATCH_ALL is never an automatic PASS" was being
    # decided by branch order.
    #
    # Read here rather than at step 5 so it reaches the disagreement rule
    # first. Two vendors saying valid and one saying "do not send" is a
    # disagreement, which holds - not a majority, which sends.
    negatives |= {p for p, e in by_provider.items()
                  if e.get("safe_to_send") is False and p in usable}
    negatives |= {p for p, e in by_provider.items()
                  if e.get("deliverable") is False and p in usable}
    # A disagreement is between two providers. One provider contradicting
    # itself is not a disagreement, it is a bad address.
    if (positives - negatives) and (negatives - positives):
        if policy.get("disagreement") != "trust_primary":
            out = verdict(HELD, False,
                          f"verifiers disagree: {sorted(positives)} say valid, "
                          f"{sorted(negatives)} do not")
            out["disagreement"] = True
            return out
        primary = policy.get("primary")
        if statuses.get(primary) == S_VALID:
            out = verdict(VERIFIED, True,
                          f"{primary} says valid and policy trusts the primary")
            out["disagreement"] = True
            return out
        out = verdict(HELD, False,
                      "verifiers disagree and the primary is not positive")
        out["disagreement"] = True
        return out

    # 3. Anything definitively bad, with nothing contradicting it, ends here.
    for provider, entry in by_provider.items():
        if entry["status"] == S_INVALID:
            return verdict(INVALID, False, f"{provider} says invalid")
        if entry["status"] == S_DISPOSABLE or entry.get("disposable") is True:
            return verdict(INVALID, False, f"{provider} says disposable")

    primary = policy.get("primary")
    primary_status = usable.get(primary)

    # 4. A clean valid from the primary.
    if primary_status == S_VALID:
        # No special case for "the secondary must also agree": `_verdict`
        # applies the confirmation rule to this branch like every other. One
        # rule in one place beats a flag that only guards the branch whose
        # author remembered it.
        return verdict(VERIFIED, True, f"{primary} says valid")

    # 5. A catch-all. Only a provider the policy trusts can clear one.
    catch_all = any(e["status"] == S_ACCEPT_ALL or e.get("catch_all") is True
                    for e in by_provider.values())
    if catch_all:
        for clearer in policy.get("accept_all_clears_on") or []:
            entry = by_provider.get(clearer)
            if not entry:
                continue
            cleared = (entry.get("safe_to_send") is True
                       or (entry["status"] == S_VALID and entry.get("catch_all") is not True))
            if cleared:
                return verdict(VERIFIED, True, f"catch-all cleared by {clearer}")
            if entry.get("safe_to_send") is False:
                return verdict(ACCEPT_ALL_UNCLEARED, False,
                               f"{clearer} says the catch-all is not safe to send")
        return verdict(ACCEPT_ALL_UNCLEARED, False,
                       "catch-all with nothing that clears it")

    # 6. A valid from somebody other than the primary.
    if positives:
        if primary_status in (None, S_UNKNOWN):
            if policy.get("trust_secondary_when_primary_unknown"):
                return verdict(VERIFIED, True,
                               f"{sorted(positives)[0]} says valid and policy "
                               "trusts it without the primary")
            return verdict(HELD, False,
                           f"{sorted(positives)[0]} says valid but the primary is "
                           f"{primary_status or 'missing'}, and policy does not "
                           "clear on the secondary alone")
        return verdict(VERIFIED, True, f"{sorted(positives)[0]} says valid")

    return verdict(UNKNOWN, False, "no verifier could resolve this address")


def is_sendable(contact, policy=None):
    """The single authority. Everything that asks about sendability asks this.

    Always **recomputed from the evidence**, never read from the stored state.

    It used to return `stored in SENDABLE_STATES` whenever a verification block
    existed, which made `verification.state` a second source of truth: anything
    that could write that string - a hand edit, a resumed run under an older
    policy, a future UI, a bug - could make an address sendable without a
    provider ever having said so. The evidence list is the durable fact; the
    state is a cached opinion about it, and this is the function that must not
    be reading a cache.

    Re-deciding is cheap: `decide` is pure, does no I/O, and reads a handful of
    dicts already in memory.
    """
    if not contact or not contact.get("email"):
        return False
    return decide(all_evidence(contact), policy)["sendable"] is True


def resolve(contact, policy=None):
    """The full recomputed decision for one contact, for anything that needs
    the reason and the counts rather than just the boolean."""
    return decide(all_evidence(contact), policy)


# --------------------------------------------------------------- planning

def plan(contact, policy=None):
    """What this address still needs, why, and what it could cost.

    Conditional steps are marked: a maximum exposure is not a forecast.
    """
    policy = policy or DEFAULT_POLICY
    ops = []
    if not contact.get("email"):
        return ops

    evidence = all_evidence(contact)
    decision = decide(evidence, policy)
    if decision["state"] in (VERIFIED, INVALID):
        return ops                                # settled, spend nothing

    # A provider that errored has not answered, so it is not "have".
    #
    # This counted every stored entry, including `error`. On the Productive
    # pilot that meant nine contacts held at one confirmation of a required
    # two - ContactOut answering 404 and Deliverable refusing - reported an
    # empty plan and therefore zero expected verification spend. `needs()`
    # would still re-call them, so a re-run worked; what broke was every
    # forecast and every cost estimate reading `plan()`, which said this
    # pilot needed no verification budget at exactly the moment it needed
    # one. An error is a question that did not get answered, and the
    # difference between that and an answer is the whole point of recording
    # it separately.
    have = {e["provider"] for e in evidence if e.get("status") != S_ERROR}
    primary, secondary, catch_all = (policy.get("primary"),
                                     policy.get("secondary"),
                                     policy.get("catch_all"))

    if primary and primary not in have:
        ops.append({"provider": primary, "operation": "email-verifier",
                    "planned": True, "conditional": False,
                    "cost": COSTS.get(primary, 1),
                    "reason": "no stored verdict for this address"})
    if secondary and secondary not in have:
        # Not conditional any more. With `required_confirmations: 2` the
        # secondary runs on every address that survives the primary, so
        # planning it as a maybe would under-report the bill by half.
        # Expected when the primary alone would still leave us short. The
        # `+ 1` is the primary's own confirmation, which is planned above: at
        # `required_confirmations: 1` it closes the gap on its own and the
        # secondary goes back to being the conditional it always was.
        count, required = _shortfall(evidence, policy)
        expected = count + (1 if primary and primary not in have else 0) < required
        ops.append({"provider": secondary, "operation": "verify",
                    "planned": expected, "conditional": not expected,
                    "cost": COSTS.get(secondary, 1),
                    "reason": (f"a second independent confirmation is required "
                               f"({count} of {required} so far)" if expected
                               else f"only if {primary} is ambiguous")})
    if catch_all and catch_all not in have:
        ops.append({"provider": catch_all, "operation": "verify-power",
                    "planned": False, "conditional": True,
                    "cost": COSTS.get(catch_all, 1),
                    "reason": "only if a catch-all is still unresolved"})
    return ops


def exposure(ops):
    """Expected cost versus the worst case, kept apart on purpose."""
    return {
        "expected": sum(o["cost"] for o in ops if not o["conditional"]),
        "maximum": sum(o["cost"] for o in ops),
    }


# ------------------------------------------------------------ the runner

def verifiers():
    """Imported here so a missing optional provider cannot break the module."""
    from .providers import contactout, deliverable, reoon
    return {"contactout": contactout, "deliverable": deliverable, "reoon": reoon}


def _local_refusals():
    """Provider errors raised before any network call, so nothing was spent.

    A tuple rather than a single class so the next provider that declines
    locally is added here rather than by loosening the test above.
    """
    from .providers.deliverable import ContractNotVerified

    return (ContractNotVerified,)


def call(provider, email):
    """One verifier, normalised, never raising into the caller."""
    from .providers import ProviderError
    module = verifiers().get(provider)
    if module is None:
        return result(provider, S_ERROR, email, reason="no such verifier")
    try:
        if provider == "contactout":
            answer = module.email_verifier(email)
            verdict = answer.get("verdict", S_UNKNOWN)
            status = verdict if verdict in PROVIDER_STATUSES else S_UNKNOWN
            return result("contactout", status, email,
                          catch_all=(verdict == S_ACCEPT_ALL),
                          disposable=(verdict == S_DISPOSABLE))
        if provider == "deliverable":
            return module.verify(email)
        if provider == "reoon":
            answer = module.verify(email)
            safe = answer.get("is_safe_to_send")
            status = S_VALID if safe is True else (
                S_ACCEPT_ALL if answer.get("is_catch_all") else S_UNKNOWN)
            return result("reoon", status, email, safe_to_send=safe,
                          catch_all=answer.get("is_catch_all"),
                          deliverable=answer.get("is_deliverable"),
                          score=answer.get("overall_score"))
    except ProviderError as e:
        # A REFUSAL IS NOT A PURCHASE.
        #
        # `deliverable.verify` raises `ContractNotVerified` BEFORE it touches
        # the network: its response shape has never been read from a real
        # answer, so it declines rather than spending a credit to find out.
        # That refusal arrived here as a plain error and was billed anyway -
        # 41 rows and 41 credits in the spend ledger for calls that provably
        # never happened, against a declared ceiling those credits consume.
        #
        # Only a LOCAL refusal is exempt. A timeout or a 500 stays charged,
        # because the provider may well have done the work before failing to
        # tell us, and guessing in the cheap direction is how a ledger starts
        # under-reporting a real bill.
        charged = not isinstance(e, _local_refusals())
        return result(provider, S_ERROR, email, reason=str(e)[:120],
                      charged=charged)
    except Exception as e:                       # a timeout, a broken adapter
        return result(provider, S_ERROR, email, reason=f"{type(e).__name__}")
    return result(provider, S_UNKNOWN, email)


# What each verifier's call is named in the waterfall's own vocabulary.
CALL_NAMES = {"contactout": "email-verifier",
              "deliverable": "deliverable-verify",
              "reoon": "reoon-verify"}

# Why each rung is allowed, in the waterfall's own vocabulary. The primary
# needs no justification; each fallback names the thing that was wrong with
# the answer before it, which is what `waterfall.require` checks.
LEDGER_REASONS = {"contactout": None,
                  "deliverable": "verification_inconclusive",
                  "reoon": "verification_contradiction"}


def verify(contact, policy=None, live=False, rec=None, budget=None,
           config=None):
    """Walk the waterfall for one address and write the verdict onto the contact.

    Stops the moment the policy has enough. Returns the decision.

    `config` is the client's, and it is what carries the declared spend
    ceilings. Without it the call is still LEDGERED - the audit is never
    optional - but no durable ceiling can be enforced, because a ceiling
    nobody declared is not a ceiling this function may invent. The one
    production caller, `enrich.verify_contacts`, passes it.
    """
    policy = policy or DEFAULT_POLICY
    email = contact.get("email")
    if not email:
        return apply(contact, {"state": UNKNOWN, "sendable": False,
                               "reason": "no address"}, [], rec=rec)

    evidence = list(all_evidence(contact))
    spent = 0
    # Why the waterfall stopped, when it stopped for a reason that is not an
    # answer. A run that ran out of budget and a run that asked three
    # providers both end here; only one of them is a finding.
    stopped = None
    cap = policy.get("max_verification_cost_per_contact")
    order = [policy.get("primary"), policy.get("secondary"), policy.get("catch_all")]

    if rec is not None:
        events.record(rec, events.VERIFICATION_STARTED,
                      contact_key=contact.get("key"), channel="email")

    for provider in [p for p in order if p]:
        decision = decide(evidence, policy)
        if decision["state"] in (VERIFIED, INVALID):
            break                                 # settled: spend nothing more
        if any(e["provider"] == provider and e.get("status") != S_ERROR
               for e in evidence):
            continue                              # already have this one
        # An error is not an answer, and this is where that mattered most.
        # `plan()` was corrected to stop counting a failed call as evidence
        # held; this loop was not, so the two disagreed: the forecast said
        # ContactOut was worth calling and the execution skipped it, for ever,
        # because a stored `error` looked like a verdict. Nine Productive
        # contacts sat at one confirmation of a required two with the primary
        # never re-asked - and the primary is the one whose absence holds
        # every address under `trust_secondary_when_primary_unknown`.
        if not needs(provider, evidence, policy):
            continue
        cost = COSTS.get(provider, 1)
        if cap is not None and spent + cost > cap:
            stopped = "verification cost cap for this contact"
            if rec is not None:
                events.record(rec, events.PROVIDER_CALL_SKIPPED,
                              contact_key=contact.get("key"), provider=provider,
                              operation="verify", reason=stopped)
            break
        if budget is not None and not budget.charge(cost, f"verify:{provider}"):
            # Recorded, not just broken out of. The per-contact cap above
            # writes an event and this did not, so a contact left half
            # verified by the batch budget looked identical to one the
            # waterfall had finished with - which is how a stopped run reads
            # as a completed one. The two stops are different facts and the
            # log has to be able to tell them apart.
            stopped = "batch verification budget exhausted"
            if rec is not None:
                events.record(rec, events.PROVIDER_CALL_SKIPPED,
                              contact_key=contact.get("key"), provider=provider,
                              operation="verify", reason=stopped)
            break
        if not live:
            break                                 # planning only
        # THE DURABLE CEILING, BEFORE THE CALL AND NOT AFTER IT.
        #
        # The two stops above are in-memory: `cap` is per contact and `budget`
        # is per batch, and both die with the process. `spendledger` is the
        # one that survives a run, and verification never consulted it -
        # `enrich.spend` is described in its own comment as "the one door
        # every provider call goes through", and this waterfall does not go
        # through it. So a client's declared `per_day` ceiling could not see
        # the verification bill at all, and on the next Productive shard the
        # preflight prices that bill at 37 of 37 expected credits: the whole
        # run, unbounded.
        #
        # Refused the same way the other two are - an event, a named stop,
        # and out - so a contact stopped by the durable ceiling is still
        # distinguishable from one the waterfall finished with.
        if rec is not None:
            try:
                spendledger.check(rec.get("client"), config, cost,
                                  provider=provider)
            except spendledger.BudgetExceeded as e:
                stopped = f"durable budget: {e}"
                events.record(rec, events.PROVIDER_CALL_SKIPPED,
                              contact_key=contact.get("key"), provider=provider,
                              operation="verify", reason=stopped[:200])
                break
        if rec is not None:
            events.record(rec, events.PROVIDER_CALL_STARTED,
                          contact_key=contact.get("key"), provider=provider,
                          operation="verify", estimated_cost=cost)
        entry = call(provider, email)
        evidence.append(entry)
        # A call the provider declined locally costs nothing, so it is not
        # counted against the per-contact budget either - otherwise a
        # verifier that never runs still exhausts `max_verification_cost_per_
        # contact` and starves the verifier that would have answered.
        charged = entry.get("charged") is not False
        if charged:
            spent += cost
        elif budget is not None:
            budget.refund(cost)
        if rec is not None:
            # The ledger the spend audit reads.
            #
            # This charged the budget and stopped there, so verification was
            # invisible to `waterfall.spend` - and verification is one to
            # three credits per address, which at any real list size is most
            # of the bill. CLAUDE.md is explicit that a provider call skipping
            # the ledger is invisible to the audit, and that an audit
            # reporting clean because it watched nothing is worse than none.
            # The `EMAIL_VERIFICATION` stage was already declared here with
            # all three providers and their call names; nothing wrote to it.
            from . import waterfall
            waterfall.record_step(
                rec, waterfall.EMAIL_VERIFICATION, provider,
                CALL_NAMES.get(provider, f"{provider}-verify"),
                reason=LEDGER_REASONS.get(provider),
                result=entry.get("status"),
                expected_cost=cost if charged else 0)
            # AND THE SPEND LEDGER, WHICH IS A DIFFERENT LEDGER.
            #
            # `waterfall` is per record and answers "what was bought for this
            # company"; `spendledger` is per client and per day and is what
            # `spendledger.report`, `spendledger.check` and the shard
            # preflight all read. Writing only the first left the second
            # under-reporting by exactly the verification bill. Measured on
            # this estate: 30 credits across ten contacts, 37 stored evidence
            # rows, and not one row in `work/spend-ledger.jsonl` - 13% of the
            # true spend to date, and 100% of what the next 250-record shard
            # is forecast to cost, because the company-level work is done and
            # what remains is addresses.
            if charged:
                spendledger.record(
                    rec.get("client"), provider,
                    CALL_NAMES.get(provider, f"{provider}-verify"), cost)
        if rec is not None:
            events.record(rec, events.PROVIDER_CALL_COMPLETED,
                          contact_key=contact.get("key"), provider=provider,
                          operation="verify", estimated_cost=cost,
                          status=entry["status"])

    decision = decide(evidence, policy)
    decision["cost"] = spent
    decision["stopped"] = stopped
    return apply(contact, decision, evidence, rec=rec, policy=policy)


def needs(provider, evidence, policy):
    """Whether this provider has anything to add, given what is already known.

    Three reasons to call one, and the first is new: an address that is
    otherwise fine but short of its required confirmations needs another
    independent opinion, not because anything is ambiguous but because one
    opinion is not enough on its own.
    """
    decision = decide(evidence, policy)
    if provider == policy.get("primary"):
        return True

    count, required = _shortfall(evidence, policy)
    settled = decision["state"] == INVALID
    if settled:
        return False                      # definitively bad: buy nothing more

    if provider == policy.get("secondary"):
        # Short of confirmations, or the primary left it ambiguous.
        return (count < required
                or decision["state"] in (ACCEPT_ALL_UNCLEARED, UNKNOWN, HELD))
    if provider == policy.get("catch_all"):
        # The escalation. It resolves a catch-all, a disagreement, or a
        # shortfall the secondary could not close - which is what happens when
        # the secondary answers `unknown`, or errors, or is a provider whose
        # response contract we cannot yet read.
        return (decision["state"] in (ACCEPT_ALL_UNCLEARED, HELD, UNKNOWN)
                or count < required)
    return False


def _row_key(entry):
    """What makes one stored provider answer distinct from another."""
    return (entry.get("provider"), normalise_address(entry.get("email")),
            entry.get("at"))


def _keep_evidence(stored, incoming):
    """Stored rows the caller is not restating, then the caller's own.

    A provider answer that was bought is a fact about a mailbox at a moment.
    Nothing later un-buys it, so this list only grows. The caller's rows go
    last, which is the order `decide`'s per-provider last-wins needs.
    """
    restated = {_row_key(entry) for entry in incoming}
    return [e for e in stored
            if _row_key(e) not in restated] + list(incoming)


def apply(contact, decision, evidence, rec=None, policy=None):
    """Write the verdict. The only place `sendable` is ever assigned.

    The evidence list is the durable fact and the state is a cached opinion
    about it - `is_sendable` says so and recomputes rather than trusting the
    stored state. So a caller handing over a shorter list than what is stored
    is not downgrading a verdict, it is deleting paid provider answers. Three
    verifications for one address became "no verification evidence" that way,
    while the waterfall ledger still showed the spend.

    Evidence is therefore append-only here, and the decision is recomputed
    when the caller's list turns out to be missing something already stored.
    That is deliberately not a rule against UNKNOWN overwriting a verdict: an
    operator correcting a bounced address *should* land on UNKNOWN, and
    `evidence_for` binds evidence to the address it was bought for, so the
    history survives without the new mailbox inheriting the old one's
    confirmations.
    """
    stored = evidence_of(contact)
    merged = _keep_evidence(stored, evidence)
    if len(merged) != len(evidence):
        # Something stored was not restated. The verdict has to be about the
        # whole history, not about the caller's slice of it.
        decision = dict(decide(evidence_for(contact, merged),
                               policy or DEFAULT_POLICY),
                        cost=decision.get("cost", 0),
                        stopped=decision.get("stopped"))
    evidence = merged
    current = evidence_for(contact, evidence)
    by_provider = {}
    for entry in current:
        by_provider[entry["provider"]] = entry           # last answer wins
    reason = decision.get("reason")
    if decision.get("stopped"):
        # A stop is not a finding. Without this a run that asked nobody
        # published "no verification evidence" as though it were an answer.
        reason = f"{reason}; verification stopped early: {decision['stopped']}"
    contact["verification"] = {
        "state": decision["state"],
        "sendable": bool(decision["sendable"]),
        "reason": reason,
        "stopped": decision.get("stopped"),
        "cost": decision.get("cost", 0),
        "at": store.now(),
        "evidence": evidence,
        "providers": [e["provider"] for e in current],
        # The history, not just the verdict. A reviewer needs to see which
        # providers were asked, what each said and when, because "held" for
        # want of a second opinion and "held" because two providers disagree
        # are different problems with different fixes.
        "confirmation_count": decision.get("confirmation_count", 0),
        "required_confirmations": decision.get("required_confirmations", 1),
        "confirmed_by": decision.get("confirmed_by") or [],
        "disagreement": bool(decision.get("disagreement")),
        "results": {
            provider: {
                "verdict": entry.get("status"),
                "checked_at": entry.get("at"),
                "reason": entry.get("reason"),
                "is_safe_to_send": entry.get("safe_to_send"),
                "is_catch_all": entry.get("catch_all"),
                "score": entry.get("score"),
            } for provider, entry in sorted(by_provider.items())
        },
    }
    contact["sendable"] = bool(decision["sendable"])
    # The schema's own fields stay readable. They are a projection of the
    # evidence, never a second source of truth: is_sendable ignores them once a
    # verification block exists.
    primary = next((e for e in evidence if e["provider"] == "contactout"), None)
    if primary and primary["status"] in ("valid", "invalid", "accept_all",
                                         "disposable", "unknown"):
        contact["verdict"] = primary["status"]
    deep = next((e for e in evidence if e["provider"] == "reoon"), None)
    if deep:
        contact["reoon"] = {
            "is_catch_all": deep.get("catch_all"),
            "is_deliverable": deep.get("deliverable"),
            "is_safe_to_send": deep.get("safe_to_send"),
            "overall_score": deep.get("score"),
            "status": deep.get("status"),
        }

    if rec is not None:
        events.record(rec, events.VERIFICATION_RESULT,
                      contact_key=contact.get("key"), channel="email",
                      state=decision["state"], reason=decision.get("reason"))
        if "disagree" in (decision.get("reason") or ""):
            events.record(rec, events.VERIFICATION_DISAGREEMENT,
                          contact_key=contact.get("key"),
                          reason=decision.get("reason"))
    return decision


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.verification")
    p.add_argument("--id", help="only this record")
    a = p.parse_args(argv)

    for rec in store.load():
        if a.id and rec["id"] != a.id:
            continue
        for contact in rec.get("contacts") or []:
            if not contact.get("email"):
                continue
            ops = plan(contact)
            cost = exposure(ops)
            state = (contact.get("verification") or {}).get("state") or \
                decide(all_evidence(contact))["state"]
            print(f"{rec['id']}:{contact.get('key')}  {state}")
            for op in ops:
                mark = "planned    " if not op["conditional"] else "conditional"
                print(f"    {mark} {op['provider']:<12} {op['cost']} credit  {op['reason']}")
            if ops:
                print(f"    expected {cost['expected']}, maximum {cost['maximum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
