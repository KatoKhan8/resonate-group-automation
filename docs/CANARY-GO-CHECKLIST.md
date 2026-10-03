# CANARY GO / NO-GO CHECKLIST

**Every item is BINARY and carries the command that decides it.** No item is
satisfied by a document, a handoff sentence or anybody's recollection — only by
the command printing what the item says it must print. An item whose command
cannot be run is **NO-GO**, not "probably fine": an unreadable authority means
UNKNOWN, and UNKNOWN is never a pass.

Written 2026-10-03 on the operator's order. Run it top to bottom immediately
before the send, not once and then trusted — several of these change
underneath you between one hour and the next.

**THERE ARE TWO GO DECISIONS AND THEY ARE SEPARATE.** Operator, 2026-10-03:
**EMAIL GO** and **LINKEDIN GO** are two distinct approvals, each given by the
operator **in writing**, each naming **the exact recipient, the exact sender
and the exact campaign**. Neither implies the other. Passing this checklist
does not authorise a send; it only makes one askable.

**And the standing limit on everything below:** no provider write and no Slack
post outside the OUTPUT channel without the operator's GO.

Run from the MAIN checkout, `C:\Users\Zvonimir\Desktop\resonate-group-automation`,
with `PYTHONUTF8=1` set — without it the console is cp1250 and a provider reply
carrying Czech or Polish text raises `UnicodeEncodeError` in the middle of a
report.

---

## A. The code that is about to run

### A1. Master is what you think it is, and the remote agrees

    git fetch origin && git rev-parse master origin/master

**GO:** two identical SHAs. **NO-GO:** they differ — something is unpushed, or
master moved under you.

### A2. The canary-critical branches are IN master

Measured, never recalled. The canary cannot send safely without the
internal-campaign protection, the copy gate, the token budget and the
eligibility authority.

    for b in task-guard-regressions-rebased task-word-contract-enforced task-942-token-budget task-one-os-authority ; do git merge-base --is-ancestor $b master && echo "MERGED  $b" || echo "MISSING $b" ; done

**GO:** four `MERGED`. **NO-GO:** any `MISSING`.
*State at 2026-10-03: `task-one-os-authority` is NOT merged.*

### A3. The internal-campaign classifier exists and refuses by default

`resonate_internal` appeared in ZERO files under `src/` until 2026-10-03, so an
internal campaign was never refused FOR BEING THEIRS.

    py -3 -c "from src import providerwrites as p; print(hasattr(p,'classify_campaign')); print([p.classify_campaign('email', c) for c in (274,327,328,352,481)]); print([p.classify_campaign('email', j) for j in (None,'','abc',0,-1,[])])"

**GO:** `True`; four `resonate_internal` then one `resonate_os`; then six
`unknown`. **NO-GO:** anything else — especially any junk value returning
something other than `unknown`.

### A4. The tree is clean and the suite verdict describes THIS tree

    git status --short
    py -3 -c "import os,datetime; print(datetime.datetime.fromtimestamp(os.path.getmtime(r'scripts/suite_verdict.txt')))"

**GO:** no output from the first; the second is LATER than the start of the run
you believe it describes. **NO-GO:** a dirty tree, or a verdict older than the
run. A stale `suite_verdict.txt` was read as a fresh one on 2026-10-03 and it
described a different tree.

---

## B. Nothing can send by accident

### B1. The kill switch refuses, in code

    py -3 -c "from src import killswitch as k; print(k.workspace_state('productive'))"

**GO:** the state the operator intends, and no other. **NO-GO:** anything
unexpected. The recorded limit stands: **the killswitch refuses to START an
action and cannot END one already running.** Turning `sending.live` off was
never a pause.

### B2. Provider writes from us are still zero, and the readback says so

    py -3 scripts/provider_truth.py --verify 2>&1 | tail -20

**GO:** the readback matches the ledger. **NO-GO:** any disagreement. A local
dry run, a generated sequence, an adapter test or a "write passed" line in a
handoff is **not** evidence a campaign exists — only a provider readback
against a real campaign id is.

### B3. The three paused legacy campaigns are still paused

**CORRECTED 2026-10-03 by running it.** The command here read `d['campaigns']`
and `c['id']`. There is no top-level `campaigns` key — the list is at
`d['emailbison']['campaigns']` — and the id field is `bison_campaign_id`, not
`id`. As written it raised `KeyError: 'campaigns'`, which is a NO-GO by this
checklist's own rule and was not one anybody intended.

    py -3 -c "import json,datetime; d=json.load(open(r'docs/state/PROVIDER-CAMPAIGNS.json',encoding='utf-8')); print(d.get('generated_at'),'| today',datetime.date.today().isoformat()); print({c['bison_campaign_id']:c.get('status') for c in d['emailbison']['campaigns'] if str(c['bison_campaign_id']) in ('487','489','493')})"

Note the ordering trap: **B2 REWRITES this file.** Run B2 first and this
item's `generated_at` is today by construction; run it second and you are
reading whatever was there before.

**GO:** all three `paused`, and `generated_at` is from TODAY. **NO-GO:** any
other status, or a stale file — this file was two days stale once and a handoff
reported 0 sends where there had been 6.

---

## C. The operator's named condition: a reply reaches a human

### C1. THE DELIVER LOOP IS RUNNING UNDER A SUPERVISOR

`notify.plan` writes a row at `status=PLANNED`. **`notify.deliver` is the only
thing that reaches Slack.** Measured 2026-10-03 21:30: four production callers
exist — `scripts/notify_deliver_loop.py:72`, `src/digestwatch.py:250`,
`src/orchestrator.py:862`, `scripts/slack_replay_today.py:133` — and **ZERO
python processes were running on the machine**, so every PLANNED row sat
undrained. The code being right is not the loop being up.

**AMENDED 2026-10-03 BY THE OPERATOR. THE HEARTBEAT IS THE TEST.** Not that a
scheduled task exists, and not merely that a process is listed. A process
census can see a hung interpreter and call it up; the one thing a hung loop
cannot do is keep rewriting a file. The loop runs as a **detached user
process under a restart loop** — NOT a scheduled task — and refreshes
`C:\Users\Zvonimir\Desktop\resonate-ops\runtime\deliver.heartbeat`.

**THE TEST.** The heartbeat is younger than five minutes:

    py -3 -c "import os,datetime; p=r'C:\Users\Zvonimir\Desktop\resonate-ops\runtime\deliver.heartbeat'; age=datetime.datetime.now().timestamp()-os.path.getmtime(p); print('age_seconds %.1f' % age); print('GO' if age < 300 else 'NO-GO')"

**GO:** `age_seconds` under 300. **NO-GO:** over 300, or the file is missing —
`FileNotFoundError` is a NO-GO and never a "probably fine". The loop sweeps
every 30 seconds, so five minutes is ten missed sweeps rather than a slow one.

**The process census is a SECOND and WEAKER signal**, kept because it says
*what* is up and under what parent, which the heartbeat cannot:

    powershell -NoProfile -Command "$a=Get-CimInstance Win32_Process; 'self-check: ' + [bool]($a | Where-Object {$_.ProcessId -eq $PID}); $a | Where-Object { $_.CommandLine -match 'notify_deliver_loop|supervise-notify-deliver' -and $_.ProcessId -ne $PID } | Select-Object ProcessId,ParentProcessId,CreationDate | Format-List"

Self-check `False` makes the census blind and it then proves nothing either
way. **And exclude your own PID**: the filter matches the command line of the
very command running it, so an unfiltered census ALWAYS returns at least one
row and reads as UP on a machine with nothing running.

**Never use `tasklist` in the Bash tool for this** — it returns zero rows for
every query there, so a live process reads as GONE.

### C2. AND IT IS PROVEN BY A ROW THAT ARRIVES, WITHIN FIVE MINUTES

A running process is not a working one. Operator's condition, stated in these
words: *the loop works under a supervisor, proven by one test row that reaches
`#resonate-os-output` within 5 minutes.*

**CORRECTED 2026-10-03 by running it, and the correction is not cosmetic.**
`notify.OPERATIONAL` DOES NOT EXIST — there is no such constant and no such
event type. Worse, **no destination in `destination_for()` resolves
`output_channel()` at all**: `GLOBAL` goes to ops, `STATUS` to status,
`WORKSPACE` to the workspace's own room, and nothing routes to OUTPUT. So a
row CANNOT be planned into `#resonate-os-output` by routing, and the probe
has to set the channel itself and SAY SO. `output_channel()` exists and is
tested and has zero production callers.

    py -3 -c "from src import providers, notify; providers.load_env(); OUT=notify.output_channel(); r=notify.plan(notify.STATUS_CHECKPOINT, None, fields={'note':'canary go-checklist probe'}, ids={'probe':'go-checklist'}); u=notify._update(r['id'], channel=OUT, why='probe: channel overridden to OUTPUT; nothing routes there'); print(u['id'], u['status'], u['channel'])"

Then, within **five minutes**, touching nothing:

    py -3 -c "from src import notify; rows=[r for r in notify.load() if r['ids'].get('probe')=='go-checklist']; print([(r['id'], r['status']) for r in rows])"

**GO:** the status has moved off `planned` **and** the message is visible in
`#resonate-os-output` (`C0C6DES2L7L`) — checked with your own eyes, because a
status field is this system's claim about reality and the channel is reality.
**NO-GO:** still `planned` after five minutes, or nothing in the channel.

Delete the probe row afterwards or declare it. An undeclared probe is noise
somebody will chase.

### C3. The output channel is its own, and is not the ops channel

    py -3 -c "from src import providers, notify; providers.load_env(); print('output', notify.output_channel()); print('ops   ', notify.ops_channel()); print('differ', notify.output_channel()!=notify.ops_channel())"

**GO:** output `C0C6DES2L7L`, ops `C0C3C6MDN9L`, `differ True`. **NO-GO:**
output is `None`, or the two are equal — generated copy would then be published
into the room that exists for alerts, which is how an operations channel gets
muted. Requires `task-1008` merged.

---

## D. The person being written to

### D1. The address is verified and sendable by the policy's primary field

    py -3 -c "from src import providers, store; providers.load_env(); r=[x for x in store.load() if x['id']=='savagebrands-com'][0]; c=r['contacts'][0]; print('state', r.get('state')); print('sendable', c.get('sendable'), 'verdict', c.get('verdict')); print('at', (c.get('verification') or {}).get('at'))"

**GO:** `state verified`, `sendable True`, `verdict valid`, `at` recent.
**NO-GO:** anything else. Recorded trap: EmailBison's own `status` field is a
DIFFERENT fact from ContactOut's and Reoon's verdicts, and reading it alone
once produced a false "never verified".

### D2. They are not blocked, held, or already ours to leave alone

    py -3 -c "from src import providers, store, eligibility; providers.load_env(); rec=[x for x in store.load() if x['id']=='savagebrands-com'][0]; print(eligibility.decide(rec, rec['contacts'][0], 'em1', channel='email'))"

**GO:** the verdict the operator approved for this canary, with its reason.
**NO-GO:** any block, any hold, or `unknown` — **UNKNOWN never becomes cold and
never becomes revival.**

### D3. Nobody at this account sits in an internal or unknown-owner campaign

    py -3 -m src.collision --workspace 10 savagebrands.com

The workspace argument is the NUMERIC id the credential is bound to. The name
is refused: `emailbison` compares against workspace 10 and says so, because
`workspace_id` is ignored by every route and a read taken against the wrong
binding cannot be told apart from a correct one afterwards.

**GO:** no collision, or a HOLD the operator has explicitly accepted.
**NO-GO:** a collision with 274/327/328/352, or with any campaign whose owner is
`unknown` — those are NOT CLEAN for outreach whoever owns them.

---

## E. The words

### E1. The copy is GENERATED, not a template

The phase 2 brief records phase 0 reaching gate 7 with an `li1` TEMPLATE and no
model call at all, because `step_objective_block` had 0 occurrences.

    py -3 -c "from src import llm; print(type(llm.from_env()).__name__)"

**GO:** `OpenAICompatibleModel`, or another real model. **NO-GO:** `NoModel` — a
live run with no model refuses, and a run reporting GENERATED without one is the
shape this repository has been bitten by twice.

### E2. One authority for the word count

    py -3 -c "from src import lint; print(lint.STEP_WORD_CONTRACT); print('REPLY_MIN_WORDS' in dir(lint), 'REPLY_MAX_WORDS' in dir(lint))"

**GO:** one contract printed, then `False False`. **NO-GO:** either constant
present — two authorities for one number intersected to exactly ONE legal length
for em2, which is an equality and not a threshold.

### E3. No em dash reaches a prospect

**CORRECTED 2026-10-03 by running it.** `tests.test_punctuation` DOES NOT
EXIST — `ModuleNotFoundError`, counted as one error, which is what the old
command's `FAILED (errors=1)` actually was. The real modules are
`test_punctuation_normalisation` and
`test_the_normaliser_does_not_manufacture_a_banned_dash`.

    py -3 -m unittest tests.test_copylint tests.test_punctuation_normalisation tests.test_the_normaliser_does_not_manufacture_a_banned_dash 2>&1 | tail -5

Every `lint` entry point takes a RECORD, not a string, so there is no honest
one-liner for a raw body. But `normalise_punctuation` takes a STRING, so the
ban itself CAN be proven directly, and should be — a green module proves the
module's expectations are met, not that the dash is gone:

    py -3 -c "from src import lint; print({n: (c not in lint.normalise_punctuation('word'+c+'word')) for n,c in {'em':'—','en':'–','bar':'―','minus':'−','figure':'‒'}.items()}); print('control, plain hyphen untouched:', lint.normalise_punctuation('word-word'))"

**GO:** `em` is `True` — the em dash does not survive the normaliser — and the
control leaves a plain hyphen alone. **NO-GO:** `em` is `False`.

*Measured 2026-10-03:* `em` and `en` are both removed, so the item PASSES. Two
things found while proving it, neither of which changes the verdict:
`test_punctuation_normalisation` has **5 failing tests** because the
replacement changed from `" - "` to `", "` and the assertions still expect the
old string — the guard holds and its own tests are stale, which is the worst
way for a guard to be red. And `U+2015`, `U+2212` and `U+2012` all survive the
normaliser untouched.

### E4. The copy-review file exists, and names what the writer stood on

Operator's requirement, 2026-10-03: the copy-review file states **the contract,
the role ladder, and the research rows the writer stood on** — not just the
finished text.

    dir /b C:\Users\Zvonimir\Desktop\resonate-ops\copy-review\PHASE0-*.md

**GO:** a file for this run, carrying those three things, and the operator has
graded it. **NO-GO:** no file, a file missing any of the three, or one nobody
has read. A negative grade is a defect-map finding and the canary waits for it.

---

## F. Money and volume

### F1. The OpenRouter ceiling binds, and verification credits are not in scope

**AMENDED 2026-10-03 BY THE OPERATOR, ZVONIMIR, AND THIS REPLACES THE OLD F1.**
The old item failed the run on `USD_PER_UNIT['credits'] is None`, which made
every unpriced credit provider a blocker.

**VERIFICATION CREDITS ARE AUTHORISED WITHOUT A PRICE.** Reoon and Deliverable
are authorised to spend credits with **no USD price attached** —
**authorised by the operator, Zvonimir, on 2026-10-03.** They therefore
**neither count towards any cap nor block this item**, and `credits` having
no entry in `USD_PER_UNIT` is no longer a NO-GO. Nobody has priced them, that
is still a real answer, and the operator has decided it does not matter here.

**THE ONLY HARD CAP IS OPENROUTER: 50 USD FOR THE NIGHT, FAIL-CLOSED ON
`BudgetExceeded`, SHARED ACROSS BOTH LANES.** One budget, not one per lane.

    py -3 -c "from src import clients, spendledger as sl; cfg=clients.load('productive'); print('ceilings', sl.provider_caps(cfg,'openrouter')); print('spent_usd', sl.spent('productive', provider='openrouter')/1_000_000)"

And the cap must be proven to BIND, by effect rather than by reading the
YAML — bisect the largest spend that is still allowed:

    py -3 -c "from src import clients, spendledger as sl; cfg=clients.load('productive'); lo,hi=1,60_000_000; exec('while lo<hi:\n mid=(lo+hi+1)//2\n try:\n  sl.check(\'productive\',cfg,mid,provider=\'openrouter\'); lo=mid\n except sl.BudgetExceeded:\n  hi=mid-1'); print('largest allowed USD', lo/1_000_000)"

**GO:** the largest allowed spend is the operator's figure, and one unit more
raises `BudgetExceeded`. **NO-GO:** no ceiling is declared for `openrouter`
(an absent key is refused, which is safe but is not a cap), or the largest
allowed spend is **not** the operator's figure — in EITHER direction. A cap
that binds somewhere other than where the operator set it is not the
operator's cap, and a run sized against 50 USD that actually refuses at 20
cents will halt in the middle of the night with nobody awake to see why.

*Measured 2026-10-03 22:45, and this is why the "in either direction" clause
is there:* `openrouter.per_day` is declared at `20000000` (USD 20.00), but the
largest OpenRouter spend `check` will actually allow is **USD 0.199973**. The
client-wide `budget.per_day` of `200000` is checked too, it is a documented
MIXED-UNIT TRIPWIRE summing cents and credits, and at 200,000 it is a hundred
times SMALLER than the provider ceiling it sits in front of — so the provider
ceiling is unreachable and USD 1.00 of OpenRouter is refused today.

### F1b. Report the OpenRouter running total every 90 minutes

Operator, 2026-10-03. The figure goes into
`docs/MORNING-HANDOVER-2026-10-04.md`, with a wall-clock timestamp on each
entry.

    py -3 -c "from src import spendledger as sl; print(sl.spent('productive', provider='openrouter')/1_000_000)"

### F2. The mailbox actually has room

    py -3 -c "from src import providers, senderheadroom as s; providers.load_env(); st=s.load_state(); print('walked_at', s.walked_at(st)); print('freshness', s.freshness(st))"

**GO:** room today, from a walk that was complete and fresh. **NO-GO:** a
REFUSED walk. **REFUSED IS NOT ROOM**, and the send date is a property of the
MAILBOX, not of the campaign.

---

## G. After the send, before anybody calls it a success

### G1. The provider confirms it, not us

    py -3 scripts/provider_truth.py 2>&1 | tail -10

**GO:** a provider-confirmed send event for this campaign id. **NO-GO:**
anything derived from our own ledger. *Recovered is not sent, scheduled is not
sent, enrolled is not sent, and active is not sent.*

### G2. A reply still reaches a human

Re-run **C1 and C2**. They are the condition both before and after: a canary
whose reply reaches nobody is a canary nothing can be learned from.

---

## The standing refusals this checklist does not re-litigate

- **Two separate written GOs**, email and LinkedIn, each naming recipient,
  sender and campaign. Neither implies the other.
- **No provider write and no Slack post outside the output channel** without
  the operator's GO.
- **Nothing is resumed, activated, paused or attached** without an explicit
  `APPROVED`. The 2026-09-26 freeze covers launches, activations, enrolments,
  provider attachments, cohort pushes and prospect-facing sends.
- **Internal campaigns are never written to.** Absence of a positive Resonate OS
  record in the ledger is a refusal, never a pass.
- **Legacy campaigns are never resumed**, from code or by hand.
- **487 is never resumed again** under any outcome. That grant is spent.

---

## STATE AT THE MOMENT OF WRITING — 2026-10-03, ~22:00

**Every command above was EXECUTED while writing this file, and six of them
were wrong and were corrected by running them.** A checklist whose commands
do not run is worse than none: it is read as reassurance. The six were
`classify_campaign` (needs a `channel` first argument), `spendledger.caps`
(needs a config; use the CLI), `lint.check` (takes a RECORD, not a string —
there is no honest one-liner for a raw body), `collision.check` (does not
exist; the CLI does, and wants the NUMERIC workspace id), `eligibility.decide`
(takes a record and a contact and a step key, not two id strings), and
`senderheadroom.describe` (does not exist).

### Currently NO-GO

| item | state | what it would take |
|---|---|---|
| **A2** | `task-one-os-authority` is NOT in master | merge it |
| **C1** | **ZERO python processes on the machine** — no deliver loop, no digestwatch | start one under a supervisor |
| **C2** | cannot pass while C1 fails | C1 first |
| **C3** | `task-1008` not merged, so `notify.output_channel` does not exist on master | merge it |
| **F2** | headroom walk is from **2026-09-24**, `freshness` returns **False** at **217.7 hours** stale | re-walk the estate |

### Currently GO, measured

| item | measured |
|---|---|
| **A3** | `True`; `resonate_internal` ×4 for 274/327/328/352, `resonate_os` for 481; all six junk values `unknown` |
| **D1** | `state verified`, `sendable True`, `verdict valid`, verified `2026-10-03T11:51:25` |
| **D3** | `savagebrands.com: clear` — **`sent=0`, `replies=0`** |
| **E2** | one contract; `REPLY_MIN_WORDS` and `REPLY_MAX_WORDS` both absent |

### Two findings the verification produced

1. **D2 confirms the em1 ruling concretely.** `eligibility.decide` on
   savagebrands today returns
   `blocked:lint:em1_body_103_words_over_contract_60_to_90`. The STORED copy
   is 103 words: refused by master's `(60, 75, 90)` and inside
   `task-copy-exemplars`' `(90, 120, 140)`. This is the operator's "generating
   under the 90 ceiling would return the old shape", measured rather than
   argued — and it is also why phase 0 must use GENERATED copy, not stored.

2. **D3 closes the canary brief's open measurement.** That brief asked "does
   savagebrands have prior provider sends?" and said to treat
   `task-937-prior-contact-copylint` as REQUIRED until it was answered, the
   conservative reading. The answer is **`sent=0`**, so 937 is **not required**
   for this canary. The copy cannot be claiming a first contact falsely
   because there was no prior contact.
