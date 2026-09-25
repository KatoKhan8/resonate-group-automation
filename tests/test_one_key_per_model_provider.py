"""One name per provider, and a drift between two names is visible.

On 2026-09-25 OpenRouter was authenticated through `LLM_API_KEY` while
`OPENROUTER_API_KEY` was added separately for the Groq fallback. Both held the
same credential - two names for one key, which is how a rotation gets
half-applied and the provider fails only on the modules reading the other one.
"""
import os
import unittest
from unittest import mock

from src import config, providers


class OneKeyPerProvider(unittest.TestCase):

    def setUp(self):
        self._env = dict(os.environ)
        for name in ("OPENROUTER_API_KEY", "LLM_API_KEY", "GROQ_API_KEY",
                     "LLM_BASE_URL", "LLM_MODEL"):
            os.environ.pop(name, None)
        # load_env() must not repopulate from the real config/.env
        patcher = mock.patch.object(providers, "load_env", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_the_canonical_name_wins(self):
        os.environ["OPENROUTER_API_KEY"] = "canonical"
        os.environ["LLM_API_KEY"] = "legacy"
        value, found_as = providers.model_key("openrouter")
        self.assertEqual(value, "canonical")
        self.assertEqual(found_as, "OPENROUTER_API_KEY")

    def test_the_legacy_name_still_answers(self):
        # Removing it would authenticate the next deploy and nothing already
        # running: ~20 loops import at start and never reload.
        os.environ["LLM_API_KEY"] = "legacy"
        value, found_as = providers.model_key("openrouter")
        self.assertEqual(value, "legacy")
        self.assertEqual(found_as, "LLM_API_KEY")

    def test_absent_raises_and_names_the_canonical_spelling(self):
        with self.assertRaises(providers.MissingKey) as caught:
            providers.model_key("openrouter")
        self.assertIn("OPENROUTER_API_KEY", str(caught.exception))

    def test_absent_is_none_when_not_required(self):
        self.assertEqual(providers.model_key("openrouter", required=False),
                         (None, None))

    def test_an_unknown_provider_is_refused_not_guessed(self):
        with self.assertRaises(providers.MissingKey):
            providers.model_key("definitely-not-a-provider")

    def test_drift_between_two_names_is_reported(self):
        os.environ["OPENROUTER_API_KEY"] = "one"
        os.environ["LLM_API_KEY"] = "two"
        drift = providers.model_key_drift("openrouter")
        self.assertEqual(set(drift), {"OPENROUTER_API_KEY", "LLM_API_KEY"})

    def test_the_same_key_under_two_names_is_not_drift(self):
        os.environ["OPENROUTER_API_KEY"] = "same"
        os.environ["LLM_API_KEY"] = "same"
        self.assertEqual(providers.model_key_drift("openrouter"), {})

    def test_drift_never_returns_a_credential(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-secret-one"
        os.environ["LLM_API_KEY"] = "sk-secret-two"
        rendered = repr(providers.model_key_drift("openrouter"))
        self.assertNotIn("sk-secret-one", rendered)
        self.assertNotIn("sk-secret-two", rendered)

    def test_both_names_are_registered_so_health_can_see_them(self):
        # `credential_health.py` reads the registry and so cannot invent a
        # name. A variable that is set but unregistered is invisible to it.
        names = {name for name, _c, _g, _w in config.VARIABLES}
        self.assertIn("OPENROUTER_API_KEY", names)
        self.assertIn("GROQ_API_KEY", names)


class TheGenericSeamDoesNotLeakTheKey(unittest.TestCase):
    """`LLM_BASE_URL` may point anywhere. The OpenRouter key may not follow."""

    def setUp(self):
        self._env = dict(os.environ)
        for name in ("OPENROUTER_API_KEY", "LLM_API_KEY", "LLM_BASE_URL",
                     "LLM_MODEL"):
            os.environ.pop(name, None)
        patcher = mock.patch.object(providers, "load_env", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def _client(self):
        from src import llm
        return llm.OpenAICompatibleModel()

    def test_openrouter_key_is_used_when_the_endpoint_is_openrouter(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-openrouter"
        os.environ["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
        os.environ["LLM_MODEL"] = "openai/gpt-oss-120b"
        self.assertTrue(self._client().configured())

    def test_openrouter_key_is_NOT_sent_to_a_local_server(self):
        # Handing a live OpenRouter credential to a local model server sends
        # it somewhere it was never meant to go. Unconfigured is the safer
        # failure, and it is the one that must happen.
        os.environ["OPENROUTER_API_KEY"] = "sk-openrouter"
        os.environ["LLM_BASE_URL"] = "http://127.0.0.1:11434/v1"
        os.environ["LLM_MODEL"] = "llama"
        client = self._client()
        self.assertFalse(client.configured())
        self.assertIn("LLM_API_KEY", client.why_not())

    def test_an_explicit_key_still_wins_everywhere(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-openrouter"
        os.environ["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
        os.environ["LLM_MODEL"] = "m"
        from src import llm
        self.assertTrue(llm.OpenAICompatibleModel(key="explicit").configured())


if __name__ == "__main__":
    unittest.main()
