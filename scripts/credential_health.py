#!/usr/bin/env python3
"""Which credentials are configured, and which actually authenticate.

    py -3 scripts/credential_health.py              names and configured-ness
    py -3 scripts/credential_health.py --verify     also calls each check()

READ-ONLY, and it NEVER prints a credential value. Only the name, whether it
is set, its length, and what the provider said.

## The mistake this exists to make impossible

On 2026-09-20 an audit - mine - reported "CONTACTOUT_KEY absent, the primary
enrichment provider is unauthenticated" and concluded that decision-maker
discovery was dead and cohort expansion impossible. That shaped a whole
funnel analysis and a recommendation to the operator.

**The variable is `CONTACTOUT_TOKEN`, and it was set the whole time.** The
provider had 36,679 credits and 117,419 searches remaining. The codebase was
never wrong: `src/config.py`, `src/providers/contactout.py`, `src/web/api.py`,
`src/web/security.py`, `tests/base.py` and `.env.example` all say
`CONTACTOUT_TOKEN`. The only wrong spelling in the repository was in the
hand-written audit script, which invented a plausible name instead of asking.

So this reads `config.VARIABLES` - the registry every other consumer already
reads - and cannot invent a name. A provider added there appears here for
free; a provider NOT there cannot be reported on at all, which is the honest
failure rather than a confident wrong one.

**A CONFIGURED CREDENTIAL IS NOT AN AUTHENTICATED ONE**, which is the other
half of the same lesson: presence of an environment variable proves nothing
about whether it works, whose account it belongs to, or whether it has quota.
`--verify` calls each provider's own `check()`, which the adapters already
implement against free status endpoints.

## The five states, kept distinct

    CREDENTIAL_NOT_CONFIGURED         the variable is unset or blank
    CREDENTIAL_CONFIGURED_UNVERIFIED  set, and nothing has asked the provider
    AUTHENTICATION_VERIFIED           the provider answered as this account
    AUTHENTICATION_FAILED             the provider rejected the credential
    PROVIDER_UNAVAILABLE              the provider could not be reached at all

The last two are separated deliberately. A network failure is not a bad key,
and treating them alike is how a provider outage gets diagnosed as a
credential problem at two in the morning.
"""
import argparse
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import config                                    # noqa: E402
from src.providers import load_env                        # noqa: E402

NOT_CONFIGURED = "CREDENTIAL_NOT_CONFIGURED"
UNVERIFIED = "CREDENTIAL_CONFIGURED_UNVERIFIED"
VERIFIED = "AUTHENTICATION_VERIFIED"
FAILED = "AUTHENTICATION_FAILED"
UNAVAILABLE = "PROVIDER_UNAVAILABLE"

# variable name -> the adapter module that OWNS it. The mapping is here and
# not in the provider modules because `config.VARIABLES` is the registry of
# NAMES and the adapters are the owners of BEHAVIOUR; this is the one place
# that needs both. A name absent from this map is still reported for
# configured-ness - it simply cannot be verified, and says so.
CHECKERS = {
    "CONTACTOUT_TOKEN": "contactout",
    "AIARK_KEY": "aiark",
    "REOON_KEY": "reoon",
    "BISON_KEY": "bison",
    "HEYREACH_KEY": "heyreach",
    "BLITZ_API_KEY": "blitz",
    "DELIVERABLE_KEY": "deliverable",
    "XAI_API_KEY": "xai",
    "ZAI_API_KEY": "glm",
    "GROQ_API_KEY": "groq",
    "OPENROUTER_API_KEY": "openrouter",
}


def credential_names():
    """Every provider credential the registry knows about, in its order.

    From `config.VARIABLES`, never from a list written here. That is the
    whole point: a hand-written list is what produced `CONTACTOUT_KEY`.
    """
    return [name for name, _cls, group, _why in config.VARIABLES
            if group == "providers"]


def state_of(name, verify=False):
    """The five-state classification for one credential name."""
    value = (os.environ.get(name) or "").strip()
    if not value:
        return NOT_CONFIGURED, {"length": 0}
    detail = {"length": len(value)}
    if not verify:
        return UNVERIFIED, detail
    module_name = CHECKERS.get(name)
    if not module_name:
        detail["why"] = "no adapter maps to this variable; cannot verify"
        return UNVERIFIED, detail
    started = time.time()
    try:
        module = __import__("src.providers." + module_name,
                            fromlist=[module_name])
        answer = module.check()
    except Exception as exc:
        detail["latency_ms"] = int((time.time() - started) * 1000)
        detail["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:160])
        # A transport failure is NOT a bad credential. Classifying them alike
        # is how an outage gets diagnosed as an auth problem.
        transport = ("HttpTimeout", "HttpTransportError", "URLError",
                     "TimeoutError", "ConnectionError")
        return (UNAVAILABLE if type(exc).__name__ in transport else FAILED,
                detail)
    detail["latency_ms"] = int((time.time() - started) * 1000)
    if isinstance(answer, dict):
        detail["status"] = answer.get("status")
        detail["note"] = str(answer.get("note") or "")[:200]
        if answer.get("ok"):
            return VERIFIED, detail
        if answer.get("status") is None:
            return UNAVAILABLE, detail
        return FAILED, detail
    return UNVERIFIED, detail


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify", action="store_true",
                        help="call each provider's free check() endpoint")
    args = parser.parse_args(argv)

    load_env(os.path.join(_ROOT, "config", ".env"))

    print("=" * 76)
    print("  CREDENTIAL HEALTH - names from config.VARIABLES, never guessed")
    print("=" * 76)
    worst = 0
    for name in credential_names():
        state, detail = state_of(name, verify=args.verify)
        bits = []
        if detail.get("length"):
            bits.append("len=%d" % detail["length"])
        if "latency_ms" in detail:
            bits.append("%dms" % detail["latency_ms"])
        if detail.get("note"):
            bits.append(detail["note"][:90])
        if detail.get("error"):
            bits.append(detail["error"][:90])
        print(f"  {name:20} {state:32} {' '.join(bits)}")
        if state in (FAILED,):
            worst = max(worst, 2)
        elif state in (UNAVAILABLE,):
            worst = max(worst, 1)
    print()
    print("  A CONFIGURED CREDENTIAL IS NOT AN AUTHENTICATED ONE.")
    if not args.verify:
        print("  Nothing above asked a provider. Re-run with --verify.")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
