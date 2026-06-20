# core/mcp_client.py
import asyncio
import json
import logging
import os
import re
import shutil
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPAppiumClient:
    def __init__(
        self,
        android_home: Optional[str] = None,
        ai_vision_enabled: bool = False,
        ai_vision_api_base_url: Optional[str] = None,
        ai_vision_api_key: Optional[str] = None,
    ):
        self.android_home = android_home or os.getenv("ANDROID_HOME", "C:\\AndroidSDK")
        self.ai_vision_enabled = ai_vision_enabled
        self.ai_vision_api_base_url = ai_vision_api_base_url
        self.ai_vision_api_key = ai_vision_api_key
        self.process = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task = None
        self._initialized = False
        self.session_id: Optional[str] = None

    async def __aenter__(self):
        env = os.environ.copy()
        env["ANDROID_HOME"] = self.android_home
        env["NO_UI"] = "true"
        if self.ai_vision_enabled:
            env["AI_VISION_ENABLED"] = "true"
            if self.ai_vision_api_base_url:
                env["AI_VISION_API_BASE_URL"] = self.ai_vision_api_base_url
            if self.ai_vision_api_key:
                env["AI_VISION_API_KEY"] = self.ai_vision_api_key

        npx_path = shutil.which("npx")
        if not npx_path:
            common_paths = [
                "C:\\Program Files\\nodejs\\npx.cmd",
                "C:\\Program Files\\nodejs\\npx",
                "C:\\Users\\ADMIN\\AppData\\Roaming\\npm\\npx.cmd",
                "C:\\Users\\ADMIN\\AppData\\Roaming\\npm\\npx",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    npx_path = path
                    break
        if not npx_path:
            raise FileNotFoundError("npx not found. Install Node.js.")

        logger.info(f"Starting Appium MCP server using: {npx_path}")
        self.process = await asyncio.create_subprocess_exec(
            npx_path, "-y", "appium-mcp@latest",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())

        await self._send_request("initialize", {
            "protocolVersion": "0.1.0",
            "clientInfo": {"name": "mantis-explorer", "version": "1.0.0"},
            "capabilities": {},
        })
        self._initialized = True
        logger.info("Connected to Appium MCP server")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None
        if self._reader_task:
            self._reader_task.cancel()
        logger.info("Disconnected from MCP server")

    async def _read_stdout(self):
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                if "id" in data and data["id"] in self._pending_requests:
                    future = self._pending_requests.pop(data["id"])
                    if "error" in data:
                        future.set_exception(Exception(f"MCP error: {data['error']}"))
                    else:
                        future.set_result(data)
            except json.JSONDecodeError:
                pass

    async def _read_stderr(self):
        while True:
            line = await self.process.stderr.readline()
            if not line:
                break
            logger.debug(f"[MCP server] {line.decode('utf-8').strip()}")

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._request_id += 1
        req_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = future

        self.process.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError(f"Request {method} timed out")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Not connected.")
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        result = response.get("result", {})
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "{}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
        return result

    async def create_session(
        self,
        platform: str = "android",
        app_path: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        cap = capabilities or {}
        if app_path:
            cap["appium:app"] = app_path

        if platform == "android":
            cap.setdefault("appium:deviceName", "emulator-5554")
            cap.setdefault("appium:platformVersion", "16")
            cap.setdefault("appium:automationName", "UiAutomator2")

        cap_str = json.dumps(cap)
        result = await self.call_tool("appium_session_management", {
            "action": "create",
            "platform": platform,
            "capabilities": cap_str,
        })

        # DEBUG: log the full result to see what we got
        logger.info(f"Create session raw result: {result}")

        # Extract session ID from various possible fields
        session_id = None

        # 1. From 'text' field using regex
        text = result.get("text", "")
        match = re.search(r"ID:\s*([a-f0-9\-]+)", text, re.IGNORECASE)
        if match:
            session_id = match.group(1)
            logger.info(f"Extracted session ID from text: {session_id}")
            self.session_id = session_id
            return session_id

        # 2. From direct 'sessionId' field
        if result.get("sessionId"):
            session_id = result["sessionId"]
            logger.info(f"Extracted session ID from sessionId field: {session_id}")
            self.session_id = session_id
            return session_id

        # 3. From 'result.sessionId' (nested)
        if result.get("result", {}).get("sessionId"):
            session_id = result["result"]["sessionId"]
            logger.info(f"Extracted session ID from result.sessionId: {session_id}")
            self.session_id = session_id
            return session_id

        # 4. If nothing found, raise a clear error
        logger.error(f"Could not extract session ID from response: {result}")
        raise RuntimeError(f"Session creation failed: {result}")

    async def delete_session(self, session_id: Optional[str] = None) -> None:
        sid = session_id or self.session_id
        if sid:
            await self.call_tool("appium_session_management", {
                "action": "delete",
                "sessionId": sid,
            })

    async def get_page_source(self, session_id: Optional[str] = None) -> str:
        sid = session_id or self.session_id
        if not sid:
            raise ValueError("No session ID available.")
        result = await self.call_tool("appium_get_page_source", {
            "sessionId": sid,
        })
        return result.get("pageSource", "")

    async def get_screenshot(self, session_id: Optional[str] = None) -> str:
        sid = session_id or self.session_id
        if not sid:
            raise ValueError("No session ID available.")
        result = await self.call_tool("appium_screenshot", {
            "sessionId": sid,
        })
        return result.get("screenshotPath", "")

    async def find_element(
        self,
        strategy: str,
        selector: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sid = session_id or self.session_id
        if not sid:
            raise ValueError("No session ID available.")
        return await self.call_tool("appium_find_element", {
            "sessionId": sid,
            "strategy": strategy,
            "selector": selector,
        })

    async def tap(
        self,
        element_uuid: Optional[str] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> None:
        sid = session_id or self.session_id
        if not sid:
            raise ValueError("No session ID available.")
        args = {
            "sessionId": sid,
            "action": "tap",
        }
        if element_uuid:
            args["elementUUID"] = element_uuid
        elif x is not None and y is not None:
            args["x"] = x
            args["y"] = y
        else:
            raise ValueError("Provide either element_uuid or (x, y)")
        await self.call_tool("appium_gesture", args)