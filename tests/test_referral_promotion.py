"""Turning a referral into a contact, without letting it skip anything.

A reply says "email dana@acme.test instead". That address is the most
useful thing in the inbox and, until now, adding it was hand work with no
screen - which meant it was not done.

The whole risk is in the word "instead". A referral arrives inside a
conversation somebody is already having, and the temptation is to treat the
person it names as pre-approved: already introduced, already wanted,
already fine to write to. They are none of those things. What follows is
the list of what a referral may not skip, one test each.

**Canonical identity.** A name is not an identity, so a mention carrying
only "Priya Nair" has nothing to add and says so. An address or a canonical
profile is.

**Suppression.** Somebody who asked not to be contacted is not added
because a colleague named them.

**Duplication.** If that identifier is already on the account, the answer
is who it is, not a second row for the same person.

**Verification.** The contact arrives with no evidence, so it is not
sendable. Being referred is not being verified.

**Campaign eligibility.** It arrives unselected. Who a campaign opens with
is somebody's decision, and it is not the decision of the person who was
referred.

**Workspace boundaries.** The write goes through `Repo`, which is scoped at
construction.

**The edge, and who may write it.** `events.REFERRAL_RECORDED` has always
been "written by a person" rather than "never written". A person clicking
this button is that person; the classifier still cannot reach it.

**Decided now, not when the reply arrived.** The stored status is minutes
or weeks old. Somebody may have added that person, or suppressed them,
since.
"""
import unittest

from tests.campaignbase import CampaignTest, contact as make_contact
from tests.webbase import WebTest

from src import (agencydnc, events, hygiene, lint, referral, replies, store,
                 account)

SEP1 = "2026-09-01T09:00:00+00:00"


class PromotionTest(CampaignTest):

    def seed(self, text="You should email dana@acme.test instead."):
        recs = self.seed_records()
        self.rec = recs[0]
        self.recs = recs
        replies.apply(self.rec, "acme-champ", text, at=SEP1, channel="email")
        store.save(recs)
        return self.rec

    def mention(self):
        return next(e for e in self.rec["events"]
                    if e.get("type") == events.REFERRAL_MENTIONED)

    def answer(self, **kw):
        return referral.promotable(self.rec, self.mention(), **kw)


class WhatCanBeAdded(PromotionTest):

    def test_an_address_is_something_to_add(self):
        self.seed()
        found = self.answer()
        self.assertEqual(found["status"], referral.READY)
        self.assertEqual(found["email"], "dana@acme.test")

    def test_a_canonical_profile_is_too(self):
        self.seed("Talk to https://www.linkedin.com/in/dana-reed/?trk=x")
        found = self.answer()
        self.assertEqual(found["status"], referral.READY)
        self.assertIn("dana-reed", found["linkedin"])

    def test_a_name_alone_is_not(self):
        """Two people share a name and one person has three. There is
        nothing here to add."""
        self.seed("The right person is Priya Nair.")
        found = self.answer()
        self.assertEqual(found["status"], referral.NOT_A_CANDIDATE)
        self.assertIsNone(found["email"])

    def test_somebody_already_on_the_account_is_not_added_twice(self):
        self.rec = self.seed_records()[0]
        self.rec["contacts"].append(
            make_contact("acme-ops", "Ops Acme", "ops@acme.test"))
        replies.apply(self.rec, "acme-champ",
                      "You should email ops@acme.test instead.", at=SEP1,
                      channel="email")
        found = self.answer()
        self.assertEqual(found["status"], referral.ALREADY_HERE)
        self.assertEqual(found["contact"], "acme-ops")

    def test_the_answer_is_worked_out_now_rather_than_stored(self):
        """Somebody may have added that person since the reply arrived."""
        self.seed()
        self.assertEqual(self.answer()["status"], referral.READY)
        self.rec["contacts"].append(
            make_contact("acme-dana", "Dana Reed", "dana@acme.test"))
        self.assertEqual(self.answer()["status"], referral.ALREADY_HERE)

    def test_a_suppressed_person_is_not_added_because_a_colleague_named_them(self):
        """The agency index answers "is this person suppressed" and never
        by whom. That is enough to refuse."""
        self.seed()
        index = agencydnc.Index({
            agencydnc.fingerprint("email", "dana@acme.test"):
                {"reason": agencydnc.REQUESTED, "at": SEP1}})
        found = self.answer(history=hygiene.index([]), agency=index)
        self.assertEqual(found["status"], referral.SUPPRESSED)
        self.assertIn("suppressed", found["why"].lower())

    def test_every_refusal_says_why_in_a_sentence(self):
        self.assertEqual(sorted(referral.PROMOTION_LABEL),
                         sorted([referral.ALREADY_HERE,
                                 referral.NOT_A_CANDIDATE,
                                 referral.READY, referral.SUPPRESSED]))
        for status, sentence in referral.PROMOTION_LABEL.items():
            with self.subTest(status=status):
                self.assertGreater(len(sentence), 15)


class ReferredIntoTheEstate(WebTest):
    """Helpers. A different referred address per test.

    `WebTest` builds one estate for the class, so a contact one test adds
    is still there for the next. Deriving the address from the test's own
    name keeps them off each other without pretending the estate is fresh -
    which it is not, and which is closer to a real workspace anyway.
    """

    def setUp(self):
        super().setUp()
        import re as _re
        import zlib
        from src import repo as repo_module

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        recs = self.repo.records()
        self.rec = next(r for r in recs if r.get("contacts"))
        self.who = self.rec["contacts"][0]["key"]
        name = self.id().rsplit(".", 1)[-1]
        self.address = _re.sub(r"[^a-z]", "", name) + "@newperson.test"
        # A distinct timestamp as well as a distinct address. An event id
        # is a hash of provider, type, record, contact, channel and time -
        # not of the body - so two mentions at the same instant on the same
        # reply are one event however different the addresses in them are.
        minutes = zlib.crc32(name.encode("utf-8")) % 600
        self.at = "2026-09-01T{:02d}:{:02d}:00+00:00".format(
            9 + minutes // 60, minutes % 60)
        replies.apply(self.rec, self.who,
                      f"You should email {self.address} instead.",
                      at=self.at, channel="email")
        self.repo.save_records([self.rec])

    def mention_id(self):
        rec = self.repo.record(self.rec["id"])
        return next(e["id"] for e in rec["events"]
                    if e.get("type") == events.REFERRAL_MENTIONED
                    and self.address in (e.get("emails") or []))


class WhatTheNewContactIsNot(ReferredIntoTheEstate):
    """The gates a referred person does not skip."""

    def add(self):
        from src.web import api
        return api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                        self.mention_id(),
                                        by="ops@productive.test")

    def test_it_is_added_at_all(self):
        added = self.add()
        self.assertEqual(added["email"], self.address)
        self.assertIn(added["key"],
                      [c["key"] for c in
                       self.repo.record(self.rec["id"])["contacts"]])

    def test_it_is_not_sendable(self):
        """Being referred is not being verified."""
        self.assertFalse(lint.sendable(self.add()))

    def test_it_carries_no_verification_evidence(self):
        added = self.add()
        self.assertEqual(added.get("verification"), None)

    def test_it_is_not_selected(self):
        """Who a campaign opens with is somebody's decision, and it is not
        the decision of the person who was referred."""
        self.assertFalse(self.add().get("selected"))

    def test_it_records_where_it_came_from(self):
        source = self.add()["source"]
        self.assertEqual(source["from"], "referral")
        self.assertEqual(source["referred_by"], self.who)
        self.assertEqual(source["added_by"], "ops@productive.test")

    def test_the_edge_is_written_because_a_person_wrote_it(self):
        added = self.add()
        edges = account.referrals(self.repo.record(self.rec["id"]))
        self.assertTrue(any(e["from_contact"] == self.who
                            and e["to_contact"] == added["key"]
                            for e in edges))

    def test_the_keys_already_on_the_record_are_untouched(self):
        """A contact key is referenced by the cadence, the event log, the
        approvals and the touch graph, so an append must not re-derive
        them. `identity.contact_key` returns a key a contact already has,
        which is what makes the import helper safe to reuse here."""
        before = [c["key"] for c in self.repo.record(self.rec["id"])
                  ["contacts"]]
        self.add()
        after = [c["key"] for c in self.repo.record(self.rec["id"])
                 ["contacts"]]
        self.assertEqual(after[:len(before)], before)

    def test_two_people_from_one_reply_get_two_edges(self):
        """An event id is a hash of provider, type, record, contact,
        channel and time - not of who was referred. Without something to
        tell them apart, two added inside the same second are one edge and
        the second person silently has none."""
        second = "colleague-" + self.address
        replies.apply(self.rec, self.who,
                      f"You should email {second} instead.",
                      at=self.at.replace(":00+", ":30+"), channel="email")
        self.repo.save_records([self.rec])
        rec = self.repo.record(self.rec["id"])
        mentions = [e["id"] for e in rec["events"]
                    if e.get("type") == events.REFERRAL_MENTIONED
                    and (self.address in (e.get("emails") or [])
                         or second in (e.get("emails") or []))]
        self.assertEqual(len(mentions), 2)

        from src.web import api
        added = [api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                          mention, by="ops@productive.test")
                 for mention in mentions]
        edges = account.referrals(self.repo.record(self.rec["id"]))
        pointed = {e["to_contact"] for e in edges}
        for person in added:
            with self.subTest(who=person["key"]):
                self.assertIn(person["key"], pointed)

    def test_it_is_in_the_audit_log(self):
        from src import workspaces as ws

        self.add()
        actions = [row.get("action") for row in ws.audit("productive")]
        self.assertIn("referral.contact_added", actions)

    def test_adding_the_same_one_twice_is_refused(self):
        from src.web import api

        self.add()
        with self.assertRaises(api.ActionRefused):
            self.add()

    def test_a_mention_that_is_not_there_is_not_an_error(self):
        from src.web import api

        self.assertIsNone(api.add_referred_contact(
            self.repo, self.rec["id"], self.who, "ev_nothing"))

    def test_a_record_in_another_workspace_is_not_reachable(self):
        """`Repo` refuses rather than returning nothing, which is the
        stronger answer: a caller cannot mistake it for "no such record"."""
        from src import repo as repo_module
        from src.web import api

        theirs = repo_module.Repo.for_user("ops@demo-client.test",
                                           "demo-client")
        with self.assertRaises(repo_module.CrossClientAccess):
            api.add_referred_contact(theirs, self.rec["id"], self.who,
                                     self.mention_id())


class OnTheScreen(ReferredIntoTheEstate):

    def view(self):
        """Narrowed to this test's own referral, for the same reason the
        address is unique: the others are still on the record."""
        from src.web import api
        found = api.reply_context(self.repo, self.rec["id"], self.who)
        found["referred"] = [r for r in found["referred"]
                             if r["email"] == self.address]
        return found

    def test_the_reply_page_names_who_was_pointed_at(self):
        rows = self.view()["referred"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], self.address)
        self.assertTrue(rows[0]["promotable"])

    def test_the_page_offers_the_action(self):
        session = self.signin("ops@productive.test")
        status, body, _ = session.get(
            f"/replies/context/{self.rec['id']}/{self.who}")
        self.assertEqual(status, 200)
        self.assertIn("Who they pointed us at", body)
        self.assertIn("Add to this account", body)
        self.assertIn("not contacting them", body)

    def test_a_role_that_may_not_import_may_not_add(self):
        """This writes a person into the account. That is the authority to
        import somebody, not the authority to read a reply."""
        session = self.signin("client@productive.test")
        status, _, _ = session.post(
            "/replies/referral/add",
            {"csrf": session.csrf(), "record_id": self.rec["id"],
             "contact_key": self.who, "event_id": "x"})
        self.assertIn(status, (403, 404))

    def test_the_button_is_gone_once_they_are_a_contact(self):
        from src.web import api
        from src.web import pages

        api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                 self.mention_id(), by="ops@productive.test")
        html = pages.reply_context(self.view(), "csrf")
        self.assertNotIn("Add to this account", html)
        self.assertIn("already has that identifier", html)


if __name__ == "__main__":
    unittest.main()
