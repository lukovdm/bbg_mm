import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

from .bgg import BGGClient, BGGWishlistItem
from .notify import NtfyNotifier, format_ntfy_message
from .shop import ShopClient, ShopProduct
from .state import AvailabilityState


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check BGG wishlist against Moenen en Mariken availability.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON (default: config.json)")
    parser.add_argument("--dry-run", action="store_true", help="Do not send notifications, only print output.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def load_config(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file {path} not found. Copy config.example.json to {path} and edit it.")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_notifier(ntfy_cfg: Optional[Dict], session: requests.Session) -> Optional[NtfyNotifier]:
    if not ntfy_cfg:
        return None

    missing = [key for key in ("topic",) if key not in ntfy_cfg]
    if missing:
        raise ValueError(f"ntfy configuration missing keys: {', '.join(missing)}")

    base_url = ntfy_cfg.get("base_url", "https://ntfy.sh")
    return NtfyNotifier(
        base_url=base_url,
        topic=ntfy_cfg["topic"],
        session=session,
        token=ntfy_cfg.get("token"),
        priority=ntfy_cfg.get("priority"),
        tags=ntfy_cfg.get("tags"),
        timeout=int(ntfy_cfg.get("timeout", 30)),
    )


def fetch_available_products(
    bgg_client: BGGClient,
    shop_client: ShopClient,
    username: str,
    priorities: Optional[Iterable[int]],
) -> List[ShopProduct]:
    wishlist: List[BGGWishlistItem] = bgg_client.fetch_wishlist(username=username, priorities=priorities)
    logging.info("Checking availability for %s games", len(wishlist))
    available: List[ShopProduct] = []
    for entry in wishlist:
        product = shop_client.lookup(entry["name"])
        if product is None:
            logging.debug("No shop match for %s", entry["name"])
            continue
        if product.available:
            logging.info("Available: %s -> %s", entry["name"], product.url)
            available.append(product)
        else:
            logging.debug("Found but not available: %s", entry["name"])
    return available


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config_path = Path(args.config)
    config = load_config(config_path)

    bgg_cfg = config.get("bgg", {})
    if "username" not in bgg_cfg:
        raise ValueError("bgg.username is required in the configuration.")

    priorities = bgg_cfg.get("wishlist_priorities")
    if priorities is not None:
        priorities = [int(p) for p in priorities]

    shop_cfg = config.get("shop", {})
    base_url = shop_cfg.get("base_url")
    if not base_url:
        raise ValueError("shop.base_url is required in the configuration.")

    state_file = Path(config.get("state_file", "data/availability.json"))
    state = AvailabilityState(state_file)
    state.load()

    session = requests.Session()
    session.headers.update({"User-Agent": "BGG-MM Availability Checker/1.0"})

    bgg_client = BGGClient(session=session)
    shop_client = ShopClient(base_url=base_url, session=session)

    available_products = fetch_available_products(
        bgg_client=bgg_client,
        shop_client=shop_client,
        username=bgg_cfg["username"],
        priorities=priorities,
    )

    known_urls = state.known_urls
    newly_available = [product for product in available_products if product.url not in known_urls]

    notifier = build_notifier(config.get("ntfy"), session=session)
    if newly_available and notifier:
        logging.info("Detected %s newly available games.", len(newly_available))
        if args.dry_run:
            logging.info("Dry run enabled; skipping ntfy send.")
        else:
            body = format_ntfy_message(newly_available)
            notifier.send(
                title="BGG Wishlist availability update",
                body=body,
            )
    elif newly_available:
        logging.info("Detected newly available games but no ntfy configuration provided.")
    else:
        logging.info("No newly available games detected.")

    state.update(product.url for product in available_products if product.available)

    for product in available_products:
        line = f"{'AVAILABLE' if product.available else 'UNAVAILABLE'}: {product.name} - {product.url}"
        if product.price:
            line += f" ({product.price})"
        print(line)


if __name__ == "__main__":
    main()
