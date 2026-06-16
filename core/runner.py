from core.healer import SelfHealer
import time
from anyio import value
import yaml
import os
from datetime import datetime
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class TestRunner:
    def __init__(self, device_key="android_emulator", config_path="config/devices.yaml", enable_healing=True):
        self.driver = None
        self.device_key = device_key
        self.config = self._load_config(config_path)
        self.results = []
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshot_dir = f"reports/screenshots/{self.run_id}"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.enable_healing = enable_healing
        self.healer = SelfHealer() if enable_healing else None
        self.healed_steps = []   # tracks which steps got healed, for YAML auto-update

    def _load_config(self, config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

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
            "id":             AppiumBy.ID,
            "xpath":          AppiumBy.XPATH,
            "text":           AppiumBy.ANDROID_UIAUTOMATOR,
            "class":          AppiumBy.CLASS_NAME,
            "accessibility":  AppiumBy.ACCESSIBILITY_ID,
        }

        # Special handling for text-based search
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

    def execute_step(self, step):
        """Execute a single test step and return result."""
        action = step.get("action")
        target = step.get("target", {})
        value = step.get("value", "")
        description = step.get("description", action)
        expected = step.get("expected", "")

        print(f"\n▶ Step: {description}")

        result = {
            "step": description,
            "action": action,
            "expected": expected,
            "status": "pass",
            "error": None,
            "screenshot": None,
        }

        try:
            if action == "launch_app":
                self.driver.activate_app(
                    self.config["devices"][self.device_key]["app_package"]
                )
                time.sleep(2)

            elif action == "tap":
                element = self.find_element(target["by"], target["value"])
                element.click()
                time.sleep(1)

            elif action == "type":
                element = self.find_element(target["by"], target["value"])
                element.clear()
                element.send_keys(value)
                time.sleep(0.5)

            elif action == "swipe_up":
                size = self.driver.get_window_size()
                self.driver.swipe(
                    size["width"] // 2, size["height"] * 0.7,
                    size["width"] // 2, size["height"] * 0.3,
                    duration=500
                )
                time.sleep(1)

            elif action == "wait":
                time.sleep(int(value))

            elif action == "verify_text":
                element = self.find_element(target["by"], target["value"])
                actual_text = element.text
                if expected.lower() not in actual_text.lower():
                    raise AssertionError(
                        f"Expected '{expected}' but found '{actual_text}'"
                    )

            elif action == "verify_element_exists":
                self.find_element(target["by"], target["value"])
                
            elif action == "tap_digit_sequence":
              # value is a string like "5000", tap each digit button
              for digit in str(value):
                  btn_text = f"{digit}"
                  element = self.find_element("text", btn_text)
                  element.click()
                  time.sleep(0.2)
                  
            else:
                raise ValueError(f"Unknown action: {action}")

            screenshot = self.take_screenshot(description)
            result["screenshot"] = screenshot
            print(f"  ✅ Passed")

        except (TimeoutException, NoSuchElementException) as e:
            print(f"  ⚠️  Locator failed: {target.get('value', '')}. Attempting self-heal...")

            healed = False
            if self.enable_healing and action in ("tap", "type", "verify_text", "verify_element_exists"):
                try:
                    page_source = self.get_page_source()
                    suggestion = self.healer.heal(step, page_source)

                    if suggestion.get("found"):
                        new_by = suggestion["by"]
                        new_value = suggestion["value"]
                        print(f"  🩹 Healer suggests: by={new_by}, value={new_value} ({suggestion.get('reasoning','')})")

                        try:
                            element = self.find_element(new_by, new_value)
                            if action == "tap":
                                element.click()
                            elif action == "type":
                                element.clear()
                                element.send_keys(value)
                            elif action == "verify_text":
                                actual_text = element.text
                                if expected.lower() not in actual_text.lower():
                                    raise AssertionError(f"Expected '{expected}' but found '{actual_text}'")
                            # verify_element_exists just needed the find to succeed

                            time.sleep(1)
                            healed = True

                            # Record the healed locator so we can update the YAML afterward
                            self.healed_steps.append({
                                "description": description,
                                "old_by": target.get("by"),
                                "old_value": target.get("value"),
                                "new_by": new_by,
                                "new_value": new_value,
                            })

                            result["status"] = "pass"
                            result["error"] = None
                            result["healed"] = True
                            result["healed_reasoning"] = suggestion.get("reasoning", "")
                            screenshot = self.take_screenshot(description)
                            result["screenshot"] = screenshot
                            print(f"  ✅ Passed after self-healing")

                        except Exception as retry_error:
                            print(f"  ❌ Healing attempt also failed: {retry_error}")

                    else:
                        print(f"  ❌ Healer could not find a match: {suggestion.get('reasoning','')}")

                except Exception as heal_error:
                    print(f"  ⚠️  Healer itself errored: {heal_error}")

            if not healed:
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
        print(f"  Run Complete: {passed}/{total} steps passed" + (f" ({len(self.healed_steps)} self-healed)" if self.healed_steps else ""))
        print(f"{'='*50}\n")

        return summary
    
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