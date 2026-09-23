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


# --------------------------------------------------------------------------
# EVERY MODULE IS HANDED THE ENVIRONMENT THE LAST ONE WAS HANDED.
#
# `load_tests` is the documented hook for assembling a package's suite, and
# assembling it here is what lets every module be wrapped without editing 522
# modules. See `tests/envisolation.py` for the measurement that produced this
# and for what it deliberately does not cover.
#
# The modules are loaded BY NAME rather than by re-running `loader.discover`:
# discover would re-enter this function, and a recursion guard that returns
# early would silently assemble an EMPTY suite. A suite that runs no tests and
# reports success is the failure this repository has shipped twice, and it is
# not being introduced by the file that exists to stop things being dishonest.
#
# THIS HOOK IS NOT THE MAIN PATH, and believing it was cost a whole
# measurement. `unittest` consults `load_tests` only when `tests` is
# discovered as a PACKAGE - `python -m unittest discover -t . -s tests`.
# `tests/offline.py`, which is the runner the baseline is measured with,
# calls `loader.discover("tests")` with no `top_level_dir`, making `tests`
# itself the top level: its modules import as top-level names and this
# function is never called. `tests/offline.py:build_suite` does the wrapping
# for that path, and both delegate to `envisolation.wrap_discovered` so there
# is one implementation rather than two that can disagree.

_GUARD_MODULE = "tests.test_no_test_leaves_the_environment_changed"


def load_tests(loader, standard_tests, pattern):
    import fnmatch
    import unittest as _unittest

    from . import envisolation

    here = os.path.dirname(os.path.abspath(__file__))
    match = pattern or "test*.py"
    names = sorted(fn[:-3] for fn in os.listdir(here)
                   if fn.endswith(".py") and fnmatch.fnmatch(fn, match))

    # The guard runs LAST, by construction rather than by hoping its filename
    # sorts that way: it reports which modules leaked, and it can only see the
    # ones that have already run.
    ordered = [n for n in names if "tests." + n != _GUARD_MODULE]
    if any("tests." + n == _GUARD_MODULE for n in names):
        ordered.append(_GUARD_MODULE.split(".", 1)[1])

    pairs = []
    for name in ordered:
        dotted = "tests." + name
        try:
            pairs.append((dotted, loader.loadTestsFromName(dotted)))
        except Exception:                                       # noqa: BLE001
            # A module that cannot even be imported is a real failure and must
            # not be swallowed. `loadTestsFromName` builds a _FailedTest for
            # that case; this branch is for the loader itself raising.
            pairs.append((dotted, loader.suiteClass(
                [_unittest.loader._make_failed_import_test(
                    dotted, loader.suiteClass)])))

    suite = envisolation.wrap(pairs)
    if standard_tests.countTestCases():
        suite.addTest(standard_tests)
    return suite
