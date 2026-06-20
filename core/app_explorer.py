# core/app_explorer.py
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from .mcp_client import MCPAppiumClient

logger = logging.getLogger(__name__)

class UIElement:
    def __init__(self, semantic_name: str, strategy: str, value: str, element_type: str = "container"):
        self.semantic_name = semantic_name
        self.strategy = strategy
        self.value = value
        self.element_type = element_type

class AppExplorer:
    def __init__(
        self,
        android_home: str = "C:\\AndroidSDK",
        ai_vision_enabled: bool = False,
        ai_vision_api_base_url: Optional[str] = None,
        ai_vision_api_key: Optional[str] = None,
    ):
        self.android_home = android_home
        self.ai_vision_enabled = ai_vision_enabled
        self.ai_vision_api_base_url = ai_vision_api_base_url
        self.ai_vision_api_key = ai_vision_api_key
        self.screens: Dict[str, List[UIElement]] = {}
        self.visited = set()

    async def explore(self, app_path: str, max_screens: int = 10) -> Dict[str, Any]:
        async with MCPAppiumClient(
            android_home=self.android_home,
            ai_vision_enabled=self.ai_vision_enabled,
            ai_vision_api_base_url=self.ai_vision_api_base_url,
            ai_vision_api_key=self.ai_vision_api_key,
        ) as client:
            # Adjust capabilities to match your device/emulator
            session_id = await client.create_session(
                platform="android",
                app_path=app_path,
                capabilities={
                    "appium:deviceName": "emulator-5554",   # Change if needed
                    "appium:platformVersion": "16",         # Change to your API level
                    "appium:automationName": "UiAutomator2",
                }
            )
            logger.info(f"Session created: {session_id}")

            # Start exploring
            await self._explore_screen(client, session_id, "initial", 0, max_screens)

            profile = self._generate_profile()
            flows = self._generate_flows()
            return {"profile": profile, "flows": flows}

    async def _explore_screen(self, client, session_id, screen_name, depth, max_depth):
        if depth > max_depth or screen_name in self.visited:
            return
        self.visited.add(screen_name)
        logger.info(f"Exploring screen: {screen_name}")

        page_source = await client.get_page_source(session_id)
        screenshot_path = await client.get_screenshot(session_id)

        elements = self._parse_elements(page_source)
        self.screens[screen_name] = elements

        # Navigate to new screens via tappable elements
        tappable = [e for e in elements if e.element_type in ["button", "menu_item"]]
        for elem in tappable[:3]:
            try:
                result = await client.find_element(elem.strategy, elem.value, session_id)
                if result and "uuid" in result:
                    await client.tap(element_uuid=result["uuid"], session_id=session_id)
                    await asyncio.sleep(2)
                    new_screen = f"{screen_name}_{elem.semantic_name}"
                    await self._explore_screen(client, session_id, new_screen, depth + 1, max_depth)
                    # Go back
                    await client.call_tool("appium_gesture", {"sessionId": session_id, "action": "back"})
                    await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to navigate via {elem.semantic_name}: {e}")

    def _parse_elements(self, page_source: str) -> List[UIElement]:
        elements = []
        patterns = [
            (r'resource-id="([^"]+)"', "id"),
            (r'content-desc="([^"]+)"', "accessibility"),
            (r'text="([^"]+)"', "text"),
        ]
        for pattern, strategy in patterns:
            matches = re.findall(pattern, page_source)
            for match in matches[:10]:
                if match and not match.startswith("android:"):
                    elem_type = "button" if "button" in match.lower() else "container"
                    name = re.sub(r'[^a-zA-Z0-9_]', '_', match.lower())
                    elements.append(UIElement(name, strategy, match, elem_type))
        return elements

    def _generate_profile(self) -> Dict:
        profile = {"screens": {}}
        for screen, elements in self.screens.items():
            profile["screens"][screen] = {
                "elements": {e.semantic_name: {"by": e.strategy, "value": e.value} for e in elements}
            }
        return profile

    def _generate_flows(self) -> Dict:
        steps = [{"action": "launch_app", "description": "Launch the app"}]
        for screen, elements in self.screens.items():
            for elem in elements[:3]:
                if elem.element_type == "button":
                    steps.append({
                        "action": "tap",
                        "description": f"Tap {elem.semantic_name}",
                        "target": {"by": elem.strategy, "value": elem.value}
                    })
        return {"smoke_test": steps}