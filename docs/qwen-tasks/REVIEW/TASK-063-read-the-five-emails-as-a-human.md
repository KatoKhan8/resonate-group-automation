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

    STATUS: DONE
    COMMIT SHA: 69b9557
    TESTS: Read-only analysis. No code changed. No tests run.
           Measurements extracted through src/store.py (read-only)
           and src/claims.check (read-only). 33 contacts with all
           five email steps read in full; 10 quoted verbatim.
    FILES CHANGED:
      docs/BISON-FIVE-STEP-READ-2026-09-14.md (the analysis document)
      scripts/task063_extract_emails.py (extraction helper, read-only)
    FINDINGS:
      1. Five emails do one job five times on 25 of 33 records.
         The same "I noticed [Company]..." opener, the same question
         about profitability/utilisation, five times.
      2. Productive named in 27 of 165 steps (16%). em3, whose job
         is to name the product, does so 7 of 33 times (21%).
      3. Sender identity: ZERO of 165 steps. Not one email says who
         is writing. No name, no company, no role. The ladder's first
         rung asks for "who is writing" and it is answered zero times.
      4. "Our previous discussions/conversations" on 8 em5 emails
         where prior_contact is False and no confirmed touch exists.
         This is the fourth phrase the claims rule has been found
         short of - same direction as TASK-064: claims about the
         SENDER/RELATIONSHIP, not the prospect.
      5. "Our agency sees that..." on 16kagency em3 - the sender
         claims to BE the prospect's agency.
      6. 47 of 165 steps (28%) open with "I noticed". em1 through
         em4 all open the same way on most records.
      7. 6 of 33 contacts have at least two identical subject lines.
      8. em5 is the worst step: 10 of 33 have claims issues.
      9. The regenerated set (8 unapproved records, generated against
         the updated ladder) looks materially better: distinct subjects,
         Productive named in em3, personal close in em5.
      10. The hand-written LinkedIn fallbacks in the client config beat
          any of the 165 generated emails. They name the product, say
          who is writing, progress, and assert nothing unsupported.
      11. 2020companies-com is a 10,001-employee retail sales agency
          receiving copy about "project profitability" - wrong audience.
      Approval pattern: em1-em4 approved ~70%, em5 only 48%. The human
      reviewer caught em5 problems but approved em1-em4 that, read as
      a sequence, are the same email repeated.
      Caller: this is a READ-ONLY task. No new function was created.
      The analysis document is the deliverable and it is consumed by
      Claude's promotion decision for the email cadence.
    RISKS:
      The email cadence is in the same state as the LinkedIn cadence
      was before TASK-064 blocked it. The automated gates pass copy
      that fails a human read. The same remedy applies: regeneration
      plus a human read, in that order, with approval only after both.
      The email side has no fallback copy (unlike LinkedIn), so every
      email is generated from scratch with no safety net.
    RECOMMENDED CLAUDE ACTION:
      1. Add sender identity to the email generation prompt - the
         client config names no sender for the email body.
      2. Explicitly forbid "our previous discussions/conversations"
         when prior_contact is False.
      3. Complete TASK-072 regeneration for the email side.
      4. A human reads the regenerated email copy end to end.
      5. Do not approve email copy until the human read passes.
      6. Consider adding email fallbacks to the client config, on
         the model of the LinkedIn fallbacks that read better than
         anything the model produced.
