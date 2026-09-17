# Seven of the ten live prospects are in America. The campaign sends on Zagreb hours.

2026-09-17. Provider truth for campaign 487, joined to our own records.

## The finding

    campaign 487 schedule   09:00-17:00, Mon-Fri, timezone Europe/Zagreb
    its ten live leads      US 7   CA 1   DK 1   BE 1
    in Croatia              ZERO

The ten scheduled sends, with their US Eastern and US Pacific equivalents:

    07:12Z  US   03:12 EDT   00:12 PDT
    08:24Z  US   04:24 EDT   01:24 PDT
    08:55Z  US   04:55 EDT   01:55 PDT
    09:46Z  US   05:46 EDT   02:46 PDT
    10:00Z  BE   12:00 CEST
    11:13Z  DK   13:13 CEST
    12:35Z  CA   08:35 EDT
    12:42Z  US   08:42 EDT   05:42 PDT
    13:22Z  US   09:22 EDT   06:22 PDT
    14:00Z  US   10:00 EDT   07:00 PDT

**Four of the seven American prospects are scheduled to receive a cold email
between 03:12 and 05:46 their time**, and if any of them are on the west
coast, between 00:12 and 02:46. The two European prospects land at midday,
which is the window working exactly as designed - for the two people it fits.

The campaign name says it out loud and nobody read it as a problem:
`RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL V3`.

## The client already declared the right policy

`config/clients/productive.yaml`, read through `geo.windows`:

    email     09:00 - 11:30    LOCAL
    linkedin  09:30 - 16:00    LOCAL
    days      Mon-Fri

So the intended contract is a **two and a half hour window in the prospect's
own morning**. The provider is running an eight-hour window in ours. These are
not the same policy and the provider's wins, because nothing connects the two.

## The architecture is built. Nothing on the sending path calls it.

`src/geo.py` resolves country, region and timezone from whatever location
evidence a record has, with `timezone_confidence` and an explicit refusal
where the evidence is too thin - "a guessed timezone is worse than a missing
one" - and `geo.schedulable()` is the predicate that says whether a record may
be scheduled at all.

`src/schedule.py` goes further and is worth quoting, because it was written
for exactly thisproblem:

> When each cadence step would land, in the prospect's own local time. A batch
> spanning London, New York, Zagreb and Sydney has no single "09:30" - it has
> four, they are 15 hours apart, and two of them change by an hour on
> different weekends.

It handles DST by computing offsets through the IANA zone on each step's own
date, rolls a step that lands on a weekend forward and records the roll, and
refuses rather than guessing.

**`src/schedule.py` has ZERO importers.** `grep` finds none in `src/`, none in
`scripts/`, and one test. `geo.send_window` and `geo.schedulable` are called
from `src/demo_outreach.py` - a demo - and from segment labelling. **No
production sending path consults either.**

This is the defect CLAUDE.md names as the recurring one: a thing computed
correctly that nothing downstream reads. Here it has a cost measured in
prospects emailed at four in the morning.

## What our data can actually support today

Every record with a sendable contact carries `company_facts.offices`, and
every one of those strings ends in an ISO country code:

    records with a sendable contact          67
    with at least one parseable ISO code     67   (US 41, GB 6, CA 5, PL 4,
                                                  DE 4, BE 3, SG 3, AU 3,
                                                  NL 2, JP 2, IN 2, DK/IE/
                                                  ES/AT/KR/SE 1 each)
    with MORE than one country               4    (ambiguous, needs a rule)

But run through the designed entry point, `geo.from_record`:

    timezone_confidence HIGH     21
    timezone unresolved          46
    geo.schedulable() == True    21 of 67

**Thirty-one per cent.** The gap is not missing data - it is that
`geo.resolve` matches free text against city and country NAMES, and the
evidence we hold is an ISO CODE. `resolve(country="US")` returns "no usable
location evidence" while `resolve(country="US", city="Austin")` returns
`America/Chicago` at high confidence. `geo` already holds `ISO_TO_COUNTRY`;
the offices parser never reaches it.

Feeding the trailing ISO code in would resolve the 26 non-US records to a
country-level zone immediately. **It would not resolve the 41 US ones**, and
geo says why itself: a US state is the only thing that makes a US company
schedulable. Those need a city or state out of the office string, which is
present in some of them and not in others.

## What must NOT be done

**Do not change 487's schedule.** Not yet, and not on this evidence alone.
Three reasons, in order of how much they cost to ignore:

1. **The provider semantics are unproven.** Whether EmailBison interprets a
   window in the campaign's timezone, the workspace's, or the recipient's -
   and whether it supports recipient-local sending at all - is being asked of
   the vendor's documentation now (`scripts/grok_provider_research.py`,
   question `timezone`). Changing a window on a guess about whose clock it is
   would be the same class of error as everything above.
2. **487 has ten scheduled rows with fully rendered copy**, the first real
   artefact this campaign has produced. `bison.set_schedule` is a PUT on a
   live campaign and what it does to an existing queue is not known.
3. **`scheduled_date_local` on those rows is already six hours off**
   `scheduled_date` while Zagreb is UTC+2. Something in this provider's
   timezone handling is not what it appears, and that is a reason to measure
   before writing, not after.

## The order of work this implies

1. **Prove the provider semantics** - Grok on the documentation, then a
   readback against our own campaigns. Until then every option is a guess.
2. **Close the ISO-code gap in the offices parser.** Bounded, testable, no
   provider contact, and it moves resolution from 21/67 toward 47/67.
3. **Decide what US records need** - city, state, or a person-level signal -
   and price it. 41 of 67 is the majority of the addressable estate.
4. **Give the next campaign a schedule chosen per timezone bucket**, rather
   than retro-fitting 487. A cohort is already the unit of a campaign
   (`PRODUCTION-SCALE-POLICY.md`); a timezone bucket is a coherent cohort
   dimension and needs no new concept.
5. **Connect `src/schedule.py` to something.** It is the only component here
   that already knows the answer.
