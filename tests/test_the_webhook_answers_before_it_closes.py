"""2f — the webhook receiver answers a refusal BEFORE closing, and records only.

THE FINDING THIS FILE IS BUILT ON. `test_upload_is_never_truncated
.AnOversizedUploadIsRefused`, all four of it, fails on Linux and passes on
Windows with `BrokenPipeError: [Errno 32] Broken pipe`. The server refuses an
oversized body and closes while the client is still sending; on Linux the
client gets EPIPE and never reads the refusal at all. A sender in that
position has a transport error instead of an answer, and retries forever.

The receiver in 2f runs on that same Linux host, so it has to get this right.

HONEST LIMIT OF THESE TESTS, stated because it would otherwise be a green
that means less than it looks. **This suite runs on Windows**, where the
original four tests PASS anyway. So the oversize test below is a weaker
witness here than it will be on the host — it cannot, on this machine,
distinguish "drains correctly" from "got away with it".

That is why the drain is asserted THREE ways, only one of which is
platform-dependent:

  1. the client reads the refusal and it names the limit   (platform-dependent)
  2. the server logs that it DRAINED the announced bytes   (platform-independent)
  3. the drained bytes are recorded NOWHERE               (platform-independent)

2 and 3 are the ones that will still mean something on the host.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import importlib.util  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "webhook_receiver",
    os.path.join(ROOT, "scripts", "server", "webhook_receiver.py"))
wr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(wr)

SECRET = "zz-not-a-real-signing-secret"


class _Serving(unittest.TestCase):
    """A real receiver on loopback. Loopback is not the network."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-webhook-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.records = os.path.join(self.tmp, "records")
        self.log = io.StringIO()
        self._stderr, sys.stderr = sys.stderr, self.log
        self.httpd = wr.serve(self.records, port=0, secret=SECRET)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)

    def _stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=10)
        sys.stderr = self._stderr

    def url(self, path=wr.PATH):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def post(self, body, signature=None, path=wr.PATH, content_length=None):
        """Returns (status, decoded body). An HTTPError still carries one -
        which is the entire point of this file."""
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers[wr.SIGNATURE_HEADER] = signature
        if content_length is not None:
            headers["Content-Length"] = str(content_length)
        req = urllib.request.Request(self.url(path), body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8", "replace")

    def recorded(self):
        if not os.path.isdir(self.records):
            return []
        out = []
        for name in sorted(os.listdir(self.records)):
            with io.open(os.path.join(self.records, name),
                         encoding="utf-8") as fh:
                out += [json.loads(l) for l in fh if l.strip()]
        return out


class AnOversizedBodyGetsAnAnswerAndNotABrokenPipe(_Serving):

    def body(self):
        blob = b'{"x":"' + b"z" * (wr.MAX_BODY * 3) + b'"}'
        self.assertGreater(len(blob), wr.MAX_BODY)
        return blob

    def test_the_sender_reads_the_refusal(self):
        """Witness 1, and the platform-dependent one: on Linux, before the
        drain, this is where EPIPE appeared instead of a status."""
        status, text = self.post(self.body(), signature="sha256=whatever")
        self.assertEqual(413, status)
        self.assertIn("over the", text)

    def test_the_refusal_says_what_the_limit_is(self):
        """A refusal a sender cannot act on produces a retry loop. The
        original four tests assert exactly this, and on the host there was no
        response to read it from."""
        _status, text = self.post(self.body(), signature="sha256=whatever")
        self.assertIn(str(wr.MAX_BODY), text)
        self.assertIn("Do not retry unchanged", text)

    def test_the_server_says_it_drained_before_answering(self):
        """Witness 2, platform-independent. The log line is written by the
        drain itself, so it cannot appear unless the drain ran."""
        self.post(self.body(), signature="sha256=whatever")
        self.assertIn("drained", self.log.getvalue())
        self.assertIn("recorded none", self.log.getvalue())

    def test_nothing_oversized_is_ever_recorded(self):
        """Witness 3. Draining is not accepting - the bytes are read to clear
        the socket and thrown away unparsed."""
        self.post(self.body(), signature="sha256=whatever")
        self.assertEqual([], self.recorded())

    def test_the_refusal_says_nothing_was_recorded(self):
        _status, text = self.post(self.body(), signature="sha256=whatever")
        self.assertIn("NOTHING WAS RECORDED", text)

    def test_the_drain_is_bounded(self):
        """An unbounded drain is a denial of service with a polite excuse."""
        self.assertLessEqual(wr.DRAIN_LIMIT, 8 * 1024 * 1024)
        self.assertGreater(wr.DRAIN_LIMIT, wr.MAX_BODY)


class ItRefusesAnythingItCannotVerify(_Serving):

    def test_a_correctly_signed_body_is_recorded(self):
        body = b'{"event":"reply","campaign":497}'
        status, text = self.post(body, signature=wr.sign(SECRET, body))
        self.assertEqual(200, status, text)
        rows = self.recorded()
        self.assertEqual(1, len(rows))
        self.assertEqual(body.decode(), rows[0]["body"])

    def test_an_unsigned_body_is_refused_and_not_recorded(self):
        status, text = self.post(b'{"event":"reply"}')
        self.assertEqual(401, status)
        self.assertIn("nothing recorded", text)
        self.assertEqual([], self.recorded())

    def test_a_wrong_signature_is_refused(self):
        body = b'{"event":"reply"}'
        status, _ = self.post(body, signature=wr.sign("the-wrong-secret", body))
        self.assertEqual(401, status)
        self.assertEqual([], self.recorded())

    def test_a_signature_for_a_different_body_is_refused(self):
        """The signature must cover THIS body, not merely be well-formed."""
        status, _ = self.post(b'{"event":"tampered"}',
                              signature=wr.sign(SECRET, b'{"event":"reply"}'))
        self.assertEqual(401, status)
        self.assertEqual([], self.recorded())

    def test_an_unknown_path_is_refused(self):
        status, _ = self.post(b"{}", signature="x", path="/not-the-webhook")
        self.assertEqual(404, status)
        self.assertEqual([], self.recorded())


class ItRecordsAndNeverActs(_Serving):

    def test_the_success_message_says_it_never_acts(self):
        body = b'{"event":"reply"}'
        _status, text = self.post(body, signature=wr.sign(SECRET, body))
        self.assertIn("never acts on a webhook", text)

    def test_the_body_is_stored_as_text_and_not_evaluated(self):
        """A webhook is a claim by a third party. It is evidence, not an
        instruction, and nothing in this build treats one as one."""
        body = b'{"event":"stop_campaign","campaign":497}'
        self.post(body, signature=wr.sign(SECRET, body))
        row = self.recorded()[0]
        self.assertIsInstance(row["body"], str)
        self.assertEqual(body.decode(), row["body"])

    def test_the_receiver_imports_nothing_from_src(self):
        """THE IMPORT GRAPH, not the source text.

        The first version of this test grepped the source for words like
        "queue" and "providers" - and failed on this module's own docstring,
        which says it never writes the queue. CLAUDE.md names that mistake
        directly: "Searching source for words produces a test that fails when
        somebody writes a comment, which has happened repeatedly here."

        What actually matters is that the receiver CANNOT reach the queue, a
        provider or a sender, whatever any comment says. So this reads the
        module's imports.
        """
        import ast
        path = os.path.join(ROOT, "scripts", "server", "webhook_receiver.py")
        with io.open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), path)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported.add(node.module.split(".")[0])
                elif node.level:
                    imported.add("<relative import>")
        self.assertNotIn("src", imported,
                         "the record-only receiver imports application code")
        self.assertNotIn("<relative import>", imported)
        # Everything it does import is the standard library.
        self.assertEqual(set(), imported - {
            "argparse", "datetime", "hashlib", "hmac", "io", "json", "os",
            "sys", "http"})

    def test_importing_it_pulls_in_no_application_module(self):
        """The same claim, checked a second way: loading the module must not
        put a single `src.*` module into sys.modules."""
        before = {m for m in sys.modules if m.startswith("src")}
        spec = importlib.util.spec_from_file_location(
            "webhook_receiver_isolated",
            os.path.join(ROOT, "scripts", "server", "webhook_receiver.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        after = {m for m in sys.modules if m.startswith("src")}
        self.assertEqual(before, after,
                         "loading the receiver imported application code")

    def test_healthz_answers_without_being_a_webhook_path(self):
        with urllib.request.urlopen(self.url("/healthz"), timeout=30) as r:
            self.assertEqual(200, r.status)
            self.assertIn("record-only", r.read().decode())


class TheCaddyfileRefusesWithoutAHostname(unittest.TestCase):
    """PUBLIC_HOSTNAME is a named, unfilled operator input.

    A guessed hostname is not a harmless placeholder: Caddy attempts an ACME
    issuance for it at startup - a real request to a real certificate
    authority for a name we do not control - and Let's Encrypt rate-limits
    failures for a week, per ACCOUNT.
    """

    SCRIPT = os.path.join(ROOT, "scripts", "server", "generate_caddyfile.py")

    def run_it(self, *args, hostname=None):
        import subprocess
        env = dict(os.environ)
        env.pop("PUBLIC_HOSTNAME", None)
        if hostname is not None:
            env["PUBLIC_HOSTNAME"] = hostname
        return subprocess.run([sys.executable, self.SCRIPT] + list(args),
                              cwd=ROOT, env=env, capture_output=True, text=True)

    def test_it_refuses_when_the_hostname_is_unset(self):
        proc = self.run_it()
        self.assertEqual(2, proc.returncode)
        self.assertIn("REFUSING", proc.stderr)
        self.assertIn("PUBLIC_HOSTNAME", proc.stderr)
        self.assertEqual("", proc.stdout)

    def test_the_refusal_says_why_a_guess_is_not_harmless(self):
        proc = self.run_it()
        self.assertIn("certificate authority", proc.stderr)
        self.assertIn("rate-limit", proc.stderr)

    def test_a_url_is_not_a_hostname(self):
        """A URL here produces a Caddyfile that parses and a site block that
        never matches, which looks like a networking problem."""
        proc = self.run_it(hostname="https://webhooks.example.com/")
        self.assertEqual(2, proc.returncode)
        self.assertIn("not a hostname", proc.stderr)

    def test_an_ip_address_is_not_a_hostname(self):
        proc = self.run_it(hostname="203.0.113.10")
        self.assertEqual(2, proc.returncode)

    def test_it_uses_tls_alpn_because_only_443_is_open(self):
        """provision.sh opens 22 and 443, default deny. HTTP-01 needs 80 and
        would fail as a certificate that never issues."""
        proc = self.run_it(hostname="webhooks.example.com")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("tls-alpn-01", proc.stdout)
        self.assertNotIn("http-01", proc.stdout)

    def test_only_the_webhook_path_is_proxied(self):
        proc = self.run_it(hostname="webhooks.example.com")
        self.assertIn("reverse_proxy 127.0.0.1:%d" % wr_port(), proc.stdout)
        self.assertEqual(1, proc.stdout.count("reverse_proxy"),
                         "more than one thing is exposed to the internet")

    def test_the_default_route_refuses_rather_than_404s(self):
        """A 404 confirms the host is serving and invites the next request."""
        proc = self.run_it(hostname="webhooks.example.com")
        self.assertIn("403", proc.stdout)


def wr_port():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gc", os.path.join(ROOT, "scripts", "server", "generate_caddyfile.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.RECEIVER_PORT


if __name__ == "__main__":
    unittest.main()
