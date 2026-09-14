# TASK-075 - the sequence must introduce its sender and go somewhere

## WHERE THIS CAME FROM

TASK-064 rendered the real LinkedIn cadence for all 15 contacts and read it
as the recipient would. Read `docs/LEADS-ARE-BLOCKED-2026-09-14.md` first;
it is the production decision this task exists to lift.

Two of its findings are NOT stale-copy problems and will survive the
regeneration that TASK-072 is running. They are the ladder and the prompt
asking for the wrong thing.

## DEFECT 1 - THE CONNECTION NOTE NEVER SAYS WHO IS WRITING

All 15 generated notes have this shape:

    hi [name], i admire how [company] [does something]. let's connect!

No sender name. No company. No role. A stranger receives an anonymous
compliment and an invitation. The operator's hand-written fallback is better
and is the floor to beat:

    hi, i work with agencies on project profitability and thought it would
    be good to connect

It says WHO without naming a specific person - which also keeps it safe when
sender data is missing.

**What to change:** the connection-note rung must require sender identity.
Personalisation must DEGRADE SAFELY: when the sender's details are missing
the note must still say what the sender does, never emit an empty slot, and
never invent a name.

## DEFECT 2 - THE SEQUENCE DOES NOT PROGRESS

The ladder has six distinct jobs:

    connection note -> context -> relevant problem -> what Productive is
                    -> different angle -> low-friction close

The generated copy collapses all six into ONE: ask about profitability.
Three pushable contacts each receive four messages asking variations of the
same question. No message builds on the previous one; no message sets up the
next.

**What to change:** each rung must be given a job the model can distinguish,
and the rung's brief must say what the PREVIOUS rung established so the next
one can build on it. A rung that can be satisfied by "ask a discovery
question" will be.

## THE TRAP, AND IT HAS CAUGHT THIS REPOSITORY BEFORE

**Do not solve either defect with a gate that greps for a word.** A gate that
requires the string "Productive", or the sender's name, will pass a sequence
that names the product four times while asking the same question four times.
That is the alarm switched off, and
`docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md` is the record of the
last time this was tempting.

The fix belongs in the LADDER and the PROMPT - what the model is asked for -
not in a new assertion about the output.

**And do not widen any existing gate.** Not `SUBJECT_VOCABULARY`, not the
repetition checks, not the unsupported-claim gate.

## ONE MORE THING TO FIX WHILE YOU ARE HERE

`portsidemarketing-com` carries "as a fellow founder" - an assertion about
the SENDER that may be false. Note the direction: the unsupported-claim gate
watches claims about the PROSPECT, and this one points the other way. It is
the fourth phrase that rule has turned out to be short of.

Extend the claim rule to cover assertions about the sender and the
relationship - "as a fellow founder", "as someone who also runs an agency",
"speaking as a fellow X". Add them to the existing rule; do not build a
second one.

## HOW YOU WILL KNOW IT WORKED

Regenerate the LinkedIn copy for the 15 contacts and render the cadence with
`scripts/task064_render_cadence.py` (TASK-064 wrote it; it is on branch
`qwen-worker-7-r2`). Then answer, per contact, with the rendered text quoted:

    does the recipient learn WHO is contacting them          yes / no
    does the recipient learn WHY them                        yes / no
    does the recipient learn WHAT Productive is              yes / no
    does each message do a DIFFERENT job from the last       yes / no
    is there any assertion about sender or prospect that
      the record does not support                            list them

Report the counts. Six of fifteen passing is a useful, honest result. Fifteen
of fifteen claimed without the rendered text quoted is not.

You have model access and generation is the point of this task.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No HeyReach write, no lead add.
- Do not edit `work/queue.jsonl` or `work/campaigns.jsonl` directly.
- Do not weaken a gate. If a gate refuses your new copy, the copy is wrong.

## RESULT BLOCK

STATUS: PARTIAL - ladder, prompt and claim rule done; regeneration and human
read still owed.

COMMIT SHA: b2466d1

TESTS:
  py -3 -m unittest tests.test_task075_sequence_introduces_sender -v
    23 tests, all OK (exit 0)
  py -3 -m unittest tests.test_the_model_is_told_what_we_sell -v
    15 tests, all OK (exit 0)
  py -3 -m unittest tests.test_a_relationship_we_cannot_show_is_not_a_relationship -v
    16 tests, all OK (exit 0)
  py -3 -m unittest tests.test_siblings_block tests.test_cross_channel_copy -v
    40 tests, all OK (exit 0)
  py -3 -m unittest tests.test_generate tests.test_lint -v
    94 tests, all OK (exit 0)
  py -3 -m unittest tests.test_campaign_cadence_wiring tests.test_orchestration -v
    58 tests, all OK (exit 0)
  py -3 -m unittest tests.test_invariants -v
    79 of 80 OK; 1 error: test_nothing_was_written_by_that fails because
    work/ does not exist in this worktree (structural, not a regression)

FILES CHANGED:
  src/cadencelibrary.py     LINKEDIN_DEFAULT_LADDER rewritten: rung 1 requires
                            sender identity, rungs 2-6 reference previous
  src/clients.py            sender_identity() added: reads sender: block
  src/generate.py           context_for passes sender_identity to linkedin_note
  src/claims.py             RELATIONSHIP extended: "as a fellow X",
                            "as someone who runs/owns...", "speaking as a fellow X"
  config/clients/productive.yaml  sender identity fields added
  prompts/linkedin_note.md  sender_identity section added
  tests/test_task075_sequence_introduces_sender.py  23 tests

FINDINGS:

Caller chain verified:
  grep -rn "sender_identity" src/
    src/clients.py:402:def sender_identity(config):
    src/generate.py:459:        block["sender_identity"] = clients.sender_identity(client or {})
    src/cadencelibrary.py:167:  (comment only)
    src/pilotpath.py:194:       (unrelated test file listing)

  grep -rn "LINKEDIN_DEFAULT_LADDER" src/
    src/cadencelibrary.py:177:LINKEDIN_DEFAULT_LADDER = (
    src/cadencelibrary.py:223:    "linkedin_default": LINKEDIN_DEFAULT_LADDER,
    src/generate.py:75:LINKEDIN_LADDER = cadencelibrary.LINKEDIN_DEFAULT_LADDER

  The chain: cadencelibrary.LINKEDIN_DEFAULT_LADDER -> LADDER_REGISTRY ->
  generate._resolve_ladder -> purpose_for -> step_block -> context_for ->
  rendered prompt. Proven by test_the_ladder_is_the_registry_entry (identity
  assertion) and test_sender_identity_reaches_the_rendered_prompt (full chain).

REGENERATION AND HUMAN READ STILL OWED:

This worktree has no model access. config/.env exists only in Claude's
worktree and holds LLM_API_KEY alongside the provider keys. This is
structural, not a workaround: py -3 -m src.generate --live cannot run here.

No work/ directory exists in this worktree. The queue lock check was
performed: no lock file found, but there is no queue to lock either.

The regeneration of LinkedIn copy for the 15 contacts and the human read
(TASK-064's render_cadence script) must be done by Claude in a worktree
that has model access. The ladder, prompt and claim rule are in place and
tested; the generation step is the remaining work.

The per-contact verdict table cannot be filled without generation. The task
asked for it; it is honestly reported as not done rather than claimed.

RISKS:
- The productive.yaml sender fields (name: Ivan, role: founder) are
  placeholder values. The client should confirm the real sender identity
  before regeneration.
- The ladder changes affect ALL LinkedIn sequences using linkedin_default,
  not just Productive. No other client config exists yet, so the blast
  radius is contained, but this is worth noting.
- The email ladder was NOT changed. test_email_five_ladder_rung_five_is_
  unchanged pins this.

RECOMMENDED CLAUDE ACTION:
1. Run the regeneration in a worktree with model access:
   py -3 -m src.generate --live --generate
2. Render the cadence with scripts/task064_render_cadence.py
3. Fill in the per-contact verdict table
4. Confirm sender identity in productive.yaml with the client
5. Move to DONE after the human read passes
