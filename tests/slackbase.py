"""Shared setup for the Slack agent's tests: isolate the state first.

Every test that drives a real turn reads the knowledge pack, and a stale
pack is REBUILT AND WRITTEN. Since the agent's writers went behind
`store.refuse_production_write`, a test that has not isolated the store gets
a refusal rather than a quiet write into the developer's real `work/` - and
several of them had not isolated it.

They passed anyway, for a while, and that is the part worth writing down.
A full-suite run has every module's environment changes leaking into the
next, so a test file that isolates nothing passes when it runs after one
that does. `tests.test_slack_agent_numbers` was green in a 415-test run and
failed on its own, which is the same class of mistake as a mutation run
against a red suite: the result was real, it just was not about the thing
being measured.

`store.use_directory` is the canonical move-everything helper - it owns the
file names, which is why `test_invariants` fails any other module that
spells one out - so this wraps that rather than listing overrides again.
"""
import os
import shutil
import tempfile

from src import store


class IsolatedState:
    """Mixin. Points every state file at a throwaway directory."""

    #: Set by the class that uses this, before `isolate` is called.
    ISOLATE_PREFIX = "rga-slack-"

    def isolate(self):
        """Call FIRST in setUp. Returns the directory."""
        self._isolated = tempfile.mkdtemp(prefix=self.ISOLATE_PREFIX)
        self._isolated_env = {key: os.environ.get(key)
                              for key in ("QUEUE", "OUT", "CLIENTS_DIR")}
        for override in store.STATE_OVERRIDES:
            self._isolated_env[override] = os.environ.get(override)
        store.use_directory(self._isolated)
        os.environ["OUT"] = os.path.join(self._isolated, "out")
        # The pack, the thread memory and the request journal follow the
        # queue, so `use_directory` has already moved them. Asserted rather
        # than assumed, because a state file that does not move is the one
        # that writes into the real directory.
        from src import slackknowledge
        assert slackknowledge.cache_path().startswith(self._isolated), \
            "the knowledge pack did not move with the state directory"
        return self._isolated

    def restore(self):
        """Call LAST in tearDown."""
        for key, value in getattr(self, "_isolated_env", {}).items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(getattr(self, "_isolated", "") or "", ignore_errors=True)
