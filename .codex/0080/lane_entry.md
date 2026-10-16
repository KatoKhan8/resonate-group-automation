## 2026-10-16 19:04-20:10 — TASK 0080 — THE VERDICTS THAT REST ON A MODULE NOBODY RELOADED: 55 KEPT RECORDS — SAFE 30 / UNKNOWN 19 / AFFECTED 6, AND ALL SIX AFFECTED ARE ALREADY ON RECORD AS INCIDENTS

The back-audit `0075` asked for: every recorded mutation-proof claim in this
file, classified under `0075`'s clearing rule. **Not the remedy — `0078` and
`0079`, queued beside this brief, own that.** Read `qwen/0176`'s failed
classifier first, as briefed: it died hand-validating a 14-record sample whose
denominator mixed `## VERIFICATION` subsections and commentary into records.
This audit's records come only from its own extractor, all 16 exclusions are
documented per line, and C3 sampled the exclusion classes as well as the
verdicts.

### THE INSTRUMENT (two layers, `.codex/0080/`)

`extract.py`, adapted from `0078`'s `parse_lane.py`: bullet / numbered / table /
`**Mutation proof**:` unit scoping, LEADS post-lead scoping, `;`-clause
splitting, the ~95-column wrap normalised, MAX_SPAN 30, stale-marker capture,
single-plant merge. `classify.py`, a pure rule engine over one record's facts,
in order: a recorded stale marker prints AFFECTED; not-an-in-place-mutation
prints SAFE; a kill with a clause-local test name AND a stated signature prints
SAFE; a recorded load-proof CLEAN prints SAFE; a recorded or derived size
change prints SAFE; a strictly later whole second prints SAFE; a recorded
`__pycache__` precaution prints SAFE; everything else prints UNKNOWN with its
missing facts named — fail closed, never SAFE by absence of evidence.
Clause-local is clause-local: a name in the neighbouring clause does not clear
a record. That strictness is deliberate and its cost is measured below.

### CONTROLS

- **C1 positive — the six plants pass.** `0074` s3's entry verbatim
  (L3060-3211): plants A-F each print SAFE, every clearing fact present.
  **C1 negative — the same entry with every recorded reason redacted** (test
  tokens, Plant B's verbatim pair, got-receipts, error classes, the pyc
  protocol phrase) prints UNKNOWN on all six plants and SAFE on nothing — the
  pre-0072 recording style modelled exactly. A first cut that also redacted
  backtick spans mispaired across the 95-column wrap and ate the kill
  vocabulary; the final cut redacts only backtick-independent tokens and keeps
  both legs line-identical. That cut is recorded in `make_c1.py`'s header so
  the simplification is not mysterious.
- **C2, the paired one — a live replay of `0075` P3, and the classifier prints
  AFFECTED, not SAFE.** Throwaway worktree `wt-glm-0080-c2-2026-10-16`,
  detached at this lane's own HEAD `b67c61ab4` (asserted before anything ran).
  PRIME: a fresh process imports pristine `src/spendledger.py`, compiles the
  pyc, `load_proof` CLEAN, the guard raises `UnpricedCall`. PLANT: 4 B
  `not ` -> 4 B `0 * ` at the unique guard line, mtime rolled back ns-exact so
  the timestamp-mode pyc header still validates. STALE LEG: a fresh process
  imports the PRE-PLANT bytecode — `load_proof` STALE BYTECODE while the probe
  still raises `UnpricedCall` from bytes no longer on disk: `0075` P3's forged
  green, observed live. Classifier: AFFECTED. REVERT, in a `finally`:
  pristine bytes and pristine stamp restored, verified by sha256 AND an
  import-level read (CLEAN, the refusal back). Classifier: SAFE. The worktree
  was removed and its removal verified twice (path gone, absent from
  `worktree list --porcelain`). PASS on the first run.
- **C3 — hand validation, 31 rows, 51% of the table.** 28 kept rows drawn
  stratified over every verdict class, every clearing disjunct and both
  recording eras, plus the three exclusion classes. Every span re-read from
  `LANE-glm.md` this session, not trusted from the dump. Hand verdict vs
  classifier: **0 disagreements in 28 — false SAFE 0, false UNKNOWN 0, false
  AFFECTED 0.** Residuals stated as residuals, not errors: six UNKNOWN rows
  (L186, L1181, L1186, L1194, L1198, L2557) carry their name or signature one
  clause away — the measured cost of clause-local strictness; two SAFE rows
  rest on the documented extensions below; and extraction recall (a unit the
  extractor never turns into a record at all) cannot be measured by a verdict
  sample — the census cross-check bounds it.
- **C4 — the gate.** THE table is printed only because C1 printed both states,
  C2 printed both states (AFFECTED over the planted disk, then SAFE over the
  verified revert), and C3 stated both error directions over 28 kept rows
  (floor 12). An all-clear-shaped table would have been refused outright — it
  is the dangerous wrong answer here.

### CENSUS CROSS-CHECK (recall)

Over the pre-`0079` slice (first 4040 lines), `0078`'s independent
`parse_lane.parse` made 46 record lines; all 46 are a subset of this
extractor's 57 — no recall miss. The 11 ours-only lines (L1194, L1526, L1531,
L2557, L3871, L3908, L3911, L3915, L3969, L3970, L4006) are stale-marker and
no-kill-vocabulary records its kill/survive-only design never makes. No
documented exclusion matched zero records.

### THE TABLE — 55 KEPT RECORDS (16 EXCLUDED, EACH DOCUMENTED)

**SAFE 30 / UNKNOWN 19 / AFFECTED 6**, from 71 records, 0 unparsed.

**AFFECTED (6)** — every one already on record as an incident: L3284 (`0075`
P3 itself, "the runner imported the stale original bytecode and never
recompiled"); L3911 + L3915 (`0078` §2's deliberate demonstration);
L4085 (`0079` R2, SURVIVED with load-proof STALE BYTECODE — a void verdict,
not a real survivor); L4125 + L4127 (the unremedied column and the R2 column
of `0079`'s four-way table). Six rows, all inside entries that exist to
document the hazard.

**UNKNOWN (19)** — L56a, L56b, L165 x5, L186, L759, L764, L1181, L1183, L1186,
L1194, L1198, L1925, L1929, L1933, L2557. Every one is pre-`0072`: the era
that recorded outcomes without names, sizes or timing. The distribution the
brief predicted, and the honest shape of it — the early span is UNKNOWN-heavy
not because those verdicts were wrong but because they cannot be re-derived
from what was written down. A kill whose reason was described but never named
is UNKNOWN to a reader today, however true it was on the day.

**SAFE (30)** — spanning every disjunct: not-in-place x6, named-reason kill
x8, size change x5, whole-second x1, `__pycache__` precaution x8, load-proof
x4 (some records clear on more than one).

**Two documented extensions beyond the letter of the brief's five disjuncts,
flagged as such:** (1) a recorded load-proof CLEAN clears — `0078`'s
instrument subsumes the pyc-precaution test and is strictly stronger (four
records); (2) a size change derived arithmetically from a verbatim mutation
pair (L1202, `if not found["refused"]:` 24 B -> `if True:` 8 B, -16 B) is
trusted as recorded. The brief's list named neither; both are stated here so
the table's SAFE count is auditable against the rule as written.

### TASK-0180 (webapp's) — WHICH CLAIMS REST ON A STALE MODULE, AND THE PRICE OF RE-MEASURING

`0075` named it the realized incident; this audit did not re-run it, as
briefed. The entry is `LANE-webapp.md` L6368-6766, commit `8b2d12d11`,
branch only.

**Established: the void claims are the intermediate NO-OP readings, and the
entry itself voided them.** Defect 3 (L6594-6599): M3/M3b/M3c were three -4 B
writes inside one second — runs two and three imported the *previous*
mutation's bytecode and reported NO-OP. That is `0075` P3 realized, exactly.
Defect 2 (L6588-6593) is separated honestly: twelve NO-OPs from a *raised
behaviour probe* (`sorted` comparing None with str, a one-row error
fingerprint identical across mutations) — a dead instrument, not a stale
import. Both classes were diagnosed inside the entry, the harness repaired
(deletes the `__pycache__` entry before every run; REFUSES on a raised probe
or tiny fingerprint), and everything re-measured. **The final table (14
MUTATIONS, 14 KILLED, 0 SURVIVED, 0 NO-OP, L6534-6554) does not rest on a
stale module**: it ran under the repaired harness with the per-plant
`__pycache__` deletion (disjunct d), reverts proved by byte round-trip and
sha256 — never `git checkout` — both targets hash-identical afterwards, and
every kill is a named-reason kill with its count and the C4/C5 controls named,
which is self-certifying: stale bytecode can only counterfeit a green.

**Downstream citations: nothing cites the void readings.** `8b2d12d11` is
cited as a measurement base (`0190`, `0210`, `qwen/0177`'s flip census), as a
push-forensics anchor (`TASK-0235`), and its driver / revert-protocol lines
are quoted as invocation records by the `TASK-0340` / `TASK-0390` censuses and
`LANE-suppression`'s artifact table — all describing the repaired protocol.
`0075`'s own citation names the incident itself, which is the correct
citation. (`CONTINUITY-LOG` L714 and L767 mention other lanes' `0180`s —
pilotcaps' rows and pilotcaps' fence.)

**Price and recommendation — NO DISPATCH.** The run cost 48m31s (watcher
START 08:22:30 -> DONE 09:11:01, exit0; the commit landed 09:06:35).
Re-measuring the mutation table alone would cost roughly 15-25 minutes of
lane time, a full re-dispatch about 50, against the reference the brief gave:
`glm-c/0220` spent 150 minutes timing out for a 559-byte `.out` on work
already recorded. A re-measure would buy nothing — the load-bearing table is
self-certifying under `0075`'s rule, the void claims were superseded inside
the entry the same hour they were made, and reproducing the stale-pyc NO-OPs
deliberately would repeat `0075` P3 and `0079` R2, both already on record.

### CONTINUITY.md

One paragraph added at the end of the pyc passage in §4 (after "Say which
rule you applied and in which direction."): the reader's test — a kill that
names the test and states the signature certifies itself; everything else
needs one recorded fact (size change, later whole second, `__pycache__` drop,
or load-proof CLEAN) or it is UNKNOWN; size-identical inside the same whole
second is void, re-measure before building on it. A test, not a warning.

### DISCIPLINE

No suite, no mutation driver change, no load-proof landed (`0078`/`0079` own
those). No provider, Apify, Slack or network call beyond `ls-remote`:
`origin/master` `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2` at start (19:04)
and at close, identical. No cap, gate, `src/providers/*`, `config/.env`,
production `work/` or watcher touched; `src/providers/glm.py` never opened.
`scripts/run_suite.py` md5 `65c50c89ac0e2279fa7178cba251f256` at start and at
close, identical. The only tree created was the C2 throwaway, on the Desktop
beside this lane's tree, removed and verified gone. `.codex/0080/` (five .py
tools plus the four control artifacts) committed to this lane's branch only;
the pre-existing untracked `.codex/0065/ref_suite_launch.out` is not mine and
was left where it lies. `LANE-glm.md` 4216 lines / 267896 bytes before this
entry, 4395 lines / 278977 bytes after, read back and verified.

This run ends here so the watcher dispatches the next brief.
