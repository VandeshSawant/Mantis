"""
Action: launch_app
Forces a clean restart of the configured app — terminates it if running,
then relaunches it. This guarantees every run starts from the app's
initial state, instead of resuming wherever a previous run left off.

Step fields used: none
"""
import time


def run(runner, step):
    app_package = runner.config["devices"][runner.device_key]["app_package"]

    if runner.driver.is_app_installed(app_package):
        runner.driver.terminate_app(app_package)
        time.sleep(1)

    runner.driver.activate_app(app_package)
    time.sleep(2)
    return True