# TASK-978 — write the 30 phase-2 scenario YAML files from the catalogue

**WRITE `REPORT.md` NOW, EMPTY, IN YOUR WORKTREE ROOT, BEFORE YOU READ ANYTHING
ELSE. Then append to it as you go.** One line per scenario file you finish, and
one line for anything you could not do and why. A report written at the end is a
report that does not exist when the session dies.

## The one deliverable

**30 YAML files**, one per scenario, at `docs/phase2-scenarios/scenarios/S01.yaml`
through `S30.yaml`.

**No code. No test. No change under `src/`, `tests/`, `work/` or `config/`.**
If you believe a scenario needs code, write that in `REPORT.md` and move to the
next file.

## Where the catalogue is

Read these two files before writing anything. They are on another branch, so
read them by ABSOLUTE PATH rather than checking anything out:

    C:\Users\Zvonimir\AppData\Local\Temp\claude\C--Users-Zvonimir\0cac0b96-c38b-49ae-b244-b10ce22784c7\scratchpad\wt-lane3\docs\phase2-scenarios\CATALOGUE.md
    C:\Users\Zvonimir\AppData\Local\Temp\claude\C--Users-Zvonimir\0cac0b96-c38b-49ae-b244-b10ce22784c7\scratchpad\wt-lane3\docs\phase2-scenarios\README.md

`CATALOGUE.md` has one row per scenario: the id, its intent, the setup it needs,
the event it injects and the expected outcome. `README.md` states the YAML shape
and it carries a WORKED EXAMPLE for S01 — copy that file's shape exactly.

## The shape, and the three things the parser refuses

Every file is `setup:` / `event:` / `expected:`, plus `id:` and `intent:` lines
taken verbatim from the catalogue row.

This project parses its own YAML with a strict subset (`src/clients.py:parse`),
and the README states this with measurements. Three things RAISE:

1. **Block lists.** `- item` is refused. Write `[a, b, c]` on one line.
2. **Folded scalars.** `>-` and `|` are refused. Every value is one line.
3. **A line with no colon.** Every line is `key: value` or `key:` followed by a
   more-indented block.

And one thing that does NOT raise and is worse: **a float silently becomes a
string**, so floats are forbidden outright. Write rates as integers in an
explicitly named unit (`rate_per_10000: 220`), never `0.022`.

## How to check your own work

After each file, run exactly this and paste the result into `REPORT.md`:

    python -c "import sys; sys.path.insert(0,'.'); from src import clients; d=clients.parse(open('docs/phase2-scenarios/scenarios/S01.yaml',encoding='utf-8').read()); assert set(('id','intent','setup','event','expected')) <= set(d), sorted(d); print('OK', d['id'], '->', sorted(d))"

with `S01` replaced by the file you just wrote. A file that does not parse is
not done, and a file whose top-level keys are missing is not done either.

## Synthetic data only

Every contact in every scenario is synthetic and every domain ends `.invalid`.
No real company, no real person, no real email address, no provider id from the
live estate. The simulation never touches a provider and these files must not
carry anything that could be mistaken for live data.

## When you are finished

Commit the 30 files and `REPORT.md` on your own worker branch and push it. **Do
not merge anything. Do not touch master.** The main session reviews your commit
through GLM before taking it over.

If you finish fewer than 30, that is a result and not a failure: say which ones
and why in `REPORT.md`, commit what you have, and push.
