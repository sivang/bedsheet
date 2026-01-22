"""Tests for CodeTransformer - async to sync code transformation."""
import pytest

from bedsheet.deploy.code_transformer import CodeTransformer, AsyncToSyncTransformer
from bedsheet.deploy.source_extractor import SourceExtractor


# Mock async functions used in test function bodies (never actually called)
# These are referenced in test functions for AST analysis but never executed
async def get_data(url: str) -> str:
    """Mock async function."""
    return ""


async def transform(data: dict) -> dict:
    """Mock async function."""
    return data


async def make_request(endpoint: str) -> str:
    """Mock async function."""
    return ""


async def process(value: object) -> object:
    """Mock async function."""
    return value


async def fetch(value: object) -> object:
    """Mock async function."""
    return value


async def open_file(path: str) -> str:
    """Mock async function."""
    return ""


async def create_user(name: str) -> dict:
    """Mock async function."""
    return {}


async def fetch_list() -> list:
    """Mock async function."""
    return []


async def get_value(key: str) -> object:
    """Mock async function."""
    return None


async def get_connection() -> object:
    """Mock async function."""
    return None


class TestCodeTransformerSyncFunctions:
    """Test that sync functions remain unchanged."""

    def test_transform_keeps_sync_function_unchanged(self):
        """Sync functions should stay sync for all targets."""
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        extractor = SourceExtractor(greet)
        source_info = extractor.extract()

        # Test for all targets
        for target in ["local", "gcp", "aws"]:
            transformer = CodeTransformer(target=target)
            result = transformer.transform(source_info)

            assert "async def" not in result.source_code
            assert "def greet" in result.source_code
            assert result.is_async is False
            assert "await" not in result.source_code


class TestCodeTransformerAsyncToSync:
    """Test async to sync transformation for different targets."""

    def test_transform_async_to_sync_for_gcp(self):
        """Async functions should be converted to sync for GCP target."""
        async def fetch(url: str) -> str:
            return await get_data(url)

        extractor = SourceExtractor(fetch)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        assert "async def" not in result.source_code
        assert "def fetch" in result.source_code
        assert "await" not in result.source_code
        assert result.is_async is False

    def test_transform_async_to_sync_for_aws(self):
        """Async functions should be converted to sync for AWS target."""
        async def process(data: dict) -> dict:
            result = await transform(data)
            return result

        extractor = SourceExtractor(process)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="aws")
        result = transformer.transform(source_info)

        assert "async def" not in result.source_code
        assert "def process" in result.source_code
        assert "await" not in result.source_code
        assert result.is_async is False

    def test_transform_keeps_async_for_local(self):
        """Async functions should remain async for local target."""
        async def fetch(url: str) -> str:
            return await get_data(url)

        extractor = SourceExtractor(fetch)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="local")
        result = transformer.transform(source_info)

        # Local target should preserve async
        assert "async def" in result.source_code
        assert result.is_async is True
        assert "await" in result.source_code


class TestAwaitExpressionUnwrap:
    """Test await expression unwrapping."""

    def test_await_expression_unwrap(self):
        """Await expressions should be unwrapped: await foo() -> foo()."""
        async def call_api(endpoint: str) -> str:
            response = await make_request(endpoint)
            return response

        extractor = SourceExtractor(call_api)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        assert "await" not in result.source_code
        assert "make_request(endpoint)" in result.source_code

    def test_nested_await(self):
        """Nested await expressions should be properly unwrapped."""
        async def nested_calls(value: int) -> int:
            result = await process(await fetch(value))
            return result

        extractor = SourceExtractor(nested_calls)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="aws")
        result = transformer.transform(source_info)

        assert "await" not in result.source_code
        # After unwrapping: process(fetch(value))
        assert "process(fetch(value))" in result.source_code


class TestAsyncForConversion:
    """Test async for to for conversion."""

    def test_async_for_to_for(self):
        """Async for loops should be converted to regular for loops."""
        async def iterate_items(items: list) -> list:
            results = []
            async for item in items:
                results.append(item)
            return results

        extractor = SourceExtractor(iterate_items)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        assert "async for" not in result.source_code
        assert "for item in items:" in result.source_code
        assert result.is_async is False


class TestAsyncWithConversion:
    """Test async with to with conversion."""

    def test_async_with_to_with(self):
        """Async with statements should be converted to regular with statements."""
        async def use_resource(path: str) -> str:
            async with open_file(path) as f:
                content = f.read()
            return content

        extractor = SourceExtractor(use_resource)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="aws")
        result = transformer.transform(source_info)

        assert "async with" not in result.source_code
        assert "with open_file(path) as f:" in result.source_code
        assert result.is_async is False


class TestPreservesMetadata:
    """Test that imports and parameters are preserved after transformation."""

    def test_preserves_imports(self):
        """Imports should be preserved after transformation."""
        async def process_json(data: str) -> dict:
            import json
            return json.loads(data)

        extractor = SourceExtractor(process_json)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        # Imports list should be preserved
        assert result.imports == source_info.imports

    def test_preserves_parameters(self):
        """Parameters should remain unchanged after transformation."""
        async def complex_func(
            name: str,
            age: int,
            active: bool = True,
            score: float = 0.0,
        ) -> dict:
            return await create_user(name, age, active, score)

        extractor = SourceExtractor(complex_func)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="aws")
        result = transformer.transform(source_info)

        # Check parameter count
        assert len(result.parameters) == len(source_info.parameters)

        # Check each parameter is preserved
        for orig, transformed in zip(source_info.parameters, result.parameters):
            assert orig.name == transformed.name
            assert orig.type_hint == transformed.type_hint
            assert orig.json_type == transformed.json_type
            assert orig.required == transformed.required
            assert orig.default == transformed.default

    def test_preserves_return_type(self):
        """Return type should be preserved after transformation."""
        async def get_items() -> list[str]:
            return await fetch_list()

        extractor = SourceExtractor(get_items)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        assert result.return_type == source_info.return_type
        assert "list" in result.return_type


class TestInvalidTarget:
    """Test error handling for invalid targets."""

    def test_invalid_target_raises_error(self):
        """Invalid target should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CodeTransformer(target="invalid")

        assert "Invalid target" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)


class TestAsyncToSyncTransformerDirect:
    """Direct tests for the AsyncToSyncTransformer AST transformer."""

    def test_async_function_def_conversion(self):
        """Test AsyncFunctionDef to FunctionDef conversion via AST."""
        import ast

        code = "async def foo(): pass"
        tree = ast.parse(code)

        transformer = AsyncToSyncTransformer()
        new_tree = transformer.visit(tree)

        # Check that we have a FunctionDef, not AsyncFunctionDef
        func = new_tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        assert not isinstance(func, ast.AsyncFunctionDef)

    def test_await_removal(self):
        """Test await expression unwrapping via AST."""
        import ast

        code = """
async def foo():
    x = await bar()
    return x
"""
        tree = ast.parse(code)

        transformer = AsyncToSyncTransformer()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        result = ast.unparse(new_tree)

        assert "await" not in result
        assert "x = bar()" in result


class TestFunctionBody:
    """Test function body extraction."""

    def test_function_body_is_extracted(self):
        """Function body should be extracted separately."""
        async def simple(x: int) -> int:
            result = x * 2
            return result

        extractor = SourceExtractor(simple)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        # Function body should contain the statements
        assert "result = x * 2" in result.function_body
        assert "return result" in result.function_body
        # But not the function definition
        assert "def simple" not in result.function_body


class TestComplexScenarios:
    """Test complex transformation scenarios."""

    def test_multiple_awaits_in_sequence(self):
        """Multiple await calls in sequence should all be unwrapped."""
        async def gather_data(a: str, b: str) -> list:
            result_a = await fetch(a)
            result_b = await fetch(b)
            return [result_a, result_b]

        extractor = SourceExtractor(gather_data)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        assert "await" not in result.source_code
        assert result.source_code.count("fetch(") == 2

    def test_await_in_expression(self):
        """Await within larger expressions should be unwrapped correctly."""
        async def compute(x: int) -> int:
            return (await get_value(x)) + 10

        extractor = SourceExtractor(compute)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="aws")
        result = transformer.transform(source_info)

        assert "await" not in result.source_code
        assert "get_value(x)" in result.source_code

    def test_combined_async_constructs(self):
        """Test function with multiple async constructs."""
        async def process_all(items: list) -> list:
            results = []
            async with get_connection() as conn:
                async for item in items:
                    result = await process(item, conn)
                    results.append(result)
            return results

        extractor = SourceExtractor(process_all)
        source_info = extractor.extract()

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(source_info)

        assert "async def" not in result.source_code
        assert "async with" not in result.source_code
        assert "async for" not in result.source_code
        assert "await" not in result.source_code
        assert result.is_async is False

        # Check regular constructs are present
        assert "with get_connection() as conn:" in result.source_code
        assert "for item in items:" in result.source_code


class TestSourceInfoCopying:
    """Test that original SourceInfo is not mutated."""

    def test_original_source_info_not_mutated(self):
        """Transformation should not mutate the original SourceInfo."""
        async def original_func(x: int) -> int:
            return await process(x)

        extractor = SourceExtractor(original_func)
        original_source_info = extractor.extract()

        # Save original values
        original_code = original_source_info.source_code
        original_is_async = original_source_info.is_async
        original_params = [p.name for p in original_source_info.parameters]

        transformer = CodeTransformer(target="gcp")
        result = transformer.transform(original_source_info)

        # Verify original is unchanged
        assert original_source_info.source_code == original_code
        assert original_source_info.is_async == original_is_async
        assert [p.name for p in original_source_info.parameters] == original_params

        # Verify result is different
        assert result.source_code != original_code
        assert result.is_async != original_is_async
