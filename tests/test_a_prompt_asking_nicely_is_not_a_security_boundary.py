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
import threading
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import providers  # noqa: E402
# Imported for its REGISTRATION side effect, not for its API: `bison` calls
# `guard_prospect_facing` at import, and without it `send.resonategroup.co`
# is not in the guarded set and half these tests assert nothing. Test order
# must not decide whether the guard is armed.
from src.providers import bison, heyreach  # noqa: E402,F401


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
        # A ContextVar, not a list, since the thread-leak fix.
        providers._write_scopes.set(())
        self.addCleanup(providers._write_scopes.set, ())
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

    # ----------------------------------- GLM's second round, all confirmed

    def test_a_bytes_verb_does_not_evade_the_guard(self):
        """`str(b"post").upper()` is `"B'POST'"`, which is in no method set,
        so a bytes verb fell straight past the guard - while requests and
        httpx both normalise `b"post"` to POST and SEND IT. Reproduced before
        it was accepted."""
        for verb in (b"POST", b"post", bytearray(b"patch"), " patch ",
                     "Delete"):
            with self.subTest(verb=verb):
                with self.assertRaises(providers.ProviderWriteRefused):
                    providers.refuse_unauthorized_write(
                        verb,
                        "https://send.resonategroup.co/api/campaigns/487/x")

    def test_a_bytes_read_verb_is_still_not_refused(self):
        self.assertIsNone(providers.refuse_unauthorized_write(
            b"GET", "https://send.resonategroup.co/api/campaigns/487"))

    def test_the_authorization_does_not_leak_into_another_thread(self):
        """A plain module-level list let a worker THREAD read
        writes_allowed() -> True while the main thread held the block, and
        `gather` runs a pool of eight. Reproduced: the thread saw True.

        A ContextVar fails CLOSED into code that relied on the global scope,
        which is the safe direction and the point."""
        seen = []

        def worker():
            seen.append(providers.writes_allowed()[0])

        with providers.allow_writes("main thread only"):
            t = threading.Thread(target=worker)
            t.start()
            t.join()
        self.assertEqual([False], seen)

    def test_a_thread_spawned_inside_the_block_is_refused_not_permitted(self):
        refused = []

        def worker():
            try:
                self.wire("PATCH")
            except providers.ProviderWriteRefused:
                refused.append(True)
            except Exception:
                refused.append(False)

        with providers.allow_writes("main thread only"):
            t = threading.Thread(target=worker)
            t.start()
            t.join()
        self.assertEqual([True], refused)
        self.assertEqual([], self.opened)

    def test_nesting_still_works_after_the_contextvar_change(self):
        with providers.allow_writes("outer"):
            with providers.allow_writes("inner"):
                self.assertIn("inner", providers.writes_allowed()[1])
            allowed, why = providers.writes_allowed()
            self.assertTrue(allowed)
            self.assertIn("outer", why)
        self.assertFalse(providers.writes_allowed()[0])

    def test_the_guard_does_not_claim_to_stop_a_determined_insider(self):
        """GLM's first finding, CONCEDED rather than argued with: anything in
        this process can self-authorise. The guard stops reaching a mutation
        BY ACCIDENT, which is the failure that actually happened - Buggie
        passed a bad dict and fell through orchestrator.pause.

        This test pins the HONESTY, because overclaiming a safety property is
        the failure class the audit graded highest. The module must say what
        it is not."""
        source = open(providers.__file__, encoding="utf-8").read()
        self.assertIn("NOT enforcement against a determined in-process actor",
                      source)
        # And the concession is true: self-authorising really does work.
        with providers.allow_writes("an insider can do this"):
            self.assertTrue(providers.writes_allowed()[0])

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


class PostThatReadsTest(unittest.TestCase):
    """HeyReach answers its reads with POST, and the guard refused them all.

    The guard's own argument for a host-based scope listed every POST that is
    really a read - the model lanes, the enrichment providers, Slack - and
    concluded none of them belonged to a guarded host. HeyReach does.
    `/campaign/GetAll`, `/campaign/GetLeadsFromCampaign`,
    `/stats/GetOverallStats` and `/inbox/GetConversationsV2` are POSTs that
    read, they are what the LIVE 605732 watcher calls, and from 17:04 on
    2026-09-20 every one of them raised `ProviderWriteRefused`.

    It was invisible for a day because nothing already running had to
    re-import: the watcher started at 14:23 and holds the pre-guard module in
    memory. `provider_truth.py`, started fresh, crashed on the first call.

    These pin the exemption AND its edges. The exemption is the narrow thing
    that makes the guard survivable; the edges are why it is not a hole.
    """

    def setUp(self):
        self._env = os.environ.get(providers.WRITES_ENV)
        self.addCleanup(self._restore)
        os.environ.pop(providers.WRITES_ENV, None)
        providers._write_scopes.set(())
        self.addCleanup(providers._write_scopes.set, ())
        self.opened = []
        self._urlopen = providers.urllib.request.urlopen
        providers.urllib.request.urlopen = self._booby_trap
        self.addCleanup(setattr, providers.urllib.request, "urlopen",
                        self._urlopen)

    def _restore(self):
        if self._env is None:
            os.environ.pop(providers.WRITES_ENV, None)
        else:
            os.environ[providers.WRITES_ENV] = self._env

    def _booby_trap(self, *a, **k):
        self.opened.append(a[0].get_method() if a else "?")
        raise AssertionError("the wire was reached")

    def wire(self, method, url):
        return providers._urllib_transport(method, url, {}, None, 5)

    def assertReachedWire(self):
        return self.assertRaisesRegex(providers.HttpTransportError,
                                      "the wire was reached")

    # ------------------------------------------------ the exemption itself

    def test_every_declared_read_route_is_postable_without_authorization(self):
        """The regression. A diagnostic must not have to claim write
        authority it does not want in order to read a live campaign."""
        for route in heyreach.READ_ROUTES_ALL:
            with self.subTest(route=route):
                with self.assertReachedWire():
                    self.wire("POST", heyreach.BASE + route)

    def test_the_watcher_reads_that_a_restart_would_have_broken(self):
        """Named individually because these three are the live monitor's
        actual calls, and that monitor is the only thing watching 605732."""
        for route in ("/campaign/GetAll", "/campaign/GetLeadsFromCampaign",
                      "/stats/GetOverallStats"):
            with self.subTest(route=route):
                self.assertIn(route, heyreach.READ_ROUTES_ALL)
                with self.assertReachedWire():
                    self.wire("POST", heyreach.BASE + route)

    def test_a_query_string_does_not_defeat_the_match(self):
        with self.assertReachedWire():
            self.wire("POST", heyreach.BASE + "/campaign/GetAll?offset=0")

    # ------------------------------------------------------------ the edges

    def test_a_write_route_on_the_same_host_is_still_refused(self):
        """The exemption is per PATH. Being on a host that has declared some
        reads must buy a write route nothing at all."""
        for route in heyreach.WRITE_ROUTES:
            with self.subTest(route=route):
                with self.assertRaises(providers.ProviderWriteRefused):
                    self.wire("POST", heyreach.BASE + route)
        self.assertEqual([], self.opened)

    def test_only_post_is_exempt_on_a_declared_read_path(self):
        """A provider that overloads POST is the reason for the exemption. A
        PATCH to the same path is not that, and is refused."""
        url = heyreach.BASE + "/campaign/GetAll"
        for method in ("PUT", "PATCH", "DELETE", b"patch"):
            with self.subTest(method=method):
                with self.assertRaises(providers.ProviderWriteRefused):
                    self.wire(method, url)
        self.assertEqual([], self.opened)

    def test_a_traversal_or_a_suffix_matches_nothing(self):
        """Exact match on the parsed path, fail-closed. Each of these reads
        as a declared route to a careless eye and none of them is one."""
        for path in ("/campaign/GetAllPause",
                     "/campaign/GetAll/Pause",
                     "/x/campaign/GetAll",
                     "/campaign/%47etAll"):
            with self.subTest(path=path):
                with self.assertRaises(providers.ProviderWriteRefused):
                    self.wire("POST", heyreach.BASE + path)
        self.assertEqual([], self.opened)

    def test_the_exemption_is_scoped_to_the_host_that_declared_it(self):
        """The same path on the OTHER guarded provider is not a read."""
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("POST",
                      "https://send.resonategroup.co/api/public/campaign/GetAll")

    def test_the_incident_verb_is_still_refused(self):
        """The guard exists for this exact call. Kept here so a future
        widening of the read exemption has to walk past it."""
        with self.assertRaises(providers.ProviderWriteRefused):
            self.wire("PATCH",
                      "https://send.resonategroup.co/api/campaigns/487/pause")

    # -------------------------------------------------- declaration hygiene

    def test_declared_reads_and_write_routes_are_disjoint(self):
        """The day these overlap, the exemption IS a mutation. Compared as
        full paths, through the same joining the guard uses, because a
        module-relative comparison would miss a base-prefixed collision."""
        declared = providers.declared_reads(heyreach.BASE)
        writes = {providers.path_of(heyreach.BASE + r)
                  for r in heyreach.WRITE_ROUTES}
        self.assertEqual(set(), declared & writes)

    def test_the_declaration_covers_exactly_the_modules_read_allowlist(self):
        """`_read` enforces `READ_ROUTES_ALL` and the guard enforces what was
        declared. Two allowlists for one question drift; this pins them."""
        self.assertEqual(
            {providers.path_of(heyreach.BASE + r)
             for r in heyreach.READ_ROUTES_ALL},
            providers.declared_reads(heyreach.BASE))

    def test_the_get_only_routes_are_not_declared_as_postable(self):
        """`READ_GET_ROUTES` take their argument in the query string. A GET
        is never refused anyway, so declaring them would only assert that
        POST is allowed on them - which the module does not believe."""
        declared = providers.declared_reads(heyreach.BASE)
        for route in heyreach.READ_GET_ROUTES:
            with self.subTest(route=route):
                self.assertNotIn(providers.path_of(heyreach.BASE + route),
                                 declared)

    def test_the_other_guarded_provider_declares_no_post_reads(self):
        """EmailBison reads with GET throughout. If that changes, this test
        is where the change gets argued rather than assumed."""
        self.assertEqual(set(), providers.declared_reads(bison.base()))


if __name__ == "__main__":
    unittest.main()
