"""The read command that answers for one prospect, or says it cannot.

TASK 0230, section 3. The write ledger records every attempt through the
door; nothing reads it back per prospect. When a canary prospect replies
with something unexpected, the first question is "what did they receive,
and when" - and the answer has to come from this file, in order, with the
step (named since TASK 0230 section 2) and who drove the write.

`scripts/read_prospect_writes.py --email <address>` is that command. These
tests pin its contract:

  - a planted sequence comes back IN ORDER, with timestamp, verb, campaign,
    step and `by=` - the five fields the brief names;
  - a staging row (a pause, a resume - no authorization, no prospect) is
    not this prospect's write and does not poison the account;
  - the command is read-only: the ledger and the queue are byte-identical
    before and after;
  - an old row from before the step change - prospect-facing, no contact
    key - is an UNACCOUNTABLE WINDOW: the output says so and exits 2
    rather than printing a clean-looking list that happens to miss it;
  - an unparseable line is named, not skipped;
  - a timestamp that goes backwards breaks the "in order" claim, and the
    output withdraws it;
  - an email the store cannot resolve is NOT a clean empty answer, and a
    missing ledger is not either. Fail-closed means the command refuses to
    look complete when it cannot know.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

_SPEC = importlib.util.spec_from_file_location(
    "read_prospect_writes",
    os.path.join(ROOT, "scripts", "read_prospect_writes.py"))
COMMAND = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(COMMAND)


EMAIL = "jane.doe@example.com"


def attributed(at, step, operation="heyreach.add_lead", outcome="sent",
               campaign="c605732", by="canary", rec="rec1",
               contact="jane-doe"):
    return {"at": at, "operation": operation, "outcome": outcome,
            "campaign": campaign, "step": step, "by": by,
            "key": f"{rec}:{contact}:{step}:linkedin"}


class _Planted(unittest.TestCase):
    """A throwaway queue with one record, and a throwaway ledger.

    Never the real `work/`: the queue names a real person and the ledger is
    the operator's own audit trail.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-read-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.queue = os.path.join(self.tmp, "queue.jsonl")
        self.ledger = os.path.join(self.tmp, "provider-writes.jsonl")
        with io.open(self.queue, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "id": "rec1", "state": "queued",
                "contacts": [{"key": "jane-doe", "email": EMAIL}],
            }) + "\n")
        self._old = {name: os.environ.get(name) for name in
                     ("QUEUE", "PROVIDER_WRITES_LEDGER")}
        os.environ["QUEUE"] = self.queue
        os.environ["PROVIDER_WRITES_LEDGER"] = self.ledger
        self.addCleanup(self._restore)

    def _restore(self):
        for name, value in self._old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def plant(self, *rows):
        """Rows may be dicts (a JSON line) or str (written verbatim - the
        way an unparseable line gets planted)."""
        with io.open(self.ledger, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(row if isinstance(row, str)
                         else json.dumps(row, ensure_ascii=False))
                fh.write("\n")

    def run_command(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = COMMAND.main(["--email", EMAIL] + list(extra), _out=out)
        return code, out.getvalue()

    def bytes_of(self, path):
        with io.open(path, "rb") as fh:
            return fh.read()


class TheReadCommandReconstructsAPlantedSequence(_Planted):

    def test_in_order_with_every_field_the_brief_names(self):
        """Three writes across two channels come back in the order they
        landed, each carrying timestamp, verb, campaign, step and by=."""
        self.plant(
            attributed("2026-10-14T09:00:00Z", "li1"),
            attributed("2026-10-14T09:00:00Z", "em1", operation="bison.push_lead",
                       outcome="performed", by="canary-worker"),
            attributed("2026-10-15T11:30:00Z", "li2", outcome="refused"),
        )
        code, out = self.run_command()
        self.assertEqual(0, code, out)
        self.assertIn("rec1", out)
        self.assertIn("jane-doe", out)
        for needle in ("2026-10-14T09:00:00Z", "heyreach.add_lead", "sent",
                       "c605732", "li1", "canary",
                       "bison.push_lead", "canary-worker",
                       "2026-10-15T11:30:00Z", "li2", "refused"):
            self.assertIn(needle, out, f"the account lost {needle!r}")
        self.assertLess(out.index("li1"), out.index("em1"))
        self.assertLess(out.index("em1"), out.index("li2"))
        self.assertIn("complete", out)

    def test_a_staging_row_is_not_this_prospects_write(self):
        """A pause is a provider write, but it is a campaign-scoped one with
        no prospect and no authorization. It must not be attributed to
        jane.doe and must not turn their account partial."""
        self.plant(
            attributed("2026-10-14T09:00:00Z", "li1"),
            {"at": "2026-10-14T10:00:00Z", "operation": "bison.pause",
             "outcome": "refused", "campaign": "c491", "step": "UNKNOWN",
             "key": "UNKNOWN", "by": "operator"},
        )
        code, out = self.run_command()
        self.assertEqual(0, code, out)
        self.assertNotIn("bison.pause", out.split("account:")[0],
                         "a staging row was printed as this prospect's write")
        self.assertIn("complete", out)

    def test_the_command_changes_nothing_on_disk(self):
        """Read-only means read-only: both files byte-identical after."""
        self.plant(attributed("2026-10-14T09:00:00Z", "li1"))
        before = (self.bytes_of(self.queue), self.bytes_of(self.ledger))
        self.run_command()
        after = (self.bytes_of(self.queue), self.bytes_of(self.ledger))
        self.assertEqual(before, after, "the read command wrote something")


class AGapInTheLedgerMakesTheOutputSaySo(_Planted):

    def test_an_old_row_with_no_key_is_an_unaccountable_window(self):
        """The row shape before TASK 0230: a prospect-facing write with no
        contact key. It might be jane.doe's and it might not - the ledger
        cannot say - so a clean list of the attributable rows would be a
        lie by omission. The output must name the window and exit 2."""
        self.plant(
            attributed("2026-10-14T09:00:00Z", "li1"),
            {"at": "2026-10-14T10:00:00Z", "operation": "heyreach.add_lead",
             "outcome": "performed", "campaign": "c605732", "by": "canary"},
            attributed("2026-10-15T11:30:00Z", "li2"),
        )
        code, out = self.run_command()
        self.assertEqual(2, code, "an unaccountable window exited clean")
        self.assertIn("INCOMPLETE", out)
        self.assertIn("heyreach.add_lead", out)
        self.assertIn("cannot be attributed", out)
        self.assertIn("NOT every write", out)
        # The attributable rows are still printed - partial, not empty.
        self.assertIn("li1", out)
        self.assertIn("li2", out)

    def test_an_unparseable_line_is_named_not_skipped(self):
        """A truncated or corrupt line is a hole in the audit trail. The
        command names it by line number and refuses the clean exit."""
        self.plant(
            attributed("2026-10-14T09:00:00Z", "li1"),
            '{"at": "2026-10-14T10:00:00Z", "operation": "bison.p',
        )
        code, out = self.run_command()
        self.assertEqual(2, code)
        self.assertIn("unreadable", out.lower())
        self.assertIn("line 2", out)

    def test_a_timestamp_that_goes_backwards_breaks_the_order_claim(self):
        """An append-only ledger never goes back in time; one that does has
        been edited or merged, and `in order` stops being a claim this file
        can support. Say so rather than sorting silently."""
        self.plant(
            attributed("2026-10-15T11:30:00Z", "li2"),
            attributed("2026-10-14T09:00:00Z", "li1"),
        )
        code, out = self.run_command()
        self.assertEqual(2, code)
        self.assertIn("backwards", out)


class AnEmailTheStoreCannotResolveIsNotACleanEmptyList(_Planted):

    def test_no_record_no_clean_zero(self):
        """An email no record holds is UNKNOWN, not zero: maybe a typo,
        maybe a mailbox this system never enrolled. Printing an empty
        account would read as 'nothing was ever sent', which is exactly the
        clean-looking answer the brief forbids."""
        self.plant(attributed("2026-10-14T09:00:00Z", "li1"))
        out = io.StringIO()
        with redirect_stdout(out):
            code = COMMAND.main(["--email", "nobody@nowhere.test"], _out=out)
        self.assertEqual(2, code)
        self.assertIn("CANNOT ACCOUNT", out.getvalue())

    def test_no_ledger_file_no_clean_zero(self):
        """A missing ledger cannot account for any window, including every
        window before the file was created. Exit 2, never an empty list."""
        out = io.StringIO()
        with redirect_stdout(out):
            code = COMMAND.main(["--email", EMAIL], _out=out)
        self.assertEqual(2, code)
        self.assertIn("CANNOT ACCOUNT", out.getvalue())


if __name__ == "__main__":
    unittest.main()
