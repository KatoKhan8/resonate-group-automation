# Merge request — the reply is the unsubscribe

Branch `worktree-agent-a229ee3cba3357ce9`, one commit, in its own worktree.
**Not pushed, not merged.** No provider write, nothing written to `work/`, no
credential read, no real prospect address or name in any tracked file.

> **OPERATOR DECISION, 2026-09-24.** *There will be no unsubscribe link in any
> campaign. The opt-out mechanism is the REPLY.*

That makes `src/replies.py` the only thing standing between a person asking to
be left alone and us continuing to mail them. This is what it took to build it
to that standard, and — the part that matters more — what it still does not do.

---

## 0. `RULE_HASH` MOVED, AND THAT IS THE CORRECT OUTCOME

    before   rules-4+63ac5f605770
    after    rules-4+d4ddb2f3dc53

`replies.RULE_HASH` is derived from every `*_PATTERNS` group plus `RULES`'
order and confidences, so a pattern edit moves it by construction. **Every
verdict stored before this change stops being confirmable**, which is exactly
what `replyverdict.is_confirmed` is for: the rules moved, the release name did
not, and a verdict made by the old rules is no longer evidence about the new
ones. `confirmed_positives` will read zero until new verdicts accumulate. Do
not work around it.

`VERSION` stays `rules-4`. It is a release name and was never an identity.

---

## 1. WHAT WAS THERE, MEASURED

`UNSUBSCRIBE_PATTERNS` held **14 entries, every one English**. Against that,
the live estate measured on 2026-09-24:

| source | rows | what it says |
|---|---:|---|
| `work/qualified-supply.jsonl` | 32,951 | the sourced pool spans exactly **20 countries** |
| `work/learning-replies.jsonl` | 179,715 | replies have arrived from `.de .pl .cz .fi .nl .ch .be .se .no .fr .ie .at .dk .lt .it .si .es .ee .rs .lv .hu .hr .gr` |
| `work/queue.jsonl` | 1,582 | our own estate carries `.de .se .nl .dk .pl .si .fi .no .fr .gr .hu .cz .at .lt .ch .it` |

So the languages are **derived, not chosen**. `replies.LANGUAGE_COVERAGE`
carries the mapping and
`tests/…_in_every_language_we_send_to.py::TheLanguagesAreDerivedFromWhereWeActuallySend`
reads the real supply file when it is present and **skips loudly** when it is
not, rather than passing on an empty check.

### 1a. The real corpus, and how thin it is

The only inbound reply TEXT on this machine is `work/reply-drafts.jsonl` —
**28 real bodies** EmailBison delivered on 2026-09-22/23. It is real and it is
small. Everything else is gone or textless:

- the TASK-058 HeyReach conversation cache (`%TEMP%/task058_cache`,
  `task067_dataset`) is **empty** — both directories exist with zero files;
- `work/learning-replies.jsonl` is 179,715 rows of `{reply_id, campaign_id,
  lead_id, domain, received_at, interested, automated}` and **no text at all**;
- `work/watch-events/*.jsonl` is 1,922 log lines, no bodies;
- **no provider credential is available to this session.** `BISON_KEY` and
  `HEYREACH_KEY` are the real names (`config.VARIABLES`) and both are unset
  here; the running loops have them, this shell does not. Nothing was guessed
  and no key was hunted for.

**So the honest position is: English opt-out phrasings are OBSERVED in our own
corpus; non-English ones are ATTESTED from outside it.** Section 4 says exactly
what "attested" means per phrase, and the test file records the tag on every
single one.

### 1b. What the 28 real replies classified as, before and after

One verdict changed. One.

    #11  "no. stop."      unknown 0.00   ->   unsubscribe 0.95

Every other verdict is byte-identical: 9 `out_of_office`, 3 `negative`,
3 `not_relevant`, 1 `automated`, 1 `positive`, 1 `referral`, 8 `unknown` (all
of them foreign-language autoresponders, which is a different problem and is
out of scope here).

**`"no. stop."` is a real person answering a live sequence with three words,
and it was invisible.** It is the entire justification for this change and it
is the fixture the new tests are built on.

---

## 2. THREE DEFECTS FOUND ON THE WAY, EACH REPRODUCED

### 2a. The quote header wraps, and that defeated every whole-message anchor

`_ON_WROTE = r"^On .+\bwrote:"` cannot match a Gmail attribution that wraps:

    no. stop.

    On Tue, Sep 22, 2026 at 3:34 PM <our sender> <…>
    wrote:
    > Hey <first name>,

`.` does not cross a newline, so the header was never recognised, the quote
start fell through to the first `>` line, and `extract_prospect_text` returned
**94 characters instead of 9** — the reply *plus* the attribution.

That is not cosmetic. `^stop$`, `^no$`, `^nope$` and every standalone opt-out
token are anchored precisely so a risky one-word pattern cannot fire inside a
sentence; an extractor that leaves a quote header attached means the anchor
never gets the chance. Bounded fix: at most two continuation lines, 200
characters each.

### 2b. `inbound.ingest` did not save an unattributable reply's state

    if own and any(o["applied"]["status"] == "applied" for o in outcomes):
        store.save(recs, expect_digest=base)

`handle` writes real state for a reply it refuses to attribute — a hold on
every record carrying that person, and now a suppression. Both are in-memory
mutations of `recs`, and the only save was gated on some event **in the same
page** having matched a record. A page whose replies were all unattributable
**saved nothing**.

It never showed as a failure because
`test_a_reply_stops_a_person_on_every_record` calls `handle` directly and
writes the records back itself (`with store.transaction() as rows: rows[:] =
recs`) — the test supplies the save that production does not. Now asked as
"did anything change" rather than "did anything match", and a new test goes
through `ingest` and re-reads the file.

### 2c. A bare `gdpr` made a buying question an unsubscribe

    classify("Is your platform GDPR compliant?")  ->  unsubscribe 0.95

`\bgdpr\b` matched and UNSUBSCRIBE outranks QUESTION and POSITIVE. **This was
already wrong and this change makes it far more expensive** — an unsubscribe
is now permanent and agency-wide, so that false positive would make a prospect
who asked a compliance question unreachable by every client we have, for good.

**This is the one existing pattern I narrowed, and I am flagging it because
narrowing is close to weakening.** It is narrowing for PRECISION, which
TASK-076's note explicitly permits and distinguishes from widening for recall.
The regulation's name now has to sit beside an act — delete, erase, remove,
object, withdraw, opt out — and nothing real is lost, because a reply whose
entire content is the bare word is still caught by the standalone-token tier.

---

## 3. THE DESIGN: TWO TIERS, AND THE SECOND ONE IS THE SAFETY ARGUMENT

Four independent sourcing passes arrived at the same rule, and so had this
module two days earlier when it removed the bare English `stop`:

**Tier A — `OPT_OUT_PHRASES`, safe anywhere.** Multiword, usually
first-person, carrying its own context: `me desinscrire`,
`borrenme de la lista`, `aus dem verteiler streichen`,
`non voglio piu ricevere`, `zahtevam izbris podatkov`, `wnosze sprzeciw`,
`leiratkoz-`.

**Tier B — `STANDALONE_STOP_PATTERNS`, one clause and nothing else.** Every
token in it is an ordinary word in its own language:

| token | what it ordinarily means | counter-example that must not suppress |
|---|---|---|
| `stop` (en, de, nl, da, no, sv, pl, it, hr, sl, el) | halt; an alloy in Polish; a ban in Italian headlines | "Can you stop by our office next week?" |
| `abmelden` (de) | **log out** | "Bitte melden Sie sich vom System ab." |
| `abbestellen` (de) | cancel a delivery | "Wir möchten die Lieferung für März abbestellen." |
| `austragen` (de) | to HOLD an event | "Der Wettkampf wird in Berlin ausgetragen." |
| `afmelden` (nl) | decline a meeting | "Ik moet me afmelden voor de meeting van donderdag." |
| `uitschrijven` (nl) | issue a tender | "We gaan een tender uitschrijven." |
| `arret` (fr) | **sick leave**, in an out-of-office | "Je suis en arrêt maladie jusqu'au 12." |
| `baja` (es) | **sick leave**, in an out-of-office | "Estoy de baja hasta el 15 de marzo." |
| `sair` (pt) | to leave / to come out | "O relatório vai sair amanhã." |
| `avsluta` (sv) | end a meeting | "Kan vi avsluta mötet 15:00?" |
| `lopeta` / `peru` (fi) | end production / cancel a meeting | "Lopetamme tuotannon ensi vuonna." |
| `odhlasit se` (cs, sk) | **log out** | "Musím se odhlásit z portálu a přihlásit znovu." |
| `wypisz` (pl) | issue an invoice; a register extract | "Potrzebuję wypis z KRS." |
| `atsisakyti` (lt) | decline an offer | "Turėsiu atsisakyti susitikimo." |
| `atteikties` (lv) | decline an offer | "Diemžēl mums jāatsakās no šī piedāvājuma." |
| `odjava` (hr, sl) | logout, hotel check-out, deregistration | "Odjava radnika iz HZMO-a je u tijeku." |
| `διαγραφη` (el) | deletion of anything; expulsion | "θέλουμε διαγραφή του τελευταίου όρου από τη σύμβαση" |

**A clause, not the whole message.** `^stop[\s.!]*$` was the whole message and
the estate's one real bare-stop reply is `"no. stop."` — two clauses. A
signature with no `--` separator defeats it the same way. The clause must be
EXACTLY the token (plus an optional politeness word), which is what keeps
"please stop asking", "stop by our office", "we had to stop the project" and
"full stop" out: in each of those the clause is longer than the token.

### 3a. Where I refused to add a token, and why

- **Italian `basta`. Refused outright, in every form.** It means "that is
  enough" AND "it suffices", and the second is standard business Italian in
  sentences that are *buying signals*: "basta che mi confermi la data",
  "mi basta sapere il prezzo". There is no anchoring that separates them.
- **Spanish `alto`, `parar`, `detener`.** Attested only as SMS keywords. In
  prose `alto` means tall/senior ("un alto directivo") and the other two are
  ordinary verbs.
- **Bare cancel-verbs in every language** — `cancelar`, `cancellare`,
  `annuler`, `annuleren`, `absagen`, `zrusit`, `atsaukti`, `torol`. They are
  overwhelmingly about a MEETING, and "I need to cancel Thursday's call" is a
  live deal.
- **"Not interested" in every language** — `nie jestem zainteresowany`,
  `nemám zájem`, `nem érdekel`, `non sono interessato`, `no me interesa`,
  `kein Interesse`. They are answers about the offer, they are already
  NEGATIVE, and an unsubscribe is permanent and agency-wide where a refusal is
  neither. Hungarian `nem aktuális` in particular means "not right now".
- **Bare `no` as a whole message.** Kept as NEGATIVE. It answers whatever
  question was asked and both readings are real.
- **Serbian CYRILLIC and Greeklish.** Not covered, named as not covered. The
  fold is one-character-in-one-character-out by design (§3b), which cannot
  transliterate `њ`; and Greeklish transliterations are inconsistent
  (`θ`→`th`/`8`, `ξ`→`ks`/`x`/`3`), so enumerating them would be guessing. The
  mitigation is real but partial: speakers of both routinely type
  `unsubscribe` in Latin, which Tier A catches.

### 3b. The fold, which is ISSUE-024's fix generalised

ISSUE-024 read `#računi` past an English safety list. `slack_history.py` fixed
it with a five-character Croatian translation table. `replies.fold()` is the
same idea for twenty languages: NFD, drop combining marks, plus an explicit
table for letters NFD does not decompose (`ß ø æ œ đ ð þ ł ı`).

**It is one character in, one character out**, which is why `ß`→`s` and not
`ss`. Evidence is sliced out of the ORIGINAL text by the match's own offsets,
so an alert shows what the person actually typed, accents and all — and that
only works if folding cannot move an index. A test asserts the length is never
changed, and another asserts every shipped pattern is **already in folded
form**, because a pattern that is not could never fire and would look exactly
like a language nobody writes an opt-out in. That is the redaction-filter
discipline: self-test the filter against every value.

Greek stays Greek. `Διαγραφή` folds to `διαγραφη`, never to `diagrafi`.

---

## 4. LANGUAGES COVERED, AND HOW THE PHRASINGS WERE SOURCED

Provenance is recorded **per phrase** in
`tests/test_an_unsubscribe_is_read_in_every_language_we_send_to.py`:

    OBSERVED   verbatim from work/reply-drafts.jsonl, our own inbound corpus
    REPLY      a person-written reply in a public mailing-list archive
    LABEL      the exact words on a real unsubscribe link or button
    REGULATOR  a DPA's or consumer authority's own wording
    TEMPLATE   a GDPR Art. 21 / Art. 17 letter published to be copy-pasted

| lang | countries | status | principal sources |
|---|---|---|---|
| en | US UK IE AU NZ CA | full | our own corpus; ICO; datarequests.org; Klaviyo; Twilio keyword set |
| de | DE AT CH | full | Gmail DE; CleverReach; Inxmail; absolit.de; datenanfragen.de; Verbraucherzentrale Niedersachsen |
| fr | FR BE CH CA | full | Gmail FR; **CNIL model letter**; postgresql.org and debian-user-french archives; BetterPic support |
| nl | NL BE | full | Gmail NL; SeniorWeb; OSM talk-nl / talk-be archives; **Belgian GBA** |
| it | IT CH | full | Gmail IT; TheBlondLawyer; 4DEM University; OSM talk-it-fvg |
| es | ES | full | Gmail ES; postgresql.org archive (two real reader replies); OSM talk-latam |
| pt | PT (+BR vocabulary) | **partial** | Gmail pt-PT/pt-BR; RD Station; OSM talk-br. Only ONE real pt reply sentence could be attested |
| sv | SE | full | Gmail sv; **IMY** (incl. its Art. 21 letter template) |
| da | DK | full | Gmail da; **Forbrugerombudsmanden**; Forbrugerrådet Tænk; Version2 |
| no | NO | full | Gmail no; **Datatilsynet**; **Forbrukertilsynet**; MENY |
| fi | FI | full | Gmail fi; **tietosuoja.fi**; **KKV**; TEM; Smaily |
| et | EE | full | Gmail et; **AKI**; Smaily; Curaprox EE |
| pl | PL | full | Gmail pl; WP.pl; Interia; **niebezpiecznik.pl**; infor.pl Art. 21 and consent-withdrawal templates |
| cs | CZ | full | Gmail cs; **ÚOOÚ FAQ**; Ecomail |
| sk | SK | **partial** | Gmail sk; **dataprotection.gov.sk**; Websupport; techbox.sk. No attested Slovak consumer REPLY sentence exists on the open web |
| hu | HU | full | Gmail hu; SalesAutopilot; Listamester; hrabovszkyconsulting |
| lt | LT | full | Gmail lt; bite.lt; **rplc.lt** rights-procedure; bonusway.lt |
| lv | LV | **partial** | Gmail lv; **Datu valsts inspekcija**; data.gov.lv; inbox.lv. No attested Latvian reply sentence |
| hr (+sr, bs) | HR RS BA | **partial — Latin only** | Gmail hr; artrea.com.hr; marker.hr; **AZOP**; osobnipodaci.org Art. 21 and Art. 17 templates |
| sl | SI | full | eu-skladi.si; Lidl SI; natura2000.gov.si; **Informacijski pooblaščenec**; tiodlocas.si |
| el | GR | **partial — Greek script only** | Gmail el; **Greek DPA (dpa.gr)**; lifo.gr (a real reader complaint) |

**Coverage against the measured supply: 20 of 20 countries.** Four languages
are PARTIAL and say why in `LANGUAGE_COVERAGE` itself; two scripts are not
covered at all.

**What was deliberately NOT shipped.** Phrasings that four sourcing passes
could not attest — Swedish "ta bort mig från listan", Croatian "maknite me s
liste" / "prestanite mi slati", Slovenian "odjavite me" / "ne pošiljajte mi
več", Slovak "odhláste ma z odberu" as a reply, Latvian "lūdzu izslēdziet
mani", Hungarian "ne küldjenek több e-mailt", Lithuanian "nebesiųskite",
Portuguese "não quero mais receber e-mails", and the English "leave me alone",
"this is spam", "please don't email again", bare "unsubscribed". They are
obviously real. **They are not in the classifier and they are not in the
test**, because a translation I invented would be indistinguishable from a
measurement once it was in the file. The place to get them is our own reply
corpus, and §6 says what that needs.

---

## 5. SUPPRESSION: DOES IT GENUINELY CROSS WORKSPACES?

**Before this change: no. Not at all.**

`reply.on_unsubscribe` is `(STOP, CONTACT)`, so `effects()` gives the replier
`SUPPRESS` and the account `CONTINUE`, and `_suppress_contact` writes
`unsubscribed = True` **on one contact on one record**. `agencydnc` — the one
mechanism in this system that holds a do-not-contact across a tenancy boundary
— had **no production caller at all**: every `agencydnc.add` in the repository
was in a test file. Its own docstring says so deliberately: *"A reply in one
workspace does not put anybody here."*

**After: yes, and by the only mechanism that can.**
`accountpolicy._suppress_agency_wide` writes the replier's strong identifiers
to `agencydnc` with reason `REQUESTED`, and `eligibility._suppressed` already
reads that list on the send path (it is in `executionguard.SUPPRESSION_REASONS`).

### 5a. "The address AND the account" — the reading I took, stated plainly

`agencydnc.keys_for` takes exactly two kinds of strong identifier and no
others: an email **ADDRESS** and a LinkedIn **ACCOUNT**. Both are written. A
person who opts out by email is not written to on LinkedIn tomorrow by a
workspace that only ever knew their profile URL.

**I did not read "the account" as "the employer".** Three reasons, and the
operator should overrule me if the third is wrong:

1. `agencydnc` **has no kind for a domain or a company**, so a company-wide
   suppression is not expressible in the mechanism that crosses workspaces at
   all. "Across workspaces" can only mean these two identifier kinds.
2. A company-wide removal already has its own classification,
   `account_do_not_contact`, which ranks ABOVE unsubscribe and suppresses the
   record through `_suppress_account`. The two classes are kept apart on
   purpose and at length in `accountpolicy`.
3. Widening one person's removal request into a permanent ban on their
   employer suppresses colleagues who asked for nothing, and no operator can
   take it back from the outside.

**The account IS still held.** `inbound.handle`'s fail-safe pauses the account
on any reply that is not a pure out-of-office, unsubscribe included.

**`account_do_not_contact` DOES carry every colleague across**, and that is
correct rather than an accident: `_suppress_account` already suppressed every
contact on the record individually, so each one's identifiers now cross with
them. The company spoke for them. That is the entire difference between the
two classes, and it is why collapsing them would be a policy change rather
than a tidy-up. Same for an unattributable removal request, where
`apply_reply` already widens to the account because we cannot name who asked —
`uncertainty never narrows` is the existing rule and this follows it.

### 5b. The cross-workspace case was also the case that did nothing

One person worked by two of our workspaces is two records.
`events.match_record` refuses to say which one a reply answers — correctly —
so `inbound.handle` took the `unmatched` branch, and the entire outcome of
"unsubscribe me" from the person hardest to attribute was a **reversible
hold** that an operator clears the moment they have read it.

The refusal is about WHICH RECORD. A removal request does not depend on the
answer. So the text is now classified in that branch — reading costs nothing
and claims nothing — and **only the two stop classes act**: `unsubscribe` and
`account_do_not_contact` suppress everywhere that person is held and write the
agency list; everything else takes the hold exactly as before. No reply event,
no classification event, no claim that any record received anything.

**Nothing is suppressed for somebody we do not hold.** `correspondents`
returning nothing means the reply is not to us — the HeyReach key is
workspace-wide and most of that inbox is the client's own traffic
(REFUTED-006) — and putting a stranger's address on the agency list would
suppress, for every client we have, a person we never wrote to.

### 5c. A failure to write the agency list is recorded, never swallowed

`_suppress_agency_wide` sits inside `apply_reply`, which runs between
`store.digest()` and `store.save(expect_digest=…)` (ISSUE-001). An exception
there would abandon the reply event, the classification and the LOCAL
suppression — trading the strong local guarantee for the weaker global one. So
it is caught, and then recorded as **`AGENCY_SUPPRESSION_REFUSED`** on the
record, with `AGENCY_SUPPRESSION_RECORDED` for the success. Two events, not
one: a removal request that reached only this workspace is a live compliance
gap and must never print the same as success. The same event fires when the
contact carries neither an email nor a LinkedIn profile — there is no strong
identifier to hash, and that is said out loud rather than returned as an empty
success.

**NOTHING ALERTS ON THAT EVENT YET.** It is auditable, not announced: it is in
`events.REPLY_EFFECT_EVENTS` so every consumer of that tuple sees it, and
`replywatch` does not raise on it the way it raises on a refused provider
stop. Wiring that alert is a separate, small change, and claiming it exists
would be the "existence is not function" defect this repository collects. All
three paths were exercised by hand: success writes two fingerprints and
`agency_suppression_recorded`; an `OSError` from `agencydnc.add` leaves
`unsubscribed = True` on the contact and writes
`agency_suppression_refused`; a contact with no email and no profile writes
the same refusal with "no strong identifier".

**The concrete follow-up**, so nobody has to rediscover it:
`replywatch._write_status` already surfaces `stop_refusals` from
`inbound.summarise_stops` with the comment *"a refused stop means somebody may
still be written to after they answered"*. An
`agency_suppression_refusals` field beside it, built the same way, is the
whole of the change — and it is the same sentence one level up: a refused
agency write means somebody may still be written to **by another client**
after they asked us all to stop.

Only hashes are written. No name, no company, no workspace, no record id — the
privacy model in `agencydnc`'s docstring is unchanged.

---

## 6. THE 15 MINUTES: HOW IT IS MEASURED

Three terms, and the file says which are measured:

    1  provider visibility   reply sent -> row readable in the inbox feed
    2  detection             reply_watch_loop --interval 300
    3  ingest + suppress     handle -> classify -> suppress -> agency list
                             -> provider stop

- **Term 2 = 300 s**, read from the loop rather than restated: the test
  reconstructs `reply_watch_loop.main`'s `--interval` default and asserts it,
  and separately asserts `REPLY_POLL_SECONDS`' documented default agrees, so
  the two constants cannot drift apart unnoticed.
- **Term 3, local half: measured in the test**, against a 30 s budget. It is
  classification, a few dict writes, one JSONL append and one queue save.
  Classification itself is **5.8 ms per reply**, measured over 560 runs of the
  28 real bodies with the full 251-pattern unsubscribe row — so a 100-reply
  page costs about 0.6 s, and the budget is two orders of magnitude of
  headroom rather than a guess.
- **Term 3, provider write: 1.694 s**, the max of three live `bison.stop_lead`
  calls measured 2026-09-23 against leads already terminal in campaign 492.
  Carried over from
  `test_a_linkedin_reply_stops_email_inside_fifteen_minutes.py` rather than
  re-derived, because two copies of one measurement drift.

    worst case = 300 + 1.694 + 30  =  331.7 s   against a 900 s gate
    headroom for term 1            =  568 s     (asserted > 8 minutes)

**Term 1 is UNMEASURED and this document does not pretend otherwise.** It
cannot be measured without a human sending a real message from a real mailbox.
The test asserts the headroom left for it rather than assuming it away, and
goes red if a constant change ever lets the unmeasured term dominate.

**And "takes effect" means the LOCAL gate, not the provider.** The provider
stop is what stops the queued email; the suppression is what stops every
future campaign in every workspace, and it is the one that is permanent. Both
are inside the same 15 minutes and only one of them can be proved offline, so
the file says which is which.

---

## 7. THE LIST-UNSUBSCRIBE ITEM IS DROPPED

It was planned in exactly two places and both are edited:

- `docs/qwen-tasks/TODO/TASK-271-…md` — the header gate and its four required
  tests are struck. The COMPLIANCE.md half of that task **stands and is
  strengthened**: the document must now say that this estate sets no
  `List-Unsubscribe` header, has no provider field to set one in, ships no
  unsubscribe link, and that the reply classifier is therefore the entire
  opt-out mechanism — with the languages covered, the ones not covered, and
  the 15-minute figure named.
- `docs/LEARNED-FROM-OSS-2026-09-23.md` §6 — same, with the operator decision
  quoted.

The measurement those documents carry stays true and stays useful: the
EmailBison sequence-step payload is
`{order, email_subject, email_body, wait_in_days, active, variant,
variant_from_step, thread_reply}` and there is no mail-header field in it.

---

## 8. FILES, AND THE TESTS

    src/replies.py          the fold, two pattern tiers, 20 languages,
                            LANGUAGE_COVERAGE, the wrapped-quote fix,
                            the GDPR narrowing
    src/accountpolicy.py    _suppress_agency_wide, AGENCY_SUPPRESSION_OUTCOMES
    src/events.py           AGENCY_SUPPRESSION_RECORDED / _REFUSED
    src/inbound.py          removal requests act in the unmatched branch;
                            ingest saves when anything CHANGED
    docs/…TASK-271…md       the header gate dropped
    docs/LEARNED-FROM-OSS-2026-09-23.md   the same
    tests/test_an_unsubscribe_is_read_in_every_language_we_send_to.py   NEW
    tests/test_an_unsubscribe_crosses_every_workspace_inside_fifteen_minutes.py  NEW
    tests/test_a_reply_stops_a_person_on_every_record.py   three assertions
                            moved, see §8a
    tests/test_hygiene.py   the tenancy invariant split, see §8a

### 8a. TWO existing tests changed, and I am saying so rather than burying it

**`tests/test_hygiene.py::test_a_reply_does_not_put_anybody_on_the_agency_list`
asserted the invariant the operator has now overridden** — "client history
stays inside the client's tenancy", of EVERY reply including an unsubscribe.
It is not deleted and it is not weakened. It is split:

- `test_an_ordinary_reply_does_not_put_anybody_on_the_agency_list` now asserts
  it across **ten** outcomes (positive, neutral, negative, not_now, not_icp,
  wrong_person, left_company, existing_client, referral, unknown) — broader
  coverage of the guarantee than the single case it replaced;
- `test_only_a_removal_request_crosses_the_tenancy_boundary` asserts the new
  exception, through `agencydnc.keys_for` rather than a hand-hashed string;
- `test_a_company_wide_stop_carries_every_colleague_across` pins the
  `account_do_not_contact` widening;
- `test_what_crosses_still_leaks_nothing` re-asserts the privacy model against
  the file that is now actually written by a reply — no name, company,
  workspace, profile or outcome word in it, reason `requested`.



`test_a_reply_stops_a_person_on_every_record` reproduces the 2026-09-12
incident with the reply **"please stop, we are not interested"**. That read
NEGATIVE, so the unattributed branch gave it the reversible hold.

`please stop` as a COMPLETE CLAUSE is now an unsubscribe, so that person is
SUPPRESSED on both records rather than held on both. **The outcome got
stronger, not weaker**, and the file's actual subject — being known twice must
not make somebody harder to stop — is more true than it was. The hold path is
still tested, under its own name, with a reply nobody has classified
(`test_an_unclassifiable_reply_is_only_held`). `"please stop asking"` remains
NEGATIVE, because that is one clause and it is longer than the token.

### 8b. Tests

`tests/test_an_unsubscribe_is_read_in_every_language_we_send_to.py` — 18
tests. ~150 attested opt-out phrases across 20 languages, each tagged with its
provenance; **52 real ordinary sentences that must not suppress anybody**,
each with what it actually means; every Tier-B token asserted to fire alone
and asserted NOT to fire inside three carrier sentences; the fold self-tested
against every pattern and every token; the coverage table checked against the
live supply file.

`tests/test_an_unsubscribe_crosses_every_workspace_inside_fifteen_minutes.py`
— 19 tests. The real `"no. stop."` reply; SUPPRESS rather than STOP; both
identifier kinds on the agency list with reason `REQUESTED`; **a workspace
that imports the person TOMORROW is bound**; the send gate honours it; a
refusal and an out-of-office reach the agency list **not at all**; idempotent
on replay; the ambiguous two-record case suppresses rather than holds while
attribution stays refused; `ingest` persists a suppression it could not
attribute; and the clock, computed from the real constants.

### 8c. Suite

Run as a set diffed BY NAME against the same suite with these changes stashed,
both directions. Result recorded in the commit message.

**One pre-existing failure is untouched and is not mine:**
`tests.test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence`
asserts `verdict["classifier"] == replies.VERSION`, which has not been true
since `RULE_HASH` was introduced — it is `rules-4+<digest>`. Verified failing
with `src/replies.py` stashed. Left alone deliberately: it is a stale
assertion about a different decision and fixing it here would be a change
nobody asked for. It belongs in PRODUCT-GAPS or a one-line follow-up.

---

## 9. WHAT THIS STILL DOES NOT DO — read before believing §4

1. **No non-English phrasing here was observed in OUR OWN reply corpus**,
   because no such corpus exists on this machine any more. They are attested
   from labels, regulators, templates and public list archives. That is a real
   step up from invented, and it is not the same as measured.
2. **`ACCOUNT_DNC_PATTERNS` is still English-only.** A German reply saying
   "remove our whole company" classifies as `unsubscribe` — the person is
   suppressed and the account is held, but not company-suppressed. Same defect
   class, one row up the priority table. Out of scope today; it should be the
   next increment and it is smaller than this one.
3. **The out-of-office patterns are still English-only in the BODY.** Eight of
   the 28 real replies are foreign-language autoresponders reading `unknown`.
   `subject_says_out_of_office` covers six languages and is why this is not
   worse. Unrelated to opt-out, named because it is visible in §1b.
4. **Serbian Cyrillic and Greeklish are not covered at all.**
5. **`\bremove me\b` is unchanged and slightly over-broad** — "remove me from
   that thread, wrong Zvonimir" suppresses. It is pre-existing, the operator
   named "remove me" explicitly in the brief, and narrowing the phrase the
   operator named is not a decision I should take unasked.
6. **Nothing here is PRODUCTION_VERIFIED.** No reply has been ingested live
   through this code. Code written is not FIXED and FIXED is not
   PRODUCTION_VERIFIED.

---

## 10. FOR THE REVIEWER

Three questions worth a decision, in order of consequence:

1. **§5a — is "the account" the person's LinkedIn account, or their
   employer?** I took the first and gave three reasons. If the second was
   meant, the change is one line (`reply.on_unsubscribe` from `(STOP, CONTACT)`
   to `(STOP, ACCOUNT)`), it makes `unsubscribe` behave exactly like
   `account_do_not_contact`, and it is not reversible for the colleagues it
   suppresses.
2. **§2c — the GDPR narrowing.** It is the only existing pattern I made
   stricter.
3. **§8a — an existing reproduction test's expected outcome changed** because
   "please stop" is now an opt-out.

---

## APPENDIX — the sources, so the phrasings can be re-checked

Sourced 2026-09-24 by four independent passes. Listed per language so a
reviewer can re-derive any phrase rather than take it on trust. Gmail's own
localisation is used throughout for link labels because it is the wording a
recipient actually has in front of them; the pattern is
`support.google.com/mail/answer/15433283?hl=<lang>`.

**Cross-cutting**

- AWS End User Messaging required opt-out keywords (the only authoritative
  multilingual list found, and it contains exactly one non-English token):
  `docs.aws.amazon.com/sms-voice/latest/userguide/keywords-required.html`
- Twilio default keyword set and its "only words in the message" rule:
  `support.twilio.com/hc/en-us/articles/223134027`
- Klaviyo on why substring matching for STOP is required and what it costs
  ("Don't stop my order" opts the customer out):
  `help.klaviyo.com/hc/en-us/articles/29109965092251`

**en** ico.org.uk right-to-erasure wording · datarequests.org Art. 21 letter ·
groups.csail.mit.edu anti-spam cease-and-desist notice ·
help.klaviyo.com/hc/en-us/articles/35737275447067 · our own
`work/reply-drafts.jsonl`
**de** inetbib.de/austragen · cleverreach.com Abmeldelink · brevo.com/de ·
inxmail.de (what recipients reply to no-reply senders) · absolit.de ·
datenanfragen.de Musterbrief · verbraucherzentrale-niedersachsen.de
**nl** seniorweb.nl · lists.openstreetmap.org talk-nl 2018-11 and talk-be
2013-01 (three real reader replies) · gegevensbeschermingsautoriteit.be
**fr** **cnil.fr/fr/modele/courrier/ne-plus-recevoir-de-publicites** ·
postgresql.org message-id archive · mail-archive.com debian-user-french ·
support.betterpic.io · help.smsfactor.com
**it** theblondlawyer.it · university.4dem.it/article/788 ·
lists.openstreetmap.org talk-it-fvg 2023-09
**es** postgresql.org archive (two real reader replies, incl. the subject
"POR FAVOR NO MAS CORREOS") · lists.openstreetmap.org talk-latam 2016-01 ·
sent.dm Spain SMS guide
**pt** ajuda.rdstation.com Descadastro · privacytech.com.br ·
lists.openstreetmap.org talk-br 2014-01 · anacom.pt (403, partially verified)
**sv** **imy.se** FAQ, objection page and Art. 21 letter template ·
socialchefer.se · adressgruppen.se · support.confetti.events
**da** **forbrugerombudsmanden.dk** · danskerhverv.dk · taenk.dk ·
kaufmann.dk · gjensidige.dk · version2.dk
**no** **datatilsynet.no** nyhetsbrev/epostlister page ·
**forbrukertilsynet.no** · meny.no/nyhetsbrev/avmelding · power.no ·
komputer.no
**fi** **tietosuoja.fi** · **kkv.fi** direct-marketing prohibition ·
tem.fi/tietosuoja-uutiskirjeissa · smaily.com · EiMainoksiaKiitos
**et** **aki.ee** internet-and-web FAQ · smaily.com · curaprox.ee · obo.ee ·
ituudised.ee
**pl** pomoc.poczta.interia.pl · pomoc.wp.pl · pomoc.ecomail.pl ·
**niebezpiecznik.pl** (four real demand sentences) · infor.pl Art. 21 and
consent-withdrawal templates
**cs** **uoou.gov.cz** commercial-messages FAQ · support.ecomail.cz ·
pravopisne.cz (exists because people write both spellings)
**sk** **dataprotection.gov.sk** · techbox.sk · websupport.sk ·
support.westwing.com/hc/sk-sk
**hu** support.salesautopilot.com · listamester.hu ·
hrabovszkyconsulting.hu · blog.fps.hu (documents the leiratkozás/leíratkozás
misspelling)
**lt** bite.lt/profai/naujienlaiskiai-el-paste · topocentras.lt ·
**rplc.lt** rights-procedure · info.bonusway.lt
**lv** **dvi.gov.lv** (two pages) · data.gov.lv · sif.gov.lv ·
help.inbox.eu · lvportals.lv
**hr / sr / bs** artrea.com.hr/odjava.html · marker.hr · cyberfolks.hr ·
**azop.hr** · **osobnipodaci.org** Art. 21 and Art. 17 templates ·
en.wiktionary.org/wiki/odjava (the ordinary senses)
**sl** eu-skladi.si/sl/odjava-od-e-novic · lidl.si · natura2000.gov.si ·
megatel.si/komercialna-sporocila · **ip-rs.si** · tiodlocas.si ·
fran.si (SSKJ² on the four ordinary senses of *stop*)
**el** **dpa.gr** newsletter-unsub and rights pages · lifo.gr/articles/
mikropragmata/117334 (quotes a real Greek marketing email AND a real reader
complaint) · en.wikipedia.org/wiki/Greeklish

**What each pass could NOT find, in its own words:** an attested corpus of
what real people WRITE IN A REPLY, in any language but English. Quoted-phrase
searches for the obvious candidates returned zero pages containing them. That
is why §4's "not shipped" list exists and why §9.1 is the first caveat.
