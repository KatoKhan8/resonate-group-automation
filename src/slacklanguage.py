#!/usr/bin/env python3
"""Which language a question is in, so the answer is in the same one.

OPERATOR, 2026-09-22: "answer in the language the question was asked in.
Croatian in, Croatian out; English in, English out. Numbers, ids and
domains unchanged."

## WHY THERE IS DETECTION AT ALL, WHEN THE MODEL COULD JUST MIRROR

The model is told to mirror, and it does. Detection exists for the two
things a prompt cannot do:

1. **The lines this module writes itself.** The "as of" stamp, the
   attribution line on a relayed answer, and the deterministic fallback are
   assembled in code. Code cannot mirror a language it has not identified.
2. **The log.** A turn records the language it answered in, so "it replied
   in English to a Croatian question" is a thing somebody can find rather
   than a thing somebody remembers.

## IT IS DELIBERATELY SMALL, AND IT ABSTAINS

Two languages, because two are in use. A message it cannot place returns
`None`, which means "mirror it" to the model and "use English" for the
lines written in code - English being the language the system itself is
written in, not a guess about the reader.

Croatian is identified by its diacritics and by function words that are not
English words. Both halves matter: `č ć ž š đ` are decisive when present
and absent from plenty of real Croatian typed without them, and a Croatian
sentence with no diacritics is still full of `koje`, `koliko`, `možete`,
`nam`. English is identified the same way, so a message in neither scores
zero on both and abstains rather than defaulting to the more common one.
"""
import re
import unicodedata

CROATIAN = "hr"
ENGLISH = "en"

NAMES = {CROATIAN: "Croatian", ENGLISH: "English"}

#: Letters that occur in Croatian and not in English.
_CROATIAN_LETTERS = set("čćžšđ")

#: Function words. Short, common, and not English words - `i` and `a` are
#: deliberately absent because they are English words too.
_CROATIAN_WORDS = frozenset("""
    je su smo ste nije nisu bio bila biti ima imamo imate nemamo
    koji koje koja kojih koliko kada gdje kako zašto zasto sto što
    da li jel jeli molim hvala pozdrav bok
    mogu mozemo možemo mozete možete treba trebam trebamo
    nam nas naše nase naš nas vam vas vaše vase
    popis spisak lista domena domene domenama mailove mailova
    kampanja kampanje kampanjama kampanji sender senderi
    salje šalje saljete šaljete poslano poslali
    tjedan tjedna tjedno nedelja nedelje danas jučer jucer sutra
    zadnji zadnja zadnje prvi prva prvo
    ovo ova ovaj taj ta to te ti
    sa sam samo ali ili pa jos još već vec
    u na za od do iz po uz kroz bez
""".split())

_ENGLISH_WORDS = frozenset("""
    the a an is are was were be been being have has had
    which what who when where why how many much
    can could would should will do does did
    our us we you your their they them
    list domain domains mailbox mailboxes sender senders
    campaign campaigns send sends sent sending
    week today yesterday tomorrow last first
    this that these those there here
    and or but so for from with without of to in on at by
""".split())

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _words(text):
    return [w.lower() for w in _WORD.findall(str(text or ""))]


def _strip_mentions(text):
    """A Slack mention is an id, not a word in anybody's language."""
    body = re.sub(r"<[@#!][^>]*>", " ", str(text or ""))
    return re.sub(r"https?://\S+", " ", body)


def score(text):
    """`(croatian score, english score)`. Counts, not probabilities."""
    body = _strip_mentions(text)
    words = _words(body)
    lowered = unicodedata.normalize("NFC", body.lower())
    croatian = sum(1 for ch in lowered if ch in _CROATIAN_LETTERS)
    croatian += sum(1 for w in words if w in _CROATIAN_WORDS)
    english = sum(1 for w in words if w in _ENGLISH_WORDS)
    return croatian, english


def detect(text):
    """`"hr"`, `"en"`, or `None` when it cannot tell.

    None is a real answer and the commonest one for a three-word message.
    It means "mirror the message" to the model, which is better at that
    than this is, and "English" to the code that has to write a line.
    """
    croatian, english = score(text)
    if croatian == english:
        return None
    return CROATIAN if croatian > english else ENGLISH


def name(code):
    return NAMES.get(code or "", "the language of the message")


def instruction(text):
    """The sentence added to the prompt for one incoming message."""
    code = detect(text)
    if code is None:
        return ("Answer in THE SAME LANGUAGE as the message below. If you "
                "cannot tell, answer in English.")
    return ("Answer in %s. The message is in %s and the reply must be too. "
            "Numbers, campaign ids, domains and email addresses are written "
            "exactly as they appear in the material - they are not "
            "translated." % (NAMES[code], NAMES[code]))
