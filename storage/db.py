"""
Run history storage for Mantis.

Stores one row per flow run (summary-level) and one row per step within
that run (detail-level). The step-level table is what makes flaky-step
detection and screenshot-history lookups possible later — each step row
keeps its screenshot path, so "show me this step's screenshots across the
last N runs" is a simple query, not a manual folder hunt.

Screenshots themselves are NOT stored in the database — only their file
paths are. The actual image files stay on disk under reports/screenshots/,
exactly as they already do today.
"""
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "storage/mantis.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    flow_name       TEXT NOT NULL,
    flow_description TEXT,
    started_at      TEXT NOT NULL,
    total_steps     INTEGER NOT NULL,
    passed_steps    INTEGER NOT NULL,
    failed_steps    INTEGER NOT NULL,
    healed_steps    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL  -- 'passed' or 'failed' (whole-run outcome)
);

CREATE TABLE IF NOT EXISTS steps (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    flow_name         TEXT NOT NULL,
    step_order        INTEGER NOT NULL,
    description       TEXT NOT NULL,
    action            TEXT,
    status            TEXT NOT NULL,   -- 'pass' or 'fail'
    error             TEXT,
    healed            INTEGER NOT NULL DEFAULT 0,  -- 0/1 boolean
    healed_reasoning  TEXT,
    screenshot_path   TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps(run_id);
CREATE INDEX IF NOT EXISTS idx_steps_flow_description ON steps(flow_name, description);
CREATE INDEX IF NOT EXISTS idx_runs_flow_name ON runs(flow_name);
"""


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist yet. Safe to call every time."""
    with _connect() as conn:
        conn.executescript(SCHEMA)


def save_run(summary, flow_name=None, flow_description=None):
    """
    Persist a completed run's summary (as returned by TestRunner.run_flow())
    into the database. Call this once, after a run finishes.
    """
    init_db()

    run_id = summary["run_id"]
    total = summary["total"]
    passed = summary["passed"]
    failed = summary["failed"]
    healed_count = summary.get("healed_count", 0)
    overall_status = "passed" if failed == 0 else "failed"
    flow_name = flow_name or summary.get("flow_name", "unknown_flow")

    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO runs
               (run_id, flow_name, flow_description, started_at,
                total_steps, passed_steps, failed_steps, healed_steps, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, flow_name, flow_description, datetime.now().isoformat(),
             total, passed, failed, healed_count, overall_status)
        )

        for i, step in enumerate(summary["results"]):
            conn.execute(
                """INSERT INTO steps
                   (run_id, flow_name, step_order, description, action,
                    status, error, healed, healed_reasoning, screenshot_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, flow_name, i, step.get("step", ""), step.get("action", ""),
                 step.get("status", ""), step.get("error"),
                 1 if step.get("healed") else 0, step.get("healed_reasoning"),
                 step.get("screenshot"))
            )

    print(f"💾 Run history saved ({len(summary['results'])} steps recorded)")


def get_run_history(flow_name=None, limit=50):
    """Return recent runs, optionally filtered by flow_name, most recent first."""
    init_db()
    with _connect() as conn:
        if flow_name:
            rows = conn.execute(
                "SELECT * FROM runs WHERE flow_name = ? ORDER BY started_at DESC LIMIT ?",
                (flow_name, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_pass_rate_trend(flow_name):
    """Return [(started_at, pass_rate_percent), ...] for a given flow, oldest first."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT started_at, passed_steps, total_steps
               FROM runs WHERE flow_name = ? ORDER BY started_at ASC""",
            (flow_name,)
        ).fetchall()
        trend = []
        for r in rows:
            rate = round((r["passed_steps"] / r["total_steps"]) * 100) if r["total_steps"] else 0
            trend.append((r["started_at"], rate))
        return trend


def get_step_history(flow_name, description, limit=20):
    """
    Return recent occurrences of a specific step (matched by flow_name + description)
    across past runs, most recent first. Useful for:
      - flaky-step detection (look at status across occurrences)
      - screenshot history (compare screenshot_path across occurrences over time)
    """
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT s.*, r.started_at FROM steps s
               JOIN runs r ON s.run_id = r.run_id
               WHERE s.flow_name = ? AND s.description = ?
               ORDER BY r.started_at DESC LIMIT ?""",
            (flow_name, description, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_flaky_steps(flow_name=None, min_occurrences=3):
    """
    Return steps that have BOTH passed and failed across their recorded history
    (a step that's always pass or always fail isn't flaky, just consistently
    good or consistently broken). Each result includes pass/fail counts.
    """
    init_db()
    with _connect() as conn:
        query = """
            SELECT flow_name, description,
                   COUNT(*) as total_occurrences,
                   SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as pass_count,
                   SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as fail_count
            FROM steps
        """
        params = []
        if flow_name:
            query += " WHERE flow_name = ?"
            params.append(flow_name)
        query += " GROUP BY flow_name, description HAVING total_occurrences >= ? AND pass_count > 0 AND fail_count > 0"
        params.append(min_occurrences)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_healing_events(flow_name=None, limit=50):
    """Return steps that required self-healing, most recent first. Useful as an
    audit trail — frequent healing on the same step suggests real instability,
    even if every individual run reports a pass."""
    init_db()
    with _connect() as conn:
        query = """SELECT s.*, r.started_at FROM steps s
                   JOIN runs r ON s.run_id = r.run_id
                   WHERE s.healed = 1"""
        params = []
        if flow_name:
            query += " AND s.flow_name = ?"
            params.append(flow_name)
        query += " ORDER BY r.started_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]