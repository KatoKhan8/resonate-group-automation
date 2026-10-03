# GLM branch verification: TASK-962

Branch: `task-one-os-authority`
Date: 2026-10-02T21:26:07.054058+00:00
Model: glm-5.3
Duration: 98.983s
Usage: {'prompt_tokens': 7530, 'completion_tokens': 7845, 'total_tokens': 15375, 'reasoning_tokens': 6973, 'cached_tokens': 832}

Parts: 8 (part 1=FAIL, part 2=NEEDS_CLAUDE, part 3=FAIL, part 4=NEEDS_CLAUDE, part 5=PASS, part 6=PASS, part 7=FAIL, part 8=PASS)

## Verdict: FAIL

**part 1 of 8: the prior-contact authority ships uncalled (draft.md's own note: the caller still passes the boolean "until that caller is changed"), leaving the named defect enforced only by prompt prose, and canary_cohort.py:23-24 commits an impossible count (52 wrong people among "EXACTLY 43 rows").**

## GLM spend

This call: 28 ledger rows, 429581 micro-USD

## Changed files (22)

- `docs/ATTRIBUTION-AND-COLLISION-ARE-TWO-QUESTIONS-2026-10-02.md`
- `docs/qwen-tasks/REVIEW/TASK-962-one-os-authority-and-collision-never-asks-whose-it-is.md`
- `prompts/draft.md`
- `scripts/canary_cohort.py`
- `src/claims.py`
- `src/collision.py`
- `src/eligibility.py`
- `src/executionguard.py`
- `src/nextaction.py`
- `src/osattribution.py`
- `tests/test_a_cohort_is_a_set_of_people_not_a_number.py`
- `tests/test_a_lead_is_classified_before_it_is_contacted.py`
- `tests/test_a_live_sequence_holds_whoever_is_running_it.py`
- `tests/test_a_reply_counts_even_when_the_counter_says_zero.py`
- `tests/test_an_empty_ledger_is_not_a_first_contact.py`
- `tests/test_an_undeclared_campaign_is_never_ours.py`
- `tests/test_no_write_happens_without_every_gate.py`
- `tests/test_our_own_staging_is_not_their_history.py`
- `tests/test_staging_refuses_colliding_contacts.py`
- `tests/test_the_account_is_not_cold_and_we_would_have_said_it_was.py`
- `tests/test_the_guard_asks_who_contacted_them.py`
- `tests/test_the_second_client_runs_on_the_same_engine.py`

## Diff stat

```
 ...N-AND-COLLISION-ARE-TWO-QUESTIONS-2026-10-02.md |  253 ++++
 ...thority-and-collision-never-asks-whose-it-is.md |  131 +++
 prompts/draft.md                                   |   66 +-
 scripts/canary_cohort.py                           |  238 ++++
 src/claims.py                                      |  123 ++
 src/collision.py                                   | 1211 +++++++++++++++++++-
 src/eligibility.py                                 |  143 ++-
 src/executionguard.py                              |   61 +
 src/nextaction.py                                  |   23 +-
 src/osattribution.py                               |  163 +++
 ...est_a_cohort_is_a_set_of_people_not_a_number.py |  179 +++
 ..._a_lead_is_classified_before_it_is_contacted.py | 1030 +++++++++++++++++
 ..._a_live_sequence_holds_whoever_is_running_it.py |  433 +++++++
 ...reply_counts_even_when_the_counter_says_zero.py |   31 +-
 .../test_an_empty_ledger_is_not_a_first_contact.py |  281 +++++
 tests/test_an_undeclared_campaign_is_never_ours.py |  311 +++++
 tests/test_no_write_happens_without_every_gate.py  |   49 +-
 tests/test_our_own_staging_is_not_their_history.py |   41 +-
 tests/test_staging_refuses_colliding_contacts.py   |   63 +-
 ...nt_is_not_cold_and_we_would_have_said_it_was.py |   36 +-
 tests/test_the_guard_asks_who_contacted_them.py    |  303 +++++
 ...st_the_second_client_runs_on_the_same_engine.py |   49 +-
 22 files changed, 5163 insertions(+), 55 deletions(-)

```

## Acceptance output

```
$ python -c "import os,subprocess,sys; out=subprocess.run(['git','rev-parse','--path-format=absolute','--git-common-dir'],capture_output=True,text=True,encoding='utf-8').stdout.strip(); assert out and os.path.isabs(out), 'git would not answer absolutely, so the ledger cannot be found'; os.environ['CAMPAIGNS']=os.path.join(os.path.dirname(out),'work','campaigns.jsonl'); sys.path.insert(0,'.'); from src import collision; ids,readable=collision.os_campaign_ids(); assert readable, 'the authority was not readable, so every \"not ours\" below would be vacuous'; keys={collision.campaign_key(i) for i in ids}; assert collision.campaign_key(481) in keys, '481 is not in the authority: wrong ledger'; internal=[c for c in (274,327,328,352) if collision.campaign_key(c) in keys]; assert not internal, 'operator-declared internal campaigns are in the OS authority: '+str(internal); print('OK 481 is OS, 274/327/328/352 are not, authority readable,', len(ids), 'campaigns, from', os.environ['CAMPAIGNS'])"
exit=0
OK 481 is OS, 274/327/328/352 are not, authority readable, 20 campaigns, from C:/Users/Zvonimir/Desktop/resonate-group-automation\work\campaigns.jsonl

$ python -c "import sys; sys.path.insert(0,'.'); from src import osattribution as oa; read=oa.attribution('bison',481,ledger_says='resonate_internal',authority_says=(frozenset(),True)); blind=oa.attribution('bison',481,ledger_says='resonate_internal',authority_says=(frozenset(),False)); assert read=='not_ours', 'a READ authority must let a positive internal claim disown: '+read; assert blind=='unknown', 'an UNREADABLE authority must give UNKNOWN, never not_ours: '+blind; assert oa.attribution('bison',481,ledger_says='resonate_os',authority_says=(frozenset(),False))=='ours'; print('OK readable+internal ->', read, '| unreadable+internal ->', blind)"
exit=0
OK readable+internal -> not_ours | unreadable+internal -> unknown

$ python -c "import sys; sys.path.insert(0,'.'); from src import collision as c; mem=lambda cid: {'campaign_id':cid,'status':'in_sequence','emails_sent':1,'replies':0,'opens':0,'interested':False}; raw=lambda e,cid: {'email':e,'id':1,'status':'active','overall_stats':{'emails_sent':1,'replies':0,'opens':0},'lead_campaign_data':[mem(cid)],'created_at':'2026-08-01T00:00:00+00:00'}; acct=lambda cid: (lambda people: {'domain':'example.test','workspace':'productive','leads':len(people),'people':people,'our_staging_excluded':[],'emails_sent_total':1,'anyone_in_sequence':any(p['in_sequence'] for p in people),'unknown_statuses':[],'any_bounce':False,'verdict':c.IN_SEQUENCE,'checked_at':'2026-10-02T00:00:00+00:00'})([c.touches_of(raw('a@example.test',cid))]); ours=acct(487); theirs=acct(352); assert ours['anyone_in_sequence'] and theirs['anyone_in_sequence'], 'the fixture carries no live sequence, so it proves nothing'; vo,wo=c.account_policy(ours); vt,wt=c.account_policy(theirs); assert vo==c.HOLD and vt==c.HOLD, 'a live sequence must HOLD whoever owns it: OS='+vo+' internal='+vt; assert 'our' not in wo.lower() and 'ours' not in wt.lower(), 'the reason claims ownership, which collision never asks: '+wo+' / '+wt; print('OK OS 487 ->', vo, '| internal 352 ->', vt, '| same verdict:', vo==vt)"
exit=0
OK OS 487 -> hold | internal 352 -> hold | same verdict: True

$ python -c "import sys; sys.path.insert(0,'.'); from src import collision as c; mem={'campaign_id':352,'status':'in_sequence','emails_sent':2,'replies':1,'opens':1,'interested':False}; raw={'email':'a@example.test','id':1,'status':'active','overall_stats':{'emails_sent':2,'replies':1,'opens':1},'lead_campaign_data':[mem],'created_at':'2026-08-01T00:00:00+00:00'}; p=c.touches_of(raw); acct={'domain':'example.test','workspace':'productive','leads':1,'people':[p],'our_staging_excluded':[],'emails_sent_total':2,'anyone_in_sequence':p['in_sequence'],'unknown_statuses':[],'any_bounce':False,'verdict':c.IN_SEQUENCE,'checked_at':'2026-10-02T00:00:00+00:00'}; v,why=c.account_policy(acct); assert v==c.STOP, 'a reply is terminal and is asked FIRST, before the live-sequence HOLD: got '+v+' - '+why; print('OK a reply beside a live sequence ->', v)"
exit=0
OK a reply beside a live sequence -> stop
```

## GLM response

### Part 1 — FAIL

the prior-contact authority ships uncalled (draft.md's own note: the caller still passes the boolean "until that caller is changed"), leaving the named defect enforced only by prompt prose, and canary_cohort.py:23-24 commits an impossible count (52 wrong people among "EXACTLY 43 rows").

## 1. Does the new code have a production caller?

**For `src/claims.py` (`prior_contact_state`, `may_claim_first_contact`): NO CALLER, by the branch's own text.** The added note in `prompts/draft.md` ("A NOTE ON WHERE THIS VALUE COMES FROM") states the live caller still passes `bool(claims.prior_contact(...))` and must be read as `unknown` "**until that caller is changed**" — i.e., it was not changed on this branch, and no prompt-building module appears in the 22-file changed list. So the three-state authority that the `claims.py` header calls THE fix (912 provider sends read as "you have not met them") is consumed only by tests, and the property is enforced by prose instructions to an LLM, not by `may_claim_first_contact`. Defeat at stated scale: any of the ~911/912 provider-touched people with an empty `rec["events"]` reaches `draft.md` as `prior_contact: false`; the first-touch branch stays reachable and only model compliance with the new paragraph stands between the system and the exact false assertion the header names. Whether `src/nextaction.py`/`src/executionguard.py` (part 3) or `src/collision.py` (part 2) gate on it is settled by those parts; part 1 establishes the copy-layer caller is untouched.

`scripts/canary_cohort.py` is an operator CLI, not pipeline-wired; it consumes `collision`, nothing consumes it. `src/osattribution.py`'s production caller, if any, is `src/collision.py` — **part 2**.

## 2. Can the acceptance check fail?

Command 1 can fail concretely: unset `CAMPAIGNS` with no `work/campaigns.jsonl` under the git common dir → `readable` false → AssertionError. Commands 2–4 evaluate pure fixtures and can fail only on code change, which is their job. Two vacuity gaps:

- **None of the four commands touches `prior_contact_state`, `may_claim_first_contact`, `canary_cohort.py`, or `draft.md`.** The bulk of the diff (~2,900 lines: claims, canary, prompt, their tests) has zero acceptance coverage.
- **Command 2 never supplies the conflict case**: `ledger_says='resonate_internal'` with `authority_says=(frozenset({'…481'}), True)` — ledger says internal, readable authority says OS. That is the one input "one OS authority" exists to settle, and the check only exercises agreement and unreadable-authority cases. The answer lives in part 3 (`src/osattribution.py`), unverified by the check.

## 3. Do the numbers reconcile?

- `scripts/canary_cohort.py` lines 23–24: "`bison_lead_id AND has_research` selects EXACTLY 43 rows - and 52 of them are the wrong people." **52 wrong people cannot fit in 43 rows.** Either the selection is 95 rows (then "exactly 43 rows" is false) or the 52 is false — in the header of the file whose thesis is that counts mislead. Line 20's 37+3+2+1=43 does reconcile.
- 912 sends / 1 local touch / 1,582 records (`draft.md`, `claims.py` header) are mutually consistent but recomputable from nothing in the diff; no changed code prints or derives them.

## Also checked

- `scripts/canary_cohort.py` and `tests/test_a_cohort_is_a_set_of_people_not_a_number.py` answer to the 2026-10-01 cohort-reproducibility rule, not to "one OS authority and collision never asks whose it is." Part 8 may claim the linkage; the title does not.
- No scratch files (*.txt/*.err/*.out) at root in the changed list.

VERDICT: FAIL - the prior-contact authority ships uncalled (draft.md's own note: the caller still passes the boolean "until that caller is changed"), leaving the named defect enforced only by prompt prose, and canary_cohort.py:23-24 commits an impossible count (52 wrong people among "EXACTLY 43 rows").

### Part 2 — NEEDS_CLAUDE

collision.py is cut at 58% (38,229/65,661 chars) and its remainder is in no part, so the classification engine's production callers and the consumer of the fail-open `revival_approved` coercion cannot be settled from any part.

## 1. Production caller?

**Partial only — and the gap is the majority of the new code.**

- `campaign_key` (hunk @@ -405,6 +406,81, ~L410) → called by `mid_sequence_campaigns` (~L445).
- `mid_sequence_campaigns` → called by `account_policy` at the `anyone_in_sequence` arm (~L1470), which is a pre-existing production path. These two are wired.

**NO VISIBLE CALLER** for the entire step 1–5 engine added in hunk @@ -1371,6 +1527,1049: `settings`, `dated_sends`, `last_send_at`, `os_campaign_ids`, `our_heyreach_campaign_ids`, `email_history`, and whatever `classify` entry sits after them. The patch is cut at char 38,229 of 65,661 — mid-`email_history` — and `src/collision.py` appears in **no other part**, so the file's remainder (where the classification entry point, its `nextaction`/`eligibility` wiring, and the `osattribution` bridge's caller would live) is visible nowhere. `email_history`'s `anyone["claimed"]` is also never incremented in the visible text — probably assigned post-loop, but unverifiable.

## 2. Can the acceptance check fail?

Yes — none is vacuous:
- Check 1 fails if a ledger row mis-binds 274/327/328/352, or if the ledger is unreadable (`assert readable`).
- Check 3 fails under the pre-branch code (mid-sequence → `STOP`, assert `vo==c.HOLD` fires) and if the reason names ownership.
- Check 4 fails if the replied check ran after `anyone_in_sequence` (would return `HOLD`, assert `STOP` fires). The order swap is genuinely load-bearing and genuinely tested.

## 3. Numbers reconcile?

`20 campaigns` in the output reconciles with the `os_campaign_ids` docstring ("twenty bound provider campaigns, 451 to 506"). The other claimed measurements (1,555 paused rows, 69 heyreach rows, 1,381 contacts, 912-vs-1 sends, ~209,000 emails, 15-row pages) are external-data claims — not recomputable from the diff, not contradicted by it.

## Findings

- **`settings()` fail-open on the one flag that arms sending** (hunk @@ -1371,6 +1527,1049): `out["revival_approved"] = bool(out["revival_approved"])`. Input `recontact: {revival_approved: "false"}` (or `"0"`) in client YAML → `settings()["revival_approved"] is True` — every revival-classified lead becomes sendable. The branch validates the two day-counts with `CollisionUnknown` on a bad type, then string-coerces the interlock whose DEFAULTS comment reads "Only the operator flips this." Caveat priced honestly: the consumer of this flag is in the cut remainder, so I cannot prove the send gate reads it — the mechanism is visible, the blast radius is not.
- **NO FINDING** otherwise in the visible half: `account_policy`'s reply-before-sequence order, `last_send_at`'s complete/claimed fail-closed logic, and the `bool` guard in `campaign_key` all hold against the adversarial inputs I constructed.
- Minor, not a defeat: `mid_sequence_campaigns` counts only `IN_SEQUENCE` while `ACTIVE_MEMBERSHIP` has four words — reason-string-only; the HOLD comes from the flag, so no gate can soften.

## Also

- **Files vs task:** `prompts/draft.md` and `scripts/canary_cohort.py` are not visibly answerable to "OS authority / collision never asks whose it is" from this part — part 1 and the review doc (part 8) would settle them. All `src/` and test files plausibly answer.
- **Scratch files:** none — no `*.txt`/`*.err`/`*.out` at repo root in the changed list.

## Verdict

VERDICT: NEEDS_CLAUDE - collision.py is cut at 58% (38,229/65,661 chars) and its remainder is in no part, so the classification engine's production callers and the consumer of the fail-open `revival_approved` coercion cannot be settled from any part.

### Part 3 — FAIL

the branch's centerpiece `src/osattribution.py` has no production caller, its "file is deleted" claim is absent from the diff, and the heyreach authority numbers (40/36/4) are asserted by nothing.

## 1. Production caller for the new code

- `eligibility.recontact` / `decide(recontact_dossier=...)`: **CALLED** — `src/executionguard.py` (+~686–731) calls `collision.recontact_check`, then `eligibility.decide(..., recontact_dossier=...)`.
- **`src/osattribution.py` (163 new lines): NO CALLER.** Its own docstring says it is "destined for the eligibility path" — future tense. `eligibility.recontact` calls `collision.classify` directly (eligibility.py +~815–820), `executionguard` calls `collision` + `eligibility`, `nextaction` calls `collision.account_policy`. The only invocation of `osattribution.attribution` in the entire branch is acceptance command 2 (`python -c` with `authority_says=` injected). The module named first in the task title ("one OS authority") is dead code; the consolidation it claims is enforced nowhere a send decision is made.

## 2. Can the acceptance check fail?

Not vacuous, but it tests the wrong half:
- Cmds 1, 3, 4 can fail (ledger without 481; `account_policy` returning STOP for mid-sequence; reply-vs-sequence order swapped) — they bite.
- Cmd 2 bites only on **dead code** (osattribution, no caller).
- **No acceptance command reaches `executionguard.authorize` gate 4** — the code the diff itself calls "the one line that makes this rule bite on a live send." A schema typo like `contact.get("email")` vs the real key would pass exit=0 across all four commands.

## 3. Numbers

- "20 campaigns" (cmd 1) ↔ osattribution.py docstring table bison authority = 20: **reconciles**.
- **heyreach 40 / file 36 / authority-only 4: unreconciled** — no check reads `our_heyreach_campaign_ids`; not recomputable from the diff.
- canary docstring: "`bison_lead_id AND has_research` selects EXACTLY 43 rows, and 52 of them are the wrong people" — **52 > 43 as written is impossible**; it only reconcils if "them" means the 86 rows of both sets (d=52 ⇒ overlap 17). Input is outside the repo, unverifiable.
- osattribution.py:8–18 claims `config/resonate-os-campaigns.txt` "is gone" — **the 22-file diff contains no deletion of it.** Either it was never tracked ("shipped with" is then false) or it is still in the tree and the dual-authority defect persists on disk.

## Additional defects

- **eligibility.py `decide` (+~899–906): the docstring's "carries that onto every verdict it returns" is false.** Only the suppression-blocked and final-eligible returns attach `recontact=asked`; the `campaign_reason` and content-lint returns do not. Concrete consequence in executionguard (+~724–728): campaign stopped + cold dossier → `decided` returns early without `recontact` → `_classified.get("asked")` is `None` → `_require` fails with *"the lead classification did not run on this step"* — a false statement that masks the real reason (campaign_stopped) and sends the operator to fix the wrong thing. No wrong send; wrong label at 100% of such refusals.
- executionguard +~717: `except Exception` on `recontact_check` turns a code bug (AttributeError) and an unreadable ledger into the same clean refusal — a total send halt with exit=0 and no distinction raised.

## File scope / scratch

- `scripts/canary_cohort.py` + `tests/test_a_cohort_is_a_set_of_people_not_a_number.py`: shortlist-digest work; on its face unrelated to "one OS authority / collision never asks whose it is" (part 8's review doc may claim otherwise — it is the only place that could).
- No scratch files at repo root.

VERDICT: FAIL - the branch's centerpiece `src/osattribution.py` has no production caller, its "file is deleted" claim is absent from the diff, and the heyreach authority numbers (40/36/4) are asserted by nothing.

### Part 4 — NEEDS_CLAUDE

30% of the file under review is cut mid-file (visible in no other part) and the production-caller answer lives in parts 2–3, so neither the file's complete assertions nor a PASS on question 1 can be settled here.

## 1. Production caller

**Not answerable from this part — it contains only a test file.** `tests/test_a_lead_is_classified_before_it_is_contacted.py` calls `collision.classify`, `collision.email_history`, `collision.linkedin_history`, `collision.recontact_dossier`, `eligibility.recontact` (lines ~145–180), so the *callee* side of the bridge exists in `src/`. Whether `src/eligibility.py` / `src/nextaction.py` / `src/executionguard.py` actually call `classify`/`recontact` in the send path — the caller side — is in **part 3** (and whether `collision` calls the new `osattribution.attribution` bridge is in **part 2**). No caller can be confirmed here.

## 2. Can the acceptance check fail?

Yes, all four have nameable failure inputs; none is vacuous:

- **Check 1** fails on ledger state: append a line binding campaign 352 in `work/campaigns.jsonl` → `assert not internal` fires; delete the 481 binding → `assert collision.campaign_key(481) in keys` fires; make the file unreadable → `assert readable` fires. Note it reads the git **common** dir's ledger, i.e. shared main-worktree state, not branch state — correct, since `work/campaigns.jsonl` is not in the changed-files list.
- **Check 2** is a pure-function pin: any regression returning `unknown` on readable+internal (treating `resonate_internal` as needing authority confirmation) fails it.
- **Check 3** fails if `account_policy` returns ALLOW for `in_sequence`, or if either reason string contains the substring `our`/`ours`. (Minor asymmetry: it checks `our` only in the OS reason and `ours` only in the internal one — a internal reason reading "our internal campaign" would pass. Wording-only; the HOLD==HOLD behavior itself is asserted, so no cost.)
- **Check 4** fails if replies are consulted after the live-sequence check (would yield HOLD, not STOP).

## 3. Do the numbers reconcile?

- **"20 campaigns"** reconciles: `OS_CAMPAIGNS` (lines 47–49) has exactly 20 elements; the docstring (line ~30) claims "exactly twenty bound provider campaigns, 451 to 506"; the acceptance run prints 20 from the real ledger.
- **Not recomputable from the diff:** ~209,000 manual sends by 274/327/328/352; 406 / 1,948 / 406 queue rows; 1,555 paused legacy rows. These are provider-side claims carried in the docstring only — no test or acceptance command recomputes them, and no test asserts them (fixtures are synthetic). Unverified, but they gate nothing in code; the classification logic keys on statuses, not these counts.

**Findings in the visible ~70%: NO FINDING.** I checked the sentinel-default trap (`_UNSET`, line ~62), the `sent_row` id arithmetic (no cross-campaign collisions: campaign-id gaps ≥7,800 > max 400 days), the day-14 boundary with `_ago`'s whole-second truncation (slack ≤1s, immaterial), and the ledger-unreadable → UNKNOWN case (covered at `test_an_unreadable_campaign_ledger_blocks_rather_than_going_cold`). Nothing constructs a wrong-send input.

## Also checked

- File/task alignment: this file is directly on-task (each "Required case 1–10" named in test docstrings). `prompts/draft.md` and `scripts/canary_cohort.py` are auditable only in parts 1 and 3; no off-task file nameable from here.
- Scratch files: none in the changed list.

## Verdict

The file is cut mid-file at `test_the_newest_os_touch_across_both_channels_sets_the_revival_clock` (~16,200 of 54,483 chars, roughly the last 300 of 1,030 lines unseen, and the test-run output is itself cut mid-class), and that tail exists in no other part; the production-caller question additionally requires parts 2–3.

VERDICT: NEEDS_CLAUDE - 30% of the file under review is cut mid-file (visible in no other part) and the production-caller answer lives in parts 2–3, so neither the file's complete assertions nor a PASS on question 1 can be settled here.

### Part 5 — PASS



## 1. Production caller?

Part 5 adds only tests, so no caller is required *of* these files. The functions they pin (`collision.account_policy`, `mid_sequence_campaigns`, `touches_of`, `recontact_dossier`, `claims.prior_contact_state`) are defined in parts 1–3; whether `src/nextaction.py`/`scripts/canary_cohort.py` call them is settled by parts 1 and 3 — not here.

One caller gap is visible *from part 5 itself*: `generate.py` — the renderer of `prompts/draft.md` — is **not in the changed-file list**, and the branch admits it. `tests/test_an_empty_ledger_is_not_a_first_contact.py`, final test (~lines 272–281): "Until `generate.py` passes the state, `false` still arrives." So `prior_contact_state` reaches the sent email only as an instruction in the prompt telling the model to reinterpret the boolean. COST, at the branch's own scale: on 1,581 of 1,582 records the draft still receives `prior_contact: false`; suppression of the false "first contact" claim is per-draft LLM compliance, not code.

## 2. Can the acceptance check fail?

Yes, for the collision/osattribution half: delete 481 from (or add 352 to) `work/campaigns.jsonl` → cmd 1 asserts fire; unreadable ledger → `readable` False → fires; invert the reply/live-sequence precedence → cmd 4 gets `hold` → fires; a reason containing substring "our" (e.g. "hours") → cmd 3 fires.

But it is **vacuous for half the branch**: no input to any of the four commands reaches `src/claims.py` (123 new lines), `prior_contact_state`, `may_claim_first_contact`, or `prompts/draft.md`. The empty-ledger defect — the one that put a false sentence in front of real people — has zero acceptance coverage; only the (unshown) test suite guards it.

## 3. Numbers reconcile?

- Internal: 1,582 records − 1 with a local touch = 1,581, matching the test's "1,581 of 1,582". ✓
- `mid_sequence_campaigns` expectations reconcile: person A = 487 live + 352 finished, person B = 352 live → `({"487","352"}, 0)`. ✓
- "912 sends", "~209,000 emails", "1,555 rows": source data not in any part I can see — docstring claims, unrecomputable.
- `OURS = 487` ("in the ledger authority as measured", `test_a_live_sequence...` ~line 38) is verified by nothing: acceptance checked 481 ∈, 352 ∉, never 487. Harmless (these tests booby-trap the authority), but the provenance comment is unconfirmed.

## Also

- All three part-5 files answer to TASK-962: the live-sequence file is the collision half, the empty-ledger file the attribution half, and `test_a_reply_counts...` is the precedence re-verdict the HOLD introduced.
- No scratch files in the changed list; `canary_cohort.py` is under `scripts/`. 
- The provided test-results block truncates mid-name (`test_an_unrecorded_linkedin_touch_still_c`) and shows **no result lines for either new part-5 file**. If that is the actual run rather than a clipped report, both new files never executed and exit=0 would not show it — this must be confirmed in parts 4/6–8's output.

## Findings

1. **No wired consumer for `prior_contact_state` in the sending path** — `generate.py` unchanged, admitted in-test; mitigation is prompt text, cost is model-compliance on 1,581/1,582 records per draft.
2. **Acceptance commands 1–4 cannot fail on `claims.py` or `draft.md` changes** — vacuous for that half.
3. Minor: `OURS=487` ledger-membership claim unverified against the acceptance run; cmd 3's `'our' not in why` is substring-brittle.

VERDICT: PASS

### Part 6 — PASS



## Q1 — Production caller for the new code

Part 6 adds **zero production code** — all five files are tests. The new surface they exercise (`osattribution.attribution`/`authority`/`_key`, `collision.HOLD`, `collision.recontact_check`, `collision.campaign_key`, `recontact_dossier`/`email_history`/`linkedin_history`) is consumed in production by **part 2 (src/collision.py)** and **part 3 (src/executionguard.py +61, src/eligibility.py, src/nextaction.py)** — the `recontact` dict added to the `decide` double at tests/test_no_write_happens_without_every_gate.py:761-768 implies the guard reads `decide()["recontact"]["asked"]`; that call site is part 3.

One caller claim **no part can settle**: test_our_own_staging_is_not_their_history.py:268-272 asserts "the two factories test `in (STOP, HOLD)`", but no factory file appears anywhere in the branch's file list. The STOP→HOLD re-verdict (three tests re-verdicted across this part) is safe only if that unchanged code is as described; the patch never shows it.

## Q2 — Can the acceptance check fail?

Yes, all four, on named inputs:
- Cmd 1: a ledger row `{"bison_campaign_id": 327}` added, or `work/campaigns.jsonl` replaced by a directory — breaks the internal-ids assert or `assert readable`.
- Cmd 2: make `attribution` return `unknown` on readable+internal, or `not_ours` on unreadable+internal — either assert fires.
- Cmd 3: put ownership back into `account_policy` — OS/internal verdicts diverge or the reason contains "our".
- Cmd 4: move the reply check after the sequence check — returns `hold`, assert fails.

Fragility, not vacuity: cmd 3's `'our' not in why.lower()` also fails on "hour"/"four"/"labour" in any reason string — a false-fail trap, but it proves the check has teeth.

## Q3 — Do the numbers reconcile?

Reconciled: BISON tuple (test_an_undeclared_campaign_is_never_ours.py:29-31) enumerates to **20**; HEYREACH (:33-38) to **40**; both match cmd 1's "20 campaigns" and the pinned assertions. INTERNAL (274,327,328,352) is disjoint from BISON, matching cmd 1. The incident list in test_staging_refuses_colliding_contacts.py: 4 named + "five more" = **9**, matches "Nine were already in the client's own campaigns".

**Not reconcilable from the diff — two items:**
1. The docstring (test_an_undeclared_campaign_is_never_ours.py:8-13) claims `config/resonate-os-campaigns.txt` "was deleted" and was measured a strict subset "4 of 20 bison, 36 of 40 heyreach". **The branch's file list contains no config/ deletion**, and no script in the branch reproduces the 4/36 measurement (scripts/canary_cohort.py is cohort digests, per part 1). Either the deletion happened outside this branch (part 2, which shows collision.py's read of it, or part 8's review doc, must say) or "the authority is now the only answer" is false and two sources of truth persist. If the strict-subset claim was wrong for even one id, that campaign flips OURS→UNKNOWN→cold and its leads become re-contactable — a cost I can name but not construct without the deleted file.
2. Pre-existing (unchanged context, same file header): "caught five (bounced); the other nine attached" = 14 of **19** staged — 5 unaccounted. Predates the branch; the PII edit sits directly above it.

## Also check

- All five part-6 files answer to TASK-962 (authority, ownership-blind collision, gate 4, STOP→HOLD). **scripts/canary_cohort.py** and **prompts/draft.md** (part 1) have no visible link to OS authority/collision from this part; parts 1 and 8 settle.
- No scratch files: no *.txt/*.err/*.out anywhere in the changed list.
- **Evidence gap**: the results block covers only part 3/4 test files and truncates mid-name; none of part 6's five files appears in it, so their pass status is asserted, not shown.

VERDICT: PASS

### Part 7 — FAIL

the parity evidence contradicts itself (165+70=235 vs failures=231; 14773 vs "of 14818"; 221 vs 231 names at one SHA), and the by-name diff proving "0 newly failing" cannot see the results the gap implies.

## 1. Production caller?

YES for the bridge this part concerns. `collision.recontact_check` / `recontact_dossier` are called by gate 4 in `src/executionguard.py` → `eligibility.decide(recontact_dossier=...)`. The call line itself is in **part 3**, but this part carries independent proof the call is real: `tests/test_the_second_client_runs_on_the_same_engine.py` (hunk @@ -455,17 +471,36 @@, `allow_collision`, new lines ~475–507) had to add a fourth mock for `recontact_check` to keep the pre-existing tenancy tests passing, and its comment states the failure mode unbound ("fails on a missing provider key and refuses at `recontact`") — a mock that nothing called would be inert, not required. `refused()`/`auth.gates` assertions in `tests/test_the_guard_asks_who_contacted_them.py:88-101` pin the gate name in `authorize`'s output. Unresolvable here: `src/claims.py` → **part 1**; whether `osattribution.attribution` has any caller besides the acceptance command → **part 2** (`collision.classify` step 5).

## 2. Can the acceptance check fail?

All four, non-vacuous:
- **Cmd 1**: a `work/campaigns.jsonl` row with campaign 327 → `assert not internal` fires; ledger unreadable → `assert readable` fires. It reads real external state.
- **Cmd 2**: `attribution` returning `not_ours` on an unreadable authority → `blind=='unknown'` assert fires.
- **Cmd 3**: the old rule (mid-sequence → STOP) → `vo==c.HOLD` fires. This is literally the mutation the doc says it ran ("HOLD → STOP … 14 tests red").
- **Cmd 4**: swapping arm order (mid-sequence asked before answered) → verdict becomes HOLD → `v==c.STOP` fires.

## 3. Do the numbers reconcile?

One does: the diffstat churn, 253+131+66+…+49 = **5218 = 5163 insertions + 55 deletions**. Exact.

The full-suite parity run (docs/ATTRIBUTION-AND-COLLISION-ARE-TWO-QUESTIONS-2026-10-02.md, § "The authoritative full-suite run", ~lines 155–165) does **not**:
- `165 failure(s), 70 error(s)` = **235**, but `failures=231`. Four failing results unaccounted, and the doc's parser control claims the runner itself "declared (231)" — both cannot be the failing count.
- `results_reached=14773` vs the runner's own `of 14818` — **45** unexplained, with `failures_are_partial=False` claiming completeness.
- Two baselines pinned to the same SHA `87a77eba`: "master 221-name baseline" (§ Per-module name-set diff, ~line 130) vs "FULL baseline … 231 names at 87a77eba" — **10 names** apart at one commit, unexplained.

**Cost, at scale:** the "0 newly failing / 0 no longer failing" headline is computed **by name set**. Whatever the 4 (and 45) results are — module-import errors and setup errors are the usual nameless kinds — the comparison method is structurally blind to exactly them. Up to 4 newly broken modules on this branch would be counted as parity. One line reconciling 235→231 (dedup? nameless errors?) would close this; none exists.

## Also checked

- **File scope**: all collision/guard/attribution/test files answer to TASK-962. `scripts/canary_cohort.py` + `tests/test_a_cohort_is_a_set_of_people_not_a_number.py` (+417 lines together) are cohort tooling whose tie to "one OS authority" is not visible from part 7 — content in **part 1**; the review doc in part 8 may justify it.
- **Scratch files**: none. `suite_verdict.txt` is referenced but lives in the uncommitted `scratchpad/measure` worktree, not the tree.

VERDICT: FAIL - the parity evidence contradicts itself (165+70=235 vs failures=231; 14773 vs "of 14818"; 221 vs 231 names at one SHA), and the by-name diff proving "0 newly failing" cannot see the results the gap implies.

### Part 8 — PASS



**1. Production caller?**

Not decidable from part 8 — this part is docs-only (the file itself says "Files: None", line ~105 of `docs/qwen-tasks/REVIEW/TASK-962-...md`). What part 8 *does* establish: the only callers of `collision.os_campaign_ids`, `collision.campaign_key`, `collision.account_policy`, `collision.touches_of`, and `osattribution.attribution` visible here are the four acceptance commands and tests — neither counts. The caller chain (whether `eligibility.py`/`nextaction.py`/`executionguard.py` invoke `osattribution`/`claims`, and whether `collision.os_campaign_ids` calls `claims`) is in **part 2 (src/collision.py)** and **part 3 (src/eligibility.py, nextaction.py, executionguard.py, osattribution.py)**; `scripts/canary_cohort.py` is **part 1**. Note the doc's own "Not in scope" says the send path is untouched — so if parts 2–3 show no src→src call into `osattribution`, the honest answer for that module is NO CALLER.

**2. Can the acceptance fail?**

Yes — nameable inputs for all four commands, so not vacuous:
- **Cmd 1**: any fresh worktree (empty `work/campaigns.jsonl`) → `campaign_key(481) not in keys` → `AssertionError: 481 is not in the authority` (recorded as measured); unreadable ledger trips `assert readable`; a ledger containing 274 trips the internal assert.
- **Cmd 2**: any build where `attribution` ignores readability makes `blind` return `not_ours` and fails.
- **Cmd 3**: the pre-refinement code (`8bfd9431`, STOP-on-OS) makes `vo=='stop'` and fails; a mis-shaped fixture trips the `anyone_in_sequence` pre-assert.
- **Cmd 4**: reply checked after the HOLD arm gives `hold` and fails.

Weakness, not defeat: cmd 3's ownership control `'our' not in wo.lower()` is evadable ("belongs to resonate") and false-positives on "hour"/"course"/"your"; the second `'ours' not in` clause is dead code (`'our' ⊂ 'ours'`). The real control is `vo==vt`, which is sound — the two fixtures differ only in `campaign_id`. Also: the three "observed failing" negative-control outputs are asserted in prose, not present in the result block I was given.

**3. Numbers reconcile?**

No number here recomputes from the diff, and mostly by design: `20 campaigns` is a live read of gitignored `work/campaigns.jsonl` (outside every part). `231 names, 0 new, 0 gone` and "the same five failing names" in `test_fixture_hygiene` cannot be checked — the test result block provided is truncated mid-name (`test_an_unrecorded_linkedin_touch_still_c…`); the five pre-existing failures are on master's reference, not introduced here. Reconciliation needs a rerun or **parts 3–7**.

**Also check**

- Off-task suspects: `scripts/canary_cohort.py` + `tests/test_a_cohort_is_a_set_of_people_not_a_number.py` (cohort digests, "NothingPrintsAProspect") are nowhere mentioned in the review doc's scope table — plausibly the consumer of the new `eligibility.py` cohort selection, but verify in **parts 1 and 3**. `prompts/draft.md` (66 lines) — **part 1**.
- Scratch files at root: none — all 22 files are docs/, prompts/, scripts/, src/, tests/.

**Verdict**

No production defeat constructible from part 8 alone; the checks can fail on named inputs; the unreconciled numbers point outside the repo or to parts 3–7.

VERDICT: PASS
