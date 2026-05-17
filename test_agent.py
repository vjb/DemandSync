import pytest
import asyncio
from demandsync_v2_agent import DemandSyncV2Agent

@pytest.mark.asyncio
async def test_agent_builder_pricing_compliance():
    agent = DemandSyncV2Agent()
    # Mocking item and event to test price cap rule (15% for severe weather)
    item = {
        "name": "Heavy Duty Snow Shovel",
        "price": 100.0,
        "stock_count": 5
    }
    
    event_desc = "Category 4 Blizzard hitting Central Park"
    
    # Calculate price
    result = await agent.calculate_dynamic_price(item, event_desc)
    
    new_price = result.get("new_price")
    
    # Assert price is capped at +15% (<= 115)
    assert new_price <= 115.0, f"Compliance Failure: Price {new_price} exceeded 15% markup cap."
    assert "reasoning" in result

@pytest.mark.asyncio
async def test_agent_builder_sports_compliance():
    agent = DemandSyncV2Agent()
    # Mocking item and event to test price cap rule (35% for sports)
    item = {
        "name": "US Open Tennis Official Hat",
        "price": 100.0,
        "stock_count": 5
    }
    
    event_desc = "Local American Tennis Player wins US Open upset"
    
    # Calculate price
    result = await agent.calculate_dynamic_price(item, event_desc)
    
    new_price = result.get("new_price")
    
    # Assert price is capped at +35% (<= 135)
    assert new_price <= 135.0, f"Compliance Failure: Price {new_price} exceeded 35% markup cap."
