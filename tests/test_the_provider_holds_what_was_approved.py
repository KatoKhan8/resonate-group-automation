"""Nothing compared the provider's configuration to the approved one.

THE LIVE FAILURE THIS PINS. A dedicated one-lead LinkedIn canary was built by
hand in the vendor UI on 2026-09-09 with the approved note pasted in. Provider
read-back showed HeyReach's own pre-filled placeholder:

    payload.messages == ["Hey, would love to connect!"]

Every existing check passed it - provably LinkedIn-only, no hazard, note not
empty, right lead, right seat, right workspace - because "a note exists" and
"the note is the approved note" are different questions and only the first was
ever asked. `configdiff` asks all of them at once.

Three properties are asserted here above all others:

  * the diff walks the UNION of both sides, so a sender, node or lead that
    exists at the provider and in nobody's approval FAILS as `unexpected`;
  * `unverifiable` is a failure for a required field, never a warning;
  * `APPROVED_CONFIG` is built from canonical state, so no provider value can
    ever become its own approval.
"""
import unittest
from unittest import mock

from src import configdiff

APPROVED_NOTE = ("hi Dana, i work with Design Services teams on utilisation. "
                 "curious how Brightpath handles it at your size. happy to connect.")
PLACEHOLDER = "Hey, would love to connect!"


def approved(**over):
    """A normalised APPROVED_CONFIG for a one-lead LinkedIn canary."""
    row = {
        "campaign_id": "594061",
        "campaign_name": "CLIENT - CANARY - 2026-09-09",
        "status": "PAUSED",
        "org_unit": "118832",
        "sender_ids": frozenset({"116968"}),
        "list_id": "926076",
        "lead_set": frozenset({"danamarsh"}),
        "lead_count": 1,
        "actions": ("CONNECTION_REQUEST", "END"),
        "note": APPROVED_NOTE,
        "delays": (("DAY", 3),),
        "linkedin_only": True,
        "bison_handoff": False,
        "daily_limit": 1,
    }
    row.update(over)
    return row


def provider(**over):
    """The provider side, shaped as `provider_heyreach` returns it."""
    row = dict(approved())
    row["lead_set"] = configdiff.UNVERIFIABLE
    row["daily_limit"] = configdiff.UNVERIFIABLE
    row["delays"] = (("DAY", 3),)
    row.update(over)
    return row


def run(a=None, p=None, required=configdiff.REQUIRED_HEYREACH):
    return configdiff.diff(a or approved(), p or provider(), required)


class AnExactMatchPasses(unittest.TestCase):
    def test_the_intended_canary_passes(self):
        result = run()
        self.assertEqual(result["verdict"], configdiff.PASS, result["failures"])

    def test_it_actually_checked_something(self):
        """A diff that examined nothing must not read as agreement."""
        result = run()
        self.assertGreaterEqual(result["checked"], 12)
        self.assertTrue(result["required"])

    def test_whitespace_around_the_note_is_not_a_difference(self):
        result = run(p=provider(note=APPROVED_NOTE))
        self.assertEqual(result["fields"]["note"]["verdict"], configdiff.MATCH)


class ThePlaceholderNoteFails(unittest.TestCase):
    """The live defect, as a test."""

    def test_the_exact_placeholder_that_was_configured_fails(self):
        result = run(p=provider(note=PLACEHOLDER))
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertEqual(result["fields"]["note"]["verdict"], configdiff.MISMATCH)
        self.assertIn("note: mismatch", result["failures"])

    def test_the_failure_reports_both_sides(self):
        """A verdict nobody can act on is not much better than no verdict."""
        row = run(p=provider(note=PLACEHOLDER))["fields"]["note"]
        self.assertEqual(row["approved"], APPROVED_NOTE)
        self.assertEqual(row["provider"], PLACEHOLDER)

    def test_an_empty_note_fails(self):
        self.assertEqual(run(p=provider(note=""))["verdict"], configdiff.FAIL)

    def test_one_changed_word_fails(self):
        altered = APPROVED_NOTE.replace("utilisation", "utilization")
        self.assertEqual(run(p=provider(note=altered))["verdict"],
                         configdiff.FAIL)

    def test_changed_case_fails_because_case_is_the_copy(self):
        self.assertEqual(run(p=provider(note=APPROVED_NOTE.capitalize()))["verdict"],
                         configdiff.FAIL)

    def test_a_truncated_note_fails(self):
        self.assertEqual(run(p=provider(note=APPROVED_NOTE[:60]))["verdict"],
                         configdiff.FAIL)


class UnexpectedThingsFailEvenWhenNobodyListedThem(unittest.TestCase):
    """The union rule. The dangerous field is the one nobody approved."""

    def test_an_extra_sender_fails(self):
        result = run(p=provider(sender_ids=frozenset({"116968", "129531"})))
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertEqual(result["fields"]["sender_ids"]["verdict"],
                         configdiff.MISMATCH)

    def test_an_extra_sequence_action_fails(self):
        result = run(p=provider(
            actions=("CONNECTION_REQUEST", "MESSAGE", "END")))
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertEqual(result["fields"]["actions"]["verdict"],
                         configdiff.MISMATCH)

    def test_a_second_lead_fails_on_the_count(self):
        result = run(p=provider(lead_count=2))
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertIn("lead_count: mismatch", result["failures"])

    def test_a_provider_only_field_fails_as_unexpected(self):
        """Not in REQUIRED, and it must fail anyway: nobody approved it."""
        result = run(p=provider(inmail_enabled=True))
        self.assertEqual(result["fields"]["inmail_enabled"]["verdict"],
                         configdiff.UNEXPECTED)
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertIn("inmail_enabled: unexpected", result["failures"])

    def test_an_unexpected_field_fails_even_with_no_required_list(self):
        result = run(p=provider(inmail_enabled=True), required=())
        self.assertEqual(result["verdict"], configdiff.FAIL)


class CrossChannelAndTenancyFail(unittest.TestCase):
    def test_a_bison_handoff_fails(self):
        result = run(p=provider(bison_handoff=True))
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertIn("bison_handoff: mismatch", result["failures"])

    def test_not_provably_linkedin_only_fails(self):
        result = run(p=provider(linkedin_only=False))
        self.assertEqual(result["verdict"], configdiff.FAIL)

    def test_a_different_org_unit_fails(self):
        result = run(p=provider(org_unit="999999"))
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertIn("org_unit: mismatch", result["failures"])

    def test_a_different_list_fails(self):
        """Re-using the client's big production list would look like this."""
        result = run(p=provider(list_id="605355"))
        self.assertEqual(result["verdict"], configdiff.FAIL)

    def test_a_different_campaign_id_fails(self):
        result = run(p=provider(campaign_id="594060"))
        self.assertEqual(result["verdict"], configdiff.FAIL)

    def test_an_activated_campaign_fails_the_expected_status(self):
        result = run(p=provider(status="IN_PROGRESS"))
        self.assertEqual(result["verdict"], configdiff.FAIL)


class UnverifiableIsAFailureNotAWarning(unittest.TestCase):
    def test_an_unverifiable_required_field_fails(self):
        result = run(p=provider(note=configdiff.UNVERIFIABLE))
        self.assertEqual(result["fields"]["note"]["verdict"],
                         configdiff.UNVERIFIABLE)
        self.assertEqual(result["verdict"], configdiff.FAIL)
        self.assertIn("note: unverifiable", result["failures"])

    def test_the_two_structurally_unverifiable_heyreach_fields_do_not_fail(self):
        """Deliberate, and documented: HeyReach publishes no route for a
        campaign's lead identities and no per-campaign limit field. So a
        ONE-lead campaign is proven by `lead_count` plus a verified `list_id`,
        and both are required. Neither `lead_set` nor `daily_limit` is."""
        self.assertNotIn("lead_set", configdiff.REQUIRED_HEYREACH)
        self.assertNotIn("daily_limit", configdiff.REQUIRED_HEYREACH)
        self.assertIn("lead_count", configdiff.REQUIRED_HEYREACH)
        self.assertIn("list_id", configdiff.REQUIRED_HEYREACH)
        self.assertEqual(run()["verdict"], configdiff.PASS)

    def test_emailbison_requires_the_fields_heyreach_cannot_verify(self):
        """The asymmetry is real: EmailBison publishes limits and both sets."""
        for field in ("max_emails_per_day", "max_new_leads_per_day",
                      "lead_count", "sender_ids", "subjects", "bodies"):
            self.assertIn(field, configdiff.REQUIRED_BISON)


class TheComparisonRefusesRatherThanPassing(unittest.TestCase):
    """`DiffRefused` means the question was not asked. Never a PASS."""

    def test_a_non_dict_side_is_refused(self):
        for bad in (None, [], "config", 0):
            with self.subTest(bad=bad):
                with self.assertRaises(configdiff.DiffRefused):
                    configdiff.diff(approved(), bad)
                with self.assertRaises(configdiff.DiffRefused):
                    configdiff.diff(bad, provider())

    def test_no_canonical_campaign_is_refused(self):
        with self.assertRaises(configdiff.DiffRefused):
            configdiff.approved_heyreach(None)

    def test_a_campaign_naming_no_provider_id_is_refused(self):
        with self.assertRaises(configdiff.DiffRefused):
            configdiff.approved_heyreach({"client": "productive"})

    def test_a_missing_provider_campaign_is_refused_not_treated_as_empty(self):
        with mock.patch.object(heyreach_mod(), "campaign_by_id",
                               return_value=None):
            with self.assertRaises(configdiff.DiffRefused):
                configdiff.provider_heyreach("594061")

    def test_an_unwalkable_graph_is_refused(self):
        hr = heyreach_mod()
        with mock.patch.object(hr, "campaign_by_id", return_value={"id": 1}), \
             mock.patch.object(hr, "campaign_sequence", return_value={}), \
             mock.patch.object(hr, "walk_sequence",
                               return_value=([], set(), True)):
            with self.assertRaises(configdiff.DiffRefused):
                configdiff.provider_heyreach("594061")

    def test_two_provider_notes_are_refused(self):
        hr = heyreach_mod()
        node = {"nodeType": "CONNECTION_REQUEST", "actionDelay": 0}
        with mock.patch.object(hr, "campaign_by_id", return_value={"id": 1}), \
             mock.patch.object(hr, "campaign_sequence", return_value=node), \
             mock.patch.object(hr, "walk_sequence",
                               return_value=([node], {"CONNECTION_REQUEST"}, False)), \
             mock.patch.object(hr, "connection_notes", return_value=["a", "b"]):
            with self.assertRaises(configdiff.DiffRefused):
                configdiff.provider_heyreach("594061")


class ApprovedNeverComesFromTheProvider(unittest.TestCase):
    """If it did, the diff would be the provider agreeing with itself."""

    def test_the_approved_builder_makes_no_provider_call(self):
        hr = heyreach_mod()
        with mock.patch.object(hr, "campaign_by_id") as by_id, \
             mock.patch.object(hr, "campaign_sequence") as seq:
            with self.assertRaises(configdiff.DiffRefused):
                configdiff.approved_heyreach({"client": "productive"})
            by_id.assert_not_called()
            seq.assert_not_called()


def heyreach_mod():
    from src.providers import heyreach
    return heyreach


if __name__ == "__main__":
    unittest.main()
