import json
import logging
from pathlib import Path
from typing import Iterable, Set


class AvailabilityState:
    """Persists previously seen available product URLs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._known_urls: Set[str] = set()

    @property
    def known_urls(self) -> Set[str]:
        return set(self._known_urls)

    def load(self) -> None:
        if not self.path.exists():
            logging.debug("State file %s does not exist yet", self.path)
            self._known_urls = set()
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logging.warning("State file %s is not valid JSON; starting fresh", self.path)
            data = []
        self._known_urls = set(data)

    def update(self, available_urls: Iterable[str]) -> None:
        self._known_urls = set(available_urls)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._known_urls), indent=2), encoding="utf-8")

