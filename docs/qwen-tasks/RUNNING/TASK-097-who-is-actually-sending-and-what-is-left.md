# TASK-097 - which senders are actually busy, and what capacity is really free

## WHAT IS ALREADY MEASURED

`scripts/sender_capacity.py` -> `docs/state/SENDER-CAPACITY.json`, read from
the provider 2026-09-15:

    seats                             41
    healthy (isActive + authIsValid)  33
    active but auth INVALID            1   looks available, FAILS ON USE
    inactive                           7
    daily ceiling, healthy          1054 connection requests, 1143 messages
    healthy seats with NO active campaign   0

**That last line is the one that matters and it is why this task exists.**
Zero healthy seats are uncommitted. Every one is already attached to at least
one campaign - mostly the client's own pre-Resonate campaigns, 83 of them
going back to April. So "assign more senders to a cohort" is a question about
seats that are already working, not about picking up spares.

## THE QUESTION

**How much of that 1054/day ceiling is actually free?**

A ceiling summed over seats that are each already running eight campaigns is
not capacity. Establish, per healthy seat:

1. Which campaigns is it attached to, and what is the STATUS of each? A seat
   attached to six FINISHED and two PAUSED campaigns is effectively idle; a
   seat on an IN_PROGRESS campaign is not. 12 campaigns in the account are
   IN_PROGRESS.
2. What has it actually DONE recently? A configured limit is not throughput.
   Find whatever the provider exposes on real activity per seat, and say
   plainly if it exposes nothing - "the provider does not report this" is a
   finding, not a failure.
3. What is its remaining safe headroom today, and what is that number based
   on - a measurement, or an assumption?
4. Cooldowns: `connectionRequestCooldown`, `connectionNoteCooldown`,
   `inMailCooldown` and `searchCooldown` are on every seat. What do they mean
   for how fast a seat can actually be reused? A planner that ignores them
   will promise throughput the provider will not deliver.

## THEN ANSWER THE OPERATIONAL QUESTION

Given the healthy estate as it stands: **how fast could a 50-lead cohort move
through a connection-request-then-message cadence, and how many seats would it
need?** Show the arithmetic. If the answer is "one seat could do it in two
days", then the multi-sender question is not urgent and you should say so.

## HARD RULES

- **Never propose raising a per-seat limit.** Add senders or add days. A
  raised limit changes the risk taken with a client's real LinkedIn account
  and is not an engineering decision. The policy states this and this task may
  not soften it.
- **An `authIsValid: false` seat is not capacity** even though it reports
  `isActive: true`. It accepts an assignment and then fails, which is worse
  than being absent because leads queue behind it looking scheduled. There is
  exactly one such seat; find out whether it is recoverable or should be
  excluded from every plan.
- Reads only. Do not attach, detach, pause or modify any seat or campaign.
- A seat is a REAL PERSON. Hash names, emails and profile URLs. The existing
  output does this; do not regress it. Seat ids and numeric limits are fine.

## DELIVERABLE

`docs/SENDER-UTILISATION-2026-09-15.md` and an updated
`docs/state/SENDER-CAPACITY.json` carrying per-seat campaign attachment and
real headroom. Separate what you MEASURED from what you ASSUMED, and give the
cohort-throughput arithmetic explicitly so the assumption behind it can be
attacked.
