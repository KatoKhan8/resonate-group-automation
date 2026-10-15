"""The provider-write log, and the four different nothings it must tell apart.

WHAT THIS FILE IS FOR. `/admin` renders "No provider call has been made. This
build does not make one from any surface" whenever `api.provider_health`'s list
is empty - and that list walks `waterfall.ledger(rec)`, the per-record paid-
enrichment ledger, which cannot record a provider WRITE. Writes go to
`work/provider-writes.jsonl`, and before this page nothing under `src/web/`
read that file. So the one surface that could contradict the sentence did not
exist.

The invariant under test is therefore NOT "the page exists" and NOT the text of
any docstring - a test that greps source fails when somebody writes a comment,
which is this repository's own named anti-pattern. It is the BEHAVIOUR the
sentence got wrong: **an absence must not be rendered as a zero, and an
unreadable authority must not be rendered as clean.** Four states, four
different answers:

    the file is not there        -> no row has been RECORDED, which is weaker
                                    than no write having happened
    the file cannot be read      -> UNKNOWN, and never a zero
    the file is there and empty  -> no rows
    the file has rows            -> the rows, each saying what it proves

NOTHING HERE REACHES A PROVIDER OR A NETWORK. No transport is called, patched
or imported: every row in every fixture is a line this test writes into a
throwaway file with `json.dumps`. The only socket in play is the loopback
listener `tests/webbase.WebTest` owns, on an ephemeral port - never 8765-8799 -
and no page was looked at by a human while writing this.
"""
import hashlib
import json
import os
import tempfile
import unittest

from src import providerwrites, repo as repo_module, workspaces as ws
from src.web import api, pages
from src.web.app import permission_for
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
ADMIN = "admin@productive.test"

PATH = "/provider-writes"

# The tenant `providerwrites.perform` is handed is `campaign["client"]`, and
# the demo workspace `productive` has client `productive`. Asserted in setUp
# rather than trusted, because the whole scoping argument rests on it.
MINE = "productive"
SOMEBODY_ELSE = "contactout"


def a_row(outcome="accepted", at="2026-10-15T20:00:00Z", operation="bison.pause",
          tenant=MINE, campaign="C1", by="ops@productive.test", detail=""):
    """One ledger row in the exact shape `providerwrites._ledger` writes.

    Nine keys, named here so that a change to that writer's shape shows up as
    a failure in this file rather than as a quietly empty column on the page.
    """
    return {"at": at, "operation": operation, "outcome": outcome,
            "campaign": campaign, "tenant": tenant, "by": by,
            "detail": detail, "pid": 1234, "argv": ["app.py"]}


class LedgerFixture:
    """Point `providerwrites.ledger_path()` somewhere disposable."""

    def point_the_ledger_at(self, target):
        # The captured value travels WITH the cleanup. One test points the
        # ledger three times, and a `_restore` that re-read an attribute
        # would restore whatever the last call happened to capture - leaving
        # the variable set to a temp path for every test after it.
        self.addCleanup(
            self._restore,
            os.environ.get(providerwrites.PROVIDER_WRITES_LEDGER))
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = target
        # Read back through the module rather than trusting the assignment:
        # the page resolves the path per call and a test that set a variable
        # the code does not read would pass while watching nothing.
        self.assertEqual(providerwrites.ledger_path(), os.path.abspath(target))

    @staticmethod
    def _restore(previous):
        if previous is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = previous

    def write_ledger(self, rows, where=None):
        target = where or os.path.join(
            tempfile.mkdtemp(prefix="rga-plog-"), "provider-writes.jsonl")
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(
                    row if isinstance(row, str)
                    else json.dumps(row, ensure_ascii=False))
                handle.write("\n")
        self.point_the_ledger_at(target)
        return target


class TheFourNothingsAreFourDifferentAnswers(WebTest, LedgerFixture):
    """A missing file, an unreadable file and an empty file are three facts.

    This is the one the estate keeps getting wrong. `store.read_jsonl` returns
    `[]` for a missing file, so a page built on it cannot tell the first two
    apart from the third - which is why this page does not use it.
    """

    def test_an_absent_ledger_is_not_a_zero(self):
        self.point_the_ledger_at(
            os.path.join(tempfile.mkdtemp(prefix="rga-plog-"), "nothing.jsonl"))
        status, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("No ledger file", body)
        # The distinction is the point: it must NOT claim nothing happened.
        self.assertIn("weaker statement", body)
        self.assertNotIn("No rows", body)

    def test_an_unreadable_ledger_is_UNKNOWN_and_never_clean(self):
        """A path that exists and cannot be read.

        A directory, which is the portable way to produce exactly that: it
        exists, so the absent branch is not taken, and `open` raises an
        OSError on every platform this runs on.
        """
        unreadable = tempfile.mkdtemp(prefix="rga-plog-dir-")
        self.point_the_ledger_at(unreadable)
        self.assertTrue(os.path.exists(unreadable), "the premise: it exists")
        status, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("UNKNOWN", body)
        self.assertIn("never a zero", body)
        self.assertNotIn("No rows", body)
        self.assertNotIn("No ledger file", body)

    def test_an_empty_ledger_says_empty_and_not_absent(self):
        self.write_ledger([])
        status, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("No rows", body)
        self.assertNotIn("No ledger file", body)
        self.assertNotIn("never a zero", body)

    def test_the_three_states_render_three_different_pages(self):
        """The control for the three above: they must not all look the same.

        Three assertions that each state contains a string is satisfied by a
        page that contains all three strings always. This is the test that
        says they are exclusive.
        """
        session = self.signin(OPERATOR)
        # ALL THREE SHARE THE SAME BASENAME, and that is the point of this
        # version. The first draft gave them different file names, and the
        # page renders the ledger name - so it passed on an incidental
        # difference, and a mutation collapsing absent into empty did NOT
        # turn it red. A control that can pass for the wrong reason is the
        # defect this file is about, committed in the file itself.
        name_only = "provider-writes.jsonl"
        absent = os.path.join(tempfile.mkdtemp(prefix="rga-plog-"), name_only)
        unreadable = os.path.join(
            tempfile.mkdtemp(prefix="rga-plog-"), name_only)
        os.mkdir(unreadable)
        empty = os.path.join(tempfile.mkdtemp(prefix="rga-plog-"), name_only)
        with open(empty, "w", encoding="utf-8"):
            pass

        seen = {}
        for label, target in (("absent", absent), ("unreadable", unreadable),
                              ("empty", empty)):
            self.point_the_ledger_at(target)
            self.assertEqual(name_only, os.path.basename(target))
            seen[label] = session.get(PATH)[1]
        self.assertEqual(len(set(seen.values())), 3,
                         "two of the three nothings rendered identically: "
                         + ", ".join(sorted(seen)))

    def test_a_damaged_line_is_counted_and_not_dropped(self):
        """A row nobody can parse may be the one recording the write.

        `store.read_jsonl` raises on the first bad line, which loses every
        row in the file including the good ones before it. Dropping it
        silently would be worse: it turns a damaged ledger into a clean one.
        """
        self.write_ledger([a_row(), "{not json at all", a_row(at="2026-10-15T21:00:00Z")])
        status, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("could not be parsed", body)
        # And the readable rows survived rather than being lost with it.
        self.assertIn("bison.pause", body)


class AnOutcomeMeansWhatProviderwritesSaysItMeans(WebTest, LedgerFixture):
    """The outcome column is the only claim on this page, so it is the one
    thing that may not be approximated."""

    def test_the_known_outcomes_are_exactly_the_ones_the_writer_can_write(self):
        """The premise, asserted rather than assumed.

        `_perform` has ONE return statement and it is guarded by
        `if verdict != ACCEPTED: raise WriteUnverified`, so `accepted` is the
        only success class the ledger can hold - which is why `drifted` and
        `unknown` are deliberately absent from this page's table. If
        `providerwrites` ever gains a second successful return, this fails and
        the page gets a new row rather than silently filing it somewhere.
        """
        self.assertEqual(set(api.OUTCOMES),
                         {"refused", "accepted", "unverified", "failed",
                          "performed"})
        # The classifier verdicts are NOT ledger outcomes. If one of these
        # ever becomes one, the page must learn it explicitly.
        for verdict in (providerwrites.DRIFTED, providerwrites.UNKNOWN):
            self.assertNotIn(verdict, api.OUTCOMES,
                             f"{verdict} is now a ledger outcome and the page "
                             f"has not been told what it proves")

    def test_a_refusal_says_the_provider_was_not_reached(self):
        self.write_ledger([a_row(outcome="refused",
                                 detail="bison.pause names campaign 418")])
        _, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertIn("did not reach the provider", body)
        self.assertNotIn("needs a person", body)

    def test_an_unverified_write_needs_a_person_and_is_not_a_success(self):
        """The row that matters most. `providerwrites` says of it: the
        provider may have acted, do NOT retry, settle it by hand."""
        self.write_ledger([a_row(outcome="unverified",
                                 detail="read-back says drifted")])
        _, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertIn("needs a person", body)
        self.assertNotIn("the mandatory read-back agreed", body)

    def test_an_unrecognised_outcome_is_not_filed_into_a_bucket(self):
        """A verb-outcome added to providerwrites later must surface as
        unrecognised rather than landing in whichever bucket is first."""
        self.write_ledger([a_row(outcome="something-new-in-november")])
        _, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertIn("unrecognised", body)
        self.assertIn("nothing is claimed about it", body)
        self.assertNotIn("did not reach the provider", body)


class AnAgeItCannotComputeIsNotZero(WebTest, LedgerFixture):
    """The only value on this page that is not copied straight from a ledger
    row is the age, so it is the only one that can be wrong by arithmetic."""

    def _repo(self, email=OPERATOR):
        return repo_module.Repo.for_user(email, "productive")

    def test_a_row_with_no_readable_stamp_renders_UNKNOWN(self):
        self.write_ledger([a_row(at="whenever"), a_row(at=None)])
        _, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertIn("no readable timestamp", body)
        # The failure mode being refused: an unparseable stamp read as now.
        self.assertNotIn("0 seconds ago", body)

    def test_an_undateable_row_is_age_None_and_not_age_zero(self):
        """At the service layer, where the arithmetic is."""
        self.write_ledger([a_row(at="whenever")])
        data = api.provider_write_log(self._repo())
        self.assertEqual(1, len(data["rows"]))
        self.assertIsNone(data["rows"][0]["age_seconds"])
        self.assertEqual(1, data["undated"])
        self.assertIsNone(data["newest_age_seconds"])

    def test_the_age_is_measured_against_an_injected_now(self):
        """Injected, so the test is not racing the wall clock - and the
        control is that a different `now` gives a different answer."""
        import datetime

        self.write_ledger([a_row(at="2026-10-15T20:00:00Z")])
        fixed = datetime.datetime(2026, 10, 15, 20, 0, 30,
                                  tzinfo=datetime.timezone.utc)
        later = datetime.datetime(2026, 10, 25, 20, 0, 0,
                                  tzinfo=datetime.timezone.utc)
        self.assertEqual(
            30, api.provider_write_log(self._repo(), now=fixed)
                   ["rows"][0]["age_seconds"])
        self.assertEqual(
            10 * 86400, api.provider_write_log(self._repo(), now=later)
                           ["rows"][0]["age_seconds"])

    def test_a_stamp_in_the_future_says_so_rather_than_rendering_a_negative(self):
        import datetime

        self.write_ledger([a_row(at="2026-10-15T20:00:00Z")])
        before = datetime.datetime(2026, 10, 15, 19, 0, 0,
                                   tzinfo=datetime.timezone.utc)
        data = api.provider_write_log(self._repo(), now=before)
        self.assertLess(data["rows"][0]["age_seconds"], 0)
        self.assertIn("stamped in the future", pages.provider_write_log(data))


class TheLedgerIsScopedToOneTenant(WebTest, LedgerFixture):

    def test_another_tenants_rows_are_not_shown_and_not_counted(self):
        self.assertEqual("productive",
                         repo_module.Repo.for_user(OPERATOR, "productive").client,
                         "the premise: this workspace's client is the tenant "
                         "providerwrites is handed")
        self.write_ledger([
            a_row(tenant=MINE, operation="bison.pause"),
            a_row(tenant=SOMEBODY_ELSE, operation="heyreach.pause"),
            a_row(tenant=None, operation="bison.resume"),
        ])
        _, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertIn("bison.pause", body)
        self.assertNotIn("heyreach.pause", body)
        self.assertNotIn("bison.resume", body)
        data = api.provider_write_log(
            repo_module.Repo.for_user(OPERATOR, "productive"))
        self.assertEqual(1, data["mine"])
        self.assertEqual({"accepted": 1}, data["counts"])

    def test_the_page_says_it_cannot_see_another_tenant(self):
        """Scoping silently is how a page comes to look complete."""
        self.write_ledger([a_row()])
        _, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertIn("another tenant", body)
        self.assertIn("naming none at all", body)


class OnlyThePermissionIChoseReachesIt(WebTest):
    """The choice is asserted, not assumed - and no role is hardcoded
    anywhere, which is what `api.py:3223` is the standing reason for."""

    def test_the_route_is_gated_on_provider_settings_view(self):
        self.assertEqual(ws.PROVIDER_SETTINGS_VIEW, permission_for(PATH))

    def test_that_permission_is_narrower_than_operations_view(self):
        """The premise behind choosing it, measured off GRANTS rather than
        restated: every role holding it also holds operations.view, and at
        least one role holds operations.view without it."""
        holders = {r for r in ws.ROLES if ws.may(r, ws.PROVIDER_SETTINGS_VIEW)}
        wider = {r for r in ws.ROLES if ws.may(r, ws.OPERATIONS_VIEW)}
        self.assertTrue(holders < wider, f"{holders} is not narrower than {wider}")
        self.assertIn(ws.REVIEWER, wider - holders)

    def test_a_reviewer_is_refused_although_they_may_see_operations(self):
        self.assertTrue(ws.may(ws.REVIEWER, ws.OPERATIONS_VIEW))
        self.assertFalse(ws.may(ws.REVIEWER, ws.PROVIDER_SETTINGS_VIEW))
        status, _, _ = self.signin(REVIEWER).get(PATH)
        self.assertEqual(403, status)

    def test_a_client_facing_viewer_is_refused(self):
        self.assertFalse(ws.may(ws.VIEWER, ws.PROVIDER_SETTINGS_VIEW))
        self.assertEqual(403, self.signin(VIEWER).get(PATH)[0])

    def test_an_operator_and_an_admin_are_admitted(self):
        for who, role in ((OPERATOR, ws.OPERATOR), (ADMIN, ws.WORKSPACE_ADMIN)):
            self.assertTrue(ws.may(role, ws.PROVIDER_SETTINGS_VIEW), role)
            self.assertEqual(200, self.signin(who).get(PATH)[0], who)

    def test_anonymous_is_sent_to_sign_in_and_never_served_the_page(self):
        status, body, _ = self.anonymous().get(PATH)
        self.assertNotIn("Provider writes", body)
        self.assertIn(status, (200, 303))

    def test_the_nav_offers_it_on_exactly_the_permission_the_route_checks(self):
        """A visible link that leads to a refusal, or a reachable page with
        no link, are the two halves of the same defect. Both were found on
        this surface today."""
        found = [item for item in pages.NAV if item[0] == PATH]
        self.assertEqual(1, len(found), "the nav names this page once")
        self.assertEqual(permission_for(PATH), found[0][2])


class NothingThisPageDoesWritesAnything(WebTest, LedgerFixture):
    """Asserted, not stated. Read-only was the reason this page was built
    first, so it is the one claim worth measuring rather than promising."""

    @staticmethod
    def _snapshot(root):
        """Name, size and content hash of every file under the store."""
        found = {}
        for where, _, names in os.walk(root):
            for name in names:
                full = os.path.join(where, name)
                try:
                    with open(full, "rb") as handle:
                        blob = handle.read()
                except OSError:
                    continue
                found[os.path.relpath(full, root)] = (
                    len(blob), hashlib.sha256(blob).hexdigest())
        return found

    def test_a_request_for_this_page_changes_no_file_in_the_store(self):
        from src import store

        self.write_ledger([a_row(), a_row(outcome="refused"),
                           a_row(outcome="unverified")])
        # Signed in FIRST, and the snapshot taken after. The claim under test
        # is "this page writes nothing", not "signing in writes nothing", and
        # folding the second into the first would make a failure unreadable.
        session = self.signin(OPERATOR)
        root = os.path.dirname(store.queue_path())
        before = self._snapshot(root)
        self.assertTrue(before, "the premise: the store holds files to compare")
        for _ in range(3):
            self.assertEqual(200, session.get(PATH)[0])
        self.assertEqual(before, self._snapshot(root))

    def test_it_writes_no_audit_row_either(self):
        """The three exports on this surface audit a GET. This must not:
        reading what was written is not itself an event."""
        from src import workspaces

        self.write_ledger([a_row()])
        session = self.signin(OPERATOR)
        before = len(workspaces.load())
        audit_before = len(api.audit_entries(None, limit=100000))
        self.assertEqual(200, session.get(PATH)[0])
        self.assertEqual(before, len(workspaces.load()))
        self.assertEqual(audit_before,
                         len(api.audit_entries(None, limit=100000)))

    def test_the_ledger_file_itself_is_untouched_by_being_read(self):
        target = self.write_ledger([a_row()])
        session = self.signin(OPERATOR)
        with open(target, "rb") as handle:
            before = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(200, session.get(PATH)[0])
        with open(target, "rb") as handle:
            self.assertEqual(before, hashlib.sha256(handle.read()).hexdigest())

    def test_the_snapshot_would_notice_a_write(self):
        """The control. A comparison that cannot detect a change is not
        evidence of its absence - which is this file's whole subject."""
        root = tempfile.mkdtemp(prefix="rga-plog-ctl-")
        with open(os.path.join(root, "a"), "w", encoding="utf-8") as handle:
            handle.write("one")
        before = self._snapshot(root)
        with open(os.path.join(root, "a"), "w", encoding="utf-8") as handle:
            handle.write("two")
        self.assertNotEqual(before, self._snapshot(root))


if __name__ == "__main__":
    unittest.main()
