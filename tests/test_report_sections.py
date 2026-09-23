"""Five report sections that were written, rendered, and never assembled.

`clientreport` reads `data["linkedin"]`, `["pipeline"]`, `["accounts"]`,
`["by_sender"]` and `["months"]`. `api.report_data` produced none of them.
So four rates - LinkedIn acceptance, LinkedIn reply rate, per-sender reply
rate and month-over-month reply rate - could not be computed at all, and
five sections of the monthly and detailed templates printed an excuse
about the period to explain a field that was simply not wired.

That is this repository's own recurring defect, five times over, in the
document a client reads.

None of what closes it is new measurement. Every number here is the event
log or `account.graph`, read the way the rest of the report reads them,
and the tests below are mostly about the two places where reading them the
obvious way would say something untrue:

**An acceptance is never inferred.** A LinkedIn message going out after a
connection request does not prove the request was accepted - a cadence can
queue one - so `accepted` counts only what a provider reported.

**A request is not a message.** Rolling them together gives an acceptance
rate whose denominator includes messages sent after the acceptance.
"""
import unittest

from tests.campaignbase import CampaignTest, contact as make_contact
from tests.test_client_reports import text_of

from src import events, store


class Sections(CampaignTest):

    def seeded(self):
        recs = self.seed_records()
        self.rec = recs[0]
        # A fresh estate: replacing the seeded contacts would drop their paid
        # verification evidence, which `store.save` refuses.
        self.reset_estate()
        self.rec["contacts"] = [
            make_contact("acme-champ", "Champ Acme", "champ@acme.test"),
            make_contact("acme-ops", "Ops Acme", "ops@acme.test")]
        store.save(recs)
        return recs

    def data(self):
        from src import repo as repo_module
        from src.web import api

        return api.report_data(repo_module.Repo.for_client("demo"))

    def touch(self, key, channel, step, at="2026-08-01T09:00:00+00:00"):
        events.record(self.rec, events.PUSH_MARKED, contact_key=key,
                      channel=channel, at=at, step=step, sender_id="anna")

    def reply(self, key, channel, at="2026-08-05T09:00:00+00:00",
              positive=False):
        events.record(self.rec, events.REPLY_RECEIVED, contact_key=key,
                      channel=channel, at=at)
        if positive:
            events.record(self.rec, events.POSITIVE_REPLY_DETECTED,
                          contact_key=key, channel=channel, at=at)


class TheLinkedInSection(Sections):

    def test_a_request_and_a_message_are_counted_apart(self):
        """Together they make an acceptance rate whose denominator
        includes messages sent after the acceptance."""
        self.seeded()
        self.touch("acme-champ", "linkedin", "day3")
        self.touch("acme-champ", "linkedin", "day8")
        store.save([self.rec])
        found = self.data()["linkedin"]
        self.assertEqual(found["requests"], 1)
        self.assertEqual(found["messages"], 1)

    def test_an_acceptance_is_only_ever_reported_by_a_provider(self):
        """A message going out after a request does not prove the request
        was accepted. A cadence can queue one."""
        self.seeded()
        self.touch("acme-champ", "linkedin", "day3")
        self.touch("acme-champ", "linkedin", "day8")
        store.save([self.rec])
        self.assertEqual(self.data()["linkedin"]["accepted"], 0)

    def test_a_reported_acceptance_is_counted(self):
        self.seeded()
        events.record(self.rec, events.LINKEDIN_CONNECTED,
                      contact_key="acme-champ", channel="linkedin",
                      at="2026-08-02T09:00:00+00:00")
        store.save([self.rec])
        self.assertEqual(self.data()["linkedin"]["accepted"], 1)

    def test_only_linkedin_replies_count(self):
        self.seeded()
        self.reply("acme-champ", "linkedin")
        self.reply("acme-ops", "email")
        store.save([self.rec])
        self.assertEqual(self.data()["linkedin"]["replies"], 1)

    def test_an_email_touch_is_not_a_linkedin_one(self):
        self.seeded()
        self.touch("acme-champ", "email", "day1")
        store.save([self.rec])
        found = self.data()["linkedin"]
        self.assertEqual(found["requests"] + found["messages"], 0)


class ThePipeline(Sections):

    def test_a_positive_reply_puts_somebody_in_it(self):
        self.seeded()
        self.reply("acme-champ", "email", positive=True)
        store.save([self.rec])
        rows = self.data()["pipeline"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["contact"], "Champ Acme")
        self.assertEqual(rows[0]["company"], "Acme Services")

    def test_an_ordinary_reply_does_not(self):
        self.seeded()
        self.reply("acme-champ", "email")
        store.save([self.rec])
        self.assertEqual(self.data()["pipeline"], [])

    def test_it_carries_no_reply_text(self):
        """There is none stored. A table that quoted one would be quoting
        something this build does not keep."""
        self.seeded()
        self.reply("acme-champ", "email", positive=True)
        store.save([self.rec])
        row = self.data()["pipeline"][0]
        self.assertEqual(sorted(row),
                         ["channel", "company", "contact", "sender",
                          "status", "title"])

    def test_a_sender_nobody_assigned_is_absent_rather_than_guessed(self):
        self.seeded()
        self.reply("acme-champ", "linkedin", positive=True)
        store.save([self.rec])
        self.assertIsNone(self.data()["pipeline"][0]["sender"])


class TheAccountCounts(Sections):
    """The PDF's account section, in THE OPERATOR'S VOCABULARY.

    OPERATOR, 2026-09-23: `_accounts` takes `untouched / sequenced /
    engaged / replied / meeting / won / lost / do_not_contact`, plus
    `unanswerable` as its own tile. The old `targeted / contacted /
    engaged / positive` keys are RETIRED, not aliased.

    The reason they could not be aliased is the third test below. Under the
    old vocabulary an account that replied counted as `engaged`, because
    `engaged` meant "at least one reply". Under the operator's it counts as
    `replied`, because `engaged` means something deliberately SHORT of a
    reply. One word, two meanings, in a document a client receives - so the
    word had to stop being ambiguous rather than be forwarded.
    """

    def test_it_counts_companies_not_contacts(self):
        """Two people at one company is one account."""
        self.seeded()
        self.touch("acme-champ", "email", "day1")
        self.touch("acme-ops", "email", "day1")
        store.save([self.rec])
        found = self.data()["accounts"]
        self.assertEqual(found["sequenced"], 1)
        self.assertEqual(found["multi_dm"], 1)

    def test_one_person_worked_is_not_a_multi_contact_account(self):
        self.seeded()
        self.touch("acme-champ", "email", "day1")
        store.save([self.rec])
        self.assertEqual(self.data()["accounts"]["multi_dm"], 0)

    def test_a_reply_is_replied_and_not_engaged(self):
        """THE COLLISION, pinned. This is the test that would have failed
        silently under an alias: the number would have moved from one tile
        to another and no assertion would have noticed."""
        self.seeded()
        self.reply("acme-champ", "email")
        store.save([self.rec])
        found = self.data()["accounts"]
        self.assertEqual(found["replied"], 1)
        self.assertEqual(found["engaged"], 0)

    def test_the_eight_states_account_for_every_record(self):
        """Every record sits in exactly one state, so the eight sum to the
        estate. A key that silently went missing would break this before it
        reached a client as a section of zeros."""
        from src import accountstate

        recs = self.seeded()
        found = self.data()["accounts"]
        for state in accountstate.ACCOUNT_STATES:
            self.assertIn(state, found)
        total = sum(found[s] for s in accountstate.ACCOUNT_STATES)
        self.assertEqual(total + found["unanswerable"], len(recs))

    def test_the_retired_keys_are_gone_rather_than_aliased(self):
        """An alias would be the same collision with a forwarding address."""
        found = self.data()["accounts"]
        self.seeded()
        for retired in ("targeted", "contacted", "positive"):
            self.assertNotIn(retired, found)


class TheMonths(Sections):

    def test_activity_is_grouped_by_calendar_month(self):
        self.seeded()
        self.touch("acme-champ", "email", "day1", at="2026-07-02T09:00:00+00:00")
        self.touch("acme-ops", "email", "day1", at="2026-08-02T09:00:00+00:00")
        self.reply("acme-ops", "email", at="2026-08-05T09:00:00+00:00")
        store.save([self.rec])
        months = {m["month"]: m for m in self.data()["months"]}
        self.assertEqual(months["2026-07"]["touches"], 1)
        self.assertEqual(months["2026-08"]["touches"], 1)
        self.assertEqual(months["2026-08"]["replies"], 1)

    def test_they_come_back_in_order(self):
        self.seeded()
        self.touch("acme-champ", "email", "day1", at="2026-08-02T09:00:00+00:00")
        self.touch("acme-ops", "email", "day1", at="2026-07-02T09:00:00+00:00")
        store.save([self.rec])
        found = [m["month"] for m in self.data()["months"]]
        self.assertEqual(found, sorted(found))

    def test_contacted_counts_people_once_per_month(self):
        self.seeded()
        self.touch("acme-champ", "email", "day1", at="2026-08-02T09:00:00+00:00")
        self.touch("acme-champ", "email", "day8", at="2026-08-09T09:00:00+00:00")
        store.save([self.rec])
        month = self.data()["months"][0]
        self.assertEqual(month["touches"], 2)
        self.assertEqual(month["contacted"], 1)

    def test_an_undated_event_is_left_out_rather_than_filed_under_now(self):
        """Filing it under the current month would move history every
        time the report was run."""
        self.seeded()
        events.record(self.rec, events.PUSH_MARKED, contact_key="acme-champ",
                      channel="email", at="not a date", step="day1",
                      sender_id="anna")
        store.save([self.rec])
        self.assertEqual(self.data()["months"], [])


class TheSenderRows(Sections):

    def test_a_sender_with_no_confirmed_touch_is_not_a_row(self):
        """There is nothing to attribute."""
        self.seeded()
        self.assertEqual(self.data()["by_sender"], [])

    def test_each_channel_is_its_own_row(self):
        self.seeded()
        self.rec["contacts"][0]["selected"] = True
        self.touch("acme-champ", "email", "day1")
        self.touch("acme-champ", "linkedin", "day3")
        store.save([self.rec])
        channels = sorted(r["channel"] for r in self.data()["by_sender"])
        self.assertEqual(channels, ["email", "linkedin"])

    def test_it_does_not_count_replies_a_fourth_way(self):
        """Three places counted one reply differently before the last
        audit. This reuses the sender report rather than becoming a
        fourth."""
        from src import repo as repo_module
        from src.web import api

        self.seeded()
        self.rec["contacts"][0]["selected"] = True
        self.touch("acme-champ", "email", "day1")
        self.reply("acme-champ", "email")
        store.save([self.rec])
        repo = repo_module.Repo.for_client("demo")
        rows = api.sender_report(repo, dimension="sender")["rows"]
        self.assertEqual(
            sum(r["replies"] for r in self.data()["by_sender"]),
            sum(r["replies"] for r in rows))


class OnThePage(Sections):

    def test_the_sections_render_rather_than_excusing_themselves(self):
        from src import clientreport

        self.seeded()
        self.rec["contacts"][0]["selected"] = True
        self.touch("acme-champ", "linkedin", "day3")
        self.reply("acme-champ", "linkedin", positive=True)
        store.save([self.rec])
        data = self.data()
        self.assertTrue(data["linkedin"]["requests"])
        self.assertTrue(data["pipeline"])
        # This record replied, so it is `replied` - not `sequenced`.
        self.assertTrue(data["accounts"]["replied"])
        self.assertTrue(data["months"])
        # And the renderer takes them without falling into its excuse.
        raw = clientreport.build(
            data, {"template": "detailed", "workspace_slug": "demo",
                   "workspace_name": "Demo"},
            clientreport.sections_for("detailed"))
        self.assertTrue(raw)
        # And it did not fall into the branch that says there is nothing
        # behind these sections.
        # DECOMPRESS BEFORE ASSERTING. `clientreport` writes page content
        # as FlateDecode streams, so `assertNotIn(b"...", raw)` against the
        # raw bytes CANNOT FAIL - the words are not findable in either
        # direction, and this assertion was green for that reason rather
        # than because the sections rendered. `text_of` is the canonical
        # reader, already used by tests/test_client_reports.py.
        drawn = text_of(raw)
        self.assertNotIn("is not assembled for this report", drawn)
        # And it drew SOMETHING - otherwise the line above passes on an
        # empty document, which is the same vacuity one level down.
        self.assertIn("Account Engagement", drawn)


if __name__ == "__main__":
    unittest.main()
