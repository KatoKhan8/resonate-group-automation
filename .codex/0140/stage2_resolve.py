# TASK-0140 -- stage 2: resolve, per row of the 64, every artefact that could
# carry the row's missing evidence, stat it, and measure (counts only, never
# content) whether it COULD carry that evidence.
#   candidates per row:
#     (a) references in the row span + W1 block (0120's own evidence blocks)
#     (b) references in the owning TASK entry: its head, its `### Artefacts`
#         sections, and backticked/absolute path tokens anywhere in it
#     (c) task-number globs over resonate-ops\ and resonate-ops\logs\
#     (d) basename search under resonate-ops for every named token
#     (e) git SHAs named near the row, resolved in THIS worktree's git
#   capacity (script only): distinct test_ names, which signature vocab
#   matched, which clearing-fact vocab matched, basename linkage, json keys.
# OFF-LIMITS guard: anything under work/, any other worktree, the main
# checkout, or .codex/config.toml is never opened -- recorded by name only.
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0120"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import run_0090                          # noqa: E402
import widen                             # noqa: E402  for NAME_W / _counts_of
import extract_pilotcaps as _ep          # noqa: E402  for the vocabularies

OPS = r"C:\Users\Zvonimir\Desktop\resonate-ops"
LANE = run_0090.LANE_PILOTCAPS
FORBIDDEN_ROOTS = [
    r"C:\Users\Zvonimir\Desktop\resonate-group-automation",   # main checkout
    r"C:\Users\Zvonimir\Desktop\wt-pilotcaps-2026-10-14",
    r"C:\Users\Zvonimir\Desktop\wt-glm-b-2026-10-14",
    r"C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14",
    r"C:\Users\Zvonimir\Desktop\wt-suppression-2026-10-14",
    r"C:\Users\Zvonimir\Desktop\wt-webapp-2026-10-14",
]
MAX_FILE = 4 << 20          # per-file read cap for capacity checks
MAX_DIR_FILES = 300
MAX_ENTRY_TOKENS = 16

HDR_TASK = re.compile(r'^#{1,6} .*TASK[ -]?(\d{2,4}[a-z]?)(?![0-9])', re.I)
ABS_PATH = re.compile(r'[A-Za-z]:\\[^\s`)\]\|,"\'{]+')
TICK = re.compile(r'`([^`\n]{2,120})`')
TICK_PATHISH = re.compile(r'[\\/]|^\w[\w.-]*\.(py|json|md|out|txt|log|jsonl)$',
                          re.I)
SHA = re.compile(r'^[0-9a-f]{7,40}$')

def off_limits(p):
    p = os.path.normpath(p)
    if p.endswith(".codex\\config.toml") or p.endswith(".codex/config.toml"):
        return True
    for root in FORBIDDEN_ROOTS:
        if p.startswith(root):
            return True
    parts = p.lower().split("\\")
    return "work" in parts      # any work/ directory, any tree

# ---- one basename index over resonate-ops (depth<=3, dirs only + files) ----
BASENAME_INDEX = {}
for dirpath, dirnames, filenames in os.walk(OPS):
    rel = os.path.relpath(dirpath, OPS)
    depth = 0 if rel == "." else rel.count("\\") + 1
    dirnames[:] = [d for d in dirnames if d != ".git"]
    if depth >= 3:
        dirnames[:] = []
    for f in filenames:
        BASENAME_INDEX.setdefault(f.lower(), []).append(
            os.path.join(dirpath, f))
    if depth >= 2:                      # index dir names too (TASK-0248 etc.)
        for d in dirnames:
            BASENAME_INDEX.setdefault(d.lower(), []).append(
                os.path.join(dirpath, d))

def by_basename(tok):
    base = os.path.basename(tok.replace("/", "\\")).lower()
    if not base or base in (".git",):
        return []
    hits = BASENAME_INDEX.get(base, [])
    return [h for h in hits if not off_limits(h)][:4]

def task_globs(num):
    out = []
    for pat in ("TASK-%s*" % num, "pilotcaps-%s*" % num.lstrip("0"),
                "pilotcaps-*-%s*" % num.lstrip("0"), "scratch-%s*" % num,
                "*%s*" % num):
        out += [p for p in glob.glob(os.path.join(OPS, pat))
                if not off_limits(p)]
        out += [p for p in glob.glob(os.path.join(OPS, "logs", pat))
                if not off_limits(p)]
    seen, ded = set(), []
    for p in out:
        if p.lower() not in seen:
            seen.add(p.lower())
            ded.append(p)
    return ded[:6]

def capacity(path, row_tokens=()):
    """Counts-only check that `path` could carry a row's evidence."""
    row_tokens = {t.lower() for t in row_tokens}
    res = {"names": 0, "sigs": [], "clearing": [], "link": [], "json": None,
           "files": 0, "bytes_read": 0}
    files = []
    if os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in (".git",
                                                            "__pycache__")]
            for f in filenames:
                files.append(os.path.join(dirpath, f))
            if len(files) >= MAX_DIR_FILES:
                break
    else:
        files = [path]
    res["files"] = len(files)
    for fp in files[:MAX_DIR_FILES]:
        try:
            if os.path.getsize(fp) > MAX_FILE:
                continue
            raw = open(fp, "rb").read()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue                       # binary: cannot carry text evidence
        try:
            txt = raw.decode("utf-8", errors="replace")
        except Exception:
            continue
        res["bytes_read"] += len(raw)
        base = os.path.basename(fp).lower()
        stem = base.rsplit(".", 1)[0]
        if (base in row_tokens or stem in row_tokens) and base not in \
                res["link"]:
            res["link"].append(base)
        res["names"] += len(set(widen.NAME_W.findall(txt)))
        res["sigs"] += [n for n, p in _ep.SIGNATURES if p.search(txt)
                        and n not in res["sigs"]]
        for label, p in (("size-change", _ep.SIZE_CHANGE_CLAIM),
                         ("whole-second", _ep.SECOND_CLEARING),
                         ("pyc-precaution", _ep.PYC_PRECAUTION),
                         ("load-proof", _ep.LOADPROOF_CLEAR)):
            if p.search(txt) and label not in res["clearing"]:
                res["clearing"].append(label)
        if fp.lower().endswith(".json") and res["json"] is None:
            try:
                j = json.loads(txt)
                if isinstance(j, dict):
                    res["json"] = sorted(j.keys())[:12]
                elif isinstance(j, list):
                    res["json"] = ["<list:%d>" % len(j)]
            except Exception:
                res["json"] = ["<unparsed>"]
    res["sigs"] = res["sigs"][:6]
    return res

def stat_token(tok, row_tokens=()):
    """Resolve one named token to (status, path, stat, capacity)."""
    cands = []
    if re.match(r'^[A-Za-z]:\\', tok):
        cands.append(tok.rstrip('.,;:'))
    elif TICK_PATHISH.search(tok):
        for root in (OPS, os.path.join(OPS, "logs")):
            p = os.path.join(root, tok.lstrip(".\\/"))
            cands.append(p)
        cands += by_basename(tok)
    for p in cands:
        p = os.path.normpath(p)
        if off_limits(p):
            return ("OFF-LIMITS", p, None, None)
        if os.path.exists(p):
            st = os.stat(p)
            return ("EXISTS", p, {"size": st.st_size,
                                   "mtime": int(st.st_mtime)},
                    capacity(p, row_tokens))
    return ("ABSENT", cands[0] if cands else tok, None, None)

def git_check(sha):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_CONFIG"):
            del env[k]
    try:
        t = subprocess.run(["git", "cat-file", "-t", sha], cwd=HERE,
                           capture_output=True, text=True, timeout=30,
                           env=env).stdout.strip()
    except Exception:
        return ("ABSENT", None)
    if t not in ("commit", "blob", "tree", "tag"):
        return ("ABSENT", None)
    if t != "commit":
        return ("EXISTS", {"type": t})
    out = subprocess.run(["git", "show", "--name-only", "--format=", sha],
                         cwd=HERE, capture_output=True, text=True, timeout=60,
                         env=env).stdout
    paths = [x for x in out.splitlines() if x.strip()]
    return ("EXISTS", {"type": "commit", "files": len(paths),
                       "test_files": sum(1 for x in paths
                                         if x.startswith("tests/"))})

# ---- entry map -------------------------------------------------------------
text = open(LANE, "rb").read().decode("utf-8")
lines = [ln.rstrip("\r") for ln in text.split("\n")]
hdrs = []
for i, ln in enumerate(lines):
    m = HDR_TASK.match(ln)
    if m:
        hdrs.append((i + 1, m.group(1).lower(), ln[:90]))

def entry_of(ln):
    best = None
    for h_ln, num, txt in hdrs:
        if h_ln <= ln:
            best = (h_ln, num, txt)
        else:
            break
    return best

def artefacts_sections(entry_ln, next_ln):
    """(start, end) line ranges of `### Artefacts` sections in an entry."""
    out, k = [], entry_ln
    while k < min(next_ln, len(lines)):
        if lines[k - 1].startswith("### Artefacts"):
            e = k
            while e < next_ln and not re.match(r'^#{1,3} ', lines[e]):
                e += 1
            out.append((k, e))
            k = e
        else:
            k += 1
    return out

def main():
    rows = json.load(open(os.path.join(HERE, "rows64.json"),
                          encoding="utf-8"))["rows"]
    result = []
    for r in rows:
        ln = r["line"]
        ent = entry_of(ln)
        ent_ln, task_num, ent_txt = ent if ent else (0, "?", "(none)")
        nxt = next((h for h, n, t in hdrs if h > ent_ln), len(lines))
        # tokens: row+block, entry head (25 lines), Artefacts sections
        zones = []
        span = lines[ln - 1:r["end_line"]]
        blk = [lines[n - 1] for n in r["block"]]
        zones.append("\n".join(span + blk))
        zones.append("\n".join(lines[ent_ln - 1:ent_ln - 1 + 25]))
        for a, b in artefacts_sections(ent_ln, nxt):
            zones.append("\n".join(lines[a - 1:b]))
        toks = []
        for z in zones:
            for m in ABS_PATH.finditer(z):
                toks.append(m.group(0).rstrip('.,;:'))
            for m in TICK.finditer(z):
                t = m.group(1).strip()
                if TICK_PATHISH.search(t):
                    toks.append(t)
                elif SHA.match(t):
                    toks.append("sha:" + t)
        seen, ordered = set(), []
        for t in toks:
            if t.lower() not in seen:
                seen.add(t.lower())
                ordered.append(t)
        ordered = ordered[:MAX_ENTRY_TOKENS]

        cands = []
        row_toks = set(re.findall(r'[A-Za-z0-9_.\-]{4,}',
                                  "\n".join(span) + "\n" + "\n".join(blk)))
        for t in ordered:
            if t.startswith("sha:"):
                status, info = git_check(t[4:])
                cands.append({"kind": "git", "token": t[4:], "status": status,
                              "stat": info, "capacity": None,
                              "origin": "named"})
            else:
                status, path, st, cap = stat_token(t, row_toks)
                cands.append({"kind": "path", "token": t, "status": status,
                              "path": path, "stat": st, "capacity": cap,
                              "origin": "named"})
        for p in task_globs(task_num):
            st = os.stat(p)
            cands.append({"kind": "path", "token": os.path.relpath(p, OPS),
                          "status": "EXISTS", "path": p,
                          "stat": {"size": st.st_size,
                                   "mtime": int(st.st_mtime)},
                          "capacity": capacity(p, row_toks),
                          "origin": "task-glob"})
        # stated count over row+block (W2a form), for the capacity bar
        rb = "\n".join(span + blk)
        r["stated_counts"] = sorted(set(widen._counts_of(rb)))
        r["entry"] = {"line": ent_ln, "task": task_num, "header": ent_txt}
        r["cands"] = cands
        result.append(r)

    json.dump(result, open(os.path.join(HERE, "resolve.json"), "w",
                           encoding="utf-8"), indent=1)

    # ---- compact printout ----------------------------------------------------
    stat_counts = {}
    for r in result:
        for c in r["cands"]:
            key = (c["kind"], c["status"])
            stat_counts[key] = stat_counts.get(key, 0) + 1
    print("entry/task map (64 rows -> distinct entries):")
    tasks = {}
    for r in result:
        tasks.setdefault(r["entry"]["task"], []).append(r["line"])
    for t in sorted(tasks):
        print("  task %-6s rows %s" % (t, ",".join(str(x) for x in tasks[t])))
    print("\ncandidate token status census: %s" % stat_counts)
    rows_with_existing = sum(1 for r in result
                             if any(c["status"] == "EXISTS"
                                    for c in r["cands"]))
    rows_with_named_absent = sum(
        1 for r in result if any(c["status"] == "ABSENT"
                                 and c["origin"] == "named"
                                 for c in r["cands"]))
    print("rows with >=1 EXISTS candidate: %d/64" % rows_with_existing)
    print("rows with >=1 named-ABSENT token: %d/64" % rows_with_named_absent)
    print("\nper-row candidate summary (statuses + capacity counts):")
    for r in result:
        cs = []
        for c in r["cands"][:5]:
            if c["status"] == "EXISTS" and c["kind"] == "path":
                cap = c["capacity"]
                cs.append("E[%s n=%d sig=%s clr=%s]" % (
                    os.path.basename(c["path"])[:24], cap["names"],
                    ",".join(cap["sigs"])[:24] or "-",
                    ",".join(cap["clearing"])[:20] or "-"))
            elif c["status"] == "EXISTS":
                cs.append("E[git %s]" % c["stat"])
            else:
                cs.append("%s[%s]" % (c["status"][:4],
                                      os.path.basename(str(c.get("path")
                                                           or c["token"]))
                                      [:24]))
        print("L%-6d t=%-5s %-24s cnt=%-6s %s" % (
            r["line"], r["entry"]["task"], r["need"],
            r["stated_counts"] or "-", " ".join(cs) or "(no candidates)"))


if __name__ == "__main__":
    main()
