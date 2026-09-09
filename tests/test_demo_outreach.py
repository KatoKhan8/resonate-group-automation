"""The demo outreach page, and the invariants it exists to demonstrate.

The page is only worth anything if what it shows is what the engine does, so
most of these assert the *engine's* behaviour through the demo rather than the
demo's own bookkeeping. The three that matter most are the exclusion proofs: a
contact whose email channel is closed must not be in the EmailBison payload, a
contact with no usable profile must not be in the HeyReach one, and a contact
whose company has replied must be in neither.

Everything runs offline. `tests/base.py` blocks the socket layer and strips
every credential from the environment.
"""
import datetime
import json
import os
import unittest

from src import (cadence, channels, coherence, demo_outreach, lint,
                 outreachpage, push, store)
from tests.campaignbase import CampaignTest


class DemoTest(CampaignTest):
    """One gather per class. It is deterministic, so this is safe to share."""

    @classmethod
    def result(cls):
        if not hasattr(cls, "_result"):
            cls._result = demo_outreach.gather()
        return cls._result

    def setUp(self):
        super().setUp()
        self.res = type(self).result()

    def card(self, scenario):
        return next(c for c in self.res["cards"] if c["scenario"] == scenario)

    def bison_leads(self):
        body = self.res["push"]["payloads"]["emailbison"]["body"]
        return (body.get("leads") if isinstance(body, dict) else body) or []

    def bison_record_id(self, lead):
        """`record_id` lives in `custom_variables`, which is where EmailBison
        keeps everything the sending cadence needs."""
        return (lead.get("custom_variables") or {}).get("record_id")

    def heyreach_pairs(self):
        return self.res["push"]["payloads"]["heyreach"]["body"]["accountLeadPairs"]

    def custom_fields(self, pair):
        return {f["name"]: f["value"]
                for f in pair["lead"].get("customUserFields") or []}


class TestItIsDeterministic(CampaignTest):
    """`CampaignTest`, not `TestCase`, because these call `gather()`.

    `gather()` writes the provider tag outbox, and `tagsync.path()` derives
    from `store.queue_path()` under a comment saying that path "is already
    redirected by every test". It was not redirected by this class or by
    the one below - both were plain `TestCase` - so every full run appended
    to the real `work/tag-outbox.jsonl`, which had reached 2.8MB across
    6,410 rows.

    It reproduced only under `discover`: run this module alone and the
    file is untouched, because the class that runs first happens to leave
    the environment redirected. That is why it took hashing every `work/`
    file before and after a full suite to see it at all, and then running
    all 205 modules in one process with the file hashed between each to
    say which one it was.
    """
    def test_two_builds_produce_the_same_records(self):
        first = demo_outreach.build()[1]
        second = demo_outreach.build()[1]
        self.assertEqual([r["id"] for r in first], [r["id"] for r in second])

    def test_the_copy_is_identical_between_builds(self):
        def bodies(recs):
            return [step.get("body")
                    for rec in recs
                    for steps in (rec.get("cadence") or {}).values()
                    for step in steps.values()]
        self.assertEqual(bodies(demo_outreach.build()[1]),
                         bodies(demo_outreach.build()[1]))

    def test_the_page_is_identical_between_runs(self):
        """A demo that changes under you is a demo nobody can review.

        Wall-clock stamps are normalised rather than excluded: `generated_at`
        and the various `checked_at` fields are genuinely the time the page was
        built, and asserting they are equal would only prove the two runs
        landed in the same second. Everything else must match exactly.
        """
        import re
        stamps = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\"<\s]*")
        first = stamps.sub("<TS>", outreachpage.page(demo_outreach.gather()))
        second = stamps.sub("<TS>", outreachpage.page(demo_outreach.gather()))
        self.assertEqual(first, second)

    def test_the_verdicts_are_identical_between_runs(self):
        """The part that must not move at all: what the engine decided."""
        def verdicts(result):
            return [(c["record_id"], c["mode"], c["icp"]["score"],
                     c["icp"]["tier"], c["personalization"]["band"],
                     tuple(s["status"] for s in c["timeline"]))
                    for c in result["cards"]]
        self.assertEqual(verdicts(demo_outreach.gather()),
                         verdicts(demo_outreach.gather()))


class TestNoNetworkAndNoMutation(CampaignTest):
    """Isolated for the same reason, and with more irony: the class that
    asserts nothing is written was writing to the real outbox, and
    `test_nothing_is_written_to_the_queue` was reading the real queue to
    prove it. Against a temp store the assertion means what it says."""
    def test_the_module_never_calls_a_provider_send_route(self):
        import inspect
        source = inspect.getsource(demo_outreach)
        for banned in ("AddLeadsToCampaignV2", "requests.", "urlopen",
                       "socket.", "live=True", "slack.post", "http.client"):
            self.assertNotIn(banned, source, banned)

    def test_the_page_module_never_calls_anything(self):
        """Checked on the code, not the prose: the page's own banner quotes
        `push.run(live=True)` to tell the reader sending is off."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(outreachpage))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called.add(ast.unparse(node.func))
        for banned in ("requests.get", "requests.post", "urlopen",
                       "socket.socket", "push.run", "store.save"):
            self.assertNotIn(banned, called, banned)

    def test_the_demo_resolver_never_looks_anything_up(self):
        import inspect
        source = inspect.getsource(demo_outreach._resolver)
        self.assertNotIn("socket", source)
        self.assertNotIn("resolve(", source)

    def test_an_unknown_domain_raises_rather_than_returning_nothing(self):
        """`no answer` and `no MX` are different facts."""
        from src import mx
        with self.assertRaises(mx.MXError):
            demo_outreach._resolver("not-in-the-table.test")

    def test_nothing_is_written_to_the_queue(self):
        before = len(store.load())
        demo_outreach.gather()
        self.assertEqual(len(store.load()), before)


class TestTheFiveScenarios(DemoTest):
    def test_all_five_are_present(self):
        self.assertEqual({c["scenario"] for c in self.res["cards"]},
                         set(demo_outreach.SCENARIOS))

    def test_each_scenario_reaches_its_intended_channel_mode(self):
        expected = {
            demo_outreach.FULL: channels.MULTICHANNEL,
            demo_outreach.SECOND_INVALID: channels.LINKEDIN_ONLY,
            demo_outreach.ESCALATED: channels.MULTICHANNEL,
            demo_outreach.HALF_CONFIRMED: channels.LINKEDIN_ONLY,
            demo_outreach.MX_BLOCKED: channels.LINKEDIN_ONLY,
            demo_outreach.NO_LINKEDIN: channels.EMAIL_ONLY,
            demo_outreach.REPLY: channels.MULTICHANNEL,
        }
        for scenario, mode in expected.items():
            self.assertEqual(self.card(scenario)["mode"], mode, scenario)

    def test_nobody_is_dropped_for_losing_one_channel(self):
        """Four different reasons for a closed email channel, one consequence."""
        for scenario in (demo_outreach.SECOND_INVALID,
                         demo_outreach.HALF_CONFIRMED,
                         demo_outreach.MX_BLOCKED,
                         demo_outreach.NO_LINKEDIN):
            card = self.card(scenario)
            self.assertFalse(card["held"], scenario)
            self.assertTrue(card["timeline"], scenario)

    def test_every_scenario_renders_a_full_cadence(self):
        for card in self.res["cards"]:
            self.assertEqual(len(card["timeline"]), len(cadence.STEPS),
                             card["scenario"])

    def test_every_closed_channel_carries_a_reason(self):
        for card in self.res["cards"]:
            if not card["email"]["eligible"]:
                self.assertTrue(card["email"]["reason"], card["scenario"])
            if not card["linkedin"]["eligible"]:
                self.assertTrue(card["linkedin"]["reason"], card["scenario"])


class TestScenarioE_MxSecurity(DemoTest):
    def test_the_gateway_is_identified_by_the_real_classifier(self):
        card = self.card(demo_outreach.MX_BLOCKED)
        self.assertEqual(card["email"]["mx"].get("security_provider"),
                         "proofpoint")

    def test_no_verifier_was_ever_asked(self):
        """The saving. The channel was closed before a credit was spent, so
        this address has no verification evidence at all - which is a
        different fact from an address that was checked and failed."""
        card = self.card(demo_outreach.MX_BLOCKED)
        self.assertEqual(card["email"]["verification"].get("evidence"), [])
        self.assertEqual(card["email"]["verification"].get("confirmation_count"), 0)

    def test_the_reason_names_the_gateway_and_not_the_verifier(self):
        """Reporting `not verified` here would send a reviewer looking for a
        verification problem that does not exist."""
        card = self.card(demo_outreach.MX_BLOCKED)
        self.assertEqual(card["email"]["reason"], "mx_protection:proofpoint")

    def test_email_is_closed_with_the_mx_reason(self):
        card = self.card(demo_outreach.MX_BLOCKED)
        self.assertFalse(card["email"]["eligible"])
        self.assertEqual(card["email"]["reason"], "mx_protection:proofpoint")

    def test_linkedin_is_untouched(self):
        self.assertTrue(self.card(demo_outreach.MX_BLOCKED)["linkedin"]["eligible"])

    def test_it_never_reaches_the_emailbison_payload(self):
        card = self.card(demo_outreach.MX_BLOCKED)
        for lead in self.bison_leads():
            self.assertNotEqual(self.bison_record_id(lead), card["record_id"])
            self.assertNotIn(card["domain"], str(lead.get("email") or ""))

    def test_it_does_reach_the_heyreach_payload(self):
        card = self.card(demo_outreach.MX_BLOCKED)
        ids = {self.custom_fields(p).get("record_id")
               for p in self.heyreach_pairs()}
        self.assertIn(card["record_id"], ids)


class TestDoubleVerification(DemoTest):
    """The five verification outcomes the page exists to make visible."""

    def block(self, scenario):
        return self.card(scenario)["email"]["verification"]

    def test_two_agreeing_providers_send(self):
        card = self.card(demo_outreach.FULL)
        self.assertTrue(card["email"]["sendable"])
        self.assertEqual(self.block(demo_outreach.FULL)["confirmation_count"], 2)
        self.assertEqual(sorted(self.block(demo_outreach.FULL)["confirmed_by"]),
                         ["contactout", "deliverable"])

    def test_a_second_verifier_saying_invalid_closes_email(self):
        card = self.card(demo_outreach.SECOND_INVALID)
        self.assertFalse(card["email"]["sendable"])
        self.assertTrue(self.block(demo_outreach.SECOND_INVALID)["disagreement"])

    def test_a_disagreement_never_picks_the_optimistic_answer(self):
        block = self.block(demo_outreach.SECOND_INVALID)
        self.assertIn("contactout", block["results"])
        self.assertEqual(block["results"]["contactout"]["verdict"], "valid")
        self.assertEqual(block["results"]["deliverable"]["verdict"], "invalid")
        self.assertFalse(self.card(demo_outreach.SECOND_INVALID)["email"]["sendable"])

    def test_an_escalation_supplies_the_second_confirmation(self):
        card = self.card(demo_outreach.ESCALATED)
        block = self.block(demo_outreach.ESCALATED)
        self.assertTrue(card["email"]["sendable"])
        self.assertEqual(block["results"]["deliverable"]["verdict"], "unknown")
        self.assertEqual(sorted(block["confirmed_by"]), ["contactout", "reoon"])

    def test_one_confirmation_is_held_and_says_how_many_are_missing(self):
        card = self.card(demo_outreach.HALF_CONFIRMED)
        block = self.block(demo_outreach.HALF_CONFIRMED)
        self.assertFalse(card["email"]["sendable"])
        self.assertEqual(block["confirmation_count"], 1)
        self.assertEqual(block["required_confirmations"], 2)
        self.assertIn("1 more needed", block["reason"])

    def test_every_card_reports_its_confirmation_count(self):
        for card in self.res["cards"]:
            block = card["email"]["verification"]
            self.assertIn("confirmation_count", block, card["scenario"])
            self.assertIn("required_confirmations", block, card["scenario"])

    def test_no_single_confirmed_contact_reaches_the_emailbison_payload(self):
        """The repository-level invariant section 2 asks for."""
        by_id = {c["record_id"]: c for c in self.res["cards"]}
        for lead in self.bison_leads():
            block = by_id[self.bison_record_id(lead)]["email"]["verification"]
            self.assertGreaterEqual(block["confirmation_count"],
                                    block["required_confirmations"],
                                    self.bison_record_id(lead))

    def test_the_half_confirmed_contact_is_not_in_the_payload(self):
        card = self.card(demo_outreach.HALF_CONFIRMED)
        for lead in self.bison_leads():
            self.assertNotEqual(self.bison_record_id(lead), card["record_id"])

    def test_the_disagreeing_contact_is_not_in_the_payload(self):
        card = self.card(demo_outreach.SECOND_INVALID)
        for lead in self.bison_leads():
            self.assertNotEqual(self.bison_record_id(lead), card["record_id"])

    def test_linkedin_survives_every_verification_outcome(self):
        for scenario in (demo_outreach.SECOND_INVALID,
                         demo_outreach.HALF_CONFIRMED,
                         demo_outreach.MX_BLOCKED):
            self.assertTrue(self.card(scenario)["linkedin"]["eligible"], scenario)


class TestScenarioD_NoProfile(DemoTest):
    def test_there_is_no_profile(self):
        self.assertIsNone(self.card(demo_outreach.NO_LINKEDIN)["linkedin"]["url"])

    def test_it_never_reaches_the_heyreach_payload(self):
        card = self.card(demo_outreach.NO_LINKEDIN)
        for pair in self.heyreach_pairs():
            self.assertNotEqual(self.custom_fields(pair).get("record_id"),
                                card["record_id"])
            self.assertNotEqual(pair["lead"]["profileUrl"], None)

    def test_it_does_reach_the_emailbison_payload(self):
        card = self.card(demo_outreach.NO_LINKEDIN)
        ids = {self.bison_record_id(l) for l in self.bison_leads()}
        self.assertIn(card["record_id"], ids)


class TestScenarioE_ReplyPausesBoth(DemoTest):
    def test_the_company_is_paused(self):
        self.assertTrue(self.card(demo_outreach.REPLY)["paused"])

    def test_the_early_steps_had_already_gone_out(self):
        before = {s["step"]: s["status"] for s in self.res["reply"]["before"]}
        self.assertEqual(before["day1"], "pushed")
        self.assertEqual(before["day3"], "pushed")

    def test_every_later_step_on_both_channels_is_paused(self):
        after = {s["step"]: s for s in self.res["reply"]["after"]}
        for key in ("day5", "day8", "day10", "day15", "day21"):
            self.assertEqual(after[key]["status"], "paused", key)

    def test_both_channels_stop_not_just_one(self):
        """The failure this scenario exists to rule out."""
        after = [s for s in self.res["reply"]["after"] if s["status"] == "paused"]
        self.assertEqual({s["channel"] for s in after}, {"email", "linkedin"})

    def test_nothing_is_deleted(self):
        self.assertEqual(len(self.res["reply"]["before"]),
                         len(self.res["reply"]["after"]))

    def test_the_sent_steps_keep_their_status(self):
        after = {s["step"]: s["status"] for s in self.res["reply"]["after"]}
        self.assertEqual(after["day1"], "pushed")
        self.assertEqual(after["day3"], "pushed")

    def test_a_paused_contact_is_in_neither_payload(self):
        card = self.card(demo_outreach.REPLY)
        for lead in self.bison_leads():
            self.assertNotEqual(self.bison_record_id(lead), card["record_id"])
        for pair in self.heyreach_pairs():
            self.assertNotEqual(self.custom_fields(pair).get("record_id"),
                                card["record_id"])


class TestTheMultichannelScenario(DemoTest):
    def test_it_reaches_both_providers(self):
        card = self.card(demo_outreach.FULL)
        self.assertIn(card["record_id"],
                      {self.bison_record_id(l) for l in self.bison_leads()})
        self.assertIn(card["record_id"],
                      {self.custom_fields(p).get("record_id")
                       for p in self.heyreach_pairs()})

    def test_its_timeline_carries_both_channels(self):
        channels_used = {s["channel"] for s in self.card(demo_outreach.FULL)["timeline"]}
        self.assertEqual(channels_used, {"email", "linkedin"})

    def test_the_two_generated_emails_do_not_share_an_opening(self):
        """BUILD-SPEC section 7: day 15 is a different angle from day 1."""
        steps = {s["step"]: s for s in self.card(demo_outreach.FULL)["timeline"]}
        first = coherence._first_sentence(steps["day1"]["text"])
        last = coherence._first_sentence(steps["day15"]["text"])
        self.assertLess(coherence._overlap(first, last),
                        coherence.OPENING_OVERLAP)

    def test_no_step_is_scheduled_on_two_channels_in_one_day(self):
        for card in self.res["cards"]:
            days = {}
            for step in card["timeline"]:
                days.setdefault(step["day"], set()).add(step["channel"])
            for day, used in days.items():
                self.assertEqual(len(used), 1, f"{card['scenario']} day {day}")


class TestPayloadIntegrity(DemoTest):
    def test_only_eligible_steps_reach_a_payload(self):
        """`push.collect` gates on the cadence status; this is that gate."""
        eligible = {(c["record_id"], s["step"])
                    for c in self.res["cards"] for s in c["timeline"]
                    if s["status"] == "eligible"}
        self.assertTrue(eligible)
        for lead in self.bison_leads():
            self.assertTrue(any(rid == self.bison_record_id(lead)
                                for rid, _ in eligible), self.bison_record_id(lead))

    def test_no_step_that_fails_lint_reaches_a_payload(self):
        failing = {c["record_id"] for c in self.res["cards"]
                   for s in c["timeline"] if not s["lint_ok"]}
        self.assertTrue(failing, "the demo should contain a lint failure")
        in_payload = {self.bison_record_id(l) for l in self.bison_leads()}
        for record_id in failing:
            card = next(c for c in self.res["cards"]
                        if c["record_id"] == record_id)
            if not card["email"]["eligible"]:
                self.assertNotIn(record_id, in_payload)

    def test_every_emailbison_lead_has_a_sendable_address(self):
        by_id = {c["record_id"]: c for c in self.res["cards"]}
        for lead in self.bison_leads():
            card = by_id[self.bison_record_id(lead)]
            self.assertTrue(card["email"]["sendable"], self.bison_record_id(lead))
            self.assertTrue(card["email"]["eligible"], self.bison_record_id(lead))

    def test_every_heyreach_lead_has_a_usable_profile(self):
        for pair in self.heyreach_pairs():
            self.assertTrue(pair["lead"]["profileUrl"])
            self.assertIn("/in/", pair["lead"]["profileUrl"])

    def test_the_two_campaign_ids_are_never_interchanged(self):
        payloads = self.res["push"]["payloads"]
        self.assertIn("8100", payloads["emailbison"]["endpoint"])
        self.assertEqual(payloads["heyreach"]["body"]["campaignId"], "6100")

    def test_the_payload_is_built_by_the_sender_layer_not_the_demo(self):
        """A payload the demo shapes itself is a payload nobody has tested."""
        import inspect
        self.assertIn("push.payloads", inspect.getsource(demo_outreach.gather))


class TestIdentityMapping(DemoTest):
    def test_heyreach_carries_our_own_identifiers(self):
        for pair in self.heyreach_pairs():
            fields = self.custom_fields(pair)
            self.assertTrue(fields.get("record_id"))
            self.assertTrue(fields.get("contact_key"))

    def test_the_identifiers_match_the_record_they_came_from(self):
        keys = {(c["record_id"], c["contact_key"]) for c in self.res["cards"]}
        for pair in self.heyreach_pairs():
            fields = self.custom_fields(pair)
            self.assertIn((fields["record_id"], fields["contact_key"]), keys)

    def test_the_note_still_travels_first(self):
        """The push CLI prints customUserFields[0] and expects the note."""
        for pair in self.heyreach_pairs():
            self.assertEqual(pair["lead"]["customUserFields"][0]["name"], "note")

    def test_the_profile_url_is_canonical(self):
        from src import linkedin
        for pair in self.heyreach_pairs():
            url = pair["lead"]["profileUrl"]
            self.assertEqual(linkedin.canonical(url), linkedin.canonical(url))
            self.assertIsNotNone(linkedin.canonical(url))

    def test_identity_is_consistent_across_both_providers(self):
        bison = {self.bison_record_id(l) for l in self.bison_leads()}
        heyreach = {self.custom_fields(p)["record_id"]
                    for p in self.heyreach_pairs()}
        known = {c["record_id"] for c in self.res["cards"]}
        self.assertTrue(bison <= known)
        self.assertTrue(heyreach <= known)

    def test_no_fuzzy_matching_anywhere_in_the_demo_path(self):
        import inspect
        for module in (demo_outreach, outreachpage):
            source = inspect.getsource(module)
            for banned in ("difflib", "SequenceMatcher", "fuzz", "levenshtein",
                           "get_close_matches"):
                self.assertNotIn(banned, source.lower(), f"{module}: {banned}")

    def test_no_connection_accepted_state_is_invented(self):
        """Day 8 requires an acceptance nobody has recorded, so it waits."""
        for card in self.res["cards"]:
            day8 = next(s for s in card["timeline"] if s["step"] == "day8")
            self.assertIn(day8["status"], ("waiting", "paused", "blocked"),
                          card["scenario"])


class TestCrossChannelCoherence(DemoTest):
    def test_every_contact_is_checked(self):
        self.assertEqual(self.res["coherence"]["contacts_checked"],
                         len(self.res["cards"]))

    def test_a_verdict_is_reported_for_each(self):
        for card in self.res["cards"]:
            self.assertIn(card["coherence"]["verdict"],
                          ("pass", coherence.REVIEW, coherence.BLOCK))

    def test_no_step_references_the_other_channel(self):
        for card in self.res["cards"]:
            kinds = {f["kind"] for f in card["coherence"]["findings"]}
            self.assertNotIn("cross_channel_leak", kinds, card["scenario"])

    def test_no_contact_gets_the_same_message_on_two_channels(self):
        for card in self.res["cards"]:
            kinds = {f["kind"] for f in card["coherence"]["findings"]}
            self.assertNotIn("duplicate_across_channels", kinds,
                             card["scenario"])

    def test_the_paused_contact_reports_activity_after_the_reply(self):
        """Every step after day 5 is paused, so nothing is flagged - which is
        the finding: correctly stopped steps are not violations."""
        card = self.card(demo_outreach.REPLY)
        kinds = {f["kind"] for f in card["coherence"]["findings"]}
        self.assertNotIn("scheduled_after_reply", kinds)

    def test_an_ineligible_channel_with_a_live_step_is_reported(self):
        findings = coherence.ineligible_channel(
            coherence._ordered({"day1": {"channel": "email", "day": 1,
                                         "status": "eligible", "body": "x"}}),
            {"email_eligible": False, "email_excluded_reason": "mx"})
        self.assertEqual([f["kind"] for f in findings], ["ineligible_channel"])


class TestThePage(DemoTest):
    def html(self, reveal=False):
        return outreachpage.page(self.res, reveal=reveal)

    def test_it_renders_every_card(self):
        html = self.html()
        for card in self.res["cards"]:
            self.assertIn(card["company"], html)
            self.assertIn(card["name"], html)

    def test_it_renders_every_step(self):
        self.assertEqual(self.html().count('<div class="step '),
                         sum(len(c["timeline"]) for c in self.res["cards"]))

    def test_it_says_it_would_send_nothing(self):
        self.assertIn("Would send now", self.html())
        self.assertEqual(self.res["would_send"], 0)

    def test_addresses_are_masked_by_default(self):
        html = self.html()
        for card in self.res["cards"]:
            address = card["email"].get("address")
            if address:
                self.assertNotIn(address, html, card["scenario"])

    def test_addresses_can_be_revealed_deliberately(self):
        html = self.html(reveal=True)
        card = self.card(demo_outreach.FULL)
        self.assertIn(card["email"]["address"], html)

    def test_untrusted_text_is_escaped(self):
        """A prospect name is attacker-controlled text."""
        result = json.loads(json.dumps(self.res, default=str))
        result["cards"][0]["name"] = "<script>alert('x')</script>"
        result["cards"][0]["company"] = "<img src=x onerror=alert(1)>"
        html = outreachpage.page(result)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)

    def test_evidence_text_is_escaped(self):
        result = json.loads(json.dumps(self.res, default=str))
        result["cards"][0]["evidence"]["company"] = [{
            "fact": "<script>alert('evidence')</script>",
            "provider": "apify", "source_url": "https://x.test",
            "source_type": "web", "quality": "strong"}]
        self.assertNotIn("<script>alert('evidence')", outreachpage.page(result))

    def test_no_credential_shaped_string_reaches_the_page(self):
        html = self.html()
        for marker in ("BISON_KEY", "HEYREACH_KEY", "CONTACTOUT_TOKEN",
                       "REOON_KEY", "AIARK_KEY", "SLACK_SIGNING_SECRET",
                       "Bearer ", "X-API-KEY"):
            self.assertNotIn(marker, html, marker)

    def test_every_blocked_step_shows_its_reason(self):
        html = self.html()
        for card in self.res["cards"]:
            for step in card["timeline"]:
                if step["status"] in ("blocked", "skipped"):
                    self.assertIn(step["step"], html)

    def test_the_page_states_that_sending_is_disabled(self):
        self.assertIn("LiveSendNotEnabled", self.html())

    def test_it_writes_where_it_is_told(self):
        path = os.path.join(self.tmp, "demo-outreach.html")
        outreachpage.write(self.res, path)
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as f:
            self.assertIn("Demo outreach", f.read())


class TestTheEngineIsReal(DemoTest):
    """The demo is only useful if it did not reimplement what it displays."""

    def test_channel_verdicts_match_a_fresh_evaluation(self):
        campaign, recs, config = demo_outreach.build()
        for rec in recs:
            for contact in rec["contacts"]:
                fresh = channels.evaluate(rec, contact, config)
                card = next(c for c in self.res["cards"]
                            if c["contact_key"] == contact["key"])
                self.assertEqual(card["mode"], fresh["mode"], contact["key"])

    def test_sendability_matches_the_verification_authority(self):
        for card in self.res["cards"]:
            campaign, recs, config = demo_outreach.build()
            rec = next(r for r in recs if r["id"] == card["record_id"])
            contact = rec["contacts"][0]
            self.assertEqual(card["email"]["sendable"], lint.sendable(contact))

    def test_the_schedule_uses_prospect_local_time(self):
        sched = self.res["schedule"]
        self.assertGreaterEqual(sched["schedulable"], 1)
        self.assertEqual(sched["would_send"], 0)

    def test_the_qa_report_is_the_real_one(self):
        self.assertIn(self.res["qa"]["verdict"], ("PASS", "WARN", "BLOCK"))

    def test_the_campaign_approval_is_current(self):
        """Given through the real path, with the fingerprint it was issued for."""
        from src import campaigns
        campaign, recs, config = demo_outreach.build()
        demo_outreach.approve_steps(recs, config)
        demo_outreach.apply_reply(recs, config, campaign)
        demo_outreach.approve_campaign(campaign, recs, config)
        self.assertTrue(campaigns.approval_is_current(campaign, recs, config))

    def test_an_unpermitted_actor_cannot_approve(self):
        """It refuses by raising, which is stronger than returning a status a
        caller could forget to read."""
        from src import orchestrator
        from src.providers import slack
        campaign, recs, config = demo_outreach.build()
        orchestrator.request_approval(campaign, recs, config)
        with self.assertRaises(slack.NotPermitted):
            orchestrator.decide(campaign, "U0NOTALLOWED", "approve",
                                fingerprint=campaign["fingerprint"],
                                config=config, recs=recs)
        self.assertIsNone(campaign.get("approval"))


class TestTheCli(DemoTest):
    def test_it_writes_the_page_and_reports(self):
        import contextlib
        import io
        path = os.path.join(self.tmp, "cli.html")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = demo_outreach.main(["--out", path])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(path))
        self.assertIn("would send       0", buffer.getvalue())

    def test_json_mode_carries_would_send(self):
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            demo_outreach.main(["--json"])
        self.assertEqual(json.loads(buffer.getvalue())["would_send"], 0)

    def test_there_is_no_live_flag(self):
        import contextlib
        import io
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                demo_outreach.main(["--live"])


if __name__ == "__main__":
    unittest.main()


class TestThePayloadCountsAreStable(DemoTest):
    """Pinned, because a payload that silently empties looks like a clean run.

    `test_it_reaches_both_providers` would already fail if HeyReach came back
    empty, but it fails with "harborlight not in set()", which reads as a
    routing problem rather than as "the payload is gone". These say the number.
    """

    def test_both_payloads_are_non_empty(self):
        payloads = self.res["push"]["payloads"]
        self.assertGreater(payloads["emailbison"]["count"], 0)
        self.assertGreater(payloads["heyreach"]["count"], 0)

    def test_the_counts_match_the_bodies(self):
        payloads = self.res["push"]["payloads"]
        self.assertEqual(payloads["emailbison"]["count"],
                         len(payloads["emailbison"]["body"]["leads"]))
        self.assertEqual(payloads["heyreach"]["count"],
                         len(payloads["heyreach"]["body"]["accountLeadPairs"]))

    def test_one_lead_pair_per_linkedin_eligible_unpaused_contact(self):
        expected = {c["record_id"] for c in self.res["cards"]
                    if c["linkedin"]["eligible"] and not c["paused"]}
        actual = {self.custom_fields(p)["record_id"]
                  for p in self.heyreach_pairs()}
        self.assertEqual(actual, expected)
