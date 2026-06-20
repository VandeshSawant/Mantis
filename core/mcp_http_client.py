"""
Alternative MCP client that uses stdio communication without the mcp package.
"""

import json
import subprocess
import asyncio
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPAppiumClient:
    """
    Client for Appium MCP server using direct stdio communication.
    """

    def __init__(
        self,
        android_home: Optional[str] = None,
        ai_vision_enabled: bool = True,
        ai_vision_api_base_url: Optional[str] = None,
        ai_vision_api_key: Optional[str] = None,
    ):
        self.android_home = android_home
        self.ai_vision_enabled = ai_vision_enabled
        self.ai_vision_api_base_url = ai_vision_api_base_url
        self.ai_vision_api_key = ai_vision_api_key
        self.process = None
        self.session_id: Optional[str] = None
        self._connected = False
        self._request_id = 0

    def _build_env(self) -> dict:
        env = os.environ.copy()
        if self.android_home:
            env["ANDROID_HOME"] = self.android_home
        if self.ai_vision_enabled:
            env["AI_VISION_ENABLED"] = "true"
            if self.ai_vision_api_base_url:
                env["AI_VISION_API_BASE_URL"] = self.ai_vision_api_base_url
            if self.ai_vision_api_key:
                env["AI_VISION_API_KEY"] = self.ai_vision_api_key
        env["NO_UI"] = "true"
        return env

    async def connect(self) -> None:
        """Start the MCP server subprocess and initialize."""
        cmd = ["npx", "-y", "appium-mcp@latest"]
        env = self._build_env()

        logger.info("Starting Appium MCP server...")
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )

        # Initialize connection
        await self._send_request("initialize", {
            "protocolVersion": "0.1.0",
            "clientInfo": {"name": "mantis-explorer"},
            "capabilities": {},
        })
        self._connected = True
        logger.info("Connected to Appium MCP server")

    async def _send_request(self, method: str, params: Dict) -> Dict:
        """Send JSON-RPC request and wait for response."""
        if not self.process:
            raise RuntimeError("MCP server not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        # Read response
        response_line = await asyncio.get_event_loop().run_in_executor(
            None, self.process.stdout.readline
        )
        if not response_line:
            raise RuntimeError("MCP server closed connection")

        response = json.loads(response_line)
        if "error" in response:
            raise Exception(f"MCP error: {response['error']}")

        return response.get("result", {})

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self._connected:
            raise RuntimeError("MCP client not connected")

        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        # Extract content
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "{}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
        return result

    async def create_session(self, platform: str = "android", app_path: Optional[str] = None, capabilities: Optional[Dict[str, Any]] = None) -> str:
        """Create a new Appium session."""
        cap = capabilities or {}
        if app_path:
            cap["appium:app"] = app_path
        if platform == "android":
            cap.setdefault("appium:deviceName", "Android Device")
            cap.setdefault("appium:platformVersion", "11.0")
            cap.setdefault("appium:automationName", "UiAutomator2")

        result = await self.call_tool("appium_session_management", {
            "platform": platform,
            "capabilities": cap,
        })
        self.session_id = result.get("sessionId")
        return self.session_id

    async def delete_session(self, session_id: Optional[str] = None) -> None:
        await self.call_tool("appium_session_management", {
            "action": "delete",
            "sessionId": session_id or self.session_id,
        })

    async def get_page_source(self, session_id: Optional[str] = None) -> str:
        result = await self.call_tool("appium_get_page_source", {
            "sessionId": session_id or self.session_id
        })
        return result.get("pageSource", "")

    async def get_screenshot(self, session_id: Optional[str] = None) -> str:
        result = await self.call_tool("appium_screenshot", {
            "sessionId": session_id or self.session_id
        })
        return result.get("screenshotPath", "")

    async def find_element(self, strategy: str, selector: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        return await self.call_tool("appium_find_element", {
            "sessionId": session_id or self.session_id,
            "strategy": strategy,
            "selector": selector,
        })

    async def tap(self, element_uuid: Optional[str] = None, x: Optional[int] = None, y: Optional[int] = None, session_id: Optional[str] = None) -> None:
        args = {"sessionId": session_id or self.session_id, "action": "tap"}
        if element_uuid:
            args["elementUUID"] = element_uuid
        elif x is not None and y is not None:
            args["x"] = x
            args["y"] = y
        else:
            raise ValueError("Either element_uuid or (x, y) must be provided")
        await self.call_tool("appium_gesture", args)

    async def disconnect(self) -> None:
        if self.process:
            self.process.stdin.close()
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self._connected = False
            logger.info("Disconnected from MCP server")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()