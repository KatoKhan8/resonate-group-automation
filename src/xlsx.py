#!/usr/bin/env python3
"""A one-sheet .xlsx, written with the standard library and nothing else.

    from src import xlsx
    xlsx.write(path, header, rows, widths={"email": 34})

## WHY THIS EXISTS RATHER THAN `import openpyxl`

`requirements.txt` declares no packages, and
`test_deployment_config.TestRequirements` checks BOTH halves of that claim:
that the file lists nothing, and that every import under `src/` is stdlib
or local. The first draft of `src/reviewfile.py` imported openpyxl and
turned that test red, which is the test doing its job - DEPLOYMENT-PLAN.md
1 calls the zero-dependency claim the deployment's biggest advantage, and a
review file is not a reason to spend it.

The operator asked for `.xlsx` and meant it: 333 leads by 3 steps of full
email bodies is not a CSV anybody opens twice. So this writes one. It is
the same trade the repository has already made twice - there is a
hand-written PDF writer and a hand-written DNS client in here for exactly
this reason.

## WHAT AN XLSX ACTUALLY IS

A ZIP of XML. Six members, all of them small:

    [Content_Types].xml         what each part is
    _rels/.rels                 the workbook is the root
    xl/workbook.xml             one sheet, named
    xl/_rels/workbook.xml.rels  where the sheet and the styles live
    xl/styles.xml               two formats: bold header, wrapped body
    xl/worksheets/sheet1.xml    the cells

THE ELEMENT ORDER INSIDE A WORKSHEET IS PART OF THE SCHEMA, not a
preference: `sheetViews` before `cols` before `sheetData`. Written the
other way round the file is a valid ZIP full of well-formed XML that Excel
refuses to open, which is the most annoying possible way to be wrong.

## EVERY CELL IS A STRING, AND THAT IS DELIBERATE

`t="inlineStr"` puts the text in the cell rather than in a shared-strings
table. A shared-strings table is smaller on a file with much repetition and
is a second index to keep consistent with the sheet; these files are read
once by a person and correctness matters more than bytes.

More importantly it means NOTHING IS PARSED AS A NUMBER OR A DATE. A lead
id, a date-shaped string and a company called `2026` all arrive as the
characters they are. Excel's type inference is a known way to silently
change data on import, and a review file that quietly rewrites what the
provider holds is the exact failure this lane exists about.

Callers still pass every value through `export.safe_cell` first, which is
what stops a leading `=` from being a formula - `src/export.py` says why at
length. This module does not do it for them: one guard, one place.
"""
import os
import zipfile

#: The ranges XML 1.0 permits: tab, newline, carriage return, and then
#: three contiguous blocks. Everything else - a NUL, a stray C0 control, an
#: unpaired surrogate - cannot be represented at all, and a provider
#: payload has carried one before now.
#:
#: Written as ranges over code points rather than as a regex character
#: class because the class has to be spelled with escapes, and an escape
#: that is written literally instead produces a pattern containing a real
#: tab - which still compiles, still matches something, and is wrong in a
#: way nothing would report.
_XML_RANGES = ((0x09, 0x09), (0x0A, 0x0A), (0x0D, 0x0D),
               (0x20, 0xD7FF), (0xE000, 0xFFFD), (0x10000, 0x10FFFF))


def _is_xml_char(char):
    point = ord(char)
    return any(low <= point <= high for low, high in _XML_RANGES)


def escape(value):
    """One value as XML text: illegal characters dropped, markup escaped."""
    text = "".join(c for c in str("" if value is None else value)
                   if _is_xml_char(c))
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def column_letter(index):
    """1 -> A, 26 -> Z, 27 -> AA. One-based, as the format is."""
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

#: Three cell formats. `s="1"` is the bold header; `s="2"` wraps and aligns
#: to the top, which is what makes a 400-word email body readable in a row.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""

HEADER_STYLE = 1
BODY_STYLE = 2


def _row(number, values, style):
    cells = ['<row r="%d">' % number]
    for index, value in enumerate(values, start=1):
        text = escape(value)
        if not text:
            continue
        cells.append('<c r="%s%d" s="%d" t="inlineStr">'
                     '<is><t xml:space="preserve">%s</t></is></c>'
                     % (column_letter(index), number, style, text))
    cells.append("</row>")
    return "".join(cells)


def sheet_xml(header, rows, widths=None, freeze_header=True):
    """The worksheet part, in schema order. Public so a test can read it."""
    widths = widths or {}
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/'
           'spreadsheetml/2006/main">',
           '<sheetViews><sheetView workbookViewId="0">']
    if freeze_header:
        out.append('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft"'
                   ' state="frozen"/>')
    out.append("</sheetView></sheetViews>")
    columns = [(index, widths.get(name))
               for index, name in enumerate(header, start=1)
               if widths.get(name)]
    if columns:
        out.append("<cols>")
        for index, width in columns:
            out.append('<col min="%d" max="%d" width="%g" customWidth="1"/>'
                       % (index, index, float(width)))
        out.append("</cols>")
    out.append("<sheetData>")
    out.append(_row(1, header, HEADER_STYLE))
    for number, values in enumerate(rows, start=2):
        out.append(_row(number, values, BODY_STYLE))
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write(path, header, rows, widths=None, sheet_name="Sheet1",
          freeze_header=True):
    """One sheet, header row first. Returns `path`.

    `widths` maps a HEADER NAME to a column width, so a caller names the
    column rather than counting to it - a positional list silently shifts
    every width the day a column is inserted in the middle.
    """
    header = [str(h) for h in header]
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", _CONTENT_TYPES)
        book.writestr("_rels/.rels", _RELS)
        book.writestr("xl/workbook.xml",
                      _WORKBOOK % escape(sheet_name)[:31])
        book.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        book.writestr("xl/styles.xml", _STYLES)
        book.writestr("xl/worksheets/sheet1.xml",
                      sheet_xml(header, rows, widths, freeze_header))
    return path
