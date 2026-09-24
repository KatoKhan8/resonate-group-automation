# Production handoff — 2026-09-24 midday

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-24-MORNING.md`.**

Master is at `d07ae25a` and pushed. Two branches merged today: `infra` at its
tip and `slack-agent` at `a87e787c`.

**NOTHING HAS PUSHED TO A CAMPAIGN SINCE THE INCIDENT.** Confirmed twice, two
independent sources — a queue read across all nine of our campaigns, and the
provider's event stream, where **all 194 post-midnight events belong to the
client's own campaigns 328 and 352 and none to ours.**

---

## 1. THE DRILL'S INSTRUMENT WORKS. IT IS THE FIRST TIME.

    20 of 20 monitors have two witnesses.      exit 0

**And adopting `46474c6c` was not what fixed it.** That was merged first, and
the very next `--verify` still answered `0 of 20`.

Witness 1 is "a live pid from a state file written after the boot". **Only
`supervise.py` ever wrote that file, and this estate is started by
`scripts/start_monitors.py`** — so `work/supervisor/` did not exist at all and
no monitor could hold witness 1, ever. Meanwhile `start_monitors --status`
read `20 UP` on `beat+process` and the table `--verify` prints directly
underneath showed every monitor beating within a minute.

Four handoffs read that as a reason to refuse the drill. **Refusing was
right; the diagnosis stopped one layer short.** `46474c6c` fixed the
monitor-name to heartbeat-file map, which is the NAME half. This is the other
half. ISSUE-028, fixed in `c1d93e94`.

The fix is `supervisor.record_started(name, pid)`, public, called by
`start_monitors.spawn`. **Deliberately not a change to the process model:**
making the supervisor the only thing allowed to start a monitor would mean
changing how a live estate is run, mid-day, to satisfy a measuring
instrument. `supervise.py` still writes the same file for the same monitors,
so the server cutover is unaffected.

**The drill is now runnable and has NOT been run.** It belongs in the no-send
window, per the standing instruction, and the operator's stop-and-report rule
still applies.

---

## 2. THE MONITOR TABLE IS DERIVED, AND 493 WAS UNWATCHED

Both hand-written lists are gone. The derived table reads **20** at today's
registry: the 15 plus `493` and the four `draft` campaigns 451/481/484/485.

**493 was `active`, had sent 22 emails, held 22 scheduled rows, and nothing
was watching it** — exactly the campaign the derived table said was missing
from the list a person typed while fixing an incident caused by campaigns
missing from that list. It is watched now and reads 0 blanks.

All 20 loops run one instance each on merged code.

---

## 3. 491 IS PAUSED BY SOMEBODY WE CANNOT NAME — OPERATOR

**Do not resume it without the operator's word.** This is the one item
blocking on a person.

**When:** `2026-09-23T22:15:31Z`, from the campaign's `updated_at`. The last
send in 491 was `20:47:46Z`, an hour and a half earlier, so that timestamp is
not a send. The 491 watcher detected it correctly one cycle later.

**Who: not us, and not nameable.** Every source and what it can say:

- the watcher's own attribution check: our campaign row logs no pause,
  archive or stop step
- `work/provider-write-refusals.jsonl`: **no 491 entry** — no refused attempt
  from our code
- `work/action-ledger.jsonl`: **dead.** 136 rows, last entry
  `2026-09-18T05:35:58Z`, zero 491 rows ever
- **the provider's event feed carries no campaign-lifecycle events at all** —
  8 types across 900 events, all delivery, lead and account. *So the ledger
  write-back in the standing order will never answer this class of question.*
  Worth knowing before building it.
- Slack: no message in the window
- no running process of ours could have done it. The only autonomous pause
  path is the watcher's blank-content halt, which emits
  `campaign_blank_content` first; the only such notification is 497 at
  `20:18:58Z`, and it was REFUSED.

### 3.1 The technical case for resuming, complete and measured today

- **0 blank rows sendable**, under the stricter predicate of §4. All 93
  faulty rows settled.
- **273 of 273** leads with resumable rows read individually, 0 errors:
  `subject_1`, `body_1`, `body_2`, `body_3` all present and non-empty on
  every one. No literal `None`.
- **0 foreign leads** among them — all 273 carry both `record_id` and
  `contact_key`.
- step **4753 has no queue rows yet** and would be generated on resume. It
  renders `Re: {SUBJECT_1}` / `{BODY_3}`, both present on all 273. The
  literal-`None` writer does not touch 491: its unused variables are
  `subject_2` / `subject_3` and no step references them.

The technical case is complete. The **authority** case is not, and the
watcher's own alert says find out who first.

---

## 4. A PAUSED CAMPAIGN IS DORMANT, NOT CONTAINED — ISSUE-026

`emptyrender.scan` split rows with an **allowlist** of sendable statuses and
filed everything else under `already`, a bucket whose own comment read
"already sent or stopped". **`sending_paused` is neither.**

491 was paused, so all 275 of its undelivered rows read `sending_paused`, and
blank row 22356723 was counted as contained when the only thing containing it
was the pause.

**Both witnesses said `pending: 0` and both were wrong in the same way**,
because the watcher heartbeat and an independent provider read share this
predicate. And **pausing the campaign is what moved the row out of `pending`**
— the halt erased the evidence of its own necessity.

Now a **denylist**: `SETTLED_STATUSES = {sent, stopped, bounced}`. An
allowlist fails closed on a status nobody anticipated, and failing closed here
means calling an unknown row safe. `5257adbe`.

**The sweep of all 275 found exactly one fault**, the known blank. The other
274 carry correct personalised copy. That lead was stopped against the
provider and reads `stopped`.

---

## 5. EVERY EXTERNAL-STOP CRITICAL NAMED CAMPAIGN 487 — ISSUE-027

The call site passed the module constant `PROVIDER_ID` (= 487) instead of
`watched`. One script runs nine times over nine campaigns.

    {"campaign": "487", "was": "active", "now": "paused",
     "emails_sent": 322, "leads": 332}

487 has 0 sends and 10 leads and was active throughout; those are 491's
figures. **A CRITICAL naming a campaign anybody can see is healthy reads as a
false alarm**, which is how the pause of the largest sending campaign went
unactioned into the morning. `d6a719c2`, and a correction is posted in
#resonate-notifications.

The existing tests could not catch it: they call the function with
`provider_id` and `watched` set to the same value, so the fixture agreed with
the bug. The new test reads the CALL SITE by `ast`.

---

## 6. THE GAG SHOULD NOT BE LIFTED YET, AND THE REASON IS IN ITS OWN TEXT

`CLIENT_CHANNEL_GAG` names **three** faults and says *"Nothing is posted to a
client channel until all three are live."* The standing order lists two of
them. **The third is not live:**

    replies.VERSION = rules-3        no RULE_HASH / RULES_HASH / FINGERPRINT

That is the reply-count source — the fault where the agent told a client
there were three positive replies when our own classifier says zero.
`positive_confirmed` is 0 and rules-4 is still blocked.

**What was fixed instead** (`c62c6309`, ISSUE-029): a gagged client question
reached **nobody**. The path wrote one log row, one stdout line, and
returned — no Slack post, no ticket, no notification. The gag stopped the
agent saying something **wrong** to a client and also stopped the operator
finding out the client had **asked**: 11 of 32 questions in the replay audit,
34% of real traffic, answered with silence that nothing reported. Now raises
`notify.CLIENT_QUESTION_UNANSWERED`, ACTION_REQUIRED, **internal only**.

The gag has still never been exercised in production: **zero `kind: gagged`
rows**, because no client question has been asked since it was set.

### 6.1 Measuring client latency requires lifting the gag in the harness

The replay resolves the real scope of each question, so a client question
hits the gag and returns in 0.0s. **Client-scope latency is therefore not
measurable while the gag is on** — which is exactly why the morning audit
could report `terms` as n/a 32 of 32.

The way to measure it is to set `slackconversation.CLIENT_CHANNEL_GAG = ""`
**inside the replay process only**. That is a measurement and not a deploy:
the constant is module-level, the running loop imports at start and does not
reload, and the replay posts nothing to Slack in any scope.

Run it from a directory that is **not** the Windows temp root: a stray
`inspect.py` sits there and shadows the standard library for anything
executed from it, which fails deep inside `argparse` with an error naming
neither. Use `PYTHONUTF8=1`; the console is cp1252 and replies carry Czech,
German and Polish out-of-office text.

---

## 7. THE REMOVE-LEAD VERB CANNOT BE BUILT — ISSUE-030

The operator approved it on 2026-09-24 assuming a route to hang it on.
`docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` enumerates **50 routes and none
of them detaches a lead from a campaign.**

**`DELETE /leads/{id}` is not the verb and must not be reached for.** It
deletes the lead outright, and these 91 are the **client's own** leads, months
old, members of their campaigns 327/328/352. Deleting them destroys client
data — considerably worse than leaving them attached.

Inferring `leads/remove-leads` from the `remove-sender-emails` symmetry is
what that document explicitly forbids: *"No route is inferred from naming
patterns alone."* And this module's history is three wrong conclusions that a
route did not exist, each reached by guessing a URL and reading the failure
as absence — so a probe can establish presence but never absence.

**What unblocks it:** a vendor documentation page for a lead-detach route, or
an independent implementation. The precedent for `remove-sender-emails` was
the vendor's own page plus an independent CLI.

Until then the foreign leads stay **stopped and attached**, which is safe (0
sendable rows, verified per lead) and unhygienic.

---

## 8. NOT STARTED, FROM THE STANDING ORDER

Supply in full (the 09-07 chain, the research-pack pilot, copy lint, batches,
LinkedIn, the AU ninth campaign and the 289 re-engagement leads). Learning in
full. Ledger write-back — **read §3 first, the provider cannot supply campaign
lifecycle events.** rules-4. Roles from Slack membership. Per-workspace
credentials. Client-two runbook. The env-mutation fix.

The LinkedIn lane has a prerequisite recorded on the slack-agent branch and
worth repeating: master carries a contradiction where `heyreach.stop_lead` is
enabled by one commit and asserted unsupported by two tests. The lane may not
enrol until the account-level stop is real in **both** directions; only one
direction has ever been measured.

---

## 9. THE PATTERN, AGAIN

**A predicate two witnesses share is one witness.** §4: the heartbeat and an
independent provider read agreed on `pending: 0` and both were reading the
same allowlist.

**An allowlist of "can still happen" fails toward calm.** The safe default is
to treat an unrecognised state as live.

**A measuring instrument can be broken in a way that looks exactly like the
thing it measures.** §1: four handoffs read a broken witness as a broken
estate.

**An alert that names the wrong object is worse than no alert**, because it
is actively dismissed rather than merely missed. §5.

**A guard that stops an output can also stop an input.** §6: the gag
swallowed the question along with the answer.

And the one that keeps recurring: **four of today's five findings were
invisible to a green suite, and every one of them was visible in the provider
or on the live estate.**


---

# ADDENDUM — 2026-09-24 afternoon

## A1. LANE FREEZE, operator, valid to 2026-10-01

This session is **lane 1, production: supply and quality only.** Engineering
allowed: what a push today needs (rules-4, the lint, the account stop) and
hard-stop fixes.

**Frozen, and to be carried into October:** ISSUE-025 / the remove-lead verb
(also blocked on ISSUE-030 regardless), the client-two runbook, ledger
write-back beyond what the status post needs, the learning doc beyond
Friday's scorecard, git hygiene beyond keeping the guard green, and the
reboot drill.

## A2. rules-4 SHIPPED — `1481a747`

`replies.VERSION` is `rules-4` and `replies.RULE_HASH` is
`rules-4+<12 hex>`, a digest **derived** from every `*_PATTERNS` group,
`RULES` with its order and confidences, and the two scalars that change a
verdict without touching a pattern. All six verdict writers stamp the hash;
a test asserts no seventh stamps `VERSION`.

`replyverdict.current_rule_identity()` now answers, exactly as its docstring
promised it would, **without being edited**. A fresh verdict is confirmable;
the stale `rules-3` row is not. This closes the gag's third fault. Phase D
item 4 still waits on the ledger write-back, which is frozen.

## A3. 491 — THE PROVIDER-SIDE HYPOTHESIS IS CLOSED, AND IT IS NEGATIVE

Checked at the operator's request before asking Productive again:

- **No auto-pause rule exists.** The campaign record carries no bounce
  threshold, no complaint threshold, no auto-pause flag and no
  warmup-protection field. `max_emails_per_day` and `max_new_leads_per_day`
  are **945, not zero**.
- **No mailbox is disconnected.** All 63 read `Connected`, `daily_limit` 15
  on every one, warmup enabled on every one. **This provider's sender schema
  has no last-error field at all** — that is a schema fact, not a null read.
- **Bounce cannot have tripped anything.** 491 itself is 1 in 322 (0.31%);
  across its 63 mailboxes lifetime 451 in 60,056 (0.75%); worst single
  mailbox 1.26%. All under the 1.5% rule. Unsubscribes 0.
- **No account or campaign event in a window spanning the pause.** 750
  events walked back to `2026-09-23T18:52:29Z`: EMAIL_SENT,
  EMAIL_SEND_FAILED, EMAIL_BOUNCED, LEAD_FIRST_CONTACTED, LEAD_REPLIED,
  BLACKLISTED_DOMAIN_ADDED. **Zero ACCOUNT, CAMPAIGN or PAUSE events.**
- The one event near the pause — `EMAIL_BOUNCED` at `22:13:59Z`, 92 seconds
  before it — belongs to **campaign 327, the client's own**, not ours.

**A NEGATIVE THAT IS NOT EVIDENCE, stated so nobody quotes it as one:** the
63 mailboxes all carry `updated_at` from *today* 10:00–11:00Z, overwritten
by activity from the client's campaigns that share the roster. That field
**cannot** speak to last night, and "no mailbox was updated in the window"
must not be reported as a finding. The event feed is what carries the
negative.

**Conclusion: no provider rule paused 491. It was a human in Productive.**

## A4. FOUR LIVE CREDENTIALS WERE IN `work/slack-history/`

14 distinct secret-shaped values across 3 files. By provider:

    Anthropic             2    none live
    OpenAI project key    1    none live
    OpenAI file handle    1    not a credential
    OpenRouter            1    STILL LIVE
    Slack bot token       2    1 of 2 STILL LIVE
    Slack app token       1    STILL LIVE
    unclassified          6    1 of 6 STILL LIVE

"Still live" means **the value is byte-identical to one in `config/.env`
today** — the only test that answers "must this be rotated", and it is a
stronger statement than a date. **Four need rotating and that is the
operator's action.**

Archive redacted in place, markers naming the provider so a reader knows
what was removed. The redactor verifies the **output** and does so **before**
touching disk — 2026-09-23 is why: a correct filter with the check in the
wrong place let one value through. It also refused its first run because it
was validating `_cursors.json` as JSONL, which is the abort behaving
correctly. Verified after writing: 0 of 14 values remain on disk.

`work/` is gitignored, so none of this was ever in git.

## A5. A NEW QUEUE STATUS APPEARED THE SAME DAY

The estate read shows `queued_for_sending: 1` — a status this codebase had
never seen. Under the allowlist it would have been filed as `already`, i.e.
contained. Under the denylist of §4 it counts as **pending**, so a blank in
that state would halt the campaign. It is not blank, and the fix was
vindicated within hours of landing.
