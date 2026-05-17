import os
import json
import asyncio
import base64
from pymongo import MongoClient
from google import genai
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/hackathon")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

class DynamicPriceResponse(BaseModel):
    new_price: float = Field(description="The calculated surge price.")
    reasoning: str = Field(description="Reasoning for the price adjustment.")

class DemandSyncV2Agent:
    def __init__(self, update_callback=None):
        self.update_callback = update_callback or (lambda msg, data=None: None)
        try:
            self.ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
        except Exception:
            self.ai_client = None
        self.npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
            
    async def log_step(self, message: str, data: Any = None):
        print(f"[INFO] {message}")
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
                    search_tool = next((t.name for t in tools_result.tools if "vector" in t.name.lower() or "search" in t.name.lower()), None)
                    
                    if search_tool:
                        await self.log_step(f"Using MCP tool: {search_tool}")
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
                            return json.loads(result.content[0].text)
                    else:
                        await self.log_step("No suitable MCP vector search tool found.")
        except Exception as e:
            await self.log_step(f"MCP Connection failed or timed out: {e}. Falling back to PyMongo...")

        # Fallback PyMongo search
        await self.log_step("Executing direct PyMongo vector search (or semantic match fallback)...")
        client = MongoClient(MONGO_URI)
        db = client.get_database("demandsync_db")
        collection = db.get_collection("local_inventory")
        
        try:
            results = list(collection.aggregate([{
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": vector,
                    "numCandidates": 15,
                    "limit": 5
                }
            }]))
            if results: return results
        except Exception:
            pass
        return list(collection.find({"stock_count": {"$gt": 0}}).limit(3))

    async def calculate_dynamic_price(self, item: Dict, event_description: str) -> Dict:
        base_price = item.get("price", 0.0)
        stock = item.get("stock_count", 0)
        
        await self.log_step(f"Calculating dynamic pricing for '{item.get('name')}' (Base: ${base_price}, Stock: {stock})...")
        
        if not self.ai_client:
            # Fallback mock dynamic pricing
            new_price = round(base_price * 1.25, 2)
            reasoning = "Simulated surge pricing due to high demand and low stock."
            return {"new_price": new_price, "reasoning": reasoning}

        prompt = f"""
        You are an expert retail FinOps agent. A weather event is occurring: "{event_description}".
        We have a matching product in stock in Midtown Manhattan.
        Product: {item.get('name')}
        Current Base Price: ${base_price}
        Current Stock: {stock}
        
        Based on the severity of the weather and the remaining stock, calculate a new surge price to maximize profit margin while remaining plausible. 
        Higher severity + lower stock = higher markup.
        """
        
        try:
            response = self.ai_client.models.generate_content(
                model='gemini-3.1-pro-preview',
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DynamicPriceResponse,
                    temperature=0.2
                )
            )
            parsed = json.loads(response.text)
            new_price = round(parsed["new_price"], 2)
            
            # Ensure price doesn't go below base
            if new_price < base_price:
                new_price = base_price
                
            return {"new_price": new_price, "reasoning": parsed["reasoning"]}
        except Exception as e:
            await self.log_step(f"Gemini Pricing Error: {e}")
            return {"new_price": round(base_price * 1.15, 2), "reasoning": "Fallback algorithmic surge."}

    async def generate_ad_creative(self, product_name: str, event_description: str) -> str:
        await self.log_step("Generating visual ad creative with Imagen 3.0...")
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
        except Exception as e:
            await self.log_step(f"Imagen API Error: {e}")
            
        return image_b64

    def generate_supplier_purchase_order(self, item_id: str, restock_quantity: int) -> Dict:
        po = {
            "po_number": f"PO-{os.urandom(4).hex().upper()}",
            "supplier": "GlobalSupply Networks API",
            "item_id": item_id,
            "quantity": restock_quantity,
            "status": "TRANSMITTED",
            "timestamp": asyncio.get_event_loop().time()
        }
        print(f"\n[INFO] Purchase order structure generated:\n{json.dumps(po, indent=2)}\n")
        return po

    async def handle_environmental_trigger(self, event_description: str):
        await self.log_step(f"Received Trigger: {event_description}")
        
        # 1. Semantic Trigger & MCP Vector Search
        await self.log_step("Converting trigger to semantic concept...")
        vector = await self.get_embedding(event_description)
        raw_inventory = await self.run_vector_search_mcp(vector, event_description)
        
        in_stock_inventory = [item for item in raw_inventory if item.get('stock_count', 0) > 0]
        if not in_stock_inventory:
            await self.log_step("Stock verification failed: Stock count zero.")
            return None

        top_match = in_stock_inventory[0]
        if '_id' in top_match:
            top_match['_id'] = str(top_match['_id'])
            
        await self.log_step(f"Top Semantic Match: {top_match.get('name')} (Stock: {top_match.get('stock_count')})")
        
        # 2. Dynamic Pricing Engine
        pricing_data = await self.calculate_dynamic_price(top_match, event_description)
        new_price = pricing_data["new_price"]
        await self.log_step(f"Surge Price set to ${new_price}. Reasoning: {pricing_data['reasoning']}")
        
        # Update MongoDB with new price
        client = MongoClient(MONGO_URI)
        db = client.get_database("demandsync_db")
        collection = db.get_collection("local_inventory")
        collection.update_one(
            {"item_id": top_match["item_id"]},
            {"$set": {"dynamic_price": new_price}}
        )
        top_match["dynamic_price"] = new_price
        
        # 3. Multimodal Ad Studio
        await self.log_step("Generating hyper-local ad copy with Gemini 3.1 Pro...")
        prompt = f"""
        You are an expert copywriter. A weather event is occurring: "{event_description}".
        Product: {top_match.get('name')}
        Stock: {top_match.get('stock_count')}
        Price: ${new_price}
        
        Write a short, urgent 1-2 sentence ad copy (max 150 chars). 
        Include the dynamic price and mention stock count.
        """
        ad_copy = f"Urgent! Only {top_match.get('stock_count')} left. Grab your {top_match.get('name')} now for ${new_price}!"
        if self.ai_client:
            try:
                response = self.ai_client.models.generate_content(model='gemini-3.1-pro-preview', contents=prompt)
                ad_copy = response.text.strip()
            except Exception as e:
                await self.log_step(f"Gemini API Error: {e}")
                
        await self.log_step(f"Generated Copy: {ad_copy}")
        image_b64 = await self.generate_ad_creative(top_match.get('name'), event_description)
        
        # 4 & 5 handled in the simulate_viral_sales endpoint in main.py, 
        # but we return the campaign details first.
        return {
            "item_id": top_match["item_id"],
            "copy": ad_copy,
            "image_b64": image_b64,
            "zip_code": "10018",
            "item": top_match,
            "current_price": new_price,
            "pricing_reasoning": pricing_data["reasoning"],
            "remaining_stock": top_match.get('stock_count')
        }

    async def execute_viral_sales(self, item_id: str):
        # 4. Simulate viral sales reducing stock to 0
        await self.log_step("Viral Sales Simulation initiated...")
        client = MongoClient(MONGO_URI)
        db = client.get_database("demandsync_db")
        collection = db.get_collection("local_inventory")
        
        item = collection.find_one({"item_id": item_id})
        if not item:
            return None
            
        stock = item.get("stock_count", 0)
        
        # Simulate rapidly decreasing stock
        for i in range(stock, -1, -1):
            collection.update_one({"item_id": item_id}, {"$set": {"stock_count": i}})
            await self.log_step(f"Stock decremented -> {i}")
            await asyncio.sleep(0.5) # Simulate speed
            
        # 5. Supply Chain Actuation
        await self.log_step("Stock simulation cycle completed.")
        po = self.generate_supplier_purchase_order(item_id, 100)
        await self.log_step(f"Purchase order {po['po_number']} transmitted.")
        
        return po
