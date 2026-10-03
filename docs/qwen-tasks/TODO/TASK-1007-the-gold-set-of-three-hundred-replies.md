# TASK-1007 — the gold set: 300 replies for a human to label

**WRITE `REPORT.md` NOW, EMPTY, IN YOUR WORKTREE ROOT, BEFORE YOU READ ANYTHING
ELSE. Then append to it as you go.** One line per step you finish and one line
for anything you could not do and why. A report written at the end is a report
that does not exist when the session dies.

## Why this exists

The reply classifier's corpus-wide precision on `positive` was measured at
**38.5%** in email, and `positive_reply` is the metric the operator has made
PRIMARY. There is no gold set, so that number cannot be improved or even
trusted. Worse: **three artefacts of the same 899 replies exist on disk and no
two of them agree.** A count from a classification is meaningless unless it
carries the identity of the run that produced it.

This task produces the thing that fixes that: 300 real replies for the operator
and Martina to label BY HAND.

## The one deliverable

A table of **300 rows**, four columns, in this order:

| column | content |
|---|---|
| `reply_text` | the reply, verbatim, not truncated |
| `channel` | `email` or `linkedin` |
| `our_message_before` | the message WE sent that this is a reply to, verbatim |
| `label` | **EMPTY.** The human fills this in. |

Plus a hidden-from-the-labeller `row_id` as the first column so the labels can
be joined back.

## THE OUTPUT DOES NOT GO IN GIT

These are real replies from real people. `docs/` is committed; `work/` is
gitignored for exactly this reason. Write the table to:

    C:\Users\Zvonimir\Desktop\resonate-ops\gold-set\

as **both** `gold-set-300.csv` (for Martina, openable in Excel, UTF-8 BOM so
Croatian characters survive) and `gold-set-300.jsonl` (for the join). Create the
directory. **Do not commit either file. Do not put a single reply's text in any
file under `docs/`, in a commit message, or in `REPORT.md`.**

## The five things that decide whether this is worth anything

1. **NAME THE SOURCE ARTEFACT AND ITS IDENTITY.** Find the three disagreeing
   classified artefacts of the 899 replies. Say in `REPORT.md` what each one is,
   where it is, when it was produced and how many rows it has. Sample from the
   RAW replies, not from any classification. Record the source file, its mtime
   and its md5 in `REPORT.md`.

2. **THE LABEL COLUMN IS EMPTY AND THE MODEL'S GUESS IS NOT IN THE TABLE.** A
   labeller shown the classifier's answer will agree with it; that is the whole
   reason the 38.5% was never caught. Write the classifier's existing prediction
   for each `row_id` to a SEPARATE file, `predictions-300.jsonl`, so precision
   can be computed after the humans are done and never before.

3. **STRATIFY AND STATE THE SEED.** 300 of 899 is a sample, so say how it was
   drawn. Stratify by channel and by the classifier's predicted class so every
   class — including the rare ones — has enough rows to measure, and record the
   per-stratum counts. Use a fixed seed, write the seed in `REPORT.md`, and
   prove a re-run reproduces the same 300 BY DIGEST, not by count.

4. **`our_message_before` IS THE HARD PART AND MAY BE UNKNOWN.** It has to be
   the actual preceding message in that thread, per lead per channel. Where you
   cannot establish it, write `UNKNOWN` — never a guess, never the campaign's
   template, never the step-1 copy because it was probably that. Report how many
   of the 300 came back UNKNOWN; if it is most of them, that is itself the
   finding and you should stop and say so rather than fill the column.

5. **THE LABEL VOCABULARY IS THE ONE THAT ALREADY EXISTS.** Do not invent a
   second vocabulary for facts that already have names. Read the canonical
   outcomes out of `src/accountpolicy.py` (`OUTCOMES`) and put that list, with a
   one-line gloss each, at the top of the CSV as a comment block and in a
   `README.md` next to it, so the two humans label against the same words. If a
   reply fits none of them, the labeller writes `none-of-these` — that list is a
   deliverable too.

## Constraints

- **No code change.** No change under `src/`, `tests/` or `config/`. If you
  believe a fix is needed, write it in `REPORT.md` and carry on.
- **A FULL SUITE MAY BE RUNNING.** Do not run `python -m tests.offline`,
  `unittest discover` or `scripts/run_suite.py`. Individual modules only, and
  only if you actually need one.
- **Your own worktree**, never the main checkout, never master. The worktree
  name must not contain `aiark`, `apify`, `blitz`, `bison`, `contactout`, `glm`,
  `heyreach`, `slack` or `xai` — that list is substring-matched against the
  ABSOLUTE PATH by `test_invariants`' send guard, and such a name exempts every
  file in the repository.
- **No `git stash`** — the stack is shared across ~40 worktrees. Use a WIP commit.
- **No provider call, no provider write, no Slack post.** Everything here is a
  local read.
- `git push` is refused by the Claude Code classifier. Commit locally and report
  the branch and SHA.

## Acceptance

    py -3 -c "import csv,io; r=list(csv.DictReader(io.open(r'C:\Users\Zvonimir\Desktop\resonate-ops\gold-set\gold-set-300.csv', encoding='utf-8-sig'))); print(len(r)); print(sorted(r[0].keys())); print(sum(1 for x in r if x['label'].strip()))"

Must print `300`, the five column names, and **`0`** — zero filled labels, because
the humans have not labelled it yet. A non-zero third number means something
pre-filled the column and the gold set is void.
