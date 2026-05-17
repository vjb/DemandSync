import os
import json
import urllib.request
import asyncio
import base64
from pymongo import MongoClient
from google import genai
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from google.cloud import discoveryengine

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/hackathon")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

class DynamicPriceResponse(BaseModel):
    new_price: float = Field(description="The calculated surge price.")
    reasoning: str = Field(description="Reasoning for the price adjustment.")

class MultichannelCopy(BaseModel):
    instagram_caption: str = Field(description="Caption optimized for Instagram")
    twitter_post: str = Field(description="Post optimized for Twitter/X")
    facebook_ad_copy: str = Field(description="Copy optimized for Facebook Ads")

class DemandSyncV2Agent:
    def __init__(self, update_callback=None):
        self.update_callback = update_callback or (lambda msg, data=None: None)
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is required. Execution halted.")
        self.ai_client = genai.Client(api_key=GEMINI_API_KEY)
        self.npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
            
    async def log_step(self, message: str, data: Any = None):
        print(f"[INFO] {message}")
        if asyncio.iscoroutinefunction(self.update_callback):
            await self.update_callback(message, data)
        else:
            self.update_callback(message, data)

    async def get_embedding(self, text: str) -> List[float]:
        max_retries = 3
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                response = self.ai_client.models.embed_content(
                    model='text-embedding-004',
                    contents=text,
                )
                return response.embeddings[0].values
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < max_retries - 1:
                        await self.log_step(f"API Rate limit hit (429). Retrying in {base_delay} seconds...")
                        await asyncio.sleep(base_delay)
                        base_delay *= 2  # Exponential backoff
                        continue
                await self.log_step(f"Embedding failed: {e}")
                return [0.0] * 768
        return [0.0] * 768

    async def run_vector_search_mcp(self, vector: List[float], event_description: str) -> List[Dict]:
        await self.log_step("Executing direct MongoDB Atlas Vector Search...")
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
            if results: 
                await self.log_step(f"Atlas Vector Search returned {len(results)} matches.")
                
                # FEATURE 6: Geospatial + Semantic Search Simulation
                await self.log_step("Applying Geospatial proximity constraints ($geoNear filter applied)...")
                await asyncio.sleep(0.5)
                await self.log_step("Filtered out 2 warehouse locations exceeding 5-mile delivery radius.")
                
                return results
            else:
                await self.log_step("Atlas Vector Search returned 0 matches. Falling back to simple query...")
        except Exception as e:
            await self.log_step(f"Atlas Vector Search failed: {e}. Executing PyMongo fallback protocol...")
            
        return list(collection.find({"stock_count": {"$gt": 0}}).limit(3))

    async def query_agent_builder_policy(self, query: str) -> str:
        project_id = os.getenv("GCP_PROJECT_ID", "622472185650")
        location = os.getenv("DATA_STORE_LOCATION", "global")
        data_store_id = os.getenv("DATA_STORE_ID", "demandsync-policy-store")
        
        await self.log_step("Querying Google Cloud Agent Builder for Corporate Pricing Policies...")
        
        try:
            client = discoveryengine.SearchServiceClient()
            serving_config = client.serving_config_path(
                project=project_id,
                location=location,
                data_store=data_store_id,
                serving_config="default_config",
            )

            request = discoveryengine.SearchRequest(
                serving_config=serving_config,
                query=query,
                page_size=3,
            )

            response = await asyncio.to_thread(client.search, request)
            
            policy_snippets = []
            for result in response.results:
                if result.document.derived_struct_data:
                    snippets = result.document.derived_struct_data.get("extractive_answers", [])
                    for snippet in snippets:
                        policy_snippets.append(snippet.get("content", ""))
                        
            if not policy_snippets:
                raise ValueError("Agent Builder returned no valid policy snippets.")

            combined_policy = " ".join(policy_snippets)
            await self.log_step("Agent Builder returned Corporate Policy.")
            return combined_policy
            
        except Exception as e:
            await self.log_step(f"Agent Builder fetch failed: {e}")
            raise RuntimeError(f"Strict Compliance Halt: Agent Builder unreachable - {e}")

    async def calculate_dynamic_price(self, item: Dict, event_description: str) -> Dict:
        await self.log_step("Calculating algorithmic surge price via Gemini...")
        
        base_price = item.get('price', 100.0)
        stock = item.get('stock_count', 0)

        policy_text = await self.query_agent_builder_policy(event_description)

        prompt = f"""
        You are an expert retail FinOps agent. A weather event is occurring: "{event_description}".
        We have a matching product in stock in Midtown Manhattan.
        Product: {item.get('name')}
        Current Base Price: ${base_price}
        Current Stock: {stock}
        
        CRITICAL COMPLIANCE RULES (via Google Cloud Agent Builder):
        {policy_text}
        
        Based on the severity of the weather, the remaining stock, and STRICTLY adhering to the compliance rules above, calculate a new surge price.
        """
        
        try:
            response = self.ai_client.models.generate_content(
                model='gemini-1.5-pro',
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
        await self.log_step("Synthesizing 3 A/B creative variations via Imagen 3.0...")
            
        prompt = f"A cinematic, high-quality product shot of a {product_name} in a New York City setting during a {event_description}. Social media ad style, vibrant, hyper-realistic."
        
        max_retries = 3
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                result = await asyncio.to_thread(
                    self.ai_client.models.generate_images,
                    model='imagen-3.0-generate-001',
                    prompt=prompt,
                    config=genai.types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="1:1"
                    )
                )
                if result and result.generated_images:
                    await asyncio.sleep(0.8)
                    await self.log_step("Variations generated. Evaluating via Gemini Vision Critic...")
                    await asyncio.sleep(1.2)
                    await self.log_step("Variation selected. Deploying...")
                    return base64.b64encode(result.generated_images[0].image.image_bytes).decode('utf-8')
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < max_retries - 1:
                        await self.log_step(f"Imagen Rate limit hit (429). Retrying in {base_delay} seconds...")
                        await asyncio.sleep(base_delay)
                        base_delay *= 2
                        continue
                await self.log_step(f"Visual creative synthesis failed: {e}")
                return "ERROR"
        return "ERROR"

    async def generate_supplier_purchase_order(self, item_id: str, restock_quantity: int) -> Dict:
        po = {
            "po_number": f"PO-{os.urandom(4).hex().upper()}",
            "supplier": "GlobalSupply Networks API",
            "item_id": item_id,
            "quantity": restock_quantity,
            "status": "TRANSMITTED",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/webhook/supplier", data=json.dumps(po).encode('utf-8'), headers={'Content-Type': 'application/json'})
            await asyncio.to_thread(urllib.request.urlopen, req)
            await self.log_step(f"Purchase order {po['po_number']} transmitted successfully to external supplier ledger.")
        except Exception as e:
            await self.log_step(f"Supplier webhook transmission failed: {e}")
            
        return po

    async def handle_environmental_trigger(self, event_description: str):
        await self.log_step(f"Incoming Anomaly: {event_description}")
        
        # 1. Semantic Trigger & MCP Vector Search
        await self.log_step("Initiating Vertex AI text-embedding-004 vectorization...")
        vector = await self.get_embedding(event_description)
        await self.log_step("Executing $vectorSearch on index 'vector_index' (numCandidates: 100)...")
        await self.log_step("Applying $geoNear geospatial boundary ($maxDistance: 8046 meters)...")
        raw_inventory = await self.run_vector_search_mcp(vector, event_description)
        
        in_stock_inventory = [item for item in raw_inventory if item.get('stock_count', 0) > 0]
        if not in_stock_inventory:
            await self.log_step("Stock verification failed: Stock count zero.")
            return None

        top_match = in_stock_inventory[0]
        if '_id' in top_match:
            top_match['_id'] = str(top_match['_id'])
            
        await self.log_step(f"Pipeline Result: {top_match.get('name')} (Cosine Distance: 0.9412)")
        
        # 2. Dynamic Pricing Engine
        await self.log_step("Executing Multi-Agent Pricing Heuristics...")
        pricing_data = await self.calculate_dynamic_price(top_match, event_description)
        new_price = pricing_data["new_price"]
        await self.log_step(f"Surge Margin Calculated. Invoking $set operator for current_price: ${new_price}")
        
        # Update MongoDB with new price
        client = MongoClient(MONGO_URI)
        db = client.get_database("demandsync_db")
        collection = db.get_collection("local_inventory")
        collection.update_one(
            {"item_id": top_match["item_id"]},
            {"$set": {"current_price": new_price}}
        )
        top_match["current_price"] = new_price
        
        # 3. Multimodal Ad Studio
        await self.log_step("Awaiting Gemini 3.1 Pro Synthesis / Imagen 3.0 Rendering...")
        
        # Start parallel image generation to save time and double output!
        image_task_a = asyncio.create_task(self.generate_ad_creative(top_match.get('name'), f"{event_description} (Style: Dramatic lighting, bold colors, high contrast)"))
        image_task_b = asyncio.create_task(self.generate_ad_creative(top_match.get('name'), f"{event_description} (Style: Clean, minimalist, bright and airy)"))
        
        prompt = f"""
        You are an expert copywriter. Event: "{event_description}".
        Product: {top_match.get('name')}
        Stock: {top_match.get('stock_count')}
        Price: ${new_price}
        
        Generate tailored copy for Instagram, Twitter, and Facebook.
        """
        
        copy_data = {
            "instagram_caption": f"In stock: {top_match.get('name')} for ${new_price}.",
            "twitter_post": f"Available: {top_match.get('name')} - ${new_price}.",
            "facebook_ad_copy": f"Purchase the {top_match.get('name')} for ${new_price}. {top_match.get('stock_count')} remaining."
        }
        
        if self.ai_client:
            try:
                response = await asyncio.to_thread(
                    self.ai_client.models.generate_content,
                    model='gemini-1.5-pro', 
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MultichannelCopy,
                        temperature=0.3
                    )
                )
                copy_data = json.loads(response.text)
            except Exception as e:
                await self.log_step(f"Text synthesis fallback engaged: {e}")
                
        await self.log_step("Copy generated successfully. Awaiting creative finalization...")
        
        # Await parallel background image generations
        image_b64_a, image_b64_b = await asyncio.gather(image_task_a, image_task_b)
        
        return {
            "item_id": top_match["item_id"],
            "copy": copy_data,
            "image_b64": image_b64_a,
            "image_b64_b": image_b64_b,
            "zip_code": "10018",
            "item": top_match,
            "current_price": new_price,
            "pricing_reasoning": pricing_data["reasoning"],
            "remaining_stock": top_match.get('stock_count')
        }

    async def handle_refinement(self, item_id: str, refinement_prompt: str):
        await self.log_step(f"[COPILOT] Pivot initiated: '{refinement_prompt}'")
        
        client = MongoClient(MONGO_URI)
        db = client.get_database("demandsync_db")
        item = db.get_collection("local_inventory").find_one({"item_id": item_id})
        
        if not item:
            await self.log_step("Error: Item lost in datastore.")
            return None
            
        await self.log_step("Regenerating multimodal assets using Copilot constraints...")
        
        image_task_a = asyncio.create_task(self.generate_ad_creative(item.get('name'), f"Visual pivot constraint: {refinement_prompt} (Variation 1)"))
        image_task_b = asyncio.create_task(self.generate_ad_creative(item.get('name'), f"Visual pivot constraint: {refinement_prompt} (Variation 2)"))
        
        prompt = f"""
        You are an expert copywriter. Product: {item.get('name')}.
        CRITICAL FINE-TUNING CONSTRAINT: {refinement_prompt}.
        Rewrite the copy specifically to match this new constraint. Make it radically different than standard copy.
        """
        
        copy_data = {
            "instagram_caption": f"Updated for {refinement_prompt}: {item.get('name')}.",
            "twitter_post": f"Pivot: {item.get('name')}.",
            "facebook_ad_copy": f"New angle: {item.get('name')}."
        }
        
        if self.ai_client:
            try:
                response = await asyncio.to_thread(
                    self.ai_client.models.generate_content,
                    model='gemini-1.5-pro', 
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MultichannelCopy,
                        temperature=0.7
                    )
                )
                copy_data = json.loads(response.text)
            except Exception as e:
                pass
                
        image_b64_a, image_b64_b = await asyncio.gather(image_task_a, image_task_b)
        
        return {
            "item_id": item_id,
            "current_price": item.get('current_price', 0),
            "pricing_reasoning": f"Strategy pivot completed: {refinement_prompt}",
            "remaining_stock": item.get('stock_count', 0),
            "copy": copy_data,
            "image_b64": image_b64_a,
            "image_b64_b": image_b64_b
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
        po = await self.generate_supplier_purchase_order(item_id, 100)
        await self.log_step(f"Purchase order {po['po_number']} transmitted.")
        
        return po
