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

*This section will be populated after running integration tests.*

### Example Bug Entry (Remove after adding real bugs)

**Bug ID**: EXAMPLE-001  
**Severity**: Medium  
**Component**: Shop Scraping  
**Description**: Price extraction fails for certain product formats  
**Expected Behavior**: Price should be extracted as "€ 45,00"  
**Actual Behavior**: Price is None  
**Steps to Reproduce**:
1. Search for product "Example Game"
2. Check product.price field
3. Observe None value

**Stack Trace/Error**: N/A  
**Status**: Open

---

## Test Execution Notes

*Document any issues encountered during test execution here.*

### First Test Run - [Date will be added]

- **Environment**: Python 3.x, pytest
- **Configuration Used**: 
  - BGG Username: mageleve
  - Shop URL: http://www.moenen-en-mariken.nl
- **Notes**: Initial test run to discover bugs

---

## Summary Statistics

- **Total Bugs Found**: 0 (will be updated)
- **Critical**: 0
- **High**: 0
- **Medium**: 0
- **Low**: 0

---

*Last Updated*: [To be updated after test run]
