#!/usr/bin/env python3
"""Do this contact's email and LinkedIn steps read as one conversation?

## Why this is not covered by what already exists

Three modules each check part of it and none checks the whole:

- `duplicates.py` compares emails to emails. Line for line it is the right
  comparison, and it filters to `channel == "email"` - so a LinkedIn note that
  makes the identical argument to day 1's email has never been compared to it.
- `cadence.cross_channel_leaks()` catches a step that *names* the other
  channel. That is one specific leak, not coherence.
- `eligibility.decide()` answers whether one step may go out. It has no view
  of the sequence around it.

The prospect does not experience three modules. They experience seven messages
from one company over three weeks, and the failure they notice is the one none
of the three was looking for: the same sentence twice in two places, an email
arguing margin while the note argues capacity, or a message arriving after they
already replied.

## What this does not do

It does not decide eligibility, and it does not block. It reports findings with
a severity, and `qa.py` is where a blocker becomes a verdict. Two copies of
"may this send" is the failure `eligibility.py` exists to prevent, and this
module is not going to become the second one.

Every finding names the two steps it is about, so a reviewer can read them
side by side rather than trusting a label.

  python -m src.coherence --record <id> --contact <key>
"""
import argparse
import json

from . import cadence, clients, duplicates, store

# Severities. `blocking` is what QA escalates; `review` is for a human.
BLOCK = "block"
REVIEW = "review"
NOTE = "note"
SEVERITIES = (BLOCK, REVIEW, NOTE)

# A call to action, in the forms this codebase's own templates produce. Matched
# on the normalised text, so punctuation and casing do not hide one.
CTA_PHRASES = (
    "worth a look", "worth a conversation", "open to a look",
    "happy to share", "would that help", "is that useful",
    "want me to send", "shall i send", "worth fifteen minutes",
    "worth 15 minutes", "any interest", "would you be open",
)

# How much overlap between two openings counts as the same opening. Compared
# on the first sentence only: outbound copy legitimately repeats a company
# name, and flagging that would make the check noise.
OPENING_WORDS = 8
OPENING_OVERLAP = 0.75


def _finding(severity, kind, message, steps=(), detail=None):
    return {"severity": severity, "kind": kind, "message": message,
            "steps": list(steps), "detail": detail}


def _text_of(step):
    """The words a recipient would read, whatever channel carried them."""
    if step.get("channel") == "linkedin":
        return step.get("note") or step.get("message") or ""
    return step.get("body") or ""


def _ordered(steps):
    """Steps in the order they would arrive, with their keys."""
    return sorted(((key, step) for key, step in steps.items()),
                  key=lambda pair: (pair[1].get("day") or 0, pair[0]))


def _first_sentence(text):
    normalised = duplicates.normalize(text)
    return normalised.split(".")[0].split()[:OPENING_WORDS]


def _overlap(left, right):
    if not left or not right:
        return 0.0
    shared = len(set(left) & set(right))
    return shared / float(max(len(left), len(right)))


# ------------------------------------------------------------- the checks

def duplicate_across_channels(ordered):
    """The same argument made twice on two different channels.

    `duplicates.fingerprint` returns "" when there is nothing substantive, and
    two empty fingerprints are deliberately not a match - otherwise every short
    LinkedIn note would match every other one.
    """
    out = []
    for i, (key, step) in enumerate(ordered):
        for other_key, other in ordered[i + 1:]:
            if step.get("channel") == other.get("channel"):
                continue          # duplicates.py already owns same-channel
            if duplicates.same_body(_text_of(step), _text_of(other)):
                out.append(_finding(
                    BLOCK, "duplicate_across_channels",
                    f"{key} and {other_key} make the same argument on "
                    f"different channels",
                    steps=(key, other_key),
                    detail=duplicates.fingerprint(_text_of(step))[:200]))
    return out


def repeated_opening(ordered):
    """Two steps that open with the same words but then diverge.

    Same-channel or cross-channel: a prospect reading the day 3 note after the
    day 1 email notices the identical first line whichever way round it came.

    Pairs whose *whole* body already matches are skipped and left to
    `duplicates.py` and `duplicate_across_channels`. Reporting them here too
    would mean two findings for one problem, and a reviewer counting findings
    would think there were two things to fix.
    """
    out = []
    for i, (key, step) in enumerate(ordered):
        text = _text_of(step)
        opening = _first_sentence(text)
        if len(opening) < 4:
            continue
        for other_key, other in ordered[i + 1:]:
            other_text = _text_of(other)
            if duplicates.same_body(text, other_text):
                continue                  # a duplicate, not a shared opening
            other_opening = _first_sentence(other_text)
            if len(other_opening) < 4:
                continue
            if _overlap(opening, other_opening) >= OPENING_OVERLAP:
                out.append(_finding(
                    REVIEW, "repeated_opening",
                    f"{key} and {other_key} open with nearly the same words",
                    steps=(key, other_key),
                    detail=" ".join(opening)))
    return out


def repeated_cta(ordered):
    """The same ask, in the same words, more than once.

    A cadence is allowed to ask more than once - that is what a cadence is.
    What reads as automated is asking in *identical* words, so this matches on
    the phrase rather than on the presence of an ask.
    """
    seen, out = {}, []
    for key, step in ordered:
        text = duplicates.normalize(_text_of(step))
        for phrase in CTA_PHRASES:
            if phrase in text:
                if phrase in seen:
                    out.append(_finding(
                        REVIEW, "repeated_cta",
                        f"{seen[phrase]} and {key} use the same call to "
                        f"action, word for word",
                        steps=(seen[phrase], key), detail=phrase))
                else:
                    seen[phrase] = key
    return out


def contradictory_angles(ordered):
    """Two steps arguing different angles at the same person.

    The angle is on the step where the generator put it. Where it is absent
    nothing is claimed: an unlabelled step is not evidence of agreement.
    """
    angles = {}
    for key, step in ordered:
        angle = step.get("angle")
        if angle:
            angles.setdefault(angle, []).append(key)
    if len(angles) <= 1:
        return []
    named = ", ".join(f"{angle} ({'/'.join(keys)})"
                      for angle, keys in sorted(angles.items()))
    return [_finding(
        REVIEW, "contradictory_angles",
        f"this contact is approached on {len(angles)} different angles: {named}",
        steps=[k for keys in angles.values() for k in keys],
        detail=sorted(angles))]


def ordering_problems(ordered):
    """Two channels on one day, or a sequence that does not advance.

    BUILD-SPEC section 7: never two channels on the same day for the same
    person. That rule is enforced when the timeline is built; this is the
    check that it *stayed* true through template expansion and any hand edit.
    """
    out, by_day = [], {}
    for key, step in ordered:
        day = step.get("day")
        if day is None:
            out.append(_finding(NOTE, "step_without_a_day",
                                f"{key} has no day", steps=(key,)))
            continue
        by_day.setdefault(day, []).append((key, step.get("channel")))
    for day, entries in sorted(by_day.items()):
        channels = {channel for _, channel in entries}
        if len(entries) > 1 and len(channels) > 1:
            out.append(_finding(
                BLOCK, "two_channels_one_day",
                f"day {day} carries {len(entries)} steps on "
                f"{len(channels)} channels",
                steps=[key for key, _ in entries]))
    return out


def leaks(steps):
    """The one cross-channel rule cadence already owns. Reported here too."""
    return [_finding(BLOCK, "cross_channel_leak", leak, steps=(leak.split(":")[0],))
            for leak in cadence.cross_channel_leaks(steps)]


def after_the_pause(ordered, paused_at=None):
    """Anything scheduled after the company answered.

    `paused_at` is a day number. A step on the same day is included: the reply
    and the send are not ordered within a day, and the safe reading of an
    ambiguous ordering is that the send should not have gone.
    """
    if paused_at is None:
        return []
    out = []
    for key, step in ordered:
        day = step.get("day")
        if day is None or day < paused_at:
            continue
        if step.get("status") in ("paused", "blocked", "skipped", "not_planned"):
            continue                      # correctly stopped
        out.append(_finding(
            BLOCK, "scheduled_after_reply",
            f"{key} is on day {day}, after the reply on day {paused_at}, and "
            f"its status is {step.get('status')!r}",
            steps=(key,)))
    return out


def ineligible_channel(ordered, channel_verdict):
    """A step planned on a channel this contact cannot be reached on."""
    if not channel_verdict:
        return []
    out = []
    for key, step in ordered:
        channel = step.get("channel")
        allowed = channel_verdict.get(f"{channel}_eligible")
        if allowed is not False:
            continue
        if step.get("status") in ("blocked", "skipped", "not_planned", "paused"):
            continue                      # correctly excluded
        reason = channel_verdict.get(f"{channel}_excluded_reason")
        out.append(_finding(
            BLOCK, "ineligible_channel",
            f"{key} is planned on {channel}, which is excluded for this "
            f"contact: {reason}",
            steps=(key,), detail=reason))
    return out


# ------------------------------------------------------------- the report

def for_contact(rec, contact_key, timeline=None, config=None,
                channel_verdict=None, paused_at=None, campaign=None):
    """Every coherence finding for one person's whole sequence."""
    config = config or clients.load(rec.get("client"))
    if timeline is None:
        timeline = cadence.build(rec, config, campaign=campaign)
    steps = (timeline.get("contacts") or {}).get(contact_key) or {}
    ordered = _ordered(steps)

    findings = []
    findings += duplicate_across_channels(ordered)
    findings += repeated_opening(ordered)
    findings += repeated_cta(ordered)
    findings += contradictory_angles(ordered)
    findings += ordering_problems(ordered)
    findings += leaks(steps)
    findings += after_the_pause(ordered, paused_at)
    findings += ineligible_channel(ordered, channel_verdict)

    return {
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "steps_checked": len(ordered),
        "findings": findings,
        "blocking": [f for f in findings if f["severity"] == BLOCK],
        "verdict": verdict(findings),
    }


def verdict(findings):
    """One word. A blocker is never averaged away by a clean check."""
    if any(f["severity"] == BLOCK for f in findings):
        return BLOCK
    if any(f["severity"] == REVIEW for f in findings):
        return REVIEW
    return "pass"


def summarise(reports):
    """Counts across many contacts, for a campaign-level line."""
    counts = {BLOCK: 0, REVIEW: 0, "pass": 0}
    by_kind = {}
    for report in reports:
        counts[report["verdict"]] = counts.get(report["verdict"], 0) + 1
        for finding in report["findings"]:
            by_kind[finding["kind"]] = by_kind.get(finding["kind"], 0) + 1
    return {
        "contacts_checked": len(reports),
        "by_verdict": counts,
        "by_kind": dict(sorted(by_kind.items())),
        "coherent": counts["pass"],
        "needs_review": counts.get(REVIEW, 0),
        "blocked": counts.get(BLOCK, 0),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.coherence",
                                description=__doc__)
    p.add_argument("--record", required=True)
    p.add_argument("--contact")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    rec = store.get(args.record)
    if not rec:
        raise SystemExit(f"no such record: {args.record}")
    config = clients.load(rec.get("client"))
    # A report on one record is a report on the sequence that record will
    # actually run, which is its campaign's - the same question
    # `push.collect` and `approve.pending` ask of a record they were handed.
    from . import campaigns

    campaign = campaigns.by_record().get(rec.get("id"))
    timeline = cadence.build(rec, config, campaign=campaign)
    keys = [args.contact] if args.contact else list(timeline["contacts"])

    reports = [for_contact(rec, key, timeline, config, campaign=campaign)
               for key in keys]
    if args.json:
        print(json.dumps({"reports": reports, "summary": summarise(reports)},
                         indent=2))
        return 0
    for report in reports:
        print(f"\n{report['contact_key']}  {report['verdict'].upper()}  "
              f"({report['steps_checked']} steps)")
        for finding in report["findings"]:
            print(f"  {finding['severity']:<7} {finding['kind']}")
            print(f"          {finding['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
