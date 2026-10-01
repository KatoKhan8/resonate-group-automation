"""One appender for all prospect-facing trailing content.

TASK-906.  TASK-560 shipped ``_append_ps`` twice - ``src/render.py`` and
``src/bisonfactory.py`` - with byte-identical logic.  TASK-904 added the
opt-out on top.  TASK-906 adds the signature.  Three independent append
operations on the same body, on two surfaces (the rendered email and the
EmailBison projection), must produce byte-identical output.

ONE FUNCTION, ONE ORDER.  ``compose`` takes the raw body and every piece
of trailing content, applies them in the fixed order, and returns the
final body.  Both surfaces call the same function with the same inputs,
so they cannot drift apart.

THE ORDER IS LOAD-BEARING.

    body
    <blank line>
    CTA link           (the offer's one licensed URL, when it declares one)
    <blank line>
    signature          (sender's name + company - the sign-off)
    <blank line>
    P.S.               (a post-script addition)
    <blank line>
    opt-out line       (compliance footer)

A person reading the email sees the sign-off first, then the P.S., then
the compliance line.  Reversing any pair changes what a person reads and
breaks the byte-identical assertion between the two surfaces.

THE CTA LINK IS APPENDED HERE AND NOWHERE ELSE, AND NO MODEL EVER TYPES IT.

Measured 2026-09-30: not one of the five generated canary emails contained a
URL.  ``offer.cta_link`` was declared in ``config/clients/productive-offers.yaml``
and read by NOTHING except ``copylint``, which only validates URLs that are
already present - so ``check_cta_links([])`` passed vacuously and an offer with
a CTA shipped without one.

``src/copyprompts.py`` tells the writer "NEVER write a URL" and that rule is
CORRECT and stays: a model asked for a URL retypes it and gets it wrong
(measured 2026-09-25).  The link is therefore CONFIG, carried verbatim from the
offer record to the composed body by the same single composer that already owns
the signature and the opt-out.  ``append_cta`` copies the string; it never
formats, shortens, re-cases or appends a slash to it.

WHERE IT SITS, AND WHY.  Above the sign-off, because the link is part of the
ASK and a reader who has reached the signature has finished reading.  Below the
opt-out it would read as footer boilerplate.  The relative order of body,
signature, P.S. and opt-out is unchanged, so every existing byte-identity
assertion between the rendered email and the EmailBison projection still holds
for a step that carries no link.
"""

import re

from . import optout


#: A P.S. the writer already labelled, in any of the spellings it uses.
#: Matched so the label is normalised rather than doubled.
_PS_LABEL = re.compile(r"^\s*p\.?\s*s\.?\s*[:\-]?\s*", re.I)


def append_ps(body, ps):
    """Append a P.S. to the body, separated by a blank line.

    Consolidated from the two byte-identical copies that lived in
    ``src/render.py`` and ``src/bisonfactory.py``.  Neither module may
    hold its own copy; both import this one.

    THE LABEL IS THE RENDERER'S JOB, NOT THE WRITER'S.  Operator
    direction 2026-09-29: a P.S. must visibly render as ``P.S. <message>``
    and never as an unlabelled paragraph.  The writer sometimes typed the
    label and sometimes did not, so a reader got one or the other
    depending on the draft.  Any label the writer supplied is stripped and
    the canonical one applied, which also makes doubling ("P.S. P.S. ...")
    unreachable.  Both surfaces - the rendered email and the EmailBison
    projection - go through here, so they stay byte-identical.
    """
    ps = (ps or "").strip()
    if not ps:
        return body or ""
    ps = "P.S. " + _PS_LABEL.sub("", ps).strip()
    body = (body or "").rstrip()
    return f"{body}\n\n{ps}" if body else ps


def append_cta(body, cta_link):
    """Append the offer's CTA link to the body, separated by a blank line.

    THE STRING IS COPIED, NOT COMPOSED.  Whatever the offer record declares is
    what a prospect sees, byte for byte: no trailing slash is added or removed,
    no scheme is normalised, no anchor text is wrapped around it.  Only
    surrounding whitespace is stripped, because a YAML value can carry a
    trailing newline and a URL never legitimately has one.

    NO LINK, NO CHANGE.  An offer that declares no ``cta_link`` - every
    capability offer in the current library - composes exactly as it did
    before.  Absence is not an error here; it is the sequence gate's job to
    refuse a sequence whose offer DOES declare one and whose composed output
    carries none, and that gate reads the composed output rather than this
    argument.

    AN EMPTY BODY GETS NO LINK, which is `optout.append_opt_out`'s discipline
    rather than `append_ps`'s: a body that rendered to nothing must not be
    turned into an email consisting of one bare URL.  The empty body is refused
    upstream, and this function must not disguise it.
    """
    link = (cta_link or "").strip()
    body = (body or "").rstrip()
    if not link or not body:
        return body
    return f"{body}\n\n{link}"


def compose(body, ps=None, signature=None, cta_link=None):
    """Compose the full prospect-facing body.

    Applies trailing content in the fixed order: CTA link, signature, P.S.,
    then opt-out.  The CTA link and the signature are composed INTO the body
    before the P.S. so the ask and the sign-off sit between the body text and
    the post-script.

    Returns the final body string.  Both the rendered email and the
    EmailBison projection call this same function with the same inputs.
    """
    result = (body or "").rstrip()
    result = append_cta(result, cta_link)
    sig = (signature or "").strip()
    if sig and result:
        result = f"{result}\n\n{sig}"
    elif sig:
        result = sig
    result = append_ps(result, ps)
    result = optout.append_opt_out(result)
    return result
