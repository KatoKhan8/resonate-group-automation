#!/usr/bin/env python3
"""A HeyReach sequence is campaign-level, so it may say nothing about one lead.

THE INCIDENT THIS PINS, and it was caught one call before it happened.

`heyreachfactory._plan` built the campaign graph like this:

    complete = [c for c in per_contact if not c["missing"]]
    copy_block = complete[0]["copy"]          # the FIRST eligible contact
    sequence, touch_report = build_sequence(copy_block, ...)

One contact's approved, personalised words became the whole campaign's copy,
as literal strings with no merge fields. Read back from HeyReach campaign
599020 on 2026-09-14, whose canonical row names FOURTEEN records:

    CONNECTION_REQUEST  "hi jacob, as a founder, you know the importance of
                         having profitability visible on monday. let's connect!"
    MESSAGE             "...how are you currently managing this at &Partner?"

`jacob` is `ogpartner-dk`/`jacob-faertz`, who sorted first. Enabling
`LINKEDIN_ADD_LEAD` would have sent thirteen people at thirteen other
companies a connection note addressing them as Jacob.

WHY `_plan` HAD NO TESTS AND THAT IS THE POINT. `tests/test_heyreachfactory.py`
covers the mapping, the refusals, the graph shape and the write door - 36 tests
- and calls neither `_plan` nor `stage`. Every piece was correct and the
function that assembled them was never asked what it produced. That is the
defect shape CLAUDE.md names: a thing computed correctly that nothing
downstream checks.

So these tests assert on what `_plan` RETURNS, and the central one is negative:
no contact's own sentence may appear anywhere in the graph.
"""
import json
import unittest

from src import approval, heyreachfactory
from tests.test_heyreachfactory import _full_record, _record_missing_step


def rewrite_note(rec, contact_key, step_key, note):
    """Give a step different words AND the approval that certifies them.

    A fixture that edits a step's note without re-stamping it is an
    edited-after-approval step, and `heyreachfactory._step_copy` now refuses
    one - correctly. Every test below that rewrites a note is asking a
    different question (whose words reach whose lead, does the claims gate
    fire), so the words it substitutes have to be approved words.
    """
    step = rec["cadence"][contact_key][step_key]
    step["note"] = note
    step["approval"] = dict(step.get("approval") or {},
                            fingerprint=approval.fingerprint(step))
    return step


def config_with_fallbacks(**overrides):
    """A client config carrying a fallback for every required role."""
    fallbacks = {role: f"fallback for {role}"
                 for role in heyreachfactory.REQUIRED_ROLES}
    fallbacks.update(overrides)
    return {"name": "Test", "linkedin_sequence": {"fallbacks": fallbacks}}


def campaign_row(record_ids):
    return {"campaign_id": "c1", "client": "productive",
            "name": "test", "record_ids": list(record_ids),
            "heyreach_campaign_id": "599020"}


def plan(recs, config=None):
    return heyreachfactory._plan(
        campaign_row([r["id"] for r in recs]), recs,
        config or config_with_fallbacks())


class TheGraphCarriesNobodysWords(unittest.TestCase):

    def test_no_contacts_sentence_appears_in_the_sequence(self):
        """THE REGRESSION. This is the whole incident in one assertion."""
        rec = _full_record("pat")
        built = plan([rec])
        blob = json.dumps(built["sequence"])
        for step_key, step in rec["cadence"]["pat"].items():
            note = (step.get("note") or "").strip()
            if not note:
                continue
            with self.subTest(step=step_key):
                self.assertNotIn(
                    note, blob,
                    f"{step_key}'s approved words are baked into the "
                    f"campaign-level graph; every other lead would receive "
                    f"copy written for this one")

    def test_the_sequence_carries_a_variable_for_every_required_role(self):
        built = plan([_full_record()])
        blob = json.dumps(built["sequence"])
        for role in heyreachfactory.REQUIRED_ROLES:
            with self.subTest(role=role):
                self.assertIn("{" + role + "}", blob)

    def test_two_contacts_share_one_graph_and_keep_their_own_words(self):
        """The property that makes a campaign-level sequence safe at all."""
        first = _full_record("pat")
        second = _full_record("carla")
        second["id"] = "beta"
        rewrite_note(second, "carla", "li1", "Hi Carla, quite different.")

        built = plan([first, second])
        fields = {c["contact_key"]: c["custom_fields"]
                  for c in built["contacts"]}
        self.assertEqual(set(fields), {"pat", "carla"})
        self.assertNotEqual(fields["pat"]["connection_note"],
                            fields["carla"]["connection_note"])
        self.assertEqual(fields["carla"]["connection_note"],
                         "Hi Carla, quite different.")
        # And exactly one graph, mentioning neither of them.
        blob = json.dumps(built["sequence"])
        self.assertNotIn("Carla", blob)
        self.assertNotIn("Pat", blob)

    def test_the_graph_does_not_change_when_the_first_contact_changes(self):
        """`complete[0]` was the bug. Reordering must be a no-op now."""
        first = _full_record("pat")
        second = _full_record("carla")
        second["id"] = "beta"
        second["cadence"]["carla"]["li1"]["note"] = "Totally different words."
        forwards = plan([first, second])["sequence"]
        backwards = plan([second, first])["sequence"]
        self.assertEqual(json.dumps(forwards), json.dumps(backwards))


class AnIncompleteContactDoesNotDecideWhatTheCampaignSays(unittest.TestCase):

    def test_an_incomplete_contact_is_reported_and_not_pushable(self):
        good = _full_record("pat")
        bad = _record_missing_step("li3", "carla")
        bad["id"] = "beta"
        built = plan([good, bad])
        pushable = {c["contact_key"] for c in built["pushable"]}
        self.assertEqual(pushable, {"pat"})
        self.assertTrue(any(m[0] == "carla" for m in built["missing"]))

    def test_the_sequence_is_unaffected_by_an_incomplete_contact(self):
        """Before this change an incomplete contact could not be tolerated at
        all: the graph came from a contact, so a missing step was a campaign
        problem. Now it is only that lead's problem."""
        good = _full_record("pat")
        bad = _record_missing_step("li3", "carla")
        bad["id"] = "beta"
        alone = plan([good])["sequence"]
        together = plan([good, bad])["sequence"]
        self.assertEqual(json.dumps(alone), json.dumps(together))


class TheFallbackIsTheClientsAndNotThisModules(unittest.TestCase):

    def test_a_missing_fallback_refuses_and_names_the_role(self):
        config = config_with_fallbacks()
        del config["linkedin_sequence"]["fallbacks"]["connected_4"]
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            plan([_full_record()], config)
        self.assertIn("connected_4", str(caught.exception))

    def test_no_fallbacks_at_all_refuses(self):
        with self.assertRaises(heyreachfactory.FactoryRefused):
            plan([_full_record()], {"name": "Test"})

    def test_the_configured_fallbacks_pass_lint_and_claims(self):
        """THE FALLBACKS ARE PROSPECT-FACING COPY AND NOTHING GUARDED THEM.

        Every other word this system sends is generated, linted, claim-checked
        and approved. These are typed into a YAML file by a human and go
        straight to a real person the moment HeyReach cannot fill a variable -
        which is precisely the moment something has already gone wrong.

        So they are held to the same two gates as generated copy. `quality` is
        not applied: it asks whether a message repeats its siblings, and these
        deliberately share wording across the two branches because the same
        rung means the same thing on both.
        """
        from src import claims, clients, lint

        config = clients.load("productive")
        fallbacks = (config.get("linkedin_sequence") or {}).get("fallbacks")
        self.assertTrue(fallbacks, "the client config declares no fallbacks")

        rec = {"id": "probe", "client": "productive", "company": "Example",
               "state": "approved", "company_facts": {"name": "Example"},
               "contacts": [{"key": "c1", "name": "Ada Tester",
                             "first_name": "Ada", "title": "Founder",
                             "linkedin": "https://www.linkedin.com/in/ada"}]}
        contact = rec["contacts"][0]
        for role in heyreachfactory.REQUIRED_ROLES:
            text = fallbacks.get(role)
            with self.subTest(role=role):
                self.assertTrue(text, f"no fallback declared for {role}")
                action = "connect" if role == "connection_note" else "message"
                step = {"channel": "linkedin", "linkedin_action": action,
                        "note": text}
                self.assertEqual(sorted(lint.check_linkedin(rec, "c1", step)),
                                 [])
                self.assertEqual(claims.check(text, rec, contact), [])

    def test_the_fallbacks_claim_no_prior_contact(self):
        """The one claim a fallback could most easily make by accident.

        A fallback fires when personalisation failed, so it is read by
        somebody this system may never have written to. Stated separately
        from the gate above because it is the specific failure that reached a
        provider once already - lead 203708's "Final note on our previous
        discussions"."""
        from src import clients

        fallbacks = ((clients.load("productive").get("linkedin_sequence")
                      or {}).get("fallbacks") or {})
        for role, text in sorted(fallbacks.items()):
            with self.subTest(role=role):
                low = str(text).lower()
                for phrase in ("previous", "as discussed", "as i mentioned",
                               "following up on our", "last time we",
                               "great speaking", "thanks for your time"):
                    self.assertNotIn(phrase, low)

    def test_the_fallback_reaches_the_graph(self):
        """It has to be IN the graph, not merely configured - HeyReach reads
        `fallbackMessage` off the node when a variable will not fill."""
        built = plan([_full_record()])
        blob = json.dumps(built["sequence"])
        for role in heyreachfactory.REQUIRED_ROLES:
            with self.subTest(role=role):
                self.assertIn(f"fallback for {role}", blob)


class OnlyTheCampaignsOwnRecordsAreConsidered(unittest.TestCase):
    """`_plan` walked the whole estate, and `pushable` is what a lead write
    reads.

    Measured against `productive-linkedin-production-v1`, whose row names
    fourteen records: 92 contacts considered and 598 missing-copy entries for
    records not in the campaign. Harmless while the graph came from one
    contact and the extra names only padded a report; not harmless once a set
    of pushable contacts is the input to a write.
    """

    def test_a_record_the_campaign_does_not_name_is_not_considered(self):
        inside = _full_record("pat")
        outside = _full_record("carla")
        outside["id"] = "not-in-this-campaign"
        built = heyreachfactory._plan(
            campaign_row(["acme"]), [inside, outside], config_with_fallbacks())
        self.assertEqual([c["contact_key"] for c in built["contacts"]],
                         ["pat"])
        self.assertEqual(built["missing"], [])

    def test_a_record_belonging_to_another_client_refuses(self):
        """Not skipped quietly. A campaign naming another client's record is a
        tenancy error, and the permissive reading is how one client's prospect
        enters another client's campaign."""
        other = _full_record("carla")
        other["id"] = "beta"
        other["client"] = "contactout"
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._plan(campaign_row(["acme", "beta"]),
                                  [_full_record("pat"), other],
                                  config_with_fallbacks())
        self.assertIn("tenancy", str(caught.exception))

    def test_a_campaign_naming_no_records_refuses(self):
        """An empty set is not a licence to walk the estate."""
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._plan(campaign_row([]), [_full_record()],
                                  config_with_fallbacks())
        self.assertIn("names no records", str(caught.exception))


class LinkedInCopyIsClaimCheckedBeforeItCanBePushed(unittest.TestCase):
    """The email half had three gates at store time and the LinkedIn push had
    none of them at push time.

    `generate` runs lint, claims and quality when a draft is STORED, and
    `executionguard` runs claims again before a SEND. Putting a lead into a
    campaign is not a send, so nothing stood between a stored LinkedIn note
    and a real person receiving it.

    Measured 2026-09-14 across the Productive estate: 26 stored LinkedIn notes
    assert something the record does not support, and eight of the fifteen
    contacts this campaign would have pushed carried one. The checkpoint's
    "17 unsupported drafts remain" was EMAIL ONLY - the 194 stored LinkedIn
    notes had never been audited at all.
    """

    def test_a_contact_claiming_prior_contact_cannot_be_pushed(self):
        """With one contact and that contact unsafe, the whole plan refuses -
        there is nobody left to build a campaign for."""
        rec = _full_record("pat")
        rewrite_note(rec, "pat", "li2",
                     "Following up on our previous discussions about your "
                     "delivery pipeline.")
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            plan([rec])
        self.assertIn("does not support", str(caught.exception))

    def test_the_refusal_is_not_the_missing_copy_one(self):
        """Three different problems, three different messages. "No approved
        copy" is a generation job and "asserts something unsupported" is a
        regeneration job on copy that already exists; one message covering
        both sends a reader to the wrong place."""
        rec = _full_record("pat")
        rewrite_note(rec, "pat", "li2",
                     "Following up on our previous discussions.")
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            plan([rec])
        message = str(caught.exception)
        self.assertNotIn("approved LinkedIn copy is missing", message)
        self.assertIn("regenerate", message)
        # li2 fills both first-message roles, so the named variable is one of
        # them rather than the cadence step key.
        self.assertTrue("connected_1" in message or "message_2" in message)

    def test_a_step_with_no_graph_role_cannot_block_a_push(self):
        """`li6` has no position in the graph, so its words never reach
        anybody and its claims cannot disqualify the contact.

        This is the difference between auditing STORED copy and auditing copy
        that will actually be SENT. Three contacts in the real cohort are
        pushable precisely because their only bad step is li6.
        """
        rec = _full_record("pat")
        rec["cadence"]["pat"]["li6"]["note"] = (
            "As we discussed on our previous call about your margins.")
        built = plan([rec])
        self.assertEqual(built["unsupported"], [])
        self.assertEqual([c["contact_key"] for c in built["pushable"]],
                         ["pat"])

    def test_one_bad_contact_does_not_stop_a_clean_one(self):
        good = _full_record("pat")
        bad = _full_record("carla")
        bad["id"] = "beta"
        bad["cadence"]["carla"]["li2"]["note"] = (
            "Great speaking with you on our previous call.")
        built = heyreachfactory._plan(
            campaign_row(["acme", "beta"]), [good, bad],
            config_with_fallbacks())
        self.assertEqual([c["contact_key"] for c in built["pushable"]],
                         ["pat"])

    def test_the_sequence_is_unaffected_by_an_unsupported_claim(self):
        """The graph carries variables, so one contact's bad words cannot
        change what the campaign says - only whether they are in it."""
        good = _full_record("pat")
        bad = _full_record("carla")
        bad["id"] = "beta"
        bad["cadence"]["carla"]["li2"]["note"] = "As per our previous call."
        alone = plan([good])["sequence"]
        together = heyreachfactory._plan(
            campaign_row(["acme", "beta"]), [good, bad],
            config_with_fallbacks())["sequence"]
        self.assertEqual(json.dumps(alone), json.dumps(together))


class InMailIsRefusedRatherThanHalfWired(unittest.TestCase):

    def test_include_inmail_refuses_and_says_why(self):
        """An INMAIL carries a subject AND a message, so it needs two
        variables per lead. Neither is wired and no InMail copy is ever
        approved, so this refuses rather than sending one of the two."""
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._plan(
                campaign_row(["acme"]), [_full_record()],
                config_with_fallbacks(), include_inmail=True)
        self.assertIn("InMail", str(caught.exception))

    def test_the_plan_reports_inmail_as_absent(self):
        self.assertFalse(plan([_full_record()])["inmail_included"])


if __name__ == "__main__":
    unittest.main()
