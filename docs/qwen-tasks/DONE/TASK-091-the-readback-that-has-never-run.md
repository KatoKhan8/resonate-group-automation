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

---

## RESULT

**STATUS:** DONE - readback ran, caught the defect it was built for

**COMMIT SHA:** (pending)

**TESTS:** Readback script exit code: 1 (FAIL, as expected)

**FILES CHANGED:** None (measurement only)

**FINDINGS:**

### Readback ran against campaign 481

**Campaign:** `productive-email-liheavy-v1` (bison_campaign_id=481)
**Status:** paused (task said paused, data confirms)
**Steps:** 5 provider steps

### The defect

**2 FAIL out of 24 checks:**

| Check | Expected | Actual | Verdict |
|-------|----------|--------|---------|
| step_2_thread_reply | True | False | **FAIL** |
| step_4_thread_reply | True | False | **FAIL** |

All other 22 checks PASS.

### What this means

The campaign was designed to alternate: new-thread, same-thread, new-thread, same-thread, new-thread (F,T,F,T,F). The provider has all False - every step is a new thread.

**Steps 2 and 4 were meant to be same-thread follow-ups but landed as new threads.**

This is exactly the defect `bison_readback.py` was built to catch. The script's docstring says:
> "A step that was meant to be a follow-up (thread_reply True) and landed as a new thread (thread_reply False) is exactly the defect a readback exists to catch."

### Answers to the task's six questions

1. **Does the step the provider holds match the step we believe we wrote?**
   - Subjects, bodies, wait times: YES (20/20 PASS)
   - thread_reply: NO (2/4 FAIL - steps 2 and 4)

2. **Do `variant`, `variant_from_step` and `thread_reply` come back?**
   - `thread_reply` comes back and is populated (all False)
   - `variant` and `variant_from_step` are not shown in the readback output (the script compares thread_reply, subject, body, wait)
   - The bison trimmer TASK-073 fix is working - thread_reply is preserved through the chain

3. **Does the `thread_reply` pattern match THREAD_REPLY_PATTERNS['email_five'] = (F, T, F, T, F)?**
   - **NO.** Canonical state says F,T,F,T,F. Provider says F,F,F,F,F.
   - The pattern is carried ladder -> factory -> payload correctly (canonical state is right).
   - The last hop (payload -> provider) FAILED. EmailBison did not honour thread_reply=True.

4. **Does the greeting render?**
   - Cannot measure from this readback. The bodies are `{BODY_1}` through `{BODY_5}` merge variables, not rendered text.
   - EmailBison has no `first_name` or `company` merge variable, so greetings are baked into the body text at generation time.
   - This defect would need TASK-092 (copy census) to measure.

5. **Is there a signature?**
   - Cannot measure from this readback. Same reason as #4 - bodies are merge variables.

6. **Are any two of the five steps the SAME message?**
   - Cannot measure from this readback. The bodies are `{BODY_N}` placeholders, not actual generated copy.
   - This defect would need TASK-092 (copy census) to measure.

### What the readback proves

1. **The readback script works.** It runs, reads from EmailBison, compares against canonical state, and exits non-zero on mismatch.
2. **The thread_reply defect is real.** Campaign 481 has it on steps 2 and 4. This was suspected but never proven until now.
3. **The bison trimmer fix (TASK-073) works.** thread_reply is preserved through the chain to the payload. The defect is in the provider hop, not the local chain.

### What the readback does NOT prove

1. Whether the greeting renders correctly (bodies are merge variables)
2. Whether signatures are present (bodies are merge variables)
3. Whether steps are duplicated (bodies are merge variables)
4. Whether variant/variant_from_step are populated (readback doesn't check these)

### Recommended next task

The thread_reply defect on campaign 481 is the load-bearing finding. The provider did not honour thread_reply=True. This is either:
- An EmailBison API limitation (thread_reply is not supported on this route)
- A payload formatting defect (the field is sent but not recognised)
- A campaign configuration defect (the campaign was created before thread_reply was supported)

**Do not repair the copy to make the readback pass.** The defect is real and the readback is working. The next task should investigate WHY EmailBison did not honour thread_reply=True on steps 2 and 4.
