"""
Action: tap_digit_sequence
Taps numeric keypad buttons one at a time, for apps that use a custom
on-screen calculator instead of the system keyboard for numeric input.

Step fields used:
  value - a numeric string, e.g. "5000"

Assumption: button resource-ids follow the pattern
  <app_package>:id/btn_<digit>
This is read from the connected app's package in config/devices.yaml,
not hardcoded, so this action works for any app following that id pattern.
"""
import time


def run(runner, step):
    value = str(step.get("value", ""))
    app_package = runner.config["devices"][runner.device_key]["app_package"]

    for digit in value:
        btn_text = f"{digit}"
        element = runner.find_element("text", btn_text)
        element.click()
        time.sleep(0.2)
    return True
                  