PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-908 — the approval hash must cover the sender, or it does not bind the copy

**Filed by Claude 2026-09-28 as the smallest remediation for a gap a hard gate
found.** Not a new feature. It is the **last** thing between the operator and
the one-account review artifact, because that artifact must contain an
**"approval hash for the exact provider-bound content"** and today's hash does
not cover all of it.

## The defect, proven at runtime

`sequenceplan.approval_hash` hashes exactly this:

    client, account, strategy_id,
    and per contact: email, sequences, subjects

Its own docstring promises:

> *"Two plans with the same approval hash produce the same prospect-facing
> copy."*

**Measured by Claude, both directions:**

    change the P.S.     -> hash CHANGES     81eee1ca... -> 9dcf3e93...
    change the SENDER   -> hash IDENTICAL   81eee1ca... -> 81eee1ca...

The P.S. is covered **transitively**, because `generate_campaign` puts
`ps_em1`/`ps_em3` inside `sequences` and the whole `sequences` dict is hashed.
**The sender is not covered at all.**

## Why it only became a defect today

**Before TASK-906 this was harmless.** No signature was composed into
prospect-facing copy, so the sender did not change a single rendered byte.

TASK-906 merged (`49c2ec98`) and now `sendersignature.compose(sender)` puts
**two prospect-facing lines — the mailbox owner's full name, then
`Productive` — into every body and into the EmailBison projection.**

So today: **two plans with the same approval hash, sent from different
mailboxes, produce different prospect-facing copy.** The docstring's guarantee
is false, and the execution guard that uses this hash to "detect drift between
what was approved and what the provider payload carries" cannot see a signature
swap.

**This is TASK-560's fingerprint defect one level up** — there, approved copy
and the same copy with a different P.S. hashed identically. Same shape, same
fix: put the new prospect-facing content into the digest that binds it.

## What to build — the SMALLEST change

**Include the sender identity in `approval_hash`'s `material`.** One dict key,
in one function, in `src/sequenceplan.py`.

Hash **the sender identity the signature is derived FROM** (whatever the plan
carries to identify the mailbox — read `sendersignature.compose` to see exactly
what it consumes), not a re-rendered signature string. Hashing the identity
covers the signature and stays stable if the signature's formatting changes.

**Do not** restructure the plan, add a module, change `approval.fingerprint`
(TASK-560 owns it and it is correct), touch the rendering path (TASK-906 owns
it), or "improve" the hash while you are in there. **One key.**

**Say in your result block whether existing stored approval hashes change.**
They will, for any plan that carries a sender — that is the point — but it must
be stated, not discovered. Nothing is sending and every campaign is paused, so
no live approval depends on the old value.

## Acceptance

1. **The hash CHANGES when the sender changes**, all else equal. This is the
   defect; it is the first assertion.
2. **The hash is STABLE when nothing changes** — same plan twice, same hash.
   A digest that moves on its own is worse than one that misses a field.
3. **The P.S. coverage that already works must keep working:** change the P.S.,
   the hash changes.
4. **NEGATIVE CONTROL:** a plan with **no** sender must still hash, and must
   not raise. Absence is not an error, and `approval_hash` must not start
   refusing plans it used to accept. Two senderless plans that are otherwise
   identical must hash identically.
5. **The runtime probe still passes**, unchanged: `derive_bison_payload >= 1`,
   `approval_hash >= 1`, and **`bisonfactory._approved_copy == 0`**.
6. **MUTATION:** remove your key from `material`; acceptance 1 must go red for
   that reason, with no other guard firing first. Restore and verify
   **byte-identical by sha256**. Files are **CRLF** — an `\n`-anchored regex
   matches zero times and the mutation becomes a silent no-op.

### ACCEPTANCE COMMANDS — run these exactly and paste the real output

**These must stay in THIS section.** GLM's extractor enters at the first
`## Acceptance` heading and stops at the next `## `, so commands in a later
section are invisible — that cost four verdicts on TASK-560/907/906. It only
takes lines beginning `py -3`, `python`, `grep` or `scripts/`.

    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task560_ps_reaches_the_person
    py -3 -m unittest tests.test_task907_ps_producer_hop
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task905_projection_from_plan
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_approve
    py -3 -m unittest tests.test_generate

All eight must be green; `tests.test_render_preview` must be **29 tests, 0
failures**.

**The sender assertion, which is the whole task** — exits 0 only when the hash
moves on a sender change and holds still otherwise:

    py -3 -c "import sys, copy; from src import sequenceplan as S; p={'client':'c','account':'a','strategy':{'strategy_id':'s'},'contacts':[{'email':'x@y.z','sequences':{'em1':'b','ps_em1':'P.S. one'},'subjects':{'em1':'s1'}}]}; a=copy.deepcopy(p); a['contacts'][0]['sender']='anna@productive.io'; b=copy.deepcopy(p); b['contacts'][0]['sender']='other@productive.io'; ha,hb=S.approval_hash(a),S.approval_hash(b); n=copy.deepcopy(p); h1,h2=S.approval_hash(n),S.approval_hash(copy.deepcopy(n)); sys.exit('sender not covered: %s == %s'%(ha,hb)) if ha==hb else (sys.exit('unstable: %s != %s'%(h1,h2)) if h1!=h2 else print('OK: sender covered and hash stable'))"

**Read the exit code OFF THE PROCESS, never through a pipe** — `| tail` masks
it and reports 0 for a failing command.

**The runtime probe, verified by Claude on master — use it verbatim.** It needs
`--state`, a COPY of production `work/`, and `--mode project` also needs
`--campaign`. Your worktree has no `work/` of its own, so copy it first:

    py -3 -c "import shutil,os; src=r'C:/Users/Zvonimir/Desktop/resonate-group-automation/work'; dst=os.path.join(os.environ.get('TEMP','.'),'probe-work-908'); shutil.rmtree(dst,ignore_errors=True); shutil.copytree(src,dst); print(dst)"
    py -3 scripts/runtime_approval_hash_probe.py --state "%TEMP%/probe-work-908" --mode project --campaign productive-email-batch1-kresimir --construct-from productive-email-batch1-kresimir --construct-limit 1

**`bisonfactory._approved_copy` must read 0.** Expect the CLI inside the probe
to exit 1 with `FactoryRefused` on `step_objectives` — that is a known data-level
gate refusal on the constructed lead, it happens **after** the projection and
hash are entered, and it is **not yours**.

## Files
`src/sequenceplan.py` only, plus your own tests. **Do NOT touch**
`src/render.py`, `src/bisonfactory.py`, `src/trailingcontent.py`,
`src/sendersignature.py` (TASK-906), `src/approval.py` (TASK-560) or
`src/generate.py` (TASK-907).

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`.** Verify after checkout that
  HEAD equals `origin/master` **before** doing any work — six of twelve
  dispatches once landed on months-old history and built for 30-50 minutes on
  the wrong codebase.
- **NEVER WIDEN A GATE TO MAKE SOMETHING PASS.** Fix what a gate CONSULTS,
  never what it PERMITS.
- **A test count is never a PASS.** Name the production path, the negative
  control, and the killed mutation.
- **Do not report a PREDICTED result.** Run it and measure it. A claim
  contradicted by one command is worse than no claim.
- **PROVIDER WRITES = 0.** `sending.live` is false, the freeze stands, nothing
  is sent, enrolled or attached.
- Production `work/` is **READ-ONLY** — copy it, never point at it. Verify
  `work/queue.jsonl` and `work/campaigns.jsonl` unchanged **by sha256 from a
  fresh process**; mtime is the wrong instrument.
- **Write suite logs OUTSIDE the repository.** A suite with no `Ran N tests`
  line is an **absent measurement, not a failure** — sweep `%TEMP%` and re-run.
- Baseline `docs/state/SUITE-BASELINE-2026-09-26.txt` is compared **AS SETS,
  NEVER COUNTS** and is **known stale** (TASK-549). In particular
  `test_set_regeneration...test_successful_regeneration_replaces_all_notes`
  fails on master at `5 != 6` **with no branch at all** — not yours, do not fix
  it, do not report it as yours.
- Commit and push to your own branch and **verify the remote with
  `git rev-parse`**. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** (VERIFIED / UNPROVEN /
  UNKNOWN) and your exact branch head SHA. GLM verifies against that SHA.

**The operator is waiting on a one-account review artifact that must contain an
approval hash over the exact provider-bound content. Until this lands, that
field would be a hash that does not cover the signature the person actually
sees.**
