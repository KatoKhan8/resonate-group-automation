# R2 PHASE 1 — THE SIGNATURE MEASUREMENT

Read-only measurement for RAMP TRACK R2. No source file changed, no provider
write, no credit spent. Every provider call in this document is a `GET`.

    measured at   2026-10-01T10:20Z - 10:42Z
    repo          master 85158003 at session start; 617f910e by the end
                  (another session merged "When to merge without asking"
                  mid-measurement - 85158003 is an ancestor of 617f910e, so
                  nothing below was invalidated, but the SHA in the task
                  prompt is no longer HEAD)
    provider      https://send.resonategroup.co/api, workspace 10 PRODUCTIVE
                  per `GET /users` - the only route that states the workspace
    not read      campaigns 487, 489, 493, 327, 328, 352. Frozen by the task.
                  Where that leaves a question open it is marked UNKNOWN below
                  and the one GET that would close it is named.

Everything is reported as CLAIM / AUTHORITY / MEASURED AT / STATE. UNKNOWN
never becomes PASS.

---

## 0. THE DISCRIMINATOR THAT MADE THE REST POSSIBLE

Before anything else, because two campaigns were about to be mis-attributed.

**CLAIM.** A campaign is OURS if and only if its leads carry the custom
variable `record_id`. Campaign name is not evidence of ownership.

**AUTHORITY.** `GET /campaigns/{id}/scheduled-emails` -> `lead.id` ->
`GET /leads/{id}` -> `custom_variables`.

**MEASURED AT** 2026-10-01T10:38Z.

**STATE — CONFIRMED.**

    c498  17 lead variables  record_id present   "RESONATE - PRODUCTIVE - ..."
    c494   7 lead variables  record_id present   "RESONATE - PRODUCTIVE - ..."
    c503  11 lead variables  record_id present   "PRODUCTIVE-USEast-..."
    c502   0 lead variables  record_id ABSENT    "PRODUCTIVE - SOFTWARE DEV..."
    c418   0 lead variables  record_id ABSENT    "PRODUCTIVE - SOFTWARE DEV..."

502 and 418 are NOT ours. Both carry the word PRODUCTIVE in the name, both
hold copy written as spintax directly in the sequence template, and neither
stages a single variable through `bisonfactory`. 503 IS ours despite having no
`RESONATE -` prefix. Name-based attribution would have got both wrong in both
directions — which is the same defect CLAUDE.md records for
`provider_truth.owned_by_resonate`.

This matters below because 502 is the only campaign in the estate where a
provider-side signature token and a Productive-shaped name coexist, and
reading it as ours would have reported a live double-signature risk that does
not exist.

---

## 1. THE EmailBison PER-MAILBOX SENDER VARIABLE NAME

**CLAIM.** EmailBison resolves three sender variables per sending mailbox,
spelled in SINGLE braces and upper case:

    {SENDER_FIRST_NAME}        CONFIRMED resolving
    {SENDER_EMAIL_SIGNATURE}   CONFIRMED resolving
    {SENDER_FULL_NAME}         PRESENT in a stored template, NEVER OBSERVED
                               RESOLVING -> UNKNOWN

`{SENDER_EMAIL_SIGNATURE}` resolves to the `email_signature` field of the
`/sender-emails` row for the mailbox that sends that row.

**AUTHORITY.** Four independent reads, and no route documents any of this:

1. `GET /custom-variables`, fully paged — 24 names on TWO pages. All 24 are
   lead-level and ours or the operator's (`body_1..6`, `subject_1..6`,
   `record_id`, `contact_key`, `client`, `sender_id`, `sender_account_id`,
   `provider_account_id`, `headline`, `industry`, `location`, `title`,
   `subject`, `body`). NONE is a sender name. *(Note for a later reader:
   `bison.custom_variables`'s docstring says this workspace has twelve on one
   page. It has 24 on two. `_paged` handles it, the comment is stale.)*
2. Route discovery, read-only `GET`, 15 paths. `/variables`,
   `/system-variables`, `/merge-tags`, `/merge-variables`, `/placeholders`,
   `/default-variables`, `/sender-variables`, `/signatures`,
   `/email-signatures`, `/settings`, `/workspace-settings`, `/sending-settings`
   are all **404**. **No API route enumerates EmailBison's system variables.**
   The vendor's own data is the only authority available.
3. `GET /campaigns/{id}/sequence-steps` for all 34 non-frozen campaigns of 40,
   every `{...}` token counted. The sender tokens that exist in stored
   templates: `{SENDER_FIRST_NAME}` x123 in 12 campaigns,
   `{SENDER_EMAIL_SIGNATURE}` x44 in 6, `{SENDER_FULL_NAME}` x15 in ONE.
4. Resolution proved against rendered rows, which is what `email_body` on a
   scheduled-email is good for — proving a variable DID resolve, as opposed to
   proving nothing was added later (see section 2).

**MEASURED AT** 2026-10-01T10:24Z - 10:36Z.

**STATE.**

`{SENDER_FIRST_NAME}` — **CONFIRMED, PER MAILBOX.**

    campaign   rows matched to a known mailbox   body carries that mailbox's
                                                 own first name   raw token left
    c329              13                              13                0
    c330              11                              11                0
    c331              15                              15                0
    c334              14                              14                0
    c335              15                              15                0

And the decisive form of it — distinctness INSIDE ONE SHARED TEMPLATE.
Campaign 331, 45 rendered rows across three pages:

    31 rows sent by a Kresimir Simicic mailbox -> body contains "Kresimir"
                                                  and no other owner's name
    14 rows sent by a Bernarda Vrbat mailbox   -> body contains "Bernarda"
                                                  and no other owner's name

One template, two values, zero cross-contamination. The variable is bound to
the mailbox, not to the campaign.

`{SENDER_EMAIL_SIGNATURE}` — **CONFIRMED, PER MAILBOX, AND IT READS THE
`email_signature` FIELD.** Campaign 418, template step bodies end
`<p>{SENDER_EMAIL_SIGNATURE}</p>`: 15 of 15 rendered rows contain the exact
stored `email_signature` text of their own mailbox, 0 of 15 retain a raw
`{SENDER_*}`. The rendered tail of a row sent by a Bernarda Vrbat mailbox is
literally `<p>Bernarda Vrbat<br>Productive</p>`, byte-equal to that row's
mailbox `email_signature`.

The second, stronger proof is campaign 502, and it proves the SOURCE field
rather than just the behaviour. 502's leads carry **zero** custom variables
(section 0), so nothing the signature could have come from exists on the lead
— yet its step-4779 and step-4780 rows carry a per-mailbox sign-off and its
step-4781 rows, whose template has no token, carry none. The resolved value in
those rows is *"Bernarda Vrbat / Account Executive @ Productive"*, which is NOT
the value `/sender-emails` stores for that mailbox today
(`<p>Bernarda Vrbat<br>Productive</p>`). Two conclusions, both load-bearing:

  * the token reads the mailbox's stored signature field, because it produced
    that field's older value and could have produced it from nowhere else; and
  * **the resolution is frozen into the queue row at schedule time.** 502's
    rows were rendered 2026-09-25; the signature was bulk-edited later; the
    queued rows still hold the pre-edit string. 418's queue was rendered after
    the edit and holds the post-edit string. A signature change does NOT
    propagate to rows already queued.

`{SENDER_FULL_NAME}` — **UNKNOWN. This is the trap and it was baited.** It is
the one that looks right, and it is the one nothing confirms. It occurs 15
times, in campaign 234 ALONE. Campaign 234 is `archived`, `emails_sent = 0`,
and `GET /campaigns/234/scheduled-emails` returns `total: 0`. There is not one
rendered row in the estate in which `{SENDER_FULL_NAME}` has ever been
resolved. An operator typing a token into the EmailBison UI is not the
provider accepting it: the UI stores free text, and 234 never sent. Per the
task's own rule it stays UNKNOWN and must not be shipped on.

**THE TASK'S NOTE IS ALMOST RIGHT, AND THE EXCEPTION IS WORTH RECORDING.** The
brief states that `SENDER_FULL_NAME` "appears NOWHERE in this repository". A
repo-wide grep (not just `src/`, and including every worktree) measured at
2026-10-01T10:44Z says:

    occurrences under src/                                 0
    occurrences in tracked files                           1
      docs/HANDOFF-2026-10-01-CANARY.md:289

That one occurrence does NOT make it ours, so the brief's conclusion stands —
but it is not nowhere, and a later session grepping for it will find it and
needs to know what it is. In context it reads: *"signature renders ONCE. All
222 provider-side signatures are literal text, 0 contain "{", 0 contain
SENDER_FULL_NAME. EmailBison does NOT append one to campaign emails - three
independent live reads."* It is a **negative assertion about the mailbox
signatures**, not a variable our code emits, reads or declares. Both halves of
it are independently re-confirmed by this measurement (section 2's census: 0 of
222 contain `{` at all, so a fortiori none contains a token).

So: `SENDER_FULL_NAME` exists in this repository only as a statement that it is
absent from the provider's signature fields, and in provider-side template text
on one archived campaign. Both are consistent with an operator-side bulk edit
in the EmailBison UI, and neither is evidence that the provider resolves it.

**THE ANSWER FOR THE RAMP.** The confirmed instrument is
**`{SENDER_EMAIL_SIGNATURE}`**, not a name variable. It is better than one on
the measurement: it resolves the WHOLE sign-off from the mailbox's own stored
field, and all 222 mailboxes already store that field in the exact two-line
shape our renderer composes — `<Owner Full Name>` then `Productive`. A name
variable would still leave the company line to us. If a bare name is
nonetheless wanted, `{SENDER_FIRST_NAME}` is confirmed and
`{SENDER_FULL_NAME}` is not.

---

## 2. HOW EmailBison APPLIES A MAILBOX SIGNATURE — RE-CONFIRMED, AND THE
##    RESIDUAL IS NARROWED BUT NOT CLOSED

**CLAIM (the one being re-tested).** All 222 mailboxes store a LITERAL
signature, 0 contain `{`, and the provider does NOT append it to a campaign
email on its own.

**AUTHORITY.** `GET /sender-emails` fully paged (15/page, 15 pages);
`GET /campaigns/498`; `GET /campaigns/498/sequence-steps`;
`GET /campaigns/498/scheduled-emails` fully paged; and — new, and on the far
side of the SMTP handoff — `GET /replies` walked for 600 rows.

**MEASURED AT** 2026-10-01T10:26Z - 10:40Z.

**STATE — CONFIRMED on every count, independently, and extended.**

*Prior art, agreeing.* `docs/HANDOFF-2026-10-01-CANARY.md` section (e) already
records "signature renders ONCE... all 222 provider-side signatures are literal
text, 0 contain `{`... EmailBison does NOT append one to campaign emails -
three independent live reads." This measurement is a fourth independent read of
the same claim and agrees with it in every figure. What it adds is the
recipient-side evidence below, which is a different KIND of authority rather
than another count of the same field — and the explicit statement that the
residual is still open.

The mailbox census, 222 of 222, provider total 222:

    non-empty email_signature          222   (0 empty)
    signatures containing "{"            0
    signatures containing "{{"           0
    distinct signature strings          11
    signature contains its own
      mailbox `name` field             222   (0 do not)
    mailbox 2778                       i.mamic@withproductive-ai.com
                                       name            "Ivan Mamic"
                                       email_signature "<p>Ivan Mamic<br>Productive</p>"
                                       status Connected, google_workspace_oauth

Campaign 498, which is ours (`record_id` present) and whose templates carry no
sender token — `email_subject: "{SUBJECT_1}"`, `email_body: "<p>{BODY_1}</p>"`:

    scheduled-emails total              26   (10 sent, 16 stopped)
    sent rows containing "Ivan Mamic"    0
    sent rows containing "Ivan"          0
    sent rows with "{" in email_body     0
    sent rows with "unsubscribe"         0
    campaign signature field          NONE   (29 keys, none signature-shaped)
    campaign footer toggle            NONE
    can_unsubscribe                  false
    unsubscribe_text                  null

A sent body ends mid-sentence-of-the-last-copy-paragraph:
`...have you already put something in place for it?</p>`. Nothing follows it.

**THE RESIDUAL, AND WHAT MOVED ON IT.** The objection stands as stated:
`email_body` on a scheduled-email is the provider's RENDERED QUEUE copy, and a
queue copy cannot prove the absence of a splice performed later, at SMTP
handoff. I did not try to settle it with another read of that same field.

Instead there is a second authority nobody had used: **a prospect's reply
quotes the message the prospect's own mail client received.** That text is on
the far side of the handoff. Walking `GET /replies` (600 rows) and keeping only
replies on OUR campaigns whose templates carry NO sender token:

    replies on our no-token campaigns                     31
    ... that quote our original copy back                  7
    ... of those, quoted original contains a two-line
        "<Owner Name> / Productive" sign-off               0
    ... quoted original contains an opt-out phrase         0

Five of the seven are human replies (`automated_reply: false`) from five
different recipients on campaigns 491, 492 and 494, and their quote
attribution lines are in three different formats — `On Sep 22, 2026 at 9:26 AM
-0700, ... wrote:`, `On Tue, 22 Sep 2026 15:31:26 -0400, ... wrote:`, `On Sep
23, 2026, at 7:23 AM, ... wrote:` — i.e. three different mail clients.

One trap inside that measurement, recorded because it nearly produced the
opposite finding: a mailbox owner's full name DOES appear in six of the seven.
Every single occurrence is inside the client's quote **attribution line**
(`On <date>, Bernarda Vrbat <addr> wrote:`), which carries the SMTP From
display name, never a body signature. The adjacency test
`<Owner Name>` immediately followed by `Productive` — the shape a spliced
signature would have — returns **0 across all seven replies and both the
`text_body` and `html_body` of each**. Counting a name hit without checking
its context would have reported a splice that is not there.

**STATE: CONFIRMED that the provider appends nothing, with the residual
NARROWED to the point of implausibility but NOT CLOSED.** What is now required
to believe a splice exists is that five independent mail clients each clipped a
trailing two-line signature while faithfully preserving the final copy
paragraph immediately above it. That is not credible. It is also not proof.

**WHAT WOULD SETTLE IT.** One instrument, and nothing weaker:

> Enrol ONE seed address on a mailbox we control ourselves, let the canary
> send to it, and read the **raw received MIME** from that inbox — headers and
> all parts — comparing the delivered `text/html` and `text/plain` bodies
> byte-for-byte against the `email_body` the provider queued for that same
> `scheduled_email_id`. Equal bodies settle it affirmatively; any trailing
> delta is the splice, named exactly.

A seed send is a send, so it is out of scope for Phase 1 and belongs to the
canary that is being generated. Until that MIME is read, the correct state of
"the provider does not splice at SMTP handoff" is **STRONGLY EVIDENCED, NOT
SETTLED**, and no gate may be written that assumes it.

**AND ONE GENUINELY OPEN HOLE.** Whether campaigns 487, 489 and 493 carry
`{SENDER_EMAIL_SIGNATURE}` in their sequence templates is **UNKNOWN** — they
were not read, by instruction. Each is one GET:
`GET /campaigns/{487,489,493}/sequence-steps`. Until those three are read, "no
campaign of ours carries a provider signature token" is true only of the 34
campaigns actually scanned.

---

## 3. THE DUPLICATE RISK, AS A MEASUREMENT

**CLAIM.** If em1 goes out through mailbox 2778 today, the recipient sees the
signature **ONCE**, with **no unresolved variable**, and with the **WRONG
NAME**. The duplicate risk today is ZERO; it is one operator bulk edit away
from being REAL, and that bulk edit has already happened once in this
workspace.

**AUTHORITY.** Local render through the two named functions, plus the provider
reads above. The render is read-only and spends nothing:

    clients.sender_identity(productive.yaml)
      -> {"company":"Productive","name":"Ivan","role":"founder",
          "works_on":"project profitability for agencies"}
    sendersignature.compose(...)      -> 'Ivan\nProductive'
    trailingcontent.compose(body, ps, signature, cta_link) ->
        <body>
        <blank>
        https://productive.io/get-started/
        <blank>
        Ivan
        Productive
        <blank>
        P.S. <...>
        <blank>
        If this isn't relevant, reply STOP and I'll close the file.

**MEASURED AT** 2026-10-01T10:41Z.

**STATE — ONCE, WRONG NAME.**

    how many times does the sign-off appear?   ONCE
      our side        1  (bisonfactory._variables_for -> trailingcontent.compose
                          writes it into the body_N custom variable)
      provider side   0  (498's template carries no sender token; 498's sent
                          rows carry no appended signature; 5 recipient-side
                          quoted originals carry none either)
    unresolved variable?                       NO
      our path emits no {...} token at all — the signature is a literal
      composed string, and 0 of the 26 rows on 498 contain "{"
    what the recipient actually reads
      From display name   "Ivan Mamic"   (mailbox 2778 `name`; confirmed as the
                                          From name by the reply attribution
                                          lines in section 2)
      body sign-off       "Ivan"         (config `sender.name`)
      stored signature    "Ivan Mamic"   — never reached the email

So the measured defect is not duplication. It is that **one message carries two
different names for one person**: the header says Ivan Mamic and the sign-off
says Ivan. That is the standing rule's violation, and it is section 4.

**WHERE THE DUPLICATE BECOMES REAL.** Two paths, and one of them is not
hypothetical:

  * if the ramp adds `{SENDER_EMAIL_SIGNATURE}` to our sequence templates
    while `_variables_for` still injects a composed signature, the recipient
    reads the sign-off TWICE — once from `body_N`, once from the token. The
    two would not even match today: `Ivan / Productive` then
    `Ivan Mamic / Productive`.
  * **the operator has already bulk-edited `{SENDER_EMAIL_SIGNATURE}` into
    campaign templates in this workspace** — 6 campaigns carry it, and 502's
    step 4780 was edited at 2026-09-25T14:10Z, hours after it was created. Not
    one of those 6 is ours (section 0), so no double signature exists today.
    But nothing in our code or our gates would notice if the next bulk edit
    swept a campaign that IS ours. That is control D, and it is why D cannot
    be a one-time check.

`sendersignature.refuse_if_duplicate(body, signature)` exists and raises
`SignatureDuplicate` on `sig in body`. It is the right primitive and it is
blind to this risk in both directions: it compares our composed signature
against our own body, so it can never see a token in the provider's template
nor a value the provider resolves, and after a name fix it would be comparing
`Ivan Mamic / Productive` against a body that carries
`Ivan Mamic / Productive` resolved by the provider only AFTER we hand the body
over. **The duplicate check has to read the provider's template, not our
body.**

---

## 4. THE NAME MISMATCH

**CLAIM.** `config/clients/productive.yaml` renders `Ivan`; mailbox 2778's
From name, its stored signature and its attested owner are all `Ivan Mamic`.

**AUTHORITY.** `config/clients/productive.yaml` lines under `sender:`;
`GET /sender-emails` row id 2778.

**MEASURED AT** 2026-10-01T10:31Z.

**STATE — CONFIRMED. The file already says so itself.** The `sender:` block as
it stands:

    sender:
      mode: client_rep
      name: Ivan                # client representative
      role: founder
      company: Productive
      works_on: project profitability for agencies

Its own comment block, dated 2026-09-30, records the measurement and the
conclusion: *"AND THE NAME BELOW IS NOT THE MAILBOX OWNER... The engine signs
every one of them 'Ivan'. A message signed with one person's name sent from
another person's mailbox is incident B, so the sending mailbox and this name
must be reconciled before any send."* This measurement agrees with that
comment in every particular, and adds that the mismatch is visible to the
recipient in the same message (From name vs sign-off), not only across
mailboxes.

**THE EXACT ONE-LINE CHANGE THAT WOULD ALIGN THEM — NOT MADE:**

    - line:  `  name: Ivan                # client representative`
    + line:  `  name: Ivan Mamic          # client representative`

in `config/clients/productive.yaml`. That makes
`sendersignature.compose` return `Ivan Mamic\nProductive`, which is byte-equal
to the tag-stripped `email_signature` stored on mailbox 2778.

**TWO CONSEQUENCES THE IMPLEMENTATION MUST CARRY, BOTH MEASURED.**

1. It moves the approval fingerprint. `approval.sender_fingerprint` digests the
   sender block together with the composed signature, so editing `name`
   invalidates every stored approval. Measured today:
   `sender_fingerprint(productive.yaml) = 1c3322421086becf`. CLAUDE.md already
   records 0 of 3,005 stored approvals as valid, so this costs nothing that is
   not already spent — but it must be a deliberate re-approval, not a
   surprise.
2. **It fixes exactly one mailbox and leaves 221.** This is the part a
   one-line change does NOT solve and must not be reported as solving. The
   name census over all 222 mailboxes:

       77  Kresimir Simicic        12  Fran Vizintin
       57  Bernarda Vrbat          12  Ivan Mamic
       17  Riley Parker             6  Bojan Rendulic
       17  Morgan Ellis            (and the balance across 11 distinct
       17  Casey Wright             stored signature strings)

   One `name:` in one client config cannot be correct for eight owners. A
   single config-level name is structurally incapable of matching a 222-mailbox
   estate, which is the actual argument for section 1's conclusion: let the
   PROVIDER resolve it per mailbox with `{SENDER_EMAIL_SIGNATURE}` and stop
   composing the sign-off on our side at all. The one-line change is the
   correct stopgap for a canary pinned to mailbox 2778; it is not the ramp.

---

## 5. THE NEGATIVE-CONTROL MATRIX A–J — SPECIFICATION ONLY

Not implemented. This section specifies what each control asserts, against
which authority, and whether it is a REFUSE before sending or an INCIDENT
after.

**The classification rule, stated once.** A control is a **REFUSE** when it is
decidable from state we hold BEFORE the provider has queued anything. It is an
**INCIDENT** when it is only observable in a provider readback after the fact.
Section 1 added a third, real window that the matrix should exploit: because
the provider renders the queue copy at schedule time and FREEZES it, rows sit
in `sending_paused`/`scheduled` with their final bytes already determined and
not yet delivered. Several controls below are therefore INCIDENT-class by
authority but still catchable as a **REFUSE-TO-RESUME** in that window, which
is strictly better than an apology. Where that applies it is named.

| | control | assertion, exactly | authority | verdict |
|---|---|---|---|---|
| **A** | unresolved variable | For every token `{X}` in the staged sequence template, `X` lower-cased is either a key in the lead's `custom_variables` or a CONFIRMED provider variable from the whitelist `{SENDER_FIRST_NAME, SENDER_EMAIL_SIGNATURE, FIRST_NAME, COMPANY, TITLE, LOCATION, HEADLINE, INDUSTRY}`. Assert the set difference is EMPTY. `{SENDER_FULL_NAME}` is NOT on the whitelist (section 1) and must fail this control until a rendered row resolves it. | `GET /campaigns/{id}/sequence-steps` + `bison.variables_of(lead)`, both pre-attach | **REFUSE** |
| **B** | empty variable | For every token the template reads, the lead's value is non-empty after `strip()`. Note `bison._variables` DROPS empty values rather than sending them blank, so an empty variable is INDISTINGUISHABLE from an absent one at the provider — which collapses B into A at the wire and is why B must be asserted on the mapping BEFORE `_variables` is called. Assert on `_variables_for`'s dict, not on its return value. | the dict inside `bisonfactory._variables_for` | **REFUSE** |
| **C** | unsupported variable | A token naming a variable the workspace has never declared AND that is not on the confirmed provider whitelist. Assert `GET /custom-variables` (FULLY PAGED — it is 24 names on 2 pages, and the module docstring's "twelve" is stale) ∪ whitelist ⊇ every template token. Distinct from A: A is "nothing will fill it for THIS lead", C is "this name does not exist at all". | `GET /custom-variables` paged + template | **REFUSE** |
| **D** | duplicate signature | Assert that the number of sign-off sources for one step is exactly ONE. Count: (i) does `trailingcontent.compose` inject a signature into `body_N`, and (ii) does the sequence template contain any token in `{SENDER_EMAIL_SIGNATURE, SENDER_FULL_NAME, SENDER_FIRST_NAME}`. Assert `(i) + (ii) == 1`. It must read the PROVIDER's live template every run, not a cached copy and not our own body — the operator bulk-edits templates in the UI (502's step 4780 was edited 5h48m after creation) and `sendersignature.refuse_if_duplicate` is structurally blind to that (section 3). | `GET /campaigns/{id}/sequence-steps` + the composer's own inputs | **REFUSE** |
| **E** | token changed after approval | Assert the sequence template's bytes at send time equal those approved. The provider gives a free, exact instrument: each step carries `updated_at`. Bind the step `id` -> `updated_at` pairs into the approval stamp and assert equality before release. Today `approval.fingerprint` covers OUR words and nothing covers the PROVIDER's template, so an operator UI edit between approval and send is invisible — measured as a real event on 502. | `GET /campaigns/{id}/sequence-steps` `updated_at` vs the approval stamp | **REFUSE** |
| **F** | mailbox changed after approval | Assert the mailbox that will send is the mailbox the approval was taken against, by provider `sender_email.id`, AND that its `name` and `email_signature` are unchanged since the stamp. See the gap analysis below — this is the control the existing fingerprint does NOT cover. | `GET /campaigns/{id}/sender-emails` (or the row's `sender_email`) + `GET /sender-emails` | **REFUSE** |
| **G** | raw `{VAR}` in a provider readback | Assert that no queued row's `email_body` or `email_subject` matches `\{[A-Z_]+\}`. Measured baseline: 0 of 15 on 418, 0 of 15 on 502, 0 of 26 on 498 — so a single hit is a true positive, not noise. The row is already rendered when this can be asked, so the words are fixed; but they are not yet DELIVERED. | `GET /campaigns/{id}/scheduled-emails` | **INCIDENT** — and a REFUSE-TO-RESUME while the row is `sending_paused` |
| **H** | no signature in a readback | Assert that each queued row's rendered body contains a sign-off — and name WHICH source it came from, so a pass is not vacuous. If the design is `{SENDER_EMAIL_SIGNATURE}`, assert the tag-stripped body ENDS WITH the tag-stripped `email_signature` of that row's own mailbox. 498's 10 sent rows are the measured failure case: 0 carried one, and nothing noticed. | `GET /campaigns/{id}/scheduled-emails` + `GET /sender-emails` | **INCIDENT** — REFUSE-TO-RESUME in the paused window |
| **I** | wrong sender in a readback | Assert that the owner name appearing in the row's rendered sign-off is the `name` of the row's own `sender_email` and of no other mailbox. The positive control is campaign 331: 31 Kresimir rows and 14 Bernarda rows, each naming only its own owner. The test MUST ignore quote-attribution context when run against reply text — six of seven replies in section 2 carry an owner name only in `On ... wrote:`, and counting those would have inverted the finding. | `GET /campaigns/{id}/scheduled-emails` + `GET /sender-emails` | **INCIDENT** — REFUSE-TO-RESUME in the paused window |
| **J** | mailbox with an empty stored signature | Assert that every mailbox attached to the campaign has a non-empty `email_signature`, BEFORE attaching it. Measured today: 0 of 222 are empty — so this control currently cannot fire, which is precisely why it must exist as a GATE and not as a test. A newly provisioned inbox arrives with the field blank, and under a `{SENDER_EMAIL_SIGNATURE}` design that mailbox sends an email with NO sign-off and no unresolved token to notice. The one failure mode that a green estate hides completely. | `GET /sender-emails`, pre-attach | **REFUSE** |

### What `approval.sender_fingerprint` already covers, and what it does not

The task's framing needs one correction, and it is the load-bearing finding of
this section.

**It does not bind the mailbox.** Read it:
`sender_fingerprint(config)` digests the client config's `sender:` block over
`SENDER_FIELDS = ('mode','name','title','role','company','works_on','email')`
together with `sendersignature.compose(clients.sender_identity(config))`.
Every input is CONFIG-SIDE. Not one provider value is an input.

**COVERED** (and genuinely well — `is_approved` fails closed in every
direction, a pre-binding stamp matches no client, and a config that declares
no sender digests `NO_SENDER_DECLARED` rather than an empty string):

  * the declared sender block — so the one-line change in section 4 correctly
    invalidates every approval; and
  * the rendered signature STRING our composer produces — so an edit to
    `sendersignature.COMPANY_LINE` or to the composer also invalidates it.

**NOT COVERED — all four provider-side facts:**

  1. **the mailbox identity.** `productive.yaml`'s `sender:` block declares no
     `email`, so of the seven `SENDER_FIELDS` the one that could have carried a
     mailbox is absent. Swapping mailbox 2778 for any of the other 221 does
     **not** move the digest — verified by inspection of the inputs. Control F
     is therefore entirely unimplemented, and the fingerprint's name invites
     the opposite conclusion.
  2. **the mailbox's `name`** — the SMTP From display name the recipient
     actually reads (section 2's attribution lines). Not an input.
  3. **the mailbox's stored `email_signature`** — the string a
     `{SENDER_EMAIL_SIGNATURE}` design would put in front of the prospect.
     Not an input. Under that design the fingerprint would bind a signature
     our code composes and NOT the one that is sent.
  4. **the sequence template** — control E. Not an input, and the provider
     offers `updated_at` per step for free.

So: `sender_fingerprint` covers **E and F for our own config**, and covers
**neither E nor F as asked**, because both questions are about provider state.
Its correct description is *the rendered-signature fingerprint of the declared
sender*, and the honest reading of the four gaps is that F cannot be built from
it at all — it needs a second digest over
`(sender_email.id, sender_email.name, sender_email.email_signature,
 [step.id, step.updated_at])`, taken at approval and re-read at release.

---

## 6. SUMMARY TABLE

| # | question | state |
|---|---|---|
| 1 | per-mailbox sender variable | **`{SENDER_EMAIL_SIGNATURE}` CONFIRMED** (resolves the mailbox's `email_signature`, per mailbox, inside a shared template). `{SENDER_FIRST_NAME}` CONFIRMED. **`{SENDER_FULL_NAME}` UNKNOWN** — one archived template, zero rendered rows, never observed resolving. |
| 2 | provider applies a mailbox signature? | **CONFIRMED it does not append one.** 222/222 literal signatures, 0 contain `{`; 498 has no signature field, no footer toggle, no token, and 0 of 10 sent rows carry a sign-off. Extended with recipient-side evidence: 0 of 7 quoted originals carry one. **Residual NARROWED, NOT SETTLED** — needs raw received MIME from a seed inbox we own. |
| 3 | duplicate risk for em1 via 2778 | **ONCE**, no unresolved variable, **wrong name** (From "Ivan Mamic" vs sign-off "Ivan"). Duplicate risk is zero today and one operator bulk edit away; 6 campaigns already carry the token, none of them ours. |
| 4 | name mismatch | **CONFIRMED.** One-line change stated, not made. Fixes 1 mailbox of 222 and invalidates every approval. |
| 5 | matrix A–J | Specified. A,B,C,D,E,F,J = REFUSE; G,H,I = INCIDENT, each also catchable as REFUSE-TO-RESUME in the measured pre-delivery window. |
| — | open UNKNOWNs | 487/489/493 templates unread (3 GETs). `{SENDER_FULL_NAME}` resolution. Whether a splice occurs at SMTP handoff. |

**Safety.** Every provider call was a GET. No send, activate, resume, pause,
enrol, attach or create. No setting changed. No credential printed. 487, 489,
493, 327, 328 and 352 were not read. No source file modified; this document is
the only file created. No prospect name, address or domain appears above.
