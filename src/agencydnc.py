#!/usr/bin/env python3
"""An agency-wide do-not-contact list that leaks nothing between clients.

## The requirement, and why it is awkward

Somebody tells Resonate - not a client, Resonate - never to contact them
again. That has to hold whichever workspace next imports them. A per-client
suppression list cannot do it, because client B has never heard of the
request and would import them tomorrow.

The obvious implementation is a shared table of people. That is the one thing
this must not be. Workspace B asking "may I contact sarah@acme.test" and
being told "no, she replied to Productive on 5 August" has just learned who
another client is talking to, which is exactly the leak the whole tenancy
model exists to prevent.

## What is stored

A one-way hash of a strong identifier, and a category. Nothing else.

    sha256("email:sarah@acme.test")  ->  {"reason": "requested", "at": ...}

No name. No company. No workspace. No campaign. No record id. No plaintext
identifier. The file cannot be read to enumerate anybody: answering "is this
person on the list" requires already knowing the identifier, which the
workspace asking has, because they are holding the row.

That is the whole privacy model, and it is worth stating what it does and
does not buy. It is not encryption: somebody with a list of candidate
addresses can test each one, exactly as the importing workspace does. What it
prevents is the file itself being a directory of other clients' prospects,
and a lookup returning anything beyond yes.

## What a workspace is told

`SUPPRESSED BY AGENCY SAFETY POLICY`, and the reason category. Never who
asked, never when they were last contacted, never by whom. `reason` is a
closed vocabulary for the same reason: a free-text note is where somebody
eventually writes "replied to Productive".

## What it is not

Not a mirror of reply state. A reply in one workspace does **not** put
anybody here - that is the client's business and stays inside their tenancy.
Only a request made to the agency does, and it is written deliberately by a
super admin, never derived.
"""
import hashlib
import json
import os

from . import dedupe, linkedin, store

# Why somebody is on the list. Closed, because a free-text reason is where a
# client's private history eventually gets written down.
REQUESTED = "requested"           # they asked Resonate directly
LEGAL = "legal"                   # a legal or regulatory instruction
COMPLAINT = "complaint"           # a complaint we are honouring
INTERNAL = "internal"             # our own decision - a competitor, a partner
REASONS = (REQUESTED, LEGAL, COMPLAINT, INTERNAL)

REASON_LABEL = {
    REQUESTED: "asked us directly",
    LEGAL: "legal or regulatory",
    COMPLAINT: "complaint",
    INTERNAL: "internal decision",
}

# What any workspace is told. One sentence, no detail, deliberately.
NOTICE = "suppressed by agency safety policy"


def path():
    """Resolved per call so tests can point it somewhere disposable."""
    # Beside the queue, not beside the repository. `store.queue_path()` is
    # already redirected by every test and by any deployment that moves its
    # state, so this follows it - a path anchored to `store.ROOT` wrote a
    # test's provider outbox into the working copy.
    return os.path.abspath(
        os.environ.get("AGENCY_DNC")
        or os.path.join(os.path.dirname(store.queue_path()), "agency-dnc.jsonl"))


def fingerprint(kind, value):
    """The stored key. One-way, and salted by nothing on purpose.

    A per-install salt would stop an attacker with the file from testing
    guesses, and would also stop the file being portable between the CLI and
    the web process, which is where it has to work. The threat this addresses
    is a *reader of the file* enumerating clients' prospects, not an attacker
    who already has both the file and a candidate list.
    """
    return hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()


def keys_for(candidate):
    """Every hashed key a candidate row could match on.

    Strong identity only, exactly as `dedupe` defines it. A name never
    reaches this function, so a name can never suppress anybody.
    """
    out = {}
    email = dedupe.normalise_email(candidate.get("email"))
    if email:
        out[f"email:{email}"] = fingerprint("email", email)
    profile = linkedin.canonical(candidate.get("linkedin"))
    if profile:
        out[f"linkedin:{profile}"] = fingerprint("linkedin", profile)
    return out


def load(file_path=None):
    """The index, as {fingerprint: {reason, at}}. Missing file is empty."""
    file_path = file_path or path()
    if not os.path.exists(file_path):
        return {}
    out = {}
    with open(file_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue                    # a corrupt line suppresses nobody
            key = row.get("fingerprint")
            if key:
                out[key] = {"reason": row.get("reason") or REQUESTED,
                            "at": row.get("at")}
    return out


def add(kind, value, reason=REQUESTED, at=None, file_path=None):
    """Put one identifier on the list. Append-only; nothing is rewritten.

    Returns the fingerprint written. The plaintext `value` is used to compute
    it and is never stored.
    """
    if kind not in ("email", "linkedin"):
        raise ValueError(f"identity kind must be email or linkedin: {kind!r}")
    if reason not in REASONS:
        raise ValueError(f"unknown reason: {reason!r}")
    value = (dedupe.normalise_email(value) if kind == "email"
             else linkedin.canonical(value))
    if not value:
        raise ValueError("not a usable identifier")
    digest = fingerprint(kind, value)
    file_path = file_path or path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"fingerprint": digest, "reason": reason,
                                 "at": at or store.now()},
                                sort_keys=True) + "\n")
    return digest


def lookup(candidate, index=None):
    """Is this row suppressed agency-wide? A sentence, or None.

    The return value is deliberately thin. It says that the row is
    suppressed and which category, and there is no argument that would make
    it say more, because there is nothing more in the file to say.
    """
    index = load() if index is None else index
    for _plain, digest in keys_for(candidate).items():
        hit = index.get(digest)
        if hit:
            label = REASON_LABEL.get(hit["reason"], hit["reason"])
            return f"{NOTICE} ({label})"
    return None


class Index:
    """A loaded index with the shape `hygiene.check` expects.

    `hygiene` asks `agency.get(key)` for a plaintext key like
    `email:sarah@acme.test`; this hashes it on the way in, so the plaintext
    never has to be stored anywhere for the lookup to work.
    """

    def __init__(self, index=None):
        self._index = load() if index is None else index

    def __len__(self):
        return len(self._index)

    def get(self, plain_key):
        kind, _, value = str(plain_key).partition(":")
        if kind not in ("email", "linkedin") or not value:
            return None
        hit = self._index.get(fingerprint(kind, value))
        if not hit:
            return None
        label = REASON_LABEL.get(hit["reason"], hit["reason"])
        return f"{NOTICE} ({label})"
