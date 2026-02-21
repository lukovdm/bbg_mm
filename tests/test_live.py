"""Live network tests — hit the real BGG API and Moenen en Mariken shop.

Run with:
    pytest tests/test_live.py -v -m live

Or skip them in normal CI:
    pytest tests/ -m "not live"

The BGG API token is read from the BGG_API_TOKEN environment variable,
matching what the production code expects.
"""
import os

import pytest
import requests

from bgg_mm.bgg import BGGClient, BGGWishlistItem
from bgg_mm.shop import ShopClient, ShopProduct

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BGG_USERNAME = "mageleve"  # The account used in the debug XML fixtures
BGG_TOKEN = os.environ.get("BGG_API_TOKEN", "")
SHOP_BASE_URL = "http://www.moenen-en-mariken.nl"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"User-Agent": "BGG-MM live test/1.0"})
    return s


@pytest.fixture(scope="module")
def bgg_client():
    if not BGG_TOKEN:
        pytest.skip("BGG_API_TOKEN not set — skipping live BGG tests")
    return BGGClient(access_token=BGG_TOKEN)


@pytest.fixture(scope="module")
def shop_client(session):
    return ShopClient(base_url=SHOP_BASE_URL, session=session)


# ---------------------------------------------------------------------------
# BGG live tests
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestBGGLive:
    def test_fetch_wishlist_returns_items(self, bgg_client):
        """Fetch the real BGG wishlist and verify the structure of each item."""
        items = bgg_client.fetch_wishlist(BGG_USERNAME)
        assert isinstance(items, list), "fetch_wishlist should return a list"
        assert len(items) > 0, (
            f"Expected at least one wishlist item for '{BGG_USERNAME}', got none. "
            "The wishlist may be empty or the API token may be invalid."
        )

    def test_wishlist_items_have_required_fields(self, bgg_client):
        items = bgg_client.fetch_wishlist(BGG_USERNAME)
        for item in items:
            assert isinstance(item, BGGWishlistItem)
            assert "name" in item, f"Item missing 'name': {item!r}"
            assert "object_id" in item, f"Item missing 'object_id': {item!r}"
            assert isinstance(item["name"], str) and item["name"], (
                f"'name' should be a non-empty string, got {item['name']!r}"
            )
            assert isinstance(item["object_id"], str) and item["object_id"], (
                f"'object_id' should be a non-empty string, got {item['object_id']!r}"
            )

    def test_wishlist_object_ids_are_unique(self, bgg_client):
        items = bgg_client.fetch_wishlist(BGG_USERNAME)
        ids = [item["object_id"] for item in items]
        assert len(ids) == len(set(ids)), (
            "Duplicate object_ids found — deduplication is broken"
        )

    def test_wishlist_boardgame_subtype_only(self, bgg_client):
        items = bgg_client.fetch_wishlist(BGG_USERNAME, subtypes=["boardgame"])
        assert isinstance(items, list)
        # Just verify we got something back and the structure is correct
        for item in items:
            assert "name" in item
            assert "object_id" in item

    def test_wishlist_priority_filter(self, bgg_client):
        """Filtering by priority 1 (must have) should return a subset of all items."""
        all_items = bgg_client.fetch_wishlist(BGG_USERNAME)
        prio1_items = bgg_client.fetch_wishlist(BGG_USERNAME, priorities=[1])
        assert isinstance(prio1_items, list)
        # Priority-1 list should be a subset (<=) of all items
        all_ids = {item["object_id"] for item in all_items}
        for item in prio1_items:
            assert item["object_id"] in all_ids, (
                f"Priority-1 item {item['name']!r} not found in full wishlist"
            )

    def test_fetch_wishlist_with_expansions(self, bgg_client):
        items = bgg_client.fetch_wishlist(
            BGG_USERNAME, subtypes=["boardgame", "boardgameexpansion"]
        )
        assert isinstance(items, list)


# ---------------------------------------------------------------------------
# Shop live tests
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestShopLive:
    # Use a game that was seen in the debug fixtures (known to exist in the shop).
    KNOWN_GAME = "Vantage"
    KNOWN_GAME_CODE = "850032180863"

    def test_catalog_search_returns_results(self, shop_client):
        """The catalog POST search for a known game should return at least one result."""
        results = shop_client._search_product_catalog(self.KNOWN_GAME, timeout=30)
        assert isinstance(results, list)
        assert len(results) > 0, (
            f"Expected catalog results for '{self.KNOWN_GAME}', got none. "
            "The shop may be down or the game has been removed."
        )

    def test_catalog_result_has_required_fields(self, shop_client):
        results = shop_client._search_product_catalog(self.KNOWN_GAME, timeout=30)
        for r in results:
            assert "title" in r, f"Result missing 'title': {r!r}"
            assert "url" in r, f"Result missing 'url': {r!r}"
            assert r["url"].startswith("http"), f"URL should be absolute: {r['url']!r}"

    def test_fetch_detail_by_code(self, shop_client):
        """Fetch a product detail page by its numeric barcode."""
        product = shop_client.fetch_detail_by_code(self.KNOWN_GAME_CODE, timeout=30)
        assert product is not None, (
            f"Expected a product for code '{self.KNOWN_GAME_CODE}', got None"
        )
        assert isinstance(product, ShopProduct)
        assert product.name, "Product name should not be empty"
        assert product.url, "Product URL should not be empty"
        assert isinstance(product.available, bool)

    def test_fetch_detail_by_code_returns_correct_product(self, shop_client):
        """The detail page for KNOWN_GAME_CODE must describe KNOWN_GAME, not an arbitrary product."""
        product = shop_client.fetch_detail_by_code(self.KNOWN_GAME_CODE, timeout=30)
        assert product is not None, (
            f"Expected a product for code '{self.KNOWN_GAME_CODE}', got None"
        )
        assert self.KNOWN_GAME_CODE in product.url, (
            f"Product URL {product.url!r} should contain the barcode {self.KNOWN_GAME_CODE!r}"
        )
        assert self.KNOWN_GAME.lower() in product.name.lower(), (
            f"Product name {product.name!r} does not contain expected game name {self.KNOWN_GAME!r}. "
            f"The detail page may have been fetched for the wrong product."
        )

    def test_lookup_returns_correct_product(self, shop_client):
        """lookup() must return the product matching the queried game name, not a random result."""
        product = shop_client.lookup(self.KNOWN_GAME, timeout=30)
        assert product is not None, (
            f"lookup('{self.KNOWN_GAME}') returned None — game not found in shop"
        )
        assert self.KNOWN_GAME.lower() in product.name.lower(), (
            f"lookup('{self.KNOWN_GAME}') returned {product.name!r} — wrong product matched. "
            f"Check _pick_best_match scoring."
        )

    def test_lookup_returns_product(self, shop_client):
        """Full lookup pipeline for a known game returns a well-formed ShopProduct."""
        product = shop_client.lookup(self.KNOWN_GAME, timeout=30)
        assert product is not None, (
            f"lookup('{self.KNOWN_GAME}') returned None — game not found in shop"
        )
        assert isinstance(product, ShopProduct)
        assert product.name
        assert product.url.startswith("http")
        assert isinstance(product.available, bool)

    def test_lookup_unknown_game_returns_none(self, shop_client):
        """A made-up game name should return None (not crash)."""
        result = shop_client.lookup("ZzZzThisGameDoesNotExist99999", timeout=30)
        assert result is None

    def test_lookup_price_is_string_or_none(self, shop_client):
        product = shop_client.lookup(self.KNOWN_GAME, timeout=30)
        if product is not None:
            assert product.price is None or isinstance(product.price, str)

    def test_shop_connectivity(self, shop_client):
        """Basic connectivity check — the catalog endpoint should respond 200."""
        response = shop_client._request_with_fallback(
            f"{SHOP_BASE_URL}/producten/",
            timeout=15,
            method="POST",
            data={"f[artnaam]": "test"},
        )
        assert response.status_code == 200, (
            f"Shop returned HTTP {response.status_code} — may be down"
        )


# ---------------------------------------------------------------------------
# Regression tests for subtitle / punctuation matching (real wishlist games)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestSubtitleMatchingLive:
    """Verify that games whose BGG title has a long subtitle are still found.

    These are the exact BGG titles from the mageleve wishlist. The shop
    lists them under a shorter name — the subtitle-stripping + punctuation
    normalisation in _shortened_queries must bridge the gap.
    """

    # Each tuple: (bgg_title, expected_substring_in_shop_name)
    CASES = [
        ("Dead Cells: The Rogue-Lite Board Game", "Dead Cells"),
        ("Clank!: A Deck-Building Adventure",      "Clank"),
        ("Slay the Spire: The Board Game",         "Slay the Spire"),
    ]

    @pytest.mark.parametrize("bgg_title,expected", CASES)
    def test_lookup_finds_game_with_subtitle(self, shop_client, bgg_title, expected):
        """lookup() must return the correct product despite the BGG title having a subtitle."""
        product = shop_client.lookup(bgg_title, timeout=30)
        assert product is not None, (
            f"lookup({bgg_title!r}) returned None. "
            f"The shop may carry it under a shorter name — check _shortened_queries."
        )
        assert expected.lower() in product.name.lower(), (
            f"lookup({bgg_title!r}) returned {product.name!r}, "
            f"which does not contain expected substring {expected!r}."
        )
        assert isinstance(product.available, bool)
        assert product.url.startswith("http")


# ---------------------------------------------------------------------------
# End-to-end live test: BGG wishlist → shop lookup
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestEndToEndLive:
    def test_wishlist_to_shop_lookup(self, bgg_client, shop_client):
        """Fetch first 3 wishlist games and check each against the shop.

        This is the core workflow of the application. We don't assert that
        games are available (stock changes), only that the pipeline runs
        without errors and returns well-formed results.
        """
        items = bgg_client.fetch_wishlist(BGG_USERNAME, subtypes=["boardgame"])
        assert items, "Wishlist is empty — cannot run end-to-end test"

        # Only test the first 3 to keep runtime reasonable
        sample = items[:3]
        for entry in sample:
            name = entry["name"]
            product = shop_client.lookup(name, timeout=30)
            # product can be None (not in shop) or a ShopProduct — both are valid
            if product is not None:
                assert isinstance(product, ShopProduct)
                assert product.url.startswith("http"), (
                    f"Product URL for {name!r} is not absolute: {product.url!r}"
                )
                assert isinstance(product.available, bool)
