# Merge request — the adversarial sweep, and two checks that could not fail

**Branch `slack-agent` at `a8458d53`.** Overnight queue item 6, plus a
defect in the hygiene guard found while doing it.

    63200814  the replay harness (item 1, still running)
    98ec408a  the guard could not see a file until it was committed
    a8458d53  921 adversarial probes, and "Claude" walked straight through

---

## 1. THE LEAK, FOUND ON THE FIRST RUN

    "Claude is reviewing the branch."   reached a client channel

`slackscope.INTERNAL_WORKER_TERMS` held `"claude code"` and **not** bare
`"claude"` — while `qwen`, `glm` and `grok`, the other three model workers,
were all there. To a client this agent is Resonate OS; which model writes
its code is not their business.

**The trade-off is written where the term is.** `Claude` is also a French
given name, so an answer about a contact called Claude is now refused and
the client gets the fallback instead. That is the safe direction — a
refusal is visible and recoverable, a disclosure is not — and `TASK-249`
already establishes that this agent answers about an account and never
names a person, so the collision should not arise in practice.

---

## 2. WHAT IS BEING FUZZED IS NOT THE MODEL

There is no model in `tests/test_the_client_scope_under_attack.py`.
`check_outbound` and `tools.run` are, because those are the parts that must
hold **when the model says something wrong** — and a fuzz run whose result
depends on what a model happened to reply is a run that cannot be repeated.

Two sides, because a leak can happen at either:

| side | probes | what a pass means |
|---|---|---|
| **input** | 37 crafted arguments × 24 client tools = **888** | `ToolRefused` is correct; **any other exception is a failure** |
| **output** | 25 sentences | 20 must be refused, **5 must not be** |
| **overrides** | 8 | data, not instructions: no crash, no other workspace |

**921 probes**, against the 50 asked for.

The input set is deliberately nasty: Unicode RTL overrides, zero-width
joiners, NUL bytes, full-width `ＢＥＴＡ`, path traversal, SQL, `None`, empty
string, and 5,000 characters. A `ToolRefused` is the *correct* outcome for a
scope violation; an `AttributeError` is not, because it means an argument
reached code that did not expect it and the next one might reach further.

**The five that must NOT be refused are the control.** A backstop that
refused everything would pass all twenty leak assertions and leave the agent
useless, and there would be no test that could tell the difference.

---

## 3. THE KNOWN GAP IS RECORDED, NOT QUIETLY CLOSED

The four internal-tool paraphrases found earlier today —
*"I can't run next_actions here"*, *"The monitors tool is internal only"* —
**still pass `check_outbound`, and this file asserts that they do.**

They are ordinary English. Forbidding `monitors` would refuse "the system
monitors your bounce rate", and a backstop that fires on innocent prose gets
widened until it fires on nothing. The fix was made in the **material**
instead: `_refusal_text` no longer names the tool to a client, so the model
is never handed the name it would have to paraphrase — and a test here
asserts that too.

If somebody later adds those paraphrases to `CLIENT_FORBIDDEN_TERMS`, this
file goes red and they read why it was rejected before widening it.

---

## 4. AND A DEFECT IN THE GUARD THAT AUDITS EVERYTHING ELSE

Found the hard way, by me, an hour after writing the exemption into that
same file.

I wrote the final handoff — **a section of which describes the guard
catching a real name in a handoff** — ran `test_fixture_hygiene`, was told
13 of 13, and committed it carrying a real handle.

`tracked_files()` called `git ls-files`, which lists **only what is already
tracked**. A brand-new file is invisible until it is staged. So the green
was a statement about the *previous* state of the repository, and the
natural order of work — write the file, run the check, commit — is exactly
the order in which the check could not fail.

**Fixed** with `--others --exclude-standard`: files that are new and not
ignored, which is precisely what a `git add` would sweep up. `work/`, `out/`
and `config/suppress.local.txt` stay out, because `--exclude-standard`
honours `.gitignore` — the property the docstring already depended on.

**Proven, not argued.** With the guard green, an untracked file naming a
real person was dropped into `docs/`; the names assertion went red and named
it; removing the file returned it to green. Before the change, that file
would have passed. It adds nothing to the corpus today — there are zero
untracked non-ignored files — so it costs nothing now and closes the hole
permanently.

---

## 5. THE COUNT THAT MATTERS

This is the **sixth** instance today of a test that was green because it was
unfalsifiable, and the first where the unfalsifiable check was **the one
auditing all the others**:

    assertNotIn(b"...") against a Flate-compressed PDF
    schedule tests building `now` from the zone they were pinning
    a version guard that catches a BUMP but not the DRIFT
    an internal-tool enumeration derived from the registry it polices
    an override test whose sentence never opened with a compose verb
    a PII guard that could not see a file until it was committed

---

## 6. THE SUITE

`tests/test_fixture_hygiene`: **13 of 13**. 160 tests across the six
affected modules, with the single pre-existing error
(`test_a_whole_turn_in_a_client_channel_discards_a_leaking_answer`, caused
by `CLIENT_CHANNEL_GAG`) that is in every failure set since the baseline.

The full by-name diff runs after item 1's replay finishes, to avoid two
suites binding loopback at once.
