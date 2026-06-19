"""
Action: verify_text
Finds an element and asserts its text contains the expected value.

Step fields used:
  target.by    - locator strategy
  target.value - locator value
  expected     - substring expected to appear in the element's text
"""


def run(runner, step):
    target = step.get("target", {})
    expected = step.get("expected", "")
    element = runner.find_element(target["by"], target["value"])
    actual_text = element.text
    if expected.lower() not in actual_text.lower():
        raise AssertionError(f"Expected '{expected}' but found '{actual_text}'")
    return True
