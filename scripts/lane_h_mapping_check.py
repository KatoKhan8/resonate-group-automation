"""The step-key -> provider-position mapping, DERIVED BY RUNNING THE CODE.

Two committed documents got this wrong and the brief for this lane names it
as the thing not to take from a document. So it is not read off one: lane B's
`CADENCE_STEPS` and lane B's `email_sequence` block are fed to the real
`bisonfactory._sequence_steps`, and the real `_variables_for` is then asked
which provider variable each step's words arrive in.
"""
import sys, os, json, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
LANE_B = "worktree-agent-a68c1abeb4d3a99f5"

import yaml
from src import bisonfactory


def blob(path):
    out = subprocess.run(["git", "show", f"{LANE_B}:{path}"], cwd=ROOT,
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8")


cfg = yaml.safe_load(blob("config/clients/productive.yaml"))
seq_cfg = cfg["email_sequence"]

# lane B's own CADENCE_STEPS, lifted out of their script by executing it in a
# namespace rather than retyping the days.
ns = {"__file__": os.path.join(ROOT, "scripts", "stage_s7_copy.py"),
      "__name__": "laneb_s7"}
exec(compile(blob("scripts/batch1_build.py"), f"{LANE_B}:batch1_build.py",
             "exec"), ns)
steps = ns["CADENCE_STEPS"]
print("lane B CADENCE_STEPS:")
for s in steps:
    print("   ", s)
print("lane B STEP_KEYS:", ns["STEP_KEYS"])
print("config thread_reply_pattern:", seq_cfg["thread_reply_pattern"])
print("config declared waits:",
      {k: v.get("wait_in_days") for k, v in seq_cfg["steps"].items()})

seq = bisonfactory._sequence_steps(seq_cfg, steps)
print("\n_sequence_steps built %d step(s):" % len(seq))
for node in seq:
    print("   order=%s step_key=%-4s wait=%s thread_reply=%s body=%r"
          % (node.get("order"), node.get("step_key"), node.get("wait_in_days"),
             node.get("thread_reply"), node.get("email_body")))

gaps = [b["day"] - a["day"] for a, b in zip(steps, steps[1:])]
print("\ncadence days   :", [s["day"] for s in steps])
print("cadence gaps   :", gaps, "(+ last step's inert wait)")
print("declared waits :", [n.get("wait_in_days") for n in seq])

# _variables_for: which numbered variable does each step key land in?
lead = {"record_id": "r1", "contact_key": "c1",
        "copy": [{"step_key": n["step_key"], "subject": "S",
                  "body": "BODY-OF-%s" % n["step_key"]} for n in seq]}
values = bisonfactory._variables_for(lead, {"client": "productive"}, seq)
print("\n_variables_for ->")
for item in values:
    name = item.get("name") if isinstance(item, dict) else item
    val = item.get("value") if isinstance(item, dict) else values[item]
    if str(name).startswith(("body_", "subject_")):
        print("   %-12s %r" % (name, val))
print("\nSO: step key -> provider variable")
for n in seq:
    print("   %-4s  ->  {BODY_%d}" % (n["step_key"], n["order"]))
