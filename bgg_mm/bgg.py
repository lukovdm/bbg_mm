import logging
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Optional, Union

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
        subtypes: Optional[Iterable[Optional[str]]] = None,
        debug_dump_dir: Optional[Union[str, Path]] = None,
        timeout: int = 30,
        max_retries: int = 5,
        poll_delay: float = 2.0,
    ) -> List[BGGWishlistItem]:
        """Return wishlist items for `username`, optionally filtering by priority values and subtype."""
        priorities_list = list(priorities) if priorities is not None else None
        if priorities_list:
            priorities_list = [int(p) for p in priorities_list]

        subtype_values: List[Optional[str]]
        if subtypes is None:
            subtype_values = [None]
        else:
            subtype_values = []
            seen = set()
            for subtype in subtypes:
                key = subtype or ""
                if key in seen:
                    continue
                seen.add(key)
                subtype_values.append(subtype or None)

        dump_path: Optional[Path] = None
        if debug_dump_dir is not None:
            dump_path = Path(debug_dump_dir)
            dump_path.mkdir(parents=True, exist_ok=True)

        aggregated: List[BGGWishlistItem] = []
        for subtype in subtype_values:
            aggregated.extend(
                self._fetch_wishlist_single(
                    username=username,
                    priorities_list=priorities_list,
                    subtype=subtype,
                    debug_dump_dir=dump_path,
                    timeout=timeout,
                    max_retries=max_retries,
                    poll_delay=poll_delay,
                )
            )

        # Deduplicate by object_id, keep first occurrence.
        by_object: dict[str, BGGWishlistItem] = {}
        for item in aggregated:
            object_id = item.get("object_id")
            if object_id and object_id not in by_object:
                by_object[object_id] = item

        logging.info("Parsed %s wishlist entries from BGG across %s subtype requests", len(by_object), len(subtype_values))
        return list(by_object.values())

    def _fetch_wishlist_single(
        self,
        username: str,
        priorities_list: Optional[List[int]],
        subtype: Optional[str],
        *,
        debug_dump_dir: Optional[Path],
        timeout: int,
        max_retries: int,
        poll_delay: float,
    ) -> List[BGGWishlistItem]:
        if priorities_list and len(priorities_list) == 1:
            priority_param = str(priorities_list[0])
        else:
            priority_param = None

        params = {
            "username": username,
            "wishlist": 1,
            "stats": 0,
            "subtype": subtype,
        }
        if priority_param is not None:
            params["wishlistpriority"] = priority_param

        params = {k: v for k, v in params.items() if v is not None}

        for attempt in range(1, max_retries + 1):
            logging.debug("Fetching BGG wishlist attempt %s params=%s", attempt, params)
            response = self.session.get(BGG_COLLECTION_ENDPOINT, params=params, timeout=timeout)
            if response.status_code == 202:
                logging.info("BGG reports data queued (202); sleeping %.1fs", poll_delay)
                time.sleep(poll_delay)
                continue

            response.raise_for_status()
            payload = response.text
            if debug_dump_dir:
                self._dump_debug_payload(debug_dump_dir, username, subtype, payload)
            return self._parse_wishlist(payload, priorities_list)

        raise RuntimeError(
            "BoardGameGeek API kept returning 202 (queued). "
            "Try again later or increase retries/delay."
        )

    @staticmethod
    def _dump_debug_payload(target_dir: Path, username: str, subtype: Optional[str], payload: str) -> None:
        timestamp = int(time.time())
        subtype_label = subtype or "all"
        filename = f"bgg-wishlist-{username}-{subtype_label}-{timestamp}.xml"
        path = target_dir / filename
        path.write_text(payload, encoding="utf-8")
        logging.debug("Wrote debug payload to %s", path)

    @staticmethod
    def _parse_wishlist(xml_payload: str, priorities: Optional[Iterable[int]]) -> List[BGGWishlistItem]:
        root = ET.fromstring(xml_payload)
        items: List[BGGWishlistItem] = []
        filter_priorities = set(int(p) for p in priorities) if priorities else None

        for item in root.findall("item"):
            object_id = item.attrib.get("objectid")
            name_elem = item.find("name")
            status_elem = item.find("status")

            if status_elem is None:
                logging.debug("Skipping item %s because no status element found", object_id)
                continue

            wishlist_flag = status_elem.attrib.get("wishlist", "0")
            if wishlist_flag not in {"1", "true", "True"}:
                logging.debug("Skipping item %s because wishlist flag is %s", object_id, wishlist_flag)
                continue

            priority = None
            raw_priority = status_elem.attrib.get("wishlistpriority")
            if raw_priority:
                try:
                    priority = int(raw_priority)
                except ValueError:
                    logging.debug("Could not parse wishlist priority '%s' for item %s", raw_priority, object_id)
                    priority = None

            if filter_priorities and (priority is None or priority not in filter_priorities):
                continue

            name = (
                (
                    name_elem.attrib.get("value")
                    if name_elem is not None and "value" in name_elem.attrib
                    else (name_elem.text.strip() if name_elem is not None and name_elem.text else None)
                )
                or item.attrib.get("name")
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
