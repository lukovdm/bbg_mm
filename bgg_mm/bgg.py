"""BGG client using the bgg-api Python library."""
import logging
from typing import Iterable, List, Optional

from boardgamegeek import BGGClient as BGGAPIClient
from boardgamegeek.exceptions import (
    BGGApiError,
    BGGApiRetryError,
    BGGApiUnauthorizedError,
    BGGValueError,
)


class BGGWishlistItem(dict):
    """Small typed dict wrapper for wishlist entries."""

    name: str
    object_id: str
    year: Optional[int]
    priority: Optional[int]


class BGGClient:
    """Client for the BGG API using the bgg-api library."""

    def __init__(self, access_token: Optional[str] = None) -> None:
        """Initialize BGG client.
        
        Args:
            access_token: BGG API access token (required for authentication)
        """
        self.access_token = access_token or ""
        self.client = BGGAPIClient(self.access_token)

    def fetch_wishlist(
        self,
        username: str,
        priorities: Optional[Iterable[int]] = None,
        subtypes: Optional[Iterable[Optional[str]]] = None,
        debug_dump_dir: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 5,
        poll_delay: float = 2.0,
    ) -> List[BGGWishlistItem]:
        """Return wishlist items for `username`, optionally filtering by priority values and subtype.
        
        Args:
            username: BGG username
            priorities: List of wishlist priorities to filter (1-5)
            subtypes: List of subtypes to fetch (e.g., ['boardgame', 'boardgameexpansion'])
            debug_dump_dir: Not used with bgg-api library
            timeout: Request timeout (not currently used by bgg-api)
            max_retries: Number of retries for API requests
            poll_delay: Delay between retries
            
        Returns:
            List of BGGWishlistItem dicts
            
        Raises:
            RuntimeError: If the API returns errors or authentication fails
        """
        priorities_set = set(int(p) for p in priorities) if priorities else None
        
        # Determine subtypes to fetch
        subtype_list = list(subtypes) if subtypes else ["boardgame"]
        
        all_wishlist_items: List[BGGWishlistItem] = []
        seen_ids = set()
        
        # Fetch collection for each subtype
        for subtype in subtype_list:
            # Skip None/empty subtypes
            if not subtype:
                continue
                
            collection = None
            last_error = None
            
            # Retry loop for each subtype
            for attempt in range(1, max_retries + 1):
                try:
                    logging.debug("Fetching BGG collection for user %s, subtype %s, attempt %s", 
                                username, subtype, attempt)
                    
                    # Fetch wishlist items for this subtype
                    # If priorities are specified, we need to filter after fetching
                    collection = self.client.collection(
                        user_name=username,
                        subtype=subtype,
                        wishlist=True  # Only fetch wishlist items
                    )
                    break
                    
                except BGGApiRetryError as e:
                    logging.info("BGG API requested retry (attempt %s/%s); waiting %.1fs", 
                               attempt, max_retries, poll_delay)
                    last_error = e
                    if attempt < max_retries:
                        import time
                        time.sleep(poll_delay)
                        
                except BGGApiUnauthorizedError as e:
                    raise RuntimeError(
                        f"BoardGameGeek API authentication failed for user '{username}'. "
                        "The BGG API now requires an access token for authentication.\n\n"
                        "To fix this:\n"
                        "1. Log in to BoardGameGeek.com\n"
                        "2. Go to Account Settings > API Access\n"
                        "3. Generate an access token\n"
                        "4. Add 'access_token' to your bgg configuration in config.json\n\n"
                        "Example config:\n"
                        '  "bgg": {\n'
                        '    "username": "your-username",\n'
                        '    "access_token": "your-token-here",\n'
                        '    ...\n'
                        '  }'
                    ) from e
                    
                except (BGGApiError, BGGValueError) as e:
                    raise RuntimeError(
                        f"Error fetching BGG collection for user '{username}': {e}"
                    ) from e
            
            if collection is None:
                raise RuntimeError(
                    f"Failed to fetch BGG collection for user '{username}', subtype '{subtype}' "
                    f"after {max_retries} attempts. Last error: {last_error}"
                )
            
            # Process collection items
            for item in collection.items:
                # Skip if already seen (deduplication across subtypes)
                if item.id in seen_ids:
                    continue
                seen_ids.add(item.id)
                
                # Apply priority filter if specified
                priority = item.wishlist_priority
                if priorities_set and (priority is None or priority not in priorities_set):
                    continue
                
                all_wishlist_items.append(
                    BGGWishlistItem(
                        {
                            "name": item.name,
                            "object_id": str(item.id),
                            "year": item.year,
                            "priority": priority,
                        }
                    )
                )
        
        logging.info("Fetched %s wishlist items from BGG for user %s", 
                    len(all_wishlist_items), username)
        return all_wishlist_items
