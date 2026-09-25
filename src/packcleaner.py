"""Strip navigation chrome from research pack snippets before the model sees them.

EVERY PACK SNIPPET IN THE STORE opens with the site's nav strip:

    "Skip to the content About Clients Archive Menu 3x34 ... "
    "Call +353 1 864 3704 home our work experience live experience ..."
    "Services Testimonials Case Studies About Book a call ..."
    "Login About Paradigm Leadership Services Recent Work Contact ..."

The incident's "quote" was the head of one of these. Both prompts in
`copyprompts.py` are told what nav text looks like and to refuse it; this
module removes it before the model ever sees it, so the model cannot quote
what it was never shown.

## WHAT THIS IS AND IS NOT

This is a PRE-MODEL cleaner. It runs on the raw snippet before it reaches
the extractor. It is not a fact checker - `copyprompts.EXTRACT_SYSTEM` and
the quote-verification in `copyextract` are the fact checkers. This removes
the material that is KNOWN to not be content: menu items, skip links,
social icon labels, cookie banners, and phone/address lines that precede
the first real sentence.

## HOW IT DECIDES WHAT IS CHROME

A snippet is split into tokens. Tokens are classified as nav-like or
content-like. A prefix of consecutive nav-like tokens is stripped. The
first content-like token starts the cleaned text.

Nav-like tokens are:
- Known skip-link prefixes ("Skip to content", "Skip to the content")
- Known nav words (About, Services, Contact, Menu, Home, Blog, ...)
- Social icon labels (Facebook-f, Twitter, Linkedin, Instagram, ...)
- Phone numbers and email addresses at the start
- Short fragments (< 4 chars) that are nav separators (|, ·, bullet)
- Cookie/banner phrases

The FIRST sentence that is long enough and carries a verb is treated as
content. A sentence that is only nav words is not content even if it has
a period.
"""
import re

#: Prefixes that are always stripped. Case-insensitive, matched at the start.
SKIP_PREFIXES = (
    r"skip\s+to\s+(?:the\s+)?content",
    r"skip\s+to\s+main\s+content",
)

#: Words that are navigation when they appear in the opening strip. Matched
#: case-insensitively as whole words. A word like "About" in a sentence
#: "About our approach to margin visibility" is content; "About" as the
#: third token in a menu strip is chrome. The distinction is POSITION:
#: these are only stripped from the PREFIX, never from the middle.
NAV_WORDS = frozenset({
    "about", "services", "contact", "menu", "home", "work", "team",
    "blog", "careers", "privacy", "cookie", "cookies", "newsletter",
    "facebook", "facebook-f", "twitter", "linkedin", "instagram", "youtube",
    "tiktok", "pinterest", "testimonials", "cases", "case", "studies",
    "clients", "archive", "search", "subscribe", "sign", "log", "login",
    "register", "faq", "terms", "legal", "solutions", "resources",
    "industries", "company", "news", "events", "press", "partners",
    "portfolio", "projects", "process", "approach", "vacancies",
    "experience", "live", "fit", "book", "call", "get", "started",
    "link", "account", "dashboard", "pricing",
})

#: Social icon labels that appear as nav items. These are not words a person
#: wrote; they are alt-text from icon fonts.
SOCIAL_LABELS = frozenset({
    "facebook-f", "facebook", "twitter", "linkedin", "linkedin-in",
    "instagram", "youtube", "tiktok", "pinterest", "vimeo", "behance",
    "dribbble", "github", "slack", "whatsapp", "telegram",
})

#: Cookie banner phrases. Matched as substrings, case-insensitive.
COOKIE_PHRASES = (
    "we use cookies",
    "this website uses cookies",
    "accept all cookies",
    "cookie settings",
    "manage cookies",
    "reject non-essential",
    "by continuing to use this site",
    "please accept cookies",
)

#: Separator characters that appear between nav items.
SEPARATORS = frozenset("·•|–—▸▹►▻❯❮‹›»«")

_WORD_RE = re.compile(r"[A-Za-z0-9'_-]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_PHONE_RE = re.compile(
    r"(?:\+?\d[\d\s().-]{6,}\d)")
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _strip_prefixes(text):
    """Remove known skip-link prefixes from the start."""
    for pattern in SKIP_PREFIXES:
        text = re.sub(r"^" + pattern + r"\s*", "", text, flags=re.I)
    return text


def _is_cookie_banner(segment):
    """Is this segment part of a cookie/privacy banner?"""
    low = segment.lower()
    return any(phrase in low for phrase in COOKIE_PHRASES)


def _is_nav_token(token):
    """Is this single token navigation chrome?"""
    low = token.lower().rstrip(".,;:!?")
    if not low:
        return True
    if low in NAV_WORDS:
        return True
    if low in SOCIAL_LABELS:
        return True
    # Short NON-alphabetic tokens are separators (·, |, •, →). Short
    # alphabetic tokens like "we", "a" are content words and must NOT be
    # stripped - that was the bug that ate "We are a creative agency".
    if not any(c.isalpha() for c in low) and len(low) <= 2:
        return True
    if all(c in SEPARATORS | set(" \t") for c in low):
        return True
    return False


def _is_phone_or_email(token):
    """Does this token look like a phone fragment or email?"""
    return bool(_PHONE_RE.match(token) or _EMAIL_RE.match(token))


def _starts_with_verb(sentence):
    """Does this sentence start with a verb form? A rough heuristic.

    Content sentences usually start with a verb, a determiner, or the
    company name. Nav items start with a noun from the menu. This is not
    perfect but it catches the common case where the nav strip ends and
    a real sentence begins.
    """
    words = sentence.split()
    if not words:
        return False
    first = words[0].lower().rstrip(".,;:!?")
    # Common content starters that are NOT nav items
    content_starters = {
        "we", "our", "the", "a", "an", "with", "at", "from", "for",
        "is", "are", "was", "were", "have", "has", "had", "do", "does",
        "help", "drive", "build", "create", "deliver", "provide",
        "specialise", "specialize", "focus", "offer", "bring", "make",
        "design", "develop", "manage", "grow", "partner", "work",
        "trusted", "leading", "award-winning", "results-driven",
        "driven", "passionate", "dedicated", "proud", "here",
        "when", "if", "because", "since", "while", "although",
        "every", "your", "you", "they", "it", "this", "that",
    }
    return first in content_starters


def clean(text):
    """Strip navigation chrome from one snippet. Returns the cleaned text.

    If no content is found after stripping, returns the original text
    unchanged - the extractor's prompt already refuses nav text, and
    returning empty would lose the signal that this snippet had nothing.
    """
    if not text or not str(text).strip():
        return ""
    text = str(text)
    original = text

    # Step 1: Remove known skip-link prefixes
    text = _strip_prefixes(text).strip()

    # Step 2: Walk tokens from the start, stripping nav-like ones
    tokens = text.split()
    content_start = 0
    for i, token in enumerate(tokens):
        stripped = token.rstrip(".,;:!?")
        if _is_nav_token(token) or _is_phone_or_email(token):
            content_start = i + 1
            continue
        # A token that is not nav-like: check if it starts real content
        break

    if content_start > 0:
        text = " ".join(tokens[content_start:]).strip()

    # Step 3: If what remains starts with a sentence that looks like a
    # cookie banner, skip past it
    if text and _is_cookie_banner(text[:200]):
        sentences = _SENTENCE_END.split(text)
        for j, s in enumerate(sentences):
            if not _is_cookie_banner(s):
                text = " ".join(sentences[j:]).strip()
                break

    # Step 4: If the remaining text still looks like nav (all short tokens,
    # no sentence > 30 chars), try to find the first real sentence
    if text and len(text) > 20:
        sentences = _SENTENCE_END.split(text)
        for j, s in enumerate(sentences):
            if len(s.strip()) > 30 and _starts_with_verb(s):
                candidate = " ".join(sentences[j:]).strip()
                if candidate:
                    text = candidate
                    break

    return text if text.strip() else original


def clean_sources(sources):
    """Clean a list of {label, url, text} sources. Returns new list.

    Each source's `text` is cleaned. Other fields are preserved.
    Reports before/after character counts for the acceptance metric.
    """
    out = []
    total_before = 0
    total_after = 0
    for s in (sources or []):
        raw = s.get("text") or ""
        cleaned = clean(raw)
        total_before += len(raw)
        total_after += len(cleaned)
        out.append({**s, "text": cleaned,
                    "_raw_len": len(raw), "_clean_len": len(cleaned)})
    return out, total_before, total_after


def mean_chars_per_lead(sources_before, sources_after):
    """Mean characters per lead before and after cleaning.

    The acceptance metric from the task: report mean chars per lead before
    and after cleaning.
    """
    n = max(len(sources_before), len(sources_after), 1)
    before = sum(len(s.get("text") or "") for s in sources_before) / n
    after = sum(len(s.get("text") or "") for s in sources_after) / n
    return round(before, 1), round(after, 1)
