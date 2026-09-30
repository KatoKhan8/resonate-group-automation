# Canary handoff — 2026-10-01 (overnight session)

Format: CLAIM / AUTHORITY / MEASURED AT / STATE. Invariant 0 applies: an
unreadable authority is UNKNOWN, and **UNKNOWN never becomes PASS**.

**No prospect PII in this file.**

    master at handoff   e798d68a   (pushed, origin/master agrees)
    session started at  5fd49bb7

## THE HEADLINE

**The canary has no viable candidate.** All five in the operator's order are
exhausted, and three defects block a send regardless of which candidate is
chosen. **Nothing was sent. Provider writes by this work: 0.**

## a) What was merged, with its GLM verdict

    d64821f8  B1  an excluded contact is refused by the send path      GLM PASS
    9ad8bc10  A   the send gate asks the client's verification policy  GLM PASS
    1a062282  B2  the angle gate is scoped to the send scope           GLM PASS
    cbb079ce      cherry-pick: permanent operator exclusion (that
                  commit only; the branch is -41,798 lines behind
                  master and must never be merged whole)
    8e47fc4c  B3  we are never our own recipient                       GLM PASS
    4098dad7      two exclusion bypasses GLM found (subdomain,
                  plus-addressing)                                     GLM PASS
    e798d68a      gmail dot-folding, closing GLM's last UNKNOWN

GLM-5.3 attacked each SHA adversarially with five questions: can an excluded
contact, the operator, a sending inbox, a contact the client's policy refuses,
or a sendable contact with no angle reach the send path. Two rounds returned
UNKNOWN (it had been shown only the `src/` diff, so it could not confirm the
register rows existed); re-asked with the measured gate output as evidence it
returned PASS on `sending_inbox`, and UNKNOWN on `operator` until the dot fold
existed. **No UNKNOWN was recorded as a PASS.**

### Blast radius of A, measured read-only on the live queue

    804 of 1,308 contacts with an address were refused under a policy their
    own client had cleared.
    Over 2,693 generated email steps whose contact is still on the record:
      before  2,047 held:verification_unknown    91 eligible
      after     220 held:verification_unknown  2,034 eligible
    The 220 that stay refused are the negative control at scale.

### Blast radius of B3

    225 of 225 of our own sending addresses passed `must_not_contact` as
    RECIPIENTS before the fix, filed under a STRANGER's record. After: 0.
    Live re-read: 222 mailboxes, 222 of 222 covered by the register.

## b) The candidates — all five exhausted

    CLAIM      no candidate in the operator's order can be the canary today
    AUTHORITY  store.load(), eligibility.decide, collision.account_policy,
               and per-person provider lookups (bison.find_lead_by_email)
    MEASURED   2026-09-30 evening
    STATE      exhausted, per row below

    westcarygroup-com  FAIL  em4/em5 never converged (30 attempts); the same
                             person stands in both `contacts` and `excluded`;
                             the send path independently refuses her at
                             verification. Disposition written to the record.
    rkconnect-com      FAIL  its only sendable contact has no persona, no
                             angle and no generated copy. The contact that
                             HAS copy is on the excluded list.
    obexp-com          FAIL  the PERSON is clean - no lead row at the
                             provider, proven with controls, not index
                             silence. The ACCOUNT is not: 5 leads in client
                             campaigns 274/327/352, one of them REPLIED, and
                             327 and 352 are ACTIVE.
    aimclear-com       FAIL  person clean; a colleague REPLIED on campaign
                             352, which is ACTIVE.
                             `collision.account_policy` -> **STOP**,
                             "the account is answered".
    nuvolum-com        the only account `collision.account_policy` calls
                             **ALLOW** - nobody has replied and nobody is
                             mid-sequence. BUT its sendable contact has no
                             copy, no persona and no angle; the generated
                             copy belongs to the EXCLUDED contact.

**So the only clean account needs copy generated for a contact who has no
persona yet, and `persona_angle` is the stage that was failing with
`SchemaError: evidence not traceable to the record`.**

## c) Three defects that block a send whichever candidate is chosen

### 1. No CTA reaches the prospect. Not in any email, for any candidate.

    CLAIM      zero URLs in all ten generated emails across both candidates
    AUTHORITY  URL scan of subject + projected body + P.S., and a repo grep
               for `cta_link`
    MEASURED   2026-09-30
    STATE      CONFIRMED and it is not an accident of prompting.
               `copyprompts.py:130` says **"NEVER write a URL"** - deliberate,
               because a model retypes a URL and gets it wrong (measured
               2026-09-25). `offer.cta_link` is declared in
               `config/clients/productive-offers.yaml` and read by NOTHING
               except `copylint`, which only validates URLs that are already
               present. `check_cta_links([])` passes vacuously.

The fix is not to let the writer type it. It is to inject `offer.cta_link` in
`trailingcontent.compose`, the same place the signature and the opt-out line
are already injected. **That changes what every prospect receives, so it is a
policy change and is NOT merged. It awaits the operator's DA.**

### 2. em4 overclaims a product capability

    CLAIM      em4's description of Report Intelligence is not what its
               licensed source says
    AUTHORITY  offer `ai_capabilities['Report Intelligence'].page_text`
    MEASURED   2026-09-30
    STATE      licensed text is pull-based - "Ask anything about your business
               data" - and the email asserts proactive real-time surfacing and
               flagging. `copylint.licensed_names` exempts the NAME from
               `untraceable_company_claim`; nothing traces the DESCRIPTION
               back to the page text. No gate catches it. Present in em4 for
               BOTH candidates.

### 3. A mailbox can be substituted after approval

    CLAIM      neither the approval hash nor execution scope prevents it
    AUTHORITY  synthetic-record probes against the real gates
    MEASURED   2026-09-30
    STATE      `approval.fingerprint` covers channel, subject, body, note and
               ps - NOT mailbox, NOT recipient, NOT signature, NOT campaign.
               `executionscope.require()` has no mailbox parameter, and its
               stored `approval_hash` and `purpose` are never compared.
               Swapping the mailbox, the signature or the campaign leaves the
               step gate answering `eligible`. Swapping body or subject
               correctly gives `held:approval_stale`.
               The only backstop is `campaigns.approval_is_current`, and only
               when a campaign row is passed; with `campaign=None` all four
               sail through.
               `executionscope`'s default IS refuse, proven by call.

    RELATED    `sequenceplan.approval_hash` reads `plan["sender"]`, which
               `bisonfactory._plan` never assigns. The hash did not move
               across three different sender identities in the production
               plan shape. The test that proves sender coverage injects the
               key by hand - including a case labelled "production path".
               The hash `bisonfactory` computes is returned in a dict and
               compared nowhere in `src/`.

## d) Two more that gate the canary but are the operator's call

    SIGNATURE NAME  we render "Ivan"; mailbox 2778's From name, its stored
                    signature and its attested owner are all "Ivan Mamic".
                    The operator's rule is that they must be equal.
                    Fix is one line in `config/clients/productive.yaml`
                    (`sender.name`), and it is the operator's.

    MAILBOX FULL    2778 is 15/15 booked on 2026-09-30 by the CLIENT's still
                    active campaign 328, so our pause does not free it. The
                    forward book is 146.7h stale and can prove FULL but never
                    ROOM, so a fresh census is needed before any day can be
                    called free.

## e) What IS settled and good

    mailbox 2778    i.mamic@withproductive-ai.com, Connected,
                    google_workspace_oauth, From name "Ivan Mamic",
                    daily limit 15, warmup on. 12 Ivan Mamic mailboxes
                    confirmed live, 2778 among them.
    signature       renders ONCE. All 222 provider-side signatures are
                    literal text, 0 contain "{", 0 contain
                    SENDER_FULL_NAME. EmailBison does NOT append one to
                    campaign emails - three independent live reads.
    variables       zero unresolved placeholders in all five steps, over
                    `lint.PLACEHOLDER_RE`, `copylint.UNRENDERED_RE` and 23
                    hand-written patterns.
    opt-out         present exactly once per email, reply-based.
    trailingcontent one composer; provider variables byte-identical to it.
    credentials     BISON_KEY AUTHENTICATION_VERIFIED, bound to workspace 10
                    PRODUCTIVE. ContactOut, Blitz, AIARK, HeyReach verified.
    provider truth  refreshed 2026-09-30T20:40:42Z, 40 of 40 campaigns.
                    487/489/493 still PAUSED, 6/10/22 sent, no provider write
                    since the operator's 09-28 pause.
    killswitch      global refuses IN CODE (`push.run(live=True)` raises);
                    workspace `sending.live` off. Two layers, both refusing.

## f) UNKNOWN — and staying UNKNOWN

    Reply-To on 2778 - the provider's sender-emails schema has no such field
    whether EmailBison splices a signature at SMTP handoff (everything
      measurable says no; only a real send read back would settle it)
    the DIRECTION of the aimclear reply - no body is attributable
    whether anything is queued for nuvolum's lead in 327/352 - proving it
      would mean walking ~95k rows and is a rate-limit event
    provider WRITE authority - verified on GETs only, never attempted
    dots in non-Gmail addresses are deliberately not folded

## g) Next step

1. The operator decides the copy question: regenerate with a CTA and a
   corrected em4, or send as is. **My recommendation: regenerate.** A
   five-email sequence that never makes an offer and never gives a link is
   not a canary worth spending a first send on.
2. If regenerating: nuvolum-com is the only clean account, so `persona_angle`
   for its sendable contact has to resolve first.
3. The three blocked branches (CTA injection, em4 traceability, mailbox in
   the approval hash) are prepared as findings, NOT merged, per the
   operator's rule 4.

## h) Safety — unchanged

Freeze ON. `sending.live` = false. **Nothing sent by this work. Provider
writes by this work: 0.** 487/489/493 and the client's campaigns untouched.
No gate weakened - every change this session made a gate ask a question it
was already supposed to ask. No force push. No PII in git.
