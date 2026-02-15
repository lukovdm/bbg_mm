import argparse
import logging
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

import requests
from requests import Response
from requests.exceptions import RequestException
from bs4 import BeautifulSoup


@dataclass
class ShopProduct:
    name: str
    url: str
    available: bool
    price: Optional[str] = None


def _normalise_whitespace(value: str) -> str:
    return " ".join(value.split())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    slug = slug.strip("-")
    return slug or "data"


def _dump_response(content: str, dump_dir: Optional[Path], label: str) -> None:
    if not dump_dir:
        return
    dump_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(label)
    path = dump_dir / f"{slug}-{int(time.time())}.html"
    path.write_text(content, encoding="utf-8")
    logging.info("Dumped %s to %s", label, path)


class ShopClient:
    """Scraper for the Moenen en Mariken WooCommerce catalogue."""

    def __init__(
        self, base_url: str, session: Optional[requests.Session] = None
    ) -> None:
        base_url = base_url.rstrip("/")
        if "://" not in base_url:
            base_url = f"http://{base_url}"

        parsed = urlparse(base_url)
        if not parsed.netloc:
            raise ValueError(f"shop.base_url must include a hostname, got {base_url!r}")

        # Force HTTP scheme because the shop does not provide a valid HTTPS certificate.
        parsed = parsed._replace(scheme="http")

        def normalise(url: str) -> str:
            return url.rstrip("/")

        canonical = normalise(urlunparse(parsed))

        candidates = [canonical]
        if parsed.netloc.startswith("www."):
            alt = parsed._replace(netloc=parsed.netloc[4:])
            candidates.append(normalise(urlunparse(alt)))
        else:
            www_url = parsed._replace(netloc=f"www.{parsed.netloc}")
            candidates.append(normalise(urlunparse(www_url)))

        # Remove duplicates while preserving order.
        seen = set()
        deduped = []
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            deduped.append(candidate)

        self._base_candidates = deduped
        self.base_url = deduped[0]
        self.session = session or requests.Session()
        self._popup_regex = re.compile(r"javascript:popup\('([^']+)'\)")

    def _request_with_fallback(
        self,
        url: str,
        *,
        timeout: int,
        method: str = "GET",
        data: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Response:
        suffix: Optional[str] = None
        if url.startswith(self.base_url):
            suffix = url[len(self.base_url) :]

        last_exc: Optional[RequestException] = None
        for candidate_base in self._base_candidates:
            candidate_url = candidate_base + suffix if suffix is not None else url
            try:
                response = self.session.request(
                    method=method,
                    url=candidate_url,
                    timeout=timeout,
                    data=data,
                    headers=headers,
                )
                self.base_url = candidate_base
                return response
            except RequestException as exc:
                last_exc = exc
                logging.warning(
                    "Request to %s failed (%s). Trying next fallback.",
                    candidate_base,
                    exc,
                )
                continue

        if last_exc:
            raise last_exc
        return self.session.request(
            method=method, url=url, timeout=timeout, data=data, headers=headers
        )

    def _resolve_url(self, url: str) -> Optional[str]:
        if not url:
            return None

        logging.debug(f"resolving url {url}")

        match = self._popup_regex.match(url)
        if match:
            code = match.group(1)
            resolved = urljoin(
                f"{self.base_url}/", f"producten/details.php?code={code}"
            )
            logging.debug("Resolved javascript popup url %s to %s", url, resolved)
            return resolved

        if url.startswith("http://") or url.startswith("https://"):
            return url

        if url.startswith("javascript:"):
            logging.debug("Skipping unsupported javascript url %s", url)
            return None

        return urljoin(f"{self.base_url}/", url.lstrip("/"))

    def _build_candidate_from_anchor(self, anchor) -> Optional[dict]:
        if not anchor or not anchor.get("href"):
            return None

        href = anchor.get("href")
        logging.debug("resolving url %s", href)
        resolved_url = self._resolve_url(href)
        if not resolved_url:
            return None

        title = anchor.get_text(strip=True)
        if not title:
            parent = anchor.find_parent()
            if parent:
                title_node = parent.select_one(
                    ".prodTitle, .artikelname, .woocommerce-loop-product__title"
                )
                if title_node:
                    title = title_node.get_text(strip=True)
        if not title:
            return None

        container = (
            anchor.find_parent(class_="prodBox")
            or anchor.find_parent("article")
            or anchor.find_parent("li")
            or anchor.parent
        )
        if container and not hasattr(container, "select_one"):
            container = None

        price_text = None
        availability: Optional[bool] = None

        if container:
            price_node = container.select_one(
                ".prodPrijs, .prodPrice, .price .amount, .woocommerce-Price-amount, .price"
            )
            if price_node:
                price_text = _normalise_whitespace(price_node.get_text())

            stock_node = container.select_one(".prodStock, .stock, .availability")
            if stock_node:
                stock_text = _normalise_whitespace(stock_node.get_text()).lower()
                is_out = any(
                    marker in stock_text
                    for marker in (
                        "uitverkocht",
                        "niet op voorraad",
                        "out of stock",
                        "backorder",
                    )
                )
                availability = not is_out

        return {
            "title": title,
            "url": resolved_url,
            "price": price_text,
            "available": availability,
        }

    def _extract_candidates_from_soup(
        self,
        soup: BeautifulSoup,
        query: str,
        timeout: int,
        dump_dir: Optional[Path],
        max_detail_fetch: int = 5,
    ) -> List[dict]:
        anchors = soup.select(
            "li.artikelname a[href], .prodTitle a[href], article.product a[href], .prodBox a[href], a[href^='javascript:popup(']"
        )
        candidates: List[dict] = []
        seen_urls: set[str] = set()
        query_tokens = [
            token for token in re.split(r"\s+", query.lower()) if token and token != "+"
        ]
        matched: List[dict] = []
        others: List[dict] = []

        for anchor in anchors:
            candidate = self._build_candidate_from_anchor(anchor)
            if not candidate:
                continue

            url = candidate["url"]
            if url in seen_urls:
                continue

            seen_urls.add(url)
            candidates.append(candidate)
            title_lower = candidate["title"].lower()
            if query_tokens and all(token in title_lower for token in query_tokens):
                matched.append(candidate)
            elif query_tokens and any(token in title_lower for token in query_tokens):
                matched.append(candidate)
            else:
                others.append(candidate)

        if matched:
            logging.debug(
                "Found %d candidates with title matching query '%s'", len(matched), query
            )
            return matched

        # Attempt to enrich a limited number of candidates by fetching detail pages to obtain titles.
        enrich_count = 0
        for candidate in candidates:
            if (
                enrich_count >= max_detail_fetch
                or candidate["title"]
                and not candidate["title"].startswith("http")
            ):
                continue

            detail = self._fetch_detail(
                candidate["url"], timeout=timeout, dump_dir=dump_dir
            )
            enrich_count += 1
            if detail:
                candidate["title"] = detail.name
                if candidate.get("price") is None:
                    candidate["price"] = detail.price
                candidate["available"] = detail.available

        if query_tokens:
            enriched_matches = [
                candidate
                for candidate in candidates
                if candidate["title"]
                and any(token in candidate["title"].lower() for token in query_tokens)
            ]
            if enriched_matches:
                logging.debug(
                    "After enrichment found %d candidates matching '%s'",
                    len(enriched_matches),
                    query,
                )
                return enriched_matches

        logging.debug(
            "No title matches for '%s'; returning %d fallback candidates",
            query,
            len(candidates),
        )
        return candidates

    def lookup(self, game_name: str, timeout: int = 30) -> Optional[ShopProduct]:
        """Return product information for `game_name`, or None if not found."""

        logging.debug("Searching shop for %s", game_name)
        search_results = self._search(game_name, timeout=timeout)
        if not search_results:
            logging.info("No search hits for %s", game_name)
            return None

        best = self._pick_best_match(game_name, search_results)
        if best is None:
            return None

        detail = self._fetch_detail(best["url"], timeout=timeout)
        return detail or ShopProduct(
            name=best["title"],
            url=best["url"],
            available=best.get("available", False),
            price=best.get("price"),
        )

    def _search(
        self, query: str, timeout: int, dump_dir: Optional[Path] = None
    ) -> List[dict]:
        productos = self._search_product_catalog(
            query, timeout=timeout, dump_dir=dump_dir
        )
        if productos:
            return productos

        params = {"s": query, "post_type": "product"}
        search_url = f"{self.base_url}/?{urlencode(params)}"
        response = self._request_with_fallback(search_url, timeout=timeout)
        response.raise_for_status()
        _dump_response(response.text, dump_dir, f"search-{query}")

        soup = BeautifulSoup(response.text, "html.parser")

        products = self._extract_candidates_from_soup(
            soup, query, timeout=timeout, dump_dir=dump_dir
        )
        if products:
            logging.debug("Found %d candidate products for %s", len(products), query)
            return products

        # If search results were empty, try following the first product link if the shop redirected to a single item page.
        first_link = soup.select_one(
            ".product a, .woocommerce-product-gallery__image a, a.woocommerce-LoopProduct-link"
        )
        href = first_link.get("href") if first_link else None
        resolved = self._resolve_url(href) if href else None
        if resolved:
            logging.debug(
                "No listing nodes for %s, fetching detail page %s", query, resolved
            )
            detail = self._fetch_detail(resolved, timeout=timeout, dump_dir=dump_dir)
            if detail:
                return [
                    {
                        "title": detail.name,
                        "url": detail.url,
                        "price": detail.price,
                        "available": detail.available,
                    }
                ]
        else:
            logging.debug("No usable product link found for %s (href=%s)", query, href)
        logging.info("No search hits for %s", query)
        return []

    def _search_product_catalog(
        self, query: str, timeout: int, dump_dir: Optional[Path] = None
    ) -> List[dict]:
        catalog_url = urljoin(f"{self.base_url}/", "producten/")
        form_data = {
            "f[artnaam]": query,
            "f[categorie]": "",
            "f[spMin_min]": "",
            "f[spMax_max]": "",
            "f[lMin_min]": "",
            "f[lMax_max]": "",
            "f[sdMin_min]": "",
            "f[sdMax_max]": "",
            "f[stype]": "",
            "f[ontwerper]": "",
            "f[producent]": "",
            "f[prijs_min]": "",
            "f[prijs_max]": "",
        }
        try:
            response = self._request_with_fallback(
                catalog_url, timeout=timeout, method="POST", data=form_data
            )
        except RequestException as exc:
            logging.debug("Catalog POST search failed for %s (%s)", query, exc)
            return []

        if response.status_code != 200:
            logging.debug(
                "Catalog POST search returned status %s for %s",
                response.status_code,
                query,
            )
            return []

        _dump_response(response.text, dump_dir, f"catalog-{query}")

        soup = BeautifulSoup(response.text, "html.parser")
        products = self._extract_candidates_from_soup(
            soup, query, timeout=timeout, dump_dir=dump_dir
        )
        logging.debug(
            "Catalog search extracted %d candidates for %s", len(products), query
        )
        return products

    @staticmethod
    def _pick_best_match(target: str, candidates: List[dict]) -> Optional[dict]:
        def score(title: str) -> float:
            return SequenceMatcher(None, title.lower(), target.lower()).ratio()

        sorted_candidates = sorted(
            candidates, key=lambda c: score(c["title"]), reverse=True
        )
        return sorted_candidates[0] if sorted_candidates else None

    def _fetch_detail(
        self, url: str, timeout: int, dump_dir: Optional[Path] = None
    ) -> Optional[ShopProduct]:
        absolute_url = self._resolve_url(url)
        if not absolute_url:
            logging.debug("Could not resolve detail url %s", url)
            return None
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.base_url}/producten/",
        }
        response = self._request_with_fallback(
            absolute_url, timeout=timeout, headers=headers
        )
        if response.status_code != 200:
            logging.warning(
                "Failed to open %s (%s)", absolute_url, response.status_code
            )
            return None

        _dump_response(response.text, dump_dir, f"detail-{absolute_url}")

        soup = BeautifulSoup(response.text, "html.parser")
        title_node = soup.select_one(".product_title, h1.product_title")
        title = title_node.get_text(strip=True) if title_node else None

        price_node = soup.select_one(
            ".summary .price .amount, .summary .price .woocommerce-Price-amount"
        )
        price_text = price_node.get_text(strip=True) if price_node else None

        availability = True
        stock_node = soup.select_one(".summary .stock")
        if stock_node:
            stock_text = _normalise_whitespace(stock_node.get_text()).lower()
            css_classes = stock_node.get("class", [])
            is_out = any(token in css_classes for token in ("out-of-stock",)) or any(
                marker in stock_text
                for marker in ("out of stock", "uitverkocht", "niet op voorraad", "backorder")
            )
            availability = not is_out
        else:
            # If no stock element, fall back to checking the CTA button for hints.
            button = soup.select_one("form.cart button[type=submit]")
            if button:
                button_text = button.get_text(strip=True).lower()
                availability = not any(
                    marker in button_text for marker in ("lees meer", "read more")
                )

        return ShopProduct(
            name=title or url,
            url=absolute_url,
            available=availability,
            price=price_text,
        )

    def search_catalog(
        self, query: str, timeout: int = 30, dump_dir: Optional[Path] = None
    ) -> List[dict]:
        """Expose the catalog POST search for debugging."""
        return self._search_product_catalog(query, timeout=timeout, dump_dir=dump_dir)

    def search_candidates(
        self, query: str, timeout: int = 30, dump_dir: Optional[Path] = None
    ) -> List[dict]:
        """Expose the combined search logic (catalog + fallback WooCommerce page)."""
        return self._search(query, timeout=timeout, dump_dir=dump_dir)

    def fetch_detail_by_code(
        self, code: str, timeout: int = 30, dump_dir: Optional[Path] = None
    ) -> Optional[ShopProduct]:
        """Fetch a product detail page directly via its numeric code."""
        return self._fetch_detail(
            f"producten/details.php?code={code}", timeout=timeout, dump_dir=dump_dir
        )


def _format_candidate(candidate: dict) -> str:
    parts = [candidate.get("title", "<unknown>"), candidate.get("url", "")]
    availability = candidate.get("available")
    if availability is not None:
        parts.append(f"available={availability}")
    price = candidate.get("price")
    if price:
        parts.append(f"price={price}")
    return " | ".join(str(part) for part in parts if part)


def _format_product(product: ShopProduct) -> str:
    status = "AVAILABLE" if product.available else "UNAVAILABLE"
    text = f"{status}: {product.name} - {product.url}"
    if product.price:
        text += f" ({product.price})"
    return text


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug Moenen en Mariken shop scraping."
    )
    parser.add_argument(
        "--base-url", default="http://www.moenen-en-mariken.nl", help="Shop base URL."
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Search term to inspect (repeatable). Defaults to 'Vantage' if omitted.",
    )
    parser.add_argument(
        "--detail-code",
        action="append",
        dest="detail_codes",
        help="Product code for details.php (repeatable).",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="HTTP timeout in seconds."
    )
    parser.add_argument(
        "--dump-dir",
        type=Path,
        help="Directory where raw HTML responses should be stored.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    return parser.parse_args()


def _run_cli() -> None:
    args = _parse_cli_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    dump_dir = args.dump_dir
    client = ShopClient(base_url=args.base_url)

    queries: List[str] = args.queries or ["Vantage"]
    for query in queries:
        logging.info("=== Query: %s ===", query)
        catalog = client.search_catalog(query, timeout=args.timeout, dump_dir=dump_dir)
        if catalog:
            logging.info("Catalog returned %d entries", len(catalog))
            for idx, candidate in enumerate(catalog):
                logging.info("Catalog[%d] %s", idx, _format_candidate(candidate))
        else:
            logging.info("Catalog search produced no entries for %s", query)

        candidates = client.search_candidates(
            query, timeout=args.timeout, dump_dir=dump_dir
        )
        if candidates:
            logging.info("Combined search yielded %d candidates", len(candidates))
            for idx, candidate in enumerate(candidates):
                logging.info("Candidate[%d] %s", idx, _format_candidate(candidate))
            best = ShopClient._pick_best_match(query, candidates)
            if best:
                logging.info("Best candidate: %s -> %s", best["title"], best["url"])
                detail = client._fetch_detail(
                    best["url"], timeout=args.timeout, dump_dir=dump_dir
                )
                if detail:
                    logging.info("Detail: %s", _format_product(detail))
                else:
                    logging.info("Detail fetch failed for %s", best["url"])
        else:
            logging.info("No candidates found for %s", query)

    for code in args.detail_codes or []:
        logging.info("--- Detail by code: %s ---", code)
        product = client.fetch_detail_by_code(
            code, timeout=args.timeout, dump_dir=dump_dir
        )
        if product:
            logging.info("%s", _format_product(product))
        else:
            logging.info("Could not fetch detail for code %s", code)


if __name__ == "__main__":
    _run_cli()
