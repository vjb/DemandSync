# DemandSync
Autonomous Retail Orchestration and Dynamic Margin Optimization

DemandSync is an autonomous retail orchestration application. The system implements a pipeline combining MongoDB Atlas Vector Search, Google Cloud Agent Builder, Gemini 1.5 Pro, and Imagen 3.0 to execute semantic inventory matching, dynamic margin optimization, localized deployment, and supply chain replenishment.

## Architecture and Execution Flow

1. Semantic Triggering: The pipeline accepts event descriptions via HTTP requests. A vector representation is computed using text-embedding-004 and matched against the local_inventory collection via a MongoDB Atlas Vector Search index.
2. Compliance Check: The system queries a Google Cloud Agent Builder unstructured Data Store to retrieve the corporate pricing policy.
3. Dynamic Price Adjustment: The system queries a generative model to compute a margin-optimized price based on stock scarcity, external event severity, and the retrieved corporate pricing policy. The primary database is mutated synchronously to reflect the adjusted price.
4. Multimodal Payload Generation: The system synthesizes text copy mapping to the current stock level and initiates parallel asynchronous API requests to Imagen 3.0 for visual asset rendering.
5. Sales Simulation: A localized simulation sequentially decrements the integer state of stock_count toward zero.
6. Supply Chain Actuation: Conditional logic triggers a mock supplier API JSON transmission precisely when stock_count reaches zero.

## Step 0: Environment Configuration

You must duplicate .env.example into a local .env file and populate all variables prior to running any installation or execution commands.

```bash
cp .env.example .env
```

## Step 1: Database Setup

The database requires an active vector search index mapping to the embedding array field in the local_inventory collection. Execute the state generation module to populate the primary database with retail data.

```bash
python db_setup.py
```

## Step 2: Application Execution

Execute the FastAPI application:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Navigate to http://localhost:8000 to interact with the frontend visualization dashboard.

## Known Limitations and Future Work

* Synchronous Generation Constraints: Currently, the system relies on blocking HTTP calls to the Google GenAI API for text synthesis. Production requires an asynchronous event-driven polling mechanism to prevent event loop saturation.
* Supply Chain Isolation: The generate_supplier_purchase_order logic currently outputs to local standard output. Production integration requires an established messaging queue (e.g., Apache Kafka or AWS SQS) for external ledger synchronization.
* Hardcoded Geospatial Boundaries: The current implementation utilizes a fixed geographic coordinate for all vector search queries. A production implementation must map the event description to a dynamically generated coordinate.
