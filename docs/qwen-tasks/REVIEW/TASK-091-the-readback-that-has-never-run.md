# TASK-091 - the EmailBison readback has never been run against a campaign

## THE FACT

`scripts/bison_readback.py` was BUILT and is on master. Checkpoint D records
it plainly: **"BUILT. NOT yet run against a live campaign. Owed."**

The HeyReach side has the equivalent and it runs green - 27/27 PASS on
campaign 599020, re-verified after every change. EmailBison has no such
proof. A readback that has never run is an untested guarantee, and this
repository has been bitten three times by a green suite that asserted its own
assumption.

## WHAT TO DO - READ ONLY

**This task performs ZERO provider writes.** Every call is a GET. Campaign
activation, lead addition and sends are Claude's, not yours, and nothing here
needs them.

Run the readback against the two campaigns that exist and are ours:

    481   RESONATE - PRODUCTIVE - EMAIL - ZAGREB-H   paused, 23 leads,
                                                     5 provider steps, 0 sent
    451   RESONATE - PRODUCTIVE CANARY               completed, 1 sent

481 is the useful one: five real provider steps to compare against.

Report, per step:

1. Does the step the provider holds match the step we believe we wrote?
2. Do `variant`, `variant_from_step` and `thread_reply` come back? The bison
   trimmer was discarding all three until TASK-073; this is the first chance
   to prove the provider actually populates them on OUR campaign.
3. Does the `thread_reply` pattern match `THREAD_REPLY_PATTERNS['email_five']`
   = (F, T, F, T, F)? Checkpoint D says that pattern is carried ladder ->
   factory -> payload -> readback. Prove the last hop.
4. Does the greeting render? There is NO `first_name` and NO `company` merge
   variable at EmailBison - the whole body travels as `body_N`. So a broken
   greeting is not caught by the provider and goes straight to a person.
   Check for "Hey ,", "Hi undefined,", "Hi null," and a bare comma.
5. Is there a signature, and does it say who is writing? Sender identity was
   in ZERO of 165 email steps before the ladder fix.
6. Are any two of the five steps the SAME message? A duplicate follow-up is a
   send-safety problem, not a copy problem.

## WHAT NOT TO DO

- **No writes.** No PATCH, POST, PUT or DELETE to EmailBison. If the readback
  script has a write path, do not call it.
- **Do not activate, unpause or add a lead to 481.** It is paused on purpose.
- Do not use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and ZERO of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- Do not set `per_page` and believe it. It is accepted and ignored on every
  route; you get 15 rows regardless.
- Do not put real prospect addresses in the report. Hash them.

## DELIVERABLE

`docs/BISON-READBACK-481-2026-09-15.md` - a PASS/FAIL table in the shape of
the HeyReach one, with the exit code read off the process. If it FAILS, the
failure is the deliverable and the defect is the next task; do not repair the
copy to make the readback pass.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** dba8cbb
- **TESTS:** `py -3 scripts/bison_readback.py productive-email-liheavy-v1 --expect` -> exit 1 (22 pass, 2 fail). `py -3 scripts/bison_readback.py productive-canary-email-2026-09-13 --expect` -> exit 1 (5 pass, 3 fail).
- **FILES CHANGED:** `docs/BISON-READBACK-481-2026-09-15.md` (new), task file moved TODO -> REVIEW.
- **FINDINGS:**
  1. **thread_reply FAIL on steps 2 and 4 (campaign 481).** Expected (F,T,F,T,F) per `THREAD_REPLY_PATTERNS['email_five']`. Provider has (F,F,F,F,F). The ladder -> factory -> payload -> provider chain breaks at the last hop: the local state is correct, the provider stored `false` on every step.
  2. **variant and variant_from_step come back** from the provider (both empty/null on all steps). TASK-073's trimmer fix is confirmed - the fields survive the round-trip.
  3. **No greeting exists** in any body_N variable. No broken merge found (no "Hey ,", "Hi undefined,", etc.) because the body travels entirely as `{BODY_N}` with no first_name/company merge variables.
  4. **No signature** on any step. Sender identity is absent from all five steps on all 14 populated leads.
  5. **No duplicate bodies** across steps on any of the 14 populated leads. Three leads have duplicate subjects across steps (not bodies).
  6. **9 of 23 leads have zero body_N variables.** If campaign 481 were resumed, these leads would receive empty emails.
  7. **Campaign 451** has a shape mismatch: provider holds single-step `{SUBJECT}/{BODY}`, canonical moved to five-step `{SUBJECT_N}/{BODY_N}`.
- **RISKS:** Campaign 481 is paused, so the thread_reply defect reaches nobody today. If resumed, recipients get five separate threads instead of three threads with nested follow-ups. The 9 empty leads are a separate send-safety issue.
- **RECOMMENDED CLAUDE ACTION:** The thread_reply defect is the next task - the write path either did not send `thread_reply: true` in the POST body or the provider discarded it. Trace which.
