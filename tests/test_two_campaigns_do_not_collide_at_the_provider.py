"""Multi-campaign operation, and the five ways it was not idempotent.

Every behaviour asserted here was measured against the live EmailBison estate
on 2026-09-13 with throwaway campaigns and throwaway leads at
resonategroup.co, and `tests/fakebison.py` models what was observed. The five
attacks, and what each one found:

  TWO CAMPAIGNS FOR ONE CLIENT, STAGED AT THE SAME TIME. Failed. The loser of
  the race hit two different walls: the provider refused to attach a lead the
  winner had just created (see below), and then refused to find that lead by
  address because its search index runs about a second behind creation, so the
  run stopped as AMBIGUOUS. Both are fixed here.

  A BINDING TO A DELETED CAMPAIGN. Survived, but only at the end of the
  deletion. `DELETE /campaigns/{id}` is asynchronous: it answers 200 "queued
  for deletion", the campaign keeps answering GET with status
  `pending deletion` for a second or two, and only then becomes a 404. Staging
  during that window wrote a cap, a schedule, a sequence and a set of leads
  into a campaign that was about to stop existing, and every readback in
  between looked correct.

  THE SAME PERSON IN TWO CAMPAIGNS - the one that matters for account-based
  work. A lead reads `in_sequence` the moment it is attached to a campaign
  that has not been stopped, DRAFT IS ENOUGH, and a lead that is in_sequence
  anywhere cannot be attached anywhere else. The refusal is a 422 that names
  no lead and no campaign, conflates three different facts - in another
  sequence, bounced, unsubscribed - and attaches NOBODY, so one held person
  empties a campaign of two hundred. The factory attached its leads and paused
  afterwards, which made every one of its own leads unattachable elsewhere for
  the length of a staging run. It pauses first now.

  A CRASH BETWEEN CREATE AND PERSIST. Failed. The module's docstring claimed
  this case "is reported as ambiguous rather than retried"; the code went
  straight to a second POST, and the provider accepted two campaigns with
  byte-identical names.

  A RESTART MID-STAGE. Survived cleanly, and still does.
"""
import unittest

from src import bisonfactory, campaigns, providers, providerwrites, store, workspaces
from src.providers import bison
from tests.base import ProviderTest
from tests.fakebison import FakeBison

CONFIG = {
    "name": "Fixture client",
    "sender": {"mode": "client_rep"},
    "email_sequence": {"title": "fixture cadence", "subject": "{SUBJECT}",
                       "body": "<p>{BODY}</p>", "wait_in_days": 3},
    "sending_window": {"days": ["monday", "tuesday"], "start": "09:00",
                       "end": "17:00", "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}

APPROVAL = {"by": "operator", "at": "2026-09-13T00:00:00+00:00",
            "fingerprint": "fixture"}


def record(rid, email, first="Ada", last="Byron", subject="a subject",
           body="a body"):
    key = f"{first}-{last}".lower()
    return {"id": rid, "company": f"Co {rid}", "domain": "example.test",
            "state": "approved",
            "contacts": [{"key": key, "name": f"{first} {last}",
                          "first_name": first, "last_name": last,
                          "title": "Operations Manager", "email": email,
                          "persona": "champion", "angle": "operations",
                          "verdict": "valid", "sendable": True,
                          "primary": True}],
            "cadence": {key: {"day1": {"channel": "email", "generated": True,
                                       "subject": subject, "body": body,
                                       "approval": dict(APPROVAL)}}}}


class FactoryTest(ProviderTest):
    """A factory run against a stateful EmailBison that never leaves here."""

    def setUp(self):
        super().setUp()
        # `ProviderTest` fills every credential variable with a placeholder,
        # BISON_BASE included, so the base has to be a URL again before any
        # path in it means anything. Restored by the base class.
        import os
        os.environ["BISON_BASE"] = "https://emailbison.invalid/api"
        self.bison = FakeBison()
        self.providers.set_transport(self.bison)
        # The workspace killswitch must be on for lead writes. `_ensure_leads`
        # consults `killswitch.workspace_state` before creating or attaching
        # any lead. The client used in this test is "acme".
        ws = workspaces.new_workspace("acme", "Acme", client="acme")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def estate(self, campaign_id="c1", name="A campaign", rids=("r1",),
               senders=(11,), records=None):
        store.save(list(records or [record(r, f"{r}@example.test")
                                    for r in rids]))
        row = campaigns.new_campaign(campaign_id, "acme", name)
        row["record_ids"] = list(rids)
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        row["senders"] = {"email": [{"provider_account_id": s} for s in senders],
                          "linkedin": []}
        rows = campaigns.load()
        rows.append(row)
        campaigns.save(rows)
        return row

    def stage(self, campaign_id="c1", config=None):
        return bisonfactory.stage(campaign_id, config=config or CONFIG,
                                  live=True, by="test")

    def creates(self):
        return [c for c in self.bison.calls if c == ("POST", "/campaigns")]


class TheSameSpecBuildsOneCampaign(FactoryTest):
    """One canonical campaign, one provider campaign. However it is reached."""

    def test_a_second_run_reuses_the_first_campaign(self):
        self.estate()
        first = self.stage()["provider"]["campaign_id"]
        second = self.stage()["provider"]["campaign_id"]
        self.assertEqual(first, second)
        self.assertEqual(len(self.creates()), 1)

    def test_a_campaign_created_and_never_recorded_is_recovered(self):
        """The crash between the POST and the persist.

        The provider holds a real campaign; the row is bound to nothing. A
        second POST is what used to happen, and it is what must not.
        """
        row = self.estate()
        ghost = self.bison.add_campaign(bisonfactory.provider_campaign_name(row))
        report = self.stage()
        self.assertEqual(report["provider"]["campaign_id"], ghost)
        self.assertTrue(report["provider"].get("recovered"))
        self.assertEqual(self.creates(), [])
        self.assertEqual(campaigns.require("c1")["bison_campaign_id"], ghost)

    def test_two_campaigns_under_that_name_is_ambiguous_not_a_choice(self):
        row = self.estate()
        name = bisonfactory.provider_campaign_name(row)
        self.bison.add_campaign(name)
        self.bison.add_campaign(name)
        with self.assertRaises(bisonfactory.FactoryAmbiguous):
            self.stage()
        self.assertEqual(self.creates(), [])

    def test_a_campaign_pending_deletion_is_not_recovered(self):
        """It is on its way out. Binding to it is binding to nothing."""
        row = self.estate()
        ident = self.bison.add_campaign(
            bisonfactory.provider_campaign_name(row))
        self.bison.campaigns[ident]["status"] = bison.PENDING_DELETION
        report = self.stage()
        self.assertNotEqual(report["provider"]["campaign_id"], ident)
        self.assertEqual(len(self.creates()), 1)


class TheNameIsIdentityAndTheFingerprintIsMaterial(FactoryTest):
    """Two different questions, and a name that answered the wrong one would
    rebuild the campaign every time a draft changed."""

    def test_the_name_carries_the_client_and_the_campaign_id(self):
        row = self.estate(campaign_id="uk-digital", name="UK Digital")
        name = bisonfactory.provider_campaign_name(row)
        self.assertIn("acme", name)
        self.assertIn("uk-digital", name)
        self.assertTrue(name.startswith("UK Digital"))

    def test_two_clients_may_use_the_same_human_name(self):
        a = campaigns.new_campaign("q4", "acme", "Q4 push")
        b = campaigns.new_campaign("q4", "borealis", "Q4 push")
        self.assertNotEqual(bisonfactory.provider_campaign_name(a),
                            bisonfactory.provider_campaign_name(b))

    def test_changing_the_material_moves_the_fingerprint(self):
        """The control. Without it the next test proves nothing."""
        row = self.estate()
        recs = store.load()
        before = campaigns.fingerprint(row, recs=recs, config=CONFIG)
        row["daily_volume"] = {"email": 9, "linkedin": 0}
        self.assertNotEqual(
            campaigns.fingerprint(row, recs=recs, config=CONFIG), before)

    def test_changing_the_material_does_not_move_the_name(self):
        """So a regenerated draft reconciles the campaign it already built."""
        row = self.estate()
        before = bisonfactory.provider_campaign_name(row)
        row["daily_volume"] = {"email": 9, "linkedin": 0}
        row["senders"] = {"email": [{"provider_account_id": 77}], "linkedin": []}
        row["bison_campaign_id"] = 12345
        self.assertEqual(bisonfactory.provider_campaign_name(row), before)

    def test_a_regenerated_draft_still_reuses_the_same_campaign(self):
        """The property end to end, not just on the name function."""
        self.estate()
        first = self.stage()["provider"]["campaign_id"]
        recs = store.load()
        recs[0]["cadence"]["ada-byron"]["day1"]["subject"] = "rewritten"
        store.save(recs)
        self.assertEqual(self.stage()["provider"]["campaign_id"], first)
        self.assertEqual(len(self.creates()), 1)


class TheSequenceIsWrittenOnceOrNotAtAll(FactoryTest):
    """`POST .../sequence-steps` APPENDS and nothing can undo it.

    Measured 2026-09-13 on a throwaway campaign: one write left one step, a
    second left two, a third of two steps left four - renumbered 1, 3, 2, 4.
    `PUT` is 405 and no per-step route exists, so a campaign whose sequence
    was written twice sends twice, the older copy second, and the only remedy
    is deleting the campaign.
    """

    def steps(self, ident):
        return [s["email_subject"] for s in self.bison.sequences.get(ident, [])]

    def test_staging_twice_leaves_one_step(self):
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        self.stage()
        self.stage()
        self.assertEqual(self.steps(ident), ["{SUBJECT}"])

    def test_a_changed_sequence_refuses_instead_of_appending(self):
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        changed = dict(CONFIG, email_sequence=dict(
            CONFIG["email_sequence"], subject="something else"))
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage(config=changed)
        self.assertIn("APPENDS", str(caught.exception))
        self.assertEqual(self.steps(ident), ["{SUBJECT}"])

    def test_a_campaign_with_no_sequence_says_so_in_a_200(self):
        """Measured: `{"success": false, "message": "Sequence steps do not
        exist for <name>"}`, with a 200. Reading that shape as anything but
        "none" is what licenses writing into a route that only appends."""
        ident = self.bison.add_campaign("empty")
        self.assertEqual(bison.sequence_steps(ident), [])

    def test_an_unreadable_shape_is_not_read_as_no_sequence(self):
        ident = self.bison.add_campaign("weird")
        original = self.bison.route

        def nonsense(method, path, params, body):
            if path.endswith("/sequence-steps") and method == "GET":
                return 200, {"data": {"unexpected": True}}
            return original(method, path, params, body)

        self.bison.route = nonsense
        with self.assertRaises(providers.ProviderError):
            bison.sequence_steps(ident)

    def test_the_provider_would_have_appended(self):
        """The control. Without it the refusal above proves nothing about the
        provider, only about this code's opinion of it."""
        ident = self.bison.add_campaign("anything")
        bison.set_sequence(ident, "t", [{"order": 1, "email_subject": "A",
                                         "email_body": "a", "wait_in_days": 1}])
        bison.set_sequence(ident, "t", [{"order": 1, "email_subject": "B",
                                         "email_body": "b", "wait_in_days": 1}])
        self.assertEqual(self.steps(ident), ["A", "B"])

    def rebuild(self, clear_create_record):
        """Somebody deleted the provider campaign and wants it rebuilt."""
        first = self.stage()["provider"]["campaign_id"]
        del self.bison.campaigns[first]
        with campaigns.transaction() as rows:
            for row in rows:
                if row["campaign_id"] != "c1":
                    continue
                row["bison_campaign_id"] = None
                if clear_create_record:
                    (row.get("provider_staged") or {}).pop(
                        providerwrites.EMAIL_CREATE_CAMPAIGN, None)
        return first

    def test_a_rebuild_is_refused_until_the_staging_record_is_cleared(self):
        """`providerwrites` remembers that this row asked for a campaign with
        this material, and a second ask normally builds a second campaign. A
        human deleted the first one; a human clearing the record is the
        matching act, and it stays manual on purpose."""
        self.estate()
        self.rebuild(clear_create_record=False)
        with self.assertRaises(providerwrites.WriteRefused):
            self.stage()

    def test_and_then_the_rebuilt_campaign_gets_its_sequence(self):
        """The sequence record must not block it on its own. It did: the
        material was the title and the steps, so a new provider campaign
        holding no steps was refused the only words it could have."""
        self.estate()
        first = self.rebuild(clear_create_record=True)
        second = self.stage()["provider"]["campaign_id"]
        self.assertNotEqual(second, first)
        self.assertEqual(self.steps(second), ["{SUBJECT}"])

    def test_a_write_that_stored_nothing_is_not_a_success(self):
        """The read-back used to be the request compared to itself."""
        self.estate()
        original = self.bison.route

        def swallow(method, path, params, body):
            if path.endswith("/sequence-steps") and method == "POST":
                return 201, {"data": {"id": 1}}
            return original(method, path, params, body)

        self.bison.route = swallow
        with self.assertRaises(providerwrites.WriteUnverified):
            self.stage()
        ident = campaigns.require("c1")["bison_campaign_id"]
        self.assertEqual(self.steps(ident), [])


class AStaleBindingIsNotABinding(FactoryTest):
    def test_a_binding_the_provider_will_not_return_refuses(self):
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        del self.bison.campaigns[ident]
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.stage()
        self.assertEqual(len(self.creates()), 1)

    def test_a_binding_to_a_campaign_pending_deletion_refuses(self):
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        self.bison.campaigns[ident]["status"] = bison.PENDING_DELETION
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.stage()


class OnePersonCannotBeInTwoLiveSequences(FactoryTest):
    """The account-based case, and the ordering that decides whether it works."""

    def test_nobody_is_ever_attached_to_a_campaign_that_can_hold_them(self):
        """The invariant, not the call order.

        A lead in a campaign that has not been stopped reads `in_sequence`
        from the instant it is attached - draft is enough - and `in_sequence`
        anywhere makes it unattachable everywhere. The old order attached and
        then paused, so for the length of a staging run every lead in this
        campaign was hostile to every other campaign that needed one of them.
        """
        self.estate()
        self.stage()
        self.assertEqual(set(self.bison.attach_states), {"paused"})

    def test_a_run_that_left_a_campaign_unstopped_would_be_caught(self):
        """The control for the test above: with the same estate and the same
        assertion, an unstopped campaign is a different answer."""
        self.estate()
        ident = self.bison.add_campaign("by hand", status="draft")
        self.bison.members[ident] = []
        bison.attach_leads(ident, [self.bison.add_lead("x@example.test")])
        self.assertEqual(self.bison.attach_states, ["draft"])

    def test_two_stopped_campaigns_may_hold_the_same_person(self):
        shared = record("r1", "shared@example.test")
        self.estate(campaign_id="c1", rids=("r1",), records=[shared])
        self.estate(campaign_id="c2", name="Second", rids=("r1",),
                    records=[shared])
        one = self.stage("c1")["provider"]["campaign_id"]
        two = self.stage("c2")["provider"]["campaign_id"]
        self.assertNotEqual(one, two)
        self.assertEqual(self.bison.members[one], self.bison.members[two])
        self.assertEqual(len(self.bison.leads), 1)

    def test_a_person_already_in_sequence_refuses_and_says_who_holds_them(self):
        shared = record("r1", "shared@example.test")
        self.estate(campaign_id="c1", rids=("r1",), records=[shared])
        self.estate(campaign_id="c2", name="Second", rids=("r1",),
                    records=[shared])
        held = self.stage("c1")["provider"]["campaign_id"]
        # The first campaign is started by somebody else, the way a real one is.
        self.bison.campaigns[held]["status"] = "active"
        with self.assertRaises(bison.LeadsNotAttachable) as caught:
            self.stage("c2")
        message = str(caught.exception)
        self.assertIn("shared@example.test", message)
        self.assertIn(str(held), message)
        self.assertIn("in_sequence", message)

    def test_the_refusal_is_its_own_class_because_a_retry_cannot_fix_it(self):
        self.assertTrue(issubclass(bison.LeadsNotAttachable, providers.ProviderError))

    def test_it_does_not_claim_a_collision_it_did_not_find(self):
        """The provider's sentence also covers bounced and unsubscribed, and
        reporting those as a sequence collision would have a caller retrying a
        person it must never contact."""
        lead_id = self.bison.add_lead("nobody@example.test")
        ident = self.bison.add_campaign("target")
        message = bison._attach_refusal(ident, [lead_id], 422, {})
        self.assertIn("none found", message)
        self.assertIn("unsubscribed", message)


class ALeadCreatedInARaceIsFoundNotDuplicated(FactoryTest):
    """The other half of the concurrency failure: the search index lags."""

    def test_the_reconciliation_waits_for_the_index(self):
        self.bison.add_lead("shared@example.test")      # the winner's lead
        self.bison.search_lag_calls = 3                 # absent for three reads
        self.estate(rids=("r1",),
                    records=[record("r1", "shared@example.test")])
        report = self.stage()
        self.assertEqual(report["provider"]["leads"]["reconciled"], 1)
        self.assertEqual(len(self.bison.leads), 1)

    def test_a_lead_that_never_appears_still_stops_the_run(self):
        """Waiting is not the same as assuming. An address the provider says
        exists and will not return must not be guessed at."""
        self.bison.add_lead("shared@example.test")
        self.bison.search_lag_calls = 99
        self.estate(rids=("r1",),
                    records=[record("r1", "shared@example.test")])
        with self.assertRaises(bisonfactory.FactoryAmbiguous):
            self.stage()

    def test_one_read_is_still_the_default(self):
        """A caller that is not racing anything pays for one read."""
        self.bison.add_lead("someone@example.test")
        self.bison.search_lag_calls = 1
        self.assertIsNone(bison.find_lead_by_email("someone@example.test"))


class AWindowThatChangedMustBeWritten(FactoryTest):
    def test_narrowing_the_hours_is_not_already_correct(self):
        self.estate()
        self.stage()
        narrower = dict(CONFIG, sending_window=dict(
            CONFIG["sending_window"], end="12:00"))
        report = self.stage(config=narrower)
        self.assertNotIn("schedule already correct; unchanged", report["did"])
        ident = report["provider"]["campaign_id"]
        self.assertEqual(self.bison.schedules[ident]["end_time"], "12:00:00")

    def test_an_unchanged_window_writes_nothing(self):
        self.estate()
        self.stage()
        before = len(self.bison.calls)
        report = self.stage()
        self.assertIn("schedule already correct; unchanged", report["did"])
        self.assertNotIn(("PUT", f"/campaigns/"
                          f"{report['provider']['campaign_id']}/schedule"),
                         self.bison.calls[before:])

    def test_the_second_write_is_a_put_because_post_will_not_replace(self):
        ident = self.bison.add_campaign("anything")
        bison.set_schedule(ident, ["monday"], "09:00", "17:00", "UTC")
        self.assertIn(("POST", f"/campaigns/{ident}/schedule"), self.bison.calls)
        bison.set_schedule(ident, ["monday"], "09:00", "12:00", "UTC")
        self.assertIn(("PUT", f"/campaigns/{ident}/schedule"), self.bison.calls)
        self.assertEqual(self.bison.schedules[ident]["end_time"], "12:00:00")

    def test_a_two_hundred_that_wrote_nothing_is_not_a_success(self):
        """The POST-onto-an-existing-schedule trap, forced directly."""
        ident = self.bison.add_campaign("anything")
        bison.set_schedule(ident, ["monday"], "09:00", "17:00", "UTC")
        self.bison.schedules[ident]["start_time"] = "06:00:00"   # drifted
        original = self.bison.route

        def post_only(method, path, params, body):
            if path.endswith("/schedule") and method == "PUT":
                method = "POST"
            return original(method, path, params, body)

        self.bison.route = post_only
        with self.assertRaises(providers.ProviderError) as caught:
            bison.set_schedule(ident, ["monday"], "09:00", "17:00", "UTC")
        self.assertIn("wrote nothing", str(caught.exception))

    def test_the_hours_are_read_back(self):
        """A window that was asked for and not stored must not return.

        The provider here answers 200, says nothing about having ignored the
        hours, and keeps the old ones - which is what a schedule write that
        silently does not take looks like from this side.
        """
        ident = self.bison.add_campaign("anything")
        bison.set_schedule(ident, ["monday"], "09:00", "17:00", "UTC")
        original = self.bison.route

        def keep_the_old_hours(method, path, params, body):
            status, data = original(method, path, params, body)
            if path.endswith("/schedule") and method in ("POST", "PUT"):
                self.bison.schedules[ident]["end_time"] = "17:00:00"
            return status, data

        self.bison.route = keep_the_old_hours
        with self.assertRaises(providers.ProviderError) as caught:
            bison.set_schedule(ident, ["monday"], "09:00", "12:00", "UTC")
        self.assertIn("end_time", str(caught.exception))


class ResumeSaysWhetherItActuallyStarted(FactoryTest):
    """The one verb here that reaches a person, so an unknown is not a yes."""

    def ready(self):
        ident = self.bison.add_campaign("ready", status="paused")
        self.bison.members[ident] = [self.bison.add_lead("a@example.test")]
        return ident

    def test_active_is_started(self):
        ident = self.ready()
        self.assertEqual(bison.resume_campaign(ident, expect_leads=1)["status"],
                         "active")

    def test_failed_is_not_started(self):
        """Measured twice live: resume answers 200, the campaign reads
        `failed` seconds later, and nothing sends."""
        ident = self.ready()
        self.bison.resume_lands_on = "failed"
        with self.assertRaises(providers.ProviderError) as caught:
            bison.resume_campaign(ident, expect_leads=1)
        self.assertIn("NOT sending", str(caught.exception))

    def test_queued_that_never_resolves_is_not_started(self):
        ident = self.ready()
        self.bison.resume_lands_on = "queued"
        with self.assertRaises(providers.ProviderError) as caught:
            bison.resume_campaign(ident, expect_leads=1, attempts=2,
                                  interval=0)
        self.assertIn("UNKNOWN", str(caught.exception))

    def test_a_status_this_module_cannot_classify_is_refused(self):
        ident = self.ready()
        self.bison.resume_lands_on = "hibernating"
        with self.assertRaises(providers.ProviderError) as caught:
            bison.resume_campaign(ident, expect_leads=1, attempts=1)
        self.assertIn("cannot classify", str(caught.exception))

    def test_the_lead_count_guard_still_comes_first(self):
        ident = self.ready()
        self.bison.resume_lands_on = "active"
        with self.assertRaises(providers.ProviderError):
            bison.resume_campaign(ident, expect_leads=9)
        self.assertNotIn(("PATCH", f"/campaigns/{ident}/resume"),
                         self.bison.calls)


class FindingACampaignByNameReadsTheTable(FactoryTest):
    """Not the search index: the index is a second behind creation, and the
    whole point is finding something created a moment ago."""

    def test_it_walks_every_page(self):
        for i in range(37):
            self.bison.add_campaign(f"campaign {i}")
        wanted = self.bison.add_campaign("the one")
        found = bison.find_campaigns_by_name("the one")
        self.assertEqual([f["id"] for f in found], [wanted])

    def test_it_matches_the_whole_name_and_not_a_prefix(self):
        self.bison.add_campaign("Q4 push [acme/q4]")
        self.assertEqual(bison.find_campaigns_by_name("Q4 push"), [])

    def test_a_short_read_refuses_rather_than_reporting_an_absence(self):
        """An absence is what licenses creating a campaign."""
        self.bison.add_campaign("the one")
        original = self.bison.route

        def truncate(method, path, params, body):
            status, data = original(method, path, params, body)
            if path == "/campaigns" and method == "GET":
                data["data"] = []
            return status, data

        self.bison.route = truncate
        with self.assertRaises(providers.ProviderError) as caught:
            bison.find_campaigns_by_name("the one")
        self.assertIn("partial read", str(caught.exception))


class APageIsNotAMembership(FactoryTest):
    """The worst of what this run found, and none of it was multi-campaign.

    `GET /campaigns/{id}/leads` and `GET /campaigns/{id}/sender-emails` both
    IGNORE `per_page` and serve fifteen rows. Measured 2026-09-13: campaign
    352 asked for 200 answers fifteen, `meta.total: 21159`, `meta.last_page:
    1411`; its sender list answers fifteen and holds 222.

    Three reads believed the page. Each consequence is asserted below, and
    each was live: the per-lead STOP was unreachable for every campaign this
    agency runs, an attach past the first page raised on a write that had
    succeeded, and the resume guard - the one that stops a campaign reaching
    more people than the caller believes - could be satisfied by a page.
    """

    def big(self, members=3000, senders=59):
        ident = self.bison.add_campaign("big one", status="active")
        self.bison.members[ident] = [
            self.bison.add_lead(f"p{i}@example.test") for i in range(members)]
        self.bison.senders[ident] = list(range(1, senders + 1))
        return ident

    def test_a_member_on_a_later_page_is_still_a_member(self):
        """`leadstop.stop` refuses a lead `membership` cannot see, so this is
        the whole per-lead stop path."""
        ident = self.big(members=300)
        far = self.bison.members[ident][-1]
        self.assertEqual(bison.membership(ident, [far]),
                         {far: bison_in_sequence()})

    def test_stopping_a_lead_beyond_the_first_page_is_possible(self):
        ident = self.big(members=300)
        far = self.bison.members[ident][-1]
        out = bison.stop_lead(ident, [far], attempts=2, interval=0)
        self.assertEqual(out["stopped"], {far: "stopped"})
        self.assertEqual(out["sampled_of"], 300)

    def test_the_blast_radius_check_says_how_much_it_checked(self):
        """A bounded check that admits its bound, rather than a complete
        sounding one that never was."""
        ident = self.big(members=300)
        out = bison.stop_lead(ident, [self.bison.members[ident][0]],
                              attempts=2, interval=0)
        self.assertLess(len(out["untouched"]), out["sampled_of"])

    def test_attaching_to_a_campaign_past_its_first_page_succeeds(self):
        ident = self.big(members=100)
        self.bison.campaigns[ident]["status"] = "paused"
        fresh = self.bison.add_lead("new@example.test")
        out = bison.attach_leads(ident, [fresh])
        self.assertEqual(out["attached"], [fresh])
        self.assertEqual(out["count"], 101)

    def test_the_resume_guard_counts_the_campaign_not_the_page(self):
        ident = self.big(members=3000)
        self.bison.campaigns[ident]["status"] = "paused"
        self.assertEqual(bison.campaign_lead_count(ident), 3000)
        with self.assertRaises(providers.ProviderError) as caught:
            bison.resume_campaign(ident, expect_leads=15)
        # The exact sentence, because a refusal from somewhere else in the
        # call - a page walk giving up, say - would satisfy a looser one and
        # leave the guard itself untested.
        self.assertIn("holds 3000 lead(s) and the caller expected 15",
                      str(caught.exception))
        self.assertNotIn(("PATCH", f"/campaigns/{ident}/resume"),
                         self.bison.calls)

    def test_every_bound_sender_is_read_back(self):
        """`attach_senders` proves a bind by reading this, so a short read
        raises on a write that worked."""
        ident = self.big(senders=59)
        self.assertEqual(len(bison.campaign_senders(ident)), 59)

    def test_a_campaign_too_big_to_list_refuses_rather_than_truncating(self):
        ident = self.big(members=3000)
        with self.assertRaises(bison.PartialInventory) as caught:
            bison.campaign_lead_ids(ident)
        self.assertIn("campaign_lead_count", str(caught.exception))

    def test_a_campaign_small_enough_to_list_is_listed_whole(self):
        """The control: the refusal above is about size, not about failing."""
        ident = self.big(members=100)
        self.assertEqual(len(bison.campaign_lead_ids(ident)), 100)

    def test_the_pre_send_queue_is_the_queue_and_not_its_first_page(self):
        """`leadobserve.scheduled_rows` reads this to say what is about to go
        out. Campaign 352 holds 95,312 rows and answered fifteen."""
        ident = self.big(members=0)
        self.bison.queue[ident] = [{"id": i, "status": "scheduled"}
                                   for i in range(40)]
        self.assertEqual(len(bison.scheduled_emails(ident)), 40)

    def test_declared_variables_past_the_first_page_are_seen(self):
        """`ensure_custom_variables` decides what is MISSING from this, so a
        name on page two would be created again and refused."""
        for i in range(30):
            self.bison.variables.add(f"v{i:02d}")
        self.assertEqual(len(bison.custom_variables()), 30)
        self.assertEqual(bison.ensure_custom_variables(("v00", "v29"))["created"],
                         [])

    def test_the_factory_reports_the_campaign_size_not_a_page(self):
        self.estate(rids=tuple(f"r{i}" for i in range(20)),
                    records=[record(f"r{i}", f"p{i}@example.test",
                                    first=f"Ada{i}") for i in range(20)])
        report = self.stage()
        self.assertEqual(report["provider"]["readback"]["leads"], 20)


def bison_in_sequence():
    from tests.fakebison import FakeBison
    return FakeBison.IN_SEQUENCE


class TheFactoryStillCannotSend(FactoryTest):
    """None of the above may have widened what this module is allowed to do."""

    def test_the_write_routes_are_unchanged(self):
        self.assertEqual(set(bison.WRITE_ROUTES), {
            "/campaigns",
            "/campaigns/{campaign_id}/update",
            "/campaigns/{campaign_id}/sequence-steps",
            "/campaigns/{campaign_id}/leads/attach-leads",
            "/campaigns/{campaign_id}/pause",
            "/campaigns/{campaign_id}/resume",
            "/campaigns/{campaign_id}/leads/stop-future-emails",
            "/campaigns/{campaign_id}/schedule",
            "/campaigns/{campaign_id}/attach-sender-emails",
            "/leads",
            "/custom-variables",
        })

    def test_staging_never_resumes(self):
        self.estate()
        self.stage()
        self.assertEqual([c for c in self.bison.calls
                          if c[1].endswith("/resume")], [])

    def test_a_staged_campaign_is_left_paused(self):
        self.estate()
        report = self.stage()
        self.assertEqual(report["provider"]["readback"]["status"], "paused")

    def test_a_running_campaign_is_not_stopped_by_a_restage(self):
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        self.bison.campaigns[ident]["status"] = "active"
        report = self.stage()
        self.assertTrue(report["provider"].get("left_running"))
        self.assertEqual(self.bison.campaigns[ident]["status"], "active")

    def test_a_failed_campaign_is_not_reported_as_running(self):
        """`failed` is the provider saying it tried to start and gave up. It
        is not draft and not paused, and the old test divided the world into
        those two and "running"."""
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        self.bison.campaigns[ident]["status"] = "failed"
        report = self.stage()
        self.assertFalse(report["provider"].get("left_running"))
        self.assertTrue(report["provider"].get("provider_failed"))
        self.assertEqual(report["provider"]["readback"]["status"], "paused")

    def test_a_restage_does_not_rename_the_provider_campaign(self):
        """The cap route requires `name` in the same body, so writing a cap
        rewrites the name. A person who renamed it in the UI keeps their
        name."""
        self.estate()
        ident = self.stage()["provider"]["campaign_id"]
        self.bison.campaigns[ident]["name"] = "renamed by a human"
        self.stage()
        self.assertEqual(self.bison.campaigns[ident]["name"],
                         "renamed by a human")


if __name__ == "__main__":
    unittest.main()
