#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TASK-0246 - the controls for `scripts/exit_nine_pins.py`.

A resolver that has only ever printed `RESOLVES` is the B7 shape: it looks
like a check and it is a constant. So every control below is PAIRED - one that
must resolve and one that must not - and the two mutants at the end must kill
DIFFERENT, NAMED, NON-EMPTY sets of them.

    py -3 -B scripts/exit_pins_controls.py c1       a pin known good
    py -3 -B scripts/exit_pins_controls.py c2       the two that must FAIL
    py -3 -B scripts/exit_pins_controls.py c3       the finder's floor
    py -3 -B scripts/exit_pins_controls.py c4       both mutants, paired
    py -3 -B scripts/exit_pins_controls.py all      every control

## NOTHING TRACKED IS MUTATED, AND THAT IS STRONGER THAN A PROVEN REVERT

`scripts/exit_nine_pins.py` is a pure READER - it opens files and runs
`git show`, and it writes nothing. So a mutant is built as a COPY in the
system temp folder and loaded from there with its `ROOT` pointed back at this
repository. The tracked file is never opened for writing at all, and each
mode asserts its sha256 identical at entry and at exit. A revert that has to
be proven is a revert that happened; this one did not need to.

The one trap that applies anyway, and the reason every copy gets a UNIQUE
name: `.pyc` invalidation is whole-second, so two same-size mutants written
into one path inside one second import the FIRST one's bytes and the second
reads as a no-op. `-B` is passed and the filename carries a counter.
"""
import hashlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = os.path.join(ROOT, "scripts", "exit_nine_pins.py")
SCRATCH = os.environ.get("EXIT_PINS_SCRATCH",
                         os.path.join(tempfile.gettempdir(), "exit-pins-0246"))

#: The pin TASK-0243 found. Not retyped from the brief - this is the literal
#: that stood in `REMOVAL_DEMONSTRATION` at dcd618d9c and still stands in
#: `obs2_nine.DEMONSTRATION`.
DEAD_PIN = ("tests.test_a_suppressed_address_cannot_reach_a_provider"
            ".ARemovalRequestWritesARow"
            ".test_an_attributed_removal_request_writes_a_suppression_row")
#: The class that actually holds those two demonstrations.
LIVE_PIN = ("tests.test_a_suppressed_address_cannot_reach_a_provider"
            ".ARemovalRequestIsWrittenAndSurvivesARestart"
            ".test_an_attributed_removal_request_writes_a_suppression_row")
#: Invented in this session, on 2026-10-16, and deliberately plausible. If
#: this ever resolves, the resolver is answering without looking.
INVENTED_PIN = ("tests.test_a_suppressed_address_cannot_reach_a_provider"
                ".ASuppressionRowIsBurnishedOnTuesdays"
                ".test_the_burnishing_is_idempotent_across_a_restart")

#: THE EVALUATOR THIS HARNESS USES AS A CORPUS, CHOSEN FROM WHAT THE BRANCH
#: ACTUALLY HAS. `exit_nine.py` and `obs2_nine.py` live on two branches that
#: do not contain each other - which is the condition that let TASK-0243's
#: correction to one leave the other shipping the same dead pin - so a harness
#: hard-coded to either is inoperable on half the lineages. First existing
#: wins; none existing is a loud refusal, never a silent skip.
CORPUS_CANDIDATES = ("scripts/exit_nine.py", "scripts/obs2_nine.py",
                     "scripts/exit_nine_reachability.py")


def corpus():
    """(rel path, source text) of an evaluator present in THIS tree."""
    for rel in CORPUS_CANDIDATES:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.isfile(path):
            with io.open(path, encoding="utf-8") as handle:
                return rel, handle.read()
    raise SystemExit(
        "none of %s is in this tree, so C1c and C3 have no corpus to read. "
        "A control with nothing to watch is not a control that passed."
        % ", ".join(CORPUS_CANDIDATES))


_counter = [0]


def sha256_of(path):
    with io.open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load(source_text, tag):
    """Import `source_text` as a throwaway module with ROOT pointed here."""
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    _counter[0] += 1
    name = "pins_%s_%d_%d" % (tag, os.getpid(), _counter[0])
    path = os.path.join(SCRATCH, name + ".py")
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(source_text)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    return module, path


def pristine():
    with io.open(PINS, encoding="utf-8") as handle:
        return handle.read()


def cell(label, expect, got, extra=""):
    ok = (expect == got)
    print("  %-5s %-58s expect %-18s got %-18s %s%s"
          % ("PASS" if ok else "KILLED", label, expect, got,
             "" if ok else "<-- ", extra))
    return ok


# ------------------------------------------------------------------------ C1

def c1(module=None):
    """The resolver must be shown ABLE to resolve. Four good pins, four kinds."""
    module = module or load(pristine(), "c1")[0]
    disk = module.DiskTree(ROOT)
    out = []
    verdict, reason = module.resolve_dotted(disk, LIVE_PIN)
    out.append(("C1a dotted module.Class.method, known good", verdict, reason))
    verdict, reason = module.resolve_dotted(
        disk, "tests.test_a_suppressed_address_cannot_reach_a_provider")
    out.append(("C1b dotted module only", verdict, reason))
    rel, _ = corpus()
    verdict, reason = module.resolve_path(disk, rel)
    out.append(("C1c repo path (%s)" % rel, verdict, reason))
    verdict, reason = module.resolve_file_symbol(
        disk, "tests/test_a_suppressed_address_cannot_reach_a_provider.py::"
              "ARemovalRequestIsWrittenAndSurvivesARestart")
    out.append(("C1d file::symbol", verdict, reason))

    results = {}
    print("C1 - the resolver can resolve")
    for label, verdict, reason in out:
        results[label.split()[0]] = cell(label, module.RESOLVES, verdict)
    #: the gate itself, on good pins, must NOT raise
    try:
        module.require_resolvable([LIVE_PIN], disk, "C1e")
        results["C1e"] = cell("C1e require_resolvable passes a good pin",
                              "no raise", "no raise")
    except module.UnresolvablePin as raised:
        results["C1e"] = cell("C1e require_resolvable passes a good pin",
                              "no raise", "raised", str(raised)[:60])
    return results


# ------------------------------------------------------------------------ C2

def c2(module=None):
    """Paired, and the one that matters: the resolver must be able to FAIL."""
    module = module or load(pristine(), "c2")[0]
    disk = module.DiskTree(ROOT)
    results = {}
    print("C2 - the resolver can fail")
    verdict, reason = module.resolve_dotted(disk, DEAD_PIN)
    results["C2a"] = cell("C2a ARemovalRequestWritesARow (0243's find)",
                          module.DOES_NOT_RESOLVE, verdict)
    print("        %s" % reason[:150])
    verdict, reason = module.resolve_dotted(disk, INVENTED_PIN)
    results["C2b"] = cell("C2b a name invented in this session",
                          module.DOES_NOT_RESOLVE, verdict)
    print("        %s" % reason[:150])
    verdict, _ = module.resolve_path(disk, "scripts/no_such_file_0246.py")
    results["C2c"] = cell("C2c a repo path that is not there",
                          module.DOES_NOT_RESOLVE, verdict)
    verdict, _ = module.resolve_file_symbol(
        disk, "tests/test_a_suppressed_address_cannot_reach_a_provider.py::"
              "ARemovalRequestWritesARow")
    results["C2d"] = cell("C2d file::symbol, symbol absent",
                          module.DOES_NOT_RESOLVE, verdict)
    try:
        module.require_resolvable([DEAD_PIN], disk, "C2e")
        results["C2e"] = cell("C2e require_resolvable REFUSES a dead pin",
                              "raised", "no raise")
    except module.UnresolvablePin:
        results["C2e"] = cell("C2e require_resolvable REFUSES a dead pin",
                              "raised", "raised")
    return results


# ------------------------------------------------------------------------ C3

#: A pin assembled at runtime. The finder reads string CONSTANTS, so the
#: dotted name below never exists as one literal and cannot be seen.
INVISIBLE_PLANT = '''

#: TASK-0246 C3 plant - a pin in a shape the finder does not look for.
_C3_MODULE = "tests.test_a_suppressed_address_cannot_reach_a_provider"
_C3_CLASS = "A" + "RemovalRequestWritesARow"
C3_PIN = "%s.%s.test_an_attributed_removal_request_writes_a_suppression_row" % (
    _C3_MODULE, _C3_CLASS)
'''
#: The control for the control: the SAME pin as one literal must be seen, or
#: "not found" would prove nothing about the shape.
VISIBLE_PLANT = '''

#: TASK-0246 C3 control - the same pin, as one literal.
C3_PIN_VISIBLE = ("tests.test_a_suppressed_address_cannot_reach_a_provider"
                  ".ARemovalRequestWritesARow"
                  ".test_an_attributed_removal_request_writes_a_suppression_row")
'''


def c3(module=None):
    """Show the FINDER able to miss one, and say the word FLOOR if it does."""
    module = module or load(pristine(), "c3")[0]
    rel, original = corpus()
    base = module.find_pins(original, "copy-of-" + rel)
    results = {}
    print("C3 - can the finder miss a pin?")
    print("  corpus    %s" % rel)
    print("  baseline  %d pin(s) in an unplanted copy" % len(base))

    seen_visible = module.find_pins(original + VISIBLE_PLANT, "copy")
    gained_v = len(seen_visible) - len(base)
    results["C3a"] = cell("C3a a pin planted as ONE LITERAL is seen",
                          1, gained_v)

    seen_invisible = module.find_pins(original + INVISIBLE_PLANT, "copy")
    gained_i = len(seen_invisible) - len(base)
    #: The invisible plant does add TWO literals the finder can see - the
    #: module name and the leaf - but NOT the pin itself, which is the
    #: three-part dotted name naming the dead class. That distinction is the
    #: whole control, so it is measured by NAME and not by count.
    literals = set(p.literal for p in seen_invisible) - set(
        p.literal for p in base)
    whole_pin = ("tests.test_a_suppressed_address_cannot_reach_a_provider"
                 ".ARemovalRequestWritesARow"
                 ".test_an_attributed_removal_request_writes_a_suppression_row")
    results["C3b"] = cell("C3b the runtime-assembled pin is NOT seen",
                          False, whole_pin in literals)
    print("        new literals the finder did see: %s"
          % (", ".join(sorted(literals)) or "none"))
    print("  VERDICT   the denominator is a FLOOR. %d pin(s) is what this "
          "finder can see," % len(base))
    print("            not what exists: a pin assembled at runtime - here "
          "%r built from" % whole_pin[:48])
    print("            two fragments - is invisible to it, and was invisible "
          "to it just now.")
    return results


# ------------------------------------------------------------------------ C4

MUTANTS = {
    "always": (
        '''def resolve_dotted(tree, dotted):
    return RESOLVES, "MUTANT always"''',
        "every pin resolves"),
    "never": (
        '''def resolve_dotted(tree, dotted):
    return DOES_NOT_RESOLVE, "MUTANT never"''',
        "no pin resolves"),
}
ANCHOR = 'def resolve_dotted(tree, dotted):'


def _mutate(source, which):
    body, _ = MUTANTS[which]
    if source.count(ANCHOR) != 1:
        raise SystemExit("the mutation anchor %r occurs %d times, need 1 - a "
                         "plant that lands nowhere is the shape this harness "
                         "exists to catch" % (ANCHOR, source.count(ANCHOR)))
    head, tail = source.split(ANCHOR, 1)
    #: swallow the original def entirely, up to the next top-level def
    rest = tail.split("\ndef ", 1)
    remainder = "\ndef " + rest[1] if len(rest) > 1 else ""
    return head + body + "\n" + remainder


def c4():
    """Paired mutation. Each mutant must kill a NAMED, DIFFERENT, NON-EMPTY
    set of the controls above. A mutant that kills nothing is a reportable
    result, not a pass."""
    before = sha256_of(PINS)
    source = pristine()
    print("C4 - paired mutation of the matcher")
    print("  tracked file sha256 at entry  %s" % before)
    print()

    print("  --- UNMUTATED, the reference set ---")
    clean, _ = load(source, "clean")
    reference = {}
    reference.update(c1(clean))
    reference.update(c2(clean))
    reference.update(c3(clean))
    green = set(k for k, v in reference.items() if v)
    print("  reference GREEN: %s" % ", ".join(sorted(green)))
    print()

    killed = {}
    for which in ("always", "never"):
        _, what = MUTANTS[which]
        print("  --- MUTANT %r: %s ---" % (which, what))
        module, path = load(_mutate(source, which), which)
        got = {}
        got.update(c1(module))
        got.update(c2(module))
        got.update(c3(module))
        dead = sorted(k for k in green if not got.get(k, False))
        killed[which] = dead
        print("  MUTANT %-7s KILLS %d control(s): %s"
              % (which, len(dead), ", ".join(dead) or "NOTHING"))
        print("  mutant source %s" % path)
        print()

    after = sha256_of(PINS)
    print("  tracked file sha256 at exit   %s" % after)
    print("  UNCHANGED: %s  (no tracked file was ever opened for writing)"
          % (before == after))
    print()
    both = set(killed["always"]) & set(killed["never"])
    print("  C4 VERDICT")
    print("    always kills  %s" % (", ".join(killed["always"]) or "NOTHING"))
    print("    never  kills  %s" % (", ".join(killed["never"]) or "NOTHING"))
    print("    overlap       %s" % (", ".join(sorted(both)) or "none"))
    ok = (killed["always"] and killed["never"]
          and set(killed["always"]) != set(killed["never"]))
    print("    non-empty AND different: %s" % ok)
    if not ok:
        print("    A MUTANT THAT KILLS NOTHING IS A REPORTABLE RESULT, NOT A "
              "PASS - see the lane entry.")
    return ok


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    before = sha256_of(PINS)
    if mode == "c1":
        c1()
    elif mode == "c2":
        c2()
    elif mode == "c3":
        c3()
    elif mode == "c4":
        c4()
    elif mode == "all":
        c1()
        print()
        c2()
        print()
        c3()
        print()
        c4()
    else:
        raise SystemExit("modes: c1 c2 c3 c4 all")
    after = sha256_of(PINS)
    print()
    print("scripts/exit_nine_pins.py sha256  %s -> %s  identical=%s"
          % (before[:16], after[:16], before == after))
    return 0 if before == after else 1


if __name__ == "__main__":
    sys.exit(main())
