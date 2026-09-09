"""The deployment files, checked against the application rather than read.

A `Procfile`, a `railway.json` and a `requirements.txt` are four lines of
configuration that look like a deployment and prove nothing on their own -
the exact shape `CLAUDE.md` calls existence mistaken for function. A start
command with a flag this build refuses, a health check pointing at a route
that needs a session, or an environment template that has drifted from
`src/config.py` all pass a reading and fail a deploy.

So each of them is asserted against the thing it configures:

  Procfile / railway.json   parsed by `app.parser()`, the parser `main()`
                            itself uses, then put through
                            `app.check_configuration` - the same refusal a
                            real start goes through - under *each* of the
                            environments a deployment actually runs it in
  healthcheckPath           dispatched over HTTP with no session
  requirements.txt          checked against every import in `src/`

`config/.env.example` is deliberately absent from that list.
`tests/test_secrets.py` already checks it in both directions - every
variable the code reads is named, every variable named is read, every
classified variable is present, and none carries a value - and a second
set of assertions over the same file is a second place that can disagree
with the first.
"""
import ast
import io
import json
import os
import shlex
import sys
import unittest
import urllib.request

from src import config
from src.web import app
from tests.webbase import WebTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    return io.open(os.path.join(ROOT, *parts), encoding="utf-8").read()


def start_command(line):
    """The arguments a start command hands to `python -m src.web`.

    `$PORT` is what the platform substitutes; 0 stands in for it, which is
    also what the tests bind.
    """
    words = shlex.split(line.replace("$PORT", "0"))
    module = words.index("src.web")
    return words[module + 1:]


class TestTheStartCommands(unittest.TestCase):
    """Every start command this repository ships must actually start."""

    def commands(self):
        found = {}
        for line in read("Procfile").splitlines():
            if ":" in line and not line.startswith("#"):
                name, _, command = line.partition(":")
                found[f"Procfile {name.strip()}"] = command.strip()
        railway = json.loads(read("railway.json"))
        found["railway.json startCommand"] = railway["deploy"]["startCommand"]
        return found

    def environment(self, **values):
        """Run a check with exactly these variables set, then put it back."""
        names = ("APP_MODE", "QUEUE", "AUTH_PROVIDER", "AUTH_ISSUER",
                 "AUTH_CLIENT_ID", "AUTH_CLIENT_SECRET", "AUTH_REDIRECT_URL")
        previous = {k: os.environ.get(k) for k in names}
        for key in names:
            os.environ.pop(key, None)
        os.environ.update(values)
        try:
            yield_to = self.commands()
            for where, command in yield_to.items():
                args = app.parser().parse_args(start_command(command))
                demo = args.demo or config.demo_estate_requested()
                app.check_configuration(args.host, demo)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_the_shipped_command_runs_the_published_demonstration(self):
        """One command, and the environment says which service this is.

        `APP_MODE=demo`, set explicitly, is what the demonstration sets.
        """
        self.environment(APP_MODE="demo")

    def test_the_same_command_runs_the_real_deployment(self):
        """The other service. Same command, different environment.

        This is the assertion the old version of this file could not make:
        the only start command the repository shipped hardcoded `--demo`,
        so a production deploy from it would have served fictional
        companies at a production URL - safe, and wrong in the way that is
        worst, which is convincingly.
        """
        self.environment(APP_MODE="production",
                         QUEUE="/data/work/queue.jsonl",
                         AUTH_PROVIDER="oidc",
                         AUTH_ISSUER="https://accounts.google.com",
                         AUTH_CLIENT_ID="client",
                         AUTH_CLIENT_SECRET="secret",
                         AUTH_REDIRECT_URL="https://app.test/auth/callback")

    def test_the_same_command_refuses_when_the_environment_says_neither(self):
        """No estate to serve and nothing proving identity, on a public bind.

        The command is identical. What changed is that nothing in the
        environment makes it safe, and it fails closed rather than picking
        one of the two meanings.
        """
        with self.assertRaises(Exception) as caught:
            self.environment()
        self.assertNotIsInstance(caught.exception, AssertionError)

    def test_they_are_the_same_command(self):
        """Two files, one command. A platform reads one of them and which one
        depends on how the service was created."""
        self.assertEqual(len(set(self.commands().values())), 1,
                         f"start commands disagree: {self.commands()}")

    def test_a_public_bind_without_demo_would_be_caught_here(self):
        """The other half: this test must be able to fail.

        If `check_configuration` were ever softened, the assertion above
        would pass for a command that publishes a real estate, so the same
        call is made with the unsafe shape and required to refuse.
        """
        args = app.parser().parse_args(["--host", "0.0.0.0", "--port", "0"])
        with self.assertRaises(app.Unauthenticated):
            app.check_configuration(args.host, args.demo)

    def test_one_replica_only(self):
        """State is JSONL under a file lock and demo state is per process.

        Two replicas would either corrupt the store or serve two different
        estates behind one URL. PRODUCT-GAPS.md 5.
        """
        railway = json.loads(read("railway.json"))
        self.assertEqual(railway["deploy"]["numReplicas"], 1)


class TestTheHealthCheck(WebTest):

    def test_the_configured_path_answers_without_a_session(self):
        path = json.loads(read("railway.json"))["deploy"]["healthcheckPath"]
        with urllib.request.urlopen(self.base + path, timeout=10) as answer:
            self.assertEqual(answer.status, 200)
            body = json.loads(answer.read())
        self.assertTrue(body["ok"])
        self.assertFalse(body["live_sending"])


class TestRequirements(unittest.TestCase):

    def test_requirements_declares_no_packages(self):
        lines = [l.strip() for l in read("requirements.txt").splitlines()]
        self.assertEqual([l for l in lines if l and not l.startswith("#")], [])

    def test_and_that_is_true_of_the_source(self):
        """The claim, checked. Every import in `src/` is stdlib or local."""
        stdlib = set(sys.stdlib_module_names)
        outside = {}
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "src")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                tree = ast.parse(io.open(path, encoding="utf-8").read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0]
                            if top not in stdlib and top != "src":
                                outside.setdefault(top, path)
                    elif isinstance(node, ast.ImportFrom):
                        if node.level:          # relative: inside this package
                            continue
                        top = (node.module or "").split(".")[0]
                        if top and top not in stdlib and top not in ("src",
                                                                     "tests"):
                            outside.setdefault(top, path)
        self.assertEqual(outside, {},
                         "src/ imports something that is not in the standard "
                         "library, so requirements.txt is no longer true")


if __name__ == "__main__":
    unittest.main()
