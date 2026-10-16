# TASK-0140 -- stage 3: classify each of the 64 rows PROMOTABLE-IF-READ /
# UNKNOWN-STILL / EVIDENCE-CANNOT-EXIST against stage 2's resolved candidates,
# then write the deliverables resonate-ops\glm-0140\promotion-inventory.{md,json}.
#
# Verdict bar (settled in the lane entry design):
#   PROMOTABLE-IF-READ      >=1 candidate EXISTS, in scope (task-glob origin,
#                            task number in its name, or basename linkage to
#                            the row) and passes the need's capacity check:
#                            kill needs-names+signature: names >= stated N
#                            (else >=1) AND >=1 signature-vocab match;
#                            kill needs-signature:  >=1 signature match;
#                            survive: clearing-fact vocab AND basename linkage.
#   UNKNOWN-STILL           nothing capable, but either a named carrier is
#                            off limits by standing rule (pilotcaps lane's
#                            own worktree -- recorded by name, never opened),
#                            a named record-family carrier EXISTS with the
#                            need's vocabulary but cannot be scoped to the
#                            row (promotion needs a pointer, not a recording),
#                            or a named carrier is ABSENT by stat and of a
#                            carrier family (.out/.log/.json/.txt/.md/
#                            .jsonl/.csv, dir-like-with-a-number, date-named,
#                            or an unresolvable git sha).  NOT carrier
#                            families: api-route templates ({}), git refs
#                            (all-alpha like origin/master), trailing-
#                            separator prose fragments, source .py.
#   EVIDENCE-CANNOT-EXIST   nothing existing or named can carry it; the reason
#                            names the recording that would have to be made
#                            and by whom.
#   Priority: PROMOTABLE > UNKNOWN-STILL(off-limits) > UNKNOWN-STILL(unscoped
#             vocabulary) > UNKNOWN-STILL(absent) > EVIDENCE-CANNOT-EXIST.
#   Source files are never carriers: vocabulary in a .py is the word in code,
#   not a recorded failure (is_record_family).
# Controls: planted synthetic rows A (existing carrier -> PROMOTABLE) and
# B (nothing anywhere -> EVIDENCE-CANNOT-EXIST) run through the SAME
# classify_row on candidates measured by stage 2's own stat_token/capacity;
# plant C (named absent carrier -> UNKNOWN-STILL); known-answer arm reruns
# widen on the three certified SAFE flips.  Control lines print BEFORE the
# real 64.  Capacity prints counts/booleans only, never content.
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0080"))
sys.path.insert(0, os.path.join(CODEX, "0120"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import stage2_resolve as S2             # noqa: E402  (main() is guarded)
import extract_pilotcaps                # noqa: E402
from classify import classify_records   # noqa: E402
import run_0090                         # noqa: E402
import widen                            # noqa: E402

OPS = S2.OPS
OUT_DIR = os.path.join(OPS, "glm-0140")
os.makedirs(OUT_DIR, exist_ok=True)
OVERBROAD = {os.path.normcase(os.path.normpath(p))
             for p in (OPS, os.path.join(OPS, "logs"),
                       os.path.join(OPS, "queue"),
                       os.path.join(OPS, "pilotcaps"))}
CARRIER_EXT = {".out", ".log", ".json", ".txt", ".md", ".jsonl", ".csv",
               ".html"}

rows = json.load(open(os.path.join(HERE, "resolve.json"),
                      encoding="utf-8"))
CORPUS_SHA = json.load(open(os.path.join(HERE, "rows64.json"),
                            encoding="utf-8"))["corpus_sha256"]


def in_scope(c, row):
    if c["origin"] == "task-glob":
        return True
    base = os.path.basename(str(c.get("path") or c["token"])).lower()
    task = row["entry"]["task"]
    if task and (task in base or task.lstrip("0") in base):
        return True
    cap = c.get("capacity")
    return bool(cap and cap.get("link"))


def is_record_family(path):
    """A single-file carrier must be a record, not source code: vocabulary
    in a .py is the word in code, not a recorded failure."""
    if os.path.isdir(path):
        return True
    return os.path.splitext(path)[1].lower() in CARRIER_EXT


def capable(c, row):
    if c["kind"] != "path" or c["status"] != "EXISTS":
        return False
    if os.path.normcase(os.path.normpath(c["path"])) in OVERBROAD:
        return False
    if not is_record_family(c["path"]):
        return False
    if not in_scope(c, row):
        return False
    cap = c["capacity"] or {}
    need = row["need"]
    n = max(row["stated_counts"]) if row.get("stated_counts") else 1
    if need == "kill:needs-names+signature":
        return cap.get("names", 0) >= n and bool(cap.get("sigs"))
    if need == "kill:needs-signature":
        return bool(cap.get("sigs"))
    if need == "survive:needs-clearing-fact":
        return bool(cap.get("clearing")) and bool(cap.get("link"))
    return False


def plausible_named_absent(cands):
    for c in cands:
        if c.get("origin") != "named":
            continue
        if c["kind"] == "git" and c["status"] == "ABSENT":
            return c
        if c["kind"] == "path" and c["status"] == "ABSENT":
            tok = c["token"]
            p = str(c.get("path") or tok)
            if "temp\\nowhere" in p.lower():
                continue                      # prose brake path, not a carrier
            if "{" in tok or "}" in tok:
                continue                      # api route template, not a file
            if tok.endswith(("/", "\\")):
                continue                      # prose fragment ("...under X\\")
            ext = os.path.splitext(tok)[1].lower()
            if ext in CARRIER_EXT:
                return c
            if re.search(r'[\\/]', tok) and not ext:
                if re.search(r'\d', tok):
                    return c                  # dir-like named path with a
                                              # task/date number (glm/0055)
                continue                      # all-alpha: a ref (origin/master)
            if re.match(r'^[A-Za-z0-9]+-[A-Za-z0-9-]+\d{4}', tok):
                return c                      # date-named run dir
    return None


def unscoped_vocab_named(row):
    """Named, EXISTS, record-family, not over-broad, carrying the need's
    VOCABULARY but failing only the scoping rule: the evidence may be in
    there and promotion needs a pointer, not a recording."""
    need = row["need"]
    for c in row["cands"]:
        if (c.get("origin") != "named" or c["kind"] != "path"
                or c["status"] != "EXISTS" or not c.get("capacity")):
            continue
        if os.path.normcase(os.path.normpath(c["path"])) in OVERBROAD:
            continue
        if not is_record_family(c["path"]):
            continue
        cap = c["capacity"]
        hit = cap.get("sigs") if need.startswith("kill:") else \
            cap.get("clearing")
        if hit:
            return c
    return None


def offlimits_named(cands):
    for c in cands:
        if (c.get("origin") == "named" and c["kind"] == "path"
                and c["status"] == "OFF-LIMITS"):
            p = str(c.get("path") or "")
            if "temp\\nowhere" not in p.lower():
                return c
    return None


def classify_row(row):
    """Same code path for the planted controls and the real 64."""
    need = row["need"]
    task = row["entry"]["task"]
    n = max(row["stated_counts"]) if row.get("stated_counts") else None
    for c in row["cands"]:
        if capable(c, row):
            cap = c["capacity"]
            why = ("carrier EXISTS and passes the capacity bar for %s "
                   "(names=%d%s, sigs=%s, clearing=%s, link=%s; in scope: %s)"
                   % (need, cap.get("names", 0),
                      ">=%d" % (n or 1), ",".join(cap.get("sigs", [])) or "-",
                      ",".join(cap.get("clearing", [])) or "-",
                      ",".join(cap.get("link", [])) or "-",
                      c["origin"]))
            return {"verdict": "PROMOTABLE-IF-READ", "carrier": c, "why": why}
    ol = offlimits_named(row["cands"])
    if ol is not None:
        return {"verdict": "UNKNOWN-STILL",
                "carrier": ol,
                "why": ("named carrier is the pilotcaps lane's own worktree "
                        "(off limits to this lane by standing rule; directory "
                        "entry never opened) -- a pilotcaps brief may read it")}
    uv = unscoped_vocab_named(row)
    if uv is not None:
        cap = uv["capacity"]
        return {"verdict": "UNKNOWN-STILL", "carrier": uv,
                "why": ("named carrier EXISTS with the need's vocabulary "
                        "(%s) but is not scoped to this row -- not "
                        "task-numbered, not basename-linked; promotion needs "
                        "a pointer into it, not a recording"
                        % (",".join(cap.get("sigs", []) or
                                    cap.get("clearing", []))))}
    ab = plausible_named_absent(row["cands"])
    if ab is not None:
        return {"verdict": "UNKNOWN-STILL", "carrier": ab,
                "why": "named carrier ABSENT by stat: %s -- no existing "
                       "artefact passes the capacity bar for %s" %
                       (ab["token"] if ab["kind"] == "path" else
                        "git sha " + ab["token"], need)}
    if need == "survive:needs-clearing-fact":
        rec = ("record a clearing fact for the row's mutated file (size-change"
               " claim / whole-second recompile / pyc precaution / load-proof"
               " CLEAN) tied to the file the row names")
    elif need == "kill:needs-signature":
        rec = ("re-run the kill battery capturing the failure-signature lines"
               " for the tests the row already names%s"
               % (" (count certification N=%d)" % n if n else ""))
    else:
        rec = ("re-run the kill battery recording the killed test names AND "
               "their failure-signature lines%s"
               % (" (count certification N=%d)" % n if n else ""))
    return {"verdict": "EVIDENCE-CANNOT-EXIST", "carrier": None,
            "why": ("no existing or named artefact can carry %s; the recording"
                    " needed: %s" % (need, rec)), "recording": rec}


# ---- known-answer arm: the three certified SAFE flips must reproduce -------
text = open(run_0090.LANE_PILOTCAPS, "rb").read().decode("utf-8")
recs, _ = extract_pilotcaps.parse(text)
cls = classify_records(recs)
kept = [r for r in cls if r["line"] not in run_0090.EXCLUSIONS]
wide = {w["line"]: w for w in widen.widen_corpus(kept, text)}
ka_lines = []
for ln in (10480, 15382, 16148):
    w = wide[ln]
    ka_lines.append("known-answer L%-6d strict=%-7s wide=%-7s %s" % (
        ln, w["strict"], w["wide"],
        "REPRODUCED" if (w["strict"] == "UNKNOWN" and w["wide"] == "SAFE")
        else "DRIFT"))

# ---- planted controls --------------------------------------------------------
CTRL_DIR = os.path.join(HERE, "controls")
os.makedirs(CTRL_DIR, exist_ok=True)
FIXTURE = os.path.join(CTRL_DIR, "synthetic_carrier_a.txt")
open(FIXTURE, "w", encoding="utf-8").write(
    "synthetic control fixture A -- TASK-0140 classifier both-answer arm\n"
    "test_synthetic_kill_row_alpha ... FAIL\n"
    "    AssertionError: synthetic control A expected the refusal\n"
    "test_synthetic_kill_row_beta ... FAIL\n"
    "    AssertionError: synthetic control A expected the second refusal\n")
plant_a_row = {
    "line": 0, "need": "kill:needs-names+signature", "stated_counts": [2],
    "entry": {"task": "synthetic"},
    "cands": [], "row_toks": {"synthetic_carrier_a",
                              "test_synthetic_kill_row_alpha",
                              "test_synthetic_kill_row_beta"}}
status, path, st, cap = S2.stat_token(FIXTURE, plant_a_row["row_toks"])
plant_a_row["cands"] = [{"kind": "path", "token": FIXTURE, "status": status,
                         "path": path, "stat": st, "capacity": cap,
                         "origin": "named"}]
plant_b_row = {"line": 0, "need": "kill:needs-names+signature",
               "stated_counts": [2], "entry": {"task": "synthetic"},
               "cands": []}
plant_c_row = {"line": 0, "need": "kill:needs-signature", "stated_counts": [],
               "entry": {"task": "synthetic"},
               "cands": [{"kind": "path",
                          "token": "controls\\named_but_missing_recording.json",
                          "status": "ABSENT", "path": os.path.join(
                              CTRL_DIR, "named_but_missing_recording.json"),
                          "stat": None, "capacity": None,
                          "origin": "named"}]}
ctrl_lines = []
for tag, row, expect in (
        ("A", plant_a_row, "PROMOTABLE-IF-READ"),
        ("B", plant_b_row, "EVIDENCE-CANNOT-EXIST"),
        ("C", plant_c_row, "UNKNOWN-STILL")):
    v = classify_row(row)
    ok = v["verdict"] == expect
    ctrl_lines.append("[CONTROL-%s] expect=%-22s got=%-22s %s | %s" % (
        tag, expect, v["verdict"], "PASS" if ok else "FAIL", v["why"][:120]))

# ---- the real 64 -------------------------------------------------------------
out_rows = []
for r in rows:
    v = classify_row(r)
    rec_id = None
    if v["verdict"] == "PROMOTABLE-IF-READ":
        action = "read %s (EXISTS, %d B) -- no new recording needed" % (
            os.path.relpath(v["carrier"]["path"], OPS),
            v["carrier"]["stat"]["size"])
        rec_id = "read-" + r["entry"]["task"]
    elif v["verdict"] == "UNKNOWN-STILL" and "off limits" in v["why"]:
        action = ("read the own-worktree artefact %s and record what it "
                  "carries for rows of task %s -- maker: pilotcaps brief "
                  "dispatched into that worktree (the glm lane may not open it)"
                  % (v["carrier"].get("path") or v["carrier"]["token"],
                     r["entry"]["task"]))
        rec_id = "worktree-" + r["entry"]["task"]
    elif v["verdict"] == "UNKNOWN-STILL" and "needs a pointer" in v["why"]:
        action = ("point a reader into %s (EXISTS with the need's vocabulary "
                  "but unscoped): record where in it the rows of task %s "
                  "live, or excerpt them into the lane entry -- maker: "
                  "pilotcaps lane (revived watcher) or an operator-dispatched "
                  "brief" % (os.path.relpath(v["carrier"]["path"], OPS),
                             r["entry"]["task"]))
        rec_id = "pointer-" + r["entry"]["task"]
    elif v["verdict"] == "UNKNOWN-STILL":
        action = ("recover or recreate %s (ABSENT by stat; carrier family "
                  "token) for rows of task %s -- maker: operator with the "
                  "remote (git sha), or pilotcaps lane for a named file"
                  % (v["carrier"]["token"], r["entry"]["task"]))
        rec_id = "recover-" + r["entry"]["task"]
    else:
        action = v["recording"] + " -- maker: pilotcaps lane (revived watcher)"\
            " or an operator-dispatched brief with pilotcaps scope; rows of "\
            "task " + r["entry"]["task"]
        rec_id = "record-" + r["entry"]["task"] + "-" + r["need"][:6]
    out_rows.append({"line": r["line"], "task": r["entry"]["task"],
                     "need": r["need"],
                     "stated_counts": r.get("stated_counts") or [],
                     "verdict": v["verdict"],
                     "carrier": (None if v["carrier"] is None else {
                         "kind": v["carrier"]["kind"],
                         "token": v["carrier"]["token"],
                         "status": v["carrier"]["status"],
                         "path": os.path.relpath(
                             v["carrier"]["path"], OPS).replace("\\", "/")
                         if v["carrier"].get("path") else None,
                         "size": (v["carrier"].get("stat") or {}).get("size"),
                         "capacity": v["carrier"].get("capacity")}),
                     "why": v["why"], "recording_id": rec_id,
                     "recording": action})

# ---- consolidate recordings --------------------------------------------------
recordings = {}
for o in out_rows:
    e = recordings.setdefault(o["recording_id"],
                              {"id": o["recording_id"], "tasks": set(),
                               "rows": [], "action": o["recording"]})
    e["tasks"].add(o["task"])
    e["rows"].append(o["line"])
for e in recordings.values():
    e["tasks"] = sorted(e["tasks"])
    e["rows"] = sorted(e["rows"])

order = {"PROMOTABLE-IF-READ": 0, "UNKNOWN-STILL": 1,
         "EVIDENCE-CANNOT-EXIST": 2}
out_rows.sort(key=lambda o: (order[o["verdict"]], o["line"]))
tally = {k: sum(1 for o in out_rows if o["verdict"] == k)
         for k in order}
recordings = sorted(recordings.values(),
                    key=lambda e: (0 if e["id"].startswith("read-") else
                                   1 if e["id"].startswith("pointer-") else
                                   2 if e["id"].startswith("worktree-") else
                                   3 if e["id"].startswith("recover-") else 4,
                                   e["id"]))

# ---- write deliverables --------------------------------------------------------
payload = {
    "task": "TASK 0140",
    "generated": "2026-10-17",
    "denominator": len(out_rows),
    "corpus": {"path": "resonate-ops/LANE-pilotcaps.md",
               "sha256": CORPUS_SHA,
               "certification": "0120 gates re-run PASS at be6ed8b21 "
                                "machinery (kept 82; strict 14/67/1; "
                                "unknown67 widened 3/64/0)"},
    "premise_correction": "table_result.json holds counts and the 3 flips "
                          "only; the 64 row IDs were re-derived by script "
                          "(.codex/0140/dump_64.py) and gated on all four "
                          "certified tallies",
    "controls": {"planted": ctrl_lines, "known_answer": ka_lines},
    "verdicts": tally,
    "capacity_method": "script only; per artefact <=300 files, <=4 MB/file; "
                       "counts and vocabulary booleans only, no content; "
                       "logs\\*.out checked counts-only (rule 7 tension "
                       "recorded in the lane entry)",
    "rows": out_rows,
    "recordings": recordings,
}
json_path = os.path.join(OUT_DIR, "promotion-inventory.json")
json.dump(payload, open(json_path, "w", encoding="utf-8"), indent=1)

md = []
md.append("# TASK 0140 -- promotion inventory for the 64 evidence-absent "
          "UNKNOWN rows\n")
md.append("Corpus: `resonate-ops/LANE-pilotcaps.md` sha256 `%s`; the 64 rows "
          "re-derived by script from the certified 0120 pipeline (all four "
          "gates PASS). %s\n" % (CORPUS_SHA, payload["premise_correction"]))
md.append("## Controls (planted both-answer arm + known-answer arm)\n")
for ln in ctrl_lines + ka_lines:
    md.append("> " + ln)
md.append("")
md.append("## Verdicts (denominator %d)\n" % len(out_rows))
for k in ("PROMOTABLE-IF-READ", "UNKNOWN-STILL", "EVIDENCE-CANNOT-EXIST"):
    md.append("- %s: %d/%d" % (k, tally[k], len(out_rows)))
md.append("")
md.append("## Per-row table\n")
md.append("| line | task | need | verdict | carrier |")
md.append("|---|---|---|---|---|")
for o in out_rows:
    c = o["carrier"]
    if c is None:
        carrier = "-none-"
    else:
        carrier = "%s `%s`" % (c["status"],
                               (c.get("path") or c["token"]).replace("\\",
                                                                     "/"))
    md.append("| L%d | %s | %s | %s | %s |" % (
        o["line"], o["task"], o["need"].split(":")[1], o["verdict"], carrier))
md.append("")
md.append("## The recordings a future pilotcaps brief must make\n")
md.append("Ordered: read-only promotions first (no recording), then "
          "pointers into existing unscoped carriers, then worktree reads, "
          "then recoveries, then new recordings.\n")
for e in recordings:
    md.append("### %s -- tasks %s, rows %s\n" % (
        e["id"], ",".join(e["tasks"]), ",".join("L%d" % x
                                                for x in e["rows"])))
    md.append(e["action"] + "\n")
md.append("## Method notes\n")
md.append(payload["capacity_method"] + ". Off-limits guard: work/, other "
          "lanes' worktrees, the main checkout and .codex/config.toml were "
          "never opened; an off-limits worktree named by an entry counts as "
          "UNKNOWN-STILL, decided on the directory entry only.")
md_path = os.path.join(OUT_DIR, "promotion-inventory.md")
open(md_path, "w", encoding="utf-8").write("\n".join(md) + "\n")

# ---- printout: controls BEFORE the real 64 ------------------------------------
print("== controls ==")
for ln in ctrl_lines + ka_lines:
    print(ln)
print("\n== the 64 ==")
for o in out_rows:
    c = o["carrier"]
    carr = ("-" if c is None else "%s %s" % (
        c["status"], (c.get("path") or c["token"]).replace("\\", "/")))
    print("L%-6d t=%-5s %-24s %-22s %s" % (
        o["line"], o["task"], o["need"], o["verdict"], carr))
print("\nverdicts: %s (denominator %d)" % (tally, len(out_rows)))
print("recordings consolidated: %d" % len(recordings))
for p in (json_path, md_path):
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    print("sha256 %s %s %d B" % (p, h, os.path.getsize(p)))
