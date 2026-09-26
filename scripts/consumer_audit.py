#!/usr/bin/env python3
"""Consumer audit: every producer names a consumer or is DISCONNECTED.

Walks the import and call graph of src/ using ast and classifies every
module that exposes public names as CONNECTED or DISCONNECTED.

A module is CONNECTED when at least one non-test src/ module imports a
public name from it AND uses that name in a call or attribute access.
A re-export through __init__.py is not a consumer — the name must reach
a real call site.

Usage:
    python scripts/consumer_audit.py              # markdown table to stdout
    python scripts/consumer_audit.py --json        # JSON to stdout
    python scripts/consumer_audit.py --write-map   # also write CONSUMER-MAP.md
"""
import ast
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

SKIP_DIRS = {"__pycache__", ".qwen"}


def _src_modules():
    """Return {dotted_name: absolute_path} for every .py under src/."""
    modules = {}
    for dirpath, dirnames, filenames in os.walk(SRC_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, PROJECT_ROOT).replace("\\", "/")
            parts = rel.split("/")
            if parts[-1] == "__init__.py":
                dotted = ".".join(parts[:-1])
            else:
                parts[-1] = parts[-1][:-3]
                dotted = ".".join(parts)
            modules[dotted] = full
    return modules


def _parse(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return ast.parse(f.read(), filename=path)
    except (SyntaxError, UnicodeDecodeError):
        return None


def _public_names(tree):
    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.add(target.id)
    return names


def _collect_imports(tree, importing_dotted):
    """Return {resolved_source_dotted: {imported_names}}.

    Resolves relative imports against the importing module's position.
    """
    imports = {}
    parts = importing_dotted.split(".")
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        level = node.level or 0
        mod = node.module or ""
        names = {a.name for a in node.names if not a.name.startswith("_")}
        if not names:
            continue
        if level > 0:
            base = parts[:-level] if level <= len(parts) else []
            if mod:
                base.append(mod)
            resolved = ".".join(base)
        else:
            resolved = mod
        if resolved:
            imports.setdefault(resolved, set()).update(names)
    return imports


def _collect_used_names(tree):
    """Single AST walk: collect all Name-loads and Attribute bases.

    Returns (bare_names: set[str], dotted_uses: dict[str, set[str]]).
    bare_names: names used in Load context (calls, refs, etc.)
    dotted_uses: {alias: {attr_names}} for alias.attr patterns
    """
    bare = set()
    dotted = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            bare.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                dotted.setdefault(node.value.id, set()).add(node.attr)
    return bare, dotted


def _collect_all_names(tree):
    """Collect names listed in __all__ if present."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        return {
                            elt.value for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }
    return set()


def audit():
    """Run the consumer audit. Returns a list of row dicts."""
    modules = _src_modules()

    parsed = {}
    for dotted, path in modules.items():
        tree = _parse(path)
        if tree is not None:
            parsed[dotted] = (path, tree)

    # Pre-compute per-module: public names, imports, used names, __all__
    info = {}
    for dotted, (path, tree) in parsed.items():
        pub = _public_names(tree)
        if not pub:
            continue
        imports = _collect_imports(tree, dotted)
        used_bare, used_dotted = _collect_used_names(tree)
        all_decl = _collect_all_names(tree)
        info[dotted] = {
            "path": path,
            "tree": tree,
            "public": pub,
            "imports": imports,
            "used_bare": used_bare,
            "used_dotted": used_dotted,
            "__all__": all_decl,
        }

    # Build reverse map: for each producer, which consumers import what
    # producer_dotted -> {consumer_dotted: {imported_names}}
    producer_imports = {}
    for consumer_dotted, cinfo in info.items():
        for source_dotted, imported_names in cinfo["imports"].items():
            # Each imported name might be a submodule
            for name in list(imported_names):
                sub = f"{source_dotted}.{name}" if source_dotted else name
                if sub in info and sub != consumer_dotted:
                    producer_imports.setdefault(sub, {})
                    producer_imports[sub].setdefault(
                        consumer_dotted, set()
                    ).add(name)

            # The package itself may also export the names
            if source_dotted in info:
                producer_imports.setdefault(source_dotted, {})
                producer_imports[source_dotted].setdefault(
                    consumer_dotted, set()
                ).update(imported_names)

    results = []
    for dotted in sorted(info):
        pinfo = info[dotted]
        pub = pinfo["public"]
        path = pinfo["path"]
        rel_path = os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")
        short_name = dotted.split(".")[-1]

        consumers = []
        raw_consumers = producer_imports.get(dotted, {})

        for consumer_dotted, imported_names in sorted(raw_consumers.items()):
            if "tests" in consumer_dotted.split("."):
                continue
            if consumer_dotted not in info:
                continue
            cinfo = info[consumer_dotted]

            matched = imported_names & pub
            short = dotted.split(".")[-1]
            module_import = short in imported_names and short not in pub
            if not matched and not module_import:
                continue

            # __init__.py re-export check
            if consumer_dotted.endswith(".__init__"):
                locally_used = set()
                check_names = matched if matched else set()
                for name in check_names:
                    if name in cinfo["used_bare"]:
                        locally_used.add(name)
                    for alias, attrs in cinfo["used_dotted"].items():
                        if name in attrs:
                            locally_used.add(name)
                if module_import and not locally_used:
                    if short not in cinfo["used_bare"]:
                        continue
                elif not locally_used and not module_import:
                    continue

            actually_used = set()
            for name in matched:
                if name in cinfo["used_bare"]:
                    actually_used.add(name)
                for alias, attrs in cinfo["used_dotted"].items():
                    if name in attrs:
                        actually_used.add(name)

            if module_import and short in cinfo["used_bare"]:
                for attr_name in cinfo["used_dotted"].get(short, set()):
                    if attr_name in pub:
                        actually_used.add(attr_name)

            if actually_used:
                consumers.append({
                    "module": consumer_dotted,
                    "path": os.path.relpath(
                        cinfo["path"], PROJECT_ROOT
                    ).replace("\\", "/"),
                    "names": sorted(actually_used),
                })

        verdict = "CONNECTED" if consumers else "DISCONNECTED"
        row = {
            "component": rel_path,
            "dotted": dotted,
            "public_names": sorted(pub),
            "source": rel_path,
            "canonical_store": _canonical_store(dotted),
            "retrieval": _retrieval(dotted),
            "consumers": consumers,
            "decision_or_copy_effect": _decision_effect(dotted, consumers),
            "validation": _validation(dotted),
            "verdict": verdict,
        }
        results.append(row)

    return results


def _canonical_store(dotted):
    name = dotted.split(".")[-1]
    m = {
        "store": "work/queue.jsonl + work/campaigns.jsonl",
        "secondbrain": "config/clients/<client>.yaml",
        "contextpack": "config/clients/<client>.yaml (via clients.load)",
        "spendledger": "work/spend.jsonl",
        "actionledger": "work/actions.jsonl",
        "bisonevents": "EmailBison provider state",
        "heyreachfactory": "HeyReach provider state",
        "campaigns": "work/campaigns.jsonl",
        "evidence": "work/evidence/",
        "clients": "config/clients/*.yaml",
    }
    return m.get(name, "—")


def _retrieval(dotted):
    name = dotted.split(".")[-1]
    m = {
        "secondbrain": "for_task(task, client)",
        "contextpack": "build(recs, campaign, ...)",
        "sequencegate": "check(sequence, ...)",
        "copystages": "hypothesis_user / match_user / strategy_user / writer_user",
    }
    return m.get(name, "—")


def _decision_effect(dotted, consumers):
    if not consumers:
        return "no production consumer — DISCONNECTED"
    parts = []
    for c in consumers:
        parts.append(f"{c['module']} reads {', '.join(c['names'][:3])}")
    return "; ".join(parts)


def _validation(dotted):
    name = dotted.split(".")[-1]
    m = {
        "secondbrain": "returns only sections the task needs",
        "sequencegate": "checks whole-sequence repetition and cross-channel",
        "copystages": "each stage returns a prompt string",
        "contextpack": "build() assembles recs into a display dict",
        "copylint": "lint.check_step returns pass/fail per message",
    }
    return m.get(name, "—")


def render_markdown(rows):
    lines = [
        "# Consumer Map",
        "",
        "<!-- GENERATED by scripts/consumer_audit.py — do not hand-edit -->",
        "",
        f"**Generated:** {__import__('datetime').date.today().isoformat()}",
        "",
        f"**Total producers:** {len(rows)}",
        f"**CONNECTED:** {sum(1 for r in rows if r['verdict'] == 'CONNECTED')}",
        f"**DISCONNECTED:** {sum(1 for r in rows if r['verdict'] == 'DISCONNECTED')}",
        "",
        "| COMPONENT | SOURCE | CANONICAL STORE | RETRIEVAL | CONSUMER | "
        "DECISION OR COPY EFFECT | VALIDATION | VERDICT |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        consumer_str = "; ".join(
            f"{c['module']}({', '.join(c['names'][:3])})" for c in r["consumers"]
        ) or "—"
        lines.append(
            f"| {r['component']} "
            f"| {r['source']} "
            f"| {r['canonical_store']} "
            f"| {r['retrieval']} "
            f"| {consumer_str} "
            f"| {r['decision_or_copy_effect']} "
            f"| {r['validation']} "
            f"| **{r['verdict']}** |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Consumer audit for src/")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--write-map", action="store_true",
                        help="Write docs/state/CONSUMER-MAP.md")
    args = parser.parse_args()

    rows = audit()

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(render_markdown(rows))

    if args.write_map:
        map_path = os.path.join(PROJECT_ROOT, "docs", "state", "CONSUMER-MAP.md")
        os.makedirs(os.path.dirname(map_path), exist_ok=True)
        with open(map_path, "w", encoding="utf-8") as f:
            f.write(render_markdown(rows))
        print(f"\nWrote {map_path}", file=sys.stderr)

    disconnected = [r for r in rows if r["verdict"] == "DISCONNECTED"]
    if disconnected:
        print(f"\n{len(disconnected)} DISCONNECTED component(s):", file=sys.stderr)
        for r in disconnected:
            print(f"  {r['component']}: {', '.join(r['public_names'][:5])}",
                  file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
