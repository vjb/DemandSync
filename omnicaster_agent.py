import os
import json
import asyncio
from pymongo import MongoClient
from google import genai
from pydantic import BaseModel
from typing import List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

# Environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/hackathon")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# We need a mock Python function for deployment
def deploy_geofenced_ad(zip_code: str, radius: float, copy: str, item_id: str = None) -> bool:
    print(f"DEPLOYING AD to {zip_code} (radius: {radius}mi): {copy}")
    if not item_id:
        return True
        
    client = MongoClient(MONGO_URI)
    db = client.get_database("omnicaster_db")
    collection = db.get_collection("local_inventory")
    
    result = collection.update_one(
        {"item_id": item_id, "stock_count": {"$gt": 0}},
        {"$inc": {"stock_count": -1}}
    )
    return result.modified_count > 0

class OmniCaster:
    def __init__(self, update_callback=None):
        self.update_callback = update_callback or (lambda msg, data=None: None)
        
        try:
            self.ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
        except Exception:
            self.ai_client = None

        # Determine OS specific command
        self.npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
            
    async def log_step(self, message: str, data: Any = None):
        print(f"[OmniCaster] {message}")
        if asyncio.iscoroutinefunction(self.update_callback):
            await self.update_callback(message, data)
        else:
            self.update_callback(message, data)

    async def get_embedding(self, text: str) -> List[float]:
        if not self.ai_client:
            # Return dummy embedding if no key
            return [0.0] * 768
            
        try:
            response = self.ai_client.models.embed_content(
                model='gemini-embedding-2',
                contents=text,
            )
            return response.embeddings[0].values
        except Exception as e:
            await self.log_step(f"Embedding failed: {e}")
            return [0.0] * 768

    async def run_vector_search_mcp(self, vector: List[float], event_description: str) -> List[Dict]:
        await self.log_step("Initializing MongoDB MCP server...")
        
        # Prepare MCP
        env = os.environ.copy()
        env["MONGO_URI"] = MONGO_URI
        
        server_params = StdioServerParameters(
            command=self.npx_cmd,
            args=["-y", "@mongodb/mcp"],
            env=env
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Added timeout to prevent hanging if npx fails and doesn't write to stdout
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    await self.log_step("MongoDB MCP Connected. Searching for tools...")
                    
                    tools_result = await session.list_tools()
                    tools = tools_result.tools
                    tool_names = [t.name for t in tools]
                    await self.log_step(f"Available MCP Tools: {tool_names}")
                    
                    # Instead of forcing a specific tool name, we can ask the MCP to do the search if a vector tool exists.
                    # Since @mongodb/mcp tool names might be like "mongodb_atlas_vector_search" or "search_mongodb", we handle dynamically or fallback
                    search_tool = next((t.name for t in tools if "vector" in t.name.lower() or "search" in t.name.lower()), None)
                    
                    if search_tool:
                        await self.log_step(f"Using MCP tool: {search_tool}")
                        try:
                            # Typical args might be db, collection, index, queryVector
                            result = await session.call_tool(
                                search_tool,
                                arguments={
                                    "database": "omnicaster_db" if "omnicaster_db" in MONGO_URI else "omnicaster",
                                    "collection": "local_inventory",
                                    "queryVector": vector,
                                    "index": "vector_index",
                                    "path": "embedding",
                                    "numCandidates": 10,
                                    "limit": 5
                                }
                            )
                            # Try to parse the result
                            if result.content and len(result.content) > 0:
                                parsed = json.loads(result.content[0].text)
                                return parsed
                        except Exception as e:
                            await self.log_step(f"MCP Tool call failed: {e}. Falling back to PyMongo...")
                    else:
                        await self.log_step("No suitable MCP vector search tool found. Falling back to PyMongo...")
                        
        except Exception as e:
            await self.log_step(f"MCP Connection failed: {e}. Falling back to PyMongo...")

        # Fallback to direct PyMongo if MCP fails or is unavailable in the environment
        await self.log_step("Executing direct PyMongo vector search (or semantic match fallback)...")
        client = MongoClient(MONGO_URI)
        db = client.get_database("omnicaster_db")
        collection = db.get_collection("local_inventory")
        
        # If true vector search is set up in Atlas:
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": vector,
                        "numCandidates": 10,
                        "limit": 5
                    }
                }
            ]
            results = list(collection.aggregate(pipeline))
            if results:
                return results
        except Exception:
            pass

        # If no vector index is created yet, we simulate a semantic search by fetching all and just returning a few that might match text
        # For hackathon/demo purposes without atlas configured
        items = list(collection.find({"stock_count": {"$gt": 0}}).limit(3))
        return items

    async def handle_environmental_trigger(self, event_description: str):
        await self.log_step(f"Received Trigger: {event_description}")
        
        # 1. Get embedding
        await self.log_step("Converting trigger to semantic concept...")
        vector = await self.get_embedding(event_description)
        
        # 2. Vector search via MCP
        raw_inventory = await self.run_vector_search_mcp(vector, event_description)
        
        # Filter stock count > 0 (just in case query didn't)
        in_stock_inventory = [item for item in raw_inventory if item.get('stock_count', 0) > 0]
        
        if not in_stock_inventory:
            await self.log_step("No relevant in-stock inventory found for this event.")
            return None

        # Take the top match
        top_match = in_stock_inventory[0]
        if '_id' in top_match:
            top_match['_id'] = str(top_match['_id'])
        await self.log_step(f"Top Semantic Match: {top_match.get('name')} (Stock: {top_match.get('stock_count')})", data=top_match)
        
        # 3. Generate Ad Copy
        await self.log_step("Generating hyper-local ad copy with Gemini 3.1 Pro...")
        prompt = f"""
        You are an expert copywriter. A weather event has just occurred: "{event_description}".
        We have a matching product in stock in our Midtown Manhattan store.
        Product: {top_match.get('name')}
        Stock Remaining: {top_match.get('stock_count')}
        Price: ${top_match.get('price')}
        
        Write a short, urgent, and catchy 1-2 sentence ad copy (max 150 chars). 
        Make sure to specifically mention the exact stock count!
        Example: "Caught in the rain in Midtown? We have 12 storm-proof umbrellas left at our 5th Ave store."
        """
        
        ad_copy = "Caught in the weather? We have what you need in stock!" # Fallback
        if self.ai_client:
            try:
                response = self.ai_client.models.generate_content(
                    model='gemini-3.1-pro-preview', # We use the latest available SDK model, referring to as 3.1 Pro in prompt/docs
                    contents=prompt
                )
                ad_copy = response.text.strip()
            except Exception as e:
                await self.log_step(f"Gemini API Error: {e}. Using fallback copy.")
        else:
            await self.log_step("Gemini API Key missing. Using fallback copy.")
            
        await self.log_step(f"Generated Copy: {ad_copy}")
        
        # 4. Deploy Ad
        await self.log_step("Executing tool call: deploy_geofenced_ad...")
        zip_code = "10018" # Midtown Manhattan
        success = deploy_geofenced_ad(zip_code, radius=1.5, copy=ad_copy, item_id=top_match.get('item_id'))
        
        if success:
            await self.log_step("Deployment Successful. Inventory decremented.")
        else:
            await self.log_step("Deployment completed, but inventory decrement failed (out of stock?).")
            
        return {
            "copy": ad_copy,
            "zip_code": zip_code,
            "item": top_match,
            "remaining_stock": top_match.get('stock_count', 1) - 1
        }
