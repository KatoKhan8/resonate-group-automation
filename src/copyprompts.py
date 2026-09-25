"""The prompts for the model steps, shaped for what the copy costs.

OPERATOR DECISIONS, 2026-09-25.

Path: cleaned pack -> gpt-oss-120b on Groq extracts 3-5 facts and picks the
angle -> Claude Sonnet writes ONLY what the prospect reads -> lint -> review
file. Claude writes these prompts; Qwen runs the pipeline.

Cost: under 0.3 cents per lead at scale, without lowering what the prospect
reads. Batch API, prompt caching on the cohort system prompt, one call per
lead for every step, input under 1,500 tokens and output under 400.

WHY THE PROMPTS ARE A MODULE AND NOT A STRING IN A SCRIPT.

The incident came from `work/gencopy.py`, a scratch script that invented its
own copy and referenced `productive.yaml` zero times. A prompt that lives in
whatever script happened to run is unversioned, unreviewable, and different on
the next run.

WHY SONNET WRITES SPANS AND NOT BODIES — THE MEASUREMENT.

Measured on the 48 leads shipped on 2026-09-25:

    full bodies, all five steps + subject ....... median 663 tokens
    plus the two LinkedIn messages .............. ~783 tokens
    the operator's output cap ................... 400

Whole bodies do not fit and never will. But the body is mostly STANDING text -
the approved paragraphs from `productive.yaml`, identical for every lead:

    em1 personalised first line ................. median  36 tokens
    em1 standing paragraphs ..................... median 103 tokens

So Sonnet writes the subject, the first line, the four bridge sentences and
the two LinkedIn messages; the templates supply everything else; the pipeline
assembles. That budget is 315 tokens with 85 to spare, and **the prospect
reads exactly the same words either way.** Cheapness here comes from not
paying a frontier model to retype approved paragraphs, not from writing less.

THE CACHE BREAKPOINT IS `COHORT_SYSTEM`.

Everything a cohort shares - product, voice, rules, subject law, the standing
paragraphs - lives in `COHORT_SYSTEM`, sent once per batch and cached. The
per-lead turn from `lead_user` carries only what differs: the person, the
company, three to five fact sentences, the angle. Anything drifting from the
system prompt into the per-lead turn is paid for on every lead, so that is the
line to watch when editing.
"""
import hashlib
import json
import re

#: Angles the extractor may choose. A closed list: an invented angle cannot be
#: matched to approved copy downstream, and "other" is not something anybody
#: can write a message from.
ANGLES = (
    "margin_visible_late",       # cannot see project margin until after
    "utilisation_unknown",       # capacity and billable split are guesswork
    "tools_fragmented",          # finance view and delivery view disagree
    "growth_without_systems",    # winning or hiring faster than they can track
    "manual_reporting",          # someone rebuilds the same report by hand
)

#: Fewer than three facts and the writer has nothing to choose between; more
#: than five and the model pads with the About-page boilerplate every agency
#: site carries.
MIN_FACTS, MAX_FACTS = 3, 5

#: The operator's budget, per lead, per call. Enforced by `budget_faults`
#: rather than hoped for: a cap nobody measures is a number in a document.
MAX_INPUT_TOKENS = 1500
MAX_OUTPUT_TOKENS = 400


# --------------------------------------------------------------------------
# STEP 1 - the cheap model. Cleaning, extraction, angle. Never the copy.
# --------------------------------------------------------------------------

EXTRACT_SYSTEM = """\
You extract verifiable facts about a company from text scraped from their own \
website, their LinkedIn company posts, their open roles, and where available \
the individual's LinkedIn profile and posts.

You are not writing marketing copy. You are producing evidence another writer \
will quote, and that writer will quote you verbatim. A fact you invent becomes \
a sentence a real person reads about their own company.

WHAT COUNTS AS A FACT

A complete sentence, carrying a verb, that you could show to someone at that \
company and have them agree it is accurate and about them. It must be \
supported by a span of the supplied text. Prefer, in order:

1. Something they said about themselves recently - a post, an announcement, a \
   named piece of work, a role they are hiring for.
2. Something concrete and durable on their site - what they do, who for, how \
   they are structured, where they are.
3. Scale or shape signals - team size, offices, service lines, named clients.

WHAT IS NOT A FACT, AND WILL BE REJECTED

- Navigation and menu text. Scraped pages open with strings like "Login About \
  Services Recent Work Contact" or "Skip to main content". That is chrome.
- Cookie banners, privacy notices, newsletter prompts, button labels.
- Slogans with no content: "We are passionate about results."
- Anything inferred, generalised, or known from outside the supplied text.
- A claim about their internal problems. You do not know how they run their \
  finance. Do not say you do.

OUTPUT - strict JSON, no prose around it:

{"facts":[{"text":"<the fact as one clean sentence, faithful to the span>",
           "quote":"<the exact span, copied verbatim from the input>",
           "source_index":<the NUMBER of the source block it came from>,
           "kind":"post|role|site|profile",
           "confidence":0.0-1.0}],
 "angle":"<one allowed angle, or null>",
 "angle_reason":"<one sentence: what in the facts points to this angle>",
 "company_hook":"<ONE sentence about the COMPANY that any contact there could \
receive. This is cached and reused for their colleagues.>",
 "usable":true|false,
 "why_this_lead":"<ONE line: why this company is worth writing to>"}

RULES

- Between 3 and 5 facts. If the text does not support three real facts, return \
  fewer and set "usable": false. **A short honest answer is correct. Padding \
  to reach three is the failure.**
- "quote" must appear character-for-character in the input. It is checked.
- **NEVER write a URL.** Give `source_index`, the number of the block the span
  came from. A model asked for a URL retypes it and gets it wrong: on
  2026-09-25 `boweryboost.com` came back as `bowiumboost.com` and would have
  been shown to the operator as the source of a quote. The caller holds the
  real URLs and looks them up by index.
- **NEVER COMPUTE A NUMBER FROM A DATE.** If the site says "over 25 years",
  say "over 25 years". Do not turn "since 2011" into "14 years" - the site's
  own phrasing is what they will recognise, arithmetic drifts the moment the
  year turns, and a number we derived is a claim we made.
- Set "usable": false when the only material is nav text, boilerplate or \
  slogans. Downstream this HOLDS the lead, which is intended. Nobody is sent \
  generic copy because you could not find anything.
- The angle must be one of the allowed values or null. Never invent one.
"""


def _numbered(sources):
    """Source blocks, numbered, WITHOUT their URLs.

    The URL is withheld deliberately. The model answers with `source_index`
    and the caller resolves the URL from this same list, so a retyped domain
    cannot reach a review file as provenance.
    """
    return ["### [%d] %s\n%s" % (i, s.get("label"), (s.get("text") or "").strip())
            for i, s in enumerate(sources, start=1)]


def extract_user(company, domain, sources):
    """`sources` is a list of {label, url, text}, already cleaned of chrome."""
    return ("Company: %s\nDomain: %s\n\nAllowed angles: %s\n\n"
            "Source material follows, numbered. Everything you assert must be "
            "supported by a span inside it, and `source_index` is the number "
            "of the block you took it from.\n\n%s"
            % (company, domain, ", ".join(ANGLES), "\n\n".join(_numbered(sources))))


def source_url_for(fact, sources):
    """The REAL url for a fact, from our own list. Never the model's.

    Measured 2026-09-25: asked to return a URL, the extractor answered
    `bowiumboost.com` for `boweryboost.com`. A source we cannot trust is worse
    than no source at all, because it is displayed as provenance.
    """
    try:
        i = int(fact.get("source_index"))
    except (TypeError, ValueError):
        return None
    return (sources[i - 1] or {}).get("url") if 1 <= i <= len(sources) else None


# --------------------------------------------------------------------------
# STEP 0 - qualification. Is this company even the thing the client sells to?
# --------------------------------------------------------------------------

ICP_SYSTEM = """\
You decide one thing: is this company a SERVICES AGENCY THAT RUNS CLIENT \
PROJECTS?

That means it sells its people's time on projects for clients, bills for that \
work, and has to know whether a project made money. A marketing agency, a \
design studio, a web or software consultancy, a PR or branding firm qualify.

These do NOT qualify, however much the website sounds like an agency:

- A SOFTWARE PRODUCT company, even one selling to agencies. It has a product, \
  not client projects.
- A DATA or LEAD-GENERATION platform selling access to a database.
- An AFFILIATE, creator or media network placing ads for commission.
- A staffing or recruitment business placing people into other companies.
- A freelancer or a one-person operation.
- A holding company, a directory, a marketplace.

Judge from what the text SAYS THEY DO, never from the industry label attached \
to them. "Marketing & Advertising" is attached to plenty of software products.

OUTPUT - strict JSON, no prose:

{"is_agency": true|false,
 "confidence": 0.0-1.0,
 "evidence": "<the phrase from the text that decided it, quoted verbatim>",
 "what_they_actually_are": "<if false: one short phrase>"}

**When the text does not let you tell, answer false with low confidence.** A \
held lead costs nothing. A software company receiving a message about its \
project margin has been told, in one sentence, that we did not read its site.
"""


def icp_user(company, domain, sources):
    return ("Company: %s\nDomain: %s\n\n%s"
            % (company, domain, "\n\n".join(_numbered(sources))))


# --------------------------------------------------------------------------
# STEP 2 - Sonnet. ONLY what the prospect reads, and only the parts that vary.
# --------------------------------------------------------------------------

#: The standing paragraphs, quoted into the system prompt so the model writes
#: spans that JOIN correctly. They are approved copy from productive.yaml and
#: the model must not reproduce or reword them - it writes into the gaps.
STANDING = """\
em1  <first_line>

     The pattern I see in teams the size of {company} is that the numbers
     arrive too late to act on. Utilisation and margin are known at the end of
     the month, which is after the month when something could have been done
     about them. The work itself is rarely the problem. The visibility into it
     is.

     Is that roughly how it works at {company} today, or have you already put
     something in place for it?

em2  <bridge>   then the approved comparable-proof paragraphs
em3  <bridge>   then the approved rung-3 paragraphs
em4  <bridge>   then the approved angle-shift paragraphs
em5  <bridge>   then the approved close
"""

COHORT_SYSTEM = """\
You write cold outreach for Productive, software that shows agencies their \
project margin and utilisation while the work is still running, instead of \
weeks after it finished.

You write as a named person at Productive to a named person at an agency.

WHAT YOU WRITE, AND WHAT YOU DO NOT

The emails are mostly approved standing copy that is already written. **You \
write only the parts that change per lead**: the subject, the first line of \
email 1, one bridge sentence opening each of emails 2 to 5, and the two \
LinkedIn messages. Everything else is supplied. Do not reproduce, reword or \
summarise the standing paragraphs - your spans are joined to them.

Here is the shape you are writing into:

%s

THE ONE RULE THAT MATTERS MOST

**The first line quotes or closely paraphrases one supplied fact, and it is \
about THEM.** Not agencies in general, not Productive.

**ANY REAL FACT ABOUT THEM QUALIFIES.** It does not have to be about margin, \
utilisation, finance or how they run projects - the standing paragraph that \
follows makes that turn. What they do, who they do it for, what they are \
hiring, what they have just shipped, how they describe their own work: all of \
these are a legitimate opening, because the point of the first line is to show \
we looked, not to prove the thesis before the message has started.

Hold ONLY when there is no real fact about this specific company at all - when \
the material is navigation text, slogans, or sentences that would be true of \
any agency. Holding is better than sending something generic; holding a lead \
we have three true, specific sentences about is not.

A bridge sentence carries the reader from what you observed about them into \
the standing paragraph that follows. One sentence. It must not restate the \
first line and the four must not restate each other.

SUBJECTS

- Four to seven words. Never more than nine.
- Lowercase, except a proper noun that is genuinely capitalised.
- Specific to this lead: their company, their role, or the fact you quoted.
- **No two subjects in a batch may be identical.**
- No pain phrase. "profitability visible on Monday not two weeks late" is a \
  pain phrase and is banned, as is any sentence that would fit every agency \
  equally.
- No question marks as bait, no "quick question".
- **A NOUN PHRASE ABOUT THEM, NOT A HEADLINE.** The subject names the thing;
  the first line explains it. "hiring three designers in brooklyn" reads as a
  headline about them and is wrong here; "your brooklyn design hires" is a
  noun phrase the first line then picks up. Avoid verbs that make it an
  announcement, and avoid anything that would sit comfortably on a blog post.

VOICE

- Plain English. Short sentences.
- **NO DASHES ANYWHERE. This is absolute and it covers every field you \
  return**: subjects, email bodies, both P.S. lines, and all four LinkedIn \
  messages. No em dash, no en dash, and no hyphen used as a separator \
  between clauses. Write two sentences, or use a comma, or a colon. \
  Measured 2026-09-25: the previous run put " - " in the connection note and \
  in the first follow-up, because the rule had been stated for email bodies \
  and the LinkedIn section had never been told. A hyphen INSIDE a word that \
  really is hyphenated, like "B2B" or "well-known", is fine.
- **Write no signature and no sign-off name.** The sending mailbox appends the \
  sender's own signature. A name you write is somebody else's name.
- Never mention Resonate, outbound, agency founders, pipelines, or "I work \
  with". You are Productive.
- Claim nothing about their internal operations, numbers or tools. You know \
  what they published.
- **NEVER COMPUTE A NUMBER FROM A DATE - in the subject or the body.** If the \
  fact says "since 2011", write "since 2011". Do not turn it into "a decade", \
  "over ten years" or "14 years". Measured 2026-09-25: the extractor obeyed \
  this and the writer, which had not been told, put "Huemor's decade of \
  website work" in a subject line. Their own phrasing is what they recognise; \
  arithmetic drifts the moment the year turns, and a number we derived is a \
  claim we made rather than one they published.

THE P.S.

**Emails 1 and 3 ALWAYS carry a P.S.** It is written from a DIFFERENT fact \
than the one the first line used - a second thing you noticed, not a \
restatement. One sentence, human, a question allowed. It is the line people \
read first and it should sound like a person added it, not like a second pitch.

You are told which P.S. VARIANT to write: `ps_fact` uses a second fact, \
`ps_capability` names one Productive capability in plain words. Those are the \
only two.

THE LINKEDIN CADENCE - IT MIRRORS THE EMAIL, IT IS NOT A LOWERCASE NOTE

Full sentences, proper capitalisation, the same voice as the emails. \
**`{firstName}` opens every message after the connect.** Each under 600 \
characters.

- `connect`: the connection request. Under 280 characters, lowercase \
  register, **no company name**, exactly one fact about them, no pitch. This \
  one stays as it is - a note naming their company reads like a mail merge.
- `msg1`, after they accept: "Hi {firstName}," then who you are - your name, \
  Productive, and ONE line on what Productive does - then why you are writing \
  **to them specifically**, using the same fact and the same angle as email 1. \
  End on one question.
- `msg2`: the capability in one line, then say plainly that you also sent a \
  note by email about this, so the two channels correlate rather than looking \
  like two strangers. One soft ask.
- `msg3`: breakup. Short, no pressure, leaves the door open.

THREE SUBJECTS, BECAUSE THERE ARE THREE THREADS

The cadence is not one thread. Operator decision, 2026-09-25:

    em1  day 1   NEW THREAD, subject A
    em2  day 4   reply in that thread          (the provider prepends Re:)
    em3  day 8   NEW THREAD, subject B, opening fresh
    em4  day 12  reply in THAT thread          (Re: B)
    em5  day 21  NEW THREAD, breakup, subject C - short, its own

So **both of your first two subjects are sent.** Neither is a spare. And em3
OPENS a thread: its bridge cannot assume the reader has the earlier one in
front of them, so it re-establishes who this is in its first clause without
repeating email 1 word for word. em5 likewise opens cold and is brief.

Return:

    subject    A - the opener
    subject_alt B - opens the second thread at day 8, a genuinely different
               noun phrase about them, not a reworded first
    subject_breakup C - short, three or four words, no hook, no question

OUTPUT - strict JSON, no prose around it:

{"hold":false,"hold_reason":null,
 "subject":"<the one you would send>",
 "subject_alt":"<a genuinely different second option>",
 "first_line":"<email 1 opening line, quoting one fact>",
 "bridges":{"em2":"<one sentence>","em3":"<one sentence>",
            "em4":"<one sentence>","em5":"<one sentence>"},
 "subject_breakup":"<short, three or four words, for em5>",
 "ps":{"em1":"<one sentence>","em3":"<one sentence>"},
 "ps_variant":"<the variant you were told to write>",
 "linkedin":{"connect":"<under 280 chars, lowercase, no company name>",
             "msg1":"<Hi {firstName}, who you are, why them, one question>",
             "msg2":"<the capability, the email cross-reference, one ask>",
             "msg3":"<breakup, short>"},
 "facts_used":["<the fact NUMBER used, per place, e.g. \\"first_line: 2\\">"],
 "confidence":0.0-1.0,
 "why_this_lead":"<one line>"}

Set "hold": true with a "hold_reason" when the facts do not support a real \
first line. That path is expected and is not a failure.
""" % STANDING


#: THE P.S. EXPERIMENT. Assigned per lead, deterministically, so the same
#: lead always gets the same arm and a rerun does not reshuffle the test.
#: Tagged on the row so replies can be compared later - an experiment whose
#: arm is not recorded is not an experiment, it is three versions of a thing.
PS_VARIANTS = ("ps_fact", "ps_capability", "ps_none")


def ps_variant_for(key):
    """Which P.S. arm this lead is in. Deterministic from its own key."""
    digest = hashlib.sha256(str(key or "").encode()).hexdigest()
    return PS_VARIANTS[int(digest[:8], 16) % len(PS_VARIANTS)]


def lead_user(lead, company, facts, angle, angle_reason, company_hook=None,
              ps_variant="ps_fact", capability=None):
    """The per-lead turn. Everything shared lives in COHORT_SYSTEM.

    Kept deliberately small: this is the half that is NOT cached and is paid
    for on every single lead.
    """
    lines = ["%d. %s" % (i, f.get("text")) for i, f in enumerate(facts, 1)]
    out = ["%s, %s at %s" % (lead.get("name"),
                             lead.get("title") or "role unknown", company),
           "angle: %s (%s)" % (angle, angle_reason),
           "facts:"] + lines
    if company_hook:
        # SECOND CONTACT AT AN ACCOUNT ALREADY WRITTEN FOR. The company hook is
        # reused verbatim and Sonnet writes only the person-specific lines, so
        # two colleagues never receive two different descriptions of their own
        # company - which is both cheaper and more correct.
        out.append("company hook already approved for this account, reuse it "
                   "rather than writing a new one: %s" % company_hook)
    out.append("ps_variant: %s" % ps_variant)
    if ps_variant == "ps_capability" and capability:
        # The client's OWN words for the capability, from productive.yaml via
        # `cadence.product_words`. Not a paraphrase the model invents, and not
        # a second copy of the sentence living in this file.
        out.append("capability to name in the P.S.: %s" % capability)
    if lead.get("linkedin"):
        out.append("this lead HAS a LinkedIn profile, so write the four "
                   "LinkedIn messages. Profile: %s" % lead["linkedin"])
    else:
        out.append("this lead has NO LinkedIn profile: return null for every "
                   "LinkedIn message rather than writing one nobody can send")
    return "\n".join(out)


# --------------------------------------------------------------------------
# The budget, and the batch-level checks. A cap nobody measures is a number
# in a document.
# --------------------------------------------------------------------------

def approx_tokens(text):
    """Rough count for budgeting. English prose runs ~0.75 words per token.

    Deliberately an APPROXIMATION and named as one. The real count comes from
    the provider's usage block, and that is what gets ledgered - this exists
    to catch a prompt that has grown, before the bill does.
    """
    return round(len(str(text or "").split()) / 0.75)


def budget_faults(system_text, user_text, output_tokens=None):
    """Every budget rule this call breaks. Empty means it passes."""
    out = []
    # The system half is CACHED, so it is not what per-lead cost turns on.
    # The user half is paid every time.
    if approx_tokens(user_text) > MAX_INPUT_TOKENS:
        out.append("per-lead input %d tokens, cap %d"
                   % (approx_tokens(user_text), MAX_INPUT_TOKENS))
    if output_tokens is not None and output_tokens > MAX_OUTPUT_TOKENS:
        out.append("output %d tokens, cap %d"
                   % (output_tokens, MAX_OUTPUT_TOKENS))
    return out


def account_cache_key(facts, persona):
    """`(account facts hash + persona)` - the operator's reuse key.

    The SECOND contact at an account reuses the company hook and pays only for
    the person-specific lines. Hashing the fact TEXTS rather than the raw pack
    means a re-crawl that finds the same facts hits the cache, and one that
    finds new facts does not.
    """
    texts = sorted(str(f.get("text") or "").strip().lower() for f in facts)
    digest = hashlib.sha256(json.dumps(texts).encode()).hexdigest()[:16]
    return "%s:%s" % (digest, str(persona or "").strip().lower())


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
    if not s:
        return ["empty"]
    out = []
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


def bridge_faults(bridges):
    """Bridges must not restate one another. One sentence each."""
    out = []
    seen = {}
    for key in ("em2", "em3", "em4", "em5"):
        text = str((bridges or {}).get(key) or "").strip()
        if not text:
            out.append("%s: empty" % key)
            continue
        if len(re.findall(r"[.!?]", text)) > 1:
            out.append("%s: more than one sentence" % key)
        norm = re.sub(r"[^a-z ]", "", text.lower())
        for other, prev in seen.items():
            shared = set(norm.split()) & set(prev.split())
            if len(shared) >= max(4, int(0.6 * len(set(norm.split())))):
                out.append("%s restates %s" % (key, other))
                break
        seen[key] = norm
    return out
