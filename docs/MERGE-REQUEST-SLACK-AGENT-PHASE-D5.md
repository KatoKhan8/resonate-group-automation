# Merge request — Phase D5: a second client, and the assertions that were half a test

**For the production session.** Branch `slack-agent` at `ab421a5c`, pushed
and verified against the remote. Not merged, not pushed to master.

Phase D **item 6**, multi-workspace readiness, as the operator specified it
on 2026-09-23: *"Synthetic second client bound to a test channel: every
client tool, the accounts-first answers and the weekly report run for both
workspaces; zero cross-visibility asserted from both sides, not one. This is
the proof for the second real client."*

**Fifth in the stack.** It sits on D3 (`b428fea9`), D4 (`e9a6e848`),
`94725a3d` and `2619f536`, none of which are merged. It does not depend on
any of them to be correct, but it was written on top of them and the tests
read `weekly_report` and `account_status`, which arrive in 4 and 2.

## 0. WHAT THIS TOUCHES THAT IS YOURS

    nothing

No `config/.env`, no `work/`, no `src/providers/*`, no `*_watch_loop.py`.
Production's `work/` was read — the campaign store, to count sender shapes —
and never written.

    src/slackagenttools.py    sender_summary, _sending_account_id  (§4)
    tests/test_two_clients_cannot_see_each_other.py   NEW, 41 tests

---

## 1. WHAT WAS ACTUALLY WRONG WITH THE OLD ASSERTIONS

They were not wrong. They were **half a test**, and the half that was
missing is the half that can fail.

`account_status` asserts that another client's domain and a domain nobody
has return the identical note, word for word, because the difference between
them is the leak. `weekly_report`, `lead_counts` and `lead_in_campaign` have
the same shape. Every one of those was written against a fixture with **one**
real workspace in it, so "the other client" was a slug with nothing behind
it.

**A tool that read the entire estate would have passed all of them**, because
there was nothing in the estate but the asker's own rows.

So this increment furnishes both sides — records, campaigns, senders,
mailboxes, ownership attestations, replies, approved copy and a bound
channel each — and asks every question in both directions. A leak now has
something to carry.

---

## 2. THE FIXTURE IS A SHARED PROVIDER ESTATE, AND THAT IS THE DESIGN

The fake `bison` holds **both** clients' campaigns, **both** clients'
mailboxes, and **one** reply feed with both clients' replies in it. It
answers `find_lead_by_email` for either client's address without hesitation.

That is what the real EmailBison is: one estate with every client in it.

**A fake partitioned per client would prove nothing** — the partition would
be doing the work the scoping is supposed to do, and the test would pass on a
tool that reads everything.

Nothing else is mocked. The workspaces, queue, campaigns and senders are real
files in a temp directory written in the live store's shapes; the scope is
resolved from a channel id by the real `slackscope.resolve`; the tools are
called through the real `tools.run`. The one other pin is the knowledge pack,
and its `provider_campaign_ids` are real per side because `_campaign_is_visible`
reads them and that gate is under test.

### 2a. The tool list is enumerated, not listed

`for_scope(scope)` decides which tools each side is asked, so **a client tool
added tomorrow is covered the day it is added** rather than the day somebody
remembers this file exists.

---

## 3. ATTACKED SIX WAYS, AND TWO OF THEM CHANGED THE FILE

Each attack removes one piece of the scoping and re-runs all 41:

    records ignore the workspace                    11 fail
    the workspace argument is honoured in a channel  7
    every campaign is visible to every channel       2
    campaign rows ignore the workspace               2
    the sender roster ignores the workspace          5
    the attestation gate AND the account join        7

**The first run of the attacks failed the file, not the code.** Attacks 2 and
4 moved only one test each, and both times the reason was a gap here:

- The argument-taking tools were never asked about the other client **by
  workspace slug** — which is the most obvious injection there is, "show me
  the other client's summary". `workspace_summary`, `cadence_detail` and
  `sender_summary` take one. Added; attack 2 went 1 → 7.
- `sending_domains` and `sender_roster` were answering **empty for their own
  domain**, because the fixture had the person but not the mailbox or the
  ownership attestation. Every isolation assertion passed on an answer that
  said nothing. Added; attack 4 went 1 → 2 plus a substance test.

### 3a. One gate is redundant, and it is written down rather than claimed

Removing the `attestation.get("workspace") != slug` filter **alone changes
nothing** — all 41 still pass. The join through
`senderidentity.email_accounts(slug)` is what actually scopes that answer:
the other client's `account_id` is not in the asker's account map, so the
row is dropped.

Two gates is good. **Claiming this file tests both would be false**, so it is
recorded here instead. Removing both together leaks, and is caught on both
sides.

### 3b. The control, without which none of it counts

`test_each_side_really_does_see_its_own` requires each client's **own**
markers to appear across its own catalogue.

Isolation achieved by emptiness is not isolation — it is the
confidently-empty failure this project has hit four times, wearing a security
property's colours. That control is what caught `sending_domains` above, and
a second one (`test_the_answers_that_could_be_empty_are_not`) checks the four
no-argument tools individually, because a marker can otherwise get into the
blob just by being echoed back from the argument.

---

## 4. THE DEFECT THIS FOUND, AND IT IS IN A CLIENT-FACING COUNT

**`sender_summary` could not read one of the two shapes its own store holds.**

    for entry in senders.get("email") or []:
        email.add(str(entry.get("provider_account_id")
                      or entry.get("account_id")))

Counted on the live campaign store, 2026-09-23:

    provider_account_id     164 entries
    account_id              159
    NEITHER - only `id`      13    {"id": "bison-a", "daily_limit": 50}

On those thirteen the expression is the **string `"None"`**, and `str()`
makes it a legitimate-looking set member. They did not go uncounted, which
would at least have been visible as a smaller number. **They counted as one
sending account, shared between them.**

Live, before the fix:

    productive   156 email sending accounts — one of which is the "None"
                 bucket standing for 3 real entries
    contactout     1 — and that 1 IS the bucket. Both of its email sender
                   entries carry only `id`, so the answer to "how many
                   senders are sending for us" was the number of shapes
                   this function could not read.

ContactOut has no `slack.agent_channel` today, so no client has been told
this. An operator asking internally has been.

The fix reads `id` as a third fallback and returns `None` for an entry with
no identifier at all, so the caller counts those apart under
`sender_entries_without_an_id` rather than inventing a distinct account out
of a missing field. **`None` is not a count of one**, which is the same
argument `_ledger_carries_sends` makes about its witness and `2619f536`
makes about `unanswerable`.

**Nothing asserted these counts anywhere.** That is why it survived. Six
tests do now, and with the old read restored exactly those six fail and
nothing else — so it is those tests holding the property and not a
neighbour.

Same family as the four shape bugs in D4 §4: a field read that knew one of
the store's shapes. That is now five.

---

## 5. THE TESTS

**41.** The ones that matter:

    1  the binding resolves both ways, and BOTH slugs were known when
       each scope resolved - if only one existed the backstop's slug
       check would pass vacuously and everything below is worth nothing
    2  every client tool, enumerated from the registry, runs for both
    3  no client tool's readback carries ANY of the other's markers,
       either direction, including through `run_all`
    4  asking each channel with the OTHER client's own argument
    5  a rival's campaign id and an invented one are refused in the
       SAME WORDS - otherwise trying ids is a way to learn which exist
    6  a rival account and a stranger's read word for word, both ways,
       for account_status / account_lookup / lead_lookup /
       lead_in_campaign - and a CONTROL that its own account does not
    7  the rollup, the reply ledger and the weekly report per workspace
    8  the outbound backstop, both ways, including with the store
       emptied after resolution

**`lead_in_campaign` is the sharp one.** The shared fake answers
`find_lead_by_email` for the other client's address, so the provider has
already said yes; the campaign scoping has to do the work afterwards, and the
answer still has to read like a stranger's.

Suite: **1,919 tests** over the slack and client files. 14 failures, and the
failure set is **identical by name** to the same run with this diff reverted.
All 14 are in the 71/35 infra baseline and none is touched here. Diffed by
name rather than by count, per the standing rule.

---

## 6. WHAT THIS DOES AND DOES NOT PROVE ABOUT A SECOND REAL CLIENT

**Proves:** the pinning holds from both sides when both sides have data; the
argument never widens a scope; the refusals do not distinguish a rival from a
fiction; the accounts-first answers and the weekly report compute per
workspace; the backstop is armed in both channels.

**Does not prove:**

- **Anything about a real client's data.** The two live client channels
  (named in the workspace policy, not here) carry real traffic. Binding one is an
  operator decision, and that is exactly why the synthetic one is the right
  vehicle.
- **That the two gates on the sender path are independently load-bearing.**
  §3a: one is redundant with the other.
- **Anything about DM scope.** `resolve` binds a DM by USER, not channel, and
  this file binds channels. A workspace user's DM is a client scope and is not
  exercised here. It is the obvious next assertion and it is small.

---

## 7. STILL YOURS

- **Nothing new is required for this to be correct.** Unlike D3 and D4 this
  increment is not switched off waiting on anything — it is tests plus one
  count fix.
- **`sender_summary`'s live numbers change when this merges**, by design:
  Productive 156 → 158 (the three demo-shaped entries counted properly, less
  the bucket) and ContactOut 1 → 2. If anything of yours quotes those figures
  from before today, it was quoting the bug.
- **`workspace_summary` is the one client tool that does not stamp
  `workspace` on its answer** — it returns the knowledge-pack entry verbatim.
  Not changed here because it is not this increment's business, but it makes
  that answer the only one you cannot audit for scope by looking at it.

Carried forward: `docs/SLACK-AGENT-HANDOFF-2026-09-23-PM.md` §5, unchanged.
The write-back, the `replies.VERSION` bump and the `account.replies()`
widening are still what everything else waits on.
