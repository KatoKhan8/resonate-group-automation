"""A client-facing role is not shown the vendor stack.

`api.DIMENSIONS` includes `mx_provider`, `mx_category`, `email_source` and
`verifier`. A dropdown listing those names every supplier in the pipeline, and
a breakdown screen is an odd place to disclose who we buy from. So
`app._dimensions` narrows to `CLIENT_DIMENSIONS` for anyone without
`operations.view`, and a dimension outside the list falls back rather than
being honoured.

Both halves were correct and neither was tested: the mutation audit's
"let a client-facing role reach the vendor dimensions" - which replaces the
whole branch with `return api.DIMENSIONS` - was not caught by
`tests.test_web_app`. Two screens take the narrowed list, `/reporting` and
`/compare`, and `/compare` is reachable at `reporting.view`, which the
client-facing viewer holds.

The forged-dimension test is the one that matters. Narrowing a dropdown is
presentation; refusing the value when somebody types it into the query string
is the actual control.
"""
import unittest

from src.web import api
from tests.webbase import WebTest

VENDOR = ("mx_provider", "mx_category", "email_source", "verifier")
CLIENT = "client@productive.test"
OPERATOR = "ops@productive.test"


class TheVendorStackIsNotClientFacing(WebTest):

    def setUp(self):
        self.client = self.signin(CLIENT)
        self.operator = self.signin(OPERATOR)

    def named_in(self, session, path):
        status, body, _ = session.get(path)
        self.assertEqual(status, 200, path)
        return [d for d in VENDOR if d in body]

    # ------------------------------------------------------- the narrowing

    def test_the_two_lists_actually_differ(self):
        """If they were equal every assertion below would pass on nothing."""
        for name in VENDOR:
            self.assertIn(name, [d for d, _ in api.DIMENSIONS])
            self.assertNotIn(name, [d for d, _ in api.CLIENT_DIMENSIONS])

    def test_a_viewer_is_not_offered_a_vendor_dimension_on_reporting(self):
        self.assertEqual(self.named_in(self.client, "/reporting"), [])

    def test_a_viewer_is_not_offered_one_on_compare_either(self):
        """`/compare` sits at reporting.view, which the viewer holds."""
        self.assertEqual(self.named_in(self.client, "/compare"), [])

    def test_an_operator_still_gets_them(self):
        """Otherwise the narrowing hides them from everybody and proves
        nothing about the boundary."""
        self.assertEqual(sorted(self.named_in(self.operator, "/reporting")),
                         sorted(VENDOR))

    # ---------------------------------------------------------- the control

    def test_a_viewer_naming_a_vendor_dimension_is_not_honoured(self):
        """The dropdown is presentation. This is the control."""
        for name in VENDOR:
            status, body, _ = self.client.get("/compare?dimension=" + name)
            self.assertEqual(status, 200)
            self.assertNotIn(name, body,
                             f"{name} was honoured when it was asked for")

    def test_the_same_on_reporting(self):
        for name in VENDOR:
            status, body, _ = self.client.get("/reporting?dimension=" + name)
            self.assertEqual(status, 200)
            self.assertNotIn(name, body)


if __name__ == "__main__":
    unittest.main()
