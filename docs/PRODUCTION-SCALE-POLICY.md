# Production scale, cohorts and sender utilisation

Standing policy, set by the operator 2026-09-15. It governs how campaigns are
shaped and how leads are grouped, and it outranks convenience. It does NOT
outrank any safety or quality gate: nothing here is a licence to widen a gate,
raise a sender limit, or skip a human approval.

---

## 1. A campaign is a COHORT, not a person

The unit of a campaign is a **hypothesis about a group**, never an individual.
Personalisation belongs inside the campaign - in merge variables, enrichment
fields, per-lead generated fields and message variants - not in the campaign
boundary.

    target      ~50 qualified leads per normal cohort, where inventory supports it
    prefer      larger coherent batches where operationally useful
    never       hundreds of tiny campaigns because personalisation differs

A new campaign is justified by a real difference in **target cohort, signal,
hypothesis, cadence, sender strategy, a major messaging experiment, or an
operational constraint.** It is NOT justified because the company, the first
name, a sentence or an enrichment field differs.

**Do not fabricate cohort similarity to reach 50.** A signal with 17 qualified
leads is held and accumulated, merged with a genuinely compatible cohort, or
run explicitly as a small exploratory cohort with its sample size recorded.
Forcing unrelated leads together to hit a number destroys the attribution the
cohort exists to produce.

## 2. Every cohort is a durable record

    COHORT_ID        SIGNAL           ICP FILTER       QUALIFICATION RULE
    EXCLUSION RULE   LEAD COUNT       MESSAGE HYPOTHESIS
    CAMPAIGN         VARIANTS         SENDERS          START DATE
    OUTCOMES         CONFIDENCE       LEARNING

Grouping is by evidence-backed signal only - hiring and growth, leadership
change, headcount movement, service expansion, tooling or process signals,
delivery complexity, geographic expansion, funding, role, company type,
specialisation, a recent company event, prior engagement, or a signal
discovered from historical outcomes. **Where the data does not support a
signal, the signal does not exist.** A cohort assembled on a field that is
null for most of its members is a cohort about nothing.

Coverage is already measured and constrains this directly. First name, title,
company, domain, industry, headcount and persona are 100% on the 92 contacts
of not-dropped records; email is 94%, angle 88%, specialties 73% - all of
which need a safe fallback - and `employee_range` is 19%, which excludes the
record rather than guessing. Headcount is contested on the full estate: 7
conflicts and 64 range/value disagreements across 300 records, so it is not
safe as a cohort key on those.

## 3. Sender estate - measured 2026-09-15

`scripts/sender_capacity.py` writes `docs/state/SENDER-CAPACITY.json`.

    seats                      41
    healthy (active + auth)    33
    auth invalid but active     1    <- looks available, fails on use
    inactive                    7
    daily ceiling, healthy   1054 connection requests, 1143 messages
    healthy seats with NO active campaign   0

**Throughput has never been the constraint.** Campaign 599020 carried one
sender and zero leads while 33 healthy seats were configured for a thousand
connection requests a day. What blocked production was approval and copy
quality, and no amount of sender capacity addresses either.

The one number to read carefully: **zero healthy seats are uncommitted.**
Every healthy seat is already attached to at least one campaign, most of them
the client's own pre-Resonate campaigns. So "add more senders to a cohort" is
a question about reassigning seats that are already working, not about
picking up spares, and it needs the current per-seat load read before it is
answered.

### Two rules that may not be traded for volume

- **Never raise a per-seat limit to gain throughput.** Add senders, or add
  days. A raised limit changes the risk taken with a client's real LinkedIn
  account and is not an engineering decision.
- **An `authIsValid: false` seat is not capacity.** It accepts an assignment
  and then fails, which is worse than being absent, because the leads queue
  behind it looking scheduled.

## 4. Consolidation over proliferation

Before creating a campaign: *does this need a new campaign, or can it be
expressed inside an existing one through variables and variants?* Maintain a
campaign registry so the system knows its own experiments and cannot create a
duplicate. Prefer fewer meaningful campaigns with larger coherent cohorts,
rich per-lead personalisation and multiple variants.

## 5. Copy requirements apply to every campaign

No hardcoded names. Only merge variables the provider actually exposes -
HeyReach has its own set and per-variable fallbacks; **EmailBison has
`headline`, `industry` and `location` and NOTHING else**, no `first_name` and
no `company`, because the whole body travels as `body_N`. A greeting cannot be
delegated to EmailBison, so a broken one goes straight to a person and the
pre-write greeting guard is the only thing standing in front of it.

Product context must exist. Sequence progression must exist. No duplicate
conceptual message and no asking one question five times. **At least five
meaningful variants at experimentable positions where supported** - differing
in angle, tone, structure, hook, CTA, pain, product framing or personalisation
depth, never a synonym swap. Where an arm requires evidence the record does
not carry, the honest count is four; a fabricated observation is worse than a
missing arm.

## 6. Cadence is measured, not decreed

Five steps is a starting design, not a rule. The question is **"does step 5
generate incremental value?"** - not "did somebody reply in a campaign that
had five steps". Measure outcome, reply, positive reply and acceptance by
step, delay performance, drop-off, incremental replies from later steps, and
sender, cohort and variant effects where measurable.

Standing cautions from what has already been measured: the 8.49% reply rate
for 8-step sequences is UNREPRODUCED and may not be quoted. No open rate may
be quoted - `open_tracking` is False estate-wide, which is an absent
measurement and not a zero. An UNKNOWN reply is not a negative, and 53.4% of
unknowns are correctly unknown. INTERESTED measured 0.44 precision on the old
pattern set and the new set is unmeasured, which is not the same as good.

## 7. EmailBison gets the same philosophy

Coherent cohorts, not one campaign per lead. Personalisation through supported
variables. Correct signatures. Meaningful variants. Conversational sequences
where later emails are **same-thread follow-ups** rather than a new subject
every step - `THREAD_REPLY_PATTERNS['email_five']` is (F, T, F, T, F) and the
follow-up rung tells the model it is continuing a thread rather than only
flipping a flag.

Note what is NOT evidence: the estate has **no control group** for the
alternating structure. Every campaign with sends uses `thread_reply=True` at
step 2, and campaign 481 - the only one with False there - has zero sends. The
alternating design is a bet, and it is recorded as a bet.

## 8. Autonomy, and its boundary

Once a cohort passes the established gates, move it forward without asking:
create or update the campaign, assign appropriate senders, add the batch, read
back, and go live within the established rules. Do not require manual approval
for every normal batch that falls inside rules already set.

**The boundary is unchanged and is not a formality.** A human read of the
sequence still gates promotion - `pushable` was retired as the promotion
criterion precisely because raising it while the human read fails just
manufactures more copy nobody should send. `heyreach.add_leads` is not in
`providerwrites.SUPPORTED`, and enabling it is an operator decision. Bulk
approval to raise a count remains the single most damaging action available.

Do not block a good cohort because unrelated infrastructure is imperfect. Do
not weaken a correct gate to increase lead count. Both failures are available
at all times and the second is worse.

## 9. Success condition

Not "200 campaigns generated". A manageable number of meaningful campaigns,
coherent signal-based cohorts of 50-200+ where inventory supports it, multiple
healthy senders, multiple meaningful variants, real provider writes, real
readback, live activity, measured outcomes, continuous learning.

Optimise for maximum safe learning velocity, maximum useful live production,
minimum campaign chaos.
