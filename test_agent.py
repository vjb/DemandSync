import asyncio
from omnicaster_agent import OmniCaster

async def main():
    agent = OmniCaster()
    result = await agent.handle_environmental_trigger("Downpour in Midtown")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
