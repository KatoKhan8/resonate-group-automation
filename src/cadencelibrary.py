#!/usr/bin/env python3
"""The named sequences a client may choose between.

WHY THIS IS A LIBRARY AND NOT A CLIENT FILE. `cadence.steps_for` already
resolves a sequence from the campaign, then the client's named cadence, then
the constant - so selecting a strategy is already configuration. What the
client file cannot hold is the sequence ITSELF: `clients.parse` reads scalars
and inline scalar lists, and a step is a mapping. An inline list of mappings
comes back split on its commas.

So the sequences live here, once, and a client file picks one by name:

    cadence: productive_li_heavy_v1

Comparing two intensities is then a one-line edit to that file, which is the
property that matters - the alternative is a sequence pasted into several
modules, which is what "do not hard-code the cadence" is about.

WHAT A LINKEDIN STEP MAY SAY. `requires` already existed and gated a step on
`connection_accepted`. The LinkedIn-heavy cadence needs more than one branch,
so a step may also carry:

    linkedin_action   connect | message | inmail | open_profile_message
    requires          the prospect state this step needs, or absent
    capability        a PROVIDER capability this step depends on

THE MESSAGES ARE GENERATED, NOT TEMPLATED. Only two LinkedIn templates exist
- `linkedin_intro`, the connection note, and `linkedin_followup` - and four
messages that each have a different job cannot come from one of them. A first
version named five templates nothing defines, which renders as a KeyError the
moment a timeline is built: a cadence that looks configured and crashes.

`capability` is the load-bearing one. Whether HeyReach can detect an Open
Profile, or send an InMail, or report that a connection request was declined,
is not yet established - it is being measured. A step naming a capability the
provider has not been proven to support must be HELD by the state machine,
never silently skipped and never executed as if it worked. A cadence that
quietly drops its InMail fallback reports eleven touches and sends ten.
"""

# ---------------------------------------------------------------- states

OPEN_PROFILE = "open_profile"
CONNECTED = "connected"
CONNECTION_ACCEPTED = "connection_accepted"
CONNECTION_NOT_ACCEPTED = "connection_not_accepted"

# ---------------------------------------------------------- capabilities
#
# Named so a step can say what it depends on and the planner can refuse
# rather than guess. None of these is proven on HeyReach yet.

CAP_OPEN_PROFILE = "linkedin.open_profile_message"
CAP_INMAIL = "linkedin.inmail"
CAP_CONNECT = "linkedin.connection_request"
CAP_MESSAGE = "linkedin.message"

# --------------------------------------------------------- email ladders
#
# Each sequence names which ladder its email steps resolve against. The
# ladder is looked up by name in LADDER_REGISTRY; `generate._resolve_ladder`
# reads the `_ladder` attribute off the sequence tuple.
#
# RUNG 5 IS UNCHANGED, AND THAT IS THE PART OF THIS WARNING THAT BINDS. It is
# the production ladder for `productive_li_heavy_v1`, EmailBison campaign 481
# is staged with nine real leads carrying approved subject_5/body_5, and
# changing rung 5 would silently rewrite the final email of a live sequence.
#
# RUNGS 1, 3 AND 4 DID CHANGE, 2026-09-14, deliberately. Rung 3 had no way to
# do its job: measured by rendering the real prompt, the word "Productive" did
# not appear in it once, so "new value" could only be argued from
# `angle_wording` and the model reached for the same phrase every rung. The
# `product:` block in the client config is the missing input and these two
# rungs are what consume it - rung 1 says who is writing, rung 3 says what
# the thing is. Rung 4 asked for "the shortest message in the sequence" and
# the forty-word floor refused what that produced; em4 was NOT WRITTEN for
# several records across multiple regeneration attempts.
#
# CONSEQUENCE, STATED RATHER THAN DISCOVERED: 481's nine leads carry copy
# generated against the OLD rungs 1, 3 and 4. They are not rewritten by this
# change - stored copy is stored - but regenerating them will now produce
# materially different em1, em3 and em4, and it must happen before 481 sends.
# The campaign is paused and `EMAIL_ACTIVATE` is not in
# `providerwrites.SUPPORTED`, so nothing can send in the meantime.
EMAIL_FIVE_LADDER = (
    "Relevance, and who is writing. Why you are writing to THIS person at "
    "THIS company, in their own operational language, and one clause saying "
    "what the product is so the question that follows has a sender behind "
    "it. One question they can answer in a line.",
    "A different angle from the first email. Not the same argument rephrased: "
    "a different part of how the business runs, and a different question.",
    "SAY WHAT THE PRODUCT IS AND WHAT IT IS WORTH. Use the product's name "
    "in the message, and say in one line what it joins up - only the "
    "capabilities in `product.capabilities` that fit this person's angle - "
    "and give one concrete consequence a team their size would recognise: "
    "what changes when this is visible while the work is running rather "
    "than reconstructed afterwards.",
    # RUNG 4 CHANGED, 2026-09-14. "The shortest message in the sequence"
    # invited a twenty-word body and the forty-word floor refused it. em4
    # was NOT WRITTEN for several records across multiple regeneration
    # attempts. The fix is in the brief, not the floor: ask for a focused
    # follow-up with a distinct argument rather than the shortest message.
    "A follow-up that makes a DIFFERENT argument from every email before it. "
    "One focused idea and one question - no recap of earlier messages and no "
    "new pitch beyond the single point this message carries.",
    "Close the loop. Give them an easy no, make no new pitch, ask for nothing "
    "beyond permission to stop.",
)

# The eight-step ladder, read off the client's best-performing sequence
# (12.23% reply rate at 8 steps, n=17,690). Rungs 1-4 match the five-step
# ladder; rungs 5-7 are new; rung 8 is the breakup moved from rung 5.
EMAIL_EIGHT_LADDER = (
    "Relevance, and who is writing. Why you are writing to THIS person at "
    "THIS company, in their own operational language, and one clause saying "
    "what the product is so the question that follows has a sender behind "
    "it. One question they can answer in a line.",
    "A different angle from the first email. Not the same argument rephrased: "
    "a different part of how the business runs, and a different question.",
    "SAY WHAT THE PRODUCT IS AND WHAT IT IS WORTH. Use the product's name "
    "in the message, and say in one line what it joins up - only the "
    "capabilities in `product.capabilities` that fit this person's angle - "
    "and give one concrete consequence a team their size would recognise: "
    "what changes when this is visible while the work is running rather "
    "than reconstructed afterwards.",
    # RUNG 4 CHANGED, 2026-09-14. "The shortest message in the sequence"
    # invited a twenty-word body and the forty-word floor refused it. em4
    # was NOT WRITTEN for several records across multiple regeneration
    # attempts. The fix is in the brief, not the floor: ask for a focused
    # follow-up with a distinct argument rather than the shortest message.
    "A follow-up that makes a DIFFERENT argument from every email before it. "
    "One focused idea and one question - no recap of earlier messages and no "
    "new pitch beyond the single point this message carries.",
    "The cost of the current way of doing it. What the existing approach "
    "actually spends in time, risk or reconstruction - not a feature pitch, "
    "a number they can recognise.",
    "What a team their size found when they looked. The pattern, not the "
    "product: what changed when visibility arrived during the work rather "
    "than after it.",
    "The referral ask. Am I talking to the right person about this, and who "
    "should I be talking to. This is the rung that feeds stakeholder "
    "escalation in ACCOUNT-OUTREACH.md.",
    "Close the loop. Give them an easy no, make no new pitch, ask for nothing "
    "beyond permission to stop.",
)

# Rung one is the CONNECTION REQUEST, which is a different object from a
# message: it has no subject, it is read beside a profile photo, and asking a
# question that needs thought in it is how it gets ignored. Rungs two onward
# are messages to somebody who accepted.
#
# RUNG 4 CHANGED, 2026-09-14. It read "the use case" and could not be written
# to: nothing in the prompt said what the product was, so the model answered
# with an offer to explain - "i'd love to share how teams like yours have
# improved their project visibility" - rather than an explanation. It is now
# the rung that names the product, and it consumes the client config's
# `product:` block.
#
# RUNGS 1-6 REWRITTEN, 2026-09-14, TASK-075. Two defects measured by TASK-064's
# human read of all 15 contacts:
#
#   1. The connection note never said who is writing. No sender name, no
#      company, no role. A stranger received an anonymous compliment and an
#      invitation. The operator's hand-written fallback - "i work with agencies
#      on project profitability" - was better, and it is the floor to beat.
#      Rung 1 now REQUIRES sender identity: who you are and what you do. The
#      prompt passes `sender_identity` from the client config; when it is
#      empty the note must still say what the sender does, never emit an empty
#      slot, and never invent a name.
#
#   2. The sequence did not progress. All six rungs collapsed into one: ask
#      about profitability. Three pushable contacts each received four
#      messages asking variations of the same question. Each rung now says
#      what the PREVIOUS rung established so the next one can build on it. A
#      rung whose brief can be satisfied by "ask a discovery question" will
#      be, and the ladder now prevents that by naming what is already spent.
LINKEDIN_DEFAULT_LADDER = (
    # RUNG 1: THE CONNECTION REQUEST. Must say WHO is writing.
    # TASK-087: The connection request is a fixed form (LinkedIn constrains
    # it), so the brief describes the form AND the job together. Variant
    # generation does not apply to connection requests.
    "A connection request note. Say who you are in one clause - your name "
    "and what you do, or what you work on if no sender detail is available. "
    "Then one line on why you are writing to them specifically, in the "
    "operational language of their angle. No ask beyond connecting, and no "
    "question that needs a considered answer. The recipient must learn WHO "
    "is contacting them from this note alone.",
    # RUNG 2: FIRST MESSAGE. Builds on the connection note.
    # TASK-087: The brief used to say "this message asks a question about
    # how they handle one specific part of their operation today". That
    # prescribed the FORM (a question) and every variant approach collapsed
    # to the same structure: opening=question, cta=question. The fix
    # separates the JOB (establish their current approach to X) from the
    # FORM (which the variant approach controls).
    # TASK-131: The sender was identified in the connection note. Do not
    # re-introduce them.
    "Establish how they handle one specific part of their operation today. "
    "Pick an angle DIFFERENT from the one the connection note used. If the "
    "note named their hiring pipeline, pick their project margin; if it "
    "named profitability, pick resourcing visibility. The connection note "
    "already said who you are and why you connected. Do not re-introduce "
    "yourself - the recipient already knows.",
    # RUNG 3: SECOND MESSAGE. Builds on both previous messages.
    # TASK-087: The brief used to say "this one names the consequence"
    # (prescriptive) and referenced the previous rung's form ("The first "
    # message asked how they handle something"). Now describes only the job.
    "Name the consequence of not having visibility - what goes wrong, what "
    "gets rebuilt after the fact rather than seen during the work. Pick a "
    "DIFFERENT operational angle from both the connection note and the "
    "first message. Do not re-introduce yourself - the sender was identified "
    "in the connection note.",
    # RUNG 4: THE PRODUCT RUNG. The recipient learns what is being offered.
    # TASK-087: The brief used to say "it is a statement, not a question: "
    # "by now they have been asked three times and told nothing". That "it "
    # "is a statement" prescribed the form. The job is to name the product.
    # The reference to the PREVIOUS steps is deliberate and is TASK-075's
    # progression fix - it is what stops all six rungs collapsing into one
    # discovery question. TASK-087 removed form instructions from the rungs so
    # a variant approach could control structure, and stripped this reference
    # with them. It is restored here WITHOUT a form instruction: it says what
    # the earlier steps ESTABLISHED, not what shape this one must take.
    "The previous steps established the problem and have named no solution. "
    "Use the product's name and say in one line what it joins up, choosing "
    "only the capabilities in `product.capabilities` that fit this person's "
    "angle. This is the rung where the recipient learns what they are being "
    "offered. Evidence belongs here if there is any; if there is none, "
    "describe the pattern as ours rather than theirs. Do not re-introduce "
    "yourself.",
    # RUNG 5: FINAL FOLLOW-UP. Different from everything before.
    # TASK-087: The brief used to say "in one line and one question" "
    # (prescribing the form). Now describes only the job.
    "Add one new angle no previous step touched - a different part of the "
    "business, or a different consequence. No recap of the previous "
    "messages. Do not re-introduce yourself.",
    # RUNG 6: THE CLOSE.
    # TASK-131: The close must give the prospect a graceful exit AND ask
    # whether somebody else owns this. The fallback's connected_4 is the
    # target shape: "happy to leave it here if the timing is wrong. is
    # there someone else who owns this?" The brief states the JOB, not
    # the form, per TASK-087.
    "Close the loop. The sequence has done its work. Give them a graceful "
    "way to decline - make it easy to say no. Ask whether somebody else "
    "owns this. No new pitch, no summary of what was said.",
)

LADDER_REGISTRY = {
    "email_five": EMAIL_FIVE_LADDER,
    "email_eight": EMAIL_EIGHT_LADDER,
    "linkedin_default": LINKEDIN_DEFAULT_LADDER,
}

# ----------------------------------------- thread-reply patterns per ladder
#
# Each ladder may state which of its rungs are same-thread follow-ups. A
# follow-up uses the provider's `thread_reply` flag rather than a new subject:
# the step carries an `email_subject` EVEN WHEN `thread_reply` is True, so
# the flag is the mechanism and omitting the subject is NOT how follow-up is
# expressed.
#
# THE STARTING HYPOTHESIS, read off campaign 352 (the estate's largest at
# 92,806 sent): F, T, F, T, F across five parents. TASK-080 measures whether
# this shape actually performs, so these patterns are CONFIGURABLE and must
# not be hardcoded as universal. A client config's `email_sequence` block may
# override with its own `thread_reply_pattern` list.
#
# A follow-up rung's brief must ALSO tell the model it is continuing a
# thread, or it writes another cold open and the flag is the only thing that
# changed. `FOLLOWUP_ADDENDUM` is appended to the rung's purpose in the
# prompt when `thread_reply` is True.
THREAD_REPLY_PATTERNS = {
    "email_five": (False, True, False, True, False),
    "email_eight": (False, True, False, True, False, True, False, True),
}

# "Be short." WAS HERE AND IS DELIBERATELY GONE. TASK-080 measured the
# estate: same-thread follow-ups that earned replies average 857 characters
# against 571 for new threads - the follow-ups that worked are LONGER, not
# shorter. That is survivorship (it is measured on emails that GOT replies,
# so it does not show that length CAUSES replies), which is exactly why the
# instruction is removed rather than inverted. We do not tell the model to be
# long either. "Add one thought" carries the intent without asserting a
# length nobody has evidence for.
FOLLOWUP_ADDENDUM = (
    " THIS IS A SAME-THREAD FOLLOW-UP: you are continuing an existing "
    "conversation, not starting a new one. Add one thought. Do "
    "not repeat what the earlier email said. Do not re-introduce the sender "
    "from scratch. The email subject is carried for the provider's threading "
    "mechanism but this message lands in the same thread as the previous one."
)


def thread_reply_for(ladder_name, ordinal):
    """Whether this rung is a same-thread follow-up, or None when unknown.

    None when the ladder has no declared pattern or the ordinal is past its
    end. A rung past the ladder is nobody's decision and must not be guessed.
    """
    if not ladder_name or not ordinal:
        return None
    pattern = THREAD_REPLY_PATTERNS.get(ladder_name)
    if not pattern or ordinal > len(pattern):
        return None
    return bool(pattern[ordinal - 1])


def purpose_with_thread(ladder_name, ordinal, base_purpose=None):
    """The rung's brief, with the follow-up addendum when it is a follow-up.

    Returns the base purpose unchanged for new-thread rungs. For follow-ups,
    appends `FOLLOWUP_ADDENDUM` so the model knows it is continuing a thread.
    `base_purpose` may be supplied when the caller already resolved it; when
    absent, the ladder is looked up directly.
    """
    if base_purpose is None:
        ladder = LADDER_REGISTRY.get(ladder_name or "") or ()
        base_purpose = ladder[ordinal - 1] if ordinal and ordinal <= len(ladder) else None
    if not base_purpose:
        return base_purpose
    if thread_reply_for(ladder_name, ordinal):
        return base_purpose + FOLLOWUP_ADDENDUM
    return base_purpose


# The operator's initial production hypothesis, 2026-09-13: roughly five email
# touches and six LinkedIn activities - four of them messages - across three
# weeks. It is a hypothesis to measure, not a rule: `productive_balanced_v1`
# below exists to be compared against it.
#
# Day 1 carries two steps on purpose. Equal days are allowed; only a step
# EARLIER than its predecessor is refused.
PRODUCTIVE_LI_HEAVY_V1 = (
    # Day 1 - both channels open together.
    {"key": "li1", "day": 1, "channel": "linkedin",
     "linkedin_action": "connect", "capability": CAP_CONNECT,
     "template": "linkedin_intro",
     # The Open Profile branch: where the provider says a direct message needs
     # no connection, the first action should not be spent asking for one.
     "alternative": {"requires": OPEN_PROFILE,
                     "linkedin_action": "open_profile_message",
                     "capability": CAP_OPEN_PROFILE,
                     "generated": True}},
    {"key": "em1", "day": 1, "channel": "email", "generated": True},

    {"key": "li2", "day": 3, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "em2", "day": 4, "channel": "email", "generated": True},

    # The fork. Connected, this is the second message; unaccepted after the
    # wait window, it is the InMail fallback - and an InMail is NOT sent
    # merely because the request has not been accepted yet.
    {"key": "li3", "day": 6, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True,
     "alternative": {"requires": CONNECTION_NOT_ACCEPTED,
                     "linkedin_action": "inmail", "capability": CAP_INMAIL,
                     "generated": True}},
    {"key": "em3", "day": 8, "channel": "email", "generated": True},

    {"key": "li4", "day": 10, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "em4", "day": 12, "channel": "email", "generated": True},

    {"key": "li5", "day": 15, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "li6", "day": 18, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "em5", "day": 21, "channel": "email", "generated": True},
)

# The shape that ran before: seven steps, email-led. Kept as a named
# alternative so cadence INTENSITY is a comparable variable rather than a
# rewrite - §14 of the operator's brief asks for exactly this pair.
PRODUCTIVE_BALANCED_V1 = (
    {"key": "day1", "day": 1, "channel": "email", "generated": True},
    {"key": "day3", "day": 3, "channel": "linkedin",
     "linkedin_action": "connect", "capability": CAP_CONNECT,
     "template": "linkedin_intro"},
    {"key": "day5", "day": 5, "channel": "email", "template": "persona_pain"},
    {"key": "day8", "day": 8, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "template": "linkedin_followup", "requires": CONNECTION_ACCEPTED},
    {"key": "day10", "day": 10, "channel": "email",
     "template": "comparable_proof",
     "variant_if_accepted": "comparable_proof_short"},
    {"key": "day15", "day": 15, "channel": "email", "generated": True},
    {"key": "day21", "day": 21, "channel": "email", "template": "breakup"},
)

# The eight-step email cadence. TASK-028.
#
# Read off the client's best-performing sequence: 12.23% reply rate at 8
# steps (n=17,690). The waits mirror the best performer's 2/3/2/3/3/3/3/1
# pattern: days 1, 3, 6, 8, 11, 14, 17, 20.
#
# This is email-led with NO LinkedIn steps. The existing li_heavy cadence
# carries six LinkedIn activities; this one carries zero. The comparison
# is sequence LENGTH on the email channel, not total touch count. An
# eight-email cadence alongside six LinkedIn steps would be fourteen
# touches, and the fatigue caps are paced for eleven.
#
# The ladder is `email_eight`, which has eight rungs. Rung 5 is NOT the
# breakup (that is rung 8); the five-step cadence's ladder is unaffected.
PRODUCTIVE_EMAIL_EIGHT_V1 = (
    {"key": "em1", "day": 1, "channel": "email", "generated": True},
    {"key": "em2", "day": 3, "channel": "email", "generated": True},
    {"key": "em3", "day": 6, "channel": "email", "generated": True},
    {"key": "em4", "day": 8, "channel": "email", "generated": True},
    {"key": "em5", "day": 11, "channel": "email", "generated": True},
    {"key": "em6", "day": 14, "channel": "email", "generated": True},
    {"key": "em7", "day": 17, "channel": "email", "generated": True},
    {"key": "em8", "day": 20, "channel": "email", "generated": True},
)

# --------------------------------------------------------- ladder tagging
#
# Each sequence carries the name of the ladder its email steps resolve
# against. `generate._resolve_ladder` calls `ladder_name_for` to look up
# the ladder; sequences absent from this mapping fall through to the
# default ladder in generate.LADDERS.
#
# PRODUCTIVE_LI_HEAVY_V1 uses `email_five` - the same five-rung ladder that
# has been production since the beginning. This is NOT a change: the ladder
# content is identical to generate.EMAIL_LADDER. The tagging just makes it
# explicit so the eight-step cadence can use a different one.
#
# Keyed by cadence NAME, not id(). `cadence.steps_for` runs every sequence
# through `validate_steps`, which returns a new tuple of new dicts - so
# id() never matches through the path production actually uses. The name
# is the canonical identity: `SEQUENCES` is already a name-to-sequence
# mapping and `named()` reads it.
_SEQUENCE_LADDERS = {
    "productive_li_heavy_v1": {"email": "email_five"},
    "productive_balanced_v1": {"email": "email_five"},
    "productive_email_eight_v1": {"email": "email_eight"},
}


def ladder_name_for(sequence, channel):
    """The ladder name this sequence uses for this channel, or None.

    None means 'use the default ladder in generate.LADDERS'. A sequence
    not in the mapping, or a channel it does not name, returns None.

    Matches by step keys - the one thing that survives `validate_steps`.
    `cadence.steps_for` returns a new tuple of new dicts, so id() and
    content equality both fail. Keys are preserved through validation
    and are the identity a step key is: unique within a sequence.
    """
    if sequence is None:
        return None
    keys = tuple(s.get("key") for s in sequence)
    for name, seq in SEQUENCES.items():
        if tuple(s.get("key") for s in seq) == keys:
            mapping = _SEQUENCE_LADDERS.get(name)
            if mapping:
                return mapping.get(channel)
    return None

SEQUENCES = {
    "productive_li_heavy_v1": PRODUCTIVE_LI_HEAVY_V1,
    "productive_balanced_v1": PRODUCTIVE_BALANCED_V1,
    "productive_email_eight_v1": PRODUCTIVE_EMAIL_EIGHT_V1,
}


def named(name):
    """The sequence with this name, or None. Never a near match."""
    return SEQUENCES.get(str(name or ""))


def capabilities_used(steps):
    """Every provider capability this sequence depends on.

    What a planner asks a provider adapter about before it plans anything: a
    sequence whose InMail fallback is unsupported is a different sequence,
    and it should be reported as such rather than discovered a fortnight in.
    """
    found = set()
    for step in steps or ():
        for node in (step, step.get("alternative") or {}):
            if node.get("capability"):
                found.add(node["capability"])
    return sorted(found)


def shape(steps):
    """How many touches, by channel. For reporting a cadence honestly."""
    email = sum(1 for s in steps or () if s.get("channel") == "email")
    linkedin = [s for s in steps or () if s.get("channel") == "linkedin"]
    messages = sum(1 for s in linkedin
                   if s.get("linkedin_action") in ("message",
                                                   "open_profile_message"))
    return {"email": email, "linkedin": len(linkedin),
            "linkedin_messages": messages,
            "total": email + len(linkedin),
            "days": max([int(s.get("day") or 0) for s in steps or ()] or [0])}
