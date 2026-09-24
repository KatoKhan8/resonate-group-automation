"""Is this the email a person should receive, or is it nothing at all?

ONE DEFINITION OF BLANK, USED BY BOTH CONTROLS. The push guard
(`bisonfactory`) and the watcher check (`scripts/bison_watch_loop.py`) ask the
same question of the same object, so they ask it through this module. Two
predicates that drift apart is how a guard reports clean on the case its
sibling halts.

## WHY THIS EXISTS

2026-09-22/23: 76 emails with subject `''` and body `'<p></p>'` were sent to
real prospects, and one of them replied. See
`docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.

The mechanism, measured rather than reasoned: our sequence steps are PURE
MERGE TEMPLATES - campaign 497 step 4769 is `{SUBJECT_1}` and
`<p>{BODY_1}</p>` verbatim at the provider. EmailBison substitutes the lead's
custom variables when it builds the `scheduled-emails` queue. A lead carrying
no `body_1` renders to `<p></p>`, and the provider sends that. Nothing on the
provider's side refuses an empty render, and the vendor documents no guard
that would (Grok research, 2026-09-23: injection timing, empty-variable
behaviour and any pre-send render readback are all NOT DOCUMENTED).

## WHAT THIS LOOKS AT, AND WHY IT IS THE ONLY OBJECT THAT ANSWERS

The RENDERED QUEUE ROW. Not the sequence, whose fields are placeholders on
both sides and compare equal on an empty render. Not the lead's variables,
because the render is a SNAPSHOT: leads 141278, 190068 and 140657 carry
correct copy today and still sent blank, because all three were patched up to
54 minutes AFTER the empty row had been queued and sent. Reading the lead
shows perfect copy and tells you nothing about what went out.

So: `email_subject` and `email_body` off `bison.scheduled_emails`, which is
the provider's own statement of what it will send, readable days ahead.

## THE FOUR SHAPES, AND WHY EACH IS HERE

`EMPTY`        `''`, whitespace, or HTML that renders to nothing - `<p></p>`,
               `<br>`, `&nbsp;`. This is what actually sent 76 times.
`LITERAL_NONE` the four-character string `None`, or `null`. Factory leads
               carry `'None'` in `body_4..6` and `subject_2..6` today. It did
               not cause the incident - those positions are not referenced by
               a three-step sequence - but it is one step of cadence growth
               from sending the word "None" to a prospect. The operator named
               it explicitly, and this is where it is caught.
`PLACEHOLDER`  an unresolved merge field still present in the RENDERED row
               (`{BODY_1}`, `{{FIRST_NAME}}`). The provider left the token
               because the variable did not exist. A prospect reading
               `{BODY_1}` is worse than one reading nothing, because it also
               tells them how the sausage is made.
`SUBJECT_RE`   a threaded follow-up whose subject rendered to `Re:` and
               nothing else. This is the empty case wearing the thread's
               clothes: every follow-up step references `{SUBJECT_1}`, so
               `Re: ` with nothing after it is `subject_1` resolving to
               nothing. Campaign 497's stopped rows read exactly that.

## WHAT IS DELIBERATELY NOT BLANK

An empty SUBJECT on a threaded follow-up whose template does not carry one.
`bisonfactory._variables_for` writes `subject_N = ""` for threaded positions
on purpose - the provider prepends `Re:` itself - so the absence is the
design rather than a fault. That case is distinguished by the row's own
`thread_reply` flag plus a subject that is empty rather than a bare `Re:`.
A body is never legitimately empty on any step, so `email_body` has no such
exemption.
"""

import re

EMPTY = "EMPTY"
LITERAL_NONE = "LITERAL_NONE"
PLACEHOLDER = "PLACEHOLDER"
SUBJECT_RE = "SUBJECT_RE_ONLY"

#: Values that are the string `None` rather than an absent value. Compared
#: casefolded and stripped. `str(None)` reaching a provider variable is the
#: fault this catches; `"none"` as a real word never appears alone in a
#: subject or body we would approve.
NONE_WORDS = frozenset({"none", "null", "nil", "undefined"})

#: HTML that renders to nothing. Matched as the WHOLE value after stripping,
#: never as a substring: a real body containing `<br>` is a real body.
_NOTHING = re.compile(r"\A(?:<[^>]*>|&nbsp;|&#160;|\s)*\Z", re.I)

#: An unresolved merge field, in either syntax the provider accepts.
_PLACEHOLDER = re.compile(r"\{\{?\s*[A-Za-z_][A-Za-z0-9_]*\s*\}?\}")

#: A subject that is nothing but a reply prefix.
_RE_ONLY = re.compile(r"\A\s*(?:re\s*:\s*)+\Z", re.I)


def _visible(value):
    """The text a person would actually see, tags and entities removed."""
    if value is None:
        return ""
    text = re.sub(r"<[^>]*>", "", str(value))
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.I)
    return text.strip()


def classify_subject(value, thread_reply=False):
    """Why this subject is not sendable, or None if it is fine.

    `thread_reply` marks a follow-up step. Those legitimately carry an empty
    subject variable - the provider supplies `Re:` from the thread - so an
    empty value on a threaded row is NOT a fault. A bare `Re:` still is: that
    is `{SUBJECT_1}` resolving to nothing, which means the opener's subject
    never reached this lead.
    """
    raw = "" if value is None else str(value)
    if _PLACEHOLDER.search(raw):
        return PLACEHOLDER
    if _RE_ONLY.match(raw):
        return SUBJECT_RE
    visible = _visible(raw)
    if visible.casefold() in NONE_WORDS:
        return LITERAL_NONE
    if not visible:
        return None if thread_reply else EMPTY
    return None


def classify_body(value):
    """Why this body is not sendable, or None if it is fine.

    No step has a legitimate empty body, threaded or not, so there is no
    exemption here and there must not be one.
    """
    raw = "" if value is None else str(value)
    if _PLACEHOLDER.search(raw):
        return PLACEHOLDER
    visible = _visible(raw)
    if visible.casefold() in NONE_WORDS:
        return LITERAL_NONE
    if not visible or _NOTHING.match(raw):
        return EMPTY
    return None


def classify_row(row):
    """`(field, reason)` pairs for one `scheduled_emails` row. Empty if fine.

    Reads the row's OWN `thread_reply` flag rather than being told, so a
    caller cannot accidentally exempt an opener.
    """
    threaded = bool(row.get("thread_reply"))
    found = []
    subject = classify_subject(row.get("email_subject"), thread_reply=threaded)
    if subject:
        found.append(("subject", subject))
    body = classify_body(row.get("email_body"))
    if body:
        found.append(("body", body))
    return found


#: Row statuses that are SETTLED - the row is a fact and cannot become a
#: message. A `sent` row has already gone, a `stopped` one cannot go, and a
#: `bounced` one went and failed. Everything else can still reach a person.
#:
#: THIS IS A DENYLIST, AND IT USED TO BE AN ALLOWLIST. Until 2026-09-24 the
#: rule was `PENDING_STATUSES = {"scheduled", "queued", "pending", ""}` and
#: every status outside it fell to `already` - the bucket whose own comment
#: read "already sent or stopped". `sending_paused` is neither. Campaign 491
#: was paused, so its whole queue read `sending_paused`, and blank row
#: 22356723 (lead 204724, `Re: ` / `<p></p>`) was filed as contained when the
#: only thing containing it was the campaign's pause. Resuming 491 would have
#: sent it. Both witnesses - the watcher heartbeat and a direct provider read
#: - agreed on "0 pending" and both were wrong in the same way, because they
#: share this predicate.
#:
#: An allowlist of sendable statuses fails CLOSED on a status nobody thought
#: of, and failing closed here means calling an unknown row safe. The
#: denylist fails the other way: a status this module has never seen is
#: treated as able to send, which at worst halts a campaign for a row that
#: was never going anywhere. Only a row that is BOTH faulty AND unsettled
#: halts anything, so an unrecognised status on well-rendered copy costs
#: nothing.
SETTLED_STATUSES = frozenset({"sent", "stopped", "bounced"})


def scan(rows):
    """Every offending row, split by whether it can still send.

    Returns `{"pending": [...], "already": [...]}`. Each entry is
    `{"row", "lead", "step", "status", "faults"}` and carries NO prospect
    identifier - ids only - so a caller may log it anywhere.

    THE CALLER DECIDES WHAT TO DO, and the split is what lets the watcher
    halt on `pending` while still reporting `already`. A scan that returned
    one list would make a campaign whose blanks have all been stopped look
    exactly like one about to send more.

    `already` MEANS SETTLED, NOT DORMANT. A row is `already` only when the
    provider says `sent`, `stopped` or `bounced` - see `SETTLED_STATUSES`.
    A paused campaign's rows are `sending_paused`, which is dormant: the only
    thing holding them is a campaign status an operator can change in one
    click. They count as `pending`.
    """
    pending, already = [], []
    for row in rows or []:
        faults = classify_row(row)
        if not faults:
            continue
        status = str(row.get("status") or "").strip().lower()
        lead = row.get("lead") or {}
        entry = {"row": row.get("id"),
                 "lead": lead.get("id") if isinstance(lead, dict) else None,
                 "step": row.get("sequence_step_id"),
                 "status": status,
                 "faults": faults}
        (already if status in SETTLED_STATUSES else pending).append(entry)
    return {"pending": pending, "already": already}


def summarise(found):
    """One line per bucket, for a log or an alert. No identifiers."""
    def counts(entries):
        tally = {}
        for entry in entries:
            for field, reason in entry["faults"]:
                key = f"{field}/{reason}"
                tally[key] = tally.get(key, 0) + 1
        return ", ".join(f"{k} x{v}" for k, v in sorted(tally.items())) or "none"
    return (f"pending {len(found['pending'])} ({counts(found['pending'])}); "
            f"already {len(found['already'])} ({counts(found['already'])})")
