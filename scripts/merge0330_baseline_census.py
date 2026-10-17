#!/usr/bin/env python3
"""TASK merge/0330 - ref-by-carrier census for `.github/` and `BASELINE_MODE`.

The question this answers, in one sentence: which refs carry `.github/`, which
of those declare `BASELINE_MODE` and with what value, and which carriers are
descendants of `origin/master` `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`.

Why it exists. merge/0300's F3 finding was that the claim "`BASELINE_MODE`
stays untouched" is VACUOUS: there is no `.github/` at `00da12331` or at
`origin/master`, so nothing observable could have changed either way, and the
only carrier ever found was one branch. A safety claim that nothing can
falsify is not a safety claim. This turns it into a census with a denominator.

WHAT IT MEASURES, per ref, and the authority for each field
----------------------------------------------------------
(a) `.github/` exists at the ref's tip          `git ls-tree` on the tip tree
(b) a `BASELINE_MODE` occurrence in any bounded  `git cat-file --batch` over
    blob, where "bounded" is EXACTLY:            blob contents, deduped by
      - every blob under `.github/**`            blob sha
      - `scripts/ci_suite.py`
      - `scripts/provenance_report.py`
    Never a whole-tree grep. The bound is the point: this is a content search
    scoped to the three places a `BASELINE_MODE` could actually be read from.
(c) descendant of the base commit                `git merge-base --is-ancestor`
                                                 per unique tip, cross-checked
                                                 against a children-map walk of
                                                 `git rev-list --all --parents`

Read-only. It resolves no ref, checks out nothing, writes no repository state.
Output paths are explicit and required; nothing is written implicitly.

Denominator discipline: every ref `git for-each-ref` lists is walked and every
one appears in the output. A ref that cannot be read is `UNKNOWN` with the
reason, and is never dropped and never counted clean.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys

BASE_DEFAULT = "b1f290c847eb2500b7eb39987ac34f6d6a8d00d2"

# The bounded search set. `.github` is a whole subtree; the two scripts are
# single paths. Nothing else is read.
GITHUB_DIR = ".github"
BOUNDED_BLOBS = ("scripts/ci_suite.py", "scripts/provenance_report.py")
BOUNDED_PATHS = (GITHUB_DIR,) + BOUNDED_BLOBS

TOKEN = b"BASELINE_MODE"

# A "declaration" is the token in a position where a value is assigned to it.
# A bare mention in prose (`# see BASELINE_MODE above`) is recorded separately,
# because conflating the two is exactly how a report overstates a carrier.
DECL_SEPARATORS = (":", "=")


def _utcnow() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env() -> dict:
    """Environment for git, with the GIT_CONFIG_* family removed.

    A lane shell carries GIT_CONFIG_COUNT / GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n
    (and sometimes an empty GIT_CONFIG_SYSTEM), which make git read config from
    nowhere or from a file that is not there. Every measurement in this repo
    that went quietly wrong on config went wrong here, so it is cleared once,
    centrally, rather than remembered per call site. Nothing else is touched and
    no value is ever printed.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}


def git(repo: str, args, data: str | None = None) -> bytes:
    """Run one git command from `repo`. Bytes out, so no decoding guess."""
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=repo,
        env=_env(),
        input=None if data is None else data.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "git %s failed rc=%d: %s"
            % (" ".join(args), proc.returncode, proc.stderr.decode("utf-8", "replace").strip()[:400])
        )
    return proc.stdout


def git_rc(repo: str, args) -> int:
    """Run one git command and return ONLY its exit code.

    `merge-base --is-ancestor` speaks in exit codes - 0 yes, 1 no, 128 error -
    and collapsing 1 into 128 would turn "not an ancestor" into "could not
    read", which is the one confusion this census exists to prevent. So the
    three states are kept apart.
    """
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=repo,
        env=_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode


def parse_refs(raw: bytes):
    """`for-each-ref` -> one row per ref. This is the denominator."""
    fmt = "%(refname)%09%(objectname)%09%(objecttype)%09%(creatordate:iso-strict)%09%(*objectname)%09%(*objecttype)"
    rows = []
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        while len(parts) < 6:
            parts.append("")
        rows.append(
            {
                "refname": parts[0],
                "objectname": parts[1],
                "objecttype": parts[2],
                "creatordate": parts[3],
                "peeled": parts[4],
                "peeled_type": parts[5],
            }
        )
    # A second, independent read of the same listing: the format above is one
    # command and a parsing slip in it would silently shrink the denominator.
    # The count comes from a separate `--format=%(refname)` invocation.
    return rows


def resolve_tips(refs):
    """Give every ref a commit tip, or an UNKNOWN reason. Never drop one."""
    tips = {}
    for r in refs:
        ref = r["refname"]
        if r["objecttype"] == "commit":
            tips[ref] = (r["objectname"], "commit", "")
        elif r["objecttype"] == "tag":
            if r["peeled_type"] == "commit" and r["peeled"]:
                tips[ref] = (r["peeled"], "tag->commit", "")
            else:
                tips[ref] = (
                    None,
                    "tag",
                    "annotated tag does not peel to a commit (peeled type %r)" % (r["peeled_type"] or "unknown"),
                )
        else:
            tips[ref] = (
                None,
                r["objecttype"],
                "ref points at a %s, not a commit; no tree to list" % (r["objecttype"] or "unknown"),
            )
    return tips


def batch_check(repo: str, tips):
    """One process: which bounded paths exist at each unique tip, and as what.

    `cat-file --batch-check` takes arbitrary `<rev>:<path>` object expressions,
    so all ~6000 lookups happen in a single git invocation instead of 6000.

    THE TRAP, MEASURED. The obvious reading of the output is that the first
    field echoes the query, so `expr.partition(":")` recovers the tip and the
    path. It does not. For an expression that RESOLVES, git prints the resolved
    OBJECT ID; only an expression that does not resolve is echoed verbatim:

        cc112ae60:.github            -> 5402ec32e85f... tree 82      <- the tree's id
        cc112ae60:no/such/path       -> cc112ae60:no/such/path missing <- the query

    Keying on that field therefore files every present path under its own blob
    or tree sha and every lookup by tip misses - which is how the first run of
    this census reported 0 positives while an independent `ls-tree` sweep found
    37 tips with a `.github`. So the answer is taken from POSITION, not from the
    echoed name: the batch interface emits exactly one line per input line, in
    input order. The line count is asserted, so a short or long answer is a
    refusal rather than a quietly shortened map.
    """
    unique = sorted({t[0] for t in tips.values() if t[0]})
    exprs = []
    for sha in unique:
        for p in BOUNDED_PATHS:
            exprs.append("%s:%s" % (sha, p))
    out = git(repo, ["cat-file", "--batch-check"], "\n".join(exprs) + "\n")
    lines = [l for l in out.decode("utf-8", "replace").split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) != len(exprs):
        raise RuntimeError(
            "cat-file --batch-check answered %d lines for %d expressions; positional "
            "parsing is unsafe, so this is a refusal and not a map" % (len(lines), len(exprs))
        )

    found = {}
    echoed_name_differs = 0
    for expr, line in zip(exprs, lines):
        sha, _, path = expr.partition(":")
        bits = line.split(" ")
        if len(bits) >= 2 and bits[1] != "missing":
            found[(sha, path)] = (bits[1], int(bits[2]) if len(bits) > 2 and bits[2].isdigit() else 0)
            if bits[0] != expr:
                echoed_name_differs += 1
        else:
            found[(sha, path)] = None
    return unique, found, echoed_name_differs


def list_github_trees(repo: str, tree_shas):
    """`git ls-tree -r` each unique `.github` tree once.

    Deduped by tree sha because 2557 refs share a handful of trees, and the
    listing is the authority for what is *inside* `.github` - including the
    case where a blob is literally named `.github` and is not a directory.
    """
    blobs = {}
    problems = {}
    for sha in tree_shas:
        out = git(repo, ["ls-tree", "-r", "-z", sha])
        entries = []
        for chunk in out.split(b"\x00"):
            if not chunk:
                continue
            meta, _, path = chunk.partition(b"\t")
            fields = meta.decode("utf-8", "replace").split()
            if len(fields) != 3:
                problems.setdefault(sha, []).append("unparseable ls-tree entry %r" % meta)
                continue
            mode, otype, osha = fields
            path = path.decode("utf-8", "replace")
            entries.append((path, otype, osha, mode))
            if otype == "commit":
                # A gitlink: a submodule. Its contents are not in this object
                # store, so the census cannot read them and says so rather than
                # reading the empty directory and calling it clean.
                problems.setdefault(sha, []).append("gitlink (submodule) at %s" % path)
        blobs[sha] = entries
    return blobs, problems


def read_blobs(repo: str, blob_shas):
    """One process: the content of every unique bounded blob."""
    shas = sorted(blob_shas)
    if not shas:
        return {}
    out = git(repo, ["cat-file", "--batch"], "\n".join(shas) + "\n")
    contents = {}
    pos = 0
    for sha in shas:
        nl = out.find(b"\n", pos)
        if nl < 0:
            break
        header = out[pos:nl].decode("utf-8", "replace").split()
        pos = nl + 1
        if len(header) != 3:
            contents[sha] = None
            continue
        size = int(header[2])
        contents[sha] = out[pos : pos + size]
        pos += size + 1
    return contents


def classify_blob(content: bytes):
    """Occurrences of BASELINE_MODE, in three kinds that are not the same claim.

    A `BASELINE_MODE: report` line inside a `#` comment is prose ABOUT the
    setting; it is not the setting. The workflow file at the only carrier found
    so far contains both - an uncommented `BASELINE_MODE: report` under `env:`
    and a commented paragraph discussing it - so a census that counts the token
    alone would report the same number for a file that merely talks about the
    mode as for one that sets it. Both are therefore counted, separately:

        declaration          token followed by `:`/`=`, on a non-comment line
        comment_declaration  token followed by `:`/`=`, on a `#` comment line
        mention              token with no separator after it
    """
    declarations, comment_declarations = [], []
    mentions = 0
    occurrences = 0
    for raw in content.split(b"\n"):
        line = raw.rstrip(b"\r").decode("utf-8", "replace")
        is_comment = line.lstrip()[:1] == "#"
        idx = 0
        while True:
            at = line.find("BASELINE_MODE", idx)
            if at < 0:
                break
            occurrences += 1
            idx = at + len("BASELINE_MODE")
            rest = line[idx:].lstrip()
            if rest[:1] in DECL_SEPARATORS:
                # The value is the first token after the separator, so a prose
                # line that happens to fit the shape yields its first word
                # rather than a whole sentence, and the two readings stay
                # comparable.
                tail = rest[1:].strip().split("#")[0].strip()
                value = tail.split()[0] if tail.split() else "<empty>"
                entry = "BASELINE_MODE%s %s" % (rest[0], value)
                (comment_declarations if is_comment else declarations).append(entry)
            else:
                mentions += 1
    return occurrences, sorted(set(declarations)), sorted(set(comment_declarations)), mentions


def grep_control(repo: str, unique_tips):
    """Independent differential for (b): git's OWN content search, same bound.

    The census reads blobs and searches them itself, which means a bug in its
    own reader is indistinguishable from a real absence. `git grep` is a
    different implementation of the same question over the same three paths, so
    running both and diffing IN BOTH DIRECTIONS is a real control: a carrier the
    census missed fails one way, an invented carrier fails the other.

    Exit codes are the answer - 0 matched, 1 did not, anything else is an error -
    and they are kept apart, because "git could not read this tip" and "this tip
    does not carry the token" are different claims.
    """
    hits = {}
    for sha in unique_tips:
        rc = git_rc(repo, ["grep", "-l", "-F", TOKEN.decode(), sha, "--",
                           GITHUB_DIR] + list(BOUNDED_BLOBS))
        if rc == 0:
            hits[sha] = "yes"
        elif rc == 1:
            hits[sha] = "no"
        else:
            hits[sha] = "UNKNOWN(rc=%d)" % rc
    return hits


def descendants_of(repo: str, base: str):
    """Commits having `base` as an ancestor, by walking children once.

    `rev-list --all --parents` is a single process for the whole graph (9858
    commits here); the forward walk from `base` then answers the question for
    every tip at once. This is the CROSS-CHECK, not the authority - the
    authority is `merge-base --is-ancestor`, run per tip below, and any
    disagreement between the two is printed as a finding.
    """
    out = git(repo, ["rev-list", "--all", "--parents"])
    children = collections.defaultdict(list)
    known = set()
    for line in out.decode("utf-8", "replace").split("\n"):
        bits = line.split()
        if not bits:
            continue
        known.add(bits[0])
        for parent in bits[1:]:
            children[parent].append(bits[0])
    if base not in known:
        return None, known
    seen = set()
    stack = [base]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(children.get(cur, ()))
    return seen, known


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="absolute path to the worktree to read (read-only)")
    ap.add_argument("--base", default=BASE_DEFAULT, help="the commit to test ancestry against")
    ap.add_argument("--out-tsv", required=True, help="where the full per-ref map goes")
    ap.add_argument("--out-json", required=True, help="where the summary goes")
    ap.add_argument("--no-ancestor-subprocess", action="store_true",
                    help="skip the per-tip `merge-base --is-ancestor` pass (cross-check only)")
    ap.add_argument("--control-grep", action="store_true",
                    help="also run the independent `git grep` differential for (b)")
    args = ap.parse_args()

    if not args.repo:
        # A falsy root must never fall through to the environment's idea of a
        # repository: an empty string would resolve against cwd and measure a
        # different tree while looking like it measured this one.
        print("FATAL: --repo must be a non-empty absolute path", file=sys.stderr)
        return 2
    repo = os.path.abspath(args.repo)
    # The denominator is a live listing, and this repository gains refs while
    # the census runs - measured 2026-10-17: 2557 refs at first contact, 2560 by
    # the time the parser was finished. So the instant of the listing is part of
    # the measurement, not decoration.
    measured_at = _utcnow()

    raw = git(repo, [
        "for-each-ref",
        "--format=%(refname)%09%(objectname)%09%(objecttype)%09%(creatordate:iso-strict)%09%(*objectname)%09%(*objecttype)",
    ])
    refs = parse_refs(raw)
    # Independent second read of the listing: if these disagree, the parse above
    # lost rows and every count below is against the wrong denominator.
    refnames_second = [
        l for l in git(repo, ["for-each-ref", "--format=%(refname)"]).decode("utf-8", "replace").split("\n") if l.strip()
    ]
    denominator_reads = {"formatted_multi_field": len(refs), "refname_only": len(refnames_second)}
    denominator_agrees = len(refs) == len(refnames_second) and sorted(r["refname"] for r in refs) == sorted(refnames_second)

    tips = resolve_tips(refs)

    unique_tips, found, echoed_name_differs = batch_check(repo, tips)

    # --- (a) `.github/` at the tip -----------------------------------------
    # `.github` exists at a tip when the object store resolves `<tip>:.github`
    # to something. It counts as a DIRECTORY only when that something is a tree;
    # a blob named `.github` is not a directory and is reported UNKNOWN rather
    # than folded into the "has .github/" count.
    github_by_tip = {sha: found[(sha, GITHUB_DIR)] for (sha, path) in found if path == GITHUB_DIR and found[(sha, path)]}
    have_github = sorted(sha for sha, info in github_by_tip.items() if info[0] == "tree")
    # The tree object id, needed to enumerate contents. One call per unique tip
    # that has a `.github` tree, which is a small set.
    tree_of = {}
    for sha in have_github:
        out = git(repo, ["rev-parse", "%s:%s" % (sha, GITHUB_DIR)])
        tree_of[sha] = out.decode("utf-8", "replace").strip()

    # A control on the (a) authority itself. `ls-tree` IS the authority the
    # brief names; the batch-check resolution above is the fast path, so every
    # tip is checked in BOTH directions against ls-tree:
    #   positive - a tip the fast path called a tree must ls-tree to exactly
    #              one entry, of type tree, with the same object id;
    #   negative - a tip the fast path called missing must ls-tree to NOTHING.
    # The negative direction is run over every such tip, not a sample: a fast
    # path that invents a `.github` and one that loses one fail in opposite
    # directions and only the complete sweep catches the second.
    ls_tree_agreement = {"positive_checked": 0, "positive_agree": 0,
                         "negative_checked": 0, "negative_agree": 0, "disagree": []}
    for sha in have_github:
        out = git(repo, ["ls-tree", sha, "--", GITHUB_DIR]).decode("utf-8", "replace").strip()
        lines = [l for l in out.split("\n") if l.strip()]
        ls_tree_agreement["positive_checked"] += 1
        if len(lines) == 1 and lines[0].split()[1] == "tree" and lines[0].split()[2] == tree_of[sha]:
            ls_tree_agreement["positive_agree"] += 1
        else:
            ls_tree_agreement["disagree"].append({"tip": sha, "direction": "positive", "ls_tree": out})
    for sha in unique_tips:
        if sha in github_by_tip:
            continue
        out = git(repo, ["ls-tree", sha, "--", GITHUB_DIR]).decode("utf-8", "replace").strip()
        ls_tree_agreement["negative_checked"] += 1
        if out == "":
            ls_tree_agreement["negative_agree"] += 1
        else:
            ls_tree_agreement["disagree"].append({"tip": sha, "direction": "negative", "ls_tree": out})

    tree_blobs, tree_problems = list_github_trees(repo, sorted(set(tree_of.values())))

    # --- (b) BASELINE_MODE in the bounded set -------------------------------
    blob_roles = collections.defaultdict(set)  # blob sha -> {role}
    for sha, tree in tree_of.items():
        for path, otype, osha, mode in tree_blobs.get(tree, []):
            if otype == "blob":
                blob_roles[osha].add("%s/%s" % (GITHUB_DIR, path))
            else:
                blob_roles.setdefault(osha, set()).add("%s (type %s)" % (path, otype))
    # `found` gives each path's type and size, not its object id. The token
    # search is keyed on blob CONTENT, so two refs sharing a blob must share one
    # verdict and one read - hence the id and the dedupe.
    blob_of_path = {}
    for sha in unique_tips:
        for path in BOUNDED_BLOBS:
            info = found.get((sha, path))
            if info and info[0] == "blob":
                out = git(repo, ["rev-parse", "%s:%s" % (sha, path)])
                bsha = out.decode("utf-8", "replace").strip()
                blob_of_path[(sha, path)] = bsha
                blob_roles[bsha].add(path)

    contents = read_blobs(repo, set(blob_roles))
    blob_verdict = {}
    for bsha, content in contents.items():
        if content is None:
            blob_verdict[bsha] = {"readable": False, "occurrences": 0, "declarations": [],
                                  "comment_declarations": [], "mentions": 0}
            continue
        occ, decls, cdecls, mentions = classify_blob(content)
        blob_verdict[bsha] = {
            "readable": True,
            "occurrences": occ,
            "declarations": decls,
            "comment_declarations": cdecls,
            "mentions": mentions,
        }

    # --- (c) ancestry -------------------------------------------------------
    # AUTHORITY: `git merge-base --is-ancestor <base> <tip>`, one call per unique
    # tip. CROSS-CHECK: a single children-map walk of the whole commit graph.
    # Neither is allowed to fail silently into the other's answer: a tip the
    # graph never saw is UNKNOWN, not "no".
    desc_set, known = descendants_of(repo, args.base)
    graph_missing_tips = []
    anc_by_tip = {}
    anc_disagreements = []
    if not args.no_ancestor_subprocess:
        for i, sha in enumerate(unique_tips):
            rc = git_rc(repo, ["merge-base", "--is-ancestor", args.base, sha])
            if rc == 0:
                anc_by_tip[sha] = "yes"
            elif rc == 1:
                anc_by_tip[sha] = "no"
            else:
                anc_by_tip[sha] = "UNKNOWN(rc=%d)" % rc
            if desc_set is None or sha not in known:
                # The graph walk cannot speak about this tip, so its silence is
                # not a "no" and is never counted as one.
                graph_missing_tips.append(sha)
            else:
                walked = "yes" if sha in desc_set else "no"
                if anc_by_tip[sha] in ("yes", "no") and anc_by_tip[sha] != walked:
                    anc_disagreements.append({"tip": sha, "merge_base": anc_by_tip[sha], "graph_walk": walked})
            if (i + 1) % 250 == 0:
                print("  ancestry %d/%d" % (i + 1, len(unique_tips)), file=sys.stderr)
    else:
        for sha in unique_tips:
            if desc_set is None or sha not in known:
                anc_by_tip[sha] = "UNKNOWN(graph does not reach this tip)"
            else:
                anc_by_tip[sha] = "yes" if sha in desc_set else "no"

    # --- assemble one row per ref ------------------------------------------
    def bounded_blobs_for(tip):
        """Every blob in the bounded set at one tip, as (label, blob_sha, otype).

        The bound is the three named places and nothing else: every blob under
        `.github/**`, plus `scripts/ci_suite.py` and `scripts/provenance_report.py`.
        """
        out = []
        for path, otype, osha, _mode in tree_blobs.get(tree_of.get(tip, ""), []):
            out.append(("%s/%s" % (GITHUB_DIR, path), osha, otype))
        for path in BOUNDED_BLOBS:
            info = found.get((tip, path))
            if info is None:
                continue
            out.append((path, blob_of_path.get((tip, path), ""), info[0]))
        return out

    rows = []
    for r in refs:
        ref = r["refname"]
        tip, tip_kind, reason = tips[ref]
        row = {
            "refname": ref,
            "objectname": r["objectname"],
            "objecttype": r["objecttype"],
            "creatordate": r["creatordate"],
            "tip_commit": tip or "",
            "tip_kind": tip_kind,
            "has_github": "",
            "github_tree": "",
            "github_blob_count": "",
            "baseline_mode_token": "",
            "baseline_mode_declared": "",
            "baseline_mode_declarations": "",
            "baseline_mode_comment_declarations": "",
            "carrier_paths": "",
            "ci_suite_blob": "",
            "provenance_blob": "",
            "ancestor_of_base": "UNKNOWN(no tip)",
            "read_status": "OK",
            "unknown_reason": "",
        }

        def note(msg):
            row["unknown_reason"] = (row["unknown_reason"] + "; " if row["unknown_reason"] else "") + msg
            row["read_status"] = "UNKNOWN"

        if tip is None:
            note(reason)
            rows.append(row)
            continue

        gi = found.get((tip, GITHUB_DIR))
        if gi is None:
            row["has_github"] = "no"
        elif gi[0] == "tree":
            row["has_github"] = "yes"
            row["github_tree"] = tree_of.get(tip, "")
            row["github_blob_count"] = str(
                len([e for e in tree_blobs.get(tree_of.get(tip, ""), []) if e[1] == "blob"])
            )
        else:
            row["has_github"] = "no"
            note("`.github` exists at this tip but is a %s, not a tree" % gi[0])

        for path in BOUNDED_BLOBS:
            info = found.get((tip, path))
            bsha = blob_of_path.get((tip, path))
            row["ci_suite_blob" if path.endswith("ci_suite.py") else "provenance_blob"] = bsha or ""
            if info and info[0] != "blob":
                note("%s exists but is a %s, not a blob" % (path, info[0]))

        toks = 0
        decls, cdecls, carriers_here = set(), set(), set()
        for label, bsha, otype in bounded_blobs_for(tip):
            if otype != "blob" or not bsha:
                continue
            v = blob_verdict.get(bsha)
            if v is None:
                note("no verdict for blob %s at %s" % (bsha, label))
                continue
            if not v["readable"]:
                note("unreadable blob %s at %s" % (bsha, label))
                continue
            if v["occurrences"]:
                toks += v["occurrences"]
                carriers_here.add(label)
                decls.update(v["declarations"])
                cdecls.update(v["comment_declarations"])

        row["baseline_mode_token"] = "yes" if toks else "no"
        row["baseline_mode_declared"] = "yes" if decls else "no"
        row["baseline_mode_declarations"] = "|".join(sorted(decls))
        row["baseline_mode_comment_declarations"] = "|".join(sorted(cdecls))
        row["carrier_paths"] = "|".join(sorted(carriers_here))
        row["ancestor_of_base"] = anc_by_tip.get(tip, "UNKNOWN")
        rows.append(row)

    rows.sort(key=lambda x: x["refname"])

    # --- the independent differential for (b), if asked for ------------------
    grep_diff = {"ran": False}
    if args.control_grep:
        gh = grep_control(repo, unique_tips)
        census_token = {}
        for r in rows:
            if r["tip_commit"]:
                # A ref's answer is its tip's answer; tips are shared, so build
                # the per-tip census answer the same way grep's is built.
                census_token.setdefault(r["tip_commit"], r["baseline_mode_token"])
        only_census, only_grep, unknown_grep = [], [], []
        for sha, token in census_token.items():
            g = gh.get(sha, "UNKNOWN(absent)")
            if g == "yes" and token != "yes":
                only_grep.append(sha)
            elif g == "no" and token != "no":
                only_census.append(sha)
            elif g.startswith("UNKNOWN"):
                unknown_grep.append({"tip": sha, "grep": g})
        grep_diff = {
            "ran": True,
            "authority": "git grep -l -F BASELINE_MODE <tip> -- .github scripts/ci_suite.py scripts/provenance_report.py",
            "tips_compared": len(census_token),
            "census_token_yes": len([v for v in census_token.values() if v == "yes"]),
            "grep_yes": len([v for v in gh.values() if v == "yes"]),
            "carriers_only_the_census_found": only_census,
            "carriers_only_grep_found": only_grep,
            "tips_grep_could_not_read": unknown_grep,
            "agree": not only_census and not only_grep and not unknown_grep,
        }

    # --- counts -------------------------------------------------------------
    refs_with_github = [r for r in rows if r["has_github"] == "yes"]
    carriers = [r for r in rows if r["baseline_mode_token"] == "yes"]
    declared = [r for r in rows if r["baseline_mode_declared"] == "yes"]
    carrier_desc = [r for r in carriers if r["ancestor_of_base"] == "yes"]
    declared_desc = [r for r in declared if r["ancestor_of_base"] == "yes"]
    unknowns = [r for r in rows if r["read_status"] == "UNKNOWN"]
    decl_breakdown = collections.Counter()
    for r in declared:
        decl_breakdown[r["baseline_mode_declarations"] or "<unparsed>"] += 1
    path_breakdown = collections.Counter()
    for r in carriers:
        for p in r["carrier_paths"].split("|"):
            if p:
                path_breakdown[p] += 1

    summary = {
        "task": "merge/0330",
        "base": args.base,
        "repo": repo,
        "finished_at_utc": _utcnow(),
        "denominator": {
            "for_each_ref_multi_field": denominator_reads["formatted_multi_field"],
            "for_each_ref_refname_only": denominator_reads["refname_only"],
            "reads_agree": denominator_agrees,
            "distinct_tips": len(unique_tips),
            "authority": "git for-each-ref --format=%(refname)%09%(objectname)%09%(objecttype)%09%(creatordate:iso-strict)",
        },
        "counts": {
            "refs_with_github": len(refs_with_github),
            "refs_carrying_baseline_mode": len(carriers),
            "carriers_descendant_of_base": len(carrier_desc),
            "refs_with_uncommented_declaration": len(declared),
            "declared_carriers_descendant_of_base": len(declared_desc),
            "refs_unknown": len(unknowns),
        },
        "baseline_mode_declaration_breakdown": dict(decl_breakdown),
        "carrier_path_breakdown": dict(path_breakdown),
        "unique_github_trees": len(set(tree_of.values())),
        "batch_check_expressions": len(unique_tips) * len(BOUNDED_PATHS),
        "batch_check_lines_whose_echoed_name_is_not_the_query": echoed_name_differs,
        "unique_bounded_blobs_read": len(contents),
        "ls_tree_agreement": ls_tree_agreement,
        "grep_differential": grep_diff,
        "measured_at_utc": measured_at,
        "ancestry_cross_check": {
            "authority": "git merge-base --is-ancestor %s <tip>" % args.base,
            "cross_check": "children-map walk of git rev-list --all --parents",
            "disagreements": anc_disagreements,
            "tips_the_graph_walk_never_saw": graph_missing_tips,
            "graph_walk_commits": len(known),
            "graph_walk_descendants_of_base": None if desc_set is None else len(desc_set),
            "base_in_graph": desc_set is not None,
        },
        "github_tree_problems": tree_problems,
        "refs_with_github_names": [r["refname"] for r in refs_with_github],
        "carrier_names": [r["refname"] for r in carriers],
        "carrier_names_descendant": [r["refname"] for r in carrier_desc],
        "declared_carrier_names": [r["refname"] for r in declared],
        "declared_carrier_names_descendant": [r["refname"] for r in declared_desc],
        "unknown_rows": [{"refname": r["refname"], "reason": r["unknown_reason"]} for r in unknowns],
    }

    columns = [
        "refname", "objectname", "objecttype", "creatordate", "tip_commit", "tip_kind",
        "has_github", "github_tree", "github_blob_count", "baseline_mode_token",
        "baseline_mode_declared", "baseline_mode_declarations",
        "baseline_mode_comment_declarations", "carrier_paths",
        "ci_suite_blob", "provenance_blob",
        "ancestor_of_base", "read_status", "unknown_reason",
    ]
    with open(args.out_tsv, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(columns) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]).replace("\t", " ") for c in columns) + "\n")
    with open(args.out_json, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({k: summary[k] for k in ("denominator", "counts", "baseline_mode_declaration_breakdown",
                                              "ls_tree_agreement", "ancestry_cross_check")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())