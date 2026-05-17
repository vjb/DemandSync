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

def deploy_geofenced_ad(zip_code: str, radius: float, copy: str, image_url: str, item_id: str = None) -> bool:
    print(f"DEPLOYING AD to {zip_code} (radius: {radius}mi): {copy} | Image: {image_url}")
    if not item_id:
        return True
        
    client = MongoClient(MONGO_URI)
    db = client.get_database("demandsync_db")
    collection = db.get_collection("local_inventory")
    
    result = collection.update_one(
        {"item_id": item_id, "stock_count": {"$gt": 0}},
        {"$inc": {"stock_count": -1}}
    )
    return result.modified_count > 0

class DemandSyncAgent:
    def __init__(self, update_callback=None):
        self.update_callback = update_callback or (lambda msg, data=None: None)
        
        try:
            self.ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
        except Exception:
            self.ai_client = None

        self.npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
            
    async def log_step(self, message: str, data: Any = None):
        print(f"[DemandSync] {message}")
        if asyncio.iscoroutinefunction(self.update_callback):
            await self.update_callback(message, data)
        else:
            self.update_callback(message, data)

    async def get_embedding(self, text: str) -> List[float]:
        if not self.ai_client:
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
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    await self.log_step("MongoDB MCP Connected. Searching for tools...")
                    
                    tools_result = await session.list_tools()
                    tools = tools_result.tools
                    search_tool = next((t.name for t in tools if "vector" in t.name.lower() or "search" in t.name.lower()), None)
                    
                    if search_tool:
                        await self.log_step(f"Using MCP tool: {search_tool}")
                        try:
                            result = await session.call_tool(
                                search_tool,
                                arguments={
                                    "database": "demandsync_db",
                                    "collection": "local_inventory",
                                    "queryVector": vector,
                                    "index": "vector_index",
                                    "path": "embedding",
                                    "numCandidates": 15,
                                    "limit": 5
                                }
                            )
                            if result.content and len(result.content) > 0:
                                parsed = json.loads(result.content[0].text)
                                return parsed
                        except Exception as e:
                            await self.log_step(f"MCP Tool call failed: {e}. Falling back to PyMongo...")
                    else:
                        await self.log_step("No suitable MCP vector search tool found. Falling back to PyMongo...")
                        
        except Exception as e:
            await self.log_step(f"MCP Connection failed or timed out: {e}. Falling back to PyMongo...")

        # Fallback PyMongo search
        await self.log_step("Executing direct PyMongo vector search (or semantic match fallback)...")
        client = MongoClient(MONGO_URI)
        db = client.get_database("demandsync_db")
        collection = db.get_collection("local_inventory")
        
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": vector,
                        "numCandidates": 15,
                        "limit": 5
                    }
                }
            ]
            results = list(collection.aggregate(pipeline))
            if results:
                return results
        except Exception:
            pass

        items = list(collection.find({"stock_count": {"$gt": 0}}).limit(3))
        return items

    async def generate_ad_creative(self, product_name: str, event_description: str) -> str:
        await self.log_step("Generating visual ad creative with Imagen 3.0...")
        import base64
        
        image_b64 = ""
        if not self.ai_client:
            await self.log_step("No GenAI API key. Simulating creative generation.")
            return image_b64
            
        prompt = f"A cinematic, high-quality product shot of a {product_name} in a New York City setting during a {event_description}. Social media ad style, vibrant, hyper-realistic."
        
        try:
            try:
                result = self.ai_client.models.generate_images(
                    model='imagen-3.0-generate-001',
                    prompt=prompt,
                    config=genai.types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="1:1"
                    )
                )
            except Exception as model_err:
                await self.log_step(f"Imagen 3.0 failed ({model_err}). Trying fallback to imagen-4.0...")
                result = self.ai_client.models.generate_images(
                    model='imagen-4.0-generate-001',
                    prompt=prompt,
                    config=genai.types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="1:1"
                    )
                )

            if result.generated_images:
                image_b64 = base64.b64encode(result.generated_images[0].image.image_bytes).decode('utf-8')
                await self.log_step("Ad creative generated successfully!")
            else:
                await self.log_step("No image generated by API.")
        except Exception as e:
            await self.log_step(f"Imagen API Error: {e}")
            
        return image_b64

    async def handle_environmental_trigger(self, event_description: str):
        await self.log_step(f"Received Trigger: {event_description}")
        
        # 1. Get embedding
        await self.log_step("Converting trigger to semantic concept...")
        vector = await self.get_embedding(event_description)
        
        # 2. Vector search via MCP
        raw_inventory = await self.run_vector_search_mcp(vector, event_description)
        
        # Anti-False Advertising check
        in_stock_inventory = [item for item in raw_inventory if item.get('stock_count', 0) > 0]
        
        if not in_stock_inventory:
            await self.log_step("Anti-False Advertising Engine: Aborting! No stock available for matching items.")
            return None

        # Take top match
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
        
        ad_copy = "Caught in the weather? We have what you need in stock!" 
        if self.ai_client:
            try:
                response = self.ai_client.models.generate_content(
                    model='gemini-3.1-pro-preview',
                    contents=prompt
                )
                ad_copy = response.text.strip()
            except Exception as e:
                await self.log_step(f"Gemini API Error: {e}. Using fallback copy.")
        else:
            await self.log_step("Gemini API Key missing. Using fallback copy.")
            
        await self.log_step(f"Generated Copy: {ad_copy}")
        
        # 4. Generate Creative (Imagen 3.0)
        image_b64 = await self.generate_ad_creative(top_match.get('name'), event_description)
        
        # 5. Deploy Ad
        await self.log_step("Executing tool call: deploy_geofenced_ad...")
        zip_code = "10018" # Midtown Manhattan
        success = deploy_geofenced_ad(zip_code, radius=1.5, copy=ad_copy, image_url="base64_image", item_id=top_match.get('item_id'))
        
        if success:
            await self.log_step("Deployment Successful. Inventory decremented.")
        else:
            await self.log_step("Deployment completed, but inventory decrement failed (out of stock?).")
            
        return {
            "copy": ad_copy,
            "image_b64": image_b64,
            "zip_code": zip_code,
            "item": top_match,
            "remaining_stock": top_match.get('stock_count', 1) - 1
        }
