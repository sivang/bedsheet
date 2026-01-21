"""Tests for bedsheet.deploy.targets.gcp module."""
import tempfile
from pathlib import Path

import pytest

from bedsheet import Agent, ActionGroup, Supervisor
from bedsheet.deploy import (
    AgentConfig,
    BedsheetConfig,
    GCPTargetConfig,
)
from bedsheet.deploy.introspect import extract_agent_metadata
from bedsheet.deploy.targets import GCPTarget, GeneratedFile
from bedsheet.testing import MockLLMClient, MockResponse


@pytest.fixture
def mock_gcp_config():
    """Create a mock BedsheetConfig for GCP testing."""
    return BedsheetConfig(
        name="test-agent",
        agents=[
            AgentConfig(
                name="calculator",
                module="myapp.agents.calculator",
                class_name="CalculatorAgent",
                description="A calculator agent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(
                project="my-test-project",
                region="us-central1",
                model="gemini-2.5-flash",
            ),
        },
    )


@pytest.fixture
async def mock_single_agent_metadata():
    """Create a mock AgentMetadata for a single agent."""
    mock = MockLLMClient([MockResponse(text="ok")])

    agent = Agent(
        name="TestAgent",
        instruction="Test agent for GCP deployment",
        model_client=mock,
    )

    group = ActionGroup(name="TestGroup", description="Test actions")

    @group.action(name="add", description="Add two numbers")
    async def add(a: int, b: int) -> int:
        return a + b

    @group.action(name="multiply", description="Multiply two numbers")
    async def multiply(x: int, y: int) -> int:
        return x * y

    agent.add_action_group(group)

    return extract_agent_metadata(agent)


@pytest.fixture
async def mock_supervisor_metadata():
    """Create a mock AgentMetadata for a supervisor with collaborators."""
    mock = MockLLMClient([MockResponse(text="ok")])

    # Create collaborator agents
    calculator = Agent(
        name="Calculator",
        instruction="Do math calculations",
        model_client=mock,
    )
    calc_group = ActionGroup(name="MathOps", description="Math operations")

    @calc_group.action(name="add", description="Add numbers")
    async def add(a: int, b: int) -> int:
        return a + b

    calculator.add_action_group(calc_group)

    weather = Agent(
        name="Weather",
        instruction="Get weather info",
        model_client=mock,
    )
    weather_group = ActionGroup(name="WeatherOps", description="Weather operations")

    @weather_group.action(name="get_weather", description="Get current weather")
    async def get_weather(city: str) -> str:
        return f"Weather in {city}"

    weather.add_action_group(weather_group)

    # Create supervisor
    supervisor = Supervisor(
        name="MultiAgent",
        instruction="Coordinate multiple agents",
        model_client=mock,
        collaborators=[calculator, weather],
    )

    return extract_agent_metadata(supervisor)


def test_gcp_target_name():
    """Test GCPTarget.name property."""
    target = GCPTarget()
    assert target.name == "gcp"


def test_gcp_target_validate_valid_config(mock_gcp_config):
    """Test GCPTarget.validate with valid config."""
    target = GCPTarget()
    errors = target.validate(mock_gcp_config)
    assert errors == []


def test_gcp_target_validate_invalid_project_id_too_short():
    """Test GCPTarget.validate with project ID that's too short."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="abc", region="us-central1"),
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert len(errors) == 1
    assert "Invalid GCP project ID length" in errors[0]


def test_gcp_target_validate_invalid_project_id_too_long():
    """Test GCPTarget.validate with project ID that's too long."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(
                project="a" * 31,  # 31 chars, max is 30
                region="us-central1",
            ),
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert len(errors) == 1
    assert "Invalid GCP project ID length" in errors[0]


def test_gcp_target_validate_invalid_project_id_starts_with_number():
    """Test GCPTarget.validate with project ID starting with number."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="123-project", region="us-central1"),
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert len(errors) == 1
    assert "must start with a letter" in errors[0]


def test_gcp_target_validate_invalid_project_id_ends_with_hyphen():
    """Test GCPTarget.validate with project ID ending with hyphen."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="my-project-", region="us-central1"),
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert len(errors) == 1
    assert "cannot end with hyphen" in errors[0]


def test_gcp_target_validate_invalid_project_id_uppercase():
    """Test GCPTarget.validate with project ID containing uppercase."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="My-Project", region="us-central1"),
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert len(errors) == 1
    assert "lowercase letters, digits, and hyphens" in errors[0]


def test_gcp_target_validate_empty_region():
    """Test GCPTarget.validate with empty region."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="my-project", region="   "),
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert len(errors) == 1
    assert "region cannot be empty" in errors[0]


def test_gcp_target_validate_no_gcp_config():
    """Test GCPTarget.validate when no GCP config exists."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="my-project"),  # Default region
        },
    )

    target = GCPTarget()
    errors = target.validate(config)
    assert errors == []


@pytest.mark.asyncio
async def test_gcp_target_generate_creates_all_files(mock_gcp_config, mock_single_agent_metadata):
    """Test GCPTarget.generate creates all expected files."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        # Check we got all expected files
        assert len(files) == 15

        file_names = [f.path.name for f in files]
        assert "agent.py" in [f.path.name for f in files if f.path.parent.name == "agent"]
        assert "__init__.py" in [f.path.name for f in files if f.path.parent.name == "agent"]
        assert "Dockerfile" in file_names
        assert "cloudbuild.yaml" in file_names
        assert "Makefile" in file_names
        assert ".env.example" in file_names
        assert "pyproject.toml" in file_names

        # Check all are GeneratedFile instances
        for file in files:
            assert isinstance(file, GeneratedFile)
            assert isinstance(file.path, Path)
            assert isinstance(file.content, str)
            assert len(file.content) > 0


@pytest.mark.asyncio
async def test_gcp_target_generate_agent_py_content_single_agent(
    mock_gcp_config, mock_single_agent_metadata
):
    """Test GCPTarget.generate creates agent.py with correct ADK imports for single agent."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # Check for expected ADK imports
        assert "from google.adk.agents import LlmAgent" in content
        # Single agent should not import SequentialAgent
        assert "SequentialAgent" not in content

        # Check for agent configuration
        assert 'name="TestAgent"' in content
        assert 'model="gemini-2.5-flash"' in content
        assert "Test agent for GCP deployment" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_agent_py_content_supervisor(
    mock_gcp_config, mock_supervisor_metadata
):
    """Test GCPTarget.generate creates agent.py with ParallelAgent for supervisor."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_supervisor_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # Check for expected ADK imports for multi-agent
        assert "from google.adk.agents import LlmAgent, ParallelAgent" in content

        # Check for collaborator agent definitions
        assert "Calculator" in content
        assert "Weather" in content

        # Check for ParallelAgent usage (parallel delegation for supervisor pattern)
        assert "ParallelAgent" in content
        assert "sub_agents=" in content


@pytest.mark.asyncio
async def test_gcp_target_determine_orchestration_single(mock_single_agent_metadata):
    """Test _determine_orchestration returns 'single' for single agent."""
    target = GCPTarget()
    orchestration = target._determine_orchestration(mock_single_agent_metadata)
    assert orchestration == "single"


@pytest.mark.asyncio
async def test_gcp_target_determine_orchestration_supervisor(mock_supervisor_metadata):
    """Test _determine_orchestration returns 'parallel' for supervisor pattern."""
    target = GCPTarget()
    orchestration = target._determine_orchestration(mock_supervisor_metadata)
    # Supervisor pattern uses parallel delegation for concurrent collaborator execution
    assert orchestration == "parallel"


@pytest.mark.asyncio
async def test_gcp_target_generate_dockerfile_content(mock_gcp_config, mock_single_agent_metadata):
    """Test GCPTarget.generate creates Dockerfile with correct content."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        dockerfile = next(f for f in files if f.path.name == "Dockerfile")
        content = dockerfile.content

        # Check for expected Dockerfile elements
        assert "FROM python:3.11" in content
        assert "WORKDIR /app" in content
        assert "COPY pyproject.toml" in content
        assert "uv pip install" in content
        assert "COPY agent/" in content
        assert "ENV PORT=8080" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_pyproject_toml_content(
    mock_gcp_config, mock_single_agent_metadata
):
    """Test GCPTarget.generate creates pyproject.toml with correct dependencies."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        pyproject_file = next(f for f in files if f.path.name == "pyproject.toml")
        content = pyproject_file.content

        # Check for expected dependencies
        assert "google-adk" in content
        assert "google-genai" in content
        assert "bedsheet" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_cloudbuild_yaml_content(
    mock_gcp_config, mock_single_agent_metadata
):
    """Test GCPTarget.generate creates cloudbuild.yaml with correct content."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        cloudbuild_file = next(f for f in files if f.path.name == "cloudbuild.yaml")
        content = cloudbuild_file.content

        # Check for expected Cloud Build elements
        assert "steps:" in content
        assert "gcr.io/cloud-builders/docker" in content or "docker" in content.lower()
        # Cloud Build uses $PROJECT_ID variable, not hardcoded project name
        assert "$PROJECT_ID" in content or "PROJECT_ID" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_env_example_content(mock_gcp_config, mock_single_agent_metadata):
    """Test GCPTarget.generate creates .env.example with correct content."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        env_file = next(f for f in files if f.path.name == ".env.example")
        content = env_file.content

        # Check for expected env vars
        assert "GCP_PROJECT" in content or "PROJECT" in content
        assert "my-test-project" in content  # From config


@pytest.mark.asyncio
async def test_gcp_target_generate_makefile_content(mock_gcp_config, mock_single_agent_metadata):
    """Test GCPTarget.generate creates Makefile with correct content."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        makefile = next(f for f in files if f.path.name == "Makefile")
        content = makefile.content

        # Check for expected Makefile targets
        assert ".PHONY:" in content
        assert "gcloud" in content.lower() or "deploy" in content.lower()


@pytest.mark.asyncio
async def test_gcp_target_generate_with_default_config(mock_single_agent_metadata):
    """Test GCPTarget.generate uses default GCP config when target config is not GCP."""
    # Create config with GCP target but minimal settings
    config = BedsheetConfig(
        name="minimal-gcp-test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(project="minimal-project"),
        },
    )

    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        # Should still generate all files with defaults
        assert len(files) == 15

        # Check that default model is used (claude-sonnet-4-5@20250929 from GCPTargetConfig)
        agent_file = next(f for f in files if f.path.name == "agent.py")
        # Default model should be claude from Vertex AI
        assert "claude" in agent_file.content.lower() or "model=" in agent_file.content


# =============================================================================
# Google Search Grounding Tests
# =============================================================================


def test_gcp_config_builtin_tools_default_empty():
    """Test GCPTargetConfig.builtin_tools defaults to empty list."""
    config = GCPTargetConfig(project="my-project")
    assert config.builtin_tools == []


def test_gcp_config_builtin_tools_google_search():
    """Test GCPTargetConfig accepts google_search as builtin tool."""
    config = GCPTargetConfig(
        project="my-project",
        builtin_tools=["google_search"],
    )
    assert config.builtin_tools == ["google_search"]


def test_gcp_config_builtin_tools_code_execution():
    """Test GCPTargetConfig accepts code_execution as builtin tool."""
    config = GCPTargetConfig(
        project="my-project",
        builtin_tools=["code_execution"],
    )
    assert config.builtin_tools == ["code_execution"]


def test_gcp_config_builtin_tools_multiple():
    """Test GCPTargetConfig accepts multiple builtin tools."""
    config = GCPTargetConfig(
        project="my-project",
        builtin_tools=["google_search", "code_execution"],
    )
    assert config.builtin_tools == ["google_search", "code_execution"]


def test_gcp_config_builtin_tools_invalid():
    """Test GCPTargetConfig rejects invalid builtin tool names."""
    with pytest.raises(ValueError) as exc_info:
        GCPTargetConfig(
            project="my-project",
            builtin_tools=["invalid_tool"],
        )
    assert "Invalid built-in tool: invalid_tool" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gcp_target_generate_with_google_search(mock_single_agent_metadata):
    """Test GCPTarget.generate includes Google Search import and tool."""
    config = BedsheetConfig(
        name="search-agent",
        agents=[
            AgentConfig(
                name="searcher",
                module="myapp.agents.searcher",
                class_name="SearchAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(
                project="my-test-project",
                region="us-central1",
                builtin_tools=["google_search"],
            ),
        },
    )

    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # When google_search is used with custom tools, we use GoogleSearchTool with bypass flag
        assert "from google.adk.tools.google_search_tool import GoogleSearchTool" in content

        # Check that GoogleSearchTool is in tools list with bypass flag
        assert "GoogleSearchTool(bypass_multi_tools_limit=True)" in content
        assert "tools=" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_with_code_execution(mock_single_agent_metadata):
    """Test GCPTarget.generate includes code_execution import and tool."""
    config = BedsheetConfig(
        name="code-agent",
        agents=[
            AgentConfig(
                name="coder",
                module="myapp.agents.coder",
                class_name="CodeAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(
                project="my-test-project",
                region="us-central1",
                builtin_tools=["code_execution"],
            ),
        },
    )

    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # Check for code_execution import
        assert "from google.adk.tools import code_execution" in content

        # Check that code_execution is in tools list
        assert "code_execution" in content
        assert "tools=" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_with_multiple_builtin_tools(mock_single_agent_metadata):
    """Test GCPTarget.generate includes multiple builtin tools."""
    config = BedsheetConfig(
        name="multi-tool-agent",
        agents=[
            AgentConfig(
                name="multi",
                module="myapp.agents.multi",
                class_name="MultiAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(
                project="my-test-project",
                region="us-central1",
                builtin_tools=["google_search", "code_execution"],
            ),
        },
    )

    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # When google_search is used with custom tools, we use GoogleSearchTool with bypass flag
        assert "from google.adk.tools.google_search_tool import GoogleSearchTool" in content
        assert "from google.adk.tools import code_execution" in content

        # Check both are in tools list
        assert "GoogleSearchTool(bypass_multi_tools_limit=True)" in content
        assert "code_execution" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_with_custom_and_builtin_tools(mock_single_agent_metadata):
    """Test GCPTarget.generate combines custom tools with builtin tools."""
    config = BedsheetConfig(
        name="hybrid-agent",
        agents=[
            AgentConfig(
                name="hybrid",
                module="myapp.agents.hybrid",
                class_name="HybridAgent",
            )
        ],
        target="gcp",
        targets={
            "gcp": GCPTargetConfig(
                project="my-test-project",
                region="us-central1",
                builtin_tools=["google_search"],
            ),
        },
    )

    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # When google_search is used with custom tools, we use GoogleSearchTool with bypass flag
        assert "from google.adk.tools.google_search_tool import GoogleSearchTool" in content

        # Check for custom tool definitions (from mock_single_agent_metadata)
        assert "def add(" in content
        assert "def multiply(" in content

        # Check tools list includes both custom and builtin
        assert "tools=" in content
        assert "GoogleSearchTool(bypass_multi_tools_limit=True)" in content
        assert "add" in content
        assert "multiply" in content


@pytest.mark.asyncio
async def test_gcp_target_generate_no_builtin_tools_no_import(mock_gcp_config, mock_single_agent_metadata):
    """Test GCPTarget.generate does not import builtin tools when none specified."""
    target = GCPTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_gcp_config, mock_single_agent_metadata, output_dir)

        agent_file = next(f for f in files if f.path.name == "agent.py")
        content = agent_file.content

        # Should NOT have builtin tools import line
        assert "from google.adk.tools import" not in content
