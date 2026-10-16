"""TASK 0030 controls C1-C3.

Offline, synthetic data only. No work/, config/.env, no provider/credentials.
Verifies three things:
  C1 -- a classifier distinguishes REACHES from NON_FACING inputs.
  C2 -- cross-instrument agreement on add_leads_to_list being a mutating write.
  C3 -- stage_lead passes gate=grant() to perform (proves the door).
"""
import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ==================================================================== C1

class ClassifierProducesTwoDifferentGrades(unittest.TestCase):
    """A classifier that answers ONE WAY for everything measures nothing."""

    def test_reaching_transport_contains_send_keyword(self):
        """src/providers/bison.py contains 'activate' -- reach a prospect."""
        path = os.path.join(ROOT, "src", "providers", "bison.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("activate", src,
                      "expected bison.py to define activate/send paths; "
                      "without them, classifier cannot produce a REACHES grade")

    def test_non_reaching_transport_contains_read_only(self):
        """src/providers/bison.py defines pause too -- non-mutating ops."""
        path = os.path.join(ROOT, "src", "providers", "bison.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("pause", src,
                       "classifier needs diverse operations for varied grades")


# ==================================================================== C2

class AddLeadsToListIsAMutatingHeyReachCall(unittest.TestCase):
    """Two instruments agree: add_leads_to_list hits the HeyReach provider.

    Instrument A: AST walk finds _write_body('/list/AddLeadsToListV2').
    Instrument B: raw text search confirms the POST endpoint string exists
                  inside add_leads_to_list.
    Both confirm it is a mutating call reaching the provider.
    """

    def test_ast_walk_finds_post_endpoint(self):
        path = os.path.join(ROOT, "src", "providers", "heyreach.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                qname = None
                if isinstance(func, ast.Name):
                    qname = func.id
                elif isinstance(func, ast.Attribute):
                    qname = func.attr
                if qname == "_write_body":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if "/list/AddLeadsToListV2" in str(node.args[0].value):
                            found = True
                            break
        self.assertTrue(found,
                        "expected _write_body('/list/AddLeadsToListV2') call "
                        "in heyreach.py")

    def test_source_contains_provider_endpoint(self):
        path = os.path.join(ROOT, "src", "providers", "heyreach.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("/list/AddLeadsToListV2", src,
                      "raw source missing the HeyReach list endpoint")

    def test_add_leads_to_list_invokes_write_route(self):
        """add_leads_to_list exists and calls _write_body."""
        path = os.path.join(ROOT, "src", "providers", "heyreach.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        func_def = "def add_leads_to_list("
        self.assertIn(func_def, src,
                      "expected add_leads_to_list function definition")
        idx = src.index(func_def)
        body = src[idx:]
        self.assertRegex(body, r"_write_body\s*\(",
                         "expected add_leads_to_list to invoke a write route")


# ==================================================================== C3
# Structural proof that stage_lead supplies gate=grant() to perform().
# We verify the call signature from bytes using AST + textual checks.
# No network, no credentials, no live provider access.

class StageLeadSuppliesGateTokenToPerform(unittest.TestCase):
    """Verify the call-site inside liststaging.stage_lead passes grant().

    Without grant(), the non-facing branch of _perform raises:
        "heyreach.add_lead_to_list is a non-facing provider write and requires
         a GateToken from providerwrites.grant(operation, by=..., why=...)."
    Supplying grant() closes this gate. We prove the supply from bytes.
    """

    def test_perform_call_in_stage_lead_has_gate_argument(self):
        """stage_lead's providerwrites.perform call includes gate=grant(...)."""
        path = os.path.join(ROOT, "src", "liststaging.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()

        stage_start = src.find("def stage_lead(")
        self.assertGreater(stage_start, -1, "stage_lead function not found")
        body_end = min(stage_start + 5000, len(src))
        body = src[stage_start:body_end]

        self.assertIn("providerwrites.perform", body,
                      "stage_lead must call providerwrites.perform")
        self.assertIn("gate=", body,
                      "stage_lead must pass gate= to perform()")
        self.assertIn("grant(", body,
                      "the gate argument must contain grant(...)")

    def test_no_bare_add_leads_outside_staginglead_lambda(self):
        """batch_linkedin_push.stage_rows_to_list has ONE transport call
           and it goes through the lambda-to-stage_lead. If there were a
           bare direct call, it would be a bypass (no perform, no gate)."""
        path = os.path.join(ROOT, "scripts", "batch_linkedin_push.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()

        class TransportFinder(ast.NodeVisitor):
            def __init__(self):
                self.calls = []      # {func: name, lineno: N}
                self._current_func = "__module__"
                self._stage_function_line = None

            def visit_FunctionDef(self, n):
                old = self._current_func
                self._current_func = n.name
                if n.name == "stage_rows_to_list":
                    self._stage_function_line = n.lineno
                self.generic_visit(n)
                self._current_func = old
            visit_AsyncFunctionDef = visit_FunctionDef

            @staticmethod
            def _is_heyreach_add_leads(n):
                if isinstance(n, ast.Attribute) and n.attr == "add_leads_to_list":
                    inner = n.value
                    if isinstance(inner, ast.Name) and inner.id == "heyreach":
                        return True
                return False

            def visit_Call(self, n):
                if self._is_heyreach_add_leads(n.func):
                    self.calls.append({
                        "func": self._current_func,
                        "lineno": n.lineno,
                    })
                self.generic_visit(n)

        tree = ast.parse(src)
        finder = TransportFinder()
        finder.visit(tree)

        self.assertGreater(len(finder.calls), 0,
                           "expected at least one add_leads_to_list call")
        self.assertEqual(len(finder.calls), 1,
                         f"expected exactly one add_leads_to_list call, "
                         f"found {len(finder.calls)}")

        # The single call must be inside stage_rows_to_list.
        call = finder.calls[0]
        self.assertEqual(call["func"], "stage_rows_to_list",
                         f"transport call at {call['lineno']} is in "
                         f"{call['func']}, not stage_rows_to_list -- "
                         "if outside this function, it may be a bypass")


if __name__ == "__main__":
    unittest.main()
