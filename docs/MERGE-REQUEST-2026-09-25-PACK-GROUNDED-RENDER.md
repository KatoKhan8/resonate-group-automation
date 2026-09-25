# Step 1 re-rendered from each lead's own pack — and the honest yield is 25

Lane H, 2026-09-25. Branch `worktree-agent-a1c6f33167025b67f`.
**Not merged, not pushed. No provider call of any kind.**

**The headline is a small number and that is the point.** Of the 128, **25**
carry a step 1 that quotes a sourced span of that lead's own website. The
other **103 are HELD**. Lane C's 80-of-128 rule-1 pass was real and was also
not evidence of grounding; this replaces it with 25 openers where the
grounding is a verbatim string, and says out loud what the other 103 cost.

Read §1 for the number, §3 for whether it actually moved the defect, §4.1 for
the lever the operator has, and §6 for two findings that are not this lane's
copy and block the push anyway.

Built from: lane B `a68a5813`, lane C `ba2c31b9`, lane D `c38c5934`, this
lane `afd4bda6`. §2.6 says why those shas are in the first paragraph.

---

## 0. DENOMINATORS, ONCE, BECAUSE EVERY NUMBER BELOW NAMES ONE

Reproduced from the stage files, not taken from a document:

| set | what it is | leads | domains |
| --- | --- | --- | --- |
| 927 | lines in `work/stage/s7-copy.jsonl` | 927 | |
| 814 | of those, `state == "rendered"` | 814 | |
| **179** | rendered, UK/EU by `s3-icp.jsonl` country, client-approved | 179 | 153 |
| **128** | of the 179, whose domain has **no record in `work/queue.jsonl`** | 128 | 114 |
| **105** | of the 179, under `batch1_build`'s caps (uk 2×45, eu 1×45) | 105 | 92 |

**128 and 105 are NOT nested.** 54 leads are in both, 74 are in the 128 only,
51 are in the 105 only, 0 are in neither. Any sentence of the form "the 105
is the strongest subset of the 128" is false.

### 0.1 I agree with lane C's derivation of the 128, and reproduced it exactly

    journal rows          927
    rendered              814
    UK/EU rendered+appr   179 over 153 domain(s)
    NO queue record       128 over 114 domain(s)

Same cut, same numbers, run independently against the same three files
(`s7-copy.jsonl`, `s3-icp.jsonl`, `queue.jsonl` through `store.load`). It is
still an inference — the handoff gives the number without a derivation — but
it is the only cut of this data that lands on 128 and I could not construct a
second one that does. **Agreed, as an inference.**

**The 128 are 117 EU and 11 UK/Ireland**: 39 Germany, 26 Sweden, 17 France,
16 Netherlands, 10 UK, 9 Denmark, 6 Norway, 4 Finland, 1 Ireland. That single
fact turns out to dominate §4, and neither lane C's nor lane D's document
mentions it.

---

## 1. BEFORE AND AFTER, PER SET, WITH THE DENOMINATOR ON EVERY ROW

`before` is S7's current `body_1` for that lead, measured against the same
identity-checked pack. `after` is this lane's re-rendered `body_1`. Both call
`copylint.pack_text`, `copylint.first_line` and `copylint._WORD` — the gate's
own functions, called rather than described, so this report and the gate
cannot disagree.

### the 128 (no queue record)

| | leads | carry an admitted fact | rule 1 passes | of those, rest on ONE word | that word is `marketing` | category words only | anchor ≥ 4 words |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **before** | 128 | 97 | **69** | **37** | 9 | 13 | **0** |
| **after** | 128 | 97 | **25** | **0** | **0** | **0** | **25** |

**25 re-rendered, 103 HELD.** Median anchor after: **16 words**, minimum 7.

### all UK/EU rendered + approved (179)

| | leads | carry an admitted fact | rule 1 | single-word | `marketing` | category only | anchor ≥ 4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **before** | 179 | 137 | 105 | 55 | 11 | 20 | 1 |
| **after** | 179 | 137 | **41** | **0** | **0** | **0** | **41** |

41 re-rendered, 138 HELD. Median anchor after: 15 words.

### under the cohort caps (105)

| | leads | carry an admitted fact | rule 1 | single-word | `marketing` | category only | anchor ≥ 4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **before** | 105 | 84 | 67 | 36 | 5 | 12 | 1 |
| **after** | 105 | 84 | **32** | **0** | **0** | **0** | **32** |

32 re-rendered, 73 HELD. Median anchor after: 15 words.

### 1.1 Why my "carry a fact" is 97 and lane C's is 107, reconciled exactly

    of the 128: any cached fact at all        107      <- lane C's number
                carry a site_page fact         97      <- mine
                carry ONLY LinkedIn posts      10      <- the difference

The ten are `person_posts`. `packfacts.identity_of` returns **unverifiable**
for them: the host of a LinkedIn post is LinkedIn's and the row carries no
website field, so it does not say whose post it is. Unverifiable is not a
pass, so those ten accounts have no admitted pack and are held.
**107 − 10 = 97, and the whole difference is the identity rule.**

---

## 2. THE METHOD

### 2.1 What step 1 now says

    {FIRST}, I read {DOMAIN} before writing this rather than after. The
    {PAGE} says "{QUOTE}".

    I work with {INDUSTRY} teams on {ANGLE}. A position that specific is
    usually sold on scope and delivered in hours, and the two only meet at
    month end. Utilisation and margin per project are known after the month
    in which something could have been done about them. The work itself is
    rarely the problem. The visibility into it is.

    Is that roughly how it runs today, or is there already something in
    place for it?

`{QUOTE}` is a **verbatim span of that lead's own site** and `{PAGE}` names
the page it came from. Paragraphs two and three are campaign 489's approved
argument with the two sentences that named the company removed. Rendered:

> Charles, I read harderbetterstronger.com before writing this rather than
> after. The home page says "We design, build and deliver creative events
> and experiences that trigger the right vibe".

> Insa, I read affiliprint.com before writing this rather than after. The
> about page says "Founded in 2010 in Oldenburg, Germany, Affiliprint
> launched with a bold vision: to bridge the gap between online precision
> and offline impact".

The quote sits in the **first line**, which is what `copylint.first_line`
hands to rule 1, so the rule reads the fact rather than the frame.

**Removing `{COMPANY}` from step 1 is deliberate and it closes lane D's
task B at `body_1`.** Lane D measured 280 unsupported specifics, all at
`body_1`, every one the company's own name, because `persona_pain` is the
only template of eight that pairs a direct address with `{company}`. No
sentence in the new step 1 does that, so `untraceable_company_claim` has
nothing at `body_1` to fire on. It does **not** fix `persona_pain`, which is
lane B's file and is still what the other 686 rendered rows carry.

### 2.2 How a quote is extracted, and what is thrown away

Every crawled snippet is ~400 characters with the site's whole navigation
menu on the front. Five stages, all of which throw work away:

1. **Site-wide nav strip.** Every page of one site opens with the same menu,
   so the longest common word prefix across that site's snippets IS the menu.
   Measured: 30 words on sign-specialists.co.uk, 52 on pushon.co.uk — where
   it is the entire snippet, which is how that domain correctly ends up with
   nothing to quote.
2. **Per-page prose scan.** A domain that returned one page, or whose pages
   carry different menus, gets no help from stage 1. Prose begins at the
   first six-word window carrying three or more uncapitalised words.
3. **Sentence split, truncated tail dropped.** The snippet is cut at a fixed
   length, so its last span very often ends mid-word. Quoting one would put a
   fragment in front of a prospect that does not appear on their site in that
   form, which is the opposite of grounding.
4. **Every sentence start is offered as a quotation start.** The crawler glues
   a heading to the prose behind it with no punctuation, so `in advertising
   Products Techniques Our strength We are Fotolight Fotolight is a production
   company with 70 years of experience…` arrives as ONE span. Each place a
   capitalised word is followed by a lowercase one is offered; the filters
   throw away the ones still carrying a menu, and what survives is `Fotolight
   is a production company with 70 years of experience in outdoor and instore
   communication for A-brands` — the sentence on the page.
5. **Filters. Every one of them was written because it caught something this
   extractor had already accepted.** Length 6–26 words · the estate's own
   `lint.normalise_punctuation` applied first · no U+FFFD, because a lost
   encoding is not their sentence · no URL or contact block · nothing
   `copylint`'s dash or buzzword rules fire on · prose not a menu (two
   stopwords, ≤60% Title Case) · does not open on a navigation word · does not
   open mid-sentence or on a comma or colon (`Dance:`, `Hits,`) · does not
   open on a conjunction (`And we know how to bring the two together`) · no
   run of four capitalised words · no adjacent repeat (`Fotolight Fotolight`)
   · no capitalised word mid-sentence unless it is an acronym or follows a
   preposition or article (`the new Exceeding your expectations` is a seam;
   `based in Clerkenwell, East London` and `an established FMCG agency` are
   sentences) · not browser or cookie boilerplate — `The store will not work
   correctly in the case when cookies are disabled` went out as idegroup.se's
   own words before that list existed.

One span then wins on a score preferring the about page, a year, a
`based in`/`founded` phrase, a sentence-like opening, and distinct
non-category vocabulary — and **penalising every capitalised word after the
first**. That last term is load-bearing: without it the longest span always
won, and the longest span is the one with the menu still attached. `Contact
Us Shomei is built around creative minds…` outscored `Shomei is built around
creative minds…` purely on length.

**The filters are asserted, not asserted-about.** `scripts/lane_h_filter_check.py`
runs 8 quotes that MUST survive, 12 seams that MUST be rejected each with the
reason it must be rejected for, and 4 language calls. 23 cases, exit 0. A
filter that rejects the seam and also rejects `based in Clerkenwell, East
London` has not helped, so the survivors are asserted too.

### 2.3 Identity: both guards, fail-closed, and a fact must satisfy both

- `packfacts.identity_of` — lane D's, loaded from lane D's branch, not copied.
  admitted / refused / **unverifiable, which is not a pass**.
- `actors.is_this_company(row, domain, "source_url")` — lane C's, applied to
  the only website field a crawled page carries. Fail-closed with no field.

Over every fact offered to the 179:

    admitted        288
    refused           0
    unverifiable    239      <- every one a LinkedIn post; §1.1

**No second identity guard was written.**

### 2.4 Steps 3, 4 and 5, and what was NOT rewritten

Rendered by **lane B's own `_steps_three_four_and_five`**, loaded from lane
B's branch and called, so `rung3_economic_buyer`, `rung3_champion`,
`angle_shift_*` and `close_*` are lane B's exact strings. **Not one word of
approved copy is retyped in this lane.** Rung 3 is used as approved.

- **Step 2 is untouched** — lane B's `BODY_2` constant, campaign 489's words.
- **The subject is untouched** — lane B's `subject_for`.
- **`{capability}`** resolves through lane B's `cadence.product_words` to the
  client's own unedited sentence, with `product.capability_by_persona` read
  out of lane B's `productive.yaml` blob rather than reimplemented.

A complete five-step render is reproducible with
`py -3 scripts/lane_h_read_render.py`.

### 2.5 The variable mapping, DERIVED BY RUNNING THE CODE

The brief names this as the thing not to take from a document, and two
committed documents already got it wrong. `scripts/lane_h_mapping_check.py`
feeds lane B's `CADENCE_STEPS` and lane B's `email_sequence` block to the
real `bisonfactory._sequence_steps`, then asks the real `_variables_for`:

    cadence days     1 / 4 / 8 / 12 / 21       gaps 3 / 4 / 4 / 9
    declared waits   3 / 4 / 4 / 9 / 1         thread [F, T, T, T, T]

    order=1 step_key=em1 wait=3 thread_reply=False body='<p>{BODY_1}</p>'
    order=2 step_key=em2 wait=4 thread_reply=True  body='<p>{BODY_2}</p>'
    order=3 step_key=em3 wait=4 thread_reply=True  body='<p>{BODY_3}</p>'
    order=4 step_key=em4 wait=9 thread_reply=True  body='<p>{BODY_4}</p>'
    order=5 step_key=em5 wait=1 thread_reply=True  body='<p>{BODY_5}</p>'

    _variables_for -> body_1..body_5 hold em1..em5's words; subject_1 only

**The agreement between key number and position number is a COINCIDENCE of
this shape.** At four steps em4 was the third provider step and read
`{BODY_3}`. Nothing here relies on it: the journal emits STEP-KEY names and
`bisonfactory` owns the translation.

### 2.6 THE BRANCHES MOVED UNDER THIS LANE, TWICE

When this file was first written lane B's config declared waits **3/4/5/5/1**
on days 1/4/8/13/18. An hour later the same branch declared **3/4/4/9/1** on
days 1/4/8/12/21 — which is what the brief said and what §2.5 measures.
Lane C's and lane D's branches moved too.

The blobs are read live, so this output is always the branches' current copy
— and the summary JSON therefore records all four branch HEADs, and so does
the first paragraph of this document. **A number quoted without them is a
number about a tree that no longer exists.** Re-run the script; do not trust
this file's numbers against a different set of shas.

---

## 3. THE SINGLE-WORD PROBLEM, ANSWERED DIRECTLY

Lane C: *"54 of 117 passes rest on a single word, and that word is `marketing`
in 53 of them. 24 rest on category words alone."*

**On the 128 specifically, before this lane:**

    rule 1 passes                              69
      resting on exactly ONE distinct word     37
      that one word being `marketing`           9
      `marketing` matched at all               29
      resting on category words alone          13

The other single words were `green` ×2, `werbeagentur` ×2, and one each of
`appvestor`, `mecenat`, `prestige`, `comms`, `zorba`, `synneo`, `teams`.

**After: 0 single-word passes, 0 on `marketing`, 0 on category words alone.**

### 3.1 Rule 1 is not the measurement. The anchor is.

Rule 1 asks whether **any** word over four letters appears **anywhere** in the
pack, which a 400-character dump of a site's prose answers by accident. A
**contiguous run** cannot be answered by accident. Longest run of opener words
present verbatim in the pack, on the 128:

| anchor length | 0 | 1 | 2 | 3 | 4–6 | 7–27 |
| --- | --- | --- | --- | --- | --- | --- |
| **before** (n=128) | 31 | 63 | 25 | 9 | **0** | **0** |
| **after** (n=25) | 0 | 0 | 0 | 0 | 0 | **25** |

**Not one of the 128 openers had a four-word phrase in common with its pack
before — the longest anywhere was three. Every re-rendered one has at least
seven, median sixteen, longest twenty-seven.** That is the difference between
sharing vocabulary and referencing a fact.

### 3.2 Would the reference survive a human reading the website?

The audit journal carries the exact `source_url`, the `fact_id` and the
quoted span for every one, so the check is: open the URL, find the sentence.
All 25 quote a page on the account's own domain — **13 home pages, 10 about
pages, 1 services page, 1 work page**.

**They are NOT all equally good. Reading all 25 myself:**

- **19 are sentences a person would recognise as their own.** `We design,
  build and deliver creative events and experiences that trigger the right
  vibe` · `Founded in 2010 in Oldenburg, Germany, Affiliprint launched with a
  bold vision: to bridge the gap between online precision and offline impact`
  · `Shomei is built around creative minds with decades of experience, sharp
  instincts and a shared ability to turn complexity into clarity` · `Biborg
  is an independent full-service agency dedicated to the gaming industry` ·
  `When we opened our doors back in 2009, we wrote 3 words on the wall in the
  office` · `Delivering the tastiest world food experiences in over 2.000
  ethnics stores in the EU`.
- **5 are true and uninformative** — verbatim, on the page, and a reader would
  not feel recognised by them: `garritz.com` *"The house, its inheritance, its
  reading room"* · `dqcomms.com` *"Our creativity is driven by results and
  client satisfaction"* · `estpopulo.com` *"Advertising with a focus on
  automation to boost your bottom line"* (starts mid-list) ·
  `wearetribeglobal.com` *"With a formidable network of contacts, a huge range
  of skill-sets and capabilities, we are ready for any challenge"* ·
  `offroadglobal.com` *"We've created digital solutions that have transformed
  businesses and solved complex challenges"*.
- **1 is awkward though clean** — `norvelljefferson.com` *"Exceeding your
  expectations and ensuring you value with undeniably unique content that
  captivates your audience"*. It is their sentence; it is not good English and
  that is their copy, not this render's.

**Those 6 are named so a person reads them before the push, not so the count
looks better.** They are in the journal by address. **Dropping all 6 leaves
19**, and §8 is priced both ways.

### 3.3 What this does NOT prove

- It does not prove the quote is **relevant** to the reason we are writing. It
  proves the opener refers to something on their site. A sentence that is
  true, sourced and beside the point is still beside the point, and no
  measurement here reaches that.
- The anchor is measured against `copylint.pack_text`, which is the **crawl
  snippet**. It is **not** measured against the live website, which may have
  changed since 2026-09-24 22:4xZ. Nothing here re-fetched a page.

---

## 4. HOLDS — 103 of the 128, and none of them gets a generic line

| reason | of the 128 | of the 179 | of the 105 |
| --- | --- | --- | --- |
| no quotable span on any admitted page | **52** | 72 | 42 |
| no identity-admitted site page in the pack | **31** | 42 | 21 |
| only non-English quotable spans | **19** | 21 | 8 |
| `copylint` dash, from the company name | **1** | 3 | 2 |
| **HELD** | **103** | **138** | **73** |
| **re-rendered** | **25** | **41** | **32** |

The 19 held on language are unknown 9, Dutch 3, Danish/Norwegian 3, Swedish 3,
German 1 — and §4.1.1 explains why German is 1 and not 20.

Only 1 of the 6 dashed company names in the 128 shows as a dash hold: the
other 5 were already held for want of a quotable span. §6.1 has the estate
number.

### 4.1 THE DOMINANT CONSTRAINT IS A FACT NOBODY WROTE DOWN: 117 OF THE 128 ARE NOT ENGLISH-SPEAKING

Their sites are in their own languages and the approved copy is in English.

**The first version of this extractor held 64 spans as "not prose" because
its function-word list was English only.** They were ordinary Dutch and
Swedish sentences. That is a defect in a measurement, and it is exactly the
shape this repository keeps finding: a number about the tool rather than
about the estate. The prose test now spans seven languages and the
**English-only rule is applied afterwards and separately**, so its cost is a
number rather than an accident.

**THE OPERATOR HAS A LEVER HERE AND IT IS WORTH 19 LEADS.**

    english-only                  25 of 128 re-render
    quote in the site's language  44 of 128 re-render

Run with `--allow-non-english`; the output is
`work/lane-h-nonen-render-2026-09-25.json`. A verbatim Swedish sentence
inside an English email is **grounded** — identity, anchor and lint are all
satisfied — and whether it reads as thoughtful or as broken is a copy
judgement no measurement in this lane can make. **Held by default because the
fail-closed direction is not sending it.**

### 4.1.1 GERMAN IS UNDERCOUNTED IN THAT LEVER, AND I KNOW WHY

**German capitalises its nouns.** `klare Strategie und starke Kreation` looks
exactly like a heading run into the sentence behind it, so the glued-sentence
filter — the one that correctly catches `the new Exceeding your expectations`
— rejects almost all German prose **before the language rule ever sees it**.
German spans therefore land under *"no quotable span"* rather than under
*"not in English"*, which is why that row reads German 1.

So **`--allow-non-english` is worth more than the 44 it reports**, and the
44 itself fell from 59 when the seam filters were tightened — the tightening
that improved English quote quality cost non-English yield, because the rule
assumes English capitalisation. Asserted in `scripts/lane_h_filter_check.py`
rather than left to be rediscovered. **39 of the 128 are German**, so this is
the single largest thing between this extractor and a bigger number. Fixing
it means language-aware capitalisation rules, which is a different piece of
work and is not attempted here.

### 4.2 The 31 with no admitted site page are not a re-crawl away

They are lane C's residual by another name: `HTTP_INSUFFICIENT` (the site
answered and says too little), `BLOCKED`, `JS_RENDERING_REQUIRED`, `NON_2XX`,
`TIMEOUT` — plus the 10 that carry only LinkedIn posts, whose identity has to
be established upstream where the fact is made. Only `JS_RENDERING_REQUIRED`
and `BLOCKED` are worth a second attempt at all.

---

## 5. CHANGING STEP 1 DOES NOT MOVE LIVE COPY, AND THAT IS MEASURED

The brief asks for this loudly and separately. **No lead of the 128 has ever
been contacted, and the check has a CONTROL so a zero is evidence rather than
a broken lookup.**

    raw work/queue.jsonl: 1582 rows
      CONTROL (the 51 UK/EU leads that DO have a record):
                       39 of 39 domains found, 51 of 51 addresses found
      the 128:          0 of 114 domains,        0 of 128 addresses

`scripts/lane_h_never_contacted.py`. The raw file is read rather than
`store.load()`, because a dropped record is still a record and the raw file
cannot hide one. A lead with no record has no contacts, no cadence, no
approval fingerprint and no `push_id`, and `bisonfactory.stage` cannot reach
it.

**The provider readback files cannot answer this question and were not used
as if they could.** `work/stage/pc-leads.jsonl`, `pc-lead-sends.jsonl` and
`pc-sends.jsonl` are keyed by provider `lead_id` and carry **no email address
at all**. A first attempt "found" 0 of 128 addresses — and also 0 of 20,221
addresses overall, which is a lookup that cannot fail. That attempt was
thrown away rather than reported.

So for the 25: **step 1 is new copy to a person who has never heard from us.
Nothing live moves.**

---

## 6. TWO FINDINGS THAT ARE NOT THIS LANE'S COPY

### 6.1 A SUPPLIER FIELD REFUSES THE PUSH — 14 of the 814 rendered rows

`copylint`'s `dash` rule reads the whole body. Steps 2, 3, 4 and 5 all embed
`{company}`. Some Company cells in
`work/Productive/productive_ICP_safe_to_send (1).csv` contain a **spaced
hyphen**:

    Quickfire - Shopify Premier Partner
    Giffits - Die Welt der Werbeartikel
    Lane - a Certified B Corp
    KB&B - Family Marketing Experts
    Duo - Standing with you
    BASIC CPH - Model Agency
    World Platinum Investment Council - WPIC®

    of the 814 rendered journal rows   14
    of the 179                          9
    of the 128                          6
    of the 105                          4

**The rule fires on APPROVED copy because of a CSV cell**, and it is not a
UK/EU property — it will refuse leads in every future cohort. This lane HOLDS
them. The fix is not in `copylint` (never widen a rule): it is a
normalisation of the Company field at S7 render time, or `{company}` rendered
from a cleaned name. **That is lane B's file and is stated here rather than
edited.**

### 6.2 `persona_pain` is still what 686 other rendered rows carry

Lane D's task B. Step 1 here no longer pairs a direct address with
`{company}`, but only because this lane writes a different step 1 for 25
leads. The template in `src/cadence.py` is unchanged.

---

## 7. THE COPYLINT VERDICT, AND WHY IT PASSING PROVES LITTLE ON ITS OWN

`copylint.check_batch(leads, packs, steps_expected=5)` over what would
actually be pushed:

    the 128:  25 rendered, 103 held   PASSED: 25 of 25 leads clean
    the 179:  41 rendered, 138 held   PASSED: 41 of 41 leads clean
    the 105:  32 rendered,  73 held   PASSED: 32 of 32 leads clean

`steps_expected=5`, this plan's own length, not `copylint.STEPS_EXPECTED`.

**That PASS is a post-condition of this lane's own holds and is not by itself
evidence.** Every lead that would have failed was held first, with the rule's
own name in the hold reason. A gate that cannot fail is not a gate.

**THE RED CHECK.** `--no-prelint` turns the per-lead hold off so the batch
lint sees those leads:

    the 128:  26 rendered, 102 held
      REFUSED: 25 of 26 leads clean
        dash    1   qleguelvoud@duodisplay.com
    the 179:  44 rendered, 135 held
      REFUSED: 41 of 44 leads clean
        dash    3   barry@quickfiredigital.com, billie@quickfiredigital.com,
                    qleguelvoud@duodisplay.com
    the 105:  34 rendered, 71 held
      REFUSED: 32 of 34 leads clean
        dash    2   barry@quickfiredigital.com, billie@quickfiredigital.com

It refuses **exactly** the dashed-company-name leads, by name, and nothing
else — so the 25 pass for a reason and not because nothing was asked.

### 7.1 A fragility `duplicate_first_line` did not fire on and could

A pack belongs to a DOMAIN, so two contacts at one account get the **same
quote**, and their step-1 first lines then differ only by the first name.
Measured on the re-rendered 179: 43 distinct first lines of 43 at the time it
was checked, but four domains carry more than one contact
(`sirendesign.co.uk` 4, `sign-specialists.co.uk` 3, `red-stone.com` 2,
`wholegraindigital.com` 2) and each has exactly one distinct quote. **Two
colleagues sharing a first name would collide and the batch would refuse.**
None of the 25 in the 128 shares a domain, so it does not bite today.

---

## 8. THE NUMBER I WOULD ACTUALLY PUSH

**25 of the 128.**

Every one of them: opens on a verbatim span of its own website with the page
named; the span is identity-admitted by **both** guards; the anchor is at
least seven words; the lead has **never been contacted**; and all five steps
render and clear `copylint` at `steps_expected=5`.

**Not 80, and not 69.** Those were rule-1 passes on vocabulary overlap, which
is the defect the operator named.

Two conditions:

1. **Read the six named in §3.2 first.** Five are true and uninformative, one
   is awkward. **Dropping all six leaves 19, and I would be comfortable with
   19 with nobody reading anything.**
2. **The 6 dashed company names in the 128 are held here and will refuse the
   push wherever else they appear** (14 across the 814). §6.1 is a task before
   the next cohort, not after.

If the operator decides a quotation in the prospect's own language is
acceptable copy, **the number is 44**, and §4.1.1 says it would be higher
still with language-aware capitalisation.

**25 does not fill a 45-lead campaign, and that is the real consequence.** It
belongs in the sequencing decision rather than in a copy report: the free
crawl cleared the **lint**; it did not clear the **grounding**; and the gap
between those two is 44 leads of the 69 that rule 1 was passing.

---

## 9. FILES

    scripts/lane_h_pack_grounded_render.py   the re-render and every number
    scripts/lane_h_filter_check.py           §2.2, 23 assertions, exit 0
    scripts/lane_h_never_contacted.py        §5, with the control
    scripts/lane_h_mapping_check.py          §2.5, by running the code
    scripts/lane_h_tables.py                 the tables in §0, §1, §3, §4
    scripts/lane_h_read_render.py            reads the output journal
    docs/MERGE-REQUEST-2026-09-25-PACK-GROUNDED-RENDER.md

Written to `work/` — gitignored, new files nothing else reads:

    lane-h-render-2026-09-25.json     per lead: before, after, the pack fact
                                      with source_url and fact_id, the hold
                                      reason, and all five rendered bodies
    lane-h-summary-2026-09-25.json    the tables above + the branch HEADs
    lane-h-nonen-*-2026-09-25.json    the --allow-non-english variant
    lane-h-redcheck-*-2026-09-25.json the --no-prelint variant

**Nothing under `src/` was edited, and nothing another lane owns.** Not
`config/.env`, not `src/providers/*`, not `scripts/*_watch_loop.py`, not lane
B's `src/cadence.py`, `config/clients/productive.yaml`,
`scripts/batch1_build.py` or `scripts/stage_s7_copy.py`, not lane D's
`src/packfacts.py`, not lane C's `src/researchpack/*`. Every one of those is
read out of git and executed as the module it would have been.

---

## 10. WHAT `stage_s7_copy.py` WOULD NEED — STATED, NOT EDITED

Lane B owns it. To make this production rather than a lane's output:

1. **A pack argument.** `render(row, config)` becomes
   `render(row, config, pack)` and `main` loads packs by domain. The shape is
   `packfacts.pack_for`'s output — lane D's, already on a branch.
2. **`BODY_1` becomes two constants**, the grounded one and the current one,
   and the grounded one is used when a quotable span exists. **A lead with no
   span must be HELD**, through the same `(None, reason)` path the file
   already uses for a missing first name, and the reason should name the
   pack rather than the render.
3. **The extractor.** `grounded_fact` and its filters are the part worth
   taking. They belong beside `src/webfetch.py` or in
   `src/researchpack/site.py` rather than in a script.
4. **Normalise `{company}`** before it reaches any template (§6.1).

**The better fix is upstream of all four.** Every filter in §2.2 exists
because the crawler stores a 400-character flat string with the navigation in
it. If `site.research` kept page regions — heading, nav, body — separately,
most of §2.2 would be unnecessary, the German problem in §4.1.1 would
largely dissolve with it, and the yield would be well above 25. **That is
lane C's file.**

---

## 11. WHAT I COULD NOT VERIFY

1. **That the quoted sentence is still on the live page.** The anchor is
   measured against the 2026-09-24 crawl snippet; nothing here re-fetched a
   URL. A site that changed overnight would make an opener quote a page that
   no longer says it.
2. **That the quote is RELEVANT.** §3.3. Sourced and beside the point is
   still beside the point.
3. **Whether a non-English quotation reads well to its recipient.** §4.1. It
   is measurably grounded; it is not measurably good.
4. **The country classification of the 179.** Taken from `s3-icp.jsonl`
   exactly as lane C took it, not re-derived.
5. **`bisonfactory.stage`'s copylint wiring.** Taken on lane D's report, as
   lane C did. This lane measured the rule and the render, not the wiring.
6. **Anything at the provider.** No EmailBison call, no HeyReach call. §5's
   "never contacted" rests on the store, with a control — not on a provider
   readback, because those files carry no addresses.
7. **The other copylint rules on the 686 rendered rows outside UK/EU.** Only
   this cohort was measured. §6.1 gives the dash defect's estate-wide count
   because it is cheap; the rest was not asked.
8. **That 25 is the maximum.** It is what this extractor gets from this
   crawl. §10 says why a better crawl beats it and §4.1/§4.1.1 say the
   English rule alone is worth 19 more today and more than that with
   language-aware rules.
9. **The other lanes' branches at merge time.** All three moved while this ran
   (§2.6). These numbers are against `a68a5813` / `ba2c31b9` / `c38c5934`.

---

## 12. SUITE

ONE pass, `py -3 scripts/run_suite.py --offline --timeout 2400`.

SUITE_RESULTS_PLACEHOLDER

**`scripts/suite_verdict.txt` is the trap lane C wrote up.** It is a tracked,
committed file on this branch, and master has already untracked it
(`1101937d`, *"a committed verdict is never evidence"*). It was deleted
before this run so a stale verdict could not be read as a fresh one, and the
committed blob is restored afterwards so this branch's diff carries no change
to a file this lane was not sent to touch. **The numbers above come from the
run log, not from that file.**
