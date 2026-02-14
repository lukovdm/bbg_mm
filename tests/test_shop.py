"""Tests for shop client functionality."""
import pytest
from unittest.mock import Mock, MagicMock
from bgg_mm.shop import ShopClient, ShopProduct


# Sample HTML from catalog search
SAMPLE_CATALOG_HTML = """
<html>
<body>
<li class="artikelname">
    <a href="javascript:popup('5425016929131')">Vantage</a>
    <div class="prodPrice">€ 45,00</div>
    <div class="prodStock">Op voorraad</div>
</li>
<li class="artikelname">
    <a href="javascript:popup('5425016928882')">Another Game</a>
    <div class="prodPrice">€ 30,00</div>
    <div class="prodStock">Uitverkocht</div>
</li>
</body>
</html>
"""

# Sample HTML for product detail page
SAMPLE_DETAIL_HTML_AVAILABLE = """
<html>
<body>
<h1 class="product_title">Vantage</h1>
<div class="summary">
    <div class="price">
        <span class="woocommerce-Price-amount amount">€ 45,00</span>
    </div>
    <div class="stock in-stock">Op voorraad</div>
</div>
</body>
</html>
"""

SAMPLE_DETAIL_HTML_OUT_OF_STOCK = """
<html>
<body>
<h1 class="product_title">Out of Stock Game</h1>
<div class="summary">
    <div class="price">
        <span class="woocommerce-Price-amount amount">€ 50,00</span>
    </div>
    <div class="stock out-of-stock">Uitverkocht</div>
</div>
</body>
</html>
"""


class TestShopClient:
    """Test shop client functionality."""

    def test_resolve_popup_url(self):
        """Test resolving javascript popup URLs."""
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        
        url = "javascript:popup('5425016929131')"
        resolved = client._resolve_url(url)
        
        assert resolved == "http://www.moenen-en-mariken.nl/producten/details.php?code=5425016929131"

    def test_resolve_relative_url(self):
        """Test resolving relative URLs."""
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        
        url = "/producten/details.php?code=123"
        resolved = client._resolve_url(url)
        
        assert resolved == "http://www.moenen-en-mariken.nl/producten/details.php?code=123"

    def test_resolve_absolute_url(self):
        """Test resolving absolute URLs."""
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        
        url = "http://www.moenen-en-mariken.nl/producten/details.php?code=123"
        resolved = client._resolve_url(url)
        
        assert resolved == url

    def test_parse_catalog_results(self):
        """Test parsing catalog search results."""
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_CATALOG_HTML, "html.parser")
        
        candidates = client._extract_candidates_from_soup(
            soup, "Vantage", timeout=30, dump_dir=None, max_detail_fetch=0
        )
        
        assert len(candidates) >= 1
        # Should find Vantage
        vantage = next((c for c in candidates if "Vantage" in c["title"]), None)
        assert vantage is not None
        assert "details.php?code=5425016929131" in vantage["url"]

    def test_fetch_detail_page_available(self, mocker):
        """Test fetching detail page for available product."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_DETAIL_HTML_AVAILABLE
        mock_session.request.return_value = mock_response
        
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl", session=mock_session)
        
        product = client._fetch_detail(
            url="producten/details.php?code=123",
            timeout=30
        )
        
        assert product is not None
        assert product.name == "Vantage"
        assert product.available is True
        assert "€ 45,00" in product.price

    def test_fetch_detail_page_out_of_stock(self, mocker):
        """Test fetching detail page for out of stock product."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_DETAIL_HTML_OUT_OF_STOCK
        mock_session.request.return_value = mock_response
        
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl", session=mock_session)
        
        product = client._fetch_detail(
            url="producten/details.php?code=456",
            timeout=30
        )
        
        assert product is not None
        assert product.name == "Out of Stock Game"
        assert product.available is False
        assert "€ 50,00" in product.price

    def test_pick_best_match(self):
        """Test picking the best matching product from candidates."""
        candidates = [
            {"title": "Some Other Game", "url": "http://example.com/1"},
            {"title": "Vantage", "url": "http://example.com/2"},
            {"title": "Vantage Special Edition", "url": "http://example.com/3"},
        ]
        
        best = ShopClient._pick_best_match("Vantage", candidates)
        
        assert best["title"] == "Vantage"  # Exact match should win

    def test_lookup_not_found(self, mocker):
        """Test lookup when product is not found."""
        mock_session = Mock()
        
        # Empty search results
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body></body></html>"
        mock_session.request.return_value = mock_response
        
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl", session=mock_session)
        
        product = client.lookup("NonExistentGame")
        
        assert product is None

    def test_base_url_normalization(self):
        """Test that base URLs are normalized correctly."""
        # Test with and without www
        client1 = ShopClient(base_url="http://moenen-en-mariken.nl")
        assert "moenen-en-mariken.nl" in client1.base_url
        
        client2 = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        assert "moenen-en-mariken.nl" in client2.base_url

    def test_base_url_forces_http(self):
        """Test that HTTPS is converted to HTTP."""
        client = ShopClient(base_url="https://www.moenen-en-mariken.nl")
        
        # Should be forced to HTTP
        assert client.base_url.startswith("http://")

    def test_extract_price_from_catalog(self):
        """Test extracting price information from catalog."""
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_CATALOG_HTML, "html.parser")
        
        candidates = client._extract_candidates_from_soup(
            soup, "Vantage", timeout=30, dump_dir=None, max_detail_fetch=0
        )
        
        vantage = next((c for c in candidates if "Vantage" in c["title"]), None)
        assert vantage is not None
        # Price might be available in the candidate
        if vantage.get("price"):
            assert "45" in vantage["price"]

    def test_extract_availability_from_catalog(self):
        """Test extracting availability information from catalog."""
        client = ShopClient(base_url="http://www.moenen-en-mariken.nl")
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_CATALOG_HTML, "html.parser")
        
        candidates = client._extract_candidates_from_soup(
            soup, "", timeout=30, dump_dir=None, max_detail_fetch=0
        )
        
        # Find the out of stock game
        out_of_stock = next((c for c in candidates if c.get("available") is False), None)
        assert out_of_stock is not None

    def test_stock_detection_keywords(self, mocker):
        """Test that various out-of-stock keywords are detected."""
        test_cases = [
            ("uitverkocht", False),
            ("niet op voorraad", False),
            ("out of stock", False),
            ("backorder", False),
            ("Op voorraad", True),
            ("In stock", True),
        ]
        
        for stock_text, expected_available in test_cases:
            html = f"""
            <html>
            <body>
            <h1 class="product_title">Test Game</h1>
            <div class="summary">
                <div class="stock">{stock_text}</div>
            </div>
            </body>
            </html>
            """
            
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = html
            mock_session.request.return_value = mock_response
            
            client = ShopClient(base_url="http://www.moenen-en-mariken.nl", session=mock_session)
            product = client._fetch_detail(url="test", timeout=30)
            
            assert product.available == expected_available, f"Failed for stock text: {stock_text}"
