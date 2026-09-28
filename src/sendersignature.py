#!/usr/bin/env python3
"""Which signature THIS EXACT sender's mail carries, or a named refusal.

## The link this module is

    mailbox owner -> canonical sender identity -> the signature stored at the
    REAL source of truth for that exact sender -> the rendered final email ->
    the same signature in the EmailBison projection

`TASK-425` acceptance criterion 2. Until this module existed the middle of
that chain had **no implementation at all**: `email_signature` appeared exactly
once in `src/`, in a docstring example in `src/slackagenttools.py`, so nothing
in the pipeline had ever read the field. The blocker was therefore never only
missing data, and filling the data at the provider does not on its own move it.

## THE SOURCE OF TRUTH, NAMED, AND THE THREE THINGS THAT ARE NOT IT

The signature for a mailbox is **EmailBison's `email_signature` field on that
mailbox's `sender_email` object**, read through `bison.sender_emails()` - a
GET-only, fully-paginated read that refuses a partial inventory.

    NOT the authority   our `senderidentity` account row (it has no signature
                        field at all, measured across 225 productive rows)
    NOT the authority   the client YAML's `sender` block (no signature field;
                        `mode: client_rep` says the sending inbox adds it)
    NOT the authority   an operator statement that signatures were added. That
                        is a claim about reality, and this module reads reality.

**No signature is hardcoded, defaulted or synthesised anywhere here.** What a
sender's signature says is the operator's and the client's decision; a default
would manufacture the exact defect launch blocker 3 describes, and a fallback
would make an unattributed mailbox look attributed. Every failure is a named
refusal instead.

## WHY A SHARED SIGNATURE IS A REFUSAL AND NOT A PASS

`email_signature` is only evidence about identity while it DISCRIMINATES. A
block used by two different owners attributes nothing: the mail it signs could
be either person's, and reporting it as "that sender's signature" would be the
same-value-different-authority error `TASK-462` exists to fix one level down.
So a signature resolving to more than one owner is `AMBIGUOUS`, which fails
closed, rather than being returned because it is non-empty.

That check is measured rather than assumed: on 2026-09-28 the provider's 222
productive inboxes carried 11 distinct signatures across 11 display names, one
signature per name and no sharing, so the field discriminates in this estate.
The refusal is kept because that is a property of today's data and not of the
schema.
"""

import os

from . import senderidentity as si, senderownership as so

#: The field on EmailBison's `sender_email` object that holds the block. Named
#: once, here, so the join has exactly one spelling to break.
PROVIDER_FIELD = "email_signature"

#: EmailBison's own id for a mailbox, as it appears on a `sender_email` row.
#: Our canonical account row stores the same value in `provider_account_id`,
#: and that pair IS the join. Both are named here so the mapping is one
#: statement rather than a string repeated at four call sites.
PROVIDER_ID_FIELD = "id"
CANONICAL_ID_FIELD = "provider_account_id"

OK = "OK"
NO_OWNER = "NO_OWNER"
NO_CANONICAL_HUMAN = "NO_CANONICAL_HUMAN"
NO_PROVIDER_ROW = "NO_PROVIDER_ROW"
SIGNATURE_ABSENT = "SIGNATURE_ABSENT"
SIGNATURE_EMPTY = "SIGNATURE_EMPTY"
SIGNATURE_AMBIGUOUS = "SIGNATURE_AMBIGUOUS"

#: The five links, in order. A report names the FIRST one that failed, because
#: a later link measured on an unresolved earlier one is not a measurement.
LINKS = ("owner", "identity", "signature", "rendered", "projection")


def normalise(value):
    """Whitespace-collapsed comparison form. Never a value's only spelling.

    Two renderings of one block differ by indentation alone often enough that
    comparing raw bytes reports a mismatch where there is none. Collapsing is
    the comparison, not a rewrite: the stored value is what gets carried.
    """
    return " ".join(str(value or "").split())


def index_provider(provider_rows):
    """`{provider mailbox id: the row}`, keyed the way the join reads it.

    THE MAPPING THE MUTATION TEST BREAKS. `provider_account_id` on our row and
    `id` on the provider's row are the same number, and joining on anything
    else - the address, the position in the list, the display name - pairs a
    sender with somebody else's signature while every count still looks right.
    """
    out = {}
    for row in provider_rows or ():
        ident = str(row.get(PROVIDER_ID_FIELD) or "").strip()
        if ident:
            out[ident] = row
    return out


def provider_row_for(account, provider_index):
    """The provider's own row for THIS canonical mailbox, or None."""
    ident = str((account or {}).get(CANONICAL_ID_FIELD) or "").strip()
    return (provider_index or {}).get(ident) if ident else None


def owners_of_signature(accounts, rows, provider_index):
    """`{normalised signature: {owner sender_id, ...}}`.

    The discrimination measurement. A key with more than one owner cannot
    attribute the mail it signs, which is what makes `AMBIGUOUS` a refusal.
    """
    out = {}
    for account in accounts or ():
        row = provider_row_for(account, provider_index)
        if not row:
            continue
        sig = normalise(row.get(PROVIDER_FIELD))
        if not sig:
            continue
        owner = so.resolve_owner(account, rows)
        if owner:
            out.setdefault(sig, set()).add(owner)
    return out


def signature_for(account, rows, provider_index, signature_owners=None):
    """This mailbox's signature and its status. Fails closed, never defaults.

    Returns `(signature_or_None, status, note)`. A non-`OK` status always
    carries `None` as the signature: a caller cannot accidentally render a
    refusal's explanation at the bottom of an email.
    """
    owner = so.resolve_owner(account, rows)
    if not owner:
        return None, NO_OWNER, (
            "no owner resolves for account %r: neither its own sender_id nor "
            "an ownership attestation names a human, so there is no sender "
            "whose signature this would be"
            % (account or {}).get("account_id"))
    workspace = (account or {}).get("workspace")
    if not si.sender(workspace, owner, rows=rows):
        return None, NO_CANONICAL_HUMAN, (
            "account %r is attested to sender %r, who is not a canonical "
            "human in workspace %r"
            % ((account or {}).get("account_id"), owner, workspace))

    row = provider_row_for(account, provider_index)
    if row is None:
        return None, NO_PROVIDER_ROW, (
            "the source of truth has no mailbox %r: our canonical row claims "
            "provider account %r and the provider's inventory does not carry "
            "it, so its signature is UNKNOWN rather than absent"
            % ((account or {}).get("account_id"),
               (account or {}).get(CANONICAL_ID_FIELD)))
    if PROVIDER_FIELD not in row:
        return None, SIGNATURE_ABSENT, (
            "the provider row for mailbox %r carries no %r field at all"
            % ((account or {}).get(CANONICAL_ID_FIELD), PROVIDER_FIELD))
    signature = row.get(PROVIDER_FIELD)
    if not normalise(signature):
        return None, SIGNATURE_EMPTY, (
            "mailbox %r stores an empty %r. An empty signature is a BLOCK, "
            "not a signature, and no default is supplied here"
            % ((account or {}).get(CANONICAL_ID_FIELD), PROVIDER_FIELD))

    if signature_owners is not None:
        sharers = signature_owners.get(normalise(signature)) or set()
        if len(sharers) > 1:
            return None, SIGNATURE_AMBIGUOUS, (
                "mailbox %r stores a signature shared by %d owners (%s). A "
                "block used by more than one human attributes nothing, so it "
                "is not this sender's signature"
                % ((account or {}).get(CANONICAL_ID_FIELD), len(sharers),
                   ", ".join(sorted(sharers))))
    return signature, OK, "read from %s.%s for mailbox %s" % (
        "sender_email", PROVIDER_FIELD, (account or {}).get(CANONICAL_ID_FIELD))


def carries(text, signature):
    """Does this rendered text carry THIS signature?

    Substring on the normalised forms, deliberately: a rendered email is the
    body with the block appended, so containment is the question, and
    equality would refuse every real message. `signature` empty returns False
    rather than True - the empty string is a substring of everything, and
    reading that as "the signature is present" is precisely the
    guard-that-cannot-fail shape launch blocker 3 was hiding behind.
    """
    sig = normalise(signature)
    if not sig:
        return False
    return sig in normalise(text)


def signature_in_projection(steps, signature, lead_variables=None):
    """Is this signature anywhere in the EmailBison projection for a sender?

    Reads the projection's own step fields and, because the projection is a
    template of merge fields whose words travel per lead, the lead's custom
    variables too. Reporting a template placeholder as "no signature" would be
    true of every campaign ever staged and would prove nothing.
    """
    sig = normalise(signature)
    if not sig:
        return False
    for step in steps or ():
        for value in (step or {}).values():
            if carries(value, sig):
                return True
    for entry in lead_variables or ():
        if isinstance(entry, dict):
            if carries(entry.get("value"), sig):
                return True
        elif carries(entry, sig):
            return True
    return False


def chain_for(account, rows, provider_index, *, signature_owners=None,
              rendered=None, projection_steps=None, lead_variables=None):
    """All five links for ONE mailbox. Every link named, no link inferred.

    `rendered` is the final message text the pipeline would send for this
    sender - the projection's template with this lead's own variables
    resolved. It is passed in rather than built here because the renderer is
    not this module's to own, and a verifier that renders its own input is
    verifying itself.
    """
    result = {
        "account_id": (account or {}).get("account_id"),
        "provider_account_id": (account or {}).get(CANONICAL_ID_FIELD),
        "owner": so.resolve_owner(account, rows),
        "links": {},
        "failed_link": None,
        "status": None,
        "note": None,
    }
    signature, status, note = signature_for(
        account, rows, provider_index, signature_owners=signature_owners)
    result["status"], result["note"] = status, note
    result["signature_present_at_source"] = signature is not None

    result["links"]["owner"] = (status != NO_OWNER)
    result["links"]["identity"] = (
        result["links"]["owner"] and status not in
        (NO_CANONICAL_HUMAN, NO_PROVIDER_ROW))
    result["links"]["signature"] = (status == OK)
    result["links"]["rendered"] = bool(
        status == OK and carries(rendered, signature))
    result["links"]["projection"] = bool(
        status == OK
        and signature_in_projection(projection_steps, signature,
                                    lead_variables=lead_variables))

    for link in LINKS:
        if not result["links"][link]:
            result["failed_link"] = link
            break
    result["pass"] = result["failed_link"] is None
    return result


def load_provider_rows(expect_workspace=None, env_path=None):
    """The source of truth, read. GET only; this module never writes.

    Separated from every function above so the whole chain can be evaluated
    against rows a test supplies, without a test ever being able to pass
    itself off as the provider inside `signature_for`.
    """
    from .providers import bison, load_env

    if env_path:
        load_env(env_path)
    rows, meta = bison.sender_emails(expect_workspace=expect_workspace)
    return rows, meta


def accounts_and_rows(workspace):
    """Canonical mailboxes and the roster they live in."""
    rows = si.load()
    return si.email_accounts(workspace, rows=rows), rows


def env_default():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "config", ".env")
