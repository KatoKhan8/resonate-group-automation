PRIORITY: P2
DEPENDS:

# TASK-254 — the caller survey becomes a test

The SQLite migration is feasible only because **no module under `src/` parses
`work/queue.jsonl` itself.** Surveyed 2026-09-22: of `queue_path()`'s callers
outside `store.py`, 36 use `os.path.dirname(...)` and want only the directory;
the rest use it as a display string, a size for profiling, or a prefix
assertion. The direct readers are:

    scripts/profile_scale.py      read_jsonl(store.queue_path())   x2
    scripts/task191_funnel.py     open(queue_path)
    src/queuejournal.py           open(queue_path)   — store's own sidecar

That is a property the whole design rests on and nothing enforces it. A module
added next week that reads the file directly breaks the migration silently,
and the first symptom is a wrong number in a report.

## Do

1. A test in `tests/test_invariants.py`: no module under `src/` other than
   `store` and `queuejournal` may `open()` or `read_jsonl()` a path resolved
   from `queue_path()`. **Assert on behaviour or the AST, never on source
   text** — this repository has been bitten repeatedly by tests that grep
   source and then fail when somebody writes a comment. Walk the AST for a
   call to `open` / `read_jsonl` whose argument derives from `queue_path()`.
2. Update the two scripts to go through `store.load()`.
   `scripts/profile_scale.py` is measuring file bytes **on purpose** in at
   least one place — read it before changing it and keep what it is actually
   measuring. If it genuinely needs the file, give it an explicit exemption
   with a comment saying why, not a silent pass.
3. The exemption list is asserted the way `SELF_WRITERS` already is, so it
   cannot fall behind the code. Two halves: the list, and a walk that fails
   when something is missing from it.

## Do not

Break what `profile_scale` measures. It is the evidence behind the design's
section 1, and a profiler that stops measuring bytes is worse than no test.
