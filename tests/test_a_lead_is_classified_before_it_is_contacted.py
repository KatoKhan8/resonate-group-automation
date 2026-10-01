#!/usr/bin/env python3
"""Five outcomes, mutually exclusive, and only one of them may be sent to.

THE OPERATOR'S PERMANENT RULE, 2026-10-01, under "LEAD KLASIFIKACIJA" in
`docs/OPERATING-MODE.md`. It replaces "zero previous emails", and it replaces
the 30-day cold-or-not binary that briefly stood in its place.

    1 BLOCKED   a negative reply, DNC, unsubscribe, opt-out, bounce or invalid
                address, operator exclusion or suppression list, FROM ANY
                SOURCE. A live conversation or a positive reply is also this
                step: it goes to a HUMAN.
    2 ON HOLD   currently in a live campaign belonging to ANYONE, or a paused
                campaign still holding non-terminal rows.
    3 OURS?     did RESONATE OS contact them, per campaigns POSITIVELY RECORDED
                IN `work/campaigns.jsonl`?  YES -> REVIVAL.  NO -> COLD,
                however much manual history exists.  Undeterminable -> BLOCKED.
    4 GAP       a COLD lead touched by a manual campaign inside N days waits.
                N IS CONFIG.
    5 REVIVAL   proposed, NOT approved: classified only, never sent.

THE THREE THINGS THIS FILE EXISTS TO PIN DOWN, each measured rather than
imagined:

1. MANUAL HISTORY DOES NOT MAKE A LEAD OURS. Campaigns 274, 327, 328 and 352
   have sent roughly 209,000 emails between them and NONE of them is in
   `work/campaigns.jsonl`, which holds exactly twenty bound provider campaigns,
   451 to 506. That absence IS the ledger proof. A lead mailed twenty times by
   352 and never by us is COLD, and a lead mailed once by 491 is a STARI LEAD.
   `WhoSentItDecidesTheTrack` asserts both directions on identical dates.

2. A PAUSE IS NOT AN ENDING. 327/328/352 still hold 406 / 1,948 / 406 scheduled
   queue rows, so they will send again; and 1,555 rows of our own legacy
   campaigns sit behind a pause. Their members are ON HOLD, not COLD, until the
   operator formally closes them.

3. THE STATUS IS AUTHORITATIVE, NOT THE COUNTER. grayloon.com carries campaign
   274 with membership status `replied` and `replies: 0` on the same row.

EVERY FIXTURE IS A DOCUMENTED PROVIDER SHAPE, NOT AN INVENTION. The lead row
carries the keys `GET /leads/{id}` returns, with `overall_stats` and
`lead_campaign_data` as `docs/BISON-PROVIDER-TRUTH-2026-09-14.md` recorded them
field by field; the queue row carries the twenty-one fields
`GET /leads/{id}/scheduled-emails` returns; the conversation row carries
`correspondentProfile`, `linkedInAccount`, `totalMessages`, `lastMessageAt` and
`lastMessageSender` as HeyReach returns them. Each is read by the REAL parser -
`collision.touches_of` and `collision.linkedin_touches_of` - so a fixture cannot
drift into a shape the provider does not produce, and nothing under test is
stubbed out. `os_campaigns` and `bindings` are passed explicitly, so no test
here can reach the provider or depend on a worktree's own `work/`.

NOTHING HERE ASSERTS A LOG STRING. Every assertion is on the outcome, the
decision, and the eligibility reason the send path actually consumes.
"""
import datetime
import unittest

from src import collision, eligibility, replies
from tests.base import QueueTest
from tests.test_eligibility import GateTest

# Provider campaign ids, used as the real ones they are.
OS_CAMPAIGNS = frozenset({451, 481, 484, 485, 487, 489, 491, 492, 493, 494,
                          495, 496, 497, 498, 500, 501, 503, 504, 505, 506})
OURS = 491              # a Resonate OS campaign, in the ledger
OURS_LEGACY = 503       # one of the legacy campaigns behind a pause
MANUAL = 352            # internal/manual: ~209k sends, NOT in the ledger
MANUAL_2 = 274          # the grayloon `replied`/`replies: 0` campaign

SLUG = "dana-whitfield-kestrelwharf"
ADDRESS = "dana@kestrelwharf.test"

#: A MODULE-LEVEL sentinel, and it has to be. `def f(x=object())` then
#: `if x is object()` compares against a FRESH object on every call, so the
#: default never matches and every fixture silently takes the override branch.
#: That bug produced 25 spurious failures the first time this file ran, and it
#: was in the fixture rather than in the rule.
_UNSET = object()


def _ago(days):
    """An aware ISO timestamp `days` days before now, as the provider writes it.

    `Z`-suffixed UTC, which is the shape `sent_at` and `lastMessageAt` both come
    back in. STAMPED AT CALL TIME rather than written as a literal, for the
    reason `tests.base.mx_cache_entries` stamps `checked_at`: these comparisons
    are against the real clock, so a literal date would walk across a boundary
    and this file would start failing on a day nobody committed anything.
    """
    when = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days))
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def membership(campaign_id, status, emails_sent=0, replies_=0,
               interested=False):
    """One `lead_campaign_data` entry, in the provider's own six fields."""
    return {"campaign_id": campaign_id, "status": status,
            "emails_sent": emails_sent, "replies": replies_, "opens": 0,
            "interested": interested}


def lead_row(memberships=(), emails_sent=0, replies_=0, status="unverified"):
    """A lead row exactly as `GET /leads/{id}` returns one."""
    return {
        "id": 172105,
        "uuid": "11111111-2222-3333-4444-555555555555",
        "first_name": "Dana", "last_name": "Whitfield",
        "email": ADDRESS, "title": "Operations Director",
        "company": "Kestrel Wharf", "notes": None, "status": status,
        "custom_variables": [], "tags": [],
        "lead_campaign_data": list(memberships),
        "overall_stats": {"emails_sent": emails_sent, "opens": 0,
                          "replies": replies_, "unique_opens": 0,
                          "unique_replies": replies_},
        "created_at": _ago(400), "updated_at": _ago(1),
    }


def sent_row(campaign_id, days_ago, status="sent", sent_at=_UNSET):
    """A queue row as `GET /leads/{id}/scheduled-emails` returns one.

    `sent_at` may be overridden with None to build the shape the provider really
    does write - a row reading `sent` that carries no date - which is not a send
    and must not be read as one.
    """
    return {
        "id": 22290485 + campaign_id * 100 + days_ago,
        "campaign_id": campaign_id,
        "campaign": {"id": campaign_id, "status": "sequence_finished"},
        "lead": {"id": 172105, "email": ADDRESS},
        "sender_email": {"id": 9001, "email": "ops@sender.test"},
        "sequence_step_id": 5500 + days_ago,
        "status": status,
        "sent_at": _ago(days_ago) if sent_at is _UNSET else sent_at,
        "scheduled_date": _ago(days_ago),
        "scheduled_date_local": _ago(days_ago),
        "email_subject": "a subject", "email_body": "a body",
        "opens": 0, "replies": 0, "unique_opens": 0, "unique_replies": 0,
        "clicks": 0, "interested": False, "thread_reply": False,
        "raw_message_id": f"<{campaign_id}.{days_ago}@sender.test>",
    }


def conversation(days_ago, total_messages=1, from_them=False, seat="77",
                 slug=SLUG, last_message_at=_UNSET):
    """A HeyReach conversation row, scoped to one of our own seats."""
    return {
        "id": f"conv-{days_ago}-{slug}",
        "correspondentProfile": {
            "profileUrl": f"https://www.linkedin.com/in/{slug}/",
            "firstName": "Dana", "lastName": "Whitfield",
            "companyName": "Kestrel Wharf"},
        "linkedInAccount": {"id": seat, "firstName": "Marko",
                            "lastName": "Sender"},
        "totalMessages": total_messages,
        "lastMessageAt": (_ago(days_ago) if last_message_at is _UNSET
                          else last_message_at),
        "lastMessageSender": ("correspondent" if from_them else "user"),
    }


def email_side(memberships=(), emails_sent=None, replies_=0, sent_rows=(),
               complete=True, lookup=collision.LOOKUP_OK,
               sends_lookup=collision.LOOKUP_OK, lead_status="unverified",
               os_campaigns=OS_CAMPAIGNS, ledger_readable=True):
    """The email half, built through the REAL parser from a real row shape.

    `emails_sent` defaults to the sum the memberships claim, so a fixture cannot
    accidentally claim more sends than it dates - which is itself a block, and
    would make a test pass for the wrong reason.
    """
    if emails_sent is None:
        emails_sent = sum(int(m.get("emails_sent") or 0) for m in memberships)
    return collision.email_history(
        lead_row=lead_row(memberships, emails_sent, replies_, lead_status),
        lookup=lookup, sent_rows=sent_rows, sends_lookup=sends_lookup,
        sends_complete=complete, bindings={}, os_campaigns=os_campaigns,
        ledger_readable=ledger_readable)


def linkedin_side(rows=(), lookup=collision.LOOKUP_OK, slug=SLUG,
                  ours_recorded=False):
    return collision.linkedin_history(conversation_rows=rows, slug=slug,
                                      lookup=lookup,
                                      ours_recorded=ours_recorded)


def dossier(email=None, link=None, suppression=(), reply_class=None,
            channel=eligibility.EMAIL):
    return collision.recontact_dossier(
        email=email if email is not None else email_side(),
        linkedin_=link if link is not None else linkedin_side(),
        suppression=suppression, reply_class=reply_class,
        candidate_channel=channel)


class ClassifyTest(QueueTest):
    """Assert the OUTCOME, the decision, and the code the send path consumes."""

    #: Revival approved OFF, which is the operator's actual state. Tests that
    #: care about the approval flag set it explicitly.
    OPTIONS = None

    def verdict(self, dos, now=None, options=None):
        decision, klass, why = collision.classify(
            dos, now=now, options=options if options is not None else self.OPTIONS)
        self.assertTrue(why and why.strip(),
                        "every outcome must carry a sentence for an operator")
        self.assertIn(klass, collision.CLASSES, f"{klass!r} is not an outcome")
        return decision, klass

    def assertClass(self, dos, klass, reason, decision=None, now=None,
                    options=None, why=""):
        got_decision, got = self.verdict(dos, now=now, options=options)
        self.assertEqual(klass, got, why)
        if decision is not None:
            self.assertEqual(decision, got_decision, why)
        answer = eligibility.recontact(
            dos, now=now, options=options if options is not None else self.OPTIONS)
        self.assertEqual(reason, answer["reason"], why)
        self.assertEqual(klass, answer["klass"])
        self.assertTrue(answer["asked"])

    def assertBlocked(self, dos, **kw):
        self.assertClass(dos, collision.CLASS_BLOCKED,
                         eligibility.BLOCKED_RECONTACT_REFUSED,
                         decision=collision.STOP, **kw)

    def assertOnHold(self, dos, **kw):
        self.assertClass(dos, collision.CLASS_ON_HOLD,
                         eligibility.HELD_IN_A_LIVE_CAMPAIGN,
                         decision=collision.HOLD, **kw)

    def assertUnknown(self, dos, **kw):
        self.assertClass(dos, collision.CLASS_UNKNOWN,
                         eligibility.BLOCKED_RECONTACT_UNKNOWN,
                         decision=collision.STOP, **kw)

    def assertRevival(self, dos, **kw):
        self.assertClass(dos, collision.CLASS_REVIVAL,
                         eligibility.HELD_REVIVAL_NOT_APPROVED, **kw)

    def assertCold(self, dos, **kw):
        self.assertClass(dos, collision.CLASS_COLD, None,
                         decision=collision.ALLOW, **kw)

    def assertWaiting(self, dos, **kw):
        self.assertClass(dos, collision.CLASS_COLD_WAITING,
                         eligibility.HELD_MANUAL_CONTACT_GAP,
                         decision=collision.HOLD, **kw)


# ---- a reusable "would be cold" baseline -----------------------------------

def cold_baseline(days=200, campaign=MANUAL):
    """Touched only by a manual campaign, long ago, finished. COLD."""
    return email_side([membership(campaign, "sequence_finished", emails_sent=1)],
                      sent_rows=[sent_row(campaign, days)])


# 1 ------------------------------------------------------------------------
class StepOneIsForever(ClassifyTest):

    def test_a_dnc_from_a_manual_campaign_blocks(self):
        """Required case 1. The SOURCE does not matter; the instruction does."""
        self.assertBlocked(dossier(cold_baseline(), suppression=("agency_dnc",)),
                           why="a DNC recorded against manual work is still a "
                               "DNC, and 200 days of silence does not lift it")
        self.assertCold(dossier(cold_baseline()),
                        why="the control: the only difference is the DNC entry")

    def test_every_local_exclusion_source_blocks(self):
        """Operator exclusion, suppression list, unsubscribe, hand work."""
        for source in ("agency_dnc", "operator_excluded", "client_suppressed",
                       "unsubscribed", "record_do_not_contact", "set_aside",
                       "manual_hand_exclusion"):
            with self.subTest(source=source):
                self.assertBlocked(dossier(cold_baseline(),
                                           suppression=(source,)))

    def test_a_negative_reply_a_year_ago_blocks(self):
        """Required case 2. A reply is not a date problem."""
        answered = email_side(
            [membership(MANUAL, collision.REPLIED, emails_sent=3)],
            sent_rows=[sent_row(MANUAL, d) for d in (380, 375, 370)])
        self.assertBlocked(dossier(answered, reply_class=replies.NEGATIVE),
                           why="a year is still not long enough")

    def test_it_is_still_blocked_five_years_later(self):
        """FOREVER means forever. The CLOCK moves, the fixture does not."""
        far = (datetime.datetime.now(datetime.timezone.utc)
               + datetime.timedelta(days=5 * 365))
        answered = email_side(
            [membership(MANUAL, collision.REPLIED, emails_sent=3)],
            sent_rows=[sent_row(MANUAL, d) for d in (380, 375, 370)])
        self.assertBlocked(dossier(answered, reply_class=replies.NEGATIVE),
                           now=far)
        # The control for the control: on that same far-future clock, a lead
        # whose ONLY difference is that nobody replied is COLD. So the
        # assertion above is about the reply and not about the clock.
        self.assertCold(dossier(cold_baseline()), now=far)

    def test_a_positive_reply_blocks_too_and_goes_to_a_person(self):
        """Step 1's second half. Blocked, and for a different reason."""
        answered = email_side(
            [membership(MANUAL, collision.REPLIED, emails_sent=1)],
            sent_rows=[sent_row(MANUAL, 380)])
        for name in sorted(collision.HUMAN_REPLIES):
            with self.subTest(human=name):
                self.assertBlocked(dossier(answered, reply_class=name))
        for name in sorted(collision.PERMANENT_REPLIES):
            with self.subTest(permanent=name):
                self.assertBlocked(dossier(answered, reply_class=name))

    def test_an_unclassified_reply_blocks_rather_than_passing(self):
        """The default has to be the safe half, and this pins which one."""
        answered = email_side(
            [membership(MANUAL, collision.REPLIED, emails_sent=1)],
            sent_rows=[sent_row(MANUAL, 380)])
        for unclassified in (None, "", "a-class-nobody-added-yet",
                             replies.UNKNOWN):
            with self.subTest(reply_class=unclassified):
                self.assertBlocked(dossier(answered, reply_class=unclassified))

    def test_a_bounce_blocks_from_either_field(self):
        """A bounce is about the ADDRESS and survives whoever found it."""
        self.assertBlocked(dossier(email_side(
            [membership(MANUAL, collision.BOUNCED, emails_sent=1)],
            sent_rows=[sent_row(MANUAL, 400)])))
        self.assertBlocked(dossier(email_side(
            [membership(MANUAL, "sequence_finished", emails_sent=1)],
            lead_status=collision.BOUNCED,
            sent_rows=[sent_row(MANUAL, 400)])))


# 2 ------------------------------------------------------------------------
class StepTwoIsAnybodysLiveCampaign(ClassifyTest):

    def test_an_active_internal_campaign_puts_the_lead_on_hold(self):
        """Required case 3. 327/328/352 still hold queue rows: they WILL send."""
        for status in sorted(collision.ACTIVE_MEMBERSHIP):
            with self.subTest(status=status):
                self.assertOnHold(dossier(email_side(
                    [membership(MANUAL, status, emails_sent=4)],
                    sent_rows=[sent_row(MANUAL, d) for d in
                               (400, 380, 360, 340)])),
                    why=f"{status!r} on an internal campaign is still a live "
                        f"campaign, and ON HOLD is not COLD")

    def test_an_active_campaign_of_ours_also_puts_the_lead_on_hold(self):
        """Step 2 says ANYONE, so ownership must not change the outcome."""
        self.assertOnHold(dossier(email_side(
            [membership(OURS, collision.IN_SEQUENCE, emails_sent=4)],
            sent_rows=[sent_row(OURS, d) for d in (400, 380, 360, 340)])))

    def test_a_paused_legacy_os_campaign_with_a_live_row_is_on_hold(self):
        """Required case 4. The 1,555 rows behind a pause are THIS case.

        A resume flips `sending_paused` back to `in_sequence`, so the rows are
        still there. ON HOLD until the operator formally CLOSES the campaign -
        and in particular NOT revival, even though the campaign is ours.
        """
        self.assertOnHold(dossier(email_side(
            [membership(OURS_LEGACY, collision.SENDING_PAUSED, emails_sent=2)],
            sent_rows=[sent_row(OURS_LEGACY, 200), sent_row(OURS_LEGACY, 190)])),
            why="ours, paused, rows still live: ON HOLD rather than REVIVAL")

    def test_the_same_legacy_campaign_once_the_row_is_terminal_is_revival(self):
        """The control. Same campaign, same dates; the ROW is terminal now.

        This is what formally closing a campaign looks like to this gate, and
        it is the one change that moves the lead from step 2 to step 3.
        """
        self.assertRevival(dossier(email_side(
            [membership(OURS_LEGACY, "sequence_finished", emails_sent=2)],
            sent_rows=[sent_row(OURS_LEGACY, 200),
                       sent_row(OURS_LEGACY, 190)])),
            decision=collision.HOLD)

    def test_a_paused_manual_campaign_with_a_live_row_is_on_hold(self):
        """And the control in the other direction: not ours, same outcome."""
        self.assertOnHold(dossier(email_side(
            [membership(MANUAL, collision.SENDING_PAUSED, emails_sent=2)],
            sent_rows=[sent_row(MANUAL, 200), sent_row(MANUAL, 190)])))

    def test_on_hold_outranks_the_gap_and_the_revival_minimum(self):
        """Step 2 comes before steps 3-5, so a recent touch cannot re-label it."""
        self.assertOnHold(dossier(email_side(
            [membership(MANUAL, collision.IN_SEQUENCE, emails_sent=1)],
            sent_rows=[sent_row(MANUAL, 1)])))
        self.assertOnHold(dossier(email_side(
            [membership(OURS, collision.IN_SEQUENCE, emails_sent=1)],
            sent_rows=[sent_row(OURS, 900)])))


# 3, 5 ---------------------------------------------------------------------
class WhoSentItDecidesTheTrack(ClassifyTest):
    """The ledger decides, and it is the whole of step 3."""

    def test_a_resonate_os_send_forty_days_ago_is_revival(self):
        """Required case 5. Ours, finished, no reply, past the 30-day minimum."""
        self.assertRevival(dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 40)])),
            decision=collision.HOLD,
            why="a STARI LEAD on the revival track, classified only")

    def test_a_manual_send_six_months_ago_is_cold(self):
        """Required case 6, and the direct control for the one above.

        THE ONLY DIFFERENCE BETWEEN THESE TWO FIXTURES IS THE CAMPAIGN ID. One
        is in `work/campaigns.jsonl` and one is not, and that is the entire
        basis on which a lead gets a revival angle or a brand-new sequence.
        """
        self.assertCold(dossier(cold_baseline(days=180)),
                        why="manual history does not make a lead ours")

    def test_the_same_dates_both_ways_round(self):
        """The cleanest possible control: identical everything but the owner."""
        for days in (31, 40, 100, 400):
            with self.subTest(days=days):
                self.assertRevival(dossier(email_side(
                    [membership(OURS, "sequence_finished", emails_sent=1)],
                    sent_rows=[sent_row(OURS, days)])))
                self.assertCold(dossier(email_side(
                    [membership(MANUAL, "sequence_finished", emails_sent=1)],
                    sent_rows=[sent_row(MANUAL, days)])))

    def test_twenty_manual_sends_still_leave_the_lead_cold(self):
        """"REGARDLESS of how much internal/manual history exists"."""
        members = [membership(MANUAL, "sequence_finished", emails_sent=20)]
        rows = [sent_row(MANUAL, 100 + i) for i in range(20)]
        self.assertCold(dossier(email_side(members, sent_rows=rows)))

    def test_one_os_send_beats_twenty_manual_ones(self):
        """And a single touch of ours moves the whole lead to revival."""
        members = [membership(MANUAL, "sequence_finished", emails_sent=20),
                   membership(OURS, "sequence_finished", emails_sent=1)]
        rows = [sent_row(MANUAL, 100 + i) for i in range(20)]
        rows.append(sent_row(OURS, 95))
        self.assertRevival(dossier(email_side(members, sent_rows=rows)))

    def test_an_os_touch_inside_the_revival_minimum_is_still_revival(self):
        """Step 3 settles the TRACK; step 5's clock only says "not yet"."""
        self.assertRevival(dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 5)])),
            decision=collision.HOLD,
            why="ours and recent is revival-too-soon, never cold")

    def test_revival_only_sends_once_the_operator_approves(self):
        """Step 5 is PROPOSED. The default must refuse, and it must be a flag."""
        dos = dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 40)]))
        self.assertRevival(dos, decision=collision.HOLD,
                           why="not approved: classified only")
        decision, klass, _why = collision.classify(
            dos, options={"revival_approved": True})
        self.assertEqual((collision.ALLOW, collision.CLASS_REVIVAL),
                         (decision, klass))
        # Approval does not lift the minimum.
        too_soon = dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 5)]))
        decision, klass, _why = collision.classify(
            too_soon, options={"revival_approved": True})
        self.assertEqual((collision.HOLD, collision.CLASS_REVIVAL),
                         (decision, klass))


# 4 ------------------------------------------------------------------------
class StepFourIsAConfigValue(ClassifyTest):

    def test_a_manual_touch_five_days_ago_waits(self):
        """Required case 7. COLD, but not yet."""
        self.assertWaiting(dossier(cold_baseline(days=5)),
                           why="cold and inside the default 14-day gap")
        self.assertCold(dossier(cold_baseline(days=200)),
                        why="the control: the only difference is the date")

    def test_the_gap_comes_from_config_and_not_from_code(self):
        """The operator is still deciding N, so N must be one edit.

        Asserted through `settings`, the reader a client yaml feeds, AND
        end-to-end through `classify(config=...)`, so a value in the file
        actually changes the outcome rather than merely being parsed.
        """
        self.assertEqual(14, collision.DEFAULTS["manual_gap_days"])
        self.assertEqual(
            7, collision.settings({"recontact": {"manual_gap_days": 7}})
            ["manual_gap_days"])
        config = {"recontact": {"manual_gap_days": 60}}
        decision, klass, _why = collision.classify(
            dossier(cold_baseline(days=30)), config=config)
        self.assertEqual((collision.HOLD, collision.CLASS_COLD_WAITING),
                         (decision, klass),
                         "a 30-day-old manual touch must WAIT under a 60-day "
                         "gap, and the 60 came from the config")
        decision, klass, _why = collision.classify(
            dossier(cold_baseline(days=30)))
        self.assertEqual((collision.ALLOW, collision.CLASS_COLD),
                         (decision, klass),
                         "and the SAME lead clears the default 14-day gap, so "
                         "the config value is what moved it")

    def test_zero_means_no_gap_and_is_not_an_absent_value(self):
        """"0 means no gap" - so 0 must not fall back to the default 14."""
        config = {"recontact": {"manual_gap_days": 0}}
        self.assertEqual(0, collision.settings(config)["manual_gap_days"])
        decision, klass, _why = collision.classify(
            dossier(cold_baseline(days=1)), config=config)
        self.assertEqual((collision.ALLOW, collision.CLASS_COLD),
                         (decision, klass),
                         "with the gap at 0 a touch yesterday is still COLD")
        self.assertWaiting(dossier(cold_baseline(days=1)),
                           why="and the control: the default 14 makes it wait")

    def test_an_unreadable_gap_value_refuses_rather_than_guessing(self):
        """A typo must not silently become the decision "no gap"."""
        for bad in ("fourteen", None, "", [], {"a": 1}):
            with self.subTest(value=bad):
                with self.assertRaises(collision.CollisionUnknown):
                    collision.settings({"recontact": {"manual_gap_days": bad}})

    def test_the_boundary_is_asserted_rather_than_left_to_a_comparison(self):
        """"WAITS until N days have passed" - so day N passes, N-1 waits."""
        self.assertWaiting(dossier(cold_baseline(days=13)))
        self.assertCold(dossier(cold_baseline(days=14)))

    def test_the_gap_measures_the_newest_manual_touch_not_the_oldest(self):
        members = [membership(MANUAL, "sequence_finished", emails_sent=2)]
        self.assertWaiting(dossier(email_side(
            members, sent_rows=[sent_row(MANUAL, 400), sent_row(MANUAL, 2)])))

    def test_the_gap_does_not_apply_to_a_lead_nobody_ever_touched(self):
        """A genuine first contact has no gap to wait out."""
        self.assertCold(dossier(
            collision.email_history(lead_row=None,
                                    lookup=collision.LOOKUP_ABSENT,
                                    bindings={}, os_campaigns=OS_CAMPAIGNS)))


# 8 ------------------------------------------------------------------------
class TheStatusIsAuthoritativeNotTheCounter(ClassifyTest):
    """Campaign 274 at grayloon.com: status `replied`, `replies: 0`, one row."""

    def test_a_replied_status_blocks_even_when_the_counter_says_zero(self):
        """Required case 8. Every reply counter in the fixture is zero."""
        row = lead_row([membership(MANUAL_2, collision.REPLIED, emails_sent=5,
                                   replies_=0)], emails_sent=5, replies_=0)
        self.assertEqual(0, row["overall_stats"]["replies"],
                         "the fixture must really carry a zero counter, or "
                         "this test proves nothing")
        self.assertEqual(0, row["lead_campaign_data"][0]["replies"])
        self.assertBlocked(dossier(email_side(
            [membership(MANUAL_2, collision.REPLIED, emails_sent=5,
                        replies_=0)], replies_=0,
            sent_rows=[sent_row(MANUAL_2, d) for d in
                       (300, 290, 280, 270, 260)])),
            why="the status answered; the counter was zero")

    def test_the_counter_alone_also_blocks(self):
        """The other direction: a counter without the status still blocks."""
        self.assertBlocked(dossier(email_side(
            [membership(MANUAL_2, "sequence_finished", emails_sent=5,
                        replies_=0)], replies_=1,
            sent_rows=[sent_row(MANUAL_2, d) for d in
                       (300, 290, 280, 270, 260)])),
            why="neither field is trusted to be the only one consulted")

    def test_with_both_at_zero_and_finished_the_lead_is_cold(self):
        """The negative control. Identical sends, identical dates."""
        self.assertCold(dossier(email_side(
            [membership(MANUAL_2, "sequence_finished", emails_sent=5,
                        replies_=0)], replies_=0,
            sent_rows=[sent_row(MANUAL_2, d) for d in
                       (300, 290, 280, 270, 260)])),
            why="five manual emails, no reply in either field, finished")

    def test_the_interested_flag_blocks_with_no_reply_recorded_at_all(self):
        self.assertBlocked(dossier(email_side(
            [membership(MANUAL_2, "sequence_finished", emails_sent=1,
                        interested=True)],
            sent_rows=[sent_row(MANUAL_2, 300)])))


# 9 ------------------------------------------------------------------------
class UnknownNeverBecomesColdOrRevival(ClassifyTest):

    def test_a_failed_lookup_on_either_channel_blocks(self):
        """Required case 9."""
        for answer in (collision.LOOKUP_FAILED, collision.LOOKUP_PARTIAL,
                       collision.LOOKUP_NOT_ASKED):
            with self.subTest(email_lookup=answer):
                self.assertUnknown(dossier(cold_baseline_with(lookup=answer)))
            with self.subTest(sends_lookup=answer):
                self.assertUnknown(
                    dossier(cold_baseline_with(sends_lookup=answer)))
            with self.subTest(linkedin=answer):
                self.assertUnknown(dossier(cold_baseline(),
                                           linkedin_side(lookup=answer)))

    def test_an_unreadable_campaign_ledger_blocks_rather_than_going_cold(self):
        """THE MOST DANGEROUS FAILURE THIS RULE HAS, pinned down.

        `campaign_bindings` returns `{}` both when we own nothing and when the
        file could not be read, and under this rule those have OPPOSITE
        consequences: an empty-but-read ledger correctly makes everybody COLD,
        while an unreadable one making everybody COLD would hand a full new
        sequence to every person we have already written to.
        """
        self.assertUnknown(dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 100)], ledger_readable=False)))
        # The control: the SAME lead with the ledger readable is revival, and
        # an empty-but-readable ledger makes the same lead COLD - which is the
        # pair that shows the flag is doing the work, not the campaign id.
        self.assertRevival(dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 100)], ledger_readable=True)))
        self.assertCold(dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 100)], os_campaigns=frozenset(),
            ledger_readable=True)))

    def test_a_status_with_no_verified_meaning_blocks(self):
        """An unread word is not a finished one. It may be running right now."""
        for word in ("never_contacted", "never-contacted", "sending",
                     "warming", ""):
            with self.subTest(status=word):
                self.assertUnknown(dossier(email_side(
                    [membership(MANUAL, word, emails_sent=1)],
                    sent_rows=[sent_row(MANUAL, 300)])))

    def test_stopped_is_ambiguous_and_therefore_blocks(self):
        """`stopped` does not say WHO stopped it, so it cannot become cold."""
        self.assertUnknown(dossier(email_side(
            [membership(MANUAL, collision.STOPPED, emails_sent=1)],
            sent_rows=[sent_row(MANUAL, 300)])))

    def test_a_send_that_cannot_be_dated_blocks(self):
        """A `sent` row with a null `sent_at` is a real provider shape."""
        self.assertUnknown(dossier(email_side(
            [membership(MANUAL, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(MANUAL, 300, sent_at=None)])))
        self.assertCold(dossier(cold_baseline(days=300)))

    def test_a_lead_with_no_linkedin_identifier_blocks(self):
        """Nothing can be asked about a channel with no identity to ask about."""
        self.assertUnknown(dossier(cold_baseline(),
                                   linkedin_side(rows=(), slug=None)))

    def test_a_linkedin_thread_nothing_can_date_blocks(self):
        for broken in (conversation(300, last_message_at=None),
                       conversation(300, total_messages=0)):
            with self.subTest(row=broken["id"]):
                self.assertUnknown(dossier(cold_baseline(),
                                           linkedin_side(rows=[broken])))

    def test_everything_answered_is_cold_so_the_blocks_above_are_the_cause(self):
        """The positive control for the whole class."""
        self.assertCold(dossier(cold_baseline(), linkedin_side(rows=())))


def cold_baseline_with(**kw):
    return email_side([membership(MANUAL, "sequence_finished", emails_sent=1)],
                      sent_rows=[sent_row(MANUAL, 200)], **kw)


# 10 -----------------------------------------------------------------------
class TheChannelsAreOneHistory(ClassifyTest):

    def test_a_linkedin_action_from_an_os_campaign_is_an_os_contact(self):
        """Required case 10. The email side here has NEVER been ours.

        A HeyReach conversation carries no campaign id, so "was this ours" is
        settled by our own record that we staged the person into a HeyReach
        campaign of ours - `ours_recorded`. With it True, a dated action on our
        own seat is a Resonate OS contact and the lead is a STARI LEAD even
        though every EMAIL send belongs to campaign 352.
        """
        self.assertRevival(
            dossier(cold_baseline(days=400),
                    linkedin_side(rows=[conversation(40)], ours_recorded=True)),
            decision=collision.HOLD,
            why="a LinkedIn touch of ours makes the whole lead revival")

    def test_the_same_conversation_not_recorded_as_ours_leaves_it_cold(self):
        """The control, and the only difference is the ledger's answer."""
        self.assertCold(
            dossier(cold_baseline(days=400),
                    linkedin_side(rows=[conversation(40)],
                                  ours_recorded=False)),
            why="not positively recorded as ours, so it is manual history")

    def test_an_unrecorded_linkedin_touch_still_counts_for_the_gap(self):
        """Not ours for step 3, but still a prospect-facing touch for step 4."""
        self.assertWaiting(
            dossier(cold_baseline(days=400),
                    linkedin_side(rows=[conversation(3)], ours_recorded=False)),
            why="somebody messaged them three days ago on LinkedIn")

    def test_an_email_inside_the_gap_blocks_a_linkedin_candidate_too(self):
        """The other direction: the candidate channel changes nothing."""
        self.assertWaiting(
            dossier(cold_baseline(days=3), linkedin_side(rows=()),
                    channel=eligibility.LINKEDIN))

    def test_a_linkedin_reply_is_step_one_whichever_channel_is_sending(self):
        """`lastMessageSender: correspondent` is them, and that goes to a human."""
        self.assertBlocked(dossier(
            cold_baseline(), linkedin_side(rows=[conversation(300,
                                                             from_them=True)])))
        self.assertCold(dossier(
            cold_baseline(), linkedin_side(rows=[conversation(300,
                                                             from_them=False)])),
            why="the control: only `lastMessageSender` differs")

    def test_another_persons_profile_on_our_seat_changes_nothing(self):
        """The slug match is the second half of the tenancy guarantee."""
        self.assertCold(dossier(
            cold_baseline(),
            linkedin_side(rows=[conversation(3, slug="somebody-else",
                                             from_them=True)])),
            why="a three-day-old reply from a different person")

    def test_the_newest_os_touch_across_both_channels_sets_the_revival_clock(self):
        """An old email of ours and a recent message of ours: the message wins."""
        dos = dossier(email_side(
            [membership(OURS, "sequence_finished", emails_sent=1)],
            sent_rows=[sent_row(OURS, 900)]),
            linkedin_side(rows=[conversation(5)], ours_recorded=True))
        decision, klass, why = collision.classify(dos)
        self.assertEqual((collision.HOLD, collision.CLASS_REVIVAL),
                         (decision, klass))
        self.assertIn("5 day", why,
                      "the revival clock must run from the NEWEST touch of "
                      "ours, which is the LinkedIn one")


# the rule's own shape ------------------------------------------------------
class TheOutcomesAreMutuallyExclusive(ClassifyTest):

    def test_exactly_one_outcome_comes_back_and_only_cold_may_send(self):
        cases = {
            collision.CLASS_BLOCKED: dossier(cold_baseline(),
                                             suppression=("agency_dnc",)),
            collision.CLASS_ON_HOLD: dossier(email_side(
                [membership(MANUAL, collision.IN_SEQUENCE, emails_sent=1)],
                sent_rows=[sent_row(MANUAL, 400)])),
            collision.CLASS_UNKNOWN: dossier(
                cold_baseline_with(lookup=collision.LOOKUP_FAILED)),
            collision.CLASS_REVIVAL: dossier(email_side(
                [membership(OURS, "sequence_finished", emails_sent=1)],
                sent_rows=[sent_row(OURS, 40)])),
            collision.CLASS_COLD: dossier(cold_baseline()),
            collision.CLASS_COLD_WAITING: dossier(cold_baseline(days=3)),
        }
        self.assertEqual(set(collision.CLASSES), set(cases),
                         "every outcome in the vocabulary needs a case here, "
                         "or one of them is untested")
        seen = []
        for wanted, dos in cases.items():
            decision, klass, _why = collision.classify(dos)
            self.assertEqual(wanted, klass)
            seen.append(klass)
            allowed = decision == collision.ALLOW
            self.assertEqual(klass in collision.SENDABLE_CLASSES, allowed,
                             f"{klass} must allow a send only if it is in "
                             f"SENDABLE_CLASSES")
        self.assertEqual(len(seen), len(set(seen)), "outcomes must be distinct")
        self.assertEqual({collision.CLASS_COLD}, collision.SENDABLE_CLASSES)

    def test_a_lead_tripping_two_steps_belongs_to_the_earlier_one(self):
        """Order is the rule. A DNC on somebody mid-sequence is BLOCKED."""
        both = email_side([membership(MANUAL, collision.IN_SEQUENCE,
                                      emails_sent=1)],
                          sent_rows=[sent_row(MANUAL, 1)])
        self.assertBlocked(dossier(both, suppression=("agency_dnc",)))
        self.assertOnHold(dossier(both))


# the fifteen-row trap -----------------------------------------------------
class TheFifteenRowTrap(QueueTest):
    """`/leads/{id}/scheduled-emails` serves fifteen rows and ignores per_page."""

    def rows(self, count, newest_first=True, campaign=MANUAL):
        days = [10 + 5 * i for i in range(count)]
        if not newest_first:
            days = list(reversed(days))
        return [sent_row(campaign, d) for d in days]

    def test_a_truncated_read_answers_nothing_however_well_sorted(self):
        """The rows ARE newest-first here, and that is still not enough.

        Fifteen rows in perfect newest-first order against a provider that
        counts twenty-three sends: the sixteenth row could be yesterday's, so
        there is no date to be had. `proven` must be False and `when` None - a
        caller must not be able to read a date out of this.
        """
        when, detail = collision.last_send_at(self.rows(15), claimed=23,
                                              complete=False)
        self.assertIsNone(when)
        self.assertFalse(detail["proven"])
        self.assertEqual("consistent with newest-first", detail["ordering"],
                         "the fixture must really be sorted newest-first, or "
                         "this test is not about the ordering at all")

    def test_a_complete_read_that_does_not_reconcile_answers_nothing(self):
        when, detail = collision.last_send_at(self.rows(15), claimed=23,
                                              complete=True)
        self.assertIsNone(when)
        self.assertFalse(detail["proven"])
        self.assertEqual(15, detail["dated_sends"])

    def test_a_complete_reconciling_read_answers_the_true_maximum(self):
        """And the SAME date whatever order the rows arrived in.

        Order-independence is the property that makes the provider's paging
        order irrelevant rather than trusted, so it is asserted directly.
        """
        wanted = None
        for label, rows in (("newest-first", self.rows(15, True)),
                            ("oldest-first", self.rows(15, False)),
                            ("shuffled", [self.rows(15)[i] for i in
                                          (7, 0, 14, 3, 11, 1, 9, 5, 13, 2,
                                           10, 6, 12, 4, 8)])):
            with self.subTest(order=label):
                when, detail = collision.last_send_at(rows, claimed=15,
                                                      complete=True)
                self.assertTrue(detail["proven"])
                self.assertIsNotNone(when)
                if wanted is None:
                    wanted = when
                self.assertEqual(wanted, when)

    def test_the_truncation_blocks_a_lead_that_would_otherwise_be_cold(self):
        """End to end: the trap reaches the send path as UNKNOWN, not COLD.

        Every one of the fifteen dated rows is old, so a gate that took the
        maximum it could see would call this person cold. The provider counts
        twenty-three sends; eight are undated and one of those could be
        yesterday.
        """
        side = collision.email_history(
            lead_row=lead_row([membership(MANUAL, "sequence_finished",
                                          emails_sent=23)], emails_sent=23),
            lookup=collision.LOOKUP_OK,
            sent_rows=[sent_row(MANUAL, 40 + 5 * i) for i in range(15)],
            sends_lookup=collision.LOOKUP_OK, sends_complete=True,
            bindings={}, os_campaigns=OS_CAMPAIGNS)
        dos = collision.recontact_dossier(email=side,
                                          linkedin_=linkedin_side(rows=()))
        decision, klass, _why = collision.classify(dos)
        self.assertEqual((collision.STOP, collision.CLASS_UNKNOWN),
                         (decision, klass))
        self.assertEqual(eligibility.BLOCKED_RECONTACT_UNKNOWN,
                         eligibility.recontact(dos)["reason"])
        # The control: the same lead whose claim MATCHES what was dated.
        ok = collision.email_history(
            lead_row=lead_row([membership(MANUAL, "sequence_finished",
                                          emails_sent=15)], emails_sent=15),
            lookup=collision.LOOKUP_OK,
            sent_rows=[sent_row(MANUAL, 40 + 5 * i) for i in range(15)],
            sends_lookup=collision.LOOKUP_OK, sends_complete=True,
            bindings={}, os_campaigns=OS_CAMPAIGNS)
        decision, klass, _why = collision.classify(
            collision.recontact_dossier(email=ok,
                                        linkedin_=linkedin_side(rows=())))
        self.assertEqual((collision.ALLOW, collision.CLASS_COLD),
                         (decision, klass))

    def test_the_os_subset_reconciles_separately(self):
        """Step 3 needs OUR send count dated, not just the total.

        Twenty-three total sends, all dated, but the lead's OS membership claims
        two sends and only one of them is in the rows. The TOTAL reconciles and
        the OURS subset does not, so this is UNKNOWN - and without the separate
        reconciliation it would read as a cold lead with no OS history at all.
        """
        rows = [sent_row(MANUAL, 40 + i) for i in range(22)]
        rows.append(sent_row(OURS, 60))
        side = collision.email_history(
            lead_row=lead_row([membership(MANUAL, "sequence_finished",
                                          emails_sent=22),
                               membership(OURS, "sequence_finished",
                                          emails_sent=2)], emails_sent=24),
            lookup=collision.LOOKUP_OK, sent_rows=rows,
            sends_lookup=collision.LOOKUP_OK, sends_complete=True,
            bindings={}, os_campaigns=OS_CAMPAIGNS)
        self.assertEqual(2, side["ours"]["claimed"])
        self.assertFalse(side["ours"]["last_send"]["proven"])
        decision, klass, _why = collision.classify(
            collision.recontact_dossier(email=side,
                                        linkedin_=linkedin_side(rows=())))
        self.assertEqual((collision.STOP, collision.CLASS_UNKNOWN),
                         (decision, klass))

    def test_only_a_sent_row_with_a_date_counts_as_a_send(self):
        self.assertEqual([], collision.dated_sends([
            sent_row(MANUAL, 5, status="scheduled"),
            sent_row(MANUAL, 6, status="stopped"),
            sent_row(MANUAL, 7, status="paused"),
            sent_row(MANUAL, 8, sent_at=None)]))
        self.assertEqual(1, len(collision.dated_sends([sent_row(MANUAL, 9)])))

    def test_dated_sends_can_be_restricted_to_one_owners_campaigns(self):
        rows = [sent_row(MANUAL, 10), sent_row(OURS, 20), sent_row(MANUAL, 30)]
        self.assertEqual(3, len(collision.dated_sends(rows)))
        self.assertEqual(1, len(collision.dated_sends(
            rows, only_campaigns=OS_CAMPAIGNS)))
        self.assertEqual(0, len(collision.dated_sends(
            rows, only_campaigns=frozenset())))

    def test_a_naive_timestamp_is_unreadable_rather_than_assumed_utc(self):
        """Guessing a zone moves a boundary by up to a day, silently."""
        naive = sent_row(MANUAL, 31)
        naive["sent_at"] = "2026-08-31T12:00:00"
        self.assertEqual([], collision.dated_sends([naive]))


# the ledger ---------------------------------------------------------------
class TheLedgerIsTheOwnershipAuthority(QueueTest):

    def test_an_empty_ledger_reads_as_ours_being_none_and_says_it_was_read(self):
        """`campaign_bindings` conflates two answers; this must not.

        Run against this test's own throwaway store, which has no campaigns -
        so the honest answer is "we own none, and the file was read", and the
        second half is what keeps that from becoming step 3c.
        """
        ids, readable = collision.os_campaign_ids()
        self.assertTrue(readable)
        self.assertEqual(frozenset(), ids)

    def test_the_four_internal_campaigns_are_not_ours(self):
        """The measurement, as a test: 274/327/328/352 are absent by id."""
        for campaign in (274, 327, 328, 352):
            self.assertNotIn(campaign, OS_CAMPAIGNS,
                             f"{campaign} is an internal campaign and must "
                             f"never appear in the bound set")
        for campaign in (451, 491, 503, 506):
            self.assertIn(campaign, OS_CAMPAIGNS)


# the wiring ---------------------------------------------------------------
class TheClassificationIsWiredIntoTheDecision(GateTest):
    """`eligibility.decide` must consume the dossier, and say when it did not.

    Built on `test_eligibility.GateTest` rather than on a record assembled here:
    `ready()` is the record the whole existing suite asserts is genuinely
    eligible through every other gate, so the dossier is the only variable in
    each comparison below. `GateTest` carries no test methods of its own, so
    importing it adds no test names to this module.
    """

    def test_the_baseline_step_is_eligible_so_every_verdict_below_is_the_dossier(self):
        rec, recs = self.ready()
        self.assertTrue(self.decide(rec, recs).eligible)

    def test_each_outcome_reaches_the_send_path_with_the_right_verdict(self):
        """Blocked blocks, held holds, and cold leaves the step eligible."""
        cases = (
            (eligibility.BLOCKED, eligibility.BLOCKED_RECONTACT_REFUSED,
             dossier(cold_baseline(), suppression=("agency_dnc",))),
            (eligibility.HELD, eligibility.HELD_IN_A_LIVE_CAMPAIGN,
             dossier(email_side([membership(MANUAL, collision.IN_SEQUENCE,
                                            emails_sent=1)],
                                sent_rows=[sent_row(MANUAL, 400)]))),
            (eligibility.HELD, eligibility.HELD_MANUAL_CONTACT_GAP,
             dossier(cold_baseline(days=3))),
            (eligibility.HELD, eligibility.HELD_REVIVAL_NOT_APPROVED,
             dossier(email_side([membership(OURS, "sequence_finished",
                                            emails_sent=1)],
                                sent_rows=[sent_row(OURS, 40)]))),
            (eligibility.BLOCKED, eligibility.BLOCKED_RECONTACT_UNKNOWN,
             dossier(cold_baseline_with(lookup=collision.LOOKUP_FAILED))),
        )
        for verdict, reason, dos in cases:
            with self.subTest(reason=reason):
                rec, recs = self.ready()
                decided = self.decide(rec, recs, recontact_dossier=dos)
                self.assertEqual(verdict, decided["verdict"],
                                 decided["reasons"])
                self.assertEqual(reason, decided["reason"])
                self.assertTrue(decided["recontact"]["asked"])
                self.assertTrue(decided["recontact"]["why"])

    def test_a_cold_dossier_leaves_the_step_eligible(self):
        """The positive control: the gate is not a blanket refusal."""
        rec, recs = self.ready()
        decided = self.decide(rec, recs, recontact_dossier=dossier(cold_baseline()))
        self.assertTrue(decided.eligible, decided["reasons"])
        self.assertEqual(collision.CLASS_COLD, decided["recontact"]["klass"])

    def test_a_step_decided_without_a_dossier_says_so_on_its_verdict(self):
        """THE GATE MUST NOT BE INVISIBLY INERT.

        `decide(recontact_dossier=None)` cannot enforce a rule whose evidence it
        was not given, and this repository has shipped a matcher that was
        structurally unable to match anything past eighteen green tests. So
        every verdict carries `recontact.asked`, and a reviewer reading one can
        see whether the classification ran at all. `executionguard.authorize`
        gate 4 is where the dossier has to be supplied on a live send - it
        already makes three provider collision reads there - and THAT FILE IS
        NOT CHANGED BY THIS WORK. The gap is asserted here and reported, rather
        than papered over with a default that passes.
        """
        rec, recs = self.ready()
        decided = self.decide(rec, recs)
        self.assertTrue(decided.eligible)
        self.assertIn("recontact", decided)
        self.assertIs(False, decided["recontact"]["asked"])
        self.assertIsNone(decided["recontact"]["reason"])

    def test_every_outcome_has_a_code_and_a_sentence(self):
        """An outcome added in `collision` with no code here would pass silently."""
        mapped = eligibility._recontact_codes()
        for klass in collision.CLASSES:
            if klass in collision.SENDABLE_CLASSES:
                self.assertNotIn(klass, mapped)
                continue
            self.assertIn(klass, mapped, f"{klass} reaches no eligibility code")
            code = mapped[klass]
            self.assertIn(code, eligibility.REASONS)
            self.assertNotEqual(code, eligibility.explain(code),
                                f"{code} has no sentence for a human")
        self.assertEqual(len(set(mapped.values())), len(mapped),
                         "two outcomes sharing one code lose which is which")
