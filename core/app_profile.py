"""
Loads config/app_profile.yaml and renders it into prompt-ready text.

This is the single place that knows how to turn the structured app profile
into text an LLM can read. parser.py and healer.py both call this instead of
hardcoding app-specific facts themselves.
"""
import yaml


class AppProfile:
    def __init__(self, profile_path="config/app_profile.yaml"):
        self.profile_path = profile_path
        self._data = self._load(profile_path)

    def _load(self, profile_path):
        with open(profile_path, "r") as f:
            return yaml.safe_load(f)

    @property
    def name(self):
        return self._data.get("app", {}).get("name", "Unknown App")

    @property
    def description(self):
        return self._data.get("app", {}).get("description", "")

    @property
    def package_ref(self):
        return self._data.get("app", {}).get("package_ref")

    @property
    def behavioral_notes(self):
        return self._data.get("behavioral_notes", [])

    @property
    def screens(self):
        return self._data.get("screens", [])

    def render_for_prompt(self):
        """
        Render the full app profile as a text block suitable for embedding
        directly into an LLM system prompt.
        """
        lines = []
        lines.append(f"App: {self.name}")
        if self.description:
            lines.append(f"Description: {self.description}")

        if self.behavioral_notes:
            lines.append("\nBehavioral notes (important quirks of this app):")
            for note in self.behavioral_notes:
                lines.append(f"- {note}")

        if self.screens:
            lines.append("\nKnown screens and elements:")
            for screen in self.screens:
                screen_name = screen.get("name", "unnamed_screen")
                screen_desc = screen.get("description", "")
                lines.append(f"\n- Screen: {screen_name}" + (f" ({screen_desc})" if screen_desc else ""))
                for element in screen.get("elements", []):
                    key = element.get("key", "unknown")
                    desc = element.get("description", "")
                    by = element.get("by", "")
                    value = element.get("value", "")
                    lines.append(f"    - {key}: {desc} | locator: by={by}, value={value}")

        return "\n".join(lines)

    def find_element(self, key):
        """Look up a known element by its key, across all screens. Returns dict or None."""
        for screen in self.screens:
            for element in screen.get("elements", []):
                if element.get("key") == key:
                    return element
        return None