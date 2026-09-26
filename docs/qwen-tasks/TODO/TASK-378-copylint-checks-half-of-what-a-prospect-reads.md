PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-378 — three copylint rules, and one field reader, are blind to half of what a prospect reads

**GLM adversarial review**, `docs/glm-reviews/copylint.md`, reproduced
independently 2026-09-26 evening against `origin/master` (`1a8d9a92`) — both
findings below CONFIRMED CURRENT, not stale.

## Finding 1 (P0, BYPASS) — fabricated claims in LinkedIn/subject/P.S. text pass silently

`check_batch` already builds `rendered = whole + "\n" + subjects + "\n" + extra`
and uses it for `unrendered_variable`, `empty_sentence`, the CTA-link rules and
the case-study rules. **Three earlier rules never look at it:**

    untraceable(whole, pack)              — only email bodies
    buzzwords_in(whole)                   — only email bodies
    for earlier in bodies[:-1]: FINALITY  — only email bodies

Reproduced: a lead whose five email bodies are clean and traceable, with a
LinkedIn connect note fabricating **"$120M raise and 40% headcount jump"**,
returns `check_batch(...)["refused"] == False`. The only rule that fires is
`step1_without_pack_fact`, a WARNING that does not block. An invented number in
a LinkedIn message today reaches a prospect with nothing to stop it.

**Secondary, same root cause:** `COMPANY_CLAIM`'s trigger-word whitelist (13
words) misses a claim with no trigger word ("Acme closed a $40M round in
March"), and its specifics regex `\b\d[\d,.]{1,}\b` requires 2+ digits, so a
single-digit invention ("8 of your posts") is never extracted as a specific at
all — worth tightening in the same pass, not a separate task.

## Finding 2 (P0, FALSE-REFUSE-EVERYTHING) — `_body` doesn't read the provider's own field name

    def _body(step):
        return step.get("body") or step.get("text") or ""    # never email_body

    def _subject(step):
        """`email_subject` is the provider's spelling and `subject` is ours...
        the sequence rows carry `email_subject`/`email_body` and nothing else."""
        return step.get("subject") or step.get("email_subject") or ""

`_subject` was patched to read the provider's real field name; `_body` was
not. Feed `check_batch` rows shaped like the provider's own sequence rows
(`email_subject`/`email_body`, nothing else) and every body reads as `""` —
every lead fires `empty_step`, the batch refuses 100% of the time. A gate
that refuses everything during a push gets worked around by its caller, which
is worse than the gate not existing: nobody notices it stopped meaning
anything.

## Build

    src/copylint.py   MODIFY

1. Point `untraceable(...)`, `buzzwords_in(...)` and the finality loop at
   `rendered` (or the LinkedIn/subject/P.S. text specifically, if checking
   `rendered` wholesale double-counts something already checked — decide and
   say which).
2. `_body(step)` reads `email_body` the same way `_subject` reads
   `email_subject`.
3. Tighten `COMPANY_CLAIM` and the specifics regex only as far as closing the
   two concrete gaps above requires — no broader rewrite.

## Acceptance — RUN each, paste real output

1. **The reproduction above, re-run, now refuses.** Paste the exact lead and
   `check_batch` output, before (False) and after (True, naming the LinkedIn
   claim).
2. **Guard failure:** revert the `rendered`-vs-`whole` change alone, confirm
   the reproduction goes back to `refused: False`, restore.
3. **The provider-shaped-rows case:** a batch of leads whose steps carry only
   `email_subject`/`email_body` (no `subject`/`body`) is linted correctly —
   real violations still refuse, and a genuinely clean batch does NOT refuse
   100% of the time. Paste both.
4. Re-lint the fifty's existing copy (same as TASK-354's acceptance 6) and
   report the delta against the count already on record — a change this size
   to three rules may catch real prior violations; name any lead newly
   refused.
5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the current baseline. Not a count.

## What this task may NOT do

- Do not widen or weaken any rule to make a draft pass — this task only makes
  existing rules see the text they already claim to police.
- Do not touch the CTA-link rules (TASK-354) or the case-study rules
  (TASK-365) — both already read the right text; this task is about the three
  that don't.
- Nothing sent, nothing activated. Production freeze.

## Deferred from the same review, not this task

- `report["rules"]` is written but nothing reads it (`report_lines` iterates
  the module-global `RULES` instead) — dead field, `docs/BACKLOG.md`.
- `WARNING_RULES`'s "explicitly time-boxed to 2026-09-28" is a comment, not
  code — nothing reverts it automatically after that date. Worth a one-line
  follow-up task nearer the date, not now.
