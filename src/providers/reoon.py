#!/usr/bin/env python3
"""Reoon deep verification. BUILD-SPEC section 5.3.

GET https://emailverifier.reoon.com/api/v1/verify?email=&key=<REOON_KEY>&mode=power

Run only on an `accept_all` verdict: catch-all domains lie both ways, and one
verifier is never enough on a catch-all (section 9, trap 2). Only
`is_safe_to_send: true` clears an address.

Health check spends nothing by default. It confirms the key is configured and
the module is ready, and makes no request. A real verification costs a credit,
so it sits behind an explicit flag:

  python -m src.providers.reoon --check            configuration only, free
  python -m src.providers.reoon --check --live     one real verify, costs 1 credit
"""
import argparse

from . import MissingKey, ProviderError, key, ok, query, request, result, failed

BASE = "https://emailverifier.reoon.com/api/v1"

FIELDS = ("is_catch_all", "is_deliverable", "is_safe_to_send", "mx_records",
          "overall_score", "status")

LIVE_CHECK_ADDRESS = "test@example.com"


def verify_url(email, mode="power"):
    return query(f"{BASE}/verify", {"email": email, "key": key("REOON_KEY"), "mode": mode})


def verify(email, mode="power"):
    """One address, power mode. Costs a Reoon credit. Returns six fields."""
    status, data = request("GET", verify_url(email, mode))
    if not ok(status):
        raise ProviderError(f"reoon verify: {status}")
    data = data or {}
    return {f: data.get(f) for f in FIELDS}


def is_clear(reoon):
    """Only is_safe_to_send true clears an address. Section 5.3."""
    return bool(reoon) and reoon.get("is_safe_to_send") is True


def check(live=False):
    """Default spends nothing: configuration readiness only, no request."""
    if not live:
        try:
            key("REOON_KEY")
        except MissingKey as e:
            return failed("Reoon", e)
        # Reoon's only endpoint verifies an address, and that costs a credit.
        # Configuration readiness is as far as a health check should go.
        return {"provider": "Reoon", "ok": None, "status": None, "skipped": True,
                "note": "key configured, no call made: the only endpoint costs "
                        "a credit (--live-reoon to spend one)"}
    try:
        status, data = request("GET", verify_url(LIVE_CHECK_ADDRESS, "quick"))
        return result("Reoon", status, str(data))
    except ProviderError as e:
        return failed("Reoon", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.reoon")
    p.add_argument("--check", action="store_true")
    p.add_argument("--live", action="store_true",
                   help="spend one verifier credit on a real check")
    a = p.parse_args(argv)
    r = check(live=a.live)
    print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['provider']:<12} "
          f"{r['status'] if r['status'] is not None else '-'}  {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
