import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from demandsync_v2_agent import DemandSyncV2Agent

@pytest.fixture
def agent():
    return DemandSyncV2Agent()

@pytest.mark.asyncio
async def test_dynamic_pricing_logic(agent):
    agent.ai_client = MagicMock()
    
    # Mock Gemini pricing response
    mock_response = MagicMock()
    mock_response.text = '{"new_price": 145.50, "reasoning": "High demand blizzard."}'
    agent.ai_client.models.generate_content.return_value = mock_response
    
    item = {"name": "Snow Boots", "price": 120.00, "stock_count": 2}
    result = await agent.calculate_dynamic_price(item, "Blizzard")
    
    assert result["new_price"] == 145.50
    assert "reasoning" in result

@pytest.mark.asyncio
async def test_multichannel_copy_json(agent):
    agent.run_vector_search_mcp = AsyncMock(return_value=[
        {"item_id": "P003", "name": "Test Item", "stock_count": 10, "price": 50}
    ])
    agent.get_embedding = AsyncMock(return_value=[0.1] * 768)
    
    agent.generate_ad_creative = AsyncMock(return_value="data:image/jpeg;base64,TEST")
    
    agent.ai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"new_price": 50, "reasoning": "Standard"}'
    
    mock_copy_response = MagicMock()
    mock_copy_response.text = '{"instagram_caption": "IG", "twitter_post": "TW", "facebook_ad_copy": "FB"}'
    
    agent.ai_client.models.generate_content.side_effect = [mock_response, mock_copy_response]

    with patch("demandsync_v2_agent.MongoClient") as mock_mongo:
        result = await agent.handle_environmental_trigger("Another trigger")
        
        assert "instagram_caption" in result["copy"]
        assert "twitter_post" in result["copy"]
        assert "facebook_ad_copy" in result["copy"]

@pytest.mark.asyncio
async def test_supply_chain_actuation(agent):
    # Test that PO is generated correctly
    po = agent.generate_supplier_purchase_order("P001", 100)
    assert po["item_id"] == "P001"
    assert po["quantity"] == 100
    assert po["status"] == "TRANSMITTED"
    assert "PO-" in po["po_number"]

@pytest.mark.asyncio
async def test_execute_viral_sales(agent):
    # Mock MongoDB
    with patch("demandsync_v2_agent.MongoClient") as mock_mongo:
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_mongo.return_value = mock_client
        mock_client.get_database.return_value = mock_db
        mock_db.get_collection.return_value = mock_collection
        
        # Initial state: stock is 3
        mock_collection.find_one.return_value = {"item_id": "P001", "stock_count": 3}
        
        po = await agent.execute_viral_sales("P001")
        
        # Verify it decremented stock all the way to 0
        assert mock_collection.update_one.call_count == 4 # 3, 2, 1, 0
        mock_collection.update_one.assert_called_with({"item_id": "P001"}, {"$set": {"stock_count": 0}})
        
        # Verify PO was generated
        assert po is not None
        assert po["item_id"] == "P001"
