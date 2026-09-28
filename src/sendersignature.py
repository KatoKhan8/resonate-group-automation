"""The sender's signature block, composed from the sender identity.

TASK-906.

THE RULE.  The signature is composed into our rendered copy and the
EmailBison projection, read from the canonical per-mailbox source, so
it is visible and verifiable BEFORE anything is sent.  No provider
signature configuration; no provider writes.

THE CONTENT.  Two lines: the mailbox owner's full name, then
``Productive``.  No title, no phone, no link.  The single-link rule
stands: the only link permitted anywhere is
``https://productive.io/get-started/``.

THE CHAIN.  owner -> identity -> signature -> rendered email ->
projection.  All five links must hold.  A break at any link is reported,
not silently degraded.

THE SOURCE.  ``clients.sender_identity(config)`` returns the sender
block from the client config.  The ``name`` field is the owner's full
name.  The company line is the fixed word ``Productive`` - it is not
read from the config because the config's ``name`` is the CLIENT's name,
not the product the sender works for.
"""

COMPANY_LINE = "Productive"


def compose(sender):
    """Compose the signature block from a sender identity dict.

    Returns a two-line string: the sender's full name, then
    ``Productive``, separated by a newline.  Returns an empty string
    when the sender has no name - a signature without a name is not
    a signature, and an invented name is somebody else's.

    The sender dict comes from ``clients.sender_identity(config)``.
    An empty dict or a dict without ``name`` returns empty.
    """
    name = ((sender or {}).get("name") or "").strip()
    if not name:
        return ""
    return f"{name}\n{COMPANY_LINE}"


def refuse_if_duplicate(body, signature):
    """Refuse a body that already carries the signature block.

    If the provider ever appends its own signature, our check must
    detect the duplicate and BLOCK.  A body already carrying the
    signature block is refused, not double-signed.

    Returns the body unchanged if the signature is absent.
    Raises SignatureDuplicate if the body already ends with the
    signature block.
    """
    sig = (signature or "").strip()
    if not sig:
        return body or ""
    body = body or ""
    if sig in body:
        raise SignatureDuplicate(
            f"body already contains the signature block; "
            f"refusing to double-sign")
    return body


class SignatureDuplicate(RuntimeError):
    """The body already carries a signature and must not receive another."""
