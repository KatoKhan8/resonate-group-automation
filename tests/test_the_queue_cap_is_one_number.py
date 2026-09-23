"""One refused read must not blind a watcher, and three readers agree.

MEASURED 2026-09-23. `work/heartbeat/bison-491.json` read
`READ-ERROR 122x PartialInventory` for hours while `campaign(491)` answered
fine - 281 sent, 8 replied, 331 leads, membership fully countable. Campaign
491's scheduled-email queue had grown to 647 rows, 44 pages, and
`bison_watch_loop` walked it at the 40-page default while
`slackagentreadback` and `scripts/hard_stop_check.py` both walked 400.

Two defects, and the second is the expensive one:

    the cap      a third reader with a different cap. The comment beside one
                 of the other two says why that is dangerous in as many
                 words: readers that disagree about how much of a campaign
                 they can see will disagree about what was sent.

    the blast    the queue read sat at the top of `snapshot()` with nothing
                 around it, so ONE refused sub-read discarded every other
                 field. `_membership_states` and `_provider_sending_plan` in
                 the same file already degrade to UNKNOWN; the queue read
                 never got the treatment.

The refusal itself was CORRECT and is not what is being fixed. The queue
genuinely could not be read whole, and returning 600 of 647 as though it were
all of them is the failure `_paged` exists to prevent.
"""
import unittest

from src.providers import bison


class TestTheCapIsOneNumber(unittest.TestCase):
    """The anti-drift mechanism. `slackagentreadback` imports bison inside
    its functions on purpose, so it cannot reference the constant at module
    level - a test is the only way to pin the agreement without costing that
    lazy import."""

    def test_the_agent_readback_agrees_with_the_provider(self):
        from src import slackagentreadback
        self.assertEqual(slackagentreadback.QUEUE_PAGE_CAP,
                         bison.CAMPAIGN_QUEUE_PAGE_CAP)

    def test_the_hard_stop_check_agrees_with_the_provider(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_hsc", "scripts/hard_stop_check.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.QUEUE_PAGE_CAP,
                         bison.CAMPAIGN_QUEUE_PAGE_CAP)

    def test_the_campaign_cap_is_larger_than_the_default(self):
        """If these were ever equalised the watcher would silently go back to
        refusing 491, which is the state this fixes."""
        self.assertGreater(bison.CAMPAIGN_QUEUE_PAGE_CAP, bison.PAGE_CAP)

    def test_it_still_covers_the_491_case_that_broke_it(self):
        """647 rows at 15 a page is 44 pages. The cap must clear it with
        room, and still be a cap rather than unbounded."""
        pages_491 = 44
        self.assertGreater(bison.CAMPAIGN_QUEUE_PAGE_CAP, pages_491)
        self.assertLess(bison.CAMPAIGN_QUEUE_PAGE_CAP, 10_000)


class TestARefusedQueueDoesNotBlindTheWatcher(unittest.TestCase):

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_bwl", "scripts/bison_watch_loop.py")
        self.watch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.watch)

    def _snapshot_with_refusing_queue(self):
        """The 2026-09-23 shape: the campaign row answers, the queue refuses."""
        real_campaign = self.watch.bison.campaign
        real_queue = self.watch.bison.scheduled_emails
        real_members = self.watch.bison.membership
        real_schedule = self.watch.bison.sending_schedule

        def refusing(*a, **k):
            raise bison.PartialInventory(
                "emailbison scheduled_emails: 44 pages to walk and this read "
                "stops at 40")

        self.watch.bison.campaign = lambda *a, **k: {
            "status": "active", "emails_sent": 281, "replied": 8,
            "bounced": 1, "unsubscribed": 0, "total_leads": 331,
            "updated_at": "2026-09-23T16:28:26.000000Z"}
        self.watch.bison.scheduled_emails = refusing
        self.watch.bison.membership = lambda *a, **k: {
            1: "in_sequence", 2: "replied"}
        self.watch.bison.sending_schedule = lambda *a, **k: {
            "emails_being_sent": 74}
        self.addCleanup(setattr, self.watch.bison, "campaign", real_campaign)
        self.addCleanup(setattr, self.watch.bison, "scheduled_emails",
                        real_queue)
        self.addCleanup(setattr, self.watch.bison, "membership", real_members)
        self.addCleanup(setattr, self.watch.bison, "sending_schedule",
                        real_schedule)
        return self.watch.snapshot(491)

    def test_the_snapshot_survives_the_refusal(self):
        """It used to raise out of `snapshot` and the whole heartbeat became
        READ-ERROR."""
        state = self._snapshot_with_refusing_queue()
        self.assertIsInstance(state, dict)

    def test_every_field_that_could_be_read_is_still_reported(self):
        """The point. 281 sends and 8 replies were readable the whole time
        and nobody could see them."""
        state = self._snapshot_with_refusing_queue()
        self.assertEqual(state["emails_sent"], 281)
        self.assertEqual(state["replied"], 8)
        self.assertEqual(state["bounced"], 1)
        self.assertEqual(state["leads"], 331)
        self.assertEqual(state["membership"], {"in_sequence": 1, "replied": 1})

    def test_the_queue_reads_unknown_and_never_zero(self):
        """A false zero here reports 647 rows -> 0 and fires QUEUED as though
        the provider had emptied the queue."""
        state = self._snapshot_with_refusing_queue()
        self.assertIsNone(state["queue_rows"])
        self.assertIsNone(state["sent_rows"])
        self.assertNotEqual(state["queue_rows"], 0)

    def test_first_scheduled_does_not_claim_nothing_is_planned(self):
        """`none` asserts the queue is empty. An unreadable queue cannot make
        that claim."""
        state = self._snapshot_with_refusing_queue()
        self.assertEqual(state["first_scheduled"], "unknown")
        self.assertNotEqual(state["first_scheduled"], "none")


class TestUnknownNeverReportsMovement(unittest.TestCase):
    """`None > 0` is a TypeError, and comparing against an unknown cannot
    mean a send happened either."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_bwl2", "scripts/bison_watch_loop.py")
        self.watch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.watch)

    def test_known_refuses_a_none_on_either_side(self):
        self.assertFalse(self.watch._known(None, 5))
        self.assertFalse(self.watch._known(5, None))
        self.assertFalse(self.watch._known(None, None))

    def test_known_accepts_two_real_readings_including_zero(self):
        """Zero is a reading. Guarding with `or 0` would have made these
        indistinguishable, which is the substitution being prevented."""
        self.assertTrue(self.watch._known(0, 0))
        self.assertTrue(self.watch._known(647, 600))


if __name__ == "__main__":
    unittest.main()
