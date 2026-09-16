"""TASK-189: Consistent PII scrub for docs/ and scripts/.

Hash function: SHA-256 with a fixed salt, truncated to 12 hex chars,
prefixed with 'px-' (for 'pixelated'). The same input always produces
the same output, so a reader can follow one entity across documents.

    px-adcuratio.com   = sha256('resonate-pii-salt-2026-09-16' + 'adcuratio.com')[:12]
    -> 'px-' + that 12-char hex

The salt is public (it is in this script, which is tracked). It exists
only to prevent rainbow-table lookup of the hashes. The hashes are not
secrets; they are opaque replacements.

Usage:
    py -3 scripts/task189_scrub_pii.py          # dry run, prints changes
    py -3 scripts/task189_scrub_pii.py --apply   # writes files
"""
import hashlib
import os
import re
import sys

SALT = "resonate-pii-salt-2026-09-16"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FORBIDDEN_DOMAINS = (
    "arbona.hr", "bornfight.com", "five.agency", "beauhurst.com", "robotiq.ai",
    "levelupleads.io", "whatson.ai", "fornate.com", "leapin.co", "jobadder.com",
    "321webmarketing.com", "20northmarketing.com", "adcreations.com",
    "adcuratio.com", "1secondleads.com", "28row.com", "adblend.co",
    "anewagencyworld.com", "aubryandco.com", "arcoagency.se", "nineyards.ie",
    "thirtythree-usa.com",
    "clay.com", "relpro.com", "auvale.de", "alta.com", "tawk.to",
    "synquery.com", "farseer.io", "q-agency.com", "netnada.com.au",
    "nextoria.com", "cyber64.hr", "productive.io",
    "goproductive.online", "goproductive.net", "goproductivelab.com",
    "goproductivelabs.live", "tryproductive.online", "withproductive.online",
    "gonetnada.com", "trynetnada.live", "netnadadigital.shop",
    "contactout.io",
)

FORBIDDEN_NAMES = (
    "mahovic", "mahović", "klaric", "klarić", "blackler", "hopkins",
    "gudelj", "galic", "galić", "ivce", "pavlovic", "pavlović",
    "van ulden", "baauw", "karsant", "lucic", "gokdeniz", "beslic", "beslić",
    "brooke baron", "brookebaron", "josephoneill", "joseph o'neill",
    "lingenfelter", "dahlstrom",
    "mediaboard", "netnada", "cyber64",
    "nineyards", "brooke", "arbona", "bornfight", "jobadder", "adcuratio",
    "adcreations", "321webmarketing", "20northmarketing", "1secondleads",
    "28row", "adblend", "anewagencyworld", "aubryandco", "arcoagency",
    "thirtythree-usa", "goproductive", "gonetnada", "trynetnada",
)

FORBIDDEN_FIGURES = (
    "179268", "142737", "39826", "119616", "54317", "32509",
    "189,683", "189683", "269,973", "269973", "27,144", "27144",
    "17,362", "17362", "1,853",
)


def px(value):
    """Deterministic hash: same input -> same output, everywhere."""
    h = hashlib.sha256((SALT + value).encode("utf-8")).hexdigest()[:12]
    return f"px-{h}"


def build_replacements():
    """Ordered longest-first so 'brooke baron' replaces before 'brooke'."""
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

    sample = [("adcuratio.com", px("adcuratio.com")),
              ("adcuratio", px("adcuratio")),
              ("28row.com", px("28row.com")),
              ("brooke", px("brooke")),
              ("nineyards", px("nineyards"))]
    print("Sample hashes:")
    for val, h in sample:
        print(f"  {val!r:30s} -> {h}")
    print()

    files = files_to_scrub()
    changed = 0
    total_replacements = 0

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
            n = sum(1 for o, _ in replacements
                    if o.lower() in original.lower())
            changed += 1
            total_replacements += n
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
