"""TASK 0030 (GLM-B): an unwritten email step must not vanish silently.

THE DEFECT THIS PINS. A generated email step whose body has never been
written disappears from the rendered timeline instead of being reported.

The chain, verified on master before this module was written:

  - `cadence.expand_step` returns None for a `generated` step whose stored
    words are empty - "phase 5 has not written it yet"
    (`src/cadence.py`, the `if not (written or "").strip(): return None`
    branch).
  - `cadence.build` then keeps a step whose spec carries `requires` (it is
    synthesised as a minimal waiting step, because "omitting it hides the
    step from approval and from the campaign graph") - and `continue`s past
    every step that does not.
  - In `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1` (and in
    `PRODUCTIVE_EMAIL_EIGHT_V1`), the `li2`..`li5` steps carry
    `requires: connected` and the `em1`..`em5` steps carry no `requires` at
    all. So the LinkedIn half survives an unwritten note and the email half
    does not: an email step with no body is silently dropped.

Nobody downstream can see the hole. `preview._person_card` renders one row
per step the timeline returns, `approve` walks the same timeline, `qa` and
`report` count what it holds - each would show a four-step cadence for a
contact whose cadence is five steps, with no indication that a fifth exists
and is unwritten. The operator approves a shorter campaign than the one he
thinks he is approving.

THE CONTRACT THIS REQUIRES, AND IT IS RED ON MASTER UNTIL THE OPERATOR
ORDERS THE FIX: a generated email step with no stored body must be REPORTED
on the rendered timeline with status `stepstate.PLANNED` - the state
machine's own gloss is "a step exists in the timeline but has no draft" -
never silently dropped.

Why PLANNED and not a new word. `stepstate` is "deliberately built over the
names that already exist rather than a parallel vocabulary", and it already
defines exactly this state; `src/qa.py` already reads it (a contact counts
as "complete" only when no step of theirs is `planned`), so the report has
a consumer the day the fix lands. A bodiless step is also not `blocked`:
blocked says a rule refuses words that exist, and the truth is that nobody
wrote them. "Four ways to not send, and collapsing them loses the only
information an operator can act on."

THE ASSERTION IS ON THE REPORT, NOT ON PRESENCE. The guard below never
asserts `"em3" in steps`: a step that appeared looking healthy would pass
that and still hide the gap. It asserts the step's STATUS says the draft is
missing. Presence of the control (every body written -> every step
rendered, none reported planned) is what makes the guard a test OF the
deleted body rather than of a broken fixture: same record, same build, the
one deleted body is the only difference.

THE FIX IS NOT HERE AND IS NOT `requires`. Adding `requires` to the em
steps would change what the cadence means (a gate on an event) to paper
over a reporting gap; the operator decides the fix. This module only
defines the observable behaviour any fix must produce.
"""
import unittest

from src import cadence, cadencelibrary, clients, stepstate

# The email half of `productive_li_heavy_v1`, verbatim from the library:
# days 1, 4, 8, 12 and 21, every step `generated`, none carrying
# `requires`. Carried on the campaign row as `cadence_steps`, which is the
# production mechanism for a campaign running its own sequence - and it
# keeps the LinkedIn half's template rendering out of a test that is about
# the email half.
EMAIL_STEPS = tuple(dict(s) for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
                    if s.get("channel") == "email")
EM_KEYS = ("em1", "em2", "em3", "em4", "em5")

CONTACT = "unwritten-c1"
DOMAIN = "example.com"


def all_bodies():
    """Every em step written. Distinct strings so a swap cannot hide."""
    return {k: f"body written for {k}" for k in EM_KEYS}


def record(bodies):
    """One ready record whose contact holds exactly the bodies given.

    A missing key in `bodies` is the defect's starting condition: phase 5
    never wrote that step's words. The record is otherwise complete, so the
    only thing that can differ between two builds from this helper is the
    absence of one body.
    """
    stored = {k: {"channel": "email", "subject": f"subject for {k}",
                  "body": bodies[k]}
              for k in EM_KEYS if bodies.get(k)}
    return {"id": "unwritten-co", "client": "productive", "domain": DOMAIN,
            "company": "Example", "state": "ready",
            "cadence": {CONTACT: stored},
            "contacts": [{"key": CONTACT, "email": f"c1@{DOMAIN}",
                          "first_name": "Ana", "last_name": "Tester",
                          "sendable": True, "verified": True}]}


class UnwrittenEmailStep(unittest.TestCase):
    """A step with no body is reported, never silently dropped."""

    def setUp(self):
        self.config = clients.load("productive")
        self.campaign = {"campaign_id": "camp-unwritten",
                         "cadence_steps": [dict(s) for s in EMAIL_STEPS]}

    def steps(self, bodies):
        built = cadence.build(record(bodies), self.config,
                              campaign=self.campaign)
        return built["contacts"][CONTACT]

    def test_every_written_step_is_rendered_and_none_is_reported_planned(self):
        """The control: with every body written the timeline is complete.

        Presence is asserted HERE and only here - this is the run that
        proves the harness, the record and the build are sound, so the red
        test below is caused by the deleted body and nothing else.
        """
        steps = self.steps(all_bodies())
        self.assertEqual(sorted(k for k in steps if k in EM_KEYS),
                         sorted(EM_KEYS),
                         f"a fully written cadence must render all five "
                         f"email steps; rendered: {sorted(steps)}")
        for key in EM_KEYS:
            self.assertNotEqual(
                steps[key].get("status"), stepstate.PLANNED,
                f"{key} is written; reporting it as having no draft would "
                f"be a false missing-report")

    def test_an_unwritten_email_step_is_reported_missing_not_dropped(self):
        """THE GUARD. Red on master until the operator orders the fix.

        em3's body is deleted from an otherwise complete record. The built
        timeline must REPORT em3 as a step with no draft - status
        `stepstate.PLANNED` - so that every consumer of `cadence.build`
        (preview, approve, qa, report) shows a five-step cadence with one
        step named as unwritten, rather than a silent four-step one.
        """
        bodies = all_bodies()
        del bodies["em3"]                    # the one deleted body
        steps = self.steps(bodies)
        reported = (steps.get("em3") or {}).get("status")
        self.assertEqual(
            reported, stepstate.PLANNED,
            "em3's body was never written and the rendered timeline must "
            "REPORT that (status 'planned': a step exists in the timeline "
            "but has no draft). "
            + ("The step is present but its status does not say the draft "
               "is missing, which hides the gap behind a healthy-looking "
               f"entry: {reported!r}."
               if steps.get("em3") else
               "The step has no entry at all - it silently dropped out of "
               f"the timeline, which renders {sorted(steps)}: a four-step "
               "cadence with no indication a fifth exists and is unwritten."))


if __name__ == "__main__":
    unittest.main()
