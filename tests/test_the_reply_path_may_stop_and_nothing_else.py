"""The reply path can stop a lead. It cannot enrol, pause, resume or create.

## The defect this closes

2026-09-23. `reply_watch_loop` opts into no write scope - it sets
`REPLY_POLL_ENABLED=1` and nothing else - so `inbound._stop_at_provider` was
refused by `providers.refuse_unauthorized_write` on every call, and the
refusal was caught and returned as a dict nobody read.

Measured, from `work/provider-write-refusals.jsonl`:

    2026-09-23T11:19:35Z POST .../campaigns/491/leads/stop-future-emails
    argv: ['reply_watch_loop.py', '--interval', '300']

Megan Ward replied "no thank you" on LinkedIn at 11:12:33Z and stayed
`in_sequence` in EmailBison 491 for 2h07m.

**It hid behind a coincidence.** EmailBison marks a lead `replied` by itself
when the reply arrives BY EMAIL, and four of the five locally-stopped
contacts read `replied` at the provider for that reason alone. The
cross-channel case - a LinkedIn reply stopping an EMAIL sequence - is the
only one that depends on this call, and it was the broken one.

## Why a route-scoped grant and not `RESONATE_PROVIDER_WRITES=1`

Setting the env var on the loop would fix the stop and hand the same process
authority to enrol, pause, resume and create - giving back exactly what the
487 guard was built to take away. `allow_writes(only=...)` keeps the grant
the size of the job, and these tests are what make that a property rather
than a comment.
"""
import os
import unittest

from src import inbound, providers


ENROL = "https://send.resonategroup.co/api/campaigns/491/leads"
PAUSE = "https://send.resonategroup.co/api/campaigns/491/pause"
RESUME = "https://send.resonategroup.co/api/campaigns/491/resume"
CREATE = "https://send.resonategroup.co/api/campaigns"
STOP_EMAIL = "https://send.resonategroup.co/api/campaigns/491/leads/stop-future-emails"
STOP_LINKEDIN = "https://api.heyreach.io/api/public/campaign/StopLeadInCampaign"


class TheStopRoutesAreNamed(unittest.TestCase):

    def test_both_providers_stop_routes_are_listed(self):
        self.assertIn("stop-future-emails", inbound.STOP_ROUTES)
        self.assertIn("stopleadincampaign", inbound.STOP_ROUTES)

    def test_they_are_fragments_not_whole_urls(self):
        """A host change must not silently void the allowlist."""
        for route in inbound.STOP_ROUTES:
            self.assertNotIn("://", route)
            self.assertEqual(route, route.lower())


class AScopedGrantPermitsOnlyItsRoutes(unittest.TestCase):

    def scope(self):
        return providers.allow_writes("stop on reply", only=inbound.STOP_ROUTES)

    def test_it_permits_the_email_stop(self):
        self.assertTrue(self.scope().permits(STOP_EMAIL))

    def test_it_permits_the_linkedin_stop_whatever_its_casing(self):
        self.assertTrue(self.scope().permits(STOP_LINKEDIN))
        self.assertTrue(self.scope().permits(STOP_LINKEDIN.lower()))

    def test_it_refuses_enrol_pause_resume_and_create(self):
        scope = self.scope()
        for url in (ENROL, PAUSE, RESUME, CREATE):
            with self.subTest(url=url):
                self.assertFalse(
                    scope.permits(url),
                    f"the reply path was permitted to write {url}")

    def test_an_unscoped_grant_still_permits_everything(self):
        """The wide form must keep working for the callers that need it."""
        wide = providers.allow_writes("a deliberate broad grant")
        for url in (ENROL, PAUSE, RESUME, CREATE, STOP_EMAIL):
            self.assertTrue(wide.permits(url))

    def test_an_empty_allowlist_is_refused_at_construction(self):
        """An `only` computed to empty is a bug, not a silent authorise-all."""
        with self.assertRaises(ValueError):
            providers.allow_writes("reason", only=())


class TheGrantReachesTheGuard(unittest.TestCase):
    """End to end through `writes_allowed`, which is what the guard calls."""

    def test_outside_any_scope_nothing_is_allowed(self):
        allowed, why = providers.writes_allowed(STOP_EMAIL)
        self.assertFalse(allowed)
        self.assertIn("no", why.lower())

    def test_inside_the_scope_the_stop_is_allowed(self):
        with providers.allow_writes("stop on reply", only=inbound.STOP_ROUTES):
            allowed, why = providers.writes_allowed(STOP_EMAIL)
        self.assertTrue(allowed)
        self.assertIn("stop on reply", why)

    def test_inside_the_scope_an_enrol_is_still_refused(self):
        with providers.allow_writes("stop on reply", only=inbound.STOP_ROUTES):
            allowed, why = providers.writes_allowed(ENROL)
        self.assertFalse(allowed, "the reply path could enrol a lead")
        self.assertIn("does not cover", why)

    def test_the_refusal_distinguishes_wrong_route_from_no_scope(self):
        """Two different investigations; they must not print the same."""
        _a, no_scope = providers.writes_allowed(ENROL)
        with providers.allow_writes("stop on reply", only=inbound.STOP_ROUTES):
            _b, wrong_route = providers.writes_allowed(ENROL)
        self.assertNotEqual(no_scope, wrong_route)

    def test_the_scope_closes(self):
        with providers.allow_writes("stop on reply", only=inbound.STOP_ROUTES):
            pass
        allowed, _why = providers.writes_allowed(STOP_EMAIL)
        self.assertFalse(allowed, "the scope outlived its block")


class TheStopPathAsksForTheNarrowGrant(unittest.TestCase):
    """ASSERTED ON BEHAVIOUR, NOT ON THE TEXT OF A FUNCTION.

    These two tests used to call `inspect.getsource(inbound._stop_at_provider)`
    and grep it for "allow_writes" and "STOP_ROUTES". The scope later moved
    into `_stop_one`, where the per-channel work actually happens, and both
    tests have been failing ever since - carried in the suite baseline as
    accepted failures - **while the behaviour they were written to protect
    was correct the whole time.**

    That is the failure mode CLAUDE.md names: "Searching source for words
    produces a test that fails when somebody writes a comment". It is worse
    than a false alarm. A guard that fails for a reason nobody believes gets
    filed under "known", and then it cannot raise its voice on the day the
    scope really does go missing.

    So the question is asked of the running code instead: at the moment the
    reply path calls a stopper, what does the write guard actually permit?
    That holds no matter which function holds the `with`.
    """

    def _permissions_seen_by(self, channel):
        """Drive the reply path and capture what the guard allowed INSIDE it."""
        seen = {}

        def probe(rec, contact, why, **kw):
            seen["stop_email"], _ = providers.writes_allowed(STOP_EMAIL)
            seen["stop_linkedin"], _ = providers.writes_allowed(STOP_LINKEDIN)
            seen["enrol"], _ = providers.writes_allowed(ENROL)
            seen["pause"], _ = providers.writes_allowed(PAUSE)
            seen["resume"], _ = providers.writes_allowed(RESUME)
            seen["create"], _ = providers.writes_allowed(CREATE)
            return {"stopped": True, "already": False}

        from src import leadstop
        target = ("stop_contact" if channel == "email"
                  else "stop_linkedin_contact")
        original = getattr(leadstop, target)
        setattr(leadstop, target, probe)
        try:
            inbound._stop_at_provider(
                {"id": "r1"},
                {"key": "c1", "bison_lead_id": "1", "heyreach_lead_id": "2",
                 "linkedin": "https://www.linkedin.com/in/example-person/"},
                rows=[])
        finally:
            setattr(leadstop, target, original)
        return seen

    def test_the_linkedin_stop_is_permitted_where_the_work_happens(self):
        seen = self._permissions_seen_by("linkedin")
        self.assertTrue(seen.get("stop_linkedin"),
                        "the reply path cannot stop a LinkedIn lead")

    def test_the_email_stop_is_permitted_where_the_work_happens(self):
        seen = self._permissions_seen_by("email")
        self.assertTrue(seen.get("stop_email"),
                        "the reply path cannot stop an email lead")

    def test_and_nothing_else_is_permitted_while_it_runs(self):
        """The other half of the guarantee, and the half worth having."""
        for channel in ("email", "linkedin"):
            seen = self._permissions_seen_by(channel)
            for verb in ("enrol", "pause", "resume", "create"):
                self.assertFalse(
                    seen.get(verb),
                    "the reply path could %s while stopping on %s"
                    % (verb, channel))

    def test_the_scope_does_not_outlive_the_reply(self):
        """A grant that leaks past its block would hand the whole loop the
        authority the 487 guard exists to take away."""
        self._permissions_seen_by("linkedin")
        for url in (STOP_EMAIL, STOP_LINKEDIN, ENROL):
            allowed, _why = providers.writes_allowed(url)
            self.assertFalse(allowed, "the scope outlived the reply path")

    def test_it_does_not_reach_for_the_env_var(self):
        """`RESONATE_PROVIDER_WRITES=1` would re-open everything, so the
        reply path must not be what sets it. Asserted by RUNNING without it
        and checking the narrow grant is what did the permitting: a wide
        grant would have permitted the enrol above too."""
        self.assertNotIn("RESONATE_PROVIDER_WRITES", os.environ,
                         "this test is meaningless with the env var set")
        seen = self._permissions_seen_by("linkedin")
        self.assertTrue(seen.get("stop_linkedin"))
        self.assertFalse(seen.get("enrol"))


if __name__ == "__main__":
    unittest.main()
