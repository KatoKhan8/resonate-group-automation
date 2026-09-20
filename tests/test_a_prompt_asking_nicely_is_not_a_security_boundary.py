"""An audit agent paused a live campaign by importing src and calling through.

2026-09-20T12:44:45Z. A throwaway probe passed a bare dict to
`orchestrator.pause`; `campaigns.get()` returned None, the staging-repeat
guard did not fire, `providerwrites.perform` called the transport, `key()`
read `config/.env`, and a real `PATCH /api/campaigns/487/pause` reached
send.resonategroup.co. Ten approved openers stopped being scheduled to send.

Nothing was misconfigured. No rule was broken. **There was no rule.**
`store.refuse_production_write` protects STATE and nothing protected the WIRE,
so the only barrier between an ad-hoc script and a live client campaign was a
sentence in a prompt asking it not to.

These tests pin the guard and, as importantly, its SHAPE:

  - it sits in the REAL transport, so the thousands of tests that swap a
    cassette in are untouched - a guard that forces a blanket opt-in across
    the suite is a guard somebody switches off
  - it refuses BEFORE the socket, so a refusal proves nothing was sent
  - reads are never refused
  - the opt-in is an ACT at an entry point, not an inheritance a library can
    grant itself - `providerwrites.perform` is how Buggie got there
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import providers  # noqa: E402


class ProviderWriteGuardTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._env = {k: os.environ.get(k)
                     for k in (providers.WRITES_ENV, "PROVIDER_WRITE_REFUSALS")}
        self.addCleanup(self._restore)
        os.environ.pop(providers.WRITES_ENV, None)
        os.environ["PROVIDER_WRITE_REFUSALS"] = os.path.join(
            self.tmp, "refusals.jsonl")
        # Any scope a failing test left behind must not leak into this one.
        del providers._write_scopes[:]
        self.addCleanup(lambda: providers._write_scopes.clear())
        self.opened = []
        self._urlopen = providers.urllib.request.urlopen
        providers.urllib.request.urlopen = self._booby_trap
        self.addCleanup(setattr, providers.urllib.request, "urlopen",
                        self._urlopen)

    def _restore(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _booby_trap(self, *a, **k):
        """Proves whether the socket was reached. A refusal that happened
        AFTER the request left is not a refusal."""
        self.opened.append(a[0].get_method() if a else "?")
        raise AssertionError("the wire was reached")

    def wire(self, method, url="https://send.resonategroup.co/api/campaigns/487/pause"):
        return providers._urllib_transport(method, url, {}, None, 5)

    def assertReachedWire(self):
        """`_urllib_transport` wraps everything below it in
        `HttpTransportError`, so the booby trap comes back wearing that. The
        sentinel text is what distinguishes "the socket was reached" from any
        other transport failure."""
        return self.assertRaisesRegex(providers.HttpTransportError,
                                      "the wire was reached")

    # ------------------------------------------------------- the refusal

    def test_a_mutation_with_no_authorization_is_refused(self):
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH")

    def test_the_refusal_lands_before_the_socket(self):
        """The whole safety claim. A refusal after the request left the
        machine would be a log line, not a guard."""
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("POST")
        self.assertEqual([], self.opened)

    def test_every_mutating_method_is_refused(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "patch", "delete"):
            with self.subTest(method=method):
                with self.assertRaises(providers.ProviderWriteRefused):
                    self.wire(method)
        self.assertEqual([], self.opened)

    def test_the_refusal_names_the_campaign_it_would_have_changed(self):
        with self.assertRaises(providers.ProviderWriteRefused) as caught:
            self.wire("PATCH")
        message = str(caught.exception)
        self.assertIn("487", message)
        self.assertIn("NOTHING WAS SENT", message)
        self.assertIn(providers.WRITES_ENV, message)

    # ---------------------------------------------------------- the reads

    def test_a_read_is_never_refused(self):
        """Every diagnostic in this repository is a reader, and a reader
        cannot change a prospect's state."""
        for method in ("GET", "HEAD", "OPTIONS"):
            with self.subTest(method=method):
                with self.assertReachedWire():
                    self.wire(method)
        self.assertEqual(3, len(self.opened))

    # -------------------------------------------------------- the opt-in

    def test_an_explicit_scope_permits_the_write(self):
        with providers.allow_writes("resume 487 per OPERATOR-AUTH 2026-09-20"):
            with self.assertReachedWire():
                self.wire("PATCH")
        self.assertEqual(1, len(self.opened))

    def test_the_scope_closes_behind_it(self):
        with providers.allow_writes("one write"):
            pass
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH")

    def test_a_scope_closes_even_when_the_block_raises(self):
        with self.assertRaises(ValueError):
            with providers.allow_writes("one write"):
                raise ValueError("boom")
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH")

    def test_nesting_does_not_let_the_inner_block_close_the_outer_one(self):
        with providers.allow_writes("outer"):
            with providers.allow_writes("inner"):
                pass
            allowed, why = providers.writes_allowed()
            self.assertTrue(allowed)
            self.assertIn("outer", why)

    def test_an_authorization_must_carry_a_reason(self):
        """"Who authorised this write and for what" is the question an
        incident asks first, and the 487 pause could not answer it."""
        for bad in ("", "   ", None):
            with self.subTest(reason=bad):
                with self.assertRaises(ValueError):
                    providers.allow_writes(bad)

    def test_the_process_wide_env_opt_in_works(self):
        os.environ[providers.WRITES_ENV] = "1"
        with self.assertReachedWire():
            self.wire("PATCH")

    def test_any_value_but_1_is_not_an_opt_in(self):
        """`RESONATE_PROVIDER_WRITES=false` must not read as permission."""
        for value in ("0", "false", "no", "", "true", "yes"):
            os.environ[providers.WRITES_ENV] = value
            with self.subTest(value=value):
                if value == "1":
                    continue
                with self.assertRaises(providers.ProviderWriteRefused):
                    self.wire("PATCH")

    # --------------------------------------------------------- the scope

    def test_only_the_two_providers_that_reach_a_prospect_are_guarded(self):
        """THE SCOPING THAT MAKES THE GUARD USABLE.

        The first version refused every non-GET on the wire and would have
        taken out the entire system: glm and xai POST a model completion,
        contactout/aiark/blitz/apify POST a PAID READ, slack POSTs a notice.
        None of them can change what a prospect experiences. A guard that
        breaks everything is a guard somebody deletes.
        """
        import src.providers.bison            # noqa: F401  - registers
        import src.providers.heyreach         # noqa: F401  - registers
        self.assertTrue(providers.is_prospect_facing(
            "https://send.resonategroup.co/api/campaigns/487/pause"))
        self.assertTrue(providers.is_prospect_facing(
            "https://api.heyreach.io/api/public/campaign/StartCampaign"))
        for url in ("https://api.x.ai/v1/responses",
                    "https://api.contactout.com/v1/people/search",
                    "https://api.ai-ark.com/v1/mcp",
                    "https://api.blitz-api.ai/x",
                    "https://api.apify.com/v2/acts/x/runs",
                    "https://slack.com/api/chat.postMessage"):
            with self.subTest(url=url):
                self.assertFalse(providers.is_prospect_facing(url))

    def test_a_model_completion_post_is_not_refused(self):
        """The adversarial reviewer and the research model both POST. If this
        fails, the AI workforce is down and the guard did it."""
        with self.assertReachedWire():
            self.wire("POST", "https://api.x.ai/v1/responses")

    def test_a_paid_enrichment_post_is_not_refused(self):
        with self.assertReachedWire():
            self.wire("POST", "https://api.contactout.com/v1/people/search")

    def test_the_two_guarded_modules_are_exactly_the_two_with_WRITE_ROUTES(self):
        """The guarded set is not a hand-maintained list that can drift: it
        is the modules that declare prospect-facing write routes, and this
        asserts the two definitions still agree."""
        import src.providers.bison as bison_mod
        import src.providers.heyreach as heyreach_mod
        self.assertTrue(hasattr(bison_mod, "WRITE_ROUTES"))
        self.assertTrue(hasattr(heyreach_mod, "WRITE_ROUTES"))
        self.assertEqual({"send.resonategroup.co", "api.heyreach.io"},
                         set(providers._prospect_facing_hosts))

    def test_an_unregistered_host_is_not_guarded_and_that_is_deliberate(self):
        """Recorded rather than left implicit: the guard is a allow-list of
        DANGEROUS hosts, not a deny-list of safe ones. A new prospect-facing
        provider must call `guard_prospect_facing` at import, and this test
        is where somebody adding one will be reminded."""
        with self.assertReachedWire():
            self.wire("PATCH", "https://some-new-provider.test/campaigns/1")

    # ------------------------------------------- GLM's evasions, confirmed

    def test_a_trailing_dot_fqdn_does_not_evade_the_guard(self):
        """FOUND BY GLM'S ADVERSARIAL REVIEW, hours after the guard landed,
        and REPRODUCED before it was accepted.

        `send.resonategroup.co.` is a valid FQDN that DNS and HTTP resolve
        identically, and the first version compared host strings exactly - so
        `BISON_BASE=https://send.resonategroup.co./api` would have mutated
        live campaigns with the guard reporting nothing to guard.
        """
        import src.providers.bison   # noqa: F401  - registers
        self.assertTrue(providers.is_prospect_facing(
            "https://send.resonategroup.co./api/campaigns/487/pause"))
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH",
                      "https://send.resonategroup.co./api/campaigns/487/pause")
        self.assertEqual([], self.opened)

    def test_case_does_not_evade_the_guard(self):
        import src.providers.bison   # noqa: F401
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH",
                      "https://SEND.ResonateGroup.CO/api/campaigns/487/pause")

    def test_a_malformed_url_does_not_raise_out_of_the_guard(self):
        """Also GLM's. `urlsplit("http://[tracking-link]").hostname` raises
        ValueError, and bracket placeholders are ordinary in scraped
        signature HTML. `str(url or "")` proved the function was meant to be
        total over garbage; it was not."""
        for bad in ("http://[tracking-link]", "http://[", "http://[::zz]"):
            with self.subTest(url=bad):
                self.assertIsNotNone(providers.host_of(bad))   # no raise

    def test_an_unreadable_destination_is_refused_rather_than_waved_through(self):
        """Fail-closed, deliberately. A URL nobody can parse is not evidence
        of safety, and it costs nothing real - urllib is about to reject it
        anyway."""
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH", "http://[tracking-link]/campaigns/1")
        self.assertEqual([], self.opened)

    def test_a_malformed_url_on_a_READ_is_still_not_refused(self):
        """The fail-closed direction applies to mutations only. A read of a
        garbage URL must reach urllib and fail there, as it always did."""
        with self.assertRaises(Exception) as caught:
            self.wire("GET", "http://[tracking-link]/x")
        self.assertNotIsInstance(caught.exception,
                                 providers.ProviderWriteRefused)

    def test_registration_and_lookup_normalise_through_the_same_function(self):
        """Two spellings of one host must not be able to disagree about
        whether it is guarded."""
        providers.guard_prospect_facing("https://Example.TEST./api")
        try:
            self.assertTrue(providers.is_prospect_facing(
                "https://example.test/x"))
            self.assertTrue(providers.is_prospect_facing(
                "https://EXAMPLE.TEST./x"))
        finally:
            providers._prospect_facing_hosts.discard("example.test")

    def test_an_unparseable_host_is_never_registered_as_guarded(self):
        before = set(providers._prospect_facing_hosts)
        providers.guard_prospect_facing("http://[tracking-link]")
        self.assertEqual(before, set(providers._prospect_facing_hosts))

    # ---------------------------------------------------------- the shape

    def test_a_swapped_transport_is_untouched_by_the_guard(self):
        """The reason the guard is in the wire and not in `request`. Tests
        replay cassettes through `set_transport` and exercise the write paths
        on purpose; refusing those would force a blanket opt-in across the
        suite, which is how a guard gets switched off."""
        calls = []

        def cassette(method, url, headers, body, timeout):
            calls.append(method)
            return 200, '{"ok": true}'

        previous = providers.set_transport(cassette)
        try:
            status, data = providers.request("PATCH", "https://example.test/x")
        finally:
            providers.set_transport(previous)
        self.assertEqual(200, status)
        self.assertEqual(["PATCH"], calls)

    def test_a_library_cannot_authorise_itself(self):
        """Buggie reached the transport THROUGH `providerwrites.perform`. An
        opt-in that a library could grant would have authorised the incident,
        so the authorization is an act at an entry point and this asserts
        that nothing in the write path has quietly taken one."""
        import src.providerwrites as providerwrites
        source = open(providerwrites.__file__, encoding="utf-8").read()
        self.assertNotIn("allow_writes", source)
        self.assertNotIn(providers.WRITES_ENV, source)

    # ----------------------------------------------------------- the log

    def test_a_refused_mutation_is_recorded_for_somebody_to_find(self):
        """Reading another agent's incident report is not a detection
        mechanism."""
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH")
        with open(os.environ["PROVIDER_WRITE_REFUSALS"], encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(1, len(rows))
        self.assertEqual("PATCH", rows[0]["method"])
        self.assertIn("487", rows[0]["url"])
        self.assertEqual(os.getpid(), rows[0]["pid"])

    def test_an_unwritable_log_does_not_turn_a_refusal_into_a_crash(self):
        """A full disk must not convert a refusal into a different exception
        that some caller catches and retries around."""
        os.environ["PROVIDER_WRITE_REFUSALS"] = os.path.join(
            self.tmp, "a-file", "nested", "x.jsonl")
        with open(os.path.join(self.tmp, "a-file"), "w") as f:
            f.write("")
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH")

    def test_an_authorized_write_is_not_logged_as_a_refusal(self):
        with providers.allow_writes("authorised"):
            with self.assertReachedWire():
                self.wire("PATCH")
        self.assertFalse(os.path.exists(
            os.environ["PROVIDER_WRITE_REFUSALS"]))


if __name__ == "__main__":
    unittest.main()
