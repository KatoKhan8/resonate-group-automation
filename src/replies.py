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

Classification never resumes anything. The pause is conditional on the
classification: a pure out-of-office skips the pause, everything else -
including `unknown` - pauses. The pause happens in `replies.apply` through
`accountpolicy.apply_reply`, after classification and before notification.
No verdict here can lift a pause once applied. The worst this can do is
fail to raise an alert, which is why `unknown` is safe and why a model
failure degrades to it rather than to `neutral`.

The model adapter is a seam, not a dependency: deterministic rules run first
and decide the clear cases for free. Tests never reach a model.
"""
import re

VERSION = "rules-3"

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
# TASK-067: the analysis layer splits further (interested, meeting_intent,
# objection) for the learning dataset. Those are analysis categories, not
# policy categories - they map to existing outcomes in accountpolicy.
NEUTRAL = "neutral"
NEGATIVE = "negative"
UNSUBSCRIBE = "unsubscribe"
ACCOUNT_DNC = "account_do_not_contact"
OUT_OF_OFFICE = "out_of_office"
NOT_NOW = "not_now"
REFERRAL = "referral"
NOT_RELEVANT = "not_relevant"
UNKNOWN = "unknown"

# TASK-074: finer-grained analysis categories for the learning dataset.
# These sub-classify replies that production rules leave as UNKNOWN so
# cadence and copy analysis can distinguish curiosity from a concrete
# meeting step from a stated constraint.  They are analysis labels, not
# policy outcomes: every one maps to UNKNOWN in
# `accountpolicy.CLASSIFIER_OUTCOME`, so an analysis category can never
# widen what automation is allowed to do.
INTERESTED = "interested"
MEETING_INTENT = "meeting_intent"
OBJECTION = "objection"
#: Added 2026-09-23: the reply-engine brief named both as answerable
#: classes and neither existed, so the engine refused them as UNAVAILABLE.
QUESTION = "question"
SEND_INFO = "send_info"

# OPERATOR DECISION, Zvonimir Bešlić, 2026-09-22.
#
#   "add class automated (out-of-office, auto-acknowledgement, ticketing,
#    assistant or EA redirect, 'thanks for your email' with no content).
#    Automated is never positive_reply. Assistant redirects get their own
#    class assistant_redirect: logged as a new contact candidate at that
#    account, routed to internal review only. Positive requires intent: a
#    question, interest, a meeting ask, a request for more."
#
# `AUTOMATED` covers the machine-written acknowledgements that carry no
# person: ticketing systems, receipt confirmations, "thank you for your
# email" with nothing after it.
#
# `OUT_OF_OFFICE` KEEPS ITS OWN LABEL and is automated by the predicate
# below rather than by being folded into this one. It is named directly in
# `events`, in `inbound`, and in `accountpolicy.CLASSIFIER_OUTCOME`, and a
# pure out-of-office is the one reply shape that SKIPS the cadence pause -
# see this module's own docstring. Collapsing the label would change which
# replies pause a cadence, which is a sending-behaviour change nobody asked
# for. The operator's rule is enforced by `is_automated`, which is what the
# never-positive guarantee and every automated-vs-human count read.
AUTOMATED = "automated"
ASSISTANT_REDIRECT = "assistant_redirect"

CATEGORIES = (POSITIVE, NEUTRAL, NEGATIVE, UNSUBSCRIBE, ACCOUNT_DNC,
              OUT_OF_OFFICE, NOT_NOW, REFERRAL, NOT_RELEVANT,
              UNKNOWN, INTERESTED, MEETING_INTENT, OBJECTION,
              QUESTION, SEND_INFO,
              AUTOMATED, ASSISTANT_REDIRECT)

#: Every classification that means "no human chose to write this to us",
#: which is the operator's `automated` umbrella. ONE definition, because
#: the 18:00 summary, the client-facing counts and the never-positive
#: guarantee all have to agree on what automated means.
AUTOMATED_CATEGORIES = (OUT_OF_OFFICE, AUTOMATED, ASSISTANT_REDIRECT)


def is_automated(classification):
    """True when a classification is automated under the operator's rule.

    An assistant redirect IS automated in the sense that matters here -
    nobody at the account has expressed interest - and it is separately
    classified because it carries a contact candidate worth keeping.
    """
    return str(classification or "") in AUTOMATED_CATEGORIES


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
    # TASK-067: "Stop please" and "please stop" were both seen. The existing
    # pattern only had "please stop"; the reversed order was missed.
    r"\bstop please\b",
    # TASK-035: standalone "stop" - the one-word unsubscribe. 15+ replies
    # across the email corpus that are just "Stop" or "stop" with nothing
    # else. The existing patterns require "stop" to be followed by a
    # gerund ("stop emailing") or preceded by "please" ("please stop");
    # the bare word was not caught. Gated on NOT being followed by words
    # that change the meaning: "stop by" is a visit, "stop the" is about
    # an object.
    # A BARE "stop" IS NOT AN UNSUBSCRIBE, and this used to be one - with a
    # small lookahead that excluded "stop by/the/it" and nothing else. It
    # matched "please stop asking", which `NEGATIVE_PATTERNS` names
    # explicitly, and unsubscribe outranks negative in `RULES` - so a negative
    # reply was escalated into a removal request.
    #
    # That is over-suppression, which is the safe direction and still wrong:
    # an unsubscribe suppresses globally and for good, a negative stops an
    # account. Recording somebody as having asked for removal when they asked
    # a question sharply is asserting more than we know, and this system's
    # whole discipline is not doing that.
    #
    # The specific forms - stop emailing, stop contacting, stop messaging,
    # stop sending, stop writing - are already patterns above and catch the
    # real cases.
    #
    # EXCEPT ONE, WHICH IS REAL: a reply whose ENTIRE content is "stop".
    # Somebody answering a sequence with the single word is asking to be
    # removed and nothing else, and the estate contains them. Anchored to the
    # whole message so it cannot fire inside a sentence - which is exactly
    # what the bare pattern got wrong.
    r"^stop[\s.!]*$",
)
OUT_OF_OFFICE_PATTERNS = (
    r"\bout of (?:the )?office\b", r"\bautomatic reply\b", r"\bauto[- ]?reply\b",
    r"\bon (?:annual |parental |sick )?leave\b", r"\bon holiday\b",
    r"\bon vacation\b", r"\bmaternity leave\b", r"\bpaternity leave\b",
    r"\bi am away\b", r"\bcurrently away\b", r"\breturning on\b",
    r"\bback in the office\b", r"\blimited access to email\b",
    # TASK-066: "sabbatical" was not in the leave alternation, so "on a
    # sabbatical leave" was missed. The article "a" before the leave type
    # also prevented matching.
    r"\bon (?:a |an )?(?:sabbatical|extended|unpaid)\s+leave\b",
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
    # TASK-066: "not for now" is a deferral, not a refusal - the sender
    # named "now" as the problem, not the topic. Common on LinkedIn where
    # a single clause carries the whole reply.
    r"\bnot for now\b",
    # TASK-067: delay phrasings from the live LinkedIn estate.
    r"\bon (?:a )?pause\b",
    r"\bnot (?:there|ready) yet\b",
    r"\boverworked\b",
    r"\b(?:bit|little) (?:overworked|busy|swamped) (?:at )?(?:the )?moment\b",
    r"\bnot with this (?:project|role) anymore\b",
)

NEGATIVE_PATTERNS = (
    r"\bnot interested\b", r"\bno thanks?\b", r"\bno,? thank you\b",
    r"\bwe(?:'re| are) (?:all )?(?:set|sorted|covered)\b",
    r"\bplease stop\b", r"\bnot a (?:good )?fit\b",
    # "pass" is a decline ONLY when nothing is being passed ALONG.
    #
    # 2026-09-23: this was a bare `\bpass\b`, and it read "I'll pass this
    # along to him" - an assistant FORWARDING to the buyer - as a refusal at
    # 0.8. NEGATIVE outranks ASSISTANT_REDIRECT by design, because a refusal
    # written by an assistant stays a refusal - so the broader pattern won
    # and the redirect never got a chance to match.
    #
    # Word order carries the whole meaning, and the lookaheads follow it:
    #     "I'll pass this on"    -> forward, excluded here
    #     "I'll pass on this"    -> decline, still matches
    #     "I'll pass"            -> decline, still matches
    #     "we'll pass for now"   -> decline, still matches
    r"\bpass\b(?!\s+(?:this|it|that|these|them|the\s+\w+)\s+"
    r"(?:along|on|over|to)\b)(?!\s+along\b)",
    # "we already use X" and "happy with our current Y" moved to
    # OBJECTION_PATTERNS on 2026-09-23, on the operator's instruction. They
    # are a conversation, not a door closing. Paired with an explicit decline
    # ("we already use Harvest, no thanks") the decline still wins, because
    # NEGATIVE ranks above OBJECTION in RULES - which is the whole mechanism.
    r"\bhappy with (?:our|the) current (?:setup|process|way|arrangement)\b",
    # TASK-020: short refusals common on both email and LinkedIn.
    r"\bnot for me\b", r"\bno need\b", r"\bwe(?:'re| are) good\b",
    r"\b(?:don'?t|do not) need (?:this|that|your)\b",
    r"\bnot (?:looking|shopping) (?:for|at) (?:this|that|a)\b",
    r"\b(?:not |un)(?:likely|likely) to (?:be|work|help)\b",
    r"\bno (?:interest|need) (?:at this time|right now|currently|for now)\b",
    # TASK-067: standalone short refusals that were outright misses on
    # LinkedIn. Anchored to the whole message so they cannot fire inside
    # a sentence. "No" alone is a refusal; "No, but..." is not caught here
    # because the sentence continues and needs the full patterns.
    r"^no[.?!]*$",
    r"^nope[.?!]*$",
    r"^nah[.?!]*$",
    # TASK-067: first-person variants and misspellings from the live estate.
    r"\bi'?m (?:all )?set\b",
    r"\bnot interessed\b",
    r"\bno longer (?:active|operational|accepting)\b",
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
    # "not a priority" -> OBJECTION_PATTERNS, 2026-09-23. Same reasoning:
    # a priority can change, and "not a priority, remove me" still reads
    # unsubscribe because UNSUBSCRIBE ranks above both.
    r"\bnot interesting for\b",
    r"\bno longer interested\b",
    r"\bnot for us\b",
    # TASK-066: LinkedIn replies are short and drop qualifiers. The existing
    # "no (interest|need) (at this time|...)" required a qualifier that
    # LinkedIn senders omit. "No interest" bare and "no, thank you" with a
    # comma were both missed. 30 of 100 hand-labelled unknowns were clear
    # refusals that no pattern caught.
    r"\bno interest\b",
    # TASK-066: "no requirement" is the formal variant of "no need" - common
    # in enterprise replies where the sender uses professional language.
    r"\bno requirement\b",
    # TASK-066: LinkedIn-specific refusals measured across 3,869 unknowns.
    # "No interest" is the plain form - 27 replies said "no interest" or
    # "no interest at the moment" and the existing "not interested" did
    # not reach them. "At the moment" was missing from the qualifier list.
    r"\bno (?:interest|need) at the moment\b",
    # "Nope" is unambiguous - more so than bare "no", which can answer a
    # different question. 4+ replies.
    r"\bnope\b",
    # "Not at this stage" - variant of "not at this time". 6+ replies.
    r"\bnot at this stage\b",
    # "No budget" / "no funding" - a refusal grounded in resources.
    r"\bno (?:budget|funding)\b",
    # "Don't have a need" - the existing pattern requires "need this/that"
    # directly; "have a need" inserts a verb that broke the match.
    r"\b(?:don'?t|do not) have (?:a |any )?need\b",
    # "Not looking" without a following preposition - "we're not looking"
    # is a refusal even without "for this". 39 replies.
    r"\bnot (?:looking|seeking)\b",
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
    # TASK-066: "handled by X" / "managed by X" - a hand-off phrase that
    # the existing patterns missed. 5+ replies. Still requires
    # `_points_at_somebody` in `classify_rules` to avoid false positives
    # from sentences like "this is handled by our team" with no name.
    r"\b(?:handled|managed|covered) by\b",
)

NOT_RELEVANT_PATTERNS = (
    r"\bwrong person\b", r"\bnot (?:the|my) (?:right )?(?:person|department)\b",
    r"\bno longer (?:with|at)\b", r"\bhas left the (?:company|business)\b",
    r"\bi don'?t handle\b", r"\bnot my (?:area|remit|decision)\b",
    r"\btry (?:contacting|reaching)\b",
    # TASK-020: "not relevant" phrasings that name no one.
    # TASK-067: broadened to catch "not relevant" standalone or followed by
    # comma/period (not just prepositions). "Not relevant, thanks" was missed.
    r"\bnot relevant\b",
    r"\b(?:doesn'?t|does not|won'?t) (?:apply|work|help) (?:for |to |us)\b",
    r"\bnot (?:something|anything) (?:we|I) (?:need|use|want)\b",
    # TASK-035: the first-person variant of "wrong person." The existing
    # pattern catches "not the right person" but misses "not be the right
    # person" - common when somebody says "I wouldn't be the right person"
    # or "I may not be the right person." The referral guard in
    # `classify_rules` still requires a named person for REFERRAL; this
    # catches the same phrase when it points at nobody. ~5 replies.
    r"\bnot (?:be )?(?:the )?right person\b",
    # TASK-066: "I don't work at X" is a common LinkedIn not_relevant
    # signal - the person is at a different company than the one targeted.
    r"\bi (?:don'?t|do not) work (?:at|for)\b",
    r"\bnot in (?:that |this )?(?:field|area|department)\b",
    # TASK-066: LinkedIn "I left" / "no longer here" phrasings. 89 replies
    # across the unknown set said they had left the company or were no
    # longer in the role, and the existing patterns required "the company"
    # or "the business" after "left" - "left Protosell" did not match.
    # "No longer work/working" catches the verb form that "no longer with"
    # missed when a verb intervened.
    r"\bno longer (?:work|working)\b",
    r"\b(?:i'?m|i am) not (?:at|with) \S+ (?:anymore|any more)\b",
    r"\bnot (?:responsible|in charge) (?:for|of)\b",
)
# An assistant, EA or PA answering for somebody else. OPERATOR, 2026-09-22:
# its own class, logged as a new contact candidate at that account and
# routed to internal review only.
#
# Every pattern needs the ASSISTANT ROLE in it. "Please contact Sam" is a
# referral and stays one; it is only this when the writer says who they are.
# That is the difference between "somebody named a person" and "the person
# who manages the diary just introduced themselves", and only the second is
# a reliable new contact.
ASSISTANT_REDIRECT_PATTERNS = (
    r"\b(?:executive |personal |admin(?:istrative)? )?assistant to\b",
    r"\b(?:i'?m|i am|this is) [^.\n]{0,40}\b(?:executive |personal )?"
    r"assistant\b",
    r"\b(?:i'?m|i am|this is) [^.\n]{0,40}\b(?:ea|pa) to\b",
    r"\bon behalf of\b",
    r"\bi (?:look after|manage|handle|keep|run) [^.\n]{0,30}"
    r"(?:diary|calendar|schedule|inbox)\b",
    r"\b(?:i'?m|i am) (?:the )?(?:ea|pa|executive assistant|"
    r"personal assistant)\b",
    r"\bcopying (?:in )?[^.\n]{0,30}assistant\b",
    r"\bplease (?:go through|liaise with|coordinate with) me\b",
    # THE FORWARDING ASSISTANT. Added 2026-09-23 after measurement.
    #
    # Every pattern above requires the writer to IDENTIFY as an assistant
    # ("I'm the EA to..."). Most of them never do. They just forward - and
    # those replies were landing in three different wrong places:
    #
    #     "I'll pass this along to him."          -> negative   0.80
    #     "Forwarded to our CEO."                 -> unclassified
    #     "I've forwarded your email to our CEO,
    #      he'll be in touch if interested."      -> POSITIVE   0.75
    #
    # The third is the one that matters. POSITIVE fires the first-human-reply
    # client trigger, so a secretary forwarding an email would have announced
    # a buying signal to the client. ASSISTANT_REDIRECT is in
    # AUTOMATED_CATEGORIES, so `is_automated()` is true and that trigger
    # cannot fire from here - which is the operator's stated requirement.
    r"\b(?:i(?:'|’)?(?:ll|ve)|i (?:will|have)|we(?:'|’)?(?:ll|ve)"
    r"|we (?:will|have))\s+(?:just\s+)?(?:pass(?:ed)?|forward(?:ed)?|sen[dt])"
    r"\s+(?:this|it|that|these|your\s+\w+)\s+(?:along|on|over|to)\b",
    r"\bpass(?:ed|ing)?\s+(?:this|it|that|these|them)\s+(?:along|on|over|to)\b",
    r"\bforward(?:ed|ing)?\s+(?:this|it|that|your\s+\w+)\s+(?:along|on|over|to)\b",
    r"\bforwarded\s+to\b",
)

# Machine-written acknowledgements. Nobody chose to send these to us.
#
# The bare-thanks case is deliberately NOT here: "thanks for your email"
# is only automated when it carries nothing else, and "no content" is a
# property of the whole message rather than a phrase in it. It is handled
# in `classify_rules` by `_is_bare_acknowledgement`, which requires the
# phrase AND the absence of intent AND a short body - a human who writes
# "thanks for your email, what does it cost?" is not an autoresponder.
AUTOMATED_PATTERNS = (
    r"\bthis is an automated\b", r"\bautomated (?:response|reply|message)\b",
    r"\bdo not reply to this\b", r"\bplease do not reply\b",
    r"\bno[- ]?reply@\b",
    # Ticketing and case management.
    r"\b(?:ticket|case|request|enquiry|inquiry) (?:#|number|id|ref)\b",
    r"\b(?:ticket|case) #?\d+\b",
    r"\byour (?:ticket|case|request) has been (?:created|logged|received|"
    r"opened)\b",
    r"\bwe have (?:received|logged) your (?:email|message|request|enquiry)\b",
    r"\bwe'?ve (?:received|logged) your (?:email|message|request|enquiry)\b",
    r"\breference number\b",
    r"\bhas been (?:assigned|routed) to (?:a|our) (?:team|agent|advisor)\b",
    # Receipt confirmations with a promise and no person.
    r"\bthank you for contacting\b",
    r"\bthanks? for (?:getting in touch|reaching out)[^.\n]{0,20}"
    r"we(?:'| wi)ll (?:get back|be in touch|respond)\b",
    r"\bsomeone (?:from our team )?will (?:be in touch|get back to you)\b",
    r"\bwithin \d+ (?:business )?(?:hours|days)\b",
)

#: The bare acknowledgement, which is only automated when it says nothing
#: else. Paired with `_carries_intent` and a length ceiling in
#: `classify_rules`.
BARE_ACKNOWLEDGEMENT_PATTERNS = (
    r"\b(?:thank you|thanks|many thanks) (?:so much |very much )?"
    r"for (?:your|the) (?:email|e-mail|message|note|mail)\b",
    r"\b(?:thank you|thanks)[!.,]*\s*$",
    r"\breceived,? thank(?:s| you)\b",
    r"\bnoted,? thank(?:s| you)\b",
    r"\back(?:nowledged)?,? thank(?:s| you)\b",
)

#: How long a "thanks for your email" may be before it stops being bare.
#: A real person who thanks you and then writes three sentences has
#: written three sentences.
BARE_ACKNOWLEDGEMENT_MAX_CHARS = 160

# OPERATOR, 2026-09-22: "Positive requires intent: a question, interest, a
# meeting ask, a request for more."
#
# `POSITIVE_PATTERNS` below carries bare nouns - `pricing`, `calendar`,
# `availability` - which were added because they appear in warm replies.
# They also appear in signatures, in autoresponders and in sentences about
# somebody else's calendar. This is the gate: a POSITIVE match that carries
# no intent does NOT become positive, it becomes UNKNOWN and a person looks
# at it. That is the direction this module always fails in.
INTENT_PATTERNS = (
    r"\?",                                   # they asked us something
    r"\binterested\b", r"\bkeen\b",
    r"\bhappy to (?:chat|talk|speak|meet|connect)\b",
    r"\blet'?s (?:chat|talk|speak|do)\b",
    r"\bwould (?:like|love) to\b",
    r"\btell me more\b", r"\bmore (?:info|information|details)\b",
    r"\bsend (?:me|us|over|through)\b",
    r"\b(?:book|set up|schedule|arrange) (?:a|some)\b",
    r"\b(?:i'?m|i am|we'?re|we are) (?:in|up for it|game)\b",
    r"\b(?:call|meeting|demo|chat) (?:on|next|this|at)\b",
    r"\bworks for me\b", r"\bsounds (?:good|great|interesting)\b",
    r"\bwhen (?:are|can|would) you\b",
    r"\bwhat (?:does|is|are)\b", r"\bhow (?:much|many|does)\b",
)


def _carries_intent(body):
    """Did the writer ask, invite, or want something? See `INTENT_PATTERNS`."""
    return bool(_hits(body, INTENT_PATTERNS))


def _is_bare_acknowledgement(body):
    """"Thanks for your email" and nothing else."""
    if len(body) > BARE_ACKNOWLEDGEMENT_MAX_CHARS:
        return False
    if _carries_intent(body):
        return False
    return bool(_hits(body, BARE_ACKNOWLEDGEMENT_PATTERNS))


POSITIVE_PATTERNS = (
    r"\binterested\b", r"\bsounds (?:good|interesting|great)\b",
    r"\bhappy to (?:chat|talk|speak|meet|connect)\b",
    r"\blet'?s (?:chat|talk|speak)\b",
    r"\bbook (?:a|some) time\b", r"\bset up a (?:call|meeting)\b",
    r"\bkeen to\b", r"\bwould like to (?:know|hear) more\b",
    r"\btell me more\b",
    # TASK-066: the send-info pattern missed "information" (only matched
    # "info") and "send me any more info" (the "any" before "more" was not
    # in the expected position). LinkedIn replies use both "information"
    # and "info" interchangeably, and "any" is a common softener.
    r"\bsend (?:me )?(?:over |through )?(?:(?:some |any )?(?:more )?)?(?:info|information|details)\b",
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
    # TASK-066: LinkedIn short affirmatives that the TASK-020 companion
    # gate missed. "Yes please" is unambiguous enthusiasm - "please"
    # converts a bare "yes" from acknowledgment into a request. "Happy to
    # connect" is a willingness signal on the channel where the outreach
    # happened. "Pitch deck" is a specific material request.
    r"\byes please\b",
    r"\bsend (?:me )?(?:a )?(?:pitch deck|deck|one[- ]pager)\b",
    # TASK-067: short LinkedIn replies that were outright misses. "Show me"
    # is a clear request for more information - warmer than neutral.
    # Anchored variants so they do not fire inside longer sentences.
    r"^show me[.?!]*$",
    r"^i'?m interested[.?!]*$",
    r"^yes please[.?!]*$",
    r"^yes,? please[.?!]*$",
    r"^sure thing[.?!]*$",
    r"^sure[.?!]*$",
    # TASK-066: "send me the details" - the existing pattern's optional
    # chain did not include "the", so "send me the details" fell through.
    # 5+ replies. Kept separate from the existing pattern to avoid
    # restructuring a chain that already works for email.
    r"\bsend (?:me )?the (?:details|info)\b",
    # "Happy to learn/hear/know more" - expresses curiosity without
    # committing. Distinct from "happy to chat" (existing) which is about
    # a conversation; this is about the content. 3+ replies.
    r"\bhappy to (?:learn|hear|know) more\b",
)


#: The POSITIVE patterns that are BARE NOUNS, and the only ones the intent
#: gate applies to.
#:
#: These three were added because they appear in warm replies. They also
#: appear in email signatures, in autoresponders, and in sentences about
#: somebody else's diary - "I look after his calendar", which is the EA
#: reply this decision was written about. Every other positive pattern
#: already carries a verb somebody chose: `interested`, `send me`,
#: `let's talk`, `can we schedule`.
#:
#: So the gate is narrow on purpose. Applying it to the whole list dropped
#: "Yes please", "Show me" and "Sure, happy to discuss" to `unknown`, which
#: is the opposite of the fix: a false negative on a real buying signal
#: costs a client a meeting.
WEAK_POSITIVE_PATTERNS = (
    r"\bpricing\b", r"\bcalendar\b", r"\bavailability\b",
)

STRONG_POSITIVE_PATTERNS = tuple(
    p for p in POSITIVE_PATTERNS if p not in WEAK_POSITIVE_PATTERNS)


def _positive_carries_intent(body):
    """OPERATOR, 2026-09-22: "Positive requires intent."

    True when the reply carries a positive signal somebody chose to send -
    a strong pattern, or a weak one corroborated by intent elsewhere in the
    message. False when the only evidence is a bare `pricing`, `calendar`
    or `availability` sitting in a signature or an autoresponder.
    """
    if _hits(body, STRONG_POSITIVE_PATTERNS):
        return True
    return _carries_intent(body)


#: A real question about the product, the company or the claim. Answerable by
#: the reply engine. Added 2026-09-23: the brief named `question` as one of
#: six answerable classes and `CATEGORIES` did not contain it, so the engine
#: refused it as UNAVAILABLE rather than acting on a class it could not see.
QUESTION_PATTERNS = (
    r"\b(?:how|what|which|where|who|why|when) (?:do(?:es)?|is|are|can|could|"
    r"would|will|exactly)\b[^.?!]{0,80}\?",
    r"\bcan (?:you|it|this) (?:do|handle|support|manage|track|cope)\b",
    r"\bdoes (?:it|this|productive) (?:do|handle|support|work|integrate)\b",
    r"\bhow does (?:it|this|that) work\b",
    r"\bwhat (?:exactly )?(?:is|does) (?:it|this|productive)\b",
    r"\btell me more about\b",
    r"\bcurious (?:how|what|about)\b",
)

#: An explicit request to be SENT something. Distinct from a question: the
#: answer is an attachment or a link rather than a sentence, which is why the
#: engine routes them differently.
SEND_INFO_PATTERNS = (
    r"\b(?:send|share|forward|email) (?:me |us |over |through )?"
    r"(?:some |more |the |a |any )?(?:info|information|details|detail|deck|"
    r"one[- ]?pager|overview|brochure|case stud(?:y|ies)|material|materials|"
    r"documentation|docs)\b",
    r"\b(?:can|could) (?:you|we) (?:get|have|see|send) (?:me |us )?"
    r"(?:some |more |a )?(?:info|information|details|deck|overview)\b",
    r"\bmore (?:info|information|details)\b",
    r"\bsend (?:it |that )?(?:over|across|through|along)\b",
)

#: Moved out of NEGATIVE_PATTERNS 2026-09-23 on the operator's instruction:
#: "we already use X", "we have a tool for this" and "not a priority right
#: now" are OBJECTIONS, not declines. "We already use Harvest" is a
#: conversation; "We already use Harvest, no thanks" is a door closing, and
#: the second still reads NEGATIVE because NEGATIVE ranks above OBJECTION in
#: `RULES`. That position IS the rule "the decline patterns win only when
#: present" - it needs no extra logic.
OBJECTION_PATTERNS = (
    # budget and capacity objections
    r"\btoo (?:expensive|costly|pricey|cheap)\b",
    r"\b(?:no|not enough) budget\b",
    r"\b(?:no|not enough) (?:time|resources|bandwidth)\b",
    r"\b(?:too|too many|too few) (?:people|staff|team members)\b",
    r"\bour team is too (?:small|large)\b",
    r"\b(?:we|I) (?:do not|don'?t) have (?:the |a )?(?:budget|time|resources)\b",
    r"\bnot (?:in |within )?(?:our |the )?budget\b",
    r"\b(?:above|beyond|outside) (?:our |the )?budget\b",
    r"\bwe(?:'re| are) (?:too small|too big|not big enough)\b",
    # the soft objections moved out of NEGATIVE, 2026-09-23
    r"\bwe already (?:have|use|got)\b",
    r"\bhappy with (?:our|the|my) current\b",
    r"\bwe (?:have|use|run|are on) (?:a|another|an existing) (?:tool|system|"
    r"platform|solution|vendor|provider)\b",
    r"\b(?:we|I) (?:have|use) (?:something|a tool) for (?:this|that)\b",
    r"\bnot a priority (?:right now|at the moment|for us|this quarter)\b",
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
    # OPERATOR, 2026-09-22. BOTH SIT DIRECTLY ABOVE POSITIVE AND BELOW EVERY
    # REFUSAL, which is the whole of the placement decision.
    #
    # Above POSITIVE because that is the error being fixed: an EA writing
    # "happy to help, I look after his calendar" matched POSITIVE_PATTERNS
    # twice and was counted as interest from a person who has expressed
    # none.
    #
    # Below NOT_RELEVANT, NEGATIVE and NOT_NOW because those are stops and
    # deferrals, and a classification may never soften one. "Not interested
    # - I'm his assistant" is a refusal that happens to be written by an
    # assistant, and it stays a refusal. This is the same ordering argument
    # REFERRAL is given below.
    #
    # ASSISTANT_REDIRECT before AUTOMATED: an EA redirect is automated
    # under `is_automated`, and it is the more specific reading, so it must
    # not be swallowed by a generic acknowledgement phrase.
    (ASSISTANT_REDIRECT, ASSISTANT_REDIRECT_PATTERNS, 0.85),
    (AUTOMATED, AUTOMATED_PATTERNS, 0.85),
    (POSITIVE, POSITIVE_PATTERNS, 0.75),
    # SEND_INFO and QUESTION sit BELOW POSITIVE, and the choice was measured
    # rather than assumed. Ranked above it they took six replies off the
    # positive signal that genuinely carried one - "Interested - what does it
    # cost?", "Send me the details please" - and the positive count is a
    # number the client reads. So POSITIVE keeps anything carrying explicit
    # interest, and these two catch the requests that carry none.
    #
    # The cost of that choice, stated because it is real: a warm reply that
    # ALSO asks a question is routed as positive, and the engine answers
    # positive with a booking link. Where the question is about price, terms
    # or dates the commitment gate catches it first and raises a ticket, so
    # the dangerous half is covered; the rest is a judgement the operator can
    # reverse by moving these two lines up.
    (SEND_INFO, SEND_INFO_PATTERNS, 0.8),
    (QUESTION, QUESTION_PATTERNS, 0.75),
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
    # 2026-09-23. All three sit BELOW every stop above them, deliberately.
    #
    # OBJECTION carries the shapes moved out of NEGATIVE - "we already use
    # X", "not a priority right now". An objection paired with an explicit
    # decline ("we already use Harvest, no thanks") still reads NEGATIVE,
    # because NEGATIVE matched higher up. That ordering IS the operator's
    # rule "the decline patterns win only when present", and it needs no
    # extra logic - only this position.
    #
    # SEND_INFO before QUESTION: "can you send me more details" is both, and
    # the answer to it is a document rather than a sentence.
    (OBJECTION, OBJECTION_PATTERNS, 0.75),
)

# ---------------------------------------------------------------------------
# TASK-074: a finer taxonomy for the learning dataset.
#
# Three analysis categories that sub-classify what production rules leave
# as UNKNOWN.  They exist so cadence and copy analysis can distinguish
# curiosity from a concrete meeting step from a stated constraint.
#
# Three rules make them safe:
#
#   1. Negation first.  No pattern fires when the same clause negates it.
#      "Not intriguing" must not become INTERESTED.  The guard is clause-
#      based: a negator in a different clause ("I am not sure, but it is
#      intriguing") does not block, because the "not" modifies "sure",
#      not "intriguing".
#
#   2. Ambiguity stays UNKNOWN.  A bare question with no commitment signal
#      is UNKNOWN.  Context may only move UNKNOWN to a named category when
#      the reply itself carries the signal - never when the signal comes
#      only from what we said.
#
#   3. Nothing new maps to POSITIVE.  Every new category maps to UNKNOWN
#      in accountpolicy.CLASSIFIER_OUTCOME.  An analysis label can never
#      widen what automation is allowed to do.
#
# These patterns run ONLY when production rules return nothing.  A message
# that production rules already classify is never reclassified here.
# ---------------------------------------------------------------------------

# Clause boundaries for the negation guard.  A negator in one clause does
# not block a pattern in another: "I am not sure, but it is intriguing"
# has "not" in the first clause and "intriguing" in the second.
_CLAUSE_BOUNDARY = re.compile(r"[,;:!?]|\b(?:but|and|or|yet|however)\b")

# Words that negate the next content word in the same clause.
_NEGATOR = re.compile(
    r"\b(?:not|n'?t|never|neither|nor|no|hardly|barely|scarcely)\b", re.I)

# What the taxonomy considers when deciding interest.  Each pattern is
# guarded by `_is_negated` before it fires.  Bare adjectives
# ("interesting", "curious") are included because the negation guard is
# the safety net - production rules do not catch "not intriguing" or
# "curious about your platform", and the taxonomy must handle both.
# TASK-076 MEASURED THIS SET AND MOST OF IT WAS WRONG. Precision 0.44 on a
# 263-reply sample: 29 of the 52 replies called INTERESTED were not.
#
# 21 of those 29 came from ONE pattern - a bare `interesting|intriguing|
# intrigued`. In outbound sales "interesting" is a POLITENESS MARKER rather
# than an interest signal: "sounds interesting, but..." was a refusal 29
# times out of 52. The bare adjective patterns are removed for that reason.
# Narrowing for precision is permitted; widening for recall is what TASK-076
# forbids.
#
# What survives is the phrasings where the sender ASKS FOR SOMETHING. A
# request is an act; an adjective is a manner. MEETING_INTENT and OBJECTION
# measured 1.00 precision because they were already built that way.
#
# All 29 false positives are listed in docs/TAXONOMY-PRECISION-2026-09-14.md.
# Anyone tempted to put the adjective back should read that list first.
INTERESTED_PATTERNS = (
    r"\bi (?:find|found|am) (?:this|it|that) (?:interesting|intriguing|curious)\b",
    # PREDICATIVE ONLY - "that's interesting", never "that's an interesting
    # <noun>". The noun-phrase form cannot be made safe: "that's an intriguing
    # approach" and "this is an interesting waste of my time" are the same
    # shape, and the NOUN carries the meaning. Admitting it put the measured
    # false positive straight back. Regex cannot read the noun, so the form
    # is refused entirely and a genuine "intriguing approach" is lost with it.
    r"\b(?:that|this|it)(?:'?s| is) (?:interesting|intriguing|curious)\b",
    r"\b(?:i'?m|i am) curious about\b",
    r"\bcurious to (?:learn|know|hear|see)\b",
    r"\bi(?:'d| would) like to know more\b",
    r"\btell me (?:about|something|everything|why)\b",
    r"\bgo on\b",
    r"\bshow me\b",
)

# A concrete step towards a meeting: proposing a time, asking for
# availability, or naming a scheduling action.  Distinct from POSITIVE
# because these are the messages where the prospect is not just warm but
# actively trying to set up a meeting.  Production rules catch many of
# these already ("book a time", "set up a call"); the taxonomy catches
# the ones that slip through.
MEETING_INTENT_PATTERNS = (
    r"\blet'?s (?:meet|book|schedule|set up)\b",
    r"\bcan we (?:meet|talk|chat)\b",
    r"\bhow about (?:a call|meeting|we (?:talk|chat|meet))\b",
    r"\b(?:next|this) (?:monday|tuesday|wednesday|thursday|friday)\b",
    r"\b(?:what|when) (?:time|day) works\b",
    r"\b(?:send|share) (?:me )?(?:a )?(?:calendar|invite)\b",
    r"\bi (?:am|'m) (?:free|available) (?:on|next|this|tomorrow)\b",
    r"\b(?:pick|choose|suggest) (?:a )?(?:time|slot|day)\b",
)

# A specific stated constraint, not a blanket refusal.  "Too expensive"
# is an objection that a future pricing conversation could address; "not
# interested" is a refusal.  The distinction matters for the learning
# dataset because objections signal a negotiable barrier while refusals
# signal a closed door.
OBJECTION_PATTERNS = (
    r"\btoo (?:expensive|costly|pricey|cheap)\b",
    r"\b(?:no|not enough) budget\b",
    r"\b(?:no|not enough) (?:time|resources|bandwidth)\b",
    r"\b(?:too|too many|too few) (?:people|staff|team members)\b",
    r"\bour team is too (?:small|large)\b",
    r"\b(?:we|I) (?:do not|don'?t) have (?:the |a )?(?:budget|time|resources)\b",
    r"\bnot (?:in |within )?(?:our |the )?budget\b",
    r"\b(?:above|beyond|outside) (?:our |the )?budget\b",
    r"\bwe(?:'re| are) (?:too small|too big|not big enough)\b",
)

TAXONOMY_RULES = (
    (MEETING_INTENT, MEETING_INTENT_PATTERNS, 0.7),
    (OBJECTION, OBJECTION_PATTERNS, 0.7),
    (INTERESTED, INTERESTED_PATTERNS, 0.6),
)


def _is_negated(text, match_start):
    """Whether the match position is negated within its own clause.

    Splits the text at clause boundaries (commas, semicolons, question
    marks, and coordinating conjunctions) and checks whether the clause
    containing the match also contains a negator before the match
    position.  A negator in a different clause does not block:

        "I am not sure, but it is intriguing"
            -> 'not' is in the first clause, 'intriguing' in the second
            -> NOT negated (the 'not' modifies 'sure', not 'intriguing')

        "not intriguing at all"
            -> 'not' and 'intriguing' in the same clause
            -> IS negated
    """
    clause_start = 0
    for boundary in _CLAUSE_BOUNDARY.finditer(text):
        if boundary.end() <= match_start:
            clause_start = boundary.end()
        else:
            break
    clause = text[clause_start:match_start]
    return bool(_NEGATOR.search(clause))


def classify_taxonomy(text):
    """The analysis pass.  Runs only when production rules return nothing.

    Returns a verdict dict for INTERESTED, MEETING_INTENT, or OBJECTION,
    or None if no taxonomy pattern matched (after negation filtering).

    Every category the taxonomy produces maps to UNKNOWN in
    accountpolicy, so a taxonomy verdict can never widen what automation
    is allowed to do.
    """
    body = normalise(text)
    if not body:
        return None
    for category, patterns, confidence in TAXONOMY_RULES:
        for pattern in patterns:
            match = re.search(pattern, body, re.I)
            if match and not _is_negated(body, match.start()):
                return {
                    "classification": category,
                    "confidence": confidence,
                    "reason": f"taxonomy: matched {category} phrase",
                    "evidence": [match.group(0).strip().lower()],
                    "classifier": VERSION,
                }
    return None


def normalise(text):
    # TASK-066: LinkedIn (and many mobile clients) use the Unicode right
    # single quotation mark (U+2019, ') instead of the ASCII apostrophe.
    # Every pattern in this module uses '? to make the apostrophe optional,
    # but that only matches U+0027. Normalising here fixes every pattern
    # at once rather than doubling each alternation.
    text = (text or "").replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip()


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
        if category == AUTOMATED and not hits and _is_bare_acknowledgement(body):
            # OPERATOR, 2026-09-22: "'thanks for your email' with no
            # content" is automated. It is checked HERE, at AUTOMATED's own
            # place in the table, and not before the loop.
            #
            # Before the loop is where I first put it and it was wrong:
            # "No, thank you.", "Not for me, thanks." and "No interest,
            # thanks." are all short, carry no intent, and end in a thanks,
            # so every one of them became `automated` - a refusal softened
            # by a classification, which is the single thing this module's
            # docstring says must never happen. Three existing tests caught
            # it. At this position every refusal has already been tested.
            hits = _hits(body, BARE_ACKNOWLEDGEMENT_PATTERNS)
        if category == REFERRAL and hits and not _points_at_somebody(body):
            continue                  # a hand-off phrase pointing at nobody
        if category == POSITIVE and hits and not _positive_carries_intent(body):
            # OPERATOR, 2026-09-22: "Positive requires intent." A bare
            # `pricing` or `calendar` out of a signature or an
            # autoresponder is not somebody asking for anything. Fall
            # through rather than claim interest: whatever matches next is
            # safer, and nothing matching leaves it UNKNOWN for a person.
            continue
        if hits:
            return {"classification": category, "confidence": confidence,
                    "reason": f"matched {len(hits)} {category} phrase(s)",
                    "evidence": hits[:4], "classifier": VERSION}
    return None
def _excerpt(text, limit=200):
    body = normalise(text)
    return body if len(body) <= limit else body[:limit - 1] + "…"


#: Out-of-office markers in the SUBJECT LINE, which is where every mail
#: client in every language announces an autoresponder plainly while the body
#: is free prose in a language our patterns do not read.
#:
#: 2026-09-23: nine of nine unclassified replies on 2026-09-22 were
#: autoresponders in German, Danish, Czech, Hungarian and English. One of them
#: - "Sehr geehrte Damen und Herren... In dringenden Faellen wenden Sie sich
#: bitte an buero@..." - classified as REFERRAL at 0.8 off its emergency
#: contact line, and referral is an ANSWERABLE class. The body could not be
#: read; the subject said "Automatische Antwort" in plain sight.
#:
#: Matched case-insensitively as substrings against the subject, because
#: clients prefix and suffix them freely ("Automatische Antwort: [EXTERN] ...").
OUT_OF_OFFICE_SUBJECTS = (
    # English
    "out of office", "out-of-office", "automatic reply", "auto-reply",
    "auto reply", "autoreply", "away from", "on leave", "on holiday",
    "on annual leave", "maternity leave", "paternity leave",
    # German
    "automatische antwort", "abwesenheitsnotiz", "abwesend",
    "nicht im buero", "nicht im büro", "urlaub",
    # Danish / Norwegian
    "autosvar", "fravaer", "fravær", "ferie", "ikke på kontoret",
    # Czech / Slovak
    "automatická odpověď", "automaticka odpoved",
    "mimo kancelář", "mimo kancelar", "dovolená", "dovolena",
    # Hungarian
    "szabadság", "szabadsag", "automatikus válasz",
    "automatikus valasz", "távollét",
    # Croatian / Serbian / Bosnian
    "automatski odgovor", "odsutnost", "odsutan", "godišnji odmor",
    "godisnji odmor", "izvan ureda",
)


#: Mailboxes that belong to a company rather than a person. A referral to
#: one of these is not a referral to somebody - it is an autoresponder's
#: emergency contact, a website footer, or a switchboard.
#:
#: 2026-09-23: a German out-of-office naming `buero@example-agency.test`
#: classified as REFERRAL at 0.8. Under the reply-engine brief a referral
#: writes to the referred person via a NEW SEQUENCE, so the engine would have
#: enrolled a company's general office inbox because their autoresponder
#: listed it. Local part only, matched exactly after stripping +tags.
GENERIC_MAILBOXES = frozenset((
    "info", "office", "buero", "bureau", "kontakt", "contact", "hello",
    "hallo", "sales", "support", "admin", "team", "mail", "email", "post",
    "enquiries", "inquiries", "general", "reception", "help", "desk",
    "helpdesk", "service", "customerservice", "accounts", "accounting",
    "billing", "invoice", "invoices", "finance", "hr", "jobs", "careers",
    "recruitment", "marketing", "press", "media", "privacy", "legal",
    "noreply", "no-reply", "donotreply", "webmaster", "postmaster",
    "abuse", "security", "newsletter", "subscribe", "unsubscribe",
))


def is_generic_mailbox(address):
    """True when an address belongs to a company rather than to a person."""
    local = str(address or "").strip().lower().split("@")[0]
    local = local.split("+")[0]
    if not local:
        return False
    if local in GENERIC_MAILBOXES:
        return True
    # `info.uk`, `sales-eu`, `office_2` - a generic name with a suffix is
    # still generic. Split on the usual separators and test the head.
    head = re.split(r"[._-]", local)[0]
    return head in GENERIC_MAILBOXES


def subject_says_out_of_office(subject):
    """True when the SUBJECT plainly announces an autoresponder.

    The subject is the one part of an autoresponder that is reliably
    formulaic across languages: the mail client writes it, not the person.
    """
    # `.lower()` explicitly: `normalise` collapses whitespace but does NOT
    # change case, and every marker below is lowercase. Relying on normalise
    # for it matched nothing and looked exactly like "no autoresponders
    # today" - caught only because the test asserted a real subject line.
    text = normalise(str(subject or "")).lower()
    return any(marker in text for marker in OUT_OF_OFFICE_SUBJECTS)


def classify(text, model=None, threshold=CONFIDENCE_THRESHOLD,
             subject=None):
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

    # THE SUBJECT OUTRANKS A BODY NOBODY CAN READ - but never a stop.
    #
    # An autoresponder in a language these patterns do not speak lands as
    # `unknown` at best and, on 2026-09-22, as REFERRAL at 0.8 at worst: a
    # German out-of-office naming an emergency contact matched a referral
    # phrase, and referral is a class the reply engine may act on.
    #
    # So a subject that plainly says "Automatische Antwort" or "Szabadsag"
    # settles it. The exception is the rule this module already enforces
    # everywhere else: a classification may never SOFTEN a stop. If the body
    # independently reads as an unsubscribe or a refusal, that wins - a
    # person who writes "remove me" inside an autoresponder still means it.
    if subject is not None and subject_says_out_of_office(subject):
        found = (verdict or {}).get("classification")
        if found not in (UNSUBSCRIBE, NEGATIVE, ACCOUNT_DNC):
            return {"classification": OUT_OF_OFFICE, "confidence": 0.9,
                    "reason": "the subject line announces an autoresponder",
                    "evidence": [str(subject)[:120]],
                    "classifier": VERSION,
                    "extract_method": extracted.get("method"),
                    "subject_detected": True,
                    "body_would_have_been": found}
    # TASK-074: the analysis taxonomy runs after production rules and
    # before the model.  It sub-classifies UNKNOWN into INTERESTED,
    # MEETING_INTENT, or OBJECTION for the learning dataset.  Every new
    # category maps to UNKNOWN in accountpolicy, so this can never widen
    # what automation is allowed to do.
    if verdict is None:
        verdict = classify_taxonomy(cleaned)
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

    Never resumes anything. The pause is conditional on the classification:
    a pure out-of-office skips `accountpolicy.apply_reply` entirely (the
    OUT_OF_OFFICE_RECORDED event carries the return date for `oooreturn`);
    a provider-flagged automated non-OOO reply also skips it; everything
    else - including UNKNOWN - goes through `accountpolicy.apply_reply`,
    which may add hold/stop/suppress state and may never subtract from it.

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
    # TASK-030: `accountpolicy.apply_reply` is skipped for automated
    # non-OOO replies. A mail-server autoresponder is not a person and
    # must not suppress outreach. An out-of-office is the exception: it
    # still defers the next touch through `apply_reply` and the
    # OUT_OF_OFFICE_RECORDED event above.
    #
    # For a pure out-of-office (machine-generated, no human sentence),
    # `apply_reply` runs and defers the contact, but `inbound.handle`
    # undoes the account-level pause afterwards. An OOO that also
    # contains a human sentence goes through `apply_reply` and the
    # account pause stands - the fail-safe requires it.
    #
    # The classification event is recorded above for reporting in all
    # cases; what changes is whether `apply_reply` runs at all.
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
        # Last, and deliberately last. The account was paused by
        # `accountpolicy.apply_reply` above (a positive reply maps to HOLD
        # at ACCOUNT scope), the classification is recorded, and only now
        # is anybody told. `notify.positive_reply` cannot raise - see its
        # docstring - so a Slack problem cannot unwind any of it. A
        # notification layer that runs before the pause is a notification
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
    Either way the caller's business state is already correct: the account
    is paused (by `accountpolicy.apply_reply` for a positive reply) and the
    classification is recorded before this runs.
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
