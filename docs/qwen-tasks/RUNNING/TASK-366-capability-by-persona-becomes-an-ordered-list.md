PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-366 — capability_by_persona becomes an ordered list, primary first

**Operator decision, 2026-09-26.** The exact values, and they are not yours to
adjust:

    capability_by_persona:
      economic_buyer: [profitability, budgeting, billing]
      champion:       [resource_planning, project_management, time_tracking]

**First entry is the primary angle.** `capability_by_persona` is now **only the
angle order within an offer** — the new `offers:` block (TASK-367) owns
persona-to-offer. **No other mapping anywhere.**

## CONFIG AND CODE LAND TOGETHER, IN ONE COMMIT

The moment the value becomes a list, `src/cadence.py:775` breaks:

    key = ((product.get(CAPABILITY_BY_PERSONA_KEY) or {}).get(persona) ...)
    sentence = str((product.get("capabilities") or {}).get(key) or "").strip()

`capabilities.get(['profitability', ...])` does not resolve — a list is not a key.
That is on the **copy path**, so a config-only change silently empties the
`capability` template variable for every contact. **Do not split this into two
commits.**

## Every reader and caller — verified on master `79fd87e8`

**Readers of the mapping:**

    config/clients/productive.yaml:359          the data
    src/cadence.py:743                          CAPABILITY_BY_PERSONA_KEY
    src/cadence.py:775                          the single-key lookup - BREAKS
    src/secondbrain.py:174-178                  iterates persona, capability and
                                                formats a fact string. A list
                                                renders as "['a', 'b']" - wrong,
                                                not a crash. Fix it too.
    tests/test_the_cadence_lands_in_every_file.py:355,356,413,416

**Callers of `product_words`** (its return contract must not change shape):

    src/cadence.py:823          values.update(product_words(contact, config))
    scripts/stage_s7_copy.py:357
    tests/test_the_cadence_lands_in_every_file.py:362,377,392

Ignore `.claude/worktrees/*` — separate checkouts of this repo, they pick the
change up from master.

## The design constraint that keeps the copy path working

`product_words` currently returns `capability` as **one sentence**. Three callers
depend on that.

**Keep `capability` as the PRIMARY capability's sentence** — list entry 0 resolved
through `product.capabilities`. Then expose the full ordered list under a **new**
key so nothing existing changes meaning. Name it and say why.

**Accept a bare string as well as a list.** Other clients' configs may still hold a
single value, and `clients.load` serves every client. A string is treated as a
one-item list. Do not migrate other client files in this task.

**A persona absent from the mapping must behave exactly as it does today** — the
existing test at line 392 passes `{"persona": "nobody"}` and expects
`product_words` to omit what it cannot resolve. Do not turn that into a crash or an
empty string.

## Acceptance — RUN each, paste real output

1. The list loads and the primary resolves:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import clients, cadence;\\
    c=clients.load('productive');\\
    m=c['product']['capability_by_persona'];\\
    assert m['economic_buyer'][0]=='profitability', m;\\
    assert m['champion'][0]=='resource_planning', m;\\
    w=cadence.product_words({'persona':'economic_buyer'}, c);\\
    caps=c['product']['capabilities'];\\
    assert w['capability']==caps['profitability'], w;\\
    print('primary resolves:', w['capability'])"

2. **The champion primary is resource_planning, not budgeting** — the stale mapping
   is gone. Assert `product_words({'persona':'champion'})['capability']` equals the
   `resource_planning` sentence.

3. **The full ordered list is available**, in the operator's order, for both
   personas.

4. **A bare string still works.** Fixture config with `economic_buyer: profitability`
   resolves identically.

5. **An unknown persona behaves as before:**

    py -3 -m unittest tests.test_the_cadence_lands_in_every_file -v

   all existing assertions pass, including line 392's `"nobody"` case.

6. **`secondbrain` emits one fact per capability, not a stringified list.** Assert
   no fact text contains `[` or `'`.

7. **The guard is seen to fail:** revert `cadence.py` to the single-key lookup,
   confirm a test FAILS naming the empty capability, restore, confirm green.
   Confirm the revert landed. Paste both runs.

8. **`scripts/stage_s7_copy.py` still works** — it calls `product_words` and
   `values.update`s the result. Exercise it or prove by inspection that the return
   contract is unchanged, and say which you did.

9. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). Not a count.

## What this task may NOT do

- **Do not change the operator's values or their order.**
- Do not create a second mapping anywhere. This is the only one.
- Do not change what `product_words` returns under the `capability` key.
- Do not migrate other clients' config files.
- Do not touch `approval_status` on any offer.
- Nothing sent, nothing activated.
