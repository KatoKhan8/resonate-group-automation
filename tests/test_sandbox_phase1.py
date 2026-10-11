"""FIVE synthetic agencies, five predetermined verdicts, one sealed sandbox.

WHAT THIS FILE IS. Phase 0 (`docs/GOLDEN-PATH-GATE-7-2026-10-02.md` on
`task-golden-path`) proved ONE record can reach `executionguard` gate 7.
That answers reachability and nothing about discrimination: a guard that
says ALLOW to everything reaches gate 7 too. This file walks FIVE records
whose expected verdicts are decided in advance and DIFFER, so that a path
which answers the same thing to all five is visible as a failure here.

    1 clean, never contacted, research MEDIUM      -> ALLOW at gate 7
    2 legacy sends from a NON-OS campaign, no reply -> not blocked ("FRESH"),
      a legacy touch count, and copy that does not claim a first contact
    3 a previous NEGATIVE email reply               -> blocked on BOTH channels
    4 research only WEAK, relevance 0.35            -> HELD on research
    5 ICP contradiction, 8 from one source and 40
      from another                                  -> UNKNOWN -> HELD

THE SAFETY IS THE SAME AS PHASE 0's AND IS NOT THE `synthetic` FLAG.
Measured 2026-10-02 and unchanged: 0 of 15 pool queries exclude on
`synthetic: true`. Safety here is (a) `store.use_directory` into a throwaway
copy, asserted on `queue_path()` AND `campaigns_path()` separately, (b) the
transport seam sealed BY HOST with a positive control that is run before
every walk, and (c) the MAIN CHECKOUT's own `work/` files md5'd before and
after.

(c) IS NOT THE WORKTREE'S `work/`. This module is normally run from a linked
worktree, where `work/` does not exist at all - so `_md5` would answer None
before and None after and the assertion would be a test that cannot fail.
`_production_root()` resolves the MAIN checkout through `.git`, and
`setUp` asserts both files are actually there.
"""
import contextlib
import datetime
import hashlib
import os
import tempfile
import unittest
from unittest import mock

from src import (actionledger, approval, cadence, campaigns, campaignstrategy,
                 claims, clients, collision, configdiff, eligibility, evidence,
                 events, executionguard, headcount, icp, icpstructural,
                 killswitch, lint, llm, providers, research, segments,
                 senderidentity, store, workspaces)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _production_root():
    """The MAIN checkout, even when this file sits in a linked worktree."""
    dot = os.path.join(ROOT, ".git")
    if os.path.isdir(dot):
        return ROOT
    with open(dot, encoding="utf-8") as handle:
        pointer = handle.read().strip()
    # `gitdir: <main>/.git/worktrees/<name>`
    gitdir = pointer.split(":", 1)[1].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.abspath(os.path.join(ROOT, gitdir))
    return os.path.dirname(os.path.dirname(os.path.dirname(gitdir)))


PRODUCTION = _production_root()
PRODUCTION_FILES = ("queue.jsonl", "campaigns.jsonl")

CLIENT = "productive"

# The host the writer speaks to. Everything else on the wire is refused,
# because the writer model and the provider calls share ONE transport seam
# (`providers.set_transport`) and a blanket sentinel there kills generation.
WRITER_HOSTS = ("openrouter.ai",)
PROVIDER_CONTROL_URL = "https://api.emailbison.com/api/v1/workspaces"

# Rung 1 of `productive_li_heavy_v1`, the connection request. The ONLY step
# in that cadence carrying a `template`, so it renders with no model call -
# measured on this base: li1 template, em1..em5 and li2..li5 `generated`.
STEP_KEY = "li1"
EMAIL_STEP_KEY = "em1"

HEYREACH_CAMPAIGN = 594061
HEYREACH_LIST = 926076
ORG_UNIT = 118832
SEAT = 116968
SEAT_OWNER = "seat-owner-synthetic"
SEAT_OWNER_NAME = "Senda Mockworth"
SEAT_PROFILE = "https://www.linkedin.com/in/senda-mockworth-synthetic"

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
FRESH = (NOW - datetime.timedelta(minutes=1)).isoformat()
STALE = (NOW - datetime.timedelta(minutes=30)).isoformat()

ANGLE_WORDS = ["live budget burn", "scope creep", "resourcing visibility"]

# A NON-OS CAMPAIGN. `config/resonate-os-campaigns.txt` declares the 40 OS
# campaigns on `task-eligibility-reply-only`; 274/327/328/352 are NOT OS.
# Case 2's legacy sends are attributed to 327.
LEGACY_PROVIDER_CAMPAIGN = 327
LEGACY_SEND_COUNT = 3


class WireSealed(RuntimeError):
    """A host outside the writer's was reached. Nothing was sent."""


def _md5(path):
    if not os.path.exists(path):
        return None
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------- the subjects

def _imports_of(path):
    """Every module name a file imports, from its AST.

    CLAUDE.md: "Test behaviour, not the text of the source. Searching source
    for words produces a test that fails when somebody writes a comment."
    An import is structure; a mention is not.
    """
    import ast
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.update(alias.name.split("."))
                names.add((alias.asname or "").strip())
        elif isinstance(node, ast.ImportFrom):
            names.update((node.module or "").split("."))
            for alias in node.names:
                names.add(alias.name)
                names.add((alias.asname or "").strip())
    return {n for n in names if n}


def _calls_in(function):
    """The dotted call targets inside one function, from its own AST."""
    import ast
    import inspect
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target, parts = node.func, []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
            out.add(".".join(reversed(parts)))
    return out


class Company:
    """One synthetic agency. Obviously fake, on `.invalid`, one contact."""

    def __init__(self, rec_id, company, domain, vertical, key, name, title):
        self.rec_id = rec_id
        self.company = company
        self.domain = domain
        self.vertical = vertical
        self.key = key
        self.name = name
        self.title = title
        self.email = "%s@%s" % (key.replace("-", "."), domain)
        self.linkedin = "https://www.linkedin.com/in/%s-synthetic" % key
        self.campaign_id = "phase1-%s" % rec_id


CASE1 = Company("phase1-clean", "Zyntara Media (SYNTHETIC)",
                "zyntara-media.invalid", "Digital Marketing Agency",
                "vera-synthova", "Vera Synthova", "Head of Delivery")
CASE2 = Company("phase1-legacy", "Quorvex Studio (SYNTHETIC)",
                "quorvex-studio.invalid", "Creative / Branding Agency",
                "milo-mockworth", "Milo Mockworth", "Managing Partner")
CASE3 = Company("phase1-replied", "Drexlo Performance (SYNTHETIC)",
                "drexlo-performance.invalid", "Performance Marketing Agency",
                "ines-fauxley", "Ines Fauxley", "Operations Lead")
CASE4 = Company("phase1-weak", "Pellumbra Search (SYNTHETIC)",
                "pellumbra-search.invalid", "SEO Agency",
                "tomo-dummett", "Tomo Dummett", "Head of Client Services")
CASE5 = Company("phase1-conflict", "Vantiqo Design (SYNTHETIC)",
                "vantiqo-design.invalid", "Design / UX Agency",
                "lena-testova", "Lena Testova", "Studio Director")

ALL_CASES = (CASE1, CASE2, CASE3, CASE4, CASE5)


def about(subject):
    """Prose carrying the ICP signals, and NO second headcount source.

    `headcount.witnesses` reads structured fields, not prose - phase 0's
    subject said "our team of forty" in `about` and still resolved to ONE
    source - so this sentence is safe. Case 5's second source is written
    through `headcount.observe`, which is the only way to make two.
    """
    return (
        "%s is a %s. We are a full service agency running paid media "
        "campaigns, brand campaigns and performance marketing retainers for "
        "our clients. Our studio delivers client projects on a retainer and "
        "day rate basis, and every studio hour is billable and logged on a "
        "timesheet so that utilisation across the studio stays visible."
        % (subject.company, subject.vertical.lower()))


def medium_fact(subject):
    """ONE fact engineered to score in the MEDIUM band and stay there.

    Measured on this base: angle hit (+0.35) and operational term (+0.25),
    both earned by the single word `budget`, plus recency (+0.10 x ~0.97)
    lands at 0.697 - at or above `evidence.MIN_RELEVANCE` (0.65) and below
    the 0.75 that would make it STRONG. A CHANGE term would add 0.35 and
    carry it to 1.0, so this sentence deliberately names no launch, hire,
    move or raise.
    """
    return ("%s publishes the budget bands it works to for client retainers "
            "on its services page and says each band is agreed with the "
            "client before any work starts." % subject.company)


# NO DIGIT ANYWHERE IN THESE. `evidence.relevance` adds +0.10 for `\b\d+\b`,
# which carries 0.697 to 0.797 and MEDIUM to STRONG - measured, and it is how
# the first draft of this file failed. The three rows differ by a clause, not
# by a number.
MEDIUM_TAILS = (
    "",
    " The same page sets out how a band is revised when the brief widens.",
    " It also names who on the account side signs a band off.",
)

WEAK_TAILS = (
    "",
    " The post is on the agency journal rather than a services page.",
    " Nothing else on the site returns to the subject.",
)


def weak_fact(subject):
    """relevance EXACTLY 0.35: the angle term and nothing else.

    `creep` is in `ANGLE_WORDS` ("scope creep") and is NOT in
    `evidence.OPERATIONAL_TERMS`, so it earns the +0.35 angle component
    alone. `published_at=None` buckets UNKNOWN with freshness score 0.0, so
    nothing is added for recency and nothing subtracted: 0.35 exactly. By
    `evidence.quality` that is WEAK, not UNUSABLE - 0.35 is the boundary and
    the comparison is `relevance_score < 0.35`.
    """
    return ("%s says on its blog that creep is something the agency talks "
            "about with every new client it takes on." % subject.company)


def research_rows(subject, kind="medium", count=3, today=None):
    """`rec["research"]`: a LIST of `evidence.make` rows, the canonical shape.

    THREE rows, not one. `research.MIN_COPY_EVIDENCE_ROWS` is 3 and
    `_copy_evidence_missing` asks `evidence.select`, so a company with two
    admissible rows is held for research however good they are - which would
    make case 1 fail for case 4's reason.
    """
    today = today or datetime.date.today()
    published = (today - datetime.timedelta(days=10)).isoformat()
    rows = []
    for index in range(count):
        if kind == "medium":
            fact = medium_fact(subject) + MEDIUM_TAILS[index % 3]
            at = published
        else:
            fact = weak_fact(subject) + WEAK_TAILS[index % 3]
            at = None
        row = evidence.make(
            fact=fact,
            source_url="https://%s/evidence-%d" % (subject.domain, index),
            source_type="website", provider="synthetic-fixture",
            record_id=subject.rec_id, contact_key=subject.key,
            published_at=at, persona="champion",
            angle_words=ANGLE_WORDS, today=today)
        row["field"] = "about"
        row["retrieved_at"] = published
        rows.append(row)
    return rows


def synthetic_record(subject, employees=40, research="medium"):
    """The subject. Marketing agency, headcount from ONE source, UK, verified."""
    rec = store.new_record(subject.rec_id, "domains", CLIENT,
                           subject.company, subject.domain)
    rec["state"] = "verified"
    rec["synthetic"] = True
    rec["company_facts"] = {
        "industry": subject.vertical,
        "about": about(subject),
        "description": about(subject),
        # ONE SOURCE, and that is the point of writing only this key: no
        # `employee_range`, no `headcount` block, no `headcount_signal`. Two
        # sources on opposite sides of the floor are CONFLICT in
        # `headcount.resolve`, which `icpstructural._employees` answers
        # UNKNOWN - and UNKNOWN never becomes PASS. Case 5 writes the second.
        "employees": employees,
        "offices": ["Flat 0, Nonexistent House, London, GB"],
        "country": "United Kingdom",
        "research_outcome": "HTTP_SUCCESS",
    }
    rec["contacts"] = [{
        "key": subject.key, "name": subject.name, "title": subject.title,
        "email": subject.email, "linkedin": subject.linkedin,
        "persona": "champion", "angle": "delivery",
        "verification": {"evidence": [
            {"provider": "contactout", "status": "valid",
             "email": subject.email, "catch_all": False, "disposable": False,
             "at": "2026-10-01T00:00:00+00:00"},
            {"provider": "reoon", "status": "valid", "email": subject.email,
             "catch_all": False, "disposable": False, "safe_to_send": True,
             "at": "2026-10-01T00:00:00+00:00"}]},
        "mx": {"status": "known_allowed", "email_eligible": True},
    }]
    rec["research"] = research_rows(subject, kind=research)
    return rec


def legacy_events(subject, count=LEGACY_SEND_COUNT):
    """`count` confirmed sends from a NON-OS campaign, and NO reply.

    `email_delivered` is in `claims.PRIOR_CONTACT_EVENTS`, which is what
    `claims.prior_contact` reads, and it is NOT `events.is_reply`, which is
    what `eligibility._replied` reads. That is precisely the state case 2
    exists to put the system in: touched, but carrying no blocking signal
    under the operator's 2026-10-02 rule.
    """
    rows = []
    for index in range(count):
        at = (NOW - datetime.timedelta(days=120 + index * 7)).isoformat()
        rows.append({"type": events.EMAIL_DELIVERED, "contact": subject.key,
                     "at": at, "channel": "email", "provider": "emailbison",
                     "provider_campaign_id": LEGACY_PROVIDER_CAMPAIGN,
                     "campaign": None, "synthetic": True,
                     "note": "legacy send from a non-OS campaign"})
    return rows


# THE THREE DRAFTS THAT SHIPPED CLEAN BEFORE TASK-981. Measured against a
# record carrying three confirmed `email_delivered` events: `claims.check`
# returned `[]` for every one of them.
FIRST_CONTACT_DRAFTS = (
    "Hi Milo, I am reaching out for the first time about how your studio "
    "handles budget bands on client retainers.",
    "Hi Milo, this is the first time we have written to you and I wanted to "
    "ask about your retainer budget bands.",
    "Hi Milo, apologies for the cold outreach - we have never been in touch "
    "before.",
)


def email_step(subject):
    """An email payload a sender would be holding. 41+ words: the word-range
    floor is exactly 40, measured, 41 passes and 39 fails."""
    body = ("hi %s, we work with agency teams on where a retainer budget "
            "actually goes while the work is still running, rather than at "
            "month end when the margin is already decided. if that is a "
            "question at %s right now i can send over how two other studios "
            "handle it, and if it is not then say so and i will leave it "
            "there for good." % (subject.name.split()[0], subject.company))
    assert len(body.split()) > 40, len(body.split())
    return {"key": EMAIL_STEP_KEY, "channel": "email", "day": 1,
            "subject": "where the retainer budget goes", "body": body}


def negative_reply_event(subject):
    """ONE negative email reply. The only blocking signal under the rule."""
    return {"type": events.REPLY_RECEIVED, "contact": subject.key,
            "at": (NOW - datetime.timedelta(days=9)).isoformat(),
            "channel": "email", "provider": "emailbison",
            "category": "negative", "sentiment": "negative",
            "synthetic": True,
            "body": "not interested, please take us off this list"}


# ------------------------------------------------------------- the sandbox

class SealedSandbox(unittest.TestCase):
    """A store copy, a wire sealed by host, and a before/after md5."""

    def setUp(self):
        # THE MAIN CHECKOUT, NOT THIS WORKTREE, AND ASSERTED PRESENT. A
        # worktree has no `work/`, so md5'ing it would compare None to None.
        self.prod_paths = {name: os.path.join(PRODUCTION, "work", name)
                           for name in PRODUCTION_FILES}
        for name, path in self.prod_paths.items():
            self.assertTrue(os.path.exists(path),
                            "production %s not found at %s - the before/after "
                            "md5 would be vacuous" % (name, path))
        self.prod = {name: _md5(path)
                     for name, path in self.prod_paths.items()}
        self.assertTrue(all(self.prod.values()))
        self.addCleanup(self._assert_production_untouched)

        self.tmp = tempfile.mkdtemp(prefix="sandbox-phase1-")
        self.sandbox = os.path.join(self.tmp, "work")
        before_queue = store.queue_path()
        before_campaigns = store.campaigns_path()
        self.addCleanup(store.use_directory(self.sandbox))

        self.assertNotEqual(store.queue_path(), before_queue)
        self.assertNotEqual(store.campaigns_path(), before_campaigns)
        self.assertTrue(store.queue_path().startswith(
            os.path.abspath(self.sandbox)), store.queue_path())
        self.assertTrue(store.campaigns_path().startswith(
            os.path.abspath(self.sandbox)), store.campaigns_path())
        self.assertIsNone(os.environ.get("CAMPAIGNS"))
        for resolved in (store.queue_path(), store.campaigns_path()):
            self.assertNotIn(os.path.abspath(resolved),
                             {os.path.abspath(p)
                              for p in self.prod_paths.values()}, resolved)

        previous_out = os.environ.get("OUT")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        self.addCleanup(lambda: os.environ.__setitem__("OUT", previous_out)
                        if previous_out is not None
                        else os.environ.pop("OUT", None))

        self.wire = []
        self._seal_wire()
        lint.forget_policies()
        self.addCleanup(lint.forget_policies)
        from src import generate
        generate.clear_company_cache()
        self.addCleanup(generate.clear_company_cache)
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)

    def _seal_wire(self):
        real = providers._urllib_transport
        log = self.wire

        def sealed(method, url, headers, body, timeout):
            host = str(url).split("//", 1)[-1].split("/", 1)[0].lower()
            log.append({"host": host, "method": method})
            if any(host == h or host.endswith("." + h) for h in WRITER_HOSTS):
                return real(method, url, headers, body, timeout)
            raise WireSealed(
                "the wire is sealed: %s %s is not the writer's host. Allowed: "
                "%s. Nothing was sent." % (method, host, WRITER_HOSTS))

        previous = providers.set_transport(sealed)
        self.addCleanup(providers.set_transport, previous)

    def assert_the_seal_fires(self):
        """THE POSITIVE CONTROL. A seal nobody has seen refuse is a seal
        nobody can prove is on, and `calls == []` under a dead seal proves
        only that the code never got that far for some other reason."""
        with self.assertRaises(WireSealed):
            providers.request("GET", PROVIDER_CONTROL_URL, {}, timeout=5)
        self.assertEqual(self.wire[-1]["host"], "api.emailbison.com")

    def assert_no_provider_host_was_reached(self):
        reached = {entry["host"] for entry in self.wire}
        self.assertEqual(reached - {"api.emailbison.com"}, set(),
                         "a host other than the positive control was reached")

    def _assert_production_untouched(self):
        now = {name: _md5(path) for name, path in self.prod_paths.items()}
        self.assertEqual(now, self.prod,
                         "this test changed the main checkout's work/ state")


class Phase1Case(SealedSandbox):
    """One subject, its estate, and the guard call that walks it.

    Subclasses set `SUBJECT` and may override `build_record`.
    """

    SUBJECT = CASE1

    def build_record(self):
        return synthetic_record(self.SUBJECT)

    def setUp(self):
        super().setUp()
        self.assert_the_seal_fires()
        self.subject = self.SUBJECT
        # THE LIVE CLIENT CONFIG, NOT THE FIXTURE CADENCE. The fixture pins
        # `productive_balanced_v1`, whose generated steps are `day1`/`day15`;
        # the writer and this cadence both name `li1`/`em1`..`em5`.
        self.config = dict(clients.load(CLIENT))

        with store.transaction() as rows:
            rows.append(self.build_record())
        self.rec = store.get(self.subject.rec_id)
        self.contact = self.rec["contacts"][0]

        self.campaign = self._campaign()
        self.step = cadence.expand_step(
            self.rec, self.contact,
            executionguard._spec_for(STEP_KEY, campaign=self.campaign,
                                     config=self.config, rec=self.rec,
                                     contact=self.contact),
            self.config)
        self.assertTrue(self.step, "the li1 template did not render")
        self._approve_step(self.step)
        self.rec = store.get(self.subject.rec_id)
        self.contact = self.rec["contacts"][0]

        self._switch_the_workspace_on()
        self._inventory_the_seat()
        # LAST: `campaigns.fingerprint` digests the LEAD SET, so the record
        # has to be final before the campaign approval is taken.
        self._approve_campaign()
        self.spy = Transport()

    # ------------------------------------------------------------- the estate

    def _campaign(self):
        campaign = campaigns.new_campaign(
            self.subject.campaign_id, CLIENT, "CLIENT - SANDBOX PHASE 1",
            created_by="operator")
        campaign.update({
            "heyreach_campaign_id": HEYREACH_CAMPAIGN,
            "heyreach_list_id": HEYREACH_LIST,
            "org_unit": ORG_UNIT, "record_ids": [self.subject.rec_id],
            "senders": {"email": [],
                        "linkedin": [{"id": SEAT, "daily_limit": 1}]},
            "daily_volume": {"email": 0, "linkedin": 1},
            "provider_delays": [["HOUR", 0]],
            "provider_status_expected": "PAUSED",
        })
        return campaign

    def _approve_step(self, step):
        with store.transaction() as rows:
            for row in rows:
                if row["id"] != self.subject.rec_id:
                    continue
                row.setdefault("cadence", {}).setdefault(
                    self.subject.key, {})[STEP_KEY] = dict(
                        step,
                        approval={"by": "operator", "at": store.now(),
                                  "fingerprint": approval.fingerprint(step),
                                  "sender_fingerprint":
                                      approval.sender_fingerprint(self.config)})

    def _approve_email_step(self):
        """Store and approve an em1 the way a generated step is stored.

        `em1` is `generated: True`, so `cadence.expand_step` renders it from
        copy ON THE RECORD rather than from a template - which is what lets
        the email channel be walked at all without asking a writer.
        """
        spec = executionguard._spec_for(
            EMAIL_STEP_KEY, campaign=self.campaign, config=self.config,
            rec=self.rec, contact=self.contact)
        with store.transaction() as rows:
            for row in rows:
                if row["id"] != self.subject.rec_id:
                    continue
                row.setdefault("cadence", {}).setdefault(
                    self.subject.key, {})[EMAIL_STEP_KEY] = dict(
                        email_step(self.subject))
        rec = store.get(self.subject.rec_id)
        rendered = cadence.expand_step(rec, rec["contacts"][0], spec,
                                       self.config)
        self.assertTrue(rendered, "em1 did not render from the stored copy")
        with store.transaction() as rows:
            for row in rows:
                if row["id"] != self.subject.rec_id:
                    continue
                row["cadence"][self.subject.key][EMAIL_STEP_KEY] = dict(
                    rendered,
                    approval={"by": "operator", "at": store.now(),
                              "fingerprint": approval.fingerprint(rendered),
                              "sender_fingerprint":
                                  approval.sender_fingerprint(self.config)})
        self.rec = store.get(self.subject.rec_id)
        self.contact = self.rec["contacts"][0]
        return rendered

    def _approve_campaign(self):
        current = campaigns.fingerprint(self.campaign, store.load(),
                                        self.config)
        self.campaign["approval"] = {"action": "approve", "by": "operator",
                                     "at": store.now(), "fingerprint": current}
        self.campaign["fingerprint"] = current
        self.campaign["status"] = campaigns.APPROVED

    def _switch_the_workspace_on(self):
        with workspaces.transaction() as rows:
            rows.append(workspaces.new_workspace(CLIENT, "Productive",
                                                 client=CLIENT))
        workspaces.set_policy(CLIENT, {"sending.live": "on"}, actor="operator")
        self.assertTrue(killswitch.workspace_state(CLIENT)["sending"])

    def _inventory_the_seat(self):
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_sender(CLIENT, SEAT_OWNER,
                                                  SEAT_OWNER_NAME))
            rows.append(senderidentity.new_linkedin_account(
                CLIENT, "li-%s" % SEAT, SEAT_OWNER, SEAT_PROFILE,
                provider="heyreach", provider_account_id=str(SEAT),
                active=True, daily_limit=40, health="ok"))

    # -------------------------------------------------------------- the guard

    def readback(self, **over):
        kw = dict(diff={"verdict": configdiff.PASS, "failures": []},
                  approved={}, provider={},
                  campaign_id=self.subject.campaign_id, channel="linkedin",
                  provider_campaign_id=HEYREACH_CAMPAIGN, verified_at=FRESH)
        kw.update(over)
        return configdiff.Readback(**kw)

    @contextlib.contextmanager
    def clear_collision(self, profile=None, account=None):
        profile = profile if profile is not None else (collision.CLEAR, {})
        account = account if account is not None else {
            "verdict": collision.CLEAR, "people": [], "emails_sent_total": 0,
            "anyone_in_sequence": False, "any_bounce": False}
        with mock.patch.object(collision, "check_linkedin_profile",
                               return_value=profile), \
             mock.patch.object(collision, "check_account",
                               return_value=account):
            yield

    def authorize(self, **over):
        kw = dict(operation="heyreach.add_lead_to_list", channel="linkedin",
                  campaign=self.campaign, rec=self.rec, contact=self.contact,
                  step_key=STEP_KEY, workspace=ORG_UNIT, config=self.config,
                  now=NOW, readback=self.readback(), staging=True)
        kw.update(over)
        return executionguard.authorize(**kw)

    def allow(self, **over):
        with self.clear_collision():
            return self.authorize(**over)

    def refused_at(self, gate, profile=None, account=None, **over):
        self._clear_the_ledger()
        with self.clear_collision(profile=profile, account=account):
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                auth = self.authorize(**over)
                self.spy.write(auth)
        self.assertEqual(
            caught.exception.gate, gate,
            "expected a refusal at %r, got %r: %s"
            % (gate, caught.exception.gate, caught.exception.why))
        self.assertEqual(self.spy.calls, [],
                         "a provider write happened behind a refused gate")
        return caught.exception

    def walk(self, **over):
        """Run the guard and report (verdict, gates, why) without asserting.

        Used by the probe that builds the report's gate table, so the table
        and the assertions below read the same walk.
        """
        self._clear_the_ledger()
        with self.clear_collision():
            try:
                auth = self.authorize(**over)
            except executionguard.NotAuthorized as refusal:
                return {"verdict": "REFUSED", "gate": refusal.gate,
                        "passed": tuple(refusal.passed), "why": refusal.why}
        return {"verdict": "ALLOW", "gate": None, "passed": tuple(auth.gates),
                "why": None, "key": auth.key}

    def _clear_the_ledger(self):
        if os.path.exists(actionledger.path()):
            os.remove(actionledger.path())


class Transport:
    """Any provider write. Records; never sends."""

    def __init__(self):
        self.calls = []

    def write(self, authorization, **kw):
        if not isinstance(authorization, executionguard.Authorization):
            raise AssertionError(
                "a write layer must refuse anything that is not an "
                "Authorization; a dict claiming the gates passed is not proof")
        authorization.spend()
        self.calls.append({"key": authorization.key, **kw})
        return {"ok": True}


# =========================================================== the five subjects

class EverySubjectIsSynthetic(Phase1Case):
    """Nothing here can reach a human, on any of the five."""

    def test_every_domain_is_on_invalid(self):
        for case in ALL_CASES:
            with self.subTest(case=case.rec_id):
                self.assertTrue(case.domain.endswith(".invalid"))
                self.assertTrue(case.email.endswith(".invalid"))
                self.assertIn("synthetic", case.linkedin)
                self.assertIn("SYNTHETIC", case.company)

    def test_the_record_carries_the_flag_that_protects_nothing(self):
        """Set for the reader. Measured 2026-10-02 and re-read here: it is
        not what keeps this safe, the store copy and the host seal are."""
        self.assertIs(self.rec["synthetic"], True)


# ----------------------------------------------------- case 1: ALLOW at gate 7

EXPECTED_GATES = (
    "tenancy", "approval", "campaign_approval", "readback",
    "eligibility", "suppression", "copy", "claims", "fatigue",
    "collision", "account_collision",
    "sender", "pilot_cap", "stoppability",
    "ledger", "killswitch:workspace", "reserved",
)


class CaseOneReachesAllow(Phase1Case):
    """Clean, never contacted, research MEDIUM -> ALLOW at gate 7."""

    SUBJECT = CASE1

    def test_the_research_is_medium_and_derived_not_asserted(self):
        """MEDIUM, not STRONG and not WEAK, and re-derived on read."""
        usable = evidence.usable(self.rec["research"])
        self.assertEqual(len(usable), len(self.rec["research"]))
        for row in usable:
            self.assertEqual(row["quality"], evidence.MEDIUM_Q)
            self.assertGreaterEqual(row["relevance_score"],
                                    evidence.MIN_RELEVANCE)
            self.assertLess(row["relevance_score"], 0.75)

    def test_a_stored_band_does_not_survive_the_recheck(self):
        """THE NON-VACUITY OF 'DERIVED'."""
        forged = dict(self.rec["research"][0],
                      fact="we use cookies on this website to improve your "
                           "experience",
                      relevance_score=0.99, quality=evidence.STRONG)
        self.assertEqual(evidence.recheck(forged)["quality"],
                         evidence.UNUSABLE)

    def test_research_does_not_hold_this_record(self):
        self.assertIsNone(research.why(self.rec, for_copy=True))

    def test_both_icp_authorities_say_pass(self):
        segment = segments.classify(self.rec, self.config)
        structural = icpstructural.structural(self.rec, self.config, segment)
        self.assertEqual(structural["verdict"], icpstructural.ICP_PASS)
        self.assertTrue(structural["eligible"])
        self.assertEqual(structural["unknown_criteria"], [])
        scored = icp.score(self.rec, self.config, segment)
        self.assertEqual(scored["structural"]["verdict"],
                         icpstructural.ICP_PASS)

    def test_the_headcount_comes_from_exactly_one_source(self):
        segment = segments.classify(self.rec, self.config)
        lower, _upper, source = icpstructural.resolve_employees(self.rec,
                                                                segment)
        self.assertEqual(lower, 40)
        self.assertEqual(source, "company_facts.employees")
        self.assertNotIn("+", source)

    def test_eligibility_says_eligible(self):
        decision = eligibility.decide(self.rec, self.contact, STEP_KEY,
                                      channel="linkedin",
                                      campaign=self.campaign,
                                      recs=store.load(), config=self.config)
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE,
                         decision.get("reasons"))

    def test_gate_seven_returns_allow_and_names_every_gate(self):
        auth = self.allow()
        self.assertIsInstance(auth, executionguard.Authorization)
        self.assertEqual(auth.gates, EXPECTED_GATES)
        self.assertIn("killswitch:workspace", auth.gates)
        self.assertEqual(auth.key, "%s:%s:%s:linkedin"
                         % (self.subject.rec_id, self.subject.key, STEP_KEY))

    def test_the_transport_was_never_called(self):
        self.allow()
        self.assertEqual(self.spy.calls, [])
        self.assert_no_provider_host_was_reached()

    def test_the_walk_reserved_exactly_one_action_in_the_sandbox(self):
        auth = self.allow()
        rows = actionledger.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], auth.key)
        self.assertTrue(actionledger.path().startswith(
            os.path.abspath(self.sandbox)), actionledger.path())

    def test_a_cold_record_may_still_say_it_is_a_cold_approach(self):
        """THE NEGATIVE CONTROL FOR TASK-981, and the reason the new rule is
        asked only when a confirmed touch exists. This person has never been
        written to, so every one of case 2's three drafts is TRUE here and
        must still ship."""
        self.assertIsNone(claims.prior_contact(self.rec, self.contact))
        for draft in FIRST_CONTACT_DRAFTS:
            with self.subTest(draft=draft[:40]):
                self.assertEqual(claims.check(draft, self.rec, self.contact),
                                 [])

    def test_a_false_claim_of_prior_contact_is_still_refused(self):
        """The rule TASK-981 mirrors, unchanged."""
        draft = ("Hi Vera, following up on my last email about your "
                 "retainer budget bands.")
        problems = claims.check(draft, self.rec, self.contact)
        self.assertTrue(problems)
        self.assertIn("no confirmed touch", problems[0]["why"])


# ------------------------------------------- case 2: legacy, non-OS, no reply

class CaseTwoIsTouchedButNotBlocked(Phase1Case):
    """Legacy sends from a NON-OS campaign, no reply.

    Under the operator's rule of 2026-10-02 the ONLY blocking signal is a
    reply, so membership in a non-OS campaign must block nothing - and the
    copy must not go on to claim a first contact.
    """

    SUBJECT = CASE2

    def build_record(self):
        rec = synthetic_record(self.SUBJECT)
        rec["events"] = legacy_events(self.SUBJECT)
        return rec

    def test_the_legacy_sends_are_on_the_record(self):
        delivered = [e for e in self.rec["events"]
                     if e["type"] == events.EMAIL_DELIVERED]
        self.assertEqual(len(delivered), LEGACY_SEND_COUNT)
        self.assertTrue(all(e["provider_campaign_id"]
                            == LEGACY_PROVIDER_CAMPAIGN for e in delivered))

    def test_none_of_them_is_a_reply(self):
        self.assertEqual([e for e in self.rec["events"]
                          if events.is_reply(e)], [])

    def test_nothing_blocks_this_person(self):
        """FRESH: a non-OS campaign is not a blocking signal."""
        fired = [r for r in eligibility.must_not_contact(
            self.rec, self.contact, config=self.config) if r]
        self.assertEqual(fired, [])

    def test_eligibility_still_says_eligible(self):
        decision = eligibility.decide(self.rec, self.contact, STEP_KEY,
                                      channel="linkedin",
                                      campaign=self.campaign,
                                      recs=store.load(), config=self.config)
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE,
                         decision.get("reasons"))

    def test_the_system_knows_it_has_touched_this_person(self):
        """THE HALF THAT EXISTS ON THIS BASE. `claims.prior_contact` reads
        `PRIOR_CONTACT_EVENTS` and returns the FIRST matching entry."""
        touch = claims.prior_contact(self.rec, self.contact)
        self.assertIsNotNone(touch)
        self.assertEqual(touch["type"], events.EMAIL_DELIVERED)

    def test_the_copy_block_cannot_say_how_many_times(self):
        """THE HALF THAT DOES NOT. `generate.py` collapses the touch to a
        BOOL, so the prompt can say "contacted" and cannot say "three legacy
        sends from campaign 327, none of them ours". There is no
        `legacy_touched` anywhere in `src/`, and no count reaches the writer.

        Asserted as an EFFECT on the base, not as a wish: this is what the
        branch's `claims.prior_contact_state` and `src/osattribution.py`
        were written to supply and neither is merged.
        """
        import importlib
        from src import generate

        # The three-state authority and the OS/legacy attribution module are
        # both absent from this base. Asked of the objects, not of the text.
        self.assertFalse(hasattr(claims, "prior_contact_state"))
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("src.osattribution")

        # AND THE EFFECT ON THE PROMPT, built by the real builder. The block
        # the writer is handed carries a BOOL and no count, no campaign and
        # no attribution - so the prompt can say "contacted" and cannot say
        # "three legacy sends, from campaign 327, none of them ours".
        block = generate.context_for(
            "linkedin_note", self.rec, self.contact, client=self.config,
            step_key=STEP_KEY)
        self.assertIs(block["prior_contact"], True)
        self.assertIsInstance(block["prior_contact"], bool)
        flat = repr(block)
        self.assertNotIn("legacy_touched", flat)
        self.assertNotIn(str(LEGACY_PROVIDER_CAMPAIGN), flat)
        self.assertNotIn("email_delivered", flat)

    def test_the_copy_must_not_claim_a_first_contact(self):
        """TASK-981. Measured 2026-10-03 on this base BEFORE the fix: all
        three of these returned `claims.check -> []` against a record
        carrying three confirmed `email_delivered` events."""
        for draft in FIRST_CONTACT_DRAFTS:
            with self.subTest(draft=draft[:40]):
                problems = claims.check(draft, self.rec, self.contact)
                self.assertTrue(problems, "a false first contact shipped")
                self.assertIn("first contact", problems[0]["why"])

    def test_a_true_claim_of_prior_contact_still_ships(self):
        """The opposite direction, so the rule is not "refuse everything":
        with a confirmed touch, "following up on my last email" is TRUE and
        must pass - and `implies_prior_contact` does match it, which is what
        makes this a real test of the `contacted` branch."""
        draft = ("Hi Milo, following up on my last email about your "
                 "retainer budget bands.")
        self.assertIsNotNone(claims.implies_prior_contact(draft))
        self.assertEqual(claims.check(draft, self.rec, self.contact), [])

    def test_gate_seven_is_still_reached(self):
        """FRESH, end to end: a non-OS legacy campaign blocks nothing."""
        auth = self.allow()
        self.assertEqual(auth.gates, EXPECTED_GATES)


# ---------------------------------------------- case 3: a negative email reply

class CaseThreeIsStoppedOnBothChannels(Phase1Case):
    """A previous NEGATIVE email reply stops LinkedIn too."""

    SUBJECT = CASE3

    def build_record(self):
        rec = synthetic_record(self.SUBJECT)
        rec["events"] = [negative_reply_event(self.SUBJECT)]
        return rec

    def test_the_reply_is_the_blocking_signal(self):
        fired = [r for r in eligibility.must_not_contact(
            self.rec, self.contact, config=self.config) if r]
        self.assertIn(eligibility.BLOCKED_REPLIED, fired)

    def test_email_with_nothing_planned_is_skipped_not_blocked(self):
        """MEASURED, AND NOT A DEFECT - recorded so the next reader does not
        mistake it for one. Asked about `em1` with no content in hand, the
        timeline has no such step (em1 is `generated` and nothing generated
        it), so `decide` answers `skipped:no_such_step` BEFORE
        `must_not_contact` is consulted. Nothing goes out either way; the
        point is that this answer is not the stop, and a cross-channel proof
        resting on it would prove nothing."""
        decision = eligibility.decide(self.rec, self.contact, EMAIL_STEP_KEY,
                                      channel="email", campaign=self.campaign,
                                      recs=store.load(), config=self.config)
        self.assertEqual(decision["verdict"], eligibility.SKIPPED)
        self.assertEqual(decision["reasons"], [eligibility.SKIPPED_NO_STEP])

    def test_email_is_blocked_when_there_is_a_step_to_block(self):
        """The email channel, with the payload in hand, as a sender has it."""
        decision = eligibility.decide(
            self.rec, self.contact, EMAIL_STEP_KEY, channel="email",
            campaign=self.campaign, recs=store.load(), config=self.config,
            step=email_step(self.subject))
        self.assertEqual(decision["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_REPLIED, decision["reasons"])

    def test_linkedin_is_blocked_by_the_same_reply(self):
        """THE CROSS-CHANNEL STOP. The reply arrived by EMAIL and stops the
        LINKEDIN step, because `_replied` reads the record's event log and
        not a channel."""
        decision = eligibility.decide(self.rec, self.contact, STEP_KEY,
                                      channel="linkedin",
                                      campaign=self.campaign,
                                      recs=store.load(), config=self.config)
        self.assertEqual(decision["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_REPLIED, decision["reasons"])

    def test_the_guard_refuses_at_the_eligibility_gate(self):
        refusal = self.refused_at("eligibility")
        self.assertIn("readback", refusal.passed)
        self.assertIn(eligibility.BLOCKED_REPLIED, refusal.why)

    def test_the_stop_is_channel_free_by_construction(self):
        """`must_not_contact` TAKES NO CHANNEL. That is the cross-channel
        stop: there is no per-channel answer for a caller to pick, so the
        LinkedIn path and the email path are asking one question."""
        import inspect
        signature = inspect.signature(eligibility.must_not_contact)
        self.assertNotIn("channel", signature.parameters)
        fired = [r for r in eligibility.must_not_contact(
            self.rec, self.contact, config=self.config) if r]
        self.assertIn(eligibility.BLOCKED_REPLIED, fired)

    def test_the_heyreach_factory_asks_that_very_question(self):
        """`heyreachfactory.ensure_leads` gate 2 calls
        `eligibility.must_not_contact` and raises `FactoryRefused` naming the
        contact. The call site is asserted here rather than exercised: the
        factory refuses EARLIER, for want of an approved ten-step sequence
        (measured - the same refusal appears for case 1, which is not
        blocked at all), so running the push and watching it refuse would
        not discriminate between a stopped contact and a clean one."""
        from src import heyreachfactory
        # The import graph, not the text: the factory holds the eligibility
        # module itself, which is the binding a comment cannot fake.
        self.assertIs(heyreachfactory.eligibility, eligibility)
        self.assertIn("eligibility.must_not_contact",
                      _calls_in(heyreachfactory.ensure_leads))

    def test_the_email_guard_route_cannot_be_walked_in_this_sandbox(self):
        """RECORDED SO THE ABSENT ROW IN THE REPORT IS EXPLAINED, AND NOT
        DEFEATED. `executionguard` gate 1 on the email channel calls
        `bison.require_workspace`, which reads the live binding over the
        wire. `tests/__init__.py` scrubs `BISON_KEY` from the environment
        for every test in this package, and the host seal refuses
        api.emailbison.com - so gate 1 is the furthest the email channel
        reaches here, for two independent safety reasons, and neither is
        going to be switched off to produce a verdict."""
        self.assertIsNone(os.environ.get("BISON_KEY"))
        self._approve_email_step()
        refusal = self.refused_at(
            "tenancy", channel="email", step_key=EMAIL_STEP_KEY,
            operation="bison.add_lead_to_campaign",
            readback=self.readback(channel="email"))
        self.assertEqual(tuple(refusal.passed), ())
        self.assertIn("BISON_KEY", refusal.why)

    def test_the_script_the_brief_warns_about_proves_nothing(self):
        """RECORDED, NOT RELIED ON. `scripts/batch_linkedin_push.py` imports
        none of the modules that carry the gates, so a push run through it
        could not have been stopped by this reply - which is why case 3's
        proof is taken at `eligibility` and at the factory instead.

        Asked of the IMPORT GRAPH, parsed from the AST, so a comment
        mentioning a module name does not change the answer."""
        path = os.path.join(ROOT, "scripts", "batch_linkedin_push.py")
        imported = _imports_of(path)
        for name in ("heyreachfactory", "providerwrites", "eligibility",
                     "executionguard"):
            self.assertNotIn(name, imported,
                             "%s is now imported by batch_linkedin_push" % name)


# ------------------------------------------------ case 4: weak research only

class CaseFourIsHeldOnResearch(Phase1Case):
    """Relevance 0.35 is WEAK, and WEAK reaches no writer."""

    SUBJECT = CASE4

    def build_record(self):
        return synthetic_record(self.SUBJECT, research="weak")

    def test_the_rows_score_exactly_point_three_five(self):
        for row in self.rec["research"]:
            self.assertEqual(row["relevance_score"], 0.35)

    def test_point_three_five_is_weak_not_unusable(self):
        for row in self.rec["research"]:
            self.assertEqual(row["quality"], evidence.WEAK)
            self.assertNotEqual(row["quality"], evidence.UNUSABLE)

    def test_nothing_is_admissible(self):
        self.assertEqual(evidence.usable(self.rec["research"]), [])
        self.assertEqual(evidence.select(self.rec["research"]), [])

    def test_research_holds_the_record(self):
        """THE HOLD, AT THE AUTHORITY THAT OWNS IT.

        `research.why(for_copy=True)` is what decides a record is not worth
        asking a writer about, and `enrich` is its caller. Three rows on the
        record and none admissible: `MIN_COPY_EVIDENCE_ROWS` is 3 and
        `_copy_evidence_missing` counts `evidence.select`, not
        `rec["research"]`."""
        self.assertIsNotNone(research.why(self.rec, for_copy=True))
        self.assertEqual(len(self.rec["research"]),
                         research.MIN_COPY_EVIDENCE_ROWS)

    def test_the_template_step_is_authorised_and_that_is_not_a_hallucination(
            self):
        """MEASURED, AND REPORTED AS A PROPERTY OF THE DUMMY, NOT A DEFECT.

        `li1` carries `template: linkedin_intro`. It renders without a model
        and WITHOUT a research fact - the note names the vertical and the
        company and asserts nothing about them - so the `claims` gate finds
        nothing to trace and gate 7 returns ALLOW on a record held for
        research. A case written to test "must not proceed on a
        hallucination" has to walk a step that could carry one, and the only
        steps that can are the generated ones.

        What IS recorded here, as a finding rather than a fix: neither
        `eligibility.decide` nor `executionguard.authorize` consults
        `research.why`. The hold lives upstream.
        """
        auth = self.allow()
        self.assertEqual(auth.gates, EXPECTED_GATES)
        self.assertEqual(self.step.get("template"), "linkedin_intro")
        self.assertEqual(claims.check(self.step.get("note") or "",
                                      self.rec, self.contact), [])
        # The import graph: neither send-path module holds `research` at all,
        # so neither can be asking `research.why`.
        for module in (eligibility, executionguard):
            self.assertFalse(hasattr(module, "research"),
                             "%s now reads research" % module.__name__)

    def test_a_draft_built_on_a_weak_row_is_held_by_eligibility(self):
        """The second authority, reached by naming the weak row as the one
        the draft leans on: `held:evidence_aged_out`."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] != self.subject.rec_id:
                    continue
                row["contacts"][0]["personalization"] = {
                    "selected_evidence_ids":
                        [self.rec["research"][0]["evidence_id"]]}
        rec = store.get(self.subject.rec_id)
        decision = eligibility.decide(rec, rec["contacts"][0], STEP_KEY,
                                      channel="linkedin",
                                      campaign=self.campaign,
                                      recs=store.load(), config=self.config)
        self.assertEqual(decision["verdict"], eligibility.HELD)
        self.assertIn(eligibility.HELD_EVIDENCE_AGED_OUT, decision["reasons"])


# -------------------------------------------- case 5: two headcount authorities

class CaseFiveIsUnknownAndHeld(Phase1Case):
    """8 from one source and 40 from another is CONFLICT, which is UNKNOWN,
    and UNKNOWN never becomes PASS."""

    SUBJECT = CASE5

    def build_record(self):
        rec = synthetic_record(self.SUBJECT, employees=40)
        # THE SECOND AUTHORITY, written the only way two can exist:
        # `headcount.observe` appends rather than overwrites, because a
        # second opinion that replaced the first would destroy the only
        # evidence that a conflict exists.
        headcount.observe(rec, "contactout", value=8)
        headcount.observe(rec, "apollo", value=40)
        return rec

    def test_the_two_sources_disagree(self):
        resolved = headcount.resolve(self.rec, self.config)
        self.assertEqual(resolved["state"], headcount.CONFLICT)
        self.assertTrue(resolved["contradictions"])
        self.assertIsNone(resolved["value"])

    def test_the_structural_answer_is_unknown(self):
        segment = segments.classify(self.rec, self.config)
        structural = icpstructural.structural(self.rec, self.config, segment)
        self.assertIn("employees", structural["unknown_criteria"])
        self.assertNotIn(structural["criteria"]["employees"]["status"],
                         icpstructural.PASSING)

    def test_a_contradiction_goes_to_review_and_never_to_eligible(self):
        """TASK-982. BEFORE THE FIX, measured 2026-10-03: this answered
        `icp_pass_with_uncertainty`, `eligible: True`,
        `icp.score -> icp_status: qualified`, and the record walked to
        `executionguard` gate 7 with an ALLOW."""
        segment = segments.classify(self.rec, self.config)
        structural = icpstructural.structural(self.rec, self.config, segment)
        self.assertEqual(structural["verdict"], icpstructural.ICP_REVIEW)
        self.assertNotEqual(structural["verdict"], icpstructural.ICP_PASS)
        self.assertNotEqual(structural["verdict"],
                            icpstructural.ICP_PASS_WITH_UNCERTAINTY)
        self.assertFalse(structural["eligible"])
        self.assertTrue(structural["criteria"]["employees"]["contradicted"])
        scored = icp.score(self.rec, self.config, segment)
        self.assertEqual(scored["icp_status"], icp.REVIEW)

    def test_an_unmeasured_headcount_is_still_only_uncertainty(self):
        """THE NON-VACUITY OF TASK-982, and the half it must not break.

        Silence is not a contradiction. A record with NO headcount source at
        all still reaches `icp_pass_with_uncertainty` and stays eligible,
        which is what `ICP_PASS_WITH_UNCERTAINTY` was written for. Only the
        contradicted answer is new.
        """
        quiet = synthetic_record(CASE1, employees=None)
        quiet["company_facts"].pop("employees", None)
        segment = segments.classify(quiet, self.config)
        structural = icpstructural.structural(quiet, self.config, segment)
        self.assertIn("employees", structural["unknown_criteria"])
        self.assertFalse(structural["criteria"]["employees"]["contradicted"])
        self.assertEqual(structural["verdict"],
                         icpstructural.ICP_PASS_WITH_UNCERTAINTY)
        self.assertTrue(structural["eligible"])

    def test_the_send_path_never_asks_the_icp_question(self):
        """A FINDING, REPORTED WITH BOTH SIDES AND NOT FIXED HERE.

        After TASK-982 the ICP authority answers REVIEW and the record is
        not eligible - but `eligibility.decide` still says `eligible` and
        `executionguard.authorize` still reaches gate 7, because neither
        module reads `icp_status`, `qualification` or `icpstructural` at
        all. The ICP verdict is enforced upstream, at selection and at
        `qualify`, and `bisonfactory` re-asks it through
        `qualify.state_of`; the LinkedIn/`executionguard` route does not.

        NOT WIDENED HERE. Making `eligibility` refuse on an ICP verdict
        would also refuse every record whose `qualification` block has not
        been written yet (`not_processed`), which is most of a fresh queue,
        and that is a change to what `eligible` MEANS across the estate.
        The narrow fix is the one taken: make the authority answer REVIEW,
        so the layers that do read it stop qualifying the company.
        """
        for module in (eligibility, executionguard):
            for name in ("icp", "icpstructural", "qualify", "headcount"):
                self.assertFalse(hasattr(module, name),
                                 "%s now reads %s" % (module.__name__, name))
        segment = segments.classify(self.rec, self.config)
        self.assertFalse(icpstructural.structural(
            self.rec, self.config, segment)["eligible"])
        decision = eligibility.decide(self.rec, self.contact, STEP_KEY,
                                      channel="linkedin",
                                      campaign=self.campaign,
                                      recs=store.load(), config=self.config)
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE)
        auth = self.allow()
        self.assertEqual(auth.gates, EXPECTED_GATES)

    def test_the_contradiction_is_the_reason_and_not_the_smaller_number(self):
        """Not 8 and not 40. Picking either would be choosing which half of
        the evidence to believe."""
        resolved = headcount.resolve(self.rec, self.config)
        self.assertIsNone(resolved["value"])
        values = {c["value"] for c in resolved["contradictions"]}
        self.assertEqual(values, {8, 40})


if __name__ == "__main__":
    unittest.main()
