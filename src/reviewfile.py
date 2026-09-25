"""The operator's review file: what a person reads before approving a campaign.

TASK-301 column spec, standing for EVERY review file:

    sender mailbox | sender name | lead email | name | title | company
    cohort tag | persona
    each email step: subject + FULL BODY exactly as the provider will send it
    LinkedIn connection note and follow-ups, where a profile exists
    PERSONALISATION BLOCK:
        source URL | retrieved date | the exact snippet | USED or NOT USED
        for a USED fact: WHICH SENTENCE of the copy it feeds

WHY THIS IS NOT `src/render.py`. That module renders a batch review for the
operator to inspect before a push. This module builds the ACTIVATION review
file: the thing the operator approves by hash before a campaign goes live.
The column spec is different (sender mailbox, personalisation block, LinkedIn
side-by-side), the audience is different (the operator, not the engineer),
and the hash gates activation through `reviewapproval.require`.

WHY THE DATA COMES FROM THE PROVIDER, NOT FROM OUR CSV. The incident was
that our CSV said one thing and the provider sent another. A review file
built from what we intended to send certifies our intent, which is not the
thing that failed. So the body text is READ BACK from the provider after
the variables are written, not rendered locally.

THREE STEPS, NOT FIVE. Campaigns 491-498 hold three email steps each. That
is legitimate (TASK-296): they were built before the five-step cadence
arrived. The file renders three steps and says so, rather than inventing
two more to match a different campaign's shape.
"""
import csv
import hashlib
import html
import io
import json
import os
import re
import zipfile

from . import reviewapproval


# --------------------------------------------------------- column spec
#
# The operator's standing spec from TASK-301. Every review file carries
# these columns in this order. A column added here is added to every file;
# a column removed is removed from every file.

BASE_COLUMNS = (
    "sender_mailbox",
    "sender_name",
    "lead_email",
    "name",
    "title",
    "company",
    "cohort_tag",
    "persona",
)

# LinkedIn columns, present where a profile exists.
LINKEDIN_COLUMNS = (
    "linkedin_profile_url",
    "linkedin_connection_note",
    "linkedin_followup_1",
    "linkedin_followup_2",
)

# The personalisation block columns.
PACK_COLUMNS = (
    "pack_source_url",
    "pack_retrieved_at",
    "pack_snippet",
    "pack_used",
    "pack_feeds_sentence",
)


def step_columns(n_steps):
    """Subject + body for each email step, named by position."""
    cols = []
    for i in range(1, n_steps + 1):
        cols.append(f"step_{i}_subject")
        cols.append(f"step_{i}_body")
    return cols


def all_columns(n_steps, has_linkedin=False):
    """The full column list for the review file."""
    cols = list(BASE_COLUMNS)
    cols.extend(step_columns(n_steps))
    if has_linkedin:
        cols.extend(LINKEDIN_COLUMNS)
    cols.extend(PACK_COLUMNS)
    return cols


# --------------------------------------------------------- data shape

class ReviewRow:
    """One lead's row in the review file.

    Built from the provider readback, not from local render. The body text
    is what the provider will send, read back after variable write.
    """

    def __init__(self, *, sender_mailbox, sender_name, lead_email, name,
                 title, company, cohort_tag, persona, steps,
                 linkedin=None, pack_facts=None):
        self.sender_mailbox = sender_mailbox
        self.sender_name = sender_name
        self.lead_email = lead_email
        self.name = name
        self.title = title
        self.company = company
        self.cohort_tag = cohort_tag
        self.persona = persona
        self.steps = steps
        self.linkedin = linkedin or {}
        self.pack_facts = pack_facts or []

    def as_dict(self, n_steps, has_linkedin=False):
        """Flat dict keyed by column name, for CSV/XLSX writing."""
        row = {
            "sender_mailbox": self.sender_mailbox,
            "sender_name": self.sender_name,
            "lead_email": self.lead_email,
            "name": self.name,
            "title": self.title,
            "company": self.company,
            "cohort_tag": self.cohort_tag,
            "persona": self.persona,
        }
        for i, step in enumerate(self.steps, start=1):
            row[f"step_{i}_subject"] = step.get("subject", "")
            row[f"step_{i}_body"] = step.get("body", "")
        if has_linkedin and self.linkedin:
            row["linkedin_profile_url"] = self.linkedin.get("profile_url", "")
            row["linkedin_connection_note"] = self.linkedin.get(
                "connection_note", "")
            row["linkedin_followup_1"] = self.linkedin.get("followup_1", "")
            row["linkedin_followup_2"] = self.linkedin.get("followup_2", "")
        elif has_linkedin:
            for col in LINKEDIN_COLUMNS:
                row[col] = ""
        # Personalisation block: one row per pack fact, but the FIRST row
        # carries the lead data. Additional facts expand to additional rows
        # in the final output (see expand_pack_rows below).
        if self.pack_facts:
            first = self.pack_facts[0]
            row["pack_source_url"] = first.get("source_url", "")
            row["pack_retrieved_at"] = first.get("retrieved_at", "")
            row["pack_snippet"] = first.get("snippet", "")
            row["pack_used"] = first.get("used", "NOT USED")
            row["pack_feeds_sentence"] = first.get("feeds_sentence", "")
        else:
            for col in PACK_COLUMNS:
                row[col] = ""
        return row


def expand_pack_rows(base_row, pack_facts, n_steps, has_linkedin=False):
    """One lead with N pack facts becomes N rows, all sharing lead columns.

    The first row carries the lead data AND the first fact. Additional rows
    repeat the lead columns (so the file is readable as a flat table) and
    carry one additional fact each. This is what makes the NOT USED facts
    visible alongside the USED one.
    """
    if not pack_facts:
        return [base_row]
    rows = []
    for i, fact in enumerate(pack_facts):
        if i == 0:
            rows.append(base_row)
        else:
            dup = {col: "" for col in all_columns(n_steps, has_linkedin)}
            dup["sender_mailbox"] = base_row.get("sender_mailbox", "")
            dup["lead_email"] = base_row.get("lead_email", "")
            dup["company"] = base_row.get("company", "")
            dup["pack_source_url"] = fact.get("source_url", "")
            dup["pack_retrieved_at"] = fact.get("retrieved_at", "")
            dup["pack_snippet"] = fact.get("snippet", "")
            dup["pack_used"] = fact.get("used", "NOT USED")
            dup["pack_feeds_sentence"] = fact.get("feeds_sentence", "")
            rows.append(dup)
    return rows


# --------------------------------------------------------- HTML output

_HTML_STYLE = """
:root{--bg:#0E1116;--card:#161B22;--line:#232A33;--fg:#E9EEF3;--mut:#93A1AF;
--acc:#4DD0B1;--bad:#FF7B72;--warn:#E3B341}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}
.wrap{max-width:1400px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:24px 0 8px}
.meta{color:var(--mut);margin-bottom:24px;font-size:13px}
.meta b{color:var(--fg)}
.hash{font-family:monospace;background:var(--card);padding:4px 8px;border-radius:4px;border:1px solid var(--line)}
table{width:100%;border-collapse:collapse;margin-bottom:24px;font-size:12px}
th{background:var(--card);color:var(--acc);text-align:left;padding:8px;border:1px solid var(--line);position:sticky;top:0;white-space:nowrap}
td{padding:6px 8px;border:1px solid var(--line);vertical-align:top;max-width:400px;overflow-wrap:break-word}
tr:nth-child(even){background:rgba(255,255,255,0.02)}
tr.pack-not-used td{opacity:0.6}
.step-body{white-space:pre-wrap;font-family:inherit;max-width:380px}
.pack-snippet{font-style:italic;color:var(--mut);max-width:300px}
.pack-used{font-weight:600}
.pack-used.YES{color:var(--acc)}
.pack-used.NO{color:var(--warn)}
.lead-sep{border-top:2px solid var(--acc)}
.li-col{background:rgba(77,208,177,0.05)}
footer{margin-top:16px;color:var(--mut);font-size:12px}
"""


def _esc(text):
    return html.escape(str(text or ""), quote=True)


def to_html(rows, campaign_id, file_hash, n_steps, has_linkedin=False,
            sender_pool=None):
    """The review file as a self-contained HTML page."""
    columns = all_columns(n_steps, has_linkedin)
    header_cells = "".join(f"<th>{_esc(c)}</th>" for c in columns)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{_esc(row.get(c, ''))}</td>" for c in columns)
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        "<!doctype html><meta charset=utf-8>\n"
        "<title>Review file: campaign %s</title>\n"
        "<style>%s</style>\n"
        "<div class=wrap>\n"
        "<h1>Review file &mdash; campaign %s</h1>\n"
        '<div class=meta><b>%d</b> leads &middot; <b>%d</b> email steps '
        "&middot; hash <span class=hash>%s</span></div>\n"
        "<table>\n<thead><tr>%s</tr></thead>\n<tbody>\n%s\n</tbody>\n"
        "</table>\n"
        "<footer>Generated for operator approval. "
        "Activate only after APPROVED %s &lt;hash&gt;.</footer>\n"
        "</div>\n"
    ) % (campaign_id, _HTML_STYLE, campaign_id, len(rows), n_steps,
         file_hash, header_cells, "\n".join(body_rows), campaign_id)


# --------------------------------------------------------- XLSX output
#
# Zero third-party dependencies. An xlsx is a zip of XML files. This writer
# emits the minimum set of parts Excel and LibreOffice both read.

_XL_CONTENT_TYPES = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
  <Override PartName="/xl/styles.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

_XL_RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="xl/workbook.xml"/>
</Relationships>"""

_XL_WORKBOOK = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Review" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

_XL_WORKBOOK_RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
    Target="sharedStrings.xml"/>
  <Relationship Id="rId3"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    Target="styles.xml"/>
</Relationships>"""

_XL_STYLES = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="2">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
  </fills>
  <borders count="1"><border/></border>
  <cellStyleXfs count="1"><xf/></cellStyleXfs>
  <cellXfs count="1"><xf/></cellXfs>
</styleSheet>"""


def _col_letter(index):
    """Zero-based column index to Excel column letter(s)."""
    result = ""
    while True:
        result = chr(65 + index % 26) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def _cell_ref(row, col):
    """1-based row, 0-based col to cell reference like A1."""
    return f"{_col_letter(col)}{row}"


def _xml_escape(text):
    """Escape for XML content."""
    return (str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "&#10;"))


def to_xlsx(rows, columns):
    """The review file as xlsx bytes.

    All cell values go through the shared strings table, which is the
    standard approach for text-heavy workbooks. Numeric conversion is
    deliberately absent: every value in a review file is text.
    """
    strings = []
    string_index = {}

    def _si(text):
        s = str(text or "")
        if s not in string_index:
            string_index[s] = len(strings)
            strings.append(s)
        return string_index[s]

    # Pre-index all strings: column headers first, then cell values.
    _si("")  # index 0 is the empty string
    for col_name in columns:
        _si(col_name)
    for row in rows:
        for col in columns:
            _si(row.get(col, ""))

    # Build shared strings XML.
    si_parts = []
    for s in strings:
        si_parts.append(f"<si><t>{_xml_escape(s)}</t></si>")
    shared_strings = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        f' count="{len(strings)}" uniqueCount="{len(strings)}">\n'
        + "\n".join(si_parts)
        + "\n</sst>"
    )

    # Build worksheet XML.
    sheet_parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    # Header row.
    sheet_parts.append('<row r="1">')
    for ci, col_name in enumerate(columns):
        ref = _cell_ref(1, ci)
        sheet_parts.append(
            f'<c r="{ref}" t="s"><v>{_si(col_name)}</v></c>')
    sheet_parts.append("</row>")
    # Data rows.
    for ri, row in enumerate(rows, start=2):
        sheet_parts.append(f'<row r="{ri}">')
        for ci, col_name in enumerate(columns):
            ref = _cell_ref(ri, ci)
            val = row.get(col_name, "")
            sheet_parts.append(
                f'<c r="{ref}" t="s"><v>{_si(val)}</v></c>')
        sheet_parts.append("</row>")
    sheet_parts.append("</sheetData>")
    sheet_parts.append("</worksheet>")
    sheet_xml = "\n".join(sheet_parts)

    # Assemble the zip.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _XL_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _XL_RELS)
        zf.writestr("xl/workbook.xml", _XL_WORKBOOK)
        zf.writestr("xl/_rels/workbook.xml.rels", _XL_WORKBOOK_RELS)
        zf.writestr("xl/styles.xml", _XL_STYLES)
        zf.writestr("xl/sharedStrings.xml", shared_strings)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


# --------------------------------------------------------- CSV output

def to_csv(rows, columns):
    """The review file as CSV text. Guarded against formula execution."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        guarded = {}
        for k, v in row.items():
            s = str(v or "")
            if s and s[0] in ("=", "+", "-", "@"):
                s = "'" + s
            guarded[k] = s
        writer.writerow(guarded)
    return buf.getvalue()


# --------------------------------------------------------- file hash

def compute_hash(content_bytes):
    """sha256, first 16 hex chars. Same as `reviewapproval.file_hash`."""
    return reviewapproval.file_hash(content_bytes)


# --------------------------------------------------------- assembly

def build(campaign_id, leads, *, n_steps=3, has_linkedin=False):
    """Assemble the review file rows from provider readback data.

    `leads` is a list of dicts, each carrying:
      - sender_mailbox, sender_name
      - lead_email, name, title, company
      - cohort_tag, persona
      - steps: [{subject, body}, ...] - READ BACK FROM PROVIDER
      - linkedin: {profile_url, connection_note, followup_1, followup_2}
      - pack_facts: [{source_url, retrieved_at, snippet, used, feeds_sentence}]

    Returns (rows, columns, html_content, xlsx_content, file_hash).
    The hash is computed over the xlsx content, which is what gets posted.
    """
    columns = all_columns(n_steps, has_linkedin)
    flat_rows = []
    for lead in leads:
        row_obj = ReviewRow(**lead)
        base = row_obj.as_dict(n_steps, has_linkedin)
        expanded = expand_pack_rows(base, lead.get("pack_facts") or [],
                                    n_steps, has_linkedin)
        flat_rows.extend(expanded)

    xlsx_content = to_xlsx(flat_rows, columns)
    html_content = to_html(flat_rows, campaign_id,
                           compute_hash(xlsx_content), n_steps,
                           has_linkedin)
    csv_content = to_csv(flat_rows, columns)
    file_hash = compute_hash(xlsx_content)

    return {
        "campaign_id": str(campaign_id),
        "columns": columns,
        "rows": flat_rows,
        "lead_count": len(leads),
        "n_steps": n_steps,
        "has_linkedin": has_linkedin,
        "xlsx": xlsx_content,
        "html": html_content,
        "csv": csv_content,
        "file_hash": file_hash,
    }


def write(result, directory):
    """Write the review file pair to disk. Returns (xlsx_path, html_path)."""
    os.makedirs(directory, exist_ok=True)
    cid = result["campaign_id"]
    xlsx_path = os.path.join(directory, f"{cid}-review.xlsx")
    html_path = os.path.join(directory, f"{cid}-review.html")
    csv_path = os.path.join(directory, f"{cid}-review.csv")
    with open(xlsx_path, "wb") as f:
        f.write(result["xlsx"])
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(result["html"])
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(result["csv"])
    return xlsx_path, html_path, csv_path
