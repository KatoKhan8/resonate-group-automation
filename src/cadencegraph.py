#!/usr/bin/env python3
"""Cadences that branch, wait, and involve more than one human.

## What was wrong with a list

`src/cadence.py` models a sequence as an ordered list of steps with a day
number. That is exactly right for "email day 1, LinkedIn day 3, email day 5"
and exactly wrong for what the founder actually runs:

    connection request
    → accepted?   yes → message      no → wait 7 days, then email instead
    → replied?    yes → stop         no → follow up
    → still nothing after a month?   → re-engage from a different sender

A list cannot express "if". Encoding it as a list plus a `requires` field -
which is what the old model does for `connection_accepted` - handles one
condition and stops. So the model here is a small directed graph: nodes with
typed actions, and edges that may carry a condition.

## Deliberately not a workflow engine

There is no scripting, no user-defined predicate, no loop construct. The node
types in `NODES` and the conditions in `CONDITIONS` are a closed set covering
what Resonate does, and adding to that set is a visible edit to this file.

A general engine would be more powerful and much worse: it would let somebody
build a cadence whose behaviour nobody can predict from reading it, and the
whole point of every safety rule in this repository is that outreach behaviour
is predictable from reading it.

## Reference material

The brief mentions HeyReach exports of successful sequences as a structural
reference. **Those files are not in this repository**, so the node vocabulary
below is built from the brief's own list (§9) and from what
`src/providers/heyreach.py` demonstrably supports. Two node types the brief
names - post reaction and connection withdrawal - are present but marked
`validated: False`, because no recorded contract here proves the provider
does them. A cadence using an unvalidated node is refused at QA rather than
quietly planned. See `CADENCE-MODEL.md`.

## Graphs are versioned

`SCHEMA_VERSION` travels on every stored graph. A cadence written under an
older version is read under that version's rules rather than reinterpreted -
silently re-reading an old plan under new semantics is how a campaign
somebody approved becomes a campaign nobody approved.
"""
import collections

SCHEMA_VERSION = 2

EMAIL = "email"
LINKEDIN = "linkedin"

# ------------------------------------------------------------- node types
#
# (key, label, channel, does it contact the prospect, is the provider
#  capability validated by a recorded contract, one line of what it is)
#
# `contacts` is the column that matters for fatigue and for claims: a WAIT or
# a CHECK is a node in the graph but not a touch, and counting it as one would
# both throttle a campaign wrongly and let a message claim an approach that
# never happened.
NODES = (
    ("wait", "Wait", None, False, True,
     "hold for a number of days before the next node"),
    ("email", "Email", EMAIL, True, True,
     "send an email from an assigned inbox"),
    ("connection_request", "Connection request", LINKEDIN, True, True,
     "send a LinkedIn connection request, with or without a note"),
    ("linkedin_message", "LinkedIn message", LINKEDIN, True, True,
     "direct message; requires an accepted connection"),
    ("linkedin_followup", "LinkedIn follow-up", LINKEDIN, True, True,
     "a later message in the same LinkedIn thread"),
    ("connection_check", "Connection state check", LINKEDIN, False, True,
     "read whether the request was accepted"),
    ("reply_check", "Reply check", None, False, True,
     "read whether this contact has replied"),
    ("branch", "Branch", None, False, True,
     "split on a condition"),
    ("handoff", "Cross-channel handoff", None, False, True,
     "move the thread to the other channel, carrying a permitted reference"),
    ("dm_handoff", "Decision-maker handoff", None, False, True,
     "move to another contact at the same account"),
    ("reengage", "Re-engagement", None, False, True,
     "restart after a long wait, usually from a different sender"),
    ("stop", "Stop", None, False, True,
     "end this contact's sequence"),
    # Present because the brief names them; refused by QA until a recorded
    # contract proves the provider supports them. Naming them as unvalidated
    # is better than omitting them: an operator who wants one should be told
    # what is missing rather than left wondering why it is absent.
    ("post_reaction", "React to a post", LINKEDIN, False, False,
     "react to the prospect's recent post - PROVIDER CAPABILITY UNVALIDATED"),
    ("withdraw_request", "Withdraw connection request", LINKEDIN, False, False,
     "cancel a pending request - PROVIDER CAPABILITY UNVALIDATED"),
)

NODE_KEYS = tuple(n[0] for n in NODES)
NODE = {n[0]: {"key": n[0], "label": n[1], "channel": n[2], "contacts": n[3],
               "validated": n[4], "why": n[5]} for n in NODES}

CONTACTING = tuple(k for k in NODE_KEYS if NODE[k]["contacts"])
UNVALIDATED = tuple(k for k in NODE_KEYS if not NODE[k]["validated"])

# ------------------------------------------------------------- conditions
#
# Everything a branch may test. Each maps onto a fact the engine already
# records; there is no condition here that needs a new kind of evidence.
CONDITIONS = {
    "connection_accepted": "the connection request was accepted",
    "connection_pending": "the connection request has not been accepted",
    "replied": "this contact has replied",
    "no_reply": "this contact has not replied",
    "positive_reply": "this contact replied positively",
    "email_confirmed_sent": "an earlier email to this contact is confirmed sent",
    "referral_received": "somebody at this account referred us to this contact",
    "other_dm_replied": "another decision maker at this account replied",
    "always": "always",
}

TRUE_BRANCH = "yes"
FALSE_BRANCH = "no"

# Decision-maker roles a node may target. Constants rather than loose strings
# so a template and a cadence cannot disagree about what "secondary" is.
PRIMARY_ROLE = "primary"
SECONDARY_ROLE = "secondary"
TERTIARY_ROLE = "tertiary"
REFERRAL_ROLE = "referral"
ROLES = (PRIMARY_ROLE, SECONDARY_ROLE, TERTIARY_ROLE, REFERRAL_ROLE)


class CadenceError(ValueError):
    """The graph is not a graph this system will run."""


def node(key, node_type, day=None, sender_id=None, contact_role=None,
         template=None, condition=None, wait_days=None, label=None,
         phase=None, **extra):
    """One node. `contact_role` targets a decision maker by role, not by id.

    Roles rather than contact keys, because a cadence is a plan for an
    account and the specific people are resolved when it runs. A graph naming
    `contact_key=k3` is a graph that only works for one company.
    """
    if node_type not in NODE:
        raise CadenceError(f"unknown node type: {node_type!r}")
    if condition is not None and condition not in CONDITIONS:
        raise CadenceError(f"unknown condition: {condition!r}")
    return {
        "key": key,
        "type": node_type,
        "label": label or NODE[node_type]["label"],
        "channel": NODE[node_type]["channel"],
        "day": day,
        "wait_days": wait_days,
        "sender_id": sender_id,
        "contact_role": contact_role,
        "template": template,
        "condition": condition,
        "phase": phase,
        "next": {},
        **extra,
    }


def graph(name, nodes, start=None, version=SCHEMA_VERSION):
    return {"name": name, "version": version,
            "start": start or (nodes[0]["key"] if nodes else None),
            "nodes": {n["key"]: n for n in nodes}}


def connect(graph_, from_key, to_key, on=TRUE_BRANCH):
    node_ = graph_["nodes"].get(from_key)
    if node_ is None:
        raise CadenceError(f"no such node: {from_key!r}")
    if to_key is not None and to_key not in graph_["nodes"]:
        raise CadenceError(f"no such node: {to_key!r}")
    node_["next"][on] = to_key
    return graph_


# ---------------------------------------------------------------- reading

def walk(graph_, taken=None, limit=200):
    """Every node reachable from the start, in order, following `taken`.

    `taken` maps a node key to the branch a real run took. Without it, walk
    follows the `yes` edge, which is what a preview of the intended path
    shows. The limit is a backstop against a cycle somebody built by hand;
    `validate` refuses cycles outright, so reaching it means a graph got in
    without validation.
    """
    taken = taken or {}
    order, seen = [], set()
    current = graph_.get("start")
    while current and len(order) < limit:
        if current in seen:
            break
        seen.add(current)
        node_ = graph_["nodes"].get(current)
        if node_ is None:
            break
        order.append(node_)
        branch = taken.get(current, TRUE_BRANCH)
        current = node_["next"].get(branch) or node_["next"].get(TRUE_BRANCH)
    return order


def steps_of(graph_):
    """Only the nodes that actually contact somebody.

    What fatigue counts and what a claim may reference. A WAIT is a node; it
    is not a touch, and anything treating it as one is wrong in both
    directions at once.
    """
    return [n for n in graph_["nodes"].values()
            if NODE[n["type"]]["contacts"]]


def senders_of(graph_):
    return sorted({n["sender_id"] for n in graph_["nodes"].values()
                   if n.get("sender_id")})


def roles_of(graph_):
    return sorted({n["contact_role"] for n in graph_["nodes"].values()
                   if n.get("contact_role")})


def channels_of(graph_):
    return sorted({n["channel"] for n in graph_["nodes"].values()
                   if n.get("channel")})


def describe(graph_):
    """A summary for a card or a table row."""
    contacting = steps_of(graph_)
    return {
        "name": graph_.get("name"),
        "version": graph_.get("version"),
        "nodes": len(graph_["nodes"]),
        "touches": len(contacting),
        "senders": senders_of(graph_),
        "roles": roles_of(graph_),
        "channels": channels_of(graph_),
        "branches": len([n for n in graph_["nodes"].values()
                         if len(n["next"]) > 1]),
        "unvalidated": sorted({n["type"] for n in graph_["nodes"].values()
                               if n["type"] in UNVALIDATED}),
        "longest_wait": max([n.get("wait_days") or 0
                             for n in graph_["nodes"].values()] or [0]),
    }


# -------------------------------------------------------------- validation

def validate(graph_, team=None, config=None, names=None):
    """Every structural problem, as a list of findings.

    Structure only: whether the graph is runnable and internally consistent.
    Whether it is *wise* - too dense, unsupported claims - is fatigue and
    claim resolution, checked by their own modules against a real account.

    `names` maps sender id to display name. Optional, because a graph can be
    validated without a roster to hand - but a finding that says "john" while
    the step beside it says "John Adeyemi" makes a reviewer check whether
    they are the same person.
    """
    names = names or {}
    findings = []
    nodes = graph_.get("nodes") or {}

    def fail(level, why, where=None):
        findings.append({"level": level, "why": why, "node": where})

    if graph_.get("version") != SCHEMA_VERSION:
        fail("warn",
             f"written under schema version {graph_.get('version')}; this "
             f"build reads version {SCHEMA_VERSION}. It is read under its "
             f"own version's rules, not reinterpreted")

    if not nodes:
        fail("block", "the cadence has no nodes")
        return findings
    if graph_.get("start") not in nodes:
        fail("block", f"the start node {graph_.get('start')!r} does not exist")
        return findings

    for key, node_ in sorted(nodes.items()):
        kind = node_.get("type")
        if kind not in NODE:
            fail("block", f"unknown node type {kind!r}", key)
            continue
        if kind in UNVALIDATED:
            fail("block",
                 f"{NODE[kind]['label']} needs a provider capability nothing "
                 f"here has validated. See LIVE-VALIDATION-PLAN.md", key)
        for branch, target in (node_.get("next") or {}).items():
            if target is not None and target not in nodes:
                fail("block", f"branch {branch!r} points at {target!r}, "
                              f"which does not exist", key)
        if kind == "branch":
            if not node_.get("condition"):
                fail("block", "a branch with no condition cannot branch", key)
            elif node_["condition"] not in CONDITIONS:
                fail("block", f"unknown condition "
                              f"{node_['condition']!r}", key)
            if len(node_.get("next") or {}) < 2:
                fail("warn", "a branch with one edge is a step, not a "
                             "branch", key)
        if kind == "wait" and not node_.get("wait_days"):
            fail("block", "a wait with no duration waits forever", key)
        if NODE[kind]["contacts"] and not node_.get("sender_id"):
            fail("block", f"{NODE[kind]['label']} has no sender; a message "
                          f"nobody is sending cannot be sent", key)
        if (kind == "linkedin_message"
                and not _preceded_by(graph_, key, "connection_request")):
            fail("warn", "a LinkedIn message with no connection request "
                         "before it will fail unless already connected", key)

    reachable = {n["key"] for n in walk(graph_)}
    for branch_node in [n for n in nodes.values() if len(n["next"]) > 1]:
        reachable.update(_reachable_from(graph_, branch_node["key"]))
    for key in sorted(set(nodes) - reachable):
        fail("warn", "no path reaches this node", key)

    if _has_cycle(graph_):
        fail("block", "the cadence loops back on itself; it would never end")

    if team:
        allowed = set(team)
        for key, node_ in sorted(nodes.items()):
            sender = node_.get("sender_id")
            if sender and sender not in allowed:
                fail("block",
                     f"{names.get(sender, sender)} is not on this campaign's "
                     f"outreach team; a sender outside the team must not "
                     f"enter a prospect's cadence", key)
    return findings


def _preceded_by(graph_, key, node_type):
    for node_ in graph_["nodes"].values():
        if node_["type"] != node_type:
            continue
        if key in _reachable_from(graph_, node_["key"]):
            return True
    return False


def _reachable_from(graph_, key, seen=None):
    seen = seen if seen is not None else set()
    node_ = graph_["nodes"].get(key)
    if node_ is None:
        return seen
    for target in (node_.get("next") or {}).values():
        if target and target not in seen:
            seen.add(target)
            _reachable_from(graph_, target, seen)
    return seen


def _has_cycle(graph_):
    colour = collections.defaultdict(int)       # 0 unseen, 1 open, 2 closed

    def visit(key):
        if colour[key] == 1:
            return True
        if colour[key] == 2:
            return False
        colour[key] = 1
        node_ = graph_["nodes"].get(key) or {}
        for target in (node_.get("next") or {}).values():
            if target and visit(target):
                return True
        colour[key] = 2
        return False

    return any(visit(key) for key in graph_["nodes"])


def blocking(findings):
    return [f for f in findings if f["level"] == "block"]


# ---------------------------------------------------------------- templates
#
# Reusable shapes, not client copy. Each builds a graph from the senders it is
# given, so the same template works for any workspace - a template carrying
# one client's messaging would be a template nobody else can use.


def _t(name, build):
    return {"name": name, "build": build}


def standard_email_linkedin(email_sender, linkedin_sender, **_):
    """The classic: email opens, LinkedIn supports, email closes."""
    nodes = [
        node("d1", "email", day=1, sender_id=email_sender,
             contact_role="primary", template="opener"),
        node("d3", "connection_request", day=3, sender_id=linkedin_sender,
             contact_role="primary"),
        node("d4", "branch", condition="connection_accepted"),
        node("d5", "linkedin_message", day=5, sender_id=linkedin_sender,
             contact_role="primary", template="linkedin_intro"),
        node("d6", "wait", wait_days=3),
        node("d8", "email", day=8, sender_id=email_sender,
             contact_role="primary", template="persona_pain"),
        node("d12", "branch", condition="replied"),
        node("d13", "stop"),
        node("d14", "email", day=14, sender_id=email_sender,
             contact_role="primary", template="breakup"),
    ]
    g = graph("Email + LinkedIn standard", nodes, "d1")
    connect(g, "d1", "d3")
    connect(g, "d3", "d4")
    connect(g, "d4", "d5", TRUE_BRANCH)
    connect(g, "d4", "d6", FALSE_BRANCH)
    connect(g, "d5", "d8")
    connect(g, "d6", "d8")
    connect(g, "d8", "d12")
    connect(g, "d12", "d13", TRUE_BRANCH)
    connect(g, "d12", "d14", FALSE_BRANCH)
    return g


def linkedin_heavy(email_sender, linkedin_sender, second_linkedin=None, **_):
    """LinkedIn-led, with a second profile taking over if the first stalls."""
    second = second_linkedin or linkedin_sender
    nodes = [
        node("c1", "connection_request", day=1, sender_id=linkedin_sender,
             contact_role="primary"),
        node("w1", "wait", wait_days=3),
        node("k1", "connection_check", day=4, sender_id=linkedin_sender,
             contact_role="primary"),
        node("b1", "branch", condition="connection_accepted"),
        node("m1", "linkedin_message", day=5, sender_id=linkedin_sender,
             contact_role="primary", template="linkedin_intro"),
        node("e1", "email", day=6, sender_id=email_sender,
             contact_role="primary", template="opener"),
        node("w2", "wait", wait_days=4),
        node("b2", "branch", condition="replied"),
        node("s1", "stop"),
        node("m2", "linkedin_followup", day=10, sender_id=linkedin_sender,
             contact_role="primary", template="linkedin_followup"),
        node("w3", "wait", wait_days=21),
        node("r1", "reengage", label="Re-engage from a second profile"),
        node("m3", "linkedin_message", day=35, sender_id=second,
             contact_role="primary", template="linkedin_intro"),
    ]
    g = graph("LinkedIn heavy", nodes, "c1")
    connect(g, "c1", "w1")
    connect(g, "w1", "k1")
    connect(g, "k1", "b1")
    connect(g, "b1", "m1", TRUE_BRANCH)
    connect(g, "b1", "e1", FALSE_BRANCH)
    connect(g, "m1", "w2")
    connect(g, "e1", "w2")
    connect(g, "w2", "b2")
    connect(g, "b2", "s1", TRUE_BRANCH)
    connect(g, "b2", "m2", FALSE_BRANCH)
    connect(g, "m2", "w3")
    connect(g, "w3", "r1")
    connect(g, "r1", "m3")
    return g


def account_multi_dm(email_sender, linkedin_sender, second_email=None,
                     second_linkedin=None, **_):
    """Two decision makers, two email humans, two LinkedIn humans.

    The shape the brief is actually about: the primary is opened by one pair,
    and the secondary by a different pair, with the second person's sequence
    aware of the first's.
    """
    email_two = second_email or email_sender
    linkedin_two = second_linkedin or linkedin_sender
    nodes = [
        node("p1", "email", day=1, sender_id=email_sender,
             contact_role="primary", template="opener"),
        node("p2", "connection_request", day=3, sender_id=linkedin_sender,
             contact_role="primary"),
        node("p3", "branch", condition="replied"),
        node("p4", "stop"),
        node("w1", "wait", wait_days=4),
        node("s1", "email", day=8, sender_id=email_two,
             contact_role="secondary", template="opener"),
        node("s2", "branch", condition="other_dm_replied"),
        node("s3", "dm_handoff", label="Prioritise whoever answered"),
        node("s4", "connection_request", day=11, sender_id=linkedin_two,
             contact_role="secondary"),
        node("b3", "branch", condition="referral_received"),
        node("r1", "dm_handoff", label="Activate the referred contact"),
        node("r2", "email", day=15, sender_id=email_sender,
             contact_role="referral", template="opener"),
        node("z1", "stop"),
    ]
    g = graph("Account-based multi-DM", nodes, "p1")
    connect(g, "p1", "p2")
    connect(g, "p2", "p3")
    connect(g, "p3", "p4", TRUE_BRANCH)
    connect(g, "p3", "w1", FALSE_BRANCH)
    connect(g, "w1", "s1")
    connect(g, "s1", "s2")
    connect(g, "s2", "s3", TRUE_BRANCH)
    connect(g, "s2", "s4", FALSE_BRANCH)
    connect(g, "s3", "b3")
    connect(g, "s4", "b3")
    connect(g, "b3", "r1", TRUE_BRANCH)
    connect(g, "b3", "z1", FALSE_BRANCH)
    connect(g, "r1", "r2")
    connect(g, "r2", "z1")
    return g


def reengagement(email_sender, linkedin_sender, **_):
    """A long, quiet sequence for accounts that went cold."""
    nodes = [
        node("w0", "wait", wait_days=30),
        node("e1", "email", day=30, sender_id=email_sender,
             contact_role="primary", template="opener"),
        node("b1", "branch", condition="replied"),
        node("s1", "stop"),
        node("w1", "wait", wait_days=30),
        node("l1", "linkedin_message", day=60, sender_id=linkedin_sender,
             contact_role="primary", template="linkedin_followup"),
        node("z1", "stop"),
    ]
    g = graph("Re-engagement", nodes, "w0")
    connect(g, "w0", "e1")
    connect(g, "e1", "b1")
    connect(g, "b1", "s1", TRUE_BRANCH)
    connect(g, "b1", "w1", FALSE_BRANCH)
    connect(g, "w1", "l1")
    connect(g, "l1", "z1")
    return g


def account_multichannel(email_sender, linkedin_sender, second_email=None,
                         second_linkedin=None, **_):
    """The full shape: four humans, three decision makers, six phases.

    Lives in `src/web/democadence.py` because it is long enough to be worth
    reading on its own, and it is the one template that exercises every
    primitive this model has.
    """
    from .web import democadence

    return democadence.build(email_sender, second_email, linkedin_sender,
                             second_linkedin)


TEMPLATES = collections.OrderedDict((
    ("standard", _t("Email + LinkedIn standard", standard_email_linkedin)),
    ("account_multichannel", _t("Account-based multichannel (full)",
                                account_multichannel)),
    ("linkedin_heavy", _t("LinkedIn heavy", linkedin_heavy)),
    ("account_multi_dm", _t("Account-based multi-DM", account_multi_dm)),
    ("reengagement", _t("Re-engagement", reengagement)),
))


def from_template(key, **senders):
    template = TEMPLATES.get(key)
    if template is None:
        raise CadenceError(f"unknown cadence template: {key!r}")
    return template["build"](**senders)


def from_legacy(steps, email_sender=None, linkedin_sender=None):
    """Read an old linear cadence as a graph, without reinterpreting it.

    `src/cadence.py`'s `STEPS` are a list with an optional `requires`. Every
    one of them maps onto a node here, and `requires: connection_accepted`
    becomes an explicit branch - which is what it always meant.

    Version 1 is stamped on the result so nothing pretends an old plan was
    authored under the richer model.
    """
    nodes, previous = [], None
    for spec in steps:
        key = spec.get("key")
        kind = ("email" if spec.get("channel") == EMAIL
                else "linkedin_message" if spec.get("requires")
                else "connection_request" if previous is None
                else "linkedin_followup")
        sender = email_sender if spec.get("channel") == EMAIL \
            else linkedin_sender
        if spec.get("requires") == "connection_accepted":
            gate = node(f"{key}_gate", "branch",
                        condition="connection_accepted")
            nodes.append(gate)
        nodes.append(node(key, kind, day=spec.get("day"), sender_id=sender,
                          contact_role="primary",
                          template=spec.get("template")))
        previous = key

    g = graph("Imported cadence", nodes,
              nodes[0]["key"] if nodes else None, version=1)
    ordered = [n["key"] for n in nodes]
    for earlier, later in zip(ordered, ordered[1:]):
        connect(g, earlier, later)
    return g


# ------------------------------------------------------------------- phases
#
# A forty-node cadence rendered as one vertical column is a wall. Phases give
# it structure without adding a concept: a phase is a label on a node, nodes
# inherit the phase of whatever preceded them, and nothing about execution
# changes.
#
# The names below are the ones Resonate sequences actually fall into. They are
# defaults, not a fixed vocabulary - `node(..., phase="Whatever")` works, and
# `phases_of` returns whatever the graph uses.

OPENING = "Initial outreach"
CONNECTING = "LinkedIn connection"
FOLLOW_UP = "Multichannel follow-up"
SECOND_SENDER = "Second sender"
SECONDARY_DM = "Secondary decision maker"
REENGAGEMENT = "Re-engagement"
CLOSING = "Close"

PHASE_ORDER = (OPENING, CONNECTING, FOLLOW_UP, SECOND_SENDER, SECONDARY_DM,
               REENGAGEMENT, CLOSING)


def phases_of(graph_):
    """Every phase in this graph, with its nodes, in walk order.

    Nodes inherit the previous node's phase, so a cadence only has to label
    where a phase *starts*. A graph with no phases at all comes back as one
    unnamed group, which is what a short cadence should look like.
    """
    ordered = walk(graph_)
    seen = {n["key"] for n in ordered}
    ordered += [graph_["nodes"][k] for k in sorted(graph_["nodes"])
                if k not in seen]

    # A phase is a *set* of nodes, not a contiguous run of them. The walk
    # follows the default path and legitimately jumps between phases - the
    # secondary-DM arm is reached from two places - so grouping by
    # consecutive runs turned a six-phase cadence into twenty-three
    # one-node groups.
    #
    # Order is `PHASE_ORDER` where the phase is a known one, then first
    # appearance for anything a workspace named itself.
    seen_order, buckets = [], {}
    current = None
    for node_ in ordered:
        phase = node_.get("phase") or current or ""
        current = phase
        if phase not in buckets:
            buckets[phase] = []
            seen_order.append(phase)
        buckets[phase].append(node_)

    def rank(phase):
        if phase in PHASE_ORDER:
            return (0, PHASE_ORDER.index(phase))
        return (1, seen_order.index(phase))

    return [{"phase": phase, "nodes": buckets[phase]}
            for phase in sorted(buckets, key=rank)]
