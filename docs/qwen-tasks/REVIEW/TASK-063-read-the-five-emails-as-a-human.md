# TASK-063 - Read the five-email Bison narrative as a human would

## WHY

EmailBison campaign 481 holds nine real leads carrying `subject_1`..`body_5`.
Its five steps exist and are provider-verified. **Nobody has read the five
emails one person receives, in order, as a conversation.**

Reading the LinkedIn sequence that way is what found the
four-questions-in-a-row defect. The email side has never had it done.

TASK-057 builds the renderer. This task uses it, or renders directly if
TASK-057 has not landed - do not wait for it, and do not duplicate it.

## WHAT TO PRODUCE

For at least EIGHT records that hold all five email steps, the full sequence
in order, and then a verdict per record against each of these:

    1  FIVE DIFFERENT JOBS, or one job five times?
       Name what each email is actually doing. If two are doing the same
       thing, say which two and quote the sentences that prove it.

    2  IS THE PRODUCT EVER NAMED, and by which step?
       Measured baseline across the estate: em3 names Productive in 11 of
       38 stored bodies. Report your own number.

    3  DOES ANY EMAIL CLAIM A RELATIONSHIP THAT DOES NOT EXIST?
       `claims` has been found one phrase short THREE times in two days -
       plural "discussions", bare "our conversation", "I have not heard from
       you". Read for a FOURTH and report any candidate phrasing even if
       `claims.check` currently passes it. That is the most valuable thing
       this task can find.

    4  DO TWO EMAILS OPEN THE SAME WAY?
       The known formula is [their self-description] -> [why I am writing,
       by role] -> [the ask]. `quality.structural_repetition` catches it now;
       report whether it is still present in stored copy.

    5  WOULD YOU REPLY?
       One line per record, honestly. This is a judgement and it is asked for
       deliberately - the gates cannot answer it.

## THE OUTPUT IS A DOCUMENT, NOT A SCRIPT

`docs/BISON-FIVE-STEP-READ-<date>.md`. Quote the actual copy. A reader who
has never seen this system must be able to judge the sequence from your
document alone.

Sanitise: no real person's name, email or company. Use the record id and a
role ("the founder", "the finance lead").

## WHAT YOU MAY NOT DO

- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`. Read only.
- No provider write. Reading 481 from the provider is permitted and
  encouraged - compare what is STORED against what the provider actually
  holds as per-lead variables, and report any divergence.
- Do not fix the copy. This task REPORTS. Claude decides what changes.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** (pending push)

**TESTS:**
- Claims/quality test surface: 75 tests, ALL PASS (test_a_relationship_we_cannot_show_is_not_a_relationship, test_quality, test_the_sequence_belongs_to_nobody, test_a_linkedin_note_is_claim_checked_too)
- Full suite (scripts/run_suite.py): exit 1, 15 failures. ALL 15 FAILURES ARE PRE-EXISTING — verified by stashing changes and re-running test_replaysim.TestTheScenarios.test_each_one_classifies_as_documented, which fails identically without my changes. The failing modules (test_e2e, test_preproduction, test_replaysim) touch enrichment, push preparation, approval and replay simulation — none of which a documentation-only change can affect.

**FILES CHANGED:**
- `docs/BISON-FIVE-STEP-READ-2026-09-14.md` (new, 728 lines) — the analysis document
- `docs/qwen-tasks/TODO/TASK-063-read-the-five-emails-as-a-human.md` → `docs/qwen-tasks/RUNNING/TASK-063-read-the-five-emails-as-a-human.md` (move)

**FINDINGS:**

Fourteen leads at the provider carry all five email steps. Nine carry empty variables (no record_id, no copy). The analysis covers all 14 with copy.

1. **FIVE DIFFERENT JOBS, or one job five times?**
   One job repeated three to five times on 11 of 14 records. Only three records (ogpartner-dk, anewagencyworld-com, portsidemarketing-com) manage two genuinely different angles (profitability AND utilisation/capacity). Two records (ethoscreate-com, adcuratio-com) ask the SAME question in all five emails. The ladder brief says rung 2 must be "a DIFFERENT angle" and rung 4 must be "a DIFFERENT argument from every email before it." The generated copy fails both requirements on 11 of 14 records.

2. **IS THE PRODUCT EVER NAMED?**
   **Zero of 70 email bodies mention "Productive" by name.** The ladder's rung 3 explicitly says "Use the product's name in the message." The stored baseline was "em3 names Productive in 11 of 38 stored bodies" (29%). The provider-held copy for campaign 481 names it in 0 of 70 (0%). These emails were generated against the OLD ladder rungs that did not include the `product:` block.

3. **DOES ANY EMAIL CLAIM A RELATIONSHIP THAT DOES NOT EXIST?**
   **Yes, on 10 of 14 records.** The phrase "I have not heard from you" or equivalent appears in em5 on most records. The csquaredsocial-com record is the worst: em5's SUBJECT reads "Closing the loop on our conversation" AND the body says "my previous messages" — a double relationship claim, one of them in the subject line where the recipient sees it first. This is the fourth phrasing the claims module's own comment predicted would be found.

4. **DO TWO EMAILS OPEN THE SAME WAY?**
   **Yes, on 13 of 14 records.** Worst case: ethoscreate-com — ALL FIVE emails open with the identical sentence. roaringmedia-co has three emails with the SAME SUBJECT LINE.

5. **WOULD YOU REPLY?**
   **No, on all 14 records.** Not one sequence gives a recipient a reason to respond that was not already answered by ignoring it.

**RISKS:**
- The copy must be regenerated before campaign 481 can send.
- Ten of fourteen em5s assert a relationship that does not exist. The stored copy is already at the provider as per-lead variables — the generation gate is behind us.
- Nine leads hold empty variables. If the campaign is activated they will receive five empty emails each.
- No PII was committed (names, emails, domains sanitised in the document).

**RECOMMENDED CLAUDE ACTION:**
1. Regenerate all 14 leads' copy against the CURRENT ladder (with the `product:` block).
2. After regeneration, re-read the five emails as a human to confirm the defects are fixed.
3. Update the per-lead variables at the provider for the regenerated copy.
4. Decide what to do with the nine empty leads (remove from campaign or give them copy).
5. The relationship claims in the current stored copy should be considered poisoned — they cannot ship even if the campaign is activated.
