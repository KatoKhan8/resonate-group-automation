# Merge request — Phase C3: the three decisions, built

**For the production session.** Branch `slack-agent` at `ecb93a9f`, pushed.
Not merged, not pushed to master.

Four commits: one per decision, plus the follow-up on variant status.

    5025feb6  meetings_booked — the number the contract runs on
    0e376be1  the promise scan — 53 promises, now checked
    1f840c4f  campaign_copy — nobody ever asked for the shape
    ecb93a9f  the variant visibility axis (your follow-up decision)

`docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C2.md` covers increments 3 to 6,
which are also still unmerged. **The branch now carries nine commits
master does not have** — C2's five and these four.

## WHAT THIS TOUCHES THAT IS YOURS

    nothing

No `config/.env`, no `work/`, no `src/providers/*`, no `*_watch_loop.py`.
`scripts/digest_loop.py` is untouched — see §1e for the one line you may
want to add to the digest.

New: `src/slackmeetings.py`, `src/slackpromises.py`, and three test files.
Modified: `src/slackagenttools.py`, `src/slackconversation.py`,
`src/variants.py` (additive — see §3c), `scripts/slack_agent_briefing.py`,
`tests/test_slack_agent_cannot_act.py`, `tests/test_invariants.py`,
`tests/test_what_a_client_is_shown.py`.

`src/variants.py` is the one file here that is not slack-agent code.
Checked first: no branch ahead of master touches it. The change is two
constants, one derived reader, one defaulted keyword, one line in
`apply_to_step` and one `validate` check — no existing filter, allocation
rule or status value changed, and the 218 variant-engine tests pass
untouched.

**Still true from C2 §0: the running agent loop is executing pre-merge
code.** It started 13:18:29 and has never been restarted. None of this
does anything until it is.

---

# 1. MEETINGS BOOKED

Your design, built as specified. First on the catalogue's build list: 93
questions, and the single most-asked number nothing could produce.

    @Resonate OS meeting booked <domain> <date>
    @Resonate OS meeting booked acme.com 24.09.2026 with CFO
    @Resonate OS meeting booked acme.com today for productive

## 1a. Sources never merge, and the return type is what enforces it

`counts()` returns `{source: n}`. **There is no function in the module that
hands back a bare number.** `total_across()` reports a sum only alongside
the list of sources it spans, with a note saying so. The day Calendly is
wired it becomes a second key and every reader sees two numbers — rather
than one number that grew overnight and nobody can now reconstruct.

That is your rule expressed as a type rather than as a comment somebody has
to remember while adding the second source.

## 1b. A question never writes a row

*"how many meetings booked this week"* is the far more common message and
arrives in almost the same words. An asking-shaped message is rejected
before the grammar is tried. The recogniser is a **regex, not the model**:
a Slack message cannot talk its way into a row by being persuasive, only by
being in the exact shape.

## 1c. The check is on the person, not only the room

`scope.is_internal` is true for anybody speaking in one of our channels.
The ledger also checks the speaker against `slackscope.internal_users()`,
because the number the contract is measured by is not one the other party
writes. A client channel cannot reach it at all.

## 1d. Attribution is refused rather than guessed

Both kinds of uncertainty refuse: no client holds the domain, or more than
one does. A meeting filed against the wrong client is a figure in that
client's own answer that was never theirs, and it surfaces — if ever — when
somebody quotes it back.

Every refusal names the phrase to type instead (`... for <workspace>`),
because a hand-fed ledger nobody can feed is an empty one. **`for <x>` is
only read as a workspace when it names a real one** — "with the head of ops
for EMEA" is a role containing the word.

A duplicate (same workspace, domain, date) is refused and the first row
named, so the count cannot double when two people record one meeting.

## 1e. Where the counts appear — and the one line that is yours

Done here: the `meetings_booked` tool (internal and client), the weekly
plan, and the 07:15 briefing.

**The digest is yours.** `scripts/digest_loop.py` and `src/digest.py` are
production-session files and this session does not edit them. One call adds
it:

    from src import slackmeetings
    slackmeetings.counts(workspace=<slug>, since=<iso date>)   # {source: n}

Per-domain detail is resolved from the **scope**, never from the argument,
so no phrasing in a client channel reaches another client's rows.

## 1f. What it says about itself

> this is a ledger people write to by hand. It is as complete as what has
> been recorded, which is not the same as what happened — an absent meeting
> is an unrecorded one, not a meeting that did not occur.

That sentence is in every answer. A hand-fed number that presents itself as
a measurement is worse than no number.

## 1g. Two things left deliberately undone

- **No correction verb.** The journal is append-only with latest-row-per-id
  (the shape `slackrequests` and `slackfollowup` use), so `meeting removed
  <id>` is a small addition — but you did not ask for one and a delete verb
  on a commercial number deserves your say-so. Until then a wrong row is
  corrected by editing the journal.
- **The date is echoed, not validated.** `03/04` is read in European order
  because that is how the people typing it write dates. The confirmation
  names the ISO date it recorded and asks you to correct it if it read it
  wrong — a parser that guesses is only safe when the guess is visible.

---

# 2. THE PROMISE SCAN

Your definition, implemented verbatim in `src/slackpromises.py`. The
expectations doc called this the highest-value thing the history suggests
and the one thing it could not build, because it needed exactly this
decision.

## 2a. Four states, and only one of them is a reproach

    delivered   something arrived in the thread after it
    open        the stated time has passed and nothing did
    due         a stated time that has not arrived yet
    undated     a promise with no time in it

Only `open` reaches the briefing. **`undated` is never called late** —
calling a promise late when nobody said when is how a monitor teaches its
readers to skip it, and a section people skip is worse than no section.

## 2b. "danas ili sutra" is judged on sutra

The later of two stated times wins. One false alarm costs more attention
than one missed promise — and the promise this whole scan was written about
is phrased exactly that way.

## 2c. The evidence is named, not collapsed

A file, a link, a list of 3+ lines, an explicit delivery word, or the
system's own artifact — the answer says **which**, and how many minutes it
took. The domain-list promise was "kept" in 119 minutes with the wrong
artefact; a scan that only said `delivered` would have said it about that
one too. Naming the evidence is what lets a person disagree with it.

A delivery is ours or the system's. A client posting a link in the thread
is not us keeping a promise.

## 2d. An acknowledgement is deliberately not a promise

"momenat, gledam" and "on it, dodala task!" owe nobody an artefact. The
recogniser is narrower than forward-looking language on purpose: a briefing
full of things nobody owes anybody is a briefing people stop reading.
Questions containing the verb ("možeš poslati popis?") are never promises.

## 2e. An empty history is not a clean week

The scan reads `work/slack-history/`, which `scripts/slack_history.py
--read` fills and which is **not currently being refreshed** — that loop is
still handed over and not running. So the summary distinguishes the two
cases explicitly and names the command:

> no Slack history has been pulled, so this is not a clean week — it is an
> empty file. Run `py -3 scripts/slack_history.py --read`.

### The monitor, for you to start

**Your decision: this goes to the production session as a monitor, and this
session does not run it.** The scan is correct and empty until it does.

    py -3 -u scripts/slack_history.py --read          # one pull
    py -3 -u scripts/slack_history.py --loop          # as a monitor

`--loop` is written and has never been started — it is on the open list in
every handoff since the 22nd. It writes only `work/slack-history/` and
reads only rooms the bot is already in; unbound shared channels are skipped
by name and listed, so no unattributable client room is pulled.

**One thing to know before you start it.** The raw history contains the
plaintext GoDaddy password, payroll and personal phone numbers — the
standing exposure already on your list — and a scheduled pull puts a copy
of it on disk on a schedule. `work/` is gitignored and uncommitted. The
promise scan reads message shape only and never quotes a body into an
answer, but the file on disk is the file on disk.

## 2f. Clients never see it — structurally

Registered `_INTERNAL`, so `run` refuses it by name in a client channel and
`for_scope` never lists it. There is no filtering step to get wrong.

## 2g. One consequence of the definition, taken literally

Delivery counts **in the promise's own thread**. A promise made at channel
level and answered by a separate channel message will read as `open`. That
is your definition rather than a widening of it — "anything the same person
said later in the channel" would close promises on unrelated messages. If
the briefing shows false opens of that shape, the fix is a decision about
the window, not a patch.

---

# 3. CAMPAIGN COPY

Your scope decision, built. 110 questions about cadence and copy, against a
tool that could only give the sequence's shape.

## 3a. The approved set is the filter, and it excludes history for free

The walk is over **approvals, not over steps**: there is no path in this
function that reads a step without first asking `approval.is_approved`,
which compares the signature against the step's *current* words.

So a revoked approval is gone, and an edited step drops out the moment a
word changes. "Not history" is enforced without anything having to know
what history is. Your second named test is asserted three ways: never
approved, approved-then-edited, and revoked.

## 3b. Client A cannot see client B's copy

Your first named test, with a **positive control beside every absence
assertion** — beta's own channel does see beta's words, and alpha's answer
does carry alpha's. "The other client's copy is absent" passes by accident
against an empty fixture, and that is the shape of test this repository has
been caught by before.

## 3c. Testing / winner / retired — your follow-up decision, built

`ecb93a9f`. A client sees a **winner** as part of the cadence and never a
`testing` or `retired` one. Internal sees all three, each labelled. No
variant vocabulary and no approver's name reach a client channel.

**A second axis, not a renaming of the first.** `variants.status` decides
ALLOCATION — who receives which arm — and `even_allocation`,
`experiment_of`, `shifted_allocation` and `validate` all read it. Rewriting
its vocabulary would let a visibility decision change which message a real
person gets. So `client_status` is its own field, and a variant is `active`
for sending and `testing` for showing, which is the ordinary state.

    variants.TESTING / VARIANT_WINNER / RETIRED
    variants.client_status(entry)    testing | winner | retired, never None
    variants.client_may_see(entry)   winner only
    apply_to_step()                  writes `variant_client_status` onto
                                     the step, so the readers of a step do
                                     not each re-derive it

### The migration note

**Nothing to backfill, and no client answer changes on merge.**
`client_status` is DERIVED, not required:

    an explicit `client_status`   that, when it is one of the three
    `status` is `retired`         retired — a retired arm is retired on
                                  both axes; two truths about one thing
                                  would be worse than one
    anything else                 testing

So every variant written before today reads as `testing` and is withheld,
which is precisely how it behaved before the field existed. Promoting a
winner is a deliberate act, one variant at a time, by setting
`client_status: "winner"` on the entry in the cadence node.

**Testing is the default and the default is the withheld one.** An unknown
or typo'd value reads as `testing`, so the failure mode is copy staying
private rather than copy under test quoted to a customer as settled. But
`variants.validate` **blocks** an unrecognised value — a `winnner` that
silently meant `testing` would be a decision you made that the system
quietly did not carry out, so it fails loudly instead.

### And the winner is not labelled a winner

It arrives in a client answer as ordinary cadence copy, with no experiment
vocabulary attached: "winner" implies the losers they are not being shown.
Withheld messages are still counted, so an answer showing one of three does
not read as the whole set.

218 variant-engine tests still green, unchanged.

## 3d. Merge-resolved copy names a prospect — CONFIRMED, STAYS AS JUDGED

The copy is merge-resolved, so a body can carry a recipient's first name
and company — *"Hi Ivana, one line about margins."* **"As sent" cannot be
satisfied any other way.** A client seeing their own outreach to their own
prospect in their own channel is the rule `lead_lookup` already runs on,
and addresses are still stripped by the answer guard. Confirmed by the
operator on 2026-09-22: it stays as judged.

## 3e. One step carries several texts

Because the copy is personalised per recipient. Identical texts collapse to
one row with a recipient count, the list is capped at five per step, and
the cap says how many it hid. A step with three hundred recipients does not
become a three-hundred-message answer.

---

# 4. TESTS

    tests/test_the_number_the_contract_runs_on.py              25  NEW
    tests/test_nothing_tracked_whether_a_promise_was_kept.py   27  NEW
    tests/test_nobody_ever_asked_for_the_shape.py              36  NEW

**591 slack tests, green**, run together and each file alone, plus 218
variant-engine tests unchanged and green.
`tests/test_invariants.py` keeps its one pre-existing failure (two modules
importing `ProviderError` by name), which predates this branch.

## The cannot-act guarantee covers the write

`src/slackmeetings.py` is the first module the agent writes on somebody's
instruction, so it is on `AGENT_SOURCES` and its journal is in the
"writes only inside `work/`" assertion, alongside the follow-up journal
which was also missing from it. `src/slackpromises.py` is there too.

It is also in `tests/test_invariants.py`'s self-writer list, where the
production-write barrier is proved by **driving the writer for real**
rather than by grepping for the guard — the distinction that file's own
docstring draws, and the reason a module with two append sites once passed
with the guard deleted from one.

---

# 5. STILL YOURS

Carried forward and unchanged:

- **Restart `slack_agent_loop.py`.** It is running pre-merge code.
- **Start `slack_followup_loop.py --interval 60`**, or the follow-up offer
  stays correctly switched off.
- **Fill in `slack.roles`** for Productive.
- Seat ownership; `hr-`/`li-` reconciliation; the plaintext GoDaddy
  password in Slack history; the eight unbound shared channels;
  `src/providers/slack.py` `thread_parent`.

New:

- **Start `scripts/slack_history.py --loop` as a monitor** (§2e). The
  promise scan is correct and empty without it, and it has never been
  started. Read the note there about what the raw history contains.
- **The digest line** in §1e, if you want meeting counts there.
- **Promote a winner** when there is one (§3c). Until then every variant
  reads as `testing` and no client sees one, which is the pre-merge
  behaviour.
- **A correction verb for the meetings ledger**, if you want one.

## One thing found on the way past, and not ours to fix

`tests/test_the_cadence_the_client_chose_is_the_one_that_runs.py` and
`tests/test_the_cadence_reacts_to_what_the_prospect_did.py` both fail:
`productive_li_heavy_v1` is expected to carry **6 LinkedIn steps and has
5**, total 10 rather than 11.

**Verified pre-existing.** They fail identically against the pristine
`src/variants.py` from before this branch touched it, so nothing here
caused it. It reads as drift between the client config and the tests'
expectation. It may be this worktree's own `work/clients/productive`
rather than production's, so it is worth one check on master before
anybody edits a cadence on the strength of it.
