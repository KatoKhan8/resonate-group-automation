"""Shared test setup: every test runs against a throwaway queue file.

Provider tests additionally run offline. ProviderTest replaces the transport
with a cassette player and booby-traps urlopen, so a test that would reach a
real API fails loudly instead of spending a credit.
"""
import json
import os
import re
import shutil
import tempfile
import time
import unittest
import urllib.request

from src import evidence as _evidence, offers as _offers, store

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

#: The one fact `canonical_research` carries. A CHANGE term ("opened",
#: "hiring"), an OPERATIONAL term ("delivery", "project", "office") and a
#: figure, because `evidence.relevance` needs all three to clear
#: `MIN_RELEVANCE` and anything below it is scored WEAK and dropped by
#: `evidence.select` - a fixture that looks like research and reaches no prompt.
RESEARCH_FACT = ("TestCorp opened a second office in Zagreb and is hiring 12 "
                 "delivery project managers")


def canonical_research(record_id, fact=RESEARCH_FACT,
                       source_url="https://testcorp.test/about", field="about"):
    """One research row in THE canonical shape: a LIST of evidence entries.

    `rec["research"]` is a list of `evidence.make` rows (`SCHEMA.md`), and this
    builds one through `evidence.make` rather than by hand so a fixture cannot
    drift from the writer's own shape.

    `published_at` is STAMPED AT CALL TIME, seven days back, for the reason
    `mx_cache_entries` above stamps `checked_at`: `evidence.select` re-ages every
    row against the real clock, and past the policy's maximum age `quality` caps
    at WEAK however relevant the fact is. A literal date in a fixture therefore
    stops reaching any prompt on a day nobody committed anything - and a test
    that still passes because the pack quietly became empty is worse than a
    failing one.

    `field` is the page the fact came from. `evidence.make` does not set it -
    `research.py`'s crawl adds it, on 1,137 of the 1,198 rows in the production
    store - and it is what the prompt prints as the source block's label.
    """
    published = time.strftime("%Y-%m-%d",
                              time.gmtime(time.time() - 7 * 86400))
    row = _evidence.make(
        fact=fact, source_url=source_url, source_type="crawl",
        provider="free-crawler", record_id=record_id,
        published_at=published,
        retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()))
    row["field"] = field
    assert row["quality"] in _evidence.USABLE, (
        "this fixture exists to REACH a prompt, and evidence.select only "
        "passes %s rows: got quality=%r relevance=%r"
        % (list(_evidence.USABLE), row["quality"], row["relevance_score"]))
    return [row]


def mx_cache_entries(domains):
    """A seeded MX cache that says "checked just now", not "checked on a date".

    `mx.settings` carries `cache_days: 7` and `mx._fresh` compares
    `checked_at` against the wall clock, so a fixture stamped with a literal
    date stops being fresh on its seventh day and the resolver is consulted
    for real. A fictional `.test` domain publishes no MX, so the stored
    decision flips to `no_mx` and every email step is refused as
    `mx_no_mx` - which is what happened on 2026-09-14 to a fixture stamped
    2026-09-07. The tests had been passing for six days and failed on the
    seventh with no commit in between.

    Stamping `checked_at` at call time is the fixture saying what it means:
    this domain was checked recently and accepts mail.
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return {domain: {"mx_records": ["aspmx.l.google.com"], "status": "ok",
                     "checked_at": now}
            for domain in domains}


def fixture_config(client="productive", **over):
    """A client config pinned to the cadence the FIXTURES were built for.

    THE FIXTURES AND THE LIVE CLIENT FILE ARE TWO DIFFERENT THINGS, and until
    now a great many tests conflated them: `clients.load("productive")` reads
    the config Productive actually runs, so the day that client switched to
    `productive_li_heavy_v1` - steps `em1`..`em5`, `li1`..`li6` - every test
    holding a fixture whose stored cadence is keyed `day1`, `day3`, `day5`
    went red. Measured 2026-09-13, the first time the whole suite was ever
    run to a verdict: 134 failures across 21 modules, and the commonest cause
    by a distance was `NotApprovable: meridian:ivana-saric:day1: no such
    step`.

    None of those tests is about which cadence Productive runs. They are
    about approval, about gates, about push. So they pin the sequence their
    own fixtures were written against - `productive_balanced_v1`, whose keys
    are exactly the `day1`..`day21` the fixture files carry and exactly the
    module constant `cadence.STEPS` - and a client editing their own YAML
    stops being able to turn the suite red.

    It is the same precedent `test_staging_a_campaign_twice_builds_one`
    already set for the EmailBison sequence: pin what the test is not about.

    A test that IS about the live cadence should call `clients.load` directly
    and say why.
    """
    from src import clients

    config = dict(clients.load(client))
    config["cadence"] = "productive_balanced_v1"
    config.update(over)
    return config


def pin_client_config(test, client="productive", **over):
    """Make every module that loads this client's config see the fixture one.

    `fixture_config` is enough for anything that TAKES a config. It is not
    enough for `push.run()` or `approve.pending()`, which load the client's
    file themselves - so a test could pin the cadence it passed in and still
    watch `push` build a timeline from the live one. Measured: after pinning
    the passed config, `approve.pending()` still answered `li1` for every
    contact because it had gone and read `productive.yaml`.

    Patched on the `clients` module object, which is what every caller holds:
    they all do `from . import clients` and then `clients.load(...)`.

    Registers its own cleanup, so a caller writes one line in `setUp`.
    """
    from unittest import mock

    from src import clients, lint

    pinned = fixture_config(client, **over)
    real = clients.load

    def load(name, *a, **kw):
        return dict(pinned) if name == client else real(name, *a, **kw)

    patch = mock.patch.object(clients, "load", load)
    patch.start()
    test.addCleanup(patch.stop)

    # AND FORGET THE POLICY CACHED FROM THE UNPINNED CONFIG.
    #
    # `lint.policy_for_record` caches one verification policy per client slug,
    # so a test that ran earlier and read the LIVE `productive.yaml` leaves that
    # policy behind and this pin is silently ignored - the patch replaces
    # `clients.load`, which the cache means nobody calls again. Cleared on the
    # way in and on the way out, so neither this test nor the next inherits the
    # other's policy.
    #
    # Latent until 2026-09-30, when `eligibility._email_checks` started asking
    # `policy_for_record` too: before that only `lint.check` could be misled by
    # it, and the pinned tests happened not to care.
    lint.forget_policies()
    test.addCleanup(lint.forget_policies)
    return pinned


def pin_fixture_clients(test, **over):
    """Pin BOTH client slugs the record fixtures name, and return the config.

    `phase2`, `phase4` and `phase5` give `harbourline` and `parked` the client
    `contactout`, which is a real slug elsewhere in this suite - `workspaces`,
    `clientapproval` and the hygiene tests all use it - and has no file in
    `config/clients/`. The old email writer tolerated that silently:
    `sequence_for` catches `ConfigError` and leaves the module constant.

    TASK-400's campaign path does not, deliberately. A record it cannot
    configure is refused BY NAME, because the offer gate cannot refuse what it
    was never given, and REWORK 2 was blocked precisely for swallowing that
    error. So the fix for a fixture whose client has no config is to SUPPLY the
    config, never to soften the refusal. `productive_balanced_v1` - what
    `fixture_config` pins - has generated email steps `day1` and `day15`, which
    is byte-identical to the module constant those records already ran on, so
    nothing about any sequence changes.
    """
    from unittest import mock

    from src import clients

    pinned = fixture_config("productive", **over)
    real = clients.load

    def load(name, *a, **kw):
        if name in ("productive", "contactout"):
            return dict(pinned)
        return real(name, *a, **kw)

    patch = mock.patch.object(clients, "load", load)
    patch.start()
    test.addCleanup(patch.stop)
    return pinned


#: One approved offer, for tests that need generation to RUN rather than to
#: fail-close. All six real offers are `approval_status: pending` (launch
#: blocker 8) and `generate_campaign` raises `NotApproved` on any of them, which
#: is correct and is asserted by effect in `tests/test_task400_rework2.py`
#: acceptance 1. A test about something else pins this the same way it pins a
#: cadence: pin what the test is not about. It is a PIN, not a bypass -
#: `allow_pending_offers` is a separate, explicit argument and is never passed.
FIXTURE_APPROVED_OFFER = {
    "OFFER-FIXTURE-001": {
        "capability": "profitability",
        "segment": "all",
        # NO PERSONA, for the same reason the segment is `all`. This offer
        # exists to make the gate PASS for tests that are not about the gate,
        # and `_applies_to` records that "an offer that declares no persona
        # matches every persona". Pinned to `champion` it selected nothing
        # for a fixture record whose persona is `economic_buyer`, and the
        # gate fail-closed with `NotApproved: no offer is selected` - a
        # refusal about the fixture, in tests about a missing model.
        "persona": "",
        "business_problem": "margin is only visible after the month closes",
        "value_proposition": "see project margin while the work runs",
        "concrete_deliverable": "one view per project",
        "cta": "worth a look",
        "approval_status": _offers.APPROVED,
        "campaigns": [],
    }
}


def pin_approved_offer(test):
    """Make the offer gate PASS for a test that is not about the offer gate."""
    from unittest import mock

    patch = mock.patch.object(_offers, "load",
                              return_value=dict(FIXTURE_APPROVED_OFFER))
    patch.start()
    test.addCleanup(patch.stop)


# ---------------------------------------------------------------------------
# THE CAMPAIGN-AWARE MODEL, shared.
#
# TASK-400 routes every copy op through `generate_campaign.generate()`, which
# asks the model six questions per record before the writer speaks (strategy,
# ICP, extract, hypothesis, match, write). `llm.ScriptedModel` plays answers in
# ORDER, so every positional fixture in this suite hands the ICP stage whatever
# the old per-step writer was going to be asked first, and the test then fails
# on its fixture rather than on the behaviour it is about.
#
# It lives HERE rather than in one test module because five modules need it:
# test_generate, test_task400_rework3, test_set_regeneration, test_run and the
# end-to-end pair. Dispatching on the prompt also makes the call ORDER
# irrelevant, which is the right property - almost nothing in this suite is
# about how many times a model is asked.
# ---------------------------------------------------------------------------

#: A body's greeting, which is "Firstname," at the very start. `lint.check`
#: refuses a body that greets somebody who is not the recipient - the defect that
#: put eleven wrong-person drafts into a push file - so a reusable fixture has to
#: address whoever the prompt names rather than whoever it was written for.
_GREETING_RE = re.compile(r"^[A-Z][a-z]+,")


def addressed(text, who):
    return _GREETING_RE.sub(who + ",", text, count=1)


#: The diagnose answer a revive record needs before `lint.check` will accept an
#: email for it at all: `revive_no_diagnosis` fires on a record whose thread was
#: never diagnosed.
DEFAULT_DIAGNOSIS = json.dumps({
    "died_on": "2024-10-17",
    "died_because": ("the question about running the key against a realistic "
                     "list was never answered"),
    "failure_mode": "unanswered_question",
    "last_position": None,
    "what_changed": None,
})

CAMPAIGN_SUBJECTS = {"A": "friday capacity", "B": "overrun timing",
                     "C": "closing the file"}

#: FIVE DISTINCT EMAILS AND FOUR NOTES, which is what the campaign writer emits
#: per call whatever cadence the record runs. All five are filled because
#: `copylint` refuses a lead with an empty step, all five are over the forty-word
#: floor, all five are distinct enough for the repetition gate, and the greeting
#: is rewritten per recipient by `addressed`.
# EACH BODY IS INSIDE ITS OWN STEP'S DECLARED RANGE, because `lint` enforces
# `skills.cold_email_writing.WORD_CONTRACT` and a fixture that calls itself clean
# copy has to be clean copy. Measured 2026-10-02: em1 43, em2 41 and em3 46 words
# were under the floors of 60, 45 and 60, so three of the five steps in every
# campaign test's "good" sequence were drafts this gate refuses. em1 is now 75,
# em2 61 and em3 72; em4 (45) and em5 (49) were already inside theirs. The added
# sentences are QUESTIONS AND HEDGES ON PURPOSE: a fixture lengthened with
# assertions trips `claims.check` instead, which is how an earlier attempt at
# this failed.
CAMPAIGN_SEQUENCES = {
    "em1": (
        "Ivana, your scheduling runs through one spreadsheet that three "
        "people edit across offices, and nobody can say on Tuesday whether "
        "Friday is already full. What decides today whether a new project can "
        "start next week without pushing something else out of the queue? "
        "When two of those three people write a different answer into the "
        "same cell, who do you ask for the one that is right rather than "
        "the one that is most recent?"),
    "em2": (
        "Ivana, month end reconciliation takes four days here and most of it "
        "is chasing which hours belong to which client project. The hours "
        "themselves are recorded; what takes the four days is deciding which "
        "of them were billable and against what. How long after the last "
        "working day do you actually know what each account earned, and who "
        "assembles that answer?"),
    "em3": (
        "Ivana, a studio your size usually discovers a budget overrun when "
        "the invoice is drafted rather than while the work is happening on "
        "the ground. By then the hours are spent and the only lever left is "
        "deciding who absorbs it, which is a reporting delay rather than a "
        "spending problem. What would have to change for an overrun to "
        "surface in week two instead of week six on your active projects?"),
    "em4": (
        "Ivana, when a project slips you hear about it on Friday instead of "
        "Tuesday because the weekly status report is assembled by hand not "
        "observed in real time. What would change for your team if project "
        "status were visible while the work was actually running?"),
    "em5": (
        "Ivana, if none of this is a priority right now, just say so and I "
        "will close the file and stop writing. If it is, the one thing worth "
        "knowing is where your current answer comes from today and how much "
        "reconstruction sits behind it every single reporting month."),
    "connect": ("Ivana, reading about how finance and delivery are split "
                "across the offices. No pitch, happy to follow along."),
    "msg1": ("Ivana, the question I keep asking heads of finance is when a "
             "project overrun becomes visible. Is it while the work runs, or "
             "once the invoice is drafted?"),
    "msg2": ("Ivana, the part that costs the most is usually reconstructing "
             "which hours belong to which client after the month has closed."),
    "msg3": ("Ivana, no pressure at all. If this is not a priority I will "
             "leave it with you."),
}


def writer_answer(sequences, subjects, who=None):
    if who:
        sequences = {k: addressed(v, who) for k, v in sequences.items()}
    return json.dumps({
        "hold": False, "hold_reason": None,
        "subject": subjects["A"],
        "subject_alt": subjects["B"],
        "subject_breakup": subjects["C"],
        "emails": {k: sequences.get(k, "")
                   for k in ("em1", "em2", "em3", "em4", "em5")},
        "ps": {},
        "ps_variant": "ps_fact",
        "linkedin": {k: sequences.get(k, "")
                     for k in ("connect", "msg1", "msg2", "msg3")},
        "facts_used": {}, "confidence": 0.9, "why_this_lead": "fixture",
    })


#: What a body looks like when no rewrite can save it: an unfilled placeholder,
#: an em dash, an attachment reference and a banned opener, all in one line.
CAMPAIGN_BAD_BODY = ("[FIRST NAME], I wanted to reach out about your audit"
                     "—screenshot attached below.")


def is_campaign_prompt(prompt):
    """Is this one of `generate_campaign`'s six stage prompts?

    For a fixture model that already answers the per-step prompts and needs to
    answer these as well. Matched on the same phrases `CampaignModel` dispatches
    on, in one place, so the two cannot disagree about what a campaign prompt is.
    """
    low = str(prompt or "").lower()
    return any(marker in low for marker in (
        "write cold outreach", "is this company", "services agency",
        "extract verifiable facts", "propose one operational problem",
        "choose one productive capability", "plan a nine message",
        # The strategy call. `campaignstrategy._build_strategy_prompt`'s own
        # last line, not "segment" or "persona" - those two appear in several
        # prompts and would have this function claiming prompts it cannot
        # answer, which is how a fixture starts silently returning the wrong
        # thing instead of raising.
        "decide the strategy for this segment"))


def campaign_answer(prompt, bad=False, sequences=None, subjects=None):
    """The answer for one campaign stage prompt. `bad=True` fails every gate."""
    if bad:
        sequences = {k: CAMPAIGN_BAD_BODY for k in CAMPAIGN_SEQUENCES}
    return CampaignModel(
        ((sequences or CAMPAIGN_SEQUENCES),
         (subjects or CAMPAIGN_SUBJECTS))).complete(prompt)


class CampaignModel:
    """Deterministic, and dispatches on the PROMPT rather than on call order.

    `attempts` is one `(sequences, subjects)` pair per writer call; the last
    pair repeats for any further attempt, so `CampaignModel((bad, subs), (good,
    subs))` is "the first draft is refused, the regenerated one passes".
    """

    name = "campaign-aware"

    def __init__(self, *attempts, diagnosis=None, angle=None, hook=None):
        self.attempts = list(attempts) or [(CAMPAIGN_SEQUENCES,
                                            CAMPAIGN_SUBJECTS)]
        self.prompts = []
        self.writer_prompts = []
        self.diagnosis = (diagnosis if diagnosis is not None
                          else DEFAULT_DIAGNOSIS)
        self.angle = angle or json.dumps(
            {"angle": "finance", "evidence": ["Zagreb HR"]})
        self.hook = hook or json.dumps({"hook": "tried three outbound agencies"})

    @property
    def retry_prompts(self):
        """Writer prompts that carry a regeneration instruction."""
        return self.writer_prompts[1:]

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        self.prompts.append(prompt)
        low = prompt.lower()
        if "# diagnose" in low:
            return self.diagnosis
        if "# persona_angle" in low:
            return self.angle
        if "# hook" in low:
            return self.hook
        if "write cold outreach" in low:
            self.writer_prompts.append(prompt)
            i = min(len(self.writer_prompts), len(self.attempts)) - 1
            sequences, subjects = self.attempts[i]
            m = re.search(r"^Writing to:\s*(\S+)", prompt, re.M)
            who = m.group(1).strip().rstrip(",") if m else None
            return writer_answer(sequences, subjects, who)
        if "is this company" in low or "services agency" in low:
            return json.dumps({"is_agency": True, "confidence": 0.9,
                               "evidence": "the record calls it an agency"})
        if "extract verifiable facts" in low:
            return json.dumps({
                "facts": [{"text": "offices in Zagreb HR",
                           "quote": "offices in Zagreb HR",
                           "source_index": 1, "kind": "record",
                           "confidence": 0.9},
                          {"text": "tested a realistic list against "
                                   "fifty credits",
                           "quote": "tested a realistic list against "
                                    "fifty credits",
                           "source_index": 0, "kind": "record",
                           "confidence": 0.9}],
                "angle": "margin_visible_late",
                "angle_reason": "the record supports it",
                "company_hook": "offices in Zagreb HR",
                "usable": True, "why_this_lead": "fixture"})
        if "propose one operational problem" in low:
            return json.dumps({
                "signal_strength": "strong", "signal": "offices in Zagreb HR",
                "business_model": "agency",
                "operational_complexity": "multi-office",
                "role_family": "executive",
                "hypothesis": "margin is only visible after the month closes",
                "hypothesis_basis": "offices in Zagreb HR",
                "qualification": "QUALIFIED_RICH", "confidence": 0.85})
        if "choose one productive capability" in low:
            return json.dumps({"capability_key": "profitability",
                               "why_this_one": "matches the hypothesis",
                               "what_changes": "margin becomes visible",
                               "runner_up": "budgeting", "confidence": 0.8})
        # The strategy call. It only has to parse.
        return json.dumps({})




CASSETTES = os.path.join(FIXTURES, "cassettes")

# What `tests/fixtures/cassettes/bison.json` answers `GET /users` with, and
# therefore which checkpoint slot a fixture poll of EmailBison reads and
# writes. Fictional on purpose: a fixture must exercise the identity read
# without stating a real client's workspace id.
FIXTURE_WORKSPACE = {"id": 99, "name": "Fixture Workspace"}
FIXTURE_SCOPE = "ws%d" % FIXTURE_WORKSPACE["id"]

# The ContactOut routes that may be reached with POST. ONE definition, read by
# both guards that assert it - `test_providers.TestNoSendPathExists` and
# `test_invariants.TestNothingCanSend`.
#
# It lives HERE, in the test tree, and deliberately not beside
# `contactout.ROUTES`: a guard that reads its allowlist from the module it is
# guarding passes whatever that module does, which is not a guard. But two
# independent COPIES are not the answer either. On 2026-09-22 `c56800ae`
# established that `POST /company/search` is a paid search rather than a write
# and added it to the `test_invariants` copy. The `test_providers` copy was
# not touched, and that guard has been RED ever since - on master as well as
# here. Two places that know one fact are two places that can disagree, and
# this pair did, for a day, with a "nothing can send" test carrying the
# disagreement.
CONTACTOUT_READ_ONLY_ROUTES = frozenset({
    "/people/count", "/people/search", "/domain/enrich", "/company/search",
})

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


#: The verbs a STAGING run performs. Deliberately not every verb there is:
#: `EMAIL_ACTIVATE` is absent, so a fixture that activates a campaign still
#: has to say so, and `SETUP NEVER IMPLIES ACTIVATE` keeps its teeth here too.
FIXTURE_STAGING_OPERATIONS = (
    "bison.create_campaign", "bison.set_sequence", "bison.assign_sender",
    "bison.set_limits", "bison.pause", "bison.add_lead", "bison.stop_lead",
)


class StagingAuthority:
    """Mixin: the operator authorization a fixture staging run implies.

    TASK-566 made campaign-scoped authority a precondition of creating or
    attaching leads, and its default is REFUSE. Every test that drives
    `bisonfactory.stage(live=True)` is asserting something DOWNSTREAM of that
    authorization - what the copy says, what the lead variables carry, that
    two campaigns do not collide - so it states the authorization here rather
    than discovering a refusal from a layer it is not about.

    WHAT THIS DOES NOT DO, because it would hollow out the guard it works
    around:

      - it grants SETUP only, never ACTIVATE;
      - it names the staging verbs, not every verb;
      - it is opened per client, so a fixture reaching a client it did not
        name is still refused;
      - `tests/test_task566_campaign_scoped_authority.py` extends
        `unittest.TestCase` directly and therefore never gets this. Its
        `TheLeadFactoryRequiresAGrant` is the case that proves an
        UNauthorized `_ensure_leads` still refuses, and it has to keep
        failing when the guard is removed.

    The campaign is left UNBOUND. `bisonfactory` binds the grant to whatever
    campaign the run resolves, which is the real bootstrap path, so a fixture
    exercises it rather than routing around it.
    """

    #: The client slugs the staging fixtures actually use. `acme` is the
    #: factory fixtures' own tenant; `productive` is everything else's. A
    #: fixture reaching a client outside this list is still refused, which is
    #: the property worth keeping - not the length of the list.
    FIXTURE_CLIENTS = ("productive", "acme")

    def grant_staging_authority(self, *clients, operations=None):
        from src import executionscope

        grants = []
        for client in (clients or self.FIXTURE_CLIENTS):
            cm = executionscope.grant(
                client=client, provider="bison",
                purpose="test fixture staging",
                phase=executionscope.SETUP,
                operations=operations or FIXTURE_STAGING_OPERATIONS)
            grants.append(cm.__enter__())
            self.addCleanup(cm.__exit__, None, None, None)
        return grants


class QueueTest(StagingAuthority, unittest.TestCase):
    def setUp(self):
        self.grant_staging_authority()
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
        install_fixture(name, self.queue)
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


class ProviderTest(StagingAuthority, unittest.TestCase):
    def setUp(self):
        self.grant_staging_authority()
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


def write_as_another_process(recs):
    """Persist records through the active backend without save()'s merge.

    On jsonl, this is store._write. On sqlite, it's store._write_sqlite.
    One definition, because two places that know how to write are two places
    that can disagree, which is the whole hazard _current_records exists to close.

    Used by tests that simulate a second writer or construct fixture state
    directly. NOT for production writes - those go through save().
    """
    mode = store.backend()
    if mode == "sqlite":
        store._write_sqlite(recs)
    else:
        store._write(recs)


def refuse_writes():
    """Patch both backend writers to raise QueueLocked.

    Returns a callable that restores the originals. The refusal tests need
    this because patching store._write only fires on jsonl; under sqlite,
    save() calls _write_sqlite instead. Patching both ensures the refusal
    fires regardless of which backend is active.
    """
    originals = {}
    def refuse(*a, **kw):
        raise store.QueueLocked("another process has the queue")
    for name in ("_write", "_write_sqlite"):
        originals[name] = getattr(store, name)
        setattr(store, name, refuse)
    def restore():
        for name, fn in originals.items():
            setattr(store, name, fn)
    return restore


def install_fixture(name, queue_path=None):
    """Install a JSONL fixture into the active backend.

    Under jsonl, copies the file to queue_path (or the default queue path).
    Under sqlite, reads the JSONL and writes it to the DB, because store.load()
    reads from the DB, not the JSONL file.
    """
    src = os.path.join(FIXTURES, name)
    mode = store.backend()
    if mode == "sqlite":
        recs = store.read_jsonl(src)
        write_as_another_process(recs)
    else:
        target = queue_path or store.queue_path()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(src, target)


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
