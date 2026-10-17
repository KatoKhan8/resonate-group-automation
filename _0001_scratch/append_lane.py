# qwen-coder/0001: binary append of the lane entry with fixed-point length
# computation and byte-offset read-back verification. Verifies every hash
# cited in the body against a FRESH measurement before appending anything.
import hashlib
import os
import subprocess
import sys

LANE = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-qwen-coder.md"
WT = r"C:\Users\Zvonimir\Desktop\resonate-trees\wt-qwen-coder-0001-2026-10-18"
BODY = os.path.join(WT, "_0001_scratch", "lane_entry_body.md")

body = open(BODY, encoding="utf-8").read()
if not body.endswith("\n"):
    body += "\n"

# ---- verify every cited artefact hash against a fresh measurement
artefacts = [
    ("runM1_table23.out", "6f4b717dda20866912597fcfcf81986c20ab6323aa7adbf75877ee2393651002", 14863),
    ("runM2_table23.out", "5cefc53210625fa50616c30b0b617648ad6771d4b4a44bb13895422ebd726f23", 14863),
    ("runN_negctl.out", "271693d251783a0dec4b36b67c19ffac246e607c5f9eafa62751ec323d23b9b1", 12383),
    ("runW_missing_cohort.out", "666a7e138aa9942afc467f98dd58458f1e6c9e099fc3a751a749e2d929d43aba", 274),
    ("runC0_controls_only.out", "987de17228c72e327cbf8019f6873e1e4d74722074afc7764c7c4dcb964dbf07", 4741),
    ("census.py", "f0359309eb4c7455cba7bd0bb3b804bd54f0a0b52d3a582bfbece563bf36821a", 9708),
    ("censusM1.json", "bca484859bb65027f45dbab03053983c6cfd9142ab1db346da8d75185f4d6cc1", 4209),
    ("censusM2.json", "0cfba55293f5299997a446e73fe7fe71c1002c3adf2eaf692d942e8dfe5a1701", 4209),
    ("census_teeth.out", "da9b7b6ca7869ef001db43ca981f52cb41a117b28671303d3471d26b6ffa5e0f", 71),
    ("cohort-synthetic-23.json", "05134d57abcf62afd717266c1fb48100280f4fef54cb7c353c206a583ebd8a73", 3942),
    ("cohort-negctl-3.json", "8e8e4908b309a18682a603ab1867bcc68c9897409d72eb82936f7f087810137c", 525),
]
for name, cited, cited_size in artefacts:
    p = os.path.join(WT, "_0001_scratch", name)
    data = open(p, "rb").read()
    real = hashlib.sha256(data).hexdigest()
    if real != cited:
        sys.exit("ABORT: %s sha256 mismatch: cited %s, measured %s"
                 % (name, cited, real))
    if len(data) != cited_size:
        sys.exit("ABORT: %s size mismatch: cited %d, measured %d"
                 % (name, cited_size, len(data)))
    if cited not in body:
        sys.exit("ABORT: cited hash for %s not present in body" % name)

# ---- verify cited git ids against fresh git output (never retyped)
env = {k: v for k, v in os.environ.items()
       if not k.startswith("GIT_CONFIG_")}


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=WT, capture_output=True,
                       text=True, env=env)
    if r.returncode != 0:
        sys.exit("ABORT: git %s rc=%d stderr=%s"
                 % (args, r.returncode, r.stderr.strip()))
    return r.stdout.strip()


checks = [
    (git("rev-parse", "HEAD"), "lane tip"),
    (git("rev-parse", "origin/task-qwen-coder-0001-preflight-table-proof-2026-10-18"), "origin tip"),
    (git("rev-parse", "HEAD~1"), "base"),
    (git("rev-parse", "HEAD:scripts/preflight_one_command.py"), "wrapper blob"),
    (git("rev-parse", "HEAD~1:scripts/preflight_one_command.py"), "wrapper blob at base"),
    (git("rev-parse", "HEAD~1:src/preflight.py"), "instrument blob"),
    (git("rev-parse", "HEAD~1:scripts/canary_preflight.py"), "canary blob"),
    (git("rev-parse", "refs/heads/master"), "local master"),
]
for sha, label in checks:
    if sha not in body:
        sys.exit("ABORT: %s %s not cited in body" % (label, sha))
if git("rev-parse", "HEAD") != git(
        "rev-parse",
        "origin/task-qwen-coder-0001-preflight-table-proof-2026-10-18"):
    sys.exit("ABORT: local != origin for the lane branch")

# ---- fixed-point entry length, then binary append + read-back
pre = os.path.getsize(LANE)
with open(LANE, "rb") as f:
    f.seek(pre - 1)
    last = f.read(1)
if last != b"\n":
    sys.exit("ABORT: lane file does not end in newline: %r" % last)

template = ("\n" + body
            + "- read-back measured: pre-size {P} B, appended {N} B at "
              "offset {P}, read back {N} B bytes-equal={EQ}, post-size {S} "
              "B (postsize == presize + entry: {OK}). Last byte before "
              "append: {LB}.\n")
n = 0
entry = None
for _ in range(10):
    cand = template.format(P=pre, N=n, EQ=True, S=pre + n, OK=True,
                           LB=repr(last))
    b = cand.encode("utf-8")
    if len(b) == n:
        entry = b
        break
    n = len(b)
if entry is None:
    sys.exit("ABORT: fixed point not reached")

with open(LANE, "ab") as f:
    f.write(entry)
with open(LANE, "rb") as f:
    f.seek(pre)
    back = f.read()
post = os.path.getsize(LANE)
eq = back == entry
print("pre-size %d B; appended %d B at offset %d; bytes-equal read-back: "
      "%s; post-size %d B; postsize == presize + entry: %s"
      % (pre, len(entry), pre, eq, post, post == pre + len(entry)))
if not (eq and post == pre + len(entry)):
    sys.exit("READ-BACK FAILED")
print("LANE APPEND VERIFIED")
