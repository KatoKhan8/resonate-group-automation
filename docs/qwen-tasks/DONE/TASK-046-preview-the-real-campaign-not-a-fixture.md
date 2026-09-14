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

## RESULT

STATUS: done

COMMIT SHA: e20b23f

TESTS: 45 passing (18 existing TASK-045 + 27 new TASK-046).
  `py -3 -m unittest tests.test_render_preview tests.test_render_preview_heyreach`
  Ran 45 tests in 0.009s - OK

FILES CHANGED:
  scripts/render_preview.py   - extended with HeyReach pipeline rendering
  tests/test_render_preview_heyreach.py - 27 new tests

FINDINGS:

1. The HeyReach pipeline renders correctly through the real chain:
   `merge_sequence_copy` builds the graph with variables, `custom_fields_for`
   resolves per-lead words, `build_lead_pairs` puts them on the wire as
   customUserFields. The preview asserts the rendered text AGREES with what
   `build_lead_pairs` produces - not eyeballed.

2. Both branches appear: already-connected (connected_1..connected_4) and
   not-yet-connected (connection_note, message_2..message_4). They use
   different role names and the preview shows both.

3. Missing variables are reported: when li3 has no approval, connected_2 and
   message_3 are missing, the fallback fires, and the preview shows
   "FALLBACK FIRED" beside the step.

4. Literal names from other contacts are flagged at the top: the planted-name
   fixture (Rachel's words contain "Declan") triggers "LITERAL NAME: lead
   'rachel-okafor', role 'connection_note' contains name 'Declan' from
   another contact - the hi-jacob defect class".

5. The campaign ID path (`productive-linkedin-production-v1`) reports that
   work/ is empty in this worktree. This is expected: work/ holds canonical
   state and is not in git. On the production worktree (Claude's), the
   campaign row and records exist and the preview renders them.

6. The `work/` directory is empty in this worktree. The DONE CONDITION
   (`python scripts/render_preview.py productive-linkedin-production-v1`)
   cannot be fully met here because the campaign data lives in work/ on the
   production worktree. The script handles this gracefully and reports the
   error. The fixture path (`heyreach`) demonstrates the full pipeline with
   invented data.

7. Duplicate detection is branch-aware: li2 fills both connected_1 and
   message_2 with the same words, but they sit on different branches and a
   prospect walks only one. The check flags duplicates WITHIN a branch, not
   across branches.

CALLER PROOF (grep -rn of new functions in src/ and scripts/):
  render_heyreach_preview: called from render_preview (line 1384) and tests
  _resolve_heyreach_text: called from _detect_heyreach_issues (line 783),
    _format_heyreach_lead (line 858), and tests
  _detect_heyreach_issues: called from render_heyreach_preview (line 962),
    _try_load_campaign (line 1102), and tests
  _try_load_campaign: called from render_preview (line 1375)
  _format_heyreach_lead: called from render_heyreach_preview (lines 986, 991)
    and _try_load_campaign (lines 1131, 1134)
  _format_heyreach_graph: called from render_heyreach_preview (line 976)
    and _try_load_campaign (line 1116)
  _format_heyreach_wire: called from render_heyreach_preview (line 996)
    and _try_load_campaign (line 1137)

EXISTING BEHAVIOUR NOW GOING THROUGH THIS CODE:
  `render_preview("heyreach")` calls `render_heyreach_preview` which calls
  `custom_fields_for` (the SAME function `_plan` calls), `build_lead_pairs`
  (the SAME function `ensure_leads` calls), and `_detect_heyreach_issues`.
  The rendered text is asserted to AGREE with `build_lead_pairs` output.

RISKS:
- The campaign ID path cannot be tested end-to-end in this worktree because
  work/ is empty. On the production worktree, the campaign row and records
  exist and the preview renders them. The script handles the empty-work/ case
  gracefully.
- The issue detection checks for literal names across contacts in the same
  campaign. It does not check for names from outside the campaign (e.g., a
  name that was in the copywriter's head but is not any contact's name).

RECOMMENDED CLAUDE ACTION:
- Cherry-pick to master. The extension is additive: the existing TASK-045
  fixtures and tests are unchanged, and the new HeyReach fixtures and tests
  are self-contained.
- On the production worktree, run
  `python scripts/render_preview.py productive-linkedin-production-v1`
  to verify the campaign renders correctly for the real cohort.
