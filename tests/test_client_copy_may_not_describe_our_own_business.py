"""GATE 2, against the copy that actually shipped out of a client's mailboxes.

On 2026-09-25, 690 leads were staged on EmailBison campaigns 503, 504 and
505 with copy assembled as string literals in a scratch script. 64 of them
were sent. The copy described Resonate's business, out of Productive's
mailboxes, signed with the operator's name, from 41 inboxes belonging to 6
real people.

Each of the three questions gate 2 asks has its own fixture here, built so
that it fails THAT question and passes the other two - because a test whose
fixture fails everything proves only that something refused it.
"""
import unittest

from src import clients, copyprovenance as cp

#: The client's cadence, named the way `productive.yaml` names it. A dict
#: rather than `clients.load`, so a client editing their own file cannot
#: turn this test red - `TheRealClientFileAuthorisesSomething` below is
#: where the live file is checked, and it is checked for being non-empty
#: rather than for its contents.
CONFIG = {"cadence": "productive_li_heavy_v1", "name": "productive"}
GOOD_ID = "productive:productive_li_heavy_v1:em1"

#: THE BODY THAT SHIPPED. EmailBison campaign 503, step 1, as the provider
#: holds it - the company name replaced, nothing else touched.
SHIPPED = (
    "Hi Rhett, I was reading the Northwind site this week and the line "
    "about please allow me to introduce myself, the agency and our mission "
    "is what made me write.\n\n"
    "I work with agency founders who want a second source of new business "
    "that does not depend on referrals arriving on time.\n\n"
    "We run the outbound side end to end, so the pipeline keeps moving "
    "while the team stays on client work.\n\n"
    "Worth a short call next week?\n\nZvonimir")

#: Copy that is about the CLIENT'S product and signed by nobody, which is
#: what `sender.mode: client_rep` in `productive.yaml` asks for: the engine
#: writes no signature and the sending mailbox appends its own.
CLEAN = (
    "Scott, your site says margin is known at the end of the month.\n\n"
    "The pattern in teams your size is that the numbers arrive too late to "
    "act on. Utilisation and margin are known after the month when "
    "something could have been done about them.\n\n"
    "Is that roughly how it works at your end today?")


class TheCopyThatShipped(unittest.TestCase):

    def test_it_is_refused_and_every_reason_is_named(self):
        verdict = cp.check_step(SHIPPED, template_id=None,
                                owner_name="Dana Whitfield",
                                approved_ids=cp.template_ids(CONFIG, "productive"))
        self.assertFalse(verdict["ok"])
        why = " ".join(verdict["reasons"])
        self.assertIn("no template id", why)
        self.assertIn("refused term", why)
        self.assertIn("mailbox belongs to", why)

    def test_every_word_on_the_operators_list_is_found(self):
        hits = cp.refused_terms_in(SHIPPED)
        for term in ("outbound", "agency founders", "i work with", "we run",
                     "pipeline", "zvonimir"):
            self.assertIn(term, hits)

    def test_the_signature_is_read_out_of_the_providers_html(self):
        # The provider stores `<p>...<br><br>Zvonimir</p>`. A naive tag
        # strip runs the signature onto the last sentence and finds none.
        held = ("<p>Following up on the note below.<br><br>Happy to send it "
                "over rather than book a call.<br><br>Zvonimir</p>")
        self.assertEqual(cp.signature_of(held), "Zvonimir")


class OneQuestionAtATime(unittest.TestCase):
    """Three fixtures, each failing exactly one of the three questions."""

    def setUp(self):
        self.approved = cp.template_ids(CONFIG, "productive")

    def _check(self, body, template_id=GOOD_ID, owner="Owen Marsh"):
        return cp.check_step(body, template_id=template_id, owner_name=owner,
                             approved_ids=self.approved)

    def test_the_clean_fixture_passes_so_the_others_mean_something(self):
        verdict = self._check(CLEAN)
        self.assertTrue(verdict["ok"], verdict["reasons"])

    def test_only_the_template_id_is_wrong(self):
        verdict = self._check(CLEAN, template_id="gencopy-v1")
        self.assertFalse(verdict["ok"])
        self.assertEqual(len(verdict["reasons"]), 1)
        self.assertIn("is not one the client's copy file declares",
                      verdict["reasons"][0])

    def test_only_the_product_is_wrong(self):
        body = CLEAN + "\n\nI work with agency founders on this."
        verdict = self._check(body)
        self.assertFalse(verdict["ok"])
        self.assertEqual(len(verdict["reasons"]), 1)
        self.assertIn("refused term", verdict["reasons"][0])

    def test_only_the_signature_is_wrong(self):
        verdict = self._check(CLEAN + "\n\nDana Whitfield",
                              owner="Owen Marsh")
        self.assertFalse(verdict["ok"])
        self.assertEqual(len(verdict["reasons"]), 1)
        self.assertIn("mailbox belongs to", verdict["reasons"][0])

    def test_a_signature_matching_its_own_mailbox_passes(self):
        verdict = self._check(CLEAN + "\n\nOwen Marsh",
                              owner="Owen Marsh")
        self.assertTrue(verdict["ok"], verdict["reasons"])

    def test_a_signature_with_no_known_owner_is_refused(self):
        # An unbound lead is where a constant signature is least visible,
        # so it fails closed rather than being excused for lacking a
        # comparison.
        verdict = self._check(CLEAN + "\n\nZvonimir", owner="")
        self.assertFalse(verdict["ok"])
        self.assertIn("mailbox owner is not known",
                      " ".join(verdict["reasons"]))


class AbsenceIsNotAPass(unittest.TestCase):
    """Lane S: a gate asking whether a field is non-empty passed 12,407 of
    12,407 rows because the supplier had filled the field before anybody
    looked. This asks where the value CAME FROM."""

    def test_no_template_id_at_all_is_a_refusal(self):
        verdict = cp.check_step(CLEAN, template_id=None,
                                owner_name="Owen Marsh",
                                approved_ids=cp.template_ids(CONFIG, "productive"))
        self.assertFalse(verdict["ok"])
        self.assertIn("no template id", " ".join(verdict["reasons"]))

    def test_a_plausible_template_id_is_not_a_provenance(self):
        # Non-empty, well-formed, and invented. This is the exact shape the
        # scratch script would have produced if asked for one.
        verdict = cp.check_step(CLEAN, template_id="productive:cold:step1",
                                owner_name="Owen Marsh",
                                approved_ids=cp.template_ids(CONFIG, "productive"))
        self.assertFalse(verdict["ok"])

    def test_an_empty_approved_set_refuses_everything(self):
        # A config that names no cadence authorises NOTHING. The dangerous
        # reading is the other one: an empty set that lets every id through
        # because there is nothing to compare against.
        self.assertEqual(cp.template_ids({}, "productive"), frozenset())
        verdict = cp.check_step(CLEAN, template_id=GOOD_ID,
                                owner_name="Owen Marsh",
                                approved_ids=cp.template_ids({}, "productive"))
        self.assertFalse(verdict["ok"])

    def test_a_lead_with_no_copy_variables_is_refused(self):
        report = cp.check_lead({}, owner_name="Owen Marsh", config=CONFIG,
                               client="productive")
        self.assertFalse(report["ok"])
        self.assertIn("no copy variables", " ".join(report["reasons"]))

    def test_an_unresolved_merge_field_is_refused_not_read_as_a_name(self):
        # Campaign 491 renders `<p>{BODY_3}</p>` for 94 of its 333 leads.
        # The last line of that is one capitalised token with no terminal
        # punctuation - the shape of a signature - and the audit reported
        # `{BODY_3}` as a person signing emails until this was added.
        self.assertIsNone(cp.signature_of("<p>{BODY_3}</p>"))
        verdict = cp.check_step("<p>{BODY_3}</p>", template_id=GOOD_ID,
                                owner_name="Owen Marsh",
                                approved_ids=cp.template_ids(CONFIG, "productive"))
        self.assertFalse(verdict["ok"])
        self.assertIn("unresolved merge field", " ".join(verdict["reasons"]))


class OneNameOutOfManyMailboxes(unittest.TestCase):
    """The batch property. 41 mailboxes, 6 people, one literal."""

    def test_a_signature_spanning_two_owners_is_reported(self):
        constants = cp.constant_signatures([
            ("Zvonimir", "Dana Whitfield"),
            ("Zvonimir", "Owen Marsh"),
            ("Zvonimir", "Paul Ridley"),
        ])
        self.assertEqual(sorted(constants), ["zvonimir"])
        self.assertEqual(len(constants["zvonimir"]), 3)

    def test_each_owner_signing_their_own_name_is_not_a_constant(self):
        self.assertEqual(cp.constant_signatures([
            ("Dana Whitfield", "Dana Whitfield"),
            ("Owen Marsh", "Owen Marsh"),
        ]), {})


class TheCertificateCoversTheWords(unittest.TestCase):

    def test_certify_then_verify(self):
        steps = [(1, GOOD_ID, "a subject", CLEAN)]
        values = cp.certify(steps, client="productive",
                            owner_name="Owen Marsh", config=CONFIG)
        held = dict(values, subject_1="a subject", body_1=CLEAN)
        ok, why = cp.verify_certificate(held, client="productive")
        self.assertTrue(ok, why)

    def test_a_word_changed_after_certification_fails(self):
        steps = [(1, GOOD_ID, "a subject", CLEAN)]
        values = cp.certify(steps, client="productive",
                            owner_name="Owen Marsh", config=CONFIG)
        held = dict(values, subject_1="a subject", body_1=CLEAN + " Zvonimir")
        ok, why = cp.verify_certificate(held, client="productive")
        self.assertFalse(ok)
        self.assertIn("the words changed after they were certified", why)

    def test_a_certificate_for_another_client_does_not_travel(self):
        steps = [(1, GOOD_ID, "a subject", CLEAN)]
        values = cp.certify(steps, client="productive",
                            owner_name="Owen Marsh", config=CONFIG)
        held = dict(values, subject_1="a subject", body_1=CLEAN)
        ok, why = cp.verify_certificate(held, client="contactout")
        self.assertFalse(ok)
        self.assertIn("minted for", why)

    def test_the_shipped_copy_cannot_be_certified_at_all(self):
        with self.assertRaises(cp.CopyRefused) as caught:
            cp.certify([(1, GOOD_ID, "quick question", SHIPPED)],
                       client="productive", owner_name="Dana Whitfield",
                       config=CONFIG)
        self.assertIn("refused term", str(caught.exception))


class TheLintThatRanAndPassedIt(unittest.TestCase):
    """`work/gencopy.py` imported copylint, called `check_batch` per lead,
    DROPPED any draft it refused, and printed the batch report. It ran on
    all 690 and refused none of them.

    So the claim these gates rest on is not "the lint was not called". It
    is that the lint answers different questions, and this asserts the
    difference directly rather than asserting copylint is bad - which
    would go red the day somebody improves it.
    """

    def _lead(self):
        # The shape gencopy handed to check_batch, with the pack fact that
        # the opener quotes - a real navigation bar, which is why rule 1
        # passed.
        opener = ("Hi Rhett, I was reading the Northwind site this week and "
                  "the line about check out a few of our case studies is "
                  "what made me write.")
        return {
            "id": "northwind.test",
            "steps": [{"body": opener + "\n\n" + SHIPPED.split("\n\n", 1)[1]},
                      {"body": "Following up on the note below.\n\nZvonimir"},
                      {"body": "One more thought.\n\nZvonimir"},
                      {"body": "Keeping this one short.\n\nZvonimir"},
                      {"body": "Closing the loop.\n\nZvonimir"}],
        }, {"northwind.test": {"facts": [
            {"fact_id": "aaaa1111", "source_url": "https://northwind.test/",
             "snippet": "Home About Services check out a few of our case "
                        "studies Contact us"}]}}

    def test_rule_one_is_satisfied_by_a_navigation_bar(self):
        from src import copylint
        lead, packs = self._lead()
        report = copylint.check_batch([lead], packs, steps_expected=5)
        self.assertEqual(report["counts"]["step1_without_pack_fact"], 0,
                         "the opener quotes a menu and rule 1 counts it as "
                         "grounded - which is what happened")

    def test_gate_two_refuses_what_that_lint_let_through(self):
        report = cp.check_lead(
            {"subject_1": "quick question", "body_1": self._lead()[0]["steps"][0]["body"]},
            owner_name="Dana Whitfield", config=CONFIG, client="productive")
        self.assertFalse(report["ok"])
        why = " ".join(r for s in report["steps"] for r in s["reasons"])
        self.assertIn("refused term", why)

    def test_gate_three_refuses_the_span_that_lint_called_grounded(self):
        from src import packfact
        _lead, packs = self._lead()
        fact = packs["northwind.test"]["facts"][0]
        verdict = packfact.check_span("check out a few of our case studies",
                                      fact)
        self.assertFalse(verdict["ok"])
        self.assertEqual(packfact.quotable(fact), [],
                         "nothing in this pack is quotable, so the lead is "
                         "HELD rather than sent generic")


class TheRealClientFileAuthorisesSomething(unittest.TestCase):
    """Existence is not function: a set derived from a file nobody reads is
    an empty set that refuses everything and looks strict."""

    def test_productive_yaml_declares_template_ids(self):
        ids = cp.template_ids(clients.load("productive"), "productive")
        self.assertTrue(ids, "the client's own copy file authorises nothing")
        self.assertTrue(any(i.endswith(":em1") for i in ids),
                        "the email opener is not in the authorised set")


if __name__ == "__main__":
    unittest.main()
