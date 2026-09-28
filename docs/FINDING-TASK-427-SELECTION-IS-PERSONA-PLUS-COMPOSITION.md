# FINDING — TASK-427: where offer selection actually happens, and the two
# things TASK-425 needs to know about it

Written because a finding that exists only in terminal output does not exist.
Measured on `f6979300` and on the branch head, through `generate_campaign.generate`
and `src/generate.py`, never by reading the YAML a second way.

## 1. SELECTION HAPPENED AFTER THE CHECK, AND IT SILENTLY DROPPED THE UNAPPROVED

There was no offer-selection step in `generate_campaign` at all. The only code
that narrows the offer library to a prospect is
**`campaignstrategy._offers_for_segment(segment_key, persona)`**, reached from
`generate()` **step 3** — two steps AFTER `_check_offers` at step 1. It filters
by segment (`all` matches everything) and persona (an offer declaring no persona
matches every persona), and it also `continue`s past any offer whose
`approval_status` is not `approved`.

So the estate had the two halves the wrong way round:

    step 1  _check_offers        the WHOLE library, refuses on the first pending
    step 3  _offers_for_segment  the prospect's offers, silently DROPS pending

That second half is the more interesting defect of the two and it is why the
check could not simply be moved: had `_check_offers` been handed
`_offers_for_segment`'s output, it would have been handed a set from which every
unapproved record had already been removed, and the gate would have become
vacuous — green forever, testing nothing. The selection had to be computed
WITHOUT the approval filter so that an unapproved selected offer still exists to
be refused by name.

`generate_campaign._select_offers` now does that, and
`test_the_validated_selection_is_the_set_the_strategy_plans_around` pins its
result to `_offers_for_segment`'s on the real library, so the set the gate
validates cannot drift from the set the strategy plans around.

**`offers.for_campaign(campaign_id, require_approved=True)` has NO production
caller** (only `src/offers.py`'s own docstring and tests), so `_check_offers` was
the single offer-approval gate on the generation path. There is no second one to
keep in step.

## 2. COMPOSED OFFERS: THE CONSTITUENTS ARE PROVENANCE

`offers.load()` returns 8 records: 2 approved and 6 pending. The 6 pending are
capability offers, and 5 of them are named in a `composes` list —
`OFFER-A-ECONOMIC-BUYER` composes `OFFER-PR-001` and `OFFER-BU-001`;
`OFFER-B-OPERATIONS` composes `OFFER-PM-001`, `OFFER-TT-001` and `OFFER-RP-001`.

**Approving a composed offer does NOT approve what it composes.** What the
operator reviewed is the composed record; its constituents record where its
clauses came from. The implemented reading is therefore that a constituent is
provenance and never separately selectable — the conservative one of the two,
because the alternative has this code treating six unreviewed offers as approved.

**`OFFER-BI-001` is the case a constituent-only rule gets wrong, and it is worth
knowing about.** It is a pending capability offer (billing, `economic_buyer`)
that NO composed offer composes. Under constituent-exclusion alone it stays in
the economic buyer's selection and refuses every economic-buyer run — which would
have blocked `TASK-425` acceptance criterion 1C while looking like a correct
fail-closed answer. Selection therefore also applies the distinction the offers
file makes in its own words ("the two composed offers … these COMPOSE the
capability offers above"): where a persona's scope contains a composed offer,
that is the shippable unit and the bare capability offers beside it are building
blocks. A library with no composed offers keeps every non-constituent offer in
scope, so the step narrows and never widens.

## 3. WHAT TASK-425 NEEDS TO KNOW ABOUT THE PERSONA

**"Operations" is the persona `champion`.** The operator's criterion 1C says
"persona economic buyer → operations — Offer A → B". There is no persona string
`operations` anywhere in the library or the code: the two-persona vocabulary is
`champion` and `economic_buyer`, and `src/demo.py:120` records the translation —
`PERSONA_WORDS = {"champion": "operations leads", "economic_buyer": "founders"}`.
Measured, on the real library and with nothing mocked:

    persona=champion       -> OFFER-B-OPERATIONS      (approved)
    persona=economic_buyer -> OFFER-A-ECONOMIC-BUYER  (approved)
    persona=procurement    -> NotApproved: no offer is selected

So criterion 1C is served by setting `rec["persona"]` to `economic_buyer` and to
`champion`. **A run that sets it to the literal string `operations` REFUSES**, by
design and loudly — that is the fail-closed answer for a persona the library has
no offer for, not a bug to work around.

## 4. THE NEXT BLOCKER, VISIBLE FOR THE FIRST TIME BECAUSE THE GATE OPENED

**`rec["research"]` has two incompatible shapes and the TASK-400 path cannot
produce copy under either.** Pre-existing, not created by TASK-427, and
previously unreachable: the offer gate refused before the pipeline could touch
either reader. Same pattern as the two blockers `TASK-426` made visible.

The canonical shape is a **LIST of evidence entries**. That is what
`companies.py:326`, `demo.py:182` and `benchmark.py:53` WRITE, and what
`claims.py:519`, `dossier.py:126`, `eligibility.py:802` and `generate.py:115`
and `:232` READ. But the TASK-400 production caller,
`generate.py::_generate_via_campaign`, reads
`(rec.get("research") or {}).get("sources") or []` — a **DICT with a `sources`
key**. Measured, each reader against each shape:

    research = LIST (canonical)   _generate_via_campaign -> AttributeError:
                                    'list' object has no attribute 'get'
                                  claims.support_text    -> ok
    research = DICT with sources  _generate_via_campaign -> ok
                                  claims.support_text    -> AttributeError:
                                    'str' object has no attribute 'get'
                                    (iterating a dict yields its KEYS)
    research = [] or absent       both ok, and the account research pack never
                                  reaches the pipeline, so the copy has no facts

`claims.support_text` is reached from `_campaign_validator`, the `validate`
callback `generate_campaign` retries on, and that call sits inside
`_process_contact`'s broad `except Exception`. So the crash does not surface as a
crash: **every contact comes back `hold_kind="error"`, `held="AttributeError:
'str' object has no attribute 'get'"`, `stored_pairs=0`** — a run that looks like
it completed and stored nothing. Measured through
`generate._generate_via_campaign` with the real `productive` config and the real
offer library, for both personas.

**So there is no shape of `rec["research"]` for which the new path produces
copy**, and `TASK-425` cannot pass its causal matrix until this is answered: a
run whose facts never arrive cannot show that changing a fact changes the angle.

**NOT FIXED HERE, deliberately.** `src/claims.py` is outside TASK-427's file
scope, and the choice between "make the caller read the canonical list" and
"change what `research` holds" is a canonical-state decision with six other
readers, not a call-site tweak. It needs its own task. The broad
`except Exception` in `_process_contact` that turned a crash into a per-contact
hold is a second, separate thing worth looking at: it is the "no silent fallbacks
on a safety path" rule, and it is why this went unnoticed for one full run.

## 5. THE DRY-RUN STAMP STILL SAYS `OFFERS PENDING`

`DRY_RUN_STAMP` is the
literal `"DRY-RUN / OFFERS PENDING"` and a dry run's artifact still carries it,
correctly, because `live=False` alone stamps. The wording is now misleading — the
selected offer is approved and the stamp is about the dry run, not about offers.
It was left alone on purpose: the string is the contract between
`generate_campaign.dry_run_stamp_of` and four provider refusal sites, and
renaming it is a separate change with its own blast radius. Cosmetic debt, noted
so nobody reads a stamped `TASK-425` artifact as evidence that an offer is
pending.
