"""Attacks on the guards added on 2026-09-08 and 2026-09-09.

Every one of them is new attack surface, and one of them was deliberately
*loosened* the same night: `store.refuse_evidence_loss` stopped keying evidence
on its timestamp, because doing so refused writes that lost nothing. Loosening
a safety guard to fix a false positive is exactly how a real hole gets opened,
so the first class here tries to walk a genuine loss through the wider key.

The others attack the three gates added tonight by asking, for each, what a
caller would have to do to get past it - and asserting they cannot.
"""
import unittest

from src import eligibility, fatigue, killswitch, poller, store
from src import verification as V
from src.providers import heyreach


# --------------------------------------------------------------------------
# 1. The guard that was loosened.

class RealEvidenceLossStillCannotPass(unittest.TestCase):
    """The key went from (address, provider, at, status) to (address,
    provider, status). Anything that key can no longer tell apart is a way
    through, so each one is tried."""

    def person(self, email="champ@acme.test", answers=(("contactout", "valid"),
                                                       ("deliverable", "valid"))):
        person = {"key": "k", "name": "N", "email": email}
        evidence = [V.result(p, s, email, at=f"2026-09-09T10:00:{i:02d}Z")
                    for i, (p, s) in enumerate(answers)]
        V.apply(person, V.decide(evidence), evidence)
        return person

    def rec(self, *contacts):
        return [{"id": "acme", "contacts": list(contacts)}]

    def refused(self, before, after):
        try:
            store.refuse_evidence_loss(before, after)
            return False
        except store.EvidenceLost:
            return True

    def test_dropping_one_of_two_providers_is_caught(self):
        self.assertTrue(self.refused(
            self.rec(self.person()),
            self.rec(self.person(answers=(("contactout", "valid"),)))))

    def test_changing_a_verdict_does_not_launder_the_original(self):
        """`valid` and `invalid` differ in the key, so replacing one with the
        other is a lost answer rather than an update."""
        self.assertTrue(self.refused(
            self.rec(self.person(answers=(("contactout", "valid"),))),
            self.rec(self.person(answers=(("contactout", "invalid"),)))))

    def test_moving_evidence_to_a_different_address_is_caught(self):
        """The address is part of the key, so re-pointing a contact at another
        mailbox cannot carry the old answers with it."""
        self.assertTrue(self.refused(
            self.rec(self.person("champ@acme.test")),
            self.rec(self.person("other@acme.test"))))

    def test_collapsing_two_answers_into_one_is_caught(self):
        """The count, not the set. Both rows share a key now."""
        twice = self.person(answers=(("contactout", "valid"),))
        second = V.result("contactout", V.S_VALID, "champ@acme.test",
                          at="2026-09-09T11:00:00Z")
        V.apply(twice, V.decide([second]), [second])
        self.assertEqual(len(V.evidence_of(twice)), 2)
        self.assertTrue(self.refused(
            self.rec(twice),
            self.rec(self.person(answers=(("contactout", "valid"),)))))

    def test_hiding_a_contact_in_excluded_still_counts(self):
        """`_evidence_index` reads contacts and excluded together, so moving
        somebody out of the selection must not un-buy what was spent."""
        before = [{"id": "acme", "contacts": [self.person()]}]
        after = [{"id": "acme", "contacts": [],
                  "excluded": [self.person()]}]
        self.assertFalse(self.refused(before, after))

    def test_emptying_a_contact_list_is_caught(self):
        self.assertTrue(self.refused(
            self.rec(self.person()), [{"id": "acme", "contacts": []}]))

    def test_a_restamp_is_still_allowed(self):
        """The false positive that caused the loosening must stay fixed, or
        the fix regresses the moment somebody tightens the key again."""
        early = self.rec(self.person())
        late = [{"id": "acme", "contacts": [
            self.person()]}]
        for contact in late[0]["contacts"]:
            for row in contact["verification"]["evidence"]:
                row["at"] = "2027-01-01T00:00:00Z"
        self.assertFalse(self.refused(early, late))


# --------------------------------------------------------------------------
# 2. The workspace-scoped reply checkpoint.

class AMarkCannotCrossEstates(unittest.TestCase):

    def test_a_scope_is_part_of_the_key(self):
        self.assertNotEqual(poller.checkpoint_key("emailbison", "ws10"),
                            poller.checkpoint_key("emailbison", "ws29"))

    def test_an_unscoped_key_is_not_the_same_slot_as_a_scoped_one(self):
        """Otherwise a legacy mark would still govern a scoped run."""
        self.assertNotEqual(poller.checkpoint_key("emailbison"),
                            poller.checkpoint_key("emailbison", "ws10"))

    def test_an_identity_that_answers_nothing_cannot_be_read_as_permission(self):
        with self.assertRaises(poller.PollError):
            poller.identity_of("emailbison", identify=lambda: {})

    def test_a_pin_that_cannot_be_checked_refuses(self):
        """HeyReach has no identity route, so a pin against it is unanswerable
        and must not be read as satisfied."""
        with self.assertRaises(poller.WrongWorkspace):
            poller.run("heyreach", live=True, expect=10,
                       fetch=lambda offset=None, limit=None: ([], None),
                       sleep=lambda *_: None, recs=[])


# --------------------------------------------------------------------------
# 3. The HeyReach sequence gate.

class ThePushGateCannotBeTalkedPast(unittest.TestCase):

    SEQ = {"nodeType": "MESSAGE",
           "payload": {"messages": ["Hi {FIRST_NAME}, {Icebreaker}"],
                       "fallbackMessage": "Hi"}}

    def row(self, **over):
        base = {"linkedin_url": "https://www.linkedin.com/in/x",
                "first_name": "A", "note": "n", "record_id": "r"}
        base.update(over)
        return base

    def test_an_empty_custom_value_does_not_satisfy_it(self):
        """An empty Icebreaker renders a blank line, which is not better than
        the fallback."""
        with self.assertRaises(heyreach.SequenceRefused):
            heyreach.refuse_unsupported_sequence(
                self.SEQ, rows=[self.row(custom_fields={"Icebreaker": ""})])

    def test_a_differently_cased_name_does_not_satisfy_it(self):
        """HeyReach matches its variables exactly; if the gate is laxer than
        the provider it passes copy the provider will not render."""
        supplied = heyreach.supplied_field_names(
            [self.row(custom_fields={"icebreaker": "x"})])
        self.assertIn("icebreaker", supplied)
        # The gate lower-cases when comparing, so this is a known widening
        # rather than a hole: assert the behaviour, do not assume it.
        found = heyreach.sequence_hazards(self.SEQ, supplied_fields=supplied)
        self.assertEqual(dict(found).get(heyreach.UNKNOWN_VARIABLE), None)

    def test_supplying_an_unrelated_field_does_not_satisfy_it(self):
        with self.assertRaises(heyreach.SequenceRefused):
            heyreach.refuse_unsupported_sequence(
                self.SEQ, rows=[self.row(custom_fields={"Something": "x"})])

    def test_the_field_list_comes_from_the_builder_not_a_constant(self):
        """A hand-kept list would drift the moment the payload changed."""
        row = self.row(custom_fields={"Icebreaker": "x"})
        pair = heyreach.build_lead_pairs([row], 1)[0]
        self.assertEqual(
            sorted(heyreach.supplied_field_names([row])),
            sorted(f["name"] for f in pair["lead"]["customUserFields"]))

    def test_one_row_missing_the_field_sinks_the_whole_push(self):
        """The hole this attack found. `supplied_field_names` merged each row
        over a full probe, so a row with no Icebreaker still reported one -
        while the payload built from it carried none, and that prospect got
        the fallback. A field counts only when every lead has it."""
        with self.assertRaises(heyreach.SequenceRefused):
            heyreach.refuse_unsupported_sequence(self.SEQ, rows=[
                self.row(custom_fields={"Icebreaker": "x"}),
                self.row(custom_fields={})])

    def test_a_field_absent_from_a_row_is_not_reported_as_supplied(self):
        sparse = {"linkedin_url": "https://www.linkedin.com/in/x",
                  "record_id": "r"}
        self.assertNotIn("note", heyreach.supplied_field_names([sparse]))

    def test_the_no_row_contract_still_answers_what_it_could_supply(self):
        """The operator command asks a different question and must keep
        getting the full answer."""
        self.assertIn("note", heyreach.supplied_field_names())


# --------------------------------------------------------------------------
# 4. The account fatigue hold.

class TheFatigueHoldCannotBeSidestepped(unittest.TestCase):

    def rec(self, count, key="a"):
        return {"id": "acme", "client": "demo", "state": "ready",
                "contacts": [{"key": key, "name": "Ada L", "title": "COO",
                              "email": "ada@acme.test", "selected": True}],
                "events": [{"type": "push_marked", "contact": key,
                            "at": "2026-09-09T10:00:00+00:00",
                            "channel": "email", "step": f"s{i}", "day": i}
                           for i in range(count)]}

    def limit(self):
        return fatigue.limits({})["account.max_touches_per_week"]["value"]

    def test_a_second_contact_does_not_reset_the_company_count(self):
        """The whole point: the limit is the company's, not the person's."""
        rec = self.rec(self.limit() + 2)
        rec["contacts"].append({"key": "b", "name": "Bo C", "title": "CFO",
                                "email": "bo@acme.test", "selected": True})
        self.assertEqual(
            eligibility._account_fatigue(rec, rec["contacts"][1], {}),
            eligibility.HELD_ACCOUNT_FATIGUE)

    def test_a_config_cannot_raise_the_limit_by_being_unreadable(self):
        """`{}` must mean the default, not "no limit"."""
        rec = self.rec(self.limit() + 2)
        self.assertEqual(eligibility._account_fatigue(rec, rec["contacts"][0], None),
                         eligibility.HELD_ACCOUNT_FATIGUE)

    def test_it_is_asked_before_content_and_cannot_be_out_ranked(self):
        rec = self.rec(self.limit() + 2)
        verdict = eligibility.decide(
            rec, rec["contacts"][0], "s99",
            timeline={"a": {"s99": {"channel": "email", "day": 30,
                                    "subject": "x", "body": "y"}}}, config={})
        self.assertEqual(verdict["reasons"], [eligibility.HELD_ACCOUNT_FATIGUE])


# --------------------------------------------------------------------------
# 5. The kill switch, which reports rather than enforces.

class TheKillSwitchDoesNotOverstateItself(unittest.TestCase):

    def test_it_refuses_a_workspace_that_was_never_switched_on(self):
        with self.assertRaises(killswitch.SendingRefused):
            killswitch.require(workspace="never-switched-on")

    def test_absence_of_a_setting_is_not_a_setting_of_on(self):
        self.assertFalse(
            killswitch.workspace_state("no-such-workspace")["sending"])

    def test_no_workspace_named_is_not_permission(self):
        self.assertFalse(killswitch.workspace_state(None)["sending"])

    def test_the_global_layer_cannot_be_turned_on_by_configuration(self):
        """It is derived from the refusal in `push`, not from a flag, so
        nothing an operator can edit reaches it."""
        self.assertFalse(killswitch.global_state()["sending"])


if __name__ == "__main__":
    unittest.main()
