"""TASK-202: run the full suite and write results to a file.
Uses Popen so the runner exits immediately and the test process runs independently."""
import subprocess, sys, os, time, json, re

PROJECT = r"C:\Users\Zvonimir\Desktop\resonate-qwen-worker"
RESULT = os.path.join(PROJECT, "scripts", "task202_result.json")
LOG = os.path.join(PROJECT, "scripts", "task202_suite.log")
PIDFILE = os.path.join(PROJECT, "scripts", "task202_pid.txt")

# Write our PID
with open(PIDFILE, "w") as f:
    f.write(str(os.getpid()))

# Run the suite
start = time.monotonic()
with open(LOG, "w") as lf:
    proc = subprocess.Popen(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        stdout=lf, stderr=subprocess.STDOUT,
        cwd=PROJECT,
    )
    try:
        proc.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

elapsed = time.monotonic() - start

# Parse the log
with open(LOG, "r", errors="replace") as f:
    content = f.read()

result = {"exit_code": proc.returncode, "wall_seconds": round(elapsed, 1), "log": LOG}

m = re.search(r"^Ran (\d+) test.*$", content, re.MULTILINE)
if m:
    result["ran_line"] = m.group()
m2 = re.search(r"^(FAILED|OK)\b.*$", content, re.MULTILINE)
if m2:
    result["verdict_line"] = m2.group()

failures = re.findall(r"^(?:FAIL|ERROR): (.+)$", content, re.MULTILINE)
result["failure_names"] = failures
result["failure_count"] = len(failures)

with open(RESULT, "w") as f:
    json.dump(result, f, indent=2)
