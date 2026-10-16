"""TASK 0150 IDENTITY — 14 backup originals vs tracked counterparts at b1f290c84.

Prints and records NAMES, SIZES, SHA256s and one-word verdicts only.
File contents are never printed. Blob bytes are hashed in-process and discarded.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

WT = r"C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14"
BACKUP = os.path.join(WT, ".codex", "0110", "backup")
PIN = "b1f290c847eb2500b7eb39987ac34f6d6a8d00d2"
OUT_JSON = os.path.join(WT, ".codex", "0150", "identity_result.json")

# mutation-site suffix observed in 0110's backup names: .L1929 .L1933 .L56a .L56b
# .l186 .m1a .m1b .m2 .m3a .m3b .m5  (case varies)
MUT = re.compile(r"\.(?:[Ll]\d+[ab]?|m\d+[ab]?)$")


def git_env():
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_CONFIG_KEY") or k.startswith("GIT_CONFIG_VALUE"):
            env.pop(k)
    env.pop("GIT_CONFIG_COUNT", None)
    return env


def git(args):
    p = subprocess.run(["git", "-C", WT] + args, env=git_env(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("git %s failed rc=%d" % (args[0], p.returncode))
    return p.stdout


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def norm(data):
    return data.replace(b"\r\n", b"\n")


def main():
    files = sorted(f for f in os.listdir(BACKUP) if f.endswith(".orig"))
    all_entries = sorted(f for f in os.listdir(BACKUP) if os.path.isfile(os.path.join(BACKUP, f)))
    print("backup-dir=%s" % BACKUP)
    print("entries-total=%d  .orig-files=%d" % (len(all_entries), len(files)))
    if all_entries != files:
        print("WARNING non-.orig entries present: %s" %
              [f for f in all_entries if not f.endswith(".orig")])

    tracked = git(["ls-tree", "-r", "--name-only", PIN]).decode("utf-8", "replace").splitlines()
    by_base = {}
    for p in tracked:
        by_base.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    print("tracked-paths-at-%s=%d  distinct-basenames=%d" % (PIN[:9], len(tracked), len(by_base)))

    rows = []
    for name in files:
        path = os.path.join(BACKUP, name)
        with open(path, "rb") as fh:
            data = fh.read()
        base = name[:-len(".orig")]
        stripped_base = MUT.sub("", base)
        cands = sorted(by_base.get(stripped_base, []))
        raw, nrm = sha256_bytes(data), sha256_bytes(norm(data))
        row = {
            "name": name, "size": len(data), "raw_sha256": raw, "norm_sha256": nrm,
            "derived_base": stripped_base, "candidates": cands,
            "candidate_count": len(cands), "matches": [],
        }
        for c in cands:
            blob_sha = git(["rev-parse", "%s:%s" % (PIN, c)]).decode().strip()
            bdata = git(["cat-file", "blob", blob_sha])
            row["matches"].append({
                "path": c, "blob_sha": blob_sha,
                "raw_sha256": sha256_bytes(bdata), "norm_sha256": sha256_bytes(norm(bdata)),
            })
        ident = [m for m in row["matches"] if m["raw_sha256"] == raw]
        neq = [m for m in row["matches"] if m["norm_sha256"] == nrm and m["raw_sha256"] != raw]
        if not cands:
            row["verdict"] = "NO-TRACKED-COUNTERPART"
            row["note"] = ""
        elif ident:
            row["verdict"] = "IDENTICAL"
            row["note"] = "matched %s" % ident[0]["path"]
        elif neq:
            row["verdict"] = "DIFFERS"
            row["note"] = "normalised-equal (CRLF/LF only) vs %s" % neq[0]["path"]
        else:
            row["verdict"] = "DIFFERS"
            row["note"] = "differs from every candidate"
        rows.append(row)

    print()
    print("%-42s %8s  %-4s %-64s %s" % ("name", "size", "cand", "disk-sha256", "verdict"))
    for r in rows:
        print("%-42s %8d  %-4d %-64s %s" %
              (r["name"], r["size"], r["candidate_count"], r["raw_sha256"], r["verdict"]))
    print()
    for r in rows:
        if r["candidate_count"] != 1:
            print("CANDIDATE-NOTE %-42s count=%d paths=%s" %
                  (r["name"], r["candidate_count"], ",".join(r["candidates"]) or "(none)"))
        for m in r["matches"]:
            print("  MATCH %-42s <-> %-38s blob=%s raw-eq=%s norm-eq=%s" %
                  (r["name"], m["path"], m["blob_sha"][:12],
                   m["raw_sha256"] == r["raw_sha256"], m["norm_sha256"] == r["norm_sha256"]))
        if r["note"]:
            print("  NOTE %s : %s" % (r["name"], r["note"]))

    clusters = {}
    for r in rows:
        clusters.setdefault(r["raw_sha256"], []).append(r["name"])
    dups = {h: n for h, n in clusters.items() if len(n) > 1}
    print()
    print("distinct-byte-streams=%d of %d files; duplicate-clusters=%d" %
          (len(clusters), len(rows), len(dups)))
    for h, n in sorted(dups.items()):
        print("  CLUSTER %s : %s" % (h, ", ".join(sorted(n))))

    tallies = {}
    for r in rows:
        tallies[r["verdict"]] = tallies.get(r["verdict"], 0) + 1
    print()
    print("VERDICT-TALLIES %s  denominator=%d" % (tallies, len(rows)))

    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"pin": PIN, "rows": rows, "tallies": tallies,
                   "distinct_streams": len(clusters)}, fh, indent=1)
    print("wrote %s (%d B)" % (OUT_JSON, os.path.getsize(OUT_JSON)))


if __name__ == "__main__":
    sys.exit(main())
