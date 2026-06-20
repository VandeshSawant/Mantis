import asyncio
import logging
from core.mcp_client import MCPAppiumClient

logging.basicConfig(level=logging.INFO)

async def test():
    async with MCPAppiumClient(android_home="C:\\AndroidSDK") as client:
        print("✅ Connected to Appium MCP server")
        
        # List tools (to verify)
        result = await client.call_tool("tools/list", {})
        tools = result.get("tools", [])
        print(f"✅ Found {len(tools)} tools")
        for tool in tools[:5]:
            print(f"  - {tool.get('name')}")
        
        # Try to create a session (without app, just to see if Appium starts)
        # This may fail if no device/emulator is available, but we'll catch it.
        try:
            session_id = await client.create_session(platform="android")
            print(f"✅ Created session: {session_id}")
            await client.delete_session(session_id)
            print("✅ Deleted session")
        except Exception as e:
            print(f"❌ Session creation failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())