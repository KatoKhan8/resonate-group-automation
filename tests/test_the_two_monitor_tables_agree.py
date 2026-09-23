"""There are two monitor tables and they disagree about what production runs.

MEASURED 2026-09-23, while writing the systemd units for 2b.

    scripts/start_monitors.py   MONITORS   12 entries   on master, and it is
                                                        what has actually been
                                                        starting the estate
    src/supervisor.py           MONITORS    8 entries   on infra, and it is
                                                        what `supervise
                                                        --status` and
                                                        `cold_start --verify`
                                                        read

They differ in BOTH directions:

    only in start_monitors   bison-491, bison-492, bison-494, bison-495,
                             slack-followup
    only in supervisor       bison_mailbox_utilisation

**The four missing bison watchers are the live campaigns.** 491-498 are the
ACTIVE cohort - `CLAUDE.md` says so, and master's own commits tonight are
about 491 going blind at 647 queue rows and 495 being archived by nobody we
can name. The two the supervisor DOES carry, 487 and 489, are the historical
pair.

So a host whose units are generated from `supervisor.MONITORS` would watch
two campaigns that are finished and none of the four that are sending, and
`cold_start --verify` would report the estate healthy while doing it. That
is the failure `supervisor.py`'s own docstring opens with - "gone quiet" and
"died" being indistinguishable - arriving one level up, at the table itself.

`scripts/start_monitors.py` predicted this in its own words:

    `src/supervisor.py` (TASK-263) lives on branch `infra` and is not
    merged. When it is, this file's job shrinks to starting the supervisor,
    and the per-monitor table below moves into it.

The merge happened tonight (`a4924f7c`). The table did not move, and now
both exist.

## WHY THIS TEST DOES NOT FIX IT

Which monitors production runs is a decision about running production loops,
and this session does not own those - the same boundary the night handoff
drew for the two heartbeat findings in its §3b. Four questions have to be
answered by the session that does:

    1. 487 and 489 are finished. Keep watching them, or retire them?
    2. 495 was archived at 15:57:22Z today by nobody we can name. A watcher
       on an archived campaign still reports transitions - keep it?
    3. `bison_mailbox_utilisation` is in the supervisor table and has never
       been in the start_monitors one. IS IT RUNNING IN PRODUCTION AT ALL?
       It writes no heartbeat, so its own status can never answer this.
    4. 493, 496, 497 and 498 have first sends on 09-24 and are watched by
       neither table. They become live tomorrow.

This test FAILS until they are answered, and names the difference rather
than a count. A count would have said 12 against 8 and told nobody which
campaign was unwatched.
"""
import unittest


def _supervisor_names():
    from src import supervisor

    return {m["name"] for m in supervisor.MONITORS}


def _start_monitors_names():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "start_monitors.py"
    spec = importlib.util.spec_from_file_location("_start_monitors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name for name, _ in module.MONITORS}


def _canonical(name):
    """The two tables spell the same monitor differently: `bison_watch_487`
    against `bison-487`, `notify_deliver` against `notify-deliver`. Compare
    the monitors, not the punctuation - otherwise this test reports twelve
    differences and hides the four that matter."""
    name = name.replace("_", "-")
    name = name.replace("bison-watch-", "bison-")
    name = name.replace("reply-watch", "replies")
    name = name.replace("heyreach-watch", "heyreach")
    # heyreach-605732 in one table, heyreach_watch in the other: one loop,
    # and it takes no --campaign (passing one made argparse exit 2).
    if name.startswith("heyreach"):
        return "heyreach"
    return name


class TestTheTwoMonitorTablesAgree(unittest.TestCase):
    def test_every_monitor_production_starts_is_in_the_supervisor_table(self):
        """The dangerous direction. A loop production runs that the
        supervisor does not know about is a loop no systemd unit will be
        generated for and no --verify will notice is missing."""
        started = {_canonical(n) for n in _start_monitors_names()}
        supervised = {_canonical(n) for n in _supervisor_names()}
        missing = sorted(started - supervised)
        self.assertEqual(
            missing, [],
            "production starts these and the supervisor does not carry them, "
            "so units generated from supervisor.MONITORS would not run them "
            f"and cold_start --verify would not miss them: {missing}",
        )

    def test_the_supervisor_carries_no_monitor_nobody_starts(self):
        """The other direction is not safe either: a monitor in the table
        that nothing starts reads DOWN forever, or - if it writes no
        heartbeat - UP_ONE_WITNESS forever, which is worse because it looks
        like an answer."""
        started = {_canonical(n) for n in _start_monitors_names()}
        supervised = {_canonical(n) for n in _supervisor_names()}
        extra = sorted(supervised - started)
        self.assertEqual(
            extra, [],
            "the supervisor carries these and nothing starts them: "
            f"{extra}",
        )

    def test_the_live_campaigns_are_watched(self):
        """Named explicitly, because the set difference above would go green
        the moment somebody deleted the four entries from start_monitors
        instead of adding them to the supervisor.

        491-498 are the ACTIVE cohort. 493, 496, 497 and 498 have first sends
        on 2026-09-24 and are deliberately not asserted yet - the day they
        send, this list is what has to grow."""
        supervised = {_canonical(n) for n in _supervisor_names()}
        for campaign in ("491", "492", "494"):
            self.assertIn(
                f"bison-{campaign}", supervised,
                f"campaign {campaign} is live and the supervisor does not "
                "watch it",
            )


if __name__ == "__main__":
    unittest.main()
