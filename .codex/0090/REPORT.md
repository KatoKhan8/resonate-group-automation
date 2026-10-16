# TASK 0090 — 0075's clearing rule over a corpus it did not write (LANE-pilotcaps.md)

origin/master at open and at close: `b1f290c847eb2500b7eb39987ac34f6d6d8a8d00d2`
(read-only `ls-remote`; no ref moved, no push, local master divergence is the
operator's).

Measurement inputs, named by sha256:

- `LANE-pilotcaps.md` (the foreign corpus) —
  `70c8190f6e07bf7a23d05a68ee3b2916354cacf6b4d15f5c6b864ce4d2b026da`,
  1,128,659 B / 19,841 lines.
- `LANE-glm.md` (C3's input, bounded at L4219) —
  `5f3fcaaa4941ceab74903be17f532b5fa77f9cc5282f08bfbb7c46ccff900d28`,
  278,978 B / 4,395 lines / CR=2.
- `.codex/0080/classify.py` (UNCHANGED — every verdict came from this file) —
  `8fffb67a5719fafc3111f3c46994013258c288ec3b54a2ac892da7bc61fb2b9d`.
- `.codex/0080/extract.py` (UNCHANGED — C3's instrument) —
  `3857fb61006eda3973bb21c29876e27351f9cd5378319c0955cfc53d70b0dd40`.

Corpus chosen: `LANE-pilotcaps.md` over `LANE-glm-b.md` / `LANE-glm-c.md` —
by density of recorded mutation verdicts (157 verdict-shaped records found by
the adapter before any patch, vs the low tens in the other two lanes' files;
0080's own home corpus is 71). Regions read back, by line range:
L856-879, L1172-1185, L1524x, L1846-1877, L1918-1977, L2500-2515, L2965-2980,
L3930-3945, L4125-4140, L5470-5485, L5920-5935, L6810-6830, L6915-6930,
L7045-7070, L7148-7165, L7335-7380, L7460-7500, L7615-7675, L7840-7870,
L7975-8010, L8275-8300, L8360-8375, L8480-8505, L8535-8545, L8885-8900,
L8965-8980, L9040-9050, L9145-9155, L9250-9262, L9468-9509, L9625-9635,
L9725-9732, L9780-9790, L9815-9825, L10090-10110, L10140-10150, L10225-10240,
L10466-10487, L10505-10515, L10640-10655, L10685-10695, L10795-10810,
L10920-10935, L11000-11010, L11040-11050, L11215-11225, L11385-11395,
L11540-11550, L12055-12090, L12430-12440, L12710-12720, L12915-12925,
L13105-13115, L13595-13605, L14505-14525, L14925-14935, L15242-15259,
L15376-15393, L15445-15455, L15655-15682, L15770-15805, L16140-16155,
L16365-16375, L16690-16775, L17360-17375, L17600-17615, L17785-17795,
L18050-18095, L18275-18290, L18365-18375, L18445-18490, L18785-18795,
L19115-19130, L19175-19190, L19500-19521, L19730-19790 — every excluded and
kept record's span was read from the lane file itself, never from a `.out` or
`DONE\` filename.

## THE TABLE (0080's four columns)

Denominator stated: **160 candidate rows** = 158 records the adapter parsed +
2 refused by the both-vocabulary gate (L5748, L7057, fail-closed). Of the 158:
**76 excluded** (each documented per line; the full ledger is
`run_0090.EXCLUSIONS`, embedded verbatim in `table_result.json`) and
**82 kept**:

| verdict  | n  |                                                    |
|----------|----|----------------------------------------------------|
| SAFE     | 14 | L6815 L6819 L7052 L7366-7370 L16701 L16714 L16733 L19513 L19514 L19780 |
| UNKNOWN  | 67 | see table_result.json / the printed table           |
| AFFECTED |  1 | L6827 (stale marker: "Python reused M6's `__pycache__` for M7") |

**SAFE rate: 14/82 = 17.1% on the foreign corpus vs 30/55 = 54.5% on glm's
own (0080). The rule reads a corpus it did not write at less than one-third
the rate.**

## The answer: convention, partly

The rule's SAFE disjuncts are readable two ways — as EVIDENCE requirements
(a proof the bytes were fresh) or as FORMAT requirements (a clearing fact
recorded in glm's dialect, inside the same clause). On the home corpus the
two are indistinguishable: glm writes the way the rule reads because 0072+
drilled that style. On the foreign corpus they separate. The readback showed
most UNKNOWN rows are not missing evidence — the evidence is recorded one
indent below the verdict row (names, signatures, whole kill-reason blocks),
or stated as a count ("KILLED 7"), or under control-label grammar ("C4a"),
or in verdict words the rule has no vocabulary for ("every one printed
MET — 6 of 6", "kill sets then {3}, {1}, {1}").

The 14 SAFE rows are exactly the ones where pilotcaps happened to use a
glm-compatible form: a section-recorded `PYTHONDONTWRITEBYTECODE=1` protocol
(8 rows: 0235/0236, 0241 §9), a section-recorded per-plant load-proof
paragraph — "the subprocess asserts its own marker is present in
`inspect.getsource(agencydnc._rows_in)` … All three load-proofs passed"
(L16692-16696, verified in the readback; 3 rows), recorded byte-length
deltas "+49 B / +17 B" (PC0252's two boundary rows — the ONLY survivor rows
in the entire foreign corpus that carry a glm-dialect clearing fact), and
one named kill with a stated signature (L19780, `test_three` +
AssertionError).

So: **CONTINUITY.md §4, read as written, certifies a recording convention,
not only a proof standard.** A SAFE under §4 means "the record carries a
glm-dialect clearing fact in its own clause", not "the verdict was proved
cleared"; and an UNKNOWN under §4 means "the rule cannot read this record",
not "the verdict was uncleared". Cross-lane application of §4 must therefore
read UNKNOWN as the rule's blind spot, and the AFFECTED vocabulary is
likewise convention-bound — the stale marker is the literal wording of
glm's own M6/M7 incident, and pilotcaps records the same physics as doctrine
("a mutation written inside one second can import the previous bytes and
read as a NO-OP"), which S1 deliberately does not mark: AFFECTED falls from
6/55 = 10.9% at home to 1/82 = 1.2% away.

## Where UNKNOWN concentrates — one kind, not one era

The 67 UNKNOWN span L5478 (TASK-0231) to L19784 (TASK-0260) — the whole
mutation-program era, every section, no date boundary. They concentrate by
KIND, in three piles (by the classifier's own reason strings):

- 47/67 (70%) — **no clause-local killer name**: plant-table and
  control-matrix rows that state the verdict as a count ("KILLED 7",
  "CAUGHT by 2", "kill-set {C1,C3}") or a control label, with the test
  names on a subordinate indented line the grammar does not merge.
- 8/67 (12%) — **killer named, signature not stated**: L5478, L7471, L9503,
  L9786, L9821, L9822, L10096, L16148.
- 12/67 (18%) — **survivor verdicts with no glm-dialect clearing fact**:
  L8282, L8542, L9477, L12061, L12063, L12064, L15386, L15661, L18789-18792.

The named boundary: **the rule clears a verdict only when the killing test
is named in `test_…` grammar with a quoted failure signature, or when a
glm-dialect clearing fact sits in the same clause. pilotcaps states verdicts
as counts and control labels and puts its evidence one indent below the row.**
Merging subordinate evidence lines was deliberately NOT done: it is a
mid-readback grammar change that would have upgraded UNKNOWN→SAFE (L16148
and L10480 would both flip), and the fact-placement convention is the
finding under test, not an adapter defect.

## Records the rule cannot classify either way, and the one fact each

The cheapest improvers — evidence the corpus ALREADY records, one
placement away from where the rule reads:

- **L16148** — kill-set names
  `test_the_door_is_the_first_statement_of_the_transport`; the AssertionError
  is recorded one line below the clause. Missing: the signature in-clause.
- **L10480** — signature present (AssertionError quoted); the two test
  names sit on the FAIL rows one indent below. Missing: the names in-clause.
- **L15382** — "KILLED (3), by name:" — the three names on the three
  6-space lines below, the kill-reason block below that. Missing: names +
  signature in the header clause.
- **L5478** — names (from test filenames) and line numbers stated, failure
  text not quoted. Missing: the quoted failure signature.
- **L9503, L9786, L9821, L9822, L10096, L7471** — killer named, no stated
  signature. Missing: the signature.
- **L15386, L8282, L18789-18792** (survivor rows) — no clearing fact in any
  dialect. Missing: the byte-length delta next to the verdict (exactly what
  PC0252's L19513/L19514 did — the only survivors that cleared).
- **L7057 (refused, unparsed)** — M14's first-pass void ("counted UNKILLED")
  and the re-run kill ("killed by 2 names") share one clause, so both
  vocabularies fire and the gate refuses. Missing: the void and the re-run
  kill stated as separate clauses. (L5748, the other refusal, is not a
  mutation record at all — documentation-drift prose the gate correctly
  declined.)

**Cheapest single improvement: quote the failure signature (or the killer's
name) inside the verdict row itself.** The corpus already writes both, one
indent below; promoting the evidence line into its row is one line of
recording discipline and no new rule vocabulary. Its survivor-side twin is
the byte-length note, proven by the two rows that clear.

## Controls (fail-closed)

- **C1 positive** (synthetic: size-identical write reverted inside the same
  whole second, `__pycache__` reused) — printed **AFFECTED**. PASS.
- **C1 negative** (synthetic: named kill
  `test_the_brake_refuses_before_the_join` with stated AssertionError
  signature) — printed **SAFE**. PASS.
- **C2** (synthetic: kill reason described, never named, no byte-length
  change, no later-second revert, no `__pycache__` deletion, no load-proof)
  — printed **UNKNOWN**. PASS.
- **C3** (re-run 0080's byte-identical extract+classify over LANE-glm.md
  against 0080's recorded output) — first run **FAILED**: 72 records /
  AFFECTED 7 vs the recorded 71/6, the extra record at L4257. Cause: not
  adapter leak — the input. LANE-glm.md is append-only and 0080's own entry
  (from L4219) restates its AFFECTED findings in prose its extractor reads
  as a record; 0080 measured before that entry existed. Fixed in the
  IMPLEMENTATION, not the rule: C3 bounds its input at 0080's entry header
  (found by pattern, printed in the control output), reconstructing the
  measurement conditions. Re-run: 71/71 records, 55/55 kept,
  SAFE 30 / UNKNOWN 19 / AFFECTED 6 — zero drift; the five printed rows
  (L3284 AFFECTED, L4085 AFFECTED, L1181 UNKNOWN, L2557 UNKNOWN, L3144 SAFE
  as 0074-s3's C1 positive) all REPRODUCED. PASS.
- **C4 gate** — C1 both states, C2 UNKNOWN, C3 no drift: all yes. THE table
  printed only after the gate, and its shape (UNKNOWN 67, AFFECTED 1) is
  not all-clear.

## Adapter deltas, all documented in-file

`extract_pilotcaps.py` vs 0080's `extract.py`: unit grammar (bold-lead
units, 4-7-space indented rows with 8+-space continuations, same-line
same-outcome clause merge, section-scoped facts) and vocabulary (CAUGHT /
killed by / `-> <cell/count/name> red` / non-empty kill-set / `**YES**` /
`**no**`; UNKILLED / NOBODY SAW IT / kill-set EMPTY / survives / loses-the-
red; pyc and load-proof dialects). Two readback-driven corrections this
task: the arrow-red character class widened to include `_` (a genuine
named-kill row, 0231's re-run table L9503, was not a record at all — a
recall patch, never a verdict upgrade), and the `**YES**`/`**no**` header
note corrected (those cell forms also fire on 8 barrier-prospect rows and
one fixture row, excluded per line; the patterns are kept for the genuine
PC0252 products). `classify.py` is imported UNCHANGED — its sha256 is above.

## Discrepancies reported, not fixed

1. **CONTINUITY.md §10 header-time defect** (pre-existing, 0080's): a
   paragraph spliced in around 20:11 while the section header still claims
   16:58:33. Not edited — this task has no CONTINUITY.md write grant.
2. **0080's discipline note vs the tree**: TASK 0080's lane entry claims its
   control artifacts were committed, but `c1_negative.md`, `c1_positive.md`,
   `continuity_para.md`, `lane_entry.md` (`.codex/0080/`) and
   `0065/ref_suite_launch.out` are untracked (`??`) in this worktree's git
   status.
3. **A control-finding about C3's design, fixed here**: 0080's recorded
   output is version-bound to a lane file that has since grown; any re-run
   of 0080's instrument over the live LANE-glm.md double-counts 0080's own
   prose (see C3 above). The bound is the fix and is printed on every run.
