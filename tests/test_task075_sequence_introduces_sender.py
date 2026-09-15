"""TASK-075: the sequence must introduce its sender and go somewhere.

Two defects measured by TASK-064's human read of all 15 contacts:

  1. The connection note never said who is writing. The ladder's first rung
     must require sender identity, and the prompt must pass it.

  2. The sequence did not progress. Each rung must say what the PREVIOUS rung
     established so the next one can build on it.

Plus the claim rule extension: "as a fellow founder" is an assertion about
the sender that may be false, and the unsupported-claim gate must catch it.

These tests assert on behaviour - what functions return and what the prompt
carries - not on source text. The ladder is resolved through
`generate.purpose_for`, which is the path production uses.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import cadencelibrary, claims, clients, generate


class LadderRungsReferenceThePrevious(unittest.TestCase):
    """Each LinkedIn rung says what the previous one established.

    The defect was that all six rungs collapsed into one: ask about
    profitability. The fix is in the brief: each rung references what the
    previous rung already said, so a model that satisfies rung 3 by repeating
    rung 2's angle is failing the brief, not meeting it.
    """

    def _purposes(self):
        seq = cadencelibrary.named("productive_li_heavy_v1")
        return [generate.purpose_for("linkedin", n, sequence=seq)
                for n in range(1, 7)]

    def test_rung_one_requires_sender_identity(self):
        """The connection note must say who is writing."""
        p = self._purposes()[0]
        self.assertIn("who you are", p.lower(),
                       "rung 1 does not require sender identity")

    def test_rung_two_references_the_connection_note(self):
        """Rung 2 must reference what rung 1 established."""
        p = self._purposes()[1]
        self.assertIn("connection note", p.lower(),
                       "rung 2 does not reference the connection note")

    def test_rung_three_references_both_previous_steps(self):
        """Rung 3 must not repeat rung 1 or rung 2's angle."""
        p = self._purposes()[2]
        low = p.lower()
        self.assertIn("different", low,
                       "rung 3 does not require a different angle")

    def test_rung_four_references_previous_questions(self):
        """Rung 4 says the previous messages asked questions and told nothing."""
        p = self._purposes()[3]
        low = p.lower()
        self.assertIn("previous", low,
                       "rung 4 does not reference previous messages")

    def test_rung_five_references_the_sequence_so_far(self):
        """Rung 5 must not repeat what the sequence already said."""
        p = self._purposes()[4]
        low = p.lower()
        self.assertIn("previous", low,
                       "rung 5 does not reference previous steps")

    def test_rung_six_is_the_close(self):
        """Rung 6 closes the loop with no new pitch."""
        p = self._purposes()[5]
        low = p.lower()
        self.assertIn("close", low,
                       "rung 6 is not the close")

    def test_rung_six_requires_a_graceful_exit(self):
        """Rung 6 must give the prospect a graceful way to decline.

        TASK-131: 58 of 69 sequences lacked an easy out. The fallback's
        connected_4 says "happy to leave it here if the timing is wrong".
        The brief must state this job.
        """
        p = self._purposes()[5]
        low = p.lower()
        self.assertIn("graceful", low,
                       "rung 6 does not require a graceful exit")

    def test_rung_six_requires_a_referral_ask(self):
        """Rung 6 must ask whether somebody else owns this.

        TASK-131: the fallback's connected_4 asks "is there someone else
        who owns this?" The brief must state this job.
        """
        p = self._purposes()[5]
        low = p.lower()
        self.assertIn("somebody else", low,
                       "rung 6 does not require a referral ask")

    def test_rungs_two_through_six_forbid_reintroduction(self):
        """Rungs 2-6 must not re-introduce the sender.

        TASK-131: every LinkedIn message opened "hi [name], ivan here/from
        Productive". The sender was identified at rung 1; rungs 2-6 must
        not repeat it.
        """
        purposes = self._purposes()
        for i in range(1, 6):
            low = purposes[i].lower()
            self.assertIn("re-introduce", low,
                          f"rung {i+1} does not forbid re-introducing sender")

    def test_all_six_rungs_are_distinct(self):
        """No two rungs have the same text."""
        purposes = self._purposes()
        self.assertEqual(len(set(purposes)), 6,
                         "two rungs have identical briefs")

    def test_the_ladder_is_the_registry_entry(self):
        """The resolved ladder IS the registry entry, not a copy."""
        self.assertIs(generate.LINKEDIN_LADDER,
                      cadencelibrary.LADDER_REGISTRY["linkedin_default"])


class SenderIdentityReachesThePrompt(unittest.TestCase):
    """The connection note prompt must carry who is writing.

    The chain: client config -> clients.sender_identity ->
    generate.context_for -> rendered prompt. Each link is asserted
    separately because a block assembled and not rendered is the shape
    of defect this repository keeps finding.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)
        self._orig = os.environ.get("CLIENTS_DIR")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmpdir, "clients")
        os.makedirs(os.environ["CLIENTS_DIR"], exist_ok=True)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("CLIENTS_DIR", None)
        else:
            os.environ["CLIENTS_DIR"] = self._orig

    def _write_config(self, sender_block=""):
        path = os.path.join(os.environ["CLIENTS_DIR"], "testclient.yaml")
        with open(path, "w") as f:
            f.write(f"name: TestCo\ndomain: test.test\n"
                    f"sender:\n{sender_block}\n"
                    f"cadence: productive_li_heavy_v1\n")
        return clients.load("testclient")

    def test_sender_identity_reads_the_config(self):
        config = self._write_config(
            "  mode: client_rep\n"
            "  name: Ivan\n"
            "  role: founder\n"
            "  company: Productive\n"
            "  works_on: project profitability for agencies\n")
        identity = clients.sender_identity(config)
        self.assertEqual(identity["name"], "Ivan")
        self.assertEqual(identity["role"], "founder")
        self.assertEqual(identity["company"], "Productive")
        self.assertEqual(identity["works_on"],
                         "project profitability for agencies")

    def test_sender_identity_returns_empty_for_no_sender_block(self):
        config = self._write_config("  mode: client_rep\n")
        identity = clients.sender_identity(config)
        self.assertEqual(identity, {})

    def test_sender_identity_skips_empty_fields(self):
        config = self._write_config(
            "  mode: client_rep\n"
            "  works_on: project profitability\n")
        identity = clients.sender_identity(config)
        self.assertEqual(identity, {"works_on": "project profitability"})
        self.assertNotIn("name", identity)

    def test_context_for_passes_sender_identity_to_linkedin_note(self):
        """The chain: config -> context_for -> prompt context."""
        config = self._write_config(
            "  mode: client_rep\n"
            "  name: Ivan\n"
            "  role: founder\n"
            "  works_on: project profitability\n")
        rec = {"id": "test", "client": "testclient",
               "company": "Acme", "domain": "acme.test",
               "state": "qualified", "lane": "domains",
               "contacts": [{"key": "ck-1", "name": "Jane Doe",
                             "title": "COO", "persona": "champion",
                             "angle": "operations",
                             "linkedin": "https://linkedin.com/in/jane"}],
               "company_facts": {"name": "Acme", "industry": "marketing"},
               "events": []}
        contact = rec["contacts"][0]
        ctx = generate.context_for("linkedin_note", rec, contact, config,
                                   step_key="li1")
        self.assertIn("sender_identity", ctx)
        self.assertEqual(ctx["sender_identity"]["name"], "Ivan")
        self.assertEqual(ctx["sender_identity"]["works_on"],
                         "project profitability")

    def test_context_for_passes_empty_sender_when_absent(self):
        """An empty sender block reaches the prompt as {}, not None."""
        config = self._write_config("  mode: client_rep\n")
        rec = {"id": "test", "client": "testclient",
               "company": "Acme", "domain": "acme.test",
               "state": "qualified", "lane": "domains",
               "contacts": [{"key": "ck-1", "name": "Jane Doe",
                             "title": "COO", "persona": "champion",
                             "angle": "operations",
                             "linkedin": "https://linkedin.com/in/jane"}],
               "company_facts": {"name": "Acme"},
               "events": []}
        contact = rec["contacts"][0]
        ctx = generate.context_for("linkedin_note", rec, contact, config,
                                   step_key="li1")
        self.assertIn("sender_identity", ctx)
        self.assertEqual(ctx["sender_identity"], {})

    def test_sender_identity_reaches_the_rendered_prompt(self):
        """The full chain: config -> context_for -> rendered prompt text."""
        config = self._write_config(
            "  mode: client_rep\n"
            "  name: Ivan\n"
            "  role: founder\n"
            "  works_on: project profitability\n")
        rec = {"id": "test", "client": "testclient",
               "company": "Acme", "domain": "acme.test",
               "state": "qualified", "lane": "domains",
               "contacts": [{"key": "ck-1", "name": "Jane Doe",
                             "title": "COO", "persona": "champion",
                             "angle": "operations",
                             "linkedin": "https://linkedin.com/in/jane"}],
               "company_facts": {"name": "Acme", "industry": "marketing"},
               "events": []}
        contact = rec["contacts"][0]
        rendered = generate.render_prompt("linkedin_note", rec, contact,
                                          config, step_key="li1")
        self.assertIn("Ivan", rendered)
        self.assertIn("project profitability", rendered)


class TheClaimRuleCoversSenderIdentity(unittest.TestCase):
    """The fourth phrase the rule was short of.

    `portsidemarketing-com` carried "as a fellow founder" - an assertion
    about the SENDER that may be false. The gate watched claims about the
    PROSPECT and this one pointed the other way.

    These tests assert on `implies_prior_contact` - the function that
    decides whether a sentence asserts something about a relationship
    the record must support. "as a fellow founder" asserts the sender
    shares a category with the recipient, which is a claim.
    """

    def test_as_a_fellow_founder_is_caught(self):
        """The exact phrase from portsidemarketing-com."""
        found = claims.implies_prior_contact(
            "as a fellow founder i thought it would be good to connect")
        self.assertIsNotNone(found)

    def test_as_a_fellow_any_noun_is_caught(self):
        for noun in ("founder", "operator", "agency owner", "marketer"):
            with self.subTest(noun=noun):
                found = claims.implies_prior_contact(
                    f"as a fellow {noun} i wanted to reach out")
                self.assertIsNotNone(found,
                                     f"'as a fellow {noun}' was not caught")

    def test_as_someone_who_runs_is_caught(self):
        found = claims.implies_prior_contact(
            "as someone who also runs an agency i understand the challenge")
        self.assertIsNotNone(found)

    def test_as_someone_who_owns_is_caught(self):
        found = claims.implies_prior_contact(
            "as someone who owns a studio i know how it works")
        self.assertIsNotNone(found)

    def test_speaking_as_a_fellow_is_caught(self):
        found = claims.implies_prior_contact(
            "speaking as a fellow founder i wanted to connect")
        self.assertIsNotNone(found)

    def test_neutral_copy_is_not_caught(self):
        """Honest copy that does not assert a shared identity."""
        for sentence in (
            "most agencies we work with track time in spreadsheets",
            "i work with agencies on project profitability",
            "our platform connects budgets and time tracking",
            "we built productive so budgets and resourcing talk to each other",
            "curious how you handle resourcing at your size",
        ):
            with self.subTest(sentence=sentence):
                self.assertIsNone(claims.implies_prior_contact(sentence),
                                  f"honest copy was refused: {sentence!r}")

    def test_the_full_claims_check_refuses_unsupported_sender_claim(self):
        """End-to-end: `claims.check` refuses 'as a fellow founder'
        on a record with no supporting evidence."""
        rec = {"id": "test", "company": "Acme", "domain": "acme.test",
               "contacts": [{"key": "ck-1", "name": "Jane",
                             "title": "Founder"}],
               "company_facts": {"name": "Acme"},
               "events": [], "research": []}
        contact = rec["contacts"][0]
        problems = claims.check(
            "as a fellow founder i thought it would be good to connect",
            rec, contact)
        self.assertTrue(problems,
                        "'as a fellow founder' passed the claims check")


class TheEmailLadderIsUnchanged(unittest.TestCase):
    """The email ladder was NOT part of this task. Guard against drift."""

    def test_email_five_ladder_rung_one_is_unchanged(self):
        self.assertTrue(
            cadencelibrary.EMAIL_FIVE_LADDER[0].startswith(
                "Relevance, and who is writing"))

    def test_email_five_ladder_rung_five_is_unchanged(self):
        self.assertEqual(
            cadencelibrary.EMAIL_FIVE_LADDER[4],
            "Close the loop. Give them an easy no, make no new pitch, ask "
            "for nothing beyond permission to stop.")


if __name__ == "__main__":
    unittest.main()
