"""The opt-out line every prospect-facing email carries.

TASK-904.

ONE PLACE for the wording. A wording change is one edit in this file and
nothing else. The constant is imported by the renderer (which appends it
to every body) and by the lint (which checks it is present exactly once).

REPLY-BASED, NOT A LINK. The single-CTA rule allows exactly one URL in
prospect-facing copy (``https://productive.io/get-started/``). The opt-out
is a plain-text instruction to reply STOP, not a hyperlink.

PROVISIONAL WORDING. The exact text is operator content and will be
confirmed or changed at artifact review.
"""

#: The opt-out line appended to every rendered email body.
OPT_OUT_LINE = "If this isn't relevant, reply STOP and I'll close the file."


def append_opt_out(body):
    """Append the opt-out line to a body, separated by a blank line.

    ALWAYS appends, even when the body already contains the line. The
    duplicate is the lint's job to catch: a body that already carries an
    opt-out AND receives another is a duplicate that must BLOCK, not
    silently de-duplicate. See TASK-904 acceptance 3.
    """
    body = (body or "").rstrip()
    if not body:
        return body
    return f"{body}\n\n{OPT_OUT_LINE}"
