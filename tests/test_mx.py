"""The MX gate: which gateway, whose domain, and what it may stop.

No test here touches DNS. Every resolver is a function returning a fixed list,
because a suite that depends on a resolver is a suite that fails on a train.

The two properties worth stating up front: a blocked gateway stops the EMAIL
channel and nothing else, and the push builder re-derives the decision itself
so that tampering with stored state upstream changes nothing.
"""
import json
import os
import unittest

from src import cadence, clients, events, mx, push, store
from tests.campaignbase import CampaignTest, contact

PROOFPOINT = ["mx1.pphosted.com", "mx2.pphosted.com"]
MIMECAST = ["eu-smtp-inbound-1.mimecast.com"]
BARRACUDA = ["mx01.ess.barracudanetworks.com"]
GOOGLE = ["aspmx.l.google.com", "alt1.aspmx.l.google.com"]
MICROSOFT = ["acme-test.mail.protection.outlook.com"]
UNKNOWN_MX = ["mail.someinternalthing.example"]


def resolver_for(mapping, calls=None):
    """A fake resolver. Records what it was asked, so caching can be proved."""
    def resolve(domain, *args, **kwargs):
        if calls is not None:
            calls.append(domain)
        if domain not in mapping:
            raise mx.MXError(f"no fixture for {domain}")
        value = mapping[domain]
        if isinstance(value, Exception):
            raise value
        return list(value)
    return resolve


class TestTheBlockedGateways(unittest.TestCase):
    def policy(self, **over):
        return mx.settings({"email_security": {"mx_filter": {**over}}})

    def decide(self, hosts, **over):
        return mx.decide(hosts, self.policy(**over), domain="acme.test")

    def test_barracuda_blocks_email(self):
        d = self.decide(BARRACUDA)
        self.assertEqual(d["status"], mx.KNOWN_BLOCKED)
        self.assertFalse(d["email_cadence_allowed"])
        self.assertEqual(d["security_provider"], "barracuda")

    def test_proofpoint_blocks_email(self):
        d = self.decide(PROOFPOINT)
        self.assertEqual(d["status"], mx.KNOWN_BLOCKED)
        self.assertFalse(d["email_cadence_allowed"])

    def test_mimecast_blocks_email(self):
        d = self.decide(MIMECAST)
        self.assertEqual(d["status"], mx.KNOWN_BLOCKED)
        self.assertFalse(d["email_cadence_allowed"])

    def test_google_workspace_is_allowed_by_default(self):
        d = self.decide(GOOGLE)
        self.assertEqual(d["status"], mx.KNOWN_ALLOWED)
        self.assertTrue(d["email_cadence_allowed"])
        self.assertEqual(d["security_provider"], "google")

    def test_microsoft_365_is_allowed_by_default(self):
        d = self.decide(MICROSOFT)
        self.assertEqual(d["status"], mx.KNOWN_ALLOWED)
        self.assertTrue(d["email_cadence_allowed"])

    def test_neither_mailbox_host_can_be_blocked_by_naming_it(self):
        """They are recognised, but they are not gateways: naming one in
        blocked_providers is dropped rather than honoured."""
        policy = self.policy(blocked_providers=["google", "microsoft"])
        self.assertEqual(policy["blocked_providers"], ())
        self.assertTrue(mx.decide(GOOGLE, policy)["email_cadence_allowed"])

    def test_an_unknown_gateway_follows_the_policy(self):
        allowed = mx.decide(UNKNOWN_MX, self.policy(unknown_provider_policy="allow"))
        blocked = mx.decide(UNKNOWN_MX, self.policy(unknown_provider_policy="block"))
        self.assertTrue(allowed["email_cadence_allowed"])
        self.assertFalse(blocked["email_cadence_allowed"])
        self.assertEqual(allowed["status"], mx.UNKNOWN_PROVIDER)

    def test_one_blocked_record_among_several_blocks(self):
        d = self.decide(["mail.acme.test", "backup.acme.test"] + PROOFPOINT)
        self.assertEqual(d["security_provider"], "proofpoint")
        self.assertFalse(d["email_cadence_allowed"])

    def test_hostnames_are_case_insensitive(self):
        self.assertEqual(self.decide(["MX1.PPHOSTED.COM"])["security_provider"],
                         "proofpoint")

    def test_a_trailing_dot_is_normalised(self):
        self.assertEqual(self.decide(["mx1.pphosted.com."])["security_provider"],
                         "proofpoint")

    def test_matching_is_on_label_boundaries_never_substrings(self):
        for lookalike in ("notpphosted.com", "pphosted.com.evil.test",
                          "mimecast.com.attacker.test", "mymimecast.net"):
            d = self.decide([lookalike])
            self.assertIsNone(d["security_provider"], lookalike)

    def test_every_other_supported_gateway_is_recognised(self):
        for hosts, key in ((["a.iphmx.com"], "cisco"),
                           (["x.mailcontrol.com"], "forcepoint"),
                           (["a.hes.trendmicro.com"], "trendmicro"),
                           (["mx.spamtitan.com"], "spamtitan"),
                           (["a.antispameurope.com"], "hornetsecurity"),
                           (["cluster.messagelabs.com"], "symantec"),
                           (["mx.sophos.com"], "sophos")):
            self.assertEqual(mx.classify(hosts)[0], key, hosts)

    def test_a_gateway_beats_the_mailbox_behind_it(self):
        """A Mimecast-fronted Microsoft tenant is a Mimecast domain here."""
        d = self.decide(MIMECAST + MICROSOFT)
        self.assertEqual(d["security_provider"], "mimecast")


class TestTheEmailDomainIsTheOneUsed(unittest.TestCase):
    def test_the_address_domain_is_extracted_not_the_company(self):
        self.assertEqual(mx.email_domain("john@mail-acme-group.test"),
                         "mail-acme-group.test")

    def test_case_and_trailing_dots_are_normalised(self):
        self.assertEqual(mx.email_domain("John@Mail-Acme-Group.TEST."),
                         "mail-acme-group.test")

    def test_junk_yields_nothing_rather_than_a_guess(self):
        for junk in ("", None, "not-an-address", "@", 42):
            self.assertIsNone(mx.email_domain(junk), repr(junk))

    def test_the_company_domain_is_never_substituted(self):
        """The whole rule in one test: a contact at company.test whose address
        is elsewhere is judged by elsewhere."""
        calls = []
        resolve = resolver_for({"mail-acme-group.test": PROOFPOINT}, calls)
        decision = mx.for_domain(mx.email_domain("john@mail-acme-group.test"),
                                 {}, cache={}, resolver=resolve, save=False)
        self.assertEqual(calls, ["mail-acme-group.test"])
        self.assertFalse(decision["email_cadence_allowed"])


class TestFailureStates(unittest.TestCase):
    def test_a_dns_failure_holds_the_channel_rather_than_allowing_it(self):
        resolve = resolver_for({"acme.test": mx.MXError("timeout")})
        d = mx.for_domain("acme.test", {}, cache={}, resolver=resolve, save=False)
        self.assertEqual(d["status"], mx.DNS_FAILURE)
        self.assertFalse(d["email_cadence_allowed"])
        self.assertIn("held", d["reason"])

    def test_a_dns_failure_is_never_cached(self):
        cache = {}
        resolve = resolver_for({"acme.test": mx.MXError("timeout")})
        mx.for_domain("acme.test", {}, cache=cache, resolver=resolve, save=False)
        self.assertNotIn("acme.test", cache)

    def test_no_mx_means_the_domain_takes_no_mail(self):
        resolve = resolver_for({"acme.test": []})
        d = mx.for_domain("acme.test", {}, cache={}, resolver=resolve, save=False)
        self.assertEqual(d["status"], mx.NO_MX)
        self.assertFalse(d["email_cadence_allowed"])

    def test_a_failure_never_becomes_a_provider_guess(self):
        resolve = resolver_for({"acme.test": mx.MXError("servfail")})
        d = mx.for_domain("acme.test", {}, cache={}, resolver=resolve, save=False)
        self.assertIsNone(d["security_provider"])
        self.assertFalse(d["security_detected"])

    def test_the_five_states_are_distinct(self):
        self.assertEqual(len(set(mx.STATUSES)), len(mx.STATUSES))


class TestTheCache(CampaignTest):
    def setUp(self):
        super().setUp()
        os.environ["MX_CACHE"] = os.path.join(self.tmp, "work", "mx-cache.json")

    def test_fifty_contacts_at_one_domain_resolve_once(self):
        calls = []
        resolve = resolver_for({"acme.test": PROOFPOINT}, calls)
        cache = {}
        for _ in range(50):
            mx.for_domain("acme.test", {}, cache=cache, resolver=resolve,
                          save=False)
        self.assertEqual(len(calls), 1)

    def test_a_second_run_reuses_a_fresh_result(self):
        calls = []
        resolve = resolver_for({"acme.test": PROOFPOINT}, calls)
        cache = {}
        mx.for_domain("acme.test", {}, cache=cache, resolver=resolve, save=False)
        again = mx.for_domain("acme.test", {}, cache=cache, resolver=resolve,
                              save=False)
        self.assertEqual(len(calls), 1)
        self.assertTrue(again["cached"])
        self.assertFalse(again["email_cadence_allowed"])

    def test_a_stale_entry_is_looked_up_again(self):
        calls = []
        resolve = resolver_for({"acme.test": PROOFPOINT}, calls)
        cache = {"acme.test": {"mx_records": GOOGLE, "status": mx.KNOWN_ALLOWED,
                               "checked_at": "2020-01-01T00:00:00+00:00"}}
        mx.for_domain("acme.test", {}, cache=cache, resolver=resolve, save=False)
        self.assertEqual(calls, ["acme.test"])

    def test_the_cache_survives_a_write_and_read(self):
        mx.save_cache({"acme.test": {"mx_records": GOOGLE,
                                     "status": mx.KNOWN_ALLOWED,
                                     "checked_at": store.now()}})
        self.assertIn("acme.test", mx.load_cache())

    def test_a_corrupt_cache_does_not_stop_the_world(self):
        path = mx.cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(mx.load_cache(), {})

    def test_no_raw_dns_payload_is_stored(self):
        cache = {}
        resolve = resolver_for({"acme.test": PROOFPOINT})
        mx.for_domain("acme.test", {}, cache=cache, resolver=resolve, save=False)
        entry = cache["acme.test"]
        self.assertEqual(sorted(entry), ["checked_at", "mx_records", "status"])


class TestChannelSuppressionNotADrop(CampaignTest):
    def record(self, hosts=PROOFPOINT, sendable=True):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test",
                                   sendable=sendable)]
        rec["contacts"][0]["mx"] = mx.decide(hosts, mx.settings(self.config),
                                             domain="acme.test")
        self.draft_everything(recs)
        return rec, recs

    def timeline(self, rec, recs):
        return cadence.build(rec, self.config, recs=recs)

    def test_email_steps_are_skipped_with_the_provider_named(self):
        rec, recs = self.record()
        steps = self.timeline(rec, recs)["contacts"]["acme-champ"]
        email = [s for s in steps.values() if s["channel"] == "email"]
        self.assertTrue(email)
        for step in email:
            self.assertEqual(step["status"], "skipped")
            self.assertIn("mx_security_provider_blocked:proofpoint",
                          step["blocked_by"])

    def test_linkedin_steps_are_untouched(self):
        rec, recs = self.record()
        steps = self.timeline(rec, recs)["contacts"]["acme-champ"]
        linkedin = [s for s in steps.values() if s["channel"] == "linkedin"]
        self.assertTrue(linkedin)
        for step in linkedin:
            self.assertNotEqual(step["status"], "skipped")

    def test_the_contact_is_not_dropped_and_the_steps_are_not_deleted(self):
        rec, recs = self.record()
        self.assertEqual(len(rec["contacts"]), 1)
        steps = self.timeline(rec, recs)["contacts"]["acme-champ"]
        self.assertGreaterEqual(len(steps), 5)

    def test_a_clean_domain_is_unaffected(self):
        rec, recs = self.record(GOOGLE)
        steps = self.timeline(rec, recs)["contacts"]["acme-champ"]
        email = [s for s in steps.values() if s["channel"] == "email"]
        for step in email:
            self.assertNotEqual(step["status"], "skipped")

    def test_a_verified_address_behind_a_blocked_gateway_is_still_blocked(self):
        """sendable=true is not permission when MX says no."""
        rec, recs = self.record(PROOFPOINT, sendable=True)
        from src import lint
        self.assertTrue(lint.sendable(rec["contacts"][0]))
        steps = self.timeline(rec, recs)["contacts"]["acme-champ"]
        email = [s for s in steps.values() if s["channel"] == "email"]
        self.assertTrue(all(s["status"] == "skipped" for s in email))

    def test_a_dns_failure_also_stops_email_but_keeps_linkedin(self):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        rec["contacts"][0]["mx"] = mx.decide([], mx.settings(self.config),
                                             status=mx.DNS_FAILURE,
                                             domain="acme.test")
        self.draft_everything(recs)
        steps = self.timeline(rec, recs)["contacts"]["acme-champ"]
        email = [s for s in steps.values() if s["channel"] == "email"]
        linkedin = [s for s in steps.values() if s["channel"] == "linkedin"]
        self.assertTrue(all(s["status"] == "skipped" for s in email))
        self.assertTrue(all(s["status"] != "skipped" for s in linkedin))

    def test_a_contact_never_checked_is_not_blocked_by_default(self):
        recs = self.seed_records()
        self.draft_everything(recs)
        steps = self.timeline(recs[0], recs)["contacts"]["acme-champ"]
        email = [s for s in steps.values() if s["channel"] == "email"]
        self.assertTrue(all(s["status"] != "skipped" for s in email))


class TestThePushInvariant(CampaignTest):
    """No EmailBison payload may contain an MX-blocked contact, even if the
    stored state has been altered."""

    def item(self, hosts=PROOFPOINT, tamper=False):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        decision = mx.decide(hosts, mx.settings(self.config), domain="acme.test")
        if tamper:
            decision["email_cadence_allowed"] = True
            decision["status"] = mx.KNOWN_ALLOWED
            decision["security_provider"] = None
        rec["contacts"][0]["mx"] = decision
        self.draft_everything(recs)
        self.approve_drafts(recs)
        step = rec["cadence"]["acme-champ"]["day1"]
        step["channel"] = "email"
        return {"record": rec, "contact": rec["contacts"][0],
                "contact_key": "acme-champ", "step_key": "day1", "step": step,
                "channel": "email", "push_id": "acme:acme-champ:day1:email"}

    def test_the_payload_builder_refuses_a_blocked_contact(self):
        from src import eligibility
        with self.assertRaises(AssertionError) as e:
            push.verify_before_payload(self.item())
        self.assertIn(eligibility.BLOCKED_MX, str(e.exception))

    def test_tampering_with_the_stored_verdict_does_not_help(self):
        """The classification is re-derived from the MX hostnames, so setting
        email_cadence_allowed by hand changes nothing."""
        from src import eligibility
        with self.assertRaises(AssertionError) as e:
            push.verify_before_payload(self.item(tamper=True))
        self.assertIn(eligibility.BLOCKED_MX, str(e.exception))

    def test_a_clean_contact_still_passes(self):
        push.verify_before_payload(self.item(GOOGLE))

    def test_no_blocked_row_reaches_the_emailbison_rows(self):
        item = self.item()
        with self.assertRaises(AssertionError):
            push.emailbison_rows([item])

    def test_the_check_happens_before_sendability(self):
        """MX is free and final, so it is asked before the verification state
        is consulted. Both now live in the central gate."""
        import inspect
        from src import eligibility
        source = inspect.getsource(eligibility._email_checks)
        self.assertLess(source.index("mx.allows_email"),
                        source.index("lint.sendable"))


class TestEventsAndSummary(CampaignTest):
    def prepared(self, hosts=PROOFPOINT):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        resolve = resolver_for({"acme.test": hosts})
        mx.apply_to_record(rec, self.config, cache={}, resolver=resolve)
        return rec

    def test_every_event_name_is_registered(self):
        for name in events.MX_EVENTS:
            self.assertIn(name, events.KNOWN, name)

    def test_a_blocked_contact_records_the_whole_story(self):
        rec = self.prepared()
        kinds = [e["type"] for e in rec["events"]]
        for expected in (events.MX_LOOKUP_STARTED, events.MX_LOOKUP_COMPLETED,
                         events.MX_SECURITY_PROVIDER_DETECTED,
                         events.EMAIL_CHANNEL_BLOCKED_MX):
            self.assertIn(expected, kinds, expected)

    def test_a_clean_contact_records_no_block(self):
        rec = self.prepared(GOOGLE)
        kinds = [e["type"] for e in rec["events"]]
        self.assertNotIn(events.EMAIL_CHANNEL_BLOCKED_MX, kinds)

    def test_a_failure_records_a_failure(self):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        resolve = resolver_for({"acme.test": mx.MXError("timeout")})
        mx.apply_to_record(rec, self.config, cache={}, resolver=resolve)
        self.assertIn(events.MX_LOOKUP_FAILED,
                      [e["type"] for e in rec["events"]])

    def test_no_dns_payload_reaches_the_record(self):
        rec = self.prepared()
        blob = json.dumps(rec)
        self.assertNotIn("rcode", blob)
        self.assertNotIn("\\x00", blob)

    def test_the_summary_counts_blocked_and_linkedin_only(self):
        rec = self.prepared()
        counts = mx.summarise([rec], self.config)
        self.assertEqual(counts["blocked"], 1)
        self.assertEqual(counts["linkedin_only"], 1)
        self.assertEqual(counts["by_provider"], {"proofpoint": 1})


class TestPolicyIsConfigurable(unittest.TestCase):
    def test_disabling_it_allows_everything(self):
        config = {"email_security": {"mx_filter": {"enabled": False}}}
        decision = mx.for_domain("acme.test", config, cache={},
                                 resolver=resolver_for({}), save=False)
        self.assertTrue(decision["email_cadence_allowed"])
        self.assertEqual(decision["status"], mx.NOT_CHECKED)

    def test_an_unrecognised_provider_name_is_dropped_not_honoured(self):
        policy = mx.settings({"email_security": {"mx_filter": {
            "blocked_providers": ["proofpoint", "not-a-real-gateway"]}}})
        self.assertEqual(policy["blocked_providers"], ("proofpoint",))
        self.assertEqual(policy["unknown"], ["not-a-real-gateway"])

    def test_a_client_can_block_more_than_the_default_three(self):
        policy = mx.settings({"email_security": {"mx_filter": {
            "blocked_providers": ["proofpoint", "cisco", "symantec"]}}})
        self.assertIn("cisco", policy["blocked_providers"])
        self.assertFalse(mx.decide(["a.iphmx.com"],
                                   policy)["email_cadence_allowed"])

    def test_a_nonsense_cache_setting_falls_back(self):
        policy = mx.settings({"email_security": {"mx_filter": {
            "cache_days": "forever"}}})
        self.assertEqual(policy["cache_days"], mx.DEFAULTS["cache_days"])


class TestNoLiveDns(CampaignTest):
    def test_the_suite_never_resolves_anything(self):
        """Every test here injects a resolver. This asserts the real one is
        not reachable by accident: the socket tripwire would fire."""
        with self.assertRaises(Exception):
            mx.resolve("example.test", timeout=0.01, servers=("203.0.113.1",))


if __name__ == "__main__":
    unittest.main()
