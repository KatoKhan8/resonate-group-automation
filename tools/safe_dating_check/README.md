# safe_dating_check — a coupling-safe instrument for dating a string in git history

Persisted by **TASK webapp/0400**, 2026-10-17, from `webapp/0380`'s scratch.
**Unreviewed.** This branch exists so the bytes survive a scratch loss; landing
it is the operator's decision, not this lane's.

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

`safe_dating.py`, `run_arms.py` and `step6_corrections.py` are **0380's exact
bytes**, hash-verified on copy (§6). They were not edited, reformatted or
"improved" in the move.

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

    py -3 -B run_arms.py

Prints every control with `PASS`/`FAIL` and a denominator, ending in
`CONTROLS: 16/16 PASS` and `VERDICT: SAFE-CHECK-BUILT`. Anything other than
16/16 is `FIX-INCOMPLETE`, and the harness says so rather than exiting non-zero —
**check the verdict line, not `$?`.**

Two full runs are byte-identical to each other. A run in a different directory
differs from `reference/controls-run-0380.txt` in **exactly 4 lines**, all of
them the `REPO    ...` line naming the fixture's own location. Any fifth changed
line is a real difference and is a finding.

### The applied list

    py -3 -B step6_corrections.py

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
`sha256sum` on disk: **7 of 7 MATCH**.

Check against the blob — it is the authority, and it is what survives a bad
checkout:

    git show <commit>:tools/safe_dating_check/safe_dating.py | sha256sum

| File | bytes | flavour | sha256 (blob AND disk — identical) |
| --- | --- | --- | --- |
| `safe_dating.py` | 8739 | LF | `a119883439b30e446eca934ad8b442a91b1be573242b02bfcd94fdd45acef527` |
| `run_arms.py` | 14910 | LF | `acf1ec275826a1b30d8e37577757618fe08fa7282c49f3e82b86879cbe30ec21` |
| `step6_corrections.py` | 6289 | LF | `c6463aaf25ea220576f20702c7781bb718e1f283ea3741ff20ed53e7ad7f1b52` |
| `reference/controls-run-0380.txt` | 19550 | CRLF | `c3ea8ad85279496398a93b451ad58f3ca0c67905c11a046d252c9d08385998a6` |
| `reference/step6-run-0380.txt` | 28386 | CRLF | `caeac52532ab78741d305628378151251f1df4108cc53a2ec42a097c9a91bb44` |

These five are **0380's own recorded hashes**, re-measured as-found by 0400
before the copy, after the copy, and again from the blob after the commit. If
`git show` gives you a different hash for a file in this table, you are not
running 0380's instrument and no result you get from it may be compared to
0380's or 0390's.

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

**`run_arms.py` and `step6_corrections.py` hardcode an absolute estate path:**

    ESTATE = r"C:\Users\Zvonimir\Desktop\resonate-trees\wt-webapp-2026-10-15"

Arm (a) and the whole of step 6 read that worktree. On any other machine, or
after that worktree is removed, **arm (a)'s 6 controls and step 6 cannot run** —
arms (b) and (c) and their 10 controls are self-contained and still can. This is
0380's byte, left unedited on purpose; a future lane that needs portability
should parameterise it in a new commit rather than silently assume the path
resolved.

**Never `sed` a Windows path into one of these files.** `sed` interprets the
backslash escapes: `\r` becomes a literal CR and `\c` / `\U` are eaten. 0380 lost
time to exactly this, and the injected CR is invisible in normal terminal output
— it shows up under `cat -A`. Pass paths as `sys.argv`, or rewrite the file.

**Do not relax the precheck to make a dating come out.** Widening a guard so an
answer appears is how the wrong commit gets published with confidence. If the
precheck refuses, the needle is the thing to change.
