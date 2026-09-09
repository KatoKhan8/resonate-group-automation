"""A paginated endpoint answered a question about totals with one page.

WHAT HAPPENED. `GET /sender-emails` was read, `response["data"]` held fifteen
rows, and the Productive estate was reported as fifteen inboxes. The operator
said 225. Both were looking at the same response: `meta.per_page` was 15 and
`meta.last_page` was 15. Fifteen was the page size. 15 x 15 = 225.

Nothing was wrong with the API and nothing was wrong with the credential. The
read looked at `data` and never at the envelope - and there was no adapter
function to look at it for anyone, because the route had only ever been probed
by hand.

WHY IT MATTERS MORE THAN AN OFF-BY-FOURTEEN. An inventory is what capacity gets
planned against. Fifteen inboxes at fifteen a day is 225 sends; 225 inboxes is
3,375. A short read does not look like a failure, it looks like a small
estate - and it would have been used to size a pilot cap, a warmup ramp and a
per-sender allocation.

So `bison.sender_emails` reads `meta` first, walks every page, and refuses to
return a list shorter than `meta.total` says exists.
"""
import os
import unittest

from src import providers
from src.providers import bison


class Wire:
    """Serves pages, and records what was asked for."""

    def __init__(self, pages, total=None, per_page=15):
        self.pages = pages
        self.total = total if total is not None else sum(len(p) for p in pages)
        self.per_page = per_page
        self.calls = []

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url})
        page = 1
        if "page=" in url:
            page = int(url.split("page=")[1].split("&")[0])
        index = page - 1
        rows = self.pages[index] if 0 <= index < len(self.pages) else []
        return 200, {
            "data": rows,
            "meta": {"current_page": page, "last_page": len(self.pages),
                     "per_page": self.per_page, "total": self.total},
            "links": {},
        }


def inbox(ident, **over):
    row = {"id": ident, "email": f"a{ident}@example.test",
           "status": "Connected", "type": "custom", "daily_limit": 15,
           "warmup_enabled": True, "emails_sent_count": 500,
           "bounced_count": 1, "tags": []}
    row.update(over)
    return row


def paged(count, per_page=15):
    rows = [inbox(i) for i in range(1, count + 1)]
    return [rows[i:i + per_page] for i in range(0, len(rows), per_page)]


def fake_key():
    """A placeholder credential for the duration of one test.

    These tests stub the transport, so no call leaves the machine - but they
    used to reach `providers.key()` with nothing set, which read the operator's
    real `config/.env`. The suite-wide firewall in `tests/__init__.py` now makes
    that a loud `MissingKey` instead of a silent real credential, so a test that
    needs a key has to say so.
    """
    import contextlib

    @contextlib.contextmanager
    def _fake():
        before = os.environ.get("BISON_KEY")
        os.environ["BISON_KEY"] = "test-key-not-real"
        try:
            yield
        finally:
            if before is None:
                os.environ.pop("BISON_KEY", None)
            else:
                os.environ["BISON_KEY"] = before
    return _fake()


class EveryPageIsRead(unittest.TestCase):
    def setUp(self):
        self._real = providers._transport if hasattr(providers, "_transport") else None

    def wire(self, pages, **kw):
        w = Wire(pages, **kw)
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        keyed = fake_key()
        keyed.__enter__()
        self.addCleanup(keyed.__exit__, None, None, None)
        return w

    def test_fifteen_pages_of_fifteen_is_two_hundred_and_twenty_five(self):
        """The exact shape of the real workspace."""
        self.wire(paged(225))
        rows, meta = bison.sender_emails()
        self.assertEqual(len(rows), 225)
        self.assertEqual(meta["total"], 225)
        self.assertEqual(meta["per_page"], 15)

    def test_it_asked_for_every_page(self):
        wire = self.wire(paged(225))
        bison.sender_emails()
        asked = sorted(int(c["url"].split("page=")[1].split("&")[0])
                       for c in wire.calls)
        self.assertEqual(asked, list(range(1, 16)))

    def test_one_page_is_still_one_call(self):
        wire = self.wire(paged(9))
        rows, _ = bison.sender_emails()
        self.assertEqual(len(rows), 9)
        self.assertEqual(len(wire.calls), 1)

    def test_an_empty_estate_is_not_an_error(self):
        self.wire([[]], total=0)
        rows, meta = bison.sender_emails()
        self.assertEqual(rows, [])
        self.assertEqual(meta["total"], 0)

    def test_every_call_is_a_get(self):
        wire = self.wire(paged(30))
        bison.sender_emails()
        self.assertEqual({c["method"] for c in wire.calls}, {"GET"})


class AShortReadIsRefused(unittest.TestCase):
    """The guard. Returning what arrived is the defect, not the fallback."""

    def wire(self, w):
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        keyed = fake_key()
        keyed.__enter__()
        self.addCleanup(keyed.__exit__, None, None, None)
        return w

    def test_a_total_larger_than_what_arrived_raises(self):
        # One page of 15, but the envelope says there are 225.
        self.wire(Wire([paged(225)[0]], total=225))
        with self.assertRaises(bison.PartialInventory):
            bison.sender_emails()

    def test_the_refusal_names_both_numbers(self):
        self.wire(Wire([paged(225)[0]], total=225))
        try:
            bison.sender_emails()
        except bison.PartialInventory as e:
            self.assertIn("225", str(e))
            self.assertIn("15", str(e))
        else:
            self.fail("a short inventory was returned as if whole")

    def test_the_refusal_says_why_it_matters(self):
        self.wire(Wire([paged(225)[0]], total=225))
        try:
            bison.sender_emails()
        except bison.PartialInventory as e:
            self.assertIn("capacity", str(e))

    def test_it_is_a_provider_error_so_callers_already_handle_it(self):
        self.assertTrue(issubclass(bison.PartialInventory,
                                   providers.ProviderError))

    def test_a_missing_data_array_is_not_an_empty_estate(self):
        class NoData:
            def __call__(self, method, url, headers=None, body=None,
                         timeout=None):
                return 200, {"meta": {"total": 225}}

        self.wire(NoData())
        with self.assertRaises(providers.ProviderError) as caught:
            bison.sender_emails()
        self.assertIn("refusing", str(caught.exception))

    def test_a_non_dict_response_is_refused(self):
        class Listy:
            def __call__(self, method, url, headers=None, body=None,
                         timeout=None):
                return 200, [inbox(1)]

        self.wire(Listy())
        with self.assertRaises(providers.ProviderError):
            bison.sender_emails()

    def test_a_missing_last_page_stops_after_one_page(self):
        """No `last_page` to walk to. One page is all the response claims."""
        class OnePage:
            def __init__(self):
                self.calls = 0

            def __call__(self, method, url, headers=None, body=None,
                         timeout=None):
                self.calls += 1
                return 200, {"data": [inbox(1)], "meta": {}}

        wire = self.wire(OnePage())
        rows, _ = bison.sender_emails()
        self.assertEqual(len(rows), 1)
        self.assertEqual(wire.calls, 1)


class TheRouteStaysReadOnly(unittest.TestCase):
    def test_the_path_is_the_documented_one(self):
        self.assertEqual(bison.SENDER_EMAILS_PATH, "/sender-emails")

    def test_the_reader_is_not_on_a_write_path(self):
        """Only the GET assertion above is this file's business.

        `tests/test_invariants.py` already forbids a mutation-shaped public
        FUNCTION name on this module, and it scopes the rule to callables -
        which is the right scope, because `SENDER_EMAILS_PATH` contains the
        substring "send" and is a constant naming a read route. A second,
        cruder copy of that rule here failed on exactly that.
        """
        self.assertTrue(callable(bison.sender_emails))
        self.assertNotIn(bison.SENDER_EMAILS_PATH,
                         (bison.leads_endpoint("1"),))


if __name__ == "__main__":
    unittest.main()
