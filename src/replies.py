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

VERSION = "rules-2"

POSITIVE = "positive"
# TASK-020: should `positive` split into `positive` and `meeting`? The
# operator's hierarchy names them separately:
#
#     MEETING / QUALIFIED OPPORTUNITY
#     POSITIVE REPLY
#     MEANINGFUL REPLY
#
# Decision: no split at the classifier level. A meeting is determined by
# an action (calendar link accepted, time agreed, meeting scheduled), not
# by words alone. "Let's talk Thursday" is a positive reply until a
# calendar event exists; "Sounds interesting" is positive but not a
# meeting. The classifier can flag language that suggests a meeting, but
# confirming one requires observing that a calendar event was created or
# a time was agreed - a downstream signal, not a classification. Splitting
# here would require the classifier to predict future actions, which is
# not what rules do. The Slack alert already offers MARK_MEETING as an
# action, which is where the distinction belongs: in a person's decision,
# not in a pattern match.
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
    # TASK-020: common phrasings from the unmatched 35%. Every one of these
    # is a removal request in words, and the estate has no unsubscribe link
    # so opt-out arrives only as a reply somebody has to classify.
    r"\bstop (?:sending|writing)\b",
    r"\bno more (?:emails|messages|mail)\b",
    r"\b(?:remove|delete) me from (?:your|this|the) (?:list|database|mailing)\b",
    r"\bplease (?:do not|don'?t) (?:send|write) (?:me |any )?(?:more |any )?(?:emails?|messages?|mail)\b",
    r"\b(?:do not|don'?t) (?:send|write) me (?:any )?(?:more |any )?(?:emails?|messages?|mail)\b",
    # TASK-035: standalone "stop" - the one-word unsubscribe. 15+ replies
    # across the email corpus that are just "Stop" or "stop" with nothing
    # else. The existing patterns require "stop" to be followed by a
    # gerund ("stop emailing") or preceded by "please" ("please stop");
    # the bare word was not caught. Gated on NOT being followed by words
    # that change the meaning: "stop by" is a visit, "stop the" is about
    # an object.
    r"\bstop\b(?! (?:by|the|it|this|that|your?|my|our|a |an ))",
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
    # TASK-020: delay phrasings that do not refuse but do not commit.
    r"\bmaybe (?:later|sometime|another time|in the future)\b",
    r"\bnot at this time\b",
    r"\b(?:get|reach) back to (?:me|us) (?:sometime|later|when)\b",
    r"\b(?:shelve|park) (?:this|it) (?:for )?(?:now|later)\b",
)

NEGATIVE_PATTERNS = (
    r"\bnot interested\b", r"\bno thanks?\b", r"\bno thank you\b",
    r"\bwe(?:'re| are) (?:all )?(?:set|sorted|covered)\b",
    r"\bplease stop\b", r"\bnot a (?:good )?fit\b", r"\bpass\b",
    r"\bwe already (?:have|use)\b", r"\bhappy with (?:our|the) current\b",
    # TASK-020: short refusals common on both email and LinkedIn.
    r"\bnot for me\b", r"\bno need\b", r"\bwe(?:'re| are) good\b",
    r"\b(?:don'?t|do not) need (?:this|that|your)\b",
    r"\bnot (?:looking|shopping) (?:for|at) (?:this|that|a)\b",
    r"\b(?:not |un)(?:likely|likely) to (?:be|work|help)\b",
    r"\bno (?:interest|need) (?:at this time|right now|currently|for now)\b",
    # TASK-035: grouped from the unmatched 53%. "Not a priority" is a
    # refusal, not a delay - the sender is saying this does not rank high
    # enough to act on, not naming a later time. ~15 replies across both
    # corpora. "Not interesting for" is the polite-cousin of "not
    # interested" - 10+ replies that say "not interesting for us" and
    # slipped through because the existing pattern matches "not interested"
    # but not "not interesting." The "for" gate keeps it away from the
    # positive "sounds interesting" group. "No longer interested" catches
    # the tense shift: "we are no longer interested" did not match "not
    # interested." ~5 replies. "Not for us" is the plural of the existing
    # "not for me" - 5+ replies, especially LinkedIn.
    r"\bnot (?:a |the )?priority\b",
    r"\bnot interesting for\b",
    r"\bno longer interested\b",
    r"\bnot for us\b",
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
    # TASK-020: "not relevant" phrasings that name no one.
    r"\bnot relevant (?:for|to|at)\b",
    r"\b(?:doesn'?t|does not|won'?t) (?:apply|work|help) (?:for |to |us)\b",
    r"\bnot (?:something|anything) (?:we|I) (?:need|use|want)\b",
    # TASK-035: the first-person variant of "wrong person." The existing
    # pattern catches "not the right person" but misses "not be the right
    # person" - common when somebody says "I wouldn't be the right person"
    # or "I may not be the right person." The referral guard in
    # `classify_rules` still requires a named person for REFERRAL; this
    # catches the same phrase when it points at nobody. ~5 replies.
    r"\bnot (?:be )?(?:the )?right person\b",
)
POSITIVE_PATTERNS = (
    r"\binterested\b", r"\bsounds (?:good|interesting|great)\b",
    r"\bhappy to (?:chat|talk|speak|meet)\b", r"\blet'?s (?:chat|talk|speak)\b",
    r"\bbook (?:a|some) time\b", r"\bset up a (?:call|meeting)\b",
    r"\bkeen to\b", r"\bwould like to (?:know|hear) more\b",
    r"\btell me more\b", r"\bsend (?:me )?(?:over |through )?(?:some )?(?:more )?(?:info|details)\b",
    r"\bwhat does it cost\b", r"\bhow much (?:is|does)\b", r"\bpricing\b",
    r"\bcalendar\b", r"\bavailability\b", r"\bnext week works\b",
    # TASK-020: short affirmative replies, especially LinkedIn where a
    # single clause is the norm. "Sure" and "yes" alone are risky - they
    # can acknowledge receipt without buying anything - so they are gated
    # on a companion phrase that carries intent.
    r"\b(?:yes|sure|absolutely|definitely),?\s+(?:let'?s|happy|glad|would love|available)\b",
    r"\blet'?s do (?:it|this)\b",
    r"\b(?:i'?m|i am) (?:interested|keen|up for it)\b",
    r"\b(?:that|this) (?:would be|sounds) (?:great|helpful|useful)\b",
    r"\bsend (?:me )?(?:a |over )?(?:demo|proposal|quote|estimate)\b",
    r"\bcan we (?:schedule|arrange|organise|set up)\b",
    # TASK-035: "I'd like to learn more" and close variants. Grouped from
    # ~20 replies across both corpora that express curiosity without
    # committing. The existing "would like to (know|hear) more" catches
    # the formal version; this catches the contracted one and adds
    # "learn" and "see" which the original missed. "Interesting" alone
    # is NOT here - it is too ambiguous between "sounds interesting"
    # (positive) and just acknowledging the word. ~20 replies.
    r"\bi'?d (?:like|love) to (?:know|hear|learn|see) more\b",
    # TASK-035: "send me a video" / "can you send a video" - a specific
    # information request that signals engagement. 4-5 replies. Added to
    # the existing send-me-X pattern rather than as a separate line.
    r"\bsend (?:me )?(?:a )?video\b",
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


# ---------------------------------------------------------------------------
# TASK-029: extracting the prospect's own words from a raw email body.
#
# 85% of email replies carry the quoted original message below the reply.
# The classifier was handed the whole body, so it matched patterns in our
# own outreach copy and in the sender's signature block, and reported the
# result as the prospect's sentiment. 94 of 110 "referrals" were our own
# words quoted below the reply.
#
# The function below returns only what the prospect typed. It handles:
#   - top-posting (reply above the quote) - the 85% case;
#   - bottom-posting (reply below the quote) - detected, not assumed away;
#   - inline replies (text interleaved with quote lines) - text above the
#     first quote marker is kept, which is the recoverable portion;
#   - signature blocks after -- or ___ separators;
#   - bodies with no quote at all - returned byte for byte.
#
# This does NOT retune any classifier pattern. It fixes the input.
# ---------------------------------------------------------------------------

# Quote-header patterns: the line that introduces a quoted block.
_ON_WROTE = re.compile(
    r"^On .+\bwrote:", re.M)
_OUTLOOK_SEP = re.compile(
    r"^-{5,}Original Message-+$", re.M | re.I)

# Signature separators.
_SIG_DASH = re.compile(r"^--\s*$", re.M)
_SIG_UNDERSCORE = re.compile(r"^_{3,}\s*$", re.M)

# Greeting-only text: a line that is just a salutation or very short.
_GREETING = re.compile(
    r"^(?:hi|hey|hello|dear|good\s+(?:morning|afternoon|evening)|"
    r"thanks|thank\s+you|regards|cheers|greetings|"
    r"good\s+day|hiya|morning|afternoon)\b[.,:!]*\s*$",
    re.I)


def _find_quote_start(lines):
    """Line index where the quoted thread begins, or None.

    Checks three marker families in order of specificity:
    1. Outlook ``-----Original Message-----`` separator
    2. ``On <date> … wrote:`` header (Apple Mail, Gmail mobile)
    3. First line starting with ``>``

    Returns the index of the marker line itself. The caller decides
    whether to keep text above or below it.
    """
    joined = "\n".join(lines)
    outlook = _OUTLOOK_SEP.search(joined)
    if outlook:
        prefix = joined[:outlook.start()]
        return prefix.count("\n")

    on_match = _ON_WROTE.search(joined)
    if on_match:
        prefix = joined[:on_match.start()]
        return prefix.count("\n")

    for i, line in enumerate(lines):
        if line.startswith(">"):
            return i

    return None


def _strip_signature(text):
    """Remove the signature block from the end of a text.

    Returns ``(cleaned, was_stripped)``.  Recognises ``-- `` and ``___``
    separators.  A signature without a separator is left in place -
    guessing where a signature starts without a delimiter is where false
    positives live, and a missed signature is safer than a clipped reply.
    """
    for pattern in (_SIG_DASH, _SIG_UNDERSCORE):
        match = pattern.search(text)
        if match:
            before = text[:match.start()].rstrip()
            if before:
                return before, True
    return text, False


def _is_greeting_only(text):
    """Whether every non-empty line in *text* is just a salutation."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return True
    return all(_GREETING.match(l) or len(l) <= 2 for l in lines)


def extract_prospect_text(body):
    """The prospect's own words from a raw email body.

    85% of email replies carry the quoted original message below the
    reply.  Classifying the whole body matches patterns in our own
    outreach copy and reports the result as the prospect's sentiment.
    This function returns only what the prospect typed.

    Handles top-posting (reply above, quote below) as the default.
    Detects bottom-posting: if stripping leaves nothing or only a
    greeting, the reply is below the quote and is recovered.

    Returns a dict:

    ``text``
        The prospect's words, signatures removed.
    ``original_length``
        Character count of the raw input.
    ``stripped_length``
        Character count of ``text``.
    ``had_quote``
        Whether a quoted thread was found.
    ``had_signature``
        Whether a signature block was removed.
    ``method``
        How the reply was located: ``"top_post"``, ``"bottom_post"``,
        ``"no_quote"``, or ``"empty"``.
    ``original``
        The untouched input, so a caller that needs the whole body
        can still reach it.
    """
    if not body:
        return {"text": "", "original_length": 0, "stripped_length": 0,
                "had_quote": False, "had_signature": False,
                "method": "empty", "original": body or ""}

    lines = body.split("\n")
    quote_idx = _find_quote_start(lines)

    if quote_idx is None:
        cleaned, had_sig = _strip_signature(body)
        return {"text": cleaned, "original_length": len(body),
                "stripped_length": len(cleaned),
                "had_quote": False, "had_signature": had_sig,
                "method": "no_quote", "original": body}

    before = "\n".join(lines[:quote_idx]).strip()
    after_lines = []
    for i in range(quote_idx, len(lines)):
        if not lines[i].startswith(">"):
            after_lines.append(lines[i])
    after = "\n".join(after_lines).strip()

    if before and not _is_greeting_only(before):
        reply_text = before
        method = "top_post"
    elif after:
        reply_text = after
        method = "bottom_post"
    elif before:
        reply_text = before
        method = "top_post"
    else:
        return {"text": "", "original_length": len(body),
                "stripped_length": 0,
                "had_quote": True, "had_signature": False,
                "method": "empty", "original": body}

    cleaned, had_sig = _strip_signature(reply_text)
    if not cleaned.strip():
        cleaned = reply_text
        had_sig = False

    return {"text": cleaned, "original_length": len(body),
            "stripped_length": len(cleaned),
            "had_quote": True, "had_signature": had_sig,
            "method": method, "original": body}


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

    TASK-029 rework: the prospect's own words are extracted before
    classification. 85% of email replies carry the quoted original below
    the reply, and classifying the whole body matched patterns in our own
    outreach copy. The verdict carries ``extract_method`` and
    ``extract_stripped_length`` so a caller can tell what was judged.
    """
    extracted = extract_prospect_text(text)
    cleaned = extracted["text"]

    verdict = classify_rules(cleaned)
    if verdict is None and model is not None:
        try:
            answer = model(normalise(cleaned)) or {}
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
        # "No rule matched" is UNKNOWN, not NEUTRAL. NEUTRAL means "we read
        # this and it is genuinely lukewarm" - a measurement. UNKNOWN means
        # "we could not read this" - a gap. Reporting the gap as a measurement
        # is how 35% of replies on the live estate became invisible: they
        # showed up as a category in reports rather than as the missing
        # coverage they actually are. TASK-020, measured 2026-09-14.
        verdict = {"classification": UNKNOWN, "confidence": 0.0,
                   "reason": "no rule matched and no classifier was available",
                   "evidence": [], "classifier": VERSION}

    # Below the bar, nobody is woken up and a human decides.
    if verdict["classification"] in ALERTING and verdict["confidence"] < threshold:
        verdict = {**verdict, "classification": UNKNOWN,
                   "reason": (f"{verdict['classification']} below the "
                              f"{threshold} threshold: manual review"),
                   "needs_review": True}
    verdict["extract_method"] = extracted["method"]
    verdict["extract_stripped_length"] = extracted["stripped_length"]
    verdict["excerpt"] = _excerpt(cleaned)
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
    # TASK-020: the provider's own automated flag travels with the verdict.
    # A provider-flagged auto-reply is not a reply from a person. It must
    # not count toward a reply rate and must not suppress outreach the way
    # a human reply does - though an out-of-office should still defer the
    # next touch. The flag is recorded here so every downstream consumer
    # can see it without re-reading the provider row.
    verdict["is_automated"] = automated is True
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
    # TASK-029 rework: check referral cues on the prospect's own words,
    # not the raw body. A referral phrase in the quoted thread is our own
    # outreach copy, not the prospect handing somebody on.
    _cleaned = extract_prospect_text(text)["text"]
    if (verdict["classification"] not in (UNSUBSCRIBE, ACCOUNT_DNC)
            and mentions_referral(_cleaned)):
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
    #
    # TASK-020: a provider-flagged automated reply is not a person. It must
    # not suppress outreach the way a human reply does. An out-of-office is
    # the exception: it still defers the next touch, which is the policy
    # outcome NOT_NOW and is what the operator wants. Every other automated
    # classification - including one the rules could not read - skips the
    # policy application entirely. The classification event is still
    # recorded above for reporting; what changes is that no HOLD or STOP
    # lands on the account because a mail server wrote back.
    if automated is True and verdict["classification"] != OUT_OF_OFFICE:
        effect = None
    else:
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
