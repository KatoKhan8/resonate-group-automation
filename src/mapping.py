#!/usr/bin/env python3
"""Does the external campaign this campaign points at actually exist, and is it
the right one?

An internal campaign carries a `bison_campaign_id` and a `heyreach_campaign_id`.
Both are typed in by a human, and a typo in either is not a small mistake: it
sends a client's sequence into another client's campaign. The id is a small
integer, so a wrong one is usually a *valid* one belonging to someone else.

So mapping is validated rather than trusted, and validation is read-only:

  EmailBison   GET  /api/campaigns          -> {"data": [...]}
  HeyReach     POST /campaign/GetAll        -> {"items": [...], "totalCount"}

Both are confirmed live. Neither creates anything, and there is no code here
that could: creating an external campaign is not implemented, on purpose.

Three answers, never two:

  ok        the id exists and looks like ours
  mismatch  the id exists and belongs to something else - refuse loudly
  unknown   we could not check, because the provider was unreachable. Not a
            pass. An unreachable provider is a reason to wait, not to launch.

  python -m src.mapping validate <campaign-id>
  python -m src.mapping list --provider heyreach
"""
import argparse
import sys

from . import campaigns, events, observability, store
from .providers import ProviderError, bison, heyreach

OK = "ok"
MISMATCH = "mismatch"
MISSING = "missing"
UNKNOWN = "unknown"
UNMAPPED = "unmapped"


def _result(state, provider, detail, external_id=None, name=None):
    return {"state": state, "provider": provider, "detail": detail,
            "external_id": external_id, "name": name,
            "ok": state == OK}


# ---------------------------------------------------------------- EmailBison

def bison_campaigns(fetch=None):
    """Every campaign this key can see. Read-only: GET /api/campaigns."""
    if fetch is not None:
        return fetch()
    from .providers import request
    status, data = request("GET", f"{bison.base()}/campaigns", bison.headers())
    if not (200 <= int(status or 0) < 300):
        raise ProviderError(f"emailbison campaigns: {status}")
    rows = (data or {}).get("data") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def check_bison(campaign_id, expected_name=None, fetch=None):
    """Is this EmailBison campaign real, and plausibly ours?"""
    if not campaign_id:
        return _result(UNMAPPED, "emailbison", "no bison_campaign_id is set")
    try:
        rows = bison_campaigns(fetch)
    except Exception as e:            # unreachable is not a pass
        return _result(UNKNOWN, "emailbison",
                       f"could not reach EmailBison to check: {type(e).__name__}",
                       campaign_id)
    for row in rows:
        if str(row.get("id")) == str(campaign_id):
            name = row.get("name")
            if expected_name and name and expected_name.lower() not in str(name).lower():
                return _result(MISMATCH, "emailbison",
                               f"campaign {campaign_id} exists but is named "
                               f"{name!r}, which does not look like "
                               f"{expected_name!r}", campaign_id, name)
            return _result(OK, "emailbison",
                           f"campaign {campaign_id} exists" +
                           (f" ({name})" if name else ""), campaign_id, name)
    return _result(MISSING, "emailbison",
                   f"no campaign {campaign_id} is visible to this key. Either "
                   "the id is wrong or the key belongs to another workspace",
                   campaign_id)


# ------------------------------------------------------------------ HeyReach

def check_heyreach(campaign_id, expected_accounts=None, fetch=None):
    """Is this HeyReach campaign real, and does it use the accounts we expect?

    `campaignAccountIds` is the mapping that matters: a campaign wired to
    somebody else's LinkedIn account would send from the wrong person.
    """
    if not campaign_id:
        return _result(UNMAPPED, "heyreach", "no heyreach_campaign_id is set")
    fetch = fetch or heyreach.campaign_by_id
    try:
        found = fetch(campaign_id)
    except Exception as e:
        return _result(UNKNOWN, "heyreach",
                       f"could not reach HeyReach to check: {type(e).__name__}",
                       campaign_id)
    if not found:
        return _result(MISSING, "heyreach",
                       f"no campaign {campaign_id} is visible to this key",
                       campaign_id)

    name = found.get("name")
    accounts = [str(a) for a in (found.get("campaignAccountIds") or [])]
    if expected_accounts:
        expected = {str(a) for a in expected_accounts}
        if accounts and not (expected & set(accounts)):
            return _result(MISMATCH, "heyreach",
                           f"campaign {campaign_id} sends from account(s) "
                           f"{', '.join(sorted(accounts))}, none of which is "
                           f"one of ours ({', '.join(sorted(expected))})",
                           campaign_id, name)
    status = str(found.get("status") or "")
    return _result(OK, "heyreach",
                   f"campaign {campaign_id} exists ({name}, {status}), "
                   f"accounts: {', '.join(accounts) or 'none listed'}",
                   campaign_id, name)


# ------------------------------------------------------------------ both

def validate(campaign, live=False, bison_fetch=None, heyreach_fetch=None,
             expected_accounts=None):
    """Check both mappings. Dry by default: reading is safe, surprising is not."""
    if not live:
        return {"live": False, "ok": None,
                "checks": [
                    _result(UNKNOWN, "emailbison",
                            "dry run: not checked", campaign.get("bison_campaign_id")),
                    _result(UNKNOWN, "heyreach",
                            "dry run: not checked", campaign.get("heyreach_campaign_id")),
                ],
                "why": "dry run: no provider was contacted"}

    checks = [
        check_bison(campaign.get("bison_campaign_id"),
                    expected_name=campaign.get("client"), fetch=bison_fetch),
        check_heyreach(campaign.get("heyreach_campaign_id"),
                       expected_accounts=expected_accounts, fetch=heyreach_fetch),
    ]
    # UNMAPPED is not a failure here: whether a channel needs a mapping is the
    # launch checklist's question, and it already asks it.
    bad = [c for c in checks if c["state"] in (MISMATCH, MISSING)]
    unknown = [c for c in checks if c["state"] == UNKNOWN]
    ok = not bad and not unknown
    return {"live": True, "ok": ok, "checks": checks,
            "blocked_by": [c["provider"] for c in bad],
            "unverified": [c["provider"] for c in unknown]}


def apply(campaign, result):
    """Record what validation found on the campaign itself."""
    campaign["mapping_checked"] = {
        "at": store.now(),
        "ok": result.get("ok"),
        "checks": [{k: v for k, v in c.items() if k != "name"}
                   for c in result.get("checks") or []],
    }
    name = (events.CAMPAIGN_MAPPING_VALIDATED if result.get("ok")
            else events.CAMPAIGN_MAPPING_FAILED)
    observability.count(name,
                        campaign_id=campaign.get("campaign_id"),
                        detail="; ".join(c["detail"]
                                         for c in result.get("checks") or []))
    from . import orchestrator
    orchestrator._note(campaign, name, ok=bool(result.get("ok")))
    campaigns.log(campaign, "mapping",
                  "validated" if result.get("ok") else "validation failed")
    return campaign


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.mapping")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("campaign_id")
    v.add_argument("--live", action="store_true",
                   help="actually look the campaigns up. Read-only")
    listing = sub.add_parser("list")
    listing.add_argument("--provider", choices=("emailbison", "heyreach"),
                         required=True)
    a = p.parse_args(argv)

    if a.cmd == "list":
        try:
            if a.provider == "emailbison":
                rows = bison_campaigns()
                for row in rows:
                    print(f"  {str(row.get('id')):<10} {row.get('name')}")
            else:
                items, total = heyreach.campaigns(limit=50)
                for row in items:
                    accounts = ", ".join(str(x) for x in
                                         row.get("campaignAccountIds") or [])
                    print(f"  {str(row.get('id')):<10} {str(row.get('status')):<12} "
                          f"{row.get('name')}  accounts=[{accounts}]")
                print(f"  ({total} total)")
        except ProviderError as e:
            print(f"REFUSED: {e}")
            return 2
        print("\nRead-only listing. Nothing was created or changed.")
        return 0

    try:
        campaign = campaigns.require(a.campaign_id)
    except campaigns.NotFound as e:
        print(f"REFUSED: {e}")
        return 2

    result = validate(campaign, live=a.live)
    print(f"campaign {a.campaign_id} external mapping "
          f"({'live' if result['live'] else 'DRY RUN'})")
    for check in result["checks"]:
        mark = {OK: "ok   ", MISMATCH: "WRONG", MISSING: "GONE ",
                UNKNOWN: "?    ", UNMAPPED: "-    "}.get(check["state"], "?    ")
        print(f"  {mark} {check['provider']:<12} {check['detail']}")
    if result["live"]:
        print("\n" + ("mapping is valid" if result["ok"] else
                      "mapping is NOT valid: " +
                      ", ".join(result["blocked_by"] + result["unverified"])))
    else:
        print(f"\n{result['why']}")
    return 0 if result.get("ok") is not False else 1


if __name__ == "__main__":
    sys.exit(main())
