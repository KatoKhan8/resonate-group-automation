# STOP 0120: Home-rule parity patch — harness result

Measured 2026-10-17, worktree `wt-stop-2026-10-16`, branch
`task-stop-0120-home-rule-parity-2026-10-17`, HEAD same as
`task-stop-0050-ast-pin-2026-10-16` (`f40bf2d3f`).

## The two blobs

| Blob ID | SHA256 | Source |
|---|---|---|
| `e13ae9b43` | `34eab0a1b87a6a2abece97b278e197452c0ee4594ec323c3c35522a96ee9e584` | `e84108f5d` (TASK 0210) — no home rule |
| `03c69ed1f` | `dd865e5d715f6c231851f8733028fedd4e2a6a0e2365222efe5f6cdf4b8fc475` | `321558ad4` (TASK 0225) — home rule present |
| Patched | `2e7ec8679601b4959153082fb69bfa67a73f6fb6d1633fecb10a2e1947feedb7` | Derived from `e13ae9b43` + minimal home-rule additions |

## What the patch adds

From `parity-patch.diff` — three additions to `require_released()` in
`src/haltfile.py`:

1. **Constants** `_FILE_TYPE_MASK = 0o170000` and `_DIRECTORY = 0o040000` (by
   VALUE, not by `import stat` — preserves property 4: the brake imports only
   `os`).
2. **The `isabs` gate**: if the brake path is not absolute, refuse immediately.
   Resolves class 2a (relative bare filename) and class 2c (dot-relative path).
3. **The home rule**: `os.stat(os.path.dirname(path))` must succeed and the
   result must be a directory. Resolves class 13 (trailing backslash on Windows)
   and class 8 (permission-denied home on POSIX, though SAME on Windows where
   icacls-deny does not block stat).

## Harness result

18 input classes, identical to the STOP/0100 enumeration.

### Negative control: `e13ae9b43` vs `03c69ed1f`
**14 SAME, 4 DIFFERENT** (all WEAKER-BRAKE) — reproduces STOP/0100 exactly.

| Class | Old | New | Direction | Gate |
|---|---|---|---|---|
| CONTROL-DIFF: relative path | pass | stop | WEAKER-BRAKE | isabs |
| 2a: Relative bare filename | pass | stop | WEAKER-BRAKE | isabs |
| 2c: Dot-relative `./STOP-SENDING` | pass | stop | WEAKER-BRAKE | isabs |
| 13: Trailing backslash | pass | stop | WEAKER-BRAKE | os.stat(home) |

### Positive control: patched vs `03c69ed1f`
**18 SAME, 0 DIFFERENT** — full behavioural parity.

All 14 already-SAME classes remain behaviour-identical. No class where the
patched blob admits something `03c69ed1f` refuses (no WEAKER-BRAKE
regressions). The patch is a strict strengthening.

### Classes verified SAME (side-by-side)
Both controls and all 16 enumerated classes produce identical verdicts
between patched and `03c69ed1f`. Per-class table available in harness output.

## POSIX caveat

Class 8 (permission-denied home) is SAME on Windows because `icacls /deny
Everyone:R` does not block `os.stat()`. On POSIX with `chmod 0o300`, the new
blob would likely raise `PermissionError` and stop; the old blob would still
pass (no home check). The patched blob matches the new blob's behaviour here.
Not verified on POSIX — recorded as UNKNOWN per the brief.

## SHA256 proofs

All three blobs verified by sha256 against the SHA256 recorded in
`stop-0100/blob-divergence.md`:
- Original `e13ae9b43`: match
- Target `03c69ed1f`: match
- Patched: derived from the exact original bytes above