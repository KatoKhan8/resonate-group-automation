# Three questions to Productive, 2026-10-02, and what the system does until they are answered

The operator's own draft, kept verbatim because the wording is the ask and a
paraphrase would change what was agreed. **It is recorded here, not sent from
this system** — no outbound mail leaves without the operator, and this is the
operator's own message to their client.

---

> **Subject: Outbound copy: tri stvari koje trebam od vas**
>
> Bok {ime},
>
> Prije nego pustimo prvu sekvencu, tri pitanja o ponudi u mailu.
>
> 1. Smijemo li prospektu unaprijed konfigurirati workspace iz javnih podataka
>    (tim s LinkedIna, usluge sa stranice, tri tipična projekta) i reći mu da ga
>    zadrži 30 dana bez obveze? To bi bio glavni "give" u prvom mailu umjesto
>    generičkog triala.
>
> 2. Imate li benchmark po veličini agencije (utilizacija, marža, billable rate
>    za 30 do 60 ljudi u digitalu) koji smijemo citirati u follow-upu?
>
> 3. Dvije agencije klijenti s brojem koji smijemo napisati, npr. "{Agencija} je
>    nakon Productivea X". Imena i broj trebaju biti odobreni s vaše strane, jer
>    ih sustav ne smije koristiti bez toga.
>
> Bez 1 i 3 sekvenca ide bez ponude i bez dokaza, i to je slabiji mail nego što
> želimo poslati u vaše ime.
>
> Hvala,
> Zvonimir

---

## What each answer unblocks

| question | what it unblocks | what happens without it |
|---|---|---|
| 1 — the pre-configured workspace | em1's **give**, and em5's close ("the workspace stays yours for 30 days") | `OFFER-GIVE-001` stays `client_approved: false`, so copy generates but **eligibility HOLDS `offer_unapproved`** |
| 2 — the size-banded benchmark | a benchmark in **em3 or em4** | the benchmark block is **omitted**, never invented — recorded in the offer as `benchmark_placement` |
| 3 — two agencies with a number | **em3's role**, which is proof with a named client and a number | em3 is **HELD `proof_required`**: TASK-964 requires TWO licensed proof rows and there are currently **zero** |

## The working hypothesis, as data

The operator's hypothesis of 2026-10-02 night is recorded in
`config/clients/productive-offers.yaml` as **`OFFER-GIVE-001`**:

- the give is a workspace pre-configured from **public data only** — the team
  from LinkedIn, the service lines from the website, three typical projects —
  kept for 30 days;
- em2's smaller piece is **one screenshot of the next four weeks of bookings
  against budget**;
- em5 closes with **the workspace stays yours for 30 days**;
- the benchmark goes to em3 or em4 **only if the client confirms the figures**.

**Two flags, two different questions, and the separation is the whole design:**

    approval_status: approved      may the WRITER use it?  Yes - the operator
                                   supplied every term and wants the sequence
                                   generated so it can be read tomorrow.
                                   approved_by: Zvonimir, 2026-10-02, cd8e00bc.
    client_approved: false         may anything be SENT with it?  NO.

So the operator sees what the sequence looks like in copy-review, and nothing
can reach a prospect until Productive answers. **Generation is not sending**, and
this is the first place in this repository where that distinction is written as
two fields rather than argued in prose.

The same rule governs proof rows: a row with `client_approved: false` blocks the
SEND, not the generation.

## What is NOT decided here

Whether the 30 days with no obligation is a commercial term Productive will
stand behind. It is the operator's wording and it is in `conditions` with that
noted — a commercial term invented by this system would be the worst defect in
the file.
