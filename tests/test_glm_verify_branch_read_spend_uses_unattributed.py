"""_read_spend reads 'unattributed' GLM rows, not the old '_model' client.

TASK-395. TASK-346 changed the GLM provider's default client from '_model'
to 'unattributed', but scripts/glm_verify_branch.py:_read_spend still
filtered by client=='_model' - finding zero rows. This test proves the
function reads the correct client value after the fix.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store                        # noqa: E402
from scripts.glm_verify_branch import _read_spend         # noqa: E402


class ReadSpendUsesUnattributed(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task395-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        spendledger.new_run(f"test-{id(self)}")

    def test_read_spend_counts_unattributed_glm_rows(self):
        """Rows with client='unattributed' and provider='glm' are counted."""
        spendledger.record("unattributed", "glm", "complete:glm-5.3", 2560,
                           unit="microusd")
        spendledger.record("unattributed", "glm", "complete:glm-5.3", 1280,
                           unit="microusd")
        n, cost = _read_spend()
        self.assertEqual(2, n)
        self.assertEqual(3840, cost)

    def test_read_spend_ignores_old_model_client(self):
        """Rows with the old client='_model' are NOT counted."""
        spendledger.record("_model", "glm", "complete:glm-5.3", 5000,
                           unit="microusd")
        n, cost = _read_spend()
        self.assertEqual(0, n)
        self.assertEqual(0, cost)

    def test_read_spend_ignores_other_clients_glm_rows(self):
        """GLM rows attributed to a real client are not counted."""
        spendledger.record("acme", "glm", "complete:glm-5.3", 9999,
                           unit="microusd")
        n, cost = _read_spend()
        self.assertEqual(0, n)
        self.assertEqual(0, cost)

    def test_read_spend_ignores_non_glm_unattributed(self):
        """Non-GLM unattributed rows are not counted."""
        spendledger.record("unattributed", "anthropic", "complete:sonnet",
                           5000, unit="microusd")
        n, cost = _read_spend()
        self.assertEqual(0, n)
        self.assertEqual(0, cost)


if __name__ == "__main__":
    unittest.main()
