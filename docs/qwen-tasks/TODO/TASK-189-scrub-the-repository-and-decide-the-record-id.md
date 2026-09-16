PRIORITY: P1
DEPENDS:

# TASK-189 - 77 domains, 107 names, and one convention that is PII by design

## WHERE THIS SITS

TASK-178 strengthened the PII guard and it is now red, correctly:

    test_every_email_address_is_on_a_reserved_domain     4 test emails
    test_no_linkedin_url_with_real_vanity_name           1 handle
    test_no_real_client_prospect_or_roster_domain       77 real domains
    test_no_real_person_or_client_named                107 real names

Across 19 files, most of it older than today. Claude scrubbed the LinkedIn
handles already. The rest is this task, and it is bulk work with one genuine
question buried in it.

## THE QUESTION THAT IS NOT BULK

The guard flags `adcuratio` as a real name. It appears because the system's
record ids are derived from prospect domains:

    adcuratio.com   ->   adcuratio-com

`semcasting-com`, `roaringmedia-co`, `savagebrands-com` and hundreds like them
appear in `docs/CLAUDE-HANDOFF.md`, in context resets, in cohort documents, in
state files and in the queue itself. They are the system's primary key.

**A record id derived from a prospect's domain identifies that prospect exactly
as well as the domain does.** So the convention is a PII leak by design, in
every document that names a record, and no amount of scrubbing individual files
fixes it while the convention stands.

Answer this before scrubbing anything:

1. How many tracked files contain at least one domain-derived record id, and
   how many distinct record ids appear? Count, do not list.
2. What would a non-identifying record id cost? Where is the id generated, what
   reads it, and what breaks if it becomes a hash - state files, queue lines,
   provider lead `record_id` fields already written at EmailBison, documents,
   scripts. Be specific about the provider side: leads in campaign 481 carry
   `record_id` values that we cannot rewrite.
3. Is the guard right to flag them, or should record ids be allowlisted as a
   distinct category from prospect names? Argue it, and note that the answer
   decides whether this guard can ever be green.

Do NOT change the convention. It is an operator decision and it reaches
provider state we do not own.

## THEN THE BULK

4. Scrub the 4 test emails onto reserved domains, and the 77 domains and 107
   names in `docs/` and `scripts/`, hashing consistently - the same input must
   give the same hash everywhere, so a reader can still follow one company
   across two documents.
5. **Do not touch `tests/test_fixture_hygiene.py` or the forbidden-value lists
   any guard reads.** Those files are the one place the real strings must stay;
   hashing them there disables the detector. Claude did this by accident this
   morning and reverted it within a minute. The guard excludes itself from
   scanning for exactly this reason.
6. Do not edit a worker's RESULT block to reach green. If a result block
   carries PII, report the file and let Claude decide - one has already been
   scrubbed on those grounds and the precedent is Claude's to set, not yours.
7. Report what remains red after your scrub and why, separating "still leaking"
   from "flagged by the record-id convention".

## THE TRAP

Consistency is the whole value. If `adcuratio.com` becomes one hash in one
document and a different hash in another, every cross-document analysis in this
repository becomes unreadable, and the cost of that is higher than the leak.
Use one function, salt it the same way everywhere, and write down what it is.

Second trap: git history. Everything you scrub stays in history, and the
rewrite is an operator decision. Do not rewrite history, do not force-push.
Say in the deliverable that the working tree is clean and history is not.

## WHAT YOU MAY NOT DO

- No provider writes, no provider calls.
- Do not change the record-id convention or the code that generates ids.
- Do not weaken, skip or `expectedFailure` any hygiene assertion.
- Do not rewrite git history. Do not force-push. Do not delete a branch.
- Do not print the values you find into the deliverable - counts, paths and
  line numbers only.

## FILES ALLOWED

    docs/   scripts/   (scrubbing; NOT qwen-tasks RESULT blocks)
    docs/PII-SCRUB-2026-09-16.md   (new - counts and locations, no values)
    scripts/task189_*.py

## FILES FORBIDDEN

    tests/test_fixture_hygiene.py   src/   work/   config/
    docs/qwen-tasks/**  (RESULT blocks)

## DELIVERABLE

The record-id counts, the cost of changing the convention including the
provider-side ids we cannot rewrite, your argument on whether the guard should
allowlist them, the consistent scrub with its hash function written down, and
what remains red split into still-leaking versus convention-flagged.
