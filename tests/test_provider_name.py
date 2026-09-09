"""What a Resonate campaign is called inside a provider.

The point of the string is legibility from the *other* side: an employee
opening EmailBison sees a list of campaigns somebody typed, and nothing
on that screen says which of them Resonate is filling.

The point of these tests is that the string never becomes identity.
Provider ids are what a payload is addressed to; a campaign renamed by
hand inside the provider is still the same campaign.
"""
import unittest

from src import providername as pn


class TheNameSaysWhoOwnsIt(unittest.TestCase):

    def test_it_renders_the_agreed_shape(self):
        self.assertEqual(
            pn.render("Productive", "EMAIL", "C-0241",
                      "DACH Agencies 50-100"),
            "[RESONATE-AUTO] | Productive | EMAIL | "
            "DACH Agencies 50-100 | C-0241")

    def test_the_marker_is_not_ambiguous(self):
        """`[AUTO]` answers "something automated this" without answering
        what. A provider account can hold automation from several tools."""
        self.assertEqual(pn.MARKER, "[RESONATE-AUTO]")
        self.assertTrue(pn.render("W", "EMAIL", "C-1").startswith(pn.MARKER))

    def test_both_channels_carry_the_same_canonical_id(self):
        """One logical campaign, two provider campaigns, findable as a
        pair from either side."""
        found = pn.describe("Productive", "C-0241", segment="DACH")
        self.assertEqual(len(found["names"]), 2)
        for name in found["names"].values():
            self.assertIn("C-0241", name)

    def test_the_channel_distinguishes_them(self):
        found = pn.describe("Productive", "C-0241")
        self.assertIn("EMAIL", found["names"]["email"])
        self.assertIn("LINKEDIN", found["names"]["linkedin"])
        self.assertNotEqual(found["names"]["email"],
                            found["names"]["linkedin"])

    def test_an_unknown_channel_is_refused(self):
        with self.assertRaises(ValueError):
            pn.render("W", "CARRIER_PIGEON", "C-1")

    def test_a_name_without_a_campaign_id_is_refused(self):
        """The id is the part somebody needs to match against Resonate."""
        with self.assertRaises(ValueError):
            pn.render("W", "EMAIL", "")

    def test_a_pipe_inside_a_segment_cannot_forge_a_field(self):
        name = pn.render("Prod|uctive", "EMAIL", "C-1")
        self.assertEqual(name.count(" | "), 3)


class TruncationKeepsWhatMatters(unittest.TestCase):
    """A name cut off mid-identifier is worse than a short one."""

    def test_a_long_name_is_within_the_limit(self):
        name = pn.render("Productive", "EMAIL", "C-0241", "X" * 400)
        self.assertLessEqual(len(name), pn.MAX_LENGTH)

    def test_the_marker_survives_truncation(self):
        name = pn.render("Productive", "EMAIL", "C-0241", "X" * 400)
        self.assertTrue(name.startswith(pn.MARKER))

    def test_the_campaign_id_survives_truncation(self):
        """It is last, and it is the part that identifies the campaign."""
        name = pn.render("Productive", "EMAIL", "C-0241", "X" * 400)
        self.assertTrue(name.endswith("C-0241"))

    def test_the_description_is_what_gets_dropped(self):
        name = pn.render("Productive", "EMAIL", "C-0241", "X" * 400)
        self.assertLess(name.count("X"), 400)

    def test_a_tiny_limit_still_keeps_marker_and_id(self):
        name = pn.render("Productive", "EMAIL", "C-0241", "Long segment",
                         maximum=60)
        self.assertLessEqual(len(name), 60)
        self.assertIn("C-0241", name)


class ANameIsNeverAnIdentity(unittest.TestCase):
    """The property this module must not quietly cost."""

    def test_it_exports_no_way_to_look_a_campaign_up_by_name(self):
        for forbidden in ("parse", "find", "lookup", "match", "by_name",
                          "resolve"):
            self.assertFalse(
                [n for n in dir(pn) if forbidden in n.lower()],
                f"{forbidden}: rendering must stay one-way")

    def test_is_managed_is_a_display_question(self):
        """It answers "show me which rows are ours" and nothing routes on
        it."""
        self.assertTrue(pn.is_managed("[RESONATE-AUTO] | Productive | EMAIL"))
        self.assertFalse(pn.is_managed("Q3 outbound"))
        self.assertFalse(pn.is_managed(None))

    def test_nothing_in_the_codebase_routes_on_a_provider_name(self):
        """Payloads are addressed to stored provider ids. If this ever
        fails, a rename inside a provider has become able to break a
        campaign."""
        import inspect

        from src import push
        source = inspect.getsource(push)
        self.assertNotIn("providername", source)
        self.assertIn("bison_campaign_id", source)


class MetadataIsProposedNotAssumed(unittest.TestCase):

    def test_it_carries_the_canonical_identifiers(self):
        found = pn.metadata("productive", "C-0241")
        self.assertEqual(found["managed_by"], "resonate")
        self.assertEqual(found["resonate_campaign_id"], "C-0241")
        self.assertEqual(found["workspace_id"], "productive")

    def test_support_is_unknown_rather_than_claimed(self):
        """Whether either provider accepts custom fields on a campaign is
        not established in this build, and inventing a capability is how
        an integration ships broken."""
        self.assertIsNone(pn.describe("W", "C-1")["metadata_supported"])

    def test_nothing_here_sends_anything(self):
        import inspect

        source = inspect.getsource(pn)
        for forbidden in ("requests", "urlopen", "http", "POST", "session"):
            self.assertNotIn(forbidden, source)

    def test_the_value_says_resonate_does_not_create_campaigns(self):
        """A reader of the description should not have to find that out
        from a document."""
        note = pn.describe("W", "C-1")["note"]
        self.assertIn("does not create", note)
        self.assertIn("never this string", note)


if __name__ == "__main__":
    unittest.main()
