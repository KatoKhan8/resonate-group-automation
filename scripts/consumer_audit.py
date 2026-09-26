#!/usr/bin/env python3
"""Consumer audit: every producer names a consumer or is DISCONNECTED.

Walks the import and call graph of src/ using ast and classifies every
module that exposes public names as CONNECTED or DISCONNECTED.

A module is CONNECTED when at least one non-test src/ module or scripts/
module imports a public name from it AND uses that name in a call or
attribute access.  A re-export through __init__.py is not a consumer -
the name must reach a real call site.

Consumer surfaces:
  - src/   (production modules importing each other)
  - scripts/  (operator scripts importing from src.)

NOT consumer surfaces:
  - tests/  (a module whose only caller is its own test is disconnected)
  - work/   (gitignored scratch)

CLI entry points:
  A module exposing ``if __name__ == "__main__":`` or a top-level
  ``def main()`` is CONNECTED with consumer="operator CLI" even when
  no other module imports it.

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
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

SKIP_DIRS = {"__pycache__", ".qwen"}


def _py_files(directory):
    """Return absolute paths of every .py under *directory*."""
    result = []
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                result.append(os.path.join(dirpath, fn))
    return result


def _src_modules():
    """Return {dotted_name: absolute_path} for every .py under src/."""
    modules = {}
    root = os.path.dirname(SRC_DIR)
    for full in _py_files(SRC_DIR):
        rel = os.path.relpath(full, root).replace("\\", "/")
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


def _is_cli_entry_point(tree):
    """True when the module has ``if __name__ == "__main__":`` or ``def main()``."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "main":
                return True
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Compare):
                left = test.left
                if (
                    isinstance(left, ast.Name)
                    and left.id == "__name__"
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Eq)
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value == "__main__"
                ):
                    return True
    return False


def _collect_imports(tree, importing_dotted):
    """Return {resolved_source_dotted: {local_names}}.

    Handles both ``from X import Y`` (ast.ImportFrom) and
    ``import X`` (ast.Import).

    Resolves relative imports against the importing module's position.

    For ``from . import foo as bar``, the resolved source is the module
    ``foo`` itself, and the tracked local name is ``bar`` (the alias).
    For ``from .foo import BAZ``, the resolved source is ``foo`` and the
    tracked local name is ``BAZ``.
    """
    imports = {}
    parts = importing_dotted.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            level = node.level or 0
            mod = node.module or ""
            if level > 0:
                base = parts[:-level] if level <= len(parts) else []
                if mod:
                    base.append(mod)
                resolved_base = ".".join(base)
            else:
                resolved_base = mod

            # Each imported name might be a submodule or a name from the module
            for a in node.names:
                if a.name.startswith("_"):
                    continue
                local_name = a.asname if a.asname else a.name
                # Try resolving as a submodule first
                sub_module = f"{resolved_base}.{a.name}" if resolved_base else a.name
                # We'll add both possibilities; the reverse map builder
                # will check which one exists in the module registry
                imports.setdefault(resolved_base, set()).add(local_name)
                if sub_module != resolved_base:
                    imports.setdefault(sub_module, set()).add(local_name)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("_"):
                    continue
                local_name = alias.asname if alias.asname else name
                imports.setdefault(name, set()).add(local_name)

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


def _script_dotted(full):
    """Return a dotted identifier for a scripts/ file.

    scripts/bison_readback.py -> 'scripts.bison_readback'
    """
    rel = os.path.relpath(full, PROJECT_ROOT).replace("\\", "/")
    parts = rel.split("/")
    parts[-1] = parts[-1][:-3]
    return ".".join(parts)


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

    # --- Scan scripts/ as a consumer surface ---
    script_consumers = {}
    for full in _py_files(SCRIPTS_DIR):
        tree = _parse(full)
        if tree is None:
            continue
        s_dotted = _script_dotted(full)
        s_imports = _collect_imports(tree, s_dotted)
        s_used_bare, s_used_dotted = _collect_used_names(tree)
        script_consumers[s_dotted] = {
            "path": full,
            "imports": s_imports,
            "used_bare": s_used_bare,
            "used_dotted": s_used_dotted,
        }

    # Build reverse map: for each producer, which consumers import what
    # producer_dotted -> {consumer_dotted: {imported_names}}
    producer_imports = {}
    for consumer_dotted, cinfo in info.items():
        for source_dotted, imported_names in cinfo["imports"].items():
            for name in list(imported_names):
                sub = f"{source_dotted}.{name}" if source_dotted else name
                if sub in info and sub != consumer_dotted:
                    producer_imports.setdefault(sub, {})
                    producer_imports[sub].setdefault(
                        consumer_dotted, set()
                    ).add(name)

            if source_dotted in info:
                producer_imports.setdefault(source_dotted, {})
                producer_imports[source_dotted].setdefault(
                    consumer_dotted, set()
                ).update(imported_names)

    # Also add script consumers to the reverse map
    for s_dotted, sinfo in script_consumers.items():
        for source_dotted, imported_names in sinfo["imports"].items():
            for name in list(imported_names):
                sub = f"{source_dotted}.{name}" if source_dotted else name
                if sub in info:
                    producer_imports.setdefault(sub, {})
                    producer_imports[sub].setdefault(
                        s_dotted, set()
                    ).add(name)

            if source_dotted in info:
                producer_imports.setdefault(source_dotted, {})
                producer_imports[source_dotted].setdefault(
                    s_dotted, set()
                ).update(imported_names)

    # Build initial consumer lists per producer
    initial_consumers = {}
    for dotted in sorted(info):
        pinfo = info[dotted]
        pub = pinfo["public"]
        consumers = []
        raw_consumers = producer_imports.get(dotted, {})

        for consumer_dotted, imported_names in sorted(raw_consumers.items()):
            is_script = consumer_dotted.startswith("scripts.")

            if not is_script:
                if "tests" in consumer_dotted.split("."):
                    continue
                if consumer_dotted not in info:
                    continue
                cinfo = info[consumer_dotted]
            else:
                cinfo = script_consumers.get(consumer_dotted)
                if cinfo is None:
                    continue

            # Check which imported names are actually used
            actually_used = set()

            # Direct name use: imported name appears in used_bare or as an attribute
            matched = imported_names & pub
            for name in matched:
                if name in cinfo["used_bare"]:
                    actually_used.add(name)
                for alias, attrs in cinfo["used_dotted"].items():
                    if name in attrs:
                        actually_used.add(name)

            # Module-level dotted access: imported name used as base for
            # attribute access where the attribute is a producer public name.
            # e.g., ``from . import secondbrain`` then ``secondbrain.for_task``
            for local_name in imported_names:
                for attr_name in cinfo["used_dotted"].get(local_name, set()):
                    if attr_name in pub:
                        actually_used.add(attr_name)

            if actually_used:
                c_rel = os.path.relpath(
                    cinfo["path"], PROJECT_ROOT
                ).replace("\\", "/")
                consumers.append({
                    "module": consumer_dotted,
                    "path": c_rel,
                    "names": sorted(actually_used),
                })

        initial_consumers[dotted] = consumers

    # --- Transitive disconnection ---
    # A module whose only consumers are themselves DISCONNECTED is also
    # DISCONNECTED. Iterate until stable.
    verdict = {}
    for dotted in info:
        consumers = initial_consumers.get(dotted, [])
        if consumers:
            verdict[dotted] = "CONNECTED"
        elif _is_cli_entry_point(info[dotted]["tree"]):
            verdict[dotted] = "CONNECTED"
        else:
            verdict[dotted] = "DISCONNECTED"

    changed = True
    while changed:
        changed = False
        for dotted in info:
            if verdict[dotted] != "CONNECTED":
                continue
            consumers = initial_consumers.get(dotted, [])
            # Terminal consumers: operator CLI and scripts.* are never
            # DISCONNECTED themselves, so they anchor a module as CONNECTED.
            has_terminal = any(
                c["module"] == "operator CLI" or c["module"].startswith("scripts.")
                for c in consumers
            )
            if has_terminal:
                # Module has a terminal consumer, so it's anchored as CONNECTED
                continue
            reachable = consumers
            if not reachable:
                continue
            all_disconnected = all(
                verdict.get(c["module"]) == "DISCONNECTED"
                for c in reachable
                if c["module"] in verdict
            )
            if all_disconnected and reachable:
                verdict[dotted] = "DISCONNECTED"
                changed = True

    results = []
    for dotted in sorted(info):
        pinfo = info[dotted]
        pub = pinfo["public"]
        path = pinfo["path"]
        rel_path = os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")

        consumers = initial_consumers.get(dotted, [])

        # CLI entry point: add only if still needed for verdict
        if verdict[dotted] == "CONNECTED" and not consumers:
            consumers = [{
                "module": "operator CLI",
                "path": rel_path,
                "names": ["__main__"],
            }]
        elif verdict[dotted] == "CONNECTED" and _is_cli_entry_point(pinfo["tree"]):
            has_cli = any(c["module"] == "operator CLI" for c in consumers)
            if not has_cli:
                consumers.append({
                    "module": "operator CLI",
                    "path": rel_path,
                    "names": ["__main__"],
                })

        v = verdict[dotted]
        row = {
            "component": rel_path,
            "dotted": dotted,
            "public_names": sorted(pub),
            "source": rel_path,
            "canonical_store": _canonical_store(dotted),
            "retrieval": _retrieval(dotted),
            "consumers": consumers if v == "CONNECTED" else [],
            "decision_or_copy_effect": _decision_effect(dotted, consumers if v == "CONNECTED" else []),
            "validation": _validation(dotted),
            "verdict": v,
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
    return m.get(name, "-")


def _retrieval(dotted):
    name = dotted.split(".")[-1]
    m = {
        "secondbrain": "for_task(task, client)",
        "contextpack": "build(recs, campaign, ...)",
        "sequencegate": "check(sequence, ...)",
        "copystages": "hypothesis_user / match_user / strategy_user / writer_user",
    }
    return m.get(name, "-")


def _decision_effect(dotted, consumers):
    if not consumers:
        return "no production consumer - DISCONNECTED"
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
    return m.get(name, "-")


def render_markdown(rows):
    lines = [
        "# Consumer Map",
        "",
        "<!-- GENERATED by scripts/consumer_audit.py - do not hand-edit -->",
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
        ) or "-"
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
