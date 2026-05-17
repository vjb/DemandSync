# DemandSync

DemandSync is an autonomous retail orchestration gateway. The system implements a pipeline combining MongoDB Atlas Vector Search, Gemini 3.1 Pro, and Imagen 3.0 to execute semantic inventory matching, dynamic margin optimization, localized deployment, and autonomous supply chain replenishment.

## Architecture and Execution Flow

1. **Semantic Triggering:** The pipeline accepts event descriptions via HTTP requests. A vector representation is computed using `gemini-embedding-2` and matched against the `local_inventory` collection via the official `@mongodb/mcp` Server protocol.
2. **Dynamic Price Adjustment:** The system queries a generative model to compute a margin-optimized price based on stock scarcity and external event severity. The database is mutated synchronously to reflect the adjusted float.
3. **Multimodal Payload Generation:** The system synthesizes text copy mapping to the current stock level and initiates an API request to `imagen-3.0-generate-001` for conditional visual asset rendering.
4. **Sales Simulation:** A localized mock routine sequentially decrements the integer state of `stock_count` toward zero.
5. **Supply Chain Actuation:** Conditional logic triggers a mock supplier API JSON transmission precisely when `stock_count == 0` is reached, simulating an automated purchase order.

## Setup and Initialization

### Step 0: Environment Configuration

You must duplicate `.env.example` into a local `.env` file and populate all variables prior to running any installation or execution commands.

```bash
cp .env.example .env
```

### Step 1: Database Setup

The database requires an active vector search index mapping to the `embedding` array field in the `local_inventory` collection.

Execute the state generation module to populate placeholder retail data:
```bash
python db_setup.py
```

### Step 2: Application Execution

Execute the FastAPI gateway:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
Navigate to `http://localhost:8000` to interact with the frontend visualization dashboard.

## Known Limitations & Future Work

* **Synchronous Generation Constraints:** Currently, the system relies on blocking HTTP calls to the Google GenAI API for image synthesis. Production requires an asynchronous event-driven polling mechanism to prevent event loop saturation.
* **NPM Dependency Resolution:** The implementation relies on local subprocess invocation of `@mongodb/mcp`. Future iterations require a containerized, resilient service layer to mitigate local path execution errors.
* **Supply Chain Isolation:** The mock `generate_supplier_purchase_order` logic currently outputs to local stdout. Production integration requires an established messaging queue (e.g., Apache Kafka or AWS SQS) for robust external ledger synchronization.
