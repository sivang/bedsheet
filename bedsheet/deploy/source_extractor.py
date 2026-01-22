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
    type_hint: str              # Python type as string: "str", "int", "list[str]"
    json_type: str              # JSON Schema type: "string", "integer", "array"
    description: str | None     # From docstring parsing (future)
    required: bool              # True if no default value
    default: Any | None         # Default value if any


@dataclass
class SourceInfo:
    """Extracted source code and metadata from an @action function."""
    source_code: str                    # Complete function source (without decorator)
    function_body: str                  # Just the function body (statements inside)
    is_async: bool                      # True if async def
    parameters: list[ParameterInfo]     # Parsed parameter metadata
    return_type: str                    # Return type annotation as string
    imports: list[str] = field(default_factory=list)  # Required imports


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

        return SourceInfo(
            source_code=clean_source,
            function_body=function_body,
            is_async=is_async,
            parameters=parameters,
            return_type=return_type,
            imports=imports,
        )

    def _find_function_node(self, tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef:
        """Find the function definition node in the AST.

        Handles both regular functions and async functions.
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == self.fn.__name__:
                    return node
        raise ValueError(f"Could not find function {self.fn.__name__} in source")

    def _extract_clean_source(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        full_source: str
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
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        full_source: str
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

            parameters.append(ParameterInfo(
                name=param_name,
                type_hint=type_hint,
                json_type=json_type,
                description=None,  # TODO: Parse from docstring
                required=required,
                default=default,
            ))

        return parameters

    def _extract_return_type(self) -> str:
        """Extract the return type annotation."""
        annotations = self.fn.__annotations__
        if "return" in annotations:
            return self._type_to_string(annotations["return"])
        return "Any"

    def _extract_imports(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Extract import statements used within the function body.

        This analyzes the function body to find module references
        and generates appropriate import statements.

        Note: This is a heuristic - complex import patterns may need manual handling.
        """
        imports: list[str] = []

        # Walk the function body looking for module attribute access
        for node in ast.walk(func_node):
            # Look for calls like datetime.now(), json.dumps(), etc.
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    module_name = node.value.id
                    # Common standard library modules
                    if module_name in ('datetime', 'json', 'os', 'sys', 're',
                                       'math', 'random', 'time', 'uuid',
                                       'collections', 'itertools', 'functools'):
                        import_stmt = f"from {module_name} import {module_name}"
                        if module_name == 'datetime':
                            import_stmt = "from datetime import datetime"
                        elif module_name not in [i.split()[-1] for i in imports]:
                            import_stmt = f"import {module_name}"
                        if import_stmt not in imports:
                            imports.append(import_stmt)

        return imports

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
