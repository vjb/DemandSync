import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from omnicaster_agent import OmniCaster

app = FastAPI(title="OmniCaster API")

# Mount static files
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class TriggerRequest(BaseModel):
    event_description: str

# Message queue for SSE
log_queue = asyncio.Queue()

async def update_callback(message: str, data=None):
    payload = {"message": message}
    if data:
        payload["data"] = data
    await log_queue.put(json.dumps(payload))

@app.post("/api/trigger")
async def trigger_event(req: TriggerRequest):
    # Fire off agent in background so we don't block
    asyncio.create_task(run_agent_flow(req.event_description))
    return {"status": "started"}

async def run_agent_flow(event_description: str):
    agent = OmniCaster(update_callback=update_callback)
    
    # Notify start
    await log_queue.put(json.dumps({"message": "--- AGENT STARTED ---"}))
    
    result = await agent.handle_environmental_trigger(event_description)
    
    if result:
        await log_queue.put(json.dumps({
            "message": "--- AGENT COMPLETED ---",
            "campaign": result
        }))
    else:
        await log_queue.put(json.dumps({
            "message": "--- AGENT FAILED TO FIND MATCH ---"
        }))

@app.get("/api/logs")
async def stream_logs(request: Request):
    async def event_generator():
        while True:
            # If client closes connection, stop sending
            if await request.is_disconnected():
                break
                
            try:
                # Wait for next log message
                log_msg = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                yield {
                    "event": "message",
                    "data": log_msg
                }
            except asyncio.TimeoutError:
                # Keep connection alive
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
