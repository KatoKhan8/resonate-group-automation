# INCIDENT 2026-09-25: Resonate's own pitch sent from Productive's mailboxes

**Status: CONTAINED, NOT CLOSED.** 503/504/505 are paused. 491-498 are
worse than anybody thought and are the reason this document is longer than
the incident that triggered it.

> **READ THIS BEFORE THE NEXT EMAIL PUSH.** The copy gate now runs at the
> transport, on the last line before the socket. Nothing in the repository
> mints a certificate yet, so **the next `bisonfactory.stage --live` will
> be REFUSED** with `UncertifiedCopyRefused` at `_ensure_leads`, where it
> writes a lead carrying copy. That is fail-closed and it is deliberate:
> every lead the old path would stage tonight is a lead that fails gates 2
> and 3, and 1,465 of them are already at the provider. Section 6 says
> what has to be built to make a legitimate push pass again.
>
> **LinkedIn is unaffected.** HeyReach lead rows carry no words, so
> `heyreachfactory.stage` is not refused - and for the same reason the
> gate does not cover the LinkedIn copy at all. Section 4, NOT COVERED.

**Nothing in this document was written by a provider write.** Every number
below comes from a GET against EmailBison on 2026-09-25, snapshotted to
`work/review/raw/bison-<id>.json` by `scripts/copy_snapshot.py`, and every
verdict comes from re-running the gates over those snapshots with
`scripts/copy_audit.py`. The snapshots are in `work/`, which is gitignored,
because they are 1,465 real people.

---

## 1. THE NUMBERS, AND THEY ARE THREE DIFFERENT NUMBERS

**76 emails with nothing in them were sent to real prospects. 64 carried
the wrong company's pitch. 685 leads merely contain an ordinary English
phrase that is also on the refuse-list, and those are fine.**

Conflating the three is the easiest mistake available here, and the first
version of this gate made it: matched as bare terms, the operator's list
refuses 286 of campaign 491's 333 leads and catches the incident in none
of them, because Productive's own approved opener is *"I work with
Marketing & Advertising teams on..."*. So the table reports them apart.

| campaign | status | leads | attempted | BLANK rows | blank sent | OUR PITCH | pitch sent | advisory |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 491 | active | 333 | 362 | 93 | 42 | 0 | 0 | 287 |
| 492 | active | 206 | 223 | 45 | 21 | 0 | 0 | 182 |
| 493 | active | 22 | 22 | 0 | 0 | 0 | 0 | 22 |
| 494 | active | 76 | 86 | 14 | 7 | 0 | 0 | 69 |
| 495 | archived | 60 | 42 | 2 | 1 | **5** | **4** | 59 |
| 496 | active | 43 | 3 | 11 | 0 | 0 | 0 | 38 |
| 497 | completed | 20 | 7 | 9 | 5 | 0 | 0 | 15 |
| 498 | completed | 15 | 10 | 4 | 0 | 0 | 0 | 13 |
| **491-498** | | **775** | **755** | **178** | **76** | **5** | **4** | **685** |
| 503 | paused | 250 | 25 | 0 | 0 | 250 | 25 | 250 |
| 504 | paused | 223 | 14 | 0 | 0 | 223 | 14 | 223 |
| 505 | paused | 217 | 25 | 0 | 0 | 217 | 25 | 217 |
| **503-505** | | **690** | **64** | **0** | **0** | **690** | **64** | **690** |

`BLANK rows` are queue rows the provider renders to nothing - empty
subject, `<p></p>` body - counted on the PROVIDER'S RENDERED OUTPUT rather
than on our variables. 178 of them exist on 491-498; **76 have already
been handed to a mailbox and 102 are still queued.**

`OUR PITCH` is phrase-level: `I work with agency founders`, `we run the
outbound side`, `second source of new business`, or the operator's name.
`advisory` is a bare term from the operator's list appearing in copy that
is otherwise the client's own - reported for a human to read, never a
refusal.

`attempted` counts queue rows carrying a `sent_at`, **not** rows whose
status reads `sent`. Two rows on 503 were attempted, reached a real
address and bounced; counting status would have reported 62 where the
operator counted 64.

### Gate 2 and gate 3 still fail on every lead

| campaign set | leads | steps | gate 2 fail | gate 3 fail | both |
|---|---:|---:|---:|---:|---:|
| 491-498 | 775 | 2,325 | 775 | 775 | 775 |
| 503-505 | 690 | 3,450 | 690 | 690 | 690 |

That is the STRUCTURAL failure and it is a different statement from the
three above: **no lead in the estate carries a template id or a quoted
pack fact**, so gate 2's first question and gate 3 refuse all 1,465
whatever else is true of them. It is worth exactly as much as it says -
nothing records provenance yet - and section 6 says what has to be built.

`attempted` counts queue rows carrying a `sent_at`, **not** rows whose
status reads `sent`. Two rows on 503 were attempted, reached a real
address and bounced; counting status would have reported 62 where the
operator counted 64. The two numbers now agree, which is the only reason
to believe either of them.

### 76 BLANK EMAILS, AND WHERE THEY CAME FROM

This is not the copy incident and it reached more people than the copy
incident did. Empty subject, `<p></p>` body, status `sent`, 2026-09-23.

491-498's sequence steps are `{SUBJECT_1}` and `<p>{BODY_1}</p>` - all
copy travels as per-lead custom variables - and **83 leads across those
campaigns carry no `body_1` at all.** The provider renders the absent
variable to nothing and sends the shell rather than refusing.

**The cause is lead-record REUSE, and the provider's own data says so.**
Of those 83 leads:

- **81 already belonged to more than one campaign.**
- **74 were created before their own campaign's build day** - most of them
  on 2026-04-08, five months earlier.
- **2 are neither.**

Against the leads on the same campaigns that DO carry copy: 256 of 287 on
491 belong to exactly one campaign, 252 were created on the build day
itself, and 253 carry the full set of seven custom variables. The
no-copy leads carry two variables, or none.

So the attach path took existing lead ids rather than creating leads, and
never wrote this campaign's copy onto them. That is the same class as the
37-of-120 defect the empty-render gate caught on the 503/504/505 push,
confirmed here from `lead_campaign_data` and `created_at` rather than
assumed.

**Gate 2 now refuses a step that renders to nothing, before it asks
anything else**, and it asks it of the provider's rendered row rather than
of our variables dict - `copyprovenance.renders_to_nothing`. A campaign, a
schedule, a sender and a membership all read correctly for these leads.
Only the rendered queue row shows the email is empty.

### Why each lead failed

Sub-checks, counted independently. A lead usually fails several.

| gate 2 - copy provenance (REFUSALS) | 491-498 | 503-505 |
|---|---:|---:|
| no template id in the lead's custom variables | 775 | 690 |
| **our pitch, at phrase level** | **5** | **690** |
| signed by somebody who does not own the mailbox | 0 | 690 |
| signed, and the mailbox owner cannot be established | 5 | 0 |
| **a step that renders to nothing** | **94** | **0** |
| a step still holding an unresolved `{BODY_N}` | 83 | 0 |

| reported, NOT refused | 491-498 | 503-505 |
|---|---:|---:|
| a bare term from the operator's list, in the client's own approved copy | 685 | 690 |

| gate 3 - pack fact | 491-498 | 503-505 |
|---|---:|---:|
| no pack fact quoted at all - sent generic where it should have been HELD | 775 | 42 |
| the quoted span was cut by the 400-character cap, not closed by its author | 0 | 648 |
| the quoted span asserts nothing: no finite verb | 0 | 210 |
| the quoted span has a verb but no subject in front of it | 0 | 190 |
| the quoted span is an imperative - a button | 0 | 52 |
| named navigation text | 0 | 10 |
| under six words | 0 | 52 |
| a language switcher inside the quote | 0 | 3 |

**The two sets failed in opposite ways and both are serious.**

503-505 quoted the wrong thing: 648 of 690 openers quote a span that no
sentence test can accept.

491-498 quoted **nothing**. All 775 openers are the generic fallback -

> `<First name>, I work with Marketing & Advertising teams on <angle>, and
> I do not know how <Company> handles it`

- a sentence that mentions the prospect only as the thing we admit we know
nothing about, out of a client's mailbox, opening with a phrase on the
operator's own refuse-list. Gate 3 says a lead with no usable pack fact is
HELD. 755 of them were sent instead.

### THE INCIDENT COPY IS ALSO ON A LIVE CAMPAIGN

503/504/505 are not the only campaigns carrying Resonate's pitch.

**Campaign 495 holds 5 leads whose step 3 is the incident copy, word for
word, signed `Zvonimir`. Four of those five have had an email attempted.**

> One more thought. Most founders I speak with have referrals working well
> and nothing reliable underneath them, so a slow month arrives with no
> warning. That gap is the thing we fix. Worth fifteen minutes?
>
> Zvonimir

That is `body_3` from 503/504/505, on an archived campaign in the 491-498
set that nobody was looking at, with no senders bound - which is why the
signature has no owner to be compared against and why it reads
`** NOT RECORDED AT THE PROVIDER **` in the review file. So the count of
real people who received Resonate's pitch out of Productive's mailboxes
is **at least 68, not 64**, and the four extra went out days earlier.

### AND THE FALSE POSITIVES THE FIRST VERSION PRODUCED

Three leads on campaign 494 match `Resonate` and are **fine**: the
prospect company is called Resonate, so the copy reads *"I do not know how
Resonate handles it"* - a correct rendering of Productive's own pitch at a
company that happens to share our name.

682 more match `I work with`, `we run` or `pipeline` and are also fine.
Measured on 491: the bare list refuses 286 of 333 and catches the incident
in **none** of them.

Both now land in the `advisory` column, which the review file prints and
which refuses nothing. That is not the gate going soft - the phrase-level
list still refuses all 690 leads on 503/504/505 and all 5 on 495, and the
signature check refuses them a second time. It is the gate refusing the
thing it was written for instead of the language it was written in.

### The constant signature, measured

| campaign | signature | distinct mailbox owners it was sent from |
|---|---|---|
| 503 | `Zvonimir` | 2 |
| 504 | `Zvonimir` | 3 |
| 505 | `Zvonimir` | 4 |

**The owners are not named here.** They are the client's sending roster -
real people who work at Productive - and `tests/test_fixture_hygiene.py`
forbids their surnames in any tracked file. It caught this document naming
three of them, which is the guard doing exactly what it is for.
`py scripts/copy_audit.py` prints the roster for whoever holds the
credential, which is where it belongs.

56 mailboxes were bound across the three campaigns; **41 of them actually
sent**, and 6 real people own them. That matches the operator's own count
exactly, from an independent read.

---

## 2. WHAT HAPPENED

Four failures stacked, and the fourth is the one that made the other three
irrelevant.

1. **The copy was never rendered from `productive.yaml`.** It was
   hand-written string literals in `work/gencopy.py`, lines 173-183 -
   `"I work with agency founders who want a second source of new
   business..."`, `"We run the outbound side end to end..."`, and
   `"\n\nZvonimir"` appended to step 1 and to every follow-up in the loop
   below it. Read from the file: it contains **zero** references to
   `productive.yaml`, `cadence.TEMPLATES`, `_variables_for` or anything
   named `approved`.
2. **The signature `"Zvonimir"` was hardcoded**, in step 1 and every
   follow-up. Nothing asked who owned the mailbox.
3. **COPYLINT RAN. IT PASSED EVERY ONE OF THEM.** This is the correction
   that matters most, and it is read off the script itself rather than
   assumed:

   ```
   work/gencopy.py:11    from src import copylint
   work/gencopy.py:207   solo = copylint.check_batch([cand], {...})
   work/gencopy.py:211   if solo["refused"] or solo.get("warned"):
   work/gencopy.py:213       dropped["lint:" + ...] += 1;  continue
   work/gencopy.py:217   rep = copylint.check_batch(leads, {...})
   ```

   The lint was called per lead, a failing draft was DROPPED and the next
   candidate taken, and the batch report was printed at the end. So the
   story is not "the lint did not run" - it ran on all 690 and refused
   none of them, because its six rules (`step1_without_pack_fact`,
   `duplicate_first_line`, `untraceable_company_claim`, `empty_step`,
   `dash`, `buzzword`) contain nothing about whose product the copy
   describes or whose name signs it.

   Worse, **rule 1 actively certified the nav chrome.**
   `step1_without_pack_fact` asks whether the opener uses words from the
   lead's pack. The opener quoted `check out a few of our case studies`,
   which IS in the pack - so the rule passed, and the lint's verdict was
   read as evidence the copy was grounded. A gate that asks whether a pack
   fact was used, and never what KIND of span it is, will bless a
   navigation bar every time. That is the whole reason gate 3 exists and
   why it tests the SPAN rather than the fact.

   Two smaller corrections to the brief, both checked: there are **six**
   rules, not seven, and **`finality_before_last_step` does not exist** -
   `grep -rn finality_before_last_step src/ tests/ docs/` returns nothing.
4. **The production gate never ran.** The push used `bison.create_lead` +
   `bison.attach_leads` directly, which bypass `bisonfactory.stage` - so
   `_ensure_leads`, `_refuse_unsupported`, `_approved_copy` and the tenancy
   check never executed on those 690 leads.

The nav-chrome quotes have their own cause. The render used the 400-char
pack cache, and on most pages the first 400 characters are the menu.

    py scripts/packfact_measure.py work/researchpack-us-*.jsonl

    pack rows read          : 22961
    rows that are NOT packs : 4478   (a summary file was in the glob)
    rows carrying facts     : 11645
    rows with a quotable    : 4697   (40.3%)
    rows HELD               : 6948   (59.7%)

**Three fifths of the fact-carrying rows in the cache contain no complete
declarative sentence at all**, and that is after four rules were loosened
for over-refusing real prose - the first version of gate 3 held 70%. Those
are the leads that must be HELD, and there is no version of this system in
which they can be personalised from that cache.

The other two fifths is the answer to "then what do we send": 4,697 rows
do carry a quotable body sentence with a source URL behind it, so a
personalised cohort is still possible at roughly 40% of the size. The
command prints a sample of the accepted spans so a person can read them
and judge whether they are prose, which is the only check that matters and
is not one any of these rules performs.

---

## 3. THE THREE GATES

### Gate 1 - the review file, before any activation

`src/reviewfile.py`. `py -m src.reviewfile 503 --snapshot <file> --packs ...`

Writes `work/review/<campaign>-<date>.xlsx` **and** `.html`: one row per
lead, with sender mailbox, **sender name**, subject and full body of every
step, the pack fact quoted and **its source URL**, and the verdict of gates
2 and 3 per step.

**Every cell is read back from the provider.** Each row says which read it
came from:

- `provider_queue` - `GET /campaigns/{id}/scheduled-emails`, the pre-send
  row with merge fields already resolved. This is the row the provider will
  hand to the mailbox.
- `provider_rendered` - the campaign's stored sequence
  (`GET /campaigns/{id}/sequence-steps`) filled from the **lead's** stored
  custom variables (`GET /campaigns/{id}/leads`). Used where the provider
  has not built a queue row yet. Still two provider reads, never ours.

A step with no copy prints `** NO COPY AT THE PROVIDER **` and an unbound
lead prints `** NOT BOUND YET: one of N mailboxes (...) **`. Nothing is
left blank, because a blank cell reads as "fine".

**`bisonfactory.stage` builds one on every push**, last, after
`_ensure_leads`, from five provider reads - because a generator nothing
calls is a generator that will not be there the next time somebody pushes
690 leads. It never raises out of `stage`: a run that staged and then
failed to write a spreadsheet has still staged, and the report carries
either the paths or the reason. `"error"` there is a refusal to ACTIVATE,
not a refusal to stage.

Two barriers point at `work/` from opposite sides - a review file may only
be written there, and a test may never write there - so `work_dir()`
follows `store.queue_path()` rather than a constant. In production that is
`work/`; under `store.use_directory(tmp)` it is the isolated copy; a test
that forgot to isolate is refused by `store.refuse_production_write`.
Hardcoding it would have made every existing staging test drop real
recipients beside the live queue the moment `stage` started building one.

The 22 files for this incident are in `work/review/`.

### Gate 2 - copy provenance

`src/copyprovenance.py`. Three questions, per step, against the words the
provider holds:

1. **Where did this template come from?** The step must carry a template id
   in the lead's custom variables (`template_N`) and that id must be a
   member of `template_ids(config)`, which is **derived** from the client's
   own copy file: the cadence `productive.yaml` names, resolved through
   `cadence.steps_for`, one id per step key. A script cannot mint one
   without reading the client's file, and if it reads the client's file it
   is using the client's copy.
2. **Whose product does it describe?** AT PHRASE LEVEL, case-insensitive,
   on word boundaries: `I work with agency founders`, `we run the outbound
   side`, `the outbound side end to end`, `second source of new business`,
   `agency founders`, `resonate group`, and the operator's name. The
   operator's bare terms - `Resonate`, `outbound`, `I work with`, `we
   run`, `pipeline` - are REPORTED and refuse nothing, because measured
   against live 491 they refuse 286 of 333 leads of the client's own
   approved copy and catch the incident in none of them.
3. **Who signs it?** The signature - the last non-empty line, when it is a
   name rather than a sentence - must equal the mailbox owner's name from
   the sender pool. This is the strongest single discriminator and the
   only exact one: `sender.mode: client_rep` means Productive's approved
   bodies end on a question with no sign-off at all, and the sixty-four
   ended `Zvonimir`. `constant_signatures()` additionally refuses one
   literal used across several owners, which is a property only visible
   across a batch.
4. **Does it render at all?** Asked FIRST, because a blank step makes
   every other question moot and because blank is what reached 76 people.
   `renders_to_nothing` is asked of the PROVIDER'S rendered row: an empty
   body, a surviving `{BODY_N}`, or an empty subject on the opening step.
   A threaded follow-up legitimately carries no subject of its own.

`certify()` runs all three and returns the custom variables to stage,
including a SHA-256 over the exact words, the client and the owner.
`verify_certificate()` checks that the certificate still covers the copy in
a payload. A boolean flag would have been a boolean anybody could set; a
fingerprint over copy that passed is the check itself.

### Gate 3 - the pack fact

`src/packfact.py`. A quoted span must be a **complete declarative
sentence** from a page body. Nine named rules, each individually removable
in a test:

`terminator` - the span must end on `.`/`!`/`?` **inside** the snippet. A
span running to the end of a 400-character snippet was cut by us, and we do
not know what it said. This one rule refuses 648 of the 648 spans that
shipped.

`declarative` - the verb must be FINITE and must have a SUBJECT IN FRONT OF
IT. `check out a few of our case studies` has a verb. So do `Book a
Meeting`, `Request a Demo` and `Get started`. Nav chrome is imperative and
body prose is declarative, and that is the distinction that separates them.

`capitalised_run` - four capitalised words in a row is a navigation bar,
even when the sentence bolted onto the end of it has a subject, a verb, a
full stop and a title-case ratio under half.

Plus `length`, `subordinator`, `nav_marker`, `nav_glyph`,
`language_switcher`, `title_case`.

**If no span in the pack passes, `choose()` raises `Held`.** There is no
generic fallback. The generic fallback is what shipped 755 times.

---

## 4. WHERE THE GATES RUN, AND WHAT IS NOT COVERED

The lint existed and did not fire because the push route did not call it. A
gate that only lives in `bisonfactory.stage` is a gate any script can walk
around, and one did.

Six refusals live inside that one call path and every one of them ran zero
times on those 690 leads - the workspace tenancy check in `stage` itself,
and `_refuse_unsupported`, `_refuse_bad_greetings`,
`_refuse_colliding_leads`, `_refuse_unvariabled_leads` and
`_refuse_blank_render`, all reached only through `_ensure_leads`. Read the
call sites rather than the names: `grep -n "_refuse_.*(" src/bisonfactory
.py` shows each one defined once and called once, from inside `stage`.

So the check is at the **provider write**:
`providers.refuse_uncertified_copy(method, url, body)`, called from
`_urllib_transport` on the line after `refuse_unauthorized_write` and
**before the socket**.

It asks one question, which is the only one the transport can ask: do these
words carry a certificate minted by something that knew the client, the
copy file and the mailbox owner?

**It fires on copy that travels WITH A RECIPIENT** - words and an address
in the same payload, which is the exact shape of `POST /leads` and of the
write that caused the incident. Words with no recipient in the payload are
a template; see NOT COVERED.

### COVERED

- Every `POST`/`PUT`/`PATCH`/`DELETE` to a host registered by
  `guard_prospect_facing` - EmailBison and HeyReach - whose payload carries
  words **and** a recipient field, **whatever called it**. That is
  `bison.create_lead` and `bison.update_lead`, reached from
  `bisonfactory.stage`, from `providerwrites.perform`, or from a scratch
  script that imports `src.providers.bison` and posts its own literals.
  **The last one is the whole point**; it is the route the incident took.
- HeyReach's lead routes, if a lead row ever carries words. Today they do
  not - `accountLeadPairs[].lead` is `profileUrl`/`firstName`/`lastName`
  and the copy lives in the sequence - so those writes pass trivially, and
  `test_a_linkedin_lead_carrying_words_is_refused` pins what happens on the
  day somebody adds a `message` to a row.

### NOT COVERED - stated, not discovered later

- **`heyreach.set_sequence`.** A HeyReach sequence is real prose with merge
  variables in it and there is **no lead in the payload to hang a
  certificate on**, so this gate cannot cover it - which means the copy in
  a LinkedIn campaign is still gated only by whatever calls
  `heyreachfactory.stage`. `heyreachfactory.stage` was left uncovered by
  the last wiring and the doc said so, which is the only reason anybody
  knew; this is the same statement, made in advance, with a test
  (`test_a_sequence_with_words_and_no_recipient_is_NOT_refused`) that turns
  red if somebody widens the gate by accident instead of on purpose.
- **Anything that does not go through `_urllib_transport`.** A test that
  installs a fake transport with `providers.set_transport` bypasses this
  guard, by design: the fake reaches no prospect. A future provider module
  that builds its own HTTP call would also bypass it, and the existing test
  pinning `WRITE_ROUTES` against declared reads does not cover that.
- **Words already at the provider.** This refuses a WRITE. The 1,465 leads
  staged before it landed are the retroactive audit's job, not this
  function's, and they are all still there.
- **`bison.attach_leads` and `bison.set_sequence`.** Both pass trivially:
  attach sends ids, and the EmailBison sequence is a template of `{BODY_N}`
  merge fields with no words of its own. The copy travels in the lead, and
  the lead is gated. It does mean attaching an already-staged bad lead to
  another campaign is not refused here.
- **Activation.** `bison.activate` is not in `providerwrites.SUPPORTED` and
  this changes nothing about that. Production may not approve its own
  samples.
- **The in-process ceiling, unchanged.** Anything running in this process
  can monkeypatch `refuse_uncertified_copy`, exactly as it can call
  `allow_writes("because I said so")`. This is a guard and an audit trail,
  not a sandbox. The fix for that threat is a separate process with its own
  credentials, and it is still not done.

---

## 5. WHAT WOULD HAVE MADE THIS A FALSE PASS

Each of these was a real way to ship a gate that reports clean. Each has a
test named after it.

**A gate that passes because the field it reads is absent.** Lane S found
this an hour before: all 12,407 rows already carried a `www.linkedin.com`
URL from the supplier, so "does this row have a LinkedIn URL" passed
12,407/12,407 before a single discovery call. Gate 2 therefore refuses a
lead with no template id rather than excusing it, refuses a plausible
invented id (`productive:cold:step1`) because it is not in the set derived
from the client's file, and refuses everything when that set is empty -
the dangerous reading being an empty set that lets everything through
because there is nothing to compare against. `AbsenceIsNotAPass`, both test
modules.

**A count read as a list.** `work/researchpack-us-cohort-2026-09-25.jsonl`
carries `"facts": 3` - an integer - and sits beside three files with almost
the same name carrying the real list. `if pack.get("facts")` scores that
row as having three usable facts without looking at one.
`packfact.facts_of` returns nothing for anything that is not a list of
mappings, and `test_a_count_of_facts_is_not_a_list_of_facts` pins it.

**A refuse-list matched against our render rather than the provider's
stored copy.** `check_lead` takes the lead's custom variables as read back
off the provider, and the review file's
`test_the_queue_wins_over_anything_we_would_render` uses a fixture whose
queue body deliberately differs from the lead's own stored variables - so
a generator that rendered our side would fail it.

**A "complete sentence with a verb" test that a nav bar passes.** The
CHROME fixtures in `test_a_navigation_bar_is_not_a_pack_fact.py` are real
400-character cache entries and real shipped spans. All 648 spans that went
to real people on 503/504/505 are refused, checked by replaying them
through the gate.

**A test that has not been shown to fail when its guard is removed.**
`packfact.reasons_against(span, skip=("declarative",))` runs the gate with
one named rule removed. `SINGLE_RULE` holds, for **every** rule, a real
cached span that that rule ALONE refuses - found by walking the cache and
keeping spans where exactly one rule fired, which is what
`py scripts/packfact_measure.py work/researchpack-us-*.jsonl --isolate`
does and what it will keep doing when a rule stops earning its place - and
the test
asserts both that the span is refused with the rule and accepted without
it. The transport test does the same to the wiring: it neuters
`refuse_uncertified_copy` and requires the incident payload to reach a
booby-trapped `urlopen`.

**A guard whose lookup erases the thing it looks for.** The contraction
rule accepts `We're one flat, integrated team...` because `we're` carries
its own subject and verb, and it stripped punctuation before the lookup -
which folds `it's` onto `its`, `we'll` onto `well` and `I'd` onto `id`.
A menu reading `Our Products and its Features` then satisfied the
declarative rule by containing a possessive pronoun. The token must carry
an apostrophe to count, and `test_a_verb_alone_does_not_make_a_sentence`
plus the CHROME fixtures pin both halves.

**A REFUSE-LIST THAT REFUSES THE CLIENT'S OWN COPY.** The largest one, and
it was caught by measurement rather than by reading. The operator's list
taken as bare terms refuses 286 of campaign 491's 333 leads - Productive's
approved opener contains `I work with` - and catches the incident in NONE
of them. A gate that refuses 86% of a client's approved copy and 0% of the
thing it was written for is not strict; it is the gate somebody switches
off next week. `ABroadWordIsNotTheIncident` holds the client's real opener
and requires it to PASS while the incident copy fails.

**A blank email counted as a copy problem.** 76 emails with nothing in
them were sent - more than the 64 that carried the wrong copy - and the
first version of this gate reported them inside the same "refused term"
bucket as an ordinary English phrase. They are now their own refusal,
asked first, of the provider's rendered row, counted in their own column,
and traced to their own cause.

**A rule that is quietly refusing real prose.** The opposite failure, and
it is how a lint gets widened later by somebody who needs a draft to pass.
Four rules were found over-refusing against the real cache and were
corrected against it, each with its own comment in the source: `case
studies` / `our work` / `careers` as nav markers (they refused *We check
every one of our case studies before we publish it.*); `it`, `no`, `he`,
`hi` as language codes (they refused a sentence containing "it" twice);
`since`/`when` as subordinators with no main-clause test (they refused
*Since 2006, we have helped...*); and a missing base verb form (it refused
*We solve the complexities of enterprise Oracle environments.*, the one
real sentence in its whole cached fact). The PROSE fixtures pin all four.

---

## 6. WHAT IS NOT FIXED

**1,465 staged leads are still at the provider and all of them fail.** The
gates refuse a WRITE; they do not retract a stage. 491-498 are live and
have attempted 755 deliveries. **That is an operator decision, not a lane
decision**, and the review files in `work/review/` are what it should be
made against.

**Nothing has been regenerated, and the next staging run will be refused.**
No lead in the estate carries a `template_N`, a `copy_certificate` or a
`pack_fact_source_url`, so every lead fails gate 2's first question and
will keep failing it until copy is minted through
`copyprovenance.certify`. **Nothing calls `certify` yet.** This lane added
the gate, the wiring and the review file; it did not add the path that
mints a certificate, because that means changing what `generate` and
`bisonfactory._variables_for` produce and that is a bigger change than an
incident response should make at once.

The consequence is concrete and is stated here rather than discovered:
**`bisonfactory.stage --live` will now fail at `_ensure_leads` with
`UncertifiedCopyRefused`**, because the lead payload carries copy and no
certificate. That is the correct direction - fail closed - and it is also
a thing that will surprise somebody at 3am. The next piece of work is
`_variables_for` calling `certify` with the step's cadence key as its
template id and the bound mailbox's owner as the signature, which is the
point at which a legitimate push starts passing again.

**`I work with` IS IN THE CLIENT'S OWN APPROVED TEMPLATES, and the gate no
longer refuses it - it reports it.** Two templates in `cadence.TEMPLATES`
that the client's cadence selects carry the phrase:

```
comparable_proof   "the teams I work with that look most like {company}"
linkedin_intro     "hi {first_name}, i work with {sector} teams on ..."
```

`linkedin_intro` is the LinkedIn connection note - the first thing a
prospect ever reads from this system. Refusing on the bare phrase would
stop every legitimate campaign this client runs, which is why `advisory`
exists and why 685 of the 775 live leads land there rather than in the
refusal column.

**The decision that is still owed** is whether that phrasing should stay
in the client's templates at all, given it is also the opening of our own
pitch. Narrowing the gate does not answer it; it only stops the gate being
the thing that forces the answer. A lane does not edit a client's approved
copy, and the review file now shows an operator exactly which leads carry
it.

**`src/copylint.py` still has no caller inside `src/`.** The only thing
that ever called it was the scratch script that caused this, which is its
own comment on where the gates were. It answers different questions from
these three - duplicate first lines and untraceable specifics are real
and neither gate 2 nor gate 3 asks them - so it is still wanted, wired
into the same place. Not done here.

**FOUR MAILBOX OWNERS ARE OUTSIDE THE NAME GUARD.**
`tests/test_fixture_hygiene.py` forbids the client's sending roster by
surname, and it caught this lane naming three of them - which is the guard
working. But the list is hardcoded and the roster is not: four surnames on
the sender pools of these eleven campaigns are on no list, so a document
naming one of them passes every test in this repository.

`py scripts/copy_audit.py` now reports them every run (surnames only, to a
terminal, which is not a tracked file). **They are deliberately not added
to `FORBIDDEN_NAMES` here**: three of the four are already named in
operator-authored documents under `docs/` as mailboxes the register
EXCLUDES, so adding them turns those documents red, and whether each is a
real person or a persona is the operator's answer rather than a lane's.

**Sixteen prospect domains are already committed to git.** The redaction
self-test (`scripts/copy_audit.py`, run after the review files are written)
takes the 2,820 distinct recipient addresses and domains from these eleven
campaigns and searches every git-tracked file, each file against every
value. No file written by this lane carries one. Sixteen files that were
already in the repository do:

```
docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D4.md                        1
docs/state/PROBLEM-REGISTER.md                                    1
scripts/batch1_build.py                                           1
src/bisonfactory.py                                               5
src/slackagenttools.py                                            1
tests/test_a_cohort_name_in_prose_is_not_a_planted_greeting.py    5
tests/test_fixture_hygiene.py                                     1
tests/test_what_is_happening_with_this_account.py                 1
```

**The domains are deliberately not written here.** This document is
committed, and a leak report that quotes the leaked values is the leak
again with a heading on it - the first draft of this section listed all
eight and failed its own self-test. Run `py scripts/copy_audit.py` to see
them; the file names and counts are enough to act on.

These are live prospects of a client, in a pushed repository, put there as
examples by earlier work. They are domains rather than addresses, which is
the lesser half of the problem and still the client's list. Not fixed here
- they are in four other lanes' files - and the self-test exits non-zero
until they are.

---

## 7. HOW TO RE-RUN ANY OF THIS

```
# provider truth, reads only
py scripts/copy_snapshot.py 491 492 493 494 495 496 497 498 503 504 505 \
    --out work/review/raw

# the table in section 1, plus the redaction self-test
py scripts/copy_audit.py --packs work/researchpack-us-*.jsonl

# one campaign's review file
py -m src.reviewfile 503 --snapshot work/review/raw/bison-503.json \
    --packs work/researchpack-us-cohortJ-2026-09-25.jsonl

# gate 3 against the real cache; --isolate rebuilds the SINGLE_RULE table
# the guard-removal test is built on; --shipped replays the 648 spans that
# went to real people and exits non-zero if any is accepted
py scripts/packfact_measure.py work/researchpack-us-*.jsonl
py scripts/packfact_measure.py work/researchpack-us-*.jsonl --isolate
py scripts/packfact_measure.py --shipped work/review/raw

# the gates
py -m unittest tests.test_a_navigation_bar_is_not_a_pack_fact \
    tests.test_client_copy_may_not_describe_our_own_business \
    tests.test_the_transport_refuses_words_no_gate_certified \
    tests.test_a_review_file_reads_the_provider_and_stays_in_work
```

`scripts/copy_snapshot.py` reads `RESONATE_ENV_FILE` when it is set, because
a worktree has its own root with no `config/.env` in it and a lane running
from one otherwise makes every call unauthenticated. It is READ; nothing
here writes a credential file.
