# Resonate OS — the canonical product goal

Read this before proposing architecture. Every other document in this
repository describes how some part of the system works; this one says what the
system is *for*, and therefore which designs are correct.

## What this is

**An internal, multi-client, admin-operated lead generation engine for
Resonate Group.**

Resonate admins operate it. Clients receive reporting and results. That is the
whole operating model, and it settles a great many design arguments on its own.

## What this is not

- **Not a public SaaS.** No signup, no billing, no subscription management.
- **Not client-operated.** Clients do not configure campaigns, providers,
  ICPs, workflows, approvals or sending, and no screen should be built on the
  assumption that they will.
- **Not a Productive-specific automation.** See below.

Customer self-service, customer campaign builders, customer provider settings,
customer RBAC and customer-facing execution controls are **out of scope**. Do
not build them speculatively. If one is ever wanted it will be asked for.

## The hierarchy

    RESONATE
      -> CLIENT
        -> CLIENT WORKSPACE
          -> ICP(s)
            -> COHORTS / CAMPAIGN INTENTS
              -> ACCOUNTS
                -> CONTACTS
                  -> ACTIONS
                    -> PROVIDER CAMPAIGNS
                      -> OUTCOMES
                        -> REPORTING

A client may have many ICPs, personas, offers, angles, campaigns, sender pools,
provider bindings and lead sources. All of them hang beneath **one canonical
Resonate client identity**.

## Productive is client #1, not the architecture

Productive is the first real production proving ground and it must never become
a special case in engine logic.

The line is not whether the client's name appears — it is *where* it appears:

- **Client-specific CONFIGURATION is correct.** A client's ICP rules, angles,
  caps, sender pool, provider binding and budget all belong in that client's
  configuration and data. Do not strip a Productive value out of
  `config/clients/productive.yaml` merely because it names Productive.
- **Client-specific ENGINE LOGIC is a defect.** A branch in `src/` that behaves
  differently because the client is Productive is the thing to remove.

The engine should be able to run Productive, Client B and Client C through the
same code paths, differing only in what their configuration says.

## The non-negotiable invariant

    NO CLIENT CONTEXT
      = NO CLIENT DATA ACCESS
      = NO PROVIDER AUTHORIZATION
      = NO PROSPECT-FACING EXECUTION

Every safety-relevant object and action must be attributable to a canonical
client. A provider operation binds `client_id` + `provider` + the expected
provider workspace or account.

**Provider identity is not client identity.** Resonate owns the client
identity; a provider workspace is a *binding* beneath it. A credential that
happens to reach an estate proves nothing about whose estate it is.

## Cross-client contamination

These must be structurally impossible, and failing closed is the requirement —
detecting the damage afterwards is not enough:

- one client's lead reaching another client's campaign
- one client's suppression suppressing another's
- one client's sender sending for another
- one client's credential performing another's operation
- one client's reply landing on another's record
- one client's spend reaching another's ledger
- evidence gathered for one client licensing claims or actions for another
- a campaign from one client reconciled against another's

## Scale

A realistic client input is 30,000 domains, and several clients may run at
once. Optimise for bounded work, durable checkpoints, restart safety, budget
control, provider rate limits, fair scheduling between clients, and client
isolation — in that order, and never at the cost of correctness. A design that
requires the whole dataset to sit inside one synchronous operation is the wrong
design.

## Where this is going

The admin onboarding path:

    CREATE CLIENT -> CREATE WORKSPACE -> DEFINE ICP(s) -> DEFINE PERSONAS/OFFER
      -> BIND PROVIDERS -> ASSIGN SENDERS -> DEFINE BUDGET/LIMITS
      -> IMPORT DOMAINS/LEADS -> START ENGINE

After which routine lead-level execution should become increasingly autonomous:

    QUALIFY -> RESEARCH -> SELECT CONTACT -> ENRICH -> VERIFY -> PERSONALIZE
      -> BUILD CAMPAIGN -> SAFETY GATES -> EXECUTE -> OBSERVE -> REPLY STOP
      -> EXPAND/HOLD/STOP -> REPORT

A Resonate admin supervises the engine. An admin should not have to operate
every lead by hand or assemble every routine provider campaign by hand.

Autonomy here means fewer manual steps, never fewer gates. Nothing on this path
licenses relaxing suppression, collision, fatigue, reply-stop, claims, tenancy,
budget, approval, provider read-back or the kill switch.

## Reporting

Reporting is **read-only with respect to execution**, and the two architectures
stay separate. It should eventually summarise per client, ICP, persona, angle,
channel, campaign and period: accounts processed and qualified, contacts found,
verified and contacted, actions by channel, replies, positive replies, meetings,
opportunities, spend, cost per reply, cost per meeting, and conversion rates.

"Best ICP / persona / angle / channel / cadence" are reporting questions, and
they stay subject to the evidence rules the rest of the system already has: a
rate carries its numerator and its denominator, assignment is not exposure, and
a small sample says INSUFFICIENT_DATA rather than naming a winner.

## The multi-client acceptance test

The canonical proof, to be written as the client contract firms up: Client A =
Productive, Client B = a synthetic isolated client, with different ICPs,
domains, contacts, provider bindings, sender pools, suppressions, budgets and
campaign intents — processed through the same engine, proving zero cross-client
contacts, evidence, sender use, campaigns, provider access, suppression,
collision contamination (unless a policy makes it explicitly global), replies,
spend, approvals and actions. And proving that pausing or failing Client B does
not stop unrelated safe work for Productive.

## How to use this document

Audit against it; do not refactor merely because it now exists. When current
work touches code, prefer the design compatible with this goal. When two
designs are otherwise equal, choose the one that makes a cross-client operation
impossible rather than the one that detects it.
