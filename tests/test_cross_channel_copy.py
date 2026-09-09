"""The reference reaches the copy, or nothing does.

`test_cross_channel.py` tests the gate. This tests what happens on the other
side of it: that a licensed context actually produces the sentence, that an
unlicensed one produces a standalone message, and - the part that matters most
- that the leak guard now catches a mention which is *not* backed by the
evidence, including one that names the wrong person.

The old guard banned every cross-channel mention, which was right while nothing
could substantiate one. Replacing a ban with a licence is only safe if the
licence is checked, so most of this file is about checking it.
"""
import unittest

from src import assignment, cadence, events, senderidentity as si, store, touch
from tests.campaignbase import CampaignTest

WS = "productive"
ALLOW = {"sender_policy": {"colleague_language": True}}


def roster():
    return [
        si.new_sender(WS, "anna", "Anna Novak", team="growth"),
        si.new_sender(WS, "petar", "Petar Horvat", team="growth"),
        si.new_email_account(WS, "anna07", "anna", "anna07@productive.test"),
        si.new_linkedin_account(WS, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar"),
    ]


def contact_record(with_touch=None, sender_id="anna"):
    rec = store.new_record("acme", "domains", "productive", "Acme",
                           "acme.test")
    rec["contacts"] = [{"key": "k", "name": "Mark Bauer",
                        "email": "mark@acme.test", "selected": True,
                        "primary": True, "persona": "champion",
                        "linkedin": "https://www.linkedin.com/in/mark"}]
    rec["cadence"] = {}
    if with_touch:
        events.record(rec, with_touch, contact_key="k", channel="email",
                      step="day1", day=1, sender_id=sender_id,
                      account_id="anna07")
    return rec, rec["contacts"][0]


class TheOpenerReachesTheCopy(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())

    def step_with(self, context, channel="linkedin", note="happy to connect."):
        step = {"channel": channel, "note": note} if channel == "linkedin" \
            else {"channel": channel, "subject": "s", "body": "hello there."}
        return cadence.apply_cross_channel(step, context)

    def context_for(self, rec, contact, channel="linkedin", day=3):
        assignment.ensure(rec, contact, WS)
        return touch.context(rec, contact, channel, f"day{day}", day, WS,
                             config=ALLOW)

    def test_a_handoff_names_the_person_the_evidence_names(self):
        rec, contact = contact_record(events.PUSH_MARKED)
        ctx = self.context_for(rec, contact)
        step = self.step_with(ctx)
        self.assertIn("anna", step["note"].lower())
        self.assertIn("colleague", step["note"].lower())
        self.assertEqual(step["cross_channel_applied"], touch.TEAM_HANDOFF)

    def test_an_unlicensed_context_changes_nothing(self):
        rec, contact = contact_record(events.PUSH_PREPARED)
        ctx = self.context_for(rec, contact)
        step = self.step_with(ctx)
        self.assertEqual(step["note"], "happy to connect.")
        self.assertNotIn("cross_channel_applied", step)

    def test_no_context_at_all_changes_nothing(self):
        step = self.step_with(None)
        self.assertEqual(step["note"], "happy to connect.")

    def test_the_context_travels_on_the_step_for_the_preview(self):
        rec, contact = contact_record(events.PUSH_PREPARED)
        ctx = self.context_for(rec, contact)
        step = self.step_with(ctx)
        self.assertFalse(step["cross_channel"]["may_reference"])
        self.assertIn("payload built",
                      step["cross_channel"]["reference_reason"])

    def test_a_handoff_with_no_name_writes_standalone(self):
        """A licence to reference somebody nameless is not a licence."""
        rec, contact = contact_record(events.PUSH_MARKED)
        ctx = self.context_for(rec, contact)
        ctx["reference"]["first_name"] = ""
        step = self.step_with(ctx)
        self.assertEqual(step["note"], "happy to connect.")

    def test_same_sender_continuity_claims_nothing_about_anybody_else(self):
        si.install(roster() + [
            si.new_linkedin_account(WS, "anna-li", "anna",
                                    "https://www.linkedin.com/in/anna")])
        rec, contact = contact_record(events.PUSH_MARKED)
        contact["sender_assignment"] = {
            "email": {"sender_id": "anna", "display_name": "Anna Novak",
                      "account_id": "anna07"},
            "linkedin": {"sender_id": "anna", "display_name": "Anna Novak",
                         "account_id": "anna-li"}}
        ctx = touch.context(rec, contact, "linkedin", "day3", 3, WS,
                            config=ALLOW)
        step = self.step_with(ctx)
        self.assertEqual(step["cross_channel_applied"], touch.SAME_SENDER)
        self.assertNotIn("colleague", step["note"].lower())


class TheLeakGuardChecksTheLicence(CampaignTest):
    """Replacing a ban with a licence is only safe if the licence is checked."""

    def setUp(self):
        super().setUp()
        si.install(roster())

    def licensed_context(self, name="Anna"):
        return {"may_reference": True,
                "reference": {"mode": touch.TEAM_HANDOFF, "first_name": name,
                              "sender_id": "anna", "channel": "email"}}

    def test_an_unlicensed_mention_is_still_a_leak(self):
        steps = {"day3": {"channel": "linkedin",
                          "note": "my colleague emailed you last week"}}
        leaks = cadence.cross_channel_leaks(steps)
        self.assertTrue(leaks)
        self.assertIn("no confirmed cross-channel touch", leaks[0])

    def test_a_mention_with_a_refusing_context_is_a_leak(self):
        """What a hand-edited or injected body would look like."""
        steps = {"day3": {"channel": "linkedin",
                          "note": "anna emailed you last week",
                          "cross_channel": {"may_reference": False,
                                            "reference_reason": "no"}}}
        self.assertTrue(cadence.cross_channel_leaks(steps))

    def test_a_licensed_mention_naming_the_right_person_is_clean(self):
        steps = {"day3": {"channel": "linkedin",
                          "note": "my colleague anna emailed you earlier.",
                          "cross_channel": self.licensed_context("Anna")}}
        self.assertEqual(cadence.cross_channel_leaks(steps), [])

    def test_a_licensed_mention_naming_the_wrong_person_is_a_leak(self):
        """The failure that puts a prospect in front of a colleague who never
        wrote to them. The old guard could not see this at all."""
        steps = {"day3": {"channel": "linkedin",
                          "note": "my colleague petar emailed you earlier.",
                          "cross_channel": self.licensed_context("Anna")}}
        leaks = cadence.cross_channel_leaks(steps)
        self.assertTrue(leaks)
        self.assertIn("does not name Anna", leaks[0])

    def test_an_email_mentioning_linkedin_without_a_licence_is_a_leak(self):
        steps = {"day5": {"channel": "email", "subject": "hi",
                          "body": "I sent a connection request on LinkedIn."}}
        self.assertTrue(cadence.cross_channel_leaks(steps))

    def test_a_step_with_no_mention_at_all_is_clean_either_way(self):
        for context in (None, self.licensed_context()):
            steps = {"day3": {"channel": "linkedin",
                              "note": "happy to connect.",
                              "cross_channel": context}}
            self.assertEqual(cadence.cross_channel_leaks(steps), [])


class TheWholePipeline(CampaignTest):
    """cadence.build, with cross-channel on, end to end."""

    def setUp(self):
        super().setUp()
        si.install(roster())

    def built(self, rec, contact, allow_colleague=True):
        """The fixture config does not enable colleague language, and that is
        the correct default - so a test that wants a handoff has to say so,
        exactly as a real workspace would."""
        config = dict(self.config)
        if allow_colleague:
            config["sender_policy"] = {"colleague_language": True}
        assignment.ensure(rec, contact, WS)
        return cadence.build(rec, config, workspace=WS, cross_channel=True)

    def test_the_fixture_default_refuses_a_handoff(self):
        """Proof that the permission is doing the work, not the plumbing."""
        rec, contact = contact_record(events.PUSH_MARKED)
        steps = (self.built(rec, contact, allow_colleague=False)
                 .get("contacts") or {}).get("k") or {}
        note = steps.get("day3") or {}
        if not note:
            self.skipTest("no day3 step for this contact")
        self.assertFalse(note["cross_channel"]["may_reference"])
        self.assertIn("colleague_language",
                      note["cross_channel"]["reference_reason"])

    def test_off_by_default_so_no_existing_caller_changes(self):
        rec, contact = contact_record(events.PUSH_MARKED)
        plain = cadence.build(rec, self.config)
        for step in (plain.get("contacts") or {}).get("k", {}).values():
            self.assertNotIn("cross_channel_applied", step)

    def test_a_confirmed_email_licenses_the_linkedin_note(self):
        rec, contact = contact_record(events.PUSH_MARKED)
        steps = (self.built(rec, contact).get("contacts") or {}).get("k") or {}
        note = steps.get("day3") or {}
        if not note:
            self.skipTest("no day3 step for this contact")
        self.assertTrue(note["cross_channel"]["may_reference"],
                        note["cross_channel"]["reference_reason"])
        self.assertIn("anna", (note.get("note") or "").lower())

    def test_a_prepared_payload_does_not(self):
        rec, contact = contact_record(events.PUSH_PREPARED)
        steps = (self.built(rec, contact).get("contacts") or {}).get("k") or {}
        note = steps.get("day3") or {}
        if not note:
            self.skipTest("no day3 step for this contact")
        self.assertFalse(note["cross_channel"]["may_reference"])
        self.assertNotIn("anna", (note.get("note") or "").lower())

    def test_the_built_timeline_never_leaks(self):
        for event in (None, events.PUSH_PREPARED, events.PUSH_MARKED):
            rec, contact = contact_record(event)
            steps = (self.built(rec, contact).get("contacts") or {}).get("k") or {}
            self.assertEqual(cadence.cross_channel_leaks(steps), [],
                             f"leak with {event}")

    def test_a_touch_is_referenced_once_not_in_every_later_step(self):
        """Five emails each opening "my colleague Petar reached out" is not
        five times as personal. It is a sequence a person recognises as
        generated, and the first version of this did exactly that."""
        rec, contact = contact_record(events.PUSH_MARKED)
        steps = (self.built(rec, contact).get("contacts") or {}).get("k") or {}
        applied = [s for s in steps.values() if s.get("cross_channel_applied")]
        self.assertLessEqual(len(applied), 1,
                             "the same touch was referenced more than once")

    def test_a_reference_never_points_forwards_in_time(self):
        """A step cannot mention a touch that happens after it. Persona
        offsets shift every day in the cadence, so the comparison has to be
        made in one coordinate system - it was not, and a day-1 email opened
        by referring to a LinkedIn note two days in its future."""
        rec, contact = contact_record(events.PUSH_MARKED)
        steps = (self.built(rec, contact).get("contacts") or {}).get("k") or {}
        for step in steps.values():
            reference = (step.get("cross_channel") or {}).get("reference")
            if not reference:
                continue
            self.assertLess(reference.get("day") or 0, step.get("day") or 0,
                            f"{step.get('channel')} step references a touch "
                            "that has not happened yet")

    def test_a_context_that_cannot_be_built_licenses_nothing(self):
        """Failing closed: an exception must not become a fabricated claim."""
        rec, contact = contact_record(events.PUSH_MARKED)
        # No roster at all - every lookup inside the context raises or empties.
        si.install([])
        steps = (self.built(rec, contact).get("contacts") or {}).get("k") or {}
        for step in steps.values():
            self.assertNotIn("cross_channel_applied", step)
        self.assertEqual(cadence.cross_channel_leaks(steps), [])


if __name__ == "__main__":
    unittest.main()


class TheProviderPayloadCarriesTheSender(CampaignTest):
    """A LinkedIn account is per contact, not per push.

    The existing payload tests all exercise the *fallback* - records with no
    assignment, where the caller's single account id is used. This covers the
    path that matters once contacts are assigned: two prospects assigned to
    two different LinkedIn humans must not both go out from whichever profile
    the caller happened to name.
    """

    def setUp(self):
        super().setUp()
        si.install(roster() + [
            si.new_sender(WS, "tom", "Tom Ricci", team="partnerships"),
            si.new_linkedin_account(WS, "tom-li", "tom",
                                    "https://www.linkedin.com/in/tom",
                                    provider_account_id="7007")])
        si.install(si.load() + [
            si.new_linkedin_account(WS, "petar-li2", "petar",
                                    "https://www.linkedin.com/in/petar2",
                                    provider_account_id="7001")])

    def row_for(self, sender_id, account_id, provider_account_id):
        return {"linkedin_url": "https://www.linkedin.com/in/mark",
                "first_name": "Mark", "last_name": "Bauer",
                "company": "Acme", "title": "COO", "note": "hello",
                "record_id": "acme", "contact_key": "k", "client": "productive",
                "sender_id": sender_id, "sender_account_id": account_id,
                "provider_account_id": provider_account_id}

    def test_each_row_goes_out_from_its_own_assigned_account(self):
        from src.providers import heyreach

        rows = [self.row_for("petar", "petar-li", "7001"),
                self.row_for("tom", "tom-li", "7007")]
        pairs = heyreach.build_lead_pairs(rows, linkedin_account_id=999)
        self.assertEqual([p["linkedInAccountId"] for p in pairs], [7001, 7007],
                         "every lead went out from the caller's fallback")

    def test_a_row_with_no_assignment_uses_the_fallback(self):
        from src.providers import heyreach

        rows = [self.row_for(None, None, None)]
        pairs = heyreach.build_lead_pairs(rows, linkedin_account_id=42)
        self.assertEqual(pairs[0]["linkedInAccountId"], 42)

    def test_a_provider_id_that_is_not_a_number_falls_back(self):
        """Guessing an account id would send from a profile nobody chose."""
        from src.providers import heyreach

        rows = [self.row_for("petar", "petar-li", "not-a-number")]
        pairs = heyreach.build_lead_pairs(rows, linkedin_account_id=42)
        self.assertEqual(pairs[0]["linkedInAccountId"], 42)

    def test_the_human_travels_in_the_custom_fields(self):
        from src.providers import heyreach

        pairs = heyreach.build_lead_pairs(
            [self.row_for("petar", "petar-li", "7001")], 0)
        fields = {f["name"]: f["value"]
                  for f in pairs[0]["lead"]["customUserFields"]}
        self.assertEqual(fields["sender_id"], "petar")
        self.assertEqual(fields["sender_account_id"], "petar-li")
        # The note still travels first; the push CLI prints field zero.
        self.assertEqual(pairs[0]["lead"]["customUserFields"][0]["name"], "note")

    def test_no_credential_travels_in_the_linkedin_payload(self):
        from src.providers import heyreach

        pairs = heyreach.build_lead_pairs(
            [self.row_for("petar", "petar-li", "7001")], 0)
        blob = str(pairs).lower()
        for forbidden in ("token", "secret", "password", "api_key", "bearer"):
            self.assertNotIn(forbidden, blob)
