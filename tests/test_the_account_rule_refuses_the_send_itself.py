"""The account rule REFUSES A SEND, rather than returning a value nobody reads.

TASK-275's tests call `account_rule.evaluate` directly. That proves the rule
computes the right verdict; it does not prove anything is wired to it. A
helper returning REFUSE while `executionguard.authorize` sails past it is the
exact shape of `stoppedcause.py`, which has classified stop causes correctly
since 2026-09-18 and has no caller on any send path to this day.

So every test here asserts the EFFECT:

    the send gate raises `NotAuthorized`, at gate `account_rule`, and
    `spy.calls == []` - no provider call was made at all.

The spy is the method. It records every call it receives and is never wired to
a transport, so an empty call list says the code never got as far as trying.

TWO ARMS, ALWAYS. Every refusal below is paired with the case that must still
authorize. A gate that refuses everything passes every refusal test ever
written and is an outage, which is the failure
`test_a_finished_campaign_with_no_suspect_status_authorizes` was added to
`test_no_write_happens_without_every_gate.py` to catch.

REAL-STORE SHAPE, NOT AN INVENTED ONE. `TheStopShapeTheStoreActuallyCarries`
builds its stop events the way the live `work/queue.jsonl` builds all eight of
them - a `contact_stopped` carrying `outcome` and nothing else. Neither
`our_stop` nor `operator_recorded` exists on any of them, and a gate that
lifted its hold on a field that is simply absent is ISSUE-041 repeated.
"""
import datetime
import unittest
from unittest import mock

from src import account_rule, collision, executionguard

from tests.test_no_write_happens_without_every_gate import GuardTest, NOW

SIBLING = "rory-vance"


def _days_ago(n):
    return (NOW - datetime.timedelta(days=n)).replace(microsecond=0).isoformat()


class AccountRuleAtTheSendGate(GuardTest):
    """`dana-marsh` is the contact being sent to. A colleague is added beside
    her so the account can have a history that is not hers."""

    def setUp(self):
        super().setUp()
        self.rec["contacts"].append({
            "key": SIBLING, "name": "Rory Vance",
            "title": "Operations Lead", "email": "rory@brightpath.test",
            "linkedin": "roryvance", "persona": "economic_buyer",
            "angle": "operations", "sendable": True,
        })
        self.rec.setdefault("events", [])
        # THE PERSONA CAP IS LIFTED HERE, AND ONLY HERE, ON PURPOSE.
        #
        # Productive's live config sets `fatigue.account.max_active_contacts:
        # 2`. `fatigue.account_check` WARNs at exactly that number and BLOCKs
        # above it, and `executionguard`'s own `fatigue` gate demands "ok" -
        # so on the real config a SECOND persona is refused at `fatigue` and a
        # THIRD at `eligibility`, both of them before the account rule is
        # reached. Leaving the cap in place here would make every ALLOW arm
        # below fail for a reason that has nothing to do with this rule, and
        # would leave the rule itself untested.
        #
        # That collision is not swept away by lifting it: it is pinned, with
        # the live config and no lifting, by
        # `TheLiveConfigRefusesBeforeThisRuleIsReached` at the bottom of this
        # file. Read that class before concluding the rule is in force.
        self.config.setdefault("fatigue", {}).setdefault("account", {})[
            "max_active_contacts"] = 9

    # ----------------------------------------------------------- fixtures

    def touch(self, contact_key, days, channel="email"):
        """A CONFIRMED touch, which is `push_marked` and never
        `push_prepared` - see src/touch.py, which excludes the latter by
        name because every planned payload is built and none is sent."""
        self.rec["events"].append({
            "type": "push_marked", "contact": contact_key,
            "channel": channel, "at": _days_ago(days),
            "sender_id": "mina", "id": f"ev-touch-{contact_key}-{days}",
        })

    def reply(self, contact_key, days, classification):
        self.rec["events"].append({
            "type": "reply_classified", "contact": contact_key,
            "at": _days_ago(days), "classification": classification,
            "outcome": classification, "id": f"ev-reply-{contact_key}-{days}",
        })

    def stop(self, contact_key, days, **fields):
        entry = {"type": "contact_stopped", "contact": contact_key,
                 "at": _days_ago(days), "id": f"ev-stop-{contact_key}-{days}"}
        entry.update(fields)
        self.rec["events"].append(entry)

    # ------------------------------------------------------------ harness

    def send(self):
        """Run the real send gate with the account estate clear.

        `check_account` is stubbed CLEAR deliberately: `collision` is ANDed
        with the account rule, so leaving it live would let a test pass on
        `collision`'s refusal and prove nothing about this rule.
        """
        with mock.patch.object(collision, "check_linkedin_profile",
                               return_value=(collision.CLEAR, {})), \
             mock.patch.object(collision, "check_account",
                               return_value={"verdict": collision.CLEAR,
                                             "people": [],
                                             "emails_sent_total": 0,
                                             "anyone_in_sequence": False,
                                             "any_bounce": False}), \
             self.allow_killswitch(), self.allow_sender():
            auth = self.authorize()
            self.spy.write(auth, note="x")
            return auth

    def refused(self):
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            self.send()
        self.assertEqual(caught.exception.gate, "account_rule",
                         f"refused at the wrong gate: "
                         f"{caught.exception.gate}: {caught.exception.why}")
        self.assertEqual(self.spy.calls, [],
                         "a provider call was made despite the refusal")
        return caught.exception

    def authorized(self):
        auth = self.send()
        self.assertIn("account_rule", auth.gates)
        self.assertEqual(len(self.spy.calls), 1)
        return auth


class TheSameContactIsNeverContactedTwice(AccountRuleAtTheSendGate):

    def test_a_contact_already_touched_cannot_be_sent_to_again(self):
        self.touch("dana-marsh", 30)
        why = str(self.refused())
        self.assertIn("never contacted twice", why)

    def test_a_contact_touched_on_the_other_channel_is_still_refused(self):
        """Email then LinkedIn is the same person, and the account is the
        unit of outreach across both."""
        self.touch("dana-marsh", 12, channel="linkedin")
        self.refused()

    def test_an_untouched_contact_still_sends(self):
        """The arm that stops the two above from passing by refusing all."""
        self.authorized()


class TheSecondPersonaWaitsFiveDays(AccountRuleAtTheSendGate):

    def test_a_second_persona_on_day_four_is_refused_at_the_gate(self):
        self.touch(SIBLING, 4)
        why = str(self.refused())
        self.assertIn("5 days of silence", why)

    def test_a_second_persona_on_day_five_sends(self):
        self.touch(SIBLING, 5)
        self.authorized()


class TheThirdPersonaWaitsSevenMore(AccountRuleAtTheSendGate):
    """Two colleagues already contacted; Dana is the third persona."""

    def setUp(self):
        super().setUp()
        self.rec["contacts"].append({
            "key": "tam-okoro", "name": "Tam Okoro", "title": "Studio Lead",
            "email": "tam@brightpath.test", "linkedin": "tamokoro",
            "persona": "champion", "angle": "operations", "sendable": True,
        })

    def test_a_third_persona_on_day_eleven_is_refused_at_the_gate(self):
        self.touch(SIBLING, 16)
        self.touch("tam-okoro", 11)
        self.refused()

    def test_a_third_persona_on_day_twelve_sends(self):
        self.touch(SIBLING, 17)
        self.touch("tam-okoro", 12)
        self.authorized()

    def test_a_fourth_persona_is_refused_however_long_we_wait(self):
        """The rule names a first, a second and a third and stops. An
        undefined case refuses rather than inventing a fourth gap."""
        self.rec["contacts"].append({
            "key": "noa-bell", "name": "Noa Bell", "title": "Producer",
            "email": "noa@brightpath.test", "linkedin": "noabell",
            "persona": "champion", "angle": "operations", "sendable": True,
        })
        self.touch(SIBLING, 300)
        self.touch("tam-okoro", 290)
        self.touch("noa-bell", 280)
        why = str(self.refused())
        self.assertIn("does not define a fourth", why)


class AnyReplyOrUnsubscribeStopsEveryoneElse(AccountRuleAtTheSendGate):

    def test_a_human_reply_at_the_account_refuses_the_send(self):
        self.touch(SIBLING, 40)
        self.reply(SIBLING, 38, "negative")
        why = str(self.refused())
        self.assertIn("account has answered", why)

    def test_an_unsubscribe_at_the_account_refuses_the_send(self):
        self.touch(SIBLING, 40)
        self.reply(SIBLING, 38, "unsubscribe")
        why = str(self.refused())
        self.assertIn("unsubscribed", why)

    def test_an_automated_reply_does_not_refuse_the_send(self):
        """An out-of-office is not a human answering. If this refused, the
        rule would treat every holiday responder as a closed account."""
        self.touch(SIBLING, 40)
        self.reply(SIBLING, 38, "out_of_office")
        self.authorized()

    def test_a_reply_nobody_classified_refuses(self):
        """Unclassified is not automated. Nobody has said what it is, and
        'we could not tell' must never read as 'it was a robot'."""
        self.touch(SIBLING, 40)
        self.rec["events"].append({
            "type": "reply_received", "contact": SIBLING,
            "at": _days_ago(38), "id": "ev-bare-reply"})
        why = str(self.refused())
        self.assertIn("not yet classified", why)


class TheStopShapeTheStoreActuallyCarries(AccountRuleAtTheSendGate):
    """ISSUE-035 and ISSUE-041 in the same class, deliberately.

    All eight `contact_stopped` events in the live store carry `outcome` and
    nothing else. If the exception fired on a missing field, every one of them
    would lift its account's hold - which is ISSUE-041's shape: a gate that
    passes because the field it reads is absent.
    """

    def test_a_live_shaped_stop_carrying_neither_field_still_holds(self):
        self.touch(SIBLING, 40)
        self.stop(SIBLING, 2, outcome="not_now")
        why = str(self.refused())
        self.assertIn("cannot prove is ours", why)

    def test_a_stop_we_made_without_an_operator_move_still_holds(self):
        """One arm is not the exception. Both are."""
        self.touch(SIBLING, 40)
        self.stop(SIBLING, 2, reason="operator_move", our_stop=True)
        self.refused()

    def test_an_operator_move_on_a_stop_that_is_not_ours_still_holds(self):
        """The other single arm, so neither can lift the hold alone."""
        self.touch(SIBLING, 40)
        self.stop(SIBLING, 2, reason="provider_stop", operator_recorded=True)
        self.refused()

    def test_an_external_stop_holds_however_it_is_labelled(self):
        self.touch(SIBLING, 40)
        self.stop(SIBLING, 2, reason="bounce", our_stop=False,
                  operator_recorded=False)
        self.refused()

    def test_our_own_stop_with_an_operator_move_does_not_hold_the_account(self):
        """ISSUE-035. This is the one arm that WIDENS who may be contacted,
        and it is the reason this whole change wants an adversarial review."""
        self.touch(SIBLING, 40)
        self.stop(SIBLING, 2, reason="operator_move", our_stop=True,
                  operator_recorded=True)
        self.authorized()

    def test_a_stop_cannot_outrank_the_same_contact_rule(self):
        """An excused stop is a reason to approach somebody ELSE at the
        account. It is never a reason to write to the same person twice."""
        self.touch("dana-marsh", 40)
        self.stop("dana-marsh", 2, reason="operator_move", our_stop=True,
                  operator_recorded=True)
        why = str(self.refused())
        self.assertIn("never contacted twice", why)

    def test_a_stop_cannot_outrank_a_human_reply(self):
        self.touch(SIBLING, 40)
        self.reply(SIBLING, 30, "negative")
        self.stop(SIBLING, 2, reason="operator_move", our_stop=True,
                  operator_recorded=True)
        why = str(self.refused())
        self.assertIn("account has answered", why)


class LinkedInReplyStateThatCannotBeRead(AccountRuleAtTheSendGate):
    """ISSUE-041. LinkedIn replies are ingested against `heyreach_lead_id`.
    Exactly one contact in the 1,065 in `work/queue.jsonl` carries one, and it
    is the operator's own test identity - so for every real account, a
    LinkedIn reply has no path to land."""

    def test_a_linkedin_touch_with_no_heyreach_binding_refuses(self):
        self.touch(SIBLING, 40, channel="linkedin")
        why = str(self.refused())
        self.assertIn("no path to reach us", why)

    def test_the_same_account_with_a_heyreach_binding_sends(self):
        """The arm that proves the refusal is about the missing binding and
        not about LinkedIn."""
        self.touch(SIBLING, 40, channel="linkedin")
        self.rec["contacts"][1]["heyreach_lead_id"] = "ACoAA-synthetic"
        self.authorized()

    def test_an_email_only_history_is_not_refused_for_this(self):
        """No LinkedIn touch means no missing LinkedIn reply state to worry
        about. Refusing here would refuse the entire email estate."""
        self.touch(SIBLING, 40, channel="email")
        self.authorized()


class TheCacheIsNotConsulted(AccountRuleAtTheSendGate):
    """Handoff §7 item 1. `work/stage/last-touch.json` is stale by 109 days on
    the measured snapshot, and `last_touch_at` is never written onto a queue
    record by anything in `src/`, so a gap computed from it never refuses."""

    def test_a_stale_cache_cannot_satisfy_the_gap(self):
        self.touch(SIBLING, 1)
        self.rec["contacts"][1]["last_touch_at"] = _days_ago(200)
        self.refused()

    def test_an_absent_cache_cannot_manufacture_a_gap(self):
        """No `last_touch_at` anywhere, and the event log still refuses."""
        self.touch(SIBLING, 2)
        self.assertNotIn("last_touch_at", self.rec["contacts"][1])
        self.refused()

    def test_the_module_never_reads_the_field_at_all(self):
        """Stated as source, because the two tests above would also pass if
        the field were read and merely happened to agree."""
        import inspect
        from src import account_rule as mod
        source = inspect.getsource(mod)
        offenders = [line.strip() for line in source.splitlines()
                     if 'get("last_touch_at")' in line
                     or "get('last_touch_at')" in line]
        self.assertEqual(offenders, [])


class APayloadIsNotASend(AccountRuleAtTheSendGate):
    """`push_prepared` must never count as a touch, and this is the class that
    pins it.

    ADDED AFTER MUTATION TESTING FOUND NOTHING PINNED IT. Flipping
    `account.touches(..., confirmed_only=True)` to `False` in
    `src/account_rule.py` left all 51 other tests GREEN. That mutation is the
    single most dangerous one available here: every planned payload is built
    and, on this build, none is sent, so counting one as a touch makes every
    account with a drafted email read as already worked - and the rule would
    then refuse the entire estate while reporting that it was staggering it.

    It is also the exact defect TASK-275 shipped in its own fixture, which
    recorded `push_prepared` and called it a confirmed send. See
    `src/touch.py`, which excludes it by name.
    """

    def prepared(self, contact_key, days):
        """A payload built for somebody, and never sent."""
        self.rec["events"].append({
            "type": "push_prepared", "contact": contact_key,
            "channel": "email", "at": _days_ago(days),
            "sender_id": "mina", "state": "sent", "confirmed": True,
            "id": f"ev-prep-{contact_key}-{days}"})

    def test_a_prepared_payload_for_this_contact_does_not_refuse_them(self):
        """Dana has a payload built yesterday and has never been written to.
        Refusing her would strand every contact whose copy is drafted."""
        self.prepared("dana-marsh", 1)
        self.authorized()

    def test_a_prepared_payload_for_a_colleague_does_not_start_the_stagger(self):
        self.prepared(SIBLING, 1)
        verdict = account_rule.evaluate(self.rec, "dana-marsh")
        self.assertEqual(verdict["verdict"], account_rule.ALLOW)
        self.assertEqual(verdict["rule"], "first_persona",
                         "a built payload must not read as a contacted "
                         "persona; see src/touch.py")

    def test_the_same_event_as_push_marked_does_refuse(self):
        """The other arm. Identical shape, one word different, and that word
        is the whole difference between planned and sent."""
        self.touch(SIBLING, 1)
        verdict = account_rule.evaluate(self.rec, "dana-marsh")
        self.assertEqual(verdict["verdict"], account_rule.REFUSE)
        self.assertEqual(verdict["rule"], "stagger_gap")

    def test_a_prepared_payload_never_satisfies_a_gap_either(self):
        """The dangerous direction: a stale `push_prepared` must not be the
        thing that makes an account look old enough to touch again."""
        self.touch(SIBLING, 1)
        self.prepared(SIBLING, 400)
        verdict = account_rule.evaluate(self.rec, "dana-marsh")
        self.assertEqual(verdict["verdict"], account_rule.REFUSE,
                         "the confirmed touch is one day old; a 400-day-old "
                         "payload must not age the account")


class TheLiveConfigRefusesBeforeThisRuleIsReached(unittest.TestCase):
    """THE OPERATOR'S STAGGER IS UNREACHABLE ON PRODUCTIVE'S LIVE CONFIG, and
    this class exists so that fact cannot be lost.

    `config/clients/productive.yaml` sets `fatigue.account.max_active_contacts:
    2`, configured rather than defaulted, with the comment "One email track
    plus one LinkedIn track is what the providers permit."
    `fatigue.account_check` WARNs when the count WOULD EQUAL that limit and
    BLOCKs above it. `executionguard` then demands `fatigue` be exactly "ok",
    and `eligibility._account_fatigue` holds on BLOCK.

    The arithmetic, measured rather than reasoned:

        1 colleague already touched  -> warn   -> the `fatigue` gate refuses
        2 colleagues already touched -> block  -> `eligibility` refuses

    So a SECOND persona - which the operator's rule allows after five days of
    silence - is refused today whatever this rule says, and a THIRD is refused
    twice over. The US second-persona batch is exactly this case.

    THIS IS NOT FIXED HERE. `config/clients/productive.yaml` belongs to
    another lane this morning and raising a send cap is an operator decision,
    not a test's. The number is named so somebody can change it deliberately.
    """

    def limits(self):
        from src import clients, fatigue
        return fatigue.limits(clients.load("productive"))

    def test_the_cap_is_two_and_it_is_configured_not_defaulted(self):
        cap = self.limits()["account.max_active_contacts"]
        self.assertEqual(cap["value"], 2,
                         "if this changed, the stagger may now be reachable "
                         "and this whole class should be re-read")
        self.assertTrue(cap["configured"])

    def test_a_second_persona_warns_on_the_live_config(self):
        from src import clients, fatigue
        verdict = fatigue.account_check(self.record(1), config=clients.load("productive"),
                                        contact_key="dana")
        self.assertEqual(verdict["state"], fatigue.WARN,
                         "a WARN is refused by executionguard's fatigue gate, "
                         "which requires 'ok'")

    def test_a_third_persona_blocks_on_the_live_config(self):
        from src import clients, fatigue
        verdict = fatigue.account_check(self.record(2), config=clients.load("productive"),
                                        contact_key="dana")
        self.assertEqual(verdict["state"], fatigue.BLOCK)

    def test_a_first_persona_is_fine_so_this_is_not_a_blanket_refusal(self):
        from src import clients, fatigue
        verdict = fatigue.account_check(self.record(0), config=clients.load("productive"),
                                        contact_key="dana")
        self.assertEqual(verdict["state"], fatigue.OK)

    def record(self, colleagues_touched):
        contacts = [{"key": "dana", "name": "D", "email": "d@b.test",
                     "sendable": True}]
        events = []
        for i in range(colleagues_touched):
            key = f"sib{i}"
            contacts.append({"key": key, "name": "S",
                             "email": f"s{i}@b.test", "sendable": True})
            events.append({"type": "push_marked", "contact": key,
                           "channel": "email", "at": _days_ago(30 + i * 10),
                           "sender_id": "mina", "id": f"ev-{i}"})
        return {"id": "r", "client": "productive", "domain": "b.test",
                "company": "B", "state": "verified",
                "contacts": contacts, "events": events}


class TheOperatorsTestIdentityIsNotAProspect(unittest.TestCase):

    def test_the_test_record_is_recognised(self):
        self.assertTrue(account_rule.is_test_identity(
            {"id": "crosschannel-stop-test-2026-09-23"}))

    def test_the_test_contact_key_is_recognised(self):
        self.assertTrue(account_rule.is_test_identity(
            {"id": "other"}, "zvonimir-beslic"))

    def test_an_ordinary_record_is_not(self):
        self.assertFalse(account_rule.is_test_identity(
            {"id": "brightpath-test"}, "dana-marsh"))


if __name__ == "__main__":
    unittest.main()
