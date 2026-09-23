# Slack agent — handoff, 2026-09-23 evening

Supersedes `SLACK-AGENT-HANDOFF-2026-09-23-PM.md` and everything before it.
Written to the test CLAUDE.md sets: a fresh session on another machine, with
a clone and the secrets supplied separately, should be able to read this and
say what happened and what to do next.

**Branch `slack-agent` at `812b461f`**, pushed and verified against the
remote. Master is `342c832b`.

---

## 1. WHAT THE STACK LOOKS LIKE NOW — FIVE, AND NONE MERGED

    1  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D3.md   2afc2020 .. b428fea9
       the two-post follow-up offer
    2  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D4.md   0e8133a8 .. e9a6e848
       account_status, on the ledger, provider as periodic witness
    3  (no separate doc)                            94725a3d
       reply counting on both sides of production's one-row fix
    4  (no separate doc)                            2619f536
       weekly_report - accounts first, then emails
    5  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D5.md   ab421a5c .. 812b461f
       a synthetic second client; both-sided isolation; NEW

**Verified this session: none of the five is on master.** Only D2
(`edb9146f`, as `81e82ad8` at 12:16) is. `git merge-base --is-ancestor` on
each, not a reading of the log.

D5 is the only one of the five that is **not switched off waiting on
something**. D3 waits on its loop being started, D4 and the item-4 half of
the report wait on the write-back. D5 is tests plus one count fix and is
merge-ready on its own — though it is written on top of 3 and 4 and its
tests read `weekly_report` and `account_status`, so taking it alone means
taking those two with it.

### 1a. The ordering rule, unchanged

**When D3 merges, restart `slack_followup_loop.py` AND `slack_agent_loop.py`
in the same step.** D3 changes `OFFER_NOTICE` to promise two posts.

---

## 2. THE LIVE STATE, MEASURED RATHER THAN READ OFF A LOG

**`slack_agent_loop.py` is alive — pid 19580, started 13:56:10**, heartbeat
`work/heartbeat/slack-agent.json` at 14:45:40Z, connected, 28 answered.

**It is not running today's reply engine.** Files against that start time:

    scripts/slack_agent_loop.py   13:55:45   LOADED
    src/slackconversation.py      13:55:13   LOADED   <- the gag
    src/slackagenttools.py        14:24:41   NOT loaded  (ed26fb9b)
    src/replies.py                14:44:43   NOT loaded  (95bc71cb, 83a30652)

Production merged the cross-channel stop and a 210-line reply engine between
14:24 and 14:46, and the running agent has neither. **A merge is not a
deploy**; the loop imports at start and never reloads. It needs a restart,
and that is production's, not this session's.

**The gag is on.** `CLIENT_CHANNEL_GAG` is a set module constant checked at
the top of `respond()`, and `slackconversation.py` was loaded before the
process started, so it is live in the running process and not merely on
disk. Lifting it is an edit plus a restart, which is the friction its own
commit message argues for.

**`scripts/slack_followup_loop.py` has still never been started.** There is
no `work/heartbeat/slack-followup.json`.

---

## 3. THE TWO BLOCKERS BOTH STILL STAND, AND ONE GOT WORSE

`replies.VERSION` is **still `"rules-3"`**, on master and on disk.
`account.replies()` still projects `contact_key, channel, at, type,
classification, positive` — **no `classifier`, no `provider_event_id`**. So
this session's item 3 and Phase D item 4 are both still waiting, for exactly
the reasons `SLACK-AGENT-HANDOFF-2026-09-23-PM.md` §3b gave.

**And the rules moved twice more today underneath that unchanged version
string:**

    0b78fd68  13:18  rewrote the \bpass\b pattern; moved "we already use"
                     and "not a priority" out of NEGATIVE into OBJECTION
    83a30652  14:46  added QUESTION and SEND_INFO as classes, 210 lines

`VERSION` is `"rules-3"` through all of it — the same string the stale
Jennifer/Rose event carries.

### 3a. And the guard written for this did not fire, by construction

`tests/test_the_report_counts_accounts_before_emails.py` asserts
`replies.VERSION == "rules-3"` so that **bumping** it fails loudly and
somebody revisits the caveat.

It catches the bump. **It does not catch the drift**, which is the actual
fault. The rules have now changed twice under a caveat that says they have
not, and nothing went red. That is a weakness in `2619f536`, stated here
rather than left for somebody to find.

It also makes the third increment on this session's list the right shape
rather than a placeholder: **a test that a `rules-3` verdict is never
counted**, which fails on the stale data itself rather than on a version
string somebody has to remember to change.

---

## 4. WHAT THIS SESSION DELIVERED: D5

`docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D5.md` has the argument. In short:

- A synthetic second client (`alpha` / `bravo`) bound to its own test
  channel, on disk in a temp dir, in the live stores' real shapes.
- **The provider fake is a shared estate** holding both clients, because
  that is what the real EmailBison is. A partitioned fake would do the
  scoping's job for it.
- Every client tool **enumerated from the REGISTRY**, run for both, with
  cross-visibility asserted in both directions. 41 tests.
- **Attacked six ways.** The first run failed the FILE, not the code, twice:
  the slug-argument injection was never tested, and `sending_domains` was
  answering empty for its own domain. Both fixed; the attacks now move 11,
  7, 2, 2, 5 and 7 tests.
- **One gate turned out to be redundant** — removing the attestation
  `workspace` filter alone changes nothing, because the
  `senderidentity.email_accounts(slug)` join is what scopes that answer.
  Recorded rather than claimed as tested.

### 4a. The defect it found

**`sender_summary` could not read one of the two shapes its own campaign
store holds.** 164 sender entries carry `provider_account_id`, 159 carry
`account_id`, and 13 carry only `id` — on those, `str(a or b)` is the string
`"None"`, so every one of them counted as **one shared sending account**.

    productive   156 email sending accounts, one of them that bucket
    contactout     1 - and that 1 IS the bucket

Fixed by reading `id` third and counting identifier-less entries apart under
`sender_entries_without_an_id`. Nothing asserted those counts anywhere,
which is why it lived. **Productive 156 -> 158 and ContactOut 1 -> 2 when
this merges.** Fifth member of the shape-bug family.

---

## 5. THE NEXT INCREMENT IS THE WEEKLY REPORT, AND ITS PDF STEP HAS A
##    MEASURED OBSTACLE — READ THIS BEFORE STARTING IT

The operator's second increment: the parts item 3 lacks — **Monday 08:00
local schedule, a 07:30 preview into `#resonate-os` with a stop, the PDF via
`clientreport.py` from the report's data dict, and "@Resonate OS send me the
weekly report" in thread.**

The schedule, the preview and the thread trigger are ordinary work and are
not started. **The PDF step is not ordinary, and here is why, measured.**

`clientreport.build(data, meta)` lays out what it is given and renders a key
it cannot find as "not tracked". Its renderers read **33** keys. Compared
against what `weekly_report` returns:

    shared: meetings

**One key of thirty-three.** The PDF wants a sourcing-and-email funnel —
`domains_uploaded`, `contacts_found`, `contacts_verified`, `emails_pushed`,
`emails_delivered`, `replies`, `positive_replies`. `weekly_report` returns
`in_flight`, `engaged`, `replied`, `meetings`, `untouched`,
`do_not_contact`, `unanswerable`.

So feeding `weekly_report` into `build()` as it stands produces **the old
email-first document with the accounts figures dropped** — which undoes the
feature. "Every number this system has put in front of this client has been
an email number" is the sentence item 3 was written against.

### 5a. There IS an accounts section, and that is where the trap is

`_accounts` exists, is wired into `RENDERERS`, and already says the honest
thing when its key is missing: *"Account-level engagement is not assembled
for this report... this section has no data behind it rather than nothing to
report."*

Its vocabulary is **targeted / contacted / engaged / positive / multi_dm /
referrals**. The operator's is **in_flight / engaged / replied / meetings /
untouched / do_not_contact / unanswerable**.

**They share the word `engaged` and mean different things by it.** In the
PDF it is "at least one reply"; in `account_status` it is deliberately
*short of* a reply — D4 §3 made exactly this argument about not aliasing
`account.py`'s vocabulary onto the operator's. Mapping one onto the other
puts a different number under the same word **in a client's document**.

And **`unanswerable` has no home at all.** There is no tile for "we cannot
currently tell you", so the figure that `2619f536` insisted must never be
folded into `untouched` would be folded into silence by the PDF.

### 5b. So the PDF step needs a decision, not an adapter

Three ways, and the first is the only one that keeps the feature:

1. **Give `_accounts` the operator's vocabulary** — new tiles, including one
   that says how many accounts are unanswerable and why. `src/clientreport.py`
   is not on the forbidden list, so this is doable here; it is layout work in
   a 55KB module and it changes a document a client receives.
2. **Leave them separate** and have the Monday post carry the accounts
   answer in Slack while the PDF stays the email document it is. Honest, and
   it means two answers to one question, which is what the PM handoff already
   warned about.
3. Feed it as-is. **Do not.** See above.

**Nothing has been built for this increment.** The finding above is the
whole of it, and it is written down so the next session starts from a
measurement rather than rediscovering it.

---

## 6. INCREMENTS 3 AND 4 ARE NOT STARTED

For the record, and in the operator's own order:

    3. item 4 (positives to the client channel) only once the VERSION bump
       and the ledger write-back are live; until then A TEST THAT A rules-3
       VERDICT IS NEVER COUNTED.  See §3a - this is now the more valuable
       half, because the version guard provably does not catch the drift.
    4. items 5-8: catalogue second pass, briefing additions, "what are we
       working on" as a client answer, account status from the ledger as
       write-back lands, then CLIENT-PORTAL-DESIGN.md for review.

---

## 7. THE CROATIAN CORRECTION — STILL UNSENT, AND THE TEXT IS HERE

**It cannot be sent from here.** `#productive-resonate-outbound`
(`C0ADUMGQX8S`) is Slack Connect and the MCP token is refused with
`mcp_externally_shared_channel_restricted`. Only the app can post there.
**A person has to send it.** Reading the thread works; posting does not.

The unsent draft `Dr0C3XFG2CCR` lives in Bruno's thread
`1790061486.125249`. Drafts are not readable through the API, so the text
below was composed fresh from the verified facts rather than recovered — and
it is recorded here so it survives this session.

**The facts it rests on, each verified:** the 14:42 automatic report of
2026-09-22 marked **every one** of 69 domains `bez slanja u zadnjih 7 dana`
— confirmed by reading the thread; those mailboxes sent **494** that day;
the domain names, **159** mailboxes and **8** senders were correct; only the
recency markers were wrong; **the fault is fixed in production** — D2 merged
at 12:16 today and the loop was restarted onto it.

**Do not send D1 §5 verbatim instead.** Its flags were generated while
campaign 491 was still unreadable.

> Bok Bruno, ispravak na automatski izvještaj od 22.09. u 14:42.
>
> Uz svaku domenu u onom popisu pisalo je „bez slanja u zadnjih 7 dana" — i
> to je bilo netočno, za svih 69 domena. Istoga dana s tih je sandučića
> otišlo 494 maila.
>
> Sam popis je bio točan: domene, 159 sandučića i 8 pošiljatelja stoje kako
> su i napisani. Pogrešna je bila samo oznaka o slanju u zadnjih sedam dana.
>
> Uzrok je bio na našoj strani — sustav nije uspio pročitati kampanju iz koje
> se slalo, pa je svaku domenu prijavio kao neaktivnu. Ispravljeno je i
> popravak je u produkciji.
>
> Ispričavam se na zabuni.

**One check before sending:** the "494" is 2026-09-22's figure as it stood
this afternoon. If you send this after the watchers have read back further,
re-read it rather than trusting this line.

---

## 8. THE RULES THIS SESSION WORKED UNDER

Unchanged, restated by the operator at the start of this session, verified
for every commit above:

- Never merges to master and never pushes to it. Delivery is a merge-request
  doc in `docs/` plus one line in `#resonate-os` (`C0C3C6MDN9L`) — posted for
  D5 at 16:50 local.
- Never edits `config/.env`, `work/`, `src/providers/*` or
  `scripts/*_watch_loop.py`. **Verified**: this session's diff touches
  `src/slackagenttools.py`, one new test file and two docs. Production's
  `work/` was read — `campaigns.jsonl`, to count the sender shapes in §4a —
  and never written.
- A merge request per increment; a handoff before context runs out.
- Adversarial probes offline only. Every attack in §4 ran against a temp-dir
  estate and a fake provider; the only live reads were of production's
  `work/` files and one Slack thread read.

## 9. THE THING THIS SESSION LEARNED THAT IS NOT IN A DIFF

**An attack that moves one test is a finding about the test.** Two of the
six attacks in §4 moved exactly one test each on the first run, and both
times the instinct to call that "well defended" would have been wrong — it
meant the file had never asked the question. The slug-argument injection and
the empty `sending_domains` answer were both found that way, not by writing
more tests but by breaking the code and being unsatisfied with how little
complained.

**And the count that matters is the failure set by NAME.** The slack/client
suite runs 1,919 tests with 14 failures both with and without this session's
diff — the same 14, diffed by name. A count-to-count comparison would have
said the same thing and proved nothing.
