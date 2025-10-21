import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup


@dataclass
class ShopProduct:
    name: str
    url: str
    available: bool
    price: Optional[str] = None


def _normalise_whitespace(value: str) -> str:
    return " ".join(value.split())


class ShopClient:
    """Scraper for the Moenen en Mariken WooCommerce catalogue."""

    def __init__(self, base_url: str, session: Optional[requests.Session] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

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

    def _search(self, query: str, timeout: int) -> List[dict]:
        params = {"s": query, "post_type": "product"}
        search_url = f"{self.base_url}/?{urlencode(params)}"
        response = self.session.get(search_url, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        products: List[dict] = []
        for node in soup.select(".products li.product, .products article.product"):
            link = node.find("a")
            if not link or not link.get("href"):
                continue

            title_node = node.select_one(".woocommerce-loop-product__title, h2, h3")
            title = title_node.get_text(strip=True) if title_node else link.get("title") or link.get_text(strip=True)
            if not title:
                continue

            price_node = node.select_one(".price .amount, .price .woocommerce-Price-amount")
            price_text = price_node.get_text(strip=True) if price_node else None

            availability = True
            availability_node = node.select_one(".out-of-stock, .stock")
            if availability_node:
                text = availability_node.get_text(strip=True).lower()
                is_out = any(marker in text for marker in ("out of stock", "uitverkocht", "niet op voorraad"))
                availability = not is_out

            products.append(
                {
                    "title": title,
                    "url": link["href"],
                    "price": price_text,
                    "available": availability,
                }
            )

        logging.debug("Found %d candidate products for %s", len(products), query)
        return products

    @staticmethod
    def _pick_best_match(target: str, candidates: List[dict]) -> Optional[dict]:
        def score(title: str) -> float:
            return SequenceMatcher(None, title.lower(), target.lower()).ratio()

        sorted_candidates = sorted(candidates, key=lambda c: score(c["title"]), reverse=True)
        return sorted_candidates[0] if sorted_candidates else None

    def _fetch_detail(self, url: str, timeout: int) -> Optional[ShopProduct]:
        absolute_url = url if url.startswith("http") else urljoin(f"{self.base_url}/", url.lstrip("/"))
        response = self.session.get(absolute_url, timeout=timeout)
        if response.status_code != 200:
            logging.warning("Failed to open %s (%s)", absolute_url, response.status_code)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        title_node = soup.select_one(".product_title, h1.product_title")
        title = title_node.get_text(strip=True) if title_node else None

        price_node = soup.select_one(".summary .price .amount, .summary .price .woocommerce-Price-amount")
        price_text = price_node.get_text(strip=True) if price_node else None

        availability = True
        stock_node = soup.select_one(".summary .stock")
        if stock_node:
            stock_text = _normalise_whitespace(stock_node.get_text()).lower()
            css_classes = stock_node.get("class", [])
            is_out = any(token in css_classes for token in ("out-of-stock",)) or any(
                marker in stock_text for marker in ("out of stock", "uitverkocht", "niet op voorraad")
            )
            availability = not is_out
        else:
            # If no stock element, fall back to checking the CTA button for hints.
            button = soup.select_one("form.cart button[type=submit]")
            if button:
                button_text = button.get_text(strip=True).lower()
                availability = not any(marker in button_text for marker in ("lees meer", "read more"))

        return ShopProduct(
            name=title or url,
            url=absolute_url,
            available=availability,
            price=price_text,
        )

