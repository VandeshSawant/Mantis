"""
Action: swipe_up
Performs a vertical swipe from lower screen to upper screen (scroll down content).

Step fields used: none
"""
import time


def run(runner, step):
    size = runner.driver.get_window_size()
    runner.driver.swipe(
        size["width"] // 2, int(size["height"] * 0.7),
        size["width"] // 2, int(size["height"] * 0.3),
        duration=500
    )
    time.sleep(1)
    return True
