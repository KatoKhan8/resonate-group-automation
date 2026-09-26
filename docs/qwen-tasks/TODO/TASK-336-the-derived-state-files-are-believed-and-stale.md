PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-336 - the derived state files are believed, and they are stale

**SEVERITY: MEDIUM.** Buggie finding M6, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

`CLAUDE.md`'s own rule: *"a ledger somebody has to remember to update is a ledger
that drifts - and a drifted ledger is worse than none, because it is believed."*

Measured 2026-09-26 against master:

    docs/state/TASK-REGISTRY.json      master_head da6860fb (HEAD is later); records
                                       TASK-317 as QUEUED/TODO while the file is
                                       physically in DONE/
    docs/state/LEDGER.json             generated 2026-09-20
    docs/state/QUEUE-MANIFEST.json     generated 2026-09-20
    docs/state/READY-RESERVOIR.json    generated 2026-09-18
    docs/state/SENDER-CAPACITY.json    generated 2026-09-21
    docs/state/PROVIDER-CAMPAIGNS.json generated 2026-09-23

`docs/state/PROBLEM-REGISTER.md` is also missing both of the newest confirmed
defects: the Resonate-copy incident (64 emails, a different agency's pitch) and
the Second Brain's fabricated provenance.

## What to do

1. Regenerate every derived file with its own generator. They are DERIVED and
   **never hand-edited** - if a generator does not exist for one, say so rather
   than writing the file by hand.

       py -3 scripts/durable_state.py        -> LEDGER.json, QUEUE-MANIFEST.json
       py -3 scripts/task_registry.py        -> TASK-REGISTRY.json

   `scripts/durable_state.py` **exits non-zero when a branch holds unpushed work
   or a worktree is dirty. That exit code is a durability alarm, not a crash** -
   report what it names, do not suppress it.

2. **`PROVIDER-CAMPAIGNS.json` is written by asking the providers**
   (`scripts/provider_truth.py`). That is a READ, not a write, and it is
   permitted - but confirm it makes no mutating call before running it. If you
   cannot confirm that from the code, DO NOT RUN IT: report it as needing
   authorisation instead. The production freeze forbids provider changes.

3. Add the two missing defects to `PROBLEM-REGISTER.md`, in the file's existing
   row format, each with the commit or document that confirms it. Follow the
   register's own two rules: code written is not FIXED, and FIXED is not
   PRODUCTION_VERIFIED. Both of these are CONFIRMED, not fixed.

4. **Report a staleness guard.** Every one of these drifted silently. Under
   FINDINGS, propose (do not build) the smallest check that would have caught it -
   e.g. a test asserting `master_head` in each derived file matches
   `git rev-parse master`. Whether to add it is the operator's call.

## Acceptance

    py -3 -c "import json,glob,subprocess;\
    head=subprocess.check_output(['git','rev-parse','master']).decode().strip()[:8];\
    bad=[];\
    [bad.append((f,d.get('master_head'))) for f in glob.glob('docs/state/*.json')\
      for d in [json.load(open(f,encoding='utf-8'))] if isinstance(d,dict)\
      and d.get('master_head') and not head.startswith(str(d['master_head'])[:8])];\
    print('stale:',bad) or (bad and exit(1))"

plus: TASK-REGISTRY.json must no longer report TASK-317 as TODO, and
PROBLEM-REGISTER.md must contain both new entries.

## What this task may NOT do

- Do not hand-edit a derived file. Regenerate it or report the missing generator.
- Do not run anything that mutates provider state. Reads only, and only if you
  can prove from the code that the call is a read.
- Do not suppress `durable_state.py`'s non-zero exit.
- Nothing sent, nothing activated.
