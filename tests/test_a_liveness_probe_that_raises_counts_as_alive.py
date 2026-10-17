#!/usr/bin/env python3
"""A liveness probe that RAISES counts as ALIVE, never dead - the closing test.

THE GAP THIS CLOSES. canary/0150 traced the suitelock test corpus across every
ref that holds one: 100/100 traced tests, and ZERO executions of `_alive`'s
fail-closed branch - the `except Exception: return True` that answers ALIVE
when the process probe itself cannot answer (Windows seam: the `tasklist`
subprocess call raising). The gap was recorded, not closed, because both blobs
the question spans belong to other lanes. canary/0180 closes it on its own
branch, modifying no other lane's blob: the two blobs are pinned here as
byte-faithful fixture copies, and this test executes the branch on each.

THE CONTRACT UNDER TEST, quoted from `_alive`'s own docstring in both blobs:
"Is this PID running? Unknown counts as ALIVE, so a lock is never stolen on a
guess - waiting costs time, stealing costs a corrupted run." A probe that
raises is the definition of unknown. If this branch ever returns False (or
lets the exception escape), a live suite holder's lock becomes stealable the
moment one `tasklist` call fails - two suites, one evidence path, destroyed
names. That is the regression this test exists to make red.

THE TWO PINNED BLOBS (oids and line numbers in MANIFEST.json, verified against
the bytes by `test_the_fixture_blobs_are_the_pinned_blobs`, never retyped
into assertions by hand):

* the identity blob - `src/suitelock.py` as held by the lock-identity branch
  (0399 lineage). Fail-closed branch at its L373-L374.
* the master blob - `src/suitelock.py` at `origin/master`. Fail-closed branch
  at its L154-L155.

SHAPE OF THE PROOF. One raising fake, installed as the loaded blob module's
`subprocess` attribute, so the ONLY call `_alive` makes raises OSError - the
shape of a real probe failure (missing executable, spawn error). No real
process is ever queried: the fake raises before any spawn, and the test
asserts the fake fired exactly once, because a plant that lands nowhere reads
as a dead row. The pid is synthetic. Then `assertIs(result, True)`: identity,
not truthiness, because the contract is the singleton.

MUTATION TEETH (measured with the tracer harness beside this file, transcripts
under `arms/`): flipping the pinned blob copy's fail-closed `return True` to
`return False` - one line, byte-verified - makes exactly this test fail, by
name, on the `assertIs`, with the fake-fired witness still green and no other
guard firing first. Restoring the bytes makes it green again.

TRACER HARNESS. `tracer_arm.py` in the fixture directory proves line
execution: BEFORE arm (the pre-existing corpus without this test) shows 0
executions of the branch; AFTER arm (corpus plus this test) shows the except
line = 1 and the return line = 1, on both blobs. When the harness runs an
arm, it points `CANARY0180_BLOB_<LABEL>` at the package copy it is tracing
and restricts `CANARY0180_LABELS`; a hash pin is then the harness's job (it
verifies the package copy against MANIFEST before every arm), and this test's
own fixture-hash method guards the committed copies. With no environment
override - the way a reviewer runs it - this test loads the committed fixture
copies directly and checks their pins itself.

Standalone by construction: stdlib only, no `src` import, no lock file, no
network, no real process. Runs module-scoped
(`py -3 tests/test_a_liveness_probe_that_raises_counts_as_alive.py -v`)
or under discovery like every other file in `tests/`.
"""
import hashlib
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / \
    "suitelock_failclosed_canary0180"
LABELS = ("identity", "master")

#: Which labels this process is restricted to. The tracer harness sets this
#: when an arm exercises one blob; unset means both, which is reviewer mode.
_SELECTED = tuple(
    x.strip() for x in
    os.environ.get("CANARY0180_LABELS", ",".join(LABELS)).split(",")
    if x.strip()
)

#: The synthetic holder pid. Shaped like a Windows pid (a multiple of 4),
#: never looked up: the raising fake fires before any spawn, and the
#: fake-fired assertion witnesses that it did.
SYNTHETIC_PID = 424248


def _manifest():
    with open(FIXTURE_DIR / "MANIFEST.json", "rb") as handle:
        return json.loads(handle.read().decode("ascii"))


def _git_oid(data: bytes) -> str:
    """The git object id of these bytes: sha1 of header + content."""
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _blob_path(label: str) -> Path:
    override = os.environ.get("CANARY0180_BLOB_" + label.upper())
    if override:
        return Path(override)
    return FIXTURE_DIR / _manifest()["labels"][label]["file"]


def _load_suitelock(label: str):
    """The pinned blob as a fresh module, executed from its bytes every call.

    Fresh module object each time (never a sys.modules hit), so a mutated
    file on disk is what this loads - the property the mutation arm depends
    on. The caller's harness sweeps bytecode caches around every write.
    """
    path = _blob_path(label)
    name = "_canary0180_suitelock_" + label
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _RaisingRun:
    """The one-line raising fake: stands in for the blob module's
    `subprocess` and makes the ONE call `_alive` performs raise."""

    def __init__(self):
        self.calls = 0

    def run(self, *args, **kwargs):
        self.calls += 1
        raise OSError(
            "synthetic probe failure (canary/0180 fixture): "
            "no real process was queried")


class ALivenessProbeThatRaisesCountsAsAlive(unittest.TestCase):
    """Unknown counts as ALIVE, on both pinned blobs."""

    def test_the_fixture_blobs_are_the_pinned_blobs(self):
        """Provenance guard, separate from behaviour so its red can never
        mask or replace the fail-closed assertion's red."""
        manifest = _manifest()
        for label in LABELS:
            entry = manifest["labels"][label]
            data = (FIXTURE_DIR / entry["file"]).read_bytes()
            self.assertEqual(
                _git_oid(data), entry["oid"],
                f"the {label} fixture is not the pinned blob")
            self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(
                hashlib.sha256(data).hexdigest(), entry["sha256"])
            lines = data.split(b"\n")
            exc_line, ret_line = entry["target_lines"]
            self.assertIn(
                b"except Exception:", lines[exc_line - 1],
                f"{label}: the except line moved out from under the pin")
            self.assertEqual(
                lines[ret_line - 1].strip(), b"return True",
                f"{label}: the fail-closed return moved out from under "
                f"the pin")

    @unittest.skipUnless(
        os.name == "nt",
        "the subprocess seam under test is the Windows tasklist branch; "
        "the POSIX fail-closed path is a different except")
    @unittest.skipUnless("identity" in _SELECTED,
                         "restricted by CANARY0180_LABELS")
    def test_a_probe_that_raises_counts_as_alive_on_the_identity_blob(self):
        self._failclosed_is_alive("identity")

    @unittest.skipUnless(
        os.name == "nt",
        "the subprocess seam under test is the Windows tasklist branch; "
        "the POSIX fail-closed path is a different except")
    @unittest.skipUnless("master" in _SELECTED,
                         "restricted by CANARY0180_LABELS")
    def test_a_probe_that_raises_counts_as_alive_on_the_master_blob(self):
        self._failclosed_is_alive("master")

    def _failclosed_is_alive(self, label):
        module = _load_suitelock(label)
        probe = _RaisingRun()
        original = module.subprocess
        module.subprocess = probe                    # the one-line patch
        try:
            result = module._alive(SYNTHETIC_PID)
        finally:
            module.subprocess = original
        self.assertEqual(
            probe.calls, 1,
            "the raising fake never fired: _alive did not reach its "
            "subprocess call, so this test observed nothing")
        self.assertIs(
            result, True,
            "fail-closed contract broken: a liveness probe that raises "
            "must answer ALIVE (True), never dead - a lock is never "
            "stolen on a guess - but the %s blob's _alive returned %r"
            % (label, result))


if __name__ == "__main__":
    unittest.main()
