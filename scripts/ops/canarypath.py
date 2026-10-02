"""Which branches are on the canary's send path, measured rather than judged.

The send path is defined by what the code that SENDS actually imports, walked
transitively inside `src/`. A branch is ON the path if it changes a module in
that closure, or a config file that closure reads. Anything else is off it, and
"off it" is then a measured statement rather than an opinion.

    python canarypath.py <repo-with-all-branches> <branch> [<branch> ...]
"""
import ast
import os
import subprocess
import sys

#: The entry points a prospect-facing EmailBison send actually goes through.
#: `executionguard.authorize` is the one gate a provider write must pass;
#: `providerwrites.perform` is the only thing that writes; `eligibility.decide`
#: picks who; `generate`/`generate_campaign` write the words; `lint` and `claims`
#: decide whether the words may ship.
ROOTS = [
    "executionguard", "providerwrites", "eligibility", "lint", "claims",
    "generate", "generate_campaign", "campaigns", "collision", "copystages",
    "channels", "agencydnc", "approve", "cadence", "store",
]


def src_modules(repo):
    out = {}
    base = os.path.join(repo, "src")
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            mod = rel[:-3].replace("/", ".")
            if mod.endswith(".__init__"):
                mod = mod[: -len(".__init__")]
            out[mod] = full
    return out


def imports_of(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return set()
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module)
            # `from . import x` / `from ..providers import y`
            for alias in node.names:
                found.add(alias.name)
    return {f.split(".")[-1] for f in found} | {f for f in found}


def closure(repo):
    mods = src_modules(repo)
    seen, stack = set(), [r for r in ROOTS if r in mods]
    missing = [r for r in ROOTS if r not in mods]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        for name in imports_of(mods[mod]):
            for candidate in (name, name.split(".")[-1]):
                if candidate in mods and candidate not in seen:
                    stack.append(candidate)
    return seen, missing, mods


def changed(repo, branch, base="master"):
    mb = subprocess.run(["git", "merge-base", base, branch], cwd=repo,
                        capture_output=True, text=True).stdout.strip()
    if not mb:
        return None
    out = subprocess.run(["git", "diff", "--name-only", mb, branch], cwd=repo,
                         capture_output=True, text=True)
    return [f for f in out.stdout.splitlines() if f]


def main():
    repo, branches = sys.argv[1], sys.argv[2:]
    path_mods, missing, mods = closure(repo)
    print(f"  send-path closure: {len(path_mods)} modules in src/")
    if missing:
        print(f"  ROOTS NOT FOUND (so not counted): {missing}")
    # the control: a module nobody on the send path imports must be OUTSIDE
    outsiders = sorted(set(mods) - path_mods)
    print(f"  modules OUTSIDE the closure: {len(outsiders)}"
          f"  e.g. {outsiders[:4]}")
    print()
    for branch in branches:
        files = changed(repo, branch)
        if files is None:
            print(f"  {branch}: no merge base with master")
            continue
        on, off = [], []
        for f in files:
            if f.startswith("src/") and f.endswith(".py"):
                mod = f[len("src/"):-3].replace("/", ".")
                short = mod.split(".")[-1]
                (on if (mod in path_mods or short in path_mods) else off
                 ).append(f)
            elif f.startswith("config/") or f.startswith("prompts/"):
                on.append(f + "  (config/prompt the path reads)")
            else:
                off.append(f)
        verdict = "ON THE SEND PATH" if on else "OFF THE SEND PATH"
        print(f"  {branch}")
        print(f"    {len(files)} file(s) changed -> {verdict}")
        for f in on:
            print(f"      ON : {f}")
        if not on:
            for f in off[:6]:
                print(f"      off: {f}")
            if len(off) > 6:
                print(f"      off: ... and {len(off) - 6} more")
        print()


if __name__ == "__main__":
    main()
