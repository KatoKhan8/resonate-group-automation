# TASK-425 — sažetak za operatera

**Hrvatski, bez žargona, prema `docs/OPERATING-MODE.md` "OPERATER FEED".** Tehnički
identifikatori ostaju kakvi su u kodu. Puni tehnički artefakt je
`docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md`, a nalazi su u
`docs/TASK-425-FINDINGS-2026-09-28.md`.

---

## STVARNI PROSPEKTI

**Ništa nije poslano. Ništa nije aktivirano, nastavljeno, pauzirano, upisano ni
priključeno. Provider writes = 0.** Kampanje 487, 489 i 493 nisu dotaknute.

Provjereno po SADRŽAJU, ne po vremenu izmjene: `queue.jsonl` **nema ni jedan red
ovog testa** (0 od 1.582 reda), a `campaigns.jsonl`, `workspaces.jsonl` i
`spend-ledger.jsonl` su bajt-identični po sha256 prije i poslije. Vrijeme izmjene
ovdje nije mjerilo — 23 procesa rade iz glavnog checkouta od 24.9. i sami pišu u
`queue.jsonl`, pa on jest promijenjen, ali ne od ovog testa.

Cijeli test radio je u privremenom direktoriju koji se briše. Nula je dokazana, ne
tvrđena: postavljena su dva presretača na jedinu točku kroz koju svaki provider
prolazi, i **oba su namjerno okinuta** na pravoj EmailBison adresi, jer presretač
koji nikad nije upaljen izgleda isto kao čist prolaz.

---

## ŠTO SI TRAŽIO, I ŠTO SI DOBIO

> **ISPRAVAK, 2026-09-28 13:10.** Prva verzija ovog sažetka pisala je "tri su
> prošla, jedan je blokiran" i kriterij 1 kao PROŠLO. **To nije bilo točno.**
> Mjerenje na kojem je taj zaključak stajao usporedilo je TRI RAZLIČITE OSOBE:
> prolaz A napisao je tekst za jednu osobu, a njegova vlastita kontrola za drugu,
> pa razlika između njih nije bila o sustavu. Ponovljeno mjerenje je u
> `docs/TASK-425-FINDINGS-2026-09-28.md`, sekcija 0.
>
> **Točno stanje: dva kriterija su prošla (3 i 4), dva su BLOKIRANA (1 i 2).**

Četiri kriterija koja si zamrznuo 2026-09-27.

### 1. Uzročna matrica — **BLOKIRANO**

Jedan račun, četiri prolaza, svaki put mijenja se JEDNA stvar, a peti prolaz je
kontrola: isti ulaz dva puta.

**Kontrola sada radi i dva prolaza su čist dokaz.** U ponovljenom mjerenju
kontrola je dala BAJT-IDENTIČNE upite na svim dijelovima koji ovise samo o ulazu,
za istu osobu. Kad se promijenila jedna činjenica (prolaz B), ti su se upiti
pomakli i cijeli tekst se promijenio — to je uzročnost, izmjerena, ne tvrđena.
Kad se promijenila persona (prolaz C), ponuda se prebacila s A na B, sve tri
sposobnosti su se zamijenile i ljestvica koju stroj provodi zamijenila se cijela.

**Zašto je ipak blokirano:** stroj za pisanje teksta **ne uspijeva pouzdano
napisati tekst za IMENOVANU osobu.** Matrica traži istu osobu s obje strane svake
usporedbe, a kroz tri puna mjerenja imenovani kontakt prošao je u 3 od 5, 1 od 5
i 2 od 5 prolaza. U jednom mjerenju odbijeno je **osamnaest nacrta po prolazu** —
svaki od strane prave provjere s pravim razlogom. Prolazi C i D zato nisu
usporedivi.

Dakle: uzročni mehanizam radi. Ono što ne radi je stroj za tekst, i to je sljedeći
zadatak, ne popravak mjerenja.

### 2. Potpis pošiljatelja — **BLOKIRANO, i to je bio očekivani ishod**

Nijedna karika lanca ne nosi potpis. Ni lokalni model poštanskog sandučića, ni
`sender` blok u klijentovoj konfiguraciji, ni inventar pošiljatelja, ni projekcija
prema provideru, a ni krajnja poruka onako kako bi je primatelj vidio: završava
bez potpisa.

**Potpis nije izmišljen da bi kriterij prošao.** Što piše u potpisu je tvoja i
klijentova odluka, a napisati ga sam značilo bi staviti riječi koje nitko nije
odobrio na dno svakog e-maila. Ovo je standing launch blocker 3 i ostaje otvoren.

### 3. Redoslijed ponude kao ciljevi koraka — PROŠLO

Ljestvica koju si odobrio (za Ponudu A: vidljivost marže, ponuda protiv potrošnje,
odluke o ljudima koje pomiču maržu, mehanizam samo ako pojačava kut, preokvir i
zatvaranje) **do sada je bila zapisana u konfiguraciji i nitko je nije čitao.** U
istoj datoteci stajalo je "provodi se" i, red niže, "još nije provedeno".

Sada se provodi. Slijed koji krši ljestvicu je ODBIJEN, odbijenica imenuje koji
korak i koju rungu, i dokazano je da odbija upravo ta provjera: kad se ona
isključi, isti pokvareni slijed prođe do kraja.

### 4. Revizijski zapis po poruci — PROŠLO

Za svaku poruku: glavni problem, izabrana ponuda i zašto, izabrane sposobnosti,
je li i koja AI sposobnost upotrijebljena i zašto je relevantna, izvor i njegova
provjerljivost, točna tvrdnja koja je licencirana i gdje se pojavila u tekstu.
Plus: činjenice s izvorima, strategija, cijeli e-mail i LinkedIn tekst, obje
provider projekcije, suppression, trošak i provider writes = 0.

---

## ŠTO JE OVAJ TEST NAŠAO, A NISI ZNAO

Petnaest nalaza. Tri su odmah popravljena. Pet je upisano u kanonski registar
problema kao ISSUE-050 do ISSUE-055. **Jedan je važniji od ostalih:**

🔴 **Izmišljen broj prolazi kroz OBA sita ako rečenica ne spominje primatelja.**
Oba sita gledaju samo rečenice koje govore "vi" ili "vaše". Rečenica poput "marža
od 40 posto tiho padne na 25 posto kad se obuhvat proširi" ne spominje primatelja,
pa je nitko ne provjerava. Te brojke je izmislio model, prošle su i bile
zapisane. Ispravak je zatvoren jer mijenja što smije izaći za svaki postojeći
lead, a to je tvoja odluka, ne moja. **Predlažem da to bude prvi zadatak nakon
tvojeg pregleda.**

Ostalo, kratko:

- Put strategije **nije mogao pročitati vlastiti model** i rušio je cijeli prolaz
  na prvom odgovoru u ogradicama. Popravljeno.
- Provjera "dva ista naslova" odbijala je **ispravno vođen razgovor**, jer je
  dobivala jedan naslov po koraku umjesto jedan po nizu. Popravljeno.
- Svaki LinkedIn korak mjeri se kao **zahtjev za povezivanje od 300 znakova**,
  premda poruka ima pravo na 1900. Jedna predugačka poruka odbila je cijeli
  kontakt i povukla pet e-mailova sa sobom.
- Pisac emitira **četiri LinkedIn poruke za peterostupanjsku kadencu**, pa peti
  korak nikad nema tekst i HeyReach ga odbija.
- **Put pisanja teksta je na granici.** S istim ulazom neki prolaz da cijeli niz
  koji prođe sve provjere, a neki se zaustavi na jednoj rečenici. Artefakt piše
  koliko je pokušaja svaki prolaz trebao. To je najiskreniji odgovor na pitanje
  koliko je stroj blizu spremnom: nije "radi".

---

## ŠTO NISAM MOGAO IZMJERITI

- **Killswitch.** `sending.live` je ugašen za `productive`, ali test bez upisa ga
  nikad i ne pročita jer se vraća prije toga. Ovaj prolaz **nije** dokaz da
  killswitch radi. Dokaz je
  `tests/test_sending_live_off_blocks_only_our_new_writes.py`.
- **`copylint` na LinkedIn tekstu na putu do providera.** Tamo ga nema uopće.
  LinkedIn tekst prošao je kroz `lint`, `claims` i provjeru ponavljanja, ali ne
  kroz `copylint`.
- **Deset računa.** Izvan opsega, po tvojoj izričitoj uputi.

---

## TREBAM OD TEBE

Ništa dok ne pročitaš artefakt. Zadatak staje ovdje, kako si i rekao. Ništa nije
mergeano na master; sve je na grani `task-425-one-account-dry-run`.
