# Integration Tests Guide

## Overview

This repository includes comprehensive integration tests that validate the actual BGG API and Moenen en Mariken shop scraping functionality using real API calls. These tests are designed to discover bugs and validate the end-to-end workflow.

## Quick Start

### Running Integration Tests

Integration tests are **disabled by default** to keep regular test runs fast. To run them:

```bash
# Run all integration tests
pytest -m integration tests/

# Run with verbose output
pytest -m integration tests/ -v

# Run specific test categories
pytest -m integration -k "bgg" tests/          # BGG API tests only
pytest -m integration -k "shop" tests/         # Shop scraping tests only
pytest -m integration -k "e2e" tests/          # End-to-end tests only
```

### Running Regular Unit Tests

By default, integration tests are excluded:

```bash
# Run all unit tests (integration tests skipped automatically)
pytest tests/

# Explicitly exclude integration tests
pytest -m "not integration" tests/
```

## Test Categories

### 1. BGG API Integration Tests (6 tests)

These tests validate BGG API functionality with real API calls:

- `test_bgg_api_authentication_with_token` - Verifies authentication works
- `test_bgg_fetch_wishlist_real` - Fetches actual wishlist and validates structure
- `test_bgg_wishlist_priority_filtering` - Tests priority filtering [1, 2, 3]
- `test_bgg_wishlist_subtype_filtering` - Tests subtype filtering
- `test_bgg_wishlist_data_structure` - Validates data field types
- `test_bgg_api_error_handling` - Tests error handling for invalid input

**Example:**
```bash
pytest -m integration -k "test_bgg" tests/ -v
```

### 2. Shop Scraping Integration Tests (7 tests)

These tests validate shop scraping with real HTTP requests:

- `test_shop_search_real_game` - Searches for real board games
- `test_shop_product_availability_detection` - Verifies stock detection logic
- `test_shop_detail_page_parsing` - Tests product detail page parsing
- `test_shop_price_extraction` - Validates price extraction
- `test_shop_backorder_detection` - Tests backorder detection
- `test_shop_out_of_stock_detection` - Tests all stock markers
- `test_shop_url_fallback` - Tests www vs non-www fallback

**Example:**
```bash
pytest -m integration -k "test_shop" tests/ -v
```

### 3. End-to-End Integration Tests (3 tests)

These tests validate the complete workflow:

- `test_e2e_wishlist_to_shop_matching` - Full workflow from BGG to shop
- `test_e2e_availability_state_tracking` - Tests state file management
- `test_e2e_new_availability_detection` - Tests new availability detection

**Example:**
```bash
pytest -m integration -k "test_e2e" tests/ -v
```

## Test Configuration

Integration tests use configuration from `tests/integration_config.py`:

```python
BGG_TEST_USERNAME = "mageleve"
BGG_TEST_TOKEN = "e62efc9d-932d-46e4-a5c4-32d311aae2df"
SHOP_BASE_URL = "http://www.moenen-en-mariken.nl"
TEST_TIMEOUT = 30
MAX_RETRIES = 3
```

## Test Features

### Automatic Retry

Integration tests include automatic retry logic for flaky network requests:

```python
@pytest.mark.flaky(reruns=MAX_RETRIES, reruns_delay=2)
```

This ensures transient network issues don't cause false failures.

### Timeout Protection

All integration tests have timeout protection:

```python
@pytest.mark.timeout(TEST_TIMEOUT)  # 30 seconds for regular tests
@pytest.mark.timeout(60)             # 60 seconds for E2E tests
```

### Detailed Logging

Integration tests log detailed information about API responses for debugging:

```bash
pytest -m integration tests/ -v -s  # -s shows all logging output
```

## Expected Results

### Test Execution Time

- **All Integration Tests**: ~30 seconds
- **BGG API Tests**: ~5-10 seconds
- **Shop Tests**: ~15-20 seconds
- **E2E Tests**: ~10-15 seconds

### Current Status

As of the last run, all 16 integration tests pass:

```
✓ BGG API Integration Tests: 6/6 passed
✓ Shop Scraping Tests: 7/7 passed
✓ End-to-End Tests: 3/3 passed
```

## Bugs Found

Integration tests have discovered and helped fix 3 bugs:

1. **INT-001** (High): Priority field type mismatch
2. **INT-002** (Medium): Year field returns 0 instead of None
3. **INT-003** (Medium): Missing exception handler for invalid username

See [INTEGRATION_BUGS.md](INTEGRATION_BUGS.md) for detailed documentation.

## Best Practices

### When to Run Integration Tests

Run integration tests:
- Before major releases
- After significant code changes to BGG or shop integration
- When troubleshooting API or scraping issues
- As part of CI/CD pipeline (recommended: nightly or weekly)

### Interpreting Failures

If integration tests fail:

1. **Check network connectivity** - Tests require internet access
2. **Verify API credentials** - Ensure BGG token is valid
3. **Check shop availability** - Shop might be down or changed
4. **Review logs** - Use `-v -s` flags for detailed output
5. **Document new bugs** - Add to INTEGRATION_BUGS.md

### Contributing

When adding new features:

1. Add corresponding integration tests
2. Mark tests with `@pytest.mark.integration`
3. Add appropriate timeouts and retry logic
4. Document expected behavior
5. Update this guide if needed

## Troubleshooting

### Tests Taking Too Long

```bash
# Reduce timeout for faster feedback
pytest -m integration tests/ --timeout=15
```

### Network Issues

```bash
# Increase retry count for flaky networks
pytest -m integration tests/ --reruns=5
```

### Debugging Specific Tests

```bash
# Run single test with full output
pytest -m integration tests/test_integration.py::test_bgg_api_authentication_with_token -v -s
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Run nightly at 2 AM
  workflow_dispatch:      # Allow manual trigger

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest -m integration tests/ -v
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-timeout documentation](https://pypi.org/project/pytest-timeout/)
- [pytest-rerunfailures documentation](https://pypi.org/project/pytest-rerunfailures/)
- [BGG API documentation](https://boardgamegeek.com/wiki/page/BGG_XML_API2)

## Support

For issues or questions about integration tests:
1. Check [INTEGRATION_BUGS.md](INTEGRATION_BUGS.md) for known issues
2. Review test logs with `-v -s` flags
3. Create an issue with test output and logs
