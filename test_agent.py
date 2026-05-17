import asyncio
from demandsync_v2_agent import DemandSyncV2Agent

async def main():
    agent = DemandSyncV2Agent()
    result = await agent.handle_environmental_trigger("Category 4 Blizzard hitting Central Park")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
