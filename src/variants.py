#!/usr/bin/env python3
"""Five ways to say the same true thing, and how we find out which works.

## What this is not

It is not five drafts for an operator to pick from. Picking by taste is
what the product did before, and taste is not evidence. This assigns
contacts to variants, measures what came back, and shifts *future* traffic
toward what worked - while refusing to call a winner from four replies
against three.

## The unit is a step, and the unit of assignment is a contact

Every message-bearing node runs its own experiment: the winner on day 1
says nothing about day 6, because they are different messages to a person
in a different state. `MESSAGE_NODES` names which node types carry copy;
a wait, a branch and a reply check do not.

One contact gets **one variant per step**. Not one per account - see
`ACCOUNT` below for why that is configurable and why contact-level is the
default.

## Assignment is deterministic, and history is immutable

`assign()` is a pure function of (campaign, step, contact, allocation
version). The same planned touch resolves to the same variant on every
read, so a page refresh or a worker restart cannot move somebody from A to
D. When a touch is actually prepared, the assignment is *recorded* - and
from then on the record is authoritative, so changing the allocation later
cannot rewrite what somebody was already sent.

That is the whole of requirements 5, 6 and 22: optimisation applies to
future assignments and never to history.

## Style is a first-class dimension

A variant is not "B". It is "short and direct", and that word is what
makes the result reusable: across campaigns, across steps, eventually
across a workspace's whole history. Storing only a letter throws away the
only part of the finding that generalises.

## Safety is not a variant-level decision

Every variant passes the same claim and lint gates independently. A
campaign does not become approvable because variant A is clean while
variant D says "my colleague Anna emailed you" with nothing behind it -
`campaignqa` checks all of them, and the worst answer is the answer.

Style may change tone, length, structure, opening and call to action. It
may not change what is true. `src/outreachclaims.py` remains the authority
on what a message may assert, and a variant that wants to say more needs
evidence, not a different style.
"""
import hashlib

from . import cadencegraph

# Node types that carry copy. Everything else in the graph is control flow.
MESSAGE_NODES = ("email", "connection_request", "linkedin_message",
                 "linkedin_followup")

MINIMUM_VARIANTS = 5

# ------------------------------------------------------------- the styles
#
# A hypothesis, not a label. Each says what is being varied so a result can
# be read as evidence about an approach rather than about a letter.

EMAIL_STYLES = {
    "short_direct": "Short and direct. Two sentences and one question.",
    "casual": "Casual. Written the way a peer would write it.",
    "professional": "Professional. Complete sentences, measured tone.",
    "consultative": "Consultative. Names the pattern before the ask.",
    "problem_led": "Problem-led. Opens on the cost of the status quo.",
}

LINKEDIN_STYLES = {
    "casual": "Casual. Lower case, short, conversational.",
    "short_direct": "Short and direct. One line and a question.",
    "professional": "Professional. Full sentences, no abbreviation.",
    "consultative": "Consultative. A short observation, then the ask.",
    "peer_to_peer": "Peer to peer. One operator writing to another.",
}

def style_name(node_type, style):
    """"Short and direct", not `short_direct`.

    The description in `STYLES_FOR` opens with the name, so the name is its
    first sentence. Keeping one table rather than two means a style cannot
    be renamed in one place and not the other.
    """
    described = STYLES_FOR.get(node_type, {}).get(style)
    if not described:
        return str(style or "").replace("_", " ").capitalize()
    return described.split(".")[0].strip()


STYLES_FOR = {
    "email": EMAIL_STYLES,
    "connection_request": LINKEDIN_STYLES,
    "linkedin_message": LINKEDIN_STYLES,
    "linkedin_followup": LINKEDIN_STYLES,
}

# ------------------------------------------------------------- the states

EXPLORING = "exploring"
INSUFFICIENT_DATA = "insufficient_data"
LEADING = "leading"
WINNER = "winner"
NO_CLEAR_WINNER = "no_clear_winner"
PAUSED = "paused"
COMPLETED = "completed"
STATES = (EXPLORING, INSUFFICIENT_DATA, LEADING, WINNER, NO_CLEAR_WINNER,
          PAUSED, COMPLETED)

STATE_LABEL = {
    EXPLORING: "Exploring",
    INSUFFICIENT_DATA: "Not enough data yet",
    LEADING: "One variant is ahead",
    WINNER: "Winner",
    NO_CLEAR_WINNER: "No clear winner",
    PAUSED: "Paused",
    COMPLETED: "Completed",
}

ACTIVE = "active"
VARIANT_PAUSED = "paused"
RETIRED = "retired"
VARIANT_STATUSES = (ACTIVE, VARIANT_PAUSED, RETIRED)

# ------------------------------------------- what a CLIENT may be shown
#
# OPERATOR, 2026-09-22: "Variants carry a status: testing / winner /
# retired. Clients see winner as part of the cadence, never testing or
# retired; internal sees all."
#
# A SECOND AXIS, NOT A RENAMING OF THE FIRST. `status` above decides
# ALLOCATION - who gets which arm, and `even_allocation`, `experiment_of`,
# `shifted_allocation` and `validate` all read it. Rewriting its vocabulary
# would change which message real people receive, which is not what a
# visibility decision should be able to do.
#
# So this is its own field. Allocation is unaffected by it and it is
# unaffected by allocation: a variant can be `active` for sending and
# `testing` for showing, which is exactly the normal state of affairs.
#
# MIGRATION. Every variant written before today carries no `client_status`
# and therefore reads as TESTING, which is withheld from clients - the same
# behaviour as before this field existed. Nothing needs backfilling and no
# client answer changes until somebody promotes a variant on purpose.
# Promoting one is a deliberate act and is meant to be.
TESTING = "testing"
VARIANT_WINNER = "winner"
CLIENT_STATUSES = (TESTING, VARIANT_WINNER, RETIRED)


def client_status(entry):
    """`testing` | `winner` | `retired` for one variant. Never None.

    Derived rather than required, so existing data is readable:

        an explicit `client_status`   that, when it is a known one
        `status` is `retired`         retired - a retired arm is retired
                                      on both axes and saying otherwise
                                      would be two truths about one thing
        anything else                 testing

    TESTING IS THE DEFAULT AND THE DEFAULT IS THE WITHHELD ONE. An unknown
    or missing value must not be the one that reaches a client, because the
    failure then is copy under test quoted to the customer as settled.
    """
    stated = str((entry or {}).get("client_status") or "").strip().lower()
    if stated in CLIENT_STATUSES:
        return stated
    if str((entry or {}).get("status") or "").strip().lower() == RETIRED:
        return RETIRED
    return TESTING


def client_may_see(entry):
    """Only a winner. Written as its own function so the rule has one home."""
    return client_status(entry) == VARIANT_WINNER

# ------------------------------------------------------- what we optimise
#
# Business outcomes, in the order a person would defend them. Opens and
# clicks are deliberately absent: they are not authoritative here, and a
# system that optimised for them would be optimising for a proxy nobody
# asked for.
POSITIVE_REPLIES = "positive_replies"
REPLIES = "replies"
MEETINGS = "meetings"
OBJECTIVES = (POSITIVE_REPLIES, REPLIES, MEETINGS)

OBJECTIVE_LABEL = {
    POSITIVE_REPLIES: "Positive replies",
    REPLIES: "Replies",
    MEETINGS: "Meetings",
}

DEFAULT_OBJECTIVE = POSITIVE_REPLIES

# ---------------------------------------------------------- the thresholds
#
# Conservative on purpose, and all configurable. The failure this guards
# against is declaring a winner from four replies against three, which is
# not a finding - it is noise with a rosette on it.
DEFAULTS = {
    # Evaluation begins here. A checkpoint, not a verdict.
    "first_checkpoint": 0.10,
    # No winner is possible below this many exposures per active variant,
    # whatever the rates look like.
    "minimum_per_variant": 30,
    # ...nor below this many outcomes across the whole experiment, because
    # 30 exposures with one reply between them settles nothing.
    "minimum_outcomes": 8,
    # How much better the leader must be, proportionally, before the word
    # "winner" is used at all.
    "minimum_lift": 0.30,
    # What a winner keeps once it has won. The remainder stays with the
    # challengers, because a variant that stops being served stops being
    # measured and drift stops being visible.
    "winner_share": 0.75,
    # Later checkpoints. Leading at 10% is not leading at 50%.
    "checkpoints": (0.10, 0.25, 0.50, 0.75),
}


def settings(config=None):
    """Thresholds in force, workspace overrides on top of the defaults."""
    out = dict(DEFAULTS)
    override = ((config or {}).get("experiments") or {})
    for key, value in override.items():
        if key in out and value is not None:
            out[key] = value
    return out


# ------------------------------------------------------------ the variant

def variant(variant_id, style, *, subject=None, body=None, note=None,
            status=ACTIVE, version=1, allocation=None,
            client_status=TESTING):
    """One complete message. Not a subject *or* a body - both together.

    Complete variants rather than a factorial of parts: five subjects by
    five bodies is six hundred and twenty-five cells, none of which anybody
    would have enough traffic to settle. Whatever varies, the variant is
    what was sent and what the outcome is attributed to.
    """
    return {
        "variant_id": str(variant_id),
        "style": style,
        "subject": subject,
        "body": body,
        "note": note,
        "status": status,
        # The visibility axis. Defaults to the withheld value, so a variant
        # written without thinking about clients is not shown to one.
        "client_status": client_status,
        "version": int(version),
        "allocation": allocation,
    }


def content_of(entry):
    """The copy a variant carries, in the shape a step uses."""
    return {k: v for k, v in (("subject", entry.get("subject")),
                              ("body", entry.get("body")),
                              ("note", entry.get("note"))) if v}


def is_message_node(node):
    return (node or {}).get("type") in MESSAGE_NODES


def experiment_of(node):
    """The active variants on this step, or None if it has no experiment."""
    entries = [v for v in (node or {}).get("variants") or []
               if v.get("status") == ACTIVE]
    return entries or None


def fingerprint(entry):
    """What was approved, for one variant. Any edit moves it.

    Deliberately the same material `approval.fingerprint` hashes, so an
    edited variant invalidates its approval by the same rule that an edited
    step always has.
    """
    material = " ".join(str(entry.get(k) or "")
                        for k in ("style", "subject", "body", "note"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------- the allocation

def even_allocation(entries):
    """Equal shares, with the remainder spread rather than dumped on one."""
    active = [v for v in entries if v.get("status") == ACTIVE]
    if not active:
        return {}
    share = 1.0 / len(active)
    return {v["variant_id"]: share for v in active}


def allocation_of(node, config=None):
    """The shares in force for this step, normalised to sum to one.

    A stored allocation wins; otherwise every active variant gets an equal
    share. Normalising here rather than trusting the stored numbers means a
    hand-edited allocation that sums to 0.9 still assigns everybody.
    """
    entries = experiment_of(node) or []
    stored = {v["variant_id"]: v["allocation"] for v in entries
              if v.get("allocation") is not None}
    if not stored or len(stored) != len(entries):
        return even_allocation(entries)
    total = sum(float(v) for v in stored.values())
    if total <= 0:
        return even_allocation(entries)
    return {k: float(v) / total for k, v in stored.items()}


def allocation_version(node):
    """Which allocation an assignment was made under.

    Bumped whenever the shares move, so a recorded assignment can say which
    regime produced it and a later shift cannot make history look wrong.
    """
    return int((node or {}).get("allocation_version") or 1)


# ---------------------------------------------------------- the assignment

def _bucket(campaign_id, step_key, contact_key, version):
    """A stable number in [0, 1) for this contact on this step.

    Hashed rather than random: the same planned touch resolves the same way
    on every read, in every process, forever. A random draw would move
    somebody from A to D on a page refresh, and the assignment would then
    be a property of when it was looked at.

    The campaign and step are in the material so one contact is not put in
    the same relative position in every experiment they are part of, which
    would quietly correlate the results of every step.
    """
    material = f"{campaign_id}|{step_key}|{contact_key}|{version}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def assign(node, campaign_id, contact_key, config=None):
    """Which variant this contact gets on this step. Pure and repeatable."""
    entries = experiment_of(node)
    if not entries:
        return None
    shares = allocation_of(node, config)
    version = allocation_version(node)
    point = _bucket(campaign_id, node.get("key"), contact_key, version)
    running = 0.0
    for entry in entries:
        running += shares.get(entry["variant_id"], 0.0)
        if point < running:
            return entry["variant_id"]
    return entries[-1]["variant_id"]


def resolve(node, campaign_id, contact_key, recorded=None, config=None):
    """The variant in force, preferring what was actually recorded.

    `recorded` is the assignment written when the touch was prepared. It
    wins over the deterministic function, because once somebody has been
    put in a cell the experiment has to remember it - otherwise shifting
    traffic tomorrow would rewrite who was in which cell yesterday, and
    every rate computed from it would be wrong.
    """
    entries = {v["variant_id"]: v for v in (node.get("variants") or [])}
    if recorded and recorded in entries:
        return entries[recorded]
    chosen = assign(node, campaign_id, contact_key, config)
    return entries.get(chosen)


def apply_to_step(step, entry):
    """Put a variant's copy into a step, leaving everything else alone."""
    if not entry:
        return step
    out = dict(step or {})
    out.update(content_of(entry))
    out["variant_id"] = entry["variant_id"]
    out["variant_style"] = entry.get("style")
    out["variant_version"] = entry.get("version")
    # CARRIED ONTO THE STEP so the one reader of a step - the Slack agent's
    # `campaign_copy` among them - does not have to find the cadence node
    # and re-derive it. Two readers of one fact drift, and CLAUDE.md says
    # so in as many words.
    out["variant_client_status"] = client_status(entry)
    return out


# ------------------------------------------------------------ the evidence

def wilson_low(successes, trials, z=1.96):
    """Lower bound of a Wilson interval. Conservative on small samples.

    Chosen over a plain proportion because the plain one says a variant
    with one reply from one send has a 100% rate. Wilson pulls that toward
    nothing, which is what the evidence actually supports, and it is a
    closed form somebody can check rather than a simulation nobody can.
    """
    if trials <= 0:
        return 0.0
    p = successes / float(trials)
    denominator = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * ((p * (1 - p) / trials + z * z / (4 * trials * trials))
                  ** 0.5)
    return max(0.0, (centre - margin) / denominator)


def wilson_high(successes, trials, z=1.96):
    if trials <= 0:
        return 1.0
    p = successes / float(trials)
    denominator = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * ((p * (1 - p) / trials + z * z / (4 * trials * trials))
                  ** 0.5)
    return min(1.0, (centre + margin) / denominator)


def evaluate(node, results, config=None, progress=None, objective=None):
    """What this experiment can honestly be said to show.

    `results` is {variant_id: {"exposures": n, "<objective>": n}}.
    `progress` is how much of the eligible population has run, 0..1.

    The order of the checks is the argument:

      1. paused or no experiment      - nothing to say
      2. before the first checkpoint  - EXPLORING, by policy not by data
      3. too little per variant       - INSUFFICIENT_DATA, whatever the rates
      4. a leader whose lower bound clears the field's upper bound, by
         enough to matter                                        - WINNER
      5. a leader that has not cleared it                        - LEADING
      6. nothing separating them                       - NO_CLEAR_WINNER

    Step 4 is the whole safety property. Two variants at 4 and 3 replies
    have overlapping intervals and produce NO_CLEAR_WINNER, which is the
    truthful answer and the one a rosette would hide.
    """
    entries = experiment_of(node)
    if not entries:
        return {"state": PAUSED, "why": "no active variants", "rows": [],
                "leader": None, "objective": objective or DEFAULT_OBJECTIVE}

    rules = settings(config)
    objective = objective or (node.get("objective") or DEFAULT_OBJECTIVE)
    rows = []
    for entry in entries:
        found = (results or {}).get(entry["variant_id"]) or {}
        exposures = int(found.get("exposures") or 0)
        outcomes = int(found.get(objective) or 0)
        rows.append({
            "variant_id": entry["variant_id"],
            "style": entry.get("style"),
            # The name, for the sentence this function writes. A verdict
            # reading "short_direct leads" is a verdict written for a
            # database rather than for the person acting on it.
            "style_name": style_name(node.get("type"), entry.get("style")),
            "exposures": exposures,
            "outcomes": outcomes,
            # Always a pair. A percentage on its own is a sentence somebody
            # has to trust rather than one they can check.
            "rate": (outcomes / float(exposures)) if exposures else None,
            "low": wilson_low(outcomes, exposures),
            "high": wilson_high(outcomes, exposures),
        })
    rows.sort(key=lambda r: (-(r["rate"] or 0), r["variant_id"]))

    total_outcomes = sum(r["outcomes"] for r in rows)
    smallest = min(r["exposures"] for r in rows)
    result = {"rows": rows, "objective": objective,
              "objective_label": OBJECTIVE_LABEL.get(objective, objective),
              "leader": rows[0]["variant_id"] if rows else None,
              "checkpoint": rules["first_checkpoint"],
              "minimum_per_variant": rules["minimum_per_variant"]}

    if progress is not None and progress < rules["first_checkpoint"]:
        return {**result, "state": EXPLORING, "leader": None,
                "why": (f"{progress:.0%} of this experiment has run; the "
                        f"first checkpoint is "
                        f"{rules['first_checkpoint']:.0%}")}

    if smallest < rules["minimum_per_variant"] or \
            total_outcomes < rules["minimum_outcomes"]:
        return {**result, "state": INSUFFICIENT_DATA, "leader": None,
                "why": (f"{smallest} exposure(s) on the smallest variant and "
                        f"{total_outcomes} outcome(s) in total; this needs "
                        f"{rules['minimum_per_variant']} and "
                        f"{rules['minimum_outcomes']}")}

    leader, rest = rows[0], rows[1:]
    best_other = max((r["high"] for r in rest), default=0.0)
    runner_rate = max((r["rate"] or 0.0) for r in rest) if rest else 0.0
    lift = ((leader["rate"] - runner_rate) / runner_rate
            if runner_rate else None)

    if leader["low"] > best_other and (
            lift is None or lift >= rules["minimum_lift"]):
        return {**result, "state": WINNER,
                "why": (f"{leader['style_name']} leads on "
                        f"{leader['outcomes']}/{leader['exposures']} and its "
                        f"range does not overlap the others")}
    if leader["outcomes"] and leader["rate"] > runner_rate:
        return {**result, "state": LEADING,
                "why": (f"{leader['style_name']} is ahead on "
                        f"{leader['outcomes']}/{leader['exposures']}, but the "
                        f"ranges still overlap")}
    return {**result, "state": NO_CLEAR_WINNER, "leader": None,
            "why": "nothing separates these variants yet"}


def shifted_allocation(node, verdict, config=None):
    """Where future traffic should go. Never rewrites an assignment.

    A winner does not take everything by default. A variant that stops
    being served stops being measured, and an experiment that stops
    measuring cannot notice that its winner has stopped working.
    """
    entries = experiment_of(node) or []
    if verdict.get("state") != WINNER or not verdict.get("leader"):
        return allocation_of(node, config)
    rules = settings(config)
    if node.get("winner_takes_all"):
        return {v["variant_id"]: (1.0 if v["variant_id"] == verdict["leader"]
                                  else 0.0) for v in entries}
    winner_share = float(rules["winner_share"])
    others = [v for v in entries if v["variant_id"] != verdict["leader"]]
    rest = (1.0 - winner_share) / len(others) if others else 0.0
    out = {verdict["leader"]: winner_share}
    for entry in others:
        out[entry["variant_id"]] = rest
    return out


# ------------------------------------------------------------- validation

def validate(node):
    """Whether this step's experiment is one we would run.

    Structure only. Whether the *copy* is safe is `campaignqa`'s question,
    asked of every variant separately.
    """
    findings = []
    entries = node.get("variants") or []
    if not entries:
        return findings
    if not is_message_node(node):
        findings.append({
            "level": "block",
            "why": (f"{cadencegraph.NODE[node['type']]['label']} carries no "
                    f"copy, so it cannot have variants.")})
        return findings

    active = [v for v in entries if v.get("status") == ACTIVE]
    if 0 < len(active) < MINIMUM_VARIANTS:
        findings.append({
            "level": "warn",
            "why": (f"{len(active)} active variant(s) on this step; the "
                    f"supported experiment is {MINIMUM_VARIANTS}.")})

    seen = set()
    for entry in entries:
        if entry["variant_id"] in seen:
            findings.append({"level": "block",
                             "why": f"two variants share the id "
                                    f"{entry['variant_id']!r}."})
        seen.add(entry["variant_id"])
        if entry.get("status") not in VARIANT_STATUSES:
            findings.append({"level": "block",
                             "why": f"{entry['variant_id']}: unknown status "
                                    f"{entry.get('status')!r}."})
        stated = entry.get("client_status")
        if stated is not None and stated not in CLIENT_STATUSES:
            # BLOCK, NOT WARN. An unrecognised value reads as `testing` and
            # is therefore withheld, which is safe - but a typo'd `winner`
            # that silently means `testing` is a decision somebody made and
            # the system quietly did not carry out.
            findings.append({"level": "block",
                             "why": (f"{entry['variant_id']}: unknown "
                                     f"client_status {stated!r}. One of "
                                     f"{CLIENT_STATUSES}.")})
        styles = STYLES_FOR.get(node["type"], {})
        if entry.get("style") not in styles:
            findings.append({
                "level": "warn",
                "why": (f"{entry['variant_id']}: {entry.get('style')!r} is "
                        f"not one of this channel's styles, so its result "
                        f"will not group with anything.")})
        if not content_of(entry):
            findings.append({"level": "block",
                             "why": f"{entry['variant_id']} has no copy."})

    shares = allocation_of(node)
    if shares and abs(sum(shares.values()) - 1.0) > 0.001:
        findings.append({"level": "block",
                         "why": "the traffic allocation does not sum to 1."})
    return findings


# ----------------------------------------------------------- attribution
#
# Three different questions, kept apart because collapsing them is how a
# variant gets credit it did not earn:
#
#   EXPOSED_TO      this contact was sent this variant on this step
#   LAST_TOUCH      this variant was the last confirmed touch before a reply
#   JOURNEY         every variant this contact saw, in order
#
# The rate that drives optimisation is last-touch, because it is the only
# one with a denominator that means anything. The journey travels beside it
# so nobody reads "variant E won" as "variant E did it alone".

LAST_TOUCH = "last_touch"
EXPOSED = "exposed"


def journey_of(rec, contact_key):
    """Every variant this contact was actually sent, in order.

    Confirmed touches only. A planned touch is not an exposure, and
    counting one would put a denominator under a message nobody received.
    """
    from . import account

    out = []
    for touch in account.touches(rec, contact_key, confirmed_only=True):
        if touch.get("variant_id"):
            out.append({"step": touch.get("step"),
                        "channel": touch.get("channel"),
                        "at": touch.get("at"),
                        "variant_id": touch["variant_id"],
                        "style": touch.get("variant_style"),
                        "version": touch.get("variant_version")})
    return out


def _first_reply_at(rec, contact_key, objective):
    """When this contact produced the outcome we are optimising for."""
    from . import account, events as event_model

    if objective == MEETINGS:
        for entry in rec.get("events") or []:
            if (entry.get("type") == event_model.MEETING_MARKED
                    and entry.get("contact") == contact_key):
                return entry.get("at")
        return None
    replies = account.replies(rec, contact_key)
    if objective == POSITIVE_REPLIES:
        replies = [r for r in replies if r.get("positive")]
    return replies[0]["at"] if replies else None


def results_from(recs, step_key, objective=DEFAULT_OBJECTIVE):
    """Exposures and outcomes per variant for one step.

    An exposure is a confirmed touch carrying a variant id. An outcome is
    credited to the variant on the **last confirmed touch before** the
    reply - which is a reporting convention, not a claim about cause, and
    the UI says so.
    """
    from . import account

    tally = {}
    for rec in recs or []:
        for contact in account.contacts_of(rec):
            key = contact.get("key")
            mine = [t for t in journey_of(rec, key) if t["step"] == step_key]
            if not mine:
                continue
            for touch in mine:
                row = tally.setdefault(touch["variant_id"],
                                       {"exposures": 0, REPLIES: 0,
                                        POSITIVE_REPLIES: 0, MEETINGS: 0})
                row["exposures"] += 1
            outcome_at = _first_reply_at(rec, key, objective)
            if not outcome_at:
                continue
            # The last confirmed touch on *any* step before the outcome
            # decides who is credited; if that is not this step, this step
            # gets the exposure and no outcome.
            before = [t for t in journey_of(rec, key)
                      if str(t["at"] or "") <= str(outcome_at)]
            if before and before[-1]["step"] == step_key:
                tally[before[-1]["variant_id"]][objective] += 1
    return tally
