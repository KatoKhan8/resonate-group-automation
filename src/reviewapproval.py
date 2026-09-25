"""The operator's approval of a review file, as a mechanism rather than a habit.

OPERATOR DIRECTIVE, Zvonimir, 2026-09-25, standing and without exception:

    No campaign is activated and no lead is attached to an active campaign
    without a review file approved by me. Activation happens only after my
    reply "APPROVED <campaign> <file hash>". Production does not approve its
    own work.

WHY THIS IS CODE AND NOT A CHECKLIST.

On 2026-09-25 sixty-four emails went to real prospects from the client's
mailboxes carrying a DIFFERENT agency's pitch, signed with the operator's
name instead of the mailbox owner's, quoting navigation-bar text as the
personalised fact. Five samples were posted for veto and read. The reviewer
found a real defect in them - a step claiming to be the last one - and did not
notice that the product, the voice and the signature were all wrong.

The samples gate ran. It ran correctly. It was performed by the same session
that produced the copy, so there was no independent step in it anywhere, and
a reviewer checking their own work checks the things they were already
thinking about. That is what this module removes: approval now comes from
outside the process that made the thing, or the activation does not happen.

WHY IT HOOKS THE TRANSPORT AND NOT THE FACTORY.

`bisonfactory.stage` already carried a copy lint, a tenancy check, an approved
copy check and an empty-render refusal. **None of them ran**, because the push
that caused the incident used `bison.create_lead` and `bison.attach_leads`
directly and never entered the factory at all. A gate that lives in the
factory is a gate any script can walk around, and one did - written by the
same session that had merged the lint into the factory that morning.

So the check sits on the ACTIVATION CALL ITSELF. Every route to activation -
factory, script, notebook, a future runner nobody has written - goes through
`bison.resume_campaign` or `heyreach.activate_campaign`, and both ask here.

WHAT IT DELIBERATELY DOES NOT DO.

It does not judge the review file. It does not read the copy. It asks one
question - did the operator, by name, approve THIS campaign against THIS file
hash - and refuses when the answer is no. A gate that also formed an opinion
would be a second thing to get wrong.
"""
import hashlib
import json
import os

from . import store


class NotApproved(Exception):
    """Activation was attempted without the operator's approval record."""


#: Only this person's approval counts. An approval recorded by the production
#: session for its own work is the thing the incident was made of, so `by` is
#: checked against this and not merely required to be non-empty.
OPERATOR = "zvonimir"

#: Approvals live beside the queue, not in git: they name real campaigns and
#: are operational state rather than something that reconstructs the system.
FILENAME = "review-approvals.jsonl"


def path():
    return os.path.join(os.path.dirname(store.queue_path()), FILENAME)


def file_hash(path_or_bytes):
    """The hash the operator quotes back. sha256, hex, first 16 characters.

    Short enough to type into Slack, long enough that two different review
    files do not collide in any estate this will ever see.
    """
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as handle:
            data = handle.read()
    return hashlib.sha256(data).hexdigest()[:16]


def load():
    try:
        return store.read_jsonl(path())
    except FileNotFoundError:
        return []
    except Exception as e:                                    # noqa: BLE001
        # An unreadable approval file is not an absent one. Refusing to read
        # it as empty is the same argument `spendledger.load` makes: a control
        # that opens when its own state is damaged fails exactly when
        # something is already wrong.
        raise NotApproved(
            f"{path()} could not be read ({type(e).__name__}). Refusing to "
            f"treat unreadable approvals as absent ones") from None


def record(campaign, review_hash, by, source="slack", at=None, note="",
           pairs=None, held=None):
    """Write one approval. Returns the row.

    `campaign` is the PROVIDER campaign id as a string, because that is what
    the activation call knows. `review_hash` is what `file_hash` produced for
    the file that was actually posted.

    TRAINING CAPTURE (TASK-310). When `pairs` is given, each dict is written
    to ``work/training/pairs.jsonl`` as an approved training pair. When
    `held` is given, each dict is written to ``work/training/held.jsonl`` as
    a negative example. The capture is best-effort: a bad pair is skipped
    but the approval always succeeds, because an approval must never fail
    because its training row was malformed. A pair not written at approval
    time is gone for good.
    """
    who = str(by or "").strip().lower()
    if not who:
        raise ValueError("an approval with no author is not an approval")
    row = {"at": at or store.now(), "campaign": str(campaign),
           "review_hash": str(review_hash), "by": who,
           "source": source, "note": note}
    store.refuse_production_write(path())
    with store.lock(for_path=path()):
        with open(path(), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    # CAPTURE AFTER THE APPROVAL IS DURABLE. If the training write fails
    # the approval must still stand - the operator said yes, and that is
    # the event that matters.
    from . import training
    training.capture(row, pairs=pairs, held=held)
    return row


def approval_for(campaign, rows=None):
    """The operator's most recent approval for this campaign, or None."""
    campaign = str(campaign)
    found = None
    for row in (load() if rows is None else rows):
        if not isinstance(row, dict):
            continue
        if str(row.get("campaign")) != campaign:
            continue
        if str(row.get("by") or "").strip().lower() != OPERATOR:
            continue
        found = row
    return found


def require(campaign, review_hash=None, rows=None):
    """Raise `NotApproved` unless the operator approved this campaign.

    When `review_hash` is given it must MATCH. That is what makes the
    approval about a particular file rather than about the campaign in
    general: re-rendering the copy produces a new file, a new hash, and
    therefore needs a new approval. An approval that survived a re-render
    would approve words nobody read.
    """
    given = approval_for(campaign, rows=rows)
    if given is None:
        raise NotApproved(
            f"campaign {campaign} has no approval from {OPERATOR!r}. "
            f"Activation is refused: the operator approves the review file "
            f"before a campaign sends, and production does not approve its "
            f"own work")
    if review_hash is not None and str(given.get("review_hash")) != str(review_hash):
        raise NotApproved(
            f"campaign {campaign} was approved against review file "
            f"{given.get('review_hash')!r}, not {review_hash!r}. The copy has "
            f"changed since it was read. Post the new review file and get a "
            f"new approval rather than reusing the old one")
    return given
