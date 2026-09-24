"""A/B the readback cache and the per-campaign fan-out, offline.

THIS IS A MECHANISM MEASUREMENT, NOT A LIVE LATENCY MEASUREMENT. The
provider is a stub with a fixed per-call delay, so what it proves is that
the change removes the serial round trips it was built to remove. The live
p50/p95 still has to come from the replay harness against the real
provider; this cannot and does not stand in for it.

The "before" configuration is exactly the old code: PROVIDER_FANOUT = 1
and READBACK_TTL = 0. Nothing is reverted to measure it.

    py -3 measure_fanout.py [--call-seconds 1.4] [--campaigns 10]
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import store                                            # noqa: E402


def stub_provider(delay, ids):
    """`bison.campaign` and `bison.scheduled_emails`, each costing `delay`."""
    from src.providers import bison
    calls = {"n": 0}

    def campaign(campaign_id):
        calls["n"] += 1
        time.sleep(delay)
        return {"id": campaign_id, "name": "campaign %s" % campaign_id,
                "status": "active", "emails_sent": 40, "replied": 2,
                "bounced": 1, "unsubscribed": 0, "total_leads": 50,
                "updated_at": "2026-09-24T07:00:00Z"}

    def scheduled_emails(campaign_id, cap=None):
        calls["n"] += 1
        time.sleep(delay)
        return [{"status": "sent", "sent_at": "2026-09-23T09:00:00Z",
                 "scheduled_date": "2026-09-23", "lead_id": i,
                 "sender_email": "s@sending-domain-a.example.test"}
                for i in range(20)]

    def sending_schedule(campaign_id, day):
        calls["n"] += 1
        time.sleep(delay)
        return {"emails_being_sent": 12}

    def campaign_lead_count(campaign_id):
        calls["n"] += 1
        time.sleep(delay)
        return 50

    bison.campaign = campaign
    bison.scheduled_emails = scheduled_emails
    bison.campaign_lead_count = campaign_lead_count
    bison.sending_schedule = sending_schedule
    return calls


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--call-seconds", type=float, default=1.4)
    parser.add_argument("--campaigns", type=int, default=10)
    args = parser.parse_args(argv)

    work = tempfile.mkdtemp(prefix="rga-measure-")
    store.use_directory(work)
    os.environ["OUT"] = os.path.join(work, "out")

    from src import slackagenttools as tools
    from src import slackagentreadback as readback
    from src import slackknowledge as knowledge
    from src import slackscope

    ids = [str(490 + i) for i in range(args.campaigns)]
    calls = stub_provider(args.call_seconds, ids)

    pack = {"workspaces": {"productive": {"provider_campaign_ids": ids}}}
    knowledge.pack = lambda *a, **k: pack

    scope = slackscope.Scope(slackscope.CLIENT, workspace="productive",
                             source="measure")

    TOOLS = (("sends_today", tools.sends_today),
             ("activity_this_week", tools.activity_this_week),
             ("weekly_plan", tools.weekly_plan),
             ("lead_counts", tools.lead_counts))

    def run(label, fanout, ttl):
        old_fanout, old_ttl = tools.PROVIDER_FANOUT, readback.READBACK_TTL
        tools.PROVIDER_FANOUT, readback.READBACK_TTL = fanout, ttl
        print("\n%s  (fan-out %d, cache TTL %gs)" % (label, fanout, ttl))
        print("  %-22s %8s %8s" % ("tool", "seconds", "calls"))
        readback.cache_clear()
        calls["n"] = 0
        turn_started = time.monotonic()
        # ONE TURN, which is what the cache is scoped to. Outside a
        # turn `cached` is a pass-through, so measuring without this
        # reports 146 calls in BOTH columns and makes the cache look
        # like it does nothing - see `readback._TURN_DEPTH`. Measured
        # that way once by accident, which is the cheapest possible
        # proof that the scoping works.
        turn = readback.turn()
        turn.__enter__()
        for name, fn in TOOLS:
            before = calls["n"]
            started = time.monotonic()
            try:
                fn(scope, None)
            except Exception as exc:                            # noqa: BLE001
                print("  %-22s FAILED %s: %s" % (name, type(exc).__name__,
                                                 str(exc)[:60]))
                continue
            print("  %-22s %8.2f %8d" % (name, time.monotonic() - started,
                                         calls["n"] - before))
        turn.__exit__(None, None, None)
        total = time.monotonic() - turn_started
        print("  %-22s %8.2f %8d   <- a four-tool turn"
              % ("TURN", total, calls["n"]))
        tools.PROVIDER_FANOUT, readback.READBACK_TTL = old_fanout, old_ttl
        return total, calls["n"]

    print("stub provider: %.2fs per call, %d campaigns"
          % (args.call_seconds, args.campaigns))
    before_s, before_c = run("BEFORE - serial, no cache", 1, 0)
    after_s, after_c = run("AFTER  - fan-out %d, 60s cache"
                           % tools.PROVIDER_FANOUT,
                           tools.PROVIDER_FANOUT, readback.READBACK_TTL)

    print("\n  turn      %.1fs -> %.1fs   (%.1fx faster)"
          % (before_s, after_s, before_s / after_s if after_s else 0))
    print("  provider  %d calls -> %d calls  (%d saved by the cache)"
          % (before_c, after_c, before_c - after_c))
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
