# GLM adversarial review - collision

2026-09-17T18:11:21.891223+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## collision.check_account

`glm-5.3`, 52.22s, usage {'prompt_tokens': 678, 'completion_tokens': 2985, 'total_tokens': 3663, 'reasoning_tokens': 2614, 'cached_tokens': 640}.

1. **FINDING** — the staging exclusion can flip the account verdict from IN_SEQUENCE to CLEAR, and the docstring's own invariant paragraph only defends `emails_sent_total`, never `in_sequence`.

2. **Trigger state:** one lead at `acme.com` whose only sequence membership is in a campaign this system built that is *scheduled but not yet launched* — zero emails sent, so it passes `staging_artifact_evidence`'s four arms ("has never sent an email to anybody" is a retrospective predicate; a campaign launching tomorrow satisfies it).

**Call order:** `check_account("acme.com")` → `without_our_staging` drops that membership row → `any(p["in_sequence"] ...)` is now False and `sent == 0` → verdict `CLEAR`.

**Consequence:** whatever gates enrollment on this verdict treats the account as untouched and enrolls a second sequence. When the staging campaign launches, every lead on its roster is in two live sequences: double sends from the same sending domain, reply-collision, and 100% duplicate enrollment for that roster at whatever size it was built. Scale is proportional to the pre-launch roster, not to some edge rate.

3. **Smallest fix:** compute `anyone_in_sequence`, `sent`, and `verdict` from the pre-exclusion people (snapshot before the loop); keep the exclusion cosmetic, confined to `our_staging_excluded` and the `people` detail.

**Risk:** this re-pollutes the verdict with dead staging artifacts — an account our own cancelled campaign sat on reads IN_SEQUENCE, and operators skip accounts that were genuinely free. That measurable lost reach is the exact problem the exclusion was built to solve; the fix trades a send-time collision for a check-time false alarm.

## collision.without_our_staging

The call did not return.

GlmMalformedResponse: glm: answered 200 with an empty completion (finish_reason='length'). Refusing rather than returning '', which would be read as a bad answer instead of no answer


---

## CLAUDE VERIFICATION, 2026-09-17

**FINDING 1 (`check_account`): REJECTED as stated. FALSE POSITIVE, and the
reason is instructive.**

The defeat requires `without_our_staging` to drop a membership row whose
status is `in_sequence`, so that the recomputed `rebuilt["in_sequence"]` flips
to False. It cannot. `_excludable` refuses any status outside
`EXCLUDABLE_MEMBERSHIP`, which is `frozenset({'sending_paused', 'stopped'})`.
Measured directly:

    status='in_sequence'     excludable=False
      "membership reads 'in_sequence', which our own zero-send staging
       does not leave behind"
    status='stopped'         excludable=True
    status='sending_paused'  excludable=True

GLM was shown one function's source and inferred a constant it could not see.
That is the documented shape of this tool - "the output is a LEAD, not a
VERDICT" - working exactly as intended, and it cost one verification.

**THE ADJACENT HAZARD IS REAL, and GLM reached it by the wrong route.** A
campaign of OURS that is staged and left `paused` produces membership rows
reading `sending_paused`, which IS excludable, and such a campaign CAN later
be activated. `staging_artifact_evidence`'s four arms are all retrospective -
"has never sent" is satisfied by a campaign that is about to. So between
staging cohort A and activating it, cohort B can be built at the same accounts
because A's rows are excluded.

What closes it is order rather than design: the moment A activates, its rows
read `in_sequence`, stop being excludable, and B's activation is refused by
the account gate. The second activation fails closed. **That is a property
nothing asserts**, and it deserves a test rather than a paragraph - a staged
paused campaign, a second cohort at the same account, and the assertion that
whichever activates second is refused.

Right now this is not hypothetical furniture: campaign 485 is a DRAFT holding
the same ten leads as 487, and its membership rows read `stopped`.

**FINDING 2 (`without_our_staging`): NOT DELIVERED.** The call returned 200
with an empty completion and `finish_reason: length` - the model spent its
whole budget on reasoning tokens. The adapter refused to return `""` rather
than letting an empty answer read as "no defeat found", which is the correct
failure. Re-run with a larger `--max-tokens`.
