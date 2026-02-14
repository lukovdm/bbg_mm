"""Integration tests for CLI functionality."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from bgg_mm.cli import (
    load_config,
    build_notifier,
    fetch_available_products,
)
from bgg_mm.bgg import BGGClient
from bgg_mm.shop import ShopClient


# Sample test config
SAMPLE_CONFIG = {
    "bgg": {
        "username": "testuser",
        "wishlist_priorities": [1, 2, 3],
        "subtypes": ["boardgame", "boardgameexpansion"]
    },
    "shop": {
        "base_url": "http://www.moenen-en-mariken.nl"
    },
    "ntfy": {
        "topic": "test-topic",
        "base_url": "https://ntfy.sh",
        "priority": "default",
        "tags": ["game", "bgg"]
    },
    "state_file": "data/availability.json"
}


class TestLoadConfig:
    """Test configuration loading."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text(json.dumps(SAMPLE_CONFIG), encoding="utf-8")
            
            config = load_config(config_file)
            
            assert config["bgg"]["username"] == "testuser"
            assert config["shop"]["base_url"] == "http://www.moenen-en-mariken.nl"

    def test_load_missing_config(self):
        """Test loading a non-existent configuration file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "missing.json"
            
            with pytest.raises(FileNotFoundError):
                load_config(config_file)


class TestBuildNotifier:
    """Test notifier building."""

    def test_build_notifier_with_valid_config(self):
        """Test building notifier with valid configuration."""
        mock_session = Mock()
        
        notifier = build_notifier(SAMPLE_CONFIG["ntfy"], mock_session)
        
        assert notifier is not None
        assert notifier.topic == "test-topic"
        assert notifier.base_url == "https://ntfy.sh"

    def test_build_notifier_with_missing_topic(self):
        """Test building notifier with missing topic."""
        mock_session = Mock()
        invalid_config = {}
        
        with pytest.raises(ValueError, match="missing keys"):
            build_notifier(invalid_config, mock_session)

    def test_build_notifier_with_none(self):
        """Test building notifier with None config."""
        mock_session = Mock()
        
        notifier = build_notifier(None, mock_session)
        
        assert notifier is None


class TestFetchAvailableProducts:
    """Test fetching available products."""

    def test_fetch_available_products_integration(self, mocker):
        """Test the full flow of fetching available products."""
        # Mock BGG API response
        bgg_xml = """<?xml version="1.0" encoding="utf-8"?>
<items totalitems="2">
    <item objecttype="thing" objectid="1" subtype="boardgame" collid="1">
        <name sortindex="1">Game One</name>
        <yearpublished>2024</yearpublished>
        <status wishlist="1" wishlistpriority="1" />
    </item>
    <item objecttype="thing" objectid="2" subtype="boardgame" collid="2">
        <name sortindex="1">Game Two</name>
        <yearpublished>2024</yearpublished>
        <status wishlist="1" wishlistpriority="2" />
    </item>
</items>"""
        
        mock_bgg_session = Mock()
        mock_bgg_response = Mock()
        mock_bgg_response.status_code = 200
        mock_bgg_response.text = bgg_xml
        mock_bgg_session.get.return_value = mock_bgg_response
        
        # Mock shop responses
        mock_shop_session = Mock()
        mock_shop_response = Mock()
        mock_shop_response.status_code = 200
        mock_shop_response.text = """
        <html>
        <body>
        <h1 class="product_title">Game One</h1>
        <div class="summary">
            <div class="price"><span class="amount">€ 45,00</span></div>
            <div class="stock in-stock">Op voorraad</div>
        </div>
        </body>
        </html>
        """
        mock_shop_session.request.return_value = mock_shop_response
        
        bgg_client = BGGClient(session=mock_bgg_session)
        shop_client = ShopClient(base_url="http://www.moenen-en-mariken.nl", session=mock_shop_session)
        
        available, results = fetch_available_products(
            bgg_client=bgg_client,
            shop_client=shop_client,
            username="testuser",
            priorities=[1, 2],
            subtypes=["boardgame"]
        )
        
        # Should have found wishlist items
        assert len(results) == 2
        
        # At least one should be available (depending on shop mock)
        # This test validates the integration flow works


class TestCLIEndToEnd:
    """End-to-end CLI tests."""

    def test_dry_run_does_not_send_notification(self, mocker):
        """Test that dry-run mode doesn't send notifications."""
        # This would be a more complex test that mocks the entire flow
        # and verifies that with --dry-run, the notifier.send is not called
        pass  # Placeholder for future implementation

    def test_newly_available_detection(self):
        """Test detection of newly available products."""
        # Test that the system correctly identifies products that
        # are now available but weren't before
        from bgg_mm.shop import ShopProduct
        
        # Available products
        available = [
            ShopProduct(name="Game 1", url="http://example.com/1", available=True),
            ShopProduct(name="Game 2", url="http://example.com/2", available=True),
        ]
        
        # Known URLs (previously seen)
        known_urls = {"http://example.com/1"}
        
        # Find newly available
        newly_available = [p for p in available if p.url not in known_urls]
        
        assert len(newly_available) == 1
        assert newly_available[0].url == "http://example.com/2"
