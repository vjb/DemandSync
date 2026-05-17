import os
import json
from pymongo import MongoClient
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Setup environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/hackathon")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def setup_database():
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not set. Cannot generate embeddings.")
    
    # Initialize Google GenAI client
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Failed to initialize GenAI client: {e}")
        ai_client = None

    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    db = client.get_database("demandsync_db")
    
    collection = db.get_collection("local_inventory")
    
    # Clear existing data for fresh seed
    collection.delete_many({})

    mock_products = [
        {
            "item_id": "P001", "name": "Carbon-Fiber Storm Umbrella", "stock_count": 12, "price": 45.99,
            "semantic_description": "A highly durable, wind-resistant carbon-fiber umbrella designed to withstand severe thunderstorms and heavy downpours."
        },
        {
            "item_id": "P002", "name": "Lightweight Raincoat", "stock_count": 5, "price": 89.99,
            "semantic_description": "Waterproof, breathable jacket perfect for spring showers and sudden rain in the city."
        },
        {
            "item_id": "P003", "name": "Heavy Duty Snow Boots", "stock_count": 8, "price": 120.00,
            "semantic_description": "Insulated and waterproof boots with high traction, perfect for blizzard conditions and deep snow."
        },
        {
            "item_id": "P004", "name": "Thermal Winter Coat", "stock_count": 0, "price": 199.99,
            "semantic_description": "Extreme cold weather parka designed to retain body heat in freezing temperatures and snowstorms."
        },
        {
            "item_id": "P005", "name": "UV Protection Sunglasses", "stock_count": 25, "price": 150.00,
            "semantic_description": "Polarized sunglasses offering 100% UV protection, ideal for extremely sunny and hot days."
        },
        {
            "item_id": "P006", "name": "Portable Neck Fan", "stock_count": 18, "price": 25.50,
            "semantic_description": "Battery-operated wearable fan to keep you cool during extreme heat waves and humid weather."
        },
        {
            "item_id": "P007", "name": "Compact Travel Umbrella", "stock_count": 30, "price": 15.99,
            "semantic_description": "Small, easily packable umbrella for light rain and everyday carry in a bag."
        },
        {
            "item_id": "P008", "name": "Insulated Hydration Flask", "stock_count": 40, "price": 35.00,
            "semantic_description": "Double-walled vacuum water bottle keeps drinks ice-cold for 24 hours during sweltering heat."
        },
        {
            "item_id": "P009", "name": "Windbreaker Pullover", "stock_count": 14, "price": 65.00,
            "semantic_description": "Light layer to block strong winds and light drizzles on chilly autumn days."
        },
        {
            "item_id": "P010", "name": "Ice Traction Cleats", "stock_count": 22, "price": 19.99,
            "semantic_description": "Slip-on spikes for shoes to walk safely on icy sidewalks and frozen streets after a winter storm."
        },
        {
            "item_id": "P011", "name": "Waterproof Backpack Cover", "stock_count": 10, "price": 22.00,
            "semantic_description": "Protective neon cover to keep your backpack and electronics dry during torrential downpours."
        },
        {
            "item_id": "P012", "name": "Cooling Towel", "stock_count": 45, "price": 12.50,
            "semantic_description": "Evaporative cooling towel that instantly chills when soaked in water, great for heatwaves."
        },
        {
            "item_id": "P013", "name": "Heated Gloves", "stock_count": 7, "price": 85.00,
            "semantic_description": "Battery-powered heated gloves to prevent frostbite during extreme winter freezes."
        },
        {
            "item_id": "P014", "name": "Emergency Poncho", "stock_count": 100, "price": 5.99,
            "semantic_description": "Disposable, ultra-lightweight rain poncho for unexpected showers and storms."
        },
        {
            "item_id": "P015", "name": "Sunscreen SPF 50", "stock_count": 55, "price": 18.00,
            "semantic_description": "Broad-spectrum, sweat-resistant sunblock to protect skin from harsh UV rays during summer."
        },
        {
            "item_id": "P016", "name": "NY Local Team Championship Hat", "stock_count": 150, "price": 35.00,
            "semantic_description": "Limited edition championship cap for the local New York sports team victory celebration."
        },
        {
            "item_id": "P017", "name": "Home Team Jersey (Blue & Orange)", "stock_count": 20, "price": 125.00,
            "semantic_description": "Authentic local team sports jersey, highly sought after during playoffs and finals."
        },
        {
            "item_id": "P018", "name": "Pro Tennis Racket", "stock_count": 12, "price": 250.00,
            "semantic_description": "High-performance tennis racket, popular during the US Open or local tennis tournaments."
        },
        {
            "item_id": "P019", "name": "Viral Dance Studio Ring Light", "stock_count": 45, "price": 40.00,
            "semantic_description": "Portable LED ring light for social media influencers and viral pop culture dance trends."
        },
        {
            "item_id": "P020", "name": "Trending Noise-Cancelling Headphones", "stock_count": 8, "price": 299.99,
            "semantic_description": "Premium wireless headphones frequently worn by celebrities and athletes in viral moments."
        }
    ]

    for product in mock_products:
        if ai_client:
            try:
                # We try the standard embedding model
                response = ai_client.models.embed_content(
                    model='gemini-embedding-2',
                    contents=product['semantic_description'],
                )
                product['embedding'] = response.embeddings[0].values
            except Exception as e:
                print(f"Failed to generate embedding for {product['item_id']}: {e}")
                product['embedding'] = []
        else:
            product['embedding'] = []

    collection.insert_many(mock_products)
    print(f"Successfully inserted {len(mock_products)} products into local_inventory.")

if __name__ == "__main__":
    setup_database()
