# Integration Test Bug Documentation

This file documents bugs discovered during integration testing of the BGG API and shop scraping functionality.

## Bug Report Template

Each bug should be documented with:
- **Bug ID**: Unique identifier
- **Severity**: Critical | High | Medium | Low
- **Component**: BGG API | Shop Scraping | E2E Workflow
- **Description**: What is the bug?
- **Expected Behavior**: What should happen?
- **Actual Behavior**: What actually happens?
- **Steps to Reproduce**: How to reproduce the bug?
- **Stack Trace/Error**: Any error messages or stack traces
- **Status**: Open | In Progress | Fixed

---

## Bugs Found

### Bug #1: Priority Field Type Mismatch

**Bug ID**: INT-001  
**Severity**: High  
**Component**: BGG API  
**Description**: The BGG API library returns wishlist priority as a string instead of an integer, causing type validation failures and potential filtering issues.

**Expected Behavior**: The `priority` field in BGGWishlistItem should be an integer (or None)

**Actual Behavior**: The `priority` field is returned as a string (e.g., '3' instead of 3)

**Steps to Reproduce**:
1. Fetch wishlist using BGGClient.fetch_wishlist()
2. Check the type of item['priority']
3. Observe it's a string, not an int

**Root Cause**: The bgg-api library returns `item.wishlist_priority` as a string value

**Fix Applied**: Added type conversion in bgg.py:
```python
priority_raw = item.wishlist_priority
priority = int(priority_raw) if priority_raw else None
```

**Status**: Fixed ✓

---

### Bug #2: Year Field Returns 0 Instead of None

**Bug ID**: INT-002  
**Severity**: Medium  
**Component**: BGG API  
**Description**: When a board game doesn't have a published year, the BGG API library returns 0 instead of None, which is semantically incorrect.

**Expected Behavior**: The `year` field should be None for games without a published year

**Actual Behavior**: The `year` field is 0 for games without a published year

**Steps to Reproduce**:
1. Fetch wishlist items that include games without publication years
2. Check the year field value
3. Observe it's 0 instead of None

**Root Cause**: The bgg-api library returns `item.year` as 0 for missing years

**Fix Applied**: Added year normalization in bgg.py:
```python
year_raw = item.year
year = year_raw if year_raw and year_raw > 0 else None
```

**Status**: Fixed ✓

---

### Bug #3: Missing Exception Handler for Invalid Username

**Bug ID**: INT-003  
**Severity**: Medium  
**Component**: BGG API  
**Description**: When an invalid username is provided, the BGG API library raises BGGItemNotFoundError, but this exception was not caught, leading to unhandled exceptions.

**Expected Behavior**: Should raise a RuntimeError with a user-friendly message when username is invalid

**Actual Behavior**: BGGItemNotFoundError propagates uncaught with message "Invalid username specified"

**Steps to Reproduce**:
1. Call fetch_wishlist() with a non-existent username
2. Observe BGGItemNotFoundError exception
3. No user-friendly error message provided

**Stack Trace/Error**:
```
boardgamegeek.exceptions.BGGItemNotFoundError: Invalid username specified
```

**Fix Applied**: Added exception handler in bgg.py:
```python
except BGGItemNotFoundError as e:
    raise RuntimeError(
        f"BoardGameGeek user '{username}' not found or has no collection. "
        f"Please verify the username is correct."
    ) from e
```

**Status**: Fixed ✓

---

## Test Execution Notes

### First Test Run - 2026-02-18

- **Environment**: Python 3.12.3, pytest 9.0.2
- **Configuration Used**: 
  - BGG Username: mageleve
  - BGG Access Token: e62efc9d-932d-46e4-a5c4-32d311aae2df
  - Shop URL: http://www.moenen-en-mariken.nl
- **Notes**: 
  - Initial test run discovered 3 bugs, all related to BGG API integration
  - All bugs were related to type handling and error management
  - Shop scraping tests all passed without issues
  - E2E workflow tests passed successfully
  - All tests now pass after fixes

### Test Results Summary

- **Total Tests**: 16 integration tests
- **BGG API Tests**: 6 tests - All Pass ✓
- **Shop Scraping Tests**: 7 tests - All Pass ✓
- **End-to-End Tests**: 3 tests - All Pass ✓

---

## Summary Statistics

- **Total Bugs Found**: 3
- **Critical**: 0
- **High**: 1 (Priority type mismatch)
- **Medium**: 2 (Year field, Exception handling)
- **Low**: 0
- **Fixed**: 3 ✓
- **Open**: 0

---

## Observations and Recommendations

### BGG API Integration

1. **Type Safety**: The bgg-api library doesn't provide strong type guarantees. Recommend adding validation layer for all external API responses.

2. **Error Handling**: All BGG exceptions should be caught and converted to user-friendly RuntimeError messages with actionable instructions.

3. **Data Validation**: Consider adding a validation step after fetching data to ensure all fields meet expected types and constraints.

### Shop Scraping

1. **Robustness**: The shop scraping implementation is robust and handles various HTML structures well.

2. **Availability Detection**: The stock detection logic correctly identifies multiple stock status markers (uitverkocht, out of stock, niet op voorraad, backorder).

3. **URL Fallback**: The www/non-www fallback mechanism works correctly and provides good resilience.

### End-to-End Workflow

1. **State Management**: The AvailabilityState class correctly tracks product URLs and detects newly available items.

2. **Integration**: The full workflow from BGG wishlist to shop matching works seamlessly.

3. **Performance**: Integration tests complete in reasonable time (~30 seconds for all 16 tests).

---

*Last Updated*: 2026-02-18
