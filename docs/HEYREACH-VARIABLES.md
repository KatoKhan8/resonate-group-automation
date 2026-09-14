# HeyReach variables: what the provider actually accepts

Measured 2026-09-14 by reading the sequence of every campaign in the client's
HeyReach estate - 81 of 83 returned one - and counting every `{VAR}` and
`{{VAR}}` occurrence. This is provider truth, not documentation.

## THE SYNTAX IS SINGLE BRACES

    single-brace occurrences   3,295
    double-brace occurrences       0

**Zero campaigns anywhere in this estate use `{{double}}` braces.** Anything
written with them would reach a prospect as literal text, because HeyReach
would not recognise it as a variable and would not substitute it - and the
provider does not error on an unknown variable, it sends the fallback.

## WHAT IS ACTUALLY USED, by occurrence

    {FIRST_NAME}       1197      the prospect's first name
    {COMPANY}           922      the prospect's company
    {MY_FIRST_NAME}     598      THE SENDER'S first name
    {POSITION}          228      the prospect's job title
    {INDUSTRY}          228
    {LOCATION}          108
    {MY_LAST_NAME}        8
    {Icebreaker}          6      the only CUSTOM field in the whole estate

67 of 81 campaigns use at least one.

## THREE THINGS THAT FOLLOW

**1. The built-ins cover more than we use.** `POSITION` and `INDUSTRY` are
provider-filled and appear 228 times each; our sequence uses neither, so we
are asking the model to write what the provider would substitute for free.

**2. `MY_FIRST_NAME` is the SENDER, and it is the third most used variable in
the estate.** Nothing we generate uses it. A message that names who is writing
reads differently from one that does not, and this is the cheapest
personalisation there is - it needs no research at all.

**3. `Icebreaker` is the only custom user field in 81 campaigns, used 6
times.** Our design sends EIGHT custom fields per lead
(`connection_note`, `connected_1`..`connected_4`, `message_2`..`message_4`).

That is far beyond anything this estate has exercised. It is not known to be
wrong - `heyreach.build_lead_pairs` carries arbitrary `customUserFields` and
`refuse_unsupported_sequence` refuses a push whose variables are not all
supplied - but it is UNPROVEN AT THIS SHAPE on this provider, and the first
live push is what establishes it. Treat a whole-message-in-a-variable design
as the thing being tested, not as a given.

## THE RULE THIS SETTLES

Campaign-level copy may contain NO literal person, company or title. It
carries `{FIRST_NAME}`, `{COMPANY}`, `{POSITION}` and named custom fields, and
every custom field must be supplied for EVERY lead in the push or the push
refuses - which `refuse_unsupported_sequence` already enforces, because a
variable nobody supplies renders as the fallback and the prospect receives
copy this system did not write.
