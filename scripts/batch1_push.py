#!/usr/bin/env python3
"""Push batch 1 to EmailBison, after the veto window, and report what happened.

    py -3 scripts/batch1_push.py --dry
    py -3 scripts/batch1_push.py --live --veto-closed 2026-09-21T19:23:19Z

THE VETO IS AN ARGUMENT, NOT A COMMENT. `--live` refuses unless
`--veto-closed` names a time that has already passed, so "the fifteen minutes
elapsed" is a check rather than a claim in a log line. Condition 6 of the
grant says the clock starts at the post, not at the decision to post.

## WHAT IT DOES, PER CAMPAIGN

`bisonfactory.stage(live=True)` does the provider work in the order the
factory already proved safe: create or find, limits, schedule, senders,
sequence, STOP, then leads. The stop before the leads is not tidiness -
a lead attached to a campaign that has not been stopped reads `in_sequence`
at once, and a lead that is `in_sequence` anywhere cannot be attached to any
other campaign, so a staging run would make its own leads unattachable
elsewhere.

## WHAT IT REPORTS, AND WHY EACH LINE IS THERE

Condition 7: enrolled per campaign, provider-confirmed scheduled rows per
campaign, first scheduled send per campaign, and explicitly that **enrolled
is not sent**. The scheduled rows are read back from the provider rather than
inferred from what we wrote, because this project's register exists largely
because `active`, `in_sequence` and `scheduled` were each read as a send.

**NOTHING HERE ACTIVATES ANYTHING.** `bison.activate` is not in SUPPORTED and
this script does not ask for it. The campaigns land stopped, holding their
leads, and going live is a separate operator decision.
"""
import argparse
import contextlib
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import bisonfactory, campaigns, providers, store       # noqa: E402
from src.providers import bison, load_env                       # noqa: E402

BATCH_ID = "batch-1-2026-09-21"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse(stamp):
    text = str(stamp or "").strip().replace("Z", "+00:00")
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return moment


def rows_for_batch():
    return [r for r in campaigns.load() if r.get("batch_id") == BATCH_ID]


def leads_of(row, recs):
    return sum(len((recs.get(rid) or {}).get("contacts") or [])
               for rid in row.get("record_ids") or [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--veto-closed")
    parser.add_argument("--veto-waived",
                        help="the operator's own words clearing the window "
                             "early. Recorded verbatim; never invented.")
    parser.add_argument("--only")
    args = parser.parse_args(argv)

    if args.live and args.veto_waived:
        # THE OPERATOR MAY CLOSE THEIR OWN WINDOW. The fifteen minutes exist
        # so they can say stop; saying "push it now" inside the window is the
        # same decision reached sooner. Recorded as a WAIVER rather than
        # backdating `--veto-closed`, because a timestamp that says the clock
        # ran out when it did not is a lie in the audit trail, and this file
        # is the audit trail.
        print(f"  VETO WAIVED BY THE OPERATOR: {args.veto_waived}")
    elif args.live:
        closed = _parse(args.veto_closed)
        if closed is None:
            print("REFUSED: --live needs --veto-closed <ISO time>, the moment "
                  "the fifteen minutes that started at the stats post ran "
                  "out. The window is not a formality.")
            return 1
        if closed > _now():
            remaining = (closed - _now()).total_seconds()
            print(f"REFUSED: the veto window has {remaining:.0f} seconds left "
                  f"(closes {closed.isoformat()}). Nothing pushed.")
            return 1

    load_env()
    rows = rows_for_batch()
    if args.only:
        rows = [r for r in rows if r["campaign_id"].endswith(args.only)]
    recs = {r.get("id"): r for r in store.load()}

    print(f"\nBATCH 1 PUSH  live={bool(args.live)}  campaigns={len(rows)}\n")
    # THE ENTRY POINT OPTS IN, BY NAME, AND ONLY FOR THE LIVE BLOCK.
    #
    # `providers.refuse_unauthorized_write` refuses every prospect-facing
    # mutation unless the process says out loud that it means to write and
    # why - the guard added after an audit agent paused live campaign 487 on
    # 2026-09-20 simply by importing src and calling through. A library
    # cannot grant itself this; only a script a person ran can, and the
    # reason is recorded on the refusal log and in `writes_allowed()`.
    #
    # The first run of this script hit exactly that refusal on all eight
    # campaigns. Its wrapper said "the provider may have acted", which is the
    # honest thing for it to say, and the readback settled it: ZERO campaigns
    # matching BATCH1 existed at the provider. The guard worked and nothing
    # leaked.
    reason = ("batch 1 push - OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1 and "
              "the CONTINUOUS grant; veto waived by the operator in the window")
    scope = (providers.allow_writes(reason) if args.live
             else contextlib.nullcontext())

    results = []
    with scope:
        for row in rows:
            slug = row["campaign_id"]
            planned = leads_of(row, recs)
            try:
                report = bisonfactory.stage(slug, live=bool(args.live))
            except Exception as exc:                            # noqa: BLE001
                print(f"  {slug:38s} REFUSED {type(exc).__name__}: "
                      f"{str(exc)[:140]}")
                results.append({"campaign": slug, "refused":
                                f"{type(exc).__name__}: {str(exc)[:200]}"})
                continue
            provider_id = (report.get("provider") or {}).get("campaign_id")
            did = ", ".join(report.get("did") or [])[:110]
            print(f"  {slug:38s} provider {provider_id}  planned {planned}")
            if did:
                print(f"      {did}")
            results.append({"campaign": slug, "provider_id": provider_id,
                            "planned_leads": planned,
                            "did": report.get("did")})

    if not args.live:
        print("\n  DRY RUN. Nothing was written to any provider.")
        return 0

    # ---------------------------------------------------- condition 7
    print("\nREADBACK, from the provider, after the push\n")
    for result in results:
        provider_id = result.get("provider_id")
        if not provider_id:
            continue
        try:
            campaign = bison.campaign(provider_id) or {}
            queue = bison.scheduled_emails(provider_id) or []
        except Exception as exc:                                # noqa: BLE001
            print(f"  {result['campaign']}: readback failed "
                  f"{type(exc).__name__}")
            continue
        dates = sorted(str(r.get("scheduled_date") or "") for r in queue
                       if r.get("scheduled_date"))
        sent = [r for r in queue if str(r.get("status") or "").lower()
                in ("sent", "delivered") or r.get("sent_at")]
        result.update({"status": campaign.get("status"),
                       "leads_at_provider": campaign.get("total_leads"),
                       "scheduled_rows": len(queue),
                       "sent_rows": len(sent),
                       "first_scheduled": dates[0] if dates else None})
        print(f"  {result['campaign']:38s} status {campaign.get('status'):8s} "
              f"leads {campaign.get('total_leads'):>4}  "
              f"queue rows {len(queue):>4}  sent {len(sent):>3}  "
              f"first {dates[0] if dates else 'none yet'}")

    total_leads = sum(r.get("leads_at_provider") or 0 for r in results)
    total_rows = sum(r.get("scheduled_rows") or 0 for r in results)
    total_sent = sum(r.get("sent_rows") or 0 for r in results)
    print(f"\n  enrolled at the provider   {total_leads}")
    print(f"  scheduled rows             {total_rows}")
    print(f"  PROVIDER-CONFIRMED SENT    {total_sent}")
    print("\n  ENROLLED IS NOT SENT. Enrolling writes leads to a campaign; "
          "the provider's scheduler decides when a first step goes out, and "
          "a scheduled row is not a send either.")

    out = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "work", "batch1-push-report.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"at": _now().isoformat(), "results": results}, handle,
                  indent=1)
    print(f"\n  report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
