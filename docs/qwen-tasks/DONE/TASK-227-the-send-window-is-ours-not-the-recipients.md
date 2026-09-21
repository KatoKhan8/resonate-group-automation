# TASK-227 - the send window is ours, not the recipient's

## The observation, 2026-09-18

EmailBison campaign 487 sends on a `09:00-17:00 Europe/Zagreb` window. Its
ten recipients are not in Zagreb. 09:00 Zagreb is 03:00 US Eastern, so a
cohort of US recipients gets its openers scheduled across their night, and
only the last two hours of our window land in their morning.

`bison.set_schedule(campaign_id, days, start, end, timezone)` already takes a
timezone. Nothing computes which one a cohort should get.

## The objective

A function that proposes a campaign send window from the RECIPIENTS, and
refuses to guess.

Falsifiable requirements:

1. Given a cohort of records, resolve each recipient's timezone from evidence
   that already exists - the geo/ISO resolution on branch
   `geo-iso-resolution-2026-09-17`, company location, and whatever
   `src/geo.py` already resolves. **Missing evidence is never positive
   evidence, and a guessed timezone is worse than a missing one.** CLAUDE.md
   says so explicitly, and this is the task where it bites.
2. Return a classified result per recipient: RESOLVED (with the evidence that
   resolved it), AMBIGUOUS, or UNKNOWN. Never a default dressed as an answer.
3. Propose ONE window for the cohort - a campaign has one schedule - chosen
   so the maximum number of RESOLVED recipients fall in local business hours,
   and REPORT who does not rather than hiding them in an average.
4. **When too few recipients resolve, return NO PROPOSAL and say why.** The
   caller then uses the existing production default. An incomplete timezone
   architecture must not block an otherwise valid approved send - but it must
   not fabricate precision to avoid blocking one either.
5. READ-ONLY and PURE. It proposes; it does not call `set_schedule`, does not
   write canonical state, and has no provider side effect.

## Tests required

A cohort that is unambiguously single-region proposes that region's window.
A cohort split across three continents returns NO PROPOSAL with the reason.
A cohort whose evidence is absent returns UNKNOWN per recipient and NO
PROPOSAL - and specifically must NOT return a country as a timezone when only
a country is known and that country spans several.

## Boundaries

No provider write. No canonical write. No credit spend. Do not change any
existing campaign's schedule.
