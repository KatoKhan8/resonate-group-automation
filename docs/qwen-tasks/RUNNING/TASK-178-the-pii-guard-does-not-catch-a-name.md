PRIORITY: P1
DEPENDS:

# TASK-178 - the PII guard does not catch the column the name moved to

## WHERE THIS SITS

Three times in one morning a worker hashed the obvious PII field and committed
the name in a different one. Claude caught all three by hand, before push, and
that is not a control.

    TASK-174   hashed email_hash, name_hash, first_name_hash - and wrote
               contact_key in plain text, which is a person's name as a slug.
               Ten real names. Also committed scripts/task174_raw_data.json,
               a raw provider dump, which the rules forbid outright.
    TASK-176   hashed nothing. Three real prospect names in the result block
               and in two scripts, one of them alongside the company they
               work at.
    TASK-171   two unhashed domains in a findings document.

And one leak is older than this morning:

    docs/BISON-COHORT-LIVE-2026-09-15.md holds a prospect's full display
    name next to their domain and lead id. Committed before today.

There is already a PII guard - TASK-095 fixed it once - and it passed every
one of these.

## THE QUESTION

1. **Find the guard and read it.** Which test enforces the PII rules, what
   does it actually scan, and which of the four leaks above would it catch if
   the files were re-added today? Run it and prove the answer rather than
   reading the assertions.
2. **Why did it miss a name in a slug?** `ray-kingman` and `ray.kingman@` are
   the same person and only one of them looks like PII to a regex. Establish
   what the guard tests for - field names, value shapes, both - and where a
   name-shaped slug falls through.
3. **Sweep the repository as it stands.** Every tracked file. Report every
   occurrence of a prospect or seat-holder name, an unhashed prospect domain,
   an email address, a LinkedIn profile URL, or reply text. Do not fix them
   yet - count them and name the files, because the count is the finding.
4. **Then strengthen the guard** so all four leak shapes fail the test, and
   fix the occurrences the sweep found in `docs/` - EXCEPT any that are in a
   task result block, which Claude will handle, since editing a worker's
   recorded result is different from editing a document.

## THE TRAP

A guard that greps for a fixed list of known names is a guard that passes
tomorrow. The leaks above were `contact_key`, a display name, and a raw dump -
three different shapes, none of them predictable from the last one. Test the
SHAPE: a value that looks like a human name, a value that looks like a domain,
a field whose name is not on an allowlist in a file that is committed.

Second trap: record ids like `semcasting-com` are the system's own identifier
convention and appear in dozens of committed documents by design. A guard that
fails on those is a guard somebody will disable within a day. Distinguish a
record id from a person's name slug and say how.

Third trap: git history. A leak scrubbed from the working tree is still in
history, and a history rewrite is an operator decision. Do not rewrite
history. Report what is in it.

## WHAT YOU MAY NOT DO

- No provider writes, no provider calls at all - this task needs none.
- Do not weaken or skip an existing assertion to make the suite green.
- Do not rewrite git history, do not force-push.
- Do not edit a task result block in `docs/qwen-tasks/`.
- Do not print the names you find into the deliverable. Report counts, file
  paths and line numbers. A PII report that lists the PII is the leak again.

## FILES ALLOWED

    tests/   (the PII guard)
    docs/    (fixing found occurrences, except qwen-tasks result blocks)
    docs/PII-SWEEP-2026-09-16.md   (new - counts and locations, NO values)
    scripts/task178_*.py

## FILES FORBIDDEN

    src/   work/   config/   docs/qwen-tasks/**/RESULT blocks

## DELIVERABLE

What the guard scans and which of the four leaks it catches today, why a name
in a slug falls through, the repository-wide sweep as counts and locations
only, the strengthened guard with the four shapes now failing, and the exit
code read off the process.
