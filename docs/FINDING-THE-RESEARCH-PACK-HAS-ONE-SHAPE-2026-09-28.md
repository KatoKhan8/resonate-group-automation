# FINDING — `rec["research"]` has one shape, and the generation path now reads it

Closes section 4 of
`docs/FINDING-TASK-427-SELECTION-IS-PERSONA-PLUS-COMPOSITION.md`, which found
this and deliberately did not fix it. Measured on `8cdc9234` through
`generate._generate_via_campaign` with the real `productive` config and the real
offer library, one shape per run, nothing mocked but the model. Branch
`worktree-agent-a294c6a33a77f116d`.

## 1. WHAT WAS WRONG, AND WHY IT WAS WORSE THAN A TYPE ERROR

`src/generate.py:2472` built the campaign pipeline's account dict with

    "sources": (rec.get("research") or {}).get("sources") or [],

a DICT read. Measured, per shape:

    LIST (canonical)   AttributeError: 'list' object has no attribute 'get'
                       raised at that line, before the pipeline ran at all.
    DICT {"sources"}   got past it, then AttributeError: 'str' object has no
                       attribute 'get' inside `claims.support_text` — reached
                       through `_campaign_validator`, the `validate` callback
                       `generate_campaign` retries on — INSIDE
                       `_process_contact`'s broad `except Exception`. Every
                       contact came back hold_kind="error", stored_pairs=0.
    [] or absent       copy produced, and the account research pack never
                       reached the pipeline at all.

**The middle row is the reason this was the last blocker before `TASK-425` and
not an ordinary bug.** The run completed, reported no crash, and stored nothing.
A `TASK-425` artifact produced against it would have been EMPTY while appearing
to have worked — a confident, empty deliverable handed to the operator, which is
the exact failure shape the frozen acceptance criteria exist to catch.

## 2. WHICH SHAPE IS CANONICAL — COUNTED, NOT PREFERRED

The LIST, by every available measure.

    SCHEMA.md            documents `"research": [{source_type, provider,
                         source_url, actor, retrieved_at, field, title, fact,
                         record_id}]` — a list, and "a prompt sees at most
                         three entries".
    WRITERS (7 modules)  research.py (the production crawl, three call sites:
                         :414, :474, :732), companies.py:326, demo.py:182,
                         demo_outreach.py:417, benchmark.py:53,
                         synthetic.py:270/273, web/demodata.py:479
    READERS (19 modules) claims:519 · dossier:126/144/206 ·
                         eligibility:802/815 · generate:115/232 · icp:462/581 ·
                         packfacts:239 · preview:200 · qa:276 ·
                         qualify:86/484 · quality:217/362 · report:298 ·
                         segments:337 · personalization:99 · llm:754 ·
                         funnel:194/363 · simulator:299 · web/api:2052 ·
                         research:254/321/758 · benchmark:97 ·
                         demo_outreach:763 — plus 20-odd `scripts/`
    DICT READERS         one: generate.py:2472
    PRODUCTION STORE     1,582 records: 394 a populated list, 23 an empty
                         list, 1,165 absent, **0 a dict**

So the dict was a single reader's private idea of the shape. Nothing writes it
and no record carries it. The reader moved; the canonical state did not, and
**nothing added handles two shapes** — a tolerant reader over both is how the
two would have gone on drifting.

## 3. WHAT CHANGED

**`src/generate.py` — `_account_sources(rec)`**, a projection of the canonical
list, used by `_generate_via_campaign`.

It projects through **`research.for_prompt`**, the projection that already
exists: "the evidence a prompt may see: attributed, trimmed, and small",
quality-filtered and re-aged through `evidence.select`, capped at the three
entries `SCHEMA.md` licenses. That is what the OLD pipeline's `context_for`
already shows a model, so both generation paths are now shown the same evidence
and cannot drift. `field -> label`, `source_url -> url`, `fact -> text`, which
is the shape `copyprompts._numbered` and `copyprompts.source_url_for` read.

Measured over the production store: on the 394 records with a populated list,
`research.for_prompt` and `generate.research_block` deliver on the **same 125**
records. The other 269 carry only `weak`/`unusable` rows and correctly deliver
nothing — the projection narrows and never widens.

**A non-list `research` is refused by name** (`CampaignPipelineError`), not read
as an empty pack. Reading it as empty is the silent failure: copy written from
evidence that was dropped on the way in is indistinguishable from copy written
from evidence that was never there.

**`src/claims.py` was NOT touched.** It reads the canonical list correctly at
:519; it had six live callers and nothing about the shape question needed it.
Same for `src/dossier.py`.

## 4. THE SECOND DEFECT — the broad `except Exception`

`_process_contact` converted **any** exception into `hold_kind="error"` for the
contact. That is what hid defect 1 for a whole run: a crash presented as a
per-contact hold.

`generate_campaign.PIPELINE_DEFECTS = (AttributeError, TypeError, KeyError,
IndexError, NameError)` now propagate as `CampaignPipelineError`, naming the
contact and the exception type. This is the treatment `llm.ModelError` already
had two lines above, for the reason written there: **a fault that is not a
property of the prospect is never written onto the prospect.**

Three outcomes are now tellable apart by an operator reading a run report:

    NotApproved / CampaignPipelineError(offer)   a GATE refused, by name
    hold_kind=qualification|writer_hold|
              copy_refused|error                 the PROSPECT is unusable,
                                                 on the plan, run continues
    CampaignPipelineError(pipeline defect)       THE CODE BROKE — there is no
                                                 run report at all

**`ValueError` is deliberately NOT in that tuple.** `_parse_json` raises it when
a model answer is not JSON, and that is a model failure ON a record: it still
holds the contact, per operator decision 3 (2026-09-27). Asserted by
`test_a_model_answer_that_is_not_json_still_holds_the_contact`.

### WHAT WAS DELIBERATELY NOT DONE, AND THE COST THAT IS ACCEPTED

- **The `except Exception` was NOT removed.** Narrowing it to the defect types
  is as far as this goes. Everything else — a `ValueError`, a provider
  exception, anything a stage raises that is genuinely about this record — still
  holds the contact and still returns a plan.
- **NAMED RISK, not hidden:** a model answer that parses as JSON but carries the
  wrong types (`{"emails": "…"}`) raises `AttributeError` inside
  `_process_contact` too, and now stops the ACCOUNT's run rather than holding
  one contact. That direction is the conservative one — nothing is stored and
  the operator is told once — and a malformed-shape answer is a fault of ours or
  of the model, never of the company. It is a real behaviour change and it is
  the reason `ValueError` was left out of the tuple: the common case (no JSON at
  all) keeps its old handling.
- **A `CampaignPipelineError` aborts `generate.run()`'s whole pass**, because
  `run()` catches nothing per record and `generate_record` only catches
  `llm` errors. Earlier records in a live pass are already committed
  (`store.transaction` per record), so the loss is bounded to the failing
  record. Making a defect record-scoped would mean catching it in `run()`, which
  is the same fail-open shape one level up.

## 5. TWO SMALLER FINDINGS, NOT FIXED HERE

1. **`tests/test_hold_reasons.py:273` carries a THIRD invented shape**,
   `"research": {"evidence": ["fact one"]}` on a record fixture. It is
   unreachable — the test patches `generate.plan` and `generate.diagnose`, so no
   reader ever sees it — and the module passes 36/36. Left alone as out of
   scope; it should become a canonical list when somebody is in that file.
2. **The shape check runs BEFORE the offer gate**, because
   `_generate_via_campaign` builds the account dict before calling
   `generate_campaign.generate()`. So a record with an unreadable research shape
   AND an unapproved offer now reports the shape refusal rather than the offer
   refusal. Both fail closed and nothing proceeds under either, and no
   production record carries an unreadable shape, so this is a message-ordering
   note rather than a safety one.

## 6. PROOF

`tests/test_the_research_pack_has_one_shape.py`, 18 tests, through the
production caller:

- the canonical LIST produces copy, `stored_pairs` is non-empty, and the copy
  reaches `rec["cadence"]`;
- **CONSUMER:** the pack's fact appears in the ICP and extract prompts, and the
  extracted fact carries the row's own `source_url`, resolved from our own list
  — `None` when no pack arrives, so no provenance is invented;
- the projection equals `research.for_prompt`'s, row for row (one truth), and an
  `unusable` row is not shown to the model;
- absence and `[]` both produce copy and invent nothing;
- an unreadable shape refuses by name with nothing written, a gate that raises
  `AttributeError` refuses by name, and — the controls in the other direction —
  a writer hold and a `copy_refused` still come back ON the plan;
- each of `claims`, `dossier`, `eligibility` and `generate` is asserted on its
  ANSWER against the canonical row, each with a control that removes the row and
  shows the answer change. Existence is not function.

`tests/test_only_the_selected_offer_is_validated.py`'s `_rec()` fixture moved to
the canonical shape with the reader: it was written against the dict read, and
its own `_proceeded` docstring names this defect as the reason it asserts
indirectly. 14/14, unchanged in count and in what each test asserts.

**MUTATION.** The dict read was reintroduced byte-exactly (`tmp/mutate.py`,
binary read/write, CRLF preserved), the file verified CHANGED by md5
(`828818fe…` → `5f1a2421…`), and the acceptance-1 tests failed with
`AttributeError: 'list' object has no attribute 'get'` at the reintroduced line
— the intended reason, with no other guard firing first. The protected offer
proof also went 14/14 → 3 errors under the mutation, which is what makes its
fixture change load-bearing rather than cosmetic. Restored from the saved
original bytes and verified md5-identical (`828818fe…`) and `git status` clean.

**Provider writes 0. No model called — `tests/base.CampaignModel` throughout.
The production store is untouched and verified md5-identical before and after
(`3c487bd73cf6b6c72b1a5bad8d7d1dcf`, 1,582 records).**
