"""Provider modules, offline. BUILD-SPEC sections 5 and 9.

Every test here replays a hand written cassette. No test may reach a real API,
spend a credit, send a lead, or touch a campaign.
"""
import unittest

from src import providers
from src.providers import aiark, bison, contactout, heyreach, reoon
from tests.base import NoNetwork, ProviderTest


class TestTheHarnessItself(ProviderTest):
    def test_a_bypassed_transport_is_fatal(self):
        import urllib.request
        with self.assertRaises(NoNetwork):
            urllib.request.urlopen("https://api.contactout.com/v1/stats")

    def test_an_unmatched_call_is_fatal_rather_than_live(self):
        with self.assertRaises(NoNetwork):
            providers.request("GET", "https://api.example.com/unknown")

    def test_config_env_is_not_read_during_tests(self):
        self.assertFalse(providers.load_env())


class TestKeysAndRedaction(ProviderTest):
    def test_a_missing_key_raises_before_any_request(self):
        self.clear_keys()
        for fn in (contactout.check, aiark.check, bison.check, heyreach.check):
            self.assertFalse(fn()["ok"], fn)
        self.assertFalse(reoon.check()["ok"])
        self.assertEqual(self.cassette.calls, [])

    def test_missing_key_message_names_the_variable(self):
        self.clear_keys()
        with self.assertRaises(providers.MissingKey) as e:
            providers.key("CONTACTOUT_TOKEN")
        self.assertIn("CONTACTOUT_TOKEN", str(e.exception))

    def test_urls_and_headers_are_redacted(self):
        self.assertEqual(providers.redact("https://api.ai-ark.com/v1/mcp?token=abc123"),
                         "https://api.ai-ark.com/v1/mcp?token=***")
        self.assertEqual(
            providers.redact("https://emailverifier.reoon.com/api/v1/verify?email=a@b.c&key=SEKRIT&mode=power"),
            "https://emailverifier.reoon.com/api/v1/verify?email=a@b.c&key=***&mode=power")
        self.assertEqual(providers.redact({"token": "abc", "authorization": "basic"}),
                         {"token": "***", "authorization": "basic"})
        self.assertEqual(providers.redact({"X-API-KEY": "abc"}), {"X-API-KEY": "***"})

    def test_no_check_output_leaks_a_key(self):
        for r in (contactout.check(), aiark.check(), reoon.check(),
                  bison.check(), heyreach.check()):
            self.assertNotIn("test-key-not-real", str(r))


class TestContactOut(ProviderTest):
    def test_auth_headers(self):
        contactout.check()
        headers = self.cassette.calls[0]["headers"]
        self.assertEqual(headers["authorization"], "basic")
        self.assertEqual(headers["token"], "test-key-not-real")

    def test_decision_makers_is_trimmed_to_eight_fields(self):
        people = contactout.decision_makers("meridian.test")
        self.assertEqual(len(people), 2)
        self.assertEqual(set(people[0]), {"name", "title", "company", "linkedin",
                                          "email", "location", "seniority", "current"})
        self.assertEqual(people[0]["name"], "Ivana Saric")
        self.assertEqual(people[0]["email"], "ivana.saric@meridian.test")

    def test_the_noise_in_the_payload_never_escapes(self):
        blob = str(contactout.decision_makers("meridian.test"))
        for noise in ("experience", "skills", "profile_picture", "contact_info",
                      "i.saric@example.com", "+385"):
            self.assertNotIn(noise, blob, noise)

    def test_people_search_always_sends_output_fields(self):
        """Search is a POST, so the filters travel in the body, not the query."""
        contactout.people_search(domain="meridian.test", job_title="Account Manager")
        call = self.cassette.calls[-1]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/people/search"), call["url"])
        self.assertIn("output_fields", call["body"])
        self.assertEqual(call["body"]["current_company_only"], "true")

    def test_output_fields_are_values_contactout_accepts(self):
        """The live schema allows a fixed list. work_email and seniority are not on it."""
        allowed = {"li_vanity", "full_name", "title", "headline", "company",
                   "company.name", "company.website", "company.headquarter",
                   "company.domain", "company.size", "location", "industry",
                   "experience", "education", "skills", "profile_picture_url"}
        self.assertTrue(set(contactout.OUTPUT_FIELDS) <= allowed,
                        set(contactout.OUTPUT_FIELDS) - allowed)

    def test_the_data_envelope_is_unwrapped(self):
        """Live responses arrive as a status/data envelope."""
        self.assertEqual(contactout.unwrap({"status": 200, "data": {"a": 1}}), {"a": 1})
        self.assertEqual(contactout.unwrap({"a": 1}), {"a": 1})
        self.assertEqual(contactout.unwrap(None), {})

    def test_an_address_behind_contact_info_is_found(self):
        """With reveal_info the address arrives under contact_info, not at the top."""
        people = contactout.decision_makers("meridian.test", reveal_info=True)
        self.assertEqual(people[0]["email"], "ivana.saric@meridian.test")

    def test_reveal_info_is_off_unless_asked_for(self):
        contactout.decision_makers("meridian.test")
        self.assertIn("reveal_info=false", self.cassette.urls()[-1])

    def test_company_info_asks_with_the_domains_array(self):
        contactout.company_info("meridian.test")
        call = self.cassette.calls[-1]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/domain/enrich"), call["url"])
        self.assertEqual(call["body"]["domains"], ["meridian.test"])

    def test_people_count_is_free_and_trimmed(self):
        """Live-verified field names: total_results and estimated_phones."""
        got = contactout.people_count("Operations Manager", location="United Kingdom")
        self.assertEqual(got, {"query": "Operations Manager", "profiles": 230222,
                               "mobiles": 125588})
        self.assertEqual(providers.COST["people-count"], "free")
        self.assertIn("people-count", providers.FREE)

    def test_people_count_uses_location_not_current_work_location(self):
        contactout.people_count("Operations Manager", location="United Kingdom")
        call = self.cassette.calls[-1]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/people/count"), call["url"])
        self.assertEqual(call["body"]["location"], ["United Kingdom"])
        self.assertEqual(call["body"]["job_title"], ["Operations Manager"])
        self.assertNotIn("current_work_location", call["body"])

    def test_current_work_location_is_refused_outright(self):
        """Section 9, trap 7: it returned 86 where location returned 230,222."""
        for fn in (contactout.people_count, contactout.people_search):
            with self.assertRaises(ValueError) as e:
                fn(current_work_location="United Kingdom")
            self.assertIn("current_work_location", str(e.exception))
        self.assertEqual(self.cassette.calls, [])

    def test_email_verifier_returns_a_known_verdict_only(self):
        got = contactout.email_verifier("ivana.saric@meridian.test")
        self.assertEqual(got, {"email": "ivana.saric@meridian.test", "verdict": "accept_all"})
        self.assertIn(got["verdict"], contactout.VERDICTS)

    def test_company_info_surfaces_the_real_mail_domain(self):
        """Section 9, trap 3: the mail domain is not always the website domain."""
        got = contactout.company_info("meridian.test")
        self.assertEqual(got["domain"], "meridian.test")
        self.assertEqual(got["email_domain"], "meridian-mail.test")
        self.assertEqual(got["employees"], 26)
        self.assertEqual(set(got), {"name", "domain", "email_domain", "employees",
                                    "revenue", "founded", "industry", "offices",
                                    "specialties", "stack",
                                    # li_vanity, kept rather than trimmed: it
                                    # is the address every Blitz search is
                                    # keyed by, and without it a missing
                                    # company LinkedIn URL cannot be stated as
                                    # a ContactOut miss at all.
                                    "linkedin"})
        self.assertNotIn("description", str(got))


class TestAiArk(ProviderTest):
    def test_check_lists_tools_and_costs_nothing(self):
        r = aiark.check()
        self.assertTrue(r["ok"])
        self.assertIn("tools", r["note"])
        self.assertEqual(self.cassette.calls[0]["body"]["method"], "tools/list")

    def test_the_token_travels_in_the_query_string(self):
        aiark.check()
        self.assertIn("token=test-key-not-real", self.cassette.urls()[0])

    def test_strict_enums_must_come_from_the_lookup(self):
        with self.assertRaises(aiark.EnumNotLookedUp) as e:
            aiark.people_search(companyDomain="meridian.test", industry="Advertising Services")
        self.assertIn("industry_search", str(e.exception))
        self.assertEqual(self.cassette.calls, [])

    def test_after_the_lookup_the_same_value_is_accepted(self):
        values = aiark.industry_search("advertising")
        self.assertIn("Advertising Services", values)
        aiark.people_search(companyDomain="meridian.test", industry="Advertising Services")
        self.assertEqual(self.cassette.calls[-1]["body"]["params"]["name"], "people_search")

    def test_every_enum_field_is_guarded(self):
        """Five enum arguments in the live schema, not three."""
        self.assertEqual(set(aiark.ENUM_FIELDS),
                         {"industry", "location", "companyIndustry",
                          "companyLocation", "companyTechnology"})
        for field in aiark.ENUM_FIELDS:
            with self.assertRaises(aiark.EnumNotLookedUp):
                aiark.people_search(**{field: "invented value"})

    def test_a_comma_separated_enum_is_checked_token_by_token(self):
        aiark.industry_search("advertising")
        with self.assertRaises(aiark.EnumNotLookedUp):
            aiark.people_search(industry="Advertising Services,Invented Industry")

    def test_a_keyword_search_always_carries_keyword_sources(self):
        """Without it the API answers 400 sources is required."""
        aiark.people_search(companyDomain="meridian.test", keyword="agency")
        body = self.cassette.calls[-1]["body"]
        args = body["params"]["arguments"]
        self.assertEqual(args["keywordSources"], "HEADLINE,SUMMARY,ORGANIZATION")

    def test_no_keyword_means_no_keyword_sources(self):
        aiark.people_search(companyDomain="meridian.test")
        args = self.cassette.calls[-1]["body"]["params"]["arguments"]
        self.assertNotIn("keywordSources", args)

    def test_people_search_is_trimmed(self):
        people = aiark.people_search(companyDomain="meridian.test")
        self.assertEqual(set(people[0]), {"name", "title", "company", "linkedin",
                                          "email", "location"})
        self.assertNotIn("summary", str(people))

    def test_email_finder_polls_until_ready_and_is_trimmed(self):
        """Live contract: state PENDING then DONE, people under content[]."""
        got = aiark.find_email(companyDomain="meridian.test", fullName="Tomislav Barić",
                               interval=0, sleep=lambda s: None)
        self.assertEqual(got["state"], "done")
        self.assertEqual(got["people"][0]["email"], "tomislav.baric@meridian.test")
        self.assertEqual(set(got["people"][0]),
                         {"name", "title", "company", "linkedin", "email", "location"})
        self.assertNotIn("raw_smtp", str(got))

    def test_polling_is_bounded_and_gives_up(self):
        calls = []
        original = aiark.email_finder_results
        aiark.email_finder_results = lambda t: calls.append(t) or {
            "track_id": t, "state": "pending", "people": []}
        try:
            got = aiark.find_email(companyDomain="meridian.test", attempts=3,
                                   interval=0, sleep=lambda s: None)
        finally:
            aiark.email_finder_results = original
        self.assertEqual(got["state"], "timeout")
        self.assertEqual(len(calls), 3)

    def test_an_rpc_error_is_raised_not_returned(self):
        with self.assertRaises(providers.ProviderError) as e:
            aiark.call_tool("__no_sources__", {})
        self.assertIn("sources is required", str(e.exception))


class TestReoon(ProviderTest):
    def test_default_check_spends_nothing_and_makes_no_call(self):
        r = reoon.check()
        self.assertTrue(r["skipped"])
        self.assertIsNone(r["ok"])
        self.assertEqual(self.cassette.calls, [])
        self.assertIn("no call made", r["note"])

    def test_live_check_is_opt_in_only(self):
        r = reoon.check(live=True)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.cassette.calls), 1)
        self.assertIn("mode=quick", self.cassette.urls()[0])

    def test_verify_is_power_mode_and_trimmed_to_six_fields(self):
        got = reoon.verify("ivana.saric@meridian.test")
        self.assertIn("mode=power", self.cassette.urls()[0])
        self.assertEqual(set(got), set(reoon.FIELDS))
        self.assertNotIn("debug_log", str(got))

    def test_only_is_safe_to_send_clears_an_address(self):
        self.assertTrue(reoon.is_clear({"is_safe_to_send": True}))
        for reoon_block in ({"is_safe_to_send": False},
                            {"is_deliverable": True, "overall_score": 99},
                            {}, None):
            self.assertFalse(reoon.is_clear(reoon_block), reoon_block)


class TestBison(ProviderTest):
    def test_check_is_a_read_only_campaign_list(self):
        r = bison.check()
        self.assertTrue(r["ok"])
        self.assertEqual(self.cassette.calls[0]["method"], "GET")
        self.assertIn("/campaigns", self.cassette.urls()[0])
        self.assertEqual(self.cassette.calls[0]["headers"]["Authorization"],
                         "Bearer test-key-not-real")

    def test_the_builder_puts_the_draft_in_custom_variables(self):
        payload = bison.build_leads([{
            "email": "ivana.saric@meridian.test", "first_name": "Ivana",
            "last_name": "Saric", "company": "Meridian", "title": "Head of Finance",
            "subject": "five offices, one finance function", "body": "the draft",
            "record_id": "meridian"}])
        lead = payload["leads"][0]
        self.assertEqual(lead["email"], "ivana.saric@meridian.test")
        variables = bison.variables_of(lead)
        self.assertEqual(variables["subject"],
                         "five offices, one finance function")
        self.assertEqual(variables["body"], "the draft")
        self.assertEqual(variables["record_id"], "meridian")

    def test_the_builder_sends_nothing(self):
        bison.build_leads([{"email": "a@b.c"}])
        self.assertEqual(self.cassette.calls, [])

    def test_base_url_is_overridable(self):
        import os
        os.environ["BISON_BASE"] = "https://staging.example.com/api/"
        self.assertEqual(bison.leads_endpoint(42),
                         "https://staging.example.com/api/campaigns/42/leads")


class TestHeyReach(ProviderTest):
    def test_check_is_the_documented_endpoint(self):
        r = heyreach.check()
        self.assertTrue(r["ok"])
        self.assertIn("/auth/CheckApiKey", self.cassette.urls()[0])
        self.assertEqual(self.cassette.calls[0]["headers"]["X-API-KEY"], "test-key-not-real")

    def test_the_builder_produces_account_lead_pairs(self):
        pairs = heyreach.build_lead_pairs([{
            "linkedin_url": "https://www.linkedin.com/in/ivana-saric",
            "first_name": "Ivana", "last_name": "Saric", "company": "Meridian",
            "title": "Head of Finance", "note": "five offices, one finance function"}], 3)
        self.assertEqual(pairs[0]["linkedInAccountId"], 3)
        self.assertEqual(pairs[0]["lead"]["profileUrl"],
                         "https://www.linkedin.com/in/ivana-saric")
        self.assertEqual(pairs[0]["lead"]["customUserFields"],
                         [{"name": "note", "value": "five offices, one finance function"}])

    def test_the_builder_sends_nothing(self):
        heyreach.build_lead_pairs([{"linkedin_url": "x"}], 1)
        self.assertEqual(self.cassette.calls, [])


class TestNoSendPathExists(unittest.TestCase):
    """Neither sender can START anything, which is what a send needs.

    This used to say "neither may issue a POST at all", and that was the right
    guarantee while EmailBison had no proven write verbs. It has them now -
    campaign creation, sequences, limits, membership, and the per-lead stop -
    so a blanket ban on POST would have to be either deleted or worked around,
    and both are worse than moving the guarantee to where it actually lives.

    The verb was never the safety property. The ROUTE is. A send on EmailBison
    is started by `/campaigns/{id}/resume` and on HeyReach by
    `/campaign/AddLeadsToCampaignV2`, and neither appears in the allowlist its
    module is permitted to reach.
    """

    def test_neither_sender_exposes_a_verb_that_starts_anything(self):
        for module in (bison, heyreach):
            names = [n for n in dir(module) if not n.startswith("_")]
            for banned in ("send", "push", "add_leads", "start", "resume",
                           "activate", "launch"):
                self.assertNotIn(banned, names, f"{module.__name__}.{banned}")

    def test_exactly_one_bison_write_route_can_start_a_send(self):
        """The resume route exists now. Everything else still stages or stops.

        It was added on 2026-09-13 under explicit operator authorisation for a
        bounded canary, and the honest guarantee changed shape with it: not
        "no route can send" - which would now be false - but that exactly ONE
        can, that it is named, and that nothing gated can reach it.

        Counted rather than merely checked for absence, so a second starting
        route arriving quietly fails here.
        """
        starting = [r for r in bison.WRITE_ROUTES
                    if any(verb in r for verb in
                           ("resume", "start", "launch", "activate",
                            "send-test"))]
        self.assertEqual(starting, ["/campaigns/{campaign_id}/resume"],
                         f"unexpected starting route(s): {starting}")

    def test_nothing_gated_can_drive_the_send_route(self):
        """The route is reachable by hand. It is not reachable by the system.

        `providerwrites` is the door every automated write goes through, and
        the operation that would start a campaign is not in its supported set
        - so no cadence, no runner and no orchestrator can resume anything.
        Exercising it takes somebody writing the call deliberately.
        """
        from src import providerwrites
        self.assertFalse(
            providerwrites.is_supported(providerwrites.EMAIL_ACTIVATE))
        self.assertNotIn("/campaign/AddLeadsToCampaignV2", heyreach.READ_ROUTES)

    def test_the_send_route_refuses_a_reach_it_was_not_told_to_expect(self):
        """A resumed campaign sends to everybody it holds.

        `expect_leads` is the containment: the caller states how many people
        it believes are in the campaign, and a disagreement stops the send
        rather than being discovered afterwards. There is no recalling the
        difference.
        """
        import inspect
        self.assertIn("expect_leads",
                      inspect.signature(bison.resume_campaign).parameters)

    def test_no_prospect_facing_operation_is_supported_on_either(self):
        """The end of the chain: even a route that existed could not be used."""
        from src import providerwrites
        for operation, (_channel, facing, _why) in                 providerwrites.OPERATIONS.items():
            if facing:
                self.assertFalse(providerwrites.is_supported(operation),
                                 operation)

    def test_reoon_still_never_posts(self):
        """Verification is a read. Nothing about that changed."""
        import inspect
        self.assertNotIn('"POST"', inspect.getsource(reoon))

    def test_every_contactout_post_goes_to_a_read_only_route(self):
        read_only = {"/people/count", "/people/search", "/domain/enrich"}
        posted = {path for method, path in contactout.ROUTES.values()
                  if method == "POST"}
        self.assertTrue(posted <= read_only, f"unexpected POST route: {posted - read_only}")

    def test_no_contactout_route_is_a_mutation(self):
        for name, (method, path) in contactout.ROUTES.items():
            for mutating in ("send", "message", "campaign", "lead", "sequence",
                             "invite", "connect"):
                self.assertNotIn(mutating, path.lower(), f"{name} -> {path}")


if __name__ == "__main__":
    unittest.main()
