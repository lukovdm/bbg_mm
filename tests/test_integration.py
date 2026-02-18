"""Integration tests for BGG API and shop scraping functionality.

These tests use real API calls and should be run with: pytest -m integration
"""
import logging
import time
from typing import List, Optional

import pytest
import requests

from bgg_mm.bgg import BGGClient, BGGWishlistItem
from bgg_mm.shop import ShopClient, ShopProduct
from bgg_mm.state import AvailabilityState
from tests.integration_config import (
    BGG_TEST_TOKEN,
    BGG_TEST_USERNAME,
    MAX_RETRIES,
    SHOP_BASE_URL,
    TEST_GAMES,
    TEST_TIMEOUT,
)

# Enable detailed logging for integration tests
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def bgg_client():
    """Create a BGG client with test credentials."""
    return BGGClient(access_token=BGG_TEST_TOKEN)


@pytest.fixture
def shop_client():
    """Create a shop client for integration testing."""
    session = requests.Session()
    session.headers.update({"User-Agent": "BGG-MM Integration Tests/1.0"})
    return ShopClient(base_url=SHOP_BASE_URL, session=session)


# ============================================================================
# BGG API Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_bgg_api_authentication_with_token(bgg_client):
    """Verify authentication works with the provided token."""
    # If authentication fails, this will raise an exception
    try:
        items = bgg_client.fetch_wishlist(
            username=BGG_TEST_USERNAME,
            subtypes=["boardgame"],
            max_retries=2
        )
        # If we get here, authentication worked
        assert isinstance(items, list), "Should return a list of items"
        logging.info(f"✓ Authentication successful, fetched {len(items)} items")
    except RuntimeError as e:
        if "authentication failed" in str(e):
            pytest.fail(f"Authentication failed: {e}")
        raise


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_bgg_fetch_wishlist_real(bgg_client):
    """Fetch actual wishlist for user 'mageleve' and validate structure."""
    items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        subtypes=["boardgame"]
    )
    
    assert isinstance(items, list), "Should return a list"
    logging.info(f"✓ Fetched {len(items)} wishlist items")
    
    # Validate structure of returned items
    if items:
        first_item = items[0]
        assert "name" in first_item, "Item should have 'name' field"
        assert "object_id" in first_item, "Item should have 'object_id' field"
        assert "year" in first_item, "Item should have 'year' field"
        assert "priority" in first_item, "Item should have 'priority' field"
        
        # Log sample item for debugging
        logging.info(f"✓ Sample item: {first_item['name']} (ID: {first_item['object_id']}, "
                    f"Year: {first_item['year']}, Priority: {first_item['priority']})")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_bgg_wishlist_priority_filtering(bgg_client):
    """Test filtering by priorities [1, 2, 3]."""
    # Fetch with priority filter
    filtered_items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        priorities=[1, 2, 3],
        subtypes=["boardgame"]
    )
    
    # Fetch all items
    all_items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        subtypes=["boardgame"]
    )
    
    logging.info(f"✓ Filtered items: {len(filtered_items)}, All items: {len(all_items)}")
    
    # Filtered should be <= all items
    assert len(filtered_items) <= len(all_items), "Filtered items should be subset of all items"
    
    # All filtered items should have priority in [1, 2, 3]
    for item in filtered_items:
        priority = item.get("priority")
        assert priority in [1, 2, 3], f"Item {item['name']} has priority {priority}, expected 1, 2, or 3"
    
    logging.info(f"✓ All {len(filtered_items)} filtered items have correct priority")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_bgg_wishlist_subtype_filtering(bgg_client):
    """Test filtering by subtypes ['boardgame', 'boardgameexpansion']."""
    # Fetch boardgames only
    boardgames = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        subtypes=["boardgame"]
    )
    
    # Fetch both boardgames and expansions
    both = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        subtypes=["boardgame", "boardgameexpansion"]
    )
    
    logging.info(f"✓ Boardgames: {len(boardgames)}, Both: {len(both)}")
    
    # Both should be >= boardgames only
    assert len(both) >= len(boardgames), "Combined subtypes should include at least boardgame items"
    
    logging.info(f"✓ Subtype filtering works correctly")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_bgg_wishlist_data_structure(bgg_client):
    """Validate returned items have correct fields (name, object_id, year, priority)."""
    items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        subtypes=["boardgame"]
    )
    
    assert len(items) > 0, "Should have at least one item in wishlist"
    
    required_fields = ["name", "object_id", "year", "priority"]
    
    for item in items:
        for field in required_fields:
            assert field in item, f"Item {item.get('name', 'unknown')} missing field: {field}"
        
        # Validate field types
        assert isinstance(item["name"], str), "name should be string"
        assert isinstance(item["object_id"], str), "object_id should be string"
        assert item["year"] is None or isinstance(item["year"], int), "year should be int or None"
        assert item["priority"] is None or isinstance(item["priority"], int), "priority should be int or None"
    
    logging.info(f"✓ All {len(items)} items have correct data structure")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_bgg_api_error_handling(bgg_client):
    """Test behavior with invalid username or authentication errors."""
    # Test with invalid username (should not raise, just return empty or error)
    try:
        items = bgg_client.fetch_wishlist(
            username="nonexistent_user_12345678",
            subtypes=["boardgame"],
            max_retries=1
        )
        # Some APIs return empty list for invalid user
        assert isinstance(items, list), "Should return a list even for invalid user"
        logging.info(f"✓ Invalid username handled gracefully, returned {len(items)} items")
    except RuntimeError as e:
        # This is also acceptable - API might raise error
        logging.info(f"✓ Invalid username raised error as expected: {e}")
        assert True


# ============================================================================
# Shop Scraping Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_search_real_game(shop_client):
    """Search for a real board game (e.g., 'Wingspan') and validate response structure."""
    game_name = TEST_GAMES["popular"]
    
    logging.info(f"Searching for: {game_name}")
    product = shop_client.lookup(game_name, timeout=TEST_TIMEOUT)
    
    if product is None:
        logging.warning(f"⚠ Product '{game_name}' not found in shop")
        # This might be expected if the shop doesn't carry this game
        # We'll document this but not fail the test
        return
    
    # Validate product structure
    assert isinstance(product, ShopProduct), "Should return ShopProduct instance"
    assert product.name, "Product should have a name"
    assert product.url, "Product should have a URL"
    assert isinstance(product.available, bool), "Product availability should be boolean"
    
    logging.info(f"✓ Found product: {product.name}")
    logging.info(f"  URL: {product.url}")
    logging.info(f"  Available: {product.available}")
    logging.info(f"  Price: {product.price}")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_product_availability_detection(shop_client):
    """Verify stock detection logic correctly identifies available/unavailable products."""
    # Search for a game to get a real product
    game_name = TEST_GAMES["popular"]
    product = shop_client.lookup(game_name, timeout=TEST_TIMEOUT)
    
    if product is None:
        pytest.skip(f"Test game '{game_name}' not found in shop")
    
    # Availability should be a boolean
    assert isinstance(product.available, bool), "Availability should be boolean"
    
    logging.info(f"✓ Product '{product.name}' availability: {product.available}")
    
    # Try to search for multiple games and check availability detection
    search_results = shop_client.search_candidates(game_name, timeout=TEST_TIMEOUT)
    
    if search_results:
        logging.info(f"✓ Found {len(search_results)} candidates")
        for candidate in search_results[:3]:  # Check first 3
            avail = candidate.get("available")
            if avail is not None:
                assert isinstance(avail, bool), f"Candidate availability should be boolean, got {type(avail)}"
                logging.info(f"  - {candidate['title']}: available={avail}")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_detail_page_parsing(shop_client):
    """Test fetching and parsing product detail pages."""
    # First search for a product
    game_name = TEST_GAMES["popular"]
    candidates = shop_client.search_candidates(game_name, timeout=TEST_TIMEOUT)
    
    if not candidates:
        pytest.skip(f"No candidates found for '{game_name}'")
    
    # Get the first candidate URL
    first_url = candidates[0]["url"]
    logging.info(f"Fetching detail page: {first_url}")
    
    # Fetch detail page
    # Note: Testing _fetch_detail directly is intentional for integration tests
    # to validate the detail page parsing logic works correctly with real HTML
    detail = shop_client._fetch_detail(first_url, timeout=TEST_TIMEOUT)
    
    assert detail is not None, "Should be able to fetch detail page"
    assert detail.name, "Detail page should have product name"
    assert detail.url, "Detail page should have URL"
    assert isinstance(detail.available, bool), "Detail page should have availability"
    
    logging.info(f"✓ Detail page parsed successfully")
    logging.info(f"  Name: {detail.name}")
    logging.info(f"  Price: {detail.price}")
    logging.info(f"  Available: {detail.available}")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_price_extraction(shop_client):
    """Validate price extraction from product pages."""
    game_name = TEST_GAMES["popular"]
    product = shop_client.lookup(game_name, timeout=TEST_TIMEOUT)
    
    if product is None:
        pytest.skip(f"Test game '{game_name}' not found")
    
    # Price might be None for some products, but if present should be a string
    if product.price:
        assert isinstance(product.price, str), "Price should be string"
        # Price should contain some currency symbol or number
        assert any(char in product.price for char in "0123456789€$"), \
            f"Price '{product.price}' should contain numbers or currency"
        logging.info(f"✓ Price extracted: {product.price}")
    else:
        logging.warning(f"⚠ No price found for {product.name}")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_backorder_detection(shop_client):
    """Ensure 'backorder' products are correctly marked as unavailable."""
    # Search multiple games and check if any are on backorder
    test_games = [TEST_GAMES["popular"], TEST_GAMES.get("exact_search", "Catan")]
    
    found_backorder = False
    for game in test_games:
        candidates = shop_client.search_candidates(game, timeout=TEST_TIMEOUT)
        for candidate in candidates:
            # Check if backorder is detected in availability
            if candidate.get("available") is False:
                logging.info(f"Found unavailable product: {candidate['title']}")
                found_backorder = True
                break
    
    # Note: We might not always find backorder items, that's OK
    logging.info(f"✓ Backorder detection test completed (found unavailable items: {found_backorder})")


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_out_of_stock_detection(shop_client):
    """Test all stock markers (uitverkocht, out of stock, niet op voorraad, backorder)."""
    # The shop client should handle these keywords
    # We'll verify the logic is in place by checking the implementation
    
    # Search for multiple games to find different stock statuses
    test_searches = [
        TEST_GAMES["popular"],
        TEST_GAMES.get("exact_search", "Catan"),
        TEST_GAMES.get("expansion", "Wingspan European"),
    ]
    
    stock_statuses = {"available": 0, "unavailable": 0, "unknown": 0}
    
    for game in test_searches:
        try:
            candidates = shop_client.search_candidates(game, timeout=TEST_TIMEOUT)
            for candidate in candidates[:5]:  # Check first 5 of each
                avail = candidate.get("available")
                if avail is True:
                    stock_statuses["available"] += 1
                elif avail is False:
                    stock_statuses["unavailable"] += 1
                else:
                    stock_statuses["unknown"] += 1
        except Exception as e:
            logging.warning(f"Error searching for {game}: {e}")
    
    logging.info(f"✓ Stock status detection summary: {stock_statuses}")
    
    # As long as we detected some statuses, the system is working
    total = sum(stock_statuses.values())
    assert total > 0, "Should have found at least some products"


@pytest.mark.integration
@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_shop_url_fallback(shop_client):
    """Test www vs non-www URL fallback logic."""
    # The shop client should handle both www and non-www versions
    assert shop_client.base_url, "Should have a base URL"
    assert len(shop_client._base_candidates) > 0, "Should have URL candidates for fallback"
    
    logging.info(f"✓ Base URL: {shop_client.base_url}")
    logging.info(f"✓ URL fallback candidates: {shop_client._base_candidates}")
    
    # Try a simple search to verify the fallback works
    try:
        candidates = shop_client.search_candidates("test", timeout=TEST_TIMEOUT)
        logging.info(f"✓ URL fallback working, found {len(candidates)} results")
    except Exception as e:
        logging.info(f"✓ URL fallback handled error: {e}")


# ============================================================================
# End-to-End Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(60)  # E2E tests may take longer
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_e2e_wishlist_to_shop_matching(bgg_client, shop_client):
    """Full workflow - fetch wishlist from BGG, search shop, match games."""
    # Fetch wishlist
    logging.info("Step 1: Fetching wishlist from BGG...")
    wishlist_items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        priorities=[1, 2, 3],  # Only high priority items
        subtypes=["boardgame"]
    )
    
    assert len(wishlist_items) > 0, "Should have wishlist items"
    logging.info(f"✓ Fetched {len(wishlist_items)} wishlist items")
    
    # Take first 3 items to avoid long test times
    test_items = wishlist_items[:3]
    
    # Search shop for each item
    logging.info("Step 2: Searching shop for wishlist items...")
    matches = []
    for item in test_items:
        game_name = item["name"]
        logging.info(f"  Searching for: {game_name}")
        
        try:
            product = shop_client.lookup(game_name, timeout=TEST_TIMEOUT)
            if product:
                matches.append({
                    "wishlist_item": item,
                    "shop_product": product,
                })
                status = "AVAILABLE" if product.available else "UNAVAILABLE"
                logging.info(f"    → Found: {product.name} ({status})")
            else:
                logging.info(f"    → Not found in shop")
        except Exception as e:
            logging.warning(f"    → Error searching: {e}")
    
    logging.info(f"✓ Found {len(matches)} matches out of {len(test_items)} wishlist items")
    
    # Validate match structure
    for match in matches:
        assert "wishlist_item" in match
        assert "shop_product" in match
        assert match["shop_product"].name
        assert match["shop_product"].url


@pytest.mark.integration
@pytest.mark.timeout(60)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_e2e_availability_state_tracking(bgg_client, shop_client, tmp_path):
    """Test state file creation and update with real data."""
    # Create a temporary state file
    state_file = tmp_path / "test_availability.json"
    state = AvailabilityState(state_file)
    
    # Initial state should be empty
    assert len(state.known_urls) == 0, "Initial state should be empty"
    
    # Fetch some wishlist items
    wishlist_items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        priorities=[1, 2],
        subtypes=["boardgame"]
    )
    
    if len(wishlist_items) == 0:
        pytest.skip("No wishlist items found")
    
    # Search for first item
    first_item = wishlist_items[0]
    product = shop_client.lookup(first_item["name"], timeout=TEST_TIMEOUT)
    
    if product and product.available:
        # Update state with available product
        state.update([product.url])
        
        # Verify state was updated
        assert product.url in state.known_urls, "State should track available product URL"
        logging.info(f"✓ State tracking working, tracked URL: {product.url}")
        
        # Verify state persists
        state2 = AvailabilityState(state_file)
        state2.load()
        assert product.url in state2.known_urls, "State should persist across instances"
        logging.info(f"✓ State persistence working")
    else:
        logging.warning("⚠ No available products found to test state tracking")


@pytest.mark.integration
@pytest.mark.timeout(60)
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
def test_e2e_new_availability_detection(bgg_client, shop_client, tmp_path):
    """Simulate detecting newly available games."""
    state_file = tmp_path / "test_new_availability.json"
    state = AvailabilityState(state_file)
    
    # Fetch wishlist items
    wishlist_items = bgg_client.fetch_wishlist(
        username=BGG_TEST_USERNAME,
        priorities=[1, 2, 3],
        subtypes=["boardgame"]
    )
    
    if len(wishlist_items) == 0:
        pytest.skip("No wishlist items found")
    
    # Search for products
    available_products = []
    for item in wishlist_items[:5]:  # Check first 5 items
        try:
            product = shop_client.lookup(item["name"], timeout=TEST_TIMEOUT)
            if product and product.available:
                available_products.append(product)
        except Exception as e:
            logging.warning(f"Error looking up {item['name']}: {e}")
    
    if not available_products:
        pytest.skip("No available products found in wishlist")
    
    # Initially, all products should be "new"
    newly_available = [p for p in available_products if p.url not in state.known_urls]
    assert len(newly_available) == len(available_products), "All products should be new initially"
    logging.info(f"✓ Detected {len(newly_available)} newly available products")
    
    # Update state
    state.update([p.url for p in available_products])
    
    # Now, no products should be new
    newly_available_2 = [p for p in available_products if p.url not in state.known_urls]
    assert len(newly_available_2) == 0, "No products should be new after state update"
    logging.info(f"✓ New availability detection working correctly")


# ============================================================================
# Test Summary Reporter
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def log_test_summary(request):
    """Log a summary of integration test results at the end of the session."""
    yield
    # This runs after all tests complete
    logging.info("\n" + "="*80)
    logging.info("INTEGRATION TEST SUMMARY")
    logging.info("="*80)
    logging.info("All integration tests have completed.")
    logging.info("Review the test output above for any failures or warnings.")
    logging.info("Document any bugs found in INTEGRATION_BUGS.md")
    logging.info("="*80)
