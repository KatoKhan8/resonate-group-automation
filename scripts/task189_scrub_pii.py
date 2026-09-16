"""TASK-189: Consistent PII scrub for docs/ and scripts/.

Hash function: SHA-256 with a fixed salt, truncated to 12 hex chars,
prefixed with 'px-' (for 'pixelated'). The same input always produces
the same output, so a reader can follow one entity across documents.

The salt is public (it is in this script, which is tracked). It exists
only to prevent rainbow-table lookup of the hashes. The hashes are not
secrets; they are opaque replacements.

The forbidden values are imported from tests/test_fixture_hygiene.py
(the guard itself) rather than hardcoded here, so this script does not
trigger the guard it is trying to help.

Usage:
    py -3 scripts/task189_scrub_pii.py          # dry run, prints changes
    py -3 scripts/task189_scrub_pii.py --apply   # writes files
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Import forbidden values from the guard itself, so we do not duplicate
# them here and trigger the scanner we are trying to satisfy.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_fixture_hygiene import (FORBIDDEN_DOMAINS, FORBIDDEN_NAMES,
                                  FORBIDDEN_FIGURES)

SALT = "resonate-pii-salt-2026-09-16"


def px(value):
    """Deterministic hash: same input -> same output, everywhere."""
    h = hashlib.sha256((SALT + value).encode("utf-8")).hexdigest()[:12]
    return f"px-{h}"


def build_replacements():
    """Ordered longest-first so multi-word names replace before tokens."""
    reps = []
    for d in FORBIDDEN_DOMAINS:
        reps.append((d, px(d)))
    for n in sorted(FORBIDDEN_NAMES, key=len, reverse=True):
        reps.append((n, px(n)))
    for f in FORBIDDEN_FIGURES:
        reps.append((f, px(f)))
    reps.sort(key=lambda pair: len(pair[0]), reverse=True)
    return reps


def result_block_start(text):
    """Line number (0-based) where a RESULT block begins, or None."""
    for i, line in enumerate(text.split("\n")):
        if line.startswith("#") and "RESULT" in line:
            return i
    return None


def scrub_text(text, replacements, only_above_line=None):
    """Replace all forbidden values. If only_above_line, only scrub that region."""
    if only_above_line is not None:
        lines = text.split("\n")
        head = "\n".join(lines[:only_above_line])
        tail = "\n".join(lines[only_above_line:])
        for old, new in replacements:
            head = case_insensitive_replace(head, old, new)
        return head + "\n" + tail
    else:
        for old, new in replacements:
            text = case_insensitive_replace(text, old, new)
        return text


def case_insensitive_replace(text, old, new):
    """Replace all case-insensitive occurrences of old with new."""
    pattern = re.compile(re.escape(old), re.IGNORECASE)
    return pattern.sub(new, text)


def files_to_scrub():
    """Tracked files in docs/ and scripts/, excluding forbidden paths."""
    import subprocess
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    all_files = [f for f in out.strip().split("\n") if f]

    TEXT_SUFFIXES = (".py", ".json", ".jsonl", ".csv", ".txt", ".md",
                     ".yaml", ".yml", ".cfg", ".ini", ".toml", ".html",
                     ".js", ".css")

    result = []
    for f in all_files:
        if not f.endswith(TEXT_SUFFIXES):
            continue
        if not (f.startswith("docs/") or f.startswith("scripts/")):
            continue
        if f == "tests/test_fixture_hygiene.py":
            continue
        result.append(f)
    return result


def main():
    apply = "--apply" in sys.argv
    replacements = build_replacements()

    print("Hash function: SHA-256(salt + value)[:12], prefixed 'px-'")
    print(f"Salt: {SALT}")
    print(f"Replacements: {len(replacements)}")
    print()

    files = files_to_scrub()
    changed = 0

    for f in files:
        path = os.path.join(ROOT, f)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                original = fh.read()
        except (OSError, IOError):
            continue

        only_above = None
        if f.startswith("docs/qwen-tasks/"):
            only_above = result_block_start(original)

        scrubbed = scrub_text(original, replacements, only_above_line=only_above)

        if scrubbed != original:
            changed += 1
            if apply:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(scrubbed)
                print(f"  SCRUBBED: {f}")
            else:
                print(f"  WOULD SCRUB: {f}")

    print(f"\nFiles {'scrubbed' if apply else 'to scrub'}: {changed}")
    if not apply:
        print("Run with --apply to write changes.")


if __name__ == "__main__":
    main()
