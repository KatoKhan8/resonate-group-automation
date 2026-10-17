# safe_dating_check — a coupling-safe instrument for dating a string in git history

Persisted by **TASK webapp/0400**, 2026-10-17, from `webapp/0380`'s scratch.
**Unreviewed.** This branch exists so the bytes survive a scratch loss; landing
it is the operator's decision, not this lane's.

Provenance, newest first — each is a separate unlanded commit:

| Commit | Task | What it did |
| --- | --- | --- |
| this one | `webapp/0430` | **README only.** Replaced 0400's hardcoded-path finding with 0420's shipped contract (§7), re-pinned the §6 hash table to `d6b922ee278`, corrected §3's changed-line count. No other persisted file touched. |
| `d6b922ee2782d7b2c047e00abd0d4ca9efa86494` | `webapp/0420` | `_resolve_estate(argv)` in `run_arms.py` and `step6_corrections.py` (§7) |
| `ded7a4a91f5757bbc45e147f0ef77ddc7aea8a2f` | `webapp/0400` | persisted 0380's 7 files, the 16 controls and this page |

---

## 1. The question it answers, and the one it refuses

"When did this string first appear in this file?"

The obvious instrument is `git log -S<string> -- <path>`, oldest hit first.
**That instrument is wrong in a way that does not announce itself.** `-S` reports
every commit where the *occurrence count* of the string changed. If a longer
string that happens to CONTAIN your needle already existed in an earlier commit,
the oldest `-S` hit is that earlier commit — and you get a confident, precise,
wrong date for a line that did not exist there.

This was not hypothetical. Arm (a) of the control harness reproduces it against
a real file in this repository: the naive walk dates a clause to
`3a623688973cbcc61ec53d235f3da14b32c72ae7`, where the clause does not exist.

Two rules fix it, and they are separate:

**The parent-count rule.** A `-S` hit at commit C is the INTRODUCTION only if
`count(C's blob) >= 1` AND `count == 0` in **every** parent of C. A root commit
with `count >= 1` and no parents is `CONFIRMED-INTRODUCTION` by definition.

**The uniqueness precheck.** The parent-count rule alone is **not enough**, and
0380's own measurement says so: on arm (a) it still prints the same wrong commit.
So before any walk, count the needle in the blob you are dating **from** (the
reference). If it occurs more than once, two different pieces of text satisfy it
and no dating of either is trustworthy — **refuse**.

> A refusal is the product. It is not a failure of the instrument and it is
> never rounded up to an answer.

Counting is **literal non-overlapping byte counting on the raw blob bytes** as
git stores them (`git cat-file blob`), never on a decoded string, so the LF/CRLF
flavour of a blob cannot move the number. Each blob's CR count is printed so its
flavour is on the record.

The instrument is **read-only** against any repository: it runs only
`git rev-parse`, `git rev-list`, `git log` and `git cat-file`. It never writes a
ref, an object or a file in the repository it is measuring.

---

## 2. Files

| File | Role |
| --- | --- |
| `safe_dating.py` | the instrument — precheck, parent-count rule, blob counting |
| `run_arms.py` | the control harness: 3 arms, **16 controls**, builds its own fixture |
| `step6_corrections.py` | an applied use: runs 10 published datings through the instrument and **lists** what would change. Applies nothing. |
| `reference/controls-run-0380.txt` | 0380's recorded harness output (known answer) |
| `reference/step6-run-0380.txt` | 0380's recorded `step6_corrections.py` output |
| `.gitattributes` | pins this directory to `* -text` — no line-ending conversion, see §6 |

`safe_dating.py` is **0380's exact bytes**, hash-verified on copy (§6) — not
edited, reformatted or "improved" in the move.

`run_arms.py` and `step6_corrections.py` were 0380's exact bytes as persisted by
0400, and were then edited **once**, by **webapp/0420**, for one reason: to
resolve the estate they read instead of hardcoding it (§7). Their hashes in §6
are therefore **0420's, not 0380's**, and the table says which is which. Nothing
else in either file changed — not the arms, not the controls, not the counting.

**There are no stored fixture files, and that is deliberate.** `run_arms.py`
calls `build_fixture()`, which `rmtree`s and rebuilds an 8-commit synthetic repo
from scratch on every run, with fixed author/committer identity, fixed dates and
`core.autocrlf=false`. Its commit SHAs are therefore byte-stable:
HEAD (the merge commit `M`) is always
`e4fdb9187f7ee95d0fef45592539fdc0d58612dc`. A stored fixture would be a second
representation of the same truth that could drift from the generator; the
generator is the authority.

All fixture content is **synthetic**. The only address anywhere in these files is
`fixture@example.invalid`, in the reserved `.invalid` TLD. No client, prospect,
contact, credential or provider data is present.

---

## 3. Running it

### The instrument, directly

    py -3 -B safe_dating.py <repo> <path> <needle> [ref]

* `<repo>` — absolute path to any git repository. Read-only.
* `<path>` — repo-relative path of the file, forward slashes.
* `<needle>` — the literal string, encoded UTF-8. Quote it.
* `[ref]` — **the reference blob**: the commit/ref whose blob the uniqueness
  precheck is run at. Defaults to `HEAD`. See §5 — this argument is load-bearing.

Exit status is **not** the result. Read the verdicts.

### The 16 controls

    py -3 -B run_arms.py                    # zero-config, checked out in-tree
    py -3 -B run_arms.py --estate <path>    # any other estate

Prints every control with `PASS`/`FAIL` and a denominator, ending in
`CONTROLS: 16/16 PASS` and `VERDICT: SAFE-CHECK-BUILT`. Anything other than
16/16 is `FIX-INCOMPLETE`, and the harness says so rather than exiting non-zero —
**check the verdict line, not `$?`.**

Two full runs from the same directory against the same estate commit are
byte-identical to each other. Compared with `reference/controls-run-0380.txt`,
**5 lines** change, and each one has a known cause — measured by webapp/0430
running in-tree at `d6b922ee2782d7b2c047e00abd0d4ca9efa86494`:

| Lines | Which | Moves when |
| --- | --- | --- |
| 4 | `REPO    ...` naming the **fixture's** location | the instrument is run from a different directory (the fixture is built under the script's own dir) |
| 1 | `HEAD        : <sha>` | the **estate's HEAD moves** — it is the clock, not a fault |

0380's reference was captured from `webapp-0380`'s scratch dir with the estate at
`d1fa9a29b03881c237a076120f3437481928b238`; an in-tree run at `d6b922ee278` gives
those 5. **A sixth changed line is a real difference and is a finding.**

> An earlier version of this section said **exactly 4**, and that any fifth line
> was a finding. It was written when `ESTATE` was a hardcoded constant and the
> estate's `HEAD` line was not yet being compared across moving tips. Taken
> literally it would have sent a future lane to investigate the clock.

The 2 `REPO    ...` lines that name the **estate** do *not* change on an in-tree
run, because `_resolve_estate` resolves to the same worktree 0380 hardcoded (§7).
They do change under `--estate <other>`, and that is the argument working.

### The applied list

    py -3 -B step6_corrections.py                    # zero-config, in-tree
    py -3 -B step6_corrections.py --estate <path>

Output is byte-identical to `reference/step6-run-0380.txt` when run against the
same estate commit. It **lists**; it corrects nothing. Applying a correction is
the operator's.

---

## 4. The verdict grammar — closed

Nothing outside these sets is ever printed, and none of them is a synonym for
another.

**Precheck, at the reference blob — three values:**

| Verdict | Meaning | Action |
| --- | --- | --- |
| `UNIQUE-AT-REF` | exactly 1 occurrence | **proceed** to the walk |
| `AMBIGUOUS-NEEDLE` | 2 or more occurrences | **REFUSE** — disambiguate the needle, then re-run |
| `NEEDLE-ABSENT-AT-REF` | 0 occurrences | **REFUSE** — there is nothing to date at this ref |

> **`AMBIGUOUS-NEEDLE` IS A REFUSAL AND IS NEVER A PASS.** It does not mean
> "probably the oldest one", it does not mean "pick the first", and it must not
> be reported as a dating with a caveat. The instrument has measured that the
> question as asked has more than one answer. The only valid next step is a
> **longer, unique needle** — in practice, include the key or the surrounding
> syntax, as `"defect": r"diverged on 2026"` does for the bare
> `diverged on 2026`. Re-running with `precheck=False` to get past it produces a
> number with no warrant behind it.

**Per-commit, for each `-S` hit — two values:**

| Verdict | Meaning |
| --- | --- |
| `CONFIRMED-INTRODUCTION` | count >= 1 here and 0 in every parent (or: count >= 1 at a root commit) — this commit introduced it |
| `MOVED-COUNT-ONLY` | the count changed here, but at least one parent already had it — **this is not an introduction** |

`NAIVE-OLDEST-HIT` is also printed. It is the **old instrument's answer, shown
for contrast**. It is never this instrument's verdict and must not be quoted as
one.

**`step6_corrections.py` per published dating — four values:**
`UNCHANGED`, `WOULD-MOVE`, `REFUSED-BY-PRECHECK`, `AMBIGUOUS-RESULT`.
`REFUSED-BY-PRECHECK` means the published dating is **not derivable from that
needle** and must be re-derived from a unique one — it does not mean the
published dating is wrong, and it does not mean it is right.

**Harness:** `SAFE-CHECK-BUILT` (16/16) or `FIX-INCOMPLETE`.

---

## 5. The reference-blob requirement

The precheck is run **at one named ref**, and uniqueness is a property **of that
blob**, not of the history. A needle unique at `HEAD` may occur twice three
commits back. So:

* **Name the ref explicitly** and record it with every verdict. `HEAD` is a
  moving target; a verdict recorded against "HEAD" with no sha is not a
  measurement.
* **Pass a ref, not a blob id.** The argument is handed to
  `git rev-parse <ref>:<path>`, which requires something that resolves to a
  commit or tree. 0390 recorded the trap: a brief named
  `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2` as "the reference blob" — it is a
  **commit**, and one that does not contain the file in question. The
  instrument's answer there was `NEEDLE-ABSENT-AT-REF`, which is the correct
  refusal and is **not** the same statement as "the needle is not in this
  repository".
* **`NEEDLE-ABSENT-AT-REF` is frequently a wrong ref, not a missing string.**
  Check that the ref contains the path before concluding anything about the
  needle.

---

## 6. Byte identity — how a future lane proves it is running the same instrument

Recorded by webapp/0400.

**The line endings in this directory are MIXED, on purpose, and that is the
whole reason `.gitattributes` says `* -text`.** Measured 2026-10-17:

| | flavour | why |
| --- | --- | --- |
| `*.py`, `*.md`, `.gitattributes` | **LF** (CR=0) | this worktree was created with `GIT_CONFIG_SYSTEM` neutralised, so `core.autocrlf` did not apply |
| `reference/*.txt` | **CRLF** | Python's `print()` emits `\r\n` to a redirected file on Windows — these are 0380's captured stdout |

This repository has `core.autocrlf=true` in the shared `.git/config`. Left to
itself git would have done **both** damaging conversions: normalised the CRLF
reference outputs to LF on commit, and rewritten the LF scripts to CRLF on
checkout. Either one silently changes a sha256 that exists to prove the bytes
are unchanged. `* -text` disables conversion in both directions, so **blob bytes
== disk bytes == 0380's bytes**, and one table serves both checks.

Verified at commit time, all seven files, `git cat-file blob` against
`sha256sum` on disk: **7 of 7 MATCH**. Re-verified **7 of 7 EQUAL** by
webapp/0430 at `d6b922ee2782d7b2c047e00abd0d4ca9efa86494`.

Check against the blob — it is the authority, and it is what survives a bad
checkout:

    git show <commit>:tools/safe_dating_check/safe_dating.py | sha256sum

**A hash table is pinned to a commit.** This one is measured at
`d6b922ee2782d7b2c047e00abd0d4ca9efa86494` — 0420's tip, the commit that
introduced `_resolve_estate`:

| File | bytes | flavour | whose bytes | sha256 (blob AND disk — identical) |
| --- | --- | --- | --- | --- |
| `safe_dating.py` | 8739 | LF | 0380 | `a119883439b30e446eca934ad8b442a91b1be573242b02bfcd94fdd45acef527` |
| `run_arms.py` | 17098 | LF | **0420** | `e1118508f72a6b3c858b07a3398ad8d569c63eaba6f54173882460e7782d48bc` |
| `step6_corrections.py` | 8477 | LF | **0420** | `b76893ff07d9d77189744351babeb7d382a2ac28426a86d0f5e8808a05fbef47` |
| `reference/controls-run-0380.txt` | 19550 | CRLF | 0380 | `c3ea8ad85279496398a93b451ad58f3ca0c67905c11a046d252c9d08385998a6` |
| `reference/step6-run-0380.txt` | 28386 | CRLF | 0380 | `caeac52532ab78741d305628378151251f1df4108cc53a2ec42a097c9a91bb44` |

Three of the five are **0380's own recorded hashes**, re-measured as-found by
0400 before the copy, after the copy, and again from the blob after the commit.
Two are **0420's**, and these are the bytes they replaced — kept so the trail is
auditable rather than overwritten:

| File | 0380/0400 bytes | superseded sha256 | superseded at |
| --- | --- | --- | --- |
| `run_arms.py` | 14910 | `acf1ec275826a1b30d8e37577757618fe08fa7282c49f3e82b86879cbe30ec21` | `d6b922ee278` |
| `step6_corrections.py` | 6289 | `c6463aaf25ea220576f20702c7781bb718e1f283ea3741ff20ed53e7ad7f1b52` | `d6b922ee278` |

If `git show` gives you a hash that is in **neither** column for one of these
files, the bytes are not accounted for: you are running neither 0380's
instrument nor 0420's, and no result you get from it may be compared to 0380's,
0390's or 0420's.

> **This table was a trap between `d6b922ee278` and this commit**, and the trap
> is the reason the "whose bytes" column exists. 0420 changed two of the five
> files and did not update the table, so §6 still carried 0400's hashes while
> telling the reader that a mismatch means *"you are not running 0380's
> instrument"*. At 0420's tip that sentence **falsely condemned the correct
> instrument** for 2 of 5 files. A byte-integrity table that is not re-measured
> on the commit that changes a file does not detect drift — it manufactures it.
> Measured by webapp/0430: 3 of 5 rows matched, 2 of 5 were stale in both size
> and hash.

If you ever see one of the `.py` files come out of a checkout at a *larger* byte
count than the table, you have a CRLF rewrite: `.gitattributes` was dropped,
bypassed (`git archive` applies conversion where `cat-file` does not), or
overridden. Restore from `git cat-file blob`, not from the working tree.

---

## 7. For anyone editing this

**The pyc rule.** Python validates cached bytecode on mtime **and size**, and
mtime granularity is a whole second — so a same-second rewrite of equal length
reads as a no-op and you run the OLD code while reading the NEW source. Delete
`.pyc` and `__pycache__` **on every `.py` write and on every revert, in both
directions**, or always invoke with `py -3 -B`. **No `.pyc` is ever committed.**

**How `run_arms.py` and `step6_corrections.py` find the estate they read.**
Both resolve it through `_resolve_estate(argv)`, shipped by **webapp/0420** in
`d6b922ee2782d7b2c047e00abd0d4ca9efa86494`. The contract, in order:

1. an explicit **`--estate <path>`** argument always wins;
2. otherwise the **nearest git work tree above the script's own file** — which
   is the zero-config answer when the instrument is checked out in-tree at
   `tools/safe_dating_check/`;
3. otherwise a **loud `SystemExit`**, naming the argument and the directory
   walked.

A path that **is not a git work tree is a refusal too**, and **there is no cwd
fallback** — an instrument that dates commits must never guess which repository
it is dating. `--estate` with no path after it is also a refusal.

Arm (a)'s 6 controls and the whole of step 6 read the resolved estate; arms (b)
and (c) and their 10 controls build their own fixture and need no estate at all.
So on a machine where neither rule 1 nor rule 2 can be satisfied, the
instrument **refuses by name** rather than reading the wrong repository or
silently reporting arm (a) as unrunnable.

> **This section recorded the opposite until this commit, and the correction is
> the point.** 0400 persisted 0380's hardcoded
> `ESTATE = r"...\wt-webapp-2026-10-15"` and filed the consequence here as an
> **open finding** — "left unedited on purpose; a future lane that needs
> portability should parameterise it". 0420 shipped exactly that, and the
> finding stayed on this page for one commit, telling every reader that the fix
> was still owed. **A finding that has been fixed is not a finding; left
> standing, it is a false statement about the code** — and this file is the
> first thing a future lane reads. Corrected by webapp/0430 in a README-only
> commit; the 6 other persisted files are byte-identical to `d6b922ee278`.

**Never `sed` a Windows path into one of these files.** `sed` interprets the
backslash escapes: `\r` becomes a literal CR and `\c` / `\U` are eaten. 0380 lost
time to exactly this, and the injected CR is invisible in normal terminal output
— it shows up under `cat -A`. Pass paths as `sys.argv`, or rewrite the file.

**Do not relax the precheck to make a dating come out.** Widening a guard so an
answer appears is how the wrong commit gets published with confidence. If the
precheck refuses, the needle is the thing to change.
