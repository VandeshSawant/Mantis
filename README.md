# 🦗 Mantis

**AI-powered mobile QA automation that writes its own tests, heals its own locators, and tells you what broke.**

Mantis is a sanity-testing framework for mobile apps built on top of Appium. Instead of writing brittle, hand-coded UI tests, you describe what you want tested in plain English — Mantis generates the test steps, runs them against your app, automatically repairs broken element locators when your app's UI changes, and produces a visual report of what passed and failed.

Built and tested against a real Android app (an expense-tracking app from the Play Store), not a toy demo.

---

## Why

Mobile UI tests break constantly — a button's resource ID changes, a label gets renamed, a screen gets restructured — and traditional test suites just fail loudly and require a human to go fix the locator. Mantis tries to close that loop automatically, and tries to lower the barrier to writing tests in the first place by letting plain English act as the authoring interface.

---

## Features

- **Plain English → executable test flow.** Describe a goal like _"add an expense of 750 for transport using cash account"_ and an LLM converts it into a structured, reusable YAML test case — no manual locator-hunting required for the first draft.
- **Self-healing locators.** When a step fails because an element can't be found, Mantis captures the current screen's UI hierarchy, sends it to an LLM along with the original step's intent, and gets back a corrected locator. If the fix works, the YAML file is automatically rewritten — so the test gets more reliable every time it breaks, instead of staying broken until someone manually fixes it.
- **Action-based YAML test format.** Every test is a deterministic, human-readable, version-controllable YAML file. The LLM is only used to _author_ or _repair_ tests — it is never in the loop during actual execution, so test runs are fast, repeatable, and don't depend on non-deterministic model output once a flow exists.
- **Visual HTML reports.** Every run produces a self-contained HTML report with a pass/fail summary, per-step results, and embedded screenshots (click to enlarge) for every single action taken.

---

## How it works

```
 Plain English goal
        │
        ▼
 ┌─────────────┐      generates       ┌──────────────────┐
 │   parser.py │ ───────────────────► │  flow.yaml        │
 │  (LLM call) │                      │ (structured steps)│
 └─────────────┘                      └─────────┬─────────┘
                                                 │
                                                 ▼
                                       ┌───────────────────┐
                                       │     runner.py      │
                                       │ executes steps via │
                                       │      Appium        │
                                       └─────────┬──────────┘
                                                 │
                              step fails?        │    step passes
                          ┌──────────────────────┤
                          ▼                      │
                ┌───────────────────┐            │
                │     healer.py      │            │
                │ reads page source, │            │
                │ asks LLM for a fix,│            │
                │  retries once      │            │
                └─────────┬──────────┘            │
                          │ heals YAML if fixed     │
                          ▼                      ▼
                                  ┌────────────────────┐
                                  │   generator.py      │
                                  │ builds HTML report  │
                                  │ with screenshots     │
                                  └────────────────────┘
```

1. **Author** a flow either by hand-writing YAML, or by describing it in plain English (`parser.py` calls an LLM with a system prompt describing the app's known UI elements and the framework's available actions).
2. **Execute** the flow — `runner.py` connects to an Appium session and walks through each step (`tap`, `type`, `tap_digit_sequence`, `verify_text`, etc.), screenshotting after every action.
3. **Heal** on failure — if a locator doesn't match anything on screen, `healer.py` dumps the live UI hierarchy, asks an LLM to suggest a corrected locator based on the step's original intent, and retries once. A successful heal gets written back into the YAML file so future runs don't need healing for that same issue.
4. **Report** — `generator.py` renders a single HTML file per run with pass/fail counts and embedded screenshots for every step.

---

## Project structure

```
mantis/
├── core/
│   ├── runner.py        # Executes YAML test steps via Appium
│   ├── parser.py         # Converts plain English → structured YAML (LLM)
│   └── healer.py          # Self-healing: repairs broken locators at runtime (LLM)
├── tests/
│   └── flows/              # Test cases as YAML (hand-written or LLM-generated)
├── reports/
│   ├── generator.py         # Builds the HTML report
│   └── screenshots/           # Screenshots captured per run
├── config/
│   └── devices.yaml            # Appium/emulator connection config
├── main.py                      # CLI entry point
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.9+
- [Appium server](https://appium.io/) running locally
- An Android emulator (or real device) with your target app installed
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/)) — used for flow generation and self-healing

### Install

```bash
git clone https://github.com/VandeshSawant/Mantis.git
cd mantis
pip install -r requirements.txt
```

### Configure

1. Set your Gemini API key:

   ```bash
   # Windows (PowerShell)
   $env:GEMINI_API_KEY="your-key-here"

   # macOS/Linux
   export GEMINI_API_KEY="your-key-here"
   ```

2. Edit `config/devices.yaml` with your app's package name, main activity, and emulator/device details.

3. Start Appium in a separate terminal:
   ```bash
   appium
   ```

---

## Usage

**Run existing test flows:**

```bash
python main.py
```

**Generate and run a new flow from plain English:**

```bash
python main.py "Add an expense of 500 for groceries using the cash account"
```

This generates a YAML test case under `tests/flows/`, runs it immediately against your connected emulator, and produces an HTML report under `reports/`.

**View a report:**
Open the generated `reports/report_<run_id>.html` file in any browser.

---

## Writing test flows manually

Each flow is a YAML file with a list of steps. Supported actions:

| Action                  | Description                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `launch_app`            | Launches the configured app                                                                                         |
| `wait`                  | Pauses for N seconds                                                                                                |
| `tap`                   | Finds an element and taps it                                                                                        |
| `type`                  | Finds a field and types text into it                                                                                |
| `tap_digit_sequence`    | Taps numeric keypad buttons in sequence (for apps using custom calculator-style input instead of a system keyboard) |
| `swipe_up`              | Performs a vertical swipe                                                                                           |
| `verify_text`           | Asserts an element's text matches an expected value                                                                 |
| `verify_element_exists` | Asserts an element is present on screen                                                                             |

Locator types (`by` field): `id`, `text`, `accessibility`, `xpath`.

Example:

```yaml
flow_name: Add Income in the app
description: Verifies a user can add an income entry
steps:
  - action: launch_app
    description: Launch the expense app
  - action: tap
    description: Tap Add button to open new record screen
    target:
      by: accessibility
      value: Add new record
  - action: tap_digit_sequence
    description: Enter income amount 5000
    value: "5000"
  - action: tap
    description: Save the income entry
    target:
      by: id
      value: com.raha.app.mymoney.free:id/btn_save
```

---

## Roadmap

- [ ] Run history storage (SQLite) for tracking pass-rate trends over time
- [ ] Streamlit chat interface for authoring and triggering runs without the CLI
- [ ] Scheduled runs (cron / CI integration) for true "regular sanity checks"
- [ ] Configurable retry counts and continue-on-failure mode
- [ ] Surface self-healing events directly in the HTML report (currently logged to console + YAML only)

---

## Design notes

The LLM is intentionally kept **out of the execution path**. It's used only to _author_ a test (convert English → YAML) or to _repair_ a broken locator at the moment of failure — never to drive the test run itself. This keeps runs fast, deterministic, and inspectable: every test is a plain YAML file you can read, edit, and diff in version control, regardless of how it was created.

---

## License

MIT
