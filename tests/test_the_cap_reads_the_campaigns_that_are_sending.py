r"""A cap that takes the oldest campaigns answers about the dead ones.

MEASURED LIVE, 2026-09-22 18:20Z, and this file is the reproduction.

The operator asked the running agent *what was sent today* in
`#resonate-os`. It answered with 491 and 492, said it could not attribute
494's sends to today, and **never mentioned 495 at all**. Read straight
off the provider in the same minute:

    491   145 sent today
    492    86 sent today
    494    42 sent today
    495    23 sent today          <- absent from the answer
    ---------------------------
          296 sent today, of which the agent could see 231

`sends_today` reads `ids[:8]`. `slackknowledge` built that list with
`sorted()` over the campaign ids **as strings**, so it ran oldest first:

    451 481 484 485 487 489 491 492 | 493 494 495 496 497 498
    \------------ the 8 read -----/   \-- the six cut off ---/

Every campaign that sent today except 491 and 492 sat past the cut. The
six the cap did read include four that have not sent since the 14th.

Two faults, and the second is the one that generalises:

1. **The cap took the wrong end.** New campaigns get new ids, so the
   newest work is always at the back of an ascending list and always the
   first thing a cap discards. Seven readers take `ids[:N]`.

2. **A truncated answer did not say it was truncated.** `lead_in_campaign`
   reports `campaigns_checked` and `lead_counts` calls an unreadable
   campaign a floor; `sends_today` returned 231 as though it were 296.
   A number that is a floor and does not say so is the defect this
   repository's whole problem register is made of.

And one latent fault the same line carries: the ids are sorted as TEXT, so
the day this provider issues a four-digit id, `'1001'` sorts below `'451'`
and the order stops meaning anything at all.
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackagenttools as tools                         # noqa: E402
from src import slackknowledge as knowledge                      # noqa: E402
from src import slackscope                                       # noqa: E402

#: The estate as it stood when this was measured, WITH THE REAL FIELDS.
#:
#: The `created_at` values are the live ones, and they are the reason this
#: file exists twice over: the six historical campaigns carry a date and
#: **the eight that are sending carry `None`**. A first fix ordered on
#: `created_at` and sorted the dead six above the live eight - the original
#: defect, restored by its own repair, and caught only because this fixture
#: was rebuilt from `work/campaigns.jsonl` instead of invented.
THE_ESTATE = [
    {"bison_campaign_id": "451", "created_at": "2026-09-13T08:36:04+00:00"},
    {"bison_campaign_id": "481", "created_at": "2026-09-13T19:29:23+00:00"},
    {"bison_campaign_id": "484", "created_at": "2026-09-16T05:45:04+00:00"},
    {"bison_campaign_id": "485", "created_at": "2026-09-16T08:20:14+00:00"},
    {"bison_campaign_id": "487", "created_at": "2026-09-17T06:25:21+00:00"},
    {"bison_campaign_id": "489", "created_at": "2026-09-18T05:17:19+00:00"},
    {"bison_campaign_id": "491", "created_at": None},
    {"bison_campaign_id": "492", "created_at": None},
    {"bison_campaign_id": "493", "created_at": None},
    {"bison_campaign_id": "494", "created_at": None},
    {"bison_campaign_id": "495", "created_at": None},
    {"bison_campaign_id": "496", "created_at": None},
    {"bison_campaign_id": "497", "created_at": None},
    {"bison_campaign_id": "498", "created_at": None},
]

#: What each of them had actually sent when the agent was asked.
SENT_TODAY = {"491": 145, "492": 86, "494": 42, "495": 23}


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


class TheListIsOrderedNewestFirst(unittest.TestCase):
    """`slackknowledge` decides which campaigns every capped reader sees.

    Fixing it here rather than at each `[:N]` is the point: there are seven
    of those and the next one written will not remember the rule.
    """

    def _ids(self, rows):
        with mock.patch.object(knowledge, "_campaign_rows",
                               lambda slug: rows):
            entry = {}
            return knowledge._campaign_ids_newest_first(rows)

    def test_the_newest_campaign_is_first(self):
        ids = self._ids(THE_ESTATE)
        self.assertEqual(ids[0], "498")
        self.assertEqual(ids[-1], "451")

    def test_every_campaign_that_sent_today_is_inside_the_smallest_cap(self):
        """The whole finding, as one assertion.

        Eight is the tightest cap any reader uses. Every campaign that sent
        today has to be inside it, or the agent answers a question about
        today out of campaigns that last sent a week ago.
        """
        ids = self._ids(THE_ESTATE)[:8]
        for campaign_id in sorted(SENT_TODAY):
            self.assertIn(campaign_id, ids,
                          "%s sent %d emails today and the cap hid it"
                          % (campaign_id, SENT_TODAY[campaign_id]))

    def test_the_old_ordering_is_what_lost_them(self):
        """The bug, asserted, so nobody restores `sorted()` by hand."""
        old = sorted(r["bison_campaign_id"] for r in THE_ESTATE)[:8]
        self.assertNotIn("495", old)
        self.assertNotIn("494", old)

    def test_a_four_digit_id_does_not_sort_below_a_three_digit_one(self):
        """Sorted as text, '1001' lands under '451'. Counted, it lands
        where it belongs."""
        rows = [{"bison_campaign_id": "451"}, {"bison_campaign_id": "1001"}]
        self.assertEqual(self._ids(rows)[0], "1001")

    def test_two_ids_order_by_number_not_by_text(self):
        rows = [{"bison_campaign_id": "7"}, {"bison_campaign_id": "12"}]
        self.assertEqual(self._ids(rows), ["12", "7"])

    def test_created_at_does_not_decide_the_order(self):
        """THE FIRST FIX'S OWN BUG, asserted.

        Every campaign that is sending carries `created_at: None` and every
        dead one carries a date, so any ordering that consults the field -
        nulls first or nulls last - puts the dead ones in front of the cap.
        The id is the only signal present on all of them.
        """
        ids = self._ids(THE_ESTATE)
        self.assertEqual(ids[:8], ["498", "497", "496", "495",
                                   "494", "493", "492", "491"])
        dated = self._ids([r for r in THE_ESTATE if r["created_at"]])
        self.assertEqual(dated[0], "489")

    def test_a_non_numeric_id_sorts_after_the_numbers_rather_than_raising(self):
        rows = list(THE_ESTATE) + [{"bison_campaign_id": "draft-x"}]
        self.assertEqual(self._ids(rows)[0], "draft-x")
        self.assertEqual(self._ids(rows)[1], "498")

    def test_a_row_with_no_provider_id_is_dropped_not_carried_as_none(self):
        rows = list(THE_ESTATE) + [{"created_at": "2026-09-30T00:00:00Z"}]
        ids = self._ids(rows)
        self.assertEqual(len(ids), len(THE_ESTATE))
        self.assertNotIn("None", ids)
        self.assertNotIn(None, ids)


class ACappedAnswerSaysItIsCapped(unittest.TestCase):
    """A floor that presents itself as a total is worse than no number."""

    def setUp(self):
        self._pack = tools.knowledge.pack
        self._detail = tools.readback.campaign_by_id
        self._default = tools._default_workspace
        ordered = knowledge._campaign_ids_newest_first(THE_ESTATE)
        tools.knowledge.pack = lambda *a, **k: {
            "workspaces": {"alpha": {"provider_campaign_ids": ordered}}}
        tools._default_workspace = lambda: "alpha"
        tools.readback.campaign_by_id = lambda cid: {
            "campaign_id": cid, "name": "campaign %s" % cid,
            "status": "active", "emails_sent": SENT_TODAY.get(str(cid), 0),
            "queue_rows": 10}
        self.addCleanup(self._restore)

    def _restore(self):
        tools.knowledge.pack = self._pack
        tools.readback.campaign_by_id = self._detail
        tools._default_workspace = self._default

    def test_sends_today_reads_the_campaigns_that_sent(self):
        out = tools.sends_today(internal())
        read = {str(row["campaign_id"]) for row in out["campaigns"]}
        for campaign_id in sorted(SENT_TODAY):
            self.assertIn(campaign_id, read)

    def test_sends_today_names_what_the_cap_hid(self):
        out = tools.sends_today(internal())
        self.assertEqual(out["campaigns_in_workspace"], len(THE_ESTATE))
        self.assertEqual(out["campaigns_not_read"],
                         len(THE_ESTATE) - tools.SENDS_TODAY_CAP)
        self.assertIn("floor", out["note"].lower())

    def test_a_workspace_inside_the_cap_is_not_called_a_floor(self):
        """The note has to be absent when it does not apply, or it becomes
        a line people stop reading."""
        tools.knowledge.pack = lambda *a, **k: {
            "workspaces": {"alpha": {"provider_campaign_ids": ["498", "497"]}}}
        out = tools.sends_today(internal())
        self.assertEqual(out["campaigns_not_read"], 0)
        self.assertNotIn("floor", out["note"].lower())

    def test_the_cap_is_still_a_cap(self):
        """Fixing the order is not permission to read forty campaigns."""
        tools.knowledge.pack = lambda *a, **k: {
            "workspaces": {"alpha": {
                "provider_campaign_ids": [str(i) for i in range(40)]}}}
        asked = []
        tools.readback.campaign_by_id = lambda cid: asked.append(cid) or {
            "campaign_id": cid, "emails_sent": 1, "queue_rows": 1}
        tools.sends_today(internal())
        self.assertEqual(len(asked), tools.SENDS_TODAY_CAP)

    def test_a_client_channel_still_only_reaches_its_own(self):
        """The ordering change moves which ids are read. It may not move
        WHOSE."""
        tools.knowledge.pack = lambda *a, **k: {"workspaces": {
            "alpha": {"provider_campaign_ids": ["498"]},
            "beta": {"provider_campaign_ids": ["601"]}}}
        asked = []
        tools.readback.campaign_by_id = lambda cid: asked.append(str(cid)) or {
            "campaign_id": cid, "emails_sent": 1, "queue_rows": 1}
        tools.sends_today(client("alpha"))
        self.assertEqual(asked, ["498"])
        self.assertNotIn("601", asked)


if __name__ == "__main__":
    unittest.main()
