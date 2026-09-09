#!/usr/bin/env python3
"""A PDF writer, in the same spirit as everything else here: by hand.

The repository has zero third-party dependencies. `src/clients.py` hand-parses
the subset of YAML the client files use rather than importing PyYAML, and the
web app is `http.server` rather than a framework. Adding ReportLab or WeasyPrint
to render a client report would make this the first thing in the project that
cannot be run by unzipping it and typing `py`, and a client report is not worth
that.

So this writes PDF 1.4 directly. It is deliberately small and covers exactly
what a business report needs:

  * text in the fourteen standard fonts, which every reader has built in, so
    nothing is embedded and the file stays tens of kilobytes
  * rules, filled rectangles and simple vector paths, which is enough for
    tables, bars and a cover
  * pages, with a running footer and page numbers

What it does not do: images, embedded fonts, transparency, forms, tagging. If
a report ever needs one of those, that is the moment to reconsider a library -
not before.

**Encoding.** The standard fonts are single-byte. `WinAnsiEncoding` covers
Latin-1 plus the common punctuation, which handles the European names this
system actually sees - Kowalski, Novák, Hörst, Bähr, Łukasz. Anything outside
it is transliterated where there is an obvious equivalent and replaced with
"?" where there is not, by `encode()`, rather than silently dropped or
crashing the report. A client report that renders a name wrong is bad; one
that fails to generate because somebody is called Ola Kowalczyk-Żuk is worse.
"""
import io
import re
import unicodedata
import zlib

# ---------------------------------------------------------------- geometry
#
# Points, because that is the PDF unit. A4 rather than Letter: the clients are
# European and so is the agency.

A4 = (595.28, 841.89)
MARGIN = 56.0            # ~20mm
CONTENT_TOP = 780.0
CONTENT_BOTTOM = 72.0

# The fourteen standard fonts need no embedding. Three are enough for a
# report, and using three rather than seven is what keeps it looking designed.
HELV = "Helvetica"
HELV_BOLD = "Helvetica-Bold"
HELV_OBLIQUE = "Helvetica-Oblique"
FONTS = (HELV, HELV_BOLD, HELV_OBLIQUE)


class PdfError(RuntimeError):
    pass


# ------------------------------------------------------------------ widths
#
# Helvetica advance widths, per 1000 units, for the printable WinAnsi range.
# Measuring text is what makes wrapping, centring and right-aligned numbers
# possible; without it every column is a guess and long company names run off
# the page. These are the published AFM values.

_HELV_WIDTHS = {
    32: 278, 33: 278, 34: 355, 35: 556, 36: 556, 37: 889, 38: 667, 39: 191,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 278, 59: 278, 60: 584, 61: 584, 62: 584, 63: 556,
    64: 1015, 65: 667, 66: 667, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 500, 75: 667, 76: 556, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 278, 92: 278, 93: 278, 94: 469, 95: 556,
    96: 333, 97: 556, 98: 556, 99: 500, 100: 556, 101: 556, 102: 278,
    103: 556, 104: 556, 105: 222, 106: 222, 107: 500, 108: 222, 109: 833,
    110: 556, 111: 556, 112: 556, 113: 556, 114: 333, 115: 500, 116: 278,
    117: 556, 118: 500, 119: 722, 120: 500, 121: 500, 122: 500, 123: 334,
    124: 260, 125: 334, 126: 584,
}
# Bold differs enough that using one table for both makes headers overflow.
_BOLD_WIDTHS = {
    32: 278, 33: 333, 34: 474, 35: 556, 36: 556, 37: 889, 38: 722, 39: 238,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 333, 59: 333, 60: 584, 61: 584, 62: 584, 63: 611,
    64: 975, 65: 722, 66: 722, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 556, 75: 722, 76: 611, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 333, 92: 278, 93: 333, 94: 584, 95: 556,
    96: 333, 97: 556, 98: 611, 99: 556, 100: 611, 101: 556, 102: 333,
    103: 611, 104: 611, 105: 278, 106: 278, 107: 556, 108: 278, 109: 889,
    110: 611, 111: 611, 112: 611, 113: 611, 114: 389, 115: 556, 116: 333,
    117: 611, 118: 556, 119: 778, 120: 556, 121: 556, 122: 500, 123: 389,
    124: 280, 125: 389, 126: 584,
}
_FALLBACK_WIDTH = 556


def width_of(text, font=HELV, size=10.0):
    """How wide this string renders, in points. The basis of every layout."""
    table = _BOLD_WIDTHS if font == HELV_BOLD else _HELV_WIDTHS
    total = 0
    for char in encode(text):
        total += table.get(char, _FALLBACK_WIDTH)
    return total * size / 1000.0


# ---------------------------------------------------------------- encoding

# Characters that have an obvious plain equivalent. Transliterating is better
# than "?" for every one of these: a reader seeing "Zuk" understands the name,
# and a reader seeing "?uk" thinks the report is broken.
_TRANSLITERATE = {
    "‘": "'", "’": "'", "‚": ",", "“": '"',
    "”": '"', "„": '"', "–": "-", "—": "-",
    "…": "...", "•": "-", " ": " ", "−": "-",
    "Ł": "L", "ł": "l", "Đ": "D", "đ": "d",
    "Š": "S", "š": "s", "Ž": "Z", "ž": "z",
    "Ć": "C", "ć": "c", "Č": "C", "č": "c",
    "€": "EUR", "£": "GBP",
}


def encode(text):
    """One string to WinAnsi bytes, losing as little meaning as possible.

    Three passes, in order of how much they cost the reader: the character as
    it is, then a decomposition that strips an accent the font cannot draw,
    then "?". Nothing here can raise - a report that will not generate because
    of one character in one company name is a worse outcome than a report with
    one imperfect character in it.
    """
    out = bytearray()
    for char in str(text if text is not None else ""):
        if char in _TRANSLITERATE:
            for part in _TRANSLITERATE[char]:
                out.extend(part.encode("cp1252", "replace"))
            continue
        try:
            out.extend(char.encode("cp1252"))
            continue
        except UnicodeEncodeError:
            pass
        # Strip the accent rather than lose the letter.
        stripped = "".join(
            c for c in unicodedata.normalize("NFD", char)
            if not unicodedata.combining(c))
        try:
            out.extend(stripped.encode("cp1252"))
        except UnicodeEncodeError:
            out.extend(b"?")
    return bytes(out)


def _escape(text):
    """PDF string literal escaping. Unbalanced parentheses corrupt a page."""
    return (encode(text).replace(b"\\", b"\\\\")
            .replace(b"(", b"\\(").replace(b")", b"\\)")
            .replace(b"\r", b"\\r"))


def wrap(text, width, font=HELV, size=10.0):
    """Greedy word wrap to a pixel width. Returns a list of lines.

    A word longer than the whole column - a URL, a German compound, a domain -
    is broken rather than allowed to run into the next column, because a table
    that overlaps is unreadable in a way that a hyphenless break is not.
    """
    words = re.split(r"\s+", str(text or "").strip())
    lines, current = [], ""
    for word in [w for w in words if w]:
        candidate = f"{current} {word}".strip()
        if width_of(candidate, font, size) <= width or not current:
            if width_of(candidate, font, size) > width and not current:
                # One word, too wide on its own.
                piece = ""
                for char in candidate:
                    if width_of(piece + char, font, size) > width and piece:
                        lines.append(piece)
                        piece = char
                    else:
                        piece += char
                current = piece
                continue
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def truncate(text, width, font=HELV, size=10.0):
    """One line, cut with an ellipsis rather than allowed to overflow."""
    text = str(text if text is not None else "")
    if width_of(text, font, size) <= width:
        return text
    ellipsis = "..."
    budget = width - width_of(ellipsis, font, size)
    out = ""
    for char in text:
        if width_of(out + char, font, size) > budget:
            break
        out += char
    return (out.rstrip() + ellipsis) if out else ellipsis


# ------------------------------------------------------------------- canvas

class Page:
    """One page's content stream, built up as drawing operators."""

    def __init__(self, size=A4):
        self.size = size
        self.ops = bytearray()

    # -- text

    def text(self, x, y, string, font=HELV, size=10.0, colour=(0, 0, 0)):
        r, g, b = colour
        self.ops.extend(
            b"BT /%s %.2f Tf %.3f %.3f %.3f rg %.2f %.2f Td (%s) Tj ET\n"
            % (font.replace("-", "#2D").encode("ascii"), size, r, g, b,
               x, y, _escape(string)))
        return self

    def text_right(self, right, y, string, font=HELV, size=10.0,
                   colour=(0, 0, 0)):
        """Right-aligned. Numbers in a column that do not line up are noise."""
        return self.text(right - width_of(string, font, size), y, string,
                         font, size, colour)

    def text_centre(self, centre, y, string, font=HELV, size=10.0,
                    colour=(0, 0, 0)):
        return self.text(centre - width_of(string, font, size) / 2.0, y,
                         string, font, size, colour)

    # -- shapes

    def rect(self, x, y, w, h, colour=(0, 0, 0), fill=True, line_width=0.6):
        r, g, b = colour
        if fill:
            self.ops.extend(b"%.3f %.3f %.3f rg %.2f %.2f %.2f %.2f re f\n"
                            % (r, g, b, x, y, w, h))
        else:
            self.ops.extend(
                b"%.3f %.3f %.3f RG %.2f w %.2f %.2f %.2f %.2f re S\n"
                % (r, g, b, line_width, x, y, w, h))
        return self

    def line(self, x1, y1, x2, y2, colour=(0.8, 0.8, 0.8), width=0.6):
        r, g, b = colour
        self.ops.extend(
            b"%.3f %.3f %.3f RG %.2f w %.2f %.2f m %.2f %.2f l S\n"
            % (r, g, b, width, x1, y1, x2, y2))
        return self

    def stream(self):
        return bytes(self.ops)


class Document:
    """Pages, and the object table that turns them into a file."""

    def __init__(self, title="Report", author="Resonate Group",
                 subject="", size=A4):
        self.title = title
        self.author = author
        self.subject = subject
        self.size = size
        self.pages = []

    def page(self):
        page = Page(self.size)
        self.pages.append(page)
        return page

    def render(self):
        """The whole file as bytes. Deterministic: same input, same output.

        No creation date is written. Two reports over the same period with the
        same data produce byte-identical files, which is what makes "did this
        change?" answerable by comparing them - and which a timestamp in the
        trailer would quietly destroy.
        """
        if not self.pages:
            raise PdfError("a document with no pages is not a document")

        objects = []                    # 1-indexed on output

        def add(body):
            objects.append(body)
            return len(objects)

        font_ids = {}
        for name in FONTS:
            font_ids[name] = add(
                b"<< /Type /Font /Subtype /Type1 /BaseFont /%s "
                b"/Encoding /WinAnsiEncoding >>"
                % name.replace("-", "#2D").encode("ascii"))

        resources = ("<< /Font << " + " ".join(
            f"/{n.replace('-', '#2D')} {font_ids[n]} 0 R" for n in FONTS)
            + " >> >>").encode("ascii")

        pages_id = len(objects) + 1 + 2 * len(self.pages)
        page_ids = []
        for page in self.pages:
            raw = page.stream()
            packed = zlib.compress(raw, 9)
            content_id = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n"
                             % len(packed) + packed + b"\nendstream")
            page_ids.append(add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] "
                b"/Resources %s /Contents %d 0 R >>"
                % (pages_id, page.size[0], page.size[1], resources,
                   content_id)))

        kids = b" ".join(b"%d 0 R" % i for i in page_ids)
        pages_obj = add(b"<< /Type /Pages /Count %d /Kids [%s] >>"
                        % (len(page_ids), kids))
        if pages_obj != pages_id:                       # pragma: no cover
            raise PdfError("page tree id drifted; the object order changed")

        info_id = add(b"<< /Title (%s) /Author (%s) /Subject (%s) "
                      b"/Producer (Resonate Outbound OS) >>"
                      % (_escape(self.title), _escape(self.author),
                         _escape(self.subject)))
        catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj)

        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(objects, start=1):
            offsets.append(out.tell())
            out.write(b"%d 0 obj\n" % number)
            out.write(body)
            out.write(b"\nendobj\n")

        xref_at = out.tell()
        out.write(b"xref\n0 %d\n" % (len(objects) + 1))
        out.write(b"0000000000 65535 f \n")
        for offset in offsets:
            out.write(b"%010d 00000 n \n" % offset)
        out.write(b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\n"
                  % (len(objects) + 1, catalog_id, info_id))
        out.write(b"startxref\n%d\n%%%%EOF\n" % xref_at)
        return out.getvalue()
