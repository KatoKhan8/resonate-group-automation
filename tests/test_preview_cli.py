"""The command a person actually types, and what it refuses to do.

    python -m src.preview --client productive --batch 2026-08

One command, five files, nothing sent. The tests here run the CLI itself
rather than the functions behind it, because a working library behind a broken
entry point is a preview nobody can produce.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stdout

from src import campaigns, preview, previewpage, simulator, store, synthetic
from tests.campaignbase import CampaignTest


class PreviewCLITest(CampaignTest):
    def seeded(self, client="demo", batch="batch-1", size=28):
        recs = synthetic.dataset(size, self.config)
        for rec in recs:
            rec["client"] = client
            rec["batch"] = batch
        store.save(recs)
        return store.load()

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = preview.main(list(argv))
        return code, out.getvalue()


class TestTheSuggestedCommand(PreviewCLITest):
    def test_a_client_and_batch_produce_the_five_files(self):
        self.seeded()
        code, output = self.run_cli("--client", "demo", "--batch", "batch-1")
        self.assertEqual(code, 0)
        for name in previewpage.FILES:
            self.assertIn(name, output, name)
            self.assertTrue(os.path.exists(os.path.join(store.out_dir(), name)))

    def test_a_client_alone_works_without_a_batch(self):
        self.seeded()
        code, output = self.run_cli("--client", "demo")
        self.assertEqual(code, 0)
        self.assertIn("preview.html", output)

    def test_it_says_it_would_send_nothing(self):
        self.seeded()
        _, output = self.run_cli("--client", "demo")
        self.assertIn("would send: 0", output)
        self.assertIn("Nothing was sent", output)

    def test_the_headline_is_printed_for_a_human(self):
        self.seeded()
        _, output = self.run_cli("--client", "demo")
        for word in ("companies", "contacts", "emailable", "on LinkedIn",
                     "held"):
            self.assertIn(word, output, word)

    def test_a_batch_narrows_the_preview(self):
        recs = self.seeded(batch="batch-1")
        recs[0]["batch"] = "batch-2"
        store.save(recs)
        self.run_cli("--client", "demo", "--batch", "batch-2")
        with open(os.path.join(store.out_dir(), "preview.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["headline"]["companies"], 1)

    def test_an_unknown_client_produces_an_empty_preview_not_a_crash(self):
        self.seeded()
        code, output = self.run_cli("--client", "nobody")
        self.assertEqual(code, 0)
        with open(os.path.join(store.out_dir(), "preview.json"),
                  encoding="utf-8") as f:
            self.assertEqual(json.load(f)["headline"]["companies"], 0)

    def test_addresses_are_masked_unless_asked_for(self):
        recs = self.seeded()
        self.run_cli("--client", "demo")
        with open(os.path.join(store.out_dir(), "preview.html"),
                  encoding="utf-8") as f:
            page = f.read()
        address = next(c["email"] for r in recs for c in r["contacts"]
                       if c.get("email"))
        self.assertNotIn(address, page)

        self.run_cli("--client", "demo", "--reveal-emails")
        with open(os.path.join(store.out_dir(), "preview.html"),
                  encoding="utf-8") as f:
            self.assertIn(address, f.read())

    def test_the_card_cap_can_be_set_from_the_command_line(self):
        self.seeded()
        self.run_cli("--client", "demo", "--max-cards", "3")
        with open(os.path.join(store.out_dir(), "preview.html"),
                  encoding="utf-8") as f:
            self.assertIn("are not shown on this page", f.read())

    def test_no_provider_was_called(self):
        self.seeded()
        self.run_cli("--client", "demo")
        self.assertEqual(self.cassette.calls, [])


class TestTheCampaignPathStillWorks(PreviewCLITest):
    def test_a_campaign_id_still_writes_the_single_page(self):
        campaign, _, _ = self.approved_campaign()
        code, output = self.run_cli(campaign["campaign_id"])
        self.assertEqual(code, 0)
        self.assertIn("Read-only", output)

    def test_an_unknown_campaign_is_refused_rather_than_guessed_at(self):
        code, output = self.run_cli("no-such-campaign")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", output)

    def test_the_demo_path_still_works(self):
        code, output = self.run_cli("--demo")
        self.assertEqual(code, 0)
        self.assertIn("Fictional data only", output)


class TestTheOtherEntryPoints(PreviewCLITest):
    def test_the_previewpage_module_runs_standalone(self):
        self.seeded()
        out = io.StringIO()
        with redirect_stdout(out):
            code = previewpage.main(["--client", "demo"])
        self.assertEqual(code, 0)
        self.assertIn("Nothing was sent", out.getvalue())

    def test_the_simulator_module_prints_the_headline(self):
        self.seeded()
        out = io.StringIO()
        with redirect_stdout(out):
            code = simulator.main(["--client", "demo"])
        self.assertEqual(code, 0)
        self.assertIn("would send", out.getvalue())

    def test_the_simulator_refuses_an_unknown_campaign(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = simulator.main(["--campaign", "nope"])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", out.getvalue())


if __name__ == "__main__":
    unittest.main()
