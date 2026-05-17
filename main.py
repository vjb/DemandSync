import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from demandsync_v2_agent import DemandSyncV2Agent
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="DemandSync API")

os.makedirs("static", exist_ok=True)
os.makedirs("static/assets", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class TriggerRequest(BaseModel):
    event_description: str

class SimulateSalesRequest(BaseModel):
    item_id: str

class RefineRequest(BaseModel):
    item_id: str
    refinement: str

log_queue = asyncio.Queue()

async def update_callback(message: str, data=None):
    payload = {"message": message}
    if data:
        payload["data"] = data
    await log_queue.put(json.dumps(payload))

agent = DemandSyncV2Agent(update_callback=update_callback)

@app.post("/api/trigger")
async def trigger_event(req: TriggerRequest):
    asyncio.create_task(run_agent_flow(req.event_description))
    return {"status": "started"}

@app.post("/api/simulate_sales")
async def simulate_sales(req: SimulateSalesRequest):
    asyncio.create_task(run_viral_sales(req.item_id))
    return {"status": "simulating"}

@app.post("/api/refine")
async def refine_campaign(req: RefineRequest):
    asyncio.create_task(run_refine_flow(req.item_id, req.refinement))
    return {"status": "started"}

async def run_refine_flow(item_id: str, refinement: str):
    await log_queue.put(json.dumps({"message": f"[INFO] Copilot refinement initiated: {refinement}"}))
    result = await agent.handle_refinement(item_id, refinement)
    if result:
        await log_queue.put(json.dumps({
            "message": "[INFO] Ad payload generated and deployed.",
            "campaign": result
        }))

async def run_agent_flow(event_description: str):
    await log_queue.put(json.dumps({"message": "[INFO] Agent flow sequence initiated."}))
    result = await agent.handle_environmental_trigger(event_description)
    
    if result:
        await log_queue.put(json.dumps({
            "message": "[INFO] Ad payload generated and deployed.",
            "campaign": result
        }))
    else:
        await log_queue.put(json.dumps({
            "message": "[WARN] Agent sequence aborted: No semantic match or stock zero."
        }))

async def run_viral_sales(item_id: str):
    await log_queue.put(json.dumps({"message": "[INFO] Sales simulation loop initiated."}))
    po = await agent.execute_viral_sales(item_id)
    if po:
        await log_queue.put(json.dumps({
            "message": "[INFO] Supply chain actuation event completed.",
            "po": po
        }))

@app.post("/api/webhook/supplier")
async def supplier_webhook(req: Request):
    data = await req.json()
    await log_queue.put(json.dumps({
        "message": f"[EXTERNAL WEBHOOK] Supplier API received PO {data.get('po_number')} for {data.get('quantity')} units."
    }))
    return {"status": "received", "ledger_id": os.urandom(4).hex()}

@app.get("/api/logs")
async def stream_logs(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                log_msg = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                yield {
                    "event": "message",
                    "data": log_msg
                }
            except asyncio.TimeoutError:
                yield {
                    "event": "ping",
                    "data": "keepalive"
                }

    return EventSourceResponse(event_generator())

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
