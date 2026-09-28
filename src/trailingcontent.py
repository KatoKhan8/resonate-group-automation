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
    signature          (sender's name + company - the sign-off)
    <blank line>
    P.S.               (a post-script addition)
    <blank line>
    opt-out line       (compliance footer)

A person reading the email sees the sign-off first, then the P.S., then
the compliance line.  Reversing any pair changes what a person reads and
breaks the byte-identical assertion between the two surfaces.
"""

from . import optout


def append_ps(body, ps):
    """Append a P.S. to the body, separated by a blank line.

    Consolidated from the two byte-identical copies that lived in
    ``src/render.py`` and ``src/bisonfactory.py``.  Neither module may
    hold its own copy; both import this one.
    """
    ps = (ps or "").strip()
    if not ps:
        return body or ""
    body = (body or "").rstrip()
    return f"{body}\n\n{ps}" if body else ps


def compose(body, ps=None, signature=None):
    """Compose the full prospect-facing body.

    Applies trailing content in the fixed order: P.S., then opt-out.
    The signature is composed INTO the body before the P.S. so the
    sign-off sits between the body text and the post-script.

    Returns the final body string.  Both the rendered email and the
    EmailBison projection call this same function with the same inputs.
    """
    result = (body or "").rstrip()
    sig = (signature or "").strip()
    if sig and result:
        result = f"{result}\n\n{sig}"
    elif sig:
        result = sig
    result = append_ps(result, ps)
    result = optout.append_opt_out(result)
    return result
