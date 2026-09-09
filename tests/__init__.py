"""A credential firewall for the whole suite, installed at import.

WHY THIS FILE EXISTS AT ALL.

`tests/base.py` promises, in its own comment, that "no key may reach a provider
from the developer's own environment". That promise held inside `ProviderTest`,
which pops every key variable and points `providers.ENV_FILE` at a file that
does not exist. It did not hold anywhere else, and most test modules here are
plain `unittest.TestCase`.

Measured on a full run: **1,289 reads of the real `config/.env`**. The path is
short and entirely innocent-looking - a plain-`TestCase` module stubs the
transport, calls something that builds provider headers, `key()` calls
`load_env()`, and `os.environ.setdefault` then makes the operator's real
credential permanent for every test that runs afterwards. Because
`addCleanup(providers.reset_transport)` restores the real urllib transport at
the end of such a module, a later test that reaches `providers.request()` would
do so with real credentials present and no `urlopen` tripwire armed.

So the firewall is installed once, here, at package import, before any test
module is loaded:

  * `providers.ENV_FILE` points at a path that cannot exist, so `load_env()` is
    a no-op no matter who calls it or how deep in the stack;
  * every credential variable is removed from `os.environ`.

`ProviderTest` still does its own per-test scrubbing and still sets placeholder
values - that is not redundant. This is the floor for the tests that never
inherit it, and it makes the failure mode a loud `MissingKey` rather than a
quiet live call.

It deliberately does NOT stub the transport. A test that reaches the wire should
fail on a missing key, which names the real problem, rather than on a refused
socket, which names a symptom.
"""
import os

from src import providers

# A path that cannot exist on any platform this runs on. Named rather than
# empty so a traceback mentioning it explains itself.
NO_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fixtures", "no-such-suite-wide.env")

# Every credential the providers read, plus the two that are configuration
# rather than credentials but are read from the same file and change behaviour:
# a workspace pin decides which estate an assertion is about, and Deliverable's
# result shape decides whether that provider will spend at all.
SUITE_SCRUBBED = (
    "CONTACTOUT_TOKEN", "BLITZ_API_KEY", "AIARK_KEY", "REOON_KEY",
    "DELIVERABLE_KEY", "BISON_KEY", "BISON_BASE", "HEYREACH_KEY",
    "APIFY_TOKEN", "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_LIVE",
    "BISON_WORKSPACE_ID", "DELIVERABLE_RESULT_SHAPE",
)


def install():
    """Point env loading at nothing and clear every credential. Idempotent."""
    providers.ENV_FILE = NO_ENV_FILE
    removed = [name for name in SUITE_SCRUBBED
               if os.environ.pop(name, None) is not None]
    return {"env_file": NO_ENV_FILE, "cleared": removed}


INSTALLED = install()
