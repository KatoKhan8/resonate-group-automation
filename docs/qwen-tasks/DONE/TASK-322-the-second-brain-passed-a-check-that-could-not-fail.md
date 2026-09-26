PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-322 — the Second Brain passed a check that could not fail

**GLM adversarial review, `docs/glm-reviews/TASK-317-secondbrain.md`. Every
finding below was then confirmed by running against the merged code on
master. This is a fix task, not a discussion.**

`src/secondbrain.py` is on master at `4ff299a9`. It is inert rather than
dangerous - nothing imports it - so there is no rollback. Fix it forward.

## What is wrong

**1. The gate has three bypasses.**

    all_sections(client)        public, takes no task, returns everything.
                                Its only guard is a docstring saying
                                "Not for prompts."
    TASK_SECTIONS               a mutable module dict. Assign to it and
                                for_task returns the whole brain.
    **scope                     accepted and silently discarded, so a
                                caller's declared narrowing is unenforced.

Confirmed: `all_sections` present, `TASK_SECTIONS` is a plain dict, `scope`
is never read.

**2. `for_task` HAS ZERO CALLERS.** `grep -rl secondbrain src/ --include=*.py`
returns only the module itself. This is the pattern the audit named and this
module was built to end: a retrieval layer that computes correctly and feeds
nothing.

**3. THE PROVENANCE IS FABRICATED.** Every `source` is the hardcoded literal
`"config/clients/productive.yaml ..."`, at nineteen sites, **regardless of the
`client` argument**. `for_task("cold_email_writing", "acme")` cites
Productive's file as the source of Acme's facts. That is worse than a missing
source, because a reader trusts it.

**4. THREE TESTS THAT CANNOT FAIL.**

    verified=True and date=TODAY are stamped unconditionally at retrieval,
    so any assertion about verification or freshness passes by construction.

    _competitors, _offers and _learning return [] always, so
    `assert result["offers"] == []` is green by construction.

    The "Missing Information" block is hardcoded prose, not derived from the
    data. It will still say "no approved campaign offers yet (TASK-318)"
    after TASK-318 ships.

**5. `index_html` does not write the file its docstring promises.** It returns
a string; nothing opens a file. `import os` is unused - the corpse of the
deleted write.

## The acceptance check that let this through was mine, and it was the same defect

    assert all(f.get('source') and f.get('date') for s in r.values() for f in s)

Every fact is stamped with a source and a date unconditionally, so that
assertion could never fail for any input. **It tested that the stamping code
ran, not that the provenance was true.** Do not re-use it.

## Fix

- `all_sections` becomes `_all_sections`, or takes an explicit
  `reason=` argument and is refused without one.
- `TASK_SECTIONS` becomes immutable: a `MappingProxyType` or frozen tuples.
- `**scope` is either honoured or removed. An accepted-and-discarded argument
  is a lie in the signature.
- **`source` is derived from the file actually read**, per client, per fact.
  If a fact came from `config/clients/acme.yaml`, that is its source.
- `verified` reflects something. If nothing verifies a fact, the value is
  `unverified`, not `True`.
- `index_html` writes the file, or its docstring stops saying it does and the
  caller writes it. Remove the unused `import os` either way.
- **Give `for_task` a caller.** The Second Brain is consumed by the stage that
  needs it or it is not done. `copystages`/`copypath` is the consumer.

## Acceptance, and it must be able to fail

    py -3 -c "import sys;sys.path.insert(0,'.');from src import secondbrain as b;\
    r=b.for_task('cold_email_writing','productive');\
    srcs={f['source'] for s in r.values() for f in s};\
    assert all('productive' in s for s in srcs), srcs;\
    r2=b.for_task('cold_email_writing','demo');\
    s2={f['source'] for s in r2.values() for f in s};\
    assert not any('productive' in s for s in s2), 'cites the wrong client: %s' % s2"

plus `grep -rl secondbrain src/ --include=*.py` naming a consumer that is not
the module itself, and a test that FAILS when `TASK_SECTIONS` is mutated.

**Prove each new test fails.** Break the thing it guards, show the red, restore.

Close with the section 11 report, pushed, remote SHA verified.
