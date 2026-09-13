#!/usr/bin/env python3
"""A campaign staged twice is one campaign, and its leads are made once.

Proven against the live provider on 2026-09-13 (EmailBison campaign 434:
created, populated, reused, lead count stable at 2, left `paused`) and pinned
here offline so it keeps holding.

The second run is the whole test. The first one passing proves only that the
routes work; it is the re-run that decides whether this system can be
interrupted and restarted without building a second campaign and mailing
everybody twice. Both failure modes in here were real:

  - the campaign was reused but its LEADS were created again, and the provider
    refused with "The email has already been taken";
  - and the tempting fix - looking the lead up by `?email=` - reads an
    unfiltered page as if it were a filtered one.
"""
import unittest

from src import bisonfactory, campaigns, store
from src import providers
from tests.base import QueueTest


class FakeBison:
    """A provider that behaves the way the measured one does.

    Including the parts that bite: creating a lead whose address already
    exists raises exactly the provider's error, and attaching a lead that is
    already in the campaign is silently ignored.
    """

    def __init__(self):
        self.campaigns = {}
        self.leads = {}
        self.members = {}
        self.next_id = 500
        self.created_campaigns = 0
        self.created_leads = 0
        # The workspace starts with only what the real one had, so a lead
        # carrying an undeclared variable is refused here exactly as the
        # provider refuses it.
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
            held[v["name"]] = v["value"]          # PATCH merges, per the API
        row["custom_variables"] = [{"name": k, "value": v}
                                   for k, v in sorted(held.items())]
        return held

    def custom_variables(self):
        return {name: i for i, name in enumerate(sorted(self.declared))}

    def ensure_custom_variables(self, names=None):
        names = names or ("subject", "body", "record_id", "contact_key",
                          "client")
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
        # 1000 is the provider's default, and it is what a campaign really
        # carries however it was created - a cap passed here is discarded.
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

    # The status vocabulary, taken from the real module rather than retyped:
    # a fixture that disagreed with it about what "started" means would be
    # testing a provider that does not exist.
    from src.providers.bison import (FAILED_STATES, NOT_STARTED_STATES,
                                     PENDING_DELETION, STARTED_STATES,
                                     STARTING_STATES)

    def find_campaigns_by_name(self, name):
        """The crash-recovery lookup: a campaign nobody wrote down.

        Here it is also the thing that proves the second run of this test
        reuses a BINDING rather than rediscovering the campaign by name -
        `created_campaigns` stays at one either way, so the fake has to be
        able to answer honestly.
        """
        return [{"id": c["id"], "name": c["name"], "status": c["status"]}
                for c in self.campaigns.values() if c["name"] == name]

    def campaign_lead_ids(self, cid):
        return list(self.members.get(int(cid), []))

    def campaign_lead_count(self, cid):
        """How many, read from `meta.total` in the real module: the campaign
        lead route serves fifteen rows whatever `per_page` asks for, so a
        count taken from a list is a count of a page."""
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
        # "09:00" is stored and "09:00:00" comes back, which is the asymmetry
        # `schedule_matches` exists to absorb. Modelled here so a comparison
        # that got it wrong would fail in this test too.
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
        # IT APPENDS. Measured 2026-09-13: two writes leave two steps, and
        # there is no replace and no delete. Modelled so this fixture cannot
        # make a double-send look like an idempotent re-stage.
        self.steps.setdefault(int(cid), []).extend(
            {"id": self._id(), "order": i + 1,
             "email_subject": s.get("email_subject"),
             "email_body": s.get("email_body"),
             "wait_in_days": s.get("wait_in_days"), "active": True}
            for i, s in enumerate(steps))
        return {"id": self._id(), "title": title}

    def sequence_steps(self, cid):
        return [dict(s) for s in self.steps.get(int(cid), [])]

    def pause_campaign(self, cid):
        self.campaigns[int(cid)]["status"] = "paused"
        return {"campaign_id": cid, "status": "paused"}


CID = "camp-factory"


class StagingTwiceBuildsOne(QueueTest):

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self.bison.DAYS = FakeBison.DAYS
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)

        store.save([self._record("rec-1", "one@example.com", "Ada"),
                    self._record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Factory test")
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    @staticmethod
    def _record(rid, email, first):
        return {"id": rid, "client": "productive", "domain": "example.com",
                "company": "Example", "state": "ready",
                "contacts": [{"key": f"{rid}-c1", "email": email,
                              "first_name": first, "last_name": "Tester",
                              "sendable": True, "verified": True}]}

    def test_the_second_run_creates_nothing(self):
        first = bisonfactory.stage(CID, live=True)
        second = bisonfactory.stage(CID, live=True)

        self.assertEqual(self.bison.created_campaigns, 1,
                         "a second provider campaign was built")
        self.assertEqual(self.bison.created_leads, 2,
                         "the leads were created again on the re-run")
        self.assertEqual(first["provider"]["campaign_id"],
                         second["provider"]["campaign_id"])
        self.assertEqual(second["provider"]["readback"]["leads"], 2)
        # HOW the second run found them, not just that it did. Without this
        # the test passes on the reconciliation path - create, get refused,
        # search - which avoids duplicates only while the provider's lead
        # search happens to be current.
        # `refreshed: 0` matters as much as `created: 0`. The copy travels in
        # custom variables and is reconciled against the provider on every
        # run, so an unchanged campaign must rewrite nothing - otherwise a
        # re-stage would churn every lead's words for no reason.
        self.assertEqual(second["provider"]["leads"],
                         {"created": 0, "reused": 2, "reconciled": 0,
                          "refreshed": 0})

    def test_the_provider_id_is_persisted_where_it_can_be_found(self):
        """An id the provider issued and we did not record is a duplicate."""
        bisonfactory.stage(CID, live=True)
        row = campaigns.get(CID, campaigns.load())
        self.assertTrue(row.get("bison_campaign_id"),
                        "the campaign row does not name its provider campaign")
        for rec in store.load():
            for contact in rec["contacts"]:
                self.assertTrue(contact.get("bison_lead_id"),
                                f"{contact['key']} has no provider lead id")

    def test_every_lead_can_be_traced_back_to_its_person(self):
        """A reply names an address. It has to be able to name a person.

        `adapters.from_emailbison` reads `record_id` and `contact_key` off an
        inbound reply, so a lead staged without them produces replies that
        stop nobody. The provider refuses undeclared variable names, which is
        why this also proves the declaration happened first.
        """
        bisonfactory.stage(CID, live=True)
        self.assertEqual(len(self.bison.leads), 2)
        for lead in self.bison.leads.values():
            carried = {v["name"]: v["value"]
                       for v in lead.get("custom_variables") or []}
            self.assertIn("record_id", carried)
            self.assertIn("contact_key", carried)
            self.assertEqual(carried.get("client"), "productive")
            self.assertTrue(carried["record_id"].startswith("rec-"))

    def test_an_uncapped_campaign_is_refused(self):
        """"Nobody set a rate" and "a thousand a day" are not the same state.

        `POST /campaigns` accepts a cap and stores the 1000/day default
        silently, so a campaign is uncapped until something caps it on
        purpose.
        """
        with campaigns.transaction() as rows:
            campaigns.get(CID, rows)["daily_volume"] = {"email": 0}
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, live=True)
        self.assertIn("1000", str(caught.exception))

    def test_the_cap_is_applied_before_anybody_is_attached(self):
        """A cap applied after the leads is a cap that was briefly absent."""
        bisonfactory.stage(CID, live=True)
        cid = int(campaigns.get(CID, campaigns.load())["bison_campaign_id"])
        self.assertEqual(self.bison.campaigns[cid]["max_emails_per_day"], 5)

    def test_it_is_left_stopped(self):
        """A staged campaign that can send has not been staged."""
        report = bisonfactory.stage(CID, live=True)
        self.assertEqual(report["provider"]["readback"]["status"], "paused")

    def test_re_staging_does_not_stop_a_running_campaign(self):
        """Re-staging reconciles material. It is not a way to stop a send.

        Measured on 2026-09-13: the duplicate-refusal check re-staged the
        authorised canary and paused the campaign, suspending the send it had
        just committed. Nothing raised, because pausing looks like the safe
        direction - and a routine re-stage silently stopping a live campaign
        is its own kind of unsafe.
        """
        bisonfactory.stage(CID, live=True)
        cid = int(campaigns.get(CID, campaigns.load())["bison_campaign_id"])
        self.bison.campaigns[cid]["status"] = "active"     # somebody started it
        report = bisonfactory.stage(CID, live=True)
        self.assertEqual(self.bison.campaigns[cid]["status"], "active",
                         "re-staging stopped a running campaign")
        self.assertTrue(report["provider"].get("left_running"))

    def test_a_foreign_workspace_is_refused(self):
        """The credential's real estate must be the client's estate."""
        self.bison.bound_workspace = lambda: {"id": 25, "name": "Ironvault"}
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, live=True)
        self.assertIn("25", str(caught.exception))
        self.assertEqual(self.bison.created_campaigns, 0)

    def test_a_dry_run_touches_nothing(self):
        report = bisonfactory.stage(CID, live=False)
        self.assertFalse(report["live"])
        self.assertEqual(self.bison.created_campaigns, 0)
        self.assertEqual(self.bison.created_leads, 0)


if __name__ == "__main__":
    unittest.main()
