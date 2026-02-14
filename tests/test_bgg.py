"""Tests for BGG client functionality."""
import pytest
from unittest.mock import Mock, MagicMock
from bgg_mm.bgg import BGGClient, BGGWishlistItem


# Test data from debug_xml/bgg-wishlist-mageleve-boardgame-1761056242.xml
SAMPLE_XML_WITH_ITEMS = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<items totalitems="6" termsofuse="https://boardgamegeek.com/xmlapi/termsofuse" pubdate="Tue, 21 Oct 2025 14:12:36 +0000">
		<item objecttype="thing" objectid="371183" subtype="boardgame" collid="137033272">
	<name sortindex="1">JOYRIDE: Survival of the Fastest</name>
		<yearpublished>2024</yearpublished>			<image>https://cf.geekdo-images.com/ywWVqGH03eEOWFaRPtmlAg__original/img/igW-m9SJJZJe-uRH1UaZVcn0AhU=/0x0/filters:format(png)/pic7186560.png</image>
		<thumbnail>https://cf.geekdo-images.com/ywWVqGH03eEOWFaRPtmlAg__small/img/zSIuSMwVuw0ZnLBCow6a71SBeHM=/fit-in/200x150/filters:strip_icc()/pic7186560.png</thumbnail>
			<status own="0" prevowned="0" fortrade="0" want="0" wanttoplay="0" wanttobuy="0" wishlist="1" wishlistpriority="2" preordered="0" lastmodified="2025-10-04 08:32:41" />
	<numplays>0</numplays>							</item>
		<item objecttype="thing" objectid="422780" subtype="boardgame" collid="137029752">
	<name sortindex="1">Mistborn: The Deckbuilding Game</name>
		<yearpublished>2024</yearpublished>			<image>https://cf.geekdo-images.com/Fr_k9-uU3hEUnw_3s-UnZQ__original/img/XhMQVwHzTcQPTS_2cjIn_NdZJwM=/0x0/filters:format(png)/pic8290518.png</image>
		<thumbnail>https://cf.geekdo-images.com/Fr_k9-uU3hEUnw_3s-UnZQ__small/img/YLbnyONFWmI-9bu5J30aZke7BjI=/fit-in/200x150/filters:strip_icc()/pic8290518.png</thumbnail>
			<status own="0" prevowned="0" fortrade="0" want="0" wanttoplay="0" wanttobuy="0" wishlist="1" wishlistpriority="3" preordered="0" lastmodified="2025-10-04 02:04:24" />
	<numplays>0</numplays>							</item>
		<item objecttype="thing" objectid="357873" subtype="boardgame" collid="137029766">
	<name sortindex="5">The Old King&#039;s Crown</name>
		<yearpublished>2025</yearpublished>			<image>https://cf.geekdo-images.com/q3Qp4L-rU3VOW6fMAFUJnQ__original/img/zICTkM9KNDlQ6wZgIMQ2HavR4PE=/0x0/filters:format(jpeg)/pic8937255.jpg</image>
		<thumbnail>https://cf.geekdo-images.com/q3Qp4L-rU3VOW6fMAFUJnQ__small/img/wLX_C6w13ebCON4euesUohQE_Ck=/fit-in/200x150/filters:strip_icc()/pic8937255.jpg</thumbnail>
			<status own="0" prevowned="0" fortrade="0" want="0" wanttoplay="0" wanttobuy="0" wishlist="1" wishlistpriority="2" preordered="0" lastmodified="2025-10-04 08:32:29" />
	<numplays>0</numplays>							</item>
		<item objecttype="thing" objectid="338960" subtype="boardgame" collid="137033451">
	<name sortindex="1">Slay the Spire: The Board Game</name>
		<yearpublished>2024</yearpublished>			<image>https://cf.geekdo-images.com/PQzVclEoOQ_wr4e1V86kxA__original/img/KXOf1hP1cIJQLabKhZulWP-e9wI=/0x0/filters:format(png)/pic8157856.png</image>
		<thumbnail>https://cf.geekdo-images.com/PQzVclEoOQ_wr4e1V86kxA__small/img/cpmsSDagE5RvQ1ERXl-fMJIaUUg=/fit-in/200x150/filters:strip_icc()/pic8157856.png</thumbnail>
			<status own="0" prevowned="0" fortrade="0" want="0" wanttoplay="0" wanttobuy="0" wishlist="1" wishlistpriority="3" preordered="0" lastmodified="2025-10-04 05:13:16" />
	<numplays>0</numplays>							</item>
		<item objecttype="thing" objectid="420033" subtype="boardgame" collid="137033268">
	<name sortindex="1">Vantage</name>
		<yearpublished>2025</yearpublished>			<image>https://cf.geekdo-images.com/M0e9l-SHH2H4RMSAcnsDgg__original/img/nT1NtVviWxSBgVv5lvM4RmemITs=/0x0/filters:format(jpeg)/pic8658546.jpg</image>
		<thumbnail>https://cf.geekdo-images.com/M0e9l-SHH2H4RMSAcnsDgg__small/img/TL_OB6SKLJpCM1u1MD4ddEAp9ic=/fit-in/200x150/filters:strip_icc()/pic8658546.jpg</thumbnail>
			<status own="0" prevowned="0" fortrade="0" want="0" wanttoplay="0" wanttobuy="0" wishlist="1" wishlistpriority="4" preordered="0" lastmodified="2025-10-04 08:32:35" />
	<numplays>0</numplays>							</item>
		<item objecttype="thing" objectid="113924" subtype="boardgame" collid="137033454">
	<name sortindex="1">Zombicide</name>
		<yearpublished>2012</yearpublished>			<image>https://cf.geekdo-images.com/ZqjfzvtaTIT5FYp1D2CfKw__original/img/Arh3sc5cBx5FYg92vCvwtx-lKJw=/0x0/filters:format(jpeg)/pic1196191.jpg</image>
		<thumbnail>https://cf.geekdo-images.com/ZqjfzvtaTIT5FYp1D2CfKw__small/img/3Z0sYfpvqCcSDIgHHPSWIlgjTVk=/fit-in/200x150/filters:strip_icc()/pic1196191.jpg</thumbnail>
			<status own="0" prevowned="0" fortrade="0" want="0" wanttoplay="0" wanttobuy="0" wishlist="1" wishlistpriority="3" preordered="0" lastmodified="2025-10-04 05:13:51" />
	<numplays>0</numplays>							</item>
		
</items>"""

SAMPLE_XML_EMPTY = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<items totalitems="0" termsofuse="https://boardgamegeek.com/xmlapi/termsofuse" pubdate="Tue, 21 Oct 2025 14:15:01 +0000">
		
</items>"""


class TestBGGClient:
    """Test BGG client functionality."""

    def test_parse_wishlist_basic(self):
        """Test parsing a basic wishlist XML response."""
        items = BGGClient._parse_wishlist(SAMPLE_XML_WITH_ITEMS, priorities=None)
        
        assert len(items) == 6
        assert items[0]["name"] == "JOYRIDE: Survival of the Fastest"
        assert items[0]["object_id"] == "371183"
        assert items[0]["year"] == 2024
        assert items[0]["priority"] == 2

    def test_parse_wishlist_with_priority_filter(self):
        """Test parsing wishlist with priority filter."""
        # Filter for priority 2 only
        items = BGGClient._parse_wishlist(SAMPLE_XML_WITH_ITEMS, priorities=[2])
        
        assert len(items) == 2  # JOYRIDE and The Old King's Crown
        assert all(item["priority"] == 2 for item in items)

    def test_parse_wishlist_with_multiple_priorities(self):
        """Test parsing wishlist with multiple priority filter."""
        # Filter for priorities 2 and 3
        items = BGGClient._parse_wishlist(SAMPLE_XML_WITH_ITEMS, priorities=[2, 3])
        
        assert len(items) == 5  # All except Vantage (priority 4)
        assert all(item["priority"] in [2, 3] for item in items)

    def test_parse_wishlist_empty(self):
        """Test parsing an empty wishlist."""
        items = BGGClient._parse_wishlist(SAMPLE_XML_EMPTY, priorities=None)
        assert len(items) == 0

    def test_fetch_wishlist_deduplication(self, mocker):
        """Test that duplicate items from different subtypes are deduplicated."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_XML_WITH_ITEMS
        mock_session.get.return_value = mock_response
        
        client = BGGClient(session=mock_session)
        
        # Fetch with two subtypes - should deduplicate
        items = client.fetch_wishlist(
            username="testuser",
            priorities=None,
            subtypes=["boardgame", "boardgame"],  # Same subtype twice
        )
        
        # Should only have 6 unique items, not 12
        assert len(items) == 6

    def test_fetch_wishlist_handles_202_retry(self, mocker):
        """Test that fetch_wishlist retries when getting 202 response."""
        mock_session = Mock()
        
        # First call returns 202, second returns 200
        response_202 = Mock()
        response_202.status_code = 202
        
        response_200 = Mock()
        response_200.status_code = 200
        response_200.text = SAMPLE_XML_WITH_ITEMS
        
        mock_session.get.side_effect = [response_202, response_200]
        
        client = BGGClient(session=mock_session)
        
        # Should succeed after retry
        items = client.fetch_wishlist(
            username="testuser",
            priorities=None,
            subtypes=["boardgame"],
            max_retries=3,
            poll_delay=0.1,  # Short delay for test
        )
        
        assert len(items) == 6
        assert mock_session.get.call_count == 2

    def test_fetch_wishlist_raises_on_max_retries(self, mocker):
        """Test that fetch_wishlist raises error after max retries."""
        mock_session = Mock()
        
        # Always return 202
        response_202 = Mock()
        response_202.status_code = 202
        mock_session.get.return_value = response_202
        
        client = BGGClient(session=mock_session)
        
        # Should raise after exhausting retries
        with pytest.raises(RuntimeError, match="kept returning 202"):
            client.fetch_wishlist(
                username="testuser",
                priorities=None,
                subtypes=["boardgame"],
                max_retries=2,
                poll_delay=0.1,
            )

    def test_wishlist_item_name_extraction(self):
        """Test that game names are properly extracted from XML."""
        xml_with_special_chars = """<?xml version="1.0" encoding="utf-8"?>
<items totalitems="1">
    <item objecttype="thing" objectid="1" subtype="boardgame" collid="1">
        <name sortindex="5">The Old King&#039;s Crown</name>
        <yearpublished>2025</yearpublished>
        <status wishlist="1" wishlistpriority="1" />
    </item>
</items>"""
        
        items = BGGClient._parse_wishlist(xml_with_special_chars, priorities=None)
        
        assert len(items) == 1
        assert items[0]["name"] == "The Old King's Crown"

    def test_wishlist_without_year(self):
        """Test handling items without year published."""
        xml_no_year = """<?xml version="1.0" encoding="utf-8"?>
<items totalitems="1">
    <item objecttype="thing" objectid="1" subtype="boardgame" collid="1">
        <name sortindex="1">Test Game</name>
        <status wishlist="1" wishlistpriority="1" />
    </item>
</items>"""
        
        items = BGGClient._parse_wishlist(xml_no_year, priorities=None)
        
        assert len(items) == 1
        assert items[0]["year"] is None
