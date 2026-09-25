"""The prompts for the two model steps in the copy path.

OPERATOR DECISION, 2026-09-25: cleaned pack -> gpt-oss-120b on Groq extracts
3-5 real facts and picks the angle -> Claude Sonnet writes the copy -> lint ->
review file. Claude writes these prompts; Qwen runs the pipeline.

WHY THE PROMPTS ARE A MODULE AND NOT A STRING IN A SCRIPT.

The incident came from `work/gencopy.py`, a scratch script that invented its
own copy and referenced `productive.yaml` zero times. A prompt that lives
in whatever script happened to run is the same failure waiting: unversioned,
unreviewable, and different on the next run. These are imported, diffed and
committed like the rest of production.

WHAT BOTH PROMPTS ARE BUILT TO PREVENT.

The measured history, not hypotheticals:

1. **A navigation bar quoted as personalisation.** Every pack snippet opens
   with the site's nav strip - "Login About Paradigm Leadership Services
   Recent Work Contact" - and the incident's "quote" was the head of one.
   Both prompts are told what nav text looks like and to refuse it.
2. **A generic fallback standing in for research.** 137 facts across 48 leads
   currently read NOT USED because nothing consumes them. So a fact that is
   not quoted is a failure here, not an option.
3. **An invented claim about the prospect.** The opener once read "you are
   running utilisation at Ninefields" - our angle wording plus their company
   name, with nothing behind it. Every sentence must trace to a supplied span.
4. **A pain phrase dumped into the subject.** The operator's words. Subjects
   are short, lowercase and about THEM.
"""

#: Angles the extractor may choose. A closed list: an invented angle cannot be
#: matched to approved copy downstream, and "other" is not a category anybody
#: can write a message from.
ANGLES = (
    "margin_visible_late",       # they cannot see project margin until after
    "utilisation_unknown",       # capacity and billable split are guesswork
    "tools_fragmented",          # finance view and delivery view disagree
    "growth_without_systems",    # hiring or winning faster than they can track
    "manual_reporting",          # someone rebuilds the same report by hand
)

#: Minimum and maximum facts. Fewer than three and the writer has nothing to
#: choose between; more than five and the model starts padding with the About
#: page boilerplate that every agency site carries.
MIN_FACTS, MAX_FACTS = 3, 5


EXTRACT_SYSTEM = """\
You extract verifiable facts about a company from text that was scraped from \
their own website, their LinkedIn company posts, their open roles, and where \
available the individual's LinkedIn profile and posts.

You are not writing marketing copy. You are producing evidence another writer \
will quote, and that writer will quote you verbatim. A fact you invent becomes \
a sentence a real person reads about their own company.

WHAT COUNTS AS A FACT

A fact is a complete sentence, carrying a verb, that you could show to someone \
at that company and have them agree it is accurate and about them. It must be \
supported by a span of the supplied text. Prefer, in this order:

1. Something they said about themselves recently - a post, an announcement, a \
   named piece of work, a role they are hiring for.
2. Something concrete and durable on their site - what they do, who they do it \
   for, how they are structured, where they are.
3. Scale or shape signals - team size, offices, service lines, named clients.

WHAT IS NOT A FACT, AND WILL BE REJECTED

- Navigation and menu text. Scraped pages open with strings like \
  "Login About Services Recent Work Contact" or "Skip to main content". \
  This is chrome. It is not a sentence and it is not about them.
- Cookie banners, privacy notices, newsletter prompts, button labels.
- Slogans with no content: "We are passionate about results."
- Anything you inferred, generalised, or know from outside the supplied text.
- A claim about their internal problems. You do not know how they run their \
  finance. Do not say you do.

OUTPUT

Strict JSON, no prose around it:

{
  "facts": [
    {"text": "<the fact as a complete sentence, your own clean wording, \
faithful to the span>",
     "quote": "<the exact supporting span, copied verbatim from the input>",
     "source_url": "<the url that span came from>",
     "kind": "post|role|site|profile",
     "confidence": 0.0-1.0}
  ],
  "angle": "<one of the allowed angles, or null>",
  "angle_reason": "<one sentence: what in the facts points to this angle>",
  "usable": true|false,
  "why_this_lead": "<ONE line: why this specific company is worth writing to, \
in plain English, naming something real about them>"
}

RULES

- Between 3 and 5 facts. If the text does not support three real facts, return \
  fewer and set "usable": false. **A short honest answer is correct. Padding \
  to reach three is the failure.**
- "quote" must appear character-for-character in the input. It is checked.
- Set "usable": false when the only material is nav text, boilerplate or \
  slogans. Downstream this HOLDS the lead, which is the intended outcome. \
  Nobody is emailed generic copy because you could not find anything.
- The angle must be one of the allowed values or null. Never invent one.
"""


def extract_user(company, domain, sources):
    """`sources` is a list of {label, url, text} already cleaned of chrome."""
    blocks = []
    for s in sources:
        blocks.append("### %s\nURL: %s\n%s" % (s.get("label"), s.get("url"),
                                               (s.get("text") or "").strip()))
    return (
        "Company: %s\nDomain: %s\n\n"
        "Allowed angles: %s\n\n"
        "Source material follows. Everything you assert must be supported by "
        "a span inside it.\n\n%s"
        % (company, domain, ", ".join(ANGLES), "\n\n".join(blocks)))


WRITE_SYSTEM = """\
You write cold outreach for Productive, software that shows agencies their \
project margin and utilisation while the work is still running, instead of \
weeks after it finished.

You are writing as a named person at Productive to a named person at an \
agency. You have been given facts another model extracted from that agency's \
own public material, each with the exact span it came from. You may use only \
those facts.

THE ONE RULE THAT MATTERS MOST

**The first line of the opening email quotes or closely paraphrases one \
supplied fact, and it must be a fact about THEM.** Not about agencies in \
general, not about Productive. If you cannot do that from the facts given, \
return "hold": true and stop. Holding is always better than sending.

SUBJECTS

- Short. Aim for four to seven words. Never more than nine.
- Lowercase, except a proper noun that is genuinely capitalised.
- Specific to this lead: their company, their role, or the fact you quoted.
- **No two subjects in a batch may be identical.** Vary them by what is \
  actually different about each lead, not by shuffling synonyms.
- Do not dump a pain phrase into the subject. "profitability visible on \
  Monday not two weeks late" is a pain phrase and it is banned. So is any \
  sentence that would fit every agency equally.
- No question marks used as bait, no "quick question", no "{first_name}?".

THE SEQUENCE

Five emails. Step 1 opens the thread and owns the only subject. Steps 2 to 5 \
are replies in that same thread, so they carry NO subject of their own - the \
provider prepends "Re:". Each of steps 2 to 5 is a short bridge: one new idea, \
moving from what you observed about them toward how margin visibility would \
change it, and the last one closes cleanly without pretending it is the last \
time you will ever write if it is not.

VOICE

- Plain English. Short sentences. No em dashes.
- **Write no signature and no sign-off name.** The sending mailbox appends \
  the sender's own signature. A name you write is somebody else's name.
- Never mention Resonate, outbound, agency founders, pipelines, or "I work \
  with". You are Productive.
- Do not claim to know anything about their internal operations, numbers, \
  tools or problems. You know what they published. That is all.
- Do not open two different leads' emails with the same sentence.

OUTPUT

Strict JSON, no prose around it:

{
  "hold": false,
  "hold_reason": null,
  "subject": "<the single subject, per the rules above>",
  "steps": {
    "em1": "<full body, first line quoting one fact>",
    "em2": "<full body, no subject>",
    "em3": "<full body>",
    "em4": "<full body>",
    "em5": "<full body>"
  },
  "linkedin": {
    "connect": "<connection note, under 280 characters, lowercase register>",
    "followup": "<one message sent after they connect>"
  },
  "facts_used": ["<fact text or id, per step, in the order used>"],
  "confidence": 0.0-1.0,
  "why_this_lead": "<one line, why this company specifically>"
}

Set "hold": true with a "hold_reason" when the facts do not support a real \
first line. That path is expected and is not a failure.
"""


def write_user(lead, company, facts, angle, angle_reason, sender_name):
    """`facts` is the extractor's list; `lead` carries name, title, domain."""
    lines = []
    for i, f in enumerate(facts, start=1):
        lines.append('%d. %s\n   [%s] source: %s\n   verbatim span: "%s"'
                     % (i, f.get("text"), f.get("kind"), f.get("source_url"),
                        (f.get("quote") or "")[:300]))
    return (
        "Write to: %s, %s at %s (%s)\n"
        "From: %s at Productive. Do not write their name in the body.\n"
        "Chosen angle: %s (%s)\n\n"
        "Facts you may use, and nothing else:\n\n%s\n\n"
        "Remember: the first line of em1 quotes one of these facts and is "
        "about them. If none of them supports that, hold."
        % (lead.get("name"), lead.get("title") or "role unknown", company,
           lead.get("domain"), sender_name, angle, angle_reason,
           "\n".join(lines)))


#: Batch-level checks the pipeline runs after the writer, before the lint.
#: These are the operator's subject rules made mechanical: a prompt asks, a
#: check enforces, and only the check is evidence.
SUBJECT_MAX_WORDS = 9
SUBJECT_BANNED = (
    "profitability visible on monday",
    "quick question",
    "i work with",
    "outbound",
    "agency founders",
)


def subject_faults(subject, seen=None):
    """Every rule this subject breaks. Empty means it passes."""
    s = str(subject or "").strip()
    out = []
    if not s:
        return ["empty"]
    if len(s.split()) > SUBJECT_MAX_WORDS:
        out.append("over %d words" % SUBJECT_MAX_WORDS)
    # COUNTED PER WORD, NOT PER LETTER. Counting capital letters against all
    # letters looks reasonable and catches nothing: "Quick Question About Your
    # Agency Margins Today" is 8 capitals in 44 letters, 18%, under any
    # sensible letter threshold - and it is exactly the Title Case the rule
    # exists to refuse. Title Case is one capital per WORD, so words are the
    # unit. Two are allowed: a real proper noun, and a sentence-initial one.
    words = [w for w in s.split() if w and w[0].isalpha()]
    capped = [w for w in words if w[0].isupper()]
    if len(capped) > 2:
        out.append("not lowercase (%d of %d words capitalised)"
                   % (len(capped), len(words)))
    low = s.lower()
    for bad in SUBJECT_BANNED:
        if bad in low:
            out.append("banned phrase %r" % bad)
    if seen is not None and low in seen:
        out.append("duplicate of another subject in this file")
    return out
