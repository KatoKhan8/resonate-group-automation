#!/usr/bin/env python3
"""What a reply means, decided conservatively.

Every classification here is a guess about a human being, so the whole module is
built to fail towards `unknown` and towards *not* claiming interest. Three rules
carry most of the weight:

  1. An unsubscribe beats everything. If a message asks to be left alone, it
     does not matter how warm the rest of it reads.
  2. An out-of-office is never positive. "I would love to hear more, I am back
     on the 5th" is an autoresponder, not a buying signal, and treating it as
     one puts a human on a call that nobody agreed to.
  3. Below the confidence threshold, the answer is `unknown` and a person
     looks at it. An unknown costs someone a minute. A false positive costs
     the client's reputation.

Classification never resumes anything. A reply pauses the company - that
happens in events.py, before this module is ever consulted - and no verdict
here can lift it. The worst this can do is fail to raise an alert, which is why
`unknown` is safe and why a model failure degrades to it rather than to
`neutral`.

The model adapter is a seam, not a dependency: deterministic rules run first
and decide the clear cases for free. Tests never reach a model.
"""
import re

VERSION = "rules-1"

POSITIVE = "positive"
NEUTRAL = "neutral"
NEGATIVE = "negative"
UNSUBSCRIBE = "unsubscribe"
ACCOUNT_DNC = "account_do_not_contact"
OUT_OF_OFFICE = "out_of_office"
NOT_NOW = "not_now"
REFERRAL = "referral"
NOT_RELEVANT = "not_relevant"
UNKNOWN = "unknown"

CATEGORIES = (POSITIVE, NEUTRAL, NEGATIVE, UNSUBSCRIBE, ACCOUNT_DNC,
              OUT_OF_OFFICE, NOT_NOW, REFERRAL, NOT_RELEVANT,
              UNKNOWN)

# Only `positive` is worth waking someone for.
ALERTING = (POSITIVE,)

CONFIDENCE_THRESHOLD = 0.6

# Ordered by precedence, and that order is the safety property: unsubscribe is
# tested before anything can call a message warm, and out-of-office before that
# same warmth can be read out of an autoresponder.
# A removal request that speaks for the company, not for the sender.
#
# Tested before `UNSUBSCRIBE`, because every phrasing here also contains a
# personal-removal phrase and the broader reading is the safe one: reading
# "remove us" as "remove me" leaves colleagues contactable after a company
# asked us to stop, and that is the error that cannot be taken back.
#
# Every pattern needs a word that means *more than one person* - company,
# organisation, anyone, all of us. "Remove me" must not reach this list.
ACCOUNT_DNC_PATTERNS = (
    r"\b(?:remove|delete|take) (?:our|the|this) (?:whole |entire )?"
    r"(?:company|organisation|organization|business|firm|team)\b",
    r"\b(?:do not|don'?t|never) (?:contact|email|message|approach) "
    r"(?:anyone|anybody|any(?:one|body) else|us|our (?:staff|team|people|"
    r"employees|company))\b",
    r"\b(?:stop|cease) (?:contacting|emailing|messaging) "
    r"(?:anyone|anybody|us|our (?:staff|team|people|employees|company))\b",
    r"\bno one (?:here|at (?:our|this) company) (?:wants|is interested)\b",
    r"\b(?:remove|take) (?:us|our (?:company|domain|details)) off\b",
    r"\bblacklist (?:our|this) (?:company|domain|organisation|organization)\b",
    r"\bcompany[- ]wide (?:opt[- ]?out|do not contact)\b",
)

UNSUBSCRIBE_PATTERNS = (
    r"\bunsubscribe\b", r"\bopt[- ]?out\b", r"\bremove me\b",
    r"\btake me off\b", r"\bstop (?:emailing|contacting|messaging)\b",
    r"\bdo not (?:contact|email|message) me\b", r"\bgdpr\b",
)
OUT_OF_OFFICE_PATTERNS = (
    r"\bout of (?:the )?office\b", r"\bautomatic reply\b", r"\bauto[- ]?reply\b",
    r"\bon (?:annual |parental |sick )?leave\b", r"\bon holiday\b",
    r"\bon vacation\b", r"\bmaternity leave\b", r"\bpaternity leave\b",
    r"\bi am away\b", r"\bcurrently away\b", r"\breturning on\b",
    r"\bback in the office\b", r"\blimited access to email\b",
)
# Somebody who has named a later time. Distinct from a refusal: they have
# said when, and that is a date worth keeping rather than a door closing.
#
# Tested *after* NEGATIVE on purpose. "No thanks, maybe try us in Q1" is a
# refusal with a politeness on the end, and reading it as a future
# appointment would put a follow-up in front of somebody who said no.
NOT_NOW_PATTERNS = (
    r"\bnot (?:right )?now\b", r"\bnot at the (?:moment|minute)\b",
    r"\btry (?:me|us) (?:again )?(?:in|next|after|around)\b",
    r"\breach (?:out|back) (?:to (?:me|us) )?(?:again )?(?:in|next|after)\b",
    r"\b(?:circle|check|come|get) back (?:to (?:me|us) )?(?:in|next|after|around)\b",
    r"\bping (?:me|us)\b", r"\bfollow up (?:in|next|after)\b",
    r"\brevisit (?:this )?(?:in|next|after)\b",
    r"\b(?:bad|wrong) timing\b", r"\btoo early\b",
    r"\bnext (?:quarter|year|month)\b",
    r"\bafter (?:the )?(?:new year|summer|holidays)\b",
)

NEGATIVE_PATTERNS = (
    r"\bnot interested\b", r"\bno thanks?\b", r"\bno thank you\b",
    r"\bwe(?:'re| are) (?:all )?(?:set|sorted|covered)\b",
    r"\bplease stop\b", r"\bnot a (?:good )?fit\b", r"\bpass\b",
    r"\bwe already (?:have|use)\b", r"\bhappy with (?:our|the) current\b",
)
# Handing somebody on.
#
# A cue on its own is not enough, and these were briefly allowed to be. "I
# need to talk to my boss first" is a delay, "reach out to me next quarter"
# is a date, and "that would be great" is somebody agreeing - all three
# match a hand-off phrase and none of them hands anybody on. So a cue only
# makes this a referral when the sentence also points at somebody: see
# `_points_at_somebody`.
REFERRAL_PATTERNS = (
    r"\b(?:talk|speak) to \b", r"\breach out to \b",
    r"\b(?:right|best|correct) person is\b",
    r"\b(?:forward|passing|passed) (?:this |it )?(?:on )?to\b",
    r"\bcopying in\b", r"\bcc(?:'?ing)? (?:in )?\b",
    # "Please contact Sam." A bare "contact" would also match "we contact
    # Acme quarterly", which is a sentence about a supplier.
    r"\b(?:please|instead,?) (?:contact|email|ask|try|speak to|talk to)\b",
    r"\b(?:you|you'?d) (?:should|want|need) (?:to )?(?:talk|speak|contact|email)\b",
)

NOT_RELEVANT_PATTERNS = (
    r"\bwrong person\b", r"\bnot (?:the|my) (?:right )?(?:person|department)\b",
    r"\bno longer (?:with|at)\b", r"\bhas left the (?:company|business)\b",
    r"\bi don'?t handle\b", r"\bnot my (?:area|remit)\b",
    r"\btry (?:contacting|reaching)\b",
)
POSITIVE_PATTERNS = (
    r"\binterested\b", r"\bsounds (?:good|interesting|great)\b",
    r"\bhappy to (?:chat|talk|speak|meet)\b", r"\blet'?s (?:chat|talk|speak)\b",
    r"\bbook (?:a|some) time\b", r"\bset up a (?:call|meeting)\b",
    r"\bkeen to\b", r"\bwould like to (?:know|hear) more\b",
    r"\btell me more\b", r"\bsend (?:me )?(?:over |through )?(?:some )?(?:more )?(?:info|details)\b",
    r"\bwhat does it cost\b", r"\bhow much (?:is|does)\b", r"\bpricing\b",
    r"\bcalendar\b", r"\bavailability\b", r"\bnext week works\b",
)

RULES = (
    (ACCOUNT_DNC, ACCOUNT_DNC_PATTERNS, 0.95),
    (UNSUBSCRIBE, UNSUBSCRIBE_PATTERNS, 0.95),
    (OUT_OF_OFFICE, OUT_OF_OFFICE_PATTERNS, 0.9),
    (NOT_RELEVANT, NOT_RELEVANT_PATTERNS, 0.8),
    (NEGATIVE, NEGATIVE_PATTERNS, 0.8),
    # Above POSITIVE for the same reason OUT_OF_OFFICE is: "sounds good,
    # try me in Q1" is a date, not a conversation to start today, and
    # reading it as warmth continues a cadence somebody asked to pause.
    # Whether that is the right trade is the same open question the
    # out-of-office ranking raises - see PRODUCT-GAPS 15b, which now covers
    # both rather than two decisions that could drift apart.
    (NOT_NOW, NOT_NOW_PATTERNS, 0.8),
    (POSITIVE, POSITIVE_PATTERNS, 0.75),
    # Last, and that is the whole design of it. `reply.on_referral` holds
    # the replier where `on_negative` and `on_wrong_person` stop them, so a
    # referral winning over either of those would leave somebody who
    # refused merely paused - a classification softening a stop, which is
    # the error this module is built to avoid. "Not interested, try Acme"
    # is a refusal; "sounds good, but talk to Sarah" is a positive.
    #
    # Nothing is lost by ranking it here, because the *mention* is recorded
    # from the evidence rather than from the winning category - see
    # `mentions_referral` and `apply`. The category decides what happens to
    # a cadence; the mention is a note for a person, and a reply can be one
    # thing and carry the other.
    (REFERRAL, REFERRAL_PATTERNS, 0.8),
)


def normalise(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _hits(text, patterns):
    found = []
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            found.append(match.group(0).strip().lower())
    return found


def _points_at_somebody(body):
    """Whether a hand-off phrase actually names anybody.

    A referral is two things - a cue and a person - and the cue alone is
    the half that produces false positives. `referral.evidence` already
    reads the second half, and reusing it means the classifier and the
    resolver cannot disagree about what a sentence said.

    Nothing here identifies anybody. A capitalised word after a cue is
    evidence that a name was used; `referral.resolve` is still the only
    thing allowed to say who that is.
    """
    from . import referral

    found = referral.evidence(body)
    return bool(found["names"] or found["emails"] or found["profiles"])


def mentions_referral(text):
    """Whether this reply hands somebody on, whatever it is classified as.

    A hand-off phrase *and* somebody it points at. Both, or neither: the
    cue alone matches sentences that hand nobody on, and an address alone
    matches every quoted thread footer in the corpus.

    Deliberately not the same question as `classification == REFERRAL`. A
    refusal that names a colleague is a refusal - it has to be, or the
    refusal would be downgraded to a hold - and it still names a colleague.
    """
    body = normalise(text)
    return bool(_hits(body, REFERRAL_PATTERNS)) and _points_at_somebody(body)


def classify_rules(text):
    """The deterministic pass. Returns a verdict or None if nothing matched."""
    body = normalise(text)
    if not body:
        return {"classification": UNKNOWN, "confidence": 0.0,
                "reason": "empty reply", "evidence": [],
                "classifier": VERSION}
    for category, patterns, confidence in RULES:
        hits = _hits(body, patterns)
        if category == REFERRAL and hits and not _points_at_somebody(body):
            continue                  # a hand-off phrase pointing at nobody
        if hits:
            return {"classification": category, "confidence": confidence,
                    "reason": f"matched {len(hits)} {category} phrase(s)",
                    "evidence": hits[:4], "classifier": VERSION}
    return None


def _excerpt(text, limit=200):
    body = normalise(text)
    return body if len(body) <= limit else body[:limit - 1] + "…"


def classify(text, model=None, threshold=CONFIDENCE_THRESHOLD):
    """Classify one reply. Rules first, a model only for what they cannot call.

    `model` is any callable taking the text and returning a dict with at least
    `classification`; anything it raises, and anything it returns that this
    module does not recognise, becomes `unknown`. It is never called in tests
    and never called for a message the rules already settled.
    """
    verdict = classify_rules(text)
    if verdict is None and model is not None:
        try:
            answer = model(normalise(text)) or {}
            category = str(answer.get("classification") or "").lower()
            if category in CATEGORIES:
                verdict = {
                    "classification": category,
                    "confidence": float(answer.get("confidence") or 0.0),
                    "reason": answer.get("reason") or "model",
                    "evidence": list(answer.get("evidence") or [])[:4],
                    "classifier": str(answer.get("classifier") or "model"),
                }
        except Exception as e:                       # a model is never trusted
            verdict = {"classification": UNKNOWN, "confidence": 0.0,
                       "reason": f"classifier failed: {type(e).__name__}",
                       "evidence": [], "classifier": VERSION}

    if verdict is None:
        verdict = {"classification": NEUTRAL, "confidence": 0.5,
                   "reason": "no rule matched and no classifier was available",
                   "evidence": [], "classifier": VERSION}

    # Below the bar, nobody is woken up and a human decides.
    if verdict["classification"] in ALERTING and verdict["confidence"] < threshold:
        verdict = {**verdict, "classification": UNKNOWN,
                   "reason": (f"{verdict['classification']} below the "
                              f"{threshold} threshold: manual review"),
                   "needs_review": True}
    verdict["excerpt"] = _excerpt(text)
    return verdict


def is_positive(verdict):
    return (verdict or {}).get("classification") == POSITIVE


def apply(rec, contact_key, text, at=None, model=None, channel=None,
          provider=None, provider_event_id=None,
          threshold=CONFIDENCE_THRESHOLD, automated=None):
    """Classify a reply, record it, and apply the policy it now resolves to.

    Never resumes anything. `events.apply` already held the account when the
    reply arrived unclassified; this may add to that state and may never
    subtract from it. `accountpolicy.apply_reply` only ever writes state that
    is absent, so a classification cannot lift a hold, clear a suppression,
    or reopen an account - whatever it says.

    That asymmetry is the safety property. A classifier that could unpause
    would make "not interested, we already bought" a way to resume outreach.
    """
    from . import accountpolicy, events, ooo, referral, store

    verdict = classify(text, model=model, threshold=threshold)
    # The policy outcome is recorded beside the classifier's own word.
    # They are two vocabularies - `out_of_office` is something a
    # classifier says and not something a policy has - and anything that
    # translated one into the other on the way *back* out read an
    # autoresponder as unclassified. Written once, here, where the
    # translation is already being done.
    outcome = accountpolicy.CLASSIFIER_OUTCOME.get(
        verdict["classification"], accountpolicy.UNKNOWN)
    entry = events.record(
        rec, events.REPLY_CLASSIFIED, contact_key=contact_key, channel=channel,
        at=at, provider=provider,
        provider_event_id=(f"{provider_event_id}:classified"
                           if provider_event_id else None),
        classification=verdict["classification"],
        outcome=outcome,
        confidence=verdict.get("confidence"),
        classifier=verdict.get("classifier"),
        reason=verdict.get("reason"))
    store.log(rec, "reply", f"classified {verdict['classification']}",
              contact=contact_key)

    # An out-of-office carries two facts the category cannot: whether a
    # person or a mail system wrote it, and when they said they are back.
    # Both are recorded as evidence here and acted on by nobody - what to do
    # about a return date is account policy's question, and this build has
    # no follow-up scheduler to answer it yet. Recording it now is what makes
    # that answerable later without re-reading messages that are gone.
    #
    # `automated` comes from the provider where the provider has an opinion.
    # None means it did not say, which is not the same as "no".
    if verdict["classification"] == OUT_OF_OFFICE:
        reading = ooo.read(text, at, automated=automated)
        events.record(
            rec, events.OUT_OF_OFFICE_RECORDED, contact_key=contact_key,
            channel=channel, at=at, provider=provider,
            provider_event_id=(f"{provider_event_id}:ooo"
                               if provider_event_id else None),
            absence_kind=reading["absence"]["kind"],
            automated_source=reading["absence"]["automated_source"],
            return_date=reading["return"]["return_date"],
            return_status=reading["return"]["status"],
            timezone_known=reading["return"]["timezone_known"],
            reason=reading["return"]["reason"],
            parser=reading["return"]["parser"])

    # "Try me in November" is not an absence - nobody is away - but it is a
    # date somebody gave for when to come back, and it is worth exactly as
    # much as a return date. Same grammar, different cue words; the reading
    # is recorded and acted on by nobody, for the same reason.
    if verdict["classification"] == NOT_NOW:
        when = ooo.return_date(text, at, cue=ooo.NOT_NOW_CUE)
        events.record(
            rec, events.NOT_NOW_RECORDED, contact_key=contact_key,
            channel=channel, at=at, provider=provider,
            provider_event_id=(f"{provider_event_id}:notnow"
                               if provider_event_id else None),
            return_date=when["return_date"],
            return_status=when["status"],
            reason=when["reason"],
            parser=when["parser"])

    # Somebody pointed at somebody else. What is recorded is the mention
    # and what could be proved about it - never an edge, and never a
    # contact. `events.REFERRAL_RECORDED` stays what it has always been: an
    # introduction between two people we already hold, written by a person.
    #
    # Recorded on the evidence, not on the winning category, because a
    # referral is ranked below every reading that stops a cadence and would
    # otherwise be lost every time somebody refuses politely and hands us
    # on in the same sentence.
    #
    # Except for a removal request. "Remove our company - talk to Sarah" is
    # a company-wide stop, and a queue item naming a colleague inside one
    # is the single worst thing this could produce.
    if (verdict["classification"] not in (UNSUBSCRIBE, ACCOUNT_DNC)
            and mentions_referral(text)):
        pointed = referral.read(rec, text, referrer=contact_key)
        events.record(
            rec, events.REFERRAL_MENTIONED, contact_key=contact_key,
            channel=channel, at=at, provider=provider,
            provider_event_id=(f"{provider_event_id}:referral"
                               if provider_event_id else None),
            referral_status=pointed["status"],
            referred_contact=pointed["contact"],
            named=", ".join(pointed["evidence"]["names"]) or None,
            # The identifiers themselves, not a count of them. A person
            # deciding whether to add the referred contact needs the address
            # in front of them, and the reply it came from is not stored -
            # so a count would leave the decision unmakeable. Already
            # normalised and already bounded by `referral.evidence`, and no
            # more than any imported lead carries.
            emails=list(pointed["evidence"]["emails"]),
            profiles=list(pointed["evidence"]["profiles"]),
            needs_a_person=pointed["needs_a_person"],
            reason=pointed["why"])

    # Business state first, notification second - and the state moves here,
    # before anything is announced, so a Slack failure cannot leave a
    # classified reply that changed nothing.
    effect = accountpolicy.apply_reply(rec, contact_key, outcome,
                                       at=at, channel=channel,
                                       workspace=rec.get("client"))

    notification = None
    if is_positive(verdict):
        events.record(rec, events.POSITIVE_REPLY_DETECTED,
                      contact_key=contact_key, channel=channel, at=at,
                      provider=provider,
                      provider_event_id=(f"{provider_event_id}:positive"
                                         if provider_event_id else None),
                      confidence=verdict.get("confidence"))
        # Last, and deliberately last. The company was paused by
        # `events.apply` before this function ran, the classification is
        # recorded above, and only now is anybody told. `notify.positive_reply`
        # cannot raise - see its docstring - so a Slack problem cannot unwind
        # any of it. A notification layer that runs first is a notification
        # layer that can lose a pause.
        notification = _announce(rec, contact_key, verdict, channel, provider,
                                provider_event_id, at, effect)
    return {"verdict": verdict, "event": entry,
            "paused": bool(rec.get("paused")),
            "effect": effect,
            "notification": notification}


def _announce(rec, contact_key, verdict, channel, provider, provider_event_id,
              at, effect=None):
    """Route the positive reply to this workspace's own Slack channel.

    The workspace is resolved from the record's client, and only when exactly
    one workspace claims that client. A record carries a client rather than a
    workspace, and treating the two as the same string happens to be right in
    every current deployment - which is exactly why it is worth not relying
    on. If the resolution is ambiguous the reply is announced nowhere.

    Returns the notification row, or None if there was nothing to route to.
    Either way the caller's business state is already correct: the company is
    paused and the classification is recorded before this runs.
    """
    from . import notify

    workspace = notify.workspace_for_client(rec.get("client"))
    if not workspace:
        return None
    campaign = _campaign_for(rec)
    return notify.positive_reply(
        rec, contact_key, workspace, campaign=campaign,
        excerpt=verdict.get("excerpt") or verdict.get("text"),
        channel=channel, provider=provider,
        provider_event_id=provider_event_id,
        # What the policy already did, so the alert says whether the rest
        # of the account is still being written to. Passed rather than
        # recomputed: this is the same `effect` the caller applied, and a
        # second derivation could disagree with what actually happened.
        effect=effect)


def _campaign_for(rec):
    """The campaign this record belongs to, or None.

    Read rather than guessed: a record with no campaign produces a
    notification with no campaign name, which is a smaller problem than one
    naming the wrong campaign.
    """
    try:
        from . import campaigns as campaign_store

        for campaign in campaign_store.load():
            if (campaign.get("client") == rec.get("client")
                    and rec.get("id") in (campaign.get("record_ids") or [])):
                return campaign
    except Exception:                                       # noqa: BLE001
        return None
    return None
