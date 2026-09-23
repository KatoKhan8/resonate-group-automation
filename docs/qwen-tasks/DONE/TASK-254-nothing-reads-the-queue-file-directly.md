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

## RESULT

- **STATUS:** DONE
- **COMMIT:** 49330349
- **TESTS:** The two new tests pass:
  - `test_no_src_module_reads_the_queue_file_directly` - AST walk finds only
    `store` calling `queue_path()` and then `open()`/`read_jsonl()` on the result
  - `test_the_direct_reader_exemption_list_has_not_fallen_behind` - both halves:
    nothing unlisted reads the queue, nothing listed has stopped
  - Verified the AST walk catches `open(store.queue_path())`,
    `store.read_jsonl(store.queue_path())`, and does NOT false-positive on
    comments mentioning the pattern
  - Full `test_invariants.py`: 85 tests, 2 pre-existing failures (unrelated:
    ProviderError imports and bison campaign binding)
- **FILES CHANGED:**
  - `tests/test_invariants.py` - added `_ast_contains_queue_path()`,
    `_find_direct_queue_readers()`, `QUEUE_DIRECT_READERS_EXEMPT`, and two
    test methods to `TestTheQueueIsTheOnlyState`
  - `scripts/profile_scale.py` - added EXEMPT comments to two
    `read_jsonl(queue_path())` calls that profile raw primitives
  - `scripts/task191_funnel.py` - replaced direct `open()` parsing with
    `store.use_directory()` + `store.load()`; removed `load_records()`
- **FINDINGS:**
  - `queuejournal` does NOT need an exemption. It receives the queue path as
    a function parameter from `store` - it never calls `queue_path()` itself.
    The AST walk correctly does not match it. The exemption list is just
    `("store",)`.
  - The two `profile_scale.py` direct reads are genuine: they profile
    `refuse_history_loss` and `snapshot.merge_onto` against the raw base file
    that `store.save` passes in production. Switching to `store.load()` would
    measure a Snapshot with journal replay, which is a different operation.
  - Of the 80 `queue_path` references across `src/`, the vast majority are
    `os.path.dirname(store.queue_path())` (wanting the directory) or display
    strings. Only `store.py` itself calls `queue_path()` and then opens the
    result.
- **RISKS:** The AST walk matches `open()` and `read_jsonl()` by function name.
  A module that imports `read_jsonl` under an alias would not be caught. This
  is the same limitation every name-based AST check has, and it is acceptable
  because the convention is to call it as `store.read_jsonl()`.
- **RECOMMENDED CLAUDE ACTION:** Review and merge. The property is now enforced
  and cannot silently regress.
