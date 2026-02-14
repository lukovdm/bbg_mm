"""Integration test for state management with real-world scenario."""
import tempfile
from pathlib import Path
from bgg_mm.state import AvailabilityState
from bgg_mm.shop import ShopProduct

print("=== Testing State Management Integration ===\n")

with tempfile.TemporaryDirectory() as tmpdir:
    state_file = Path(tmpdir) / "data" / "availability.json"
    
    print(f"State file: {state_file}")
    print()
    
    # Scenario 1: First run - some games are available
    print("--- First run: 3 games found available ---")
    state = AvailabilityState(state_file)
    state.load()
    
    available_products = [
        ShopProduct(name="Game A", url="http://shop.com/game-a", available=True, price="€40"),
        ShopProduct(name="Game B", url="http://shop.com/game-b", available=True, price="€50"),
        ShopProduct(name="Game C", url="http://shop.com/game-c", available=True, price="€60"),
    ]
    
    # All are newly available (nothing in state yet)
    newly_available = [p for p in available_products if p.url not in state.known_urls]
    print(f"Newly available: {len(newly_available)}")
    for p in newly_available:
        print(f"  - {p.name} @ {p.price}")
    
    # Update state
    state.update(p.url for p in available_products if p.available)
    print(f"State updated with {len(state.known_urls)} URLs")
    print()
    
    # Scenario 2: Second run - same games still available + 1 new
    print("--- Second run: Same 3 games + 1 new game ---")
    state2 = AvailabilityState(state_file)
    state2.load()
    
    print(f"Loaded state with {len(state2.known_urls)} known URLs")
    
    available_products2 = [
        ShopProduct(name="Game A", url="http://shop.com/game-a", available=True, price="€40"),
        ShopProduct(name="Game B", url="http://shop.com/game-b", available=True, price="€50"),
        ShopProduct(name="Game C", url="http://shop.com/game-c", available=True, price="€60"),
        ShopProduct(name="Game D", url="http://shop.com/game-d", available=True, price="€70"),  # NEW!
    ]
    
    # Only Game D should be newly available
    newly_available2 = [p for p in available_products2 if p.url not in state2.known_urls]
    print(f"Newly available: {len(newly_available2)}")
    for p in newly_available2:
        print(f"  - {p.name} @ {p.price}")
    
    assert len(newly_available2) == 1
    assert newly_available2[0].name == "Game D"
    
    # Update state
    state2.update(p.url for p in available_products2 if p.available)
    print(f"State updated with {len(state2.known_urls)} URLs")
    print()
    
    # Scenario 3: Third run - Game B becomes unavailable
    print("--- Third run: Game B becomes unavailable ---")
    state3 = AvailabilityState(state_file)
    state3.load()
    
    print(f"Loaded state with {len(state3.known_urls)} known URLs")
    
    available_products3 = [
        ShopProduct(name="Game A", url="http://shop.com/game-a", available=True, price="€40"),
        ShopProduct(name="Game C", url="http://shop.com/game-c", available=True, price="€60"),
        ShopProduct(name="Game D", url="http://shop.com/game-d", available=True, price="€70"),
        # Game B is not in the list (became unavailable)
    ]
    
    # Nothing newly available
    newly_available3 = [p for p in available_products3 if p.url not in state3.known_urls]
    print(f"Newly available: {len(newly_available3)}")
    
    assert len(newly_available3) == 0
    
    # Update state - Game B should be removed
    state3.update(p.url for p in available_products3 if p.available)
    print(f"State updated with {len(state3.known_urls)} URLs (Game B removed)")
    
    assert "http://shop.com/game-b" not in state3.known_urls
    print()
    
    # Scenario 4: Fourth run - Game B becomes available again
    print("--- Fourth run: Game B becomes available again ---")
    state4 = AvailabilityState(state_file)
    state4.load()
    
    print(f"Loaded state with {len(state4.known_urls)} known URLs")
    
    available_products4 = [
        ShopProduct(name="Game A", url="http://shop.com/game-a", available=True, price="€40"),
        ShopProduct(name="Game B", url="http://shop.com/game-b", available=True, price="€45"),  # Back!
        ShopProduct(name="Game C", url="http://shop.com/game-c", available=True, price="€60"),
        ShopProduct(name="Game D", url="http://shop.com/game-d", available=True, price="€70"),
    ]
    
    # Game B should be newly available again
    newly_available4 = [p for p in available_products4 if p.url not in state4.known_urls]
    print(f"Newly available: {len(newly_available4)}")
    for p in newly_available4:
        print(f"  - {p.name} @ {p.price}")
    
    assert len(newly_available4) == 1
    assert newly_available4[0].name == "Game B"
    
    print()
    print("=== State Management Integration Tests PASSED! ===")
