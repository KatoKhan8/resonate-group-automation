# TASK-046 - Preview the REAL campaign, through the HeyReach path

Extends TASK-045, which is integrated. Read it and its script first.

## WHAT TASK-045 BUILT, AND WHAT IT DOES NOT ANSWER

`scripts/render_preview.py` renders RAW TEMPLATE -> VARIABLES -> FINAL
RENDERED COPY, shows where a fallback would fire, and reads well. Keep it.

It takes a FIXTURE name - `balanced`, `li_heavy`, `no_linkedin`,
`missing_variable` - not a campaign. And it renders through
`cadence.expand_step`, which is the TEMPLATE path.

The operator's question was "what does the PERSON ACTUALLY RECEIVE" about the
real Productive HeyReach campaign, and that campaign does not go through
`cadence.expand_step`. It goes through:

    heyreachfactory._plan        builds a graph of MERGE FIELDS
                                 `{connection_note}`, `{connected_1}`, ...
    custom_fields_for            each lead's own approved words, per role
    heyreach.build_lead_pairs    those words onto the wire as customUserFields
    HeyReach                     substitutes them into the graph

So the preview currently shows a different message from a different pipeline.
`grep -n "heyreach\\|custom_fields\\|merge" scripts/render_preview.py` returns
nothing.

## GOAL

Preview a REAL campaign by its canonical id, through the path that campaign
actually uses.

## SCOPE

1. Accept a canonical campaign id - `productive-linkedin-production-v1`,
   `productive-email-liheavy-v1` - as well as the existing fixtures. Fixtures
   stay: they are how the tests run without an estate.
2. For a HeyReach campaign, render the real chain per lead:

       graph node  ->  `{connected_2}`
       lead field  ->  that contact's approved li3 words
       result      ->  what the person reads

   and show the FALLBACK text beside it, so a reviewer sees what fires if the
   variable does not arrive.
3. Render BOTH BRANCHES. An already-connected prospect walks
   `connected_1..connected_4`; a not-yet-connected one walks the invite then
   `message_2..message_4`. They are different messages and both must be shown.
4. Flag anything that would embarrass us, loudly and at the top: a literal
   person or company name in the graph, a `{{double brace}}`, a variable no
   lead supplies, two rendered steps that read the same.
5. Do not read `work/**` to obtain leads if that means writing it. Read-only.

## THE POINT, so the shape is right

The "hi jacob" defect survived a green suite, a provider readback and a
field-for-field comparison. It would not have survived one person reading the
rendered output. This artifact is for that person. Optimise it for being READ,
not for being complete.

## FILES ALLOWED

`scripts/render_preview.py`, `tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

Every `src/**` file - if the preview needs something the factory does not
expose, say so in FINDINGS rather than changing the factory. `work/**` is
READ-ONLY.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials. The preview must work from canonical state
alone; if it cannot render without calling a provider, that is a finding.

## TESTS REQUIRED

- the rendered LinkedIn text for a fixture lead equals what
  `build_lead_pairs` plus the graph would produce - assert they AGREE rather
  than eyeballing;
- both branches appear;
- a missing variable is reported and its fallback shown;
- a literal name planted in a fixture graph is flagged at the top.

## DONE CONDITION

`python scripts/render_preview.py productive-linkedin-production-v1` prints,
for several real cohort leads, every step of both branches with its variables,
fallback and final text - and a reviewer can decide from it alone whether the
campaign may be sent.
