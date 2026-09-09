"""`mapping.bison_campaigns` read page one and called it every campaign.

THE DEFECT, AND WHY IT MATTERED MORE THAN IT LOOKED. `GET /campaigns` returns
the Laravel `{data, links, meta}` envelope with `meta.per_page` of 15 - the same
envelope and the same page size that once turned a 225-inbox estate into a
fifteen-inbox one. One real estate holds 25 campaigns. So any campaign id past
the first fifteen answered MISSING, and `validate` treats MISSING as
`blocked_by` - so the launch was correctly blocked with a FALSE DIAGNOSIS, and
the message it printed said "either the id is wrong or the key belongs to another
workspace". Somebody would go hunting a typo that did not exist.

It also returned `[]` on a body of the wrong shape, where `bison.sender_emails`
refuses and `providers.mapping` raises. A silent empty here is a claim about the
provider ("no campaign of that id exists") made out of our own inability to read
the answer.

And it was the only EmailBison reader that never asserted tenancy, on the check
whose own failure message raises the possibility of a wrong workspace.

Every test here drives the real `request` through the transport seam. Nothing
reaches a network.
"""
import os
import unittest

from src import mapping
from src import providers


class Wire:
    """A paginated `/campaigns` endpoint. Records what was asked for."""

    def __init__(self, pages, total=None, last_page=None, body=None,
                 per_page=15):
        self.pages = pages
        self.total = sum(len(p) for p in pages) if total is None else total
        self.last_page = len(pages) if last_page is None else last_page
        self.per_page = per_page
        self.body = body
        self.urls = []

    def __call__(self, method, url, headers, payload=None, timeout=None):
        self.urls.append(url)
        if self.body is not None:
            return 200, self.body
        page = 1
        if "page=" in url:
            page = int(url.rsplit("page=", 1)[-1])
        # Cycles rather than running out, so a pager that never declares an end
        # can be tested without the walk stopping on an empty page.
        rows = self.pages[(page - 1) % len(self.pages)] if self.pages else []
        return 200, {"data": rows,
                     "meta": {"total": self.total, "per_page": self.per_page,
                              "last_page": self.last_page, "current_page": page}}


def campaign(n):
    return {"id": n, "name": f"CLIENT - CAMPAIGN {n}", "status": "active"}


def paged(count, per_page=15):
    rows = [campaign(i) for i in range(1, count + 1)]
    return [rows[i:i + per_page] for i in range(0, len(rows), per_page)] or [[]]


class PagedTest(unittest.TestCase):
    def wire(self, w):
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        before = os.environ.get("BISON_KEY")
        os.environ["BISON_KEY"] = "test-key-not-real"

        def restore():
            if before is None:
                os.environ.pop("BISON_KEY", None)
            else:
                os.environ["BISON_KEY"] = before
        self.addCleanup(restore)
        return w


class EveryPageIsRead(PagedTest):
    def test_twenty_five_campaigns_over_two_pages_are_all_returned(self):
        """The shape of a real estate: 25 campaigns, 15 to a page."""
        w = self.wire(Wire(paged(25)))
        rows = mapping.bison_campaigns()
        self.assertEqual(len(rows), 25)
        self.assertEqual(len(w.urls), 2)

    def test_a_campaign_past_the_first_page_is_found(self):
        """The defect, as the operator would have met it."""
        self.wire(Wire(paged(25)))
        found = mapping.check_bison(20)
        self.assertEqual(found["state"], mapping.OK, found["detail"])
        self.assertTrue(found["ok"])

    def test_a_campaign_on_the_first_page_still_works(self):
        self.wire(Wire(paged(25)))
        self.assertEqual(mapping.check_bison(3)["state"], mapping.OK)

    def test_an_id_that_really_is_absent_is_still_missing(self):
        """The fix must not turn a wrong id into a pass."""
        self.wire(Wire(paged(25)))
        found = mapping.check_bison(9999)
        self.assertEqual(found["state"], mapping.MISSING)
        self.assertFalse(found["ok"])

    def test_an_empty_estate_is_not_an_error(self):
        self.wire(Wire([[]], total=0, last_page=1))
        self.assertEqual(mapping.bison_campaigns(), [])

    def test_one_page_exactly_is_one_request(self):
        w = self.wire(Wire(paged(15)))
        self.assertEqual(len(mapping.bison_campaigns()), 15)
        self.assertEqual(len(w.urls), 1)

    def test_every_request_is_a_get(self):
        w = self.wire(Wire(paged(25)))
        mapping.bison_campaigns()
        self.assertTrue(all("/campaigns" in u for u in w.urls))


class AShortOrUnreadableAnswerIsRefused(PagedTest):
    def test_a_total_larger_than_what_arrived_raises(self):
        """A short read makes a real campaign look like a wrong id."""
        self.wire(Wire([paged(25)[0]], total=25, last_page=1))
        with self.assertRaises(providers.ProviderError) as caught:
            mapping.bison_campaigns()
        self.assertIn("15", str(caught.exception))
        self.assertIn("25", str(caught.exception))

    def test_a_body_that_is_not_an_object_raises(self):
        self.wire(Wire([], body=["not", "an", "envelope"]))
        with self.assertRaises(providers.ProviderError):
            mapping.bison_campaigns()

    def test_a_body_with_no_data_array_raises(self):
        self.wire(Wire([], body={"meta": {"total": 3}}))
        with self.assertRaises(providers.ProviderError) as caught:
            mapping.bison_campaigns()
        self.assertIn("not a provider with no campaigns",
                      str(caught.exception))

    def test_a_refusal_reaches_check_bison_as_unknown_not_missing(self):
        """"We could not read it" must never read as "it is not there"."""
        self.wire(Wire([], body={"meta": {}}))
        found = mapping.check_bison(20)
        self.assertEqual(found["state"], mapping.UNKNOWN)
        self.assertFalse(found["ok"])

    def test_an_unbounded_pager_is_refused_rather_than_crawled(self):
        """A `last_page` that never arrives must not become a crawl."""
        endless = Wire(paged(30), total=10 ** 9, last_page=10 ** 9)
        self.wire(endless)
        with self.assertRaises(providers.ProviderError) as caught:
            mapping.bison_campaigns(max_pages=3)
        self.assertIn("partial read", str(caught.exception))
        self.assertEqual(len(endless.urls), 3)


class TheTenancyAssertionIsAvailable(PagedTest):
    """This was the one EmailBison reader that never asserted its tenant, on
    the check whose MISSING message raises a wrong workspace as the cause."""

    def test_a_workspace_may_be_pinned(self):
        from unittest import mock
        self.wire(Wire(paged(25)))
        with mock.patch.object(mapping.bison, "require_workspace") as guard:
            mapping.bison_campaigns(expect_workspace=10)
        guard.assert_called_once_with(10)

    def test_an_unpinned_read_asserts_nothing(self):
        """Unpinned stays unpinned: a default would assert an ownership this
        module cannot prove, which is `bison.require_workspace`'s own rule."""
        from unittest import mock
        self.wire(Wire(paged(25)))
        with mock.patch.object(mapping.bison, "require_workspace") as guard:
            mapping.bison_campaigns()
        guard.assert_not_called()

    def test_a_mismatched_workspace_stops_the_read(self):
        from unittest import mock
        w = self.wire(Wire(paged(25)))
        with mock.patch.object(mapping.bison, "require_workspace",
                               side_effect=mapping.bison.WorkspaceMismatch("29")):
            with self.assertRaises(mapping.bison.WorkspaceMismatch):
                mapping.bison_campaigns(expect_workspace=10)
        self.assertEqual(w.urls, [], "it read pages before checking the tenant")


if __name__ == "__main__":
    unittest.main()
