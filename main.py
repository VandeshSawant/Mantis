#!/usr/bin/env python
# main.py - Mantis CLI entry point

import argparse
import asyncio
import logging
import sys
import yaml
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def async_main(args):
    """Async entry point for CLI."""
    if args.explore:
        # --- Exploration mode: only import what's needed ---
        from core.app_explorer import AppExplorer

        if not args.app:
            logger.error("--app is required when using --explore")
            sys.exit(1)

        android_home = args.android_home or "C:\\AndroidSDK"

        explorer = AppExplorer(
            android_home=android_home,
            ai_vision_enabled=args.ai_vision_enabled,
            ai_vision_api_base_url=args.ai_vision_api_base_url,
            ai_vision_api_key=args.ai_vision_api_key,
        )

        logger.info(f"Exploring app: {args.app}")
        result = await explorer.explore(
            app_path=args.app,
            max_screens=args.max_screens or 10
        )

        # Save profile
        profile_path = Path("config") / "app_profile.yaml"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(profile_path, "w") as f:
            yaml.dump(result["profile"], f, default_flow_style=False)
        logger.info(f"Saved profile to {profile_path}")

        # Save generated flow(s)
        flows_dir = Path("tests") / "flows"
        flows_dir.mkdir(parents=True, exist_ok=True)
        for flow_name, steps in result["flows"].items():
            flow_data = {
                "flow_name": flow_name.replace("_", " ").title(),
                "description": f"Auto-generated {flow_name}",
                "steps": steps,
            }
            flow_path = flows_dir / f"{flow_name}.yaml"
            with open(flow_path, "w") as f:
                yaml.dump(flow_data, f, default_flow_style=False)
            logger.info(f"Saved flow to {flow_path}")

        logger.info("✅ Exploration complete!")
        return

    # --- Standard test execution (non-exploration) ---
    # Imports are done here to avoid errors when exploration is used
    from core.runner import TestRunner
    from core.parser import parse_goal

    runner = TestRunner()

    if args.goal:
        logger.info(f"Generating flow from goal: {args.goal}")
        flow_data = parse_goal(args.goal)
        if args.save:
            flow_name = args.goal[:30].replace(" ", "_") + ".yaml"
            flow_path = Path("tests/flows") / flow_name
            with open(flow_path, "w") as f:
                yaml.dump({"flow_name": args.goal, "steps": flow_data["steps"]}, f)
            logger.info(f"Saved flow to {flow_path}")
        runner.run_flow(flow_data)
    else:
        runner.run_all_flows()


def main():
    parser = argparse.ArgumentParser(
        description="Mantis - AI-powered mobile QA automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Add an expense of 500 for groceries using cash"
  python main.py --explore --app /path/to/app.apk
  python main.py --explore --app /path/to/app.apk --max-screens 5
        """
    )
    parser.add_argument(
        "goal",
        nargs="?",
        help="Plain English test goal (e.g., 'Add an expense of 500')"
    )
    parser.add_argument(
        "--explore",
        action="store_true",
        help="Explore an app and generate profile and test flows"
    )
    parser.add_argument(
        "--app",
        help="Path to the app APK (required with --explore)"
    )
    parser.add_argument(
        "--max-screens",
        type=int,
        default=10,
        help="Maximum number of screens to explore (default: 10)"
    )
    parser.add_argument(
        "--android-home",
        help="Path to Android SDK (default: C:\\AndroidSDK)"
    )
    parser.add_argument(
        "--ai-vision-enabled",
        action="store_true",
        help="Enable AI vision for element finding (requires API key/URL)"
    )
    parser.add_argument(
        "--ai-vision-api-base-url",
        help="Base URL for vision API (e.g., https://dashscope.aliyuncs.com/compatible-mode/v1)"
    )
    parser.add_argument(
        "--ai-vision-api-key",
        help="API key for vision service"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save generated flow to a YAML file (when using a goal)"
    )

    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()