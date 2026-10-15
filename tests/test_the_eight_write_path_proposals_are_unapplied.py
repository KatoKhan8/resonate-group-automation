"""Eight RED tests, one per write-path proposal from PILOTCAPS TASK 0030.

**EVERY TEST IN THIS MODULE IS EXPECTED TO FAIL TODAY.** A red name here is
not rot: it is the evidence that a proposed fix is needed, and it is the thing
that turns green when the operator orders that fix. Each test's own docstring
names its proposal number and carries the sentence "RED until the operator
orders the fix."

TASK 0030 closed the write-path question with eight proposals, each with its
cost, ranked, the prospect-facing one at the top. TASK 0080 writes the tests.
**Nothing in this module applies any of them.** The order below is 0030's own
ranked order.

    rank  proposal  what it closes
    0     P1        scripts/batch_activate.py:144 resumes a paused campaign
                    without re-checking suppression. PROSPECT-FACING.
    1     P4        the two unscoped allow_writes scopes authorise every
                    mutating route for the duration of the block
    2     P2        scripts/resume_487.py re-exercises a grant that is SPENT
    3     P6        scripts/probe_list_staging.py --stage2 writes to a list
                    BOUND to the production campaign
    4     P3        scripts/write_linkedin_lead_variables.py converts a gate
                    failure into an ungated transport write
    5     P5        the door-B bypass enumeration records THAT a call is
                    direct, not WHICH gate holds it
    6     P8        scripts/linkedin_activate.py:158-160 retries an
                    activation without its lead-count containment
    7     P7        providers.ProviderWriteRefused is not a ProviderError, so
                    a door-A refusal escapes the handler written for it

## WHY THESE DRIVE `main()` RATHER THAN READING SOURCE

CLAUDE.md: "Test behaviour, not the text of the source. Searching source for
words produces a test that fails when somebody writes a comment." Every test
here that can be behavioural drives the real entry point with the real guards
in place and asserts on what the provider write verb received. The provider
verbs are replaced by spies, so the assertion is "this verb was reached with
these arguments", which is the property, not the spelling.

P5 is the one exception and it is a deliberate one, named in the report: P5's
applied form is itself a test, and a test cannot make another test go green.
What is asserted instead is the registry property P5's cost line states - the
enumeration must name the gate that holds each declared direct call - which is
red today and green the moment that field exists.

## WHAT THESE TESTS PIN, AND WHY THAT IS NOT CHEATING

Several of the scripts gate their live path on conditions that are not what
the test is about - a sending window against the wall clock, a seat's auth at
the provider, an approved-copy lookup over the production estate. Those are
stubbed, following `tests/base.fixture_config`'s own precedent: pin what the
test is not about, so a clock or a client config cannot turn the suite red.
Each stub says in a comment what it is standing in for. Nothing that gates
the WRITE is stubbed - the door-A scope, the killswitch, the suppression
revalidation and the signature checks all run for real.
"""
import importlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import campaigns, providers, store                        # noqa: E402
from tests.base import ProviderTest                                # noqa: E402
from tests.campaignbase import CampaignTest                        # noqa: E402

#: `scripts/batch_linkedin_reconcile.py` does `import batch_linkedin_push`,
#: a sibling-as-toplevel import, so `scripts/` has to be importable as a
#: directory and not only as a package. Registered once at module import and
#: left alone: removing it in a cleanup would break a second test in the same
#: process that had already resolved the sibling.
#:
#: THIS IS PROCESS-WIDE AND THAT WAS MEASURED RATHER THAN ARGUED, because a
#: path entry that outlives the module could change another test's answer and
#: pollute the next lane's baseline. Of the 298 modules under `scripts/`,
#: exactly one name - `funnel` - collides with anything, and it collides with
#: `src/funnel.py`, which is only ever imported as `src.funnel`. Nothing
#: collides with the standard library or with an installed distribution, and
#: the entry is APPENDED, so any name importable from elsewhere still wins.
#: Five test modules already do the riskier `sys.path.insert(0, scripts)`, so
#: `scripts/` is on the path during a full run whatever this file does.
_SCRIPTS = os.path.join(ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)


def script(name):
    """Import `scripts/<name>.py`, or None when the file is not there.

    THE `None` BRANCH IS THE POINT FOR P2 AND P6. Both propose DELETING a
    script, and the property each test asserts is "no runnable path in this
    repository can do X". A module that does not exist cannot do X, so an
    absent module satisfies the property and the test passes. That is the
    only honest way to write a test that a deletion turns green.
    """
    try:
        return importlib.import_module("scripts.%s" % name)
    except ImportError:
        return None


class _Patch(object):
    """`setattr` with an `addCleanup`-registered restore, absence included."""

    @staticmethod
    def attr(test, obj, name, value):
        missing = object()
        was = getattr(obj, name, missing)
        if was is missing:
            test.addCleanup(lambda: delattr(obj, name))
        else:
            test.addCleanup(setattr, obj, name, was)
        setattr(obj, name, value)


class _PinEnv(object):
    """One environment variable, restored to exactly what was there."""

    def _pin_env(self, name, value):
        was = os.environ.get(name)

        def restore():
            if was is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = was

        self.addCleanup(restore)
        os.environ[name] = value


# ---------------------------------------------------------------------------
# rank 0 - P1 - PROSPECT-FACING
# ---------------------------------------------------------------------------

class TheActivateScriptMustRevalidateSuppression(CampaignTest):
    """P1: route `scripts/batch_activate.py:144` through `providerwrites.perform`.

    This is the one that goes top regardless of effort. `bison.resume_campaign`
    restarts a paused sequence in front of people. TASK-331 added the
    EMAIL_RESUME CONDITIONAL on 2026-09-26 for exactly that reason - 76
    recipients are suppressed from the 2026-09-23 blank-email incident and a
    resume was restarting without re-checking that set - and skipping
    `perform` skips the CONDITIONAL.
    """

    def test_p1_a_resume_does_not_restart_a_campaign_holding_a_suppressed_contact(self):
        """P1. RED until the operator orders the fix.

        The property: the EmailBison resume verb is not reached for a campaign
        whose own records hold an unsubscribed contact. Nothing here asserts
        that `perform` is called - routing through `perform` is one way to
        satisfy the property and the test does not care which way is chosen.
        """
        batch_activate = script("batch_activate")
        self.assertIsNotNone(batch_activate, "scripts/batch_activate.py is gone")

        records = self.seed_records()
        campaign = self.make_campaign(
            records, campaign_id="productive-email-batch1-suppressed")
        # `check()` reads `senders.email[].provider_account_id`; the base
        # fixture writes `id`, which is a different field.
        campaign["senders"] = {"email": [{"provider_account_id": "2736",
                                          "daily_limit": 40}]}
        self.save_campaign(campaign)

        # The suppression this resume must see. `unsubscribed` on a contact is
        # one of the terminal states `eligibility` treats as BLOCKED FOREVER.
        records[0]["contacts"][0]["unsubscribed"] = True
        store.save(records)

        resumed = []
        bison = batch_activate.bison
        # Stubs for the two hard stops this test is not about: mailbox bounce
        # rate and the bounced-while-unsent contradiction. Both are made to
        # PASS, so the only thing left that can stop the write is suppression.
        _Patch.attr(self, bison, "sender_emails", lambda *a, **k: ([
            {"id": "2736", "emails_sent_count": 400, "bounced_count": 0}], 1))
        _Patch.attr(self, bison, "campaign", lambda cid: {
            "status": "paused", "total_leads": 2, "emails_sent": 5,
            "bounced": 0, "unsubscribed": 0})
        _Patch.attr(self, bison, "scheduled_emails", lambda cid: [])
        _Patch.attr(self, bison, "resume_campaign",
                    lambda *a, **k: resumed.append((a, k)) or {
                        "status": "active"})
        # The report is written to `<ROOT>/work/`, which is the real one.
        _Patch.attr(self, batch_activate, "ROOT", tempfile.mkdtemp(
            prefix="rga-p1-"))
        os.makedirs(os.path.join(batch_activate.ROOT, "work"), exist_ok=True)

        batch_activate.main(["--live"])

        self.assertEqual(
            [], resumed,
            "scripts/batch_activate.py --live resumed a campaign holding an "
            "unsubscribed contact: %r. The resume verb restarts a paused "
            "sequence in front of people and this path does not re-check the "
            "suppression set. P1 routes it through providerwrites.perform, "
            "whose EMAIL_RESUME CONDITIONAL refuses and names the count."
            % (resumed,))


# ---------------------------------------------------------------------------
# rank 1 - P4
# ---------------------------------------------------------------------------

class AWriteScopeMustNotAuthoriseEveryRoute(ProviderTest):
    """P4: add `only=` to the two unscoped `allow_writes` scopes.

    `allow_writes.__doc__`: "Without `only`, a scope authorises EVERY mutating
    route for the duration of the block. That is narrow in time and wide in
    power: a function you believe only stops a lead is one refactor away from
    also pausing the campaign, and the scope would have permitted it silently."
    """

    #: A real EmailBison resume route. The reconcile script has no business
    #: holding authority over this one - its own scope reason says so, in
    #: words: "no creates, no activation".
    EMAIL_RESUME_ROUTE = ("https://api.emailbison.com/api/campaigns/487"
                          "/resume-campaign")

    def test_p4_a_linkedin_sequence_scope_does_not_authorise_an_email_resume(self):
        """P4. RED until the operator orders the fix.

        The property: while `batch_linkedin_reconcile --live` holds its write
        scope, the process does NOT hold authority to resume an EmailBison
        campaign. Measured from inside the block, through the same
        `providers.writes_allowed` the transport itself consults, so this is
        the authority the socket would see and not a reading of the source.
        """
        reconcile = script("batch_linkedin_reconcile")
        self.assertIsNotNone(
            reconcile, "scripts/batch_linkedin_reconcile.py is gone")

        authority_inside = []

        def probe_set_sequence(campaign_id, graph):
            authority_inside.append(
                providers.writes_allowed(self.EMAIL_RESUME_ROUTE))
            return {"ok": True}

        # One campaign that needs a sequence, so the body of the scope runs.
        # `provider_state` is a pure provider read and is what this test is
        # not about.
        _Patch.attr(self, reconcile, "provider_state",
                    lambda: ({"seat-1": {"id": 7001}}, {}))
        _Patch.attr(self, reconcile.heyreach, "campaign_sequence",
                    lambda cid: None)
        _Patch.attr(self, reconcile.build, "standard_graph",
                    lambda: {"nodeType": "SEND_CONNECTION_REQUEST"})
        _Patch.attr(self, reconcile.heyreach, "set_sequence",
                    probe_set_sequence)
        # The write-back pass after the scope reads `work/senders.jsonl`,
        # which no worktree has. Not what this test is about.
        _Patch.attr(self, reconcile.build, "attested_seats", lambda: [])
        _Patch.attr(self, reconcile.time, "sleep", lambda seconds: None)

        reconcile.main(["--live"])

        self.assertEqual(
            1, len(authority_inside),
            "the probe never ran inside the scope, so nothing was measured")
        allowed, why = authority_inside[0]
        self.assertFalse(
            allowed,
            "while scripts/batch_linkedin_reconcile.py --live held its write "
            "scope, the process ALSO held authority to resume an EmailBison "
            "campaign: %s. The scope's own reason says 'no creates, no "
            "activation'. P4 adds only= so the authority matches the job."
            % (why,))


# ---------------------------------------------------------------------------
# rank 2 - P2
# ---------------------------------------------------------------------------

class ASpentGrantMustNotBeExercisedTwice(ProviderTest):
    """P2: delete `scripts/resume_487.py`.

    CLAUDE.md: "487 WAS RESUMED AND RECOVERED on 2026-09-21T09:06Z ... That
    grant is now SPENT: do not resume 487 again under any outcome." And the
    campaign has since been paused by hand by the operator on 2026-09-28,
    whose recorded reason is old copy, no signature, no opt-out route.
    """

    def test_p2_no_runnable_path_resumes_campaign_487(self):
        """P2. RED until the operator orders the fix.

        The property: no runnable path in this repository resumes campaign
        487. Deleting the script satisfies it; so would a spent-grant check.
        The test does not care which.

        The five authorization conditions are stubbed to PASS. They are not
        what this test is about - one of them reads the wall clock, which must
        never decide a suite - and stubbing them is what exposes the thing
        that IS missing: nothing on this path asks whether the grant has
        already been used.
        """
        resume_487 = script("resume_487")
        if resume_487 is None:
            return  # deleted. There is no runnable path. The property holds.

        resumed = []
        _Patch.attr(self, resume_487, "window_gate", lambda: None)
        _Patch.attr(self, resume_487, "copy_gate", lambda: None)
        _Patch.attr(self, resume_487, "truth_gate", lambda bison: (
            {"status": "paused"}, {"sending_paused": 10}, {"timezone": "UTC"}))
        _Patch.attr(self, resume_487, "_setup_data_access", lambda: None)
        _Patch.attr(self, resume_487, "membership_of",
                    lambda bison: ([], {"in_sequence": 10}))
        _Patch.attr(self, resume_487, "verdict", lambda after: "RECOVERED")

        from src.providers import bison as bison_module
        _Patch.attr(self, bison_module, "resume_campaign",
                    lambda *a, **k: resumed.append((a, k)) or {
                        "status": "active"})
        _Patch.attr(self, bison_module, "campaign",
                    lambda cid: {"status": "active"})

        resume_487.main(["--live"])

        self.assertEqual(
            [], resumed,
            "scripts/resume_487.py --live resumed campaign 487: %r. The grant "
            "was spent on 2026-09-21 and the campaign was paused by the "
            "operator on 2026-09-28. Nothing on this path asks whether the "
            "grant has already been used. P2 deletes the script."
            % (resumed,))


# ---------------------------------------------------------------------------
# rank 3 - P6
# ---------------------------------------------------------------------------

class NoRunnablePathFillsABoundList(CampaignTest):
    """P6: delete `scripts/probe_list_staging.py`.

    Its own `--stage2` help text: "If a list write activates its campaign,
    this sends a real connection request." The question it was written to
    answer has been answered and the answer lives in `src/liststaging.py`.
    """

    def test_p6_no_runnable_path_adds_a_lead_to_a_bound_list(self):
        """P6. RED until the operator orders the fix.

        The property: no runnable path adds a lead to a HeyReach list that is
        bound to a production campaign. A bound list is the one place where a
        list write can put a real person in front of a connection request.
        """
        probe = script("probe_list_staging")
        if probe is None:
            return  # deleted. There is no runnable path. The property holds.

        records = self.seed_records()
        campaign = self.make_campaign(records, campaign_id=probe.CAMPAIGN)
        campaign["heyreach_campaign_id"] = "605732"
        campaign["heyreach_list_id"] = 944355
        self.save_campaign(campaign)

        written = []
        state = {"status": "DRAFT", "leads": 3,
                 "stats": {"connectionsSent": 0, "uniqueLeadsContacted": 0}}
        # The approved-copy lookup over the production estate, and the
        # campaign-state reader. Neither is what this test is about.
        _Patch.attr(self, probe, "_one_approved_contact", lambda config: {
            "record_id": "acme", "contact_key": "acme-champ",
            "slug": "acme-champ",
            "linkedin_url": "https://www.linkedin.com/in/acme-champ",
            "first_name": "Champ", "last_name": "Acme", "custom_fields": {}})
        _Patch.attr(self, probe, "_campaign_state", lambda pid: dict(state))
        _Patch.attr(self, probe.heyreach, "create_list",
                    lambda name: {"id": 999999, "campaignIds": []})
        _Patch.attr(self, probe.heyreach, "list_leads", lambda list_id: (
            [{"profile_url": "https://www.linkedin.com/in/acme-champ"}], 1))
        _Patch.attr(self, probe.heyreach, "add_leads_to_list",
                    lambda list_id, leads: written.append(
                        (list_id, leads)) or {"ok": True})

        probe.main(["--live", "--stage2"])

        bound = [row for row in written if str(row[0]) == "944355"]
        self.assertEqual(
            [], bound,
            "scripts/probe_list_staging.py --live --stage2 added a lead to "
            "list 944355, which is BOUND to production campaign 605732: %r. "
            "Its own help text says a list write that activates its campaign "
            "sends a real connection request. P6 deletes the script."
            % (bound,))


# ---------------------------------------------------------------------------
# rank 4 - P3
# ---------------------------------------------------------------------------

class AGateFailureIsNotAnUngatedRetry(CampaignTest):
    """P3: retire `scripts/write_linkedin_lead_variables.py`.

    CLAUDE.md: "No silent fallbacks on a safety path." This is that rule in
    its most literal form - an `except TypeError` handler that converts a
    gate's signature refusal into a direct, ungated transport write. It is not
    a fallback: `liststaging.stage_lead` takes no `allow_restage`, so the
    handler fires on EVERY call and the gated branch has never once run.
    """

    def test_p3_a_refused_staging_call_is_not_retried_through_the_bare_transport(self):
        """P3. RED until the operator orders the fix.

        The property: when `liststaging.stage_lead` refuses a write, the
        transport underneath it is not called anyway. `stage_lead` runs for
        real - the refusal under test is its own, not a fabricated one.
        """
        writer = script("write_linkedin_lead_variables")
        if writer is None:
            return  # retired. There is no runnable path. The property holds.

        direct = []
        planned_row = {
            "hash": "4684b25b0372",
            "linkedin_url": "https://www.linkedin.com/in/someone",
            "first_name": "Some", "last_name": "One",
            "custom_fields": {"li1_message": "hello"}}
        # `planned()` walks the production estate for approved copy and
        # `provider_fields()` is a provider read. Neither is what this test is
        # about. `liststaging.stage_lead` is NOT stubbed.
        _Patch.attr(self, writer, "planned", lambda: ([planned_row], []))
        _Patch.attr(self, writer, "provider_fields", lambda: {})
        _Patch.attr(self, writer.heyreach, "campaign_read",
                    lambda pid: {"status": "DRAFT"})
        _Patch.attr(self, writer.heyreach, "add_leads_to_list",
                    lambda list_id, leads: direct.append(
                        (list_id, leads)) or {"ok": True})

        writer.main(["--live"])

        self.assertEqual(
            [], direct,
            "liststaging.stage_lead refused the call and "
            "scripts/write_linkedin_lead_variables.py called "
            "heyreach.add_leads_to_list anyway: %r. The except TypeError "
            "handler fires on every call, so every --live write this script "
            "has ever made went around the staging gate. P3 retires it."
            % (direct,))


# ---------------------------------------------------------------------------
# rank 5 - P5
# ---------------------------------------------------------------------------

class EveryDeclaredDirectCallNamesItsHoldingGate(unittest.TestCase):
    """P5: the boundary test the operator asked for.

    `tests/test_write_surface_enumeration.py` records THAT a factory write is
    direct. It does not record WHICH gate holds it, and the measurement that
    proves the gap is this: `bison.create_lead` and `bison.attach_leads` are
    `facing=True`, their only killswitch is six lines in
    `src/bisonfactory.py`, and deleting those six lines turns no test red.

    This is the one proposal of the eight whose applied form is itself a test,
    so it cannot be tested behaviourally - a test cannot make another test go
    green. What is asserted is the registry property P5's own cost line
    states, which is red today and green the moment the field exists.
    """

    def test_p5_each_declared_direct_call_names_the_gate_that_holds_it(self):
        """P5. RED until the operator orders the fix.

        The property: for every write that is declared to bypass
        `providerwrites.perform`, the enumeration names a gate that holds it.
        An undeclared gate is a bypass nobody can audit, which is what the
        enumeration exists to prevent and is the half of the job it does not
        yet do.
        """
        enumeration = importlib.import_module(
            "tests.test_write_surface_enumeration")
        declared = enumeration._DECLARED_DIRECT_CALLS
        gates = getattr(enumeration, "_DECLARED_DIRECT_CALL_GATES", None)

        ungated = []
        for filename, calls in sorted(declared.items()):
            for call in sorted(calls):
                named = (gates or {}).get((filename,) + tuple(call))
                if not (named and str(named).strip()):
                    ungated.append("%s %s.%s" % ((filename,) + tuple(call)))

        self.assertEqual(
            [], ungated,
            "%d declared direct provider write(s) name no holding gate: %s. "
            "The enumeration records THAT the call bypasses "
            "providerwrites.perform and not WHICH gate holds it, so the six "
            "lines in src/bisonfactory.py that are the only killswitch on "
            "bison.create_lead and bison.attach_leads can be deleted with no "
            "test going red. P5 adds the field."
            % (len(ungated), ungated))


# ---------------------------------------------------------------------------
# rank 6 - P8 (the rank-6 row of 0030's table, which carries no P number)
# ---------------------------------------------------------------------------

class AContainmentArgumentIsNotDroppedOnRetry(ProviderTest):
    """P8: delete `scripts/linkedin_activate.py:158-160`.

    `expect_leads` is the brake: the verb refuses when the provider's own lead
    count disagrees with what was planned. Lines 158-160 catch the TypeError
    the gated call can raise and retry WITHOUT it, so the retry activates a
    campaign whose lead count nobody checked.
    """

    def test_p8_an_activation_is_not_retried_without_its_lead_count_containment(self):
        """P8. RED until the operator orders the fix.

        The property: the HeyReach activation verb is never called without
        `expect_leads`. The TypeError is induced at the verb, which is the
        exact condition the handler was written for, so what is measured is
        the handler's behaviour.
        """
        activate = script("linkedin_activate")
        self.assertIsNotNone(activate, "scripts/linkedin_activate.py is gone")

        calls = []

        def spy(campaign_id, **kwargs):
            calls.append(kwargs)
            if "expect_leads" in kwargs:
                # What the handler at :158 was written to absorb.
                raise TypeError(
                    "activate_campaign() got an unexpected keyword argument "
                    "'expect_leads'")
            return {"status": "IN_PROGRESS"}

        wanted = tempfile.mkdtemp(prefix="rga-p8-")
        path = os.path.join(wanted, "linkedin-batch-campaigns.json")
        with io.open(path, "w", encoding="utf-8") as handle:
            json.dump([{"id": 604869, "seat": "2736"}], handle)
        _Patch.attr(self, activate, "CAMPAIGNS", path)
        # Seat auth and list occupancy at the provider: reads, and not what
        # this test is about. Both made to PASS so the activation is reached.
        _Patch.attr(self, activate, "seat_health", lambda: {
            "2736": {"auth": True, "active": True, "in_campaigns": 2}})
        _Patch.attr(self, activate, "list_counts", lambda: {"2736": 7})
        _Patch.attr(self, activate.heyreach, "activate_campaign", spy)
        # The post-activation readback. Left unstubbed it costs the suite
        # thirty seconds of `retry` against a cassette that has no entry, and
        # it writes a report into the real `work/`.
        _Patch.attr(self, activate.heyreach, "campaign_by_id",
                    lambda cid: {"status": "IN_PROGRESS"})
        _Patch.attr(self, activate.heyreach, "campaign_stats", lambda cid: {})
        _Patch.attr(self, activate, "ROOT", wanted)
        os.makedirs(os.path.join(wanted, "work"), exist_ok=True)
        _Patch.attr(self, activate.time, "sleep", lambda seconds: None)

        activate.main(["--live"])

        bare = [kwargs for kwargs in calls if "expect_leads" not in kwargs]
        self.assertEqual(
            [], bare,
            "scripts/linkedin_activate.py --live retried the activation "
            "without expect_leads: %r of %r calls. expect_leads is the "
            "lead-count containment and the retry drops it, so a campaign "
            "whose provider-side count nobody checked was started. P8 deletes "
            "the retry." % (bare, calls))


# ---------------------------------------------------------------------------
# rank 7 - P7
# ---------------------------------------------------------------------------

class ADoorARefusalIsCaughtByTheHandlerWrittenForIt(_PinEnv, ProviderTest):
    """P7: `providers.ProviderWriteRefused` must be a `providers.ProviderError`.

    `make_481_inert.py` is a SAFETY script - it can only ever reduce what
    somebody receives - and it is written to report a provider-layer refusal
    as an exit code with the partial state named. Its two handlers catch
    `ProviderError`. `ProviderWriteRefused.__mro__` runs straight to
    `RuntimeError`, so door A's refusal is not a `ProviderError` and escapes
    both of them.
    """

    def test_p7_a_refused_stop_is_reported_rather_than_escaping(self):
        """P7. RED until the operator orders the fix.

        The property: when door A refuses the stop, the script reports it and
        exits non-zero. It does not raise out of `main`, because the second
        refusal can arrive AFTER the canary stop has landed and a traceback
        leaves nobody told which rows are converted.

        Door A does the refusing for real. No write verb is stubbed: the
        script opens no `allow_writes` scope and no `RESONATE_PROVIDER_WRITES`
        is set, so `refuse_unauthorized_write` raises, which is the production
        condition.

        DOOR A HAS TO BE PUT BACK AT THE SEAM FIRST, and that is a finding in
        its own right. `refuse_unauthorized_write` is called from exactly one
        place - the first line of `providers._urllib_transport` - so every
        test that swaps the transport for a cassette, which is every
        `ProviderTest` in this suite, silently removes the write door. The
        transport installed below calls it on the same first line the wire
        does, so what refuses here is door A itself and not a stand-in.
        """
        inert = script("make_481_inert")
        self.assertIsNotNone(inert, "scripts/make_481_inert.py is gone")

        def door_a_at_the_seam(method, url, headers, body, timeout):
            providers.refuse_unauthorized_write(method, url)
            raise AssertionError(
                "door A permitted %s %s; this test needs it to refuse"
                % (method, url))

        previous = providers.set_transport(door_a_at_the_seam)
        self.addCleanup(providers.set_transport, previous)
        # A refusal APPENDS to `<ROOT>/work/provider-write-refusals.jsonl`,
        # which is the real one. This is the only test in the suite that
        # reaches door A, so it is the only one that has to say where.
        self._pin_env("PROVIDER_WRITE_REFUSALS", os.path.join(
            tempfile.mkdtemp(prefix="rga-p7-"),
            "provider-write-refusals.jsonl"))

        rows = {str(1000 + n): "sending_paused" for n in range(9)}

        def membership(campaign_id, lead_ids=None):
            # `bison.stop_lead` consults this itself for its own blast-radius
            # sample, with `lead_ids` named - so the stub has to carry the
            # real signature or the refusal under test never gets reached.
            if int(campaign_id) == inert.DORMANT:
                answer = dict(rows)
            elif int(campaign_id) == inert.LIVE:
                # The nine must be 487's live cohort or the script refuses
                # as stale. Not what this test is about.
                answer = {lead: "in_sequence" for lead in rows}
            else:
                answer = {}
            if lead_ids is None:
                return answer
            # Keyed by int in this form, exactly as the real reader is, or
            # `stop_lead`'s own absent-lead check fires FIRST and the test
            # passes on a refusal that is not the one under test.
            named = {int(lead_id) for lead_id in lead_ids}
            return {int(lead): status for lead, status in answer.items()
                    if int(lead) in named}

        _Patch.attr(self, inert.bison, "membership", membership)
        # The two reads `stop_lead` takes before the socket: the denominator
        # for its blast-radius sample, and the sample itself. Reads, and not
        # what this test is about.
        _Patch.attr(self, inert.bison, "campaign_lead_count",
                    lambda campaign_id: len(rows))
        _Patch.attr(self, inert.bison, "_sample",
                    lambda campaign_id: {})

        try:
            code = inert.main(["--live"])
        except Exception as escaped:                            # noqa: BLE001
            self.fail(
                "a door-A refusal escaped make_481_inert.main as an "
                "unhandled %s: %s. The script's handlers catch ProviderError "
                "and ProviderWriteRefused is not one, so a safety script "
                "aborts with a traceback instead of naming which rows are "
                "converted. P7 makes ProviderWriteRefused a ProviderError."
                % (type(escaped).__name__, escaped))

        self.assertNotEqual(
            0, code,
            "the refusal was neither raised nor reported: main returned 0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
