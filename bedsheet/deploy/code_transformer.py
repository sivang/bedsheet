"""Code transformation for target-specific deployment.

This module transforms extracted source code for different target platforms
(AWS, GCP, Local). Key transformations include:
- async→sync conversion for GCP/AWS targets (using AST transformation)
- Preserving imports
- Handling edge cases (async for, async with, await expressions)
"""
import ast
from typing import Literal

from .source_extractor import SourceInfo, ParameterInfo


class AsyncToSyncTransformer(ast.NodeTransformer):
    """AST NodeTransformer that converts async code to synchronous code.

    Transformations performed:
    - AsyncFunctionDef → FunctionDef
    - Await expressions → unwrap the awaited value
    - async for → for
    - async with → with
    """

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.FunctionDef:
        """Convert async function definition to regular function definition."""
        # First, recursively transform the body
        new_body = [self.visit(stmt) for stmt in node.body]

        # Build kwargs for FunctionDef - type_params is Python 3.12+ only
        kwargs: dict[str, object] = {
            "name": node.name,
            "args": node.args,
            "body": new_body,
            "decorator_list": node.decorator_list,
            "returns": node.returns,
            "type_comment": node.type_comment,
        }
        # Add type_params if available (Python 3.12+)
        if hasattr(node, 'type_params'):
            kwargs["type_params"] = node.type_params

        return ast.FunctionDef(**kwargs)  # type: ignore[arg-type]

    def visit_Await(self, node: ast.Await) -> ast.AST:
        """Unwrap await expressions, returning just the awaited value.

        Example: `await some_func()` → `some_func()`
        """
        # Recursively transform the awaited expression
        return self.visit(node.value)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> ast.For:
        """Convert async for loop to regular for loop.

        Example:
            async for item in async_iter:
                ...
        Becomes:
            for item in async_iter:
                ...
        """
        # Transform body and orelse recursively
        new_body = [self.visit(stmt) for stmt in node.body]
        new_orelse = [self.visit(stmt) for stmt in node.orelse]

        return ast.For(
            target=self.visit(node.target),
            iter=self.visit(node.iter),
            body=new_body,
            orelse=new_orelse,
            type_comment=node.type_comment,
        )

    def visit_AsyncWith(self, node: ast.AsyncWith) -> ast.With:
        """Convert async with statement to regular with statement.

        Example:
            async with resource as r:
                ...
        Becomes:
            with resource as r:
                ...
        """
        # Transform items and body recursively
        new_items = []
        for item in node.items:
            new_item = ast.withitem(
                context_expr=self.visit(item.context_expr),
                optional_vars=self.visit(item.optional_vars) if item.optional_vars else None,
            )
            new_items.append(new_item)

        new_body = [self.visit(stmt) for stmt in node.body]

        return ast.With(
            items=new_items,
            body=new_body,
            type_comment=node.type_comment,
        )

    def generic_visit(self, node: ast.AST) -> ast.AST:
        """Ensure all child nodes are also visited."""
        return super().generic_visit(node)


class CodeTransformer:
    """Transform extracted source code for different target platforms.

    This class applies target-specific transformations to source code
    extracted from @action decorated functions. The main transformation
    is converting async code to synchronous code for platforms that
    don't support async natively (GCP ADK, AWS Bedrock).

    Example:
        >>> transformer = CodeTransformer("gcp")
        >>> transformed = transformer.transform(source_info)
        >>> # Async functions are now sync for GCP deployment

    Supported targets:
        - "local": No transformations (async preserved)
        - "gcp": async→sync conversion
        - "aws": async→sync conversion
    """

    # Targets that require async→sync transformation
    SYNC_TARGETS = {"gcp", "aws"}

    def __init__(self, target: Literal["local", "gcp", "aws"]):
        """Initialize transformer for a specific target platform.

        Args:
            target: The deployment target ("local", "gcp", or "aws")
        """
        if target not in ("local", "gcp", "aws"):
            raise ValueError(f"Invalid target: {target}. Must be 'local', 'gcp', or 'aws'")
        self.target = target

    def transform(self, source_info: SourceInfo) -> SourceInfo:
        """Transform source code for the target platform.

        This method applies all necessary transformations based on the
        target platform. For GCP and AWS, this includes converting
        async functions to synchronous functions.

        Args:
            source_info: The extracted source information to transform

        Returns:
            A new SourceInfo with transformed source code
        """
        # For local target, no transformation needed
        if self.target == "local":
            return source_info

        # For GCP/AWS, convert async to sync if needed
        if source_info.is_async and self.target in self.SYNC_TARGETS:
            return self._async_to_sync(source_info)

        # No transformation needed (already sync)
        return source_info

    def _async_to_sync(self, source_info: SourceInfo) -> SourceInfo:
        """Convert async source code to synchronous code.

        Uses AST transformation to:
        - Convert async def → def
        - Unwrap await expressions
        - Convert async for → for
        - Convert async with → with

        Args:
            source_info: The async source information to convert

        Returns:
            A new SourceInfo with synchronous source code
        """
        # Parse the source code into AST
        tree = ast.parse(source_info.source_code)

        # Apply the async→sync transformation
        transformer = AsyncToSyncTransformer()
        transformed_tree = transformer.visit(tree)

        # Fix missing line numbers and column offsets
        ast.fix_missing_locations(transformed_tree)

        # Convert back to source code
        transformed_source = ast.unparse(transformed_tree)

        # Extract the transformed function body
        transformed_body = self._extract_transformed_body(transformed_tree)

        # Create new SourceInfo with transformed code
        # Make a shallow copy of parameters to avoid mutating the original
        new_parameters = [
            ParameterInfo(
                name=p.name,
                type_hint=p.type_hint,
                json_type=p.json_type,
                description=p.description,
                required=p.required,
                default=p.default,
            )
            for p in source_info.parameters
        ]

        return SourceInfo(
            source_code=transformed_source,
            function_body=transformed_body,
            is_async=False,  # Now synchronous
            parameters=new_parameters,
            return_type=source_info.return_type,
            imports=list(source_info.imports),  # Copy the list
        )

    def _extract_transformed_body(self, tree: ast.Module) -> str:
        """Extract the function body from a transformed AST.

        Args:
            tree: The AST module containing the transformed function

        Returns:
            The function body as a string
        """
        # Find the function definition in the tree
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Extract and unparse each body statement
                body_lines = [ast.unparse(stmt) for stmt in node.body]
                return "\n".join(body_lines)

        # Fallback: return empty string if no function found
        return ""
