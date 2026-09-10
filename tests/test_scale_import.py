"""A 30,000-domain TAM upload, offline, with no provider reached.

## What this file is asking

The import path is advertised for 200,000 rows and the batch path is
advertised as resumable. Both claims are cheap to make and expensive to
discover wrong at the size a real TAM list arrives in, so this asserts
them at 30,000 rows and asks the two questions that decide whether an
upload is safe:

  1. Is anything meaningful discarded without a reason attached to it?
  2. Can 30,000 rows turn into 30,000 paid calls?

Nothing here reaches a provider, resolves DNS, or writes to `work/`.
`upload.parse` writes nothing by construction; `enrich.plan` and
`enrich.run(live=False)` make no calls; every store-backed test runs
against the throwaway queue `QueueTest` builds. The 30,000-row file is
generated in a temporary directory and thrown away.

## The findings this file pins down

Each of these is asserted as current behaviour so that changing it breaks
a test rather than a client:

- `xlsx.rows` **silently discards** every cell past `MAX_COLUMNS`. Rows
  past `MAX_ROWS` raise; columns past `MAX_COLUMNS` do not, and nothing
  in the returned grid, the parse report or the module docstring says a
  column was dropped. It is the one place in the import path where data
  goes missing with no reason.
- `MAX_BYTES` is the binding limit, not `MAX_ROWS`. A realistic 30,000-row
  export with twenty columns is over 8 MB and is refused whole, so the
  200,000-row ceiling is reachable only by a file averaging under ~42
  bytes a row.
- An IDN in unicode is refused; the same name in punycode is accepted -
  but only under an ASCII TLD. A punycode TLD (`xn--p1ai`, the .рф zone)
  is refused, because `ingest.HOSTNAME` requires the last label to be
  letters. Refusals are reported; the asymmetry is not documented.
- latin-1 bytes are decoded as UTF-8 with replacement, so a company name
  arrives mojibake and the report says nothing about it.
- `jobs.run_step`'s budget counts *records*, not credits.
- `run.stage_enrich` does not thread `scrape_budget` or `config` into
  `enrich.enrich_record`, so on the `python -m src.run --spend` path the
  Apify per-batch scrape ceiling is not enforced at all.
"""
import io
import os
import shutil
import tempfile
import time
import tracemalloc
import unittest
import zipfile

from src.providers import apify
from src import clients
from src import enrich, icp, ingest, jobs, research, run as runner, store
from src.web import upload, xlsx
from tests.base import QueueTest

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Big enough to be the real question and small enough to run in a test suite.
TAM = 30_000

# The pilot ratios this exercise was given. They are inputs, not measurements
# taken here, and they are named so a reader can tell which is which.
FREE_RESOLVE = 0.52          # domains answered by the free local HTTP fetch
APIFY_FALLBACK = 0.26        # domains that need a scrape instead
COMPANY_CREDITS = 1          # per domain, company-level
PERSON_CREDITS = 10          # per QUALIFIED account, person discovery


def workbook(rows, sheet="Leads"):
    """A minimal but real xlsx. Inline strings, so no shared table to keep."""
    def ref(column, row):
        out, column = "", column + 1
        while column:
            column, rest = divmod(column - 1, 26)
            out = chr(65 + rest) + out
        return out + str(row)

    body = ""
    for r, row in enumerate(rows, start=1):
        body += ('<row r="%d">' % r) + "".join(
            '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref(c, r), v)
            for c, v in enumerate(row)) + "</row>"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{SHEET_NS}"><sheets>'
            f'<sheet name="{sheet}"/></sheets></workbook>')
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{SHEET_NS}"><sheetData>{body}</sheetData>'
            "</worksheet>")
    return buf.getvalue()


def domains_csv(count, prefix="c"):
    return ("domain\n" + "".join("%s%d.test\n" % (prefix, i)
                                 for i in range(count))).encode("utf-8")


def parse(data, **kw):
    """`suppress` always supplied, so no test reads the repository's own list."""
    kw.setdefault("suppress", set())
    return upload.parse(data, **kw)


# --------------------------------------------------------------------------
# Part 1: import robustness
# --------------------------------------------------------------------------

class ThirtyThousandDomains(unittest.TestCase):
    """The headline case: a domain-only TAM list, whole."""

    @classmethod
    def setUpClass(cls):
        # Generated on disk rather than in memory, because the question is
        # about a file somebody uploads. Never in `work/`.
        cls.scratch = tempfile.mkdtemp(prefix="rga-scale-")
        cls.path = os.path.join(cls.scratch, "tam-30k.csv")
        with open(cls.path, "wb") as handle:
            handle.write(domains_csv(TAM))
        with open(cls.path, "rb") as handle:
            cls.data = handle.read()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.scratch, ignore_errors=True)

    def test_every_row_survives_and_the_report_says_so(self):
        report = parse(self.data)
        self.assertEqual(report["uploaded"], TAM)
        self.assertEqual(report["unique"], TAM)
        self.assertEqual(len(report["rows"]), TAM)
        self.assertEqual(report["excluded"], [])
        self.assertEqual(report["ragged_rows"], 0)
        self.assertEqual(report["invalid"], 0)
        self.assertFalse(report["committed"])

    def test_it_finishes_in_a_time_a_browser_can_wait_for(self):
        start = time.perf_counter()
        report = parse(self.data)
        elapsed = time.perf_counter() - start
        self.assertEqual(report["unique"], TAM)
        # Measured at ~0.2s. The bound is loose on purpose: this is a
        # regression guard against an accidental quadratic, not a benchmark.
        self.assertLess(elapsed, 30.0,
                        f"30,000 rows took {elapsed:.1f}s, which is a shape "
                        "change rather than a slow machine")

    def test_memory_is_proportional_and_bounded(self):
        tracemalloc.start()
        try:
            report = parse(self.data)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(report["unique"], TAM)
        # Measured at ~21 MB peak for 30,000 rows: the whole report is held
        # in memory, so the ceiling is what matters, not the growth rate.
        self.assertLess(peak, 256 * 1024 * 1024,
                        f"peak {peak / 1048576:.0f} MB for {TAM} rows")

    def test_the_byte_cap_bites_long_before_the_row_cap(self):
        """A realistic wide export of 30,000 rows is refused whole.

        `MAX_ROWS` is 200,000 and `MAX_BYTES` is 8 MB, so the row ceiling is
        reachable only by a file averaging under ~42 bytes a row. A twenty
        column Apollo-shaped export is roughly 330 bytes a row.
        """
        header = ("Company Website,Company Name,Work Email,Job Title,"
                  "First Name,Last Name,Person Linkedin Url,Employees,"
                  "Industry,City,Country,Seniority,Department,Phone,"
                  "Founded,Revenue,Technologies,Description,Source,Notes\n")
        row = ("c%d.test,Company %d,p%d@c%d.test,Chief Executive Officer,"
               "Firstname,Lastname,https://www.linkedin.com/in/person-%d,250,"
               "Marketing and Advertising,London,United Kingdom,C-Level,"
               "Executive,+44 20 7000 0000,2011,10M-50M,"
               "Hubspot;Salesforce;Wordpress,"
               "A mid sized agency doing paid media and seo work,apollo,"
               "imported\n")
        blob = (header + "".join(row % (i, i, i, i, i)
                                 for i in range(TAM))).encode("utf-8")
        self.assertGreater(len(blob), upload.MAX_BYTES)
        with self.assertRaises(upload.UploadRefused) as caught:
            parse(blob)
        # Refused loudly, which is the right half of this. The wrong half is
        # that `MAX_ROWS` advertises a ceiling this file cannot reach.
        self.assertIn("larger than", str(caught.exception))


class TheRowCaps(unittest.TestCase):

    def test_csv_accepts_exactly_max_rows_and_refuses_one_more(self):
        report = parse(domains_csv(upload.MAX_ROWS))
        self.assertEqual(report["uploaded"], upload.MAX_ROWS)
        with self.assertRaises(upload.UploadRefused) as caught:
            parse(domains_csv(upload.MAX_ROWS + 1))
        self.assertIn(str(upload.MAX_ROWS), str(caught.exception))

    def test_a_workbook_over_max_rows_is_refused_not_truncated(self):
        rows = [["domain"]] + [["c%d.test" % i]
                              for i in range(xlsx.MAX_ROWS + 5)]
        with self.assertRaises(xlsx.NotAWorkbook) as caught:
            xlsx.rows(workbook(rows))
        self.assertIn(str(xlsx.MAX_ROWS), str(caught.exception))


class TheColumnCapIsTheOneSilentLoss(unittest.TestCase):
    """`xlsx.MAX_COLUMNS` drops cells with no reason recorded anywhere.

    Every other bound in the import path refuses, reports, or both.
    `xlsx.rows` `continue`s past a cell whose column index is at or beyond
    `MAX_COLUMNS`, and neither the grid, the parse report, nor the module
    docstring's list of guards mentions that anything was dropped.

    This is asserted rather than fixed: changing `src/` was out of scope
    for this exercise, and a test that pins the loss is what makes the
    next person's fix provable.
    """

    def test_cells_past_the_column_cap_are_refused_not_dropped(self):
        width = xlsx.MAX_COLUMNS + 2
        header = ["col%d" % i for i in range(width)]
        values = ["v%d" % i for i in range(width)]
        header[0], values[0] = "domain", "acme.test"
        header[-1], values[-1] = "Work Email", "buried@acme.test"

        # FIXED. Was a silent `continue`: the sheet came back truncated, a
        # `Work Email` column at position 514 simply was not there, and the
        # parse report - the only thing an operator reads - showed a clean
        # import of a file that had lost two columns. It refuses now, which is
        # what every other bound in this path already did.
        with self.assertRaises(xlsx.NotAWorkbook) as raised:
            xlsx.rows(workbook([header, values]))
        self.assertIn("columns", str(raised.exception))
        self.assertIn(str(xlsx.MAX_COLUMNS), str(raised.exception))

    def test_a_row_cap_by_contrast_refuses(self):
        """The comparison that makes the finding a finding, not a preference."""
        with self.assertRaises(xlsx.NotAWorkbook):
            xlsx.rows(workbook([["domain"]] +
                               [["c%d.test" % i]
                                for i in range(xlsx.MAX_ROWS + 1)]))


class SpreadsheetsGoThroughTheSameDoor(unittest.TestCase):

    def test_a_workbook_parses_as_a_csv_does(self):
        report = parse(workbook([["Company Website", "Company Name"],
                                 ["acme.test", "Acme"],
                                 ["b.test", "B"]]))
        self.assertEqual(report["uploaded"], 2)
        self.assertEqual(report["unique"], 2)
        self.assertEqual(report["sheet"], "Leads")

    def test_the_sheet_that_was_read_is_named(self):
        report = parse(workbook([["domain"], ["acme.test"]], sheet="Tab One"))
        self.assertEqual(report["sheet"], "Tab One")

    def test_a_csv_reports_no_sheet(self):
        self.assertIsNone(parse(b"domain\nacme.test\n")["sheet"])

    def test_a_zip_that_is_not_a_workbook_is_refused_with_a_reason(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("hello.txt", "not a workbook")
        with self.assertRaises(upload.UploadRefused) as caught:
            parse(buf.getvalue())
        self.assertIn("worksheet", str(caught.exception))


class Encodings(unittest.TestCase):

    def test_a_utf8_byte_order_mark_is_stripped_from_the_first_header(self):
        report = parse("﻿domain,company\nacme.test,Acme\n".encode("utf-8"))
        self.assertEqual(report["unique"], 1)
        self.assertEqual(report["rows"][0]["company"], "Acme")

    def test_non_ascii_company_names_survive_intact(self):
        report = parse("domain,company\na.test,Rhône Café\n"
                       "b.test,株式会社テスト\n".encode("utf-8"))
        self.assertEqual([r["company"] for r in report["rows"]],
                         ["Rhône Café", "株式会社テスト"])

    def test_latin1_bytes_become_mojibake_and_nothing_says_so(self):
        """The row is imported; the company name is damaged; the report is clean.

        `parse` decodes with `errors="replace"`, which is deliberate - see
        the module docstring - but the replacement never reaches the report,
        so an operator has no signal that a name was corrupted.
        """
        report = parse("domain,company\nacme.test,Rhône Café\n"
                       .encode("latin-1"))
        self.assertEqual(report["unique"], 1)
        self.assertIn("�", report["rows"][0]["company"])
        self.assertEqual(report["excluded"], [])
        self.assertEqual(report["ragged"], [])

    def test_a_latin1_domain_column_is_at_least_refused(self):
        """Where it matters most, the hostname shape check catches it."""
        report = parse("domain\nrhône.test\n".encode("latin-1"))
        self.assertEqual(report["unique"], 0)
        self.assertEqual(len(report["excluded"]), 1)
        self.assertIn("hostname", report["excluded"][0]["reason"])


class InternationalDomains(unittest.TestCase):
    """Which spellings are accepted, and whether the rule is discoverable."""

    def parse_one(self, value):
        report = parse(("domain\n%s\n" % value).encode("utf-8"))
        return report["rows"][0] if report["rows"] else report["excluded"][0]

    def test_a_unicode_idn_is_refused_with_a_reason(self):
        for value in ("münchen.de", "例え.テスト", "пример.рф", "café.test"):
            with self.subTest(value=value):
                outcome = self.parse_one(value)
                self.assertIn("reason", outcome,
                              f"{value} was imported as a domain")
                self.assertIn("hostname", outcome["reason"])

    def test_punycode_under_an_ascii_tld_is_accepted(self):
        outcome = self.parse_one("xn--mnchen-3ya.de")
        self.assertEqual(outcome.get("domain"), "xn--mnchen-3ya.de")
        self.assertNotIn("reason", outcome)

    def test_a_punycode_tld_is_refused_and_that_is_not_documented(self):
        """`.рф` in its wire form. `HOSTNAME`'s last label must be letters.

        `ingest.HOSTNAME` ends `[a-z]{2,63}`, so `xn--p1ai` fails on its
        digit. Nothing in `ingest`, `upload` or `columns` says an
        internationalised TLD is out of scope, and no upload path converts
        unicode to punycode either - so an entire class of European and
        Asian domain is refused as malformed with no note anywhere that
        this is intended.
        """
        for value in ("xn--e1afmkfd.xn--p1ai", "xn--r8jz45g.xn--zckzah"):
            with self.subTest(value=value):
                outcome = self.parse_one(value)
                self.assertIn("reason", outcome)
                self.assertIn("hostname", outcome["reason"])

        # The rule itself, stated where a reader can check it.
        self.assertTrue(ingest.is_hostname("xn--mnchen-3ya.de"))
        self.assertFalse(ingest.is_hostname("xn--e1afmkfd.xn--p1ai"))
        self.assertFalse(ingest.is_hostname("münchen.de"))


class HeadersAndColumns(unittest.TestCase):

    def test_a_foreign_export_maps_onto_canonical_fields(self):
        report = parse(b"Company Website,Organization,Work Email,Job Title,"
                       b"Employees,Notes\r\n"
                       b"https://acme.test/x?q=1,Acme Ltd,a@acme.test,CEO,"
                       b"50,hello\r\n")
        row = report["rows"][0]
        self.assertEqual(row["domain"], "acme.test")
        self.assertEqual(row["company"], "Acme Ltd")
        self.assertEqual(row["contacts"][0]["email"], "a@acme.test")
        self.assertEqual(row["contacts"][0]["title"], "CEO")

    def test_unexpected_extra_columns_are_kept_as_provenance_not_dropped(self):
        report = parse(b"domain,email,Employees,Notes\r\n"
                       b"acme.test,a@acme.test,50,hello\r\n")
        self.assertEqual(report["unmapped_columns"], ["Employees", "Notes"])
        self.assertEqual(report["rows"][0]["contacts"][0]["source"],
                         {"Employees": "50", "Notes": "hello"})

    def test_missing_optional_fields_are_not_an_error(self):
        report = parse(b"domain\nacme.test\n")
        self.assertEqual(report["unique"], 1)
        self.assertEqual(report["rows"][0]["company"], "acme.test")
        self.assertEqual(report["rows"][0]["contacts"], [])

    def test_a_file_with_no_company_column_is_refused_not_half_read(self):
        with self.assertRaises(upload.UploadRefused) as caught:
            parse(b"company,email\nAcme,a@acme.test\n")
        self.assertIn("no column identifies the company", str(caught.exception))

    def test_a_duplicated_header_refuses_the_whole_file(self):
        """Two `domain` columns map to neither, so the file has none.

        The refusal is loud, which is right. The message is not: it says
        no column identifies the company about a file with two that do.
        """
        with self.assertRaises(upload.UploadRefused) as caught:
            parse(b"domain,domain\nacme.test,other.test\n")
        self.assertIn("no column identifies the company", str(caught.exception))

    def test_a_semicolon_export_is_read_rather_than_refused(self):
        report = parse('Company Website;Company Name\r\n'
                       'acme.test;"Acme, Ltd"\r\n'.encode("utf-8"))
        self.assertEqual(report["delimiter"], ";")
        self.assertEqual(report["rows"][0]["company"], "Acme, Ltd")


class NothingIsDiscardedWithoutAReason(unittest.TestCase):
    """The critical question, asked as an accounting identity."""

    MESSY = (b"domain,company,email\r\n"
             b"acme.test,Acme,\r\n"                      # 2 kept
             b"\r\n"                                     # blank, csv skips
             b",,\r\n"                                   # 4 no domain
             b"Acme.Test,Acme,\r\n"                      # 5 duplicate
             b"www.acme.test,Acme,\r\n"                  # 6 duplicate
             b"b.test,B,one@b.test\r\n"                  # 7 kept
             b"b.test,B,two@b.test\r\n"                  # 8 attached
             b"b.test,B,one@b.test\r\n"                  # 9 duplicate contact
             b"c.test,C,x@c.test,SPILL\r\n"              # 10 kept + ragged
             b"d.test\r\n"                               # 11 kept + ragged
             b'"=IMPORTXML(1)",E,\r\n'                   # 12 formula
             b"not a domain,F,\r\n"                      # 13 not a hostname
             b"g.test,G,\r\n")                           # 14 kept

    def test_every_excluded_row_carries_a_reason(self):
        report = parse(self.MESSY)
        for entry in report["excluded"]:
            self.assertTrue(entry.get("reason"), entry)
            self.assertIn("row", entry)
        for entry in report["ragged"]:
            self.assertTrue(entry.get("reason"), entry)

    def test_the_counts_add_up(self):
        """uploaded == imported + excluded + attached, for row-level outcomes."""
        report = parse(self.MESSY)
        self.assertEqual(report["uploaded"], 12)         # the blank line is not a row
        self.assertEqual(
            report["uploaded"],
            len(report["rows"]) + len(report["excluded"])
            + len(report["attached"]))
        self.assertEqual(report["duplicates"], 2)
        self.assertEqual(report["duplicate_contacts"], 1)
        self.assertEqual(report["additional_contacts"], 1)
        self.assertEqual(report["invalid"], 3)           # no domain, formula, shape
        self.assertEqual(report["ragged_rows"], 2)

    def test_a_ragged_row_is_reported_and_still_imported(self):
        report = parse(self.MESSY)
        ragged = {entry["row"] for entry in report["ragged"]}
        # 9 and 10 by the reader's count; lines 10 and 11 of the file. See
        # `test_the_reported_row_number_drifts_after_a_blank_line`.
        self.assertEqual(ragged, {9, 10})
        kept = {row["domain"] for row in report["rows"]}
        self.assertIn("c.test", kept)
        self.assertIn("d.test", kept)

    def test_a_second_person_at_a_known_company_is_attached_not_dropped(self):
        report = parse(self.MESSY)
        by_domain = {row["domain"]: row for row in report["rows"]}
        self.assertEqual(
            sorted(c["email"] for c in by_domain["b.test"]["contacts"]),
            ["one@b.test", "two@b.test"])
        self.assertEqual(report["attached"][0]["row"], 7)     # file line 8

    def test_the_reported_row_number_drifts_after_a_blank_line(self):
        """`row` is the reader's position, not the line in the file.

        `parse` numbers with `enumerate(reader, start=2)`, and
        `csv.DictReader` does not yield a wholly blank line at all. So
        every blank line in a file shifts every subsequent `row` number
        down by one, and an operator told "row 4 is not a usable domain"
        opens their spreadsheet at row 5. Nothing is lost - the reason is
        still attached to the right row's data - but the number that
        points at it is wrong, and the report offers no other handle.
        """
        report = parse(b"domain\r\n"
                       b"a.test\r\n"
                       b"\r\n"                    # file line 3
                       b"\r\n"                    # file line 4
                       b"not a domain\r\n")       # file line 5
        self.assertEqual(len(report["excluded"]), 1)
        self.assertEqual(report["excluded"][0]["row"], 3)
        self.assertNotEqual(report["excluded"][0]["row"], 5)
        # A file with no blank lines numbers correctly, which is what makes
        # this a drift rather than a constant offset.
        clean = parse(b"domain\r\na.test\r\nnot a domain\r\n")
        self.assertEqual(clean["excluded"][0]["row"], 3)

    def test_an_oversized_address_is_reported_but_the_row_is_still_counted(self):
        """The one place the accounting identity does not hold.

        A row whose `email` exceeds `MAX_CELL` is kept - correctly, it is
        still a company - and *also* appended to `excluded`, because the
        `continue` there leaves the contact-column loop rather than the row
        loop. So `uploaded` is 2, `rows` is 2 and `excluded` is 1: one row
        is counted twice. The address is refused whole rather than cut,
        which is the safe half; the count is the unsafe half, because
        `excluded` reads as "rows that did not make it".
        """
        long_address = "a" * 240 + "@acme.test"
        report = parse(("domain,email\nacme.test,%s\nb.test,ok@b.test\n"
                        % long_address).encode("utf-8"))
        self.assertEqual(report["uploaded"], 2)
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(len(report["excluded"]), 1)
        self.assertNotEqual(
            report["uploaded"],
            len(report["rows"]) + len(report["excluded"])
            + len(report["attached"]))
        # Nothing was truncated into a valid-looking different address.
        self.assertEqual(report["rows"][0]["contacts"], [])
        self.assertIn("not shortened", report["excluded"][0]["reason"])

    def test_a_formula_never_becomes_a_domain(self):
        report = parse(b'domain,company\r\n'
                       b'"=IMPORTXML(1)",A\r\n'
                       b'"\t=cmd",B\r\n'
                       b'"@SUM(1)",C\r\n'
                       b'acme.test,"=HYPERLINK(1)"\r\n')
        self.assertEqual(report["unique"], 1)
        self.assertEqual(len(report["excluded"]), 3)
        for entry in report["excluded"]:
            self.assertIn("formula", entry["reason"])
        # A formula in the *company* column falls back to the domain rather
        # than storing the formula.
        self.assertEqual(report["rows"][0]["company"], "acme.test")

    def test_a_duplicate_at_thirty_thousand_is_counted_not_lost(self):
        blob = (b"domain\n" + b"".join(b"c%d.test\n" % (i // 2)
                                       for i in range(TAM)))
        report = parse(blob)
        self.assertEqual(report["uploaded"], TAM)
        self.assertEqual(report["unique"], TAM // 2)
        self.assertEqual(report["duplicates"], TAM // 2)
        self.assertEqual(report["unique"] + report["duplicates"], TAM)


class IngestAtScale(QueueTest):
    """`ingest.run` is the CLI half of the same path, and it writes."""

    def csv(self, name, lines):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("company,domain\n")
            for line in lines:
                handle.write(line + "\n")
        return path

    def none(self):
        """A suppress file that does not exist, so the repository's is not read."""
        return os.path.join(self.tmp, "no-such-suppress.txt")

    def test_every_row_lands_as_a_record_or_a_drop_with_a_reason(self):
        path = self.csv("mixed.csv", [
            "Acme,acme.test",
            "Dupe,acme.test",
            "Nothing,",
            "Beta,b.test",
        ])
        result = ingest.run(path, "productive", "domains",
                            suppress_path=self.none())
        self.assertEqual(len(result["queued"]), 2)
        self.assertEqual(len(result["dropped"]), 2)
        for _rid, reason in result["dropped"]:
            self.assertTrue(reason)
        # Nothing was deleted: every input row is a row in the queue.
        self.assertEqual(len(store.load()), 4)

    def test_the_cli_path_applies_its_own_hostname_rule(self):
        """`ingest.HOSTNAME` exists, and `ingest.run` never asks it.

        This is the finding this file exists to catch. `upload.parse` -
        the browser path - refuses a value that is not the shape of a
        hostname, and its comment says the rule "lives in `ingest`, so the
        import path and the discovery path cannot drift into two different
        opinions about what a domain is."

        `ingest.run` is the import path, and it does not consult it.
        `norm_domain` normalises without judging - it says so - so
        anything that survives it non-empty is queued as a domain. That
        includes a spreadsheet formula, the residue of a DDE injection
        payload, and a sentence. Those records then carry a fabricated
        domain into MX lookups, provider payloads and client exports.

        The two consumers of `is_hostname` are `discovery.py:150` and
        `web/upload.py:353`. There is no third.
        """
        path = self.csv("junk.csv", [
            "Good,acme.test",
            "Junk,not a domain",
            "Formula,=IMPORTXML(1)",
            'Inject,"cmd|\'/c calc\'!A1"',
        ])
        result = ingest.run(path, "productive", "domains",
                            suppress_path=self.none())
        # FIXED. `ingest.run` now applies the rule this module defines, so the
        # two import paths hold one opinion about what a domain is - which is
        # what the comment above `HOSTNAME` always claimed.
        self.assertEqual(len(result["queued"]), 1)
        self.assertEqual(len(result["dropped"]), 3)
        for _company, why in result["dropped"]:
            self.assertIn("not the shape of a hostname", why)

        queued = {rec["id"]: rec["domain"] for rec in store.load()
                  if not rec.get("drop_reason")}
        self.assertEqual(set(queued.values()), {"acme.test"})
        web = parse(b"domain,company\r\n"
                    b"not a domain,Junk\r\n"
                    b'"=IMPORTXML(1)",Formula\r\n'
                    b'"cmd|\'/c calc\'!A1",Inject\r\n')
        self.assertEqual(web["unique"], 0)
        self.assertEqual(len(web["excluded"]), 3)

    def test_both_import_paths_now_agree_about_international_domains(self):
        """The same drift, in the direction that matters commercially.

        A unicode IDN and a punycode TLD are both queued by `ingest.run`
        and both refused by `upload.parse`. Whichever answer is right, two
        importers giving different ones is the defect.
        """
        path = self.csv("idn.csv", [
            "Munich,münchen.de",
            "Rf,xn--e1afmkfd.xn--p1ai",
        ])
        result = ingest.run(path, "productive", "domains",
                            suppress_path=self.none())
        # FIXED - the two paths now agree. They agree on *refusing* both,
        # which is conservative and not necessarily right: `HOSTNAME` ends
        # `[a-z]{2,63}`, so a punycode TLD fails on its digit and a whole
        # class of European and Asian domains is unimportable by either
        # route. That is now one documented decision instead of two
        # importers disagreeing, and it is recorded in PRODUCT-GAPS.md.
        self.assertEqual(len(result["queued"]), 0)
        self.assertEqual(len(result["dropped"]), 2)

        web = parse("domain,company\r\nmünchen.de,Munich\r\n"
                    "xn--e1afmkfd.xn--p1ai,Rf\r\n".encode("utf-8"))
        self.assertEqual(web["unique"], 0)
        self.assertEqual(len(web["excluded"]), 2)

    def test_ids_stay_unique_when_every_slug_collides(self):
        """`slug` cuts at 40 characters, so long names collide by design.

        The de-collision loop is a linear scan per record, which makes this
        input quadratic: 500 rows took 0.04s, 1,000 took 0.12s and 2,000
        took 0.35s when measured. It is correct at every size - which is
        what this asserts - and the cost is recorded rather than bounded,
        because a threshold here would be a machine-speed test.
        """
        stem = "a" * 40
        rows = ["X,%s%04d.test" % (stem, i) for i in range(300)]
        result = ingest.run(self.csv("collide.csv", rows), "productive",
                            "domains", suppress_path=self.none())
        self.assertEqual(len(result["queued"]), 300)
        ids = [rec["id"] for rec in store.load()]
        self.assertEqual(len(set(ids)), 300)

    def test_a_second_run_of_the_same_file_writes_nothing_new(self):
        path = self.csv("again.csv", ["Acme,acme.test", "Beta,b.test"])
        ingest.run(path, "productive", "domains", suppress_path=self.none())
        second = ingest.run(path, "productive", "domains",
                            suppress_path=self.none())
        self.assertEqual(second["queued"], [])
        self.assertEqual(len(second["skipped"]), 2)
        self.assertEqual(len(store.load()), 2)


# --------------------------------------------------------------------------
# Part 2: batch control
# --------------------------------------------------------------------------

class ThirtyThousandRowsDoNotFanOut(QueueTest):
    """Is there queueing, or does an upload become 30,000 calls at once?"""

    def test_the_import_path_reaches_no_provider_and_spends_nothing(self):
        report = parse(domains_csv(1000))
        self.assertEqual(report["unique"], 1000)
        # `verification` and `hygiene` are the two keys that could imply a
        # spend, and both are None when nothing was passed to compare against.
        self.assertIsNone(report["verification"])
        self.assertIsNone(report["hygiene"])

    def test_nothing_in_the_spend_path_is_concurrent(self):
        """Behaviour, not source text: work is observed strictly in order."""
        order = []
        items = [{"id": "r%03d" % i} for i in range(250)]
        job = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="tam",
                       total=len(items))
        jobs.run_to_completion(job, items, lambda i: order.append(i["id"]) or "ok",
                               slice_size=jobs.SLICE)
        self.assertEqual(order, [i["id"] for i in items])

    def test_a_slice_bounds_how_much_one_call_does(self):
        items = [{"id": "r%05d" % i} for i in range(TAM)]
        job = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="tam",
                       total=len(items))
        touched = []
        jobs.run_step(job, items, lambda i: touched.append(i) or "ok",
                      slice_size=jobs.SLICE)
        self.assertEqual(len(touched), jobs.SLICE)
        self.assertEqual(job["processed"], jobs.SLICE)
        self.assertEqual(job["status"], jobs.RUNNING)


class CheckpointAndResume(QueueTest):

    def items(self):
        return [{"id": "r%05d" % i} for i in range(TAM)]

    def test_a_batch_that_dies_at_twelve_thousand_resumes_there(self):
        items = self.items()
        before = []
        job = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="tam",
                       total=len(items))
        for _ in range(120):
            jobs.run_step(job, items, lambda i: before.append(i["id"]) or "ok",
                          slice_size=100)
        self.assertEqual(job["processed"], 12_000)
        self.assertEqual(job["cursor"], "r11999")

        # The process dies. A new one loads the job row and calls again.
        resumed = dict(job)
        after = []
        jobs.run_step(resumed, items, lambda i: after.append(i["id"]) or "ok",
                      slice_size=100)
        self.assertEqual(after[0], "r12000")
        self.assertEqual(set(after) & set(before), set())

    def test_the_cursor_survives_the_batch_growing_underneath_it(self):
        items = self.items()[:500]
        job = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="tam",
                       total=len(items))
        jobs.run_step(job, items, lambda i: "ok", slice_size=100)
        grown = [{"id": "new-%d" % i} for i in range(50)] + items
        touched = []
        jobs.run_step(job, grown, lambda i: touched.append(i["id"]) or "ok",
                      slice_size=100)
        # Identity, not index: it continues after r00099, not after item 99.
        self.assertEqual(touched[0], "r00100")

    def test_re_running_a_record_does_not_re_buy_what_it_already_bought(self):
        """Idempotency on resume is read off the waterfall ledger."""
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["company_facts"] = {"headcount_signal": 40}
        self.assertFalse(enrich.already_bought(
            rec, "company-information-from-domain"))
        first = [op["call"] for op in enrich.plan(rec)]
        self.assertIn("company-information-from-domain", first)

        rec["waterfall"] = [{"call": "company-information-from-domain"}]
        second = [op["call"] for op in enrich.plan(rec)]
        self.assertNotIn("company-information-from-domain", second)
        self.assertTrue(enrich.already_bought(
            rec, "company-information-from-domain"))

    def test_a_finished_stage_is_not_re_run_by_the_runner(self):
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        self.assertTrue(runner.needs(rec, "enrich"))
        runner.mark(rec, "enrich", "done")
        self.assertFalse(runner.needs(rec, "enrich"))
        # A cap-shortened record is `partial`, so the next pass picks it up.
        runner.mark(rec, "enrich", "partial")
        self.assertTrue(runner.needs(rec, "enrich"))


class WhichCapsExist(QueueTest):

    def qualified(self, i):
        rec = store.new_record("q%d" % i, "domains", "productive",
                               "Q%d" % i, "q%d.test" % i)
        rec["company_facts"] = {"headcount_signal": 40}
        rec["qualification"] = {"verdict": {"icp_status": icp.QUALIFIED}}
        return rec

    def test_a_per_run_credit_cap_exists_and_refuses_rather_than_overspending(self):
        budget = enrich.Budget(15)
        self.assertTrue(budget.charge(10, "a:decision-makers"))
        self.assertFalse(budget.charge(10, "b:decision-makers"))
        self.assertEqual(budget.spent, 10)
        self.assertEqual(budget.refused, ["b:decision-makers"])
        self.assertEqual(budget.remaining(), 5)

    def test_no_cap_at_all_is_the_default(self):
        """`--cap` is optional, and `Budget(None)` affords anything."""
        budget = enrich.Budget(None)
        self.assertTrue(budget.affordable(10 ** 9))
        self.assertIsNone(budget.remaining())

    def test_the_cap_is_per_run_and_nothing_carries_between_runs(self):
        """Two runs of `--cap 100` spend 200. There is no daily or workspace cap.

        Asserted as behaviour: a second `enrich.run` with the same cap gets
        the same fresh allowance, because the budget is a local in `run()`
        and nothing anywhere records credits spent per day or per workspace.
        """
        store.append([self.qualified(i) for i in range(10)])
        first = enrich.run(live=False, cap=100)
        second = enrich.run(live=False, cap=100)
        self.assertEqual(first["spent"], second["spent"])
        self.assertGreater(first["spent"], 0)
        # Nothing in the queue records a running credit total either.
        for rec in store.load():
            self.assertNotIn("credits_spent_today", rec)
            self.assertNotIn("workspace_credits", rec)

    def test_a_spending_job_refuses_to_run_without_a_budget(self):
        job = jobs.new(jobs.ENRICH, "productive", batch="tam", total=3)
        self.assertTrue(job["spends"])
        with self.assertRaises(jobs.JobError) as caught:
            jobs.run_step(job, [{"id": "a"}], lambda i: "ok")
        self.assertIn("refusing to run", str(caught.exception))

    def test_the_job_budget_counts_records_not_credits(self):
        """The unit mismatch. `budget=20` is twenty *records*, not twenty credits.

        `run_step` increments `spent` by exactly one per unit of work
        regardless of what that work cost, and stops when `spent >=
        budget`. A record that buys `decision-makers` costs ten credits,
        so a job given a budget of 20 authorises up to 200 credits. The
        docstring and the refusal message both talk about credits.
        """
        items = [{"id": "r%03d" % i} for i in range(50)]
        job = jobs.new(jobs.ENRICH, "productive", batch="tam",
                       total=len(items))
        jobs.run_to_completion(job, items, lambda i: "ok", slice_size=10,
                               budget=20)
        self.assertEqual(job["processed"], 20)
        self.assertEqual(job["spent"], job["processed"])
        # What that would have cost, had each record bought one person search.
        self.assertEqual(job["spent"] * enrich.COSTS["decision-makers"], 200)
        # And no actual cost is recorded, by design.
        self.assertIsNone(job["actual_cost"])

    def test_the_web_layer_refuses_every_spending_job_outright(self):
        from src.web import api
        for job_type in jobs.SPENDING_TYPES:
            self.assertNotIn(job_type, api.RUNNABLE_JOBS,
                             f"{job_type} is runnable from a web request")
            self.assertIn(job_type, api.UNRUNNABLE_JOBS)

    def test_a_batch_of_failures_stops_the_job_rather_than_grinding_on(self):
        items = [{"id": "r%03d" % i} for i in range(200)]
        job = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="tam",
                       total=len(items))

        def always_fails(item):
            raise ValueError("no")

        jobs.run_to_completion(job, items, always_fails, slice_size=50)
        self.assertEqual(job["status"], jobs.FAILED)
        self.assertLess(job["processed"], len(items))
        self.assertIn("problem with the batch", job["error"])


class TheScrapeCeilingIsNotThreadedThrough(QueueTest):
    """A real gap, found by tracing the chain rather than reading the docstring.

    `research.RunBudget` is the only ceiling on how many Apify runs a batch
    may start, because `COSTS["apify-research"]` is zero and the credit cap
    therefore cannot see a scrape. `enrich.run` builds one and threads it in.
    `run.stage_enrich` - the `python -m src.run --spend` path, which is the
    one an operator uses to walk a whole batch - calls `enrich_record` with
    neither `scrape_budget` nor `config`, so on that path the ceiling is
    `None` and `research.run` skips the check entirely.
    """

    def test_research_only_enforces_the_ceiling_when_one_is_supplied(self):
        budget = research.RunBudget(2)
        self.assertTrue(budget.allow("a"))
        self.assertTrue(budget.allow("b"))
        self.assertFalse(budget.allow("c"))
        self.assertEqual(budget.refused, ["c"])
        # None is the unbounded case, and it is what `run.py` supplies.
        self.assertTrue(research.RunBudget(None).allow("z"))

    def test_the_runner_passes_both_the_budget_and_the_config(self):
        """Asserted on the call, by recording what `enrich_record` received."""
        seen = {}
        original = enrich.enrich_record

        def spy(rec, budget, live=False, log=None, config=None,
                scrape_budget=None, mx_cache=None):
            seen["config"] = config
            seen["scrape_budget"] = scrape_budget
            seen["mx_cache"] = mx_cache
            return []

        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        enrich.enrich_record = spy
        try:
            runner.stage_enrich([rec], spend=True, cap=None, notes=[])
        finally:
            enrich.enrich_record = original

        # FIXED. Was: neither reached `enrich_record`, so on the batch-runner
        # path `max_runs_per_batch` bounded nothing, `research` never ran at
        # all because it is gated on `config`, the client's verification
        # policy fell back to module defaults, and MX was never screened
        # before a verification credit was spent.
        self.assertIsNotNone(seen["scrape_budget"],
                             "the scrape ceiling is not threaded through")
        # The MX cache is threaded for the same reason and was missing for
        # longer: `enrich_record` loaded one per record and could never persist
        # it, so every run re-resolved every domain from scratch.
        self.assertIsNotNone(seen["mx_cache"],
                             "the MX cache is not threaded through, so every "
                             "record resolves its own domains again")
        self.assertEqual(seen["scrape_budget"].cap,
                         apify.settings(clients.load("productive"))
                         ["max_runs_per_batch"])
        self.assertIsNotNone(seen["config"], "the client config is not passed")
        self.assertEqual(seen["config"].get("name"), "Productive")


class TheForecastAgainstWhatIsSpent(QueueTest):

    def qualified(self, i):
        rec = store.new_record("q%d" % i, "domains", "productive",
                               "Q%d" % i, "q%d.test" % i)
        rec["company_facts"] = {"headcount_signal": 40}
        rec["qualification"] = {"verdict": {"icp_status": icp.QUALIFIED}}
        return rec

    def test_expected_and_maximum_are_different_numbers(self):
        ops = enrich.plan(self.qualified(0))
        self.assertEqual(enrich.exposure(ops),
                         {"expected": 10, "maximum": 13})

    def test_an_unqualified_company_is_forecast_at_company_prices_only(self):
        rec = store.new_record("u", "domains", "productive", "U", "u.test")
        rec["company_facts"] = {"headcount_signal": 40}
        ops = enrich.plan(rec)
        self.assertEqual([op["call"] for op in ops],
                         ["company-information-from-domain"])
        self.assertEqual(enrich.exposure(ops)["maximum"], 1)

    def test_the_dry_run_charges_the_budget_the_maximum_not_the_expected(self):
        """`run(live=False)` reports the worst case as "committed".

        `run` charges every planned op, conditional or not, so
        `result["spent"]` is the maximum exposure while the printed
        "expected credit spend" is the smaller number. Sizing a cap against
        the dry run's committed figure over-reserves by 30% on a qualified
        record - safe, but not the same question - and a dry run *with* a
        cap refuses ops a live run would never make.
        """
        store.append([self.qualified(i) for i in range(10)])
        result = enrich.run(live=False)
        expected = sum(enrich.exposure(r["ops"])["expected"]
                       for r in result["records"])
        maximum = sum(enrich.exposure(r["ops"])["maximum"]
                      for r in result["records"])
        self.assertEqual(expected, 100)
        self.assertEqual(maximum, 130)
        self.assertEqual(result["spent"], maximum)
        self.assertNotEqual(result["spent"], expected)

    def test_the_forecast_cannot_see_verification_at_upload_time(self):
        """A domain-only record forecasts no verification, and then buys some.

        `enrich.plan` prices verification per contact that already carries
        an address. A freshly imported domain carries none, so the forecast
        for a 30,000-domain TAM contains zero verification credits - and
        every address `decision-makers` returns then needs between one and
        three. The forecast is not wrong about what it priced; it is
        incomplete about the run, and the gap is not marked.
        """
        rec = self.qualified(0)
        self.assertEqual([op["call"] for op in enrich.plan(rec)],
                         ["decision-makers",
                          "company-information-from-domain",
                          "aiark-people-search"])
        rec["contacts"] = [{"email": "a@q0.test", "verdict": None}]
        after = [op["call"] for op in enrich.plan(rec)]
        self.assertTrue(any("verify" in call for call in after),
                        "verification appears only once an address exists")

    def test_a_scrape_is_forecast_at_zero_credits_and_that_is_honest(self):
        """Apify bills in compute units. Zero here is "not in this currency"."""
        self.assertEqual(enrich.COSTS["apify-research"], 0)
        # Which is exactly why the credit cap cannot restrain it, and why
        # `research.RunBudget` counts starts instead.
        budget = enrich.Budget(0)
        self.assertTrue(budget.affordable(enrich.COSTS["apify-research"]))


# --------------------------------------------------------------------------
# Part 3: the 30,000-domain forecast
# --------------------------------------------------------------------------

UNKNOWN = "UNKNOWN"


def forecast(domains=TAM, qualified_rate=0.25, aiark_fallback=0.0,
             addresses_per_account=2.0, verifications_per_address=1):
    """What 30,000 domains cost, built from `enrich.COSTS` and nothing else.

    Every price is read from the module rather than written here, so a
    change to the cost table changes the forecast. Apify is reported as
    UNKNOWN rather than as zero: zero credits is true and zero *cost* is
    not, and a forecast that says zero is the one somebody budgets against.
    """
    qualified = round(domains * qualified_rate)
    addresses = round(qualified * addresses_per_account)
    lines = {
        "people-count (free, every domain)":
            domains * enrich.COSTS["people-count"],
        "company-information-from-domain (every domain)":
            domains * COMPANY_CREDITS * enrich.COSTS[
                "company-information-from-domain"],
        "decision-makers (QUALIFIED only)":
            qualified * enrich.COSTS["decision-makers"],
        "aiark-people-search (ContactOut miss)":
            round(qualified * aiark_fallback) * enrich.COSTS[
                "aiark-people-search"],
        "email verification (per address found)":
            addresses * verifications_per_address * enrich.COSTS[
                "email-verifier"],
    }
    return {
        "domains": domains,
        "qualified": qualified,
        "addresses": addresses,
        "lines": lines,
        "credits": sum(lines.values()),
        "apify_runs": round(domains * APIFY_FALLBACK),
        "apify_cost": UNKNOWN,
    }


class ThirtyThousandDomainForecast(unittest.TestCase):
    """The table, computed from the real cost tables. Nothing is invented."""

    # The qualified share is the one input the pilot ratios did not supply,
    # so it is the axis these three columns vary. Named as assumptions.
    COLUMNS = (
        ("CONSERVATIVE", dict(qualified_rate=0.10, aiark_fallback=0.0,
                              addresses_per_account=1.0,
                              verifications_per_address=1)),
        ("EXPECTED", dict(qualified_rate=0.25, aiark_fallback=0.25,
                          addresses_per_account=2.0,
                          verifications_per_address=2)),
        ("WORST", dict(qualified_rate=0.50, aiark_fallback=1.0,
                       addresses_per_account=3.0,
                       verifications_per_address=3)),
    )

    def test_the_prices_are_the_repositorys_own(self):
        self.assertEqual(enrich.COSTS["people-count"], 0)
        self.assertEqual(enrich.COSTS["company-information-from-domain"],
                         COMPANY_CREDITS)
        self.assertEqual(enrich.COSTS["decision-makers"], PERSON_CREDITS)
        self.assertEqual(enrich.COSTS["apify-research"], 0)

    def test_the_free_tier_costs_nothing_at_thirty_thousand(self):
        """52% resolving free is 15,600 domains that never reach a credit."""
        self.assertEqual(round(TAM * FREE_RESOLVE), 15_600)
        self.assertEqual(round(TAM * FREE_RESOLVE)
                         * enrich.COSTS["people-count"], 0)

    def test_apify_is_reported_unknown_and_never_priced(self):
        for _label, assumptions in self.COLUMNS:
            with self.subTest(_label):
                result = forecast(**assumptions)
                self.assertEqual(result["apify_cost"], UNKNOWN)
                self.assertEqual(result["apify_runs"], 7_800)
                self.assertNotIn("apify", " ".join(result["lines"]))

    def test_the_three_columns_are_ordered_and_add_up(self):
        totals = [forecast(**a)["credits"] for _l, a in self.COLUMNS]
        self.assertEqual(totals, sorted(totals))
        for _label, assumptions in self.COLUMNS:
            with self.subTest(_label):
                result = forecast(**assumptions)
                self.assertEqual(sum(result["lines"].values()),
                                 result["credits"])

    def test_the_company_first_floor_is_the_whole_list(self):
        """Every domain pays one company credit before anybody is qualified."""
        result = forecast(qualified_rate=0.0, addresses_per_account=0)
        self.assertEqual(result["credits"], TAM * COMPANY_CREDITS)

    def test_person_spend_scales_only_with_qualified_accounts(self):
        low = forecast(qualified_rate=0.10, aiark_fallback=0,
                       addresses_per_account=0)
        high = forecast(qualified_rate=0.20, aiark_fallback=0,
                        addresses_per_account=0)
        self.assertEqual(high["credits"] - low["credits"],
                         round(TAM * 0.10) * PERSON_CREDITS)

    def test_the_forecast_agrees_with_what_plan_says_per_record(self):
        """One qualified record, priced by hand and by `enrich.plan`."""
        rec = store.new_record("q", "domains", "productive", "Q", "q.test")
        rec["company_facts"] = {"headcount_signal": 40}
        rec["qualification"] = {"verdict": {"icp_status": icp.QUALIFIED}}
        per_record = forecast(domains=1, qualified_rate=1.0,
                              aiark_fallback=0.0, addresses_per_account=0)
        self.assertEqual(per_record["credits"],
                         COMPANY_CREDITS + PERSON_CREDITS)
        self.assertEqual(enrich.exposure(enrich.plan(rec))["maximum"],
                         COMPANY_CREDITS + PERSON_CREDITS + 2)   # + AI Ark


if __name__ == "__main__":
    unittest.main()
