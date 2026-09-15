#!/usr/bin/env python3
"""Cadence expansion. BUILD-SPEC section 7, phase 7.

One shared multichannel timeline per contact, and one pause per company.

  day  channel   what                                    generated
   1   email     the opener                              yes
   3   linkedin  connection request with a short note    no, template
   5   email     persona pain, template plus one line    no, template
   8   linkedin  message, only if the connection landed  no, template
  10   email     comparable proof                        no, template
  15   email     a different angle from day 1            yes
  21   email     clean exit                              no, template

Two of the emails are model written, day 1 and day 15. The other three are
templates. That ratio is the difference between a workable and an unworkable
cost per lead at 500 domains, so it is asserted, not assumed.

Rules enforced here, all from section 7:

  - never two channels on the same day for the same person
  - the LinkedIn note never references the email, and the email never
    references the LinkedIn note
  - if the connection is accepted, day 10 switches to the short variant
  - a reply on either channel pauses both tracks for the whole company
  - the economic buyer track starts start_offset_days behind the champion

Every template email is expanded here and then linted as a finished email.
Nothing that fails lint is push eligible, whatever produced it.
"""
import argparse
import re

from . import (approval, clients, events, lint, linkedinstate, stepstate,
               store)

CHAMPION = "champion"
BUYER = "economic_buyer"

# The timeline. `requires` gates a step on an event; `variant` swaps the
# template once the connection is accepted.
STEPS = (
    {"key": "day1", "day": 1, "channel": "email", "generated": True},
    {"key": "day3", "day": 3, "channel": "linkedin", "template": "linkedin_intro"},
    {"key": "day5", "day": 5, "channel": "email", "template": "persona_pain"},
    {"key": "day8", "day": 8, "channel": "linkedin", "template": "linkedin_followup",
     "requires": "connection_accepted"},
    {"key": "day10", "day": 10, "channel": "email", "template": "comparable_proof",
     "variant_if_accepted": "comparable_proof_short"},
    {"key": "day15", "day": 15, "channel": "email", "generated": True},
    {"key": "day21", "day": 21, "channel": "email", "template": "breakup"},
)


# --------------------------------------------------- whose cadence is this
#
# `STEPS` above is the cadence every campaign has ever run: a module
# constant, seven steps, fixed days and fixed channels. Nothing about a
# campaign changed it, which means cadence length has never been a variable
# in this system - and an experiment comparing four steps against seven
# needs it to be one.

# A campaign may carry its own sequence under this key. Absent, the
# constant applies and behaviour is exactly what it has always been.
CADENCE_KEY = "cadence_steps"

# A client config already names its cadence - `cadence: demo_default` - and
# has since before this function existed. The first version of `steps_for`
# read `config["cadence"]["steps"]` and crashed on every real client file,
# because that key holds a string.
#
# So the name keeps its meaning and the sequences live beside it:
#
#     cadence: demo_default
#     cadences:
#       demo_default:
#         steps: [...]
#
# A name with no matching entry falls through to the constant, which is
# what every client file does today.
CADENCE_LIBRARY_KEY = "cadences"

# What a step must name to be executable. Deliberately the same shape the
# constant already uses, because the whole point is that the two paths
# produce the same kind of object.
REQUIRED_STEP_FIELDS = ("key", "day", "channel")


class BadCadence(ValueError):
    """A campaign named a sequence that cannot be executed.

    Raised rather than falling back to the constant. A campaign that meant
    to run four steps and silently ran seven is worse than one that
    refuses: the first sends three messages nobody authorised.
    """


def steps_for(campaign=None, config=None, rec=None, contact=None):
    """The sequence this campaign runs, or the one every campaign ran.

    `rec` and `contact` are what a cadence *experiment* is resolved
    against: when the campaign carries one and this unit has been assigned
    an arm, the arm's sequence is what runs. That is the link that makes an
    arm a real treatment rather than a label - without it an experiment
    would assign, report, and change nothing about what was sent.

    Three properties hold and each has a test.

    **A campaign with no cadence behaves identically.** Not approximately:
    the constant is returned unchanged, and a test walks a record through
    both paths and compares the whole timeline.

    **Step keys are identity, not labels.** Approvals are fingerprinted per
    step key, events carry it, and `push_id` is
    `record:contact:step:channel`. A sequence that reused a key for a
    different step would inherit that step's approvals and events, so keys
    are required to be unique and are checked here rather than trusted.

    **Days ascend.** A sequence whose day numbers go backwards is not a
    sequence; `_due` compares against a batch day and would let a later
    step fire before an earlier one.
    """
    # The assigned arm first: a campaign running an experiment has a
    # sequence per unit, not one for the campaign. Imported here rather
    # than at module scope because `cadencearms` validates through this
    # module and the two would otherwise import each other at load time.
    steps = None
    if rec is not None:
        from . import cadencearms

        steps = cadencearms.steps_for(campaign, rec, contact, config)
    if steps is None:
        steps = (campaign or {}).get(CADENCE_KEY)
    if steps is None:
        steps = _named_sequence(config)
    if steps is None:
        steps = _library_sequence(config)
    if steps is None:
        return STEPS
    # Present and empty is not the same as absent. A campaign configured
    # with no steps meant something by it, and running seven instead is
    # the silent substitution this function exists to refuse.
    return validate_steps(steps)


def _named_sequence(config):
    """The sequence this client's named cadence defines, if it defines one.

    `cadence:` has always held a name. Most client files name one and
    define nothing, which is the case that returns `None` and lands on the
    constant.
    """
    config = config or {}
    name = config.get("cadence")
    if not isinstance(name, str) or not name:
        return None
    library = config.get(CADENCE_LIBRARY_KEY)
    if not isinstance(library, dict):
        return None
    entry = library.get(name)
    if isinstance(entry, dict):
        return entry.get("steps")
    if isinstance(entry, (list, tuple)):
        return entry
    return None


def _library_sequence(config):
    """A sequence from the shipped library, selected by the client's name.

    The client file names its cadence and cannot hold the steps themselves:
    `clients.parse` reads scalars and inline scalar lists, and a step is a
    mapping - an inline list of mappings comes back split on its commas. So
    the sequences live in `cadencelibrary` and the client file picks one,
    which keeps cadence INTENSITY a one-line configuration change rather than
    a sequence pasted into several modules.

    A config that defines its own `cadences` entry still wins: this is the
    fallback between that and the module constant.
    """
    from . import cadencelibrary

    name = (config or {}).get("cadence")
    return cadencelibrary.named(name) if isinstance(name, str) else None


VARIANTS_KEY = "variants"

# `variants` groups results by node type, and all three LinkedIn types
# share one style table - so the choice between them changes the label on a
# report and nothing about assignment or evaluation. A step may name its
# own `node_type`; otherwise the channel decides.
NODE_TYPE_FOR_CHANNEL = {"email": "email", "linkedin": "linkedin_message"}


def variant_node(spec):
    """A step spec as `src/variants.py` expects to read it.

    Variants live beside `template` and `variant_if_accepted`, which is
    where this sequence already keeps the question of which words a step
    uses. The cadence graph in `src/cadencegraph.py` holds variants too,
    but its node keys are its own (`d1`, `d3`) and it contains branch, wait
    and stop nodes with no linear equivalent - so resolving a running
    step's node out of a graph needs a mapping that does not exist, and the
    graph is not stored on a campaign anyway.
    """
    return dict(spec, type=(spec.get("node_type")
                            or NODE_TYPE_FOR_CHANNEL.get(spec.get("channel"))))


def variant_for(spec, campaign, contact_key, recorded=None, config=None):
    """Which wording this contact gets on this step, or None.

    None when the step has no experiment, and None when there is no
    campaign: an assignment that cannot say which experiment it belongs to
    cannot be reported, and an unreportable assignment is worse than none.

    `recorded` is the variant already written onto the stored step. It
    wins, so a step that was drafted and approved as variant C is still
    variant C after the traffic is shifted.
    """
    from . import variants

    if not (spec or {}).get(VARIANTS_KEY):
        return None
    campaign_id = (campaign or {}).get("campaign_id")
    if not campaign_id:
        return None
    return variants.resolve(variant_node(spec), campaign_id, contact_key,
                            recorded=recorded, config=config)


def validate_steps(steps):
    """Check a candidate sequence, or raise. Returns it as a tuple.

    Checked at read time rather than at write time as well, because a
    sequence can arrive from a stored campaign written by an older build
    and the execution path is the one that must not be surprised.
    """
    if not isinstance(steps, (list, tuple)) or not steps:
        raise BadCadence("a cadence needs at least one step")

    seen, last_day = set(), None
    out = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise BadCadence(f"step {index} is not a step")
        missing = [f for f in REQUIRED_STEP_FIELDS if not step.get(f)]
        if missing:
            raise BadCadence(
                f"step {index} is missing {', '.join(missing)}")
        key = str(step["key"])
        if key in seen:
            raise BadCadence(
                f"two steps share the key {key!r}. A step key is identity: "
                "approvals are fingerprinted against it and every event "
                "carries it, so a repeat would inherit another step's "
                "history")
        seen.add(key)
        try:
            day = int(step["day"])
        except (TypeError, ValueError):
            raise BadCadence(f"step {key!r} has a day that is not a number")
        if last_day is not None and day < last_day:
            raise BadCadence(
                f"step {key!r} is on day {day}, after a step on day "
                f"{last_day}. Steps run in the order they are listed and "
                "the days have to agree with that")
        last_day = day
        if step["channel"] not in ("email", "linkedin"):
            raise BadCadence(
                f"step {key!r} is on channel {step['channel']!r}, which is "
                "not a channel this build sends on")
        if step.get(VARIANTS_KEY):
            if step.get("generated"):
                raise BadCadence(
                    f"step {key!r} is generated and carries variants. A "
                    "generated step's copy is written for this contact and "
                    "a variant would replace it wholesale, which is not a "
                    "variant of anything")
            from . import variants

            blocking = [f for f in variants.validate(variant_node(step))
                        if f["level"] == "block"]
            if blocking:
                raise BadCadence(
                    f"step {key!r}: "
                    + "; ".join(f["why"] for f in blocking))
        out.append(dict(step, day=day, key=key))

    # ONE CONNECTION REQUEST PER PERSON, PER SEQUENCE.
    #
    # `linkedinstate` refuses a second invitation at execution time - a
    # request while one is outstanding is a wait, and a request to somebody
    # who did not accept is a wait too - so a sequence carrying two of them
    # would be a sequence whose second LinkedIn step can never run. That is
    # the shape of a cadence that reports eleven touches and sends ten, and
    # it is exactly what a denser LinkedIn cadence gets wrong: a message
    # step that forgot to say `requires` reads as a second request.
    #
    # Checked here rather than at authoring time as well, because a sequence
    # can arrive from a stored campaign written by an older build and the
    # execution path is the one that must not be surprised.
    requests = linkedinstate.connection_requests(out)
    if len(requests) > 1:
        raise BadCadence(
            "this sequence sends "
            + str(len(requests)) + " connection requests to one person ("
            + ", ".join(str(s["key"]) for s in requests)
            + "). A second invitation is not a retry, and a LinkedIn step "
              "that meant to be a message has to say so - `linkedin_action: "
              "message`, or `requires: connection_accepted`")
    return tuple(out)


def describe_steps(steps):
    """A sequence in one line, for a screen and for a comparison.

    `E -> E -> LI -> E` rather than a table: the shape is the thing an
    operator is comparing, and four of these stacked read faster than four
    tables.
    """
    marks = {"email": "E", "linkedin": "LI"}
    return " -> ".join(marks.get(s.get("channel"), "?") for s in steps or ())

GENERATED_KEYS = tuple(s["key"] for s in STEPS if s.get("generated"))
EMAIL_KEYS = tuple(s["key"] for s in STEPS if s["channel"] == "email")


def generated_keys(steps=None):
    """The step keys that require an LLM call, derived from the sequence.

    A step counts if it or its alternative carries ``generated: True``.
    Returns an empty tuple for a sequence with no generated steps, so an
    estimate derived from this never falls back to a default.

    This replaces ``len(GENERATED_KEYS)`` in every estimator. The module
    constant is tied to ``STEPS`` and drifted when the production cadence
    moved to five emails and six LinkedIn notes; deriving the count from
    the sequence itself is the second representation that was missing.
    """
    if not steps:
        return ()
    out = []
    for step in steps:
        if step.get("generated"):
            out.append(step["key"])
        else:
            alt = step.get("alternative") or {}
            if alt.get("generated"):
                out.append(step["key"])
    return tuple(out)

# Deterministic templates. Section 8 defines four prompts and none of them is a
# LinkedIn note, so the note is a template too: it costs nothing and it cannot
# wander into referencing the email.
TEMPLATES = {
    "linkedin_intro": {
        "note": "hi {first_name}, i work with {sector} teams on {angle_phrase}. "
                "curious how {company} handles it at your size. happy to connect."},
    "linkedin_followup": {
        "note": "thanks for connecting {first_name}. no pitch here. if {angle_phrase} "
                "is on your list this quarter i am happy to share what similar teams did."},
    "persona_pain": {
        "subject": "{angle_phrase}",
        "body": "{first_name}, {line}\n\n"
                "The pattern I see in teams the size of {company} is that the numbers "
                "arrive too late to act on. Utilisation and margin are known at the end "
                "of the month, which is after the month when something could have been "
                "done about them. The work itself is rarely the problem. The visibility "
                "into it is.\n\n"
                "Is that roughly how it works at {company} today, or have you already "
                "put something in place for it?"},
    # NEITHER OF THESE MAY ASSERT A PRIOR MESSAGE. `breakup` below was fixed
    # for exactly this and these two were missed, one screen above it. "one
    # more note and then I will leave it" and "following on from what I
    # mentioned" both claim we have written before. On a record with no
    # confirmed touch - every record in a rebuilt estate, and every record
    # whose day-1 step needs a model that does not ship - that is false on the
    # first message a prospect ever receives.
    #
    # It is the default shape rather than an edge case: `due(day=21)` returns
    # day3, day5, day10 and day21 in ONE batch and 21 is `run.py`'s default, so
    # day10 can be a first touch. `claims.py` cannot catch it - a claim about
    # US carries no number, month or event word - and `outreachclaims`, which
    # is the authority on claims about us, has no consumer on the send path.
    "comparable_proof": {
        "subject": "how teams your size handle {angle_word}",
        "body": "{first_name}, the teams I work with that look most like "
                "{company} tend to arrive at the same place.\n\n"
                "They stop reconciling hours after the fact and start "
                "seeing project margin while the project is still running. The change "
                "that makes the difference is not a new process for the delivery team, "
                "it is that the finance view and the delivery view stop being two "
                "different spreadsheets maintained by two different people.\n\n"
                "Would it be useful to see what that looked like for a team your size?"},
    "comparable_proof_short": {
        "subject": "how teams your size handle {angle_word}",
        "body": "{first_name}, the teams that look "
                "most like {company} usually stop reconciling hours after the fact and "
                "start seeing project margin while the work is still running. The change "
                "is not a new process for delivery, it is that finance and delivery stop "
                "keeping two separate spreadsheets.\n\n"
                "Worth a look at what that did for a team your size?"},
    "breakup": {
        "subject": "closing the loop",
        # This body used to open "I have written a few times ... and not
        # heard back". That is a claim about US, so `claims.py` never saw
        # it: GENERIC_SUBJECTS drops any sentence opening "I ", because
        # claims about the *prospect* are its job. `outreachclaims` is the
        # authority on claims about us and has no consumer on the send
        # path, so on a record with no confirmed touches - every record in
        # a rebuilt estate - a first-ever message asserted a history of
        # messages. This wording claims nothing about what we have sent,
        # which is the only version true whenever it goes out.
        "body": "{first_name}, if {angle_phrase} is not something you are "
                "looking at right now, that is a fair answer in itself. I "
                "will leave it here.\n\n"
                "If it becomes relevant later, the thing worth knowing is that most "
                "teams the size of {company} start looking at this when a project lands "
                "under margin and nobody can say exactly when it went wrong.\n\n"
                "Anything you would want me to send over, or shall I leave it there?"},
}

# Wording that would make one channel reference the other. Section 7.
EMAIL_MENTIONS_LINKEDIN = ("linkedin", "connection request", "connect with me",
                           "my invite", "accepted my request")
NOTE_MENTIONS_EMAIL = ("email", "emailed", "my message", "wrote to you", "inbox",
                       "sent you a note", "replied to my")

# ------------------------------------------------- cross-channel openers
#
# One opener per copy mode, and the mode is decided by `touch.context` from
# evidence rather than chosen here. These are templates for the same reason
# the LinkedIn note is a template: a fixed sentence cannot wander, and the
# only variable in it - the name - comes from the confirming event.
#
# There is deliberately no opener for "somebody reached out". A prospect who
# cannot place the name is being asked to believe something about a
# relationship we were not authorised to describe, and a vague version of an
# unauthorised claim is still the claim. When no mode applies the step is
# written standalone.

CROSS_CHANNEL_OPENERS = {
    # The same human on both channels. No claim about anybody else.
    "same_sender_continuity": {
        "linkedin": "i sent you a note over email as well - thought i would "
                    "connect here too.",
        "email": "i reached out on linkedin as well, so apologies if this "
                 "arrives twice.",
    },
    # Two humans the workspace has said may be described as colleagues.
    "team_handoff": {
        "linkedin": "my colleague {first_name} reached out over email "
                    "earlier. thought i would connect here as well.",
        "email": "My colleague {first_name} reached out on LinkedIn "
                 "recently, so I wanted to follow up here.",
    },
}


REPLY_EVENTS = ("email_reply", "linkedin_reply")
ACCEPT_EVENT = "connection_accepted"


class CadenceError(RuntimeError):
    """The timeline could not be built as specified."""


# ------------------------------------------------------------- the offset

def track_offset(contact, config):
    """The economic buyer starts start_offset_days behind the champion."""
    persona = contact.get("persona")
    if not persona:
        return 0
    settings = clients.personas(config).get(persona) or {}
    return int(settings.get("start_offset_days") or 0)


# ------------------------------------------------------------ expansion

def angle_words(contact, config):
    """The client's own words for this angle, never invented here."""
    persona = contact.get("persona") or CHAMPION
    angles = clients.angles_for(config, persona)
    angle = contact.get("angle")
    phrase = angles.get(angle) if angle else None
    if not phrase:
        phrase = next(iter(angles.values()), "how the work is tracked")
    # The first configured angle, not the literal word "operations". When a
    # contact carries no angle, `phrase` above already falls back to the first
    # angle's phrase, so returning a literal here made the key and the phrase
    # describe two different angles - and the key was then printed into a
    # subject line.
    return angle or next(iter(angles), "operations"), str(phrase)


# `lint.MAX_SUBJECT` fails at 60, so 59 is the longest subject that passes,
# and "how teams your size handle " is 27 characters. That leaves 32 for the
# substitution. The number is not a comment somebody has to keep true: a test
# walks every TEMPLATES subject carrying {angle_word} and proves 32 passes
# lint and 33 does not.
ANGLE_WORD_MAX = 32

# When the client configured no label and their own first clause will not fit.
# Client-agnostic and not marketing copy - it is the idea the `persona_pain`
# body already puts in the client's mouth. The internal angle key is never a
# candidate: "how teams your size handle founder" is the defect this replaces,
# and it reads as nonsense to the person receiving it.
FALLBACK_ANGLE_WORD = "the numbers behind the work"


def angle_word(angle, clause, config):
    """The short topic a subject names, in at most ANGLE_WORD_MAX characters.

    Three sources, most specific first: the label this client configured for
    this angle, the client's own first clause when it fits, and a generic
    topic when neither does. The angle key is never one of them.

    An over-long configured label falls through rather than raising. This is
    copy, not a guard: refusing here would block every day-10 step for that
    client behind a `subject_too_long` buried in `blocked_by`, which is a
    worse failure than a shorter true subject.
    """
    label = clients.angle_labels(config).get(str(angle or "").strip().lower())
    if label and len(label) <= ANGLE_WORD_MAX:
        return label
    if clause and len(clause) <= ANGLE_WORD_MAX:
        return clause
    return FALLBACK_ANGLE_WORD


class CompanyNameUnusable(CadenceError):
    """The only name we hold for this company is its domain."""


def company_name(rec):
    """What to call this company in a message a person will read.

    `rec["company"]` IS OFTEN THE DOMAIN. It is whatever the input file said,
    and on 2026-09-11 three of the five fully verified contacts in the live
    estate held a bare hostname there while `company_facts["name"]` on the same
    record held the real name - an initialism in one case and a two-word name in
    another. Every template interpolates `{company}` two or three times, so the
    first thing those prospects would have read is their own hostname, which is
    the most obvious possible signal that nobody looked.

    So the provider's name wins, the input column is the fallback, and a value
    that is still domain-shaped raises rather than shipping. Raising is the
    conservative direction: `expand_step` already treats a `CadenceError` as a
    step that cannot be rendered, so the step is held and a person sees why,
    instead of a prospect seeing a URL.
    """
    HOSTNAME = re.compile(r"\.[a-z]{2,}$", re.I)
    facts = rec.get("company_facts") or {}
    domain = str(rec.get("domain") or "").strip().lower()
    for candidate in (facts.get("name"), rec.get("company")):
        name = str(candidate or "").strip()
        if not name:
            continue
        # LOOKING LIKE A HOSTNAME IS THE TEST, not resembling the domain.
        #
        # A first version rejected any name whose letters matched the domain's
        # first label. That refused a correct one-word company name at the
        # matching domain - and it did so on the one contact in the live estate
        # that is ready to send, so it would have held the canary and every
        # ordinary record with it. Most companies are named after their domain
        # or the other way round. The defect is a value carrying a TLD, not a
        # value agreeing with the domain.
        if name.lower() == domain or HOSTNAME.search(name.split()[-1]):
            continue
        return name
    raise CompanyNameUnusable(
        f"the only company name on {rec.get('id')!r} is domain-shaped "
        f"({rec.get('company')!r}); refusing to address a prospect by their "
        f"own hostname. Set company_facts.name from a provider lookup")


def template_vars(rec, contact, config):
    angle, phrase = angle_words(contact, config)
    first = (contact.get("name") or "").split()[0] if contact.get("name") else "there"
    facts = rec.get("company_facts") or {}
    company = company_name(rec)
    evidence = (rec.get("evidence") or {}).get(lint.contact_key(contact)) or []
    # The fallback asserts nothing about the prospect.
    #
    # It used to read "you are running utilisation at Ninefields" - a factual
    # claim about how somebody runs their agency, assembled out of OUR angle
    # wording and THEIR company name, with nothing on the record behind it.
    # Two things hid it. `rec["evidence"]` is written only by
    # `generate.persona_angle`, which needs a model and none ships, so the
    # preferred branch above has never once fired and this was the only email
    # text that could ship. And `claims.is_claim` examines a sentence only when
    # it carries a number, a month or an event word, and "running" is none of
    # those, so the claim checker never read it. PRODUCT-GAPS 36.
    #
    # The replacement says who we work with and admits what we do not know.
    # Every value in it - the sector and the company - is on the record.
    # Capital "I" because `{line}` is used by `persona_pain` alone, which is
    # the day-5 EMAIL; the lowercase register belongs to the LinkedIn notes,
    # and mixing it into a body that says "The pattern I see" reads like two
    # people wrote the message.
    line = evidence[0] if evidence else (
        f"I work with {facts.get('industry') or 'services'} teams on "
        f"{phrase.split(',')[0]}, and I do not know how {company} "
        f"handles it")
    return {
        "first_name": first,
        "company": company,
        "angle": angle,
        "angle_word": angle_word(angle, phrase.split(",")[0].strip(), config),
        "angle_phrase": phrase.split(",")[0].strip(),
        "sector": facts.get("industry") or "services",
        "line": str(line).rstrip("."),
    }


def render(template, values):
    out = {}
    for field, text in template.items():
        try:
            out[field] = text.format(**values)
        except KeyError as e:
            raise CadenceError(f"template needs {e} which the record does not have")
    return out


def apply_cross_channel(step, context):
    """Prepend the licensed opener, or leave the step exactly as it was.

    Everything about this function is written so that the unlicensed path is
    the path of least resistance: no context, a context that refuses, a mode
    with no opener, or a missing name all fall through to `return step`
    unchanged. There is no branch in which a reference is added on anything
    other than an explicit `may_reference` with a mode and a name behind it.

    The step keeps the whole context under `cross_channel`, so the preview can
    print the evidence beside the sentence and `cross_channel_leaks` can check
    that the sentence matches the evidence.
    """
    if not context:
        return step
    step["cross_channel"] = context
    if not context.get("may_reference"):
        return step
    reference = context.get("reference") or {}
    opener = (CROSS_CHANNEL_OPENERS.get(reference.get("mode")) or {}).get(
        step.get("channel"))
    if not opener:
        return step
    first_name = (reference.get("first_name") or "").strip()
    if "{first_name}" in opener and not first_name:
        # A handoff with no name to hand off to. Nothing is invented.
        return step

    line = opener.format(first_name=first_name)
    if step.get("channel") == "linkedin":
        note = (step.get("note") or "").strip()
        step["note"] = f"{line} {note}".strip() if note else line
    else:
        body = (step.get("body") or "").strip()
        step["body"] = f"{line}\n\n{body}".strip() if body else line
    step["cross_channel_applied"] = reference.get("mode")
    return step


def expand_step(rec, contact, spec, config, accepted=False, context=None,
                campaign=None):
    """The finished step: a real subject and body, or a real note."""
    key = lint.contact_key(contact)
    stored = ((rec.get("cadence") or {}).get(key) or {}).get(spec["key"]) or {}

    if spec.get("generated"):
        # A GENERATED STEP'S WORDS LIVE UNDER `body` ON EMAIL AND `note` ON
        # LINKEDIN, and this asked only about `body`. So every generated
        # LinkedIn step returned None however well written it was, and the
        # branch below that DOES read a note was reachable only for the
        # literal key `day3` - the old cadence's connection request.
        #
        # Under `productive_li_heavy_v1` the LinkedIn steps are `li1`..`li6`.
        # `li1` survived because it names a template and falls through to the
        # else branch; li2..li6 are generated and have no template, so they
        # vanished from every timeline even with all six notes written on the
        # record. Measured 2026-09-14 on `ogpartner-dk`: six notes stored,
        # one step surfaced.
        #
        # That is what deadlocked HeyReach. The graph is written once and
        # needs every message, `approve` walks the timeline, and the timeline
        # had nothing to approve.
        written = stored.get("body") if spec.get("channel") == "email" \
            else stored.get("note")
        if not (written or "").strip():
            return None                     # phase 5 has not written it yet
        step = dict(stored)
        step.setdefault("channel", spec.get("channel") or "email")
        step["generated"] = True
    elif ((stored.get("note") or "").strip()
          and (stored.get("generated")
               or (stored.get("approval") and not stored.get("template")))):
        # A WRITTEN NOTE BEATS THE TEMPLATE IT WAS MEANT TO REPLACE, on a
        # step the SEQUENCE calls a template. This is the client having asked
        # for `linkedin_connection_note.mode: llm` against a step like the
        # balanced cadence's `day3`, which names `linkedin_intro` and is not
        # marked generated: the model wrote a note, and re-rendering the
        # template over it would throw away the words somebody paid for.
        #
        # Previously spelled `spec["key"] == "day3"`, which was the old
        # cadence's connection request and matched nothing under
        # `productive_li_heavy_v1`. The condition is the stored note, not the
        # key it happens to sit on.
        #
        # AND IT IS NOT THE `generated` FLAG EITHER. That flag says a MODEL
        # wrote the words, and this branch was reading it as "somebody wrote
        # words worth keeping" - which is nearly the same thing right up
        # until the words come from the operator.
        #
        # The CONTROL arm is exactly that case. `build_control_cohort.py`
        # installs the client's own validated fallback copy onto li1..li5 and
        # approves it, and li1 names the template `linkedin_intro` - so this
        # branch re-rendered the template straight over the operator's
        # approved sentence, the fingerprint moved, and the approval gate
        # refused every contact in the cohort. The copy somebody actually
        # chose was the one thing being thrown away.
        #
        # SO: an approved note that is NOT ITSELF A TEMPLATE EXPANSION beats
        # the template. The `template` key is what tells them apart -
        # `approve.approve_step` copies it onto the slot when the approved
        # step came from one, and nothing writes it otherwise.
        #
        # That distinction is load-bearing and keeps the property this whole
        # mechanism exists for. A note stored BECAUSE a template rendered it
        # still re-renders, so editing that template still moves the
        # fingerprint and still drops the approval - which is the point
        # `approval.is_approved` makes in its own docstring. Only a note that
        # was never a template's output is protected from one.
        step = dict(stored)
        step["channel"] = spec["channel"]
        step["generated"] = bool(stored.get("generated"))
    else:
        name = spec["template"]
        if accepted and spec.get("variant_if_accepted"):
            name = spec["variant_if_accepted"]
        step = dict(stored)
        step.update(render(TEMPLATES[name], template_vars(rec, contact, config)))
        step["channel"] = spec["channel"]
        step["template"] = name
        step["generated"] = False

    # The wording, after the template and before the cross-channel opener,
    # so a variant's own copy is what the opener is prepended to. Sticky on
    # what the stored step already recorded, so approving a draft fixes the
    # variant as well as the words.
    entry = variant_for(spec, campaign, key, recorded=stored.get("variant_id"),
                        config=config)
    if entry is not None:
        from . import variants

        step = variants.apply_to_step(step, entry)

    step["day"] = spec["day"] + track_offset(contact, config)
    step["requires"] = spec.get("requires")
    return apply_cross_channel(step, context)


def _context_for(rec, contact, spec, config, workspace, built_so_far,
                 campaign=None, referenced=None):
    """The cross-channel context for one step, or None if it cannot be built.

    Deferred import: `touch` reads a timeline and this module builds one, so
    importing it at module level would be a cycle. Doing it here also means a
    caller that never asks for cross-channel copy never loads the module.

    The partial timeline built so far is passed through rather than rebuilt.
    `touch.history` needs a timeline to know which steps exist, and calling
    `build` from inside `build` would recurse.
    """
    from . import touch

    try:
        return touch.context(rec, contact, spec["channel"], spec["key"],
                             spec["day"] + track_offset(contact, config),
                             workspace, timeline=dict(built_so_far),
                             config=config, campaign=campaign,
                             already_referenced=referenced)
    except Exception:                                    # noqa: BLE001
        # A context that cannot be built is a context that licenses nothing.
        # Failing closed here is the whole point: an exception must not turn
        # into a message that references a touch nobody verified.
        return None


def channel_conflicts(steps):
    """Never two channels on the same day for the same person."""
    seen = {}
    clashes = []
    for key, step in steps.items():
        day = step.get("day")
        if day in seen and seen[day] != step.get("channel"):
            clashes.append(day)
        seen[day] = step.get("channel")
    return clashes


def cross_channel_leaks(steps):
    """A step that names the other channel without evidence that it happened.

    This used to be simpler: any mention at all was a leak, because nothing
    could establish that a cross-channel touch had occurred and so no mention
    could be true. `src/touch.py` establishes it now, so the rule changes from
    "never mention the other channel" to "never mention it without a licence".

    That is a stricter guard, not a looser one. It still catches every
    unlicensed mention, and it additionally catches two things the old version
    could not:

      - a licensed step whose copy names somebody other than the person the
        evidence names, which is the failure that would put a real prospect in
        front of a colleague who never wrote to them
      - a mention on a step carrying a context that *refused*, which is what a
        prompt-injected or hand-edited body would look like

    A step with no context at all is treated as unlicensed, so nothing that
    skips the context path can smuggle a mention through.
    """
    leaks = []
    for key, step in steps.items():
        context = step.get("cross_channel") or {}
        licensed = bool(context.get("may_reference"))
        reference = context.get("reference") or {}

        if step.get("channel") == "linkedin":
            text = (step.get("note") or "").lower()
            found = [p for p in NOTE_MENTIONS_EMAIL if p in text]
            what = "note mentions"
        else:
            text = f"{step.get('subject', '')} {step.get('body', '')}".lower()
            found = [p for p in EMAIL_MENTIONS_LINKEDIN if p in text]
            what = "email mentions"

        if not found:
            continue
        if not licensed:
            leaks += [f"{key}: {what} {p} with no confirmed cross-channel "
                      f"touch behind it" for p in found]
            continue
        # Licensed. The name in the copy still has to be the name on the
        # evidence - a licence to reference Anna is not a licence to
        # reference anybody.
        named = (reference.get("first_name") or "").strip().lower()
        if named and named not in text:
            leaks.append(
                f"{key}: {what} the other channel but does not name "
                f"{reference.get('first_name')}, who is who the evidence "
                "names")
    return leaks


# -------------------------------------------------------------- the state

def event_log(rec):
    return rec.get("events") or []


def accepted_connection(rec, contact=None):
    key = lint.contact_key(contact) if contact else None
    for e in event_log(rec):
        if events.is_acceptance(e) and (key is None or e.get("contact") == key):
            return True
    return False


def pause_state(rec, config=None):
    """Whether this whole account is stopped, and why.

    Four sources, most final first:

      1. an account suppression - a company-wide do-not-contact, permanent
      2. `rec["paused"]` - the reversible hold `accountpolicy.apply_reply`
         writes when a reply's policy holds the account
      3. a booked meeting anywhere at this company
      4. a reply in the log that never went through that path

    (4) is a safety net, and it used to be the whole rule: *any* reply
    paused the company. It now asks the same policy, so a reply classified
    "not interested" no longer stops three colleagues who were never
    written to. An unclassified reply still resolves to a hold, so the net
    still catches everything it caught before that nobody has read.

    (3) IS THE ACCOUNT, NOT THE PERSON, AND IT HAD NO CONSUMER AT ALL.
    `events.MEETING_MARKED` was read by `hygiene`, `outcomes`, `report`,
    `signals`, `tagsync` and `variants` - six reporting consumers - and by
    nothing on any send or plan path. So a meeting booked with the COO did
    not stop the cold sequence to the CFO, and the only thing that stopped
    it was whatever the reply beside it happened to be classified as. A
    meeting is the strongest possible statement that this account is being
    worked by a human, and cold outreach continuing into one is the
    "agency that does not talk to itself" failure at its most expensive.

    Derived rather than written, for the same reason (4) is: nothing in
    `src/` writes `MEETING_MARKED` today - a person or the UI does - so a
    transition keyed to a writer would have no writer. `accountpolicy` stays
    the authority on what an event MEANS; this reads the event.
    """
    from . import accountpolicy

    suppression = rec.get("suppression") or {}
    if suppression.get("unsubscribed"):
        return {"since": suppression.get("since"),
                "reason": suppression.get("reason") or "account_suppressed",
                "outcome": suppression.get("reason"),
                "channel": None, "by": suppression.get("by"),
                "permanent": True}
    if rec.get("paused"):
        return rec["paused"]
    review = rec.get("review") or {}
    if review.get("open"):
        return {"since": review.get("since"), "reason": "review_required",
                "outcome": review.get("reason"), "channel": None,
                "by": review.get("by")}
    for e in event_log(rec):
        if e.get("type") != events.MEETING_MARKED:
            continue
        return {"since": e.get("at"), "reason": events.MEETING_MARKED,
                "outcome": "meeting_booked", "channel": e.get("channel"),
                "by": e.get("contact"),
                "why": "a meeting is booked at this company, so nothing cold "
                       "goes to anybody here"}
    # One classification per contact who replied, not one per reply event:
    # `classify_outcome` walks the log, so asking it inside a loop over the
    # log is quadratic on a record with a long history.
    seen = {}
    for e in event_log(rec):
        if not events.is_reply(e):
            continue
        who = e.get("contact")
        if who not in seen:
            seen[who] = accountpolicy.effects(
                accountpolicy.classify_outcome(rec, who), config)
        if seen[who]["account"] != accountpolicy.CONTINUE:
            return {"since": e.get("at"), "reason": e.get("type"),
                    "outcome": seen[who]["outcome"],
                    "channel": e.get("channel"), "by": who}
    return None


CHANNEL_OF = {"email_reply": "email", "linkedin_reply": "linkedin",
              "connection_accepted": "linkedin"}


def record_event(rec, kind, contact_key=None, at=None):
    """Append a cadence event and derive the company pause. Never deletes.

    The store is src/events.py, so a reply that arrives from a provider webhook
    and a reply recorded by hand end up in the same stream and pause the same
    way.
    """
    if kind not in REPLY_EVENTS + (ACCEPT_EVENT,):
        raise CadenceError(f"unknown event: {kind}")
    entry = events.record(rec, kind, contact_key=contact_key, at=at,
                          channel=CHANNEL_OF.get(kind))
    if entry is None:
        return None                       # already recorded, nothing changes
    if kind in REPLY_EVENTS:
        # Same policy, same single entry point. A reply recorded by hand is
        # unclassified like one from a webhook, so it holds the company -
        # and if somebody classifies it later, `replies.apply` narrows it.
        #
        # TASK-030 moved the provider-webhook path to `inbound.handle`
        # (classify first, then pause), so `events.apply_reply_policy`
        # returns None. But the hand-recorded path is NOT a webhook: an
        # operator recording a reply is saying "this is a real reply," so
        # the conservative UNKNOWN outcome applies immediately.
        from . import accountpolicy
        accountpolicy.apply_reply(
            rec, contact_key, accountpolicy.UNKNOWN, config=None,
            at=entry.get("at"), channel=entry.get("channel"),
            reason=entry.get("type"), workspace=rec.get("client"))
    else:
        store.log(rec, "event", f"{kind} from {contact_key or 'someone'}")
    return entry


def paused_domains(recs, client=None):
    """(client, domain) pairs that are paused anywhere in the queue."""
    out = set()
    for rec in recs:
        if pause_state(rec):
            out.add((rec.get("client"), rec.get("domain")))
    return out


# ----------------------------------------------------------- the timeline

def build(rec, config=None, recs=None, paused_set=None, workspace=None,
          campaign=None, cross_channel=False):
    """The whole company's timeline, with a status on every step.

    Statuses: pending, eligible, paused, pushed, blocked, waiting.

    `paused_set` is the set of paused (client, domain) pairs, computed once by
    a caller that is building many timelines. Without it this walks every
    record to answer the same question for every record, which is quadratic:
    at 5,000 domains that was 25 million checks and fifteen seconds, and it
    grows with the square of the batch. A single caller-side call to
    paused_domains() removes it entirely.
    """
    config = config or clients.load(rec.get("client"))
    paused = pause_state(rec)
    if not paused and (paused_set is not None or recs):
        if paused_set is None:
            paused_set = paused_domains(recs)
        if (rec.get("client"), rec.get("domain")) in paused_set:
            paused = {"reason": "another record for this company is paused"}

    # The campaign's own sequence, or the one every campaign ran. Read
    # once for the record rather than per contact: it is the same answer
    # for all of them and validating it five times is five chances to
    # disagree with itself.
    timeline = {}
    for contact in rec.get("contacts") or []:
        # Resolved per contact, because a contact-unit experiment gives two
        # people at one company different sequences. For the account unit -
        # the default - every contact here resolves to the same arm, and
        # the repeat is a dictionary lookup.
        sequence = steps_for(campaign, config, rec, contact)
        key = lint.contact_key(contact)
        accepted = accepted_connection(rec, contact)
        steps = {}
        # Which confirmed touches this contact's cadence has already named.
        # Carried across steps so the reference is made once rather than in
        # every message after it.
        referenced = set()
        for spec in sequence:
            # The cross-channel context is built per step, because what is
            # confirmed depends on where in the cadence this step sits: a day-3
            # LinkedIn note may reference a day-1 email, and a day-1 email may
            # reference nothing. Off by default so that every existing caller
            # gets exactly the timeline it got before.
            context = None
            if cross_channel and workspace:
                context = _context_for(rec, contact, spec, config, workspace,
                                       steps, campaign, referenced)
            step = expand_step(rec, contact, spec, config, accepted=accepted,
                               context=context, campaign=campaign)
            if step is None:
                # A generated step whose content has not been written yet.
                # When the step carries a precondition (requires), the step
                # must still appear in the timeline: a step whose requires
                # is unmet is waiting, not absent. Omitting it hides the
                # step from approval and from the campaign graph, which is
                # the deadlock that blocks HeyReach staging.
                if spec.get("requires"):
                    step = {"channel": spec["channel"],
                            "day": spec["day"] + track_offset(contact, config),
                            "requires": spec["requires"]}
                else:
                    continue
            if step.get("cross_channel_applied"):
                reference = (context or {}).get("reference") or {}
                referenced.add(f"{reference.get('channel')}:"
                               f"{reference.get('step')}")
            stored = ((rec.get("cadence") or {}).get(key) or {}).get(spec["key"]) or {}
            step["status"] = status_for(rec, contact, spec, step, stored,
                                        paused=paused, accepted=accepted,
                                        config=config, sequence=sequence)
            steps[spec["key"]] = step
        timeline[key] = steps
    return {"paused": paused, "contacts": timeline}


def status_for(rec, contact, spec, step, stored, paused, accepted,
               config=None, sequence=None):
    # A terminal state is returned as it stands. Recomputing a status for a
    # step that has already been sent, confirmed or cancelled would let a
    # rebuild move it, and `stepstate.reconcile` documents that rule as the
    # point of the state machine. The literal here was `== "pushed"`, which
    # is the only terminal state anything writes today; reading the set
    # means a `confirmed` step stays confirmed the day something starts
    # writing one.
    if stepstate.is_terminal(stored.get("status")):
        return stored["status"]              # already sent, never sent again
    if paused:
        return "paused"
    if rec.get("state") in lint.UNSHIPPABLE:
        return "blocked"
    # Channel availability outranks the dependency. A LinkedIn step that
    # requires an accepted connection, for a contact we have no profile for,
    # used to report `waiting` - which reads to a reviewer as "this will happen
    # later" when it can never happen at all: there is nobody to send the
    # connection request to. Blocked is the truthful answer, and it is the one
    # the cross-channel check agrees with.
    if spec["channel"] == "linkedin" and not contact.get("linkedin"):
        return "blocked"
    # THE LINKEDIN BRANCH, ASKED OF THE ONE MODULE THAT HOLDS IT.
    #
    # This was `spec["requires"] == ACCEPT_EVENT and not accepted` - a
    # boolean, which cannot tell "they declined" from "nobody has read
    # whether they accepted" and answers `waiting` to both. It also had no
    # answer at all for the cadence this client now runs: an open profile
    # that needs no request, a message that needs a connection the provider
    # reports, and an InMail fallback that must be HELD rather than skipped
    # while nothing can send one.
    #
    # `linkedinstate.plan_step` is that branch and is the only place it
    # lives. `waiting` and `skipped` are the existing vocabulary and keep
    # their meanings, so `eligibility._dependency` and
    # `eligibility._linkedin_checks`, which both read `waiting`, are
    # unchanged.
    if spec["channel"] == "linkedin":
        move = linkedinstate.plan_step(rec, contact, spec, steps=sequence,
                                       config=config)
        step["linkedin_state"] = move["state"]
        step["linkedin_action"] = move["action"]
        if move["status"] == linkedinstate.SKIP:
            step["skipped_reason"] = move["why"]
            return "skipped"
        if move["status"] == linkedinstate.WAIT:
            step["waiting_on"] = move["why"]
            return "waiting"
    if spec["channel"] == "email":
        # MX policy suppresses the CHANNEL, not the contact: the step stays in
        # the timeline, named and auditable, and LinkedIn is untouched.
        from . import mx
        allowed, why = mx.allows_email(contact, config)
        if not allowed:
            step["blocked_by"] = [mx.block_reason(contact, config) or "mx"]
            step["skipped_reason"] = why
            return "skipped"
    # `lint.sendable`, not `contact["sendable"]`. The stored field is a
    # projection that SCHEMA.md warns about by name; `verification.is_sendable`
    # is the one authority, and everything else in the pipeline - channels,
    # eligibility, the payload gate - already asks it. Reading the flag here
    # meant this one place could disagree with all of them: a stale True
    # reached `push.collect` and died on an assertion at payload-build time,
    # and a stale or absent False silently blocked a contact that had cleared
    # verification.
    if spec["channel"] == "email" and not lint.sendable(contact):
        return "blocked"
    if spec["channel"] == "linkedin" and not contact.get("linkedin"):
        return "blocked"
    # Both channels lint, after expansion, through the same door. A template
    # step that expanded into something unsendable is not campaign-ready just
    # because nobody generated it.
    failures = lint.check_step(rec, lint.contact_key(contact), step)
    if failures:
        step["blocked_by"] = failures
        return "blocked"
    # Lint clean is not permission. A human approves the exact words, and an
    # edit after approval puts the step back here.
    if not approval.is_approved(rec, lint.contact_key(contact), spec["key"], step):
        return "unapproved"
    return "eligible"


def due(timeline, day):
    """Steps whose scheduled day has arrived. Deterministic: no wall clock."""
    out = []
    for key, steps in timeline["contacts"].items():
        for step_key, step in steps.items():
            if step["status"] == "eligible" and step["day"] <= day:
                out.append({"contact": key, "step": step_key, **step})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadence")
    p.add_argument("--day", type=int, default=21, help="batch day to evaluate")
    p.add_argument("--id", action="append", dest="ids")
    a = p.parse_args(argv)

    recs = store.load()
    for rec in recs:
        if a.ids and rec["id"] not in a.ids:
            continue
        try:
            timeline = build(rec, recs=recs)
        except clients.ConfigError as e:
            print(f"{rec['id']}: skipped, {e}")
            continue
        head = f"{rec['id']} ({rec.get('domain')})"
        if timeline["paused"]:
            head += f"  PAUSED: {timeline['paused'].get('reason')}"
        print(f"\n{head}")
        for key, steps in timeline["contacts"].items():
            print(f"  {key}")
            for step_key in (s["key"] for s in STEPS):
                step = steps.get(step_key)
                if not step:
                    continue
                detail = step.get("subject") or step.get("note") or ""
                print(f"    day {step['day']:>2}  {step['channel']:<9} "
                      f"{step['status']:<9} {detail[:48]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
