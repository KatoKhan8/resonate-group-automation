"""Production hand-wrote 15 monitors tonight. The derived table must cover them.

WHY THIS EXISTS. On 2026-09-23, after blank emails went out of campaign 497,
production hand-edited BOTH monitor tables - `src/supervisor.py`'s constant
and `scripts/start_monitors.py`'s list - to 15 entries, adding 491-498. This
branch had already replaced both with one derived table, so the merge deleted
both hand-written lists. Deleting them is only safe if the rule PRODUCES what
they listed, and "it should" is not a test.

So this file pins the derived set against the 15, BY NAME.

THE 15 ARE NOT THE ANSWER, THEY ARE THE FLOOR. The derived set at today's
registry is 20, and the difference is the whole argument for deriving:

  +493   an APPROVED campaign in the same batch as 491-498, which
         production's hand-written list does not contain. Nobody decided to
         leave it out; it is the same forgetting that left 496, 497 and 498
         unwatched until the night 497 sent blank emails and a person noticed
         BY HAND. The rule does not forget, so 493 is watched.

  +451, +481, +484, +485
         four campaigns the registry calls `draft`. They are watched because
         THE REGISTRY CANNOT BE TRUSTED TO SAY WHAT IS SENDING, and 497 is the
         proof: its row says `status=approved, launch.state=not_launched`
         while it was sending the blank emails this gate exists for. A rule
         that dropped a watcher on `launch.state` would read 497's own row and
         retire the watcher for the campaign in the incident. So the rule
         watches every campaign that has a provider id, and over-watching
         costs provider calls where under-watching costs an unwatched sender.

Hence: SUPERSET, and a BOUNDED one. Every production name must be present, and
the extras must be exactly those five. A sixth extra appearing, or any of the
15 disappearing, fails here rather than going quiet in production.

NO REAL REGISTRY IS COMMITTED. The rows below carry provider campaign ids and
statuses only - the same ids already written in both tables' comments - and no
client, name, address or contact. Verified against the real registry at
2026-09-23: it derives these same 20 names.
"""
import ast
import io
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import supervisor  # noqa: E402

#: Today's registry, reduced to the two fields the rule reads. Statuses are
#: verbatim: the live vocabulary is `approved` / `draft` / `awaiting_approval`,
#: and NONE of them is in `LIVE_STATUSES` or `FINISHED_STATUSES`.
TODAYS_REGISTRY = (
    [{"campaign_id": "b%d" % cid, "status": "draft", "bison_campaign_id": cid}
     for cid in (451, 481, 484, 485)]
    + [{"campaign_id": "b%d" % cid, "status": "approved",
        "bison_campaign_id": cid}
       for cid in (487, 489, 491, 492, 493, 494, 495, 496, 497, 498)]
    + [{"campaign_id": "h594061", "status": "paused",
        "heyreach_campaign_id": 594061}]
    + [{"campaign_id": "h%d" % cid, "status": "approved",
        "heyreach_campaign_id": cid}
       for cid in (599020, 604869, 605487, 605732)]
    + [{"campaign_id": "unlaunched-%d" % i, "status": "awaiting_approval"}
       for i in range(6)]
)

#: The 15 production hand-wrote, spelled the way the derived table spells
#: them. `start_monitors.py` wrote them hyphenated (`bison-497`); the
#: supervisor's names are the canonical ones and the two differ only in
#: spelling, which is itself an argument for one table.
THE_INCIDENT_GATES_15 = {
    "reply_watch",
    "notify_deliver",
    "digest",
    "slack_agent",
    "slack_followup",
    "heyreach_watch_605732",
    "bison_watch_487",
    "bison_watch_489",
    "bison_watch_491",
    "bison_watch_492",
    "bison_watch_494",
    "bison_watch_495",
    "bison_watch_496",
    "bison_watch_497",
    "bison_watch_498",
}

#: Watched, and deliberately not in the 15. See the module docstring.
THE_FIVE_THE_HAND_WRITTEN_LIST_MISSED = {
    "bison_watch_493",
    "bison_watch_451",
    "bison_watch_481",
    "bison_watch_484",
    "bison_watch_485",
}

#: Added to the static half AFTER this file was written, each with a reason.
#: Named individually rather than loosening the ceiling to "20 or more",
#: because the ceiling is the only thing standing between a derived table and
#: a watcher nobody chose.
ADDED_SINCE_WITH_A_REASON = {
    # `scripts/weekly_report_loop.py` existed from 2026-09-23 and was in no
    # table, so nothing started it and `--status` could not report it
    # missing. An absent row reads as a healthy estate - the same shape as
    # 493 having no watcher. Operator instruction 2026-09-24.
    "weekly_report",
}


def _derived_names():
    """The derived set at today's registry.

    `sequence_source` returns 0 - "nothing is in sequence" - which is the
    HARSHEST input the rule can be given: it is the only answer that lets a
    campaign retire. Anything still watched under it is watched on the
    campaign's own status, not on the benefit of the doubt.
    """
    return {m["name"] for m in supervisor.monitors(
        rows=TODAYS_REGISTRY, sequence_source=lambda provider, cid: 0)}


class TheDerivedTableCoversTheIncidentGate(unittest.TestCase):

    def test_every_one_of_the_15_is_derived_by_name(self):
        """The floor. Deleting two hand-written lists is safe only if this
        holds - otherwise the merge silently unwatches a campaign that was
        watched tonight, which is the incident happening again through the
        fix for it."""
        missing = THE_INCIDENT_GATES_15 - _derived_names()
        self.assertEqual(
            set(), missing,
            "the derived table lost monitors production hand-wrote tonight: %s"
            % (sorted(missing),))

    def test_the_derived_set_is_exactly_the_15_plus_the_five_named_extras(self):
        """The ceiling. A superset is only defensible while every member of it
        is accounted for; an unexplained extra is a watcher nobody chose."""
        self.assertEqual(
            THE_INCIDENT_GATES_15 | THE_FIVE_THE_HAND_WRITTEN_LIST_MISSED
            | ADDED_SINCE_WITH_A_REASON,
            _derived_names())

    def test_493_is_watched_although_the_hand_written_list_omits_it(self):
        """The argument for deriving, stated as an assertion. 493 is approved,
        in the same batch as 491-498, and absent from the list a person typed
        while fixing an incident caused by three campaigns being absent from
        the list a person typed."""
        self.assertIn("bison_watch_493", _derived_names())
        self.assertNotIn("bison_watch_493", THE_INCIDENT_GATES_15)

    def test_a_draft_is_still_watched_because_497_sent_while_not_launched(self):
        """A regression guard on a fix nobody should make. Dropping the four
        drafts would make the derived set equal the 15 exactly - and would
        read `launch.state` / `status`, the same fields that call 497
        `not_launched` while it was sending."""
        names = _derived_names()
        for cid in (451, 481, 484, 485):
            self.assertIn("bison_watch_%d" % cid, names)


class TheHeyreachEntryIsDeclaredNotDerived(unittest.TestCase):
    """`heyreach_watch_loop` watches a HARDCODED campaign and takes no
    `--campaign`, so which campaign it watches is not a fact about the
    registry. Deriving it picked 594061 out of the five heyreach rows and
    resolved the heartbeat to `heyreach-594061.json`, which nothing writes."""

    def test_the_declared_heyreach_campaign_is_the_loops_own(self):
        """Read from the source, not imported: importing the loop pulls in
        providers. If either constant moves, this fails."""
        path = os.path.join(ROOT, "scripts", "heyreach_watch_loop.py")
        with io.open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), path)
        found = [node.value.value
                 for node in ast.walk(tree)
                 if isinstance(node, ast.Assign)
                 and isinstance(node.value, ast.Constant)
                 for target in node.targets
                 if isinstance(target, ast.Name) and target.id == "PROVIDER_ID"]
        self.assertEqual(1, len(found),
                         "expected exactly one PROVIDER_ID in the loop")
        self.assertEqual(str(found[0]), supervisor.HEYREACH_CAMPAIGN)

    def test_the_heyreach_heartbeat_is_the_file_the_loop_writes(self):
        """The defect itself, pinned. `heartbeat_file` must name the file the
        loop actually beats to, or `cold_start --verify` polls a path nothing
        writes and reports the monitor down forever."""
        table = supervisor.monitors(rows=TODAYS_REGISTRY,
                                    sequence_source=lambda p, c: 0)
        entries = [m for m in table if "heyreach" in m["name"]]
        self.assertEqual(1, len(entries),
                         "one heyreach loop, however many campaigns exist")
        self.assertEqual(
            "heyreach-605732.json",
            os.path.basename(supervisor.heartbeat_file(entries[0])))

    def test_the_registrys_other_heyreach_rows_do_not_become_monitors(self):
        """Five heyreach rows, one loop. The other four must not appear."""
        names = _derived_names()
        for cid in (594061, 599020, 604869, 605487):
            self.assertNotIn("heyreach_watch_%d" % cid, names)


if __name__ == "__main__":
    unittest.main()
