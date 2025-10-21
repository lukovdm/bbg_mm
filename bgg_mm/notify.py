import logging
from typing import Iterable, List, Optional

import requests

from .shop import ShopProduct


class NtfyNotifier:
    """Send notifications to an ntfy topic."""

    def __init__(
        self,
        base_url: str,
        topic: str,
        session: Optional[requests.Session] = None,
        token: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.topic = topic.strip("/")
        self.session = session or requests.Session()
        self.token = token
        self.priority = priority
        self.tags: List[str] = list(tags or [])
        self.timeout = timeout

    def send(self, title: str, body: str) -> None:
        url = f"{self.base_url}/{self.topic}"
        headers = {"Title": title}
        if self.priority:
            headers["Priority"] = self.priority
        if self.tags:
            headers["Tags"] = ",".join(self.tags)
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        logging.info("Sending ntfy notification to %s", url)
        response = self.session.post(url, data=body.encode("utf-8"), headers=headers, timeout=self.timeout)
        response.raise_for_status()


def format_ntfy_message(new_products: Iterable[ShopProduct]) -> str:
    lines = [
        "The following wishlist games are now available at Moenen en Mariken:",
        "",
    ]
    for product in new_products:
        line = f"- {product.name}"
        if product.price:
            line += f" ({product.price})"
        line += f": {product.url}"
        lines.append(line)

    lines.append("")
    lines.append("Happy gaming!")
    return "\n".join(lines)
