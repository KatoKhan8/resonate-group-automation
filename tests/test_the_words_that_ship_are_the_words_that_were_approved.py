"""The sequence readback compares placeholders. This one compares the text.

`bison_readback` passes on campaign 487 and is right to: three steps, correct
`thread_reply`, correct waits, and subjects reading `{SUBJECT_1}` on both
sides. Every field it compares is a MERGE VARIABLE. A campaign can pass it
with every rendered email wrong - a variable resolving empty, a name that
never substituted, a body carrying another lead's company.

The provider renders `scheduled_emails` days before it sends them, with each
lead's own variables already substituted, so the sendable text is readable in
advance. These tests are about comparing it honestly.

THE MEASUREMENT BEHIND `unwrap`. Run against 487 on 2026-09-20 the first
version failed three of ten rows: `Marketing &amp; Advertising` queued
against `Marketing & Advertising` approved. Reading lead 203709's own `body_1`
custom variable back showed a BARE `&` on our side, which located the escape
at the provider's render rather than in our write. So the entities are undone
before comparing - and only on the provider's side, only once, and only in
the body.

No network: a fake provider, fixtures built from the real 487 shape, and no
real prospect's name or address.
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts import queued_copy_readback as qcr  # noqa: E402


APPROVED_BODY = ("Ada, I work with Marketing & Advertising teams on "
                 "utilisation, and I do not know how Northwind handles it"
                 "\n\nThe pattern I see is that the numbers arrive too late."
                 "\n\nIs that roughly how it works at Northwind today?")
RENDERED_BODY = ("<p>Ada, I work with Marketing &amp; Advertising teams on "
                 "utilisation, and I do not know how Northwind handles it"
                 "<br><br>The pattern I see is that the numbers arrive too "
                 "late.<br><br>Is that roughly how it works at Northwind "
                 "today?</p>")
SUBJECT = "utilisation and capacity across live projects"


def record(email="ada@northwind.test", key="ada-lovelace",
           subject=SUBJECT, body=APPROVED_BODY):
    return {"id": "northwind-test",
            "contacts": [{"key": key, "email": email}],
            "cadence": {key: {"em1": {"subject": subject, "body": body,
                                      "channel": "email"}}}}


def queued(email="ada@northwind.test", subject=SUBJECT, body=RENDERED_BODY,
           step_id=4742):
    return {"id": 1, "sequence_step_id": step_id, "email_subject": subject,
            "email_body": body, "status": "scheduled",
            "lead": {"id": 1, "email": email}}


class FakeBison:
    """Only the two reads `check` makes."""

    def __init__(self, steps, rows):
        self._steps = steps
        self._rows = rows

    def sequence_steps(self, campaign_id):
        return self._steps

    def scheduled_emails(self, campaign_id):
        return self._rows


CANONICAL = [{"bison_campaign_id": 487,
              "cadence_steps": [{"key": "em1"}, {"key": "em2"},
                                {"key": "em3"}]}]
STEPS = [{"id": 4742}, {"id": 4743}, {"id": 4744}]


def run(rows, snapshot=None, canonical=None, steps=None):
    return qcr.check(487, snapshot if snapshot is not None else [record()],
                     canonical if canonical is not None else CANONICAL,
                     FakeBison(steps if steps is not None else STEPS, rows))


def verdicts(findings):
    return [(f[0], f[2]) for f in findings]


class UnwrapTest(unittest.TestCase):

    def test_the_factorys_paragraph_wrap_is_undone(self):
        self.assertEqual("one\n\ntwo",
                         qcr.unwrap("<p>one<br><br>two</p>"))

    def test_a_single_break_is_a_single_newline(self):
        self.assertEqual("one\ntwo", qcr.unwrap("<p>one<br>two</p>"))

    def test_the_providers_entities_are_undone_because_they_are_the_providers(self):
        """Measured on 487: our `body_1` holds a bare `&`, the queued row
        holds `&amp;`, so the escape is the provider's render and the
        prospect sees `&`."""
        self.assertEqual("Marketing & Advertising",
                         qcr.unwrap("<p>Marketing &amp; Advertising</p>"))

    def test_a_double_encoded_body_still_fails(self):
        """One level of unescaping, not a loop. A prospect really would read
        `&amp;` here, so it must not be absorbed."""
        self.assertEqual("Marketing &amp; Advertising",
                         qcr.unwrap("<p>Marketing &amp;amp; Advertising</p>"))

    def test_tags_are_undone_before_entities(self):
        """Reversed, an escaped `&lt;br&gt;` would become a real line break
        and this would approve markup nobody wrote."""
        self.assertEqual("one<br>two", qcr.unwrap("<p>one&lt;br&gt;two</p>"))

    def test_a_shape_the_factory_does_not_write_is_refused_not_guessed(self):
        self.assertIsNone(qcr.unwrap("<div>one</div>"))
        self.assertIsNone(qcr.unwrap("bare text"))
        self.assertIsNone(qcr.unwrap(None))


class CheckTest(unittest.TestCase):

    def test_a_row_carrying_the_approved_text_passes(self):
        self.assertEqual([("row", "PASS")], verdicts(run([queued()])))

    def test_a_changed_body_fails_and_says_where(self):
        rows = [queued(body=RENDERED_BODY.replace("too late", "on time"))]
        findings = run(rows)
        self.assertEqual([("body", "FAIL")], verdicts(findings))
        self.assertIn("differs at", findings[0][3])

    def test_an_unresolved_variable_fails(self):
        """The defect the sequence readback cannot see: the step is perfect
        and the render still carries the placeholder."""
        findings = run([queued(body="<p>{BODY_1}</p>")])
        self.assertEqual([("body", "FAIL")], verdicts(findings))

    def test_a_body_that_resolved_empty_fails(self):
        findings = run([queued(body="<p></p>")])
        self.assertEqual([("body", "FAIL")], verdicts(findings))

    def test_a_changed_subject_fails(self):
        findings = run([queued(subject="something else entirely")])
        self.assertEqual([("subject", "FAIL")], verdicts(findings))

    def test_the_providers_Re_on_a_followup_is_not_a_subject_change(self):
        """Step 1 owns the only subject and the provider prefixes the rest.
        Reporting that every run would train an operator to ignore it."""
        self.assertEqual([("row", "PASS")],
                         verdicts(run([queued(subject="Re: " + SUBJECT)])))

    def test_an_entity_in_the_SUBJECT_fails_because_a_header_is_not_html(self):
        """Unlike the body. A prospect would read `&amp;` in their inbox
        list, so this must not be absorbed the way the body's is."""
        findings = run([queued(subject="a &amp; b")],
                       snapshot=[record(subject="a & b")])
        self.assertEqual([("subject", "FAIL")], verdicts(findings))

    def test_a_lead_no_canonical_record_holds_fails(self):
        findings = run([queued(email="stranger@elsewhere.test")])
        self.assertEqual([("lead", "FAIL")], verdicts(findings))

    def test_a_step_id_this_campaign_does_not_have_fails(self):
        findings = run([queued(step_id=9999)])
        self.assertEqual([("step", "FAIL")], verdicts(findings))

    def test_a_step_count_mismatch_refuses_to_pair_rather_than_guessing(self):
        findings = run([queued()], steps=[{"id": 4742}, {"id": 4743}])
        self.assertEqual([("steps", "FAIL")], verdicts(findings))

    def test_an_empty_queue_is_reported_as_empty_not_as_passing(self):
        """Nothing queued is not the same answer as everything correct, and a
        gate that returned PASS here would wave through a campaign it had not
        checked."""
        self.assertEqual([("queue", "EMPTY")], verdicts(run([])))

    def test_a_provider_id_no_canonical_campaign_claims_fails(self):
        findings = run([queued()], canonical=[])
        self.assertEqual([("campaign", "FAIL")], verdicts(findings))

    def test_one_bad_row_does_not_stop_the_others_being_checked(self):
        """A bad record is HELD with a reason while unrelated records
        continue - the standing invariant, here at row level."""
        rows = [queued(email="stranger@elsewhere.test"), queued()]
        self.assertEqual([("lead", "FAIL"), ("row", "PASS")],
                         verdicts(run(rows)))


if __name__ == "__main__":
    unittest.main()
