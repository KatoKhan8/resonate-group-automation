# Merge request — increment 4: the catalogue enumerated both ways, and a briefing that was over its own budget

**Branch `slack-agent` at `7fe619a3`.** One commit for this increment, on top
of increments 2 and 3 and the two fixes the operator asked for in between.

    30bf9920  the operator's own name, out of five tracked files
    7fe619a3  the briefing asked for six and got five, and the catalogue
              was enumerated one way                     <- THIS INCREMENT

---

## 0. THE SHORT VERSION

Two halves, and the first one had to be a bug fix before it could be an
addition:

| | |
|---|---|
| **The briefing was over its own call budget** | It asked for six readbacks against a cap of five. `monitors` was sixth and was dropped **every morning since the briefing was written**. |
| **Anything added would have been dropped too** | So "briefing additions" was impossible as stated — the increment would have looked done and changed nothing. |
| **The catalogue was enumerated in one direction** | Client-visible tools are registry-enumerated; internal-only tools were hand-typed in two files, four names in one and five in the other. |
| **The refusal was itself a disclosure** | `"a client channel may not call 'who_does_what'"` reached the model's material in a client channel, and `check_outbound` does not catch the paraphrase. |

---

## 1. THE BRIEFING HAS NEVER CARRIED A DEAD WATCHER

`scripts/slack_agent_briefing.py` `gather()` passed **six** calls to
`tools.run_all`, and `MAX_CALLS_PER_TURN = 5`. Measured, not read:

    next_actions     ok
    sends_today      ok
    batch_state      ok
    meetings_booked  ok
    promises         ok
    monitors         DROPPED -> dropped: over the 5-call budget

`run_all` does not truncate silently — it records the drop — so what the
model received every morning was the string
`{"_error": "dropped: over the 5-call budget"}` where the watcher health
should have been.

**`monitors` is "which watchers are beating and how long ago".** A dead
watcher is the most briefing-shaped fact there is. On the day this was found
it would have reported `bison-491` failing its inventory read a hundred
times, and a follow-up loop that had never been started — the two live
faults this session reported by hand instead.

### 1a. The budget was NOT raised, and that is the point

`MAX_CALLS_PER_TURN` is an anti-injection cap on a conversational **turn**.
The module header states the reasoning: a message can drive an agent into a
loop, and the call list on that path is chosen by a model reading text a
prospect wrote. Raising it would have removed the protection from the one
path that needs it.

A scheduled job is the other thing entirely: its call list is a literal in
this repository and nothing anyone says changes it. So
`slackagenttools.run_scheduled` takes no budget and **refuses any scope but
`INTERNAL`** — which is the whole safety argument, and is the first thing
the tests assert. `run_all` keeps its cap, and a test asserts that too, so
this cannot be read later as a general loosening.

### 1b. What was added, and why each one

Both were already registered tools that nobody had ever asked for:

- **`sender_roster`** — `docs/SLACK-AGENT-EXPECTATIONS.md` §4 item 2 is the
  operator's own instruction: lead with *"any sender over 1.5% bounce —
  early enough to matter, not at 2%"*. `sender_roster` carries
  `bounce_rate_percent` and the briefing had never asked for it. **This is
  the highest-value single addition and it required no new code**, only the
  budget fix that made a seventh call possible.
- **`weekly_plan`** — its own docstring cites this briefing by name: *"the
  07:15 briefing is supposed to already hold it when somebody asks"*. It did
  not.

### 1c. Two more defects in the same file

- **The prompt contradicted itself.** *"EXACTLY THREE SENTENCES, in this
  order"* followed by **four** numbered items. A rule the material cannot
  satisfy is a rule the model has to choose which half of to break.
- **`_plain()` answered a smaller question than it was asked.** The no-model
  fallback read `next_actions`, `sends_today` and `change_requests` — three
  of the six readbacks it gathered. `meetings_booked`, `promises` and
  `monitors` were fetched every morning and discarded, so **with no model
  configured the operator's promises requirement silently vanished**. A
  fallback that quietly narrows the question is worse than one that fails,
  because the output still looks like a briefing.

It now also names a **failed read** rather than letting it read as an
absence: a morning where `monitors` could not be read must not look like a
morning where every watcher was healthy.

### 1d. Three shapes guessed wrong, corrected before they shipped

The first draft of the fallback guessed the readbacks' shapes. All three
were wrong, and this is the same premise failure this session has been
auditing all day — caught here in my own code:

    monitors returns {"monitors": [...]}       not "watchers"
    rows carry age_seconds                     there is no `beating` flag
    bounce_rate_percent is ALREADY a percent   1.5 means 1.5%

The third is the dangerous one: a threshold of `0.015` compared against
`1.5` flags **every sender**, and the renderer would have printed `150%`.
The shapes are now taken off the real returns, and a test pins the
threshold's unit.

An undated heartbeat counts as **quiet**, which is `watchsink.stale`'s rule
and its reasoning: the question is whether silence may be read as unchanged,
and for a beat that cannot be read the answer is no.

---

## 2. THE CATALOGUE, ENUMERATED IN BOTH DIRECTIONS

`tests/test_two_clients_cannot_see_each_other.py` enumerates `REGISTRY` in
the **client** direction, and its own comment says it is written that way
"so tomorrow's tool is covered today".

**The internal direction was never enumerated.** The internal-only set is
hand-typed in two places — four names in `tests/test_slack_agent_scope.py`,
five in the isolation file — and an internal tool added tomorrow is covered
by neither.

Now enumerated from `REGISTRY`: every internal-only tool is never offered,
refused by name in **both** client workspaces, and absent from the rendered
catalogue string. Plus three smaller gaps of the same shape:

- **Registry row shape.** A three-tuple entry would raise at `run()`'s
  unpack in production rather than fail a test. Every entry is now asserted
  to be a 4-tuple with a callable, a non-empty description, one of the two
  known scope tuples, and `None`-or-string argument help.
- **`catalogue()`'s rendered text**, which is what the planner model
  actually reads. `for_scope` and `catalogue` are two views of one fact and
  could have disagreed silently; they are now asserted equal both ways, and
  the `(argument: …)` / `(no argument)` suffix is asserted against the
  registry row.
- **`UNBOUND` is refused at `run()`**, not merely offered an empty list.
  Those are different claims and only the weaker one was tested.

---

## 3. AND THE REFUSAL WAS ITSELF A DISCLOSURE

`run()` refuses a client channel with
`"a client channel may not call 'who_does_what'"`. `run_all` puts that
string into the result row, `render()` dumps it into the prompt and
`material_for` hands it to the model — so **in a client channel the model
was told the internal name of a tool it may not use.**

`check_outbound` does not catch the paraphrase. Measured against a real
client scope:

    "I'm not allowed to call who_does_what in this channel."   LEAKS
    "I can't run next_actions here."                           LEAKS
    "The monitors tool is internal only."                      LEAKS
    "I can't check promises for you."                          LEAKS
    "I can't see the credits balance."                         caught

Four of five, and the fifth only by accident — `credit` was already in
`INTERNAL_COMMERCIAL_TERMS` for an unrelated reason.

**The forbidden-terms list is the wrong place to fix this.** `monitors` and
`promises` are ordinary English; forbidding them would refuse a legitimate
answer that says "the system monitors your bounce rate", and a backstop that
fires on innocent prose gets widened until it fires on nothing.

So the fix is the one `for_client` already makes for numbers and campaign
labels: **correct the material, so the model has nothing wrong to repeat.**
A client turn's refusal row reads `"not available in this channel"`. The
internal wording is unchanged, where it is a useful thing to read in a log.

A test records that `check_outbound` still does not catch those sentences —
deliberately, so that if somebody later adds them to the forbidden terms,
that test goes red and they read the reasoning here first.

---

## 4. THE ATTACK THAT MOVED ZERO TESTS

Eleven attacks across the two new files. Ten behaved. **One moved nothing,
and it was the most important one.**

Flipping `monitors` from `_INTERNAL` to `_INTERNAL_CLIENT` — a one-token
change that hands a client channel Resonate's watcher health — moved **zero
tests**. Every assertion in the new file derives `INTERNAL_ONLY` *from*
`REGISTRY`, so a tool **moved** tomorrow simply shrinks the set and the
whole suite stays green.

A derived enumeration is self-maintaining for a tool **added** and blind to
a tool **moved**, which is exactly the regression that matters most. The
boundary is therefore also pinned by name — `EXPECTED_INTERNAL_ONLY`,
following this repository's own `TestKnownSets` convention, where a change
is a question for a human rather than a failure. **The same flip now moves
2.**

This is the third time today that "an attack that moves one test is a
finding about the test" has paid, and the first time it found the weakness
in a file written an hour earlier rather than in one already on master.

---

## 5. WHAT THIS DOES NOT DO

- **The briefing loop is still not supervised.** It is not in
  `scripts/start_monitors.py`'s `MONITORS` table, so it is not restarted on
  reboot and `--status` never reports it. Same class of gap that file's own
  comment records for `slack_followup_loop`. Adding it is a change to a
  supervisor this session did not otherwise touch; reported rather than
  taken.
- **`report_link` is still missing.** `docs/SLACK-AGENT-QUESTION-CATALOGUE.md`
  §4 ordered five tools; four are built and this is the fifth — "point at
  the monthly report rather than compose one". With `weeklyreportpdf` now
  existing (increment 2), it is smaller than it was.
- **Nothing was posted and nothing was sent.**

---

## 6. THE SUITE

45 new tests across the two files; all green. The affected set —
`test_the_catalogue_is_enumerated_in_both_directions`,
`test_the_briefing_asked_for_six_and_got_five`, `test_slack_agent_scope`,
`test_two_clients_cannot_see_each_other`,
`test_the_report_counts_accounts_before_emails`,
`test_a_rules_3_verdict_is_never_counted`,
`test_nothing_tracked_whether_a_promise_was_kept` — runs 194 tests with one
error, `test_a_whole_turn_in_a_client_channel_discards_a_leaking_answer`,
which is **in both the baseline and the pre-increment failure sets** and is
not this diff's.

The full by-name diff against the `9788ce2e` baseline is running. The
previous increment's diff, for reference, was **zero new failures** across
increments 2 and 3, the PDF-assertion fix and the PII fix:

    baseline  9788ce2e   11,917 tests   126 failures/errors
    final     30bf9920   12,011 tests   121 failures/errors
    NEW: 0      GONE: 5
