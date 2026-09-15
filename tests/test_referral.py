"""Somebody pointing at somebody else, and how sure we are who that is.

Three decisions are defended here and they are the whole feature.

**A name is evidence, never identity.** Two people share a name and one
person has three. "Talk to Sarah" resolves to `unknown` however obvious it
looks, and nothing downstream may turn it into a contact, a selection, or a
referral edge. `events.REFERRAL_RECORDED` keeps its meaning - an
introduction between two people we already hold, written by a person - and
the classifier is not allowed near it.

**A referral never softens a stop.** `reply.on_referral` holds the replier
where `on_negative` and `on_wrong_person` stop them, so a message read as a
referral is read as *less* final than the same message read as a refusal.
That is why the rule is ranked last: "not interested, try Acme" is a
refusal, "I'm not the right person, talk to Sarah" is a wrong-person reply,
and "sounds good, but speak to Sarah" is a positive. All three still name
somebody, which is the third decision.

**The mention is recorded from the evidence, not from the winning
category.** Otherwise ranking the rule last would throw away the useful
half of every polite refusal. The exception is a removal request: a queue
item naming a colleague inside a company-wide stop is the worst thing this
could produce, so that one is dropped rather than recorded.
"""
import unittest

from tests.campaignbase import CampaignTest, contact as make_contact
from src import events, inbound, referral, replies, tasks

SEP2 = "2026-09-02T09:00:00+00:00"


class ReadingWhatWasSaid(unittest.TestCase):
    """`evidence` reports, it does not interpret."""

    def test_an_address_after_a_cue(self):
        found = referral.evidence("You should email bo@acme.test about it.")
        self.assertEqual(found["emails"], ["bo@acme.test"])

    def test_an_address_is_normalised_the_way_every_other_one_is(self):
        """Identity is exact, so it has to be exact in the same way."""
        found = referral.evidence("Contact BO@Acme.TEST instead.")
        self.assertEqual(found["emails"], ["bo@acme.test"])

    def test_a_profile_url_is_canonicalised(self):
        found = referral.evidence(
            "Talk to https://www.linkedin.com/in/dana-reed/?trk=copy")
        self.assertEqual(len(found["profiles"]), 1)
        self.assertIn("dana-reed", found["profiles"][0])
        self.assertNotIn("trk=", found["profiles"][0])

    def test_a_name_only_after_a_cue(self):
        self.assertEqual(referral.evidence("Talk to Sarah Jones.")["names"],
                         ["Sarah Jones"])
        self.assertEqual(referral.evidence("I met Sarah Jones in June.")
                         ["names"], [])

    def test_a_sentence_may_open_with_the_cue(self):
        """The cue is matched without case and the name is not. A
        case-sensitive cue missed every referral that started a sentence."""
        self.assertEqual(referral.evidence("Copying in Dana Reed.")["names"],
                         ["Dana Reed"])

    def test_a_lower_case_word_after_a_cue_is_not_a_name(self):
        """Making the whole pattern case-insensitive returns "someone"."""
        self.assertEqual(referral.evidence("Talk to someone else.")["names"],
                         [])

    def test_nothing_is_read_out_of_an_empty_message(self):
        for text in ("", None, "   "):
            with self.subTest(text=text):
                found = referral.evidence(text)
                self.assertEqual(
                    (found["emails"], found["profiles"], found["names"]),
                    ([], [], []))

    def test_a_flood_of_addresses_is_bounded(self):
        body = "Contact " + " ".join(f"p{n}@acme.test" for n in range(40))
        self.assertLessEqual(len(referral.evidence(body)["emails"]), 5)


class WhoItPointsAt(unittest.TestCase):
    """`resolve` is the only thing allowed to say who somebody is."""

    def record(self):
        return {"id": "acme", "client": "demo", "company": "Acme Services",
                "contacts": [
                    {"key": "acme-champ", "name": "Champ Acme",
                     "email": "champ@acme.test",
                     "linkedin": "https://www.linkedin.com/in/acme-champ"},
                    {"key": "acme-ops", "name": "Ops Acme",
                     "email": "ops@acme.test",
                     "linkedin": "https://www.linkedin.com/in/acme-ops"},
                ]}

    def read(self, text, referrer="acme-champ"):
        return referral.read(self.record(), text, referrer=referrer)

    def test_an_address_we_already_hold_is_an_exact_match(self):
        got = self.read("You should email ops@acme.test instead.")
        self.assertEqual(got["status"], referral.EXACT_MATCH)
        self.assertEqual(got["contact"], "acme-ops")
        self.assertFalse(got["needs_a_person"])

    def test_a_profile_we_already_hold_is_an_exact_match(self):
        got = self.read("Talk to https://www.linkedin.com/in/acme-ops")
        self.assertEqual(got["status"], referral.EXACT_MATCH)
        self.assertEqual(got["contact"], "acme-ops")

    def test_an_address_we_do_not_hold_is_a_candidate_and_nobody_yet(self):
        got = self.read("Please email dana@acme.test about this.")
        self.assertEqual(got["status"], referral.CANDIDATE)
        self.assertIsNone(got["contact"])
        self.assertTrue(got["needs_a_person"])

    def test_a_name_is_never_an_identity_however_obvious(self):
        """There is an `Ops Acme` on this account and this still refuses."""
        got = self.read("Talk to Ops Acme about it.")
        self.assertEqual(got["status"], referral.UNKNOWN)
        self.assertIsNone(got["contact"])
        self.assertEqual(got["evidence"]["names"], ["Ops Acme"])

    def test_two_contacts_named_at_once_identify_nobody(self):
        got = self.read("Talk to ops@acme.test or "
                        "https://www.linkedin.com/in/acme-champ",
                        referrer="somebody-else")
        self.assertEqual(got["status"], referral.AMBIGUOUS)
        self.assertIsNone(got["contact"])

    def test_the_referrers_own_signature_is_not_a_referral_to_themselves(self):
        """Every signed reply would otherwise be an introduction."""
        got = self.read("Please contact champ@acme.test -- Champ")
        self.assertEqual(got["status"], referral.UNKNOWN)
        self.assertIsNone(got["contact"])

    def test_a_referrer_we_do_not_know_does_not_break_it(self):
        got = self.read("Email ops@acme.test.", referrer="nobody")
        self.assertEqual(got["status"], referral.EXACT_MATCH)

    def test_a_record_with_no_contacts_at_all(self):
        got = referral.read({"id": "x"}, "Email ops@acme.test.")
        self.assertEqual(got["status"], referral.CANDIDATE)

    def test_every_status_says_what_it_means_in_a_sentence(self):
        self.assertEqual(sorted(referral.STATUS_LABEL),
                         sorted(referral.STATUSES))
        for status in referral.STATUSES:
            with self.subTest(status=status):
                self.assertGreater(len(referral.STATUS_LABEL[status]), 10)


class AReferralNeverSoftensAStop(unittest.TestCase):
    """The ranking, asserted as behaviour rather than as a list."""

    def kind(self, text):
        return replies.classify(text)["classification"]

    def test_a_refusal_that_names_a_colleague_is_a_refusal(self):
        self.assertEqual(self.kind("Not interested - please try Acme."),
                         replies.NEGATIVE)

    def test_a_wrong_person_reply_that_names_a_colleague_is_wrong_person(self):
        self.assertEqual(
            self.kind("I'm not the right person - talk to Sarah Jones."),
            replies.NOT_RELEVANT)

    def test_an_unsubscribe_still_beats_everything(self):
        self.assertEqual(self.kind("Unsubscribe. Talk to Sarah Jones."),
                         replies.UNSUBSCRIBE)

    def test_a_company_wide_stop_still_beats_everything(self):
        self.assertEqual(
            self.kind("Remove our whole company. Talk to Sarah Jones."),
            replies.ACCOUNT_DNC)

    def test_warmth_that_names_a_colleague_is_still_positive(self):
        self.assertEqual(
            self.kind("Sounds good, but talk to Sarah Jones about it."),
            replies.POSITIVE)

    def test_a_date_that_names_nobody_is_still_a_date(self):
        self.assertEqual(self.kind("Reach out to me next quarter."),
                         replies.NOT_NOW)

    def test_a_plain_hand_off_is_a_referral(self):
        for text in ("The right person is Priya Nair.",
                     "Copying in Dana Reed who owns this.",
                     "You should contact bo@acme.test instead."):
            with self.subTest(text=text):
                self.assertEqual(self.kind(text), replies.REFERRAL)

    def test_a_cue_pointing_at_nobody_is_not_a_referral(self):
        """The half that produced every false positive."""
        for text in ("I need to talk to my boss first.",
                     "That would be great - happy to chat.",
                     "Can I ask what this is about?",
                     "Please forward this to our ops lead."):
            with self.subTest(text=text):
                self.assertNotEqual(self.kind(text), replies.REFERRAL)

    def test_the_mention_survives_whatever_the_category_is(self):
        """Ranking it last would otherwise throw away the useful half of
        every polite refusal."""
        for text in ("Not interested - please try Acme.",
                     "I'm not the right person - talk to Sarah Jones.",
                     "Sounds good, but talk to Sarah Jones about it."):
            with self.subTest(text=text):
                self.assertTrue(replies.mentions_referral(text))

    def test_an_address_with_no_cue_is_not_a_mention(self):
        """Every quoted thread footer carries an address."""
        self.assertFalse(replies.mentions_referral(
            "Thanks.\n\nOn Monday, sender@resonate.test wrote:"))


class TheWholeChain(CampaignTest):

    def seed(self):
        recs = self.seed_records()
        recs[0]["contacts"].append(
            make_contact("acme-ops", "Ops Acme", "ops@acme.test"))
        return recs

    def ingest(self, text, ident=7001, recs=None):
        recs = self.seed() if recs is None else recs
        row = {"id": ident, "uuid": f"u{ident}", "type": "Tracked Reply",
               "folder": "Inbox", "from_email_address": "champ@acme.test",
               "created_at": SEP2, "date_received": SEP2, "text_body": text,
               "automated_reply": False,
               "custom_variables": {"record_id": "acme",
                                    "contact_key": "acme-champ",
                                    "client": "demo"}}
        inbound.ingest({"data": [row]}, "emailbison", recs=recs,
                       config=self.config, post=lambda p, c=None: {"ok": True})
        return recs[0]

    def mentions(self, rec):
        return [e for e in rec.get("events") or []
                if e.get("type") == events.REFERRAL_MENTIONED]

    def test_the_mention_is_recorded_against_the_referrer(self):
        rec = self.ingest("The right person is Priya Nair.")
        found = self.mentions(rec)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["contact"], "acme-champ")
        self.assertEqual(found[0]["referral_status"], referral.UNKNOWN)
        self.assertEqual(found[0]["named"], "Priya Nair")

    def test_an_address_we_hold_resolves_to_that_contact(self):
        rec = self.ingest("You should email ops@acme.test instead.")
        found = self.mentions(rec)
        self.assertEqual(found[0]["referral_status"], referral.EXACT_MATCH)
        self.assertEqual(found[0]["referred_contact"], "acme-ops")

    def test_no_edge_is_written_and_nobody_is_activated(self):
        """`REFERRAL_RECORDED` is an introduction a person made. A
        classifier writing one manufactures an introduction that never
        happened, and the next message opens by claiming it did."""
        rec = self.ingest("You should email ops@acme.test instead.")
        self.assertEqual(
            [e for e in rec["events"]
             if e.get("type") == events.REFERRAL_RECORDED], [])
        for entry in rec["events"]:
            self.assertNotEqual(entry.get("type"),
                                events.REFERRED_CONTACT_ACTIVATED)

    def test_no_contact_is_created_for_somebody_we_do_not_hold(self):
        rec = self.ingest("Please email dana@acme.test about this.")
        keys = [c["key"] for c in rec["contacts"]]
        self.assertEqual(sorted(keys), ["acme-champ", "acme-ops"])
        self.assertEqual(self.mentions(rec)[0]["referral_status"],
                         referral.CANDIDATE)

    def test_nobody_named_in_a_referral_is_selected_for_outreach(self):
        rec = self.ingest("You should email ops@acme.test instead.")
        target = next(c for c in rec["contacts"] if c["key"] == "acme-ops")
        self.assertFalse(target.get("selected"))

    def champ(self, rec):
        return next(c for c in rec["contacts"] if c["key"] == "acme-champ")

    def test_a_plain_hand_off_holds_the_referrer(self):
        """A referral is not permission to keep writing to the person who
        handed us on. `reply.on_referral` stops their sequence - the
        referrer said 'not me', which is final for this contact, not a
        pause a person can lift."""
        rec = self.ingest("The right person is Priya Nair.")
        self.assertTrue(self.champ(rec).get("stopped"))

    def test_a_refusal_that_hands_us_on_still_stops_the_referrer(self):
        """The ranking, proved on state rather than on the category. If
        the referral rule won here, somebody who said "I am not the right
        person" would be left paused instead of stopped."""
        rec = self.ingest("I'm not the right person - talk to Sarah Jones.",
                          ident=7030)
        self.assertTrue(self.champ(rec).get("stopped"))
        self.assertTrue(self.mentions(rec))

    def test_a_removal_request_records_no_mention_at_all(self):
        """A queue item naming a colleague inside a company-wide stop is
        the worst thing this could produce."""
        cases = (("Unsubscribe. Talk to Sarah Jones.", 7020),
                 ("Remove our whole company. Talk to Sarah Jones.", 7021))
        for text, ident in cases:
            with self.subTest(text=text):
                rec = self.ingest(text, ident=ident)
                self.assertEqual(self.mentions(rec), [])

    def test_the_same_reply_delivered_twice_records_one_mention(self):
        recs = self.seed()
        for _ in range(2):
            self.ingest("The right person is Priya Nair.", ident=7010,
                        recs=recs)
        self.assertEqual(len(self.mentions(recs[0])), 1)

    def test_a_reply_that_names_nobody_records_nothing(self):
        rec = self.ingest("Thanks, I will take a look.")
        self.assertEqual(self.mentions(rec), [])


class TheWorkQueue(CampaignTest):

    def seed(self):
        recs = self.seed_records()
        recs[0]["contacts"].append(
            make_contact("acme-ops", "Ops Acme", "ops@acme.test"))
        return recs

    def ingest(self, text, ident=7101):
        recs = self.seed()
        row = {"id": ident, "uuid": f"u{ident}", "type": "Tracked Reply",
               "folder": "Inbox", "from_email_address": "champ@acme.test",
               "created_at": SEP2, "date_received": SEP2, "text_body": text,
               "automated_reply": False,
               "custom_variables": {"record_id": "acme",
                                    "contact_key": "acme-champ",
                                    "client": "demo"}}
        inbound.ingest({"data": [row]}, "emailbison", recs=recs,
                       config=self.config, post=lambda p, c=None: {"ok": True})
        return recs

    def kinds(self, recs, workspace="demo"):
        return [r["kind"] for r in
                tasks.collect(workspace, recs=recs, config=self.config,
                              today="2026-09-20")]

    def test_a_name_nobody_can_resolve_becomes_work(self):
        recs = self.ingest("The right person is Priya Nair.")
        self.assertIn(tasks.REVIEW_REFERRAL, self.kinds(recs))

    def test_an_address_we_do_not_hold_becomes_work(self):
        recs = self.ingest("Please email dana@acme.test about this.")
        self.assertIn(tasks.REVIEW_REFERRAL, self.kinds(recs))

    def test_somebody_we_already_hold_is_not_work(self):
        """The reply pointed at a contact on the account. Turning that into
        an edge is a person's decision, not a queue item."""
        recs = self.ingest("You should email ops@acme.test instead.")
        self.assertNotIn(tasks.REVIEW_REFERRAL, self.kinds(recs))

    def test_the_row_says_who_was_named_and_where(self):
        recs = self.ingest("The right person is Priya Nair.")
        row = next(r for r in tasks.collect("demo", recs=recs,
                                            config=self.config)
                   if r["kind"] == tasks.REVIEW_REFERRAL)
        self.assertIn("Priya Nair", row["title"])
        self.assertIn("Acme Services", row["title"])
        self.assertTrue(row["why"])

    def test_it_points_at_what_a_reply_carries_not_at_a_tab(self):
        """The tab filters on the classification and a mention is recorded
        from the evidence, so a referral inside a polite refusal sits under
        `negative`. `?kind=referral` would open a page without it;
        `?carries=referral` is the question that finds it."""
        recs = self.ingest("Not interested - please try Priya Nair.")
        row = next(r for r in tasks.collect("demo", recs=recs,
                                            config=self.config)
                   if r["kind"] == tasks.REVIEW_REFERRAL)
        self.assertEqual(row["where"], "/replies?carries=referral")
        self.assertNotIn("kind=", row["where"])
        classified = [e["classification"] for e in recs[0]["events"]
                      if e.get("type") == events.REPLY_CLASSIFIED]
        self.assertEqual(classified, [replies.NEGATIVE])

    def test_reading_the_reply_resolves_it(self):
        """Canonical: a reply stops needing somebody when it is marked
        handled, which already lives on the receipt. A second flag saying
        the same thing is how two screens start disagreeing."""
        recs = self.ingest("The right person is Priya Nair.")
        self.assertIn(tasks.REVIEW_REFERRAL, self.kinds(recs))
        marked = 0
        for entry in recs[0]["events"]:
            if entry.get("type") == events.REPLY_RECEIVED:
                entry["handled"] = {"by": "ops@productive.test",
                                    "at": SEP2, "note": ""}
                marked += 1
        self.assertEqual(marked, 1)
        self.assertNotIn(tasks.REVIEW_REFERRAL, self.kinds(recs))

    def test_another_workspace_does_not_see_it(self):
        recs = self.ingest("The right person is Priya Nair.")
        self.assertNotIn(tasks.REVIEW_REFERRAL,
                         self.kinds(recs, workspace="productive"))

    def test_the_digest_counts_it_too(self):
        """The recurring defect here is a thing computed correctly that
        nothing downstream reads. `tasks.collect` has three consumers and
        none of them names a kind, so proving one proves the wiring."""
        from src import digest
        recs = self.ingest("The right person is Priya Nair.")
        built = digest.build("demo", recs=recs, config=self.config,
                             today="2026-09-20", now=SEP2)
        self.assertEqual(built["counts"].get(tasks.REVIEW_REFERRAL), 1)
        self.assertIn(tasks.LABEL[tasks.REVIEW_REFERRAL],
                      " ".join(digest.lines(built)))

    def test_it_is_offered_as_work_a_person_has_to_do(self):
        from src import notify
        self.assertEqual(tasks.SEVERITY[tasks.REVIEW_REFERRAL],
                         notify.ACTION_REQUIRED)
        self.assertIn(tasks.REVIEW_REFERRAL, tasks.KINDS)
        self.assertTrue(tasks.LABEL[tasks.REVIEW_REFERRAL])


if __name__ == "__main__":
    unittest.main()
