import logging
from typing import Iterable, List, Optional

from boardgamegeek import BGGClient as _BGGClient
from boardgamegeek.api import BGGRestrictCollectionTo

SUBTYPE_MAP = {
    "boardgame": BGGRestrictCollectionTo.BOARD_GAME,
    "boardgameexpansion": BGGRestrictCollectionTo.BOARD_GAME_EXTENSION,
    "boardgameaccessory": BGGRestrictCollectionTo.BOARD_GAME_ACCESSORY,
    "rpgitem": BGGRestrictCollectionTo.RPG,
    "rpgissue": BGGRestrictCollectionTo.RPG_ISSUE,
    "videogame": BGGRestrictCollectionTo.VIDEO_GAME,
}


class BGGWishlistItem(dict):
    """Small typed dict wrapper for wishlist entries."""

    name: str
    object_id: str
    year: Optional[int]
    priority: Optional[int]


class BGGClient:
    """Thin wrapper around the bgg-api BGGClient for fetching wishlists."""

    def __init__(self, access_token: str) -> None:
        self._client = _BGGClient(access_token=access_token)

    def fetch_wishlist(
        self,
        username: str,
        priorities: Optional[Iterable[int]] = None,
        subtypes: Optional[Iterable[Optional[str]]] = None,
    ) -> List[BGGWishlistItem]:
        """Return wishlist items for *username*, filtered by optional priorities and subtypes."""
        priorities_list: Optional[List[int]] = (
            [int(p) for p in priorities] if priorities is not None else None
        )

        subtype_values: List[str]
        if subtypes is None:
            subtype_values = ["boardgame", "boardgameexpansion"]
        else:
            seen: set = set()
            subtype_values = []
            for s in subtypes:
                key = s or "boardgame"
                if key not in seen:
                    seen.add(key)
                    subtype_values.append(key)

        aggregated: List[BGGWishlistItem] = []
        for subtype in subtype_values:
            api_subtype = SUBTYPE_MAP.get(subtype, BGGRestrictCollectionTo.BOARD_GAME)
            if priorities_list:
                # The library only supports filtering by a single wishlist_prio at a time.
                for prio in priorities_list:
                    aggregated.extend(self._fetch_collection(username, api_subtype, prio))
            else:
                aggregated.extend(self._fetch_collection(username, api_subtype, None))

        # Deduplicate by object_id, keep first occurrence.
        by_id: dict[str, BGGWishlistItem] = {}
        for item in aggregated:
            oid = item.get("object_id")
            if oid and oid not in by_id:
                by_id[oid] = item

        logging.info(
            "Fetched %s unique wishlist entries from BGG across %s subtype(s)",
            len(by_id),
            len(subtype_values),
        )
        return list(by_id.values())

    def _fetch_collection(
        self,
        username: str,
        subtype: str,
        wishlist_prio: Optional[int],
    ) -> List[BGGWishlistItem]:
        kwargs: dict = dict(user_name=username, subtype=subtype, wishlist=True)
        if wishlist_prio is not None:
            kwargs["wishlist_prio"] = wishlist_prio

        logging.debug(
            "Fetching BGG collection subtype=%s wishlist_prio=%s", subtype, wishlist_prio
        )
        collection = self._client.collection(**kwargs)

        items: List[BGGWishlistItem] = []
        for game in collection.items:
            items.append(
                BGGWishlistItem(
                    {
                        "name": game.name,
                        "object_id": str(game.id),
                        "year": game.year,
                        "priority": getattr(game, "wishlist_priority", None),
                    }
                )
            )

        logging.debug(
            "Got %s items for subtype=%s wishlist_prio=%s", len(items), subtype, wishlist_prio
        )
        return items
