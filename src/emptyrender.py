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

## THE SHAPES, AND WHY EACH IS HERE

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
`COLLAPSED`    a merge token that resolved to NOTHING inside copy that is
               otherwise present and grammatical. Added 2026-10-01, and the
               only shape here that the rendered row alone cannot see.

## THE FIFTH SHAPE, AND WHY THE FIRST FOUR ALL MISS IT

Every one of the four above needs a VISIBLE WOUND in the rendered row: an
empty value, the word `None`, a token the provider left behind, a bare `Re:`.
`COLLAPSED` leaves none of those. The sentence is present, correctly
punctuated, and short of exactly the word it was built around.

MEASURED 2026-10-01 ON THE LIVE PROVIDER. Internal EmailBison campaign 352 -
operator-declared internal, read-only, never written to - carries `{INDUSTRY}`
in the subject templates of parent step 4040's variants
(`docs/BISON-PROVIDER-TRUTH-2026-09-14.md`, lines 240-241, PROVIDER FACT). The
token rendered EMPTY in 100% of its uses, and 88 subject lines went out reading

    what we see with agencies

where an industry word should have stood. `classify_subject` returned CLEAN on
that string, and was right to: it is a correct English sentence. No predicate
over the rendered text ALONE can separate it from copy somebody wrote that way
on purpose, and banning the sentence would halt healthy campaigns.

THIS MATTERS BEYOND A MISSING WORD. The email package an operator approves is
read as full text, and a sentence that lost a word to a collapsed token can
read perfectly well while being false or vacuous - "I work with teams on
profitability" claims nothing, and "quick math on margins" names no business.
A residual that survives a human reading is the class that has to stop the
line rather than be documented.

## THE TWO WITNESSES, AND WHAT EACH CAN AND CANNOT DECIDE

The evidence is the TEMPLATE, not the rendered text, and both halves are
obtainable: `bison.sequence_steps` returns the stored `email_subject` and
`email_body` per step id, and `bison.scheduled_emails` returns the rendered row
carrying `sequence_step_id`. Measured on campaign 352, that id is the VARIANT
step's id and not the parent's, so the join is by id and never by order.

`collapsed_by_values`  CERTAIN. A token whose value is absent from the map,
                       empty, or whitespace cannot have rendered to anything,
                       and no reading of the output is needed to say so. Needs
                       the lead's variable map.
`collapsed_by_render`  STRUCTURAL, and needs nothing but the template and the
                       row. The literal words either side of the token are
                       ADJACENT in the rendered text, so the token contributed
                       no word. Certain where that context is found in the
                       output; UNDECIDABLE where it is not, which is what the
                       provider's own spintax (`{a|b}`) does to it.

UNDECIDABLE IS NEITHER CLEAN NOR A HALT. `classify_merge` returns
`MERGE_UNVERIFIED` for it and `classify_row` raises no fault, because halting
every spintax campaign in the estate on an open question is a worse failure
than the one this shape fixes. `merge_coverage` is where the open question is
reported, and it answers the only question that makes a clean report mean
anything: how many fields were actually DECIDED. Zero decided is not a pass,
for the same reason `blank_render_verified` is False on zero rows.

## WHICH CALL PATHS HAVE THE TEMPLATE, AND WHICH HAVE ONLY THE RENDER

`classify_row(row)` and `scan(rows)` WITHOUT `steps` are unchanged and cannot
see the fifth shape at all - there is no template in the argument, so there is
nothing to compare. That is the call shape
`bisonfactory._refuse_blank_render`, `scripts/bison_watch_loop.py` and
`scripts/qa/check_readback.py` all use today, so this shape is INERT on those
three paths until they read the sequence and pass it. Wiring them is a change
to those files and not to this one; it is stated here rather than assumed, and
`tests/test_a_collapsed_merge_token_is_not_clean_copy.py` asserts the gap so it
cannot be quietly forgotten.

`bisonfactory._verify_leads_carry_their_copy` already holds BOTH halves in one
scope - `plan["provider_sequence"]` and the `wanted` variable map - and so does
`scripts/stage_s7_copy.render`, which renders our own templates against a
`fields` dict. That renderer guards by hand, field by field (`if not industry:
return None, ...`), which is correct for the four fields it knows and inherits
nothing for a fifth; `collapsed_by_values` is the predicate it can use instead.

## WHAT IS DELIBERATELY NOT BLANK

An empty SUBJECT on a threaded follow-up whose template does not carry one.
`bisonfactory._variables_for` writes `subject_N = ""` for threaded positions
on purpose - the provider prepends `Re:` itself - so the absence is the
design rather than a fault. That case is distinguished by the row's own
`thread_reply` flag plus a subject that is empty rather than a bare `Re:`.
A body is never legitimately empty on any step, so `email_body` has no such
exemption.

AND THAT EXEMPTION EXTENDS TO THE FIFTH SHAPE, which is why the merge check
runs LAST of the five. A threaded step's template still references
`{SUBJECT_1}` while `_variables_for` deliberately writes `subject_N = ""`, so
the certain witness would see a collapsed token on every healthy follow-up in
the estate. The fifth shape is defined as a token that collapsed INSIDE copy
that is otherwise present: where there is no visible rendered text at all,
shapes one and four own the answer and this one stays silent.
"""

import re

EMPTY = "EMPTY"
LITERAL_NONE = "LITERAL_NONE"
PLACEHOLDER = "PLACEHOLDER"
SUBJECT_RE = "SUBJECT_RE_ONLY"

#: The fifth shape. A merge token the provider resolved to nothing, inside copy
#: that is otherwise present and grammatical.
COLLAPSED = "COLLAPSED_TOKEN"

#: NOT A FAULT. The template carries tokens and neither witness could decide
#: them - no value map, and the provider's spintax defeated the structural
#: check. It is reported so that "no collapsed tokens" cannot be read as "every
#: token verified", and it never halts anything.
MERGE_UNVERIFIED = "MERGE_UNVERIFIED"

#: Values that are the string `None` rather than an absent value. Compared
#: casefolded and stripped. `str(None)` reaching a provider variable is the
#: fault this catches; `"none"` as a real word never appears alone in a
#: subject or body we would approve.
NONE_WORDS = frozenset({"none", "null", "nil", "undefined"})

#: HTML that renders to nothing. Matched as the WHOLE value after stripping,
#: never as a substring: a real body containing `<br>` is a real body.
_NOTHING = re.compile(r"\A(?:<[^>]*>|&nbsp;|&#160;|\s)*\Z", re.I)

#: An unresolved merge field, in either syntax the provider accepts.
#:
#: THE GROUP IS THE TOKEN'S NAME, and it is one pattern rather than two on
#: purpose: the fifth shape needs the name, every pre-existing use of this
#: pattern is a truth test on `search`, and a second copy of the same regex is
#: how the "is this a token" question comes to have two answers.
#:
#: It does NOT match the provider's variant syntax - `{a|b}`, or
#: `{what we see with {INDUSTRY} agencies|...}` - because the whole brace
#: content has to be a single identifier. Only the `{INDUSTRY}` inside is a
#: token, which is correct: the outer braces are the provider's choice of
#: alternative, not a merge field.
_PLACEHOLDER = re.compile(r"\{\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}")

#: A subject that is nothing but a reply prefix.
_RE_ONLY = re.compile(r"\A\s*(?:re\s*:\s*)+\Z", re.I)

#: Any letter or digit. "The token contributed nothing" means the gap it left
#: in the rendered copy holds none of these - whitespace and the punctuation
#: the template put there itself do not count as a word.
_WORD = re.compile(r"[^\W_]")

#: How many words of literal copy either side of a token are used to find it in
#: the rendered text. Four is long enough to be unique inside a sentence and
#: short enough to survive the provider's own whitespace handling.
_CONTEXT_WORDS = 4


def _visible(value):
    """The text a person would actually see, tags and entities removed."""
    if value is None:
        return ""
    text = re.sub(r"<[^>]*>", "", str(value))
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.I)
    return text.strip()


def _flat(value):
    """`_visible`, with runs of whitespace collapsed and casefolded.

    FOR MATCHING ONLY, and never for a verdict about emptiness. The provider's
    render of an empty value leaves one space where the token stood, or two, or
    none - measured as all three across the estate - and a comparison that can
    tell those apart would answer differently about the same fault.
    """
    return re.sub(r"\s+", " ", _visible(value)).strip().casefold()


def token_names(template):
    """Every merge token in `template`, first-seen order, deduplicated."""
    seen, names = set(), []
    for name in _PLACEHOLDER.findall(template or ""):
        if name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


def collapsed_by_values(template, values):
    """`(collapsed, literal_none)` token names, judged against a value map.

    THE CERTAIN WITNESS. A token whose value is absent, empty or whitespace
    cannot have rendered to anything, and the rendered output does not need to
    be read to say so. This is the strongest answer available anywhere on this
    path, which is why a caller holding the map should pass it.

    NAMES MATCH CASEFOLDED, because the two sides disagree by convention and
    always have: templates shout `{INDUSTRY}` and the provider stores
    `industry`. A case-sensitive lookup would report every correctly rendered
    row collapsed, which is the false positive that halts a healthy campaign.

    A NAME THAT CASEFOLDS ONTO TWO KEYS IS AMBIGUOUS, and ambiguity counts as
    collapsed if either of them is blank: the provider picks one and we cannot
    know which, so the only safe reading is the one that halts.

    A value that is the WORD `None` is reported separately, as `literal_none`.
    It is not empty - it renders four characters into the sentence - and the
    existing whole-value check cannot see it there, because factory leads carry
    `'None'` in a variable and a sentence built around one reads "I work with
    None teams".
    """
    index = {}
    for key, value in (values or {}).items():
        index.setdefault(str(key).strip().casefold(), []).append(value)
    collapsed, literal_none = [], []
    for name in token_names(template):
        held = index.get(name.casefold())
        if not held:
            collapsed.append(name)
        elif any(not _visible(value) for value in held):
            collapsed.append(name)
        elif any(_visible(value).casefold() in NONE_WORDS for value in held):
            literal_none.append(name)
    return collapsed, literal_none


def _token_contexts(template):
    """`(name, before, after)` per token OCCURRENCE, as flattened word runs.

    CONTEXT STOPS AT THE NEIGHBOURING TOKEN. Words borrowed from across another
    token are not context, because that token may itself have collapsed and the
    check would then be reading its own fault as literal copy.
    """
    raw = template or ""
    spans = [(m.start(), m.end(), m.group(1))
             for m in _PLACEHOLDER.finditer(raw)]
    out = []
    for i, (start, end, name) in enumerate(spans):
        prev_end = spans[i - 1][1] if i else 0
        next_start = spans[i + 1][0] if i + 1 < len(spans) else len(raw)
        before = _flat(raw[prev_end:start]).split()
        after = _flat(raw[end:next_start]).split()
        out.append((name,
                    " ".join(before[-_CONTEXT_WORDS:]),
                    " ".join(after[:_CONTEXT_WORDS])))
    return out


def _collapsed_in_text(text, before, after):
    """True collapsed, False filled, None the render cannot say.

    COLLAPSED MEANS ADJACENT: the literal copy either side of the token sits
    together in the rendered text with nothing holding a letter or a digit
    between them, so the token put no word into the sentence.
    """
    if not before and not after:
        # The token IS the whole template, so its emptiness is the rendered
        # text's emptiness - which shapes one and four already own.
        return None if not text else False
    if before and after:
        at = 0
        while True:
            head = text.find(before, at)
            if head < 0:
                return None
            gap = head + len(before)
            tail = text.find(after, gap)
            if tail < 0:
                at = head + 1
                continue
            return not _WORD.search(text[gap:tail])
    if before:
        return text.endswith(before)
    return text.startswith(after)


def collapsed_by_render(template, rendered):
    """`(collapsed, undecided)` token names, from the template and render alone.

    THE WITNESS AVAILABLE WHERE THE VALUE MAP IS NOT, which on the queue path
    is most of the time: a `scheduled_emails` row carries `lead` but is not
    established to nest that lead's variables, and one local record of sent rows
    carries `lead_id: null` outright.

    WHAT IT CAN DECIDE: any token whose surrounding literal copy it can find in
    the output. That covers the measured campaign-352 shape exactly.

    WHAT IT CANNOT: a token inside the provider's variant syntax, where the
    alternative that was chosen is unknown, so the context being absent from
    the output means "a different variant ran" and not "the token collapsed".
    Those come back as `undecided`, never as a fault. It also cannot see a
    value that rendered the word `None`, because four characters in the gap
    look exactly like a word that was supposed to be there.
    """
    text = _flat(rendered)
    collapsed, undecided = [], []
    for name, before, after in _token_contexts(template):
        verdict = _collapsed_in_text(text, before, after)
        if verdict is True and name not in collapsed:
            collapsed.append(name)
        elif verdict is None and name not in undecided:
            undecided.append(name)
    return collapsed, [n for n in undecided if n not in collapsed]


def merge_detail(template, rendered=None, values=None):
    """What the witnesses say about one field's merge tokens.

    `{"tokens", "collapsed", "literal_none", "undecided", "witness"}`, and
    token NAMES only - never a value and never a line of copy - so a caller may
    log this anywhere, exactly as it may log a `scan` entry.

    A VALUE MAP IS TREATED AS COMPLETE EVIDENCE. A token missing from a map
    that was supplied is collapsed, not undecided: the provider had nothing to
    substitute either. A caller that holds only part of a lead's variables must
    pass None rather than a partial map, or it will refuse rows that are fine.
    """
    tokens = token_names(template)
    collapsed, literal_none, undecided, witness = [], [], [], []
    if values is not None:
        collapsed, literal_none = collapsed_by_values(template, values)
        witness.append("values")
    if rendered is not None:
        structural, unsure = collapsed_by_render(template, rendered)
        witness.append("render")
        collapsed = collapsed + [n for n in structural if n not in collapsed]
        if values is None:
            undecided = [n for n in unsure if n not in collapsed]
    elif values is None:
        undecided = list(tokens)
    return {"tokens": tokens,
            "collapsed": sorted(collapsed),
            "literal_none": sorted(n for n in literal_none
                                   if n not in collapsed),
            "undecided": sorted(undecided),
            "witness": witness}


def classify_merge(template, rendered=None, values=None):
    """Why this field's merge tokens are not sendable, or None if they are.

    `COLLAPSED`, then `LITERAL_NONE`, then `MERGE_UNVERIFIED`, then None. A
    template with no tokens is None and so is no template at all: there is
    nothing here that can be wrong about copy nobody merged into.
    """
    if not template:
        return None
    detail = merge_detail(template, rendered=rendered, values=values)
    if detail["collapsed"]:
        return COLLAPSED
    if detail["literal_none"]:
        return LITERAL_NONE
    if detail["undecided"]:
        return MERGE_UNVERIFIED
    return None


def _merge_fault(template, rendered, values):
    """The fifth shape's FAULT for one field, or None.

    `MERGE_UNVERIFIED` IS NOT A FAULT. A template neither witness can decide is
    an open question, and halting every spintax campaign in the estate on an
    open question is a worse failure than the one this shape fixes.
    `merge_coverage` is where that question is reported instead.
    """
    reason = classify_merge(template, rendered=rendered, values=values)
    return None if reason == MERGE_UNVERIFIED else reason


def classify_subject(value, thread_reply=False, template=None, values=None):
    """Why this subject is not sendable, or None if it is fine.

    `thread_reply` marks a follow-up step. Those legitimately carry an empty
    subject variable - the provider supplies `Re:` from the thread - so an
    empty value on a threaded row is NOT a fault. A bare `Re:` still is: that
    is `{SUBJECT_1}` resolving to nothing, which means the opener's subject
    never reached this lead.

    `template` and `values` ARE THE FIFTH SHAPE AND ARE BOTH OPTIONAL. Without
    `template` the answer is byte-identical to what this returned before the
    shape existed, because there is no second object to compare against. The
    merge check runs LAST, after all four of the older shapes, so a row that is
    empty is still reported EMPTY rather than relabelled - and so the threaded
    exemption above still holds, since an absent subject never reaches here.
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
    return _merge_fault(template, raw, values)


def classify_body(value, template=None, values=None):
    """Why this body is not sendable, or None if it is fine.

    No step has a legitimate empty body, threaded or not, so there is no
    exemption here and there must not be one.

    `template` and `values` carry the fifth shape, exactly as on the subject,
    and are optional in the same way and for the same reason.
    """
    raw = "" if value is None else str(value)
    if _PLACEHOLDER.search(raw):
        return PLACEHOLDER
    visible = _visible(raw)
    if visible.casefold() in NONE_WORDS:
        return LITERAL_NONE
    if not visible or _NOTHING.match(raw):
        return EMPTY
    return _merge_fault(template, raw, values)


def _step_for(row, steps):
    """The sequence step this row rendered FROM, or `{}` when unavailable.

    Takes the list `bison.sequence_steps` returns, or a mapping keyed by step
    id, and joins on the row's own `sequence_step_id`. THE JOIN IS BY ID AND
    CANNOT BE BY ORDER: measured on campaign 352, 42 of 60 sampled rows
    reference a VARIANT step directly rather than its parent, and each variant
    holds different template copy.
    """
    if not steps:
        return {}
    wanted = row.get("sequence_step_id")
    if wanted is None:
        return {}
    if isinstance(steps, dict):
        return steps.get(wanted) or steps.get(str(wanted)) or {}
    for step in steps:
        if isinstance(step, dict) and step.get("id") == wanted:
            return step
    return {}


def _values_of(row):
    """The merge values behind this row, or None when there are none to read.

    NONE AND `{}` MEAN DIFFERENT THINGS, and conflating them is how this check
    would come to report clean on the worst case it has. An empty map says
    every token in the template collapsed, which is exactly the 2026-09-23 lead
    (167865) carrying `headline`, `location` and no copy at all. None says the
    map was never seen, and the structural witness has to answer alone.

    WHETHER A LIVE QUEUE ROW CARRIES THE LEAD'S VARIABLES IS NOT ESTABLISHED.
    The incident fixtures carry `lead: {"id": ...}` and nothing more, and
    `work/INCIDENT-sent-rows.json` holds sent rows with `lead_id: null`. So a
    caller wanting the certain witness may have to read the lead itself and
    attach the map; both shapes are accepted, the provider's own
    `custom_variables` list of `{name, value}` and a plain mapping.
    """
    lead = row.get("lead")
    sources = [row.get("variables")]
    if isinstance(lead, dict):
        sources.append(lead.get("custom_variables"))
    for source in sources:
        if isinstance(source, dict):
            return source
        if isinstance(source, list):
            return {v.get("name"): v.get("value") for v in source
                    if isinstance(v, dict)}
    return None


def classify_row(row, steps=None):
    """`(field, reason)` pairs for one `scheduled_emails` row. Empty if fine.

    Reads the row's OWN `thread_reply` flag rather than being told, so a
    caller cannot accidentally exempt an opener.

    `steps` IS THE CAMPAIGN'S SEQUENCE, and it is what makes the fifth shape
    answerable: without it there is no template, so a collapsed token leaves
    nothing here to compare and this returns exactly what it returned before
    that shape existed. A caller that wants it reads `bison.sequence_steps` for
    the campaign once and passes the result.
    """
    threaded = bool(row.get("thread_reply"))
    step = _step_for(row, steps)
    values = _values_of(row)
    found = []
    subject = classify_subject(row.get("email_subject"), thread_reply=threaded,
                               template=step.get("email_subject"),
                               values=values)
    if subject:
        found.append(("subject", subject))
    body = classify_body(row.get("email_body"),
                         template=step.get("email_body"), values=values)
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


def scan(rows, steps=None):
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

    `steps` IS PASSED STRAIGHT THROUGH to `classify_row` and is what lets the
    fifth shape be seen at all. Without it this scan cannot detect a collapsed
    merge token - see `merge_coverage`, which is how a caller proves whether it
    looked rather than asserting that it did.
    """
    pending, already = [], []
    for row in rows or []:
        faults = classify_row(row, steps=steps)
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


def merge_coverage(rows, steps=None):
    """How much of the fifth shape was actually DECIDED, and by what.

    `{"rows", "fields", "decided", "collapsed", "undecided", "verified"}`,
    counted per FIELD rather than per row, because a step can carry tokens in
    its subject and its body and they fail independently.

    ZERO DECIDED IS NOT A PASS, for exactly the reason `blank_render_verified`
    is False on zero rows: a caller that reports "no collapsed tokens" after
    looking at no templates has reported nothing at all, and would go on
    reporting it for ever. `verified` is True only when at least one field was
    decided by at least one witness.
    """
    rows = list(rows or [])
    out = {"rows": len(rows), "fields": 0, "decided": 0, "collapsed": 0,
           "undecided": 0, "verified": False}
    for row in rows:
        step = _step_for(row, steps)
        values = _values_of(row)
        for field in ("email_subject", "email_body"):
            template = step.get(field)
            if not template or not token_names(template):
                continue
            out["fields"] += 1
            detail = merge_detail(template, rendered=row.get(field),
                                  values=values)
            if detail["collapsed"]:
                out["collapsed"] += 1
            if detail["undecided"]:
                out["undecided"] += 1
            else:
                out["decided"] += 1
    out["verified"] = out["decided"] > 0
    return out


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
