"""Tests for bgg_mm.state — AvailabilityState persistence."""
import json
from pathlib import Path

import pytest

from bgg_mm.state import AvailabilityState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_state(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _read_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# load — initial / missing state
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_missing_file_starts_empty(self, tmp_path):
        state = AvailabilityState(tmp_path / "state.json")
        state.load()
        assert state.known_urls == set()
        assert state.known_unavailable_urls == set()

    def test_load_invalid_json_starts_empty(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("not json", encoding="utf-8")
        state = AvailabilityState(path)
        state.load()
        assert state.known_urls == set()
        assert state.known_unavailable_urls == set()


# ---------------------------------------------------------------------------
# load — v1 migration (old flat list format)
# ---------------------------------------------------------------------------

class TestLoadV1Migration:
    def test_v1_list_migrates_to_available(self, tmp_path):
        """Old format: a JSON list of available URLs."""
        path = tmp_path / "state.json"
        _write_state(path, ["http://shop/a", "http://shop/b"])
        state = AvailabilityState(path)
        state.load()
        assert state.known_urls == {"http://shop/a", "http://shop/b"}
        assert state.known_unavailable_urls == set()

    def test_v1_empty_list_migrates_cleanly(self, tmp_path):
        path = tmp_path / "state.json"
        _write_state(path, [])
        state = AvailabilityState(path)
        state.load()
        assert state.known_urls == set()
        assert state.known_unavailable_urls == set()


# ---------------------------------------------------------------------------
# load — v2 format
# ---------------------------------------------------------------------------

class TestLoadV2:
    def test_loads_available_and_unavailable(self, tmp_path):
        path = tmp_path / "state.json"
        _write_state(path, {
            "available":   ["http://shop/a"],
            "unavailable": ["http://shop/b"],
        })
        state = AvailabilityState(path)
        state.load()
        assert state.known_urls == {"http://shop/a"}
        assert state.known_unavailable_urls == {"http://shop/b"}

    def test_loads_missing_unavailable_key(self, tmp_path):
        """A v2 file without 'unavailable' key should still load cleanly."""
        path = tmp_path / "state.json"
        _write_state(path, {"available": ["http://shop/a"]})
        state = AvailabilityState(path)
        state.load()
        assert state.known_urls == {"http://shop/a"}
        assert state.known_unavailable_urls == set()


# ---------------------------------------------------------------------------
# update — writes correct v2 format
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_writes_v2_format(self, tmp_path):
        path = tmp_path / "state.json"
        state = AvailabilityState(path)
        state.update(
            available_urls=["http://shop/a"],
            unavailable_urls=["http://shop/b"],
        )
        data = _read_state(path)
        assert "available" in data
        assert "unavailable" in data
        assert data["available"] == ["http://shop/a"]
        assert data["unavailable"] == ["http://shop/b"]

    def test_update_creates_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "state.json"
        state = AvailabilityState(path)
        state.update(available_urls=[], unavailable_urls=[])
        assert path.exists()

    def test_update_sorts_urls(self, tmp_path):
        path = tmp_path / "state.json"
        state = AvailabilityState(path)
        state.update(
            available_urls=["http://shop/z", "http://shop/a"],
            unavailable_urls=["http://shop/y", "http://shop/b"],
        )
        data = _read_state(path)
        assert data["available"] == ["http://shop/a", "http://shop/z"]
        assert data["unavailable"] == ["http://shop/b", "http://shop/y"]

    def test_update_then_load_round_trips(self, tmp_path):
        path = tmp_path / "state.json"
        state = AvailabilityState(path)
        state.update(
            available_urls=["http://shop/a"],
            unavailable_urls=["http://shop/b"],
        )
        state2 = AvailabilityState(path)
        state2.load()
        assert state2.known_urls == {"http://shop/a"}
        assert state2.known_unavailable_urls == {"http://shop/b"}

    def test_update_clears_previous_state(self, tmp_path):
        path = tmp_path / "state.json"
        state = AvailabilityState(path)
        state.update(available_urls=["http://shop/old"], unavailable_urls=[])
        state.update(available_urls=[], unavailable_urls=["http://shop/old"])
        assert state.known_urls == set()
        assert state.known_unavailable_urls == {"http://shop/old"}


# ---------------------------------------------------------------------------
# Transition detection (the logic that lives in cli.py but tested here via state)
# ---------------------------------------------------------------------------

class TestTransitionDetection:
    """Simulate the newly_available / newly_unavailable detection from cli.py."""

    def test_newly_available_detected(self, tmp_path):
        """A URL not in last run's available set is newly available."""
        path = tmp_path / "state.json"
        _write_state(path, {"available": [], "unavailable": []})
        state = AvailabilityState(path)
        state.load()

        current_available_urls = {"http://shop/game"}
        newly_available = current_available_urls - state.known_urls
        assert newly_available == {"http://shop/game"}

    def test_newly_unavailable_detected(self, tmp_path):
        """A URL that was available last run but is now unavailable."""
        path = tmp_path / "state.json"
        _write_state(path, {"available": ["http://shop/game"], "unavailable": []})
        state = AvailabilityState(path)
        state.load()

        current_unavailable_urls = {"http://shop/game"}
        newly_unavailable = current_unavailable_urls & state.known_urls
        assert newly_unavailable == {"http://shop/game"}

    def test_no_change_not_reported(self, tmp_path):
        """A URL already in available from last run is not newly available."""
        path = tmp_path / "state.json"
        _write_state(path, {"available": ["http://shop/game"], "unavailable": []})
        state = AvailabilityState(path)
        state.load()

        current_available_urls = {"http://shop/game"}
        newly_available = current_available_urls - state.known_urls
        assert newly_available == set()
