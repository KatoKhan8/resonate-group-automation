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

from . import identity, store

# Section 6.2. Never widen one of these to make a draft pass. Regenerate the draft.
MIN_WORDS = 40
MAX_WORDS = 180
MAX_SUBJECT = 60          # "under 60 characters": 59 passes, 60 fails
DASHES = ("—", "–")

BANNED_PHRASES = (
    "i hope this email finds you well", "i wanted to reach out", "circling back",
    "just following up", "touching base", "as per my last email", "synergy",
    "game-changer",
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


def sendable(contact):
    """Section 6.1, decided in one place.

    The rule itself now lives in src/verification.py, which is the only module
    allowed to conclude that an address may be written to. This stays as the
    name the rest of the codebase already calls, and delegates.
    """
    from . import verification
    return verification.is_sendable(contact)


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


def check(rec, key, step):
    """Return the sorted, deduped failure codes for one generated email."""
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
    elif not sendable(contact):
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

    if any(d in body or d in subject for d in DASHES):
        fails.add("em_dash")
    if ATTACHMENT_RE.search(body):
        fails.add("attachment")
    # "no unfilled placeholder" is not scoped to the body: a subject line is
    # the most visible place for one.
    if PLACEHOLDER_RE.search(body) or PLACEHOLDER_RE.search(subject):
        fails.add("placeholder")

    words = len(body.split())
    if words < MIN_WORDS:
        fails.add("body_too_short")
    if words > MAX_WORDS:
        fails.add("body_too_long")

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
    if lane == "domains" and any(not c.get("angle") for c in rec.get("contacts") or []):
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


def is_connection_note(step):
    return (step or {}).get("requires") != CONNECTION_ACCEPTED


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
    if any(d in text for d in DASHES):
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


def check_step(rec, key, step):
    """Lint one step of either channel. The single door every step goes through."""
    if (step or {}).get("channel") == "linkedin":
        return check_linkedin(rec, key, step)
    return check(rec, key, step)


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
        failures = check(rec, key, step)
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
