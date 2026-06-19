"""
Action: tap
Finds an element and clicks it.

Step fields used:
  target.by    - locator strategy (id, text, xpath, accessibility)
  target.value - locator value
"""
import time


def run(runner, step):
    target = step.get("target", {})
    element = runner.find_element(target["by"], target["value"])
    element.click()
    time.sleep(1)
    return True
