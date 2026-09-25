"""Lane R: a transport that CANNOT write, and counts every request it makes.

Installed before the first provider call, not after it. HeyReach reads with
POST, so "refuse every POST" would refuse the reads as well; the rule here is
the module's own allowlist:

    GET   - always a read on this API, allowed
    POST  - allowed ONLY on `heyreach.READ_ROUTES_ALL`
    anything else, and any POST off that list, raises

That is the same allowlist `heyreach._read` enforces one layer up. Enforcing
it again at the transport means a call that bypasses `_read` - a helper, a
retry, a future edit - still cannot mutate.

Every call is counted by route so the volume can be REPORTED rather than
estimated.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.dirname(os.path.dirname(HERE))
if WORKTREE not in sys.path:
    sys.path.insert(0, WORKTREE)

from src import providers                      # noqa: E402
from src.providers import heyreach             # noqa: E402

CALLS = Counter()
REFUSED = []


class WriteRefused(SystemExit):
    pass


def _allowed(method, url):
    method = str(method).upper()
    if method == "GET":
        return True
    if method != "POST":
        return False
    path = str(url).split("?")[0]
    if path.startswith(heyreach.BASE):
        path = path[len(heyreach.BASE):]
    return path in heyreach.READ_ROUTES_ALL


def install(env_path=None):
    """Load production credentials by path and seal the transport."""
    if env_path:
        providers.load_env(env_path)
    original = providers.request

    def counted(method, url, headers=None, body=None, **kw):
        route = str(url).split("?")[0]
        if route.startswith(heyreach.BASE):
            route = route[len(heyreach.BASE):]
        if not _allowed(method, url):
            REFUSED.append((str(method).upper(), route))
            raise WriteRefused(
                "LANE R is reads-only: refusing %s %s" % (method, route))
        CALLS[route] += 1
        return original(method, url, headers, body, **kw)

    providers.request = counted
    heyreach.request = counted
    return counted


def total():
    return sum(CALLS.values())


def report():
    lines = ["provider requests made by this run: %d" % total()]
    for route, n in CALLS.most_common():
        lines.append("  %-42s %d" % (route, n))
    if REFUSED:
        lines.append("  REFUSED WRITES: %r" % (REFUSED,))
    return "\n".join(lines)


def selftest():
    """Prove the seal refuses a write BEFORE anything else runs.

    A guard installed and never exercised is a guard that agrees with you.
    This calls the transport directly with the real stop route and requires
    a refusal; if it returns instead, the run aborts.
    """
    try:
        providers.request("POST", heyreach.BASE + "/campaign/StopLeadInCampaign",
                          {}, {"campaignId": 0})
    except WriteRefused:
        pass
    else:
        raise SystemExit(
            "LANE R seal FAILED: a POST to /campaign/StopLeadInCampaign was "
            "not refused. Aborting before any provider call.")
    try:
        providers.request("POST", heyreach.BASE + "/campaign/AddLeadsToCampaignV2",
                          {}, {})
    except WriteRefused:
        pass
    else:
        raise SystemExit("LANE R seal FAILED: AddLeadsToCampaignV2 allowed.")
    if CALLS:
        raise SystemExit("LANE R seal FAILED: a refused write was counted.")
    return True
