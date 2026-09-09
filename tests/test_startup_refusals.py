"""What the process refuses to become, and what now lets it stop refusing.

There are two sign-in mechanisms and exactly one is in force at a time:
demo sign-in, which takes an email address and believes it, and an identity
provider, which proves one. `AUTH_PROVIDER` chooses, and nothing on a
request can.

Three things could put this build somewhere it must not be, and all three
were reachable before these tests existed:

**Production mode.** `PRODUCTION-READINESS.md` said production "refuses to
start without AUTH_PROVIDER". Nothing called `config.verify()`, so nothing
refused anything.

**A reachable interface.** `DEPLOYMENT-PLAN.md` documented
`--host 0.0.0.0` as the start command, which published a console whose
sign-in screen asked only which user you would like to be.

**Configuration nothing reads.** `WEB_HOST` and `WEB_PORT` were declared,
reported by the settings screen, and consumed by no code path.

Both refusals read one predicate - `security.sign_in_proves_identity()` -
so the tests here come in pairs. Each asserts the refusal *and* the thing
it must not refuse: a guard that refuses everything passes a one-sided
test and ships a product nobody can run.
"""
import os
import unittest

from src import config
from src.web import app, security

# A complete, plausible identity provider configuration. No network is
# touched by any test in this file: `check_configuration` asks whether a
# provider is configured, never whether it answers.
OIDC_ENV = {
    "AUTH_PROVIDER": "oidc",
    "AUTH_ISSUER": "https://issuer.test",
    "AUTH_CLIENT_ID": "client-abc",
    "AUTH_CLIENT_SECRET": "secret-xyz",
    "AUTH_REDIRECT_URL": "https://app.test/auth/callback",
}


class EnvGuard(unittest.TestCase):
    """Restore every environment variable a test in here can touch."""

    VARS = ("APP_MODE", "DATABASE_URL", "QUEUE", "WEB_HOST", "WEB_PORT",
            "SESSION_SECRET", "AUTH_ALLOWED_DOMAINS") + tuple(OIDC_ENV)

    def setUp(self):
        self._prev = {k: os.environ.get(k) for k in self.VARS}
        for key in self.VARS:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def configure_provider(self):
        os.environ.update(OIDC_ENV)

    def configure_production(self):
        self.configure_provider()
        os.environ["APP_MODE"] = "production"
        # The persistence lever, not a database URL: there is no SQL backend
        # in this build, and QUEUE is what decides whether state survives a
        # deploy. `src/config.py` says why they were the wrong way round.
        os.environ["QUEUE"] = "/data/work/queue.jsonl"

    def serves(self, **kwargs):
        """Start a real server, assert it bound, and always close the socket."""
        server = app.serve(0, **kwargs)
        try:
            self.assertTrue(server.server_address[1])
        finally:
            server.server_close()

    def permits(self, host, demo=False):
        """The guard allows this, asserted without binding anything.

        `serve()` binds, and an address like `192.168.1.10` is not
        assignable on a laptop - a socket error there would look like the
        guard refusing when it did not. What is under test is
        `check_configuration`, so that is what is called.
        """
        app.check_configuration(host, demo)


class TestTheFactUnderneath(EnvGuard):
    """One predicate, two refusals. Asserted on its own so that if it ever
    becomes True by accident, both of them lifting is not silent."""

    def test_demo_sign_in_proves_nothing(self):
        self.assertFalse(security.sign_in_proves_identity())
        self.assertEqual(security.sign_in_mode(), security.DEMO_SIGN_IN)

    def test_a_configured_provider_does(self):
        self.configure_provider()
        self.assertTrue(security.sign_in_proves_identity())
        self.assertEqual(security.sign_in_mode(), security.OIDC_SIGN_IN)

    def test_an_unimplemented_provider_is_refused_not_ignored(self):
        """The dangerous answer is a shrug.

        `okta` is a plausible thing to type. Falling back to demo sign-in
        because of it would be unauthenticated access reached by way of a
        variable somebody set in order to turn authentication *on*.
        """
        os.environ["AUTH_PROVIDER"] = "okta"
        with self.assertRaises(security.AuthNotConfigured) as caught:
            security.sign_in_mode()
        self.assertIn("okta", str(caught.exception))

    def test_a_half_configured_provider_is_refused_and_says_which_half(self):
        self.configure_provider()
        os.environ.pop("AUTH_CLIENT_SECRET")
        with self.assertRaises(security.AuthNotConfigured) as caught:
            security.sign_in_mode()
        self.assertIn("AUTH_CLIENT_SECRET", str(caught.exception))


class TestProductionMode(EnvGuard):

    def test_an_empty_production_environment_refuses(self):
        os.environ["APP_MODE"] = "production"
        with self.assertRaises(RuntimeError) as caught:
            app.serve(0, demo=True)
        message = str(caught.exception)
        self.assertIn("AUTH_PROVIDER", message)
        self.assertNotIsInstance(caught.exception, app.Unauthenticated)

    def test_production_on_demo_sign_in_refuses(self):
        """Everything else set, no provider. The mechanism is the blocker."""
        os.environ["APP_MODE"] = "production"
        os.environ["QUEUE"] = "/data/work/queue.jsonl"
        with self.assertRaises(RuntimeError):
            app.serve(0, demo=True)

    def test_production_without_persistent_state_refuses(self):
        """A deployment that would silently lose every record.

        The provider is configured and sign-in would work, so nothing about
        authentication stops this - which is the point. An ephemeral queue
        looks healthy right up until the next deploy.
        """
        self.configure_production()
        os.environ.pop("QUEUE")
        with self.assertRaises(RuntimeError) as caught:
            app.serve(0, demo=True)
        self.assertIn("QUEUE", str(caught.exception))

    def test_an_unimplemented_provider_does_not_start_production(self):
        """Every AUTH_ name filled in, and one of them naming something that
        does not exist here.

        This is the trap the mechanism check exists for. The environment is
        complete, so `config.verify()` is satisfied and has nothing to say -
        an operator who cleared that error would believe authentication was
        on. It is the mechanism, checked second, that refuses.
        """
        self.configure_production()
        os.environ["AUTH_PROVIDER"] = "okta"
        self.assertEqual(config.report(config.PRODUCTION)["blockers"], [],
                         "the environment check is satisfied, which is what "
                         "makes this the dangerous case")
        with self.assertRaises(security.AuthNotConfigured):
            app.serve(0, demo=True)

    def test_a_missing_auth_variable_is_named_by_the_environment_check(self):
        """The other order: incomplete environment, caught earlier and with a
        more useful message than "not implemented"."""
        self.configure_production()
        os.environ.pop("AUTH_ISSUER")
        with self.assertRaises(RuntimeError) as caught:
            app.serve(0, demo=True)
        self.assertIn("AUTH_ISSUER", str(caught.exception))

    def test_production_with_a_provider_starts(self):
        """The other half, and the point of the whole exercise.

        A refusal that cannot be lifted by doing the right thing is not a
        guard, it is a wall. This is the assertion that would catch a guard
        left in place after the reason for it was removed.
        """
        self.configure_production()
        self.permits("0.0.0.0")
        self.serves(demo=False, host="0.0.0.0")

    def test_demo_mode_starts_with_an_empty_environment(self):
        """An empty environment must still be able to run the demonstration."""
        self.serves(demo=True)


class TestReachableBind(EnvGuard):

    PUBLIC = ("0.0.0.0", "", "::", "192.168.1.10")

    def test_a_public_bind_without_demo_or_a_provider_is_refused(self):
        for host in self.PUBLIC:
            with self.subTest(host=host):
                with self.assertRaises(app.Unauthenticated):
                    app.serve(0, demo=False, host=host)

    def test_a_public_bind_with_a_provider_is_allowed(self):
        """What proves identity is the provider, not the mode label.

        A build doing real sign-in may answer on a real interface even with
        `APP_MODE` unset, because the thing that made a public bind unsafe
        was never the label.
        """
        self.configure_provider()
        for host in self.PUBLIC:
            with self.subTest(host=host):
                self.permits(host)
        # And one of them all the way to a bound socket, so this is not only
        # a statement about the guard.
        self.serves(demo=False, host="0.0.0.0")

    def test_loopback_without_demo_is_allowed(self):
        """The operator's own machine is the design, not an exception."""
        self.serves(demo=False, host="127.0.0.1")

    def test_demo_may_be_published_because_it_has_nothing_to_leak(self):
        self.serves(demo=True, host="0.0.0.0")

    def test_the_empty_host_is_not_treated_as_loopback(self):
        """`ThreadingHTTPServer(("", port))` binds every interface. It is
        0.0.0.0 spelt in a way that looks like a default."""
        self.assertNotIn("", app.LOOPBACK)


class TestTheSessionCookie(EnvGuard):

    def test_it_is_not_secure_on_a_plain_loopback_session(self):
        """A `Secure` cookie over plain http signs the operator out of their
        own machine, which is how a security flag gets deleted."""
        cookie = security.session_cookie("t")
        self.assertNotIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_it_is_secure_once_a_provider_is_configured(self):
        self.configure_provider()
        self.assertIn("Secure", security.session_cookie("t"))

    def test_a_misconfigured_provider_gets_the_restrictive_answer(self):
        """"I do not know" resolves to the safe reading, not the convenient
        one. The process will not be serving in this state anyway."""
        os.environ["AUTH_PROVIDER"] = "okta"
        self.assertIn("Secure", security.session_cookie("t"))

    def test_clearing_keeps_the_flags(self):
        """A logout cookie that drops HttpOnly is still a cookie being set."""
        self.configure_provider()
        cookie = security.session_cookie(None, clearing=True)
        self.assertIn("Max-Age=0", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)


class TestDeclaredConfigurationIsRead(EnvGuard):

    def parsed(self, argv):
        """The parser `main()` itself uses, without starting a server.

        `app.parser()` and not a copy of it: a test that rebuilds the
        arguments passes while the real command line does something else.
        """
        return app.parser().parse_args(argv)

    def test_web_port_is_consumed(self):
        os.environ["WEB_PORT"] = "9101"
        self.assertEqual(self.parsed([]).port, 9101)

    def test_web_host_is_consumed(self):
        os.environ["WEB_HOST"] = "127.0.0.2"
        self.assertEqual(self.parsed([]).host, "127.0.0.2")

    def test_the_flag_still_wins(self):
        """A deployment passing --port $PORT must not be overridden by a
        stale WEB_PORT in the same environment."""
        os.environ["WEB_PORT"] = "9101"
        os.environ["WEB_HOST"] = "127.0.0.2"
        args = self.parsed(["--port", "9202", "--host", "127.0.0.3"])
        self.assertEqual((args.host, args.port), ("127.0.0.3", 9202))

    def test_the_defaults_are_unchanged_when_nothing_is_set(self):
        args = self.parsed([])
        self.assertEqual((args.host, args.port),
                         ("127.0.0.1", app.DEFAULT_PORT))


if __name__ == "__main__":
    unittest.main()
