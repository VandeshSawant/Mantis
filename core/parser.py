import os
import json
import yaml
import requests

SYSTEM_PROMPT = """You are a test step generator for a mobile app QA automation framework built on Appium.

Your job: convert a plain English test goal into a structured YAML-style list of test steps.

## App Context
Package: com.raha.app.mymoney.free
This is an expense management app. Known screens and elements:

- Home screen: has an "Add new record" button (accessibility id: "Add new record")
- Add record screen: has INCOME/EXPENSE/TRANSFER toggle buttons
  - Income toggle: xpath //android.widget.CompoundButton[@resource-id='com.raha.app.mymoney.free:id/btn_1' and @text='INCOME']
  - Expense toggle: xpath //android.widget.CompoundButton[@resource-id='com.raha.app.mymoney.free:id/btn_2' and @text='EXPENSE']
  - Account button: id com.raha.app.mymoney.free:id/btn_from
  - Category button: id com.raha.app.mymoney.free:id/btn_to
  - Note field: id com.raha.app.mymoney.free:id/et_note
  - Amount display: id com.raha.app.mymoney.free:id/tv_display
  - Calculator buttons: id com.raha.app.mymoney.free:id/btn_0 through btn_9, btn_c (clear), btn_equal
  - Save button: id com.raha.app.mymoney.free:id/btn_save
  - Cancel button: id com.raha.app.mymoney.free:id/btn_cancel
  - Date field: id com.raha.app.mymoney.free:id/tv_date

## Available Actions (use ONLY these action types)
- launch_app: no target needed
- wait: requires "value" (seconds, as string or number)
- tap: requires "target" with "by" and "value"
- type: requires "target" and "value" (only use for real text fields, NOT for amount entry)
- tap_digit_sequence: requires "value" (a numeric string) — use this for entering amounts via the calculator keypad, NEVER use "type" for amounts in this app
- swipe_up: no target needed
- verify_text: requires "target" and "expected"
- verify_element_exists: requires "target" only

## Locator types for "by" field
- "id": Android resource-id (format: com.raha.app.mymoney.free:id/xxx)
- "text": exact visible text on screen (uses UiSelector text match)
- "accessibility": accessibility id / content-desc
- "xpath": full XPath when more precision is needed (e.g. disambiguating buttons that share an id)

## Rules
1. If a screen/element isn't in the known context above, infer a reasonable locator based on naming patterns you see in the known elements (e.g. likely id format is "com.raha.app.mymoney.free:id/btn_xxx" or "tv_xxx" or "et_xxx"). Make your best guess — it's okay to be wrong, the user will tell you if a step fails.
2. ALWAYS use "tap_digit_sequence" for entering money amounts, never "type" or individual digit taps.
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

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"


class FlowParser:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set. Set it as an environment variable.")

    def parse(self, goal_text, save_path=None):
        """
        Convert plain English goal into structured YAML steps using Gemini.
        Returns parsed dict (flow_name, description, steps).
        """
        prompt = f"{SYSTEM_PROMPT}\n\nGenerate test steps for this goal:\n\n{goal_text}"

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
        response.raise_for_status()
        data = response.json()

        try:
            raw_yaml = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected Gemini response format:\n{json.dumps(data, indent=2)}")

        # Strip accidental markdown fences just in case
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