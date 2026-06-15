"""Baby tracking service interface and stub (experimental feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.experimental.baby import BabySnapshot
from launchpad.services.base import DataService


class BabyService(DataService[BabySnapshot]):
    """Retrieves the most recent baby-care events."""

    @abstractmethod
    def fetch(self) -> BabySnapshot:
        raise NotImplementedError
