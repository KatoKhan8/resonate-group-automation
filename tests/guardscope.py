"""How a guard decides which FILES it is allowed to skip.

NOT a `test_` module on purpose. `tests/offline.py` discovers with `tests`
as the top level, so a second module importing a `test_`-prefixed sibling
registers that sibling twice and the runner then assembles more children
than there are files on disk. This holds the shared rule instead, and
nothing here is collected as a test.

## THE BUG THIS EXISTS TO MAKE IMPOSSIBLE

`test_invariants.TestNothingCanSend` and `test_audit` both filtered their
offenders with

    if not any(a in p for a in allowed)

where `p` is the ABSOLUTE path from `source_files()`. The allowlist is a
set of provider module names - `slack` among them - so ANY directory
anywhere above the repository could satisfy it. Measured 2026-10-13: a
worktree at `.../scratchpad/wt-slack-24h` exempted **258 of 258 source
files**, against 25 of 258 from a neutral path. The guard reported green
while guarding nothing, and a whole suite run had to be discarded.

## THE RULE

A file is exempt when its OWN BASENAME contains an allowed token. Not the
absolute path, and not the path relative to the root either: a directory
is not a module, so no directory name - chosen by a person, a worktree
tool or a CI runner - can widen the exemption.

Measured equivalence at the time of the change, on a neutral path:
absolute 25, relative-to-root 25, basename 25, and basename == relative
exactly. So this tightens the SCOPE without changing which files in the
repository are exempt today.
"""
import os


def is_exempt(path, allowed):
    """True when this file's own name carries an allowed token.

    `path` may be absolute; only its basename is consulted, which is the
    whole point.
    """
    name = os.path.basename(str(path))
    return any(token in name for token in allowed)


def offenders(hits, allowed):
    """Filter `(path, lineno, line)` hits down to the non-exempt ones."""
    return [(p, i, line) for p, i, line in hits
            if not is_exempt(p, allowed)]


def exempt_count(paths, allowed):
    """How many of `paths` this rule exempts. For the scope control."""
    return sum(1 for p in paths if is_exempt(p, allowed))


def would_absolute_path_widen(paths, allowed, prefix):
    """THE CONTROL FOR THE CONTROL.

    Returns `(exempt_under_rule, exempt_if_absolute_were_used)` for the
    same file list re-rooted under `prefix`. A sound rule gives the same
    first number for every prefix; the second number is what the old
    absolute-path filter would have produced and is there to prove the
    hole was real rather than theoretical.
    """
    moved = [os.path.join(prefix, os.path.relpath(p, os.path.commonpath(
        [os.path.abspath(p) for p in paths]))) if len(paths) > 1
        else os.path.join(prefix, os.path.basename(p)) for p in paths]
    under_rule = exempt_count(moved, allowed)
    under_absolute = sum(1 for p in moved
                         if any(t in p for t in allowed))
    return under_rule, under_absolute
