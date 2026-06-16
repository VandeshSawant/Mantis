import os
import json
import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

HEALER_SYSTEM_PROMPT = """You are a self-healing locator assistant for a mobile UI test automation framework (Appium).

A test step just FAILED because its locator did not match any element on the current screen.
You will be given:
1. The original step's intent (description + the locator that failed)
2. The current screen's UI hierarchy (XML dump)

Your job: find the element in the XML that most likely matches the step's intent, and return a NEW locator for it.

## Output Format
Respond with ONLY valid JSON, no markdown fences, no explanation:
{
  "found": true or false,
  "by": "id" | "text" | "accessibility" | "xpath",
  "value": "<the new locator value>",
  "reasoning": "<one short sentence on why you picked this>"
}

If you cannot find any reasonable match in the XML, return:
{
  "found": false,
  "by": null,
  "value": null,
  "reasoning": "<why nothing matched>"
}

## Locator type guidance
- Prefer "id" (resource-id) if the element has one — most reliable
- Use "text" for exact visible text match
- Use "accessibility" for content-desc
- Use "xpath" only if you need to combine attributes to uniquely identify the element (e.g. same resource-id used by multiple elements, like calculator digit buttons reused for category toggles)
"""


class SelfHealer:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set.")

    def heal(self, step, page_source):
        """
        Given a failed step and the current screen's XML, ask Gemini for an alternative locator.
        Returns dict: {found, by, value, reasoning}
        """
        description = step.get("description", "")
        original_target = step.get("target", {})
        action = step.get("action", "")

        # Truncate page source if huge, to keep token usage sane
        max_chars = 12000
        if len(page_source) > max_chars:
            page_source = page_source[:max_chars] + "\n...[truncated]"

        prompt = f"""{HEALER_SYSTEM_PROMPT}

## Failed Step
Action: {action}
Description: {description}
Original locator that failed: by={original_target.get('by')}, value={original_target.get('value')}

## Current Screen XML
{page_source}
"""

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key,
        }

        response = requests.post(GEMINI_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        try:
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            return {"found": False, "by": None, "value": None, "reasoning": "Healer response malformed"}

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"found": False, "by": None, "value": None, "reasoning": f"Could not parse healer JSON: {raw_text}"}

        return result