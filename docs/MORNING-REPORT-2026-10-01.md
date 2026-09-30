# Morning report — 2026-10-01

Intended for `#resonate-os` (C0C3C6MDN9L). **It could not be posted.** See
"Why this is a file" at the bottom. Written to be read on a phone.

## READ THIS FIRST — master is broken, and it is not from tonight's work

Your own commit `f7d4d5cd` ("Missing personalization selects a weaker angle
instead of discarding the account", **18:29 tonight**, three hours before this
session started) rewrote `src/personalization.py` into the L1-L4 ladder. The
ladder is fine. But it deleted 343 lines and **nineteen public names, without
updating the callers.** Eight of them are still called from nineteen modules —
`selected_contacts` alone from eleven.

    MEASURED on master:
      channels.summarise(recs, config)   AttributeError on a real record
      mx.apply_to_record(rec, config)    AttributeError - the ENRICHMENT path
      full suite  13,542 tests   243 failures   3,067 errors

**The SEND path is intact** — `eligibility.decide` ran clean all night;
eligibility's two mentions of `personalization` are docstring prose, not
calls. And nothing is running, so nothing is being harmed while it sits.

A restoration is being prepared on a branch (keep the new ladder, bring back
the removed API) with a before/after suite count and a regression test that
walks `src/` for the names it actually calls. **Not merged** — it is 343 lines
and the right fix might be "update the callers" instead, which is your call.

---

**Canary: BLOCKED. Not ready for GO. Nothing was sent.**

    provider writes by this work   0
    sends by this work             0
    sending.live                   false
    freeze                         ON
    487 / 489 / 493                still paused, 6 / 10 / 22 sent,
                                   no provider write since your 09-28 pause
    master                         see `git rev-parse master` — this session
                                   pushed after every commit and verified the
                                   remote each time; a SHA typed here goes
                                   stale the moment the next one lands

---

## Merged tonight — 8 commits, every one GLM-verified

    d64821f8  an excluded contact is refused by the send path       PASS
    9ad8bc10  the send gate asks the CLIENT's verification policy   PASS
    1a062282  the angle gate is scoped to the send scope            PASS
    cbb079ce  cherry-pick: operator exclusion (that commit only)
    8e47fc4c  we are never our own recipient                        PASS
    4098dad7  two bypasses GLM found: subdomain, plus-addressing    PASS
    e798d68a  gmail dot-folding, closing GLM's last UNKNOWN
    8ff27be1 / d6178590   handoff

Two numbers worth your attention:

- **804 of 1,308** contacts with an address were being refused under a policy
  their own client had cleared. Productive dropped ContactOut from
  verification on 09-21; `approve.why_not` was fixed that day, `eligibility`
  was missed. 220 stay refused — that is the negative control.
- **225 of 225** of our own sending mailboxes could be enrolled as prospects,
  including through another company's record. Now 0. Live re-read: 222
  mailboxes, all covered.

GLM found two real bypasses after I thought B3 was done — a subdomain
(`ivan@eu.resonategroup.co`) and a plus-tag — and returned UNKNOWN rather than
PASS twice when I had not shown it enough. No UNKNOWN was recorded as a PASS.

---

## Why the canary cannot go

Fixing the verification policy made 807 contacts sendable where almost all
had been refused, so I re-screened the whole domains lane rather than your
five. **Nine** contacts have em1-em5 stored and pass every LOCAL gate. All
nine were then checked at the provider.

**`collision.account_policy` returns ALLOW for ZERO of them**, and — the part
that matters more — **not one of the nine has zero provider history.** Each
has already received 8 to 21 emails from us. The fix surfaced previously
worked leads, not fresh ones.

    3 STOP   somebody at the account is mid-sequence RIGHT NOW on active 328,
             and in two cases it is the candidate himself; one account is
             answered (2 replies on active 327)
    4 HOLD   "a campaign at this account ended early (stopped) and the status
             does not say whether we stopped it, they unsubscribed, or the
             provider stopped it on a reply"

**The one real finding underneath all of it.** Exactly three sendable
contacts in the estate cannot be written to because their job title does not
map to a persona — and **two of them sit at the only two accounts measured
ALLOW, with zero provider history each.** That is not a coincidence: a person
the system could never write to is a person it has never written to.

    rkconnect / mike-hurt      no lead row at all   account ALLOW
    nuvolum   / deva-putney    no lead row at all   account ALLOW
    8ms       / ailsa-duncan   no lead row at all   account HOLD

I first dismissed the persona gap as trivial because it affects only three
people. That was the wrong reading. Those three are the only untouched ones
we have.

I also checked whether the set-aside people with copy could be recalled.
**They cannot.** Their reason says "re-askable", which invites the assumption
that tonight's fix frees them. Measured per person, it frees exactly one, and
she is disqualified three other ways. Three of them were verified by the very
pair Productive dropped, so the corrected gate refuses them correctly. Acting
on the obvious guess would have put people your own policy refuses back on
the send path.

**And three defects would block a send whichever candidate we had:**

1. **No CTA and no ask.** Two separate things, both missing:
   - Zero URLs in all ten generated emails. `copyprompts` forbids the writer
     typing a URL — deliberately, models retype them wrong — and nothing
     injects `offer.cta_link` afterwards. No gate requires one;
     `check_cta_links([])` passes vacuously.
   - **The licensed mechanism is never asked for.** The offer file says "the
     walkthrough is the primary ask for the economic buyer, per the operator
     2026-09-27". It appears in **zero of five** of Allison's emails, and in
     Marty's only in **em5 — the give-up email**, twice. Four emails of
     build-up and the ask arrives as we are walking away.
   A link is not an offer. The prepared branch injects the URL; it does not
   make the ask. Regenerating the copy is what fixes the second half.
2. **em4 overclaims.** It describes Report Intelligence as proactively
   flagging margin risks in real time. Its licensed text is "ask anything
   about your business data" — pull, not push. `copylint` exempts the
   capability's NAME and nothing checks the DESCRIPTION.
3. **A mailbox can be swapped after approval.** `approval.fingerprint` has no
   mailbox input; `executionscope.require` has no mailbox parameter and never
   compares its stored approval hash. Only `campaigns.approval_is_current`
   catches it, and only when a campaign row is passed. This is your own
   blocker criterion 3i.

Related and worse: `sequenceplan.approval_hash` reads `plan["sender"]`, which
`bisonfactory._plan` never sets. The test that proves sender coverage injects
that key by hand — including a case labelled "production path". The hash is
computed and compared nowhere.

---

## Waiting on you

1. **The copy — regenerate or send as is? I recommend regenerate.** Five
   emails that never make one of the three approved offers and never give a
   link. An independent reviewer who had not seen how it was written said the
   same unprompted: reads as automated, em3 and em4 duplicate each other, and
   the em3/em4 subject describes content the bodies do not contain.
2. **How we get a candidate at all. My recommendation has changed** now that
   all nine are screened:
   **(a) Give `mike-hurt` a persona.** He is the best canary target in the
       estate: zero provider history, account ALLOW, passes verification,
       `email_verdict`, `must_not_contact` and every local gate. The only
       thing stopping him is that "Media Activation Director" is not in
       `personas` for this client, so he can get no angle and no copy.
       It is a config change that widens who the system will write to, so it
       is a policy decision and yours, not mine. Same change covers
       `deva-putney` at the other ALLOW account.
   (b) Source fresh accounts. The honest read of tonight is that this estate
       is worked out: every person with copy has been emailed 8-21 times.
   (c) Resolve the re-contact rule with Bruno — this is what would unlock the
       four HOLD candidates. **Do not let a cooldown be invented**;
       conservative handling stands until Bruno answers.
   (d) Re-verify a set-aside person against the current primary. Costs
       credits and lands you back among previously-worked leads, so I now
       rank this last rather than first.
3. **Signature name.** We render "Ivan"; mailbox 2778's From name, stored
   signature and attested owner are all "Ivan Mamic". One line in
   `config/clients/productive.yaml`.
4. **Branches prepared, NONE merged** per your rule 4. Each has tests and an
   attack set; awaiting your DA.

       CTA injection + gate        e534254b   GLM: hole found, then fixed
       approval binds the mailbox  8ab8f8dc   GLM: PASS
       capability claim tracing    415bc727   GLM: 4 bypasses, then fixed
       personalization restore     fa9a126b   errors 642 -> 4, measured

   **The restore's number.** The 36 modules that error on the deleted API,
   run on both trees:

       master     1056 tests   8 failures   642 errors    22s
       restore    1075 tests  11 failures     4 errors   161s

   Errors 642 -> 4. The time is evidence too: errors fail instantly, so a
   suite that gets slower is a suite that started actually running. 11
   failures remain against 8, and 19 more tests ran — I have NOT proven those
   three extra failures are tests that previously errored rather than new
   breakage, so treat it as unresolved, not as clean.

   The risk in restoring was that bringing back the deleted API would
   disturb the L1-L4 ladder your commit was FOR. It does not. Measured over
   all 1,582 records, the level distribution is byte-identical on master and
   on the branch - L2 1178, none 338, L1 65, L4 1 - with the same LEVEL
   constants. Both APIs coexist, and the two broken production paths
   (`channels.summarise`, `mx.apply_to_record`) work again.

   Every branch was attacked, and two came back with real holes that were
   then closed. On the capability gate GLM found four bypasses — a fronted
   phrase ("With X, you can watch…") walked past the subject test entirely,
   a pronoun after an adverbial escaped an anchored pattern, the
   no-licensed-text refusal was never reached, and a 50% coverage ratio let
   an unlicensed verb ride along on licensed nouns. I reproduced all four,
   they were fixed, and I re-verified all four closed with the controls
   still passing.

   **One cost on that branch you should know about.** With the capability as
   the SUBJECT, an offer fact is now refused:

       "Report Intelligence is included in the trial."        REFUSED
       "The premium trial includes Report Intelligence."      passes

   Both say the same true, approved thing — AI features in the trial is one
   of Bruno's three approved offers. The gate refuses the first because
   "included"/"trial" appear nowhere in that capability's licensed text. It
   fails CLOSED, so it blocks true copy rather than admitting false copy, and
   there is a legal phrasing. But the asymmetry is arbitrary and the copy
   writer has to know it. Worth a decision rather than a discovery.

   **The approval branch has a consequence you must weigh before saying yes.**
   It deliberately does NOT grandfather: an approval stamped before the
   binding existed no longer matches, so it goes stale. I measured what that
   costs — **851 records, 3,005 approved steps in the estate would all need
   re-taking.** That is the conservative and correct reading of invariant 0,
   and it is a lot of re-approval. Nothing is sending, so it blocks nothing
   today. Your call whether to accept it, or to grandfather stamps older than
   the change and bind only new ones.

   Two residuals on that branch, stated rather than hidden:
   `executionscope.require()` still has no mailbox parameter and still never
   compares its stored `approval_hash`; and `campaigns.approval_is_current`
   plus the reporting surfaces still ask the words-only question, so they
   will show "approved" for a record `eligibility` now refuses. Fail-closed
   at the gate, but the inconsistency is visible to you.

5. **An incident with no damage, logged for the record.** Git worktrees share
   ONE stash ref. One agent's bare `git stash pop` pulled another agent's
   uncommitted work (a 379-line file and a 131-line test) out of its
   worktree. Nothing was lost — I found it on the stash, verified both parts
   were intact, and sent the owner exact recovery instructions. No repo state
   was harmed and nothing reached a provider. Worth knowing before running
   parallel worktree agents again.

---

## Settled and good

Mailbox 2778 confirmed: Connected, From name "Ivan Mamic", limit 15, warmup
on; 12 Ivan Mamic mailboxes, live. **Signature renders exactly once** — all
222 provider signatures are literal text, none contains a variable, and
EmailBison does not append one (three independent live reads). Zero
unresolved placeholders in the copy. Opt-out present once per email.
BISON_KEY verified, bound to workspace 10 PRODUCTIVE. Provider truth
refreshed: 40 of 40 campaigns, nothing new since 09-28. Killswitch refuses in
code, not by a flag.

## UNKNOWN — and staying that way

Reply-To on 2778 (the provider schema has no such field) · whether EmailBison
splices a signature at SMTP handoff (everything measurable says no; only a
real send read back settles it) · the direction of the aimclear reply ·
whether anything is queued for nuvolum's lead in 327/352 (proving it means
walking ~95k rows) · provider WRITE authority, verified on GETs only.

## Also found, not fixed, off the critical path

`tests/test_linkedin_lint.py` has 3 pre-existing errors on master
(`personalization.settings` missing). `eligibility._account_fatigue` cannot
see the client's campaigns at an account because provider touches were never
ingested. `scripts/task_registry.py --status` rewrites
`docs/state/TASK-REGISTRY.json` as a side effect of a read. A duplicated
`_claim_detail(unsupported)` in the LinkedIn branch of `_email_checks`'
sibling.

## Why this is a file and not a Slack message

Posting needs `SLACK_BOT_TOKEN` **and** `SLACK_LIVE`. `SLACK_LIVE` is not set
in this build, `notify.ops_channel()` returns None, and `slack.post` refuses —
`src/config.py:173` states the rule: "a token alone never enables posting".
That is a deliberate guard, and turning it on is outward-facing, so I did not.
Say the word and I will post this and the checkpoint, or you can paste it.
