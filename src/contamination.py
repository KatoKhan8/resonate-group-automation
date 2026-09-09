#!/usr/bin/env python3
"""State files known to hold test fixtures, and what may not be concluded.

WHY THIS IS A MODULE RATHER THAN A NOTE. Until `a191a2a` the second barrier
covered only `work/queue.jsonl`, so any test that forgot to isolate the store
wrote into whichever other state file it touched. Two files took real damage:
`report-drafts.jsonl` collected sixteen `a@b.test` rows per suite run since
2026-08-28, and `replywatch.json` holds `RuntimeError: still on fire` from
`tests/test_replywatch.py`.

The barrier is closed now, so nothing new can land. What is not closed is the
reading of what is already there - and that already cost something. PRODUCT-
GAPS section 22 item 9 cited `work/replywatch.json` as evidence that reply
detection is down. The conclusion happened to be true, but a red team had read
test fixtures as a production signal, and nothing on any screen said the file
was contaminated.

Clearing the files is a destructive write to client state and is a human
decision, deliberately not taken here. So the registry stands in for it: while
a file is listed, anything read from it is inadmissible as evidence about a
client, and `python -m src.check` says so where an operator is already looking.

REMOVING AN ENTRY. Only when the file has actually been cleared or rebuilt -
not because it looks plausible again, and not because the fixtures are old. A
registry somebody trims to make a report look clean is worse than no registry.
"""
import argparse
import json
import os

from . import store


class Contaminated:
    """One state file, why it is untrustworthy, and what not to conclude."""

    def __init__(self, filename, marker, why, do_not_conclude, since):
        self.filename = filename
        self.marker = marker            # a string proving fixtures are present
        self.why = why
        self.do_not_conclude = do_not_conclude
        self.since = since

    def path(self):
        return os.path.join(os.path.dirname(store.queue_path()), self.filename)

    def present(self):
        """Is the file still there at all?"""
        return os.path.exists(self.path())

    def proven(self):
        """Is the fixture marker still in it?

        Read rather than assumed. The registry says a file *was* contaminated;
        this says whether it still is, so an entry cannot outlive its subject
        and quietly go on discrediting a file somebody has since rebuilt. The
        caution learned twice on this project applies - "the file exists" and
        "the hash did not change" were each treated as proof and each was
        wrong - so the content is what is checked.
        """
        try:
            with open(self.path(), encoding="utf-8") as handle:
                return self.marker in handle.read()
        except OSError:
            return False

    def report(self):
        return {
            "file": self.filename,
            "path": self.path(),
            "present": self.present(),
            "fixtures_still_present": self.proven(),
            "why": self.why,
            "do_not_conclude": self.do_not_conclude,
            "since": self.since,
        }


REGISTRY = (
    Contaminated(
        "report-drafts.jsonl",
        marker="a@b.test",
        why=("every row carries created_by a@b.test, a reserved-TLD fixture "
             "address. 4,944 rows had accumulated at sixteen per suite run "
             "since 2026-08-28, because tests/test_report_editor.py created "
             "real drafts with no store isolation"),
        do_not_conclude=("that any client has ever had a report drafted. No "
                         "genuine draft exists in this file - not one row has "
                         "a real author"),
        since="2026-08-28",
    ),
    Contaminated(
        "replywatch.json",
        marker="still on fire",
        why=("holds `RuntimeError: still on fire` and `RuntimeError: no` from "
             "tests/test_replywatch.py, interleaved with real-looking poller "
             "rows, because replywatch wrote its own temp-file-and-replace "
             "outside the store barrier"),
        do_not_conclude=("anything about reply-watcher health from this file. "
                         "Whether reply detection is running is answerable "
                         "from work/checkpoints.json and from whether "
                         "credentials are configured - not from here. "
                         "PRODUCT-GAPS 22 item 9 made exactly this mistake"),
        since="2026-09-02",
    ),
    Contaminated(
        "tag-outbox.jsonl",
        marker="sven.halvorsen@wintergreen.test",
        why=("6,436 rows, every one workspace `demo`, and only three distinct "
             "record ids - `wintergreen` 6,424 times, plus `t` and `acme`. "
             "None of the three exists in the queue, so every row is orphaned. "
             "`tests/test_demo_outreach.py` and `tests/test_invariants.py` both "
             "diagnosed this in prose and neither registered it, so it went on "
             "growing: 2.8MB"),
        do_not_conclude=("that any provider tag has ever been queued for a real "
                         "client. Not one row belongs to productive, contactout "
                         "or demo-client"),
        since="2026-08-29",
    ),
    Contaminated(
        "signals.jsonl",
        marker="walk-",
        why=("all 50 rows are `walk-0` .. `walk-49`, byte-identical except the "
             "id, and `walk-` appears nowhere in src/ so no production or demo "
             "path can produce them. These are the same fixtures that replaced "
             "the real queue during the incident; the queue was restored and "
             "this file was not"),
        do_not_conclude=("that any account has a hiring surge or any other "
                         "signal. Worse than stale: `signals.install` REPLACES "
                         "the file, so whatever was here before was truncated "
                         "rather than merged around, and no genuine signal "
                         "survives to be preserved"),
        since="2026-08-27",
    ),
)


def contaminated_files():
    """Only the entries whose fixtures are still demonstrably in place."""
    return [entry for entry in REGISTRY if entry.proven()]


def is_contaminated(filename):
    return any(entry.filename == filename for entry in contaminated_files())


def report():
    return [entry.report() for entry in REGISTRY]


def check():
    """A `src.check`-shaped result, so it prints beside the provider sweep.

    FAIL rather than SKIP when a file is still contaminated: this is a real
    condition with a real consequence, and a diagnostic nobody can fail is a
    diagnostic nobody reads.
    """
    dirty = contaminated_files()
    if not dirty:
        return {"provider": "State files", "ok": True, "status": None,
                "skipped": False,
                "note": "no state file is holding known test fixtures"}
    names = ", ".join(entry.filename for entry in dirty)
    return {
        "provider": "State files", "ok": False, "status": None,
        "skipped": False,
        "note": (f"{len(dirty)} file(s) hold test fixtures and are NOT client "
                 f"truth: {names}. Run `python -m src.contamination` for what "
                 f"may not be concluded from each."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.contamination",
                                description=__doc__)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    rows = report()
    if a.json:
        print(json.dumps({"contaminated": rows}, indent=2, sort_keys=True))
        return 1 if any(r["fixtures_still_present"] for r in rows) else 0

    dirty = [r for r in rows if r["fixtures_still_present"]]
    if not dirty:
        print("No state file is holding known test fixtures.")
        for r in rows:
            print(f"  cleared: {r['file']} (registered {r['since']})")
        return 0

    print(f"{len(dirty)} state file(s) hold test fixtures. "
          f"NOT client truth.\n")
    for r in dirty:
        print(f"  {r['file']}   contaminated since {r['since']}")
        print(f"    why              : {r['why']}")
        print(f"    do NOT conclude  : {r['do_not_conclude']}")
        print()
    print("Clearing these is a destructive write to client state and needs a "
          "human decision. Until then, nothing read from them is evidence "
          "about a client.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
