"""Tests for notification functionality."""
import pytest
from unittest.mock import Mock
from bgg_mm.notify import NtfyNotifier, format_ntfy_message
from bgg_mm.shop import ShopProduct


class TestNtfyNotifier:
    """Test ntfy notification functionality."""

    def test_send_notification_basic(self, mocker):
        """Test sending a basic notification."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        
        notifier = NtfyNotifier(
            base_url="https://ntfy.sh",
            topic="test-topic",
            session=mock_session
        )
        
        notifier.send(title="Test Title", body="Test Body")
        
        # Verify the call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        
        assert "https://ntfy.sh/test-topic" in call_args[0]
        assert call_args[1]["data"] == b"Test Body"
        assert call_args[1]["headers"]["Title"] == "Test Title"

    def test_send_notification_with_priority(self, mocker):
        """Test sending notification with priority."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        
        notifier = NtfyNotifier(
            base_url="https://ntfy.sh",
            topic="test-topic",
            session=mock_session,
            priority="high"
        )
        
        notifier.send(title="Test", body="Body")
        
        call_args = mock_session.post.call_args
        assert call_args[1]["headers"]["Priority"] == "high"

    def test_send_notification_with_tags(self, mocker):
        """Test sending notification with tags."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        
        notifier = NtfyNotifier(
            base_url="https://ntfy.sh",
            topic="test-topic",
            session=mock_session,
            tags=["game", "bgg"]
        )
        
        notifier.send(title="Test", body="Body")
        
        call_args = mock_session.post.call_args
        assert call_args[1]["headers"]["Tags"] == "game,bgg"

    def test_send_notification_with_token(self, mocker):
        """Test sending notification with authentication token."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        
        notifier = NtfyNotifier(
            base_url="https://ntfy.sh",
            topic="test-topic",
            session=mock_session,
            token="secret-token"
        )
        
        notifier.send(title="Test", body="Body")
        
        call_args = mock_session.post.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer secret-token"

    def test_base_url_normalization(self):
        """Test that base URLs are normalized correctly."""
        notifier = NtfyNotifier(
            base_url="https://ntfy.sh/",  # With trailing slash
            topic="test-topic"
        )
        
        assert notifier.base_url == "https://ntfy.sh"

    def test_topic_normalization(self):
        """Test that topic is normalized correctly."""
        notifier = NtfyNotifier(
            base_url="https://ntfy.sh",
            topic="/test-topic/"  # With slashes
        )
        
        assert notifier.topic == "test-topic"


class TestFormatNtfyMessage:
    """Test ntfy message formatting."""

    def test_format_single_product(self):
        """Test formatting a single product."""
        products = [
            ShopProduct(
                name="Vantage",
                url="http://example.com/vantage",
                available=True,
                price="€ 45,00"
            )
        ]
        
        message = format_ntfy_message(products)
        
        assert "Vantage" in message
        assert "€ 45,00" in message
        assert "http://example.com/vantage" in message
        assert "Happy gaming!" in message

    def test_format_multiple_products(self):
        """Test formatting multiple products."""
        products = [
            ShopProduct(
                name="Vantage",
                url="http://example.com/vantage",
                available=True,
                price="€ 45,00"
            ),
            ShopProduct(
                name="Zombicide",
                url="http://example.com/zombicide",
                available=True,
                price="€ 50,00"
            )
        ]
        
        message = format_ntfy_message(products)
        
        assert "Vantage" in message
        assert "Zombicide" in message
        assert "€ 45,00" in message
        assert "€ 50,00" in message

    def test_format_product_without_price(self):
        """Test formatting a product without price."""
        products = [
            ShopProduct(
                name="Mystery Game",
                url="http://example.com/mystery",
                available=True,
                price=None
            )
        ]
        
        message = format_ntfy_message(products)
        
        assert "Mystery Game" in message
        assert "http://example.com/mystery" in message
        # Should not have empty parentheses
        assert "()" not in message

    def test_format_empty_list(self):
        """Test formatting an empty list."""
        message = format_ntfy_message([])
        
        # Should still have the header and footer
        assert "Happy gaming!" in message
