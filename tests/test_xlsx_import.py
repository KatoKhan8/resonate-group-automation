"""Reading the file a client actually works in.

"Save it as CSV first" was friction on every import, and the client who has
to do it is the one whose list we most want. An `.xlsx` is a zip of XML and
both are in the standard library, so the dependency this build refuses to
take was never actually required - only the care was.

The care is most of this file. A zip from outside is an attack surface
before it is a spreadsheet, and a partial reader that silently misreads a
column is worse than a clear refusal - so the limits are asserted as
loudly as the happy path, and the one thing that *is* misread is written
down rather than left to be discovered.

The workbook is converted to the same bytes a CSV arrives as, and
everything downstream - the alias table, the formula guard, the hygiene
screen, the ragged-row report - then applies to a spreadsheet exactly as it
applies to an export. One parser for the file, one for the shape.
"""
import io
import unittest
import zipfile

from src.web import upload, xlsx

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def workbook(rows, sheet="Leads", extra=None, shared=True):
    """A minimal but real xlsx: workbook, shared strings, one sheet."""
    buf = io.BytesIO()
    strings = []

    def cell(ref, value):
        if shared:
            if value not in strings:
                strings.append(value)
            return f'<c r="{ref}" t="s"><v>{strings.index(value)}</v></c>'
        return (f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')

    body = ""
    for r, row in enumerate(rows, start=1):
        body += ('<row r="%d">' % r) + "".join(
            cell(chr(65 + c) + str(r), value)
            for c, value in enumerate(row)) + "</row>"

    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{SHEET_NS}"><sheets>'
            f'<sheet name="{sheet}"/></sheets></workbook>')
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{SHEET_NS}">'
            + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        extra = dict(extra or {})
        if "xl/worksheets/sheet1.xml" not in extra:
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                f'<worksheet xmlns="{SHEET_NS}"><sheetData>{body}</sheetData>'
                "</worksheet>")
        for name, content in extra.items():
            archive.writestr(name, content)
    return buf.getvalue()


class WhatItReads(unittest.TestCase):

    def test_a_sheet_of_text(self):
        grid, name = xlsx.rows(workbook([["Company Website", "Work Email"],
                                         ["acme.test", "a@acme.test"]]))
        self.assertEqual(grid, [["Company Website", "Work Email"],
                                ["acme.test", "a@acme.test"]])
        self.assertEqual(name, "Leads")

    def test_an_inline_string_reads_the_same_as_a_shared_one(self):
        grid, _ = xlsx.rows(workbook([["domain"], ["acme.test"]],
                                     shared=False))
        self.assertEqual(grid, [["domain"], ["acme.test"]])

    def test_a_short_row_is_padded_rather_than_called_ragged(self):
        """A trailing empty cell is not stored at all, so a caller
        comparing row length to header length would call every such row
        malformed."""
        grid, _ = xlsx.rows(workbook([["domain", "email"], ["acme.test"]]))
        self.assertEqual(grid[1], ["acme.test", ""])

    def test_the_sheet_it_read_comes_back_with_the_rows(self):
        """A workbook whose leads are on the second tab imports the first
        one, and being told which is the only way to notice."""
        _, name = xlsx.rows(workbook([["domain"]], sheet="Sheet1"))
        self.assertEqual(name, "Sheet1")


class WhatItRefuses(unittest.TestCase):

    def test_a_csv_is_not_routed_here(self):
        """And the refusal says which of the two problems it is. "Not a
        zip" sends somebody to look at the file they uploaded; "not a
        readable zip" sends them to look at whatever wrote it."""
        self.assertFalse(xlsx.looks_like_xlsx(b"domain,email\nacme.test,x\n"))
        with self.assertRaises(xlsx.NotAWorkbook) as caught:
            xlsx.rows(b"domain,email\n")
        self.assertIn("so it is not an xlsx", str(caught.exception))

    def test_a_zip_that_is_not_a_workbook(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("readme.txt", "hello")
        with self.assertRaises(xlsx.NotAWorkbook):
            xlsx.rows(buf.getvalue())

    def test_a_declared_entity_is_refused_before_it_is_parsed(self):
        """Entity expansion - the billion laughs. Refusing the declaration
        is simpler to be sure of than configuring a parser not to honour
        it."""
        bomb = ('<!DOCTYPE lolz [<!ENTITY lol "lol">]>'
                f'<worksheet xmlns="{SHEET_NS}"><sheetData></sheetData>'
                "</worksheet>")
        data = workbook([["domain"]],
                        extra={"xl/worksheets/sheet1.xml": bomb})
        with self.assertRaises(xlsx.NotAWorkbook) as caught:
            xlsx.rows(data)
        self.assertIn("entity", str(caught.exception))

    def test_a_zip_bomb_is_refused_without_being_read(self):
        """A few kilobytes that expand to gigabytes. Refused on the
        declared size, before a byte of it is decompressed."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", "<x/>")
            archive.writestr("xl/worksheets/sheet1.xml",
                             "0" * (xlsx.MAX_UNPACKED + 1))
        with self.assertRaises(xlsx.NotAWorkbook) as caught:
            xlsx.rows(buf.getvalue())
        self.assertIn("MB", str(caught.exception))

    def test_many_members_that_each_fit_but_together_do_not(self):
        """The per-member cap catches one huge entry. This is the other
        shape: twelve entries, each comfortably under the limit, adding up
        to more than the whole file may unpack to. Without the aggregate
        check the per-member one passes each of them."""
        buf = io.BytesIO()
        chunk = "0" * (xlsx.MAX_UNPACKED // 10)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", "<x/>")
            for n in range(12):
                archive.writestr(f"xl/media/{n}.bin", chunk)
        with self.assertRaises(xlsx.NotAWorkbook) as caught:
            xlsx.rows(buf.getvalue())
        self.assertIn("unpacks to more than", str(caught.exception))

    def test_a_zip_with_too_many_members_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            for n in range(xlsx.MAX_ENTRIES + 1):
                archive.writestr(f"junk/{n}", "x")
        with self.assertRaises(xlsx.NotAWorkbook) as caught:
            xlsx.rows(buf.getvalue())
        self.assertIn("members", str(caught.exception))

    def test_a_broken_zip_says_so(self):
        with self.assertRaises(xlsx.NotAWorkbook):
            xlsx.rows(xlsx.MAGIC + b"not really a zip")


class ThroughTheImport(unittest.TestCase):
    """One parser for the file, one for the shape."""

    def parse(self, data):
        return upload.parse(data, batch="b", client="productive")

    def test_a_workbook_imports_like_the_csv_it_becomes(self):
        out = self.parse(workbook([["Company Website", "Work Email",
                                    "First Name"],
                                   ["acme.test", "a@acme.test", "Ann"]]))
        self.assertEqual(len(out["rows"]), 1)
        self.assertEqual(out["rows"][0]["domain"], "acme.test")
        self.assertEqual(out["rows"][0]["contacts"][0]["email"],
                         "a@acme.test")

    def test_the_preview_names_the_sheet_it_read(self):
        out = self.parse(workbook([["domain"], ["acme.test"]],
                                  sheet="Q3 Targets"))
        self.assertEqual(out["sheet"], "Q3 Targets")

    def test_a_csv_has_no_sheet(self):
        out = self.parse(b"domain\nacme.test\n")
        self.assertIsNone(out["sheet"])

    def test_the_formula_guard_still_runs_on_a_workbook(self):
        """A cached formula result can still start with `=`, and the cell
        is the same attack on whoever opens the export later."""
        out = self.parse(workbook([["domain", "email"],
                                   ["acme.test", "=cmd|'/c calc'!A1"]]))
        # The company survives; the cell does not become a person.
        self.assertEqual(len(out["rows"]), 1)
        self.assertEqual(out["rows"][0]["contacts"], [])
        self.assertNotIn("calc", repr(out["rows"]))

    def test_the_alias_table_applies_the_same_way(self):
        out = self.parse(workbook([["Organization", "Company Website"],
                                   ["Acme Ltd", "acme.test"]]))
        self.assertEqual(out["rows"][0]["company"], "Acme Ltd")

    def test_a_cell_containing_a_comma_survives_the_conversion(self):
        """The workbook becomes the bytes a CSV arrives as, so a company
        called "Acme, Inc" has to be quoted on the way through or it
        becomes two columns and every row after it is ragged."""
        out = self.parse(workbook([["Organization", "Company Website"],
                                   ["Acme, Inc", "acme.test"]]))
        self.assertEqual(out["rows"][0]["company"], "Acme, Inc")
        self.assertEqual(out["ragged_rows"], 0)

    def test_an_empty_workbook_is_refused_with_a_reason(self):
        with self.assertRaises(upload.UploadRefused) as caught:
            self.parse(workbook([]))
        self.assertIn("empty", str(caught.exception))

    def test_a_refusal_reaches_the_operator_rather_than_raising(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("readme.txt", "hello")
        with self.assertRaises(upload.UploadRefused):
            self.parse(buf.getvalue())


class WhatItGetsWrong(unittest.TestCase):
    """Written down rather than discovered."""

    def test_a_date_arrives_as_the_number_the_file_stores(self):
        """Excel keeps a date as a serial number and the format lives
        somewhere this does not read. No canonical column is a date, so
        the worst case is a provenance column carrying a number."""
        buf = io.BytesIO()
        body = ('<row r="1"><c r="A1" t="inlineStr"><is><t>Added</t></is></c>'
                "</row>"
                '<row r="2"><c r="A2"><v>45678</v></c></row>')
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("xl/workbook.xml",
                             f'<workbook xmlns="{SHEET_NS}"><sheets>'
                             '<sheet name="S"/></sheets></workbook>')
            archive.writestr("xl/worksheets/sheet1.xml",
                             f'<worksheet xmlns="{SHEET_NS}"><sheetData>'
                             f"{body}</sheetData></worksheet>")
        grid, _ = xlsx.rows(buf.getvalue())
        self.assertEqual(grid[1][0], "45678")


if __name__ == "__main__":
    unittest.main()
