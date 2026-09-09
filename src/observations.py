#!/usr/bin/env python3
"""What a message may say it noticed about them.

## Three modules, three questions

`src/outreachclaims.py` checks claims about *us* - "my colleague Anna
emailed you" - against our own event log. `src/claims.py` checks a finished
draft for sentences nothing supports. This module answers the question in
front of both of them: before a word is written, what has this system
actually observed about this company or this person that a message is
allowed to state, and on what evidence.

The three are not interchangeable. `claims` is a refusal at the end;
this is a licence at the start, and a generator that has to guess what it
may mention will guess generously.

## Knowing something and being allowed to say it are different

This is the whole point of the module. The system knows a great deal it
must not repeat:

    a signal              never licenses a sentence. See below
    a low-quality fact    known, not worth writing from
    an aged-out fact      known, and no longer current enough to state
    a fact with no URL    known, and not defensible if they ask

Each of those is a real thing in canonical state and each is refused, with
the reason on the decision. A screen can therefore show "we know this and
will not say it", which is a more useful sentence than either half alone.

## A signal is never evidence for a sentence

`src/signals.py` records that something is happening at an account:
funding, hiring, a new executive. Those move priority, timing and which
angle a campaign leads with, and that is the whole of their job.

They may not be *stated*. A signal carries a type, a date, a confidence
and a short evidence note - and no source URL, because it is a reading
rather than a citation. A message that says "I saw you're hiring three
implementation managers" is making a checkable factual claim, and the only
thing that can back one is a piece of evidence with a link.

So `resolve()` refuses every signal explicitly rather than by omission.
The refusal is visible on the decision, because "the system did not
mention it" and "the system decided not to mention it" look identical from
outside and are not the same thing.

## Recent is itself a claim

"I saw you just opened a Vienna office" asserts a date. An observation
whose evidence is old enough to have left the freshness window may still
be stated - the office is still there - but not as news. `may_call_it_now`
carries that separately from `allowed`, and an undated fact never gets it:
a wrong "last month" is a small lie the recipient can check.

## Permission is not obligation

Every type has a campaign switch, defaulting conservative, exactly as
`outreachclaims` does. Evidence existing does not mean a message should
use it.
"""
import argparse
import json

from . import clients, evidence, personalization, store

# -------------------------------------------------------- observation types

COMPANY_EVENT = "company_event"
COMPANY_ATTRIBUTE = "company_attribute"
PERSON_ROLE = "person_role"
PERSON_CONTENT = "person_content"

TYPES = (COMPANY_EVENT, COMPANY_ATTRIBUTE, PERSON_ROLE, PERSON_CONTENT)

# type -> (label, what a message would be doing with it, the minimum)
OBSERVATIONS = {
    COMPANY_EVENT: (
        "Something the company did",
        "referring to a dated event at their company",
        "a company-subject evidence row with a source URL, usable today, "
        "and dated"),
    COMPANY_ATTRIBUTE: (
        "Something the company is",
        "referring to a durable fact about their company",
        "a company-subject evidence row with a source URL, usable today"),
    PERSON_ROLE: (
        "Something about this person's role",
        "referring to what this person does or has done",
        "a person-subject evidence row for this contact, with a source URL, "
        "usable today"),
    PERSON_CONTENT: (
        "Something this person published",
        "referring to something this person wrote or said",
        "a person-subject evidence row for this contact, authored by them, "
        "with a source URL, usable today"),
}

# Which subject each type needs, so a company fact cannot be phrased as a
# person fact. That swap is the one a generator makes without noticing.
SUBJECT_OF = {
    COMPANY_EVENT: evidence.COMPANY,
    COMPANY_ATTRIBUTE: evidence.COMPANY,
    PERSON_ROLE: evidence.PERSON,
    PERSON_CONTENT: evidence.PERSON,
}

# Types that assert something happened on a date, so an undated row cannot
# support them however good it is.
DATED = {COMPANY_EVENT}

POLICY_KEYS = {
    COMPANY_EVENT: ("observations.company_event", True),
    COMPANY_ATTRIBUTE: ("observations.company_attribute", True),
    PERSON_ROLE: ("observations.person_role", False),
    PERSON_CONTENT: ("observations.person_content", False),
}

# Freshness buckets in which an observation may be stated *as current*.
# Outside them the fact may still be true and still be mentioned - it may
# not be called news.
CURRENT = (evidence.HIGH, evidence.MEDIUM)


class Decision(dict):
    """A licence with its reason. Truthy only when the message may say it."""

    def __bool__(self):
        return bool(self.get("allowed"))


def _no(observation_type, why, **extra):
    return Decision(allowed=False, observation=observation_type, why=why,
                    evidence=None, may_call_it_now=False, **extra)


def _yes(observation_type, why, row, **extra):
    return Decision(allowed=True, observation=observation_type, why=why,
                    evidence=row, **extra)


def _at(config, dotted):
    node = config or {}
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def allowed_by_policy(observation_type, config=None):
    """Is this type switched on for this campaign? Returns (bool, why)."""
    key, default = POLICY_KEYS.get(observation_type, (None, False))
    if key is None:
        return False, f"{observation_type} is not an observation type this " \
                      "system knows"
    value = _at(config or {}, key)
    if value is None:
        return bool(default), (f"{key} is not configured; the default is "
                               f"{'on' if default else 'off'}")
    on = str(value).strip().lower() in ("on", "true", "yes", "1")
    return on, f"{key} is {'on' if on else 'off'}"


# ------------------------------------------------------------- the evidence

def _citable(row):
    """Is this row something a message could point at if asked?

    A fact without a source URL is one we cannot defend when the recipient
    replies "where did you see that". Being true is not sufficient; being
    checkable is the bar for putting it in front of somebody.
    """
    return bool((row.get("source_url") or "").strip())


def candidates(rec, contact_key, observation_type, today=None):
    """Every stored row that could support this type, best first, re-aged.

    Re-aged rather than read as stored: `evidence.make` froze a freshness
    verdict on the day the fact was found, and a licence granted at message
    time has to answer for today. `personalization.stored` does that at the
    door, so this reads through it rather than around it.
    """
    subject = SUBJECT_OF[observation_type]
    rows = personalization.stored(
        rec, subject=subject,
        contact_key=contact_key if subject == evidence.PERSON else None,
        today=today)
    if observation_type == PERSON_CONTENT:
        rows = [r for r in rows if r.get("authored_by_person")]
    if observation_type in DATED:
        rows = [r for r in rows if r.get("published_at")]
    return evidence.rank(rows)


def resolve(observation_type, rec, contact_key=None, config=None, today=None):
    """May a message state an observation of this kind? A `Decision`.

    Fails closed at every step, and every refusal names itself. There is no
    path that returns a maybe and no caller can get the boolean without the
    reason, so a preview cannot show a permitted observation without also
    showing what permits it.
    """
    if observation_type not in TYPES:
        return _no(observation_type, "not an observation type this system "
                                     "knows")

    on, policy_why = allowed_by_policy(observation_type, config)
    if not on:
        return _no(observation_type,
                   "the campaign has this switched off", policy=policy_why)

    rows = candidates(rec, contact_key, observation_type, today)
    if not rows:
        return _no(observation_type,
                   "nothing stored about this "
                   + ("person" if SUBJECT_OF[observation_type] ==
                      evidence.PERSON else "company")
                   + " could support it", policy=policy_why)

    citable = [r for r in rows if _citable(r)]
    if not citable:
        return _no(observation_type,
                   "what is stored has no source to point at, and a fact we "
                   "cannot show them is one we cannot defend when they ask",
                   policy=policy_why, known=len(rows))

    usable = [r for r in citable if r.get("quality") in evidence.USABLE]
    if not usable:
        aged = [r for r in citable if r.get("aged_out")]
        return _no(observation_type,
                   ("what is stored has aged out of being worth writing from"
                    if aged else
                    "what is stored is not strong enough to write from"),
                   policy=policy_why, known=len(citable),
                   aged_out=bool(aged))

    best = usable[0]
    current = best.get("freshness_bucket") in CURRENT
    return _yes(observation_type,
                "a stored, checkable fact supports it",
                {
                    "evidence_id": best.get("evidence_id"),
                    "fact": best.get("fact"),
                    "source_url": best.get("source_url"),
                    "published_at": best.get("published_at"),
                    "age_days": best.get("age_days"),
                    "freshness": best.get("freshness_bucket"),
                    "quality": best.get("quality"),
                },
                policy=policy_why,
                # Separate from `allowed` on purpose. The office is still
                # there; it is not news. An undated fact never earns this,
                # because a wrong "last month" is a small lie the recipient
                # can check against their own calendar.
                may_call_it_now=bool(current and best.get("published_at")),
                why_not_now=(None if current and best.get("published_at")
                             else "the fact is real but not recent enough to "
                                  "be described as news"
                             if best.get("published_at")
                             else "the fact carries no date, so nothing may "
                                  "be said about when it happened"),
                alternatives=len(usable) - 1)


def available(rec, contact_key=None, config=None, today=None):
    """Every observation type, allowed or not, with the reason for each.

    Refused ones are returned too. "Why can this message not mention their
    funding round" is a question an operator asks, and "we have nothing
    with a link" and "the campaign has it switched off" are different
    answers with different fixes.
    """
    out = []
    for observation_type in TYPES:
        label, doing, minimum = OBSERVATIONS[observation_type]
        decision = resolve(observation_type, rec, contact_key, config, today)
        out.append({
            "observation": observation_type,
            "label": label,
            "doing": doing,
            "minimum": minimum,
            "allowed": bool(decision),
            "why": decision.get("why"),
            "evidence": decision.get("evidence"),
            "may_call_it_now": decision.get("may_call_it_now", False),
            "why_not_now": decision.get("why_not_now"),
            "policy": decision.get("policy"),
        })
    return out


# ---------------------------------------------------- what stays unspoken

def withheld(rec, workspace=None, config=None, today=None,
             signal_index=None):
    """What this system knows and will not say, with the reason for each.

    Signals are the whole of the first half. They move priority, timing and
    which angle a campaign leads with; none of that requires stating them,
    and none of them can be stated - a signal carries a reading, not a
    citation, and a message that says "I saw you're hiring" is making a
    checkable claim that nothing here can back.

    Returned as rows rather than left implicit, because a system that
    silently declines to mention something looks exactly like a system that
    never knew it.
    """
    from . import signals as signal_module

    workspace = workspace or rec.get("client")
    found = list(signal_module.derive(rec, workspace, config, today))
    found += (list((signal_index or {}).get(rec.get("id")) or [])
              if signal_index is not None
              else signal_module.for_record(rec.get("id"), workspace))

    out = []
    for signal in found:
        out.append({
            "kind": "signal",
            "what": signal_module.LABEL.get(signal.get("type"),
                                            signal.get("type")),
            "observed_at": signal.get("observed_at"),
            "why": "a signal moves priority, timing and angle. It carries no "
                   "source a message could point at, so it is never stated",
        })

    for row in personalization.stored(rec, today=today):
        if not _citable(row):
            out.append({"kind": "evidence", "what": row.get("fact"),
                        "observed_at": row.get("published_at"),
                        "why": "no source to point at"})
        elif row.get("quality") not in evidence.USABLE:
            out.append({"kind": "evidence", "what": row.get("fact"),
                        "observed_at": row.get("published_at"),
                        "why": ("it has aged out of being worth writing from"
                                if row.get("aged_out") else
                                "not strong enough to write from")})
    return out


def summarise(rec, contact_key=None, config=None, today=None,
              workspace=None):
    rows = available(rec, contact_key, config, today)
    quiet = withheld(rec, workspace, config, today)
    return {
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "allowed": [r for r in rows if r["allowed"]],
        "refused": [r for r in rows if not r["allowed"]],
        "withheld": quiet,
        "counts": {
            "allowed": sum(1 for r in rows if r["allowed"]),
            "may_call_it_now": sum(1 for r in rows if r["may_call_it_now"]),
            "refused": sum(1 for r in rows if not r["allowed"]),
            "withheld": len(quiet),
        },
        "note": "knowing something and being allowed to say it are different "
                "questions. Everything under `withheld` is real and stays "
                "unspoken",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.observations",
                                description=__doc__)
    p.add_argument("--id", required=True)
    p.add_argument("--contact")
    p.add_argument("--today")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    rec = next((r for r in store.load() if r.get("id") == a.id), None)
    if rec is None:
        print(f"no such record: {a.id}")
        return 1
    config = clients.load(rec.get("client"))
    found = summarise(rec, a.contact, config, a.today, rec.get("client"))
    if a.json:
        print(json.dumps(found, indent=2, sort_keys=True))
        return 0

    for row in found["allowed"]:
        now = " (may be called current)" if row["may_call_it_now"] else ""
        print(f"MAY SAY   {row['label']}{now}")
        print(f"            {row['evidence']['fact']}")
        print(f"            {row['evidence']['source_url']}")
    for row in found["refused"]:
        print(f"MAY NOT   {row['label']}: {row['why']}")
    for row in found["withheld"]:
        print(f"UNSPOKEN  {row['what']}: {row['why']}")
    print("\n" + found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
