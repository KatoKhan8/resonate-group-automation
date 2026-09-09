"""The sentence "my colleague Anna emailed you" is either true or it is a lie.

There is no third option and no way to tell from the copy, so this file walks
every state a previous step can be in and asserts which of them license the
claim. Exactly four do. The other nine do not, and `payload_ready` is the one
worth staring at: in this build every payload is built and none is sent, so a
system that treated it as evidence would claim to have contacted every prospect
it has ever planned to.
"""
import unittest

from src import assignment, events, senderidentity as si, store, touch
from tests.campaignbase import CampaignTest

WS = "productive"


def roster():
    """Two humans, one inbox and one profile each. Anna emails, Petar LinkedIns."""
    return [
        si.new_sender(WS, "anna", "Anna Novak", title="Account Director",
                      team="growth"),
        si.new_sender(WS, "petar", "Petar Horvat", title="Partnerships",
                      team="growth"),
        si.new_email_account(WS, "anna07", "anna", "anna07@productive.test",
                             provider_account_id="bison-anna07"),
        si.new_linkedin_account(WS, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar-horvat",
                                provider_account_id="hr-petar"),
    ]


def colleague_config(allowed=True):
    return {"sender_policy": {"colleague_language": allowed}}


class ConfirmedTouchDefinition(CampaignTest):
    """One test per state, because the list is the specification."""

    def setUp(self):
        super().setUp()
        si.install(roster())

    def contact_with(self, state_event=None, sender_id="anna"):
        """A record whose day-1 email is in whichever state we are testing."""
        rec = self.record()
        contact = rec["contacts"][0]
        if state_event:
            events.record(rec, state_event, contact_key=contact["key"],
                          channel="email", step="day1", day=1,
                          sender_id=sender_id, account_id="anna07")
        return rec, contact

    def record(self):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{
            "key": "acme-mark", "name": "Mark Bauer", "email": "mark@acme.test",
            "selected": True, "primary": True, "persona": "champion",
            "linkedin": "https://www.linkedin.com/in/mark-bauer",
        }]
        rec["cadence"] = {}
        return rec

    def linkedin_context(self, rec, contact, config=None):
        assignment.ensure(rec, contact, WS)
        return touch.context(rec, contact, "linkedin", "day3", 3, WS,
                             config=config or colleague_config())

    # ---------------------------------------------------------- refused

    def test_nothing_at_all_refuses(self):
        rec, contact = self.contact_with()
        ctx = self.linkedin_context(rec, contact)
        self.assertFalse(ctx["may_reference"])
        self.assertIn("no confirmed", ctx["reference_reason"])

    def test_a_built_payload_is_not_a_send(self):
        """The dangerous near-miss: every payload is built in this build."""
        rec, contact = self.contact_with(events.PUSH_PREPARED)
        ctx = self.linkedin_context(rec, contact)
        self.assertFalse(ctx["may_reference"],
                         "a built payload was treated as a send")
        self.assertIn("payload built", ctx["reference_reason"])

    def test_an_approved_draft_is_not_a_send(self):
        rec, contact = self.contact_with()
        contact_key = contact["key"]
        rec["cadence"][contact_key] = {"day1": {"approved": True,
                                                "status": "eligible"}}
        ctx = self.linkedin_context(rec, contact)
        self.assertFalse(ctx["may_reference"])

    def test_a_blocked_step_is_not_a_send(self):
        rec, contact = self.contact_with()
        rec["cadence"][contact["key"]] = {"day1": {"status": "blocked"}}
        ctx = self.linkedin_context(rec, contact)
        self.assertFalse(ctx["may_reference"])

    def test_a_held_step_is_not_a_send(self):
        rec, contact = self.contact_with()
        rec["cadence"][contact["key"]] = {"day1": {"status": "waiting"}}
        ctx = self.linkedin_context(rec, contact)
        self.assertFalse(ctx["may_reference"])

    def test_a_bounced_email_is_not_a_send(self):
        rec, contact = self.contact_with(events.EMAIL_BOUNCED)
        ctx = self.linkedin_context(rec, contact)
        self.assertFalse(ctx["may_reference"])

    # ---------------------------------------------------------- allowed

    def test_a_marked_push_is_a_send(self):
        rec, contact = self.contact_with(events.PUSH_MARKED)
        ctx = self.linkedin_context(rec, contact)
        self.assertTrue(ctx["may_reference"], ctx["reference_reason"])
        self.assertEqual(ctx["reference"]["sender_id"], "anna")
        self.assertEqual(ctx["reference"]["mode"], touch.TEAM_HANDOFF)

    def test_a_provider_delivery_is_a_send(self):
        rec, contact = self.contact_with(events.EMAIL_DELIVERED)
        ctx = self.linkedin_context(rec, contact)
        self.assertTrue(ctx["may_reference"])

    def test_the_reason_names_the_evidence(self):
        rec, contact = self.contact_with(events.PUSH_MARKED)
        ctx = self.linkedin_context(rec, contact)
        line = touch.explain(ctx)
        self.assertIn("Anna Novak", line)
        self.assertIn("email", line)
        self.assertIn("day 1", line)

    def test_every_confirmed_state_is_covered_by_an_event(self):
        """The two lists have to agree or one of them is decoration."""
        produced = set(touch.CONFIRMING_EVENTS.values())
        self.assertTrue(produced <= touch.CONFIRMED_STATES)


class WhoIsNamed(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())

    def rec_with_touch(self, sender_id="anna"):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "Mark", "email": "m@acme.test",
                            "selected": True, "primary": True,
                            "linkedin": "https://www.linkedin.com/in/m"}]
        rec["cadence"] = {}
        contact = rec["contacts"][0]
        kwargs = {"contact_key": "k", "channel": "email", "step": "day1",
                  "day": 1, "account_id": "anna07"}
        if sender_id:
            kwargs["sender_id"] = sender_id
        events.record(rec, events.PUSH_MARKED, **kwargs)
        return rec, contact

    def test_a_touch_with_no_sender_is_confirmed_but_unattributed(self):
        """It happened. It may not be attributed to a person by name."""
        rec, contact = self.rec_with_touch(sender_id=None)
        assignment.ensure(rec, contact, WS)
        ctx = touch.context(rec, contact, "linkedin", "day3", 3, WS,
                            config=colleague_config())
        self.assertFalse(ctx["may_reference"])
        self.assertIn("does not record which sender", ctx["reference_reason"])
        # But the history still knows it happened.
        self.assertEqual(
            len(touch.confirmed_touches(rec, "k")), 1)

    def test_a_touch_naming_an_unknown_sender_is_refused(self):
        rec, contact = self.rec_with_touch(sender_id="somebody-else")
        assignment.ensure(rec, contact, WS)
        ctx = touch.context(rec, contact, "linkedin", "day3", 3, WS,
                            config=colleague_config())
        self.assertFalse(ctx["may_reference"])
        self.assertIn("not a sender in this workspace",
                      ctx["reference_reason"])

    def test_history_names_the_sender_on_the_touch_not_the_current_one(self):
        """A reassignment must not rewrite what already happened."""
        rec, contact = self.rec_with_touch(sender_id="anna")
        assignment.ensure(rec, contact, WS)
        # Move the email relationship to somebody else, after the fact.
        si.add(si.new_sender(WS, "mark", "Mark Weber", team="growth"))
        si.add(si.new_email_account(WS, "mark01", "mark",
                                    "mark01@productive.test"))
        assignment.reassign(rec, contact, WS, "email", "mark", by="ops",
                            reason="anna left")

        confirmed = touch.confirmed_touches(rec, "k")
        self.assertEqual(confirmed[0]["sender_id"], "anna",
                         "a reassignment rewrote history")


class CopyModes(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())

    def build(self, current_channel, previous_channel, previous_sender,
              config=None):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "Mark", "email": "m@acme.test",
                            "selected": True, "primary": True,
                            "linkedin": "https://www.linkedin.com/in/m"}]
        rec["cadence"] = {}
        contact = rec["contacts"][0]
        events.record(rec, events.PUSH_MARKED, contact_key="k",
                      channel=previous_channel, step="day1", day=1,
                      sender_id=previous_sender, account_id="x")
        assignment.ensure(rec, contact, WS)
        return rec, contact, touch.context(
            rec, contact, current_channel, "day3", 3, WS,
            config=config if config is not None else colleague_config())

    def test_same_sender_on_both_channels_is_continuity(self):
        si.install(roster() + [
            si.new_linkedin_account(WS, "anna-li", "anna",
                                    "https://www.linkedin.com/in/anna-novak")])
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "M", "email": "m@acme.test",
                            "selected": True, "primary": True,
                            "linkedin": "https://www.linkedin.com/in/m"}]
        rec["cadence"] = {}
        contact = rec["contacts"][0]
        # Force both channels onto Anna.
        contact["sender_assignment"] = {
            "email": {"sender_id": "anna", "display_name": "Anna Novak",
                      "account_id": "anna07"},
            "linkedin": {"sender_id": "anna", "display_name": "Anna Novak",
                         "account_id": "anna-li"}}
        events.record(rec, events.PUSH_MARKED, contact_key="k",
                      channel="email", step="day1", day=1, sender_id="anna",
                      account_id="anna07")
        ctx = touch.context(rec, contact, "linkedin", "day3", 3, WS,
                            config=colleague_config())
        self.assertTrue(ctx["may_reference"])
        self.assertEqual(ctx["reference"]["mode"], touch.SAME_SENDER)

    def test_two_humans_with_permission_is_a_handoff(self):
        _, _, ctx = self.build("linkedin", "email", "anna")
        self.assertTrue(ctx["may_reference"])
        self.assertEqual(ctx["reference"]["mode"], touch.TEAM_HANDOFF)

    def test_two_humans_without_permission_write_standalone(self):
        """Not a vaguer sentence. No sentence."""
        _, _, ctx = self.build("linkedin", "email", "anna",
                               config=colleague_config(False))
        self.assertFalse(ctx["may_reference"])
        self.assertIn("colleague_language", ctx["reference_reason"])

    def test_an_unconfigured_workspace_refuses_by_default(self):
        _, _, ctx = self.build("linkedin", "email", "anna", config={})
        self.assertFalse(ctx["may_reference"])

    def test_a_sender_may_opt_out_against_the_workspace(self):
        rows = roster()
        rows[0] = si.new_sender(WS, "anna", "Anna Novak", team="growth",
                                colleague_language=False)
        si.install(rows)
        _, _, ctx = self.build("linkedin", "email", "anna")
        self.assertFalse(ctx["may_reference"])
        self.assertIn("narrower refusal wins", ctx["reference_reason"])

    def test_linkedin_first_then_email_also_works(self):
        si.install(roster() + [
            si.new_email_account(WS, "petar01", "petar",
                                 "petar01@productive.test")])
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "M", "email": "m@acme.test",
                            "selected": True, "primary": True,
                            "linkedin": "https://www.linkedin.com/in/m"}]
        rec["cadence"] = {}
        contact = rec["contacts"][0]
        contact["sender_assignment"] = {
            "email": {"sender_id": "anna", "display_name": "Anna Novak",
                      "account_id": "anna07"},
            "linkedin": {"sender_id": "petar", "display_name": "Petar Horvat",
                         "account_id": "petar-li"}}
        events.record(rec, events.PUSH_MARKED, contact_key="k",
                      channel="linkedin", step="day1", day=1,
                      sender_id="petar", account_id="petar-li")
        ctx = touch.context(rec, contact, "email", "day5", 5, WS,
                            config=colleague_config())
        self.assertTrue(ctx["may_reference"])
        self.assertEqual(ctx["reference"]["channel"], "linkedin")
        self.assertEqual(ctx["reference"]["sender_id"], "petar")

    def test_a_same_channel_touch_is_not_a_cross_channel_reference(self):
        """A previous email does not license an email saying "I emailed you"."""
        _, _, ctx = self.build("email", "email", "anna")
        self.assertFalse(ctx["may_reference"])


class HistoryIsNotShared(CampaignTest):
    """A contact's history is its own. Two ways that could go wrong."""

    def setUp(self):
        super().setUp()
        si.install(roster())

    def two_contacts(self):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [
            {"key": "a", "name": "A", "email": "a@acme.test", "selected": True,
             "primary": True, "linkedin": "https://www.linkedin.com/in/a"},
            {"key": "b", "name": "B", "email": "b@acme.test", "selected": True,
             "linkedin": "https://www.linkedin.com/in/b"}]
        rec["cadence"] = {}
        return rec

    def test_a_contact_does_not_inherit_a_sibling_touch(self):
        rec = self.two_contacts()
        events.record(rec, events.PUSH_MARKED, contact_key="a",
                      channel="email", step="day1", day=1, sender_id="anna",
                      account_id="anna07")
        self.assertEqual(len(touch.confirmed_touches(rec, "a")), 1)
        self.assertEqual(len(touch.confirmed_touches(rec, "b")), 0,
                         "one contact inherited another's touch")

        contact_b = rec["contacts"][1]
        assignment.ensure(rec, contact_b, WS)
        ctx = touch.context(rec, contact_b, "linkedin", "day3", 3, WS,
                            config=colleague_config())
        self.assertFalse(ctx["may_reference"])

    def test_a_contact_does_not_inherit_another_workspaces_touch(self):
        """Events live on the record, and a record belongs to one client."""
        mine = self.two_contacts()
        theirs = store.new_record("other", "domains", "contactout", "Other",
                                  "other.test")
        theirs["contacts"] = [{"key": "a", "name": "A", "email": "a@o.test",
                               "selected": True, "primary": True}]
        events.record(theirs, events.PUSH_MARKED, contact_key="a",
                      channel="email", step="day1", day=1, sender_id="anna",
                      account_id="anna07")
        self.assertEqual(len(touch.confirmed_touches(mine, "a")), 0)


class RepliesStopTheFuture(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())

    def test_a_reply_is_visible_in_the_history(self):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "M", "email": "m@acme.test",
                            "selected": True, "primary": True,
                            "linkedin": "https://www.linkedin.com/in/m"}]
        rec["cadence"] = {}
        events.record(rec, events.PUSH_MARKED, contact_key="k",
                      channel="email", step="day1", day=1, sender_id="anna",
                      account_id="anna07")
        events.record(rec, events.REPLY_RECEIVED, contact_key="k",
                      channel="email")
        built = touch.history(rec, "k")
        self.assertTrue(built["replied_at"])

    def test_a_paused_record_says_so(self):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "M", "email": "m@acme.test",
                            "selected": True, "primary": True}]
        rec["cadence"] = {}
        rec["paused"] = {"since": "now", "reason": "reply_received"}
        self.assertTrue(touch.history(rec, "k")["paused"])


if __name__ == "__main__":
    unittest.main()


class ATouchInTheFutureIsNotAPreviousTouch(CampaignTest):
    """The mutation audit found this one: the ordering filter had no test.

    Every fixture elsewhere plants a day-1 touch and then asks a later step
    about it, so removing the `before_day` filter changed nothing observable.
    A guard nobody can fail is a guard that gets deleted by somebody tidying
    up. These plant a touch *after* the step being built.
    """

    def setUp(self):
        super().setUp()
        si.install(roster())

    def rec_with_late_touch(self):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "k", "name": "Mark", "email": "m@acme.test",
                            "selected": True, "primary": True,
                            "linkedin": "https://www.linkedin.com/in/m"}]
        rec["cadence"] = {}
        contact = rec["contacts"][0]
        # A confirmed LinkedIn touch on day 8 - later than the day-3 step that
        # will ask whether anything came before it.
        events.record(rec, events.PUSH_MARKED, contact_key="k",
                      channel="linkedin", step="day8", day=8,
                      sender_id="petar", account_id="petar-li")
        assignment.ensure(rec, contact, WS)
        return rec, contact

    def test_confirmed_touches_excludes_one_that_comes_later(self):
        rec, _ = self.rec_with_late_touch()
        self.assertEqual(touch.confirmed_touches(rec, "k", before_day=3), [],
                         "a day-8 touch was offered to a day-3 step")
        # And it is genuinely there when nothing bounds the query.
        self.assertEqual(len(touch.confirmed_touches(rec, "k")), 1)

    def test_a_step_may_not_reference_a_touch_that_comes_after_it(self):
        rec, contact = self.rec_with_late_touch()
        ctx = touch.context(rec, contact, "email", "day3", 3, WS,
                            config=colleague_config())
        self.assertFalse(ctx["may_reference"],
                         "a step referenced a touch from its own future")

    def test_the_same_touch_is_available_to_a_step_after_it(self):
        """The filter bounds the query; it does not disable it."""
        rec, contact = self.rec_with_late_touch()
        ctx = touch.context(rec, contact, "email", "day10", 10, WS,
                            config=colleague_config())
        self.assertTrue(ctx["may_reference"], ctx["reference_reason"])
        self.assertEqual(ctx["reference"]["day"], 8)

    def test_a_touch_on_the_same_day_is_not_a_previous_touch(self):
        """Same day is not "earlier". Two touches on one day are a same-day
        collision, which the separation rule already refuses."""
        rec, contact = self.rec_with_late_touch()
        ctx = touch.context(rec, contact, "email", "day8", 8, WS,
                            config=colleague_config())
        self.assertFalse(ctx["may_reference"])
