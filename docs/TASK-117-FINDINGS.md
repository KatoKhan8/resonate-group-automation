# TASK-117 Findings: sender-identity claims the rule cannot see

## THE FACT

The claims rule has been extended four times, each time by one phrase, each
time after a phrase escaped. The pattern is not the individual phrases - it
is the CLASS they belong to.

## WHAT CLASS OF CLAIM IS ESCAPING

**Sender-identity assertions that imply shared category with the recipient.**

"As a fellow founder" asserts the sender is a founder AND implies the
recipient is one too. The rule caught "as a fellow X" but not the 21 other
ways to express the same thing.

### The probe: 28 candidates, 7 caught, 21 pass

Tested against the real `claims.implies_prior_contact` and `claims.check`
on a bare record (no prior contact, no supporting evidence).

**Currently caught (7 of 28):**

| Phrase | Pattern that catches it |
|--------|----------------------|
| as a fellow founder | `\bas\s+a\s+fellow\s+\w+\b` |
| as a fellow operator | same |
| as a fellow bootstrapper | same |
| as someone who runs | `\bas\s+someone\s+who\s+(?:also\s+)?(?:runs?\|owns?\|...)` |
| as someone who founded | same |
| speaking as a fellow founder | `\bspeaking\s+as\s+a\s+fellow\s+\w+\b` |
| speaking as someone who built | pattern 2 |

**Currently passing (21 of 28):**

| Shape | Example | Why it escapes |
|-------|---------|---------------|
| "as a X" without "fellow" | as a founder myself | No "fellow", no "someone who" |
| "as an X" | as an agency owner | Same |
| Participial experience | having run a team your size | No pattern matches |
| "I am also a X" | i am also a founder | No pattern matches |
| "I am a fellow X" | i am a fellow founder | "am" not "as" or "speaking as" |
| Present perfect experience | i have built two agencies | No pattern matches |
| "Like you, I..." | like you i am a founder | No pattern matches |
| "I know what it's like" | i know what it is like to run an agency | No pattern matches |
| Possessive identity | my agency has 20 people | No pattern matches |
| Group identity | we are founders too | Starts with "we", exits via GENERIC_SUBJECTS |

### The shapes fall into two categories

**Catchable with patterns (7 more, zero false refusals):**
- "having [identity verb]" - having run, having built, having scaled
- "also a/an" - i am also a founder
- "like you ... I" - like you i am a founder
- "[role] too" - i am an agency owner too

**Structurally hard to catch without false refusals (14 remaining):**
- "as a X" without "fellow" - catches "as a founder" but also "as a result"
- "I know what it's like" - indistinguishable from "i know you handle X"
- "I have VERBed" - indistinguishable from "i have a question for you"
- "my [noun]" - indistinguishable from "my last message"
- "we are X too" - the "we" exit in `is_claim` prevents any "we" sentence
  from being classified as a claim

## CAN THE CLASS BE CAUGHT WITHOUT MORE PHRASES?

**No, not with the current architecture.** The claims rule decides whether
a sentence is a claim by its SYNTAX (numbers, event words, second-person
assertions, relationship patterns). Sender-identity assertions are a
SEMANTIC class - they can be expressed in any syntactic form.

The three safe patterns above catch 7 more phrases (14 -> 8 caught, 33%
of the escaping set). But 14 remain, and catching them requires either:

1. **A broader pattern with false refusals.** `\bas\s+(?:a|an)\s+\w+`
   catches "as a founder" but also refuses "as a result", "as a reminder",
   "as a short note", and "as a follow up" - four legitimate phrases.

2. **A config check against sender identity.** Instead of pattern-matching
   the text, check whether the sender config SUPPORTS the identity being
   asserted. "As a fellow founder" is fine if `sender.role == "founder"`.
   This is a different kind of rule - it validates against config, not
   against syntax.

3. **A prompt-level constraint.** Tell the model to use ONLY the identity
   stated in `sender_identity`, never to infer roles or experiences. The
   prompt already says "NEVER invent a sender name, title or company" but
   the model extends this to "as a fellow X" and the claims rule does not
   catch it.

## WHAT WOULD A BROADER RULE FALSELY REFUSE?

Tested 22 legitimate sender-identity phrases against the proposed patterns.

**Zero false refusals** from the safe patterns (having/also/like-you/too).

**Four false refusals** from the `as a/an` pattern:
- "as a result we improved visibility across the board"
- "as a reminder the deadline is Friday"
- "as a short note i wanted to mention the feature"
- "as a follow up to our conversation here is the deck"

The last one is already caught by the existing `\bfollow(?:ing)?[- ]?up`
relationship pattern, so the `as a/an` pattern adds three new false
refusals.

**The "we" exit problem.** Any rule that catches "we are founders too"
must first get past `is_claim`'s `GENERIC_SUBJECTS` exit, which waves
through anything starting with "we", "our", "i", etc. A rule that
overrides this exit for sender-identity patterns would also catch "we
help agencies connect project delivery to finance" - the exact copy
TASK-075 requires.

## THE TENSION

The sequence must say who is writing (TASK-075, ladder rung 1).
The claims rule must not let the sender claim what they are not.

These two requirements are in tension because:
- The ladder prompt says "say who you are"
- The sender config provides the facts (name, role, company, works_on)
- The model must express the sender's identity WITHOUT asserting shared
  category with the recipient

The line is: **the sender may state their own identity from the config,
but may not assert that the recipient shares it.**

"I am Ivan, founder of Productive" - states identity from config. SAFE.
"As a fellow founder" - asserts shared category. UNSAFE.
"I work with agencies on resourcing" - states what the sender does. SAFE.
"Having run a team your size" - asserts experience AND implies shared
category. UNSAFE.

## PROVEN LEARNINGS

1. The claims rule catches 7 of 28 sender-identity phrases (25%).
2. Four safe patterns catch 7 more (total 14 of 28, 50%) with zero
   false refusals.
3. The remaining 14 cannot be caught by phrase patterns without false
   refusals, because they use syntactic forms indistinguishable from
   legitimate copy.
4. The real fix is not a fifth phrase but a different kind of rule:
   one that checks sender-identity assertions against the sender config
   rather than pattern-matching the text.
5. The prompt already says "NEVER invent a sender name, title or company"
   but the model extends beyond the literal words. The prompt may need
   to be more specific about what "invent" means - including "as a
   fellow X", "having run a team", and "like you, I am a X".

## RECOMMENDED CLAUDE ACTION

1. Add the four safe patterns to the RELATIONSHIP tuple in claims.py.
2. Update the linkedin_note.md prompt to explicitly forbid shared-category
   assertions ("as a fellow X", "having run a team your size", "like you,
   I am a founder").
3. Consider a config-level check: when a sentence contains a role word
   (founder, CEO, owner, operator) and a shared-identity marker (fellow,
   also, too, like you), check whether the sender config supports it.
4. TASK-075 tests must not break. Run them.
