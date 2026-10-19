"""Write the tech stack as the table the architect reads at checkpoint 3.

One Markdown row per row of the stack (stack.v2): Area, Tool, Version, Status —
chosen, or not needed with its reason. The areas every stack holds come first,
in the order of AREAS, then the product's own. The agent puts the table in the
checkpoint-3 request and in the pull request; the stack file stays the source
(decision 10 of the architecture stage).

    python tools/write_stack_table_tool.py [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_product_config_tool import ConfigError, read_product_config  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

__all__ = ["AREAS", "GIVEN", "NEEDED", "stack_table"]

# Every stack holds these areas.
AREAS = (
    "language",
    "runtime",
    "package_manager",
    "frameworks",
    "libraries",
    "data_stores",
    "llm",
    "external_services",
    "test_runner",
    "lint",
    "format",
    "static_analysis",
    "secrets_scanner",
    "dependencies_scanner",
    "build",
    "deployment",
    "version_control",
    "ci_cd",
    "task_management",
    "requirements_engineering",
    "documentation",
    "diagram_tool",
)
# The areas a product cannot do without: the gates run their tools.
NEEDED = ("language", "test_runner", "lint", "format", "secrets_scanner", "dependencies_scanner")
# The areas the framework gives: the host's tool, or the qf.yaml slot that names it.
GIVEN = {
    "version_control": "GitHub",
    "ci_cd": "GitHub Actions",
    "task_management": "GitHub Issues",
    "requirements_engineering": "slot:create_requirements_plugin",
    "diagram_tool": "slot:create_diagram_plugin",
}


def stack_table(rows: list[dict]) -> str:
    """The rows as a Markdown table, the framework's areas first."""
    order = {area: i for i, area in enumerate(AREAS)}
    ranked = sorted(enumerate(rows), key=lambda p: (order.get(p[1]["area"], len(AREAS)), p[0]))
    lines = ["| Area | Tool | Version | Status |", "|---|---|---|---|"]
    for _, row in ranked:
        if "tool" in row:
            cells = [row["tool"], row.get("version", "—"), "chosen"]
        else:
            cells = ["—", "—", f"not needed: {row['not_needed']}"]
        lines.append("| " + " | ".join([row["area"], *(_cell(c) for c in cells)]) + " |")
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        print(err.message, file=sys.stderr)
        return 2
    stack = read_stack(config)
    if stack is None:
        print("The stack is missing or invalid: nothing to write.", file=sys.stderr)
        return 2
    print(stack_table(stack["areas"]), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
