import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient

def setup_vector_index():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("MONGO_URI not found in .env")
        return

    client = MongoClient(mongo_uri)
    db = client.get_database("demandsync_db")
    collection = db.get_collection("local_inventory")

    # Define the vector search index model
    # Note: Depending on pymongo version, create_search_index might have different signatures
    # or we might need to use the raw command.
    index_def = {
        "name": "vector_index",
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 768,
                    "similarity": "cosine"
                }
            ]
        }
    }
    
    try:
        print("Attempting to create search index via pymongo...")
        # PyMongo 4.5+ supports create_search_indexes
        from pymongo.operations import SearchIndexModel
        model = SearchIndexModel(
            definition=index_def["definition"],
            name=index_def["name"],
            type="vectorSearch"
        )
        res = collection.create_search_index(model)
        print("Search index creation response:", res)
    except Exception as e:
        print("PyMongo native method failed:", e)
        print("Trying raw db command...")
        try:
            res = db.command({
                "createSearchIndexes": "local_inventory",
                "indexes": [index_def]
            })
            print("Raw command response:", res)
        except Exception as e2:
            print("Raw command failed too:", e2)

if __name__ == "__main__":
    setup_vector_index()
