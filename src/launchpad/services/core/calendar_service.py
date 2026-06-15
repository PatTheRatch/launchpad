"""Calendar service interface and stub (core feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.calendar import Agenda
from launchpad.services.base import DataService


class CalendarService(DataService[Agenda]):
    """Retrieves the agenda of relevant calendar events."""

    @abstractmethod
    def fetch(self) -> Agenda:
        raise NotImplementedError
