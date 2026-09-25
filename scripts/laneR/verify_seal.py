"""Lane R: prove the read-only seal STOPS THE TRANSPORT, not just that it raises.

`readonly.selftest()` asserts that a write raises. That is necessary and it
is not sufficient: a guard that raises AFTER handing the request to the
transport would pass it while the write had already happened. So this asserts
the effect - the underlying transport is replaced by a spy, and the spy must
never be called for a write and must be called for a read.

It also proves the guard can FAIL, by checking the read routes are allowed.
A guard that refuses everything would pass a refusal test and be useless.

No credential and no network: the spy replaces the transport entirely.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

from src import providers                  # noqa: E402
from src.providers import heyreach         # noqa: E402

WRITES = ("/campaign/StopLeadInCampaign", "/campaign/AddLeadsToCampaignV2",
          "/campaign/AddLeadsToCampaign", "/list/CreateList",
          "/campaign/Create", "/campaign/Pause", "/campaign/Resume")
READS = ("/campaign/GetCampaignsForLead", "/lead/GetLead",
         "/li_account/GetAll", "/campaign/GetLeadsFromCampaign",
         "/stats/GetOverallStats", "/campaign/GetAll")


def main():
    calls = []

    def spy(method, url, headers=None, body=None, **kw):
        calls.append((str(method).upper(), url))
        return 200, {"items": [], "totalCount": 0}

    providers.request = spy
    heyreach.request = spy
    readonly.install()                     # no env: nothing here needs a key
    failures = []

    for route in WRITES:
        before = len(calls)
        try:
            providers.request("POST", heyreach.BASE + route, {}, {})
        except readonly.WriteRefused:
            pass
        else:
            failures.append("%s was ALLOWED" % route)
        if len(calls) != before:
            failures.append("%s REACHED THE TRANSPORT" % route)

    for route in READS:
        before = len(calls)
        try:
            providers.request("POST", heyreach.BASE + route, {}, {})
        except readonly.WriteRefused:
            failures.append("%s was refused - the guard refuses everything, "
                            "which is not a guard" % route)
        if len(calls) == before:
            failures.append("%s never reached the transport" % route)

    # A GET anywhere is a read on this API.
    before = len(calls)
    providers.request("GET", heyreach.BASE + "/campaign/GetById?x=1", {})
    if len(calls) == before:
        failures.append("a GET was blocked")

    # The counter must not credit a refused write.
    if any(r in readonly.CALLS for r in WRITES):
        failures.append("a refused write was counted as a request")

    print("write routes tested : %d" % len(WRITES))
    print("read routes tested  : %d" % len(READS))
    print("transport calls     : %d (reads only)" % len(calls))
    print("refusals recorded   : %d" % len(readonly.REFUSED))
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS: every write route was refused BEFORE the transport, every "
          "read route reached it, and no refused write was counted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
