"""Tests for bgg_mm.bgg — BGGClient wrapper."""
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from bgg_mm.bgg import BGGClient, BGGWishlistItem, SUBTYPE_MAP
from boardgamegeek.api import BGGRestrictCollectionTo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(name: str, game_id: int, year: Optional[int] = 2020, wishlist_priority: Optional[int] = 1):
    """Return a minimal mock game object as returned by the bgg-api library."""
    game = MagicMock()
    game.name = name
    game.id = game_id
    game.year = year
    game.wishlist_priority = wishlist_priority
    return game


def _make_collection(*games):
    """Return a mock collection whose .items property yields the given games."""
    col = MagicMock()
    col.items = list(games)
    return col


# ---------------------------------------------------------------------------
# SUBTYPE_MAP
# ---------------------------------------------------------------------------

class TestSubtypeMap:
    def test_known_subtypes_present(self):
        expected = {
            "boardgame",
            "boardgameexpansion",
            "boardgameaccessory",
            "rpgitem",
            "rpgissue",
            "videogame",
        }
        assert expected == set(SUBTYPE_MAP.keys())

    def test_boardgame_maps_to_board_game(self):
        assert SUBTYPE_MAP["boardgame"] == BGGRestrictCollectionTo.BOARD_GAME

    def test_boardgameexpansion_maps_to_extension(self):
        assert SUBTYPE_MAP["boardgameexpansion"] == BGGRestrictCollectionTo.BOARD_GAME_EXTENSION


# ---------------------------------------------------------------------------
# BGGClient._fetch_collection
# ---------------------------------------------------------------------------

class TestFetchCollection:
    def setup_method(self):
        with patch("bgg_mm.bgg._BGGClient"):
            self.client = BGGClient(access_token="dummy-token")
        self.mock_inner = self.client._client

    def test_returns_mapped_items(self):
        game = _make_game("Pandemic", 30549, year=2008, wishlist_priority=2)
        self.mock_inner.collection.return_value = _make_collection(game)

        result = self.client._fetch_collection(
            "testuser", BGGRestrictCollectionTo.BOARD_GAME, None
        )

        assert len(result) == 1
        item = result[0]
        assert item["name"] == "Pandemic"
        assert item["object_id"] == "30549"
        assert item["year"] == 2008
        assert item["priority"] == 2

    def test_object_id_is_string(self):
        game = _make_game("Catan", 13, year=1995)
        self.mock_inner.collection.return_value = _make_collection(game)

        result = self.client._fetch_collection(
            "testuser", BGGRestrictCollectionTo.BOARD_GAME, None
        )
        assert isinstance(result[0]["object_id"], str)

    def test_wishlist_prio_passed_when_given(self):
        self.mock_inner.collection.return_value = _make_collection()

        self.client._fetch_collection(
            "testuser", BGGRestrictCollectionTo.BOARD_GAME, wishlist_prio=3
        )

        call_kwargs = self.mock_inner.collection.call_args.kwargs
        assert call_kwargs["wishlist_prio"] == 3
        assert call_kwargs["wishlist"] is True

    def test_wishlist_prio_omitted_when_none(self):
        self.mock_inner.collection.return_value = _make_collection()

        self.client._fetch_collection(
            "testuser", BGGRestrictCollectionTo.BOARD_GAME, wishlist_prio=None
        )

        call_kwargs = self.mock_inner.collection.call_args.kwargs
        assert "wishlist_prio" not in call_kwargs
        assert call_kwargs["wishlist"] is True

    def test_missing_wishlist_priority_attribute(self):
        game = _make_game("Azul", 230802)
        # Simulate attribute not existing on the game object
        del game.wishlist_priority
        self.mock_inner.collection.return_value = _make_collection(game)

        result = self.client._fetch_collection(
            "testuser", BGGRestrictCollectionTo.BOARD_GAME, None
        )
        assert result[0]["priority"] is None

    def test_empty_collection_returns_empty_list(self):
        self.mock_inner.collection.return_value = _make_collection()

        result = self.client._fetch_collection(
            "testuser", BGGRestrictCollectionTo.BOARD_GAME, None
        )
        assert result == []


# ---------------------------------------------------------------------------
# BGGClient.fetch_wishlist
# ---------------------------------------------------------------------------

class TestFetchWishlist:
    def setup_method(self):
        with patch("bgg_mm.bgg._BGGClient"):
            self.client = BGGClient(access_token="dummy-token")
        self.mock_inner = self.client._client

    def _setup_collection(self, *games):
        self.mock_inner.collection.return_value = _make_collection(*games)

    def test_default_subtypes_boardgame_and_expansion(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser")

        # Should have been called twice: once for boardgame, once for boardgameexpansion
        assert self.mock_inner.collection.call_count == 2
        subtypes_used = [
            call.kwargs["subtype"]
            for call in self.mock_inner.collection.call_args_list
        ]
        assert BGGRestrictCollectionTo.BOARD_GAME in subtypes_used
        assert BGGRestrictCollectionTo.BOARD_GAME_EXTENSION in subtypes_used

    def test_custom_subtypes_used(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser", subtypes=["rpgitem"])

        assert self.mock_inner.collection.call_count == 1
        subtype = self.mock_inner.collection.call_args.kwargs["subtype"]
        assert subtype == BGGRestrictCollectionTo.RPG

    def test_priorities_cause_per_prio_calls(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser", subtypes=["boardgame"], priorities=[1, 2])

        # 1 subtype × 2 priorities = 2 calls
        assert self.mock_inner.collection.call_count == 2
        prios_used = [
            call.kwargs.get("wishlist_prio")
            for call in self.mock_inner.collection.call_args_list
        ]
        assert 1 in prios_used
        assert 2 in prios_used

    def test_deduplication_by_object_id(self):
        game_a = _make_game("Pandemic", 30549)
        game_b = _make_game("Pandemic", 30549)  # duplicate id
        # Return same game from boardgame + boardgameexpansion subtypes
        self.mock_inner.collection.return_value = _make_collection(game_a, game_b)

        result = self.client.fetch_wishlist("testuser")

        ids = [item["object_id"] for item in result]
        assert len(ids) == len(set(ids)), "Duplicate object_ids should be removed"

    def test_returns_bgg_wishlist_item_instances(self):
        game = _make_game("Catan", 13)
        self._setup_collection(game)

        result = self.client.fetch_wishlist("testuser", subtypes=["boardgame"])
        assert all(isinstance(item, BGGWishlistItem) for item in result)

    def test_priorities_none_means_no_wishlist_prio_kwarg(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser", subtypes=["boardgame"], priorities=None)

        call_kwargs = self.mock_inner.collection.call_args.kwargs
        assert "wishlist_prio" not in call_kwargs

    def test_unknown_subtype_falls_back_to_board_game(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser", subtypes=["unknown_type"])

        subtype = self.mock_inner.collection.call_args.kwargs["subtype"]
        assert subtype == BGGRestrictCollectionTo.BOARD_GAME

    def test_duplicate_subtypes_deduplicated(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser", subtypes=["boardgame", "boardgame"])

        # Only one unique subtype, so only one call
        assert self.mock_inner.collection.call_count == 1

    def test_none_subtype_treated_as_boardgame(self):
        self._setup_collection()
        self.client.fetch_wishlist("testuser", subtypes=[None])

        assert self.mock_inner.collection.call_count == 1
        subtype = self.mock_inner.collection.call_args.kwargs["subtype"]
        assert subtype == BGGRestrictCollectionTo.BOARD_GAME
