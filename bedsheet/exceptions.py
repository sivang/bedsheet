"""Custom exceptions for Bedsheet Agents."""


class BedsheetError(Exception):
    """Base exception for all Bedsheet errors."""
    pass


class MaxIterationsError(BedsheetError):
    """Raised when agent exceeds maximum iterations."""
    pass


class LLMError(BedsheetError):
    """Raised when LLM call fails after retries."""
    pass


class ActionNotFoundError(BedsheetError):
    """Raised when LLM calls an unknown action."""
    pass
