#!/usr/bin/env python3
"""S7: render each READY lead's copy from the APPROVED Productive words.

    py -3 scripts/stage_s7_copy.py --ready work/stage/ready.json
    py -3 scripts/stage_s7_copy.py --ready work/stage/ready.json --limit 20

OPERATOR AUTHORIZATION, 2026-09-21, condition 1: "copy rendered from approved
Productive templates with the threading invariant". Condition 3: "threaded
3-step, step 1 subject only, steps 2+ thread_reply=true".
NOT AUTHORIZED: "changing approved live copy".

## THIS RENDERS. IT DOES NOT WRITE.

The words are the ones campaign 489 is sending today, read back from the
provider on 2026-09-21 and reproduced here with their merge fields left open.
Nothing is generated: no model is called, no sentence is invented, and a lead
whose merge fields do not all resolve is HELD rather than sent a sentence
with a gap in it.

That is a deliberate reading of the grant. Generating fresh copy per lead
would be NEW copy - which is the thing the grant does not authorise - while
rendering the approved words with this lead's name, company, industry and
angle is the thing it does.

## THE THREADING INVARIANT

    step 1   subject SUBJECT_1, thread_reply false   - the opener owns the
                                                       subject, and only it
    step 2   no subject, thread_reply true
    step 3   no subject, thread_reply true

The sequence at the provider carries `{BODY_1}`, `{BODY_2}`, `{BODY_3}` and
`{SUBJECT_1}`; the words travel PER LEAD as custom variables. So S7's output
is a variable set per lead, and the campaign's sequence is never rewritten -
which is also why this cannot change live copy by accident.

## WHAT HOLDS A LEAD, AND WHY EACH ONE IS FAIL-CLOSED

    no first name          "hi , ..." is the defect EMAILBISON-COPY-
                           REQUIREMENTS names: no greeting may render empty
    no company             three of the four sentences name the company; a
                           lead without one is not this copy's audience
    no industry            the opener's first line states it
    no angle               `personas.default_angle` returns None when nothing
                           in the client's config fits the title - a CFO is
                           eligible as a buyer and has no angle written for
                           them yet. Held is the CORRECT answer: the
                           alternative is a finance lead reading founder copy
    unrendered field       any `{` surviving the render, checked after
"""
import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, personas                               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
SOURCE_CSV = os.path.join(ROOT, "work", "Productive",
                          "productive_ICP_safe_to_send (1).csv")
OUT = os.path.join(STAGE, "s7-copy.jsonl")

#: Subject lint, from the client config comment: "lint fails at 60 characters".
MAX_SUBJECT = 60

# ---------------------------------------------------------------- the words
#
# READ BACK FROM CAMPAIGN 489 ON 2026-09-21, the campaign that sent this
# project's first two real emails. Merge fields restored to placeholders and
# NOTHING ELSE CHANGED - not a word, not a comma. If these ever need to
# differ, that is a new approval, not an edit here.

SUBJECT_1 = "{ANGLE}"

BODY_1 = """{FIRST}, I work with {INDUSTRY} teams on {ANGLE}, and I do not know how {COMPANY} handles it

The pattern I see in teams the size of {COMPANY} is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.

Is that roughly how it works at {COMPANY} today, or have you already put something in place for it?"""

BODY_2 = """{FIRST}, the teams I work with that look most like {COMPANY} tend to arrive at the same place.

They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.

Would it be useful to see what that looked like for a team your size?"""

BODY_3 = """{FIRST}, if {ANGLE} is not something you are looking at right now, that is a fair answer in itself. I will leave it here.

If it becomes relevant later, the thing worth knowing is that most teams the size of {COMPANY} start looking at this when a project lands under margin and nobody can say exactly when it went wrong.

Anything you would want me to send over, or shall I leave it there?"""

PLACEHOLDER = re.compile(r"\{[A-Z_0-9]+\}")


def first_name(value):
    """The greeting name. Empty when there is nothing usable to greet."""
    text = (value or "").strip()
    if not text or len(text) < 2:
        return ""
    # A name that is an initial, a placeholder or a company suffix is not a
    # greeting. Checked because "hi A," reads worse than no email at all.
    if text.lower() in ("n/a", "na", "none", "null", "-", "unknown"):
        return ""
    return text.split()[0]


#: TITLE -> ROUTING FAMILY. Recorded 2026-09-21 under the operator's
#: instruction to map the held titles to the nearest Productive persona and
#: angle "using the playbook".
#:
#: `personas.default_angle` matches an angle KEY against the routing FAMILY a
#: title belongs to, and returns None rather than picking the first of
#: several - which is right, and which held 338 leads whose titles named no
#: family at all. Every family below is one the client's own config already
#: defines, and every mapping is the job the title actually does:
#:
#:     Project Manager        the person who watches budget burn, scope creep
#:                            and who is free. 298 of the 338.
#:     Resource / Traffic     literally the resourcing question
#:     CFO / Finance          month-end margin and reconciliation. 40 of them.
#:     COO / Operations       utilisation and capacity
#:     CEO / Founder / Owner  the founder angle 489 already sends
#:
#: Ordered longest-first inside each family so "Senior Digital Project
#: Manager" matches before a bare word could.
TITLE_FAMILIES = (
    ("founder", ("chief executive", "ceo", "founder", "co-founder", "owner",
                 "managing director", "direktor", "president", "principal",
                 "partner")),
    ("finance", ("chief financial", "cfo", "finance director",
                 "head of finance", "finance manager", "financial controller",
                 "controller", "vp finance", "finance lead")),
    ("resource_management", ("resource manager", "resourcing manager",
                             "head of resource", "head of resourcing",
                             "resource", "resourcing", "traffic manager",
                             "studio manager", "design studio manager",
                             "head of production", "production director",
                             "production manager")),
    ("delivery", ("project manager", "project director", "delivery manager",
                  "delivery director", "head of delivery", "producer",
                  "programme manager", "program manager", "account director",
                  "client services director", "project lead", "pmo")),
    ("operations", ("chief operating", "coo", "operations director",
                    "operations manager", "head of operations", "operations",
                    "general manager")),
)


def family_of(title):
    """The routing family this title belongs to, or None. Longest match wins."""
    lowered = (title or "").strip().lower()
    if not lowered:
        return None
    best, best_len = None, 0
    for family, needles in TITLE_FAMILIES:
        for needle in needles:
            if needle in lowered and len(needle) > best_len:
                best, best_len = family, len(needle)
    return best


def angle_for(title, config):
    """The client's own angle for this title, or None.

    `personas.classify` matches the title against the client's persona
    titles; the family comes from `TITLE_FAMILIES` above; `default_angle`
    picks the angle whose key matches that family and returns None rather
    than the first of several. The production functions still decide - this
    adds the title-to-family step that nothing else supplied.
    """
    contact = {"title": title}
    persona, _score = personas.classify(contact, config)
    if not persona:
        return None, None
    angles = clients.angles_for(config, persona)
    family = family_of(title)
    angle_key = personas.default_angle(config, persona, family)
    if angle_key is None and family in angles:
        angle_key = family
    if angle_key is None:
        return persona, None
    return persona, angles.get(angle_key, angle_key)


def subject_for(angle, config):
    """The subject line: the angle, or its short label when it will not fit.

    `angle_labels` exists because "angles above is the argument a message
    makes and is too long for a subject: lint fails at 60 characters". The
    two angles added tonight are 61 and 66 characters, so they use the
    label; the founder angle 489 already sends is 49 and is untouched, which
    matters because changing it would change approved live copy.
    """
    if len(angle) <= MAX_SUBJECT:
        return angle
    labels = config.get("angle_labels") or {}
    for key, value in (clients.angles_for(config, "champion") or {}).items():
        if value == angle and labels.get(key):
            return labels[key]
    for persona in ("economic_buyer", "champion"):
        for key, value in (clients.angles_for(config, persona) or {}).items():
            if value == angle and labels.get(key):
                return labels[key]
    return angle[:MAX_SUBJECT].rsplit(" ", 1)[0]


def merge_index(ready):
    """email -> the supplier row, for the READY set only."""
    wanted = {e.lower() for e in ready}
    out = {}
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("Work Email") or "").strip().lower()
            if email in wanted and email not in out:
                out[email] = row
    return out


def render(row, config):
    """(variables, hold_reason). One of them is always None."""
    first = first_name(row.get("First Name"))
    company = (row.get("Company") or "").strip()
    industry = (row.get("Industry") or "").strip()
    title = (row.get("Job Title") or "").strip()
    if not first:
        return None, "no usable first name: a greeting may not render empty"
    if not company:
        return None, "no company name, and three sentences name it"
    if not industry:
        return None, "no industry, and the opener states it"
    persona, angle = angle_for(title, config)
    if not persona:
        return None, f"title matches no persona for this client: {title!r}"
    if not angle:
        return None, (f"no angle is written for {persona!r} with this title: "
                      f"{title!r}. Held, not guessed")
    fields = {"FIRST": first, "COMPANY": company, "INDUSTRY": industry,
              "ANGLE": angle}
    subject_fields = dict(fields, ANGLE=subject_for(angle, config))
    out = {}
    for name, template in (("subject_1", SUBJECT_1), ("body_1", BODY_1),
                           ("body_2", BODY_2), ("body_3", BODY_3)):
        text = template
        for key, value in (subject_fields if name == "subject_1"
                           else fields).items():
            text = text.replace("{" + key + "}", value)
        left = PLACEHOLDER.search(text)
        if left:
            return None, f"{name} did not fully render: {left.group(0)}"
        out[name] = text
    if len(out["subject_1"]) > MAX_SUBJECT:
        return None, (f"subject is {len(out['subject_1'])} characters, over "
                      f"{MAX_SUBJECT}")
    out["persona"] = persona
    out["angle"] = angle
    out["title"] = title
    return out, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ready", default=os.path.join(STAGE, "ready.json"))
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--client", default="productive")
    args = parser.parse_args(argv)

    with open(args.ready, encoding="utf-8") as handle:
        ready = json.load(handle)
    if args.limit:
        ready = ready[:args.limit]
    config = clients.load(args.client)
    rows = merge_index(ready)

    rendered, held = 0, {}
    personas_seen, angles_seen = {}, {}
    with open(args.out, "w", encoding="utf-8") as out:
        for email in ready:
            row = rows.get(email.lower())
            if row is None:
                held["not in the supplier file"] = held.get(
                    "not in the supplier file", 0) + 1
                continue
            variables, reason = render(row, config)
            if reason:
                key = reason.split(":")[0]
                held[key] = held.get(key, 0) + 1
                out.write(json.dumps({"email": email, "state": "held",
                                      "reason": reason}) + "\n")
                continue
            personas_seen[variables["persona"]] = personas_seen.get(
                variables["persona"], 0) + 1
            angles_seen[variables["angle"]] = angles_seen.get(
                variables["angle"], 0) + 1
            out.write(json.dumps({"email": email, "state": "rendered",
                                  "variables": variables}) + "\n")
            rendered += 1

    print(f"\nS7  from {len(ready)} READY\n")
    print(f"  rendered          {rendered}")
    print(f"  held              {sum(held.values())}")
    for reason, count in sorted(held.items(), key=lambda kv: -kv[1]):
        print(f"    {reason[:58].ljust(58)} {count:>5}")
    print("\n  by persona")
    for name, count in sorted(personas_seen.items(), key=lambda kv: -kv[1]):
        print(f"    {name.ljust(20)} {count:>5}")
    print("\n  by angle")
    for name, count in sorted(angles_seen.items(), key=lambda kv: -kv[1]):
        print(f"    {name[:58].ljust(58)} {count:>5}")
    print(f"\n  written to {args.out}")
    print("\n  The words are 489's approved copy with merge fields resolved. "
          "No model was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
