# MERGE 0280 — `MISMATCH:265!=261` is a units error, and the block declares the bridge

ADR 0280. **Advisory only: nothing here is wired, and nothing here is merged.**

    tree        wt-merge-2026-10-16
    branch      task-merge-0280-units-reconcile-2026-10-17
    the change  c266b64b8a3b6d579c2050a58c1b465899e1683e
                the reader, and the 11-arm control harness beside it
    the harness 932246a13e21f0c8e37ced2819170bcc0a986629
                prints refs-scanned / carrier-refs / distinct-tips rather
                than labelling the first of those "carrier refs"
    this file   one of three commits on the branch; a SHA cannot name the
                commit that carries it, so run
                `git log --oneline c266b64b8..HEAD`
    base        task-merge-0270-provenance-reader-2026-10-17
                @ 4e5d3ba65e4ec79dd477bd3f7529ce713dfab6de
    origin/master b1f290c847eb2500b7eb39987ac34f6d6a8d00d2 (unchanged)

Every number below is reproduced by the harness at `932246a13` unless it names
a source of its own. The population figures 1181 / 62 / 36 are that harness's
own header. At `c266b64b8` the same three numbers are printed, but the first of
them is labelled `carrier refs` - which is why the label fix is a separate
commit and not part of the change under review.

---

## 1. The one question, answered

**UNIT-ERROR at every tip, and TRUE-STALENESS at none.**

| Tip | Refs carrying it | before | after the spec |
| --- | --- | --- | --- |
| `f1552d4ec644d1e6c49c91ac0018c1efb045f2fb` | `refs/heads/task-suppression-0395-both-guards-2026-10-16` | `MISMATCH:265!=261` / 3 | `VALID` / 0 |
| `bbb18bd13d4168ae5dfaa5e8bb35018f680d2ed6` | `refs/heads/task-suppression-0398-bounce-unknown-2026-10-16` | `MISMATCH:265!=261` / 3 | `VALID` / 0 |
| `0efe2fef959d9ef352b920d9d895f530a18d017a` | `refs/remotes/origin/task-gates-0070-prove-guard-fails-2026-10-16` | `MISMATCH:265!=261` / 3 | `VALID` / 0 |
| `9ecad20e7a937b44b7d3856e4397ce0839f5fac3` | `refs/heads/task-pool-0160-fallback-handler-2026-10-17` | `MISMATCH:265!=261` / 3 | `VALID` / 0 |

**And the denominator is not four.** Both lanes reported "4 of 4 carrier tips".
Measured here: 1181 refs scanned, **62 carry `.github/suite-baseline.txt`, over
36 distinct tips**, all carrying the **same** blob. Before the change all **36 of
36** read `MISMATCH:265!=261` exit 3; after it all **36 of 36** read `VALID` exit
0. Three of the brief's four are not even maximal tips — `f1552d4ec`,
`0efe2fef9` and `9ecad20e7` are ancestors of other carrier tips, and only
`bbb18bd13` is maximal. Four was the set that had been named, not the set that
exists, which is how a denominator shrinks without anyone deciding it should.

Of those three numbers only the FIRST moves, and it moves for reasons that are
not this repository's: the sweep taken before this branch was pushed read
**1180** refs, the two harness runs after it read **1181** - the one-ref
difference being this lane's own
`refs/remotes/origin/task-merge-0280-units-reconcile-2026-10-17` - and a third
run taken while this report was being written read **1182** with no ref of this
lane having moved in between. The two that ARE the population - 62 carriers, 36
distinct tips - are equal in all three runs. Quoting a ref count as if it were a
property of the repository is the same mistake in a smaller place as quoting 4
as the size of a set of 36.

The block is **arithmetically honest in its own unit**. The reader compared two
different units. The evidence for that, and not merely the assertion of it, is
section 2.

---

## 2. Re-derived from the CI bytes

Read-only from `resonate-ops/pilotcaps-ci-2026-10-15/`, sha256 of each log
asserted before and after. Neither lane's prose was taken as a measurement.

    X2-offline-suite_run.log  3015774 B  CR 25388
        sha256 521c35aeecfcea0c82d67f54dc60627b38437584e0ebe5b2639237bb782f9275
    X1-plain-suite_run.log    4142284 B  CR 33181
        sha256 937c75b9ac1a7dc931befb2ca186a22265f2363c9a020041187db390dd612ef4

| Quantity | X2-offline (the log the block names) | X1-plain (the control run) |
| --- | --- | --- |
| `FAILED (...)` line | `failures=172, errors=93, skipped=17, expected failures=18` | `failures=180, errors=91, ...` |
| closing lines under `^(FAIL\|ERROR):` | **265** = 172 FAIL + 93 ERROR | **271** = 180 + 91 |
| `_SUMMARY`-keyed unique names | **261** | **267** |
| `run_suite._parse_failures` unique names | **261** | **267** |
| absorbed | **4** | **4** |

`_parse_failures` and `_SUMMARY` were **exec'd out of `origin/master`'s blob of
`scripts/run_suite.py`** (blob `4ca2763b69a5d514a828034ca78a81b3d8d0dc5a`,
sha256 `71ef60a6e5d42ac275045af129f1a5a642ac81b3cc810e92845ba7ef6404fd4e`), not
retyped — the worktree's own copy is 171 lines ahead of master and would not
have been the authority the block was measured against.

### The 4 absorbed events are one subTest

`_SUMMARY = ^(FAIL|ERROR):\s+\S+\s+\(([^)\s]+)`. Group 2 stops at the first `)`,
so a closing line's second parenthetical never reaches the key:

    FAIL: test_the_lead_carries_one_subject_and_a_body_per_step
          (test_a_threaded_sequence_is_threaded_at_every_length.TheInvariantHoldsAtEveryLength.test_the_lead_carries_one_subject_and_a_body_per_step)
          (steps=N)

Five such lines exist in the X2 log, `(steps=2)` through `(steps=6)`, all
`FAILED`. All five key to the same dotted path; `kinds.setdefault` keeps the
first; the other four are no-ops. **5 events, 1 name, 4 absorbed.**

    265 events − 4 = 261 names      residual 0

### The file is exactly that log's collapse — both directions

The negative half of the comparison, which is what makes this a units error
rather than a stale block:

| Comparison | file → log | log → file |
| --- | --- | --- |
| names vs `_parse_failures` (X2) | **0** | **0** |
| names vs `_SUMMARY` keys (X2) | **0** | **0** |

Nothing in the file is absent from the log, and nothing in the log is absent
from the file. The block names the right log, the right SHA and the right
runner counts, and its 261 names **are** that log's collapse. There is no
residue for staleness to live in.

### Why this is a repair and not a weakening

Check (d) as it stood could not pass on **either** measured run — 265≠261 and
271≠267, the same 4-event shape twice. **A check that is red on every honest
input carries no information.** Removing the units error removes no power from
the reader; it restores the check the error had emptied. Section 5 shows the
check is live afterwards, with two mutants killed.

---

## 3. The spec, byte-exact

One substantive change — the reader's comparison basis — **plus the declaration
that basis needs**, because the block is the only place the missing term can
honestly live.

### 3a. The block gains one field

Inserted immediately after the `runner` field of the provenance block in
`.github/suite-baseline.txt`. Committed blob
`061ea22b4d8b03afd6e591baf3e46fbfeefb854a`, 30674 B, sha256
`f3fbf08fd5e16394afa42164e8f4d8b28c6a8a23e4513bbe7323df87c28be3f2`.

    #   collapsed  4 - one parameterised subTest printed five closing FAIL
    #              lines, `(steps=2)` through `(steps=6)`, and
    #              `_parse_failures` keys all five by the dotted path, so
    #              these 265 closing lines are 261 distinct names

Amended: **30936 B, +262 bytes**, sha256
`1bb613a4deb7630d450f247de33510aa26dfa5a566985c999885b2ac2b18f6ee`.
**261 names, byte-identical before and after** — the repair moves no name.

### 3b. The reader's comparison basis

    before   failures(172) + errors(93) = 265              vs names 261   → MISMATCH
    after    failures(172) + errors(93) = 265 events
             − collapsed(4)               = 261 names      vs names 261   → OK

`collapsed` is added to `FIELD_KEYS`, parsed by a new `COLLAPSED = re.compile(r"(\d+)")`
(leading integer of the value), and subtracted. The verdict's left-hand number
is the **name side**, so the printed verdict is the comparison actually made:

    check d    arithmetic  OK - failures(172) + errors(93) = 265 events
               - collapsed(4) = 261 name(s) vs parsed unique names 261
    VERDICT    VALID

### 3c. Fail closed on an undeclared bridge

No `collapsed` field means a declared collapse of **zero** — the *stricter*
reading, and the printed line says so rather than defaulting quietly:

    check d    arithmetic  MISMATCH - failures(172) + errors(93) = 265 events
               - collapsed(0, no `collapsed` field declared) = 265 name(s)
               vs parsed unique names 261

So a block that has not stated its units gets no benefit of the doubt: the
committed block unamended still reads `MISMATCH:265!=261`.

---

## 4. Why the block-only variant is refused

The brief allowed either half. A block-only change exists, and it is the one
thing this file must not do.

The reader's event total comes from `RUNNER.search` / `ERRORS.search` over the
`runner` field's value. Editing that field to `failures=168 errors=93` makes the
sum 261 and the reader prints `VALID` — with **no reader change at all**. It is
also a fabricated transcription of a line the X2 log does not contain. The log
says `failures=172, errors=93`, and the block quotes it verbatim as evidence.

**A provenance block that misquotes its own evidence is precisely the failure
the block exists to prevent.** So the missing term is *declared* in a new field
and the reader *subtracts* it, rather than the evidence being bent to fit the
check. `SPEC-PRODUCED`, on both sides of the comparison, for that reason.

---

## 5. Controls — 11 arms, every plant asserted, two mutants killed

`scripts/check_baseline_provenance_controls.py`, committed on the branch. It
derives the carrier population and the declared SHA **out of the repository at
run time** — no SHA is written down in it — and asserts each plant applied
before believing the result. Fixtures are written outside the tree.

    OK   committed block, all carrier tips          MISMATCH:265!=261   3
    OK   amended block, all carrier tips            VALID               0
    OK   stale: tip does not contain the SHA        STALE:not-an-ancestor-of-tip  3
    OK   stale: the SHA names no commit             STALE-UNRESOLVED:000...0      3
    OK   stale: block says it was carried forward   STALE:inherited               3
    OK   mismatch: bridge declared, does not close  MISMATCH:262!=261   3
    OK   mismatch: units left undeclared            MISMATCH:265!=261   3
    OK   mismatch: 4 events against 5 names         MISMATCH:4!=5       3
    OK   no block at all                            NO-PROVENANCE       3
    OK   no file at all                             NO-PROVENANCE       3
    OK   repository git cannot be asked about       UNKNOWN:repo-unreadable 2

    11/11 arms as expected

0270's five-arm table is preserved. The arm that matters most is
`mismatch: bridge declared, does not close` (a `collapsed` of 3 against a
measured 4 → `MISMATCH:262!=261`): **it proves the changed reader can still
print `MISMATCH` on a block that declares a bridge**, so the amendment is not a
reader that can only print `VALID`.

### Mutants

| Mutant | Result | Arms that caught it |
| --- | --- | --- |
| `names_side = total` (subtraction dropped) | 9/11 | amended carrier sweep; declared-bridge arm |
| undeclared default `1` instead of `0` | 8/11 | undeclared arm; carrier sweep; 4-vs-5 arm |

Both died for the intended reason and in the directed direction — the mutants
*move the compared number*, and the arms read the moved number.

---

## 6. What is still not seen, and what was found but not repaired

**Named in the reader's own docstring rather than implied.** A block that
declares a `collapsed` it did not measure is internally consistent. This reader
reads a **file**, not the log the block names, so it can only test the block
against itself. That ceiling is unchanged by this repair, and it is why the
harness's arms are the real evidence.

**A defect the controls exposed, reported and NOT repaired.** Arm (a) asks "is
there a provenance block at all?" as a case-folded **substring** test over `#`
lines, so a header that merely uses the word answers the question YES. Measured:

    # failing test names. This file carries no provenance block.
    synthetic_module.SyntheticCase.test_planted_0
    → STALE-UNRESOLVED:      exit 3        (want NO-PROVENANCE)

Not a discovery, and that is the finding: merge/0270 already knew — its commit
message says the absent-block message is written "in words that do not contain
the token the reader looks for". **The mitigation is a wording convention, held
in a commit message, that every future writer has to remember.** It is arm (a),
not the units question, so it is measured in the harness and left undone rather
than smuggled into this diff. Recommended: file in
`docs/state/PROBLEM-REGISTER.md` with the repair — anchor the block marker to
`^#\s*PROVENANCE\b` instead of a substring search — rather than to
`PRODUCT-GAPS.md`, whose own charter is "nothing here is a bug" and this is one.

**`(c2)` is a real, separate finding, and unchanged.** The declared SHA
`4d2d19b9b259cef817869864c9b170b1f1deab75` is **not** an ancestor of
`origin/master`; it is an ancestor of every carrier tip. These names were
measured on a lineage master does not contain. That is a baselines-for-what
question, printed as a WARN, deliberately not judged by the reader, and **not
touched by this change**.

---

## 7. What is deliberately not done

- No `BASELINE_MODE` flip. merge/0270's operator recommendation stands verbatim:
  do **not** flip it, and do not wire the reader yet.
- No CI wiring. The reader remains **advisory and unwired**.
- No merge, no cherry-pick, no push to master. Nothing lands. The branch is for
  review.
- No `.github/suite-baseline.txt` was written. The amended block is produced
  from the committed blob by the documented insertion and its sha256 is stated
  above; whoever lands it lands those 262 bytes over that blob.