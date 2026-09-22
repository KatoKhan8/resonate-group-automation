# What people actually ask — Slack question catalogue

Mined from Resonate's own Slack, 2026-09-22. **6,091 messages across 22
channels**; 4,324 usable after sensitive rooms are excluded; **988
questions** classified.

Regenerate with `py -3 scripts/slack_question_catalogue.py --report`.
Raw history is in `work/slack-history/` and is gitignored.

**Every example below is redacted and then hand-checked before it is put
here.** The script's filters are good and not sufficient: they caught
eleven names and missed a twelfth, and a client's domain survived one pass
inside a mangled address. A capitalised-word rule cannot see a name typed
in lower case. So the script proposes and a person disposes — treat
anything it emits as a draft, not as publishable.

---

## 1. WHAT THE HISTORY ACTUALLY IS

Not a support queue. The first read pulled salaries with names and amounts,
a GoDaddy password typed in plain text, personal phone numbers, client
contracts, and four clients' internal threads.

**`#resonate-leadership`, `#računi`, `#finance-weekend-team` and
`#finance-weekend` are never mined.** Their questions are real and they are
none of the agent's business. That is 1,210 messages excluded by name, plus
every message anywhere carrying a credential marker dropped whole rather
than redacted — a sentence about a password is not a question shape worth
keeping even with the password removed.

---

## 2. BY INTENT, MOST FREQUENT FIRST

| Intent | Qs | Who asks | Answered today by |
| --- | --- | --- | --- |
| leads and lists | 175 | internal ≫ client | `lead_lookup`, `account_lookup` — **list counts MISSING** |
| cadence and copy | 110 | internal, some client | `cadence_detail` — **the copy TEXT itself MISSING** |
| senders and domains | 106 | internal ≫ client | `sending_domains`, `sender_roster`, `sender_summary` ✓ |
| replies and meetings | 93 | mixed | `replies` — **meetings booked MISSING** |
| status and volume | 76 | mixed | `sends_today`, `activity_this_week`, `batch_state` ✓ |
| onboarding and access | 24 | internal | **MISSING, and should stay missing** |
| change requests | 24 | **client-heavy** | the ticket flow ✓ |
| reporting | 11 | client | **MISSING** — `clientreport.py` exists and is unwired |
| capacity and planning | 11 | internal | `sender_summary` — **forward book MISSING** |
| other | 358 | — | not outbound questions |

`other` being the largest bucket is the honest headline: **most of what is
said in these rooms is not a question this agent should answer.**

---

## 3. THE PHRASINGS

Croatian dominates internally and in three client channels; English appears
in the Australian and UK-facing ones. Both forms matter because the
keyword fallback runs when no model is configured.

### Senders and domains — answered ✓

> *popis domena s kojih šaljete mailove u email kampanjama*
> *koji od ovih sendera nam trebaju a koji ne?*
> *jel možemo zasad pauzirati tu domenu?*
> *da li mogu sve sendere na tim kampanjama ili ima specifičnih za eu?*
> *kampanja ima visok bounce rate, jesi provlačio kroz [verifier]?*
> *@person mijenjao si sendere?*

Note the shape: almost never "list the domains". Usually **one domain, one
sender, one campaign** — which `sending_domains` answers at the wrong
granularity. Per-domain lookup is a gap worth closing.

### Leads and lists — partly answered

> *Jel ICP? Odgovara [client] teamu?*
> *na koliko leadova smo poslali ... ovaj tjedan?*
> *Jel bilo dobrih leadova danas na heyreach?*
> *predlažem da podijelimo one EU ili safe to send leadove po kampanjama*
> *imamo 1.5 kontakata po domeni?*

**The gap is counting, not looking up.** `lead_lookup` answers "is this
person in a campaign"; nobody asks that. They ask *how many*, *of which
kind*, *ready when*.

### Cadence and copy — partly answered

> *da li poruka samo nakon conn requesta ili da dodamo i još jedan short fup?*
> *imamo 17 varijanti connect requesta?*
> *kak ide follow upanje?*

`cadence_detail` gives the shape. **Nobody has ever asked for the shape.**
They ask what the message *says*. Showing approved copy to a client in
their own channel is a scope decision, not a missing function.

### Replies and meetings — partly answered

> *kakvo je bilo stanje s pozivima do sad?*
> *jel imamo koji meeting još?*
> *Na koliko smo [client] meetinga sada?*
> *should we mark booked ones as DNC also?*

**Meetings booked is the single most-asked number the agent cannot
produce.** It is the number the commercial relationship runs on.

### Change requests — client-heavy, and one of them matters

> **can you please stop sending messages to people who have replied????**
> *I haven't received your content in regards to sequencing for me to
> add/review. Can you send it here, please?*
> *mozemo li u [tool] naziv [client] promijeniti u SUNSET?*

The first is a **client, in a client channel, with four question marks.**
It is a reply-stop complaint, it is the highest-severity shape in this
whole corpus, and the agent's current answer would be to raise a
`stop_account` ticket. That is correct and it is not enough: a question of
that shape should also be visible to the operator immediately.

### Status and volume — answered ✓

> *jesu puštene kampanje sada?*
> *jesmo im ovo bili poslali?*
> *what's the status on that?*
> *na kolko smo?*

### Reporting — missing

> *možeš izvući reports?*
> *monthly report?*

`src/clientreport.py` exists. Nothing calls it from here.

---

## 4. THE TOOLS THIS SAYS TO BUILD, IN ORDER

1. **`meetings_booked`** — replies and meetings, 93 questions, and the
   number the contract is measured by. Needs a source; none is wired.
2. **`lead_counts`** — how many leads are ready / verified / held, by
   cohort. 175 questions want counting, not lookup.
3. **`domain_detail`** — one domain: its mailboxes, health, bounce, which
   campaigns. The real questions are singular, not list-shaped.
4. **`campaign_copy`** — what a step actually says. Client visibility is an
   operator decision first.
5. **`report_link`** — point at the monthly report rather than compose one.

---

## 5. STYLE — HOW RESONATE WRITES TO CLIENTS

Ten exchanges, names replaced by roles, from client channels only.

**It is not report-shaped.** It is short, lower case, warm, and it commits
to a time rather than describing a process.

| # | Client says | Resonate replies |
| --- | --- | --- |
| 1 | *trebam popis domena…* | *može, pošaljemo najnoviju listu danas ili sutra* |
| 2 | *[domain], kakva je ovo domena?* | *momenat, gledam* |
| 3 | — | *šalim se, možemo ju maknuti ak želite, samo .com domene najbolje i prolaze* |
| 4 | *ok, ako radi, nek ostane* | *možemo vidjeti metrike nje u odnosu na druge domene* |
| 5 | *(returns from leave)* | *heeej, you're back!* |
| 6 | *kakav nam je status s ovim leadom?* | *on it, dodala task!* |
| 7 | *can you stop sending to people who replied????* | *(escalation, same day)* |
| 8 | *par info o listi koju si gore poslao?* | *evo spiska svih sendera* + file |
| 9 | *jel ICP?* | *da, i što manje domena sa sličnim paternom* |
| 10 | *when we book a call, do I have to let the team know?* | *(direct answer, no preamble)* |

### What the agent should copy

- **Open with the answer.** "može", "da", "evo" — not "Thank you for your
  question".
- **Lower case, contractions, the odd emoji.** These are colleagues.
- **Commit or say you cannot.** "pošaljemo danas ili sutra" is a real
  answer. "I will check with the team" with no time is the agent's current
  habit and it reads colder than the humans do.
- **Say "momenat, gledam" when looking.** Acknowledging beats silence.

### What it must not copy

- **The humans promise times. The agent may not** — it cannot keep one, and
  a bot's promise becomes Resonate's obligation. This is the one place the
  agent should read differently from the people around it, and the merge
  request says so.
- The humans paste files. The agent posts structured lists it built itself.

---

## 6. WHAT THIS DOCUMENT DOES NOT CONTAIN

No prospect name, no address, no client name, no amount, no credential, no
phone number, and no message from `#resonate-leadership`, `#računi` or
either finance room. Which client asked which question stays in `work/`,
where the scoping rule keeps it: what is read in a client's channel informs
that workspace's answers and nothing else.
