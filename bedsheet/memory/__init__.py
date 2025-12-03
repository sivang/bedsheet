"""Memory implementations for conversation persistence."""
from bedsheet.memory.base import Memory, Message
from bedsheet.memory.in_memory import InMemory

__all__ = ["Memory", "Message", "InMemory"]

# Optional Redis support - only available if redis is installed
try:
    from bedsheet.memory.redis import RedisMemory  # noqa: F401
    __all__.append("RedisMemory")
except ImportError:
    pass
