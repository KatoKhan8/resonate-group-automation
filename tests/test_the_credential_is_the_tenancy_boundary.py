"""EmailBison tenancy: the credential is the boundary, and it is asserted.

WHY A PARAMETER WOULD BE WORSE THAN NONE. Every EmailBison list route accepts
`workspace_id` and discards it. Probed read-only: `?workspace_id=10`,
`?workspace_id=3` and `?workspace_id=999` all answer 200 with byte-identical
rows, and the answer for a workspace that does not exist is the same as the
answer for the one that does. Six query forms and eight header forms were
tried. None scopes anything.

So an argument named after tenancy would be a scope somebody believes they set.
There is no such argument on this module and `scope()` says so out loud.

WHY ASSERTING IT MATTERS MORE THAN DOCUMENTING IT. Between 2026-09-07 and
2026-09-08 the same credential answered for four different estates with nothing
changing on this side: 51 inboxes, then 225, then 32 Greenfield, then 32
Bluewave. The active workspace is chosen in the vendor's UI. A read that does
not assert its binding is a read whose tenancy is whatever somebody last
clicked - and the full inbox inventory and the whole-estate prior-contact check
are both attributed to a client.

Hence `require_workspace`, called before the first page rather than after the
last: an inventory attributed to the wrong workspace is worse the more complete
it is.
"""
import unittest

from src import collision, providers
from src.providers import bison

PRODUCTIVE = {"data": {"workspace": {"id": 10, "name": "PRODUCTIVE"}}}
GREENFIELD = {"data": {"workspace": {"id": 3, "name": "Greenfield"}}}


class Wire:
    """Answers the binding route one way and every other route with rows."""

    def __init__(self, binding, rows=None):
        self.binding = binding
        self.rows = rows if rows is not None else []
        self.paths = []

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        self.paths.append(url)
        if bison.USERS_PATH in url:
            return 200, self.binding
        return 200, {"data": self.rows,
                     "meta": {"current_page": 1, "last_page": 1,
                              "per_page": 15, "total": len(self.rows)}}


def inbox(ident):
    return {"id": ident, "email": f"a{ident}@example.test",
            "status": "Connected", "type": "custom", "daily_limit": 15,
            "warmup_enabled": False, "emails_sent_count": 100,
            "bounced_count": 0, "tags": []}


class TheScopeIsStatedRatherThanInferred(unittest.TestCase):
    def test_the_boundary_is_the_credential(self):
        self.assertEqual(bison.scope()["kind"], bison.WORKSPACE_SCOPE)
        self.assertEqual(bison.WORKSPACE_SCOPE, "credential_bound")

    def test_there_is_no_workspace_parameter_and_it_says_why(self):
        found = bison.scope()
        self.assertIsNone(found["parameter"])
        self.assertIn("discards it", found["why"])

    def test_no_public_function_takes_a_workspace_id(self):
        """The rule, asserted over signatures rather than over prose.

        A parameter the provider ignores is a scope somebody will believe they
        set, so it must not exist - not on a reader added later either.
        """
        import inspect
        for name, fn in vars(bison).items():
            if name.startswith("_") or not inspect.isfunction(fn):
                continue
            params = inspect.signature(fn).parameters
            self.assertNotIn("workspace_id", params,
                             f"{name} takes a workspace_id the provider ignores")


class AnIgnoredParameterCannotCreateFalseSafety(unittest.TestCase):
    """The trap, reproduced: the provider answers the same for any id."""

    def test_the_provider_answers_identically_for_a_nonexistent_workspace(self):
        wire = Wire(PRODUCTIVE, rows=[inbox(1), inbox(2)])
        providers.set_transport(wire)
        self.addCleanup(providers.reset_transport)
        first, _ = bison.sender_emails()
        # Whatever a caller appended, the rows are the same rows - which is why
        # no argument here can be trusted to scope.
        second, _ = bison.sender_emails()
        self.assertEqual([r["id"] for r in first], [r["id"] for r in second])

    def test_the_binding_route_is_what_settles_it(self):
        wire = Wire(PRODUCTIVE, rows=[inbox(1)])
        providers.set_transport(wire)
        self.addCleanup(providers.reset_transport)
        bison.sender_emails(expect_workspace=10)
        self.assertTrue(any(bison.USERS_PATH in p for p in wire.paths))


class TheWrongClientCannotReuseACredential(unittest.TestCase):
    def wire(self, binding, rows=None):
        w = Wire(binding, rows=rows)
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        return w

    def test_a_greenfield_binding_refuses_a_productive_read(self):
        self.wire(GREENFIELD, rows=[inbox(1)])
        with self.assertRaises(bison.WorkspaceMismatch):
            bison.sender_emails(expect_workspace=10)

    def test_the_refusal_names_both_workspaces(self):
        self.wire(GREENFIELD)
        try:
            bison.require_workspace(10)
        except bison.WorkspaceMismatch as e:
            self.assertIn("3", str(e))
            self.assertIn("Greenfield", str(e))
            self.assertIn("10", str(e))

    def test_the_refusal_says_why_it_cannot_be_fixed_afterwards(self):
        self.wire(GREENFIELD)
        try:
            bison.require_workspace(10)
        except bison.WorkspaceMismatch as e:
            self.assertIn("cannot be corrected after the fact", str(e))

    def test_the_matching_binding_passes_and_returns_it(self):
        self.wire(PRODUCTIVE)
        self.assertEqual(bison.require_workspace(10)["name"], "PRODUCTIVE")

    def test_an_id_given_as_a_string_still_matches(self):
        self.wire(PRODUCTIVE)
        self.assertEqual(bison.require_workspace("10")["id"], 10)

    def test_unpinned_asks_nothing_and_asserts_nothing(self):
        """A guard, not a getter.

        The first version called the binding route on every read, which made an
        unpinned inventory read depend on `/users` and fail without it. And
        unpinned must not default to 10: `replywatch.pinned_workspace` gives
        the reason - a default asserts ownership this module cannot prove.
        """
        wire = self.wire(GREENFIELD)
        self.assertIsNone(bison.require_workspace(None))
        self.assertEqual(wire.paths, [], "an unpinned guard called the wire")

    def test_an_unpinned_read_needs_no_binding_route(self):
        """The regression this caused: 25 suite errors, from a guard that
        turned a working read into one that depends on another route."""
        class OnlyRows:
            def __init__(self):
                self.paths = []

            def __call__(self, method, url, headers=None, body=None,
                         timeout=None):
                self.paths.append(url)
                if bison.USERS_PATH in url:
                    return 200, {"data": {}}      # no workspace object
                return 200, {"data": [inbox(1)],
                             "meta": {"last_page": 1, "total": 1,
                                      "per_page": 15, "current_page": 1}}

        wire = OnlyRows()
        providers.set_transport(wire)
        self.addCleanup(providers.reset_transport)
        rows, _ = bison.sender_emails()
        self.assertEqual(len(rows), 1)
        self.assertEqual([p for p in wire.paths if bison.USERS_PATH in p], [])


class TheReadIsRefusedBeforeItHappens(unittest.TestCase):
    """Not alongside, and not after. A partial read of the wrong estate is
    still a read of the wrong estate."""

    def wire(self, binding, rows=None):
        w = Wire(binding, rows=rows)
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        return w

    def test_no_inventory_page_is_fetched_on_a_mismatch(self):
        wire = self.wire(GREENFIELD, rows=[inbox(1)])
        with self.assertRaises(bison.WorkspaceMismatch):
            bison.sender_emails(expect_workspace=10)
        self.assertEqual([p for p in wire.paths
                          if bison.SENDER_EMAILS_PATH in p], [])

    def test_no_lead_page_is_fetched_on_a_mismatch(self):
        wire = self.wire(GREENFIELD)
        with self.assertRaises(bison.WorkspaceMismatch):
            collision.leads_for_domain("example.test", expect_workspace=10)
        self.assertEqual([p for p in wire.paths
                          if collision.LEADS_PATH in p], [])

    def test_a_prior_contact_check_binds_too(self):
        """The most dangerous one to get wrong: a clear verdict from the wrong
        estate would clear somebody a colleague is mid-sequence with."""
        self.wire(GREENFIELD)
        with self.assertRaises(bison.WorkspaceMismatch):
            collision.check_address("a@example.test", expect_workspace=10)

    def test_a_matching_binding_lets_the_read_proceed(self):
        self.wire(PRODUCTIVE, rows=[inbox(1)])
        rows, meta = bison.sender_emails(expect_workspace=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta["total"], 1)

    def test_the_mismatch_is_a_provider_error_so_callers_handle_it(self):
        self.assertTrue(issubclass(bison.WorkspaceMismatch,
                                   providers.ProviderError))


if __name__ == "__main__":
    unittest.main()
