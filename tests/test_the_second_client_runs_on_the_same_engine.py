"""The multi-client acceptance test PRODUCT-GOAL.md asks for, written early.

PRODUCT-GOAL.md names the canonical proof: "Client A = Productive, Client B =
a synthetic isolated client, with different ICPs, domains, contacts, provider
bindings, sender pools, suppressions, budgets and campaign intents - processed
through the same engine, proving zero cross-client contacts, evidence, sender
use, campaigns, provider access, suppression, collision contamination (unless
a policy makes it explicitly global), replies, spend, approvals and actions.
And proving that pausing or failing Client B does not stop unrelated safe work
for Productive."

This file is that proof, and it is written BEFORE the second client exists on
purpose: the point of an acceptance test is to say what onboarding one would
cost, not to certify it afterwards. Two clients are built in a throwaway
estate, run through the same functions with nothing but their configuration
differing, and every isolation axis is asserted one at a time.

## How to read it

Every test's docstring opens with one word:

  HOLDS   - the boundary is enforced today, and the docstring names the guard.
  LEAKS   - it is not, and the test asserts the leak so that fixing it turns
            this file red. A characterisation test is the only kind that
            fails on the day somebody closes the hole.
  ABSENT  - the thing that would have to hold the boundary does not exist at
            all. Written as `expectedFailure` with the missing piece named.

`ABSENT` is the highest-value output here and nothing below papers over one.
There is no canonical provider binding in this repository: a credential is a
process-global environment variable, the campaign row carries no binding, and
`workspace` names both the Resonate client slug and the vendor estate id -
inside one parameter list, in `executionguard.authorize`. Those are written as
`expectedFailure`, not skipped, so that the day a binding lands they turn green
and announce themselves.

## Why it does not touch anything real

`store.use_directory` moves the queue, campaigns, workspaces, audit log,
senders, action ledger, spend ledger and the agency DNC index together;
`CLIENTS_DIR` moves the client configs. Every assertion below is against a
temporary directory and the first thing `setUp` does is prove it. Nothing here
performs a provider call: the transports are never wired, and the two places a
gate would reach one are mocked with the mock itself asserted on.

Client A carries the slug `productive` because the engine has one remaining
hard-coded default that names it (`senderinventory.main`), and a test that
renamed it would not find that. Its config is a copy of the real file into the
temporary directory; Client B's is the same file with a different market, a
different geography and a budget. Every prospect, company, domain and person
below is invented and `.test`.
"""
import datetime
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

from src import (actionledger, agencydnc, approval, cadence, campaigns,
                 clients, collision, configdiff, eligibility, events,
                 executionguard, hygiene, ingest, killswitch)
from src import repo as repo_module
from src import senderidentity as si
from src import senderinventory, spendledger, store
from src import workspaces as ws

A = "productive"                 # client #1, per PRODUCT-GOAL.md
B = "clientb"                    # the synthetic second client

A_OPS = "ops@a.test"
B_OPS = "ops@b.test"

# The two vendor estates. Numbers, because EmailBison's are: the binding is
# chosen in the vendor UI and has moved mid-session, which is the whole reason
# `bison.require_workspace` exists.
A_ESTATE = 10
B_ESTATE = 29

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
FRESH = (NOW - datetime.timedelta(minutes=1)).isoformat()

REAL_CONFIG = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "config", "clients", "productive.yaml")


def _without_providers(raw):
    """`raw` with any top-level `providers:` block removed.

    THE FIXTURE ASSUMED WHAT THE REAL FILE CONTAINS, AND THE REAL FILE
    CHANGED. Both client fixtures below append their own binding, written
    when `config/clients/productive.yaml` carried none. It carries one now,
    and the two consequences point opposite ways: `clients.parse` lets a
    second top-level key replace the first (src/clients.py:111), so the
    APPENDED binding won and every test asserting a binding kept passing -
    while `test_an_unbound_client_is_held_rather_than_defaulted`, which needs
    a client with NO binding, silently got the real file's and asserted that
    a bound client is refused.

    So subtract it, rather than depending on what that file happens to say
    today. Line-based because `clients.parse` is a hand-written YAML subset
    and there is no parser here to round-trip through.
    """
    out, dropping = [], False
    for line in raw.splitlines(keepends=True):
        body, indent = line.strip(), len(line) - len(line.lstrip(" "))
        if dropping:
            if not body or indent > 0:
                continue                  # still inside the block
            dropping = False
        if indent == 0 and body.startswith("providers:"):
            dropping = True
            continue
        out.append(line)
    return "".join(out)


def _client_b_config(raw):
    """Client A's config, made into a genuinely different client.

    A different market sentence, a different size floor, a different
    geography and a declared budget - which is what "a different ICP" means
    in this system, because `icp.score` reads `icp.markets` and
    `personas.icp_flags` reads `market`.
    """
    text = raw
    text = text.replace("name: Productive", "name: Client B")
    text = text.replace("productive.test", "clientb.test")
    text = re.sub(r"^  must: .*$", "  must: a discrete manufacturer",
                  text, flags=re.M)
    text = re.sub(r"^  size_min_employees: .*$", "  size_min_employees: 200",
                  text, flags=re.M)
    # Both list-of-country keys, so the flagger and the scorer agree.
    text = re.sub(r"^  geos: \[[^\]]*\]", "  geos: [Germany]",
                  text, flags=re.M | re.S)
    text = re.sub(r"^  markets: \[[^\]]*\]", "  markets: [Germany]",
                  text, flags=re.M | re.S)
    return (_without_providers(text)
            + "\nbudget:\n  per_day: 5\n  total: 5\n"
            + f"providers:\n  emailbison:\n    workspace: {B_ESTATE}\n")


def _client_a_config(raw):
    """Client A's config plus its own provider binding.

    `clients.provider_workspace` is the canonical binding, and this fixture
    states Client A's own rather than inheriting whichever estate the real
    `config/clients/productive.yaml` happens to name. That is the correct
    place for it - one row per (client, provider), in the client's own
    configuration - and the report names the remaining callers that still
    take an estate from an argument instead. `_without_providers` runs first,
    so the file carries one binding and not two.
    """
    return (_without_providers(raw)
            + f"\nproviders:\n  emailbison:\n    workspace: {A_ESTATE}\n")


class _NoProviderCall(AssertionError):
    """This file attempted a network call. Nothing here may reach a provider."""


def cli_arguments(module):
    """Every `add_argument` a module's `main` declares, without running it.

    The parser is built during `main`, so the arguments cannot be read
    without entering it - and entering it is how an earlier version of this
    test hung: a mocked `ArgumentParser` returned a `MagicMock` namespace and
    `senderinventory.main` went straight on to read a live EmailBison estate.
    So `parse_args` raises instead. By then the parser is fully constructed
    and nothing past it has run.

    THE METHODS ARE PATCHED, NEVER THE NAME, AND THAT DISTINCTION TOOK THE
    MACHINE DOWN. Replacing `argparse.ArgumentParser` with a subclass of it -
    the obvious way to write this, and what stood here - recurses for ever.
    `ArgumentParser.__init__` reaches its base through
    `super(ArgumentParser, self)` (Lib/argparse.py:1880), reading
    `ArgumentParser` from the argparse module globals, which is the name the
    patch just rebound to the subclass. So `super(subclass, self)` resolves to
    the real `ArgumentParser.__init__`, which evaluates the same expression
    again. On 3.14 a Python frame is heap-allocated and no RecursionError
    arrives to stop it: measured 2026-09-12, one call reached 9.8GB of RSS on
    a 31GB machine in under a minute and took the whole session with it.

    Patching `add_argument`, `parse_args` and `parse_known_args` on the class
    leaves the name alone, so `super(ArgumentParser, self)` still means what
    argparse wrote it to mean. `-h` is recorded too, because `__init__` adds
    it through the same method; no caller here cares.
    """
    import argparse
    seen = {}
    add = argparse.ArgumentParser.add_argument

    def add_argument(self, *a, **kw):
        if a and str(a[0]).startswith("-"):
            seen[a[0]] = kw
        return add(self, *a, **kw)

    def stop(self, *a, **kw):
        raise SystemExit("cli_arguments: parser built, stopping here")

    with mock.patch.object(argparse.ArgumentParser, "add_argument",
                           add_argument), \
            mock.patch.object(argparse.ArgumentParser, "parse_args", stop), \
            mock.patch.object(argparse.ArgumentParser, "parse_known_args",
                              stop):
        try:
            module.main([])
        except SystemExit:
            pass
    return seen


class _both:
    """Enter several patchers as one context manager, yielding their mocks."""

    def __init__(self, *patchers):
        self.patchers = patchers

    def __enter__(self):
        self.mocks = [p.start() for p in self.patchers]
        return self.mocks[0] if len(self.mocks) == 1 else tuple(self.mocks)

    def __exit__(self, *exc):
        for p in reversed(self.patchers):
            p.stop()
        return False


def a_record(rid, client, company, domain, contact_key, email, linkedin):
    """One verified, researched record. `store.validate` accepts it."""
    return {
        "id": rid, "lane": "domains", "client": client, "company": company,
        "domain": domain, "state": "verified", "drop_reason": None,
        "log": [], "events": [],
        "company_facts": {"industry": "Design Services",
                          "research_outcome": "HTTP_SUCCESS"},
        "contacts": [{
            "key": contact_key, "name": "Pat Person",
            "title": "Head of Production", "email": email,
            "linkedin": linkedin, "persona": "champion",
            "angle": "operations", "selected": True, "verified": True,
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid", "email": email,
                 "catch_all": False, "disposable": False,
                 "at": NOW.isoformat()},
                {"provider": "reoon", "status": "valid", "email": email,
                 "catch_all": False, "disposable": False,
                 "safe_to_send": True, "at": NOW.isoformat()}]},
            "mx": {"status": "known_allowed", "email_eligible": True},
        }],
    }


class Estate(unittest.TestCase):
    """Two clients, one engine, one throwaway directory.

    Everything that differs between them differs in CONFIGURATION, which is
    the line PRODUCT-GOAL.md draws: client-specific configuration is correct,
    client-specific engine logic is a defect.
    """

    maxDiff = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-two-clients-")
        self._prev = {k: os.environ.get(k) for k in
                      ("QUEUE", "OUT", "CLIENTS_DIR", "BISON_WORKSPACE_ID",
                       "BISON_KEY", "HEYREACH_KEY") + store.STATE_OVERRIDES}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.makedirs(os.environ["CLIENTS_DIR"], exist_ok=True)
        # A stale pin from `config/.env` would make every binding assertion
        # below answer for whatever the developer last ran.
        os.environ.pop("BISON_WORKSPACE_ID", None)
        # The one assertion that makes every other one meaningful.
        self.assertTrue(
            store.queue_path().startswith(os.path.abspath(self.tmp)))
        self.assertTrue(
            spendledger.path().startswith(os.path.abspath(self.tmp)))
        self.assertTrue(
            actionledger.path().startswith(os.path.abspath(self.tmp)))

        # NOTHING HERE MAY REACH A PROVIDER. Two of the gates below would,
        # and they are mocked - but a mock somebody deletes is a mock that
        # stops protecting anything, and the failure mode is a real HTTP
        # request to a real estate rather than a red test. So the transport
        # itself is booby-trapped for the duration.
        import urllib.request
        from src import providers as providers_mod
        real_urlopen = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", real_urlopen)
        urllib.request.urlopen = self._no_network
        providers_mod.set_transport(self._no_network)
        self.addCleanup(providers_mod.reset_transport)

        with open(REAL_CONFIG, encoding="utf-8") as f:
            raw = f.read()
        # Pinned: these tests are about multi-client isolation, not about
        # which cadence Productive currently runs. The fixtures use day1..day21
        # step keys, so the config must match.
        raw = raw.replace("productive_li_heavy_v1", "productive_balanced_v1")
        self.raw_config = raw
        self._write_config(A, _client_a_config(raw))
        self._write_config(B, _client_b_config(raw))

        ws.ensure(A, "Client A", A)
        ws.ensure(B, "Client B", B)
        ws.add_user(A_OPS, "A Ops")
        ws.add_user(B_OPS, "B Ops")
        ws.assign(A_OPS, A, ws.WORKSPACE_ADMIN)
        ws.assign(B_OPS, B, ws.WORKSPACE_ADMIN)

        store.append([
            a_record("a-1", A, "Northgate", "northgate.test",
                     "avery-nolan", "avery@northgate.test", "avery-nolan"),
            a_record("b-1", B, "Westmill", "westmill.test",
                     "robin-vale", "robin@westmill.test", "robin-vale"),
        ])

        # Separate sender pools. Both carry provider account id `p-100`
        # deliberately: a vendor's id space offers no cross-tenant
        # uniqueness, so resolving one globally would be a walk from a
        # provider id into another client's roster.
        si.install([
            si.new_sender(A, "ansel", "Ansel A"),
            si.new_email_account(A, "ansel-01", "ansel", "ansel@a.test",
                                 provider_account_id="p-100", active=True,
                                 health="ok"),
            si.new_linkedin_account(A, "a-li", "ansel",
                                    "https://www.linkedin.com/in/ansel-a",
                                    provider="heyreach",
                                    provider_account_id="700",
                                    active=True, daily_limit=40, health="ok"),
            si.new_sender(B, "bergen", "Bergen B"),
            si.new_email_account(B, "bergen-01", "bergen", "bergen@b.test",
                                 provider_account_id="p-100", active=True,
                                 health="ok"),
            si.new_linkedin_account(B, "b-li", "bergen",
                                    "https://www.linkedin.com/in/bergen-b",
                                    provider="heyreach",
                                    provider_account_id="800",
                                    active=True, daily_limit=40, health="ok"),
        ])

        self.campaign_a = self._campaign(A, "a-camp", "a-1", 700, 900001)
        self.campaign_b = self._campaign(B, "b-camp", "b-1", 800, 900002)

        self.repo_a = repo_module.Repo.for_user(A_OPS, A)
        self.repo_b = repo_module.Repo.for_user(B_OPS, B)
        self.config_a = self.repo_a.config()
        self.config_b = self.repo_b.config()

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _no_network(*a, **kw):
        raise _NoProviderCall(
            "a test in this file attempted a provider call. Every gate that "
            "would read an estate is mocked; if this fires, one of the mocks "
            "is gone and the test was about to answer for a real client.")

    def _write_config(self, slug, text):
        with open(os.path.join(os.environ["CLIENTS_DIR"], f"{slug}.yaml"),
                  "w", encoding="utf-8") as f:
            f.write(text)

    def _campaign(self, client, campaign_id, record_id, seat, provider_id):
        row = campaigns.new_campaign(campaign_id, client,
                                     f"{client} - canary",
                                     created_by="operator")
        row.update({
            "heyreach_campaign_id": provider_id,
            "heyreach_list_id": provider_id + 1,
            "org_unit": 118000 + seat,
            "record_ids": [record_id],
            "senders": {"email": [],
                        "linkedin": [{"id": seat, "daily_limit": 1}]},
            "daily_volume": {"email": 0, "linkedin": 1},
            "provider_delays": [["HOUR", 0]],
            "provider_status_expected": "PAUSED",
        })
        campaigns.save(campaigns.load() + [row])
        return row

    def rec(self, record_id):
        return store.get(record_id)

    def approved(self, client, record_id, campaign):
        """A record and campaign carrying the approvals a send requires.

        Both are real approvals written through the canonical fields, not
        stubs: the step fingerprint and the campaign fingerprint are what
        `executionguard` re-derives, so a fixture that faked them would make
        the gates pass for the wrong reason.
        """
        config = clients.load(client)
        rec = store.get(record_id)
        contact = rec["contacts"][0]
        step = cadence.expand_step(
            rec, contact, executionguard._spec_for("day3"), config)
        self.assertTrue(step, "the fixture does not render a day3 step")
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == record_id:
                    row.setdefault("cadence", {}).setdefault(
                        contact["key"], {})["day3"] = dict(
                            step,
                            approval={"by": "operator", "at": store.now(),
                                      "fingerprint":
                                          approval.fingerprint(step)})
        rec = store.get(record_id)
        fingerprint = campaigns.fingerprint(campaign, store.load(), config)
        campaign["approval"] = {"action": "approve", "by": "operator",
                                "at": store.now(), "fingerprint": fingerprint}
        campaign["fingerprint"] = fingerprint
        campaign["status"] = campaigns.APPROVED
        return rec, rec["contacts"][0], campaign, config

    def readback(self, campaign, verdict=configdiff.PASS):
        return configdiff.Readback(
            diff={"verdict": verdict, "failures": []}, approved={},
            provider={}, campaign_id=campaign["campaign_id"],
            channel="linkedin",
            provider_campaign_id=campaign["heyreach_campaign_id"],
            verified_at=FRESH)

    def authorize(self, client, record_id, campaign, **over):
        rec, contact, campaign, config = self.approved(client, record_id,
                                                       campaign)
        kw = dict(operation="linkedin_connection_request", channel="linkedin",
                  campaign=campaign, rec=rec, contact=contact,
                  step_key="day3", workspace=A_ESTATE, config=config,
                  now=NOW, readback=self.readback(campaign))
        kw.update(over)
        return executionguard.authorize(**kw)

    def allow_collision(self):
        """Neutralise the gates that would otherwise reach a provider.

        Two of them: the person-level LinkedIn read and the account-level
        EmailBison read. Both are mocked, and both are asserted on rather
        than merely installed - `expect_workspace` on each is the tenant the
        gate believes it is asking about, and the tests below check it.
        """
        return _both(
            mock.patch.object(collision, "check_linkedin_profile",
                              return_value=(collision.CLEAR, {})),
            mock.patch.object(collision, "check_account", return_value={}),
            mock.patch.object(collision, "account_policy",
                              return_value=(collision.ALLOW, "no history")))

    def allow_killswitch(self):
        return mock.patch.object(killswitch, "require", return_value=True)

    def refused_at(self, gate, client, record_id, campaign, **over):
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(client, record_id, campaign, **over)
        self.assertEqual(
            caught.exception.gate, gate,
            f"expected gate {gate!r}, got {caught.exception.gate!r}: "
            f"{caught.exception.why}")
        return caught.exception


# ===================================================================== 1 ===

class TheEngineRunsBothClients(Estate):
    """Same code, different configuration. That is the whole requirement."""

    def test_the_two_clients_differ_only_in_configuration(self):
        """HOLDS - one loader, `clients.load`, two answers."""
        self.assertEqual(self.config_a["market"]["size_min_employees"], 20)
        self.assertEqual(self.config_b["market"]["size_min_employees"], 200)
        self.assertEqual(self.config_b["icp"]["markets"], ["Germany"])
        self.assertNotEqual(self.config_a["icp"]["markets"],
                            self.config_b["icp"]["markets"])
        # Client B's declared ceiling is B's, whatever A happens to declare.
        # This asserted `caps(config_a)["total"] is None`, which was only ever
        # true because the real `config/clients/productive.yaml` declared no
        # budget - the same coupling to that file's current contents that
        # `_without_providers` exists for, and it broke the day Productive got
        # a runaway guard. What the requirement actually says is that the two
        # clients differ, and that each gets its own answer from one loader.
        self.assertEqual(spendledger.caps(self.config_b)["total"], 5)
        self.assertNotEqual(spendledger.caps(self.config_a)["total"],
                            spendledger.caps(self.config_b)["total"])

    def test_one_engine_call_answers_for_whichever_client_it_was_given(self):
        """HOLDS - `cadence.expand_step` is passed a config, not a slug.

        The same function, the same step spec, two clients: the rendered copy
        differs because the configs do, and nothing in the call names either
        client.
        """
        rendered = {}
        for client, record_id in ((A, "a-1"), (B, "b-1")):
            rec = store.get(record_id)
            rendered[client] = cadence.expand_step(
                rec, rec["contacts"][0], executionguard._spec_for("day3"),
                clients.load(client))
        self.assertTrue(rendered[A] and rendered[B])
        self.assertNotEqual(rendered[A], rendered[B])

    def test_LEAK_one_engine_module_still_defaults_to_client_one(self):
        """LEAKS - src/senderinventory.py:411 `--workspace` default.

        Every other CLI in `src/` either requires the client or leaves it
        `None`. This one defaults it to the string `productive`, which means
        `python -m src.senderinventory --live` with no arguments rebuilds
        Productive's canonical sender roster from whatever estate the
        credential currently happens to be bound to. That is a client-specific
        value in engine logic, which PRODUCT-GOAL.md calls a defect by name.

        Asserted on the parser rather than on the source text: a test that
        grepped for the word would go green when somebody wrote a comment.
        """
        seen = cli_arguments(senderinventory)
        self.assertIn("--workspace", seen)
        self.assertEqual(seen["--workspace"].get("default"), "productive",
                         "the default is gone - delete this test and the "
                         "entry it holds in the report")


# ===================================================================== 2 ===

class ContactsAndEvidenceDoNotCross(Estate):
    """Records, their contacts, and the evidence hanging off them."""

    def test_neither_client_can_read_the_others_contacts(self):
        """HOLDS - `Repo._mine` / `_guard`, src/repo.py:193-202."""
        self.assertEqual([r["id"] for r in self.repo_a.records()], ["a-1"])
        self.assertEqual([r["id"] for r in self.repo_b.records()], ["b-1"])
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.record("b-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_b.contact("a-1", "avery-nolan")

    def test_evidence_is_unreachable_because_the_record_that_holds_it_is(self):
        """HOLDS, structurally - evidence has no store of its own.

        `src/evidence.py` mints ids from `(record_id, source_url, fact)` and
        the items live on the record, so evidence isolation IS record
        isolation and there is no second boundary to get wrong. This is the
        design the goal document asks for - one canonical home - and the test
        exists to keep it that way: the day evidence gets its own file, this
        assertion is the one that has to be rewritten.
        """
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "b-1":
                    row["evidence"] = [{"id": "e1", "fact": "b only"}]
        self.assertEqual(self.repo_b.record("b-1")["evidence"][0]["id"], "e1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.record("b-1")
        self.assertEqual(
            [r.get("evidence") for r in self.repo_a.records()], [None])

    def test_a_write_that_smuggles_a_foreign_row_is_refused_whole(self):
        """HOLDS - src/repo.py:263-267 checks every element of the batch."""
        mine = self.repo_a.record("a-1")
        theirs = store.get("b-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.save_records([mine, theirs])
        self.assertEqual(len(store.load()), 2)


# ===================================================================== 3 ===

class SenderPoolsDoNotCross(Estate):
    """A client's sender must never send for another."""

    def test_the_roster_is_scoped_and_a_shared_provider_id_does_not_cross(self):
        """HOLDS - `senderidentity._rows` has no unscoped variant."""
        self.assertEqual([s["sender_id"] for s in si.senders(A)], ["ansel"])
        self.assertEqual([s["sender_id"] for s in si.senders(B)], ["bergen"])
        with self.assertRaises(si.CrossWorkspaceSender):
            si.sender(A, "bergen")
        self.assertEqual(
            si.by_provider_account(A, si.EMAIL, "p-100")["account_id"],
            "ansel-01")
        self.assertEqual(
            si.by_provider_account(B, si.EMAIL, "p-100")["account_id"],
            "bergen-01")

    def test_ATTACK_client_a_record_with_client_b_seat_is_refused(self):
        """HOLDS - executionguard's sender gate, src/executionguard.py:396-404.

        The campaign is Client A's, the record is Client A's, and the seat
        named on the campaign belongs to Client B's roster. Nothing about the
        provider would object: HeyReach holds seat 800 and would accept the
        request. The refusal comes from canonical state saying the seat is not
        this client's.
        """
        self.campaign_a["senders"] = {"email": [],
                                      "linkedin": [{"id": 800,
                                                    "daily_limit": 1}]}
        why = self.refused_at("sender", A, "a-1", self.campaign_a)
        self.assertIn("800", why.why)
        self.assertIn(A, why.why)
        # And the gates that ran before it did pass, so this is the sender
        # boundary refusing rather than an earlier accident.
        self.assertIn("collision", why.passed)

    def test_ATTACK_rebuilding_a_roster_does_not_touch_the_other_client(self):
        """HOLDS - `senderinventory.replace` filters on workspace.

        The dangerous half of this is in `ProviderIdentityIsNotClientIdentity`
        below: `replace` is correctly scoped, and what it is asked to install
        is not.
        """
        rebuilt = [si.new_email_account(A, "ansel-02", "ansel", "a2@a.test",
                                        provider="emailbison",
                                        provider_account_id="p-101")]
        removed = senderinventory.replace(A, rebuilt)
        self.assertEqual(removed, 1, "A's own emailbison row was swapped out")
        self.assertEqual(
            sorted(r["account_id"] for r in si.email_accounts(A)),
            ["ansel-02"])
        # The whole point: B's roster is untouched by A's rebuild.
        self.assertEqual(
            sorted(r["account_id"] for r in si.email_accounts(B)),
            ["bergen-01"])


# ===================================================================== 4 ===

class CampaignsDoNotCross(Estate):
    """A campaign from one client reconciled against another's."""

    def test_a_foreign_campaign_readback_raises_rather_than_returning_none(self):
        """HOLDS - src/repo.py:243-248."""
        self.assertEqual([c["campaign_id"] for c in self.repo_a.campaigns()],
                         ["a-camp"])
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.campaign("b-camp")
        self.assertIsNone(self.repo_a.campaign("no-such-campaign"))

    def test_a_campaign_may_not_claim_the_other_clients_records(self):
        """HOLDS - src/repo.py:314-320 checks the record ids, not just the row."""
        stolen = dict(self.campaign_a, record_ids=["a-1", "b-1"])
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.save_campaign(stolen)
        self.assertEqual(campaigns.get("a-camp")["record_ids"], ["a-1"])

    def test_ATTACK_a_readback_for_the_other_campaign_is_refused(self):
        """HOLDS - the readback is sealed to one campaign id.

        `configdiff.Readback` carries the campaign it compared, so Client B's
        verified read-back cannot authorise a write to Client A's campaign
        even though both are `PASS` and both are fresh.
        """
        self.refused_at("readback", A, "a-1", self.campaign_a,
                        readback=self.readback(self.campaign_b))


# ===================================================================== 5 ===

class ProviderIdentityIsNotClientIdentity(Estate):
    """The invariant PRODUCT-GOAL.md states and this repository cannot yet keep.

    "A provider operation binds `client_id` + `provider` + the expected
    provider workspace or account. Provider identity is not client identity."

    Nothing binds them. A credential is `BISON_KEY` in the process
    environment, the estate it reaches is chosen in the vendor's UI, the pin
    that would assert which estate is `BISON_WORKSPACE_ID` - also
    process-global - and the canonical campaign row has no field for either.
    """

    def test_the_credential_is_process_global_and_carries_no_client(self):
        """LEAKS - src/providers/bison.py:27-28, `key('BISON_KEY')`.

        One process holds one EmailBison credential. Two clients in one run
        therefore share it, and which estate it reaches is a vendor UI setting
        neither client's canonical state records. There is no per-client
        credential lookup to call, which is the finding: not a weak boundary,
        an absent one.
        """
        from src.providers import bison
        import inspect
        source_params = inspect.signature(bison.headers).parameters
        self.assertEqual(list(source_params), [],
                         "headers() now takes an argument - if it takes a "
                         "client, this leak is closed")
        self.assertEqual(list(inspect.signature(bison.base).parameters), [])
        # And the module says so itself, in the one place tenancy is declared.
        self.assertEqual(bison.scope()["parameter"], None)
        self.assertEqual(bison.scope()["kind"], "credential_bound")

    def test_the_canonical_binding_is_one_row_per_client_and_provider(self):
        """HOLDS - `clients.provider_workspace`, src/clients.py:192-221.

        This is the right shape and the right place: the binding lives in the
        client's own configuration under `providers.<provider>.workspace`, so
        it is derived from client identity rather than handed in by a caller,
        and it is not defaulted to `BISON_WORKSPACE_ID`.
        """
        self.assertEqual(
            clients.provider_workspace(self.config_a, "emailbison"),
            str(A_ESTATE))
        self.assertEqual(
            clients.provider_workspace(self.config_b, "emailbison"),
            str(B_ESTATE))
        # Unbound is None, and None is never permission.
        self.assertIsNone(
            clients.provider_workspace(self.config_a, "heyreach"))
        self.assertIsNone(clients.provider_workspace({}, "emailbison"))
        self.assertIsNone(clients.provider_workspace(None, "emailbison"))

    def test_the_send_gate_reads_the_binding_rather_than_its_caller(self):
        """HOLDS - src/executionguard.py:387-392.

        The account-level collision read takes its estate from
        `clients.provider_workspace(config, ...)`, not from the `workspace`
        argument. Asserted by giving the call Client B's estate number and
        watching the gate ask about Client A's anyway.
        """
        with self.allow_collision() as (_li, account, _policy), \
                self.allow_killswitch():
            self.authorize(A, "a-1", self.campaign_a, workspace=B_ESTATE)
        self.assertEqual(account.call_args.kwargs["expect_workspace"],
                         str(A_ESTATE))

    def test_an_unbound_client_is_held_rather_than_defaulted(self):
        """HOLDS, fail-closed - src/executionguard.py:388-391.

        A brand new client with no `providers` block. The wrong behaviour is
        to fall back to the env pin or to client #1's estate; the right one
        is to refuse, which is what happens.

        The subtraction is asserted before the gate is asked. This wrote
        `self.raw_config` back on the assumption that the real file carried
        no binding; it does now, so the test rewrote a BOUND client and then
        failed because a bound client was allowed - the fixture reporting a
        product bug that was not there.
        """
        unbound = _without_providers(self.raw_config)
        self._write_config(A, unbound)
        self.assertIsNone(
            clients.provider_workspace(clients.parse(unbound), "emailbison"),
            "the fixture still carries a binding, so this test would prove "
            "nothing about an unbound client")
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(A, "a-1", self.campaign_a)
        self.assertEqual(caught.exception.gate, "account_collision")
        self.assertIn("names no EmailBison workspace", caught.exception.why)

    @unittest.expectedFailure
    def test_ABSENT_the_email_lane_still_takes_its_estate_from_the_caller(self):
        """ABSENT - the binding reached one of the two collision reads.

        `executionguard.authorize` now has both in it, eight lines apart:

          src/executionguard.py:362  check_address(expect_workspace=workspace)
          src/executionguard.py:392  check_account(expect_workspace=estate)

        The first is the caller's `--workspace` integer; the second is the
        canonical binding. So an email action can read PERSON-level prior
        contact from one estate and ACCOUNT-level prior contact from another,
        with nothing comparing them - and the person-level read is the one
        that answered CLEAR against Bluewave's empty estate on 2026-09-09.

        The assertion below is what closing it looks like: the two reads
        agree because both come from the binding. It fails today.
        """
        rec, contact, campaign, config = self.approved(A, "a-1",
                                                       self.campaign_a)
        with _both(mock.patch.object(collision, "check_address",
                                     return_value=(collision.CLEAR, {})),
                   mock.patch.object(collision, "check_account",
                                     return_value={}),
                   mock.patch.object(collision, "account_policy",
                                     return_value=(collision.ALLOW, "none")),
                   mock.patch.object(killswitch, "require",
                                     return_value=True)) as (address,
                                                             account, _p, _k):
            try:
                executionguard.authorize(
                    operation="bison.add_lead", channel="email",
                    campaign=campaign, rec=rec, contact=contact,
                    step_key="day3", workspace=B_ESTATE, config=config,
                    now=NOW, readback=self.readback(campaign))
            except executionguard.NotAuthorized:
                pass
        self.assertEqual(str(address.call_args.kwargs["expect_workspace"]),
                         str(account.call_args.kwargs["expect_workspace"]))

    @unittest.expectedFailure
    def test_ABSENT_nothing_binds_a_credential_to_the_client_it_reaches(self):
        """ABSENT - the binding is asserted, the credential is not selected.

        `provider_workspace` says which estate Client A's actions belong in,
        and `bison.require_workspace` proves the credential currently reaches
        that estate. What neither can do is pick a credential: there is one
        `BISON_KEY` per process. Two clients in one run share it, so if their
        estates differ, at most one of them can act - and which one depends on
        a vendor UI setting.

        The assertion below is what a real binding would make possible:
        asking the client's configuration which credential to use. Fails
        today because no such lookup exists.
        """
        self.assertTrue(hasattr(clients, "provider_credential"))
        self.assertNotEqual(
            clients.provider_credential(self.config_a, "emailbison"),
            clients.provider_credential(self.config_b, "emailbison"))

    @unittest.expectedFailure
    def test_ABSENT_the_cli_can_still_name_an_estate_for_any_client(self):
        """ABSENT - `--workspace` survives on the modules that read estates.

        `src/executionguard.py:670` requires `--workspace` as an integer and
        `src/collision.py:472` requires it too. With a canonical binding in
        place these arguments are no longer the source of truth, and while
        they exist an operator can still name any estate for any client on
        the command line. They should be removed, not merely ignored.
        """
        seen = dict(cli_arguments(executionguard))
        seen.update(cli_arguments(collision))
        self.assertNotIn("--workspace", seen)

    def test_ATTACK_an_unnamed_estate_is_refused_on_the_email_lane(self):
        """HOLDS - src/executionguard.py:235-240.

        The narrow half that IS enforced: an email action with no workspace
        named is refused at gate 1 rather than reading prior contact from
        whatever estate the credential was last pointed at. This is the
        2026-09-09 false clear, closed. It does not establish WHOSE estate a
        named one is.
        """
        rec, contact, campaign, config = self.approved(A, "a-1",
                                                       self.campaign_a)
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.authorize(
                operation="bison.add_lead", channel="email",
                campaign=campaign, rec=rec, contact=contact, step_key="day3",
                workspace=None, config=config, now=NOW,
                readback=self.readback(campaign))
        self.assertEqual(caught.exception.gate, "tenancy")

    def test_ATTACK_a_defaulted_estate_pin_is_not_inherited_from_the_process(self):
        """LEAKS - `BISON_WORKSPACE_ID` is process-global, src/replywatch.py:125.

        The pin that says which estate a read is for is one environment
        variable for the whole process. Set it once - `providers.load_env`
        reads `config/.env` and leaves it in `os.environ` - and every client
        in that process inherits it, including the one it is wrong for.

        `senderinventory.run` is the concrete consumer
        (src/senderinventory.py:379-386): called for Client B with no explicit
        pin, it takes Client A's. Asserted here without reaching a provider:
        the pin is read and the value observed, and the read stops there.
        """
        from src import replywatch
        self.assertIsNone(replywatch.expected_workspace("emailbison"))
        os.environ["BISON_WORKSPACE_ID"] = str(A_ESTATE)
        # Read for a completely different client. Same answer.
        self.assertEqual(replywatch.expected_workspace("emailbison"),
                         str(A_ESTATE))
        import inspect
        self.assertNotIn(
            "client",
            inspect.signature(replywatch.expected_workspace).parameters,
            "expected_workspace now takes a client - the pin is bound")

    def test_ATTACK_an_inventory_run_stamps_the_client_it_was_told(self):
        """LEAKS - src/senderinventory.py:142 `build(workspace, rows)`.

        The rows come from whatever estate the credential reaches; the client
        slug comes from `--workspace` on the command line. Nothing compares
        them. So one estate's inboxes can be installed as ANOTHER client's
        canonical roster, and once installed they satisfy the executionguard
        sender gate for that client - the gate that exists precisely to prove
        a seat is ours.

        Proved against `build` alone, with no provider read: the provider row
        below is Client A's inbox by every field it carries, and `build`
        attributes it to Client B without complaint.
        """
        a_inbox = {"id": 500, "email": "ansel@a.test", "name": "Ansel A",
                   "daily_limit": 40, "type": "smtp"}
        built = senderinventory.build(B, [a_inbox])
        self.assertEqual(len(built), 1)
        self.assertEqual(built[0]["workspace"], B)
        self.assertEqual(built[0]["email_address"], "ansel@a.test")


# ===================================================================== 6 ===

class SuppressionDoesNotCross(Estate):
    """One client's suppression must not suppress another's - except by policy."""

    def test_the_agency_dnc_is_global_and_that_is_the_policy(self):
        """HOLDS BY DESIGN - src/agencydnc.py, and it must stay this way.

        Somebody tells Resonate never to contact them again. That has to hold
        whichever client next imports them, so this list is deliberately
        global - and stores a fingerprint rather than an address, so being
        global does not make it a directory of other clients' prospects.

        This test is here to stop a future isolation pass from "fixing" it.
        """
        agencydnc.add("email", "robin@westmill.test")
        # Suppressed for whoever asks, which is the policy.
        self.assertTrue(agencydnc.lookup({"email": "robin@westmill.test"}))
        self.assertIsNotNone(
            agencydnc.Index().get("email:robin@westmill.test"))
        # And the file names nobody. That is what makes global safe: it is an
        # index of fingerprints, not a directory of other clients' prospects.
        index = agencydnc.load()
        row = list(index.values())[0]
        self.assertNotIn("westmill", str(index))
        self.assertNotIn("client", row)

    def test_a_client_suppression_is_on_the_record_and_travels_with_it(self):
        """HOLDS - suppression lives on the queue record, which is scoped."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "b-1":
                    row["suppression"] = {"reason": "client asked",
                                          "at": store.now()}
        self.assertTrue(self.repo_b.record("b-1").get("suppression"))
        self.assertIsNone(self.repo_a.record("a-1").get("suppression"))
        # And A's eligibility never consults B's row.
        self.assertEqual(
            [r["id"] for r in self.repo_a.records()], ["a-1"])

    def test_LEAK_the_hygiene_index_is_unscoped_by_default(self):
        """LEAKS - src/hygiene.py:221, `recs = store.load()` when None.

        `hygiene.index()` with no arguments indexes EVERY tenant, and
        `hygiene.check` then reports another client's contact history -
        company, domain, contact name, last touch - as the reason an import
        row is suppressed. Every caller in `src/web` passes
        `repo.records()`, so this is not exploited today; it is default-open,
        which is the wrong default for a tenancy boundary.

        The scoped call beside it is the proof the default is doing the
        damage rather than the data.
        """
        wide = hygiene.index()
        self.assertEqual(wide["records"], 2)
        self.assertIn("email:robin@westmill.test", wide["by_identity"])
        scoped = hygiene.index(self.repo_a.records(), workspace=A)
        self.assertEqual(scoped["records"], 1)
        self.assertNotIn("email:robin@westmill.test", scoped["by_identity"])
        # And the leak is a disclosure, not just a refusal: B's company name
        # is in the answer A would get.
        leaked = hygiene.check({"email": "robin@westmill.test",
                                "domain": "westmill.test"}, wide)
        self.assertIn("Westmill", str(leaked))

    def test_LEAK_the_domain_suppression_file_is_global_and_unmovable(self):
        """LEAKS - src/ingest.py:31-35, anchored to the repo root.

        `config/suppress.txt` and `config/suppress.local.txt` are read by
        `ingest.load_suppress` and consumed by `eligibility._suppressed`.
        They take no client, have no environment override, and are NOT in
        `store.STATE_OVERRIDES` - so `store.use_directory` does not move them
        and this estate is reading the developer's real file right now.

        Two consequences. Client B suppressing a domain suppresses it for
        Client A, with nothing recording who asked. And a test cannot isolate
        it, which is why this assertion is about the PATH rather than about
        behaviour: writing to it to prove the leak would edit a real file.
        """
        self.assertNotIn("SUPPRESS", store.STATE_OVERRIDES)
        import inspect
        self.assertEqual(
            list(inspect.signature(ingest.load_suppress).parameters),
            ["path"], "load_suppress now takes a client - leak closed")
        for path in (ingest.SUPPRESS, ingest.SUPPRESS_LOCAL):
            self.assertFalse(
                os.path.abspath(path).startswith(os.path.abspath(self.tmp)),
                f"{path} moved with the estate - update this test")


# ===================================================================== 7 ===

class CollisionDoesNotCross(Estate):
    """Prior contact, read from the right estate or not read at all."""

    def test_the_linkedin_seat_set_is_this_clients_canonical_roster(self):
        """HOLDS - src/collision.py:304-323.

        HeyReach's inbox route has no organisation scope, so the tenant
        boundary cannot come from the query. It comes from the answer: a
        conversation counts as ours only if the seat that held it is in this
        client's inventoried roster.
        """
        self.assertEqual(collision.our_linkedin_seats(A), {"700"})
        self.assertEqual(collision.our_linkedin_seats(B), {"800"})

    def test_a_client_with_no_inventoried_seats_refuses_rather_than_clears(self):
        """HOLDS, fail-closed - `CollisionUnknown`, src/collision.py:318-322.

        A brand new client has no seats. The wrong answer is CLEAR - "nobody
        has written to them" - read from an inbox that is not theirs. This is
        the one that must never become a default.
        """
        self._write_config("clientc", _client_b_config(self.raw_config))
        with self.assertRaises(collision.CollisionUnknown):
            collision.our_linkedin_seats("clientc")

    def test_ATTACK_collision_is_re_read_at_the_gate_with_this_clients_tenant(self):
        """HOLDS for LinkedIn - src/executionguard.py:360-362 passes the client.

        And that is the whole of the naming problem in one place: the
        LinkedIn call gets `campaign["client"]`, the email call two lines
        below gets the vendor estate id, and the parameter is called
        `expect_workspace` in both.
        """
        # Three mocks, and the FIRST is the one this asserts on: the
        # person-level LinkedIn read. Written when `allow_collision` yielded
        # one mock, it bound the whole tuple and asked a tuple for
        # `call_args`, so the gate it exists to pin went unchecked behind an
        # AttributeError.
        with self.allow_collision() as (profile, _account, _policy), \
                self.allow_killswitch():
            self.authorize(A, "a-1", self.campaign_a)
        self.assertEqual(profile.call_args.kwargs["expect_workspace"], A)

    def test_the_two_collision_entry_points_disagree_about_what_a_workspace_is(self):
        """LEAKS (by naming) - one parameter name, two namespaces.

        `check_linkedin_profile(expect_workspace=...)` wants a Resonate client
        slug; `check_address(expect_workspace=...)` wants an EmailBison estate
        id. Asserted on behaviour rather than on the signature text: the slug
        resolves for the LinkedIn side and is meaningless to the email side,
        and vice versa.
        """
        self.assertEqual(collision.our_linkedin_seats(A), {"700"})
        # The client slug on the email side reaches the provider binding
        # check, where it is compared against a numeric vendor id.
        with mock.patch("src.providers.bison.bound_workspace",
                        return_value={"id": A_ESTATE, "name": "A"}):
            from src.providers import bison
            with self.assertRaises(bison.WorkspaceMismatch):
                bison.require_workspace(A)
            self.assertIsNotNone(bison.require_workspace(A_ESTATE))


# ===================================================================== 8 ===

class RepliesDoNotCross(Estate):
    """One client's reply landing on another's record."""

    def test_an_event_naming_the_wrong_client_is_refused(self):
        """HOLDS - src/events.py:423-425 compares the event's client."""
        event = events.neutral(client=B, record_id="a-1",
                               contact_key="avery-nolan", channel="email",
                               type=events.REPLY_RECEIVED)
        out = events.match(event, store.get("a-1")) if hasattr(
            events, "match") else None
        if out is None:
            self.skipTest("events exposes no single-record matcher to call")
        self.assertEqual(out["status"], "unmatched")

    def test_a_reply_on_one_record_is_invisible_to_the_other_client(self):
        """HOLDS - the reply is a record event, and records are scoped."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "b-1":
                    row.setdefault("events", []).append(
                        {"type": events.REPLY_RECEIVED, "at": store.now(),
                         "contact": "robin-vale", "client": B})
        self.assertTrue(self.repo_b.record("b-1")["events"])
        self.assertEqual(self.repo_a.record("a-1")["events"], [])
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.record("b-1")


# ===================================================================== 9 ===

class SpendDoesNotCross(Estate):
    """One client's spend reaching another's ledger, or another's ceiling."""

    def test_every_spend_row_names_its_client_and_check_refuses_without_one(self):
        """HOLDS - src/spendledger.py:85-103 and :145-148."""
        spendledger.record(A, "contactout", "people-search", 2)
        spendledger.record(B, "contactout", "people-search", 3)
        self.assertEqual(spendledger.spent(A), 2)
        self.assertEqual(spendledger.spent(B), 3)
        with self.assertRaises(spendledger.BudgetExceeded):
            spendledger.check(None, self.config_a, 1)
        with self.assertRaises(spendledger.BudgetExceeded):
            spendledger.check("", self.config_a, 1)

    def test_a_budget_is_enforced_against_the_clients_own_rows_only(self):
        """HOLDS - `check` filters by client before comparing to the cap.

        Client B declares a total of 5. Client A spends 100. B's ceiling is
        untouched, and B's own fourth credit is refused.
        """
        spendledger.record(A, "contactout", "people-search", 100)
        spendledger.check(B, self.config_b, 5)          # still affordable
        spendledger.record(B, "contactout", "people-search", 4)
        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(B, self.config_b, 2)
        self.assertIn(B, str(caught.exception))
        self.assertNotIn(A, str(caught.exception).replace(B, ""))

    def test_LEAK_the_per_run_credit_budget_has_no_client_at_all(self):
        """LEAKS - src/enrich.py:113 `Budget`, and :1028 one per run.

        `enrich.run` walks the WHOLE queue - it takes no client filter - and
        charges every record to one in-memory `Budget` built from `--cap`. So
        Client B's enrichment consumes the ceiling an operator set for a
        Client A batch, and the durable per-client ledger never sees it
        because the in-memory cap refused first.

        A denial of service rather than a disclosure, but it is on
        PRODUCT-GOAL's list: one client's spend reaching another's budget.
        """
        import inspect
        from src import enrich
        from src.enrich import Budget
        self.assertNotIn("client", inspect.signature(enrich.run).parameters)
        self.assertNotIn("client", inspect.signature(Budget).parameters)
        budget = Budget(3)
        self.assertTrue(budget.charge(2, "b-1:people-search"))
        self.assertFalse(budget.charge(2, "a-1:people-search"),
                         "A's call was refused by B's spend")

    def test_the_declared_per_run_ceiling_is_enforced_now(self):
        """WAS A LEAK UNTIL 2026-09-25 - `per_run` was read by nothing.

        The recurring defect CLAUDE.md names: a thing computed correctly that
        nothing downstream consumes. `caps()` reported it, the config
        declared it, and `check()` compared only `per_day`, `total` and
        `per_provider_per_day`. The cost of that gap was measured, not
        argued: a chunk stopped at 2,044 credits against a declared ceiling
        of 2,000.

        `check()` now enforces it, by reservation rather than by inspection -
        see `tests/test_a_provider_ceiling_refuses_before_the_call.py`, which
        drives eight real threads at it. Kept in THIS file because the
        tenancy question is the one it was filed under: `per_run` is scoped
        by client, and B's run must not be refused by A's spend.
        """
        self.assertIn("per_run", spendledger.SCOPES)
        config = dict(self.config_b, budget={"per_run": 1})
        self.assertEqual(spendledger.caps(config)["per_run"], 1)
        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(B, config, 1000)
        self.assertIn("per_run", str(caught.exception))
        # A's spend in the same run does not consume B's per_run.
        spendledger.record(A, "contactout", "people-search", 5000)
        spendledger.check(B, dict(self.config_b, budget={"per_run": 5000}), 1)


# ==================================================================== 10 ===

class ActionsAndCapsDoNotCross(Estate):
    """The prospect-facing ledger, and the ceilings measured against it."""

    def test_the_ledger_tenant_is_the_client_not_the_vendor_estate(self):
        """HOLDS - src/actionledger.py:122-157, and the reason is recorded.

        Two clients worked from one EmailBison estate would otherwise share a
        daily ceiling, and one client worked from two estates would have its
        ceiling split with both halves passing.
        """
        today = store.now()
        actionledger.reserve("a-1:avery-nolan:day3:linkedin",
                             channel="linkedin", workspace=A,
                             provider_workspace=A_ESTATE,
                             campaign_id="a-camp", sender_id="700",
                             rec_id="a-1", contact_key="avery-nolan",
                             step_key="day3", operation="li", fingerprint="f",
                             by="test", cap_per_day=1, cap_per_sender=1)
        self.assertEqual(actionledger.count_on(today, workspace=A), 1)
        self.assertEqual(actionledger.count_on(today, workspace=B), 0)
        # And B's first action is not refused by A's having used the ceiling.
        actionledger.reserve("b-1:robin-vale:day3:linkedin",
                             channel="linkedin", workspace=B,
                             provider_workspace=B_ESTATE,
                             campaign_id="b-camp", sender_id="800",
                             rec_id="b-1", contact_key="robin-vale",
                             step_key="day3", operation="li", fingerprint="f",
                             by="test", cap_per_day=1, cap_per_sender=1)
        self.assertEqual(actionledger.count_on(today, workspace=B), 1)

    def test_the_provider_estate_is_recorded_beside_the_tenant_not_as_it(self):
        """HOLDS - src/actionledger.py:232-234.

        This is the shape a canonical binding should take everywhere: the
        client is the tenant, the vendor estate is evidence of where the
        action was aimed. It exists on the ledger row and nowhere upstream of
        it, which is the gap `ProviderIdentityIsNotClientIdentity` names.
        """
        actionledger.reserve("a-1:avery-nolan:day3:linkedin",
                             channel="linkedin", workspace=A,
                             provider_workspace=A_ESTATE,
                             campaign_id="a-camp", sender_id="700",
                             rec_id="a-1", contact_key="avery-nolan",
                             step_key="day3", operation="li", fingerprint="f",
                             by="test", cap_per_day=1, cap_per_sender=1)
        row = actionledger.rows_for("a-1:avery-nolan:day3:linkedin")[0]
        self.assertEqual(row["workspace"], A)
        self.assertEqual(row["provider_workspace"], A_ESTATE)

    def test_ATTACK_a_campaign_naming_no_client_cannot_reserve_anything(self):
        """HOLDS, fail-closed - src/executionguard.py:424-426.

        No client context is no execution. The campaign row is otherwise
        complete and approved.
        """
        rec, contact, campaign, config = self.approved(A, "a-1",
                                                       self.campaign_a)
        campaign = dict(campaign, client=None)
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                executionguard.authorize(
                    operation="linkedin_connection_request",
                    channel="linkedin", campaign=campaign, rec=rec,
                    contact=contact, step_key="day3", workspace=A_ESTATE,
                    config=config, now=NOW, readback=self.readback(campaign))
        # It used to refuse at `campaign_approval`, incidentally: the approval
        # fingerprint covers the client field, so blanking it invalidated the
        # approval before any tenancy check was reached, and this asserted
        # that. Gate 1 now asks directly whether the record's client and the
        # campaign's client are the same, and refuses an empty one on either
        # side - so a clientless campaign is caught by the gate whose subject
        # it is, at the first gate that can see it, rather than by a
        # side-effect of fingerprinting two gates later.
        #
        # The property that matters is unchanged and still asserted last:
        # nothing was reserved.
        self.assertEqual(caught.exception.gate, "tenancy")
        self.assertIn("unowned record", caught.exception.why)
        self.assertEqual(actionledger.load(), [])

    def test_ATTACK_a_record_may_not_run_in_another_clients_campaign(self):
        """The leak that gate: everything below gate 1 reads the CAMPAIGN's
        client - the killswitch, the pilot caps, the sender roster, the ledger
        row - and nothing asked whether the record was that client's.
        `eligibility._selected` checks only that the campaign lists the record
        id, which is exactly the thing a mistake supplies.

        So Client B's prospect inside Client A's campaign was authorised under
        A's tenancy and recorded against it: contacted from the wrong estate,
        by the wrong sender, out of the wrong daily allowance, and invisible
        in B's audit.
        """
        rec, contact, campaign, config = self.approved(A, "a-1",
                                                       self.campaign_a)
        theirs = dict(rec, client=B)
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                executionguard.authorize(
                    operation="linkedin_connection_request",
                    channel="linkedin", campaign=campaign, rec=theirs,
                    contact=contact, step_key="day3", workspace=A_ESTATE,
                    config=config, now=NOW, readback=self.readback(campaign))
        self.assertEqual(caught.exception.gate, "tenancy")
        self.assertIn(B, caught.exception.why)
        self.assertIn(A, caught.exception.why)
        self.assertEqual(actionledger.load(), [],
                         "one client's prospect was reserved against another")


# ==================================================================== 11 ===

class ApprovalsDoNotCross(Estate):
    """An approval granted in one tenancy consumed in another."""

    def test_an_approval_is_bound_to_the_record_that_carries_it(self):
        """HOLDS - approval lives in `rec["cadence"]`, and records are scoped."""
        rec_b, contact_b, _camp, _cfg = self.approved(B, "b-1",
                                                      self.campaign_b)
        self.assertTrue(approval.is_approved(
            rec_b, contact_b["key"], "day3",
            rec_b["cadence"][contact_b["key"]]["day3"]))
        rec_a = store.get("a-1")
        self.assertEqual(rec_a.get("cadence"), None)
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.record("b-1")

    def test_ATTACK_client_bs_campaign_approval_does_not_bless_client_as_step(self):
        """HOLDS - the campaign fingerprint covers the campaign's own contents.

        Client B's campaign is approved. Client A's campaign is not. The
        gate refuses A whatever B holds.
        """
        self.approved(B, "b-1", self.campaign_b)
        rec, contact, campaign, config = self.approved(A, "a-1",
                                                       self.campaign_a)
        campaign.pop("approval")
        campaign["status"] = campaigns.DRAFT
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                executionguard.authorize(
                    operation="linkedin_connection_request",
                    channel="linkedin", campaign=campaign, rec=rec,
                    contact=contact, step_key="day3", workspace=A_ESTATE,
                    config=config, now=NOW, readback=self.readback(campaign))
        self.assertEqual(caught.exception.gate, "campaign_approval")


# ==================================================================== 12 ===

class PausingClientBDoesNotStopClientA(Estate):
    """"Pausing or failing Client B does not stop unrelated safe work."

    The three pauses this system has are separate on purpose - the workspace
    switch, the campaign pause and the account pause - and each is asserted
    below for its own blast radius.
    """

    def test_the_sending_switch_is_per_workspace(self):
        """HOLDS - src/killswitch.py:112-134 reads one workspace's policy.

        Absence is off, which is why both start refused: the assertion is
        that turning A on while B stays off gives two different answers from
        the same function.
        """
        ws.set_policy(A, {"sending.live": "on"}, actor="test")
        a_layer = killswitch.workspace_state(A)
        b_layer = killswitch.workspace_state(B)
        self.assertTrue(a_layer["sending"], a_layer["why"])
        self.assertFalse(b_layer["sending"])
        self.assertEqual(b_layer["layer"], killswitch.WORKSPACE)
        self.assertEqual(a_layer["layer"], killswitch.WORKSPACE)
        # And turning B on afterwards does not turn A off.
        ws.set_policy(B, {"sending.live": "on"}, actor="test")
        self.assertTrue(killswitch.workspace_state(A)["sending"])
        self.assertTrue(killswitch.workspace_state(B)["sending"])

    def test_freezing_client_bs_campaign_leaves_client_as_running(self):
        """HOLDS - the freeze is a field on one campaign row."""
        campaigns.freeze(self.campaign_b, "client B incident", by="operator")
        campaigns.save([c for c in campaigns.load()
                        if c["campaign_id"] != "b-camp"] + [self.campaign_b])
        self.assertFalse(
            killswitch.campaign_state(campaigns.get("b-camp"))["sending"])
        self.campaign_a["status"] = campaigns.RUNNING
        self.assertTrue(killswitch.campaign_state(self.campaign_a)["sending"])

    def test_pausing_client_bs_account_does_not_pause_client_as(self):
        """HOLDS - `cadence.paused_domains` keys on (client, domain)."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "b-1":
                    row["paused"] = {"reason": "client asked",
                                     "at": store.now()}
        paused = cadence.paused_domains(store.load())
        self.assertIn((B, "westmill.test"), paused)
        self.assertNotIn((A, "northgate.test"), paused)

    def test_LEAK_paused_domains_accepts_a_client_and_ignores_it(self):
        """LEAKS (latently) - src/cadence.py:826, the parameter is unused.

        `paused_domains(recs, client=B)` returns Client A's paused pairs too.
        Nothing is exploited by it today because every consumer matches on
        the whole `(client, domain)` tuple - but a caller reading the
        signature would believe it had scoped, and a parameter that looks
        like a filter and filters nothing is how the tuple match gets removed
        later as redundant.
        """
        with store.transaction() as rows:
            for row in rows:
                row["paused"] = {"reason": "x", "at": store.now()}
        asked_for_b = cadence.paused_domains(store.load(), client=B)
        self.assertIn((A, "northgate.test"), asked_for_b)

    def test_a_failure_reading_client_bs_config_does_not_stop_client_a(self):
        """HOLDS - `clients.load` is per client and raises for the broken one.

        Client B's config file is corrupted mid-run. Client A still loads,
        still renders its step, and still authorizes. This is the "failing
        Client B" half of the requirement.
        """
        self._write_config(B, "example: true\n")
        with self.assertRaises(clients.ConfigError):
            clients.load(B)
        with self.allow_collision(), self.allow_killswitch():
            auth = self.authorize(A, "a-1", self.campaign_a)
        self.assertEqual(auth.workspace, A)
        self.assertIn("reserved", auth.gates)


# ==================================================================== 13 ===

class NoClientContextIsNoAccess(Estate):
    """The invariant, asserted as a refusal on each of its four clauses."""

    def test_an_unknown_or_absent_client_slug_is_refused(self):
        """HOLDS - src/repo.py:113-119, and the grammar at :50."""
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client(None)
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("")
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("no-such-client")
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("../productive")

    def test_a_missing_workspace_id_is_refused_before_the_filesystem(self):
        """HOLDS - src/repo.py:133-137."""
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(A_OPS, None)
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(A_OPS, "../clientb")
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(A_OPS, B)

    def test_a_config_load_with_no_client_raises_rather_than_defaulting(self):
        """HOLDS, fail-closed - src/clients.py:145-150.

        The important half is that it does not fall back to client #1. A
        default here would make every unscoped call site silently Productive's.
        """
        for bad in (None, "", "PRODUCTIVE", "../productive"):
            with self.assertRaises(clients.ConfigError):
                clients.load(bad)

    def test_an_unowned_record_belongs_to_nobody_rather_than_to_everybody(self):
        """HOLDS - src/repo.py:193-194 requires an exact match.

        `store.append` now refuses a null client (src/store.py:808), so
        the orphan is created via `store.transaction`, the lower-level
        path. The test asserts the Repo boundary, not the ingestion path.
        """
        orphan = dict(a_record("orphan", None, "Orphan",
                               "orphan.test", "k", "k@orphan.test", "k"),
                      client=None)
        with store.transaction() as rows:
            rows.append(orphan)
        self.assertEqual([r["id"] for r in self.repo_a.records()], ["a-1"])
        self.assertEqual([r["id"] for r in self.repo_b.records()], ["b-1"])
        self.assertEqual(len(repo_module.admin_repo().records()), 3)
        with self.assertRaises(repo_module.CrossClientAccess):
            self.repo_a.record("orphan")

    def test_the_61_unscoped_cli_entry_points_are_the_remaining_surface(self):
        """LEAKS - most CLIs leave `--client` optional and unscoped.

        `Repo` is the canonical boundary and the CLI does not go through it:
        an omitted `--client` means `None`, which in most of these modules
        means every tenant. Asserted on one representative rather than all
        of them, because the fix is structural and belongs in one place.
        """
        import inspect
        from src import spendledger as sl
        params = inspect.signature(sl.report).parameters
        self.assertIsNone(params["client"].default)
        spendledger.record(A, "contactout", "c", 7)
        spendledger.record(B, "contactout", "c", 9)
        # No client named: both tenants, in one number.
        self.assertEqual(sl.report(None)["expected_total"], 16)


if __name__ == "__main__":
    unittest.main()
