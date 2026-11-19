"""Write one session's row into the cost ledger, <QF_COSTS_DIR>/costs.sqlite.

The cost monitoring's stack keeps 15 days; a stage can run longer. So every
session the framework starts (tools/start_session_tool.py, the watcher) and the
person's own session, the orchestrator (the cost monitoring's status line),
keep what they cost in a ledger of their own: one row per session in the table
sessions, kept for the whole project, read by the dashboard's *Cost of a stage*
section through Grafana's SQLite data source (COST_MONITORING.md). One file per
machine holds every product, each row naming its own.

The status line runs this with whatever Python the machine has, so it uses the
standard library only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

__all__ = ["COLUMNS", "COSTS_DIR", "LEDGER", "write_row"]

COSTS_DIR = "QF_COSTS_DIR"  # where the ledger is, from a .env or the environment
LEDGER = "costs.sqlite"
COLUMNS = {
    "id": "TEXT PRIMARY KEY",  # the session: new per started one, Claude's for the orchestrator
    "time": "TEXT",  # when it ended, or was last seen running (ISO 8601, UTC)
    "product": "TEXT",  # the product's repository name
    "pr": "INTEGER",  # the pull request, on the reviewer's side
    "branch": "TEXT",  # the branch, on the author's side, before a pull request exists
    "stage": "TEXT",  # the stage it worked for, as in agent/stages.yaml; none for the orchestrator
    "kind": "TEXT",  # clarify, tester, coder, reviewer, describe_*, expect_cases, orchestrator
    "llm": "TEXT",  # the program that ran it: the command's first word
    "model": "TEXT",  # the model that cost most, where the LLM reports it
    "input_tokens": "INTEGER",
    "output_tokens": "INTEGER",
    "cache_read_tokens": "INTEGER",
    "cache_creation_tokens": "INTEGER",
    "seconds": "REAL",  # how long it ran
    "cost_usd": "REAL",  # list price, where the LLM reports it
    "timed_out": "INTEGER",  # 1: stopped at its time limit, its cost unknown
}


def write_row(folder: Path, row: dict) -> Path:
    """Add the session's row, or replace it when the session wrote one before;
    the ledger. Raises OSError or sqlite3.Error when the folder cannot be written."""
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    ledger = folder / LEDGER
    columns = ", ".join(f"{name} {kind}" for name, kind in COLUMNS.items())
    names = [name for name in COLUMNS if name in row]
    db = sqlite3.connect(ledger, timeout=5)  # another session may be writing
    try:
        with db:
            db.execute(f"CREATE TABLE IF NOT EXISTS sessions ({columns})")
            db.execute(
                f"INSERT OR REPLACE INTO sessions ({', '.join(names)}) "
                f"VALUES ({', '.join('?' for _ in names)})",
                [row[name] for name in names],
            )
    finally:
        db.close()
    return ledger
