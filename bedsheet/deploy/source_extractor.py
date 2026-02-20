"""Source code extraction from @action decorated functions.

This module extracts the actual Python source code from user-defined
@action functions, enabling "Build Once, Deploy Everywhere" - the ability
to compile Bedsheet agents to any target platform (AWS, GCP, Local).
"""

import ast
import asyncio
import inspect
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable


# Python type to JSON Schema type mapping
PYTHON_TO_JSON_TYPE: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "null",
    "NoneType": "null",
}


@dataclass
class ParameterInfo:
    """Metadata for a single function parameter."""

    name: str
    type_hint: str  # Python type as string: "str", "int", "list[str]"
    json_type: str  # JSON Schema type: "string", "integer", "array"
    description: str | None  # From docstring parsing (future)
    required: bool  # True if no default value
    default: Any | None  # Default value if any


@dataclass
class SourceInfo:
    """Extracted source code and metadata from an @action function."""

    source_code: str  # Complete function source (without decorator)
    function_body: str  # Just the function body (statements inside)
    is_async: bool  # True if async def
    parameters: list[ParameterInfo]  # Parsed parameter metadata
    return_type: str  # Return type annotation as string
    imports: list[str] = field(default_factory=list)  # Required imports
    module_constants: list[str] = field(
        default_factory=list
    )  # Module-level constants used


class SourceExtractor:
    """Extract source code and metadata from @action decorated functions.

    This class uses Python's inspect and ast modules to extract the complete
    source code of a function, along with metadata about its parameters,
    return type, and whether it's async.

    Example:
        >>> @tools.action(name="greet")
        ... async def greet(name: str) -> str:
        ...     return f"Hello, {name}!"
        ...
        >>> extractor = SourceExtractor(greet)
        >>> info = extractor.extract()
        >>> print(info.source_code)
        async def greet(name: str) -> str:
            return f"Hello, {name}!"
    """

    def __init__(self, fn: Callable[..., Any]):
        """Initialize extractor with a function.

        Args:
            fn: The function to extract source from (typically an @action function)
        """
        self.fn = fn

    def extract(self) -> SourceInfo:
        """Extract source code and metadata from the function.

        Returns:
            SourceInfo containing the function source, parameters, and metadata.

        Raises:
            OSError: If source code cannot be retrieved (e.g., built-in functions)
        """
        # Get the raw source code
        raw_source = inspect.getsource(self.fn)

        # Dedent to handle indented class methods
        dedented_source = textwrap.dedent(raw_source)

        # Parse to AST to extract clean function (without decorators)
        tree = ast.parse(dedented_source)

        # Find the function definition (skip decorators)
        func_node = self._find_function_node(tree)

        # Extract clean source (function def without decorators)
        clean_source = self._extract_clean_source(func_node, dedented_source)

        # Extract function body (just the statements inside)
        function_body = self._extract_function_body(func_node, dedented_source)

        # Check if async
        is_async = asyncio.iscoroutinefunction(self.fn)

        # Extract parameters
        parameters = self._extract_parameters()

        # Extract return type
        return_type = self._extract_return_type()

        # Extract imports from function body
        imports = self._extract_imports(func_node)

        # Extract module-level constants referenced by this function
        module_constants = self._extract_module_constants(func_node)

        return SourceInfo(
            source_code=clean_source,
            function_body=function_body,
            is_async=is_async,
            parameters=parameters,
            return_type=return_type,
            imports=imports,
            module_constants=module_constants,
        )

    def _find_function_node(
        self, tree: ast.Module
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        """Find the function definition node in the AST.

        Handles both regular functions and async functions.
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == self.fn.__name__:
                    return node
        raise ValueError(f"Could not find function {self.fn.__name__} in source")

    def _extract_clean_source(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, full_source: str
    ) -> str:
        """Extract function source without decorators.

        This removes the @action decorator and any other decorators,
        returning just the function definition and body.
        """
        # Clear decorators from the node
        func_node.decorator_list = []

        # Use ast.unparse to get clean source (Python 3.9+)
        return ast.unparse(func_node)

    def _extract_function_body(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, full_source: str
    ) -> str:
        """Extract just the function body (statements inside the function)."""
        # Create a module with just the body statements
        body_nodes = func_node.body

        # Unparse each statement and join
        body_lines = []
        for stmt in body_nodes:
            body_lines.append(ast.unparse(stmt))

        return "\n".join(body_lines)

    def _extract_parameters(self) -> list[ParameterInfo]:
        """Extract parameter metadata from the function signature."""
        sig = inspect.signature(self.fn)
        annotations = self.fn.__annotations__

        parameters = []
        for param_name, param in sig.parameters.items():
            # Get type hint
            type_hint = "Any"
            if param_name in annotations:
                ann = annotations[param_name]
                type_hint = self._type_to_string(ann)

            # Map to JSON type
            json_type = self._python_type_to_json(type_hint)

            # Check if required (no default value)
            required = param.default is inspect.Parameter.empty

            # Get default value
            default = None if required else param.default

            parameters.append(
                ParameterInfo(
                    name=param_name,
                    type_hint=type_hint,
                    json_type=json_type,
                    description=None,  # TODO: Parse from docstring
                    required=required,
                    default=default,
                )
            )

        return parameters

    def _extract_return_type(self) -> str:
        """Extract the return type annotation."""
        annotations = self.fn.__annotations__
        if "return" in annotations:
            return self._type_to_string(annotations["return"])
        return "Any"

    # Standard library modules that may appear as attribute access (e.g. os.path.join)
    _STDLIB_MODULES = frozenset(
        {
            "datetime",
            "json",
            "os",
            "sys",
            "re",
            "math",
            "random",
            "time",
            "uuid",
            "collections",
            "itertools",
            "functools",
            "hashlib",
            "pathlib",
            "typing",
            "dataclasses",
            "enum",
            "copy",
            "io",
            "struct",
            "base64",
            "urllib",
            "http",
            "logging",
            "threading",
            "asyncio",
            "contextlib",
            "abc",
            "inspect",
            "ast",
            "textwrap",
            "string",
            "shutil",
            "tempfile",
        }
    )

    def _extract_imports(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[str]:
        """Extract import statements used within the function body.

        Looks for module attribute access (e.g. os.path.join, hashlib.sha256)
        and inline import statements inside the function body.
        """
        imports: list[str] = []
        seen: set[str] = set()

        def _add(stmt: str) -> None:
            if stmt not in seen:
                seen.add(stmt)
                imports.append(stmt)

        for node in ast.walk(func_node):
            # Inline imports inside the function (e.g. `import random`)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _add(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = ", ".join(
                    alias.asname if alias.asname else alias.name for alias in node.names
                )
                _add(f"from {node.module} import {names}")
            # Attribute access on a bare name: os.path, hashlib.sha256, etc.
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                module_name = node.value.id
                if module_name in self._STDLIB_MODULES:
                    if module_name == "datetime":
                        _add("from datetime import datetime")
                    else:
                        _add(f"import {module_name}")

        return imports

    def _extract_module_constants(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[str]:
        """Extract module-level constants referenced by this function.

        Walks the function body to find free names (not local, not params),
        then looks them up in the enclosing module's top-level assignments.
        """
        # Collect locally-defined names (params + local assignments)
        local_names: set[str] = set()
        for arg in func_node.args.args:
            local_names.add(arg.arg)
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                local_names.add(node.target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # Names brought in by inline imports are also local
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        local_names.add(alias.asname or alias.name.split(".")[0])
                else:
                    for alias in node.names:
                        local_names.add(alias.asname or alias.name)

        # Names loaded (referenced) but not defined locally
        referenced: set[str] = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in local_names and not node.id.startswith("_"):
                    referenced.add(node.id)

        # Skip Python builtins and common names that don't need capturing
        builtins = frozenset(
            dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__)
        )
        referenced -= builtins
        referenced -= self._STDLIB_MODULES

        if not referenced:
            return []

        # Get the source module and parse its top-level assignments
        module = inspect.getmodule(self.fn)
        if module is None:
            return []
        try:
            module_source = inspect.getsource(module)
        except OSError:
            return []

        module_tree = ast.parse(module_source)
        constants: list[str] = []
        seen: set[str] = set()

        for node in module_tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in referenced:
                        stmt = ast.unparse(node)
                        if stmt not in seen:
                            seen.add(stmt)
                            constants.append(stmt)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in referenced:
                    stmt = ast.unparse(node)
                    if stmt not in seen:
                        seen.add(stmt)
                        constants.append(stmt)

        return constants

    def _type_to_string(self, type_annotation: Any) -> str:
        """Convert a type annotation to its string representation."""
        if type_annotation is None:
            return "None"

        # Handle string annotations
        if isinstance(type_annotation, str):
            return type_annotation

        # Handle basic types
        if hasattr(type_annotation, "__name__"):
            return type_annotation.__name__

        # Handle generic types like list[str], dict[str, int]
        if hasattr(type_annotation, "__origin__"):
            origin = type_annotation.__origin__
            args = getattr(type_annotation, "__args__", ())

            origin_name = getattr(origin, "__name__", str(origin))

            if args:
                args_str = ", ".join(self._type_to_string(a) for a in args)
                return f"{origin_name}[{args_str}]"
            return origin_name

        # Fallback to string representation
        return str(type_annotation)

    def _python_type_to_json(self, type_hint: str) -> str:
        """Convert Python type string to JSON Schema type."""
        # Handle generic types by extracting base type
        base_type = type_hint.split("[")[0].strip()

        return PYTHON_TO_JSON_TYPE.get(base_type, "string")
