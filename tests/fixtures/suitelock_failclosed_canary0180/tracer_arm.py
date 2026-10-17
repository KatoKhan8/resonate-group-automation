#!/usr/bin/env python3
"""canary/0180 line-tracer harness for the fail-closed `_alive` branch.

Runs five arms per label (identity, master) against a hermetic package whose
`src/suitelock.py` is a byte-faithful copy of the pinned blob, and answers the
one question: does the closing test
`tests/test_a_liveness_probe_that_raises_counts_as_alive.py` execute the
fail-closed `except Exception: return True` branch, and does it fail naming
itself when the branch is mutated?

ARMS, in order (order is load-bearing: the AFTER arm is compared by NAME SET
against the BEFORE arm of the same label):

  calibration  the closing behaviour method alone, under the line tracer.
               This is canary/0150's passing control re-run FIRST: fake-raise
               must give except-line = 1 and return-line = 1. An arm whose
               instrument cannot print 1/1 proves nothing else.
  before       the pre-existing corpus WITHOUT the closing test (its module is
               never imported - asserted, not assumed). Reproduces 0150's zero:
               both target lines = 0, while the witness table shows the corpus
               really did execute _alive's body (so the zero is a branch never
               taken, not a function never run).
  after        corpus PLUS the closing test: both target lines = exactly 1,
               and the red/green name set is UNCHANGED versus before (set
               equality, never counts).
  mutation     the pinned copy's fail-closed `return True` is flipped to
               `return False` - one line, byte-verified, whole-file line diff
               printed - and the behaviour method must FAIL, naming itself,
               on the fail-closed assertion, with the fake-fired witness still
               green (no other guard fired first) and 0 errors.
  restore      the pinned bytes are written back (oid re-verified), the
               behaviour method is green again and 1/1 again: the red was the
               flip and nothing else.

DISCIPLINE. Bytecode caches are swept under the package after every .py write
(direction "write": pkg build, mutation) and after every revert (direction
"revert": restore), and before every arm run ("pre-arm"), with the removed
count printed - Python invalidates .pyc on mtime AND size with whole-second
mtime granularity, so a same-second revert could otherwise import stale bytes.
Every git call clears GIT_CONFIG_* from the child environment and surfaces
stderr instead of swallowing it. Transcripts are scrubbed of machine paths
(<PKG>, <TMP>, <SOURCE_ROOT>, <REPO>) and are pure ASCII, LF-only.

Exit code 0 iff every arm expectation passed AND the summary prints
"ARMS: ALL-PASS". An exit code is not a result; the transcripts are.

Usage (from a checkout of the task branch, or from the stage tree):
  py -3 tracer_arm.py --repo <git checkout with the pinned objects>
"""
import argparse
import collections
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = FIXTURE_DIR.parents[2]
MY_TEST_NAME = "test_a_liveness_probe_that_raises_counts_as_alive"
MY_TEST_REL = Path("tests") / (MY_TEST_NAME + ".py")
MY_CLASS = "ALivenessProbeThatRaisesCountsAsAlive"
CLOSING_PHRASE = "fail-closed contract broken"
NEVER_FIRED_PHRASE = "never fired"
LABELS = ("identity", "master")
ARMS = ("calibration", "before", "after", "mutation", "restore")
CORPUS_COUNT_RECORDED_BY_0170 = 26  # collateral tests, for comparison only


def log(*args):
    print(*args, flush=True)


def git_oid(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(repo, *args):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_CONFIG_"):
            env.pop(key)
    proc = subprocess.run(["git"] + list(args), cwd=str(repo), env=env,
                          capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"git {args} FAILED rc={proc.returncode} "
            f"stderr={proc.stderr!r}")
    if proc.stderr:
        log("  git %s stderr surfaced: %s"
            % (args[0], proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


class Sweeper:
    """pyc discipline with printed counts, per direction."""

    def __init__(self):
        self.totals = collections.Counter()

    def sweep(self, root, direction, note, emit):
        dirs = 0
        for candidate in sorted(Path(root).rglob("__pycache__")):
            if candidate.is_dir():
                shutil.rmtree(candidate)
                dirs += 1
        loose = 0
        for candidate in sorted(Path(root).rglob("*.pyc")):
            candidate.unlink()
            loose += 1
        self.totals[direction] += dirs
        emit("pyc sweep [%s] %s: removed %d __pycache__ dir(s), %d loose .pyc"
             % (direction, note, dirs, loose))


class LineTracer:
    """Counts 'line' events for exactly one file, by absolute normcase path."""

    def __init__(self, target_path):
        self.target = os.path.normcase(os.path.abspath(str(target_path)))
        self.counts = collections.Counter()
        self._cache = {}

    def _is_target(self, filename):
        hit = self._cache.get(filename)
        if hit is None:
            hit = os.path.normcase(os.path.abspath(filename)) == self.target
            self._cache[filename] = hit
        return hit

    def _trace(self, frame, event, arg):
        if self._is_target(frame.f_code.co_filename):
            if event == "line":
                self.counts[frame.f_lineno] += 1
            return self._trace
        return None

    def __enter__(self):
        sys.settrace(self._trace)
        return self

    def __exit__(self, *exc_info):
        sys.settrace(None)
        return False


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test.id())


def load_module_from_path(path, unique_name):
    spec = importlib.util.spec_from_file_location(unique_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def purge_modules():
    """Drop every name a previous arm bound, so the next arm re-imports."""
    stems = ("src", "_canary0180_suitelock_",
             "test_a_holder_that_dies_mid_check_is_stale_not_held",
             "test_the_suite_lock_holder_is_a_process_not_a_number",
             MY_TEST_NAME)
    for name in list(sys.modules):
        if name == stems[0] or name.startswith("src."):
            del sys.modules[name]
        elif any(name.startswith(stem) for stem in stems[1:]):
            del sys.modules[name]


def clean_sys_path(keep_root):
    """Remove every canary0180 package root except the current arm's."""
    keep = os.path.normcase(os.path.abspath(str(keep_root)))
    for entry in list(sys.path):
        absolute = os.path.normcase(os.path.abspath(entry or os.getcwd()))
        if absolute != keep and "canary0180-" in absolute:
            sys.path.remove(entry)


def build_pkg(label, manifest, pkg, repo, sweeper, emit):
    entry = manifest["labels"][label]
    (pkg / "src").mkdir(parents=True, exist_ok=True)
    (pkg / "src" / "__init__.py").write_bytes(b"")
    data = git(repo, "cat-file", "blob", entry["oid"])
    if git_oid(data) != entry["oid"]:
        raise SystemExit("pkg blob extraction does not match the pin")
    (pkg / "src" / "suitelock.py").write_bytes(data)
    tests = pkg / "tests"
    tests.mkdir(exist_ok=True)
    for corpus in manifest["corpus"]:
        body = git(repo, "cat-file", "blob", corpus["oid"])
        if git_oid(body) != corpus["oid"]:
            raise SystemExit(f"corpus extraction mismatch: {corpus['name']}")
        (tests / corpus["name"]).write_bytes(body)
    mine = (SOURCE_ROOT / MY_TEST_REL).read_bytes()
    (tests / (MY_TEST_NAME + ".py")).write_bytes(mine)
    mirror = tests / "fixtures" / "suitelock_failclosed_canary0180"
    mirror.mkdir(parents=True, exist_ok=True)
    for name in ("suitelock_identity.py", "suitelock_master.py",
                 "MANIFEST.json"):
        shutil.copyfile(FIXTURE_DIR / name, mirror / name)
    sweeper.sweep(pkg, "write", "after pkg build", emit)
    return data


def census(label, manifest, pkg, emit):
    """Count corpus test cases WITHOUT the tracer armed (import noise stays
    out of every arm), then purge so each arm re-imports cleanly."""
    loader = unittest.defaultTestLoader
    counts = {}
    for corpus in manifest["corpus"]:
        module = load_module_from_path(
            pkg / "tests" / corpus["name"],
            corpus["name"][:-3] + "__census__" + label)
        counts[corpus["name"]] = loader.loadTestsFromModule(
            module).countTestCases()
    purge_modules()
    clean_sys_path(pkg)
    for name, count in counts.items():
        emit(f"census: {name} -> {count} test(s)")
    total = sum(counts.values())
    emit(f"census: corpus total = {total} "
         f"(0170 recorded the collateral at "
         f"{CORPUS_COUNT_RECORDED_BY_0170})")
    return total


def flip_target_line(pinned_bytes, label, manifest, src_path, sweeper, emit):
    """Mutate ONLY the fail-closed return; prove the diff is one line."""
    target_line = manifest["labels"][label]["target_lines"][1]
    lines = pinned_bytes.split(b"\n")
    old = lines[target_line - 1]
    if old.strip() != b"return True":
        raise SystemExit(f"mutation target is not 'return True': {old!r}")
    indent = old[:len(old) - len(old.lstrip())]
    lines[target_line - 1] = indent + b"return False"
    mutated = b"\n".join(lines)
    original_lines = pinned_bytes.split(b"\n")
    mutated_lines = mutated.split(b"\n")
    differing = [i + 1 for i, (a, b) in
                 enumerate(zip(original_lines, mutated_lines)) if a != b]
    if differing != [target_line] or \
            len(original_lines) != len(mutated_lines):
        raise SystemExit(f"mutation touched more than one line: {differing}")
    src_path.write_bytes(mutated)
    sweeper.sweep(src_path.parent.parent, "write",
                  "after mutation write", emit)
    emit("mutation: L%d  before: %r" % (target_line, old.decode("ascii")))
    emit("mutation: L%d  after : %r"
         % (target_line, lines[target_line - 1].decode("ascii")))
    emit("mutation: whole-file differing lines = %r (exactly [L%d]); "
         "line count %d -> %d; oid %s -> %s (pinned match now False)"
         % (differing, target_line, len(original_lines),
            len(mutated_lines), git_oid(pinned_bytes), git_oid(mutated)))


def restore_pinned(pinned_bytes, label, manifest, src_path, sweeper, emit):
    src_path.write_bytes(pinned_bytes)
    sweeper.sweep(src_path.parent.parent, "revert",
                  "after restore write", emit)
    oid_now = git_oid(src_path.read_bytes())
    pinned = manifest["labels"][label]["oid"]
    emit(f"restore: bytes written back; oid {oid_now}; == pinned: "
         f"{oid_now == pinned}")
    if oid_now != pinned:
        raise SystemExit("restore did not reproduce the pinned blob")


def run_arm(label, arm, pkg, pinned_bytes, manifest, sweeper, repo, state,
            out_dir):
    entry = manifest["labels"][label]
    first, last = entry["alive_range"]
    exc_line, ret_line = entry["target_lines"]
    src_path = pkg / "src" / "suitelock.py"
    transcript = []

    def emit(text=""):
        transcript.append(str(text))
        log(f"  [{label}/{arm}] {text}")

    emit(f"arm={arm} label={label} utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    emit(f"python={sys.version.split()[0]} platform={sys.platform}")
    emit(f"pinned blob oid={entry['oid']} bytes={entry['bytes']} "
         f"source_ref={entry['source_ref']} tip={entry['source_ref_tip']}")
    emit(f"target lines: L{exc_line} (except Exception:) / L{ret_line} "
         f"(return True); _alive range L{first}-L{last}")

    if arm == "mutation":
        flip_target_line(pinned_bytes, label, manifest, src_path, sweeper,
                         emit)
    if arm == "restore":
        restore_pinned(pinned_bytes, label, manifest, src_path, sweeper, emit)

    oid_now = git_oid(src_path.read_bytes())
    emit(f"pkg src oid at arm run: {oid_now} (== pinned: "
         f"{oid_now == entry['oid']})")

    sweeper.sweep(pkg, "pre-arm", f"before the {arm} run", emit)
    purge_modules()
    clean_sys_path(pkg)
    for other in LABELS:
        os.environ.pop("CANARY0180_BLOB_" + other.upper(), None)
    os.environ["CANARY0180_BLOB_" + label.upper()] = str(src_path)
    os.environ["CANARY0180_LABELS"] = label
    emit("env: CANARY0180_BLOB_%s=<PKG>/src/suitelock.py, CANARY0180_LABELS=%s"
         % (label.upper(), label))

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    modules_loaded = []
    behaviour_method = ("test_a_probe_that_raises_counts_as_alive_on_the_"
                        + label + "_blob")

    if arm in ("before", "after"):
        for corpus in manifest["corpus"]:
            module = load_module_from_path(
                pkg / "tests" / corpus["name"],
                corpus["name"][:-3] + f"__{label}__{arm}")
            suite.addTests(loader.loadTestsFromModule(module))
            modules_loaded.append(corpus["name"])
    if arm == "after":
        module = load_module_from_path(
            pkg / "tests" / (MY_TEST_NAME + ".py"),
            f"{MY_TEST_NAME}__{label}__{arm}")
        suite.addTests(loader.loadTestsFromModule(module))
        modules_loaded.append(MY_TEST_NAME + ".py (whole module)")
    if arm in ("calibration", "mutation", "restore"):
        module = load_module_from_path(
            pkg / "tests" / (MY_TEST_NAME + ".py"),
            f"{MY_TEST_NAME}__{label}__{arm}")
        suite = loader.loadTestsFromNames(
            [f"{MY_CLASS}.{behaviour_method}"], module=module)
        modules_loaded.append(MY_TEST_NAME + f".py (single method "
                               f"{behaviour_method})")
    emit("modules loaded for this arm: " + "; ".join(modules_loaded))
    emit("note: the tracer is armed for the RUN phase; test-module imports "
         "precede it, so import-time lines of the blob are counted only "
         "where a load happens inside a test (the closing test's own "
         "importlib load).")

    buffer = io.StringIO()
    runner = unittest.TextTestRunner(stream=buffer, verbosity=2,
                                     resultclass=RecordingResult)
    tracer = LineTracer(src_path)
    with tracer:
        result = runner.run(suite)
    my_imported = any(MY_TEST_NAME in name for name in sys.modules)

    emit("--- unittest -v ---")
    for line in buffer.getvalue().rstrip().splitlines():
        emit(line)
    emit("--- tracer: target lines (THE ANSWER) ---")
    emit(f"L{exc_line} (except Exception:) = {tracer.counts[exc_line]}")
    emit(f"L{ret_line} (return True as pinned) = {tracer.counts[ret_line]}")
    emit(f"--- tracer: _alive witness table L{first}-L{last} ---")
    src_lines = src_path.read_bytes().split(b"\n")
    for number in range(first, last + 1):
        emit("L%-4d = %3d | %s"
             % (number, tracer.counts[number],
                src_lines[number - 1].decode("ascii", "replace")))
    body_total = sum(tracer.counts[n] for n in range(first, last + 1))
    emit(f"total traced line executions inside _alive L{first}-L{last}: "
         f"{body_total}")

    fail_ids = sorted(test.id() for test, _ in result.failures)
    err_ids = sorted(test.id() for test, _ in result.errors)
    skip_ids = sorted(test.id() for test, _ in result.skipped)
    # Normalised ids for cross-arm set comparison: each arm loads the corpus
    # under a unique module name (stem__label__arm) so a stale sys.modules hit
    # is impossible; the comparison strips that suffix, leaving
    # <file stem>.<Class>.<method> - the name a reviewer would recognise.
    arm_suffix = f"__{label}__{arm}"

    def norm(ids):
        return sorted(i.replace(arm_suffix, "") for i in ids)

    fail_names = norm(fail_ids)
    err_names = norm(err_ids)
    bad_names = set(fail_names) | set(err_names)
    emit(f"normalised red names (suffix '{arm_suffix}' stripped): "
         f"{len(bad_names)} total")
    emit(f"testsRun={result.testsRun}")
    emit("failure ids: " + (", ".join(fail_ids) if fail_ids else "(none)"))
    emit("error ids: " + (", ".join(err_ids) if err_ids else "(none)"))
    emit("skipped ids: " + (", ".join(skip_ids) if skip_ids else "(none)"))
    mine_green = sorted(s for s in result.successes if MY_TEST_NAME in s)
    emit("closing-test successes: "
         + (", ".join(mine_green) if mine_green else "(none)"))
    emit(f"closing-test module imported during this arm: {my_imported}")

    expectations = []

    def expect(condition, text):
        expectations.append((bool(condition), text))

    if arm == "calibration":
        expect(result.testsRun == 1, "Ran exactly 1 test")
        expect(not result.failures and not result.errors,
               "the control passed: fake-raise answered ALIVE")
        expect(tracer.counts[exc_line] == 1 and tracer.counts[ret_line] == 1,
               f"L{exc_line}=1 and L{ret_line}=1 - 0150's passing control "
               f"reproduced FIRST, so the instrument can print both answers")
    elif arm == "before":
        expect(not my_imported,
               "the closing-test module was NOT imported (arm without it)")
        expect(tracer.counts[exc_line] == 0 and tracer.counts[ret_line] == 0,
               f"L{exc_line}=0 and L{ret_line}=0 - 0150's zero reproduced")
        expect(result.testsRun == state["corpus_total"],
               "every census-counted corpus test ran")
        expect(body_total > 0,
               "the corpus DID execute _alive's body, so the zero is a "
               "branch never taken, not a function never run")
        if label == "identity":
            expect(not result.failures and not result.errors,
                   "identity corpus green (0170's measurement re-checked)")
        else:
            expect(len(result.failures) >= 1,
                   "master corpus carries the born-red L323 failure "
                   "(0170's red arm re-checked)")
        state["before_bad_names"] = bad_names
    elif arm == "after":
        expect(tracer.counts[exc_line] == 1 and tracer.counts[ret_line] == 1,
               f"L{exc_line}=1 and L{ret_line}=1: exactly ONE execution of "
               f"the fail-closed branch, added by the closing test")
        suffix = f"__{label}__after.{MY_CLASS}."
        behaviour_id = MY_TEST_NAME + suffix + behaviour_method
        hash_id = (MY_TEST_NAME + suffix
                   + "test_the_fixture_blobs_are_the_pinned_blobs")
        expect(behaviour_id in result.successes,
               "the closing behaviour test ran and passed")
        expect(hash_id in result.successes,
               "the fixture-hash guard passed on the pristine mirror")
        expect(bad_names == state["before_bad_names"],
               "the red NAME SET is unchanged versus the before arm "
               "(set equality on arm-suffix-stripped ids, not counts; "
               f"both arms: {len(bad_names)} names)")
        expect(result.testsRun == state["corpus_total"] + 3,
               "ran = corpus + my 3 (behaviour, hash guard, other-label "
               "skip)")
    elif arm == "mutation":
        expect(result.testsRun == 1 and len(result.failures) == 1
               and not result.errors,
               "Ran 1, exactly 1 FAILURE and 0 errors")
        if result.failures:
            failed_test, traceback_text = result.failures[0]
            expect(failed_test.id().endswith(behaviour_method),
                   "the failing test IS the closing behaviour test - it "
                   "names itself: " + failed_test.id())
            expect(CLOSING_PHRASE in traceback_text,
                   "the failure is the fail-closed assertion (the intended "
                   "reason), not an import/attribute error")
            expect(NEVER_FIRED_PHRASE not in traceback_text,
                   "the fake-fired witness did NOT fail: no other guard "
                   "fired first")
        expect(tracer.counts[exc_line] == 1 and tracer.counts[ret_line] == 1,
               "the branch still EXECUTES 1/1 under mutation: the flip "
               "changed the value, not the coverage - the test catches it "
               "by value")
    elif arm == "restore":
        expect(oid_now == entry["oid"],
               "pkg src is byte-identical to the pinned blob again")
        expect(result.testsRun == 1 and not result.failures
               and not result.errors,
               "green again after the revert")
        expect(tracer.counts[exc_line] == 1 and tracer.counts[ret_line] == 1,
               "1/1 again after the revert")

    arm_ok = True
    emit("--- expectations ---")
    for passed, text in expectations:
        emit(("PASS " if passed else "FAIL ") + text)
        arm_ok = arm_ok and passed
    emit(f"ARM {arm} ({label}): {'PASS' if arm_ok else 'FAIL'}")

    write_transcript(out_dir, f"arm-{label}-{arm}.txt", transcript,
                     scrub_pairs(pkg, repo))
    return arm_ok


def scrub_pairs(pkg, repo):
    return ((str(pkg), "<PKG>"),
            (tempfile.gettempdir(), "<TMP>"),
            (str(SOURCE_ROOT), "<SOURCE_ROOT>"),
            (str(repo), "<REPO>"))


def write_transcript(out_dir, name, transcript, pairs):
    """Scrub machine paths, force ASCII (transliterating and SAYING so - a
    corpus docstring from another lane may carry an em-dash, and the evidence
    must survive that rather than die on it), LF-only, with a readback."""
    text = "\n".join(transcript) + "\n"
    for raw, placeholder in pairs:
        text = text.replace(raw, placeholder)
        text = text.replace(os.path.normcase(raw), placeholder)
    non_ascii = [ch for ch in text if ord(ch) > 127]
    if non_ascii:
        text += (f"[transcript note: {len(non_ascii)} non-ASCII character(s) "
                 f"in the captured output were transliterated to '?' for the "
                 f"committed copy; distinct codepoints: "
                 f"{sorted({hex(ord(c)) for c in non_ascii})}]\n")
    data = text.encode("ascii", "replace")
    out_path = Path(out_dir) / name
    out_path.write_bytes(data)
    readback = out_path.read_bytes()
    if readback != data:
        raise SystemExit(f"transcript readback mismatch: {out_path}")
    log(f"  transcript written: {out_path} ({len(readback)} bytes, "
        f"CR={readback.count(bytes([13]))}, non-ascii transliterated="
        f"{len(non_ascii)})")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=",".join(LABELS))
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--repo", default=os.getcwd(),
                        help="git checkout holding the pinned objects")
    parser.add_argument("--out", default=str(FIXTURE_DIR / "arms"))
    parser.add_argument("--pkg-parent", default=tempfile.gettempdir())
    args = parser.parse_args()

    labels = [x.strip() for x in args.labels.split(",") if x.strip()]
    arms = [x.strip() for x in args.arms.split(",") if x.strip()]
    for label in labels:
        if label not in LABELS:
            raise SystemExit(f"unknown label: {label}")
    for arm in arms:
        if arm not in ARMS:
            raise SystemExit(f"unknown arm: {arm}")
    ambient = {k: v for k, v in os.environ.items()
               if k.startswith("CANARY0180_")}
    if ambient:
        log(f"ambient CANARY0180_* cleared before the run: {sorted(ambient)}")
        for key in ambient:
            os.environ.pop(key)

    manifest = json.loads(
        (FIXTURE_DIR / "MANIFEST.json").read_bytes().decode("ascii"))
    if not (SOURCE_ROOT / MY_TEST_REL).exists():
        raise SystemExit(f"closing test not found at {SOURCE_ROOT / MY_TEST_REL}")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sweeper = Sweeper()
    summary = []
    overall = True
    for label in labels:
        pkg = Path(tempfile.mkdtemp(prefix=f"canary0180-{label}-",
                                    dir=args.pkg_parent))
        log(f"== label {label}: pkg {pkg} ==")
        build_lines = [f"build/census record for label={label} "
                       f"utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                       f"python={sys.version.split()[0]}",
                       f"manifest labels entry oid={manifest['labels'][label]['oid']}"]

        def build_emit(line, _t=label):
            build_lines.append(str(line))
            log(f"  [build/{_t}] {line}")

        pinned_bytes = build_pkg(label, manifest, pkg, args.repo, sweeper,
                                 build_emit)
        state = {}
        state["corpus_total"] = census(label, manifest, pkg, build_emit)
        write_transcript(out_dir, f"arm-{label}-build.txt", build_lines,
                         scrub_pairs(pkg, args.repo))
        for arm in arms:
            ok = run_arm(label, arm, pkg, pinned_bytes, manifest, sweeper,
                         args.repo, state, out_dir)
            summary.append((label, arm, ok))
            overall = overall and ok
        final_oid = git_oid((pkg / "src" / "suitelock.py").read_bytes())
        log(f"== label {label}: pkg src final oid {final_oid} "
            f"(== pinned: {final_oid == manifest['labels'][label]['oid']}); "
            f"pkg kept for inspection ==")
    log("--- summary ---")
    for label, arm, ok in summary:
        log(f"{label:9s} {arm:12s} {'PASS' if ok else 'FAIL'}")
    log("pyc sweeps by direction: "
        + ", ".join(f"{k}={v}" for k, v in sorted(sweeper.totals.items())))
    log("ARMS: " + ("ALL-PASS" if overall else "FAIL"))
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
