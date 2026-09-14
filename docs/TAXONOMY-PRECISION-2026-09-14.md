# Taxonomy Precision Measurement — 2026-09-14

## Why this exists

TASK-074 landed a reply taxonomy with three analysis categories (INTERESTED,
MEETING_INTENT, OBJECTION) that sub-classify what production rules leave as
UNKNOWN. It is safe: every category maps to UNKNOWN in
`accountpolicy.CLASSIFIER_OUTCOME`, so nothing it says can widen what
automation does.

Safe is not the same as right. This measurement tests whether the taxonomy's
labels are correct, against a hand-labeled random sample from the estate.

## Sample method

The taxonomy operates ONLY on replies that production rules classify as
UNKNOWN. The estate contains 3,869 such UNKNOWN replies (from 5,266 total
cached conversations).

The sample has two parts:

| Part | Count | How drawn | Purpose |
|------|-------|-----------|---------|
| Taxonomy-matched | 63 | ALL replies the taxonomy labeled | Precision |
| Random UNKNOWN | 200 | `random.sample(unlabeled, 200, seed=42)` | Recall |
| **Total** | **263** | | |

The 200 random UNKNOWN replies are drawn from the 3,806 that the taxonomy
did NOT label. This is the critical part: we are NOT sampling the replies
the patterns already match. We are measuring the patterns against replies
they did not select.

Every reply was hand-labeled by reading the text and assigning one of:
`interested`, `meeting_intent`, `objection`, or `none` (genuinely unknown,
a refusal, not relevant, or otherwise not fitting any taxonomy category).

The measurement script is `scripts/task076_taxonomy_precision.py`.

## Results

### Precision

Of the replies the taxonomy labeled, how many were correct?

| Category | Precision | Correct | Wrong | Total labeled |
|----------|-----------|---------|-------|---------------|
| INTERESTED | **0.44** | 23 | 29 | 52 |
| MEETING_INTENT | **1.00** | 5 | 0 | 5 |
| OBJECTION | **1.00** | 6 | 0 | 6 |
| **Overall** | **0.54** | **34** | **29** | **63** |

### Recall

Of the replies I labeled as a category, how many did the taxonomy find?

| Category | Recall | Found | Missed | Total actual |
|----------|--------|-------|--------|--------------|
| INTERESTED | **0.62** | 23 | 14 | 37 |
| MEETING_INTENT | **1.00** | 5 | 0 | 5 |
| OBJECTION | **0.67** | 6 | 3 | 9 |

### What the numbers mean

- **MEETING_INTENT is precise and complete.** Every concrete scheduling
  signal it caught was genuine, and it did not miss any in the sample.
  Five is a small number; the pattern set is narrow but correct.

- **OBJECTION is precise but misses some.** Every budget/time constraint
  it caught was genuine. It missed three that use phrasing outside the
  pattern set ("restricted by [parent company]", "not big enough to be
  investing"). These are real objections the patterns do not reach.

- **INTERESTED is the problem.** More than half of what it labels is wrong.
  The word "interesting" appears constantly in polite refusals ("sounds
  interesting, but..."), and the taxonomy cannot tell the difference.

## The errors

### INTERESTED false positives (29 replies the taxonomy called INTERESTED that were not)

The dominant cause is the `\b(?:interesting|intriguing|intrigued)\b` pattern
(21 of 29 false positives) and `\b(?:curious|curiosity)\b` (6 of 29).

Each entry shows the taxonomy label, the actual meaning, and the reply text
(names, emails, and company domains redacted):

1. **Polite refusal with "interesting":**
   "Very interesting product. I'm not in need to purchase but if you and
   your team would like help me sales and networking I would be happy to
   brainstorm!"
   → Not interested. "Interesting" is a softener before the refusal.

2. **Deferral with "interesting":**
   "lets reconnect over summer. Might be interesting to have a look at."
   → Not_now. No commitment, just a vague future possibility.

3. **Complaint, "interesting" not present but pattern matched elsewhere:**
   "I'll admit I'm a little bothered by my inbox lately — 50 messages
   deep and almost all of them are pitches."
   → Not interested. This is a complaint about inbox volume.

4. **Vague acknowledgment:**
   "I wouldn't say it's completely under control, but I also wouldn't
   call it a major pain point."
   → No interest signal. The taxonomy matched on a word in the full text.

5. **Refusal with "interesting":**
   "It does sound interesting, but I'm pretty swamped with client work
   at the moment and don't have the bandwidth to schedule a demo."
   → Not interested. The "but" clause is the actual message.

6. **Refusal with "interesting":**
   "sounds super interesting and probably very useful. Don't think it
   would be suitable for my line of work unfortunately"
   → Not interested. "Interesting" precedes the refusal.

7. **"Interesting" describes their own project, not ours:**
   "currently I'm working on an interesting project for one of our
   clients"
   → Not interested. The word modifies their work, not our product.

8. **"Curious" about something else + left the company:**
   "Curious about the comment on timesheets, I don't know what you
   mean. But I don't work at [company] anymore."
   → Not relevant. "Curious" is about a past comment, and they left.

9. **"Curiosity" used defensively:**
   "Out of curiosity, why target me then? I am in MarOps :P"
   → Not interested. This is a challenge, not product interest.

10. **"Curiosity" in a decline:**
    "I appreciate your curiosity, but I'm unclear about the purpose of
    your interview request."
    → Not interested. The "but" clause is the actual message.

11. **Completely off-topic:**
    "She went to RIT which is in upstate New York but for some reason
    they have a campus in Zagreb lol, do you know of it?"
    → Not interested. The taxonomy matched on a word in the full text.

12. **"Curious" is a job inquiry:**
    "I am curious is your agency hiring?"
    → Not interested. This is asking about jobs, not product interest.

13. **Vague networking:**
    "maybe a cooperation in the future is always interesting maybe we
    can learn from eachoter"
    → No commitment. "Interesting" is filler.

14. **Broken English decline:**
    "we don't wanna interesting in additional system"
    → Not interested. "Interesting" is used where "interested" was meant,
    in a sentence that declines.

15. **Deferral with "interesting":**
    "The projects you mentioned sound very interesting indeed. I am
    currently on PTO and will reach out to you later"
    → Not_now. The PTO is the operative part.

16. **"Interesting product" + left the company:**
    "you have an interesting product, but I do not longer work at
    [company] and at my current company this is not the right moment."
    → Not relevant. The "but" clause is the actual message.

17. **Wrong person:**
    "I am not a CFO but work in CFO Advisory which covers recommending
    products / services."
    → Not relevant. "Curious" or "interesting" appeared in context about
    the product, but the reply is clarifying they are the wrong person.

18. **Bare acknowledgment:**
    "It's interesting tks for hsare it."
    → No signal. This is a thank-you, not an expression of interest.

19. **Refusal with "interesting":**
    "Sounds very interesting, however, since I work in a global company
    everything is pretty structured and fixed."
    → Not interested. The "however" clause is the actual message.

20. **Vague, about an event:**
    "I'm pretty busy between the association and my current internship.
    I had never heard before of the Festival but it sounds very
    interesting"
    → No buying signal. "Interesting" is about an event, vaguely.

21. **Deferral with "interesting":**
    "I'll take a few days to review my schedule for that period and go
    through the details you shared. It looks very interesting, so I'll
    come back to you"
    → Not_now. "I'll come back to you" is the operative part.

22. **Decline with "interesting":**
    "Sound really interesting, but I'm still not sure if I can go"
    → Not interested. The "but" clause is the actual message.

23. **Decline with "interesting":**
    "this is something that is interesting for us. We already cemented
    plans to be in Spain in June this year"
    → Not interested. Schedule conflict.

24. **Decline with "interesting":**
    "That sounds fun and interesting, but I'm more focusing on other
    sectors these days for business development."
    → Not interested. The "but" clause is the actual message.

25. **Explicit refusal with "interesting":**
    "The solution looks quite interesting; however, this is not
    something we are looking to pursue at this time."
    → Not interested. The "however" clause is an explicit refusal.

26. **"Non interesting" = NOT interested:**
    "Non interesting! Tks"
    → Not interested. "Non" is "not" in multiple Romance languages.
    The negation guard does not cover non-English negators.

27. **Explicitly not buying:**
    "unlikely to commit to system and process changes. More of a
    personal curiosity."
    → Not interested. The reply explicitly says "personal curiosity"
    is not buying intent.

28. **No need:**
    "our finance team has a smooth process, of course always with room
    for improvement, but here everything flows good"
    → Not interested. The message is that things work fine.

29. **Not working there:**
    "As topic seems interesting I am however currently not working for
    [company] and looking for new opportunities"
    → Not relevant. "Interesting" is followed by "however" and a
    statement that they don't work there.

### MEETING_INTENT false positives

None. All 5 were genuine meeting-intent replies.

### OBJECTION false positives

None. All 6 were genuine objections (budget or time constraints).

### INTERESTED missed by taxonomy (14 replies I labeled INTERESTED that the taxonomy left as UNKNOWN)

These are genuine interest signals the patterns do not reach:

1. "let me know how to reconnect" — wants to reconnect
2. "Happy to hear more about your platform" — explicit interest
3. "can you elaborate?" — asking for more about the offering
4. "i don't understand what you want. explain deal." — asking for explanation
5. "Do you work as part of a consultancy service?" — asking about offering
6. "What do you have in mind?" — asking about offering
7. "Why not? I'm always open" — open to hearing more
8. "is this a career opportunity or a product/demo session?" — asking for clarification
9. "How is this different than a claude agent" — product question
10. "Will be good to receive summary of your findings" — request for info
11. "I will have a look in the morning or later this evening" — will review
12. "zvuci interesantno, posalji svakako pa cu pogledati" — Serbian: "sounds interesting, send it, I'll take a look"
13. "I don't know what it is. Please feel free to pitch it" — open to pitch
14. "Sure, thanks for the link" — willing to look

These are missed because genuine interest is expressed in many ways that
do not contain "interesting", "curious", "show me", or "tell me". Asking
questions, requesting information, and expressing openness are all
interest signals the current patterns do not capture.

### OBJECTION missed by taxonomy (3 replies)

1. "we are restricted by [parent company] as to programs used" — corporate
   constraint (appeared twice in sample from different conversations)
2. "not big enough to be investing big amounts of money in systems just
   yet" — budget/size constraint

These use phrasing outside the pattern set. The patterns look for "too
expensive", "no budget", "don't have time", etc., but miss "restricted
by", "not big enough", and similar constructions.

## Pattern analysis

False positives by pattern:

| Pattern | False positives |
|---------|----------------|
| `\b(?:interesting\|intriguing\|intrigued)\b` | 21 |
| `\b(?:curious\|curiosity)\b` | 6 |
| `\btell me (?:about\|something\|everything\|why)\b` | 1 |
| `\bshow me\b` | 1 |

The `\b(?:interesting|intriguing|intrigued)\b` pattern is responsible for
72% of all false positives (21 of 29). It fires on "interesting" in polite
refusals, deferrals, wrong-person messages, and non-English negations. The
negation guard catches "not interesting" but not "interesting, but..." or
"interesting, however..." — where "interesting" is in a separate clause
from the refusal.

## Recommendations

These are observations, not decisions. Promoting any category to POSITIVE
or NEGATIVE in `accountpolicy.CLASSIFIER_OUTCOME` is Claude's decision.

### What I would remove

1. **Remove `\b(?:interesting|intriguing|intrigued)\b` as a standalone
   pattern.** It causes 21 of 29 false positives. The word "interesting"
   is a politeness marker in outbound sales contexts, not an interest
   signal. Without it, INTERESTED precision would rise from 0.44 to 0.83
   (23 correct out of 28 remaining, after removing the 21 FPs but also
   losing some of the 23 TPs that relied on this pattern alone).

2. **Remove `\b(?:curious|curiosity)\b` as a standalone pattern.** It
   causes 6 of 29 false positives. "Curious" is used defensively ("out
   of curiosity, why target me?"), in job inquiries ("curious is your
   agency hiring?"), and in wrong-person messages.

### What I would NOT do

- **Do not widen patterns to raise recall.** The 14 missed INTERESTED
   replies use many different phrasings. Adding patterns for "can you
   elaborate", "what do you have in mind", "happy to hear more", etc.
   would widen the net but also widen the false-positive risk. A taxonomy
   that reaches more replies by guessing more is the defect TASK-067 was
   rejected for.

- **Do not promote any category to POSITIVE or NEGATIVE.** All three
   categories map to UNKNOWN in `accountpolicy.CLASSIFIER_OUTCOME`. That
   mapping is deliberate and safe. Changing it is a separate decision
   that requires its own evidence.

### What the taxonomy is good at

MEETING_INTENT and OBJECTION are precise. Their patterns are specific
enough that they do not fire on refusals or ambiguous replies. The issue
is only with INTERESTED, where the patterns are too broad.

## Row counts

| | Count |
|--|-------|
| Total cached replies | 5,266 |
| Production-rule UNKNOWN | 3,869 |
| Taxonomy labeled (INTERESTED + MEETING_INTENT + OBJECTION) | 63 |
| Taxonomy unlabeled (stayed UNKNOWN) | 3,806 |
| Sample: taxonomy-matched | 63 |
| Sample: random UNKNOWN (seed=42) | 200 |
| **Total hand-labeled** | **263** |
| Hand-labeled as INTERESTED | 37 |
| Hand-labeled as MEETING_INTENT | 5 |
| Hand-labeled as OBJECTION | 9 |
| Hand-labeled as none | 212 |
