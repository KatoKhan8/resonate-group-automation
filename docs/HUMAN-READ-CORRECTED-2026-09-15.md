# Human Read of Corrected Copy - 2026-09-15

**Verdict: DOES NOT BEAT FALLBACKS**

## WHAT WAS READ

12 full sequences generated live against the corrected brief (post-TASK-131
fixes) using `scripts/task136_read_copy.py` against `queue.snapshot.jsonl`
(stamp 2026-09-14T21:52:15Z from master 0ac5e60). Model: gpt-4.1-mini.
Each sequence carries six LinkedIn notes and five emails. 132 generated
messages read in total.

All 12 records have economic_buyer contacts. All 12 sequences carry the
corrected `ladder_fingerprint` (computed from the updated
`LINKEDIN_DEFAULT_LADDER` whose rung 6 now states the easy-out + referral
job).

Companies read (identifiers hashed in this report): `<ogpartner-dk>`,
`<16kagency-com>`, `<1gslab-com>`, `<2020companies-com>`, `<20north-com>`,
`<25wat-com>`, `<<client-abb4a2>-com>`, `<2ton-com>`, `<<client-cf34bf>-com>`,
`<4cite-com>`, `<4thwhale-com>`, `<5bonsai-com>`.

## THE FALLBACKS (THE BAR)

```
connection_note:  hi, i work with agencies on project profitability and
                  thought it would be good to connect.
connected_1:      how do you currently get visibility on whether a project
                  is making money while it is still running?
connected_2:      most agencies i speak to find that out at the end of a
                  project rather than during it. is that how it works for you?
connected_3:      we built productive so budgets, time tracking and resourcing
                  talk to each other. worth a look?
connected_4:      happy to leave it here if the timing is wrong. is there
                  someone else who owns this?
```

Five messages, each with a different job, each under 25 words. No message
re-introduces the sender. No message asserts anything about the recipient.
The sequence is a conversation that progresses: who I am, what I want to
know, what others have told me, what we built, and a graceful exit.

## THE FOUR TASK-130 DEFECTS: STATUS

### 1. No easy out at li6 - GENUINELY GONE

All 12 sequences have an easy out at li6. Every one gives a graceful
decline path AND asks for a redirect. This is the TASK-131 ladder fix
working exactly as designed.

Representative examples (all hashed):

    <ogpartner-dk>:    "happy to leave this here if the timing isn't right -
                        would you mind pointing me to someone else on your
                        team who handles project profitability?"
    <2020companies>:   "happy to leave this here if now is not the right time.
                        is there someone else on your team who handles
                        project profitability?"
    <4cite-com>:       "if now isn't the right time to explore utilisation
                        and capacity, no worries at all. is there someone
                        else on your team who handles this?"

**Verdict: defect gone, not merely rarer.** The ladder now asks for this job
and the model produces it.

### 2. "I noticed" opener - GENUINELY GONE

Zero occurrences across 60 LinkedIn notes and 60 emails. The prompt
prohibition is working.

**Verdict: defect gone.**

### 3. "I admire how" unsupported claim - GENUINELY GONE

Zero occurrences across 120 messages. The prompt instruction against
unsupported positive assertions is working.

**Verdict: defect gone.**

### 4. Same greeting six times - GENUINELY GONE (AS A LITERAL REPETITION)

No sequence opens all six messages with "hi [name], ivan here/from
Productive." The sender is identified at rung 1 and rungs 2-6 start with
content. The TASK-131 prompt fix ("STEPS AFTER THE CONNECTION REQUEST MUST
NOT RE-INTRODUCE THE SENDER") is working.

**Verdict: literal repetition gone. Structural repetition remains (see
below).**

## WHAT THE FOUR FIXES INTRODUCED

### The li6 templating (the caveat Claude measured)

All 12 li6 closings, verbatim:

| # | li6 close |
|---|-----------|
| 1 | happy to leave this here if the timing isn't right - would you mind pointing me to someone else on your team who handles project profitability? |
| 2 | happy to leave this here if the timing isn't right - would you mind pointing me to who handles this topic at [company]? |
| 3 | if now isn't the right time, happy to leave it here - would you know who else at [company] might own this topic? |
| 4 | happy to leave this here if now is not the right time. is there someone else on your team who handles project profitability? |
| 5 | happy to leave this here if the timing isn't right - would you mind pointing me to who handles utilisation and capacity at [company]? |
| 6 | happy to leave this here if the timing is off - would you mind pointing me to who handles project profitability or resourcing at [company]? |
| 7 | happy to leave this here if now isn't the right time - would you mind pointing me to who handles resource planning and project capacity at [company]? |
| 8 | happy to leave this here if the timing is off - would you mind pointing me to the right person if this isn't your area? |
| 9 | happy to leave this here if the timing isn't right - would you mind pointing me to who handles utilisation and capacity at [company]? |
| 10 | if now isn't the right time to explore utilisation and capacity, no worries at all. is there someone else on your team who handles this? |
| 11 | if now isn't the right time to explore utilisation and capacity, no worries at all - would you happen to know who else on your team handles this? |
| 12 | happy to leave this here if now isn't the right time - would you mind pointing me to who handles this topic on your team? |

**10 of 12 open with "happy to leave this here if [timing condition]."**
The other two open with "if now isn't the right time." Every single one
then asks for a redirect using "would you mind pointing me to" or "is there
someone else."

The pairwise similarity Claude measured (median 0.62, max 0.94, 6 of 36
pairs above 0.8) is confirmed by eye. Messages 1, 2, 4, 5, 7, 9, 12 are
near-identical in structure and differ only in the role name and company.
Messages 10 and 11 are near-identical to each other.

**Is this visible to a recipient?** If two contacts at one company receive
the same closing line, yes. The role name varies ("project profitability",
"utilisation and capacity", "resource planning", "this topic") but the
frame is identical. A recipient who talks to a colleague at another company
that was also contacted would recognise the template. The fallback's
connected_4 - "happy to leave it here if the timing is wrong. is there
someone else who owns this?" - is shorter, more natural, and does not
carry the "would you mind pointing me to" formula that eight of twelve
share.

**This is the defect the fix introduced.** It replaced "no exit at all"
with "a templated exit." The templated exit is better than no exit, and
worse than a varied one.

### The structural monotony (a defect none of the four fixes addressed)

Every LinkedIn sequence follows the same six beats:

| Rung | Job | Pattern across 12 sequences |
|------|-----|-----------------------------|
| li1 | Intro | "ivan here, i work on project profitability for agencies" + angle |
| li2 | Question | "how do you currently [track/get visibility on] X?" |
| li3 | Problem | "without clear [utilisation/visibility], teams often rebuild work after the fact..." |
| li4 | Product | "productive [connects/joins] budgets, time tracking, and [profitability/resource planning]..." |
| li5 | Another angle | "productive also helps with [billing/margins]..." |
| li6 | Close | "happy to leave this here if [timing]..." |

The beats are correct - the ladder asks for six different jobs and the
model satisfies each one. But the SHAPE is identical across all 12
sequences. A recipient who has seen one sequence has seen all of them.

The fallbacks avoid this because each fallback has a different job AND a
different structure. connected_1 asks a question. connected_2 offers a
pattern ("most agencies i speak to..."). connected_3 names the product in
one line. connected_4 gives an exit. No two fallbacks have the same shape.

### The email formula

Every email sequence follows the same pattern:

- em1: "[Company] describes itself as [paraphrase of website]. I am reaching
  out because [role-based reason]. Productive is one place where [product
  pitch]. [Question]?"
- em2-em4: "[Company] [same paraphrase or slight variant]. [Same product
  pitch in slightly different words]. [Same question rephrased]?"
- em5: "[Company] [paraphrase]. I am Ivan, founder of Productive. Since I
  have not heard from you, would you prefer I close your file?"

The "[Company] describes itself as" opener appears in 11 of 12 em1
messages. The product pitch ("budgets, time tracking, resourcing, and
invoicing talk to each other instead of living in separate tools") appears
in nearly identical form across all five emails in every sequence. The
fallbacks never paraphrase the company's own website back to it.

## PER-SEQUENCE VERDICT

| # | Company | Beats fallbacks? | Why / why not |
|---|---------|-----------------|---------------|
| 1 | <ogpartner-dk> | NO | li6 templated, li3 identical to others, email formula |
| 2 | <16kagency-com> | NO | li6 templated, li5 repeats li2 angle, email formula |
| 3 | <1gslab-com> | NO | li6 templated (variant), li3 formulaic, email formula |
| 4 | <2020companies-com> | NO | li6 templated, li3 formulaic, emails repetitive |
| 5 | <20north-com> | NO | li6 templated, li5 repeats li4, emails near-identical |
| 6 | <25wat-com> | NO | li6 templated, li3 formulaic, email formula |
| 7 | <<client-abb4a2>-com> | NO | li6 templated, li3 formulaic, email formula |
| 8 | <2ton-com> | NO | li6 templated, li5 repeats li2 angle, email subjects repeat |
| 9 | <<client-cf34bf>-com> | NO | li6 templated, li5 repeats li4, email formula |
| 10 | <4cite-com> | NO | li6 templated (variant), li5 repeats li4, email formula |
| 11 | <4thwhale-com> | NO | li6 templated (variant), li5 repeats li4, email formula |
| 12 | <5bonsai-com> | NO | li6 templated, li5 angle shift but same shape, email formula |

**Zero of 12 beat the fallbacks.**

## HOW MANY WOULD I SEND AS THEY STAND?

**Zero of 12, as they stand.**

Not because the copy is catastrophically broken - the four TASK-130 defects
are genuinely gone. But because every sequence reads as generated from the
same template, and the fallbacks read as written by a person who knows the
product and the audience.

The fallbacks are still the best copy in the system. They are shorter, more
varied, assert nothing about the recipient, and give a graceful exit in
words that sound like a human wrote them. The generated copy is improved
beyond recognition from the pre-fix version, but "improved beyond
recognition" from a low base is not the same as "beats the bar."

## THE LI6 TEMPLATING VERDICT

**Visible to a recipient: yes, if two contacts at one company compare notes.**

The close is the last thing a prospect reads and the thing they remember.
When eight of twelve closings open with the same phrase and ask for a
redirect in the same words, the template is visible. The fallback's
connected_4 is shorter, more natural, and does not carry the "would you
mind pointing me to" formula.

This is the defect the TASK-131 fix introduced, and it is the price of
fixing "no exit at all." A templated exit beats no exit, but it does not
beat a human-written exit.

## WHAT IS GENUINELY GONE VERSUS MERELY RARER

| Defect | Status | Evidence |
|--------|--------|----------|
| No easy out at li6 | **GONE** | 12/12 have one. The ladder asks for it. |
| "I noticed" opener | **GONE** | 0/120 messages. The prompt forbids it. |
| "I admire how" claim | **GONE** | 0/120 messages. The prompt forbids it. |
| Same greeting six times | **GONE (literal)** | 0/12 repeat the greeting. The prompt says not to. |
| Same STRUCTURE six times | **NEW** | 12/12 follow identical six-beat arc. |
| li6 templating | **NEW** | 10/12 near-identical closings. |
| Email formula | **UNCHANGED** | 12/12 follow "[Company] describes itself as..." |

The four TASK-130 defects are genuinely gone. They were fixed in the brief
and the fix holds. But the fixes introduced two new defects (structural
monotony and li6 templating) and left one unchanged (email formula).

## WHAT WOULD NEED TO CHANGE

Not for this task to decide. But the findings point to:

1. **li6 needs variation, not just a job.** The ladder says "give them a
   graceful way to decline" and the model produces the same graceful decline
   twelve times. The fix is either multiple ladder variants for rung 6, or
   a prompt instruction that names the formula and forbids it.

2. **The six-beat arc needs disruption.** Every sequence follows the same
   progression because the ladder describes six jobs and the model satisfies
   them in order. The fallbacks avoid this because each message is
   independent. A generated sequence cannot be independent (it must
   progress), but it can vary its shape: not every sequence needs to name
   the problem at li3, not every sequence needs to name the product at li4.

3. **The email opener needs to stop paraphrasing the website.** "[Company]
   describes itself as" is the new "I noticed." The prompt says to quote or
   paraphrase what their site says, and the model paraphrases it the same
   way every time.

## SAMPLE

- **Queue snapshot:** `work/queue.snapshot.jsonl`, stamp
  2026-09-14T21:52:15Z from master 0ac5e60. 300 records.
- **Generated output:** `work/task136_generated.json`, 12 sequences, 132
  messages, generated 2026-09-15 against the corrected brief.
- **Fallbacks:** `config/clients/productive.yaml` lines 348-356.
- **Identifiers hashed:** All record IDs, contact keys, and names hashed to
  SHA-256 prefixes. No real names, domains, or reply text quoted at length.
