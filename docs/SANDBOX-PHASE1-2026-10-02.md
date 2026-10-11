# SANDBOX FAZA 1 — pet sintetickih agencija, pet unaprijed odredenih presuda

Mjereno 2026-10-03 na grani `task-sandbox-phase1`, baza master
`2bf7b8a571fe11bada4f56fbebeee768ab1e78a8`. Zamrznuto kao
`tests/test_sandbox_phase1.py` — **43 testa, 5.5 s, bez mreze**.

Faza 0 (`docs/GOLDEN-PATH-GATE-7-2026-10-02.md` na `task-golden-path`) dokazala
je da JEDAN zapis moze doci do `executionguard` vrata 7. To odgovara na pitanje
dosezivosti i ni na sto drugo: cuvar koji svemu kaze ALLOW takoder dolazi do
vrata 7. Ova faza vodi PET zapisa cije se ocekivane presude RAZLIKUJU, pa je put
koji svima petorici odgovara isto — vidljiv kao greska.

**Rezultat: 2 prava defekta popravljena ovdje, 1 pravi defekt koji se popravlja
spajanjem tude grane, 1 krivo napisan dummy popravljen, i 2 nalaza prijavljena s
obje strane i namjerno NEdirnuta.**

---

## 0. Sigurnost, kako je mjerena

| | |
|---|---|
| produkcijski `work/queue.jsonl` md5 na pocetku | `72cb039ffbad853515c4d4c01eecec44` |
| produkcijski `work/campaigns.jsonl` md5 na pocetku | `fb7d7bfe0b1cbdb99a7c9bc5e52210df` |
| `work/campaigns.jsonl` md5 na kraju | `fb7d7bfe0b1cbdb99a7c9bc5e52210df` — **nepromijenjen** |
| `work/queue.jsonl` md5 na kraju | **promijenjen, i to NE od mene** — vidi nize |
| dosegnuti provider hostovi | nijedan osim pozitivne kontrole |
| provider upisi | 0 |
| Slack poruke | 0 |
| OpenRouter potrosnja | **0 USD** — nijedan slucaj ne treba pisca |

**`queue.jsonl` se promijenio jer u paralelnoj traci radi generiranje**, sto je
operator izricito odobrio. To nije rupa u dokazu nego razlog zasto dokaz NIJE
jedan globalni par md5-ova: **svaki od 43 testa sam uzme md5 obje produkcijske
datoteke u `setUp` i usporedi ih u `addCleanup`**, pa se tvrdi bajt-identicnost
preko VLASTITOG prozora izvodenja. 43 zelena testa znaci 43 takve usporedbe, sve
jednake. Da je bilo koji moj test dirnuo produkcijski `work/`, taj bi test pao.

`_production_root()` razrjesava GLAVNI checkout kroz `.git`, jer radno stablo
(`git worktree`) uopce nema `work/` — bez toga bi `_md5` vratio `None` prije i
`None` poslije i tvrdnja bi bila test koji ne moze pasti. `setUp` eksplicitno
tvrdi da obje datoteke POSTOJE.

**Spremiste je kopija.** `store.use_directory()` u privremeni direktorij, s
pomakom koji se tvrdi na `queue_path()` **i zasebno** na `campaigns_path()` —
potonji se seli BRISANJEM `CAMPAIGNS` override-a, pa bi ustajali override prezivio
i samo ga zasebna tvrdnja vidi.

    sandbox queue_path    : ...\Temp\sandbox-phase1-6qk8e3mq\work\queue.jsonl
    sandbox campaigns_path: ...\Temp\sandbox-phase1-6qk8e3mq\work\campaigns.jsonl

**Zica je zapecacena PO HOSTU, ne po transportu.** Pisac i provider zovu isti
sav (`providers.set_transport`), pa slijepi sentinel ubija i generiranje — to je
srusilo prvi pokusaj faze 0. OpenRouter je propusten, svaki drugi host odbijen.
Pozitivna kontrola trci u `setUp` SVAKOG slucaja, prije bilo koje sonde:

    GET api.emailbison.com -> WireSealed: the wire is sealed:
    GET api.emailbison.com is not the writer's host.
    Allowed: ('openrouter.ai',). Nothing was sent.

    writer host allowed by the seal: True ('openrouter.ai',)
    hosts reached during the walk: {'api.emailbison.com'}   <- samo kontrola

**`synthetic: true` ne stiti nista** (mjereno 2026-10-02: 0 od 15 upita nad
bazenom iskljucuje po njemu) i nije se na njega oslanjalo. Sve domene su na
`.invalid`, koji RFC 2606 rezervira, pa se nikad ne mogu razrijesiti.

---

## 1. Pet subjekata

Sve: marketinska/digitalna agencija, UK, jedan izvor broja zaposlenih (osim
slucaja 5 gdje je kontradikcija sam predmet testa), vertikala popunjena, jedan
kontakt s LinkedIn URL-om, persona `champion`.

| # | tvrtka | domena | vertikala | kontakt |
|---|---|---|---|---|
| 1 | Zyntara Media (SYNTHETIC) | `zyntara-media.invalid` | Digital Marketing Agency | Vera Synthova, Head of Delivery |
| 2 | Quorvex Studio (SYNTHETIC) | `quorvex-studio.invalid` | Creative / Branding Agency | Milo Mockworth, Managing Partner |
| 3 | Drexlo Performance (SYNTHETIC) | `drexlo-performance.invalid` | Performance Marketing Agency | Ines Fauxley, Operations Lead |
| 4 | Pellumbra Search (SYNTHETIC) | `pellumbra-search.invalid` | SEO Agency | Tomo Dummett, Head of Client Services |
| 5 | Vantiqo Design (SYNTHETIC) | `vantiqo-design.invalid` | Design / UX Agency | Lena Testova, Studio Director |

### Istrazivanje je NAPRAVLJENO da postigne pojas, nije mu pojas upisan

`evidence.recheck` ponovno izvodi `quality`, ali NE `relevance_score` (mjereno,
`src/evidence.py:477-515`) — relevantnost je pohranjena i prezivi, kvaliteta je
izvedena. Zato:

* **Slucaj 1 (MEDIUM):** cinjenica koja pogada kut (+0.35) i operativni pojam
  (+0.25), oboje zasluzeno jednom rijecju `budget`, plus svjezina (+0.10 × 0.973)
  = **0.697**. Iznad `MIN_RELEVANCE` (0.65) i ispod 0.75 koji bi bio STRONG.
  U cinjenicama NEMA NIJEDNE ZNAMENKE: `\b\d+\b` dodaje +0.10 i nosi 0.697 na
  0.797, odnosno MEDIUM na STRONG — tako je prvi nacrt ovog spisa pao.
* **Slucaj 4 (WEAK, tocno 0.35):** samo pojam kuta. `creep` je u `ANGLE_WORDS`
  ("scope creep") i NIJE u `evidence.OPERATIONAL_TERMS`, pa zaraduje samo +0.35;
  `published_at=None` daje kosaru UNKNOWN i svjezinu 0.0. **0.35 je WEAK, ne
  UNUSABLE** — usporedba je `relevance_score < 0.35`.
* **TRI reda, ne jedan.** `research.MIN_COPY_EVIDENCE_ROWS` je 3 i
  `_copy_evidence_missing` broji `evidence.select`, pa bi tvrtka s dva
  prihvatljiva reda pala iz razloga slucaja 4.

---

## 2. Tablica: tvrtka/kontakt × vrata × presuda × trajanje

Jedan redak po vratima po tvrtki, pa su vrata koja nikad nisu dosegnuta
**vidljivo odsutna** (`NIJE DOSEGNUTO`), a ne tiho izostavljena.

`executionguard.authorize` ne izlaze trajanje po vratima, pa su vremena mjerena
linijskim tracerom nad `src/executionguard.py` koji oznaci svaku liniju koja
dopisuje u trag vrata. **Trajanja su zato napuhana otprilike 2–5×** (slucaj 1:
36.3 ms s tracerom, ~7 ms bez njega); odnosi medu vratima su ono sto vrijedi.
Vrata koja `gates.extend` dopisuje ZAJEDNO dijele oznaku i prikazana su s
0.0 ms — to su pet JIT provjera (`eligibility`..`fatigue`) i par
`collision`/`account_collision`.

| tvrtka / kontakt | vrata | presuda | ms | kumulativno ms |
|---|---|---|---|---|
| **Zyntara / Vera Synthova** | tenancy | PASS | 0.524 | 0.524 |
| | approval | PASS | 0.050 | 0.574 |
| | campaign_approval | PASS | 1.572 | 2.146 |
| | readback | PASS | 0.146 | 2.292 |
| | eligibility | PASS | 29.029 | 31.320 |
| | suppression | PASS | 0.0 | 31.320 |
| | copy | PASS | 0.0 | 31.320 |
| | claims | PASS | 0.0 | 31.320 |
| | fatigue | PASS | 0.0 | 31.320 |
| | collision | PASS | 0.263 | 31.583 |
| | account_collision | PASS | 0.0 | 31.583 |
| | sender | PASS | 0.312 | 31.895 |
| | pilot_cap | PASS | 0.245 | 32.141 |
| | stoppability | PASS | 0.015 | 32.155 |
| | ledger | PASS | 0.047 | 32.202 |
| | **killswitch:workspace** | **PASS → ALLOW** | 0.359 | 32.561 |
| | reserved | PASS | 2.167 | 34.728 |
| **Quorvex / Milo Mockworth** | tenancy | PASS | 0.372 | 0.372 |
| | approval | PASS | 0.038 | 0.410 |
| | campaign_approval | PASS | 1.362 | 1.772 |
| | readback | PASS | 0.127 | 1.899 |
| | eligibility | PASS | 10.717 | 12.616 |
| | suppression | PASS | 0.0 | 12.616 |
| | copy | PASS | 0.0 | 12.616 |
| | claims | PASS | 0.0 | 12.616 |
| | fatigue | PASS | 0.0 | 12.616 |
| | collision | PASS | 0.169 | 12.785 |
| | account_collision | PASS | 0.0 | 12.785 |
| | sender | PASS | 0.268 | 13.053 |
| | pilot_cap | PASS | 0.169 | 13.222 |
| | stoppability | PASS | 0.012 | 13.234 |
| | ledger | PASS | 0.030 | 13.264 |
| | **killswitch:workspace** | **PASS → ALLOW** | 0.324 | 13.587 |
| | reserved | PASS | 1.612 | 15.199 |
| **Drexlo / Ines Fauxley** | tenancy | PASS | 0.388 | 0.388 |
| | approval | PASS | 0.040 | 0.428 |
| | campaign_approval | PASS | 1.011 | 1.440 |
| | readback | PASS | 0.130 | 1.569 |
| | **eligibility** | **REFUSED** `blocked:replied` | — | — |
| | suppression | NIJE DOSEGNUTO | — | — |
| | copy | NIJE DOSEGNUTO | — | — |
| | claims | NIJE DOSEGNUTO | — | — |
| | fatigue | NIJE DOSEGNUTO | — | — |
| | collision | NIJE DOSEGNUTO | — | — |
| | account_collision | NIJE DOSEGNUTO | — | — |
| | sender | NIJE DOSEGNUTO | — | — |
| | pilot_cap | NIJE DOSEGNUTO | — | — |
| | stoppability | NIJE DOSEGNUTO | — | — |
| | ledger | NIJE DOSEGNUTO | — | — |
| | killswitch:workspace | NIJE DOSEGNUTO | — | — |
| | reserved | NIJE DOSEGNUTO | — | — |
| **Pellumbra / Tomo Dummett** | tenancy | PASS | 0.364 | 0.364 |
| | approval | PASS | 0.036 | 0.400 |
| | campaign_approval | PASS | 1.438 | 1.838 |
| | readback | PASS | 0.114 | 1.953 |
| | eligibility | PASS | 9.446 | 11.399 |
| | suppression | PASS | 0.0 | 11.399 |
| | copy | PASS | 0.0 | 11.399 |
| | claims | PASS | 0.0 | 11.399 |
| | fatigue | PASS | 0.0 | 11.399 |
| | collision | PASS | 0.161 | 11.560 |
| | account_collision | PASS | 0.0 | 11.560 |
| | sender | PASS | 0.250 | 11.810 |
| | pilot_cap | PASS | 0.160 | 11.970 |
| | stoppability | PASS | 0.011 | 11.981 |
| | ledger | PASS | 0.027 | 12.008 |
| | **killswitch:workspace** | **PASS → ALLOW** | 0.358 | 12.366 |
| | reserved | PASS | 1.385 | 13.751 |
| **Vantiqo / Lena Testova** | tenancy | PASS | 0.373 | 0.373 |
| | approval | PASS | 0.037 | 0.410 |
| | campaign_approval | PASS | 1.350 | 1.760 |
| | readback | PASS | 0.118 | 1.878 |
| | eligibility | PASS | 10.601 | 12.479 |
| | suppression | PASS | 0.0 | 12.479 |
| | copy | PASS | 0.0 | 12.479 |
| | claims | PASS | 0.0 | 12.479 |
| | fatigue | PASS | 0.0 | 12.479 |
| | collision | PASS | 0.169 | 12.648 |
| | account_collision | PASS | 0.0 | 12.648 |
| | sender | PASS | 0.270 | 12.918 |
| | pilot_cap | PASS | 0.168 | 13.086 |
| | stoppability | PASS | 0.012 | 13.098 |
| | ledger | PASS | 0.030 | 13.128 |
| | **killswitch:workspace** | **PASS → ALLOW** | 0.330 | 13.458 |
| | reserved | PASS | 1.580 | 15.038 |

Cijela setanja: 36.3 / 16.0 / 10.4 / 14.5 / 15.8 ms (s tracerom); postavljanje
estate-a 119 / 175 / 101 / 107 / 102 ms.

### Email kanal: redak koji je odsutan i zasto

Za slucaj 3 traze se OBA kanala. Na email kanalu `executionguard` vrata 1
(`tenancy`) zovu `bison.require_workspace`, koji cita zivu vezu preko zice.
**Dva nezavisna sigurnosna sloja to zaustavljaju, i nijedan nije iskljucen da bi
se dobila presuda:**

1. `tests/__init__.py` brise `BISON_KEY` iz okoline za svaki test u paketu
   (`SUITE_SCRUBBED`), pa nijedan test ne moze vezati EmailBison workspace.
2. Pecat po hostu odbija `api.emailbison.com`.

Zato email redak na razini CUVARA zavrsava na `tenancy` s `passed=()`, i to je
zapisano kao test (`test_the_email_guard_route_cannot_be_walked_in_this_sandbox`).
Presjek kanala za slucaj 3 dokazan je jedan sloj nize, u `eligibility` —
vidi §4.

---

## 3. Presude, jedna po jedna

| # | ocekivano | izmjereno | odstupanje |
|---|---|---|---|
| 1 | ALLOW na vratima 7 | **ALLOW**, 17 vrata, kljuc `phase1-clean:vera-synthova:li1:linkedin` | nema |
| 2 | FRESH + `legacy_touched: true` + broj + kopija ne tvrdi prvi kontakt | FRESH **da**; `legacy_touched` **ne postoji**; kopija je **mogla** tvrditi prvi kontakt | **2 prava defekta** |
| 3 | DNC, blokiran na OBA kanala | **blokiran na oba**, `blocked:replied`, cuvar odbija na vratima 4 | nema |
| 4 | HELD na istrazivanju | **HELD** na `research.why(for_copy=True)`; `li1` ipak ALLOW | **krivo napisan dummy** |
| 5 | UNKNOWN → HELD | prije popravka: `icp_pass_with_uncertainty` → QUALIFIED → **ALLOW** | **pravi defekt** |

---

## 4. Slucaj 3 — presjek kanala, dokazan tamo gdje stvarno stoji

`eligibility.must_not_contact` **NE PRIMA KANAL**. To je presjek kanala: ne
postoji odgovor po kanalu koji bi pozivatelj mogao birati, pa LinkedIn put i
email put postavljaju JEDNO pitanje. Tvrdi se nad potpisom funkcije, ne nad
tekstom izvora.

    must_not_contact(rec, contact, config=None, suppressed=None)   <- bez `channel`

Jedan negativan email reply (`events.REPLY_RECEIVED`, kategorija `negative`):

| upit | odgovor |
|---|---|
| `must_not_contact` | `['blocked:replied', 'blocked:company_paused']` |
| `decide(..., channel="linkedin", step=li1)` | `blocked` / `blocked:replied` |
| `decide(..., channel="email", step=em1)` | `blocked` / `blocked:replied` |
| `executionguard.authorize(channel="linkedin")` | REFUSED na `eligibility`, 4 vrata u `passed` |

**Dva nalaza usput, oba zapisana, nijedan nije defekt:**

* `decide(..., "em1", channel="email")` **bez sadrzaja u ruci** vraca
  `skipped:no_such_step`, ne `blocked` — `em1` je `generated` i nista ga nije
  generiralo, pa vremenska crta nema taj korak i `decide` odgovori prije nego
  sto uopce pita `must_not_contact`. Nista ne izlazi ni u jednom slucaju, ali
  **dokaz presjeka kanala koji bi se oslanjao na taj odgovor ne bi dokazivao
  nista.** Zato se email strani preda stvarni payload.
* **`heyreachfactory.ensure_leads` odbija RANIJE, iz nepovezanog razloga:**
  `approved LinkedIn copy is missing for ... li2 -> connected_1 ...`. Izmjereno:
  **ista odbijenica dolazi i za slucaj 1, koji nije blokiran ni po cemu.** Pa
  pokretanje tvornice i gledanje kako odbija ne razlikuje zaustavljen kontakt od
  cistog. To je ista zamka na koju brief upozorava za
  `scripts/batch_linkedin_push.py`, samo jedan sloj dalje. Dokazano je zato
  vezivanje: `heyreachfactory.eligibility is eligibility`, i
  `eligibility.must_not_contact` je medu pozivima unutar `ensure_leads`,
  procitano iz AST-a te funkcije.
* `scripts/batch_linkedin_push.py` — potvrdeno iz AST-a uvoza: **ne uvozi**
  `heyreachfactory`, `providerwrites`, `eligibility` ni `executionguard`.

---

## 5. Pravi defekti

### TASK-980 — `legacy_touched` ne postoji na ovoj bazi · **pravi defekt**

**Reprodukcija.** Zapis s tri potvrdena `email_delivered` dogadaja iz NE-OS
kampanje 327, bez ijednog replyja:

    claims.prior_contact(rec, contact)        -> {'type': 'email_delivered', ...}
    generate.context_for("linkedin_note", ...)["prior_contact"]  -> True  (bool)
    repr(block) sadrzi "legacy_touched"?      -> Ne
    repr(block) sadrzi "327"?                 -> Ne
    repr(block) sadrzi "email_delivered"?     -> Ne
    hasattr(claims, "prior_contact_state")    -> False
    import src.osattribution                  -> ModuleNotFoundError

Sustav ZNA da je dirnuo tu osobu, ali piscu preda **bool i nista vise**. Prompt
moze reci "kontaktiran" i ne moze reci "tri legacy slanja iz kampanje 327,
nijedno nase". Trostanjska vlast postoji, ali ne na ovoj bazi:
`claims.prior_contact_state` (`src/claims.py:482`) i `src/osattribution.py` su na
`task-one-os-authority`, `task-integration-2026-10-03` i
`task-runtime-lane-2026-10-03`.

**Zasto pravi defekt, a ne krivo napisan dummy.** Dummy je tocan — legacy slanja
iz ne-OS kampanje, bez replyja — i brief to unaprijed imenuje kao najvjerojatnije
mjesto pravog defekta. Odstupanje ne proizlazi ni iz cega sto je u dummyju.

**Popravak: SPOJITI `task-one-os-authority`, NE napisati trecu izvedbu.** Ista
sposobnost vec postoji na cetiri grane; cetvrta paralelna izvedba na ovoj grani
bila bi druga reprezentacija iste istine, sto je upravo ono sto CLAUDE.md
zabranjuje, i sudarila bi se sa sekvencom spajanja koja trci u glavnom checkoutu.
Ovdje je zato defekt izmjeren i zapisan kao test koji ce **pasti u trenutku kada
`src/osattribution.py` dode na master** — sto je tocno signal da je popravljen.

### TASK-981 — kopija je smjela tvrditi prvi kontakt koji se nije dogodio · **pravi defekt** · POPRAVLJENO

**Reprodukcija**, prije popravka, isti zapis s tri potvrdena slanja:

    claims.check("Hi Milo, I am reaching out for the first time about ...")   -> []
    claims.check("Hi Milo, this is the first time we have written to you ...") -> []
    claims.check("... apologies for the cold outreach - we have never been
                  in touch before.")                                          -> []

Sve tri su lazne na vlastitom dnevniku dogadaja tog zapisa, i sve tri su recenica
koju je primatelj u boljem polozaju opovrgnuti od bilo koga. `claims.py` je imao
`implies_prior_contact` — hvata nacrt koji IZMISLJA povijest — i nista sto hvata
nacrt koji POrice povijest koja se dogodila. Nula pogodaka za "first time",
"first contact", "out of the blue", "cold" u `claims.py` i `copylint.py`.

Ovo je tocno ono sto brief za slucaj 2 trazi rijecima "kopija ne smije tvrditi
prvi kontakt", i najvaznije je upravo za leada kojem je klijentova vlastita
legacy kampanja vec pisala.

**Popravak** (`src/claims.py`): `NO_PRIOR_CONTACT` (osam uskih regexa) +
`denies_prior_contact(sentence)`, zrcalo `implies_prior_contact` ukljucujuci
`POPULATION` strazu. Provjera je u `check()`, **pod `if contacted:`**, a ne kroz
`is_claim`: tako se za zapis BEZ potvrdenog dodira ne mijenja apsolutno nista i
hladan nacrt koji kaze "apologies for the cold outreach" i dalje prolazi.
Namjerno usko — "you do not know me" nije na popisu: to je tvrdnja o
prepoznavanju, a ne o dopisivanju.

**Poslije popravka:**

    'for the first time' says this is a first contact, and a confirmed
    email_delivered on 2026-06-05T20:30:21+00:00 says it is not

**Negativne kontrole, obje zelene:**
* slucaj 1 (nikad kontaktiran): sva tri nacrta i dalje prolaze (`[]`);
* slucaj 1: `"following up on my last email"` i dalje ODBIJEN
  (`no confirmed touch`);
* slucaj 2: `"following up on my last email"` PROLAZI, jer je istina.

### TASK-982 — kontradikcija u broju zaposlenih kvalificirala je tvrtku · **pravi defekt** · POPRAVLJENO

**Reprodukcija**, prije popravka, 8 od jednog izvora i 40 od drugog (floor je 14
= 20 × (1 − 0.30)):

    headcount.resolve(rec)["state"]            -> conflict, value None
    icpstructural._employees                   -> unknown   (ispravno)
    icpstructural.structural(...)["verdict"]   -> icp_pass_with_uncertainty
    icpstructural.structural(...)["eligible"]  -> True
    icp.score(...)["icp_status"]               -> qualified
    executionguard.authorize(...)              -> ALLOW, 17 vrata

`verdict_of` je UNKNOWN na `employees` upio u "nesigurnost" jer su oba DEFINING
kriterija (`geography`, `company_type`) prosla, a `FROM_STRUCTURAL` mapira
`ICP_PASS_WITH_UNCERTAINTY` na QUALIFIED. Rezultat: tvrtka za koju jedan izvor
kaze osam ljudi dosla je do vrata 7 s ALLOW.

**Dvije vrste UNKNOWN, i samo jedna je nesigurnost.** `ICP_PASS_WITH_UNCERTAINTY`
postoji za tvrtku koju nitko nije izmjerio — sutnja nije dokaz protiv nje.
Kontradikcija nije sutnja: dva providera na suprotnim stranama klijentova poda
znace da je JEDAN od njih afirmativan dokaz da je tvrtka premala, a upijanje toga
u "nesigurnost" je nacin na koji kontradikcija pocinje argumentirati ZA kontakt.
Isti oblik kao ISSUE-023, koji je `_geography_established` vec rijesio za
geografiju i koji za `employees` nikad nije primijenjen.

**Popravak** (`src/icpstructural.py`): `_answer(..., contradicted=False)` nosi
zastavicu, `_employees` je postavlja kad `headcount.resolve` vrati CONFLICT, i
`verdict_of` salje svaki kontradiktoran kriterij koji nije PASSING u
`ICP_REVIEW`. **Nikad u FAIL** — dokazi ne kazu da je tvrtka premala, kazu da ne
znamo.

**Poslije popravka:** `icp_review`, `eligible: False`, `icp.score -> review`.

**Opseg na zivoj produkciji** (citano samo za citanje iz
`work/queue.jsonl`, bez ijednog upisa): **1.584 Productive zapisa, 10 ima
kontradikciju u broju zaposlenih, i 5 od tih 10 je bilo
`icp_pass_with_uncertainty`** — pet tvrtki kvalificiranih na proturjecnim
dokazima o velicini. Nakon popravka tih pet ide u review, ne u FAIL.

**Nevakuumnost popravka je testirana:** zapis bez IJEDNOG izvora broja zaposlenih
i dalje dobije `icp_pass_with_uncertainty` i ostaje eligible
(`test_an_unmeasured_headcount_is_still_only_uncertainty`). Nova je samo
kontradikcija.

---

## 6. Krivo napisan dummy

### Slucaj 4 — hold na istrazivanju POSTOJI; dummy je setao jedini korak koji ga ne osjeca · **krivo napisan dummy**

**Izmjereno:**

    relevance_score svih triju redova      -> 0.35
    quality                                -> weak  (ne unusable)
    evidence.usable / evidence.select      -> [] / []
    research.why(rec, for_copy=True)
        -> "public_evidence_required_for_prospect_facing_copy"   <- HOLD
    executionguard.authorize(li1)          -> ALLOW, 17 vrata

Ocekivana presuda JEST proizvedena — ali od vlasti koja je za nju nadlezna
(`research.why(for_copy=True)`, cije je pozivatelj `enrich.py:1182`), a ne od
cuvara.

**Zasto krivo napisan dummy, a ne pravi defekt.** `li1` nosi
`template: linkedin_intro`. Renderira se bez modela i **bez ijedne cinjenice iz
istrazivanja**:

    hi Tomo, i work with SEO Agency teams on live budget burn. curious how
    Pellumbra Search (SYNTHETIC) handles it at your size. happy to connect.

Ne tvrdi nista o tvrtki; vrata `claims` nemaju sto pratiti i `claims.check`
vraca `[]`. Sustav dakle ne "nastavlja na halucinaciji". Slucaj napisan da
testira "ne smije nastaviti na halucinaciji" mora setati korak koji halucinaciju
MOZE nositi, a to su jedino generirani koraci — i njih `research.why` zaustavi
prije nego sto se pisac uopce pita. **Popravak dummyja:** hold se tvrdi na
vlasti koja ga posjeduje, a ALLOW na `li1` se tvrdi eksplicitno, zajedno s
razlogom (`test_the_template_step_is_authorised_and_that_is_not_a_hallucination`).

---

## 7. Dva nalaza prijavljena s obje strane i NAMJERNO nedirnuta

### Nalaz A — hold na istrazivanju nije vrata na putu slanja

Ni `eligibility` ni `executionguard` ne drze modul `research` (tvrdeno nad
grafom uvoza, ne nad tekstom). Hold zivi uzvodno, u `enrich`.

* **Za `li1` to je ispravno** — sablona ne tvrdi nista i nema sto hraniti
  halucinaciju.
* **Za generirane korake zastita dolazi u trenutku pisanja** — `copylint`
  `untraceable_company_claim` i `claims`, kako je faza 0 i izmjerila.
* **Druga vlast ipak postoji na putu slanja:** nacrt koji se oslanja na slab red
  (`personalization.selected_evidence_ids` pokazuje na njega) dobije
  `held:evidence_aged_out` iz `eligibility.decide`. Zapisano kao test.

Nisam prosirio `eligibility` da pita `research.why`, jer bi to promijenilo
znacenje rijeci "eligible" za cijeli estate.

### Nalaz B — put slanja uopce ne postavlja ICP pitanje

Nakon TASK-982 ICP vlast kaze REVIEW i zapis nije eligible — a
`eligibility.decide` i dalje kaze `eligible` i `executionguard` i dalje dode do
vrata 7, jer nijedan od ta dva modula ne drzi `icp`, `icpstructural`, `qualify`
ni `headcount` (tvrdeno nad grafom uvoza).

**Obje strane:**
* ICP presuda se provodi uzvodno — pri odabiru i u `qualify` — i `bisonfactory`
  je ponovno pita kroz `qualify.state_of`. LinkedIn/`executionguard` ruta ne.
* Da `eligibility` odbija po ICP presudi, odbijala bi i svaki zapis kojem blok
  `qualification` jos nije zapisan (`not_processed`), a to je vecina svjezeg
  reda. To je promjena znacenja rijeci "eligible" preko cijelog estate-a.

**Uzi popravak je onaj koji je napravljen:** neka sama vlast odgovori REVIEW, pa
slojevi koji je citaju prestanu kvalificirati tvrtku. Nalaz B ostaje otvoren i
pripada fazi 2.

---

## 8. Dokaz da testovi mogu pasti

Dvije mutacije u `src/`, `__pycache__` obrisan prije svake, bajtovi potvrdeni
md5-om (datoteke su CRLF, pa se usporeduje md5, ne tekst), i provjereno je da je
pao NAMJERAVANI test.

| mutacija | md5 | ucinak |
|---|---|---|
| nista (baseline) `claims.py` | `2c6464b0005355221bd23665ac367480` | 43 prolaze |
| `if contacted:` → `if False:` | `2563b448a15b5e8cfc7b0f76120e1ebb` | **3 crvena**, sva tri imenuju `test_the_copy_must_not_claim_a_first_contact` |
| vraceno | `2c6464b0005355221bd23665ac367480` | 43 prolaze |
| nista (baseline) `icpstructural.py` | `782214e2b0d700b85405bc485ccc5127` | 43 prolaze |
| grana `contradicted` uklonjena iz `verdict_of` | `6cdb73587e36a347801d58ecb195db2a` | **1 crveno**, `test_a_contradiction_goes_to_review_and_never_to_eligible` |
| vraceno | `782214e2b0d700b85405bc485ccc5127` | 43 prolaze |

---

## 9. Regresija — razlika skupa IMENA, ne broja

**Puni paket NIJE pokrenut**: koordinator drzi strojnu bravu i brief to zabranjuje.
Umjesto toga je pokrenut najsiri skup pojedinacnih modula koji bi moje dvije
izmjene u `src/` uopce mogli vidjeti: **svih 54 testnih modula koji spominju
`claims.`, `icpstructural.` ili `headcount.`** (osim ovog i faze 0).

Ista metoda s obje strane, oba puta `__pycache__` obrisan, baza izvucena u
ZASEBNO radno stablo na istom SHA `2bf7b8a5`:

| | baza `2bf7b8a5` | grana `task-sandbox-phase1` |
|---|---|---|
| testova | 1433 | 1433 |
| trajanje | 89.2 s | 80.3 s |
| rezultat | `failures=19, errors=17, skipped=2, expected failures=4` | identicno |
| jedinstvenih imena koja padaju | 32 | 32 |

    novo pada          0
    vise ne pada       0

Fantomski `test_autonomous_production_is_not_a_self_stamp...certifies_at_staging`
koji operator unaprijed imenuje nije u ovom skupu modula i nije diran.

Osim toga, **faza 0 je pokrenuta kao pozitivna kontrola na MOJOJ bazi** prije
nego sto je faza 1 napisana: `tests/test_golden_path.py` s
`task-golden-path`, **39 testova, 2.844 s, OK** na `2bf7b8a5`. Ruta do vrata 7
prezivjela je spajanje `task-guard-regressions-rebased`. Ta datoteka NIJE
commitana na ovu granu — pripada fazi 0.

---

## 10. Sto je faza 1 jos izmjerila, a nije morala ponovno otkriti

* Pet preduvjeta prije vrata 1 (`channel`, `operation`, `campaign`, `record`,
  `copy`) ponasaju se kako ih faza 0 opisuje; `copy` je i dalje mjesto gdje se
  staje kad kampanja nije predana, jer `_spec_for` razrjesava kadencu IZ KAMPANJE.
* U `productive_li_heavy_v1` samo `li1` nosi `template`; `em1`..`em5` i
  `li2`..`li5` su svi `generated`. Zato je za email kanal trebalo pohraniti i
  odobriti `em1` na zapisu da bi se `cadence.expand_step` uopce renderirao.
* Prag raspona rijeci je tocno 40: tijelo em1 u ovom spisu ima 60 rijeci i tvrdi
  se `assert` u samom helperu.
* Potrosnja na OpenRouteru: **0 USD**. Nijedan od pet slucajeva ne treba pisca —
  `li1` je sablona, a `em1` je pohranjena kopija.

---

## 11. Je li faza 1 dovoljno cista da faza 2 krene

**Jest, uz dva imenovana uvjeta.**

Pet putova daje pet razlicitih odgovora i ni jedan od njih nije slucajan: cuvar
odbija zapis s replyjem na vratima 4 i propusta cista cetiri, ICP vlast nakon
TASK-982 razlikuje kontradikciju od sutnje, a istrazivacka vlast zadrzava zapis
sa samo slabim dokazima. Dvije izmjene u `src/` ne mijenjaju nijedno ime u
regresijskom skupu od 1433 testa, obje su dokazano sposobne pasti, i produkcijsko
stanje nije dirnuto.

Uvjeti:

1. **TASK-980 se zatvara SPAJANJEM `task-one-os-authority`,** ne novom izvedbom.
   Dok `src/osattribution.py` nije na masteru, sustav zna da je dirnuo leada, a
   ne zna koliko puta ni ciji je to bio dodir — i to je upravo pitanje na kojem
   stoji pravilo STARI LEAD / COLD LEAD iz CLAUDE.md.
2. **Nalaz B ostaje otvoren.** Put slanja ne postavlja ICP pitanje. Danas to
   drzi odabir uzvodno; faza 2, koja radi s vecim kohortama, trebala bi odluciti
   gdje se ta presuda ponovno pita prije slanja.

---

Grana: `task-sandbox-phase1`. Baza: `2bf7b8a5`.
Spis: `tests/test_sandbox_phase1.py` (43 testa).
Izmjene u `src/`: `claims.py` (TASK-981), `icpstructural.py` (TASK-982).
