"""Tests for state management functionality."""
import pytest
import json
import tempfile
from pathlib import Path
from bgg_mm.state import AvailabilityState


class TestAvailabilityState:
    """Test availability state management."""

    def test_initial_state_empty(self):
        """Test that initial state is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = AvailabilityState(state_file)
            state.load()
            
            assert len(state.known_urls) == 0

    def test_update_and_persist(self):
        """Test updating and persisting state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = AvailabilityState(state_file)
            state.load()
            
            # Update with some URLs
            urls = [
                "http://example.com/game1",
                "http://example.com/game2",
            ]
            state.update(urls)
            
            # File should exist now
            assert state_file.exists()
            
            # Load in a new instance
            state2 = AvailabilityState(state_file)
            state2.load()
            
            assert len(state2.known_urls) == 2
            assert "http://example.com/game1" in state2.known_urls
            assert "http://example.com/game2" in state2.known_urls

    def test_update_replaces_previous_state(self):
        """Test that update replaces previous state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = AvailabilityState(state_file)
            state.load()
            
            # First update
            state.update(["http://example.com/game1"])
            assert len(state.known_urls) == 1
            
            # Second update - should replace
            state.update(["http://example.com/game2", "http://example.com/game3"])
            
            # Should only have the new URLs
            assert len(state.known_urls) == 2
            assert "http://example.com/game1" not in state.known_urls
            assert "http://example.com/game2" in state.known_urls
            assert "http://example.com/game3" in state.known_urls

    def test_load_invalid_json(self):
        """Test loading invalid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            
            # Write invalid JSON
            state_file.write_text("not valid json{", encoding="utf-8")
            
            state = AvailabilityState(state_file)
            state.load()
            
            # Should start with empty state
            assert len(state.known_urls) == 0

    def test_known_urls_returns_copy(self):
        """Test that known_urls returns a copy, not the internal set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = AvailabilityState(state_file)
            state.load()
            
            state.update(["http://example.com/game1"])
            
            # Get the known URLs
            known = state.known_urls
            
            # Modify the returned set
            known.add("http://example.com/game2")
            
            # Internal state should not be affected
            assert "http://example.com/game2" not in state.known_urls
            assert len(state.known_urls) == 1

    def test_state_file_creates_parent_directory(self):
        """Test that state file creation creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "subdir" / "state.json"
            state = AvailabilityState(state_file)
            state.load()
            
            # Update should create the parent directory
            state.update(["http://example.com/game1"])
            
            assert state_file.exists()
            assert state_file.parent.exists()

    def test_json_format(self):
        """Test that saved JSON is properly formatted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = AvailabilityState(state_file)
            state.load()
            
            urls = [
                "http://example.com/game2",
                "http://example.com/game1",
            ]
            state.update(urls)
            
            # Read the file
            content = state_file.read_text(encoding="utf-8")
            data = json.loads(content)
            
            # Should be a list
            assert isinstance(data, list)
            
            # Should be sorted
            assert data == sorted(urls)
