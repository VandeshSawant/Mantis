import asyncio
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.WARNING)  # Reduce noise

async def test():
    env = {
        "ANDROID_HOME": "C:\\AndroidSDK",
        "NO_UI": "true"
    }

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "appium-mcp@latest"],
        env=env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Connected to Appium MCP server")

            # Use the proper list_tools method
            result = await session.list_tools()
            print(f"✅ Found {len(result.tools)} tools")
            for tool in result.tools[:5]:
                print(f"  - {tool.name}")

if __name__ == "__main__":
    asyncio.run(test())