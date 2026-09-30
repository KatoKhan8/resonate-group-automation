# Morning report — 2026-10-01

Intended for `#resonate-os` (C0C3C6MDN9L). **It could not be posted.** See
"Why this is a file" at the bottom. Written to be read on a phone.

**Canary: BLOCKED. Not ready for GO. Nothing was sent.**

    provider writes by this work   0
    sends by this work             0
    sending.live                   false
    freeze                         ON
    487 / 489 / 493                still paused, 6 / 10 / 22 sent,
                                   no provider write since your 09-28 pause
    master                         d6178590 (pushed, remote agrees)

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

**All five candidates are dead, and none of it is the gates' fault.**

    westcarygroup   no em4/em5 after 30 attempts; also double-listed
    rkconnect       sendable contact has no persona, no angle, no copy
    obexp           person CLEAN at the provider - but the ACCOUNT has a
                    reply and two ACTIVE client campaigns
    aimclear        colleague REPLIED on campaign 352, ACTIVE right now.
                    collision.account_policy -> STOP, "the account is answered"
    nuvolum         the ONLY account the policy calls ALLOW - but its
                    sendable contact cannot get a persona at all
                    ("Director Of Business Development" is not in the
                    persona config), so it can never get an angle or copy

I checked whether the excluded people with copy could be recalled. **They
cannot.** Their reason says "re-askable", which invites the assumption that
tonight's verification fix frees them. Measured per person: it frees exactly
one, and she is disqualified three other ways. Three of them were verified by
the very pair Productive dropped, so the corrected gate refuses them
correctly. Acting on the obvious guess would have put people your own policy
refuses back on the send path.

**And three defects would block a send whichever candidate we had:**

1. **No CTA reaches anyone.** Zero URLs in all ten generated emails.
   `copyprompts` forbids the writer typing a URL — deliberately, because
   models retype them wrong — and nothing injects `offer.cta_link`
   afterwards. No gate requires one. `check_cta_links([])` passes vacuously.
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
2. **How we get a candidate at all.** Pick one:
   (a) re-verify a set-aside person against the current primary — what their
       own exclusion reason prescribes, costs credits. **My preference.**
   (b) source a new candidate outside the five.
   (c) resolve the re-contact rule with Bruno. **Do not let a cooldown be
       invented** — conservative handling stands until Bruno answers.
   (d) extend the persona config to cover business development. Smallest
       technical change, but it widens who we write to, so it is yours.
3. **Signature name.** We render "Ivan"; mailbox 2778's From name, stored
   signature and attested owner are all "Ivan Mamic". One line in
   `config/clients/productive.yaml`.
4. **Three branches prepared, NOT merged** per your rule 4 — CTA injection,
   capability-claim traceability, mailbox binding in the approval hash. Each
   with tests and a GLM verdict, awaiting your DA.

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
