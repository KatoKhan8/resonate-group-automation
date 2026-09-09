#!/usr/bin/env python3
"""Enough of XLSX to read a lead list, and nothing else.

## Why this exists at all

"Save it as CSV first" is friction on every import, and the client who has
to do it is the one whose list we most want. An `.xlsx` is a zip of XML and
both are in the standard library, so the dependency this build refuses to
take is not actually required - only the care is.

## What it reads

The first worksheet, as text. Shared strings, inline strings, and numbers
rendered as they are stored. That covers a lead list, which is columns of
domains, addresses, names and titles.

## What it does not

**A date is returned as the number the file stores.** Excel keeps dates as
a serial number and the format lives somewhere this does not read, so a
date column arrives as `45678`. No canonical column is a date - see
`columns.CANONICAL` - so the worst case is a provenance column carrying a
number, and it is written down here rather than discovered.

**One sheet.** The first one in the workbook. A file whose leads are on the
second tab imports the first tab, which is why `sheet_name` comes back with
the rows: the preview says which one it read.

**No formulas.** A cell's cached value is read; a formula is not evaluated
and is not returned as text. The CSV path's formula guard still runs on
everything this produces, because a cached value can still start with `=`.

## The guards, and why each is here

A zip from outside is an attack surface before it is a spreadsheet:

- **A declared uncompressed size over `MAX_UNPACKED`** is refused without
  reading a byte of it. That is the zip bomb: a few kilobytes that expand
  to gigabytes.
- **More than `MAX_ENTRIES` members** is refused. A zip with a hundred
  thousand tiny entries costs nothing to send and a great deal to walk.
- **A DOCTYPE anywhere in the XML** is refused before parsing. That is
  entity expansion - the billion laughs - and refusing the declaration is
  simpler to be sure of than configuring a parser not to honour it.
- **Every member is read with a bounded read**, not `read()`, so a member
  that lies about its size cannot be believed twice.
"""
import io
import re
import xml.etree.ElementTree as ET
import zipfile

# The bytes every zip starts with. Checked before anything else so a CSV
# that happens to contain the word "xlsx" is never routed here.
MAGIC = b"PK\x03\x04"

# Bounds. Generous for a lead list and small enough that a hostile file
# cannot cost anything: 60 MB unpacked is roughly a quarter of a million
# rows of text.
MAX_UNPACKED = 60 * 1024 * 1024
MAX_ENTRIES = 512
MAX_ROWS = 200_000
MAX_COLUMNS = 512

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# `A`, `AB12`, `ZZ9`. The letters are the column; the digits are the row.
CELL_REF = re.compile(r"^([A-Z]+)")

DOCTYPE = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.I)


class NotAWorkbook(ValueError):
    """The bytes are not an xlsx this can read, and the message says why."""


def looks_like_xlsx(data):
    """Cheap enough to run on every upload before anything else."""
    return bool(data) and data[:4] == MAGIC


def _member(archive, name):
    """One member, read under a cap rather than trusted about its size."""
    info = archive.getinfo(name)
    if info.file_size > MAX_UNPACKED:
        raise NotAWorkbook(
            f"{name} unpacks to more than "
            f"{MAX_UNPACKED // (1024 * 1024)} MB")
    with archive.open(info) as handle:
        raw = handle.read(MAX_UNPACKED + 1)
    if len(raw) > MAX_UNPACKED:
        raise NotAWorkbook(f"{name} is larger than it declared")
    if DOCTYPE.search(raw):
        raise NotAWorkbook(
            "this file declares an XML entity, which this reader refuses "
            "rather than expanding")
    return raw


def _column(reference):
    """`AB12` -> 27. Zero-based, so it indexes a row directly."""
    match = CELL_REF.match(str(reference or "").upper())
    if not match:
        return None
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - 64)
    return index - 1


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(_member(archive, "xl/sharedStrings.xml"))
    out = []
    for item in root.findall(f"{NS}si"):
        # A string can be one run or several - "Acme" and "Ac"+"me" are the
        # same string to a reader and different elements in the file.
        out.append("".join(node.text or ""
                           for node in item.iter(f"{NS}t")))
    return out


def _first_sheet(archive):
    """The first worksheet's path and the name a person would recognise."""
    names = archive.namelist()
    label = None
    if "xl/workbook.xml" in names:
        root = ET.fromstring(_member(archive, "xl/workbook.xml"))
        first = root.find(f"{NS}sheets/{NS}sheet")
        if first is not None:
            label = first.get("name")
    sheets = sorted(n for n in names
                    if n.startswith("xl/worksheets/sheet") and
                    n.endswith(".xml"))
    if not sheets:
        raise NotAWorkbook("this workbook has no worksheet")
    return sheets[0], label


def rows(data):
    """Every row of the first sheet, as a list of lists of strings.

    Short rows are padded to the width of the widest one, because a
    trailing empty cell is not stored at all and a caller comparing row
    length to header length would call every such row ragged.
    """
    if not looks_like_xlsx(data):
        raise NotAWorkbook("this is not a zip, so it is not an xlsx")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise NotAWorkbook(f"this file is not a readable zip: {e}") from None

    with archive:
        names = archive.namelist()
        if len(names) > MAX_ENTRIES:
            raise NotAWorkbook(
                f"this file has {len(names)} members, more than the "
                f"{MAX_ENTRIES} an xlsx needs")
        declared = sum(archive.getinfo(n).file_size for n in names)
        if declared > MAX_UNPACKED:
            raise NotAWorkbook(
                f"this file unpacks to more than "
                f"{MAX_UNPACKED // (1024 * 1024)} MB")

        shared = _shared_strings(archive)
        path, sheet_name = _first_sheet(archive)
        root = ET.fromstring(_member(archive, path))

        out = []
        widest = 0
        for row in root.iter(f"{NS}row"):
            if len(out) >= MAX_ROWS:
                raise NotAWorkbook(f"more than {MAX_ROWS} rows")
            cells = {}
            for cell in row.findall(f"{NS}c"):
                index = _column(cell.get("r"))
                if index is None:
                    continue
                if index >= MAX_COLUMNS:
                    # Refused, not dropped.
                    #
                    # This was a `continue`, so a sheet wider than the cap
                    # came back silently truncated: a `Work Email` column at
                    # position 514 simply was not there, and `upload.parse`
                    # then reported a clean import - rows counted, nothing
                    # excluded, nothing ragged - of a file that had lost two
                    # columns. Every other bound in this path refuses or
                    # reports; this was the one place meaningful data went
                    # missing with no reason recorded anywhere.
                    raise NotAWorkbook(
                        f"more than {MAX_COLUMNS} columns: this sheet is "
                        f"wider than the importer will read, and reading part "
                        f"of it would drop columns without saying so")
                cells[index] = _text(cell, shared)
            widest = max(widest, (max(cells) + 1) if cells else 0)
            out.append(cells)

    return ([[row.get(i, "") for i in range(widest)] for row in out],
            sheet_name)


def _text(cell, shared):
    """One cell as the text a person would see, or as close as this gets."""
    kind = cell.get("t")
    if kind == "s":                                   # a shared string
        value = cell.findtext(f"{NS}v")
        try:
            return shared[int(value)]
        except (TypeError, ValueError, IndexError):
            return ""
    if kind == "inlineStr":
        node = cell.find(f"{NS}is")
        return "".join(t.text or "" for t in node.iter(f"{NS}t")) if node is not None else ""
    # Everything else - numbers, booleans, dates, and a formula's cached
    # result - is whatever `v` holds. A date is a serial number here; see
    # the module docstring.
    return cell.findtext(f"{NS}v") or ""
