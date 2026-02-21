import json
import logging
from pathlib import Path
from typing import Iterable, Set


class AvailabilityState:
    """Persists the set of product URLs that were available (and unavailable) on the last run.

    State file format (v2):
        {
          "available":   ["url1", "url2", ...],
          "unavailable": ["url3", ...]
        }

    The old format was a plain JSON list of available URLs; that is migrated
    transparently on the first load.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._available_urls: Set[str] = set()
        self._unavailable_urls: Set[str] = set()

    @property
    def known_urls(self) -> Set[str]:
        """URLs that were available on the last run."""
        return set(self._available_urls)

    @property
    def known_unavailable_urls(self) -> Set[str]:
        """URLs that were found but unavailable on the last run."""
        return set(self._unavailable_urls)

    def load(self) -> None:
        if not self.path.exists():
            logging.debug("State file %s does not exist yet", self.path)
            self._available_urls = set()
            self._unavailable_urls = set()
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logging.warning("State file %s is not valid JSON; starting fresh", self.path)
            self._available_urls = set()
            self._unavailable_urls = set()
            return

        # Migrate old flat-list format (list of available URLs).
        if isinstance(data, list):
            logging.debug("Migrating state file %s from v1 (list) to v2 (dict)", self.path)
            self._available_urls = set(data)
            self._unavailable_urls = set()
            return

        self._available_urls = set(data.get("available", []))
        self._unavailable_urls = set(data.get("unavailable", []))

    def update(
        self,
        available_urls: Iterable[str],
        unavailable_urls: Iterable[str],
    ) -> None:
        self._available_urls = set(available_urls)
        self._unavailable_urls = set(unavailable_urls)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "available": sorted(self._available_urls),
                    "unavailable": sorted(self._unavailable_urls),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

