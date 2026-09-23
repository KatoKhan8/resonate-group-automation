#!/usr/bin/env python3
"""Decide what to answer, refuse to invent the words, and send nothing.

OPERATOR, 2026-09-23: "Build the reply engine draft-only first, end to end,
every class, every 'never' enforced, every draft logged... The send path is a
single gated switch, off until Productive confirms in writing and I flip it."

## THE SWITCH

`SENDING_ENABLED = False`, and it is the only thing between this module and a
prospect's inbox. It is a module constant rather than an environment variable
for the same reason `slackconversation.CLIENT_CHANNEL_GAG` is: an env var is
unset by a restart, and flipping this has to be a deliberate edit followed by
a deliberate deploy. `send()` refuses while it is false and nothing else in
this module reaches a provider at all.

The operator's own precondition is recorded beside it: **Productive must
confirm in writing that system-written replies may go out under their
senders' names.** That confirmation is not a flag this module can check, so
the flag stands in for it and the docstring names what it stands for.

## IT REFUSES TO WRITE PROSE

`prompts/reply_handling.md` does not exist yet. Until it does, `compose()`
raises `NoRegister` and every decision comes back `DRAFT_BLOCKED` with that
reason. This is the operator's instruction - "refuse to compose, never invent
the voice" - and it is the right shape regardless: a reply engine whose voice
was guessed by the machine that runs it has no author, and "sounds about
right" is not a standard anybody can hold it to.

So today this module answers *what should happen to this reply* completely,
and *what to say* not at all. Those are separable and only one of them needs
a human's words.

## TWO CLASSES THE CLASSIFIER CANNOT PRODUCE

The operator named six answerable classes: question, objection, not_now,
send_info, referral, positive. `replies.CATEGORIES` has no `question` and no
`send_info`. They are listed in `ROUTES` as UNAVAILABLE rather than omitted,
because a class that is silently absent is a class nobody notices is never
being answered. `answerable()` refuses them by name.
"""
import datetime
import os
import re

from . import replies

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- the switch

#: THE ONLY GATE BETWEEN THIS MODULE AND A PROSPECT. Flip to True only after
#: Productive has confirmed IN WRITING that system-written replies may go out
#: under their senders' names - operator's own precondition, 2026-09-23 - and
#: only by editing this line and restarting the loop that imports it.
SENDING_ENABLED = False

#: What the flag stands in for, quoted so a future reader knows the condition
#: was a person's and not an engineering preference.
SENDING_PRECONDITION = (
    "Productive must confirm in writing that system-written replies may go "
    "out under their senders' names before the first one is sent "
    "(operator, 2026-09-23)")

REGISTER_PATH = os.path.join(ROOT, "prompts", "reply_handling.md")


class NoRegister(RuntimeError):
    """There are no standing reply instructions, so there is no voice."""


class SendingDisabled(RuntimeError):
    """The gate is shut. It is shut by default and opens by edit."""


# ---------------------------------------------------------------- the routes

REPLY = "reply"                 # the engine may answer this class
NEVER = "never"                 # the engine must not answer, ever
REVIEW = "review"               # a person decides; pause meanwhile
UNAVAILABLE = "unavailable"     # the classifier cannot produce this class

#: Every class the operator named, plus every class the classifier can
#: actually return. Anything not listed here is REVIEW by construction - see
#: `route_for`, which never defaults to REPLY.
ROUTES = {
    # answerable, per the operator
    "question": UNAVAILABLE,      # not in replies.CATEGORIES
    "send_info": UNAVAILABLE,     # not in replies.CATEGORIES
    "objection": REPLY,
    "not_now": REPLY,
    "referral": REPLY,            # writes to the REFERRED person, never a reply
    "positive": REPLY,
    "interested": REPLY,
    "meeting_intent": REPLY,

    # never answered, per the operator
    "automated": NEVER,
    "out_of_office": NEVER,
    "assistant_redirect": NEVER,
    "unsubscribe": NEVER,
    "bounce": NEVER,

    # a decline is not answered by the engine beyond the one question below
    "negative": REVIEW,
    "not_relevant": REVIEW,
    "account_do_not_contact": NEVER,

    # explicitly a gap, not a lukewarm answer
    "unknown": REVIEW,
    "neutral": REVIEW,
}

#: Below this, a reply is drafted rather than sent even when everything else
#: passes. `replies.CONFIDENCE_THRESHOLD` is the classifier's own bar; this is
#: the engine's, and it is deliberately higher - classifying a reply wrongly
#: costs a mislabel, answering one wrongly costs a relationship.
CONFIDENCE_FLOOR = 0.80

#: The operator: "never more than 2 system replies per thread without a human
#: reply in between".
MAX_SYSTEM_REPLIES_PER_THREAD = 2

#: The operator: "After a decline: one short non-sales question at most, then
#: silence; the account goes quiet 180 days."
POST_DECLINE_QUESTIONS = 1
DECLINE_QUIET_DAYS = 180

#: "Never commits to price, discount, contract terms, integrations or dates."
#: Matched against the INBOUND text: the engine refuses to answer the question
#: rather than trying to answer it carefully.
COMMITMENT_TOPICS = (
    ("price", r"\b(?:price|pricing|cost|how much|quote|rate card|per seat|"
              r"per user|budget for)\b"),
    ("discount", r"\b(?:discount|reduction|cheaper|deal|off the price|"
                 r"better price)\b"),
    ("contract", r"\b(?:contract|terms|sla|msa|dpa|notice period|"
                 r"cancellation|lock[- ]?in|invoice terms)\b"),
    ("integrations", r"\b(?:integrat\w+|api|webhook|connect(?:s|or)?\s+(?:to|with)|"
                     r"sync(?:s|ing)?\s+with)\b"),
    ("dates", r"\b(?:go[- ]?live|deadline|by when|timeline|start date|"
              r"delivery date|when can you)\b"),
)

#: The operator: "never outside the recipient's local business hours."
BUSINESS_HOURS = (9, 18)
BUSINESS_DAYS = (0, 1, 2, 3, 4)


def register(path=None):
    """Productive's standing reply instructions, or `NoRegister`.

    Never returns a default. A missing register is the one condition under
    which this engine has nothing to say, and substituting house style would
    be inventing the voice the operator told it not to invent.
    """
    path = path or REGISTER_PATH
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError:
        raise NoRegister(
            f"no reply register at {path!r}: the client's standing reply "
            "instructions are not in the repository, so this engine has no "
            "voice to write in and will not guess one")
    if not text:
        raise NoRegister(f"{path!r} is empty; an empty register is not a voice")
    return text


def have_register(path=None):
    try:
        register(path)
        return True
    except NoRegister:
        return False


def route_for(classification):
    """What the engine may do with this class. Never defaults to REPLY."""
    return ROUTES.get(str(classification or "").strip().lower(), REVIEW)


def answerable(classification):
    return route_for(classification) == REPLY


def commitments_in(text):
    """Topics the engine may never commit to, found in the INBOUND text."""
    body = str(text or "")
    return tuple(name for name, pattern in COMMITMENT_TOPICS
                 if re.search(pattern, body, re.I))


def inside_business_hours(at=None, tz_offset_hours=None):
    """Is it a weekday business hour where the RECIPIENT is?

    `tz_offset_hours` is the recipient's offset from UTC. **None means
    unknown, and unknown is treated as outside** - the register's own rule
    that a guessed timezone is worse than a missing one. Sending at 3am
    because nobody recorded a timezone is the failure this prevents.
    """
    if tz_offset_hours is None:
        return False, "the recipient's timezone is unknown, so local hours cannot be proven"
    at = at or datetime.datetime.now(datetime.timezone.utc)
    local = at + datetime.timedelta(hours=float(tz_offset_hours))
    if local.weekday() not in BUSINESS_DAYS:
        return False, f"{local:%A} is not a business day for the recipient"
    if not (BUSINESS_HOURS[0] <= local.hour < BUSINESS_HOURS[1]):
        return False, (f"{local:%H:%M} local is outside "
                       f"{BUSINESS_HOURS[0]:02d}:00-{BUSINESS_HOURS[1]:02d}:00")
    return True, None


def system_replies_in(thread):
    """How many replies in this thread the SYSTEM wrote, since the last human."""
    count = 0
    for turn in reversed(list(thread or [])):
        who = str((turn or {}).get("by") or "").lower()
        if who in ("human", "operator", "person"):
            break
        if who == "system":
            count += 1
    return count


class Decision(dict):
    """What should happen to one inbound reply, and why. Never the words."""

    @property
    def action(self):
        return self.get("action")

    @property
    def will_answer(self):
        return self.get("action") == REPLY


def decide(event, verdict, thread=None, tz_offset_hours=None, at=None,
           register_path=None):
    """Everything except the words. Pure: reads nothing, writes nothing.

    The order is the point. Class first, because a class the engine may never
    answer ends the question before any other rule is consulted. Then the
    refusals that apply to answerable classes, cheapest and most absolute
    first. `checks` records every rule that was evaluated, so a draft carries
    the reasoning and not only the verdict.
    """
    text = ""
    for field in ("text", "body", "message", "reply"):
        value = (event or {}).get(field)
        if isinstance(value, str) and value.strip():
            text = value
            break

    classification = (verdict or {}).get("classification")
    confidence = float((verdict or {}).get("confidence") or 0.0)
    route = route_for(classification)
    checks = []

    out = Decision(at=(at or datetime.datetime.now(datetime.timezone.utc)
                       ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   classification=classification, confidence=confidence,
                   route=route, checks=checks, action=None, why=None,
                   ticket=None, sending_enabled=SENDING_ENABLED)

    if route == NEVER:
        checks.append(("class", False, f"{classification} is never answered"))
        out.update(action=NEVER,
                   why=f"the engine never replies to {classification}")
        return out

    if route == UNAVAILABLE:
        checks.append(("class", False,
                       f"{classification} is not a class replies.classify can "
                       "return; it was named in the brief but does not exist"))
        out.update(action=REVIEW,
                   why=f"{classification} is UNAVAILABLE - the classifier "
                       "cannot produce it, so the engine must not act on it")
        return out

    if route == REVIEW:
        checks.append(("class", False, f"{classification} goes to a person"))
        out.update(action=REVIEW,
                   why=f"{classification} is drafted for review, never sent")
        return out

    checks.append(("class", True, f"{classification} is answerable"))

    # --- refusals that apply even to an answerable class, absolute first
    topics = commitments_in(text)
    if topics:
        checks.append(("commitment", False, "asks about " + ", ".join(topics)))
        out.update(action=REVIEW,
                   why="the reply asks about " + ", ".join(topics) +
                       ", which the engine may never commit to",
                   ticket={"to": "#resonate-os", "topics": list(topics),
                           "say": "let me get you the exact answer"})
        return out
    checks.append(("commitment", True, "no price/terms/dates commitment asked"))

    used = system_replies_in(thread)
    if used >= MAX_SYSTEM_REPLIES_PER_THREAD:
        checks.append(("thread_cap", False,
                       f"{used} system replies since the last human"))
        out.update(action=REVIEW,
                   why=f"{used} system replies already in this thread with no "
                       "human reply in between")
        return out
    checks.append(("thread_cap", True, f"{used} system replies so far"))

    if confidence < CONFIDENCE_FLOOR:
        checks.append(("confidence", False,
                       f"{confidence:.2f} < {CONFIDENCE_FLOOR}"))
        out.update(action=REVIEW,
                   why=f"confidence {confidence:.2f} is below the "
                       f"{CONFIDENCE_FLOOR} floor, so this is drafted")
        return out
    checks.append(("confidence", True, f"{confidence:.2f}"))

    ok, why = inside_business_hours(at=at, tz_offset_hours=tz_offset_hours)
    if not ok:
        checks.append(("business_hours", False, why))
        out.update(action=REVIEW, why="outside business hours: " + why)
        return out
    checks.append(("business_hours", True, "inside local business hours"))

    if not have_register(register_path):
        checks.append(("register", False, "prompts/reply_handling.md absent"))
        out.update(action=REVIEW,
                   why="the reply register does not exist, so there is no "
                       "voice to compose in")
        return out
    checks.append(("register", True, "register present"))

    out.update(action=REPLY, why="every gate passed")
    return out


def compose(event, decision, register_path=None):
    """The words. Raises `NoRegister` until the client's instructions exist."""
    text = register(register_path)          # raises NoRegister
    raise NoRegister(
        "a register is present (%d chars) but no composer is wired yet: "
        "composition is the next increment and must be written against the "
        "client's own instructions, not around them" % len(text))


def draft(event, verdict, **kw):
    """One inbound reply -> one draft record. Composes nothing it cannot."""
    decision = decide(event, verdict, **kw)
    row = {
        "kind": "reply_draft",
        "at": decision["at"],
        "provider": (event or {}).get("provider"),
        "provider_event_id": (event or {}).get("provider_event_id"),
        "channel": (event or {}).get("channel"),
        "contact": (event or {}).get("contact_key") or (event or {}).get("contact"),
        "inbound": str((event or {}).get("text") or "")[:1000],
        "classification": decision["classification"],
        "confidence": decision["confidence"],
        "action": decision["action"],
        "why": decision["why"],
        "checks": decision["checks"],
        "ticket": decision["ticket"],
        "reply": None,
        "compose_error": None,
        "status": "DRAFT (system)",
        "sent": False,
        "sending_enabled": SENDING_ENABLED,
    }
    if decision.will_answer:
        try:
            row["reply"] = compose(event, decision,
                                   register_path=kw.get("register_path"))
        except NoRegister as exc:
            row["compose_error"] = str(exc)
            row["action"] = REVIEW
            row["why"] = "would have replied, but: " + str(exc)[:160]
    return row


def send(row):
    """Refuses. The single gated switch, and it is off."""
    if not SENDING_ENABLED:
        raise SendingDisabled(
            "SENDING_ENABLED is False. " + SENDING_PRECONDITION +
            ". Nothing was sent.")
    raise SendingDisabled(
        "SENDING_ENABLED is True but no transport is wired: sending is a "
        "later increment and this refusal is the proof it has not arrived "
        "by accident.")
