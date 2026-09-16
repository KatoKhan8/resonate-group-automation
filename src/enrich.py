#!/usr/bin/env python3
"""The enrichment waterfall. BUILD-SPEC phase 4.

ContactOut first, AI Ark only on a miss, Reoon only on a catch-all, then
`sendable` per section 6.1. Nothing is guessed: every provider call carries a
reason, and a call with no reason is not made.

Cost discipline, from CLAUDE.md: people-count is free, everything else burns
credits, so cap before you fan out. Dry run is the default. Real calls need
--live.

  python -m src.enrich                  what would happen, and what it would cost
  python -m src.enrich --live --cap 50  actually enrich, stopping at 50 credits

The waterfall, per record:

  1 people-count      free      is this domain real and staffed at all
  2 decision-makers   credits   only if the record has no usable contact
  3 company-info      credits   only if 1 or 2 found nobody: rebrand check
  4 AI Ark search     credits   only if ContactOut found nobody usable
  5 email-verifier    credits   only for an address with no verdict
  6 Reoon power       credits   only for accept_all, because catch-alls lie

Outcomes: a record with a sendable address is `verified`; a record whose
addresses are unresolved is `held`, keeping everything it has; a record with
nothing usable is `dropped`, with the reason on it. Nothing is ever deleted.
"""
import argparse

from . import clients, dedupe, events, headcount, identity, linkedin, lint
from . import mx, research, store, verification
from .providers import ProviderError, aiark, apify, blitz, contactout

# What a call costs, in credits, for the cap. decision-makers charges per
# profile returned, so the plan assumes this many until the answer is known.
ASSUMED_PROFILES = 5

COSTS = {
    "people-count": 0,
    "decision-makers": ASSUMED_PROFILES * 2,     # 1 search + 1 email per profile
    "company-information-from-domain": 1,
    "aiark-people-search": 2,
    "email-verifier": 1,
    "deliverable-verify": 1,
    "reoon-verify": 1,
    "apify-research": 0,        # billed in compute units, not credits
    # Blitz bills in records, not credits. `fair_usage.records_used` on the
    # response is the real cost; these are what the cap assumes before the
    # answer is known, one record per subject.
    "blitz-domain-to-linkedin": 1,
    "blitz-linkedin-to-domain": 1,
    "blitz-company": 1,
    "blitz-employee-finder": ASSUMED_PROFILES,
    "blitz-email": 1,
}

# Why a fallback ran, in words a machine can group by. A fallback with no
# reason is a bug, not a judgement call.
CONTACTOUT_NO_PEOPLE = "contactout_no_people"
CONTACTOUT_MISSING_COMPANY_DATA = "contactout_missing_company_data"
CONTACTOUT_NO_TARGET_PERSONA = "contactout_no_target_persona"
CONTACTOUT_RESULT_COLLISION = "contactout_result_collision"
CONTACTOUT_REBRAND_DETECTED = "contactout_rebrand_detected"
CONTACTOUT_INCOMPLETE = "contactout_incomplete"
PUBLIC_EVIDENCE_REQUIRED = "public_evidence_required"
DOMAIN_UNSTAFFED = "contactout_domain_unstaffed"
# ContactOut answers both of these questions or provably cannot. `li_vanity`
# is on its /domain/enrich response, so a missing company LinkedIn URL is a
# real miss; a mail domain is absent from every ContactOut response under any
# spelling, which is a permanent gap rather than a miss. Both have to be
# stated before Blitz is paid.
CONTACTOUT_NO_COMPANY_LINKEDIN = "contactout_no_company_linkedin"
CONTACTOUT_NO_EMAIL_DOMAIN = "contactout_no_email_domain"

# Which waterfall stage each paid call belongs to. The waterfall module owns
# the policy; this is the only place that says which stage a given call is an
# instance of, so a new call has to be routed deliberately rather than falling
# out of the ledger silently. `waterfall.py` imports this module for its reason
# vocabulary, so the import back is deferred to call time inside `spend()`.
CALL_STAGE = {
    "people-count": "people_discovery",
    "decision-makers": "people_discovery",
    "aiark-people-search": "people_discovery",
    "company-information-from-domain": "company_information",
    "email-verifier": "email_verification",
    "deliverable-verify": "email_verification",
    "reoon-verify": "email_verification",
    "apify-research": "company_research",
    "blitz-domain-to-linkedin": "company_information",
    "blitz-linkedin-to-domain": "company_information",
    "blitz-company": "company_information",
    "blitz-employee-finder": "people_discovery",
    "blitz-email": "email_discovery",
}

FALLBACK_REASONS = (CONTACTOUT_NO_PEOPLE, CONTACTOUT_MISSING_COMPANY_DATA,
                    CONTACTOUT_NO_TARGET_PERSONA, CONTACTOUT_RESULT_COLLISION,
                    CONTACTOUT_REBRAND_DETECTED, CONTACTOUT_INCOMPLETE,
                    PUBLIC_EVIDENCE_REQUIRED, DOMAIN_UNSTAFFED,
                    CONTACTOUT_NO_COMPANY_LINKEDIN,
                    CONTACTOUT_NO_EMAIL_DOMAIN)

TERMINAL = ("pushed", "dropped")


# Calls this system CANNOT price, because the provider bills them in a unit
# it does not report back. `COSTS["apify-research"]` is 0 for that reason - not
# because an actor run is free. It is billed in Apify compute units, which is
# real money the credit cap cannot see.
UNPRICED = ("apify-research",)


class Budget:
    """The cap. Refuses the call rather than going over."""

    def __init__(self, cap=None):
        self.cap = cap
        self.spent = 0
        self.refused = []

    def affordable(self, cost, call=None):
        # A CAP OF ZERO MEANS START NOTHING THAT COSTS MONEY. An unpriced call
        # costs 0 by arithmetic and is affordable at every cap including zero,
        # so `--cap 0` - which an operator reads as "spend nothing" - would
        # still start a billable Apify actor. It did: a run capped at zero
        # spent roughly 33 seconds per record in compute units, and the cap
        # reported clean because it was watching a number that is always 0.
        #
        # Only zero is treated this way. A positive cap is a statement about
        # credits, and refusing an unpriced call under it would make every
        # capped run silently skip research.
        if self.cap == 0 and call in UNPRICED:
            return False
        return self.cap is None or self.spent + cost <= self.cap

    def charge(self, cost, what, call=None):
        if not self.affordable(cost, call=call):
            self.refused.append(what)
            return False
        self.spent += cost
        return True

    def refund(self, cost):
        """Return credits when a provider declines to charge.

        The budget is charged before the call so the cap can refuse it, but a
        provider that returns `charged: False` never billed the credit. Without
        a refund the budget over-reports by exactly that cost, and the waterfall
        - which records after the call - disagrees with it.
        """
        self.spent = max(0, self.spent - cost)

    def remaining(self):
        return None if self.cap is None else max(0, self.cap - self.spent)


def op(call, why, cost=None, conditional=False, provider="contactout"):
    return {"call": call, "why": why, "provider": provider,
            "conditional": conditional,
            "cost": COSTS.get(call, 0) if cost is None else cost}


def exposure(ops):
    """Expected spend versus the worst case. They are not the same number."""
    return {"expected": sum(o["cost"] for o in ops if not o.get("conditional")),
            "maximum": sum(o["cost"] for o in ops)}


def usable_contacts(rec):
    """Contacts on this record that already carry an address."""
    return [c for c in rec.get("contacts") or [] if c.get("email")]


def verification_candidates(rec):
    """The contacts verification may be BOUGHT for, in priority order.

    THE CAP ALREADY EXISTED AND NOTHING READ IT. `routing.plan` computes
    `max_contacts_to_enrich` per company - 3 for tier A, 2 for B, 1 for C, 0 for
    anything not qualified - and its docstring says in as many words that this
    "is the number that controls spend". It is stored on every record under
    `qualification.persona_plan`. Its readers were `dmplan`, `explorer`,
    `qualify` and `report`: a forecast, two screens and a report. Verification
    read `usable_contacts(rec)` - every address on the record - at up to three
    credits each.

    That is the largest single waste in the system. `decision-makers` can return
    dozens of addressed profiles for one company, and `personas.select` - which
    would have trimmed them to the cap - runs AFTER enrichment in
    `run.STAGES`, so the credits are gone before the selection that makes them
    pointless. Measured at 30,000 domains it is roughly a quarter of a million
    credits verifying people the system has already decided never to write to.

    ORDER MATTERS, because a cap without an order buys an arbitrary subset.
    Candidates are sorted by where their title appears in the plan's own
    `target_titles`, which is the same ordered list `personas.select` uses, so
    the addresses bought are the ones selection would have chosen. Ties fall
    back to the contact key, so the choice is reproducible after a restart
    rather than dependent on dict order.

    A record with no `persona_plan` is NOT capped, and that is deliberate: the
    cap is a decision made by qualification, and inventing one here for a record
    qualification has not seen would be guessing at a spend limit rather than
    honouring one. Those records are reported, not silently uncapped.
    """
    candidates = usable_contacts(rec)
    plan = ((rec.get("qualification") or {}).get("persona_plan") or {})
    if "max_contacts_to_enrich" not in plan:
        return candidates
    cap = plan.get("max_contacts_to_enrich") or 0
    titles = [str(t).strip().lower() for t in plan.get("target_titles") or []]

    def rank(contact):
        title = str(contact.get("title") or "").strip().lower()
        for i, wanted in enumerate(titles):
            if wanted and wanted in title:
                return (0, i, str(contact.get("key") or ""))
        # No declared title matched. Last, but still a candidate: the cap is
        # about how many, not about who qualifies.
        return (1, 0, str(contact.get("key") or ""))

    return sorted(candidates, key=rank)[:max(0, int(cap))]


def unverified(rec):
    return [c for c in usable_contacts(rec) if not c.get("verdict")]


def catch_alls(rec):
    """accept_all with no Reoon answer yet. Section 9, trap 2."""
    return [c for c in rec.get("contacts") or []
            if c.get("verdict") == "accept_all" and not c.get("reoon")]


def plan(rec, config=None):
    """What this record needs, and why. No call without a reason.

    Conditional operations are marked: a maximum exposure is not a forecast.
    """
    ops = []
    if rec.get("state") in TERMINAL:
        return ops
    # Asked about the answer, not about the dict.
    #
    # This tested `not rec.get("company_facts")`, and the call it guards
    # writes only `headcount_signal` - so *any* other writer of any other
    # key suppressed the free count. `staffed` was then None, `unstaffed`
    # was False, and a record with no contacts went straight to the paid
    # `decision-makers` on a domain that might be parked. The free call
    # exists precisely to stop that.
    if "headcount_signal" not in (rec.get("company_facts") or {}):
        ops.append(op("people-count",
                      "free: confirm the domain is real and staffed before spending"))
    if not usable_contacts(rec):
        # A forecast that promises calls the gate will refuse is worse than no
        # forecast, because it is the number an operator sizes a cap against.
        # Unasked, this reported 10 expected and 13 maximum for a company with
        # no verdict, where the truth is 1 - and filed that single real credit
        # under "maximum" rather than "expected", because it was described as
        # conditional on a call that can no longer run.
        from . import fieldplan
        person_ok, _state = person_level_allowed(rec)
        staffed = (rec.get("company_facts") or {}).get("headcount_signal")
        # The same two questions the execution path asks, in the same order.
        # `bought` reads the ledger; `owed` reads the fields. A forecast that
        # asked only the first promised twenty-five credits the run would
        # refuse - and the forecast is the number a cap is sized against, so
        # the two have to be one predicate rather than two that agree today.
        bought = (already_bought(rec, "company-information-from-domain")
                  or not fieldplan.company_info_is_owed(rec))
        if staffed == 0:
            if not bought:
                ops.append(op("company-information-from-domain",
                              "people-count found nobody here: rebrand check, no "
                              "search credit spent on people"))
        elif person_ok:
            ops.append(op("decision-makers",
                          "the record has no contact with an address"))
            if not bought:
                ops.append(op("company-information-from-domain",
                              "only if decision-makers finds nobody: check for a "
                              "rebrand", conditional=True))
        elif not bought:
            ops.append(op("company-information-from-domain",
                          "no ICP verdict, so no person-level call: company facts "
                          "are what produce the verdict"))
        if person_ok:
            ops.append(op("aiark-people-search",
                          "only if ContactOut finds nobody usable: different index",
                          conditional=True, provider="aiark"))
    # The headcount second opinion, forecast with the SAME predicate execution
    # uses. `verification.py` carries the note about what happens when a
    # forecast and its execution disagree, and this is the number a cap is
    # sized against. Not nested in the contact branch above, for the reason the
    # call site is not: a company with contacts can still be missing its size.
    from . import fieldplan as _fieldplan

    headcount_step, _why = _fieldplan.next_step(rec, "headcount")
    if (headcount_step and headcount_step["call"] == "blitz-company"
            and (rec.get("company_facts") or {}).get("linkedin")
            and not already_bought(rec, "blitz-company")):
        ops.append(op("blitz-company",
                      "the company record carries a headcount with no band, so "
                      "it cannot be read as one, and this client rejects on "
                      "size", provider="blitz"))
    policy = verification.policy_for(config)
    for c in usable_contacts(rec):
        for step in verification.plan(c, policy):
            ops.append({
                "call": f"{step['provider']}-verify",
                "provider": step["provider"],
                "why": f"{c['email']}: {step['reason']}",
                "cost": step["cost"],
                "conditional": step["conditional"],
            })
    return ops


def same_company(person, rec, facts=None):
    """Section 9, trap 1: an owner in Nice at an unrelated company of the same
    name must not be merged into this record.

    Domain is the identity WHEN THERE IS ONE. That is the first branch and it
    is the one that decides in practice - all 25 contacts in the estate today
    came through it, and it has excluded 40 people as "not this domain".

    The second branch is weaker than the sentence above, and saying so is the
    point of this paragraph: a person carrying no address is accepted on a
    lowercase company-NAME match, which is the very trap the first line names.
    It is not tightened, for a reason rather than by neglect. Both callers
    search BY DOMAIN - `decision_makers(rec["domain"])` and
    `people_search(companyDomain=...)` - so the payload is already scoped to
    this company before this function sees it, and this branch is a second
    opinion on that scoping rather than the only thing standing between two
    firms with one name. Removing it would reject every profile-only person a
    domain-scoped search returns, which is exactly the population the LinkedIn
    lane runs on.

    So: a name match here is licensed by the caller's domain scoping, not by
    the name. A caller that searches any other way may not use this function
    without adding a domain check of its own.

    AND THE DOMAIN SCOPING IS WEAKER THAN THE PARAGRAPH ABOVE ASSUMES.
    `work/validation/decision-makers.json` is a recorded live response: the
    call asked for `domain=resonategroup.co` and came back with a person whose
    company object reads `{"name": "Resonate Group", "domain":
    "resonategroup.com.au", "email_domain": "resonategroup.com.au"}` - a
    different firm with the same name. So `?domain=` is a search term, not a
    filter, and this branch is doing real work rather than seconding a
    guarantee. Do not loosen it into "domain-scoped, therefore accept".

    What would settle it is already in that payload and thrown away before
    this function sees it: `providers/contactout._person` trims `company` to
    its NAME and discards `company.domain` and `company.email_domain`.
    Matching those against `rec["domain"]` is strong evidence where a name is
    a guess. Until that lands, this compares names - and two things about how
    it did that were wrong in the same direction, both measured on live
    payloads after the exclusions started being kept whole:

    A PERSONAL MAILBOX WAS READ AS A DIFFERENT EMPLOYER. The first branch
    short-circuited on any address at all, so `personal@example.test` answered
    "not this domain" for a man whose payload `company` reads "&Partner ApS"
    at the record for &Partner ApS. Five of the first eleven exclusions
    measured this way were exactly that, every one of them at the right
    company: a Partner, a Client Director, a VP. A webmail address says which
    mailbox somebody uses and nothing whatever about who employs them, so
    reading it as evidence of another employer is missing evidence used as
    positive evidence - the error CLAUDE.md names in as many words. It now
    falls through to the name rather than deciding.

    AND THE NAME WAS COMPARED AGAINST A DOMAIN. `rec["company"]` holds the
    DOMAIN STRING on 272 of the 300 records in this estate, so the comparison
    was "academy xi" against "academyxi.com" and could not match however right
    the person was. `company_facts["name"]` is ContactOut's own name for the
    domain we asked about, which is the label a payload's `company` is spelled
    in; both are consulted now.

    Neither loosens what an ADDRESS decides. A work address at another domain
    still excludes, even when the company name matches - that is real evidence
    about where somebody works, and `test_trap_1_an_address_outranks_a_
    matching_company_name` pins it. A mailbox provider this list does not know
    falls through to the same exclusion as before, which is the safe way for
    the list to be incomplete.
    """
    facts = facts if facts is not None else (rec.get("company_facts") or {})
    domain = (rec.get("domain") or "").lower()
    mail_domain = (facts.get("email_domain") or "").lower()
    email = (person.get("email") or "").lower()
    at = email.split("@")[-1] if "@" in email else None
    if at and (at == domain or (mail_domain and at == mail_domain)):
        return True
    if at and at not in FREE_MAIL:
        return False    # a work address somewhere else answers the question
    company = (person.get("company") or "").lower().strip()
    # No evidence of identity is still not evidence of a match: a row with no
    # address and no company name leaves by the same door it always did.
    return bool(company) and company in company_labels(rec, facts)


# Mailbox providers that are not companies. An address here is not a work
# domain, so it neither confirms nor contradicts an employer. Deliberately
# short and deliberately not inferred: a provider missing from this set is
# treated as a work domain, which excludes, which is the direction an
# incomplete list should fail in.
FREE_MAIL = frozenset({
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.co.uk",
    "outlook.com", "live.com", "msn.com", "yahoo.com", "yahoo.co.uk",
    "ymail.com", "aol.com", "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me", "gmx.com", "gmx.de", "gmx.net", "web.de",
    "mail.com", "zoho.com", "yandex.com", "yandex.ru",
    # Reserved domain for tests. A fixture must not carry a real provider's
    # address; this entry lets a test exercise the webmail branch on a domain
    # that resolves to nothing.
    "mail.test",
})


def company_labels(rec, facts=None):
    """Every spelling of this company's name the record actually holds.

    Two, because the record keeps the name in two places and which one is
    populated varies: `company` is the label the batch was ingested with - a
    domain string far more often than a name - and `company_facts["name"]` is
    what the company-information call answered for that domain.
    """
    facts = facts if facts is not None else (rec.get("company_facts") or {})
    return {name for name in ((rec.get("company") or "").lower().strip(),
                              (facts.get("name") or "").lower().strip())
            if name}


# What a provider payload may fill in on somebody already here. Deliberately
# not the address, the verdict or the evidence: those are bought, and a later
# search result is not permission to replace them.
FILLABLE = ("title", "linkedin", "name")


# The handles that ARE identity, in the order they decide. An address or a
# canonical profile URL identifies one person. A name does not: two people
# share one and one person has three. `referral.py` states that rule in its
# own module docstring for the same reason, and this module used to disagree
# with it - which is the bug `test_a_name_is_not_an_identity` reproduces.
STRONG = ("email", "linkedin")


def handle(field, value):
    """One comparable form of a handle, or None if there is not one.

    Normalised rather than lowercased. The estate stores a profile as a bare
    vanity slug - `jannovak`, not a URL, in every one of the 25 that carry a
    profile today - and a provider returns a full URL, so raw comparison
    reads those as two people. Separating one person is not the
    safe direction here: it mints a second contact, and a fresh dict carries
    `verdict: None`, which throws away a verification somebody paid for.
    """
    if field == "email":
        return dedupe.normalise_email(value)
    if field == "linkedin":
        return linkedin.canonical(value)
    return str(value or "").strip().lower() or None


def disagree(contact, person):
    """Do these two carry DIFFERENT values for a handle they BOTH have?

    The check that makes a shared name stop being an identity. If one record
    has an address or a profile and the other has a different one, they are
    two people whatever they are called.

    Note what this deliberately does NOT do: a name match against a contact
    carrying no strong handle at all still stands. That is the case the name
    index exists for - somebody known only by name who later arrives with an
    address - and refusing it would bring back the double-minting this
    function's docstring describes. The guard removes matches contradicted by
    evidence, not matches with no evidence either way.
    """
    for field in STRONG:
        ours = handle(field, contact.get(field))
        theirs = handle(field, person.get(field))
        if ours and theirs and ours != theirs:
            return True
    return False


# Why a payload row did not become a contact at this company. TWO FINDINGS,
# and they were both recorded as the first of them.
#
# Measured on the Productive estate: 80 people sat in `excluded` under
# "company name collision: not this domain", which reads as eighty people
# discarded for working somewhere else. FIFTY of them are AI Ark rows in
# which `name`, `title`, `email` and `linkedin` are ALL absent - a paid
# fallback returned rows this system cannot read, on the two records whose
# `decision-makers` call had timed out and sent it there. Nobody was at the
# wrong company; nobody was identified at all, and `ai ark: 0 kept` is in
# both logs beside twenty-five exclusions each.
#
# The distinction is not cosmetic. A collision count is read as evidence that
# the identity check is working hard; "the fallback returns rows we cannot
# parse" is a bug with a credit cost, and for a fortnight it wore the other
# one's name.
COLLISION = "company name collision: not this domain"
UNIDENTIFIED = "the provider returned a row that identifies nobody"


def identifies_nobody(person):
    """Is there anything on this row that names a person at all?

    `title` is deliberately not enough. A row carrying "CEO" and nothing else
    is not somebody who could be contacted, looked up or de-duplicated, and
    counting it as a person found at the wrong company is how a fallback that
    returned nothing reported as an identity check doing its job.
    """
    return not any(person.get(field) for field in ("name", "email", "linkedin"))


def exclusion_reason(person):
    """What to write down when `same_company` says no.

    Separate from `same_company`, which answers one question - does this
    person belong here - and must keep answering exactly that.
    """
    return UNIDENTIFIED if identifies_nobody(person) else COLLISION


def merge_contacts(rec, people, source):
    """Add people that belong to this company; fill in the ones already here.

    A payload that re-discovers somebody already on the record is not a new
    contact. This matched on a *single* marker - the first of email, LinkedIn
    or name that was set - so a person known by name who came back with an
    address was minted a second time, and the persona cap then chose between
    the evidenced dict and the bare one.

    Worse, minting is destructive when the caller is holding the only reference
    to the original. A fresh dict carries `verdict: None` and no `verification`
    key, so re-discovering a verified person and replacing them deletes paid
    provider answers - which is how three verifications for one address became
    "no verification evidence" while the waterfall ledger still showed the
    spend. Filling in an existing contact cannot do that.
    """
    facts = rec.get("company_facts") or {}
    # Two indexes, not one, because a strong handle and a name are not the
    # same kind of evidence and must not be consulted as though they were.
    # One dict keyed by `markers()` made them interchangeable, and because it
    # was iterated as a SET the winner was undefined: the same payload could
    # merge on the address in one run and on the name in the next.
    strong_index, name_index = {}, {}

    def remember(contact):
        for field in STRONG:
            found = handle(field, contact.get(field))
            if found:
                strong_index.setdefault(found, contact)
        name = handle("name", contact.get("name"))
        if name:
            name_index.setdefault(name, contact)

    def match(person):
        """The contact this payload is about, or None to mint a new one."""
        for field in STRONG:
            found = handle(field, person.get(field))
            if found and found in strong_index:
                return strong_index[found]
        name = handle("name", person.get("name"))
        candidate = name_index.get(name) if name else None
        if candidate is not None and not disagree(candidate, person):
            return candidate
        return None

    for contact in rec.get("contacts") or []:
        remember(contact)
    added, excluded = [], []
    for p in people:
        if not same_company(p, rec, facts):
            # KEPT WHOLE, for the reason `personas.set_aside` states in its own
            # docstring and this call site did not follow: an exclusion is a
            # decision about a person, not a reason to forget them. This stored
            # `{name, title, why}` and dropped the address, the profile, the
            # location and - the one that matters most here - the COMPANY NAME
            # the decision was actually made on. So the 80 exclusions on this
            # estate cannot be audited: the field that decided each one is not
            # on the record, and re-deriving it means buying the search again.
            excluded.append(dict(p, why=exclusion_reason(p)))
            continue
        hit = match(p)
        if hit is not None:
            for field in FILLABLE:
                if not hit.get(field) and p.get(field):
                    hit[field] = p[field]
            if not hit.get("email") and p.get("email"):
                hit["email"] = p["email"]
                hit["email_source"] = source
            remember(hit)
            continue
        fresh = {"name": p.get("name"), "title": p.get("title"),
                 "linkedin": p.get("linkedin"), "email": p.get("email"),
                 "email_source": source, "persona": None, "angle": None,
                 "verdict": None, "reoon": None, "sendable": False,
                 "primary": False}
        added.append(fresh)
        remember(fresh)

    # Keys before anybody can write an event about these people.
    #
    # `assign_keys` ran in `personas.select`, which is two stages after
    # enrichment - and `mx` can run standalone at any time. So MX lookups,
    # blocks and verification results were recorded with `contact: None`,
    # which `events.record`'s duplicate guard treats as one identity: two
    # contacts at one domain in the same second collapsed into a single
    # stored event and the second was silently lost.
    #
    # Contacts and excluded share one namespace, because a key is an identity
    # and an exclusion is a decision about a person, not a new person.
    identity.assign_keys((rec.get("contacts") or []) + added
                         + (rec.get("excluded") or []) + excluded)
    return added, excluded


def reconsider_exclusions(rec, source="provider"):
    """Re-ask `same_company` about people already bought and set aside.

    Without this the fix above changes NOTHING for anybody. `merge_contacts`
    is the only caller of `same_company`, it runs only on a fresh payload, and
    nothing anywhere reads an exclusion again - so a corrected identity check
    would apply to future discoveries and leave every person it was corrected
    for sitting in `excluded`, on an estate where the discovery has already
    happened. `personas.readmit` exists for exactly this reason one stage
    later, and states it: an exclusion is a decision about a person, not a
    reason to forget them.

    The payload is on the record, so this costs nothing. Re-buying it would
    cost ten credits a company for people already paid for.

    Routed back through `merge_contacts` rather than re-implemented: that is
    the one door where `same_company` decides, identity de-duplicates and a
    contact is minted in the right shape, and a second copy of that logic
    would be the thing that drifts. Anybody it still rejects goes straight
    back into `excluded` with the current reason.

    Only exclusions THIS module made, and only the collision reason. A
    persona exclusion and a cap exclusion are different decisions taken
    further down the pipeline, and a row that identifies nobody has nothing to
    reconsider.
    """
    held = [e for e in (rec.get("excluded") or []) if e.get("why") == COLLISION]
    if not held:
        return []
    rec["excluded"] = [e for e in (rec.get("excluded") or [])
                       if e.get("why") != COLLISION]
    payload = [{k: v for k, v in entry.items() if k not in ("why", "key")}
               for entry in held]
    added, still_out = merge_contacts(rec, payload, source)
    rec.setdefault("contacts", []).extend(added)
    rec["excluded"].extend(still_out)
    if added:
        store.log(rec, "enrich",
                  f"{len(added)} contact(s) set aside as a company-name "
                  "collision are this company after all: returned to the "
                  "record rather than re-bought")
        for person in added:
            events.record(rec, events.CONTACT_FOUND, source=source,
                          name=person.get("name"))
    return added


# What a cap hit leaves behind. Not a drop reason: nothing here is a finding
# about the company.
BUDGET_REFUSED = "cap reached before this record was finished"

# Neither is a company we were not allowed to look at.
ICP_DEFERRED = "no ICP verdict yet, so no person-level call was made"
ICP_REJECTED = "rejected at ICP: no person-level enrichment"

# The calls that spend a credit on a *person*. Company-level calls are what
# produce the verdict, so gating those would make the verdict unobtainable.
PERSON_LEVEL = ("decision-makers", "aiark-people-search",
                # Every Blitz call that returns a person or a person's
                # contact details. `blitz-phone` is not wired into any
                # stage and is named anyway: a call added to the waterfall
                # later must arrive already gated.
                "blitz-employee-finder", "blitz-email", "blitz-phone")


def icp_state(rec):
    """This company's own ICP state, from the canonical resolver.

    Deferred import: `qualify` imports `dmplan`, which imports this module for
    its cost table.
    """
    from . import qualify

    return qualify.state_of(rec)


def person_level_allowed(rec):
    """May we spend a person credit on this company yet?

    CLAUDE.md: "Company first. No paid person-level call before a company
    reaches an explicit ICP verdict, and rejected, review and unknown all mean
    zero person credits."

    Nothing enforced it. This module imported neither `icp` nor `dmplan`, and
    `run()` selects on `state` alone, so a company explicitly marked
    `rejected` was planned and charged for `decision-makers` - ten credits -
    exactly like a qualified one, as was a company nobody had assessed.

    `dmplan.may_enrich` calls itself "the single gate" and has no caller on
    any path that spends; its only production caller is a screen in
    `web/api.py` that renders the answer. Its stricter clause cannot be used
    here yet: it requires `dm_approval` on a batch, and `dmplan.DM_APPROVED`
    is unreachable because nothing in `src/` writes `dm_approved` - so
    demanding it would not gate person enrichment, it would end it. That gap
    is recorded in PRODUCT-GAPS.md rather than papered over here.

    What this asks instead is `qualify.state_of`, the canonical resolver over
    the same vocabulary, which already folds in a human's explicit rejection
    and treats review and unknown alike. Returns (allowed, state).
    """
    state = icp_state(rec)
    from . import dmplan

    return state in (dmplan.QUALIFIED, dmplan.DM_APPROVED), state


def already_bought(rec, call):
    """Has this record already paid for this call?

    Read off the waterfall ledger, which `spend()` writes for every paid call,
    rather than off a new flag - the ledger is already the canonical record of
    what was bought, and a second one would drift from it.

    This matters because a record can now legitimately be processed more than
    once. A company held back by the ICP gate stays `queued` rather than being
    dropped, which is correct, and before this guard the rebrand check was
    re-bought on every pass: one credit per company per run, indefinitely, for
    an answer already on the record.
    """
    return any(step.get("call") == call for step in (rec.get("waterfall") or []))


def person_level_pending(rec):
    """Person-level work this record still needs but was not allowed to do.

    Derived rather than stored: a flag for this would be a second
    representation of the verdict, and the two would drift. A rejected company
    is *not* pending - that decision is final, and re-asking it every run
    would be a queue that never empties.
    """
    from . import dmplan

    if usable_contacts(rec):
        return False
    allowed, state = person_level_allowed(rec)
    return not allowed and state != dmplan.REJECTED


PROVIDER_FAILED = "a provider call failed, so absence was never established"


def outcome(rec, refused=False, state=None, failed=False):
    """The state this record has earned. Hold rather than guess.

    `refused` says the budget turned down at least one call for this record.
    That is a fact about our wallet, not about this company, and it used to be
    recorded as one: `enrich_record` ran to the end regardless, found no
    contacts because it had not been allowed to look for any, and returned
    `("dropped", "no contact found at this domain")`. `dropped` is terminal in
    `run.TERMINAL` and outside `run()`'s default states, so the tail of every
    capped batch was permanently retired with a reason that was not true - by
    a cap that was working exactly as designed.

    A refusal therefore returns the record to the state it arrived in, which
    is already in the retry set, and says so. No new state machine: `queued`
    and `enriched` are where the runner looks anyway.

    `failed` is the same argument about a different cause, and it was missing.
    A PROVIDER TIMEOUT also manufactures absence. On 2026-09-11 `e-2.at` - an
    87-person Creative/Branding agency in DACH, qualified, tier C, score 49,
    medium confidence - was permanently dropped with "no contact found at this
    domain" after `decision-makers` raised a TimeoutError. Nothing had been
    established about that domain at all; a socket gave up.

    `mx.py` states the general rule: "A temporary resolver failure must never
    read as no gateway found." This is that rule, one provider over.
    """
    contacts = rec.get("contacts") or []
    if any(c.get("sendable") for c in contacts):
        return "verified", None
    if refused:
        # Every remaining branch below is a conclusion drawn from absence, and
        # absence is exactly what a cap manufactures.
        return rec.get("state") or "queued", BUDGET_REFUSED
    if not contacts and state is not None:
        from . import dmplan

        # A rejected company has no contacts because we declined to look for
        # any, and that is a real and final decision - so it drops, but under
        # the reason that is true.
        if state == dmplan.REJECTED:
            return "dropped", ICP_REJECTED
        if state not in (dmplan.QUALIFIED, dmplan.DM_APPROVED):
            # Waiting on a verdict or on a human. Not a finding, and not
            # terminal: the record goes back where the runner looks.
            return rec.get("state") or "queued", ICP_DEFERRED
    if failed and not contacts:
        # A provider that did not answer also manufactures absence. Placed
        # AFTER the rejection branch on purpose: an ICP rejection is a
        # decision, and a coincidental timeout must not rescue a company the
        # model has already ruled out. My first version had these the other way
        # round and a test said so.
        return rec.get("state") or "queued", PROVIDER_FAILED
    if not contacts:
        return "dropped", "no contact found at this domain"
    unresolved = [c for c in contacts
                  if c.get("verdict") in (None, "unknown", "accept_all")]
    if unresolved:
        verdicts = {c.get("verdict") for c in unresolved}
        if verdicts <= {"accept_all"}:
            return "held", "enrich:accept_all_uncleared"
        return "held", "enrich:unresolved_verdict"
    return "dropped", "no address cleared verification"


def enrich_record(rec, budget, live=False, log=None, config=None,
                  scrape_budget=None, mx_cache=None):
    """Walk one record through the waterfall. Returns the ops actually done.

    The order is ContactOut first, every time: a stored result beats a call, a
    free call beats a paid one, and a paid ContactOut call beats a fallback.
    AI Ark runs only on a stated ContactOut miss, and Apify only when public
    evidence is actually required.
    """
    done = []
    log = log if log is not None else []
    # Whether any provider call failed on this pass. Read by `outcome`, which
    # must not conclude "nobody is there" from a call that never answered.
    failures = []
    # The budget is shared across the batch, so "was anything refused" has to
    # be asked as a difference rather than as a state.
    # Deferred: `fieldplan` imports this module for its reason vocabulary,
    # exactly as `waterfall` does in `spend()` below.
    from . import fieldplan
    refusals_before = len(budget.refused)
    events.record(rec, events.ENRICHMENT_STARTED)

    def spend(call, why, provider="contactout", reason_code=None):
        cost = COSTS.get(call, 0)
        # Company first, refused here rather than at each call site, so a
        # person-level call added later is gated by construction instead of by
        # whoever remembers to ask.
        if call in PERSON_LEVEL:
            allowed, state = person_level_allowed(rec)
            if not allowed:
                log.append(f"{rec['id']}: no ICP verdict ({state}), "
                           f"skipped {call}")
                events.record(rec, events.PROVIDER_CALL_SKIPPED,
                              provider=provider, operation=call,
                              reason=f"no icp verdict: {state}")
                return False
        events.record(rec, events.PROVIDER_CALL_PLANNED, provider=provider,
                      operation=call, reason=reason_code or why[:80],
                      estimated_cost=cost)
        if not budget.charge(cost, f"{rec['id']}:{call}", call=call):
            log.append(f"{rec['id']}: cap reached, skipped {call}")
            events.record(rec, events.PROVIDER_CALL_SKIPPED, provider=provider,
                          operation=call, reason="cost cap reached")
            return False
        # THE CEILING THAT SURVIVES THE RUN. `budget` above is in memory and
        # dies with the process, so `--cap 260` bounds THIS invocation and
        # nothing remembers the last one. Three passes at 260 over one cohort
        # on 2026-09-10 were each individually inside budget and nothing in
        # the system could state the total.
        #
        # ONLY WHEN THE CALL IS ACTUALLY GOING TO HAPPEN. `spend()` is
        # evaluated BEFORE the `if live:` that performs the call, so a dry run
        # reaches here for every call it is planning. The in-memory budget is
        # charged anyway and should be - that is what makes a dry run able to
        # say what it WOULD cost. The durable ledger must not be, because it
        # holds money committed rather than money contemplated, and a planning
        # run that consumed a real ceiling would be a spend control that
        # punishes people for checking first.
        #
        # Gated around the LEDGER ONLY, not around the rest of this closure. A
        # first version returned early here, which also skipped `done.append`
        # below - and `done` is what a dry run reports as "what this would
        # do". Five tests in `test_icp_spend_gate` said so: a planning run
        # stopped listing even `people-count`, which costs nothing.
        if live:
            # Checked AFTER the in-memory cap so the cheap refusal stays
            # cheap, and recorded only once both have allowed it.
            from . import spendledger
            try:
                spendledger.check(rec.get("client"), config, cost,
                                  provider=provider)
            except spendledger.BudgetExceeded as e:
                log.append(f"{rec['id']}: {e}")
                events.record(rec, events.PROVIDER_CALL_SKIPPED,
                              provider=provider, operation=call,
                              reason=f"durable budget: {e}"[:200])
                return False
            spendledger.record(rec.get("client"), provider, call, cost)
        done.append({"call": call, "why": why, "cost": cost, "provider": provider,
                     "reason_code": reason_code})
        if cost:
            events.record(rec, events.PROVIDER_CREDIT_ESTIMATED, provider=provider,
                          operation=call, estimated_cost=cost)
        # The ledger the spend audit reads. Written here rather than at each
        # call site because this closure is the one door every provider call
        # goes through: a call that reaches a provider without passing here
        # would not be charged either, so there is nowhere else for one to
        # hide. Deferred import: waterfall imports this module for its reason
        # vocabulary.
        from . import waterfall
        waterfall.record_step(rec, CALL_STAGE.get(call, "people_discovery"),
                              provider, call,
                              reason=reason_code or why,
                              expected_cost=cost)
        return True

    # 1. Free: is this domain real and staffed at all.
    facts = rec.get("company_facts") or {}
    if ("headcount_signal" not in facts
            and spend("people-count", "confirm the domain is staffed")):
        if live:
            try:
                count = contactout.people_count(domain=rec["domain"])
                facts = dict(facts, headcount_signal=count.get("profiles"))
                rec["company_facts"] = facts
                store.log(rec, "enrich", f"people-count: {count.get('profiles')} profiles (free)")
            except ProviderError as e:
                store.log(rec, "enrich", f"people-count failed: {e}")
                failures.append("people-count")

    # Section 5.1: the free count exists to stop a credit being spent on a
    # domain nobody works at. A parked domain goes straight to the rebrand check.
    staffed = (rec.get("company_facts") or {}).get("headcount_signal")
    unstaffed = staffed == 0

    # 1a. FREE, AND BEFORE THE PAID SEARCH ON PURPOSE. People this record
    # already bought and set aside as a company-name collision are re-asked
    # against the current identity check. Placed above `usable_contacts`
    # below, so a company whose only people are readmitted ones does not buy
    # `decision-makers` again for a payload that is already on the record.
    reconsider_exclusions(rec)

    # 2. ContactOut decision makers, only when there is no usable contact.
    if not usable_contacts(rec):
        if unstaffed:
            store.log(rec, "enrich",
                      "people-count returned 0: skipping decision-makers, "
                      "checking for a rebrand instead")
        if not unstaffed and spend("decision-makers",
                                   "no contact with an address on the record"):
            if live:
                try:
                    people = contactout.decision_makers(rec["domain"], reveal_info=True)
                    added, excluded = merge_contacts(rec, people, "provider")
                    rec.setdefault("contacts", []).extend(added)
                    rec.setdefault("excluded", []).extend(excluded)
                    for person in added:
                        events.record(rec, events.CONTACT_FOUND,
                                      source="contactout", name=person.get("name"))
                    store.log(rec, "enrich",
                              f"decision-makers: {len(added)} kept, {len(excluded)} excluded")
                except ProviderError as e:
                    store.log(rec, "enrich", f"decision-makers failed: {e}")
                    failures.append("decision-makers")

        # 3. Nobody found: a parked domain or a rebrand (trap 4).
        why_company_info = ("people-count found nobody at this domain: checking for a rebrand"
                            if unstaffed else
                            "decision-makers found nobody: checking for a rebrand")
        # Asked of the field rather than of the ledger. `already_bought` reads
        # the waterfall, and a record that has never been enriched has no
        # waterfall at all - so on the Productive estate it protected the
        # three records that had a ledger and none of the forty-seven that did
        # not, twenty-five of which already carried the company facts this
        # call buys. The question that stops that is "is the field already
        # known", and `fieldplan` is where it is asked.
        if (not usable_contacts(rec)
                and not already_bought(rec, "company-information-from-domain")
                and fieldplan.company_info_is_owed(rec)
                and spend("company-information-from-domain", why_company_info)):
            if live:
                try:
                    info = contactout.company_info(rec["domain"])
                    rec["company_facts"] = {**(rec.get("company_facts") or {}),
                                            **{k: v for k, v in info.items() if v}}
                    note = "company-info: "
                    if info.get("email_domain") and info["email_domain"] != rec["domain"]:
                        # Trap 3: the mail domain is not the website domain.
                        note += f"mail domain is {info['email_domain']}, not {rec['domain']}"
                    else:
                        note += f"{info.get('name')}, {info.get('employees')} staff"
                    store.log(rec, "enrich", note)
                except ProviderError as e:
                    store.log(rec, "enrich", f"company-info failed: {e}")
                    failures.append("company-info")

        # 4. AI Ark, only on a stated ContactOut miss, never in parallel.
        fallback_reason = (DOMAIN_UNSTAFFED if unstaffed else CONTACTOUT_NO_PEOPLE)
        if rec.get("excluded") and not usable_contacts(rec):
            fallback_reason = CONTACTOUT_RESULT_COLLISION
        if (rec.get("company_facts") or {}).get("email_domain") not in (None, rec["domain"]):
            fallback_reason = CONTACTOUT_REBRAND_DETECTED
        if not usable_contacts(rec) and spend(
                "aiark-people-search",
                f"ContactOut found nobody usable: {fallback_reason}",
                provider="aiark", reason_code=fallback_reason):
            if live:
                try:
                    people = aiark.people_search(companyDomain=rec["domain"])
                    added, excluded = merge_contacts(rec, people, "provider")
                    rec.setdefault("contacts", []).extend(added)
                    rec.setdefault("excluded", []).extend(excluded)
                    for person in added:
                        events.record(rec, events.CONTACT_FOUND, source="aiark",
                                      name=person.get("name"))
                    store.log(rec, "enrich", f"ai ark: {len(added)} kept")
                except ProviderError as e:
                    store.log(rec, "enrich", f"ai ark failed: {e}")
                    failures.append("ai ark")

    # 4a. A SECOND OPINION ON A HEADCOUNT THAT IS ABOUT TO DECIDE A REJECTION.
    #
    # `src/providers/blitz.py` has been live-confirmed since 2026-09-09 and was
    # wired into `COSTS`, `CALL_STAGE`, `waterfall.STAGES` and `fieldplan` -
    # and had ZERO call sites outside tests, so nothing could reach it. A
    # provider that cannot be called is a fixture with a docstring.
    #
    # What licenses it is stated by `fieldplan`, not decided here: the
    # `headcount` field is MISSING_CONFIRMED when the record holds a number
    # with no band, because ContactOut's `employees` is frequently a band's
    # lower bound and a lower bound with no upper bound is not a headcount.
    # Measured on the Productive estate, 123 companies were rejected on
    # exactly that. Blitz is addressed by the company LinkedIn URL already on
    # the record and returns `employees_on_linkedin` beside `size`.
    #
    # NOT nested inside the contact branch above. A company with contacts can
    # still be missing its size, and the size is what the ICP verdict turns
    # on.
    company_linkedin = (rec.get("company_facts") or {}).get("linkedin")
    headcount_step, _why_headcount = fieldplan.next_step(rec, "headcount")
    if (headcount_step and headcount_step["call"] == "blitz-company"
            and company_linkedin
            and not already_bought(rec, "blitz-company")
            and spend("blitz-company",
                      "the company record carries a headcount with no band, "
                      "so it cannot be read as one, and this client rejects "
                      "on size",
                      provider="blitz",
                      reason_code=CONTACTOUT_MISSING_COMPANY_DATA)):
        if live:
            try:
                info = blitz.company(company_linkedin)
                if info["found"]:
                    block = headcount.observe(
                        rec, "blitz-company", value=info.get("employees"),
                        band=info.get("employee_range"), config=config)
                    store.log(rec, "enrich",
                              f"blitz-company: {info.get('employees')} people, "
                              f"band {info.get('employee_range')} -> "
                              f"{block['state']}")
                    if block["state"] == headcount.CONFLICT:
                        events.record(rec, events.PROVIDER_CALL_COMPLETED,
                                      provider="blitz",
                                      operation="blitz-company",
                                      status="headcount_conflict")
                else:
                    # A stated miss, which is an answer: Blitz has been asked
                    # and the ledger row above says so, so nothing re-buys it.
                    store.log(rec, "enrich",
                              "blitz-company: found: false - Blitz does not "
                              "hold this company")
                # `fair_usage.records_used` is the only real cost there is,
                # and it is known only after the answer. Written onto the row
                # `spend()` just appended, because an expected cost standing
                # in for a reported one is what makes a ledger unauditable.
                used = (info.get("fair_usage") or {}).get("records_used")
                if used is not None:
                    for row in reversed(rec.get("waterfall") or []):
                        if row.get("call") == "blitz-company":
                            row["actual_cost"] = used
                            break
            except ProviderError as e:
                store.log(rec, "enrich", f"blitz-company failed: {e}")
                failures.append("blitz-company")

    # 4b. Public evidence, last and only on a stated need. Structured data
    # from ContactOut and AI Ark is always preferred; this runs when a step
    # downstream has nothing to work with.
    #
    # A FREE VERDICT FIRST, BECAUSE ONE OF THE NEEDS CANNOT BE STATED WITHOUT
    # ONE. `research.why` returns NEED_ICP_EVIDENCE only when `icp_status` is
    # "review" or "unknown", and the status is written by the qualify stage,
    # which runs AFTER this one - so on a first pass the status is None, the
    # need was never stated, and no scrape for it ever happened. Measured on
    # the 50-domain pilot: 30 records for which `why` returns NEED_ICP_EVIDENCE
    # today, and zero scrape events on any of them.
    #
    # Six of the twelve ICP dimensions match phrases against prose that
    # structured providers do not return at all, so those companies could not
    # score them however good they were, and LOW confidence forces `review`
    # whatever the score. That is how a pilot returns zero campaign-ready with
    # nothing visibly broken.
    #
    # `qualify.company` spends nothing, which is what makes asking it here
    # legitimate rather than a stage running twice: it is the cheap question
    # that decides whether to ask the expensive one. The qualify stage runs it
    # again afterwards and will see a changed fact fingerprint if research
    # added anything, so the verdict that survives is the one computed with
    # the evidence rather than this one.
    # COMPUTED, NOT STORED. `store_result=False` matters: writing a verdict
    # here would be a second stage doing qualify's job, and it can hold the
    # record - which stopped verification running at all when this was first
    # written that way. The qualify stage owns what is persisted; this only
    # needs to know whether the verdict is open enough to be worth reading
    # the company's website for.
    verdict = None
    if config and not research.why(rec):
        from . import qualify
        try:
            verdict = (qualify.company(rec, config,
                                       store_result=False) or {}).get("verdict")
        except Exception as e:                   # a verdict is not this stage's job
            store.log(rec, "enrich", f"pre-research verdict failed: {e}")
    if config and research.why(rec, verdict=verdict):
        research.run(rec, config, live=live and apify.settings(config)["enabled"],
                     spend=spend, scrape_budget=scrape_budget, verdict=verdict)

    # 4c. MX screening, BEFORE any verifier credit is spent.
    #
    # A DNS lookup is free and one per domain; a verification is two paid calls
    # per address under the double-confirmation policy. Screening first means a
    # domain sitting behind a gateway this client blocks never costs a
    # verifier credit at all - the email channel is closed for it whatever a
    # verifier would have said, so buying that answer is buying nothing.
    #
    # It cannot make anything sendable. `mx` closes a channel and never opens
    # one, so running it earlier changes what is *spent*, never what is
    # *allowed*. The contact stays on the record and LinkedIn is untouched.
    mx_blocked = set()
    if config:
        # Every contact this record is about to verify, not just the selected
        # ones: `mx.apply_to_record` walks `personalization.selected_contacts`,
        # and personas have not necessarily run by the time enrichment does.
        # Screening the wrong set would silently screen nothing.
        # ONE CACHE FOR THE WHOLE RUN, not one per record.
        #
        # This read `mx.load_cache()` here - inside the per-record function -
        # and then called `for_domain(cache=cache, save=False)`. Passing a cache
        # makes `own_cache` False inside `for_domain`, and the persist is gated
        # on `own_cache and save`, so BOTH conditions blocked it: the cache was
        # loaded fresh for every record, mutated in memory, and thrown away.
        # Nothing was ever written to `mx-cache.json`, so every run redid every
        # DNS lookup from scratch.
        #
        # Measured: an unscoped run over 100 records spent 9m40s almost entirely
        # in serial UDP DNS and never reached the records it was asked about.
        # At 24,710 domains that is the difference between minutes and hours.
        #
        # The caller now owns the cache for the whole run and saves it once, so
        # a domain resolves at most once per run and not at all on the next run
        # while its entry is fresh. Freshness is unchanged - `mx._fresh` still
        # applies the client's `cache_days` - and a DNS failure is still not
        # cached, because a resolver that was down for a second must not hold a
        # channel for a week.
        cache = mx.load_cache() if mx_cache is None else mx_cache
        for c in usable_contacts(rec):
            domain = mx.email_domain(c.get("email"))
            if not domain:
                continue
            try:
                c["mx"] = mx.for_domain(domain, config, cache=cache, save=False)
            except Exception as e:                # DNS down: screen nothing
                store.log(rec, "mx",
                          f"{c['email']}: screening skipped ({type(e).__name__})")
        for c in usable_contacts(rec):
            reason = mx.block_reason(c, config)
            # Narrowly: only a *positively identified* blocked gateway. A
            # DNS failure or a domain with no MX also closes the email
            # channel, but neither is evidence about the address, and a
            # resolver that was down for a minute must not quietly cancel the
            # verification of an address that is perfectly good. A recognised
            # Proofpoint or Mimecast record is a different kind of fact: it
            # will still be true tomorrow.
            if reason and reason.startswith(mx.BLOCK_REASON + ":"):
                mx_blocked.add(c.get("key"))
                store.log(rec, "mx",
                          f"{c['email']}: email channel closed ({reason}); "
                          "no verifier credit spent")

    # 5. Verification, in one place. ContactOut first, then only what the
    # policy still needs. src/verification.py owns every decision here, and it
    # is the only module that may conclude an address is sendable.
    policy = verification.policy_for(config)
    candidates = verification_candidates(rec)
    # Visible, not silent. A saving nobody can see is indistinguishable from a
    # contact that was quietly forgotten, and the next person to read the record
    # would wonder why an address on it has no verdict.
    chosen = {c.get("key") for c in candidates}
    for c in usable_contacts(rec):
        if c.get("key") in chosen:
            continue
        events.record(rec, events.PROVIDER_CALL_SKIPPED,
                      contact_key=c.get("key"), provider="verification",
                      operation="verify",
                      reason=f"over the persona cap of "
                             f"{len(candidates)} contact(s) for this company; "
                             f"selection would not have chosen this address")
    for c in candidates:
        if c.get("key") in mx_blocked:
            events.record(rec, events.PROVIDER_CALL_SKIPPED,
                          contact_key=c.get("key"), provider="verification",
                          operation="verify",
                          reason="email channel closed by MX policy before "
                                 "any verifier ran")
            continue
        before = (c.get("verification") or {}).get("state")
        # `config` threaded so the waterfall can consult the client's DURABLE
        # ceiling before each paid call. `cap` and `budget` are both in
        # memory and die with the process; `spendledger` is the one that
        # survives a run, and this is the one door verification reaches it
        # through.
        decision = verification.verify(c, policy, live=live, rec=rec,
                                       budget=budget, config=config)
        if decision.get("cost"):
            done.append({"call": "verification", "provider": "waterfall",
                         "why": f"{c['email']}: {decision['reason']}",
                         "cost": decision["cost"]})
        if decision["state"] != before:
            store.log(rec, "verify",
                      f"{c['email']}: {decision['state']} ({decision['reason']})")

    # Anything that never went through the resolver still gets its verdict from
    # it, so no contact can carry a stale or hand-set sendable flag.
    for c in rec.get("contacts") or []:
        if not c.get("email"):
            c["sendable"] = False
        elif "verification" not in c:
            verification.apply(c, verification.decide(
                verification.all_evidence(c), policy),
                verification.all_evidence(c))
    if not any(c.get("primary") for c in rec.get("contacts") or []):
        for c in rec.get("contacts") or []:
            if c.get("sendable"):
                c["primary"] = True
                break

    refused = len(budget.refused) > refusals_before
    state, reason = outcome(rec, refused=refused, state=icp_state(rec),
                            failed=bool(failures))
    rec["state"] = state
    if state == "dropped":
        rec["drop_reason"] = reason
        events.record(rec, events.RECORD_DROPPED, reason=reason)
    if state == "held" and reason:
        from . import holdreasons
        holdreasons.set_hold_reason(rec, reason)
    events.record(rec, events.ENRICHMENT_COMPLETED, outcome=state)
    store.log(rec, state, reason or f"enriched: {len(done)} provider call(s)")
    return done


class NoBudget(RuntimeError):
    """A live run was asked for with no credit ceiling. Nothing was spent."""


def require_cap(live, cap):
    """Refuse a live run from a command line that named no ceiling.

    `Budget(None)` means unlimited and `--cap` had no default, so `--live` with
    no `--cap` was an unbounded spend over whatever the queue happened to hold.
    At thirty thousand domains that is on the order of 420,000 credits at policy
    defaults, and nothing in the process could stop it: the pilot ceilings cap
    companies, contacts and sends rather than credits, and
    `dm_plan.max_batch_credits` is parsed from client config and used only to
    compute a display string.

    CLAUDE.md's rule is "Cap before you fan out". This refuses rather than
    picking a number, because a default ceiling would be a guess about somebody
    else's budget and a guess that is too high is indistinguishable from none.
    `--cap 0` is accepted and means what it says: plan everything, spend
    nothing.

    Enforced at the CLI rather than inside `run()` so that a library caller -
    including every test that exercises enrichment logic rather than budget
    policy - keeps the explicit semantics it already has.
    """
    if live and cap is None:
        raise NoBudget(
            "a live run needs an explicit --cap. Unlimited is not a ceiling, "
            "and this walks the whole queue: at thirty thousand domains an "
            "uncapped run is hundreds of thousands of credits. Pass --cap 0 to "
            "plan without spending.")
    return True


def run(live=False, cap=None, limit=None, ids=None, states=("queued", "enriched")):
    """Walk the queue. Dry by default: nothing is called and nothing is written.

    `cap=None` means UNLIMITED here, deliberately, because a caller writing
    that in code is making a choice. The refusal lives at the CLI - see
    `require_cap` - because that is where an operator's omission turns into an
    unbounded spend.
    """
    recs = store.load()
    budget = Budget(cap)
    # The scrape ceiling the client config has always declared and nothing
    # enforced. Batch-scoped, like the credit budget, because that is the
    # scope the number is written in.
    scrape_budget = research.RunBudget(None)
    # One MX cache for the whole run, loaded once and saved once. See the long
    # comment in `enrich_record`: this was loaded per record and never written,
    # so every run re-resolved every domain from scratch.
    mx_cache = mx.load_cache()
    mx_cache_at_start = len(mx_cache)
    notes = []
    targets = [r for r in recs
               if (ids is None or r["id"] in ids)
               and (states is None or r.get("state") in states)]
    if limit:
        targets = targets[:limit]

    report = []
    configs = {}
    for rec in targets:
        client = rec.get("client")
        if client not in configs:
            try:
                configs[client] = clients.load(client)
            except Exception:
                configs[client] = None
        config = configs[client]
        if live:
            # The client config was not passed here before, so every part of
            # `enrich_record` that takes one - the verification policy and now
            # the MX screening - silently ran on defaults or not at all.
            #
            # Contained per record, because `store.save` is after this loop.
            # An exception that is not a `ProviderError` - the shape of a
            # provider body being the way it has actually happened - used to
            # leave the loop, skip the save, and discard the enrichment of
            # every record already processed, including the calls already
            # paid for. One bad record is one bad record.
            #
            # This is not a swallowed exception. The record is marked, the
            # reason is on the record and in `notes`, and the report says
            # `failed` rather than reporting nothing and looking clean -
            # which is the failure mode a bare `except` would have.
            try:
                if scrape_budget.cap is None:
                    scrape_budget.cap = apify.settings(
                        config)["max_runs_per_batch"]
                done = enrich_record(rec, budget, live=True, log=notes,
                                     config=config,
                                     scrape_budget=scrape_budget,
                                     mx_cache=mx_cache)
            except Exception as e:
                why = f"{type(e).__name__}: {str(e)[:160]}"
                notes.append(f"{rec['id']}: enrichment failed, {why}")
                store.log(rec, "enrich", f"failed: {why}")
                events.record(rec, events.PROVIDER_CALL_FAILED,
                              provider="enrich", operation="enrich_record",
                              reason=why)
                report.append({"id": rec["id"], "domain": rec.get("domain"),
                               "state": rec.get("state"), "ops": [],
                               "cost": 0, "failed": why})
                continue
        else:
            done = plan(rec, config)
            for o in done:
                budget.charge(o["cost"], f"{rec['id']}:{o['call']}")
        report.append({"id": rec["id"], "domain": rec.get("domain"),
                       "state": rec.get("state"), "ops": done,
                       "cost": sum(o["cost"] for o in done)})

    if live:
        store.save(recs)
        # Persisted once, after the walk. Saving per record would rewrite the
        # whole file per domain, which is the shape of problem this fix exists
        # to remove rather than relocate.
        if len(mx_cache) != mx_cache_at_start:
            mx.save_cache(mx_cache)
    return {"live": live, "records": report, "spent": budget.spent,
            "cap": cap, "refused": budget.refused, "notes": notes,
            "mx_cache": {"at_start": mx_cache_at_start,
                         "at_end": len(mx_cache),
                         "resolved_this_run": len(mx_cache) - mx_cache_at_start}}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.enrich")
    p.add_argument("--live", action="store_true",
                   help="actually call providers and spend credits")
    p.add_argument("--cap", type=int, help="stop once this many credits are committed")
    p.add_argument("--limit", type=int, help="only this many records")
    p.add_argument("--id", action="append", dest="ids")
    a = p.parse_args(argv)

    try:
        require_cap(a.live, a.cap)
    except NoBudget as e:
        print(f"REFUSED: {e}")
        return 2
    result = run(live=a.live, cap=a.cap, limit=a.limit, ids=a.ids)
    head = "ENRICHED" if a.live else "DRY RUN, nothing called"
    print(f"{head}: {len(result['records'])} record(s)")
    expected = maximum = 0
    for r in result["records"]:
        cost = exposure(r["ops"])
        expected += cost["expected"]
        maximum += cost["maximum"]
        print(f"\n  {r['id']} ({r['domain']}) state={r['state']}"
              f"  expected {cost['expected']}, max {cost['maximum']}")
        for o in r["ops"]:
            mark = "conditional" if o.get("conditional") else "planned    "
            print(f"    {mark} {o['call']:<32} {o['cost']:>3} credits  {o['why']}")
    print(f"\nexpected credit spend: {expected}")
    print(f"maximum possible exposure: {maximum}")
    print(f"committed by this run: {result['spent']}"
          + (f" of cap {a.cap}" if a.cap else " (no cap set)"))
    for what in result["refused"]:
        print(f"  refused by cap: {what}")
    for note in result["notes"]:
        print(f"  {note}")
    if not a.live:
        print("\nadd --live to run it. --cap N bounds the spend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
