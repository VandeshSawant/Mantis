"""
Action: wait
Pauses execution for a given number of seconds.

Step fields used:
  value - number of seconds to wait (string or number)
"""
import time


def run(runner, step):
    seconds = int(step.get("value", 1))
    time.sleep(seconds)
    return True
