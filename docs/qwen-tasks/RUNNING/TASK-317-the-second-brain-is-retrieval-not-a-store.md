PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-317 — the Client Second Brain, as retrieval over what exists

Phase 1, task 1. **Read `docs/PHASE1-PLAN-2026-09-26.md` first**, then
`docs/AUDIT-2026-09-26.md` section 3, which you wrote.

## THE ONE RULE THAT DECIDES WHETHER THIS IS RIGHT OR WRONG

**`config/clients/productive.yaml` is canonical and stays canonical.** Your
own audit says it: *"Recommending a new store for facts already in
productive.yaml would be wrong."* `clients.load()` is what `generate.py`,
`bisonfactory.py`, `heyreachfactory.py`, `copyprompts.py` and `copystages.py`
all read.

**This task builds a RETRIEVAL LAYER, not a database.** If you find yourself
writing client facts to a new file, stop: that is the failure this task is
shaped to avoid.

## What already exists and must be reused

    config/clients/productive.yaml   1,008 lines, the client knowledge
    src/clients.py                   the loader
    src/contextpack.py               590 lines. Assembles segments, priority,
                                     signals, strategy, outreachclaims - and
                                     is read ONLY by src/web/api.py
    src/playbooks.py                 the existing playbook architecture

**`contextpack.py` is already most of the Second Brain and nothing in the
generation path reads it.** Making it a workflow input is the substance of
this task. Extend it; do not replace it.

## Build

`src/secondbrain.py`:

    for_task(task, client, **scope) -> {section: [fact, ...]}

Sections map to spec section 3: profile, market, customers, messaging, offers,
learning. **Competitor intelligence is reported MISSING**, never invented.

**Return only the sections the task needs.** `cold_email_writing` does not need
market structure. The spec forbids passing the whole brain into a prompt, and
the cost shape depends on it: `COHORT_SYSTEM` is 936 cached tokens and the
per-lead turn is 61. A retrieval layer that returns everything undoes that and
you would see it in the bill.

**Every fact carries `source` and `date`, and says whether it is verified or
inferred.** A fact that cannot answer those three questions is not returned.

## The index page

`work/review/secondbrain-<client>.html`, the ten sections from the spec, and
**MISSING INFORMATION AND RESEARCH PRIORITIES as a first-class section** - that
is where competitor intelligence, case studies and offers live until the client
supplies them. An index that hides its gaps is worse than no index.

## Acceptance, in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src import secondbrain as b;\
    r=b.for_task('cold_email_writing','productive');\
    assert 'market' not in r, 'returned a section this task does not need';\
    assert all(f.get('source') and f.get('date') for s in r.values() for f in s);\
    print(sorted(r))"

plus tests that two different tasks receive different sections, and that
**`secondbrain` writes no client fact anywhere** - assert it opens no file for
writing under `config/`.

## What would make this a FALSE PASS

- A new YAML or JSONL holding client facts that productive.yaml already has.
- `for_task` returning everything regardless of the task.
- A fact with no source or no date.
- An index page that omits the missing-information section.
- Leaving `contextpack.py` unread by the generation path, which was the
  finding that prompted this.

## Close it properly

Section 11 completion report, committed and **pushed**, with the remote SHA and
the GitHub URL verified on the remote. A local commit does not close a task.
