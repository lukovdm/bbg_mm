"""Configuration for integration tests."""

# BGG API Configuration
# Note: These credentials are intentionally hardcoded for integration testing
# as specified in the requirements. This is a test account token provided
# specifically for integration testing purposes.
BGG_TEST_USERNAME = "mageleve"
BGG_TEST_TOKEN = "e62efc9d-932d-46e4-a5c4-32d311aae2df"

# Shop Configuration
SHOP_BASE_URL = "http://www.moenen-en-mariken.nl"

# Test Settings
TEST_TIMEOUT = 30
MAX_RETRIES = 3

# Known test games for validation
TEST_GAMES = {
    "popular": "Wingspan",  # A well-known game likely to be found
    "exact_search": "Catan",  # Another common game
    "expansion": "Wingspan: European Expansion",  # Test expansion searches
}
