# tests/test_exceptions.py
from bedsheet.exceptions import (
    BedsheetError,
    MaxIterationsError,
    LLMError,
    ActionNotFoundError,
)


def test_bedsheet_error_is_base():
    assert issubclass(MaxIterationsError, BedsheetError)
    assert issubclass(LLMError, BedsheetError)
    assert issubclass(ActionNotFoundError, BedsheetError)


def test_exceptions_have_messages():
    err = MaxIterationsError("hit limit")
    assert str(err) == "hit limit"
