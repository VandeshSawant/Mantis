import asyncio
import logging
import json
from core.mcp_client import MCPAppiumClient

logging.basicConfig(level=logging.INFO)

async def test():
    async with MCPAppiumClient(android_home="C:\\AndroidSDK") as client:
        print("✅ Connected to Appium MCP server")

        try:
            # Create session with minimal capabilities (auto-detect device)
            session_id = await client.create_session(
                platform="android",
                capabilities={
                    "appium:deviceName": "emulator-5554",
                    "appium:platformVersion": "16",
                    "appium:automationName": "UiAutomator2",
                }
            )
            if session_id:
                print(f"✅ Session created: {session_id}")

                # Get device info
                info = await client.call_tool("appium_mobile_device_info", {
                    "sessionId": session_id,
                    "action": "info"
                })
                print(f"📱 Device info: {info}")

                # Delete session
                await client.delete_session(session_id)
                print("✅ Session deleted")
            else:
                print("❌ Session creation failed – no ID extracted.")

        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())