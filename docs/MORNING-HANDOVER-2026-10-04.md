# Morning handover, 2026-10-04

**Written through the night and filled in as it goes.** A section that says
PENDING has not happened; a section that says BLOCKED says what blocks it and
who can unblock it. Every number carries how it was measured.

---

## 1. Master SHA

**`975c18cc`**, pushed and verified equal to `origin/master`.
Reference: **`reference-228-master-975c18cc.log`**.

TWO merges landed today, both on the canary minimal path: **`task-973-write-barrier`** — the production-write
barrier now covers the MAIN checkout from inside a worktree, which it never did
before. GLM PASS, suite 228 names against the reference's 231 with **0 NEW** and
3 GONE, each of the three positively verified as having run and passed.
`git diff master <branch>` proven EMPTY afterwards, so that run became the new
reference: **`reference-228-master-7e8eee41.log`**.

## 2. The minimal path, and where each branch stands

The operator's success measure for the day: how many canary-minimal-path
branches are on master by evening, and whether phase 0 ran.

| branch | head | suite | GLM | state |
|---|---|---|---|---|
| `task-973-write-barrier` | `716a0cf7` | 228/0 new | **PASS** | **MERGED** at `7e8eee41` |
| `task-word-contract-enforced` | `874cf0ed` | **228 vs 228, 0 new, 0 gone — a perfect set match** | **PASS**, all 6 parts, at the fifth attempt | **MERGED** at `975c18cc` |
| `task-guard-regressions-rebased` | `fa644547` | clean at `758f0f98` (228/0/0) — **void now, master moved**; fresh run queued third | FAIL ×1 on a stale committed NAME-DIFF, deleted since; re-run in flight | **not merged.** Needs its fresh run |
| `task-1004-positive-replies-reach-a-human` | `a5729f2a` | **queued second**, on a tree already carrying master `975c18cc` | PENDING | **P0 — phase 0 cannot run before it** |

**Phase 0 is BLOCKED on P0 1–3**, by the operator's own reasoning: without them
a positive reply on the canary would never reach a human.

## 3. What 943's three GLM failures actually were

Worth reading before anybody "fixes" them, because two of the three would
revert decisions taken on 2026-09-30.

- **The first FAIL was the gate's**: the prompt carried `test_output[:8000]`,
  the HEAD of a verbose run over 16 changed modules, and it cut before both of
  the branch's controlling test files. GLM said so precisely and failed the
  branch for having no evidence its own tests ran. They had run: 53 OK and 15
  OK, measured directly.
- **The second FAIL was mine**: with the evidence visible, my new summary
  reported five failures with **no baseline context**, and GLM reasonably read
  five of master's standing failures as the branch's regressions.
- **The third re-run is in flight** with each failure now marked BASELINE or
  NEW and a line carrying the number that decides attribution.

The five themselves, measured on a neutral worktree **detached at master with
nothing from the branch present** — same five names, same counts, and all five
parse out of the reference:

1. **The em-dash ban is not lost.** `_PUNCTUATION_MAP["—"]` became `", "` in
   `20d9fb12` (2026-09-30) because the old `" - "` output **was** the banned
   pattern — the normaliser manufactured the refusal it existed to prevent. The
   tests were written 2026-09-28, two days earlier, and never moved.
   `lint.check` on a raw em dash still refuses, so **no em dash reaches a
   prospect either way.**
2. **Nine retries is the designed budget.** `MAX_WRITER_ATTEMPTS = 10`, raised
   3→6→10 in `b946b59c` the same day. The test pins a cap three versions old.
3. **The real defect underneath**: the rejection ledger accumulates and is never
   pruned. The reason list fed to retry 9 is **byte-identical** to retry 1 — ten
   items, nine of them from attempt 0. Logging every writer answer proves call 0
   returns the bad body and **calls 1–9 return the clean one**, so the model is
   told nine times to remove a phrase it removed on the first retry while the
   one live complaint is buried. Nine model calls per refused draft. The
   `KeyError` is this defect's symptom.

**DECISION FOR THE OPERATOR**: retire the two stale tests (which removes five
names from the 228, so the reference must be re-measured), or fix the unpruned
ledger on its own branch and merge 943 on its clean set match. The mechanism is
pinned either way.

## 4. Phase 0 / phase 1 / phase 2

- **Phase 0** — PENDING, blocked on P0 1–3. savagebrands is now **verified and
  sendable** and held only by `held:approval_stale`.
- **Phase 1** — PENDING, after phase 0.
- **Phase 2** — **RAN.** 300 accounts, 900 DMs, 8 cohorts, clock day 0→120
  through the real scheduler, classifier, DNC and recontact code. 3,116 sends,
  62 replies, 21 bounces, 15 DNC, **1 positive**. 90 scenario firings (30 × 3,
  each a different account and a different day, every verdict preset): **69
  matched, 21 not, 0 late.** 17 weekly digests written as files; `notify.plan`
  called, `notify.deliver` never. Spend **0.00 of 80 USD** — projected through
  the project's own price config rather than by spending calls.
  *"ovo kaže što sustav radi 120 dana, ne što bi zaradio; svaki odgovor je iz
  stope, ne iz tržišta."*

## 5. What is new in the second brain

`docs/second-brain/` opened today with the operator's two lines at the top of
its README — **the metric is the positive reply, the Farseer cadence is the
reference** — and the rule that every line carries source, date and `n`.

- `decisions.md` — every operator decision with its date and reason.
- `defects.md` — eight recurring PATTERNS, not individual defects; a shape earns
  its place on the second instance.
- `positive-replies.md` — the metric, its definition, and six measured answers
  about what this machine holds on Farseer.
- `email.md` — the EmailBison corpus, on `task-980-copy-learnings` @ `c66e2ed1`.
- `linkedin.md` — 121 of 121 campaigns, on `task-981-second-brain-linkedin` @
  `6b13e92e`.

## 6. Decisions for the operator

1. **943's two stale tests** — retire, or fix the ledger separately. §3.
2. **USD per credit for Deliverable and Reoon.** `spendledger.USD_PER_UNIT['credits']`
   is `None`, documented as *"NOBODY HAS PRICED IT, and that is a real answer."*
   Batch 3 of verification (483 contacts, up to 1,311 credits) is not evaluable
   against any cap until it is set.
3. **Two classifier questions only the operator can settle**, from the positive
   sample: does a price/what-is-it question count as positive (moves the
   defensible count 7↔10), and does interest with a named later date count
   (10↔12).
4. **The `client_approved` field's coverage** — now backfilled on A and B per
   today's decision; the task file records it.
5. **A third channel's vocabulary** (TASK-1001): `phone` and `whatsapp` as
   channels, or one `manual` channel with a sub-type. The second is smaller.

## 7. Monitoring log

One line every ~90 minutes: time, lock holder, what landed, what waits.

| time | suite lock | landed | waiting |
|---|---|---|---|
| 14:55 | FREE | 973 merged to master `7e8eee41` and pushed; reference re-measured at 228; gate fixed three times (evidence block, double count, baseline attribution) and pushed `d86d6dd4`; three Farseer tasks + TASK-1005 opened and pushed `203bcd80`; lane A's branch pushed `350bb2d2` after its push was refused | 943's third GLM re-run in flight; guard behind it; P0 lane running; lanes C and D landed, lane 4 and lane 3 resumed |
| 16:05 | **master** (my mistaken launch, since 15:54; the kill was refused by the classifier, so the P0 run is QUEUED behind it in the FIFO lock and starts by itself) | guard's suite CLEAN 228 vs 228, 0 new, 0 gone; P0 1-3 delivered on `task-1004-positive-replies-reach-a-human` `c41c9e05` with 32 tests and six mutations; the gate's timeout retry landed `15bf6eb2` with four tests | guard GLM running; 943's FIFTH GLM running (its parts 1-2 were GlmTimeout, not findings - A42); P0 suite queued |
| 16:30 | **master** (my mistaken launch, until ~16:45), then P0, then guard — two waiters in the FIFO queue, verified | **943 MERGED at `975c18cc`** and pushed: GLM PASS all 6 parts at the fifth attempt, suite 228 vs 228 with 0 new and 0 gone, `git diff master branch` proven empty. Guard's stale NAME-DIFF deleted `a2e4fb98` after its named regression was verified passing in BOTH logs | guard's fresh run (queued third, ~18:05) and its GLM re-run; P0's run (queued second, ~17:25) — phase 0 waits on it |
