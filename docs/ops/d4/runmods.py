"""Run named modules, print one line per test: STATUS<TAB>dotted.name.

Outcome per name, both directions, so the two trees can be diffed by SET.
"""
import os, sys, unittest

# run_suite semantics: the TREE being measured is the import root, not this
# script's directory. Without this the loader returns _FailedTest and every
# name reads ERROR, which is indistinguishable from a real break.
sys.path.insert(0, os.getcwd())

class Collect(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = {}
    def addSuccess(self, t):
        super().addSuccess(t); self.rows[t.id()] = "ok"
    def addFailure(self, t, e):
        super().addFailure(t, e); self.rows[t.id()] = "FAIL"
    def addError(self, t, e):
        super().addError(t, e); self.rows[t.id()] = "ERROR"
    def addSkip(self, t, r):
        super().addSkip(t, r); self.rows[t.id()] = "skip"
    def addExpectedFailure(self, t, e):
        super().addExpectedFailure(t, e); self.rows[t.id()] = "xfail"
    def addUnexpectedSuccess(self, t):
        super().addUnexpectedSuccess(t); self.rows[t.id()] = "xpass"

if __name__ == "__main__":
    mods = sys.argv[1:]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([loader.loadTestsFromName(m) for m in mods])
    import io
    runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=Collect, verbosity=0)
    res = runner.run(suite)
    for name in sorted(res.rows):
        print("%s\t%s" % (res.rows[name], name))
    print("#TOTAL\t%d" % len(res.rows), file=sys.stderr)
