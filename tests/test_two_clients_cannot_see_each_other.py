r"""Phase D item 6: two clients, two channels, and neither can see the other.

OPERATOR, 2026-09-23: "Synthetic second client bound to a test channel:
every client tool, the accounts-first answers and the weekly report run for
both workspaces; zero cross-visibility asserted from both sides, not one.
This is the proof for the second real client."

## WHY A SECOND WORKSPACE CHANGES WHAT THESE ASSERTIONS ARE WORTH

The isolation properties were already written and already tested - and every
one of them was tested ONE-SIDED. `account_status` asserts that another
client's domain reads like a stranger's; `weekly_report`, `lead_counts` and
`lead_in_campaign` have the same shape. With one real workspace in the
fixture, "the other client" is a slug with nothing behind it, so an answer
that leaked would have had nothing to leak. A tool could read the whole
estate and still pass, because the estate was one client.

Here both sides are furnished. Each workspace has records, campaigns,
senders, replies, meetings and a bound channel, and each side is asked for
the other's. A leak now has something to carry.

## THE FIXTURE IS A SHARED ESTATE, DELIBERATELY

The provider fake holds BOTH clients' campaigns, BOTH clients' mailboxes and
a single reply feed with both clients' replies in it, because that is what
the real provider is: one EmailBison estate with every client in it. A fake
partitioned per client would prove nothing - the partition would be doing
the work the scoping is supposed to do, and the test would pass on a tool
that reads everything.

So the ONLY thing standing between alpha's channel and bravo's data in this
file is `src/slackagenttools.py`'s own pinning. Nothing else is mocked:
the workspaces, the queue, the campaigns and the senders are real files in a
temp directory, the scope is resolved from a channel id by the real
`slackscope.resolve`, and the tools are called through the real
`tools.run`.

## WHAT IS ASSERTED, AND BOTH WAYS ROUND EVERY TIME

1. The binding resolves in both directions and neither channel can reach the
   other's workspace.
2. EVERY client tool runs for BOTH workspaces - enumerated from the
   registry, not listed here, so a tool added tomorrow is covered the day it
   is added rather than the day somebody remembers this file.
3. No client tool's readback carries a single one of the other client's
   markers - company, domain, address, person, campaign id, campaign name,
   sending domain or slug - in either direction.
4. The argument is ignored rather than validated: asking alpha's channel
   about bravo by slug, domain, address or campaign id answers about alpha
   or refuses, and never confirms bravo exists.
5. Another client's account reads WORD FOR WORD like an account nobody has,
   from both sides. The difference between those two notes is the leak.
6. The accounts-first answers and the weekly report are computed per
   workspace and their figures are disjoint.
7. The outbound backstop is armed for both scopes.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import events                                          # noqa: E402
from src import slackagenttools as tools                        # noqa: E402
from src import slackscope                                      # noqa: E402
from src import store                                           # noqa: E402

ALPHA, BRAVO = "alpha", "bravo"
ALPHA_CHANNEL, BRAVO_CHANNEL = "C0ALPHATEST", "C0BRAVOTEST"
INTERNAL_CHANNEL = "C0INTERNAL1"


# --------------------------------------------------------------- the two
#
# Every string here belongs to exactly one client. They are the markers the
# cross-visibility assertions look for, so they are deliberately unlike each
# other and unlike anything this repository says on its own.

SIDES = {
    ALPHA: {
        "slug": ALPHA,
        "name": "Alphega Industries",
        "company": "Alphega Industries",
        "domain": "alphega-industries.test",
        "contact": "prue.almandine@alphega-industries.test",
        "person": "Prue Almandine",
        "sending_domain": "alphega-mail.test",
        "mailbox": "outreach@alphega-mail.test",
        "sender_id": "almondine",
        "sender_name": "Ines Almondine",
        "campaign_id": "alphega-uk",
        "provider_campaign_id": "8101",
        "campaign_name": "RESONATE - ALPHEGA - EMAIL - UK-HOURS - CONTROL",
        "channel": ALPHA_CHANNEL,
        "lead_id": 71001,
        "provider_account_id": "bison-alphega-1",
        "subject": "Alphega utilisation, briefly",
        "body": "We help Alphega-sized firms read utilisation weekly.",
    },
    BRAVO: {
        "slug": BRAVO,
        "name": "Bravura Holdings",
        "company": "Bravura Holdings",
        "domain": "bravura-holdings.test",
        "contact": "yusuf.oyelaran@bravura-holdings.test",
        "person": "Yusuf Oyelaran",
        "sending_domain": "bravura-mail.test",
        "mailbox": "hello@bravura-mail.test",
        "sender_id": "oyelaran",
        "sender_name": "Dara Oyelaran",
        "campaign_id": "bravura-emea",
        "provider_campaign_id": "8201",
        "campaign_name": "RESONATE - BRAVURA - EMAIL - EMEA-HOURS - COHORT B",
        "channel": BRAVO_CHANNEL,
        "lead_id": 72001,
        "provider_account_id": "bison-bravura-1",
        "subject": "Bravura capacity planning",
        "body": "Bravura-sized holdings usually plan capacity a quarter out.",
    },
}

OTHER = {ALPHA: BRAVO, BRAVO: ALPHA}


def markers_of(slug):
    """Every string that belongs to this client and to nobody else.

    The slug itself is included. It is the one the outbound backstop also
    checks for, and a readback naming it is a leak whether or not the
    company name came with it.
    """
    side = SIDES[slug]
    return (side["slug"], side["name"], side["domain"], side["contact"],
            side["person"], side["sending_domain"], side["mailbox"],
            side["sender_name"], side["campaign_id"],
            side["provider_campaign_id"], side["campaign_name"],
            side["provider_account_id"], side["subject"], side["body"],
            str(side["lead_id"]))


# ------------------------------------------------------------- the estate

def _contact(side):
    first, _, rest = side["person"].partition(" ")
    return {"key": side["sender_id"] + "-c1", "name": side["person"],
            "title": "Head of Operations", "persona": "champion",
            "email": side["contact"], "selected": True, "verified": True,
            "first_name": first, "last_name": rest}


def _cadence(side):
    """One approved email step, stamped with the REAL fingerprint.

    `approval.is_approved` compares the stored fingerprint against the
    step's current words, so a hand-written hash would make the step read as
    edited-since-approval and `campaign_copy` would answer empty - passing
    the isolation assertions with nothing in the answer to isolate.
    """
    from src import approval
    step = {"channel": "email", "subject": side["subject"],
            "body": side["body"], "day": 1}
    step["approval"] = {"fingerprint": approval.fingerprint(step),
                        "by": "U0OPERATOR", "at": "2026-09-23T08:00:00Z"}
    return {side["sender_id"] + "-c1": {"day1": step}}


def _record(side, rid=None, state="verified", events_=None, domain=None):
    key = side["sender_id"] + "-c1"
    contact = _contact(side)
    if domain:
        contact = dict(contact, email="someone@" + domain, key=key)
    return {
        "id": rid or (side["slug"] + "-1"),
        "lane": "domains", "client": side["slug"],
        "company": side["company"] if not domain else domain.split(".")[0],
        "domain": domain or side["domain"],
        "state": state, "drop_reason": None,
        "log": [], "events": events_ or [],
        "contacts": [contact],
        "cadence": _cadence(side),
    }


def _touch(side, kind=events.EMAIL_DELIVERED, at="2026-09-22T09:00:00Z"):
    return {"type": kind, "contact": side["sender_id"] + "-c1", "step": 1,
            "day": 1, "at": at, "channel": "email", "sender_id": "s1"}


def _reply(side, classification="out_of_office",
           at="2026-09-22T10:00:00Z"):
    return {"type": events.REPLY_RECEIVED,
            "contact": side["sender_id"] + "-c1", "at": at,
            "classification": classification, "channel": "email"}


def _workspace_row(side):
    return {
        "kind": "workspace", "slug": side["slug"], "name": side["name"],
        "client": side["slug"], "created_at": "2026-09-23T08:00:00+00:00",
        "created_by": "test",
        "settings": {"policy": {
            "slack.agent_channel": side["channel"],
            "sending.live": "on",
        }},
    }


def _campaign_row(side):
    return {
        "kind": "campaign", "campaign_id": side["campaign_id"],
        "client": side["slug"], "name": side["campaign_name"],
        "status": "live", "created_at": "2026-09-23T08:00:00+00:00",
        "created_by": "test",
        "bison_campaign_id": side["provider_campaign_id"],
        "heyreach_campaign_id": None, "approval": None,
        "fingerprint": side["slug"] + "-fp", "pause": None,
        "record_ids": [side["slug"] + "-1", side["slug"] + "-2"],
        # THE STORE'S REAL SHAPE, both levels. `senders` is a dict keyed by
        # channel and `daily_volume` is a dict keyed the same way - checked
        # against all 26 live campaign rows, which are unanimous. The first
        # draft of this fixture made both flat, and `sender_summary` failed
        # with an AttributeError that was the FIXTURE being wrong.
        "senders": {
            "email": [{"provider_account_id": side["provider_account_id"],
                       "email_address": side["mailbox"],
                       "daily_limit": 30}],
            "linkedin": [],
        },
        "daily_volume": {"email": 20, "linkedin": 0},
        "events": [], "log": [], "launch": None, "demo": False,
    }


def _sender_rows(side):
    """The three rows it takes for a sender to be REAL to these tools.

    `sending_domains` and `sender_roster` read attested ownership, not the
    `sender` row - so a fixture with only the person in it answers "no
    authorized email sender is recorded for this workspace", which is the
    confidently-empty shape: every isolation assertion passes because the
    tool said nothing. The first draft of this file did exactly that, and
    the attack runs below are what showed it.

    So: the person, the mailbox, and the attestation that ties one to the
    other - all three in the live store's shape.
    """
    return [
        {"kind": "sender", "workspace": side["slug"],
         "sender_id": side["sender_id"],
         "display_name": side["sender_name"],
         "title": "Account Director", "team": "growth", "active": True,
         "colleague_language": None,
         "created_at": "2026-09-23T08:00:00+00:00"},
        {"kind": "email_account", "workspace": side["slug"],
         "account_id": side["provider_account_id"],
         "sender_id": side["sender_id"], "provider": "emailbison",
         "provider_account_id": side["provider_account_id"],
         "email_address": side["mailbox"],
         "domain": side["sending_domain"], "active": True,
         "daily_limit": 30, "health": "unknown",
         "created_at": "2026-09-23T08:00:00+00:00"},
        {"kind": "ownership_attestation", "workspace": side["slug"],
         "channel": "email", "account_id": side["provider_account_id"],
         "sender_id": side["sender_id"],
         "by": "test attestation", "at": "2026-09-23T08:00:00+00:00"},
    ]


# ------------------------------------------------- one shared provider

class SharedProviderEstate:
    """One EmailBison estate holding BOTH clients, as the real one does.

    Every method answers about whatever it is asked for. It is not scoped,
    it does not know what a workspace is, and it will hand bravo's rows to
    an alpha question without hesitation - which is the point. If an answer
    for alpha carries a bravo string, our code put it there.
    """

    def __init__(self):
        self.asked = []

    # -- campaigns

    def campaign(self, campaign_id):
        for slug, side in SIDES.items():
            if str(campaign_id) == side["provider_campaign_id"]:
                self.asked.append(("campaign", str(campaign_id)))
                return {"id": side["provider_campaign_id"],
                        "name": side["campaign_name"],
                        "status": "active", "emails_sent": 40,
                        "replied": 2, "bounced": 1}
        return {}

    def campaign_lead_count(self, campaign_id):
        return 25 if self._known(campaign_id) else 0

    def scheduled_emails(self, campaign_id, cap=None):
        side = self._side(campaign_id)
        if side is None:
            return []
        return [{"id": side["slug"] + "-q1", "email": side["contact"],
                 "lead": {"email": side["contact"],
                          "first_name": side["person"].split(" ")[0]},
                 "campaign_id": side["provider_campaign_id"],
                 "scheduled_at": "2026-09-24T09:00:00Z"}]

    def sending_schedule(self, campaign_id, day):
        side = self._side(campaign_id)
        if side is None:
            return {}
        return {"campaign_id": side["provider_campaign_id"], "day": day,
                "scheduled": 12, "name": side["campaign_name"]}

    # -- people

    def find_lead_by_email(self, address):
        """Answers for EITHER client's address, because the real one does.

        The lead id is an int: `lead_in_campaign` does `int(lead_id)` to key
        the membership map, so a string id made the tool raise - again the
        fixture being wrong about the provider rather than a finding.
        """
        for side in SIDES.values():
            if str(address).lower() == side["contact"].lower():
                return {"id": side["lead_id"], "email": side["contact"],
                        "first_name": side["person"].split(" ")[0]}
        return None

    def membership(self, campaign_id, lead_ids=None):
        side = self._side(campaign_id)
        if side is None:
            return {}
        return {side["lead_id"]: {"status": "active"}}

    # -- the estate

    def sender_emails(self):
        estate = []
        for side in SIDES.values():
            estate.append({"email": side["mailbox"],
                           "name": side["sender_name"],
                           "sent": 120, "bounced": 2,
                           "daily_limit": 30, "active": True})
        return estate, {"read_at": "2026-09-23T12:00:00Z"}

    def fetch_replies(self, per_page=25, **kw):
        rows = []
        for side in SIDES.values():
            rows.append({
                "uuid": side["slug"] + "-reply-1",
                "id": 900 if side["slug"] == ALPHA else 901,
                "campaign_id": side["provider_campaign_id"],
                "from_email": side["contact"],
                "text": "I am out of the office until Monday.",
                "automated_reply": True,
                "created_at": "2026-09-22T10:00:00Z",
            })
        return rows, None

    # -- helpers

    @staticmethod
    def _side(campaign_id):
        for side in SIDES.values():
            if str(campaign_id) == side["provider_campaign_id"]:
                return side
        return None

    def _known(self, campaign_id):
        return self._side(campaign_id) is not None


# ------------------------------------------------------------- the case

class TwoClientEstate(unittest.TestCase):
    """Two synthetic clients on disk, each bound to its own channel."""

    maxDiff = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-two-clients-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "OUT", "CLIENTS_DIR",
                      slackscope.INTERNAL_CHANNELS_VAR,
                      slackscope.OPS_CHANNEL_VAR,
                      slackscope.STATUS_CHANNEL_VAR,
                      slackscope.INTERNAL_USERS_VAR,
                      slackscope.OPERATOR_USER_VAR) + store.STATE_OVERRIDES}
        self.addCleanup(self._restore_env)

        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = INTERNAL_CHANNEL
        for var in (slackscope.OPS_CHANNEL_VAR,
                    slackscope.STATUS_CHANNEL_VAR,
                    slackscope.INTERNAL_USERS_VAR,
                    slackscope.OPERATOR_USER_VAR):
            os.environ.pop(var, None)

        self._write_estate()
        self._pin_knowledge()
        self.provider = self._install_provider()

        # THE WITNESS CACHE IS MODULE-LEVEL and keyed by slug. A verdict
        # left behind by another test decides this one's answer.
        tools._LEDGER_WITNESS.clear()
        self.addCleanup(tools._LEDGER_WITNESS.clear)

    def _restore_env(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # -- the files

    def _write_estate(self):
        work = os.path.join(self.tmp, "work")
        self._write(os.path.join(work, "workspaces.jsonl"),
                    [_workspace_row(SIDES[ALPHA]),
                     _workspace_row(SIDES[BRAVO])])
        self._write(os.path.join(work, "campaigns.jsonl"),
                    [_campaign_row(SIDES[ALPHA]),
                     _campaign_row(SIDES[BRAVO])])
        self._write(os.path.join(work, "senders.jsonl"),
                    _sender_rows(SIDES[ALPHA]) + _sender_rows(SIDES[BRAVO]))

        rows = []
        for slug, side in SIDES.items():
            # One account with a delivered touch and a reply, and one that
            # has had nothing. Enough for the accounts-first answers to
            # have something to count on both sides.
            rows.append(_record(side, rid=slug + "-1",
                                events_=[_touch(side), _reply(side)]))
            rows.append(_record(side, rid=slug + "-2",
                                domain="quiet-" + side["domain"]))
        self._write(os.path.join(work, "queue.jsonl"), rows)

    @staticmethod
    def _write(path, rows):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def _pin_knowledge(self):
        """A pack with each workspace's OWN provider campaign ids.

        Pinned rather than built because building it is not what this file
        is about - but the ids are real per side, because
        `_campaign_is_visible` reads them and that gate IS what this file is
        about.
        """
        pack = {"workspaces": {
            slug: {"provider_campaign_ids": [side["provider_campaign_id"]],
                   "name": side["name"],
                   "sending_window": {"timezone": "Europe/Zagreb"},
                   # Distinct per side, so `cadence_detail` is one more
                   # surface the cross-visibility assertions cover rather
                   # than a tool that refuses on both sides and proves
                   # nothing by agreeing.
                   "cadence": {"name": side["campaign_name"],
                               "steps": [{"key": "day1", "day": 1,
                                          "channel": "email",
                                          "subject": side["subject"]}]}}
            for slug, side in SIDES.items()}}
        previous = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: pack
        self.addCleanup(setattr, tools.knowledge, "pack", previous)

    def _install_provider(self):
        from src.providers import bison
        estate = SharedProviderEstate()
        for name in ("campaign", "campaign_lead_count", "scheduled_emails",
                     "sending_schedule", "find_lead_by_email", "membership",
                     "sender_emails", "fetch_replies"):
            patcher = mock.patch.object(bison, name,
                                        getattr(estate, name),
                                        create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        return estate

    # -- asking

    def scope_for(self, slug):
        """The scope a message in that client's channel really resolves to."""
        return slackscope.resolve(channel=SIDES[slug]["channel"],
                                  user="U0CLIENT01")

    def internal_scope(self):
        return slackscope.resolve(channel=INTERNAL_CHANNEL, user="U0STAFF01")

    def client_tools(self, slug):
        return sorted(tools.for_scope(self.scope_for(slug)))

    def ask(self, slug, name, argument=None):
        return tools.run(self.scope_for(slug), name, argument)

    def text_of(self, name, result, argument=None):
        return tools.render([(name, argument, result)])

    def assert_no_trace_of(self, other, text, where):
        lowered = text.lower()
        for marker in markers_of(other):
            self.assertNotIn(
                marker.lower(), lowered,
                "%s carried %r, which belongs to %s" % (where, marker, other))


# ============================== 1. THE BINDING, IN BOTH DIRECTIONS

class TheBindingResolvesBothWays(TwoClientEstate):

    def test_each_channel_resolves_to_its_own_workspace(self):
        for slug in SIDES:
            scope = self.scope_for(slug)
            self.assertTrue(scope.is_client, slug)
            self.assertEqual(scope.workspace, slug)

    def test_neither_channel_resolves_to_the_other(self):
        for slug, other in OTHER.items():
            self.assertNotEqual(self.scope_for(slug).workspace, other)

    def test_each_scope_may_see_only_itself(self):
        for slug, other in OTHER.items():
            scope = self.scope_for(slug)
            self.assertEqual(tuple(scope.workspaces_visible()), (slug,))
            self.assertFalse(scope.may_see_workspace(other))
            self.assertTrue(scope.may_see_workspace(slug))

    def test_both_slugs_were_known_when_each_scope_resolved(self):
        """The backstop checks the slug set captured at resolution.

        If only one workspace existed at that moment the other's name would
        pass the slug check vacuously, and the assertions below would be
        worth nothing.
        """
        for slug in SIDES:
            known = self.scope_for(slug).known_slugs()
            self.assertIn(ALPHA, known)
            self.assertIn(BRAVO, known)

    def test_an_internal_channel_is_not_bound_to_either(self):
        scope = self.internal_scope()
        self.assertTrue(scope.is_internal)
        self.assertIsNone(scope.workspace)


# ============================== 2. EVERY CLIENT TOOL, BOTH WORKSPACES

class EveryClientToolRunsForBothWorkspaces(TwoClientEstate):
    """Enumerated from the registry, so tomorrow's tool is covered today."""

    #: An argument that means something for the tools that take one, named
    #: as a key into `SIDES` so the SAME tool can be asked about either
    #: client. A tool given a nonsense argument answers about nothing and
    #: proves nothing.
    #:
    #: These are also the tools the cross-visibility tests can point at the
    #: other client, which is why the map lives here and is read there.
    ARGUMENTS = {
        "campaign_detail": "provider_campaign_id",
        "lead_lookup": "contact",
        "lead_counts": "provider_campaign_id",
        "lead_in_campaign": "contact",
        "account_lookup": "domain",
        "account_status": "domain",
        "domain_detail": "sending_domain",
    }

    #: Arguments that name a STEP or a window rather than a client. They are
    #: the same word in both channels, so they say nothing about either.
    LITERAL_ARGUMENTS = {"campaign_copy": "day1", "meetings_booked": "week"}

    @classmethod
    def argument_for(cls, slug, name):
        key = cls.ARGUMENTS.get(name)
        if key:
            return SIDES[slug][key]
        return cls.LITERAL_ARGUMENTS.get(name)

    def test_both_channels_are_offered_the_same_tools(self):
        self.assertEqual(self.client_tools(ALPHA), self.client_tools(BRAVO))

    def test_the_catalogue_is_not_empty_and_excludes_internal_tools(self):
        for slug in SIDES:
            names = self.client_tools(slug)
            self.assertGreater(len(names), 10, slug)
            for internal_only in ("next_actions", "who_does_what",
                                  "credits", "promises", "monitors"):
                self.assertNotIn(internal_only, names, slug)

    def test_every_client_tool_returns_a_readback_for_both(self):
        """Not a crash and not a bare error, on either side.

        A tool that raises returns `_error` from `run`, which is a readback
        the model would repeat. `_error` here means this increment broke
        something, so it fails rather than being tolerated.
        """
        for slug in SIDES:
            for name in self.client_tools(slug):
                with self.subTest(workspace=slug, tool=name):
                    result = self.ask(slug, name,
                                      self.argument_for(slug, name))
                    self.assertIsInstance(result, dict)
                    self.assertNotIn("_error", result,
                                     "%s errored for %s: %s"
                                     % (name, slug, result.get("_error")))

    def test_the_tools_that_take_no_argument_answer_for_both(self):
        for name in ("weekly_report", "sender_summary", "sending_domains",
                     "sender_roster", "activity_this_week", "replies",
                     "batch_state", "weekly_plan", "sends_today",
                     "held_by_reason", "timeline"):
            for slug in SIDES:
                with self.subTest(tool=name, workspace=slug):
                    result = self.ask(slug, name)
                    self.assertNotIn("_error", result)


# ============================== 3. ZERO CROSS-VISIBILITY, FROM BOTH SIDES

class NeitherClientSeesTheOther(TwoClientEstate):
    """The assertion this whole file exists for, and it runs twice."""

    def test_no_client_tool_carries_the_others_markers(self):
        cases = EveryClientToolRunsForBothWorkspaces
        for slug, other in OTHER.items():
            for name in self.client_tools(slug):
                argument = cases.argument_for(slug, name)
                with self.subTest(workspace=slug, tool=name):
                    result = self.ask(slug, name, argument)
                    self.assert_no_trace_of(
                        other, self.text_of(name, result, argument),
                        "%s for %s" % (name, slug))

    def test_asking_with_the_others_argument_leaks_nothing_either(self):
        """The prompt-injected question: ask alpha's channel about bravo.

        Every argument-taking tool, handed the OTHER client's own value.

        THE ARGUMENT ITSELF IS NOT A LEAK and is excluded from the marker
        set. `campaign_detail` refuses with "campaign 8201 does not belong
        to this channel's workspace", which echoes the id the ASKER
        supplied - it tells them nothing they did not type. What would be a
        leak is the answer carrying anything else of the other client's, or
        the refusal differing from the one a made-up id gets, and the test
        below this one asserts that second half word for word.
        """
        cases = EveryClientToolRunsForBothWorkspaces
        for slug, other in OTHER.items():
            for name, key in cases.ARGUMENTS.items():
                if name not in self.client_tools(slug):
                    continue
                argument = SIDES[other][key]
                with self.subTest(workspace=slug, tool=name):
                    result = self.ask(slug, name, argument)
                    text = self.text_of(name, result, None)
                    self.assert_no_trace_of(
                        other, text.replace(argument.lower(), "<asked>"),
                        "%s for %s asked about %s" % (name, slug, other))

    def test_the_refusal_is_the_same_for_a_rival_and_for_a_fiction(self):
        """A campaign id nobody has must be refused in the same words.

        If the other client's id were refused differently from an invented
        one - a different sentence, a different key, anything - then trying
        ids would be a way to learn which exist.
        """
        fiction = "9999999"
        for slug, other in OTHER.items():
            rival = self.ask(slug, "campaign_detail",
                             SIDES[other]["provider_campaign_id"])
            invented = self.ask(slug, "campaign_detail", fiction)
            self.assertEqual(
                json.dumps({k: str(v).replace(
                    SIDES[other]["provider_campaign_id"], "<id>")
                    for k, v in sorted(rival.items()) if k != "read_at"}),
                json.dumps({k: str(v).replace(fiction, "<id>")
                            for k, v in sorted(invented.items())
                            if k != "read_at"}),
                "%s told a real campaign of %s apart from a made-up one"
                % (slug, other))

    def test_the_whole_catalogue_run_at_once_leaks_nothing(self):
        """`run_all` is how a turn really calls them - up to five at once."""
        for slug, other in OTHER.items():
            names = [n for n in self.client_tools(slug)
                     if n not in EveryClientToolRunsForBothWorkspaces
                     .ARGUMENTS][:tools.MAX_CALLS_PER_TURN]
            results = tools.run_all(self.scope_for(slug),
                                    [{"name": n} for n in names])
            self.assert_no_trace_of(other, tools.render(results),
                                    "run_all for %s" % slug)

    def test_each_side_really_does_see_its_own(self):
        """THE CONTROL, and without it this file is worthless.

        Every assertion above is satisfied by a tool that answers nothing.
        Isolation achieved by emptiness is not isolation - it is the
        confidently-empty failure this project has hit four times, wearing
        the colours of a security property.

        So each client's own markers must actually APPEAR across its own
        catalogue. Not all of them in one answer; each of them somewhere.
        """
        cases = EveryClientToolRunsForBothWorkspaces
        for slug in SIDES:
            seen = []
            for name in self.client_tools(slug):
                argument = cases.argument_for(slug, name)
                seen.append(self.text_of(
                    name, self.ask(slug, name, argument), argument))
            blob = "\n".join(seen).lower()
            for marker in (SIDES[slug]["company"], SIDES[slug]["domain"],
                           SIDES[slug]["provider_campaign_id"],
                           SIDES[slug]["sending_domain"],
                           SIDES[slug]["subject"],
                           SIDES[slug]["contact"]):
                self.assertIn(
                    marker.lower(), blob,
                    "%s never saw its OWN %r - the isolation assertions "
                    "would pass on an empty answer" % (slug, marker))

    def test_the_answers_that_could_be_empty_are_not(self):
        """The control, per tool, where an argument cannot fake it.

        `test_each_side_really_does_see_its_own` searches the whole
        catalogue's output, and a marker can get in there just by being
        echoed back from the argument - which is how `sending_domains`
        answering "no authorized email sender is recorded for this
        workspace" went unnoticed on the first pass. These four take no
        argument at all, so what they contain, they found.
        """
        for slug in SIDES:
            side = SIDES[slug]
            domains = self.ask(slug, "sending_domains")
            self.assertEqual(domains.get("senders") and len(
                domains["senders"]), 1, "%s: %s" % (slug, domains))
            self.assertIn(side["sending_domain"],
                          json.dumps(domains, default=str))

            roster = self.ask(slug, "sender_roster")
            self.assertIn(side["sender_name"],
                          json.dumps(roster, default=str), slug)

            summary = self.ask(slug, "sender_summary")
            self.assertEqual(summary.get("email_sending_accounts"), 1, slug)
            self.assertEqual(summary.get("campaigns_they_serve"), 1, slug)

            copy = self.ask(slug, "campaign_copy", "day1")
            self.assertIn(side["subject"], json.dumps(copy, default=str),
                          "%s sees no approved copy: %s" % (slug, copy))

    def test_a_slug_argument_never_moves_the_answer_to_the_other_client(self):
        """The most obvious injection there is: name the other workspace.

        `workspace_summary`, `cadence_detail` and `sender_summary` take a
        workspace SLUG. In a client channel the argument is ignored, so
        each must answer about the asker and say the asker's own name back.
        """
        for slug, other in OTHER.items():
            for name in ("cadence_detail", "sender_summary"):
                with self.subTest(workspace=slug, tool=name):
                    answer = self.ask(slug, name, other)
                    self.assertEqual(answer.get("workspace"), slug)
                    self.assert_no_trace_of(
                        other, self.text_of(name, answer),
                        "%s in %s asked for %s" % (name, slug, other))

            # `workspace_summary` returns the pack entry verbatim and is the
            # one client tool that does not stamp `workspace` on its answer.
            # So it is checked by its content: the asker's own name, and
            # nothing of the other's.
            with self.subTest(workspace=slug, tool="workspace_summary"):
                answer = self.ask(slug, "workspace_summary", other)
                self.assertEqual(answer.get("name"), SIDES[slug]["name"])
                self.assert_no_trace_of(
                    other, self.text_of("workspace_summary", answer),
                    "workspace_summary in %s asked for %s" % (slug, other))

    def test_the_shared_provider_really_did_hold_both(self):
        """The fixture's own guard.

        If the fake ever stops carrying both clients, every assertion above
        passes for the wrong reason - there would be nothing to leak. So the
        estate is asserted to be shared.
        """
        estate, _meta = self.provider.sender_emails()
        addresses = {row["email"] for row in estate}
        self.assertEqual(addresses, {SIDES[ALPHA]["mailbox"],
                                     SIDES[BRAVO]["mailbox"]})
        rows, _cursor = self.provider.fetch_replies()
        campaigns = {str(row["campaign_id"]) for row in rows}
        self.assertEqual(campaigns,
                         {SIDES[ALPHA]["provider_campaign_id"],
                          SIDES[BRAVO]["provider_campaign_id"]})
        for slug in SIDES:
            self.assertTrue(
                self.provider.campaign(SIDES[slug]["provider_campaign_id"]),
                "the fake stopped answering for %s" % slug)


# ============================== 4. THE ARGUMENT IS IGNORED, NOT VALIDATED

class TheArgumentNeverWidensAScope(TwoClientEstate):

    def test_the_workspace_argument_is_ignored_in_a_client_channel(self):
        for slug, other in OTHER.items():
            scope = self.scope_for(slug)
            self.assertEqual(tools._workspace_for(scope, other), slug)
            self.assertEqual(tools._workspace_for(scope, other.upper()), slug)
            self.assertEqual(tools._workspace_for(scope, None), slug)

    def test_an_internal_channel_may_still_name_either(self):
        """The pinning is a CLIENT property, not a global one.

        If it were global this file would pass by making the tools useless
        to the operator, which is not isolation.
        """
        scope = self.internal_scope()
        for slug in SIDES:
            self.assertEqual(tools._workspace_for(scope, slug), slug)

    def test_the_others_campaign_is_not_visible_from_either_side(self):
        for slug, other in OTHER.items():
            scope = self.scope_for(slug)
            self.assertFalse(tools._campaign_is_visible(
                scope, SIDES[other]["provider_campaign_id"]))
            self.assertTrue(tools._campaign_is_visible(
                scope, SIDES[slug]["provider_campaign_id"]))

    def test_records_and_campaign_rows_are_pinned_both_ways(self):
        for slug, other in OTHER.items():
            clients = {r.get("client") for r in tools._records(slug)}
            self.assertEqual(clients, {slug})
            self.assertNotIn(other, clients)
            rows = {r.get("client") for r in tools._campaign_rows(slug)}
            self.assertEqual(rows, {slug})


# ============================== 5. A STRANGER AND A RIVAL READ ALIKE

class TheOthersAccountReadsLikeNobodys(TwoClientEstate):
    """Word for word, from both sides. The difference IS the leak."""

    NOBODY_DOMAIN = "nobody-has-this-domain-at-all.test"
    NOBODY_ADDRESS = "nobody@nobody-has-this-domain-at-all.test"

    def _note(self, result):
        """Everything the answer says, minus when it was read."""
        return json.dumps({k: v for k, v in sorted(result.items())
                           if k not in ("read_at",)},
                          default=str, sort_keys=True)

    def test_account_status_says_the_same_thing_about_both(self):
        for slug, other in OTHER.items():
            rival = self.ask(slug, "account_status", SIDES[other]["domain"])
            stranger = self.ask(slug, "account_status", self.NOBODY_DOMAIN)
            self.assertEqual(
                self._note(rival).replace(SIDES[other]["domain"],
                                          self.NOBODY_DOMAIN),
                self._note(stranger),
                "account_status told %s apart from a stranger, in %s"
                % (other, slug))

    def test_account_lookup_says_the_same_thing_about_both(self):
        for slug, other in OTHER.items():
            rival = self.ask(slug, "account_lookup", SIDES[other]["domain"])
            stranger = self.ask(slug, "account_lookup", self.NOBODY_DOMAIN)
            self.assertEqual(
                self._note(rival).replace(SIDES[other]["domain"],
                                          self.NOBODY_DOMAIN),
                self._note(stranger))

    def test_lead_lookup_says_the_same_thing_about_both(self):
        for slug, other in OTHER.items():
            rival = self.ask(slug, "lead_lookup", SIDES[other]["contact"])
            stranger = self.ask(slug, "lead_lookup", self.NOBODY_ADDRESS)
            self.assertEqual(
                self._note(rival).replace(SIDES[other]["contact"],
                                          self.NOBODY_ADDRESS),
                self._note(stranger))

    def test_lead_in_campaign_says_the_same_thing_about_both(self):
        """The hard one: the provider CAN see the other client's lead.

        `find_lead_by_email` in the shared fake answers for bravo's address
        whoever asks. The answer must still read like a stranger's, which
        means the campaign scoping has to do the work after the provider
        has already said yes.
        """
        for slug, other in OTHER.items():
            rival = self.ask(slug, "lead_in_campaign",
                             SIDES[other]["contact"])
            stranger = self.ask(slug, "lead_in_campaign",
                                self.NOBODY_ADDRESS)
            self.assertEqual(
                self._note(rival).replace(SIDES[other]["contact"],
                                          self.NOBODY_ADDRESS),
                self._note(stranger))

    def test_its_own_account_reads_differently_from_a_stranger(self):
        """The control.

        Four tests above pass trivially if every answer is the same answer.
        A client's OWN account must be distinguishable, or isolation has
        been achieved by making the tool useless.
        """
        for slug in SIDES:
            mine = self.ask(slug, "account_status", SIDES[slug]["domain"])
            stranger = self.ask(slug, "account_status", self.NOBODY_DOMAIN)
            self.assertNotEqual(
                self._note(mine).replace(SIDES[slug]["domain"],
                                         self.NOBODY_DOMAIN),
                self._note(stranger),
                "%s cannot tell its own account from a stranger's" % slug)


# ============================== 6. ACCOUNTS FIRST, PER WORKSPACE

class TheAccountsFirstAnswersAreComputedPerWorkspace(TwoClientEstate):

    def test_the_rollup_counts_only_this_workspaces_records(self):
        for slug in SIDES:
            counts, unanswerable, _ok = tools._account_rollup(slug)
            total = sum(counts.values()) + unanswerable
            self.assertEqual(total, 2,
                             "%s counted %d accounts, and it owns 2"
                             % (slug, total))

    def test_the_weekly_report_leads_with_accounts_for_both(self):
        for slug in SIDES:
            report = self.ask(slug, "weekly_report")
            self.assertNotIn("_error", report)
            keys = list(report)
            self.assertIn("accounts", keys, slug)
            self.assertIn("emails", keys, slug)
            self.assertLess(keys.index("accounts"), keys.index("emails"),
                            "%s put emails before accounts" % slug)

    def test_the_weekly_report_carries_no_trace_of_the_other(self):
        for slug, other in OTHER.items():
            report = self.ask(slug, "weekly_report")
            self.assert_no_trace_of(other,
                                    self.text_of("weekly_report", report),
                                    "weekly_report for %s" % slug)

    def test_unanswerable_is_its_own_number_on_both_sides(self):
        """Never folded into `untouched`, per 2619f536.

        With no write-back, both synthetic clients are as unanswerable as
        the real one, and the report must say so in both channels rather
        than reporting a confident zero.
        """
        for slug in SIDES:
            report = self.ask(slug, "weekly_report")
            accounts = report.get("accounts") or {}
            self.assertIn("unanswerable", accounts, slug)

    def test_the_reply_ledger_is_per_workspace(self):
        for slug, other in OTHER.items():
            mine = tools._ledger_replies(slug)
            self.assertIsNotNone(mine)
            self.assertEqual(mine["by_class"].get("out_of_office"), 1,
                             "%s should see exactly its own one reply, not "
                             "the other's as well: %s" % (slug, mine))

    def test_account_status_answers_about_its_own_account_for_both(self):
        for slug in SIDES:
            answer = self.ask(slug, "account_status", SIDES[slug]["domain"])
            self.assertNotIn("_error", answer)
            self.assertEqual(str(answer.get("domain") or "").lower(),
                             SIDES[slug]["domain"])


# ============================== 7. THE BACKSTOP IS ARMED BOTH WAYS

class TheOutboundBackstopIsArmedForBothScopes(TwoClientEstate):

    def test_naming_the_other_workspace_raises_from_either_side(self):
        for slug, other in OTHER.items():
            scope = self.scope_for(slug)
            with self.assertRaises(slackscope.ScopeViolation):
                scope.check_outbound(
                    "Here is an update on %s this week." % other)

    def test_its_own_name_passes_from_either_side(self):
        for slug in SIDES:
            scope = self.scope_for(slug)
            text = "Here is an update on %s this week." % slug
            self.assertEqual(scope.check_outbound(text), text)

    def test_the_guard_reads_the_slug_set_from_resolution(self):
        """Not a second read of the store, which could disagree.

        The scope is resolved, the store is then emptied, and the guard must
        still stop the other client's name. A re-read here would find no
        workspaces and pass on everything.
        """
        scope = self.scope_for(ALPHA)
        work = os.path.join(self.tmp, "work")
        with open(os.path.join(work, "workspaces.jsonl"), "w",
                  encoding="utf-8"):
            pass
        with self.assertRaises(slackscope.ScopeViolation):
            scope.check_outbound("an update on %s" % BRAVO)


# ============== 8. THE SENDER COUNT READS BOTH SHAPES THE STORE HOLDS

class TheSenderCountReadsBothShapesOfTheStore(TwoClientEstate):
    """Found while furnishing this fixture, and it is not the fixture.

    `sender_summary` read `provider_account_id or account_id` and
    stringified the result. The live campaign store also holds 13 sender
    entries carrying only `id` - and on those, the expression is the STRING
    "None", so every such entry across every campaign counted as ONE shared
    sending account.

    Measured on the live store before the fix:

        productive   156 email sending accounts, one of which is the
                     "None" bucket standing for 3 real entries
        contactout     1 - and that 1 IS the bucket, because both of its
                       entries carry only `id`

    Nothing asserted these counts anywhere, which is why it survived.
    """

    def _add_campaign(self, side, campaign_id, senders):
        work = os.path.join(self.tmp, "work")
        path = os.path.join(work, "campaigns.jsonl")
        row = dict(_campaign_row(side), campaign_id=campaign_id,
                   bison_campaign_id=None, senders=senders, record_ids=[])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def test_an_entry_carrying_only_id_is_counted_by_that_id(self):
        self.assertEqual(
            tools._sending_account_id({"id": "bison-a", "daily_limit": 50}),
            "bison-a")

    def test_the_named_fields_still_win_in_order(self):
        self.assertEqual(tools._sending_account_id(
            {"provider_account_id": "p", "account_id": "a", "id": "i"}), "p")
        self.assertEqual(tools._sending_account_id(
            {"account_id": "a", "id": "i"}), "a")

    def test_an_entry_with_no_identifier_at_all_is_not_an_account(self):
        """None, not the string "None".

        Returning a value here is what created the shared bucket. The
        caller counts these apart and says how many there were.
        """
        self.assertIsNone(tools._sending_account_id({"daily_limit": 50}))
        self.assertIsNone(tools._sending_account_id({}))
        self.assertIsNone(tools._sending_account_id({"id": ""}))

    def test_two_demo_shaped_entries_are_two_accounts_not_one(self):
        """The live defect, reproduced at the size it was found.

        Before the fix this answered 1 for both entries together, which is
        exactly what ContactOut's real answer was.
        """
        self._add_campaign(SIDES[ALPHA], "alpha-demo", {
            "email": [{"id": "bison-a", "daily_limit": 50},
                      {"id": "bison-b", "daily_limit": 50}],
            "linkedin": []})
        summary = self.ask(ALPHA, "sender_summary")
        self.assertEqual(summary.get("email_sending_accounts"), 3)
        self.assertNotIn("sender_entries_without_an_id", summary)

    def test_an_unidentifiable_entry_is_reported_and_never_counted(self):
        self._add_campaign(SIDES[BRAVO], "bravo-broken", {
            "email": [{"daily_limit": 50}], "linkedin": []})
        summary = self.ask(BRAVO, "sender_summary")
        self.assertEqual(summary.get("email_sending_accounts"), 1)
        self.assertEqual(summary.get("sender_entries_without_an_id"), 1)

    def test_the_other_clients_demo_campaign_is_still_not_counted(self):
        """The fix widened a READ. It must not have widened the scope."""
        self._add_campaign(SIDES[BRAVO], "bravo-demo", {
            "email": [{"id": "bison-z", "daily_limit": 50}],
            "linkedin": []})
        self.assertEqual(
            self.ask(ALPHA, "sender_summary").get(
                "email_sending_accounts"), 1)
        self.assertEqual(
            self.ask(BRAVO, "sender_summary").get(
                "email_sending_accounts"), 2)


if __name__ == "__main__":
    unittest.main()
