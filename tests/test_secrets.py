"""Credentials must not leak, into the repository or into output. Part 31.

Nothing here contains a real secret. The synthetic values below stand in for
one, and the tests prove that a value shaped like a credential does not survive
a URL, an exception, a log line or a validation report.
"""
import os
import re
import subprocess
import unittest

from src import providers, validate
from src.providers import apify, deliverable
from tests.base import ProviderTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Synthetic. Long and distinctive so a leak would be obvious.
FAKE_SECRET = "sk-synthetic-000-do-not-use-1234567890abcdef"

ENV_VARS = ("CONTACTOUT_TOKEN", "BLITZ_API_KEY", "AIARK_KEY", "REOON_KEY", "DELIVERABLE_KEY",
            "BISON_KEY", "HEYREACH_KEY", "APIFY_TOKEN", "SLACK_BOT_TOKEN",
            "SLACK_SIGNING_SECRET")

# Not a credential: a switch. Named here so the example file may carry it.
SWITCHES = ("BISON_BASE", "SLACK_LIVE")


def _non_secret_names():
    """Everything else the example file may name, read from the code.

    Derived rather than typed. A hand-maintained list here would have to be
    edited every time a state file or a configuration variable is added, and
    the edit that gets forgotten is the one that makes this test fail for a
    reason unrelated to secrets - which is how a secret-scanning test ends up
    being weakened to get a build green.

    Three sources, each the authority for its own set:
      * `store.STATE_OVERRIDES` - where state files may be redirected
      * `config.VARIABLES` - everything the app classifies by mode
      * a short literal list for names that are neither

    The AUTH_ names used to be in that literal list, described as reserved
    for an eventual provider. They are classified in `config.VARIABLES` now
    because something reads them, so they arrive by the second route and
    listing them here as well would be a second place to maintain.
    """
    from src import config as app_config
    from src import store

    reserved = (
        # Reserved for the deployment described in DEPLOYMENT-PLAN.md. Named
        # in the example so a platform's secret store can be populated before
        # the migration rather than during it.
        "DATABASE_POOL_SIZE", "REDIS_URL", "WORKER_CONCURRENCY",
        "REPORT_STORAGE_URL",
        # Deliverable's contract overrides. Only set if the provider changes
        # something; the adapter's defaults are already correct.
        "DELIVERABLE_RESULT_SHAPE", "DELIVERABLE_BASE", "DELIVERABLE_VERIFY",
        "DELIVERABLE_STATUS", "DELIVERABLE_AUTH", "DELIVERABLE_METHOD",
        # Output and config locations.
        "OUT", "CLIENTS_DIR", "WEB_QUIET",
    )
    return tuple(sorted(set(("QUEUE",) + store.STATE_OVERRIDES
                            + tuple(app_config.BY_NAME)
                            + reserved)))


class TestTheEnvFileIsIgnored(unittest.TestCase):
    def test_git_ignores_config_env(self):
        result = subprocess.run(["git", "check-ignore", "-v", "config/.env"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(".gitignore", result.stdout)

    def test_config_env_is_not_tracked(self):
        result = subprocess.run(["git", "ls-files", "config/.env"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "")

    def test_the_work_directory_is_ignored(self):
        for path in ("work/queue.jsonl", "work/validation/x.json",
                     "work/apify/raw.json"):
            result = subprocess.run(["git", "check-ignore", "-v", path],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, path)

    def test_the_example_file_carries_no_values(self):
        with open(os.path.join(ROOT, "config", ".env.example"),
                  encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, _, value = line.partition("=")
                self.assertIn(name, ENV_VARS + SWITCHES + _non_secret_names(),
                              f"{name} is in the example file but nothing "
                              f"reads it")
                self.assertEqual(value, "",
                                 f"{name} has a value in the example file")

    def test_every_variable_the_code_reads_is_in_the_example(self):
        with open(os.path.join(ROOT, "config", ".env.example"),
                  encoding="utf-8") as f:
            text = f.read()
        for name in ENV_VARS:
            self.assertIn(name, text, name)

    def test_every_classified_variable_is_in_the_example(self):
        """The other direction, for the configuration model.

        `src/config.py` decides what production requires. A variable it
        classifies but the example file never mentions is a variable somebody
        discovers when a deployment refuses to start.
        """
        from src import config as app_config

        with open(os.path.join(ROOT, "config", ".env.example"),
                  encoding="utf-8") as f:
            text = f.read()
        for name in app_config.BY_NAME:
            self.assertIn(name, text, name)

    def test_every_state_override_is_in_the_example(self):
        from src import store

        with open(os.path.join(ROOT, "config", ".env.example"),
                  encoding="utf-8") as f:
            text = f.read()
        for name in ("QUEUE",) + store.STATE_OVERRIDES:
            self.assertIn(name, text, name)


class TestNoRealCredentialInTheRepository(unittest.TestCase):
    def tracked_files(self):
        result = subprocess.run(["git", "ls-files"], cwd=ROOT,
                                capture_output=True, text=True)
        return [f for f in result.stdout.splitlines()
                if f.endswith((".py", ".json", ".jsonl", ".md", ".yaml", ".csv",
                               ".txt"))]

    def test_no_tracked_file_contains_a_credential_shaped_assignment(self):
        pattern = re.compile(
            r"(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*[\"'][A-Za-z0-9_/+-]{12,}",
            re.I)
        offenders = []
        for name in self.tracked_files():
            path = os.path.join(ROOT, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            for match in pattern.finditer(text):
                if "test-key-not-real" in match.group(0):
                    continue
                if "synthetic" in match.group(0).lower():
                    continue
                offenders.append(f"{name}: {match.group(0)[:40]}")
        self.assertEqual(offenders, [])

    def test_no_fixture_contains_a_long_opaque_token(self):
        pattern = re.compile(r"\b(sk|pat|apify_api|xox[baprs])[-_][A-Za-z0-9]{16,}")
        offenders = []
        for name in self.tracked_files():
            if not name.startswith("tests/"):
                continue
            with open(os.path.join(ROOT, name), encoding="utf-8",
                      errors="replace") as f:
                text = f.read()
            for match in pattern.finditer(text):
                if "synthetic" in match.group(0):
                    continue
                offenders.append(f"{name}: {match.group(0)[:20]}")
        self.assertEqual(offenders, [])


class TestRedaction(ProviderTest):
    def test_a_token_in_a_query_string_is_removed(self):
        url = f"https://api.apify.com/v2/users/me?token={FAKE_SECRET}"
        self.assertNotIn(FAKE_SECRET, providers.redact(url))
        self.assertIn("token=***", providers.redact(url))

    def test_a_key_in_a_query_string_is_removed(self):
        url = f"https://emailverifier.reoon.com/api/v1/verify?email=a@b.test&key={FAKE_SECRET}"
        self.assertNotIn(FAKE_SECRET, providers.redact(url))

    def test_an_authorization_header_value_is_removed(self):
        headers = {"Authorization": f"Bearer {FAKE_SECRET}",
                   "X-API-KEY": FAKE_SECRET, "token": FAKE_SECRET}
        redacted = providers.redact(headers)
        self.assertNotIn(FAKE_SECRET, str(redacted))
        for value in redacted.values():
            self.assertEqual(value, "***")

    def test_the_basic_marker_survives_because_it_is_not_a_secret(self):
        self.assertEqual(providers.redact({"authorization": "basic"}),
                         {"authorization": "basic"})

    def test_a_provider_error_carrying_a_url_is_redacted(self):
        os.environ["APIFY_TOKEN"] = FAKE_SECRET

        def explode(method, url, headers, body, timeout):
            raise providers.ProviderError(f"URLError for {url}")

        providers.set_transport(explode)
        result = apify.check()
        self.assertNotIn(FAKE_SECRET, str(result))

    def test_a_health_result_never_carries_a_key(self):
        saved = {name: os.environ.get(name) for name in ENV_VARS}
        for name in ENV_VARS:
            os.environ[name] = FAKE_SECRET
        try:
            from src import check
            for result in check.run():
                self.assertNotIn(FAKE_SECRET, str(result), result["provider"])
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_the_validation_report_redacts_an_address_and_a_token(self):
        text = validate.redact(
            f"verifying someone@mine.test with token={FAKE_SECRET}")
        self.assertNotIn(FAKE_SECRET, text)
        self.assertNotIn("someone@mine.test", text)

    def test_a_deliverable_request_url_redacts_its_key(self):
        os.environ["DELIVERABLE_KEY"] = FAKE_SECRET
        self.confirm_deliverable_contract()
        deliverable.configure(auth="query")
        plan = deliverable.build_request("someone@example.test")
        self.assertIn(FAKE_SECRET, plan["url"])          # it is really in there
        self.assertNotIn(FAKE_SECRET, providers.redact(plan["url"]))


class TestNoCredentialReachesState(ProviderTest):
    def test_no_module_writes_a_key_into_the_record(self):
        import inspect

        from src import enrich, generate, research, verification
        for module in (enrich, generate, research, verification):
            source = inspect.getsource(module)
            for name in ENV_VARS:
                self.assertNotIn(name, source, module.__name__)

    def test_the_validation_sink_is_under_the_ignored_work_directory(self):
        self.assertIn("work", validate.output_dir())

    def test_keys_are_read_at_call_time_not_at_import(self):
        """Asked in a subprocess, for the reason given in `tests/test_audit.py`.

        Reloading these two in-process rebound `ContractNotVerified`,
        `UnsafeURL` and `ScrapeRefused` to new classes while every existing
        `except` clause kept the old ones, which is a silent way to disable
        exception handling for the remainder of the run.
        """
        import subprocess
        import sys

        env = dict(os.environ)
        for key in ENV_VARS:
            env.pop(key, None)
        done = subprocess.run(
            [sys.executable, "-c",
             "import src.providers.deliverable, src.providers.apify"],
            env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0,
                         "a provider wanted a credential at import time: "
                         + done.stderr)


if __name__ == "__main__":
    unittest.main()
