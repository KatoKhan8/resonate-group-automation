# Operator authorisation and autonomous production policy

Granted by the operator 2026-09-15. **This survives `/clear` and a machine
restart because it lives here.** A fresh session reads this file and knows what
it may do without asking again.

Scope: Resonate OS / Productive outbound. Nothing here extends beyond it.

---

## 1. WHAT IS AUTHORISED

Normal reversible production operations required to get validated campaigns
live, performed autonomously and without per-action approval:

    regenerate copy                    update internal campaign state
    prepare and modify sequences       create and update campaign drafts
    create lead cohorts                add qualified lead batches
    assign available healthy senders   configure supported variables
    configure message variants         configure cadence
    PERFORM PROVIDER WRITES            perform provider readbacks
    activate/resume after verification pause on quality/readback/health failure
    run tests                          create tasks, dispatch Qwen workers
    review and integrate Qwen work     commit and push code, state, docs
    progressively scale verified batches

Explicitly including the previously blocked command:

    py -3 -m src.generate --regen-stale-ladder --live --client productive --limit N

**"--live" is no longer a reason to ask**, where the action is part of this
workflow and has passed the established gates.

### Approval revocation

Authorised to revoke stale approvals where evidence shows they protect legacy
copy that no longer meets the current production standard. **Preserve
approvals whose copy remains genuinely good.** Not approval-by-approval.

### Batch progression

    3 -> 10 -> 25 -> 50 -> larger justified batches

Each stage must pass readback and quality checks before the next. Batch size
may be increased autonomously on that evidence. **Do not regenerate all 560
blindly** - progressively, with measurement between stages.

## 2. WHAT REMAINS FORBIDDEN

Broad autonomy is not permission to be reckless. Never:

- expose credentials, commit secrets, print them unnecessarily, or put them in
  prompts, logs or task files. **Do not copy raw secrets into a Qwen prompt to
  give it access** - Qwen works through the established secure path only.
- bypass provider or LinkedIn safety or rate limits
- disable a correct quality gate to increase throughput
- fabricate lead or company data
- fabricate provider success
- **claim LIVE without a provider readback**
- perform destructive unrelated infrastructure or account actions
- purchase, upgrade or incur material new cost without asking
- delete valuable production data without a recoverable backup

## 3. WHEN TO ASK

Only for a genuinely NEW operator decision:

    irreversible destructive action
    material new spend
    scope beyond Resonate OS / Productive outbound
    legal or compliance ambiguity
    credential or security architecture change with meaningful risk
    a provider restriction forcing a choice between materially different
      strategies

**Routine status updates are not wanted.** Everything else inside the
authorised workflow is handled on evidence and existing safeguards.

## 4. CAMPAIGN AND COPY STANDARD

A campaign is a COHORT, never a person. Target ~50 qualified leads where
coherent inventory exists. Personalise INSIDE the cohort rather than
fragmenting into many campaigns.

LinkedIn sequences must progress:

    INTRO / CONTEXT -> PROBLEM -> PRODUCT / RELEVANCE -> FOLLOW-UP
      -> CLOSE / EASY OUT

Not the same question repeatedly. **No hardcoded recipient names** - use the
provider-supported variable, confirmed through documentation or readback, not
assumed. At least five genuinely different variants where the provider and the
experiment design support them, differing in angle, tone, structure, hook and
CTA - not synonyms.

EmailBison: coherent cohorts, multi-step cadence where evidence supports it,
**same-thread follow-ups where appropriate rather than a new subject every
time**, with greeting, first-name variable, Productive context, natural
progression, CTA and sender signature.

## 5. SENDERS

Use MULTIPLE healthy senders per campaign where the provider supports it.
Optimise aggregate throughput across the estate rather than pushing individual
accounts harder. Respect provider and account limits. Track per sender:
health, campaign assignments, queued leads, utilisation, configured capacity,
errors and restrictions. Rebalance when justified.

## 6. LEARNING

Every production action improves the system. Collect delivery, acceptance,
reply, positive, negative, unknown, step, variant, cohort, signal, sender,
cadence, timing, subject, CTA, threading.

Always distinguish **PROVIDER FACT** from **RESONATE RECONSTRUCTION** from
**ATTRIBUTION HYPOTHESIS**. Never present correlation as proven causation.
Never silently count an UNKNOWN reply as negative.

## 7. WORKER POOL

Eight workers, approximately eight distinct jobs running. READY backlog
significantly larger than worker count. A finished worker is reassigned
immediately; **Claude review runs concurrently and workers never wait for it.**
Duplicate claims prevented by the durable registry and atomic claiming.

Claude spends its scarce capacity on orchestration, review, high-value
reasoning and production decisions.

## 8. DURABILITY

Assume the laptop dies at any moment. A restart should cost minutes, not an
overnight run. Keep durable: task registry, worker assignments, review queue,
production ledger, experiment ledger, campaign and cohort state, next actions,
checkpoint. Never commit credentials, secrets or unnecessary PII.

## 9. HOW SUCCESS IS MEASURED

**Not tasks completed.**

    qualified leads moved into production
    coherent campaigns live
    healthy sender utilisation
    correct personalisation
    meaningful variants running
    provider-confirmed activity
    measurable outcomes
    learning fed back into Resonate OS

The immediate objective is to move from **zero live HeyReach leads** toward
controlled, verified, increasingly large production batches.

## 10. THE LOOP

    LEARN -> QUALIFY -> COHORT -> GENERATE -> VARIANTS -> VALIDATE
      -> CAMPAIGN -> SENDERS -> LEADS -> WRITE -> READBACK -> LIVE
      -> OBSERVE -> CLASSIFY -> LEARN -> SCALE

When something passes, ship it. When it fails, fix it. When a failure is
independent, keep the rest of production moving. Do not weaken a correct gate
to make something live, and do not spend a whole run polishing infrastructure
while production-safe cohorts could legitimately move.
