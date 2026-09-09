#!/usr/bin/env python3
"""Two steps in one sequence that say the same thing.

Each step can pass lint on its own and the sequence can still be broken: an
email on day 1 and the same email again on day 15 is a defect no per-step check
can see, because nothing is wrong with either message in isolation. It is only
wrong the second time it arrives.

The comparison is on the **substantive body**. A greeting, a one-line call to
action and a signature repeat in every message by design, and flagging those
would make the check useless within a week. So short paragraphs are set aside
and what remains - the argument the email is actually making - is what gets
compared.

There is no similarity threshold. Two bodies are duplicates when their
normalised substantive text is *equal*, which covers byte-identical copy,
whitespace differences, casing and punctuation. A fuzzy ratio would need a
number nobody can defend, and this codebase already refuses fuzzy matching
where a wrong answer costs something - the same reasoning applies here.

  python -m src.duplicates --record northwind
"""
import argparse
import json
import re
import unicodedata

from . import cadence, clients, lint, store

# Stable codes. These are read by QA, the preview and the Slack summary, so
# they are vocabulary rather than prose.
DUPLICATE_BODY = "duplicate_email_body"
DUPLICATE_SUBJECT = "duplicate_email_subject"
CODES = (DUPLICATE_BODY, DUPLICATE_SUBJECT)

# A paragraph shorter than this is structure rather than argument: "Hi Mara,",
# "Worth a look?", a sign-off, a booking link. Eight words is long enough to
# exclude those and short enough to keep a real one-sentence point.
MIN_SUBSTANTIVE_WORDS = 8

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize(text):
    """Casing, punctuation, accents and whitespace removed.

    Everything this strips is a difference a recipient would not notice, which
    is the definition being used: two messages are the same message when the
    only differences are ones nobody reads.
    """
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _PUNCTUATION.sub(" ", text.lower())
    return _WHITESPACE.sub(" ", text).strip()


def paragraphs(body):
    """Blank-line separated blocks, with hard wrapping folded back in."""
    body = str(body or "").replace("\r\n", "\n").replace("\r", "\n")
    return [_WHITESPACE.sub(" ", block).strip()
            for block in re.split(r"\n\s*\n", body) if block.strip()]


def substantive(body):
    """The paragraphs that carry the argument, normalised.

    Returns a list, so a caller can show what was compared rather than only
    whether it matched.
    """
    out = []
    for block in paragraphs(body):
        normalised = normalize(block)
        if len(normalised.split()) >= MIN_SUBSTANTIVE_WORDS:
            out.append(normalised)
    return out


def fingerprint(body):
    """One comparable string, or "" when there is nothing substantive to compare.

    An empty fingerprint is not a match with another empty one. Two short
    notes that happen to be all greeting are not evidence of duplication, and
    treating them as such would flag every LinkedIn note against every other.
    """
    return "\n".join(substantive(body))


def same_body(left, right):
    """Do these two emails make the same argument?"""
    first, second = fingerprint(left), fingerprint(right)
    return bool(first) and first == second


def same_subject(left, right):
    first, second = normalize(left), normalize(right)
    return bool(first) and first == second


def _difference(left, right):
    """Why two bodies are considered the same, in words for a human."""
    if left == right:
        return "byte for byte identical"
    if paragraphs(left) == paragraphs(right):
        return "identical apart from line breaks"
    if normalize(left) == normalize(right):
        return "identical apart from casing, punctuation or whitespace"
    return ("the substantive paragraphs are identical; only greetings, "
            "sign-offs or short calls to action differ")


# ------------------------------------------------------------- finding them

def email_steps(rec, contact_key, timeline=None, config=None,
                campaign=None):
    """Every email step for one contact, with its final copy.

    Reads the expanded timeline rather than the stored cadence, so a template
    step is compared as the prospect would receive it rather than as the
    template it came from.
    """
    if timeline is None:
        timeline = cadence.build(rec, config,
                                 campaign=campaign).get("contacts") or {}
    steps = timeline.get(contact_key) or {}
    out = []
    for key in sorted(steps, key=lambda k: (steps[k].get("day") or 0, k)):
        step = steps[key]
        if step.get("channel") != "email":
            continue
        out.append({"step": key, "day": step.get("day"),
                    "subject": step.get("subject") or "",
                    "body": step.get("body") or "",
                    "status": step.get("status")})
    return out


def for_contact(rec, contact_key, timeline=None, config=None):
    """Every duplicate pair among one contact's email steps."""
    steps = email_steps(rec, contact_key, timeline, config)
    findings = []
    for i, first in enumerate(steps):
        for second in steps[i + 1:]:
            body = same_body(first["body"], second["body"])
            subject = same_subject(first["subject"], second["subject"])
            if body:
                findings.append({
                    "code": DUPLICATE_BODY,
                    "record_id": rec.get("id"),
                    "contact_key": contact_key,
                    "steps": [first["step"], second["step"]],
                    "days": [first["day"], second["day"]],
                    "also_duplicate_subject": subject,
                    "why": _difference(first["body"], second["body"]),
                    "compared": len(substantive(first["body"])),
                })
            elif subject:
                # Reported, never blocking on its own: two steps may share a
                # subject line deliberately, and the body is what arrives.
                findings.append({
                    "code": DUPLICATE_SUBJECT,
                    "record_id": rec.get("id"),
                    "contact_key": contact_key,
                    "steps": [first["step"], second["step"]],
                    "days": [first["day"], second["day"]],
                    "subject": first["subject"],
                    "why": "the same subject line on two steps, with "
                           "different bodies",
                })
    return findings


def for_record(rec, config=None, recs=None, paused_set=None,
               campaign=None):
    timeline = cadence.build(rec, config, recs=recs,
                             paused_set=paused_set,
                             campaign=campaign).get("contacts") or {}
    out = []
    for contact in rec.get("contacts") or []:
        out.extend(for_contact(rec, lint.contact_key(contact), timeline,
                               config))
    return out


def find(recs, config=None, campaign=None):
    """Every duplicate across a batch, one pause scan for the whole thing.

    `campaign` decides the sequence every record here is compared
    across: two bodies are only duplicates of each other if both steps
    are actually in the cadence that will run.
    """
    paused_set = cadence.paused_domains(recs or [])
    out = []
    for rec in recs or []:
        out.extend(for_record(rec, config, recs=recs,
                              paused_set=paused_set, campaign=campaign))
    return out


def summarise(findings):
    """Counts, split by code, plus the contacts each affects."""
    bodies = [f for f in findings if f["code"] == DUPLICATE_BODY]
    subjects = [f for f in findings if f["code"] == DUPLICATE_SUBJECT]
    return {
        "duplicate_bodies": len(bodies),
        "duplicate_subjects": len(subjects),
        "contacts_with_duplicate_bodies": len(
            {(f["record_id"], f["contact_key"]) for f in bodies}),
        "contacts_with_duplicate_subjects": len(
            {(f["record_id"], f["contact_key"]) for f in subjects}),
        # The pairs, so a page can name them rather than only count them.
        "pairs": [{"record_id": f["record_id"], "contact_key": f["contact_key"],
                   "code": f["code"], "steps": f["steps"], "why": f["why"]}
                  for f in findings],
    }


def blocking(findings):
    """What must stop an approval. A shared subject alone never does."""
    return [f for f in findings if f["code"] == DUPLICATE_BODY]


def steps_involved(findings):
    """(record_id, contact_key, step) for every step in a blocking pair.

    So the preview can mark the steps themselves rather than only print a
    warning somewhere else on the page.
    """
    out = set()
    for finding in findings:
        for step in finding["steps"]:
            out.add((finding["record_id"], finding["contact_key"], step))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record")
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    if a.record:
        recs = [r for r in recs if r.get("id") == a.record]
    if a.client:
        recs = [r for r in recs if r.get("client") == a.client]
    config = {}
    try:
        config = clients.load(a.client or (recs[0].get("client") if recs
                                           else None))
    except Exception:
        config = {}

    findings = find(recs, config)
    if a.json:
        print(json.dumps({"findings": findings,
                          "summary": summarise(findings)}, indent=2))
        return 0
    if not findings:
        print("  no two email steps say the same thing")
        return 0
    for finding in findings:
        marker = "BLOCKS" if finding["code"] == DUPLICATE_BODY else "  warn"
        print(f"  {marker}  {finding['record_id']}/{finding['contact_key']}  "
              f"{' and '.join(finding['steps'])}: {finding['code']}")
        print(f"          {finding['why']}")
    return 1 if blocking(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
