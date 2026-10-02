# Five tests contradict decision 2, and they were not patched

**Branch** `task-one-os-authority` · **base** `4222ee88` · **2026-10-02**

Decision 2, as given: *"STOP na mid-sequence samo ako je sekvenca na OS kampanji
po tom autoritetu."* Implemented in `collision.account_policy`. Five tests that
pass on the base commit now fail, and **none of them has been edited.** Three of
them assert the OLD rule as correct on purpose, and two of those rest on real
production observations rather than invented fixtures. Weakening or rewriting a
guard to make a verdict green is the one move this repository does not allow, so
the change ships with them red and the decision is yours.

The other two are arguably fixture drift and could be updated faithfully, but
they are listed here rather than quietly fixed, because the line between "the
fixture happened to use a non-OS id" and "the fixture chose a non-OS id to make
exactly this point" is a judgement about intent, not a fact about code.

**Nothing here is a reason to revert.** Every one of the five fails in the same
direction - an account that used to be blocked is now sendable - which is the
intended effect of the decision. The question is only whether each of these five
accounts SHOULD become sendable.

---

## The measurement first, so the list is not confused with noise

Baseline taken at `00b49197` (this branch, task 1 only, task 2 absent) before
attributing anything:

| module | at `00b49197` | after task 2 | caused by task 2 |
|---|---|---|---|
| `test_the_account_is_not_cold_and_we_would_have_said_it_was` | OK | 1 failure | yes |
| `test_a_reply_counts_even_when_the_counter_says_zero` | OK | 1 failure | yes |
| `test_our_own_staging_is_not_their_history` | OK | 1 failure | yes |
| `test_staging_refuses_colliding_contacts` | OK | 2 failures | yes |
| `test_heyreachfactory_ensure_leads` | **4F / 13E** | 4F / 13E | **no, pre-existing** |
| `test_the_second_activation_at_an_account_is_refused` | **3F** | 3F | **no, pre-existing** |

The last two rows are the reason this table exists. Both were predicted to break
and both were **already red before this change** - they are in the master
221-name baseline of 2026-10-02. Reporting them as regressions would have been
wrong, and a count-based comparison would not have caught the difference.

Two things that were predicted to break and did **not**, because the
unidentifiable-sequence arm fails closed:

- `test_no_write_happens_without_every_gate::TheAccountIsAskedToo` - the real
  `executionguard` gate 4. Its fixture carries `anyone_in_sequence: True` with
  `"people": []`, so no campaign can be named, so the arm STOPs. **78 tests, OK.**
- `test_heyreachfactory_ensure_leads`'s collision tests, same shape.

That is the fail-closed rule earning its place on the first day it existed.

---

## GROUP A - assert the old rule deliberately. Do not patch without your word.

### A1. `test_our_own_staging_is_not_their_history.py::TheVerdictsThatMustNotMove::test_a_colleague_mid_sequence_still_stops_the_account`

The class is named `TheVerdictsThatMustNotMove` and its docstring reads *"Four
HOLDs and a STOP that this change is not allowed to touch. Each one is the
reason the account gate exists at all."* The fixture uses `THEIRS = 352`,
commented *"one of the client's own, from before we existed"*. The test name says
*still stops*.

- **For leaving it red:** this is decision 2 stated exactly, with the opposite
  verdict. 352 is one of the four you declared internal on 2026-10-01. If
  membership in 352 is not our collision, this test is now asserting something
  you have overruled, and it should be rewritten to say so.
- **Against:** the class was written to pin verdicts against *a different*
  change, and whoever wrote it believed a colleague being emailed right now was
  a fact about the account regardless of who was emailing them. That belief is
  not obviously wrong, and the commit that introduced it treated it as the
  reason the gate exists.

### A2. `test_staging_refuses_colliding_contacts.py::test_in_sequence_is_refused_by_name`

Docstring: *"A contact mid-sequence in the client's estate is REFUSED. 199963
was in_sequence in campaign 352 - being emailed RIGHT NOW."* It drives the real
`bisonfactory.stage` path.

- **For leaving it red:** same as A1, and the refusal is now gone by design.
- **Against, and this is the strongest argument in the document:** it names a
  REAL lead (199963) in a REAL campaign, and the thing it prevents is staging a
  person into a Resonate campaign while the client is actively emailing that
  same person. That is a deliverability and client-relationship problem that
  does not care whose campaign it is. Decision 2 was argued from *attribution*
  (our measured activity, legacy_touched); this test is about *two of us
  emailing one person in the same week*. Those may genuinely be two different
  questions, and decision 2 may not have been meant to answer this one.

### A3. `test_staging_refuses_colliding_contacts.py::test_the_nine_real_cases_as_a_fixture`

Same 352 seed inside a nine-case fixture drawn from real observations. The
overall refusal still fires (the `stopped` and `bounced` cases still HOLD), but
the in-sequence record `rec-seq-c1` is no longer among the refused. Same
arguments as A2.

---

## GROUP B - probably fixture drift, still not patched

### B1. `test_the_account_is_not_cold_and_we_would_have_said_it_was.py::ThePolicyKeepsTheDistinctions::test_somebody_mid_sequence_stops_it`

Fixture campaign id is `1` - a placeholder, not a declaration. The test's intent
is that the mid-sequence distinction exists at all.

- **Faithful repair:** change the fixture id to an OS campaign (487) and the
  test proves its original point under the new rule. One line.
- **Why it is here anyway:** `1` is not in the authority, so under the new rule
  the account is correctly sendable. If you would rather this test pin the
  *non*-OS case, the fix is the opposite one - rename it and assert ALLOW.

### B2. `test_a_reply_counts_even_when_the_counter_says_zero.py::test_mid_sequence_still_outranks_everything`

Fixture id is `274`, the module's default, chosen for that module's
`replied`/`replies: 0` story rather than to make an ownership point. The test is
about PRECEDENCE: mid-sequence outranks the `stopped` HOLD. It now returns HOLD.

- **Faithful repair:** use an OS id; precedence is still proven.
- **Why it is here anyway:** 274 is one of your four internal campaigns, so the
  new verdict is the one decision 2 asks for. The test name would then be
  wrong - mid-sequence no longer outranks everything, it outranks everything
  *when the sequence is ours*.

---

## One standing rule now disagrees with another, and I did not touch it

`collision.classify` - your five-step LEAD KLASIFIKACIJA of 2026-10-01, step 2 -
holds a lead for **anybody's** live campaign, ownership-blind on purpose.
`tests/test_a_lead_is_classified_before_it_is_contacted.py` pins it:
`test_an_active_campaign_of_ours_also_puts_the_lead_on_hold`, whose docstring
says *"Step 2 says ANYONE, so ownership must not change the outcome."*

After this change the two gates answer on opposite principles: `account_policy`
asks whose campaign it is, `classify` refuses to. They are not the same
question - one is an ACCOUNT-level collision check, the other a PERSON-level
classification - and decision 2 named only `account_policy`, so `classify` is
untouched and its test still passes. **If step 2 should move too, that is a
separate decision and a separate commit.** Flagging it because the inconsistency
is now real and will be rediscovered by whoever reads both gates.

---

## What is being asked

1. For A1-A3: do these accounts become sendable? If yes, the three tests should
   be rewritten to assert ALLOW and renamed. If the A2/A3 concern - two senders
   emailing one person in the same week - is a separate guard you want kept,
   then `account_policy` is the wrong place for it and it needs its own rule
   that does not depend on ownership.
2. For B1-B2: confirm these are fixture drift and the ids may be updated to OS
   campaigns, preserving each test's original point.
