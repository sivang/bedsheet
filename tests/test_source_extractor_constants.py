"""Tests for module-level constant extraction in SourceExtractor.

These functions MUST be defined at module level (not inside test classes or
closures) so that inspect.getsource() can find their containing module and
the AST walk can locate the matching top-level assignments.
"""

import os

from bedsheet.deploy.source_extractor import SourceExtractor

# --- Module-level constants used by the functions below ---

REGISTRY = {"skill_a.py": "abc123", "skill_b.py": "def456"}
KNOWN_BAD = {"data_exfiltrator.py", "keylogger.py"}
INSTALL_DIR = os.path.join(os.path.dirname(__file__), "data", "skills")
MAX_RETRIES = 3


# --- Functions that reference those constants ---


def check_registry(skill_name: str) -> str:
    if skill_name in KNOWN_BAD:
        return f"BLOCKED: {skill_name}"
    return REGISTRY.get(skill_name, "unknown")


def install_skill(skill_name: str) -> str:
    dest = os.path.join(INSTALL_DIR, skill_name)
    return f"installed to {dest}"


def retry_action(action: str) -> str:
    for i in range(MAX_RETRIES):
        if i == MAX_RETRIES - 1:
            return f"done after {i+1} tries: {action}"
    return "failed"


def no_constants_used(a: int, b: int) -> int:
    return a + b


# --- Tests ---


class TestModuleConstantExtraction:
    """Test that _extract_module_constants finds top-level constants."""

    def test_extracts_dict_constant(self):
        """Function referencing a module-level dict gets that constant extracted."""
        info = SourceExtractor(check_registry).extract()

        assert any(
            "REGISTRY" in c for c in info.module_constants
        ), f"Expected REGISTRY in constants, got: {info.module_constants}"

    def test_extracts_set_constant(self):
        """Function referencing a module-level set gets that constant extracted."""
        info = SourceExtractor(check_registry).extract()

        assert any(
            "KNOWN_BAD" in c for c in info.module_constants
        ), f"Expected KNOWN_BAD in constants, got: {info.module_constants}"

    def test_extracts_os_path_constant(self):
        """Function referencing a module-level os.path.join constant is extracted."""
        info = SourceExtractor(install_skill).extract()

        assert any(
            "INSTALL_DIR" in c for c in info.module_constants
        ), f"Expected INSTALL_DIR in constants, got: {info.module_constants}"

    def test_extracts_int_constant(self):
        """Function referencing a module-level int constant is extracted."""
        info = SourceExtractor(retry_action).extract()

        assert any(
            "MAX_RETRIES" in c for c in info.module_constants
        ), f"Expected MAX_RETRIES in constants, got: {info.module_constants}"

    def test_no_constants_when_none_referenced(self):
        """Function that uses no module-level names returns empty constants."""
        info = SourceExtractor(no_constants_used).extract()

        assert (
            info.module_constants == []
        ), f"Expected no constants, got: {info.module_constants}"

    def test_constant_value_is_valid_python(self):
        """Each extracted constant string should be parseable Python."""
        import ast

        info = SourceExtractor(check_registry).extract()
        for const in info.module_constants:
            try:
                ast.parse(const)
            except SyntaxError as e:
                raise AssertionError(
                    f"Constant is not valid Python: {const!r}\n{e}"
                ) from e

    def test_no_duplicate_constants(self):
        """Extracted constants should not contain duplicates."""
        info = SourceExtractor(check_registry).extract()
        names = [c.split("=")[0].strip() for c in info.module_constants]
        assert len(names) == len(set(names)), f"Duplicate constants found: {names}"


class TestImportDeduplication:
    """Test that _extract_imports never produces duplicates or 'from X import X'."""

    def test_no_from_x_import_x(self):
        """The old bug produced 'from os import os' — ensure this never happens."""

        def uses_os_path(path: str) -> str:
            return os.path.join(path, "file.txt")

        info = SourceExtractor(uses_os_path).extract()
        for imp in info.imports:
            parts = imp.split()
            # "from os import os" has form: from X import X where X == X
            if parts[0] == "from" and len(parts) == 4 and parts[1] == parts[3]:
                raise AssertionError(f"Redundant import found: {imp!r}")

    def test_no_duplicate_imports(self):
        """Same import should not appear twice."""

        def uses_os_twice(a: str, b: str) -> str:
            x = os.path.join(a, "x")
            y = os.path.join(b, "y")
            return x + y

        info = SourceExtractor(uses_os_twice).extract()
        assert len(info.imports) == len(
            set(info.imports)
        ), f"Duplicate imports: {info.imports}"

    def test_os_import_is_import_not_from(self):
        """os module should produce 'import os', not 'from os import os'."""

        def uses_os(path: str) -> str:
            return os.path.exists(path)

        info = SourceExtractor(uses_os).extract()
        os_imports = [i for i in info.imports if "os" in i]
        assert all(
            "import os" == i or i.startswith("from os import") for i in os_imports
        ), f"Unexpected os import form: {os_imports}"
        # Must not be 'from os import os'
        assert "from os import os" not in info.imports
