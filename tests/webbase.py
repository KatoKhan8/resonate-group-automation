"""Shared setup for the web tests: a whole demo estate, served over real HTTP.

These tests do not call handler methods directly. They start the actual
`ThreadingHTTPServer` on an ephemeral port and talk to it with `urllib`,
because most of what is worth asserting about a web layer lives in the parts a
direct call skips: the session cookie, the CSRF check, the status code, the
headers, and the fact that a refusal is a refusal rather than an exception the
test helpfully caught.

Everything is thrown away per class: its own queue, campaign file, job file,
workspace table, audit log, MX cache and - importantly - its own directory of
client configs. A web test must not be able to read, shadow or write a real
client file, and pointing `CLIENTS_DIR` somewhere disposable is how that is
guaranteed rather than promised.

Nothing here reaches the network. The demo estate is built by the real engine
from fictional input, and the only socket in play is a loopback listener this
process owns.
"""
import http.cookiejar
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

from src import store

ENV = ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT", "MX_CACHE", "OUT",
       "CLIENTS_DIR", "SLACK_BOT_TOKEN", "SLACK_LIVE", "WEB_QUIET",
       "NOTIFICATIONS", "SENDERS", "REPORTS", "SLACK_OPS_CHANNEL")


class Session:
    """One signed-in browser. Holds its cookie and its CSRF token."""

    def __init__(self, base, email=None):
        self.base = base
        self.email = email
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, path):
        try:
            with self.opener.open(self.base + path, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(
                    r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return (e.code, e.read().decode("utf-8", "replace"),
                        dict(e.headers))

    def post(self, path, fields, follow=True):
        # `doseq=True` so a list value submits as a repeated field, which is
        # what a browser sends for a checkbox group and what the report
        # section controls rely on.
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        try:
            with self.opener.open(self.base + path, data, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(
                    r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return (e.code, e.read().decode("utf-8", "replace"),
                        dict(e.headers))

    def get_bytes(self, path):
        """A binary response, undecoded. PDFs, CSVs, anything not HTML.

        `get` decodes UTF-8, which silently corrupts every byte above 0x7F -
        so a test asserting on a PDF through `get` is asserting on mojibake
        and passes or fails for reasons unrelated to the document.
        """
        try:
            with self.opener.open(self.base + path, timeout=30) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read(), dict(e.headers)

    def post_bytes(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        try:
            with self.opener.open(self.base + path, data, timeout=30) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read(), dict(e.headers)

    def csrf(self, path="/"):
        """The token this session's pages actually carry."""
        import re
        _, body, _ = self.get(path)
        found = re.search(r'name="csrf" value="([^"]+)"', body)
        return found.group(1) if found else None


class WebTest(unittest.TestCase):
    """A demo estate and a live server, built once per class."""

    @classmethod
    def setUpClass(cls):
        cls._prev = {k: os.environ.get(k) for k in ENV}
        cls.tmp = tempfile.mkdtemp(prefix="rga-web-")
        # One call, because `store` is the only module that knows what the
        # state files are called.
        store.use_directory(os.path.join(cls.tmp, "work"))
        os.environ["MX_CACHE"] = os.path.join(cls.tmp, "mx-cache.json")
        os.environ["OUT"] = os.path.join(cls.tmp, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(cls.tmp, "clients")
        # A request log per assertion buries the failure that matters.
        os.environ["WEB_QUIET"] = "1"
        # Slack must not be able to post from a test even by accident.
        os.environ.pop("SLACK_BOT_TOKEN", None)
        os.environ.pop("SLACK_LIVE", None)

        from src.web import app, demodata
        cls.app = app
        cls.demodata = demodata
        demodata.install()

        cls.server = app.serve(0, demo=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        for key, value in cls._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------ helpers

    def signin(self, email):
        session = Session(self.base, email)
        status, body, _ = session.post("/login", {"email": email})
        self.assertEqual(status, 200, f"sign-in failed for {email}: {body[:200]}")
        return session

    def anonymous(self):
        return Session(self.base)

    def switch(self, session, workspace):
        return session.post("/select-workspace",
                            {"csrf": session.csrf(), "workspace": workspace})

    def records_of(self, client):
        from src import store
        return [r for r in store.load() if r.get("client") == client]

    def a_record(self, client):
        rows = self.records_of(client)
        self.assertTrue(rows, f"no demo records for {client}")
        return rows[0]
