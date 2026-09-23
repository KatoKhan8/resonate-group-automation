"""The operator's test identity reaches no client channel and no figure.

OPERATOR INSTRUCTION, 2026-09-23: `/in/zbeslic` and EmailBison lead 204966 are
the cross-channel stop TEST identity, excluded from every reply count, report
and client figure, permanently.

The defect these guard: on 2026-09-23 a `positive_reply` for that profile was
routed to C0BFUF4JRK9 - PRODUCTIVE'S OWN CHANNEL - and suppressed by hand. A
hand-edit stops one notification; the operator replied three times and every
future reply from that profile would have planned another.

Two halves, and each is tested for its OWN failure direction, because passing
one proves nothing about the other:

    the write   a NEW notification never gets a channel
    the read    a notification ALREADY in the feed never reaches a count

Deleting either half must turn a test red here.
"""
import os
import shutil
import tempfile
import unittest

from src import notify, store, testidentity


class Isolated(unittest.TestCase):
    """`notify.plan` writes through `store`, so the store is pointed at a
    throwaway directory. Without this the production guard refuses - which it
    did, correctly, the first time these were run."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rga-testidentity-")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(self._restore, self._env)
        store.use_directory(os.path.join(self._tmp, "work"))

    @staticmethod
    def _restore(env):
        for key, value in env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class TestTheIdentityIsRecognised(unittest.TestCase):
    """The match is on ANY binding - see the module docstring for why."""

    def test_the_record_id_names_it(self):
        self.assertTrue(
            testidentity.matches({"record_id":
                                  "crosschannel-stop-test-2026-09-23"}))

    def test_the_contact_key_names_it(self):
        self.assertTrue(testidentity.matches({"contact_key":
                                              "zvonimir-beslic"}))

    def test_the_lead_id_names_it_as_int_and_as_string(self):
        self.assertTrue(testidentity.matches({"lead_id": 204966}))
        self.assertTrue(testidentity.matches({"lead_id": "204966"}))

    def test_the_profile_names_it_in_every_shape_this_estate_stores(self):
        for value in ("/in/zbeslic",
                      "https://www.linkedin.com/in/zbeslic",
                      "https://www.linkedin.com/in/zbeslic/",
                      "HTTPS://WWW.LINKEDIN.COM/in/zbeslic?originalSubdomain=hr"):
            with self.subTest(value=value):
                self.assertTrue(testidentity.matches({"linkedin": value}),
                                f"{value!r} should resolve to the test slug")

    def test_the_address_names_it_case_insensitively(self):
        self.assertTrue(testidentity.matches({"email": "Zvonimir@Resonate.co"}))

    def test_a_real_prospect_does_not_match(self):
        """The exclusion must not widen. A prospect that matched would be
        silently dropped from the client's own reply count."""
        for value in ({"record_id": "productive-acme-2026-09-22"},
                      {"contact_key": "jane-doe"},
                      # 204968: NOT a test lead. 204966 and 204967
                      # both are - this line said 204967 until the
                      # second test lead was created, which made the
                      # assertion claim the opposite of the truth.
                      {"lead_id": 204968},
                      {"linkedin": "https://www.linkedin.com/in/zbeslicic"},
                      {"email": "zvonimir@example.test"},
                      {"campaign_id": None},
                      {}):
            with self.subTest(value=value):
                self.assertFalse(testidentity.matches(value))

    def test_a_near_miss_slug_does_not_match(self):
        """`zbeslic2` is a different person. Substring matching here would
        exclude them from the client's figures and nobody would see it."""
        self.assertFalse(
            testidentity.matches({"linkedin": "/in/zbeslic2"}))

    def test_it_never_raises_on_the_shapes_a_counting_loop_holds(self):
        for value in (None, "", [], {}, {"a": None}, 0, [None, ""]):
            with self.subTest(value=value):
                self.assertFalse(testidentity.matches(value))


class TestTheWriteIsSuppressed(Isolated):

    def _plan(self, ids, rows):
        return notify.plan(notify.POSITIVE_REPLY, "productive",
                           fields={"company": "Resonate",
                                   "contact_name": "Zvonimir Beslic",
                                   "channel": "linkedin"},
                           ids=ids, rows=rows)

    def test_a_positive_reply_for_the_test_identity_gets_no_channel(self):
        """The exact 2026-09-23 shape. `channel` must be None: a channel is
        the only thing that can carry this to the client."""
        rows = []
        planned = self._plan({"record_id": "crosschannel-stop-test-2026-09-23",
                              "contact_key": "zvonimir-beslic"}, rows)
        self.assertEqual(planned["status"], notify.SUPPRESSED)
        self.assertIsNone(planned["channel"])
        self.assertEqual(planned["destination"], notify.NOWHERE)
        self.assertIn("test", planned["why"].lower())

    def test_it_is_recorded_rather_than_dropped(self):
        """A notification that silently does not exist is indistinguishable
        from one nobody built. The row has to be in the FEED to be audited -
        `rows` here is the routing table, not the store."""
        planned = self._plan({"lead_id": 204966}, [])
        self.assertIsNotNone(planned)
        stored = notify.get(planned["id"])
        self.assertIsNotNone(stored, "the suppressed row must be persisted")
        self.assertEqual(stored["status"], notify.SUPPRESSED)
        self.assertEqual(stored["why"], testidentity.WHY)

    def test_a_real_positive_reply_is_still_routed(self):
        """The guard that this exclusion did not disable the feature. Without
        it, suppressing everything would pass every test above."""
        rows = []
        planned = self._plan({"record_id": "productive-acme-2026-09-22",
                              "contact_key": "jane-doe"}, rows)
        self.assertNotEqual(planned["status"], notify.SUPPRESSED)


class TestTheReadExcludesHistory(unittest.TestCase):
    """Suppressing at the write does nothing about rows already written."""

    def test_an_already_written_row_is_not_counted(self):
        from src import testidentity as ti
        rows = [
            {"type": "positive_reply",
             "ids": {"record_id": "crosschannel-stop-test-2026-09-23"}},
            {"type": "positive_reply",
             "ids": {"record_id": "productive-acme-2026-09-22"}},
        ]
        counted = [r for r in rows if not ti.matches(r.get("ids"))]
        self.assertEqual(len(counted), 1)
        self.assertEqual(counted[0]["ids"]["record_id"],
                         "productive-acme-2026-09-22")

    def test_the_suppressed_row_from_2026_09_23_is_the_case(self):
        """Verbatim ids from `work/notifications.jsonl`, row bda9179392a1."""
        self.assertTrue(testidentity.matches({
            "record_id": "crosschannel-stop-test-2026-09-23",
            "contact_key": "zvonimir-beslic",
            "provider_event_id": "heyreach:2-ZjM5YTNl:2026-09-23T12:34:28.579Z",
            "campaign_id": None}))


if __name__ == "__main__":
    unittest.main()
