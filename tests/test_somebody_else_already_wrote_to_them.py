"""The confirmed-touch model cannot see what somebody else already sent.

MEASURED, NOT SUPPOSED. On 2026-09-09 the two contacts selected for the
Productive one-person canary were looked up in the client's own live EmailBison
workspace for the first time. One had received 21 emails across three campaigns
with no reply. The other had received four and was `in_sequence` - being worked
at that moment.

`work/queue.jsonl` said zero confirmed touches for both, and it was right about
what THIS system had done. The client's estate had been working the same list
for months. A sweep of all fifty pilot accounts found 8 clear, 21 touched and
20 with somebody mid-sequence.

The real domains are deliberately not named here. `tests/test_fixture_hygiene.py`
forbids a real client or prospect domain anywhere under `tests/`, because
fixtures live in git for ever, and prospect domains are exactly what it
protects. The specifics are in PRODUCT-GAPS, which is out of its scope.

So this is not a second suppression list. `hygiene` owns suppression over state
we wrote; the confirmed-touch model owns what we sent. Neither can answer "what
has somebody else already done from this account", and that is the question
that decides whether a canary is a first touch or a fifth.

THE SEARCH IS THE HARD PART, and getting it wrong fails open. Probed against
the live five-figure estate:

    ?email=<addr>          ignored, returns the whole estate
    ?filter[email]=<addr>  ignored, returns the whole estate
    ?q=<term>              ignored, returns the whole estate
    ?search=<bare label>   exact: 3 for an account with three leads, 0 for one
                           with none
    ?search=<label.tld>    a five-figure row count - a term containing a dot breaks it, and
                           returns the SAME a five-figure row count for an account that has no
                           leads at all

A check written as "search the address; zero results means clear" would have
called every account clear on a broad match. So the label is searched, the
address is matched locally, and a response that looks broad rather than
filtered refuses to answer at all.
"""
import unittest

from src import collision, providers
from src.providers import bison

WS = 10          # the workspace every read in this file is pinned to


def lead(email, sent=0, statuses=(), lead_status="unverified"):
    return {
        "id": abs(hash(email)) % 100000,
        "email": email,
        "status": lead_status,
        "overall_stats": {"emails_sent": sent, "replies": 0, "opens": 0},
        "lead_campaign_data": [
            {"campaign_id": 300 + i, "status": s, "emails_sent": sent,
             "replies": 0, "opens": 0, "interested": False}
            for i, s in enumerate(statuses)],
        "created_at": "2026-04-08T18:33:00.000000Z",
    }


class Wire:
    """Serves one page set, and records the search terms it was asked for."""

    def __init__(self, rows, total=None):
        self.rows = rows
        self.total = len(rows) if total is None else total
        self.terms = []

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        if bison.USERS_PATH in url:
            # Every read asserts the binding first, so the wire has to answer
            # it. That assertion is the point of TheEstateMustBeNamed below.
            return 200, {"data": {"workspace": {"id": WS, "name": "TESTWS"}}}
        if "search=" in url:
            self.terms.append(url.split("search=")[1].split("&")[0])
        return 200, {"data": self.rows,
                     "meta": {"current_page": 1, "last_page": 1,
                              "per_page": 15, "total": self.total}}


class TheSearchTermIsTheLabelNotTheDomain(unittest.TestCase):
    def test_the_tld_is_stripped(self):
        self.assertEqual(collision.search_term("acmeagency.example"),
                         "acmeagency")
        self.assertEqual(collision.search_term("northwind.test"), "northwind")
        self.assertEqual(collision.search_term("belmont.invalid"), "belmont")

    def test_a_multi_label_domain_uses_the_first_label(self):
        self.assertEqual(collision.search_term("example.co.uk"), "example")

    def test_an_address_is_reduced_to_its_domain_label(self):
        self.assertEqual(collision.search_term("a@acmeagency.example"),
                         "acmeagency")

    def test_the_dotted_form_is_never_what_gets_sent(self):
        wire = Wire([lead("a@example.test")])
        providers.set_transport(wire)
        self.addCleanup(providers.reset_transport)
        collision.leads_for_domain("example.test", expect_workspace=WS)
        self.assertEqual(wire.terms, ["example"])
        for term in wire.terms:
            self.assertNotIn(".", term)


class ABroadMatchIsNotACleanSheet(unittest.TestCase):
    """The failure that would have mattered most: absence read from noise."""

    def wire(self, rows, total):
        w = Wire(rows, total=total)
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        return w

    def test_a_four_figure_result_refuses_rather_than_answering(self):
        self.wire([lead("someone@unrelated.test")], total=12345)
        with self.assertRaises(collision.CollisionUnknown):
            collision.leads_for_domain("example.test", expect_workspace=WS)

    def test_the_refusal_says_a_search_that_ignores_its_term_proves_nothing(self):
        self.wire([lead("someone@unrelated.test")], total=12345)
        try:
            collision.leads_for_domain("example.test", expect_workspace=WS)
        except collision.CollisionUnknown as e:
            self.assertIn("cannot prove absence", str(e))

    def test_unknown_is_never_reported_as_clear(self):
        """The whole point. These two answers must not collapse."""
        self.wire([lead("someone@unrelated.test")], total=12345)
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_address("a@example.test", expect_workspace=WS)

    def test_a_provider_error_is_unknown_not_clear(self):
        class Broken:
            """The binding answers; the LEAD read is what breaks."""

            def __call__(self, method, url, headers=None, body=None,
                         timeout=None):
                if bison.USERS_PATH in url:
                    return 200, {"data": {"workspace": {"id": WS, "name": "T"}}}
                return 500, {"error": "boom"}

        providers.set_transport(Broken())
        self.addCleanup(providers.reset_transport)
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_address("a@example.test", expect_workspace=WS)

    def test_a_missing_data_array_is_unknown_not_clear(self):
        class NoData:
            """The binding answers; the lead page has no `data` array."""

            def __call__(self, method, url, headers=None, body=None,
                         timeout=None):
                if bison.USERS_PATH in url:
                    return 200, {"data": {"workspace": {"id": WS, "name": "T"}}}
                return 200, {"meta": {"total": 0}}

        providers.set_transport(NoData())
        self.addCleanup(providers.reset_transport)
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_address("a@example.test", expect_workspace=WS)


class ANeighboursLeadIsNotThisAccountsLead(unittest.TestCase):
    """A label search matched a DIFFERENT company whose name shares the prefix,
    and it happened on the real estate. Reporting that as prior contact would
    hold an account nobody has touched."""

    def test_rows_at_another_domain_are_dropped(self):
        wire = Wire([lead("robin@acmecreations.example", sent=5),
                     lead("real@acmeagency.example", sent=2)])
        providers.set_transport(wire)
        self.addCleanup(providers.reset_transport)
        rows = collision.leads_for_domain("acmeagency.example", expect_workspace=WS)
        self.assertEqual([r["email"] for r in rows], ["real@acmeagency.example"])

    def test_an_account_with_only_a_neighbour_match_is_clear(self):
        providers.set_transport(
            Wire([lead("robin@acmecreations.example", sent=5)]))
        self.addCleanup(providers.reset_transport)
        self.assertEqual(
            collision.check_account("acmeagency.example", expect_workspace=WS)["verdict"],
            collision.CLEAR)


class TheThreeVerdicts(unittest.TestCase):
    def wire(self, rows):
        providers.set_transport(Wire(rows))
        self.addCleanup(providers.reset_transport)

    def test_no_lead_at_the_address_is_clear(self):
        self.wire([lead("other@example.test", sent=9)])
        verdict, detail = collision.check_address("target@example.test", expect_workspace=WS)
        self.assertEqual(verdict, collision.CLEAR)
        self.assertIn("no lead at this address", detail["note"])

    def test_a_lead_that_has_been_emailed_is_touched(self):
        self.wire([lead("target@example.test", sent=21,
                        statuses=("sequence_finished",))])
        verdict, detail = collision.check_address("target@example.test", expect_workspace=WS)
        self.assertEqual(verdict, collision.TOUCHED)
        self.assertEqual(detail["emails_sent"], 21)

    def test_a_lead_mid_sequence_is_reported_as_such(self):
        """The sharper fact. `touched` is history; `in_sequence` is now."""
        self.wire([lead("target@example.test", sent=4,
                        statuses=("in_sequence",))])
        verdict, _ = collision.check_address("target@example.test", expect_workspace=WS)
        self.assertEqual(verdict, collision.IN_SEQUENCE)

    def test_a_lead_loaded_but_never_sent_to_is_still_not_clear(self):
        """Somebody has this person queued. That is not nothing."""
        self.wire([lead("target@example.test", sent=0, statuses=("stopped",))])
        verdict, detail = collision.check_address("target@example.test", expect_workspace=WS)
        self.assertEqual(verdict, collision.TOUCHED)
        self.assertIn("nothing sent yet", detail["note"])

    def test_an_unparseable_address_is_refused(self):
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_address("not-an-address", expect_workspace=WS)


class TheAccountVerdictCoversColleagues(unittest.TestCase):
    """Outreach here is account-based, so a colleague mid-sequence is a fact
    about the company even when the person we picked is untouched. That is
    exactly what the live sweep found at one qualified account: the selected
    contact had no lead at all, and two colleagues were in an active
    campaign - so the person was clear and the account was not."""

    def wire(self, rows):
        providers.set_transport(Wire(rows))
        self.addCleanup(providers.reset_transport)

    def test_a_colleague_in_sequence_makes_the_account_in_sequence(self):
        self.wire([lead("colleague@example.test", sent=5,
                        statuses=("in_sequence",))])
        found = collision.check_account("example.test", expect_workspace=WS)
        self.assertEqual(found["verdict"], collision.IN_SEQUENCE)
        self.assertTrue(found["anyone_in_sequence"])

    def test_the_person_can_be_clear_while_the_account_is_not(self):
        self.wire([lead("colleague@example.test", sent=5,
                        statuses=("in_sequence",))])
        verdict, _ = collision.check_address("target@example.test", expect_workspace=WS)
        self.assertEqual(verdict, collision.CLEAR)
        self.assertEqual(collision.check_account("example.test", expect_workspace=WS)["verdict"],
                         collision.IN_SEQUENCE)

    def test_a_bounce_at_the_account_is_surfaced(self):
        """A bounced colleague is a deliverability fact about the domain."""
        self.wire([lead("bad@example.test", sent=1, statuses=("bounced",),
                        lead_status="bounced")])
        self.assertTrue(collision.check_account("example.test", expect_workspace=WS)["any_bounce"])

    def test_an_empty_estate_is_clear_and_says_so(self):
        self.wire([])
        found = collision.check_account("example.test", expect_workspace=10)
        self.assertEqual(found["verdict"], collision.CLEAR)
        self.assertEqual(found["leads"], 0)
        self.assertFalse(found["anyone_in_sequence"])


if __name__ == "__main__":
    unittest.main()


class TheEstateMustBeNamed(unittest.TestCase):
    """The binding moved mid-session, and three reads answered CLEAR.

    On 2026-09-09 this credential was bound to PRODUCTIVE (10) for the sweep
    that found 42 of 50 accounts touched. Later in the same session, with
    nothing changed on this side, `GET /api/users` reported Bluewave (29) -
    the active workspace is chosen in the vendor's UI. Three prior-contact
    reads taken after that answered CLEAR against Bluewave's empty estate.

    The guard was already there. It was optional, and an optional guard on this
    path is a guard that gets skipped. So `expect_workspace` has no default:
    naming the estate is part of asking the question.
    """

    def setUp(self):
        providers.set_transport(Wire([]))
        self.addCleanup(providers.reset_transport)

    def test_an_unpinned_account_check_is_refused(self):
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_account("example.test")

    def test_an_unpinned_address_check_is_refused(self):
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_address("a@example.test")

    def test_an_unpinned_lead_read_is_refused(self):
        with self.assertRaises(collision.CollisionUnknown):
            collision.leads_for_domain("example.test")

    def test_the_refusal_says_why_an_unpinned_read_cannot_answer(self):
        try:
            collision.check_account("example.test")
        except collision.CollisionUnknown as e:
            self.assertIn("whose estate", str(e))

    def test_no_provider_call_is_made_on_an_unpinned_read(self):
        """Refused before the wire, not after."""
        wire = Wire([])
        providers.set_transport(wire)
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_account("example.test")
        self.assertEqual(wire.terms, [])

    def test_a_pinned_read_proceeds(self):
        found = collision.check_account("example.test", expect_workspace=10)
        self.assertEqual(found["verdict"], collision.CLEAR)

    def test_every_answer_names_the_estate_it_was_read_against(self):
        """A verdict without its workspace is unreadable a day later."""
        found = collision.check_account("example.test", expect_workspace=10)
        self.assertEqual(found["workspace"], 10)
