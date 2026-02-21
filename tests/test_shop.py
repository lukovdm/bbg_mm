"""Tests for bgg_mm.shop — ShopClient scraper."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from bgg_mm.shop import ShopClient, ShopProduct

# Directory containing real HTML fixtures captured from the shop.
FIXTURES = Path(__file__).parent / "fixtures"

BASE_URL = "http://www.moenen-en-mariken.nl"


def _read_fixture(filename: str) -> str:
    return (FIXTURES / filename).read_text(encoding="utf-8")


def _mock_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _make_client(responses: dict | None = None) -> ShopClient:
    """Build a ShopClient whose session returns canned HTML responses.

    *responses* maps URL substrings (or exact URLs) to response text.
    If None, an empty session mock is used.
    """
    session = MagicMock(spec=requests.Session)

    if responses:
        def _request(method, url, **kwargs):
            for key, resp in responses.items():
                if key in url:
                    if isinstance(resp, str):
                        return _mock_response(resp)
                    return resp  # already a response mock
            return _mock_response("", status_code=404)

        session.request.side_effect = _request

    return ShopClient(base_url=BASE_URL, session=session)


# ---------------------------------------------------------------------------
# ShopClient.__init__ / URL normalisation
# ---------------------------------------------------------------------------

class TestShopClientInit:
    def test_strips_trailing_slash(self):
        client = ShopClient(base_url=BASE_URL + "/", session=MagicMock())
        assert not client.base_url.endswith("/")

    def test_force_http_scheme(self):
        client = ShopClient(base_url="https://www.moenen-en-mariken.nl", session=MagicMock())
        assert client.base_url.startswith("http://")

    def test_adds_http_when_scheme_missing(self):
        client = ShopClient(base_url="www.moenen-en-mariken.nl", session=MagicMock())
        assert client.base_url.startswith("http://")

    def test_invalid_base_url_raises(self):
        # An empty string has no hostname after URL parsing — should raise
        with pytest.raises(ValueError):
            ShopClient(base_url="", session=MagicMock())

    def test_www_and_no_www_candidates(self):
        client = ShopClient(base_url=BASE_URL, session=MagicMock())
        # Should have both www and non-www variants
        assert len(client._base_candidates) == 2
        canonical = "http://www.moenen-en-mariken.nl"
        alt = "http://moenen-en-mariken.nl"
        assert canonical in client._base_candidates
        assert alt in client._base_candidates


# ---------------------------------------------------------------------------
# ShopClient._resolve_url
# ---------------------------------------------------------------------------

class TestResolveUrl:
    def setup_method(self):
        self.client = ShopClient(base_url=BASE_URL, session=MagicMock())

    def test_javascript_popup_resolves_to_detail_url(self):
        url = "javascript:popup('850032180863')"
        resolved = self.client._resolve_url(url)
        assert resolved == f"{BASE_URL}/producten/details.php?code=850032180863"

    def test_absolute_http_url_returned_as_is(self):
        url = "http://www.moenen-en-mariken.nl/producten/details.php?code=123"
        assert self.client._resolve_url(url) == url

    def test_absolute_https_url_returned_as_is(self):
        url = "https://example.com/some/page"
        assert self.client._resolve_url(url) == url

    def test_relative_url_joined_with_base(self):
        resolved = self.client._resolve_url("/producten/details.php?code=abc")
        assert resolved == f"{BASE_URL}/producten/details.php?code=abc"

    def test_unsupported_javascript_returns_none(self):
        assert self.client._resolve_url("javascript:void(0)") is None

    def test_empty_string_returns_none(self):
        assert self.client._resolve_url("") is None

    def test_none_like_empty_returns_none(self):
        assert self.client._resolve_url("") is None


# ---------------------------------------------------------------------------
# ShopClient._pick_best_match  (static method)
# ---------------------------------------------------------------------------

class TestPickBestMatch:
    def test_returns_none_for_empty_candidates(self):
        assert ShopClient._pick_best_match("Vantage", []) is None

    def test_returns_single_candidate(self):
        candidates = [{"title": "Vantage (ENG)", "url": "http://example.com/1"}]
        result = ShopClient._pick_best_match("Vantage", candidates)
        assert result is not None
        assert result["title"] == "Vantage (ENG)"

    def test_picks_closest_match(self):
        candidates = [
            {"title": "Vantage (ENG)", "url": "http://example.com/1"},
            {"title": "Completely Different Game", "url": "http://example.com/2"},
            {"title": "Another Title", "url": "http://example.com/3"},
        ]
        result = ShopClient._pick_best_match("Vantage", candidates)
        assert result["title"] == "Vantage (ENG)"

    def test_case_insensitive_scoring(self):
        candidates = [
            {"title": "PANDEMIC", "url": "http://example.com/1"},
            {"title": "Arkham Horror", "url": "http://example.com/2"},
        ]
        result = ShopClient._pick_best_match("pandemic", candidates)
        assert result["title"] == "PANDEMIC"

    def test_returns_none_below_threshold(self):
        """Candidates with no resemblance to the query should be rejected."""
        candidates = [
            {"title": "XYZ Completely Unrelated Product", "url": "http://example.com/1"},
        ]
        result = ShopClient._pick_best_match("ZzZzThisGameDoesNotExist99999", candidates)
        assert result is None

    def test_custom_min_ratio_zero_always_returns(self):
        """With min_ratio=0, even a terrible match is returned."""
        candidates = [
            {"title": "XYZ Unrelated", "url": "http://example.com/1"},
        ]
        result = ShopClient._pick_best_match("ZzZz99999", candidates, min_ratio=0.0)
        assert result is not None


# ---------------------------------------------------------------------------
# ShopClient._shortened_queries — subtitle stripping + punctuation removal
# ---------------------------------------------------------------------------

class TestShortenedQueries:
    def test_bare_title_returns_only_itself(self):
        assert ShopClient._shortened_queries("Vantage") == ["Vantage"]

    def test_strips_colon_subtitle(self):
        queries = ShopClient._shortened_queries("Dead Cells: The Rogue-Lite Board Game")
        assert "Dead Cells: The Rogue-Lite Board Game" == queries[0]
        assert "Dead Cells" in queries

    def test_strips_colon_subtitle_slay_the_spire(self):
        queries = ShopClient._shortened_queries("Slay the Spire: The Board Game")
        assert "Slay the Spire" in queries

    def test_strips_punctuation_for_clank(self):
        # "Clank!: A Deck-Building Adventure" → must include bare "Clank"
        queries = ShopClient._shortened_queries("Clank!: A Deck-Building Adventure")
        assert "Clank" in queries

    def test_full_title_is_first(self):
        queries = ShopClient._shortened_queries("Foo: Bar Baz")
        assert queries[0] == "Foo: Bar Baz"

    def test_no_duplicates(self):
        queries = ShopClient._shortened_queries("Pandemic: The Cure")
        assert len(queries) == len(set(queries))

    def test_strips_dash_subtitle(self):
        queries = ShopClient._shortened_queries("Azul - Queen Gardens")
        assert "Azul" in queries


# ---------------------------------------------------------------------------
# ShopClient._similarity — partial / token-set matching
# ---------------------------------------------------------------------------

class TestSimilarity:
    """Verify that truncated shop titles still score above the 0.4 threshold."""

    def _assert_matches(self, bgg_title: str, shop_title: str) -> None:
        score = ShopClient._similarity(bgg_title, shop_title)
        assert score >= 0.4, (
            f"Expected {bgg_title!r} vs {shop_title!r} to score ≥ 0.4, got {score:.2f}"
        )

    def test_full_match_scores_near_one(self):
        assert ShopClient._similarity("Vantage", "Vantage") == pytest.approx(1.0)

    def test_subtitle_stripped_by_shop(self):
        # "Dead Cells: The Rogue-Lite Board Game" on BGG, "Dead Cells" on shop
        self._assert_matches("Dead Cells: The Rogue-Lite Board Game", "Dead Cells")

    def test_subtitle_stripped_by_shop_clank(self):
        self._assert_matches("Clank!: A Deck-Building Adventure", "Clank!")

    def test_subtitle_stripped_by_shop_slay_the_spire(self):
        self._assert_matches("Slay the Spire: The Board Game", "Slay the Spire")

    def test_edition_suffix_on_shop(self):
        # Shop adds language suffix, BGG has bare name
        self._assert_matches("Vantage", "Vantage (ENG)")

    def test_symmetry(self):
        a, b = "Dead Cells: The Rogue-Lite Board Game", "Dead Cells"
        assert ShopClient._similarity(a, b) == pytest.approx(ShopClient._similarity(b, a))

    def test_unrelated_strings_score_low(self):
        score = ShopClient._similarity("Pandemic", "Zombicide Black Plague")
        assert score < 0.4

    def test_pick_best_match_prefers_truncated_title(self):
        """_pick_best_match should pick the truncated shop name over an unrelated one."""
        candidates = [
            {"title": "Dead Cells", "url": "http://example.com/dc"},
            {"title": "Completely Unrelated Game", "url": "http://example.com/cu"},
        ]
        result = ShopClient._pick_best_match(
            "Dead Cells: The Rogue-Lite Board Game", candidates
        )
        assert result is not None
        assert result["title"] == "Dead Cells"

    def test_pick_best_match_subtitle_game(self):
        candidates = [
            {"title": "Slay the Spire", "url": "http://example.com/sts"},
            {"title": "Pandemic Legacy Season 1", "url": "http://example.com/pl"},
        ]
        result = ShopClient._pick_best_match(
            "Slay the Spire: The Board Game", candidates
        )
        assert result is not None
        assert result["title"] == "Slay the Spire"


# ---------------------------------------------------------------------------
# ShopClient._fetch_detail — using real HTML fixtures
# ---------------------------------------------------------------------------

class TestFetchDetail:
    def _client_with_detail(self, html: str) -> ShopClient:
        return _make_client({"producten/details.php": html})

    def test_parses_product_name_from_artikelname(self):
        html = _read_fixture("detail-http-www-moenen-en-mariken-nl-producten-details-php-code-8718026306731-1761059006.html")
        client = self._client_with_detail(html)
        product = client._fetch_detail(
            f"{BASE_URL}/producten/details.php?code=8718026306731", timeout=5
        )
        assert product is not None
        # Title is parsed from h3.artikelname
        assert "Yokohama" in product.name
        assert product.url == f"{BASE_URL}/producten/details.php?code=8718026306731"

    def test_parses_available_product_from_op_voorraad(self):
        html = _read_fixture("detail-http-www-moenen-en-mariken-nl-producten-details-php-code-8718026306731-1761059006.html")
        client = self._client_with_detail(html)
        product = client._fetch_detail(
            f"{BASE_URL}/producten/details.php?code=8718026306731", timeout=5
        )
        assert product is not None
        # Fixture says "Op voorraad: Ja"
        assert product.available is True

    def test_parses_available_product(self):
        html = _read_fixture("detail-http-www-moenen-en-mariken-nl-producten-details-php-code-5425016929131-1761131513.html")
        client = self._client_with_detail(html)
        product = client._fetch_detail(
            f"{BASE_URL}/producten/details.php?code=5425016929131", timeout=5
        )
        assert product is not None
        # Fixture says "Op voorraad: Ja"
        assert product.available is True
        # Title is parsed from h3.artikelname
        assert product.name and not product.name.startswith("http")

    def test_returns_none_on_404(self):
        session = MagicMock(spec=requests.Session)
        session.request.return_value = _mock_response("", status_code=404)
        client = ShopClient(base_url=BASE_URL, session=session)
        result = client._fetch_detail(
            f"{BASE_URL}/producten/details.php?code=9999", timeout=5
        )
        assert result is None

    def test_resolves_javascript_popup_url_first(self):
        html = _read_fixture("detail-http-www-moenen-en-mariken-nl-producten-details-php-code-5425016929131-1761131513.html")
        client = self._client_with_detail(html)
        product = client._fetch_detail("javascript:popup('5425016929131')", timeout=5)
        assert product is not None
        assert "5425016929131" in product.url


# ---------------------------------------------------------------------------
# ShopClient._extract_candidates_from_soup — catalog HTML fixtures
# ---------------------------------------------------------------------------

class TestExtractCandidates:
    def test_catalog_fixture_returns_candidates(self):
        """The Vantage catalog fixture has one product listing."""
        html = _read_fixture("catalog-vantage-1761059004.html")
        client = _make_client()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        candidates = client._extract_candidates_from_soup(soup, "Vantage", timeout=5, dump_dir=None)
        assert len(candidates) > 0

    def test_catalog_fixture_candidate_has_required_keys(self):
        html = _read_fixture("catalog-vantage-1761059004.html")
        client = _make_client()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        candidates = client._extract_candidates_from_soup(soup, "Vantage", timeout=5, dump_dir=None)
        for c in candidates:
            assert "title" in c
            assert "url" in c

    def test_catalog_fixture_resolves_javascript_popup_url(self):
        html = _read_fixture("catalog-vantage-1761059004.html")
        client = _make_client()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        candidates = client._extract_candidates_from_soup(soup, "Vantage", timeout=5, dump_dir=None)
        for c in candidates:
            # All URLs should be real HTTP URLs, not javascript: URIs
            assert c["url"].startswith("http://") or c["url"].startswith("https://")

    def test_catalog_price_extracted(self):
        html = _read_fixture("catalog-vantage-1761059004.html")
        client = _make_client()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        candidates = client._extract_candidates_from_soup(soup, "Vantage", timeout=5, dump_dir=None)
        prices = [c.get("price") for c in candidates]
        # At least one candidate should have a price
        assert any(p for p in prices)


# ---------------------------------------------------------------------------
# ShopClient._search_product_catalog — end-to-end with mocked HTTP
# ---------------------------------------------------------------------------

class TestSearchProductCatalog:
    def test_catalog_search_returns_products(self):
        html = _read_fixture("catalog-vantage-1761059004.html")
        client = _make_client({"/producten/": html})
        results = client._search_product_catalog("Vantage", timeout=5)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_catalog_search_handles_network_error(self):
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.exceptions.ConnectionError("no network")
        client = ShopClient(base_url=BASE_URL, session=session)
        results = client._search_product_catalog("Vantage", timeout=5)
        assert results == []

    def test_catalog_search_handles_non_200(self):
        session = MagicMock(spec=requests.Session)
        session.request.return_value = _mock_response("", status_code=500)
        client = ShopClient(base_url=BASE_URL, session=session)
        results = client._search_product_catalog("Vantage", timeout=5)
        assert results == []


# ---------------------------------------------------------------------------
# ShopClient.lookup — full pipeline
# ---------------------------------------------------------------------------

class TestLookup:
    def test_lookup_returns_product_when_found(self):
        catalog_html = _read_fixture("catalog-vantage-1761059004.html")
        detail_html = _read_fixture("detail-http-www-moenen-en-mariken-nl-producten-details-php-code-850032180863-1761132422.html")
        client = _make_client({
            "/producten/": catalog_html,
            "details.php": detail_html,
        })
        product = client.lookup("Vantage", timeout=5)
        # Should return a ShopProduct
        assert product is not None
        assert isinstance(product, ShopProduct)

    def test_lookup_returns_none_when_no_results(self):
        session = MagicMock(spec=requests.Session)
        # Both catalog POST and WooCommerce search return empty pages
        empty_html = "<html><body><p>Nothing here</p></body></html>"
        session.request.return_value = _mock_response(empty_html)
        client = ShopClient(base_url=BASE_URL, session=session)
        result = client.lookup("GameThatDoesNotExist12345", timeout=5)
        assert result is None

    def test_lookup_product_has_url(self):
        catalog_html = _read_fixture("catalog-vantage-1761059004.html")
        detail_html = _read_fixture("detail-http-www-moenen-en-mariken-nl-producten-details-php-code-850032180863-1761132422.html")
        client = _make_client({
            "/producten/": catalog_html,
            "details.php": detail_html,
        })
        product = client.lookup("Vantage", timeout=5)
        if product:
            assert product.url.startswith("http")


# ---------------------------------------------------------------------------
# ShopClient._request_with_fallback
# ---------------------------------------------------------------------------

class TestRequestWithFallback:
    def test_returns_first_successful_response(self):
        session = MagicMock(spec=requests.Session)
        session.request.return_value = _mock_response("<html/>")
        client = ShopClient(base_url=BASE_URL, session=session)

        resp = client._request_with_fallback(f"{BASE_URL}/some/path", timeout=5)
        assert resp.status_code == 200

    def test_falls_back_to_second_candidate_on_connection_error(self):
        session = MagicMock(spec=requests.Session)
        call_count = [0]

        def side_effect(method, url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.exceptions.ConnectionError("refused")
            return _mock_response("<html/>")

        session.request.side_effect = side_effect
        client = ShopClient(base_url=BASE_URL, session=session)
        resp = client._request_with_fallback(f"{BASE_URL}/some/path", timeout=5)
        assert resp.status_code == 200
        assert call_count[0] == 2

    def test_raises_after_all_candidates_fail(self):
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.exceptions.ConnectionError("refused")
        client = ShopClient(base_url=BASE_URL, session=session)

        with pytest.raises(requests.exceptions.ConnectionError):
            client._request_with_fallback(f"{BASE_URL}/some/path", timeout=5)
