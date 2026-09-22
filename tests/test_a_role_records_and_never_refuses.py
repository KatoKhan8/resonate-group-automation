"""Roles inside a client workspace, and the one thing they must never do.

OPERATOR, 2026-09-22: "Per-user roles inside a client workspace."

The temptation with a role is to make it a gate. The highest-severity
message in the whole Slack corpus argues against that as loudly as a
message can:

    can you please stop sending messages to people who have replied????

That is a client, in their own channel, with four question marks. An agent
that answered it with "you are not authorised to ask for that" - or that
quietly held the ticket until somebody senior repeated it - would be worse
than the agent that existed before roles did.

So the rule this file exists to pin down is:

    A request that REDUCES reach is taken from anybody, always, with no
    authority check of any kind. The role is recorded on the ticket for the
    operator to read, and it decides nothing.

The second rule is that none of this is ever said back into the client's
channel. What the client hears is what they heard before: it is with the
Resonate team, and no timescale.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackrequests as requests                        # noqa: E402
from src import slackroles as roles, slackscope                  # noqa: E402

OWNER_USER = "U0OWNERAAAA"
MEMBER_USER = "U0MEMBERAAA"
OBSERVER_USER = "U0OBSERVERA"
STRANGER = "U0NOBODYAAA"


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


class WithRoles(unittest.TestCase):

    def setUp(self):
        self._prev = os.environ.get(roles.ROLES_VAR)
        os.environ[roles.ROLES_VAR] = "%s:owner,%s:member,%s:observer" % (
            OWNER_USER, MEMBER_USER, OBSERVER_USER)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(roles.ROLES_VAR, None)
        else:
            os.environ[roles.ROLES_VAR] = self._prev


# ================================ 1. THE REGISTER

class TheRegisterIsReadAndTypoesDoNotBecomeAuthority(WithRoles):

    def test_the_recorded_roles_are_read(self):
        self.assertEqual(roles.role_of(OWNER_USER, "alpha"), roles.OWNER)
        self.assertEqual(roles.role_of(OBSERVER_USER, "alpha"),
                         roles.OBSERVER)

    def test_an_unlisted_person_is_a_member_rather_than_an_error(self):
        self.assertEqual(roles.role_of(STRANGER, "alpha"), roles.MEMBER)
        self.assertFalse(roles.is_recorded(STRANGER, "alpha"))

    def test_a_role_that_is_not_a_role_is_dropped(self):
        """A typo that became authority would be the one bug this must not
        have. A typo that becomes `member` is visible on the next ticket."""
        os.environ[roles.ROLES_VAR] = "%s:ownr" % OWNER_USER
        self.assertEqual(roles.role_of(OWNER_USER, "alpha"), roles.MEMBER)
        self.assertFalse(roles.is_recorded(OWNER_USER, "alpha"))

    def test_nobody_is_recorded_when_there_is_no_register(self):
        os.environ.pop(roles.ROLES_VAR, None)
        self.assertEqual(roles.role_of(OWNER_USER, "alpha"), roles.MEMBER)


# ================================ 2. A STOP IS NEVER MADE TO WAIT

class ARequestThatReducesReachIsTakenFromAnybody(WithRoles):

    def test_every_narrowing_kind_is_taken_from_a_stranger(self):
        for kind in roles.NARROWING_KINDS:
            authority, note = roles.authority_note(kind, STRANGER, client())
            self.assertEqual(authority, "not recorded", kind)
            self.assertIn("REDUCES outreach", note, kind)
            self.assertIn("without any authority check", note, kind)

    def test_the_reply_stop_complaint_is_the_case_this_protects(self):
        """*can you please stop sending messages to people who have
        replied????* - recognised as a stop, raised from anybody."""
        kind, _fields = requests.recognise(
            "can you please stop contacting them????")
        self.assertIn(kind, roles.NARROWING_KINDS)
        authority, note = roles.authority_note(kind, STRANGER, client())
        self.assertIn("never made to wait", note)

    def test_an_observer_stopping_an_account_is_not_treated_differently(self):
        for user in (OWNER_USER, OBSERVER_USER, STRANGER):
            _authority, note = roles.authority_note(
                "stop_account", user, client())
            self.assertIn("REDUCES outreach", note, user)


# ================================ 3. A WIDENING ASK IS FLAGGED, NOT REFUSED

class AWideningRequestIsRaisedAndAnnotated(WithRoles):

    def test_an_owner_needs_no_note(self):
        authority, note = roles.authority_note("add_lead", OWNER_USER,
                                               client())
        self.assertEqual(authority, "owner")
        self.assertIsNone(note)

    def test_a_recorded_non_owner_is_named_as_what_they_are(self):
        authority, note = roles.authority_note("change_copy", OBSERVER_USER,
                                               client())
        self.assertEqual(authority, "recorded: observer")
        self.assertIn("confirm with the owner", note)

    def test_an_unrecorded_person_says_the_register_is_empty(self):
        authority, note = roles.authority_note("change_window", STRANGER,
                                               client())
        self.assertEqual(authority, "not recorded")
        self.assertIn("cannot tell you", note)
        self.assertIn(roles.ROLES_KEY, note)

    def test_an_internal_requester_has_no_authority_question(self):
        authority, note = roles.authority_note("add_lead", STRANGER,
                                               internal())
        self.assertEqual(authority, "internal")
        self.assertIsNone(note)


# ================================ 4. IT REACHES THE TICKET AND NOT THE CLIENT

class TheOperatorSeesItAndTheClientDoesNot(WithRoles):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-roles-")
        self._dir = os.environ.get(requests.REQUESTS_DIR_VAR)
        os.environ[requests.REQUESTS_DIR_VAR] = self.tmp

    def tearDown(self):
        if self._dir is None:
            os.environ.pop(requests.REQUESTS_DIR_VAR, None)
        else:
            os.environ[requests.REQUESTS_DIR_VAR] = self._dir
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def ticket(self, kind, user, fields=None):
        return requests.build(kind, fields or {"lead": "x@example.test"},
                              requester=user, channel="C1",
                              scope=client(), thread_ts="T1",
                              original="please do it")

    def test_the_ticket_carries_the_authority(self):
        self.assertEqual(
            self.ticket("add_lead", OWNER_USER)["requester_authority"],
            "owner")
        self.assertEqual(
            self.ticket("add_lead", STRANGER)["requester_authority"],
            "not recorded")

    def test_the_rendered_ticket_shows_it_to_the_person_reading(self):
        body = requests.render(self.ticket("add_lead", STRANGER))
        self.assertIn("authority", body)
        self.assertIn("not recorded", body)

    def test_the_action_required_post_carries_the_note(self):
        post = requests.action_required(self.ticket("add_lead", STRANGER))
        self.assertIn("No role is recorded", post)

    def test_an_owners_request_adds_no_noise_to_the_post(self):
        post = requests.action_required(self.ticket("add_lead", OWNER_USER))
        self.assertNotIn("No role is recorded", post)
        self.assertNotIn("confirm with the owner", post)

    def test_a_narrowing_request_tells_the_operator_why_there_is_no_gate(
            self):
        post = requests.action_required(
            self.ticket("stop_account", STRANGER, {"account": "example.test"}))
        self.assertIn("REDUCES outreach", post)

    def test_nothing_about_authority_is_said_to_the_client(self):
        """The restatement is what the client reads. It is about the
        change, never about who asked for it."""
        said = requests.restate("add_lead", {"lead": "x@example.test"},
                                "alpha", client_facing=True)
        for leaked in ("authority", "not recorded", "owner", "observer",
                       "confirm with"):
            self.assertNotIn(leaked, said.lower(), leaked)


# ================================ 5. IT CANNOT BREAK THE TICKET

class AnUnreadableRegisterStillRaisesTheTicket(WithRoles):

    def test_a_register_that_explodes_does_not_stop_a_stop(self):
        from unittest import mock
        with mock.patch.object(requests.roles, "authority_note",
                               side_effect=RuntimeError("boom")):
            ticket = requests.build(
                "stop_account", {"account": "example.test"},
                requester=STRANGER, channel="C1", scope=client(),
                thread_ts="T1", original="stop them")
        self.assertEqual(ticket["kind"], "stop_account")
        self.assertEqual(ticket["requester_authority"], "not recorded")
        self.assertIsNone(ticket["authority_note"])


if __name__ == "__main__":
    unittest.main()
