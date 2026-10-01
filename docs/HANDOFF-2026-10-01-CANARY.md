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

### Why the set-aside people cannot be recalled to fill the gap

Every record holds an `excluded` list, and several of those people DO have
generated copy. The exclusion reasons split into two classes, and the first
class reads as though this session's own fix would lift it:

    class 1  "no approved step: verification pair does not satisfy this
              client's policy. Re-askable - S5 is verifying it against the
              current primary"
              nuvolum/jeffery-thompson, rkconnect/stephanie-heusuk,
              obexp/deb-lemon, obexp/ashley-ohalloran,
              westcarygroup/lisa-moran

    class 2  "live collision stop: 1 person(s) at this account have already
              replied or been marked interested; the account is answered and
              whoever is having that conversation owns it"
              obexp/joseph-forster, aimclear/laura-weintraub

    CLAIM      commit 9ad8bc10 does NOT make the class-1 people sendable. It
               confirms four of the five should stay refused.
    AUTHORITY  verification.is_sendable under each policy, per person
    MEASURED   2026-09-30
    STATE      stephanie-heusuk, deb-lemon, ashley-ohalloran:
                   default True -> client policy FALSE. They were verified by
                   the contactout+reoon pair Productive DROPPED. The
                   corrected gate refuses them, correctly.
               jeffery-thompson: False under both.
               lisa-moran: False -> TRUE. She is the only one who flips, and
                   her verification-based exclusion reason IS now stale - but
                   she is refused for three other reasons and stays out.

**This is worth stating because the opposite was the obvious guess.** The
class-1 wording invites you to assume the corrected policy frees them. It
frees exactly one person, who is independently disqualified. The real remedy
for class 1 is what the reason says: RE-VERIFY against the current primary
(Deliverable), which costs credits and is the operator's spend decision.

Class 2 is independent corroboration of the provider findings above: the
system had already recorded, locally, that obexp and aimclear are answered
accounts. The provider read and the local exclusion agree.

## b2) The estate re-screened after the fix — and what it actually showed

Commit 9ad8bc10 made 807 contacts sendable where almost all had been refused,
so the whole domains lane was re-screened rather than the operator's five.

    CLAIM      nine contacts have em1-em5 stored, are sendable under the
               client policy, are angled, are not excluded, lint CLEAN and
               pass eligibility.must_not_contact
    AUTHORITY  store.load() + lint.check + eligibility.must_not_contact
    MEASURED   2026-09-30
    STATE      nine. Seven were then screened at the provider (obexp and
               aimclear were already known STOP).

    CLAIM      collision.account_policy returns ALLOW for ZERO of the nine,
               and not one of them has zero provider history
    AUTHORITY  collision.check_account + collision.account_policy, built as
               executionguard does; bison.find_lead_by_email per person, with
               a nonsense-term control, a nonsense-domain control and a
               round-trip of every id found
    MEASURED   2026-09-30T21:02-21:03Z, estate 10 PRODUCTIVE
    STATE      3 STOP - somebody at the account is mid-sequence on ACTIVE
                        campaign 328, and in two cases it is the candidate
                        himself; one account is answered (2 replies, status
                        AND counter agreeing, on ACTIVE 327)
               4 HOLD - "a campaign at this account ended early (stopped) and
                        the status does not say whether we stopped it, they
                        unsubscribed, or the provider stopped it on a reply"
               Every one of the nine has already received 8-21 of our emails.
               **The fix surfaced previously-worked leads, not fresh ones.**

    NOT A DEAD-ADDRESS SIGNAL. Every lead reads opens 0 against 8-21 sends,
    which looks alarming and is not evidence: `open_tracking` is FALSE on
    campaigns 327, 328 and 274 (47,768 / 38,533 / 28,331 sent, 0 opens each).
    The estate does not track opens, so deliverability at these accounts is
    UNMEASURED. `any_bounce` is False for all six domains, which is the only
    real signal available.

### The finding underneath all of it

    CLAIM      exactly three sendable contacts cannot be written to because
               their title maps to no persona - and two of them are at the
               only two accounts measured ALLOW, with no provider lead row
    AUTHORITY  personas.classify, collision.account_policy,
               bison.find_lead_by_email
    MEASURED   2026-09-30
    STATE      rkconnect / mike-hurt      no lead row   account ALLOW
               nuvolum   / deva-putney    no lead row   account ALLOW
               8ms       / ailsa-duncan   no lead row   account HOLD

               mike-hurt passes verification under the client policy,
               `channels.email_verdict` -> (True, None), and
               `must_not_contact` -> clear. The ONLY thing stopping him is
               that "Media Activation Director" classifies to persona None,
               so he can get no angle, so `domains_contact_no_angle` would
               refuse any copy - and no copy exists for him.

**This was first dismissed as trivial because it affects only three people.
That was the wrong reading: those three are the only untouched people in the
estate.** A person the system could never write to is a person it has never
written to. Giving `mike-hurt` a persona is the single highest-value change
available, and because it widens who the system will write to it is a policy
decision and the operator's.

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

### 1b. And the licensed ask is never made, which is the bigger half

    CLAIM      the approved mechanism is absent from the copy
    AUTHORITY  the offer file's own wording, and a scan of all ten bodies
    MEASURED   2026-09-30
    STATE      `OFFER-A-ECONOMIC-BUYER.mechanism_note` reads "the walkthrough
               is the primary ask for the economic buyer, per the operator
               2026-09-27". Measured: it appears in ZERO of five of
               obexp/allison-lam's emails, and in aimclear/marty-weintraub's
               only in em5 - the give-up email - where it appears twice.
               Four emails of build-up, and the ask arrives as we walk away.

**A LINK IS NOT AN OFFER, and the two defects must not be conflated.** The
prepared CTA branch injects the URL. It does not make the ask. Only
regenerating the copy does that, which is why the copy decision is the one
that matters most and why it is the operator's.

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

## g) The decisions only the operator can make

**1. The copy. Recommendation: REGENERATE.** A five-email sequence that never
makes one of the three approved offers and never gives a link is not what a
first send should spend its credibility on. An independent reviewer who had
not seen how the copy was produced reached the same place from the other
direction: it reads as automated, em3 and em4 say the same thing twice, and
the em3/em4 subject line describes content the bodies never contain.

**2. How to get a candidate at all.** Ranked after the full re-screen:

    a) GIVE `mike-hurt` A PERSONA. He is the best target in the estate: no
       provider lead row, account ALLOW, passes verification, email_verdict
       and must_not_contact. "Media Activation Director" simply is not in
       this client's persona config. It widens who the system will write to,
       so it is a policy decision and the operator's. The same change covers
       `deva-putney` at the other ALLOW account.
    b) SOURCE FRESH ACCOUNTS. The honest read of tonight is that this estate
       is worked out - every contact holding copy has been emailed 8-21 times
       already.
    c) RESOLVE THE RE-CONTACT POLICY WITH BRUNO. This is what unlocks the
       four HOLD candidates. **Do not let this be invented as a cooldown
       number** - it is a client-relationship decision, and the standing
       instruction is conservative handling until Bruno answers.
    d) RE-VERIFY a class-1 person against the current primary. Costs credits
       and lands back among previously-worked leads, so this is now ranked
       last rather than first.

**3. The signature name.** One line: `sender.name: Ivan Mamic` in
`config/clients/productive.yaml`, so the rendered name equals the attested
mailbox owner as the standing rule requires.

**4. Three branches are prepared and NOT merged** (CTA injection, capability
claim traceability, mailbox binding in the approval hash), per rule 4. Each
carries tests and a GLM verdict and awaits an explicit DA.

## h) Safety — unchanged

Freeze ON. `sending.live` = false. **Nothing sent by this work. Provider
writes by this work: 0.** 487/489/493 and the client's campaigns untouched.
No gate weakened - every change this session made a gate ask a question it
was already supposed to ask. No force push. No PII in git.

---

## CORRECTION, 2026-10-01: "the estate is worked out" was wrong

It is worked out only among the 1,582 records already INGESTED. Measured
today:

    work/agency-sourcing.jsonl   48,017 sourced company rows, 69 MB, on disk
    of those, not in the store and not in the collision index:  46,392
    scored with icp.score on a free 4,000-row sample:  82.1% qualified

So the supply of qualifying companies is roughly 38,000, already paid for and
sitting in a gitignored file. `discovery.known()` / `discovery.delta()` report
`spent: 0`; AI Ark's `company_search` is absent from `enrich.COSTS` entirely.
Spend begins at the PERSON level, not the company level.

Also corrected: CLAUDE.md's "36,679 credits and 117,419 searches remaining"
is a 2026-09-20 measurement. The ContactOut quota period rolled over on
2026-10-01, and the provider's own free `/stats` now reports 0 used of
3,822,751 this period. The old figures were true when written; they are not
current and should not be quoted as a budget.

**Minimum spend to reach ONE clean canary candidate: 0 credits, 0 new
domains.** 43 contacts pass every local gate; the only outstanding work is a
free read-only `collision.leads_for_domain` walk, because
`work/collision-index.json` carries `incomplete: [352, 328, 327, 274]` — the
exact campaigns that refuse a partial walk — so nothing may be called clear
on its authority.
