#!/usr/bin/env python3
"""Run the full offline suite and capture the summary."""
import subprocess
import sys

result = subprocess.run(
    [r"C:\Users\Zvonimir\AppData\Local\Python\pythoncore-3.14-64\python.exe", "-m", "tests.offline"],
    capture_output=True,
    text=True,
    timeout=2400  # 40 minutes
)

# Write full output to file
with open("suite_result.txt", "w", encoding="utf-8") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n=== RETURN CODE: {result.returncode} ===\n")

# Print summary
lines = result.stdout.split('\n')
for line in lines[-20:]:
    print(line)

sys.exit(result.returncode)
