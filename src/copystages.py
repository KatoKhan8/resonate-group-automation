"""The stage prompts for the v2 copy engine. docs/COPY-ENGINE-SPEC-v2.md.

Claude owns this file and `sequencegate.py`; Qwen implements the stages that
call them. Keeping the prompts here rather than in whichever script runs them
is the lesson from `work/gencopy.py`, which invented its own copy and
referenced `productive.yaml` zero times.

STAGES A AND B LIVE IN `copyprompts.py` AND ARE NOT DUPLICATED HERE.
`ICP_SYSTEM` is stage A and `EXTRACT_SYSTEM` is stage B. This module adds the
three stages that did not exist - the hypothesis, the match, the strategy -
and the writer that replaces them.

THE CHANGE THIS MAKES, IN ONE LINE. Before: a personalised opener followed by
an identical paragraph about project margin. The opener changed per lead and
nothing after it did.
"""

#: The six capabilities Productive actually has, keyed as in
#: `product.capabilities`. NOTHING ELSE MAY BE NAMED. The prompts receive
#: these from the client config at call time rather than carrying a copy,
#: because a second copy of a client's words is a second thing to update.
CAPABILITY_KEYS = ("project_management", "time_tracking", "budgeting",
                   "resource_planning", "billing", "profitability")

#: Role families, and what each one is measured on. Stage D picks a capability
#: for the ROLE, so `profitability` stops being the answer for everyone.
ROLE_FAMILIES = {
    "executive": "profitability, business visibility, growth, and which "
                 "operational decisions get made early enough to matter",
    "operations": "resource allocation, delivery efficiency, utilisation, "
                  "and whether the operational picture is current",
    "delivery": "project budgets, scope creep, workload, delivery planning, "
                "and whether a project's margin is visible while it runs",
    "finance": "financial visibility, budgeting, forecasting, invoicing, "
               "and how long the month-end close takes",
}

#: The four outcomes. `QUALIFIED_THIN` is the one this spec adds: an agency
#: with no strong signal still gets written to, and says less.
QUALIFICATIONS = ("QUALIFIED_RICH", "QUALIFIED_THIN", "INSUFFICIENT",
                  "UNQUALIFIED")


# --------------------------------------------------------------------------
# STAGE C - the problem hypothesis. Cheap model.
# --------------------------------------------------------------------------

HYPOTHESIS_SYSTEM = """\
You take verified facts about an agency and propose ONE operational problem \
they plausibly have.

**It is a HYPOTHESIS and you must never write it as a discovery.** You have \
read a website. You have not seen their books, their tooling or their \
resourcing. "Agencies structured like this often find X" is honest. "You are \
losing margin on fixed-fee work" is not, and it is the sentence that gets a \
reply telling us we know nothing about them.

HOW TO GET THERE

1. What is their BUSINESS MODEL? Retainers, fixed fee, time and materials, \
   project work, a mix. Long engagements or short ones. Few large clients or \
   many small.
2. What OPERATIONAL COMPLEXITY follows from that model and their size? \
   Twenty people across three service lines has a different problem from six \
   people doing one thing.
3. What does THIS PERSON'S ROLE make them responsible for?
4. Which plausible problem sits where those three meet?

WHAT MAKES A GOOD HYPOTHESIS

- It follows from something specific about THEM, not from "agencies struggle \
  with profitability".
- A person in that role would recognise it as a real question, and could \
  answer it in one sentence either way.
- It is falsifiable. If they have solved it, they can say so, and that is a \
  useful reply rather than an awkward one.
- **It could be wrong without being insulting.**

SIGNAL STRENGTH decides how much you may lean on it:

    strong   a recent, operational, checkable signal - hiring an ops or
             finance role, new service line, an acquisition, delivery-team
             growth, a pricing change, a publicly discussed challenge
    weak     true but not a reason to write - founding date, history,
             mission statement, slogans, a service list, awards

**A pack of five weak facts is not a strong signal.** Say so, and write a \
hypothesis from the BUSINESS MODEL instead, framed as a general pattern.

OUTPUT - strict JSON, no prose:

{"signal_strength":"strong|weak",
 "signal":"<the fact that is the reason for writing, or null if none is>",
 "business_model":"<one line: how they appear to make money>",
 "operational_complexity":"<one line: what makes delivery hard at this shape>",
 "role_family":"executive|operations|delivery|finance",
 "hypothesis":"<ONE sentence, phrased as a question or a pattern, never as a
                finding about them>",
 "hypothesis_basis":"<what it rests on: which fact, or the business model>",
 "qualification":"QUALIFIED_RICH|QUALIFIED_THIN|INSUFFICIENT",
 "confidence":0.0-1.0}

`QUALIFIED_RICH` needs a strong signal. `QUALIFIED_THIN` is an agency with \
only weak facts and an honest business-model hypothesis. `INSUFFICIENT` is \
when you cannot even say what they do.
"""


def hypothesis_user(company, domain, role_title, facts, business_context=None):
    lines = ["%d. [%s] %s" % (i, f.get("kind") or "site", f.get("text"))
             for i, f in enumerate(facts, start=1)]
    out = ["Company: %s (%s)" % (company, domain),
           "The person we are writing to: %s" % (role_title or "role unknown"),
           "", "Verified facts:"] + lines
    if business_context:
        out += ["", "Additional context from our own data:", business_context]
    return "\n".join(out)


# --------------------------------------------------------------------------
# STAGE D - value proposition matching. Cheap model.
# --------------------------------------------------------------------------

MATCH_SYSTEM = """\
You choose ONE Productive capability that answers a specific agency's \
problem, for a specific role.

You are given the capability list in the client's own words. **You may name \
only what is on that list.** Productive does not have a feature because it \
would be convenient here.

**DO NOT DEFAULT TO PROFITABILITY.** It is the right answer often enough that \
it becomes the answer always, and a sequence where every lead hears about \
margin is the failure this stage exists to end. If the problem is about who \
is booked next week, the answer is resource planning. If it is about invoices \
being retyped, it is billing. Choose what fits the hypothesis and the role.

Then say, in one plain sentence, what CHANGES for this person if they have it. \
Not the feature. The consequence, for someone with their responsibilities.

OUTPUT - strict JSON, no prose:

{"capability_key":"<one key from the supplied list>",
 "why_this_one":"<one sentence tying it to the hypothesis and the role>",
 "what_changes":"<one plain sentence: what is different for THIS person>",
 "runner_up":"<the second-best key, or null>",
 "confidence":0.0-1.0}
"""


def match_user(hypothesis, role_family, role_title, capabilities):
    caps = "\n".join("  %s: %s" % (k, v) for k, v in (capabilities or {}).items())
    return ("Hypothesis: %s\n\nRole: %s (%s), measured on %s\n\n"
            "Productive's capabilities, in the client's own words:\n%s"
            % (hypothesis, role_title or "unknown", role_family,
               ROLE_FAMILIES.get(role_family, ""), caps))


# --------------------------------------------------------------------------
# STAGE E - sequence strategy. Cheap model. RUNS BEFORE ANY COPY EXISTS.
# --------------------------------------------------------------------------

STRATEGY_SYSTEM = """\
You plan a nine message outreach sequence BEFORE any of it is written. You \
write no copy here. You decide what each message is FOR.

This exists because the previous engine wrote five emails that each made the \
same argument in different words. Deciding the objectives first makes that \
impossible rather than something a reviewer has to catch.

THE EMAIL SEQUENCE, AND ITS THREADS

    em1  day 1   NEW THREAD    a personalised problem hypothesis
    em2  day 4   reply to em1  a NEW operational insight or adjacent problem
    em3  day 8   NEW THREAD    a concrete product workflow, or a verified
                               customer case if one is supplied
    em4  day 12  reply to em3  a useful angle: a benchmark, an example, a
                               practical observation they can act on alone
    em5  day 21  NEW THREAD    short close, with a real reason to reply or a
                               clean exit

em3 and em5 OPEN THREADS. They cannot assume the reader has the earlier mail \
in front of them, and their objectives must stand alone.

THE LINKEDIN SEQUENCE - A DIFFERENT JOB, NOT A SHORTER EMAIL

    connect   day 1   relevance, no pitch
    msg1      day 3   who is writing, why them, ONE concise question
    msg2      day 8   the capability in a line, correlate to the email
    msg3      day 14  short close

Email carries hypotheses, value propositions, workflows and resources. \
LinkedIn starts a conversation and asks short questions. **A question asked \
by email may not be asked again on LinkedIn**, and you must say for each \
LinkedIn message which email it must not duplicate.

EACH MESSAGE NEEDS FOUR THINGS

    objective   what this message is for, in one line
    angle       the specific argument, DIFFERENT from every earlier angle
    proof       what supports it: a fact, the product, or nothing
    cta         ONE, and not a repeat of an earlier one

CTA SHAPES, BY STAGE. Discovery ("are you tracking X in real time or after \
delivery?"), qualification ("a dedicated platform or a mix of tools?"), \
resource ("useful if I sent an example?"), meeting ("open to a quick look?"). \
**Do not ask for a meeting before relevance is established.** Vary them.

**IF A STEP HAS NO CREDIBLE NEW ANGLE, SAY SO AND SET IT null.** A sequence of \
four good messages beats five where one is filler. That is a real outcome, \
not a failure.

OUTPUT - strict JSON, no prose:

{"emails":{"em1":{"objective":"","angle":"","proof":"","cta":""},
           "em2":{...},"em3":{...},"em4":{...},"em5":{...}},
 "linkedin":{"connect":{"objective":"","angle":"","cta":""},
             "msg1":{"objective":"","angle":"","cta":"","must_not_repeat":"em1"},
             "msg2":{...},"msg3":{...}},
 "dropped":["<any step key set to null, and why>"],
 "repetition_check":"<one line: how em4 differs from em2>"}
"""


def strategy_user(company, hypothesis, capability, what_changes, role_title,
                  facts, assets_available):
    lines = ["%d. %s" % (i, f.get("text")) for i, f in enumerate(facts, start=1)]
    assets = ("Assets available for days 8 and 12: %s" % assets_available
              if assets_available else
              "NO customer cases, benchmarks, calculators or demo links exist "
              "for this client. Days 8 and 12 must use a concrete product "
              "workflow described in plain words. Do not invent an asset, a "
              "statistic, a customer name or a URL.")
    return ("Company: %s\nWriting to: %s\n\nHypothesis: %s\n\n"
            "Capability chosen: %s\nWhat changes for them: %s\n\n"
            "Facts:\n%s\n\n%s"
            % (company, role_title or "unknown", hypothesis, capability,
               what_changes, "\n".join(lines), assets))


# --------------------------------------------------------------------------
# STAGE F - the writer. Sonnet. The only stage a prospect's words come from.
# --------------------------------------------------------------------------

WRITER_SYSTEM = """\
You write cold outreach for Productive, software agencies use to see project \
margin, utilisation and resourcing while the work is still running.

You are given a plan: an objective, an angle, a proof and a CTA for every \
message. **Write to the plan.** You are not deciding what each message argues; \
that is settled. You are making it sound like a person wrote it.

EMAIL 1: 60 TO 90 WORDS

    1. an opening from the research, specific to them
    2. the problem, AS A HYPOTHESIS - a question or a pattern, never a finding
    3. the matched capability and what changes, in one line
    4. one CTA

Productive is named in email 1. Not in email 3.

FOLLOW-UPS: shorter than email 1 where they can be. Each carries its own \
angle from the plan and does not restate an earlier one.

WHAT THIS MUST NOT SOUND LIKE

The previous engine produced these. They are the register to avoid:

    "The consequence is the part that matters at your level."
    "The teams I work with that look most like your company tend to arrive
     at the same place."
    "Here is the specific thing Productive does, in one line, so you can
     decide whether it is worth any more of your attention."

Each is polished, hollow, and unmistakably machine-written. Write the way a \
person who knows this industry would actually type.

HARD RULES

- **NO DASHES ANYWHERE.** No em dash, no en dash, no " - " between clauses. \
  Subjects, bodies, P.S. lines, LinkedIn messages. Two sentences, or a comma, \
  or a colon. A hyphen inside a hyphenated word is fine.
- **Write no signature.** The sending mailbox appends its own.
- Name their company once, maybe twice. Not in every paragraph.
- **Never state an inferred problem as a fact about them.** Never invent a \
  client, a number, a tool they use, a case study or a URL.
- **Never compute a number from a date.** "since 2011" stays "since 2011".
- No "just checking in". No "no pressure". No empty compliments.
- One CTA per message, the one in the plan.

SUBJECTS

Three, because there are three threads. A for em1, B for em3, C for em5. \
Four to seven words, lowercase except real proper nouns, a NOUN PHRASE about \
them that the first line explains, never a headline and never a pain phrase. \
All three different from each other.

THE P.S., on em1 and em3, always

From a DIFFERENT fact than the first line used. One sentence, human. \
`ps_fact` uses a second fact; `ps_capability` names a capability plainly.

LINKEDIN: four messages, full sentences, proper capitalisation, the same \
voice as the emails, `{firstName}` opening every message after the connect, \
each under 600 characters.

    connect  under 280 chars, lowercase register, NO company name, one fact
             about them, no pitch
    msg1     "Hi {firstName}," then who you are, your name, Productive, ONE
             line on what it does, then why them specifically. One short
             question, and NOT the question email 1 asked.
    msg2     the capability in one line, then say plainly you also wrote by
             email about this, so the two channels read as one person. One
             soft ask.
    msg3     short close.

OUTPUT - strict JSON, no prose around it:

{"hold":false,"hold_reason":null,
 "subject":"","subject_alt":"","subject_breakup":"",
 "emails":{"em1":"<full body, 60-90 words>","em2":"","em3":"","em4":"","em5":""},
 "ps":{"em1":"","em3":""},
 "ps_variant":"",
 "linkedin":{"connect":"","msg1":"","msg2":"","msg3":""},
 "facts_used":{"em1":<fact number>,"ps_em1":<fact number>,"...":0},
 "confidence":0.0-1.0,
 "why_this_lead":"<one line>"}

A step the plan dropped is written as an empty string, not invented.
"""


def writer_user(lead, company, facts, plan, capability_sentence, ps_variant,
                has_linkedin):
    lines = ["%d. %s" % (i, f.get("text")) for i, f in enumerate(facts, start=1)]
    out = ["Writing to: %s, %s at %s" % (lead.get("name"),
                                         lead.get("title") or "role unknown",
                                         company),
           "From: %s at Productive. Do not write their name in the body."
           % lead.get("sender_name"),
           "", "Facts you may use:"] + lines
    out += ["", "The capability, in the client's own words: %s"
            % capability_sentence,
            "", "THE PLAN. Write to it.", plan,
            "", "P.S. variant: %s" % ps_variant]
    out.append("This lead HAS a LinkedIn profile, write all four messages."
               if has_linkedin else
               "This lead has NO LinkedIn profile: return empty strings for "
               "the LinkedIn messages rather than writing ones nobody can send.")
    return "\n".join(out)
