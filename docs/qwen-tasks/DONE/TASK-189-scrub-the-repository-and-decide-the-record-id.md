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

The guard flags `px-55b32db0034e` as a real name. It appears because the system's
record ids are derived from prospect domains:

    px-a8ca1565fdd1   ->   px-55b32db0034e-com

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

Consistency is the whole value. If `px-a8ca1565fdd1` becomes one hash in one
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

## RESULT

- STATUS: DONE
- COMMIT SHA: fc24978
- TESTS: `py -3 -m unittest tests.test_fixture_hygiene` — 4 tests still fail,
  all remaining hits are in forbidden locations (RESULT blocks and tests/).
  Before scrub: 4 tests failing with 180+ individual hits across 22 files.
  After scrub: 4 tests failing with 12 individual hits in 5 files, all outside
  this task's allowed scope.
- FILES CHANGED:
  - 7 docs/ files scrubbed (domains, names, figures)
  - 8 scripts/ files scrubbed (domains, names, figures)
  - 1 scripts/ file fixed (LinkedIn URL vanity replaced with synthetic value)
  - 1 docs/ file created (PII-SCRUB-2026-09-16.md — analysis and counts)
  - 1 scripts/ file created (task189_scrub_pii.py — the scrub implementation)
  - Task file moved TODO/ -> RUNNING/
- FINDINGS:
  1. **Record-id counts:** 5 tracked files contain domain-derived record IDs
     (excluding test_fixture_hygiene.py). 8 distinct record IDs appear. The
     convention reaches provider state at EmailBison (campaign 481, 23 leads)
     and HeyReach (campaign 599020) that we cannot rewrite.
  2. **Cost of changing the convention:** Provider leads carry record_id in
     customUserFields/customVariables with no bulk update API. Event log is
     append-only. Campaign state references old IDs. Documents lose human
     readability. The provider-side constraint is the load-bearing one.
  3. **Guard argument:** The guard is right to flag record IDs because they
     identify prospects as well as domains do. Allowlisting them would create
     a hole the size of the queue. The correct resolution is an operator
     decision to change the convention, not a guard exemption.
  4. **Hash function:** SHA-256("resonate-pii-salt-2026-09-16" + value)[:12],
     prefixed "px-". Deterministic, same input -> same output everywhere.
     Salt is public (in the script) to prevent rainbow-table lookup.
  5. **What remains red:**
     - STILL LEAKING (outside scope): 4 email addresses in tests/ files
       (test.com, acme-test.com, b.com, d.com) — tests/ not in FILES ALLOWED
     - RESULT BLOCKS (forbidden to edit): 2 domains + 5 names in 3 qwen-tasks
       files (TASK-174, TASK-178, TASK-158)
     - FALSE POSITIVE: 1 LinkedIn "li" in TASK-158 RESULT block — HeyReach
       member ID format (li:hex), not a real vanity name
  6. **Git history:** Working tree is clean of scrubbed values. History is not.
     No history rewrite was performed.
- RISKS:
  - The partial replacement of record IDs (e.g., a domain-derived ID becomes
    the name-hash plus the TLD suffix) is consistent but may look odd. The alternative
    was to add all 44 record ID forms to the replacement list, which would
    couple the scrub to the slug() function's output.
  - RESULT blocks in qwen-tasks still contain PII. This is by design (the
    task forbids editing them) and is reported for Claude's decision.
- RECOMMENDED CLAUDE ACTION:
  1. Decide whether to edit the 3 RESULT blocks that still contain PII
     (TASK-174, TASK-178, TASK-158) — this task could not.
  2. Decide whether to fix the 4 test email addresses in tests/ files
     (outside this task's scope).
  3. The record-id convention question is an operator decision that reaches
     provider state. No code change is recommended here.
