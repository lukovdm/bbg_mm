import logging
import time
import xml.etree.ElementTree as ET
from typing import Iterable, List, Optional

import requests

BGG_COLLECTION_ENDPOINT = "https://boardgamegeek.com/xmlapi2/collection"


class BGGWishlistItem(dict):
    """Small typed dict wrapper for wishlist entries."""

    name: str
    object_id: str
    year: Optional[int]
    priority: Optional[int]


class BGGClient:
    """Client for the BGG XML API2."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def fetch_wishlist(
        self,
        username: str,
        priorities: Optional[Iterable[int]] = None,
        timeout: int = 30,
        max_retries: int = 5,
        poll_delay: float = 2.0,
    ) -> List[BGGWishlistItem]:
        """Return wishlist items for `username`, optionally filtering by priority values."""

        params = {
            "username": username,
            "wishlist": 1,
            "wishlistpriority": ",".join(str(p) for p in priorities) if priorities else None,
            "subtype": "boardgame",
            "stats": 0,
        }

        # Remove params with None values so the request remains clean.
        params = {k: v for k, v in params.items() if v is not None}

        for attempt in range(1, max_retries + 1):
            logging.debug("Fetching BGG wishlist attempt %s params=%s", attempt, params)
            response = self.session.get(BGG_COLLECTION_ENDPOINT, params=params, timeout=timeout)
            if response.status_code == 202:
                logging.info("BGG reports data queued (202); sleeping %.1fs", poll_delay)
                time.sleep(poll_delay)
                continue

            response.raise_for_status()
            return self._parse_wishlist(response.text, priorities)

        raise RuntimeError(
            "BoardGameGeek API kept returning 202 (queued). "
            "Try again later or increase retries/delay."
        )

    @staticmethod
    def _parse_wishlist(xml_payload: str, priorities: Optional[Iterable[int]]) -> List[BGGWishlistItem]:
        root = ET.fromstring(xml_payload)
        items: List[BGGWishlistItem] = []
        filter_priorities = set(int(p) for p in priorities) if priorities else None

        for item in root.findall("item"):
            object_id = item.attrib.get("objectid")
            name_elem = item.find("name")
            wishlist_elem = item.find("wishlist")
            priority = None
            if wishlist_elem is not None:
                try:
                    priority = int(wishlist_elem.attrib.get("priority", "0"))
                except ValueError:
                    priority = None

            if filter_priorities and (priority is None or priority not in filter_priorities):
                continue

            name = (
                name_elem.attrib.get("value")
                if name_elem is not None
                else item.attrib.get("name")
                or item.attrib.get("objectname")
                or f"object-{object_id}"
            )

            year_published = None
            year_elem = item.find("yearpublished")
            if year_elem is not None and year_elem.text:
                try:
                    year_published = int(year_elem.text)
                except ValueError:
                    year_published = None

            items.append(
                BGGWishlistItem(
                    {
                        "name": name,
                        "object_id": object_id,
                        "year": year_published,
                        "priority": priority,
                    }
                )
            )

        logging.info("Parsed %s wishlist entries from BGG", len(items))
        return items

