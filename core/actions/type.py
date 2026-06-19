"""
Action: type
Finds a text field, clears it, and types a value into it.

Step fields used:
  target.by    - locator strategy
  target.value - locator value
  value        - text to type
"""
import time


def run(runner, step):
    target = step.get("target", {})
    value = step.get("value", "")
    element = runner.find_element(target["by"], target["value"])
    element.clear()
    element.send_keys(value)
    time.sleep(0.5)
    return True
