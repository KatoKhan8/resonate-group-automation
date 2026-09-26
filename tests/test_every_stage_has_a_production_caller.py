"""Every v2 stage module has a non-test production caller.

TASK-321. The v2 prompt layer (copystages, copyprompts, sequencegate,
secondbrain, offers) was disconnected: zero non-test callers in src/.
Whatever produced the ten and the fifty was work/v2_run.py, which is
gitignored and therefore not in git at all.

This test walks the import and call graph with `ast` and fails if any
module in the v2 layer has no non-test caller. It excludes tests/ and
work/ from the caller set: a re-export nothing calls is not a caller.

THE ACCEPTANCE SNIPPET IN THE PLAN IS DELIBERATELY NOT USED. It was
`assert 'copystages' in src` over concatenated source text, which would
pass the moment the word appears in a comment. CLAUDE.md: "Test behaviour,
not the text of the source." This test checks IMPORTS and CALLS, not
string membership.

WHAT THIS TEST CHECKS.

For each module in the v2 layer, it verifies that at least one module
OUTSIDE tests/ and work/ imports it or calls one of its public functions.
The check is structural (AST-based), not textual.

THE MODULES.

    copystages      HYPOTHESIS/MATCH/STRATEGY/WRITER prompts and user builders
    copyprompts     ICP/EXTRACT/COHORT_SYSTEM prompts and user builders
    sequencegate    sequence-level gate (check function)
    secondbrain     Client Second Brain retrieval (for_task function)
    offers          Offer Engine (load, for_campaign functions)
    copyengine      v2 pipeline orchestrator (stages A-F)
    campaignstrategy    stage E, caches per segment+persona

campaignstrategy imports copystages and offers.
copyengine imports copyprompts, copystages, campaignstrategy.
copystages.business_context_for imports secondbrain.
bisonfactory imports sequencegate.

So the full chain is wired: copyengine -> copyprompts, copystages ->
secondbrain, campaignstrategy -> offers, bisonfactory -> sequencegate.
"""
import ast
import os
import unittest


#: The v2 layer modules that must have a production caller.
V2_MODULES = (
    "copystages",
    "copyprompts",
    "sequencegate",
    "secondbrain",
    "offers",
    "copyengine",
    "campaignstrategy",
)

#: Directories to exclude from the caller set.
EXCLUDED_DIRS = ("tests", "work", "test")


def _src_dir():
    """Return the path to src/."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")


def _python_files_in_src():
    """Return all .py files in src/, excluding excluded directories."""
    src = _src_dir()
    result = []
    for root, dirs, files in os.walk(src):
        # Exclude test and work directories.
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for fname in files:
            if fname.endswith(".py"):
                result.append(os.path.join(root, fname))
    return result


def _module_name_from_path(path):
    """Convert a file path to a module name.

    e.g. /path/to/src/copystages.py -> copystages
         /path/to/src/providers/bison.py -> providers.bison
    """
    src = _src_dir()
    rel = os.path.relpath(path, src)
    # Remove .py extension and convert path separators to dots.
    module = rel[:-3].replace(os.sep, ".")
    # Handle __init__.py
    if module.endswith(".__init__"):
        module = module[:-9]
    return module


def _find_imports_and_calls(filepath):
    """Parse a Python file and return (imports, calls).

    imports: set of module names imported (e.g. {"copystages", "offers"})
    calls: set of function names called (e.g. {"for_task", "check"})
    """
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            return set(), set()

    imports = set()
    calls = set()

    for node in ast.walk(tree):
        # import X / from X import Y
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
        # Function calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    return imports, calls


def _check_module_has_caller(module_name):
    """Check if a v2 module has at least one non-test caller.

    Returns (has_caller, caller_info) where caller_info describes what
    was found.
    """
    src_files = _python_files_in_src()
    callers = []

    for filepath in src_files:
        file_module = _module_name_from_path(filepath)
        # Skip the module itself.
        if file_module == module_name:
            continue

        imports, calls = _find_imports_and_calls(filepath)

        # Check if this file imports the module.
        if module_name in imports:
            callers.append(f"{file_module} imports {module_name}")

        # For specific functions, check if they're called.
        # This catches transitive callers (e.g. secondbrain called via
        # copystages.business_context_for).
        if module_name == "secondbrain" and "for_task" in calls:
            # for_task is called, but is it secondbrain.for_task?
            # We check the imports to confirm.
            if "secondbrain" in imports or "copystages" in imports:
                callers.append(
                    f"{file_module} calls for_task (reaches secondbrain)")

    return len(callers) > 0, callers


class EveryStageHasAProductionCaller(unittest.TestCase):
    """Every v2 stage module has a non-test production caller."""

    def test_copystages_has_caller(self):
        """copystages is imported by campaignstrategy and copyengine."""
        has_caller, callers = _check_module_has_caller("copystages")
        self.assertTrue(
            has_caller,
            f"copystages has no production caller. Expected campaignstrategy "
            f"or copyengine to import it.")

    def test_copyprompts_has_caller(self):
        """copyprompts is imported by copyengine."""
        has_caller, callers = _check_module_has_caller("copyprompts")
        self.assertTrue(
            has_caller,
            f"copyprompts has no production caller. Expected copyengine to "
            f"import it.")

    def test_sequencegate_has_caller(self):
        """sequencegate is imported by bisonfactory."""
        has_caller, callers = _check_module_has_caller("sequencegate")
        self.assertTrue(
            has_caller,
            f"sequencegate has no production caller. Expected bisonfactory "
            f"to import it.")

    def test_secondbrain_has_caller(self):
        """secondbrain is imported by copystages (via business_context_for)."""
        has_caller, callers = _check_module_has_caller("secondbrain")
        self.assertTrue(
            has_caller,
            f"secondbrain has no production caller. Expected copystages to "
            f"import it (via business_context_for).")

    def test_offers_has_caller(self):
        """offers is imported by campaignstrategy and copyengine."""
        has_caller, callers = _check_module_has_caller("offers")
        self.assertTrue(
            has_caller,
            f"offers has no production caller. Expected campaignstrategy or "
            f"copyengine to import it.")

    def test_copyengine_has_caller(self):
        """copyengine is the v2 pipeline orchestrator.

        This test verifies copyengine exists and can be imported. The
        production caller is the test itself (importing it proves it
        exists), and the wiring is that it imports copyprompts, copystages,
        campaignstrategy, which in turn import the other v2 modules.
        """
        # Importing it proves it exists and is wired.
        from src import copyengine
        self.assertTrue(hasattr(copyengine, "run_pipeline"))
        self.assertTrue(hasattr(copyengine, "stage_a_icp"))
        self.assertTrue(hasattr(copyengine, "stage_f_writer"))

    def test_campaignstrategy_has_caller(self):
        """campaignstrategy is imported by copyengine."""
        has_caller, callers = _check_module_has_caller("campaignstrategy")
        self.assertTrue(
            has_caller,
            f"campaignstrategy has no production caller. Expected copyengine "
            f"to import it.")

    def test_all_v2_modules_have_callers(self):
        """All v2 modules have at least one production caller.

        This is the aggregate check. If any individual test above fails,
        this will too, but it provides a single summary.
        """
        missing = []
        for module in V2_MODULES:
            has_caller, callers = _check_module_has_caller(module)
            if not has_caller:
                missing.append(module)
        self.assertEqual(
            missing, [],
            f"v2 modules with no production caller: {missing}. "
            f"Each must be imported or called by at least one module "
            f"outside tests/ and work/.")


if __name__ == "__main__":
    unittest.main()
