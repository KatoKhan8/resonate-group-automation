#!/usr/bin/env python3
"""Comparing sequence structures: four steps against seven, email against both.

## The second experiment dimension

`src/variants.py` tests what a message *says*: five wordings of one step,
one contact, one variant, measured by outcome. This tests what a sequence
*is* - how many steps, on which channels, how far apart, in what order.

They are deliberately separate, and reporting must keep them apart. A
six-step arm winning tells you nothing about which copy won inside it, and
pooling the two produces a number that answers neither question.

## The unit of randomisation is the account, by default

`variants` randomises per contact, which is right for copy: two people at
one company can receive different wordings without either outcome telling
you much about the other.

A sequence is different. If John at Acme is on a four-step arm and Sarah
at Acme is on a seven-step arm, their outcomes are not independent - the
account has a shared experience of us, `accountpolicy` couples them, a
reply from one pauses the other, and fatigue counts them together. Two
observations that influence each other are not two observations.

So the default unit is `ACCOUNT`. `CONTACT` is available and is the wrong
choice for anything account-based; it is here because a single-contact
audience is a real shape and forcing account semantics onto it would be
ceremony.

## An arm cannot force a channel a contact does not have

An arm with LinkedIn steps assigned to somebody with no profile would
either send nothing at those steps or send something else. Both invalidate
the comparison, and the second is worse: the arm would silently become a
different arm.

`STRICT` arms require every channel they use, and a contact missing one is
simply not eligible for that arm. `ADAPTIVE` arms name what they do
instead, explicitly, per channel. There is no third behaviour where steps
quietly disappear.

## Assignment is sticky and recorded

Computed once, stored on whatever the unit is, and re-read forever after.
A contact must not move from a four-step arm to a seven-step arm because
somebody edited the allocation halfway through - the first four steps
already happened, and the result would belong to neither arm.

The hash is the same construction `variants` uses, for the same reason: an
assignment that changed on a page refresh would be a property of when it
was looked at.
"""
import argparse
import hashlib
import json

# Where an experiment lives on a campaign, and where an assignment lives on
# whatever was randomised.
EXPERIMENT_KEY = "cadence_experiment"
ASSIGNMENT_KEY = "cadence_arm"

ACCOUNT = "account"
CONTACT = "contact"
UNITS = (ACCOUNT, CONTACT)

STRICT = "strict"
ADAPTIVE = "adaptive"
MODES = (STRICT, ADAPTIVE)

EMAIL = "email"
LINKEDIN = "linkedin"


class BadExperiment(ValueError):
    """An experiment that cannot be run as described.

    Raised rather than repaired. An experiment quietly corrected into a
    different experiment produces numbers nobody can trace back to a
    hypothesis.
    """


def _bucket(experiment_id, unit_key, version):
    """A stable number in [0, 1) for this unit in this experiment.

    Hashed, not drawn. The same account resolves to the same arm on every
    read, in every process, forever.

    The experiment id is in the material so one account is not placed in
    the same relative position in every experiment it takes part in, which
    would correlate the results of unrelated tests.
    """
    material = f"{experiment_id}|{unit_key}|{version}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


# ------------------------------------------------------------- definition

def arm(arm_id, label, steps, approach=None, mode=STRICT, fallback=None):
    """One sequence being compared. `steps` is a cadence sequence.

    `approach` is the hypothesis this arm represents - problem-led,
    consultative, multi-angle. It is metadata for a reader and for
    reporting; it decides nothing here, because a strategy that changed
    behaviour without being visible in the steps would be a second cadence.
    """
    return {"arm_id": str(arm_id), "label": label, "steps": list(steps or []),
            "approach": approach, "mode": mode,
            "fallback": dict(fallback or {})}


def experiment(experiment_id, arms, unit=ACCOUNT, allocation=None,
               allocation_version=1, testing=None):
    """A set of arms and how traffic is split between them."""
    return {"experiment_id": str(experiment_id), "unit": unit,
            "arms": list(arms or []), "allocation": dict(allocation or {}),
            "allocation_version": int(allocation_version),
            # What this experiment claims to be testing, in the operator's
            # words. Recorded so a reader can tell whether the arms
            # actually differ in that dimension and nothing else.
            "testing": testing}


def validate(exp):
    """Everything wrong with this experiment. Empty means it can run."""
    problems = []
    if not isinstance(exp, dict):
        return ["not an experiment"]
    if not exp.get("experiment_id"):
        problems.append("the experiment has no id")
    if exp.get("unit") not in UNITS:
        problems.append(f"unit must be one of {', '.join(UNITS)}")

    arms = exp.get("arms") or []
    if len(arms) < 2:
        problems.append("an experiment needs at least two arms; one arm is "
                        "a cadence, not a comparison")

    seen = set()
    for entry in arms:
        arm_id = entry.get("arm_id")
        if not arm_id:
            problems.append("an arm has no id")
            continue
        if arm_id in seen:
            problems.append(f"two arms share the id {arm_id!r}")
        seen.add(arm_id)
        if entry.get("mode") not in MODES:
            problems.append(f"{arm_id}: mode must be one of "
                            f"{', '.join(MODES)}")
        try:
            from . import cadence

            cadence.validate_steps(entry.get("steps"))
        except Exception as e:                    # BadCadence, and anything
            problems.append(f"{arm_id}: {e}")

    shares = exp.get("allocation") or {}
    unknown = sorted(set(shares) - seen)
    if unknown:
        problems.append("allocation names arms that do not exist: "
                        + ", ".join(unknown))
    if shares:
        total = sum(float(v) for v in shares.values())
        if abs(total - 1.0) > 0.001:
            problems.append(f"allocation sums to {total:.3f}, not 1.0")
    return problems


def require(exp):
    problems = validate(exp)
    if problems:
        raise BadExperiment("; ".join(problems))
    return exp


def arms_of(exp):
    return list((exp or {}).get("arms") or [])


def arm_by_id(exp, arm_id):
    for entry in arms_of(exp):
        if entry.get("arm_id") == arm_id:
            return entry
    return None


def allocation_of(exp):
    """The share each arm gets. Equal split unless stated.

    An even split is the honest default: unequal shares are a claim about
    which arm you expect to win, and an experiment that started with one
    has already partly answered its own question.
    """
    arms = arms_of(exp)
    if not arms:
        return {}
    stated = (exp or {}).get("allocation") or {}
    if stated:
        return {entry["arm_id"]: float(stated.get(entry["arm_id"], 0.0))
                for entry in arms}
    share = 1.0 / len(arms)
    return {entry["arm_id"]: share for entry in arms}


# ---------------------------------------------------------- eligibility

def channels_of(entry):
    """Which channels this arm's steps actually use."""
    return sorted({step.get("channel") for step in entry.get("steps") or []
                   if step.get("channel")})


def contact_channels(contact):
    """Which channels this person can be reached on at all.

    Read from identity rather than from a stored verdict: a mailbox and a
    profile URL are what a provider can address, and `eligibility` decides
    separately whether either may be used today.
    """
    found = set()
    if (contact or {}).get("email"):
        found.add(EMAIL)
    if (contact or {}).get("linkedin"):
        found.add(LINKEDIN)
    return sorted(found)


def eligible_for(entry, contact):
    """May this contact be put in this arm? Returns (bool, why).

    A strict arm needs every channel it uses. An adaptive arm needs a
    stated fallback for each channel the contact lacks - and the fallback
    is a named channel, not silence, because an arm that quietly dropped
    its LinkedIn steps would be a different arm wearing the same id.
    """
    needs = set(channels_of(entry))
    has = set(contact_channels(contact))
    missing = sorted(needs - has)
    if not missing:
        return True, "every channel this arm uses is available"

    if entry.get("mode") != ADAPTIVE:
        return False, ("this arm uses " + ", ".join(missing)
                       + " and this contact has no "
                       + " or ".join(missing)
                       + ". A strict arm is not assigned to somebody it "
                         "cannot fully run")

    fallback = entry.get("fallback") or {}
    unhandled = [channel for channel in missing
                 if fallback.get(channel) not in has]
    if unhandled:
        return False, ("this arm has no usable fallback for "
                       + ", ".join(unhandled))
    return True, ("falling back for " + ", ".join(missing) + " as the arm "
                  "states")


def eligible_arms(exp, contact):
    return [entry for entry in arms_of(exp) if eligible_for(entry, contact)[0]]


# ------------------------------------------------------------ assignment

def unit_key(exp, rec, contact=None):
    """What is being randomised: an account, or one person.

    Returns None when the unit cannot be identified, which is a refusal
    rather than a fallback - assigning on a missing key would put every
    such contact in the same arm.
    """
    if (exp or {}).get("unit") == CONTACT:
        return (contact or {}).get("key")
    return (rec or {}).get("id")


def recorded(exp, rec, contact=None):
    """An assignment already made for this unit, if it is still the same
    experiment. A stored assignment from a different experiment is not an
    assignment for this one."""
    holder = contact if (exp or {}).get("unit") == CONTACT else rec
    found = (holder or {}).get(ASSIGNMENT_KEY) or {}
    if found.get("experiment_id") != (exp or {}).get("experiment_id"):
        return None
    return found or None


def choose(exp, rec, contact=None):
    """Which arm this unit belongs in. Pure: records nothing.

    A recorded assignment outranks the calculation, always. The allocation
    may move; a contact three steps into a four-step arm may not.
    """
    already = recorded(exp, rec, contact)
    if already and already.get("arm_id"):
        entry = arm_by_id(exp, already["arm_id"])
        if entry is not None:
            return entry, "already assigned"

    key = unit_key(exp, rec, contact)
    if not key:
        return None, "nothing to randomise on"

    open_arms = eligible_arms(exp, contact) if contact is not None \
        else arms_of(exp)
    if not open_arms:
        return None, "no arm can run for this contact"

    shares = allocation_of(exp)
    # Shares are renormalised across the arms this contact can actually be
    # in. Without that, a contact ineligible for two of four arms would
    # land on the last arm half the time purely because the buckets above
    # it were unreachable.
    total = sum(shares.get(entry["arm_id"], 0.0) for entry in open_arms)
    point = _bucket(exp.get("experiment_id"), key,
                    exp.get("allocation_version", 1))
    if total <= 0:
        return open_arms[int(point * len(open_arms))], "even split"

    running = 0.0
    for entry in open_arms:
        running += shares.get(entry["arm_id"], 0.0) / total
        if point < running:
            return entry, "assigned"
    return open_arms[-1], "assigned"


def assign(exp, rec, contact=None, at=None):
    """Choose and record. Mutates the unit; the caller saves.

    Idempotent by construction: a unit that already carries an assignment
    for this experiment keeps it, and nothing is written.
    """
    from . import store

    entry, why = choose(exp, rec, contact)
    if entry is None:
        return None
    holder = contact if (exp or {}).get("unit") == CONTACT else rec
    if holder is None:
        return None
    existing = recorded(exp, rec, contact)
    if existing and existing.get("arm_id") == entry["arm_id"]:
        return existing

    record = {
        "experiment_id": exp.get("experiment_id"),
        "arm_id": entry["arm_id"],
        "unit": exp.get("unit"),
        "unit_key": unit_key(exp, rec, contact),
        "allocation_version": exp.get("allocation_version", 1),
        "at": at or store.now(),
        "why": why,
    }
    holder[ASSIGNMENT_KEY] = record
    return record


def steps_for(campaign, rec, contact=None, config=None):
    """The sequence this contact runs under this campaign's experiment.

    `None` when the campaign has no experiment, which is what every
    campaign has today - the caller then falls back to whatever it would
    have done, and that fallback is `cadence.steps_for`.

    Reads a recorded assignment and does not create one. A sequence being
    *expanded* is not the moment to decide an experiment: expansion happens
    on every page load, and an assignment written there would be an
    assignment made by whoever happened to look.
    """
    exp = (campaign or {}).get(EXPERIMENT_KEY)
    if not exp:
        return None
    already = recorded(exp, rec, contact)
    if not already:
        return None
    entry = arm_by_id(exp, already.get("arm_id"))
    if entry is None:
        return None
    return entry.get("steps") or None


def summarise(exp, recs=None, contacts=None):
    """How the units actually landed, against how they were meant to.

    Configured allocation and observed assignment are two different
    numbers and the gap between them is the interesting one: eligibility
    moves it, and an arm nobody could be assigned to reads as an arm
    nobody chose.
    """
    shares = allocation_of(exp)
    counts = {entry["arm_id"]: 0 for entry in arms_of(exp)}
    unassigned = 0
    for holder in (contacts if (exp or {}).get("unit") == CONTACT
                   else (recs or [])) or []:
        found = (holder or {}).get(ASSIGNMENT_KEY) or {}
        if found.get("experiment_id") != (exp or {}).get("experiment_id"):
            unassigned += 1
            continue
        if found.get("arm_id") in counts:
            counts[found["arm_id"]] += 1
        else:
            unassigned += 1
    assigned = sum(counts.values())
    return {
        "experiment_id": (exp or {}).get("experiment_id"),
        "unit": (exp or {}).get("unit"),
        "testing": (exp or {}).get("testing"),
        "assigned": assigned,
        "unassigned": unassigned,
        "arms": [{
            "arm_id": entry["arm_id"],
            "label": entry.get("label"),
            "approach": entry.get("approach"),
            "steps": len(entry.get("steps") or []),
            "channels": channels_of(entry),
            "shape": _shape(entry),
            "configured": shares.get(entry["arm_id"], 0.0),
            "assigned": counts.get(entry["arm_id"], 0),
            "observed": (counts.get(entry["arm_id"], 0) / assigned
                         if assigned else None),
        } for entry in arms_of(exp)],
        "note": "configured share and observed assignment are different "
                "numbers. Channel eligibility moves the second, and an arm "
                "nobody could be put in reads as an arm nobody chose",
    }


def _shape(entry):
    from . import cadence

    return cadence.describe_steps(entry.get("steps"))


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadencearms",
                                description=__doc__)
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from . import campaigns, store

    found = campaigns.get(a.campaign, campaigns.load()) if a.campaign else None
    exp = (found or {}).get(EXPERIMENT_KEY)
    if not exp:
        print("no cadence experiment on that campaign")
        return 1
    recs = [r for r in store.load()
            if r.get("id") in (found.get("record_ids") or [])]
    out = summarise(exp, recs=recs)
    if a.json:
        print(json.dumps(out, indent=2, default=str))
        return 0
    print(f"{out['experiment_id']}  unit={out['unit']}  "
          f"assigned={out['assigned']}")
    for row in out["arms"]:
        share = f"{row['configured']:.0%}"
        seen = "-" if row["observed"] is None else f"{row['observed']:.0%}"
        print(f"  {row['arm_id']:<10} {row['steps']} steps  {row['shape']:<28}"
              f"  configured {share:>4}  observed {seen:>4}")
    print("\n" + out["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
