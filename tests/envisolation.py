"""Every test module gets the environment it was handed back. Harness-level.

THE DEFECT, MEASURED 2026-09-23. A full run and a per-module standalone run
were taken at the same commit and diffed by name: 77 distinct failures under
full discovery, 75 standalone. The whole environment was snapshotted between
modules, and twelve modules left it changed:

    test_a_refusal_is_not_a_purchase          DELIVERABLE_AUTH -> 'header'
    test_a_settlement_...                     QUEUE -> a temp dir, then deleted
    test_an_active_campaign_..._topped_up     BISON_BASE, BISON_KEY
    test_claim_task                           GIT_AUTHOR_DATE, GIT_COMMITTER_DATE
    test_demo_mode                            SLACK_OPS_CHANNEL
    test_notify                               SLACK_OPS_CHANNEL -> cleared
    test_one_human_may_own_several_inboxes    QUEUE -> a temp dir, then deleted
    test_persistent_volume                    SLACK_OPS_CHANNEL
    test_replywatch                           OUT -> a temp dir, then deleted
    test_scale_generator                      QUEUE -> a temp dir, then deleted
    test_task240_arity_rule_moves_to_action   QUEUE -> a temp dir, then deleted
    test_xai_adapter                          XAI_API_KEY

Reproduced rather than inferred: `test_scale_generator` leaves `QUEUE` at its
own temp directory, and `test_slack_agent_cannot_act` then fails asserting the
agent writes only under `work\\` - while the guard it is testing is in perfect
health. It fails identically whether that directory still exists or not, so it
is the leaked PATH and not the deletion.

WHY THE FIX IS HERE AND NOT IN TWELVE MODULES. Fixing each module fixes the
twelve that were measured on one day. The class survives, because isolation a
module has to remember is isolation a module can forget - which is the
argument `tests/base.py` already makes for `ProviderTest`, in a comment, about
forty-two subclasses. This file makes the environment a module is handed the
environment the next module is handed, for every module, including ones
written after today.

WHY THE VARIABLE LIST IS NOT A LIST. The first version of this measurement
watched `QUEUE`, `OUT`, `QUEUE_BACKEND`, `QUEUE_JOURNAL`, `SHADOW_STRICT` and
`store.STATE_OVERRIDES` - the variables TASK-264's brief names. It found five
leaking modules and explained none of the three order-dependent failures,
because the leaks that mattered were in `DELIVERABLE_AUTH` and `BISON_KEY`,
which nobody had thought to name. A watch list is a list somebody has to
maintain. So the snapshot is `dict(os.environ)`, entire.

WHAT THIS DOES NOT DO. It does not restore between TESTS inside one module -
only between modules. Within a module the existing setUp/tearDown pairs are
the contract, and narrowing to per-test would change the behaviour of 522
modules to fix a cross-module problem. It also does not touch anything but
`os.environ`: a module that leaves a cached module, a monkeypatch or a shared
temp directory behind is NOT covered here, and
`test_no_test_leaves_the_environment_changed` says so out loud rather than
letting a green guard imply otherwise.
"""
import os
import unittest

#: Every module that left the environment changed, in the order they ran.
#: Appended to by `Isolated.run`, read by
#: `tests/test_no_test_leaves_the_environment_changed.py`.
#:
#: This is deliberately a RECORD rather than a silent repair. An auto-restore
#: with nothing watching it is a leak that stopped being visible, which is the
#: shape this register keeps naming: the repair would hold and the reason for
#: it would be forgotten, until something needed the environment to be honest.
LEAKS = []

#: The guard that reads `LEAKS`. Assembled last; see `wrap_discovered`.
GUARD_MODULE = "test_no_test_leaves_the_environment_changed"


def diff(before, after):
    """What changed between two environment snapshots.

    Returns a list of `(name, was, now)`, sorted, with `None` for absence.
    Absence and empty string are different: a variable popped is not a
    variable set to "".
    """
    out = []
    for name in sorted(set(before) | set(after)):
        was, now = before.get(name), after.get(name)
        if was != now:
            out.append((name, was, now))
    return out


def restore(snapshot):
    """Put the environment back exactly as `snapshot` had it.

    Set-and-unset individually rather than `os.environ.clear()` then update:
    clearing calls `unsetenv` for every variable in the process, including the
    hundreds this suite never touches, and a harness that rewrites the whole
    environment to fix five variables is a harness with its own blast radius.

    Written out rather than routed through `diff`: the first version passed
    `diff(current, snapshot)` and then restored the `was` field, which is the
    CURRENT value in that call - so it carefully set every variable back to
    what it already was. Its own three tests caught it immediately, which is
    the argument for the tests rather than for the cleverness.
    """
    current = dict(os.environ)
    for name in set(current) | set(snapshot):
        want = snapshot.get(name)
        if want is None:
            os.environ.pop(name, None)
        elif current.get(name) != want:
            os.environ[name] = want


class Isolated(unittest.TestSuite):
    """One module's tests, with the environment handed back afterwards.

    THE ORDERING THAT MAKES THIS CORRECT, and it was wrong in the first
    version. `unittest` DEFERS `tearDownClass` and `tearDownModule`: they do
    not run when a module's last test finishes, they run when the NEXT
    module's first test starts, from `TestSuite._handleModuleFixture`. So a
    naive wrapper compares its snapshot and restores while the module it just
    ran still has a class torn halfway down - and `tests/webbase.py`'s
    `tearDownClass`, which stops a live HTTP server and restores four
    variables, would then execute inside the NEXT module's window. Its
    restore would be recorded as that module's leak, and the server would be
    stopped one module late.

    Clearing `result._testRunEntered` makes this suite believe it is the top
    level, which is exactly true of it: `TestSuite.run` then finishes every
    pending class and module teardown before returning. The module behaves as
    it would if it had been run alone, which is the whole definition of
    isolation being asked for here.

    `_testRunEntered` is private. It has been in `unittest` since 3.2 and
    there is no public way to wrap a suite without it; the alternative is
    calling `_tearDownPreviousClass` and `_handleModuleTearDown` directly,
    which is three private names instead of one.
    """

    def __init__(self, tests, module):
        super().__init__(tests)
        self.module = module

    def run(self, result, debug=False):
        before = dict(os.environ)
        entered = getattr(result, "_testRunEntered", False)
        result._testRunEntered = False
        try:
            return super().run(result, debug)
        finally:
            # `finally`, not after the return: a module whose tests error out,
            # or whose setUpModule raises, is exactly the module most likely
            # to have left something set.
            result._testRunEntered = entered
            changed = diff(before, dict(os.environ))
            if changed:
                LEAKS.append({"module": self.module, "changed": changed})
            restore(before)


def wrap(suite_by_module):
    """Wrap each `(module, tests)` pair in an `Isolated` suite, in order."""
    out = unittest.TestSuite()
    for module, tests in suite_by_module:
        out.addTest(Isolated(tests, module))
    return out


def group_by_module(suite):
    """Every leaf test in `suite`, grouped into contiguous runs by module.

    Discovery order is preserved exactly: the groups come out in the order the
    modules were first seen, and tests stay in the order they were loaded.
    """
    order, groups = [], {}

    def walk(node):
        if hasattr(node, "__iter__"):
            for child in node:
                walk(child)
            return
        module = type(node).__module__ or "<unknown>"
        if module not in groups:
            groups[module] = []
            order.append(module)
        groups[module].append(node)

    walk(suite)
    return [(module, groups[module]) for module in order]


def wrap_discovered(suite):
    """Wrap an already-discovered suite so each module is isolated.

    THIS IS THE FUNCTION THE RUNNER MUST CALL, and the first version of this
    file did not have it. Isolation was installed as `load_tests` in
    `tests/__init__.py`, which `unittest` consults only when the tests package
    is discovered as a PACKAGE. `tests/offline.py` - the runner the baseline
    is measured with - calls `loader.discover("tests")` with no
    `top_level_dir`, so `tests` becomes the top level, its modules import as
    top-level names, and `load_tests` is never called.

    The harness was therefore inert in the runner that matters, while a test
    asserting `load_tests` wraps everything passed happily, because it called
    `load_tests` itself rather than the path the runner takes. Existence is
    not function; `tests/test_no_test_leaves_the_environment_changed.py` now
    asserts on `offline.build_suite()` instead.
    """
    groups = group_by_module(suite)

    # The guard reports which modules leaked and can only see the ones that
    # have already run, so it goes last - by construction, not by hoping its
    # filename sorts that way. Matched by suffix because discovery names it
    # `tests.test_no_...` as a package and `test_no_...` as a top level, and
    # this file is called from both.
    head = [g for g in groups if not g[0].endswith(GUARD_MODULE)]
    tail = [g for g in groups if g[0].endswith(GUARD_MODULE)]
    return wrap(head + tail)
