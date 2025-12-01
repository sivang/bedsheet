"""Quick demo of Bedsheet Agents."""
import asyncio
from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient
from bedsheet.memory import InMemory
from bedsheet.events import ToolCallEvent, ToolResultEvent, CompletionEvent


# Create action group with some fun tools
tools = ActionGroup(name="DemoTools", description="Demo tools")


@tools.action(name="get_weather", description="Get weather for a city")
async def get_weather(city: str) -> dict:
    """Fake weather data."""
    weather_data = {
        "San Francisco": {"temp": 65, "condition": "foggy", "humidity": 80},
        "New York": {"temp": 45, "condition": "cloudy", "humidity": 60},
        "Miami": {"temp": 82, "condition": "sunny", "humidity": 75},
    }
    data = weather_data.get(city, {"temp": 70, "condition": "unknown", "humidity": 50})
    return {"city": city, **data}


@tools.action(name="calculate", description="Perform a math calculation")
async def calculate(expression: str) -> dict:
    """Safe math evaluation."""
    try:
        # Only allow safe math operations
        allowed = set("0123456789+-*/(). ")
        if all(c in allowed for c in expression):
            result = eval(expression)
            return {"expression": expression, "result": result}
        return {"error": "Invalid expression"}
    except Exception as e:
        return {"error": str(e)}


@tools.action(name="get_time", description="Get current time in a timezone")
async def get_time(timezone: str = "UTC") -> dict:
    """Get current time."""
    from datetime import datetime, timezone as tz
    now = datetime.now(tz.utc)
    return {"timezone": timezone, "time": now.strftime("%Y-%m-%d %H:%M:%S UTC")}


async def main():
    # Create agent
    agent = Agent(
        name="DemoAssistant",
        instruction="""You are a helpful assistant with access to weather, calculator, and time tools.
Be concise and friendly. Use tools when needed to answer questions accurately.""",
        model_client=AnthropicClient(),
        memory=InMemory(),
        max_iterations=5,
    )
    agent.add_action_group(tools)

    print("=" * 60)
    print("🛏️  Bedsheet Agents Demo")
    print("=" * 60)
    print("\nType 'quit' to exit. Try asking about:")
    print("  - Weather in San Francisco, New York, or Miami")
    print("  - Math calculations like '25 * 4 + 10'")
    print("  - Current time")
    print()

    session_id = "demo-session"

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! 👋")
                break

            print("\nAssistant: ", end="", flush=True)

            async for event in agent.invoke(session_id=session_id, input_text=user_input):
                if isinstance(event, ToolCallEvent):
                    print(f"\n  [🔧 Calling {event.tool_name}...]", end="", flush=True)
                elif isinstance(event, ToolResultEvent):
                    if event.error:
                        print(f"\n  [❌ Error: {event.error}]", end="", flush=True)
                    else:
                        print("\n  [✅ Got result]", end="", flush=True)
                elif isinstance(event, CompletionEvent):
                    print(f"\n{event.response}")

            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
