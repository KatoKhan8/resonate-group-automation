#!/usr/bin/env python3
"""The gate. BUILD-SPEC section 6.

Pure functions: nothing here reads or writes the queue and nothing here changes
a record. A generated email lives in a cadence step, keyed by contact slug:

    "cadence": {"petra-horvat": {"day1": {"channel": "email",
                                             "subject": "...", "body": "..."}}}

so the unit of lint is one (record, contact, step). Steps with no body are
templates the cadence expander has not filled yet and are not linted here.

  python -m src.lint          report every generated email, exit 1 on any failure
"""
import argparse
import re
import sys

from . import identity, optout, store

# Section 6.2. Never widen one of these to make a draft pass. Regenerate the draft.
MIN_WORDS = 40
MAX_WORDS = 180
MAX_SUBJECT = 60          # "under 60 characters": 59 passes, 60 fails

# A THREAD REPLY HAS ITS OWN RANGE, BECAUSE A FLOOR THAT FORBIDS BREVITY AND A
# SPEC THAT DEMANDS IT CANNOT BOTH BE SATISFIED.
#
# Operator ruling, 2026-10-01, asked for and given in these words: "Thread-reply
# steps (em2, em4, per `thread_reply_rungs`) get their OWN range of 15 to 60
# words in the body, excluding the signature and the opt-out line. em1, em3 and
# em5 keep the existing 40-word minimum."
#
# WHAT IT RESOLVES. `copystages` specifies em2 and em4 as SHORT same-thread
# follow-ups ("shorter where they can be"), the offer library records rungs 2
# and 4 as thread replies that carry no new argument
# (`productive-offers.yaml:224`, operator 2026-09-30), and `MIN_WORDS` demanded
# 40 words of every body alike. MEASURED on the bigfish canary, 2026-10-01:
# `em4` was refused `body_too_short` on 7 of 10 attempts in one round and 10 of
# 10 in the next, and a 29-word follow-up that reads correctly is refused by
# this module today - reproduced directly, not inferred from a log.
#
# THE CEILING IS THE HALF THAT COSTS SOMETHING, and the cost is measured rather
# than assumed: of 1323 stored `em2` bodies in the queue the median is 87 words
# and 1317 are over 60, as are 33 of 54 stored `em4` bodies. So this range
# refuses most of the EXISTING estate's replies, and `cadencelibrary`'s own
# measurement (its comment at the thread-reply block) records that replies which
# earned answers average 857 characters against 571 for new threads - longer,
# not shorter. Both numbers are in the report that accompanies this change; the
# ruling stands as given and the ceiling is enforced, but nothing here decided
# it and nothing here softens it.
REPLY_MIN_WORDS = 15
REPLY_MAX_WORDS = 60

#: THE STEPS THAT RULING NAMES. `thread_reply_rungs` on the offer is the
#: authority when the offer declares one; this is the operator's own named set
#: and the fallback for an offer that does not.
#:
#: WHY A FALLBACK EXISTS RATHER THAN A HARD REQUIREMENT. `OFFER-A-ECONOMIC-BUYER`
#: declares `thread_reply_rungs: [2, 4]`; `OFFER-B-OPERATIONS` - the offer
#: `generate_campaign._select_offers` actually selects for persona `champion`,
#: which is the canary's persona - declares NONE. Measured 2026-10-01. Keying
#: the range solely off that field would therefore have left the canary's own
#: offer with the 40-word floor and changed nothing for the step the ruling is
#: about. The two sources agree wherever both speak, so this fallback widens
#: nothing: `generate_campaign` itself puts em2 in em1's thread and em4 in em3's
#: (its `_subj` map), which is the same two steps by a third authority.
#:
#: FOR THE OPERATOR: adding `thread_reply_rungs: [2, 4]` to `OFFER-B-OPERATIONS`
#: would make the offer record the authority for its own shape. That file is an
#: APPROVED offer record carrying approval SHAs, so it is not edited here.
REPLY_STEPS = ("em2", "em4")

#: Sign-off openers, for the trailing block the word count must not include.
_SIGNOFF_RE = re.compile(
    r"(?mi)^[ \t]*(?:best(?: regards| wishes)?|regards|kind regards|cheers|"
    r"thanks(?: again)?|thank you|all the best|warmly|sincerely|speak soon)"
    r"[ \t]*[,.]?[ \t]*$")


#: How many words may trail a sign-off line and still be a SIGNATURE.
#:
#: THE HOLE THIS CLOSES, FOUND BY ATTACKING THIS FUNCTION RATHER THAN BY A
#: FAILING TEST. A bare "strip from the first sign-off line onward" is a way to
#: DEFEAT THE CEILING: a 190-word em1 carrying a line reading "Best," at word
#: 100 would be counted as 100 words and pass, where before it was 190 and
#: `body_too_long` refused it. A signature is a name, maybe a company, maybe a
#: URL. Twelve words is generous for that and far short of a paragraph, so prose
#: after a sign-off is still counted and still refused.
SIGNOFF_TAIL_MAX_WORDS = 12


def countable_words(body):
    """The body's words, EXCLUDING the opt-out line and any sign-off block.

    The operator's ruling says the range is measured "in the body, excluding
    the signature and the opt-out line", so this is where that exclusion is
    made - once, for every step, so the floor and the ceiling always count the
    same thing.

    MEASURED BEFORE IT WAS WRITTEN, because an exclusion for text that is never
    there is dead code pretending to be a rule. On 2026-10-01, over all 4082
    generated email bodies in the queue: ZERO carry `optout.OPT_OUT_LINE` and
    ZERO carry a sign-off line. That is by construction and both halves have an
    owner - `copystages` instructs "Write no signature. The sending mailbox
    appends its own", and `copylint` appends the opt-out itself with
    `optout.append_opt_out(body)` before counting it, so the writer's body
    never holds one. This function therefore changes no existing verdict; it
    exists so that a body which DOES acquire either one is not credited with
    words no prospect reads.

    THE DIRECTION IS STRICTER, NEVER LOOSER: removing text can only lower a
    count, so this can refuse a short body and can never admit one.
    """
    text = str(body or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(optout.OPT_OUT_LINE, " ")
    # THE LAST sign-off, and only if what follows it is short enough to BE a
    # signature. See `SIGNOFF_TAIL_MAX_WORDS`: stripping from the first one
    # unconditionally would let a long body duck the ceiling.
    for m in reversed(list(_SIGNOFF_RE.finditer(text))):
        if len(text[m.end():].split()) <= SIGNOFF_TAIL_MAX_WORDS:
            text = text[:m.start()]
            break
    return text.split()


def reply_steps_for(offer=None):
    """Which step keys are thread replies, per the offer's own record.

    Reads the offer's `thread_reply_rungs` - the same field `sequencegate`
    reads, so one authority answers "is this step a thread reply" for both the
    word range and the step-objective ladder. Falls back to `REPLY_STEPS`,
    whose own comment carries the measurement and the reason.
    """
    rungs = (offer or {}).get("thread_reply_rungs") or ()
    if not rungs:
        return frozenset(REPLY_STEPS)
    return frozenset("em%s" % r for r in rungs)


def step_key_of(rec, key, step):
    """Which cadence key this step is stored under, or None.

    THE REASON THIS EXISTS RATHER THAN A NEW ARGUMENT AT ELEVEN CALL SITES.
    The per-step word range is only honest if EVERY gate applies the same one.
    `lint.check` is called from `approve`, `eligibility`, `executionguard`,
    `campaigns`, `cadence`, `heyreachfactory`, `benchmark` and `generate` - and a
    range enforced at generation and not at approval is worse than no range at
    all: the writer would be told 15 words, produce them, and the approval gate
    would refuse the result as `body_too_short` one step later. That is this
    repository's recurring shape, and two of those modules are owned by other
    agents and must not be edited for this.
    So the key is RECOVERED from the record, which every one of those callers
    already passes. Identity first, because `generate._trial_cadence` puts the
    very dict being linted into the trial cadence under its own key; equality
    second, for a caller that copied it.

    Returns None for a step that is not in this contact's cadence at all - a
    synthetic step built by `campaignqa` from a variant, say - and None means
    the stricter 40-word floor, never the shorter one.
    """
    cad = (rec or {}).get("cadence") or {}
    steps = cad.get(key) or {}
    if not isinstance(steps, dict):
        return None
    for k, v in steps.items():
        if v is step:
            return k
    # AN AMBIGUOUS EQUALITY MATCH ANSWERS NOTHING, AND ANSWERING ANYWAY WOULD
    # HAVE BEEN A WAY TO DEFEAT THE FLOOR.
    #
    # Byte-identical copy across steps is not hypothetical here:
    # `tests/fixtures/phase7.jsonl` is twelve generated steps carrying identical
    # bodies, and `check`'s own greeting rule exists because of that incident.
    # Returning the FIRST equal key would mean an em3 whose body is identical to
    # em2's got em2's 15-word floor - a 25-word em3 passing a check written to
    # refuse it. So two or more equal candidates resolve to None, and None is
    # the stricter 40-word floor.
    matches = []
    for k, v in steps.items():
        try:
            if v == step:
                matches.append(k)
        except Exception:                                     # noqa: BLE001
            continue
    return matches[0] if len(matches) == 1 else None


def word_range(step_key=None, reply_steps=None):
    """`(minimum, maximum)` body words for this step. Thread replies differ.

    `step_key` is the cadence step key (`em1`..`em5`). An UNKNOWN step key gets
    the stricter 40-word floor rather than the reply range: a caller that does
    not say which step it is linting must not be handed the shorter floor by
    accident, because that is exactly how a floor gets quietly widened.
    """
    steps = (frozenset(reply_steps) if reply_steps is not None
             else frozenset(REPLY_STEPS))
    if step_key is not None and str(step_key) in steps:
        return REPLY_MIN_WORDS, REPLY_MAX_WORDS
    return MIN_WORDS, MAX_WORDS

# THE EM DASH WAS NEVER THE POINT. The rule is Productive's own tone line -
# "no em dashes" - and what it is really about is a model quietly substituting
# typography a person would not have typed. Two of the sixteen generated
# drafts in the estate on 2026-09-13 carried one of these and passed:
#
#   U+2019 RIGHT SINGLE QUOTATION MARK   16kagency-com/em4, in "you<U+2019>re"
#   U+2011 NON-BREAKING HYPHEN           1gslab-com/em2
#
# A non-breaking hyphen is not a hyphen to an email client that lacks the
# glyph; it is a box. A smart apostrophe survives a modern client and does
# not survive every one, and it is the character that turns into "you?re" the
# moment anything in the chain guesses the wrong encoding - which is how it
# was found, in a terminal.
#
# Deliberately NOT every non-ASCII character. "Müller" and "straße" are
# somebody's name and somebody's street, and a rule that refused them would
# refuse half the German and Nordic market this client sells to. These five
# are substitutions for characters that are already on the keyboard.
# WRITTEN AS ESCAPES, NOT AS CHARACTERS, AND THAT IS DELIBERATE.
#
# These five are invisible in a diff and indistinguishable from their
# ASCII cousins in most editors. On 2026-09-14 a change that ADDED a
# curly-apostrophe normaliser silently rewrote both curly apostrophes in
# this tuple as straight ones (U+0027) somewhere between being written
# and being committed. The rule then refused every ordinary contraction
# - "don't", "it's" - and stopped catching the character it names.
#
# An escape cannot be mangled by an encoding round-trip and cannot be
# mistyped invisibly. `tests/test_lint.py` pins the codepoints.
SUBSTITUTED_PUNCTUATION = ("—", "–", "‑", "’", "‘")

# THE CHARACTER MAP FOR NORMALISATION. Each substituted character maps to
# the plain ASCII equivalent a person would have typed. An em dash becomes
# " - " (space-hyphen-space) because it typically separates clauses; an en
# dash becomes a bare hyphen; a non-breaking hyphen becomes a hyphen; curly
# apostrophes become straight ones.
#
# This map is exactly SUBSTITUTED_PUNCTUATION and nothing else. It is not
# a general-purpose typography normaliser and must not become one.
_PUNCTUATION_MAP = {
    # AN EM DASH BECOMES A COMMA, NOT " - ".
    #
    # It mapped to " - " as the plain-ASCII equivalent, and that was right
    # until the operator banned a dash used as punctuation on 2026-09-25.
    # `copylint.DASH_RE` matches `\s-\s`, so THIS NORMALISER WAS
    # MANUFACTURING THE EXACT PATTERN THE COPY LINT REFUSES - in the campaign
    # path, `normalise_punctuation` runs over every body, subject and note
    # immediately before `copylint.check_batch`.
    #
    # MEASURED 2026-09-30: "a dash used as punctuation" was the single most
    # recurrent writer refusal, surviving twenty attempts across two models
    # and an explicit instruction naming the exact characters. The writer was
    # told "dash", looked at output containing no dash it had typed, and
    # wrote the em dash again. It was never disobeying.
    #
    # A comma is what an em dash separating clauses means, and it is
    # punctuation nothing refuses. The en dash below still becomes a bare
    # hyphen, which `DASH_RE` does not match because it is unspaced.
    "—": ", ",       # em dash, separates clauses
    "–": "-",        # en dash
    "‑": "-",        # non-breaking hyphen
    "’": "'",        # right single quote
    "‘": "'",        # left single quote
}


def normalise_punctuation(text):
    """Replace substituted punctuation with plain ASCII equivalents.

    Applied to model output BEFORE lint, so a draft whose only defect is a
    character encoding never fails an attempt. The words are untouched; the
    meaning is untouched; only the encoding changes. This is not patching a
    failing draft - it is pre-processing, the same kind of thing as
    normalising line endings.

    Returns the normalised text. Returns the original unchanged when no
    substituted character is present, so callers may compare identity to
    detect whether normalisation did anything.
    """
    if not text:
        return text
    for bad, replacement in _PUNCTUATION_MAP.items():
        text = text.replace(bad, replacement)
    return text


# The failure key stays `em_dash`. It is the name this rule has had
# since it was written, `render` and `classify` both key off it, and
# renaming it across fourteen call sites is churn this change did not
# need. The constant is what a reader looks at to find out what the
# rule covers, so the constant is what carries the honest name.

BANNED_PHRASES = (
    "i hope this email finds you well", "i wanted to reach out", "circling back",
    "just following up", "touching base", "as per my last email", "synergy",
    "game-changer",
    # OPERATOR DIRECTION, ZVONIMIR, 2026-09-29. The routing persona is
    # internal metadata that picks the offer; a prospect must never read it.
    # This is a correctness defect, not a style preference: it leaks our own
    # taxonomy into somebody else's inbox.
    #
    # GATED RATHER THAN ASKED FOR. The writer prompt was told twice not to
    # write these and produced them anyway - li1 opened "many economic buyers
    # struggle to see project margin" and li2 said "we help economic buyers
    # get real-time margin visibility" - because nothing refused them. Every
    # other voice rule that stuck this session stuck because a gate enforced
    # it; guidance alone drifts back on the next generation.
    "economic buyer", "economic buyers", "financial leaders",
    "decision maker persona",
    # Machine register the operator named in the same direction.
    "would you be interested",
)

# Real attachment talk only. "with no pitch attached" is an idiom and must pass.
ATTACHMENT_RE = re.compile(
    r"\battachment\b"
    r"|attached (is|are|you'?ll|please|here|below)"
    r"|(see|find|i'?ve|i have|we'?ve) attached"
    r"|attached (file|screenshot|deck|pdf|doc|csv|list|sheet|rate card)"
    r"|(file|screenshot|deck|pdf|doc|csv|sheet|rate card|image)s? attached",
    re.I)

# [...] {...} <...>, but not a URL in angle brackets.
PLACEHOLDER_RE = re.compile(r"[\[{<](?!http)[^\]}>\n]{2,40}[\]}>]")

HELD_CODES = frozenset({"recipient_not_sendable"})


# WHAT A FAILURE CODE MEANS, IN WORDS A WRITER CAN ACT ON.
#
# `generate.draft` regenerates a failing draft and feeds the reason back -
# "Your previous draft failed lint: {reason}. Write a new one." It was
# feeding back the CODE. A model told `filler_phrase` three times has been
# told nothing three times, and three uninformative retries is a step that
# never gets written.
#
# Measured 2026-09-13: `em5` - the step whose job is to close the loop -
# failed on `filler_phrase` for six of twenty records across two full
# regeneration passes, and the retry prompt said only "filler_phrase". Six
# contacts could not be staged for want of one message each.
#
# The explanations live here rather than in the prompt because this module
# owns the rules, and an explanation that drifts from the rule it explains is
# worse than none.
EXPLAIN = {
    "filler_phrase": "you used a phrase that is banned outright. Remove it "
        "and say the thing directly instead",
    "em_dash": "you used an em dash, en dash, curly apostrophe or "
        "non-breaking hyphen. Plain ASCII punctuation only",
    "placeholder": "you left an unfilled placeholder in square, curly or "
        "angle brackets",
    "attachment": "you referred to an attachment. Nothing is attached",
    "body_too_short": f"the body is under {MIN_WORDS} words",
    "body_too_long": f"the body is over {MAX_WORDS} words",
    # SEPARATE CODES, NOT A REWORDED `body_too_short`. The reason string is fed
    # straight back to the writer as its retry instruction, and telling a step
    # whose own range is 15 to 60 that it is "under 40 words" is an instruction
    # to break the ceiling: measured on the bigfish canary, `em4` came back
    # under-length 7 then 10 times in consecutive rounds, having been told the
    # wrong number every time.
    "reply_too_short": f"this is a thread reply, so its body must be at least "
        f"{REPLY_MIN_WORDS} words",
    "reply_too_long": f"this is a thread reply and must stay under "
        f"{REPLY_MAX_WORDS} words. Shorten it rather than lengthening the "
        f"others",
    "subject_too_long": f"the subject is {MAX_SUBJECT} characters or more",
    "subject_missing": "there is no subject",
    "body_missing": "there is no body",
    "greets_the_wrong_person": "you greeted somebody who is not the "
        "recipient. Use their name or no name at all",
    # Not interpolated: `NOTE_MAX_CHARS` is defined below this table
    # and a forward reference at module scope is a NameError.
    "note_too_long": "the note is too long for a connection request",
    "note_too_short": "the note is too short to say anything",
    "mentions_the_email": "you referred to the other channel. Each "
        "message stands alone",
    "structural_repetition_across_rungs": "this email has the same "
        "opening and closing shape as another step in the sequence. "
        "Vary the nouns is not enough: open differently and close "
        "differently from every other step",
}


def explain(codes, text=""):
    """Failure codes as sentences a writer can act on.

    `text` is optional and is used to NAME the offending phrase rather than
    describe its category - "you used the phrase 'just following up'" is
    actionable where "you used a banned phrase" is a guessing game. A code
    with no entry is passed through unchanged rather than dropped: an
    unexplained reason is still a reason, and silently losing one would make
    a retry look unprompted.
    """
    said = str(text or "").lower()
    out = []
    for code in codes or ():
        line = EXPLAIN.get(code, code)
        if code == "filler_phrase":
            found = [p for p in BANNED_PHRASES if p in said]
            if found:
                named = ", ".join(f"\"{p}\"" for p in found)
                line = (f"you used {named}, which is banned outright. Remove "
                        f"it and say the thing directly instead")
        out.append(line)
    return "; ".join(out)


def sendable(contact, policy=None):
    """Section 6.1, decided in one place.

    The rule itself now lives in src/verification.py, which is the only module
    allowed to conclude that an address may be written to. This stays as the
    name the rest of the codebase already calls, and delegates.

    `policy` is the CLIENT's verification policy. Omitted, the conservative
    default decides - which is right for a caller that has no client in hand
    and wrong for one that does. See `policy_for_record`.
    """
    from . import verification
    return verification.is_sendable(contact, policy)


_POLICY_CACHE = {}


def policy_for_record(rec):
    """The verification policy of the client this record belongs to.

    A record knows its client and a client may have chosen its own roles, so
    a lint run over that record must ask the same question the client asked.
    Productive moved primary to Deliverable and dropped ContactOut from
    verification on 2026-09-21; without this, lint kept answering under the
    defaults and refused 564 steps whose addresses the client's own policy
    had cleared.

    Cached per client because `check` runs once per step per contact - a
    thousand YAML loads for one batch is the difference between a lint pass
    and a coffee break - and cleared by `forget_policies` for tests that
    rewrite a client config mid-run.
    """
    client = (rec or {}).get("client")
    if not client:
        return None
    if client not in _POLICY_CACHE:
        from . import clients, verification
        try:
            _POLICY_CACHE[client] = verification.policy_for(
                clients.load(client))
        except Exception:                                       # noqa: BLE001
            # A missing or unreadable client config must not decide that an
            # address is sendable. None means "the default policy", which is
            # the conservative one.
            _POLICY_CACHE[client] = None
    return _POLICY_CACHE[client]


def forget_policies():
    _POLICY_CACHE.clear()


def contact_key(contact):
    """The contact id, from src/identity.py. A stored key always wins."""
    return identity.contact_key(contact)


def find_contact(rec, key):
    """The contact a cadence key points at, in this record's own contact list."""
    contacts = rec.get("contacts") or []
    for c in contacts:
        if c.get("key") == key:
            return c
    for c in contacts:
        if contact_key(c) == key:
            return c
    return None


def send_scope(rec, contact=None):
    """The contacts on this record whose copy can actually reach a person.

    WHY THIS IS NOT `rec["contacts"]`.

    `domains_contact_no_angle` asked whether ANY contact on the record lacked an
    angle, and refused every draft on the record if one did. The rule's own
    purpose, stated in `personas.default_angle`, is that a person with no angle
    is "held rather than written to with the wrong words" - which is a fact
    about the person being written to, not about the record they share. The
    LinkedIn half of this module has always scoped it to the recipient; the
    email half did not, and that asymmetry is the defect.

    It only became load-bearing on 2026-09-30, when generation was scoped to a
    single canary contact. Measured on the three candidate records that day:
    every SENDABLE contact carried an angle - one per record - and every contact
    without one was NOT sendable (23, 20 and 4 of them). So the gate fired
    entirely on people who can never be emailed, and blocked the one person
    whose angle was correct. `generate.plan` sets angles only for workable
    contacts, so a record holding one unpersonaed, unverified contact could
    never satisfy the old form of this rule at all.

    Scope is deliberately WIDER than the recipient alone, and conservative in
    both directions: a contact counts if the record marks it `sendable`, OR if
    its evidence still resolves as sendable under the client's policy, OR if it
    is the recipient of the step being checked. A hand-set flag cannot dodge the
    gate, a stale flag cannot smuggle somebody in, and being on the record's
    `excluded` list is not a way to skip it.
    """
    policy = policy_for_record(rec)
    key = (contact or {}).get("key")
    scope = []
    for c in rec.get("contacts") or []:
        if (key is not None and c.get("key") == key) or c.get("sendable") \
                or sendable(c, policy):
            scope.append(c)
    if contact is not None and not any(c.get("key") == key for c in scope):
        scope.append(contact)
    return scope


def email_steps(rec):
    """Yield (contact_key, day, step) for every generated email in the record."""
    for key, steps in (rec.get("cadence") or {}).items():
        for day, step in (steps or {}).items():
            if not isinstance(step, dict):
                continue
            if step.get("channel") != "email":
                continue
            if not step.get("body"):
                # An unexpanded template step: no body to lint yet. This
                # generator walks what is *stored* on the record, and a
                # template has not become an email until it is expanded.
                #
                # That is not a hole, and the note that used to sit here
                # said it was one long after it had stopped being true.
                # The expanded step is linted in two places, both of which
                # see the final words rather than the template:
                # `cadence.status_for` runs `lint.check_step` after
                # expansion and blocks the step, and `eligibility` runs
                # `lint.check` again on the exact step a payload is about
                # to be built from. Nothing enters a push path unlinted.
                continue
            yield key, day, step


# A record in one of these states must not ship, whatever its draft says. A
# dropped record includes a suppressed live account, and section 9 trap 6 calls
# cold-sequencing a live customer the single most expensive mistake in the motion.
UNSHIPPABLE = {"dropped": "record_dropped", "pushed": "record_already_pushed"}


GREETINGS = ("hi", "hello", "hey", "dear", "good morning", "good afternoon")

# Openers that address nobody in particular. Not a wrong-person problem.
IMPERSONAL = ("there", "team", "all", "folks", "everyone")

# The greeting word is matched case-insensitively and the NAME is not: a
# capitalised token is what distinguishes "Dear Sam," from "the teams I work
# with". Written as an inline `(?i:...)` group rather than a flag on the whole
# pattern, because `re.IGNORECASE` would make `[A-Z]` match anything and the
# rule would then fire on ordinary prose - which is how the first version of
# this failed: it was fully case-sensitive, so "Hi Marin," and "Dear Sam,"
# both matched NOTHING and two wrong-person cases passed by accident.
GREETING_RE = re.compile(
    r"^\s*(?:(?i:hi|hello|hey|dear|good morning|good afternoon)[\s,]+)?"
    r"([A-Z][\w'’\-]+)\s*[,!.\n]", re.UNICODE)


def _greeted_name(body):
    """The name a body opens by addressing, or "" if it addresses nobody.

    Reads only the first line: a name appearing later is prose, and treating it
    as a salutation would fire on "the teams I work with that look most like
    Brightpath".
    """
    first = (body or "").strip().split("\n", 1)[0]
    found = GREETING_RE.match(first)
    if not found:
        return ""
    name = found.group(1).strip()
    return "" if name.lower() in IMPERSONAL or name.lower() in GREETINGS else name


def _names_match(greeted, full_name):
    """Does this salutation name this person?

    Generous on form and strict on identity. A first name, a full name, a
    hyphenated or accented spelling and a diminutive-free comparison all pass;
    a different person does not. Case and surrounding punctuation are not
    identity, so they are normalised away - but a name that simply is not on the
    contact is a different human, and that is the whole point.
    """
    greeted = str(greeted or "").strip().lower().strip(".,!")
    full = str(full_name or "").strip().lower()
    if not greeted:
        return True
    if not full:
        # No name recorded for the recipient, so nothing can be verified. This
        # is not a pass: a body cannot address by name somebody the record
        # cannot name.
        return False
    parts = [p for p in re.split(r"[\s\-’']+", full) if p]
    return greeted in parts or greeted == full


def check(rec, key, step, step_key=None, reply_steps=None):
    """Return the sorted, deduped failure codes for one generated email.

    `step_key` is this step's cadence key (`em1`..`em5`). It decides the body
    word range and NOTHING else: a thread reply has its own range (see
    `word_range`), and every other rule in this function is identical for every
    step. Omitting it gets the stricter 40-word floor, so an old call site
    cannot be handed the shorter one by accident.

    `reply_steps` overrides which keys count as thread replies; callers that
    know the offer pass `reply_steps_for(offer)` so the offer's own record is
    the authority.
    """
    fails = set()
    contact = find_contact(rec, key)

    if rec.get("state") in UNSHIPPABLE:
        fails.add(UNSHIPPABLE[rec["state"]])
    # Normalise line endings first: a CRLF body is still one line per paragraph,
    # and git on Windows converts on checkout.
    body = (step.get("body") or "").replace("\r\n", "\n").replace("\r", "\n")
    subject = step.get("subject") or ""

    if contact is None:
        fails.add("recipient_not_on_record")
    elif not contact.get("email"):
        fails.add("recipient_missing")
    elif not sendable(contact, policy_for_record(rec)):
        fails.add("recipient_not_sendable")

    # THE GREETING MUST NAME THE PERSON IT IS ADDRESSED TO.
    #
    # Nothing checked this, anywhere. `render.emailbison_rows` writes
    # `first_name` from the contact and `body` from the step independently, so a
    # row addressed `first_name=Marin` carrying a body that opens "Ivana," goes
    # into the push CSV as one lead. `claims.py` cannot reach it - "Ivana, you
    # run finance across five offices" has no number, no month and no event
    # word - so it was clean by every measure the system had.
    #
    # `tests/fixtures/phase7.jsonl` is the proof of how it goes wrong at scale:
    # twelve generated steps carrying byte-identical copy, eleven of them
    # addressed to somebody who is not the recipient, all twelve linting clean
    # and all twelve reaching the push file. That fixture is what the push and
    # approval tests assert against, so it is also what anybody reads to learn
    # what good copy looks like.
    #
    # Deliberately narrow: it fires only when the body opens with SOME name and
    # that name is not the recipient's. A body that opens "Hi there" or with no
    # salutation at all is a style question, not a wrong-person question, and
    # `MIN_WORDS`, `BANNED_PHRASES` and the hook rules already have opinions
    # about openers.
    if contact is not None and body.strip():
        greeted = _greeted_name(body)
        if greeted and not _names_match(greeted, contact.get("name")):
            fails.add("greets_the_wrong_person")

    if any(d in body or d in subject for d in SUBSTITUTED_PUNCTUATION):
        fails.add("em_dash")
    if ATTACHMENT_RE.search(body):
        fails.add("attachment")
    # "no unfilled placeholder" is not scoped to the body: a subject line is
    # the most visible place for one.
    if PLACEHOLDER_RE.search(body) or PLACEHOLDER_RE.search(subject):
        fails.add("placeholder")

    # THE RANGE IS PER STEP, AND THE CODES SAY WHICH RANGE WAS APPLIED.
    #
    # A thread reply is judged against `REPLY_MIN_WORDS`..`REPLY_MAX_WORDS` and
    # reports `reply_too_short`/`reply_too_long`; every other step is judged
    # against `MIN_WORDS`..`MAX_WORDS` and reports `body_too_short`/
    # `body_too_long` exactly as before. Two code pairs rather than one, because
    # the code is what the writer is told and "under 40 words" is the wrong
    # instruction for a step whose floor is 15.
    if step_key is None:
        step_key = step_key_of(rec, key, step)
    low, high = word_range(step_key, reply_steps)
    is_reply = (low, high) != (MIN_WORDS, MAX_WORDS)
    words = len(countable_words(body))
    if words < low:
        fails.add("reply_too_short" if is_reply else "body_too_short")
    if words > high:
        fails.add("reply_too_long" if is_reply else "body_too_long")

    if not subject:
        fails.add("subject_missing")
    elif len(subject) >= MAX_SUBJECT:
        fails.add("subject_too_long")

    # One unbroken line per paragraph, blank line between. Gmail keeps hard
    # breaks and they render as ragged short lines.
    for para in body.split("\n\n"):
        if len([l for l in para.split("\n") if l.strip()]) > 1:
            fails.add("hard_wrapped")
            break

    low = body.lower()
    if any(p in low for p in BANNED_PHRASES):
        fails.add("filler_phrase")

    lane = rec.get("lane")
    if lane == "revive" and not (rec.get("diagnosis") or {}).get("died_because"):
        fails.add("revive_no_diagnosis")
    if lane == "cold" and not rec.get("hook"):
        fails.add("cold_no_hook")
    if lane == "domains" and any(not c.get("angle")
                                 for c in send_scope(rec, contact)):
        fails.add("domains_contact_no_angle")

    return sorted(fails)


# ------------------------------------------------------- the LinkedIn side
#
# The email rules above do not transfer. A connection note is capped by
# LinkedIn at 300 characters, a message is a different shape again, and the
# forty-word minimum that keeps an email from reading as a drive-by would make
# a note impossible. So LinkedIn gets its own rules rather than a relaxed
# version of the email ones - and it gets rules at all, because "no final
# outbound step may bypass lint" has to include the half of the cadence that
# is not email.

NOTE_MAX_CHARS = 300          # LinkedIn's own limit on a connection request
NOTE_MIN_CHARS = 40           # below this it reads as a bot, not as brevity
MESSAGE_MAX_CHARS = 1900      # our limit, not theirs: longer does not get read
MESSAGE_MIN_CHARS = 60

# A connection note that refers to an email nobody has opened yet is the most
# common multichannel mistake, and it is unrecoverable: the recipient now knows
# they are in a sequence.
CROSS_CHANNEL_TERMS = ("my email", "the email i sent", "as i wrote",
                       "my last message", "i emailed", "check your inbox",
                       "sent you a note earlier")

LINKEDIN_HELD_CODES = frozenset({"profile_missing"})

# The step that requires an accepted connection is a message to someone who
# already agreed to hear from us; everything else on LinkedIn is the request
# itself, and only the request is capped at 300 characters. Deciding this from
# `requires` rather than from a day number keeps it true when the cadence is
# reconfigured, which it is meant to be.
CONNECTION_ACCEPTED = "connection_accepted"
#: THE SAME STATE UNDER THE NAME THE CADENCE ACTUALLY DECLARES.
#:
#: `cadencelibrary.CONNECTED` is `"connected"`, and it is the `requires` on
#: li2, li3, li4 and li5 - every LinkedIn MESSAGE in the heavy cadence. This
#: module compared against `"connection_accepted"` only, so all four messages
#: answered `is_connection_note` TRUE and were capped at 300 characters as if
#: they were connection requests. Measured 2026-09-28: li1 (action `connect`,
#: `requires` None) correctly took the 300 cap and li2-li5 took it wrongly,
#: which caused false `note_too_long` refusals in the P0-B runs.
#:
#: NO CAP IS RAISED BY THIS. `NOTE_MAX_CHARS` is still 300 and still applies
#: to the connection request, which is the only step LinkedIn itself limits.
#: What changes is which steps are classified as that request. The comment
#: above says the classification is decided from `requires` rather than from a
#: day number so it survives a cadence being reconfigured - that design is
#: right and is kept; it simply has to recognise both names for one state.
#:
#: Operator decision "A", Zvonimir, 2026-09-28.
CONNECTED = "connected"
CONNECTED_STATES = frozenset({CONNECTION_ACCEPTED, CONNECTED})


def is_connection_note(step):
    """Is this step the connection REQUEST, rather than a message?

    A step that requires an established connection is a message to somebody
    who already agreed to hear from us. Everything else is the request itself,
    and only the request carries LinkedIn's 300-character limit.
    """
    return (step or {}).get("requires") not in CONNECTED_STATES


def check_linkedin(rec, key, step):
    """Failure codes for one LinkedIn note or message, after expansion."""
    fails = set()
    contact = find_contact(rec, key)

    if rec.get("state") in UNSHIPPABLE:
        fails.add(UNSHIPPABLE[rec["state"]])

    text = (step.get("note") or step.get("body") or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # The same guard the email path carries. `personas.default_angle`
    # returns None when no configured angle fits the person - a finance
    # lead in a persona that defines only founder wording - so that they
    # are held rather than written to with the wrong words. `check`
    # enforced that and this did not, and `cadence.angle_words` falls
    # back to the first angle in the map, so on LinkedIn the held
    # contact was silently given somebody else's copy chosen by
    # dictionary order. The guard has to hold on the channel that
    # sends, not only on the one that is blocked.
    if (rec.get("lane") == "domains" and contact is not None
            and not contact.get("angle")):
        fails.add("domains_contact_no_angle")
    is_note = is_connection_note(step)

    if contact is None:
        fails.add("recipient_not_on_record")
    elif not contact.get("linkedin"):
        fails.add("profile_missing")

    if not text:
        fails.add("note_missing" if is_note else "message_missing")
        return sorted(fails)

    if PLACEHOLDER_RE.search(text):
        fails.add("placeholder")
    if any(d in text for d in SUBSTITUTED_PUNCTUATION):
        fails.add("em_dash")
    if ATTACHMENT_RE.search(text):
        fails.add("attachment")

    low = text.lower()
    if any(phrase in low for phrase in BANNED_PHRASES):
        fails.add("filler_phrase")
    if any(term in low for term in CROSS_CHANNEL_TERMS):
        fails.add("mentions_the_email")

    if is_note:
        if len(text) > NOTE_MAX_CHARS:
            fails.add("note_too_long")
        elif len(text) < NOTE_MIN_CHARS:
            fails.add("note_too_short")
    else:
        if len(text) > MESSAGE_MAX_CHARS:
            fails.add("message_too_long")
        elif len(text) < MESSAGE_MIN_CHARS:
            fails.add("message_too_short")

    return sorted(fails)


def classify_linkedin(failures):
    """Same three verdicts as email, with its own held set."""
    if not failures:
        return "clean"
    if set(failures) <= LINKEDIN_HELD_CODES:
        return "held"
    return "failed"


def check_step(rec, key, step, step_key=None, reply_steps=None):
    """Lint one step of either channel. The single door every step goes through.

    `step_key` and `reply_steps` thread to `check` and decide the body word
    range. LinkedIn notes have their own character bounds and ignore both.
    """
    if (step or {}).get("channel") == "linkedin":
        return check_linkedin(rec, key, step)
    return check(rec, key, step, step_key=step_key, reply_steps=reply_steps)


def classify(failures):
    """clean ships, held keeps its draft and waits on verification, failed is red."""
    if not failures:
        return "clean"
    if set(failures) <= HELD_CODES:
        return "held"
    return "failed"


def check_record(rec):
    """[{key, day, step, contact, failures, status}] for one record."""
    out = []
    for key, day, step in email_steps(rec):
        # `day` IS THE STEP KEY. `email_steps` yields the cadence key it read
        # the step from, so the CLI and every caller of `check_record` judge a
        # thread reply against its own range instead of em1's. Without this the
        # per-step range would exist and the module's own report would not use
        # it, which is the "computed and nothing reads it" shape.
        failures = check(rec, key, step, step_key=day)
        out.append({"record": rec, "id": rec["id"], "key": key, "day": day,
                    "step": step, "contact": find_contact(rec, key),
                    "failures": failures, "status": classify(failures)})
    return out


def check_all(recs=None):
    recs = recs if recs is not None else store.load()
    return [r for rec in recs for r in check_record(rec)]


def step_id(result):
    return f"{result['id']}:{result['key']}:{result['day']}"


def main(argv=None):
    argparse.ArgumentParser(prog="python -m src.lint").parse_args(argv)
    results = check_all()
    for r in results:
        detail = "OK" if not r["failures"] else "; ".join(r["failures"])
        print(f"{step_id(r):<40} {r['status']:<6} {detail}")
    if not results:
        print("no generated emails in the queue")
    return 1 if any(r["failures"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
