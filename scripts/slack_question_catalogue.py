#!/usr/bin/env python3
"""What people actually ask, mined from the workspace's own Slack history.

    py -3 scripts/slack_question_catalogue.py --report
    py -3 scripts/slack_question_catalogue.py --write

OPERATOR, 2026-09-22: "From that history build
docs/SLACK-AGENT-QUESTION-CATALOGUE.md: the real questions clients and
colleagues ask, grouped by intent... with the phrasing they use in Croatian
and English, who asks (client vs internal), and which existing tool answers
each or what tool is missing."

## THE HISTORY IS NOT A LIST OF QUESTIONS ABOUT OUTBOUND

The first read pulled 6,091 messages and the sample was salaries, invoices,
a GoDaddy password typed in plain text, personal phone numbers, and four
clients' internal threads. Slack is where a company does its business, not
a support queue.

So this refuses two things by construction:

1. **Sensitive channels are not mined at all.** Leadership, accounts and
   payroll rooms are read by nobody here. Their questions are real and they
   are none of the agent's business.
2. **Everything that survives is REDACTED before it is counted**, never
   after. Addresses, phone numbers, URLs, money, long digit runs and
   anything shaped like a credential are replaced before a line is stored,
   so a secret cannot reach the catalogue even if the classifier likes the
   sentence.

## WHAT COMES OUT IS A SHAPE, NOT A QUOTE

An example phrasing is kept only when it survives redaction unchanged in
meaning - it is there to show HOW somebody asks, not WHAT they asked about.
Names become roles. A client's own detail stays in `work/`.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import load_env                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def history_dir():
    from src import store
    return os.path.join(os.path.dirname(store.queue_path()), "slack-history")


#: Rooms this never reads. Payroll, invoicing and leadership are a
#: company's private business; the agent answers about outbound.
SENSITIVE_CHANNELS = (
    "resonate-leadership", "računi", "racuni", "finance-weekend-team",
    "finance-weekend",
)

#: A message carrying any of these is dropped whole, not redacted. A
#: sentence about a password is not a question shape worth keeping even
#: with the password removed.
SECRET_MARKERS = (
    "lozinka", "password", "passwd", "sifra", "šifra", "2fa", "otp",
    "api key", "apikey", "token", "secret", "credential", "login je",
    "prijava je", "pristupni",
)

#: Redactions, applied in order, BEFORE anything is counted or stored.
REDACTIONS = (
    (re.compile(r"<@[A-Z0-9]+(\|[^>]*)?>"), "@person"),
    (re.compile(r"<#[A-Z0-9]+(\|[^>]*)?>"), "#channel"),
    (re.compile(r"<https?://[^>]+>"), "<link>"),
    (re.compile(r"https?://\S+"), "<link>"),
    (re.compile(r"[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}"), "<address>"),
    (re.compile(r"\+?\d[\d\s().-]{7,}\d"), "<number>"),
    (re.compile(r"\b\d+[.,]\d{2}\s*(?:€|EUR|eur|kn|\$)"), "<amount>"),
    (re.compile(r"(?:€|\$)\s?\d[\d.,]*"), "<amount>"),
    (re.compile(r"\b[A-Za-z0-9]*\d[A-Za-z0-9]*[!@#$%^&*][A-Za-z0-9!@#$%^&*]*"),
     "<redacted>"),
)


#: Client and vendor names seen in the history. A client's identity is a
#: client-internal detail the moment it sits in a shared document beside
#: what they asked, so the catalogue carries `<client>` and the channel
#: carries a ROLE. Which client asked is in `work/` and stays there.
#:
#: Extended by reading the channel list rather than guessed: every
#: `<name>-team` and `<name>-resonate-outbound` room names one.
CLIENT_WORDS = (
    "productiv", "nextori", "netnad", "synvers", "pepermint", "idegas",
    "cyber64", "cyber-64", "mediaboard", "masterinbox", "farseer",
    "weekend media", "finance weekend", "wa-outreach", "blitz",
)

# STEM MATCHING. Croatian declines these - "netnadu", "Nextoriji" -
# and a whole-word match leaves every inflected form standing.
_CLIENT = re.compile(r"(?:%s)\w*"
                     % "|".join(re.escape(w) for w in CLIENT_WORDS), re.I)

#: First names and nicknames of the people in these rooms. A style
#: reference is about HOW somebody writes, not who they are.
PERSON_WORDS = (
    "zvonimir", "zvone", "zvoki", "tina", "martina", "jelena", "vera",
    "bruno", "kreso", "kresimir", "bernarda", "ivan", "fran",
    "tomislav", "bojan", "jakov", "luka", "marko", "gabrijela", "gabi",
    "milica", "pave", "sven", "helena", "djole", "dino", "dina",
    "munira", "nitin", "ana", "andrija", "kristijan", "mario", "igor",
)

_PERSON = re.compile(r"\b(?:%s)\w*"
                     % "|".join(re.escape(w) for w in PERSON_WORDS), re.I)


def channel_role(name):
    """A room's ROLE, never its client. `#nextoria-team` is a team room."""
    lowered = str(name or "").lower()
    if lowered.endswith("-resonate-outbound") or "outbound" in lowered:
        return "client-channel"
    if lowered.endswith("-team") or lowered.endswith("-hq"):
        return "delivery-team"
    if lowered.startswith("resonate-") or lowered in (
            "weekly-goals", "knowledge-share", "all-resonategroup",
            "social", "replies-log"):
        return "internal"
    return "internal"


def redact(text):
    body = str(text or "")
    for pattern, replacement in REDACTIONS:
        body = pattern.sub(replacement, body)
    body = _CLIENT.sub("<client>", body)
    body = _PERSON.sub("@person", body)
    return re.sub(r"\s+", " ", body).strip()


#: The intents, each with the words that mark it in both languages. Built
#: from reading the history rather than from imagining a taxonomy - the
#: order matters, first match wins, and the most specific come first.
INTENTS = (
    ("senders and domains",
     ("domena", "domene", "domenu", "domain", "sender", "sendera", "senderi",
      "pošiljatelj", "posiljatelj", "mailbox", "inbox", "seat", "sjedal",
      "warmup", "bounce", "spam", "deliverability", "godaddy", "dns")),
    ("cadence and copy",
     ("kadenc", "sekvenc", "cadence", "sequence", "copy", "poruka", "poruke",
      "messaging", "template", "predložak", "predlozak", "step", "korak",
      "connection message", "follow up", "followup", "subject")),
    ("leads and lists",
     ("lead", "leadov", "lista", "liste", "listu", "list", "icp", "cohort",
      "kohort", "prospect", "kontakt", "contacts", "targetir", "filter")),
    ("replies and meetings",
     ("odgovor", "odgovora", "reply", "replies", "meeting", "sastanak",
      "sastanka", "booked", "interested", "zainteresiran", "call", "poziv",
      "demo", "no show", "noshow")),
    ("status and volume",
     ("status", "koliko", "how many", "kolko", "volumen", "volume", "poslano",
      "sent", "poslali", "dnevno", "daily", "ovaj tjedan", "this week",
      "kampanj", "campaign", "aktivn", "active", "pokrenul", "launch")),
    ("reporting",
     ("report", "izvje", "izvest", "metrik", "metrics", "rezultat", "results",
      "dashboard", "spreadsheet", "sheet", "analytics", "connection rate",
      "reply rate")),
    ("change requests",
     ("makni", "maknuti", "ukloni", "remove", "stop", "pauzir", "pause",
      "isključ", "iskljuc", "dodaj", "add", "promijeni", "promjena",
      "change", "update", "ugasi", "restart")),
    ("onboarding and access",
     ("pristup", "access", "invite", "pozovi", "dodaj u kanal", "spojim",
      "spoji", "connect", "setup", "postav", "onboard", "kick off",
      "kickoff")),
    ("capacity and planning",
     ("kapacitet", "capacity", "plan", "planira", "sljedeci tjedan",
      "next week", "roadmap", "prioritet", "priority", "kada", "when will",
      "deadline", "rok")),
)


def classify(text):
    lowered = text.lower()
    for name, markers in INTENTS:
        if any(marker in lowered for marker in markers):
            return name
    return "other"


#: Which tool answers an intent today, or what is missing.
ANSWERED_BY = {
    "senders and domains": "sending_domains, sender_roster, sender_summary",
    "cadence and copy": "cadence_detail  (copy TEXT itself: MISSING)",
    "leads and lists": "lead_lookup, account_lookup  (list counts: MISSING)",
    "replies and meetings": "replies  (meetings booked: MISSING)",
    "status and volume": "sends_today, activity_this_week, batch_state",
    "reporting": "MISSING - no reporting tool; clientreport.py is unwired",
    "change requests": "the ticket flow (slackrequests)",
    "onboarding and access": "MISSING - and probably should stay missing",
    "capacity and planning": "sender_summary  (forward book: MISSING)",
    "other": "n/a",
}


def load(skip_sensitive=True):
    """Every usable message, redacted, with its channel and asker class."""
    rows = []
    for path in glob.glob(os.path.join(history_dir(), "*.jsonl")):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                name = str(row.get("_channel_name") or "")
                if skip_sensitive and any(s in name
                                          for s in SENSITIVE_CHANNELS):
                    continue
                if row.get("bot_id") or row.get("subtype"):
                    continue
                text = row.get("text") or ""
                if not text.strip():
                    continue
                if any(marker in text.lower() for marker in SECRET_MARKERS):
                    continue
                rows.append({"channel": name,
                             "workspace": row.get("_workspace"),
                             "user": row.get("user"),
                             "text": redact(text),
                             "ts": row.get("ts")})
    return rows


def questions(rows):
    """Messages that are asking something, in either language."""
    askish = re.compile(
        r"\?|^\s*(?:da li|dal|jel|jeli|možeš|mozes|možemo|mozemo|imaš|imas|"
        r"treba|trebam|koliko|koje|koji|kada|kad|gdje|zašto|zasto|kako|"
        r"can you|could you|do you|is there|are there|what|when|which|how)\b",
        re.I)
    return [r for r in rows if askish.search(r["text"])]


def report(rows):
    asked = questions(rows)
    by_intent = collections.Counter(classify(r["text"]) for r in asked)
    by_channel = collections.Counter(r["channel"] for r in asked)
    return {"messages": len(rows), "questions": len(asked),
            "by_intent": by_intent, "by_channel": by_channel,
            "asked": asked}


#: Capitalised words that are not somebody's name. Everything else that is
#: capitalised mid-sentence is treated as one.
SAFE_CAPITALS = frozenset("""
    slack linkedin microsoft google outlook gmail heyreach emailbison bison
    reoon apollo clay crm api csv icp dnc us usa uk eu au nsw ai sms
    whatsapp wa teams zoom meet drive sheets docs gdpr saas b2b sdr
    monday tuesday wednesday thursday friday saturday sunday
    january february march april may june july august september october
    november december
    resonate ok okay hi hey hello da ne jel
""".split())

_CAPITALISED = re.compile("(?<![.!?] )" + chr(92) + "b"
                          "[A-ZČĆŽŠĐ]"
                          "[a-zšđčćž]{2,}")


def looks_like_it_names_somebody(text):
    """Does this line carry a capitalised word that is probably a name?

    A BLOCKLIST CANNOT BE EXHAUSTIVE and this file is proof: the person
    list caught eleven names and missed the twelfth on the first run.
    Examples reach `docs/`, so they get a mechanical rule instead - any
    capitalised word mid-sentence that is not a known product, place or
    weekday is treated as a name and the example is dropped.

    It over-drops. That is the right direction for a document whose whole
    contract is that it carries question shapes and no identities.
    """
    for match in _CAPITALISED.finditer(str(text or "")):
        if match.group(0).lower() not in SAFE_CAPITALS:
            return True
    return False


def examples(asked, intent, limit=6, min_len=25, max_len=125):
    """Short, redacted phrasings that show HOW somebody asks."""
    seen, out = set(), []
    for row in asked:
        if classify(row["text"]) != intent:
            continue
        text = row["text"]
        if not (min_len <= len(text) <= max_len):
            continue
        if looks_like_it_names_somebody(text):
            continue
        key = re.sub(r"[^a-z ]", "", text.lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--intent", help="dump examples for one intent")
    args = parser.parse_args(argv)
    load_env()
    rows = load()
    found = report(rows)
    print("usable messages %d   questions %d   (sensitive channels skipped)"
          % (found["messages"], found["questions"]))
    print()
    for intent, count in found["by_intent"].most_common():
        print("%-26s %4d   %s" % (intent, count, ANSWERED_BY.get(intent, "")))
    if args.intent:
        print()
        for row in examples(found["asked"], args.intent, limit=12):
            print("  [%-15s] %s"
                  % (channel_role(row["channel"]), row["text"][:120]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
