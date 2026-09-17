"""Run a quarter of the test suite."""
import sys, os, unittest, json, time, io

PROJECT = r"C:\Users\Zvonimir\Desktop\resonate-qwen-worker"
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)

q = sys.argv[1]
module_file = os.path.join(PROJECT, "scripts", f"task202_quarter{q}.txt")
result_file = os.path.join(PROJECT, "scripts", f"task202_result_q{q}.json")
log_file = os.path.join(PROJECT, "scripts", f"task202_log_q{q}.txt")

with open(module_file) as f:
    modules = [l.strip() for l in f if l.strip()]

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for mod in modules:
    try:
        suite.addTests(loader.loadTestsFromName(f"tests.{mod}"))
    except Exception as e:
        pass

start = time.monotonic()
stream = io.StringIO()
runner = unittest.TextTestRunner(stream=stream, verbosity=0)
result = runner.run(suite)
elapsed = time.monotonic() - start

with open(log_file, "w") as f:
    f.write(stream.getvalue())

data = {
    "quarter": int(q),
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "skipped": len(result.skipped),
    "wall_seconds": round(elapsed, 1),
    "failure_names": [f"FAIL: {t}" for t,_ in result.failures] + [f"ERROR: {t}" for t,_ in result.errors],
}
with open(result_file, "w") as f:
    json.dump(data, f, indent=2)

print(f"Q{q}: ran={result.testsRun} fail={len(result.failures)} err={len(result.errors)} skip={len(result.skipped)} wall={round(elapsed,1)}s")
