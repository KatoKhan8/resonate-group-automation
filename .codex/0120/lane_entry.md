## 2026-10-16 23:26 — TASK 0120 — THE WIDENED READER: 67 FOREIGN UNKNOWNs RE-GRADED — 3 FLIP SAFE, 64 STAY UNKNOWN, 0 BECOME AFFECTED, AND NOT ONE ROW THE STRICT RULE GRADED CORRECTLY MOVES

Corpus: `LANE-pilotcaps.md`, sha256
`70c8190f6e07bf7a23d05a68ee3b2916354cacf6b4d15f5c6b864ce4d2b026da`
(1,128,659 B) — the same bytes 0090 measured. Baseline re-reproduced before
anything was widened: 158 records / 2 refused / 82 kept / strict SAFE 14 /
UNKNOWN 67 / AFFECTED 1 — 0090's numbers exactly (exit-checked, not eyeballed).

### The widened rule, as text (implementation: `.codex/0120/widen.py`, this branch)

W0 — the VERDICT layer is untouched. Both extractors are imported UNCHANGED;
which lines are records and each record's outcome (kill / survive / stale-only)
come out byte-identically. The widening adds EVIDENCE paths only: a row with no
verdict is not gradeable however much evidence sits near it, and no path may
change a record's outcome. AFFECTED is graded exactly as the strict rule grades
it (the stale path is NOT widened — doctrine-vs-demonstration is a judgment a
block form cannot support), and classify_facts runs first on the unchanged
facts, so a strict SAFE or AFFECTED can structurally never be demoted.

W1 — the EVIDENCE BLOCK: for a record whose unit span ends at line E with row
indent I, evidence is the contiguous run of lines below E, each indented >= I,
stopping at a blank, a strong unit head (header / bullet / numbered / table row
/ **bold-lead** / flush prose), the 8-line cap, and — the load-bearing stop —
BEFORE any line carrying outcome or stale vocabulary: a verdict line is never
evidence, which is what keeps a SURVIVED row (L15386) out of a KILLED row's
(L15382) block. A second boundary, measured into the rule: a RESULT ROW — a
line carrying a `test_` name and ending in a bare (unquoted) GREEN/RED cell
(L10487 `test_c1_..._is_MET   GREEN`) — records a different test's verdict and
ends the block; it can only REFUSE (end evidence earlier), never clear, and it
does not match backticked commentary like L16149's `` `ok` ``. Over row-span +
block the reader accepts the SAME vocabularies the strict rule reads — the
signature patterns, size-change claim, whole-second clearing, pyc precaution,
load-proof CLEAN — plus NAME with one recall fix: capitals admitted into the
name tail, because `test_..._is_NOT_MET_...` was harvested TRUNCATED at the
first capital (a grammar artifact; 0090 made the same class of fix for `_`).

W2a — COUNT CERTIFICATION: a kill row stating a count N ("KILLED (N)",
"failures=N", "-> N red", a kill-set with N members, …) certifies
completeness — the widened name list must hold exactly N distinct names, else
the widening REFUSES and the row stays UNKNOWN with both numbers printed.

W2b — KILL-REASON BLOCK, pointer form: a pointer line ("for the intended
reason", "kill-reasons", "captured rather than assumed") within 14 lines below
the row, followed by an indented run of signature lines, attaches those
signatures ONLY when a count N exists AND N names AND N signature lines are
found (count-certified pairing). Without a count the pointer form is refused.

W3 — grading: SAFE for a kill row = names AND a signature over row+block, with
W2a/W2b certification whenever a count or pointer is present; SAFE for a
survivor row = a clearing fact (byte-length delta / whole-second / pyc
precaution / load-proof) over row+block; everything else UNKNOWN, fail-closed,
with the reason printed. What widened is WHERE the rule looks, not WHAT it
demands — the proof standard (named killing agent + stated signature, or a
staleness-defeating fact) is 0075's, unmoved.

Stages: `run_0120.py --stage baseline | controls | table`; the re-grade table
prints only after the controls pass and refuses an all-clear shape outright.
Results mirrored to `.codex/0120/table_result.json`.

### Controls (all PASS)

- **C1 PASS** — 0090's three predicted flips all flip, each with its evidence
  block printed: L16148 (block L16149-16151: 1 name, count 1 certified),
  L10480 (block L10481-10486: 2 names, `failures=2` certified — and the block
  correctly ends before result row L10487), L15382 (block L15383-15385: 3
  names, `KILLED (3)` certified, signatures via the W2b pointer at L15390 to
  the AssertionError lines L15393-15395).
- **C2 PASS** — rows with no evidence in any form stay UNKNOWN, shown unmoved:
  L7645 ("no name over row+block; no signature over row+block") and L5926
  (same). Counts and control labels standing alone still certify nothing.
- **C3 PASS** — the home corpus (`LANE-glm.md`, input bounded at 0080's entry
  header L4219, 0090's C3 discipline) first reproduces 0080's strict
  71 records / 0 unparsed / 55 kept / SAFE 30 / UNKNOWN 19 / AFFECTED 6, then
  re-grades under the widened reader: all 30 SAFE stay SAFE (0 demoted), all 6
  AFFECTED unchanged, and **0 of the 19 home UNKNOWNs flip** — at home the
  widening finds nothing, which is the C3 finding in the other direction: home
  rows record their facts inside the verdict clause or do not record them at
  all; there is no second recording convention at home to widen into.

### The one question, answered (every count with its denominator)

Of the 67 strict-UNKNOWN rows (kept-set denominator 82 beside):

- **SAFE 3/67** (widened SAFE 17/82)
- **UNKNOWN 64/67** (widened UNKNOWN 64/82)
- **AFFECTED 0/67** — the stale path is not widened, by spec, so no UNKNOWN
  can become AFFECTED (widened AFFECTED 1/82, the same L6827).

Widened distribution over the 82 kept: SAFE 17 / UNKNOWN 64 / AFFECTED 1.

**Does the widened rule flip any row the strict rule graded correctly? No —
zero.** All 14 strict SAFE rows are still SAFE and L6827 is still AFFECTED
(structurally guaranteed by W0, and verified). W2a/W2b refusals: 0 — no row
stated a count its evidence failed to certify.

### Every flip (3 of 67), with its line cite and firing clause

- **L10480 → UNKNOWN → SAFE → W1 named-reason kill, count-certified**
  (evidence block L10481-L10486: the two FAIL rows name both killers, the
  quoted failure text carries `AssertionError`, `failures=2` = 2 names).
- **L15382 → UNKNOWN → SAFE → W1 named-reason kill, count-certified + W2b
  kill-reason block** (evidence block L15383-L15385: three names under
  `KILLED (3), by name:`; the pointer at L15390 leads to the AssertionError
  signature lines L15393-L15395, 3 of 3 as counted).
- **L16148 → UNKNOWN → SAFE → W1 named-reason kill, count-certified**
  (evidence block L16149-L16151: 1 name, kill-set of 1, AssertionError quoted
  at L16150).

Exactly the three rows 0090 named as the cheapest improvers — the widening
clears all and only the rows where a named agent with a stated signature
genuinely exists in a form below the verdict row.

### Why the other 64 stay UNKNOWN (the dump of all 67, reasons cross-checked)

- **8 rows hold a name but no signature** — the 7 named-in-row rows L5478,
  L7471, L9503, L9786, L9821, L9822, L10096, plus L10511 where the widened
  reader found the name in the block (L10512-L10514). Attribution is half
  present; without the signature the red could be any edit's. All refused.
- **44 rows hold no name anywhere near** — including L10147, the inverse case:
  its block (L10148-L10151) carries signature vocabulary but no `test_` name,
  and no name means no attribution, refused.
- **12 survivor rows** (L8282, L8542, L9477, L12061, L12063, L12064, L15386,
  L15661, L18789-L18792) — no clearing fact (byte delta, whole-second, pyc
  precaution, load-proof CLEAN) anywhere over row+block. A survivor is cleared
  only by a staleness-defeating fact, and none is recorded.
- 3 + 8 + 44 + 12 = 67. Zero stale-only rows among the 67.

What each pile would need, and the exact file it would need it in —
`LANE-pilotcaps.md` for all of them: the 8 name-only rows need the killing
signature quoted under the verdict; the 44 no-name rows need name AND
signature recorded near the row; the 12 survivors need one recorded clearing
fact (a byte-length delta is the cheapest). The strict rule stays the
convention this repo grades its own rows by; the widened reader is a scratch
instrument that proves the 64 remaining are evidence-limited, not
convention-limited — 0090's "partly a convention" finding quantifies as
3/67 convention-recoverable and 64/67 evidence-absent.

Read-only over the repo; no suite, no lock, no network call, no provider
touched, no gate/cap/test weakened. Scratch tool committed to the lane branch
only (`task-glm-review-2026-10-14`, no push): `.codex/0120/widen.py` (the
rule), `run_0120.py` (stages), `dump_kept.py` / `dump_67.py` (readback
instruments), `table_result.json` (mirrored results), `lane_entry.md` (this
text). `__pycache__` deleted after every write and every run, both directions.
Tree left clean.
