"""A uniform result type for data services.

Every service produces a :class:`Result` so the rest of the system can
distinguish three outcomes consistently:

* **present** – valid, non-empty data,
* **empty** – a valid result that happens to be empty (e.g. no trains due),
* **unavailable** – the data could not be retrieved (a failure upstream).

Note: the result *carries* the failure outcome as data; it does not represent
an exception. Services are responsible for catching their own errors and
translating them into ``Result.unavailable()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class Availability(str, Enum):
    """Whether a piece of data is present, validly empty, or unavailable."""

    PRESENT = "present"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """An immutable outcome of a single data retrieval."""

    availability: Availability
    value: T | None = None

    def __post_init__(self) -> None:
        if self.availability is Availability.PRESENT and self.value is None:
            raise ValueError("A present result must carry a value.")
        if self.availability is Availability.UNAVAILABLE and self.value is not None:
            raise ValueError("An unavailable result must not carry a value.")

    @classmethod
    def present(cls, value: T) -> "Result[T]":
        """A valid result containing non-empty data."""
        return cls(Availability.PRESENT, value)

    @classmethod
    def empty(cls, value: T | None = None) -> "Result[T]":
        """A valid result that is empty (optionally an empty container)."""
        return cls(Availability.EMPTY, value)

    @classmethod
    def unavailable(cls) -> "Result[T]":
        """A result that could not be retrieved."""
        return cls(Availability.UNAVAILABLE, None)

    @property
    def is_present(self) -> bool:
        return self.availability is Availability.PRESENT

    @property
    def is_empty(self) -> bool:
        return self.availability is Availability.EMPTY

    @property
    def is_unavailable(self) -> bool:
        return self.availability is Availability.UNAVAILABLE
