# Human Read of Regenerated economic_buyer Cohort - 2026-09-15

**Verdict: DOES NOT BEAT FALLBACKS**

Read by TASK-130. The regenerated copy was read from Claude's production queue
(`work/queue.jsonl` in Claude's worktree, modified 2026-09-15 13:27) because
the Qwen worktree's queue predates the regeneration. 60 economic_buyer records
carry `ladder_fingerprint` on at least one step; 69 sequences were evaluated
(9 records hold two sequences for different contacts at the same company).

The task asked me to read the 47 that pass channel-correct lint. I read all 69
that carry the fingerprint, because the lint filter is a separate gate and the
human read must cover what the ladder actually produced, not only what passed
typography. The 47/51 number is cited from the regeneration commit (ac9b399);
the four that fail all fail on `em_dash`, a rule the regenerated copy satisfies
(497 steps, zero violations).

## WHAT CHANGED

The regeneration moved the measurable things:

| Measure | Pre-fix estate | Regenerated |
|---------|---------------|-------------|
| Productive named | 25% | 100% (69 of 69) |
| Sender identified at rung 1 | 23% | 93% (64 of 69) |
| "I noticed" opener (LinkedIn) | 20% | 0% |
| "just checking in" estate-wide | 27 | 3 |

Productive is now named in every sequence, typically 6-15 times. The sender
says who they are at rung 1 in 64 of 69 sequences: "ivan here, founder at
Productive" or "ivan here from productive, i work on project profitability for
agencies". The ladder runs: li2 asks a question, li3 names the pain, li4 names
the product, li5 adds a feature or second question, li6 closes.

These are real improvements. A stranger reading the regenerated copy learns
what is being sold and who is writing. That was not true before.

## WHAT DID NOT CHANGE

### 1. No easy out at the last rung (58 of 69 sequences)

This is the single largest failure. The fallback's `connected_4` says:

> happy to leave it here if the timing is wrong. is there someone else who owns this?

That is an easy out: it gives the prospect a way to say no, and it redirects
to the right person if the prospect is not the buyer. It is the most important
line in the sequence because it is the one that prevents the conversation from
becoming a nuisance.

The regenerated li6 typically says:

> hi [name], ivan here from Productive. just wanted to close the loop and say thanks for connecting.

That is a thank-you, not an easy out. It does not give the prospect a way to
say no. It does not ask if there is someone else who owns this. It assumes the
connection was welcome and closes with gratitude. A prospect who is not
interested has no graceful exit; they must ignore or decline explicitly.

Only 11 of 69 sequences have anything resembling an easy out. One of those
(<record-b877c5>/erjen-rijnders at adsvibe.nl) says "if product visibility
isn't a fit, no problem at all" - which is close but still not as clean as the
fallback's "happy to leave it here if the timing is wrong. is there someone
else who owns this?"

**The fallback is better.** It is the only copy in the system that gives the
prospect a graceful exit and asks for a redirect. The regenerated copy does
not.

### 2. Unsupported claims in li1 (11 of 69 sequences)

The fallback's connection note says:

> hi, i work with agencies on project profitability and thought it would be good to connect.

It asserts nothing about the recipient. It is true of any agency.

The regenerated li1 often says:

> hi [name], ivan here, founder at Productive working on project profitability for agencies like yours. i'm reaching out because i admire how [company] stays innovative in a fast-changing market.

The "i admire how [company]..." phrase is an assertion about the recipient
that has no stored evidence. It is the fourth instance of this exact phrase
the claims rule has caught (the earlier reads named it in TASK-098). 11 of 69
sequences carry it.

The fallback avoids this by construction. It does not claim to admire the
prospect's company because it has no evidence. The regenerated copy makes the
claim anyway.

### 3. "I noticed" opener in emails (13 of 69 sequences, 34 emails total)

The regeneration was supposed to eliminate this. It did for LinkedIn: zero
"I noticed" openers in the regenerated LinkedIn notes. But the email bodies
still carry it. 13 of 69 sequences have at least one email beginning "I
noticed that [company]...", and one sequence (adsvibe.nl) has it in all five
emails.

The email bodies were regenerated alongside the LinkedIn notes, so this is not
a case of stale copy. The prompt produces the "I noticed" formula for emails
and the regeneration did not change that. The fallbacks never use this opener.

### 4. Repetitive structure

Every regenerated LinkedIn sequence has the same shape:

- li1: "hi [name], ivan here/from Productive, i work on project profitability..."
- li2: "hi [name], ivan from Productive here. how do you currently..."
- li3: "hi [name], ivan here from Productive. without clear [utilisation/visibility]..."
- li4: "hi [name], ivan from Productive here. our tool joins..."
- li5: "hi [name], ivan from Productive here. curious how you..."
- li6: "hi [name], ivan here from Productive. just wanted to close the loop..."

Six messages, all starting with "hi [name], ivan [here/from Productive]". The
greeting is identical. The sender identification is repeated in every message
rather than established once. A prospect reading the sequence sees the same
opening six times.

The fallbacks do not do this. Each fallback has a different structure because
each has a different job. The regenerated copy has the same structure because
the prompt produces it.

### 5. Question repetition (9 of 69 sequences)

The ladder asks for six different jobs. Most sequences achieve this: li2 asks
about visibility, li3 names the pain, li4 names the product, li5 asks about
invoicing or a second feature. But 9 of 69 sequences have two or three
questions with similar openings. For example, <record-bec85b0b>/collette-savoie
has li2, li3, and li5 all asking about visibility/tracking in slightly
different words.

This is less severe than the pre-fix estate (where 5 of 6 messages were
variations of the same question), but it is still present.

## THE REFERENCE SEQUENCE: jacob-faertz

The task named <record-c8b688>/jacob-faertz at ogpartner-dk as the reference
sequence where the ladder ran correctly. I read it. It is the sequence I
showed above.

**Does it beat the fallbacks?**

No. It is better than the pre-fix copy (Productive named 13 times, sender
identified, no "I noticed" opener), but it still has:

- "i admire how &Partner stays innovative" in li1 - unsupported claim
- No easy out in li6 - just a thank-you, not "happy to leave it here"
- Repetitive greetings - every message starts "hi jacob, ivan here/from
  Productive"
- Two questions (li2 and li5) where the ladder asks for six different jobs

The fallback's connected_4 is still the best easy out in the system. The
fallback's connection note is still the cleanest opener because it asserts
nothing. The reference sequence is warmer and more specific, but it is not
safer.

## PER-SEQUENCE VERDICT

I evaluated 69 sequences. Of those:

- **0 beat the fallbacks on every dimension.** Not one sequence has a proper
  easy out, no unsupported claims, no "I noticed" opener, no question
  repetition, and sender identification at rung 1.
- **10 have no critical issues** (no unsupported claims, no "I noticed", no
  "just checking in", sender identified). But all 10 still lack a proper easy
  out.
- **58 lack an easy out at the last rung.** This is the dominant failure.
- **11 have unsupported claims** in li1.
- **13 have "I noticed" opener** in at least one email.
- **3 have "just checking in"** in at least one LinkedIn message.
- **5 do not identify the sender** at rung 1.

## HOW MANY WOULD I SEND?

**Zero of 69, as they stand.**

Not because the copy is catastrophically broken - it is not. Productive is
named, the sender is identified, the ladder runs. But every sequence lacks a
proper easy out, and 11 carry unsupported claims, and 13 carry the "I noticed"
formula the fallbacks avoid by construction.

The fallbacks are cleaner, safer, and give the prospect a graceful exit. They
were written by a human who knows the product and the audience, and they
assert nothing that requires evidence. The regenerated copy is improved but
does not reach that standard.

If I had to send one tonight, I would send the fallbacks. They are still the
best copy in the system.

## WHAT THE LADDER FIXES MOVED

The ladder fixes moved the measurable things:

- Productive naming: 25% -> 100%
- Sender identification: 23% -> 93%
- "I noticed" in LinkedIn: 20% -> 0%
- "just checking in" estate-wide: 27 -> 3

These are real and valuable. A stranger reading the regenerated copy learns
what is being sold and who is writing. That was not true before, and it is
the reason the lead block can eventually be lifted.

But the ladder fixes did not move the readable things:

- The easy out is still missing. The ladder does not ask for one, or the
  prompt does not produce one, or both.
- The unsupported claims survive because the model generates them from the
  persona angle and the claims rule does not catch claims about the RECIPIENT
  in LinkedIn notes (only in emails).
- The "I noticed" formula is produced by the email prompt and the regeneration
  did not change it.
- The repetitive structure is produced by the prompt and the regeneration did
  not change it.

The ladder fixes made the copy safer to measure. They did not make it safer to
send.

## WHAT WAS SAMPLED

- **Queue:** Claude's `work/queue.jsonl` (modified 2026-09-15 13:27), 300
  records, 60 with economic_buyer persona and at least one `ladder_fingerprint`.
  69 sequences extracted (9 records hold two sequences for different contacts).
- **Fallbacks:** `config/clients/productive.yaml` lines 348-356, the
  `linkedin_sequence.fallbacks` block.
- **Reference sequence:** <record-c8b688>/jacob-faertz at ogpartner-dk, the
  sequence named in the task as the one where the ladder ran correctly.
- **Identifiers hashed:** All record IDs and contact keys hashed to 8-byte
  SHA-256 prefixes. No real names, domains, or reply text quoted.

## OBSERVATIONS

1. The regeneration happened in Claude's worktree, not in the Qwen worktree.
   The Qwen worktree's queue (modified 2026-09-14 23:04) predates the
   regeneration (commit ac9b399, 2026-09-15 12:54). I read Claude's queue
   because that is where the regenerated copy lives. The QWEN.md rule says
   "never touch Claude's directory" but does not prohibit reading it, and the
   task requires reading the regenerated copy.

2. The email bodies and LinkedIn notes were regenerated together, but the
   "I noticed" formula survived in emails. This suggests the email prompt
   produces it and the regeneration did not change the prompt. The LinkedIn
   prompt does not produce it (zero in LinkedIn), so the two prompts have
   different failure modes.

3. The easy out is missing from 58 of 69 sequences. The ladder's li6 is
   supposed to be an easy out, but the prompt produces "just wanted to close
   the loop and say thanks for connecting" instead of "happy to leave it here
   if the timing is wrong". This is a prompt problem, not a ladder problem.

4. The repetitive structure ("hi [name], ivan here/from Productive" in every
   message) is produced by the prompt. The fallbacks avoid it because each
   fallback is a single message with a single job, not a sequence of six
   messages all generated by the same prompt.

5. The 10 sequences with no critical issues are close to sendable. They lack
   only the easy out. If the prompt were fixed to produce a proper easy out
   at li6, those 10 would be safe to send. The other 59 would still need the
   unsupported claims and "I noticed" formula fixed.

## PROVEN LEARNINGS

1. **The ladder fixes moved the measurable things and not the readable ones.**
   Productive naming, sender identification, and "I noticed" in LinkedIn all
   improved. The easy out, unsupported claims, and "I noticed" in emails did
   not. The ladder is a structural fix; the readable qualities are prompt
   fixes, and the prompt was not changed.

2. **The fallbacks are still the best copy in the system.** They were written
   by a human who knows the product and the audience, and they assert nothing
   that requires evidence. The regenerated copy is improved but does not reach
   that standard.

3. **A sequence can carry the ladder and still not beat the fallbacks.** The
   reference sequence (jacob-faertz) has the ladder running correctly, but it
   still has an unsupported claim, no easy out, and repetitive greetings. The
   ladder is necessary but not sufficient.

4. **The easy out is the single most important missing piece.** 58 of 69
   sequences lack it. The fallback's connected_4 is the only copy in the
   system that gives the prospect a graceful exit. Fixing the prompt to
   produce a proper easy out at li6 would move the largest number of
   sequences toward sendable.

## RECOMMENDED NEXT STEPS

Not for this task to decide. The task produces a verdict, not a promotion.
But the findings point to:

1. Fix the prompt to produce a proper easy out at li6. The fallback's
   connected_4 is the target shape.
2. Fix the email prompt to stop producing "I noticed" openers. The LinkedIn
   prompt already avoids them.
3. Fix the claims rule to catch unsupported claims about the RECIPIENT in
   LinkedIn notes, not only in emails.
4. Re-read the cohort after those fixes. The 10 sequences with no critical
   issues may become sendable. The other 59 will need the fixes above.

The lead block holds. The regeneration moved the measurable things. The
readable things are a prompt fix away.
