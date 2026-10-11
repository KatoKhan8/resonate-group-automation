# SANDBOX FAZA 1 — izvjestaj trake

Grana `task-sandbox-phase1`, baza master
`2bf7b8a571fe11bada4f56fbebeee768ab1e78a8`, 2026-10-03.
Spis: `tests/test_sandbox_phase1.py` — **43 testa, 5.5 s, bez mreze**.
Puni nalaz s tablicom vrata po vratima: `docs/SANDBOX-PHASE1-2026-10-02.md`.

---

## 1. Pet presuda

| # | tvrtka / kontakt | ocekivano | izmjereno | odstupanje |
|---|---|---|---|---|
| 1 | Zyntara Media (SYNTHETIC) / Vera Synthova | ALLOW na vratima 7 | **ALLOW**, 17 vrata | nema |
| 2 | Quorvex Studio (SYNTHETIC) / Milo Mockworth | FRESH + `legacy_touched` + broj + kopija ne tvrdi prvi kontakt | FRESH **da**, 17 vrata; `legacy_touched` **ne postoji**; kopija je **smjela** tvrditi prvi kontakt | **2 x pravi defekt** |
| 3 | Drexlo Performance (SYNTHETIC) / Ines Fauxley | DNC, blokiran na OBA kanala | **blokiran na oba**, `blocked:replied`; cuvar odbija na vratima 4 s 4 vrata u `passed` | nema |
| 4 | Pellumbra Search (SYNTHETIC) / Tomo Dummett | HELD na istrazivanju | **HELD** na `research.why(for_copy=True)`; `li1` ipak ALLOW | **krivo napisan dummy** |
| 5 | Vantiqo Design (SYNTHETIC) / Lena Testova | UNKNOWN -> HELD | prije popravka `icp_pass_with_uncertainty` -> `qualified` -> **ALLOW** | **pravi defekt** |

---

## 2. Tablica vrata — sazetak

Puna tablica (jedan redak po vratima po tvrtki, s trajanjima) je u
`docs/SANDBOX-PHASE1-2026-10-02.md`, odjeljak 2. Sazetak:

| tvrtka | dosegnuta vrata | zadnja prosla | presuda | setanje |
|---|---|---|---|---|
| Zyntara / Vera Synthova | 17/17 | `reserved` | ALLOW | 36.3 ms (*) |
| Quorvex / Milo Mockworth | 17/17 | `reserved` | ALLOW | 16.0 ms (*) |
| Drexlo / Ines Fauxley | **4/17** | `readback` | **REFUSED na `eligibility`** | 10.4 ms (*) |
| Pellumbra / Tomo Dummett | 17/17 | `reserved` | ALLOW | 14.5 ms (*) |
| Vantiqo / Lena Testova | 17/17 | `reserved` | ALLOW | 15.8 ms (*) |

(*) s linijskim tracerom koji mjeri trajanje po vratima; bez njega ~7 ms.
Za Drexlo je **trinaest redaka u punoj tablici oznaceno `NIJE DOSEGNUTO`**,
vidljivo odsutno umjesto tiho izostavljeno.

**Email kanal na razini cuvara je odsutan redak s navedenim razlogom:**
`executionguard` vrata 1 za email zovu `bison.require_workspace`, koji cita zivu
vezu preko zice. `tests/__init__.py` brise `BISON_KEY` za svaki test u paketu, a
pecat po hostu odbija `api.emailbison.com`. Dva nezavisna sigurnosna sloja, i
nijedan nije iskljucen da bi se dobila presuda. Presjek kanala je zato dokazan
sloj nize, u `eligibility`.

---

## 3. Odstupanja — pravi defekt ili krivo napisan dummy

### Slucaj 2, dio `legacy_touched` -> **pravi defekt** (TASK-980)

`legacy_touched` ima **nula pojavljivanja** u `src/`, `scripts/` i `tests/` na
`2bf7b8a5`. `claims.prior_contact_state` i `src/osattribution.py` ne postoje na
bazi (postoje na `task-one-os-authority`, `task-integration-2026-10-03`,
`task-runtime-lane-2026-10-03`). **Sto je kopija stvarno tvrdila:** blok koji
`generate.context_for` preda piscu nosi `prior_contact: True` kao `bool` i nista
vise — nema broja, nema kampanje 327, nema tipa dogadaja.
Dummy je tocan (tri `email_delivered` iz ne-OS kampanje, bez replyja), pa
odstupanje ne dolazi iz njega. **Popravak: spojiti `task-one-os-authority`**, ne
napisati cetvrtu paralelnu izvedbu iste istine.

### Slucaj 2, dio "kopija ne smije tvrditi prvi kontakt" -> **pravi defekt** (TASK-981) — POPRAVLJENO

Prije popravka, protiv zapisa s tri potvrdena slanja:

    claims.check("I am reaching out for the first time ...")      -> []
    claims.check("this is the first time we have written to you") -> []
    claims.check("we have never been in touch before")            -> []

Nula pogodaka za "first time"/"first contact"/"out of the blue"/"cold" u
`claims.py` i `copylint.py`. `implies_prior_contact` hvata izmisljenu povijest;
nista nije hvatalo porecenu povijest koja se dogodila. Popravljeno u
`src/claims.py` (`NO_PRIOR_CONTACT`, `denies_prior_contact`, provjera u `check()`
pod `if contacted:`). Negativne kontrole zelene: hladan zapis i dalje smije reci
"cold outreach", a lazna tvrdnja PRIJASNJEG kontakta i dalje pada.

### Slucaj 4 -> **krivo napisan dummy**

Ocekivani HELD **jest** proizveden, od vlasti koja je za njega nadlezna:
`research.why(rec, for_copy=True)` vraca
`public_evidence_required_for_prospect_facing_copy` (tri reda, 0 prihvatljivih).
ALLOW se dogodio jer je dummy setao `li1`, jedini korak u
`productive_li_heavy_v1` koji nosi `template` — renderira se bez modela i bez
ijedne cinjenice iz istrazivanja, ne tvrdi nista o tvrtki, `claims.check` vraca
`[]`. Slucaj za "ne smije nastaviti na halucinaciji" mora setati korak koji
halucinaciju moze nositi. Dummy popravljen: hold se tvrdi na svojoj vlasti,
a ALLOW na `li1` se tvrdi eksplicitno zajedno s razlogom.

### Slucaj 5 -> **pravi defekt** (TASK-982) — POPRAVLJENO

8 od jednog izvora, 40 od drugog, pod je 14. `headcount.resolve` -> `conflict`,
`_employees` -> `unknown` (ispravno), ali `verdict_of` je to upio u
`icp_pass_with_uncertainty`, `FROM_STRUCTURAL` to mapira u `qualified`, i zapis
je dosao do vrata 7 s **ALLOW**. Kontradikcija nije sutnja: jedan od dva izvora
je afirmativan dokaz da je tvrtka premala. Popravljeno u `src/icpstructural.py`
— kontradiktoran kriterij ide u `ICP_REVIEW`, nikad u FAIL. Poslije popravka:
`icp_review`, `eligible: False`, `icp.score -> review`.
**Opseg na zivoj produkciji (samo citanje): 10 od 1.584 Productive zapisa ima
kontradikciju u broju zaposlenih, 5 od njih je bilo `icp_pass_with_uncertainty`.**

### Dva nalaza s obje strane, NAMJERNO nedirnuta

* **A:** hold na istrazivanju nije vrata na putu slanja (`eligibility` i
  `executionguard` ne drze modul `research`). Za `li1` je to ispravno; za
  generirane korake stite `copylint`/`claims`; a nacrt koji se oslanja na slab
  red ipak dobije `held:evidence_aged_out`.
* **B:** put slanja uopce ne postavlja ICP pitanje. Nakon TASK-982 vlast kaze
  REVIEW, ali `eligibility.decide` i dalje kaze `eligible` i cuvar i dalje dode
  do vrata 7. Prosirenje `eligibility` da pita ICP odbilo bi i svaki
  `not_processed` zapis, sto mijenja znacenje rijeci "eligible" za cijeli
  estate — zato nije napravljeno. Pripada fazi 2.

---

## 4. Dokaz da produkcija nije dirnuta

| | |
|---|---|
| `work/campaigns.jsonl` prije | `fb7d7bfe0b1cbdb99a7c9bc5e52210df` |
| `work/campaigns.jsonl` poslije | `fb7d7bfe0b1cbdb99a7c9bc5e52210df` — **nepromijenjen** |
| `work/queue.jsonl` prije (pocetak trake) | `72cb039ffbad853515c4d4c01eecec44` |
| `work/queue.jsonl` poslije (kraj trake) | `a52353e14233996737c44de927afb1c3` — **promijenjen, i to NE od mene** |

`queue.jsonl` se promijenio jer u paralelnoj traci trci generiranje, sto je
operator odobrio. Dokaz zato nije jedan globalni par md5-ova nego **43 para**:
svaki test uzme md5 obje produkcijske datoteke u `setUp` i usporedi ih u
`addCleanup`, pa tvrdi bajt-identicnost preko vlastitog prozora izvodenja.
43 zelena testa = 43 jednake usporedbe. Da je bilo koji moj test pisao u
produkcijski `work/`, taj bi test pao.

`_production_root()` razrjesava GLAVNI checkout kroz `.git`, jer radno stablo
nema `work/` — inace bi usporedba bila `None` prema `None`, test koji ne moze
pasti. `setUp` tvrdi da obje datoteke postoje.

Spremiste je kopija; pomak je tvrden na `queue_path()` **i zasebno** na
`campaigns_path()`:

    sandbox queue_path    : ...\Temp\sandbox-phase1-6qk8e3mq\work\queue.jsonl
    sandbox campaigns_path: ...\Temp\sandbox-phase1-6qk8e3mq\work\campaigns.jsonl

Provider upisi: **0**. Slack: **0**. OpenRouter: **0 USD** — nijedan od pet
slucajeva ne treba pisca (`li1` je sablona, `em1` je pohranjena kopija).

---

## 5. Pozitivna kontrola koja dokazuje da je pecat bio ziv

Trci u `setUp` **svakog** slucaja, prije bilo koje sonde:

    GET api.emailbison.com -> WireSealed: the wire is sealed:
    GET api.emailbison.com is not the writer's host.
    Allowed: ('openrouter.ai',). Nothing was sent.

    writer host allowed by the seal: True ('openrouter.ai',)
    hosts reached during the walk: {'api.emailbison.com'}   <- samo kontrola

Pecat je po HOSTU, ne po transportu: pisac i provider dijele isti sav
(`providers.set_transport`), pa slijepi sentinel ubija i generiranje — to je
srusilo prvi pokusaj faze 0. OpenRouter propusten, svaki drugi host odbijen.

---

## 6. Dokaz da testovi mogu pasti

| mutacija | md5 | ucinak |
|---|---|---|
| baseline `claims.py` | `2c6464b0005355221bd23665ac367480` | 43 prolaze |
| `if contacted:` -> `if False:` | `2563b448a15b5e8cfc7b0f76120e1ebb` | **3 crvena**, imenuju `test_the_copy_must_not_claim_a_first_contact` |
| vraceno | `2c6464b0005355221bd23665ac367480` | 43 prolaze |
| baseline `icpstructural.py` | `782214e2b0d700b85405bc485ccc5127` | 43 prolaze |
| grana `contradicted` uklonjena | `6cdb73587e36a347801d58ecb195db2a` | **1 crveno**, `test_a_contradiction_goes_to_review_and_never_to_eligible` |
| vraceno | `782214e2b0d700b85405bc485ccc5127` | 43 prolaze |

`__pycache__` obrisan prije svake; datoteke su CRLF pa se usporeduje md5.

---

## 7. Regresija — razlika skupa IMENA

**Puni paket NIJE pokrenut** (koordinator drzi strojnu bravu; brief to
zabranjuje). Pokrenut je najsiri skup pojedinacnih modula koji moje dvije izmjene
u `src/` mogu vidjeti: **54 testna modula** koja spominju `claims.`,
`icpstructural.` ili `headcount.`. Baza izvucena u zasebno radno stablo na istom
SHA `2bf7b8a5`, ista metoda s obje strane, `__pycache__` obrisan oba puta.

| | baza `2bf7b8a5` | grana |
|---|---|---|
| testova | 1433 | 1433 |
| rezultat | `failures=19, errors=17, skipped=2, xfail=4` | identicno |
| imena koja padaju | 32 | 32 |
| **novo pada** | — | **0** |
| **vise ne pada** | — | **0** |

`tests.test_fixture_hygiene`: **istih 5 imena pada na bazi i na grani** — moje
datoteke ne dodaju nijedan higijenski pad.

Kao pozitivna kontrola baze, prije nego sto je faza 1 napisana, pokrenut je
spis faze 0 (`tests/test_golden_path.py` s `task-golden-path`) na `2bf7b8a5`:
**39 testova, 2.844 s, OK**. Ta datoteka nije commitana ovdje — pripada fazi 0.

PII: diff skeniran za adrese, prave domene, IPv4 i oblike kljuceva — cist.
Sve domene su na `.invalid`, sva imena ocito sinteticka.

---

## 8. Je li faza 1 dovoljno cista da faza 2 krene

**Jest, uz dva imenovana uvjeta.** Pet putova daje pet razlicitih odgovora i ni
jedan nije slucajan. Dvije izmjene u `src/` ne mijenjaju nijedno ime u
regresijskom skupu od 1433 testa, obje su dokazano sposobne pasti, produkcijsko
stanje nije dirnuto.

1. **TASK-980 se zatvara SPAJANJEM `task-one-os-authority`**, ne novom izvedbom.
   Dok `src/osattribution.py` nije na masteru, sustav zna da je dirnuo leada ali
   ne zna koliko puta ni ciji je to bio dodir — a na tome stoji pravilo
   STARI LEAD / COLD LEAD iz CLAUDE.md.
2. **Nalaz B ostaje otvoren**: put slanja ne postavlja ICP pitanje. Danas to drzi
   odabir uzvodno; faza 2 radi s vecim kohortama i treba odluciti gdje se ta
   presuda ponovno pita prije slanja.
