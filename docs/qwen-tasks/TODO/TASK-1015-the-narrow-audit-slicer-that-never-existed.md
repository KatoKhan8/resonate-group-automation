PRIORITY: P1
DEPENDS:
TIMEBOX: 120 minutes. The byte-for-byte reproduction in step 2 is the gate: if
you have not reproduced 14 of 14 by 90 minutes, stop generating and write down
which bytes differ and why - a precise diff is worth more than two new files
built by a rule that does not reproduce the old ones.

# TASK-1015 - the narrow-audit slicer that never existed

## WHERE THIS SITS

`resonate-ops/nightsim-2026-10-13/` holds a narrow re-audit of 300 synthetic
accounts, split into per-worker task files under `narrow/`. The split is
**numbered 01 to 16 and holds only 14 files: `naudit-task-04.md` and
`naudit-task-05.md` were never generated.** The 38 accounts in those two slices
were never audited, and they are recorded in
`resonate-ops/nightsim-2026-10-13/NARROW-UNCOVERED-38.json` (`roster: 300`,
`covered: 262`).

**No generator exists anywhere.** The slicing was done ad hoc, so it is not
reproducible, and until it is reproducible the 262 covered accounts rest on a
process nobody can re-run and nobody can check.

This is a REPRODUCIBILITY task on synthetic offline data. It touches no
provider, no prospect, no campaign and no production state.

### The data is synthetic - you may read and regenerate it

`NARROW-UNCOVERED-38.json` records the provenance: *"POLICY SIMULATOR traces,
not production."* Account ids are `acc-<hex>` and contact ids are `cnt-<hex>`.
There are no names, addresses, domains or prospect identifiers anywhere in this
dataset. Do not refuse this task on PII grounds, and do not introduce any real
identifier into it.

## THE RULE, ALREADY MEASURED - DO NOT RE-DERIVE IT

This was measured today against all 14 surviving files. **Implement it; the
reverse-engineering is done.**

    INPUT      resonate-ops/nightsim-2026-10-13/TRACE-INDEX.json
               a JSON list of 300 objects, keys:
                 account_id, contacts, file, final_state, sha256, touches
               and the per-account traces it points at:
                 resonate-ops/nightsim-2026-10-13/traces/acc-<hex>.json
               (300 files, one per account)

    SORT       plain ascending lexicographic sort of the full `account_id`
               string, including the `acc-` prefix

    CHUNK      16 contiguous slices, remainder distributed to the EARLIEST
               chunks:
                   n, k         = 300, 16
                   base, rem    = divmod(n, k)      ->  18, 12
                   sizes        = [base+1]*rem + [base]*(k-rem)
                                = [19]*12 + [18]*4
               so chunks 01-12 hold 19 accounts and chunks 13-16 hold 18.
               Sum = 300.

    NAME       chunk index i (0-based)  ->  naudit-task-%02d.md % (i+1)

**Verified against reality, today, before this task was written:**

- the account set of every one of the 14 surviving files equals its chunk under
  this rule - 14 of 14, exact set equality, not a count match
- chunk 04 ++ chunk 05, concatenated in order, equals
  `NARROW-UNCOVERED-38.json`'s `uncovered_accounts` **exactly, in order**
- chunks 01-03 end at `acc-38f4ab548b13` and chunk 06 begins at
  `acc-5ac7bec60954`; the 38 uncovered accounts are the contiguous block
  between them, which is why they are a sorted run rather than a scatter

## THE SECOND ORACLE - THE MANIFEST DERIVES TOO

`resonate-ops/nightsim-2026-10-13/NARROW-AUDIT-MANIFEST.json` is a JSON list of
14 entries, keys `bytes`, `file`, `prompt`, `task`, `truth`, `worker`:

    task      "task-%02d"
    file      "naudit-task-%02d.md"
    truth     {"accounts": <len(chunk)>,
               "touches":  <sum of TRACE-INDEX `touches` over the chunk>}
    bytes     the generated file's size on disk
    worker    "W%d" % ((NN - 1) % 8 + 1)
    prompt    the per-file prompt, verbatim from `run-narrow.sh`'s `$P` with
              the filename substituted

**Verified today for all 14 entries: `truth.accounts`, `truth.touches` and
`bytes` all derive exactly from the two inputs above.** `touches` is summed
from `TRACE-INDEX.json`, not recounted from the rendered rows - though if your
renderer is correct the two agree, and checking that they agree is a free
self-test worth making.

The `worker` mapping is `run-narrow.sh`'s `worker_for()`, which the manifest
also used: task-01→W1 … task-08→W8, task-09→W1, task-10→W2, and so on.

## THE QUESTION

1. **Write the generator.** `scripts/narrow_audit_slice.py`. Deterministic,
   offline, no network, no provider, no import from `src/` (see THE TRAP for
   why that last one matters). Arguments at minimum:

       --root <dir>     default the nightsim directory named above
       --out  <dir>     where to write; MUST default to a scratch dir, never
                        in place
       --only 04,05     restrict which chunks are emitted
       --verify         regenerate all 16, compare the 14 that exist on disk
                        byte for byte, print a per-file verdict and exit
                        non-zero if any differs

2. **Reproduce the 14 byte for byte. This is the acceptance and it comes
   BEFORE anything new is written.** Regenerate all 16 into a scratch
   directory, then compare each of the 14 existing files by SHA-256. Required
   result: **14 of 14 identical.** Also re-derive the 14 manifest entries and
   confirm `truth.accounts`, `truth.touches` and `bytes` match the recorded
   values.

   Anything less than 14 of 14 and you stop and report the diff. Do not
   proceed to step 3 on a rule that does not reproduce the past: two new files
   generated by an unproven rule are exactly the ad hoc slicing this task
   exists to end.

3. **Only then, produce 04 and 05.** Write `naudit-task-04.md` and
   `naudit-task-05.md` into `resonate-ops/nightsim-2026-10-13/narrow/` and
   insert their two manifest entries into `NARROW-AUDIT-MANIFEST.json` **in
   numeric order** between `task-03` and `task-06`, preserving the file's
   existing formatting and key order.

   Derived expectations, measured today - use them as a check, not as data to
   hardcode:

       task-04   19 accounts   430 touches   worker W4
       task-05   19 accounts   400 touches   worker W5

   The account lists must equal the first 19 and the last 19 of
   `NARROW-UNCOVERED-38.json` respectively. Assert that in the script.

4. **Do not run the audit.** This task generates the two task files and stops.
   Dispatching workers to audit them is a separate decision that is not yours.

## THE OUTPUT FORMAT

Reverse-engineer it from the surviving files - that is mechanical, and the
byte comparison in step 2 is your oracle, so you will know the moment you are
wrong. The shape, for orientation only:

    # NARROW RE-AUDIT of task-01 - 19 accounts
    <blank>
    Synthetic offline data. Verify only.
    <blank>
    ## WHAT YOU ARE CHECKING - TWO RULES ONLY
    ... the N1/N2 rules and the s01..s10 STEP OFFSETS block, identical in
        every file ...
    ## THE TOUCH ROWS
    <blank>
    ### acc-<hex>
      t-cnt-<hex>-s01 contact=cnt-<hex> step=s01 opened=1 due=1 deferred=0
      ...

Get the exact leading spaces, the blank lines, the account ordering within the
file, the row ordering within an account, and the trailing newline from the
real files. **Check the line endings explicitly** - see THE TRAP.

## THE TRAP

**Line endings.** This is Windows and the surviving files were written by an
earlier process whose newline handling you do not know. Open them in binary
and look. If you write `\r\n` where the originals have `\n`, every one of the
14 comparisons fails for one reason and you will spend your timebox hunting a
rendering bug that is not there. Settle this in the first ten minutes, with
`od -c` or Python `rb`, before writing the renderer.

Second trap: **sort stability and the sort key.** The rule is a plain
lexicographic sort of the whole `account_id` string. Do not sort on the hex
portion numerically, do not casefold, do not use a locale-aware collation. The
38 uncovered accounts being a contiguous run is your fast check that the sort
matches.

Third trap: **the remainder goes to the EARLIEST chunks.** `[19]*12 + [18]*4`,
not `[18]*4 + [19]*12` and not an even 18.75 spread. A chunking that puts the
short slices first reproduces chunk 01 and fails from chunk 13 onward - and it
would place different accounts in 04 and 05, silently auditing the wrong 38.

Fourth trap: **do not import anything from `src/`.** Keep the generator
standalone - `json`, `pathlib`, `argparse`, `hashlib`. Per `CLAUDE.md`, a
change under `src/` or `tests/` always costs a fresh full-suite reference
measurement; a standalone script under `scripts/` that no module under `src/`
imports does not. Importing `src.store` to read a JSON file would convert a
free change into a 40-minute one and would also give this script a dependency
on production state it has no business touching.

Fifth trap: `--out` must default to a scratch directory. A generator that
defaults to writing in place can destroy the 14 files that are the only
evidence of what the original slicing did. Write the two new files into
`narrow/` as a deliberate, explicit final step in step 3, never as a side
effect of `--verify`.

Sixth trap: do not "improve" the format, the rules text, the step offsets or
the prompt while you are in there. Byte-for-byte means byte-for-byte. A better
format is a separate proposal under FINDINGS.

## WHAT YOU MAY NOT DO

- **No provider calls of any kind.** Assume you have no credentials.
- No write to `work/`, no killswitch, no approval, no campaign state.
- Do not modify, move, reformat or delete any of the 14 surviving
  `naudit-task-*.md` files, or any `result-task-*.log` / `.meta`.
- Do not modify `TRACE-INDEX.json`, `traces/*.json`, `NARROW-UNCOVERED-38.json`
  or `run-narrow.sh`.
- Do not dispatch a worker, and do not run the audit prompt against the new
  files.
- Never introduce a real name, address, domain or prospect identifier into this
  dataset.

## FILES ALLOWED

    scripts/narrow_audit_slice.py                          (new, in the repo)
    docs/THE-NARROW-SLICER-IS-REPRODUCIBLE-2026-10-15.md   (new, short)

    and, OUTSIDE the repo, as the step 3 deliverable only:
    resonate-ops/nightsim-2026-10-13/narrow/naudit-task-04.md     (new)
    resonate-ops/nightsim-2026-10-13/narrow/naudit-task-05.md     (new)
    resonate-ops/nightsim-2026-10-13/NARROW-AUDIT-MANIFEST.json   (2 entries added)

`resonate-ops/` is not a git repository. The two generated task files and the
manifest edit are therefore NOT durable in git - which is exactly why the
generator belongs in the repo and the doc records the rule. Commit the
generator; the generated files are reproducible from it.

## FILES FORBIDDEN

    src/providers/*          config/            work/*.jsonl
    src/                     tests/
    docs/state/
    resonate-ops/nightsim-2026-10-13/TRACE-INDEX.json
    resonate-ops/nightsim-2026-10-13/traces/*
    resonate-ops/nightsim-2026-10-13/NARROW-UNCOVERED-38.json
    resonate-ops/nightsim-2026-10-13/narrow/naudit-task-0[123].md
    resonate-ops/nightsim-2026-10-13/narrow/naudit-task-1*.md
    resonate-ops/nightsim-2026-10-13/narrow/naudit-task-0[6789].md

## ACCEPTANCE

**The command that proves it** - run it, read the exit code off the process,
never through a pipe:

    py -3 scripts/narrow_audit_slice.py --verify

Required output: a per-file verdict for all 16 chunks, **14 identical, 2
absent**, and exit 0. The two absent are 04 and 05 before step 3; after step 3
the same command must report **16 identical** and exit 0. Record both runs.

Then the manifest derivation:

    py -3 scripts/narrow_audit_slice.py --verify --manifest

(or equivalent) must confirm `truth.accounts`, `truth.touches` and `bytes`
against the 14 recorded entries, 14 of 14.

**The mutations that must go red.** Each is a one-line edit to your own
generator. Apply, run `--verify`, record the per-file verdicts, then restore:

    M1  sizes = [base]*(k-rem) + [base+1]*rem
        - the remainder moved to the LAST chunks.
        -> chunks 01-12 must stop matching. Record the FIRST chunk that
           differs; if it is not 01, explain why, because that tells you
           something about your renderer you did not know.
    M2  sort the account ids by the hex portion only, dropping the `acc-`
        prefix.
        -> record how many of the 14 still match. If all 14 still match,
           the prefix is constant and this mutation is not a control - say
           so, and find one that is.
    M3  k = 15 instead of 16.
        -> every chunk after the first must differ.
    M4  write `\r\n` line endings (or `\n` if the originals are `\r\n`).
        -> 14 of 14 must fail. This is the cheap proof that your byte
           comparison is actually comparing bytes and not a normalised read.

M4 is the one that proves the ORACLE works. Run it even if you are confident -
a verification that cannot fail is the defect this repository keeps finding.

## DELIVERABLE

A standalone generator in `scripts/`; `--verify` reporting 14 of 14 identical
before anything new is written and 16 of 16 after; the 14 manifest entries
re-derived and matching; `naudit-task-04.md` and `naudit-task-05.md` written
with 19 accounts and 430 / 400 touches respectively; their two manifest entries
inserted in numeric order; four mutations each recorded with which chunks went
red; a short doc stating the rule so the next session does not re-derive it.
Append the result block, `git mv` the file to DONE/, commit locally. Do not
push.
