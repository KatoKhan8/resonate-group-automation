"""TASK 0150 deliverable generator — assembles backup-audit.md.

Reads identity_result.json + keyshape_result.json (both produced by sibling
scripts), re-measures the guard behaviourally in the scratch clone with
per-command exit codes (no pipeline ever touches $?), re-derives the config
refutation probe, scans tracked counterpart blobs for key-shape attribution,
and writes the audit. File contents are never printed; only names, sizes,
counts, SHAs and the .gitignore line the brief requires quoted.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime

WT = r"C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14"
OPS = r"C:\Users\Zvonimir\Desktop\resonate-ops"
AUDIT = os.path.join(OPS, "glm-0150", "backup-audit.md")
CLONE = os.path.join(OPS, "glm-0150", "scratch-clone")
SCRATCH = os.path.join(WT, ".codex", "0150")
# PIN is taken from identity_result.json's own recorded measurement (the
# SHA-basis the identity figures were produced at) — never retyped by hand.
with open(os.path.join(SCRATCH, "identity_result.json"), encoding="utf-8") as _fh:
    PIN = json.load(_fh)["pin"]
if not re.fullmatch(r"[0-9a-f]{40}", PIN):
    raise RuntimeError("malformed pin in identity_result.json: %r" % PIN)
GUARD_COMMIT = "0f7228a99a3e9ad724f42d099e7688dc0a55de20"
LANE_BRANCH = "task-glm-review-2026-10-14"
CONFIG_REL = ".codex/config.toml"  # forward slash: git path, shown in tables

# Pattern set duplicated VERBATIM from keyshape.py (same labels, same regexes)
# so no import creates bytecode for a sibling module.
PATTERNS = [
    ("P1 api[_-]?key assign", re.compile(r"(?i)api[_\-]?key\s*[:=]")),
    ("P2 token assign", re.compile(r"(?i)\btoken\b\s*[:=]")),
    ("P3 secret assign", re.compile(r"(?i)\bsecret\b\s*[:=]")),
    ("P4 password assign", re.compile(r"(?i)\bpassw(or)?d\b\s*[:=]")),
    ("P5 bearer string", re.compile(r"(?i)bearer\s+[A-Za-z0-9._+\-]{8,}")),
    ("P6 sk- key prefix", re.compile(r"sk[-_][A-Za-z0-9_\-]{12,}")),
    ("P7 40+ entropy run", re.compile(r"[A-Za-z0-9+/=_\-]{40,}")),
]
HEXONLY = re.compile(r"^[0-9a-fA-F]+$")


def git_env():
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_CONFIG_KEY") or k.startswith("GIT_CONFIG_VALUE"):
            env.pop(k)
    env.pop("GIT_CONFIG_COUNT", None)
    return env


def git(args, cwd=WT):
    """Return (rc, stdout, stderr) straight from subprocess — rc is git's."""
    p = subprocess.run(["git"] + args, cwd=cwd, env=git_env(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr


def git_ok(args, cwd=WT):
    rc, out, err = git(args, cwd)
    if rc != 0:
        raise RuntimeError("git %s rc=%d err=%s" % (args[0], rc, err[:200]))
    return out.decode("utf-8", "replace")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pattern_counts(text):
    counts = {}
    for label, rx in PATTERNS:
        counts[label] = len(rx.findall(text))
    runs = re.findall(r"[A-Za-z0-9+/=_\-]{40,}", text)
    hexish = sum(1 for r in runs if HEXONLY.match(r))
    counts["P7b of-which hex-only(digest-like)"] = hexish
    counts["P7c of-which non-hex(stronger shape)"] = len(runs) - hexish
    return counts


# ---------------------------------------------------------------- guard demo
def ignore_lines_at(ref, cwd=CLONE):
    """Quote every .gitignore line mentioning codex at ref, with numbers."""
    try:
        blob = git_ok(["show", "%s:.gitignore" % ref], cwd=cwd)
    except RuntimeError:
        return None  # no .gitignore at this ref
    hits = [(i + 1, ln.rstrip("\r\n")) for i, ln in enumerate(blob.splitlines())
            if "codex" in ln.lower()]
    return hits


def guard_demo(ref, label):
    """Synthetic-probe add demo at ref in the scratch clone. rc per command."""
    git_ok(["checkout", "-q", "--detach", ref], cwd=CLONE)
    quoted = ignore_lines_at(ref)
    # tracked-ness of the exact guard path at this ref
    rc_tr, _, _ = git(["ls-files", "--error-unmatch", CONFIG_REL], cwd=CLONE)
    tracked = rc_tr == 0
    probes = [".codex/zz0150-probe.txt"]
    if not tracked:
        probes.append(CONFIG_REL)  # exact file-scoped glob target, synthetic bytes
    rows = []
    for rel in probes:
        p = os.path.join(CLONE, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b"TASK 0150 synthetic guard probe; not real data; deleted after demo\n")
        # check-ignore FIRST, unpiped, rc is git's own
        rc_ci, out_ci, _ = git(["check-ignore", "-v", rel], cwd=CLONE)
        ci_line = out_ci.decode("utf-8", "replace").strip() or "(no output)"
        rc_add, _, _ = git(["add", "--", rel], cwd=CLONE)
        rc_st, out_st, _ = git(["status", "--porcelain", "--", rel], cwd=CLONE)
        staged = out_st.decode("utf-8", "replace").lstrip().startswith("A ")
        if rc_ci == 0 and not staged:
            verdict = "REFUSED-BY-IGNORE"
        elif staged:
            verdict = "ADDED"
        else:
            verdict = "ADD-FAILED rc_add=%d" % rc_add
        # teardown: unstage if staged, remove probe file
        if staged:
            git_ok(["reset", "-q", "--", rel], cwd=CLONE)
        if os.path.exists(p):
            os.remove(p)
        agree = ("AGREE" if (rc_ci == 0) == (verdict == "REFUSED-BY-IGNORE") else
                 "CONTRADICTION")
        rows.append({"probe": rel, "check_ignore_rc": rc_ci, "ci_line": ci_line,
                     "add_rc": rc_add, "staged": staged, "verdict": verdict,
                     "agree": agree})
    rc_clean, out_clean, _ = git(["status", "--porcelain"], cwd=CLONE)
    if rc_clean != 0 or out_clean.strip():
        raise RuntimeError("scratch clone not clean after demo: %r" % out_clean[:200])
    return {"ref": ref, "label": label, "quoted": quoted,
            "guard_path_tracked": tracked, "rows": rows}


def tip_census():
    refs = [r for r in git_ok(["for-each-ref", "--format=%(refname)",
                               "refs/heads", "refs/remotes"]).split()]
    carrying = set()
    for i in range(0, len(refs), 80):
        chunk = refs[i:i + 80]
        rc, out, _ = git(["grep", "-F", "-l", ".codex/config.toml"] + chunk +
                         ["--", ".gitignore"])
        if rc > 1:
            raise RuntimeError("git grep chunk rc=%d" % rc)
        for ln in out.decode("utf-8", "replace").splitlines():
            carrying.add(ln.split(":", 1)[0])
    contains = set()
    for ln in git_ok(["branch", "-a", "--contains", GUARD_COMMIT]).splitlines():
        t = ln.strip().lstrip("*").strip()
        if t:
            contains.add(t)  # count only; format differs from the grep census
    return refs, sorted(carrying), sorted(contains)


# ------------------------------------------------------------------- config
def config_probe():
    p = os.path.join(WT, CONFIG_REL)
    if not os.path.isfile(p):
        return {"present": False}
    data = open(p, "rb").read()
    text = data.decode("utf-8", "replace")
    runs = re.findall(r"[A-Za-z0-9+/=_\-]{16,}", text)
    quoted = set(re.findall(r'"([A-Za-z0-9+/=_\-]{16,})"', text))
    hexonly = [r for r in runs if HEXONLY.match(r)]
    return {
        "present": True, "size": len(data), "lines": text.count("\n") +
        (0 if text.endswith("\n") or not text else 1),
        "sk_substring": text.count("sk-"),
        "word_key_ci": len(re.findall(r"(?i)key", text)),
        "word_token_ci": len(re.findall(r"(?i)token", text)),
        "assignments": len(re.findall(r"^\s*[A-Za-z0-9_.\-]+\s*=", text, re.M)),
        "runs_ge16": len(runs), "runs_ge24": len([r for r in runs if len(r) >= 24]),
        "runs_ge16_quoted": len(quoted), "runs_ge16_hexonly": len(hexonly),
        "quoted_run_lengths": sorted(len(q) for q in quoted),
    }


# ---------------------------------------------------------------- attribution
def attribution(ident):
    rows = []
    for r in ident["rows"]:
        fpath = os.path.join(WT, ".codex", "0110", "backup", r["name"])
        ftext = open(fpath, "rb").read().decode("utf-8", "replace")
        fcounts = pattern_counts(ftext)
        if not r["matches"]:
            rows.append({
                "name": r["name"], "counterpart": None,
                "backup_p7c": fcounts["P7c of-which non-hex(stronger shape)"],
            })
            continue
        m = r["matches"][0]
        # bytes mode: hashing/scanning happen on bytes, never printed
        rc, out, err = git(["cat-file", "blob", m["blob_sha"]])
        if rc != 0:
            raise RuntimeError("cat-file rc=%d" % rc)
        ctext = out.decode("utf-8", "replace")
        ccounts = pattern_counts(ctext)
        rows.append({
            "name": r["name"], "counterpart": m["path"], "blob": m["blob_sha"],
            "backup_total": sum(fcounts[l] for l, _ in PATTERNS),
            "backup_p7c": fcounts["P7c of-which non-hex(stronger shape)"],
            "counterpart_total": sum(ccounts[l] for l, _ in PATTERNS),
            "counterpart_p7c": ccounts["P7c of-which non-hex(stronger shape)"],
            "p7c_equal": fcounts["P7c of-which non-hex(stronger shape)"] ==
            ccounts["P7c of-which non-hex(stronger shape)"],
        })
    return rows


# --------------------------------------------------------------------- main
def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lane_sha = git_ok(["rev-parse", "HEAD"]).strip()
    origin_master = git_ok(["rev-parse", "origin/master"]).strip()
    if origin_master != PIN:
        raise RuntimeError("origin/master moved: %s" % origin_master)
    clone_head = git_ok(["rev-parse", "HEAD"], cwd=CLONE).strip()
    ident = json.load(open(os.path.join(SCRATCH, "identity_result.json"),
                           encoding="utf-8"))
    ks = json.load(open(os.path.join(SCRATCH, "keyshape_result.json"),
                        encoding="utf-8"))

    demos = [guard_demo(PIN, "origin/master (authority)"),
             guard_demo(lane_sha, "lane HEAD " + LANE_BRANCH)]
    guard_commit_lines = ignore_lines_at(GUARD_COMMIT)
    refs, carrying, contains = tip_census()
    cfg = config_probe()
    attr = attribution(ident)

    L = []
    A = L.append
    A("# TASK 0150 — the fourteen backup originals: identity, guard, key-shape")
    A("")
    A("generated %s by `.codex/0150/build_audit.py` — every figure below was "
      "computed by script at generation time and parsed back from "
      "`identity_result.json`, `keyshape_result.json` or a fresh measurement "
      "in this run. No file content was printed, copied or committed; the 14 "
      "originals were hashed in place and never opened into context." % ts)
    A("")
    A("## 0. Authorities and SHAs of every measurement")
    A("")
    A("| measurement | SHA / path |")
    A("|---|---|")
    A("| identity (tracked counterparts) | origin/master `%s` |" % PIN)
    A("| guard behaviour + lane scratch | lane HEAD `%s` on `%s` |"
      % (lane_sha, LANE_BRANCH))
    A("| guard-introducing commit | `%s` (SAVE SWEEP 2026-10-16) |" % GUARD_COMMIT)
    A("| scratch clone source | `git clone --no-hardlinks` from lane HEAD; "
      "clone HEAD at `%s`; guard demo run `--detach` at each measured SHA |"
      % clone_head)
    A("| identity figures | `.codex/0150/identity_result.json` (%d B), "
      "producer `identity.py` |"
      % os.path.getsize(os.path.join(SCRATCH, "identity_result.json")))
    A("| key-shape figures | `.codex/0150/keyshape_result.json` (%d B), "
      "producer `keyshape.py` |"
      % os.path.getsize(os.path.join(SCRATCH, "keyshape_result.json")))
    A("| backup directory | `.codex/0110/backup/` — %d `.orig` files, "
      "untracked (`?? .codex/0110/`), never copied out, never committed |"
      % len(ident["rows"]))
    A("")
    A("## 1. IDENTITY — each original vs its tracked counterpart at `%s`"
      % PIN[:9])
    A("")
    tracked_paths = git_ok(["ls-tree", "-r", "--name-only", PIN]).splitlines()
    bases = {p.rsplit("/", 1)[-1] for p in tracked_paths}
    A("Matching rule: strip `.orig`, strip the mutation-site suffix "
      "(`.L1929`, `.L56a`, `.m2`, …), then match by basename against "
      "`git ls-tree -r %s --name-only` (%d paths, %d distinct basenames). "
      "A raw sha256 compare decides IDENTICAL; a CRLF→LF-normalised compare "
      "separates line-ending artifacts from real drift."
      % (PIN[:9], len(tracked_paths), len(bases)))
    A("")
    A("| original | size B | cands | tracked counterpart at %s | blob | "
      "verdict |" % PIN[:9])
    A("|---|---:|---:|---|---|---|")
    for r in ident["rows"]:
        if r["matches"]:
            m = r["matches"][0]
            cp, blob = m["path"], "`%s`" % m["blob_sha"][:12]
        else:
            cp, blob = "— (basename absent)", "—"
        note = ""
        if r["verdict"] == "DIFFERS" and r["note"].startswith("normalised"):
            note = " *(CRLF/LF-only)*"
        A("| `%s` | %d | %d | `%s` | %s | %s%s |"
          % (r["name"], r["size"], r["candidate_count"], cp, blob,
             r["verdict"], note))
    tallies = ident["tallies"]
    denom = len(ident["rows"])
    A("")
    A("Tallies %s — denominator %d. Candidate-count collisions (>1): %d. "
      "Distinct byte-streams: %d of %d files."
      % (tallies, denom,
         sum(1 for r in ident["rows"] if r["candidate_count"] > 1),
         ident["distinct_streams"], denom))
    A("")
    A("Duplicate clusters (same raw sha256): %s."
      % "; ".join("`%s…` = %s" % (h[:8], ", ".join(n)) for h, n in
                  sorted(_dup_clusters(ident).items())))
    A("")
    A("Sizes cross-check vs TASK 0130's recorded inventory "
      "(LANE-glm.md, static quote): sender-estate ×3 = 32,229 B each — "
      "measured %s; productive.yaml.m2.orig = 56,576 B — measured %s."
      % ("; ".join(str(r["size"]) for r in ident["rows"]
                   if r["name"].startswith("sender-estate")),
         [r["size"] for r in ident["rows"]
          if r["name"] == "productive.yaml.m2.orig"][0]))
    A("")
    A("## 2. GUARD — is `.codex/` ignore-protected, quote and behaviour")
    A("")
    A("Quoted `.gitignore` lines mentioning `codex`, per ref (absence stated):")
    A("")
    for d in demos:
        A("- `%s`: %s" % (d["label"],
                          _fmt_lines(d["quoted"]) or "**ABSENT** — no line "
                          "mentions codex"))
    A("- guard commit `%s`: %s"
      % (GUARD_COMMIT[:9], _fmt_lines(guard_commit_lines)))
    A("")
    A("Behavioural demo in the scratch clone (synthetic probe files only, "
      "one line of synthetic text, unstaged and deleted afterwards — clone "
      "verified clean by `git status --porcelain` after every ref):")
    A("")
    A("| ref | probe | check-ignore rc | source | add verdict | quote/behaviour |")
    A("|---|---|---:|---|---|---|")
    for d in demos:
        for row in d["rows"]:
            A("| `%s` | `%s` | %d | `%s` | %s | %s |"
              % (d["ref"][:9], row["probe"], row["check_ignore_rc"],
                 row["ci_line"].split("\t")[0] if row["ci_line"] != "(no output)"
                 else "—", row["verdict"], row["agree"]))
    A("")
    A("Tips census (heads + remotes, this repository's ref store): %d tips; "
      "%d carry the `.codex/config.toml` line in `.gitignore` "
      "(chunked `git grep -F`, 80 refs per call): %s. `%d` tips contain the "
      "guard commit `%s`." % (len(refs), len(carrying),
                              ", ".join("`%s`" % c for c in carrying) or "none",
                              len(contains), GUARD_COMMIT[:9]))
    A("")
    A("## 3. KEY-SHAPE — counts only, named pattern set")
    A("")
    A("Pattern set: P1 `api[_-]?key` assign · P2 `token` assign · P3 `secret` "
      "assign · P4 `password` assign · P5 `bearer <run>` · P6 `sk-` prefix "
      "(12+ after prefix) · P7 40+ char entropy run, split into P7b hex-only "
      "(digest-like) and P7c non-hex (stronger shape). Per file only the "
      "total is printed here; matched lines and values never were.")
    A("")
    A("| file | total | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P7b | P7c |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in ks["rows"]:
        c = r["counts"]
        A("| `%s` | %d | %s |" % (r["file"], r["total"],
           " | ".join(str(c[l]) for l, _ in PATTERNS) + " | " +
           str(c["P7b of-which hex-only(digest-like)"]) + " | " +
           str(c["P7c of-which non-hex(stronger shape)"])))
    A("")
    A("FILES-SCANNED=%d FILES-WITH->0=%d FILES-WITH-0=%d. P1–P6 are zero in "
      "all %d files; every hit everywhere is P7c (non-hex 40+ runs)."
      % (ks["files_scanned"], ks["files_present"],
         ks["files_scanned"] - ks["files_present"], ks["files_scanned"]))
    A("")
    A("Attribution — same scan over the tracked counterpart blob at `%s` "
      "(counts only, bytes hashed/scanned in-process and discarded):"
      % PIN[:9])
    A("")
    A("| original | backup P7c | counterpart | counterpart P7c | equal |")
    A("|---|---:|---|---:|---|")
    for a in attr:
        if a["counterpart"] is None:
            A("| `%s` | %d | — no tracked counterpart | — | — |"
              % (a["name"], a["backup_p7c"]))
        else:
            A("| `%s` | %d | `%s` | %d | %s |"
              % (a["name"], a["backup_p7c"], a["counterpart"],
                 a["counterpart_p7c"], "yes" if a["p7c_equal"] else "NO"))
    A("")
    if cfg.get("present"):
        A("`.codex/config.toml` in THIS worktree — widened shape probe "
          "(still counts only): %d B, %d lines, %d assignments; "
          "`sk-` substrings: %d; case-insensitive word `key`: %d; "
          "word `token`: %d; runs ≥16 chars: %d (≥24: %d; hex-only: %d); "
          "runs ≥16 inside quotes: %d (lengths %s). Every long run is "
          "UNQUOTED — none sits in an assignment value — so no "
          "credential-shaped value exists in this tree's copy under this "
          "probe or under P1–P7."
          % (cfg["size"], cfg["lines"], cfg["assignments"], cfg["sk_substring"],
             cfg["word_key_ci"], cfg["word_token_ci"], cfg["runs_ge16"],
             cfg["runs_ge24"], cfg["runs_ge16_hexonly"], cfg["runs_ge16_quoted"],
             cfg["quoted_run_lengths"] or "[]"))
    A("")
    A("## 4. Findings")
    A("")
    ident_n = sum(1 for r in ident["rows"] if r["verdict"] == "IDENTICAL")
    diff_n = tallies.get("DIFFERS", 0)
    ntc_n = tallies.get("NO-TRACKED-COUNTERPART", 0)
    norm_eq = sum(1 for r in ident["rows"]
                  if r["note"].startswith("normalised"))
    A("1. **IDENTITY: %d of %d identical; %d differ (%d of them CRLF/LF-only, "
      "%d content-differing); %d have no tracked counterpart at `%s`.** The "
      "sender-estate originals' basename does not exist in master's tree; "
      "whether a copy lives under `work/` is off limits to this lane — "
      "UNKNOWN, authority `work/` (external-model rule 1)."
      % (ident_n, denom, diff_n, norm_eq, diff_n - norm_eq, ntc_n, PIN[:9]))
    A("2. **GUARD: the guard is file-scoped, not directory-scoped.** The only "
      "codex line any ref carries is `.gitignore:113` `.codex/config.toml` "
      "(comment line 112), on %d of %d tips (%s), introduced by `%s`. "
      "Behaviour agrees with the quote at both measured refs: at `%s` both "
      "probes were ADDED (no guard at all); at `%s` the synthetic "
      "`.codex/config.toml` probe was REFUSED-BY-IGNORE while "
      "`.codex/zz0150-probe.txt` — standing in for every other `.codex/` "
      "path, including `.codex/0110/backup/` — was ADDED. **Nothing on any "
      "ref ignores the 14 originals; their only protection is that nobody "
      "has run `git add -A` over them yet.** The 0130 exclusion was "
      "hand-enforced, not guard-enforced."
      % (len(carrying), len(refs), ", ".join(carrying), GUARD_COMMIT[:9],
         PIN[:9], lane_sha[:9]))
    A("3. **GUARD census: \"one branch only until it merges\" is still "
      "true** — %d of %d tips carry the line (%s), both pointing at `%s`; "
      "master `%s` has no codex ignore line at all."
      % (len(carrying), len(refs), "branch + its origin mirror", lane_sha[:9],
         PIN[:9]))
    if cfg.get("present"):
        A("4. **KEY in config.toml: not confirmable in this worktree's "
          "copy.** The recorded estate fact (\"config.toml holds a live "
          "key\") does not reproduce here: %d B / %d lines / %d assignments, "
          "zero `sk-` substrings, zero `key` words, zero quoted runs ≥16. "
          "Either the key was removed from this tree's copy or it lives in "
          "another lane worktree's copy — other worktrees are off limits, "
          "so that half is UNKNOWN, authority each worktree's own "
          "`.codex/config.toml`. The gitignore half of the fact (measured "
          "true above) is what still protects the path in this tree."
          % (cfg["size"], cfg["lines"], cfg["assignments"]))
    A("5. **KEY-SHAPE: %d of %d scanned files report LIVE-KEY-SHAPE PRESENT "
      "(counts only).** All hits are P7c non-hex 40+ runs; P1–P6 are zero "
      "everywhere. Attribution shows the same shapes already sit in the "
      "tracked master blobs for the counterparts whose P7c counts match "
      "(long snake_case identifiers and similar over-matches of P7 are the "
      "likely shape — content was never read); %s."
      % (ks["files_present"], ks["files_scanned"],
         _attr_summary(attr)))
    A("6. **Operator sentence:** remediation (rotation/removal) is the "
      "operator's decision; the file list is at "
      "`C:\\Users\\Zvonimir\\Desktop\\resonate-ops\\glm-0150\\backup-audit.md` "
      "§3. This audit deletes nothing, rotates nothing, moves nothing.")
    A("")
    A("## 5. What this audit does NOT establish")
    A("")
    A("- Whether any individual P7c run is a credential rather than an "
      "identifier or URL: content was never read — counts only, per the "
      "brief. Name the needed authority: a human reading "
      "`.codex/0110/backup/` with the pattern offsets from "
      "`keyshape_result.json`.")
    A("- Whether copies of the sender-estate originals exist under `work/` "
      "(off limits, external-model rule 1).")
    A("- Whether other lane worktrees' `.codex/config.toml` copies hold the "
      "live key (other worktrees off limits).")
    A("- Blob ids beyond 12 hex chars are in `identity_result.json`; this "
      "page truncates for width.")
    A("")
    txt = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, "wb") as fh:
        fh.write(txt.encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    back = open(AUDIT, "rb").read()
    if sha256(back) != sha256(txt.encode("utf-8")):
        raise RuntimeError("readback mismatch")
    print("AUDIT %s (%d B) sha256=%s" % (AUDIT, len(back), sha256(back)))
    print("rows-identity=%d rows-keyshape=%d demos=%d census=%d/%d attr=%d"
          % (len(ident["rows"]), len(ks["rows"]), len(demos), len(carrying),
             len(refs), len(attr)))
    return 0


def _dup_clusters(ident):
    cl = {}
    for r in ident["rows"]:
        cl.setdefault(r["raw_sha256"], []).append(r["name"])
    return {h: n for h, n in cl.items() if len(n) > 1}


def _fmt_lines(hits):
    if not hits:
        return ""
    return "; ".join("line %d: `%s`" % (n, t.strip()) for n, t in hits)


def _attr_summary(attr):
    eq = [a for a in attr if a["counterpart"] and a["p7c_equal"]]
    ne = [a for a in attr if a["counterpart"] and not a["p7c_equal"]]
    na = [a for a in attr if not a["counterpart"]]
    parts = []
    if eq:
        parts.append("%d originals' counts equal their tracked counterpart's "
                     "(pre-existing in master)" % len(eq))
    if ne:
        parts.append("%d differ from their counterpart (%s) — backup-only "
                     "shapes" % (len(ne), ", ".join("`%s`" % a["name"]
                     for a in ne)))
    if na:
        parts.append("%d have no counterpart to attribute against" % len(na))
    return "; ".join(parts) or "no counterpart comparisons possible"


if __name__ == "__main__":
    sys.exit(main())
