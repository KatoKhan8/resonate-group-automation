#!/usr/bin/env python3
"""Why this workspace is worked the way it is.

## The question this answers

Six months after somebody set the minimum company size to 50, the setting
is still there and the reason is not. The audit log says who changed it and
when, which is the wrong half: nobody disputes that it was changed, they
want to know whether the reason still holds.

So this is decision memory. Not what the configuration *is* - `settings`
already shows that, and it is the authority - but what somebody believed
when they set it, and what that belief rested on.

## It decides nothing

The most important thing about this module is what it does not do.
Recording "we are moving up-market to 100+ employees" changes no threshold,
excludes no company and blocks no send. It is a note about intent, and the
configuration remains the only thing that acts.

That separation is deliberate. A decision store that also enforced would be
a second configuration system, quietly disagreeing with the first, and the
one nobody thinks to check when a campaign behaves oddly. `current()`
returns what was decided; `workspaces.POLICY_KEYS` returns what is in
force; the settings screen shows them side by side and says when they have
drifted apart.

## Evidence, or an honest admission that there is none

Every decision carries a basis, and one of the allowed bases is "judgement,
nothing measured". That option exists because it is frequently the true
answer, and a required field with no honest option is a field that gets
filled with plausible-sounding fiction.

The distinction the reader needs is not "good decision" versus "bad
decision". It is *this rested on 40 replies* versus *this was somebody's
instinct in March*, because only the first can be re-examined by looking at
data, and only the second needs to be re-argued.

## Superseded, never edited

A decision that turned out wrong is not deleted or corrected in place. It
is superseded by a new one, and both stay. "We believed X, then we learned
Y" is the entire value of a decision log; a log that only shows the current
belief is a configuration file with worse ergonomics.

This is the retraction path that `signals` does not have yet - see
PRODUCT-GAPS.md - and it is built in here from the start for the same
reason it is missing there: append-only storage makes withdrawal a row,
not a delete.
"""
import json
import os

from . import store

# ------------------------------------------------------------ what a decision is about
#
# Named for the question it settles rather than for the screen it appears
# on, so a decision keeps its meaning when the interface changes.

TARGETING = "targeting"        # who we go after, and who we stopped going after
CHANNEL = "channel"            # email, LinkedIn, the mix, and why
MESSAGING = "messaging"        # which angle leads, what we stopped saying
CADENCE = "cadence"            # how many touches, how far apart
SPEND = "spend"                # what we will pay per company, and the ceiling
QUALIFICATION = "qualification"  # what counts as a fit at all
OPERATIONS = "operations"      # how the work is run: volumes, senders, timing

AREAS = (TARGETING, CHANNEL, MESSAGING, CADENCE, SPEND, QUALIFICATION,
         OPERATIONS)

AREA_LABEL = {
    TARGETING: "Who we target",
    CHANNEL: "Which channels",
    MESSAGING: "What we lead with",
    CADENCE: "How we follow up",
    SPEND: "What we spend",
    QUALIFICATION: "What counts as a fit",
    OPERATIONS: "How the work is run",
}

# ------------------------------------------------------------- what it rests on

MEASURED = "measured"          # numbers from this workspace's own results
CLIENT = "client"              # the client told us
RESEARCH = "research"          # desk research, a source we can point at
JUDGEMENT = "judgement"        # somebody's read of it, nothing measured
BASES = (MEASURED, CLIENT, RESEARCH, JUDGEMENT)

BASIS_LABEL = {
    MEASURED: "Measured in this workspace",
    CLIENT: "The client asked for it",
    RESEARCH: "Desk research",
    # Said plainly. The alternative is a decision that looks evidenced
    # because the field was mandatory.
    JUDGEMENT: "Judgement, nothing measured",
}

# A basis that can be re-examined by looking at data, versus one that has to
# be re-argued. The distinction the reader actually needs.
CHECKABLE = (MEASURED, RESEARCH)

MINIMUM_DECISION = 12
MINIMUM_WHY = 12


class DecisionRefused(ValueError):
    """The decision was not recorded, and the message says what was wrong."""


def decision(workspace, area, *, decided=None, why=None, basis=JUDGEMENT,
             evidence=None, policy_key=None, decided_by=None, at=None,
             supersedes=None):
    """One decision. What was decided, and what it rested on.

    `decided` and `why` are both required and both have to be long enough
    to mean something, because "yes" in either field produces a log that
    records that a decision happened without recording the decision.
    """
    if area not in AREAS:
        raise DecisionRefused(f"unknown area: {area}")
    if basis not in BASES:
        raise DecisionRefused(f"unknown basis: {basis}")

    decided = (decided or "").strip()
    why = (why or "").strip()
    if len(decided) < MINIMUM_DECISION:
        raise DecisionRefused(
            "say what was decided, in a sentence somebody could act on")
    if len(why) < MINIMUM_WHY:
        raise DecisionRefused(
            "say why. A decision with no reason recorded cannot be "
            "re-examined later, only obeyed or overturned")
    if basis in CHECKABLE and not (evidence or "").strip():
        raise DecisionRefused(
            f"a {basis} decision has to say what the evidence was - the "
            "numbers, or the source. Otherwise record it as judgement")

    return {
        "workspace": workspace,
        "area": area,
        "decided": decided[:600],
        "why": why[:600],
        "basis": basis,
        "evidence": (evidence or "").strip()[:600] or None,
        # Which setting this explains, when it explains one. A decision
        # need not point at a policy key - "we stopped chasing agencies
        # under 20 people" may be a targeting choice with no switch - but
        # when it does, the settings screen can say so.
        "policy_key": policy_key or None,
        "decided_by": decided_by,
        "at": at or store.now(),
        # Set on the older row when a new decision replaces it. Never a
        # delete: "we believed X, then we learned Y" is the point.
        "superseded_by": None,
        "supersedes": supersedes or None,
        "id": None,
    }


# ------------------------------------------------------------------ storage

def path():
    """Beside the queue, like every other piece of state.

    Resolved from `store.queue_path()` rather than `store.ROOT`, because
    anchoring to ROOT is how a test writes into the real `work/`.
    """
    return os.path.abspath(
        os.environ.get("GTM")
        or os.path.join(os.path.dirname(store.queue_path()), "gtm.jsonl"))


def load(workspace=None, file_path=None):
    """Every decision, newest last. Filtered by workspace when asked.

    That filter is the tenancy boundary. One client's GTM reasoning is not
    another's to read.
    """
    rows = []
    for index, entry in enumerate(store.read_jsonl(file_path or path())):
        if entry.get("id") is None:
            # Position is the identity. The file is append-only and rows
            # are never reordered, so the index is stable, and it saves
            # storing an id that could disagree with the row it names.
            entry["id"] = f"d{index}"
        if workspace and entry.get("workspace") != workspace:
            continue
        rows.append(entry)
    return rows


def record(entry, file_path=None):
    """Append one decision. Never rewrites an existing row."""
    if not entry.get("workspace"):
        raise DecisionRefused("a decision must name its workspace")
    file_path = file_path or path()
    # Inside the write barrier: this builds its own append rather than
    # going through `store.write_jsonl`, and `path()` resolves beside the
    # queue, so a test that reaches it without isolating the store writes
    # the operator's real state. Measured on `spend-ledger.jsonl`.
    store.refuse_production_write(file_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({k: v for k, v in entry.items()
                                 if k != "id"}, sort_keys=True) + "\n")
    return entry


def supersede(workspace, old_id, new_entry, file_path=None):
    """Replace a decision with a newer one. Both survive.

    The old row is rewritten only to set `superseded_by`; its text is never
    touched. That is the one write this module makes that is not an append,
    and it is a link rather than a correction.
    """
    file_path = file_path or path()
    rows = load(file_path=file_path)
    found = None
    for row in rows:
        if row["id"] == old_id and row.get("workspace") == workspace:
            found = row
            break
    if found is None:
        # A decision from another workspace is indistinguishable from one
        # that never existed, the same way a record is.
        raise DecisionRefused("no such decision in this workspace")
    if found.get("superseded_by"):
        raise DecisionRefused(
            "that decision has already been superseded; supersede the one "
            "that replaced it")

    new_entry = dict(new_entry)
    new_entry["supersedes"] = old_id
    rows.append(new_entry)
    new_id = f"d{len(rows) - 1}"
    found["superseded_by"] = new_id

    with open(file_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({k: v for k, v in row.items()
                                     if k != "id"}, sort_keys=True) + "\n")
    new_entry["id"] = new_id
    return new_entry


# ------------------------------------------------------------------ reading

def current(workspace, file_path=None):
    """What is believed now: everything not superseded."""
    return [row for row in load(workspace, file_path)
            if not row.get("superseded_by")]


def history(workspace, file_path=None):
    """Everything, superseded rows included, newest first.

    The superseded ones are the point. A log that shows only the current
    belief is a configuration file with worse ergonomics.
    """
    return list(reversed(load(workspace, file_path)))


def by_area(workspace, file_path=None):
    """Current decisions grouped by the question they settle."""
    grouped = {area: [] for area in AREAS}
    for row in current(workspace, file_path):
        grouped.setdefault(row["area"], []).append(row)
    return [{"area": area, "label": AREA_LABEL[area],
             "decisions": grouped.get(area) or []}
            for area in AREAS]


def for_policy_key(workspace, key, file_path=None):
    """The current decision explaining one setting, if there is one."""
    for row in current(workspace, file_path):
        if row.get("policy_key") == key:
            return row
    return None


def unexplained(workspace, overrides, file_path=None):
    """Settings this workspace has changed and given no reason for.

    Not a fault - most settings are left alone and most changes are
    obvious at the time. It is a list to work through once, and it is the
    only thing here that reads the configuration at all.
    """
    explained = {row.get("policy_key") for row in current(workspace,
                                                          file_path)}
    return [key for key in sorted(overrides or {}) if key not in explained]


def summarise(workspace, overrides=None, file_path=None):
    """The whole picture, for one screen.

    `checkable` is the number worth reporting: how much of the current
    strategy rests on something a person could go and look at, rather than
    on a position somebody would have to argue again from scratch.
    """
    rows = current(workspace, file_path)
    checkable = [r for r in rows if r["basis"] in CHECKABLE]
    return {
        "workspace": workspace,
        "areas": by_area(workspace, file_path),
        "decisions": len(rows),
        "checkable": len(checkable),
        "judgement": len([r for r in rows if r["basis"] == JUDGEMENT]),
        "superseded": len([r for r in load(workspace, file_path)
                           if r.get("superseded_by")]),
        "unexplained": unexplained(workspace, overrides, file_path),
        "bases": [{"basis": basis, "label": BASIS_LABEL[basis],
                   "count": len([r for r in rows if r["basis"] == basis])}
                  for basis in BASES],
    }
