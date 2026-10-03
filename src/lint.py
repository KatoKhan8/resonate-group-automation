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
from .skills import cold_email_writing as writercontract
from .skills import linkedin_writing as linkedincontract

# Section 6.2. Never widen one of these to make a draft pass. Regenerate the draft.
#
# These three are the SINGLE-EMAIL draft shape (`prompts/draft.md`: "~110 words,
# 40 to 180 range"). They are the floor under every email of every shape and they
# are NOT the five-email sequence's contract - see `STEP_WORD_CONTRACT` below,
# which is narrower and additional to them.
MIN_WORDS = 40
MAX_WORDS = 180
MAX_SUBJECT = 60          # "under 60 characters": 59 passes, 60 fails

# THE WRITER'S DECLARED WORD CONTRACT, READ RATHER THAN RESTATED, AND SINCE
# 2026-10-02 THE ONLY AUTHORITY FOR AN EMAIL BODY'S LENGTH.
#
# `skills.cold_email_writing.WORD_CONTRACT` declares a (floor, target, ceiling)
# per step of the five-email sequence. This module is the gate, and it carried no
# 60 and no 90 as a word bound anywhere: its floor was `MIN_WORDS` (40) for all
# five. Measured on the one approved canary copy, 2026-10-02, against the ranges
# the writer was being handed at the time:
#
#   em1  61 words  60-90   passed
#   em2  41 words  60-90   passed - 19 words under contract
#   em3  53 words  60-90   passed -  7 words under contract
#   em4  46 words  45-90   passed
#   em5  41 words  45-90   passed
#
# Both doors passed all five, so the declared range was enforced by nothing.
# THIS IS NOT A THRESHOLD MOVING. The numbers are not retyped here; they are
# imported from the writer's own declaration, which is the only place they are
# allowed to live. Change them there and this gate changes with them.
STEP_WORD_CONTRACT = writercontract.WORD_CONTRACT

# THE LINKEDIN SIDE'S CHARACTER CONTRACT, READ RATHER THAN RESTATED, AND SINCE
# 2026-10-03 THE ONLY AUTHORITY FOR THE LENGTH OF A LINKEDIN NOTE OR MESSAGE.
#
# Operator ruling, 2026-10-03: NOTE_MIN_CHARS, MESSAGE_MIN_CHARS and
# MESSAGE_MAX_CHARS are replaced by one measured contract in the same shape as
# the email one - li2 100-299 aiming for 125, li1 with NO floor while it is
# UNKNOWN, and the measured note ceiling of 179 recorded beside LinkedIn's own
# 300. One authority, and it is `skills.linkedin_writing`.
#
# WHAT WAS HERE UNTIL THEN AND IS DELIBERATELY GONE, each refuted by
# measurement in `docs/second-brain/linkedin.md` section 14 over 54,647
# outbound messages:
#
#   NOTE_MIN_CHARS    = 40    would have refused the best-accepting note in
#                             the estate - 19 characters, 13.66% acceptance on
#                             n = 7,988, +3.13pp over a 10.52% baseline. A
#                             floor that refuses the best-measured instance is
#                             not a floor. It is NOT replaced by 19: one
#                             campaign is not a measurement, so li1's floor is
#                             UNKNOWN and no length refusal is asserted.
#   MESSAGE_MAX_CHARS = 1900  has never bound. Longest outbound message in
#                             54,647 is 1,097 and p99 is 801; the ceiling that
#                             separates outcomes is 299.
#   MESSAGE_MIN_CHARS = 60    below the measured floor: the 60-99 band it
#                             permitted is the worst bucket in the corpus,
#                             0.136 positives per 100 on n = 4,425.
#
# The numbers are not retyped here. Change them in the skill and this gate
# changes with them - asserted by effect in
# `tests.test_the_linkedin_char_contract_is_measured.TestOneAuthority`.
LINKEDIN_CHAR_CONTRACT = linkedincontract.LINKEDIN_CHAR_CONTRACT

#: UNKNOWN re-exported so a reader of this gate can test a bound without
#: reaching past it. It is NOT None and NOT 0: see `linkedin_writing._Unknown`.
LINKEDIN_UNKNOWN = linkedincontract.UNKNOWN

#: LinkedIn's own limit on a connection request, READ FROM THE CONTRACT. It
#: keeps its name because `generate_campaign` and two tests already call it,
#: and it is the one of the four original constants the corpus confirms: 0 of
#: 47 note variants exceed it and the longest ever sent is 234.
NOTE_MAX_CHARS = LINKEDIN_CHAR_CONTRACT["li1"][2]

#: The connection note's MEASURED soft ceiling, 179, which is not a refusal.
#: Carried here under its own name so a reader of the gate can see that the
#: gate deliberately does not enforce it.
NOTE_MEASURED_CEILING = linkedincontract.LI1_MEASURED_CEILING

_LI1_FLOOR = LINKEDIN_CHAR_CONTRACT["li1"][0]
_LI_MSG_FLOOR, _LI_MSG_CEILING = linkedincontract.strictest_message_bounds()

# WHAT WAS HERE UNTIL 2026-10-02 AND IS DELIBERATELY GONE: `REPLY_MIN_WORDS` and
# `REPLY_MAX_WORDS` (15 and 60), `REPLY_STEPS`, `reply_steps_for`, the reply
# branch of `word_range` and the `reply_too_short` / `reply_too_long` codes. The
# 2026-10-01 ruling that created them - "thread-reply steps get their OWN range
# of 15 to 60 words" - was ABOLISHED by the operator on 2026-10-02, and the
# writer contract is now the only authority for an email body's word count.
#
# WHY IT WAS ABOLISHED, WHICH IS THE PART WORTH KEEPING. The two rules were
# never reconciled: the reply range said em2 was 15 to 60 and the writer contract
# said 60 to 90, so their intersection was the single value 60. A range with one
# legal length is an equality, not a threshold, and no writer can hit it
# reliably. `tests.test_word_contract_enforced.TestEveryRangeHasRoom` is the
# guard against that shape recurring.
#
# MEASURED BEFORE DELETING THEM, because deleting a name something else reads is
# how a working gate becomes a silent one. Over `src`, `tests`, `config`,
# `prompts`, `scripts` and `tools`: `REPLY_MIN_WORDS`, `REPLY_MAX_WORDS` and
# `REPLY_STEPS` were read by nothing outside this module and its own test, and
# `reply_steps_for` had exactly ONE caller, `generate._step_refusals`. The
# step-objective LADDER reads the offer's `thread_reply_rungs` directly -
# `sequencegate` at its reply-rung block and `copystages.step_objective_block` -
# and never through this module, so the ladder is untouched by their removal and
# `tests.test_a_thread_reply_carries_no_rung_of_its_own` still passes.
#
# `word_range` went with them rather than being left as a constant function:
# with the reply branch gone its one remaining branch was `return MIN_WORDS,
# MAX_WORDS`, and a second function in the gate answering "which range applies
# to this step" is the duplicate authority this change exists to remove.
# `writercontract.word_range` is that function now, and it is the only one.

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

    ONE DEFINITION OF "A WORD", for every step and every bound, so the floor and
    the ceiling and the contract always count the same thing. The 2026-10-01
    ruling that first asked for this exclusion was abolished on 2026-10-02; the
    exclusion itself was not, and it is kept because the alternative is crediting
    a body with words no prospect reads.

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


def step_key_of(rec, key, step, step_key=None):
    """Which cadence key this step is stored under, or None.

    THE REASON THIS EXISTS RATHER THAN A NEW ARGUMENT AT ELEVEN CALL SITES.
    The per-step word contract is only honest if EVERY gate applies it.
    `lint.check` is called from `approve`, `eligibility`, `executionguard`,
    `campaigns`, `cadence`, `heyreachfactory`, `benchmark` and `generate` - and a
    range enforced at generation and not at approval is worse than no range at
    all: the writer would be told one number, produce it, and the approval gate
    would refuse the result one step later. That is this repository's recurring
    shape, and two of those modules are owned by other agents and must not be
    edited for this. So the key is RECOVERED from the record, which every one of
    those callers already passes.

    Four ways, in order, because the callers differ and none of them should have
    to change in order to be gated:

    1. the caller said so - `check_record` knows the key from iteration and
       `generate._step_refusals` knows it from the pair it is linting;
    2. the step carries its own key, which some builders write;
    3. IDENTITY on the record, first, because `generate._trial_cadence` puts the
       very dict being linted into the trial cadence under its own key;
    4. unambiguous EQUALITY, for a caller that copied it, and then unambiguous
       equality OF THE BODY, for a caller that expanded it.

    (4)'s body fallback is not decoration, it is what reaches the two doors that
    matter - measured, not assumed. Over `tests.test_cadence`,
    `test_eight_step_cadence` and `test_siblings_block`, 2,734 expanded email
    steps reached this function through `cadence.status_for` and identity found
    NONE of them: `status_for` is handed a freshly expanded step, a new object
    carrying the stored body but also a status, a day and a variant the stored
    one does not, so it is equal to nothing. Over `tests.test_eligibility`,
    identity found 1 of 7,162. A body is the one thing an expanded step and its
    stored original share, and a gate that misses the timeline door and the send
    path is decoration.

    AN AMBIGUOUS MATCH ANSWERS NOTHING, AND ANSWERING ANYWAY WOULD HAVE BEEN A
    WAY TO DEFEAT THE FLOOR.

    Byte-identical copy across steps is not hypothetical here:
    `tests/fixtures/phase7.jsonl` is twelve generated steps carrying identical
    bodies, and `check`'s own greeting rule exists because of that incident.
    Returning the FIRST equal key would mean an em4 whose body is identical to
    em1's was judged against em1's 60-word floor. So two or more equal candidates
    resolve to None, and None means no contract applies and the step keeps the
    `MIN_WORDS`..`MAX_WORDS` verdict it had before - never a looser one.
    """
    named = step_key or (step or {}).get("step_key") or (step or {}).get("key")
    if named:
        return str(named).strip().lower()
    cad = (rec or {}).get("cadence") or {}
    steps = cad.get(key) or {}
    if not isinstance(steps, dict):
        return None
    for k, v in steps.items():
        if v is step:
            return str(k).strip().lower()
    body = (step or {}).get("body")
    for candidates in (
            [k for k, v in steps.items() if _equal(v, step)],
            [k for k, v in steps.items()
             if body and isinstance(v, dict) and v.get("body") == body]):
        if len(candidates) == 1:
            return str(candidates[0]).strip().lower()
    return None


def _equal(a, b):
    """`a == b`, never raising. A step may hold anything a builder put in it."""
    try:
        return bool(a == b)
    except Exception:                                         # noqa: BLE001
        return False

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
    # THE CONTRACT CODES ARE NOT IN THIS TABLE, and `reply_too_short` /
    # `reply_too_long` are gone with the ruling that created them. The reason
    # string is fed straight back to the writer as its retry instruction, and a
    # table cannot hold an entry per word count: a contract refusal carries its
    # step, its count and both bounds in the code itself and `explain_contract`
    # turns them back into the sentence. See `CONTRACT_CODE_RE`.
    "subject_too_long": f"the subject is {MAX_SUBJECT} characters or more",
    "subject_missing": "there is no subject",
    "body_missing": "there is no body",
    "greets_the_wrong_person": "you greeted somebody who is not the "
        "recipient. Use their name or no name at all",
    # INTERPOLATED FROM THE CONTRACT. These four said "too long" and "too
    # short" without a number, which is a reason a writer cannot act on, and
    # two of them were enforcing numbers the corpus refutes. The contract is
    # imported above this table now, so the bound can be named.
    "note_too_long": "the note is over %s characters, which is LinkedIn's own "
        "limit on a connection request. The one note band measured above %d "
        "characters accepted BELOW the no-note baseline, so shorter is not "
        "merely allowed, it is what was measured to work"
        % (linkedincontract.bound_phrase(NOTE_MAX_CHARS),
           NOTE_MEASURED_CEILING),
    "note_too_short": (
        "the connection note has NO measured floor - the contract says "
        "UNKNOWN - so nothing should be producing this code"
        if _LI1_FLOOR is LINKEDIN_UNKNOWN else
        "the note is under its measured floor of %d characters" % _LI1_FLOOR),
    "message_too_long": (
        "the message is over %s characters. 100-299 is the band measured to "
        "beat every band above it; aim for about %s characters on the first "
        "message after the connect and %s on a follow-up"
        % (linkedincontract.bound_phrase(_LI_MSG_CEILING),
           linkedincontract.bound_phrase(linkedincontract.char_target("li2")),
           linkedincontract.bound_phrase(
               linkedincontract.char_target("li3+")))),
    "message_too_short": (
        "the message is under %s characters, and the band just below that "
        "floor is the worst-performing length measured in the whole corpus"
        % linkedincontract.bound_phrase(_LI_MSG_FLOOR)),
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
        # A parametrised contract code explains itself; the table cannot hold
        # an entry per word count.
        contract = explain_contract(code)
        if contract:
            line = contract
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


#: A contract refusal, parsed back out of its own code. The code is
#: parametrised - `em2_body_41_words_under_contract_45_to_90` - because a refusal
#: a reader cannot act on is the defect this module's EXPLAIN table was written
#: about. A bare `body_under_contract` would send the reader off to look up which
#: step it was, how long the body was and what the bounds are; the code says it.
CONTRACT_CODE_RE = re.compile(
    r"^(?P<step>em\d+)_body_(?P<words>\d+)_words_"
    r"(?P<side>under|over)_contract_(?P<low>\d+)_to_(?P<high>\d+)$")


def contract_code(step_key, words, low, high):
    """The refusal code for a body outside its own step's declared range."""
    side = "under" if words < low else "over"
    return "%s_body_%d_words_%s_contract_%d_to_%d" % (
        step_key, words, side, low, high)


def explain_contract(code):
    """One contract refusal as a sentence, naming the miss and its size."""
    found = CONTRACT_CODE_RE.match(str(code or ""))
    if not found:
        return None
    step = found.group("step")
    words, low, high = (int(found.group(g)) for g in ("words", "low", "high"))
    target = writercontract.word_target(step) or (low + high) // 2
    if found.group("side") == "under":
        miss = "%d words under the %d-word floor" % (low - words, low)
    else:
        miss = "%d words over the %d-word ceiling" % (words - high, high)
    return ("%s is %d words and its contract is %d to %d: %s. Rewrite it to "
            "about %d words. The floor is not the target"
            % (step, words, low, high, miss, target))


def check(rec, key, step, step_key=None):
    """Return the sorted, deduped failure codes for one generated email.

    `step_key` is this step's cadence key (`em1`..`em5`). It decides which entry
    of the writer's word contract applies and NOTHING else: every other rule in
    this function is identical for every step. Omitting it is safe - the key is
    recovered from the record by `step_key_of` - and a step whose key cannot be
    established keeps the `MIN_WORDS`..`MAX_WORDS` verdict it had before, which
    is the stricter floor, never a looser one.
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

    # THE EVERY-EMAIL BOUNDS, UNCHANGED. `MIN_WORDS` 40 and `MAX_WORDS` 180 are
    # the single-email draft shape and the floor under every email of every
    # shape, including the steps the contract does not name.
    words = len(countable_words(body))
    if words < MIN_WORDS:
        fails.add("body_too_short")
    if words > MAX_WORDS:
        fails.add("body_too_long")

    # THE WRITER'S DECLARED RANGE FOR THIS PARTICULAR STEP, ON TOP OF - never
    # instead of - the two bounds above. A twenty-word em2 fails `body_too_short`
    # AND its contract, deliberately: the new rule must not mask the old one. A
    # step outside the five named in `STEP_WORD_CONTRACT` - a `day1` draft, a
    # LinkedIn message - is not mentioned by this contract and keeps exactly the
    # verdict it had before.
    #
    # AND THE CONTRACT IS STRICTLY INSIDE 40..180 AT EVERY STEP, asserted rather
    # than assumed by `tests.test_word_contract_enforced
    # .TestTheContractNeverLoosensTheOldBounds`, so this pair of rules can only
    # ever refuse more than the pair above and never fewer.
    contract_step = step_key_of(rec, key, step, step_key)
    bounds = writercontract.word_range(contract_step)
    if bounds and body.strip():
        low, high = bounds
        if words < low or words > high:
            fails.add(contract_code(contract_step, words, low, high))

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

# THE FOUR CHARACTER CONSTANTS THAT WERE HERE ARE GONE, AND SO IS EVERY COPY
# OF THEM. `NOTE_MAX_CHARS` is now read from `LINKEDIN_CHAR_CONTRACT` at the
# top of this module, where the other three were refuted by measurement and
# are not replaced by second-guesses. See that block for each refutation and
# its sample size. A constant left behind here would be the two-authorities
# defect this repository has already paid for once.

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


def check_linkedin(rec, key, step, step_key=None):
    """Failure codes for one LinkedIn note or message, after expansion.

    `step_key` is this step's cadence key (`li1`..`li5`). It selects the row of
    `LINKEDIN_CHAR_CONTRACT` that applies and NOTHING else. Omitting it is
    safe: the key is recovered from the record by `step_key_of`, and a step
    whose key cannot be established is given the STRICTEST bounds any message
    role carries, never a looser one.
    """
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

    # THE MEASURED CHARACTER CONTRACT, AND NOTHING ELSE DECIDES LENGTH HERE.
    #
    # Which ROW applies is decided in two steps, and the order matters.
    # `is_connection_note` stays the authority on whether this step is the
    # request or a message - it reads `requires`, which survives the cadence
    # being reconfigured, and that design is unchanged. The cadence KEY is
    # consulted only to tell one message row from another.
    #
    # A bound that is UNKNOWN asserts nothing. It is not zero and it is not
    # permission: li1 has no measured floor, so a short note is not refused,
    # and if a floor is ever measured this branch starts refusing without any
    # other line changing.
    role = ("li1" if is_note
            else linkedincontract.contract_role(
                step_key_of(rec, key, step, step_key)))
    if not is_note and role in (None, "li1"):
        # Known to be a message, but which one could not be established.
        floor, ceiling = linkedincontract.strictest_message_bounds()
    else:
        floor, ceiling = linkedincontract.char_bounds(role)

    length = len(text)
    if ceiling is not linkedincontract.UNKNOWN and length > ceiling:
        fails.add("note_too_long" if is_note else "message_too_long")
    elif floor is not linkedincontract.UNKNOWN and length < floor:
        fails.add("note_too_short" if is_note else "message_too_short")

    return sorted(fails)


def classify_linkedin(failures):
    """Same three verdicts as email, with its own held set."""
    if not failures:
        return "clean"
    if set(failures) <= LINKEDIN_HELD_CODES:
        return "held"
    return "failed"


def check_step(rec, key, step, step_key=None):
    """Lint one step of either channel. The single door every step goes through.

    `step_key` threads to `check` and selects this step's entry of the writer's
    word contract, and to `check_linkedin` and selects this step's row of the
    LinkedIn character contract. Until 2026-10-03 the LinkedIn door ignored it
    and carried four flat constants instead; it now reads one measured
    contract, in the same shape and from one authority.
    """
    if (step or {}).get("channel") == "linkedin":
        return check_linkedin(rec, key, step, step_key=step_key)
    return check(rec, key, step, step_key=step_key)


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
        # step against its own entry of the writer's contract. Without this the
        # per-step contract would exist and the module's own report would not
        # use it, which is the "computed and nothing reads it" shape.
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
