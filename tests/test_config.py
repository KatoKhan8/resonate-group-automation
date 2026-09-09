"""Configuration validation: permissive in demo, closed in production.

The two failure modes pull in opposite directions, and both matter:

**A demo that needs credentials is a demo nobody runs.** Somebody should be
able to clone this and type `py -m src.web --demo` with an empty environment.
A startup check insisting on a ContactOut token to show fictional data is a
check that gets deleted within a week.

**A production process that starts half-configured is worse than one that
does not start.** Without a session secret every deploy signs everybody out;
without a real auth provider the demo sign-in list is unauthenticated access
to every workspace.

So the tests come in pairs: each one that asserts production refuses has a
partner asserting demo does not.
"""
import os
import unittest

from src import config


class Isolated(unittest.TestCase):
    """Every test starts from an environment with none of these set."""

    def setUp(self):
        self._previous = {name: os.environ.get(name)
                          for name, _, _, _ in config.VARIABLES}
        self._previous["APP_MODE"] = os.environ.get("APP_MODE")
        for name in self._previous:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TheMode(Isolated):

    def test_it_is_demo_unless_told_otherwise(self):
        self.assertEqual(config.mode(), config.DEMO)

    def test_an_unrecognised_mode_falls_back_to_demo(self):
        """The safe default, not the requested one."""
        os.environ["APP_MODE"] = "prodcution"
        self.assertEqual(config.mode(), config.DEMO)

    def test_production_is_honoured_when_spelled_correctly(self):
        os.environ["APP_MODE"] = "production"
        self.assertEqual(config.mode(), config.PRODUCTION)

    def test_case_and_whitespace_do_not_change_it(self):
        os.environ["APP_MODE"] = "  PRODUCTION  "
        self.assertEqual(config.mode(), config.PRODUCTION)


class DemoStartsWithNothing(Isolated):

    def test_an_empty_environment_has_no_blockers(self):
        self.assertEqual(config.report(config.DEMO)["blockers"], [])

    def test_verify_does_not_raise(self):
        config.verify(config.DEMO)

    def test_no_variable_blocks_in_demo(self):
        for row in config.report(config.DEMO)["variables"]:
            self.assertFalse(row["blocking"], row["name"])

    def test_it_still_reports_what_is_missing(self):
        """Permissive is not the same as silent."""
        report = config.report(config.DEMO)
        missing = [r for r in report["variables"] if not r["configured"]]
        self.assertTrue(missing)
        self.assertFalse(report["live_ready"])


class ProductionFailsClosed(Isolated):

    def test_an_empty_environment_blocks(self):
        self.assertTrue(config.report(config.PRODUCTION)["blockers"])

    def test_verify_raises_and_names_what_is_missing(self):
        with self.assertRaises(RuntimeError) as caught:
            config.verify(config.PRODUCTION)
        message = str(caught.exception)
        self.assertIn("AUTH_PROVIDER", message)
        self.assertIn("APP_MODE=demo", message,
                      "the refusal should say how to run it anyway")

    def test_every_piece_of_the_identity_provider_is_required(self):
        """All five, or none of it works.

        A half-configured provider is the state that produces a sign-in
        screen which looks real and cannot work, so each part blocks on its
        own rather than the set blocking as a lump.
        """
        blockers = config.report(config.PRODUCTION)["blockers"]
        for name in ("AUTH_PROVIDER", "AUTH_ISSUER", "AUTH_CLIENT_ID",
                     "AUTH_CLIENT_SECRET", "AUTH_REDIRECT_URL"):
            self.assertIn(name, blockers)

    def test_the_queue_is_required(self):
        """The one variable that decides whether client data survives.

        A container filesystem is ephemeral. With QUEUE unset the queue
        lands somewhere that is deleted on the next deploy, and an empty
        store is a valid store - nothing downstream can tell a fresh
        workspace from one whose records were thrown away. That is the
        failure mode a startup check is actually for.
        """
        self.assertIn("QUEUE", config.report(config.PRODUCTION)["blockers"])

    def test_the_database_url_is_not_required(self):
        """It was, and it required a database nothing uses.

        There is no SQL backend in this build - no driver, no schema, no
        query. Requiring a connection string sent an operator to provision
        Postgres for a process that would never open it, while the variable
        that actually decides whether state persists was optional. The two
        were the wrong way round.
        """
        self.assertNotIn("DATABASE_URL",
                         config.report(config.PRODUCTION)["blockers"])

    def test_the_session_secret_is_no_longer_required(self):
        """It was required and read by nothing.

        `SESSION_SECRET` blocked production while production authentication
        did not exist, which made it the thing an operator set to clear an
        error - and clearing it changed nothing, because sessions are opaque
        tokens held in this process and there is no cookie to sign. The
        requirement it was standing in for is now five variables that gate a
        real identity provider. Removing a placebo is not weakening a check;
        leaving one in place is how the real checks stop being believed.
        """
        self.assertNotIn("SESSION_SECRET",
                         config.report(config.PRODUCTION)["blockers"])

    def test_a_real_auth_provider_is_required(self):
        """Demo sign-in in production is unauthenticated access."""
        self.assertIn("AUTH_PROVIDER",
                      config.report(config.PRODUCTION)["blockers"])

    def production_environment(self):
        for name, value in (("AUTH_PROVIDER", "oidc"),
                            ("AUTH_ISSUER", "https://issuer.test"),
                            ("AUTH_CLIENT_ID", "client"),
                            ("AUTH_CLIENT_SECRET", "secret"),
                            ("AUTH_REDIRECT_URL",
                             "https://app.test/auth/callback"),
                            ("QUEUE", "/data/work/queue.jsonl")):
            os.environ[name] = value

    def test_setting_them_clears_the_block(self):
        self.production_environment()
        report = config.report(config.PRODUCTION)
        self.assertEqual(report["blockers"], [])
        config.verify(config.PRODUCTION)

    def test_a_missing_provider_key_never_blocks(self):
        """This build does not call providers.

        A deployment that refused to start without a ContactOut token could
        not run a demonstration, and would be turned off rather than fixed.
        """
        self.production_environment()
        report = config.report(config.PRODUCTION)
        self.assertEqual(report["blockers"], [])
        self.assertFalse(report["live_ready"],
                         "no provider is configured, so live work is not "
                         "ready - which is correct and must still be said")


class ItNeverReturnsAValue(Isolated):
    """The same discipline as security.credential_status: names only."""

    def test_a_configured_secret_is_reported_as_a_boolean(self):
        os.environ["SLACK_BOT_TOKEN"] = "a-value-nobody-should-see"
        report = config.report(config.DEMO)
        self.assertNotIn("a-value-nobody-should-see", str(report))
        row = next(r for r in report["variables"]
                   if r["name"] == "SLACK_BOT_TOKEN")
        self.assertTrue(row["configured"])

    def test_the_cli_prints_no_value(self):
        import contextlib
        import io as _io

        os.environ["SLACK_BOT_TOKEN"] = "another-value-nobody-should-see"
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            config.main([])
        self.assertNotIn("another-value-nobody-should-see", out.getvalue())
        self.assertIn("SLACK_BOT_TOKEN", out.getvalue())


class TheClassification(unittest.TestCase):

    def test_every_variable_is_classified(self):
        for name, classification, group, why in config.VARIABLES:
            self.assertIn(classification,
                          (config.REQUIRED, config.PRODUCTION_ONLY,
                           config.LIVE, config.OPTIONAL), name)

    def test_every_variable_says_why_it_matters(self):
        """The `why` is what somebody reads when the check fails.

        Without it, "SESSION_SECRET is not set" is a line people work around
        rather than fix.
        """
        for name, _, _, why in config.VARIABLES:
            self.assertTrue(why and len(why) > 20, name)

    def test_no_variable_is_named_twice(self):
        names = [name for name, _, _, _ in config.VARIABLES]
        self.assertEqual(len(names), len(set(names)))

    def test_every_provider_key_is_live_rather_than_required(self):
        for name, classification, group, _ in config.VARIABLES:
            if group in ("providers", "slack"):
                self.assertEqual(classification, config.LIVE, name)


class TheCliExitCode(Isolated):

    def test_it_exits_non_zero_when_production_would_not_start(self):
        import contextlib
        import io as _io

        with contextlib.redirect_stdout(_io.StringIO()):
            self.assertEqual(config.main(["--mode", "production"]), 1)

    def test_it_exits_zero_for_demo(self):
        import contextlib
        import io as _io

        with contextlib.redirect_stdout(_io.StringIO()):
            self.assertEqual(config.main(["--mode", "demo"]), 0)

    def test_json_output_parses(self):
        import contextlib
        import io as _io
        import json

        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            config.main(["--json"])
        payload = json.loads(out.getvalue())
        self.assertIn("variables", payload)
        self.assertIn("mode", payload)


if __name__ == "__main__":
    unittest.main()
