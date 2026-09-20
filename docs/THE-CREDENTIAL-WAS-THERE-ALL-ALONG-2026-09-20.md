# Four providers reported unauthenticated. All four were configured.

2026-09-20. This is a record of MY error, kept because the failure mode is
cheap to repeat and expensive to believe.

## What was reported

A workforce audit checked credentials and reported:

    CONTACTOUT_KEY    absent
    BLITZ_KEY         absent
    APIFY_KEY         absent
    SLACK_BOT_TOKEN   absent

and concluded, in a checkpoint to the operator, that "the routing policy's
primary enrichment provider is unauthenticated, so the sourcing to enrichment
path cannot run at all", and that cohort expansion was blocked on a
credential only they could supply.

## What is true

    CONTACTOUT_TOKEN  AUTHENTICATION_VERIFIED   974ms
    BLITZ_API_KEY     AUTHENTICATION_VERIFIED   381ms
    AIARK_KEY         AUTHENTICATION_VERIFIED   557ms
    BISON_KEY         AUTHENTICATION_VERIFIED   159ms
    HEYREACH_KEY      AUTHENTICATION_VERIFIED   181ms
    APIFY_TOKEN       configured

ContactOut, read from its own free `/stats` endpoint:

    period      2026-09-01 -> 2026-09-30
    usage       1,553 of 38,232      -> 36,679 credits remaining
    search      396 of 117,815       -> 117,419 searches remaining

**Nothing was blocked on a credential.** The conclusion drawn from the wrong
names was the opposite of the truth, and it was delivered with numbers
attached, which is what made it credible.

## Where the error was, precisely

Not in the codebase. `src/config.py`, `src/providers/contactout.py`,
`src/web/api.py`, `src/web/security.py`, `tests/base.py` and
`config/.env.example` all say `CONTACTOUT_TOKEN` and always did. The only
wrong spelling anywhere in the repository was in the throwaway audit script,
which wrote its own list of names.

`CONTACTOUT_KEY` is a plausible name. That is the whole problem: it reads
correct, it produces a confident absent, and an absent credential is a
satisfying explanation for a stalled pipeline. A guess that confirms what you
already suspect is the hardest kind to catch.

## The structural fix

`scripts/credential_health.py` derives every name from `config.VARIABLES` -
the registry every real consumer already reads - so it CANNOT invent one. A
provider added to the registry appears there for free; a provider absent from
it cannot be reported on at all, which is the honest failure rather than a
confident wrong one. A test asserts the script still reads the registry,
because the moment it holds a literal list the bug class returns.

It also keeps five states apart, which is the second half of the lesson:

    CREDENTIAL_NOT_CONFIGURED         unset or blank
    CREDENTIAL_CONFIGURED_UNVERIFIED  set, and nothing has asked the provider
    AUTHENTICATION_VERIFIED           the provider answered as this account
    AUTHENTICATION_FAILED             the provider rejected it
    PROVIDER_UNAVAILABLE              unreachable - NOT a bad key

A set variable is not an authenticated one. A 200 is not proof the credential
belongs to the intended account. And a timeout is a provider being down, not
a credential being wrong - conflating those is how an outage gets diagnosed
as an auth problem at two in the morning.

## The general rule, which is the part worth carrying

**Ask the thing that uses it.** The adapter that spends the credit names the
variable; the registry lists it; the tests pin it. Three sources of truth
existed and the audit consulted none of them.

This is the same class as the standing correction about provider fields: a
field that reads empty is a question about the FIELD NAME until the raw keys
have been dumped. Here it was an environment variable rather than a JSON key,
and the lesson did not transfer because it had been written about providers.
It is about names.

## What it cost, and what it changed

Roughly a day of analysis pointed at the wrong bottleneck, and one checkpoint
told the operator that cohort expansion required something from them that it
did not. The corrected picture is materially different: ContactOut is live
with 36,679 credits, and a bounded sample of 40 contactless ICP accounts put
88% of them at an ALLOW account - so decision-maker discovery is both
affordable and, at the account gate, largely unobstructed.
