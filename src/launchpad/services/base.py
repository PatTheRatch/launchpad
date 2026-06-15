"""Service interfaces shared by all data services.

``DataService`` is generic over the model it produces so concrete services
stay small, single-responsibility, and interchangeable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class ServiceError(Exception):
    """Base error raised when a service fails to retrieve data."""


class DataService(ABC, Generic[T]):
    """Retrieves a single domain model of type ``T``.

    Implementations must isolate their own failures (network, parsing, auth)
    and surface them as :class:`ServiceError` so the dashboard can degrade
    gracefully without one feature breaking another.
    """

    @abstractmethod
    def fetch(self) -> T:
        """Retrieve the latest data. Raises :class:`ServiceError` on failure."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier, used for logging and diagnostics."""
        raise NotImplementedError
