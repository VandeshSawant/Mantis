import os
import json
import yaml
import requests

from core.app_profile import AppProfile

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"

# Generic engine behavior — applies to ANY app. No app-specific facts belong here.
ENGINE_RULES = """You are a test step generator for a mobile app QA automation framework built on Appium.

Your job: convert a plain English test goal into a structured YAML-style list of test steps.

## Available Actions (use ONLY these action types)
- launch_app: no target needed
- wait: requires "value" (seconds, as string or number)
- tap: requires "target" with "by" and "value"
- type: requires "target" and "value" (only use for real text fields)
- tap_digit_sequence: requires "value" (a numeric string) — use this ONLY if the app's behavioral notes say it uses a custom keypad for numeric input
- swipe_up: no target needed
- verify_text: requires "target" and "expected"
- verify_element_exists: requires "target" only

## Locator types for "by" field
- "id": Android resource-id
- "text": exact visible text on screen (uses UiSelector text match)
- "accessibility": accessibility id / content-desc
- "xpath": full XPath when more precision is needed (e.g. disambiguating elements that share an id)

## Rules
1. Prefer known elements and locators listed in the app profile below. If a screen/element isn't listed, infer a reasonable locator based on naming patterns you see in the known elements. Make your best guess — it's okay to be wrong, a self-healing step will attempt to correct it at runtime if it fails.
2. Follow any behavioral notes for this app exactly — they describe quirks that aren't obvious from element names alone.
3. Always include a "wait" step (1-2 sec) after navigation actions that open a new screen or picker.
4. Each step must have a clear, human-readable "description".
5. Add a "verify_text" or "verify_element_exists" step at the end to confirm the goal was achieved, when reasonable.
6. Output ONLY valid YAML. No markdown fences, no explanation, no preamble.

## Output Format
flow_name: <short title>
description: <one sentence>
steps:
  - action: <action>
    description: <description>
    target:
      by: <locator type>
      value: <locator value>
    value: <only if applicable>
    expected: <only if applicable>
"""


class FlowParser:
    def __init__(self, api_key=None, profile_path="config/app_profile.yaml"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set. Set it as an environment variable.")
        self.profile = AppProfile(profile_path)

    def _build_system_prompt(self):
        return f"{ENGINE_RULES}\n\n## App Profile\n{self.profile.render_for_prompt()}"

    def parse(self, goal_text, save_path=None):
        """
        Convert plain English goal into structured YAML steps using Gemini.
        Returns parsed dict (flow_name, description, steps).
        """
        system_prompt = self._build_system_prompt()
        prompt = f"{system_prompt}\n\nGenerate test steps for this goal:\n\n{goal_text}"

        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key,
        }

        response = requests.post(GEMINI_URL, headers=headers, json=payload)
        if not response.ok:
            print(f"\n⚠️  Gemini API error {response.status_code}:")
            print(response.text)
        response.raise_for_status()
        data = response.json()

        try:
            raw_yaml = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected Gemini response format:\n{json.dumps(data, indent=2)}")

        if raw_yaml.startswith("```"):
            raw_yaml = raw_yaml.split("```")[1]
            if raw_yaml.startswith("yaml"):
                raw_yaml = raw_yaml[4:]
        raw_yaml = raw_yaml.strip()

        try:
            flow = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as e:
            raise ValueError(f"Gemini generated invalid YAML:\n{raw_yaml}\n\nError: {e}")

        if save_path:
            with open(save_path, "w") as f:
                f.write(raw_yaml)
            print(f"📝 Flow saved to: {save_path}")

        return flow