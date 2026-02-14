"""Manual test script using real data from mageleve user."""
import sys
import json
from pathlib import Path
from unittest.mock import Mock
from bgg_mm.bgg import BGGClient
from bgg_mm.shop import ShopClient
from bgg_mm.cli import fetch_available_products

# Load real XML data from debug files
debug_xml_dir = Path(__file__).parent.parent / "debug_xml"
boardgame_xml = (debug_xml_dir / "bgg-wishlist-mageleve-boardgame-1761056242.xml").read_text()
expansion_xml = (debug_xml_dir / "bgg-wishlist-mageleve-boardgameexpansion-1761056244.xml").read_text()

print("=== Testing BGG Client with real mageleve data ===\n")

# Test parsing the boardgame wishlist
items_bg = BGGClient._parse_wishlist(boardgame_xml, priorities=None)
print(f"Parsed {len(items_bg)} items from boardgame wishlist:")
for item in items_bg:
    print(f"  - {item['name']} (Priority: {item['priority']}, Year: {item['year']})")

print()

# Test parsing the expansion wishlist
items_exp = BGGClient._parse_wishlist(expansion_xml, priorities=None)
print(f"Parsed {len(items_exp)} items from expansion wishlist:")
if items_exp:
    for item in items_exp:
        print(f"  - {item['name']} (Priority: {item['priority']}, Year: {item['year']})")
else:
    print("  (empty)")

print()

# Test priority filtering
print("=== Testing priority filtering ===\n")
items_p2 = BGGClient._parse_wishlist(boardgame_xml, priorities=[2])
print(f"Priority 2 only: {len(items_p2)} items")
for item in items_p2:
    print(f"  - {item['name']} (Priority: {item['priority']})")

print()

items_p23 = BGGClient._parse_wishlist(boardgame_xml, priorities=[2, 3])
print(f"Priority 2-3: {len(items_p23)} items")
for item in items_p23:
    print(f"  - {item['name']} (Priority: {item['priority']})")

print()

# Test with mock fetch_wishlist
print("=== Testing full fetch_wishlist with mock ===\n")

mock_session = Mock()
def mock_get(url, params=None, timeout=None):
    response = Mock()
    response.status_code = 200
    # Return appropriate XML based on subtype parameter
    if params and params.get("subtype") == "boardgame":
        response.text = boardgame_xml
    elif params and params.get("subtype") == "boardgameexpansion":
        response.text = expansion_xml
    else:
        response.text = boardgame_xml
    return response

mock_session.get = mock_get

client = BGGClient(session=mock_session)
wishlist = client.fetch_wishlist(
    username="mageleve",
    priorities=[2, 3],
    subtypes=["boardgame", "boardgameexpansion"]
)

print(f"Total wishlist items (deduplicated): {len(wishlist)}")
for item in wishlist:
    print(f"  - {item['name']} (Priority: {item['priority']})")

print()
print("=== Testing Shop Client URL resolution ===\n")

shop_client = ShopClient(base_url="http://www.moenen-en-mariken.nl")

# Test various URL formats
test_urls = [
    "javascript:popup('5425016929131')",
    "/producten/details.php?code=123",
    "http://www.moenen-en-mariken.nl/producten/details.php?code=456",
]

for url in test_urls:
    resolved = shop_client._resolve_url(url)
    print(f"  {url}")
    print(f"  -> {resolved}")
    print()

print("=== All manual tests completed successfully! ===")
