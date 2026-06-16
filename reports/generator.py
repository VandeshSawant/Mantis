import os
import base64
from datetime import datetime
from jinja2 import Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QA Test Report — {{ run_id }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #1a1a2e; }
        
        .header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 40px; }
        .header h1 { font-size: 28px; font-weight: 700; margin-bottom: 6px; }
        .header p { opacity: 0.6; font-size: 14px; }

        .summary { display: flex; gap: 20px; padding: 30px 40px; flex-wrap: wrap; }
        .card { background: white; border-radius: 12px; padding: 24px 32px; flex: 1; min-width: 160px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }
        .card .number { font-size: 42px; font-weight: 700; margin-bottom: 4px; }
        .card .label { font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        .card.total .number { color: #1a1a2e; }
        .card.passed .number { color: #22c55e; }
        .card.failed .number { color: #ef4444; }
        .card.duration .number { color: #6366f1; font-size: 28px; padding-top: 8px; }

        .flows { padding: 0 40px 40px; }
        .flow-block { background: white; border-radius: 12px; margin-bottom: 24px;
                      box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden; }
        .flow-header { padding: 20px 28px; border-bottom: 1px solid #f0f0f0;
                       display: flex; align-items: center; justify-content: space-between; }
        .flow-header h2 { font-size: 18px; font-weight: 600; }
        .flow-header p { font-size: 13px; color: #888; margin-top: 3px; }
        .badge { padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .badge.pass { background: #dcfce7; color: #16a34a; }
        .badge.fail { background: #fee2e2; color: #dc2626; }

        .steps { padding: 16px 0; }
        .step { display: flex; align-items: flex-start; gap: 16px; padding: 12px 28px;
                border-bottom: 1px solid #fafafa; transition: background 0.15s; }
        .step:last-child { border-bottom: none; }
        .step:hover { background: #fafafa; }
        .step-icon { font-size: 18px; margin-top: 2px; flex-shrink: 0; }
        .step-info { flex: 1; }
        .step-name { font-size: 14px; font-weight: 500; margin-bottom: 3px; }
        .step-meta { font-size: 12px; color: #aaa; }
        .step-error { font-size: 12px; color: #ef4444; margin-top: 4px;
                      background: #fff5f5; padding: 6px 10px; border-radius: 6px; border-left: 3px solid #ef4444; }
        .step-thumb { width: 48px; height: 80px; object-fit: cover; border-radius: 6px;
                      cursor: pointer; border: 2px solid #f0f0f0; flex-shrink: 0; }
        .step-thumb:hover { border-color: #6366f1; transform: scale(1.05); transition: all 0.2s; }

        /* Lightbox */
        .lightbox { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85);
                    z-index: 1000; align-items: center; justify-content: center; }
        .lightbox.active { display: flex; }
        .lightbox img { max-width: 90vw; max-height: 90vh; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.5); }
        .lightbox-close { position: absolute; top: 20px; right: 28px; color: white;
                          font-size: 32px; cursor: pointer; line-height: 1; }

        .footer { text-align: center; padding: 30px; color: #aaa; font-size: 13px; }
    </style>
</head>
<body>

<div class="header">
    <h1>🧪 QA Sanity Report</h1>
    <p>Run ID: {{ run_id }} &nbsp;·&nbsp; Generated: {{ generated_at }}</p>
</div>

<div class="summary">
    <div class="card total">
        <div class="number">{{ total_steps }}</div>
        <div class="label">Total Steps</div>
    </div>
    <div class="card passed">
        <div class="number">{{ total_passed }}</div>
        <div class="label">Passed</div>
    </div>
    <div class="card failed">
        <div class="number">{{ total_failed }}</div>
        <div class="label">Failed</div>
    </div>
    <div class="card duration">
        <div class="number">{{ pass_rate }}%</div>
        <div class="label">Pass Rate</div>
    </div>
</div>

<div class="flows">
    {% for flow in flows %}
    <div class="flow-block">
        <div class="flow-header">
            <div>
                <h2>{{ flow.flow_name }}</h2>
                <p>{{ flow.passed }}/{{ flow.total }} steps passed</p>
            </div>
            <span class="badge {{ 'pass' if flow.failed == 0 else 'fail' }}">
                {{ 'PASSED' if flow.failed == 0 else 'FAILED' }}
            </span>
        </div>
        <div class="steps">
            {% for step in flow.results %}
            <div class="step">
                <div class="step-icon">{{ '✅' if step.status == 'pass' else '❌' }}</div>
                <div class="step-info">
                    <div class="step-name">{{ step.step }}</div>
                    <div class="step-meta">Action: {{ step.action }}{% if step.expected %} &nbsp;·&nbsp; Expected: {{ step.expected }}{% endif %}</div>
                    {% if step.error %}
                    <div class="step-error">⚠ {{ step.error }}</div>
                    {% endif %}
                </div>
                {% if step.screenshot %}
                <img class="step-thumb" src="{{ step.screenshot }}" 
                     onclick="openLightbox(this.src)" 
                     alt="Screenshot: {{ step.step }}" />
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</div>

<div class="footer">Generated by QA Agent &nbsp;·&nbsp; {{ generated_at }}</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <span class="lightbox-close" onclick="closeLightbox()">✕</span>
    <img id="lightbox-img" src="" alt="Screenshot" onclick="event.stopPropagation()" />
</div>

<script>
    function openLightbox(src) {
        document.getElementById('lightbox-img').src = src;
        document.getElementById('lightbox').classList.add('active');
    }
    function closeLightbox() {
        document.getElementById('lightbox').classList.remove('active');
    }
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });
</script>

</body>
</html>
"""

def encode_screenshot(path):
    """Convert screenshot to base64 so it's embedded in the HTML."""
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""

def generate_report(summaries, output_dir="reports"):
    """
    Generate an HTML report from one or more flow summaries.
    summaries: list of dicts returned by runner.run_flow()
    """
    os.makedirs(output_dir, exist_ok=True)

    run_id = summaries[0]["run_id"] if summaries else "unknown"
    generated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Embed screenshots as base64
    flows = []
    total_passed = 0
    total_failed = 0

    for summary in summaries:
        for step in summary["results"]:
            if step.get("screenshot"):
                step["screenshot"] = encode_screenshot(step["screenshot"])

        flows.append({
            "flow_name": summary.get("flow_name", "Unnamed Flow"),
            "total":     summary["total"],
            "passed":    summary["passed"],
            "failed":    summary["failed"],
            "results":   summary["results"],
        })
        total_passed += summary["passed"]
        total_failed += summary["failed"]

    total_steps = total_passed + total_failed
    pass_rate = round((total_passed / total_steps) * 100) if total_steps > 0 else 0

    template = Template(HTML_TEMPLATE)
    html = template.render(
        run_id=run_id,
        generated_at=generated_at,
        total_steps=total_steps,
        total_passed=total_passed,
        total_failed=total_failed,
        pass_rate=pass_rate,
        flows=flows,
    )

    report_path = os.path.join(output_dir, f"report_{run_id}.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n📊 Report saved: {report_path}")
    return report_path