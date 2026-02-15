"""Tests for BGG client functionality using bgg-api library."""
import pytest
from unittest.mock import Mock, MagicMock, patch
from boardgamegeek.exceptions import BGGApiError, BGGApiRetryError, BGGApiUnauthorizedError
from bgg_mm.bgg import BGGClient, BGGWishlistItem


class MockCollectionItem:
    """Mock collection item from bgg-api library."""
    def __init__(self, id, name, wishlist_priority=None, year=None):
        self.id = id
        self.name = name
        self.wishlist_priority = wishlist_priority
        self.year = year


class MockCollection:
    """Mock collection from bgg-api library."""
    def __init__(self, items):
        self.items = items


class TestBGGClient:
    """Test BGG client functionality with bgg-api library."""

    def test_fetch_wishlist_basic(self, mocker):
        """Test fetching a basic wishlist."""
        # Create mock BGG API client
        mock_client = Mock()
        mock_collection = MockCollection([
            MockCollectionItem(1, "Game One", wishlist_priority=2, year=2024),
            MockCollectionItem(2, "Game Two", wishlist_priority=3, year=2025),
        ])
        mock_client.collection.return_value = mock_collection
        
        # Patch BGGAPIClient constructor
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", subtypes=["boardgame"])
        
        assert len(items) == 2
        assert items[0]["name"] == "Game One"
        assert items[0]["priority"] == 2
        assert items[0]["year"] == 2024
        assert items[1]["name"] == "Game Two"

    def test_fetch_wishlist_with_priority_filter(self, mocker):
        """Test fetching wishlist with priority filter."""
        mock_client = Mock()
        mock_collection = MockCollection([
            MockCollectionItem(1, "Game One", wishlist_priority=2),
            MockCollectionItem(2, "Game Two", wishlist_priority=3),
            MockCollectionItem(3, "Game Three", wishlist_priority=2),
        ])
        mock_client.collection.return_value = mock_collection
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", priorities=[2], subtypes=["boardgame"])
        
        assert len(items) == 2
        assert all(item["priority"] == 2 for item in items)

    def test_fetch_wishlist_handles_retry_error(self, mocker):
        """Test that fetch_wishlist retries on BGG API retry errors."""
        mock_client = Mock()
        mock_collection = MockCollection([
            MockCollectionItem(1, "Game One", wishlist_priority=2),
        ])
        
        # First call raises retry error, second succeeds
        mock_client.collection.side_effect = [
            BGGApiRetryError("Please retry"),
            mock_collection
        ]
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", max_retries=3, poll_delay=0.1, subtypes=["boardgame"])
        
        assert len(items) == 1
        assert mock_client.collection.call_count == 2

    def test_fetch_wishlist_raises_on_max_retries(self, mocker):
        """Test that fetch_wishlist raises error after max retries."""
        mock_client = Mock()
        mock_client.collection.side_effect = BGGApiRetryError("Please retry")
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        
        with pytest.raises(RuntimeError, match="after .* attempts"):
            client.fetch_wishlist(username="testuser", max_retries=2, poll_delay=0.1, subtypes=["boardgame"])

    def test_fetch_wishlist_handles_unauthorized_error(self, mocker):
        """Test that fetch_wishlist provides helpful error for unauthorized errors."""
        mock_client = Mock()
        mock_client.collection.side_effect = BGGApiUnauthorizedError("invalid access token")
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="invalid_token")
        
        with pytest.raises(RuntimeError, match="authentication failed"):
            client.fetch_wishlist(username="testuser", subtypes=["boardgame"])

    def test_fetch_wishlist_with_multiple_subtypes(self, mocker):
        """Test fetching wishlist with multiple subtypes."""
        mock_client = Mock()
        
        # Different items for each subtype
        boardgame_collection = MockCollection([
            MockCollectionItem(1, "Base Game", wishlist_priority=2),
        ])
        expansion_collection = MockCollection([
            MockCollectionItem(2, "Expansion", wishlist_priority=3),
        ])
        
        mock_client.collection.side_effect = [boardgame_collection, expansion_collection]
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", subtypes=["boardgame", "boardgameexpansion"])
        
        assert len(items) == 2
        assert mock_client.collection.call_count == 2

    def test_fetch_wishlist_deduplicates_across_subtypes(self, mocker):
        """Test that items appearing in multiple subtypes are deduplicated."""
        mock_client = Mock()
        
        # Same item in both collections
        same_item_1 = MockCollectionItem(1, "Same Game", wishlist_priority=2)
        same_item_2 = MockCollectionItem(1, "Same Game", wishlist_priority=2)
        
        boardgame_collection = MockCollection([same_item_1])
        expansion_collection = MockCollection([same_item_2])
        
        mock_client.collection.side_effect = [boardgame_collection, expansion_collection]
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", subtypes=["boardgame", "boardgameexpansion"])
        
        # Should only have one item despite being in both collections
        assert len(items) == 1

    def test_fetch_wishlist_handles_missing_year(self, mocker):
        """Test handling items without year published."""
        mock_client = Mock()
        mock_collection = MockCollection([
            MockCollectionItem(1, "Game Without Year", wishlist_priority=1, year=None),
        ])
        mock_client.collection.return_value = mock_collection
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", subtypes=["boardgame"])
        
        assert len(items) == 1
        assert items[0]["year"] is None

    def test_fetch_wishlist_returns_correct_format(self, mocker):
        """Test that returned items have correct format."""
        mock_client = Mock()
        mock_collection = MockCollection([
            MockCollectionItem(123, "Test Game", wishlist_priority=2, year=2024),
        ])
        mock_client.collection.return_value = mock_collection
        
        mocker.patch('bgg_mm.bgg.BGGAPIClient', return_value=mock_client)
        
        client = BGGClient(access_token="test_token")
        items = client.fetch_wishlist(username="testuser", subtypes=["boardgame"])
        
        assert len(items) == 1
        item = items[0]
        assert "name" in item
        assert "object_id" in item
        assert "year" in item
        assert "priority" in item
        assert item["object_id"] == "123"
