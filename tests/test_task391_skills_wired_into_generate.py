"""TASK-391: skills consumed at runtime by the REAL production entrypoint.

TASK-375 wired all five skills into generate_campaign.py, but that pipeline
has zero production callers. The real path is src/generate.py (record-centric,
python -m src.generate --live). This test proves two of the five skills
(cold_email_writing and linkedin_writing) are wired into generate.py's stages
(draft and linkedin_note) through sentinel injection:

1. Patch a skill's procedure with a sentinel string.
2. Drive generate.py's real stage function (draft or linkedin_note).
3. Prove the model's prompt contains the sentinel.

The other three skills (signal_verification, account_research,
campaign_strategy) have no corresponding stage in generate.py and are
honestly reported as such.

Guard-failure: revert the wiring, confirm the test fails for the right
reason (sentinel not seen), restore.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import generate, skills, llm, store
from tests.base import FIXTURES, pin_client_config


class _SentinelModel:
    """Records every prompt; returns a valid draft JSON."""

    name = "sentinel-test"

    def __init__(self, subject="test subject", body="test body that is long "
                 "enough to pass the word count check in lint because it needs "
                 "at least forty words to be accepted by the draft gate and "
                 "stored as a valid step in the cadence for this contact "                 "without any issues at all"):
        self.prompts = []
        self._subject = subject
        self._body = body

    def complete(self, prompt, temperature=0, client=None, config=None):
        self.prompts.append(prompt)
        return json.dumps({
            "subject": self._subject,
            "body": self._body,
        })


class _SentinelNoteModel:
    """Records every prompt; returns a valid LinkedIn note JSON."""

    name = "sentinel-note-test"

    def __init__(self):
        self.prompts = []

    def complete(self, prompt, temperature=0, client=None, config=None):
        self.prompts.append(prompt)
        return json.dumps({
            "note": "short connection note about their work",
        })


class TestColdEmailSkillReachesModel(unittest.TestCase):
    """Sentinel test: cold_email_writing procedure reaches the model via draft()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-t391-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        pin_client_config(self, linkedin_connection_note=None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cold_email_writing_sentinel_reaches_model_through_draft(self):
        """Patch cold_email_writing's procedure; prove draft()'s model sees it.

        This drives generate.py's real draft() function, not a direct call
        to the skill. The sentinel is injected into the skill's procedure,
        and the model's prompt is checked for the sentinel.
        """
        skill = skills.load("cold_email_writing")
        original_procedure = skill.procedure

        sentinel = "COLD_EMAIL_GENERATE_SENTINEL_4a7f"
        patched_procedure = sentinel + "\n" + original_procedure

        object.__setattr__(skill, "procedure", patched_procedure)
        try:
            rec = store.get("harbourline")
            contact = rec["contacts"][0]
            client = None
            model = _SentinelModel()

            generate.draft(rec, contact, "day1", model, client, sequence=None)

            sentinel_seen = any(sentinel in p for p in model.prompts)
            self.assertTrue(
                sentinel_seen,
                "the patched cold_email_writing procedure did not reach "
                "the model through draft() — generate.py is not using the "
                "skill for its draft stage"
            )
        finally:
            object.__setattr__(skill, "procedure", original_procedure)


class TestLinkedinSkillReachesModel(unittest.TestCase):
    """Sentinel test: linkedin_writing procedure reaches model via linkedin_note()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-t391-li-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        pin_client_config(self, linkedin_connection_note=None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_linkedin_writing_sentinel_reaches_model_through_linkedin_note(self):
        """Patch linkedin_writing's procedure; prove linkedin_note() sees it.

        This drives generate.py's real linkedin_note() function, not a
        direct call to the skill.
        """
        skill = skills.load("linkedin_writing")
        original_procedure = skill.procedure

        sentinel = "LINKEDIN_GENERATE_SENTINEL_8c3d"
        patched_procedure = sentinel + "\n" + original_procedure

        object.__setattr__(skill, "procedure", patched_procedure)
        try:
            rec = store.get("harbourline")
            contact = rec["contacts"][0]
            client = None
            model = _SentinelNoteModel()

            generate.linkedin_note(
                rec, contact, model, client, step_key="day3", sequence=None)

            sentinel_seen = any(sentinel in p for p in model.prompts)
            self.assertTrue(
                sentinel_seen,
                "the patched linkedin_writing procedure did not reach "
                "the model through linkedin_note() — generate.py is not "
                "using the skill for its linkedin_note stage"
            )
        finally:
            object.__setattr__(skill, "procedure", original_procedure)


class TestUnmappedStagesUnchanged(unittest.TestCase):
    """Stages without a corresponding skill still read from prompt files."""

    def test_diagnose_still_uses_prompt_file(self):
        prompt = generate._system_prompt_for("diagnose")
        file_prompt = generate.prompt_text("diagnose")
        self.assertEqual(prompt, file_prompt,
                         "diagnose should still use prompts/diagnose.md")

    def test_hook_still_uses_prompt_file(self):
        prompt = generate._system_prompt_for("hook")
        file_prompt = generate.prompt_text("hook")
        self.assertEqual(prompt, file_prompt,
                         "hook should still use prompts/hook.md")

    def test_persona_angle_still_uses_prompt_file(self):
        prompt = generate._system_prompt_for("persona_angle")
        file_prompt = generate.prompt_text("persona_angle")
        self.assertEqual(prompt, file_prompt,
                         "persona_angle should still use "
                         "prompts/persona_angle.md")


class TestStageToSkillMapping(unittest.TestCase):
    """Acceptance #1: name each stage and whether a skill feeds it."""

    def test_draft_uses_cold_email_writing(self):
        self.assertEqual(generate._STAGE_TO_SKILL.get("draft"),
                         "cold_email_writing")

    def test_linkedin_note_uses_linkedin_writing(self):
        self.assertEqual(generate._STAGE_TO_SKILL.get("linkedin_note"),
                         "linkedin_writing")

    def test_diagnose_has_no_skill(self):
        self.assertNotIn("diagnose", generate._STAGE_TO_SKILL)

    def test_hook_has_no_skill(self):
        self.assertNotIn("hook", generate._STAGE_TO_SKILL)

    def test_persona_angle_has_no_skill(self):
        self.assertNotIn("persona_angle", generate._STAGE_TO_SKILL)


class TestRenderPromptUsesSkill(unittest.TestCase):
    """render_prompt() produces output containing the skill's procedure."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-t391-render-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        pin_client_config(self, linkedin_connection_note=None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_prompt_draft_contains_skill_procedure(self):
        """render_prompt('draft', ...) includes the skill's procedure text."""
        rec = store.get("harbourline")
        contact = rec["contacts"][0]
        prompt = generate.render_prompt("draft", rec, contact, None, "day1")
        email_skill = skills.load("cold_email_writing")
        # The first line of the prompt should be from the skill's procedure
        self.assertIn(
            email_skill.procedure.split("\n")[0],
            prompt,
            "render_prompt('draft') does not contain the cold_email_writing "
            "skill's procedure"
        )

    def test_render_prompt_linkedin_note_contains_skill_procedure(self):
        """render_prompt('linkedin_note', ...) includes the skill's procedure."""
        rec = store.get("harbourline")
        contact = rec["contacts"][0]
        prompt = generate.render_prompt(
            "linkedin_note", rec, contact, None, "day3")
        li_skill = skills.load("linkedin_writing")
        self.assertIn(
            li_skill.procedure.split("\n")[0],
            prompt,
            "render_prompt('linkedin_note') does not contain the "
            "linkedin_writing skill's procedure"
        )


if __name__ == "__main__":
    unittest.main()
