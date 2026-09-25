#!/usr/bin/env python3
"""Staging refuses a contact the client is already emailing.

THE DEFECT THIS PINS. On 2026-09-13, nineteen Productive contacts were staged
into EmailBison campaign 481. Nine were already in the client's own campaigns:

    142476  bounced             campaign 327
    199963  in_sequence         campaign 352
    144582  stopped             campaign 352, sequence_finished in 327
    173033  sequence_finished   campaign 352
    + five more sequence_finished across 327 and 352

Nothing objected. The provider caught five (bounced); the other nine attached.
`_ensure_leads` called `bison.create_lead` and `bison.attach_leads` directly,
bypassing `executionguard.authorize()` and every gate it runs.

WHAT THIS TESTS. The collision check uses `collision.check_account` and
`collision.account_policy` - the same gates executionguard runs at send time.
The account-level verdict decides:

  in_sequence      -> STOP  -> REFUSED at staging
  stopped          -> HOLD  -> REFUSED at staging
  bounced          -> HOLD  -> REFUSED at staging
  sequence_finished -> ALLOW -> passes (history, not a live conflict)

The last is deliberate: `account_policy` already says ALLOW for finished
campaigns with no reply. This module does not invent a new verdict.

ZERO LIVE PROVIDER CALLS. Campaign 481 holds fourteen leads, nine of them
deliberately `stopped`, and 451 is active with a scheduled send. Neither is
touched. The fake transport from `tests/fakebison.py` models the estate.
"""
import unittest
from unittest import mock

from src import bisonfactory, cadence, campaigns, collision, store, workspaces
from src import providers
from tests.base import QueueTest
from tests.fakebison import FakeBison, RendersTheQueue


CID = "collision-test"

CONFIG = {
    "email_sequence": {"title": "Resonate generated cadence",
                       "subject": "{SUBJECT}", "body": "<p>{BODY}</p>",
                       "wait_in_days": 3},
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
                       "start": "09:00", "end": "17:00",
                       "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}


def _record(rid, email, first, domain="example.com"):
    from src import approval as _approval

    key = f"{rid}-c1"
    # THE STAMP COVERS THE WORDS. It carried no fingerprint at all, which was
    # enough while staging checked only that an approval existed. It is not
    # any more - `bisonfactory._certified_copy` hashes the words it is about
    # to stage and compares - and an approval that records nothing about the
    # words it was given for is refused rather than trusted.
    step = {"channel": "email", "subject": f"Hello {first}",
            "body": "<p>A real approved body.</p>"}
    step["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                        "fingerprint": _approval.fingerprint(step)}
    return {"id": rid, "client": "productive", "domain": domain,
            "company": "Example", "state": "ready",
            "cadence": {key: {"day1": step}},
            "contacts": [{"key": key, "email": email,
                          "first_name": first, "last_name": "Tester",
                          "sendable": True, "verified": True}]}


class _EstateAwareFakeBison(FakeBison):
    """A FakeBison whose /leads search returns estate membership data.

    The collision module reads leads via `GET /leads?search=<term>` and walks
    every page, matching addresses locally. This fake populates the search
    result with `lead_campaign_data` so `collision.touches_of` can read the
    per-campaign status of each lead.

    THE ESTATE IS PRE-POPULATED. `seed_estate` adds leads with specific
    campaign memberships, modelling the nine real cases from campaign 481.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._estate_leads = {}
        self._membership_status = {}  # (campaign_id, lead_id) -> status

    def seed_estate(self, email, campaign_entries):
        """Add a lead to the estate with specific campaign memberships.

        `campaign_entries` is a list of dicts: {campaign_id, status,
        emails_sent, replies}. The campaign must already exist in the fake.
        """
        lid = self.add_lead(email)
        self._estate_leads[email.lower()] = lid
        for entry in campaign_entries:
            cid = entry["campaign_id"]
            if cid not in self.campaigns:
                self.campaigns[cid] = {
                    "id": cid, "name": f"client-campaign-{cid}",
                    "status": "paused",
                    "max_emails_per_day": 1000,
                    "max_new_leads_per_day": 1000}
                self.members[cid] = []
            if lid not in self.members.get(cid, []):
                self.members.setdefault(cid, []).append(lid)
            self._membership_status[(cid, lid)] = entry["status"]

    def _campaign_data(self, lead_id):
        """Override to include estate-seeded campaign data with statuses."""
        result = []
        for cid, ids in self.members.items():
            if lead_id not in ids or cid not in self.campaigns:
                continue
            status = self._membership_status.get((cid, lead_id))
            if status is None:
                status = self.member_status(cid, lead_id)
            if status is None:
                continue
            entry = {"campaign_id": cid, "status": status}
            result.append(entry)
        return result

    def _search_leads(self, params):
        """Override to return estate leads with full campaign data."""
        term = str(params.get("search") or "").strip().lower()
        self._searches[term] = self._searches.get(term, 0) + 1
        if self._searches[term] <= self.search_lag_calls:
            return 200, {"data": [], "meta": {"last_page": 1, "total": 0,
                                               "per_page": 15,
                                               "current_page": 1}}
        rows = []
        for row in self.leads.values():
            email = str(row.get("email") or "").lower()
            if term and term in email:
                rows.append(dict(
                    row,
                    overall_stats={"emails_sent": 5, "replies": 0, "opens": 1},
                    lead_campaign_data=self._campaign_data(row["id"])))
        return 200, {"data": rows, "meta": {"last_page": 1,
                                             "total": len(rows),
                                             "per_page": 15,
                                             "current_page": 1}}


class _FakeBisonForFactory(RendersTheQueue):
    """The factory-side fake: create_campaign, attach_leads, etc.

    Separate from the estate fake because the factory and the collision check
    use different interfaces. The factory calls methods on `bisonfactory.bison`;
    the collision check calls `collision.request` which goes through the HTTP
    transport.
    """

    def __init__(self):
        self.campaigns = {}
        self.leads = {}
        self.members = {}
        self.next_id = 500
        self.created_campaigns = 0
        self.created_leads = 0
        self.declared = {"headline", "industry", "location"}
        self.schedules = {}
        self.senders = {}
        self.steps = {}

    @staticmethod
    def _variables(mapping_of):
        return [{"name": k, "value": str(v)}
                for k, v in sorted(mapping_of.items()) if str(v or "").strip()]

    @staticmethod
    def variables_of(row):
        return {v["name"]: v["value"]
                for v in (row or {}).get("custom_variables") or []}

    def lead(self, lead_id):
        return dict(self.leads[int(lead_id)])

    def update_lead(self, lead_id, fields):
        row = self.leads[int(lead_id)]
        held = {v["name"]: v["value"]
                for v in row.get("custom_variables") or []}
        for v in fields.get("custom_variables") or []:
            held[v["name"]] = v["value"]
        row["custom_variables"] = [{"name": k, "value": v}
                                   for k, v in sorted(held.items())]
        return held

    def ensure_custom_variables(self, names=None):
        from src.providers.bison import LEAD_VARIABLES
        names = names or LEAD_VARIABLES
        fresh = [n for n in names if n not in self.declared]
        self.declared.update(fresh)
        return {"declared": sorted(self.declared), "created": fresh}

    def _id(self):
        self.next_id += 1
        return self.next_id

    def bound_workspace(self):
        return {"id": 10, "name": "PRODUCTIVE"}

    def create_campaign(self, name):
        cid = self._id()
        self.campaigns[cid] = {"id": cid, "name": name, "status": "draft",
                               "max_emails_per_day": 1000,
                               "max_new_leads_per_day": 1000}
        self.members[cid] = []
        self.created_campaigns += 1
        return dict(self.campaigns[cid])

    def campaign(self, cid):
        row = self.campaigns.get(int(cid))
        if row is None:
            raise providers.ProviderError(f"no campaign {cid}")
        return dict(row)

    def create_lead(self, fields):
        address = fields["email"].lower()
        if any(l["email"] == address for l in self.leads.values()):
            raise providers.ProviderError(
                "emailbison create_lead: POST /leads -> 422 The email has "
                "already been taken.")
        if not str(fields.get("first_name") or "").strip():
            raise providers.ProviderError("422 The first name field is required.")
        for variable in fields.get("custom_variables") or []:
            if variable["name"] not in self.declared:
                raise providers.ProviderError(
                    f"422 You do not have a custom variable named "
                    f"{variable['name']}. Please create one and try again")
        lid = self._id()
        self.leads[lid] = {"id": lid, "email": address,
                           "custom_variables": fields.get("custom_variables")
                           or []}
        self.created_leads += 1
        return dict(self.leads[lid])

    def find_lead_by_email(self, email, attempts=1, interval=1.0):
        for row in self.leads.values():
            if row["email"] == str(email).lower():
                return dict(row)
        return None

    from src.providers.bison import (FAILED_STATES, NOT_STARTED_STATES,
                                     PENDING_DELETION, STARTED_STATES,
                                     STARTING_STATES)

    def find_campaigns_by_name(self, name):
        return [{"id": c["id"], "name": c["name"], "status": c["status"]}
                for c in self.campaigns.values() if c["name"] == name]

    def campaign_lead_ids(self, cid):
        return list(self.members.get(int(cid), []))

    def campaign_lead_count(self, cid):
        return len(self.members.get(int(cid), []))

    def attach_leads(self, cid, lead_ids):
        cid = int(cid)
        before = set(self.members.get(cid, []))
        fresh = [i for i in lead_ids if i not in before]
        self.members[cid] = sorted(before | set(lead_ids))
        return {"attached": fresh,
                "already": [i for i in lead_ids if i in before],
                "members": list(self.members[cid]),
                "count": len(self.members[cid])}

    def set_limits(self, cid, name, emails_per_day, new_leads_per_day=None):
        leads = emails_per_day if new_leads_per_day is None else new_leads_per_day
        self.campaigns[int(cid)]["max_emails_per_day"] = emails_per_day
        self.campaigns[int(cid)]["max_new_leads_per_day"] = leads
        return {"campaign_id": cid, "max_emails_per_day": emails_per_day,
                "max_new_leads_per_day": leads}

    DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday")

    def schedule(self, cid):
        return dict(self.schedules.get(int(cid), {}))

    def set_schedule(self, cid, days, start, end, timezone):
        row = {d: (d in days) for d in self.DAYS}
        row.update({"start_time": start + ":00", "end_time": end + ":00",
                    "timezone": timezone})
        self.schedules[int(cid)] = row
        return row

    def schedule_matches(self, existing, days, start, end, timezone):
        from src.providers import bison as real
        return real.schedule_matches(existing, days, start, end, timezone)

    def campaign_senders(self, cid):
        return list(self.senders.get(int(cid), []))

    def attach_senders(self, cid, ids):
        self.senders[int(cid)] = sorted({*self.senders.get(int(cid), []),
                                         *[int(i) for i in ids]})
        return {"campaign_id": cid, "senders": self.senders[int(cid)]}

    def set_sequence(self, cid, title, steps):
        self.steps.setdefault(int(cid), []).extend(
            {"id": self._id(), "order": i + 1,
             "email_subject": s.get("email_subject"),
             "email_body": s.get("email_body"),
             "wait_in_days": s.get("wait_in_days"), "active": True,
             "thread_reply": s.get("thread_reply")}
            for i, s in enumerate(steps))
        return {"id": self._id(), "title": title}

    def sequence_steps(self, cid):
        return [dict(s) for s in self.steps.get(int(cid), [])]

    def pause_campaign(self, cid):
        self.campaigns[int(cid)]["status"] = "paused"
        return {"campaign_id": cid, "status": "paused"}


class StagingRefusesCollidingContacts(QueueTest):
    """The nine real cases from campaign 481, as a fixture."""

    def setUp(self):
        super().setUp()
        self.factory_bison = _FakeBisonForFactory()
        self.factory_bison.DAYS = _FakeBisonForFactory.DAYS
        self._real_bison = bisonfactory.bison
        bisonfactory.bison = self.factory_bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real_bison)

        self.estate = _EstateAwareFakeBison(workspace=10, name="PRODUCTIVE")
        self._real_request = collision.request
        self._real_col_bison = collision.bison
        collision.request = self.estate
        collision.bison = _CollisionBisonShim(self.estate)
        self.addCleanup(setattr, collision, "request", self._real_request)
        self.addCleanup(setattr, collision, "bison", self._real_col_bison)
        collision.forget_tenant_scope()
        self.addCleanup(collision.forget_tenant_scope)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def _stage_with(self, records):
        store.save(records)
        row = campaigns.new_campaign(CID, "productive", "Collision test")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=CONFIG)]
        row["record_ids"] = [r["id"] for r in records]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        return bisonfactory.stage(CID, config=CONFIG, live=True)

    def test_in_sequence_is_refused_by_name(self):
        """A contact mid-sequence in the client's estate is REFUSED.

        199963 was in_sequence in campaign 352 - being emailed RIGHT NOW.
        """
        self.estate.seed_estate(
            "one@example.com",
            [{"campaign_id": 352, "status": "in_sequence",
              "emails_sent": 3, "replies": 0}])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self._stage_with([_record("rec-1", "one@example.com", "Ada")])
        self.assertIn("rec-1-c1", str(caught.exception))
        self.assertIn("one@example.com", str(caught.exception))
        self.assertEqual(self.factory_bison.created_leads, 0,
                         "a lead was created despite the collision")

    def test_stopped_is_refused(self):
        """A contact who was stopped in the client's estate is REFUSED.

        144582 was stopped in campaign 352 - the state a reply or unsubscribe
        leaves behind.
        """
        self.estate.seed_estate(
            "one@example.com",
            [{"campaign_id": 352, "status": "stopped",
              "emails_sent": 5, "replies": 0}])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self._stage_with([_record("rec-1", "one@example.com", "Ada")])
        self.assertIn("rec-1-c1", str(caught.exception))
        self.assertEqual(self.factory_bison.created_leads, 0)

    def test_bounced_is_refused(self):
        """A contact whose address bounced is REFUSED.

        142476 bounced in campaign 327.
        """
        self.estate.seed_estate(
            "one@example.com",
            [{"campaign_id": 327, "status": "bounced",
              "emails_sent": 1, "replies": 0}])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self._stage_with([_record("rec-1", "one@example.com", "Ada")])
        self.assertIn("rec-1-c1", str(caught.exception))
        self.assertEqual(self.factory_bison.created_leads, 0)

    def test_sequence_finished_may_pass(self):
        """A contact whose campaign finished with no reply is NOT refused.

        173033 and five others were sequence_finished across campaigns 327
        and 352. `account_policy` says ALLOW: a campaign that ran its course
        with no reply is history, not a live conflict.
        """
        self.estate.seed_estate(
            "one@example.com",
            [{"campaign_id": 352, "status": "sequence_finished",
              "emails_sent": 5, "replies": 0}])
        report = self._stage_with([_record("rec-1", "one@example.com", "Ada")])
        self.assertEqual(self.factory_bison.created_leads, 1,
                         "a clean contact from a finished campaign was refused")

    def test_a_clean_contact_still_stages(self):
        """A contact with no estate presence stages normally."""
        report = self._stage_with([_record("rec-1", "one@example.com", "Ada")])
        self.assertEqual(self.factory_bison.created_leads, 1)
        self.assertEqual(report["provider"]["leads"]["created"], 1)

    def test_the_nine_real_cases_as_a_fixture(self):
        """All four states together: three block, one passes.

        Models the nine contacts from campaign 481. The three that must block
        (in_sequence, stopped, bounced) are refused; the one that may pass
        (sequence_finished) stages. Each contact is at a different domain so
        the account-level check does not conflate them.
        """
        self.estate.seed_estate(
            "in-seq@in-seq.test",
            [{"campaign_id": 352, "status": "in_sequence",
              "emails_sent": 3, "replies": 0}])
        self.estate.seed_estate(
            "stopped@stopped.test",
            [{"campaign_id": 352, "status": "stopped",
              "emails_sent": 5, "replies": 0}])
        self.estate.seed_estate(
            "bounced@bounced.test",
            [{"campaign_id": 327, "status": "bounced",
              "emails_sent": 1, "replies": 0}])
        self.estate.seed_estate(
            "finished@finished.test",
            [{"campaign_id": 352, "status": "sequence_finished",
              "emails_sent": 5, "replies": 0}])

        records = [
            _record("rec-seq", "in-seq@in-seq.test", "InSeq", "in-seq.test"),
            _record("rec-stop", "stopped@stopped.test", "Stopped",
                    "stopped.test"),
            _record("rec-bounce", "bounced@bounced.test", "Bounced",
                    "bounced.test"),
            _record("rec-finish", "finished@finished.test", "Finished",
                    "finished.test"),
        ]

        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self._stage_with(records)
        msg = str(caught.exception)
        self.assertIn("rec-seq-c1", msg)
        self.assertIn("rec-stop-c1", msg)
        self.assertIn("rec-bounce-c1", msg)
        self.assertNotIn("rec-finish-c1", msg,
                         "sequence_finished was refused; account_policy says "
                         "ALLOW for finished campaigns with no reply")
        self.assertEqual(self.factory_bison.created_leads, 0,
                         "any lead was created despite the collision")

    def test_breaking_the_check_makes_the_intended_test_fail(self):
        """If the collision check is removed, the in_sequence test passes.

        This is the 'break the guard' test. It patches _refuse_colliding_leads
        to a no-op and confirms that the in_sequence contact is no longer
        refused - proving the test above fails FOR THE INTENDED REASON (the
        collision check) and not because of some other gate.
        """
        self.estate.seed_estate(
            "one@example.com",
            [{"campaign_id": 352, "status": "in_sequence",
              "emails_sent": 3, "replies": 0}])

        with mock.patch.object(bisonfactory, "_refuse_colliding_leads",
                               lambda *a, **kw: None):
            report = self._stage_with(
                [_record("rec-1", "one@example.com", "Ada")])
        self.assertEqual(self.factory_bison.created_leads, 1,
                         "with the guard removed, the contact should stage - "
                         "proving the guard is what the other tests rely on")


class _CollisionBisonShim:
    """Makes the collision module's bison calls work against the fake.

    `collision.leads_for_domain` calls `bison.require_workspace`,
    `bison.base()` and `bison.headers()`. This shim provides those against
    the fake transport.
    """

    def __init__(self, fake):
        self._fake = fake

    def require_workspace(self, workspace_id):
        if str(workspace_id) != str(self._fake.workspace.get("id")):
            raise collision.CollisionUnknown(
                f"workspace mismatch: expected {workspace_id}, "
                f"have {self._fake.workspace.get('id')}")
        return self._fake.workspace

    def base(self):
        return "http://fake-emailbison"

    def headers(self):
        return {"Authorization": "Bearer test"}


def patch_collision_empty(test):
    """Patch the collision module to return an empty estate.

    For existing factory tests that don't model an estate. The collision
    check sees no leads and allows staging to proceed. Registers cleanup.
    """
    class _EmptyTransport:
        def __call__(self, method, url, headers=None, body=None, timeout=None):
            return 200, {"data": [], "meta": {"last_page": 1, "total": 0,
                                               "per_page": 15,
                                               "current_page": 1}}

    class _EmptyBison:
        def require_workspace(self, workspace_id):
            return {"id": workspace_id, "name": "Test"}
        def base(self):
            return "http://fake"
        def headers(self):
            return {}

    real_request = collision.request
    real_bison = collision.bison
    collision.request = _EmptyTransport()
    collision.bison = _EmptyBison()
    collision.forget_tenant_scope()
    test.addCleanup(setattr, collision, "request", real_request)
    test.addCleanup(setattr, collision, "bison", real_bison)
    test.addCleanup(collision.forget_tenant_scope)


if __name__ == "__main__":
    unittest.main()
