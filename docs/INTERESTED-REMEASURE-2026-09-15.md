# INTERESTED Re-measure — 2026-09-15

## Why this exists

`docs/TAXONOMY-PRECISION-2026-09-14.md` measured the OLD INTERESTED pattern set
at precision 0.44, recall 0.62 on a 263-reply sample. More than half of what
it called INTERESTED was wrong — the bare adjective "interesting" is a
politeness marker in outbound sales contexts, not an interest signal.

The bare adjectives were removed and replaced with specific constructions
where the sender ASKS FOR SOMETHING. This measurement tests whether the NEW
set is any good.

## Sample method

| Parameter | Value |
|-----------|-------|
| Pool | 3,893 UNKNOWN replies with text (from 26,174 cached conversations) |
| Sample size | 200 |
| Seed | 109 (different from the original 42) |
| Labelling method | Hand-labelled blind to classifier output |
| Labelling date | 2026-09-15 |
| Classifier version | `rules-3` (src/replies.py, commit 92dcbef) |

The sample was drawn from the same UNKNOWN pool as the original measurement
but with a different seed, so the samples do not overlap. Every reply was
read and assigned one of: `interested`, `meeting_intent`, `objection`, or
`none` (genuinely unknown, a refusal, not relevant, or otherwise not fitting
any taxonomy category).

The classifier was then run on each reply, and the taxonomy verdict (if any)
was compared to the hand-label.

## Results

### Taxonomy coverage

The taxonomy fires on **20 of 3,893** UNKNOWN replies in the full pool (0.5%).

| Category | Fires on |
|----------|----------|
| INTERESTED | 9 |
| MEETING_INTENT | 5 |
| OBJECTION | 6 |
| **Total** | **20** |

In the 200-reply sample, the taxonomy fires on **0 replies**.

### Precision and recall on the fresh sample (n=200)

| Category | Precision | Recall | TP | FP | FN | Actual | Predicted |
|----------|-----------|--------|----|----|----|--------|-----------|
| INTERESTED | **0.00** | **0.00** | 0 | 0 | 15 | 15 | 0 |
| MEETING_INTENT | **0.00** | **0.00** | 0 | 0 | 1 | 1 | 0 |
| OBJECTION | **0.00** | **0.00** | 0 | 0 | 2 | 2 | 0 |

The classifier predicted nothing. Every reply in the sample stayed UNKNOWN.

### Hand-label breakdown

| Label | Count |
|-------|-------|
| interested | 15 |
| meeting_intent | 1 |
| objection | 2 |
| none | 182 |
| **Total** | **200** |

### What I labelled as INTERESTED (15 replies)

These are genuine interest signals the NEW patterns do not reach:

1. **#6** "How is this different than a claude agent" — product question
2. **#37** "Da, top Pošaljite" — Slovenian: "Yes, great. Send it." — requesting materials
3. **#42** "thank you for the material. Over the next few days, I will take some time to review it carefully and get back to you with feedback" — will review material
4. **#45** "Sunset mi je svakako na wishlisti" — Croatian: "Sunset is on my wishlist"
5. **#77** "I'd be happy to take a look at a short overview to learn more about the format, audience, and key topics" — explicitly asking for overview
6. **#89** "Yes, why not? Let explain me what you do and what is Sunset Sport Festival" — asking for explanation
7. **#101** "can you give me in 2 sentences what you have to offer?" — asking for pitch
8. **#106** "Do you organize events in Spain?" — product question
9. **#107** "would be interesting to hear about Productive sometime in the future" — interest signal (deferred)
10. **#136** "Sure. I will put in my work id and we can then chat. Please send me an invite" — requesting invite, providing email
11. **#137** "just drop me a link, I'll check it out" — requesting link
12. **#152** "are you referring personal finances, or organizational? and do you mind elaborating more on what you do please?" — asking for elaboration
13. **#182** "Could I know better about your project?" — asking about project
14. **#186** "Do you have any in-house expertise with meta ads to go with the tool? If yes we can talk." — conditional interest
15. **#196** "I've moved to Toronto... If not, then by all means, happy to reconnect." — conditional interest

### What I labelled as MEETING_INTENT (1 reply)

- **#61** "Let's talk in January?" — concrete meeting proposal with named constraint (locked into current tool until May, renewal in May, need 3-4 months to migrate)

Note: this reply is caught by production rules as POSITIVE (because "Let's talk" matches a POSITIVE pattern), so the taxonomy never runs. The taxonomy cannot label it MEETING_INTENT because production rules get there first.

### What I labelled as OBJECTION (2 replies)

- **#28** "currently we are not authorized by our headquarters to invest in new tools" — organizational constraint
- **#180** "we are restricted by Marriott as to programs used" — organizational constraint

Neither matches the OBJECTION patterns, which look for "too expensive", "no budget", "don't have time", etc. "Not authorized" and "restricted by" are outside the pattern set.

## Comparison with the old measurement

| | OLD (n=263) | NEW (n=200) |
|--|-------------|-------------|
| INTERESTED precision | 0.44 | 0.00 |
| INTERESTED recall | 0.62 | 0.00 |
| MEETING_INTENT precision | 1.00 | 0.00 |
| MEETING_INTENT recall | 1.00 | 0.00 |
| OBJECTION precision | 1.00 | 0.00 |
| OBJECTION recall | 0.67 | 0.00 |
| Taxonomy coverage (full pool) | 63 of 3,869 (1.6%) | 20 of 3,893 (0.5%) |

The old set was wrong more than half the time but at least it tried. The new
set is so narrow that it catches almost nothing. Precision is undefined when
nothing is predicted; recall is zero because nothing is predicted.

## What the patterns look like

The current INTERESTED_PATTERNS in `src/replies.py`:

```python
INTERESTED_PATTERNS = (
    r"\bi (?:find|found|am) (?:this|it|that) (?:interesting|intriguing|curious)\b",
    r"\b(?:that|this|it)(?:'?s| is) (?:interesting|intriguing|curious)\b",
    r"\b(?:i'?m|i am) curious about\b",
    r"\bcurious to (?:learn|know|hear|see)\b",
    r"\bi(?:'d| would) like to know more\b",
    r"\btell me (?:about|something|everything|why)\b",
    r"\bgo on\b",
    r"\bshow me\b",
)
```

These are extremely narrow. They require specific phrasings like "I find this
interesting", "that's intriguing", "I'm curious about", "curious to learn",
"I'd like to know more", "tell me about", "go on", "show me".

The 15 replies I labelled as interested use many different phrasings:
- Product questions ("How is this different...", "Do you organize events...")
- Requests for materials ("Send it", "drop me a link", "send me an invite")
- Requests for explanation ("Let explain me what you do", "can you give me 2 sentences")
- Conditional interest ("If yes we can talk", "happy to reconnect if...")
- Expressions of willingness ("I'd be happy to take a look", "on my wishlist")

None of these match the patterns. The patterns were designed to be safe by
requiring the sender to ASK FOR SOMETHING, but the phrasings they match are
so specific that they miss the vast majority of genuine interest signals.

## Recommendation

**The learning-claim restriction should NOT be lifted.** The new pattern set
does not measure well because it does not measure at all. It has zero recall
on a fresh sample — it predicts nothing.

This is not a precision problem (the old set had that). This is a coverage
problem. The patterns are so narrow that they are effectively inert.

### What this means

INTERESTED as a taxonomy category cannot be reliably detected with the
current regex pattern set. The bare adjectives were removed because they
were wrong more than half the time, and what remains is so narrow it catches
almost nothing.

The options are:

1. **Accept that INTERESTED is not detectable with regex.** The category
   stays as UNKNOWN, and every analysis that wants a positive set keeps
   using MEETING_INTENT (which measured 1.00 precision in the old sample,
   though it also measured 0 recall in this one because production rules
   catch the one meeting-intent reply first).

2. **Broaden the patterns carefully.** Add patterns for common interest
   phrasings ("send me a link", "drop me a link", "what do you have",
   "can you elaborate", "happy to take a look") with negation guards. This
   would raise recall but also risks raising precision back toward the old
   0.44 if the guards are not tight enough.

3. **Use a model for INTERESTED.** The deterministic rules are good at
   clear cases (unsubscribe, out-of-office, negative) but bad at nuance.
   A model could distinguish "sounds interesting, but..." (refusal) from
   "sounds interesting, send me more" (interest) in a way regex cannot.
   This is the approach TASK-067 gestured at but did not implement.

Option 1 is the safe default. Option 2 is the one the task forbids ("Do not
widen patterns to raise recall"). Option 3 is a separate decision that
requires its own evidence.

### What I would NOT do

- **Do not put the bare adjectives back.** The 29 false positives in the old
  measurement are listed in `docs/TAXONOMY-PRECISION-2026-09-14.md`. The word
  "interesting" is a politeness marker, not an interest signal. Putting the
  pattern back would restore the 0.44 precision.

- **Do not call this "precision 1.00" because nothing was predicted.** Zero
  predictions is not perfect precision. It is zero coverage. Reporting it as
  "precision 1.00" would be misleading in the direction the repository has
  already been bitten by — claiming a measurement that does not exist.

- **Do not lift the learning-claim restriction.** The restriction exists
  because INTERESTED was measured at 0.44 precision. The new set does not
  improve that; it abandons the attempt. The restriction should stay until
  a pattern set or model measures well on a fresh sample.

## Row counts

| | Count |
|--|-------|
| Total cached conversations | 26,174 |
| Total CORRESPONDENT messages | 5,864 |
| Production-rule UNKNOWN with text | 3,893 |
| Taxonomy fires on (full pool) | 20 (0.5%) |
| Sample size | 200 |
| Hand-labelled as interested | 15 |
| Hand-labelled as meeting_intent | 1 |
| Hand-labelled as objection | 2 |
| Hand-labelled as none | 182 |
| Taxonomy fires on (sample) | 0 |

## Scripts

- `scripts/task109_collect_unknowns.py` — draws the sample from the cache
- `scripts/task109_score.py` — runs the classifier and computes metrics
- `scripts/task109_labels.json` — hand-labels for the 200-reply sample

## Files changed

- `docs/INTERESTED-REMEASURE-2026-09-15.md` — this report
- `scripts/task109_collect_unknowns.py` — sample collection script
- `scripts/task109_score.py` — scoring script
- `scripts/task109_labels.json` — hand-labels
