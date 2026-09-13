"""Shared test setup: every test runs against a throwaway queue file.

Provider tests additionally run offline. ProviderTest replaces the transport
with a cassette player and booby-traps urlopen, so a test that would reach a
real API fails loudly instead of spending a credit.
"""
import json
import os
import shutil
import tempfile
import unittest
import urllib.request

from src import store

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CASSETTES = os.path.join(FIXTURES, "cassettes")

# What `tests/fixtures/cassettes/bison.json` answers `GET /users` with, and
# therefore which checkpoint slot a fixture poll of EmailBison reads and
# writes. Fictional on purpose: a fixture must exercise the identity read
# without stating a real client's workspace id.
FIXTURE_WORKSPACE = {"id": 99, "name": "Fixture Workspace"}
FIXTURE_SCOPE = "ws%d" % FIXTURE_WORKSPACE["id"]

KEY_VARS = ("CONTACTOUT_TOKEN", "BLITZ_API_KEY", "AIARK_KEY", "REOON_KEY", "DELIVERABLE_KEY",
            "BISON_KEY", "BISON_BASE", "HEYREACH_KEY", "APIFY_TOKEN")

# Variables that are CLEARED for the duration of a test rather than set to a
# placeholder. Two reasons to be in this list: a placeholder value would be
# read as configuration (Deliverable's contract), or as permission (Slack's
# signing secret and live switch, where a value means "trust this payload" and
# "post for real"). Clearing them also stops one test leaking them into the
# next, which is how two signing tests started passing alone and failing
# together.
CONTRACT_VARS = ("DELIVERABLE_BASE", "DELIVERABLE_VERIFY", "DELIVERABLE_STATUS",
                 "DELIVERABLE_AUTH", "DELIVERABLE_METHOD",
                 "DELIVERABLE_RESULT_SHAPE",
                 "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_LIVE",
                 "CHECKPOINTS", "OBSERVABILITY",
                 # A workspace pin is not a credential, and it belongs here for
                 # the same reason SLACK_LIVE does: it changes behaviour. Once
                 # `BISON_WORKSPACE_ID=10` was set in `config/.env`, any test
                 # that had already called `providers.load_env` - `configured()`
                 # does - left it in `os.environ` for the whole process, and
                 # twelve reply-watcher tests then failed because the poll
                 # correctly refused their fixture's workspace. They passed
                 # alone and failed in the suite, which is the signature.
                 "BISON_WORKSPACE_ID")


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-test-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        self._prev = {k: os.environ.get(k) for k in ("QUEUE", "OUT")}
        os.environ["QUEUE"] = self.queue
        os.environ["OUT"] = self.out
        self.assertEqual(store.queue_path(), os.path.abspath(self.queue))

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def use_fixture(self, name):
        """Copy a fixture queue into this test's throwaway queue file."""
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, name), self.queue)
        return store.load()

    def out_file(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as f:
            return f.read()

    def lines(self):
        if not os.path.exists(self.queue):
            return []
        with open(self.queue, encoding="utf-8") as f:
            return [l for l in f if l.strip()]

    def by_id(self):
        return {r["id"]: r for r in store.load()}

    def write_csv(self, name, lines):
        """Write a throwaway CSV in the temp dir and return its path."""
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                print(line, file=f)
        return path


class NoNetwork(AssertionError):
    """A test tried to reach the network. Nothing here may cost money."""


class Cassette:
    """Replays hand written provider fixtures. Never touches the network.

    Several cassettes may share a match: they play in order, and the last one
    repeats, which is how the async email_finder poll is exercised.
    """

    def __init__(self, *providers):
        """No arguments loads every cassette file, sorted, so a file named
        00-something.json can hold the specific matches that must win."""
        names = providers or [os.path.splitext(f)[0]
                              for f in sorted(os.listdir(CASSETTES))
                              if f.endswith(".json")]
        self.entries = []
        for name in names:
            with open(os.path.join(CASSETTES, f"{name}.json"), encoding="utf-8") as f:
                self.entries.extend(json.load(f))
        self.calls = []
        self._played = {}

    def matches(self, entry, method, url, body):
        m = entry.get("match", {})
        text = json.dumps(body) if body is not None else ""
        if m.get("method") and m["method"] != method:
            return False
        if m.get("url_contains") and m["url_contains"] not in url:
            return False
        if m.get("body_contains") and m["body_contains"] not in text:
            return False
        if m.get("not_body_contains") and m["not_body_contains"] in text:
            return False
        return True

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": dict(headers),
                           "body": body})
        found = [e for e in self.entries if self.matches(e, method, url, body)]
        if not found:
            raise NoNetwork(f"no cassette for {method} {url}")
        key = id(found[0])
        i = min(self._played.get(key, 0), len(found) - 1)
        self._played[key] = i + 1
        entry = found[i]
        return entry["status"], json.dumps(entry["response"])

    def urls(self):
        return [c["url"] for c in self.calls]


class ProviderTest(unittest.TestCase):
    def setUp(self):
        from src import providers
        from src.providers import aiark

        # The throwaway queue this module's docstring promises. It was
        # promised and not delivered: `ProviderTest` isolated the network and
        # the credentials and left the store pointing wherever it already
        # pointed, so a subclass that called `store.save` wrote into the real
        # `work/` - and `store.save` replaces the row set it is given, so the
        # write was not an append but a replacement.
        #
        # `tests/test_signals.py::TheEstateWalksReadTheSignalFileOnce` did
        # exactly that: it built twenty-five `walk-N` fixtures and saved them,
        # which is how a real client estate was replaced by test companies
        # called "Co 0". Every sibling in that file was safe - `SignalTest`
        # inherits `CampaignTest`'s isolation and `EntryTest` sets up its own -
        # so the omission was invisible beside working examples.
        #
        # It belongs here rather than in the one class that tripped over it:
        # forty-two classes inherit from this one, and isolation a subclass
        # has to remember is isolation a subclass can forget.
        #
        # Every restore below is registered with `addCleanup` where the state
        # is captured, rather than deferred to `tearDown`. `unittest` does not
        # call `tearDown` when a `setUp` raises, and forty-two classes extend
        # this one: a subclass `setUp` that failed after `super().setUp()`
        # left the tripwire installed for the rest of the process. It was
        # self-perpetuating too - the next `ProviderTest` captured
        # `_forbidden` as "the original" and restored that. One failing
        # fixture therefore broke every later test that opens a URL:
        # `tests/test_slack_route.py` posts with `urllib.request.urlopen` and
        # `src/web/oidc.py` fetches discovery and token with it, which is 63
        # failures from one error. `addCleanup` unwinds whatever was reached.
        self._store_tmp = tempfile.mkdtemp(prefix="rga-provider-")
        self.addCleanup(shutil.rmtree, self._store_tmp, ignore_errors=True)
        self._store_env = {k: os.environ.get(k)
                           for k in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(self._restore_env, self._store_env)
        store.use_directory(os.path.join(self._store_tmp, "work"))

        self.providers = providers
        self.cassette = Cassette()
        providers.set_transport(self.cassette)
        self.addCleanup(providers.reset_transport)
        aiark.reset_validated()      # the enum cache must not leak between tests

        # No key may reach a provider from the developer's own environment.
        self._keys = {k: os.environ.pop(k, None) for k in KEY_VARS + CONTRACT_VARS}
        self.addCleanup(self._restore_env, self._keys)
        for k in KEY_VARS:
            os.environ[k] = "test-key-not-real"

        # Tripwire: anything bypassing the transport seam dies here.
        self._urlopen = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", self._urlopen)
        urllib.request.urlopen = self._forbidden

        # config/.env must not be read into the test environment either.
        self._env_file = providers.ENV_FILE
        self.addCleanup(setattr, providers, "ENV_FILE", self._env_file)
        providers.ENV_FILE = os.path.join(FIXTURES, "no-such.env")

    @staticmethod
    def _restore_env(saved):
        """Put back exactly what was there, absence included."""
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    @staticmethod
    def _forbidden(*a, **kw):
        raise NoNetwork("a test attempted a real HTTP request")

    def clear_keys(self):
        for k in KEY_VARS + CONTRACT_VARS:
            os.environ.pop(k, None)

    def confirm_deliverable_contract(self):
        """Pretend one real answer has been read. Tests only.

        The endpoints and auth come from the provider's documentation and are
        already the adapter's defaults; only the response shape has to be
        vouched for here.
        """
        from src.providers import deliverable
        return deliverable.configure(result_shape="confirmed")


def qualify_everything(status=None):
    """Give every queued record an explicit ICP verdict. Tests only.

    Person-level enrichment is gated on one: CLAUDE.md is that "rejected,
    review and unknown all mean zero person credits", and `enrich.spend`
    enforces it. So a test whose subject is the *provider waterfall* - which
    call runs first, what a fallback costs, how a collision is excluded - has
    to say that its companies were qualified, exactly as a test about payloads
    has to call `approve_everything` first. Without it those tests would be
    asserting the gate's behaviour by accident instead of their own.

    Written as an explicit verdict rather than scored, deliberately. Scoring
    these fixtures for real reaches `review` at best: no client config carries
    an `icp` block, and the default thresholds want more dimensions than free
    enrichment produces. Making the fixtures score `qualified` would mean
    tuning either the fixtures or the thresholds until they did, which would
    quietly turn every waterfall test into a test of the ICP model.

    This helper is not a way to make a red test green. `tests/
    test_icp_spend_gate.py` holds the other side: that an unqualified,
    rejected, review or unknown company buys no person credit at all.
    """
    from src import icp, qualify, store

    status = status or icp.QUALIFIED
    with store.transaction() as recs:
        for rec in recs:
            existing = rec.get("qualification") or {}
            rec["qualification"] = dict(
                existing,
                inputs_fingerprint=qualify._inputs_fingerprint(rec),
                at=store.now(),
                verdict=dict(existing.get("verdict") or {},
                             icp_status=status))
    return len(recs)


def approve_everything(by="test-operator", config=None):
    """Approve every currently approvable step in the queue.

    Approval is a human act, so tests that are about eligibility, payloads or
    the pause have to grant it explicitly, exactly as an operator would.

    `config` is the one the caller is TESTING against. Without it this loads
    the client's real file, and approval is per STEP KEY - so a test running
    one cadence while this approved another left every step unapproved. That
    is what happened when Productive moved to `productive_li_heavy_v1`: the
    timelines under test used `day1`/`day3` and the approvals landed on
    `em1`/`li1`, and the failure read `'unapproved' != 'eligible'`, which
    names the symptom and hides the cause.
    """
    from src import approve, clients, store
    with store.transaction() as recs:
        results = []
        for rec in recs:
            settings = config
            if settings is None:
                try:
                    settings = clients.load(rec.get("client"))
                except clients.ConfigError:
                    continue
            results.append(approve.approve_record(rec, by=by, config=settings))
    return results
