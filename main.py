import sys
import yaml
from core.runner import TestRunner
from core.parser import FlowParser
from reports.generator import generate_report

def run_flow_from_file(flow_path, device="android_emulator"):
    with open(flow_path, "r") as f:
        flow = yaml.safe_load(f)
    return run_flow(flow, device, flow_path=flow_path)

def run_flow_from_goal(goal_text, device="android_emulator", save_path=None):
    parser = FlowParser()
    print(f"🤖 Generating test steps for: \"{goal_text}\"")
    flow = parser.parse(goal_text, save_path=save_path)
    print(f"✅ Generated flow: {flow['flow_name']} ({len(flow['steps'])} steps)\n")
    return run_flow(flow, device, flow_path=save_path)

def run_flow(flow, device="android_emulator", flow_path=None):
    print(f"\nRunning flow: {flow['flow_name']}")
    print(f"Description: {flow['description']}\n")

    runner = TestRunner(device_key=device)
    summary = runner.run_flow(
        flow["steps"],
        flow_path=flow_path,
        flow_name=flow.get("flow_name"),
        flow_description=flow.get("description"),
    )
    summary["flow_name"] = flow["flow_name"]
    return summary

if __name__ == "__main__":
    summaries = []

    if len(sys.argv) > 1:
        # Plain English mode: python main.py "add an expense of 200 for groceries"
        goal = " ".join(sys.argv[1:])
        summaries.append(run_flow_from_goal(
            goal,
            save_path=f"tests/flows/generated_{abs(hash(goal)) % 10000}.yaml"
        ))
    else:
        # Default: run saved flows
        summaries.append(run_flow_from_file("tests/flows/add_income.yaml"))
        # summaries.append(run_flow_from_file("tests/flows/add_expense.yaml"))

    generate_report(summaries)