"""Sample assistant agent."""

from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient


# Create tools for the assistant
tools = ActionGroup(name="AssistantTools", description="Tools for the assistant agent")


@tools.action(name="greet", description="Greet the user by name")
async def greet(name: str) -> str:
    """Greet a user."""
    return f"Hello, {name}! How can I help you today?"


@tools.action(name="get_time", description="Get the current time")
async def get_time() -> str:
    """Get current time."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_assistant() -> Agent:
    """Create and configure the assistant agent."""
    agent = Agent(
        name="Assistant",
        instruction="""You are a helpful assistant.

Use your tools to help users with their requests.
Be friendly and concise in your responses.""",
        model_client=AnthropicClient(),
    )
    agent.add_action_group(tools)
    return agent


# Export for bedsheet introspection
assistant = create_assistant()
