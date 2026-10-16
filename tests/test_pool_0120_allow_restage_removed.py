"""Test that write_linkedin_lead_variables.py:150 does not pass allow_restage.

This test is born red on the base tree (which passes allow_restage=True) and
killed by the patch (which removes it). The test asserts the call site does
NOT pass allow_restage, which is the minimal fix that makes the call enter
the braked seam instead of falling through to the ungated transport.

The defect: line 150 passed allow_restage=True to stage_lead, which doesn't
accept it. TypeError fired at argument binding, caught by except TypeError,
which bypassed stage_lead entirely and called heyreach.add_leads_to_list
directly — no brake, no gate, no audit.

The fix: remove allow_restage=True from the call. This makes the call bind
successfully, enter stage_lead, and go through the braked seam (once the
brake branch task-glm-c-0164-brake-ship is merged).
"""
import ast
import unittest


class TestAllowRestageRemoved(unittest.TestCase):
    """The call site at write_linkedin_lead_variables.py:150 must not pass
    allow_restage, because stage_lead doesn't accept it and the TypeError
    bypasses the braked seam."""

    def test_call_site_does_not_pass_allow_restage(self):
        """RED on base tree, GREEN on patched tree.

        Parse the script and find the stage_lead call. Assert it does not
        pass allow_restage as a keyword argument.
        """
        with open("scripts/write_linkedin_lead_variables.py", "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the stage_lead call
        stage_lead_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is a call to stage_lead
                if isinstance(node.func, ast.Attribute):
                    if (node.func.attr == "stage_lead" and
                        isinstance(node.func.value, ast.Name) and
                        node.func.value.id == "liststaging"):
                        stage_lead_calls.append(node)

        self.assertEqual(len(stage_lead_calls), 1,
                        f"Expected exactly 1 stage_lead call, found {len(stage_lead_calls)}")

        call = stage_lead_calls[0]

        # Check that allow_restage is NOT in the keywords
        for kw in call.keywords:
            self.assertNotEqual(kw.arg, "allow_restage",
                              "stage_lead call must not pass allow_restage; "
                              "the kwarg is not accepted by the signature and "
                              "causes TypeError that bypasses the braked seam")

    def test_signature_does_not_accept_allow_restage(self):
        """The stage_lead signature must not accept allow_restage.

        This asserts the invariant: if the signature doesn't accept it, the
        call site must not pass it. If a future change adds allow_restage to
        the signature, this test must be updated alongside the call site.
        """
        with open("src/liststaging.py", "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the stage_lead definition
        stage_lead_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "stage_lead":
                stage_lead_def = node
                break

        self.assertIsNotNone(stage_lead_def, "stage_lead not found in src/liststaging.py")

        # Check that allow_restage is NOT in the parameters
        param_names = []
        for arg in stage_lead_def.args.args:
            param_names.append(arg.arg)
        for arg in stage_lead_def.args.kwonlyargs:
            param_names.append(arg.arg)

        has_varkeyword = stage_lead_def.args.kwarg is not None

        self.assertNotIn("allow_restage", param_names,
                        "stage_lead signature must not accept allow_restage; "
                        "the parameter is not implemented and accepting it "
                        "would be a silent no-op")

        self.assertFalse(has_varkeyword,
                        "stage_lead signature must not have **kwargs; "
                        "this would silently accept allow_restage without "
                        "implementing it")


if __name__ == "__main__":
    unittest.main()
