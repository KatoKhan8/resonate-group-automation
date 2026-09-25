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
           #
           # THE PAIR HAS TO BE THE CLIENT'S CURRENT ONE, and this is the
           # second time that has moved. This record names client
           # `productive`, and `lint` asks the CLIENT's policy rather than
           # the default - so a pair the client no longer requires is not a
           # verified address here, and the step is refused at
           # `recipient_not_sendable` before the opener this test exists to
           # check is ever read.
           #
           #   2026-09-21  primary Deliverable, secondary Reoon. The
           #               (contactout, reoon) fixture stopped clearing.
           #   2026-09-25  primary CheapVerifier, secondary Deliverable,
           #               Reoon the third opinion. (deliverable, reoon)
           #               stopped clearing, for the same reason.
           #
           # `(cheapverifier, deliverable)` is the pair the client's policy
           # names first, and `verification.pair_accepted` agrees with it.
           # Unlike the cadence and role pins elsewhere in the suite this
           # fixture is written out by hand and reaches lint through the
           # record's own client, so it is updated rather than pinned.
           "verification": {"evidence": [
               {"provider": "cheapverifier", "status": "valid",
                "email": "ada@acmestudio.example", "catch_all": False,
                "disposable": False, "at": "2026-09-09T00:00:00+00:00"},
               {"provider": "deliverable", "status": "valid",
                "email": "ada@acmestudio.example", "catch_all": False,
                "disposable": False, "at": "2026-09-09T00:00:00+00:00"}]},
           "mx": {"status": "known_allowed", "email_eligible": True}}
    row.update(over)
    return row


class TheOpenerClaimsNothingAboutThem(unittest.TestCase):
    def setUp(self):
        # A CACHE NOTHING INVALIDATES, and it made this test order-dependent.
        #
        # `lint.policy_for_record` memoises the client's verification policy
        # in a module-level `_POLICY_CACHE`, and `lint.forget_policies` was
        # written to clear it - its docstring says "for tests that rewrite a
        # client config mid-run". Measured 2026-09-25: **nothing in src/ or
        # tests/ called it.**
        #
        # So the first test in the process to lint a `productive` record
        # decides the policy for every test after it. Dozens of them run
        # under `pin_client_config`, which pins the verification roles to
        # what the FIXTURE estates carry - so in a full run this test read a
        # pinned policy, and its fixture, which is written against the
        # client's REAL current pair, was refused. Alone it passed; in a
        # batch it failed; and which it did depended on module ordering.
        #
        # That is the shape of an intermittent failure this repository's own
        # rules say to diagnose rather than dismiss. Clearing the cache here
        # is the mechanism that was built for it finally having a caller.
        lint.forget_policies()
        self.addCleanup(lint.forget_policies)
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

    def test_every_record_that_now_has_evidence_still_renders_safely(self):
        """This branch has started firing, and that is the point of it.

        It used to assert that NO record carried `evidence`, which anchored
        why the fallback was the only text anybody had ever received:
        `generate.persona_angle` is the only writer, it needs a real model,
        and the repository shipped only `NoModel` and `ScriptedModel`.

        A real model is configured now, so the preferred branch fires and
        records carry evidence. Asserting the key is absent would be asserting
        the feature does not work.

        What still matters is what this file is about - that the opener
        asserts nothing about how somebody runs their company - so that is
        what is checked, against the real rows rather than a fixture. A
        sentence written by a model is exactly where an unfounded claim would
        appear.
        """
        import json
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "work", "queue.jsonl")
        if not os.path.exists(path):
            self.skipTest("no live queue on this machine")
        with open(path, encoding="utf-8") as handle:
            rows = [json.loads(l) for l in handle if l.strip()]
        carrying = [r for r in rows if r.get("evidence")]
        if not carrying:
            self.skipTest("no record carries evidence yet")
        for rec in carrying:
            for contact_key, lines in (rec.get("evidence") or {}).items():
                for line in lines or []:
                    for phrase in ASSERTIONS:
                        self.assertNotIn(
                            phrase, str(line).lower(),
                            f"{rec.get('id')}/{contact_key} asserts: {line!r}")


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
