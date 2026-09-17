"""Run a subset of test modules and write results."""
import sys, os, unittest, re, json, time, io

PROJECT = r"C:\Users\Zvonimir\Desktop\resonate-qwen-worker"
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)

half = sys.argv[1] if len(sys.argv) > 1 else "1"
module_file = os.path.join(PROJECT, "scripts", f"task202_half{half}.txt")
result_file = os.path.join(PROJECT, "scripts", f"task202_result_half{half}.json")
log_file = os.path.join(PROJECT, "scripts", f"task202_log_half{half}.txt")

with open(module_file) as f:
    modules = [line.strip() for line in f if line.strip()]

print(f"Half {half}: {len(modules)} modules")

start = time.monotonic()
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for mod in modules:
    try:
        suite.addTests(loader.loadTestsFromName(f"tests.{mod}"))
    except Exception as e:
        print(f"  SKIP {mod}: {e}")

# Run with output to log
stream = io.StringIO()
runner = unittest.TextTestRunner(stream=stream, verbosity=0)
result = runner.run(suite)
elapsed = time.monotonic() - start

output = stream.getvalue()
with open(log_file, "w") as f:
    f.write(output)

# Parse results
ran = result.testsRun
failures = len(result.failures)
errors = len(result.errors)
skipped = len(result.skipped)

# Extract failure names
failure_names = []
for test, _ in result.failures:
    failure_names.append(f"FAIL: {test}")
for test, _ in result.errors:
    failure_names.append(f"ERROR: {test}")

data = {
    "half": half,
    "modules": len(modules),
    "tests_run": ran,
    "failures": failures,
    "errors": errors,
    "skipped": skipped,
    "wall_seconds": round(elapsed, 1),
    "failure_names": failure_names,
    "log": log_file,
}

with open(result_file, "w") as f:
    json.dump(data, f, indent=2)

print(f"Done: ran={ran} fail={failures} err={errors} skip={skipped} wall={round(elapsed,1)}s")
print(f"Result: {result_file}")
