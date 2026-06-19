import time
import yaml
import os
import importlib
from datetime import datetime
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.healer import SelfHealer

# Actions where, if the element-finding part fails, self-healing is attempted.
# These are actions whose core job is "find an element by locator" - actions
# that don't take a target (like wait, launch_app) aren't healable since
# there's no locator to fix.
HEALABLE_ACTIONS = ("tap", "type", "verify_text", "verify_element_exists")


class TestRunner:
    def __init__(self, device_key="android_emulator", config_path="config/devices.yaml",
                 profile_path="config/app_profile.yaml", enable_healing=True):
        self.driver = None
        self.device_key = device_key
        self.config = self._load_config(config_path)
        self.results = []
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshot_dir = f"reports/screenshots/{self.run_id}"
        os.makedirs(self.screenshot_dir, exist_ok=True)

        self.enable_healing = enable_healing
        self.healer = SelfHealer(profile_path=profile_path) if enable_healing else None
        self.healed_steps = []

        self.actions = self._load_actions()

        self._current_flow_name = None
        self._current_flow_description = None

    def _load_config(self, config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _load_actions(self):
        """Auto-discover every action module in core/actions/. Each module
        must define a run(runner, step) function. The action's name is its
        filename (without .py)."""
        actions = {}
        actions_dir = os.path.join(os.path.dirname(__file__), "actions")
        for filename in sorted(os.listdir(actions_dir)):
            if filename.endswith(".py") and not filename.startswith("_"):
                action_name = filename[:-3]
                module = importlib.import_module(f"core.actions.{action_name}")
                if not hasattr(module, "run"):
                    raise ImportError(
                        f"core/actions/{filename} does not define a run(runner, step) function"
                    )
                actions[action_name] = module.run
        return actions

    def connect(self):
        """Connect to Appium server and launch the app."""
        device_caps = self.config["devices"][self.device_key]
        server = self.config["server"]
        server_url = f"{server['url']}:{server['port']}"

        options = UiAutomator2Options()
        for key, value in device_caps.items():
            options.set_capability(key, value)

        print(f"Connecting to Appium at {server_url}...")
        self.driver = webdriver.Remote(server_url, options=options)
        self.driver.implicitly_wait(10)
        print("Connected. App launched.")

    def disconnect(self):
        """Close the Appium session."""
        if self.driver:
            self.driver.quit()
            print("Session closed.")

    def take_screenshot(self, step_name):
        """Take a screenshot and save it."""
        filename = f"{self.screenshot_dir}/{step_name.replace(' ', '_')}.png"
        self.driver.save_screenshot(filename)
        return filename

    def get_page_source(self):
        """Return the current screen's UI hierarchy as XML."""
        try:
            return self.driver.page_source
        except Exception as e:
            return f"<error getting page source: {e}>"

    def find_element(self, by, value, timeout=10):
        """Wait for an element and return it."""
        by_map = {
            "id":            AppiumBy.ID,
            "xpath":         AppiumBy.XPATH,
            "text":          AppiumBy.ANDROID_UIAUTOMATOR,
            "class":         AppiumBy.CLASS_NAME,
            "accessibility": AppiumBy.ACCESSIBILITY_ID,
        }

        if by == "text":
            locator = (
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().text("{value}")'
            )
        else:
            locator = (by_map.get(by, AppiumBy.ID), value)

        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(locator)
        )

    def _attempt_heal(self, step):
        """
        Try to recover a failed step by asking the healer for a new locator
        and retrying once. Returns True if the retry succeeded, False otherwise.
        Mutates step['target'] in place on success (caller is responsible for
        persisting that back to the YAML file).
        """
        action = step.get("action")
        target = step.get("target", {})
        description = step.get("description", action)
        value = step.get("value", "")
        expected = step.get("expected", "")

        print(f"  ⚠️  Locator failed: {target.get('value', '')}. Attempting self-heal...")

        try:
            page_source = self.get_page_source()
            suggestion = self.healer.heal(step, page_source)
        except Exception as heal_error:
            print(f"  ⚠️  Healer itself errored: {heal_error}")
            return False

        if not suggestion.get("found"):
            print(f"  ❌ Healer could not find a match: {suggestion.get('reasoning', '')}")
            return False

        new_by = suggestion["by"]
        new_value = suggestion["value"]
        print(f"  🩹 Healer suggests: by={new_by}, value={new_value} ({suggestion.get('reasoning', '')})")

        healed_step = dict(step)
        healed_step["target"] = {"by": new_by, "value": new_value}

        try:
            self.actions[action](self, healed_step)
        except Exception as retry_error:
            print(f"  ❌ Healing attempt also failed: {retry_error}")
            return False

        time.sleep(1)

        # Mutate the original step so the caller can persist this to YAML
        step["target"] = {"by": new_by, "value": new_value}

        self.healed_steps.append({
            "description": description,
            "old_by": target.get("by"),
            "old_value": target.get("value"),
            "new_by": new_by,
            "new_value": new_value,
        })
        return True

    def execute_step(self, step):
        """Execute a single test step (dispatched to core/actions/) and return result."""
        action = step.get("action")
        target = step.get("target", {})
        expected = step.get("expected", "")
        description = step.get("description", action)

        print(f"\n▶ Step: {description}")

        result = {
            "step": description,
            "action": action,
            "expected": expected,
            "status": "pass",
            "error": None,
            "screenshot": None,
            "healed": False,
            "healed_reasoning": None,
        }

        if action not in self.actions:
            result["status"] = "fail"
            result["error"] = f"Unknown action: {action}"
            result["screenshot"] = self.take_screenshot(f"FAIL_{description}")
            print(f"  ❌ Failed — {result['error']}")
            self.results.append(result)
            return result

        try:
            self.actions[action](self, step)

            screenshot = self.take_screenshot(description)
            result["screenshot"] = screenshot
            print(f"  ✅ Passed")

        except (TimeoutException, NoSuchElementException) as e:
            healed = False
            if self.enable_healing and action in HEALABLE_ACTIONS:
                healed = self._attempt_heal(step)

            if healed:
                result["status"] = "pass"
                result["healed"] = True
                healed_entry = self.healed_steps[-1] if self.healed_steps else {}
                result["healed_reasoning"] = healed_entry.get("reasoning", "")
                result["screenshot"] = self.take_screenshot(description)
                print(f"  ✅ Passed after self-healing")
            else:
                result["status"] = "fail"
                result["error"] = f"Element not found: {target.get('value', '')}"
                result["screenshot"] = self.take_screenshot(f"FAIL_{description}")
                print(f"  ❌ Failed — {result['error']}")

        except AssertionError as e:
            result["status"] = "fail"
            result["error"] = str(e)
            result["screenshot"] = self.take_screenshot(f"FAIL_{description}")
            print(f"  ❌ Failed — {result['error']}")

        except Exception as e:
            result["status"] = "fail"
            result["error"] = str(e)
            result["screenshot"] = self.take_screenshot(f"FAIL_{description}")
            print(f"  ❌ Failed — {result['error']}")

        self.results.append(result)
        return result

    def update_yaml_with_healed_locators(self, flow_path, original_steps):
        """If any steps were healed, rewrite the YAML file with the new working locators."""
        if not self.healed_steps:
            return

        for healed in self.healed_steps:
            for step in original_steps:
                if step.get("description") == healed["description"]:
                    step["target"]["by"] = healed["new_by"]
                    step["target"]["value"] = healed["new_value"]

        flow_data = {
            "flow_name": self._current_flow_name,
            "description": self._current_flow_description,
            "steps": original_steps,
        }

        with open(flow_path, "w") as f:
            yaml.dump(flow_data, f, sort_keys=False, default_flow_style=False)

        print(f"\n🔧 YAML auto-updated with {len(self.healed_steps)} healed locator(s): {flow_path}")

    def run_flow(self, steps, flow_path=None, flow_name=None, flow_description=None):
        """Run a full list of steps and return summary."""
        print(f"\n{'='*50}")
        print(f"  Starting Test Run: {self.run_id}")
        print(f"{'='*50}")

        self._current_flow_name = flow_name
        self._current_flow_description = flow_description

        self.connect()

        try:
            for step in steps:
                result = self.execute_step(step)
                if result["status"] == "fail":
                    print(f"\n⚠️  Step failed. Stopping run.")
                    break
        finally:
            self.disconnect()

        if flow_path:
            self.update_yaml_with_healed_locators(flow_path, steps)

        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = total - passed

        summary = {
            "run_id": self.run_id,
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": self.results,
            "healed_count": len(self.healed_steps),
        }

        print(f"\n{'='*50}")
        healed_note = f" ({len(self.healed_steps)} self-healed)" if self.healed_steps else ""
        print(f"  Run Complete: {passed}/{total} steps passed{healed_note}")
        print(f"{'='*50}\n")

        return summary