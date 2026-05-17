import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from omnicaster_agent import OmniCaster, deploy_geofenced_ad

@pytest.fixture
def mock_agent():
    with patch('omnicaster_agent.genai.Client') as mock_client:
        agent = OmniCaster()
        agent.ai_client = mock_client.return_value
        yield agent

@pytest.mark.asyncio
async def test_vector_search_logic(mock_agent):
    # Mocking MCP to return a list with 0 stock and >0 stock items
    mock_agent.run_vector_search_mcp = AsyncMock(return_value=[
        {"item_id": "P001", "name": "Zero Stock Item", "stock_count": 0, "price": 10},
        {"item_id": "P002", "name": "Valid Item", "stock_count": 5, "price": 20}
    ])
    mock_agent.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    
    # Mock Gemini generation
    mock_agent.ai_client.models.generate_content.return_value.text = "Valid Item Ad"
    
    # Run trigger
    result = await mock_agent.handle_environmental_trigger("Test Event")
    
    # The agent should have selected P002, skipping P001 due to 0 stock
    assert result is not None
    assert result["item"]["item_id"] == "P002"
    assert result["item"]["stock_count"] == 5

@pytest.mark.asyncio
async def test_ad_generation_prompt(mock_agent):
    mock_agent.run_vector_search_mcp = AsyncMock(return_value=[
        {"item_id": "P003", "name": "Raincoat", "stock_count": 42, "price": 50}
    ])
    mock_agent.get_embedding = AsyncMock(return_value=[0.1])
    
    # Setup mock response for the LLM
    mock_response = MagicMock()
    mock_response.text = "Caught in the rain? We have 42 Raincoats left!"
    mock_agent.ai_client.models.generate_content.return_value = mock_response
    
    result = await mock_agent.handle_environmental_trigger("Rain")
    
    # Check that Gemini was called with the correct stock count in the prompt
    args, kwargs = mock_agent.ai_client.models.generate_content.call_args
    prompt_used = kwargs['contents']
    assert "Stock Remaining: 42" in prompt_used
    
    # Check output
    assert "42 Raincoats left" in result["copy"]

def test_mock_ad_deployment():
    # We patch MongoClient to avoid hitting a real DB
    with patch('omnicaster_agent.MongoClient') as mock_mongo:
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_mongo.return_value.get_database.return_value = mock_db
        mock_db.get_collection.return_value = mock_collection
        
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result
        
        # Test function
        success = deploy_geofenced_ad("10018", 1.5, "Test Ad", "P001")
        
        assert success is True
        mock_collection.update_one.assert_called_once_with(
            {"item_id": "P001", "stock_count": {"$gt": 0}},
            {"$inc": {"stock_count": -1}}
        )
