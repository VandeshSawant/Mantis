"""
Action: launch_app
Activates/launches the configured app on the device.

Step fields used: none
"""
import time


def run(runner, step):
    app_package = runner.config["devices"][runner.device_key]["app_package"]
    runner.driver.activate_app(app_package)
    time.sleep(2)
    return True
