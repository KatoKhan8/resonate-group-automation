# Inspecting a campaign before it runs

The point of everything in this document is one question: **what exactly would
go out, to whom, saying what, and why?** It should be answerable in full before
a single message is sent, and answerable by somebody who has not read the
code.

    python -m src.preview --client productive --batch 2026-08

That writes five files into `out/` and sends nothing. `would_send` is 0 in
every response, and a test reads the source of both modules to keep it that
way.

## The five files

| File | For | What it holds |
|---|---|---|
| `preview.html` | a person | the whole rehearsal, capped at 200 contact cards |
| `preview.json` | anything else | the same data, complete, every card |
| `emailbison-preview.csv` | inspection | every email step, formula-guarded |
| `heyreach-preview.json` | inspection | every LinkedIn step, with no campaign id |
| `report-preview.html` | the client | the report as it would read today |

The word "preview" is in every filename deliberately. These must never be
mistaken for something to upload, and `heyreach-preview.json` carries no
campaign id for the same reason: a file that could be posted as it stands is a
file somebody eventually posts.

The HTML cap is 200 cards because a full 5,000-domain page is 57 MB and no
browser opens it. What was left out is stated on the page, with a pointer to
the JSON. A page that silently shows the first two hundred of five thousand
reads as "this is all of it", which is a worse failure than being too large.

## What the top of the page tells you

Companies, contacts, email-eligible, LinkedIn-eligible, multichannel, held,
MX-blocked, lint failures, estimated credits, approval state — and under them a
table explaining what each number means in a sentence. A preview only a
developer can check is a preview nobody checks.

The interesting figure is never a single count. It is the drop between them:
five thousand domains became four thousand qualified, became eleven thousand
contacts found, became two thousand selected, became twelve hundred emailable.
That drop is the first thing a client asks about and the first thing this page
shows.

## What each contact card answers

Company, name, title, persona, email, verification state, MX provider and
classification, email eligibility, LinkedIn URL and eligibility. Then, in
order:

- **Why this person** — their role, plus any dated public fact about them, or
  an explicit sentence saying none was found and the copy leans on the role.
- **Why this company** — structured facts, the hook, and dated research.
- **Research used** — company and person separately, each fact with its URL,
  date and source.
- **Personalisation evidence** — exactly what the model was shown, how many
  pieces were considered, the quality band and the five components behind it.
- **Final cadence** — every step, in order, with the copy exactly as the
  prospect would receive it.

## The timeline is never compressed

Every configured step appears, including the ones that will not happen:

    DAY 1   EMAIL     blocked    lint: placeholder
    DAY 3   LINKEDIN  unapproved
    DAY 5   EMAIL     skipped    mx_protection:proofpoint
    DAY 8   LINKEDIN  waiting    requires an accepted connection

A reviewer who approves a cadence that silently lost half its touches has
approved something other than what they were shown. The same rule applies to
contacts: those found but not selected are listed with why.

## Channel eligibility

Reachability is two verdicts, not one boolean:

| Situation | email | linkedin | mode |
|---|---|---|---|
| verified address, usable profile | yes | yes | multichannel |
| behind Proofpoint, usable profile | no | yes | linkedin_only |
| no verified address, usable profile | no | yes | linkedin_only |
| verified address, no profile | yes | no | email_only |
| neither | no | no | **held**, not dropped |

Nobody is dropped for losing one channel, and every closed channel carries a
stable code (`mx_protection:proofpoint`, `verification_not_sendable`,
`no_linkedin_profile`) plus a sentence a person can read.

## MX classification

Eleven gateways and four mailbox hosts are recognised from MX hostnames by
label-boundary suffix match, never substring. Each carries a policy category:

- **normal** — ordinary mailbox host or relay
- **protected** — filtering that quarantines some cold mail
- **high_protection** — reliably quarantines it; sending costs reputation and
  buys nothing
- **unknown** — no MX evidence identifies the operator

The default policy blocks `high_protection` (Proofpoint, Mimecast, Barracuda)
and allows the rest. A client may block or allow any category. Mailbox hosts
stay unblockable even by category: blocking `normal` would reach Google,
Microsoft, Zoho and Fastmail, which is where most prospects keep their mail.

Blocking suppresses the **email channel**, not the contact. The record stays,
LinkedIn is untouched, and the reason is stored as
`email_excluded_reason = "mx_protection:proofpoint"`.

## The provider waterfall

ContactOut is first in every stage. A step that leaves ContactOut must declare
what has to be true to reach it, and offering no reason — or an invented one —
is refused rather than logged. Two ContactOut calls in sequence are the primary
path, not a fallback: what needs justifying is leaving the provider already
paid for.

Every step records reason, provider, expected cost, actual cost, result and
next reason. `actual_cost` stays `None` unless a provider actually reported
one, because a guess there would make the ledger worthless.

`python -m src.waterfall --describe` prints the whole policy.
`python -m src.waterfall --record <id>` audits one record's ledger for steps
taken without an accepted reason.

## Personalisation quality

Five components, each computed by arithmetic anybody can follow:

    company_specificity   a dated, attributable fact about THIS company?
    person_specificity    anything about THIS person beyond a title?
    evidence_recency      how old is the best thing we found?
    evidence_reliability  attributable to where?
    persona_relevance     does it bear on this persona's angle?

The band is low / medium / high and follows a rule written out in full in the
module. Nothing specific about the company caps the band at **low** however
good everything else is. A title scores as the floor rather than as zero,
because naming the floor is what stops anyone inventing a recent LinkedIn post
to fill the gap.

A campaign may set a minimum band; contacts below it are **held** for a human.

## What is never done

- No email, LinkedIn message or connection request is sent.
- No campaign is launched, and no provider campaign is mutated.
- Nothing is posted to Slack. `slack_preview()` returns the payload that would
  be posted, with `delivered: false` and the reason beside it.
- No paid enrichment, Apify actor or model call runs during a preview.
- No GET endpoint in the documented API surface spends anything.

## The scale answer

Measured, not extrapolated, on 5,000 synthetic domains offline:

| | |
|---|---|
| whole pre-production path | 12.8 s (392 domains/second) |
| peak memory | 272 MB |
| DNS lookups | 4,109 for 8,928 contacts — one per domain |
| planned provider calls | 17,856 |
| expected credits | 12,150 (21,436 maximum) |
| queue file | 19.9 MB |
| preview.html | 1.2 MB (capped) |
| slowest phase | building the simulation, 8.0 s |

Every phase grows linearly with the batch, checked per phase rather than in
total, because one quadratic phase inside an otherwise linear run is exactly
what a single total hides.

    python -m src.scalesim --sizes 100,1000,5000
