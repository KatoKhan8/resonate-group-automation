# The patterns behind the defects

Not a list of defects — the defect maps are that. This is the list of SHAPES
that keep recurring, each with the instances that earned it a place. A pattern
is written here when its **second** instance is found, because one instance is a
bug and two is a shape.

Every instance carries its date and where it was measured.

---

## 1. A check that reintroduces what it forbids

**Three instances in one night, 2026-10-02/03**, all caught by a scan rather
than by review:

- the anonymiser's own metadata field listed its substitution patterns, so the
  leak scan matched the names through the file that removed them;
- the same field again, after the first fix, in the `pattern_note` key;
- a test's literal list of forbidden strings — the prospect's company and the
  recipient's first and last name, spelled out as the tuple the assertion looped
  over — was matched by the PII scan over the staged diff. The test now holds
  them base64 and says why in its docstring.

**And a fourth instance, in this file, on 2026-10-03.** The paragraph above
originally quoted that tuple verbatim as its example, so the scan over the
staged diff matched **the document describing the pattern**. It was caught by
the positive control rather than by reading it back. The example is described
now instead of quoted.

**A fifth and a sixth instance, 2026-10-03, and these two reached source code.**
The lane building the copy gates scanned its own staged diff and found **a
recipient company name in a comment it had itself written in `src/lint.py`**,
and another in `src/copystages.py` — typed into a change whose entire subject is
not doing that. The same scan found **a mobile number, twice**, inside the one
exemplar that is a reply rather than a cold opener — **in a file that had
already passed two clean scans of its own.**

The fix there is the shape to copy: the committed test holds **41 SHA-256
hashes and no names**, scans the source files, the rendered prompt AND itself,
and ships with `test_the_scan_can_fail` so the scan's own silence is evidence of
something rather than of nothing.

**The rule that follows:** run the scan over the FINAL artefact including
metadata, and never spell a forbidden token inside the file that forbids it —
including when the file's subject IS that mistake.

**A seventh, the same day**: the verification lane's own TASK file carried a real
mailbox and 14 personal contact keys; it was redacted and the scan self-tested
before the commit.

**Seven instances in two days, two of them in `src/`, one in a task file, one in
the pattern's own documentation — and every single one caught by a scan rather
than by a person reading the diff.** Nobody here has ever caught this by
reading, which is the whole argument for running the scan on every commit
instead of trusting attention.

## 2. A measurement bound to the tree it was imported from

`ROOT` resolves per worktree, and `work/` is gitignored, so anything that must
be machine-wide silently becomes per-tree:

- **the suite lock** — six suites ran at once because the lock lived in each
  tree's own `work/` (2026-10-02, cost 3h42);
- **the spend ledger** — GLM verification billed and audited a temporary file;
  the audit read `0 glm rows, 0 clients` and passed (A41, 2026-10-02);
- **`config/.env`** — absent in a worktree, so every credentialled call from one
  dies with `MissingKey`;
- **the production-write barrier** — `refuse_production_write` protected
  `<ROOT>/work` of the invoking tree, so the MAIN checkout's
  `work/campaigns.jsonl`, the OS authority, was outside it for every run that
  has ever gated a merge (A46 / TASK-973, measured 2026-10-03: this tree
  REFUSED, main checkout ALLOWED).

**The rule:** resolve it through
`git rev-parse --path-format=absolute --git-common-dir`, and refuse a relative
answer rather than resolving it against the caller's cwd.

## 3. A validator that agrees with you

A check whose outcome cannot differ from the expectation it was written to
confirm:

- acceptance commands that could not fail — `assert … or True`, a needle
  containing a space searched in a space-stripped haystack, a function called
  without the argument that selects the path under test (three in one night,
  2026-10-02; GLM named one "a print statement wearing an assert");
- a mutation whose mutant text contained the original, so `present not in back`
  passed and the file was left mutated (2026-10-02);
- a mutation that could not be ineffective in the way it was asserted:
  `abspath(os.sep)` is `C:\` and `startswith("C:\\" + os.sep)` tests for a
  double separator (2026-10-03, recorded by the lane rather than discarded);
- `test_every_term_comes_from_a_contract` recomputes with the formula it
  polices, so a jointly edited formula passes (2026-10-02, stated as an
  inherent limit rather than hidden).

**The rule:** assert the EFFECT, name the input that would defeat the assertion,
and keep a control that a blanket fix would break. A gate that refuses
everything is as broken as one that refuses nothing — and the second half of
that sentence is the half that gets skipped.

## 4. A thing computed correctly that nothing downstream reads

The repository's oldest shape, and the reason "existence is not function" is in
`CLAUDE.md`:

- the evaluator that reported `INSUFFICIENT_DATA` forever because nothing wrote
  the field it read;
- the provider's sent-event ingest with **zero production callers**, which is
  why a campaign that had sent 6 emails read as 0 (2026-09-28);
- `claims.may_claim_first_contact`, shipped and uncalled, while the first-touch
  licence stayed with the old boolean (A45, 2026-10-02);
- `sequencegate.role_ladder`, written 2026-10-03 and **still with no production
  caller** — recorded in its own task file rather than claimed as enforcement;
- `reengagement.REENGAGE_MIN_DAYS`, defined and uncalled (2026-10-03).

**The near-miss that is worth as much:** `claims.customer_outcome_claim` looked
like this pattern — 153 mentions in `tests/` against 2 in `src/` — and was NOT:
the second `src` mention is the call, inside `claims.check`, which `generate.py`
calls at five sites. **Count the mentions, then read them.**

## 5. An attestation that outlives the tree it describes

A committed record of a measurement whose subject has moved:

- `SUITE-task-guard-regressions-2026-10-02.json` attested `31bc1801`, which
  `merge-base --is-ancestor` says is **not even an ancestor** of the branch tip
  after a rebase (A47, 2026-10-03). It sent two of five GLM parts off the rails;
- `SUITE-TASK-936-2026-10-02.json` attested `0555dfa6` and went stale the moment
  that branch was rebased for its own gate run — **2 of 2 rebased branches**, so
  the mechanism is the rebase, not one branch's untidiness;
- a handoff that said "done, artifact verified" for 13 tasks, 3 of whose
  artefacts did not exist on master (2026-09-26).

**The rule:** a rebase silently invalidates every attestation a branch carries.
Delete it rather than hand-editing the commit field — a body belonging to one
tree under a header naming another is the same defect with better camouflage.
And the field is spelled `commit` in some files and `measured_at_commit` in
others, so a checker that reads one spelling passes vacuously on the other
(measured 2026-10-03, on my own acceptance command).

## 6. A set compared by its size

- three FINISHED full suites each reported exactly **231** failing names and one
  of them was a different 231 — a fix landed and a flake appeared, and the
  scalar did not move (2026-10-02);
- a baseline test whose outcome depends on whether the worktree's `work/`
  happens to exist yet, so a name enters or leaves the set for reasons
  unconnected to the branch (TASK-977, 2026-10-03);
- seven cap-and-ceiling names that failed only in a full run, order-dependent
  rather than branch-caused (TASK-970, 2026-10-02).

- and the sharpest instance, 2026-10-03: a scripted import rewrite left a
  **SyntaxError** in a module, so the run reported **"0 new, 22 fixed"** — every
  name vanished because `unittest` never loaded the module at all. Only
  `grep "^Ran [0-9]* test"` exposed it. An empty failure set is the same shape
  as a perfect one.

**The rule:** a baseline is a NAMED LIST compared as a SET. When a name
disappears, verify it positively by finding it running and passing in the log —
absence proves nothing, and "everything is fixed" is what a module that failed
to import looks like. Assert that something RAN before reading what failed, and
run the two controls every time: reference against itself must give 0 new, one
planted name must give 1.

## 7. A reader that asks for the wrong key, and a window that is ignored

- a reader asked for `subject`/`body` where the provider returns
  `email_subject`/`email_body`, and printed empty — indistinguishable from empty
  data (2026-10-02);
- `timeFrom`/`timeTo` on the HeyReach stats endpoint is **ignored** and returns
  lifetime figures; only `startDate`/`endDate` honours the window;
- `clients.scalar` promotes only integers, so a rate written as `0.009792` comes
  back as the STRING `'0.009792'` — the parser accepts it and converts it
  wrongly, which is worse than refusing it (measured 2026-10-03);
- `subprocess(text=True)` with no `encoding` decodes with the locale codec
  (cp1250 here), so a patch carrying byte `0x90` comes back as `None` and the
  prompt slot reads "(could not generate a diff)" (A40, 2026-10-02).

**The rule:** print the KEYS of the first payload before reading fields from it,
and pin one decode policy in one place with several users rather than per call
site.

## 8. A guard switched off by its own environment

- `test_invariants`'s send guard exempts a hit with
  `any(a in p for a in allowed)` where `p` is an ABSOLUTE PATH and `allowed` are
  provider names, so a worktree called `glm-940` exempted **every file in the
  repository** and the guard passed having watched nothing (A44, 2026-10-02).
  That is why worktree names stay neutral until the fix lands;
- `refuse_production_write` returns early unless `"unittest" in sys.modules`, so
  a measurement script that forgot to import `unittest` measured a disabled
  guard and read ALLOWED on its own tree (measured, and corrected, 2026-10-03).

**The rule:** a guard's own preconditions are part of the measurement. State
them, and prove the guard was live in the process that did the asking.
