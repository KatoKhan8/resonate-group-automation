"""What is happening at an account, and whether it still matters.

Three properties, and every test is one of them:

**Signals observe; they never replace.** First-party signals are derived
from the event log, not stored beside it. A signal cannot change what a
reply meant, and where the two could disagree the canonical fact wins.

**Evidence is not optional.** A signal without evidence is a rumour with a
timestamp, and the constructor refuses one.

**Priority is not permission.** The highest-scoring account in a workspace
can be suppressed, and the assessment has to say both. This is the test
file that would fail if anybody ever let a score grant eligibility.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import (accountpolicy as ap, events, priority, refresh,
                 repo as repo_module, revival, signals as S,
                 store, workspaces)
from src.web import api
from tests.base import ProviderTest
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"
NOW = datetime.datetime(2026, 8, 29, tzinfo=datetime.timezone.utc)


def days_ago(n):
    return (NOW - datetime.timedelta(days=n)).isoformat()


class SignalTest(CampaignTest):

    def record(self, rid="sig-acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "john@acme.test", "selected": True},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "sarah@acme.test", "selected": True},
            {"key": MIKE, "name": "Michael Green", "title": "CFO",
             "email": "mike@acme.test", "selected": False},
        ]
        store.save([rec])
        return rec

    def touch(self, rec, key=JOHN, at=None):
        events.record(rec, events.PUSH_MARKED, contact_key=key,
                      channel="email", at=at or days_ago(20),
                      sender_id="anna", step="d1")
        return rec

    def reply(self, rec, key=JOHN, outcome=ap.POSITIVE, at=None):
        at = at or days_ago(10)
        events.record(rec, events.REPLY_RECEIVED, contact_key=key,
                      channel="email", at=at,
                      provider_event_id=f"r-{rec['id']}-{key}")
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=key,
                      channel="email", at=at, classification=outcome,
                      provider_event_id=f"r-{rec['id']}-{key}:c")
        if outcome == ap.POSITIVE:
            events.record(rec, events.POSITIVE_REPLY_DETECTED,
                          contact_key=key, channel="email", at=at,
                          provider_event_id=f"r-{rec['id']}-{key}:p")
        ap.apply_reply(rec, key, outcome, at=at, channel="email")
        return rec


# ------------------------------------------------------------ the model

class EvidenceIsMandatory(unittest.TestCase):

    def test_a_signal_without_evidence_is_refused(self):
        with self.assertRaises(ValueError):
            S.signal(WS, S.HIRING_SURGE, evidence=None)
        with self.assertRaises(ValueError):
            S.signal(WS, S.HIRING_SURGE, evidence="")

    def test_the_evidence_is_what_was_observed(self):
        """"7 open roles", not "scaling rapidly"."""
        entry = S.signal(WS, S.HIRING_SURGE,
                         evidence="7 open project-management roles",
                         source=S.MANUAL, confidence=S.HIGH)
        self.assertIn("7 open", entry["evidence"])
        self.assertEqual(entry["scope"], S.ACCOUNT)

    def test_an_unknown_type_is_refused(self):
        with self.assertRaises(ValueError):
            S.signal(WS, "vibes", evidence="a feeling")

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(ValueError):
            S.signal(WS, S.FUNDING, evidence="x", source="a hunch")

    def test_every_type_has_a_scope_and_a_label(self):
        for kind in S.TYPES:
            self.assertIn(S.SCOPE_OF[kind], S.SCOPES, kind)
            self.assertIn(kind, S.LABEL, kind)

    def test_engagement_signals_map_from_the_canonical_outcomes(self):
        """No second vocabulary for facts that already have names."""
        for outcome in ap.OUTCOMES:
            if outcome == ap.UNKNOWN:
                continue
            self.assertIn(outcome, S.ENGAGEMENT_SIGNAL, outcome)
            self.assertEqual(S.SCOPE_OF[S.ENGAGEMENT_SIGNAL[outcome]],
                             S.ENGAGEMENT, outcome)


class StorageHoldsOnlyWhatCannotBeDerived(SignalTest):
    """Storing a first-party signal would put a second copy of an
    event-log fact somewhere it can drift from the log.

    The mutation audit found this guard untested: it existed and nothing
    checked it, so removing it changed no test.
    """

    def test_a_first_party_signal_cannot_be_stored(self):
        """The source is the rule here, so the type must not be able to
        answer for it.

        This test used to pass an engagement type, which meant that once
        the engagement guard was added the first-party guard could be
        deleted without the test noticing - it was refused either way, for
        the other reason. The mutation audit caught exactly that. An
        account-scope type isolates the guard under test.
        """
        entry = S.signal(WS, S.HIRING_SURGE, evidence="7 open roles",
                         source=S.FIRST_PARTY)
        with self.assertRaises(ValueError) as caught:
            S.record(entry)
        self.assertIn("derived", str(caught.exception))

    def test_an_engagement_signal_cannot_be_stored_whatever_its_source(self):
        """And the other guard on its own: manual source, engagement type.

        The pair covers both routes to the same rule. Neither test can
        pass because of the other one's guard.
        """
        entry = S.signal(WS, S.ENGAGED_POSITIVE, evidence="he replied",
                         source=S.MANUAL)
        with self.assertRaises(ValueError) as caught:
            S.record(entry)
        self.assertIn("event log", str(caught.exception))

    def test_a_manual_signal_can_be(self):
        entry = S.signal(WS, S.HIRING_SURGE, evidence="7 open roles",
                         source=S.MANUAL, created_by="ops@productive.test")
        S.record(entry)
        self.assertEqual(len(S.load(WS)), 1)

    def test_a_signal_must_name_its_workspace(self):
        entry = S.signal(WS, S.FUNDING, evidence="x", source=S.MANUAL)
        entry["workspace"] = None
        with self.assertRaises(ValueError):
            S.record(entry)

    def test_stored_signals_are_scoped_to_one_workspace(self):
        S.record(S.signal(WS, S.FUNDING, evidence="ours", source=S.MANUAL))
        S.record(S.signal("contactout", S.FUNDING, evidence="theirs",
                          source=S.MANUAL))
        mine = S.load(WS)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["evidence"], "ours")

    def test_a_manual_signal_records_who_entered_it(self):
        S.record(S.signal(WS, S.FUNDING, evidence="x", source=S.MANUAL,
                          created_by="ops@productive.test"))
        self.assertEqual(S.load(WS)[0]["created_by"], "ops@productive.test")

    def test_stored_and_derived_signals_do_not_double_count(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.POSITIVE)
        S.record(S.signal(WS, S.HIRING_SURGE, evidence="7 open roles",
                          record_id=rec["id"], source=S.MANUAL,
                          observed_at=days_ago(2)))
        out = priority.assess(rec, WS, now=NOW)
        kinds = [s["type"] for s in out["signals"]]
        self.assertEqual(kinds.count(S.HIRING_SURGE), 1)
        self.assertEqual(kinds.count(S.ENGAGED_POSITIVE), 1)


class FreshnessAndDecay(unittest.TestCase):

    def entry(self, kind, age, confidence=S.HIGH):
        return S.signal(WS, kind, evidence="x", source=S.MANUAL,
                        confidence=confidence, observed_at=days_ago(age))

    def test_a_fresh_signal_keeps_most_of_its_weight(self):
        out = S.weight_at(self.entry(S.HIRING_SURGE, 5), NOW)
        self.assertEqual(out["freshness"], S.FRESH)
        self.assertGreater(out["decay"], 0.9)

    def test_an_old_signal_decays(self):
        out = S.weight_at(self.entry(S.HIRING_SURGE, 60), NOW)
        self.assertAlmostEqual(out["decay"], 0.5, places=2)

    def test_a_very_old_signal_is_stale(self):
        out = S.weight_at(self.entry(S.HIRING_SURGE, 300), NOW)
        self.assertEqual(out["freshness"], S.STALE)

    def test_decay_differs_by_type(self):
        """A funding round and a website change do not age the same."""
        funding = S.weight_at(self.entry(S.FUNDING, 90), NOW)
        website = S.weight_at(self.entry(S.WEBSITE_CHANGE, 90), NOW)
        self.assertGreater(funding["decay"], website["decay"])

    def test_a_removal_request_never_decays(self):
        """The one kind of forgetting this system must never do."""
        for kind in (S.ENGAGED_UNSUBSCRIBE, S.ENGAGED_ACCOUNT_DNC,
                     S.ENGAGED_LEFT_COMPANY, S.ENGAGED_WRONG_PERSON):
            out = S.weight_at(self.entry(kind, 900), NOW)
            self.assertEqual(out["freshness"], S.PERMANENT, kind)
            self.assertEqual(out["decay"], 1.0, kind)

    def test_an_undated_signal_is_not_treated_as_fresh(self):
        entry = S.signal(WS, S.FUNDING, evidence="x", source=S.MANUAL)
        out = S.weight_at(entry, NOW)
        self.assertLess(out["decay"], 1.0)
        self.assertIn("no observation date", out["why"])

    def test_the_reading_shows_its_own_arithmetic(self):
        out = S.weight_at(self.entry(S.HIRING_SURGE, 30), NOW)
        for key in ("weight", "decay", "age_days", "freshness", "why"):
            self.assertIn(key, out)

    def test_confidence_scales_the_weight(self):
        high = S.weight_at(self.entry(S.FUNDING, 1, S.HIGH), NOW)["weight"]
        low = S.weight_at(self.entry(S.FUNDING, 1, S.LOW), NOW)["weight"]
        self.assertGreater(high, low)

    def test_half_life_is_workspace_configurable(self):
        config = {"signals": {"half_life": {S.HIRING_SURGE: 5}}}
        out = S.weight_at(self.entry(S.HIRING_SURGE, 5), NOW, config)
        self.assertAlmostEqual(out["decay"], 0.5, places=2)


class SignalStrengthSaturates(unittest.TestCase):

    def many(self, count, kind=S.JOB_POSTING, age=1):
        return [S.signal(WS, kind, evidence=f"posting {i}", source=S.MANUAL,
                         observed_at=days_ago(age)) for i in range(count)]

    def test_ten_weak_signals_do_not_beat_one_strong_one_outright(self):
        """Additive strength would let noise outrank a referral."""
        weak = S.strength(self.many(10), NOW)
        self.assertLess(weak["score"], 1.0)

    def test_stale_signals_do_not_contribute(self):
        out = S.strength(self.many(5, age=400), NOW)
        self.assertEqual(out["count"], 0)
        self.assertEqual(len(out["stale"]), 5)
        self.assertEqual(out["score"], 0.0)

    def test_a_stale_signal_is_kept_not_deleted(self):
        """"We knew this and it aged out" is not "we never knew it"."""
        out = S.strength(self.many(2, age=400), NOW)
        self.assertEqual(len(out["stale"]), 2)

    def test_no_signals_is_zero_not_an_error(self):
        self.assertEqual(S.strength([], NOW)["score"], 0.0)


# --------------------------------------------------- derived, not stored

class FirstPartySignalsAreDerived(SignalTest):

    def test_a_confirmed_touch_becomes_a_contacted_signal(self):
        rec = self.touch(self.record())
        kinds = [s["type"] for s in S.derive(rec, WS)]
        self.assertIn(S.ENGAGED_CONTACTED, kinds)

    def test_a_planned_touch_does_not(self):
        """The rule the whole product runs on, here too."""
        rec = self.record()
        events.record(rec, events.PUSH_PREPARED, contact_key=JOHN,
                      channel="email", at=days_ago(3), sender_id="anna")
        self.assertEqual([s for s in S.derive(rec, WS)
                          if s["type"] == S.ENGAGED_CONTACTED], [])

    def test_a_positive_reply_becomes_a_positive_signal(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.POSITIVE)
        kinds = [s["type"] for s in S.derive(rec, WS)]
        self.assertIn(S.ENGAGED_POSITIVE, kinds)

    def test_each_reply_outcome_derives_its_own_signal(self):
        for outcome, expected in (
                (ap.NOT_NOW, S.ENGAGED_NOT_NOW),
                (ap.WRONG_PERSON, S.ENGAGED_WRONG_PERSON),
                (ap.LEFT_COMPANY, S.ENGAGED_LEFT_COMPANY),
                (ap.UNSUBSCRIBE, S.ENGAGED_UNSUBSCRIBE),
                (ap.ACCOUNT_DNC, S.ENGAGED_ACCOUNT_DNC)):
            rec = self.reply(self.record(f"sig-{outcome}"), JOHN, outcome)
            kinds = [s["type"] for s in S.derive(rec, WS)]
            self.assertIn(expected, kinds, outcome)

    def test_a_referral_becomes_a_referral_signal_naming_both_ends(self):
        rec = self.record()
        events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                      channel="email", referred_to=SARAH, at=days_ago(8),
                      provider_event_id="ref-1")
        found = [s for s in S.derive(rec, WS)
                 if s["type"] == S.ENGAGED_REFERRAL]
        self.assertEqual(len(found), 1)
        self.assertIn("John Smith", found[0]["evidence"])
        self.assertIn("Sarah Jones", found[0]["evidence"])

    def test_a_referral_is_counted_once_not_twice(self):
        """The edge and the reply that produced it are one fact.

        Both are recorded - the reply is classified `referral` and the edge
        names both ends - and emitting a signal from each counted one
        referral twice, which inflated the account's signal strength.
        """
        rec = self.record()
        events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                      channel="email", referred_to=SARAH, at=days_ago(8),
                      provider_event_id="ref-dup")
        self.reply(rec, JOHN, ap.REFERRAL, at=days_ago(8))
        found = [s for s in S.derive(rec, WS)
                 if s["type"] == S.ENGAGED_REFERRAL]
        self.assertEqual(len(found), 1, found)
        self.assertIn("Sarah Jones", found[0]["evidence"])

    def test_every_derived_signal_carries_evidence_and_a_source(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.POSITIVE)
        for entry in S.derive(rec, WS):
            self.assertTrue(entry["evidence"], entry["type"])
            self.assertEqual(entry["source"], S.FIRST_PARTY)

    def test_deriving_twice_changes_nothing(self):
        """Derived, not stored: reading cannot mutate."""
        rec = self.reply(self.touch(self.record()), JOHN, ap.POSITIVE)
        before = len(rec["events"])
        S.derive(rec, WS)
        S.derive(rec, WS)
        self.assertEqual(len(rec["events"]), before)

    def test_a_signal_cannot_change_what_a_reply_meant(self):
        rec = self.reply(self.record(), JOHN, ap.UNSUBSCRIBE)
        S.derive(rec, WS)
        self.assertEqual(ap.contact_state(rec["contacts"][0])[0], ap.SUPPRESS)


# ------------------------------------------------------------- priority

class TheScoreShowsItsWorking(SignalTest):

    def test_every_component_is_reported_with_its_reason(self):
        out = priority.assess(self.record(), WS, now=NOW)
        self.assertEqual({c["component"] for c in out["components"]},
                         set(priority.COMPONENTS))
        for part in out["components"]:
            self.assertTrue(part["why"], part["component"])
            self.assertIn("points", part)
            self.assertIn("weight", part)

    def test_the_points_sum_to_the_score(self):
        out = priority.assess(self.record(), WS, now=NOW)
        total = sum(c["points"] for c in out["components"])
        self.assertAlmostEqual(out["score"], round(total, 1), places=1)

    def test_a_positive_reply_raises_the_score(self):
        quiet = priority.assess(self.record("quiet"), WS, now=NOW)["score"]
        warm = priority.assess(
            self.reply(self.touch(self.record("warm")), JOHN, ap.POSITIVE),
            WS, now=NOW)["score"]
        self.assertGreater(warm, quiet)

    def test_the_weights_are_workspace_configurable(self):
        config = {"priority": {"weights": {priority.ENGAGEMENT: 0.9,
                                           priority.ICP_FIT: 0.1}}}
        share = priority.weights(config)
        self.assertAlmostEqual(sum(share.values()), 1.0, places=6)
        self.assertGreater(share[priority.ENGAGEMENT],
                           share[priority.ICP_FIT])

    def test_the_tiers_are_configurable(self):
        self.assertEqual(priority.tier_of(95), priority.HIGH)
        self.assertEqual(priority.tier_of(5), priority.LOW)
        config = {"priority": {"tiers": {priority.HIGH: 10}}}
        self.assertEqual(priority.tier_of(15, config), priority.HIGH)

    def test_why_now_is_a_sentence_not_a_score(self):
        out = priority.assess(
            self.reply(self.touch(self.record()), JOHN, ap.POSITIVE),
            WS, now=NOW)
        self.assertTrue(out["why_now"].endswith("."))
        self.assertNotIn(str(out["score"]), out["why_now"])

    def test_a_manual_signal_reaches_the_score(self):
        rec = self.record()
        extra = [S.signal(WS, S.HIRING_SURGE,
                          evidence="7 open project-management roles",
                          source=S.MANUAL, observed_at=days_ago(3),
                          confidence=S.HIGH)]
        without = priority.assess(rec, WS, now=NOW)["score"]
        with_signal = priority.assess(rec, WS, extra_signals=extra,
                                      now=NOW)["score"]
        self.assertGreater(with_signal, without)

    def test_a_stale_signal_is_shown_but_does_not_contribute(self):
        rec = self.record()
        extra = [S.signal(WS, S.WEBSITE_CHANGE, evidence="page changed",
                          source=S.MANUAL, observed_at=days_ago(400))]
        out = priority.assess(rec, WS, extra_signals=extra, now=NOW)
        self.assertTrue(out["stale_signals"])
        self.assertEqual(
            priority.assess(rec, WS, now=NOW)["score"], out["score"])


class OurOwnOutreachIsNotSomethingHappeningAtThem(SignalTest):
    """The double count, and the false sentence it produced.

    `signal strength` asks whether something is happening at the company.
    `engagement` asks how far we have got. Both were being fed the same
    derived events, so one reply scored twice - and an account we had
    merely written to last week reported "1 fresh signal(s)" in its why-now,
    which reads as interest from them rather than activity from us.
    """

    def test_a_touch_alone_scores_nothing_for_signal_strength(self):
        rec = self.touch(self.record())
        out = priority.assess(rec, WS, now=NOW)
        part = {c["component"]: c for c in out["components"]}
        self.assertEqual(part[priority.SIGNAL_STRENGTH]["raw"], 0.0)
        self.assertEqual(part[priority.SIGNAL_STRENGTH]["why"],
                         "no live signals")

    def test_a_touch_alone_does_not_claim_a_fresh_signal(self):
        rec = self.touch(self.record())
        out = priority.assess(rec, WS, now=NOW)
        self.assertNotIn("fresh signal", out["why_now"])

    def test_a_touch_still_counts_as_engagement(self):
        """Separated, not discarded. It is still worth something - just
        under the component that asks the question it answers."""
        rec = self.touch(self.record())
        out = priority.assess(rec, WS, now=NOW)
        part = {c["component"]: c for c in out["components"]}
        self.assertGreater(part[priority.ENGAGEMENT]["raw"], 0.0)

    def test_an_external_signal_does_score_for_signal_strength(self):
        rec = self.record()
        S.record(S.signal(WS, S.HIRING_SURGE, record_id=rec["id"],
                          evidence="7 open delivery roles", source=S.MANUAL,
                          observed_at=days_ago(3)))
        out = priority.assess(rec, WS, now=NOW)
        part = {c["component"]: c for c in out["components"]}
        self.assertGreater(part[priority.SIGNAL_STRENGTH]["raw"], 0.0)
        self.assertIn("fresh signal", out["why_now"])

    def test_a_reply_is_not_counted_twice(self):
        """The account with a positive reply and nothing observed should
        score its engagement once, not once per component that can see the
        same event."""
        replied = self.reply(self.touch(self.record("sig-replied")), JOHN,
                             ap.POSITIVE)
        out = priority.assess(replied, WS, now=NOW)
        part = {c["component"]: c for c in out["components"]}
        self.assertEqual(part[priority.SIGNAL_STRENGTH]["raw"], 0.0)
        self.assertEqual(part[priority.ENGAGEMENT]["raw"], 1.0)

    def test_the_engagement_signals_are_still_shown_on_the_account(self):
        """Excluded from the score, not from the page. A person reading the
        account still needs to see that we wrote to them."""
        rec = self.touch(self.record())
        out = priority.assess(rec, WS, now=NOW)
        kinds = [s["type"] for s in out["signals"]]
        self.assertIn(S.ENGAGED_CONTACTED, kinds)


class ItReadsTheVerdictWhereQualifyWroteIt(SignalTest):
    """A scorer reading the wrong path scores everything zero.

    It also looks exactly like a working scorer: components render, points
    add up, tiers come out. The only symptom is that every account is low,
    which reads as a quiet estate rather than as a bug. This is the test
    that fails when the path moves.
    """

    def qualified(self, score=86, status="qualified", tier="A"):
        rec = self.record()
        rec["qualification"] = {"verdict": {
            "icp_score": score, "icp_status": status, "icp_tier": tier}}
        return rec

    def test_a_qualified_account_scores_on_fit(self):
        raw, why, value = priority._icp_fit(self.qualified())
        self.assertGreater(raw, 0.8)
        self.assertEqual(value, 86)
        self.assertIn("86", why)
        self.assertIn("tier A", why)

    def test_a_rejected_account_scores_nothing_on_fit(self):
        rec = self.qualified(status="rejected")
        raw, why, _ = priority._icp_fit(rec)
        self.assertEqual(raw, 0.0)
        self.assertIn("rejected", why)

    def test_no_verdict_says_so_rather_than_scoring_zero_silently(self):
        raw, why, _ = priority._icp_fit(self.record())
        self.assertEqual(raw, 0.0)
        self.assertIn("no ICP verdict", why)

    def test_the_fit_component_reaches_the_score(self):
        quiet = priority.assess(self.record("plain"), WS, now=NOW)
        good = priority.assess(self.qualified(), WS, now=NOW)
        self.assertGreater(good["score"], quiet["score"])
        fit = next(c for c in good["components"]
                   if c["component"] == priority.ICP_FIT)
        self.assertGreater(fit["points"], 0)


class PriorityIsNotPermission(SignalTest):
    """The most important class in this file."""

    def test_a_suppressed_account_still_scores(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.ACCOUNT_DNC)
        out = priority.assess(rec, WS, now=NOW)
        self.assertGreater(out["score"], 0)

    def test_but_it_is_reported_as_not_eligible(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.ACCOUNT_DNC)
        out = priority.assess(rec, WS, now=NOW)
        self.assertFalse(out["eligibility"]["eligible"])
        self.assertIn("asked us to stop", out["eligibility"]["blocked"])

    def test_a_held_account_is_reported_as_held(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.POSITIVE)
        out = priority.assess(rec, WS, now=NOW)
        self.assertFalse(out["eligibility"]["eligible"])

    def test_eligibility_is_never_folded_into_the_score(self):
        """A score that quietly dropped for suppression would hide it."""
        rec = self.reply(self.touch(self.record()), JOHN, ap.POSITIVE)
        out = priority.assess(rec, WS, now=NOW)
        self.assertNotIn("eligib",
                         " ".join(c["component"] for c in out["components"]))

    def test_a_quiet_account_is_eligible(self):
        out = priority.assess(self.record(), WS, now=NOW)
        self.assertTrue(out["eligibility"]["eligible"])


class ReadingTheEstateDoesNotReReadTheFilePerAccount(SignalTest):
    """The quadratic one, measured before it was fixed.

    `for_record` reads the whole signals file. Called once per account it
    is correct; called in a loop it multiplies the file size by the estate
    size. 500 accounts against a 5,000-signal file took 19 seconds and
    2,000 took 96, which is invisible against a 33-account demo and
    fatal against a real audience.

    Asserted by counting reads rather than by timing anything, because a
    wall-clock assertion is a test that fails on a busy machine.
    """

    def reads(self, run):
        """How many times the signals file is read while `run` executes.

        Counts `signals.load`, which is the only thing that opens it.
        """
        count = {"n": 0}
        original = S.load

        def counting(*a, **kw):
            count["n"] += 1
            return original(*a, **kw)

        S.load = counting
        try:
            run()
        finally:
            S.load = original
        return count["n"]

    def estate(self, count=25):
        rows = []
        for i in range(count):
            rec = store.new_record(f"scale-{i}", "domains", WS, f"Co {i}",
                                   f"co{i}.test")
            rec["contacts"] = [{"key": JOHN, "name": "A Person",
                                "email": f"a@co{i}.test", "selected": True}]
            rows.append(rec)
        store.save(rows)
        S.install([S.signal(WS, S.HIRING_SURGE, record_id=f"scale-{i}",
                            evidence="7 open delivery roles listed",
                            source=S.MANUAL, observed_at=days_ago(2))
                   for i in range(count)])
        return rows

    def test_an_index_is_read_once_for_the_whole_estate(self):
        rows = self.estate()

        def with_index():
            index = S.index(WS)
            for rec in rows:
                priority.assess(rec, WS, now=NOW, signal_index=index)

        self.assertEqual(self.reads(with_index), 1)

    def test_without_one_every_account_reads_it_again(self):
        """The behaviour the index exists to replace, pinned so the
        comparison above cannot quietly become meaningless."""
        rows = self.estate()

        def without_index():
            for rec in rows:
                priority.assess(rec, WS, now=NOW)

        self.assertEqual(self.reads(without_index), len(rows))

    def test_the_index_returns_the_same_signals_for_an_account(self):
        """Faster and identical, or it is not a fix."""
        rows = self.estate(5)
        index = S.index(WS)
        for rec in rows:
            with_index = priority.assess(rec, WS, now=NOW,
                                         signal_index=index)
            without = priority.assess(rec, WS, now=NOW)
            self.assertEqual(with_index["score"], without["score"])
            self.assertEqual([s["type"] for s in with_index["signals"]],
                             [s["type"] for s in without["signals"]])

    def test_the_index_is_scoped_to_one_workspace(self):
        self.estate(3)
        S.record(S.signal("contactout", S.FUNDING, record_id="scale-0",
                          evidence="Series B reported elsewhere",
                          source=S.MANUAL, observed_at=days_ago(1)))
        index = S.index(WS)
        kinds = [s["type"] for s in index.get("scale-0") or []]
        self.assertEqual(kinds, [S.HIRING_SURGE])


class WhyAnAccountIsHeldIsASentence(SignalTest):
    """These strings reach a client-facing reporting dimension.

    "held: unclassified" is true and tells a reader nothing unless they
    already know the taxonomy, which a client does not.
    """

    def test_an_unclassified_reply_says_what_that_means(self):
        rec = self.reply(self.touch(self.record()), JOHN, ap.UNKNOWN)
        out = priority.assess(rec, WS, now=NOW)
        self.assertEqual(out["eligibility"]["blocked"],
                         "held: a reply nobody has classified yet")

    def test_every_outcome_that_can_hold_has_a_sentence(self):
        """A category name leaking through is the defect this prevents."""
        for outcome, sentence in priority.HELD_BECAUSE.items():
            self.assertTrue(sentence.startswith("held: "), outcome)
            self.assertGreater(len(sentence), len("held: ") + 12, outcome)
            self.assertNotEqual(
                sentence[6:].strip(),
                (ap.OUTCOME_LABEL.get(outcome) or "").lower(), outcome)

    def test_an_unknown_outcome_falls_back_to_a_readable_sentence(self):
        self.assertEqual(
            priority.HELD_BECAUSE.get("something-new",
                                      "held while a conversation is live"),
            "held while a conversation is live")


class TenancyTravelsWithTheAssessment(SignalTest):

    def test_the_assessment_names_its_workspace(self):
        out = priority.assess(self.record(), WS, now=NOW)
        self.assertEqual(out["workspace"], WS)

    def test_it_reads_only_the_record_it_was_given(self):
        mine = self.reply(self.touch(self.record("mine")), JOHN, ap.POSITIVE)
        theirs = self.record("theirs")
        out = priority.assess(theirs, WS, now=NOW)
        self.assertEqual(out["record_id"], "theirs")
        for entry in out["signals"]:
            self.assertEqual(entry["record_id"], "theirs")
        self.assertTrue(mine)


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------- manual entry
#
# Storage existed before any screen did. These are about the door: who may
# open it, what may go through it, and the one thing that may not - a
# person writing down something the event log already knows.


class EntryTest(ProviderTest):
    """A real workspace, a real repo, a real permission check.

    Built here rather than on `CampaignTest` because the question under
    test is a permission one, and a permission test that fakes the
    membership is testing nothing.
    """

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-signal-entry-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                      "SIGNALS", "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")

        from src.web import demodata
        demodata.install_configs()

        workspaces.ensure("productive", "Productive", client="productive")
        workspaces.ensure("contactout", "ContactOut", client="contactout")
        for email, name, role in (
                ("op@x.test", "Op", workspaces.OPERATOR),
                ("rev@x.test", "Rev", workspaces.REVIEWER),
                ("view@x.test", "View", workspaces.VIEWER)):
            workspaces.add_user(email, name)
            workspaces.assign(email, "productive", role)

        rec = store.new_record("acme", "domains", "productive", "Acme Ltd",
                               "acme.test")
        rec["contacts"] = [{"key": JOHN, "name": "John Smith",
                            "email": "john@acme.test", "selected": True}]
        theirs = store.new_record("theirs", "domains", "contactout",
                                  "Other Ltd", "other.test")
        store.save([rec, theirs])

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def repo(self, email="op@x.test", workspace="productive"):
        return repo_module.Repo.for_user(email, workspace)

    def enter(self, repo=None, record_id="acme", kind=S.HIRING_SURGE,
              evidence="7 open delivery roles on the careers page", **kw):
        return api.record_signal(repo or self.repo(), record_id, kind,
                                 evidence, **kw)


class OnlyAnOperatorMayRecordOne(EntryTest):
    """Reading the estate and changing what it is worked in are different
    powers. A reviewer has the first."""

    def test_an_operator_may(self):
        self.assertIsNotNone(self.enter())

    def test_a_reviewer_may_not(self):
        with self.assertRaises(workspaces.NotPermitted):
            self.enter(self.repo("rev@x.test"))

    def test_a_viewer_may_not(self):
        with self.assertRaises(workspaces.NotPermitted):
            self.enter(self.repo("view@x.test"))

    def test_the_refusal_happens_before_anything_is_written(self):
        with self.assertRaises(workspaces.NotPermitted):
            self.enter(self.repo("rev@x.test"))
        self.assertEqual(S.load("productive"), [])

    def test_a_reviewer_is_told_the_form_is_not_for_them(self):
        form = api.signal_form(self.repo("rev@x.test"), "acme")
        self.assertFalse(form["may_record"])
        self.assertTrue(api.signal_form(self.repo(), "acme")["may_record"])


class EngagementCannotBeEnteredByHand(EntryTest):
    """The rule this whole entry path is shaped around.

    Reply state comes from the event log. A person typing "they replied"
    would create a second copy of it, and between two copies the
    handwritten one is the one that goes stale. Guarded twice: the form
    does not offer the types, and `record()` refuses them at the door.
    """

    def test_the_api_refuses_an_engagement_type(self):
        with self.assertRaises(api.SignalRefused):
            self.enter(kind=S.ENGAGED_POSITIVE,
                       evidence="he said yes on the phone")

    def test_storage_refuses_one_even_wearing_a_manual_source(self):
        entry = S.signal("productive", S.ENGAGED_REFERRAL,
                         evidence="passed us to the CFO", source=S.MANUAL)
        with self.assertRaises(ValueError):
            S.record(entry)

    def test_an_unknown_type_is_told_it_is_unknown(self):
        """Not "engagement comes from the event log". Somebody who
        mistyped a type needs the mistake explained, not the rule."""
        with self.assertRaises(api.SignalRefused) as caught:
            self.enter(kind="hirring_surge")
        self.assertIn("unknown signal type", str(caught.exception))

        with self.assertRaises(api.SignalRefused) as caught:
            self.enter(kind=S.ENGAGED_MEETING)
        self.assertIn("event log", str(caught.exception))

    def test_the_form_does_not_offer_them(self):
        offered = {t["type"] for t in api.signal_form(self.repo())["types"]}
        self.assertNotIn(S.ENGAGED_POSITIVE, offered)
        self.assertNotIn(S.ENGAGED_MEETING, offered)
        self.assertIn(S.HIRING_SURGE, offered)
        self.assertIn(S.JOB_CHANGE, offered)

    def test_every_offered_type_can_actually_be_stored(self):
        """A form that offers a type the door refuses is a form that
        produces an error message instead of a signal."""
        for kind in S.enterable():
            S.record(S.signal("productive", kind, evidence="something seen",
                              source=S.MANUAL))
        self.assertEqual(len(S.load("productive")), len(S.enterable()))


class EvidenceHasToBeQuotable(EntryTest):

    def test_a_blank_is_refused(self):
        with self.assertRaises(api.SignalRefused):
            self.enter(evidence="   ")

    def test_a_word_is_refused(self):
        """"growing" is what somebody types to get past a required
        field. It is not an observation."""
        with self.assertRaises(api.SignalRefused):
            self.enter(evidence="growing")

    def test_the_refusal_says_what_good_looks_like(self):
        with self.assertRaises(api.SignalRefused) as caught:
            self.enter(evidence="yes")
        self.assertIn("careers page", str(caught.exception))

    def test_a_real_observation_is_kept_whole(self):
        entry = self.enter(evidence="7 open delivery roles on the careers "
                                    "page, posted since June")
        self.assertIn("posted since June", entry["evidence"])


class WhatEntryRecordsAboutItself(EntryTest):

    def test_it_is_marked_manual_and_attributed(self):
        entry = self.enter()
        self.assertEqual(entry["source"], S.MANUAL)
        self.assertEqual(entry["created_by"], "op@x.test")

    def test_an_undated_entry_is_dated_now_not_left_empty(self):
        """Undated signals are treated as one half-life old. That is right
        for a signal whose date was never known and wrong for one somebody
        is entering as they see it."""
        entry = self.enter()
        self.assertTrue(entry["observed_at"])
        self.assertEqual(S.weight_at(entry)["freshness"], S.FRESH)

    def test_a_given_date_is_kept(self):
        entry = self.enter(observed_at=days_ago(200))
        self.assertEqual(entry["observed_at"], days_ago(200))

    def test_it_lands_in_the_audit_log_with_its_evidence(self):
        self.enter()
        rows = workspaces.audit("productive")
        recorded = [r for r in rows if r["action"] == "signal.recorded"]
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["resource_id"], "acme")
        self.assertIn("careers page", recorded[0]["reason"])

    def test_it_reaches_the_score_it_was_entered_to_affect(self):
        before = priority.assess(self.repo().record("acme"), "productive")
        self.enter()
        after = priority.assess(self.repo().record("acme"), "productive")
        self.assertGreater(after["score"], before["score"])

    def test_a_signal_does_not_make_a_blocked_account_eligible(self):
        rec = self.repo().record("acme")
        ap.apply_reply(rec, JOHN, ap.ACCOUNT_DNC, workspace="productive")
        store.save([rec])
        self.enter()
        out = priority.assess(self.repo().record("acme"), "productive")
        self.assertFalse(out["eligibility"]["eligible"])


class EntryIsScopedToOneWorkspace(EntryTest):

    def test_another_tenants_record_is_not_writable(self):
        with self.assertRaises(repo_module.CrossClientAccess):
            self.enter(record_id="theirs")
        self.assertEqual(S.load("contactout"), [])

    def test_an_unknown_record_writes_nothing(self):
        self.assertIsNone(self.enter(record_id="no-such-account"))
        self.assertEqual(S.load("productive"), [])

    def test_a_contact_from_elsewhere_is_refused(self):
        with self.assertRaises(api.SignalRefused):
            self.enter(contact_key="somebody-else")

    def test_the_signal_carries_the_workspace_that_wrote_it(self):
        self.assertEqual(self.enter()["workspace"], "productive")


class TheEstateWalksReadTheSignalFileOnce(ProviderTest):
    """`revival.candidates` and `refresh.plan` both walk every account.

    Both took a `signal_index` parameter and neither built one, so every
    account re-read the whole signal file - the exact pattern `priority`
    carries a warning about, repeated in two newer modules.

    Measured before the fix at 9.4ms an account and rising against a
    2,000-signal file, and 0.15ms an account and flat after it. Asserted
    by counting reads rather than by timing, because a wall-clock
    assertion fails on a busy machine.
    """

    def reads(self, run):
        count = {"n": 0}
        original = S.load

        def counting(*a, **kw):
            count["n"] += 1
            return original(*a, **kw)

        S.load = counting
        try:
            run()
        finally:
            S.load = original
        return count["n"]

    def estate(self, count=25):
        rows = []
        for i in range(count):
            rec = store.new_record(f"walk-{i}", "domains", WS, f"Co {i}",
                                   f"co{i}.test")
            rec["contacts"] = [{"key": JOHN, "name": "A Person",
                                "email": f"a@co{i}.test", "selected": True,
                                "angle": "finance"}]
            rec["events"] = [{"type": events.PUSH_MARKED, "contact": JOHN,
                              "channel": "email", "step": "day1",
                              "at": "2026-01-05T09:00:00+00:00",
                              "sender_id": "mark"}]
            rows.append(rec)
        store.save(rows)
        S.install([S.signal(WS, S.HIRING_SURGE, record_id=f"walk-{i}",
                            evidence="7 open delivery roles listed",
                            source=S.MANUAL, observed_at=days_ago(2))
                   for i in range(count)])
        return rows

    def test_revival_reads_it_once_for_the_whole_estate(self):
        rows = self.estate()
        self.assertEqual(
            self.reads(lambda: revival.candidates(
                rows, today="2026-08-31", config={}, workspace=WS)),
            1)

    def test_refresh_reads_it_once_for_the_whole_estate(self):
        rows = self.estate()
        self.assertLessEqual(
            self.reads(lambda: refresh.plan(
                rows, today="2026-08-31", config={}, workspace=WS,
                suppressed=set())),
            1)

    def test_a_caller_may_still_supply_its_own_index(self):
        """A screen that already built one must not cause a second read."""
        rows = self.estate()
        index = S.index(WS)
        self.assertEqual(
            self.reads(lambda: revival.candidates(
                rows, today="2026-08-31", config={}, workspace=WS,
                signal_index=index)),
            0)

    def test_the_reads_do_not_grow_with_the_estate(self):
        """The property that matters. One read for ten accounts and one for
        fifty is the difference between linear and quadratic."""
        small = self.reads(lambda: revival.candidates(
            self.estate(10), today="2026-08-31", config={}, workspace=WS))
        large = self.reads(lambda: revival.candidates(
            self.estate(50), today="2026-08-31", config={}, workspace=WS))
        self.assertEqual(small, large)
