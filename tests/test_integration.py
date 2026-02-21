"""Integration tests for bgg_mm.cli — fetch_available_products and main()."""
import json
import os
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
import requests

from bgg_mm.bgg import BGGClient, BGGWishlistItem
from bgg_mm.cli import fetch_available_products, load_config, build_notifier
from bgg_mm.notify import format_ntfy_message, format_ntfy_unavailable_message
from bgg_mm.shop import ShopClient, ShopProduct


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wishlist_item(name: str, object_id: str, available: bool = True) -> BGGWishlistItem:
    return BGGWishlistItem({"name": name, "object_id": object_id, "year": 2020, "priority": 1})


def _make_product(name: str, url: str, available: bool, price: str = "€ 29,95") -> ShopProduct:
    return ShopProduct(name=name, url=url, available=available, price=price)


# ---------------------------------------------------------------------------
# fetch_available_products
# ---------------------------------------------------------------------------

class TestFetchAvailableProducts:
    def _setup(self, wishlist_items, shop_returns: dict):
        """
        *shop_returns* maps game name -> Optional[ShopProduct]
        """
        bgg_client = MagicMock(spec=BGGClient)
        bgg_client.fetch_wishlist.return_value = wishlist_items

        shop_client = MagicMock(spec=ShopClient)
        shop_client.lookup.side_effect = lambda name, **kw: shop_returns.get(name)

        return bgg_client, shop_client

    def test_available_product_returned_in_available_list(self):
        item = _make_wishlist_item("Pandemic", "30549")
        product = _make_product("Pandemic", "http://shop.example/pandemic", available=True)
        bgg, shop = self._setup([item], {"Pandemic": product})

        available, results = fetch_available_products(bgg, shop, "testuser", None)

        assert len(available) == 1
        assert available[0].name == "Pandemic"

    def test_unavailable_product_not_in_available_list(self):
        item = _make_wishlist_item("Yokohama", "39856")
        product = _make_product("Yokohama", "http://shop.example/yokohama", available=False)
        bgg, shop = self._setup([item], {"Yokohama": product})

        available, results = fetch_available_products(bgg, shop, "testuser", None)

        assert available == []
        assert len(results) == 1

    def test_not_found_product_excluded_from_available(self):
        item = _make_wishlist_item("NonExistentGame", "99999")
        bgg, shop = self._setup([item], {"NonExistentGame": None})

        available, results = fetch_available_products(bgg, shop, "testuser", None)

        assert available == []
        assert results[0][1] is None

    def test_mixed_results(self):
        items = [
            _make_wishlist_item("Pandemic", "1"),
            _make_wishlist_item("Yokohama", "2"),
            _make_wishlist_item("Unknown", "3"),
        ]
        shop_returns = {
            "Pandemic": _make_product("Pandemic", "http://shop/p", available=True),
            "Yokohama": _make_product("Yokohama", "http://shop/y", available=False),
            "Unknown": None,
        }
        bgg, shop = self._setup(items, shop_returns)

        available, results = fetch_available_products(bgg, shop, "testuser", None)

        assert len(available) == 1
        assert available[0].name == "Pandemic"
        assert len(results) == 3

    def test_passes_priorities_to_bgg(self):
        bgg_client = MagicMock(spec=BGGClient)
        bgg_client.fetch_wishlist.return_value = []
        shop_client = MagicMock(spec=ShopClient)

        fetch_available_products(bgg_client, shop_client, "user", priorities=[1, 2], subtypes=["boardgame"])

        bgg_client.fetch_wishlist.assert_called_once_with(
            username="user", priorities=[1, 2], subtypes=["boardgame"]
        )

    def test_empty_wishlist_returns_empty(self):
        bgg_client = MagicMock(spec=BGGClient)
        bgg_client.fetch_wishlist.return_value = []
        shop_client = MagicMock(spec=ShopClient)

        available, results = fetch_available_products(bgg_client, shop_client, "user", None)

        assert available == []
        assert results == []


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        config = {"bgg": {"username": "testuser"}, "shop": {"base_url": "http://shop.example"}}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        result = load_config(config_file)
        assert result["bgg"]["username"] == "testuser"

    def test_raises_for_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# main() — BGG_API_TOKEN env var handling
# ---------------------------------------------------------------------------

class TestMainEnvVar:
    def test_main_raises_if_token_missing(self, tmp_path):
        """main() should raise ValueError when BGG_API_TOKEN is not set."""
        config = {
            "bgg": {"username": "testuser"},
            "shop": {"base_url": "http://shop.example"},
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        with patch("sys.argv", ["bgg-mm", "--config", str(config_file)]):
            with patch.dict(os.environ, {}, clear=True):
                # Remove the token if it happens to be set
                env = {k: v for k, v in os.environ.items() if k != "BGG_API_TOKEN"}
                with patch.dict(os.environ, env, clear=True):
                    from bgg_mm.cli import main
                    with pytest.raises(ValueError, match="BGG_API_TOKEN"):
                        main()

    def test_main_raises_if_bgg_username_missing(self, tmp_path):
        config = {"bgg": {}, "shop": {"base_url": "http://shop.example"}}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        with patch("sys.argv", ["bgg-mm", "--config", str(config_file)]):
            with patch.dict(os.environ, {"BGG_API_TOKEN": "fake-token"}, clear=False):
                from bgg_mm.cli import main
                with pytest.raises(ValueError, match="bgg.username"):
                    main()

    def test_main_raises_if_shop_url_missing(self, tmp_path):
        config = {"bgg": {"username": "testuser"}, "shop": {}}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        with patch("sys.argv", ["bgg-mm", "--config", str(config_file)]):
            with patch.dict(os.environ, {"BGG_API_TOKEN": "fake-token"}, clear=False):
                from bgg_mm.cli import main
                with pytest.raises(ValueError, match="shop.base_url"):
                    main()


# ---------------------------------------------------------------------------
# build_notifier
# ---------------------------------------------------------------------------

class TestBuildNotifier:
    def test_returns_none_when_no_config(self):
        session = MagicMock(spec=requests.Session)
        assert build_notifier(None, session) is None

    def test_empty_dict_raises_missing_topic(self):
        session = MagicMock(spec=requests.Session)
        # An empty dict means ntfy is configured but 'topic' key is absent — should raise
        with pytest.raises(ValueError, match="topic"):
            build_notifier({}, session)

    def test_builds_notifier_with_topic(self):
        from bgg_mm.notify import NtfyNotifier
        session = MagicMock(spec=requests.Session)
        notifier = build_notifier({"topic": "my-topic"}, session)
        assert notifier is not None
        assert isinstance(notifier, NtfyNotifier)

    def test_uses_custom_base_url(self):
        from bgg_mm.notify import NtfyNotifier
        session = MagicMock(spec=requests.Session)
        notifier = build_notifier({"topic": "t", "base_url": "https://custom.ntfy.io"}, session)
        assert notifier is not None
        assert "custom.ntfy.io" in notifier.base_url


# ---------------------------------------------------------------------------
# format_ntfy_message / format_ntfy_unavailable_message
# ---------------------------------------------------------------------------

class TestFormatNtfyMessage:
    def _make_product(self, name: str, url: str, price: str = None) -> ShopProduct:
        return ShopProduct(name=name, url=url, available=True, price=price)

    def test_available_message_contains_product_name(self):
        products = [self._make_product("Pandemic", "http://shop/p", price="€ 49,95")]
        body = format_ntfy_message(products)
        assert "Pandemic" in body
        assert "€ 49,95" in body
        assert "http://shop/p" in body

    def test_available_message_omits_price_when_none(self):
        products = [self._make_product("Azul", "http://shop/a")]
        body = format_ntfy_message(products)
        assert "Azul" in body
        # No price parentheses should appear
        assert "(" not in body

    def test_available_message_multiple_products(self):
        products = [
            self._make_product("Pandemic", "http://shop/p"),
            self._make_product("Azul", "http://shop/a"),
        ]
        body = format_ntfy_message(products)
        assert "Pandemic" in body
        assert "Azul" in body

    def test_unavailable_message_contains_product_name(self):
        products = [ShopProduct(name="Pandemic", url="http://shop/p", available=False)]
        body = format_ntfy_unavailable_message(products)
        assert "Pandemic" in body
        assert "http://shop/p" in body

    def test_unavailable_message_multiple_products(self):
        products = [
            ShopProduct(name="Pandemic", url="http://shop/p", available=False),
            ShopProduct(name="Azul", url="http://shop/a", available=False),
        ]
        body = format_ntfy_unavailable_message(products)
        assert "Pandemic" in body
        assert "Azul" in body

    def test_available_and_unavailable_messages_are_distinct(self):
        products = [ShopProduct(name="Pandemic", url="http://shop/p", available=True, price="€ 10")]
        available_body = format_ntfy_message(products)
        unavail_body = format_ntfy_unavailable_message(products)
        # The two messages should have different framing text
        assert available_body != unavail_body
