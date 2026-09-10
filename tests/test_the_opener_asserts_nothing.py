"""The day-5 opener claimed to know how somebody ran their agency.

`persona_pain` opens with `{line}`, and `{line}` had two branches. The
preferred one reads `rec["evidence"][contact_key]`, which is written only by
`generate.persona_angle` - which needs a model, and `src/llm.py` ships only
`NoModel` and `ScriptedModel`. So that branch has never fired on any record,
and the fallback was the only text anybody would ever have received:

    "you are running utilisation at Ninefields"

That is a factual claim about how a company runs, assembled from OUR angle
wording and THEIR company name, with nothing on the record behind it.

Two things hid it. `claims.is_claim` examines a sentence only when it carries a
number, a month word or an event word, and "running" is none of those - so the
claim checker never looked at the one sentence that needed looking at. And
`lint` has no rule about asserting, because until now nothing asserted.

The replacement is the shape the LinkedIn note already uses honestly: who we
work with, and a question. Every value in it - the sector and the company name
- is on the record.
"""
import os
import sys
import unittest

from src import cadence, claims, clients, lint

CONFIG = clients.load("productive")
DAY5 = {"key": "day5", "day": 5, "channel": "email", "template": "persona_pain"}

# Phrasings that assert something about the recipient. A rendered opener that
# has no evidence behind it may not contain one.
ASSERTIONS = ("you are running", "you run ", "you have ", "your team is",
              "you currently", "we noticed", "i noticed", "i saw that you")


def record(**over):
    rec = {"id": "rec-1", "lane": "domains", "client": "productive",
           "company": "Acme Studio", "domain": "acmestudio.example",
           "state": "queued", "company_facts": {"industry": "Design Services"},
           "contacts": [], "excluded": []}
    rec.update(over)
    return rec


def contact(angle="operations", **over):
    row = {"key": "c1", "name": "Ada Lovelace", "title": "Head of Production",
           "email": "ada@acmestudio.example", "linkedin": "ada-lovelace",
           "persona": "champion", "angle": angle,
           # Sendable, or lint refuses the step before it reads a word of
           # it. `is_sendable` recomputes from the evidence and ignores the
           # stored state, so the evidence is what the fixture has to carry.
           "verification": {"evidence": [
               {"provider": "contactout", "status": "valid",
                "email": "ada@acmestudio.example", "catch_all": False,
                "disposable": False, "at": "2026-09-09T00:00:00+00:00"},
               {"provider": "reoon", "status": "valid",
                "email": "ada@acmestudio.example", "catch_all": False,
                "disposable": False, "safe_to_send": True,
                "at": "2026-09-09T00:00:00+00:00"}]},
           "mx": {"status": "known_allowed", "email_eligible": True}}
    row.update(over)
    return row


class TheOpenerClaimsNothingAboutThem(unittest.TestCase):
    def setUp(self):
        self.c = contact()
        self.rec = record(contacts=[self.c])

    def opener(self, rec=None, c=None):
        step = cadence.expand_step(rec or self.rec, c or self.c, DAY5, CONFIG)
        return step["body"].split("\n")[0].lower()

    def test_it_does_not_assert_what_they_are_doing(self):
        line = self.opener()
        for phrase in ASSERTIONS:
            self.assertNotIn(phrase, line, f"the opener asserts: {line!r}")

    def test_every_angle_produces_a_non_asserting_opener(self):
        """The old text was built from the angle phrase, so every angle had it."""
        for angle in clients.angles_for(CONFIG, "champion"):
            with self.subTest(angle=angle):
                line = self.opener(c=contact(angle=angle))
                for phrase in ASSERTIONS:
                    self.assertNotIn(phrase, line, f"{angle}: {line!r}")

    def test_it_still_names_the_company_and_the_sector(self):
        """Non-asserting must not mean generic: both are on the record."""
        line = self.opener()
        self.assertIn("acme studio", line)
        self.assertIn("design services", line)

    def test_a_record_with_no_industry_still_renders(self):
        rec = record(company_facts={}, contacts=[self.c])
        line = self.opener(rec=rec)
        self.assertTrue(line.strip())
        for phrase in ASSERTIONS:
            self.assertNotIn(phrase, line)

    def test_the_step_passes_lint_and_claims(self):
        step = cadence.expand_step(self.rec, self.c, DAY5, CONFIG)
        self.assertEqual(sorted(lint.check_step(self.rec, "c1", step)), [])
        found = claims.check(step["body"], self.rec, self.c)
        problems = found.get("problems") if isinstance(found, dict) else found
        self.assertFalse(problems)


class StoredEvidenceStillWins(unittest.TestCase):
    """The preferred branch is kept. It has simply never had anything to read."""

    def test_evidence_on_the_record_is_used_verbatim(self):
        c = contact()
        rec = record(contacts=[c],
                     evidence={"c1": ["you told us resourcing is the problem"]})
        step = cadence.expand_step(rec, c, DAY5, CONFIG)
        self.assertIn("you told us resourcing is the problem", step["body"])

    def test_no_record_in_the_live_queue_has_that_key(self):
        """Anchors why the fallback is the only text that has ever shipped."""
        import json
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "work", "queue.jsonl")
        if not os.path.exists(path):
            self.skipTest("no live queue on this machine")
        with open(path, encoding="utf-8") as handle:
            rows = [json.loads(l) for l in handle if l.strip()]
        self.assertEqual([r["id"] for r in rows if r.get("evidence")], [])


class TheClaimCheckerCanNowSeeThisClass(unittest.TestCase):
    """CLOSED 2026-09-10. This class used to assert the opposite.

    It recorded a gap: `is_claim` gated on a number, a month or an event
    word, so an asserting sentence with none of those was never examined -
    and the sentence that actually went out to a real person had none of
    them. The old test ended "if this now fails, claims got stricter -
    update this test, it is a record of a gap". It did, and this is that
    update.

    `claims.asserts_about_them` now catches a second-person operational
    assertion, and holds it to the strict standard: the operational term it
    leans on must appear in what the record actually knows.
    """

    def test_an_asserting_sentence_without_a_number_is_now_caught(self):
        rec = record(contacts=[contact()])
        found = claims.check("You are running utilisation at Acme Studio",
                            rec, contact())
        problems = found.get("problems") if isinstance(found, dict) else found
        self.assertTrue(problems,
                        "the sentence that went out is unexamined again")

    def test_a_non_asserting_opener_is_still_allowed(self):
        """The direction that keeps the fix usable. The replacement copy says
        what WE do and asks a question; if this ever fails, the guard has
        started refusing the very sentence it was written to permit."""
        rec = record(contacts=[contact()])
        found = claims.check(
            "i work with Design Services teams on utilisation. curious how "
            "Acme Studio handles it at your size.", rec, contact())
        problems = found.get("problems") if isinstance(found, dict) else found
        self.assertFalse(problems, problems)


if __name__ == "__main__":
    unittest.main()
