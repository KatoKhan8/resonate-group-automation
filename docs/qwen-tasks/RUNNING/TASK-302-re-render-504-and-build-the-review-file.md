PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-302 — re-render 504 from productive.yaml and build the operator's review file

## Why this is yours and not Claude's

Every step of it is bounded and checkable against a file the operator already
approved (`config/productive.yaml`) and gates that already exist. Claude keeps
exactly one step in the middle — the provider write — and hands it back.

## The operator's requirement, verbatim in substance

> Post the first review file (504, re-rendered from productive.yaml, every
> step, sender name, pack fact) in #resonate-os with a clock time. I want the
> email and LinkedIn messaging side by side per lead where a LinkedIn profile
> exists.

## Stage 1 — YOURS. Render locally. No provider write.

250 leads in 504, five steps each.

1. Render every step from `config/productive.yaml` through `cadence.TEMPLATES`
   and `_variables_for`. **Never from a scratch script.** The incident came
   from `work/gencopy.py`, which invented its own copy and referenced
   `productive.yaml` zero times.
2. Carry the **template id** into each lead's custom variables. That is the
   provenance gate: a step with no template id is refused at activation.
3. **Signature = the mailbox owner's name from the sender pool**, per lead,
   never a constant and never the operator's name.
4. **Pack fact gate:** the quoted span must be a complete sentence carrying a
   verb, taken from the site BODY, never nav or menu text. A lead with no such
   sentence is **HELD, not sent generic.** Report the held count; it is a real
   number and the operator would rather have 180 good leads than 250.
5. Run `copylint` over all of it. Rule 1 is a WARNING in proof mode; the
   refuse-list is **full phrases plus signature-equals-mailbox-owner**, as the
   operator confirmed — NOT bare substrings. `"I work with"` as a substring
   refuses 286 of 333 leads of the client's own approved copy, measured on 491.

## Stage 1b — YOURS. LinkedIn coverage.

**Measured 2026-09-25 16:20Z: LinkedIn coverage on 504 is 0%** — 0 of 120
sampled leads carry a profile URL. The side-by-side column would be empty for
every row, so discovery has to run before the file is worth reading.

ContactOut enrich by email, the operator's own account, **no ledger cap**
(operator decision, 2026-09-25). Bind `linkedin_id` at enrolment later; for
this file you need the profile URL and the rendered LinkedIn message.

Report coverage as a number. **If it lands low, say so rather than shipping a
file whose second column is blank** — the operator asked for side-by-side
specifically and an empty column is a worse answer than a stated coverage rate.

## Stage 2 — CLAUDE'S, NOT YOURS. Stop and hand back.

Writing the rendered variables onto the 250 provider leads and reading them
back. Do not attempt it; the write scope is not open to you. Post your stage-1
output and say it is ready.

**Note for whoever does stage 2:** 504's leads must have OUR variables written
onto them even where the lead already existed at the provider. Operator
decision, 2026-09-25: "lead already exists" is NOT a stop signal — it means our
variables must be written onto the existing lead and read back before
activation. That is exactly the step the 09-22 push skipped, and it is how 77
blank emails were sent from 491-498.

## Stage 3 — YOURS. The file.

`work/review/504-2026-09-25.xlsx` **and** `.html`.

One row per lead: sender mailbox, sender name, lead email, company, persona,
cohort tag, subject, **full body of every step exactly as the provider will
send it**, pack fact, source URL, **and the LinkedIn message beside the email
where a profile exists.**

**Rows are read back from the provider after stage 2, never from our CSV.**
A review file built from what we intended to send certifies our intent, which
is not the thing that failed.

Then `reviewapproval.file_hash(path)` and post both the file and the hash.
Activation is refused until the operator replies `APPROVED 504 <hash>`.


## THE COLUMN SPEC — operator, 2026-09-25, standing for EVERY review file

One row per lead:

    sender mailbox | sender name | lead email | name | title | company
    cohort tag | persona
    each email step: subject + FULL BODY exactly as the provider will send it
    LinkedIn connection note and follow-ups, where a profile exists
    PERSONALISATION BLOCK (see below)

### The personalisation block

**Every scraped fact for that account**, not only the used one:

    source URL | retrieved date | the exact snippet | USED or NOT USED
    and for a USED fact: WHICH SENTENCE of the copy it feeds

The pack store already carries this. Measured 2026-09-25 16:35Z, a
`researchpack-*.jsonl` row holds `facts[]` with `fact_id`, `kind`,
`source_url`, `published_at`, `snippet`, and `retrieved_at` on the pack. So
this is a join, not a new crawl. Use `fact_id` as the key between the block
and the sentence.

**Why the operator wants the NOT USED rows.** The incident's "personalisation"
was a navigation bar. Showing only the fact we used shows only our own choice;
showing all of them and which we picked is what makes a wrong pick visible to
a reader. A real example still in the store right now:

    snippet: "Order your favorite dishes in seconds! Order Online Skip to
              main content Drinks Menu Order Catering Kerrville ..."
    kind:    site_page

That is nav chrome and it is what rule 1 certified as grounded. If your gate
would let that reach a subject line, the gate is wrong.

Posted as **.xlsx and .html** in #resonate-os.

## What would make this a FALSE PASS

- A review file generated from local render output rather than provider
  readback. The whole gate is that the provider's copy is what gets read.
- Reporting a lead as rendered when its pack fact is nav text. The incident's
  "personalisation" was a navigation-bar fragment and copylint rule 1 certified
  it as grounded.
- An empty LinkedIn column presented as "side by side".
- Any step whose signature is a constant, or is "Zvonimir".

## RESULT BLOCK

**STATUS: BLOCKED - live-state access owed**

**COMMIT SHA:** (pending)

**TESTS:** 9/9 pass in `tests/test_task302_render.py`

**FILES CHANGED:**
- `scripts/task302_render_504.py` - Stage 1 rendering script
- `tests/test_task302_render.py` - Tests for the rendering logic
- `docs/qwen-tasks/RUNNING/TASK-302-re-render-504-and-build-the-review-file.md` - this file

**FINDINGS:**

1. **Stage 1 script written and tested.** `scripts/task302_render_504.py` renders
   every email step for every lead through `cadence.expand_step` (which uses
   `cadence.TEMPLATES` and `cadence.template_vars`). It carries the template id
   on each step, resolves sender name from the mailbox owner via
   `senderownership.resolve_owner`, applies the pack fact gate (complete sentence
   with verb, not nav text), and runs `copylint.check_batch` over the result.

2. **Cannot execute against campaign 504.** This worktree has no `work/queue.jsonl`
   and no `work/campaigns.jsonl`. The `work/` directory exists but holds only
   `dispatch-interpreter.json`, `lead-batch-economic-buyer.json` (a stale snapshot
   from 2026-09-14), and `provider-write-refusals.jsonl`. The live queue with
   campaign 504's 250 leads is in Claude's worktree only.

3. **Stage 1b (LinkedIn enrichment) is a provider call.** ContactOut enrich by
   email requires API credentials and is a write to the provider. The task says
   "no ledger cap (operator decision)" but I hold no ContactOut key to call.
   The task's own measurement says LinkedIn coverage on 504 is 0% (0 of 120
   sampled leads carry a profile URL).

4. **Stage 2 is explicitly Claude's.** Writing rendered variables onto the 250
   provider leads and reading them back. The write scope is not open to me.

5. **Stage 3 depends on Stage 2.** "Rows are read back from the provider after
   stage 2, never from our CSV." Cannot build the review file without the
   provider readback.

**WHAT IS OWED:**

- **Claude:** run `scripts/task302_render_504.py --campaign 504` from Claude's
  worktree where `work/queue.jsonl` and `work/campaigns.jsonl` exist. This
  produces the Stage 1 render output.
- **Claude:** Stage 1b LinkedIn enrichment via ContactOut.
- **Claude:** Stage 2 provider write and readback.
- **Claude:** Stage 3 review file from provider readback.

**RISKS:**

- The rendering script uses `cadence.expand_step` which returns None for
  generated steps with no stored copy. Campaign 504's leads need to have
  generated copy (em1, em5) already written and approved on the record, or
  those steps will render as None.
- The sender name resolution depends on `senderidentity` rows existing for the
  campaign's email accounts. If accounts are unattested, sender name will be
  "UNKNOWN".

**RECOMMENDED CLAUDE ACTION:**

1. Run the rendering script from Claude's worktree
2. Execute Stage 1b LinkedIn enrichment
3. Execute Stage 2 provider write/readback
4. Build the review file (Stage 3)
5. Post the file and hash for operator approval
