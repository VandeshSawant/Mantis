"""
Action: verify_element_exists
Asserts an element is present on the current screen. Fails (raises) if not found.

Step fields used:
  target.by    - locator strategy
  target.value - locator value
"""


def run(runner, step):
    target = step.get("target", {})
    runner.find_element(target["by"], target["value"])
    return True
